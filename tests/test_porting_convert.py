from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from vibecomfy.commands.convert import _cmd_convert
from vibecomfy.porting.convert import port_convert_workflow
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


def test_legacy_vibecomfy_convert_still_renders_loader_scratchpad(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(json.dumps({"nodes": []}), encoding="utf-8")
    out = tmp_path / "scratch.py"

    assert _cmd_convert(argparse.Namespace(workflow=str(workflow_path), out=str(out))) == 0

    text = out.read_text(encoding="utf-8")
    assert "from vibecomfy import workflow_from_file, run" in text
    assert "workflow = workflow_from_file(" in text
    assert "READY_METADATA" not in text
