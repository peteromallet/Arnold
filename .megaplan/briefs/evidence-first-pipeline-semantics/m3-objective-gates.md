# M3: Objective Gates

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Machine-verifiable success criteria become engine-owned checks with structured command evidence. LLMs may interpret objective results, but cannot override required failing gates by prose.

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
- Run objective checks through engine-owned execution.
- Record command evidence with `EvidenceRef`s and provenance.
- Inject objective gate results into review as settled engine facts.
- Mark prose-only and human-deferred criteria explicitly.
- Make required objective gate failures available to transition policy.

OUT:

- Do not replay arbitrary worker-reported commands.
- Do not invent fake objective gates for human/prose criteria.
- Do not enable global enforcement yet.

## Locked Decisions

- Objective facts are engine-owned.
- Command evidence must preserve command, cwd, exit code, duration, stdout/stderr excerpts, raw log path if applicable, runner source, base/head/code hash, and evidence id.
- Criteria without safe objective specs are explicitly prose-only or human-deferred.

## Open Questions

- Initial supported check types.
- Whitelist/allowlist policy for shell commands.
- How objective gate specs are stored in plan metadata versus derived at review time.
- How unavailable required gates route: `unknown`, `awaiting_human`, or block-by-policy.

## Constraints

- Avoid slow repeated gate runs through caching or reuse by code hash.
- Preserve current behavior for plans with no objective gate specs.
- Do not broaden enforcement before M5/M6.

## Done Criteria

1. Objective criteria can compile to structured check specs.
2. Engine-run checks produce command evidence refs.
3. Review receives objective results as settled facts.
4. Required failing objective gate can prevent `review -> done` through policy.
5. Prose-only and human-deferred criteria are explicit.
6. Tests cover passing, failing, unavailable, malformed, and prose-only criteria.

## Touchpoints

- success-criteria metadata / plan metadata
- `megaplan/orchestration/completion_contract.py`
- `megaplan/orchestration/suite_runner.py`
- review evidence service
- `megaplan/prompts/review.py`
- tests for criteria compilation and command evidence

## Rubric

- Profile: `premium`
- Robustness: `thorough`
- Depth: `high`

Rationale: structural difficulty and high enforcement risk; this becomes load-bearing for later rollout.

