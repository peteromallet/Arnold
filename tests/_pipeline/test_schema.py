"""Unit tests for megaplan._pipeline.schema — pydantic validation."""

from __future__ import annotations

import pytest
import yaml

from megaplan._pipeline.schema import (
    AgentStepSpec,
    EdgeSpec,
    GateStepSpec,
    HumanGateStepSpec,
    InputSpec,
    PanelStepSpec,
    PipelineSpec,
    ReviewerSpec,
)


# ── Valid examples ────────────────────────────────────────────────────


class TestValidPipelineSpec:
    """Happy-path YAML schemas validate without error."""

    def test_minimal_agent_pipeline(self) -> None:
        spec = PipelineSpec.model_validate(
            {
                "name": "simple",
                "version": 1,
                "description": "A simple pipeline",
                "default_profile": "partnered",
                "stages": [
                    {
                        "id": "step1",
                        "kind": "agent",
                        "prompt": "prompts/hello.md",
                    },
                ],
            }
        )
        assert spec.name == "simple"
        assert spec.version == 1
        assert len(spec.stages) == 1
        assert spec.stages[0].kind == "agent"

    def test_panel_pipeline(self) -> None:
        spec = PipelineSpec.model_validate(
            {
                "name": "panel-test",
                "version": 1,
                "description": "A panel pipeline",
                "default_profile": "partnered",
                "stages": [
                    {
                        "id": "review",
                        "kind": "panel",
                        "reviewers": [
                            {"id": "a", "prompt": "prompts/a.md"},
                            {"id": "b", "prompt": "prompts/b.md"},
                        ],
                        "inputs": ["draft"],
                    },
                    {
                        "id": "merge",
                        "kind": "agent",
                        "prompt": "prompts/merge.md",
                        "inputs": ["review.*"],
                    },
                ],
                "inputs": [{"name": "draft", "kind": "file"}],
            }
        )
        assert len(spec.stages) == 2
        panel = spec.stages[0]
        assert panel.kind == "panel"
        assert len(panel.reviewers) == 2

    def test_human_gate_pipeline(self) -> None:
        spec = PipelineSpec.model_validate(
            {
                "name": "human-test",
                "version": 1,
                "description": "A pipeline with human gate",
                "default_profile": "partnered",
                "stages": [
                    {
                        "id": "produce",
                        "kind": "agent",
                        "prompt": "prompts/gen.md",
                    },
                    {
                        "id": "decide",
                        "kind": "human_gate",
                        "artifact": "produce",
                        "choices": ["accept", "reject"],
                    },
                ],
                "edges": [
                    {"from": "decide", "when": "accept", "to": "done"},
                    {"from": "decide", "when": "reject", "to": "done"},
                ],
            }
        )
        assert len(spec.edges) == 2
        assert spec.stages[1].kind == "human_gate"

    def test_gate_pipeline(self) -> None:
        spec = PipelineSpec.model_validate(
            {
                "name": "gate-test",
                "version": 1,
                "description": "A pipeline with gate",
                "default_profile": "partnered",
                "stages": [
                    {
                        "id": "judge",
                        "kind": "gate",
                        "prompt": "prompts/judge.md",
                        "inputs": [],
                    },
                ],
            }
        )
        assert spec.stages[0].kind == "gate"

    def test_full_writing_panel_spec(self) -> None:
        """The canonical writing-panel-strict pipeline validates."""
        spec = PipelineSpec.model_validate(
            {
                "name": "writing-panel-strict",
                "version": 1,
                "description": "Adversarial review of prose drafts",
                "inputs": [{"name": "draft", "kind": "file", "required": True}],
                "supported_modes": ["polish", "restructure", "provoke"],
                "default_profile": "@writing-panel-strict:standard",
                "recommended_profiles": [
                    "@writing-panel-strict:premium",
                    "@writing-panel-strict:standard",
                    "@writing-panel-strict:cheap",
                ],
                "stages": [
                    {
                        "id": "panel_review",
                        "kind": "panel",
                        "reviewers": [
                            {"id": "pessimist", "prompt": "prompts/pessimist.md"},
                            {"id": "optimist", "prompt": "prompts/optimist.md"},
                            {"id": "structuralist", "prompt": "prompts/structuralist.md"},
                        ],
                        "inputs": ["draft"],
                        "produces": "markdown",
                        "merge": "none",
                    },
                    {
                        "id": "synth",
                        "kind": "agent",
                        "prompt": "prompts/synth.md",
                        "inputs": ["panel_review.*"],
                        "produces": "markdown",
                    },
                    {
                        "id": "revise",
                        "kind": "agent",
                        "prompt": "prompts/revise.md",
                        "inputs": ["draft", "synth"],
                        "produces": "markdown",
                    },
                    {
                        "id": "human_decide",
                        "kind": "human_gate",
                        "artifact": "revise",
                        "choices": ["continue", "stop"],
                    },
                ],
                "edges": [
                    {"from": "human_decide", "when": "continue", "to": "panel_review"},
                    {"from": "human_decide", "when": "stop", "to": "done"},
                ],
            }
        )
        assert spec.name == "writing-panel-strict"
        assert spec.supported_modes == ["polish", "restructure", "provoke"]
        assert len(spec.stages) == 4


# ── Error cases ───────────────────────────────────────────────────────


class TestSchemaErrors:
    """Malformed YAML should produce clear pydantic errors."""

    def test_duplicate_stage_ids(self) -> None:
        with pytest.raises(ValueError, match="Duplicate stage id"):
            PipelineSpec.model_validate(
                {
                    "name": "bad",
                    "version": 1,
                    "description": "bad",
                    "default_profile": "partnered",
                    "stages": [
                        {"id": "dup", "kind": "agent", "prompt": "p.md"},
                        {"id": "dup", "kind": "agent", "prompt": "p2.md"},
                    ],
                }
            )

    def test_edge_from_nonexistent_stage(self) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            PipelineSpec.model_validate(
                {
                    "name": "bad",
                    "version": 1,
                    "description": "bad",
                    "default_profile": "partnered",
                    "stages": [
                        {"id": "real", "kind": "agent", "prompt": "p.md"},
                    ],
                    "edges": [
                        {"from": "nope", "when": "go", "to": "done"},
                    ],
                }
            )

    def test_edge_to_nonexistent_stage(self) -> None:
        with pytest.raises(ValueError, match="must be an existing stage id or 'done'"):
            PipelineSpec.model_validate(
                {
                    "name": "bad",
                    "version": 1,
                    "description": "bad",
                    "default_profile": "partnered",
                    "stages": [
                        {"id": "real", "kind": "agent", "prompt": "p.md"},
                    ],
                    "edges": [
                        {"from": "real", "when": "go", "to": "nope"},
                    ],
                }
            )

    def test_edge_to_done_is_valid(self) -> None:
        """Edge target 'done' is the sentinel and should be allowed."""
        spec = PipelineSpec.model_validate(
            {
                "name": "ok",
                "version": 1,
                "description": "ok",
                "default_profile": "partnered",
                "stages": [
                    {"id": "real", "kind": "agent", "prompt": "p.md"},
                ],
                "edges": [
                    {"from": "real", "when": "go", "to": "done"},
                ],
            }
        )
        assert len(spec.edges) == 1

    def test_duplicate_reviewer_ids(self) -> None:
        with pytest.raises(ValueError, match="Duplicate reviewer id"):
            PipelineSpec.model_validate(
                {
                    "name": "bad",
                    "version": 1,
                    "description": "bad",
                    "default_profile": "partnered",
                    "stages": [
                        {
                            "id": "panel",
                            "kind": "panel",
                            "reviewers": [
                                {"id": "dup", "prompt": "a.md"},
                                {"id": "dup", "prompt": "b.md"},
                            ],
                        },
                    ],
                }
            )

    def test_panel_star_syntax_only_for_panels(self) -> None:
        """``panel_review.*`` is only valid for panel stages, not agent stages."""
        with pytest.raises(ValueError, match="not a panel stage"):
            PipelineSpec.model_validate(
                {
                    "name": "bad",
                    "version": 1,
                    "description": "bad",
                    "default_profile": "partnered",
                    "stages": [
                        {"id": "agent_x", "kind": "agent", "prompt": "p.md"},
                        {
                            "id": "consumer",
                            "kind": "agent",
                            "prompt": "p2.md",
                            "inputs": ["agent_x.*"],  # invalid: agent_x is not a panel
                        },
                    ],
                }
            )

    def test_unknown_input_ref(self) -> None:
        """Input refs must reference a declared input or existing stage."""
        with pytest.raises(ValueError, match="neither a declared input name nor an existing stage id"):
            PipelineSpec.model_validate(
                {
                    "name": "bad",
                    "version": 1,
                    "description": "bad",
                    "default_profile": "partnered",
                    "stages": [
                        {
                            "id": "s1",
                            "kind": "agent",
                            "prompt": "p.md",
                            "inputs": ["nonexistent"],
                        },
                    ],
                }
            )

    def test_human_gate_artifact_must_exist(self) -> None:
        with pytest.raises(ValueError, match="not an existing stage id"):
            PipelineSpec.model_validate(
                {
                    "name": "bad",
                    "version": 1,
                    "description": "bad",
                    "default_profile": "partnered",
                    "stages": [
                        {"id": "real", "kind": "agent", "prompt": "p.md"},
                        {
                            "id": "gate",
                            "kind": "human_gate",
                            "artifact": "nope",
                            "choices": ["ok"],
                        },
                    ],
                }
            )

    def test_missing_required_fields(self) -> None:
        """Pydantic should reject missing required fields."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PipelineSpec.model_validate(
                {
                    "name": "bad",
                    # missing version, description, default_profile, stages
                }
            )

    def test_unrecognized_top_level_field(self) -> None:
        """Extra fields at top level are forbidden."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PipelineSpec.model_validate(
                {
                    "name": "bad",
                    "version": 1,
                    "description": "bad",
                    "default_profile": "partnered",
                    "stages": [],
                    "extra_field": "nope",
                }
            )

    def test_supported_modes_not_pydantic_validated(self) -> None:
        """supported_modes is a runtime check, not pydantic validation."""
        # Any list of strings should be accepted by pydantic
        spec = PipelineSpec.model_validate(
            {
                "name": "ok",
                "version": 1,
                "description": "ok",
                "default_profile": "partnered",
                "supported_modes": ["anything", "goes", "here"],
                "stages": [
                    {"id": "s1", "kind": "agent", "prompt": "p.md"},
                ],
            }
        )
        assert spec.supported_modes == ["anything", "goes", "here"]


# ── YAML round-trip ───────────────────────────────────────────────────


class TestYAMLRoundTrip:
    """PipelineSpec should round-trip through YAML."""

    def test_yaml_to_spec(self) -> None:
        yaml_text = """
name: roundtrip
version: 2
description: "Round-trip test"
default_profile: partnered
stages:
  - id: hello
    kind: agent
    prompt: prompts/hello.md
"""
        data = yaml.safe_load(yaml_text)
        spec = PipelineSpec.model_validate(data)
        assert spec.name == "roundtrip"
        assert spec.version == 2

    def test_yaml_parse_error(self) -> None:
        """Malformed YAML should raise YAMLError."""
        bad_yaml = """
name: bad
  version: 1  # bad indentation
"""
        with pytest.raises(yaml.YAMLError):
            yaml.safe_load(bad_yaml)


# ── EdgeSpec alias ────────────────────────────────────────────────────


class TestEdgeSpec:
    """EdgeSpec uses ``from_`` as the Python-safe alias for ``from``."""

    def test_from_alias(self) -> None:
        edge = EdgeSpec.model_validate({"from": "src", "when": "go", "to": "dst"})
        assert edge.from_ == "src"
        assert edge.when == "go"
        assert edge.to == "dst"
