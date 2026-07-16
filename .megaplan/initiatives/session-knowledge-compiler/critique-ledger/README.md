# Critique Loop / Cumulative Finding Ledger Implementation Epic

This directory is the current-truth front door and canonical index for the
implementation plan derived from
[`../briefs/domain-specific-critique-finding-ledger.md`](../briefs/domain-specific-critique-finding-ledger.md).
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
supported-runtime attempt/effect evidence, declarations, payload references,
receipts, and boundary-semantic findings. This epic owns critique-domain
occurrence/reconciliation semantics and projections only. Neither may grant
execution authority or mutate lifecycle state.

## Six aggressive sprints

| Order | Sprint | Outcome | Run rubric |
|---:|---|---|---|
| 1 | Contract and M6 oracle freeze | Freeze ownership, WBC adapters, schemas, and the content-addressed M6 acceptance corpus | 5/5, `partnered-5/thorough/high +prep` |
| 2 | Ledger persistence and replay | Add append-only occurrence/reconciliation storage, compatibility reads, migration, replay, and freshness | 5/5, `partnered-5/thorough/high +prep` |
| 3 | Evaluator routing and domain briefings | Route evaluator-selected blind/history-aware tasks with bounded, complete briefings | 5/5, `partnered-5/full/medium +prep` |
| 4 | Reconciliation, reviser, and gate truth | Add semantic reconciliation, explicit dispositions, reopen rules, per-finding revision actions, and honest gate claims | 5/5, `partnered-5/full/medium +prep` |
| 5 | Offline comparison and report-only shadow | Reconstruct M6, run controlled arms, emit shadow metrics, and prove zero behavioral authority | 5/5, `partnered-5/full/medium +prep` |
| 6 | Canary, rollout, and conformance | Add allowlisted canary gates, mixed-version compatibility, observability, rollback, and release evidence | 5/5, `partnered-5/thorough/high +prep` |

Every sprint is bounded to roughly two weeks of skilled human engineering and
must write the named JSON handoff consumed by the next sprint. Missing,
unreviewed, stale, or content-mismatched handoff evidence stops the chain.
The epic is therefore approximately twelve weeks of engineering scope; it is
not constrained to one two-week delivery window, and no contract, migration,
validation, or rollback work is omitted to force such a limit.

## Canonical index

- [`NORTHSTAR.md`](NORTHSTAR.md) — scoped durable end state and invariants.
- [`chain.yaml`](chain.yaml) — six ordered milestones; fail-closed on failure or
  escalation; review-gated; not launched.
- [`briefs/`](briefs/) — implementation briefs with outcome, in/out scope,
  locked decisions, open questions, constraints, done criteria, touchpoints,
  anti-scope, and explicit successor handoff.
- [`annexes/wbc-integration.md`](annexes/wbc-integration.md) — concrete boundary,
  schema, custody, compatibility, persistence, routing, failure, observability,
  test, rollout, and rollback design.
- [`validation/m6-end-to-end.md`](validation/m6-end-to-end.md) — offline
  reconstruction → controlled comparison → shadow → gated canary sequence.
- [`notes/prep-rubric.md`](notes/prep-rubric.md) — per-sprint difficulty,
  profile, robustness, depth, prep direction, and justification.
- [`research/evidence-and-provenance.md`](research/evidence-and-provenance.md) —
  raw conversation/run/M6/WBC evidence, landed-versus-proposed audit, and exact
  import provenance.
- [`../briefs/domain-specific-critique-finding-ledger.md`](../briefs/domain-specific-critique-finding-ledger.md)
  — preserved 730-line source plan; evidence and decisions remain authoritative
  inputs, not proof that implementation exists.

## Epic done boundary

The epic is complete only after all six reviewed handoffs and the M6 acceptance
evidence exist, all WBC/critique custody and mixed-version tests pass, shadow
thresholds pass, and an allowlisted canary demonstrates fewer duplicate actions
without losing novel findings. Broad rollout, old-format deletion, deployment,
and service restart remain separately authorized operations.

This planning revision implements no runtime behavior, starts no chain, pushes
no branch, deploys nothing, and restarts nothing.
