from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from vibecomfy.ingest.index import index_workflows
from vibecomfy.ingest.normalize import convert_to_vibe_format, detect_workflow_shape, normalize_to_api
from vibecomfy.registry.library import load_workflow_reference, workflow_from_template
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


def test_workflow_from_template_reads_external_index_when_official_exists(tmp_path: Path, monkeypatch) -> None:
    official = tmp_path / "official.json"
    external = tmp_path / "external_only.json"
    official.write_text(json.dumps({"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "official"}}}), encoding="utf-8")
    external.write_text(json.dumps({"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "external"}}}), encoding="utf-8")
    (tmp_path / "template_index.json").write_text(
        json.dumps([{"id": "official-only", "path": str(official), "source": "official"}]),
        encoding="utf-8",
    )
    (tmp_path / "external_workflow_index.json").write_text(
        json.dumps([{"id": "external-only", "path": str(external), "source": "external"}]),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    workflow = workflow_from_template("external-only")

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
    (tmp_path / "template_index.json").write_text(
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
