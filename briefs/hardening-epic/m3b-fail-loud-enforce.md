# M3b — Make failures loud: enforce strict policy

**Rubric:** `partnered//high`, robustness `full`
**Position in epic:** milestone 5 of 12. Depends on M1, M2, and M3a (implements M3a's decision table). Runs after the known bugs are fixed so newly-surfaced errors are real signal, not noise.

## Outcome
Apply the control-flow-changing half of the raise/warn/emit decision table from M3a: the sites where a silent failure currently corrupts or misrepresents state must now raise or emit a distinguishable structured signal.

## Scope (IN)
Implement every site M3a's census classified as raise/halt. The known control-flow sites (audit + gap-hunt) include — but are **not limited to** — the list below; the M3a census is authoritative:
- **Tiebreaker downgrade** — `handlers/critique.py:544-550`: emit the distinguishable signal defined in the M3a table (the agreed grep-stable token, e.g. `TIEBREAKER_DOWNGRADED_MISSING_FIELDS`), so a malformed gate response is distinguishable from a legitimate ITERATE. It already computes which fields are missing — surface that, don't bury it.
- **State discard on corrupt JSON** — the `_merge_state_to_disk` site (was `_pipeline/executor.py:124-126`). **GATED:** first read the post-M2 `executor.py` — M2 may have moved `state.json` persistence behind a store method. Apply the halt/back-up to wherever the write path actually is post-M2. The back-up must be atomic (rename corrupt file before writing), not a non-atomic `shutil.copy`.
- **Vendor-lock guard** — `chain.py` `_warn_vendor_ignored_for_locked_profile` (`:1518-1530`): make the swallowed profile-load failure surface. Confirm the "no profile / `vendor=None`" path is still legitimate before making it raise — add the test the M3a table specifies for that scenario.
- **Corrupt-state read in pipeline steps (gap-hunt; corrected per Opus)** — `_pipeline/stages/inprocess_step.py:118-127`: this is a *read-only* `_read_state` fallback that silently returns `{}` on corrupt JSON (NOT itself the overwrite — the overwrite is at the executor merge site). Make it distinguish missing-vs-corrupt and surface the corrupt case, so a handler doesn't run against silently-blanked state. (GATED on the post-M2 path.)
- **Execute corrupt-batch + scope-drift (gap-hunt)** — `execute/core.py:828-829` (corrupt batch artifact silently skipped → dependent batches may wrongly proceed via the prereq check at `:844-851`) and `core.py:761` (snapshot failure → empty diff hides all changed files in the blocked-by-quality signal). These corrupt a *blocking* decision — surface them per the table.
- **auto.py write-failure (gap-hunt)** — `auto.py:893-896` returns `False` on a failed `state.json` write but the caller at `:1244` discards it and proceeds as if the orphaned step was cleared. Halt or surface on write failure.

## Locked decisions
- Implement the M3a decision table as written; do not re-open the raise/warn/emit classification.
- Operations whose silent failure corrupts or misleads state raise or emit a distinguishable signal; the grep-stable token from M3a is the contract.
- The `executor.py` fix lands on the **post-M2** write path, confirmed by reading the merged code first.

## Open questions (for plan to resolve)
- Post-M2, where does `state.json` actually get written, and is `_merge_state_to_disk` still live or dead? (read before patching)
- Does making the vendor-lock guard raise break any legitimate caller passing `vendor=None`?

## Constraints
- Must not crash on legitimately-empty/first-run conditions.
- Coordinate with M2: the persistence path may have moved — the fix must target live code, not a stale path.

## Done criteria
- The tiebreaker downgrade emits the distinguishable signal; a test asserts a malformed gate response is NOT silently treated as ITERATE (asserts the grep-stable token appears).
- Corrupt `state.json` halts or atomically backs up (no blind overwrite); test covers the corrupt-state case against the post-M2 write path.
- Vendor-lock load failure surfaces; the "no profile" scenario has a test confirming it still works.
- No bare `except Exception: pass` / `except: pass` remains at the enumerated control-flow sites.
- M0 baselines green (goldens updated only where behavior deliberately changed, with rationale).

## Touchpoints
`megaplan/handlers/critique.py`, `megaplan/_pipeline/executor.py` (or wherever M2 moved the write path) + `stages/inprocess_step.py`, `megaplan/execute/core.py`, `megaplan/chain.py`, `megaplan/auto.py`, `tests/`.

## Anti-scope
- Do NOT change the M3a classification.
- Do NOT split god files (M5*) or rename concepts (M4).
- Do NOT change store routing (M2) — only the error handling around the persistence path.
- **Enforceable guardrail:** NO edits to `_phase_command`, `drive()` next-step selection, `workflow_next`/`infer_next_steps`, `loop/engine.py` dispatch, or chain↔auto coupling, EXCEPT re-export-only moves. The `auto.py` error-handling fixes here are dispatch-*adjacent* — a reviewer greps these symbols to confirm next-step/dispatch logic is untouched.
