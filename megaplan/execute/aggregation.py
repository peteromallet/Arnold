"""Aggregation helpers — stable unique strings, aggregate payload, and scope drift.

These helpers were extracted from ``megaplan.execute.core`` in M5c to keep
``core.py`` focused on orchestration/handler logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from megaplan._core import configured_robustness, is_creative_mode, is_prose_mode
from megaplan._core.io import list_batch_artifacts, read_json
from megaplan.execute.quality import (
    _capture_git_status_snapshot,
    _collect_execute_claimed_paths,
    _normalize_execute_claimed_path,
)
from megaplan.forms.directors_notes import update_directors_notes_at_aggregate
from megaplan.forms.provocations import select_active_checks
from megaplan.receipts.drift import collect_loc_by_file, compute_scope_drift
from megaplan.types import CliError, PlanState


def _stable_unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _build_aggregate_execution_payload(
    batch_payloads: list[dict[str, Any]],
    *,
    completed_batches: int,
    total_batches: int,
    mode: str = "code",
    plan_dir: Path | None = None,
    state: PlanState | None = None,
) -> dict[str, Any]:
    outputs = [
        f"Batch {index + 1}: {payload.get('output', '')}".strip()
        for index, payload in enumerate(batch_payloads)
    ]
    deviations: list[str] = []
    task_updates: list[dict[str, Any]] = []
    sense_check_acknowledgments: list[dict[str, Any]] = []
    if is_prose_mode({"config": {"mode": mode}}):
        sections_written: list[str] = []
    else:
        files_changed: list[str] = []
    commands_run: list[str] = []
    for payload in batch_payloads:
        if is_prose_mode({"config": {"mode": mode}}):
            sections_written.extend(
                [s for s in payload.get("sections_written", []) if isinstance(s, str)]
            )
        else:
            files_changed.extend(
                [path for path in payload.get("files_changed", []) if isinstance(path, str)]
            )
        commands_run.extend(
            [
                command
                for command in payload.get("commands_run", [])
                if isinstance(command, str)
            ]
        )
        deviations.extend(
            [issue for issue in payload.get("deviations", []) if isinstance(issue, str)]
        )
        task_updates.extend(
            [item for item in payload.get("task_updates", []) if isinstance(item, dict)]
        )
        sense_check_acknowledgments.extend(
            [
                item
                for item in payload.get("sense_check_acknowledgments", [])
                if isinstance(item, dict)
            ]
        )
    output = (
        f"Aggregated execute batches: completed {completed_batches}/{total_batches}."
    )
    if outputs:
        output = output + "\n" + "\n".join(outputs)
    result: dict[str, Any] = {
        "output": output,
        "commands_run": _stable_unique_strings(commands_run),
        "deviations": deviations,
        "task_updates": task_updates,
        "sense_check_acknowledgments": sense_check_acknowledgments,
    }
    if is_prose_mode({"config": {"mode": mode}}):
        result["sections_written"] = _stable_unique_strings(sections_written)
    else:
        result["files_changed"] = _stable_unique_strings(files_changed)
    if state is not None and plan_dir is not None and is_creative_mode(state):
        checks = select_active_checks(state, configured_robustness(state), plan_dir=plan_dir)
        fired = [
            check.get("provocation", {})
            for check in checks
            if isinstance(check, dict) and isinstance(check.get("provocation"), dict)
        ]
        voice = next(
            (
                check.get("provocateur_voice")
                for check in checks
                if isinstance(check, dict) and check.get("provocateur_voice")
            ),
            None,
        )
        update_directors_notes_at_aggregate(
            plan_dir,
            state,
            result,
            iteration=int(state.get("iteration") or 1),
            voice=voice,
            fired_provocations=fired,
            preserve_existing_provocations=True,
        )
    return result


def _collect_per_batch_claimed_paths(
    plan_dir: Path | None,
    project_dir: Path,
) -> set[str]:
    """Union of top-level ``files_changed`` across every on-disk batch artifact.

    In per-batch execute mode each ``--batch N`` invocation writes its claims to
    ``execution_batch_N.json``; the final aggregate transition only sees the
    current call's payload (empty for a test-only final batch or a plain
    post-batch ``execute``). Seeding the claim baseline from every on-disk
    artifact makes the scope-drift gate compare the working-tree diff against the
    UNION of all per-batch claims, not just the current call's.
    """
    if plan_dir is None:
        return set()
    claimed: set[str] = set()
    for artifact in list_batch_artifacts(plan_dir):
        try:
            payload = read_json(artifact)
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        if isinstance(payload, dict):
            claimed |= _collect_execute_claimed_paths(payload, project_dir)
    return claimed


def _compute_execute_scope_drift(
    project_dir: Path,
    aggregate_payload: dict[str, Any],
    state: PlanState | None = None,
    plan_dir: Path | None = None,
):
    files_claimed = _collect_execute_claimed_paths(aggregate_payload, project_dir)
    # Union per-batch claims from disk so per-batch execute mode compares the
    # working-tree diff against every batch's claims, not just this call's.
    files_claimed |= _collect_per_batch_claimed_paths(plan_dir, project_dir)
    if state is not None:
        config = state.get("config") or {}
        if config.get("mode") == "doc":
            output_path = config.get("output_path")
            if isinstance(output_path, str) and output_path.strip():
                files_claimed.add(
                    _normalize_execute_claimed_path(output_path, project_dir)
                )
    try:
        observed_snapshot, observed_error = _capture_git_status_snapshot(project_dir)
    except Exception as exc:
        raise CliError(
            "scope_drift_snapshot",
            "M3B_HALT_SCOPE_DRIFT_SNAPSHOT: "
            f"failed to capture git status snapshot while evaluating execute scope drift for {project_dir}: {exc}",
            extra={"project_dir": str(project_dir)},
        ) from exc
    files_in_diff = set(observed_snapshot.keys()) if observed_error is None else set()
    loc_by_file = collect_loc_by_file(project_dir, files_in_diff)
    return compute_scope_drift(
        files_claimed=files_claimed,
        files_in_diff=files_in_diff,
        loc_by_file=loc_by_file,
    )


def _append_scope_drift_blocker(
    blocking_reasons: list[str],
    state: PlanState,
    drift: Any,
) -> None:
    robustness = configured_robustness(state)
    if drift.severity == "high" and robustness in {"thorough", "extreme"}:
        blocking_reasons.append(
            f"scope_drift_severity=high: unclaimed files {sorted(drift.files_added)} "
            f"with {drift.loc_added_outside_claimed} LOC outside the claimed set"
        )


def _compute_scope_drift_for_execute_surface(
    *,
    project_dir: Path,
    aggregate_payload: dict[str, Any],
    state: PlanState,
    phase_context: str,
    plan_dir: Path | None = None,
) -> Any:
    try:
        return _compute_execute_scope_drift(
            project_dir, aggregate_payload, state, plan_dir=plan_dir
        )
    except CliError as exc:
        if exc.code != "scope_drift_snapshot":
            raise
        raise CliError(
            exc.code,
            f"{exc} ({phase_context})",
            extra={**exc.extra, "phase_context": phase_context},
        ) from exc
