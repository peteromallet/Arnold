# M6 — Adversarial Evidence, Rollout, and Observability

## Outcome

Close the audit with end-to-end adversarial proof, operational observability, staged rollout and rollback documentation, and a canary-ready delivery lifecycle whose status can be trusted without inspecting fragmented files.

## Scope

In scope: deterministic end-to-end/fault-injection suite; concurrent duplicate and burst stress tests; restart matrix across each custody boundary; observability fields/metrics/dashboards/alerts; runbooks; compatibility evidence; staged flag plan; canary and rollback gates; documentation and conformance checks. Fix defects revealed within this lifecycle scope. Keep the sprint within roughly two human-weeks.

Out of scope: unrelated resident features, new Discord UX, deleting legacy storage, broad performance tuning, or executing irreversible production cleanup.

## Locked decisions

- Tests assert persisted ledger/outbox/execution evidence and visible transport effects, not sleeps or PID guesses.
- Rollout proceeds additive/shadow → controlled canary → wider enablement only when quantitative gates pass; rollback retains new records and restores prior serving authority safely.
- Operational views derive from the unified ledger and clearly label legacy/unknown/dead-letter states.

## Open questions for the plan

- What canary population and soak windows match the existing resident traffic/risk envelope?
- Which thresholds should page versus warn for oldest pending age, recovery lag, duplicate prevention, unknown provider outcome, retry exhaustion, and provenance invariant violation?
- Which tests can reuse existing Discord fakes and which need a new deterministic fault harness?

## Constraints

Never emit secrets or message content into metrics/log labels. Avoid flaky wall-clock tests. Preserve service availability and backward compatibility. Any unresolved unknown provider semantics must become an explicit operational caveat/gate.

## Done criteria and acceptance evidence

- A named adversarial suite covers multi-message bursts, reordered scheduling, duplicate transport delivery, duplicate launch calls, concurrent claimers, stale fences, restart/kill at every transaction/send boundary, provider timeout/callback duplication, and legacy recovery.
- End-to-end tests prove exact-origin acknowledgement and terminal reply, one logical execution, fenced effects, replay after restart, monotone ledger history, and visible dead-letter/unknown handling.
- Metrics/logs/status expose lifecycle/request id (non-secret), state, age, attempt count, lease/fence version, duplicate prevented, recovery action, provider outcome class, and causal provenance without mutable-cursor dependence.
- Alerts and runbooks cover stuck custody, retry exhaustion, unknown sends, migration divergence, recovery lag, and invariant violations.
- Rollout document defines prerequisites, feature flags, canary/soak gates, rollback, data retention, and post-cutover verification; a dry-run/canary evidence artifact records commands and results where the environment permits.
- Focused and relevant broader test suites pass, and the review explicitly maps evidence to every North Star invariant and supplied audit finding.

## Touchpoints

Expected areas: resident integration/fault tests, Discord fakes, observability/status/hot-context code, service docs/runbooks, and the implementation surfaces from M1–M5.

## Anti-scope

Do not claim exactly-once provider behavior beyond evidence, hide unknown outcomes, perform destructive migration cleanup, or alter unrelated active cloud chains/workspaces.
