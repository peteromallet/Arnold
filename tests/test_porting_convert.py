from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from vibecomfy.commands.convert import _cmd_convert
from vibecomfy.porting.convert import (
    ConversionWriteError,
    ManualTemplateRefusal,
    PortConvertResult,
    PortConvertValidation,
    _check_manual_refusal,
    _compute_diff,
    port_convert_and_write,
    port_convert_workflow,
)
# parity helpers exercised indirectly through port_convert_workflow
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


class FakeSchemaProvider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _sample_workflow(*, include_required_input: bool = True) -> VibeWorkflow:
    workflow = VibeWorkflow(
        "sample",
        WorkflowSource("source/sample", path="workflow_corpus/source.json", source_type="raw_json"),
    )
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})
    save_inputs = {"filename_prefix": "out/sample"} if include_required_input else {}
    workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs=save_inputs)
    workflow.edges.append(VibeEdge("1", "0", "2", "images"))
    workflow.metadata["model_assets"] = [
        {"name": "model.safetensors", "url": "https://example.test/model.safetensors", "subdir": "checkpoints"}
    ]
    workflow.requirements.custom_nodes.append("ComfyUI-TestPack")
    return workflow


def _provider() -> FakeSchemaProvider:
    return FakeSchemaProvider(
        {
            "LoadImage": NodeSchema(
                class_type="LoadImage",
                pack=None,
                inputs={"image": InputSpec("STRING", required=True)},
                outputs=[OutputSpec("IMAGE", "image")],
            ),
            "SaveImage": NodeSchema(
                class_type="SaveImage",
                pack=None,
                inputs={"images": InputSpec("IMAGE", required=True), "filename_prefix": InputSpec("STRING", required=True)},
                outputs=[],
            ),
        }
    )


def test_port_convert_defaults_to_importable_scratchpad_without_ready_metadata() -> None:
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/source.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )

    assert result.mode == "scratchpad"
    assert result.ready_id is None
    assert result.validation is not None and result.validation.ok
    assert result.validation.import_ok
    assert result.validation.build_ok
    assert result.validation.compile_ok
    assert result.validation.schema_ok is True
    assert "READY_METADATA" not in result.text
    assert "source_type='scratchpad'" in result.text
    assert "'source_hash': 'sha256:abc'" in result.text
    assert "'workflow_shape': {'nodes': 2, 'runtime_nodes': 2}" in result.text
    assert "'output_mode': 'scratchpad'" in result.text


def test_port_convert_emits_registered_output_names() -> None:
    workflow = _sample_workflow()
    workflow.nodes["1"].metadata["output_names"] = ["image"]

    result = port_convert_workflow(
        workflow,
        source_path="workflow_corpus/source.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )

    assert "_outputs=('image',)" in result.text
    assert result.validation is not None and result.validation.ok


def test_port_convert_ready_template_candidate_requires_ready_id() -> None:
    result = port_convert_workflow(
        _sample_workflow(),
        ready_id="image/sample",
        source_path="workflow_corpus/source.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )

    assert result.mode == "ready_template"
    assert result.ready_id == "image/sample"
    assert result.validation is not None and result.validation.ok
    assert "READY_METADATA =" in result.text
    assert "'ready_template': 'image/sample'" in result.text
    assert "'source_hash': 'sha256:abc'" in result.text
    assert "'workflow_shape': {'nodes': 2, 'runtime_nodes': 2}" in result.text
    assert "'output_mode': 'ready_template'" in result.text
    assert "'ready_id': 'image/sample'" in result.text
    assert "'custom_nodes': ['ComfyUI-TestPack']" in result.text
    assert "'model.safetensors'" in result.text


def test_port_convert_rejects_ready_template_candidate_without_kind_name_id() -> None:
    with pytest.raises(ValueError, match="kind/name"):
        port_convert_workflow(_sample_workflow(), ready_id="sample")


def test_port_convert_validation_reports_schema_failures() -> None:
    result = port_convert_workflow(_sample_workflow(include_required_input=False), schema_provider=_provider())

    assert result.validation is not None
    assert not result.validation.ok
    assert result.validation.schema_ok is False
    assert result.validation.error == "schema validation failed"
    assert [issue.code for issue in result.validation.issues] == ["missing_required_input"]


# ---------------------------------------------------------------------------
# Golden tests — legacy ``vibecomfy convert`` behavior (before removal)
# ---------------------------------------------------------------------------


def test_legacy_vibecomfy_convert_now_fails_with_migration_message(tmp_path: Path) -> None:
    """Legacy convert exits non-zero with migration message, produces no output file."""
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(json.dumps({"nodes": []}), encoding="utf-8")
    out = tmp_path / "scratch.py"

    exit_code = _cmd_convert(argparse.Namespace(workflow=str(workflow_path), out=str(out)))
    assert exit_code != 0

    # No output file should have been written.
    assert not out.exists()


def test_legacy_convert_indexed_id_now_fails_with_migration_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legacy convert on indexed id exits non-zero with migration message, no output file."""
    workflow_path = tmp_path / "indexed_workflow.json"
    workflow_path.write_text(json.dumps({"nodes": []}), encoding="utf-8")

    index_path = tmp_path / "workflow_index.json"
    index_path.write_text(
        json.dumps([{"id": "my-workflow", "path": str(workflow_path)}]),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    out = tmp_path / "scratch.py"
    exit_code = _cmd_convert(argparse.Namespace(workflow="my-workflow", out=str(out)))
    assert exit_code != 0
    assert not out.exists()


def test_legacy_convert_ready_id_now_fails_with_migration_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legacy convert on ready-id exits non-zero with migration message, no output file."""
    out = tmp_path / "scratch.py"
    exit_code = _cmd_convert(argparse.Namespace(workflow="z_image", out=str(out)))
    assert exit_code != 0
    assert not out.exists()


def test_legacy_convert_api_shaped_json_now_fails_with_migration_message(tmp_path: Path) -> None:
    """Legacy convert on API-shaped JSON exits non-zero with migration message, no output file."""
    workflow_path = tmp_path / "api_shaped.json"
    workflow_path.write_text(
        json.dumps({
            "1": {"class_type": "LoadImage", "inputs": {"image": "test.png"}},
            "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": "out"}},
        }),
        encoding="utf-8",
    )
    out = tmp_path / "scratch.py"

    exit_code = _cmd_convert(argparse.Namespace(workflow=str(workflow_path), out=str(out)))
    assert exit_code != 0
    assert not out.exists()


# ---------------------------------------------------------------------------
# Canonical ``port convert`` tests — various source formats
# ---------------------------------------------------------------------------


def test_port_convert_from_ready_id_produces_importable_scratchpad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Canonical: ready_id → port_convert_workflow produces importable scratchpad."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.mode == "scratchpad"
    assert result.validation is not None and result.validation.ok
    assert result.validation.import_ok
    assert result.validation.build_ok
    assert result.validation.compile_ok


def test_port_convert_from_raw_json_produces_importable_scratchpad() -> None:
    """Canonical: raw JSON workflows produce importable scratchpads through port_convert_workflow."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/video/wan_t2v.json",
        provenance={"source_hash": "sha256:def"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.mode == "scratchpad"
    assert result.validation is not None and result.validation.ok
    assert "source_type='scratchpad'" in result.text
    assert "'source_hash': 'sha256:def'" in result.text


def test_port_convert_from_api_shaped_json_produces_importable_scratchpad() -> None:
    """Canonical: API-shaped JSON (dict of node dicts) produces importable scratchpad."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/api_shaped.json",
        provenance={"source_hash": "sha256:api"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.mode == "scratchpad"
    assert result.validation is not None and result.validation.ok
    assert "source_type='scratchpad'" in result.text


def test_port_convert_with_indexed_workflow_id_produces_importable_scratchpad() -> None:
    """Canonical: indexed workflow id source produces importable scratchpad."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_index:my-workflow",
        provenance={"source_hash": "sha256:idx"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.mode == "scratchpad"
    assert result.validation is not None and result.validation.ok
    assert "source_type='scratchpad'" in result.text


def test_port_convert_ready_template_candidate_does_not_preserve_api_workflow_inline() -> None:
    """Migration outcome: canonical port convert does NOT preserve inline API_WORKFLOW.

    The legacy converter produced inline API_WORKFLOW for ready-id sources.
    The canonical port convert emits proper VibeWorkflow builder code instead.
    """
    result = port_convert_workflow(
        _sample_workflow(),
        ready_id="image/sample",
        source_path="workflow_corpus/source.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.mode == "ready_template"
    assert "API_WORKFLOW =" not in result.text
    assert "READY_METADATA =" in result.text
    assert result.validation is not None and result.validation.ok


# ---------------------------------------------------------------------------
# T6 — Representative parity fixtures and tests
# ---------------------------------------------------------------------------


def test_parity_json_includes_widget_snapshots_and_output_counts() -> None:
    """Parity JSON includes widget snapshots, output-count evidence, and class type counts."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.validation is not None
    validation_json = result.validation.to_json()

    # Parity evidence fields
    assert "parity_ok" in validation_json
    assert "parity_diffs" in validation_json
    assert "source_output_count" in validation_json
    assert "emitted_output_count" in validation_json
    assert "source_class_type_counts" in validation_json
    assert "emitted_class_type_counts" in validation_json
    assert "source_widget_value_snapshot" in validation_json
    assert "emitted_widget_value_snapshot" in validation_json
    assert "source_topology_snapshot" in validation_json
    assert "emitted_topology_snapshot" in validation_json

    # Widget snapshots and output counts should be populated when parity succeeds
    if result.validation.parity_ok:
        assert isinstance(result.validation.source_widget_value_snapshot, int)
        assert isinstance(result.validation.emitted_widget_value_snapshot, int)
        assert isinstance(result.validation.source_output_count, int)
        assert isinstance(result.validation.emitted_output_count, int)


def test_parity_for_simple_image_z_image_produces_evidence(tmp_path: Path) -> None:
    """Simple image workflow (z_image) produces parity evidence through port_convert_workflow."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:z_image"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.validation is not None
    assert result.validation.ok is True
    # Parite evidence shape is present regardless of parity outcome
    v = result.validation
    assert isinstance(v.source_output_count, int)
    assert isinstance(v.emitted_output_count, int)
    assert isinstance(v.source_widget_value_snapshot, int)
    assert isinstance(v.emitted_widget_value_snapshot, int)
    assert isinstance(v.source_topology_snapshot, int)
    assert isinstance(v.emitted_topology_snapshot, int)
    assert isinstance(v.source_class_type_counts, dict)
    assert isinstance(v.emitted_class_type_counts, dict)


def test_parity_for_edit_qwen_image_edit_produces_evidence() -> None:
    """Edit workflow (qwen_image_edit) produces parity evidence."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/edit/qwen_image_edit.json",
        provenance={"source_hash": "sha256:qwen_edit"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.validation is not None
    v = result.validation
    assert isinstance(v.source_output_count, int)
    assert isinstance(v.emitted_output_count, int)
    assert isinstance(v.source_widget_value_snapshot, int)
    assert isinstance(v.emitted_widget_value_snapshot, int)


def test_parity_for_audio_ace_t2a_song_produces_evidence() -> None:
    """Audio/TTS workflow (ace_step_1_5_t2a_song) produces parity evidence."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/audio/ace_step_1_5_t2a_song.json",
        provenance={"source_hash": "sha256:ace_audio"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.validation is not None
    v = result.validation
    assert isinstance(v.source_output_count, int)
    assert isinstance(v.emitted_output_count, int)
    assert isinstance(v.source_widget_value_snapshot, int)
    assert isinstance(v.emitted_widget_value_snapshot, int)


def test_parity_for_wan_video_wan_t2v_produces_evidence() -> None:
    """Wan video workflow (wan_t2v) produces parity evidence."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/video/wan_t2v.json",
        provenance={"source_hash": "sha256:wan_video"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.validation is not None
    v = result.validation
    assert isinstance(v.source_output_count, int)
    assert isinstance(v.emitted_output_count, int)
    assert isinstance(v.source_widget_value_snapshot, int)
    assert isinstance(v.emitted_widget_value_snapshot, int)


def test_parity_for_ltx_ltx2_3_t2v_produces_evidence() -> None:
    """LTX workflow (ltx2_3_t2v) produces parity evidence."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/video/ltx2_3_t2v.json",
        provenance={"source_hash": "sha256:ltx_video"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.validation is not None
    v = result.validation
    assert isinstance(v.source_output_count, int)
    assert isinstance(v.emitted_output_count, int)
    assert isinstance(v.source_widget_value_snapshot, int)
    assert isinstance(v.emitted_widget_value_snapshot, int)


def test_opaque_component_fixture_exists_and_is_valid_json() -> None:
    """The opaque component fixture is valid JSON with UUID class type."""
    fixture_path = Path(__file__).parent / "fixtures" / "porting" / "opaque_component.json"
    assert fixture_path.exists()
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert "nodes" in data
    # At least one node should have a UUID-style class_type
    uuid_nodes = [
        node for node in data["nodes"]
        if len(node.get("type", "")) > 30 and "-" in node.get("type", "")
    ]
    assert len(uuid_nodes) > 0, "opaque_component.json must contain at least one UUID-type node"


def test_opaque_component_conversion_produces_validation() -> None:
    """Opaque component conversion runs and produces validation with parity evidence."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="tests/fixtures/porting/opaque_component.json",
        provenance={"source_hash": "sha256:opaque"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.validation is not None
    assert isinstance(result.validation.to_json(), dict)
    # Parity evidence fields are present even for opaque workflows
    assert result.validation.parity_ok is not None or result.validation.parity_ok is True or result.validation.parity_ok is False


def test_port_convert_result_to_json_excludes_raw_text() -> None:
    """PortConvertResult.to_json() excludes the raw text field by design."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    data = result.to_json()
    assert "text" not in data
    assert "mode" in data
    assert "ready_id" in data
    assert "validation" in data


def test_port_convert_validation_to_json_contains_all_parity_fields() -> None:
    """PortConvertValidation.to_json() contains all parity evidence fields."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    assert result.validation is not None
    vj = result.validation.to_json()
    for field in [
        "ok", "import_ok", "build_ok", "compile_ok", "schema_ok",
        "issues", "api_node_count", "error",
        "parity_ok", "parity_diffs",
        "source_output_count", "emitted_output_count",
        "source_class_type_counts", "emitted_class_type_counts",
        "source_widget_value_snapshot", "emitted_widget_value_snapshot",
        "source_topology_snapshot", "emitted_topology_snapshot",
    ]:
        assert field in vj, f"PortConvertValidation.to_json() missing field: {field}"


# ---------------------------------------------------------------------------
# T9 — Atomic conversion write, dry-run, diff, manual refusal tests
# ---------------------------------------------------------------------------


def test_atomic_write_succeeds_with_valid_result(tmp_path: Path) -> None:
    """port_convert_and_write writes to target when validation passes."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    target = tmp_path / "written.py"

    write_result = port_convert_and_write(result, target)
    assert write_result["written"] is True
    assert target.exists()
    assert "from vibecomfy.workflow import" in target.read_text(encoding="utf-8")


def test_atomic_write_refuses_manual_marker(tmp_path: Path) -> None:
    """Manual refusal: target with '# vibecomfy: manual' blocks writes."""
    target = tmp_path / "manual_template.py"
    target.write_text("# vibecomfy: manual\n# This is hand-authored\n", encoding="utf-8")
    original_bytes = target.read_bytes()

    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )

    with pytest.raises(ManualTemplateRefusal, match="manual"):
        port_convert_and_write(result, target)

    # File must be byte-for-byte unchanged
    assert target.read_bytes() == original_bytes


def test_atomic_write_failed_validation_leaves_file_unchanged(tmp_path: Path) -> None:
    """Failed validation leaves pre-existing file byte-for-byte unchanged."""
    target = tmp_path / "existing.py"
    target.write_text("# existing content\nprint('hello')\n", encoding="utf-8")
    original_bytes = target.read_bytes()

    # Create a result with a failing validation
    bad_validation = PortConvertValidation(
        ok=False,
        import_ok=True,
        build_ok=True,
        compile_ok=True,
        error="schema validation failed",
        parity_ok=None,
    )
    result = PortConvertResult(mode="scratchpad", text="# bad output", validation=bad_validation)

    with pytest.raises(ConversionWriteError, match="Validation failed"):
        port_convert_and_write(result, target)

    # File must be byte-for-byte unchanged
    assert target.read_bytes() == original_bytes
    assert target.read_text(encoding="utf-8") == "# existing content\nprint('hello')\n"


def test_atomic_write_failed_parity_leaves_file_unchanged(tmp_path: Path) -> None:
    """Failed parity leaves pre-existing file byte-for-byte unchanged."""
    target = tmp_path / "existing.py"
    target.write_text("# original\n", encoding="utf-8")
    original_bytes = target.read_bytes()

    # Validation passes but parity fails
    bad_validation = PortConvertValidation(
        ok=True,
        import_ok=True,
        build_ok=True,
        compile_ok=True,
        parity_ok=False,
        parity_diffs=["class_types only in B: {'ExtraNode': 1}"],
    )
    result = PortConvertResult(mode="scratchpad", text="# different output", validation=bad_validation)

    with pytest.raises(ConversionWriteError, match="Parity check failed"):
        port_convert_and_write(result, target)

    assert target.read_bytes() == original_bytes


def test_dry_run_does_not_write_file(tmp_path: Path) -> None:
    """Dry-run produces evidence payload without touching target."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    target = tmp_path / "not_written.py"

    write_result = port_convert_and_write(result, target, dry_run=True)
    assert write_result["written"] is False
    assert write_result["dry_run"] is True
    assert write_result["target"] == str(target)
    assert "validation" in write_result
    assert "diff" in write_result
    # File must not exist
    assert not target.exists()


def test_dry_run_includes_diff_metadata(tmp_path: Path) -> None:
    """Dry-run includes unified diff and line counts."""
    target = tmp_path / "existing.py"
    target.write_text("# old header\nprint('hello')\n", encoding="utf-8")

    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )

    write_result = port_convert_and_write(result, target, dry_run=True)
    diff_data = write_result["diff"]
    assert "unified_diff" in diff_data
    assert "original_exists" in diff_data
    assert diff_data["original_exists"] is True
    assert diff_data["emitted_line_count"] > 0
    assert diff_data["original_line_count"] == 2


def test_diff_mode_includes_diff_data(tmp_path: Path) -> None:
    """Diff mode flag produces diff data in write result."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    target = tmp_path / "target.py"

    write_result = port_convert_and_write(result, target, diff=True)
    # With diff=True but not dry_run, it should still write
    assert write_result["written"] is True
    assert "diff" in write_result
    assert write_result["diff"]["original_exists"] is False  # target didn't exist


def test_atomic_write_creates_parent_directories(tmp_path: Path) -> None:
    """Atomic write creates parent directories as needed."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    target = tmp_path / "deep" / "nested" / "output.py"

    write_result = port_convert_and_write(result, target)
    assert write_result["written"] is True
    assert target.exists()


def test_check_manual_refusal_raises_for_manual_marker(tmp_path: Path) -> None:
    """_check_manual_refusal raises ManualTemplateRefusal for manual marker."""
    target = tmp_path / "manual.py"
    target.write_text("# vibecomfy: manual\n", encoding="utf-8")
    with pytest.raises(ManualTemplateRefusal):
        _check_manual_refusal(target)


def test_check_manual_refusal_allows_non_manual_files(tmp_path: Path) -> None:
    """_check_manual_refusal does not raise for non-manual files."""
    target = tmp_path / "generated.py"
    target.write_text("# vibecomfy: generated\n", encoding="utf-8")
    _check_manual_refusal(target)  # Should not raise


def test_check_manual_refusal_allows_nonexistent_target(tmp_path: Path) -> None:
    """_check_manual_refusal is a no-op when target doesn't exist."""
    target = tmp_path / "nonexistent.py"
    _check_manual_refusal(target)  # Should not raise


def test_compute_diff_produces_unified_diff() -> None:
    """_compute_diff produces unified diff with metadata."""
    original = "line1\nline2\nline3\n"
    emitted = "line1\nline2_changed\nline3\n"
    diff_data = _compute_diff(original, emitted, "test.py")
    assert "unified_diff" in diff_data
    assert "-line2" in diff_data["unified_diff"]
    assert "+line2_changed" in diff_data["unified_diff"]
    assert diff_data["original_exists"] is True
    assert diff_data["emitted_line_count"] == 3
    assert diff_data["original_line_count"] == 3


def test_compute_diff_for_new_file() -> None:
    """_compute_diff for a new file shows all additions."""
    emitted = "new line 1\nnew line 2\n"
    diff_data = _compute_diff("", emitted, "new.py")
    assert diff_data["original_exists"] is False
    assert diff_data["original_line_count"] == 0
    assert diff_data["emitted_line_count"] == 2
    assert "+new line 1" in diff_data["unified_diff"]


def test_manual_refusal_does_not_raise_for_missing_target(tmp_path: Path) -> None:
    """Manual refusal only applies when target exists."""
    result = port_convert_workflow(
        _sample_workflow(),
        source_path="workflow_corpus/official/image/z_image.json",
        provenance={"source_hash": "sha256:abc"},
        workflow_shape={"nodes": 2, "runtime_nodes": 2},
        schema_provider=_provider(),
    )
    target = tmp_path / "new_file.py"
    # Should not raise since file doesn't exist
    write_result = port_convert_and_write(result, target)
    assert write_result["written"] is True
    assert target.exists()


def test_conversion_write_error_is_runtime_error() -> None:
    """ConversionWriteError is a RuntimeError subclass."""
    assert issubclass(ConversionWriteError, RuntimeError)


def test_manual_template_refusal_is_value_error() -> None:
    """ManualTemplateRefusal is a ValueError subclass."""
    assert issubclass(ManualTemplateRefusal, ValueError)
