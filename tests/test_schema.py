from __future__ import annotations

import asyncio
import json

import pytest

from vibecomfy.ingest.normalize import normalize_to_api
from vibecomfy.schema import (
    InputSpec,
    LocalSchemaProvider,
    NodeSchema,
    OutputSpec,
    RuntimeSchemaProvider,
    SchemaIndexError,
    SourceSchemaProvider,
    get_schema_provider,
    schema_for,
    schema_registry_empty,
    schemas_for,
)
from vibecomfy.schema.cache import load_object_info_cache
from vibecomfy.workflow import ValidationIssue, VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


class FakeSchemaProvider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self.schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.schemas.get(class_type)


class LegacyGetSchemaProvider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _workflow(*nodes: VibeNode, edges: list[VibeEdge] | None = None) -> VibeWorkflow:
    workflow = VibeWorkflow("schema-test", WorkflowSource("schema-test"))
    workflow.nodes = {node.id: node for node in nodes}
    workflow.edges = edges or []
    return workflow


def _schema(
    class_type: str,
    *,
    inputs: dict[str, InputSpec] | None = None,
    outputs: list[OutputSpec] | None = None,
) -> NodeSchema:
    return NodeSchema(class_type=class_type, pack=None, inputs=inputs or {}, outputs=outputs or [])


def _only_issue(workflow: VibeWorkflow, provider: FakeSchemaProvider) -> ValidationIssue:
    report = workflow.validate(schema_provider=provider)
    assert len(report.issues) == 1
    issue = report.issues[0]
    assert isinstance(issue, ValidationIssue)
    return issue


def test_schema_validation_reports_unknown_class_type() -> None:
    issue = _only_issue(_workflow(VibeNode("1", "MissingNode")), FakeSchemaProvider({}))

    assert issue.code == "unknown_class_type"
    assert issue.severity == "error"


def test_schema_validation_reports_missing_required_input() -> None:
    provider = FakeSchemaProvider({"PromptNode": _schema("PromptNode", inputs={"text": InputSpec("STRING", required=True)})})
    issue = _only_issue(_workflow(VibeNode("1", "PromptNode")), provider)

    assert issue.code == "missing_required_input"
    assert issue.severity == "error"
    assert "text" in issue.message


def test_schema_validation_reports_unknown_input() -> None:
    provider = FakeSchemaProvider({"PromptNode": _schema("PromptNode", inputs={"text": InputSpec("STRING")})})
    issue = _only_issue(_workflow(VibeNode("1", "PromptNode", inputs={"extra": "value"})), provider)

    assert issue.code == "unknown_input"
    assert issue.severity == "error"


def test_schema_validation_reports_type_mismatch_as_warning() -> None:
    provider = FakeSchemaProvider(
        {
            "ImageSource": _schema("ImageSource", outputs=[OutputSpec("IMAGE", "image")]),
            "LatentSink": _schema("LatentSink", inputs={"latent": InputSpec("LATENT", required=True)}),
        }
    )
    workflow = _workflow(
        VibeNode("1", "ImageSource"),
        VibeNode("2", "LatentSink"),
        edges=[VibeEdge("1", "0", "2", "latent")],
    )
    issue = _only_issue(workflow, provider)

    assert issue.code == "type_mismatch"
    assert issue.severity == "warning"


def test_schema_validation_reports_invalid_output_index_as_error() -> None:
    provider = FakeSchemaProvider(
        {
            "TwoOutputSource": _schema("TwoOutputSource", outputs=[OutputSpec("LATENT"), OutputSpec("AUDIO")]),
            "LatentSink": _schema("LatentSink", inputs={"latent": InputSpec("LATENT", required=True)}),
        }
    )
    workflow = _workflow(
        VibeNode("1", "TwoOutputSource"),
        VibeNode("2", "LatentSink"),
        edges=[VibeEdge("1", "2", "2", "latent")],
    )
    issue = _only_issue(workflow, provider)

    assert issue.code == "invalid_output_index"
    assert issue.severity == "error"
    assert issue.detail["output_count"] == 2


def test_validate_without_schema_provider_remains_structural_only() -> None:
    workflow = _workflow(
        VibeNode("1", "CLIPTextEncode", inputs={"text": "old"}),
        VibeNode("2", "KSampler", inputs={"seed": 1, "steps": 4}),
        VibeNode("3", "SaveImage"),
        edges=[VibeEdge("1", "0", "2", "positive"), VibeEdge("2", "0", "3", "images")],
    )

    report = workflow.validate()
    explicit_none_report = workflow.validate(schema_provider=None)

    assert report.ok
    assert explicit_none_report.ok
    assert report.issues == explicit_none_report.issues == []


def test_normalize_to_api_maps_widgets_to_schema_input_names() -> None:
    provider = FakeSchemaProvider(
        {
            "PromptNode": _schema(
                "PromptNode",
                inputs={
                    "text": InputSpec("STRING"),
                    "clip": InputSpec("CLIP"),
                    "ckpt_name": InputSpec("STRING"),
                },
            )
        }
    )
    raw = {
        "nodes": [
            {
                "id": 1,
                "type": "PromptNode",
                "widgets_values": ["hello", "model.safetensors"],
                "inputs": [],
            }
        ],
        "links": [],
    }

    api = normalize_to_api(raw, schema_provider=provider)

    assert api["1"]["inputs"] == {"text": "hello", "ckpt_name": "model.safetensors"}


def test_normalize_to_api_uses_widget_only_schema_so_link_inputs_do_not_shift_positions() -> None:
    provider = FakeSchemaProvider(
        {
            "CheckpointLoaderSimple": _schema(
                "CheckpointLoaderSimple",
                inputs={
                    "model": InputSpec("MODEL"),
                    "clip": InputSpec("CLIP"),
                    "ckpt_name": InputSpec("STRING"),
                },
            )
        }
    )
    raw = {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "widgets_values": ["model.safetensors"],
                "inputs": [],
            }
        ],
        "links": [],
    }

    api = normalize_to_api(raw, schema_provider=provider)

    assert api["1"]["inputs"] == {"ckpt_name": "model.safetensors"}


def test_normalize_to_api_without_schema_provider_preserves_widget_keys() -> None:
    raw = {
        "nodes": [
            {
                "id": 1,
                "type": "PromptNode",
                "widgets_values": ["hello", "clip-ref", "model.safetensors"],
                "inputs": [],
            }
        ],
        "links": [],
    }

    api = normalize_to_api(raw)

    assert api["1"]["inputs"] == {
        "widget_0": "hello",
        "widget_1": "clip-ref",
        "widget_2": "model.safetensors",
    }


def test_normalize_to_api_preserves_dict_widget_values() -> None:
    raw = {
        "nodes": [
            {
                "id": 1,
                "type": "VHS_LoadVideo",
                "widgets_values": {
                    "video": "motion.mp4",
                    "force_rate": 16,
                    "custom_width": 832,
                    "custom_height": 480,
                    "save_output": True,
                },
                "inputs": [
                    {"name": "custom_width", "link": 1},
                ],
            },
            {"id": 2, "type": "INTConstant", "widgets_values": [512], "inputs": []},
        ],
        "links": [[1, 2, 0, 1, 0, "INT"]],
    }

    api = normalize_to_api(raw)

    assert api["1"]["inputs"]["video"] == "motion.mp4"
    assert api["1"]["inputs"]["force_rate"] == 16
    assert api["1"]["inputs"]["custom_width"] == ["2", 0]
    assert api["1"]["inputs"]["custom_height"] == 480
    assert api["1"]["inputs"]["save_output"] is True


def test_local_schema_provider_missing_index_is_empty(tmp_path) -> None:
    provider = LocalSchemaProvider(tmp_path / "missing_node_index.json")

    assert provider.schemas() == {}


def test_local_schema_provider_reports_malformed_existing_index(tmp_path) -> None:
    index = tmp_path / "node_index.json"
    index.write_text("{not-json", encoding="utf-8")
    provider = LocalSchemaProvider(index)

    with pytest.raises(SchemaIndexError) as exc_info:
        provider.schemas()

    assert exc_info.value.path == index
    assert "JSONDecodeError" in str(exc_info.value)


def test_schema_provider_helpers_support_public_and_legacy_getters() -> None:
    schema = _schema("PromptNode")

    assert schema_for(FakeSchemaProvider({"PromptNode": schema}), "PromptNode") is schema
    assert schema_for(LegacyGetSchemaProvider({"PromptNode": schema}), "PromptNode") is schema
    assert schema_for(object(), "PromptNode") is None


def test_schema_registry_empty_helper_checks_optional_schemas_method() -> None:
    assert schema_registry_empty(LocalSchemaProvider("missing-node-index.json")) is True
    assert schema_registry_empty(object()) is False
    assert schemas_for(object()) is None


def test_local_schema_provider_parses_index_rows(tmp_path) -> None:
    index = tmp_path / "node_index.json"
    index.write_text(
        json.dumps(
            [
                {
                    "class_type": "PromptNode",
                    "pack": "core",
                    "inputs": {
                        "required": {"text": "STRING"},
                        "optional": {"mode": [["fast", "slow"], {"default": "fast"}]},
                    },
                    "outputs": [{"type": "CONDITIONING", "name": "conditioning"}],
                }
            ]
        ),
        encoding="utf-8",
    )

    schema = LocalSchemaProvider(index).get_schema("PromptNode")

    assert schema is not None
    assert schema.pack == "core"
    assert schema.inputs["text"].type == "STRING"
    assert schema.inputs["text"].required is True
    assert schema.inputs["mode"].type == "CHOICE"
    assert schema.inputs["mode"].choices == ["fast", "slow"]
    assert schema.inputs["mode"].default == "fast"
    assert schema.outputs == [OutputSpec(type="CONDITIONING", name="conditioning")]


def test_malformed_object_info_cache_is_ignored(tmp_path) -> None:
    cache = tmp_path / "object_info.bad.json"
    cache.write_text("{not-json", encoding="utf-8")

    assert load_object_info_cache(cache) is None


def test_runtime_schema_provider_reads_cached_object_info(tmp_path) -> None:
    provider = RuntimeSchemaProvider(server_url="http://runtime.test", cache_dir=tmp_path)
    provider.cache_path.write_text(
        json.dumps(
            {
                "RuntimeNode": {
                    "pack": "runtime-pack",
                    "input": {"required": {"image": ["IMAGE", {"default": None}]}},
                    "output": ["LATENT"],
                    "output_name": ["latent"],
                }
            }
        ),
        encoding="utf-8",
    )

    schema = provider.get_schema("RuntimeNode")

    assert schema is not None
    assert schema.pack == "runtime-pack"
    assert schema.inputs["image"].type == "IMAGE"
    assert schema.inputs["image"].required is True
    assert schema.outputs == [OutputSpec(type="LATENT", name="latent")]


def test_runtime_schema_provider_fetches_and_writes_object_info_cache(tmp_path, monkeypatch) -> None:
    class FakeServer:
        async def __aenter__(self):
            return "http://active-runtime.test"

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeClient:
        def __init__(self, url: str) -> None:
            self.url = url

        async def object_info(self):
            assert self.url == "http://active-runtime.test"
            return {"FetchedNode": {"input": {"optional": {"strength": ["FLOAT", {"default": 1.0, "min": 0, "max": 2}]}}}}

    monkeypatch.setattr("vibecomfy.schema.provider.comfy_server", lambda **kwargs: FakeServer())
    monkeypatch.setattr("vibecomfy.schema.provider.ComfyClient", FakeClient)
    provider = RuntimeSchemaProvider(server_url="http://runtime.test", cache_dir=tmp_path)

    data = asyncio.run(provider.object_info_async())

    assert "FetchedNode" in data
    assert json.loads(provider.cache_path.read_text(encoding="utf-8")) == data
    schema = provider.get_schema("FetchedNode")
    assert schema is not None
    assert schema.inputs["strength"].default == 1.0
    assert schema.inputs["strength"].min == 0
    assert schema.inputs["strength"].max == 2


def test_source_schema_provider_reads_input_types_from_custom_node_source(tmp_path) -> None:
    node_source = tmp_path / "custom_pack" / "nodes"
    node_source.mkdir(parents=True)
    (node_source / "image_nodes.py").write_text(
        """
class ImageResizeKJv2:
    upscale_methods = ["nearest-exact", "lanczos"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "width": ("INT", {"default": 512, "min": 0}),
                "upscale_method": (cls.upscale_methods,),
            },
            "optional": {"device": (["cpu", "gpu"],)},
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
""",
        encoding="utf-8",
    )

    schema = SourceSchemaProvider([tmp_path]).get_schema("ImageResizeKJv2")

    assert schema is not None
    assert schema.inputs["image"].required is True
    assert schema.inputs["width"].type == "INT"
    assert schema.inputs["upscale_method"].choices == ["nearest-exact", "lanczos"]
    assert schema.inputs["device"].required is False
    assert schema.outputs == [OutputSpec(type="IMAGE", name="image")]


def test_get_schema_provider_auto_selection(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("vibecomfy.comfy_command.shutil.which", lambda _: None)
    monkeypatch.setattr("vibecomfy.comfy_command.importlib.util.find_spec", lambda _: None)

    assert isinstance(get_schema_provider("auto"), LocalSchemaProvider)
    assert isinstance(get_schema_provider("auto", server_url="http://runtime.test"), RuntimeSchemaProvider)

    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    assert isinstance(get_schema_provider("auto"), LocalSchemaProvider)
