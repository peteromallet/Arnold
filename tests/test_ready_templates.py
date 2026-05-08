from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.patches.ltx_lowvram import apply as apply_ltx_lowvram
from vibecomfy.patches.resolution import resolution
from vibecomfy.registry.ready import ready_template_ids, workflow_from_ready
from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.runtime.session import SessionConfig
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


SNAPSHOT_IDS = (
    "image/z_image",
    "image/flux2_klein_4b_t2i",
    "image/flux2_klein_9b_gguf_t2i",
    "edit/qwen_image_edit",
    "edit/flux2_klein_4b_image_edit_distilled",
    "video/wan_t2v",
    "video/wan_i2v",
    "video/ltx2_3_t2v",
    "video/ltx2_3_i2v",
)

PROFILE_SMOKE_TEMPLATE_IDS = (
    "video/wanvideo_wrapper_22_5b_i2v",
    "video/wan_t2v",
)


def test_ready_template_ids_include_curated_workflows() -> None:
    ids = ready_template_ids()

    assert "edit/qwen_image_edit" in ids
    assert "image/qwen_image_2512" in ids
    assert "edit/flux2_klein_4b_image_edit_base" in ids
    assert "edit/flux2_klein_9b_image_edit_base" in ids
    assert "edit/flux2_klein_9b_image_edit_distilled" in ids
    assert "image/z_image" in ids
    assert "image/flux2_klein_9b_t2i" in ids
    assert "video/wan_t2v" in ids
    assert all(not template_id.rsplit("/", 1)[-1].startswith("_") for template_id in ids)


def test_ready_template_loads_vibe_workflow() -> None:
    workflow = workflow_from_ready("edit/qwen_image_edit")

    assert workflow.validate().ok
    assert workflow.metadata["ready_template"] == "edit/qwen_image_edit"
    assert workflow.metadata["python_policy_applied"] is True


def test_all_ready_templates_load_and_validate() -> None:
    for template_id in ready_template_ids():
        workflow = workflow_from_ready(template_id)

        assert workflow.id == template_id
        assert workflow.validate().ok
        assert workflow.metadata["ready_template"] == template_id


def test_ready_template_compile_emits_no_null_api_inputs() -> None:
    workflow = workflow_from_ready("video/wanvideo_wrapper_22_wan_animate_preprocess_kijai")
    api = workflow.compile("api")

    null_inputs = [
        (node_id, node["class_type"], input_name)
        for node_id, node in api.items()
        for input_name, value in node.get("inputs", {}).items()
        if value is None
    ]

    assert null_inputs == []


def test_wan_animate_template_compile_emits_executable_api_nodes() -> None:
    workflow = workflow_from_ready("video/wanvideo_wrapper_22_wan_animate_preprocess_kijai")
    api = workflow.compile("api")

    helper_nodes = {"Note", "MarkdownNote", "SetNode", "GetNode"}
    assert {node["class_type"] for node in api.values()} & helper_nodes == set()
    assert all(
        not (_is_link(value) and str(value[0]) not in api)
        for node in api.values()
        for value in node.get("inputs", {}).values()
    )


def test_wan_animate_template_declares_sam2_node_pack() -> None:
    workflow = workflow_from_ready("video/wanvideo_wrapper_22_wan_animate_preprocess_kijai")

    assert "ComfyUI-segment-anything-2" in workflow.requirements.custom_nodes


def test_ready_template_build_has_category_qualified_metadata() -> None:
    workflow = workflow_from_ready("qwen_image_edit")

    assert workflow.id == "edit/qwen_image_edit"
    assert workflow.metadata["ready_template"] == "edit/qwen_image_edit"
    assert workflow.metadata["workflow_template"] == "qwen_image_edit"


def test_ready_template_preserves_materialized_requirements() -> None:
    workflow = workflow_from_ready("video/ltx2_3_t2v")

    assert "ComfyUI-LTXVideo" in workflow.requirements.custom_nodes
    assert "ComfyUI-KJNodes" in workflow.requirements.custom_nodes


@pytest.mark.parametrize(
    "template_id",
    ["video/wanvideo_wrapper_22_14b_t2i", "video/wanvideo_wrapper_22_14b_vace_cocktail"],
)
def test_wan_2_2_templates_use_canonical_wanvideo_lora_path(template_id: str) -> None:
    workflow = workflow_from_ready(template_id)

    lora_nodes = [
        node
        for node in workflow.nodes.values()
        if node.class_type == "WanVideoLoraSelectMulti"
    ]
    assert lora_nodes
    assert all(
        node.inputs["widget_0"]
        == "WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"
        for node in lora_nodes
    )
    assert any(
        isinstance(asset, dict)
        and asset.get("name") == "lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"
        and (asset.get("subdir") or asset.get("directory")) == "loras/WanVideo/Lightx2v"
        for asset in workflow.metadata["model_assets"]
    )


@pytest.mark.parametrize(
    "template_id",
    ["video/wanvideo_wrapper_22_14b_t2i", "video/wanvideo_wrapper_22_14b_vace_cocktail"],
)
def test_wan_2_2_templates_use_torch_compatible_precision(template_id: str) -> None:
    workflow = workflow_from_ready(template_id)

    loader_nodes = [
        node
        for node in workflow.nodes.values()
        if node.class_type == "WanVideoModelLoader"
    ]
    assert loader_nodes
    assert all(node.inputs["widget_1"] == "fp16" for node in loader_nodes)


def test_wan_vace_template_uses_root_vace_module_asset() -> None:
    workflow = workflow_from_ready("video/wanvideo_wrapper_22_14b_vace_cocktail")

    assert any(
        isinstance(asset, dict)
        and asset.get("name") == "Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors"
        and asset.get("url") == (
            "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/"
            "Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors"
        )
        and (asset.get("subdir") or asset.get("directory")) == "diffusion_models/WanVideo"
        for asset in workflow.metadata["model_assets"]
    )


@pytest.mark.parametrize(
    "template_id",
    ["video/wanvideo_wrapper_22_14b_t2i", "video/wanvideo_wrapper_22_14b_vace_cocktail"],
)
def test_wan_2_2_template_asset_urls_match_upstream_locations(template_id: str) -> None:
    workflow = workflow_from_ready(template_id)
    assets = {
        asset["name"]: asset
        for asset in workflow.metadata["model_assets"]
        if isinstance(asset, dict) and isinstance(asset.get("name"), str)
    }

    assert assets["Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors"]["url"] == (
        "https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/"
        "T2V/Wan2_2-T2V-A14B_HIGH_fp8_e4m3fn_scaled_KJ.safetensors"
    )
    assert assets["Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors"]["url"] == (
        "https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/"
        "T2V/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors"
    )
    assert assets["lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"]["url"] == (
        "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/"
        "Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"
    )
    assert assets["Wan2_1_VAE_bf16.safetensors"]["url"] == (
        "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors"
    )
    assert assets["umt5-xxl-enc-bf16.safetensors"]["url"] == (
        "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors"
    )


def test_ready_template_requirements_accept_structured_model_assets() -> None:
    workflow = VibeWorkflow("scratchpad", WorkflowSource("scratchpad"))
    workflow.add_node("CheckpointLoaderSimple", widget_0="checkpoint.safetensors")

    apply_ready_template_policy(
        workflow,
        {},
        source_path="scratch.py",
        requirements={
            "models": [
                "legacy.safetensors",
                {
                    "name": "z-model.safetensors",
                    "url": "https://example.test/z-model.safetensors",
                    "subdir": "checkpoints",
                },
                {
                    "name": "z-model.safetensors",
                    "url": "https://example.test/duplicate.safetensors",
                    "subdir": "checkpoints",
                },
                {
                    "name": "a-model.safetensors",
                    "url": "https://example.test/a-model.safetensors",
                    "subdir": "vae",
                },
            ],
            "custom_nodes": [],
        },
    )

    assert workflow.requirements.models == [
        "a-model.safetensors",
        "legacy.safetensors",
        "z-model.safetensors",
    ]
    assert all(isinstance(model, str) for model in workflow.requirements.models)
    assert workflow.metadata["model_assets"] == [
        {
            "name": "z-model.safetensors",
            "url": "https://example.test/z-model.safetensors",
            "subdir": "checkpoints",
        },
        {
            "name": "a-model.safetensors",
            "url": "https://example.test/a-model.safetensors",
            "subdir": "vae",
        },
    ]


def test_ready_template_uses_real_python_before_comfy_compile() -> None:
    workflow = workflow_from_ready("edit/qwen_image_edit")

    marker = f"external_python:{workflow.metadata['ready_template']}"
    workflow.metadata["external_python_marker"] = marker
    workflow.add_node("MarkdownNote", widget_0=marker)
    api = workflow.compile("api")

    assert workflow.metadata["external_python_marker"] == marker
    assert all(node["inputs"].get("widget_0") != marker for node in api.values())


@pytest.mark.parametrize("template_id", PROFILE_SMOKE_TEMPLATE_IDS)
@pytest.mark.parametrize("memory_profile", [1, 2, 3, 4, 5])
def test_representative_video_ready_templates_compile_under_memory_profiles(
    template_id: str,
    memory_profile: int,
) -> None:
    baseline = workflow_from_ready(template_id)
    baseline_api = baseline.compile("api")
    workflow = workflow_from_ready(template_id)
    workflow.metadata["comfy_configuration"] = {"memory_profile": memory_profile}

    config = SessionConfig.from_workflow_metadata(workflow)
    api = workflow.compile("api")

    assert config.memory_profile == memory_profile
    assert workflow.validate().ok
    assert api
    assert _class_type_counter(api) == _class_type_counter(baseline_api)
    assert _topology_counter(api) == _topology_counter(baseline_api)


@pytest.mark.parametrize("template_id", SNAPSHOT_IDS)
def test_snapshotted_ready_template_graph_matches_pre_refactor_api(template_id: str) -> None:
    workflow = workflow_from_ready(template_id)
    actual = workflow.compile("api")
    snapshot_name = template_id.rsplit("/", 1)[-1]
    expected = json.loads((Path(__file__).parent / "snapshots" / f"{snapshot_name}.api.json").read_text(encoding="utf-8"))
    if template_id.startswith("video/ltx2_3_"):
        expected_workflow = convert_to_vibe_format(expected, workflow_id=template_id)
        expected_workflow.metadata["ready_template"] = template_id
        apply_ltx_lowvram(expected_workflow)
        resolution(384, 256, 9).apply(expected_workflow)
        expected = expected_workflow.compile("api")

    assert _class_type_counter(actual) == _class_type_counter(expected)
    assert _widget_value_counter(actual) == _widget_value_counter(expected)
    assert _topology_counter(actual) == _topology_counter(expected)


def _class_type_counter(api: dict) -> Counter[str]:
    return Counter(node["class_type"] for node in api.values() if node.get("class_type") != "MarkdownNote")


def _widget_value_counter(api: dict) -> Counter[tuple[str, str, str]]:
    values: Counter[tuple[str, str, str]] = Counter()
    for node in api.values():
        class_type = node.get("class_type")
        if class_type == "MarkdownNote":
            continue
        for key, value in node.get("inputs", {}).items():
            if _is_link(value):
                continue
            values[(class_type, key, repr(value))] += 1
    return values


def _topology_counter(api: dict) -> Counter[tuple[str, str, str, int]]:
    topology: Counter[tuple[str, str, str, int]] = Counter()
    for node_id, node in api.items():
        class_type = node.get("class_type")
        if class_type == "MarkdownNote":
            continue
        for key, value in node.get("inputs", {}).items():
            if not _is_link(value):
                continue
            source = api.get(str(value[0]), {})
            source_class = source.get("class_type")
            if source_class == "MarkdownNote":
                continue
            topology[(class_type, key, source_class, int(value[1]))] += 1
    return topology


def _is_link(value: object) -> bool:
    return isinstance(value, list) and len(value) == 2 and str(value[0]).isdigit()
