"""M9 rebuild parity proof for registered rebuildable projections.

The source ledgers in these tests model immutable evidence: each record carries
WBC identity/cursor data plus projection-specific payload.  Cached projection
snapshots are disposable.  The registry must be able to delete and rebuild
every in-scope projection from source records and reproduce the same ordered
view, source cursor vector, and digest.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

import arnold_pipelines.megaplan._core.io as projection_io
from arnold_pipelines.megaplan.capsule_projection import (
    capsule_definition_identity_projection,
)
from arnold_pipelines.megaplan.custody.projections import (
    PROJECTION_SCHEMA_VERSION as CUSTODY_PROJECTION_SCHEMA_VERSION,
    ProjectionEventType,
)
from arnold_pipelines.megaplan.observability.projection_rebuild import (
    ProjectionRegistry,
    capture_source_cursor_vector,
    compare_all_projections,
    compute_projection_digest,
    rebuild_all_projections,
)
from arnold_pipelines.megaplan.orchestration.advisory_projection import (
    _project_advisory_path_list,
)
from arnold_pipelines.megaplan.prompts._projection import (
    PromptProjectionCapabilities,
    project_execute_context,
)
from arnold_pipelines.megaplan.schema_projection import project_schema_owned_fields
from arnold_pipelines.megaplan.strategy.contract import (
    REQUIRED_ROADMAP_SECTIONS,
    RoadmapEntry,
    SourceLocation,
    StrategyDocument,
    StrategyIdentity,
    StrategySection,
)
from arnold_pipelines.megaplan.strategy.projection import project_strategy
from arnold_pipelines.megaplan.workers._projection_caps import (
    codex_projection_capabilities,
    hermes_projection_capabilities,
    shannon_projection_capabilities,
)


EXPECTED_IN_SCOPE_PROJECTIONS = (
    "advisory-path-list",
    "capsule-definition",
    "custody-event-view",
    "prompt-execute-context",
    "schema-owned-fields",
    "strategy-document",
    "worker-capabilities",
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"encoding": "hex", "value": value.hex()}
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def _source_trace(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "ledger_sequence": record["ledger_sequence"],
            "attempt_id": record["attempt_id"],
            "boundary_id": record["boundary_id"],
            "event_type": record["event_type"],
            "evidence_id": record["evidence_id"],
            "content_digest": record["content_digest"],
        }
        for record in records
    ]


def _payload(records: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    return records[-1]["immutable_evidence"]["projection_payload"]


def _projection_view(
    projection_id: str,
    records: Sequence[Mapping[str, Any]],
    body: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "projection_id": projection_id,
        "authority": "non_authoritative_rebuild_projection",
        "source": {
            "kind": "authoritative_wbc_records_plus_immutable_evidence",
            "ordered_wbc_trace": _source_trace(records),
        },
        "view": dict(body),
    }


def _schema_owned_fields_builder(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    payload = _payload(records)
    projected = project_schema_owned_fields(
        payload["payload"],
        payload["schema"],
        contract="m9.schema-owned-fields",
    )
    return _projection_view(
        "schema-owned-fields",
        records,
        {"owned_fields": projected},
    )


def _capsule_definition_builder(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    payload = _payload(records)
    projection = capsule_definition_identity_projection(
        static_behavioral_hash=payload["static_behavioral_hash"],
        runtime_topology_hash=payload["runtime_topology_hash"],
    )
    return _projection_view(
        "capsule-definition",
        records,
        {"definition": _json_safe(projection)},
    )


def _strategy_document_builder(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    payload = _payload(records)
    document = StrategyDocument(
        schema_version=payload["schema_version"],
        stable_direction=[
            StrategySection(
                title=section["title"],
                body=section["body"],
                source_location=SourceLocation(**section["source"]),
            )
            for section in payload["stable_direction"]
        ],
        roadmap={
            horizon: [
                RoadmapEntry(
                    identity=StrategyIdentity(
                        type=entry["type"],
                        ref=entry["ref"],
                    ),
                    display_title=entry["title"],
                    horizon=horizon,
                    source_location=SourceLocation(**entry["source"]),
                )
                for entry in payload["roadmap"].get(horizon, [])
            ]
            for horizon in REQUIRED_ROADMAP_SECTIONS
        },
        diagnostics=[],
    )
    return _projection_view(
        "strategy-document",
        records,
        {"strategy": project_strategy(document)},
    )


def _prompt_execute_context_builder(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    payload = _payload(records)
    caps = PromptProjectionCapabilities(**payload["capabilities"])
    return _projection_view(
        "prompt-execute-context",
        records,
        {"execute_context": project_execute_context(payload["finalize_data"], capabilities=caps)},
    )


def _worker_capabilities_builder(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    payload = _payload(records)
    codex = codex_projection_capabilities(**payload["codex"])
    hermes = hermes_projection_capabilities(payload["hermes_toolsets"])
    shannon = shannon_projection_capabilities(**payload["shannon"])
    return _projection_view(
        "worker-capabilities",
        records,
        {
            "capabilities": {
                "codex": vars(codex),
                "hermes": vars(hermes),
                "shannon": vars(shannon),
            }
        },
    )


def _advisory_path_list_builder(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    payload = _payload(records)
    projection = _project_advisory_path_list(
        payload["paths"],
        plan_dir=Path(payload["plan_dir"]),
        artifact_name="unused-because-inline.json",
        label="changed_files",
        item_limit=40,
    )
    return _projection_view(
        "advisory-path-list",
        records,
        {"changed_files": projection},
    )


def _custody_event_view_builder(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    events = [
        {
            "event_type": record["immutable_evidence"]["projection_payload"]["event_type"],
            "payload": record["immutable_evidence"]["projection_payload"]["payload"],
        }
        for record in records
    ]
    return _projection_view(
        "custody-event-view",
        records,
        {
            "schema_version": CUSTODY_PROJECTION_SCHEMA_VERSION,
            "events": events,
            "event_count": len(events),
        },
    )


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _cursor_vector_dict(vector: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        projection_id: cursor.to_dict()
        for projection_id, cursor in sorted(vector.items())
    }


def _source_records(
    projection_id: str,
    *payloads: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for index, payload in enumerate(payloads, start=1):
        event_type = "started" if index == 1 else "completed"
        records.append(
            {
                "source_schema": "m9.authoritative-source-record.v1",
                "projection_id": projection_id,
                "environment": "test",
                "session": "session-alpha",
                "chain": "CHAIN-01",
                "plan_revision": "sha256:plan-revision",
                "phase": "execute",
                "task": "T31",
                "attempt_id": f"attempt-{projection_id}",
                "boundary_id": f"M9-{projection_id}",
                "ledger_sequence": index,
                "event_type": event_type,
                "evidence_id": f"evidence-{projection_id}-{index}",
                "content_digest": f"sha256:{projection_id.replace('-', ''):0<64}"[:71],
                "immutable_evidence": {
                    "kind": "projection-source-payload",
                    "projection_payload": dict(payload),
                },
            }
        )
    return tuple(records)


@pytest.fixture
def fixed_projection_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(projection_io, "now_utc", lambda: "2026-07-21T00:00:00Z")


@pytest.fixture
def rebuild_registry(tmp_path: Path) -> ProjectionRegistry:
    source_dir = tmp_path / "source-ledgers"
    advisory_plan_dir = tmp_path / "advisory-plan"
    advisory_plan_dir.mkdir()

    sources = {
        "schema-owned-fields": _source_records(
            "schema-owned-fields",
            {
                "schema": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "status": {"type": "string"},
                    },
                },
                "payload": {
                    "task_id": "T31",
                    "status": "done",
                    "raw_legacy_status": "ignored",
                },
            },
            {
                "schema": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "status": {"type": "string"},
                    },
                },
                "payload": {
                    "task_id": "T31",
                    "status": "done",
                    "raw_legacy_status": "ignored-after-rebuild",
                },
            },
        ),
        "capsule-definition": _source_records(
            "capsule-definition",
            {
                "static_behavioral_hash": "sha256:static",
                "runtime_topology_hash": None,
            },
            {
                "static_behavioral_hash": "sha256:static",
                "runtime_topology_hash": "sha256:runtime",
            },
        ),
        "strategy-document": _source_records(
            "strategy-document",
            {
                "schema_version": 1,
                "stable_direction": [
                    {
                        "title": "Mission",
                        "body": "Keep projections rebuildable from source records.",
                        "source": {"path": "STRATEGY.md", "line": 1, "column": 1},
                    }
                ],
                "roadmap": {
                    "Now": [
                        {
                            "type": "task",
                            "ref": "T31",
                            "title": "Rebuild parity",
                            "source": {"path": "plan.md", "line": 20, "column": 1},
                        }
                    ]
                },
            },
            {
                "schema_version": 1,
                "stable_direction": [
                    {
                        "title": "Mission",
                        "body": "Keep projections rebuildable from source records.",
                        "source": {"path": "STRATEGY.md", "line": 1, "column": 1},
                    }
                ],
                "roadmap": {
                    "Now": [
                        {
                            "type": "task",
                            "ref": "T31",
                            "title": "Rebuild parity",
                            "source": {"path": "plan.md", "line": 20, "column": 1},
                        }
                    ],
                    "Next": [],
                    "Later": [],
                },
            },
        ),
        "prompt-execute-context": _source_records(
            "prompt-execute-context",
            {
                "capabilities": {
                    "can_read_plan_dir": True,
                    "can_read_project_dir": True,
                    "has_file_tools": True,
                    "checkpoint_write_access": True,
                },
                "finalize_data": {
                    "tasks": [
                        {
                            "id": "T30",
                            "status": "done",
                            "description": "Gate wrapper bypasses.",
                            "executor_notes": "Converted bypasses to typed gaps.",
                        },
                        {
                            "id": "T31",
                            "status": "pending",
                            "description": "Add rebuild parity tests.",
                        },
                    ],
                    "sense_checks": [{"id": "SC31", "question": "Parity?"}],
                    "success_criteria": ["rebuild parity"],
                },
            },
            {
                "capabilities": {
                    "can_read_plan_dir": True,
                    "can_read_project_dir": True,
                    "has_file_tools": True,
                    "checkpoint_write_access": True,
                },
                "finalize_data": {
                    "tasks": [
                        {
                            "id": "T30",
                            "status": "done",
                            "description": "Gate wrapper bypasses.",
                            "executor_notes": "Converted bypasses to typed gaps.",
                        },
                        {
                            "id": "T31",
                            "status": "pending",
                            "description": "Add rebuild parity tests.",
                        },
                    ],
                    "sense_checks": [{"id": "SC31", "question": "Parity?"}],
                    "success_criteria": ["rebuild parity"],
                },
            },
        ),
        "worker-capabilities": _source_records(
            "worker-capabilities",
            {
                "codex": {"resumed_session": False},
                "hermes_toolsets": ["file-readonly"],
                "shannon": {"read_only": True},
            },
            {
                "codex": {
                    "resumed_session": True,
                    "session_has_plan_dir_access": True,
                    "checkpoint_write_access": False,
                },
                "hermes_toolsets": ["terminal"],
                "shannon": {"read_only": False},
            },
        ),
        "advisory-path-list": _source_records(
            "advisory-path-list",
            {
                "plan_dir": str(advisory_plan_dir),
                "paths": ["arnold/workflow/wbc_queries.py"],
            },
            {
                "plan_dir": str(advisory_plan_dir),
                "paths": [
                    "arnold/workflow/wbc_queries.py",
                    "arnold_pipelines/megaplan/observability/projection_rebuild.py",
                    "tests/m9/test_rebuild_digest_parity.py",
                ],
            },
        ),
        "custody-event-view": _source_records(
            "custody-event-view",
            {
                "event_type": ProjectionEventType.SNAPSHOT_BUILT.value,
                "payload": {"projection_id": "custody", "cursor": 1},
            },
            {
                "event_type": ProjectionEventType.APPEND_CURSOR_CHECKED.value,
                "payload": {"projection_id": "custody", "cursor": 2},
            },
        ),
    }

    builders = {
        "schema-owned-fields": _schema_owned_fields_builder,
        "capsule-definition": _capsule_definition_builder,
        "strategy-document": _strategy_document_builder,
        "prompt-execute-context": _prompt_execute_context_builder,
        "worker-capabilities": _worker_capabilities_builder,
        "advisory-path-list": _advisory_path_list_builder,
        "custody-event-view": _custody_event_view_builder,
    }

    registry = ProjectionRegistry()
    for projection_id, records in sources.items():
        source_path = source_dir / f"{projection_id}.jsonl"
        _write_jsonl(source_path, records)
        registry.register(
            projection_id,
            builders[projection_id],
            source_path=source_path,
        )
    return registry


def test_delete_and_rebuild_every_in_scope_projection_preserves_parity(
    rebuild_registry: ProjectionRegistry,
    tmp_path: Path,
    fixed_projection_clock: None,
) -> None:
    assert rebuild_registry.list_registered() == EXPECTED_IN_SCOPE_PROJECTIONS

    projection_dir = tmp_path / "projection-cache"
    projection_dir.mkdir()
    before_views = rebuild_all_projections(rebuild_registry)
    before_vector = _cursor_vector_dict(capture_source_cursor_vector(rebuild_registry))
    before_digests = {
        projection_id: compute_projection_digest(view)
        for projection_id, view in before_views.items()
    }
    source_bytes = {
        projection_id: rebuild_registry.source_path(projection_id).read_bytes()
        for projection_id in rebuild_registry.list_registered()
    }

    for projection_id, view in before_views.items():
        path = projection_dir / f"{projection_id}.json"
        path.write_text(json.dumps(view, sort_keys=True), encoding="utf-8")
        assert _read_json(path) == view
        path.unlink()
        assert not path.exists()

    rebuilt_views = rebuild_all_projections(rebuild_registry)
    rebuilt_vector = _cursor_vector_dict(capture_source_cursor_vector(rebuild_registry))
    reports = compare_all_projections(rebuild_registry, existing_views=before_views)

    assert rebuilt_views == before_views
    assert rebuilt_vector == before_vector
    assert set(reports) == set(EXPECTED_IN_SCOPE_PROJECTIONS)

    for projection_id in EXPECTED_IN_SCOPE_PROJECTIONS:
        rebuilt_digest = compute_projection_digest(rebuilt_views[projection_id])
        assert rebuilt_digest == before_digests[projection_id]
        report = reports[projection_id]
        assert report.parity is True
        assert report.rebuild_digest == before_digests[projection_id]
        assert report.existing_digest == before_digests[projection_id]
        assert report.source_cursor is not None
        assert report.source_cursor.to_dict() == before_vector[projection_id]
        assert report.diagnostics == ()
        assert rebuild_registry.source_path(projection_id).read_bytes() == source_bytes[projection_id]


def test_registry_reports_digest_mismatch_for_stale_cached_projection(
    rebuild_registry: ProjectionRegistry,
    fixed_projection_clock: None,
) -> None:
    current_view = rebuild_registry.rebuild("schema-owned-fields")
    stale_view = json.loads(json.dumps(current_view, sort_keys=True))
    stale_view["view"]["owned_fields"]["status"] = "stale"

    report = compare_all_projections(
        rebuild_registry,
        existing_views={"schema-owned-fields": stale_view},
    )["schema-owned-fields"]

    assert report.parity is False
    assert report.rebuild_digest != report.existing_digest
    assert report.source_cursor is not None
    assert any("Digest mismatch" in diagnostic for diagnostic in report.diagnostics)
