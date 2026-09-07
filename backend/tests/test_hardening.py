"""Tests verifying the production hardening controls."""

from pathlib import Path
import tempfile
import pytest

from backend.agent.orchestrator import _select_repository_sources, run_analysis
from backend.agent.patcher import check_patch_integrity
from backend.api.models import AnalyzeRequest
from backend.sandbox.runner import _sanitize_output


class MockLLMClient:
    def __init__(self):
        self.call_count = 0
        self.model_ids = ["test/model:free"]

    def for_job(self):
        return self


def test_patch_integrity_rejects_deleting_assertions():
    diff = (
        "--- a/tests/test_calc.py\n"
        "+++ b/tests/test_calc.py\n"
        "@@ -5,2 +5,1 @@\n"
        "-    assert calc.add(2, 3) == 5\n"
        "+    pass\n"
    )
    ok, reason = check_patch_integrity(diff, mode="repo")
    assert not ok
    assert "deleting test assertions" in (reason or "")


def test_patch_integrity_rejects_skipping_tests():
    diff = (
        "--- a/tests/test_calc.py\n"
        "+++ b/tests/test_calc.py\n"
        "@@ -4,2 +4,3 @@\n"
        "+@pytest.mark.skip\n"
        " def test_calc():\n"
    )
    ok, reason = check_patch_integrity(diff, mode="repo")
    assert not ok
    assert "disabling tests via skip/xfail" in (reason or "")


def test_patch_integrity_rejects_tampering_test_runner():
    diff = (
        "--- a/calc.py\n"
        "+++ b/calc.py\n"
        "@@ -1,2 +1,3 @@\n"
        "+import sys\n"
        "+sys.modules['pytest'] = None\n"
    )
    ok, reason = check_patch_integrity(diff, mode="repo")
    assert not ok
    assert "attempting to mock test runner" in (reason or "")


def test_output_sanitization_redacts_api_keys_and_paths(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-secret-key-1234567890abcdef")
    raw = (
        "Error with OPENROUTER_API_KEY=sk-or-v1-secret-key-1234567890abcdef "
        "and Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy_token_long_secret_value_123456 "
        "in C:/Users/someone/temp/bugfix-123/workspace/test.py"
    )
    workspace = Path("C:/Users/someone/temp/bugfix-123/workspace")
    sanitized = _sanitize_output(raw, workspace_path=workspace)
    assert "sk-or-v1-secret-key" not in sanitized
    assert "[REDACTED_API_KEY]" in sanitized or "[REDACTED_SECRET]" in sanitized
    assert "./workspace/test.py" in sanitized


def test_select_repository_sources_prioritizes_relevant_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "unrelated.py").write_text("def foo(): pass\n", encoding="utf-8")
        (root / "calculator.py").write_text("def compute(): return 42\n", encoding="utf-8")
        (root / "test_calculator.py").write_text("def test_compute(): pass\n", encoding="utf-8")
        (root / "other.py").write_text("def bar(): pass\n", encoding="utf-8")

        sources = _select_repository_sources(
            root,
            bug_report="Failure in calculator compute function",
            test_command="pytest test_calculator.py",
        )

        files = list(sources.keys())
        assert "calculator.py" in files
        assert "test_calculator.py" in files


def test_traceback_mode_inconclusive_when_not_reproduced(monkeypatch):
    # Snippet that runs with exit 0 (does not trigger any error)
    req = AnalyzeRequest(
        mode="snippet",
        code="def add(a, b):\n    return a + b\n",
        test_type="traceback",
        test_content="Traceback (most recent call last):\n  File 'snippet.py', line 2, in add\n    ValueError\n",
    )
    # Even if sandbox passes, it was never reproduced
    from backend.sandbox.runner import SandboxResult
    monkeypatch.setattr("backend.agent.orchestrator.run_python", lambda *args, **kwargs: SandboxResult(True, 0, "", "", False, "passed"))
    monkeypatch.setattr("backend.agent.orchestrator.diagnose", lambda *args, **kwargs: type("Diag", (), {"success": True, "status": "diagnosed", "model_id": "test", "diagnosis": type("P", (), {"known": [], "unknown": [], "hypothesis": "hyp", "next_action": "act", "target_files": ["snippet.py"]})()}))
    monkeypatch.setattr("backend.agent.orchestrator.generate_patch", lambda *args, **kwargs: type("Patch", (), {"success": True, "status": "diff_generated", "model_id": "test", "error": None, "diff": "--- a/snippet.py\n+++ b/snippet.py\n@@ -1,2 +1,2 @@\n def add(a, b):\n-    return a + b\n+    return a + b\n"})())
    monkeypatch.setattr("backend.agent.orchestrator.apply_unified_diff", lambda orig, cand, diff: type("App", (), {"success": True, "status": "applied", "patched_files": ["snippet.py"], "workspace_path": cand, "error": None})())

    client = MockLLMClient()
    result = run_analysis(req, client)
    assert result.status == "verification_inconclusive"
    assert "could not be deterministically reproduced" in (result.error or "")

