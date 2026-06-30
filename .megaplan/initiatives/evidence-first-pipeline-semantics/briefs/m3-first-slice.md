# M3: Vertical First Slice — execute -> review -> done

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Prove the evidence-first contract end-to-end on the narrowest load-bearing route: `execute -> review -> done`.

After this milestone, review starts from fresh engine evidence, unsupported blocking review claims are not allowed to route state, and `review -> done` writes a durable `TransitionDecision` with evidence refs.

## Scope

IN:

- Add a narrow `collect_review_evidence(...)` seam before review prompt construction.
- Write review-time current-state evidence separately from execute-time `execution_audit.json`.
- Keep execute-time audit as historical context only unless provenance matches current head/base/invocation.
- Feed fresh engine evidence into the review path used by the first slice.
- Require evidence refs for blocking findings on the `review -> done` route.
- Add `TransitionPolicy`, `TransitionDecision`, and minimal `TransitionWriter` for `review -> done`.
- Make a failing required objective/evidence fact prevent `done` for this route.
- Emit operator-visible denial detail with transition, evidence refs, base/head, retryability, and next action.

OUT:

- No full review schema migration.
- No chain/cloud route enforcement.
- No broad override/recovery rewrite.
- No full objective gate compiler beyond the minimal evidence needed to prove the seam.

## Locked Decisions

- This milestone is a vertical proof, not the final architecture rollout.
- Any enforcement block must be visible as a policy/evidence denial, not disguised as a critique/retry loop.
- Legacy artifacts remain compatible.

## Open Questions

- First artifact name: `review_audit.json`, `review_evidence.json`, or an evidence-ledger entry.
- Exact boundary where existing review state mutation is wrapped by `TransitionWriter`.
- Which first-slice evidence classes block versus warn.

## Constraints

- Preserve existing review/rework behavior outside the governed route.
- Avoid broad auto/chain rewrites.
- Keep tests focused on stale evidence and transition authorization.

## Done Criteria

1. Review-start evidence is collected before prompt construction.
2. Fresh review-time evidence wins over stale execute-time audit.
3. Stale finalize/executor notes cannot override fresh engine evidence.
4. Blocking review findings without evidence refs are downgraded, marked incomplete, or rejected by policy.
5. `review -> done` writes a `TransitionDecision`.
6. Required failing evidence prevents `done`.
7. Denial output explains retryability and next action.
8. Tests cover stale audit, stale finalize note, contradicted evidence, no-inspection review, and transition decision recording.

## Touchpoints

- `megaplan/handlers/review.py`
- `megaplan/prompts/review.py`
- `megaplan/orchestration/completion_contract.py`
- `megaplan/orchestration/execution_evidence.py`
- `megaplan/orchestration/phase_result.py`
- `megaplan/auto.py`
- tests for review, auto transition, completion contract, and execution evidence

## Rubric

- Profile: `premium`
- Robustness: `thorough`
- Depth: `high`

Rationale: this is high-stakes routing/state behavior and the proof that the foundation is usable.

