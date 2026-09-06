"""Bounded diagnose → patch → verify → judge workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable

from backend.agent.diagnosis import DiagnosisContext, diagnose
from backend.agent.judge import JudgeContext, judge_fix
from backend.agent.lint import LintResult, lint_workspace
from backend.agent.llm_client import OpenRouterClient
from backend.agent.patcher import PatchContext, apply_unified_diff, generate_patch
from backend.api.models import AnalyzeRequest
from backend.sandbox.runner import SandboxResult, run_python


HARD_MAX_ITERATIONS = 3
MAX_SOURCE_FILES = 6
MAX_TREE_ENTRIES = 100


@dataclass(frozen=True)
class TraceEvent:
    kind: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrchestrationResult:
    status: str
    trace: list[TraceEvent]
    diff: str | None
    verification: SandboxResult | None
    judge_verdict: bool | None
    judge_reasoning: str | None
    llm_call_count: int
    error: str | None = None


class _TraceBuffer(list[TraceEvent]):
    def __init__(self, on_event: Callable[[TraceEvent], None] | None) -> None:
        super().__init__()
        self._on_event = on_event

    def append(self, event: TraceEvent) -> None:
        super().append(event)
        if self._on_event is not None:
            self._on_event(event)


def _trace(trace: list[TraceEvent], kind: str, message: str, **data: Any) -> None:
    trace.append(TraceEvent(kind, message, data))


def _source_files(workspace: Path) -> dict[str, str]:
    files = sorted(path for path in workspace.rglob("*.py") if path.is_file())[:MAX_SOURCE_FILES]
    return {path.relative_to(workspace).as_posix(): path.read_text(encoding="utf-8", errors="replace")[:6_000] for path in files}


def _tree_summary(workspace: Path) -> list[str]:
    return [
        f"{path.relative_to(workspace).as_posix()} ({path.stat().st_size} bytes)"
        for path in sorted(workspace.rglob("*"))
        if path.is_file()
    ][:MAX_TREE_ENTRIES]


def _clone_repository(request: AnalyzeRequest, destination: Path) -> tuple[bool, str | None]:
    assert request.repo_url is not None
    try:
        completed = subprocess.run(
            ["git", "clone", "--depth", "1", str(request.repo_url), str(destination)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if completed.returncode != 0:
        return False, completed.stderr or "Repository clone failed."
    return True, None


def _pytest_arguments(test_command: str) -> list[str] | None:
    try:
        tokens = shlex.split(test_command, posix=True)
    except ValueError:
        return None
    if not tokens or tokens[0] != "pytest":
        return None
    allowed_options = {"-q", "-x", "--disable-warnings", "--tb=short", "--tb=line"}
    arguments: list[str] = []
    for token in tokens[1:]:
        if token in allowed_options:
            arguments.append(token)
            continue
        candidate = Path(token)
        if token.startswith("-") or candidate.is_absolute() or ".." in candidate.parts or any(char in token for char in ";|&<>$`\n"):
            return None
        arguments.append(token)
    return arguments


def _verify_candidate(candidate: Path, request: AnalyzeRequest) -> SandboxResult:
    if request.mode == "snippet" and request.test_type == "traceback":
        return run_python(candidate, "snippet.py")

    if request.mode == "snippet":
        pytest_arguments = ["test_snippet.py"]
    else:
        assert request.test_command is not None
        pytest_arguments = _pytest_arguments(request.test_command)
        if pytest_arguments is None:
            return SandboxResult(False, None, "", "", False, "execution_error", "Unsupported test command; use permitted pytest arguments only.")
    wrapper = candidate / "__verify__.py"
    wrapper.write_text(
        "import subprocess\nimport sys\n"
        f"result = subprocess.run([sys.executable, '-m', 'pytest', *{pytest_arguments!r}], check=False)\n"
        "raise SystemExit(result.returncode)\n",
        encoding="utf-8",
    )
    return run_python(candidate, "__verify__.py")


def _final(
    status: str,
    trace: list[TraceEvent],
    client: OpenRouterClient,
    *,
    diff: str | None = None,
    verification: SandboxResult | None = None,
    judge_verdict: bool | None = None,
    judge_reasoning: str | None = None,
    error: str | None = None,
) -> OrchestrationResult:
    _trace(trace, "FINAL", status, error=error)
    return OrchestrationResult(status, trace, diff, verification, judge_verdict, judge_reasoning, client.call_count, error)


def run_analysis(
    request: AnalyzeRequest,
    client: OpenRouterClient,
    *,
    max_iterations: int = HARD_MAX_ITERATIONS,
    on_event: Callable[[TraceEvent], None] | None = None,
) -> OrchestrationResult:
    """Run the bounded MVP workflow without mutating the input source workspace."""

    trace: list[TraceEvent] = _TraceBuffer(on_event)
    iterations = min(max(1, max_iterations), HARD_MAX_ITERATIONS)
    previous_failure: str | None = None
    latest_diff: str | None = None
    latest_verification: SandboxResult | None = None

    _trace(trace, "MODELS", "Discovered model fallback list.", models=list(client.model_ids))

    with tempfile.TemporaryDirectory(prefix="bugfix-analysis-") as temporary_root:
        root = Path(temporary_root)
        original = root / "original"
        if request.mode == "snippet":
            assert request.code is not None and request.test_content is not None
            import ast
            try:
                ast.parse(request.code)
            except SyntaxError as exc:
                return _final(
                    "failed",
                    trace,
                    client,
                    error=(
                        "This MVP supports Python only by design; multi-language support is a documented "
                        f"next step, not a bug (Python syntax error: {exc.msg} at line {exc.lineno})."
                    ),
                )
            if request.test_type == "pytest":
                try:
                    ast.parse(request.test_content)
                except SyntaxError as exc:
                    return _final(
                        "failed",
                        trace,
                        client,
                        error=(
                            "This MVP supports Python only by design; multi-language support is a documented "
                            f"next step, not a bug (Pytest syntax error: {exc.msg} at line {exc.lineno})."
                        ),
                    )
            original.mkdir()
            original.joinpath("snippet.py").write_text(request.code, encoding="utf-8")
            if request.test_type == "pytest":
                original.joinpath("test_snippet.py").write_text(request.test_content, encoding="utf-8")
        else:
            cloned, clone_error = _clone_repository(request, original)
            if not cloned:
                return _final("failed", trace, client, error=f"Repository clone failed: {clone_error}")

        tree = _tree_summary(original)
        source = _source_files(original)
        if not source:
            return _final(
                "failed",
                trace,
                client,
                error=(
                    "This MVP supports Python only by design; multi-language support is a documented "
                    "next step, not a bug. No Python (.py) files were found in the workspace."
                ),
            )

        for iteration in range(1, iterations + 1):
            lint: LintResult = lint_workspace(original, list(source))
            _trace(trace, "LINT", lint.status, findings=len(lint.findings), exit_code=lint.exit_code)
            if not lint.success:
                return _final("failed", trace, client, diff=latest_diff, error=lint.error)

            diagnosis = diagnose(
                client,
                DiagnosisContext(
                    bug_report=request.test_content or request.test_command or "No bug report provided.",
                    source_files=source,
                    lint_findings=lint.findings,
                    repo_tree=tree if request.mode == "repo" else (),
                    previous_verification_failure=previous_failure,
                ),
            )
            if not diagnosis.success or diagnosis.diagnosis is None:
                final_status = "model_unavailable" if diagnosis.status == "model_unavailable" else "failed"
                return _final(final_status, trace, client, diff=latest_diff, error=diagnosis.error or diagnosis.status)
            payload = diagnosis.diagnosis
            _trace(trace, "KNOWN", "Diagnosis known facts.", values=payload.known, model_id=diagnosis.model_id)
            _trace(trace, "UNKNOWN", "Diagnosis unknowns.", values=payload.unknown)
            _trace(trace, "HYPOTHESIS", payload.hypothesis)
            _trace(trace, "NEXT ACTION", payload.next_action, target_files=payload.target_files)

            patch = generate_patch(client, PatchContext(payload.hypothesis, payload.target_files, source))
            latest_diff = patch.diff
            _trace(trace, "PATCH", patch.status, error=patch.error, model_id=patch.model_id)
            if not patch.success or patch.diff is None:
                return _final("failed", trace, client, diff=latest_diff, error=patch.error or patch.status)

            candidate = root / f"candidate-{iteration}"
            applied = apply_unified_diff(original, candidate, patch.diff)
            _trace(trace, "PATCH", applied.status, patched_files=applied.patched_files, error=applied.error)
            if not applied.success or applied.workspace_path is None:
                return _final("failed", trace, client, diff=latest_diff, error=applied.error)

            latest_verification = _verify_candidate(applied.workspace_path, request)
            _trace(
                trace,
                "VERIFY",
                latest_verification.status,
                exit_code=latest_verification.exit_code,
                stdout=latest_verification.stdout,
                stderr=latest_verification.stderr,
            )
            if not latest_verification.success:
                previous_failure = latest_verification.stderr or latest_verification.stdout or latest_verification.error or "Verification failed."
                if latest_verification.status == "unsupported_platform":
                    return _final("blocked", trace, client, diff=latest_diff, verification=latest_verification, error=previous_failure)
                if iteration == iterations:
                    return _final("blocked", trace, client, diff=latest_diff, verification=latest_verification, error=previous_failure)
                continue

            patched_source = _source_files(applied.workspace_path)
            verdict = judge_fix(
                client,
                JudgeContext(
                    bug_report=request.test_content or request.test_command or "No bug report provided.",
                    final_diff=patch.diff,
                    verification_output=latest_verification.stdout + latest_verification.stderr,
                    source_files=patched_source,
                ),
            )
            if not verdict.success or verdict.verdict is None:
                return _final("failed", trace, client, diff=latest_diff, verification=latest_verification, error=verdict.error or verdict.status)
            _trace(trace, "JUDGE", "Judge verdict received.", genuine_fix=verdict.verdict.genuine_fix, reasoning=verdict.verdict.reasoning, model_id=verdict.model_id)
            if verdict.verdict.genuine_fix:
                return _final(
                    "verified",
                    trace,
                    client,
                    diff=latest_diff,
                    verification=latest_verification,
                    judge_verdict=True,
                    judge_reasoning=verdict.verdict.reasoning,
                )
            previous_failure = f"Judge rejected patch: {verdict.verdict.reasoning}"
            if iteration == iterations:
                return _final(
                    "blocked",
                    trace,
                    client,
                    diff=latest_diff,
                    verification=latest_verification,
                    judge_verdict=False,
                    judge_reasoning=verdict.verdict.reasoning,
                    error=previous_failure,
                )
    return _final("blocked", trace, client, diff=latest_diff, verification=latest_verification, error="Iteration cap reached.")
