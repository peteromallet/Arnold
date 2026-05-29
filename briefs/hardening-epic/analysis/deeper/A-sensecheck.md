# A — Layer 0 critique-cap sense-check (adversarial)

Branch `feat/critique-cap-completion-contract`. Verified by reading code + running
`tests/test_gate.py` (61 passed). Cited file:line below.

## (a) REAL problems, severity-ranked

### P0 — The ESCALATE branch does NOT escalate or halt under `auto`/chain. It silently loops `revise`.
This is the headline defect and it is the OPPOSITE of the design intent ("never silently
ship a plan with an unresolved significant flag").

- `_critique_terminate_branch` returns `("critique_cap_escalate", "override add-note", …)`
  and, crucially, **does not change `state["current_state"]`** — it stays `STATE_CRITIQUED`
  (gate.py:389-392). The force-proceed branch DOES set `STATE_GATED` (gate.py:393), so only
  escalate is broken.
- The returned `next_step` is placed only in the gate **response** (`_finish_step` →
  `response["next_step"]`, shared.py:435-445). State is persisted with
  `last_gate.recommendation = gate_summary["recommendation"] = "ITERATE"`
  (`_sync_legacy_last_gate_for_workflow`, gate.py:283).
- `auto.drive` never consumes the gate response's next_step; it re-derives from a fresh
  `status` call (auto.py:1373). `status` computes next_step via
  `infer_next_steps`=`workflow_next` (status_view.py:748), driven purely by
  `current_state` + `last_gate.recommendation`.
- For `STATE_CRITIQUED` + `recommendation=="ITERATE"`, the matching transition is
  `gate_iterate → revise` (workflow_data.py:58, workflow.py:221-222). So **status returns
  `next_step="revise"` and auto re-runs revise** — the cap-escalate is invisible. The loop
  is unbounded again exactly when there's an open correctness/security flag (the dangerous
  case). The interactive human path is fine (the operator reads the response text directly).
- Even if it DID surface as escalate, chain defaults `escalate_action="force-proceed"`
  (chain/__init__.py:308) and auto defaults `on_escalate="force-proceed"` (auto.py:1159) —
  so the chain would force-proceed past an open data-loss flag anyway. The design's claim
  that escalate "stops for the user under strict_notes" only holds if `strict_notes` is ON
  (off by default) AND the escalate actually reaches the override path — neither is true here.

**Fix:** in the escalate branch set a state/recommendation the workflow recognizes as
escalation. Either set `state["last_gate"]["recommendation"]="ESCALATE"` (so `gate_escalate`
transitions fire and auto's escalate handling at auto.py:1672+ engages), or set
`current_state=STATE_AWAITING_HUMAN`. Then add a chain/auto guard so escalate-from-cap is
NOT swept up by the default `on_escalate=force-proceed` (otherwise P0 just becomes "force-
proceeds past the significant flag"). Add an auto-level + chain-level integration test.

### P1 — Force-proceed-to-finalize CAN ship genuinely-incomplete work.
The false-kill question from M2/`max_blocked_retries=1`. The severity gate only protects
against `significant`/`likely-significant` flags. A plan that is legitimately not done but
whose remaining flags are classed `minor`/cosmetic gets force-proceeded at round 4
(gate.py:393-398, STATE_GATED→finalize). Is 4 safe? It is **plausible but not empirically
justified in-tree** — the brief asserts "most converge in 1-2, M2 was the 9-round outlier"
but no measurement is cited. `thorough`=6 gives headroom; `full`=4 is the exposure. This is
lower severity than P0 because cosmetic-only is the intended deferral, but "cosmetic" here
== "not significant", which is a broad bucket (see P2).

### P2 — Severity predicate may misclassify blocking flags as cosmetic.
`_open_blocking_flags` only treats `significant`/`likely-significant` as blocking
(gate.py:333). Any flag the critic rated `moderate` (or any non-significant label) with
blocking status is force-proceeded. The PROCEED-path predicate it mirrors (gate.py:169 uses
`== "significant"` only) is even narrower, so there's internal inconsistency about what
"blocking" means. A genuinely-blocking `moderate` correctness flag → silently shipped.

## (b) Things the design missed

- **No-progress streak / iteration coupling.** `_prior_iterate_rounds` counts history ITERATE
  entries (gate.py:289-298) while `_critique_no_progress_streak` reads
  `gate_signals_v{iteration-1}.json` by `state["iteration"]` (gate.py:352, 362;
  `_prior_unresolved_flag_ids` gate.py:543-547). These two counters can diverge on a re-run
  gate at the same iteration (gate re-run without an intervening revise → no new signals
  file, compares against the wrong round) or on RESUME if history is replayed but the
  signals file was never written. Not fatal, but the no-progress early-stop can mis-fire or
  no-op silently.
- **Counter is robust to resume across milestones** (good): streak lives in per-plan
  `state["meta"]` (gate.py:367), each milestone is a distinct plan dir, so no stale-streak
  leak from milestone N→N+1. History persists in state.json so `_prior_iterate_rounds`
  survives resume. Confirmed not the `max_blocked_retries` cross-milestone shape.
- **light is left at cap 4.** Brief §1 wanted light=2; impl ships the default 4 for light
  (only thorough/extreme get 6 via `_critique_cap_key`, gate.py:300-306). Minor — light is
  cheap-by-other-means, but it contradicts the stated policy. bare has no revise edge so the
  ITERATE branch is unreachable — safe.

## (c) Verified FINE
- Force-proceed (cosmetic) branch correctly sets STATE_GATED→finalize and works under auto
  (workflow_next on GATED → finalize, workflow_data.py:68) — tested.
- History records `recommendation="ITERATE"` even when cap fires (gate.py:738), so round
  counting stays consistent across the cap transition.
- thorough picks up 6 via get_effective + `_critique_cap_key` — tested
  (`test_critique_robust_cap_higher_for_thorough`).
- signals file for the current round is written before the prior-round read, so no
  self-comparison (gate.py:70 runs before `_apply_gate_outcome`).
- No double-capping with review.py: review cap is a separate loop/state; no overlap.

## (d) UNtested gap (important)
All 5 new tests call `_apply_gate_outcome` **directly** and assert on its return tuple. None
exercise `handle_gate` → state persistence → `status`/`workflow_next` → `auto.drive`. That
is exactly the layer where P0 lives, so the tests are green while the feature is broken in
auto/chain. Add: (1) an integration test that runs the gate handler and asserts
`status.next_step` is NOT "revise" after the cap with an open significant flag; (2) chain-
level escalate halt; (3) no-progress streak reset across a real revise round.
