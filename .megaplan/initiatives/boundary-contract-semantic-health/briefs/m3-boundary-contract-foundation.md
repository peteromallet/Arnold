# M3: Boundary Contract Foundation

## Outcome

Introduce workflow-agnostic boundary vocabulary that can describe Megaplan
phases and future Arnold workflow boundaries.

The model separates contract declaration, producer/observer evidence, and
semantic findings. It becomes the shared vocabulary for production, promotion,
transition authorization, semantic-health verification, repair, status, and
auditing without turning any single class into the owner of all of those jobs.

## Scope

IN:

- Define boundary contract data structures:
  - `boundary_id`;
  - `workflow_id`;
  - `phase`;
  - `owner`;
  - `repair_domain`;
  - `invocation_id` / `run_id` requirements;
  - input refs;
  - scratch outputs;
  - canonical outputs;
  - receipts;
  - `phase_result`;
  - expected state delta;
  - expected history entry;
  - transition policy ref;
  - external effect refs;
  - completion witnesses;
  - in-progress witnesses;
  - graph/dependency refs;
  - outcome policy;
  - temporal policy.
- Define `BoundaryReceipt` / `BoundaryEvidence` records:
  - producer id;
  - invocation/run id;
  - artifact refs and fingerprints;
  - event journal refs;
  - step-IO envelope refs;
  - warrant/capsule refs where available;
  - authority level;
  - evidence profile;
  - freshness and observation time.
- Define generic primitives that prevent the model from becoming a linear
  software-pipeline-only abstraction:
  - `BoundaryGraph`: dependencies, joins, fan-out/fan-in, cross-workflow refs,
    entity lineage, and peer-join requirements;
  - `BoundaryOutcome`: complete, incomplete, partial, tier-accepted,
    awaiting-external-evidence, waived, superseded, voided, rollback-complete,
    irreversible, degraded-continue;
  - `EvidenceProfile`: provenance, trust level, internal/external source,
    physical/digital source, actor identity, tool/version vector, confidence or
    statistical sufficiency, privacy class, and observation window;
  - `TemporalPolicy`: staleness, deadline, verification timeout, minimum
    observation duration, expiry, and sunset/renewal semantics as separate
    fields;
  - `AuthorityRecord`: actor, role, scope, conditions, quorum/delegation, expiry,
    revocation, waiver reason, and evidence refs.
- Define boundary families with required-field profiles:
  - artifact promotion;
  - lifecycle transition;
  - reducer;
  - external effect;
  - execution custody;
  - human approval/waiver;
  - graph join/fan-out;
  - external witness / physical evidence.
- Add a registry/provider pattern that can expose contracts for Megaplan first
  and other workflows later.
- Express the prep M1 rule as a contract instance.
- Add tests that verify contract serialization, lookup, receipt serialization,
  and prep rule parity.
- Add one non-Megaplan contract/evidence/finding test in M3, not M10, that
  proves a boundary can be graph-shaped, externally evidenced, and
  partially/conditionally accepted. A trivial linear artifact test is not enough.
- Reuse existing vocabulary where possible from:
  - step IO envelopes and contract results;
  - workflow manifest/runtime effects and control slots;
  - transition evidence contracts;
  - event journals/folds;
  - store/warrant/capsule projections.

OUT:

- Migrating every phase immediately.
- Making BoundaryTurn own routing.
- Forcing all workflows to implement every field at once.

## Locked Decisions

- The contract declares durable effects; it does not execute them or observe
  them.
- Contracts are generic enough for non-Megaplan workflows.
- Receipts/evidence record what happened; findings record mismatches.
- Staleness, deadlines, sufficiency windows, and expiry are separate concepts;
  do not collapse them into one timestamp field.
- Human approvals and waivers are authority records, not booleans.
- Responsibility stays split:
  - producers/promoters write receipts/evidence;
  - transition writers authorize;
  - semantic health verifies;
  - repair/status/auditor consume.
- `state.json` is a projection, not the source of all truth.

## Done Criteria

1. Prep semantic-health check is driven by contract + evidence + finding
   vocabulary.
2. The model can represent a simple non-Megaplan boundary in tests.
3. Missing contract fields fail closed only where that field is required by the
   boundary type.
4. Contract docs make clear which fields are required for phase, reducer,
   transition, external-effect, custody, and human-approval boundaries.
5. Existing step-IO, event, transition-evidence, warrant, and manifest/runtime
   concepts are referenced or adapted rather than duplicated blindly.
6. The foundation reserves vocabulary for graph-shaped workflows, external
   witnesses, physical evidence, transitive staleness, rollback, irreversible
   boundaries, and data-governance profiles without requiring full
   implementation in M3.

## Touchpoints

- new `arnold_pipelines/megaplan/cloud/boundary_contracts.py` or equivalent
- `arnold_pipelines/megaplan/template_registry.py`
- `arnold_pipelines/megaplan/orchestration/transition_policy.py`
- semantic-health module from M1
- tests under `tests/cloud/` and `tests/arnold/pipeline/`
