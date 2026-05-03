# Sprint 1 — Foundation: Schema + Store + FileStore + PlanRepository

**Authoritative source:** `docs/arnold-merge-design.md` (section "Sprint 1 — Foundation", lines ~696-716, plus Schema/Store interface/FileStore atomicity sections earlier in the doc). Read the full design doc before starting.

**Predecessor:** Sprint 0 spike report at `docs/sprint-0-spike-report.md` — fold its findings into your implementation.

## Scope

- All Pydantic models per the **Schema** section: 16 mirrored Arnold tables + new tables (`migration_runs`, `execution_leases`, `plan_artifacts`, `control_messages`, `progress_events`, `automation_actors`).
- Full `Store` Protocol per the refined definition in the design doc (~30 methods covering CRUD per entity, joined `load_hot_context`, plan artifact API, control plane API, execution leases, locks).
- `FileStore` with proper transaction journal (prepare/commit/recover), length-prefixed JSONL with `_tx_begin`/`_tx_commit` framing, blob staging.
- `BlobStore` Protocol + `LocalDirBlobStore`.
- `Plan` + `PlanArtifact` Pydantic models per the design doc.
- `PlanRepository` adapter — file mode reads/writes existing plan tree under `~/.megaplan/<repo-id>/.../plans/<plan-id>/`.
- Refactor megaplan internals (~335 touch points across ~45 files) to go through `PlanRepository` for plan-tree access and `Store` for everything else. **Heaviest in `workers.py`, `_core/state.py`, `cli.py`. Existing `_core/io.py` already factors atomic writes — extend, don't replace.**
- Existing megaplan plans become orphan plans (`epic_id=None`); `list_plans(include_orphans=True)` returns them.
- `DBStore` skeleton (Protocol satisfied with `NotImplementedError` raises) — actual impl is Sprint 2.
- Test fuzz harness in `megaplan/tests/store_contract.py` exercising any `Store`; passes against `FileStore`.

## Acceptance

- `pytest --backend file` green.
- `megaplan auto --plan <name>` runs against new code with no behavior change (orphan plan).
- Crash mid-transaction (kill -9 between prepare and commit) recovers cleanly on next open.
- Spike report's findings folded in.

## Out of scope

- DBStore implementation (Sprint 2).
- Editorial logic (Sprint 4-5).
- Promote/demote, MultiStore (Sprint 3).
- Discord control plane (Sprint 6).

## Robustness

`standard` — large refactor with concurrency-correctness requirements; needs critique.
