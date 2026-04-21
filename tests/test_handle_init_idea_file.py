from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

import megaplan
import megaplan._core
import megaplan._core.io as io_module
import megaplan.cli
from megaplan.auto import DriverOutcome
from megaplan.types import CliError


def _bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    def _config_dir(home: Path | None = None) -> Path:
        del home
        return config_path

    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    monkeypatch.setattr(io_module, "config_dir", _config_dir)
    monkeypatch.setattr(megaplan.cli, "config_dir", _config_dir)
    return root, project_dir


def _args(project_dir: Path, **overrides: object) -> Namespace:
    data: dict[str, object] = {
        "plan": None,
        "idea": None,
        "idea_file": None,
        "name": None,
        "project_dir": str(project_dir),
        "auto_approve": None,
        "robustness": "standard",
        "agent": None,
        "mode": "code",
        "output": None,
        "from_doc": None,
        "hermes": None,
        "auto_start": False,
    }
    data.update(overrides)
    return Namespace(**data)


def _load_state(root: Path, plan_name: str) -> dict:
    plan_dir = megaplan.plans_root(root) / plan_name
    return json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))


def test_init_reads_idea_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    idea_file = tmp_path / "idea.txt"
    idea_file.write_text("  file-backed idea  \n", encoding="utf-8")

    response = megaplan.handle_init(
        root,
        _args(project_dir, name="idea-file-plan", idea_file=str(idea_file)),
    )

    assert response["success"] is True
    assert response["plan"] == "idea-file-plan"
    assert response["next_step"] == "plan"


def test_init_rejects_both_positional_and_idea_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    idea_file = tmp_path / "idea.txt"
    idea_file.write_text("from file\n", encoding="utf-8")

    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            _args(project_dir, idea="positional", idea_file=str(idea_file)),
        )

    assert info.value.code == "invalid_args"


def test_init_rejects_empty_idea_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    idea_file = tmp_path / "empty.txt"
    idea_file.write_text(" \n\t", encoding="utf-8")

    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            _args(project_dir, idea_file=str(idea_file)),
        )

    assert info.value.code == "invalid_args"
    assert "--idea-file" in str(info.value)


def test_init_slugify_uses_resolved_idea_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    idea_file = tmp_path / "slug-source.txt"
    idea_file.write_text("Ship Search Results Faster\n", encoding="utf-8")

    response = megaplan.handle_init(
        root,
        _args(project_dir, idea_file=str(idea_file)),
    )

    assert response["plan"].startswith(f"{megaplan.slugify('Ship Search Results Faster')}-")


def test_init_state_idea_is_file_contents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    idea_file = tmp_path / "state-idea.txt"
    idea_file.write_text("  keep trimmed content  \n", encoding="utf-8")

    response = megaplan.handle_init(
        root,
        _args(project_dir, name="state-plan", idea_file=str(idea_file)),
    )
    state = _load_state(root, response["plan"])

    assert state["idea"] == "keep trimmed content"


def test_init_auto_start_invokes_drive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    idea_file = tmp_path / "auto-start.txt"
    idea_file.write_text("auto start from file\n", encoding="utf-8")
    calls: list[tuple[str, Path]] = []

    def fake_drive(plan: str, *, cwd: Path, **_kwargs) -> DriverOutcome:
        calls.append((plan, cwd))
        return DriverOutcome(
            status="done",
            plan=plan,
            final_state="done",
            iterations=2,
            reason="",
            last_phase="review",
            events=[{"msg": "auto advanced"}],
        )

    monkeypatch.setattr("megaplan.auto.drive", fake_drive)

    response = megaplan.handle_init(
        root,
        _args(
            project_dir,
            name="auto-start-plan",
            idea_file=str(idea_file),
            auto_start=True,
        ),
    )

    assert calls == [("auto-start-plan", root)]
    assert response["auto_outcome"] == {
        "status": "done",
        "plan": "auto-start-plan",
        "final_state": "done",
        "iterations": 2,
        "reason": "",
        "last_phase": "review",
        "events": [{"msg": "auto advanced"}],
    }
