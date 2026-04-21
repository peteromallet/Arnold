"""Tests for megaplan.prompts.tiebreaker_orchestrator — prompts, schemas, synthesis, version suffix, status."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import validate, ValidationError

from megaplan.schemas import SCHEMAS
from megaplan.prompts.tiebreaker_researcher import researcher_prompt
from megaplan.prompts.tiebreaker_challenger import challenger_prompt
from megaplan.prompts.tiebreaker_synthesis import render_synthesis
from megaplan.prompts.tiebreaker_orchestrator import _next_version_suffix, _run_tiebreaker_status
from megaplan.types import PlanState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(tmp_path: Path) -> PlanState:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    return {
        "name": "test-plan",
        "config": {"project_dir": str(tmp_path)},
        "idea": "Test idea",
        "intent": "Test intent",
        "user_notes": "",
        "meta": {"notes": []},
        "iteration": 1,
        "history": [],
    }


def _minimal_researcher_payload() -> dict:
    return {
        "question": "Should we use REST or gRPC?",
        "evidence": [
            {
                "claim": "Existing API uses REST",
                "evidence_type": "code",
                "file_paths": ["src/api.py"],
                "quote": "app = Flask(__name__)",
            }
        ],
        "options": [
            {
                "name": "REST",
                "description": "Keep using REST",
                "assumptions": ["Team knows REST"],
                "costs": ["No streaming"],
            },
            {
                "name": "gRPC",
                "description": "Switch to gRPC",
                "assumptions": ["Team can learn protobuf"],
                "costs": ["Migration effort"],
            },
        ],
        "preliminary_pick": {
            "option_name": "REST",
            "rationale": "Lower migration cost",
            "what_im_least_sure_about": "Streaming needs",
        },
    }


def _minimal_challenger_payload() -> dict:
    return {
        "measurements_vs_assumptions": "REST claim is code-backed; streaming need is assumed",
        "missing_options": [
            {
                "name": "GraphQL",
                "description": "Use GraphQL as middle ground",
                "why_missed": "Not considered due to team bias",
            }
        ],
        "hard_cases": [
            {
                "scenario": "High-throughput event stream",
                "which_option_breaks": "REST",
                "severity": "high",
            }
        ],
        "reframings": ["Consider hybrid: REST for CRUD, gRPC for streams"],
        "aging_analysis": "REST ages well for simple CRUD; gRPC ages better for microservices",
        "counter_recommendation": {
            "option_name": "gRPC",
            "rationale": "Better long-term fit",
            "agrees_with_researcher": False,
        },
    }


# ---------------------------------------------------------------------------
# 1. Researcher prompt rendering
# ---------------------------------------------------------------------------


class TestResearcherPrompt:
    def test_contains_question(self, tmp_path: Path) -> None:
        state = _make_state(tmp_path)
        plan_dir = tmp_path / "plan"
        result = researcher_prompt("Should we use REST or gRPC?", state, plan_dir, root=tmp_path)
        assert "Should we use REST or gRPC?" in result

    def test_evidence_over_opinion_directive(self, tmp_path: Path) -> None:
        state = _make_state(tmp_path)
        plan_dir = tmp_path / "plan"
        result = researcher_prompt("Q?", state, plan_dir, root=tmp_path)
        assert "evidence over opinion" in result.lower()

    def test_file_path_citation_instructions(self, tmp_path: Path) -> None:
        state = _make_state(tmp_path)
        plan_dir = tmp_path / "plan"
        result = researcher_prompt("Q?", state, plan_dir, root=tmp_path)
        assert "file path" in result.lower()


# ---------------------------------------------------------------------------
# 2. Challenger prompt rendering
# ---------------------------------------------------------------------------


class TestChallengerPrompt:
    def test_contains_researcher_json(self, tmp_path: Path) -> None:
        state = _make_state(tmp_path)
        plan_dir = tmp_path / "plan"
        researcher_data = _minimal_researcher_payload()
        result = challenger_prompt("Q?", researcher_data, state, plan_dir, root=tmp_path)
        assert "Should we use REST or gRPC?" in result
        assert "preliminary_pick" in result

    def test_stress_test_directive(self, tmp_path: Path) -> None:
        state = _make_state(tmp_path)
        plan_dir = tmp_path / "plan"
        result = challenger_prompt("Q?", {}, state, plan_dir, root=tmp_path)
        assert "stress-test" in result.lower()

    def test_no_session_context(self, tmp_path: Path) -> None:
        state = _make_state(tmp_path)
        plan_dir = tmp_path / "plan"
        result = challenger_prompt("Q?", {}, state, plan_dir, root=tmp_path)
        assert "session" not in result.lower() or "session context" not in result.lower()


# ---------------------------------------------------------------------------
# 3. Synthesis rendering
# ---------------------------------------------------------------------------


class TestSynthesisRendering:
    def test_all_section_headers_present(self) -> None:
        researcher = _minimal_researcher_payload()
        challenger = _minimal_challenger_payload()
        md = render_synthesis("Should we use REST or gRPC?", researcher, challenger)
        for header in [
            "## Decision",
            "## Options Considered",
            "## Evidence Summary",
            "## Researcher Pick",
            "## Challenger Assessment",
            "## Where They Agree",
            "## Where They Disagree",
            "## Recommended Framing",
            "## Fallback Plan",
        ]:
            assert header in md, f"Missing section header: {header}"

    def test_options_table_columns(self) -> None:
        researcher = _minimal_researcher_payload()
        challenger = _minimal_challenger_payload()
        md = render_synthesis("Q?", researcher, challenger)
        assert "| Option | Description | Assumptions | Costs |" in md

    def test_question_appears_in_decision(self) -> None:
        md = render_synthesis("My question?", _minimal_researcher_payload(), _minimal_challenger_payload())
        assert "My question?" in md

    def test_challenger_missing_options_in_table(self) -> None:
        researcher = _minimal_researcher_payload()
        challenger = _minimal_challenger_payload()
        md = render_synthesis("Q?", researcher, challenger)
        assert "GraphQL" in md
        assert "*(challenger)*" in md


# ---------------------------------------------------------------------------
# 4. Schema validation
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_researcher_schema_valid_payload(self) -> None:
        schema = SCHEMAS["tiebreaker_researcher.json"]
        validate(instance=_minimal_researcher_payload(), schema=schema)

    def test_researcher_schema_missing_required(self) -> None:
        schema = SCHEMAS["tiebreaker_researcher.json"]
        with pytest.raises(ValidationError):
            validate(instance={"question": "Q?"}, schema=schema)

    def test_challenger_schema_valid_payload(self) -> None:
        schema = SCHEMAS["tiebreaker_challenger.json"]
        validate(instance=_minimal_challenger_payload(), schema=schema)

    def test_challenger_schema_missing_required(self) -> None:
        schema = SCHEMAS["tiebreaker_challenger.json"]
        with pytest.raises(ValidationError):
            validate(instance={"measurements_vs_assumptions": "x"}, schema=schema)


# ---------------------------------------------------------------------------
# 5. Version suffix logic
# ---------------------------------------------------------------------------


class TestVersionSuffix:
    def test_first_run_no_suffix(self, tmp_path: Path) -> None:
        assert _next_version_suffix(tmp_path) == ""

    def test_second_run_v2(self, tmp_path: Path) -> None:
        (tmp_path / "tiebreaker_researcher.json").write_text("{}")
        assert _next_version_suffix(tmp_path) == "_v2"

    def test_third_run_v3(self, tmp_path: Path) -> None:
        (tmp_path / "tiebreaker_researcher.json").write_text("{}")
        (tmp_path / "tiebreaker_researcher_v2.json").write_text("{}")
        assert _next_version_suffix(tmp_path) == "_v3"


# ---------------------------------------------------------------------------
# 6. Status output
# ---------------------------------------------------------------------------


class TestTiebreakerStatus:
    def test_no_artifacts(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        state: PlanState = {"name": "test-plan", "config": {"project_dir": str(tmp_path)}, "intent": "", "user_notes": "", "iteration": 1, "history": []}
        _run_tiebreaker_status(tmp_path, tmp_path, state)
        out = json.loads(capsys.readouterr().out)
        assert out["total_runs"] == 0
        assert out["runs"] == []

    def test_partial_run(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        (tmp_path / "tiebreaker_researcher.json").write_text("{}")
        state: PlanState = {"name": "test-plan", "config": {"project_dir": str(tmp_path)}, "intent": "", "user_notes": "", "iteration": 1, "history": []}
        _run_tiebreaker_status(tmp_path, tmp_path, state)
        out = json.loads(capsys.readouterr().out)
        assert out["total_runs"] == 1
        assert out["runs"][0]["complete"] is False
        assert out["runs"][0]["challenger"] is None

    def test_complete_run(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        (tmp_path / "tiebreaker_researcher.json").write_text("{}")
        (tmp_path / "tiebreaker_challenger.json").write_text("{}")
        (tmp_path / "tiebreaker.md").write_text("# Synthesis")
        state: PlanState = {"name": "test-plan", "config": {"project_dir": str(tmp_path)}, "intent": "", "user_notes": "", "iteration": 1, "history": []}
        _run_tiebreaker_status(tmp_path, tmp_path, state)
        out = json.loads(capsys.readouterr().out)
        assert out["total_runs"] == 1
        assert out["runs"][0]["complete"] is True

    def test_multiple_runs(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        (tmp_path / "tiebreaker_researcher.json").write_text("{}")
        (tmp_path / "tiebreaker_challenger.json").write_text("{}")
        (tmp_path / "tiebreaker.md").write_text("")
        (tmp_path / "tiebreaker_researcher_v2.json").write_text("{}")
        state: PlanState = {"name": "test-plan", "config": {"project_dir": str(tmp_path)}, "intent": "", "user_notes": "", "iteration": 1, "history": []}
        _run_tiebreaker_status(tmp_path, tmp_path, state)
        out = json.loads(capsys.readouterr().out)
        assert out["total_runs"] == 2
        assert out["runs"][0]["complete"] is True
        assert out["runs"][1]["complete"] is False
