"""Deterministic, read-only Megaplan authority shadow views."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Iterable, Mapping

from arnold_pipelines.megaplan._core.scheduler.topo import schedule_batches
from arnold_pipelines.run_authority import ObservationEnvelope, RunAuthorityView, canonical_json

from .binding import TASK_COMPLETION_CLAIM


_LEGACY_TERMINAL = frozenset({"done", "completed", "skipped", "waived", "not_applicable"})


@dataclass(frozen=True, order=True)
class LegacyTaskLabel:
    """A compatibility label that is visible but never grants authority."""

    task_id: str
    label: str
    source: str
    role: str = "projection"

    def __post_init__(self) -> None:
        if self.role not in {"observation", "projection"}:
            raise ValueError("legacy labels must remain observations or projections")
        if not self.task_id or not self.label or not self.source:
            raise ValueError("legacy label identity, value, and source are required")

    def to_dict(self) -> dict[str, str]:
        return {
            "task_id": self.task_id,
            "label": self.label,
            "source": self.source,
            "role": self.role,
        }


@dataclass(frozen=True, order=True)
class PlanExecutionDiagnostic:
    code: str
    subject_id: str
    reason: str
    source: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "subject_id": self.subject_id,
            "reason": self.reason,
            "source": self.source,
        }


@dataclass(frozen=True, order=True)
class RunnerObservation:
    """A normalized, non-authoritative fact about a runner process."""

    observation_id: str
    observation_type: str
    source: str
    state: str
    identity: str | None = None
    expected_identity: str | None = None
    heartbeat_age_seconds: int | None = None
    stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "observation_type": self.observation_type,
            "source": self.source,
            "state": self.state,
            "identity": self.identity,
            "expected_identity": self.expected_identity,
            "heartbeat_age_seconds": self.heartbeat_age_seconds,
            "stale": self.stale,
        }


@dataclass(frozen=True, order=True)
class RunnerDiagnostic:
    """A source-addressable runner-liveness diagnostic."""

    code: str
    reason: str
    source: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "reason": self.reason, "source": self.source}


@dataclass(frozen=True)
class RunnerView:
    """Read-only operational liveness projection, separate from task authority."""

    schema_version: int
    status: str
    expected_identity: str | None
    observations: tuple[RunnerObservation, ...]
    source_paths: tuple[str, ...]
    diagnostics: tuple[RunnerDiagnostic, ...]
    view_hash: str

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "expected_identity": self.expected_identity,
            "observations": [item.to_dict() for item in self.observations],
            "source_paths": list(self.source_paths),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "shadow": True,
            "read_only": True,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "view_hash": self.view_hash}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


_PUBLICATION_FIELDS = (
    "branch",
    "branch_ancestry",
    "dirty_workspace",
    "pushed_sha",
    "pull_request",
    "auth",
    "no_push",
)


@dataclass(frozen=True, order=True)
class PublicationObservation:
    """One source-addressable publication fact, or an explicit unknown.

    Publication is deliberately represented as six independent observations.
    This prevents a convenient aggregate such as a PR URL from silently
    implying that a workspace was clean, a SHA was pushed, or credentials were
    usable.
    """

    field: str
    state: str
    value: str | bool | None
    source: str

    def __post_init__(self) -> None:
        if self.field not in _PUBLICATION_FIELDS:
            raise ValueError(f"unsupported publication field: {self.field!r}")
        if self.state not in {"known", "unknown", "contradicted"}:
            raise ValueError("publication observation state must be known, unknown, or contradicted")
        if not self.source:
            raise ValueError("publication observation source is required")
        if self.state != "known" and self.value is not None:
            raise ValueError("unknown or contradicted publication observations cannot have a value")
        if self.field in {"dirty_workspace", "auth", "no_push"} and self.value is not None and not isinstance(self.value, bool):
            raise ValueError(f"publication field {self.field!r} must be boolean when known")
        if self.field in {"branch", "pushed_sha", "pull_request"} and self.value is not None and not isinstance(self.value, str):
            raise ValueError(f"publication field {self.field!r} must be a string when known")

    def to_dict(self) -> dict[str, str | bool | None]:
        return {
            "field": self.field,
            "state": self.state,
            "value": self.value,
            "source": self.source,
        }


@dataclass(frozen=True, order=True)
class PublicationDiagnostic:
    """A non-authoritative reason why publication is blocked or uncertain."""

    code: str
    field: str
    reason: str
    source: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "field": self.field,
            "reason": self.reason,
            "source": self.source,
        }


@dataclass(frozen=True)
class PublicationView:
    """Read-only branch/workspace/push/PR diagnostic, separate from execution."""

    schema_version: int
    status: str
    observations: tuple[PublicationObservation, ...]
    source_paths: tuple[str, ...]
    diagnostics: tuple[PublicationDiagnostic, ...]
    view_hash: str

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "observations": [item.to_dict() for item in self.observations],
            "source_paths": list(self.source_paths),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "shadow": True,
            "read_only": True,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "view_hash": self.view_hash}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


@dataclass(frozen=True)
class AcceptedTaskAttempt:
    task_id: str
    attempt_id: str
    claim_id: str
    decision_id: str
    grant_id: str
    evidence_ids: tuple[str, ...]
    source_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "attempt_id": self.attempt_id,
            "claim_id": self.claim_id,
            "decision_id": self.decision_id,
            "grant_id": self.grant_id,
            "evidence_ids": list(self.evidence_ids),
            "source_paths": list(self.source_paths),
        }


@dataclass(frozen=True)
class TaskExecutionState:
    task_id: str
    depends_on: tuple[str, ...]
    accepted: bool
    dependency_closed: bool
    authority_status: str
    accepted_attempt_ids: tuple[str, ...]
    accepted_decision_ids: tuple[str, ...]
    unresolved_claim_ids: tuple[str, ...]
    unresolved_dependency_ids: tuple[str, ...]
    legacy_labels: tuple[LegacyTaskLabel, ...]
    source_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "depends_on": list(self.depends_on),
            "accepted": self.accepted,
            "dependency_closed": self.dependency_closed,
            "authority_status": self.authority_status,
            "accepted_attempt_ids": list(self.accepted_attempt_ids),
            "accepted_decision_ids": list(self.accepted_decision_ids),
            "unresolved_claim_ids": list(self.unresolved_claim_ids),
            "unresolved_dependency_ids": list(self.unresolved_dependency_ids),
            "legacy_labels": [item.to_dict() for item in self.legacy_labels],
            "source_paths": list(self.source_paths),
        }


@dataclass(frozen=True)
class PlanExecutionView:
    """Megaplan task projection; never used as a mutation authority in Sprint 1."""

    schema_version: int
    run_id: str
    run_revision: str
    authority_view_hash: str
    tasks: tuple[TaskExecutionState, ...]
    accepted_task_ids: tuple[str, ...]
    accepted_task_attempts: tuple[AcceptedTaskAttempt, ...]
    dependency_closed_completed_task_ids: tuple[str, ...]
    next_ready_wave: tuple[str, ...]
    unresolved_claim_ids: tuple[str, ...]
    quarantine_ids: tuple[str, ...]
    diagnostics: tuple[PlanExecutionDiagnostic, ...]
    view_hash: str

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "run_revision": self.run_revision,
            "authority_view_hash": self.authority_view_hash,
            "tasks": [item.to_dict() for item in self.tasks],
            "accepted_task_ids": list(self.accepted_task_ids),
            "accepted_task_attempts": [item.to_dict() for item in self.accepted_task_attempts],
            "dependency_closed_completed_task_ids": list(self.dependency_closed_completed_task_ids),
            "next_ready_wave": list(self.next_ready_wave),
            "unresolved_claim_ids": list(self.unresolved_claim_ids),
            "quarantine_ids": list(self.quarantine_ids),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "shadow": True,
            "read_only": True,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "view_hash": self.view_hash}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


def _task_records(plan: Mapping[str, Any] | Iterable[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    if isinstance(plan, Mapping):
        records = plan.get("tasks", ())
    else:
        records = plan
    result = tuple(records)
    if any(not isinstance(item, Mapping) for item in result):
        raise ValueError("plan tasks must be mappings")
    return result


_LIVE_RUNNER_STATES = frozenset({"live", "alive", "running", "connected"})
_STOPPED_RUNNER_STATES = frozenset({"stopped", "dead", "exited", "missing"})


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _observation_value(payload: Mapping[str, Any], observation: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
        if name in observation:
            return observation[name]
    return None


def _publication_raw_observation(
    observation: ObservationEnvelope | Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    if isinstance(observation, ObservationEnvelope):
        return (
            {
                "observation_id": observation.observation_id,
                "observation_type": observation.observation_type,
                "source": observation.source,
            },
            observation.payload,
        )
    if isinstance(observation, Mapping):
        payload = observation.get("payload")
        return observation, payload if isinstance(payload, Mapping) else observation
    raise ValueError("publication observations must be ObservationEnvelope records or mappings")


def _publication_string(value: Any) -> str | None:
    return _optional_string(value)


def _publication_boolean(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _publication_observation_values(
    observation: ObservationEnvelope | Mapping[str, Any],
) -> tuple[str, dict[str, str | bool]]:
    """Extract explicit publication facts from one generic observation.

    Mapping aliases match existing Git and cloud collector conventions but are
    only observations.  A type/value adapter lets a collector emit one field at
    a time without fabricating the rest.
    """

    raw, payload = _publication_raw_observation(observation)
    source = _optional_string(raw.get("source")) or "observation://unknown"
    values: dict[str, str | bool] = {}
    string_aliases = {
        "branch": ("branch", "branch_name", "current_branch"),
        "branch_ancestry": ("branch_ancestry", "ancestry", "ancestry_status"),
        "pushed_sha": ("pushed_sha", "pushed_commit", "remote_sha", "published_sha"),
        "pull_request": ("pull_request", "pr_url", "pr", "pr_number"),
    }
    boolean_aliases = {
        "dirty_workspace": ("dirty_workspace", "workspace_dirty", "dirty", "is_dirty"),
        "auth": ("auth", "authenticated", "auth_available", "credentials_available"),
        "no_push": ("no_push", "push_disabled"),
    }
    for field, aliases in string_aliases.items():
        value = _publication_string(_observation_value(payload, raw, *aliases))
        if value is not None:
            values[field] = value
    for field, aliases in boolean_aliases.items():
        value = _publication_boolean(_observation_value(payload, raw, *aliases))
        if value is not None:
            values[field] = value

    observation_type = (_optional_string(raw.get("observation_type") or raw.get("type")) or "").lower()
    typed_fields = {
        "branch": "branch",
        "git_branch": "branch",
        "branch_ancestry": "branch_ancestry",
        "ancestry": "branch_ancestry",
        "workspace": "dirty_workspace",
        "dirty_workspace": "dirty_workspace",
        "push": "pushed_sha",
        "pushed_sha": "pushed_sha",
        "pull_request": "pull_request",
        "pr": "pull_request",
        "auth": "auth",
        "publication_auth": "auth",
        "no_push": "no_push",
    }
    typed_field = typed_fields.get(observation_type)
    if typed_field and typed_field not in values:
        typed_value = _observation_value(payload, raw, "value")
        normalizer = _publication_boolean if typed_field in boolean_aliases else _publication_string
        normalized = normalizer(typed_value)
        if normalized is not None:
            values[typed_field] = normalized
    return source, values


def derive_publication_view(
    observations: Iterable[ObservationEnvelope | Mapping[str, Any]],
) -> PublicationView:
    """Project publication readiness without performing Git, PR, or auth work.

    Inputs may be incomplete.  Every required field remains visible as a known,
    unknown, or contradicted observation, and the view neither reads execution
    state nor consumes a ``RunnerView``.
    """

    values_by_field: dict[str, set[str | bool]] = {field: set() for field in _PUBLICATION_FIELDS}
    sources_by_field: dict[str, set[str]] = {field: set() for field in _PUBLICATION_FIELDS}
    for item in observations:
        source, values = _publication_observation_values(item)
        for field, value in values.items():
            values_by_field[field].add(value)
            sources_by_field[field].add(source)

    normalized: list[PublicationObservation] = []
    diagnostics: list[PublicationDiagnostic] = []
    for field in _PUBLICATION_FIELDS:
        values = values_by_field[field]
        sources = tuple(sorted(sources_by_field[field]))
        if not values:
            source = f"observation://unknown/{field}"
            normalized.append(PublicationObservation(field, "unknown", None, source))
            diagnostics.append(PublicationDiagnostic(
                "publication_observation_unknown", field,
                f"no observation provides {field.replace('_', ' ')}", source,
            ))
        elif len(values) == 1:
            normalized.append(PublicationObservation(field, "known", next(iter(values)), ",".join(sources)))
        else:
            source = ",".join(sources)
            normalized.append(PublicationObservation(field, "contradicted", None, source))
            diagnostics.append(PublicationDiagnostic(
                "publication_observation_contradiction", field,
                f"conflicting observations for {field.replace('_', ' ')}", source,
            ))

    by_field = {item.field: item for item in normalized}
    if by_field["dirty_workspace"].value is True:
        item = by_field["dirty_workspace"]
        diagnostics.append(PublicationDiagnostic(
            "dirty_workspace", item.field, "workspace is dirty", item.source,
        ))
    if by_field["no_push"].value is True:
        item = by_field["no_push"]
        diagnostics.append(PublicationDiagnostic(
            "no_push_configured", item.field, "publication push is explicitly disabled", item.source,
        ))
    if by_field["auth"].value is False:
        item = by_field["auth"]
        diagnostics.append(PublicationDiagnostic(
            "publication_auth_unavailable", item.field, "publication credentials are unavailable", item.source,
        ))
    if by_field["branch_ancestry"].state == "known" and by_field["branch_ancestry"].value == "invalid":
        item = by_field["branch_ancestry"]
        diagnostics.append(PublicationDiagnostic(
            "invalid_branch_ancestry", item.field,
            "branch has no common history with the target base", item.source,
        ))

    if any(item.state == "contradicted" for item in normalized):
        status = "contradicted"
    elif (
        any(by_field[field].value is True for field in ("dirty_workspace", "no_push"))
        or by_field["auth"].value is False
        or (by_field["branch_ancestry"].state == "known" and by_field["branch_ancestry"].value == "invalid")
    ):
        status = "blocked"
    elif all(by_field[field].state == "known" for field in _PUBLICATION_FIELDS):
        status = "ready"
    else:
        status = "unknown"

    values = {
        "schema_version": 1,
        "status": status,
        "observations": tuple(normalized),
        "source_paths": tuple(sorted({item.source for item in normalized})),
        "diagnostics": tuple(sorted(set(diagnostics))),
    }
    unsigned = PublicationView(**values, view_hash="pending")
    digest = hashlib.sha256(canonical_json(unsigned._payload()).encode("utf-8")).hexdigest()
    return PublicationView(**values, view_hash=digest)


def _normalized_runner_observation(
    observation: ObservationEnvelope | Mapping[str, Any],
) -> RunnerObservation:
    """Reduce supported observation shapes to stable runner facts.

    ``ObservationEnvelope`` is the normal source.  Mapping support keeps the
    view usable by existing read-only status collectors before they are adapted
    to the generic contract; those mappings are normalized, not trusted as
    authority.
    """

    if isinstance(observation, ObservationEnvelope):
        raw: Mapping[str, Any] = {
            "observation_id": observation.observation_id,
            "observation_type": observation.observation_type,
            "source": observation.source,
        }
        payload: Mapping[str, Any] = observation.payload
    elif isinstance(observation, Mapping):
        raw = observation
        candidate = observation.get("payload")
        payload = candidate if isinstance(candidate, Mapping) else observation
    else:
        raise ValueError("runner observations must be ObservationEnvelope records or mappings")

    observation_type = _optional_string(raw.get("observation_type") or raw.get("type")) or "unknown"
    source = _optional_string(raw.get("source")) or "observation://unknown"
    state = _optional_string(_observation_value(payload, raw, "state", "status")) or "unknown"
    identity = _optional_string(
        _observation_value(payload, raw, "identity", "runner_id", "session_id", "session_name")
    )
    expected_identity = _optional_string(
        _observation_value(payload, raw, "expected_identity", "expected_runner_id", "expected_session_id")
    )
    raw_age = _observation_value(payload, raw, "heartbeat_age_seconds", "age_seconds")
    heartbeat_age_seconds = raw_age if isinstance(raw_age, int) and not isinstance(raw_age, bool) and raw_age >= 0 else None
    stale = bool(_observation_value(payload, raw, "stale"))
    if heartbeat_age_seconds is not None and heartbeat_age_seconds < 0:  # defensive for future numeric adapters
        heartbeat_age_seconds = None
    observation_id = _optional_string(raw.get("observation_id") or raw.get("id"))
    if observation_id is None:
        unsigned = {
            "observation_type": observation_type,
            "source": source,
            "state": state,
            "identity": identity,
            "expected_identity": expected_identity,
            "heartbeat_age_seconds": heartbeat_age_seconds,
            "stale": stale,
        }
        observation_id = hashlib.sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()
    return RunnerObservation(
        observation_id=observation_id,
        observation_type=observation_type.lower(),
        source=source,
        state=state.lower(),
        identity=identity,
        expected_identity=expected_identity,
        heartbeat_age_seconds=heartbeat_age_seconds,
        stale=stale,
    )


def derive_runner_view(
    observations: Iterable[ObservationEnvelope | Mapping[str, Any]],
    *,
    expected_identity: str | None = None,
    stale_after_seconds: int = 300,
) -> RunnerView:
    """Project process/session/heartbeat observations without deciding execution.

    ``stale_after_seconds`` is explicit rather than clock-derived, so the same
    normalized observation set always produces the same view and hash.
    """

    if isinstance(stale_after_seconds, bool) or not isinstance(stale_after_seconds, int) or stale_after_seconds < 0:
        raise ValueError("stale_after_seconds must be a non-negative integer")
    normalized = tuple(sorted(
        {_normalized_runner_observation(item) for item in observations},
        key=lambda item: canonical_json(item.to_dict()),
    ))
    configured_identity = _optional_string(expected_identity)
    declared_identities = {item.expected_identity for item in normalized if item.expected_identity}
    if configured_identity:
        declared_identities.add(configured_identity)

    diagnostics: list[RunnerDiagnostic] = []
    if len(declared_identities) > 1:
        diagnostics.append(RunnerDiagnostic(
            "runner_identity_mismatch",
            "runner observations declare conflicting expected identities",
            ",".join(sorted(item.source for item in normalized if item.expected_identity)),
        ))
    expected = configured_identity or (next(iter(declared_identities)) if len(declared_identities) == 1 else None)
    mismatched = tuple(item for item in normalized if expected and item.identity and item.identity != expected)
    for item in mismatched:
        diagnostics.append(RunnerDiagnostic(
            "runner_identity_mismatch",
            f"observed identity {item.identity!r} does not match expected identity {expected!r}",
            item.source,
        ))

    stale_heartbeats = tuple(
        item for item in normalized
        if item.observation_type in {"heartbeat", "runner_heartbeat"}
        and (item.stale or (item.heartbeat_age_seconds is not None and item.heartbeat_age_seconds > stale_after_seconds))
    )
    for item in stale_heartbeats:
        diagnostics.append(RunnerDiagnostic(
            "stale_heartbeat",
            "heartbeat was explicitly stale" if item.stale else (
                f"heartbeat age {item.heartbeat_age_seconds}s exceeds {stale_after_seconds}s threshold"
            ),
            item.source,
        ))

    stopped = tuple(item for item in normalized if item.state in _STOPPED_RUNNER_STATES)
    for item in stopped:
        diagnostics.append(RunnerDiagnostic(
            "runner_stopped", f"runner observation reports {item.state!r}", item.source
        ))

    known_liveness = tuple(item for item in normalized if item.state in _LIVE_RUNNER_STATES | _STOPPED_RUNNER_STATES)
    if not known_liveness and not stale_heartbeats and not mismatched:
        source = ",".join(item.source for item in normalized) or "observation://unknown"
        diagnostics.append(RunnerDiagnostic(
            "runner_unknown", "no observation establishes runner liveness", source
        ))

    if mismatched or len(declared_identities) > 1:
        status = "identity_mismatch"
    elif stopped:
        status = "stopped"
    elif stale_heartbeats:
        status = "stale"
    elif any(item.state in _LIVE_RUNNER_STATES for item in normalized):
        status = "live"
    else:
        status = "unknown"

    values = {
        "schema_version": 1,
        "status": status,
        "expected_identity": expected,
        "observations": normalized,
        "source_paths": tuple(sorted({item.source for item in normalized})),
        "diagnostics": tuple(sorted(set(diagnostics))),
    }
    unsigned = RunnerView(**values, view_hash="pending")
    digest = hashlib.sha256(canonical_json(unsigned._payload()).encode("utf-8")).hexdigest()
    return RunnerView(**values, view_hash=digest)


def _decision_authoritative(decision: Any) -> bool:
    """Use the existing evidence reader's decision contract without owning it."""

    return bool(getattr(decision, "authoritative", False))


def _task_dependencies(task: Mapping[str, Any]) -> tuple[str, ...]:
    depends_on = task.get("depends_on", ())
    if not isinstance(depends_on, (list, tuple)):
        depends_on = ()
    return tuple(sorted({str(item) for item in depends_on if str(item)}))


def _dependency_closed_ids(
    *,
    task_by_id: Mapping[str, Mapping[str, Any]],
    accepted_task_ids: set[str],
) -> set[str]:
    closed: set[str] = set()
    progress = True
    while progress:
        progress = False
        for task_id in sorted(accepted_task_ids - closed):
            deps = _task_dependencies(task_by_id[task_id])
            if all(dep in closed for dep in deps if dep in task_by_id) and all(dep in task_by_id for dep in deps):
                closed.add(task_id)
                progress = True
    return closed


def _dependency_unresolved_ids(
    task_id: str,
    *,
    task_by_id: Mapping[str, Mapping[str, Any]],
    dependency_closed_completed_ids: set[str],
) -> tuple[str, ...]:
    deps = _task_dependencies(task_by_id[task_id])
    return tuple(dep for dep in deps if dep not in dependency_closed_completed_ids)


def _next_ready_wave(
    *,
    task_by_id: Mapping[str, Mapping[str, Any]],
    dependency_closed_completed_ids: set[str],
    max_ready_wave_size: int,
) -> tuple[str, ...]:
    work_list = [
        {"id": task_id, "depends_on": list(_task_dependencies(task_by_id[task_id]))}
        for task_id in sorted(task_by_id)
    ]
    batches = schedule_batches(
        work_list,
        max_batch_size=max_ready_wave_size,
        completed_ids=set(dependency_closed_completed_ids),
    )
    return tuple(batches[0]) if batches else ()


def derive_plan_execution_view(
    authority: RunAuthorityView,
    plan: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    *,
    evidence_decisions: Mapping[str, Any],
    legacy_labels: Iterable[LegacyTaskLabel] = (),
    plan_source: str = "finalize.json",
    max_ready_wave_size: int = 5,
) -> PlanExecutionView:
    """Bind generic accepted decisions to Megaplan tasks without external reads.

    Completion is the intersection of a fully linked kernel decision and the
    existing Megaplan evidence policy.  Raw plan/artifact labels are retained
    for drift diagnosis only.
    """

    records = _task_records(plan)
    task_by_id: dict[str, Mapping[str, Any]] = {}
    labels = list(legacy_labels)
    diagnostics: list[PlanExecutionDiagnostic] = []
    for task in records:
        task_id = str(task.get("id", "")).strip()
        if not task_id or task_id in task_by_id:
            raise ValueError(f"plan task IDs must be unique and non-empty: {task_id!r}")
        task_by_id[task_id] = task
        raw_status = task.get("status")
        if isinstance(raw_status, str) and raw_status:
            labels.append(LegacyTaskLabel(task_id, raw_status, plan_source, "projection"))

    labels_by_task: dict[str, list[LegacyTaskLabel]] = {task_id: [] for task_id in task_by_id}
    for label in sorted(set(labels)):
        if label.task_id not in task_by_id:
            diagnostics.append(PlanExecutionDiagnostic(
                "unknown_legacy_subject", label.task_id,
                "legacy label references a task outside the current plan revision", label.source,
            ))
            continue
        labels_by_task[label.task_id].append(label)

    evidence_by_id = {evidence.evidence_id: evidence for evidence in authority.evidence}
    attempts_by_id = {attempt.attempt_id: attempt for attempt in authority.attempts}
    claims_by_id = {claim.claim_id: claim for claim in authority.claims}
    completion_claims = {
        claim.claim_id: claim
        for claim in authority.claims
        if claim.claim_type == TASK_COMPLETION_CLAIM and claim.subject_id in task_by_id
    }
    accepted_by_task: dict[str, list[Any]] = {task_id: [] for task_id in task_by_id}
    accepted_attempts_by_task: dict[str, list[AcceptedTaskAttempt]] = {task_id: [] for task_id in task_by_id}
    resolved_claim_ids: set[str] = set()
    for decision in authority.decisions:
        claim = claims_by_id.get(decision.claim_id)
        if claim is None or claim.claim_id not in completion_claims:
            continue
        resolved_claim_ids.add(claim.claim_id)
        policy_decision = evidence_decisions.get(claim.subject_id)
        if decision.outcome == "accepted" and _decision_authoritative(policy_decision):
            accepted_by_task[claim.subject_id].append(decision)
            attempt = attempts_by_id.get(decision.attempt_id)
            if attempt is None:
                diagnostics.append(PlanExecutionDiagnostic(
                    "accepted_decision_missing_attempt", claim.subject_id,
                    "accepted task decision does not reference a retained attempt",
                    f"contract://decision/{decision.decision_id}",
                ))
                continue
            evidence_sources = tuple(sorted(
                evidence_by_id[evidence_id].source
                for evidence_id in decision.evidence_ids
                if evidence_id in evidence_by_id
            ))
            accepted_attempts_by_task[claim.subject_id].append(AcceptedTaskAttempt(
                task_id=claim.subject_id,
                attempt_id=attempt.attempt_id,
                claim_id=claim.claim_id,
                decision_id=decision.decision_id,
                grant_id=decision.grant_id,
                evidence_ids=tuple(sorted(decision.evidence_ids)),
                source_paths=evidence_sources,
            ))
        elif decision.outcome == "accepted":
            diagnostics.append(PlanExecutionDiagnostic(
                "kernel_policy_disagreement", claim.subject_id,
                "kernel accepted the claim but Megaplan evidence policy did not", 
                f"contract://decision/{decision.decision_id}",
            ))

    unresolved = sorted(set(completion_claims) - resolved_claim_ids)
    accepted_task_id_set = {task_id for task_id, decisions in accepted_by_task.items() if decisions}
    dependency_closed_completed_ids = _dependency_closed_ids(
        task_by_id=task_by_id,
        accepted_task_ids=accepted_task_id_set,
    )
    for task_id in sorted(accepted_task_id_set - dependency_closed_completed_ids):
        unresolved_dependencies = _dependency_unresolved_ids(
            task_id,
            task_by_id=task_by_id,
            dependency_closed_completed_ids=dependency_closed_completed_ids,
        )
        source = ",".join(sorted({item.source for item in labels_by_task[task_id]})) or plan_source
        diagnostics.append(PlanExecutionDiagnostic(
            "accepted_task_dependency_unresolved",
            task_id,
            "accepted task attempt is not dependency-closed; unresolved dependencies: "
            + ", ".join(unresolved_dependencies),
            source,
        ))

    for task_id in sorted(task_by_id):
        unknown_dependencies = tuple(dep for dep in _task_dependencies(task_by_id[task_id]) if dep not in task_by_id)
        for dep_id in unknown_dependencies:
            diagnostics.append(PlanExecutionDiagnostic(
                "unknown_dependency",
                task_id,
                f"task depends on unknown task {dep_id!r}",
                plan_source,
            ))

    try:
        next_ready_wave = _next_ready_wave(
            task_by_id=task_by_id,
            dependency_closed_completed_ids=dependency_closed_completed_ids,
            max_ready_wave_size=max_ready_wave_size,
        )
    except ValueError as exc:
        diagnostics.append(PlanExecutionDiagnostic(
            "dag_policy_unresolved",
            "plan",
            str(exc),
            plan_source,
        ))
        next_ready_wave = ()

    for task_id in sorted(set(task_by_id) - dependency_closed_completed_ids - set(next_ready_wave)):
        unresolved_dependencies = _dependency_unresolved_ids(
            task_id,
            task_by_id=task_by_id,
            dependency_closed_completed_ids=dependency_closed_completed_ids,
        )
        if not unresolved_dependencies:
            continue
        source = ",".join(sorted({item.source for item in labels_by_task[task_id]})) or plan_source
        diagnostics.append(PlanExecutionDiagnostic(
            "unresolved_dependency",
            task_id,
            "task dependencies are not dependency-closed: " + ", ".join(unresolved_dependencies),
            source,
        ))

    task_states: list[TaskExecutionState] = []
    for task_id, task in sorted(task_by_id.items()):
        accepted_decisions = sorted(item.decision_id for item in accepted_by_task[task_id])
        accepted_attempt_ids = sorted(item.attempt_id for item in accepted_attempts_by_task[task_id])
        task_unresolved = sorted(
            claim_id for claim_id in unresolved if completion_claims[claim_id].subject_id == task_id
        )
        task_labels = tuple(labels_by_task[task_id])
        accepted = bool(accepted_decisions)
        dependency_closed = task_id in dependency_closed_completed_ids
        unresolved_dependency_ids = _dependency_unresolved_ids(
            task_id,
            task_by_id=task_by_id,
            dependency_closed_completed_ids=dependency_closed_completed_ids,
        )
        legacy_terminal = any(item.label in _LEGACY_TERMINAL for item in task_labels)
        if legacy_terminal and not accepted:
            for item in task_labels:
                if item.label in _LEGACY_TERMINAL:
                    diagnostics.append(PlanExecutionDiagnostic(
                        "legacy_terminal_without_authority", task_id,
                        "legacy terminal label has no evidence-backed accepted kernel decision",
                        item.source,
                    ))
        if accepted and task_labels and not legacy_terminal:
            diagnostics.append(PlanExecutionDiagnostic(
                "legacy_projection_stale", task_id,
                "accepted authority contradicts the non-terminal legacy projection",
                ",".join(sorted({item.source for item in task_labels})),
            ))
        evidence_sources = {
            evidence.source
            for decision in accepted_by_task[task_id]
            for evidence in authority.evidence
            if evidence.evidence_id in decision.evidence_ids
        }
        sources = tuple(sorted(evidence_sources | {item.source for item in task_labels}))
        depends_on = _task_dependencies(task)
        task_states.append(TaskExecutionState(
            task_id=task_id,
            depends_on=depends_on,
            accepted=accepted,
            dependency_closed=dependency_closed,
            authority_status="accepted" if accepted else "unaccepted",
            accepted_attempt_ids=tuple(accepted_attempt_ids),
            accepted_decision_ids=tuple(accepted_decisions),
            unresolved_claim_ids=tuple(task_unresolved),
            unresolved_dependency_ids=unresolved_dependency_ids,
            legacy_labels=task_labels,
            source_paths=sources,
        ))

    for item in authority.diagnostics:
        diagnostics.append(PlanExecutionDiagnostic(
            item.code, item.record_id, item.reason, item.source
        ))
    for item in authority.quarantines:
        diagnostics.append(PlanExecutionDiagnostic(
            "quarantined_authority_record", item.record_id, item.reason, item.source
        ))

    values = {
        "schema_version": 1,
        "run_id": authority.run_id,
        "run_revision": authority.run_revision,
        "authority_view_hash": authority.view_hash,
        "tasks": tuple(task_states),
        "accepted_task_ids": tuple(item.task_id for item in task_states if item.accepted),
        "accepted_task_attempts": tuple(sorted(
            (
                item
                for attempts in accepted_attempts_by_task.values()
                for item in attempts
            ),
            key=lambda item: (item.task_id, item.attempt_id, item.decision_id),
        )),
        "dependency_closed_completed_task_ids": tuple(
            task_id for task_id in sorted(dependency_closed_completed_ids)
        ),
        "next_ready_wave": next_ready_wave,
        "unresolved_claim_ids": tuple(unresolved),
        "quarantine_ids": tuple(sorted(item.quarantine_id for item in authority.quarantines)),
        "diagnostics": tuple(sorted(set(diagnostics))),
    }
    unsigned = PlanExecutionView(**values, view_hash="pending")
    digest = hashlib.sha256(canonical_json(unsigned._payload()).encode("utf-8")).hexdigest()
    return PlanExecutionView(**values, view_hash=digest)


# ---------------------------------------------------------------------------
# HumanGateView — read-only projection of human-gate signals
# ---------------------------------------------------------------------------

_VALID_GATE_TYPES = frozenset(
    {
        "needs_human",
        "override",
        "user_action",
        "approval_checkpoint",
        "denial_checkpoint",
        "suspension",
    }
)

_VALID_GATE_STATUSES = frozenset(
    {"blocked", "attention_needed", "resolved", "unknown"}
)


@dataclass(frozen=True, order=True)
class HumanGateObservation:
    """A single observation about a potential human gate.

    This is deliberately *not* authority.  A ``needs_human`` sidecar or an
    ``override`` artifact is observed and projected; the observation does not
    block execution or declare a gate outcome on its own.
    """

    observation_id: str
    gate_type: str
    gate_reason: str
    source: str
    stale_token: bool = False
    superseded: bool = False

    def __post_init__(self) -> None:
        if self.gate_type not in _VALID_GATE_TYPES:
            raise ValueError(
                f"unsupported gate_type {self.gate_type!r}; must be one of "
                + ", ".join(sorted(_VALID_GATE_TYPES))
            )
        if not self.observation_id or not self.gate_reason or not self.source:
            raise ValueError(
                "HumanGateObservation requires observation_id, gate_reason, and source"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "gate_type": self.gate_type,
            "gate_reason": self.gate_reason,
            "source": self.source,
            "stale_token": self.stale_token,
            "superseded": self.superseded,
        }


@dataclass(frozen=True, order=True)
class HumanGateDiagnostic:
    """A non-authoritative reason a human-gate signal may be stale, superseded,
    or ambiguous.

    Diagnostics are observations about observations — they explain *why* a
    signal should not be treated as a live gate, but they do not themselves
    open or close gates.
    """

    code: str
    reason: str
    source: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "reason": self.reason, "source": self.source}


@dataclass(frozen=True)
class HumanGateView:
    """Read-only projection of human-gate signals.

    This view collects ``needs_human``, ``override``, ``user_action``, and
    related sidecar observations and reports whether human attention appears
    to be required, resolved, or unknown.  It is a Megaplan-local sibling of
    ``RunnerView`` and ``PublicationView`` — diagnostics only, never execution
    authority.
    """

    schema_version: int
    status: str
    human_required: bool
    typed_gate: str | None
    observations: tuple[HumanGateObservation, ...]
    source_paths: tuple[str, ...]
    diagnostics: tuple[HumanGateDiagnostic, ...]
    view_hash: str

    def __post_init__(self) -> None:
        if self.status not in _VALID_GATE_STATUSES:
            raise ValueError(
                f"unsupported HumanGateView status {self.status!r}"
            )

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "human_required": self.human_required,
            "typed_gate": self.typed_gate,
            "observations": [item.to_dict() for item in self.observations],
            "source_paths": list(self.source_paths),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "shadow": True,
            "read_only": True,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "view_hash": self.view_hash}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


def _normalize_human_gate_observation(
    signal: Mapping[str, Any],
    *,
    current_plan_revision: str | None,
) -> HumanGateObservation:
    """Normalize one human-gate signal into a stable observation.

    The signal may come from a needs-human sidecar, override artifact,
    user_action record, or checkpoint.  Every field is extracted defensively;
    nothing is trusted as authority.
    """

    source = _optional_string(signal.get("source")) or "observation://unknown"
    gate_type_raw = _optional_string(
        signal.get("gate_type") or signal.get("type") or signal.get("kind")
    )
    gate_type = gate_type_raw.lower() if gate_type_raw else "needs_human"
    if gate_type not in _VALID_GATE_TYPES:
        gate_type = "needs_human"

    reason = _optional_string(
        signal.get("gate_reason")
        or signal.get("reason")
        or signal.get("rationale")
    ) or "unspecified"

    # --- stale-token detection ------------------------------------------------
    stale_token = False
    plan_ref_raw = signal.get("plan_ref") or signal.get("plan_revision") or signal.get("target_ref")
    plan_ref = _optional_string(plan_ref_raw)
    if current_plan_revision and plan_ref and plan_ref != current_plan_revision:
        stale_token = True

    # Also honour an explicit stale marker.
    if signal.get("stale_token") is True or signal.get("stale") is True:
        stale_token = True

    # --- superseded-override detection ----------------------------------------
    superseded = False
    if signal.get("superseded") is True or signal.get("superseded_override") is True:
        superseded = True

    # --- deterministic observation id -----------------------------------------
    observation_id = _optional_string(
        signal.get("observation_id") or signal.get("id")
    )
    if observation_id is None:
        unsigned = {
            "gate_type": gate_type,
            "gate_reason": reason,
            "source": source,
            "stale_token": stale_token,
            "superseded": superseded,
        }
        observation_id = hashlib.sha256(
            canonical_json(unsigned).encode("utf-8")
        ).hexdigest()

    return HumanGateObservation(
        observation_id=observation_id,
        gate_type=gate_type,
        gate_reason=reason,
        source=source,
        stale_token=stale_token,
        superseded=superseded,
    )


def derive_human_gate_view(
    human_gate_signals: Iterable[Mapping[str, Any]],
    *,
    current_plan_revision: str | None = None,
) -> HumanGateView:
    """Project human-gate readiness without opening or closing gates.

    Every input is treated as an observation.  The view reports whether human
    attention appears required and diagnoses stale tokens (gate references a
    different plan revision) and superseded overrides, but it never blocks
    execution on its own.

    Parameters
    ----------
    human_gate_signals:
        Iterable of signal mappings.  Each mapping is expected to have at
        least a ``source`` and a ``gate_type`` (or ``type``/``kind``) key,
        plus optional ``plan_ref``, ``stale_token``, and ``superseded`` flags.
    current_plan_revision:
        When provided, plan references in signals that differ from this value
        are flagged as stale-token diagnostics.
    """

    normalized = tuple(
        sorted(
            {
                _normalize_human_gate_observation(
                    signal, current_plan_revision=current_plan_revision
                )
                for signal in human_gate_signals
                if isinstance(signal, Mapping)
            },
            key=lambda item: canonical_json(item.to_dict()),
        )
    )

    diagnostics: list[HumanGateDiagnostic] = []

    # --- stale-token diagnostics ----------------------------------------------
    stale_tokens = tuple(item for item in normalized if item.stale_token)
    for item in stale_tokens:
        diagnostics.append(
            HumanGateDiagnostic(
                "stale_token",
                f"human-gate observation {item.observation_id!r} references a "
                f"different plan revision; gate_type={item.gate_type!r}",
                item.source,
            )
        )

    # --- superseded-override diagnostics --------------------------------------
    superseded_items = tuple(item for item in normalized if item.superseded)
    for item in superseded_items:
        diagnostics.append(
            HumanGateDiagnostic(
                "superseded_override",
                f"override observation {item.observation_id!r} has been "
                f"superseded by a more recent override",
                item.source,
            )
        )

    # --- ambiguous / mechanical diagnostics -----------------------------------
    needs_human_items = tuple(
        item for item in normalized if item.gate_type == "needs_human"
    )
    override_items = tuple(
        item for item in normalized if item.gate_type == "override"
    )
    user_action_items = tuple(
        item for item in normalized if item.gate_type == "user_action"
    )

    # If there's a needs_human but it's stale, report it.
    live_needs_human = tuple(
        item for item in needs_human_items if not item.stale_token
    )
    if needs_human_items and not live_needs_human:
        diagnostics.append(
            HumanGateDiagnostic(
                "stale_needs_human",
                "all needs-human observations reference stale plan revisions; "
                "no live human gate detected",
                ",".join(sorted({item.source for item in needs_human_items})),
            )
        )

    # If there's an override but it's stale or superseded, note it.
    live_overrides = tuple(
        item
        for item in override_items
        if not item.stale_token and not item.superseded
    )
    if override_items and not live_overrides:
        diagnostics.append(
            HumanGateDiagnostic(
                "stale_or_superseded_override",
                "all override observations are either stale or superseded; "
                "no active override is in effect",
                ",".join(sorted({item.source for item in override_items})),
            )
        )

    # --- status determination -------------------------------------------------
    # Priority: blocked (live needs-human or user_action present) >
    #           attention_needed (some signal but not definitely blocking) >
    #           resolved (explicit approval/denial checkpoint without live needs-human) >
    #           unknown

    has_live_blocker = bool(live_needs_human) or bool(user_action_items)
    has_approval = any(
        item.gate_type in ("approval_checkpoint",) for item in normalized
    )
    has_denial = any(
        item.gate_type in ("denial_checkpoint",) for item in normalized
    )
    has_resolution = has_approval or has_denial or bool(live_overrides)

    if has_live_blocker:
        status = "blocked"
        human_required = True
    elif has_resolution and not has_live_blocker:
        status = "resolved"
        human_required = False
    elif normalized:
        status = "attention_needed"
        human_required = False  # diagnostic, not a definite block
    else:
        status = "unknown"
        human_required = False

    # --- typed gate extraction ------------------------------------------------
    typed_gate: str | None = None
    if human_required and live_needs_human:
        typed_gate = live_needs_human[0].gate_reason or live_needs_human[0].gate_type

    values = {
        "schema_version": 1,
        "status": status,
        "human_required": human_required,
        "typed_gate": typed_gate,
        "observations": normalized,
        "source_paths": tuple(sorted({item.source for item in normalized})),
        "diagnostics": tuple(sorted(set(diagnostics))),
    }
    unsigned = HumanGateView(**values, view_hash="pending")
    digest = hashlib.sha256(
        canonical_json(unsigned._payload()).encode("utf-8")
    ).hexdigest()
    return HumanGateView(**values, view_hash=digest)


# ---------------------------------------------------------------------------
# MegaplanRecoveryView — read-only projection of recovery/repair custody
# ---------------------------------------------------------------------------

_VALID_RECOVERY_STATUSES = frozenset(
    {
        "repairing",
        "repairable",
        "human_required",
        "broken_superfixer",
        "healthy",
        "blocked",
        "unknown",
    }
)

_VALID_PERMITTED_ACTION_TYPES = frozenset(
    {
        "retry",
        "repair_dispatch",
        "human_escalation",
        "no_action",
        "investigate_superfixer",
    }
)


@dataclass(frozen=True, order=True)
class RecoveryCustodyObservation:
    """A single, source-addressable fact about repair/retry custody.

    This observation is deliberately *not* authority.  It reports what the
    repair custody projection found without deciding whether a repair should
    proceed.  Sibling views (runner, execution, publication, human-gate) are
    consumed separately so that recovery classification does not conflate
    repair state with runner liveness or publication blockers.
    """

    observation_id: str
    custody_bucket: str
    blocker_id: str
    current_state: str
    retry_strategy: str
    failure_kind: str
    active_request_count: int
    source: str

    def __post_init__(self) -> None:
        if not self.observation_id or not self.source:
            raise ValueError(
                "RecoveryCustodyObservation requires observation_id and source"
            )
        if self.active_request_count < 0:
            raise ValueError("active_request_count must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "custody_bucket": self.custody_bucket,
            "blocker_id": self.blocker_id,
            "current_state": self.current_state,
            "retry_strategy": self.retry_strategy,
            "failure_kind": self.failure_kind,
            "active_request_count": self.active_request_count,
            "source": self.source,
        }


@dataclass(frozen=True, order=True)
class PermittedAction:
    """A recovery action that is permitted given the current projection.

    Permitted actions are derived from the custody bucket, sibling views,
    and active-step observations.  They are diagnostic — they describe what
    *may* be done, not what *must* be done.
    """

    action_id: str
    action_type: str
    rationale: str
    source: str

    def __post_init__(self) -> None:
        if self.action_type not in _VALID_PERMITTED_ACTION_TYPES:
            raise ValueError(
                f"unsupported permitted action type {self.action_type!r}; "
                f"must be one of {', '.join(sorted(_VALID_PERMITTED_ACTION_TYPES))}"
            )
        if not self.action_id or not self.rationale or not self.source:
            raise ValueError(
                "PermittedAction requires action_id, rationale, and source"
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "rationale": self.rationale,
            "source": self.source,
        }


@dataclass(frozen=True, order=True)
class RecoveryDiagnostic:
    """A non-authoritative reason the recovery view may be uncertain, stale,
    or contradictory.

    Diagnostics explain *why* a recovery action may not be safe or why the
    current custody projection may need re-evaluation.  They are observations
    about observations.
    """

    code: str
    reason: str
    source: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "reason": self.reason, "source": self.source}


@dataclass(frozen=True)
class MegaplanRecoveryView:
    """Read-only projection of repair/recovery custody and permitted actions.

    This view composes a preloaded repair custody projection with sibling
    runner, execution, publication, and human-gate views to classify whether
    recovery is needed, what custody bucket the run is in, and which recovery
    actions are permitted.

    It is a Megaplan-local sibling of ``RunnerView``, ``PublicationView``,
    ``PlanExecutionView``, and ``HumanGateView`` — diagnostics only, never
    execution authority.
    """

    schema_version: int
    status: str
    recovery_needed: bool
    custody_bucket: str | None
    observations: tuple[RecoveryCustodyObservation, ...]
    permitted_actions: tuple[PermittedAction, ...]
    source_paths: tuple[str, ...]
    diagnostics: tuple[RecoveryDiagnostic, ...]
    view_hash: str

    def __post_init__(self) -> None:
        if self.status not in _VALID_RECOVERY_STATUSES:
            raise ValueError(
                f"unsupported MegaplanRecoveryView status {self.status!r}"
            )

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "recovery_needed": self.recovery_needed,
            "custody_bucket": self.custody_bucket,
            "observations": [item.to_dict() for item in self.observations],
            "permitted_actions": [item.to_dict() for item in self.permitted_actions],
            "source_paths": list(self.source_paths),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "shadow": True,
            "read_only": True,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "view_hash": self.view_hash}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


def _normalize_recovery_custody_observation(
    custody: Mapping[str, Any],
    *,
    source: str = "custody://projection",
) -> RecoveryCustodyObservation:
    """Normalize one repair custody projection into a stable observation.

    Every field is extracted defensively; nothing is trusted as authority.
    The custody projection is treated as a preloaded artifact — this function
    does not read the filesystem, Git, processes, or the wall clock.
    """

    custody_bucket = _optional_string(custody.get("custody_bucket")) or "unknown"
    blocker_id = _optional_string(custody.get("blocker_id")) or ""
    current_state = _optional_string(custody.get("current_state")) or "unknown"
    retry_strategy = _optional_string(custody.get("retry_strategy")) or ""
    failure_kind = _optional_string(custody.get("failure_kind")) or ""
    active_requests = custody.get("active_request_ids")
    active_count = len(active_requests) if isinstance(active_requests, (list, tuple)) else 0

    unsigned = {
        "custody_bucket": custody_bucket,
        "blocker_id": blocker_id,
        "current_state": current_state,
        "retry_strategy": retry_strategy,
        "failure_kind": failure_kind,
        "active_request_count": active_count,
        "source": source,
    }
    observation_id = hashlib.sha256(
        canonical_json(unsigned).encode("utf-8")
    ).hexdigest()

    return RecoveryCustodyObservation(
        observation_id=observation_id,
        custody_bucket=custody_bucket,
        blocker_id=blocker_id,
        current_state=current_state,
        retry_strategy=retry_strategy,
        failure_kind=failure_kind,
        active_request_count=active_count,
        source=source,
    )


def _recovery_custody_has_durable_active_repair(custody: Mapping[str, Any]) -> bool:
    active_requests = {
        str(value).strip()
        for value in custody.get("active_request_ids", ())
        if isinstance(value, str) and value.strip()
    }
    active_claims = {
        str(value).strip()
        for value in custody.get("active_claim_request_ids", ())
        if isinstance(value, str) and value.strip()
    }
    if active_requests & active_claims:
        return True
    attempts = custody.get("attempts")
    if not isinstance(attempts, list):
        return False
    return any(
        isinstance(attempt, Mapping)
        and attempt.get("terminal") is False
        and bool(str(attempt.get("attempt_id") or "").strip())
        and bool(str(attempt.get("path") or "").strip())
        and (
            str(attempt.get("request_id") or "").strip() in active_requests
            or str(attempt.get("source") or "").strip() == "repair_queue_dispatch_attempt"
        )
        for attempt in attempts
    )


def derive_megaplan_recovery_view(
    repair_custody: Mapping[str, Any] | None = None,
    *,
    runner_view: RunnerView | None = None,
    execution_view: PlanExecutionView | None = None,
    publication_view: PublicationView | None = None,
    human_gate_view: HumanGateView | None = None,
    active_step_observations: Iterable[Mapping[str, Any]] = (),
    custody_source: str = "custody://projection",
) -> MegaplanRecoveryView:
    """Project recovery/repair readiness without performing I/O or deciding execution.

    The function composes a preloaded repair custody projection with sibling
    runner, execution, publication, and human-gate views to classify whether
    recovery is needed and which recovery actions are permitted.

    Parameters
    ----------
    repair_custody:
        A preloaded ``RepairCustodyProjection`` (or compatible mapping).  When
        ``None``, the view reports ``unknown`` and emits no custody observation.
    runner_view:
        Precomputed ``RunnerView`` for liveness cross-checking.
    execution_view:
        Precomputed ``PlanExecutionView`` for task-state cross-checking.
    publication_view:
        Precomputed ``PublicationView`` for publication-blocker cross-checking.
    human_gate_view:
        Precomputed ``HumanGateView`` for human-gate cross-checking.
    active_step_observations:
        Iterable of stale or active-step observations that may inform recovery
        classification (e.g., step-duration anomalies, retry-loop evidence).
    custody_source:
        Source path label for the custody projection artifact.
    """

    diagnostics: list[RecoveryDiagnostic] = []
    observations: list[RecoveryCustodyObservation] = []
    permitted_actions: list[PermittedAction] = []
    source_paths: set[str] = set()

    # --- normalize custody projection ----------------------------------------
    custody_obs: RecoveryCustodyObservation | None = None
    custody_bucket: str | None = None
    if repair_custody is not None and isinstance(repair_custody, Mapping):
        normalized_custody = dict(repair_custody)
        if (
            str(normalized_custody.get("custody_bucket") or "") == "repairing"
            and not _recovery_custody_has_durable_active_repair(normalized_custody)
        ):
            diagnostics.append(
                RecoveryDiagnostic(
                    "unsupported_repairing_custody",
                    "repairing label has no durable active claim or attempt",
                    custody_source,
                )
            )
            normalized_custody["custody_bucket"] = "unknown"
        custody_obs = _normalize_recovery_custody_observation(
            normalized_custody, source=custody_source
        )
        observations.append(custody_obs)
        source_paths.add(custody_source)
        custody_bucket = custody_obs.custody_bucket
    else:
        diagnostics.append(
            RecoveryDiagnostic(
                "custody_unavailable",
                "no repair custody projection available; recovery classification is unknown",
                custody_source,
            )
        )

    # --- incorporate sibling view source paths -------------------------------
    for view in (runner_view, publication_view, human_gate_view):
        if view is not None and hasattr(view, "source_paths"):
            source_paths.update(view.source_paths)
    if execution_view is not None:
        for task in execution_view.tasks:
            source_paths.update(task.source_paths)

    # --- runner-liveness cross-check -----------------------------------------
    runner_dead = False
    if runner_view is not None:
        if runner_view.status in ("stopped", "stale", "identity_mismatch"):
            runner_dead = True
            diagnostics.append(
                RecoveryDiagnostic(
                    "runner_unavailable",
                    f"runner is {runner_view.status}; recovery actions may be unsafe",
                    ",".join(runner_view.source_paths)
                    or "observation://unknown",
                )
            )

    # --- publication-blocker cross-check -------------------------------------
    publication_blocked = False
    if publication_view is not None:
        if publication_view.status in ("blocked", "contradicted"):
            publication_blocked = True
            diagnostics.append(
                RecoveryDiagnostic(
                    "publication_blocked",
                    f"publication is {publication_view.status}; recovery may be "
                    "ineffective until publication is resolved",
                    ",".join(publication_view.source_paths)
                    or "observation://unknown",
                )
            )

    # --- execution-view cross-check ------------------------------------------
    if execution_view is not None and execution_view.quarantine_ids:
        diagnostics.append(
            RecoveryDiagnostic(
                "authority_quarantine",
                f"execution authority has {len(execution_view.quarantine_ids)} "
                "quarantined records; recovery decisions may be based on "
                "incomplete authority",
                ",".join(execution_view.source_paths) or "observation://unknown",
            )
        )

    # --- human-gate cross-check ----------------------------------------------
    human_blocked = False
    if human_gate_view is not None:
        if human_gate_view.status == "blocked" and human_gate_view.human_required:
            human_blocked = True
            diagnostics.append(
                RecoveryDiagnostic(
                    "human_gate_blocked",
                    "human gate is blocked and requires human attention; "
                    "automated recovery may be overridden",
                    ",".join(human_gate_view.source_paths)
                    or "observation://unknown",
                )
            )

    # --- active-step staleness diagnostics -----------------------------------
    stale_steps = 0
    for step in active_step_observations:
        if not isinstance(step, Mapping):
            continue
        step_source = _optional_string(step.get("source")) or "observation://unknown"
        source_paths.add(step_source)
        if step.get("stale") is True or step.get("stale_step") is True:
            stale_steps += 1
    if stale_steps > 0:
        diagnostics.append(
            RecoveryDiagnostic(
                "stale_active_steps",
                f"{stale_steps} active-step observation(s) are stale; "
                "recovery custody may be out of date",
                ",".join(sorted(source_paths)) or "observation://unknown",
            )
        )

    # --- permitted-action derivation -----------------------------------------
    # Actions are derived from the custody bucket *and* sibling-view
    # cross-checks.  The mapping is:
    #
    #   custody bucket            | default permitted actions
    #   --------------------------+----------------------------------------
    #   repairing                 | no_action (already repairing)
    #   repairable_not_repairing  | repair_dispatch, retry
    #   human_required            | human_escalation
    #   broken_superfixer         | investigate_superfixer
    #   (unknown/missing)         | no_action
    #
    # When the runner is dead, publication is blocked, or the human gate
    # requires attention, recovery actions that would be ineffective or
    # overridden are still listed but paired with diagnostics.

    action_counter = 0

    def _add_action(action_type: str, rationale: str, source: str) -> None:
        nonlocal action_counter
        action_id = hashlib.sha256(
            canonical_json(
                {
                    "action_type": action_type,
                    "rationale": rationale,
                    "source": source,
                }
            ).encode("utf-8")
        ).hexdigest()[:16]
        permitted_actions.append(
            PermittedAction(
                action_id=action_id,
                action_type=action_type,
                rationale=rationale,
                source=source,
            )
        )

    if custody_bucket is None:
        _add_action(
            "no_action",
            "no custody projection available; recovery classification is unknown",
            custody_source,
        )
    elif custody_bucket == "repairing":
        _add_action(
            "no_action",
            "repair is already in progress",
            ",".join(sorted(source_paths)) or custody_source,
        )
    elif custody_bucket == "repairable_not_repairing":
        if runner_dead:
            _add_action(
                "no_action",
                "runner is unavailable; repair dispatch is deferred",
                ",".join(sorted(source_paths)) or custody_source,
            )
            diagnostics.append(
                RecoveryDiagnostic(
                    "repair_blocked_by_runner",
                    "repair is indicated but the runner is not live",
                    ",".join(runner_view.source_paths) if runner_view else custody_source,
                )
            )
        elif publication_blocked:
            _add_action(
                "no_action",
                "publication is blocked; repair dispatch is deferred",
                ",".join(sorted(source_paths)) or custody_source,
            )
            diagnostics.append(
                RecoveryDiagnostic(
                    "repair_blocked_by_publication",
                    "repair is indicated but publication is blocked",
                    ",".join(publication_view.source_paths) if publication_view else custody_source,
                )
            )
        elif human_blocked:
            _add_action(
                "human_escalation",
                "human gate is blocked; repair requires human attention first",
                ",".join(sorted(source_paths)) or custody_source,
            )
        else:
            _add_action(
                "repair_dispatch",
                "repair is indicated and no blockers are present",
                ",".join(sorted(source_paths)) or custody_source,
            )
            _add_action(
                "retry",
                "retry may also be considered as an alternative recovery path",
                ",".join(sorted(source_paths)) or custody_source,
            )
    elif custody_bucket == "human_required":
        _add_action(
            "human_escalation",
            "repair custody requires human intervention",
            ",".join(sorted(source_paths)) or custody_source,
        )
    elif custody_bucket == "broken_superfixer":
        _add_action(
            "investigate_superfixer",
            "superfixer is broken; automated repair cannot proceed",
            ",".join(sorted(source_paths)) or custody_source,
        )
        _add_action(
            "human_escalation",
            "human investigation of the superfixer is recommended",
            ",".join(sorted(source_paths)) or custody_source,
        )
    else:
        _add_action(
            "no_action",
            f"unrecognized custody bucket {custody_bucket!r}; no action determined",
            ",".join(sorted(source_paths)) or custody_source,
        )

    # --- status determination ------------------------------------------------
    # Priority order (highest first):
    #   blocked (runner dead / publication blocked / human gate active)
    #   human_required
    #   broken_superfixer
    #   repairing
    #   repairable
    #   healthy
    #   unknown

    if custody_bucket is None:
        status = "unknown"
        recovery_needed = False
    elif human_blocked or runner_dead or publication_blocked:
        status = "blocked"
        recovery_needed = True
    elif custody_bucket == "human_required":
        status = "human_required"
        recovery_needed = True
    elif custody_bucket == "broken_superfixer":
        status = "broken_superfixer"
        recovery_needed = True
    elif custody_bucket == "repairing":
        status = "repairing"
        recovery_needed = True
    elif custody_bucket == "repairable_not_repairing":
        status = "repairable"
        recovery_needed = True
    else:
        # No blockers and no custody evidence of distress
        status = "healthy"
        recovery_needed = False

    values = {
        "schema_version": 1,
        "status": status,
        "recovery_needed": recovery_needed,
        "custody_bucket": custody_bucket,
        "observations": tuple(sorted(observations, key=lambda item: item.observation_id)),
        "permitted_actions": tuple(sorted(permitted_actions, key=lambda item: item.action_id)),
        "source_paths": tuple(sorted(source_paths)),
        "diagnostics": tuple(sorted(set(diagnostics))),
    }
    unsigned = MegaplanRecoveryView(**values, view_hash="pending")
    digest = hashlib.sha256(
        canonical_json(unsigned._payload()).encode("utf-8")
    ).hexdigest()
    return MegaplanRecoveryView(**values, view_hash=digest)


# ---------------------------------------------------------------------------
# MegaplanPlanView — thin composition facade over all five sibling views
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MegaplanPlanView:
    """Thin composition facade packaging all five sibling authority views.

    This is deliberately a packaging convenience — operators and orchestrators
    can render a single aggregate, but internal consumers should use the
    smallest relevant sibling view.  Each sub-view retains its own hash;
    the facade hash is computed from the composition, not from re-deriving
    the sibling views.

    The facade adds no new policy.  Execution, runner, publication,
    human-gate, and recovery payloads remain separable — consumers that
    only need runner liveness should read ``runner``, not the full facade.
    """

    schema_version: int
    run_id: str
    run_revision: str
    execution: dict[str, Any]
    runner: dict[str, Any]
    publication: dict[str, Any]
    human_gate: dict[str, Any]
    recovery: dict[str, Any]
    source_paths: tuple[str, ...]
    view_hash: str

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "run_revision": self.run_revision,
            "execution": self.execution,
            "runner": self.runner,
            "publication": self.publication,
            "human_gate": self.human_gate,
            "recovery": self.recovery,
            "source_paths": list(self.source_paths),
            "shadow": True,
            "read_only": True,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "view_hash": self.view_hash}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


def derive_megaplan_plan_view(
    execution_view: PlanExecutionView,
    *,
    runner_view: RunnerView | None = None,
    publication_view: PublicationView | None = None,
    human_gate_view: HumanGateView | None = None,
    recovery_view: MegaplanRecoveryView | None = None,
) -> MegaplanPlanView:
    """Compose all five sibling authority views into a single packaging facade.

    Each sub-view retains its own hash and diagnostics.  The facade adds no
    new policy — it is a read-only packaging convenience for operators and
    orchestrators.  Internal consumers should use the smallest relevant
    sibling view rather than the full facade.

    Parameters
    ----------
    execution_view:
        Required — the plan execution view with task authority, run identity,
        and run revision.
    runner_view:
        Optional runner liveness view.
    publication_view:
        Optional publication readiness view.
    human_gate_view:
        Optional human-gate observation view.
    recovery_view:
        Optional recovery/repair custody view.
    """

    run_id = execution_view.run_id
    run_revision = execution_view.run_revision

    source_paths: set[str] = set()
    for task in execution_view.tasks:
        source_paths.update(task.source_paths)

    empty_view: dict[str, Any] = {}

    runner_dict = runner_view.to_dict() if runner_view is not None else empty_view
    publication_dict = publication_view.to_dict() if publication_view is not None else empty_view
    human_gate_dict = human_gate_view.to_dict() if human_gate_view is not None else empty_view
    recovery_dict = recovery_view.to_dict() if recovery_view is not None else empty_view

    for view in (runner_view, publication_view, human_gate_view, recovery_view):
        if view is not None:
            source_paths.update(view.source_paths)

    values = {
        "schema_version": 1,
        "run_id": run_id,
        "run_revision": run_revision,
        "execution": execution_view.to_dict(),
        "runner": runner_dict,
        "publication": publication_dict,
        "human_gate": human_gate_dict,
        "recovery": recovery_dict,
        "source_paths": tuple(sorted(source_paths)),
    }
    unsigned = MegaplanPlanView(**values, view_hash="pending")
    digest = hashlib.sha256(
        canonical_json(unsigned._payload()).encode("utf-8")
    ).hexdigest()
    return MegaplanPlanView(**values, view_hash=digest)


__all__ = [
    "AcceptedTaskAttempt",
    "HumanGateDiagnostic",
    "HumanGateObservation",
    "HumanGateView",
    "LegacyTaskLabel",
    "MegaplanPlanView",
    "MegaplanRecoveryView",
    "PermittedAction",
    "PlanExecutionDiagnostic",
    "PlanExecutionView",
    "PublicationDiagnostic",
    "PublicationObservation",
    "PublicationView",
    "RecoveryCustodyObservation",
    "RecoveryDiagnostic",
    "RunnerDiagnostic",
    "RunnerObservation",
    "RunnerView",
    "TaskExecutionState",
    "derive_human_gate_view",
    "derive_megaplan_plan_view",
    "derive_megaplan_recovery_view",
    "derive_plan_execution_view",
    "derive_publication_view",
    "derive_runner_view",
]
