# Remove the legacy hermes phase worker

## Outcome
Remove the legacy megaplan hermes phase worker and route payload helpers and parallel critique through the neutral omp worker runtime.

## Scope
- Swap the four payload-helper imports in `arnold_pipelines/megaplan/workers/_impl.py` from `workers.hermes` to `workers._payload`.
- Replace `arnold_pipelines/megaplan/orchestration/parallel_critique.py` with the `origin/omp-migration` version, adapting only imports unavailable on main.
- Delete `arnold_pipelines/megaplan/workers/hermes.py`.
- Search the repository excluding `tests/` for remaining `workers.hermes` and `workers import hermes` references; preserve `arnold/agent/` and `megaplan/resident/`.

## Done criteria
- Requested `py_compile` command passes.
- `uv run --locked python -m pytest tests/workers/test_omp_adapter.py -q` passes.
- Run the orchestration targeted test if present, otherwise import both changed modules successfully.
- Preserve unrelated dirty-tree changes.

## Constraints
Do not run formatters, linters, or the full test suite. Do not modify `arnold/agent/` or `arnold_pipelines/megaplan/resident/`.
