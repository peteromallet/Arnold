# Critique-ledger reconciliation safety amendment

**Status:** required CL1 contract amendment before CL2 is replanned or resumed
**Date:** 2026-07-28

## Why this amendment exists

The accepted CL1 contract correctly keeps occurrences immutable and records
semantic reconciliation as append-only events. It still places too much
unreviewed trust in the evaluator's duplicate, refinement, regression, split,
reopen, and resolution judgments.

A wrong semantic decision must not become unquestionable merely because it was
written to the ledger. The design also needs a permanent source of unanchored
discovery, a bounded reviser workload, auditable non-action, and deterministic
region-level staleness.

This amendment changes no lifecycle, execution, repair, revision, or gate
authority. It adds evidence, invalidation, audit, and projection rules around
the existing semantic decisions.

## Locked amendments

### 1. Reconciliation decisions are correctable evidence

Raw `CritiqueOccurrenceEnvelope` records must not assign semantic identity.
Deprecate `semantic_finding_id` on the CL1 occurrence schema through an additive
schema version and retain it only as a legacy-read field. The producer's
occurrence/finding identity remains raw evidence; only reconciliation events
map occurrences to a semantic finding.

Every reconciliation decision is an immutable, addressable event containing:

- the occurrence and candidate-finding identities considered;
- the proposed relation and resulting disposition;
- exact evaluator model, prompt, input, ledger, and plan revisions;
- rationale, evidence references, confidence, and uncertainty;
- any independent audit result;
- an optional `supersedes_event_id` for correction.

Corrections append a superseding decision. They never rewrite occurrences or
prior decisions. Replay must derive the latest valid decision while retaining
the complete disagreement and correction history.

The derived decision state is explicit:

- `accepted`
- `review_required`
- `disputed`
- `superseded`

Gate projections may rely only on current `accepted` decisions. The other
states remain visible and actionable.

### 2. Deterministic tripwires trigger re-review, never semantic closure

Deterministic code marks a finding `needs_reconciliation` when any declared
condition fires, including:

- an anchored plan region changes, disappears, or cannot be resolved;
- evidence or a contract dependency changes;
- a new occurrence has a configured lexical/fingerprint near-match to a
  resolved, duplicate, rejected, or accepted-risk finding;
- an independent audit disagrees with the disposition;
- the input, briefing, model, or schema revision required by the disposition is
  stale or unavailable.

Similarity is only a recall alarm. It may not merge, close, resolve, or suppress
a finding. The exact thresholds and false-positive budget are frozen from the
M6 corpus before CL2 implementation.

### 3. Independent audit is risk-based and non-zero

Every disposition that removes a finding from the active action set is eligible
for independent second-model or human audit. The CL1 amendment must freeze:

- mandatory audit classes for blocking/high-severity and low-confidence cases;
- a deterministic, non-zero sample floor for remaining duplicate, resolved,
  rejected, and accepted-risk decisions;
- disagreement behavior and escalation;
- calibration fixtures that prove the auditor is not simply receiving and
  repeating the original evaluator's rationale.

Audit selection and results are durable ledger events. Audit failure or
disagreement cannot silently preserve closure.

### 4. Blind discovery is mandatory

Every critique round has a non-zero blind discovery lane whose prompt contains
no prior finding identities, dispositions, reconciliation conclusions, or
revision rationales. The exact floor is profile-owned and recorded in the round
manifest; it may not be disabled by the evaluator. The default routing rule is:

```text
blind_slots = max(1, ceil(total_selected_slots * 0.20))
```

Profiles may increase this floor but may not reduce it to zero.

Blind results still enter normal occurrence custody and mandatory
history-aware reconciliation before revise or gate consumption.

### 5. The cumulative ledger is not the reviser's work queue

The ledger grows monotonically. The active action projection does not.

The active projection is derived from explicit disposition, severity, existing
gate policy, deterministic staleness/tripwire state, and declared scope. The
evaluator may propose scope or relevance, but may not silently omit a known
finding from the projection.

It exposes three explicit queues:

- `must_act` — current open/actionable findings under existing gate policy;
- `must_revalidate` — stale, disputed, tripped, or verification-pending rows;
- `context_only` — fresh inactive history that remains visible without creating
  new reviser work.

Only open, reopened, uncertain, stale, verification-pending, or otherwise
policy-actionable findings require a current action or justified non-action.
Closed historical rows remain queryable context without creating a recurring
reviser tax.

Batch actions/non-actions are allowed only when they enumerate every finding ID
and share one concrete action, evidence basis, and reopen rule. Overflow is
explicitly deferred or split; it may not deadlock the loop or disappear.

### 6. Non-action is structured and audited

Free-form plausibility is not sufficient. A non-action must include:

- a typed reason;
- the concrete claim being made;
- evidence references;
- the responsible authority when required by existing policy;
- an expiry or reopen predicate;
- the exact plan-region and dependency revisions on which it relies.

Deterministic validation checks completeness, freshness, evidence reachability,
and suspicious repeated/template rationales. Semantic adequacy is checked by
the gate evaluator or the independent audit policy. A rejected or unauditable
non-action remains active.

### 7. Findings carry region-level freshness anchors

Each finding declares one or more plan-region anchors using stable section
identity plus content hashes, and may additionally declare repository,
contract, or global-plan dependencies. Unknown or cross-cutting scope defaults
to the whole plan rather than pretending to be local.

Region changes deterministically mark affected closure/non-action decisions
stale. Unchanged regions do not require full-ledger semantic re-adjudication.
Movement, split, merge, or deletion of a region becomes an explicit unresolved
mapping until reconciled.

### 8. One finding history records critique, response, and verified outcome

Do not create a second revision ledger. Use one append-only event stream with a
small vocabulary:

- `occurrence_recorded` — what a critic reported;
- `reconciliation_decided` — how it relates to a logical finding;
- `response_declared` — the reviser's action or structured non-action;
- `outcome_verified` — whether the response dealt with the finding;
- `audit_recorded` — an independent challenge or confirmation;
- `decision_superseded` — a correction to an earlier semantic decision.

`outcome_verified` uses explicit `dealt_with`, `partially_dealt_with`,
`not_dealt_with`, or `unknown` states. It binds the outcome to exact plan-region,
evidence, implementation, and model/schema revisions and records why. A reviser
may claim `addressed`, but only independent verification may produce
`dealt_with`.

Each critique round publishes a rebuildable accountability receipt mapping:

```text
critic attempt
  -> occurrence
  -> logical finding / reconciliation decision
  -> response or explicit non-action
  -> verified outcome
  -> remaining question or reopen condition
```

The receipt accounts for every parseable occurrence and every active finding.
It is a projection, not a second authority. A later region/dependency change
does not delete `dealt_with`; it marks that outcome stale and returns the
finding to `needs_reconciliation`.

## Required acceptance scenarios

1. A wrong duplicate decision is independently challenged, superseded, and
   replayed without rewriting either occurrence.
2. A new near-match to a resolved finding trips re-review but does not
   automatically merge or reopen it.
3. Every round retains a blind discovery lane and its prompt is proven free of
   ledger history.
4. A large historical ledger produces a bounded active action projection.
5. Batch non-action cannot omit member identities or mix evidence/reopen rules.
6. Boilerplate non-action fails audit and remains active.
7. Editing one plan section stales findings anchored to it without forcing
   unrelated sections through full reconciliation.
8. A cross-cutting finding with unknown scope defaults to whole-plan freshness.
9. A critique-round receipt proves what was found, what response followed,
   whether it was independently dealt with, and why any item remains open.
10. A reviser's `addressed` claim cannot become `dealt_with` without a separate
    verification event against the exact affected region revisions.
11. A legacy occurrence carrying `semantic_finding_id` is read compatibly but
    new raw occurrences cannot author semantic identity.
12. `review_required` or `disputed` decisions remain visible and cannot support
    a clean gate projection.

## Integration into the existing epic

- **CL1 amendment gate:** review and content-address this decision plus updated
  schemas/goldens. Do not rewrite the completed CL1 history.
- **CL2:** persist corrective reconciliation/audit events, region anchors,
  response/outcome events, tripwire state, and rebuildable active and
  round-accountability projections.
- **CL3:** make blind discovery mandatory and prove prompt isolation.
- **CL4:** implement risk-based audits, correction/supersession, bounded action
  projection, structured non-action, independent outcome verification,
  round-accountability receipts, and region-aware stale/reopen behavior.
- **CL5:** require cutover evidence for blind-lane operation, disposition audit
  coverage, bounded reviser load, correction replay, and region-staleness
  scenarios.

Because CL2 was already initialized against the earlier CL1 handoff, editing its
source brief alone is insufficient. CL2 must be replanned from the amended,
reviewed handoff before execution resumes.
