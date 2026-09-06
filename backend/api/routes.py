"""HTTP routes available in the backend foundation."""

import json
from threading import Thread
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from backend.agent.orchestrator import run_analysis
from backend.api.jobs import JobStore
from backend.api.models import AnalyzeRequest, AnalyzeResponse, JobResponse


router = APIRouter(prefix="/api", tags=["jobs"])


def _job_store(request: Request) -> JobStore:
    return request.app.state.job_store


def _run_job(request: AnalyzeRequest, job_id: UUID, store: JobStore, client) -> None:
    store.mark_running(job_id)
    try:
        import os
        if os.getenv("MOCK_ORCHESTRATOR", "").strip() == "verified":
            import time
            from backend.sandbox.runner import SandboxResult
            from backend.agent.orchestrator import OrchestrationResult, TraceEvent

            fake_diff = (
                "--- a/snippet.py\n"
                "+++ b/snippet.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def add(a, b):\n"
                "-    return a - b\n"
                "+    return a + b\n"
            )
            events = [
                TraceEvent("MODELS", "Free models discovered.", {"models": ["minimax/minimax-m3:free", "google/gemma-4-31b-it:free"]}),
                TraceEvent("LINT", "Lint completed.", {"findings": 1, "exit_code": 0}),
                TraceEvent("KNOWN", "Diagnosis known facts.", {"values": ["add function exists", "test expects 5"], "model_id": "minimax/minimax-m3:free"}),
                TraceEvent("UNKNOWN", "Diagnosis unknowns.", {"values": ["operator correctness"]}),
                TraceEvent("HYPOTHESIS", "The function uses subtraction instead of addition."),
                TraceEvent("NEXT ACTION", "Patch the operator.", {"target_files": ["snippet.py"]}),
                TraceEvent("PATCH", "Diff generated.", {"model_id": "minimax/minimax-m3:free"}),
                TraceEvent("PATCH", "applied", {"patched_files": ["snippet.py"]}),
                TraceEvent("VERIFY", "passed", {"exit_code": 0, "stdout": "1 passed in 0.02s", "stderr": ""}),
                TraceEvent("JUDGE", "Judge verdict received.", {"genuine_fix": True, "reasoning": "Operator changed from - to +; test passes genuinely.", "model_id": "minimax/minimax-m3:free"}),
                TraceEvent("FINAL", "verified", {}),
            ]
            for event in events:
                store.append_event(job_id, event)
                time.sleep(0.3)
            verification = SandboxResult(True, 0, "1 passed in 0.02s", "", False, "passed", None)
            result = OrchestrationResult(
                "verified", events, fake_diff, verification, True, "Operator changed from - to +; test passes genuinely.", 3
            )
        elif os.getenv("MOCK_ORCHESTRATOR", "").strip() == "blocked":
            import time
            from backend.sandbox.runner import SandboxResult
            from backend.agent.orchestrator import OrchestrationResult, TraceEvent

            fake_diff = (
                "--- a/snippet.py\n"
                "+++ b/snippet.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def add(a, b):\n"
                "-    return a - b\n"
                "+    return a + b\n"
            )
            events = [
                TraceEvent("MODELS", "Free models discovered.", {"models": ["google/gemma-4-31b-it:free", "minimax/minimax-m3:free"]}),
                TraceEvent("LINT", "Lint completed.", {"findings": 0, "exit_code": 0}),
                TraceEvent("KNOWN", "Diagnosis known facts.", {"values": ["add function exists"], "model_id": "google/gemma-4-31b-it:free"}),
                TraceEvent("UNKNOWN", "Diagnosis unknowns.", {"values": ["operator correctness"]}),
                TraceEvent("HYPOTHESIS", "The function uses subtraction instead of addition."),
                TraceEvent("NEXT ACTION", "Patch the operator.", {"target_files": ["snippet.py"]}),
                TraceEvent("PATCH", "Diff generated.", {"model_id": "google/gemma-4-31b-it:free"}),
                TraceEvent("PATCH", "applied", {"patched_files": ["snippet.py"]}),
                TraceEvent("VERIFY", "unsupported_platform", {"exit_code": None, "stdout": "", "stderr": ""}),
                TraceEvent("FINAL", "blocked", {"error": "Sandbox execution requires a POSIX platform with resource limits."}),
            ]
            for event in events:
                store.append_event(job_id, event)
                time.sleep(0.3)
            verification = SandboxResult(False, None, "", "", False, "unsupported_platform", "Sandbox execution requires a POSIX platform with resource limits.")
            result = OrchestrationResult(
                "blocked", events, fake_diff, verification, None, None, 2, "Sandbox execution requires a POSIX platform with resource limits."
            )
        elif os.getenv("MOCK_ORCHESTRATOR", "").strip() == "failed":
            import time
            from backend.sandbox.runner import SandboxResult
            from backend.agent.orchestrator import OrchestrationResult, TraceEvent

            fake_diff = (
                "--- a/snippet.py\n"
                "+++ b/snippet.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def add(a, b):\n"
                "-    return a - b\n"
                "+    return a * b\n"
            )
            events = [
                TraceEvent("MODELS", "Free models discovered.", {"models": ["google/gemma-4-31b-it:free"]}),
                TraceEvent("LINT", "Lint completed.", {"findings": 0, "exit_code": 0}),
                TraceEvent("HYPOTHESIS", "Attempting multiplication fix."),
                TraceEvent("PATCH", "Diff generated.", {}),
                TraceEvent("PATCH", "applied", {"patched_files": ["snippet.py"]}),
                TraceEvent("VERIFY", "failed", {"exit_code": 1, "stdout": "", "stderr": "AssertionError: Expected 5, got 6"}),
                TraceEvent("FINAL", "failed", {"error": "Test failed: AssertionError: Expected 5, got 6"}),
            ]
            for event in events:
                store.append_event(job_id, event)
                time.sleep(0.3)
            verification = SandboxResult(False, 1, "", "AssertionError: Expected 5, got 6", False, "failed", "Verification failed.")
            result = OrchestrationResult(
                "failed", events, fake_diff, verification, False, "Fix did not pass tests.", 2, "Test failed: AssertionError: Expected 5, got 6"
            )
        else:
            result = run_analysis(request, client.for_job(), on_event=lambda event: store.append_event(job_id, event))
    except Exception as exc:  # Keep background failures observable by polling/SSE.
        from backend.agent.orchestrator import OrchestrationResult

        result = OrchestrationResult("failed", [], None, None, None, None, 0, f"Unexpected job failure: {exc}")
    store.complete(job_id, result)


@router.post("/analyze", response_model=AnalyzeResponse, status_code=status.HTTP_201_CREATED)
def create_analysis_job(payload: AnalyzeRequest, request: Request) -> AnalyzeResponse:
    """Create a job and start its bounded orchestration in a background thread."""

    job = _job_store(request).create(payload)
    Thread(
        target=_run_job,
        args=(payload, job.job_id, _job_store(request), request.app.state.llm_client),
        daemon=True,
        name=f"bugfix-job-{job.job_id}",
    ).start()
    return AnalyzeResponse(job_id=job.job_id)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID, request: Request) -> JobResponse:
    """Return the current process-local state for a known job."""

    job = _job_store(request).get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/stream")
def stream_job(job_id: UUID, request: Request) -> StreamingResponse:
    """Publish each trace event as SSE and end with the final job state."""

    store = _job_store(request)
    if store.get(job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    def event_stream():
        index = 0
        while True:
            events, complete, job = store.wait_for_updates(job_id, index)
            for event in events:
                index += 1
                yield f"event: trace\ndata: {json.dumps(event.model_dump(mode='json'))}\n\n"
            if complete:
                yield f"event: final\ndata: {json.dumps(job.model_dump(mode='json'))}\n\n"
                return
            yield ": keepalive\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
