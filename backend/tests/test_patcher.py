from __future__ import annotations

import json
from pathlib import Path

import httpx

from backend.agent.llm_client import OpenRouterClient
from backend.agent.patcher import PatchContext, apply_unified_diff, generate_patch


VALID_DIFF = "--- a/calculator.py\n+++ b/calculator.py\n@@ -1,2 +1,2 @@\n def add(left, right):\n-    return left - right\n+    return left + right\n"


def _client(content: str) -> OpenRouterClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(
                200,
                json={"data": [{"id": "free", "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]}}]},
            )
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = OpenRouterClient(api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.discover_models().available
    return client


def _context() -> PatchContext:
    return PatchContext(
        hypothesis="The subtraction operator should be addition.",
        target_files=["calculator.py"],
        source_files={"calculator.py": "def add(left, right):\n    return left - right\n"},
    )


def test_generate_patch_returns_valid_unified_diff() -> None:
    result = generate_patch(_client(json.dumps({"diff": VALID_DIFF})), _context())

    assert result.success is True
    assert result.status == "generated"
    assert result.diff == VALID_DIFF


def test_apply_unified_diff_updates_only_copy(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "patched"
    source.mkdir()
    original = "def add(left, right):\n    return left - right\n"
    (source / "calculator.py").write_text(original, encoding="utf-8")

    result = apply_unified_diff(source, destination, VALID_DIFF)

    assert result.success is True
    assert result.applied is True
    assert result.status == "applied"
    assert result.patched_files == ["calculator.py"]
    assert (source / "calculator.py").read_text(encoding="utf-8") == original
    assert (destination / "calculator.py").read_text(encoding="utf-8") == "def add(left, right):\n    return left + right\n"


def test_generate_patch_rejects_malformed_llm_output() -> None:
    result = generate_patch(_client("{}"), _context())

    assert result.success is False
    assert result.status == "malformed_output"


def test_apply_unified_diff_rejects_unapplicable_or_unsafe_diff(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "calculator.py").write_text("value = 1\n", encoding="utf-8")
    invalid = "--- a/calculator.py\n+++ b/calculator.py\n@@ -1 +1 @@\n-value = 2\n+value = 3\n"
    unsafe = "--- a/../../outside.py\n+++ b/../../outside.py\n@@ -1 +1 @@\n-x\n+y\n"

    invalid_result = apply_unified_diff(source, tmp_path / "invalid", invalid)
    unsafe_result = apply_unified_diff(source, tmp_path / "unsafe", unsafe)

    assert invalid_result.success is False
    assert invalid_result.status == "application_failed"
    assert unsafe_result.success is False
    assert "escapes the workspace" in (unsafe_result.error or "")
    assert not (tmp_path / "outside.py").exists()


def test_apply_unified_diff_tolerates_missing_context_space_and_count_discrepancy(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "patched"
    source.mkdir()
    original = "def take_first_n(elements, count):\n    return elements[:count - 1]\n\ndata = [1, 2, 3]\n"
    (source / "snippet.py").write_text(original, encoding="utf-8")

    # LLM diff missing leading space on context lines and with slightly miscounted hunk header
    diff = (
        "--- a/snippet.py\n"
        "+++ b/snippet.py\n"
        "@@ -1,3 +1,3 @@\n"
        "def take_first_n(elements, count):\n"
        "-    return elements[:count - 1]\n"
        "+    return elements[:count]\n"
        "\n"
        "data = [1, 2, 3]\n"
    )

    result = apply_unified_diff(source, destination, diff)
    assert result.success is True
    assert result.applied is True
    assert (destination / "snippet.py").read_text(encoding="utf-8") == (
        "def take_first_n(elements, count):\n    return elements[:count]\n\ndata = [1, 2, 3]\n"
    )

