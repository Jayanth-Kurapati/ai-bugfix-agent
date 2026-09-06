# Build Plan

## 1. Core backend and orchestrator

- Create the prescribed FastAPI, API, agent, sandbox, and frontend layout.
- Implement request validation, UUID-keyed in-memory jobs, polling, trace records, and the exact nine-step orchestration sequence.
- Use `pylint --output-format=json` to produce the pre-diagnosis structured issue list.
- Enforce a server-side repair cap of three iterations (`MAX_ITERATIONS` accepts only 1–3) and expose per-job LLM-call counts.

## 2. Sandbox and testing

- Build per-job temporary workspaces and shallow public-repository cloning with path-and-size summaries.
- Apply unified diffs only to a workspace copy.
- Implement POSIX subprocess execution with timeout and CPU/memory limits; use argument lists and never `shell=True`.
- Restrict repository commands to `pytest` plus parsed pytest arguments/relative target paths; normalize execution to `sys.executable -m pytest` from the clone root.
- Write snippets as `snippet.py` and pytest content as `test_snippet.py`; for a traceback, run `snippet.py` and require a zero exit plus disappearance of the parsed original exception signature.
- Return a clear unsupported-platform result on Windows; do not install cloned-repository dependencies automatically.

## 3. LLM integration

- Discover OpenRouter free models at startup, filter eligible models, and maintain an ordered fallback list.
- Add counted, exact-schema JSON calls for diagnosis, patch generation, and an independent judge.
- Retry one malformed response for each role, then fail the job clearly; validate unified-diff format before applying it.
- Require `OPENROUTER_API_KEY`; if startup discovery fails or finds no eligible free model, return traced `model_unavailable` job errors without paid-model fallback.

## 4. Frontend

- Build React/Vite input paths for snippet and repository modes.
- Render SSE trace events, patch diff, sandbox/test result, judge verdict, blocked/error states, and call count.
- Provide polling fallback through the job-status endpoint.

## 5. Render deployment

- Configure one Python 3.11 Render web service with `pip install -r backend/requirements.txt && npm --prefix frontend ci && npm --prefix frontend run build`, then start `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
- Provide `GET /health` for Render health checks, exposing only readiness, POSIX-platform support, and model-discovery availability.
- Add required environment-variable documentation and verify POSIX sandbox behavior on Render Linux.
- Clearly disclose ephemeral in-memory jobs and process-level—not container/VM—sandboxing.

## 6. Final QA and demo

- Test successful fixes, malformed LLM JSON, failed patches, iteration-cap blocking, judge rejection, cloning errors, and Windows refusal.
- Confirm original workspaces are never mutated, no submitted code escapes the sandbox, and no LLM call is uncounted.
- Prepare a short demo using a Python-only example and the live SSE trace.

## Patch handling

- Keep each tested candidate diff as an in-memory, display-only job artifact. Never modify the original workspace or Git-stage, commit, push, or write back a patch.
