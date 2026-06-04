# M10: Rollout Enforcement

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Finish the shadow -> warn -> enforce rollout with operator-visible status, chain, and cloud behavior. Enforcement should be understandable, scoped, and safe for legacy/prose/human-deferred paths.

Protect the full authority-increase surface, not only `review -> done`, and add a mandatory unattended-context fallback: a blocked gate with no human response must time out, then auto-waive-and-record in `warn` or fail-with-diagnostics in `enforce`. It must never hang indefinitely.

## Scope

IN:

- Productize mode semantics:
  - `shadow`: no control-flow change, visible would-block diagnostics.
  - `warn`: same routing as today, but status/chain/cloud summaries expose would-block evidence debt.
  - `enforce`: typed gate with denial detail, retryability, and waiver options.
- Enforce by policy over evidence refs, not only green-suite deltas.
- Configure which evidence classes block, warn, pass unknown, or require human.
- Protect all authority increases, including task selection, dependency scheduling, resume, chain advancement, transition writes, routing decisions, reset/reconcile, and PR/chain completion paths where used.
- Apply robustness-gated policy: lower-robustness routes skip or warn where specified; thorough/enforce routes block.
- Add unattended fallback for blocked gates with no human available: timeout, then auto-waive-and-record in `warn`; fail-with-diagnostics in `enforce`.
- Add operator-visible denial summaries in local status, chain status, and cloud/resident surfaces.
- Define legacy defaults: old artifacts warn/shadow unless explicitly migrated.
- Define prose/doc/creative mode evidence defaults.
- Define human-deferred behavior and `awaiting_human` semantics.
- Add docs/runbook for interpreting evidence denials and waivers.

OUT:

- No new schema design.
- No new transition route expansion beyond routes already identified by M7/M9.
- No global hard enforcement for legacy plan dirs.
- No indefinite unattended wait state.

## Locked Decisions

- Enforcement blocks must never be hidden as critique/retry loops.
- Unknown/unavailable evidence has per-edge policy, not accidental pass/fail behavior.
- Human-deferred criteria route explicitly, not as fake objective gate success.
- Unattended gates never hang: warn mode records an auto-waiver after timeout; enforce mode fails with diagnostics.
- The protected surface is all authority increases.

## Open Questions

- Initial default enforcement matrix.
- Operator command names for waivers/resume.
- Which status/cloud surfaces get full detail versus summary.
- Whether migration tooling is needed for old high-value plans.
- Timeout defaults and how unattended/human-available context is detected.

## Constraints

- Avoid false-positive deadlocks.
- Keep cloud/unattended behavior explicit: no hidden waits without status.
- Preserve manual override capability as scoped waiver.
- Fallback behavior must leave durable decision records and enough diagnostics to resume.

## Done Criteria

1. Shadow/warn/enforce semantics are documented and tested.
2. Status, chain, and cloud surfaces show would-block/block evidence details.
3. Enforcement matrix covers low-risk evidence classes first.
4. Legacy artifacts default to warn/shadow unknown semantics.
5. Prose and human-deferred modes have explicit evidence/awaiting-human behavior.
6. Waiver/override flow is documented and leaves durable decision records.
7. All authority-increasing surfaces are protected or explicitly documented as deferred.
8. Robustness-gated behavior is implemented and tested.
9. Unattended blocked gates time out and auto-waive-and-record in warn mode.
10. Unattended blocked gates fail with diagnostics in enforce mode.
11. Tests cover shadow, warn, enforce, legacy, prose, human-deferred, retryable, non-retryable, unattended timeout, auto-waive, fail-with-diagnostics, and robustness-gated denials.

## Touchpoints

- status CLI / views
- `megaplan/auto.py`
- `megaplan/chain/__init__.py`
- `megaplan/cloud/*`
- override/waiver commands
- transition policy and authority-increase route registry
- unattended/cloud driver loops
- docs/runbooks
- rollout, unattended fallback, and robustness-gating tests

## Rubric

- Profile: `partnered`
- Robustness: `thorough`
- Depth: `medium`

Rationale: high-stakes rollout, but lower structural novelty after the previous milestones. The main added risk is operational: unattended enforcement must be loud and finite, never a hidden deadlock.

