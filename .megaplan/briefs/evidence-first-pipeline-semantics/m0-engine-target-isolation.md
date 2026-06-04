# M0: Engine Target Isolation

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Make engine/target separation a prevention-first invariant before any evidence or enforcement work depends on it: the driver runs from an isolated frozen worktree or container, the engine is never target-writable, and engine==target overlap is refused before any mutating phase unless an explicit local-dev waiver is recorded.

This retires most contamination detection work by removing the contamination path, and removes the dogfood-shadow trap where a target execute can mutate the frozen driver engine and corrupt later milestones.

## Scope

IN:

- Establish a driver workspace model where the running engine is isolated from the target workspace.
- Freeze or otherwise pin the driver engine before mutating target phases start.
- Refuse engine==target path overlap before execute, review-rework, reset, reconcile, or any other target-mutating phase.
- Allow local development overlap only through an explicit recorded waiver with actor/source, reason, scope, and expiry or retry policy.
- Record enough isolation evidence for later transition policy and provenance milestones to cite: engine path, target path, engine pin, target head/base, waiver id where applicable.
- Ensure all target mutation goes through the target workspace, never through the frozen driver engine.

OUT:

- Do not build broad contamination-detection gates as the primary control.
- Do not solve unrelated sandbox hardening or process isolation beyond engine/target write separation.
- Do not change evidence schemas beyond minimal isolation records needed by later milestones.
- Do not make local development impossible; require an explicit waiver instead.

## Locked Decisions

- Prevention comes before detection: the engine must not be target-writable during mutating phases.
- Engine==target overlap is refused before mutation, not diagnosed after failure.
- Local-dev overlap is a waiver, not a silent normal mode.
- The frozen driver engine is the authority running the pipeline; target changes are work product, not engine updates.

## Open Questions

- Whether the default isolation mechanism is an in-repo worktree separation or a container.
- Exact local-dev waiver command/name and where its durable record is stored.
- How the engine pin is captured for existing in-flight plans.

## Constraints

- Preserve existing local iteration ergonomics when a waiver is explicit.
- Keep setup cheap enough to run before every mutating phase.
- Avoid touching target files during preflight checks.
- Produce operator-visible refusal details with paths, phase, and waiver instructions.

## Done Criteria

1. Driver startup or phase preflight identifies the engine workspace, target workspace, and engine pin.
2. Mutating phases refuse to run when the engine path and target path overlap without an explicit recorded waiver.
3. The local-dev waiver is scoped, durable, visible, and expires or requires deliberate renewal.
4. Target mutation cannot write into the frozen driver engine under the normal path.
5. Isolation records can be referenced by later provenance and transition decisions.
6. Tests cover separated worktree, container or equivalent isolation, overlap refusal, local-dev waiver, and the dogfood-shadow contamination scenario.

## Touchpoints

- engine/run bootstrap and driver workspace setup
- mutating phase preflights
- `megaplan/_core/workflow.py`
- `megaplan/handlers/execute.py`
- `megaplan/handlers/review.py`
- reset/reconcile entrypoints
- waiver/override recording
- isolation and dogfood-shadow regression tests

## Rubric

- Profile: `premium`
- Robustness: `thorough`
- Depth: `high`

Rationale: this is the prevention boundary for the contamination class and must be settled before later evidence gates can rely on the driver engine being trustworthy.

