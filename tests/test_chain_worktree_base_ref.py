"""Regression for ticket 01KTQ35AB8.

`megaplan chain start --in-worktree` forked the shared worktree from the
*invoking* HEAD instead of the chain spec's ``base_branch``. When the invoking
branch was behind ``base_branch``, carried-untracked files that are tracked on
``base_branch`` collided on the chain's ``git checkout -B <milestone>
<base_branch>`` ("untracked working tree files would be overwritten").

The fix defaults the worktree fork-point to ``base_branch`` while still letting
an explicit ``--worktree-from`` override. These unit tests pin that resolution.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from megaplan.cli import _chain_worktree_base_ref


def _args(**kw: object) -> argparse.Namespace:
    base = {"worktree_from": None, "spec": None}
    base.update(kw)
    return argparse.Namespace(**base)


def _write_spec(tmp_path: Path, base_branch: str) -> Path:
    spec = tmp_path / "chain.yaml"
    spec.write_text(
        "base_branch: %s\n"
        "milestones:\n"
        "  - label: m0\n"
        "    idea: m0.md\n" % base_branch,
        encoding="utf-8",
    )
    return spec


def test_defaults_to_spec_base_branch(tmp_path: Path) -> None:
    spec = _write_spec(tmp_path, "develop")
    assert _chain_worktree_base_ref(_args(spec=str(spec))) == "develop"


def test_explicit_worktree_from_wins_over_base_branch(tmp_path: Path) -> None:
    spec = _write_spec(tmp_path, "develop")
    args = _args(spec=str(spec), worktree_from="release/1.2")
    assert _chain_worktree_base_ref(args) == "release/1.2"


def test_falls_back_to_head_without_spec() -> None:
    assert _chain_worktree_base_ref(_args()) == "HEAD"


def test_falls_back_to_head_on_unreadable_spec(tmp_path: Path) -> None:
    # Missing file -> load_spec raises CliError -> default to HEAD, not a crash.
    missing = tmp_path / "does-not-exist.yaml"
    assert _chain_worktree_base_ref(_args(spec=str(missing))) == "HEAD"


def test_spec_default_base_branch_is_main(tmp_path: Path) -> None:
    # A spec that omits base_branch defaults to "main" (ChainSpec default),
    # which is exactly the case that hit the bug live.
    spec = tmp_path / "chain.yaml"
    spec.write_text(
        "milestones:\n  - label: m0\n    idea: m0.md\n", encoding="utf-8"
    )
    assert _chain_worktree_base_ref(_args(spec=str(spec))) == "main"
