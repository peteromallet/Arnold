# Final Sol brief: P2 control-plane reliability plan

You are GPT-5.6 Sol at high reasoning. Produce the final judgement and plan.
This is read-only: do not edit files, launch cloud commands, use collaboration
tools, or search the repository. Read only these evidence documents:

- `evidence/critique-ledger-recovery/sol-p2-framing-result-20260804.md`
- `evidence/critique-ledger-recovery/sol-final-plan-20260804.md`
- `evidence/critique-ledger-recovery/luna-vj9-review-20260804.md`
- `evidence/critique-ledger-recovery/luna-p2-explorer-synthesis-20260804.md`

## User goal

Turn the earlier recovery plan into a P2 follow-up that solves this entire
category of failures across every Megaplan/cloud pipeline, not just critique:
split runtime/source identity, stale or contradictory evidence, weak recovery
semantics, false liveness, provider-route drift, unbounded observers, duplicate
notifications, and unsafe legacy takeover. The current critique run must remain
recoverable independently; P2 must not be smuggled into its immediate resume.

## Required judgement calls

Take firm positions on:

1. Whether the ExecutionAttempt ledger/admission-controller proposal is the
   right root architecture, and what it must *not* become (avoid a second
   competing state store).
2. Which concrete bypasses are P0/P1 prerequisites versus P2 milestones versus
   later work.
3. How to make one authoritative writer while preserving existing artifacts,
   chain state, and human gates during migration.
4. The exact fail-closed boundaries for launch, resume, recovery, provider
   preflight, observer status, and artifact adoption.
5. What can run in parallel, what must be sequential, and which decisions are
   very hard/human-gated.
6. Whether the architecture generalizes beyond Megaplan and how to prove no
   entry-point bypass remains.

## Return format (under 2400 words)

- Firm root diagnosis and causal model.
- P2 north star, invariants, non-goals, and authoritative-data rule.
- Ordered milestones with dependencies and parallel workstreams.
- Immediate current-run boundary: what remains in the recovery plan and what is
  explicitly deferred to P2.
- Cross-pipeline adoption and legacy migration strategy.
- Acceptance/fault-injection matrix with concrete proof artifacts.
- Notification/observer UX contract and automatic-fixer boundary.
- High-risk judgement calls and human gates.
- A short definition of “P2 complete” and residual risks.

Do not merely repeat “add logging” or “centralize state.” Name the custody
fields, transitions, writers, reject conditions, and tests. Preserve the
distinction between deterministic validation repair (automatable) and provider,
quality, lineage, and uncertain-ownership decisions (gated).
