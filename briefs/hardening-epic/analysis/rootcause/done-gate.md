# Root cause — gate / review / PR / merge lens

Symptom: all 12 milestones show `pr_number:null` / `pr_state:null` despite
`merge_policy:auto`; m6b folded in with a RED suite, no gate caught it.

## 1. Intended phase order at end of a milestone

The chain does NOT run review/gate/merge as its own phases. It only drives a
**plan** to a terminal status and reacts to that status.

- Per-milestone loop: `megaplan/chain/__init__.py:1208` (`while idx < len(...)`).
- It drives the plan: `_drive_plan_with_blocked_execute_recovery(...)`
  (`__init__.py:1353`). All of execute→review→gate→finalize happens *inside* the
  plan's own state machine (`auto.py`), not in the chain.
- Chain reads the terminal status and maps it: `_handle_outcome(...)`
  (`__init__.py:1362`). `status == "done" → "advance"` (`__init__.py:1108-1110`).
- Only AFTER `decision == "advance"` does any PR/merge code run
  (`__init__.py:1379-1416`).

So "done" is decided by the plan; PR/merge is a chain-side afterthought gated
on `use_pr`.

## 2. What `merge_policy:auto` actually does — and why PR is null on all 12

The entire PR/merge block is guarded:

```
# __init__.py:1211
use_pr = push_enabled and bool(milestone.branch)
...
# __init__.py:1379
if decision == "advance" and use_pr and state.pr_number is not None:
    ...
    state.pr_state = _enable_auto_merge(root, state.pr_number, ...)  # :1415
```

`merge_policy` is only ever consulted at `__init__.py:1397`
(`if spec.merge_policy == "review"`) — i.e. it only chooses between *manual-merge
wait* vs *auto-merge*, and ONLY when `use_pr` is true and a PR already exists.

`use_pr` is false whenever `push_enabled` is false **or `milestone.branch` is
empty** (`__init__.py:1211`). With no per-milestone `branch`, `use_pr=False`, so:
- the init/phase PR-creation blocks (`__init__.py:1283-1337`, which call
  `_ensure_milestone_pr`) never run → `state.pr_number` stays `None`;
- the advance block (`__init__.py:1379`) short-circuits on
  `use_pr and state.pr_number is not None`;
- the milestone is recorded with `pr_number: state.pr_number` /
  `pr_state: state.pr_state` = both `None` (`__init__.py:1423-1424`).

That is exactly the observed `null/null` on all 12. The PR/merge step is
**optional and was never reached** — `merge_policy:auto` is dead config because
its precondition (`use_pr` + an existing PR) was unmet on every milestone.
(Plausible cause: milestones ran without a `branch`, or `push_enabled` false via
`--no-push`/`MEGAPLAN_CHAIN_NO_PUSH`.) `merge_policy` is *never* validated
against `use_pr`, so it fails silent.

## 3. Is the GATE a hard precondition for "done"? No.

Two independent reasons a milestone reaches "done" with a red suite:

(a) **There is no programmatic green-suite gate anywhere.** The `gate` handler
runs only between `STATE_CRITIQUED → STATE_GATED` and judges the **plan**, not
test results (`handlers/gate.py:341-345`, `require_state(state,"gate",
{STATE_CRITIQUED})` at `gate.py:450`). Review never shells out to pytest — grep
of `megaplan/review/checks.py` and `handlers/verifiability.py` for
`pytest/subprocess/run_tests` returns nothing. Review is LLM-judged
evidence/coverage only.

(b) **Review's only hard block is coverage, and it force-proceeds on rework
cap.** In `handlers/review.py:_resolve_review_outcome`:

```
# review.py:223-229  — the ONLY hard block
blocked = (verdict_count < total_tasks or check_count < total_checks
           or bool(missing_evidence))
if blocked:
    return "blocked", STATE_EXECUTED, "review"
...
# review.py:248-252  — cap hit → proceed anyway
if prior_rework_count >= max_review_rework_cycles:
    issues.append("Max review rework cycles (...) reached. "
                  "Force-proceeding to done despite unresolved review issues.")
...
# review.py:271 — falls through to DONE
return "success", STATE_REVIEWED if with_feedback else STATE_DONE, None
```

A reviewer that returns anything other than `needs_rework` (or that exhausts the
rework cap) lands on `STATE_DONE` regardless of unresolved/red issues.

**Bypass path (execute → done, no review at all):** `handlers/execute.py:211`:
if the robustness tier's workflow does not include `review`, execute writes a
**stub review with `review_verdict:"approved"`** and sets `STATE_DONE` directly
(`execute.py:212-222` for `bare`; `execute.py:248-272` stub for other
review-less tiers). No test suite is ever consulted.

## 4. Where "milestone complete" should require gate-passed + merged but doesn't

- `megaplan/chain/__init__.py:1109-1110` — `status=="done" → "advance"` with no
  check that a test suite passed or a PR merged.
- `megaplan/chain/__init__.py:1379` — PR/merge is conditional
  (`use_pr and state.pr_number is not None`); a milestone with no branch/PR
  "completes" with `pr_number=None` and is appended as done at `:1418-1426`.
- `megaplan/chain/__init__.py:1417-1426` — `state.completed.append(...,
  status=outcome.status, pr_number=None, pr_state=None)` is the literal point
  where a milestone is marked complete without ever requiring merged/green.
- `megaplan/handlers/review.py:223-229` — the lone hard gate checks coverage,
  not test results; `:248-252` force-proceeds past unresolved issues.

There is no code anywhere that asserts a green test suite before a milestone is
marked done, and `merge_policy` is never enforced as a precondition for
completion.
