"""OpenRouter free-model discovery and structured JSON chat client."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import os
from threading import Lock
from typing import Any, Generic, Sequence, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError


DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
SchemaT = TypeVar("SchemaT", bound=BaseModel)


class DiagnosisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    known: list[str]
    unknown: list[str]
    hypothesis: str
    next_action: str
    target_files: list[str]


class PatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    diff: str


class JudgeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    genuine_fix: bool
    reasoning: str


@dataclass(frozen=True)
class ModelDiscoveryResult:
    available: bool
    models: list[str]
    error: str | None = None


@dataclass(frozen=True)
class StructuredResponse(Generic[SchemaT]):
    success: bool
    status: str
    data: SchemaT | None
    model_id: str | None
    raw_content: str | None
    error: str | None = None


def _is_zero_priced(model: dict[str, Any]) -> bool:
    pricing = model.get("pricing")
    if not isinstance(pricing, dict) or not pricing:
        return False
    try:
        return all(Decimal(str(value)) == Decimal("0") for value in pricing.values())
    except (InvalidOperation, ValueError):
        return False


def _supports_text_chat(model: dict[str, Any]) -> bool:
    architecture = model.get("architecture")
    if not isinstance(architecture, dict):
        return False
    input_modalities = architecture.get("input_modalities")
    output_modalities = architecture.get("output_modalities")
    if isinstance(input_modalities, list) and isinstance(output_modalities, list):
        return "text" in input_modalities and "text" in output_modalities
    return architecture.get("modality") == "text->text"

# Preference-ordered model IDs. If any of these are discovered as eligible free
# models, they are promoted to the front of the fallback list in this order.
# All other discovered models keep their alphabetical position after the preferred ones.
# This is NOT a hardcoded-only list — it augments live discovery, never replaces it.
PREFERRED_MODEL_ORDER: list[str] = [
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "minimax/minimax-m3:free",
    "poolside/laguna-xs-2.1:free",
    "openrouter/free",
    "z-ai/glm-5.2:free",
]


def _eligible_model_ids(payload: Any) -> list[str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return []
    model_ids = [
        model["id"]
        for model in payload["data"]
        if isinstance(model, dict)
        and isinstance(model.get("id"), str)
        and _is_zero_priced(model)
        and _supports_text_chat(model)
    ]
    unique = sorted(set(model_ids))
    return _apply_preference_order(unique)


def _apply_preference_order(model_ids: list[str]) -> list[str]:
    """Promote preferred models to the front, preserving their preference rank."""
    preferred = [mid for mid in PREFERRED_MODEL_ORDER if mid in model_ids]
    rest = [mid for mid in model_ids if mid not in PREFERRED_MODEL_ORDER]
    return preferred + rest


class OpenRouterClient:
    """Synchronous client intended to be initialized during application startup."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 20.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY")
        self._base_url = (base_url or os.getenv("OPENROUTER_BASE_URL") or DEFAULT_OPENROUTER_BASE_URL).rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._http = http_client or httpx.Client(timeout=timeout_seconds)
        self._models: list[str] = []
        self._call_count = 0
        self._call_count_lock = Lock()

    @property
    def model_ids(self) -> tuple[str, ...]:
        return tuple(self._models)

    @property
    def call_count(self) -> int:
        with self._call_count_lock:
            return self._call_count

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    def for_job(self) -> "OpenRouterClient":
        """Create an independently counted client using startup-discovered models."""

        client = OpenRouterClient(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout_seconds=self._timeout_seconds,
            http_client=self._http,
        )
        client._models = list(self._models)
        return client

    def discover_models(self) -> ModelDiscoveryResult:
        """Fetch and retain the ordered, eligible free-model fallback list."""

        self._models = []
        if not self._api_key:
            return ModelDiscoveryResult(False, [], "OPENROUTER_API_KEY is not configured.")
        try:
            response = self._http.get(
                f"{self._base_url}/models",
                headers=self._headers,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            self._models = _eligible_model_ids(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            return ModelDiscoveryResult(False, [], f"Model discovery failed: {exc}")

        if not self._models:
            return ModelDiscoveryResult(False, [], "No eligible free text chat models are available.")
        return ModelDiscoveryResult(True, list(self._models))

    def request_structured(
        self,
        messages: Sequence[dict[str, str]],
        schema: type[SchemaT],
    ) -> StructuredResponse[SchemaT]:
        """Request strict JSON, retrying exactly once if the output is malformed."""

        if not self._models:
            return StructuredResponse(False, "model_unavailable", None, None, None, "No eligible free model is available.")

        last_error: str | None = None
        for model_id in self._models:
            first = self._request_once(model_id, messages, schema)
            if first.success:
                return first
            if first.status == "malformed_output":
                retry = self._request_once(model_id, messages, schema)
                if retry.success:
                    return retry
                if retry.status == "malformed_output":
                    return StructuredResponse(
                        False,
                        "malformed_output",
                        None,
                        model_id,
                        retry.raw_content,
                        "Structured output remained invalid after one retry.",
                    )
                return retry
            last_error = first.error

        return StructuredResponse(False, "request_failed", None, None, None, last_error or "All fallback models failed.")

    def _request_once(
        self,
        model_id: str,
        messages: Sequence[dict[str, str]],
        schema: type[SchemaT],
    ) -> StructuredResponse[SchemaT]:
        with self._call_count_lock:
            self._call_count += 1
        payload = {
            "model": model_id,
            "messages": list(messages),
            "response_format": {"type": "json_object"},
        }
        try:
            response = self._http.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers,
                json=payload,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return StructuredResponse(False, "request_failed", None, model_id, None, f"LLM request failed: {exc}")

        try:
            content = response.json()["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Chat completion content must be a JSON string.")
            text = content.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()
            parsed = schema.model_validate(json.loads(text))
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
            return StructuredResponse(False, "malformed_output", None, model_id, locals().get("content"), str(exc))
        return StructuredResponse(True, "completed", parsed, model_id, content)
