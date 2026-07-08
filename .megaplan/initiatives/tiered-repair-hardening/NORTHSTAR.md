---
superseded_by: custody-control-plane
---

# Tiered Repair Hardening North Star

Make cloud megaplan repair trustworthy enough to run without constant human babysitting.

The end state is not "more agents wake up." The end state is that every repair layer can identify the current target, prove what it did, avoid stale parent/session confusion, preserve human decisions, redact secret-bearing evidence, and escalate only when a real human decision remains.

The governing source documents are:

- `docs/ops/tiered-repair-implementation-plan.md`
- `docs/ops/tiered-repair-data-contract.md`
- `docs/ops/tiered-repair-and-audit-loop.md`

Non-negotiables:

- Current target resolution is explicit and recorded.
- State mutation is serialized through one shared repair lock.
- Process liveness alone is never terminal success.
- Human escalation is a durable answer/resume workflow, not a deletable notification.
- Prompt, Discord, Markdown, and summarized JSON views are redacted.
- Failure-triggered repair, meta-repair, and audit autonomy remain gated until earlier safety and conformance checks pass.
