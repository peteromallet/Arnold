from __future__ import annotations

import asyncio
import json

import pytest

import vibecomfy.schema.provider as provider_module
from vibecomfy.ingest.normalize import normalize_to_api
from vibecomfy.schema import (
    InputSpec,
    LocalSchemaProvider,
    NodeSchema,
    ObjectInfoFileSchemaProvider,
    OutputSpec,
    RuntimeSchemaProvider,
    SchemaIndexError,
    get_schema_provider,
    schema_for,
    schema_registry_empty,
    schema_provider_from_object_info_file,
    schemas_for,
)
from vibecomfy.schema.cache import load_object_info_cache
from vibecomfy.schema.provider import ObjectInfoFileSchemaProvider as ProviderObjectInfoFileSchemaProvider
from vibecomfy.schema.provider import RuntimeSchemaProvider as ProviderRuntimeSchemaProvider
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
                "widgets_values": ["hello", "clip-ref", "model.safetensors"],
                "inputs": [],
            }
        ],
        "links": [],
    }

    api = normalize_to_api(raw, schema_provider=provider)

    assert api["1"]["inputs"] == {"text": "hello", "clip": "clip-ref", "ckpt_name": "model.safetensors"}


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


def test_object_info_file_schema_provider_reads_arbitrary_file(tmp_path) -> None:
    object_info = tmp_path / "object_info.fixture.json"
    object_info.write_text(
        json.dumps(
            {
                "FixtureNode": {
                    "category": "fixture-pack",
                    "input": {
                        "required": {"steps": ["INT", {"default": 4, "min": 1, "max": 8}]},
                        "optional": {"mode": [["fast", "slow"], {"default": "fast"}]},
                    },
                    "output": ["IMAGE"],
                    "output_name": ["image"],
                }
            }
        ),
        encoding="utf-8",
    )

    provider = ObjectInfoFileSchemaProvider(object_info)
    schema = provider.get_schema("FixtureNode")

    assert isinstance(provider, ProviderObjectInfoFileSchemaProvider)
    assert schema is not None
    assert schema.pack == "fixture-pack"
    assert schema.inputs["steps"].required is True
    assert schema.inputs["steps"].type == "INT"
    assert schema.inputs["steps"].default == 4
    assert schema.inputs["steps"].min == 1
    assert schema.inputs["steps"].max == 8
    assert schema.inputs["mode"].type == "CHOICE"
    assert schema.outputs == [OutputSpec(type="IMAGE", name="image")]


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


def test_object_info_file_provider_uses_runtime_object_info_parsing(tmp_path) -> None:
    object_info = {
        "SharedNode": {
            "pack": "shared-pack",
            "input": {"required": {"image": ["IMAGE", {"default": None}]}},
            "output": ["LATENT"],
            "output_name": ["latent"],
        }
    }
    object_info_path = tmp_path / "object_info.fixture.json"
    object_info_path.write_text(json.dumps(object_info), encoding="utf-8")
    runtime_provider = RuntimeSchemaProvider(server_url="http://runtime.test", cache_dir=tmp_path)
    runtime_provider.cache_path.write_text(json.dumps(object_info), encoding="utf-8")

    file_schema = schema_provider_from_object_info_file(object_info_path).get_schema("SharedNode")
    runtime_schema = runtime_provider.get_schema("SharedNode")

    assert file_schema == runtime_schema


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
    assert isinstance(provider, ProviderRuntimeSchemaProvider)

    data = asyncio.run(provider.object_info_async())

    assert "FetchedNode" in data
    assert json.loads(provider.cache_path.read_text(encoding="utf-8")) == data
    schema = provider.get_schema("FetchedNode")
    assert schema is not None
    assert schema.inputs["strength"].default == 1.0
    assert schema.inputs["strength"].min == 0
    assert schema.inputs["strength"].max == 2


def test_get_schema_provider_auto_selection(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("vibecomfy.schema.provider.shutil.which", lambda _: None)

    assert isinstance(get_schema_provider("auto"), LocalSchemaProvider)
    assert isinstance(get_schema_provider("auto", server_url="http://runtime.test"), RuntimeSchemaProvider)

    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    assert isinstance(get_schema_provider("auto"), LocalSchemaProvider)


def test_get_schema_provider_precedence_is_explicit_and_opt_in(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("vibecomfy.schema.provider.shutil.which", lambda _: "/usr/local/bin/comfyui")
    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    object_info = tmp_path / "object_info.fixture.json"
    object_info.write_text(json.dumps({"FixtureNode": {"input": {"required": {"text": "STRING"}}}}), encoding="utf-8")

    selected = get_schema_provider("auto", object_info_path=object_info)
    explicit_selected = get_schema_provider("object_info", object_info_path=object_info)
    object_info_file_selected = get_schema_provider("object_info_file", object_info_cache_path=object_info)
    helper_selected = schema_provider_from_object_info_file(object_info)
    assert isinstance(selected, ObjectInfoFileSchemaProvider)
    assert isinstance(explicit_selected, ObjectInfoFileSchemaProvider)
    assert isinstance(object_info_file_selected, ObjectInfoFileSchemaProvider)
    assert isinstance(helper_selected, ObjectInfoFileSchemaProvider)
    assert selected.get_schema("FixtureNode") is not None

    assert isinstance(get_schema_provider("runtime"), RuntimeSchemaProvider)
    assert isinstance(get_schema_provider("local"), LocalSchemaProvider)
    assert isinstance(get_schema_provider("auto", server_url="http://runtime.test"), RuntimeSchemaProvider)

    # Local indexes win over discovered ComfyUI when object-info file selection is not explicit.
    assert isinstance(get_schema_provider("auto"), LocalSchemaProvider)
    (tmp_path / "node_index.json").unlink()
    assert isinstance(get_schema_provider("auto"), RuntimeSchemaProvider)
    monkeypatch.setattr("vibecomfy.schema.provider.shutil.which", lambda _: None)
    assert isinstance(get_schema_provider("auto"), LocalSchemaProvider)
    assert not isinstance(get_schema_provider("auto"), ObjectInfoFileSchemaProvider)
    assert not hasattr(provider_module, "ConversionSchemaProvider")


def test_get_schema_provider_object_info_preference_requires_path() -> None:
    with pytest.raises(ValueError, match="object_info_path"):
        get_schema_provider("object_info")
    with pytest.raises(ValueError, match="object_info_path"):
        get_schema_provider("object_info_file")
