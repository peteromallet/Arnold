"""Single production seam for task test-budget admission and elapsed deadlines.

T5.1 / SD-007: new plans use ``elapsed_wall_clock_v2``. Legacy tasks that
declare ``max_seconds`` without ``budget_semantics`` stay
``declared_timeout_sum_v1``. The loader never rewrites stored artifacts.

This module is the only arithmetic owner. Feasibility, prompts, splitter,
and validation-job compilers describe remaining budget; they do not keep a
second remaining-time formula.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol, TypeGuard

BUDGET_SEMANTICS_V2 = "elapsed_wall_clock_v2"
CLASSIFICATION_V1 = "declared_timeout_sum_v1"
CLASSIFICATION_V2 = "elapsed_wall_clock_v2"
CLASSIFICATION_UNDECLARED = "undeclared"
STATE_FIELD_V2 = "test_budget_state_v2"
STATE_FIELD_V1 = "test_budget_state_v1"

_TIMEOUT_PREFIX = re.compile(
    r"(?:^|[\s(])timeout\s+(?:(?:--[^\s]+)\s+)*(?P<value>\d+)(?P<unit>[sm]?)\s+"
)

_DEFAULT_COMMAND_TIMEOUT_SECONDS = 120.0


class Clock(Protocol):
    def monotonic(self) -> float: ...

    def utcnow(self) -> datetime: ...


@dataclass(frozen=True, slots=True)
class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def utcnow(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class BudgetClassification:
    semantics: str
    visible: str
    allowed_seconds: float | None
    max_runs: int | None
    mixes_state_fields: bool
    message: str


@dataclass(frozen=True, slots=True)
class ActiveRun:
    run_id: str
    command_digest: str
    started_at_utc: str
    remaining_budget_at_launch: float


@dataclass(frozen=True, slots=True)
class BudgetState:
    allowed_seconds: float
    consumed_seconds: float
    run_count: int
    active_run: ActiveRun | None
    updated_at_utc: str

    def remaining_seconds(self) -> float:
        remaining = self.allowed_seconds - self.consumed_seconds
        return remaining if remaining > 0.0 else 0.0

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "allowed_seconds": self.allowed_seconds,
            "consumed_seconds": self.consumed_seconds,
            "run_count": self.run_count,
            "active_run": None,
            "updated_at_utc": self.updated_at_utc,
        }
        if self.active_run is not None:
            payload["active_run"] = {
                "run_id": self.active_run.run_id,
                "command_digest": self.active_run.command_digest,
                "started_at_utc": self.active_run.started_at_utc,
                "remaining_budget_at_launch": self.active_run.remaining_budget_at_launch,
            }
        return payload


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    admitted: bool
    remaining_seconds: float
    subprocess_timeout_seconds: float
    run_count: int
    reason: str | None
    kind: str | None
    classification: BudgetClassification
    state: BudgetState | None


def _is_int(value: Any) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _mixes_budget_state_fields(holder: Mapping[str, Any]) -> bool:
    return bool(STATE_FIELD_V1 in holder and STATE_FIELD_V2 in holder)


def classify_narrow_tests(narrow: Mapping[str, Any] | None) -> BudgetClassification:
    """Visible compatibility classification. Never mixes v1/v2 state fields."""

    if not isinstance(narrow, Mapping):
        return BudgetClassification(
            semantics=CLASSIFICATION_UNDECLARED,
            visible=CLASSIFICATION_UNDECLARED,
            allowed_seconds=None,
            max_runs=None,
            mixes_state_fields=False,
            message="Task has no narrow_tests mapping.",
        )

    semantics = narrow.get("budget_semantics")
    max_seconds = narrow.get("max_seconds")
    test_budget_seconds = narrow.get("test_budget_seconds")
    max_runs = narrow.get("max_runs") if _is_int(narrow.get("max_runs")) else None
    mixes = _mixes_budget_state_fields(narrow)

    if semantics == BUDGET_SEMANTICS_V2:
        allowed: float | None = None
        if _is_number(test_budget_seconds):
            budget = float(test_budget_seconds)
            if budget > 0.0:
                allowed = budget
        return BudgetClassification(
            semantics=CLASSIFICATION_V2,
            visible=CLASSIFICATION_V2,
            allowed_seconds=allowed,
            max_runs=max_runs,
            mixes_state_fields=mixes,
            message=(
                "elapsed_wall_clock_v2: remaining task budget is actual elapsed "
                "wall-clock time; subprocess timeout is min(command_timeout, remaining)."
            ),
        )

    if semantics in (None, "") and _is_number(max_seconds):
        v1_allowed = float(max_seconds)
        return BudgetClassification(
            semantics=CLASSIFICATION_V1,
            visible=CLASSIFICATION_V1,
            allowed_seconds=v1_allowed,
            max_runs=max_runs,
            mixes_state_fields=mixes,
            message=(
                "declared_timeout_sum_v1: loader does not rewrite this artifact; "
                "declared timeout wrappers still sum against max_seconds."
            ),
        )

    return BudgetClassification(
        semantics=CLASSIFICATION_UNDECLARED,
        visible=CLASSIFICATION_UNDECLARED,
        allowed_seconds=None,
        max_runs=max_runs,
        mixes_state_fields=mixes,
        message="narrow_tests is present but has no recognized budget semantics.",
    )


def classify_task_budget(task: Mapping[str, Any] | None) -> BudgetClassification:
    """Classify a persisted task, including top-level v2 state next to nested v1."""

    if not isinstance(task, Mapping):
        return classify_narrow_tests(None)
    raw_narrow = task.get("narrow_tests")
    holder: dict[str, Any] = dict(raw_narrow) if isinstance(raw_narrow, Mapping) else {}
    if STATE_FIELD_V1 in task and STATE_FIELD_V1 not in holder:
        holder[STATE_FIELD_V1] = task[STATE_FIELD_V1]
    if STATE_FIELD_V2 in task and STATE_FIELD_V2 not in holder:
        holder[STATE_FIELD_V2] = task[STATE_FIELD_V2]
    if "budget_semantics" not in holder and task.get("budget_semantics") is not None:
        holder["budget_semantics"] = task.get("budget_semantics")
    if "test_budget_seconds" not in holder and task.get("test_budget_seconds") is not None:
        holder["test_budget_seconds"] = task.get("test_budget_seconds")
    if "max_seconds" not in holder and task.get("max_seconds") is not None:
        holder["max_seconds"] = task.get("max_seconds")
    if "max_runs" not in holder and task.get("max_runs") is not None:
        holder["max_runs"] = task.get("max_runs")
    return classify_narrow_tests(holder)


def command_digest(command: str) -> str:
    return hashlib.sha256(command.encode("utf-8")).hexdigest()


def parse_declared_timeout_seconds(command: str) -> float | None:
    match = _TIMEOUT_PREFIX.search(command)
    if match is None:
        return None
    value = float(int(match.group("value")))
    if match.group("unit") == "m":
        value *= 60.0
    return value


def subprocess_timeout_seconds(
    command_timeout: float | None,
    remaining_budget: float,
) -> float:
    """The one subprocess-timeout formula: min(command_timeout, remaining)."""

    remaining = remaining_budget if remaining_budget > 0.0 else 0.0
    if command_timeout is None:
        return remaining
    if command_timeout <= 0.0:
        return 0.0
    return min(float(command_timeout), remaining)


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _active_run_from_mapping(raw: Any) -> ActiveRun | None:
    if not isinstance(raw, Mapping):
        return None
    run_id = raw.get("run_id")
    digest = raw.get("command_digest")
    started = raw.get("started_at_utc")
    remaining = raw.get("remaining_budget_at_launch")
    if not isinstance(run_id, str) or not run_id:
        return None
    if not isinstance(digest, str) or not digest:
        return None
    if not isinstance(started, str) or not started:
        return None
    if not _is_number(remaining):
        return None
    remaining_at_launch = float(remaining)
    return ActiveRun(
        run_id=run_id,
        command_digest=digest,
        started_at_utc=started,
        remaining_budget_at_launch=remaining_at_launch,
    )


def load_budget_state(
    task: Mapping[str, Any],
    *,
    classification: BudgetClassification | None = None,
    clock: Clock | None = None,
) -> BudgetState | None:
    """Load persisted v2 state. Interrupted active_run is charged conservatively."""

    clock = clock or SystemClock()
    classification = classification or classify_task_budget(task)
    if classification.semantics != CLASSIFICATION_V2:
        return None
    if classification.mixes_state_fields:
        return None
    if classification.allowed_seconds is None:
        return None

    raw_state = task.get(STATE_FIELD_V2)
    if not isinstance(raw_state, Mapping):
        narrow = task.get("narrow_tests")
        if isinstance(narrow, Mapping):
            raw_state = narrow.get(STATE_FIELD_V2)
    if not isinstance(raw_state, Mapping):
        now = _format_utc(clock.utcnow())
        return BudgetState(
            allowed_seconds=float(classification.allowed_seconds),
            consumed_seconds=0.0,
            run_count=0,
            active_run=None,
            updated_at_utc=now,
        )

    allowed = raw_state.get("allowed_seconds", classification.allowed_seconds)
    consumed = raw_state.get("consumed_seconds", 0.0)
    run_count = raw_state.get("run_count", 0)
    updated = raw_state.get("updated_at_utc")
    if not _is_number(allowed) or float(allowed) <= 0.0:
        allowed = classification.allowed_seconds
    if not _is_number(consumed) or float(consumed) < 0.0:
        consumed = 0.0
    if not _is_int(run_count) or run_count < 0:
        run_count = 0
    if not isinstance(updated, str) or not updated:
        updated = _format_utc(clock.utcnow())

    state = BudgetState(
        allowed_seconds=float(allowed),
        consumed_seconds=float(consumed),
        run_count=int(run_count),
        active_run=_active_run_from_mapping(raw_state.get("active_run")),
        updated_at_utc=updated,
    )
    if state.active_run is None:
        return state
    return settle_interrupted_active_run(state, clock=clock)


def settle_interrupted_active_run(
    state: BudgetState,
    *,
    clock: Clock,
    now_utc: datetime | None = None,
) -> BudgetState:
    """Charge an interrupted active_run from UTC wall-clock, fail closed."""

    active = state.active_run
    if active is None:
        return state
    now = now_utc or clock.utcnow()
    started = _parse_utc(active.started_at_utc)
    remaining_at_launch = active.remaining_budget_at_launch
    if remaining_at_launch < 0.0:
        remaining_at_launch = 0.0
    if started is None or now < started:
        charged = remaining_at_launch
    else:
        interval = (now - started).total_seconds()
        if interval < 0.0:
            charged = remaining_at_launch
        else:
            charged = min(interval, remaining_at_launch)
    consumed = state.consumed_seconds + charged
    if consumed > state.allowed_seconds:
        consumed = state.allowed_seconds
    return BudgetState(
        allowed_seconds=state.allowed_seconds,
        consumed_seconds=consumed,
        run_count=state.run_count + 1,
        active_run=None,
        updated_at_utc=_format_utc(now),
    )


def persist_budget_state(task: dict[str, Any], state: BudgetState) -> None:
    """Write v2 state onto the task. Never persist a raw monotonic timestamp."""

    payload = state.as_dict()
    encoded = json.dumps(payload)
    if "monotonic" in encoded:
        raise ValueError("raw monotonic timestamps must never be persisted")
    task[STATE_FIELD_V2] = payload
    task.pop(STATE_FIELD_V1, None)
    narrow = task.get("narrow_tests")
    if isinstance(narrow, dict):
        narrow.pop(STATE_FIELD_V1, None)


def remaining_task_budget(state: BudgetState) -> float:
    return state.remaining_seconds()


def begin_run(
    state: BudgetState,
    *,
    command: str,
    run_id: str,
    clock: Clock,
    command_timeout: float | None = None,
) -> tuple[AdmissionDecision, BudgetState]:
    """Admit or refuse the next subprocess at the single enforcement seam."""

    classification = BudgetClassification(
        semantics=CLASSIFICATION_V2,
        visible=CLASSIFICATION_V2,
        allowed_seconds=state.allowed_seconds,
        max_runs=None,
        mixes_state_fields=False,
        message="elapsed_wall_clock_v2",
    )
    remaining = state.remaining_seconds()
    if remaining <= 0.0:
        decision = AdmissionDecision(
            admitted=False,
            remaining_seconds=0.0,
            subprocess_timeout_seconds=0.0,
            run_count=state.run_count,
            reason="no positive elapsed budget remains",
            kind="elapsed_budget_exhausted",
            classification=classification,
            state=state,
        )
        return decision, state

    timeout = subprocess_timeout_seconds(
        command_timeout if command_timeout is not None else parse_declared_timeout_seconds(command),
        remaining,
    )
    if timeout <= 0.0:
        decision = AdmissionDecision(
            admitted=False,
            remaining_seconds=remaining,
            subprocess_timeout_seconds=0.0,
            run_count=state.run_count,
            reason="subprocess timeout is not positive",
            kind="elapsed_budget_exhausted",
            classification=classification,
            state=state,
        )
        return decision, state

    now = clock.utcnow()
    next_state = BudgetState(
        allowed_seconds=state.allowed_seconds,
        consumed_seconds=state.consumed_seconds,
        run_count=state.run_count,
        active_run=ActiveRun(
            run_id=run_id,
            command_digest=command_digest(command),
            started_at_utc=_format_utc(now),
            remaining_budget_at_launch=remaining,
        ),
        updated_at_utc=_format_utc(now),
    )
    decision = AdmissionDecision(
        admitted=True,
        remaining_seconds=remaining,
        subprocess_timeout_seconds=timeout,
        run_count=next_state.run_count,
        reason=None,
        kind=None,
        classification=classification,
        state=next_state,
    )
    return decision, next_state


def complete_run(
    state: BudgetState,
    *,
    monotonic_duration_seconds: float,
    clock: Clock,
) -> BudgetState:
    """Ordinary completion: add the in-process monotonic duration."""

    duration = monotonic_duration_seconds if monotonic_duration_seconds > 0.0 else 0.0
    remaining_cap = (
        state.active_run.remaining_budget_at_launch
        if state.active_run is not None
        else state.remaining_seconds()
    )
    if remaining_cap < 0.0:
        remaining_cap = 0.0
    charged = min(duration, remaining_cap)
    consumed = state.consumed_seconds + charged
    if consumed > state.allowed_seconds:
        consumed = state.allowed_seconds
    return BudgetState(
        allowed_seconds=state.allowed_seconds,
        consumed_seconds=consumed,
        run_count=state.run_count + 1,
        active_run=None,
        updated_at_utc=_format_utc(clock.utcnow()),
    )


def enforce_max_runs(run_count: int, max_runs: int | None) -> str | None:
    if max_runs is None or not _is_int(max_runs):
        return None
    if run_count > max_runs:
        return f"{run_count} test runs exceeds max_runs={max_runs}"
    return None


def v2_admission_for_command(
    task: Mapping[str, Any],
    command: str,
    *,
    run_id: str,
    clock: Clock | None = None,
    command_timeout: float | None = None,
) -> tuple[AdmissionDecision, BudgetState | None]:
    clock = clock or SystemClock()
    classification = classify_task_budget(task)
    if classification.semantics != CLASSIFICATION_V2:
        return (
            AdmissionDecision(
                admitted=False,
                remaining_seconds=0.0,
                subprocess_timeout_seconds=0.0,
                run_count=0,
                reason="not an elapsed_wall_clock_v2 task",
                kind="incompatible_budget_semantics",
                classification=classification,
                state=None,
            ),
            None,
        )
    if classification.mixes_state_fields:
        return (
            AdmissionDecision(
                admitted=False,
                remaining_seconds=0.0,
                subprocess_timeout_seconds=0.0,
                run_count=0,
                reason="v1 and v2 budget state fields must not be mixed",
                kind="mixed_budget_state",
                classification=classification,
                state=None,
            ),
            None,
        )
    state = load_budget_state(task, classification=classification, clock=clock)
    if state is None:
        return (
            AdmissionDecision(
                admitted=False,
                remaining_seconds=0.0,
                subprocess_timeout_seconds=0.0,
                run_count=0,
                reason="v2 budget state could not be loaded",
                kind="elapsed_budget_exhausted",
                classification=classification,
                state=None,
            ),
            None,
        )
    max_runs = classification.max_runs
    if max_runs is not None and state.run_count >= max_runs:
        decision = AdmissionDecision(
            admitted=False,
            remaining_seconds=state.remaining_seconds(),
            subprocess_timeout_seconds=0.0,
            run_count=state.run_count,
            reason=f"{state.run_count + 1} test runs would exceed max_runs={max_runs}",
            kind="max_runs_exceeded",
            classification=classification,
            state=state,
        )
        return decision, state
    return begin_run(
        state,
        command=command,
        run_id=run_id,
        clock=clock,
        command_timeout=command_timeout,
    )


def describe_budget_for_prompts(classification: BudgetClassification) -> str:
    if classification.semantics == CLASSIFICATION_V2:
        return (
            "This task uses elapsed_wall_clock_v2. The harness enforces one "
            "positive test_budget_seconds deadline as actual elapsed wall-clock "
            "time. Subprocess timeout is min(command_timeout, remaining_budget). "
            "Admission stops when no positive budget remains, irrespective of "
            "the sum of declared command timeouts. max_runs is enforced at the "
            "same root seam."
        )
    if classification.semantics == CLASSIFICATION_V1:
        return (
            "This stored task is classified declared_timeout_sum_v1. The loader "
            "does not rewrite it. Declared timeout wrappers still sum against "
            "max_seconds."
        )
    return "This task has no recognized test-budget semantics."


def describe_budget_for_feasibility(classification: BudgetClassification) -> dict[str, Any]:
    return {
        "budget_classification": classification.visible,
        "budget_semantics": classification.semantics,
        "allowed_seconds": classification.allowed_seconds,
        "max_runs": classification.max_runs,
        "mixes_state_fields": classification.mixes_state_fields,
        "enforcement_seam": "arnold_pipelines.megaplan.execute.test_budget",
        "message": classification.message,
    }


def describe_budget_for_splitter(classification: BudgetClassification) -> str:
    if classification.semantics == CLASSIFICATION_V2:
        return (
            "Proof budget is elapsed_wall_clock_v2 test_budget_seconds; the "
            "execute seam charges actual elapsed time and remaining subprocess "
            "timeout. Splitter does not recompute remaining time."
        )
    if classification.semantics == CLASSIFICATION_V1:
        return (
            "Proof budget is declared_timeout_sum_v1 max_seconds; the execute "
            "seam retains documented timeout-sum behavior. Splitter does not "
            "recompute remaining time."
        )
    return "No recognized test budget; cannot form a proof subtask."


def default_command_timeout(command: str) -> float:
    parsed = parse_declared_timeout_seconds(command)
    if parsed is None:
        return _DEFAULT_COMMAND_TIMEOUT_SECONDS
    return parsed


def capped_subprocess_timeout(
    task: Mapping[str, Any],
    command_timeout: float | None,
    *,
    clock: Clock | None = None,
) -> float:
    """Describe remaining subprocess timeout without a second arithmetic owner."""

    clock = clock or SystemClock()
    classification = classify_task_budget(task)
    if classification.semantics != CLASSIFICATION_V2:
        if command_timeout is None:
            return 0.0
        return float(command_timeout) if command_timeout > 0.0 else 0.0
    state = load_budget_state(task, classification=classification, clock=clock)
    remaining = state.remaining_seconds() if state is not None else 0.0
    return subprocess_timeout_seconds(command_timeout, remaining)


def durations_from_commands_run(commands: list[str]) -> list[float]:
    """Derive charged durations from recorded commands when the worker omitted them.

    Production execution.json historically records command strings, not durations.
    A declared ``timeout <N>`` is a conservative elapsed charge for each
    pytest invocation so a v2 task cannot complete with consumed_seconds=0.0.
    """

    durations: list[float] = []
    for command in commands:
        if not isinstance(command, str):
            continue
        parsed = parse_declared_timeout_seconds(command)
        if parsed is None:
            durations.append(_DEFAULT_COMMAND_TIMEOUT_SECONDS)
        else:
            durations.append(float(parsed))
    return durations


def charge_elapsed_commands(
    task: Mapping[str, Any],
    *,
    commands: list[str],
    durations: list[float] | None = None,
    clock: Clock | None = None,
) -> tuple[BudgetState | None, list[float]]:
    """Charge recorded pytest invocations at the single elapsed seam.

    ``durations`` is the production worker's recorded elapsed list when present.
    Otherwise durations are derived from ``commands_run``. Each duration is
    charged through ``complete_run`` so run_count has one source.
    """

    clock = clock or SystemClock()
    classification = classify_task_budget(task)
    state = load_budget_state(task, classification=classification, clock=clock)
    if state is None:
        return None, []
    charged_durations = list(durations) if durations else durations_from_commands_run(commands)
    charged = state
    for raw in charged_durations:
        if not isinstance(raw, (int, float)) or isinstance(raw, bool) or raw < 0:
            duration = charged.remaining_seconds()
        else:
            duration = float(raw)
        charged = complete_run(
            charged,
            monotonic_duration_seconds=duration,
            clock=clock,
        )
    return charged, charged_durations


def default_elapsed_runner(command: str) -> Callable[[float], float]:
    """Production runner: launch ``command`` under remaining-budget timeout."""

    def _run(timeout_seconds: float) -> float:
        started = time.monotonic()
        if timeout_seconds <= 0.0:
            return 0.0
        try:
            subprocess.run(
                command,
                shell=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            pass
        return time.monotonic() - started

    return _run


def run_elapsed_command(
    task: dict[str, Any],
    command: str,
    *,
    run_id: str,
    clock: Clock | None = None,
    command_timeout: float | None = None,
    runner: Callable[[float], float] | None = None,
) -> AdmissionDecision:
    """Admit, run, and charge one command at the single elapsed-budget seam.

    ``runner(timeout_seconds)`` returns the monotonic duration of the
    subprocess. Tests inject a fake runner; production uses
    :func:`default_elapsed_runner` so the subprocess timeout is
    ``min(command_timeout, remaining_budget)``. A raw monotonic timestamp
    is never persisted.
    """
    clock = clock or SystemClock()
    timeout_arg = (
        command_timeout
        if command_timeout is not None
        else parse_declared_timeout_seconds(command)
    )
    decision, state = v2_admission_for_command(
        task,
        command,
        run_id=run_id,
        clock=clock,
        command_timeout=timeout_arg,
    )
    if not decision.admitted or state is None:
        if state is not None:
            persist_budget_state(task, state)
        return decision
    persist_budget_state(task, state)
    active_runner = runner if runner is not None else default_elapsed_runner(command)
    duration = float(active_runner(decision.subprocess_timeout_seconds))
    completed = complete_run(state, monotonic_duration_seconds=duration, clock=clock)
    persist_budget_state(task, completed)
    remaining = completed.remaining_seconds()
    return AdmissionDecision(
        admitted=remaining > 0.0,
        remaining_seconds=remaining,
        subprocess_timeout_seconds=decision.subprocess_timeout_seconds,
        run_count=completed.run_count,
        reason=None if remaining > 0.0 else "no positive elapsed budget remains",
        kind=None if remaining > 0.0 else "elapsed_budget_exhausted",
        classification=decision.classification,
        state=completed,
    )


__all__ = [
    "BUDGET_SEMANTICS_V2",
    "CLASSIFICATION_UNDECLARED",
    "CLASSIFICATION_V1",
    "CLASSIFICATION_V2",
    "STATE_FIELD_V1",
    "STATE_FIELD_V2",
    "ActiveRun",
    "AdmissionDecision",
    "BudgetClassification",
    "BudgetState",
    "Clock",
    "SystemClock",
    "begin_run",
    "charge_elapsed_commands",
    "classify_narrow_tests",
    "classify_task_budget",
    "command_digest",
    "complete_run",
    "default_command_timeout",
    "default_elapsed_runner",
    "describe_budget_for_feasibility",
    "describe_budget_for_prompts",
    "describe_budget_for_splitter",
    "durations_from_commands_run",
    "enforce_max_runs",
    "load_budget_state",
    "parse_declared_timeout_seconds",
    "persist_budget_state",
    "remaining_task_budget",
    "settle_interrupted_active_run",
    "subprocess_timeout_seconds",
    "capped_subprocess_timeout",
    "run_elapsed_command",
    "v2_admission_for_command",
]
