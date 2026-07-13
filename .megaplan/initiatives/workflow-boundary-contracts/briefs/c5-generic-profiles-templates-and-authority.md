# C5: Generic Profiles, Templates, And Authority Adapters

## Outcome

The existing workflow boundary vocabulary gains versioned evidence, graph,
outcome, temporal, and reusable template profiles that work across Megaplan
boundaries without becoming control flow or a second authority system.

Authority-bearing profiles adapt Run Authority decisions/views and Maintenance
`TransitionWriter` records. Structured-output promotion and reusable templates
share one compatibility model.

## Entry Gate

C1-C4 have stable real-run fixtures and receipts across phase, cloud, chain,
publication, repair, and audit boundaries. No unresolved duplicate owner or
compatibility reader is allowed to be generalized.

## Scope

IN:

- Make ledger schemas and durable-reference profiles part of the existing
  versioned boundary vocabulary: required result/verdict/state-delta/effect
  refs, inline size/privacy constraints, retention/redaction/security classes,
  and compatibility rules are mechanically validated rather than prose-only.
- Extend the existing `BoundaryContract`, `BoundaryReceipt`/
  `BoundaryEvidence`, `SemanticFinding`, `BoundaryOutcome`, and
  `AuthorityRecord` surfaces in place.
- Add required-field profiles for artifact promotion, validation, lifecycle
  transition, reducer/fan-in, external effect, execution custody, human
  approval/waiver, graph join/fan-out, and external witness.
- Represent dependency/join/fan-out refs, evidence provenance/trust and
  observation-set digest, partial/conditional/waived/rollback/irreversible
  outcomes, and separate staleness/deadline/verification-timeout/minimum-
  observation/expiry policies.
- Add versioned reusable templates: `RevisionBoundary`,
  `ValidationBoundary`, `ArtifactHandoffBoundary`, and `ApprovalBoundary`.
- Define required core fields, extension policy, expected evidence, valid
  outcomes, compatibility range, structural diff, and deliberate re-pin/upgrade
  flow for each template.
- Integrate the existing structured-output/template registry and promotion
  paths. Model output remains scratch until harness validation and promotion;
  canonical paths stay stable.
- Add authority adapters that reference prerequisite grant/decision/view hashes
  and `TransitionWriter` evidence. Adapters validate and describe; they never
  authorize or mutate.
- Prove at least two Megaplan contexts reuse each selected template shape and
  preserve invocation/fingerprint evidence.
- Provide replay adapters that reconstruct deterministic internal projections
  from an immutable ledger snapshot and retained inputs/results. Non-replayable
  or sensitive/external effects are replaced by explicit recorded witnesses or
  fenced dry-run stubs, never reissued implicitly.
- Provide audit export/proof generation with schema/version vector, ordered
  event range, durable-object availability/retention state, redaction records,
  authority refs, and verifier results. Exports enforce the same ACLs.

OUT:

- A new boundary registry beside the existing shared registry.
- Making templates, BoundaryTurn, or boundary profiles own route selection,
  dispatch, lifecycle mutation, authority acceptance, repair, or status.
- Domain-specific schema families in the generic core.
- Forcing all workflows to implement every profile.

## Locked Ownership

- WBC owns profile/template vocabulary and compatibility rules.
- Workflow producers/promoters emit receipts/evidence through existing writer
  seams.
- Run Authority owns grants/claims/decisions/quarantine and view reduction.
- Maintenance owns coherent observations, `TransitionWriter`, and repair/
  verification custody.
- Domain adapters map onto generic primitives without expanding core authority.

## Compatibility Fixtures

- current Megaplan artifact handoff, validation, revision, and approval cases;
- scratch written but not promoted;
- canonical promoted without required receipt/fingerprint;
- receipt present but phase result or authority decision missing;
- breaking required-field change versus non-breaking optional extension;
- producer/consumer template version mismatch and deliberate compatible re-pin;
- partial, waived with expiry, rollback, irreversible, graph join, and external
  witness outcomes.

## Required Acceptance Evidence

1. Existing boundary/receipt JSON remains readable or returns an explicit
   versioned incompatibility; no silent semantic reinterpretation occurs.
2. Template compatibility distinguishes breaking required-field changes,
   non-breaking extensions, incompatible ranges, and deliberate upgrades.
3. At least two real structured-output paths use reusable profiles and retain
   scratch/validation/promotion/fingerprint/receipt/invocation evidence.
4. Authority adapters reject missing/stale/mismatched decision or view hashes
   and cannot mutate state in negative-control tests.
5. Graph, external evidence, temporal, partial/waived/rollback/irreversible
   cases serialize without Megaplan-specific fields in the generic core.
6. The full C1-C4 fixture suite remains green after schema/profile extension.
7. Public docs state the ownership split and version/upgrade policy.
8. Query/replay golden tests reproduce state/result/verdict projections from a
   pinned snapshot and fail explicitly when required retained data is absent.
9. Security/retention conformance tests cover least-privilege query/export,
   cross-tenant denial, redaction authority/tombstones, legal hold, expiry, and
   secrets scanning.
10. The C1 support manifest reports no unresolved C2-C5 schema, storage,
    producer, consumer, or compatibility migration assigned to Megaplan.

## Automatic Failure Conditions

Fail validation and abort through `stop_chain` if generalization requires route tables in templates, duplicate authority
or transition records, breaking legacy/current fixtures without an explicit
migration, domain-specific fields in core, or a template registry separate from
the existing canonical surface.

Compatibility selection is deterministic: exact pinned versions first, then a
declared compatible range with structural validation; otherwise fail with a
stable incompatibility diagnostic. Never ask for a mid-chain re-pin.

## Likely Touchpoints

- shared workflow boundary evidence vocabulary
- existing Megaplan boundary registry and receipt/evaluator adapters
- structured-output and template registry/promotion paths
- Run Authority and TransitionWriter adapter interfaces
- serialization, compatibility, and promotion tests/docs
