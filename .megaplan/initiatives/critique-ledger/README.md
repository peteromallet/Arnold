# Critique Loop / Cumulative Finding Ledger Implementation Epic

This directory is the current-truth front door and canonical index for the
implementation plan derived from
[`../session-knowledge-compiler/briefs/domain-specific-critique-finding-ledger.md`](../session-knowledge-compiler/briefs/domain-specific-critique-finding-ledger.md).
It improves Megaplan's critique → gate → revise loop. It does not broaden,
replace, or reorder the parent Durable Session Knowledge Compiler chain.

## Current truth

The locked architecture is one cumulative logical finding ledger with immutable
per-producer occurrences and bounded per-domain projections. The evaluator
selects critics and gives every history-aware pass prior instructions, every
relevant finding and disposition, revision actions, evaluator conclusions,
evidence, unanswered questions, and reopen conditions. An optional blind pass
may protect novel discovery, but its output must be reconciled against history
before revise or gate. Semantic deduplication is model judgment; deterministic
code owns identity, custody, completeness, freshness, replay, and fail-closed
admission. `no_additional_findings` is an explicit successful result.

Current landed behavior already provides adaptive evaluator-selected lenses,
per-round producer artifacts, canonical per-occurrence finding IDs, custody
receipts, flag/revision/gate state, WBC boundary evidence, and an execution-
attempt ledger. It does **not** provide a cumulative semantic finding identity,
complete cross-round dispositions, mandatory history-aware reconciliation,
domain briefing freshness, or a semantic recurrence signal. The current
`recurring_critiques` value is only adjacent normalized-text intersection.

Workflow Boundary Contracts (WBC) is landed in the target ancestry through
merge `24afce006b9ad20391ac7af10ef67ea0b1774f9f`; its completed topic tip is the
merge's second parent `cbe69337d6f469fd7ae12f1fd0a51007d93b5d70`. WBC owns
durable attempt/effect evidence, payload references, receipts, persistence, and
compatibility boundaries. The critique ledger owns immutable critic occurrences,
semantic finding identities, disposition/reopen events, bounded history
briefings, and rebuildable derived projections. Existing Megaplan components
retain critic selection, revision, gate, and lifecycle authority.

## Five aggressive sprints

| Order | Sprint | Outcome | Run rubric |
|---:|---|---|---|
| 1 | Contract and M6 oracle freeze | Freeze ownership, WBC adapters, schemas, and the content-addressed M6 acceptance corpus | 5/5, `partnered-5/thorough/high +prep` |
| 2 | Ledger persistence and replay | Add WBC-backed append-only events, one-time legacy import, replay, rebuildable projections, and freshness | 5/5, `partnered-5/thorough/high +prep` |
| 3 | Evaluator routing and domain briefings | Route evaluator-selected blind/history-aware tasks with bounded, complete briefings | 5/5, `partnered-5/full/medium +prep` |
| 4 | Reconciliation, reviser, and gate truth | Add semantic reconciliation, explicit dispositions, reopen rules, per-finding revision actions, and honest gate claims | 5/5, `partnered-5/full/medium +prep` |
| 5 | Coordinated cutover and retirement | Revalidate M6 and the semantic loop, back up custody, switch the complete critique loop once, verify, and retire the replaced path | 5/5, `partnered-5/thorough/high +prep` |

Every sprint is bounded to roughly two weeks of skilled human engineering and
must write the named JSON handoff consumed by the next sprint. Missing,
unreviewed, stale, or content-mismatched handoff evidence stops the chain.
The epic is therefore approximately ten weeks of engineering scope; it is
not constrained to one two-week delivery window, and no contract, migration,
validation, or custody recovery work is omitted to force such a limit.

## Canonical index

- [`NORTHSTAR.md`](NORTHSTAR.md) — scoped durable end state and invariants.
- [`chain.yaml`](chain.yaml) — five ordered milestones; fail-closed on failure or
  escalation and review-gated at authority-changing boundaries.
- [`cloud.yaml`](cloud.yaml) — canonical on-box workspace/session and exact local
  target source used for a supported cloud-chain launch.
- [`briefs/`](briefs/) — implementation briefs with outcome, in/out scope,
  locked decisions, open questions, constraints, done criteria, touchpoints,
  anti-scope, and explicit successor handoff.
- [`annexes/wbc-integration.md`](annexes/wbc-integration.md) — concrete boundary,
  schema, custody, persistence, routing, failure, test, cutover, and bounded
  recovery design.
- [`validation/m6-end-to-end.md`](validation/m6-end-to-end.md) — early M6
  reconstruction gate and pre-cutover semantic-loop revalidation.
- [`notes/prep-rubric.md`](notes/prep-rubric.md) — per-sprint difficulty,
  profile, robustness, depth, prep direction, and justification.
- [`research/evidence-and-provenance.md`](research/evidence-and-provenance.md) —
  raw conversation/run/M6/WBC evidence, landed-versus-proposed audit, and exact
  import provenance.
- [`../session-knowledge-compiler/briefs/domain-specific-critique-finding-ledger.md`](../session-knowledge-compiler/briefs/domain-specific-critique-finding-ledger.md)
  — preserved 730-line source plan; evidence and decisions remain authoritative
  inputs, not proof that implementation exists.

## Epic done boundary

The epic is complete only after all five reviewed handoffs and the M6 acceptance
evidence exist; WBC and critique-ledger custody, replay, reconstruction, and
fail-closed suites pass; one coordinated cutover switches every critique-loop
consumer; and the replaced writer/reader path is retired. The cutover retains
only a content-addressed pre-cutover backup and one bounded whole-cutover restore
procedure. Deployment and service restart remain separately authorized
operations even though their eventual execution is part of the cutover gate.

These source assets implement no runtime behavior by themselves. Launch and run
state is recorded separately under durable Megaplan/cloud custody; deployment
and restart remain distinct effects.
