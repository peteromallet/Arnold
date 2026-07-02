from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

from arnold.pipeline import (
    COMPOSITE_RESUME_CURSOR_FILENAME,
    persist_composite_resume_cursor,
    read_composite_resume_cursor,
)
from arnold.pipeline.native.checkpoint import classify_resume_cursor, read_native_cursor
from arnold.pipeline.native.runtime import run_native_pipeline
from arnold.pipelines.evidence_pack.pipeline import build_pipeline
from arnold.pipelines.evidence_pack.resume import resume_evidence_pack
from arnold.pipelines.evidence_pack.verifier import make_evidence_pack_payload


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")


def _failing_evidence_pack(evidence_pack_id: str = "pack-001") -> dict[str, Any]:
    return make_evidence_pack_payload(
        evidence_pack_id=evidence_pack_id,
        source_ticket="",
        checkpoints=[
            {
                "checkpoint_id": f"{evidence_pack_id}.structural_audit",
                "status": "passed",
                "artifact_refs": [],
            },
        ],
    )


def test_evidence_pack_resume_interoperates_with_shared_composite_cursor(
    tmp_path: Path,
) -> None:
    pack_path = tmp_path / "input_pack.json"
    _write_json(pack_path, _failing_evidence_pack("pack-composite"))

    result = run_native_pipeline(
        build_pipeline().native_program,
        artifact_root=tmp_path,
        initial_state={"evidence_pack_path": str(pack_path)},
    )

    assert result.suspended is True
    assert classify_resume_cursor(tmp_path) == "native"
    native_cursor = read_native_cursor(tmp_path)
    assert native_cursor is not None

    persist_composite_resume_cursor(
        tmp_path,
        children={"human_review": {"cursor": native_cursor}},
        shared_awaitable="approval/pack-composite",
    )

    assert read_composite_resume_cursor(tmp_path) == {
        "kind": "composite_suspension",
        "version": 1,
        "children": {"human_review": {"cursor": native_cursor}},
        "shared_awaitable": "approval/pack-composite",
    }
    assert (tmp_path / COMPOSITE_RESUME_CURSOR_FILENAME).exists()

    resumed = resume_evidence_pack(
        tmp_path,
        envelope=result.envelope,
        human_input={"approved": True, "comment": "ship it"},
    )

    assert resumed.resumed is True
    assert (tmp_path / "attestation.json").exists()
    assert (tmp_path / COMPOSITE_RESUME_CURSOR_FILENAME).exists()


def test_evidence_pack_resume_module_has_no_continuation_builder() -> None:
    from arnold.pipelines.evidence_pack import resume as resume_module

    source = inspect.getsource(resume_module)
    assert "build_continuation_pipeline" not in source
