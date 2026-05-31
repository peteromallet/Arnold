"""Supervisor bakeoff runner.

This module keeps the established bakeoff mechanics intact while expressing
the profile fan-out in the shared supervisor model.  Profile initialization,
metric comparison, optional judging, and merge behavior are delegated to the
existing bakeoff modules; the supervisor-owned part is the explicit run-node
and parallel-group state plus injected ``RunDriver`` execution.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol

from megaplan._core.io import atomic_write_text, now_utc, slugify
from megaplan.bakeoff.comparison import build_comparison, write_comparison
from megaplan.bakeoff.judge import resolve_requested_judge, run_judge
from megaplan.bakeoff.merge import merge_bakeoff
from megaplan.bakeoff.metrics import collect_profile_metrics
from megaplan.bakeoff.orchestrator import _default_experiment_id, _failed_outcome, _init_profile
from megaplan.bakeoff.state import (
    BAKEOFF_SCHEMA_VERSION,
    BakeoffProfileRecord,
    BakeoffState,
    bakeoff_root,
    hash_idea_file,
    save_bakeoff_state,
)
from megaplan.bakeoff.worktree import capture_base_sha, ensure_main_worktree_clean, mark_crashed
from megaplan.supervisor.driver import DefaultRunDriver, RunDriver, RunRequest
from megaplan.supervisor.model import (
    BakeoffParallelGroup,
    DependencyAssertion,
    RunNode,
    RunRecord,
    SupervisorState,
    SupervisorVariantKind,
)
from megaplan.supervisor.outcomes import normalize_driver_outcome_from_dict
from megaplan.supervisor.state import save_supervisor_state
from megaplan.types import CliError


ProfileInitializer = Callable[
    [Path, BakeoffState, str, str, str, Path, str | None, str, str | None],
    Awaitable[BakeoffProfileRecord],
]


class BakeoffMerger(Protocol):
    def __call__(self, root: Path, exp_id: str) -> int:
        ...


def run_bakeoff_run_handler(root: Path, args: Any) -> int:
    """Sync handler shape matching ``megaplan.bakeoff.orchestrator``."""

    run_bakeoff(
        root,
        args.idea_file,
        list(args.profiles),
        args.mode,
        exp_id=args.exp_id or _default_experiment_id(),
        allow_dirty=bool(getattr(args, "allow_dirty", False)),
        robustness=getattr(args, "robustness", None),
        output=getattr(args, "output", None),
        judge=getattr(args, "judge", None),
    )
    return 0


def run_bakeoff(
    root: Path,
    idea_path: Path | str,
    profiles: list[str],
    mode: str,
    exp_id: str | None = None,
    *,
    allow_dirty: bool = False,
    robustness: str | None = None,
    output: str | None = None,
    judge: str | None = None,
    driver: RunDriver | None = None,
    initializer: ProfileInitializer | None = None,
    merger: BakeoffMerger | None = None,
    merge: bool = True,
) -> dict[str, Any]:
    """Run a bakeoff through the supervisor fan-out/reduce path.

    ``profiles`` is consumed as supplied; no profile matrix expansion or judge
    prompt/rubric changes happen here.  The reduce phase uses the existing
    comparison, judge, winner-pick state, and merge helpers.
    """

    return asyncio.run(
        _run_bakeoff_async(
            root,
            idea_path,
            profiles,
            mode,
            exp_id=exp_id,
            allow_dirty=allow_dirty,
            robustness=robustness,
            output=output,
            judge=judge,
            driver=driver,
            initializer=initializer,
            merger=merger,
            merge=merge,
        )
    )


async def _run_bakeoff_async(
    root: Path,
    idea_path: Path | str,
    profiles: list[str],
    mode: str,
    exp_id: str | None,
    *,
    allow_dirty: bool,
    robustness: str | None,
    output: str | None,
    judge: str | None,
    driver: RunDriver | None,
    initializer: ProfileInitializer | None,
    merger: BakeoffMerger | None,
    merge: bool,
) -> dict[str, Any]:
    _validate_bakeoff_args(mode=mode, output=output)
    if not profiles:
        raise CliError("invalid_args", "bake-off requires at least one profile.")

    root = root.resolve()
    idea = Path(idea_path).resolve()
    experiment_id = exp_id or _default_experiment_id()
    ensure_main_worktree_clean(root, allow_dirty=allow_dirty)
    idea_hash = hash_idea_file(idea)
    base_sha = capture_base_sha(root)
    archive_root = bakeoff_root(root, experiment_id)
    archive_root.mkdir(parents=True, exist_ok=True)

    bakeoff_state = _initial_bakeoff_state(
        experiment_id=experiment_id,
        base_sha=base_sha,
        idea_hash=idea_hash,
        idea=idea,
        mode=mode,
        output=output,
    )
    save_bakeoff_state(root, bakeoff_state)

    supervisor_state = _initial_supervisor_state(
        experiment_id=experiment_id,
        profiles=profiles,
        mode=mode,
        output=output,
        robustness=robustness,
    )
    save_supervisor_state(root, experiment_id, supervisor_state)

    init = initializer or _default_profile_initializer
    for profile in profiles:
        record = await init(
            root,
            bakeoff_state,
            profile,
            experiment_id,
            base_sha,
            idea,
            robustness,
            mode,
            output,
        )
        bakeoff_state["profiles"].append(record)
        save_bakeoff_state(root, bakeoff_state)

    run_driver = driver or DefaultRunDriver()
    records = await asyncio.gather(
        *[
            _execute_profile_node(root, experiment_id, supervisor_state, record, run_driver)
            for record in bakeoff_state.get("profiles", [])
        ]
    )
    supervisor_state.run_records.extend(records)
    supervisor_state.completed_node_ids = [record.node_id for record in records]
    supervisor_state.metadata["parallel_group_completed_at"] = now_utc()
    save_supervisor_state(root, experiment_id, supervisor_state)
    save_bakeoff_state(root, bakeoff_state)

    comparison = await _compare_and_select(root, bakeoff_state, judge)
    selected = _select_winner_profile(bakeoff_state, comparison)
    _record_winner_selection(root, bakeoff_state, selected, comparison)
    merge_code = (merger or merge_bakeoff)(root, experiment_id) if merge else None

    persisted_supervisor = save_supervisor_state(root, experiment_id, supervisor_state)
    return {
        "status": "merged" if merge else "picked",
        "experiment_id": experiment_id,
        "selected_profile": selected,
        "merge_code": merge_code,
        "bakeoff_state": bakeoff_state,
        "comparison": comparison,
        "supervisor_state_path": str(persisted_supervisor),
        "parallel_group": supervisor_state.bakeoff_parallel_groups[0].to_dict(),
        "run_nodes": [node.to_dict() for node in supervisor_state.run_nodes],
        "run_records": [record.to_dict() for record in supervisor_state.run_records],
    }


async def _default_profile_initializer(
    root: Path,
    state: BakeoffState,
    profile: str,
    experiment_id: str,
    base_sha: str,
    idea: Path,
    robustness: str | None,
    mode: str,
    output: str | None,
) -> BakeoffProfileRecord:
    return await _init_profile(
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


async def _execute_profile_node(
    root: Path,
    experiment_id: str,
    supervisor_state: SupervisorState,
    record: BakeoffProfileRecord,
    driver: RunDriver,
) -> RunRecord:
    profile = record["name"]
    node_id = _profile_node_id(profile)
    record["launched_at"] = now_utc()
    try:
        outcome = await asyncio.to_thread(
            driver.drive,
            RunRequest(root=Path(record["worktree"]), plan=record["plan_id"]),
        )
        outcome_dict = asdict(outcome)
    except Exception as exc:
        reason = f"auto driver failed: {exc}"
        mark_crashed(Path(record["worktree"]), reason)
        outcome_dict = _failed_outcome(record["plan_id"], reason)
    record["outcome"] = outcome_dict
    record["terminated_at"] = now_utc()
    normalized = normalize_driver_outcome_from_dict(outcome_dict)
    _write_outcome_file(record, outcome_dict)
    return RunRecord(
        node_id=node_id,
        attempt=_attempt_for_node(supervisor_state, node_id),
        outcome=normalized.outcome,
        original_status=normalized.original_status,
        plan_id=normalized.plan,
        final_state=normalized.final_state,
        reason=normalized.reason,
        last_phase=normalized.last_phase,
        blocking_reasons=tuple(normalized.blocking_reasons),
        total_cost_usd=normalized.total_cost_usd,
        tier_escalations_used=normalized.tier_escalations_used,
        escalation_tier_pin=normalized.escalation_tier_pin,
        metadata={"profile": profile, "parallel_group_id": f"{experiment_id}:profiles"},
    )


async def _compare_and_select(
    root: Path,
    state: BakeoffState,
    judge: str | None,
) -> dict[str, Any]:
    metrics_by_profile = {
        record["name"]: collect_profile_metrics(state, record)
        for record in state.get("profiles", [])
    }
    judge_model = resolve_requested_judge(root, state, judge)
    judge_verdict = (
        await run_judge(state, metrics_by_profile, judge_model)
        if judge_model is not None
        else None
    )
    comparison = build_comparison(state, metrics_by_profile, judge_verdict)
    write_comparison(root, comparison)
    state["phase"] = "compared"
    state["judge_model"] = judge_model
    save_bakeoff_state(root, state)
    return comparison


def _select_winner_profile(state: BakeoffState, comparison: dict[str, Any]) -> str:
    profiles = state.get("profiles", [])
    profile_names = [record["name"] for record in profiles]
    done_profiles = {
        record["name"]
        for record in profiles
        if isinstance(record.get("outcome"), dict)
        and record["outcome"].get("status") == "done"
    }
    judge_verdict = comparison.get("judge_verdict")
    rank = judge_verdict.get("rank") if isinstance(judge_verdict, dict) else None
    if isinstance(rank, list):
        for ranked in rank:
            if isinstance(ranked, str) and ranked in done_profiles:
                return ranked
        for ranked in rank:
            if isinstance(ranked, str) and ranked in profile_names:
                return ranked
    if done_profiles:
        for profile in profile_names:
            if profile in done_profiles:
                return profile
    if profile_names:
        return profile_names[0]
    raise CliError("bakeoff_profile_missing", "No profiles are available to select.")


def _record_winner_selection(
    root: Path,
    state: BakeoffState,
    selected: str,
    comparison: dict[str, Any],
) -> None:
    comparison_path = bakeoff_root(root, state["experiment_id"]) / "comparison.json"
    comparison["human_decision"] = {
        "chosen_profile": selected,
        "rationale": "selected by supervisor bakeoff reduction",
        "decided_at": now_utc(),
    }
    atomic_write_text(
        comparison_path,
        json.dumps(comparison, indent=2, sort_keys=True) + "\n",
    )
    state["chosen_profile"] = selected
    state["phase"] = "picked"
    save_bakeoff_state(root, state)


def _initial_bakeoff_state(
    *,
    experiment_id: str,
    base_sha: str,
    idea_hash: str,
    idea: Path,
    mode: str,
    output: str | None,
) -> BakeoffState:
    return {
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


def _initial_supervisor_state(
    *,
    experiment_id: str,
    profiles: list[str],
    mode: str,
    output: str | None,
    robustness: str | None,
) -> SupervisorState:
    group_id = f"{experiment_id}:profiles"
    nodes = [
        RunNode(
            node_id=_profile_node_id(profile),
            spec_ref=profile,
            description=f"bakeoff profile {profile}",
            parallel_group_id=group_id,
            metadata={
                "profile": profile,
                "mode": mode,
                "output_path": output,
                "robustness": robustness,
            },
        )
        for profile in profiles
    ]
    return SupervisorState(
        variant=SupervisorVariantKind.BAKEOFF,
        run_nodes=nodes,
        dependency_assertions=[
            DependencyAssertion(node_id=node.node_id, depends_on=()) for node in nodes
        ],
        bakeoff_parallel_groups=[
            BakeoffParallelGroup(
                group_id=group_id,
                member_node_ids=tuple(node.node_id for node in nodes),
                comparison_node_id=f"{experiment_id}:compare",
                selection_node_id=f"{experiment_id}:select",
                merge_node_id=f"{experiment_id}:merge",
            )
        ],
        metadata={
            "experiment_id": experiment_id,
            "parallel_group_started_at": now_utc(),
        },
    )


def _write_outcome_file(record: BakeoffProfileRecord, outcome: dict[str, Any]) -> None:
    outcome_path = Path(record["outcome_path"])
    outcome_path.parent.mkdir(parents=True, exist_ok=True)
    outcome_path.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _attempt_for_node(state: SupervisorState, node_id: str) -> int:
    return 1 + sum(1 for record in state.run_records if record.node_id == node_id)


def _profile_node_id(profile: str) -> str:
    return f"profile:{slugify(profile)}"


def _validate_bakeoff_args(*, mode: str, output: str | None) -> None:
    if mode not in {"code", "doc"}:
        raise CliError(
            "invalid_args",
            f"bake-off --mode must be one of code, doc; got {mode!r}.",
        )
    if mode == "code" and output:
        raise CliError("invalid_args", "--output is only valid with --mode doc.")
    if mode == "doc" and not output:
        raise CliError("invalid_args", "--output is required when --mode doc is selected")


__all__ = [
    "ProfileInitializer",
    "run_bakeoff",
    "run_bakeoff_run_handler",
]
