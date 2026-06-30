# M0: Boundary Lock And Substrate Inventory

## Outcome

Make the existing Arnold substrate explicit and protected before more code moves. Generic Arnold modules must stop depending on Megaplan implementation details by accident.

## Source Context

Use these existing source notes as authoritative context:

- `.megaplan/initiatives/aggressive-migration-deepseek-synthesis-20260607.md`
- `.megaplan/briefs/briefs/generalized-pipeline-project-scope-20260607.md`
- `.megaplan/initiatives/generalized-pipeline-seam-swarm-20260607.md`
- `.megaplan/briefs/briefs/pipeline-generalization-seams-20260607.md`

## Scope

In scope:

- Add hard boundary tests for generic packages: `arnold.pipeline`, `arnold.runtime`, and any new `arnold.control` / `arnold.supervisor` packages if they exist in this milestone.
- Generic modules must not import from `arnold.pipelines.megaplan`.
- Generic modules must not contain `.megaplan` path sentinels, `MEGAPLAN_` environment variables, `GateRecommendation`, `STATE_*`, or planning-specific default binding strings unless explicitly quarantined in a compatibility adapter outside the generic package.
- Remove or parameterize known leaks in `arnold/pipeline/schema_registry.py`, `arnold/pipeline/step_io_policy.py`, and `arnold/pipeline/artifacts.py`.
- Produce a committed inventory document naming the blessed Arnold substrate primitives and the quarantine locations for temporary compatibility bridges.
- Prove `arnold/pipelines/evidence_pack` remains a non-Megaplan pipeline with zero imports from `arnold.pipelines.megaplan`.

Out of scope:

- Moving `RunOutcome`.
- Creating StepContract.
- Executor convergence.
- Deleting Megaplan compatibility shims unless the boundary gate proves deletion is safe.

## Locked Decisions

- Generic Arnold owns graph, step, port, contract, routing, generic artifact, and generic runtime mechanics.
- Megaplan owns planning semantics, chain policy, Git/PR lifecycle, profile/robustness policy, gate recommendations, and `.megaplan` repository layout.
- Compatibility is allowed only through clearly named adapter/shim modules with tests proving they do not leak into the generic substrate.

## Done Criteria

- Boundary tests fail on any new generic import from `arnold.pipelines.megaplan`.
- Boundary tests fail on new `.megaplan`, `MEGAPLAN_`, `GateRecommendation`, or `STATE_*` leakage in generic packages, except explicitly quarantined compatibility adapters.
- Existing CI-targeted tests continue passing.
- `evidence_pack` still runs and has zero Megaplan imports.
- A substrate inventory doc is committed under `.megaplan/initiatives/aggressive-generalized-pipeline-migration/briefs/`.
