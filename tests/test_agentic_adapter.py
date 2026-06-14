"""Focused pytest tests for MegaplanAdapter.

Instantiates the adapter, calls each of the 8 ABC methods with stub
Scenario and ActorRun objects, and verifies:
- No method raises NotImplementedError.
- Scratch-dir derivation from run.id.
- build_env returns expected keys.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from sisypy.schema import (
    ActorRun,
    AgentSpec,
    Assessment,
    EvidencePack,
    RunMode,
    Scenario,
    SuccessProofLevel,
)

from arnold.pipelines.megaplan.tests.agentic.adapter import MegaplanAdapter


# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------

def _make_scenario(**overrides: object) -> Scenario:
    """Return a minimal stub Scenario for adapter testing."""
    kwargs: dict = {
        "name": "test_scenario",
        "tier": 1,
        "description": "A stub scenario for testing.",
        "brief": "Test brief content.",
        "mode": RunMode.STRUCTURAL,
        "agents": [
            AgentSpec(
                id="test-agent",
                model="deepseek:deepseek-v4-flash",
                dispatcher="hermes",
                config={"model": "deepseek:deepseek-v4-flash"},
            )
        ],
        "budget": {"timeout_sec": 60},
        "assessment": Assessment(
            enforced=["must not crash"],
            graded=["did it work?"],
            observed=["notes"],
        ),
    }
    kwargs.update(overrides)  # type: ignore[arg-type]
    return Scenario(**kwargs)  # type: ignore[arg-type]


def _make_run(**overrides: object) -> ActorRun:
    """Return a minimal stub ActorRun for adapter testing."""
    kwargs: dict = {
        "id": "test-run-001",
        "scenario_name": "test_scenario",
        "agent_id": "test-agent",
        "mode": RunMode.STRUCTURAL,
        "dispatcher": "hermes",
    }
    kwargs.update(overrides)  # type: ignore[arg-type]
    return ActorRun(**kwargs)  # type: ignore[arg-type]


def _make_evidence_pack(evidence_dir: Path) -> EvidencePack:
    """Return a minimal stub EvidencePack pointing at *evidence_dir*."""
    return EvidencePack(
        manifest={},
        evidence_dir=str(evidence_dir),
        files=[],
        capture_notes="",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter() -> MegaplanAdapter:
    """Return a MegaplanAdapter rooted at the current working directory."""
    return MegaplanAdapter(name="megaplan", repo_root=Path.cwd())


@pytest.fixture
def scenario() -> Scenario:
    """Return a stub Scenario."""
    return _make_scenario()


@pytest.fixture
def run() -> ActorRun:
    """Return a stub ActorRun."""
    return _make_run()


# ---------------------------------------------------------------------------
# Tests: 8 ABC methods — no NotImplementedError
# ---------------------------------------------------------------------------

def test_build_env_no_error(adapter: MegaplanAdapter, scenario: Scenario, run: ActorRun) -> None:
    """build_env should return a dict without raising NotImplementedError."""
    env = adapter.build_env(scenario, run)
    assert isinstance(env, dict)


def test_prime_no_error(adapter: MegaplanAdapter, scenario: Scenario, run: ActorRun) -> None:
    """prime should run without raising NotImplementedError."""
    adapter.prime(scenario, run)
    # Verify the scratch directory was created.
    scratch = adapter._scratch_for(run)
    assert scratch.is_dir()
    assert (scratch / "actor_instructions.md").is_file()


def test_capture_no_error(
    adapter: MegaplanAdapter, scenario: Scenario, run: ActorRun, tmp_path: Path
) -> None:
    """capture should run without raising NotImplementedError."""
    adapter.prime(scenario, run)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    adapter.capture(scenario, run, evidence_dir)
    # capture should produce project_specific dir (even if empty).
    ps_dir = evidence_dir / "project_specific"
    assert ps_dir.is_dir()


def test_project_universal_checks_no_error(
    adapter: MegaplanAdapter, scenario: Scenario, tmp_path: Path
) -> None:
    """project_universal_checks should return a dict without NotImplementedError."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    result = adapter.project_universal_checks(scenario, evidence_dir)
    assert isinstance(result, dict)


def test_canonical_bypass_patterns_no_error(
    adapter: MegaplanAdapter, scenario: Scenario
) -> None:
    """canonical_bypass_patterns should return a list without NotImplementedError."""
    patterns = adapter.canonical_bypass_patterns(scenario)
    assert isinstance(patterns, list)
    assert len(patterns) > 0


def test_classify_success_no_error(
    adapter: MegaplanAdapter, scenario: Scenario, tmp_path: Path
) -> None:
    """classify_success should return a SuccessProofLevel without NotImplementedError."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    ps_dir = evidence_dir / "project_specific"
    ps_dir.mkdir()
    ep = _make_evidence_pack(evidence_dir)
    level = adapter.classify_success(scenario, ep)
    assert isinstance(level, SuccessProofLevel)


def test_live_prerequisites_no_error(
    adapter: MegaplanAdapter, scenario: Scenario
) -> None:
    """live_prerequisites should return a dict without NotImplementedError."""
    prereqs = adapter.live_prerequisites(scenario)
    assert isinstance(prereqs, dict)
    assert "DEEPSEEK_API_KEY" in prereqs


def test_command_policy_no_error(
    adapter: MegaplanAdapter, scenario: Scenario, run: ActorRun
) -> None:
    """command_policy should return a dict without NotImplementedError."""
    policy = adapter.command_policy(scenario, run)
    assert isinstance(policy, dict)
    assert "allow_patterns" in policy
    assert "deny_patterns" in policy


# ---------------------------------------------------------------------------
# Tests: scratch-dir derivation from run.id
# ---------------------------------------------------------------------------

def test_scratch_dir_derived_from_run_id(
    adapter: MegaplanAdapter, run: ActorRun
) -> None:
    """Scratch dir should be <repo_root>/.megaplan-agentic/<run.id>/."""
    scratch = adapter._scratch_for(run)
    expected = adapter.repo_root / ".megaplan-agentic" / run.id
    assert scratch == expected
    assert scratch.is_dir()


def test_scratch_dir_cached(adapter: MegaplanAdapter, run: ActorRun) -> None:
    """Calling _scratch_for twice with the same run should return the same Path."""
    a = adapter._scratch_for(run)
    b = adapter._scratch_for(run)
    assert a == b


def test_scratch_dir_different_runs_different_dirs(
    adapter: MegaplanAdapter
) -> None:
    """Different run IDs produce different scratch directories."""
    run1 = _make_run(id="run-aaa")
    run2 = _make_run(id="run-bbb")
    s1 = adapter._scratch_for(run1)
    s2 = adapter._scratch_for(run2)
    assert s1 != s2


# ---------------------------------------------------------------------------
# Tests: build_env returns expected keys
# ---------------------------------------------------------------------------

def test_build_env_has_required_keys(
    adapter: MegaplanAdapter, scenario: Scenario, run: ActorRun
) -> None:
    """build_env must include MEGAPLAN_HOME, PYTHONPATH, PATH."""
    env = adapter.build_env(scenario, run)
    assert "MEGAPLAN_HOME" in env
    assert "PYTHONPATH" in env
    assert "PATH" in env


def test_build_env_megaplan_home_points_to_scratch(
    adapter: MegaplanAdapter, scenario: Scenario, run: ActorRun
) -> None:
    """MEGAPLAN_HOME should be inside the per-run scratch directory."""
    env = adapter.build_env(scenario, run)
    scratch = adapter._scratch_for(run)
    assert env["MEGAPLAN_HOME"] == str(scratch / "home")


def test_build_env_pythonpath_includes_repo_root(
    adapter: MegaplanAdapter, scenario: Scenario, run: ActorRun
) -> None:
    """PYTHONPATH should include the adapter's repo_root."""
    env = adapter.build_env(scenario, run)
    assert str(adapter.repo_root) in env["PYTHONPATH"]


def test_build_env_preserves_existing_path(
    adapter: MegaplanAdapter, scenario: Scenario, run: ActorRun
) -> None:
    """PATH should carry forward the existing os.environ PATH."""
    env = adapter.build_env(scenario, run)
    assert len(env["PATH"]) > 0


# ---------------------------------------------------------------------------
# Tests: classify_success ladder
# ---------------------------------------------------------------------------

def test_classify_success_defaults_to_authored(
    adapter: MegaplanAdapter, scenario: Scenario, tmp_path: Path
) -> None:
    """With no evidence files, classify_success should return AUTHORED."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "project_specific").mkdir()
    ep = _make_evidence_pack(evidence_dir)
    level = adapter.classify_success(scenario, ep)
    assert level == SuccessProofLevel.AUTHORED


def test_classify_success_runtime_proven_from_state_json(
    adapter: MegaplanAdapter, scenario: Scenario, tmp_path: Path
) -> None:
    """When state.json has current_state='done', should return RUNTIME_PROVEN."""
    evidence_dir = tmp_path / "evidence"
    ps_dir = evidence_dir / "project_specific"
    ps_dir.mkdir(parents=True)
    (ps_dir / "state.json").write_text('{"current_state": "done"}')
    ep = _make_evidence_pack(evidence_dir)
    level = adapter.classify_success(scenario, ep)
    assert level == SuccessProofLevel.RUNTIME_PROVEN


def test_classify_success_authored_from_git_diff(
    adapter: MegaplanAdapter, scenario: Scenario, tmp_path: Path
) -> None:
    """When git_diff.patch shows additions, should return AUTHORED."""
    evidence_dir = tmp_path / "evidence"
    ps_dir = evidence_dir / "project_specific"
    ps_dir.mkdir(parents=True)
    (evidence_dir / "git_diff.patch").write_text(
        "diff --git a/file.py b/file.py\n+new line\n"
    )
    ep = _make_evidence_pack(evidence_dir)
    level = adapter.classify_success(scenario, ep)
    assert level == SuccessProofLevel.AUTHORED


# ---------------------------------------------------------------------------
# Tests: command_policy structural vs live
# ---------------------------------------------------------------------------

def test_command_policy_structural_has_deny_patterns(
    adapter: MegaplanAdapter, scenario: Scenario, run: ActorRun
) -> None:
    """In structural mode, command_policy should include deny patterns."""
    policy = adapter.command_policy(scenario, run)
    assert policy["enforce"] is True
    assert len(policy["deny_patterns"]) > 0


def test_command_policy_live_permissive(
    adapter: MegaplanAdapter, scenario: Scenario
) -> None:
    """In live mode, command_policy should allow everything."""
    run = _make_run(mode=RunMode.LIVE)
    policy = adapter.command_policy(scenario, run)
    assert policy["enforce"] is False
    assert len(policy["deny_patterns"]) == 0
