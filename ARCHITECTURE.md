# Architecture

## Scope

Python-only bug-fixing MVP. A single Render web service runs a Python 3.11 FastAPI backend and serves the React/Vite production build at the same origin.

## Components

- `backend/main.py`: FastAPI application and built-frontend static hosting.
- `backend/api`: validate requests, create UUID-keyed in-memory jobs, expose job state and SSE.
- `backend/agent`: orchestrator, deterministic `pylint` linting, OpenRouter client, diagnosis, patching, and independent judging.
- `backend/sandbox`: isolated per-job temporary workspace, shallow public-repository cloning, diff application to a copy, and resource-limited test execution.
- `frontend`: submission form, live trace, diff, judge verdict, and LLM-call counter.

## Job flow

1. Validate request and create a per-job temporary workspace.
2. For repository mode, shallow-clone the public URL and record only a path-and-size tree summary.
3. Run `pylint --output-format=json` on target Python files before every diagnosis call and convert its JSON to the structured issue list.
4. Call a discovered OpenRouter free model for validated diagnosis JSON.
5. Request a validated unified diff from a fallback-capable free model.
6. Apply that diff only to a workspace copy, then run the requested test without `shell=True`.
7. On failure, append sandbox output and retry from diagnosis; no more than three repair iterations.
8. On pass, call an independent Judge LLM and validate its verdict JSON. A non-genuine verdict retries within the same cap.
9. Persist the trace, diff, verdict, and LLM-call count in the in-memory job; emit trace events over SSE.

## Boundaries

- OpenRouter models are discovered at startup from the live free-model list and used through an ordered fallback list; no fixed model ID.
- Submitted or cloned code runs only in a subprocess on Linux/POSIX with timeout plus CPU/memory resource limits.
- On Windows, submitted code is never run unsandboxed; the job returns a clear unsupported-platform result.
- Cloned repositories are not dependency-installed automatically.
- Jobs are ephemeral and local to one process. No Docker, Redis, Celery, database, vector DB, authentication, GitHub OAuth, PRs, webhooks, or non-Python language support.

## Execution policy

- Repository `test_command` uses the grammar `pytest [pytest arguments and relative target paths]`. It is tokenized with `shlex.split`, rejects shell metacharacters, command separators, redirects, expansions, and absolute/escaping paths, then executes as `[sys.executable, "-m", "pytest", ...]` from the cloned repository root. `shell=True` is never used.
- Snippet mode writes the submitted program to `snippet.py`. For `test_type=pytest`, it writes the supplied test function to `test_snippet.py`; that test imports `snippet`. Both are linted/tested from the per-job workspace.
- For `test_type=traceback`, the submitted traceback is an error-signature oracle: extract its final exception type and message, run `[sys.executable, "snippet.py"]` in the sandbox, and accept verification only when it exits successfully and does not reproduce that signature. A nonzero exit or inability to parse the supplied traceback blocks verification clearly.
- Structured LLM responses must be a JSON object with exactly the expected keys and values of the required types. Diagnosis uses `{known: string[], unknown: string[], hypothesis: string, next_action: string, target_files: string[]}`; patching uses `{diff: string}` containing one valid unified diff; judging uses `{genuine_fix: boolean, reasoning: string}`. Each malformed response receives one repair retry. A second malformed response fails the job cleanly, is traced, and counts both calls.

## Runtime configuration and deployment

- `OPENROUTER_API_KEY` is required. `OPENROUTER_BASE_URL` defaults to `https://openrouter.ai/api/v1`; no model ID is configured. Startup fetches `/models`, keeps only zero-priced `:free` models, and orders them for fallback.
- If discovery fails or yields no usable free model, the service stays healthy but marks LLM work unavailable; new analysis jobs terminate with a traced, clear `model_unavailable` error rather than using a paid or hardcoded model.
- `MAX_ITERATIONS` is an optional integer from 1 through 3 and defaults to 3. Sandbox timeout, CPU, and memory limits are server configuration, with safe defaults set in implementation; they are never client-controlled.
- Render build command: `pip install -r backend/requirements.txt && npm --prefix frontend ci && npm --prefix frontend run build`. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`. `GET /health` is the unauthenticated health endpoint and returns only service readiness, platform support, and model-discovery availability.

## Patch retention

“Staged/displayed only” means a candidate unified diff is retained in the in-memory job and presented to the frontend after it has been tested against a copied workspace. It is never applied to the original upload/clone, Git-staged, committed, pushed, or written back to a source repository.
