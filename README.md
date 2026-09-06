# BugFixAgent — AI Bug-Fixing Agent

An agentic bug-fixing tool that automatically diagnoses, patches, and verifies Python code fixes using LLM reasoning. Built as a GenAI Developer Intern build-sprint MVP.

**Input:** A Python file/snippet + test (pytest function or error traceback), or a public GitHub repo URL + a pytest command.

**Output:** A verified patch, produced through a diagnose → patch → sandbox-verify → judge pipeline, with the full reasoning trace streamed live to the user.

---

## Architecture

A single Render web service runs a Python 3.11 FastAPI backend and serves the React/Vite production build at the same origin.

```
┌──────────────────────────────────────────────────────────────┐
│ Render (single service, one URL)                             │
│                                                              │
│  FastAPI Backend                                             │
│  ├── /api/analyze          POST  → creates job               │
│  ├── /api/jobs/{id}/stream GET   → SSE trace events          │
│  ├── /api/jobs/{id}        GET   → poll fallback             │
│  ├── /health               GET   → readiness check           │
│  └── /                     GET   → React SPA (static files)  │
│                                                              │
│  Agent Pipeline (per job)                                    │
│  1. Validate → create temp workspace                         │
│  2. [Repo mode] git clone --depth 1                          │
│  3. pylint static analysis (zero LLM cost)                   │
│  4. Diagnosis (LLM) → structured JSON                        │
│  5. Patch generation (LLM) → unified diff                    │
│  6. Apply diff to copy → sandbox test execution              │
│  7. Retry loop (up to 3 iterations)                          │
│  8. Judge (LLM) → genuine fix verification                   │
│  9. Return trace + diff + verdict via SSE                    │
└──────────────────────────────────────────────────────────────┘
```

### Components

| Component | Path | Purpose |
|---|---|---|
| FastAPI app | `backend/main.py` | Entry point, static file serving |
| API routes | `backend/api/routes.py` | Job CRUD, SSE streaming |
| API models | `backend/api/models.py` | Pydantic request/response schemas |
| Job store | `backend/api/jobs.py` | In-memory, thread-safe, UUID-keyed |
| Orchestrator | `backend/agent/orchestrator.py` | 9-step bounded workflow |
| LLM client | `backend/agent/llm_client.py` | OpenRouter wrapper, fallback list |
| Diagnosis | `backend/agent/diagnosis.py` | Structured diagnosis prompting |
| Patcher | `backend/agent/patcher.py` | Unified diff generation + application |
| Judge | `backend/agent/judge.py` | Independent fix verification |
| Linter | `backend/agent/lint.py` | pylint JSON wrapper |
| Sandbox | `backend/sandbox/runner.py` | Process isolation, timeouts, limits |
| Frontend | `frontend/src/` | React SPA: form, live trace, diff view |

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- An [OpenRouter](https://openrouter.ai) API key (free tier)

### Install

```bash
# Backend
pip install -r backend/requirements.txt

# Frontend
cd frontend && npm ci && npm run build && cd ..
```

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENROUTER_API_KEY` | **Yes** | — | Your OpenRouter API key |
| `OPENROUTER_BASE_URL` | No | `https://openrouter.ai/api/v1` | OpenRouter API base URL |
| `MAX_ITERATIONS` | No | `3` | Repair iterations per job (1–3) |

### Run Locally

```bash
# Start the backend (serves frontend too if built)
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Or, for frontend dev with hot reload:
# Terminal 1: uvicorn backend.main:app --host 0.0.0.0 --port 8000
# Terminal 2: cd frontend && npm run dev
```

Open http://localhost:8000 (production) or http://localhost:5173 (dev mode with Vite proxy).

---

## Usage

### Snippet Mode

1. Select **Code Snippet** mode.
2. Paste your buggy Python code.
3. Choose **Pytest Function** or **Error Traceback** as the test type.
4. Paste the test function or traceback.
5. Click **Start Analysis**.

The reasoning trace streams live: lint findings → diagnosis (known facts, unknowns, hypothesis) → patch generation → sandbox verification → judge verdict.

### Repository Mode

1. Select **GitHub Repo** mode.
2. Enter a public GitHub HTTPS URL (e.g., `https://github.com/owner/repo`).
3. Enter a pytest command with relative paths only (e.g., `pytest tests/test_example.py -q`).
4. Click **Start Analysis**.

The agent clones the repo (shallow, `--depth 1`), builds a file-tree summary, and proceeds with the same pipeline.

### Demo Fixtures

Ready-to-use examples are in the [`demo/`](demo/) directory:

| Fixture | Bug | Test |
|---|---|---|
| `demo/off_by_one/` | Off-by-one error in list indexing | Pytest assertion |
| `demo/wrong_operator/` | Subtraction instead of addition | Pytest assertion |
| `demo/type_error/` | Missing type conversion | Error traceback |

### API

```
POST /api/analyze     → { job_id }
GET  /api/jobs/{id}   → current job state (poll fallback)
GET  /api/jobs/{id}/stream  → SSE stream of trace events
GET  /health          → { status: "ok" }
```

**Request body** (`POST /api/analyze`):
```json
{
  "mode": "snippet",
  "code": "def add(a, b):\n    return a - b\n",
  "test_type": "pytest",
  "test_content": "def test_add():\n    from snippet import add\n    assert add(2, 3) == 5\n"
}
```

---

## Safety Model

### Sandbox Execution

- All submitted/cloned code runs in a subprocess with:
  - **Timeout** enforcement
  - **CPU and memory limits** via `resource.setrlimit` (Linux/POSIX only)
  - **Per-job temporary directories** that are cleaned up after completion
- Tests execute via argument lists (`[sys.executable, "-m", "pytest", ...]`), never `shell=True`.
- Repository test commands are tokenized with `shlex.split` and validated: shell metacharacters, command separators, redirects, expansions, and absolute/escaping paths are all rejected.
- The original workspace (upload or clone) is **never mutated**. Diffs are applied only to a copy.

### Patch Handling

- Patches are **staged/displayed only**. A candidate unified diff is retained in the in-memory job and shown to the user after sandbox verification.
- Patches are **never** applied to the original workspace, Git-staged, committed, pushed, or written back to any repository.

### LLM Interaction

- All LLM responses must be structured JSON matching exact schemas. Malformed responses get one retry; a second failure terminates the job cleanly.
- Every LLM call is counted and exposed to the frontend.
- Only free-tier OpenRouter models are used. Model discovery happens at startup; no model ID is hardcoded.

---

## Known Limitations

> These are stated honestly per the project's design documents. None are hidden or softened.

1. **Sandbox is process-level isolation only** — timeout + resource limits via `resource.setrlimit`, **not** a container or VM sandbox. This provides basic resource control but not full security isolation. Do not run untrusted code in production without understanding this limitation.

2. **Python only** — no other programming languages are supported in this MVP.

3. **No authentication** — the API is unauthenticated. Anyone with the URL can submit jobs.

4. **No persistent storage** — jobs are stored in an in-memory dictionary keyed by UUID. All data is lost when the process restarts. This is acceptable for a single-instance, ephemeral demo.

5. **No GitHub PR/webhook integration** — the tool does not create pull requests, post comments, or respond to webhooks. This is a stretch goal, not part of the MVP.

6. **No dependency installation** — cloned repositories do not have their dependencies installed automatically. Tests that require third-party packages will fail.

7. **Windows unsupported for sandbox execution** — on Windows, submitted code is never executed. Jobs return a clear unsupported-platform result. The sandbox requires Linux/POSIX for `resource.setrlimit`.

8. **Free-tier LLM limitations** — free models rotate on OpenRouter without notice. If no eligible free model is available at startup, jobs return a `model_unavailable` error rather than falling back to paid models.

9. **Single-instance, single-process** — no horizontal scaling, no worker queue, no background job persistence across restarts.

---

## Deployment (Render)

**Build command:**
```bash
pip install -r backend/requirements.txt && npm --prefix frontend ci && npm --prefix frontend run build
```

**Start command:**
```bash
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

**Health check:** `GET /health`

**Required environment variable:** `OPENROUTER_API_KEY`

---

## Development

### Run Tests

```bash
# All backend tests
python -m pytest backend/tests -q --tb=short

# Just the mocked E2E round-trip tests
python -m pytest backend/tests/test_e2e_mocked.py -v
```

### Project Structure

```
├── AGENTS.md              # Project context and rules (source of truth)
├── ARCHITECTURE.md         # Technical architecture document
├── BUILD_PLAN.md           # Build phases
├── DECISIONS.md            # Confirmed design decisions
├── ERROR_LOG.md            # Append-only failure record
├── README.md               # This file
├── backend/
│   ├── main.py             # FastAPI app + static file serving
│   ├── requirements.txt
│   ├── api/                # Routes, models, job store
│   ├── agent/              # Orchestrator, LLM client, diagnosis, patcher, judge, lint
│   ├── sandbox/            # Runner, repo cloning
│   └── tests/              # Backend test suite
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/                # React components, hooks, styles
└── demo/                   # Demo fixtures for testing
```
