from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.schema import InputSpec, LocalSchemaProvider, NodeSchema
from vibecomfy.schema.validate import SCHEMA_VALIDATION_SKIP_CLASSES
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


class FakeSchemaProvider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        return self._schemas


def _workflow(*nodes: VibeNode) -> VibeWorkflow:
    workflow = VibeWorkflow("schema-validate-test", WorkflowSource("schema-validate-test"))
    workflow.nodes = {node.id: node for node in nodes}
    return workflow


def _schema(class_type: str, inputs: dict[str, InputSpec]) -> NodeSchema:
    return NodeSchema(class_type=class_type, pack=None, inputs=inputs, outputs=[])


def _codes(workflow: VibeWorkflow, provider: FakeSchemaProvider) -> list[str]:
    return [issue.code for issue in workflow.validate(schema_provider=provider).issues]


def test_missing_required_input_emits_error() -> None:
    provider = FakeSchemaProvider({"PromptNode": _schema("PromptNode", {"text": InputSpec("STRING", required=True)})})
    report = _workflow(VibeNode("1", "PromptNode")).validate(schema_provider=provider)

    assert not report.ok
    assert report.issues[0].code == "missing_required_input"
    assert report.issues[0].detail == {"node_id": "1", "class_type": "PromptNode", "input": "text"}


def test_unknown_input_emits_error() -> None:
    provider = FakeSchemaProvider({"PromptNode": _schema("PromptNode", {"text": InputSpec("STRING")})})
    report = _workflow(VibeNode("1", "PromptNode", inputs={"extra": "value"})).validate(schema_provider=provider)

    assert not report.ok
    assert report.issues[0].code == "unknown_input"
    assert report.issues[0].detail == {"node_id": "1", "class_type": "PromptNode", "input": "extra"}


def test_value_out_of_range_emits_error() -> None:
    provider = FakeSchemaProvider({"AceNode": _schema("AceNode", {"bpm": InputSpec("INT", min=10)})})
    report = _workflow(VibeNode("1", "AceNode", inputs={"bpm": 2})).validate(schema_provider=provider)

    assert not report.ok
    issue = report.issues[0]
    assert issue.code == "value_out_of_range"
    assert issue.detail["node_id"] == "1"
    assert issue.detail["class_type"] == "AceNode"
    assert issue.detail["input"] == "bpm"
    assert issue.detail["value"] == "2"
    assert issue.detail["min"] == 10
    assert issue.detail["max"] is None


def test_value_not_in_enum_emits_error() -> None:
    provider = FakeSchemaProvider({"ChoiceNode": _schema("ChoiceNode", {"mode": InputSpec("STRING", choices=["a", "b"])})})
    report = _workflow(VibeNode("1", "ChoiceNode", inputs={"mode": "c"})).validate(schema_provider=provider)

    assert not report.ok
    issue = report.issues[0]
    assert issue.code == "value_not_in_enum"
    assert issue.detail["node_id"] == "1"
    assert issue.detail["class_type"] == "ChoiceNode"
    assert issue.detail["input"] == "mode"
    assert issue.detail["value"] == "'c'"
    assert issue.detail["choices"] == ["a", "b"]


def test_invalid_link_shape_emits_error_for_dict_shaped_link() -> None:
    provider = FakeSchemaProvider({"Sink": _schema("Sink", {"latent": InputSpec("LATENT")})})
    report = _workflow(VibeNode("1", "Sink", inputs={"latent": {"link": 1, "node": "2"}})).validate(
        schema_provider=provider
    )

    assert not report.ok
    issue = report.issues[0]
    assert issue.code == "invalid_link_shape"
    assert issue.detail["node_id"] == "1"
    assert issue.detail["class_type"] == "Sink"
    assert issue.detail["input"] == "latent"
    assert issue.detail["value_repr"] == "{'link': 1, 'node': '2'}"


def test_skip_list_suppresses_unknown_and_value_issues_only() -> None:
    SCHEMA_VALIDATION_SKIP_CLASSES["LyingNode"] = "test-only"
    try:
        provider = FakeSchemaProvider(
            {
                "LyingNode": _schema(
                    "LyingNode",
                    {
                        "required": InputSpec("STRING", required=True),
                        "mode": InputSpec("STRING", choices=["a"]),
                    },
                )
            }
        )
        workflow = _workflow(VibeNode("1", "LyingNode", inputs={"mode": "b", "extra": "value"}))

        assert _codes(workflow, provider) == ["missing_required_input"]
    finally:
        SCHEMA_VALIDATION_SKIP_CLASSES.pop("LyingNode", None)


def test_range_enum_skipped_when_value_is_api_link() -> None:
    provider = FakeSchemaProvider({"ChoiceNode": _schema("ChoiceNode", {"mode": InputSpec("INT", min=10, choices=[10])})})
    report = _workflow(VibeNode("1", "ChoiceNode", inputs={"mode": ["3", 0]})).validate(schema_provider=provider)

    assert report.ok
    assert report.issues == []


@pytest.mark.parametrize(
    ("input_type", "accepted", "rejected"),
    [
        ("INT", [1, "1"], [True, 1.2, "1.2", "abc"]),
        ("FLOAT", [1, 1.2, "1", "1.2"], [True, "abc"]),
        ("BOOLEAN", [True, False, "true", "FALSE"], [0, 1, "yes"]),
        ("STRING", ["text"], [1, 1.2, True]),
    ],
)
def test_primitive_literal_type_validation_coercion_policy(
    input_type: str,
    accepted: list[object],
    rejected: list[object],
) -> None:
    provider = FakeSchemaProvider({"TypedNode": _schema("TypedNode", {"value": InputSpec(input_type)})})

    for value in accepted:
        report = _workflow(VibeNode("1", "TypedNode", inputs={"value": value})).validate(schema_provider=provider)
        assert report.ok, (input_type, value, [issue.code for issue in report.issues])

    for value in rejected:
        report = _workflow(VibeNode("1", "TypedNode", inputs={"value": value})).validate(schema_provider=provider)
        assert not report.ok, (input_type, value)
        assert [issue.code for issue in report.issues] == ["value_type_mismatch"]
        issue = report.issues[0]
        assert issue.detail["node_id"] == "1"
        assert issue.detail["class_type"] == "TypedNode"
        assert issue.detail["input"] == "value"
        assert issue.detail["expected_type"] == input_type


def test_primitive_type_validation_skips_strict_api_links_only() -> None:
    provider = FakeSchemaProvider({"TypedNode": _schema("TypedNode", {"value": InputSpec("INT")})})

    strict_link = _workflow(VibeNode("1", "TypedNode", inputs={"value": ["3", 0]})).validate(schema_provider=provider)
    malformed_link = _workflow(VibeNode("1", "TypedNode", inputs={"value": [3, "0"]})).validate(
        schema_provider=provider
    )

    assert strict_link.ok
    assert strict_link.issues == []
    assert not malformed_link.ok
    assert [issue.code for issue in malformed_link.issues] == ["value_type_mismatch"]


def test_dynamic_input_exceptions_are_narrow_class_and_input_predicates() -> None:
    provider = FakeSchemaProvider(
        {
            "SimpleCalculator": _schema("SimpleCalculator", {"operation": InputSpec("STRING")}),
            "LTXVAddGuide": _schema("LTXVAddGuide", {"latents": InputSpec("LATENT")}),
        }
    )
    calculator = _workflow(
        VibeNode("1", "SimpleCalculator", inputs={"operation": "add", "input_1": 1, "not_dynamic": 2})
    ).validate(schema_provider=provider)
    ltx = _workflow(VibeNode("2", "LTXVAddGuide", inputs={"latents": ["1", 0], "guide_1": ["3", 0], "extra": 1})).validate(
        schema_provider=provider
    )

    assert [issue.detail["input"] for issue in calculator.issues if issue.code == "unknown_input"] == ["not_dynamic"]
    assert [issue.detail["input"] for issue in ltx.issues if issue.code == "unknown_input"] == ["extra"]


def test_legacy_validation_modules_are_not_restored_or_used_by_first_party_code() -> None:
    assert not Path("vibecomfy/schema/call_validation.py").exists()
    assert not Path("vibecomfy/porting/validate_call.py").exists()

    legacy_markers = (
        "schema.call_validation",
        "porting.validate_call",
        "NodeCallValidation",
        "CallValidation",
    )
    first_party_sources = [
        path
        for path in Path("vibecomfy").rglob("*.py")
        if path.as_posix() not in {"vibecomfy/schema/call_validation.py", "vibecomfy/porting/validate_call.py"}
    ]
    offenders = {
        str(path): marker
        for path in first_party_sources
        for marker in legacy_markers
        if marker in path.read_text(encoding="utf-8")
    }

    assert offenders == {}


@pytest.mark.parametrize("snapshot", sorted(Path("tests/snapshots").glob("*.api.json")))
def test_snapshot_api_workflows_validate_against_permissive_local_schema(snapshot: Path, tmp_path: Path) -> None:
    api = json.loads(snapshot.read_text(encoding="utf-8"))
    rows: dict[str, dict] = {}
    for node in api.values():
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type", "Unknown"))
        row = rows.setdefault(class_type, {"class_type": class_type, "inputs": {}})
        for name in (node.get("inputs") or {}):
            row["inputs"][name] = "*"
    index_path = tmp_path / "node_index.json"
    index_path.write_text(json.dumps(list(rows.values())), encoding="utf-8")
    provider = LocalSchemaProvider(index_path)
    workflow = convert_to_vibe_format(api, workflow_id=snapshot.stem, schema_provider=provider)

    report = workflow.validate(schema_provider=provider)

    assert report.ok, [f"{issue.code}: {issue.message}" for issue in report.issues]
