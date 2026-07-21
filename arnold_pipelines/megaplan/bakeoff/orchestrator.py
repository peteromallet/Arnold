"""Async orchestration for multi-profile bake-offs."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

from arnold_pipelines.megaplan._core.io import now_utc
from arnold_pipelines.megaplan.bakeoff.live_status import print_live_status
from arnold_pipelines.megaplan.bakeoff.state import (
    BAKEOFF_SCHEMA_VERSION,
    BakeoffProfileRecord,
    BakeoffState,
    bakeoff_root,
    hash_idea_file,
    save_bakeoff_state,
    worktree_root,
)
from arnold_pipelines.megaplan.bakeoff.wbc import (
    BAKEOFF_RUN_SURFACE,
    BAKEOFF_RUN_WRITER_ID,
    BakeoffWbcRule,
    record_bakeoff_wbc_evidence,
    validate_bakeoff_transition,
)
from arnold_pipelines.megaplan.bakeoff.worktree import (
    capture_base_sha,
    create_worktree,
    ensure_main_worktree_clean,
    mark_crashed,
)
from arnold_pipelines.megaplan.types import CliError

SpawnedAuto = tuple[asyncio.subprocess.Process, IO[bytes] | None]

async def run_bakeoff(
    root: Path,
    idea_path: Path | str,
    profiles: list[str],
    mode: str,
    exp_id: str | None = None,
    *,
    allow_dirty: bool = False,
    detach: bool = False,
    robustness: str | None = None,
    output: str | None = None,
) -> BakeoffState:
    if mode not in {"code", "doc"}:
        raise CliError(
            "invalid_args",
            f"bake-off --mode must be one of code, doc; got {mode!r}.",
        )
    if mode == "code" and output:
        raise CliError(
            "invalid_args",
            "--output is only valid with --mode doc.",
        )
    if mode == "doc" and not output:
        raise CliError(
            "invalid_args",
            "--output is required when --mode doc is selected",
        )
    root = root.resolve()
    idea = Path(idea_path).resolve()
    experiment_id = exp_id or _default_experiment_id()
    ensure_main_worktree_clean(root, allow_dirty=allow_dirty)
    idea_hash = hash_idea_file(idea)
    base_sha = capture_base_sha(root)
    archive_root = bakeoff_root(root, experiment_id)
    archive_root.mkdir(parents=True, exist_ok=True)

    state: BakeoffState = {
        "schema_version": BAKEOFF_SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "base_sha": base_sha,
        "idea_hash": idea_hash,
        "idea_path": str(idea),
        "mode": mode,
        "output_path": output,
        "profiles": [],
        "phase": "running",
        "chosen_profile": None,
        "merged_at": None,
        "judge_model": None,
    }
    run_evidence = validate_bakeoff_transition(
        writer_id=BAKEOFF_RUN_WRITER_ID,
        surface_name=BAKEOFF_RUN_SURFACE,
        transition_name="run_bakeoff",
        subject=experiment_id,
        source_path=Path(__file__),
        project_dir=root,
        destructive=True,
        rules=(
            BakeoffWbcRule(
                "idea_exists",
                True,
                idea.exists(),
                idea.exists(),
            ),
            BakeoffWbcRule(
                "mode_supported",
                True,
                mode in {"code", "doc"},
                mode in {"code", "doc"},
            ),
        ),
        extra={
            "mode": mode,
            "profile_count": len(profiles),
            "output_path": output,
        },
    )
    record_bakeoff_wbc_evidence(
        state,
        entry_key=f"run:{experiment_id}",
        evidence=run_evidence,
    )
    save_bakeoff_state(root, state)

    created_worktrees: list[Path] = []
    try:
        for profile in profiles:
            record = await _init_profile(
                root,
                state,
                profile,
                experiment_id,
                base_sha,
                idea,
                robustness=robustness,
                mode=mode,
                output=output,
            )
            created_worktrees.append(Path(record["worktree"]))
            state["profiles"].append(record)
            save_bakeoff_state(root, state)
    except Exception as exc:
        for worktree in created_worktrees:
            mark_crashed(worktree, f"init failed: {exc}")
        raise

    wait_entries: list[
        tuple[BakeoffProfileRecord, asyncio.Task[tuple[BakeoffProfileRecord, dict[str, Any]]]]
    ] = []
    for record in state["profiles"]:
        result = await _launch_profile_auto(root, state, record)
        if result is not None:
            wait_entries.append((record, result))

    if detach:
        # Per-profile auto subprocesses were launched via create_subprocess_exec
        # with stdout/stderr redirected to log files; they continue running as
        # independent OS processes after this coroutine returns. User polls
        # outcomes via `megaplan bakeoff status`.
        return state

    results = await asyncio.gather(*(task for _, task in wait_entries), return_exceptions=True)
    for (record, _), result in zip(wait_entries, results):
        if isinstance(result, Exception):
            reason = f"auto task failed: {result}"
            mark_crashed(Path(record["worktree"]), reason)
            record["outcome"] = _failed_outcome(record["plan_id"], reason)
            record["terminated_at"] = now_utc()
            save_bakeoff_state(root, state)
            continue
        record, outcome = result
        record["outcome"] = outcome
        record["terminated_at"] = now_utc()
        save_bakeoff_state(root, state)
    return state


async def _init_profile(
    root: Path,
    state: BakeoffState,
    profile: str,
    experiment_id: str,
    base_sha: str,
    idea: Path,
    *,
    robustness: str | None = None,
    mode: str = "code",
    output: str | None = None,
) -> BakeoffProfileRecord:
    init_evidence = validate_bakeoff_transition(
        writer_id=BAKEOFF_RUN_WRITER_ID,
        surface_name=BAKEOFF_RUN_SURFACE,
        transition_name="init_profile",
        subject=f"{experiment_id}:{profile}",
        source_path=Path(__file__),
        project_dir=root,
        destructive=True,
        rules=(
            BakeoffWbcRule(
                "profile_name_present",
                True,
                bool(str(profile).strip()),
                bool(str(profile).strip()),
            ),
            BakeoffWbcRule(
                "base_sha_present",
                True,
                bool(str(base_sha).strip()),
                bool(str(base_sha).strip()),
            ),
        ),
        extra={
            "mode": mode,
            "output_path": output,
            "robustness": robustness,
        },
    )
    worktree = worktree_root(root, experiment_id) / profile
    profile_archive = bakeoff_root(root, experiment_id) / profile
    profile_archive.mkdir(parents=True, exist_ok=True)
    create_worktree(root, worktree, base_sha)
    # Project-layer profiles live in .megaplan/profiles.toml, which is
    # gitignored and therefore absent from the fresh worktree. Copy it in so
    # `megaplan init --profile <name>` can resolve project-only profiles.
    src_profiles = root / ".megaplan" / "profiles.toml"
    if src_profiles.is_file():
        dst_profiles = worktree / ".megaplan" / "profiles.toml"
        dst_profiles.parent.mkdir(parents=True, exist_ok=True)
        dst_profiles.write_bytes(src_profiles.read_bytes())
    cmd = [
        sys.executable,
        "-m",
        "arnold_pipelines.megaplan",
        "init",
        "--project-dir",
        str(worktree),
        "--name",
        experiment_id,
        "--idea-file",
        str(idea),
        "--profile",
        profile,
        "--mode",
        mode,
    ]
    if mode == "doc":
        if not output:
            # Defensive: should be caught upstream, but never spawn `init` in
            # doc mode without --output (init would reject it anyway).
            raise CliError(
                "invalid_args",
                "doc-mode bake-off requires --output to thread into each profile's init.",
            )
        cmd.extend(["--output", output])
    if robustness is not None:
        cmd.extend(["--robustness", robustness])
    init_log = profile_archive / "init.log"
    with init_log.open("ab") as log:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=worktree,
            stdout=log,
            stderr=log,
        )
        code = await proc.wait()
    if code != 0:
        mark_crashed(worktree, _tail(init_log))
        raise CliError("bakeoff_init_failed", f"profile {profile} init failed: {_tail(init_log)}")
    return {
        "name": profile,
        "worktree": str(worktree),
        "plan_id": experiment_id,
        "pid": None,
        "launched_at": None,
        "terminated_at": None,
        "outcome": None,
        "log_path": str(profile_archive / "auto.log"),
        "outcome_path": str(profile_archive / "outcome.json"),
        "wbc_transition_evidence": {
            "init_profile": init_evidence,
        },
    }


async def _launch_profile_auto(
    root: Path,
    state: BakeoffState,
    record: BakeoffProfileRecord,
) -> asyncio.Task[tuple[BakeoffProfileRecord, dict[str, Any]]] | None:
    worktree = Path(record["worktree"])
    log_path = Path(record["log_path"])
    outcome_path = Path(record["outcome_path"])
    launch_evidence = validate_bakeoff_transition(
        writer_id=BAKEOFF_RUN_WRITER_ID,
        surface_name=BAKEOFF_RUN_SURFACE,
        transition_name="launch_profile_auto",
        subject=f"{state['experiment_id']}:{record['name']}",
        source_path=Path(__file__),
        project_dir=root,
        destructive=True,
        rules=(
            BakeoffWbcRule(
                "worktree_exists",
                True,
                worktree.exists(),
                worktree.exists(),
            ),
            BakeoffWbcRule(
                "plan_id_present",
                True,
                bool(str(record.get("plan_id") or "").strip()),
                bool(str(record.get("plan_id") or "").strip()),
            ),
        ),
        extra={
            "worktree": str(worktree),
            "log_path": str(log_path),
            "outcome_path": str(outcome_path),
        },
    )
    try:
        spawned = await _spawn_auto(worktree, record["plan_id"], log_path, outcome_path)
    except Exception as exc:
        reason = f"auto launch failed: {exc}"
        mark_crashed(worktree, reason)
        record["outcome"] = _failed_outcome(record["plan_id"], reason)
        record["terminated_at"] = now_utc()
        save_bakeoff_state(root, state)
        return None
    process, _ = spawned
    record["pid"] = getattr(process, "pid", None)
    record["launched_at"] = now_utc()
    record_bakeoff_wbc_evidence(
        record,
        entry_key="launch_profile_auto",
        evidence=launch_evidence,
    )
    save_bakeoff_state(root, state)
    return asyncio.create_task(_wait_profile(record, spawned))


async def _spawn_auto(
    worktree: Path,
    plan_id: str,
    log_path: Path,
    outcome_path: Path,
) -> SpawnedAuto:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    outcome_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("ab")
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "arnold_pipelines.megaplan",
            "auto",
            "--plan",
            plan_id,
            "--outcome-file",
            str(outcome_path),
            cwd=worktree,
            stdout=log_handle,
            stderr=log_handle,
        )
    except Exception:
        log_handle.close()
        raise
    return process, log_handle


async def _wait_profile(
    record: BakeoffProfileRecord,
    spawned: SpawnedAuto,
) -> tuple[BakeoffProfileRecord, dict[str, Any]]:
    process, log_handle = spawned
    try:
        code = await process.wait()
    except Exception as exc:
        reason = f"auto wait failed: {exc}"
        mark_crashed(Path(record["worktree"]), reason)
        return record, _failed_outcome(record["plan_id"], reason)
    finally:
        if log_handle is not None:
            log_handle.close()

    outcome_path = Path(record["outcome_path"])
    if outcome_path.exists():
        try:
            return record, json.loads(outcome_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            reason = f"invalid outcome.json: {exc}"
            mark_crashed(Path(record["worktree"]), reason)
            return record, _failed_outcome(record["plan_id"], reason)
    reason = f"auto exited {code} without outcome.json: {_tail(Path(record['log_path']))}"
    mark_crashed(Path(record["worktree"]), reason)
    return record, _failed_outcome(record["plan_id"], reason)


def run_bakeoff_run_handler(root: Path, args: Any) -> int:
    exp_id = args.exp_id or _default_experiment_id()
    coro = _run_with_optional_status(root, args, exp_id)
    asyncio.run(coro)
    return 0


async def _run_with_optional_status(root: Path, args: Any, exp_id: str) -> BakeoffState:
    detach = bool(getattr(args, "detach", False))
    robustness = getattr(args, "robustness", None)
    output = getattr(args, "output", None)
    task = asyncio.create_task(
        run_bakeoff(
            root,
            args.idea_file,
            list(args.profiles),
            args.mode,
            exp_id,
            allow_dirty=bool(getattr(args, "allow_dirty", False)),
            detach=detach,
            robustness=robustness,
            output=output,
        )
    )
    if detach:
        return await task
    while not task.done():
        print_live_status(root, exp_id)
        await asyncio.sleep(5)
    return await task


def _failed_outcome(plan_id: str, reason: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "plan": plan_id,
        "final_state": "unknown",
        "iterations": 0,
        "reason": reason,
        "last_phase": None,
        "events": [],
    }


def _tail(path: Path, limit: int = 2000) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[-limit:].strip()


def _default_experiment_id() -> str:
    return datetime.now(timezone.utc).strftime("bakeoff-%Y%m%d-%H%M%S")
