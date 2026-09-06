from __future__ import annotations

from fastapi.testclient import TestClient

from backend.agent.orchestrator import OrchestrationResult, TraceEvent
from backend.api import routes
from backend.main import app


def _payload() -> dict[str, str]:
    return {
        "mode": "snippet",
        "code": "def add(left, right):\n    return left + right\n",
        "test_type": "pytest",
        "test_content": "def test_add():\n    assert True\n",
    }


def test_analyze_runs_orchestrator_and_exposes_final_poll_state(monkeypatch) -> None:
    def fake_run(request, client, *, max_iterations=3, on_event=None):
        event = TraceEvent("HYPOTHESIS", "The implementation is correct.", {"attempt": 1})
        assert on_event is not None
        on_event(event)
        return OrchestrationResult("verified", [event], "--- a/snippet.py\n+++ b/snippet.py\n", None, True, "Verified.", 2)

    monkeypatch.setattr(routes, "run_analysis", fake_run)
    with TestClient(app) as client:
        job_id = client.post("/api/analyze", json=_payload()).json()["job_id"]
        stream_response = client.get(f"/api/jobs/{job_id}/stream")
        poll_response = client.get(f"/api/jobs/{job_id}")

    assert stream_response.status_code == 200
    assert "event: trace" in stream_response.text
    assert '"kind": "HYPOTHESIS"' in stream_response.text
    assert "event: final" in stream_response.text
    job = poll_response.json()
    assert job["status"] == "verified"
    assert job["llm_call_count"] == 2
    assert job["iteration_count"] == 1
    assert job["diff"].startswith("--- a/snippet.py")
    assert job["judge_verdict"] is True


def test_unknown_job_poll_and_stream_return_not_found() -> None:
    unknown = "00000000-0000-0000-0000-000000000000"
    with TestClient(app) as client:
        poll_response = client.get(f"/api/jobs/{unknown}")
        stream_response = client.get(f"/api/jobs/{unknown}/stream")

    assert poll_response.status_code == 404
    assert stream_response.status_code == 404
