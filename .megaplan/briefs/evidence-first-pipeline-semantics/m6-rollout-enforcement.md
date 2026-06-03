# M6: Rollout to Enforcement

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Finish the shadow -> warn -> enforce rollout with operator-visible status, chain, and cloud behavior. Enforcement should be understandable, scoped, and safe for legacy/prose/human-deferred paths.

## Scope

IN:

- Productize mode semantics:
  - `shadow`: no control-flow change, visible would-block diagnostics.
  - `warn`: same routing as today, but status/chain/cloud summaries expose would-block evidence debt.
  - `enforce`: typed gate with denial detail, retryability, and waiver options.
- Enforce by policy over evidence refs, not only green-suite deltas.
- Configure which evidence classes block, warn, pass unknown, or require human.
- Add operator-visible denial summaries in local status, chain status, and cloud/resident surfaces.
- Define legacy defaults: old artifacts warn/shadow unless explicitly migrated.
- Define prose/doc/creative mode evidence defaults.
- Define human-deferred behavior and `awaiting_human` semantics.
- Add docs/runbook for interpreting evidence denials and waivers.

OUT:

- No new schema design.
- No new transition route expansion.
- No global hard enforcement for legacy plan dirs.

## Locked Decisions

- Enforcement blocks must never be hidden as critique/retry loops.
- Unknown/unavailable evidence has per-edge policy, not accidental pass/fail behavior.
- Human-deferred criteria route explicitly, not as fake objective gate success.

## Open Questions

- Initial default enforcement matrix.
- Operator command names for waivers/resume.
- Which status/cloud surfaces get full detail versus summary.
- Whether migration tooling is needed for old high-value plans.

## Constraints

- Avoid false-positive deadlocks.
- Keep cloud/unattended behavior explicit: no hidden waits without status.
- Preserve manual override capability as scoped waiver.

## Done Criteria

1. Shadow/warn/enforce semantics are documented and tested.
2. Status, chain, and cloud surfaces show would-block/block evidence details.
3. Enforcement matrix covers low-risk evidence classes first.
4. Legacy artifacts default to warn/shadow unknown semantics.
5. Prose and human-deferred modes have explicit evidence/awaiting-human behavior.
6. Waiver/override flow is documented and leaves durable decision records.
7. Tests cover shadow, warn, enforce, legacy, prose, human-deferred, retryable, and non-retryable denials.

## Touchpoints

- status CLI / views
- `megaplan/auto.py`
- `megaplan/chain/__init__.py`
- `megaplan/cloud/*`
- override/waiver commands
- docs/runbooks
- rollout tests

## Rubric

- Profile: `partnered`
- Robustness: `thorough`
- Depth: `medium`

Rationale: high-stakes rollout, but lower structural novelty after the previous milestones.

