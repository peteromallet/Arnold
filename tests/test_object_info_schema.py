from __future__ import annotations

from vibecomfy.porting.object_info import (
    class_defaults,
    class_has_list_output,
    class_input_types,
    class_output_count,
    get_class,
    output_names,
)


def test_offline_object_info_cache_exposes_core_defaults_types_and_outputs() -> None:
    schema = get_class("KSampler")

    assert schema is not None
    assert class_defaults("KSampler")["steps"] == 20
    assert class_defaults("KSampler")["denoise"] == 1.0
    assert class_input_types("KSampler")["latent_image"] == "LATENT"
    assert output_names("KSampler") == ["LATENT"]
    assert class_output_count("KSampler") == 1
    assert class_has_list_output("KSampler") is False


def test_offline_object_info_cache_exposes_custom_pack_schema() -> None:
    schema = get_class("WanVideoSampler")

    assert schema is not None
    assert schema["pack"] == "ComfyUI-WanVideoWrapper"
    assert "steps" in class_input_types("WanVideoSampler")
    assert class_output_count("WanVideoSampler") >= 1


def test_curated_output_fallback_repairs_dual_clip_loader_gguf_zero_output_cache_entry() -> None:
    schema = get_class("DualCLIPLoaderGGUF")

    assert schema is not None
    assert output_names("DualCLIPLoaderGGUF") == ["CLIP"]
    assert class_output_count("DualCLIPLoaderGGUF") == 1
    assert class_has_list_output("DualCLIPLoaderGGUF") is False


def test_offline_object_info_cache_marks_list_outputs() -> None:
    list_output_classes = [
        class_type
        for class_type in ("CreateList", "RebatchImages", "ImageTransformKJ")
        if get_class(class_type) is not None
    ]

    assert list_output_classes
    assert any(class_has_list_output(class_type) for class_type in list_output_classes)
