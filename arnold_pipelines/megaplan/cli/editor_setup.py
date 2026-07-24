from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core import atomic_write_text

PYPIPELINE_GITATTRIBUTES = "*.pypeline linguist-language=Python"
PYPIPELINE_VSCODE_ASSOCIATION = {"*.pypeline": "python"}
SUBLIME_APP_DIRS = (
    "Library/Application Support/Sublime Text",
    "Library/Application Support/Sublime Text 3",
)
VIM_FTDETECT = "autocmd BufRead,BufNewFile *.pypeline set filetype=python\n"
EMACS_MODE_SNIPPET = (
    ';;; pypeline-mode.el --- Treat .pypeline files as Python -*- lexical-binding: t; -*-\n'
    "(add-to-list 'auto-mode-alist '(\"\\\\.pypeline\\\\'\" . python-mode))\n"
    '(provide \'pypeline-mode)\n'
)


@dataclass(frozen=True)
class EditorSetupChange:
    path: str
    status: str
    target: str
    reason: str | None = None

    def as_dict(self) -> dict[str, str]:
        payload = {"path": self.path, "status": self.status, "target": self.target}
        if self.reason:
            payload["reason"] = self.reason
        return payload


def _write_if_changed(path: Path, content: str, target: str) -> EditorSetupChange:
    existed = path.exists()
    if existed and path.read_text(encoding="utf-8") == content:
        return EditorSetupChange(str(path), "unchanged", target)
    atomic_write_text(path, content)
    return EditorSetupChange(str(path), "updated" if existed else "created", target)


def _ensure_line(path: Path, line: str, target: str) -> EditorSetupChange:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        lines = existing.splitlines()
        if line in lines:
            return EditorSetupChange(str(path), "unchanged", target)
        suffix = "" if existing.endswith("\n") or not existing else "\n"
        atomic_write_text(path, f"{existing}{suffix}{line}\n")
        return EditorSetupChange(str(path), "updated", target)
    return _write_if_changed(path, f"{line}\n", target)


def ensure_github_linguist(root: Path) -> EditorSetupChange:
    return _ensure_line(root / ".gitattributes", PYPIPELINE_GITATTRIBUTES, "github")


def _read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return {}, None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc.msg}"
    if not isinstance(loaded, dict):
        return None, "top-level JSON value is not an object"
    return loaded, None


def _json_dump(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def ensure_vscode_workspace(root: Path) -> EditorSetupChange:
    path = root / ".vscode" / "settings.json"
    settings, reason = _read_json_object(path)
    if settings is None:
        return EditorSetupChange(str(path), "skipped", "vscode", reason)

    associations = settings.get("files.associations")
    if associations is None:
        associations = {}
    if not isinstance(associations, dict):
        return EditorSetupChange(
            str(path),
            "skipped",
            "vscode",
            "files.associations is not an object",
        )

    before = _json_dump(settings)
    associations.update(PYPIPELINE_VSCODE_ASSOCIATION)
    settings["files.associations"] = associations
    after = _json_dump(settings)
    if path.exists() and before == after:
        return EditorSetupChange(str(path), "unchanged", "vscode")
    return _write_if_changed(path, after, "vscode")


def ensure_repo_editor_support(root: Path) -> list[EditorSetupChange]:
    root = root.resolve()
    return [
        ensure_github_linguist(root),
        ensure_vscode_workspace(root),
    ]


def _sublime_settings_paths(home: Path) -> list[Path]:
    return [
        home / app_dir / "Packages" / "User" / "Python.sublime-settings"
        for app_dir in SUBLIME_APP_DIRS
        if (home / app_dir).is_dir()
    ]


def ensure_sublime_user(home: Path) -> list[EditorSetupChange]:
    changes: list[EditorSetupChange] = []
    paths = _sublime_settings_paths(home)
    if not paths:
        return [
            EditorSetupChange(
                str(home),
                "skipped",
                "sublime",
                "Sublime Text user package directory not detected",
            )
        ]
    for path in paths:
        settings, reason = _read_json_object(path)
        if settings is None:
            changes.append(EditorSetupChange(str(path), "skipped", "sublime", reason))
            continue
        extensions = settings.get("extensions")
        if extensions is None:
            extensions = []
        if not isinstance(extensions, list) or any(
            not isinstance(value, str) for value in extensions
        ):
            changes.append(
                EditorSetupChange(
                    str(path),
                    "skipped",
                    "sublime",
                    "extensions is not a string list",
                )
            )
            continue
        if "pypeline" not in extensions:
            extensions.append("pypeline")
        settings["extensions"] = sorted(set(extensions))
        changes.append(_write_if_changed(path, _json_dump(settings), "sublime"))
    return changes


def ensure_vim_user(home: Path) -> list[EditorSetupChange]:
    targets = [
        home / ".vim" / "ftdetect" / "pypeline.vim",
        home / ".config" / "nvim" / "ftdetect" / "pypeline.vim",
    ]
    changes: list[EditorSetupChange] = []
    for path in targets:
        editor_root = path.parents[1]
        target = "neovim" if "nvim" in path.parts else "vim"
        if not editor_root.exists():
            changes.append(
                EditorSetupChange(
                    str(path),
                    "skipped",
                    target,
                    f"{editor_root} not detected",
                )
            )
            continue
        changes.append(_write_if_changed(path, VIM_FTDETECT, target))
    return changes


def ensure_emacs_user(home: Path) -> EditorSetupChange:
    emacs_dir = home / ".emacs.d"
    path = emacs_dir / "pypeline-mode.el"
    if not emacs_dir.exists():
        return EditorSetupChange(
            str(path),
            "skipped",
            "emacs",
            f"{emacs_dir} not detected",
        )
    return _write_if_changed(path, EMACS_MODE_SNIPPET, "emacs")


def ensure_user_editor_support(home: Path) -> list[EditorSetupChange]:
    home = home.expanduser().resolve()
    changes: list[EditorSetupChange] = []
    changes.extend(ensure_sublime_user(home))
    changes.extend(ensure_vim_user(home))
    changes.append(ensure_emacs_user(home))
    changes.append(
        EditorSetupChange(
            "JetBrains Editor | File Types",
            "manual",
            "jetbrains",
            "associate *.pypeline with Python in IDE settings",
        )
    )
    return changes


def maybe_auto_sync_repo_editor_support(start: Path) -> None:
    """Best-effort repo-local sync used by CLI startup.

    This intentionally touches only project-local files that are safe to commit.
    User-level editor preferences remain opt-in via ``megaplan setup --editors
    --user-editors``.
    """

    try:
        root = _find_git_root(start.resolve())
        if root is None:
            return
        ensure_repo_editor_support(root)
    except Exception:
        pass


def _find_git_root(start: Path) -> Path | None:
    current = start
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent
