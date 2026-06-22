# M1: Public API Clean Break

## Outcome

Make the supported `arnold_pipelines.megaplan` public API match the clean-break contract: `build_pipeline()` returns an explicit-node `arnold.workflow.dsl.Pipeline`, and no legacy constructors or `compile_planning_pipeline()` exports remain public, importable, or normalized by tests.

## Scope

IN:

- Remove `_build_legacy_pipeline()`, `build_legacy_pipeline()`, and `compile_planning_pipeline()` from `arnold_pipelines/megaplan/pipeline.py`.
- Update `arnold_pipelines/megaplan/__init__.py` and `arnold_pipelines/megaplan/pipelines/planning/__init__.py` so they do not export `compile_planning_pipeline` or other legacy constructor names.
- Update tests that currently require legacy constructors to instead assert absence and the explicit-node `build_pipeline()` contract.
- Add or strengthen source-level public API tests before deeper import burn-down starts.
- Preserve behavior only through explicit-node DSL and compiler output, not through compatibility wrappers.

OUT:

- No broad `_pipeline/` or `stages/` deletion in this milestone unless directly required to remove the public exports.
- No `epic_blitz` deletion; that is M2.
- No generated-asset regeneration beyond files directly affected by public API docs/tests.
- No new workflow architecture or compatibility policy.

## Locked Decisions

- `WorkflowManifest` is compiler output, not hand-authored source.
- `arnold_pipelines.megaplan.pipeline.build_pipeline()` is the canonical authoring surface.
- The old typed-port `Stage`/`Edge` constructor path is not a public compatibility surface.
- No permanent alias module, lazy `__getattr__`, `__all__` entry, type stub, or docs example may preserve the removed names.

## Open Questions

- Whether any currently internal module still needs a non-public helper with similar behavior before M3 replaces its imports.
- Whether public docs should mention the removal here or defer full migration documentation to M5.

## Constraints

- Do not make tests pass by weakening the explicit-node contract.
- Do not delete baseline/parity evidence.
- Do not introduce a temporary public shim for downstream callers.
- Keep the change reviewable as a public-surface cut before the deeper topology sprint.

## Done Criteria

1. `arnold_pipelines.megaplan.pipeline` does not define `_build_legacy_pipeline`, `build_legacy_pipeline`, or `compile_planning_pipeline`.
2. `arnold_pipelines.megaplan` and `arnold_pipelines.megaplan.pipelines.planning` do not export removed constructors.
3. Focused tests assert `build_pipeline()` returns `arnold.workflow.dsl.Pipeline` and compiles through the manifest compiler.
4. Focused absence tests fail on reintroduction of legacy constructor names.
5. `git grep -n -E "build_legacy_pipeline|compile_planning_pipeline|_build_legacy_pipeline" -- arnold_pipelines tests` has only deliberate negative-gate references.
6. `scripts/m6_purge_gate.py` either passes the legacy-constructor/export portions or reports only later-sprint physical directory blockers.

## Touchpoints

- `arnold_pipelines/megaplan/pipeline.py`
- `arnold_pipelines/megaplan/__init__.py`
- `arnold_pipelines/megaplan/pipelines/planning/__init__.py`
- `tests/arnold_pipelines/megaplan/test_pipeline.py`
- `tests/arnold_pipelines/megaplan/test_package.py`
- `scripts/m6_purge_gate.py`
- public API docs that name `build_pipeline()` or `compile_planning_pipeline`

## Anti-Scope

- Do not migrate every internal `_pipeline` import here.
- Do not archive or rewrite shipped pipelines here.
- Do not add deprecation warnings for removed clean-break surfaces.
- Do not run `execute` without explicit human approval.

## Rubric

Overall plan difficulty: 5/5; profile `partnered-5`; robustness `thorough`; depth `high`.

Rationale: this is a public contract cutover where bad local tests could normalize the exact legacy surface the epic is meant to remove.
