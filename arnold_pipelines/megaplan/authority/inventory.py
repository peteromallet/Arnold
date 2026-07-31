"""Read-only inventory of Megaplan authority-relevant inputs.

The inventory is deliberately diagnostic.  It reports claims, observations,
decisions, and projections without promoting any of them to execution
authority.  Collection reads each configured source once, reduces only the
captured values, and produces a canonical JSON representation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from arnold_pipelines.megaplan._core.io import list_batch_artifacts
from arnold_pipelines.megaplan.authority.batch_scope import resolve_batch_scope
from arnold_pipelines.megaplan.chain.spec import _state_path_candidates_for
from arnold_pipelines.megaplan.cloud.current_target import resolve_current_target
from arnold_pipelines.megaplan.observability.fold import fold_events
from arnold_pipelines.megaplan.run_state.evidence import normalize_evidence
from arnold_pipelines.megaplan.store.plan_repository import PlanRepository


INVENTORY_SCHEMA_VERSION = 1
_ROLES = frozenset({"observation", "claim", "decision", "projection"})
_PRESENCE = frozenset(
    {"not_configured", "absent", "present_empty", "present", "degraded", "contradictory", "shadow_only"}
)
_S4_RE = re.compile(r"execute_batches/batch_(\d+)/tasks_([0-9a-f]{12})\.json$")
_LEGACY_RE = re.compile(r"execution_batch_(\d+)\.json$")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return _sha256(data)


@dataclass(frozen=True, slots=True)
class InventoryContradiction:
    """A disagreement found solely from already captured source values."""

    code: str
    reason: str
    source_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_paths", tuple(sorted(set(self.source_paths))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "reason": self.reason,
            "source_paths": list(self.source_paths),
        }


@dataclass(frozen=True, slots=True)
class InventoryRecord:
    """Stable diagnostic record for one source class or concrete source."""

    category: str
    source_class: str
    role: str
    reader: str
    path: str
    identity: Mapping[str, Any]
    revision: Mapping[str, Any]
    freshness: Mapping[str, Any]
    presence: str
    reason: str = ""
    contradictions: tuple[InventoryContradiction, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.role not in _ROLES:
            raise ValueError(f"unknown inventory role: {self.role}")
        if self.presence not in _PRESENCE:
            raise ValueError(f"unknown inventory presence: {self.presence}")
        object.__setattr__(self, "identity", _freeze(self.identity))
        object.__setattr__(self, "revision", _freeze(self.revision))
        object.__setattr__(self, "freshness", _freeze(self.freshness))
        object.__setattr__(self, "details", _freeze(self.details))
        object.__setattr__(
            self,
            "contradictions",
            tuple(sorted(self.contradictions, key=lambda item: (item.code, item.source_paths))),
        )

    @property
    def registry_key(self) -> tuple[str, str, str]:
        return (self.category, self.source_class, self.path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "source_class": self.source_class,
            "role": self.role,
            "reader": self.reader,
            "path": self.path,
            "identity": _thaw(self.identity),
            "revision": _thaw(self.revision),
            "freshness": _thaw(self.freshness),
            "presence": self.presence,
            "reason": self.reason,
            "contradictions": [item.to_dict() for item in self.contradictions],
            "details": _thaw(self.details),
        }


@dataclass(frozen=True, slots=True)
class AuthorityInventory:
    """Canonical inventory payload."""

    records: tuple[InventoryRecord, ...]
    schema_version: int = INVENTORY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.records, key=lambda record: record.registry_key))
        keys = [record.registry_key for record in ordered]
        if len(keys) != len(set(keys)):
            raise ValueError("inventory records must have unique registry keys")
        object.__setattr__(self, "records", ordered)

    @property
    def contradictions(self) -> tuple[InventoryContradiction, ...]:
        unique: dict[tuple[str, tuple[str, ...]], InventoryContradiction] = {}
        for record in self.records:
            for item in record.contradictions:
                unique[(item.code, item.source_paths)] = item
        return tuple(unique[key] for key in sorted(unique))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "records": [record.to_dict() for record in self.records],
            "contradictions": [item.to_dict() for item in self.contradictions],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @property
    def fingerprint(self) -> str:
        return _sha256(self.to_json().encode())


@dataclass(frozen=True, slots=True)
class InventoryConfig:
    """Explicit configuration for optional inventory sources."""

    plan_dir: Path
    chain_spec_path: Path | None = None
    session: str | None = None
    marker_dir: Path | None = None
    repair_data_dir: Path | None = None
    store: object | None = None
    collection_time: str | None = None


@dataclass(frozen=True, slots=True)
class _SourceSpec:
    category: str
    source_class: str
    role: str
    reader: str


# This is the audited T5 registry.  Parent records are never removed merely
# because a directory, backend, command, credential, or optional input is absent.
SOURCE_REGISTRY: tuple[_SourceSpec, ...] = (
    _SourceSpec("execute", "state", "projection", "PlanRepository.read_artifact_json"),
    _SourceSpec("execute", "finalize", "projection", "PlanRepository.read_artifact_json/describe_artifact"),
    _SourceSpec("execute", "s4_batch_artifacts", "claim", "list_batch_artifacts/PlanRepository.describe_artifact"),
    _SourceSpec("execute", "legacy_batch_artifacts", "claim", "list_batch_artifacts"),
    _SourceSpec("execute", "execution_auxiliary", "projection", "PlanRepository.list_artifacts/read_artifact_json"),
    _SourceSpec("execute", "completion_verdict", "decision", "read_typed_completion_verdict"),
    _SourceSpec("repository", "plan_tree", "observation", "PlanRepository.list_artifact_paths/list_artifacts"),
    _SourceSpec("store", "file_epic_events", "claim", "Store.list_epic_events_for_replay"),
    _SourceSpec("store", "db_epic_events", "claim", "Store.list_epic_events_for_replay"),
    _SourceSpec("store", "telemetry_progress", "observation", "Store.events_for_plan/list_progress_events"),
    _SourceSpec("compatibility", "store_adapter", "projection", "ArnoldStoreAdapter"),
    _SourceSpec("authority", "evidence_nucleus", "claim", "load_evidence_nucleus/authority_decision_for_task"),
    _SourceSpec("authority", "completion_projection", "projection", "authority_decision_for_task/is_task_satisfied"),
    _SourceSpec("chain", "spec", "claim", "chain.spec.load_spec"),
    _SourceSpec("chain", "state_candidates", "projection", "chain.spec._state_path_candidates_for"),
    _SourceSpec("chain", "legacy_state", "projection", "chain.spec._state_path_candidates_for"),
    _SourceSpec("chain", "status", "projection", "build_chain_status_snapshot"),
    _SourceSpec("cloud", "session_marker", "claim", "resolve_current_target/is_canonical_session_marker_path"),
    _SourceSpec("cloud", "current_target", "projection", "resolve_current_target/normalize_evidence"),
    _SourceSpec("cloud", "status_snapshot", "projection", "load_cloud_status_snapshot"),
    _SourceSpec("cloud", "health_sidecars", "projection", "build_cloud_status_snapshot"),
    _SourceSpec("watchdog", "live_snapshot", "projection", "watchdog.snapshot.build_snapshot"),
    _SourceSpec("watchdog", "persisted_report", "projection", "cloud.status_snapshot._load_watchdog_report"),
    _SourceSpec("watchdog", "registry", "projection", "WatchdogRegistry.load semantics (read-only)"),
    _SourceSpec("repair", "needs_human", "claim", "resolve_current_target/classify_needs_human_blocker"),
    _SourceSpec("repair", "data_index_attempts", "projection", "repair_contract.load_json/read_repair_index"),
    _SourceSpec("repair", "queue_requests", "claim", "iter_repair_requests(include_malformed=True)"),
    _SourceSpec("repair", "queue_decisions", "decision", "iter_repair_decisions(include_malformed=True)"),
    _SourceSpec("repair", "jsonl_sidecars", "claim", "repair_contract.read_jsonl_records"),
    _SourceSpec("git", "worktree", "observation", "repair_recurrence._probe_git_progress"),
    _SourceSpec("git", "chain_publication", "projection", "captured chain state fields"),
    _SourceSpec("git", "github_pr", "observation", "repair_recurrence._probe_pr_state"),
    _SourceSpec("process", "processes", "observation", "watchdog.processes.scan_processes"),
    _SourceSpec("session", "tmux", "observation", "default_liveness_probe/TmuxSession.exists"),
    _SourceSpec("run_state", "active_step_heartbeat", "observation", "resolve_current_target"),
    _SourceSpec("run_state", "normalization", "projection", "run_state.evidence.normalize_evidence"),
    _SourceSpec("run_state", "resolution", "decision", "run_state.resolver.resolve_run_state"),
    _SourceSpec("events", "plan_events", "observation", "events schema-compatible read-only parser"),
    _SourceSpec("wal", "shadow_state_fold", "projection", "observability.fold.fold_events"),
    _SourceSpec("events", "store_projection", "projection", "events_projection.project_events"),
    _SourceSpec("journal", "transactions", "decision", "_core.io journal path helpers/read-only JSON"),
    _SourceSpec("backend", "event_sourced_state_store", "decision", "EventSourcedStateStoreBackend"),
)

# ── Net-new Custody-owned source classes (M7 shadow-only, per SD1) ─────────────
# These 11 entries are registry additions and never reassign existing
# Run Authority (38) or WBC (5) ownership rows.
CUSTODY_SOURCE_REGISTRY: tuple[_SourceSpec, ...] = (
    _SourceSpec("custody", "writer_map", "projection", "custody.writer_map.generate_writer_map"),
    _SourceSpec("custody", "contracts", "claim", "custody.contracts (T3)"),
    _SourceSpec("custody", "lease_store", "decision", "custody.lease_store (T5)"),
    _SourceSpec("custody", "outbox", "projection", "custody.outbox (T7)"),
    _SourceSpec("custody", "action_validator", "decision", "custody.action_validator.validate_action_boundary (T8)"),
    _SourceSpec("custody", "projections", "projection", "custody.projections (T16)"),
    _SourceSpec("custody", "controlled_writer_registry", "decision", "custody.controlled_writer_registry (T10)"),
    _SourceSpec("custody", "receipts", "projection", "custody.receipts (T18)"),
    _SourceSpec("custody", "compatibility", "projection", "custody.compatibility (T20)"),
    _SourceSpec("custody", "canary", "observation", "custody.canary (T21)"),
    _SourceSpec("custody", "bypass_proof", "decision", "custody.bypass_proof (T22)"),
)

# ── Authority-increasing writer dispositions ───────────────────────────────────
# Maps (category, source_class) → (owner, enforcement) for every writer
# classified as authority-increasing in the M7 provenance map.  The invariant
# requires every such writer to be prerequisite-owned, Custody-gated,
# deferred shadow-only, or retired.
_AUTHORITY_INCREASING_DISPOSITIONS: Mapping[tuple[str, str], tuple[str, str]] = MappingProxyType({
    # Run Authority authority-increasing (deferred shadow-only in M7)
    ("execute", "completion_verdict"): ("Run Authority", "shadow_only"),
    ("repair", "queue_decisions"): ("Run Authority", "shadow_only"),
    ("run_state", "resolution"): ("Run Authority", "shadow_only"),
    # Custody authority-increasing (Custody-gated, deferred shadow-only in M7)
    ("custody", "lease_store"): ("Custody", "shadow_only"),
    ("custody", "action_validator"): ("Custody", "shadow_only"),
    ("custody", "controlled_writer_registry"): ("Custody", "shadow_only"),
    ("custody", "bypass_proof"): ("Custody", "shadow_only"),
})


def validate_authority_increasing_writers_invariant(
    source_registry: Iterable[_SourceSpec] = (),
    custody_registry: Iterable[_SourceSpec] = (),
) -> tuple[InventoryContradiction, ...]:
    """Validate that every authority-increasing writer has an allowed disposition.

    Returns contradictions for any writer that is authority-increasing but
    not prerequisite-owned, Custody-gated, deferred shadow-only, or retired.
    """
    contradictions: list[InventoryContradiction] = []

    for spec in (*source_registry, *custody_registry):
        key = (spec.category, spec.source_class)
        disposition = _AUTHORITY_INCREASING_DISPOSITIONS.get(key)
        if disposition is None:
            continue  # not classified as authority-increasing
        owner, enforcement = disposition
        # Every authority-increasing writer must be:
        #   - prerequisite-owned (Run Authority or WBC)
        #   - Custody-gated (owner == Custody)
        #   - deferred shadow-only (enforcement == "shadow_only")
        #   - retired (enforcement == "retired")
        allowed = (
            owner in ("Run Authority", "WBC")
            or owner == "Custody"
            or enforcement == "shadow_only"
            or enforcement == "retired"
        )
        if not allowed:
            contradictions.append(
                InventoryContradiction(
                    "authority_increasing_writer_not_allowed",
                    f"Writer ({spec.category}/{spec.source_class}) is authority-increasing "
                    f"with owner={owner!r}, enforcement={enforcement!r} — "
                    f"must be prerequisite-owned, Custody-gated, deferred shadow-only, or retired",
                    (spec.category + "/" + spec.source_class,),
                )
            )

    return tuple(contradictions)


def _record(
    spec: _SourceSpec,
    path: str,
    *,
    presence: str = "not_configured",
    reason: str = "source is not configured",
    identity: Mapping[str, Any] | None = None,
    revision: Mapping[str, Any] | None = None,
    freshness: Mapping[str, Any] | None = None,
    contradictions: Sequence[InventoryContradiction] = (),
    details: Mapping[str, Any] | None = None,
) -> InventoryRecord:
    return InventoryRecord(
        category=spec.category,
        source_class=spec.source_class,
        role=spec.role,
        reader=spec.reader,
        path=path,
        identity=identity or {},
        revision=revision or {},
        freshness=freshness or {},
        presence=presence,
        reason=reason,
        contradictions=tuple(contradictions),
        details=details or {},
    )


def _stat(path: Path) -> dict[str, Any]:
    try:
        return {"mtime_ns": path.stat().st_mtime_ns}
    except OSError:
        return {}


def _capture_json(repo: PlanRepository, relative: str) -> tuple[Any | None, bytes | None, str]:
    """Read through the repository seam without activating envelope telemetry."""

    try:
        data = repo.read_artifact_bytes(relative)
    except OSError as exc:
        return None, None, f"unreadable: {type(exc).__name__}: {exc}"
    if data is None:
        return None, None, "missing"
    try:
        return json.loads(data), data, ""
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, data, f"invalid_json: {type(exc).__name__}: {exc}"


def _artifact_record(
    spec: _SourceSpec,
    repo: PlanRepository,
    relative: str,
    *,
    expected_object: bool = True,
) -> tuple[InventoryRecord, Any | None]:
    path = repo.plan_dir / relative
    value, data, error = _capture_json(repo, relative)
    if data is None:
        return _record(spec, str(path), presence="absent", reason=error), value
    identity: dict[str, Any] = {"sha256": _sha256(data)}
    try:
        artifact = repo.describe_artifact(relative)
    except (ValueError, FileNotFoundError):
        artifact = None
    if artifact is not None:
        identity.update({"artifact_name": artifact.name, "role": artifact.role})
    if error or (expected_object and not isinstance(value, dict)):
        reason = error or "payload is not a JSON object"
        return _record(
            spec,
            str(path),
            presence="degraded",
            reason=reason,
            identity=identity,
            freshness=_stat(path),
        ), value
    return _record(
        spec,
        str(path),
        presence="present",
        reason="",
        identity=identity,
        freshness=_stat(path),
    ), value


def _known_subjects(finalize: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not isinstance(finalize, Mapping):
        return (), ()
    tasks = tuple(
        sorted(
            item["id"]
            for item in finalize.get("tasks", ())
            if isinstance(item, Mapping) and isinstance(item.get("id"), str)
        )
    )
    checks = tuple(
        sorted(
            item["id"]
            for item in finalize.get("sense_checks", ())
            if isinstance(item, Mapping) and isinstance(item.get("id"), str)
        )
    )
    return tasks, checks


def _read_existing_events(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return [], [f"unreadable: {type(exc).__name__}: {exc}"]
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: {exc.msg}")
            continue
        if not isinstance(value, dict):
            errors.append(f"line {line_number}: event is not an object")
            continue
        events.append(value)
    return events, errors


def _source(specs: Mapping[tuple[str, str], _SourceSpec], category: str, source_class: str) -> _SourceSpec:
    return specs[(category, source_class)]


def collect_authority_inventory(
    plan_dir_or_config: str | Path | InventoryConfig,
    *,
    chain_spec_path: str | Path | None = None,
    session: str | None = None,
    marker_dir: str | Path | None = None,
    repair_data_dir: str | Path | None = None,
    store: object | None = None,
    collection_time: str | None = None,
) -> AuthorityInventory:
    """Collect a deterministic, read-only inventory for one plan directory."""

    if isinstance(plan_dir_or_config, InventoryConfig):
        config = plan_dir_or_config
    else:
        config = InventoryConfig(
            plan_dir=Path(plan_dir_or_config),
            chain_spec_path=Path(chain_spec_path) if chain_spec_path is not None else None,
            session=session,
            marker_dir=Path(marker_dir) if marker_dir is not None else None,
            repair_data_dir=Path(repair_data_dir) if repair_data_dir is not None else None,
            store=store,
            collection_time=collection_time,
        )
    plan_dir = Path(config.plan_dir)
    specs = {(item.category, item.source_class): item for item in SOURCE_REGISTRY}
    parents: dict[tuple[str, str], InventoryRecord] = {
        key: _record(item, "", reason="source is not configured") for key, item in specs.items()
    }
    children: list[InventoryRecord] = []

    # Repository and core execute artifacts.  Bind without a Store: passing one
    # can materialize events.ndjson through the compatibility projection.
    repo = PlanRepository.from_artifact_dir(plan_dir)
    tree_spec = _source(specs, "repository", "plan_tree")
    if not plan_dir.is_dir():
        parents[("repository", "plan_tree")] = _record(
            tree_spec, str(plan_dir), presence="absent", reason="plan directory is missing"
        )
        artifact_paths: list[Path] = []
        typed_artifacts: list[Any] = []
    else:
        artifact_paths = repo.list_artifact_paths()
        typed_artifacts = repo.list_artifacts()
        parents[("repository", "plan_tree")] = _record(
            tree_spec,
            str(plan_dir),
            presence="present" if artifact_paths else "present_empty",
            reason="" if artifact_paths else "plan directory contains no artifacts",
            identity={"plan_directory": plan_dir.name},
            revision={"typed_artifacts": len(typed_artifacts)},
            freshness={"artifact_mtime_ns": [_stat(path).get("mtime_ns") for path in artifact_paths]},
            details={"artifact_paths": [path.relative_to(plan_dir).as_posix() for path in artifact_paths]},
        )

    state_spec = _source(specs, "execute", "state")
    state_record, state = _artifact_record(state_spec, repo, "state.json")
    state_contradictions: list[InventoryContradiction] = []
    if isinstance(state, Mapping) and state.get("name") not in (None, plan_dir.name):
        state_contradictions.append(
            InventoryContradiction(
                "state_plan_identity_mismatch",
                f"state name {state.get('name')!r} differs from plan directory {plan_dir.name!r}",
                (str(plan_dir / "state.json"), str(plan_dir)),
            )
        )
    state_revision = {}
    state_freshness = dict(_thaw(state_record.freshness))
    if isinstance(state, Mapping):
        state_revision = {
            key: state.get(key) for key in ("schema_version", "iteration") if key in state
        }
        for key in ("created_at",):
            if key in state:
                state_freshness[key] = state[key]
    state_record = replace(
        state_record,
        identity={**_thaw(state_record.identity), "plan_name": state.get("name") if isinstance(state, Mapping) else None},
        revision=state_revision,
        freshness=state_freshness,
        presence="contradictory" if state_contradictions else state_record.presence,
        reason=state_contradictions[0].reason if state_contradictions else state_record.reason,
        contradictions=tuple(state_contradictions),
    )
    parents[("execute", "state")] = state_record

    finalize_spec = _source(specs, "execute", "finalize")
    finalize_record, finalize = _artifact_record(finalize_spec, repo, "finalize.json")
    parents[("execute", "finalize")] = finalize_record
    known_tasks, known_checks = _known_subjects(finalize)

    completion_spec = _source(specs, "execute", "completion_verdict")
    completion_record, _completion = _artifact_record(completion_spec, repo, "completion_verdict.json")
    parents[("execute", "completion_verdict")] = completion_record

    auxiliary_spec = _source(specs, "execute", "execution_auxiliary")
    auxiliary_names = (
        "execution.json",
        "execution_audit.json",
        "execution_trace.jsonl",
    )
    auxiliary_present = 0
    for name in auxiliary_names:
        child, _ = _artifact_record(auxiliary_spec, repo, name, expected_object=name.endswith(".json"))
        child = replace(child, source_class=f"execution_auxiliary:{name}")
        children.append(child)
        auxiliary_present += child.presence in {"present", "degraded", "contradictory"}
    parents[("execute", "execution_auxiliary")] = _record(
        auxiliary_spec,
        str(plan_dir),
        presence="present" if auxiliary_present else "absent",
        reason="" if auxiliary_present else "no execution auxiliary artifacts exist",
        revision={"configured_classes": len(auxiliary_names)},
    )

    # Call the compatibility listing once, but enumerate every S4 sibling so a
    # duplicate batch claim cannot be hidden by its first-match behavior.
    selected_batches = list_batch_artifacts(plan_dir) if plan_dir.is_dir() else []
    selected = {str(path) for path in selected_batches}
    s4_paths = sorted(plan_dir.glob("execute_batches/batch_*/tasks_*.json")) if plan_dir.is_dir() else []
    legacy_paths = sorted(plan_dir.glob("execution_batch_*.json")) if plan_dir.is_dir() else []
    batch_claims: dict[int, list[tuple[Path, str, str]]] = {}
    s4_spec = _source(specs, "execute", "s4_batch_artifacts")
    for path in s4_paths:
        relative = path.relative_to(plan_dir).as_posix()
        child, payload = _artifact_record(s4_spec, repo, relative)
        match = _S4_RE.fullmatch(relative)
        contradictions: list[InventoryContradiction] = []
        scope_details: dict[str, Any] = {"selected_by_list_batch_artifacts": str(path) in selected}
        batch_number = int(match.group(1)) if match else -1
        digest = match.group(2) if match else ""
        if isinstance(payload, Mapping):
            resolution = resolve_batch_scope(
                payload,
                path,
                known_task_ids=known_tasks,
                known_sense_check_ids=known_checks,
            )
            if resolution.is_proven:
                assert resolution.scope is not None
                scope_details["batch_scope"] = resolution.scope.to_dict()
                batch_claims.setdefault(batch_number, []).append(
                    (path, resolution.scope.task_set_digest, _thaw(child.identity).get("sha256", ""))
                )
            else:
                assert resolution.quarantine is not None
                contradictions.append(
                    InventoryContradiction(
                        "invalid_batch_scope",
                        resolution.quarantine.message,
                        (str(path),),
                    )
                )
                scope_details["quarantine"] = resolution.quarantine.to_dict()
        child = replace(
            child,
            source_class=f"s4_batch_artifacts:{relative}",
            identity={**_thaw(child.identity), "batch_index": batch_number, "filename_task_digest": digest},
            revision={"batch_index": batch_number, "scope_schema_version": 1},
            details=scope_details,
            presence="contradictory" if contradictions else child.presence,
            reason=contradictions[0].reason if contradictions else child.reason,
            contradictions=tuple(contradictions),
        )
        children.append(child)
    parents[("execute", "s4_batch_artifacts")] = _record(
        s4_spec,
        str(plan_dir / "execute_batches"),
        presence="present" if s4_paths else "absent",
        reason="" if s4_paths else "no S4 batch artifacts exist",
        revision={"artifact_count": len(s4_paths), "selected_count": len([p for p in selected_batches if "execute_batches" in p.parts])},
    )

    legacy_spec = _source(specs, "execute", "legacy_batch_artifacts")
    for path in legacy_paths:
        relative = path.relative_to(plan_dir).as_posix()
        child, payload = _artifact_record(legacy_spec, repo, relative)
        contradiction = InventoryContradiction(
            "legacy_authority_identity_incomplete",
            "legacy input lacks durable batch scope, attempt, capability grant, coordinator fence, and evidence identity",
            (str(path),),
        )
        match = _LEGACY_RE.fullmatch(relative)
        children.append(
            replace(
                child,
                source_class=f"legacy_batch_artifacts:{relative}",
                identity={**_thaw(child.identity), "filename_batch_index": int(match.group(1)) if match else None},
                revision={"filename_batch_index": int(match.group(1)) if match else None},
                presence="contradictory",
                reason=contradiction.reason,
                contradictions=(contradiction,),
                details={"selected_by_list_batch_artifacts": str(path) in selected, "payload_is_object": isinstance(payload, Mapping)},
            )
        )
    parents[("execute", "legacy_batch_artifacts")] = _record(
        legacy_spec,
        str(plan_dir),
        presence="present" if legacy_paths else "absent",
        reason="legacy inputs are non-authoritative" if legacy_paths else "no legacy batch artifacts exist",
        revision={"artifact_count": len(legacy_paths)},
    )

    duplicate_contradictions: list[InventoryContradiction] = []
    for batch_number, claims in sorted(batch_claims.items()):
        identities = {(digest, payload_hash) for _, digest, payload_hash in claims}
        if len(claims) > 1 and len(identities) > 1:
            duplicate_contradictions.append(
                InventoryContradiction(
                    "duplicate_batch_claim",
                    f"batch {batch_number} has multiple S4 claims with different scope or payload hashes",
                    tuple(str(path) for path, _, _ in claims),
                )
            )
    if duplicate_contradictions:
        parents[("execute", "s4_batch_artifacts")] = replace(
            parents[("execute", "s4_batch_artifacts")],
            presence="contradictory",
            reason=duplicate_contradictions[0].reason,
            contradictions=tuple(duplicate_contradictions),
        )

    # Existing event stream: parse without read_events(), which may create it.
    events_spec = _source(specs, "events", "plan_events")
    events_path = plan_dir / "events.ndjson"
    events: list[dict[str, Any]] = []
    event_errors: list[str] = []
    event_contradictions: list[InventoryContradiction] = []
    if events_path.exists():
        events, event_errors = _read_existing_events(events_path)
        seqs = [event.get("seq") for event in events if isinstance(event.get("seq"), int)]
        if len(seqs) != len(set(seqs)):
            event_contradictions.append(
                InventoryContradiction("event_sequence_duplicate", "events contain duplicate sequence values", (str(events_path),))
            )
        if seqs != sorted(seqs):
            event_contradictions.append(
                InventoryContradiction("event_sequence_out_of_order", "event sequence differs from file order", (str(events_path),))
            )
        if seqs and sorted(seqs) != list(range(min(seqs), max(seqs) + 1)):
            event_contradictions.append(
                InventoryContradiction("event_sequence_gap", "event sequence contains a gap", (str(events_path),))
            )
        seq_sidecar = plan_dir / ".events.seq"
        if seq_sidecar.exists() and seqs:
            try:
                sidecar_seq = int(seq_sidecar.read_text(encoding="utf-8").strip())
            except (OSError, UnicodeDecodeError, ValueError):
                sidecar_seq = None
            if sidecar_seq != max(seqs):
                event_contradictions.append(
                    InventoryContradiction(
                        "event_sequence_sidecar_mismatch",
                        f".events.seq value {sidecar_seq!r} differs from maximum event sequence {max(seqs)}",
                        (str(events_path), str(seq_sidecar)),
                    )
                )
        parents[("events", "plan_events")] = _record(
            events_spec,
            str(events_path),
            presence="contradictory" if event_contradictions else ("degraded" if event_errors else ("present" if events else "present_empty")),
            reason=(event_contradictions[0].reason if event_contradictions else (event_errors[0] if event_errors else "")),
            identity={"sha256": _sha256(events_path.read_bytes())},
            revision={"event_count": len(events), "sequences": seqs},
            freshness=_stat(events_path),
            contradictions=event_contradictions,
            details={"parse_errors": event_errors},
        )
    else:
        parents[("events", "plan_events")] = _record(
            events_spec, str(events_path), presence="absent", reason="events stream is absent"
        )

    wal_spec = _source(specs, "wal", "shadow_state_fold")
    folded = fold_events(events)
    wal_contradictions: list[InventoryContradiction] = []
    if folded and isinstance(state, Mapping) and dict(state) != folded:
        wal_contradictions.append(
            InventoryContradiction(
                "wal_state_mismatch",
                "last state_written event differs from state.json",
                (str(events_path), str(plan_dir / "state.json")),
            )
        )
    parents[("wal", "shadow_state_fold")] = _record(
        wal_spec,
        str(events_path),
        presence="contradictory" if wal_contradictions else ("present" if folded else "absent"),
        reason=wal_contradictions[0].reason if wal_contradictions else ("" if folded else "no state_written snapshot exists"),
        identity={"fold_sha256": _canonical_hash(folded)} if folded else {},
        revision={"last_state_written_seq": max((event.get("seq", -1) for event in events if event.get("kind") == "state_written"), default=None)},
        freshness=_stat(events_path),
        contradictions=wal_contradictions,
    )

    # Chain candidates are read directly; load_chain_state is intentionally not
    # used because its compatibility normalization can save migrated state.
    chain_spec_spec = _source(specs, "chain", "spec")
    chain_state_spec = _source(specs, "chain", "state_candidates")
    legacy_state_spec = _source(specs, "chain", "legacy_state")
    if config.chain_spec_path is None:
        parents[("chain", "spec")] = _record(chain_spec_spec, "", reason="chain spec path is not configured")
        parents[("chain", "state_candidates")] = _record(chain_state_spec, "", reason="chain spec path is not configured")
        parents[("chain", "legacy_state")] = _record(legacy_state_spec, "", reason="chain spec path is not configured")
    else:
        spec_path = Path(config.chain_spec_path)
        if spec_path.exists():
            try:
                spec_data = spec_path.read_bytes()
                spec_presence, spec_reason = "present", ""
            except OSError as exc:
                spec_data = b""
                spec_presence, spec_reason = "degraded", f"unreadable: {exc}"
        else:
            spec_data = b""
            spec_presence, spec_reason = "absent", "configured chain spec is missing"
        parents[("chain", "spec")] = _record(
            chain_spec_spec,
            str(spec_path),
            presence=spec_presence,
            reason=spec_reason,
            identity={"sha256": _sha256(spec_data)} if spec_data else {},
            freshness=_stat(spec_path),
        )
        candidates = _state_path_candidates_for(spec_path)
        candidate_payloads: list[tuple[Path, Any, str]] = []
        for index, path in enumerate(candidates):
            try:
                data = path.read_bytes() if path.exists() else None
                payload = json.loads(data) if data is not None else None
                error = "" if isinstance(payload, dict) else ("missing" if data is None else "payload is not an object")
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                data, payload, error = None, None, f"unreadable: {type(exc).__name__}: {exc}"
            candidate_payloads.append((path, payload, error))
            children.append(
                _record(
                    chain_state_spec,
                    str(path),
                    presence="present" if isinstance(payload, dict) else ("absent" if error == "missing" else "degraded"),
                    reason=error,
                    identity={"sha256": _sha256(data)} if data is not None else {},
                    revision={key: payload.get(key) for key in ("schema_version", "current_milestone_index") if isinstance(payload, dict) and key in payload},
                    freshness=_stat(path),
                    details={"candidate_index": index},
                )
            )
        present_candidates = [(path, payload) for path, payload, _ in candidate_payloads if isinstance(payload, dict)]
        chain_contradictions: list[InventoryContradiction] = []
        identities = {_canonical_hash(payload) for _, payload in present_candidates}
        if len(identities) > 1:
            chain_contradictions.append(
                InventoryContradiction(
                    "chain_state_candidates_disagree",
                    "canonical, resolved-alias, or legacy chain states differ",
                    tuple(str(path) for path, _ in present_candidates),
                )
            )
        parents[("chain", "state_candidates")] = _record(
            chain_state_spec,
            str(spec_path),
            presence="contradictory" if chain_contradictions else ("present" if present_candidates else "absent"),
            reason=chain_contradictions[0].reason if chain_contradictions else ("" if present_candidates else "all configured chain state candidates are absent"),
            revision={"candidate_count": len(candidates), "present_count": len(present_candidates)},
            contradictions=chain_contradictions,
        )
        legacy_path = candidates[-1]
        legacy_payload = next((payload for path, payload, _ in candidate_payloads if path == legacy_path), None)
        parents[("chain", "legacy_state")] = _record(
            legacy_state_spec,
            str(legacy_path),
            presence="present" if isinstance(legacy_payload, dict) else "absent",
            reason="" if isinstance(legacy_payload, dict) else "legacy chain state is absent",
            freshness=_stat(legacy_path),
        )

    # Optional cloud target.  Resolve once, normalize that captured mapping once,
    # and project all related parent records from those values.
    cloud_keys = (
        ("cloud", "session_marker"), ("cloud", "current_target"),
        ("repair", "needs_human"), ("run_state", "active_step_heartbeat"),
        ("run_state", "normalization"),
    )
    if not config.session or config.marker_dir is None:
        for key in cloud_keys:
            parents[key] = _record(specs[key], "", reason="session and marker directory are not configured")
    else:
        marker_root = Path(config.marker_dir)
        raw_target = resolve_current_target(
            config.session,
            marker_dir=marker_root,
            repair_data_dir=config.repair_data_dir,
        )
        normalized = normalize_evidence(raw_target)
        marker_path = marker_root / f"{config.session}.json"
        marker = raw_target.get("marker") if isinstance(raw_target.get("marker"), Mapping) else {}
        disabled = raw_target.get("authoritative_source") == "resolver_observe_disabled"
        parents[("cloud", "session_marker")] = _record(
            specs[("cloud", "session_marker")],
            str(marker_path),
            presence="degraded" if disabled else ("present" if marker_path.exists() and marker else "absent"),
            reason="resolver observe is disabled" if disabled else ("" if marker_path.exists() and marker else "canonical session marker is absent or unreadable"),
            identity={key: marker.get(key) for key in ("session", "workspace", "run_kind", "remote_spec", "plan_name", "pid") if key in marker},
            freshness={**_stat(marker_path), **{key: marker.get(key) for key in ("started_at", "updated_at") if key in marker}},
        )
        parents[("cloud", "current_target")] = _record(
            specs[("cloud", "current_target")],
            str(marker_path),
            presence="degraded" if disabled else "present",
            reason="resolver observe is disabled" if disabled else "",
            identity={key: raw_target.get(key) for key in ("target_id", "target_session", "schema_version")},
            revision={"event_cursors": raw_target.get("event_cursors", {})},
            freshness={"collection_time": config.collection_time, "stale_evidence": raw_target.get("stale_evidence", [])},
            details={"authoritative_source": raw_target.get("authoritative_source")},
        )
        needs_human = raw_target.get("needs_human") if isinstance(raw_target.get("needs_human"), Mapping) else {}
        needs_path = (Path(config.repair_data_dir) if config.repair_data_dir else marker_root / "repair-data") / f"{config.session}.needs-human.json"
        parents[("repair", "needs_human")] = _record(
            specs[("repair", "needs_human")],
            str(needs_path),
            presence="present" if needs_human else "absent",
            reason="" if needs_human else "needs-human marker is absent",
            identity={key: needs_human.get(key) for key in ("session", "plan_name", "blocker_fingerprint") if key in needs_human},
            freshness={**_stat(needs_path), **{key: needs_human.get(key) for key in ("recorded_at",) if key in needs_human}},
        )
        heartbeat = raw_target.get("active_step_heartbeat") if isinstance(raw_target.get("active_step_heartbeat"), Mapping) else {}
        parents[("run_state", "active_step_heartbeat")] = _record(
            specs[("run_state", "active_step_heartbeat")],
            str(plan_dir / "state.json"),
            presence="present" if heartbeat else "absent",
            reason="" if heartbeat else "active step heartbeat is absent",
            identity={key: heartbeat.get(key) for key in ("run_id", "session_id", "worker_pid", "phase") if key in heartbeat},
            revision={"attempt": heartbeat.get("attempt")},
            freshness={key: heartbeat.get(key) for key in ("started_at", "last_activity_at") if key in heartbeat},
        )
        parents[("run_state", "normalization")] = _record(
            specs[("run_state", "normalization")],
            str(marker_path),
            presence="degraded" if disabled else "present",
            reason="resolver observe is disabled" if disabled else "",
            identity={"target_id": raw_target.get("target_id")},
            revision={"schema_version": raw_target.get("schema_version")},
            freshness={"collection_time": config.collection_time},
            details={"normalized_type": type(normalized).__name__},
        )

    # Store readers are part of the existing read-only contract.  Capture each
    # stream once and retain failures as degraded evidence instead of silently
    # falling back to filesystem authority.
    store_keys = (("store", "file_epic_events"), ("store", "db_epic_events"), ("store", "telemetry_progress"), ("compatibility", "store_adapter"), ("events", "store_projection"))
    if config.store is None:
        for key in store_keys:
            parents[key] = _record(specs[key], "", reason="Store backend is not configured")
    else:
        backend_type = f"{type(config.store).__module__}.{type(config.store).__qualname__}"
        backend_lower = backend_type.lower()
        try:
            epic_events = list(config.store.list_epic_events_for_replay(plan_dir.name))
            epic_error = ""
        except Exception as exc:  # backend/network failures are diagnostic evidence
            epic_events = []
            epic_error = f"collector failed: {type(exc).__name__}: {exc}"
        try:
            telemetry_events = list(config.store.events_for_plan(plan_dir.name))
            progress_events = list(config.store.list_progress_events(plan_id=plan_dir.name))
            telemetry_error = ""
        except Exception as exc:  # preserve unavailable backend explicitly
            telemetry_events, progress_events = [], []
            telemetry_error = f"collector failed: {type(exc).__name__}: {exc}"
        configured_store_keys = []
        if "multi" in backend_lower:
            configured_store_keys = [("store", "file_epic_events"), ("store", "db_epic_events")]
        elif any(token in backend_lower for token in ("db", "postgres", "sql")):
            configured_store_keys = [("store", "db_epic_events")]
        else:
            configured_store_keys = [("store", "file_epic_events")]
        for key in (("store", "file_epic_events"), ("store", "db_epic_events")):
            if key not in configured_store_keys:
                parents[key] = _record(specs[key], backend_type, reason="this Store backend class is not configured")
                continue
            parents[key] = _record(
                specs[key],
                backend_type,
                presence="degraded" if epic_error else ("present" if epic_events else "present_empty"),
                reason=epic_error,
                identity={"backend_type": backend_type, "event_ids": sorted(str(getattr(event, "id", "")) for event in epic_events)},
                revision={"event_count": len(epic_events)},
                freshness={"collection_time": config.collection_time},
            )
        parents[("store", "telemetry_progress")] = _record(
            specs[("store", "telemetry_progress")],
            backend_type,
            presence="degraded" if telemetry_error else ("present" if telemetry_events or progress_events else "present_empty"),
            reason=telemetry_error,
            identity={
                "backend_type": backend_type,
                "event_ids": sorted(str(getattr(event, "id", "")) for event in telemetry_events),
                "progress_ids": sorted(str(getattr(event, "id", "")) for event in progress_events),
            },
            revision={"event_count": len(telemetry_events), "progress_count": len(progress_events)},
            freshness={"collection_time": config.collection_time},
        )
        parents[("compatibility", "store_adapter")] = _record(
            specs[("compatibility", "store_adapter")], backend_type, presence="present", reason="",
            identity={"backend_type": backend_type}, freshness={"collection_time": config.collection_time},
        )
        parents[("events", "store_projection")] = _record(
            specs[("events", "store_projection")],
            backend_type,
            presence="degraded" if telemetry_error else ("present" if telemetry_events else "present_empty"),
            reason=telemetry_error,
            identity={"backend_type": backend_type},
            revision={"projectable_event_count": len(telemetry_events)},
            freshness={"collection_time": config.collection_time},
        )

    # Journal inspection is pure filesystem observation and never recovers it.
    journal_spec = _source(specs, "journal", "transactions")
    journal_dir = plan_dir / "_journal"
    prepares = sorted(journal_dir.glob("tx-*.prepare.json")) if journal_dir.is_dir() else []
    commits = sorted(journal_dir.glob("tx-*.commit")) if journal_dir.is_dir() else []
    prepare_ids = {path.name.removeprefix("tx-").removesuffix(".prepare.json") for path in prepares}
    commit_ids = {path.name.removeprefix("tx-").removesuffix(".commit") for path in commits}
    journal_contradictions: list[InventoryContradiction] = []
    for tx_id in sorted(prepare_ids - commit_ids):
        journal_contradictions.append(
            InventoryContradiction("journal_prepare_without_commit", f"transaction {tx_id} has a prepare record without commit", (str(journal_dir / f"tx-{tx_id}.prepare.json"),))
        )
    for tx_id in sorted(commit_ids - prepare_ids):
        journal_contradictions.append(
            InventoryContradiction("journal_commit_without_prepare", f"transaction {tx_id} has a commit marker without prepare", (str(journal_dir / f"tx-{tx_id}.commit"),))
        )
    parents[("journal", "transactions")] = _record(
        journal_spec,
        str(journal_dir),
        presence="contradictory" if journal_contradictions else ("present" if prepares or commits else "absent"),
        reason=journal_contradictions[0].reason if journal_contradictions else ("" if prepares or commits else "journal directory is absent or empty"),
        revision={"prepare_count": len(prepares), "commit_count": len(commits)},
        contradictions=journal_contradictions,
    )

    backend_spec = _source(specs, "backend", "event_sourced_state_store")
    parents[("backend", "event_sourced_state_store")] = _record(
        backend_spec,
        "event_sourced",
        presence="absent",
        reason="event-sourced state-store backend is unimplemented",
    )

    # Give plan-local configured classes useful paths even when absent.  These
    # defaults make absence distinguishable from lack of configuration.
    plan_local_defaults = {
        ("authority", "evidence_nucleus"): plan_dir / "completion_verdict.json",
        ("authority", "completion_projection"): plan_dir / "finalize.json",
        ("chain", "status"): config.chain_spec_path,
        ("git", "chain_publication"): config.chain_spec_path,
        ("run_state", "resolution"): plan_dir / "state.json",
    }
    for key, path in plan_local_defaults.items():
        if parents[key].path == "":
            parents[key] = _record(
                specs[key], str(path) if path is not None else "", presence="absent" if path is not None else "not_configured",
                reason="configured source is absent" if path is not None else "chain spec path is not configured",
            )

    # ── Custody-owned source classes (M7 shadow-only, per SD1) ──────────────────
    # Each Custody source class produces an inventory record with shadow_only
    # presence.  These are net-new entries; existing Run Authority (38) and
    # WBC (5) ownership rows are never reassigned.
    custody_specs = {(item.category, item.source_class): item for item in CUSTODY_SOURCE_REGISTRY}
    custody_records: list[InventoryRecord] = []
    for key, spec in custody_specs.items():
        custody_records.append(
            _record(
                spec,
                f"custody:{spec.category}/{spec.source_class}",
                presence="shadow_only",
                reason="M7 custody writer; production enforcement disabled per SD2",
                details={
                    "owner": "Custody",
                    "m7_enforcement": "shadow_only",
                    "production_enforcement_blocked": True,
                },
            )
        )

    # ── Authority-increasing writer invariant ───────────────────────────────────
    # Verify that every authority-increasing writer is prerequisite-owned,
    # Custody-gated, deferred shadow-only, or retired.  The invariant runs
    # against both the audited SOURCE_REGISTRY and the new CUSTODY_SOURCE_REGISTRY.
    invariant_contradictions = validate_authority_increasing_writers_invariant(
        source_registry=SOURCE_REGISTRY,
        custody_registry=CUSTODY_SOURCE_REGISTRY,
    )
    if invariant_contradictions:
        # Attach invariant failures to the custody writer_map record
        wm_key = ("custody", "writer_map")
        for i, record in enumerate(custody_records):
            if (record.category, record.source_class) == wm_key:
                custody_records[i] = replace(
                    record,
                    presence="contradictory",
                    reason=invariant_contradictions[0].reason,
                    contradictions=record.contradictions + invariant_contradictions,
                )
                break

    records = tuple(parents.values()) + tuple(children) + tuple(custody_records)
    return AuthorityInventory(records=records)


__all__ = [
    "CUSTODY_SOURCE_REGISTRY",
    "INVENTORY_SCHEMA_VERSION",
    "SOURCE_REGISTRY",
    "AuthorityInventory",
    "InventoryConfig",
    "InventoryContradiction",
    "InventoryRecord",
    "collect_authority_inventory",
    "validate_authority_increasing_writers_invariant",
]
