# M2: Archive/Delete `epic_blitz`

## Outcome

Remove `epic_blitz` / `epic-blitz` from active shipped pipeline discovery, CLI behavior, package contents, and source tests, while preserving only historical archive evidence.

## Scope

IN:

- Delete `arnold_pipelines/megaplan/pipelines/epic_blitz.py`.
- Delete `arnold_pipelines/megaplan/pipelines/epic-blitz/` if present.
- Remove `epic_blitz` from active discovery in `arnold_pipelines/discovery.py`.
- Update CLI/list/describe/run tests so `epic-blitz` is unknown or absent, not archived-but-active.
- Update pipeline inventory checks and package disposition source data so deleted paths are expected absent.
- Keep historical archive documentation under archive-only locations.

OUT:

- No migration of `epic_blitz` onto the explicit-node runtime.
- No new replacement pipeline.
- No broad `_pipeline/` import burn-down except dependencies required to delete `epic_blitz`.
- No unrelated discovery redesign.

## Locked Decisions

- The M5/M6 inventories classify `epic_blitz` as archive/delete.
- Archive status does not mean active discovery, package inclusion, or CLI availability.
- Historical evidence may remain in docs/archive, but active source and package artifacts must not.

## Open Questions

- Exact archive documentation path to cite in migration notes.
- Whether `discover_shipped_pipelines(include_archived=True)` should exclude deleted source entirely or return only non-importing historical metadata.

## Constraints

- Deleted source paths must not be reachable through importlib, CLI dispatch, entrypoints, package data, or generated registry rows.
- Tests should exercise unknown-pipeline behavior for `epic-blitz`.
- Do not change the clean-break public API decision from M1.

## Done Criteria

1. `arnold_pipelines/megaplan/pipelines/epic_blitz.py` and `arnold_pipelines/megaplan/pipelines/epic-blitz/` are absent.
2. Active discovery and CLI list/describe/run output do not expose `epic-blitz`.
3. CLI tests assert `epic-blitz` absence or unknown-pipeline failure.
4. Inventory/package-disposition checks treat deleted `epic_blitz` paths as absent, not live archive roots.
5. `git grep -n -E "epic[-_]blitz" -- arnold_pipelines tests scripts` has no active source/test hits except deliberate negative assertions or archive docs.
6. Wheel/sdist contents checks include `epic_blitz` absence if available at this milestone.

## Touchpoints

- `arnold_pipelines/megaplan/pipelines/epic_blitz.py`
- `arnold_pipelines/megaplan/pipelines/epic-blitz/`
- `arnold_pipelines/discovery.py`
- `scripts/check_workflow_pipeline_inventory.py`
- `docs/arnold/m5-pipeline-disposition.md`
- `docs/arnold/m6-deletion-list.md`
- `docs/arnold/package-disposition.yaml`
- `docs/arnold/package-disposition.md`
- `tests/arnold_pipelines/test_discovery.py`
- `tests/test_pipeline_run_cli.py`

## Anti-Scope

- Do not resurrect `epic_blitz` as a migrated sample.
- Do not remove unrelated archived evidence.
- Do not perform general CLI cleanup.
- Do not run `execute` without explicit human approval.

## Rubric

Overall plan difficulty: 5/5; profile `partnered-5`; robustness `thorough`; depth `high`.

Rationale: the code delta is smaller than M3, but stale discovery, CLI, package data, or generated registry references can silently keep the deleted pipeline alive.
