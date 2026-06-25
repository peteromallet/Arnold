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
- Runbooks
  Add rollout and rollback checklist for enabling the platform features beyond
  canaries.

## Verifiable Completion Criterion

- Docs accurately describe what is production-ready and what remains deferred.
- End-to-end conformance covers side effects, brokered credentialed action,
  shared pack dependency, durable DB-backed checkpoint backend, worker lease,
  approval pause/resume, cancellation, stuck-run escalation, and audit lookup.
- Megaplan chain/PR and remote execution conformance preserves existing chain
  state, PR helper, and sync-state behavior under the new broker/durable
  substrate.
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

## Risks And Blockers

- Platform docs can easily overclaim. Every production claim must have a test,
  runbook, or explicit operator prerequisite.
- Keep authoring docs focused: normal workflow authors should not need to
  understand every fleet implementation detail.

## Dependencies

- Depends on M5.
