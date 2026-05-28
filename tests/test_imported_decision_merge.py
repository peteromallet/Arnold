from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

import megaplan
import megaplan.handlers
from megaplan.handlers import _merge_imported_decision_criteria
from megaplan.types import STATE_CRITIQUED
from megaplan.workers import WorkerResult


def _args(project_dir: Path, **overrides: object) -> Namespace:
    data: dict[str, object] = {
        "plan": None,
        "idea": "merge imported decisions",
        "name": "merge-plan",
        "project_dir": str(project_dir),
        "auto_approve": None,
        "robustness": "tiny",
        "agent": None,
        "mode": "code",
        "output": None,
        "from_doc": None,
        "hermes": None,
        "ephemeral": False,
        "fresh": False,
        "persist": False,
        "confirm_destructive": True,
        "user_approved": False,
        "confirm_self_review": False,
        "batch": None,
    }
    data.update(overrides)
    return Namespace(**data)


def _load_state(root: Path, plan_name: str) -> dict:
    plan_dir = megaplan.plans_root(root) / plan_name
    return json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))


def _write_state(root: Path, plan_name: str, state: dict) -> None:
    plan_dir = megaplan.plans_root(root) / plan_name
    (plan_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _latest_meta(root: Path, plan_name: str) -> dict:
    state = _load_state(root, plan_name)
    plan_dir = megaplan.plans_root(root) / plan_name
    latest_file = state["plan_versions"][-1]["file"]
    meta_path = plan_dir / latest_file.replace(".md", ".meta.json")
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _worker_result(payload: dict) -> tuple[WorkerResult, str, str, bool]:
    return (
        WorkerResult(
            payload=payload,
            raw_output=json.dumps(payload),
            duration_ms=1,
            cost_usd=0.0,
            session_id="session-1",
        ),
        "codex",
        "ephemeral",
        False,
    )


def _plan_text(title: str) -> str:
    return f"""# {title}

## Overview
Imported decisions should appear in success criteria.

## Step 1: Update the relevant code
1. Implement the requested change.
"""


def test_merge_imported_decision_criteria_no_imports_returns_original() -> None:
    state = {"meta": {"notes": []}}
    criteria = [{"criterion": "Existing criterion", "priority": "must"}]
    assert _merge_imported_decision_criteria(state, criteria) == criteria


def test_merge_imported_decision_criteria_appends_load_bearing_and_info() -> None:
    state = {
        "meta": {
            "imported_decisions": [
                {"id": "SD-001", "decision": "Keep SQLite", "load_bearing": True},
                {"id": "SD-002", "decision": "Keep docs flat", "load_bearing": False},
            ]
        }
    }
    merged = _merge_imported_decision_criteria(state, [])
    assert merged == [
        {
            "criterion": "Plan adheres to imported decision SD-001: Keep SQLite",
            "priority": "must",
            "requires": ["subjective_judgment"],
        },
        {
            "criterion": "Plan adheres to imported decision SD-002: Keep docs flat",
            "priority": "info",
            "requires": [],
        },
    ]


def test_merge_imported_decision_criteria_skips_existing_id_reference() -> None:
    state = {
        "meta": {
            "imported_decisions": [
                {"id": "SD-001", "decision": "Keep SQLite", "load_bearing": True},
                {"id": "SD-002", "decision": "Keep docs flat", "load_bearing": False},
            ]
        }
    }
    merged = _merge_imported_decision_criteria(
        state,
        [{"criterion": "Plan already references SD-001 explicitly", "priority": "must"}],
    )
    assert merged == [
        {"criterion": "Plan already references SD-001 explicitly", "priority": "must"},
        {
            "criterion": "Plan adheres to imported decision SD-002: Keep docs flat",
            "priority": "info",
            "requires": [],
        },
    ]


def test_merge_imported_decision_criteria_is_idempotent() -> None:
    state = {
        "meta": {
            "imported_decisions": [
                {"id": "SD-001", "decision": "Keep SQLite", "load_bearing": True},
                {"id": "SD-002", "decision": "Keep docs flat", "load_bearing": False},
            ]
        }
    }
    first = _merge_imported_decision_criteria(state, [])
    second = _merge_imported_decision_criteria(state, first)
    assert second == first


def test_handle_plan_merges_imported_decisions_into_success_criteria(
    bootstrap_fixture: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, project_dir = bootstrap_fixture
    init_response = megaplan.handle_init(root, _args(project_dir, name="plan-merge"))
    state = _load_state(root, init_response["plan"])
    state["meta"]["imported_decisions"] = [
        {"id": "SD-001", "decision": "Keep SQLite", "load_bearing": True},
        {"id": "SD-002", "decision": "Keep docs flat", "load_bearing": False},
    ]
    _write_state(root, init_response["plan"], state)

    monkeypatch.setattr(
        megaplan.handlers,
        "_run_worker",
        lambda *args, **kwargs: _worker_result(
            {
                "plan": _plan_text("Plan"),
                "questions": [],
                "success_criteria": [],
                "assumptions": [],
            }
        ),
    )

    response = megaplan.handle_plan(root, _args(project_dir, plan=init_response["plan"]))
    meta = _latest_meta(root, init_response["plan"])

    assert response["success_criteria"] == meta["success_criteria"]
    assert meta["success_criteria"] == [
        {
            "criterion": "Plan adheres to imported decision SD-001: Keep SQLite",
            "priority": "must",
            "requires": ["subjective_judgment"],
        },
        {
            "criterion": "Plan adheres to imported decision SD-002: Keep docs flat",
            "priority": "info",
            "requires": [],
        },
    ]


def test_handle_revise_merges_imported_decisions_into_success_criteria(
    bootstrap_fixture: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, project_dir = bootstrap_fixture
    init_response = megaplan.handle_init(root, _args(project_dir, name="revise-merge"))
    state = _load_state(root, init_response["plan"])
    state["meta"]["imported_decisions"] = [
        {"id": "SD-001", "decision": "Keep SQLite", "load_bearing": True},
        {"id": "SD-002", "decision": "Keep docs flat", "load_bearing": False},
    ]
    _write_state(root, init_response["plan"], state)

    plan_worker = iter(
        [
            _worker_result(
                {
                    "plan": _plan_text("Plan"),
                    "questions": [],
                    "success_criteria": [],
                    "assumptions": [],
                }
            ),
            _worker_result(
                {
                    "plan": _plan_text("Revised Plan"),
                    "changes_summary": "Refined around imported decisions.",
                    "flags_addressed": [],
                    "questions": [],
                    "success_criteria": [],
                    "assumptions": [],
                }
            ),
        ]
    )
    monkeypatch.setattr(megaplan.handlers, "_run_worker", lambda *args, **kwargs: next(plan_worker))

    megaplan.handle_plan(root, _args(project_dir, plan=init_response["plan"]))
    state = _load_state(root, init_response["plan"])
    state["current_state"] = STATE_CRITIQUED
    _write_state(root, init_response["plan"], state)

    megaplan.handle_revise(root, _args(project_dir, plan=init_response["plan"]))
    meta = _latest_meta(root, init_response["plan"])

    assert meta["success_criteria"] == [
        {
            "criterion": "Plan adheres to imported decision SD-001: Keep SQLite",
            "priority": "must",
            "requires": ["subjective_judgment"],
        },
        {
            "criterion": "Plan adheres to imported decision SD-002: Keep docs flat",
            "priority": "info",
            "requires": [],
        },
    ]
