# North Star: Context-First Critique with Cumulative Finding Custody

## Destination

Every Megaplan critique loop preserves what every selected critic found, what
the evaluator concluded, what revision action followed, and why a finding is
open, resolved, rejected, deferred, duplicated, accepted as risk, or unknown.
Later rounds receive bounded domain context without erasing raw evidence or
pressuring critics to invent novelty.

The evaluator remains the semantic routing and reconciliation authority. WBC
and Megaplan custody mechanisms provide durable attempt/evidence boundaries;
the critique ledger never becomes an execution authority, lifecycle writer,
repair queue, or substitute for raw producer artifacts.

## Load-bearing invariants

1. Every critic attempt and parseable occurrence is immutable and addressable,
   including failed attempts and valid `no_additional_findings` results.
2. One cumulative logical finding set has bounded per-domain projections; a
   semantic merge never destroys or rewrites occurrences.
3. Each known finding has an explicit current disposition representing
   acted-on, ignored/non-action, deferred, rejected, duplicate, accepted-risk,
   unknown, or resolved semantics, with rationale and evidence limits.
4. Resolution and non-action include explicit reopen conditions. Relevant plan,
   evidence, contract, or repository changes make stale closure fail visible.
5. Semantic equivalence, refinement, regression, split, and reopen decisions
   are model judgments preserved as append-only reconciliation events.
6. Deterministic machinery proves custody, completeness, freshness,
   idempotency, schema/version compatibility, and exact input/output hashes.
7. The evaluator selects domain critics. Each history-aware pass receives all
   relevant findings—including non-blocking and cross-domain findings—within a
   declared budget and with explicit overflow behavior.
8. Blind discovery is optional; history-aware reconciliation is mandatory
   before revise/gate consumption.
9. `no_additional_findings`, `no_open_blocking_findings`, `no_known_findings`,
   and `no_adjacent_text_matches` remain distinct claims.
10. The reviser records one action or explicit non-action per requested finding;
    the gate sees complete cumulative truth and cannot infer absence from an
    omitted prompt row.
11. WBC owns supported-runtime attempts/effects, declarations, durable payload
    references, boundary receipts, and boundary-semantic findings. This epic
    owns critique-loop semantic reconciliation and compatible projections only.
12. Shadow mode is report-only. Canary and rollout are allowlisted, observable,
    reversible, and gated by evidence; disabling briefing use preserves raw
    occurrence custody and replayability.

## Success measures

- Zero dropped flagged producer outputs and 100% reconciliation coverage.
- The M6 blocked-handoff family reconstructs as one finding with five retained
  occurrences while the accepted replay limitation retains its disposition.
- At least 50% fewer duplicate revision actions than control.
- No more than a five-percentage-point loss in independent new-family recall.
- At least 95% of closure/non-action dispositions cite adequate evidence.
- Stale briefings, missing occurrences, invalid schemas, unsupported closures,
  and incomplete WBC custody fail closed before revise/gate behavior changes.
- Token, latency, false-merge, false-closure, reopen, novelty, and rollback
  metrics are durable and attributable to exact corpus/model/profile versions.

## Anti-scope

- No embedding database, general semantic graph, project-memory platform, or
  hard-coded similarity threshold as semantic authority.
- No parallel execution ledger, authority plane, transition writer, repair
  queue, or lifecycle state.
- No silent truncation, historical backfill that invents semantic relations,
  automatic closure from wording similarity, or severity/disposition collapse.
- No production-wide enablement, old-reader deletion, deployment, restart, or
  chain launch by these planning assets.
