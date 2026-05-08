from __future__ import annotations

import subprocess
import sys

from vibecomfy.porting.emitter import emit_ready_template_python, emit_scratchpad_python
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource
from tools.format_as_python import format_as_python


def _sample_workflow() -> VibeWorkflow:
    workflow = VibeWorkflow("sample", WorkflowSource("sample", provenance={"origin": "unit"}))
    workflow.nodes["10"] = VibeNode("10", "LoadImage", inputs={"image": "input.png"})
    workflow.nodes["20"] = VibeNode(
        "20",
        "SaveImage",
        inputs={"filename_prefix": "out/sample", "resize_type.multiple": 3},
    )
    workflow.connect("10.0", "20.images")
    workflow.register_input("prefix", "20", "filename_prefix", "out/sample")
    return workflow


def test_emit_scratchpad_python_preserves_ids_extras_inputs_and_provenance() -> None:
    text = emit_scratchpad_python(
        _sample_workflow(),
        workflow_id="scratch/sample",
        source_path="workflow_corpus/source.json",
        provenance={"source_hash": "sha256:abc"},
        registered_inputs={"prefix": ("20", "filename_prefix")},
    )

    assert "READY_METADATA" not in text
    assert "source_type='scratchpad'" in text
    assert "provenance={'source_hash': 'sha256:abc'}" in text
    assert "_extras={'resize_type.multiple': 3}" in text

    namespace: dict[str, object] = {"__file__": "out/scratchpads/sample.py"}
    exec(compile(text, "scratch emitted", "exec"), namespace)  # noqa: S102 - generated code under test
    workflow = namespace["build"]()

    assert isinstance(workflow, VibeWorkflow)
    assert workflow.id == "scratch/sample"
    assert workflow.source.source_type == "scratchpad"
    assert workflow.source.path == "workflow_corpus/source.json"
    assert workflow.source.provenance == {"source_hash": "sha256:abc"}
    assert sorted(workflow.nodes) == ["10", "20"]
    assert workflow.nodes["20"].inputs["resize_type.multiple"] == 3
    assert workflow.inputs["prefix"].node_id == "20"
    assert workflow.compile("api")["20"]["inputs"]["images"] == ["10", 0]


def test_emit_ready_template_python_has_ready_metadata_contract() -> None:
    text = emit_ready_template_python(
        _sample_workflow(),
        ready_metadata={"ready_template": "image/sample", "source_workflow": "workflow_corpus/source.json"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="image/sample",
        registered_inputs={"prefix": ("20", "filename_prefix")},
    )

    assert "READY_METADATA =" in text
    assert "READY_REQUIREMENTS =" in text
    assert 'READY_METADATA["ready_template"]' in text
    assert "source_type='ready_template'" in text

    namespace: dict[str, object] = {"__file__": "ready_templates/image/sample.py"}
    exec(compile(text, "ready emitted", "exec"), namespace)  # noqa: S102 - generated code under test
    workflow = namespace["build"]()

    assert isinstance(workflow, VibeWorkflow)
    assert workflow.id == "image/sample"
    assert workflow.source.source_type == "ready_template"
    assert sorted(workflow.nodes) == ["10", "20"]
    assert workflow.metadata["ready_template"] == "image/sample"
    assert workflow.inputs["prefix"].node_id == "20"


def test_tools_format_as_python_remains_ready_template_wrapper() -> None:
    kwargs = {
        "ready_metadata": {"ready_template": "image/sample", "source_workflow": "workflow_corpus/source.json"},
        "ready_requirements": {"models": [], "custom_nodes": []},
        "template_id": "image/sample",
        "registered_inputs": {"prefix": ("20", "filename_prefix")},
    }

    assert format_as_python(_sample_workflow(), **kwargs) == emit_ready_template_python(_sample_workflow(), **kwargs)


def test_convert_ready_templates_tool_dry_run_remains_compatible() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.convert_ready_templates",
            "--template",
            "image/qwen_image_2512",
            "--dry-run",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "image/qwen_image_2512" in result.stdout
