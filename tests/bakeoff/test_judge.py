import json
from argparse import Namespace
from pathlib import Path

import pytest

from megaplan.bakeoff import handlers
from megaplan.bakeoff.judge import auto_select_judge_model
from megaplan.bakeoff.state import load_bakeoff_state, save_bakeoff_state
from megaplan.types import CliError


def _state(root: Path, profiles: list[str]) -> dict:
    exp_id = "exp-1"
    records = []
    for name in profiles:
        worktree = root.parent / f"wt-{name}"
        records.append(
            {
                "name": name,
                "worktree": str(worktree),
                "plan_id": exp_id,
                "pid": None,
                "launched_at": None,
                "terminated_at": None,
                "outcome": {"status": "done"},
                "log_path": str(root / ".megaplan" / "bakeoffs" / exp_id / name / "auto.log"),
                "outcome_path": str(root / ".megaplan" / "bakeoffs" / exp_id / name / "outcome.json"),
            }
        )
    return {
        "schema_version": 1,
        "experiment_id": exp_id,
        "base_sha": "base",
        "idea_hash": "idea",
        "idea_path": str(root / "idea.md"),
        "mode": "code",
        "profiles": records,
        "phase": "running",
        "chosen_profile": None,
        "merged_at": None,
        "judge_model": None,
    }


def _save_state(root: Path, profiles: list[str]) -> dict:
    root.mkdir()
    state = _state(root, profiles)
    save_bakeoff_state(root, state)
    return state


def test_compare_without_judge_skips_run_judge(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _save_state(root, ["standard"])

    async def forbidden(*_args: object, **_kwargs: object) -> dict:
        raise AssertionError("run_judge should not be called when --judge is omitted")

    monkeypatch.setattr(handlers, "run_judge", forbidden)

    assert handle_compare_no_judge(root) == 0

    comparison = json.loads((root / ".megaplan" / "bakeoffs" / "exp-1" / "comparison.json").read_text())
    assert comparison["judge_verdict"] is None
    assert load_bakeoff_state(root, "exp-1")["judge_model"] is None


def test_auto_judge_uses_canonical_agent_and_model_identities(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    phase_maps = {
        "claude-profile": {"plan": "claude", "execute": "claude"},
        "codex-profile": {"plan": "codex", "execute": "codex"},
        "gpt5-profile": {"plan": "hermes:openai/gpt-5", "execute": "hermes:openai/gpt-5"},
    }

    import megaplan.bakeoff.judge as judge_module

    monkeypatch.setattr(judge_module, "load_profiles", lambda project_dir: {})
    monkeypatch.setattr(judge_module, "resolve_profile", lambda name, profiles: phase_maps[name])

    assert auto_select_judge_model(root, _state(root, ["claude-profile", "codex-profile"])) == "gpt-5"
    with pytest.raises(CliError) as excinfo:
        auto_select_judge_model(root, _state(root, ["claude-profile", "codex-profile", "gpt5-profile"]))
    assert excinfo.value.code == "bakeoff_no_free_judge"


def test_explicit_judge_runs_verbatim_regardless_of_profile_phase_maps(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "repo"
    _save_state(root, ["gpt5-profile"])
    captured: dict[str, str] = {}

    async def fake_run_judge(_state: dict, metrics: dict, judge_model: str) -> dict:
        captured["judge_model"] = judge_model
        return {
            "judge_model": judge_model,
            "rank": list(metrics),
            "rationale_per_profile": {name: "" for name in metrics},
            "scope_drift_flags": {name: [] for name in metrics},
            "concerns": [],
        }

    monkeypatch.setattr(handlers, "run_judge", fake_run_judge)

    assert handlers.handle_compare(root, Namespace(exp="exp-1", judge="gpt-5", force=False)) == 0

    assert captured["judge_model"] == "gpt-5"
    comparison = json.loads((root / ".megaplan" / "bakeoffs" / "exp-1" / "comparison.json").read_text())
    assert comparison["judge_verdict"]["judge_model"] == "gpt-5"
    assert load_bakeoff_state(root, "exp-1")["judge_model"] == "gpt-5"


def handle_compare_no_judge(root: Path) -> int:
    return handlers.handle_compare(root, Namespace(exp="exp-1", judge=None, force=False))
