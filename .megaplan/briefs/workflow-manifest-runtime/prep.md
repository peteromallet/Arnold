# Megaplan Prep: Workflow Manifest Runtime

Date: 2026-06-21

## Sprint Count

This is a six-sprint epic:

1. M1: Baseline guardrails and manifest/kernel contract.
2. M2: Explicit-node DSL and compiler.
3. M3: Manifest runner and runtime.
4. M4: Megaplan product migration.
5. M5: Shipped pipelines, CLI, docs, scaffolds, and inventories.
6. M6: Clean-break purge and conformance.

The post-merge conformance pass is a required chain-level release gate, not a separate implementation sprint. M5 may run internal M5a/M5b workstreams, but it remains one chain milestone unless deliberately split later.

## Prep Skill Sizing

This follows the local `megaplan-prep` rubric:

- Size: larger than one sprint, so use an epic chain.
- Sprint size: each milestone has a self-contained outcome and handoff artifact, roughly sprint-sized.
- Overall plan difficulty:
  - M1: 5/5, `partnered-5`, because it freezes cross-cutting contracts and guardrails that every later sprint depends on.
  - M2: 5/5, `partnered-5`, because authoring API mistakes become public contract mistakes.
  - M3: 5/5, `partnered-5`, because runtime/replay bugs can pass local tests while corrupting durable state.
  - M4: 5/5, `partnered-5`, because it is the product semantic cutover.
  - M5: 5/5, `partnered-5`, because it is the broad user/operator migration where stale generated surfaces, docs, CLI paths, and shipped pipelines can make the clean break fail while appearing green.
  - M6: 5/5, `partnered-5`, because deletion can appear green while old surfaces still ship or execute.
- Planning complexity: `thorough` for every milestone because this is a public-contract migration with import topology, packaging, state, generated artifact, and deletion risks.
- Depth: `high` for every milestone because each sprint needs substantial repo-reading and structural reasoning.
- Prep direction: each milestone has explicit `prep_direction` in `chain.yaml`.
- Prep clarify: disabled for unattended chain execution (`prep_clarify: false`).

## Run Shape

Executable chain spec:

- `.megaplan/briefs/workflow-manifest-runtime/chain.yaml`

Companion review and setup context:

- `.megaplan/briefs/workflow-manifest-runtime/review-synthesis.md`
- `.megaplan/briefs/workflow-manifest-runtime/chain-notes.md`
- `docs/arnold/workflow-manifest-runtime-review/load-bearing-questions.md`

Recommended command when ready to start:

```bash
PYENV_VERSION=3.11.11 python -m arnold.pipelines.megaplan chain start \
  --spec .megaplan/briefs/workflow-manifest-runtime/chain.yaml \
  --project-dir "$PWD" \
  --one
```

Use `--one` for the first run so M1 can complete and be reviewed before allowing the rest of the chain to advance.

Before starting, verify the refreshed base:

```bash
git fetch origin
git log --oneline -1 origin/main
```

The result should be `0035c231` or newer. If re-running after a partial or failed chain attempt, add `--fresh` to remove stale registered worktree/branch state before the chain creates a new one.
