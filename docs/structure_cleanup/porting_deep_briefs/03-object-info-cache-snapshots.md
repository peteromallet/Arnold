# Porting Deep Audit 03 — Object Info And Snapshot Boundaries

Work from repo root `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: decide whether `vibecomfy/porting/object_info`, `vibecomfy/porting/cache`, and related snapshot paths are logically placed, stale, or deletable.

Focus:
- `vibecomfy/porting/object_info/`
- `vibecomfy/porting/cache/`
- `scripts/demo_wrapper_codegen.py`
- `tests/test_wrapper_*`
- `vibecomfy/schema`, `vibecomfy/commands/schemas.py`, `vibecomfy/commands/nodes.py`

Questions:
1. Are committed object-info snapshots active fixtures/contracts or stale generated state?
2. Are cache paths generated and ignored correctly?
3. Does object-info belong under `porting/`, `schema/`, `tests/fixtures/`, or another abstraction?
4. Which files can be deleted now?

Return exact path actions with evidence.

Do not edit files.
