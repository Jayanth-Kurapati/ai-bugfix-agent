"""Deterministic pylint JSON analysis for copied workspaces."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Sequence


@dataclass(frozen=True)
class LintFinding:
    """Pylint output normalized for diagnosis context."""

    path: str
    line: int
    column: int
    severity: str
    message_id: str
    symbol: str
    message: str


@dataclass(frozen=True)
class LintResult:
    """Result of executing and parsing one pylint invocation."""

    success: bool
    status: str
    exit_code: int | None
    findings: list[LintFinding]
    raw_findings: list[dict[str, Any]]
    stdout: str
    stderr: str
    error: str | None = None


def _valid_relative_path(path: Path) -> bool:
    return not path.is_absolute() and ".." not in path.parts and path.name != ""


def _normalize_finding(finding: dict[str, Any]) -> LintFinding:
    return LintFinding(
        path=str(finding.get("path", "")),
        line=int(finding.get("line", 0)),
        column=int(finding.get("column", 0)),
        severity=str(finding.get("type", "unknown")),
        message_id=str(finding.get("message-id", "")),
        symbol=str(finding.get("symbol", "")),
        message=str(finding.get("message", "")),
    )


def lint_workspace(
    source_workspace: Path,
    target_paths: Sequence[Path | str],
    *,
    timeout_seconds: float = 15.0,
    command: Sequence[str] = (sys.executable, "-m", "pylint"),
) -> LintResult:
    """Run pylint JSON analysis only against a temporary copy of a workspace.

    A generated empty rcfile disables repository-provided pylint configuration,
    keeping the deterministic pre-pass independent of untrusted init hooks.
    ``success`` means pylint completed and its JSON was parsed; pylint findings
    can legitimately produce a nonzero ``exit_code``.
    """

    source_workspace = Path(source_workspace)
    normalized_targets = [Path(path) for path in target_paths]
    if not source_workspace.is_dir():
        return LintResult(False, "execution_error", None, [], [], "", "", "Workspace does not exist.")
    if not normalized_targets or any(not _valid_relative_path(path) for path in normalized_targets):
        return LintResult(False, "execution_error", None, [], [], "", "", "Target paths must be relative files.")
    if timeout_seconds <= 0:
        return LintResult(False, "execution_error", None, [], [], "", "", "Timeout must be positive.")
    if not command:
        return LintResult(False, "execution_error", None, [], [], "", "", "Pylint command is required.")

    try:
        with tempfile.TemporaryDirectory(prefix="bugfix-lint-") as temporary_root:
            copied_workspace = Path(temporary_root) / "workspace"
            shutil.copytree(source_workspace, copied_workspace)
            copied_targets = [(copied_workspace / path).resolve() for path in normalized_targets]
            if any(not target.is_file() or copied_workspace not in target.parents for target in copied_targets):
                return LintResult(
                    False,
                    "execution_error",
                    None,
                    [],
                    [],
                    "",
                    "",
                    "Target file does not exist inside the copied workspace.",
                )

            rcfile = copied_workspace / "safe-pylintrc"
            rcfile.write_text("# Deliberately empty: do not load workspace pylint configuration.\n", encoding="utf-8")
            completed = subprocess.run(
                [*command, "--output-format=json", f"--rcfile={rcfile}", *map(str, normalized_targets)],
                cwd=copied_workspace,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                shell=False,
            )
    except FileNotFoundError as exc:
        return LintResult(False, "missing_executable", None, [], [], "", "", str(exc))
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout or ""
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr or ""
        return LintResult(False, "timed_out", None, [], [], stdout, stderr, "Pylint timed out.")
    except (OSError, shutil.Error) as exc:
        return LintResult(False, "execution_error", None, [], [], "", "", str(exc))

    try:
        parsed = json.loads(completed.stdout)
        if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
            raise ValueError("Pylint JSON output must be a list of objects.")
        raw_findings = list(parsed)
        findings = [_normalize_finding(finding) for finding in raw_findings]
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        return LintResult(
            False,
            "malformed_output",
            completed.returncode,
            [],
            [],
            completed.stdout,
            completed.stderr,
            f"Could not parse pylint JSON: {exc}",
        )

    return LintResult(
        True,
        "completed",
        completed.returncode,
        findings,
        raw_findings,
        completed.stdout,
        completed.stderr,
    )
