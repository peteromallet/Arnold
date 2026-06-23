# Pristine Extension Foundation Megaplan Prep

Source plan: `docs/extensions/extension-layer-foundation-assessment.md`

## Sizing Decision

This work is larger than one megaplan. It is a coherent prerequisite epic whose output gates the full Phase 4 extension-family chain, but it contains multiple dependency-ordered implementation surfaces: proposal contract and persistence, agent proposal UI, settings runtime ownership, manager SchemaForm repair UX, lifecycle recovery, diagnostics provenance, inventory semantics, and readiness docs. It should run as a `megaplan chain` with sprint-sized milestones.

The user requested aggressive two-week sprints. The chain therefore groups the nine implementation units from the assessment into five milestones. Each milestone is sized as an aggressive two-week sprint for a strong engineer/agent pair; if a milestone expands during planning, split it rather than silently widening scope.

## Dial Selection

Overall plan difficulty: 5/5; selected profile: partnered-5; because the plan changes public in-repo SDK contracts, provider persistence ownership, stale/reload behavior, settings migration semantics, and readiness gates where a bad plan could pass local tests while leaving downstream Phase 4 work on the wrong contract.

Planning complexity: full. The run already has substantial prep/audit context, but each milestone still needs plan, critique, gate, revise, execute, and review. Use `thorough` only if a milestone discovers migration/security/data-loss risk beyond the known localStorage/provider migration issue.

Depth: high. The planner needs substantial repo-reading and structural reasoning across SDK, runtime provider, edge functions, settings services, manager UI, diagnostics, and tests.

Vendor: codex, matching the requested partnered-5/Codex-heavy setup and the preceding Codex extra-high sense-check.

## Milestones

1. `m1-contracts-proposal-spine`: freeze foundation contracts and proposal runtime/persistence spine.
2. `m2-agent-proposal-vertical`: wire the edge -> client -> runtime -> activity region -> accept/reject proposal path.
3. `m3-repository-first-settings-runtime`: make provider-backed settings canonical for extension runtime.
4. `m4-manager-schemaform-settings`: replace manager settings with shared SchemaForm editor and legacy repair UX.
5. `m5-lifecycle-diagnostics-readiness`: finish recovery, diagnostics, inventory semantics, foundation docs, and objective readiness gate.

## Recommended Start Command

```bash
python -m arnold.pipelines.megaplan chain start \
  --spec .megaplan/briefs/reigh-pristine-extension-foundation/chain.yaml \
  --project-dir /Users/peteromalley/Documents/reigh-workspace/reigh-app
```

For manual review between milestones:

```bash
python -m arnold.pipelines.megaplan chain start \
  --spec .megaplan/briefs/reigh-pristine-extension-foundation/chain.yaml \
  --project-dir /Users/peteromalley/Documents/reigh-workspace/reigh-app \
  --one
```

