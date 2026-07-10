"""Shared blocker recovery evaluation for execute/auto/operator commands."""

from __future__ import annotations

import hashlib
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from arnold_pipelines.megaplan.orchestration.phase_result import BlockedTask, Deviation
from arnold_pipelines.megaplan.quality_resolutions import (
    ADVANCE_WITH_DEBT,
    RERUN_REQUIRED,
    classify_quality_resolution_behavior,
    latest_quality_resolutions,
    validate_quality_resolution_event,
)
from arnold_pipelines.megaplan.resolutions import effective_user_action_resolutions
from arnold_pipelines.megaplan.resolution_contract import (
    FALLBACK,
    HARD_BLOCK,
    OMIT,
    classify_resolution_behavior,
    resolution_applies_to_task,
    resolution_state,
)

PREREQUISITE = "prerequisite"
QUALITY = "quality"
UNRESOLVED = "unresolved"
MALFORMED = "malformed"
_BEFORE_EXECUTE_GATE_PREFIX = "Read user_actions.md."


@dataclass(frozen=True)
class PrerequisiteScope:
    action_id: str
    action: dict[str, Any]
    effective_task_ids: tuple[str, ...]
    explicit_task_ids: tuple[str, ...] = ()
    synthetic_gate_task_id: str | None = None
    protected_task_ids: tuple[str, ...] = ()
    malformed_reason: str | None = None

    @property
    def uses_synthetic_gate_scope(self) -> bool:
        return self.synthetic_gate_task_id is not None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action_id": self.action_id,
            "effective_task_ids": list(self.effective_task_ids),
            "explicit_task_ids": list(self.explicit_task_ids),
            "uses_synthetic_gate_scope": self.uses_synthetic_gate_scope,
        }
        if self.synthetic_gate_task_id is not None:
            payload["synthetic_gate_task_id"] = self.synthetic_gate_task_id
            payload["protected_task_ids"] = list(self.protected_task_ids)
        if self.malformed_reason is not None:
            payload["malformed_reason"] = self.malformed_reason
        return payload


@dataclass(frozen=True)
class BlockerDetail:
    blocker_id: str
    blocker_kind: str
    task_id: str | None
    message: str
    blocking_action_ids: tuple[str, ...] = ()
    resolution_state: str = UNRESOLVED
    resolution_behavior: str = HARD_BLOCK
    phase: str | None = None
    evidence: tuple[str, ...] = ()
    debt_note: str | None = None
    fallback_mode: str | None = None
    instructions: str | None = None
    reason: str | None = None
    effective_task_ids: tuple[str, ...] = ()
    synthetic_gate_task_id: str | None = None
    protected_task_ids: tuple[str, ...] = ()
    is_non_terminal: bool = False
    is_terminal: bool = True
    requires_rerun: bool = False
    malformed_reason: str | None = None
    suggested_commands: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "blocker_id": self.blocker_id,
            "blocker_kind": self.blocker_kind,
            "task_id": self.task_id,
            "message": self.message,
            "blocking_action_ids": list(self.blocking_action_ids),
            "resolution_state": self.resolution_state,
            "resolution_behavior": self.resolution_behavior,
            "is_non_terminal": self.is_non_terminal,
            "is_terminal": self.is_terminal,
            "requires_rerun": self.requires_rerun,
            "suggested_commands": list(self.suggested_commands),
        }
        if self.phase is not None:
            payload["phase"] = self.phase
        if self.evidence:
            payload["evidence"] = list(self.evidence)
        if self.debt_note is not None:
            payload["debt_note"] = self.debt_note
        if self.fallback_mode is not None:
            payload["fallback_mode"] = self.fallback_mode
        if self.instructions is not None:
            payload["instructions"] = self.instructions
        if self.reason is not None:
            payload["reason"] = self.reason
        if self.effective_task_ids:
            payload["effective_task_ids"] = list(self.effective_task_ids)
        if self.synthetic_gate_task_id is not None:
            payload["synthetic_gate_task_id"] = self.synthetic_gate_task_id
        if self.protected_task_ids:
            payload["protected_task_ids"] = list(self.protected_task_ids)
        if self.malformed_reason is not None:
            payload["malformed_reason"] = self.malformed_reason
        return payload


@dataclass(frozen=True)
class BlockerRecoveryEvaluation:
    blockers: tuple[BlockerDetail, ...]

    @property
    def can_continue(self) -> bool:
        # Empty means the original failure source disappeared, for example a
        # stale recorded test failure now passes. Let recovery advance.
        #
        # `recover-blocked` resumes the predecessor phase so that rerun-required
        # blockers (for example quality findings marked `fixed`) can actually be
        # re-executed. Only terminal blockers must keep recovery pinned.
        return all(not blocker.is_terminal for blocker in self.blockers)

    @property
    def has_terminal_blockers(self) -> bool:
        return any(blocker.is_terminal for blocker in self.blockers)

    @property
    def requires_rerun(self) -> bool:
        return any(blocker.requires_rerun for blocker in self.blockers)

    def by_id(self) -> dict[str, BlockerDetail]:
        return {blocker.blocker_id: blocker for blocker in self.blockers}

    def to_dict(self) -> dict[str, Any]:
        return {
            "can_continue": self.can_continue,
            "has_terminal_blockers": self.has_terminal_blockers,
            "requires_rerun": self.requires_rerun,
            "blockers": [blocker.to_dict() for blocker in self.blockers],
        }


def prerequisite_blocker_id(action_id: str, task_id: str) -> str:
    return f"prereq:{action_id}:{task_id}"


def quality_blocker_id(deviation: Deviation) -> str:
    explicit_blocker_id = getattr(deviation, "blocker_id", None)
    if isinstance(explicit_blocker_id, str) and explicit_blocker_id:
        return explicit_blocker_id
    task_part = deviation.task_id or "global"
    stable_kind = _stable_quality_blocker_kind(deviation.message)
    if stable_kind is not None:
        return f"quality:{task_part}:{stable_kind}"
    digest_source = f"{deviation.kind}\n{deviation.task_id or ''}\n{deviation.message}"
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:12]
    return f"quality:{task_part}:{digest}"


def _stable_quality_blocker_kind(message: str) -> str | None:
    if message.startswith("scope_drift_severity="):
        severity = message.split(":", 1)[0].split("=", 1)[-1].strip() or "unknown"
        return f"scope-drift-{severity}"
    if message.startswith(
        "Advisory audit finding: Git status shows changed files not claimed by any task:"
    ):
        return "unclaimed-files"
    if message.startswith(
        "Advisory audit finding: Executor claimed changed files not present in git status:"
    ):
        return "claimed-files-missing-from-status"
    return None


def _is_informational_quality_deviation(message: str) -> bool:
    """Return True for non-blocking audit/bookkeeping notes.

    These messages are useful context in phase artifacts, but they do not
    represent operator-actionable blockers for ``recover-blocked``.
    """

    informational_prefixes = (
        "Advisory ",
        "Note:",
        "Backfilled batch-level metadata",
        "Execute response reconstructed from tool calls",
        "1/1 batch sense checks have no executor acknowledgment",
        "`file` utility was unavailable in the shell",
        "Scoped pytest currently fails in the cumulative workspace state",
        "Scoped pytest shows ",
        "Scoped pytest:",
        "agent_edit is now transitively imported by edit.py",
        "Leaf modules (",
        "Additional modules present in agent_edit/",
        "edit.py reduced from ",
    )
    if message.startswith(informational_prefixes):
        return True

    lowered = message.lower()
    informational_fragments = (
        "does not block",
        "noted but deferred",
    )
    return any(fragment in lowered for fragment in informational_fragments)


_TEST_NODEID_RE = re.compile(
    r"(?:\b|^)([\w/.\-]+\.py(?:::/?[\w\[\]<>\-]+)+)(?:\b|$)"
)


def _extract_nodeids(message: str) -> tuple[str, ...]:
    """Return pytest nodeids cited in a deviation message."""

    return tuple(match.group(1) for match in _TEST_NODEID_RE.finditer(message))


def _test_command_from_state(state: dict[str, Any]) -> str | None:
    config = state.get("config") if isinstance(state.get("config"), dict) else {}
    command = config.get("test_command") if isinstance(config, dict) else None
    return str(command).strip() if isinstance(command, str) and command.strip() else None


def _run_test_now_passes(
    nodeid: str,
    project_dir: Path,
    test_command: str | None,
    *,
    timeout_seconds: int = 60,
) -> bool:
    """Re-run one pytest nodeid and return True iff it now passes."""

    base = (test_command or "pytest").strip()
    for flag in ("-q", "--no-header", "-rA", "-rN", "--tb=no"):
        base = base.replace(flag, "")
    full_command = f"{base.strip()} {shlex.quote(nodeid)}"
    try:
        proc = subprocess.run(
            full_command,
            shell=True,
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


def _task_id(task: Any) -> str | None:
    if isinstance(task, dict) and isinstance(task.get("id"), str):
        return task["id"]
    return None


def _tasks_by_id(finalize_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tasks = finalize_data.get("tasks", [])
    if not isinstance(tasks, list):
        return {}
    return {
        task["id"]: task
        for task in tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }


def _depends_on(task: dict[str, Any]) -> tuple[str, ...]:
    raw = task.get("depends_on", [])
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in raw if isinstance(item, str))


def _is_synthetic_before_execute_gate_task(task: dict[str, Any]) -> bool:
    description = task.get("description")
    return isinstance(description, str) and description.startswith(
        _BEFORE_EXECUTE_GATE_PREFIX
    )


def find_synthetic_before_execute_gate(
    finalize_data: dict[str, Any],
) -> tuple[str | None, tuple[str, ...]]:
    """Derive the legacy before_execute gate from task dependency topology.

    The finalize handler injected this gate as a root task and made every other
    task directly depend on it. To avoid misclassifying unrelated root tasks
    (for example deferred baseline checkpoints in stale finalize payloads), the
    root task must also match the handler-owned user-action gate description.
    """
    tasks_by_id = _tasks_by_id(finalize_data)
    if len(tasks_by_id) < 2:
        return None, ()
    task_ids = set(tasks_by_id)
    candidates: list[tuple[str, tuple[str, ...]]] = []
    for task_id, task in tasks_by_id.items():
        if _depends_on(task):
            continue
        if not _is_synthetic_before_execute_gate_task(task):
            continue
        protected = tuple(
            sorted(
                other_id
                for other_id, other in tasks_by_id.items()
                if other_id != task_id and task_id in _depends_on(other)
            )
        )
        if set(protected) == (task_ids - {task_id}):
            candidates.append((task_id, protected))
    if len(candidates) != 1:
        return None, ()
    return candidates[0]


def build_prerequisite_scopes(
    finalize_data: dict[str, Any],
) -> dict[str, PrerequisiteScope]:
    tasks_by_id = _tasks_by_id(finalize_data)
    known_task_ids = set(tasks_by_id)
    gate_task_id, protected_task_ids = find_synthetic_before_execute_gate(finalize_data)
    raw_actions = finalize_data.get("user_actions", [])
    if not isinstance(raw_actions, list):
        return {}

    scopes: dict[str, PrerequisiteScope] = {}
    for action in raw_actions:
        if not isinstance(action, dict):
            continue
        action_id = action.get("id")
        if not isinstance(action_id, str) or not action_id.strip():
            continue
        phase = action.get("phase")
        blocks_task_ids = action.get("blocks_task_ids")
        if blocks_task_ids is None or blocks_task_ids == []:
            metadata_scope = _metadata_synthetic_gate_scope(
                action,
                known_task_ids=known_task_ids,
            )
            if metadata_scope is not None:
                metadata_gate_id, metadata_protected_ids = metadata_scope
                effective = tuple(sorted({metadata_gate_id, *metadata_protected_ids}))
                scopes[action_id] = PrerequisiteScope(
                    action_id=action_id,
                    action=action,
                    effective_task_ids=effective,
                    synthetic_gate_task_id=metadata_gate_id,
                    protected_task_ids=metadata_protected_ids,
                )
                continue
            if phase == "before_execute" and gate_task_id is not None:
                effective = tuple(sorted({gate_task_id, *protected_task_ids}))
                scopes[action_id] = PrerequisiteScope(
                    action_id=action_id,
                    action=action,
                    effective_task_ids=effective,
                    synthetic_gate_task_id=gate_task_id,
                    protected_task_ids=protected_task_ids,
                )
            else:
                scopes[action_id] = PrerequisiteScope(
                    action_id=action_id,
                    action=action,
                    effective_task_ids=(),
                    malformed_reason="missing task scope and no derivable synthetic gate",
                )
            continue
        if not isinstance(blocks_task_ids, list) or not all(
            isinstance(item, str) and item for item in blocks_task_ids
        ):
            scopes[action_id] = PrerequisiteScope(
                action_id=action_id,
                action=action,
                effective_task_ids=(),
                malformed_reason="blocks_task_ids must be a list of task IDs",
            )
            continue
        unknown = sorted(set(blocks_task_ids) - known_task_ids)
        if unknown:
            scopes[action_id] = PrerequisiteScope(
                action_id=action_id,
                action=action,
                effective_task_ids=(),
                explicit_task_ids=tuple(blocks_task_ids),
                malformed_reason="blocks_task_ids references unknown tasks: "
                + ", ".join(unknown),
            )
            continue
        scopes[action_id] = PrerequisiteScope(
            action_id=action_id,
            action=action,
            effective_task_ids=tuple(blocks_task_ids),
            explicit_task_ids=tuple(blocks_task_ids),
        )
    return scopes


def _metadata_synthetic_gate_scope(
    action: dict[str, Any],
    *,
    known_task_ids: set[str],
) -> tuple[str, tuple[str, ...]] | None:
    gate_task_id = action.get("synthetic_gate_task_id")
    protected = action.get("synthetic_gate_protected_task_ids")
    if gate_task_id is None and protected is None:
        return None
    if not isinstance(gate_task_id, str) or gate_task_id not in known_task_ids:
        return None
    if not isinstance(protected, list) or not all(
        isinstance(task_id, str) for task_id in protected
    ):
        return None
    protected_task_ids = tuple(
        task_id for task_id in protected if task_id in known_task_ids
    )
    if len(protected_task_ids) != len(protected):
        return None
    return gate_task_id, protected_task_ids


def _state_meta_list(state: dict[str, Any], field_name: str) -> list[dict[str, Any]]:
    meta = state.get("meta", {})
    if not isinstance(meta, dict):
        return []
    value = meta.get(field_name, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _prerequisite_detail(
    *,
    task_id: str,
    scope: PrerequisiteScope | None,
    resolution_event: dict[str, Any] | None,
    malformed_reason: str | None = None,
) -> BlockerDetail:
    action_id = scope.action_id if scope is not None else "unknown"
    blocker_id = prerequisite_blocker_id(action_id, task_id)
    state = resolution_state(resolution_event, source="memory") or UNRESOLVED
    if scope is None:
        behavior = RERUN_REQUIRED
    else:
        behavior = classify_resolution_behavior(state)
    is_non_terminal = behavior in {OMIT, FALLBACK}
    requires_rerun = behavior == RERUN_REQUIRED
    is_terminal = not is_non_terminal and not requires_rerun
    suggested_commands: tuple[str, ...] = ()
    if requires_rerun:
        suggested_commands = ("execute --retry-blocked-tasks",)
    elif is_terminal:
        suggested_commands = (
            f"user-action resolve --action-id {action_id} --tasks {task_id}",
        )

    return BlockerDetail(
        blocker_id=blocker_id,
        blocker_kind=PREREQUISITE,
        task_id=task_id,
        message=f"task {task_id} is blocked by user action {action_id}",
        blocking_action_ids=(action_id,) if action_id != "unknown" else (),
        resolution_state=state,
        resolution_behavior=behavior,
        phase="execute",
        evidence=_string_tuple((resolution_event or {}).get("evidence")),
        debt_note=_optional_str((resolution_event or {}).get("debt_note")),
        fallback_mode=_optional_str((resolution_event or {}).get("fallback_mode")),
        instructions=_optional_str((resolution_event or {}).get("instructions")),
        reason=_optional_str((resolution_event or {}).get("reason")),
        effective_task_ids=scope.effective_task_ids if scope is not None else (),
        synthetic_gate_task_id=(
            scope.synthetic_gate_task_id if scope is not None else None
        ),
        protected_task_ids=scope.protected_task_ids if scope is not None else (),
        is_non_terminal=is_non_terminal,
        is_terminal=is_terminal,
        requires_rerun=requires_rerun,
        malformed_reason=malformed_reason
        or (
            scope.malformed_reason if scope is not None else "no blocking action scope"
        ),
        suggested_commands=suggested_commands,
    )


def evaluate_prerequisite_blockers(
    finalize_data: dict[str, Any],
    state: dict[str, Any],
    blocked_tasks: Iterable[BlockedTask | dict[str, Any]],
    *,
    plan_dir: Path | None = None,
) -> BlockerRecoveryEvaluation:
    scopes = build_prerequisite_scopes(finalize_data)
    effective = effective_user_action_resolutions(plan_dir, state)
    details: list[BlockerDetail] = []

    for raw_blocked in blocked_tasks:
        blocked = _coerce_blocked_task(raw_blocked)
        if blocked is None:
            continue
        if _is_harness_generated_blocked_task(blocked):
            continue
        if blocked.blocking_action_ids:
            matching_scopes = [
                scopes[action_id]
                for action_id in blocked.blocking_action_ids
                if action_id in scopes
            ]
        else:
            matching_scopes = [
                scope
                for scope in scopes.values()
                if blocked.task_id in scope.effective_task_ids
            ]
        if not matching_scopes:
            details.append(
                _prerequisite_detail(
                    task_id=blocked.task_id,
                    scope=None,
                    resolution_event=None,
                )
            )
            continue
        for scope in matching_scopes:
            event = effective.get(scope.action_id)
            if event is not None and not resolution_applies_to_task(
                event, blocked.task_id, source="memory"
            ):
                event = None
            details.append(
                _prerequisite_detail(
                    task_id=blocked.task_id,
                    scope=scope,
                    resolution_event=event,
                )
            )
    return BlockerRecoveryEvaluation(tuple(details))


def _quality_detail(
    deviation: Deviation,
    resolution_event: dict[str, Any] | None,
    *,
    malformed_reason: str | None = None,
) -> BlockerDetail:
    blocker_id = quality_blocker_id(deviation)
    state = resolution_state(resolution_event, source="memory") or UNRESOLVED
    behavior = classify_quality_resolution_behavior(
        state,
        deviation_active=True,
    )
    is_non_terminal = behavior == ADVANCE_WITH_DEBT
    requires_rerun = behavior == RERUN_REQUIRED
    is_terminal = behavior == HARD_BLOCK
    suggested_commands: tuple[str, ...] = ()
    if is_terminal:
        suggested_commands = (f"quality-gate resolve --blocker-id {blocker_id}",)
    elif requires_rerun:
        suggested_commands = ("execute --retry-blocked-tasks",)

    return BlockerDetail(
        blocker_id=blocker_id,
        blocker_kind=QUALITY,
        task_id=deviation.task_id,
        message=deviation.message,
        resolution_state=state,
        resolution_behavior=behavior,
        phase=_optional_str((resolution_event or {}).get("phase"))
        or _optional_str(getattr(deviation, "phase", None)),
        evidence=_string_tuple((resolution_event or {}).get("evidence")),
        debt_note=_optional_str((resolution_event or {}).get("debt_note")),
        fallback_mode=_optional_str((resolution_event or {}).get("fallback_mode")),
        is_non_terminal=is_non_terminal,
        is_terminal=is_terminal,
        requires_rerun=requires_rerun,
        malformed_reason=malformed_reason,
        suggested_commands=suggested_commands,
    )


def evaluate_quality_blockers(
    state: dict[str, Any],
    deviations: Iterable[Deviation | dict[str, Any] | str],
) -> BlockerRecoveryEvaluation:
    latest = latest_quality_resolutions(
        _state_meta_list(state, "quality_gate_resolutions")
    )
    details: list[BlockerDetail] = []
    project_dir: Path | None = None
    test_command: str | None = None
    rerun_cache: dict[str, bool] = {}

    config = state.get("config") if isinstance(state.get("config"), dict) else {}
    raw_project_dir = config.get("project_dir") if isinstance(config, dict) else None
    if isinstance(raw_project_dir, (str, Path)):
        project_dir = Path(raw_project_dir)

    for raw_deviation in deviations:
        deviation = _coerce_deviation(raw_deviation)
        if deviation is None:
            continue
        if _is_informational_quality_deviation(deviation.message):
            continue

        nodeids = _extract_nodeids(deviation.message)
        if nodeids and project_dir is not None:
            if test_command is None:
                test_command = _test_command_from_state(state)
            all_pass = True
            for nodeid in nodeids:
                if nodeid not in rerun_cache:
                    rerun_cache[nodeid] = _run_test_now_passes(
                        nodeid, project_dir, test_command
                    )
                if not rerun_cache[nodeid]:
                    all_pass = False
                    break
            if all_pass:
                continue

        blocker_id = quality_blocker_id(deviation)
        event = latest.get(blocker_id)
        malformed_reason = None
        if event is not None:
            try:
                validate_quality_resolution_event(event)
            except Exception as error:
                malformed_reason = str(error)
                event = None
        details.append(
            _quality_detail(
                deviation,
                event,
                malformed_reason=malformed_reason,
            )
        )
    return BlockerRecoveryEvaluation(tuple(details))


def _phase_coverage_deviations(plan_dir: Path | None) -> tuple[Deviation, ...]:
    """Surface latest execution-batch authority failures as quality blockers.

    ``recover-blocked`` previously only inspected ``phase_result.json``. When
    execute ended blocked because the latest execution batch lacked
    corroborated/completed task authority, the blocker lived in the execution
    batch artifact instead, so recovery saw no current blockers and could only
    fail generically. Import the existing chain-level authority check here and
    re-express any failure as a recovery deviation.
    """

    if plan_dir is None:
        return ()

    from arnold_pipelines.megaplan.chain import _latest_execution_batch_all_tasks_done

    try:
        all_done, reason = _latest_execution_batch_all_tasks_done(plan_dir)
    except Exception:
        return ()
    if all_done or not isinstance(reason, str) or not reason:
        return ()
    if "no execution_batch" in reason:
        return ()
    return (Deviation(kind="phase_coverage", task_id=None, message=reason),)


def _is_pending_authority_coverage_deviation(deviation: Deviation | dict[str, Any] | str) -> bool:
    coerced = _coerce_deviation(deviation)
    if coerced is None:
        return False
    return coerced.message.startswith(
        "finalize.json has pending tasks without authoritative execution updates:"
    )


def evaluate_blocker_recovery(
    finalize_data: dict[str, Any],
    state: dict[str, Any],
    *,
    plan_dir: Path | None = None,
    blocked_tasks: Iterable[BlockedTask | dict[str, Any]] = (),
    deviations: Iterable[Deviation | dict[str, Any] | str] = (),
) -> BlockerRecoveryEvaluation:
    prereq = evaluate_prerequisite_blockers(
        finalize_data,
        state,
        blocked_tasks,
        plan_dir=plan_dir,
    )
    all_deviations = tuple(deviations) + _phase_coverage_deviations(plan_dir)
    if prereq.requires_rerun:
        all_deviations = tuple(
            deviation
            for deviation in all_deviations
            if not _is_pending_authority_coverage_deviation(deviation)
        )
    quality = evaluate_quality_blockers(
        state,
        all_deviations,
    )
    return BlockerRecoveryEvaluation(prereq.blockers + quality.blockers)


def command_blocker_details(
    evaluation: BlockerRecoveryEvaluation,
) -> list[dict[str, Any]]:
    return [blocker.to_dict() for blocker in evaluation.blockers]


def _coerce_blocked_task(value: BlockedTask | dict[str, Any]) -> BlockedTask | None:
    if isinstance(value, BlockedTask):
        return value
    if not isinstance(value, dict):
        return None
    try:
        return BlockedTask.from_dict(value)
    except Exception:
        return None


def _coerce_deviation(value: Deviation | dict[str, Any] | str) -> Deviation | None:
    if isinstance(value, Deviation):
        return value
    if isinstance(value, str):
        return Deviation.from_string(value)
    if not isinstance(value, dict):
        return None
    try:
        return Deviation.from_dict(value)
    except Exception:
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def _is_harness_generated_blocked_task(blocked: BlockedTask) -> bool:
    if blocked.reason != "blocked_by_prereq":
        return False
    return "[harness]" in blocked.notes
