# M6 - Platform Docs, Conformance, And Rollout

## Objective

Document and validate the production platform posture. The docs should make the
boundaries clear: composition is the primitive, platform safety handles
side-effects, credentials, shared reuse, durability, and fleet operation.

## Files To Change And Instructions

- `docs/arnold/native-platform.md`
  Create or update a platform overview covering reconcile, idempotency,
  credential broker, packs/versioning, durable backend, fleet supervision, and
  cancellation. Include a "production-covered vs local-only" matrix so users
  can see which paths are actually protected by broker, reconcile, DB durability,
  leases, and conformance.
- `docs/arnold/security.md`
  Document broker posture, scoped credentials, branch policy, approval gates,
  and audit redaction rules.
- `docs/arnold/operations.md`
  Document leases, heartbeats, progress supervision, cancellation, poison
  projects, staggered restart, capacity measurement, and rollback.
- `docs/arnold/package-authoring-contract.md`
  Add pack/versioning/re-pin guidance without weakening the composition
  contract.
- Conformance tests
  Add an end-to-end platform conformance scenario: shared pack workflow runs in
  a leased project, performs a brokered git action and an audited LLM/provider
  call where covered, records forensic audit refs, resumes after interruption
  with reconcile on the DB-backed backend, passes through an approval gate, and
  can be cancelled safely. Add Megaplan chain/PR conformance covering milestone
  PR creation, commit/push, auto-merge enablement or documented fallback,
  PR-merge wait advancement, remote `_capture_sync_state`, and chain state
  save/load across process restart.
  Rerun the exact composition M6 structural conformance, handler-purity,
  mutation, static topology, fixed scenario, rendered policy, override matrix,
  and source-path reconciliation suites against the installed package artifact,
  not only against source files.
- Runbooks
  Add rollout and rollback checklist for enabling the platform features beyond
  canaries.
- Final native-representation closeout
  Create `docs/arnold/megaplan-native-representation-conformance-report.md`.
  This is the final report-conformance ledger for the three-chain sequence,
  not a replacement for the target report. It must include sections for
  these exact headings:
  `Structural conformance`;
  `Handler purity inventory`;
  `Mutation tests`;
  `Static topology snapshots`;
  `Fixed scenario manifest`;
  `Installed package source-path reconciliation`;
  `Platform preservation rerun`.
  It must explicitly map each row in
  `docs/arnold/megaplan-native-representation-traceability.yaml` to implemented
  or deferred with proof, and no report-owned Megaplan semantic may be deferred
  because it still lives in handlers, route labels, manifests, native traces,
  or runtime side effects. Also create
  `docs/arnold/megaplan-native-representation-conformance.yaml` with schema
  `arnold.megaplan_native_representation.conformance.v1`. The YAML ledger must
  reference the target report and traceability file, include one row for every
  traceability row id, allow only `implemented` or `deferred` statuses, and
  require `id`, `status`, `semantic_carrier`, and `proof_artifacts` for each
  row. Any `deferred` row must include `downstream_owner`, `blocking_proof`,
  and `reason`. Validate the YAML ledger with
  `python scripts/validate_native_representation_conformance.py --conformance
  docs/arnold/megaplan-native-representation-conformance.yaml`. Create the final platform
  `proof-map.json` and run `megaplan chain manifest --spec
  .megaplan/initiatives/native-platform-followup/chain.yaml --proof-map
  <proof-map.json>` to produce
  `.megaplan/initiatives/native-platform-followup/completion-manifest.json`.

## Verifiable Completion Criterion

- Docs accurately describe what is production-ready and what remains deferred.
- End-to-end conformance covers side effects, brokered credentialed action,
  shared pack dependency, durable DB-backed checkpoint backend, worker lease,
  approval pause/resume, cancellation, stuck-run escalation, and audit lookup.
- Megaplan chain/PR and remote execution conformance preserves existing chain
  state, PR helper, and sync-state behavior under the new broker/durable
  substrate.
- Installed-package Megaplan native-representation conformance passes after
  broker, DB durability, reconcile, worker leases, cancellation, and rollout
  changes. The suite must prove the platform did not collapse visible workflow
  routes into runtime side effects.
- Rollout checklist names required branch protection, credential provider setup,
  database/backend setup, and fallback procedures.
- No doc tells users to bypass broker, leases, or reconcile for production
  agent work.
- A design-doc reconciliation table maps every explicitly deferred or
  out-of-scope item from the original design doc to one of: delivered by
  completion, delivered by composition, delivered by platform, intentionally
  deferred, or rejected.
- The docs contain an operator decision record for the DB backend, credential
  broker coverage, and rollout mode; each production claim links to a test,
  runbook, or required operator prerequisite.
- `docs/arnold/megaplan-native-representation-conformance-report.md` exists
  and proves final report conformance row by row against
  `docs/arnold/megaplan-native-representation-traceability.yaml`, including the
  required structural conformance, handler-purity, mutation, static topology,
  scenario, source-path, installed-package, and platform preservation evidence.
- `docs/arnold/megaplan-native-representation-conformance.yaml` exists with
  schema `arnold.megaplan_native_representation.conformance.v1`, covers every
  row id from `docs/arnold/megaplan-native-representation-traceability.yaml`,
  and records row status, semantic carrier, and proof artifacts in a
  machine-readable form. `python
  scripts/validate_native_representation_conformance.py --conformance
  docs/arnold/megaplan-native-representation-conformance.yaml` passes.
- The final platform `proof-map.json` and generated
  `.megaplan/initiatives/native-platform-followup/completion-manifest.json`
  exist and include the final conformance report plus all declared proof
  artifacts needed to audit the three-chain sequence.

## Native Representation Alignment

- Matrix rows owned or affected: all platform-affected rows in `docs/arnold/megaplan-native-representation-alignment-plan.md`, especially Human decision/suspension; Execute approval/no-review/deferred-human gates; Auto-drive/event/liveness transitions; Golden trace regeneration guard; Canonical source path reconciliation; Behavior parity with existing Megaplan.
- Expected status change: no platform-owned row may remain `missing` or planning-only `enabled`; each must be `implemented` or explicitly `deferred` with downstream owner and blocking proof.
- Proof artifacts: end-to-end platform conformance scenario, Megaplan chain/PR conformance, installed-package post-hardening structural conformance rerun, handler-purity inventory rerun, mutation/static-topology/scenario/policy/override/source-path reruns, production-covered/local-only matrix, rollout and rollback checklist, final `docs/arnold/megaplan-native-representation-conformance-report.md`, final `docs/arnold/megaplan-native-representation-conformance.yaml`, final conformance YAML validator output, final `proof-map.json`, and final `completion-manifest.json`.
- False-pass guard: platform docs or green production tests do not count if structural conformance shows Megaplan workflow semantics were moved back into opaque handlers or runtime side effects.
- Doctrine-preservation check: rerun the exact source/manifest/native_program
  relationship proof against the installed package after platform hardening.
  Platform events, manifests, broker hooks, reconcile logic, DB resume, and
  worker supervision must remain consumers of compositional source semantics,
  not owners of Megaplan product routing or loop decisions.
- Deferrals: every deferred production claim must be mapped to delivered by
  completion, delivered by composition, delivered by platform, intentionally
  deferred, or rejected. Deferrals are limited to production coverage, scale,
  rollout, or operator prerequisites; platform M6 may not defer Megaplan
  routing, loop exits, suspension semantics, override behavior, model routing,
  execute/review decisions, replay semantics, or source authority back into
  handlers/runtime side effects.
- Canonical paths/imports: final conformance must include installed-package/source-path reconciliation and prove chain/PR/remote execution still use the canonical source.

## Risks And Blockers

- Platform docs can easily overclaim. Every production claim must have a test,
  runbook, or explicit operator prerequisite.
- Keep authoring docs focused: normal workflow authors should not need to
  understand every fleet implementation detail.

## Dependencies

- Depends on M5.
