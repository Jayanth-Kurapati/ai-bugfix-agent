import json
import logging
import os
import time
from threading import Lock, Semaphore, Thread
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from backend.agent.orchestrator import run_analysis
from backend.api.jobs import JobStore
from backend.api.models import AnalyzeRequest, AnalyzeResponse, JobResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["jobs"])


class InMemoryRateLimiter:
    """Dependency-free sliding-window rate limiter tracking timestamps per client IP."""

    def __init__(self, requests_limit: int = 5, window_seconds: float = 60.0):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self._records: dict[str, list[float]] = {}
        self._lock = Lock()

    def check_and_record(self, client_ip: str, current_time: float | None = None) -> bool:
        """Return True if allowed, False if rate limit exceeded.
        Prunes expired records on each check to prevent memory leakage.
        """
        now = time.time() if current_time is None else current_time
        cutoff = now - self.window_seconds

        with self._lock:
            # Prune stale IPs and timestamps across all records
            stale_ips = []
            for ip, timestamps in list(self._records.items()):
                fresh = [t for t in timestamps if t > cutoff]
                if not fresh:
                    stale_ips.append(ip)
                else:
                    self._records[ip] = fresh

            for ip in stale_ips:
                self._records.pop(ip, None)

            # Check client quota
            client_timestamps = self._records.get(client_ip, [])
            if len(client_timestamps) >= self.requests_limit:
                return False

            client_timestamps.append(now)
            self._records[client_ip] = client_timestamps
            return True

    def reset(self) -> None:
        """Clear all records (primarily for testing)."""
        with self._lock:
            self._records.clear()


def _extract_client_ip(request: Request) -> str:
    """Extract client IP, inspecting X-Forwarded-For for reverse proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
_rate_limiter = InMemoryRateLimiter(
    requests_limit=int(os.getenv("RATE_LIMIT_PER_MINUTE", "5")),
    window_seconds=60.0,
)
_job_semaphore = Semaphore(MAX_CONCURRENT_JOBS)


def _reset_limits() -> None:
    """Reset rate limiter and semaphore (used in tests)."""
    global _job_semaphore
    _rate_limiter.reset()
    _job_semaphore = Semaphore(int(os.getenv("MAX_CONCURRENT_JOBS", "2")))



def _job_store(request: Request) -> JobStore:
    return request.app.state.job_store


def _run_job(request: AnalyzeRequest, job_id: UUID, store: JobStore, client) -> None:
    try:
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
                    "verified", events, fake_diff, verification, True, "Operator changed from - to +; test passes genuinely.", 3, None, 1
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
                    "blocked", events, fake_diff, verification, None, None, 2, "Sandbox execution requires a POSIX platform with resource limits.", 1
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
                    "failed", events, fake_diff, verification, False, "Fix did not pass tests.", 2, "Test failed: AssertionError: Expected 5, got 6", 1
                )
            else:
                result = run_analysis(request, client.for_job(), on_event=lambda event: store.append_event(job_id, event))
        except Exception as exc:  # Keep background failures observable by polling/SSE.
            from backend.agent.orchestrator import OrchestrationResult

            logger.exception("Unexpected failure in analysis job %s: %s", job_id, exc)
            result = OrchestrationResult(
                "failed", [], None, None, None, None, 0, "An unexpected error occurred during analysis.", 1
            )
        store.complete(job_id, result)
    finally:
        _job_semaphore.release()


@router.post("/analyze", response_model=AnalyzeResponse, status_code=status.HTTP_201_CREATED)
def create_analysis_job(payload: AnalyzeRequest, request: Request) -> AnalyzeResponse:
    """Create a job and start its bounded orchestration in a background thread."""
    client_ip = _extract_client_ip(request)
    if not _rate_limiter.check_and_record(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 5 requests per minute allowed.",
        )

    if not _job_semaphore.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server busy, try again shortly.",
        )

    try:
        job = _job_store(request).create(payload)
        Thread(
            target=_run_job,
            args=(payload, job.job_id, _job_store(request), request.app.state.llm_client),
            daemon=True,
            name=f"bugfix-job-{job.job_id}",
        ).start()
    except Exception:
        _job_semaphore.release()
        raise

    return AnalyzeResponse(job_id=job.job_id)



@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID, request: Request) -> JobResponse:
    """Return the current process-local state for a known job."""

    job = _job_store(request).get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return job


@router.get("/jobs/{job_id}/stream")
def stream_job(job_id: UUID, request: Request) -> StreamingResponse:
    """Publish each trace event as SSE and end with the final job state."""

    store = _job_store(request)
    if store.get(job_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

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
