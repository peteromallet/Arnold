from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

import arnold_pipelines.megaplan.authority.inventory as inventory_module
from arnold_pipelines.megaplan._core.io import stable_task_id_digest
from arnold_pipelines.megaplan.authority.inventory import (
    SOURCE_REGISTRY,
    InventoryConfig,
    collect_authority_inventory,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _scope(batch: int, task_ids: list[str]) -> dict[str, object]:
    canonical = sorted(task_ids)
    return {
        "schema_version": 1,
        "batch_number": batch,
        "task_ids": canonical,
        "sense_check_ids": [],
        "task_set_digest": stable_task_id_digest(canonical),
    }


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _base_plan(tmp_path: Path) -> Path:
    plan = tmp_path / "demo-plan"
    plan.mkdir()
    _write_json(plan / "state.json", {"name": "demo-plan", "schema_version": 1, "iteration": 2})
    _write_json(
        plan / "finalize.json",
        {
            "tasks": [{"id": "T1", "status": "pending"}, {"id": "T2", "status": "pending"}],
            "sense_checks": [],
        },
    )
    return plan


def test_inventory_is_exhaustive_deterministic_and_read_only(tmp_path: Path, monkeypatch) -> None:
    plan = _base_plan(tmp_path)
    s4 = plan / "execute_batches" / "batch_1" / f"tasks_{stable_task_id_digest(['T1'])}.json"
    _write_json(s4, {"batch_scope": _scope(1, ["T1"]), "task_updates": []})
    (plan / "events.ndjson").write_text(
        json.dumps({"seq": 1, "kind": "state_written", "payload": {"state": {"name": "demo-plan", "schema_version": 1, "iteration": 2}}}) + "\n",
        encoding="utf-8",
    )

    calls: list[Path] = []
    real_listing = inventory_module.list_batch_artifacts

    def tracked_listing(path: Path) -> list[Path]:
        calls.append(path)
        return real_listing(path)

    monkeypatch.setattr(inventory_module, "list_batch_artifacts", tracked_listing)
    before = _snapshot(plan)
    first = collect_authority_inventory(plan)
    second = collect_authority_inventory(plan)

    assert first.to_json() == second.to_json()
    assert first.fingerprint == second.fingerprint
    assert _snapshot(plan) == before
    assert calls == [plan, plan]
    assert len(SOURCE_REGISTRY) == 42
    parent_keys = {(record.category, record.source_class) for record in first.records}
    assert {(spec.category, spec.source_class) for spec in SOURCE_REGISTRY} <= parent_keys
    assert all(
        record.role
        and record.reader
        and record.presence
        and isinstance(record.identity, Mapping)
        for record in first.records
    )


def test_inventory_retains_absent_and_degraded_configured_sources(tmp_path: Path) -> None:
    plan = tmp_path / "missing-plan"
    missing_spec = tmp_path / "missing-chain.yaml"
    result = collect_authority_inventory(
        InventoryConfig(plan_dir=plan, chain_spec_path=missing_spec)
    )
    by_key = {(record.category, record.source_class): record for record in result.records}

    assert by_key[("repository", "plan_tree")].presence == "absent"
    assert by_key[("execute", "s4_batch_artifacts")].presence == "absent"
    assert by_key[("chain", "spec")].presence == "absent"
    assert by_key[("cloud", "current_target")].presence == "not_configured"
    assert by_key[("store", "file_epic_events")].presence == "not_configured"
    assert by_key[("backend", "event_sourced_state_store")].presence == "absent"
    assert all(record.reason for record in result.records if record.presence in {"absent", "degraded", "not_configured"})


def test_inventory_reports_batch_event_wal_and_legacy_contradictions(tmp_path: Path) -> None:
    plan = _base_plan(tmp_path)
    for task_id in ("T1", "T2"):
        digest = stable_task_id_digest([task_id])
        _write_json(
            plan / "execute_batches" / "batch_1" / f"tasks_{digest}.json",
            {"batch_scope": _scope(1, [task_id]), "task_updates": [{"task_id": task_id, "status": "done"}]},
        )
    _write_json(plan / "execution_batch_2.json", {"task_updates": [{"task_id": "T1", "status": "done"}]})
    (plan / "events.ndjson").write_text(
        "\n".join(
            [
                json.dumps({"seq": 3, "kind": "state_written", "payload": {"state": {"name": "wrong"}}}),
                json.dumps({"seq": 1, "kind": "worker_started", "payload": {}}),
                json.dumps({"seq": 3, "kind": "worker_finished", "payload": {}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (plan / ".events.seq").write_text("9\n", encoding="utf-8")

    result = collect_authority_inventory(plan)
    codes = {item.code for item in result.contradictions}

    assert {
        "duplicate_batch_claim",
        "legacy_authority_identity_incomplete",
        "event_sequence_duplicate",
        "event_sequence_out_of_order",
        "event_sequence_gap",
        "event_sequence_sidecar_mismatch",
        "wal_state_mismatch",
    } <= codes
    assert all(item.source_paths for item in result.contradictions)
    s4_children = [record for record in result.records if record.source_class.startswith("s4_batch_artifacts:")]
    assert len(s4_children) == 2


def test_optional_current_target_is_resolved_and_normalized_once(tmp_path: Path, monkeypatch) -> None:
    plan = _base_plan(tmp_path)
    marker_dir = tmp_path / "markers"
    _write_json(marker_dir / "session-a.json", {"session": "session-a", "workspace": str(tmp_path)})
    calls = {"resolve": 0, "normalize": 0}

    def fake_resolve(session: str, **kwargs):
        calls["resolve"] += 1
        return {
            "schema_version": 1,
            "session": session,
            "target_id": "session-a:demo-plan",
            "target_session": session,
            "authoritative_source": "canonical_session_marker",
            "marker": {"session": session, "workspace": str(tmp_path), "updated_at": "2026-01-01T00:00:00Z"},
            "event_cursors": {},
            "needs_human": {},
            "active_step_heartbeat": {},
            "stale_evidence": [],
        }

    def fake_normalize(raw):
        calls["normalize"] += 1
        assert raw["target_id"] == "session-a:demo-plan"
        return object()

    monkeypatch.setattr(inventory_module, "resolve_current_target", fake_resolve)
    monkeypatch.setattr(inventory_module, "normalize_evidence", fake_normalize)
    result = collect_authority_inventory(
        plan,
        session="session-a",
        marker_dir=marker_dir,
        collection_time="2026-01-01T00:00:01Z",
    )

    assert calls == {"resolve": 1, "normalize": 1}
    by_key = {(record.category, record.source_class): record for record in result.records}
    assert by_key[("cloud", "session_marker")].presence == "present"
    assert by_key[("cloud", "current_target")].identity["target_id"] == "session-a:demo-plan"
    assert by_key[("run_state", "normalization")].details["normalized_type"] == "object"
