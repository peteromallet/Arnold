"""Resume and abandon helpers for bake-offs."""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path
from typing import Any

from megaplan._core.io import now_utc
from megaplan._core.state import load_plan
import megaplan.bakeoff.orchestrator as orchestrator
from megaplan.bakeoff.state import (
    BakeoffProfileRecord,
    BakeoffState,
    load_bakeoff_state,
    save_bakeoff_state,
)
from megaplan.bakeoff.worktree import mark_crashed, remove_worktree
from megaplan.types import AUTOMATION_TERMINAL_STATES, CliError


def resume_bakeoff(root: Path, exp_id: str) -> int:
    asyncio.run(_resume_bakeoff(root, exp_id))
    return 0


def abandon_bakeoff(root: Path, exp_id: str) -> int:
    state = load_bakeoff_state(root, exp_id)
    for record in state.get("profiles", []):
        _abandon_profile_worktree(record)
    state["phase"] = "abandoned"
    save_bakeoff_state(root, state)
    return 0


async def _resume_bakeoff(root: Path, exp_id: str) -> BakeoffState:
    state = load_bakeoff_state(root, exp_id)
    wait_entries: list[
        tuple[BakeoffProfileRecord, asyncio.Task[tuple[BakeoffProfileRecord, dict[str, Any]]]]
    ] = []
    for record in state.get("profiles", []):
        if _should_skip_resume(state, record):
            continue
        task = await _launch_resume(root, state, record)
        if task is not None:
            wait_entries.append((record, task))
    results = await asyncio.gather(
        *(task for _, task in wait_entries),
        return_exceptions=True,
    )
    for (record, _), result in zip(wait_entries, results):
        if isinstance(result, Exception):
            reason = f"resume auto task failed: {result}"
            mark_crashed(Path(record["worktree"]), reason)
            record["outcome"] = orchestrator._failed_outcome(record["plan_id"], reason)
            record["terminated_at"] = now_utc()
            save_bakeoff_state(root, state)
            continue
        resumed, outcome = result
        resumed["outcome"] = outcome
        resumed["terminated_at"] = now_utc()
        save_bakeoff_state(root, state)
    return state


def _should_skip_resume(state: BakeoffState, record: BakeoffProfileRecord) -> bool:
    if record.get("name") == state.get("chosen_profile"):
        return True
    worktree = Path(record["worktree"])
    if not worktree.exists():
        return True
    try:
        _, plan_state = load_plan(worktree, record["plan_id"])
    except Exception:
        return True
    return str(plan_state.get("current_state") or "") in AUTOMATION_TERMINAL_STATES


async def _launch_resume(
    root: Path,
    state: BakeoffState,
    record: BakeoffProfileRecord,
) -> asyncio.Task[tuple[BakeoffProfileRecord, dict[str, Any]]] | None:
    worktree = Path(record["worktree"])
    try:
        spawned = await orchestrator._spawn_auto(
            worktree,
            record["plan_id"],
            Path(record["log_path"]),
            Path(record["outcome_path"]),
        )
    except Exception as exc:
        reason = f"resume auto launch failed: {exc}"
        mark_crashed(worktree, reason)
        record["outcome"] = orchestrator._failed_outcome(record["plan_id"], reason)
        record["terminated_at"] = now_utc()
        save_bakeoff_state(root, state)
        return None
    process, _ = spawned
    record["pid"] = getattr(process, "pid", None)
    record["launched_at"] = now_utc()
    record["terminated_at"] = None
    record["outcome"] = None
    save_bakeoff_state(root, state)
    return asyncio.create_task(orchestrator._wait_profile(record, spawned))


def _abandon_profile_worktree(record: BakeoffProfileRecord) -> None:
    target = Path(record["worktree"])
    if not target.exists():
        return
    try:
        remove_worktree(target, force=True)
    except CliError as exc:
        print(
            f"warning: failed to remove worktree for {record['name']}: {exc.message}",
            file=sys.stderr,
        )
        shutil.rmtree(target, ignore_errors=True)
