"""T34: deterministic fake-backend workflow execution."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold.execution import ExecutionRegistries, ExecutionState
from arnold.execution.backend import ArtifactSpec, NodeOutcome, NodeState
from arnold.kernel import (
    GeneratedArtifactProvenance,
    derive_pipeline_identity,
    read_event_journal,
)
from arnold.kernel.journal import NDJsonEventJournal
from tests.arnold.execution.fixtures import linear_manifest


def _normalize_event(event: Any) -> dict[str, Any]:
    """Return a comparable view of an event.

    Sequence numbers and event IDs are deterministic when the same run_id and
    counter seed are used, but we also drop them here to emphasize that the
    *payload* sequence is stable.
    """

    payload = dict(event.payload)
    # Scope stacks are serialized as lists in JSON; normalize for comparison.
    payload["scope_stack"] = tuple(payload.get("scope_stack", ()))
    return {
        "family": event.family.value,
        "kind": event.kind,
        "payload": payload,
    }


def _artifact_hashes(events: list[Any]) -> tuple[str, ...]:
    return tuple(
        e.payload["content_hash"]
        for e in events
        if e.kind == "artifact_written"
    )


def _run_deterministic(
    artifact_root: Path,
    run_id: str,
    now: datetime,
) -> Any:
    from tests.arnold.execution.conftest import FakeBackend

    manifest = linear_manifest()
    provenance = GeneratedArtifactProvenance(
        generator_module="tests.arnold.execution.test_determinism",
        generator_source_hash="sha256:" + "0" * 64,
        manifest_contract_version=manifest.SCHEMA_VERSION,
        generated_at=now.isoformat(),
    )
    backend = FakeBackend(
        run_id=run_id,
        now=now,
        init_ts=now,
        node_behaviors={
            "a": NodeOutcome(
                state=NodeState.COMPLETED,
                outputs={"value": 1},
                artifacts=(
                    ArtifactSpec(
                        artifact_id="a.out",
                        content=b"artifact-a",
                        content_type_id="text/plain",
                        extension="txt",
                        provenance=provenance,
                    ),
                ),
            ),
            "b": NodeOutcome(outputs={"value": 2}),
            "c": NodeOutcome(outputs={"value": 3}),
        },
    )
    return backend.run_manifest(
        manifest,
        artifact_root=artifact_root,
        registries=ExecutionRegistries(),
    )


def test_identical_runs_produce_identical_events_and_artifacts(
    tmp_path: Path,
) -> None:
    run_id = "run:determinism-test"
    now = datetime(2026, 6, 22, 0, 0, 0, tzinfo=timezone.utc)
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"

    result_a = _run_deterministic(root_a, run_id, now)
    result_b = _run_deterministic(root_b, run_id, now)

    assert result_a.state is ExecutionState.COMPLETED
    assert result_b.state is ExecutionState.COMPLETED
    assert result_a.outputs == result_b.outputs
    assert result_a.outputs == {"a": {"value": 1}, "b": {"value": 2}, "c": {"value": 3}}

    events_a = read_event_journal(root_a)
    events_b = read_event_journal(root_b)
    assert len(events_a) == len(events_b)
    assert [_normalize_event(e) for e in events_a] == [
        _normalize_event(e) for e in events_b
    ]

    hashes_a = _artifact_hashes(events_a)
    hashes_b = _artifact_hashes(events_b)
    assert hashes_a == hashes_b
    assert len(hashes_a) == 1


def test_separate_runs_have_independent_journals(
    tmp_path: Path,
) -> None:
    """Sanity check: two runs do not accidentally share journal state."""

    run_id = "run:isolation-test"
    now = datetime(2026, 6, 22, 0, 0, 0, tzinfo=timezone.utc)
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"

    _run_deterministic(root_a, run_id, now)
    _run_deterministic(root_b, run_id, now)

    journal_a = NDJsonEventJournal(root_a)
    journal_b = NDJsonEventJournal(root_b)
    assert len(journal_a.read()) == len(journal_b.read())
    assert journal_a.journal_uri != journal_b.journal_uri


def test_backend_populates_artifact_provenance_from_executing_manifest(
    tmp_path: Path,
) -> None:
    run_id = "run:artifact-identity-test"
    now = datetime(2026, 6, 22, 0, 0, 0, tzinfo=timezone.utc)
    result = _run_deterministic(tmp_path, run_id, now)
    manifest = linear_manifest()
    meta_payload = json.loads(
        (tmp_path / "a.out" / "v1.txt.meta.json").read_text(encoding="utf-8")
    )

    assert result.state is ExecutionState.COMPLETED
    assert meta_payload["provenance"]["workflow_alias"] == manifest.id
    assert meta_payload["provenance"]["manifest_hash"] == manifest.manifest_hash
    assert meta_payload["provenance"]["pipeline_identity"] == derive_pipeline_identity(
        manifest.id, manifest.manifest_hash
    )


def test_backend_rejects_artifact_provenance_for_different_workflow(
    tmp_path: Path,
) -> None:
    from tests.arnold.execution.conftest import FakeBackend

    now = datetime(2026, 6, 22, 0, 0, 0, tzinfo=timezone.utc)
    manifest = linear_manifest()
    other_hash = "sha256:" + "b" * 64
    backend = FakeBackend(
        run_id="run:artifact-identity-mismatch-test",
        now=now,
        init_ts=now,
        node_behaviors={
            "a": NodeOutcome(
                artifacts=(
                    ArtifactSpec(
                        artifact_id="a.out",
                        content=b"artifact-a",
                        content_type_id="text/plain",
                        extension="txt",
                        provenance=GeneratedArtifactProvenance(
                            generator_module="tests.arnold.execution.test_determinism",
                            generator_source_hash="sha256:" + "0" * 64,
                            manifest_contract_version=manifest.SCHEMA_VERSION,
                            generated_at=now.isoformat(),
                            workflow_alias=manifest.id,
                            manifest_hash=other_hash,
                            pipeline_identity=derive_pipeline_identity(
                                manifest.id, other_hash
                            ),
                        ),
                    ),
                ),
            ),
        },
    )

    result = backend.run_manifest(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
    )

    assert result.state is ExecutionState.FAILED
    assert any(
        diagnostic.code == "execution_error"
        and "executing manifest" in diagnostic.message
        for diagnostic in result.diagnostics
    )
