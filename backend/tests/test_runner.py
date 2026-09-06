from __future__ import annotations

from pathlib import Path

import pytest

from backend.sandbox import runner


requires_posix_sandbox = pytest.mark.skipif(
    not runner._supports_posix_sandbox(),
    reason="Submitted code must not run unsandboxed on this platform.",
)


def _write_program(workspace: Path, source: str, name: str = "program.py") -> Path:
    path = workspace / name
    path.write_text(source, encoding="utf-8")
    return path


@requires_posix_sandbox
def test_successful_execution_uses_copied_workspace(tmp_path: Path) -> None:
    _write_program(
        tmp_path,
        "from pathlib import Path\nPath('created-in-sandbox.txt').write_text('ok')\nprint(Path.cwd())\n",
    )

    result = runner.run_python(tmp_path, "program.py")

    assert result.success is True
    assert result.status == "passed"
    assert result.exit_code == 0
    assert Path(result.stdout.strip()) != tmp_path
    assert not (tmp_path / "created-in-sandbox.txt").exists()


@requires_posix_sandbox
def test_failing_execution_captures_output(tmp_path: Path) -> None:
    _write_program(tmp_path, "import sys\nprint('failure', file=sys.stderr)\nraise SystemExit(3)\n")

    result = runner.run_python(tmp_path, "program.py")

    assert result.success is False
    assert result.status == "failed"
    assert result.exit_code == 3
    assert "failure" in result.stderr
    assert result.timed_out is False


@requires_posix_sandbox
def test_wall_clock_timeout_is_reported(tmp_path: Path) -> None:
    _write_program(tmp_path, "import time\ntime.sleep(5)\n")

    result = runner.run_python(
        tmp_path,
        "program.py",
        limits=runner.SandboxLimits(cpu_seconds=5, memory_bytes=256 * 1024 * 1024, wall_timeout_seconds=0.1),
    )

    assert result.success is False
    assert result.status == "timed_out"
    assert result.timed_out is True
    assert result.exit_code is not None


def test_unsupported_platform_never_starts_submitted_program(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "_supports_posix_sandbox", lambda: False)
    _write_program(tmp_path, "from pathlib import Path\nPath('should-not-exist').write_text('ran')\n")

    result = runner.run_python(tmp_path, "program.py")

    assert result.status == "unsupported_platform"
    assert result.success is False
    assert not (tmp_path / "should-not-exist").exists()
