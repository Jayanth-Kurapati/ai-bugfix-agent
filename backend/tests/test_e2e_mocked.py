"""Full mocked SSE round-trip: submit → stream all trace event kinds → final state.

This test exercises the complete API/SSE flow with a fake orchestrator that
emits every trace event kind the frontend expects, then asserts the SSE
stream and poll endpoint return the correct full state.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.agent.orchestrator import OrchestrationResult, TraceEvent
from backend.api import routes
from backend.main import app
from backend.sandbox.runner import SandboxResult


FAKE_DIFF = """\
--- a/snippet.py
+++ b/snippet.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
"""


def _snippet_payload() -> dict:
    return {
        "mode": "snippet",
        "code": "def add(a, b):\n    return a - b\n",
        "test_type": "pytest",
        "test_content": "def test_add():\n    from snippet import add\n    assert add(2, 3) == 5\n",
    }


def _full_trace_events() -> list[TraceEvent]:
    """Produce the exact sequence of trace events the orchestrator emits on a
    successful single-iteration fix."""
    return [
        TraceEvent("LINT", "Lint completed.", {"findings": 1, "exit_code": 0}),
        TraceEvent("KNOWN", "Diagnosis known facts.", {"values": ["add function exists", "test expects 5"]}),
        TraceEvent("UNKNOWN", "Diagnosis unknowns.", {"values": ["operator correctness"]}),
        TraceEvent("HYPOTHESIS", "The function uses subtraction instead of addition."),
        TraceEvent("NEXT ACTION", "Patch the operator.", {"target_files": ["snippet.py"]}),
        TraceEvent("PATCH", "Diff generated.", {}),
        TraceEvent("PATCH", "Diff applied.", {"patched_files": ["snippet.py"]}),
        TraceEvent("VERIFY", "Verification passed.", {"exit_code": 0, "stdout": "1 passed", "stderr": ""}),
        TraceEvent("JUDGE", "Judge verdict received.", {"genuine_fix": True, "reasoning": "Operator changed from - to +."}),
        TraceEvent("FINAL", "verified", {}),
    ]


def _fake_run(request, client, *, max_iterations=3, on_event=None):
    """Replacement for run_analysis that emits the full trace."""
    events = _full_trace_events()
    for event in events:
        if on_event is not None:
            on_event(event)
    verification = SandboxResult(True, 0, "1 passed", "", True, "pass", None)
    return OrchestrationResult(
        "verified", events, FAKE_DIFF, verification, True, "Operator changed from - to +.", 4
    )


def test_full_mocked_sse_round_trip(monkeypatch) -> None:
    """Submit a snippet job with a fake orchestrator, consume the SSE stream,
    and verify every trace event kind appears in the correct order."""
    monkeypatch.setattr(routes, "run_analysis", _fake_run)

    with TestClient(app) as client:
        # --- Submit ---
        create = client.post("/api/analyze", json=_snippet_payload())
        assert create.status_code == 201
        job_id = create.json()["job_id"]

        # --- SSE Stream ---
        stream = client.get(f"/api/jobs/{job_id}/stream")
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")

        # Parse SSE events
        trace_events = []
        final_data = None
        for line in stream.text.splitlines():
            if line.startswith("data: "):
                payload = json.loads(line[len("data: "):])
                if "kind" in payload:
                    trace_events.append(payload)
                elif "job_id" in payload:
                    final_data = payload

        # Verify all expected event kinds appeared
        expected_kinds = ["LINT", "KNOWN", "UNKNOWN", "HYPOTHESIS", "NEXT ACTION",
                          "PATCH", "PATCH", "VERIFY", "JUDGE", "FINAL"]
        actual_kinds = [e["kind"] for e in trace_events]
        assert actual_kinds == expected_kinds, f"Expected {expected_kinds}, got {actual_kinds}"

        # Verify specific event content
        lint_event = trace_events[0]
        assert lint_event["data"]["findings"] == 1

        known_event = trace_events[1]
        assert "add function exists" in known_event["data"]["values"]

        hypothesis_event = trace_events[3]
        assert "subtraction" in hypothesis_event["message"]

        judge_event = trace_events[8]
        assert judge_event["data"]["genuine_fix"] is True
        assert "Operator" in judge_event["data"]["reasoning"]

        # Verify final SSE event has correct terminal state
        assert final_data is not None, "No 'final' SSE event received"
        assert final_data["status"] == "verified"
        assert final_data["llm_call_count"] == 4
        assert final_data["judge_verdict"] is True
        assert final_data["diff"].startswith("--- a/snippet.py")

        # --- Poll fallback ---
        poll = client.get(f"/api/jobs/{job_id}")
        assert poll.status_code == 200
        job = poll.json()
        assert job["status"] == "verified"
        assert job["llm_call_count"] == 4
        assert job["iteration_count"] == 1  # one HYPOTHESIS event
        assert job["judge_verdict"] is True
        assert job["judge_reasoning"] == "Operator changed from - to +."
        assert job["diff"] == FAKE_DIFF
        assert len(job["trace"]) == 10  # all 10 events


def test_mocked_failed_job_round_trip(monkeypatch) -> None:
    """A job that fails after diagnosis produces the correct error state."""
    def fail_run(request, client, *, max_iterations=3, on_event=None):
        events = [
            TraceEvent("LINT", "Lint completed.", {"findings": 0, "exit_code": 0}),
            TraceEvent("KNOWN", "Diagnosis known facts.", {"values": []}),
            TraceEvent("UNKNOWN", "Diagnosis unknowns.", {"values": ["everything"]}),
            TraceEvent("HYPOTHESIS", "Unable to determine the bug."),
            TraceEvent("FINAL", "failed", {"error": "Diagnosis produced no actionable result."}),
        ]
        for event in events:
            if on_event is not None:
                on_event(event)
        return OrchestrationResult(
            "failed", events, None, None, None, None, 2, "Diagnosis produced no actionable result."
        )

    monkeypatch.setattr(routes, "run_analysis", fail_run)

    with TestClient(app) as client:
        create = client.post("/api/analyze", json=_snippet_payload())
        job_id = create.json()["job_id"]
        poll = client.get(f"/api/jobs/{job_id}")

    job = poll.json()
    assert job["status"] == "failed"
    assert job["error"] == "Diagnosis produced no actionable result."
    assert job["llm_call_count"] == 2
    assert job["diff"] is None
    assert job["judge_verdict"] is None


def test_mocked_blocked_job_round_trip(monkeypatch) -> None:
    """A job that reaches the iteration cap returns blocked status."""
    def blocked_run(request, client, *, max_iterations=3, on_event=None):
        events = [
            TraceEvent("LINT", "Lint completed.", {"findings": 0, "exit_code": 0}),
            TraceEvent("HYPOTHESIS", "Attempt 1."),
            TraceEvent("PATCH", "Diff generated.", {}),
            TraceEvent("VERIFY", "Tests failed.", {"exit_code": 1, "stdout": "", "stderr": "AssertionError"}),
            TraceEvent("FINAL", "blocked", {"error": "Iteration cap reached."}),
        ]
        for event in events:
            if on_event is not None:
                on_event(event)
        verification = SandboxResult(False, 1, "", "AssertionError", False, "fail", None)
        return OrchestrationResult(
            "blocked", events, "--- a/snippet.py\n+++ b/snippet.py\n", verification,
            None, None, 6, "Iteration cap reached."
        )

    monkeypatch.setattr(routes, "run_analysis", blocked_run)

    with TestClient(app) as client:
        create = client.post("/api/analyze", json=_snippet_payload())
        job_id = create.json()["job_id"]
        poll = client.get(f"/api/jobs/{job_id}")

    job = poll.json()
    assert job["status"] == "blocked"
    assert job["error"] == "Iteration cap reached."
    assert job["llm_call_count"] == 6
