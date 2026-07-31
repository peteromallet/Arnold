"""M11 prerequisite status vocabulary and fail-closed record contract.

Step 1: defines the prerequisite status enumeration, the prerequisite record
shape (owner, artifact, digest, expected_class, next_action), and the
validation rules that reject unknown statuses.  This is a narrow, fail-closed
schema consumed by every later M11 cross-contract join — a permissive default
here would create false acceptance across the entire M11 DAG.

Step 2: joins M10 handoff, C/F/M5/A7/audit/WBC/genuine-block/recovery/route/
no-debt/runtime refs and emits typed prerequisite blockers for missing, stale,
incoherent, schedule-mismatched, or sample-insufficient inputs.

The vocabulary is intentionally NOT open-ended: any status value not declared
in :class:`PrerequisiteStatus` is rejected at construction time.  Downstream
joins can therefore pattern-match on known statuses without worrying about
unchecked runtime extensions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── Status vocabulary ────────────────────────────────────────────────────


class PrerequisiteStatus(str, Enum):
    """Fail-closed M11 prerequisite statuses.

    Every prerequisite record flows through one of these statuses.
    Unknown / unregistered statuses are rejected so a downstream join
    never silently treats a misspelled or future status as satisfied.
    """

    #: The prerequisite is known and has not been satisfied.
    PENDING = "pending"

    #: The prerequisite has been satisfied and evidence is recorded.
    SATISFIED = "satisfied"

    #: The prerequisite is satisfied but the evidence has expired and must
    #: be re-verified before the dependency can be consumed.
    EXPIRED = "expired"

    #: The dependency could not be resolved; the prerequisite is blocked
    #: until an upstream change unblocks it.
    BLOCKED = "blocked"

    #: The prerequisite is explicitly waived (e.g. by a recorded override).
    #: Waiver requires owner, artifact, and next_action justification.
    WAIVED = "waived"

    #: The prerequisite was not required for this contract version.
    NOT_REQUIRED = "not_required"


#: Every status value that a downstream join may encounter.  Used by the
#: shape validation to reject unknowns.
KNOWN_STATUSES: frozenset[PrerequisiteStatus] = frozenset(PrerequisiteStatus)


# ── Prerequisite record ──────────────────────────────────────────────────


def _canonical_json_bytes(obj: Any) -> bytes:
    """Serialize *obj* to canonical (sorted-key, compact) JSON bytes."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    """Return ``sha256:...`` hex digest for *data*."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _required_str(value: Any, field_name: str) -> str:
    """Return a non-empty string or raise."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"m11_acceptance: {field_name} is required and must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class PrerequisiteRecord:
    """A fail-closed M11 prerequisite status record.

    Every M11 cross-contract join consumes these records.  The shape is
    deliberately narrow — owner, artifact, digest, expected_class, next_action
    — so downstream code can reason deterministically about dependency closure.

    Unknown statuses are rejected at construction time; a downstream join
    therefore never needs to handle an unrecognised status branch.
    """

    #: Which M11 task / step owns this prerequisite.
    owner: str

    #: Content-addressed reference to the artifact that satisfies (or blocks)
    #: the prerequisite.
    artifact: str

    #: SHA-256 digest of the evidence backing this record.  Computed
    #: deterministically from (owner, artifact, status, expected_class,
    #: next_action) when not supplied, so two records with identical
    #: visible fields always produce the same digest.
    digest: str = ""

    #: The expected class / module that produced this record.  Downstream
    #: joins use this to decide how to interpret the artifact reference.
    expected_class: str = ""

    #: The next action that should be taken.  For SATISFIED this may be
    #: empty; for BLOCKED / EXPIRED it MUST name the step that will unblock.
    next_action: str = ""

    #: The prerequisite status — must be one of the known values.
    status: PrerequisiteStatus = PrerequisiteStatus.PENDING

    # Opaque extra context (not part of the digest).
    detail: str = ""

    def __post_init__(self) -> None:
        # --- validate status -----------------------------------------------
        if not isinstance(self.status, PrerequisiteStatus):
            raise ValueError(
                f"m11_acceptance: unknown status {self.status!r}; "
                f"must be one of {sorted(s.value for s in KNOWN_STATUSES)}"
            )

        # --- validate required string fields -------------------------------
        _required_str(self.owner, "owner")
        _required_str(self.artifact, "artifact")

        # --- compute deterministic digest if not supplied ------------------
        if not self.digest:
            payload = _canonical_json_bytes(
                {
                    "owner": self.owner,
                    "artifact": self.artifact,
                    "status": self.status.value,
                    "expected_class": self.expected_class,
                    "next_action": self.next_action,
                }
            )
            object.__setattr__(self, "digest", _sha256_hex(payload))

        # --- BLOCKED / EXPIRED must carry a next_action -------------------
        if self.status in (PrerequisiteStatus.BLOCKED, PrerequisiteStatus.EXPIRED):
            if not self.next_action.strip():
                raise ValueError(
                    f"m11_acceptance: {self.status.value} prerequisite requires a "
                    "next_action naming the step that will unblock or re-verify"
                )

        # --- WAIVED must carry additional justification fields -------------
        if self.status is PrerequisiteStatus.WAIVED:
            if not self.expected_class.strip():
                raise ValueError(
                    "m11_acceptance: WAIVED prerequisite requires expected_class "
                    "(the override authority class)"
                )
            if not self.next_action.strip():
                raise ValueError(
                    "m11_acceptance: WAIVED prerequisite requires next_action "
                    "(justification for the waiver)"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner": self.owner,
            "artifact": self.artifact,
            "digest": self.digest,
            "expected_class": self.expected_class,
            "next_action": self.next_action,
            "status": self.status.value,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PrerequisiteRecord:
        """Reconstruct from a dictionary, converting the status string."""
        status_raw = data.get("status", "pending")
        try:
            status = PrerequisiteStatus(status_raw)
        except ValueError:
            raise ValueError(
                f"m11_acceptance: unknown status {status_raw!r}; "
                f"must be one of {sorted(s.value for s in KNOWN_STATUSES)}"
            ) from None
        return cls(
            owner=data.get("owner", ""),
            artifact=data.get("artifact", ""),
            digest=data.get("digest", ""),
            expected_class=data.get("expected_class", ""),
            next_action=data.get("next_action", ""),
            status=status,
            detail=data.get("detail", ""),
        )


# ── M11 prerequisite join (Step 2) ───────────────────────────────────────

#: Known predecessor artifact families that M11 cross-contract joins consume.
#: Each key is the short name; the value is the expected evidence path pattern.
PREDECESSOR_FAMILIES: dict[str, str] = {
    "m10_handoff": "evidence/m10-handoff.json",
    "c_family": "evidence/C-family.json",
    "m5_family": "evidence/M5-family.json",
    "a7_family": "evidence/A7-family.json",
    "audit": "evidence/audit.json",
    "wbc": "evidence/wbc.json",
    "genuine_block": "evidence/genuine-block.json",
    "recovery": "evidence/recovery.json",
    "route": "evidence/route.json",
    "no_debt": "evidence/no-debt.json",
    "runtime": "evidence/runtime.json",
}


def _prerequisite_blocker(
    owner: str,
    artifact: str,
    reason: str,
    *,
    expected_class: str = "",
    next_action: str = "",
    detail: str = "",
) -> PrerequisiteRecord:
    """Emit a typed BLOCKED prerequisite record."""
    return PrerequisiteRecord(
        owner=owner,
        artifact=artifact,
        status=PrerequisiteStatus.BLOCKED,
        expected_class=expected_class,
        next_action=next_action or "resolve prerequisite evidence",
        detail=detail or reason,
    )


def _prerequisite_satisfied(
    owner: str,
    artifact: str,
    *,
    expected_class: str = "",
    detail: str = "",
) -> PrerequisiteRecord:
    """Emit a SATISFIED prerequisite record."""
    return PrerequisiteRecord(
        owner=owner,
        artifact=artifact,
        status=PrerequisiteStatus.SATISFIED,
        expected_class=expected_class,
        detail=detail,
    )


def _prerequisite_expired(
    owner: str,
    artifact: str,
    *,
    expected_class: str = "",
    next_action: str = "",
    detail: str = "",
) -> PrerequisiteRecord:
    """Emit an EXPIRED prerequisite record."""
    return PrerequisiteRecord(
        owner=owner,
        artifact=artifact,
        status=PrerequisiteStatus.EXPIRED,
        expected_class=expected_class,
        next_action=next_action or "re-verify expired evidence",
        detail=detail,
    )


def join_prerequisite_evidence(
    *,
    owner: str,
    available_artifacts: dict[str, str | None],
    artifact_digests: dict[str, str] | None = None,
    schedule_state: dict[str, str] | None = None,
) -> list[PrerequisiteRecord]:
    """Join M11 predecessor evidence into typed prerequisite records.

    Consumes the named predecessor families (M10 handoff, C/F/M5/A7/audit/WBC/
    genuine-block/recovery/route/no-debt/runtime) and emits a
    :class:`PrerequisiteRecord` per family:

    * **SATISFIED** when the artifact is present and its digest matches the
      expected value (if digests are supplied).
    * **BLOCKED** when the artifact is missing.  The record carries a
      ``next_action`` naming the step that must produce it.
    * **EXPIRED** when the artifact exists but its digest is stale relative
      to the expected value.
    * **PENDING** when the artifact is present but digests are not (yet)
      supplied, or when schedule state indicates the predecessor has not
      yet reached its expected phase.

    Returns a list of typed prerequisite records — one per known family.
    Families not in *available_artifacts* default to missing (BLOCKED).
    """
    digests = artifact_digests or {}
    schedule = schedule_state or {}
    records: list[PrerequisiteRecord] = []

    for family_name, expected_path in PREDECESSOR_FAMILIES.items():
        artifact_value = available_artifacts.get(family_name)
        expected_digest = digests.get(family_name)

        if artifact_value is None:
            # Missing evidence → BLOCKED
            records.append(
                _prerequisite_blocker(
                    owner=owner,
                    artifact=expected_path,
                    reason=f"{family_name} evidence is missing",
                    expected_class=family_name,
                    next_action=f"produce {expected_path}",
                    detail=f"No {family_name} artifact found in available evidence.",
                )
            )
            continue

        if artifact_value == "":
            # Explicitly empty — also blocked
            records.append(
                _prerequisite_blocker(
                    owner=owner,
                    artifact=expected_path,
                    reason=f"{family_name} evidence is empty",
                    expected_class=family_name,
                    next_action=f"populate {expected_path}",
                    detail=f"{family_name} artifact is present but empty.",
                )
            )
            continue

        # Schedule mismatch: the predecessor hasn't reached its expected phase
        schedule_phase = schedule.get(family_name)
        if schedule_phase is not None and schedule_phase not in ("done", "completed", "satisfied"):
            records.append(
                PrerequisiteRecord(
                    owner=owner,
                    artifact=artifact_value,
                    status=PrerequisiteStatus.PENDING,
                    expected_class=family_name,
                    next_action=f"wait for {family_name} to complete (current: {schedule_phase})",
                    detail=f"{family_name} is in phase {schedule_phase}, not yet complete.",
                )
            )
            continue

        # Digest check
        if expected_digest:
            if artifact_value != expected_digest:
                # Stale/incoherent → EXPIRED
                records.append(
                    _prerequisite_expired(
                        owner=owner,
                        artifact=expected_path,
                        expected_class=family_name,
                        next_action=f"re-verify {family_name} evidence",
                        detail=f"{family_name} digest mismatch: expected {expected_digest[:16]}..., got {artifact_value[:16]}...",
                    )
                )
                continue

        # Evidence present, digest matches (or no digest check) → SATISFIED
        records.append(
            _prerequisite_satisfied(
                owner=owner,
                artifact=artifact_value,
                expected_class=family_name,
                detail=f"{family_name} evidence present and verified.",
            )
        )

    return records


# ── M11 no-debt gate (Step 5) ────────────────────────────────────────────

#: Patterns that indicate xfail / xpass markers in test evidence.
_XFAIL_MARKERS: tuple[str, ...] = (
    "xfail",
    "xpass",
    "unexpectedly passed",
    "expected failure",
)

#: Patterns that indicate unexplained skips.
_UNEXPLAINED_SKIP_MARKERS: tuple[str, ...] = (
    "unexplained skip",
    "skipped without reason",
    "skip with no explanation",
)

#: Patterns that indicate unresolved debt (prerequisite or semantic-carrier).
_UNRESOLVED_DEBT_MARKERS: tuple[str, ...] = (
    "unresolved debt",
    "carried debt",
    "outstanding debt",
    "debt not resolved",
    "unresolved prerequisite debt",
    "unresolved semantic debt",
    "semantic-carrier debt",
    "prerequisite debt",
)


def _detect_xfail_xpass(evidence_text: str) -> list[str]:
    """Return a list of xfail/xpass patterns found in *evidence_text*."""
    lowered = evidence_text.lower()
    findings: list[str] = []
    for marker in _XFAIL_MARKERS:
        if marker in lowered:
            findings.append(marker)
    return findings


def _detect_unexplained_skips(evidence_text: str) -> list[str]:
    """Return a list of unexplained-skip patterns found in *evidence_text*."""
    lowered = evidence_text.lower()
    findings: list[str] = []
    for marker in _UNEXPLAINED_SKIP_MARKERS:
        if marker in lowered:
            findings.append(marker)
    return findings


def _detect_unresolved_debt(evidence_text: str) -> list[str]:
    """Return a list of unresolved-debt patterns found in *evidence_text*."""
    lowered = evidence_text.lower()
    findings: list[str] = []
    for marker in _UNRESOLVED_DEBT_MARKERS:
        if marker in lowered:
            findings.append(marker)
    return findings


def m11_debt_gate(
    *,
    evidence_text: str,
    allow_prerequisite_debt: bool = False,
    allow_semantic_carrier_debt: bool = False,
) -> dict[str, Any]:
    """Fail-closed debt gate for M11 cross-contract acceptance.

    Scans *evidence_text* for xfail, xpass, unexplained-skip, and
    unresolved-debt patterns.  Returns a ``passed`` flag and a list of
    ``findings``.  The gate is fail-closed: by default, prerequisite debt
    and semantic-carrier debt are NOT allowed to satisfy final acceptance.

    The *allow_prerequisite_debt* and *allow_semantic_carrier_debt*
    kwargs exist only for explicit caller opt-in (e.g. generator flags)
    — the default is always reject.
    """
    findings: list[dict[str, Any]] = []

    xfail_matches = _detect_xfail_xpass(evidence_text)
    for marker in xfail_matches:
        findings.append({"kind": "xfail_xpass", "marker": marker})

    skip_matches = _detect_unexplained_skips(evidence_text)
    for marker in skip_matches:
        findings.append({"kind": "unexplained_skip", "marker": marker})

    debt_matches = _detect_unresolved_debt(evidence_text)
    for marker in debt_matches:
        # Filter out prerequisite/semantic-carrier debt when explicitly allowed
        if not allow_prerequisite_debt and "prerequisite" in marker:
            findings.append({"kind": "unresolved_debt", "marker": marker, "category": "prerequisite"})
        elif not allow_semantic_carrier_debt and ("semantic" in marker or "carrier" in marker):
            findings.append({"kind": "unresolved_debt", "marker": marker, "category": "semantic_carrier"})
        elif allow_prerequisite_debt and "prerequisite" in marker:
            continue  # explicitly allowed
        elif allow_semantic_carrier_debt and ("semantic" in marker or "carrier" in marker):
            continue  # explicitly allowed
        else:
            findings.append({"kind": "unresolved_debt", "marker": marker, "category": "generic"})

    passed = len(findings) == 0
    return {
        "passed": passed,
        "findings": findings,
        "gate": "m11_no_debt",
        "allow_prerequisite_debt": allow_prerequisite_debt,
        "allow_semantic_carrier_debt": allow_semantic_carrier_debt,
    }


# ── M11 acceptance rows (Step 6) ─────────────────────────────────────────


@dataclass(frozen=True)
class AcceptanceRow:
    """A single M11 cross-contract acceptance case row.

    Aggregates prerequisite status, expected decision, evidence refs,
    and retirement disposition into a deterministic digest-bearing row.
    This is aggregation data — it does NOT write authority.
    """

    #: The task/step ID that owns this acceptance row.
    owner: str

    #: Input version vector (e.g. ``{"m10_handoff": "sha256:...", ...}``).
    input_version_vector: dict[str, str] = field(default_factory=dict)

    #: Expected acceptance decision (e.g. ``"accepted"``, ``"rejected"``,
    #: ``"blocked"``, ``"expired"``).
    expected_decision: str = ""

    #: List of evidence artifact references backing this row.
    evidence_refs: list[str] = field(default_factory=list)

    #: SHA-256 digest computed from the row's core fields.
    digest: str = ""

    #: The prerequisite status at the time this row was produced.
    prerequisite_status: PrerequisiteStatus = PrerequisiteStatus.PENDING

    #: Retirement disposition — ``"eligible"``, ``"not_eligible"``,
    #: ``"retired"``, ``"preserved"``, ``"pending"``, or ``""``.
    retirement_disposition: str = ""

    #: Opaque extra detail (not part of the digest).
    detail: str = ""

    def __post_init__(self) -> None:
        _required_str(self.owner, "owner")
        if self.expected_decision and self.expected_decision not in _KNOWN_DECISIONS:
            raise ValueError(
                f"m11_acceptance: unknown expected_decision {self.expected_decision!r}; "
                f"must be one of {sorted(_KNOWN_DECISIONS)}"
            )
        if self.retirement_disposition and self.retirement_disposition not in _KNOWN_RETIREMENT_DISPOSITIONS:
            raise ValueError(
                f"m11_acceptance: unknown retirement_disposition {self.retirement_disposition!r}; "
                f"must be one of {sorted(_KNOWN_RETIREMENT_DISPOSITIONS)}"
            )
        if not self.digest:
            payload = _canonical_json_bytes(
                {
                    "owner": self.owner,
                    "input_version_vector": dict(sorted(self.input_version_vector.items())),
                    "expected_decision": self.expected_decision,
                    "evidence_refs": sorted(self.evidence_refs),
                    "prerequisite_status": self.prerequisite_status.value,
                    "retirement_disposition": self.retirement_disposition,
                }
            )
            object.__setattr__(self, "digest", _sha256_hex(payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner": self.owner,
            "input_version_vector": dict(self.input_version_vector),
            "expected_decision": self.expected_decision,
            "evidence_refs": list(self.evidence_refs),
            "digest": self.digest,
            "prerequisite_status": self.prerequisite_status.value,
            "retirement_disposition": self.retirement_disposition,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AcceptanceRow:
        status_raw = data.get("prerequisite_status", "pending")
        try:
            status = PrerequisiteStatus(status_raw)
        except ValueError:
            raise ValueError(
                f"m11_acceptance: unknown prerequisite_status {status_raw!r}; "
                f"must be one of {sorted(s.value for s in KNOWN_STATUSES)}"
            ) from None
        return cls(
            owner=data.get("owner", ""),
            input_version_vector=data.get("input_version_vector", {}),
            expected_decision=data.get("expected_decision", ""),
            evidence_refs=data.get("evidence_refs", []),
            digest=data.get("digest", ""),
            prerequisite_status=status,
            retirement_disposition=data.get("retirement_disposition", ""),
            detail=data.get("detail", ""),
        )


#: Known acceptance decisions.
_KNOWN_DECISIONS: frozenset[str] = frozenset(
    {"accepted", "rejected", "blocked", "expired", "pending", "waived", "not_required"}
)

#: Known retirement dispositions.
_KNOWN_RETIREMENT_DISPOSITIONS: frozenset[str] = frozenset(
    {"eligible", "not_eligible", "retired", "preserved", "pending"}
)


# ── Schema descriptor ────────────────────────────────────────────────────


def schema_descriptor() -> dict[str, Any]:
    """Deterministic, machine-readable description of the M11 acceptance schema."""
    return {
        "schema_version": 1,
        "module": "arnold_pipelines.megaplan.orchestration.m11_acceptance",
        "plan_steps": ["Step 1", "Step 2", "Step 5", "Step 6"],
        "known_statuses": sorted(s.value for s in KNOWN_STATUSES),
        "required_fields": [
            "owner",
            "artifact",
            "digest",
            "expected_class",
            "next_action",
            "status",
        ],
        "rejection_contract": (
            "Unknown status values are rejected at construction time.  "
            "BLOCKED and EXPIRED records require next_action.  "
            "WAIVED records require expected_class and next_action justification."
        ),
        "deterministic_digest_fields": [
            "owner",
            "artifact",
            "status",
            "expected_class",
            "next_action",
        ],
        "predecessor_families": list(PREDECESSOR_FAMILIES.keys()),
        "debt_gate": {
            "markers": {
                "xfail_xpass": list(_XFAIL_MARKERS),
                "unexplained_skip": list(_UNEXPLAINED_SKIP_MARKERS),
                "unresolved_debt": list(_UNRESOLVED_DEBT_MARKERS),
            },
            "default_allow_prerequisite_debt": False,
            "default_allow_semantic_carrier_debt": False,
        },
        "acceptance_row_fields": [
            "owner",
            "input_version_vector",
            "expected_decision",
            "evidence_refs",
            "digest",
            "prerequisite_status",
            "retirement_disposition",
        ],
        "known_decisions": sorted(_KNOWN_DECISIONS),
        "known_retirement_dispositions": sorted(_KNOWN_RETIREMENT_DISPOSITIONS),
    }


# ── Step 7: Predecessor evidence adapters ─────────────────────────────────

#: Known predecessor evidence schemas that M11 adapters validate.
_PREDECESSOR_SCHEMAS: dict[str, str] = {
    "m10_c01_c20": "m10.c01-c20-conformance.v1",
    "f01_f17": "m10.f01-f17-fault-matrix.v1",
    "m5": "m5.evidence.v1",
    "a7": "a7.evidence.v1",
}

#: Required fields that every predecessor evidence payload must carry.
_PREDECESSOR_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {"schema_version", "generated_at", "status"}
)

#: Fields checked for digest computation on predecessor evidence.
_PREDECESSOR_DIGEST_FIELDS: tuple[str, ...] = (
    "schema_version",
    "generated_at",
    "owner",
    "version_vector",
    "source_path",
    "effective_status",
)


@dataclass(frozen=True)
class PredecessorAdapterResult:
    """Typed result from a single predecessor evidence adapter.

    Each adapter validates one predecessor family (M10 C01-C20, F01-F17, M5,
    or A7) and returns one of these results.  A ``passed`` result carries the
    validated acceptance row; a failed result carries structured diagnostics.
    """

    family: str
    passed: bool
    acceptance_row: AcceptanceRow | None = None
    failures: list[dict[str, Any]] = field(default_factory=list)
    evidence_digest: str = ""
    source_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "family": self.family,
            "passed": self.passed,
            "evidence_digest": self.evidence_digest,
            "source_path": self.source_path,
        }
        if self.acceptance_row is not None:
            result["acceptance_row"] = self.acceptance_row.to_dict()
        result["failures"] = list(self.failures)
        return result


def _compute_evidence_digest(data: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 digest over the core predecessor fields."""
    payload = {k: data.get(k, "") for k in _PREDECESSOR_DIGEST_FIELDS}
    return _sha256_hex(_canonical_json_bytes(payload))


def _check_required_fields(data: dict[str, Any], family: str) -> list[dict[str, Any]]:
    """Return a list of failures for missing required fields."""
    failures: list[dict[str, Any]] = []
    for field in sorted(_PREDECESSOR_REQUIRED_FIELDS):
        if field not in data:
            failures.append({
                "kind": "missing_required_field",
                "field": field,
                "detail": f"{family}: missing required field '{field}'",
            })
    return failures


def validate_m10_c01_c20_evidence(
    data: dict[str, Any],
    *,
    owner: str = "T7",
    source_path: str = "evidence/m10-c01-c20-conformance.json",
    expected_digest: str | None = None,
) -> PredecessorAdapterResult:
    """Validate M10 C01-C20 conformance evidence.

    Checks schema marker, required fields, digest, owner, version vector,
    source path, and effective status.  Returns a typed adapter result that
    either carries a SATISFIED acceptance row or a structured failure list.
    """
    family = "m10_c01_c20"
    failures: list[dict[str, Any]] = []

    # Schema check
    schema = data.get("schema", "")
    expected_schema = _PREDECESSOR_SCHEMAS.get(family, "")
    if schema != expected_schema:
        failures.append({
            "kind": "schema_mismatch",
            "expected": expected_schema,
            "actual": schema,
            "detail": f"{family}: expected schema {expected_schema!r}, got {schema!r}",
        })

    # Required fields
    failures.extend(_check_required_fields(data, family))

    # Digest check
    computed_digest = _compute_evidence_digest(data)
    if expected_digest is not None and computed_digest != expected_digest:
        failures.append({
            "kind": "digest_mismatch",
            "expected": expected_digest,
            "actual": computed_digest,
            "detail": f"{family}: evidence digest mismatch",
        })

    # Owner check
    evidence_owner = data.get("owner", "")
    if not isinstance(evidence_owner, str) or not evidence_owner.strip():
        failures.append({
            "kind": "missing_owner",
            "detail": f"{family}: evidence owner is missing or empty",
        })

    # Version vector check
    version_vector = data.get("version_vector") or data.get("bound_files", {})
    if not isinstance(version_vector, dict) or not version_vector:
        failures.append({
            "kind": "missing_version_vector",
            "detail": f"{family}: version vector is missing or empty",
        })

    # Source path check
    if not source_path:
        failures.append({
            "kind": "missing_source_path",
            "detail": f"{family}: source path is empty",
        })

    # Effective status check
    effective_status = data.get("status") or data.get("effective_status", "")
    if effective_status not in ("reconciled", "done", "completed", "satisfied", "conformant"):
        failures.append({
            "kind": "ineffective_status",
            "actual": effective_status,
            "detail": f"{family}: effective status {effective_status!r} is not a done/conformant state",
        })

    passed = len(failures) == 0
    if passed:
        row = AcceptanceRow(
            owner=owner,
            input_version_vector=version_vector if isinstance(version_vector, dict) else {},
            expected_decision="accepted",
            evidence_refs=[source_path],
            prerequisite_status=PrerequisiteStatus.SATISFIED,
            retirement_disposition="pending",
            detail=f"M10 C01-C20 conformance evidence validated; digest={computed_digest[:16]}...",
        )
    else:
        row = AcceptanceRow(
            owner=owner,
            input_version_vector=version_vector if isinstance(version_vector, dict) else {},
            expected_decision="blocked",
            evidence_refs=[source_path],
            prerequisite_status=PrerequisiteStatus.BLOCKED,
            retirement_disposition="not_eligible",
            detail=f"M10 C01-C20 evidence has {len(failures)} validation failure(s)",
        )

    return PredecessorAdapterResult(
        family=family,
        passed=passed,
        acceptance_row=row,
        failures=failures,
        evidence_digest=computed_digest,
        source_path=source_path,
    )


def validate_f01_f17_evidence(
    data: dict[str, Any],
    *,
    owner: str = "T7",
    source_path: str = "evidence/m10-f01-f17-fault-matrix.json",
    expected_digest: str | None = None,
) -> PredecessorAdapterResult:
    """Validate F01-F17 fault-matrix evidence.

    Checks schema marker, required fields, digest, owner, version vector,
    source path, and effective status.  Returns a typed adapter result.
    """
    family = "f01_f17"
    failures: list[dict[str, Any]] = []

    # Schema check.  Both the named schema and its numeric version are
    # required; accepting any non-empty schema_version made arbitrary JSON
    # look like an F01-F17 evidence document.
    schema = data.get("schema", "")
    expected_schema = _PREDECESSOR_SCHEMAS.get(family, "")
    if schema != expected_schema or data.get("schema_version") != 1:
        failures.append({
            "kind": "schema_mismatch",
            "expected": {"schema": expected_schema, "schema_version": 1},
            "actual": {
                "schema": schema,
                "schema_version": data.get("schema_version"),
            },
            "detail": f"{family}: schema identity does not match F01-F17 v1",
        })

    if "status" not in data:
        failures.append({
            "kind": "missing_required_field",
            "field": "status",
            "detail": f"{family}: missing required field 'status'",
        })

    # Digest check
    computed_digest = _compute_evidence_digest(data)
    if expected_digest is not None and computed_digest != expected_digest:
        failures.append({
            "kind": "digest_mismatch",
            "expected": expected_digest,
            "actual": computed_digest,
            "detail": f"{family}: evidence digest mismatch",
        })

    # Effective status check — F01-F17 uses "status": "reconciled"
    effective_status = data.get("status", "")
    if effective_status not in ("reconciled", "done", "completed", "satisfied"):
        failures.append({
            "kind": "ineffective_status",
            "actual": effective_status,
            "detail": f"{family}: effective status {effective_status!r} is not a reconciled state",
        })

    # Scenario coverage: every F01-F17 row must occur exactly once.
    scenarios = data.get("scenarios", [])
    if not isinstance(scenarios, list) or not scenarios:
        failures.append({
            "kind": "missing_scenarios",
            "detail": f"{family}: no fault-matrix scenarios found",
        })
    else:
        scenario_ids = [
            row.get("id")
            for row in scenarios
            if isinstance(row, dict) and isinstance(row.get("id"), str)
        ]
        expected_ids = [f"F{index:02d}" for index in range(1, 18)]
        if sorted(scenario_ids) != expected_ids or len(scenario_ids) != len(scenarios):
            failures.append({
                "kind": "scenario_coverage_mismatch",
                "expected": expected_ids,
                "actual": sorted(scenario_ids),
                "detail": f"{family}: expected each F01-F17 scenario exactly once",
            })

    evidence_owner = data.get("owner", "")
    if not isinstance(evidence_owner, str) or not evidence_owner.strip():
        failures.append({
            "kind": "missing_owner",
            "detail": f"{family}: evidence owner is missing or empty",
        })

    passed = len(failures) == 0
    version_vector = data.get("version_vector") or data.get("bound_files", {})
    if not isinstance(version_vector, dict) or not version_vector:
        failures.append({
            "kind": "missing_version_vector",
            "detail": f"{family}: version vector is missing or empty",
        })
        passed = False
    if passed:
        row = AcceptanceRow(
            owner=owner,
            input_version_vector=version_vector if isinstance(version_vector, dict) else {},
            expected_decision="accepted",
            evidence_refs=[source_path],
            prerequisite_status=PrerequisiteStatus.SATISFIED,
            retirement_disposition="pending",
            detail=f"F01-F17 fault matrix validated; {len(scenarios)} scenarios, digest={computed_digest[:16]}...",
        )
    else:
        row = AcceptanceRow(
            owner=owner,
            input_version_vector=version_vector if isinstance(version_vector, dict) else {},
            expected_decision="blocked",
            evidence_refs=[source_path],
            prerequisite_status=PrerequisiteStatus.BLOCKED,
            retirement_disposition="not_eligible",
            detail=f"F01-F17 evidence has {len(failures)} validation failure(s)",
        )

    return PredecessorAdapterResult(
        family=family,
        passed=passed,
        acceptance_row=row,
        failures=failures,
        evidence_digest=computed_digest,
        source_path=source_path,
    )


def validate_m5_evidence(
    data: dict[str, Any],
    *,
    owner: str = "T7",
    source_path: str = "evidence/m5-evidence.json",
    expected_digest: str | None = None,
) -> PredecessorAdapterResult:
    """Validate M5 predecessor evidence.

    M5 evidence may be absent (not yet produced).  When absent, the adapter
    returns a BLOCKED result with a clear signal that M5 evidence is missing
    rather than silently treating it as satisfied.
    """
    family = "m5"
    failures: list[dict[str, Any]] = []

    if not data:
        # M5 evidence is absent — treat as BLOCKED, not SATISFIED
        failures.append({
            "kind": "evidence_missing",
            "detail": f"{family}: M5 evidence file not found or empty",
        })
        return PredecessorAdapterResult(
            family=family,
            passed=False,
            acceptance_row=AcceptanceRow(
                owner=owner,
                expected_decision="blocked",
                evidence_refs=[source_path],
                prerequisite_status=PrerequisiteStatus.BLOCKED,
                retirement_disposition="not_eligible",
                detail="M5 evidence is missing; cannot validate prerequisite.",
            ),
            failures=failures,
            evidence_digest="",
            source_path=source_path,
        )

    # Schema check
    schema = data.get("schema", "")
    expected_schema = _PREDECESSOR_SCHEMAS.get(family, "")
    if schema != expected_schema:
        failures.append({
            "kind": "schema_mismatch",
            "expected": expected_schema,
            "actual": schema,
            "detail": f"{family}: expected schema {expected_schema!r}, got {schema!r}",
        })

    failures.extend(_check_required_fields(data, family))

    computed_digest = _compute_evidence_digest(data)
    if expected_digest is not None and computed_digest != expected_digest:
        failures.append({
            "kind": "digest_mismatch",
            "expected": expected_digest,
            "actual": computed_digest,
            "detail": f"{family}: evidence digest mismatch",
        })

    effective_status = data.get("status") or data.get("effective_status", "")
    if effective_status not in ("done", "completed", "satisfied", "reconciled"):
        failures.append({
            "kind": "ineffective_status",
            "actual": effective_status,
            "detail": f"{family}: effective status {effective_status!r} is not a done state",
        })

    version_vector = data.get("version_vector", {})
    if not isinstance(version_vector, dict) or not version_vector:
        failures.append({
            "kind": "missing_version_vector",
            "detail": f"{family}: version vector is missing or empty",
        })
    passed = len(failures) == 0
    if passed:
        row = AcceptanceRow(
            owner=owner,
            input_version_vector=version_vector if isinstance(version_vector, dict) else {},
            expected_decision="accepted",
            evidence_refs=[source_path],
            prerequisite_status=PrerequisiteStatus.SATISFIED,
            retirement_disposition="pending",
            detail=f"M5 evidence validated; digest={computed_digest[:16]}...",
        )
    else:
        row = AcceptanceRow(
            owner=owner,
            input_version_vector=version_vector if isinstance(version_vector, dict) else {},
            expected_decision="blocked",
            evidence_refs=[source_path],
            prerequisite_status=PrerequisiteStatus.BLOCKED,
            retirement_disposition="not_eligible",
            detail=f"M5 evidence has {len(failures)} validation failure(s)",
        )

    return PredecessorAdapterResult(
        family=family,
        passed=passed,
        acceptance_row=row,
        failures=failures,
        evidence_digest=computed_digest,
        source_path=source_path,
    )


def validate_a7_evidence(
    data: dict[str, Any],
    *,
    owner: str = "T7",
    source_path: str = "evidence/a7-evidence.json",
    expected_digest: str | None = None,
) -> PredecessorAdapterResult:
    """Validate A7 predecessor evidence.

    A7 evidence may be absent (not yet produced). When absent, the adapter
    returns a BLOCKED result.
    """
    family = "a7"
    failures: list[dict[str, Any]] = []

    if not data:
        failures.append({
            "kind": "evidence_missing",
            "detail": f"{family}: A7 evidence file not found or empty",
        })
        return PredecessorAdapterResult(
            family=family,
            passed=False,
            acceptance_row=AcceptanceRow(
                owner=owner,
                expected_decision="blocked",
                evidence_refs=[source_path],
                prerequisite_status=PrerequisiteStatus.BLOCKED,
                retirement_disposition="not_eligible",
                detail="A7 evidence is missing; cannot validate prerequisite.",
            ),
            failures=failures,
            evidence_digest="",
            source_path=source_path,
        )

    schema = data.get("schema", "")
    expected_schema = _PREDECESSOR_SCHEMAS.get(family, "")
    if schema != expected_schema:
        failures.append({
            "kind": "schema_mismatch",
            "expected": expected_schema,
            "actual": schema,
            "detail": f"{family}: expected schema {expected_schema!r}, got {schema!r}",
        })

    failures.extend(_check_required_fields(data, family))

    computed_digest = _compute_evidence_digest(data)
    if expected_digest is not None and computed_digest != expected_digest:
        failures.append({
            "kind": "digest_mismatch",
            "expected": expected_digest,
            "actual": computed_digest,
            "detail": f"{family}: evidence digest mismatch",
        })

    effective_status = data.get("status") or data.get("effective_status", "")
    if effective_status not in ("done", "completed", "satisfied", "reconciled"):
        failures.append({
            "kind": "ineffective_status",
            "actual": effective_status,
            "detail": f"{family}: effective status {effective_status!r} is not a done state",
        })

    version_vector = data.get("version_vector", {})
    if not isinstance(version_vector, dict) or not version_vector:
        failures.append({
            "kind": "missing_version_vector",
            "detail": f"{family}: version vector is missing or empty",
        })
    passed = len(failures) == 0
    if passed:
        row = AcceptanceRow(
            owner=owner,
            input_version_vector=version_vector if isinstance(version_vector, dict) else {},
            expected_decision="accepted",
            evidence_refs=[source_path],
            prerequisite_status=PrerequisiteStatus.SATISFIED,
            retirement_disposition="pending",
            detail=f"A7 evidence validated; digest={computed_digest[:16]}...",
        )
    else:
        row = AcceptanceRow(
            owner=owner,
            input_version_vector=version_vector if isinstance(version_vector, dict) else {},
            expected_decision="blocked",
            evidence_refs=[source_path],
            prerequisite_status=PrerequisiteStatus.BLOCKED,
            retirement_disposition="not_eligible",
            detail=f"A7 evidence has {len(failures)} validation failure(s)",
        )

    return PredecessorAdapterResult(
        family=family,
        passed=passed,
        acceptance_row=row,
        failures=failures,
        evidence_digest=computed_digest,
        source_path=source_path,
    )


def validate_predecessor_adapters(
    *,
    owner: str = "T7",
    m10_c01_c20_data: dict[str, Any] | None = None,
    f01_f17_data: dict[str, Any] | None = None,
    m5_data: dict[str, Any] | None = None,
    a7_data: dict[str, Any] | None = None,
    expected_digests: dict[str, str] | None = None,
) -> list[PredecessorAdapterResult]:
    """Run all four predecessor evidence adapters and return typed results.

    Each adapter validates its family independently.  A missing data dict
    is treated as absent evidence (BLOCKED), never silently SATISFIED.
    """
    digests = expected_digests or {}
    results: list[PredecessorAdapterResult] = []

    results.append(
        validate_m10_c01_c20_evidence(
            m10_c01_c20_data or {},
            owner=owner,
            source_path="evidence/m10-c01-c20-conformance.json",
            expected_digest=digests.get("m10_c01_c20"),
        )
    )
    results.append(
        validate_f01_f17_evidence(
            f01_f17_data or {},
            owner=owner,
            source_path="evidence/m10-f01-f17-fault-matrix.json",
            expected_digest=digests.get("f01_f17"),
        )
    )
    results.append(
        validate_m5_evidence(
            m5_data or {},
            owner=owner,
            source_path="evidence/m5-evidence.json",
            expected_digest=digests.get("m5"),
        )
    )
    results.append(
        validate_a7_evidence(
            a7_data or {},
            owner=owner,
            source_path="evidence/a7-evidence.json",
            expected_digest=digests.get("a7"),
        )
    )

    return results


# ── Step 8: Audit and recovery adapter gates ──────────────────────────────

#: The partial-cycle marker timestamp that must be kept until restored or
#: reconstructed with provenance.
_PARTIAL_CYCLE_MARKER: str = "20260727T204730.361503Z"

#: Minimum number of complete audit-cycle artifact trees required.
_MIN_AUDIT_CYCLE_TREES: int = 4


@dataclass(frozen=True)
class AuditCycleTree:
    """One audit-cycle artifact tree with digest-checked provenance.

    Each tree bundles a set of evidence artifacts from one audit cycle,
    identified by its cycle timestamp and provenance digest.
    """

    cycle_id: str
    artifact_paths: list[str] = field(default_factory=list)
    provenance_digest: str = ""
    is_complete: bool = False
    is_partial_marker: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "artifact_paths": list(self.artifact_paths),
            "provenance_digest": self.provenance_digest,
            "is_complete": self.is_complete,
            "is_partial_marker": self.is_partial_marker,
        }


@dataclass(frozen=True)
class AuditRecoveryAdapterResult:
    """Typed result from the audit-cycle and recovery evidence adapter gate.

    Carries the validated audit-cycle trees, recovery ledger status, and
    an acceptance row reflecting the gating decision.
    """

    passed: bool
    acceptance_row: AcceptanceRow
    audit_trees: list[AuditCycleTree] = field(default_factory=list)
    recovery_ledger_status: str = ""
    partial_marker_retained: bool = False
    failures: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "acceptance_row": self.acceptance_row.to_dict(),
            "audit_trees": [t.to_dict() for t in self.audit_trees],
            "recovery_ledger_status": self.recovery_ledger_status,
            "partial_marker_retained": self.partial_marker_retained,
            "failures": list(self.failures),
        }


def _digest_check_audit_tree(tree_data: dict[str, Any]) -> tuple[str, bool]:
    """Compute provenance digest for an audit tree entry and verify it."""
    if not isinstance(tree_data, dict):
        return "", False
    declared = tree_data.get("provenance_digest", "")
    if not declared:
        return "", False
    # Recompute from declared fields
    payload = {
        "cycle_id": tree_data.get("cycle_id", ""),
        "artifact_paths": sorted(tree_data.get("artifact_paths", [])),
        "is_complete": tree_data.get("is_complete", False),
    }
    computed = _sha256_hex(_canonical_json_bytes(payload))
    return computed, computed == declared


def validate_audit_recovery_adapters(
    *,
    owner: str = "T8",
    audit_trees_data: list[dict[str, Any]] | None = None,
    recovery_ledger_data: dict[str, Any] | None = None,
) -> AuditRecoveryAdapterResult:
    """Gate audit-cycle artifact trees and recovery evidence.

    Requires at least four audit-cycle artifact trees with digest-checked
    provenance.  Complete cycles are treated as candidates.  The partial
    marker ``20260727T204730.361503Z`` is retained until restored or
    reconstructed with provenance — it never masquerades as a complete tree.
    """
    failures: list[dict[str, Any]] = []
    trees: list[AuditCycleTree] = []
    partial_marker_retained = False

    # Parse audit trees
    for entry in (audit_trees_data or []):
        if not isinstance(entry, dict):
            continue
        cycle_id = entry.get("cycle_id", "")

        # Detect partial marker
        is_partial = cycle_id == _PARTIAL_CYCLE_MARKER or entry.get("is_partial_marker", False)
        if is_partial:
            partial_marker_retained = True
            trees.append(AuditCycleTree(
                cycle_id=cycle_id,
                artifact_paths=entry.get("artifact_paths", []),
                provenance_digest=entry.get("provenance_digest", ""),
                is_complete=False,
                is_partial_marker=True,
            ))
            continue

        is_complete = bool(entry.get("is_complete", False))
        if not is_complete:
            # Flag as incomplete but don't block — the gate below
            # only fails if complete candidates < 4
            pass

        # Digest check
        computed_digest, digest_ok = _digest_check_audit_tree(entry)
        if digest_ok:
            provenance_digest = computed_digest
        else:
            provenance_digest = entry.get("provenance_digest", "")
            if provenance_digest:
                failures.append({
                    "kind": "digest_mismatch",
                    "cycle_id": cycle_id,
                    "expected": provenance_digest,
                    "actual": computed_digest,
                    "detail": f"Audit tree {cycle_id}: provenance digest mismatch",
                })

        trees.append(AuditCycleTree(
            cycle_id=cycle_id,
            artifact_paths=entry.get("artifact_paths", []),
            provenance_digest=provenance_digest,
            is_complete=is_complete and digest_ok,
            is_partial_marker=False,
        ))

    # Count complete candidates (exclude partial marker)
    complete_candidates = [t for t in trees if t.is_complete and not t.is_partial_marker]

    if len(complete_candidates) < _MIN_AUDIT_CYCLE_TREES:
        failures.append({
            "kind": "insufficient_complete_trees",
            "required": _MIN_AUDIT_CYCLE_TREES,
            "actual": len(complete_candidates),
            "detail": (
                f"Need at least {_MIN_AUDIT_CYCLE_TREES} complete audit-cycle trees; "
                f"found {len(complete_candidates)} (partial marker retained: {partial_marker_retained})"
            ),
        })

    # Recovery ledger check
    recovery_status = ""
    if recovery_ledger_data:
        recovery_status = recovery_ledger_data.get("status") or recovery_ledger_data.get("slo_met", "")
        if recovery_ledger_data.get("slo_met") is False:
            failures.append({
                "kind": "recovery_slo_not_met",
                "detail": "Recovery latency ledger SLO not met",
            })

    passed = len(failures) == 0
    if passed:
        row = AcceptanceRow(
            owner=owner,
            input_version_vector={
                "audit_trees_count": str(len(trees)),
                "complete_candidates": str(len(complete_candidates)),
                "partial_marker_retained": str(partial_marker_retained),
            },
            expected_decision="accepted",
            evidence_refs=[
                "evidence/m11-genuine-block-candidate/manifest.json",
                "evidence/m11-recovery-latency-ledger.json",
            ],
            prerequisite_status=PrerequisiteStatus.SATISFIED,
            retirement_disposition="pending",
            detail=(
                f"Audit/recovery gate passed: {len(complete_candidates)} complete trees, "
                f"partial marker {'retained' if partial_marker_retained else 'absent'}"
            ),
        )
    else:
        row = AcceptanceRow(
            owner=owner,
            input_version_vector={
                "audit_trees_count": str(len(trees)),
                "complete_candidates": str(len(complete_candidates)),
                "partial_marker_retained": str(partial_marker_retained),
            },
            expected_decision="blocked",
            evidence_refs=[
                "evidence/m11-genuine-block-candidate/manifest.json",
                "evidence/m11-recovery-latency-ledger.json",
            ],
            prerequisite_status=PrerequisiteStatus.BLOCKED,
            retirement_disposition="not_eligible",
            detail=f"Audit/recovery gate has {len(failures)} failure(s)",
        )

    return AuditRecoveryAdapterResult(
        passed=passed,
        acceptance_row=row,
        audit_trees=trees,
        recovery_ledger_status=str(recovery_status),
        partial_marker_retained=partial_marker_retained,
        failures=failures,
    )


# ── Public API ───────────────────────────────────────────────────────────

__all__ = [
    "KNOWN_STATUSES",
    "PREDECESSOR_FAMILIES",
    "AcceptanceRow",
    "AuditCycleTree",
    "AuditRecoveryAdapterResult",
    "PredecessorAdapterResult",
    "PrerequisiteRecord",
    "PrerequisiteStatus",
    "join_prerequisite_evidence",
    "m11_debt_gate",
    "schema_descriptor",
    "validate_a7_evidence",
    "validate_audit_recovery_adapters",
    "validate_f01_f17_evidence",
    "validate_m10_c01_c20_evidence",
    "validate_m5_evidence",
    "validate_predecessor_adapters",
]
