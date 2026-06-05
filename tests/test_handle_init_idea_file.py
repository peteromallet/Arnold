from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

import arnold.pipelines.megaplan as megaplan
from arnold.pipelines.megaplan.auto import DriverOutcome
from arnold.pipelines.megaplan.types import CliError


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


def test_init_reads_idea_file(tmp_path: Path, bootstrap_fixture: tuple[Path, Path]) -> None:
    root, project_dir = bootstrap_fixture
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
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    root, project_dir = bootstrap_fixture
    idea_file = tmp_path / "idea.txt"
    idea_file.write_text("from file\n", encoding="utf-8")

    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            _args(project_dir, idea="positional", idea_file=str(idea_file)),
        )

    assert info.value.code == "invalid_args"


def test_init_rejects_empty_idea_file(tmp_path: Path, bootstrap_fixture: tuple[Path, Path]) -> None:
    root, project_dir = bootstrap_fixture
    idea_file = tmp_path / "empty.txt"
    idea_file.write_text(" \n\t", encoding="utf-8")

    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            _args(project_dir, idea_file=str(idea_file)),
        )

    assert info.value.code == "BRIEF_MISSING"
    assert "--idea-file" in str(info.value)


def test_init_rejects_missing_idea_file_with_resolved_path(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    root, project_dir = bootstrap_fixture
    idea_file = tmp_path / "missing.txt"
    resolved_path = idea_file.resolve()

    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            _args(project_dir, idea_file=str(idea_file)),
        )

    assert info.value.code == "invalid_args"
    message = str(info.value)
    assert "idea file not found" in message
    assert str(resolved_path) in message
    assert "BRIEF_MISSING" not in message


def test_init_slugify_uses_resolved_idea_text(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    root, project_dir = bootstrap_fixture
    idea_file = tmp_path / "slug-source.txt"
    idea_file.write_text("Ship Search Results Faster\n", encoding="utf-8")

    response = megaplan.handle_init(
        root,
        _args(project_dir, idea_file=str(idea_file)),
    )

    assert response["plan"].startswith(f"{megaplan.slugify('Ship Search Results Faster')}-")


def test_init_state_idea_is_file_contents(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    root, project_dir = bootstrap_fixture
    idea_file = tmp_path / "state-idea.txt"
    idea_file.write_text("  keep trimmed content  \n", encoding="utf-8")

    response = megaplan.handle_init(
        root,
        _args(project_dir, name="state-plan", idea_file=str(idea_file)),
    )
    state = _load_state(root, response["plan"])

    assert state["idea"] == "keep trimmed content"


def test_init_positional_existing_markdown_file_stores_contents(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    root, project_dir = bootstrap_fixture
    idea_file = tmp_path / "positional.md"
    idea_file.write_text("  positional file content  \n", encoding="utf-8")

    response = megaplan.handle_init(
        root,
        _args(project_dir, name="positional-file-plan", idea=str(idea_file)),
    )
    state = _load_state(root, response["plan"])
    plan_dir = megaplan.plans_root(root) / response["plan"]

    assert state["idea"] == "positional file content"
    assert state["idea"] != str(idea_file)
    assert state["idea_snapshot_path"] == "idea_snapshot.md"
    assert (
        (plan_dir / "idea_snapshot.md").read_text(encoding="utf-8")
        == "positional file content"
    )


def test_init_rejects_empty_positional_idea_file(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    root, project_dir = bootstrap_fixture
    idea_file = tmp_path / "empty-positional.md"
    idea_file.write_text(" \n\t", encoding="utf-8")

    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            _args(project_dir, idea=str(idea_file)),
        )

    assert info.value.code == "BRIEF_MISSING"
    assert "positional idea file must contain non-empty" in str(info.value)


def test_init_inline_positional_text_that_is_not_file_stays_verbatim(
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    root, project_dir = bootstrap_fixture
    idea = "ship the inline brief"

    response = megaplan.handle_init(
        root,
        _args(project_dir, name="inline-idea-plan", idea=idea),
    )
    state = _load_state(root, response["plan"])

    assert state["idea"] == idea


def test_init_auto_start_invokes_drive(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, project_dir = bootstrap_fixture
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

    monkeypatch.setattr("arnold.pipelines.megaplan.auto.drive", fake_drive)

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
