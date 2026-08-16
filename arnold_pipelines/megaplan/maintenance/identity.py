"""Strict Maintenance identity, owner-reference, and event-time primitives.

This module is the M2 Maintenance foundation.  It provides exactly one
canonical serializer / strict decoder, typed nullable identities, locator-only
immutable owner references, and validated UTC observation/event times, half-open
windows, watermarks, lateness, and correction links.

Design rules (from the M2 brief, locked decisions):

* Unknown or missing fields fail on strict decode, except keys inside the
  explicit :class:`Extensions` map.
* Identity values are never normalized, case-folded, or otherwise inferred:
  two identities match only when their kinds and values are exactly equal, and
  any mismatch is reported explicitly (see :func:`compare_identities` and
  :func:`require_identical`).
* Owner references are locator-only: they point at an owner record (Run
  Authority, WBC, Custody, plan/chain, conformance, Native manifest, ...) and
  never embed a copy of the owner record.
* Times are validated as UTC; naive datetimes are rejected rather than
  assumed to be UTC.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, ClassVar, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    RootModel,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Schema version for the closed Maintenance event namespace.
MAINTENANCE_SCHEMA_VERSION: int = 1

#: Maximum accepted length of any Maintenance identity value.
MAX_IDENTITY_LENGTH: int = 256

#: The closed set of accepted maintenance environment namespaces.  Environment
#: identity is intentionally a closed vocabulary: an observation must name a
#: real namespace or be explicitly null — it is never guessed or aliased
#: (``prod`` is not ``production``).  Mirrors the M1 cloud resolver vocabulary.
MAINTENANCE_ENVIRONMENTS: frozenset[str] = frozenset(
    {"production", "staging", "test", "fixture"}
)

#: Locator of an owner record in its canonical owner store.  The locator is
#: opaque to this package; owner adapters interpret it (ledger path + sequence,
#: attempt id, manifest ref, ...).
OwnerKind = Literal[
    "run_authority",  # Run Authority grants/attempts/decisions/fences/quarantine
    "wbc",  # WBC/kernel attempt events
    "custody",  # Custody lease/action-validation records
    "maintenance",  # maintenance observations/transitions
    "plan",  # plan events/receipts/artifact digests/accepted gate-finalize
    "chain",  # chain events
    "repair_custody",  # chain and repair-custody events
    "conformance",  # M11 conformance evidence
    "native_manifest",  # Native Parity C1/C2/S1/S2R manifests
    "snapshot",  # resident/cloud snapshots and heartbeats
    "heartbeat",  # resident/cloud heartbeats
    "status_projection",  # mutable state/status projections
    "unknown",  # explicit UNKNOWN; never a guessed owner
]

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_CONTROL_CHARS = frozenset(chr(code) for code in range(0x20)) | {"\x7f"}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MaintenanceError(ValueError):
    """Base class for all Maintenance contract failures."""


class InvalidIdentityError(MaintenanceError):
    """Raised when an identity value is malformed or outside a closed set."""


class IdentityMismatchError(MaintenanceError):
    """Raised when two identities are compared and found mismatched.

    Mismatches are always explicit: different identity kinds or different
    values raise this typed error instead of silently coercing or aliasing.
    """


class InvalidTimeError(MaintenanceError):
    """Raised when a time value is not a valid UTC instant."""


class MaintenanceCodecError(MaintenanceError):
    """Raised by the strict decoder for missing, unknown, or mistyped fields.

    Carries the structured pydantic error records (``loc``/``type``/``msg``)
    on :attr:`errors` so callers can distinguish ``missing`` fields, unknown
    ``extra_forbidden`` fields, and type errors without string parsing.
    """

    def __init__(
        self,
        message: str,
        *,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.errors: list[dict[str, Any]] = list(errors or [])


# ---------------------------------------------------------------------------
# Shared identity validation
# ---------------------------------------------------------------------------


def _validate_identity_value(value: Any, kind: str) -> str:
    """Validate one identity value without normalizing it.

    Enforces non-empty, control-character-free, length-capped strings and
    deliberately performs NO case folding, trimming, or alias resolution:
    identity semantics are exact-match only.
    """
    if not isinstance(value, str):
        raise ValueError(f"{kind} identity must be a string, got {type(value).__name__}")
    if not value:
        raise ValueError(f"{kind} identity must be a non-empty string")
    if len(value) > MAX_IDENTITY_LENGTH:
        raise ValueError(
            f"{kind} identity exceeds the maximum length of {MAX_IDENTITY_LENGTH} characters"
        )
    if _CONTROL_CHARS.intersection(value):
        raise ValueError(f"{kind} identity contains control characters")
    return value


class _BaseIdentity(RootModel[str]):
    """Shared strict, frozen, non-coercing string identity root.

    Concrete identities subclass this and override :attr:`_kind` (and, when
    the kind has a closed vocabulary, the root validator).  Values are never
    coerced from other JSON types (``strict=True``) and instances are frozen
    so identities are safe as dictionary keys and digest inputs.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    root: str

    #: Canonical kind label used by :func:`compare_identities` and errors.
    _kind: ClassVar[str] = "identity"

    @field_validator("root")
    @classmethod
    def _validate_root(cls, value: Any) -> str:
        return _validate_identity_value(value, cls._kind)

    @property
    def identity_kind(self) -> str:
        """Return the canonical kind label (``environment``, ``run``, ...)."""
        return self._kind

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.root!r})"


# ---------------------------------------------------------------------------
# Typed nullable identities
# ---------------------------------------------------------------------------
# Each identity is a distinct type so contracts can carry ``Optional[...]``
# fields that serialize to explicit JSON nulls (never omitted, never guessed).


class EnvironmentId(_BaseIdentity):
    """Closed-set maintenance environment namespace.

    Accepted values are exactly ``production``, ``staging``, ``test``, and
    ``fixture``.  Anything else — including aliases like ``prod`` or
    differently-cased spellings — is rejected; an absent environment is
    represented by ``None`` (explicit null), never by a guessed value.
    """

    _kind: ClassVar[str] = "environment"

    @field_validator("root")
    @classmethod
    def _validate_environment(cls, value: Any) -> str:
        value = _validate_identity_value(value, "environment")
        if value not in MAINTENANCE_ENVIRONMENTS:
            raise ValueError(
                f"unknown maintenance environment {value!r}; expected one of "
                f"{sorted(MAINTENANCE_ENVIRONMENTS)}"
            )
        return value


class TenantId(_BaseIdentity):
    """Tenant identity (exact-match, non-empty string)."""

    _kind: ClassVar[str] = "tenant"


class RunId(_BaseIdentity):
    """Run identity (exact-match, non-empty string)."""

    _kind: ClassVar[str] = "run"


class ChainId(_BaseIdentity):
    """Chain identity (exact-match, non-empty string)."""

    _kind: ClassVar[str] = "chain"


class PlanId(_BaseIdentity):
    """Plan identity (exact-match, non-empty string)."""

    _kind: ClassVar[str] = "plan"


class StageId(_BaseIdentity):
    """Stage identity (exact-match, non-empty string)."""

    _kind: ClassVar[str] = "stage"


class ModelId(_BaseIdentity):
    """Model identity (exact-match, non-empty string)."""

    _kind: ClassVar[str] = "model"


class ProfileId(_BaseIdentity):
    """Profile identity (exact-match, non-empty string)."""

    _kind: ClassVar[str] = "profile"


class AttemptId(_BaseIdentity):
    """Attempt identity (exact-match, non-empty string)."""

    _kind: ClassVar[str] = "attempt"


#: Union of every Maintenance identity kind.
AnyMaintenanceId = (
    EnvironmentId
    | TenantId
    | RunId
    | ChainId
    | PlanId
    | StageId
    | ModelId
    | ProfileId
    | AttemptId
)


# ---------------------------------------------------------------------------
# Explicit identity comparison (mismatches are never inferred)
# ---------------------------------------------------------------------------


class IdentityComparison(str, Enum):
    """Explicit outcome of comparing two Maintenance identities."""

    MATCH = "match"
    KIND_MISMATCH = "kind_mismatch"
    VALUE_MISMATCH = "value_mismatch"


def compare_identities(left: Any, right: Any) -> IdentityComparison:
    """Compare two identities, reporting mismatches explicitly.

    Returns :attr:`IdentityComparison.MATCH` only when both values are
    Maintenance identities of the same kind with exactly equal values.
    Different kinds or different values are reported explicitly; nothing is
    coerced or aliased.
    """
    kind_left = getattr(left, "identity_kind", None)
    kind_right = getattr(right, "identity_kind", None)
    if kind_left is None or kind_right is None:
        raise MaintenanceError(
            "compare_identities requires Maintenance identity values"
        )
    if kind_left != kind_right:
        return IdentityComparison.KIND_MISMATCH
    if left.root != right.root:
        return IdentityComparison.VALUE_MISMATCH
    return IdentityComparison.MATCH


def require_identical(left: Any, right: Any, *, context: str = "identity") -> None:
    """Raise :class:`IdentityMismatchError` unless *left* and *right* match.

    The raised error names the explicit mismatch kind so callers never have
    to guess whether a mismatch was a kind or a value difference.
    """
    result = compare_identities(left, right)
    if result is not IdentityComparison.MATCH:
        raise IdentityMismatchError(
            f"{context} mismatch ({result.value}): {left!r} != {right!r}"
        )


# ---------------------------------------------------------------------------
# Locator-only immutable owner references
# ---------------------------------------------------------------------------


class OwnerRef(BaseModel):
    """Locator-only immutable reference to an owner record.

    Carries the owner kind, the owner record type, the typed owner identity,
    the owner read-contract schema version, a locator into the owner's
    canonical store, and optional digest/cursor coordinates.  It never embeds
    owner payloads: readers resolve the locator through the owner's own
    adapter, and the record content is represented only by its canonical
    digest.  Instances are frozen so references cannot be mutated after
    creation.

    The enrichment coordinates ``record_type``, ``identity``, and
    ``schema_version`` are populated by the owner adapters (T6/T7) and used by
    the coherent join for identity-dimension and precedence validation.  They
    are part of the canonical serialized payload: an enriched reference
    canonically serializes and strict-decodes every immutable coordinate
    (``owner``, ``record_type``, ``identity``, ``schema_version``, ``cursor``,
    ``digest``, ``locator``), and absent coordinates serialize as explicit
    JSON ``null`` so unenriched references round-trip identically.  A
    reference never embeds any owner payload: the record content is
    represented only by the locator/digest coordinates.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    owner: OwnerKind
    #: Owner record type within the owner kind (``grant``, ``decision``,
    #: ``fence``, ``attempt``, ``quarantine``, ``diagnostic``, ``event``,
    #: ``ledger``, ``gap``, ``lease``, ``validation``, ``manifest``, ...).
    #: Populated by the owner adapter; never inferred from the locator.
    record_type: StrictStr | None = None
    #: Typed owner identity (run id, attempt id, lease id, subject, ...) that
    #: owns this record.  Populated by the owner adapter.
    identity: StrictStr | None = None
    #: Owner read-contract schema version at capture time.  Populated by the
    #: owner adapter.
    schema_version: StrictStr | None = None
    locator: StrictStr
    digest: StrictStr | None = None
    cursor: StrictStr | None = None

    @field_validator("locator")
    @classmethod
    def _validate_locator(cls, value: str) -> str:
        if not value:
            raise ValueError("owner locator must be a non-empty string")
        return value

    @field_validator("record_type", "identity", "schema_version")
    @classmethod
    def _validate_coordinates(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError(
                "owner reference coordinates must be non-empty strings when present"
            )
        return value

    @field_validator("digest")
    @classmethod
    def _validate_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _SHA256_HEX_RE.fullmatch(value):
            raise ValueError(
                "owner digest must be a 64-character lowercase sha256 hex digest"
            )
        return value

    @field_validator("cursor")
    @classmethod
    def _validate_cursor(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("owner cursor must be a non-empty string when present")
        return value


# ---------------------------------------------------------------------------
# Validated UTC observation/event times, watermarks, lateness, windows
# ---------------------------------------------------------------------------


class UtcTime(RootModel[datetime]):
    """A validated UTC instant for observations and events.

    Naive datetimes are rejected — a missing offset is never assumed to be
    UTC.  Aware datetimes in any offset are normalized to UTC so canonical
    serialization is always ``...Z``.
    """

    model_config = ConfigDict(frozen=True)

    root: datetime

    @field_validator("root")
    @classmethod
    def _validate_utc(cls, value: Any) -> datetime:
        if not isinstance(value, datetime):
            raise ValueError(f"time must be a datetime, got {type(value).__name__}")
        if value.tzinfo is None:
            raise ValueError(
                "naive datetime is not allowed; supply an explicit UTC offset"
            )
        return value.astimezone(timezone.utc)


def _coerce_utc(value: UtcTime | datetime, *, what: str) -> datetime:
    """Normalize a ``UtcTime`` or aware ``datetime`` to a UTC instant."""
    if isinstance(value, UtcTime):
        return value.root
    if not isinstance(value, datetime):
        raise InvalidTimeError(f"{what} must be a UtcTime or aware datetime")
    if value.tzinfo is None:
        raise InvalidTimeError(f"{what} must carry an explicit UTC offset")
    return value.astimezone(timezone.utc)


class Watermark(UtcTime):
    """A watermark: the highest observation/event time fully processed.

    Lateness boundary (explicit, closed at the watermark): an event whose
    event time is *at or before* the watermark is ``late``; only events
    strictly after the watermark are ``on_time``.  Late evidence is handled
    by append-only correction links, never by rewriting prior events.
    """

    def lateness_for(self, event_time: UtcTime | datetime) -> Lateness:
        """Classify *event_time* against this watermark."""
        return classify_lateness(event_time, self)


class Lateness(str, Enum):
    """Explicit lateness classification of an event against a watermark."""

    ON_TIME = "on_time"
    LATE = "late"


def classify_lateness(
    event_time: UtcTime | datetime,
    watermark: Watermark | datetime,
) -> Lateness:
    """Classify *event_time* against *watermark* with the closed boundary rule.

    ``event_time <= watermark`` is ``LATE``; anything strictly after the
    watermark is ``ON_TIME``.
    """
    instant = _coerce_utc(event_time, what="event_time")
    mark = _coerce_utc(watermark, what="watermark")
    return Lateness.LATE if instant <= mark else Lateness.ON_TIME


class EventWindow(BaseModel):
    """Half-open event-time window ``[start, end)``.

    ``start`` is inclusive and ``end`` is exclusive: an instant equal to
    ``end`` is NOT contained.  Windows with ``start >= end`` are rejected at
    construction and at strict decode.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: UtcTime
    end: UtcTime

    @model_validator(mode="after")
    def _check_half_open(self) -> EventWindow:
        if self.start.root >= self.end.root:
            raise ValueError(
                "event window must be half-open [start, end) with start < end"
            )
        return self

    def contains(self, instant: UtcTime | datetime) -> bool:
        """Return ``True`` when *instant* is in ``[start, end)``."""
        value = _coerce_utc(instant, what="instant")
        return self.start.root <= value < self.end.root

    @property
    def duration(self) -> timedelta:
        """Return the window duration as a ``timedelta``."""
        return self.end.root - self.start.root


# ---------------------------------------------------------------------------
# Correction links (append-only; never rewrite prior events)
# ---------------------------------------------------------------------------


class CorrectionLink(BaseModel):
    """Append-only reference from a late/correcting event to the event it
    corrects.

    Corrections never rewrite or delete the corrected event: they link to it
    by identity.  ``corrected_event_id`` is the occurrence identity of the
    original event.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    corrected_event_id: StrictStr
    reason: StrictStr | None = None

    @field_validator("corrected_event_id")
    @classmethod
    def _validate_corrected(cls, value: str) -> str:
        if not value:
            raise ValueError("corrected_event_id must be a non-empty string")
        return value

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("correction reason must be a non-empty string when present")
        return value


# ---------------------------------------------------------------------------
# Extensions — the only place unknown fields are allowed
# ---------------------------------------------------------------------------


class Extensions(RootModel[dict[str, Any]]):
    """Opaque extension map.

    This is the explicit escape hatch: unknown keys are rejected everywhere
    else, but any content is accepted inside an ``Extensions`` value.  Treat
    instances as immutable; the map is never interpreted by Maintenance code.
    """

    model_config = ConfigDict(frozen=True)

    root: dict[str, Any]


# ---------------------------------------------------------------------------
# One canonical serializer / strict decoder
# ---------------------------------------------------------------------------


def canonical_json(value: Any) -> str:
    """Encode *value* as canonical JSON.

    Canonical form: compact separators, sorted object keys, ``allow_nan=False``
    so non-finite floats fail instead of producing unstable digests.  This is
    the single canonical encoding used for digests and wire serialization.
    """
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_dumps(model: BaseModel) -> str:
    """Serialize any Maintenance pydantic model to canonical JSON.

    Uses ``mode="json"`` (datetimes become ISO-8601 ``...Z`` strings and
    identity roots become plain strings) and preserves explicit ``None``
    values — a nullable identity serializes as ``null``, never as an omitted
    field.
    """
    if not isinstance(model, BaseModel):
        raise MaintenanceError(
            "canonical_dumps requires a pydantic model, "
            f"got {type(model).__name__}"
        )
    data = model.model_dump(mode="json", by_alias=True, exclude_none=False)
    return canonical_json(data)


def canonical_digest(model: BaseModel) -> str:
    """Return the canonical sha256 hex digest of *model*."""
    return hashlib.sha256(canonical_dumps(model).encode("utf-8")).hexdigest()


_ModelT = TypeVar("_ModelT", bound=BaseModel)


def strict_loads(
    model_cls: type[_ModelT],
    data: str | bytes | Mapping[str, Any],
) -> _ModelT:
    """Strict-decode JSON into *model_cls*.

    Raises :class:`MaintenanceCodecError` for invalid JSON, non-object input,
    missing required fields, unknown fields (``extra_forbidden``), and type
    errors.  Unknown keys are accepted only inside ``Extensions`` values,
    which is enforced by the individual model configs (``extra="forbid"``).
    """
    if isinstance(data, (str, bytes)):
        try:
            raw: Any = json.loads(data)
        except json.JSONDecodeError as exc:
            raise MaintenanceCodecError(
                f"invalid JSON while strict-decoding {model_cls.__name__}: {exc}"
            ) from exc
    else:
        raw = data
    if not isinstance(raw, dict):
        raise MaintenanceCodecError(
            f"strict decode of {model_cls.__name__} requires a JSON object, "
            f"got {type(raw).__name__}"
        )
    try:
        return model_cls.model_validate(raw)
    except ValidationError as exc:
        errors = [
            {
                "loc": list(error.get("loc", ())),
                "type": error.get("type"),
                "msg": error.get("msg"),
            }
            for error in exc.errors()
        ]
        raise MaintenanceCodecError(
            f"strict decode failed for {model_cls.__name__} with "
            f"{len(errors)} error(s): {errors}",
            errors=errors,
        ) from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def utc_now() -> datetime:
    """Return the current time as an aware UTC instant."""
    return datetime.now(timezone.utc)


__all__ = [
    "AnyMaintenanceId",
    "AttemptId",
    "ChainId",
    "CorrectionLink",
    "EnvironmentId",
    "EventWindow",
    "Extensions",
    "IdentityComparison",
    "IdentityMismatchError",
    "InvalidIdentityError",
    "InvalidTimeError",
    "Lateness",
    "MAINTENANCE_ENVIRONMENTS",
    "MAINTENANCE_SCHEMA_VERSION",
    "MAX_IDENTITY_LENGTH",
    "MaintenanceCodecError",
    "MaintenanceError",
    "ModelId",
    "OwnerKind",
    "OwnerRef",
    "PlanId",
    "ProfileId",
    "RunId",
    "StageId",
    "TenantId",
    "UtcTime",
    "Watermark",
    "canonical_digest",
    "canonical_dumps",
    "canonical_json",
    "classify_lateness",
    "compare_identities",
    "require_identical",
    "strict_loads",
    "utc_now",
]
