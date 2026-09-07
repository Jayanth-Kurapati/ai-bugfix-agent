# AGENTS.md — Project Context: AI Bug-Fixing Agent

Auto-loaded at the start of every Antigravity/Claude Code session in this repo. Every rule below is non-negotiable unless the user explicitly overrides it in a prompt. Keep this file updated as ground truth — it is the single source of truth for architecture decisions, not a suggestion.

## What this project is
A GenAI Developer Intern build-sprint MVP: an agentic bug-fixing tool. Input: a Python file/snippet + test (pytest function OR error traceback), OR a public GitHub repo URL + a test command. Output: a verified patch, produced through a diagnose → patch → sandbox-verify → (loop) → judge pipeline, with the full reasoning trace streamed live to the user.

## Fixed tech stack — do not substitute without asking the user first
| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.11, FastAPI | Single service. Also serves the built frontend as static files. |
| LLM | OpenRouter, free-tier models only | Fetch the live `:free` model list at startup (`GET /models`, filter `pricing=0`). Keep an ordered fallback list. Never hardcode a single model ID — free models rotate without notice. |
| Frontend | React + Vite | Built to static files, served by FastAPI. ONE deploy, ONE URL — do not split into two separate hosted services. |
| Hosting | Render, single web service | Free tier. |
| Static analysis | pylint or flake8 | Deterministic pre-pass. Runs before any LLM call — never skip this to save time. |
| Sandbox | subprocess, per-job temp dir, timeout + `resource.setrlimit` (CPU/memory) | NOT container/VM isolation. See Limitations below — do not claim otherwise anywhere in the app or README. |
| Storage | In-memory dict keyed by job UUID | No DB in MVP. Acceptable for a single-instance, ephemeral demo. |
| Streaming | Server-Sent Events, `/api/jobs/{id}/stream` | Frontend renders the reasoning trace live as it happens, not as one final blob. |

## Folder structure
```
/backend
  main.py                  # FastAPI app; mounts built frontend as static files
  agent/
    orchestrator.py        # the 9-step loop below
    llm_client.py           # OpenRouter wrapper, fallback model list, per-job call counter
    diagnosis.py             # step 4: prompt + structured-output parsing
    patcher.py                 # step 5: prompt + diff generation
    judge.py                    # step 8: genuine-fix verification
    lint.py                       # step 3 wrapper
  sandbox/
    runner.py                # subprocess execution: timeout, resource limits, temp workspace
    repo_clone.py             # git clone --depth 1, file-tree summary, relevant-file selection
  api/
    routes.py                # /api/analyze, /api/jobs/{id}, /api/jobs/{id}/stream
    models.py                 # pydantic request/response schemas
/frontend
  src/                       # input form, live trace view, diff view, call-budget indicator
/AGENTS.md
/BUILD_PLAN.md
/README.md
```

## The agent loop — implement exactly this sequence, do not reorder or skip steps
1. Receive request → validate input → create an isolated temp workspace.
2. If `mode=repo`: `git clone --depth 1 {repo_url}` into the workspace; build a file-tree summary (paths + sizes only, not full file contents).
3. Run static analysis (pylint/flake8) on the target file(s) → structured issue list. Zero LLM cost — always do this before step 4.
4. **Diagnosis call** (LLM): prompt = code/context + lint issues + test or traceback + file-tree summary (repo mode only). Require structured JSON: `{known: [], unknown: [], hypothesis: str, next_action: str, target_files: []}`. On malformed JSON: retry once, then fail the job cleanly with a clear error — never crash silently.
5. **Patch call** (LLM): given the hypothesis + target file content, generate a unified diff — not a full file rewrite.
6. Apply the diff to a **copy** of the workspace (never mutate the original clone/upload) → run the test (pytest command, or reproduce the traceback) inside the sandbox runner → capture pass/fail + output.
7. If fail and `iteration < MAX_ITERATIONS` (default 3, env-configurable): append the failure output to context, return to step 4. If the cap is hit: return job status `blocked` with the full trace — never fail silently without explanation.
8. If pass: **Judge call** (LLM): given the original bug report + final diff + test output, verify the fix is genuine — i.e., it didn't just weaken, delete, or otherwise game the test. Structured JSON: `{genuine_fix: bool, reasoning: str}`. If `false`: treat as a failed iteration and loop (respecting the cap).
9. Return the full trace (all steps), the diff, the judge verdict, and total LLM-call count used, to the frontend via the SSE stream.

## API contract
- `POST /api/analyze` — body: `{mode: "snippet"|"repo", code?, test_type?: "pytest"|"traceback", test_content?, repo_url?, test_command?}` → `{job_id}`
- `GET /api/jobs/{job_id}/stream` — SSE stream of trace events as the loop executes
- `GET /api/jobs/{job_id}` — poll fallback; returns current/final job state

## Non-negotiable rules
- Never auto-commit or push anywhere, ever. Patches are staged/displayed only.
- Never execute submitted or cloned code outside the sandboxed subprocess (timeout + resource limits enforced).
- Every LLM call increments the job's call counter; always expose that count to the frontend — the free-tier daily quota is tight (see BUILD_PLAN.md).
- Diagnosis/Patch/Judge LLM outputs must be structured JSON, validated before use — never pass raw LLM text directly into patch application.
- The iteration cap is enforced server-side, never just in the UI.

## Known MVP limitations — state these honestly in the README, never overclaim
- Sandbox is process-level isolation (timeout + resource limits), not a full container/VM sandbox.
- Sandbox provides CPU/memory/process isolation via `resource.setrlimit`, but not network isolation; executed code could still make outbound network requests within the short execution timeout.
- Python only, no other languages in the MVP.
- No auth, no persistent storage beyond process lifetime.
- No real GitHub PR/webhook posting integration (stretch goal only — see BUILD_PLAN.md).

## Current status
*(Update this line at the end of each session so the next session starts oriented.)*
Phase complete (2026-09-07): BlockingIOError fork failure eliminated & sandbox exception leakage prevented:
1. Omitted RLIMIT_NPROC in backend/sandbox/runner.py: prevents suffocating the shared container UID process limit on Render while retaining memory and CPU limits.
2. Guaranteed sandbox subprocess reaping: process.poll() check, killpg(SIGKILL), and process.wait() in a finally block in runner.py prevents defunct/zombie processes.
3. Replaced inner subprocess fork in __verify__.py with in-process pytest.main(pytest_arguments) execution, eliminating the nested fork entirely.
4. Added explicit catching of OS-level sandbox failures (BlockingIOError, OSError, etc.) in orchestrator.py: logs full traceback server-side and surfaces sanitized non-technical message ("Verification is temporarily unavailable due to server load — please retry in a moment.") with zero raw tracebacks reaching the UI.
5. All 58 backend tests passing (55 passed, 3 skipped on Windows). Frontend build succeeds (982ms).




