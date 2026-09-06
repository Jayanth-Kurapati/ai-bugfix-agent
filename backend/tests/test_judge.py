from __future__ import annotations

import json

import httpx

from backend.agent.judge import JudgeContext, build_judge_messages, judge_fix
from backend.agent.llm_client import OpenRouterClient


def _client(contents: list[str]) -> OpenRouterClient:
    completion_index = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal completion_index
        if request.url.path.endswith("/models"):
            return httpx.Response(
                200,
                json={"data": [{"id": "free", "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]}}]},
            )
        content = contents[completion_index]
        completion_index += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = OpenRouterClient(api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.discover_models().available
    return client


def _context() -> JudgeContext:
    return JudgeContext(
        bug_report="add(1, 2) returns -1 instead of 3",
        final_diff="--- a/calculator.py\n+++ b/calculator.py\n@@ -1,2 +1,2 @@\n-    return left - right\n+    return left + right\n",
        verification_output="1 passed in 0.01s",
        source_files={"calculator.py": "def add(left, right):\n    return left + right\n"},
    )


def test_judge_returns_verified_fix_verdict() -> None:
    client = _client([json.dumps({"genuine_fix": True, "reasoning": "The operator correction matches the report and test."})])

    result = judge_fix(client, _context())

    assert result.success is True
    assert result.verdict is not None
    assert result.verdict.genuine_fix is True


def test_judge_returns_rejected_verdict() -> None:
    client = _client([json.dumps({"genuine_fix": False, "reasoning": "The patch only weakens the assertion."})])

    result = judge_fix(client, _context())

    assert result.success is True
    assert result.verdict is not None
    assert result.verdict.genuine_fix is False


def test_judge_uses_malformed_output_retry() -> None:
    client = _client(["not-json", json.dumps({"genuine_fix": True, "reasoning": "Verified."})])

    result = judge_fix(client, _context())

    assert result.success is True
    assert result.verdict is not None
    assert result.verdict.genuine_fix is True
    assert client.call_count == 2


def test_judge_prompt_includes_relevant_evidence_as_untrusted_data() -> None:
    messages = build_judge_messages(_context())

    assert "independent bug-fix judge" in messages[0]["content"]
    assert "BUG_REPORT" in messages[1]["content"]
    assert "FINAL_DIFF" in messages[1]["content"]
    assert "VERIFICATION_OUTPUT" in messages[1]["content"]
    assert "SOURCE_FILE path=calculator.py" in messages[1]["content"]
