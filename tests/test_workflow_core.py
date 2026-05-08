from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from vibecomfy.ingest.index import index_workflows
from vibecomfy.ingest.normalize import convert_to_vibe_format, detect_workflow_shape, normalize_to_api
from vibecomfy.registry.library import load_workflow_reference, workflow_from_id
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def test_api_workflow_converts_to_vibe_workflow() -> None:
    raw = {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}},
        "2": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 4, "positive": ["1", 0]}},
        "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0]}},
    }

    assert detect_workflow_shape(raw) == "api"
    workflow = convert_to_vibe_format(normalize_to_api(raw), workflow_id="sample")

    assert workflow.id == "sample"
    assert workflow.validate().ok
    assert "prompt" in workflow.inputs
    workflow.set_prompt("new").set_seed(42).set_steps(8)
    api = workflow.compile()
    assert api["1"]["inputs"]["text"] == "new"
    assert api["2"]["inputs"]["seed"] == 42
    assert api["2"]["inputs"]["steps"] == 8
    assert api["2"]["inputs"]["positive"] == ["1", 0]


def test_prompt_override_does_not_bind_conditioning_inputs() -> None:
    raw = {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}},
        "2": {"class_type": "CFGGuider", "inputs": {"positive": {"pooled": []}, "cfg": 5.0}},
        "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0]}},
    }

    workflow = convert_to_vibe_format(raw, workflow_id="conditioning")

    assert workflow.inputs["prompt"].node_id == "1"
    workflow.set_prompt("new")
    api = workflow.compile()
    assert api["1"]["inputs"]["text"] == "new"
    assert api["2"]["inputs"]["positive"] == {"pooled": []}


def test_ui_workflow_normalizes_to_api() -> None:
    raw = {
        "nodes": [
            {"id": 1, "type": "CLIPTextEncode", "widgets_values": ["hello"], "inputs": []},
            {"id": 2, "type": "SaveImage", "inputs": [{"name": "images", "link": 1}]},
        ],
        "links": [[1, 1, 0, 2, 0, "IMAGE"]],
    }

    assert detect_workflow_shape(raw) == "ui"
    api = normalize_to_api(raw)
    assert api["1"]["class_type"] == "CLIPTextEncode"
    assert api["2"]["inputs"]["images"] == ["1", 0]


@pytest.mark.skipif(
    importlib.util.find_spec("comfy_execution") is None,
    reason="GraphBuilder backend requires the installed HiddenSwitch ComfyUI runtime.",
)
def test_graphbuilder_backend_matches_api_backend() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "SourceNode", inputs={"value": 1})
    workflow.nodes["2"] = VibeNode("2", "SinkNode", inputs={})
    workflow.connect("1.0", "2.input")

    assert workflow.compile("graphbuilder") == workflow.compile("api")


def test_explicit_inputs_override_imported_widget_values_at_compile_time() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "LoadImage",
        inputs={"widget_0": "scratchpad.png", "image": "scratchpad.png"},
        widgets={"widget_0": "imported.png"},
    )

    api = workflow.compile("api")

    assert api["1"]["inputs"]["widget_0"] == "scratchpad.png"
    assert api["1"]["inputs"]["image"] == "scratchpad.png"


def test_compile_drops_video_preview_ui_payloads() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "VHS_VideoCombine",
        inputs={
            "images": ["2", 0],
            "videopreview": {
                "hidden": False,
                "params": {"filename": "preview.mp4"},
                "paused": False,
            },
        },
    )

    api = workflow.compile("api")

    assert "videopreview" not in api["1"]["inputs"]
    assert api["1"]["inputs"]["images"] == ["2", 0]


def test_compile_drops_null_prompt_inputs() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "ImageConcatMulti",
        inputs={
            "image_1": ["2", 0],
            "image_2": ["3", 0],
            "widget_3": None,
        },
    )

    api = workflow.compile("api")

    assert "widget_3" not in api["1"]["inputs"]
    assert api["1"]["inputs"]["image_1"] == ["2", 0]


def test_compile_drops_note_nodes_from_api_prompt() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "Note", inputs={"widget_0": "editor-only note"})
    workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={"images": ["3", 0]})

    api = workflow.compile("api")

    assert "1" not in api
    assert api["2"]["class_type"] == "SaveImage"


def test_compile_drops_markdown_note_nodes_from_api_prompt() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "MarkdownNote", inputs={"widget_0": "editor-only note"})
    workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={"images": ["3", 0]})

    api = workflow.compile("api")

    assert "1" not in api
    assert api["2"]["class_type"] == "SaveImage"


def test_compile_rewrites_set_get_nodes_to_direct_links() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    workflow.nodes["2"] = VibeNode(
        "2",
        "SetNode",
        inputs={"IMAGE": ["1", 0], "widget_0": "reference_image"},
    )
    workflow.nodes["3"] = VibeNode("3", "GetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["4"] = VibeNode("4", "SaveImage", inputs={})
    workflow.connect("3.0", "4.images")

    api = workflow.compile("api")

    assert set(api) == {"1", "4"}
    assert api["4"]["inputs"]["images"] == ["1", 0]


def test_compile_rewrites_edge_fed_set_get_nodes_to_direct_links() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    workflow.nodes["2"] = VibeNode("2", "SetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["3"] = VibeNode("3", "GetNode", inputs={"widget_0": "reference_image"})
    workflow.nodes["4"] = VibeNode("4", "SaveImage", inputs={"images": ["3", 0]})
    workflow.connect("1.0", "2.IMAGE")

    api = workflow.compile("api")

    assert set(api) == {"1", "4"}
    assert api["4"]["inputs"]["images"] == ["1", 0]


def test_compile_adds_named_inputs_for_known_custom_node_widgets() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "WanVideoImageToVideoEncode",
        inputs={
            "widget_0": 832,
            "widget_1": 480,
            "widget_2": 81,
            "widget_3": 0,
            "widget_4": 1,
            "widget_5": 1,
            "widget_6": True,
        },
    )
    workflow.nodes["2"] = VibeNode("2", "INTConstant", inputs={"widget_0": 6})
    workflow.nodes["3"] = VibeNode(
        "3",
        "WanVideoLoraSelect",
        inputs={
            "widget_0": "WanVideo\\Lightx2v\\example.safetensors",
            "widget_1": 1.0,
            "widget_2": False,
            "widget_3": False,
        },
    )

    api = workflow.compile("api")

    assert api["1"]["inputs"]["width"] == 832
    assert api["1"]["inputs"]["height"] == 480
    assert api["1"]["inputs"]["num_frames"] == 81
    assert api["1"]["inputs"]["noise_aug_strength"] == 0
    assert api["1"]["inputs"]["start_latent_strength"] == 1
    assert api["1"]["inputs"]["end_latent_strength"] == 1
    assert api["1"]["inputs"]["force_offload"] is True
    assert api["2"]["inputs"]["value"] == 6
    assert api["3"]["inputs"]["lora"] == "WanVideo\\Lightx2v\\example.safetensors"
    assert api["3"]["inputs"]["strength"] == 1.0


def test_wan_video_sampler_aliases_skip_seed_control_widget() -> None:
    workflow = VibeWorkflow("test", WorkflowSource("test"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "WanVideoSampler",
        inputs={
            "model": ["2", 0],
            "image_embeds": ["3", 0],
            "widget_0": 6,
            "widget_1": 1,
            "widget_2": 8,
            "widget_3": 43,
            "widget_4": "fixed",
            "widget_5": True,
            "widget_6": "dpm++_sde",
            "widget_7": 0,
            "widget_8": 1,
            "widget_9": False,
            "widget_10": "comfy",
            "widget_11": 0,
            "widget_12": 10,
            "widget_13": "",
        },
    )

    api = workflow.compile("api")

    assert api["1"]["inputs"]["seed"] == 43
    assert api["1"]["inputs"]["force_offload"] is True
    assert api["1"]["inputs"]["scheduler"] == "dpm++_sde"
    assert api["1"]["inputs"]["batched_cfg"] is False
    assert api["1"]["inputs"]["rope_function"] == "comfy"
    assert api["1"]["inputs"]["start_step"] == 0
    assert api["1"]["inputs"]["end_step"] == 10
    assert "add_noise_to_samples" not in api["1"]["inputs"]


def test_official_index_uses_package_manifest_metadata(tmp_path: Path) -> None:
    repo = tmp_path / "workflow_templates"
    templates = repo / "templates"
    package = repo / "packages" / "starter"
    templates.mkdir(parents=True)
    package.mkdir(parents=True)
    (templates / "default.json").write_text(json.dumps({"nodes": [], "links": []}), encoding="utf-8")
    (package / "manifest.json").write_text(
        json.dumps({"id": "starter-pack", "workflows": ["templates/default.json"]}),
        encoding="utf-8",
    )

    rows = index_workflows(repo)

    assert rows == [
        {
            "id": "default",
            "path": str(templates / "default.json"),
            "source": "official",
            "media_type": "unknown",
            "package_id": "starter-pack",
            "manifest_path": str(package / "manifest.json"),
        }
    ]


def test_workflow_from_id_reads_external_index_when_official_exists(tmp_path: Path, monkeypatch) -> None:
    official = tmp_path / "official.json"
    external = tmp_path / "external_only.json"
    official.write_text(json.dumps({"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "official"}}}), encoding="utf-8")
    external.write_text(json.dumps({"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "external"}}}), encoding="utf-8")
    (tmp_path / "workflow_index.json").write_text(
        json.dumps([{"id": "official-only", "path": str(official), "source": "official"}]),
        encoding="utf-8",
    )
    (tmp_path / "external_workflow_index.json").write_text(
        json.dumps([{"id": "external-only", "path": str(external), "source": "external"}]),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    workflow = workflow_from_id("external-only")

    assert workflow.id == "external-only"
    assert workflow.nodes["1"].inputs["text"] == "external"


def test_load_workflow_reference_handles_json_path_index_id_and_scratchpad(tmp_path: Path, monkeypatch) -> None:
    workflow_json = tmp_path / "workflow.json"
    indexed_json = tmp_path / "indexed.json"
    scratchpad = tmp_path / "scratchpad.py"
    workflow_json.write_text(json.dumps({"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "path"}}}), encoding="utf-8")
    indexed_json.write_text(json.dumps({"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "indexed"}}}), encoding="utf-8")
    scratchpad.write_text(
        "\n".join(
            [
                "from vibecomfy.workflow import VibeWorkflow, WorkflowSource",
                "def build():",
                "    workflow = VibeWorkflow('scratchpad', WorkflowSource('scratchpad'))",
                "    return workflow",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "workflow_index.json").write_text(
        json.dumps([{"id": "indexed", "path": str(indexed_json), "source": "official"}]),
        encoding="utf-8",
    )
    (tmp_path / "external_workflow_index.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from_path = load_workflow_reference(str(workflow_json), allow_scratchpad=True)
    from_index = load_workflow_reference("indexed", allow_scratchpad=True)
    from_scratchpad = load_workflow_reference(str(scratchpad), allow_scratchpad=True)

    assert from_path.nodes["1"].inputs["text"] == "path"
    assert from_index.id == "indexed"
    assert from_index.nodes["1"].inputs["text"] == "indexed"
    assert from_scratchpad.id == "scratchpad"
