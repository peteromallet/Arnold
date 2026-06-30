# M2 - Security Broker And Approval Gates

## Objective

Remove raw credentials from the agent process and put high-risk credentialed
actions behind scoped authority and approval gates. The agent should request
credentialed actions from a broker; the broker holds secrets, enforces branch
and operation policy, logs effects, and denies unsafe operations.

## Files To Change And Instructions

- `arnold/security/` or an equivalent broker package
  Create the local credential broker interface and policy model. Include a
  threat model that names the protected assets, covered operation classes,
  trust boundaries, and explicitly uncovered credential paths.
- Git integration call sites
  Route covered credentialed git operations through the broker. The agent
  process must not receive raw push credentials for production-covered paths.
- LLM/provider credential call sites
  Route covered LLM/provider credential use through the broker or an equivalent
  provider proxy. If provider brokering is not implemented, the docs and rollout
  gates must state that those paths are not production-covered.
- `arnold/pipeline/native/audit.py`
  Join broker action logs and content/audit references to per-attempt audit
  records by `run_id` and `step_path`. Capture prompt/completion refs where
  applicable, exact git command/effect refs, redaction status, and retention
  policy without logging secrets.
- CLI / supervisor surfaces
  Add approval-gate handling for protected operations: force-push, push to
  protected branch, credential escalation, or broker policy override. Approval
  waits must suspend durably and resume or cancel through the workflow runtime,
  not block only inside a transient process.
- Tests
  Verify an agent can push to an allowed feature branch through the broker,
  cannot read the credential, cannot push to `main`, and cannot force-push
  without approval.
  Add execute-gate scenarios covering approve, deny, cancel, resume, bare
  no-review-to-done, non-review robustness with deferred must criteria to
  `awaiting_human_verify`, and protected action approval through declared
  workflow suspension.

## Verifiable Completion Criterion

- Covered credentialed git actions run through a broker that holds secrets
  outside the agent process.
- Covered production credential paths expose no raw credential through agent
  environment variables, config files, logs, or broker responses.
- Tokens are scoped per project/repo where supported and short-lived where the
  provider supports it.
- Branch protection policy is enforced by the broker, not only by convention.
- Approval-gated operations pause for approval and denial routes into
  cancellation/stop behavior.
- Approval waits use a documented durable wait primitive. Before M4 this may be
  implemented on the existing checkpoint substrate; after M4 it must run on the
  DB-backed durable substrate.
- Broker/content audit logs record action, effect, prompt/completion refs where
  applicable, git command/diff refs, redaction status, and retention policy
  without logging credentials.
- Approval/no-review/deferred-human behavior is visible as declared suspension,
  route, or effect metadata. Hidden approval through
  `state["meta"]["user_approved_gate"]` alone does not satisfy conformance.

## Native Representation Alignment

- Matrix rows owned or affected: Human decision/suspension; Execute approval/no-review/deferred-human gates; Override full action surface; Model routing by phase/task complexity.
- Expected status change: platform `enabled` for protected action gates and credential policy; composition routes must remain visible.
- Proof artifacts: broker threat model, approval approve/deny/cancel/resume tests, no-review/deferred-human scenario tests, branch-policy tests, credential non-exposure tests, audit-log redaction tests, and uncovered-path matrix.
- False-pass guard: a broker that returns raw secrets to the agent or an approval wait that blocks only in-process does not satisfy the row.
- Deferrals: durable approval waits move to the DB-backed backend in M4; fleet-level cancellation is M5; final preservation check is M6.
- Canonical paths/imports: approval gates must integrate with declared workflow suspension points, not with private handler waits.

## Risks And Blockers

- A broker that hands the raw secret back to the agent does not satisfy this
  milestone.
- Audit logging must not become a plaintext secret sink. Log action/effect, not
  credentials.
- Some provider credentials may need staged rollout; document uncovered paths
  explicitly.
- Any path not covered by broker isolation must be labeled non-production in
  docs, rollout gates, and conformance output.

## Dependencies

- Depends on M1.
