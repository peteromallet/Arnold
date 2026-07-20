"""M7 occurrence-writer-terminal provenance map (report-only, shadow mode).

Generates a deterministic JSON artefact that joins the F01 repair-occurrence
tuple to BlockerFingerprintV1/V2 fields and
``repair_recurrence.PROBLEM_SIGNATURE_FIELDS``, explicitly marks every missing
chain-identity, Run Authority grant-id, coordinator-fence token, WBC attempt
reference, and custody-epoch field, classifies every existing writer surface
from the audited authority-inventory registry, and records M6/M6A
``production_enforcement_blocked`` metadata.

This module is **read-only** — it produces a report artefact only and never
enables any production gate or mutating effect.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

# ── F01 repair occurrence tuple (from unified-authority-efficiency-prevention) ──
F01_REPAIR_OCCURRENCE_FIELDS: tuple[str, ...] = (
    "environment",
    "session",
    "chain",
    "plan_revision",
    "phase",
    "task",
    "attempt",
    "normalized_failure_kind",
    "blocker_or_phase_result_hash",
    "fence",
)

# ── BlockerFingerprintV1 required fields (from repair_contract) ────────────────
BLOCKER_FINGERPRINT_V1_FIELDS: tuple[str, ...] = (
    "current_state",
    "retry_strategy",
    "failure_kind",
    "phase_or_step",
    "milestone_or_plan",
    "blocked_task_id",
    "target_fingerprint",
)

# ── BlockerFingerprintV2 extension fields (from repair_contract) ───────────────
BLOCKER_FINGERPRINT_V2_EXTENSION_FIELDS: tuple[str, ...] = (
    "acceptance_transaction_id",
    "acceptance_snapshot_hash",
    "predicate_kind",
    "predicate_evidence_kind",
    "predicate_summary",
    "evidence_refs",
    "safe_recovery_action",
    "recovery_action",
    "expected_hash",
    "observed_hash",
    "runtime_identity",
    "source_commit_ref",
    "custody_owner",
    "custody_epoch",
    "retry_count",
    "retry_cap",
    "predecessor_blocker_id",
    "predecessor_fingerprint_hash",
)

# ── PROBLEM_SIGNATURE_FIELDS (from repair_recurrence) ──────────────────────────
PROBLEM_SIGNATURE_FIELDS: tuple[str, ...] = (
    "failure_kind",
    "current_state",
    "phase_or_step",
    "milestone_or_plan",
    "gate_recommendation",
    "blocked_task_id",
    "event_signature",
)

ACCEPTANCE_PREDICATE_SIGNATURE_FIELDS: tuple[str, ...] = (
    "acceptance_predicate_kind",
    "acceptance_predicate_evidence_kind",
    "acceptance_predicate_summary",
    "acceptance_transaction_id",
    "acceptance_snapshot_hash",
    "acceptance_evidence_refs",
    "safe_recovery_action",
    "recovery_action",
)

EXTENDED_PROBLEM_SIGNATURE_FIELDS: tuple[str, ...] = (
    PROBLEM_SIGNATURE_FIELDS + ACCEPTANCE_PREDICATE_SIGNATURE_FIELDS
)

# ── M7 missing fields (owner-bound, not yet in any existing source) ────────────
M7_MISSING_FIELDS: tuple[str, ...] = (
    "chain_identity",
    "run_authority_grant_id",
    "coordinator_fence_token",
    "wbc_attempt_reference",
    "custody_epoch",
)

# ── M6/M6A blocker flags (report-only, gates/effects off) ──────────────────────
M6_M6A_PRODUCTION_ENFORCEMENT_BLOCKED: bool = True
M6_M6A_BLOCKER_REASONS: tuple[str, ...] = (
    "M6 prerequisite coherence incomplete — residual surface inventory not yet accepted",
    "M6A operational WBC store/API not yet landed — WBC is schema-only",
    "M6 ownership decision record not yet machine-verified",
    "M7 production gates and mutating effects remain disabled per SD2",
    "Run Authority grant/coordinator-fence contract landed but M7 validator is shadow-only",
)

# ── Writer surface classification ──────────────────────────────────────────────
OWNER_RUN_AUTHORITY = "Run Authority"
OWNER_WBC = "WBC"
OWNER_CUSTODY = "Custody"
OWNER_PROJECTION = "Projection"
OWNER_OBSERVABILITY = "Observability"
OWNER_DOMAIN = "Domain (Megaplan)"
OWNER_MAINTENANCE = "Maintenance"


@dataclass(frozen=True)
class WriterSurface:
    """Classified writer surface in the provenance map."""

    surface_id: str
    category: str
    source_class: str
    owner: str
    authority_increasing: bool
    m7_enforcement: str
    reader: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_id": self.surface_id,
            "category": self.category,
            "source_class": self.source_class,
            "owner": self.owner,
            "authority_increasing": self.authority_increasing,
            "m7_enforcement": self.m7_enforcement,
            "reader": self.reader,
            "notes": self.notes,
        }


# ── Writer surface registry ───────────────────────────────────────────────────
WRITER_SURFACES: tuple[WriterSurface, ...] = (
    # ── Run Authority writers (38 existing) ────────────────────────────────────
    WriterSurface("ra-01", "execute", "state", OWNER_RUN_AUTHORITY, False, "none",
                  "PlanRepository.read_artifact_json", "Read-only projection of execute state."),
    WriterSurface("ra-02", "execute", "finalize", OWNER_RUN_AUTHORITY, False, "none",
                  "PlanRepository.read_artifact_json/describe_artifact", "Read-only finalize projection."),
    WriterSurface("ra-03", "execute", "s4_batch_artifacts", OWNER_RUN_AUTHORITY, False, "none",
                  "list_batch_artifacts/PlanRepository.describe_artifact", "Claim-level batch artifact inspection."),
    WriterSurface("ra-04", "execute", "legacy_batch_artifacts", OWNER_RUN_AUTHORITY, False, "none",
                  "list_batch_artifacts", "Legacy batch inspection."),
    WriterSurface("ra-05", "execute", "execution_auxiliary", OWNER_RUN_AUTHORITY, False, "none",
                  "PlanRepository.list_artifacts/read_artifact_json", "Auxiliary execution projection."),
    WriterSurface("ra-06", "execute", "completion_verdict", OWNER_RUN_AUTHORITY, True, "shadow_only",
                  "read_typed_completion_verdict", "Decision-level completion verdict; M7 shadow-validates."),
    WriterSurface("ra-07", "repository", "plan_tree", OWNER_RUN_AUTHORITY, False, "none",
                  "PlanRepository.list_artifact_paths/list_artifacts", "Observation of plan tree."),
    WriterSurface("ra-08", "store", "file_epic_events", OWNER_RUN_AUTHORITY, False, "none",
                  "Store.list_epic_events_for_replay", "Claim-level event inspection."),
    WriterSurface("ra-09", "store", "db_epic_events", OWNER_RUN_AUTHORITY, False, "none",
                  "Store.list_epic_events_for_replay", "DB event inspection."),
    WriterSurface("ra-10", "store", "telemetry_progress", OWNER_RUN_AUTHORITY, False, "none",
                  "Store.events_for_plan/list_progress_events", "Observation of telemetry progress."),
    WriterSurface("ra-11", "compatibility", "store_adapter", OWNER_RUN_AUTHORITY, False, "none",
                  "ArnoldStoreAdapter", "Compatibility projection adapter."),
    WriterSurface("ra-12", "authority", "evidence_nucleus", OWNER_RUN_AUTHORITY, False, "none",
                  "load_evidence_nucleus/authority_decision_for_task", "Evidence-nucleus claim."),
    WriterSurface("ra-13", "authority", "completion_projection", OWNER_RUN_AUTHORITY, False, "none",
                  "authority_decision_for_task/is_task_satisfied", "Completion projection."),
    WriterSurface("ra-14", "chain", "spec", OWNER_RUN_AUTHORITY, False, "none",
                  "chain.spec.load_spec", "Chain spec loading claim."),
    WriterSurface("ra-15", "chain", "state_candidates", OWNER_RUN_AUTHORITY, False, "none",
                  "chain.spec._state_path_candidates_for", "Chain state candidate projection."),
    WriterSurface("ra-16", "chain", "legacy_state", OWNER_RUN_AUTHORITY, False, "none",
                  "chain.spec._state_path_candidates_for", "Legacy chain state projection."),
    WriterSurface("ra-17", "chain", "status", OWNER_RUN_AUTHORITY, False, "none",
                  "build_chain_status_snapshot", "Chain status projection."),
    WriterSurface("ra-18", "cloud", "session_marker", OWNER_RUN_AUTHORITY, False, "none",
                  "resolve_current_target/is_canonical_session_marker_path", "Session marker claim."),
    WriterSurface("ra-19", "cloud", "current_target", OWNER_RUN_AUTHORITY, False, "none",
                  "resolve_current_target/normalize_evidence", "Current target projection."),
    WriterSurface("ra-20", "cloud", "status_snapshot", OWNER_RUN_AUTHORITY, False, "none",
                  "load_cloud_status_snapshot", "Cloud status snapshot projection."),
    WriterSurface("ra-21", "cloud", "health_sidecars", OWNER_RUN_AUTHORITY, False, "none",
                  "build_cloud_status_snapshot", "Health sidecars projection."),
    WriterSurface("ra-22", "watchdog", "live_snapshot", OWNER_RUN_AUTHORITY, False, "none",
                  "watchdog.snapshot.build_snapshot", "Live watchdog snapshot projection."),
    WriterSurface("ra-23", "watchdog", "persisted_report", OWNER_RUN_AUTHORITY, False, "none",
                  "cloud.status_snapshot._load_watchdog_report", "Persisted watchdog report projection."),
    WriterSurface("ra-24", "watchdog", "registry", OWNER_RUN_AUTHORITY, False, "none",
                  "WatchdogRegistry.load semantics (read-only)", "Watchdog registry read."),
    WriterSurface("ra-25", "repair", "needs_human", OWNER_RUN_AUTHORITY, False, "none",
                  "resolve_current_target/classify_needs_human_blocker", "Needs-human claim classification."),
    WriterSurface("ra-26", "repair", "data_index_attempts", OWNER_RUN_AUTHORITY, False, "none",
                  "repair_contract.load_json/read_repair_index", "Repair data index projection."),
    WriterSurface("ra-27", "repair", "queue_requests", OWNER_RUN_AUTHORITY, False, "none",
                  "iter_repair_requests(include_malformed=True)", "Queue request claim inspection."),
    WriterSurface("ra-28", "repair", "queue_decisions", OWNER_RUN_AUTHORITY, True, "shadow_only",
                  "iter_repair_decisions(include_malformed=True)", "Repair queue decision; M7 shadow-validates."),
    WriterSurface("ra-29", "repair", "jsonl_sidecars", OWNER_RUN_AUTHORITY, False, "none",
                  "repair_contract.read_jsonl_records", "JSONL sidecar claim."),
    WriterSurface("ra-30", "git", "worktree", OWNER_RUN_AUTHORITY, False, "none",
                  "repair_recurrence._probe_git_progress", "Git worktree observation."),
    WriterSurface("ra-31", "git", "chain_publication", OWNER_RUN_AUTHORITY, False, "none",
                  "captured chain state fields", "Chain publication projection."),
    WriterSurface("ra-32", "git", "github_pr", OWNER_RUN_AUTHORITY, False, "none",
                  "repair_recurrence._probe_pr_state", "GitHub PR observation."),
    WriterSurface("ra-33", "process", "processes", OWNER_RUN_AUTHORITY, False, "none",
                  "watchdog.processes.scan_processes", "Process scan observation."),
    WriterSurface("ra-34", "session", "tmux", OWNER_RUN_AUTHORITY, False, "none",
                  "default_liveness_probe/TmuxSession.exists", "Tmux session observation."),
    WriterSurface("ra-35", "run_state", "active_step_heartbeat", OWNER_RUN_AUTHORITY, False, "none",
                  "resolve_current_target", "Active-step heartbeat observation."),
    WriterSurface("ra-36", "run_state", "normalization", OWNER_RUN_AUTHORITY, False, "none",
                  "run_state.evidence.normalize_evidence", "Run-state normalization projection."),
    WriterSurface("ra-37", "run_state", "resolution", OWNER_RUN_AUTHORITY, True, "shadow_only",
                  "run_state.resolver.resolve_run_state", "Run-state resolution decision; M7 shadow-validates."),
    WriterSurface("ra-38", "events", "plan_events", OWNER_RUN_AUTHORITY, False, "none",
                  "events schema-compatible read-only parser", "Plan-events observation."),

    # ── WBC writers (5 existing) ──────────────────────────────────────────────
    WriterSurface("wbc-01", "wal", "shadow_state_fold", OWNER_WBC, False, "none",
                  "observability.fold.fold_events", "WAL shadow-state fold projection."),
    WriterSurface("wbc-02", "events", "store_projection", OWNER_WBC, False, "none",
                  "events_projection.project_events", "Events store projection."),
    WriterSurface("wbc-03", "journal", "transactions", OWNER_WBC, False, "none",
                  "_core.io journal path helpers/read-only JSON", "Journal transaction decision."),
    WriterSurface("wbc-04", "backend", "event_sourced_state_store", OWNER_WBC, False, "none",
                  "EventSourcedStateStoreBackend", "Event-sourced state store backend decision."),
    WriterSurface("wbc-05", "events", "events_projection", OWNER_WBC, False, "none",
                  "events_projection", "Events projection placeholder."),

    # ── Net-new Custody writers (shadow-only in M7 per SD1) ────────────────────
    WriterSurface("custody-01", "custody", "writer_map", OWNER_CUSTODY, False, "none",
                  "custody.writer_map.generate_writer_map", "Report-only provenance map; no production effect."),
    WriterSurface("custody-02", "custody", "contracts", OWNER_CUSTODY, False, "shadow_only",
                  "custody.contracts (T3)", "Schema definitions; no production writes."),
    WriterSurface("custody-03", "custody", "lease_store", OWNER_CUSTODY, True, "shadow_only",
                  "custody.lease_store (T5)", "Append-only lease history; enforcement blocked until M6/M6A."),
    WriterSurface("custody-04", "custody", "outbox", OWNER_CUSTODY, False, "shadow_only",
                  "custody.outbox (T7)", "Durable cross-owner outbox; writes only Custody-owned state."),
    WriterSurface("custody-05", "custody", "action_validator", OWNER_CUSTODY, True, "shadow_only",
                  "custody.action_validator.validate_action_boundary (T8)",
                  "Conjunctive gate: validates Run Authority grant/fence + Custody lease/epoch + WBC evidence."),
    WriterSurface("custody-06", "custody", "projections", OWNER_CUSTODY, False, "shadow_only",
                  "custody.projections (T16)", "Cursor-checked projection appends; no authority grant."),
    WriterSurface("custody-07", "custody", "controlled_writer_registry", OWNER_CUSTODY, True, "shadow_only",
                  "custody.controlled_writer_registry (T10)", "Registry of controlled authority-increasing writers."),
    WriterSurface("custody-08", "custody", "receipts", OWNER_CUSTODY, False, "shadow_only",
                  "custody.receipts (T18)", "Immutable attempt-scoped evidence receipts."),
    WriterSurface("custody-09", "custody", "compatibility", OWNER_CUSTODY, False, "shadow_only",
                  "custody.compatibility (T20)", "Old-reader/new-writer compatibility bridge."),
    WriterSurface("custody-10", "custody", "canary", OWNER_CUSTODY, False, "shadow_only",
                  "custody.canary (T21)", "Idle pinned-runtime canary."),
    WriterSurface("custody-11", "custody", "bypass_proof", OWNER_CUSTODY, True, "shadow_only",
                  "custody.bypass_proof (T22)", "Bypass-proof registry; enforcement blocked until M6/M6A."),

    # ── Projection / observability / maintenance / domain ──────────────────────
    WriterSurface("proj-01", "projection", "chain_projection", OWNER_PROJECTION, False, "none",
                  "chain projections", "Derived chain state projections; no authority."),
    WriterSurface("proj-02", "projection", "cloud_projection", OWNER_PROJECTION, False, "none",
                  "cloud projections", "Derived cloud status projections."),
    WriterSurface("proj-03", "projection", "watchdog_projection", OWNER_PROJECTION, False, "none",
                  "watchdog projections", "Derived watchdog projections."),
    WriterSurface("obs-01", "observability", "operator_view", OWNER_OBSERVABILITY, False, "none",
                  "operator views", "Pure operator views; never authorizes action."),
    WriterSurface("obs-02", "observability", "auditor", OWNER_OBSERVABILITY, False, "none",
                  "auditor reasons", "Exact-evidence auditor reasons."),
    WriterSurface("maint-01", "maintenance", "scan_recovery", OWNER_MAINTENANCE, False, "none",
                  "six-hour reconciliation backstop", "Hourly scan + six-hour reconciliation; never primary dispatch."),
    WriterSurface("maint-02", "maintenance", "efficiency_analysis", OWNER_MAINTENANCE, False, "none",
                  "daily read-only efficiency analysis", "Read-only efficiency analysis."),
    WriterSurface("domain-01", "domain", "planner_compiler", OWNER_DOMAIN, False, "none",
                  "Megaplan planner/compiler", "Domain scheduling, DAG readiness, model routing, task sizing."),
    WriterSurface("domain-02", "domain", "executor_launcher", OWNER_DOMAIN, False, "none",
                  "executor/launcher", "Source/runtime preflight, verify-only adoption, bounded timeout/failover."),
)


# ── Field join mapping ─────────────────────────────────────────────────────────

def _build_field_join() -> list[dict[str, Any]]:
    """Build the deterministic join of F01 tuple, BlockerFingerprintV1/V2,
    and PROBLEM_SIGNATURE_FIELDS with explicit missing-field markers."""
    joined: list[dict[str, Any]] = []

    # F01 fields
    for field in F01_REPAIR_OCCURRENCE_FIELDS:
        joined.append({
            "field": field,
            "source": "F01_REPAIR_OCCURRENCE_TUPLE",
            "present_in_m7": True,
            "missing_reason": None,
            "owner": (OWNER_CUSTODY if field in ("environment", "plan_revision", "phase", "task",
                                                  "attempt", "normalized_failure_kind",
                                                  "blocker_or_phase_result_hash", "fence")
                      else OWNER_RUN_AUTHORITY),
            "notes": "",
        })

    # BlockerFingerprintV1 fields
    for field in BLOCKER_FINGERPRINT_V1_FIELDS:
        joined.append({
            "field": field,
            "source": "BLOCKER_FINGERPRINT_V1",
            "present_in_m7": True,
            "missing_reason": None,
            "owner": OWNER_RUN_AUTHORITY,
            "notes": "Required V1 field; must be non-empty string.",
        })

    # BlockerFingerprintV2 extension fields
    for field in BLOCKER_FINGERPRINT_V2_EXTENSION_FIELDS:
        missing = None
        if field in ("custody_owner", "custody_epoch"):
            missing = "Custody contract not yet landed (T3)"
        elif field in ("runtime_identity", "source_commit_ref"):
            missing = "Deferred to M8A"
        joined.append({
            "field": field,
            "source": "BLOCKER_FINGERPRINT_V2",
            "present_in_m7": missing is None,
            "missing_reason": missing,
            "owner": (OWNER_CUSTODY if field in ("custody_owner", "custody_epoch", "retry_count",
                                                  "retry_cap", "predecessor_blocker_id",
                                                  "predecessor_fingerprint_hash")
                      else OWNER_WBC if field.startswith("acceptance_")
                      else OWNER_RUN_AUTHORITY),
            "notes": "Optional V2 field; defaults to empty string when absent.",
        })

    # PROBLEM_SIGNATURE_FIELDS
    for field in PROBLEM_SIGNATURE_FIELDS:
        joined.append({
            "field": field,
            "source": "PROBLEM_SIGNATURE_FIELDS",
            "present_in_m7": True,
            "missing_reason": None,
            "owner": OWNER_CUSTODY,
            "notes": "From repair_recurrence.PROBLEM_SIGNATURE_FIELDS.",
        })

    # ACCEPTANCE_PREDICATE_SIGNATURE_FIELDS
    for field in ACCEPTANCE_PREDICATE_SIGNATURE_FIELDS:
        joined.append({
            "field": field,
            "source": "ACCEPTANCE_PREDICATE_SIGNATURE_FIELDS",
            "present_in_m7": False,
            "missing_reason": "Acceptance predicate signature fields require M6A operational WBC API (deferred to M8).",
            "owner": OWNER_WBC,
            "notes": "Appended to PROBLEM_SIGNATURE_FIELDS for distinct repair identities.",
        })

    # M7 explicitly missing fields
    missing_reasons: dict[str, str] = {
        "chain_identity": "Requires chain execution binding (M6A).",
        "run_authority_grant_id": "Requires Run Authority grant acceptance (M5 landed but M7 validator shadow-only).",
        "coordinator_fence_token": "Requires Run Authority coordinator fence (M5 landed but M7 validator shadow-only).",
        "wbc_attempt_reference": "Requires WBC operational attempt ledger (M6A not yet landed).",
        "custody_epoch": "Requires Custody lease contract (T3/T5).",
    }
    missing_owners: dict[str, str] = {
        "chain_identity": OWNER_CUSTODY,
        "run_authority_grant_id": OWNER_RUN_AUTHORITY,
        "coordinator_fence_token": OWNER_RUN_AUTHORITY,
        "wbc_attempt_reference": OWNER_WBC,
        "custody_epoch": OWNER_CUSTODY,
    }
    for field in M7_MISSING_FIELDS:
        joined.append({
            "field": field,
            "source": "M7_MISSING",
            "present_in_m7": False,
            "missing_reason": missing_reasons.get(field, "Blocked by M6/M6A prerequisites."),
            "owner": missing_owners.get(field, "UNKNOWN"),
            "notes": "Explicitly marked missing per SD2: production enforcement disabled.",
        })

    return joined


# ── Provenance map generation ──────────────────────────────────────────────────

PROVENANCE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class OccurrenceWriterTerminalProvenanceMap:
    """Deterministic M7 provenance map artefact."""

    schema_version: int = PROVENANCE_SCHEMA_VERSION
    generated_at: str = ""
    sha256: str = ""
    f01_repair_occurrence_fields: tuple[str, ...] = F01_REPAIR_OCCURRENCE_FIELDS
    field_join: tuple[dict[str, Any], ...] = ()
    writer_surfaces: tuple[dict[str, Any], ...] = ()
    authority_increasing_writers: tuple[str, ...] = ()
    production_enforcement_blocked: bool = M6_M6A_PRODUCTION_ENFORCEMENT_BLOCKED
    blocker_reasons: tuple[str, ...] = M6_M6A_BLOCKER_REASONS
    m7_shadow_mode: bool = True
    gates_enabled: bool = False
    effects_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "sha256": self.sha256,
            "f01_repair_occurrence_fields": list(self.f01_repair_occurrence_fields),
            "field_join": list(self.field_join),
            "writer_surfaces": list(self.writer_surfaces),
            "authority_increasing_writers": list(self.authority_increasing_writers),
            "production_enforcement_blocked": self.production_enforcement_blocked,
            "blocker_reasons": list(self.blocker_reasons),
            "m7_shadow_mode": self.m7_shadow_mode,
            "gates_enabled": self.gates_enabled,
            "effects_enabled": self.effects_enabled,
        }


def generate_writer_map(output_path: str | Path | None = None) -> OccurrenceWriterTerminalProvenanceMap:
    """Generate the deterministic M7 provenance map.

    If *output_path* is given, write the JSON artefact there atomically.
    Returns the frozen provenance map object.
    """
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    field_join = tuple(_build_field_join())
    writer_surfaces = tuple(s.to_dict() for s in WRITER_SURFACES)
    authority_increasing = tuple(
        s.surface_id for s in WRITER_SURFACES if s.authority_increasing
    )

    provenance = OccurrenceWriterTerminalProvenanceMap(
        schema_version=PROVENANCE_SCHEMA_VERSION,
        generated_at=generated_at,
        sha256="",
        f01_repair_occurrence_fields=F01_REPAIR_OCCURRENCE_FIELDS,
        field_join=field_join,
        writer_surfaces=writer_surfaces,
        authority_increasing_writers=authority_increasing,
        production_enforcement_blocked=M6_M6A_PRODUCTION_ENFORCEMENT_BLOCKED,
        blocker_reasons=M6_M6A_BLOCKER_REASONS,
        m7_shadow_mode=True,
        gates_enabled=False,
        effects_enabled=False,
    )

    # Compute deterministic SHA-256 over the canonical JSON
    provisional = provenance.to_dict()
    provisional.pop("sha256", None)
    provisional.pop("generated_at", None)
    canonical_bytes = json.dumps(provisional, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=False).encode("utf-8")
    digest = "sha256:" + hashlib.sha256(canonical_bytes).hexdigest()

    final = OccurrenceWriterTerminalProvenanceMap(
        schema_version=provenance.schema_version,
        generated_at=generated_at,
        sha256=digest,
        f01_repair_occurrence_fields=provenance.f01_repair_occurrence_fields,
        field_join=provenance.field_join,
        writer_surfaces=provenance.writer_surfaces,
        authority_increasing_writers=provenance.authority_increasing_writers,
        production_enforcement_blocked=provenance.production_enforcement_blocked,
        blocker_reasons=provenance.blocker_reasons,
        m7_shadow_mode=provenance.m7_shadow_mode,
        gates_enabled=provenance.gates_enabled,
        effects_enabled=provenance.effects_enabled,
    )

    if output_path is not None:
        _atomic_write_json(output_path, final.to_dict())

    return final


def _atomic_write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    """Atomically replace a JSON file."""
    import tempfile

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ── Module-level generation ────────────────────────────────────────────────────
_DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "evidence" / "m7-occurrence-writer-terminal-provenance-map.json"

_invoked_via_cli = os.environ.get("ARNOLD_M7_GENERATE_WRITER_MAP", "0") == "1"


def _ensure_evidence() -> OccurrenceWriterTerminalProvenanceMap:
    """Lazy-generate the evidence artefact once."""
    return generate_writer_map(output_path=_DEFAULT_OUTPUT if _invoked_via_cli else None)


CURRENT_PROVENANCE: OccurrenceWriterTerminalProvenanceMap = _ensure_evidence()
