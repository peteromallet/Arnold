## Verdict

### 1. Fixture corpus: **None exists.**
No `tests/fixtures/` directory. Zero test `state.json` files anywhere in the repo. The only source is real user plan directories (`.megaplan/plans/<name>/state.json`). `chain_state.json` fixtures are equally absent.

### 2. Forward path: **migrate-before-validate works today.**
`load_plan_from_dir` (state.py:93-101) value-sniffs → calls `write_plan_state(mode="legacy-migration")` → `_apply_legacy_state_migration` (state.py:293-308) mutates state → validation at state.py:433-434 fires *after*. No caller validates first — all paths go through `load_plan_from_dir` or `write_plan_state`. Adding absent `schema_version` → stamp → validate fits this pattern cleanly (new elif in `_apply_legacy_state_migration`).

### 3. ROLLBACK: **NOT safe. Severity: HIGH.**
If m1 stamps `schema_version: 1` and then m1 is reverted:

| Reader | Breaks on revert? | Why |
|--------|-------------------|-----|
| `Plan.from_plan_state()` (sprint1.py:248) → `Plan(**fields)` | **YES** | `StorageModel.model_config = ConfigDict(extra="forbid")` (base.py:37). Unknown key → `ValidationError`. |
| `PlanRepository.load_plan()` (plan_repository.py:352) | **YES** | Calls `Plan.from_plan_state(state)`. |
| `FilePlanMixin.create_plan()` (_file/plans.py:27) | **YES** | `Plan(**fields)` with `extra="forbid"`. |
| `DBPlanMixin.load_plan()` → `Plan(**row)` | **YES** | Same; DB columns (`_PLAN_COLUMNS`, common.py:29-35) lack `schema_version` anyway. |
| `Plan.to_plan_state()` (sprint1.py:300-322) | **Silently drops it** | Only emits known fields; version stripped on save. |
| Raw dict readers (`status_view`, `feedback`, `introspect`) | No | Extra key in dict is harmless. |
| `ChainState.from_dict()` (chain/__init__.py:472) | No | Tolerant — only reads known fields. |

**There is zero backward-tolerance designed.** No code path strips unknown keys before Pydantic ingestion. The fix must happen in m1 itself.

### 4. DB mirror: **Needs coordinated column add; reversible only with app-level tolerance.**
`_PLAN_COLUMNS` (common.py:29-35) has no `schema_version`. Adding it requires an ALTER TABLE. On revert, the old code's `SELECT` would return the column → `Plan(**row)` fails (`extra="forbid"`). The DB migration is reversible at the SQL level (DROP COLUMN), but the app-level `extra="forbid"` means old code can't read rows with the column present.

### CONCRETE PLAN CHANGE (m1)

1. **Change `StorageModel.model_config`** (base.py:37) from `extra="forbid"` to `extra="ignore"` — or add `model_config = ConfigDict(extra="ignore")` specifically on `Plan`. This is the one-line backward-tolerance fix that makes revert safe.

2. **Add `schema_version` to `Plan` fields** (sprint1.py:215) as `schema_version: int = 0` with a validator that treats missing as 0.

3. **Add `"schema_version"` to `_PLAN_COLUMNS`** (common.py:29) and `_PLAN_JSONB` → actually it's a small int, not JSONB. Add as regular column.

4. **Build fixture corpus**: capture 2-3 real `state.json` files (old no-version, current, future versioned) into `tests/fixtures/state_json_v0/`, `v1/`, etc.

5. **In `_apply_legacy_state_migration`** (state.py:293): add branch `if "schema_version" not in state: state["schema_version"] = 1; migrated = True`.

**Verdict**: Migration **testable** (structurally compatible), rollback **NOT safe without `extra="ignore"`**. Severity: **HIGH**. Fix is one line in base.py plus Plan field addition — must ship in m1 alongside the version stamp itself.