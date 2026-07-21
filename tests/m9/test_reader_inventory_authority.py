"""M9 reader-inventory gates for raw authority sources."""

from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.orchestration.authority_readers import (
    DEFERRED,
    ENFORCED,
    INFORMATIONAL,
    WARN_ONLY,
    AUTHORITY_ROUTES,
    route_ids_by_disposition,
)
from arnold_pipelines.megaplan.authority.inventory import collect_authority_inventory


def test_authority_route_inventory_has_no_unclassified_positive_routes() -> None:
    dispositions = route_ids_by_disposition()

    assert set(dispositions) == {ENFORCED, WARN_ONLY, INFORMATIONAL, DEFERRED}
    assert dispositions[ENFORCED] == ["CHAIN-01"]
    assert dispositions[INFORMATIONAL] == ["STATUS-01"]
    assert len(dispositions[WARN_ONLY]) == 22
    assert len(dispositions[DEFERRED]) == 5
    assert len({route.id for route in AUTHORITY_ROUTES}) == len(AUTHORITY_ROUTES)


def test_raw_reader_route_descriptions_are_not_marked_enforced_except_chain_gate() -> None:
    raw_terms = (
        "raw",
        "marker",
        "status",
        "terminal",
        "pointer",
        "completed_ids labels",
    )
    raw_like = [
        route
        for route in AUTHORITY_ROUTES
        if any(term in route.description.lower() for term in raw_terms)
    ]

    assert raw_like
    assert all(route.id == "CHAIN-01" or route.disposition != ENFORCED for route in raw_like)
    assert all(route.owner_or_reason.strip() for route in raw_like)


def test_historical_adapters_are_read_only_and_non_authoritative() -> None:
    payload = json.loads(Path("evidence/wbc-historical-adapters.json").read_text())
    adapters = payload["adapters"]
    classes = {adapter["adapter_class"] for adapter in adapters}

    assert {
        "filename",
        "marker",
        "mutable_receipt",
        "process",
        "prose",
        "raw_json",
        "token",
    } <= classes
    for adapter in adapters:
        proof = adapter["zero_authority_caller_proof"]
        assert proof["authority_increasing_write_allowed"] is False
        assert proof["authority_increasing_writes_detected"] == []
        assert proof["diagnostic_only"] is True
        assert proof["mode"] in {"shadow", "retired"}
        if adapter["expiry"]["status"] == "expired":
            assert adapter["non_authoritative"] is True
            assert "Zero-reader gate active" in adapter["zero_reader_gate"]


def test_boundary_inventory_has_no_approved_raw_authority_reader_rows() -> None:
    payload = json.loads(Path("evidence/wbc-boundary-inventory.json").read_text())
    rows = payload.get("rows", ())
    compatibility = payload.get("compatibility_readers", ())
    current_assertions = payload.get("current_state_assertions", ())

    encoded_rows = json.dumps(rows, sort_keys=True)
    assert "approved_raw_authority_reader" not in encoded_rows
    assert all(
        item.get("authority_posture") != "authority"
        for item in compatibility
        if isinstance(item, dict)
    )
    assert all(
        item.get("source") != "implicit_latest_authority"
        for item in current_assertions
        if isinstance(item, dict)
    )


def test_generated_inventory_marks_legacy_batch_files_contradictory_not_authority(
    tmp_path: Path,
) -> None:
    (tmp_path / "state.json").write_text(
        json.dumps({"name": tmp_path.name, "schema_version": 1}),
        encoding="utf-8",
    )
    (tmp_path / "finalize.json").write_text(
        json.dumps({"tasks": [{"id": "T33"}], "sense_checks": []}),
        encoding="utf-8",
    )
    (tmp_path / "execution_batch_1.json").write_text(
        json.dumps({"task_updates": [{"task_id": "T33", "status": "done"}]}),
        encoding="utf-8",
    )

    inventory = collect_authority_inventory(tmp_path)
    legacy_records = [
        record
        for record in inventory.records
        if record.source_class.startswith("legacy_batch_artifacts:")
    ]

    assert legacy_records
    assert {record.role for record in legacy_records} == {"claim"}
    assert {record.presence for record in legacy_records} == {"contradictory"}
    assert all("lacks durable batch scope" in record.reason for record in legacy_records)
    assert "accepted_task_ids" not in inventory.to_json()
