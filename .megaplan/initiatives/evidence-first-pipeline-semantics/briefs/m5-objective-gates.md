# M5: Objective Gates

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Machine-verifiable success criteria become engine-owned checks with structured command evidence. LLMs may interpret objective results, but cannot override required failing gates by prose.

Objective gates run asynchronously at milestone start rather than at every phase boundary, and their blocking behavior is gated by robustness: `light` skips, `full` warns, and `thorough` enforces.

## Scope

IN:

- Define structured objective gate/check specs:
  - criterion id
  - priority
  - command or check type
  - cwd
  - timeout
  - expected result
  - required capabilities
  - manual/human fallback semantics
- Compile machine-verifiable criteria into check specs where safe.
- **Support AUTHOR-DECLARED objective checks (first-class, not only engine-inferred).** A milestone brief / chain spec can declare its mechanical invariant directly as a check spec (e.g. `check: grep -rlE "^\s*(from megaplan[. ]|import megaplan[. ])" --include=*.py outside the plugin → expect 0 matches`), so bulk/mechanical milestones are deterministic BY CONSTRUCTION rather than depending on the engine to guess a grep from prose. Motivating failure: a 337-file rename milestone span-spun forever because its mechanical done-criterion ("no residual old-package imports remain") was left to LLM review, which emitted un-routable global findings; as an engine-run declared gate it would have been a deterministic pass/fail against the live tree, routing a failure straight to re-applying the bulk operation (cross-ref Step-IO m3 `bulk_operation` rework-target). Authoring guidance: mechanical/cross-cutting milestones SHOULD declare their invariants as objective checks; reserve LLM review for semantic judgment.
- Run objective checks through engine-owned execution.
- Record command evidence with `EvidenceRef`s and provenance.
- Launch objective gate execution asynchronously at milestone start.
- Cache or reuse gate results by code hash/head so review and transition policy can cite the same engine-owned facts.
- Apply robustness-gated behavior: skip under `light`, warn under `full`, enforce under `thorough`.
- Inject objective gate results into review as settled engine facts.
- Mark prose-only and human-deferred criteria explicitly.
- Make required objective gate failures available to transition policy.

OUT:

- Do not replay arbitrary worker-reported commands.
- Do not invent fake objective gates for human/prose criteria.
- Do not run objective gates at every phase boundary.
- Do not enable global enforcement beyond the robustness-gated objective gate policy.

## Locked Decisions

- Objective facts are engine-owned.
- Command evidence must preserve command, cwd, exit code, duration, stdout/stderr excerpts, raw log path if applicable, runner source, base/head/code hash, and evidence id.
- Criteria without safe objective specs are explicitly prose-only or human-deferred.
- Objective gates are per-milestone async work, not per-boundary synchronous work.
- Robustness controls gate behavior: `light` skips, `full` warns, `thorough` enforces.

## Open Questions

- Initial supported check types.
- Whitelist/allowlist policy for shell commands.
- How objective gate specs are stored in plan metadata versus derived at review time.
- How unavailable required gates route: `unknown`, `awaiting_human`, or block-by-policy.
- Exact milestone-start scheduling and cancellation behavior for async gates.

## Constraints

- Avoid slow repeated gate runs through async scheduling, caching, or reuse by code hash.
- Preserve current behavior for plans with no objective gate specs.
- Keep async gate failures visible and deterministic for transition policy.
- Do not broaden enforcement beyond the robustness gate.

## Done Criteria

1. Objective criteria can compile to structured check specs.
2. Engine-run checks produce command evidence refs.
3. Objective gates run asynchronously at milestone start and do not run at every phase boundary.
4. Review receives objective results as settled facts.
5. Required failing objective gate can prevent `review -> done` through policy under `thorough`.
6. `light` skips objective gate execution, `full` warns on failures/unavailable gates, and `thorough` enforces.
7. Prose-only and human-deferred criteria are explicit.
8. Tests cover passing, failing, unavailable, malformed, prose-only, async milestone-start scheduling, and robustness-gated behavior.

## Touchpoints

- success-criteria metadata / plan metadata
- milestone-start orchestration
- `megaplan/orchestration/completion_contract.py`
- `megaplan/orchestration/suite_runner.py`
- review evidence service
- `megaplan/prompts/review.py`
- transition policy inputs
- tests for criteria compilation, command evidence, async scheduling, and robustness gating

## Rubric

- Profile: `premium`
- Robustness: `thorough`
- Depth: `high`

Rationale: structural difficulty and high enforcement risk; this becomes load-bearing for later rollout, with additional care needed to keep async milestone-start gates deterministic and cost-bounded.

