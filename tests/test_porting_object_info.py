"""Deterministic tests for object-info serializer, consumer, and widget-order reconciliation.

No ComfyUI / RunPod / network required.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from vibecomfy.porting.object_info.consume import CACHE_DIR as _PROD_CACHE_DIR, effective_widget_names_for_class
from vibecomfy.porting.object_info.serialize import build_cache, pack_key_from_module, refresh_from_source
from vibecomfy.porting.widget_schema import WIDGET_SCHEMA


# ---------------------------------------------------------------------------
# Minimal object_info fixtures
# ---------------------------------------------------------------------------

_SAMPLE_OBJECT_INFO: dict = {
    "LTX2_NAG": {
        "python_module": "ComfyUI-KJNodes.nodes.ltxv_nodes",
        "name": "LTX2_NAG",
        "display_name": "NAG",
        "description": "Neural Adaptive Guidance for LTX2",
        "category": "LTXVideo/patches",
        "function": "patch",
        "input": {
            "required": {
                "model": ["MODEL"],
                "nag_scale": ["FLOAT", {"default": 11.0, "min": 0.5, "max": 50.0, "step": 0.25}],
                "nag_alpha": ["FLOAT", {"default": 0.25, "min": 0.05, "max": 4.0, "step": 0.01}],
                "nag_tau": ["FLOAT", {"default": 2.5, "min": 0.5, "max": 20.0, "step": 0.01}],
                "apply_to_all": ["BOOLEAN", {"default": True}],
            },
        },
        "input_order": {
            "required": ["model", "nag_scale", "nag_alpha", "nag_tau", "apply_to_all"],
            "optional": [],
        },
        "output": ["MODEL"],
        "output_name": ["MODEL"],
        "output_is_list": [False],
    },
    "PrimitiveString": {
        "python_module": "comfy_extras.nodes_primitives",
        "name": "PrimitiveString",
        "category": "",
        "function": "string",
        "display_name": "PrimitiveString",
        "description": "",
        "input": {
            "required": {"value": ["STRING", {"multiline": "", "default": ""}]},
        },
        "input_order": {"required": ["value"], "optional": []},
        "output": ["STRING"],
        "output_name": ["STRING"],
        "output_is_list": [False],
    },
    "SomeUnknownClass": {
        "python_module": "ComfyUI-KJNodes.nodes.unknown",
        "name": "SomeUnknownClass",
        "display_name": "Unknown",
        "description": "",
        "category": "misc",
        "function": "do_thing",
        "input": {
            "required": {
                "model": ["MODEL"],
                "widget_0": ["INT", {"default": 5}],
                "widget_1": ["FLOAT", {"default": 0.5}],
            },
            "optional": {"widget_2": ["STRING", {"default": "hello"}]},
        },
        "input_order": {
            "required": ["model", "widget_0", "widget_1"],
            "optional": ["widget_2"],
        },
        "output": ["MODEL"],
        "output_name": ["patched_model"],
        "output_is_list": [False],
    },
}


def _build_temp_cache(tmp_path: Path) -> Path:
    """Build object_info cache in *tmp_path* and return the cache root."""
    source = tmp_path / "object_info.json"
    source.write_text(json.dumps(_SAMPLE_OBJECT_INFO), encoding="utf-8")
    cache_root = tmp_path / "object_info"
    build_cache(str(source), version="test", cache_dir=str(cache_root))
    return cache_root


# ---------------------------------------------------------------------------
# pack_key_from_module
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "python_module, expected",
    [
        ("ComfyUI-KJNodes.nodes.ltxv_nodes", "ComfyUI-KJNodes"),
        ("ComfyUI-LTXVideo", "ComfyUI-LTXVideo"),
        ("custom_nodes.some_pack.nodes", "custom_nodes.some_pack"),
        ("nodes", "nodes"),
        (".", "comfy_core"),
        ("", "comfy_core"),
    ],
)
def test_pack_key_from_module(python_module: str, expected: str) -> None:
    assert pack_key_from_module(python_module) == expected


# ---------------------------------------------------------------------------
# build_cache (serialize)
# ---------------------------------------------------------------------------


def test_build_cache_creates_per_pack_files_and_index(tmp_path: Path) -> None:
    source = tmp_path / "object_info.json"
    source.write_text(json.dumps(_SAMPLE_OBJECT_INFO), encoding="utf-8")
    cache_root = tmp_path / "cache_obj"

    class_count, pack_count = build_cache(str(source), version="test", cache_dir=str(cache_root))

    assert class_count == 3
    assert pack_count == 2  # ComfyUI-KJNodes + comfy_extras

    # Check index.json exists
    index_file = cache_root / "index.json"
    assert index_file.is_file()
    index = json.loads(index_file.read_text())
    assert index["LTX2_NAG"] == "ComfyUI-KJNodes@test.json"
    assert index["SomeUnknownClass"] == "ComfyUI-KJNodes@test.json"
    assert index["PrimitiveString"] == "comfy_extras@test.json"

    # Check per-pack files exist and are valid JSON
    pack_file = cache_root / "ComfyUI-KJNodes@test.json"
    assert pack_file.is_file()
    pack_data = json.loads(pack_file.read_text())
    assert "LTX2_NAG" in pack_data
    assert "SomeUnknownClass" in pack_data
    assert pack_data["LTX2_NAG"]["object_info_widget_order"] == [
        None,  # model is MODEL (excluded)
        "nag_scale",
        "nag_alpha",
        "nag_tau",
        "apply_to_all",
    ]

    pack_file2 = cache_root / "comfy_extras@test.json"
    assert pack_file2.is_file()
    pack_data2 = json.loads(pack_file2.read_text())
    assert "PrimitiveString" in pack_data2


def test_build_cache_is_deterministic(tmp_path: Path) -> None:
    """Running build_cache twice with the same input must produce identical output."""
    source = tmp_path / "object_info.json"
    source.write_text(json.dumps(_SAMPLE_OBJECT_INFO), encoding="utf-8")

    cache1 = tmp_path / "cache1"
    cache2 = tmp_path / "cache2"

    build_cache(str(source), version="test", cache_dir=str(cache1))
    build_cache(str(source), version="test", cache_dir=str(cache2))

    idx1 = json.loads((cache1 / "index.json").read_text())
    idx2 = json.loads((cache2 / "index.json").read_text())
    assert idx1 == idx2

    for name in idx1.values():
        assert json.loads((cache1 / name).read_text()) == json.loads((cache2 / name).read_text())


def test_refresh_from_source(tmp_path: Path) -> None:
    source = tmp_path / "object_info.json"
    source.write_text(json.dumps(_SAMPLE_OBJECT_INFO), encoding="utf-8")
    cache_root = tmp_path / "refresh_cache"

    result = refresh_from_source(str(source), cache_dir=str(cache_root))
    assert result["status"] == "ok"
    assert result["classes_indexed"] == 3
    assert result["packs_written"] == 2
    assert result["version"] == "runpod-snapshot"


# ---------------------------------------------------------------------------
# consume module (monkeypatched to use temp cache)
# ---------------------------------------------------------------------------


def test_get_class_returns_correct_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    from vibecomfy.porting.object_info.consume import get_class as gc

    entry = gc("LTX2_NAG")
    assert entry is not None
    assert entry["pack"] == "ComfyUI-KJNodes"
    assert entry["pack_version"] == "runpod-snapshot"
    assert entry["function"] == "patch"
    assert entry["object_info_widget_order"] == [None, "nag_scale", "nag_alpha", "nag_tau", "apply_to_all"]

    assert gc("NonExistentClass") is None


def test_object_info_widget_order_filters_link_sockets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    from vibecomfy.porting.object_info.consume import object_info_widget_order as oiwo

    order = oiwo("LTX2_NAG")
    assert order == [None, "nag_scale", "nag_alpha", "nag_tau", "apply_to_all"]

    order2 = oiwo("PrimitiveString")
    assert order2 == ["value"]

    assert oiwo("NonExistentClass") == []


def test_output_names_and_types(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    from vibecomfy.porting.object_info.consume import output_names as on_, output_types as ot_

    assert on_("LTX2_NAG") == ["MODEL"]
    assert ot_("LTX2_NAG") == ["MODEL"]
    assert on_("PrimitiveString") == ["STRING"]
    assert on_("NonExistentClass") == []
    assert on_("SomeUnknownClass") == ["patched_model"]
    assert ot_("SomeUnknownClass") == ["MODEL"]


def test_list_classes_and_stats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    from vibecomfy.porting.object_info.consume import cache_stats, list_classes as lc

    classes = lc()
    assert isinstance(classes, list)
    assert len(classes) == 3
    assert classes == sorted(classes)
    assert "LTX2_NAG" in classes
    assert "PrimitiveString" in classes
    assert "SomeUnknownClass" in classes

    stats = cache_stats()
    assert stats["total_classes"] == 3
    assert stats["packs_cached"] == 0  # lazy — packs loaded on demand


# ---------------------------------------------------------------------------
# effective_widget_names_for_class (widget_schema tiered lookup)
# ---------------------------------------------------------------------------


def test_effective_widget_names_uses_curated_schema_over_object_info(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    curated = WIDGET_SCHEMA.get("LTX2_NAG")
    assert curated is not None, "LTX2_NAG must be in WIDGET_SCHEMA"

    names = effective_widget_names_for_class("LTX2_NAG", allow_object_info_fallback=True)
    assert names == curated

    from vibecomfy.porting.object_info.consume import object_info_widget_order as oiwo

    raw = oiwo("LTX2_NAG")
    assert raw != names, "curated order must differ from object_info raw order"


def test_effective_widget_names_fallback_to_object_info(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    assert "SomeUnknownClass" not in WIDGET_SCHEMA

    names_no = effective_widget_names_for_class("SomeUnknownClass", allow_object_info_fallback=False)
    assert names_no == []

    names_yes = effective_widget_names_for_class("SomeUnknownClass", allow_object_info_fallback=True)
    assert names_yes == [None, "widget_0", "widget_1", "widget_2"]


def test_effective_widget_names_unknown_class(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    assert effective_widget_names_for_class("TotallyFakeClass", allow_object_info_fallback=False) == []
    assert effective_widget_names_for_class("TotallyFakeClass", allow_object_info_fallback=True) == []


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _patch_consume_paths(monkeypatch: pytest.MonkeyPatch, cache_root: Path) -> None:
    """Point the consumer module at a temp cache directory and reset internal state."""
    import vibecomfy.porting.object_info.consume as _consume

    monkeypatch.setattr(_consume, "CACHE_DIR", cache_root)
    monkeypatch.setattr(_consume, "INDEX_PATH", cache_root / "index.json")
    monkeypatch.setattr(_consume, "_index", None)
    monkeypatch.setattr(_consume, "_pack_cache", {})
