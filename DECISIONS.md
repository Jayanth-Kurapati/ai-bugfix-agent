# Decisions

## Confirmed

- Use FastAPI with React/Vite in one Render service and one URL.
- Discover OpenRouter free models at startup and use an ordered fallback list.
- Use `pylint --output-format=json` for static analysis before every diagnosis LLM call.
- Use the ordered loop: diagnose → patch → sandbox verify → retry → independent judge.
- Permit at most three repair iterations, enforced server-side; `MAX_ITERATIONS` defaults to 3 and may only be configured from 1 to 3.
- Generate unified diffs, never full-file rewrites.
- Use an independent Judge LLM to assess whether a passing patch is genuine.
- On Linux/POSIX, use a process-level subprocess sandbox with timeout and CPU/memory resource limits; it is not container or VM isolation.
- On Windows, never execute submitted code unsandboxed; return a clear unsupported-platform result.
- Never automatically install dependencies from cloned repositories.
- Accept repository test commands only as `pytest [arguments and relative target paths]`; tokenize with `shlex.split`, reject shell syntax and escaping/absolute paths, and execute via `sys.executable -m pytest` from the clone root.
- Execute tests with argument lists; never use `shell=True`.
- Keep jobs in an in-memory dictionary keyed by UUID.
- Stream job traces through SSE.
- Support Python only.
- Exclude GitHub OAuth, pull-request creation, and webhooks.
- Exclude Docker, Redis, Celery, databases, vector databases, authentication, and multi-language support.
- Snippet programs are written as `snippet.py`; pytest content is `test_snippet.py` and imports `snippet`.
- Traceback mode runs `snippet.py` in the sandbox and requires zero exit plus absence of the parsed original final exception type/message; unparsable tracebacks or nonzero results block verification clearly.
- Diagnosis, patch, and judge outputs must be exact-schema JSON. One malformed-output retry is allowed for each role; a second malformed output fails the job cleanly and counts toward the call total. Patches must additionally be valid unified diffs.
- `OPENROUTER_API_KEY` is required and `OPENROUTER_BASE_URL` defaults to `https://openrouter.ai/api/v1`. Startup discovers zero-priced `:free` models only. Discovery failure/no eligible model makes jobs return traced `model_unavailable`, never a paid/fixed-model fallback.
- Render builds with `pip install -r backend/requirements.txt && npm --prefix frontend ci && npm --prefix frontend run build`, starts with `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`, and checks `GET /health`.
- “Staged/displayed only” means a tested candidate diff is held as an in-memory, display-only job artifact. It is not Git-staged or written to the original workspace/repository.

## OPEN

None.
