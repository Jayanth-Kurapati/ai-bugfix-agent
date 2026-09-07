"""Validated API and job-state models."""

import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


AnalysisMode = Literal["snippet", "repo"]
TestType = Literal["pytest", "traceback"]
JobStatus = Literal[
    "queued",
    "running",
    "verified",
    "failed",
    "blocked",
    "model_unavailable",
    "verification_inconclusive",
    "repository_error",
    "invalid_input",
]

_GITHUB_REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?$")


class AnalyzeRequest(BaseModel):
    """Input accepted by the documented analysis endpoint."""

    model_config = ConfigDict(extra="forbid")

    mode: AnalysisMode
    code: str | None = None
    test_type: TestType | None = None
    test_content: str | None = None
    repo_url: HttpUrl | None = None
    test_command: str | None = None

    @model_validator(mode="after")
    def validate_mode_fields(self) -> "AnalyzeRequest":
        if self.mode == "snippet":
            if not self.code or not self.code.strip():
                raise ValueError("snippet mode requires non-empty code")
            if self.test_type is None:
                raise ValueError("snippet mode requires test_type")
            if not self.test_content or not self.test_content.strip():
                raise ValueError("snippet mode requires non-empty test_content")
            if self.repo_url is not None or self.test_command is not None:
                raise ValueError("snippet mode does not accept repo_url or test_command")
            return self

        if self.repo_url is None:
            raise ValueError("repo mode requires repo_url")
        if self.repo_url.scheme != "https" or self.repo_url.host != "github.com":
            raise ValueError("repo_url must be an HTTPS github.com URL")
        repo_path = (self.repo_url.path or "").strip("/")
        if not _GITHUB_REPO_PATTERN.match(repo_path):
            raise ValueError("repo_url must point to a valid GitHub repository 'https://github.com/owner/repo'")
        if not self.test_command or not self.test_command.strip():
            raise ValueError("repo mode requires non-empty test_command")
        if any(value is not None for value in (self.code, self.test_type, self.test_content)):
            raise ValueError("repo mode does not accept snippet fields")
        return self


class AnalyzeResponse(BaseModel):
    job_id: UUID


class TraceEventResponse(BaseModel):
    kind: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    """Current job state returned by the polling endpoint."""

    job_id: UUID
    status: JobStatus
    mode: AnalysisMode
    created_at: datetime
    llm_call_count: int = 0
    iteration_count: int = 0
    trace: list[TraceEventResponse] = Field(default_factory=list)
    diff: str | None = None
    verification: dict[str, Any] | None = None
    judge_verdict: bool | None = None
    judge_reasoning: str | None = None
    error: str | None = None
