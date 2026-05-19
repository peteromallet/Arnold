from __future__ import annotations

import warnings

import pytest

import vibecomfy.templates as templates
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, _derive_output_kind, finalize, new_workflow, node
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


def _workflow(workflow_id: str = "test/workflow") -> VibeWorkflow:
    return VibeWorkflow(
        workflow_id,
        WorkflowSource(workflow_id, path="ready_templates/test_workflow.py", source_type="ready_template"),
    )


def _force_id(wf: VibeWorkflow, builder, node_id: str):
    old_id = builder.node.id
    builder.node.id = node_id
    wf.nodes[node_id] = wf.nodes.pop(old_id)
    for edge in wf.edges:
        if edge.from_node == old_id:
            edge.from_node = node_id
        if edge.to_node == old_id:
            edge.to_node = node_id
    return builder


def test_node_preserves_source_id_extras_and_rewrites_edges() -> None:
    wf = _workflow()
    source = node(wf, "LoadImage", "source", image="input.png")
    consumer = node(
        wf,
        "ImageScaleToTotalPixels",
        "scaled",
        _extras={"image": source.out(0), "resize_type.multiple": "area"},
        megapixels=1.0,
    )

    assert source.node.id == "source"
    assert consumer.node.id == "scaled"
    assert wf.nodes["scaled"].inputs["resize_type.multiple"] == "area"
    assert any(edge.from_node == "source" and edge.to_node == "scaled" and edge.to_input == "image" for edge in wf.edges)


def test_new_workflow_constructs_ready_workflow_with_metadata() -> None:
    metadata = {
        "ready_template": "image/example",
        "capability": "text_to_image",
        "provenance": {"source": "unit"},
    }

    wf = new_workflow(metadata, source_path="ready_templates/image/example.py")

    assert wf.id == "image/example"
    assert wf.source.path == "ready_templates/image/example.py"
    assert wf.source.source_type == "ready_template"
    assert wf.source.provenance == {"source": "unit"}
    assert wf.metadata["capability"] == "text_to_image"


def test_input_spec_register_preserves_current_value_and_declared_default() -> None:
    wf = _workflow()
    _force_id(wf, wf.node("PrimitiveFloat", value=0.8), "10")

    InputSpec(
        node="10",
        field="value",
        default=0.5,
        type="FLOAT",
        required=True,
        aliases=("strength",),
        media_semantics="control",
    ).register(wf, "control_strength")

    registered = wf.inputs["control_strength"]
    assert registered.value == 0.8
    assert registered.default == 0.5
    assert registered.type == "FLOAT"
    assert registered.required is True
    assert registered.aliases == ("strength",)
    assert registered.media_semantics == "control"


def test_ready_metadata_build_serializes_inputs_models_and_filters_none_extras() -> None:
    inputs = {
        "prompt": InputSpec("1", "text", "a prompt", "STRING", description="Prompt text."),
        "image": InputSpec("2", "image", "input.png", "IMAGE", media_semantics="image"),
    }
    models = {
        "main": ModelAsset(
            filename="model.safetensors",
            url="https://example.test/model.safetensors",
            subdir="checkpoints",
        ),
        "aux": ModelAsset(
            filename="aux.safetensors",
            url="https://example.test/aux.safetensors",
            subdir="loras",
            target_path="custom_nodes/pack/aux.safetensors",
        ),
    }

    metadata = ReadyMetadata.build(
        template_id="edit/example",
        capability="image_edit",
        inputs=inputs,
        models=models,
        output_prefix="out/example",
        coverage_tier="required",
        runtime_note=None,
    )

    assert metadata["ready_template"] == "edit/example"
    assert metadata["workflow_template"] == "example"
    assert metadata["capability"] == "image_edit"
    assert metadata["output_prefix"] == "out/example"
    assert metadata["unbound_inputs"] == {"prompt": "a prompt", "image": "input.png"}
    assert metadata["model_assets"] == [
        {
            "name": "model.safetensors",
            "url": "https://example.test/model.safetensors",
            "subdir": "checkpoints",
        },
        {
            "name": "aux.safetensors",
            "url": "https://example.test/aux.safetensors",
            "subdir": "loras",
            "target_path": "custom_nodes/pack/aux.safetensors",
        },
    ]
    assert metadata["edit_guide"] == "Public inputs:\n- prompt: Prompt text.\n- image: Controls image."
    assert metadata["requirements"]["models"] == metadata["model_assets"]
    assert metadata["coverage_tier"] == "required"
    assert "runtime_note" not in metadata


def test_ready_metadata_build_appends_edit_guide_extra_and_warns_once_on_model_disagreement() -> None:
    templates._MODEL_DISAGREEMENT_WARNED = False
    models = {
        "main": ModelAsset(
            filename="model.safetensors",
            url="https://example.test/model.safetensors",
            subdir="checkpoints",
        )
    }

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        metadata = ReadyMetadata.build(
            template_id="image/example",
            capability="text_to_image",
            inputs={"prompt": InputSpec("1", "text", "hello", "STRING", description="Text prompt.")},
            models=models,
            output_prefix="out/example",
            edit_guide_extra="Use short prompts for smoke tests.",
            requirements={"models": [{"name": "different.safetensors", "url": "", "subdir": "checkpoints"}]},
        )
        ReadyMetadata.build(
            template_id="image/example2",
            capability="text_to_image",
            inputs={},
            models=models,
            output_prefix="out/example2",
            requirements={"models": [{"name": "another.safetensors", "url": "", "subdir": "checkpoints"}]},
        )

    assert metadata["edit_guide"] == "Public inputs:\n- prompt: Text prompt.\nUse short prompts for smoke tests."
    assert metadata["requirements"]["models"] == [{"name": "different.safetensors", "url": "", "subdir": "checkpoints"}]
    assert len(caught) == 1
    assert "differs from MODELS-derived" in str(caught[0].message)


def test_finalize_preserves_source_requirements_and_image_output_contract() -> None:
    wf = _workflow("image/example")
    _force_id(wf, wf.node("CLIPTextEncode", text="current prompt"), "1")
    _force_id(wf, wf.node("RandomNoise", noise_seed=999, control_after_generate="fixed"), "2")
    _force_id(wf, wf.node("SaveImage", filename_prefix="out/example"), "3")
    inputs = {
        "prompt": InputSpec("1", "text", "default prompt", "STRING", required=True),
        "seed": InputSpec("2", "noise_seed", 123, "INT"),
    }
    metadata = ReadyMetadata.build(
        template_id="image/example",
        capability="text_to_image",
        inputs=inputs,
        models={
            "main": ModelAsset(
                "model.safetensors",
                "https://example.test/model.safetensors",
                "checkpoints",
            )
        },
        output_prefix="out/example",
    )

    finalize(
        wf,
        inputs,
        metadata,
        output_node="3",
        output_kind="image",
        output_type="SaveImage",
        name="image",
        mime_type="image/png",
        filename_prefix="out/example",
        expected_cardinality="one",
        source_path="ready_templates/image/example.py",
        requirements={"models": metadata["model_assets"], "custom_nodes": ["ExamplePack"]},
    )

    assert wf.metadata["ready_template_path"] == "ready_templates/image/example.py"
    assert wf.metadata["python_policy_applied"] is True
    assert wf.inputs["prompt"].value == "current prompt"
    assert wf.inputs["prompt"].default == "default prompt"
    assert wf.inputs["seed"].value == 999
    assert wf.inputs["seed"].default == 123
    assert "model.safetensors" in wf.requirements.models
    assert "ExamplePack" in wf.requirements.custom_nodes
    output = next(item for item in wf.outputs if item.node_id == "3")
    assert output.output_type == "SaveImage"
    assert output.name == "image"
    assert output.artifact_kind == "image"
    assert output.mime_type == "image/png"
    assert output.filename_prefix == "out/example"
    assert output.expected_cardinality == "one"


@pytest.mark.parametrize(
    ("kind", "output_type", "name", "mime_type"),
    [
        ("video", "SaveVideo", "video", "video/mp4"),
        ("video", "VHS_VideoCombine", "video", "video/mp4"),
        ("audio", "SaveAudioMP3", "audio", "audio/mpeg"),
        ("image", "SaveImage", "image", "image/png"),
    ],
)
def test_finalize_binds_output_contracts_across_artifact_kinds_without_output_kind(
    kind: str,
    output_type: str,
    name: str,
    mime_type: str,
) -> None:
    wf = _workflow(f"{kind}/example")
    _force_id(wf, wf.node("PrimitiveString", value="hello"), "1")
    _force_id(wf, wf.node(output_type, filename_prefix=f"{kind}/out"), "2")
    inputs = {"prompt": InputSpec("1", "value", "hello", "STRING")}
    metadata = ReadyMetadata.build(
        template_id=f"{kind}/example",
        capability=f"{kind}_capability",
        inputs=inputs,
        models={},
        output_prefix=f"{kind}/out",
    )

    finalize(
        wf,
        inputs,
        metadata,
        output_node="2",
        output_type=output_type,
        name=name,
        mime_type=mime_type,
        filename_prefix=f"{kind}/out",
        expected_cardinality="one",
    )

    output = next(item for item in wf.outputs if item.node_id == "2")
    assert output.artifact_kind == kind
    assert output.output_type == output_type
    assert output.name == name
    assert output.mime_type == mime_type


@pytest.mark.parametrize(
    ("class_type", "expected"),
    [
        ("VHS_VideoCombine", "video"),
        ("CreateVideo", "video"),
        ("SaveVideo", "video"),
        ("SaveAudioMP3", "audio"),
        ("PreviewAudio", "audio"),
        ("SaveImage", "image"),
        ("PreviewImage", "image"),
        ("Unknown", None),
    ],
)
def test_derive_output_kind(class_type: str, expected: str | None) -> None:
    assert _derive_output_kind(class_type) == expected


def test_finalize_derives_model_requirements_from_metadata_when_requirements_empty() -> None:
    wf = _workflow("image/example")
    _force_id(wf, wf.node("PrimitiveString", value="hello"), "1")
    _force_id(wf, wf.node("SaveImage", filename_prefix="out"), "2")
    inputs = {"prompt": InputSpec("1", "value", "hello", "STRING")}
    metadata = ReadyMetadata.build(
        template_id="image/example",
        capability="text_to_image",
        inputs=inputs,
        models={
            "main": ModelAsset(
                filename="model.safetensors",
                url="https://example.test/model.safetensors",
                subdir="checkpoints",
            )
        },
        output_prefix="out",
    )

    finalize(wf, inputs, metadata, output_node="2", output_type="SaveImage", requirements={})

    assert "model.safetensors" in wf.requirements.models


def test_finalize_preserves_edit_style_image_input_defaults() -> None:
    wf = _workflow("edit/example")
    _force_id(wf, wf.node("LoadImage", image="current.png"), "10")
    _force_id(wf, wf.node("TextEncodeQwenImageEdit", prompt="remove text"), "11")
    _force_id(wf, wf.node("SaveImage", filename_prefix="edit/out"), "12")
    inputs = {
        "image": InputSpec(
            "10",
            "image",
            "default.png",
            "IMAGE",
            required=True,
            aliases=("input_image",),
            media_semantics="image",
        ),
        "prompt": InputSpec("11", "prompt", "remove text", "STRING", required=True),
    }
    metadata = ReadyMetadata.build(
        template_id="edit/example",
        capability="image_edit",
        inputs=inputs,
        models={},
        output_prefix="edit/out",
    )

    finalize(
        wf,
        inputs,
        metadata,
        output_node="12",
        output_kind="image",
        output_type="SaveImage",
        name="image",
    )

    image = wf.inputs["image"]
    assert image.value == "current.png"
    assert image.default == "default.png"
    assert image.type == "IMAGE"
    assert image.aliases == ("input_image",)
    assert image.media_semantics == "image"


def test_finalize_allows_unrelated_auto_inputs_but_rejects_public_target_drift() -> None:
    wf = _workflow("image/example")
    _force_id(wf, wf.node("CLIPTextEncode", text="auto prompt"), "1")
    _force_id(wf, wf.node("RandomNoise", noise_seed=5, control_after_generate="fixed"), "2")
    _force_id(wf, wf.node("PrimitiveString", value="declared"), "3")
    _force_id(wf, wf.node("SaveImage", filename_prefix="out"), "4")
    inputs = {"custom": InputSpec("3", "value", "declared", "STRING")}
    metadata = ReadyMetadata.build(
        template_id="image/example",
        capability="text_to_image",
        inputs=inputs,
        models={},
        output_prefix="out",
    )

    finalize(wf, inputs, metadata, output_node="4", output_kind="image", output_type="SaveImage")

    assert "prompt" in wf.inputs
    assert "seed" in wf.inputs
    assert wf.inputs["custom"].node_id == "3"

    drifted = _workflow("image/drift")
    _force_id(drifted, drifted.node("CLIPTextEncode", text="declared"), "3")
    _force_id(drifted, drifted.node("SaveImage", filename_prefix="out"), "4")
    drift_inputs = {"custom_prompt": InputSpec("3", "text", "declared", "STRING")}
    drift_metadata = ReadyMetadata.build(
        template_id="image/drift",
        capability="text_to_image",
        inputs=drift_inputs,
        models={},
        output_prefix="out",
    )

    with pytest.raises(AssertionError, match="not declared"):
        finalize(
            drifted,
            drift_inputs,
            drift_metadata,
            output_node="4",
            output_kind="image",
            output_type="SaveImage",
        )
