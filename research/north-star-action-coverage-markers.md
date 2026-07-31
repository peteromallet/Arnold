# M9 — North Star Action Coverage Markers

Generated: 2026-07-22
Scope: M9 rebuildable projections and liveness — NSA7 and NSA8 closeout
Schema: m9.north-star-action-coverage-markers.v1

## Overview

This document records the plan-level north-star action coverage markers for
NSA7 and NSA8, tying each action to the exact plan-step references and
execution-graph references approved by the gate.  These markers serve as
finalize artifacts that prove NSA7 and NSA8 remain visibly closed for the
M9 milestone.

---

## NSA7 — Resident CLI, Context Tree, and Introspect Ownership

**Gate rationale:** NSA7 is addressed by explicit write paths and targeted
tests for the previously omitted resident and introspection consumers.  The
plan now gives `observability/introspect.py`, `resident/cli.py`, and
`resident/context_tree.py` explicit write ownership and named targeted
regression coverage instead of relying on broad inventory wording.

### Plan-Step References

| Step | Task | File(s) | Description |
|------|------|---------|-------------|
| Step 26 | T26 | `observability/introspect.py` | Upgrade introspect to exact-cursor projections with shared source-cursor vectors, evidence IDs, and typed liveness/block/drift dimensions. |
| Step 29 | T29 | `resident/currently_running.py`, `resident/discord.py` | Preserve Discord/currently-running parity: keep `attention` as an overlay only, listing live execution or active repair with labels from `progress.display_state` and separate attention reasons. |
| Step 30 | T30 | `resident/cli.py`, `resident/context_tree.py`, `observability/introspect.py` | Make explicit, separately reviewable source-cursor metadata changes; preserve intended output compatibility; do not bury these seams under cloud snapshot work. |

### Test Coverage References

| Step | Task | Test File(s) | Description |
|------|------|-------------|-------------|
| Step 54 | T54 | `test_phase_scoped_llm_liveness.py` | Liveness/introspect/doctor parity tests for exact-cursor liveness, stale process exclusion, typed unknowns, and agreement among introspect/status/resident/cloud for identical inputs. |
| Step 56 | T56 | `test_context_tree.py`, `test_cli.py`, `test_phase_scoped_llm_liveness.py` | Targeted regression tests for `resident/cli.py`, `resident/context_tree.py`, and `observability/introspect.py` changes, separate from broader cloud/watchdog suites. |
| Step 59 | T59 | `test_currently_running_command.py`, `test_discord_adapter.py` | Closeout parity tests for Discord and currently-running: proving attention overlay never replaces execution truth for active execute + attention, active repair + attention, and non-active attention. |

### NSA7 Closeout Verification

- [x] `observability/introspect.py` has explicit write ownership (Step 26)
- [x] `resident/cli.py` has explicit source-cursor metadata changes (Step 30)
- [x] `resident/context_tree.py` has explicit source-cursor metadata changes (Step 30)
- [x] Discord/currently-running parity is preserved with attention overlay (Step 29)
- [x] Targeted regression tests exist for all three NSA7 files (Steps 54, 56, 59)
- [x] Attention overlay never replaces execution truth (Step 59)

---

## NSA8 — Critical Path and Dispatch Graph Budget

**Gate rationale:** NSA8 is addressed by the documented 42-minute critical
path and 46-minute estimated dispatch graph, both strictly below the
48-minute admission threshold.

### Execution-Graph References

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Critical path | 42 minutes | < 48 minutes | PASS |
| Estimated dispatch graph | 46 minutes | < 48 minutes | PASS |
| Task count | 66 | — | Admitted |
| Batch count | 16 | — | Admitted |

### NSA8 Closeout Verification

- [x] Critical path documented at 42 minutes (below 48-minute threshold)
- [x] Dispatch graph documented at 46 minutes (below 48-minute threshold)
- [x] Execution order declared in plan metadata (`plan_v8.meta.json`)
- [x] Range-aware timing diagnostics admitted by finalize feasibility check

---

## Gate References

- **Gate output:** `.megaplan/plans/m9-rebuildable-projections-20260722-0431/gate.json`
- **Gate recommendation:** PROCEED
- **Gate rationale (NSA7):** "NSA7 is addressed by explicit write paths and targeted tests for the previously omitted resident and introspection consumers."
- **Gate rationale (NSA8):** "NSA8 is addressed by the documented execution graph below the 48-minute admission threshold."

---

## Notes

1. Both NSA7 and NSA8 are addressed with `action_type=change_plan` in the
   `plan_v8.meta.json` metadata.

2. NSA7 coverage spans Phases 3 and 4 of the plan, ensuring that resident
   CLI, context tree, and introspect surfaces receive explicit write
   ownership rather than being buried under broader cloud/watchdog work.

3. NSA8 coverage is structural: the plan's execution graph was re-sharded
   to fit within the 48-minute hard threshold without weakening any
   authority, observer-purity, or negative-gate protections.

4. These markers are preserved as finalize artifacts and should be carried
   forward into M10 handoff evidence.
