from __future__ import annotations

import json

from vibecomfy.contracts import build_contract, doctor_contract
from vibecomfy.contracts.model import WorkflowRuntimeContract
from vibecomfy.registry.ready import workflow_from_ready
from vibecomfy.workflow import VibeNode, VibeOutput, VibeWorkflow, WorkflowSource


def _synthetic_workflow(**metadata: object) -> VibeWorkflow:
    """Create a minimal synthetic VibeWorkflow for contract testing."""
    workflow = VibeWorkflow(
        id="test/synthetic",
        source=WorkflowSource(id="test/synthetic"),
    )
    for key, value in metadata.items():
        workflow.metadata[key] = value
    return workflow


def _synthetic_ltx_workflow(
    *class_types: str,
    sage_attention: str | None = "auto",
    runtime_packages: list[dict] | None = None,
) -> VibeWorkflow:
    """Create a synthetic LTX-style workflow with specific node class_types."""
    workflow = VibeWorkflow(
        id="test/synthetic_ltx",
        source=WorkflowSource(id="test/synthetic_ltx"),
    )
    for class_type in class_types:
        node = workflow.add_node(class_type)
        if class_type == "PathchSageAttentionKJ" and sage_attention is not None:
            node.inputs["sage_attention"] = sage_attention
    if runtime_packages is not None:
        workflow.metadata["runtime_packages"] = runtime_packages
    return workflow


# ─── (a) Build contract on real workflow ────────────────────────────

def test_build_contract_z_image() -> None:
    """build_contract on image/z_image returns version=1 with expected fields."""
    workflow = workflow_from_ready("image/z_image")
    contract = build_contract(workflow)

    assert contract.version == 1
    assert contract.workflow_id == "image/z_image"
    assert isinstance(contract.model_assets, list)
    assert len(contract.model_assets) > 0
    for asset in contract.model_assets:
        assert isinstance(asset, dict)
        assert "name" in asset

    assert isinstance(contract.custom_nodes, list)
    assert isinstance(contract.inputs, list)
    assert isinstance(contract.outputs, list)
    assert isinstance(contract.runtime_nodes, list)
    assert isinstance(contract.runtime_class_types, list)
    assert isinstance(contract.runtime_packages, list)
    assert contract.readiness_level == "ready"

    # JSON serialization round-trip
    payload = contract.to_dict()
    serialized = json.dumps(payload)
    round_tripped = json.loads(serialized)
    assert round_tripped == payload


def test_contract_additive_public_shape_round_trips_without_breaking_legacy_fields() -> None:
    workflow = VibeWorkflow(
        id="test/public_contract",
        source=WorkflowSource(id="test/public_contract"),
    )
    workflow.nodes["1"] = VibeNode(id="1", class_type="SaveImage", inputs={"filename_prefix": "old"})
    workflow.register_input(
        "filename_prefix",
        "1",
        "filename_prefix",
        "old",
        type="STRING",
        default="old",
        required=True,
        aliases=["prefix"],
        media_semantics="image",
    )
    workflow.outputs.append(
        VibeOutput(
            node_id="1",
            output_type="SaveImage",
            name="image",
            artifact_kind="image",
            mime_type="image/png",
            filename_prefix="old",
            expected_cardinality="one",
        )
    )

    payload = json.loads(json.dumps(build_contract(workflow).to_dict()))
    restored = WorkflowRuntimeContract(**payload)

    assert restored.version == 1
    assert restored.contract_shape == "workflow_runtime_contract.v1.public_descriptors.v2"
    assert payload["inputs"] == ["filename_prefix"]
    assert payload["outputs"] == [{"node_id": "1", "output_type": "SaveImage", "name": "image"}]
    assert payload["public_inputs"][0]["aliases"] == ["prefix"]
    assert payload["public_inputs"][0]["default"] == "old"
    assert payload["public_inputs"][0]["media_semantics"] == "image"
    assert "media" not in payload["public_inputs"][0]
    assert payload["public_outputs"][0]["artifact_kind"] == "image"
    assert payload["public_outputs"][0]["expected_cardinality"] == "one"
    assert restored.public_inputs == payload["public_inputs"]
    assert restored.public_outputs == payload["public_outputs"]


# ─── (b) PathchSageAttentionKJ without sageattention declared → error

def test_contract_doctor_sageattention_pathch() -> None:
    """PathchSageAttentionKJ with auto mode and no runtime_packages → error."""
    workflow = _synthetic_ltx_workflow("PathchSageAttentionKJ", sage_attention="auto")
    contract = build_contract(workflow)
    report = doctor_contract(workflow, contract)

    assert report.status == "error"
    error_diags = [d for d in report.diagnostics if d.severity == "error"]
    assert len(error_diags) >= 1
    assert any(
        d.code == "optional_acceleration_requires_unavailable_package"
        and "sageattention" in d.message.lower()
        for d in error_diags
    ), f"Expected sageattention error diagnostic, got: {error_diags}"


# ─── (c) PathchSageAttentionKJ with sageattention declared → ok

def test_contract_doctor_sageattention_declared() -> None:
    """PathchSageAttentionKJ with sageattention in runtime_packages → ok."""
    workflow = _synthetic_ltx_workflow(
        "PathchSageAttentionKJ",
        sage_attention="auto",
        runtime_packages=[
            {
                "name": "sageattention",
                "source": "pip",
                "install": "pip install sageattention",
                "probe": "import sageattention",
            }
        ],
    )
    contract = build_contract(workflow)
    report = doctor_contract(workflow, contract)

    assert report.status == "ok"
    error_diags = [d for d in report.diagnostics if d.severity == "error"]
    assert error_diags == [], f"Expected no error diagnostics, got: {error_diags}"


# ─── (d) LTX2MemoryEfficientSageAttentionPatch → error

def test_contract_doctor_ltx_memory_efficient_patch() -> None:
    """LTX2MemoryEfficientSageAttentionPatch without sageattention → error."""
    workflow = _synthetic_ltx_workflow("LTX2MemoryEfficientSageAttentionPatch")
    contract = build_contract(workflow)
    report = doctor_contract(workflow, contract)

    assert report.status == "error"
    error_diags = [d for d in report.diagnostics if d.severity == "error"]
    assert len(error_diags) >= 1
    assert any(
        d.code == "optional_acceleration_requires_unavailable_package"
        and d.class_type == "LTX2MemoryEfficientSageAttentionPatch"
        for d in error_diags
    ), f"Expected LTX2MemoryEfficientSageAttentionPatch error, got: {error_diags}"


# ─── (e) LTX2SamplingPreviewOverride → error (headless-incompatible)

def test_contract_doctor_ltx_preview_override() -> None:
    """LTX2SamplingPreviewOverride → headless-unsupported error unconditionally."""
    workflow = _synthetic_ltx_workflow("LTX2SamplingPreviewOverride")
    contract = build_contract(workflow)
    report = doctor_contract(workflow, contract)

    assert report.status == "error"
    error_diags = [d for d in report.diagnostics if d.severity == "error"]
    assert len(error_diags) >= 1
    assert any(
        d.code == "headless_preview_override_not_supported"
        and d.class_type == "LTX2SamplingPreviewOverride"
        for d in error_diags
    ), f"Expected headless_preview_override_not_supported error, got: {error_diags}"


# ─── (f) runtime_packages entry missing source/install/probe → info

def test_contract_doctor_missing_hints() -> None:
    """Declared runtime_packages entry without source/install/probe → info."""
    workflow = _synthetic_workflow(
        runtime_packages=[
            {"name": "somepackage"},  # no source/install/probe
        ]
    )
    contract = build_contract(workflow)
    report = doctor_contract(workflow, contract)

    # Missing hints produce info diagnostics, not errors
    assert report.status == "ok"
    info_diags = [d for d in report.diagnostics if d.severity == "info"]
    assert len(info_diags) >= 1
    missing_hint_diags = [
        d for d in info_diags
        if d.code == "runtime_package_missing_install_hint"
    ]
    assert len(missing_hint_diags) >= 1
    assert "somepackage" in missing_hint_diags[0].message


# ─── (g) Non-LTX workflow → ok

def test_contract_doctor_non_ltx_ok() -> None:
    """Non-LTX workflow returns ok with no error diagnostics."""
    workflow = _synthetic_workflow()
    node = workflow.add_node("CheckpointLoaderSimple")
    node.inputs["ckpt_name"] = "test.safetensors"
    workflow.metadata["model_assets"] = [
        {"name": "test.safetensors", "url": "https://example.com/test.safetensors"}
    ]
    workflow.metadata["python_policy_applied"] = True

    contract = build_contract(workflow)
    report = doctor_contract(workflow, contract)

    assert report.status == "ok"
    error_diags = [d for d in report.diagnostics if d.severity == "error"]
    assert error_diags == [], f"Expected no error diagnostics, got: {error_diags}"

    # JSON serialization round-trip for the contract
    payload = contract.to_dict()
    serialized = json.dumps(payload)
    round_tripped = json.loads(serialized)
    assert round_tripped == payload
