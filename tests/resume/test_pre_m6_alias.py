from __future__ import annotations

import json
from pathlib import Path

import pytest

from megaplan._core.workflow import resume_plan
from megaplan._pipeline import registry
from megaplan._pipeline.registry import _NAME_ALIASES, canonical_pipeline_name, get_pipeline
from megaplan.types import CliError


def test_pre_m6_planning_name_alias_resolves_registry_pipeline() -> None:
    assert _NAME_ALIASES["planning"] == "megaplan"
    assert canonical_pipeline_name("planning") == "megaplan"
    pipeline = get_pipeline("planning")
    assert pipeline is not None
    assert pipeline.entry == "prep"


def test_resume_plan_with_pre_m6_planning_cursor_runs(tmp_path: Path) -> None:
    plan = "legacy-planning"
    plan_dir = tmp_path / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan,
                "idea": "legacy",
                "current_state": "blocked",
                "iteration": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "_pipeline_name": "planning",
                "resume_cursor": {
                    "phase": "execute",
                    "pipeline": "planning",
                    "batch_index": 1,
                },
                "history": [],
                "config": {},
                "sessions": {},
                "plan_versions": [],
                "meta": {},
                "last_gate": {},
            }
        ),
        encoding="utf-8",
    )

    calls: list[list[str]] = []

    def runner(args: list[str], *, cwd: Path) -> tuple[int, str, str]:
        calls.append(list(args))
        state_path = plan_dir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["current_state"] = "done"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        return 0, "", ""

    result = resume_plan(tmp_path, plan, runner=runner)

    assert result["success"] is True
    assert calls == [
        [
            "execute",
            "--plan",
            plan,
            "--confirm-destructive",
            "--user-approved",
            "--batch",
            "1",
        ]
    ]
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "done"
    assert "resume_cursor" not in state
    assert state["meta"]["pipeline_alias_migrations"] == [
        {"from": "planning", "to": "megaplan", "phase": "execute"}
    ]


def test_resume_plan_refuses_pipeline_manifest_chimera(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEGAPLAN_M6_MANIFEST_DISCOVERY", "1")
    registry._GLOBAL_REGISTRY = registry.PipelineRegistry()
    current_hash = registry.pipeline_metadata("planning")["manifest_hash"]
    assert isinstance(current_hash, str)

    plan = "chimera-planning"
    plan_dir = tmp_path / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True)
    original_state = {
        "name": plan,
        "idea": "legacy",
        "current_state": "blocked",
        "iteration": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "_pipeline_name": "planning",
        "_pipeline_manifest_hash": "sha256:not-the-current-manifest",
        "resume_cursor": {"phase": "execute", "pipeline": "planning"},
        "history": [],
        "config": {},
        "sessions": {},
        "plan_versions": [],
        "meta": {},
        "last_gate": {},
    }
    (plan_dir / "state.json").write_text(json.dumps(original_state), encoding="utf-8")

    called = False

    def runner(args: list[str], *, cwd: Path) -> tuple[int, str, str]:
        nonlocal called
        called = True
        return 0, "", ""

    with pytest.raises(CliError) as exc:
        resume_plan(tmp_path, plan, runner=runner)

    assert exc.value.code == "pipeline_manifest_mismatch"
    assert called is False
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "blocked"


def test_resume_plan_accepts_matching_pipeline_manifest_hash(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEGAPLAN_M6_MANIFEST_DISCOVERY", "1")
    registry._GLOBAL_REGISTRY = registry.PipelineRegistry()
    current_hash = registry.pipeline_metadata("planning")["manifest_hash"]

    plan = "hashed-planning"
    plan_dir = tmp_path / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan,
                "idea": "legacy",
                "current_state": "blocked",
                "iteration": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "_pipeline_name": "planning",
                "_pipeline_manifest_hash": current_hash,
                "resume_cursor": {"phase": "execute", "pipeline": "planning"},
                "history": [],
                "config": {},
                "sessions": {},
                "plan_versions": [],
                "meta": {},
                "last_gate": {},
            }
        ),
        encoding="utf-8",
    )

    def runner(args: list[str], *, cwd: Path) -> tuple[int, str, str]:
        state_path = plan_dir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["current_state"] = "done"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        return 0, "", ""

    result = resume_plan(tmp_path, plan, runner=runner)
    assert result["success"] is True
