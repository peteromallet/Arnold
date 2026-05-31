"""Regression: chain startup preflight for the hermes/agent backend.

A fresh engine install can silently lack the agent backend (e.g. a uv version
that ignored the old `default-extras = ["agent"]` hint). Before this preflight,
a chain that did prep only discovered the missing backend deep inside the prep
phase (prep research iteration N), failing with a confusing
`phase 'prep' internal_error` whose stdout was the raw
`{"error":"agent_deps_missing",...}` payload.

These tests assert the chain now fails fast at startup (cold path) with a clear,
actionable error naming the milestone + phase, and that it does NOT fire when
the backend is importable or no milestone needs it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from megaplan.chain import (
    MilestoneSpec,
    _milestone_uses_hermes_backend,
    _preflight_agent_backends,
    load_spec,
    run_chain,
)
from megaplan.types import CliError


def _write_spec(tmp_path: Path, spec_dict: dict) -> Path:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text(yaml.safe_dump(spec_dict), encoding="utf-8")
    return spec_path


def _touch_idea(tmp_path: Path, name: str) -> Path:
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir(exist_ok=True)
    path = ideas_dir / name
    path.write_text("an idea", encoding="utf-8")
    return path


# --- unit: which milestones need the backend --------------------------------


def test_milestone_with_prep_needs_hermes() -> None:
    m = MilestoneSpec(label="m1", idea="x", with_prep=True)
    assert _milestone_uses_hermes_backend(m) == "prep"


def test_milestone_without_prep_does_not_need_hermes() -> None:
    m = MilestoneSpec(label="m1", idea="x", with_prep=False)
    assert _milestone_uses_hermes_backend(m) is None


def test_milestone_explicit_hermes_phase_model_needs_hermes() -> None:
    m = MilestoneSpec(
        label="m1",
        idea="x",
        with_prep=False,
        phase_model=["critique=hermes:deepseek:deepseek-v4-pro"],
    )
    assert _milestone_uses_hermes_backend(m) == "critique"


def test_milestone_non_hermes_phase_model_does_not_need_hermes() -> None:
    m = MilestoneSpec(
        label="m1",
        idea="x",
        with_prep=False,
        phase_model=["execute=codex:gpt-5"],
    )
    assert _milestone_uses_hermes_backend(m) is None


# --- preflight behavior -----------------------------------------------------


def _spec_with_prep_milestone(tmp_path: Path):
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea), "with_prep": True}]},
    )
    return load_spec(spec_path)


def test_preflight_raises_when_backend_missing(tmp_path: Path, monkeypatch) -> None:
    spec = _spec_with_prep_milestone(tmp_path)
    # Simulate the backend NOT importable.
    monkeypatch.setattr(
        "megaplan.workers._is_agent_available", lambda agent: False
    )
    with pytest.raises(CliError) as excinfo:
        _preflight_agent_backends(spec, writer=lambda _m: None)
    assert excinfo.value.code == "agent_deps_missing"
    msg = excinfo.value.message
    # Names the offending milestone + phase and the remediation.
    assert "m1" in msg
    assert "prep" in msg
    assert "uv pip install -e" in msg


def test_preflight_passes_when_backend_present(tmp_path: Path, monkeypatch) -> None:
    spec = _spec_with_prep_milestone(tmp_path)
    monkeypatch.setattr(
        "megaplan.workers._is_agent_available", lambda agent: True
    )
    # Must not raise.
    _preflight_agent_backends(spec, writer=lambda _m: None)


def test_preflight_noop_when_no_milestone_needs_backend(
    tmp_path: Path, monkeypatch
) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea), "with_prep": False}]},
    )
    spec = load_spec(spec_path)

    # Even if the backend is missing, a no-prep / non-hermes chain must not be
    # blocked — and the probe must not even be consulted.
    def _boom(_agent):  # pragma: no cover - should never be called
        raise AssertionError("_is_agent_available should not be probed")

    monkeypatch.setattr("megaplan.workers._is_agent_available", _boom)
    _preflight_agent_backends(spec, writer=lambda _m: None)


def test_run_chain_fails_fast_before_driving_when_backend_missing(
    tmp_path: Path, monkeypatch
) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea), "with_prep": True}]},
    )
    monkeypatch.setattr(
        "megaplan.workers._is_agent_available", lambda agent: False
    )

    # If the preflight fired, we never reach the plan-driving path. Make that
    # path explode so a regression (preflight removed) is caught loudly.
    def _should_not_run(*args, **kwargs):  # pragma: no cover
        raise AssertionError("chain drove a milestone despite missing backend")

    monkeypatch.setattr(
        "megaplan.chain._drive_plan_with_blocked_execute_recovery",
        _should_not_run,
    )

    with pytest.raises(CliError) as excinfo:
        run_chain(spec_path, tmp_path, writer=lambda _m: None)
    assert excinfo.value.code == "agent_deps_missing"
