from __future__ import annotations

from pathlib import Path

from backend.agent import orchestrator
from backend.agent.diagnosis import DiagnosisResult
from backend.agent.judge import JudgeResult
from backend.agent.lint import LintResult
from backend.agent.llm_client import DiagnosisResponse, JudgeResponse
from backend.agent.patcher import PatchResult
from backend.api.models import AnalyzeRequest
from backend.sandbox.runner import SandboxResult


class FakeClient:
    def __init__(self, call_count: int = 0) -> None:
        self.call_count = call_count
        self.model_ids = ()


def _request() -> AnalyzeRequest:
    return AnalyzeRequest(mode="snippet", code="def add(a, b):\n    return a - b\n", test_type="pytest", test_content="def test_add(): pass")


def _lint() -> LintResult:
    return LintResult(True, "completed", 0, [], [], "[]", "")


def _diagnosis() -> DiagnosisResult:
    return DiagnosisResult(True, "completed", DiagnosisResponse(known=[], unknown=[], hypothesis="fix", next_action="patch", target_files=["snippet.py"]), "free")


def _patch() -> PatchResult:
    return PatchResult(True, "generated", "--- a/snippet.py\n+++ b/snippet.py\n@@ -1 +1 @@\n-x\n+y\n", False, None, [])


def _applied(destination: Path) -> PatchResult:
    destination.mkdir(parents=True)
    (destination / "snippet.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    return PatchResult(True, "applied", "diff", True, destination, ["snippet.py"])


def _verify(success: bool) -> SandboxResult:
    return SandboxResult(success, 0 if success else 1, "passed" if success else "", "failed" if not success else "", False, "passed" if success else "failed")


def test_successful_repair_produces_verified_final_result(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator, "lint_workspace", lambda *args: _lint())
    monkeypatch.setattr(orchestrator, "diagnose", lambda *args: _diagnosis())
    monkeypatch.setattr(orchestrator, "generate_patch", lambda *args: _patch())
    monkeypatch.setattr(orchestrator, "apply_unified_diff", lambda source, destination, diff: _applied(destination))
    monkeypatch.setattr(orchestrator, "_verify_candidate", lambda *args: _verify(True))
    monkeypatch.setattr(orchestrator, "judge_fix", lambda *args: JudgeResult(True, "completed", JudgeResponse(genuine_fix=True, reasoning="genuine"), "free"))

    result = orchestrator.run_analysis(_request(), FakeClient(3))

    assert result.status == "verified"
    assert result.judge_verdict is True
    assert result.llm_call_count == 3
    assert {event.kind for event in result.trace} >= {"LINT", "KNOWN", "UNKNOWN", "HYPOTHESIS", "NEXT ACTION", "PATCH", "VERIFY", "JUDGE", "FINAL"}


def test_failed_verification_is_fed_into_next_diagnosis(monkeypatch) -> None:
    contexts = []
    verification_results = iter([_verify(False), _verify(True)])
    monkeypatch.setattr(orchestrator, "lint_workspace", lambda *args: _lint())
    monkeypatch.setattr(orchestrator, "diagnose", lambda client, context: contexts.append(context) or _diagnosis())
    monkeypatch.setattr(orchestrator, "generate_patch", lambda *args: _patch())
    monkeypatch.setattr(orchestrator, "apply_unified_diff", lambda source, destination, diff: _applied(destination))
    monkeypatch.setattr(orchestrator, "_verify_candidate", lambda *args: next(verification_results))
    monkeypatch.setattr(orchestrator, "judge_fix", lambda *args: JudgeResult(True, "completed", JudgeResponse(genuine_fix=True, reasoning="genuine"), "free"))

    result = orchestrator.run_analysis(_request(), FakeClient(), max_iterations=2)

    assert result.status == "verified"
    assert len(contexts) == 2
    assert contexts[1].previous_verification_failure == "failed"


def test_iteration_cap_blocks_after_failed_verification(monkeypatch) -> None:
    calls = 0
    monkeypatch.setattr(orchestrator, "lint_workspace", lambda *args: _lint())
    monkeypatch.setattr(orchestrator, "diagnose", lambda *args: _diagnosis())
    monkeypatch.setattr(orchestrator, "generate_patch", lambda *args: _patch())
    monkeypatch.setattr(orchestrator, "apply_unified_diff", lambda source, destination, diff: _applied(destination))

    def verify(*args):
        nonlocal calls
        calls += 1
        return _verify(False)

    monkeypatch.setattr(orchestrator, "_verify_candidate", verify)
    result = orchestrator.run_analysis(_request(), FakeClient(), max_iterations=99)

    assert result.status == "blocked"
    assert calls == 3


def test_judge_rejection_retries_and_blocks_at_cap(monkeypatch) -> None:
    judge_calls = 0
    monkeypatch.setattr(orchestrator, "lint_workspace", lambda *args: _lint())
    monkeypatch.setattr(orchestrator, "diagnose", lambda *args: _diagnosis())
    monkeypatch.setattr(orchestrator, "generate_patch", lambda *args: _patch())
    monkeypatch.setattr(orchestrator, "apply_unified_diff", lambda source, destination, diff: _applied(destination))
    monkeypatch.setattr(orchestrator, "_verify_candidate", lambda *args: _verify(True))

    def judge(*args):
        nonlocal judge_calls
        judge_calls += 1
        return JudgeResult(True, "completed", JudgeResponse(genuine_fix=False, reasoning="test was weakened"), "free")

    monkeypatch.setattr(orchestrator, "judge_fix", judge)
    result = orchestrator.run_analysis(_request(), FakeClient(), max_iterations=2)

    assert result.status == "blocked"
    assert result.judge_verdict is False
    assert judge_calls == 2


def test_model_unavailable_and_malformed_output_fail_cleanly(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator, "lint_workspace", lambda *args: _lint())
    monkeypatch.setattr(orchestrator, "diagnose", lambda *args: DiagnosisResult(False, "model_unavailable", None, None, "No models"))
    unavailable = orchestrator.run_analysis(_request(), FakeClient())
    assert unavailable.status == "model_unavailable"
    assert unavailable.error == "No models"

    monkeypatch.setattr(orchestrator, "diagnose", lambda *args: DiagnosisResult(False, "malformed_output", None, "free", "Invalid JSON"))
    malformed = orchestrator.run_analysis(_request(), FakeClient())
    assert malformed.status == "failed"
    assert malformed.error == "Invalid JSON"


def test_original_workspace_is_not_modified_by_patch_application(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "snippet.py").write_text("before\n", encoding="utf-8")
    destination = tmp_path / "candidate"
    original = (source / "snippet.py").read_text(encoding="utf-8")

    result = orchestrator.apply_unified_diff(
        source,
        destination,
        "--- a/snippet.py\n+++ b/snippet.py\n@@ -1 +1 @@\n-before\n+after\n",
    )

    assert result.success is True
    assert (source / "snippet.py").read_text(encoding="utf-8") == original
    assert (destination / "snippet.py").read_text(encoding="utf-8") == "after\n"


def test_non_python_snippet_rejected_with_honest_message() -> None:
    non_python = AnalyzeRequest(
        mode="snippet",
        code="function add(a, b) { return a + b; }",
        test_type="pytest",
        test_content="def test_add(): pass",
    )
    result = orchestrator.run_analysis(non_python, FakeClient())
    assert result.status == "failed"
    assert "This MVP supports Python only by design" in (result.error or "")
    assert "multi-language support is a documented next step, not a bug" in (result.error or "")


def test_empty_repo_rejected_with_honest_message(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator, "_clone_repository", lambda req, orig: (orig.mkdir() or True, None))
    repo_request = AnalyzeRequest(
        mode="repo",
        repo_url="https://github.com/example/no-python-repo",
        test_command="pytest",
    )
    result = orchestrator.run_analysis(repo_request, FakeClient())
    assert result.status == "failed"
    assert "This MVP supports Python only by design" in (result.error or "")
    assert "multi-language support is a documented next step, not a bug" in (result.error or "")
