"""Tests for the status-trigger babysitter goal renderer.

The status trigger renders this goal and launches ONE Flash managed agent
(hermes:deepseek:deepseek-v4-flash) whose prompt drives the whole
swarm -> codex -> implement -> relaunch -> prove flow.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

RENDERER = (
    pathlib.Path(__file__).resolve().parents[2]
    / "arnold_pipelines"
    / "megaplan"
    / "skills"
    / "babysitter"
    / "scripts"
    / "render_babysitter_goal.py"
)


def _load_renderer():
    spec = importlib.util.spec_from_file_location("render_babysitter_goal", RENDERER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_renderer_requires_single_flash_orchestrator_contract() -> None:
    renderer = _load_renderer()
    goal = renderer.render_babysitter_goal("demo-session")
    for required in (
        "You are the BABYSITTER",
        "hermes:deepseek:deepseek-v4-flash",
        "subagent-launcher/fan.py",
        "codex:gpt-5.6-sol",
        "implement",
        "relaunch",
        "prove",
        "last_state",
        "failure_fingerprint",
    ):
        assert required in goal, f"goal missing {required!r}"


def test_renderer_is_the_single_agent_orchestrator_not_an_external_protocol() -> None:
    renderer = _load_renderer()
    goal = renderer.render_babysitter_goal("demo-session")
    for forbidden in (
        "do NOT collapse the babysitter into a single agent",
        "NOT the single-agent meta-fixer",
        "prompt-only pass is a failure mode",
    ):
        assert forbidden not in goal, f"goal must not contain {forbidden!r}"


def test_renderer_embeds_session_workspace_plan_context() -> None:
    renderer = _load_renderer()
    goal = renderer.render_babysitter_goal(
        "demo-session",
        workspace="/workspace/app",
        plan="demo-plan",
        run_kind="chain",
        occurrence_digest="abc123def456",
    )
    assert '"demo-session"' in goal
    assert "- workspace: /workspace/app" in goal
    assert "- plan: demo-plan" in goal
    assert "- run_kind: chain" in goal
    assert "- occurrence_digest: abc123def456" in goal


def test_renderer_embeds_failure_evidence() -> None:
    renderer = _load_renderer()
    goal = renderer.render_babysitter_goal(
        "demo-session",
        plan="demo-plan",
        latest_failure={
            "kind": "deterministic_phase_failure",
            "phase": "finalize",
            "message": "task-graph rejection",
        },
        planner_repair={"schema": "megaplan.planner_repair", "candidate_id": "c-1"},
    )
    assert "latest_failure" in goal
    assert "deterministic_phase_failure" in goal
    assert "task-graph rejection" in goal
    assert "planner_repair" in goal
    assert "candidate_id" in goal


def test_renderer_cli_mentions_single_flash_contract(tmp_path: pathlib.Path) -> None:
    failure = tmp_path / "failure.json"
    failure.write_text(
        json.dumps({"kind": "stall_detected", "message": "driver stalled"}),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(RENDERER),
            "--target",
            "demo-session",
            "--workspace",
            "/workspace/app",
            "--plan",
            "demo-plan",
            "--failure-json",
            str(failure),
            "--occurrence-digest",
            "feedface1234",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "STEP 1 — DEPLOY THE SWARM" in result.stdout
    assert "hermes:deepseek:deepseek-v4-flash" in result.stdout
    assert "failure_fingerprint" in result.stdout
    assert "stall_detected" in result.stdout
