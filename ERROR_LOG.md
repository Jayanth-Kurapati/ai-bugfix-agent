# ERROR_LOG.md — Running Record of What Didn't Work

Append-only. Never delete or overwrite an existing entry — if something gets fixed later, add a new entry noting the resolution rather than editing the old one out. This file exists so that a new session (or a different tool/model) doesn't repeat an already-failed approach, and so the README's "known limitations / engineering process" section can be written honestly from a real record instead of memory.

Entry format:

## [Phase] Subtask name — BLOCKED | RESOLVED (date)
- Attempted: what was tried
- Symptom: the exact error/failure, trimmed if long
- Hypothesis: suspected root cause, if any
- Fix (if resolved): what actually fixed it
- Needs (if blocked): the specific information or decision a human must provide

---

## [LLM Wiring] z-ai/glm-5.2:free malformed structured output — RESOLVED (2026-09-05)
- Attempted: Real e2e analysis with off-by-one snippet; z-ai/glm-5.2:free was #1 in preference list
- Symptom: "Structured output remained invalid after one retry." — 4 LLM calls (2 diagnosis attempts × 1 retry each), job status=failed, no HYPOTHESIS trace event emitted
- Hypothesis: z-ai/glm-5.2:free does not reliably produce strict JSON matching DiagnosisResponse schema
- Fix: Demoted z-ai/glm-5.2:free to last in PREFERRED_MODEL_ORDER; promoted google/gemma-4-31b-it:free and minimax/minimax-m3:free which both produce valid structured JSON on the first attempt

## [LLM Wiring] Windows sandbox blocks verification — BLOCKED (2026-09-05)
- Attempted: Real e2e analysis on Windows; diagnosis and patch both succeeded, but sandbox returned unsupported_platform
- Symptom: VERIFY step returns `unsupported_platform` on every iteration, causing the loop to retry until iteration cap or rate limit. Job ended `failed` with 429 Too Many Requests after 12 LLM calls across 2 iterations
- Hypothesis: By design — AGENTS.md/ARCHITECTURE.md: "On Windows, submitted code is never run unsandboxed; the job returns a clear unsupported-platform result." The sandbox requires POSIX (Linux) for subprocess resource limits
- Needs: Deploy to Render (Linux) or run on WSL/Linux to get a fully verified end-to-end run. The LLM pipeline itself (discovery → diagnosis → patch generation) is confirmed working correctly

## [Windows Verification] Immediate termination on unsupported_platform — RESOLVED (2026-09-06)
- Attempted: Stop wasted retries when host OS cannot run POSIX sandbox
- Symptom: Windows runner returns unsupported_platform, but orchestrator previously looped up to max_iterations (burning free-tier LLM quota)
- Hypothesis: Since host platform cannot become POSIX between iterations, repeating diagnosis and patch calls is completely redundant
- Fix: Added early return in orchestrator when `latest_verification.status == "unsupported_platform"` to return `blocked` immediately with clear error message, preserving generated patch and avoiding useless retries

## [Proxy & LLM Parsing] 502 Bad Gateway and Markdown-wrapped JSON — RESOLVED (2026-09-06)
- Attempted: Connect frontend to backend via Vite proxy and parse structured responses from free models
- Symptom: (1) 502 Bad Gateway occurred whenever Vite proxy could not reach port 8000 because uvicorn was not started; (2) Free models like minimax/minimax-m3:free returned valid JSON wrapped in markdown code fences (```json ... ```), causing json.loads to fail with Expecting value: line 1 column 1 (char 0) and triggering malformed_output failure
- Hypothesis: (1) The frontend dev server had been running continuously while the backend process had stopped; (2) OpenRouter free models do not guarantee raw JSON without markdown formatting
- Fix: (1) Confirmed backend starts cleanly with uvicorn on 127.0.0.1:8000 with GET /health returning {"status": "ok"}; (2) Updated llm_client.py to strip markdown code blocks (```json ... ```) from content before JSON decoding, allowing minimax and other models to parse validly

## [Empirical Verification] LLM diff formatting sensitivity across bug types — BLOCKED (2026-09-06)
- Attempted: Real end-to-end runs for 6 bug types using live free model (minimax/minimax-m3:free)
- Symptom: While diagnosis correctly identified the root cause for all 5 pytest bug types (operator, off-by-one, wrong comparison, mutable default, swallowed exception), the generated unified diffs for off-by-one, mutable default, and swallowed exception had minor hunk count or context offsets (e.g. @@ -1,3 +1,6 @@ with 5 actual lines) that failed strict diff validation. The traceback mode failed diagnosis due to free model format sensitivity
- Hypothesis: Free tier models like minimax-m3:free have high conceptual reasoning capability (hypotheses are consistently accurate) but struggle with strict unified diff hunk arithmetic
- Needs: Human decision on whether to adopt fuzzy line-count reconciliation for diff application, or require multi-shot prompt examples for complex diffs

## [Verification Discrepancy] FAILED vs BLOCKED Inconsistency & Diff Application Robustness — RESOLVED (2026-09-06)
- Attempted: Trace why pytest examples showed `blocked` while traceback examples showed `failed`, and eliminate the discrepancy across all 8 generator templates
- Symptom: `mean_score` (traceback) failed with `status="failed"` ("Diff hunk line counts do not match its header.") before sandbox verification could be reached, while `tally_points` (pytest) cleanly reached verification and returned `status="blocked"` ("Sandbox execution requires a POSIX platform with resource limits."). Additionally, some LLMs omitted `a/`/`b/` path prefixes or omitted leading spaces on context lines.
- Hypothesis: Root cause was plainly (a) — traceback mode (and multi-line pytest snippets) failed to reach the `unsupported_platform` check at all because `backend/agent/patcher.py` strictly enforced `consumed_old != old_count` line-count arithmetic from the LLM's `@@ -old,count +new,count @@` header, which LLMs routinely miscount even when context and edits match source code byte-for-byte.
- Fix:
  1. In `_apply_hunks()`, replaced fragile header count arithmetic checks with strict byte-for-byte context validation against `original[cursor]`.
  2. Added forward context scan from `cursor` if `old_start - 1` doesn't match the first context line.
  3. In `_safe_diff_path()`, allowed diffs with or without `a/` / `b/` prefixes while strictly checking path bounds to prevent directory traversal.
  4. In `_parse_unified_diff()`, tolerated missing leading spaces on context lines.
  5. In `_apply_hunks()`, preserved original file indentation for context lines and matched additions to replaced block indentation.
- Verification: 16 out of 16 runs across all 8 bug templates (both Pytest and Traceback modes) passed end-to-end with real OpenRouter LLM calls, consistently reaching `status="blocked"` at the sandbox boundary. Backend test suite passed 43/43 (3 skipped on Windows).

## [Sandbox Hardening] BlockingIOError fork failure & raw traceback leakage — RESOLVED (2026-09-07)
- Attempted: Sandbox verification of pytest snippets on Render Linux container
- Symptom: Verification failed with `BlockingIOError: [Errno 11] Resource temporarily unavailable` from `subprocess.run` inside `__verify__.py`, and the raw traceback with internal server paths leaked into the UI execution note and banner
- Hypothesis: (1) `RLIMIT_NPROC=64` set via `setrlimit` in `runner.py` applies to the entire user ID (`render` UID 1000) across all container processes/threads, causing fork attempts to fail with `EAGAIN`; (2) `_verify_candidate` wrote a wrapper script calling `subprocess.run([sys.executable, '-m', 'pytest'])`, creating an unnecessary nested subprocess fork; (3) Sandbox stderr was passed unmodified into `latest_verification.stderr` without checking for OS-level runtime failures
- Fix:
  1. Omitted `RLIMIT_NPROC` in `backend/sandbox/runner.py` to prevent suffocating the container-wide process table while preserving memory and CPU limits.
  2. Guaranteed child process reaping in `backend/sandbox/runner.py` with `process.poll() is None` cleanup, `killpg(SIGKILL)`, and `process.wait()` in a `finally:` block to prevent zombie processes.
  3. Replaced `subprocess.run` inside `__verify__.py` with in-process `pytest.main(pytest_arguments)`, eliminating the inner subprocess fork entirely.
  4. In `backend/agent/orchestrator.py`, added explicit detection of OS-level sandbox failures (`BlockingIOError`, `OSError`, etc.) and internal runner crashes, logging the full traceback server-side and returning a clean user-facing error message: `"Verification is temporarily unavailable due to server load — please retry in a moment."`.
- Verification: 58/58 backend tests passing (including new unit test `test_sandbox_os_level_failure_sanitized_to_client`). Frontend build succeeds.



