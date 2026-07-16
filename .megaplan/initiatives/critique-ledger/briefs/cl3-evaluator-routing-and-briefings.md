# CL3 — Evaluator routing, blind passes, and bounded domain briefings

## Outcome

Extend adaptive critique so the evaluator records domain/mode/budget decisions
and dispatches selected critics with complete, fresh, bounded briefings. Preserve
independent discovery through an optional blind pass and always produce inputs
for mandatory reconciliation.

## In scope

- Extend evaluator inputs/validated outputs with triggering findings/surfaces,
  selected/skipped domains and reasons, blind/history-aware mode, evidence
  targets, budgets, and expected ledger/briefing revisions.
- Build domain briefings from the accepted CL2 ledger, including prior
  instructions, all relevant dispositions, revision actions, conclusions,
  evidence, questions, reopen conditions, and cross-domain findings.
- Add explicit `no_additional_findings`, overflow/split, stale/rebuild, and
  evidence-unavailable contracts.
- Wire optional blind then history-aware fanout while preserving model/profile,
  per-unit routing, raw outputs, attempt custody, and mandatory floors.
- Record included/excluded finding reasons and full input-set hashes.

## Out of scope

Final semantic reconciliation/disposition decisions, reviser/gate consumption,
cutover/retirement, changing severity/gate authority, or a
new domain ontology.

## Locked decisions

- Evaluator selects critics; no permanent always-on roster beyond approved
  deterministic safety/correctness floors.
- Blind is optional and can never bypass history-aware reconciliation.
- Every history-aware briefing carries all materially relevant findings,
  including rejected/deferred/accepted/resolved/unknown and cross-domain rows.
- Overflow is explicit split or evidence-linked hierarchy, never silent omission.
- Critics may report no additional findings without manufacturing novelty.

## Open questions

- What default/floor domains and blind capacity apply per robustness profile?
- Is briefing synthesis performed by the evaluator or a bounded curator call?
- What token/latency budget triggers compression versus split?
- How are cross-domain inclusion/exclusion explanations checked in the frozen
  fixture suite before cutover?

## Constraints

Consume accepted CL1/CL2 handoffs. Preserve current evaluator model routing and
parallel worker isolation unless an explicit tested contract requires change.
Stale or incomplete briefing admission fails before history-aware dispatch.
Keep implementation, tests, review, and handoff within roughly two weeks.

## Done criteria

- Evaluator validation rejects missing/duplicate domain decisions, invalid mode,
  unknown ledger revision, bad budget, and incomplete selection/skip accounting.
- Every selected history-aware critic receives the exact accepted briefing hash;
  blind critics receive no finding history and are marked blind in custody.
- Fixtures cover all dispositions, cross-domain inclusion, overflow/split,
  unavailable evidence, no-additional result, retries, and model/profile routes.
- Token/latency accounting is durable; no input is silently truncated.
- Existing adaptive evaluator and parallel critique suites remain compatible.

## Touchpoints

`audits/critique_evaluator.py`, `prompts/critique_evaluator.py`,
`orchestration/critique_runtime.py`, `parallel_critique.py`, `prompts/critique.py`,
prompt projection/budget code, schemas, routing ledger, custody receipts, and
their focused tests.

## Anti-scope

No semantic database, hard-coded similarity authority, always-on full critic
roster, full-history prompt dump, gate policy change, or production rollout.

## Written handoff to CL4

Write and review `docs/critique-ledger/handoffs/cl3-routing-briefings.json` with
evaluator/briefing schema hashes, routing matrix, floor/budget decisions,
blind/history-aware fixtures, inclusion/exclusion and overflow evidence, model/
profile parity, and failure diagnostics. CL4 must refuse stale or incomplete
briefing/custody inputs.
