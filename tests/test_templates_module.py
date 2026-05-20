from __future__ import annotations

import warnings
from pathlib import Path

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
            sha256="0" * 64,
            hf_revision="abc123",
            size_bytes=123,
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
            "sha256": "0" * 64,
            "hf_revision": "abc123",
            "size_bytes": 123,
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


def test_finalize_merges_metadata_custom_nodes_into_wf_requirements() -> None:
    """T4(a): custom-node requirements in READY_METADATA reach wf.requirements.custom_nodes."""
    wf = _workflow("image/example")
    _force_id(wf, wf.node("PrimitiveString", value="hello"), "1")
    _force_id(wf, wf.node("SaveImage"), "2")
    inputs = {"prompt": InputSpec("1", "value", "hello", "STRING")}
    metadata = ReadyMetadata.build(
        template_id="image/example",
        capability="text_to_image",
        inputs=inputs,
        models={},
        output_prefix="out",
        requirements={"custom_nodes": ["PackA", "PackB"]},
    )

    # Call finalize WITHOUT explicit requirements= — metadata requirements should flow through.
    finalize(wf, inputs, metadata, output_node="2", output_kind="image", output_type="SaveImage")

    assert "PackA" in wf.requirements.custom_nodes
    assert "PackB" in wf.requirements.custom_nodes


def test_finalize_unions_custom_nodes_from_both_sources() -> None:
    """T4(a): union custom_nodes lists from explicit requirements and metadata deterministically."""
    wf = _workflow("image/example")
    _force_id(wf, wf.node("PrimitiveString", value="hello"), "1")
    _force_id(wf, wf.node("SaveImage"), "2")
    inputs = {"prompt": InputSpec("1", "value", "hello", "STRING")}
    metadata = ReadyMetadata.build(
        template_id="image/example",
        capability="text_to_image",
        inputs=inputs,
        models={},
        output_prefix="out",
        requirements={"custom_nodes": ["PackA", "PackC"]},
    )

    # Call finalize WITH explicit requirements that overlap.
    finalize(
        wf,
        inputs,
        metadata,
        output_node="2",
        output_kind="image",
        output_type="SaveImage",
        requirements={"custom_nodes": ["PackB", "PackC"]},
    )

    custom = wf.requirements.custom_nodes
    assert "PackA" in custom
    assert "PackB" in custom
    assert "PackC" in custom
    # Deterministic ordering: sorted.
    assert custom == sorted(custom)


def test_finalize_uses_metadata_output_prefix_as_filename_fallback() -> None:
    """T4(b): metadata output_prefix reaches finalized output when filename_prefix omitted."""
    wf = _workflow("image/example")
    _force_id(wf, wf.node("PrimitiveString", value="hello"), "1")
    _force_id(wf, wf.node("SaveImage"), "2")
    inputs = {"prompt": InputSpec("1", "value", "hello", "STRING")}
    metadata = ReadyMetadata.build(
        template_id="image/example",
        capability="text_to_image",
        inputs=inputs,
        models={},
        output_prefix="video/ComfyUI",
    )

    # Call finalize WITHOUT filename_prefix — should fall back to metadata output_prefix.
    finalize(wf, inputs, metadata, output_node="2", output_kind="image", output_type="SaveImage")

    output = next(item for item in wf.outputs if item.node_id == "2")
    assert output.filename_prefix == "video/ComfyUI"


def test_finalize_explicit_filename_prefix_overrides_metadata_output_prefix() -> None:
    """T4(c): explicit filename_prefix still wins over metadata output_prefix."""
    wf = _workflow("image/example")
    _force_id(wf, wf.node("PrimitiveString", value="hello"), "1")
    _force_id(wf, wf.node("SaveImage"), "2")
    inputs = {"prompt": InputSpec("1", "value", "hello", "STRING")}
    metadata = ReadyMetadata.build(
        template_id="image/example",
        capability="text_to_image",
        inputs=inputs,
        models={},
        output_prefix="video/ComfyUI",
    )

    finalize(
        wf,
        inputs,
        metadata,
        output_node="2",
        output_kind="image",
        output_type="SaveImage",
        filename_prefix="custom/prefix",
    )

    output = next(item for item in wf.outputs if item.node_id == "2")
    assert output.filename_prefix == "custom/prefix"


# ── T19: PendingDeprecationWarning tests ──


def test_legacy_bind_input_still_works_and_warns() -> None:
    """T19: bind_input still works but emits PendingDeprecationWarning."""
    from vibecomfy.registry.ready_template import bind_input

    wf = _workflow("test/legacy")
    _force_id(wf, wf.node("PrimitiveString", value="hello"), "1")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = bind_input(wf, "text", "1", "value", type="STRING")

    assert result is wf
    assert wf.inputs["text"].value == "hello"
    assert len(caught) >= 1
    assert any("bind_input is deprecated" in str(w.message) for w in caught)
    assert all(issubclass(w.category, PendingDeprecationWarning) for w in caught)


def test_legacy_bind_output_still_works_and_warns() -> None:
    """T19: bind_output still works but emits PendingDeprecationWarning."""
    from vibecomfy.registry.ready_template import bind_output

    wf = _workflow("test/legacy")
    _force_id(wf, wf.node("SaveImage", filename_prefix="out"), "10")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = bind_output(wf, "10", output_type="SaveImage", name="image")

    assert result is wf
    assert wf.outputs[0].name == "image"
    assert len(caught) >= 1
    assert any("bind_output is deprecated" in str(w.message) for w in caught)
    assert all(issubclass(w.category, PendingDeprecationWarning) for w in caught)


def test_legacy_apply_ready_template_policy_still_works_and_warns() -> None:
    """T19: apply_ready_template_policy still works but emits PendingDeprecationWarning."""
    from vibecomfy.registry.ready_template import apply_ready_template_policy

    wf = _workflow("test/legacy")
    _force_id(wf, wf.node("PrimitiveString", value="hello"), "1")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        apply_ready_template_policy(wf, {"ready_template": "test"}, source_path="test.py")

    assert wf.metadata["python_policy_applied"] is True
    assert len(caught) >= 1
    assert any("apply_ready_template_policy is deprecated" in str(w.message) for w in caught)
    assert all(issubclass(w.category, PendingDeprecationWarning) for w in caught)


def test_canonical_finalize_does_not_warn() -> None:
    """T19: Canonical finalize() path suppresses PendingDeprecationWarning."""
    wf = _workflow("image/example")
    _force_id(wf, wf.node("PrimitiveString", value="hello"), "1")
    _force_id(wf, wf.node("SaveImage"), "2")
    inputs = {"prompt": InputSpec("1", "value", "hello", "STRING")}
    metadata = ReadyMetadata.build(
        template_id="image/example",
        capability="text_to_image",
        inputs=inputs,
        models={},
        output_prefix="out",
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        finalize(wf, inputs, metadata, output_node="2", output_kind="image", output_type="SaveImage")

    deprecation_warnings = [w for w in caught if issubclass(w.category, PendingDeprecationWarning)]
    assert len(deprecation_warnings) == 0, f"Unexpected PendingDeprecationWarning: {deprecation_warnings}"


# ── T5: Regression tests for four-block template static consumers ──


def test_static_contract_extracts_public_inputs_from_inputspec() -> None:
    """T5(b): static_contract derives public_inputs from PUBLIC_INPUTS/InputSpec AST nodes."""
    from vibecomfy.registry.static_contract import extract_ready_template_contract

    # wan_i2v.py has PUBLIC_INPUTS with InputSpec nodes
    contract = extract_ready_template_contract(
        Path(__file__).resolve().parents[1] / "ready_templates" / "video" / "wan_i2v.py"
    )

    public_input_names = {item["name"] for item in contract["public_inputs"]}
    expected = {"prompt", "negative_prompt", "seed", "steps", "output_fps", "width", "height", "length", "cfg", "sampler_name", "start_image"}
    for name in expected:
        assert name in public_input_names, f"Missing public input: {name}"


def test_static_contract_extracts_public_outputs_from_finalize() -> None:
    """T5(b): static_contract derives public_outputs from finalize(..., output_node=...) call."""
    from vibecomfy.registry.static_contract import extract_ready_template_contract

    contract = extract_ready_template_contract(
        Path(__file__).resolve().parents[1] / "ready_templates" / "video" / "wan_i2v.py"
    )

    # Should find at least one output from finalize call
    finalize_outputs = [item for item in contract["public_outputs"] if item.get("source") == "finalize"]
    assert len(finalize_outputs) > 0, "No outputs extracted from finalize()"
    output = finalize_outputs[0]
    assert output["node_id"] == "56"
    assert output.get("output_type") == "SaveVideo"


def test_static_contract_preserves_model_asset_reproducibility_pins(tmp_path: Path) -> None:
    from vibecomfy.registry.static_contract import extract_ready_template_contract

    source = tmp_path / "template.py"
    source.write_text(
        """
from vibecomfy.templates import ModelAsset, ReadyMetadata

MODELS = {
    "main": ModelAsset(
        filename="model.safetensors",
        url="https://example.test/model.safetensors",
        subdir="checkpoints",
        sha256="abc",
        hf_revision="rev1",
        size_bytes=42,
    )
}
READY_METADATA = ReadyMetadata.build(
    template_id="image/example",
    capability="test",
    inputs={},
    models=MODELS,
    output_prefix="out/example",
)
""",
        encoding="utf-8",
    )

    contract = extract_ready_template_contract(source)

    assert contract["model_assets"] == [
        {
            "name": "model.safetensors",
            "filename": "model.safetensors",
            "url": "https://example.test/model.safetensors",
            "subdir": "checkpoints",
            "sha256": "abc",
            "hf_revision": "rev1",
            "size_bytes": 42,
        }
    ]


def test_ready_template_metadata_handles_ready_metadata_build_call() -> None:
    """T5(a): _ready_template_metadata handles ReadyMetadata.build(...) call expressions."""
    from tools.refresh_template_index import _ready_template_metadata

    metadata, requirements = _ready_template_metadata(
        Path(__file__).resolve().parents[1] / "ready_templates" / "video" / "wan_i2v.py"
    )

    assert isinstance(metadata, dict)
    assert metadata.get("capability") == "image_to_video"
    assert metadata.get("coverage_tier") == "required"
    assert metadata.get("output_prefix") == "video/ComfyUI"


def test_readability_inventory_parses_ready_metadata_build_call() -> None:
    """T5(c): _parse_ready_metadata handles ReadyMetadata.build(...) call expressions."""
    from vibecomfy.porting.readability_inventory import _parse_ready_metadata

    metadata, requirements = _parse_ready_metadata(
        Path(__file__).resolve().parents[1] / "ready_templates" / "video" / "wan_i2v.py"
    )

    assert isinstance(metadata, dict)
    assert metadata.get("capability") == "image_to_video"
    assert metadata.get("coverage_tier") == "required"
