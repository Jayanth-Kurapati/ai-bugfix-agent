"""In-memory job storage for the single-process MVP."""

from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import dataclass
from threading import Condition, Lock
from uuid import UUID, uuid4

from backend.agent.orchestrator import OrchestrationResult, TraceEvent
from backend.api.models import AnalyzeRequest, JobResponse, TraceEventResponse


@dataclass
class _JobRecord:
    state: JobResponse
    condition: Condition
    complete: bool = False


class JobStore:
    """Thread-safe, process-local storage keyed by job UUID."""

    def __init__(self) -> None:
        self._jobs: dict[UUID, _JobRecord] = {}
        self._lock = Lock()

    def create(self, request: AnalyzeRequest) -> JobResponse:
        job = JobResponse(
            job_id=uuid4(),
            status="queued",
            mode=request.mode,
            created_at=datetime.now(UTC),
        )
        with self._lock:
            self._jobs[job.job_id] = _JobRecord(job, Condition())
        return job

    def get(self, job_id: UUID) -> JobResponse | None:
        with self._lock:
            record = self._jobs.get(job_id)
        if record is None:
            return None
        with record.condition:
            return record.state.model_copy(deep=True)

    def mark_running(self, job_id: UUID) -> None:
        record = self._record(job_id)
        if record is None:
            return
        with record.condition:
            record.state = record.state.model_copy(update={"status": "running"})
            record.condition.notify_all()

    def append_event(self, job_id: UUID, event: TraceEvent) -> None:
        record = self._record(job_id)
        if record is None:
            return
        with record.condition:
            trace = [*record.state.trace, TraceEventResponse(kind=event.kind, message=event.message, data=event.data)]
            updates: dict[str, object] = {"trace": trace}
            if event.kind == "ITERATION" and "iteration" in event.data:
                updates["iteration_count"] = int(event.data["iteration"])
            record.state = record.state.model_copy(update=updates)
            record.condition.notify_all()

    def complete(self, job_id: UUID, result: OrchestrationResult) -> None:
        record = self._record(job_id)
        if record is None:
            return
        valid_statuses = {
            "verified",
            "failed",
            "blocked",
            "model_unavailable",
            "verification_inconclusive",
            "repository_error",
            "invalid_input",
        }
        verification = result.verification.__dict__ if result.verification is not None else None
        with record.condition:
            record.state = record.state.model_copy(
                update={
                    "status": result.status if result.status in valid_statuses else "failed",
                    "llm_call_count": result.llm_call_count,
                    "iteration_count": result.iteration_count,
                    "diff": result.diff,
                    "verification": verification,
                    "judge_verdict": result.judge_verdict,
                    "judge_reasoning": result.judge_reasoning,
                    "error": result.error,
                }
            )
            record.complete = True
            record.condition.notify_all()

    def wait_for_updates(self, job_id: UUID, index: int, timeout: float = 15.0) -> tuple[list[TraceEventResponse], bool, JobResponse]:
        record = self._record(job_id)
        if record is None:
            raise KeyError(job_id)
        with record.condition:
            if len(record.state.trace) <= index and not record.complete:
                record.condition.wait(timeout)
            return record.state.trace[index:], record.complete, record.state.model_copy(deep=True)

    def _record(self, job_id: UUID) -> _JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)
