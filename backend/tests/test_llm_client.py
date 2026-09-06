from __future__ import annotations

import json

import httpx

from backend.agent.llm_client import DiagnosisResponse, OpenRouterClient


def _model(model_id: str, *, price: str = "0", text: bool = True) -> dict:
    architecture = {"input_modalities": ["text"], "output_modalities": ["text"]} if text else {
        "input_modalities": ["image"],
        "output_modalities": ["text"],
    }
    return {"id": model_id, "pricing": {"prompt": price, "completion": price}, "architecture": architecture}


def _client(handler) -> OpenRouterClient:
    return OpenRouterClient(api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def _diagnosis_content() -> str:
    return json.dumps(
        {"known": ["x"], "unknown": [], "hypothesis": "broken", "next_action": "patch", "target_files": ["a.py"]}
    )


def test_discovery_keeps_only_free_text_models_in_stable_fallback_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/models"
        return httpx.Response(200, json={"data": [_model("z-free"), _model("paid", price="0.1"), _model("image-free", text=False), _model("a-free")]})

    client = _client(handler)
    result = client.discover_models()

    assert result.available is True
    assert result.models == ["a-free", "z-free"]
    assert client.model_ids == ("a-free", "z-free")


def test_discovery_returns_model_unavailable_without_key_or_eligible_models() -> None:
    missing_key = OpenRouterClient(api_key="", http_client=httpx.Client(transport=httpx.MockTransport(lambda request: None)))
    assert missing_key.discover_models().available is False

    client = _client(lambda request: httpx.Response(200, json={"data": [_model("paid", price="1")] }))
    result = client.discover_models()

    assert result.available is False
    assert result.error == "No eligible free text chat models are available."


def test_structured_response_is_validated_and_counted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [_model("free")]})
        return httpx.Response(200, json={"choices": [{"message": {"content": _diagnosis_content()}}]})

    client = _client(handler)
    client.discover_models()
    result = client.request_structured([{"role": "user", "content": "diagnose"}], DiagnosisResponse)

    assert result.success is True
    assert result.data is not None
    assert result.data.hypothesis == "broken"
    assert client.call_count == 1


def test_malformed_structured_output_retries_once_then_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [_model("free")]})
        calls += 1
        content = "not-json" if calls == 1 else _diagnosis_content()
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = _client(handler)
    client.discover_models()
    result = client.request_structured([], DiagnosisResponse)

    assert result.success is True
    assert client.call_count == 2


def test_second_malformed_response_fails_clearly_without_extra_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [_model("free")]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "[]"}}]})

    client = _client(handler)
    client.discover_models()
    result = client.request_structured([], DiagnosisResponse)

    assert result.status == "malformed_output"
    assert result.success is False
    assert client.call_count == 2


def test_request_failure_uses_next_fallback_model() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [_model("first"), _model("second")]})
        model_id = json.loads(request.content)["model"]
        calls.append(model_id)
        if model_id == "first":
            return httpx.Response(503, json={"error": "unavailable"})
        return httpx.Response(200, json={"choices": [{"message": {"content": _diagnosis_content()}}]})

    client = _client(handler)
    client.discover_models()
    result = client.request_structured([], DiagnosisResponse)

    assert result.success is True
    assert result.model_id == "second"
    assert calls == ["first", "second"]
    assert client.call_count == 2
