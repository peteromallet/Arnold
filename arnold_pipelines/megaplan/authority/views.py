"""Deterministic, read-only Megaplan authority shadow views."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Iterable, Mapping

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
class TaskExecutionState:
    task_id: str
    depends_on: tuple[str, ...]
    accepted: bool
    authority_status: str
    accepted_decision_ids: tuple[str, ...]
    unresolved_claim_ids: tuple[str, ...]
    legacy_labels: tuple[LegacyTaskLabel, ...]
    source_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "depends_on": list(self.depends_on),
            "accepted": self.accepted,
            "authority_status": self.authority_status,
            "accepted_decision_ids": list(self.accepted_decision_ids),
            "unresolved_claim_ids": list(self.unresolved_claim_ids),
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

    if any(item.state == "contradicted" for item in normalized):
        status = "contradicted"
    elif any(by_field[field].value is True for field in ("dirty_workspace", "no_push")) or by_field["auth"].value is False:
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


def derive_plan_execution_view(
    authority: RunAuthorityView,
    plan: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    *,
    evidence_decisions: Mapping[str, Any],
    legacy_labels: Iterable[LegacyTaskLabel] = (),
    plan_source: str = "finalize.json",
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

    claims_by_id = {claim.claim_id: claim for claim in authority.claims}
    completion_claims = {
        claim.claim_id: claim
        for claim in authority.claims
        if claim.claim_type == TASK_COMPLETION_CLAIM and claim.subject_id in task_by_id
    }
    accepted_by_task: dict[str, list[Any]] = {task_id: [] for task_id in task_by_id}
    resolved_claim_ids: set[str] = set()
    for decision in authority.decisions:
        claim = claims_by_id.get(decision.claim_id)
        if claim is None or claim.claim_id not in completion_claims:
            continue
        resolved_claim_ids.add(claim.claim_id)
        policy_decision = evidence_decisions.get(claim.subject_id)
        if decision.outcome == "accepted" and _decision_authoritative(policy_decision):
            accepted_by_task[claim.subject_id].append(decision)
        elif decision.outcome == "accepted":
            diagnostics.append(PlanExecutionDiagnostic(
                "kernel_policy_disagreement", claim.subject_id,
                "kernel accepted the claim but Megaplan evidence policy did not", 
                f"contract://decision/{decision.decision_id}",
            ))

    unresolved = sorted(set(completion_claims) - resolved_claim_ids)
    task_states: list[TaskExecutionState] = []
    for task_id, task in sorted(task_by_id.items()):
        accepted_decisions = sorted(item.decision_id for item in accepted_by_task[task_id])
        task_unresolved = sorted(
            claim_id for claim_id in unresolved if completion_claims[claim_id].subject_id == task_id
        )
        task_labels = tuple(labels_by_task[task_id])
        accepted = bool(accepted_decisions)
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
        depends_on = tuple(sorted({str(item) for item in task.get("depends_on", ()) if str(item)}))
        task_states.append(TaskExecutionState(
            task_id=task_id,
            depends_on=depends_on,
            accepted=accepted,
            authority_status="accepted" if accepted else "unaccepted",
            accepted_decision_ids=tuple(accepted_decisions),
            unresolved_claim_ids=tuple(task_unresolved),
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
        "unresolved_claim_ids": tuple(unresolved),
        "quarantine_ids": tuple(sorted(item.quarantine_id for item in authority.quarantines)),
        "diagnostics": tuple(sorted(set(diagnostics))),
    }
    unsigned = PlanExecutionView(**values, view_hash="pending")
    digest = hashlib.sha256(canonical_json(unsigned._payload()).encode("utf-8")).hexdigest()
    return PlanExecutionView(**values, view_hash=digest)


__all__ = [
    "LegacyTaskLabel",
    "PlanExecutionDiagnostic",
    "PlanExecutionView",
    "PublicationDiagnostic",
    "PublicationObservation",
    "PublicationView",
    "RunnerDiagnostic",
    "RunnerObservation",
    "RunnerView",
    "TaskExecutionState",
    "derive_plan_execution_view",
    "derive_publication_view",
    "derive_runner_view",
]
