# Unified Managed-Agent Profiles and Sequential Fallbacks

Extend the existing sequential-model-fallbacks initiative into one managed-agent contract for Megaplan workers, resident-launched agents, and their managed descendants. The initiative unifies D1-D10/D5 resolution, ordered fail-closed fallback, immutable brief and request custody, bounded nested launch, inherited ceilings, structured results, migration, and restart-safe evidence while preserving scalar and v1 behavior.

## Two-sprint execution shape

Exactly two sprint-sized executable milestones target roughly four human-weeks total, with each sprint scoped to about ten skilled-engineer days:

1. **Shared foundations and managed launch (Sprint 1, days 1-10):** establish the canonical resolver/profile contract, shared fallback and mutation-safety kernel, immutable content-addressed root/task custody and additive managed-run/result schemas, plus the typed durable child-launch/result foundation.
2. **Enforcement, integration, and rollout readiness (Sprint 2, days 11-20):** complete ancestry and non-expanding authority, transactional tree/root budgets, dispatcher convergence, current/vNext migration, restart/resume evidence, adversarial conformance, observability, documentation, and staged rollout/rollback readiness.

This is not the former seven milestones hidden behind two labels. Sprint 1 explicitly runs resolver, fallback, custody/schema, and launcher-state-machine work as parallel tracks, with one early schema/receipt convergence gate before launcher integration. Sprint 2 starts authority/budget enforcement, dispatcher migration/resume, and conformance/rollout tracks together; fixtures and shadow comparisons are built while adapters land, followed by one deterministic convergence gate. `chain.yaml` contains only the necessary cross-sprint dependency.

The two-sprint split remains appropriate because Sprint 2 consumes a concrete, versioned Sprint 1 contract-handoff manifest rather than rediscovering resolver, fallback, custody, or launcher interfaces. The breadth is too large for the earlier five-to-six-day slices, but the work does not warrant restoring seven serial milestones: each sprint contains independent tracks that converge on one reviewable gate.

Both sprints are difficulty 5/5 and use `partnered-5`, vendor `codex`, `full` robustness, and high depth. High depth is justified because Sprint 1 freezes multiple public safety contracts across divergent dispatchers, while Sprint 2 must reason about concurrency, restart, migration, and false-green cross-dispatcher evidence. The chain remains suitable for later unattended auto-merge but stops on failure or escalation. These assets do not launch it.

## Coordination boundary

This initiative owns transport-neutral profile/fallback/brief/nested-agent contracts. `discord-resident-delegation-delivery-corrective` remains authoritative for Discord ingress, lifecycle/outbox, reply delivery, transport idempotency, and attachments. The seam is an immutable provenance envelope in and one root completion intent/result out; children never deliver directly.

## Locked shaping decisions

- D5 is both the missing-difficulty default and the explicit middle case; it resolves deterministically and retains reason evidence.
- Default structural ceilings are depth 2 below root, four children per parent, and eight descendants per root; all are configurable downward and require explicit operator policy to raise.
- Fallback requires affirmative no-mutation evidence and uses one classifier across dispatchers.
- Complete root/task bytes are content addressed; summaries and mutable paths are not custody.
- Existing `arnold-managed-agent-run-v2` and `arnold-resident-agent-run-v1` records are migration inputs, not names available for incompatible reuse; extend compatibly or introduce the next additive revision after characterization.
- Resident implementation work must reconcile the project checkout with the pinned resident runtime before edits so bounded context routing, task/prompt limits, immutable provenance, and delivery behavior are not silently dropped.
- Deployment-specific dollar/token/time ceilings and the final provider/model catalog are operator-owned configuration, but every resolved value and policy revision must be recorded.

See `NORTHSTAR.md`, `decisions/managed-agent-contract-boundaries.md`, `research/prep-source-and-sizing-audit-20260713.md`, and the two sprint briefs for authoritative requirements and handoffs.

## Current provider-routing truth (2026-07-17)

The resident-managed launch seam now resolves a model/agent spec before it
creates a manifest: Hermes specs dispatch through Hermes, Codex specs through
Codex, and Claude specs through Claude. The default backend is `auto`;
compatible explicit overrides remain available and conflicting backend/model
pairs fail before launch. Provider selection is recorded in the existing
`arnold-managed-agent-run-v2` manifest without changing Discord provenance,
aggregation ownership, or completion delivery.

Raw execution evidence is source record `msg_f65cd1476f49`, synthesis-owner run
`subagent-20260717-172149-30a07f47`, and bounded live launches
`subagent-20260717-175239-7ef4a1d7` (Hermes GLM 5.2, completed) and
`subagent-20260717-175239-8c8d9599` (Codex, completed). Claude dispatch reached
its durable provider worker in `subagent-20260717-175512-cb98141a` but the
installed Claude CLI had no authenticated session, so Claude remains code- and
dispatch-verified rather than live-provider-verified in this environment.
