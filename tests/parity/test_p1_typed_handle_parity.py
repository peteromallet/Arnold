from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.workflow import VibeWorkflow

ROOT = Path(__file__).resolve().parents[2]

ANCHORS = (
    (
        "audio/ace_step_1_5_t2a_song",
        "ready_templates.audio.ace_step_1_5_t2a_song",
        "tests/parity/fixtures/ace_step_1_5_t2a_song_typed.py",
    ),
    (
        "edit/flux2_klein_4b_image_edit_distilled",
        "ready_templates.edit.flux2_klein_4b_image_edit_distilled",
        "tests/parity/fixtures/flux2_klein_4b_image_edit_distilled_typed.py",
    ),
    (
        "image/flux2_klein_4b_t2i",
        "ready_templates.image.flux2_klein_4b_t2i",
        "tests/parity/fixtures/flux2_klein_4b_t2i_typed.py",
    ),
    (
        "image/flux2_klein_9b_gguf_t2i",
        "ready_templates.image.flux2_klein_9b_gguf_t2i",
        "tests/parity/fixtures/flux2_klein_9b_gguf_t2i_typed.py",
    ),
    (
        "image/z_image",
        "ready_templates.image.z_image",
        "tests/parity/fixtures/z_image_typed.py",
    ),
    (
        "edit/qwen_image_edit",
        "ready_templates.edit.qwen_image_edit",
        "tests/parity/fixtures/qwen_image_edit_typed.py",
    ),
    (
        "video/ltx2_3_i2v",
        "ready_templates.video.ltx2_3_i2v",
        "tests/parity/fixtures/ltx2_3_i2v_typed.py",
    ),
    (
        "video/ltx2_3_t2v",
        "ready_templates.video.ltx2_3_t2v",
        "tests/parity/fixtures/ltx2_3_t2v_typed.py",
    ),
    (
        "video/wan_i2v",
        "ready_templates.video.wan_i2v",
        "tests/parity/fixtures/wan_i2v_typed.py",
    ),
    (
        "video/wan_t2v",
        "ready_templates.video.wan_t2v",
        "tests/parity/fixtures/wan_t2v_typed.py",
    ),
)
"""Parity anchors cover snapshot stems plus the preserved audio anchor."""


@pytest.mark.parametrize(("template_id", "ready_module", "typed_module"), ANCHORS)
def test_typed_handle_fixture_has_valid_self_shape(template_id: str, ready_module: str, typed_module: str) -> None:
    workflow = _build(typed_module)
    canonical = _canonical_api(workflow.compile("api"))

    assert workflow.id == template_id
    assert canonical
    assert all(node["class_type"] != "MarkdownNote" for node in canonical)
    _assert_links_target_existing_nodes(canonical)


@pytest.mark.parametrize(("template_id", "ready_module", "typed_module"), ANCHORS)
def test_typed_handle_fixture_matches_graphbuilder(template_id: str, ready_module: str, typed_module: str) -> None:
    if importlib.util.find_spec("comfy_execution") is None:
        pytest.skip("GraphBuilder backend requires the installed HiddenSwitch ComfyUI runtime.")
    workflow = _build(typed_module)

    assert workflow.compile("graphbuilder") == workflow.compile("api")


@pytest.mark.parametrize(("template_id", "ready_module", "typed_module"), ANCHORS)
def test_typed_handle_fixture_matches_ready_template_corpus(
    template_id: str, ready_module: str, typed_module: str
) -> None:
    original = _build(ready_module)
    typed = _build(typed_module)

    assert _canonical_api(typed.compile("api")) == _canonical_api(original.compile("api"))


def _build(module_name: str) -> VibeWorkflow:
    if module_name.endswith(".py"):
        module_path = ROOT / module_name
        spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        workflow = module.build()
        assert isinstance(workflow, VibeWorkflow)
        return workflow
    module = importlib.import_module(module_name)
    workflow = module.build()
    assert isinstance(workflow, VibeWorkflow)
    return workflow


def _canonical_api(api: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    kept_ids = [node_id for node_id, node in api.items() if node.get("class_type") != "MarkdownNote"]
    id_map = {node_id: str(index + 1) for index, node_id in enumerate(kept_ids)}
    canonical: list[dict[str, Any]] = []
    for node_id in kept_ids:
        node = api[node_id]
        canonical.append(
            {
                "id": id_map[node_id],
                "class_type": node["class_type"],
                "inputs": _canonical_value(node.get("inputs", {}), id_map),
            }
        )
    return canonical


def _canonical_value(value: Any, id_map: dict[str, str]) -> Any:
    if isinstance(value, list):
        if len(value) == 2 and str(value[0]) in id_map and isinstance(value[1], int):
            return [id_map[str(value[0])], value[1]]
        return [_canonical_value(item, id_map) for item in value]
    if isinstance(value, dict):
        return {key: _canonical_value(item, id_map) for key, item in sorted(value.items())}
    return value


def _assert_links_target_existing_nodes(canonical: list[dict[str, Any]]) -> None:
    node_ids = {node["id"] for node in canonical}
    for node in canonical:
        for value in node["inputs"].values():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[1], int):
                assert value[0] in node_ids
