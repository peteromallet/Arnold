from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.execute.batch import _resolve_tier_spec
from arnold_pipelines.megaplan.types import AgentMode, CliError
from arnold_pipelines.megaplan.workers import _impl


def _state(tmp_path: Path) -> tuple[Path, Path, dict]:
    from arnold_pipelines.megaplan._core import ensure_runtime_layout

    root = tmp_path / "root"
    root.mkdir()
    ensure_runtime_layout(root)
    plan_dir = root / ".megaplan" / "plans" / "oneshot"
    plan_dir.mkdir(parents=True)
    state = {
        "name": "effort-routing",
        "idea": "x",
        "current_state": "critiqued",
        "iteration": 0,
        "created_at": "1970-01-01T00:00:00Z",
        "config": {"project_dir": str(tmp_path), "mode": "code"},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {},
    }
    return root, plan_dir, state


def test_tier_resolution_preserves_selected_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    selected = AgentMode(
        agent="codex",
        mode="persistent",
        refreshed=False,
        model="gpt-5.6-terra",
        effort="xhigh",
        resolved_model="gpt-5.6-terra",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.execute.batch.worker_module.resolve_agent_mode",
        lambda *_args: selected,
    )

    resolved = _resolve_tier_spec(argparse.Namespace(), "codex:gpt-5.6-terra:xhigh")

    assert resolved == selected
    assert resolved.effort == "xhigh"


@pytest.mark.parametrize("effort", ["xhigh", "max"])
def test_codex_command_preserves_supported_effort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, effort: str
) -> None:
    root, plan_dir, state = _state(tmp_path)
    output_path = plan_dir / "out.txt"
    captured: dict[str, list[str]] = {}

    def fake_run_command(command, **_kwargs):
        captured["command"] = list(command)
        output_path.write_text("batch([done()])", encoding="utf-8")
        return _impl.CommandResult(
            command=list(command), cwd=tmp_path, returncode=0,
            stdout="", stderr="", duration_ms=1,
        )

    monkeypatch.setattr(_impl, "run_command", fake_run_command)
    monkeypatch.setattr(
        _impl, "_codex_step_cost", lambda *args, **kwargs: (0.0, 0, 0, "gpt-5.6-terra", None)
    )

    _impl.run_codex_step(
        "critique", state, plan_dir, root=root, persistent=False, fresh=True,
        read_only=True, output_path=output_path, prompt_override="x",
        free_text=True, model="gpt-5.6-terra", effort=effort,
    )

    assert f"model_reasoning_effort={effort}" in captured["command"]


def test_invalid_codex_effort_fails_clearly(tmp_path: Path) -> None:
    root, plan_dir, state = _state(tmp_path)

    with pytest.raises(CliError, match="Unsupported codex effort level: ultra"):
        _impl.run_codex_step(
            "critique", state, plan_dir, root=root, persistent=False,
            fresh=True, read_only=True, effort="ultra",
        )


def test_tier_without_effort_keeps_phase_fallback() -> None:
    tier = AgentMode(
        agent="codex", mode="persistent", refreshed=False,
        model="gpt-5.6-terra", effort=None, resolved_model="gpt-5.6-terra",
    )
    phase_fallback = "medium"

    effective_effort = tier.effort if tier.effort is not None else phase_fallback

    assert effective_effort == phase_fallback
