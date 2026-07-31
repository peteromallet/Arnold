from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cli.setup import (
    handle_setup,
    handle_setup_hook_check,
    handle_setup_hooks,
    pre_commit_hook_status,
)
from arnold_pipelines.megaplan.types import CliError


def _repo(path: Path) -> Path:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    return path


def test_stale_hook_fails_with_exact_refresh_command(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    hook_path = repo / ".git" / "hooks" / "pre-commit"
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text(
        "#!/bin/sh\ngit add obsolete/generated/path\n", encoding="utf-8"
    )

    assert pre_commit_hook_status(repo) == ("stale", hook_path.resolve())
    with pytest.raises(CliError, match=r"setup --install-hooks --force"):
        handle_setup_hook_check(repo)


def test_force_refresh_repairs_stale_hook(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    hook_path = repo / ".git" / "hooks" / "pre-commit"
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    result = handle_setup_hooks(repo, force=True)

    assert result["success"] is True
    assert pre_commit_hook_status(repo)[0] == "current"
    assert hook_path.stat().st_mode & 0o111
    assert "git add arnold_pipelines/megaplan/data/_composed/" not in hook_path.read_text(
        encoding="utf-8"
    )
    assert "setup --check-hooks" in hook_path.read_text(encoding="utf-8")


def test_regen_stages_only_reported_changed_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    changed = tmp_path / "generated.md"
    changed.write_text("generated", encoding="utf-8")
    seen: list[list[str]] = []

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cli.setup.handle_regen_composed",
        lambda: {
            "success": False,
            "changed": ["generated.md"],
            "changed_paths": [str(changed)],
            "summary": "changed",
        },
    )

    def fake_run(command, **kwargs):
        seen.append(list(command))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cli.setup.subprocess.run", fake_run
    )
    args = argparse.Namespace(
        regen_composed=True,
        stage_regenerated=True,
        editors=False,
        install_hooks=False,
        check_hooks=False,
        local=False,
        target_dir=None,
        force=False,
    )

    result = handle_setup(args)

    assert result["success"] is False
    assert seen == [["git", "add", "--", str(changed)]]
