---
type: brief
slug: m10-rollout-observability
title: Rollout Controls, Budgets, Diagnostics, and Rollback
epic: session-knowledge-compiler
created_at: '2026-07-16T00:00:00+00:00'
---

# M10 — Rollout Controls, Budgets, Diagnostics, and Rollback

## Outcome

Make the complete compiler safely operable behind explicit configuration with
shadow/canary controls, bounded direct-Pro cost/concurrency/retries, privacy and
authorization inheritance, actionable diagnostics, and rollback that preserves
accepted checkpoints and never affects primary-session delivery.

## In scope

- Define disabled/shadow/canary/enabled configuration with safe threshold,
  exact direct-Pro route, cohort, concurrency, input/output/cost, retry, timeout,
  and disable controls.
- Keep idle compilation disabled unless measured evidence justifies explicit opt-in.
- Instrument eligible/checkpointed/failed/retried ranges, lag, source/model cost,
  schema/claim quality, corrections, promotions, contradictions, observation-to-
  backlog lineage, and primary-session latency/result isolation.
- Provide status/diagnostic and bounded safe-retry operations that distinguish
  scheduler, model, schema, persistence, authorization, and adapter failures.
- Inherit retention/redaction/access controls and prevent metrics/logs from
  exposing source content or credentials.
- Define shadow/canary promotion gates and evidence required before widening.
- Support immediate disable and rollback without rewriting accepted checkpoints.
- Produce `docs/session-knowledge-compiler/handoffs/m10-rollout-readiness.md`.

## Out of scope

Broad production enablement, deployment/restart, product implementation beyond
operability seams, final cross-backend conformance, and optional idle default.

## Locked decisions

- Default route remains `hermes:deepseek:deepseek-v4-pro` via `direct` only.
- Compiler/backlog failure or budget exhaustion never changes primary result/
  delivery and never advances an unaccepted range.
- Rollback preserves evidence and accepted checkpoints.
- Idle remains disabled absent explicit measured justification.
- Rollout widening is evidence-gated and reversible.

## Open questions

- What shadow/canary cohort and quality/overhead thresholds justify widening?
- Which existing observability/event surfaces should carry compiler metrics?
- What safe-retry authority is appropriate for operators versus automated repair?
- How should external deletion/retention requests propagate to derived records?

## Constraints

- No transcript/secret leakage in metrics, logs, or errors.
- Bounded concurrency/cost/retry and no silent model/provider substitution.
- Configuration compatibility and explicit defaults across file/cloud/resident.
- Rollback/disable operations are idempotent and separately authorized.

## Done criteria

- Configuration tests cover every rollout state, cohort, budget, and disabled idle.
- Forced model/schema/store/authorization/ticket failures remain diagnosable,
  retryable where valid, and harmless to primary session/cursor.
- Metrics report lag/failure/cost/quality/lineage without source content.
- Disable/rollback/re-enable tests preserve accepted checkpoints and avoid duplicates.
- M10 handoff defines exact readiness gates and test matrix M11 must verify.

## Touchpoints

M1–M9 APIs, resident/managed-agent configuration, scheduler/worker budgets,
observability/events/cost, privacy/redaction, operator diagnostics/retry, and
rollout/failure-isolation tests.

## Anti-scope

Do not deploy, restart, broadly enable, change the 100k threshold to a high-
frequency default, enable idle by default, or rewrite accepted history.

## Predecessor handoff

Require reviewed `docs/session-knowledge-compiler/handoffs/m9-backlog-lineage.md`,
landed end-to-end lineage and idempotent adapter tests, plus all earlier handoff
contracts. M10 operates the product; it does not redefine its truth model.

## Plan sizing and rubric

Estimated duration: approximately two skilled-human weeks. Overall plan
difficulty: 4/5; profile `partnered-4`; robustness `full`; depth `high`;
directed prep enabled. Contracts are fixed, but configuration, observability,
privacy, retry, and rollback span multiple runtime boundaries.
