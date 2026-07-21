"""Handlers for bake-off observation commands."""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core.io import atomic_write_text, now_utc, read_json
from arnold_pipelines.megaplan._core.state import load_plan
from arnold_pipelines.megaplan.bakeoff.comparison import build_comparison, write_comparison
from arnold_pipelines.megaplan.bakeoff.judge import resolve_requested_judge, run_judge
from arnold_pipelines.megaplan.bakeoff.lifecycle import abandon_bakeoff, resume_bakeoff
from arnold_pipelines.megaplan.bakeoff.merge import merge_bakeoff
from arnold_pipelines.megaplan.bakeoff.metrics import collect_profile_metrics
from arnold_pipelines.megaplan.bakeoff.state import BakeoffProfileRecord, BakeoffState, load_bakeoff_state
from arnold_pipelines.megaplan.bakeoff.state import bakeoff_root, save_bakeoff_state
from arnold_pipelines.megaplan.bakeoff.wbc import (
    BAKEOFF_COMPARE_SURFACE,
    BAKEOFF_COMPARE_WRITER_ID,
    BAKEOFF_PICK_SURFACE,
    BAKEOFF_PICK_WRITER_ID,
    BakeoffWbcRule,
    record_bakeoff_wbc_evidence,
    validate_bakeoff_transition,
)
from arnold_pipelines.megaplan.types import CliError


def handle_status(root: Path, args: argparse.Namespace) -> int:
    exp_id = getattr(args, "exp", None) or _latest_experiment_id(root)
    state = load_bakeoff_state(root, exp_id)
    rows = _status_rows(state)
    _render_status(rows)
    return 0


def handle_tail(root: Path, args: argparse.Namespace) -> int:
    state = load_bakeoff_state(root, getattr(args, "exp"))
    records = list(state.get("profiles", []))
    profile = getattr(args, "profile", None)
    if profile:
        record = _find_profile(records, profile)
        return subprocess.run(["tail", "-F", record["log_path"]]).returncode
    asyncio.run(_tail_many(records))
    return 0


def handle_compare(root: Path, args: argparse.Namespace) -> int:
    state = load_bakeoff_state(root, getattr(args, "exp"))
    if state.get("phase") == "abandoned":
        raise CliError("bakeoff_abandoned", "Cannot compare an abandoned bake-off.")
    comparison_path = bakeoff_root(root, state["experiment_id"]) / "comparison.json"
    if comparison_path.exists() and not getattr(args, "force", False):
        print("comparison already exists; pass --force to overwrite")
        return 0

    metrics_by_profile = {
        record["name"]: collect_profile_metrics(state, record)
        for record in state.get("profiles", [])
    }
    judge_model = resolve_requested_judge(root, state, getattr(args, "judge", None))
    judge_verdict = (
        asyncio.run(run_judge(state, metrics_by_profile, judge_model))
        if judge_model is not None
        else None
    )
    compare_evidence = validate_bakeoff_transition(
        writer_id=BAKEOFF_COMPARE_WRITER_ID,
        surface_name=BAKEOFF_COMPARE_SURFACE,
        transition_name="compare_profiles",
        subject=state["experiment_id"],
        source_path=Path(__file__),
        project_dir=root,
        rules=(
            BakeoffWbcRule(
                "profile_count_nonzero",
                True,
                len(state.get("profiles", [])),
                len(state.get("profiles", [])) > 0,
            ),
        ),
        extra={"judge_model": judge_model},
    )
    comparison = build_comparison(state, metrics_by_profile, judge_verdict)
    write_comparison(root, comparison)
    state["phase"] = "compared"
    state["judge_model"] = judge_model
    record_bakeoff_wbc_evidence(
        state,
        entry_key=f"compare:{state['experiment_id']}",
        evidence=compare_evidence,
    )
    save_bakeoff_state(root, state)
    return 0


def handle_pick(root: Path, args: argparse.Namespace) -> int:
    state = load_bakeoff_state(root, getattr(args, "exp"))
    if state.get("phase") not in {"compared", "picked"}:
        raise CliError("bakeoff_pick_invalid_phase", "Run bakeoff compare before picking a profile.")
    comparison_path = bakeoff_root(root, state["experiment_id"]) / "comparison.json"
    if not comparison_path.exists():
        raise CliError("bakeoff_comparison_missing", "Run bakeoff compare before picking a profile.")
    comparison = read_json(comparison_path)
    profiles = comparison.get("profiles") if isinstance(comparison.get("profiles"), list) else []
    selected = _comparison_profile(profiles, getattr(args, "profile"))
    pick_evidence = validate_bakeoff_transition(
        writer_id=BAKEOFF_PICK_WRITER_ID,
        surface_name=BAKEOFF_PICK_SURFACE,
        transition_name="pick_profile",
        subject=state["experiment_id"],
        source_path=Path(__file__),
        project_dir=root,
        rules=(
            BakeoffWbcRule(
                "selected_profile_present",
                True,
                getattr(args, "profile"),
                bool(str(getattr(args, "profile") or "").strip()),
            ),
            BakeoffWbcRule(
                "comparison_exists",
                True,
                comparison_path.exists(),
                comparison_path.exists(),
            ),
        ),
        extra={"selected_profile": getattr(args, "profile")},
    )
    if selected.get("outcome_status") != "done":
        print(
            f"warning: picking profile '{args.profile}' with outcome_status={selected.get('outcome_status')!r}",
            file=sys.stderr,
        )
    comparison["human_decision"] = {
        "chosen_profile": getattr(args, "profile"),
        "rationale": getattr(args, "rationale", None),
        "decided_at": now_utc(),
    }
    atomic_write_text(comparison_path, json_dumps_sorted(comparison))
    state["chosen_profile"] = getattr(args, "profile")
    state["phase"] = "picked"
    record_bakeoff_wbc_evidence(
        state,
        entry_key=f"pick:{state['experiment_id']}",
        evidence=pick_evidence,
    )
    save_bakeoff_state(root, state)
    return 0


def handle_merge(root: Path, args: argparse.Namespace) -> int:
    return merge_bakeoff(root, getattr(args, "exp"))


def handle_resume(root: Path, args: argparse.Namespace) -> int:
    return resume_bakeoff(root, getattr(args, "exp"))


def handle_abandon(root: Path, args: argparse.Namespace) -> int:
    return abandon_bakeoff(root, getattr(args, "exp"))


def _latest_experiment_id(root: Path) -> str:
    bakeoffs_dir = root / ".megaplan" / "bakeoffs"
    candidates = [
        child
        for child in bakeoffs_dir.iterdir()
        if child.is_dir() and (child / "bakeoff.json").exists()
    ] if bakeoffs_dir.exists() else []
    if not candidates:
        raise CliError("bakeoff_missing", "No bake-offs found; pass --exp after running bakeoff run.")
    return max(candidates, key=lambda path: path.stat().st_mtime).name


def _status_rows(state: BakeoffState) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for record in state.get("profiles", []):
        plan_state: dict[str, Any] = {}
        worktree = Path(record["worktree"])
        if worktree.exists():
            try:
                _, loaded = load_plan(worktree, record["plan_id"])
                plan_state = dict(loaded)
            except Exception:
                plan_state = {}
        meta = plan_state.get("meta") if isinstance(plan_state.get("meta"), dict) else {}
        rows.append(
            {
                "profile": str(record.get("name") or ""),
                "state": str(plan_state.get("current_state") or _outcome_status(record) or "missing"),
                "phase": _phase(plan_state),
                "iter": str(plan_state.get("iteration") or ""),
                "age": _age(record.get("launched_at")),
                "cost": _format_cost(meta.get("total_cost_usd")),
            }
        )
    return rows


def _render_status(rows: list[dict[str, str]]) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
    except Exception:
        _render_plain_status(rows)
        return
    table = Table(show_header=True)
    for column in ["profile", "state", "phase", "iter", "age", "cost"]:
        table.add_column(column)
    for row in rows:
        table.add_row(*(row[column] for column in ["profile", "state", "phase", "iter", "age", "cost"]))
    Console().print(table)


def _render_plain_status(rows: list[dict[str, str]]) -> None:
    columns = ["profile", "state", "phase", "iter", "age", "cost"]
    widths = {
        column: max(len(column), *(len(row[column]) for row in rows)) if rows else len(column)
        for column in columns
    }
    header = " | ".join(column.ljust(widths[column]) for column in columns)
    print(header)
    print("-+-".join("-" * widths[column] for column in columns))
    for row in rows:
        print(" | ".join(row[column].ljust(widths[column]) for column in columns))


async def _tail_many(records: list[BakeoffProfileRecord]) -> None:
    processes: list[asyncio.subprocess.Process] = []
    tasks: list[asyncio.Task[None]] = []
    try:
        for record in records:
            process = await asyncio.create_subprocess_exec(
                "tail",
                "-F",
                record["log_path"],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            processes.append(process)
            tasks.append(asyncio.create_task(_prefix_stream(record["name"], process)))
        if tasks:
            await asyncio.gather(*tasks)
    finally:
        for process in processes:
            if process.returncode is None:
                process.terminate()


async def _prefix_stream(profile: str, process: asyncio.subprocess.Process) -> None:
    assert process.stdout is not None
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        sys.stdout.write(f"[{profile}] {line.decode(errors='replace')}")
        sys.stdout.flush()
    await process.wait()


def _find_profile(records: list[BakeoffProfileRecord], profile: str) -> BakeoffProfileRecord:
    for record in records:
        if record.get("name") == profile:
            return record
    raise CliError("bakeoff_profile_missing", f"Profile '{profile}' is not part of this bake-off.")


def _comparison_profile(profiles: list[Any], profile: str) -> dict[str, Any]:
    for record in profiles:
        if isinstance(record, dict) and record.get("name") == profile:
            return record
    raise CliError("bakeoff_profile_missing", f"Profile '{profile}' is not part of this bake-off.")


def json_dumps_sorted(data: Any) -> str:
    import json

    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _phase(plan_state: dict[str, Any]) -> str:
    active = plan_state.get("active_step")
    if isinstance(active, dict):
        phase = active.get("phase") or active.get("step")
        if phase:
            return str(phase)
    history = plan_state.get("history")
    if isinstance(history, list) and history:
        last = history[-1]
        if isinstance(last, dict) and last.get("step"):
            return str(last["step"])
    return ""


def _outcome_status(record: BakeoffProfileRecord) -> str | None:
    outcome = record.get("outcome")
    if isinstance(outcome, dict) and outcome.get("status"):
        return str(outcome["status"])
    return None


def _age(launched_at: Any) -> str:
    if not isinstance(launched_at, str) or not launched_at:
        return ""
    try:
        started = datetime.fromisoformat(launched_at.replace("Z", "+00:00"))
    except ValueError:
        return ""
    seconds = max(0, int((datetime.now(timezone.utc) - started).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    minutes, remainder = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{remainder:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def _format_cost(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):.4f}"
    return ""
