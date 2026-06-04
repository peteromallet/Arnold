# M1: Evidence Contract

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Freeze the shared evidence/transition vocabulary that every later milestone imports: `EvidenceRef`, `TransitionDecision`, normalized evidence statuses, provenance fields, schema/version fields, and the four trust classes (`claim`, `evidence`, `judgment`, `routing`).

Define the corroborated-done predicate `is_task_satisfied(task, evidence_nucleus, current_head/code_hash)`, so later readers can decide whether a task is actually done by checking evidence freshness and required outputs against the current code/head instead of trusting an asserted flag.

This milestone creates the contract and low-risk telemetry skeleton. It should not change routing behavior.

## Scope

IN:

- Define durable schemas/types for `EvidenceRef` and `TransitionDecision`.
- Add schema/version fields to `PhaseResult` and `CompletionVerdict`.
- Normalize evidence statuses: `satisfied`, `unsatisfied`, `unknown`, `not_applicable`, `waived` or a carefully justified equivalent.
- Define required provenance fields: evidence id, artifact refs, source hashes, invocation id, phase, iteration, base/head SHA, code hash/diff scope, task/criterion ids, command run id/raw log path where applicable, runner source, worker/agent/model/capability context where applicable.
- Extend `completion_contract` provider outputs enough that later review/transition work can cite them by reference.
- Define `is_task_satisfied(task, evidence_nucleus, current_head/code_hash)` as the canonical corroborated-done predicate.
- Require the predicate to evaluate declared task outputs, linked evidence refs, freshness against current head/code hash, and explicit waiver or not-applicable states.
- Add telemetry skeleton for mode, providers used, schema version, legacy/unknown evidence, and would-block reasons.
- Write a canonical schema note or module doc that later milestones can cite.

OUT:

- No review prompt changes.
- No objective gate execution changes.
- No state mutation or enforcement changes.
- No broad artifact stamping beyond what is needed for the new types/tests.
- No projection store or alternate verifier for task completion.

## Locked Decisions

- `completion_contract` is the evidence nucleus; do not create a second verifier.
- `PhaseResult` is a phase-boundary report, not sole routing authority.
- `TransitionDecision` is the durable routing decision record.
- Evidence is reference-oriented: preserve suite runner facts and artifact hashes rather than flattening everything into pass/fail prose.
- Task `done` is a corroborated predicate over evidence and current code/head, not an asserted ledger flag.

## Open Questions

- Exact module placement for shared evidence/transition types.
- Whether `TransitionDecision` is JSONL append-only from day one or one JSON artifact per decision.
- How to encode `waived` without conflating operator waiver, declared noop, and not-applicable.
- Exact return shape and diagnostic detail for `is_task_satisfied(...)`.

## Constraints

- Backwards-compatible readers for existing artifacts.
- Tests must prove old artifacts without new fields load as legacy/unknown rather than crashing.
- No behavior change to existing routing.
- The corroborated-done predicate must be pure enough for authority readers to call without mutating state.

## Done Criteria

1. Shared types/schemas exist and are covered by tests.
2. `PhaseResult` and `CompletionVerdict` carry schema/version information.
3. Completion-contract provider outputs can produce stable evidence refs.
4. Suite-run facts remain linkable: command run id, raw log path, parsed failures, code hash.
5. Legacy artifacts without new metadata are classified as unknown/legacy, not as success and not as parse failures.
6. `is_task_satisfied(task, evidence_nucleus, current_head/code_hash)` exists, is documented, and returns satisfied/unsatisfied/unknown/waived/not-applicable with evidence refs and diagnostics.
7. The predicate treats missing outputs, stale evidence, and head/code-hash mismatch as not satisfied unless explicitly waived.
8. A canonical contract doc or module-level explanation exists for later milestones.

## Touchpoints

- `megaplan/orchestration/completion_contract.py`
- `megaplan/orchestration/completion_io.py`
- `megaplan/orchestration/phase_result.py`
- `megaplan/orchestration/suite_runner.py`
- shared schema/types modules
- task completion/evidence helper modules
- tests for phase result, completion contract, serialization, corroborated-done, and legacy reads

## Rubric

- Profile: `apex`
- Robustness: `thorough`
- Depth: `high`

Rationale: this freezes the contract every later sprint builds on. A wrong abstraction here is the most expensive rework, and the corroborated-done predicate becomes the authority-reader invariant for the rest of the epic.

