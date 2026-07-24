from __future__ import annotations

import json

from arnold_pipelines.megaplan.cli import build_parser
from arnold_pipelines.megaplan.cli.editor_setup import (
    ensure_repo_editor_support,
    ensure_sublime_user,
    ensure_user_editor_support,
    maybe_auto_sync_repo_editor_support,
)


def test_repo_editor_support_creates_gitattributes_and_vscode_settings(tmp_path):
    changes = ensure_repo_editor_support(tmp_path)

    assert {change.target for change in changes} == {"github", "vscode"}
    assert (
        tmp_path / ".gitattributes"
    ).read_text(encoding="utf-8") == "*.pypeline linguist-language=Python\n"
    settings = json.loads((tmp_path / ".vscode" / "settings.json").read_text())
    assert settings["files.associations"]["*.pypeline"] == "python"


def test_repo_editor_support_merges_existing_settings_idempotently(tmp_path):
    (tmp_path / ".gitattributes").write_text("*.md linguist-documentation\n")
    settings_path = tmp_path / ".vscode" / "settings.json"
    settings_path.parent.mkdir()
    settings_path.write_text(
        json.dumps(
            {
                "editor.formatOnSave": True,
                "files.associations": {"*.foo": "python"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    ensure_repo_editor_support(tmp_path)
    second = ensure_repo_editor_support(tmp_path)

    assert "*.md linguist-documentation" in (tmp_path / ".gitattributes").read_text()
    assert (
        "*.pypeline linguist-language=Python"
        in (tmp_path / ".gitattributes").read_text()
    )
    settings = json.loads(settings_path.read_text())
    assert settings["editor.formatOnSave"] is True
    assert settings["files.associations"] == {
        "*.foo": "python",
        "*.pypeline": "python",
    }
    assert all(change.status == "unchanged" for change in second)


def test_repo_editor_support_skips_invalid_vscode_json(tmp_path):
    settings_path = tmp_path / ".vscode" / "settings.json"
    settings_path.parent.mkdir()
    settings_path.write_text("{not-json", encoding="utf-8")

    changes = ensure_repo_editor_support(tmp_path)

    vscode = next(change for change in changes if change.target == "vscode")
    assert vscode.status == "skipped"
    assert vscode.reason and "invalid JSON" in vscode.reason
    assert settings_path.read_text(encoding="utf-8") == "{not-json"


def test_sublime_user_support_updates_detected_python_settings(tmp_path):
    settings_path = (
        tmp_path
        / "Library/Application Support/Sublime Text/Packages/User/Python.sublime-settings"
    )
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('{"extensions": ["py"]}\n', encoding="utf-8")

    changes = ensure_sublime_user(tmp_path)
    second = ensure_sublime_user(tmp_path)

    assert changes[0].status == "updated"
    settings = json.loads(settings_path.read_text())
    assert settings["extensions"] == ["py", "pypeline"]
    assert second[0].status == "unchanged"


def test_user_editor_support_writes_detected_vim_and_emacs_files(tmp_path):
    (tmp_path / ".vim").mkdir()
    (tmp_path / ".config" / "nvim").mkdir(parents=True)
    (tmp_path / ".emacs.d").mkdir()

    changes = ensure_user_editor_support(tmp_path)

    targets = {(change.target, change.status) for change in changes}
    assert ("vim", "created") in targets
    assert ("neovim", "created") in targets
    assert ("emacs", "created") in targets
    assert (tmp_path / ".vim" / "ftdetect" / "pypeline.vim").exists()
    assert (tmp_path / ".config" / "nvim" / "ftdetect" / "pypeline.vim").exists()
    assert (tmp_path / ".emacs.d" / "pypeline-mode.el").exists()


def test_auto_sync_finds_git_root_and_only_touches_repo_files(tmp_path):
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    maybe_auto_sync_repo_editor_support(nested)

    assert (tmp_path / ".gitattributes").exists()
    assert (tmp_path / ".vscode" / "settings.json").exists()
    assert not (nested / ".gitattributes").exists()


def test_setup_parser_accepts_editor_flags():
    args = build_parser().parse_args(["setup", "--editors", "--user-editors"])

    assert args.command == "setup"
    assert args.editors is True
    assert args.user_editors is True
