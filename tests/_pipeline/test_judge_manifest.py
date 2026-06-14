from __future__ import annotations

from dataclasses import replace

from arnold.pipelines.megaplan._pipeline import (
    EVALUAND_RECORD_CONTENT_TYPE,
    JUDGE_MANIFEST_SCHEMA,
    JudgeManifestPort,
    compute_judge_version,
    compute_piece_version,
    compute_rubric_hash,
    dump_judge_manifest,
    load_judge_manifest,
    make_judge_manifest,
)
from arnold.pipelines.megaplan._pipeline.judge_manifest import JUDGE_KIND
from arnold.pipelines.megaplan._pipeline.judge_manifest_discovery import validate_judge_manifest
from arnold.pipelines.megaplan._pipeline.types import CONTENT_TYPES


def test_piece_version_is_canonical_and_changes_with_piece_identity() -> None:
    produces = (
        JudgeManifestPort("evaluand", EVALUAND_RECORD_CONTENT_TYPE),
    )

    baseline = compute_piece_version(
        implementation="megaplan.eval.wrapper:Judge",
        arnold_api_version="2026-05-31",
        produces=produces,
        source_hash="sha256:aaa",
        extra_identity={"b": 2, "a": 1},
    )
    reordered = compute_piece_version(
        implementation="megaplan.eval.wrapper:Judge",
        arnold_api_version="2026-05-31",
        produces=produces,
        source_hash="sha256:aaa",
        extra_identity={"a": 1, "b": 2},
    )
    changed = compute_piece_version(
        implementation="megaplan.eval.wrapper:Judge",
        arnold_api_version="2026-05-31",
        produces=produces,
        source_hash="sha256:bbb",
        extra_identity={"a": 1, "b": 2},
    )

    assert baseline == reordered
    assert baseline != changed
    assert len(baseline) == 64


def test_judge_version_changes_when_rubric_body_changes() -> None:
    piece_version = compute_piece_version(
        implementation="megaplan.eval.wrapper:Judge",
        arnold_api_version="2026-05-31",
    )

    first = compute_judge_version(
        piece_version=piece_version,
        rubric_body={"criteria": ["correctness"]},
        model_identity="model:gpt-5.4",
    )
    second = compute_judge_version(
        piece_version=piece_version,
        rubric_body={"criteria": ["correctness", "style"]},
        model_identity="model:gpt-5.4",
    )

    assert first != second


def test_judge_version_changes_when_model_identity_changes() -> None:
    piece_version = compute_piece_version(
        implementation="megaplan.eval.wrapper:Judge",
        arnold_api_version="2026-05-31",
    )
    rubric_hash = compute_rubric_hash("score the answer")

    first = compute_judge_version(
        piece_version=piece_version,
        rubric_hash=rubric_hash,
        model_identity="model:gpt-5.4",
    )
    second = compute_judge_version(
        piece_version=piece_version,
        rubric_hash=rubric_hash,
        model_identity="model:gpt-5.5",
    )

    assert first != second


def test_piece_and_judge_versions_do_not_collapse_same_identity_material() -> None:
    produces = (
        JudgeManifestPort("evaluand", EVALUAND_RECORD_CONTENT_TYPE),
    )
    piece_version = compute_piece_version(
        implementation="megaplan.eval.wrapper:Judge",
        arnold_api_version="2026-05-31",
        produces=produces,
        source_hash="sha256:abc123",
    )
    judge_version = compute_judge_version(
        piece_version=piece_version,
        rubric_body={"rubric": "prefer factual answers"},
        model_identity="model:gpt-5.4",
    )

    assert piece_version != judge_version


def test_piece_version_changes_when_port_identity_changes() -> None:
    baseline = compute_piece_version(
        implementation="megaplan.eval.wrapper:Judge",
        arnold_api_version="2026-05-31",
        produces=(JudgeManifestPort("evaluand", EVALUAND_RECORD_CONTENT_TYPE),),
        source_hash="sha256:abc123",
    )
    renamed_port = compute_piece_version(
        implementation="megaplan.eval.wrapper:Judge",
        arnold_api_version="2026-05-31",
        produces=(JudgeManifestPort("scorecard", EVALUAND_RECORD_CONTENT_TYPE),),
        source_hash="sha256:abc123",
    )

    assert baseline != renamed_port


def test_manifest_json_round_trip(tmp_path) -> None:
    manifest = make_judge_manifest(
        name="wrapper_eval",
        implementation="megaplan.eval.wrapper:Judge",
        arnold_api_version="2026-05-31",
        model_identity="model:gpt-5.4",
        rubric_body={"rubric": "prefer factual answers"},
        consumes=(JudgeManifestPort("candidate", "text/markdown"),),
        produces=(JudgeManifestPort("evaluand", EVALUAND_RECORD_CONTENT_TYPE),),
        source_hash="sha256:abc123",
    )

    path = tmp_path / "wrapper_eval.judge.json"
    dump_judge_manifest(manifest, path)
    loaded = load_judge_manifest(path)

    assert loaded == manifest
    assert loaded.schema == JUDGE_MANIFEST_SCHEMA
    assert loaded.kind == "judge"


def test_validate_judge_manifest_rejects_wrong_schema_kind_and_missing_ports() -> None:
    valid = make_judge_manifest(
        name="wrapper_eval",
        implementation="megaplan.eval.wrapper:Judge",
        arnold_api_version="2026-05-31",
        model_identity="model:gpt-5.4",
        rubric_body={"rubric": "prefer factual answers"},
        consumes=(JudgeManifestPort("candidate", "text/markdown"),),
        produces=(JudgeManifestPort("evaluand", EVALUAND_RECORD_CONTENT_TYPE),),
        source_hash="sha256:abc123",
    )

    diagnostics = validate_judge_manifest(
        replace(valid, schema="wrong", kind="not-judge", consumes=(), produces=()),
        path="bad.judge.json",
    )

    assert diagnostics.ok is False
    assert f"schema must be {JUDGE_MANIFEST_SCHEMA!r}" in diagnostics.defects
    assert f"kind must be {JUDGE_KIND!r}" in diagnostics.defects
    assert "consumes must declare at least one input port" in diagnostics.defects
    assert "produces must declare at least one output port" in diagnostics.defects
    assert f"produces must include {EVALUAND_RECORD_CONTENT_TYPE!r}" in diagnostics.defects


def test_validate_judge_manifest_rejects_unknown_content_types() -> None:
    manifest = make_judge_manifest(
        name="wrapper_eval",
        implementation="megaplan.eval.wrapper:Judge",
        arnold_api_version="2026-05-31",
        model_identity="model:gpt-5.4",
        rubric_body={"rubric": "prefer factual answers"},
        consumes=(JudgeManifestPort("candidate", "application/x-unknown"),),
        produces=(JudgeManifestPort("evaluand", EVALUAND_RECORD_CONTENT_TYPE),),
        source_hash="sha256:abc123",
    )

    diagnostics = validate_judge_manifest(manifest, path="bad.judge.json")

    assert diagnostics.ok is False
    assert (
        "consumes.candidate uses unknown content type 'application/x-unknown'"
        in diagnostics.defects
    )


def test_evaluand_record_content_type_is_registered_builtin() -> None:
    assert EVALUAND_RECORD_CONTENT_TYPE in CONTENT_TYPES
    assert len(CONTENT_TYPES.get(EVALUAND_RECORD_CONTENT_TYPE)) == 64
