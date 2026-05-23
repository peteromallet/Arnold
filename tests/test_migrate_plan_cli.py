from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import megaplan.cli
from megaplan.cli import build_parser
from megaplan.types import STATE_DONE, STATE_FINALIZED


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _state(name: str = "plan") -> dict:
    return {
        "name": name,
        "idea": "idea",
        "current_state": "executed",
        "iteration": 1,
        "created_at": "2026-05-21T00:00:00Z",
        "config": {},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {},
        "last_gate": {},
    }


def _plan_dir(root: Path, name: str = "plan") -> Path:
    return root / ".megaplan" / "plans" / name


def _seed_executed_plan(root: Path, name: str = "plan") -> Path:
    plan_dir = _plan_dir(root, name)
    _write_json(plan_dir / "state.json", _state(name))
    _write_json(
        plan_dir / "finalize.json",
        {"tasks": [{"id": "T1", "status": "done", "executor_notes": "done"}]},
    )
    _write_json(
        plan_dir / "execution_batch_1.json",
        {"task_updates": [{"task_id": "T1", "status": "done"}]},
    )
    _write_json(plan_dir / "execution.json", {"batches": [{"id": 1}]})
    return plan_dir


def _tree_hashes(plan_dir: Path) -> dict[str, str]:
    return {
        path.relative_to(plan_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(plan_dir.rglob("*"))
        if path.is_file()
    }


def test_migrate_plan_parser_requires_exactly_one_action_and_plan() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["migrate-plan", "plan"])
    with pytest.raises(SystemExit):
        parser.parse_args(["migrate-plan", "--diagnose"])
    with pytest.raises(SystemExit):
        parser.parse_args(["migrate-plan", "--diagnose", "--restart", "plan"])


def test_migrate_plan_diagnose_is_read_only_and_structured(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "repo"
    plan_dir = _seed_executed_plan(root)
    before = _tree_hashes(plan_dir)

    exit_code = megaplan.cli.main([
        "migrate-plan",
        "--diagnose",
        "plan",
        "--project-dir",
        str(root),
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert _tree_hashes(plan_dir) == before
    assert payload["success"] is True
    assert payload["action"] == "diagnose"
    assert payload["plan"] == "plan"
    assert payload["diagnostic"]["read_only"] is True
    assert payload["diagnostic"]["classification"] == "legacy_batch_inferred"
    assert "migration_decisions" not in {path.name for path in plan_dir.iterdir()}


def test_migrate_plan_restart_prints_decision_path_and_resets(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "repo"
    plan_dir = _seed_executed_plan(root)

    exit_code = megaplan.cli.main([
        "migrate-plan",
        "--restart",
        "plan",
        "--project-dir",
        str(root),
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["success"] is True
    assert payload["action"] == "restart"
    assert payload["state"] == STATE_FINALIZED
    assert payload["decision_record"].startswith("migration_decisions/")
    assert Path(payload["decision_path"]).exists()
    assert not (plan_dir / "execution_batch_1.json").exists()
    assert not (plan_dir / "execution.json").exists()


def test_migrate_plan_close_prints_decision_path_and_terminal_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "repo"
    _seed_executed_plan(root)

    exit_code = megaplan.cli.main([
        "migrate-plan",
        "--close",
        "plan",
        "--project-dir",
        str(root),
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["success"] is True
    assert payload["action"] == "close"
    assert payload["state"] == STATE_DONE
    assert payload["decision_record"].startswith("migration_decisions/")
    assert Path(payload["decision_path"]).exists()


def test_migrate_plan_accepts_explicit_plan_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "repo"
    plan_dir = _seed_executed_plan(root)

    exit_code = megaplan.cli.main(["migrate-plan", "--diagnose", str(plan_dir)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["success"] is True
    assert payload["plan_dir"] == str(plan_dir.resolve())
