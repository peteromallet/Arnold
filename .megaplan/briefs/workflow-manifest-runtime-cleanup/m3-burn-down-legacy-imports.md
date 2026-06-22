# M3: Burn Down `_pipeline` / `stages` Load-Bearing Imports

## Outcome

Replace every production import of `arnold_pipelines.megaplan._pipeline` and `arnold_pipelines.megaplan.stages` with surviving Arnold workflow/runtime APIs or Megaplan-local non-legacy modules, leaving the legacy directories non-load-bearing and ready for deletion.

## Scope

IN:

- Inventory all direct, indirect, string-based, lazy, registry, CLI, entrypoint, type-checking, and generated-data references to `_pipeline` and `stages`.
- Migrate imports by family: flags/envelope, registry/run CLI, executor/driver contracts, schema/step IO adapters, routing/types, and stage classes.
- Create replacement modules only when they are non-legacy, named for their surviving responsibility, and not compatibility paths.
- Update tests around every migrated import family.
- Produce an import-family migration ledger documenting old path, new path, owner, and validation.

OUT:

- No physical deletion of `_pipeline/` or `stages/`; that is M4.
- No new public authoring syntax.
- No behavior-golden rewrites to hide migration regressions.
- No branch/worktree cleanup.

## Locked Decisions

- `_pipeline` and `stages` are obsolete implementation surfaces, not new product-owned namespaces.
- Explicit-node DSL handler refs replace legacy stage-class authoring where possible.
- Replacement modules must live under stable Arnold workflow/runtime surfaces or clearly named Megaplan-local internals without compatibility semantics.
- Dynamic imports count as imports.

## Open Questions

- Final homes for `_pipeline.flags`, `_pipeline.envelope`, `_pipeline.types`, `_pipeline.registry`, `_pipeline.executor`, `_pipeline.run_cli`, `_pipeline.schema_registry_adapter`, and `_pipeline.step_io_policy_adapter`.
- Which legacy types should be deleted outright versus converted into Arnold-owned contracts.
- Whether any generated data embeds module strings requiring generator changes before M4.

## Constraints

- Work in small import-family slices and run focused tests after each slice.
- Do not keep import-forwarding modules as a convenience.
- Preserve runtime behavior while changing module ownership.
- Keep M1 public API absence tests green throughout.
- Keep M2 `epic_blitz` absence green throughout.

## Done Criteria

1. `git grep -n "arnold_pipelines.megaplan._pipeline" -- arnold_pipelines` is empty except deliberate migration ledger text.
2. `git grep -n "arnold_pipelines.megaplan.stages" -- arnold_pipelines` is empty except deliberate migration ledger text.
3. Dynamic import scans over production code, registry data, CLI dispatch tables, config files, and generated data find no deleted-path references.
4. Focused runtime, CLI, routing, policy, store, handler, driver, and shipped pipeline tests pass for migrated families.
5. The import-family migration ledger exists and maps each removed legacy dependency to a surviving owner or deletion rationale.
6. M1 and M2 absence gates remain green.

## Touchpoints

- `arnold_pipelines/megaplan/_core/`
- `arnold_pipelines/megaplan/auto.py`
- `arnold_pipelines/megaplan/bakeoff/`
- `arnold_pipelines/megaplan/calibration/`
- `arnold_pipelines/megaplan/chain/`
- `arnold_pipelines/megaplan/cli/`
- `arnold_pipelines/megaplan/control*.py`
- `arnold_pipelines/megaplan/drivers/`
- `arnold_pipelines/megaplan/execute/`
- `arnold_pipelines/megaplan/handlers/`
- `arnold_pipelines/megaplan/loop/`
- `arnold_pipelines/megaplan/observability/`
- `arnold_pipelines/megaplan/pipelines/`
- `arnold_pipelines/megaplan/planning/`
- `arnold_pipelines/megaplan/profiles/`
- `arnold_pipelines/megaplan/routing*`
- `arnold_pipelines/megaplan/runtime/`
- `arnold_pipelines/megaplan/store/`
- `arnold_pipelines/megaplan/types.py`
- generated registry/config files containing module strings

## Anti-Scope

- Do not delete directories before every production import family is migrated.
- Do not create `legacy`, `compat`, `bridge`, or `forward` modules to make grep pass.
- Do not widen public API to compensate for removed internals.
- Do not run `execute` without explicit human approval.

## Rubric

Overall plan difficulty: 5/5; profile `partnered-5`; robustness `thorough`; depth `high`.

Rationale: this is cross-cutting package/import topology; a bad plan can pass local tests while leaving dynamic imports, registry strings, or runtime contracts broken.
