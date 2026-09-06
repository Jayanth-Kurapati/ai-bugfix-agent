from __future__ import annotations

from pathlib import Path
import subprocess

from backend.agent import lint


def test_lint_workspace_returns_normalized_pylint_findings(tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text("value = unknown_name\n", encoding="utf-8")

    result = lint.lint_workspace(tmp_path, ["sample.py"])

    assert result.success is True
    assert result.status == "completed"
    assert result.exit_code is not None
    assert result.raw_findings
    finding = next(item for item in result.findings if item.message_id == "E0602")
    assert finding.path.endswith("sample.py")
    assert finding.severity == "error"
    assert "undefined-variable" == finding.symbol
    assert "unknown_name" in finding.message


def test_lint_workspace_does_not_modify_or_run_in_source_workspace(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    source_file = source / "sample.py"
    source_file.write_text("print('hello')\n", encoding="utf-8")

    result = lint.lint_workspace(source, ["sample.py"])

    assert result.success is True
    assert not (source / "safe-pylintrc").exists()
    assert source_file.read_text(encoding="utf-8") == "print('hello')\n"


def test_lint_workspace_handles_missing_executable(tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text("value = 1\n", encoding="utf-8")

    result = lint.lint_workspace(tmp_path, ["sample.py"], command=("missing-pylint-command",))

    assert result.success is False
    assert result.status == "missing_executable"
    assert result.exit_code is None


def test_lint_workspace_handles_malformed_json(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "sample.py").write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        lint.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=1, stdout="not-json", stderr="bad"),
    )

    result = lint.lint_workspace(tmp_path, ["sample.py"])

    assert result.success is False
    assert result.status == "malformed_output"
    assert result.exit_code == 1
    assert result.stderr == "bad"


def test_lint_workspace_handles_timeout(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "sample.py").write_text("value = 1\n", encoding="utf-8")

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"], output="partial", stderr="late")

    monkeypatch.setattr(lint.subprocess, "run", raise_timeout)

    result = lint.lint_workspace(tmp_path, ["sample.py"])

    assert result.success is False
    assert result.status == "timed_out"
    assert result.stdout == "partial"
    assert result.stderr == "late"
