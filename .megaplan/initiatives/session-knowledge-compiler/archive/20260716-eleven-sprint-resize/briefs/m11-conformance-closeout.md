---
type: brief
slug: m11-conformance-closeout
title: Cross-Backend Conformance, Failure Hardening, and Operator Documentation
epic: session-knowledge-compiler
created_at: '2026-07-16T00:00:00+00:00'
---

# M11 — Cross-Backend Conformance, Failure Hardening, and Operator Documentation

## Outcome

Prove the full compiler contract across representative resident and automatic-
repair managed-session backends, close cross-layer failure gaps, and deliver
operator/agent documentation and evidence that the North Star is met without
launching or broadly enabling the product as part of this milestone definition.

## In scope

- Build an end-to-end conformance matrix for file/DB where supported, resident-
  managed agents, and at least one automatic-repair/other managed-agent path.
- Cover threshold and every terminal trigger; restart, duplicate, out-of-order,
  lease expiry, partial write, model/schema/store/authorization/adapter failure;
  four outputs; synthesis/correction/search; promotion proposal/review;
  contradiction; paper-cut consolidation; rollout disable/rollback.
- Prove exact direct-Pro route evidence and no unsafe provider fallback.
- Measure/verify primary-session result and terminal-delivery isolation under all
  compiler failures and budget exhaustion.
- Close only defects necessary to satisfy existing contracts; route unrelated
  findings to durable tickets without expanding scope.
- Document agent controls, operator status/retry/disable/rollback, privacy and
  redaction inheritance, known limits, and claim-to-primary-evidence audit.
- Produce `docs/session-knowledge-compiler/handoffs/m11-completion-evidence.md`
  with test commands, results, matrices, known limits, and rollout recommendation.

## Out of scope

Deployment, restart, broad enablement, automatic backlog fixes, organization-
wide knowledge, new product features, and unrelated refactors discovered by tests.

## Locked decisions

- Completion requires evidence for all North Star invariants, not a happy-path demo.
- Historical initialized M1 is not implementation evidence.
- Compiler failures never alter/delay/misreport primary completion/delivery.
- Evidence/claim kinds, append-only corrections, applicability, contradictions,
  and observation lineage remain intact end to end.
- Exact direct provider route is evidenced; no silent substitution.

## Open questions

- Which backend combinations are representative and stable enough for the matrix?
- Which quality/latency/cost observations are rollout blockers versus documented limits?
- What soak duration belongs in a later operational launch rather than this sprint?
- Which residual findings warrant immediate contract fixes versus follow-up tickets?

## Constraints

- Deterministic, hermetic tests where possible; bounded approved integration
  seams and no credentials in artifacts.
- No launch/deploy/restart/push side effects in verification.
- Preserve concurrent dirty work and avoid unrelated cleanup.
- Documentation must link exact commands/files/evidence and distinguish proposed
  rollout from performed operations.

## Done criteria

- Conformance matrix passes across representative backends and both trigger classes.
- Failure matrix proves no cursor corruption, duplicate records/tickets, evidence
  loss, authorization leakage, or primary-session result/delivery impact.
- Exact direct-Pro route and bounded cost/concurrency behavior are durably evidenced.
- Every named agent/operator surface is documented and tested.
- Completion-evidence handoff maps each North Star success measure to proof and
  lists explicit remaining operational launch gates.

## Touchpoints

All M1–M10 handoffs and focused suites, end-to-end fixtures, resident/managed-
agent backends, Store file/DB, provider-routing fakes/integration seams,
operator/agent docs, and ticket capture for unrelated findings.

## Anti-scope

Do not launch, deploy, restart, broadly enable, expand features, auto-fix backlog
items, suppress known failures, or count documentation assertions as proof.

## Predecessor handoff

Require reviewed `docs/session-knowledge-compiler/handoffs/m10-rollout-readiness.md`,
all earlier handoffs, passing focused suites, and explicit rollout gates. M11
verifies their composition; it does not substitute for future launch authority.

## Plan sizing and rubric

Estimated duration: approximately two skilled-human weeks. Overall plan
difficulty: 4/5; profile `partnered-4`; robustness `full`; depth `high`;
directed prep enabled. The individual contracts are settled, but cross-layer
failure matrices and representative backend topology demand deep integration
reasoning; this is substantive hardening, not a docs-only micro-milestone.
