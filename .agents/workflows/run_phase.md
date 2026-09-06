---
description: Runs a defined phase/day of the Skillians AI Bug-Fixing Agent project to completion — executes its tasks in order, self-verifies each via tests/build, logs failures to ERROR_LOG.md, and stops only on full completion or a genuine blocker.
---

1. Read AGENTS.md, ARCHITECTURE.md, BUILD_PLAN.md, DECISIONS.md, and ERROR_LOG.md (if it exists) in full before acting. Do not rely on rules having auto-loaded — read them explicitly.
2. Identify which phase/task this run covers from the user's message accompanying this command. If it isn't stated, ask once, then proceed. Do not guess the scope.
3. Before writing any code: list the concrete subtasks for this phase and the done-criteria for each (a specific test passing, a build succeeding, a specific behavior verified). This list is the loop's exit condition — do not skip creating it.
4. For each subtask, in order:
   a. Implement only what that subtask needs.
   // turbo
   b. Run the relevant test/build command for it.
   c. Pass → mark done, move to the next subtask. Do not re-touch a subtask once it's passing.
   d. Fail → attempt exactly one fix, then re-run the same command.
   e. Still failing after that one fix → append an entry to ERROR_LOG.md (format in step 8), mark the subtask BLOCKED, and move to the next subtask that does NOT depend on it. If everything remaining depends on the blocked subtask, stop the whole phase here and report — do not work around a blocker silently.
5. Never modify or rebuild a subtask/file that's already complete and passing from an earlier phase, unless you find concrete evidence it's broken — if so, log that evidence in ERROR_LOG.md before touching it.
6. Keep moving through the remaining subtasks without asking permission between each one, EXCEPT stop and ask immediately if you hit: (a) a scope ambiguity not resolvable from AGENTS.md/BUILD_PLAN.md, (b) anything on the excluded-scope list in AGENTS.md, or (c) a safety/security-relevant decision (sandbox behavior, executing untrusted code, credentials, dependency installation from an untrusted repo).
7. Stop the run when EITHER: all subtasks are done and verified (success — report it), or every remaining subtask is BLOCKED (report + wait for the user), or you've made 2 full passes over the remaining list with no net progress (report + wait — this exists specifically to protect LLM call budget, do not keep retrying past this).
8. ERROR_LOG.md entry format — append only, never overwrite or delete existing entries:
   ## [Phase] Subtask name — BLOCKED | RESOLVED (date)
   - Attempted: what was tried
   - Symptom: the exact error/failure, trimmed if long
   - Hypothesis: suspected root cause, if any
   - Fix (if resolved): what actually fixed it
   - Needs (if blocked): the specific information or decision a human must provide
9. At the end of the run, report ONLY: subtasks completed, subtasks blocked (one-line reason each — full detail lives in ERROR_LOG.md, don't repeat it here), the exact test/build commands run and their results, and the LLM/tool-call count used this run if you can determine it. No narrative walkthrough.
