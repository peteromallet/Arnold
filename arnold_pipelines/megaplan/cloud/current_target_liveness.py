"""Identity-bound current-target liveness and the T4.1 mutation gate.

Liveness describes activity and contradictions.  It never authorizes an
effect.  Selected M3b/M4 mutation paths mint a typed
:class:`MutationCapability` from exact current target, occurrence/cursor,
custody, fence, and required evidence.  Downstream code may narrow or
validate that capability's scope but cannot independently grant authority.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from weakref import WeakSet

from arnold_pipelines.megaplan.cloud.liveness_lease import observe_liveness_lease


SCHEMA = "arnold.megaplan.current_target_liveness.v1"
MUTATION_CAPABILITY_SCHEMA = "arnold.megaplan.mutation_capability.v1"
DEFAULT_CAPABILITY_TTL = timedelta(minutes=5)

PidProbe = Callable[[int], bool | None]
ProcessStartProbe = Callable[[int], str | None]
SessionProbe = Callable[[str], bool | None]


def _text(value: object) -> str:
    return str(value or "").strip()


def _integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _namespace_id() -> str:
    try:
        return Path("/proc/self/ns/pid").resolve().as_posix()
    except OSError:
        return ""


def _process_start_identity(pid: int) -> str | None:
    """Return Linux boot-id + start ticks for one PID incarnation."""

    try:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
        start_ticks = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()[21]
    except (OSError, IndexError):
        return None
    if not boot_id or not start_ticks:
        return None
    return f"{boot_id}:{start_ticks}"


def _pid_live(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _candidate(
    marker: Mapping[str, Any],
    active_step: Mapping[str, Any],
    observer_namespace: str = "",
) -> dict[str, Any]:
    """Prefer launch identity, then an explicitly-bound active worker.

    The launch (marker) identity is preferred whenever it is complete, but a
    marker PID belongs to the original runner container.  When the marker
    identity is bound to a *foreign* namespace while the active-step worker is
    bound to this observer's namespace with a recorded start identity, the
    active worker is the only identity this observer can verify.  Preferring a
    complete candidate in the observer's own namespace keeps the local live
    worker visible (``live``) instead of collapsing to ``unknown`` and fencing
    every repair/retrigger decision.  Everything else keeps the existing
    fail-closed fallback order: first complete candidate, then first candidate.

    Nested ``runner_incarnation`` fields (written by the plan engine into
    ``state.json``) are read as the active-worker binding: a flat
    ``worker_pid_namespace_id``/``worker_process_start_identity`` pair and the
    nested ``runner_incarnation.pid_namespace_id`` /
    ``runner_incarnation.worker_process_start_identity`` pair are equivalent.
    """

    candidates: list[dict[str, Any]] = []
    for source, value in (("marker", marker), ("active_step", active_step)):
        incarnation = value.get("runner_incarnation")
        incarnation = (
            incarnation if isinstance(incarnation, Mapping) else {}
        )
        pid = _integer(
            value.get("pid")
            if source == "marker"
            else value.get("worker_pid") or incarnation.get("worker_pid")
        )
        namespace = _text(
            value.get("pid_namespace_id")
            or value.get("runner_pid_namespace_id")
            or value.get("worker_pid_namespace_id")
            or incarnation.get("pid_namespace_id")
        )
        start = _text(
            value.get("process_start_identity")
            or value.get("runner_process_start_identity")
            or value.get("target_process_start_identity")
            or value.get("worker_process_start_identity")
            or incarnation.get("worker_process_start_identity")
        )
        if pid is not None:
            candidates.append(
                {
                    "source": source,
                    "pid": pid,
                    "pid_namespace_id": namespace,
                    "process_start_identity": start,
                }
            )
    if observer_namespace:
        for candidate in candidates:
            if (
                candidate["pid_namespace_id"] == observer_namespace
                and candidate["process_start_identity"]
            ):
                return candidate
    for candidate in candidates:
        if candidate["pid_namespace_id"] and candidate["process_start_identity"]:
            return candidate
    if candidates:
        return candidates[0]
    return {
        "source": "",
        "pid": None,
        "pid_namespace_id": "",
        "process_start_identity": "",
    }


def _result(
    state: str,
    *,
    source: str,
    reason: str,
    identity: Mapping[str, Any],
    lease: Mapping[str, Any],
    diagnostics: list[str],
) -> dict[str, Any]:
    known = state in {"live", "dead"}
    return {
        "schema": SCHEMA,
        "state": state,
        "live": state == "live",
        "dead": state == "dead",
        "known": known,
        "source": source,
        "reason": reason,
        "identity": dict(identity),
        "lease": dict(lease),
        "diagnostics": diagnostics,
        # A "live" observation is liveness-only evidence: it is provisional and
        # must never authorize verified recovery on its own.
        "provisional_liveness": state == "live",
        # Diagnostic projections only.  They never authorize an effect.
        "control_permitted": False,
        "mutation_permitted": False,
        "escalation_permitted": False,
        "retrigger_permitted": False,
        "authorizes_mutation": False,
    }


def observe_current_target_liveness(
    marker: Mapping[str, Any],
    *,
    marker_dir: str | Path,
    active_step: Mapping[str, Any] | None = None,
    pid_is_live: PidProbe | None = None,
    process_start_identity: ProcessStartProbe | None = None,
    observer_pid_namespace_id: str | None = None,
    session_is_live: SessionProbe | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Observe one target without interpreting foreign-namespace misses as death."""

    marker = marker if isinstance(marker, Mapping) else {}
    active_step = active_step if isinstance(active_step, Mapping) else {}
    diagnostics: list[str] = []
    session = _text(marker.get("session"))
    lease = observe_liveness_lease(marker, marker_dir=Path(marker_dir), now=now)

    observer_namespace = (
        _text(observer_pid_namespace_id)
        if observer_pid_namespace_id is not None
        else _namespace_id()
    )
    identity = _candidate(marker, active_step, observer_namespace=observer_namespace)
    expected_pid = _integer(identity.get("pid"))
    expected_namespace = _text(identity.get("pid_namespace_id"))
    expected_start = _text(identity.get("process_start_identity"))
    identity.update(
        {
            "observer_pid_namespace_id": observer_namespace,
            "namespace_matches": bool(
                expected_namespace
                and observer_namespace
                and expected_namespace == observer_namespace
            ),
            "observed_process_start_identity": "",
            "process_start_matches": None,
        }
    )

    local_state = "unknown"
    local_reason = "target has no namespace-and-start-bound local PID"
    if expected_pid is not None and expected_namespace and expected_start:
        if not observer_namespace:
            local_reason = "observer PID namespace is unavailable"
        elif expected_namespace != observer_namespace:
            local_reason = "target PID belongs to a foreign namespace"
        else:
            live_probe = pid_is_live or _pid_live
            start_probe = process_start_identity or _process_start_identity
            probe_live = live_probe(expected_pid)
            if probe_live is False:
                # The observer is in the bound namespace and the marker names
                # the exact incarnation.  Absence is therefore meaningful.
                local_state = "dead"
                local_reason = "bound PID is absent in its owning namespace"
            elif probe_live is True:
                observed_start = start_probe(expected_pid)
                identity["observed_process_start_identity"] = observed_start or ""
                identity["process_start_matches"] = bool(
                    observed_start and observed_start == expected_start
                )
                if observed_start == expected_start:
                    local_state = "live"
                    local_reason = "namespace and process-start identity match"
                elif observed_start:
                    local_state = "dead"
                    local_reason = "PID was reused by a different process incarnation"
                else:
                    local_reason = "process start identity could not be observed"
            else:
                local_reason = "bound PID probe returned unknown"
    else:
        missing = []
        if expected_pid is None:
            missing.append("pid")
        if not expected_namespace:
            missing.append("pid_namespace_id")
        if not expected_start:
            missing.append("process_start_identity")
        diagnostics.append("local identity incomplete: " + ", ".join(missing))

    # tmux is useful diagnostic evidence but cannot decide target liveness:
    # its namespace is not bound by the marker contract.
    if session and session_is_live is not None:
        try:
            diagnostics.append(f"unbound session probe={session_is_live(session)!r}")
        except Exception as exc:  # pragma: no cover - defensive adapter boundary
            diagnostics.append(f"session probe failed: {type(exc).__name__}")

    lease_live = lease.get("state") == "live" and lease.get("live") is True
    if lease_live and local_state == "dead":
        return _result(
            "unknown",
            source="contradictory_bound_evidence",
            reason="fresh owner lease contradicts local bound-PID absence",
            identity=identity,
            lease=lease,
            diagnostics=diagnostics,
        )
    if lease_live:
        return _result(
            "live",
            source="fresh_owner_lease",
            reason="fresh marker-bound runner lease",
            identity=identity,
            lease=lease,
            diagnostics=diagnostics,
        )
    if local_state in {"live", "dead"}:
        return _result(
            local_state,
            source="matched_local_process_identity",
            reason=local_reason,
            identity=identity,
            lease=lease,
            diagnostics=diagnostics,
        )
    return _result(
        "unknown",
        source="insufficient_bound_evidence",
        reason=local_reason,
        identity=identity,
        lease=lease,
        diagnostics=diagnostics,
    )


def liveness_from_current_target(target: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the canonical diagnostic view.

    Legacy booleans and permission-looking flags are never upgraded to
    authority.  Incomplete evidence remains usable as a description.
    """

    if isinstance(target, Mapping):
        value = target.get("current_target_liveness") or target.get("liveness")
        if isinstance(value, Mapping) and value.get("schema") == SCHEMA:
            observed = dict(value)
            observed["control_permitted"] = False
            observed["mutation_permitted"] = False
            observed["escalation_permitted"] = False
            observed["retrigger_permitted"] = False
            observed["authorizes_mutation"] = False
            observed["provisional_liveness"] = observed.get("state") == "live"
            return observed
    return _result(
        "unknown",
        source="canonical_observation_missing",
        reason="current target has no bound liveness observation",
        identity={},
        lease={},
        diagnostics=[],
    )


def control_liveness_from_current_target(
    target: Mapping[str, Any] | None, *, action: str = "control"
) -> dict[str, Any]:
    """Return a strict canonical *diagnostic* observation.

    This is not a permission gate.  ``action_permitted`` is always False.
    Mutation callers must mint :class:`MutationCapability` instead.
    """

    del action  # retained for call-site compatibility; never a grant
    raw = None
    if isinstance(target, Mapping):
        candidate = target.get("current_target_liveness") or target.get("liveness")
        if isinstance(candidate, Mapping):
            raw = candidate
    state = _text(raw.get("state") if raw else "").lower()
    known = state in {"live", "dead"}
    structurally_valid = bool(
        raw
        and raw.get("schema") == SCHEMA
        and state in {"live", "dead", "unknown"}
        and raw.get("known") is known
        and raw.get("live") is (state == "live")
        and raw.get("dead") is (state == "dead")
    )
    if not structurally_valid:
        result = _result(
            "unknown",
            source="canonical_observation_invalid",
            reason="canonical liveness record is missing or structurally invalid",
            identity={},
            lease={},
            diagnostics=["legacy process evidence is diagnostic-only"],
        )
        result.update(
            {
                "authoritative": False,
                "requested_action": "observe",
                "action_permitted": False,
            }
        )
        return result
    result: dict[str, Any] = dict(raw)
    result.update(
        {
            "authoritative": False,
            "requested_action": "observe",
            "action_permitted": False,
            "control_permitted": False,
            "mutation_permitted": False,
            "escalation_permitted": False,
            "retrigger_permitted": False,
            "authorizes_mutation": False,
            "provisional_liveness": state == "live",
        }
    )
    return result


# ---------------------------------------------------------------------------
# MutationCapability — the sole T4.1 permission seam
# ---------------------------------------------------------------------------


class MutationDenied(PermissionError):
    """Mutation callers fail closed on missing or contradictory identity."""

    def __init__(self, reason: str, *, code: str = "mutation_denied") -> None:
        super().__init__(reason)
        self.reason = reason
        self.code = code


class MutationCapability:
    """Typed, evidence-bound permission for one selected mutation.

    Mint-only. Downstream code may narrow ``scope`` or re-validate identity
    fields. It cannot reconstruct authority from public fields or a Mapping.
    """

    __slots__ = (
        "schema",
        "action",
        "occurrence",
        "target",
        "cursor",
        "fence_epoch",
        "evidence_digest",
        "scope",
        "expires_at",
        "import_root",
        "interpreter",
        "tree_sha_telemetry",
        "custody",
        "token",
        "__weakref__",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise MutationDenied(
            "MutationCapability is mint-only; reconstructed constructors are not authority",
            code="capability_reconstructed",
        )

    def __hash__(self) -> int:
        return id(self)

    def __eq__(self, other: object) -> bool:
        return self is other

    @classmethod
    def _mint(cls, fields: Mapping[str, Any]) -> MutationCapability:
        capability = object.__new__(cls)
        for key in _CAPABILITY_FIELDS:
            object.__setattr__(capability, key, fields[key])
        _MINTED_CAPABILITIES.add(capability)
        return capability

    def narrow(self, scope: str) -> MutationCapability:
        """Return a capability whose scope is a prefix of this one."""

        wanted = _text(scope)
        if not wanted:
            raise MutationDenied("narrowed scope must be non-empty", code="scope_empty")
        if wanted != self.scope and not wanted.startswith(self.scope + "."):
            raise MutationDenied(
                f"cannot widen capability scope {self.scope!r} to {wanted!r}",
                code="scope_widen",
            )
        fields = self.to_dict()
        fields["scope"] = wanted
        fields["token"] = _sign_capability(fields)
        return MutationCapability._mint(fields)

    def requires_action(self, action: str) -> None:
        if _text(action) != self.action:
            raise MutationDenied(
                f"capability action {self.action!r} does not match {action!r}",
                code="action_mismatch",
            )

    def requires_scope(self, scope: str) -> None:
        wanted = _text(scope)
        if wanted != self.scope:
            raise MutationDenied(
                f"capability scope {self.scope!r} does not match {wanted!r}",
                code="scope_mismatch",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "action": self.action,
            "occurrence": self.occurrence,
            "target": self.target,
            "cursor": self.cursor,
            "fence_epoch": self.fence_epoch,
            "evidence_digest": self.evidence_digest,
            "scope": self.scope,
            "expires_at": self.expires_at,
            "import_root": self.import_root,
            "interpreter": self.interpreter,
            "tree_sha_telemetry": self.tree_sha_telemetry,
            "custody": self.custody,
            "token": self.token,
        }


_CAPABILITY_FIELDS = (
    "schema",
    "action",
    "occurrence",
    "target",
    "cursor",
    "fence_epoch",
    "evidence_digest",
    "scope",
    "expires_at",
    "import_root",
    "interpreter",
    "tree_sha_telemetry",
    "custody",
    "token",
)
_CAPABILITY_MAC_KEY = secrets.token_bytes(32)
_MINTED_CAPABILITIES: WeakSet[MutationCapability] = WeakSet()


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def process_import_root() -> Path:
    """Return the live process import root of ``arnold_pipelines``.

    This is the tree the running interpreter actually imported, not
    :func:`megaplan_engine_root` (ambient PYTHONPATH / module-path walk).
    """

    import arnold_pipelines

    return Path(arnold_pipelines.__file__).resolve().parents[1]


def process_interpreter() -> Path:
    return Path(sys.executable).resolve()


def _load_runtime_manifest(path: str | Path | None) -> Mapping[str, Any] | None:
    raw_path = _text(path) or _text(os.environ.get("ARNOLD_RUNTIME_MANIFEST"))
    if not raw_path:
        return None
    try:
        payload = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _manifest_import_root(manifest: Mapping[str, Any] | None) -> str:
    if not isinstance(manifest, Mapping):
        return ""
    epic = manifest.get("epic")
    epic = epic if isinstance(epic, Mapping) else {}
    root = _text(epic.get("runtime_root"))
    if not root:
        return ""
    return str(Path(root).expanduser().resolve())


def _manifest_interpreter(manifest: Mapping[str, Any] | None) -> str:
    if not isinstance(manifest, Mapping):
        return ""
    epic = manifest.get("epic")
    epic = epic if isinstance(epic, Mapping) else {}
    generation = epic.get("dependency_generation")
    generation = generation if isinstance(generation, Mapping) else {}
    interpreter = _text(generation.get("interpreter_path"))
    if not interpreter:
        return ""
    return str(Path(interpreter).expanduser().resolve())


def _tree_sha_telemetry(root: str) -> str:
    if not root:
        return ""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    head = result.stdout.strip().lower() if result.returncode == 0 else ""
    return head if len(head) == 40 else ""


def _aware_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _extract_occurrence(evidence: Mapping[str, Any]) -> str:
    identity = evidence.get("occurrence_identity")
    if isinstance(identity, Mapping):
        for key in ("occurrence", "occurrence_fingerprint", "repair_identity_key"):
            text = _text(identity.get(key))
            if text:
                return text
    for key in (
        "occurrence",
        "occurrence_fingerprint",
        "occurrence_digest",
        "repair_identity_key",
    ):
        text = _text(evidence.get(key))
        if text:
            return text
    return ""


def _extract_custody(evidence: Mapping[str, Any], *, occurrence: str) -> str:
    """Return occurrence-bound custody identity, or empty when absent."""

    identity = evidence.get("occurrence_identity")
    candidates: list[object] = []
    if isinstance(identity, Mapping):
        candidates.extend(
            identity.get(key)
            for key in ("custody", "custody_identity", "custody_receipt")
        )
    for key in (
        "custody",
        "custody_identity",
        "custody_receipt",
        "repair_custody",
    ):
        candidates.append(evidence.get(key))
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            bound = _text(
                candidate.get("identity")
                or candidate.get("custody_identity")
                or candidate.get("receipt")
                or candidate.get("lease_id")
            )
            bound_occurrence = _text(
                candidate.get("occurrence")
                or candidate.get("occurrence_fingerprint")
            )
            if bound_occurrence and occurrence and bound_occurrence != occurrence:
                continue
            if bound:
                return bound
            if candidate:
                return _canonical_digest(dict(candidate))
        text = _text(candidate)
        if text:
            return text
    return ""



def _extract_cursor(evidence: Mapping[str, Any]) -> str:
    cursor = evidence.get("cursor")
    if isinstance(cursor, Mapping):
        digest = _text(cursor.get("digest") or cursor.get("evidence_cursor_digest"))
        if digest:
            return digest
        return _canonical_digest(dict(cursor))
    for key in ("cursor", "plan_cursor", "resume_cursor", "evidence_cursor_digest"):
        value = evidence.get(key)
        if isinstance(value, Mapping):
            return _canonical_digest(dict(value))
        text = _text(value)
        if text:
            return text
    return ""


def _extract_target(evidence: Mapping[str, Any]) -> str:
    target = evidence.get("target")
    if isinstance(target, Mapping):
        for key in ("target_fingerprint", "plan_state_fingerprint", "digest"):
            text = _text(target.get(key))
            if text:
                return text
        return _canonical_digest(dict(target))
    for key in ("target", "target_digest", "target_fingerprint"):
        text = _text(evidence.get(key))
        if text:
            return text
    return ""


def _extract_fence_epoch(evidence: Mapping[str, Any]) -> int | None:
    for key in ("fence_epoch", "fence"):
        value = evidence.get(key)
        if isinstance(value, Mapping):
            value = value.get("epoch") or value.get("fence_epoch")
        if isinstance(value, bool):
            return None
        if isinstance(value, int) and value >= 0:
            return value
        text = _text(value)
        if text.isdigit():
            return int(text)
    return None


def _extract_evidence_digest(evidence: Mapping[str, Any]) -> str:
    digest = _text(evidence.get("evidence_digest"))
    if digest:
        return digest.lower()
    payload = {
        key: evidence[key]
        for key in sorted(evidence)
        if key not in {"capability", "mutation_capability", "liveness"}
    }
    return _canonical_digest(payload)


def _contradictions(evidence: Mapping[str, Any], liveness: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if liveness.get("source") == "contradictory_bound_evidence":
        reasons.append("liveness_contradiction")
    evidence_state = evidence.get("evidence_state")
    if isinstance(evidence_state, Mapping):
        if _text(evidence_state.get("unknown_type")).lower() == "contradictory":
            reasons.append("evidence_state_contradictory")
        if evidence_state.get("authorizes_mutation") is True:
            reasons.append("evidence_state_claimed_authority")
    stale = evidence.get("stale_evidence")
    if isinstance(stale, list):
        kinds = {
            _text(item.get("kind"))
            for item in stale
            if isinstance(item, Mapping)
        }
        if "contradictory_plan_identity" in kinds:
            reasons.append("marker_plan_identity_contradiction")
        if "contradictory_manifest_identity" in kinds:
            reasons.append("marker_manifest_contradiction")
    if evidence.get("contradictory") is True:
        reasons.append("evidence_flagged_contradictory")
    marker = evidence.get("marker")
    manifest = evidence.get("manifest") or evidence.get("runtime_manifest")
    if isinstance(marker, Mapping) and isinstance(manifest, Mapping):
        marker_root = _text(
            marker.get("import_root")
            or (marker.get("runtime_identity") or {}).get("import_root")
            if isinstance(marker.get("runtime_identity"), Mapping)
            else marker.get("import_root")
        )
        epic = manifest.get("epic") if isinstance(manifest.get("epic"), Mapping) else manifest
        manifest_root = _text(epic.get("runtime_root") if isinstance(epic, Mapping) else "")
        if marker_root and manifest_root:
            try:
                if Path(marker_root).resolve() != Path(manifest_root).resolve():
                    reasons.append("marker_manifest_root_mismatch")
            except OSError:
                reasons.append("marker_manifest_root_unreadable")
    expected_cursor = _text(evidence.get("expected_cursor") or evidence.get("live_cursor"))
    supplied_cursor = _extract_cursor(evidence)
    if expected_cursor and supplied_cursor and expected_cursor != supplied_cursor:
        reasons.append("stale_cursor")
    expected_fence = evidence.get("expected_fence_epoch")
    supplied_fence = _extract_fence_epoch(evidence)
    if (
        isinstance(expected_fence, int)
        and not isinstance(expected_fence, bool)
        and supplied_fence is not None
        and supplied_fence < expected_fence
    ):
        reasons.append("stale_fence")
    return reasons


def _bind_live_tree(
    *,
    action: str,
    evidence: Mapping[str, Any],
    process_root: Path,
    process_python: Path,
) -> tuple[str, str, str]:
    """Return (import_root, interpreter, tree_sha_telemetry) or raise."""

    manifest = evidence.get("runtime_manifest")
    if not isinstance(manifest, Mapping):
        manifest = _load_runtime_manifest(evidence.get("runtime_manifest_path"))
    live_root = _manifest_import_root(manifest) or _text(
        evidence.get("import_root") or evidence.get("runtime_root")
    )
    if live_root:
        live_root = str(Path(live_root).expanduser().resolve())
    live_interpreter = _manifest_interpreter(manifest) or _text(
        evidence.get("interpreter") or evidence.get("interpreter_path")
    )
    if live_interpreter:
        live_interpreter = str(Path(live_interpreter).expanduser().resolve())

    needs_live_tree = action in {"engine_runtime", "recover-blocked"} or (
        _text(evidence.get("repair_scope")) == "engine_runtime"
        or _text(evidence.get("scope")) in {"engine_runtime", "source_repair"}
    )
    if not needs_live_tree:
        return live_root, live_interpreter, _tree_sha_telemetry(live_root)

    if not live_root:
        raise MutationDenied(
            "engine_runtime/recover-blocked requires epic.runtime_root import_root",
            code="import_root_missing",
        )
    if process_root != Path(live_root):
        raise MutationDenied(
            "process import_root does not equal the live epic.runtime_root; "
            "ambient megaplan_engine_root() is not authority",
            code="import_root_mismatch",
        )
    if live_interpreter and process_python != Path(live_interpreter):
        raise MutationDenied(
            "process interpreter does not equal the generation interpreter",
            code="interpreter_mismatch",
        )
    ambient = evidence.get("ambient_engine_root")
    if ambient:
        try:
            ambient_root = Path(str(ambient)).expanduser().resolve()
        except OSError:
            ambient_root = Path(str(ambient))
        if ambient_root != Path(live_root):
            # Ambient mismatch is a typed error, not silent alternate-root
            # selection.  The capability still binds the live tree.
            raise MutationDenied(
                "ambient megaplan_engine_root() is a foreign/read-only tree; "
                "MutationCapability binds epic.runtime_root import_root",
                code="ambient_engine_root_rejected",
            )
    return live_root, live_interpreter or str(process_python), _tree_sha_telemetry(live_root)


def _sign_capability(fields: Mapping[str, Any]) -> str:
    payload = {key: fields[key] for key in _CAPABILITY_FIELDS if key != "token"}
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    return "mc:" + hmac.new(_CAPABILITY_MAC_KEY, encoded, hashlib.sha256).hexdigest()


def _minted_object(capability: object) -> MutationCapability | None:
    if not isinstance(capability, MutationCapability):
        return None
    if capability not in _MINTED_CAPABILITIES:
        return None
    return capability


def require_mutation_capability(
    capability: MutationCapability | Mapping[str, Any] | None,
    *,
    action: str,
    occurrence: str = "",
    scope: str = "",
) -> MutationCapability:
    """Accept only a previously minted root capability.

    A reconstructed Mapping is not authority. Valid downstream
    receipt/cutover/operator evidence without this object still rejects.
    """

    if capability is None:
        raise MutationDenied(
            "mutation requires a root MutationCapability",
            code="capability_absent",
        )
    if isinstance(capability, Mapping):
        raise MutationDenied(
            "reconstructed Mapping is not a minted MutationCapability",
            code="capability_reconstructed",
        )
    minted = _minted_object(capability)
    if minted is None:
        raise MutationDenied(
            "mutation requires a previously minted MutationCapability",
            code="capability_reconstructed",
        )
    if minted.schema != MUTATION_CAPABILITY_SCHEMA:
        raise MutationDenied("unknown mutation capability schema", code="capability_schema")
    expected = _sign_capability(minted.to_dict())
    if not hmac.compare_digest(minted.token, expected):
        raise MutationDenied(
            "mutation capability token does not match bound identity",
            code="capability_forged",
        )
    try:
        expires = datetime.fromisoformat(minted.expires_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MutationDenied("capability expiry is unreadable", code="capability_expiry") from exc
    if _aware_utc(None) > _aware_utc(expires):
        raise MutationDenied("mutation capability has expired", code="capability_expired")
    minted.requires_action(action)
    if occurrence and occurrence != minted.occurrence:
        raise MutationDenied(
            "capability occurrence does not match the requested occurrence",
            code="occurrence_mismatch",
        )
    if scope:
        minted.requires_scope(scope)
    return minted


def mint_mutation_capability(
    *,
    action: str,
    evidence: Mapping[str, Any] | None,
    now: datetime | None = None,
    ttl: timedelta = DEFAULT_CAPABILITY_TTL,
    process_root: Path | None = None,
    process_python: Path | None = None,
) -> MutationCapability:
    """Mint the sole T4.1 permission grant, or fail closed.

    Diagnostic callers must not use this function.  Incomplete or
    contradictory identity refuses rather than describing the gap.
    Occurrence-bound custody is required at mint time.
    """

    action_name = _text(action)
    if not action_name:
        raise MutationDenied("mutation action is required", code="action_missing")
    if not isinstance(evidence, Mapping) or not evidence:
        raise MutationDenied(
            "mutation requires complete evidence-bound identity",
            code="evidence_missing",
        )

    liveness = liveness_from_current_target(evidence)
    contradictions = _contradictions(evidence, liveness)
    if contradictions:
        raise MutationDenied(
            "contradictory identity refuses mutation: " + ",".join(contradictions),
            code="identity_contradiction",
        )

    occurrence = _extract_occurrence(evidence)
    target = _extract_target(evidence)
    cursor = _extract_cursor(evidence)
    fence_epoch = _extract_fence_epoch(evidence)
    evidence_digest = _extract_evidence_digest(evidence)
    custody = _extract_custody(evidence, occurrence=occurrence)
    scope = _text(evidence.get("scope") or action_name)
    missing = [
        name
        for name, value in (
            ("occurrence", occurrence),
            ("target", target),
            ("cursor", cursor),
            ("evidence_digest", evidence_digest),
            ("scope", scope),
            ("custody", custody),
        )
        if not value
    ]
    if fence_epoch is None:
        missing.append("fence_epoch")
    if missing:
        raise MutationDenied(
            "mutation identity incomplete: " + ", ".join(missing),
            code="identity_incomplete",
        )

    live_root, live_interpreter, tree_sha = _bind_live_tree(
        action=action_name,
        evidence=evidence,
        process_root=(process_root or process_import_root()).resolve(),
        process_python=(process_python or process_interpreter()).resolve(),
    )
    issued = _aware_utc(now)
    expires = issued + ttl
    fields = {
        "schema": MUTATION_CAPABILITY_SCHEMA,
        "action": action_name,
        "occurrence": occurrence,
        "target": target,
        "cursor": cursor,
        "fence_epoch": fence_epoch,
        "evidence_digest": evidence_digest,
        "scope": scope,
        "expires_at": expires.isoformat().replace("+00:00", "Z"),
        "import_root": live_root,
        "interpreter": live_interpreter,
        "tree_sha_telemetry": tree_sha,
        "custody": custody,
        "token": "",
    }
    fields["token"] = _sign_capability(fields)
    return MutationCapability._mint(fields)




__all__ = [
    "SCHEMA",
    "MUTATION_CAPABILITY_SCHEMA",
    "DEFAULT_CAPABILITY_TTL",
    "MutationCapability",
    "MutationDenied",
    "control_liveness_from_current_target",
    "liveness_from_current_target",
    "mint_mutation_capability",
    "observe_current_target_liveness",
    "process_import_root",
    "process_interpreter",
    "require_mutation_capability",
]
