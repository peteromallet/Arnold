from __future__ import annotations

import json
from pathlib import Path

from scripts.runpod_matrix_plan import build_corpus_matrix_plan, format_ready_rows, format_rows
from scripts.runpod_matrix_remote import GGUF_MODEL, LTX_CHECKPOINT, patch_workflow_api


def test_corpus_matrix_plan_splits_required_workflows(tmp_path: Path) -> None:
    manifest = tmp_path / "workflow_corpus" / "manifests" / "coverage.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "workflows": [
                    {"id": "core", "path": "core.json", "media": "image", "task": "text_to_image", "coverage_tier": "required"},
                    {
                        "id": "flux2_klein_9b_gguf_t2i",
                        "path": "gguf.json",
                        "media": "image",
                        "task": "text_to_image",
                        "coverage_tier": "required",
                    },
                    {"id": "ltx2_3_t2v", "path": "ltx.json", "media": "video", "task": "text_to_video", "coverage_tier": "required"},
                    {"id": "optional", "path": "optional.json", "media": "image", "task": "text_to_image", "coverage_tier": "optional"},
                ]
            }
        ),
        encoding="utf-8",
    )
    ready = tmp_path / "ready_templates" / "image" / "core.py"
    ready.parent.mkdir(parents=True)
    ready.write_text("# ready\n", encoding="utf-8")

    plan = build_corpus_matrix_plan(tmp_path)

    assert format_rows(plan.core_rows) == "core\tcore.json\timage"
    assert format_rows(plan.gguf_rows) == "flux2_klein_9b_gguf_t2i\tgguf.json\timage"
    assert format_rows(plan.ltx_rows) == "ltx2_3_t2v\tltx.json\tvideo"
    assert format_ready_rows(plan.ready_rows, tmp_path) == "core\tready_templates/image/core.py\timage"


def test_corpus_matrix_plan_scope_can_skip_core_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "workflow_corpus" / "manifests" / "coverage.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "workflows": [
                    {"id": "core", "path": "core.json", "media": "image", "task": "text_to_image", "coverage_tier": "required"},
                    {"id": "ltx2_3_t2v", "path": "ltx.json", "media": "video", "task": "text_to_video", "coverage_tier": "required"},
                ]
            }
        ),
        encoding="utf-8",
    )

    plan = build_corpus_matrix_plan(tmp_path, scope="ltx")

    assert plan.core_rows == ()
    assert format_rows(plan.ltx_rows) == "ltx2_3_t2v\tltx.json\tvideo"


def test_corpus_matrix_plan_can_select_wan_5b_only(tmp_path: Path) -> None:
    manifest = tmp_path / "workflow_corpus" / "manifests" / "coverage.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "workflows": [
                    {
                        "id": "wanvideo_wrapper_22_5b_i2v",
                        "path": "wan5b.json",
                        "media": "video",
                        "task": "image_to_video",
                        "coverage_tier": "supplemental",
                        "ready_template": True,
                    },
                    {
                        "id": "wanvideo_wrapper_21_14b_t2v",
                        "path": "wan14b.json",
                        "media": "video",
                        "task": "text_to_video",
                        "coverage_tier": "supplemental",
                        "ready_template": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    ready = tmp_path / "ready_templates" / "video" / "wanvideo_wrapper_22_5b_i2v.py"
    ready.parent.mkdir(parents=True)
    ready.write_text("# ready\n", encoding="utf-8")

    plan = build_corpus_matrix_plan(tmp_path, scope="wan_wrapper_5b")

    assert format_rows(plan.wan_wrapper_rows) == "wanvideo_wrapper_22_5b_i2v\twan5b.json\tvideo"
    assert format_ready_rows(plan.ready_rows, tmp_path) == "wanvideo_wrapper_22_5b_i2v\tready_templates/video/wanvideo_wrapper_22_5b_i2v.py\tvideo"


def test_corpus_matrix_plan_has_z_flux_scope(tmp_path: Path) -> None:
    manifest = tmp_path / "workflow_corpus" / "manifests" / "coverage.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "workflows": [
                    {"id": "qwen_image_edit", "path": "qwen.json", "media": "image", "task": "image_edit", "coverage_tier": "required"},
                    {"id": "z_image", "path": "z.json", "media": "image", "task": "text_to_image", "coverage_tier": "required"},
                    {"id": "flux2_klein_4b_t2i", "path": "flux4.json", "media": "image", "task": "text_to_image", "coverage_tier": "required"},
                    {"id": "flux2_klein_9b_gguf_t2i", "path": "flux9.json", "media": "image", "task": "text_to_image", "coverage_tier": "required"},
                    {"id": "wan_t2v", "path": "wan.json", "media": "video", "task": "text_to_video", "coverage_tier": "required"},
                ]
            }
        ),
        encoding="utf-8",
    )

    plan = build_corpus_matrix_plan(tmp_path, scope="z_flux")

    assert format_rows(plan.core_rows) == "z_image\tz.json\timage\nflux2_klein_4b_t2i\tflux4.json\timage"
    assert format_rows(plan.gguf_rows) == "flux2_klein_9b_gguf_t2i\tflux9.json\timage"


def test_corpus_matrix_plan_has_audio_scope(tmp_path: Path) -> None:
    manifest = tmp_path / "workflow_corpus" / "manifests" / "coverage.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "workflows": [
                    {"id": "z_image", "path": "z.json", "media": "image", "task": "text_to_image", "coverage_tier": "required"},
                    {
                        "id": "ace_step_1_5_t2a_song",
                        "path": "ace.json",
                        "media": "audio",
                        "task": "text_to_audio_song",
                        "coverage_tier": "required",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    plan = build_corpus_matrix_plan(tmp_path, scope="audio_core")

    assert format_rows(plan.core_rows) == "ace_step_1_5_t2a_song\tace.json\taudio"


def test_corpus_matrix_plan_has_public_ltx_iclora_scope(tmp_path: Path) -> None:
    manifest = tmp_path / "workflow_corpus" / "manifests" / "coverage.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "workflows": [
                    {
                        "id": "ltx2_3_lightricks_iclora_hdr",
                        "path": "hdr.json",
                        "media": "video",
                        "task": "video_guided_hdr",
                        "coverage_tier": "supplemental",
                        "ready_template": True,
                    },
                    {
                        "id": "ltx2_3_lightricks_iclora_motion_track",
                        "path": "motion.json",
                        "media": "video",
                        "task": "motion_track_control",
                        "coverage_tier": "supplemental",
                        "ready_template": True,
                    },
                    {
                        "id": "ltx2_3_lightricks_iclora_union_control",
                        "path": "union.json",
                        "media": "video",
                        "task": "union_control_video_guided_i2v",
                        "coverage_tier": "supplemental",
                        "ready_template": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    plan = build_corpus_matrix_plan(tmp_path, scope="ltx_iclora_public")

    assert format_rows(plan.ltx_rows) == (
        "ltx2_3_lightricks_iclora_motion_track\tmotion.json\tvideo\n"
        "ltx2_3_lightricks_iclora_union_control\tunion.json\tvideo"
    )


def test_corpus_matrix_plan_has_public_official_ltx_scope(tmp_path: Path) -> None:
    manifest = tmp_path / "workflow_corpus" / "manifests" / "coverage.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "workflows": [
                    {"id": "ltx2_3_t2v", "path": "t2v.json", "media": "video", "task": "text_to_video", "coverage_tier": "required"},
                    {"id": "ltx2_3_i2v", "path": "i2v.json", "media": "video", "task": "image_to_video", "coverage_tier": "required"},
                    {
                        "id": "ltx2_3_lightricks_two_stage",
                        "path": "two_stage.json",
                        "media": "video",
                        "task": "two_stage_upscale",
                        "coverage_tier": "supplemental",
                        "ready_template": True,
                    },
                    {
                        "id": "ltx2_3_lightricks_iclora_hdr",
                        "path": "hdr.json",
                        "media": "video",
                        "task": "video_guided_hdr",
                        "coverage_tier": "supplemental",
                        "ready_template": True,
                    },
                    {
                        "id": "ltx2_3_lightricks_iclora_motion_track",
                        "path": "motion.json",
                        "media": "video",
                        "task": "motion_track_control",
                        "coverage_tier": "supplemental",
                        "ready_template": True,
                    },
                    {
                        "id": "ltx2_3_lightricks_iclora_union_control",
                        "path": "union.json",
                        "media": "video",
                        "task": "union_control_video_guided_i2v",
                        "coverage_tier": "supplemental",
                        "ready_template": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    plan = build_corpus_matrix_plan(tmp_path, scope="ltx_official_public")

    assert format_rows(plan.ltx_rows) == (
        "ltx2_3_t2v\tt2v.json\tvideo\n"
        "ltx2_3_i2v\ti2v.json\tvideo\n"
        "ltx2_3_lightricks_two_stage\ttwo_stage.json\tvideo\n"
        "ltx2_3_lightricks_iclora_motion_track\tmotion.json\tvideo\n"
        "ltx2_3_lightricks_iclora_union_control\tunion.json\tvideo"
    )


def test_corpus_matrix_plan_has_creation_type_scopes(tmp_path: Path) -> None:
    manifest = tmp_path / "workflow_corpus" / "manifests" / "coverage.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "workflows": [
                    {"id": "z_image", "path": "z.json", "media": "image", "task": "text_to_image", "coverage_tier": "required"},
                    {"id": "flux2_klein_4b_t2i", "path": "flux4.json", "media": "image", "task": "text_to_image", "coverage_tier": "required"},
                    {
                        "id": "flux2_klein_4b_image_edit_distilled",
                        "path": "edit.json",
                        "media": "image",
                        "task": "image_edit",
                        "coverage_tier": "required",
                    },
                    {
                        "id": "wanvideo_wrapper_21_14b_flf2v",
                        "path": "flf.json",
                        "media": "video",
                        "task": "first_last_frame_video",
                        "coverage_tier": "supplemental",
                        "ready_template": True,
                    },
                    {
                        "id": "wanvideo_wrapper_21_14b_v2v_infinitetalk",
                        "path": "v2v.json",
                        "media": "video",
                        "task": "video_to_video_talking_avatar",
                        "coverage_tier": "supplemental",
                        "ready_template": True,
                    },
                    {
                        "id": "ltx2_3_runexx_video_to_video_extend",
                        "path": "ltx-v2v.json",
                        "media": "video",
                        "task": "video_to_video_extend",
                        "coverage_tier": "supplemental",
                        "ready_template": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    image_plan = build_corpus_matrix_plan(tmp_path, scope="image_creation_types")
    wan_plan = build_corpus_matrix_plan(tmp_path, scope="wan_creation_types")
    ltx_plan = build_corpus_matrix_plan(tmp_path, scope="ltx_creation_types")

    assert "z_image\tz.json\timage" in format_rows(image_plan.core_rows)
    assert "flux2_klein_4b_image_edit_distilled\tedit.json\timage" in format_rows(image_plan.core_rows)
    assert format_rows(wan_plan.wan_wrapper_rows) == (
        "wanvideo_wrapper_21_14b_flf2v\tflf.json\tvideo\n"
        "wanvideo_wrapper_21_14b_v2v_infinitetalk\tv2v.json\tvideo"
    )
    assert format_rows(ltx_plan.ltx_rows) == "ltx2_3_runexx_video_to_video_extend\tltx-v2v.json\tvideo"


def test_corpus_matrix_plan_can_resume_ltx_creation_remainder(tmp_path: Path) -> None:
    manifest = tmp_path / "workflow_corpus" / "manifests" / "coverage.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "workflows": [
                    {"id": "ltx2_3_t2v", "path": "t2v.json", "media": "video", "task": "text_to_video", "coverage_tier": "required"},
                    {"id": "ltx2_3_i2v", "path": "i2v.json", "media": "video", "task": "image_to_video", "coverage_tier": "required"},
                    {
                        "id": "ltx2_3_lightricks_iclora_motion_track",
                        "path": "motion.json",
                        "media": "video",
                        "task": "motion_track_control",
                        "coverage_tier": "supplemental",
                        "ready_template": True,
                    },
                    {
                        "id": "ltx2_3_runexx_first_last_frame",
                        "path": "flf.json",
                        "media": "video",
                        "task": "first_last_frame_video",
                        "coverage_tier": "supplemental",
                        "ready_template": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    remainder = build_corpus_matrix_plan(tmp_path, scope="ltx_creation_remainder")
    runexx = build_corpus_matrix_plan(tmp_path, scope="ltx_runexx_creation")

    assert format_rows(remainder.ltx_rows) == (
        "ltx2_3_i2v\ti2v.json\tvideo\n"
        "ltx2_3_lightricks_iclora_motion_track\tmotion.json\tvideo\n"
        "ltx2_3_runexx_first_last_frame\tflf.json\tvideo"
    )
    assert format_rows(runexx.ltx_rows) == "ltx2_3_runexx_first_last_frame\tflf.json\tvideo"


def test_runpod_remote_patch_policy_handles_ltx_i2v() -> None:
    api = _ltx_api()

    assert patch_workflow_api("ltx2_3_i2v", api) is True

    assert api["4010"]["class_type"] == "LowVRAMAudioVAELoader"
    assert api["4010"]["inputs"] == {"ckpt_name": LTX_CHECKPOINT}
    assert api["3940"]["class_type"] == "LowVRAMCheckpointLoader"
    assert api["4977"]["inputs"]["widget_0"] is False
    assert api["2004"]["inputs"]["widget_0"] == "egyptian_queen.png"
    assert api["text_encoder"]["inputs"]["clip_name"] == "gemma_3_12B_it_fp4_mixed.safetensors"


def test_runpod_remote_patch_policy_clamps_wan_start_step_for_one_step_smokes() -> None:
    api = {
        "sampler": {
            "class_type": "WanVideoSampler",
            "inputs": {"steps": 20, "widget_0": 20, "start_step": 2, "widget_8": 2},
        }
    }

    assert patch_workflow_api("wanvideo_wrapper_21_14b_v2v_infinitetalk", api) is True

    assert api["sampler"]["inputs"]["steps"] == 1
    assert api["sampler"]["inputs"]["widget_0"] == 1
    assert api["sampler"]["inputs"]["start_step"] == 0
    assert api["sampler"]["inputs"]["widget_8"] == 0


def test_corpus_matrix_patches_wan_headless_preview_crash() -> None:
    script = Path("scripts/runpod_corpus_matrix.py").read_text(encoding="utf-8")

    assert "custom_nodes/ComfyUI-WanVideoWrapper/latent_preview.py" in script
    assert "node_id = serv.last_node_id or '0'" in script


def test_corpus_matrix_plan_has_wan_infinitetalk_scope(tmp_path: Path) -> None:
    manifest = tmp_path / "workflow_corpus" / "manifests" / "coverage.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "workflows": [
                    {
                        "id": "wanvideo_wrapper_21_14b_t2v",
                        "path": "t2v.json",
                        "media": "video",
                        "task": "text_to_video",
                        "coverage_tier": "supplemental",
                        "ready_template": True,
                    },
                    {
                        "id": "wanvideo_wrapper_21_14b_v2v_infinitetalk",
                        "path": "infinitetalk.json",
                        "media": "video",
                        "task": "video_to_video",
                        "coverage_tier": "supplemental",
                        "ready_template": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    plan = build_corpus_matrix_plan(tmp_path, scope="wan_infinitetalk")

    assert format_rows(plan.wan_wrapper_rows) == "wanvideo_wrapper_21_14b_v2v_infinitetalk\tinfinitetalk.json\tvideo"


def test_runpod_remote_patch_policy_reduces_ltx_control_preprocessing() -> None:
    api = {
        "resize": {
            "class_type": "ResizeImageMaskNode",
            "inputs": {"widget_1": 1536, "resize_type.shorter_size": 544, "resize_type.longer_size": 1536},
        },
        "dwpose": {"class_type": "DWPreprocessor", "inputs": {"widget_3": 512}},
        "canny": {"class_type": "CannyEdgePreprocessor", "inputs": {"widget_2": 512}},
        "guide": {"class_type": "LTXAddVideoICLoRAGuide", "inputs": {"widget_5": 256, "widget_6": 64}},
    }

    assert patch_workflow_api("ltx2_3_lightricks_iclora_union_control", api) is True

    assert api["resize"]["inputs"]["widget_1"] == 256
    assert api["resize"]["inputs"]["resize_type.shorter_size"] == 256
    assert api["resize"]["inputs"]["resize_type.longer_size"] == 256
    assert api["dwpose"]["inputs"]["widget_3"] == 256
    assert api["canny"]["inputs"]["widget_2"] == 256
    assert api["guide"]["inputs"]["widget_5"] == 128
    assert api["guide"]["inputs"]["widget_6"] == 32


def test_runpod_remote_patch_policy_handles_runexx_ltx_api_cleanup() -> None:
    api = {
        "loader": {
            "class_type": "Power Lora Loader (rgthree)",
            "inputs": {"model": ["model", 0], "widget_0": {}, "widget_1": {"type": "header"}, "widget_3": ""},
        },
        "group": {"class_type": "Fast Groups Bypasser (rgthree)", "inputs": {}},
        "show": {"class_type": "easy showAnything", "inputs": {"anything": ["loader", 0]}},
        "preview": {"class_type": "PreviewAny", "inputs": {"source": ["show", 0], "previewMode": None}},
        "sink": {"class_type": "SaveVideo", "inputs": {"images": ["loader", 0]}},
    }

    assert patch_workflow_api("ltx2_3_runexx_first_last_frame", api) is True

    assert api["loader"]["inputs"] == {"model": ["model", 0], "widget_3": ""}
    assert "group" not in api
    assert "show" not in api
    assert "preview" not in api


def test_runpod_remote_patch_policy_handles_runexx_ltx_models_and_video() -> None:
    api = {
        "clip": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": "gemma_3_12B_it_fp8_scaled.safetensors",
                "clip_name2": "ltx-2.3_text_projection_bf16.safetensors",
            },
        },
        "video_vae": {"class_type": "VAELoader", "inputs": {"vae_name": "LTX23_video_vae_bf16_KJ.safetensors"}},
        "audio_vae": {"class_type": "VAELoaderKJ", "inputs": {"vae_name": "LTX23_audio_vae_bf16_KJ.safetensors"}},
        "preview_vae": {"class_type": "VAELoader", "inputs": {"vae_name": "vae_approx\\taeltx2_3.safetensors"}},
        "unet": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "LTXVideo\\v2\\ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors"},
        },
        "video": {"class_type": "VHS_LoadVideo", "inputs": {"video": "joker_therapy.mp4"}},
        "audio_norm": {"class_type": "NormalizeAudioLoudness", "inputs": {"audio": ["video", 2]}},
        "scheduler": {"class_type": "LTXVScheduler", "inputs": {"steps": 8}},
        "upscale_model": {"class_type": "LatentUpscaleModelLoader", "inputs": {"model_name": "ltx-2.3-spatial-upscaler-x2-1.1.safetensors"}},
        "upscale": {"class_type": "LTXVLatentUpsampler", "inputs": {"samples": ["latent", 0], "upscale_model": ["upscale_model", 0]}},
        "upscale_sink": {"class_type": "LTXVImgToVideoInplace", "inputs": {"latent": ["upscale", 0]}},
    }

    assert patch_workflow_api("ltx2_3_runexx_video_to_video_extend", api) is True

    assert api["clip"]["inputs"]["clip_name1"] == "gemma_3_12B_it_fp4_mixed.safetensors"
    assert api["clip"]["inputs"]["clip_name2"] == "ltx-2.3_text_projection_bf16.safetensors"
    assert api["video_vae"]["inputs"]["vae_name"] == "LTX23_video_vae_bf16.safetensors"
    assert api["audio_vae"]["inputs"]["vae_name"] == "LTX23_audio_vae_bf16.safetensors"
    assert api["preview_vae"]["inputs"]["vae_name"] == "taeltx2_3.safetensors"
    assert api["unet"]["inputs"]["unet_name"] == "ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors"
    assert api["video"]["inputs"]["video"] == "ltx_smoke_guide.mp4"
    assert api["video"]["inputs"]["file"] == "ltx_smoke_guide.mp4"
    assert api["audio_norm_vibe_audio"]["class_type"] == "LoadAudio"
    assert api["audio_norm"]["inputs"]["audio"] == ["audio_norm_vibe_audio", 0]
    assert api["scheduler"]["inputs"]["steps"] == 1
    assert "upscale" not in api
    assert "upscale_model" not in api
    assert api["upscale_sink"]["inputs"]["latent"] == ["latent", 0]


def test_runpod_remote_patch_policy_handles_ace_step_audio() -> None:
    api = {
        "clip": {"class_type": "DualCLIPLoader", "inputs": {"widget_0": "a.safetensors", "widget_1": "b.safetensors", "widget_2": "ace"}},
        "vae": {"class_type": "VAELoader", "inputs": {"widget_0": "ace_1.5_vae.safetensors"}},
        "latent": {"class_type": "EmptyAceStep1.5LatentAudio", "inputs": {"seconds": ["110", 0], "widget_1": 1}},
        "110": {"class_type": "PrimitiveFloat", "inputs": {"widget_0": 120}},
        "126": {"class_type": "PrimitiveNode", "inputs": {"widget_0": 1}},
        "model": {"class_type": "UNETLoader", "inputs": {"widget_0": "acestep_v1.5_turbo.safetensors", "widget_1": "default"}},
        "shift": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["model", 0], "widget_0": 3}},
        "text": {
            "class_type": "TextEncodeAceStepAudio1.5",
            "inputs": {"clip": ["clip", 0], "seed": ["126", 0], "duration": ["110", 0], "widget_0": "tags", "widget_1": "lyrics"},
        },
        "neg": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["text", 0]}},
        "sample": {
            "class_type": "KSampler",
            "inputs": {"model": ["shift", 0], "positive": ["text", 0], "negative": ["neg", 0], "latent_image": ["latent", 0], "seed": ["126", 0]},
        },
        "decode": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["sample", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveAudioMP3", "inputs": {"audio": ["decode", 0], "widget_0": "audio/out", "widget_1": "V0"}},
    }

    assert patch_workflow_api("ace_step_1_5_t2a_song", api) is True

    assert "126" not in api
    assert "110" not in api
    assert api["clip"]["inputs"]["clip_name1"] == "a.safetensors"
    assert api["vae"]["inputs"] == {"vae_name": "ace_1.5_vae.safetensors"}
    assert api["latent"]["inputs"]["seconds"] == 2
    assert api["text"]["inputs"]["duration"] == 2
    assert api["text"]["inputs"]["bpm"] == 120
    assert api["text"]["inputs"]["top_p"] == 0.85
    assert api["text"]["inputs"]["min_p"] == 0.9
    assert api["text"]["inputs"]["top_k"] == 0
    assert api["text"]["inputs"]["temperature"] == 0
    assert api["sample"]["inputs"]["steps"] == 1
    assert api["save"]["inputs"]["filename_prefix"] == "audio/out"


def test_runpod_remote_patch_policy_handles_gguf() -> None:
    api = {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux-2-klein-9b.safetensors"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "full_encoder_small_decoder.safetensors"}},
    }

    assert patch_workflow_api("flux2_klein_9b_gguf_t2i", api) is True

    assert api["unet"]["class_type"] == "UnetLoaderGGUF"
    assert api["unet"]["inputs"]["unet_name"] == GGUF_MODEL
    assert api["vae"]["inputs"]["vae_name"] == "flux2-vae.safetensors"


def _ltx_api() -> dict[str, dict]:
    return {
        "3059": {"class_type": "EmptyLTXVLatentVideo", "inputs": {}},
        "4979": {"class_type": "Node", "inputs": {}},
        "4978": {"class_type": "Node", "inputs": {}},
        "1241": {"class_type": "Node", "inputs": {}},
        "3980": {"class_type": "Node", "inputs": {}},
        "4977": {"class_type": "Node", "inputs": {}},
        "2004": {"class_type": "LoadImage", "inputs": {}},
        "4981": {"class_type": "Node", "inputs": {}},
        "4010": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "ltx-2.3-22b-dev.safetensors"}},
        "3940": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "ltx-2.3-22b-dev.safetensors"}},
        "text_encoder": {"class_type": "CLIPLoader", "inputs": {"clip_name": "comfy_gemma_3_12B_it.safetensors"}},
    }
