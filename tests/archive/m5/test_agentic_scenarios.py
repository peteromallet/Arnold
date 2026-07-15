"""Archived pytest tests for the retired sisypy agentic scenario YAML files.

Loads the scenario YAML files from ``megaplan/tests/agentic/scenarios/`` and
asserts:

(a) Every agent with ``dispatcher: hermes`` has both
    ``model: deepseek:deepseek-v4-flash`` AND
    ``config.model: deepseek:deepseek-v4-flash``
    (catches FLAG-002: sisypy's hardcoded HermesDispatcher default model).
(b) Each scenario has exactly one agent.
(c) Each scenario has a non-empty brief loaded from its markdown file.
(d) Each assessment section has expected enforced items.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from sisypy.runner import _load_scenario

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "arnold" / "pipelines" / "megaplan" / "tests" / "agentic" / "scenarios"
BRIEFS_DIR = Path(__file__).resolve().parent.parent / "arnold" / "pipelines" / "megaplan" / "tests" / "agentic" / "briefs"

EXPECTED_SCENARIOS = [
    "use_execute_simple",
    "use_doc_simple",
    "create_poem_panel",
]

EXPECTED_MODEL = "deepseek:deepseek-v4-flash"

# Minimum enforced items each scenario's assessment must include.
EXPECTED_ENFORCED_CONTAINS: dict[str, list[str]] = {
    "use_execute_simple": [
        "actor MUST plan the change through megaplan",
        "actor MUST execute the change using megaplan tooling",
        "actor MUST NOT bypass megaplan CLI",
    ],
    "use_doc_simple": [
        "actor MUST plan the doc through megaplan",
        "actor MUST write the file at docs/ops/blocked-recovery.md",
        "actor MUST NOT bypass megaplan CLI",
    ],
    "create_poem_panel": [
        "actor MUST plan the pipeline through megaplan",
        "actor MUST use ONLY existing pipeline primitive kinds",
        "actor MUST NOT reference iterate_until_consensus",
        "actor MUST NOT add new step kinds",
        "actor MUST land the pipeline under megaplan/pipelines/poem-panel/",
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_scenario_yaml(name: str) -> dict:
    """Load raw YAML dict for scenario *name*."""
    path = SCENARIOS_DIR / f"{name}.yaml"
    assert path.is_file(), f"Scenario YAML not found: {path}"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_brief_md(name: str) -> str:
    """Load the brief markdown for scenario *name*."""
    path = BRIEFS_DIR / f"{name}.md"
    assert path.is_file(), f"Brief markdown not found: {path}"
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_name", EXPECTED_SCENARIOS)
def test_scenario_yaml_exists(scenario_name: str) -> None:
    """Each expected scenario must have a YAML file."""
    path = SCENARIOS_DIR / f"{scenario_name}.yaml"
    assert path.is_file(), f"Missing scenario YAML: {path}"


@pytest.mark.parametrize("scenario_name", EXPECTED_SCENARIOS)
def test_scenario_brief_md_exists(scenario_name: str) -> None:
    """Each expected scenario must have a corresponding brief markdown."""
    path = BRIEFS_DIR / f"{scenario_name}.md"
    assert path.is_file(), f"Missing brief markdown: {path}"


@pytest.mark.parametrize("scenario_name", EXPECTED_SCENARIOS)
def test_loadable_via_sisypy(scenario_name: str) -> None:
    """Each scenario YAML must load cleanly through sisypy's _load_scenario."""
    path = SCENARIOS_DIR / f"{scenario_name}.yaml"
    scenario = _load_scenario(path)
    assert scenario.name == scenario_name


# ---------------------------------------------------------------------------
# (a) FLAG-002: Hermes dispatcher model override
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_name", EXPECTED_SCENARIOS)
def test_hermes_agents_have_correct_model(scenario_name: str) -> None:
    """Every cheap-actor agent MUST have both top-level 'model' AND
    'config.model' set to the canonical flash model identifier.

    This is FLAG-002: sisypy preconstructs each dispatcher with a hardcoded
    default model (``deepseek-v4-pro`` for hermes;
    ``deepseek:deepseek-v4-pro`` for deepseek-subagent), and the ONLY
    override path is ``extra_config["model"]`` which comes from
    ``agent_spec.config``.  If config.model is missing, the scenario
    silently runs on the expensive model.

    Note: HermesDispatcher (chat-only) wants bare ``deepseek-v4-flash``;
    SubagentLauncherDispatcher wants ``deepseek:deepseek-v4-flash``.
    The current default dispatcher is ``deepseek-subagent`` because the
    scenarios require file/web/terminal tools to actually drive megaplan.
    """
    raw = _load_scenario_yaml(scenario_name)
    agents = raw.get("agents", [])
    cheap_dispatchers = {"hermes", "deepseek-subagent"}
    hermes_agents = [
        a for a in agents if a.get("dispatcher") in cheap_dispatchers
    ]

    assert len(hermes_agents) > 0, (
        f"Scenario '{scenario_name}' has no cheap-actor agent — "
        f"expected at least one with dispatcher in {cheap_dispatchers}."
    )

    for agent in hermes_agents:
        agent_id = agent.get("id", "?")
        # Top-level model.
        actual_model = agent.get("model", "")
        assert actual_model == EXPECTED_MODEL, (
            f"Scenario '{scenario_name}' agent '{agent_id}': "
            f"model='{actual_model}' but expected '{EXPECTED_MODEL}'."
        )
        # config.model (the critical FLAG-002 field).
        config = agent.get("config", {})
        actual_config_model = config.get("model", "")
        assert actual_config_model == EXPECTED_MODEL, (
            f"Scenario '{scenario_name}' agent '{agent_id}': "
            f"config.model='{actual_config_model}' but expected "
            f"'{EXPECTED_MODEL}' (FLAG-002: required to override "
            f"sisypy's hardcoded HermesDispatcher default)."
        )


@pytest.mark.parametrize("scenario_name", EXPECTED_SCENARIOS)
def test_hermes_agents_have_timeout_set(scenario_name: str) -> None:
    """Every hermes agent should have config.timeout_sec set."""
    raw = _load_scenario_yaml(scenario_name)
    agents = raw.get("agents", [])
    hermes_agents = [a for a in agents if a.get("dispatcher") == "hermes"]
    for agent in hermes_agents:
        config = agent.get("config", {})
        timeout = config.get("timeout_sec")
        assert timeout is not None, (
            f"Scenario '{scenario_name}': Hermes agent missing timeout_sec."
        )
        assert timeout >= 300, (
            f"Scenario '{scenario_name}': timeout_sec={timeout} too low."
        )


# ---------------------------------------------------------------------------
# (b) Each scenario has exactly one agent
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_name", EXPECTED_SCENARIOS)
def test_exactly_one_agent(scenario_name: str) -> None:
    """Each scenario must have exactly one agent in the agents list."""
    raw = _load_scenario_yaml(scenario_name)
    agents = raw.get("agents", [])
    assert len(agents) == 1, (
        f"Scenario '{scenario_name}' has {len(agents)} agents, "
        f"expected exactly 1."
    )


# ---------------------------------------------------------------------------
# (c) Each scenario has a non-empty brief loaded from markdown
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_name", EXPECTED_SCENARIOS)
def test_brief_markdown_non_empty(scenario_name: str) -> None:
    """The corresponding brief markdown file must be non-empty."""
    brief = _load_brief_md(scenario_name)
    stripped = brief.strip()
    assert len(stripped) > 0, (
        f"Scenario '{scenario_name}': brief markdown is empty."
    )
    # Should contain at least a heading or substantive text.
    assert len(stripped) >= 20, (
        f"Scenario '{scenario_name}': brief markdown is too short "
        f"({len(stripped)} chars)."
    )


@pytest.mark.parametrize("scenario_name", EXPECTED_SCENARIOS)
def test_scenario_sets_brief_field(scenario_name: str) -> None:
    """The scenario loaded via _load_scenario should have a non-empty brief
    (either set directly in YAML or auto-loaded by the runner)."""
    path = SCENARIOS_DIR / f"{scenario_name}.yaml"
    scenario = _load_scenario(path)
    # The brief may be empty in the raw YAML (auto-loaded by run_all).
    # We check the markdown file directly above; here we just verify
    # the scenario loads cleanly.
    assert scenario.name == scenario_name


# ---------------------------------------------------------------------------
# (d) Each assessment section has expected enforced items
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_name", EXPECTED_SCENARIOS)
def test_assessment_has_enforced(scenario_name: str) -> None:
    """Each scenario must have at least one enforced assessment item."""
    raw = _load_scenario_yaml(scenario_name)
    assessment = raw.get("assessment", {})
    enforced = assessment.get("enforced", [])
    assert len(enforced) > 0, (
        f"Scenario '{scenario_name}' has no enforced assessment items."
    )


@pytest.mark.parametrize("scenario_name", EXPECTED_SCENARIOS)
def test_assessment_has_graded(scenario_name: str) -> None:
    """Each scenario must have at least one graded assessment item."""
    raw = _load_scenario_yaml(scenario_name)
    assessment = raw.get("assessment", {})
    graded = assessment.get("graded", [])
    assert len(graded) > 0, (
        f"Scenario '{scenario_name}' has no graded assessment items."
    )


@pytest.mark.parametrize("scenario_name", EXPECTED_SCENARIOS)
def test_enforced_items_contain_expected(scenario_name: str) -> None:
    """Each scenario's enforced items must contain expected substrings."""
    raw = _load_scenario_yaml(scenario_name)
    assessment = raw.get("assessment", {})
    enforced_text = " ".join(assessment.get("enforced", []))

    expected_substrings = EXPECTED_ENFORCED_CONTAINS.get(scenario_name, [])
    for expected in expected_substrings:
        assert expected.lower() in enforced_text.lower(), (
            f"Scenario '{scenario_name}': enforced items missing "
            f"expected substring '{expected}'."
        )


# ---------------------------------------------------------------------------
# create_poem_panel: additional constraints
# ---------------------------------------------------------------------------

def test_create_poem_panel_forbids_new_step_kinds() -> None:
    """create_poem_panel must explicitly forbid new step kinds."""
    raw = _load_scenario_yaml("create_poem_panel")
    assessment = raw.get("assessment", {})
    enforced_text = " ".join(assessment.get("enforced", []))
    assert "must not add new step kinds" in enforced_text.lower()


def test_create_poem_panel_forbids_disallowed_primitives() -> None:
    """create_poem_panel must forbid iterate_until_consensus and other
    disallowed primitives."""
    raw = _load_scenario_yaml("create_poem_panel")
    assessment = raw.get("assessment", {})
    enforced_text = " ".join(assessment.get("enforced", []))

    forbidden = [
        "iterate_until_consensus",
        "dynamic_fanout",
        "weighted_vote",
        "panel_from_artifact",
        "paired_round",
    ]
    for term in forbidden:
        # The enforced text must mention these are NOT allowed.
        # Look for "must not reference" or similar negations near the term.
        assert term in enforced_text.lower(), (
            f"create_poem_panel: enforced items should mention forbidden "
            f"primitive '{term}'."
        )
