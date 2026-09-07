"""Process-level, POSIX-only execution for submitted Python workspaces."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Sequence

try:  # `resource` is deliberately unavailable on Windows.
    import resource
except ImportError:  # pragma: no cover - exercised by Windows runtime behavior
    resource = None  # type: ignore[assignment]


@dataclass(frozen=True)
class SandboxLimits:
    """Server-controlled limits for one child Python process."""

    cpu_seconds: int = 5
    memory_bytes: int = 256 * 1024 * 1024
    wall_timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if self.cpu_seconds < 1:
            raise ValueError("cpu_seconds must be at least 1")
        if self.memory_bytes < 1:
            raise ValueError("memory_bytes must be positive")
        if self.wall_timeout_seconds <= 0:
            raise ValueError("wall_timeout_seconds must be positive")


@dataclass(frozen=True)
class SandboxResult:
    """Captured result of a sandbox execution attempt."""

    success: bool
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    status: str
    error: str | None = None


MAX_OUTPUT_CHARS = 16_384


def _supports_posix_sandbox() -> bool:
    return os.name == "posix" and resource is not None


def _set_resource_limits(limits: SandboxLimits) -> None:
    """Applied in the child immediately before it executes Python."""

    assert resource is not None
    resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds))
    resource.setrlimit(resource.RLIMIT_AS, (limits.memory_bytes, limits.memory_bytes))
    if hasattr(resource, "RLIMIT_NPROC"):
        try:
            # Constrain process spawning (mitigate fork bombs)
            resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        except (ValueError, OSError):
            pass


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


import re

_SECRET_PATTERN = re.compile(r"(?:sk-[a-zA-Z0-9_\-]{20,}|Bearer\s+[a-zA-Z0-9_\-\.]{20,})", re.IGNORECASE)


def _sanitize_output(
    value: str | bytes | None,
    workspace_path: Path | None = None,
    max_chars: int = MAX_OUTPUT_CHARS,
) -> str:
    text = _as_text(value)
    if not text:
        return ""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if api_key and len(api_key) > 6:
        text = text.replace(api_key, "[REDACTED_API_KEY]")
    text = _SECRET_PATTERN.sub("[REDACTED_SECRET]", text)
    if workspace_path is not None:
        norm_fwd = str(workspace_path).replace("\\", "/")
        norm_back = str(workspace_path).replace("/", "\\")
        text = text.replace(norm_fwd, "./workspace").replace(norm_back, "./workspace")
    if len(text) > max_chars:
        return text[:max_chars] + f"\n... [output bounded at {max_chars} chars]"
    return text


def _bounded_text(value: str | bytes | None, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    return _sanitize_output(value, max_chars=max_chars)


def _valid_relative_script(script_path: Path) -> bool:
    return not script_path.is_absolute() and ".." not in script_path.parts and script_path.name != ""


def run_python(
    source_workspace: Path,
    script_path: Path | str,
    args: Sequence[str] = (),
    *,
    limits: SandboxLimits | None = None,
) -> SandboxResult:
    """Run a copied workspace's relative Python script under POSIX limits.

    The original workspace is never used as a subprocess working directory and
    is never modified by this function. Windows and other non-POSIX platforms
    return an explicit result without creating a child process.
    """

    if not _supports_posix_sandbox():
        return SandboxResult(
            success=False,
            exit_code=None,
            stdout="",
            stderr="",
            timed_out=False,
            status="unsupported_platform",
            error="Sandbox execution requires a POSIX platform with resource limits.",
        )

    source_workspace = Path(source_workspace)
    relative_script = Path(script_path)
    if not source_workspace.is_dir():
        return SandboxResult(False, None, "", "", False, "execution_error", "Workspace does not exist.")
    if not _valid_relative_script(relative_script):
        return SandboxResult(False, None, "", "", False, "execution_error", "Script path must be relative.")

    active_limits = limits or SandboxLimits()
    try:
        with tempfile.TemporaryDirectory(prefix="bugfix-job-") as temporary_root:
            temp_path = Path(temporary_root)
            copied_workspace = temp_path / "workspace"
            shutil.copytree(source_workspace, copied_workspace)
            copied_script = (copied_workspace / relative_script).resolve()
            if not copied_script.is_file() or copied_workspace not in copied_script.parents:
                return SandboxResult(
                    False,
                    None,
                    "",
                    "",
                    False,
                    "execution_error",
                    "Script does not exist inside the copied workspace.",
                )

            # Construct clean, unprivileged execution environment.
            # Secrets (e.g. OPENROUTER_API_KEY, cloud/Render tokens) are NEVER passed.
            safe_env = {
                "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                "LANG": os.environ.get("LANG", "en_US.UTF-8"),
                "LC_ALL": os.environ.get("LC_ALL", "en_US.UTF-8"),
                "HOME": str(temp_path),
                "TMPDIR": str(temp_path),
                "PYTHONUNBUFFERED": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            for var in ("SYSTEMROOT", "WINDIR", "COMSPEC"):
                if var in os.environ:
                    safe_env[var] = os.environ[var]

            process = subprocess.Popen(
                [sys.executable, str(relative_script), *args],
                cwd=copied_workspace,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=safe_env,
                start_new_session=True,
                preexec_fn=lambda: _set_resource_limits(active_limits),
            )
            try:
                raw_stdout, raw_stderr = process.communicate(timeout=active_limits.wall_timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    process.kill()
                raw_stdout, raw_stderr = process.communicate()
                return SandboxResult(
                    success=False,
                    exit_code=process.returncode,
                    stdout=_sanitize_output(_as_text(raw_stdout) or _as_text(exc.output), copied_workspace),
                    stderr=_sanitize_output(_as_text(raw_stderr) or _as_text(exc.stderr), copied_workspace),
                    timed_out=True,
                    status="timed_out",
                    error="Wall-clock timeout exceeded.",
                )

            stdout = _sanitize_output(raw_stdout, copied_workspace)
            stderr = _sanitize_output(raw_stderr, copied_workspace)
            return SandboxResult(
                success=process.returncode == 0,
                exit_code=process.returncode,
                stdout=stdout,
                stderr=stderr,
                timed_out=False,
                status="passed" if process.returncode == 0 else "failed",
            )
    except (OSError, shutil.Error) as exc:
        return SandboxResult(False, None, "", "", False, "execution_error", "Execution failed due to an OS-level error.")
