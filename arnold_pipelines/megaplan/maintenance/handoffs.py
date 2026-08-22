"""Strict approval-aware Maintenance handoff registry (M2 trust gate).

The registry is the explicit trust gate for every M6A/M7/M10/M11/C1/C2/S1/S2R
source consumed by the Maintenance adapters (T6/T7) and reported by the M3
handoff view (T22).  It is strictly declarative and read-only: it has no
mutation authority, never discovers trust implicitly, and never guesses an
open production value.

SC5 invariant (fail-closed resolution)::

    * an absent handoff row resolves to typed UNKNOWN with reason
      MISSING_HANDOFF and approval UNKNOWN — absence is never acceptance;
    * an unapproved row resolves to typed UNKNOWN with approval
      PENDING_HUMAN_APPROVAL (or UNKNOWN) — pending is never acceptance;
    * an APPROVED row that is missing required production data (digest, and
      WBC incarnation/restore/high-water coordinates where required)
      resolves to typed UNKNOWN with reason MISSING_FIELD — a claimed
      approval cannot substitute for missing data;
    * only a complete AND approved row resolves to ACCEPTED evidence.

Every open production value (digests, WBC store incarnation/restore/high-
water coordinates, approval state) stays explicit ``null``/pending in the
candidate data; the loader never fills a value in.

All models are frozen, forbid unknown fields, and round-trip through the
single canonical codec (``canonical_dumps`` / ``strict_loads``).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)

from arnold_pipelines.megaplan.maintenance.contracts import EVIDENCE_PRECEDENCE_VERSION
from arnold_pipelines.megaplan.maintenance.identity import (
    MAINTENANCE_SCHEMA_VERSION,
    UtcTime,
    canonical_digest,
    canonical_dumps,
    strict_loads,
)

#: The fixed handoff id set this registry must cover.  A registry missing any
#: of these ids — or carrying an unknown id — fails to load: the trust gate
#: itself must be complete and closed.
HANDOFF_IDS: tuple[str, ...] = ("M6A", "M7", "M10", "M11", "C1", "C2", "S1", "S2R")

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


# ---------------------------------------------------------------------------
# Approval state
# ---------------------------------------------------------------------------


class ApprovalState(str, Enum):
    """Explicit approval state of a handoff row.

    ``UNKNOWN`` is for rows whose approval is not even known; it is never
    used as a synonym for pending or approved.
    """

    APPROVED = "approved"
    PENDING_HUMAN_APPROVAL = "pending_human_approval"
    UNKNOWN = "unknown"


class ApprovalEvidence(BaseModel):
    """Exact approval evidence for an accepted handoff row.

    A row may resolve to ACCEPTED only when the human approval is recorded
    as evidence: the approver principal, the UTC approval instant, a
    locator/artifact reference to the durable approval record, and the
    optional canonical digest of that record.  Maintenance never infers
    acceptance from a status label or repository ancestry — an APPROVED row
    without :class:`ApprovalEvidence` stays typed UNKNOWN with reason
    MISSING_FIELD.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    approver: StrictStr
    approved_at: UtcTime
    evidence_ref: StrictStr
    digest: StrictStr | None = None

    @field_validator("approver", "evidence_ref")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("approval evidence approver/evidence_ref must be non-empty")
        return value

    @field_validator("digest")
    @classmethod
    def _validate_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _SHA256_HEX_RE.fullmatch(value):
            raise ValueError(
                "approval evidence digest must be a 64-character lowercase "
                "sha256 hex digest"
            )
        return value


# ---------------------------------------------------------------------------
# WBC runtime coordinates
# ---------------------------------------------------------------------------


class WbcCoordinates(BaseModel):
    """WBC store incarnation/restore/high-water coordinates.

    These are open production values until human-approved: absent fields stay
    explicit ``None`` and are never guessed.  Incarnation identifies the
    store generation; restore generation and high water track restores and
    the highest processed coordinate.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    incarnation: StrictStr
    restore_generation: StrictStr | None = None
    high_water: StrictStr | None = None

    @field_validator("incarnation")
    @classmethod
    def _validate_incarnation(cls, value: str) -> str:
        if not value:
            raise ValueError("WBC incarnation must be a non-empty string")
        return value

    @field_validator("restore_generation", "high_water")
    @classmethod
    def _validate_optional(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("WBC coordinates must be non-empty strings when present")
        return value


# ---------------------------------------------------------------------------
# Handoff row
# ---------------------------------------------------------------------------


class HandoffRow(BaseModel):
    """One declarative handoff candidate row.

    The row records the EXACT owner coordinates for the consumed source —
    the owner API identity (``owner_api_identity``), the owner schema
    identity (``schema_identity``) and its explicit version
    (``schema_version``), the content digest (``digest``), and the approval
    evidence (``approval_evidence``) — so acceptance is never inferred from
    a status label or repository ancestry.

    ``digest``, ``wbc_coordinates``, and ``approval_evidence`` are the
    production values that require human approval; they stay ``None``
    (explicit unknown) until approved.  ``requires_wbc_coordinates``
    declares whether acceptance of this row also requires approved WBC
    incarnation/restore/high-water coordinates (true for the M6A WBC store
    row, false for the other source paths).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: StrictStr
    source_path: StrictStr
    schema_identity: StrictStr
    #: Exact owner API identity of the consumed source (the seam the
    #: Maintenance adapters call).  Recorded explicitly; never inferred.
    owner_api_identity: StrictStr
    #: Exact owner schema version (the version component of
    #: ``schema_identity``).  Recorded explicitly; ``schema_identity`` must
    #: end with ``"." + schema_version`` so the pair is never contradictory.
    schema_version: StrictStr
    digest: StrictStr | None = None
    approval: ApprovalState
    requires_wbc_coordinates: bool = False
    wbc_coordinates: WbcCoordinates | None = None
    approval_evidence: ApprovalEvidence | None = None

    @field_validator("id", "source_path", "schema_identity", "owner_api_identity")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "handoff id/source_path/schema_identity/owner_api_identity "
                "must be non-empty"
            )
        return value

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: str) -> str:
        if not value:
            raise ValueError("handoff schema_version must be a non-empty string")
        return value

    @field_validator("digest")
    @classmethod
    def _validate_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _SHA256_HEX_RE.fullmatch(value):
            raise ValueError(
                "handoff digest must be a 64-character lowercase sha256 hex digest"
            )
        return value

    @model_validator(mode="after")
    def _check_row_invariants(self) -> HandoffRow:
        # 1. The recorded schema version must be the exact version component
        #    of the recorded schema identity (never inferred, never silent).
        if not self.schema_identity.endswith("." + self.schema_version):
            raise ValueError(
                f"handoff schema_identity {self.schema_identity!r} must end "
                f"with '.{self.schema_version}' to match schema_version"
            )
        # 2. Approval evidence without an APPROVED state is incoherent.
        if (
            self.approval_evidence is not None
            and self.approval is not ApprovalState.APPROVED
        ):
            raise ValueError(
                "handoff approval_evidence requires approval=approved; "
                f"got approval={self.approval.value!r}"
            )
        # 3. A non-approved row must never carry approved production data:
        #    a pending/unknown label cannot coexist with a content digest or
        #    recorded approval evidence (the loader never guesses either way).
        if self.approval is not ApprovalState.APPROVED and (
            self.digest is not None or self.approval_evidence is not None
        ):
            raise ValueError(
                "a non-approved handoff row must not carry digest or "
                "approval_evidence; approval is not accepted yet"
            )
        return self

    @property
    def is_complete(self) -> bool:
        """Whether every required production value for this row is present.

        The row's own identity fields are always present (enforced at
        validation); completeness here means the *approved production data*
        (content digest, recorded approval evidence, plus WBC coordinates
        when required) is present.  A claimed approval without its recorded
        evidence is never complete.
        """
        if self.digest is None:
            return False
        if self.approval_evidence is None:
            return False
        if self.requires_wbc_coordinates and self.wbc_coordinates is None:
            return False
        return True

    @property
    def acceptance_eligible(self) -> bool:
        """Whether this row may become accepted evidence (complete + approved)."""
        return self.is_complete and self.approval is ApprovalState.APPROVED


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


class HandoffResolutionState(str, Enum):
    """Final resolution of a handoff request: accepted evidence or UNKNOWN."""

    ACCEPTED = "accepted"
    UNKNOWN = "unknown"


class HandoffResolutionReason(str, Enum):
    """Typed reason for a resolution — never an inferred acceptance."""

    ACCEPTED = "accepted"
    PENDING_HUMAN_APPROVAL = "pending_human_approval"
    MISSING_FIELD = "missing_field"
    MISSING_HANDOFF = "missing_handoff"
    #: A mismatch against the accepted handoff row's source path, schema
    #: identity, content digest, or shared identity.  Any mismatch resolves to
    #: typed UNKNOWN — never acceptance — and the consuming adapter emits no
    #: references.
    PATH_MISMATCH = "path_mismatch"
    SCHEMA_MISMATCH = "schema_mismatch"
    DIGEST_MISMATCH = "digest_mismatch"
    IDENTITY_MISMATCH = "identity_mismatch"
    UNKNOWN = "unknown"


class HandoffResolution(BaseModel):
    """Read-only resolution of one handoff request.

    ``row`` is present only for an ACCEPTED resolution; every UNKNOWN
    resolution carries a typed reason and an explicit approval state so
    consumers never confuse pending, missing, or unknown with accepted.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    handoff_id: StrictStr
    state: HandoffResolutionState
    approval: ApprovalState
    reason: HandoffResolutionReason
    row: HandoffRow | None = None


class HandoffAcceptedEntry(BaseModel):
    """One frozen accepted-vector entry for a consumed source.

    Exposes the EXACT accepted coordinates — owner API identity, schema
    identity and version, content digest, WBC coordinates (when required),
    and the recorded approval evidence — for one handoff id.  Entries exist
    only for ACCEPTED resolutions; every other row is absent from the
    accepted vector (typed UNKNOWN, non-dispatchable).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    handoff_id: StrictStr
    source_path: StrictStr
    schema_identity: StrictStr
    owner_api_identity: StrictStr
    schema_version: StrictStr
    digest: StrictStr
    wbc_coordinates: WbcCoordinates | None = None
    approval_evidence: ApprovalEvidence


class HandoffDriftEntry(BaseModel):
    """One frozen drift entry for a consumed source.

    Compares the recorded (approved) content digest against the live
    artifact digest at ``artifact_path``.  ``matches`` is ``True`` only when
    both digests are present and equal; a missing recorded digest (pending),
    a missing artifact, or any mismatch reports ``matches=False`` so
    consumers fail closed.  ``live_digest`` stays ``None`` when the artifact
    is unavailable — drift is reported as data, never guessed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    handoff_id: StrictStr
    artifact_path: StrictStr
    recorded_digest: StrictStr | None = None
    live_digest: StrictStr | None = None
    matches: bool = False

    @field_validator("recorded_digest", "live_digest")
    @classmethod
    def _validate_digests(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _SHA256_HEX_RE.fullmatch(value):
            raise ValueError(
                "handoff drift digest must be a 64-character lowercase "
                "sha256 hex digest"
            )
        return value


def _resolve_row(row: HandoffRow | None, handoff_id: str) -> HandoffResolution:
    if row is None:
        return HandoffResolution(
            handoff_id=handoff_id,
            state=HandoffResolutionState.UNKNOWN,
            approval=ApprovalState.UNKNOWN,
            reason=HandoffResolutionReason.MISSING_HANDOFF,
        )
    if row.approval is not ApprovalState.APPROVED:
        reason = (
            HandoffResolutionReason.PENDING_HUMAN_APPROVAL
            if row.approval is ApprovalState.PENDING_HUMAN_APPROVAL
            else HandoffResolutionReason.UNKNOWN
        )
        return HandoffResolution(
            handoff_id=handoff_id,
            state=HandoffResolutionState.UNKNOWN,
            approval=row.approval,
            reason=reason,
        )
    if not row.is_complete:
        return HandoffResolution(
            handoff_id=handoff_id,
            state=HandoffResolutionState.UNKNOWN,
            approval=ApprovalState.APPROVED,
            reason=HandoffResolutionReason.MISSING_FIELD,
        )
    return HandoffResolution(
        handoff_id=handoff_id,
        state=HandoffResolutionState.ACCEPTED,
        approval=ApprovalState.APPROVED,
        reason=HandoffResolutionReason.ACCEPTED,
        row=row,
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class HandoffRegistry(BaseModel):
    """The closed, read-only handoff trust gate.

    Loaded from declarative candidate data; resolution is a pure function of
    the rows (see :func:`_resolve_row`).  The registry itself holds no
    mutation authority and exposes no write or discovery API.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION)
    rows: tuple[HandoffRow, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported handoff registry schema version {value}; "
                f"expected {MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("rows")
    @classmethod
    def _validate_rows(cls, rows: tuple[HandoffRow, ...]) -> tuple[HandoffRow, ...]:
        ids = tuple(row.id for row in rows)
        if len(set(ids)) != len(ids):
            raise ValueError(f"handoff registry contains duplicate rows: {ids}")
        if set(ids) != set(HANDOFF_IDS):
            missing = sorted(set(HANDOFF_IDS) - set(ids))
            extra = sorted(set(ids) - set(HANDOFF_IDS))
            raise ValueError(
                "handoff registry must cover exactly "
                f"{sorted(HANDOFF_IDS)}; missing={missing}, extra={extra}"
            )
        ordered = tuple(sorted(rows, key=lambda row: row.id))
        if ordered != rows:
            # Normalize to canonical id order so digests are stable.
            rows = ordered
        return rows

    def resolve(self, handoff_id: str) -> HandoffResolution:
        """Resolve one handoff id to accepted evidence or typed UNKNOWN."""
        for row in self.rows:
            if row.id == handoff_id:
                return _resolve_row(row, handoff_id)
        return _resolve_row(None, handoff_id)

    def resolve_all(self) -> tuple[HandoffResolution, ...]:
        """Resolve every known handoff id in canonical registry order."""
        return tuple(self.resolve(handoff_id) for handoff_id in HANDOFF_IDS)

    def accepted_vector(self) -> tuple[HandoffAcceptedEntry, ...]:
        """Return the frozen accepted vector in canonical handoff-id order.

        Only complete AND approved rows appear; every other row is absent
        from the vector (typed UNKNOWN, non-dispatchable).  The vector
        carries the exact accepted owner coordinates recorded in the rows.
        """
        entries: list[HandoffAcceptedEntry] = []
        for handoff_id in HANDOFF_IDS:
            resolution = self.resolve(handoff_id)
            if (
                resolution.state is HandoffResolutionState.ACCEPTED
                and resolution.row is not None
            ):
                row = resolution.row
                assert row.digest is not None
                assert row.approval_evidence is not None
                entries.append(
                    HandoffAcceptedEntry(
                        handoff_id=handoff_id,
                        source_path=row.source_path,
                        schema_identity=row.schema_identity,
                        owner_api_identity=row.owner_api_identity,
                        schema_version=row.schema_version,
                        digest=row.digest,
                        wbc_coordinates=row.wbc_coordinates,
                        approval_evidence=row.approval_evidence,
                    )
                )
        return tuple(entries)

    def recorded_drift(self) -> tuple[HandoffDriftEntry, ...]:
        """Return the frozen recorded drift baseline (pure, no file I/O).

        Each entry carries the row's recorded digest (``None`` while
        pending) and ``matches=False``: without a live artifact read the
        drift is unverified.  :func:`verify_handoff_drift` computes the
        live-digest variant.
        """
        return tuple(
            HandoffDriftEntry(
                handoff_id=handoff_id,
                artifact_path=row.source_path,
                recorded_digest=row.digest,
                live_digest=None,
                matches=False,
            )
            for handoff_id in HANDOFF_IDS
            for row in self.rows
            if row.id == handoff_id
        )

    def registry_digest(self) -> str:
        """Canonical digest of the registry (stable, content-addressed)."""
        return canonical_digest(self)


def load_handoff_registry(path: str | Path) -> HandoffRegistry:
    """Strict-load a :class:`HandoffRegistry` from a JSON file.

    Uses the single canonical strict decoder; missing or unknown fields,
    bad versions, unknown ids, and duplicate rows all fail with a typed
    :class:`~arnold_pipelines.megaplan.maintenance.identity.MaintenanceCodecError`.
    """
    text = Path(path).read_text(encoding="utf-8")
    return strict_loads(HandoffRegistry, text)


@lru_cache(maxsize=1)
def default_handoff_registry() -> HandoffRegistry:
    """Return the package's declarative candidate registry (lazily loaded).

    The candidate data carries every open production value as explicit
    pending/``null``; resolutions therefore remain UNKNOWN until human
    approval is recorded.
    """
    return load_handoff_registry(Path(__file__).with_name("handoffs.json"))


# ---------------------------------------------------------------------------
# M3 handoff view (T22): deterministic read-only digest/identity snapshot
# ---------------------------------------------------------------------------
# The view synthesizes version/digest identities across every M2 contract and
# distinguishes pending from accepted WITHOUT becoming authority.  It is a
# frozen, canonical, read-only model: no mutation, no dispatch, no custody /
# validation / attempt / queue / completion / transition-writer substrate of
# any kind.  Enforcement stays disabled; shadow/report operation stays on
# (SD3).

#: Canonical M3 view schema identity (frozen).
M3_VIEW_VERSION: str = "m3.handoff.v1"

#: Frozen schema digests: content-addressed sha256 of each Maintenance schema
#: definition module's source at the M2 freeze (computed 2026-08-15 by T22;
#: identity/sources/observation re-frozen 2026-08-16 after the T1 OwnerRef
#: coordinate rework and the T9/T7 follow-through rework landed).
#: ``verify_frozen_digests`` recomputes the live digests and reports drift as
#: data — the frozen view never mutates and never guesses a changed schema.
#: M3 Step 15 (T16, 2026-08-17) refreshed the events/handoffs/sources/
#: observation/projections/ledger digests AFTER the T1..T15 contract changes
#: landed; the refresh was driven by the reported drift (never guessed), and
#: every other digest (identity/contracts/boundaries/authority.coherence and
#: all fixtures) still matches its live artifact.
FROZEN_SCHEMA_DIGESTS: dict[str, str] = {
    "identity": "0ea6f35d77fdef6a8d664ec863a37e68c5fd070750235c672b1b4642132c4834",
    "contracts": "8743c5d94219b564883c10edcff8cd6f3754e145a5b1ecb71af9109a2fe031c3",
    "events": "e359d457c41e8a7ffae0fde2580780251afac1b90b5db3cbb2216f89b974443b",
    #: ``handoffs`` is content-addressed over the declarative registry data
    #: (handoffs.json) — the registry schema is a data file, and a module
    #: digest would be self-referential (the constant lives in the module).
    "handoffs": "1a5872754afc9073287beb452dc1b9f5e29d7f39d9c19f7dd28cdcc04c773d1f",
    "sources": "e2ece168591190c470d4eef10c824874724c83685e525074883d20f90889160b",
    "boundaries": "85e84195b5e6662f87effde7749ab70b791a12378d16b0bd6b0a626f5f8fac04",
    "observation": "62039424ae301dcb8dd0d6529523c5d16d577b556a560d79c4c98e884531f5b6",
    #: Re-frozen after the G6.1 ApplyDisposition export restore (dfa13c786c)
    #: touched projections.py; refresh driven by the reported drift.
    "projections": "0f8831e9da338ae1c7f04e4c8e5ddc6a29789f8f80f7a13005de96283d15786b",
    "ledger": "f15027f711d4a2da5cc52ebd1347447cf49c6e30ceaf1eb6d53b6e530b317ce3",
    #: T10 compatibility facade module (replaces the old coherence algorithm).
    "authority.coherence": "d8a51d34e9607a849ebfb792f6db3ed6e2d92d459219789b85d8c2e2cac6b77e",
}

#: Frozen fixture digests for the deterministic coherent/torn/recurrence
#: fixtures consumed by the M2 proof suite (T9/T13/M3 proof).
FROZEN_FIXTURE_DIGESTS: dict[str, str] = {
    "coherent_join": "0357add2c997534bf63a6c5770a7182925cceb0153b300f62bf068e3bcfc87e2",
    "torn_join": "6f83823e856b9b2900351ae27d89fa1ad36699b0acef6faedc769aec1ce569d1",
    "recurrence_replay": "b27cd24ea70a71c554525f87e80733d5b054ef2b8602501e3131bd99d9756920",
}

#: Adapter versions finalized by T6/T7: adapter class -> Maintenance schema
#: version of its read contract.  The adapter inventory is pinned here because
#: the view must not import the adapter module (it imports this registry).
ADAPTER_VERSIONS: dict[str, str] = {
    "RunAuthorityAdapter": "1",
    "WbcAdapter": "1",
    "CustodyAdapter": "1",
    "ConformanceAdapter": "1",
    "NativeManifestAdapter": "1",
}

#: Projection API versions finalized by T13: projection name -> schema version.
PROJECTION_API_VERSIONS: dict[str, str] = {
    "operational_custody": "1",
    "verification": "1",
    "efficiency_analysis": "1",
}

#: T10 compatibility facade identity: the authority-facing read-only entry
#: point that delegates coherent capture to the Maintenance join.
COMPATIBILITY_FACADE_IDENTITY: str = (
    "arnold_pipelines.megaplan.authority.coherence.capture_authority_coherence"
)

#: Relative source paths used by :func:`verify_frozen_digests` (read-only).
_SCHEMA_SOURCE_PATHS: dict[str, str] = {
    "identity": "arnold_pipelines/megaplan/maintenance/identity.py",
    "contracts": "arnold_pipelines/megaplan/maintenance/contracts.py",
    "events": "arnold_pipelines/megaplan/maintenance/events.py",
    "handoffs": "arnold_pipelines/megaplan/maintenance/handoffs.json",
    "sources": "arnold_pipelines/megaplan/maintenance/sources.py",
    "boundaries": "arnold_pipelines/megaplan/maintenance/boundaries.py",
    "observation": "arnold_pipelines/megaplan/maintenance/observation.py",
    "projections": "arnold_pipelines/megaplan/maintenance/projections.py",
    "ledger": "arnold_pipelines/megaplan/maintenance/ledger.py",
    "authority.coherence": "arnold_pipelines/megaplan/authority/coherence.py",
}

#: Relative fixture paths used by :func:`verify_frozen_digests` (read-only).
_FIXTURE_PATHS: dict[str, str] = {
    "coherent_join": "tests/fixtures/maintenance/coherent_join.json",
    "torn_join": "tests/fixtures/maintenance/torn_join.json",
    "recurrence_replay": "tests/fixtures/maintenance/recurrence_replay.jsonl",
}

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def _project_root() -> Path:
    """Repository root: arnold_pipelines/megaplan/maintenance -> parents[3]."""
    return Path(__file__).resolve().parents[3]


def _file_sha256(path: Path) -> str:
    """Deterministic sha256 hex of a file's bytes (read-only)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_frozen_digests(
    *, project_root: Path | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Recompute live schema/fixture digests and report drift as data.

    Read-only and never raises: a drifted schema is reported (``matches``
    ``False``) so an M3 consumer can fail closed on it, but this function
    never writes, never imports the drifted module for execution, and never
    guesses a replacement digest.
    """
    root = project_root if project_root is not None else _project_root()
    report: dict[str, dict[str, dict[str, Any]]] = {}
    for group, frozen, paths in (
        ("schema", FROZEN_SCHEMA_DIGESTS, _SCHEMA_SOURCE_PATHS),
        ("fixtures", FROZEN_FIXTURE_DIGESTS, _FIXTURE_PATHS),
    ):
        entries: dict[str, dict[str, Any]] = {}
        for key, expected in frozen.items():
            relative = paths[key]
            actual = _file_sha256(root / relative)
            entries[key] = {
                "expected": expected,
                "actual": actual,
                "matches": actual == expected,
                "path": relative,
            }
        report[group] = entries
    return report


def verify_handoff_drift(
    registry: HandoffRegistry | None = None,
    *,
    project_root: Path | None = None,
) -> tuple[HandoffDriftEntry, ...]:
    """Recompute every consumed source's live artifact digest and report drift.

    Read-only and never raises: for each handoff row, the live artifact is
    resolved at ``project_root / source_path`` and its sha256 digest is
    compared against the recorded (approved) digest.  A missing artifact
    reports ``live_digest=None`` with ``matches=False``; a pending row
    reports ``recorded_digest=None`` with ``matches=False``; only an exact
    recorded==live match reports ``matches=True``.  Drift is reported as
    data — this function never writes, never guesses a replacement digest,
    and never promotes a mismatched row.
    """
    handoffs = registry if registry is not None else default_handoff_registry()
    root = project_root if project_root is not None else _project_root()
    entries: list[HandoffDriftEntry] = []
    for handoff_id in HANDOFF_IDS:
        resolution = handoffs.resolve(handoff_id)
        row = resolution.row
        if row is None:
            entries.append(
                HandoffDriftEntry(
                    handoff_id=handoff_id,
                    artifact_path="",
                    recorded_digest=None,
                    live_digest=None,
                    matches=False,
                )
            )
            continue
        artifact = root / row.source_path
        live = _file_sha256(artifact) if artifact.is_file() else None
        recorded = row.digest
        entries.append(
            HandoffDriftEntry(
                handoff_id=handoff_id,
                artifact_path=row.source_path,
                recorded_digest=recorded,
                live_digest=live,
                matches=(
                    recorded is not None and live is not None and live == recorded
                ),
            )
        )
    return tuple(entries)


class MaintenanceHandoffView(BaseModel):
    """Canonical read-only M3-facing view over the Maintenance handoff state.

    Synthesizes the frozen schema digests, the SD1 precedence version, the
    approved-versus-pending handoff identities, the T6/T7 adapter versions,
    the coherent/recurrence fixture digests, the T13 projection API versions,
    and the T10 compatibility-facade identity.  Open production approvals are
    reported as *pending blockers to enforcement only*: the view keeps
    ``enforcement_enabled`` ``False`` (M2 never enables enforcement) and keeps
    ``shadow_operation_enabled`` ``True`` (SD3 shadow/report mode ships).

    The view is frozen, forbids unknown fields, round-trips through the single
    canonical codec, and exposes NO mutation or dispatch method — it creates no
    custody, validation, attempt, queue, completion, or transition-writer
    substrate.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    view_version: str = M3_VIEW_VERSION
    precedence_version: str = EVIDENCE_PRECEDENCE_VERSION

    schema_digests: dict[str, str]
    adapter_versions: dict[str, str]
    projection_api_versions: dict[str, str]
    fixture_digests: dict[str, str]

    compatibility_facade: str
    compatibility_facade_digest: str

    approved_handoff_ids: tuple[str, ...] = ()
    pending_handoff_ids: tuple[str, ...] = ()
    unknown_handoff_ids: tuple[str, ...] = ()
    handoff_resolutions: tuple[HandoffResolution, ...] = ()

    #: The frozen accepted vector: exact accepted owner coordinates per
    #: consumed source (empty while every handoff stays pending).
    accepted_vector: tuple[HandoffAcceptedEntry, ...] = ()
    #: Frozen drift per consumed source (recorded vs live artifact digest).
    drift: tuple[HandoffDriftEntry, ...] = ()

    #: All open (non-accepted) production approvals — enforcement-only
    #: blockers.  Shadow/report operation is never disabled by these.
    pending_blockers: tuple[str, ...] = ()
    enforcement_blocked: bool = False
    enforcement_enabled: Literal[False] = False
    shadow_operation_enabled: Literal[True] = True

    registry_digest: str

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported handoff view schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator(
        "schema_digests", "fixture_digests", "compatibility_facade_digest", "registry_digest"
    )
    @classmethod
    def _validate_digests(cls, value: Any) -> Any:
        if isinstance(value, dict):
            for key, digest in value.items():
                if not isinstance(digest, str) or not _SHA256_HEX_RE.fullmatch(digest):
                    raise ValueError(
                        f"handoff view digest {key!r} must be a 64-character "
                        "lowercase sha256 hex digest"
                    )
        elif isinstance(value, str) and not _SHA256_HEX_RE.fullmatch(value):
            raise ValueError(
                "handoff view digest must be a 64-character lowercase sha256 hex digest"
            )
        return value

    @field_validator("view_version", "compatibility_facade")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("handoff view identity fields must be non-empty")
        return value

    @model_validator(mode="after")
    def _check_consistency(self) -> MaintenanceHandoffView:
        resolution_ids = [resolution.handoff_id for resolution in self.handoff_resolutions]
        if len(set(resolution_ids)) != len(resolution_ids):
            raise ValueError("handoff view resolutions must be unique")
        all_ids = set(resolution_ids)
        accepted = {
            resolution.handoff_id
            for resolution in self.handoff_resolutions
            if resolution.state is HandoffResolutionState.ACCEPTED
        }
        pending = {
            resolution.handoff_id
            for resolution in self.handoff_resolutions
            if resolution.approval is ApprovalState.PENDING_HUMAN_APPROVAL
        }
        unknown = {
            resolution.handoff_id
            for resolution in self.handoff_resolutions
            if resolution.approval is ApprovalState.UNKNOWN
        }
        blockers = {
            resolution.handoff_id
            for resolution in self.handoff_resolutions
            if resolution.state is not HandoffResolutionState.ACCEPTED
        }
        if set(self.approved_handoff_ids) != accepted:
            raise ValueError(
                "approved_handoff_ids must equal the accepted handoff resolutions"
            )
        if set(self.pending_handoff_ids) != pending:
            raise ValueError(
                "pending_handoff_ids must equal the pending_human_approval resolutions"
            )
        if set(self.unknown_handoff_ids) != unknown:
            raise ValueError(
                "unknown_handoff_ids must equal the unknown-approval resolutions"
            )
        if (
            set(self.approved_handoff_ids)
            | set(self.pending_handoff_ids)
            | set(self.unknown_handoff_ids)
            != all_ids
        ):
            raise ValueError(
                "approved/pending/unknown handoff ids must partition every resolution"
            )
        if set(self.pending_blockers) != blockers:
            raise ValueError(
                "pending_blockers must equal every non-accepted handoff resolution"
            )
        if self.enforcement_blocked != bool(self.pending_blockers):
            raise ValueError(
                "enforcement_blocked must equal whether any pending blocker exists"
            )
        # 4. The frozen accepted vector must be derived EXACTLY from the
        #    accepted resolutions' rows, in canonical handoff-id order.
        if len({entry.handoff_id for entry in self.accepted_vector}) != len(
            self.accepted_vector
        ):
            raise ValueError("handoff view accepted_vector must not repeat handoff ids")
        if {entry.handoff_id for entry in self.accepted_vector} != accepted:
            raise ValueError(
                "accepted_vector must cover exactly the accepted handoff resolutions"
            )
        for entry in self.accepted_vector:
            resolution = next(
                resolution
                for resolution in self.handoff_resolutions
                if resolution.handoff_id == entry.handoff_id
            )
            row = resolution.row
            if row is None:
                raise ValueError(
                    f"accepted_vector entry {entry.handoff_id!r} has no row"
                )
            if (
                entry.source_path != row.source_path
                or entry.schema_identity != row.schema_identity
                or entry.owner_api_identity != row.owner_api_identity
                or entry.schema_version != row.schema_version
                or entry.digest != row.digest
                or entry.wbc_coordinates != row.wbc_coordinates
                or entry.approval_evidence != row.approval_evidence
            ):
                raise ValueError(
                    f"accepted_vector entry {entry.handoff_id!r} does not match "
                    "its handoff resolution row"
                )
        # 5. Drift must cover exactly every consumed source (closed).
        if {entry.handoff_id for entry in self.drift} != set(HANDOFF_IDS):
            raise ValueError(
                "handoff view drift must cover exactly every consumed source"
            )
        return self

    @property
    def digest(self) -> str:
        """Canonical digest of the whole view (deterministic, content-addressed)."""
        return canonical_digest(self)

    @property
    def pending_blocker_count(self) -> int:
        """Number of open production approvals (enforcement-only blockers)."""
        return len(self.pending_blockers)

    @property
    def accepted_handoff_count(self) -> int:
        """Number of handoff identities resolved to accepted evidence."""
        return len(self.approved_handoff_ids)


def build_handoff_view(
    *,
    registry: HandoffRegistry | None = None,
    drift: Sequence[HandoffDriftEntry] | None = None,
) -> MaintenanceHandoffView:
    """Build the canonical read-only M3 handoff view from a strict registry.

    Deterministic: the view is a pure function of the registry rows plus the
    frozen digest/version constants above.  It performs no file I/O, no
    mutation, and no dispatch.  ``drift`` optionally carries the live
    drift report (see :func:`verify_handoff_drift`); when omitted the view
    carries the pure recorded-drift baseline (every entry ``matches=False``).
    """
    handoffs = registry if registry is not None else default_handoff_registry()
    resolutions = handoffs.resolve_all()
    approved = tuple(
        resolution.handoff_id
        for resolution in resolutions
        if resolution.state is HandoffResolutionState.ACCEPTED
    )
    pending = tuple(
        resolution.handoff_id
        for resolution in resolutions
        if resolution.approval is ApprovalState.PENDING_HUMAN_APPROVAL
    )
    unknown = tuple(
        resolution.handoff_id
        for resolution in resolutions
        if resolution.approval is ApprovalState.UNKNOWN
    )
    blockers = tuple(
        resolution.handoff_id
        for resolution in resolutions
        if resolution.state is not HandoffResolutionState.ACCEPTED
    )
    drift_entries = (
        tuple(drift)
        if drift is not None
        else handoffs.recorded_drift()
    )
    return MaintenanceHandoffView(
        schema_version=MAINTENANCE_SCHEMA_VERSION,
        view_version=M3_VIEW_VERSION,
        precedence_version=EVIDENCE_PRECEDENCE_VERSION,
        schema_digests=dict(FROZEN_SCHEMA_DIGESTS),
        adapter_versions=dict(ADAPTER_VERSIONS),
        projection_api_versions=dict(PROJECTION_API_VERSIONS),
        fixture_digests=dict(FROZEN_FIXTURE_DIGESTS),
        compatibility_facade=COMPATIBILITY_FACADE_IDENTITY,
        compatibility_facade_digest=FROZEN_SCHEMA_DIGESTS["authority.coherence"],
        approved_handoff_ids=approved,
        pending_handoff_ids=pending,
        unknown_handoff_ids=unknown,
        handoff_resolutions=resolutions,
        accepted_vector=handoffs.accepted_vector(),
        drift=drift_entries,
        pending_blockers=blockers,
        enforcement_blocked=bool(blockers),
        enforcement_enabled=False,
        shadow_operation_enabled=True,
        registry_digest=handoffs.registry_digest(),
    )


__all__ = [
    "ADAPTER_VERSIONS",
    "ApprovalEvidence",
    "ApprovalState",
    "COMPATIBILITY_FACADE_IDENTITY",
    "FROZEN_FIXTURE_DIGESTS",
    "FROZEN_SCHEMA_DIGESTS",
    "HANDOFF_IDS",
    "HandoffAcceptedEntry",
    "HandoffDriftEntry",
    "HandoffRegistry",
    "HandoffResolution",
    "HandoffResolutionReason",
    "HandoffResolutionState",
    "HandoffRow",
    "M3_VIEW_VERSION",
    "MaintenanceHandoffView",
    "PROJECTION_API_VERSIONS",
    "WbcCoordinates",
    "build_handoff_view",
    "default_handoff_registry",
    "load_handoff_registry",
    "verify_frozen_digests",
    "verify_handoff_drift",
]
