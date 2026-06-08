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
    _capture_git_status_snapshot_recursive,
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


def _expand_untracked_directory_entries(
    project_dir: Path,
    observed_snapshot: dict[str, str],
) -> dict[str, str]:
    expanded = dict(observed_snapshot)
    for path, digest in observed_snapshot.items():
        if not path.endswith("/") or digest != "<directory>":
            continue
        root = project_dir / path
        if not root.is_dir():
            continue
        expanded.pop(path, None)
        for candidate in root.rglob("*"):
            if candidate.is_file():
                expanded[candidate.relative_to(project_dir).as_posix()] = "<untracked>"
    return expanded


def _capture_execute_scope_snapshot(
    project_dir: Path,
    *,
    base_ref: str | None = None,
) -> tuple[dict[str, str], str | None]:
    observed_snapshot, observed_error = _capture_git_status_snapshot(
        project_dir, base_ref=base_ref
    )
    if observed_error is not None:
        return observed_snapshot, observed_error
    if not any(path.endswith("/") for path in observed_snapshot):
        return observed_snapshot, None
    recursive_snapshot, recursive_error = _capture_git_status_snapshot_recursive(
        project_dir, base_ref=base_ref
    )
    if recursive_error is None:
        return recursive_snapshot, None
    return _expand_untracked_directory_entries(project_dir, observed_snapshot), None


def _compute_execute_scope_drift(
    project_dir: Path,
    aggregate_payload: dict[str, Any],
    state: PlanState | None = None,
    plan_dir: Path | None = None,
):
    # This call's own claims drive the per-call ``files_missing`` (fabrication)
    # signal; the per-batch union below only widens ``files_claimed`` so prior
    # batches' writes aren't flagged as unclaimed additions.
    per_call_claimed = _collect_execute_claimed_paths(aggregate_payload, project_dir)
    files_claimed = set(per_call_claimed)
    # Union per-batch claims from disk so per-batch execute mode compares the
    # working-tree diff against every batch's claims, not just this call's.
    files_claimed |= _collect_per_batch_claimed_paths(plan_dir, project_dir)
    if state is not None:
        config = state.get("config") or {}
        if config.get("mode") == "doc":
            output_path = config.get("output_path")
            if isinstance(output_path, str) and output_path.strip():
                doc_path = _normalize_execute_claimed_path(output_path, project_dir)
                files_claimed.add(doc_path)
                per_call_claimed.add(doc_path)
    # Extract milestone window + carry-forward fields from chain_policy.
    chain_policy: dict[str, Any] = {}
    if state is not None:
        _cp = (state.get("meta") or {}).get("chain_policy")
        if isinstance(_cp, dict):
            chain_policy = _cp
    milestone_base_sha: str | None = chain_policy.get("milestone_base_sha")
    _cf_manifest = chain_policy.get("carry_forward_manifest")
    carry_forward_paths: set[str] = set()
    if isinstance(_cf_manifest, dict):
        carry_forward_paths = set(_cf_manifest.keys())
    elif isinstance(_cf_manifest, list):
        carry_forward_paths = {str(p) for p in _cf_manifest if isinstance(p, str)}

    try:
        observed_snapshot, observed_error = _capture_execute_scope_snapshot(
            project_dir, base_ref=milestone_base_sha
        )
    except Exception as exc:
        raise CliError(
            "scope_drift_snapshot",
            "M3B_HALT_SCOPE_DRIFT_SNAPSHOT: "
            f"failed to capture git status snapshot while evaluating execute scope drift for {project_dir}: {exc}",
            extra={"project_dir": str(project_dir)},
        ) from exc
    status_files: set[str] = set(observed_snapshot.keys()) if observed_error is None else set()

    # When a declared milestone base SHA is available, scope the diff to the
    # committed range since that SHA so pre-milestone committed changes are
    # excluded from scope drift.
    if milestone_base_sha:
        from megaplan.loop.git import _collect_committed_range_paths
        window_files = _collect_committed_range_paths(project_dir, base_ref=milestone_base_sha)
        files_in_diff: set[str] = window_files | status_files
    else:
        files_in_diff = status_files

    # Carry-forward files are inherited from a prior milestone — exclude them
    # from scope drift entirely (non-blocking by definition).
    if carry_forward_paths:
        files_in_diff = files_in_diff - carry_forward_paths

    loc_by_file = collect_loc_by_file(project_dir, files_in_diff)
    return compute_scope_drift(
        files_claimed=files_claimed,
        files_in_diff=files_in_diff,
        loc_by_file=loc_by_file,
        files_claimed_for_missing=per_call_claimed,
    )


def _append_scope_drift_blocker(
    blocking_reasons: list[str],
    state: PlanState,
    drift: Any,
) -> None:
    robustness = configured_robustness(state)
    if drift.severity != "high":
        # Low/none severity (benign artifacts, directory markers, sub-threshold
        # churn) stays quiet at every robustness level — unchanged behaviour.
        return
    if robustness in {"thorough", "extreme"}:
        blocking_reasons.append(
            f"scope_drift_severity=high: unclaimed files {sorted(drift.files_added)} "
            f"with {drift.loc_added_outside_claimed} LOC outside the claimed set"
        )
        return
    # DEFECT 3: on the common `full` robustness level, surface high-severity
    # unclaimed / no-task files as a RECOVERABLE blocking reason so the operator
    # sees which files changed without being attributed to any task (e.g. a
    # discovery side-effect rewriting production manifests). We only SURFACE —
    # never auto-revert / git restore — because that is too dangerous for the
    # concurrent live chains sharing this tree. `light`/`bare` stay quiet to
    # avoid noise on trivial runs; auto-attributed files never reach here
    # because attribution folds them into the claimed set before drift is
    # computed (so `files_added` excludes them). The severity bar matches the
    # hardened gate above; only the robustness scope is widened to include
    # `full`.
    if robustness == "full" and drift.files_added:
        blocking_reasons.append(
            f"scope_drift_unclaimed_files: files changed not claimed by any task: "
            f"{sorted(drift.files_added)} "
            f"({drift.loc_added_outside_claimed} LOC outside the claimed set). "
            "Review these and attribute them to a task or recover-blocked after "
            "operator review (no files were reverted)."
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
