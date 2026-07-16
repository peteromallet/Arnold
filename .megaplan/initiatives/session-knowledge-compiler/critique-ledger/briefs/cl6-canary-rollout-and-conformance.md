# CL6 — Gated canary, compatibility rollout, and conformance closeout

## Outcome

Enable the ledger path for a small allowlist through staged boundaries, prove
mixed-version/WBC conformance and automatic rollback, and produce a final release
evidence bundle. Broad deployment and old-path retirement remain separate gates.

## In scope

- Revalidate every prior handoff, implementation/source revision, WBC contract,
  feature flag, owner, cohort, threshold, and rollback prerequisite.
- Canary by immutable new plan/run IDs: selection/briefing first, then
  reconciliation, then reviser/gate consumption with review between stages.
- Preserve legacy and candidate evidence; exercise component-level disable,
  fallback, mixed-version downgrade, projection rebuild, and rollback rehearsal.
- Add observability/SLOs, automatic stop triggers, conformance/migration matrix,
  incident/operator runbook, and final proof manifest.
- Define but do not perform broad enablement, deployment/restart, old reader/
  artifact deletion, or historical backfill gates.

## Out of scope

Production-wide rollout, remote push/merge, deployment, restart, deletion,
retention shortening, authority transfer, automatic repair, or generalizing the
ledger beyond Megaplan critique loops.

## Locked decisions

- Canary promotion is staged and evidence-gated; no single flag silently changes
  all role boundaries.
- Automatic rollback on occurrence loss, unsupported closure, significant
  suppression, stale briefing, schema/receipt failure, novelty breach, persistent
  budget breach, or unapproved gate divergence.
- Rollback restores the validated legacy consumption path but preserves all
  append-only evidence and gate history.
- Retirement requires separate authority after two accepted observation
  windows; it is not inferred from this sprint's success.
- WBC/Run Authority/Megaplan owners retain their existing authority.

## Open questions

- Which exact canary cohort and observation-window size are approved by owners?
- What production token/latency SLOs and error budgets apply after CL5 evidence?
- Which team owns ongoing semantic-quality sampling and incident response?
- What later approval retires old readers/artifacts or backfills history?

## Constraints

CL5 must explicitly accept canary. Use immutable allowlist identities, current
WBC/runtime revision checks, least-privilege evidence access, and default-off
flags. Every promotion and rollback is receipted and reversible. Stop on target
revision drift or unresolved owner/gate. Keep the staged canary, observation,
review, conformance, and handoff within roughly two weeks.

## Done criteria

- Staged canary passes all acceptance metrics and observation windows without a
  hard failure; every promotion has exact evidence and reviewer receipt.
- Automatic stop/disable and full rollback rehearsals restore legacy behavior
  while retaining replayable candidate evidence.
- WBC boundary/attempt/evidence/payload, critique custody, evaluator, role-flow,
  mixed-version, privacy, fault, replay, and negative-authority suites pass.
- Final support/migration matrix has no unexplained producer/consumer/version
  row and names later retirement/deployment gates explicitly.
- Final conformance manifest maps every North Star invariant and metric to exact
  proof and lists any operational follow-on without claiming it completed.

## Touchpoints

Feature flags/config; evaluator/briefing/reconciliation/reviser/gate adapters;
WBC contracts/receipts/conformance; compatibility readers; observability and
runbooks; CI/release evidence; rollback and projection rebuild tests.

## Anti-scope

No broad rollout, old-path deletion, deployment/restart, weakened fail-closed
checks, mutable-name allowlists, authority transfer, or evidence cleanup.

## Written handoff after CL6

Write and review `docs/critique-ledger/handoffs/cl6-final-conformance.json` with
all milestone/handoff/source hashes, canary windows and metrics, WBC and mixed-
version conformance, rollback receipts, support/migration matrix, North Star
proof map, remaining operational gates, and an explicit statement that broad
enablement/deployment/restart/retirement were not performed. This is the epic
completion evidence and the sole input to any separately authorized rollout.
