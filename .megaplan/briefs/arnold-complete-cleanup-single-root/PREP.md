# Arnold Complete Cleanup / Megaplan Single-Root Prep

Date: 2026-06-25

## Prep Decision

This should run as an epic, not a single megaplan. The current cleanup is bigger than one two-week sprint because it combines:

- final loose-work disposition after the native Python completion merge;
- a public/import contract migration;
- a package-root consolidation from `arnold.pipelines.megaplan` to `arnold_pipelines.megaplan`;
- CLI, chain, resume, worker, discovery, docs, and wheel conformance;
- final deletion gates where a false green can leave a second implementation alive.

Overall plan difficulty: 5/5; selected profile: `partnered-5`; because the plan changes public/import contracts and package topology, and a bad plan can pass local tests while breaking installed users, persisted Megaplan state, or worker subprocess imports.

Planning complexity: `thorough`; because this is a public API/package-root migration with deletion gates, not a local refactor.

Depth: `high`; because the planner must reason across import surfaces, side effects, chain/resume state, wheel packaging, and historical cleanup disposition.

Recommended shorthand for every milestone unless a later prep explicitly lowers it: `partnered-5/thorough/high`.

## Subagent Swarm Input

DeepSeek V4 Pro fan-out was run with ten component briefs:

- import/caller inventory;
- `_pipeline` surface;
- import side effects;
- CLI/resume/chain/PR compatibility;
- packaging/wheel/discovery;
- shim/deletion policy;
- skills/docs/generated assets;
- runtime/process isolation;
- tests/rollout gates;
- external loose-work disposition.

The raw outputs lived at `/tmp/arnold_single_root_swarm/outputs` during prep. The committed durable synthesis is `SWARM-SYNTHESIS.md`.

## Key Judgment Calls

1. `arnold_pipelines.megaplan` is the final implementation authority.
2. `arnold.pipelines.megaplan` is not a final public compatibility surface.
3. No permanent shims. Temporary shims are only permitted inside the migration, must forward to existing canonical targets, and must be tracked by a shrink-only registry with removal phases.
4. Do not create `arnold_pipelines.megaplan._pipeline` as the final replacement. `_pipeline` is a legacy implementation namespace. Extract its responsibilities into named canonical modules such as runtime, registry, CLI, chain, dispatch, and patterns.
5. The migration must first invert authority for real. Current repo state still has canonical surfaces delegating to legacy behavior in important places.
6. Deletion is last. The final state must prove no business logic remains under `arnold/pipelines/megaplan`; ideally the package is absent.
7. The old TypeScript snapshot is valuable but separate: archive it to an explicit remote branch, verify, then delete the local snapshot. Do not fold its code into Python Arnold.

## Invocation

```bash
python -m arnold_pipelines.megaplan chain start \
  --spec .megaplan/briefs/arnold-complete-cleanup-single-root/chain.yaml
```

Do not start this chain until local `main` has been pushed or a deliberate base branch has been chosen, because local `main` is ahead of `origin/main` after the native completion merge.
