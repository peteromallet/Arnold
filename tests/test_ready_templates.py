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
from vibecomfy.runtime.session import SessionConfig, _model_assets_from_workflow
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


def test_template_index_matches_ready_template_discovery() -> None:
    from tools.refresh_template_index import build_template_index

    expected = build_template_index()
    actual = json.loads(Path("template_index.json").read_text(encoding="utf-8"))

    assert actual["template_count"] == expected["template_count"]
    assert [item["id"] for item in actual["templates"]] == [item["id"] for item in expected["templates"]]
    assert actual["templates"] == expected["templates"]


def test_ready_templates_are_pure_python_builders() -> None:
    ready_root = Path("ready_templates")
    offenders: list[str] = []

    for path in sorted(ready_root.rglob("*.py")):
        if path.name == "__init__.py" or path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        if "API_WORKFLOW =" in text or "build_api_ready_workflow" in text:
            offenders.append(path.relative_to(ready_root).with_suffix("").as_posix())

    assert offenders == []


def test_ready_loader_applies_authored_metadata_for_manual_python_templates() -> None:
    workflow = workflow_from_ready("image/z_image")

    assert workflow.metadata["python_policy_applied"] is True
    assert {asset["name"] for asset in workflow.metadata["model_assets"]} >= {
        "qwen_3_4b.safetensors",
        "ae.safetensors",
        "z_image_bf16.safetensors",
    }
    assert {"qwen_3_4b.safetensors", "ae.safetensors", "z_image_bf16.safetensors"} <= set(
        workflow.requirements.models
    )


def test_ready_templates_do_not_enable_uncontracted_sageattention() -> None:
    offenders: list[tuple[str, str, str]] = []

    for template_id in ready_template_ids():
        api = workflow_from_ready(template_id).compile("api")
        offenders.extend(
            (template_id, node_id, inputs.get("sage_attention"))
            for node_id, node in api.items()
            if node.get("class_type") == "PathchSageAttentionKJ"
            for inputs in [node.get("inputs", {})]
            if inputs.get("sage_attention") not in {None, "disabled"}
        )

    assert offenders == []


def test_wanvideo_model_loaders_use_portable_runpod_attention_contract() -> None:
    offenders: list[tuple[str, str, str, str]] = []

    for template_id in ready_template_ids():
        api = workflow_from_ready(template_id).compile("api")
        for node_id, node in api.items():
            if node.get("class_type") != "WanVideoModelLoader":
                continue
            inputs = node.get("inputs", {})
            attention_mode = inputs.get("attention_mode")
            base_precision = inputs.get("base_precision")
            if attention_mode == "sageattn" or base_precision == "fp16_fast":
                offenders.append((template_id, node_id, str(attention_mode), str(base_precision)))

    assert offenders == []


def test_ready_templates_do_not_use_uncontracted_ltx_memory_efficient_sage_patch() -> None:
    offenders: list[tuple[str, str]] = []

    for template_id in ready_template_ids():
        api = workflow_from_ready(template_id).compile("api")
        offenders.extend(
            (template_id, node_id)
            for node_id, node in api.items()
            if node.get("class_type") == "LTX2MemoryEfficientSageAttentionPatch"
        )

    assert offenders == []


def test_ready_templates_do_not_use_headless_incompatible_ltx_preview_override() -> None:
    offenders: list[tuple[str, str]] = []

    for template_id in ready_template_ids():
        api = workflow_from_ready(template_id).compile("api")
        offenders.extend(
            (template_id, node_id)
            for node_id, node in api.items()
            if node.get("class_type") == "LTX2SamplingPreviewOverride"
        )

    assert offenders == []


@pytest.mark.parametrize(
    "template_id",
    [
        "video/ltx2_3_runexx_first_last_frame",
        "video/ltx2_3_runexx_first_last_raw_video_guide",
        "video/ltx2_3_first_last_frame_travel_iclora_control",
        "video/ltx2_3_runexx_first_middle_last_frame",
    ],
)
def test_ltx_travel_segment_outputs_omit_synthetic_audio(template_id: str) -> None:
    api = workflow_from_ready(template_id).compile("api")

    video_combine_nodes = [
        node
        for node in api.values()
        if node.get("class_type") == "VHS_VideoCombine"
    ]

    assert video_combine_nodes
    assert all("audio" not in node.get("inputs", {}) for node in video_combine_nodes)


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


def test_wan_animate_template_declares_pose_preprocess_pack_and_models() -> None:
    workflow = workflow_from_ready("video/wanvideo_wrapper_22_wan_animate_preprocess_kijai")

    assert "ComfyUI-WanAnimatePreprocess" in workflow.requirements.custom_nodes
    assert "yolov10m.onnx" in workflow.requirements.models
    assert "vitpose-l-wholebody.onnx" in workflow.requirements.models
    assert any(
        asset.get("name") == "yolov10m.onnx" and asset.get("directory") == "detection"
        for asset in workflow.metadata.get("model_assets", [])
    )
    assert any(
        asset.get("name") == "vitpose-l-wholebody.onnx" and asset.get("directory") == "detection"
        for asset in workflow.metadata.get("model_assets", [])
    )


def test_native_wan_animate_template_declares_frame_count_binding() -> None:
    workflow = workflow_from_ready("video/wan22_animate_native_first_stage")

    assert workflow.metadata["unbound_inputs"]["num_frames"] == "232:62.length"


def test_ready_template_build_has_category_qualified_metadata() -> None:
    workflow = workflow_from_ready("qwen_image_edit")

    assert workflow.id == "edit/qwen_image_edit"
    assert workflow.metadata["ready_template"] == "edit/qwen_image_edit"
    assert workflow.metadata["workflow_template"] == "qwen_image_edit"


def test_ready_template_preserves_materialized_requirements() -> None:
    workflow = workflow_from_ready("video/ltx2_3_t2v")

    assert "ComfyUI-LTXVideo" in workflow.requirements.custom_nodes
    assert "ComfyUI-KJNodes" in workflow.requirements.custom_nodes


def test_ltx_first_last_travel_iclora_control_exposes_worker_patch_points() -> None:
    workflow = workflow_from_ready("video/ltx2_3_first_last_frame_travel_iclora_control")
    api = workflow.compile("api")

    assert workflow.validate().ok
    assert workflow.metadata["source_role"] == "manual_ready_python_template"
    assert workflow.inputs["start_image"].node_id == "45"
    assert workflow.inputs["end_image"].node_id == "47"
    assert workflow.inputs["control_video"].node_id == "5001"
    assert workflow.inputs["prompt"].node_id == "16"
    assert workflow.inputs["negative"].node_id == "11"
    assert workflow.inputs["seed"].node_id == "14"
    assert workflow.inputs["frames"].node_id == "2078"
    assert workflow.inputs["width"].node_id == "2080"
    assert workflow.inputs["height"].node_id == "2079"
    assert workflow.inputs["fps"].node_id == "2076"
    assert workflow.inputs["strength"].node_id == "5012"
    assert workflow.inputs["strength"].field == "strength"
    assert workflow.inputs["ic_lora_filename"].node_id == "5011"
    assert workflow.inputs["ic_lora_strength"].node_id == "5011"
    assert workflow.inputs["ic_lora_strength"].field == "strength_model"

    assert api["45"]["class_type"] == "LoadImage"
    assert api["47"]["class_type"] == "LoadImage"
    assert api["5001"]["class_type"] == "LoadVideo"
    assert api["5000"]["class_type"] == "GetVideoComponents"
    assert api["5011"]["class_type"] == "LTXICLoRALoaderModelOnly"
    assert api["5011"]["inputs"]["lora_name"] == "ltxv/ltx2/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors"
    assert api["5011"]["inputs"]["strength_model"] == 1
    assert api["5012"]["class_type"] == "LTXAddVideoICLoRAGuide"
    assert api["5012"]["inputs"]["image"] == ["5028", 0]
    assert api["5012"]["inputs"]["frame_idx"] == 0
    assert api["5012"]["inputs"]["strength"] == 1
    assert api["5012"]["inputs"]["crop"] == "center"
    assert api["5012"]["inputs"]["use_tiled_encode"] == "disabled"
    assert api["5012"]["inputs"]["tile_size"] == 128
    assert api["5012"]["inputs"]["tile_overlap"] == 32
    assert api["210"]["class_type"] == "LTXVImgToVideoInplaceKJ"
    assert api["210"]["inputs"]["num_images.image_1"] == ["2084", 0]
    assert api["210"]["inputs"]["num_images.image_2"] == ["50", 0]
    assert api["6101"]["class_type"] == "ImageResizeKJv2"
    for resize_node_id in ("5026", "6101", "5028", "6102", "6103"):
        assert api[resize_node_id]["class_type"] == "ImageResizeKJv2"
        assert api[resize_node_id]["inputs"]["width"] == ["2080", 0]
        assert api[resize_node_id]["inputs"]["height"] == ["2079", 0]
        assert api[resize_node_id]["inputs"]["upscale_method"] == "lanczos"
        assert api[resize_node_id]["inputs"]["keep_proportion"] == "stretch"
        assert api[resize_node_id]["inputs"]["crop_position"] == "center"
        assert not any(key.startswith("resize_type") for key in api[resize_node_id]["inputs"])
    assert api["4986"]["class_type"] == "DWPreprocessor"
    assert api["6102"]["inputs"]["image"] == ["4986", 0]
    assert api["5061"]["class_type"] == "DepthAnything_V2"
    assert api["6103"]["inputs"]["image"] == ["5061", 0]
    assert api["4991"]["class_type"] == "CannyEdgePreprocessor"
    assert api["5028"]["inputs"]["image"] == ["4991", 0]
    assert api["175"]["class_type"] == "LTXVAudioVAELoader"
    assert api["175"]["inputs"]["ckpt_name"] == "LTX23_audio_vae_bf16.safetensors"
    assets = {
        asset["name"]: asset
        for asset in workflow.metadata["model_assets"]
        if isinstance(asset, dict) and isinstance(asset.get("name"), str)
    }
    assert assets["LTX23_audio_vae_bf16.safetensors"]["subdir"] == "checkpoints"
    assert assets["depth_anything_v2_vits_fp32.safetensors"]["subdir"] == "depthanything"
    assert assets["yolox_l.onnx"]["target_path"] == (
        "custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/yolox_l.onnx"
    )
    assert assets["dw-ll_ucoco_384_bs5.torchscript.pt"]["target_path"] == (
        "custom_nodes/comfyui_controlnet_aux/ckpts/hr16/DWPose-TorchScript-BatchSize5/"
        "dw-ll_ucoco_384_bs5.torchscript.pt"
    )


def test_ltx_first_last_raw_video_guide_exposes_worker_patch_points() -> None:
    workflow = workflow_from_ready("video/ltx2_3_runexx_first_last_raw_video_guide")
    api = workflow.compile("api")

    assert workflow.validate().ok
    assert "rgthree-comfy" in workflow.requirements.custom_nodes
    assert workflow.metadata["source_role"] == "manual_ready_python_template"
    assert workflow.inputs["start_image"].node_id == "45"
    assert workflow.inputs["end_image"].node_id == "47"
    assert workflow.inputs["control_video"].node_id == "5001"
    assert workflow.inputs["prompt"].node_id == "2103"
    assert workflow.inputs["negative"].node_id == "11"
    assert workflow.inputs["seed"].node_id == "14"
    assert workflow.inputs["frames"].node_id == "2078"
    assert workflow.inputs["width"].node_id == "2080"
    assert workflow.inputs["height"].node_id == "2079"
    assert workflow.inputs["fps"].node_id == "2076"
    assert workflow.inputs["strength"].node_id == "6102"
    assert workflow.inputs["first_frame_strength"].node_id == "2110"
    assert workflow.inputs["last_frame_strength"].node_id == "2108"

    assert api["45"]["class_type"] == "LoadImage"
    assert api["47"]["class_type"] == "LoadImage"
    assert api["5001"]["class_type"] == "LoadVideo"
    assert api["5000"]["class_type"] == "GetVideoComponents"
    assert api["6101"]["class_type"] == "ImageResizeKJv2"
    assert api["6101"]["inputs"]["image"] == ["5000", 0]
    assert api["6101"]["inputs"]["width"] == ["2080", 0]
    assert api["6101"]["inputs"]["height"] == ["2079", 0]
    assert api["6101"]["inputs"]["upscale_method"] == "lanczos"
    assert api["6101"]["inputs"]["keep_proportion"] == "stretch"
    assert api["6101"]["inputs"]["crop_position"] == "center"
    assert not any(key.startswith("resize_type") for key in api["6101"]["inputs"])
    assert api["6102"]["class_type"] == "PrimitiveFloat"
    assert api["2152"]["class_type"] == "LTXVAddGuide"
    assert api["2152"]["inputs"]["frame_idx"] == -1
    assert api["175"]["class_type"] == "LTXVAudioVAELoader"
    assert api["175"]["inputs"]["ckpt_name"] == "LTX23_audio_vae_bf16.safetensors"
    assert api["215"]["inputs"]["sigmas"].startswith("1.0, 0.99375")
    assert api["216"]["inputs"]["sigmas"] == "0.85, 0.7250, 0.4219, 0.0"
    assert api["92"]["inputs"]["expression"] == "a"
    assert api["2077"]["inputs"]["expression"].startswith("((round((a * b -1)")
    assert api["9"]["inputs"]["batch_size"] == 1
    assert api["26"]["inputs"]["upscale_method"] == "lanczos"
    assert api["26"]["inputs"]["scale_by"] == 0.5
    assert api["226"]["inputs"]["sage_attention"] == "disabled"
    assert api["226"]["inputs"]["allow_compile"] is False
    assert api["228"]["inputs"]["chunks"] == 2
    assert api["228"]["inputs"]["dim_threshold"] == 4096
    assert api["228"]["inputs"]["model"] == ["226", 0]
    assert api["229"]["inputs"]["triton_kernels"] is False
    assert api["197"]["inputs"]["nag_scale"] == 11
    assert api["43"]["inputs"]["filename_prefix"] == "reigh_vibecomfy_ltx_raw_guide"
    assert api["43"]["inputs"]["save_output"] is True
    assert {asset["name"] for asset in workflow.metadata["model_assets"]} >= {
        "ltx-2.3_text_projection_bf16.safetensors",
        "taeltx2_3.safetensors",
        "LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors",
    }
    assert api["2152"]["inputs"]["image"] == ["6101", 0]
    assert api["2152"]["inputs"]["strength"] == ["6102", 0]
    assert "LTXICLoRALoaderModelOnly" not in {node["class_type"] for node in api.values()}
    assert "LTXAddVideoICLoRAGuide" not in {node["class_type"] for node in api.values()}
    assert _opaque_component_nodes(api) == []


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
    [
        "video/wanvideo_wrapper_22_14b_t2i",
        "video/wanvideo_wrapper_22_14b_i2v_kijai",
        "video/wan22_animate_native_first_stage",
    ],
)
def test_video_parity_templates_have_resolvable_runtime_model_assets(template_id: str) -> None:
    workflow = workflow_from_ready(template_id)

    assets = _model_assets_from_workflow(workflow)

    assert assets


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


def _opaque_component_nodes(api: dict[str, dict]) -> list[tuple[str, str]]:
    return [
        (node_id, node["class_type"])
        for node_id, node in api.items()
        if isinstance(node.get("class_type"), str)
        and len(node["class_type"]) == 36
        and node["class_type"].count("-") == 4
    ]
