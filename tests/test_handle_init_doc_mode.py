"""Smoke tests for handle_init's doc-mode arg validation (--mode/--output)."""
from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

import megaplan
import megaplan._core
import megaplan._core.io as io_module
import megaplan.cli
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
        "idea": "doc-mode test",
        "name": None,
        "project_dir": str(project_dir),
        "auto_approve": None,
        "robustness": "standard",
        "agent": None,
        "mode": "code",
        "output": None,
        "hermes": None,
    }
    data.update(overrides)
    return Namespace(**data)


def test_doc_mode_requires_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(CliError) as info:
        megaplan.handle_init(root, _args(project_dir, mode="doc", output=None))
    assert info.value.code == "invalid_args"
    assert "--output" in str(info.value)


def test_output_rejects_absolute_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            _args(project_dir, mode="doc", output="/etc/passwd"),
        )
    assert info.value.code == "invalid_args"
    assert "relative" in str(info.value).lower() or "absolute" in str(info.value).lower()


def test_output_rejects_parent_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            _args(project_dir, mode="doc", output="../escape.md"),
        )
    assert info.value.code == "invalid_args"
    assert ".." in str(info.value)


def test_doc_mode_accepts_relative_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    response = megaplan.handle_init(
        root,
        _args(project_dir, name="doc-plan", mode="doc", output="docs/result.md"),
    )
    plan_dir = megaplan.plans_root(root) / response["plan"]
    import json as _json
    state = _json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["config"]["mode"] == "doc"
    assert state["config"]["output_path"] == "docs/result.md"


def test_code_mode_without_output_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Code mode without --output is the common case and must keep working."""
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    response = megaplan.handle_init(
        root,
        _args(project_dir, name="code-plan", mode="code", output=None),
    )
    plan_dir = megaplan.plans_root(root) / response["plan"]
    import json as _json
    state = _json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["config"]["mode"] == "code"
    assert "output_path" not in state["config"]


def test_code_mode_with_output_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--output is meaningless in code mode; accepting it silently has
    historically masked dropped --mode doc flags. Reject it loudly."""
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            _args(project_dir, mode="code", output="docs/foo.md"),
        )
    assert info.value.code == "invalid_args"
    assert "--output" in str(info.value)
    assert "--mode doc" in str(info.value)
