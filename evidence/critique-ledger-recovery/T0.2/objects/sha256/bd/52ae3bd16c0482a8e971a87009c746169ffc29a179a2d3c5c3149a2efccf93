# Critique Loop / Cumulative Finding Ledger Implementation Epic

This directory is the current-truth front door and canonical index for the
implementation plan derived from
[`../session-knowledge-compiler/briefs/domain-specific-critique-finding-ledger.md`](../session-knowledge-compiler/briefs/domain-specific-critique-finding-ledger.md).
It improves Megaplan's critique → gate → revise loop. It does not broaden,
replace, or reorder the parent Durable Session Knowledge Compiler chain.

## Current truth

The locked architecture is one append-only finding history with immutable raw
occurrences and bounded projections. Raw occurrences never assign semantic
identity. A stronger evaluator proposes reconciliation; deterministic code owns
custody, region freshness, sampling, replay, and fail-closed admission; an
independent audit can dispute or supersede semantic decisions. Every round has
a mandatory blind discovery floor plus history-aware critics. The same finding
history records the revision response, independently verified outcome, and
reopen/staleness conditions, then builds a round accountability receipt showing
what was found and what actually happened because of it.

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

CL1 contract/oracle work is already landed on this branch. The cancelled
predecessor's CL2 working tree remains preserved as an audit/source archive but
is not silently adopted.

## Four remaining sprints

| Order | Sprint | Outcome | Run rubric |
|---:|---|---|---|
| 1 | Amended ledger foundation and replay | Version the CL1 contract additively; add WBC-backed events, correction/audit/outcome history, region freshness, bounded projections, import, and replay | 5/5, `partnered-5-glm/thorough/high +prep` |
| 2 | Evaluator routing and mandatory blind discovery | Enforce the blind floor and route history-aware tasks with bounded, complete briefings | 5/5, `partnered-5-glm/full/medium +prep` |
| 3 | Reconciliation, accountability, reviser, and gate truth | Add correctable semantic decisions, independent audits, structured response/outcome history, round receipts, and honest gate claims | 5/5, `partnered-5-glm/full/medium +prep` |
| 4 | Coordinated cutover and retirement | Revalidate M6 and the amended accountability loop, back up custody, switch once, verify, and retire the replaced path | 5/5, `partnered-5-glm/thorough/high +prep` |

Every sprint is bounded to roughly two weeks of skilled human engineering and
must write the named JSON handoff consumed by the next sprint. Missing,
unreviewed, stale, or content-mismatched handoff evidence stops the chain.
The remaining epic is approximately eight weeks of engineering scope. The
completed CL1 evidence remains a prerequisite rather than being rerun.

## Canonical index

- [`NORTHSTAR.md`](NORTHSTAR.md) — scoped durable end state and invariants.
- [`chain.yaml`](chain.yaml) — four ordered remaining milestones; fail-closed on failure or
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

The epic is complete only after the landed CL1 handoff plus all four remaining
reviewed handoffs and M6 acceptance evidence exist; WBC and critique-ledger custody, replay, reconstruction, and
fail-closed suites pass; one coordinated cutover switches every critique-loop
consumer; and the replaced writer/reader path is retired. The cutover retains
only a content-addressed pre-cutover backup and one bounded whole-cutover restore
procedure. Deployment and service restart remain separately authorized
operations even though their eventual execution is part of the cutover gate.

These source assets implement no runtime behavior by themselves. Launch and run
state is recorded separately under durable Megaplan/cloud custody; deployment
and restart remain distinct effects.
