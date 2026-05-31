# Implementation status — A (critique cap) + B (completion contract)

Branch: `feat/critique-cap-completion-contract` (on the live editable install). Not committed.
The branch also carries unrelated pre-existing WIP (cloud templates, shannon, override,
decision_skill, etc.) — NOT part of this feature; commit only the files listed below.

## A — critique-loop cap ("Layer 0"). STATUS: implemented, sense-checked, P0 fixed, green.
Files: `megaplan/handlers/gate.py` (+203), `megaplan/types.py` (+config), `tests/test_gate.py` (+293).
- Cap on the plan-critique loop, scaled by robustness: light **2** · full **4** · thorough/extreme **6** ·
  bare 0. Config: `execution.max_critique_iterations`, `max_robust_critique_iterations`,
  `max_critique_no_progress` (types.py DEFAULTS + _SETTABLE_NUMERIC).
- No-net-progress early stop (2 rounds of resolved=0 & new-blocking≥1), idempotent per `iteration`.
- Severity-gated cap action: cosmetic-only open flags → force-proceed to finalize (`STATE_GATED`);
  any correctness/security flag (incl. **moderate**) → **`STATE_BLOCKED`** hard stop.

### The P0 the sense-check caught (and the fix)
The first cut changed only the gate handler's *return value*, but `auto.drive` is **status-driven** —
it re-derives the next step from STATE via `workflow_next`, ignoring the handler return. So the cap was
**invisible under `auto`/chain** and looped `revise` forever exactly when a correctness flag was open.
**Fix:** route the correctness-cap to `STATE_BLOCKED` — which has no workflow transitions, so
`workflow_next` returns `[]`, `auto.drive` hits its terminal branch and halts, and the chain's
`_decide_action` routes `blocked` to `stop_chain` (NOT the `on_escalate` force-proceed default). This
also resolves P1 (the "stops for a human" guarantee now holds via the hard block). Verified
fail-before/pass-after through the real `status`/`workflow_next` seam, not just the handler return.
Tests: 65 pass (incl. 2 status-path integration tests).

Residual (honest): integration tests cover the status-derivation seam (the load-bearing decision point)
but stop short of a full `auto.drive` subprocess run. P2 predicate is fail-safe-conservative on
unanticipated severity labels. Layers 1 (prompt convergence + churn bound) and 2 (formal loop variant +
anchored re-critique) remain deferred per the pragmatic-ROI sequencing — ship Layer 0, measure residual.

## B — completion contract, SHADOW MODE. STATUS: implemented, sense-checked, 2 verdict bugs fixed, green.
Files: `megaplan/orchestration/completion_contract.py` (new), `completion_io.py` (new),
`megaplan/auto.py` (+88 hook), `megaplan/chain/__init__.py` (+117 hook + `from_dict` fix),
`megaplan/types.py` (config), `tests/test_completion_contract.py` (new, 11 tests).
- Computes + persists `completion_verdict.json` + logs at every terminal "done" (plan & milestone).
  Six evidence providers (phase_coverage, landed_diff, worker_did_work, green_suite, review_disposition,
  declared_noop) composing existing helpers (`validate_execution_evidence`, `PhaseResult`,
  `_latest_execution_batch_all_tasks_done`, finalize baseline).
- `completion_contract_mode` (off/shadow/warn/enforce), **default shadow**. warn/enforce are stubs
  that behave like shadow + a logged WARNING — **no blocking implemented**.

### Sense-check verdict: shadow is SAFE to leave on (verified)
Both hooks are placed AFTER the outcome is decided, comprehensively try/except'd (fail-open), never run
the suite (`suite_run_in_shadow=False`), add ~30ms (one `git status`) per done. The `from_dict`
round-trip fix is correct (93 chain tests pass). Real test count is **11** (the implementer's "15" was
wrong). Control flow is provably unchanged.

### Two verdict-accuracy bugs the sense-check caught (both FIXED)
1. `worker_did_work` only counted per-task `files_changed`, but the real worker payload writes it
   **top-level** → false "no files changed" on legit batches. Fixed (now counts top-level too).
2. `landed_diff` flagged **any dirty/carried working tree** (it reuses `validate_execution_evidence`,
   which lists unclaimed working-tree paths). Fixed: that finding is now **advisory-only in shadow**
   (it's unreliable without a base-ref — the m5a carry case); real signals (phantom claims, hollow-done,
   abandonment, perfunctory notes) still drive `unsatisfied`.

Mandatory before warn/enforce (encoded in `SHADOW_TODOS`): per-milestone **base-ref diff**
(`<milestone_base_sha>..HEAD`, also fixes the m5a carry false-positive); **green-suite real run + cache**
(run once per HEAD, reuse execute's run, raise the 120s cap); a typed **waiver/declared-no-op** artifact;
and the test migration (~30-45 files; ~14 stub-worker tests fail fail-closed).

## Net
Both features green on the editable install; A actually halts now; B observes safely without touching
control flow. Total test footprint added: ~13 new/changed test cases; 662 passed in the consolidated
sweep. Nothing committed yet.
