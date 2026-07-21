"""Asymmetric bake-off merge helpers."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core.io import (
    atomic_write_text,
    collect_git_diff_patch,
    now_utc,
)
from arnold_pipelines.megaplan._core.state import write_plan_state
from arnold_pipelines.megaplan.bakeoff.state import (
    BakeoffProfileRecord,
    BakeoffState,
    bakeoff_root,
    load_bakeoff_state,
    save_bakeoff_state,
)
from arnold_pipelines.megaplan.bakeoff.wbc import (
    BAKEOFF_MERGE_SURFACE,
    BAKEOFF_MERGE_WRITER_ID,
    BakeoffWbcRule,
    record_bakeoff_wbc_evidence,
    validate_bakeoff_transition,
)
from arnold_pipelines.megaplan.bakeoff.worktree import ensure_main_worktree_clean, remove_worktree
from arnold_pipelines.megaplan.types import CliError


NO_CHANGES_SENTINEL = "No git changes detected."


def merge_bakeoff(root: Path, exp_id: str) -> int:
    state = load_bakeoff_state(root, exp_id)
    if state.get("phase") != "picked":
        raise CliError("bakeoff_merge_invalid_phase", "Run bakeoff pick before merge.")
    ensure_main_worktree_clean(root)
    chosen = state.get("chosen_profile")
    if not chosen:
        raise CliError("bakeoff_merge_missing_choice", "No chosen profile recorded.")
    merge_evidence = validate_bakeoff_transition(
        writer_id=BAKEOFF_MERGE_WRITER_ID,
        surface_name=BAKEOFF_MERGE_SURFACE,
        transition_name="merge_bakeoff",
        subject=exp_id,
        source_path=Path(__file__),
        project_dir=root,
        destructive=True,
        rules=(
            BakeoffWbcRule(
                "chosen_profile_present",
                True,
                chosen,
                bool(str(chosen).strip()),
            ),
            BakeoffWbcRule(
                "phase_is_picked",
                "picked",
                state.get("phase"),
                state.get("phase") == "picked",
            ),
        ),
        extra={"chosen_profile": chosen, "mode": state.get("mode") or "code"},
    )

    profiles = list(state.get("profiles", []))
    winner = _find_profile(profiles, chosen)
    archive_root = bakeoff_root(root, state["experiment_id"])
    mode = state.get("mode") or "code"
    if mode == "doc":
        # Doc-mode bake-offs ship a single document artifact, not a code diff.
        # Copy the winner's doc into main and skip git apply entirely.
        _merge_doc_winner(root, state, winner, archive_root)
    else:
        patch = collect_git_diff_patch(Path(winner["worktree"]))
        if patch == NO_CHANGES_SENTINEL:
            raise CliError("bakeoff_merge_no_changes", "Chosen profile has no git changes to merge.")
        patch_path = archive_root / "winner.patch"
        atomic_write_text(patch_path, patch + ("\n" if patch and not patch.endswith("\n") else ""))
        _git_apply(root, patch_path, check=True)
        _git_apply(root, patch_path, check=False)

    for profile in profiles:
        _archive_profile(root, state, profile)
    _copy_winner_plan(root, state, winner)
    for profile in profiles:
        _remove_profile_worktree(profile)

    state["phase"] = "merged"
    state["merged_at"] = now_utc()
    record_bakeoff_wbc_evidence(
        state,
        entry_key=f"merge:{exp_id}",
        evidence=merge_evidence,
    )
    save_bakeoff_state(root, state)
    return 0


def _merge_doc_winner(
    root: Path,
    state: BakeoffState,
    winner: BakeoffProfileRecord,
    archive_root: Path,
) -> None:
    output_path = state.get("output_path")
    if not output_path:
        raise CliError(
            "bakeoff_merge_missing_output",
            "doc-mode bake-off state has no output_path; cannot locate winner artifact.",
        )
    src = Path(winner["worktree"]) / output_path
    if not src.exists() or not src.is_file():
        raise CliError(
            "bakeoff_merge_no_changes",
            f"Chosen profile produced no doc artifact at {output_path}.",
        )
    dest = root / output_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = src.read_text(encoding="utf-8")
    atomic_write_text(dest, content)
    # Mirror the artifact into the bake-off archive so the merged doc is
    # auditable alongside the per-profile plans.
    archived = archive_root / "winner.doc"
    atomic_write_text(archived, content)


def _find_profile(records: list[BakeoffProfileRecord], profile: str) -> BakeoffProfileRecord:
    for record in records:
        if record.get("name") == profile:
            return record
    raise CliError("bakeoff_profile_missing", f"Profile '{profile}' is not part of this bake-off.")


def _git_apply(root: Path, patch_path: Path, *, check: bool) -> None:
    args = ["git", "apply"]
    if check:
        args.append("--check")
    args.append(str(patch_path))
    result = subprocess.run(args, cwd=root, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() or "git apply failed"
        code = "bakeoff_merge_conflict" if check else "bakeoff_merge_apply_failed"
        raise CliError(code, detail)


def _archive_profile(root: Path, state: BakeoffState, profile: BakeoffProfileRecord) -> None:
    exp_id = state["experiment_id"]
    archive_dir = bakeoff_root(root, exp_id) / profile["name"]
    worktree = Path(profile["worktree"])
    plan_src = worktree / ".megaplan" / "plans" / profile["plan_id"]
    _copy_plan(plan_src, archive_dir / "plan", project_dir=None)
    _copy_profile_artifact(Path(profile["log_path"]), archive_dir / "auto.log")
    _copy_profile_artifact(Path(profile["outcome_path"]), archive_dir / "outcome.json")
    _copy_profile_artifact(archive_dir / "init.log", archive_dir / "init.log")


def _copy_winner_plan(root: Path, state: BakeoffState, winner: BakeoffProfileRecord) -> None:
    exp_id = state["experiment_id"]
    src = Path(winner["worktree"]) / ".megaplan" / "plans" / winner["plan_id"]
    dest = root / ".megaplan" / "plans" / f"{exp_id}-{winner['name']}"
    _copy_plan(src, dest, project_dir=str(root))


def _copy_plan(src: Path, dest: Path, *, project_dir: str | None) -> None:
    if not src.exists():
        raise CliError("bakeoff_plan_missing", f"Missing profile plan directory: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, dirs_exist_ok=True)
    _rewrite_project_dir(dest / "state.json", project_dir=project_dir)


def _rewrite_project_dir(state_path: Path, *, project_dir: str | None) -> None:
    if not state_path.exists():
        return
    write_plan_state(state_path.parent, mode="copy-time-rewrite", project_dir=project_dir)


def _copy_profile_artifact(src: Path, dest: Path) -> None:
    if not src.exists():
        return
    try:
        if src.resolve() == dest.resolve():
            return
    except FileNotFoundError:
        pass
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _remove_profile_worktree(profile: BakeoffProfileRecord) -> None:
    try:
        remove_worktree(Path(profile["worktree"]), force=True)
    except CliError as exc:
        print(
            f"warning: failed to remove worktree for {profile['name']}: {exc.message}",
            file=sys.stderr,
        )
