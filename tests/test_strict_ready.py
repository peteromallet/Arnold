from __future__ import annotations

import json

from vibecomfy.porting.strict_ready import (
    HIDDEN_MODEL_FILENAME,
    OPAQUE_COMPONENT_NODE_CLASS,
    STRICT_READY_BROKEN_PUBLIC_INPUT,
    STRICT_READY_MISSING_OUTPUT_CONTRACT,
    STRICT_READY_MISSING_PUBLIC_INPUT,
    STRICT_READY_UNNAMED_OUTPUT_CONTRACT,
    STRICT_READY_UNRESOLVED_WIDGETS,
    StrictReadyContext,
    load_strict_ready_exceptions,
    validate_strict_ready_workflow,
)
from vibecomfy.workflow import VibeInput, VibeOutput, VibeWorkflow, WorkflowSource


def _workflow() -> VibeWorkflow:
    return VibeWorkflow("image/test", WorkflowSource(id="image/test", source_type="ready_template"))


def _minimal_ready_workflow() -> VibeWorkflow:
    wf = _workflow()
    wf.add_node("SaveImage", images=["1", 0], filename_prefix="strict-ready")
    wf.register_input("filename_prefix", "1", "filename_prefix")
    wf.outputs.append(VibeOutput(node_id="1", output_type="IMAGE", name="image"))
    return wf


def _codes(wf: VibeWorkflow, **kwargs: object) -> set[str]:
    return {issue.code for issue in validate_strict_ready_workflow(wf, **kwargs)}


def test_strict_ready_requires_public_inputs() -> None:
    wf = _workflow()
    wf.add_node("SaveImage", filename_prefix="x")
    wf.outputs.append(VibeOutput(node_id="1", output_type="IMAGE", name="image"))

    assert STRICT_READY_MISSING_PUBLIC_INPUT in _codes(wf)


def test_strict_ready_requires_valid_public_input_targets() -> None:
    wf = _minimal_ready_workflow()
    wf.inputs["broken"] = VibeInput(name="broken", node_id="404", field="prompt")
    wf.inputs["missing_field"] = VibeInput(name="missing_field", node_id="1", field="prompt")

    issues = validate_strict_ready_workflow(wf)
    broken = [issue for issue in issues if issue.code == STRICT_READY_BROKEN_PUBLIC_INPUT]

    assert [issue.detail["target"] for issue in broken] == ["input:broken", "input:missing_field"]


def test_strict_ready_requires_public_outputs() -> None:
    wf = _workflow()
    wf.add_node("KSampler", seed=1)
    wf.register_input("seed", "1", "seed")

    assert STRICT_READY_MISSING_OUTPUT_CONTRACT in _codes(wf)


def test_strict_ready_requires_named_public_outputs() -> None:
    wf = _workflow()
    wf.add_node("SaveImage", filename_prefix="x")
    wf.register_input("filename_prefix", "1", "filename_prefix")
    wf.outputs.append(VibeOutput(node_id="1", output_type="IMAGE"))

    issues = validate_strict_ready_workflow(wf)

    assert any(
        issue.code == STRICT_READY_UNNAMED_OUTPUT_CONTRACT and issue.detail["target"] == "output:0"
        for issue in issues
    )


def test_strict_ready_rejects_opaque_uuid_component_classes() -> None:
    wf = _minimal_ready_workflow()
    wf.add_node("7d70f9c4-1f7b-4c72-99e8-73eeac46a304")

    issues = validate_strict_ready_workflow(wf)

    assert any(
        issue.code == OPAQUE_COMPONENT_NODE_CLASS and issue.detail["target"] == "node:2"
        for issue in issues
    )


def test_strict_ready_rejects_schema_backed_unresolved_widgets() -> None:
    wf = _minimal_ready_workflow()
    widget_analysis = {
        "unresolved_widget_aliases": [
            {"node_id": "1", "class_type": "KnownNode", "input": "widget_0"},
            {"node_id": "2", "class_type": "UnknownNode", "input": "widget_0"},
        ],
        "suggestions": [
            {"class_type": "KnownNode", "schema_source": "schema_provider", "suggested_schema_entry": ["prompt"]},
            {"class_type": "UnknownNode", "schema_source": "unavailable", "suggested_schema_entry": None},
        ],
    }

    issues = validate_strict_ready_workflow(wf, widget_analysis=widget_analysis)

    assert [
        issue.detail["target"]
        for issue in issues
        if issue.code == STRICT_READY_UNRESOLVED_WIDGETS
    ] == ["node:1.widget_0"]


def test_strict_ready_rejects_hidden_model_filenames() -> None:
    wf = _minimal_ready_workflow()
    api_prompt = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"widget_0": "model.safetensors", "other": "value"},
        }
    }

    issues = validate_strict_ready_workflow(wf, api_prompt=api_prompt)

    assert any(
        issue.code == HIDDEN_MODEL_FILENAME
        and issue.severity == "error"
        and issue.detail["target"] == "node:1.widget_0"
        for issue in issues
    )


def test_strict_ready_exceptions_match_exact_ready_code_and_target(tmp_path) -> None:
    exceptions_path = tmp_path / "strict_ready_exceptions.json"
    exceptions_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "match_keys": ["ready_id", "violation_code", "target"],
                "exceptions": [
                    {
                        "id": "sre-test-001",
                        "ready_id": "image/test",
                        "violation_code": HIDDEN_MODEL_FILENAME,
                        "target": "node:1.widget_0",
                        "owner": "workflow-porting",
                        "ticket": "TEST-1",
                        "reason": "test fixture",
                        "allowed_until": "2026-06-01",
                        "removal_condition": "test removed",
                        "final_category": "blocked",
                    }
                ],
            }
        )
    )
    exceptions = load_strict_ready_exceptions(exceptions_path)
    wf = _minimal_ready_workflow()
    api_prompt = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"widget_0": "model.safetensors", "widget_1": "other.safetensors"},
        }
    }

    issues = validate_strict_ready_workflow(
        wf,
        StrictReadyContext(
            ready_id="image/test",
            exceptions=exceptions,
        ),
        api_prompt=api_prompt,
    )
    hidden = [issue for issue in issues if issue.code == HIDDEN_MODEL_FILENAME]

    assert [(issue.detail["target"], issue.severity) for issue in hidden] == [
        ("node:1.widget_0", "info"),
        ("node:1.widget_1", "error"),
    ]
    assert hidden[0].detail["exception_id"] == "sre-test-001"
