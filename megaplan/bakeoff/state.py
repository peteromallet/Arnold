"""Bake-off coordination state."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal, TypedDict

from megaplan._core.io import atomic_write_json, read_json


BAKEOFF_SCHEMA_VERSION: Literal[1] = 1
BakeoffPhase = Literal["running", "compared", "picked", "merged", "abandoned"]


class BakeoffProfileRecord(TypedDict):
    name: str
    worktree: str
    plan_id: str
    pid: int | None
    launched_at: str | None
    terminated_at: str | None
    outcome: dict[str, Any] | None
    log_path: str
    outcome_path: str


class BakeoffState(TypedDict, total=False):
    schema_version: Literal[1]
    experiment_id: str
    base_sha: str
    idea_hash: str
    idea_path: str
    mode: str
    # Relative (to each worktree) path to the doc artifact in --mode doc bake-offs.
    # Absent / None for code-mode bake-offs. Kept optional so historical state
    # files written before this field existed still load.
    output_path: str | None
    profiles: list[BakeoffProfileRecord]
    phase: BakeoffPhase
    chosen_profile: str | None
    merged_at: str | None
    judge_model: str | None


def bakeoff_root(root: Path, exp_id: str) -> Path:
    return root / ".megaplan" / "bakeoffs" / exp_id


def worktree_root(root: Path, exp_id: str) -> Path:
    return root.resolve().parent / ".megaplan-worktrees" / exp_id


def load_bakeoff_state(root: Path, exp_id: str) -> BakeoffState:
    return read_json(bakeoff_root(root, exp_id) / "bakeoff.json")


def save_bakeoff_state(root: Path, state: BakeoffState) -> None:
    atomic_write_json(
        bakeoff_root(root, state["experiment_id"]) / "bakeoff.json",
        state,
    )


def hash_idea_file(path: Path) -> str:
    content = path.read_text(encoding="utf-8").encode("utf-8")
    return hashlib.sha256(content).hexdigest()
