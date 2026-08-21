"""M5 exact-version read adapters for Run Authority, WBC, Custody, and Native evidence (Steps 7-8).

These read-only injected query adapters bridge the SD1 owner sources
consumed by the daily efficiency auditor:

* :class:`RunAuthorityAcceptedOutcomeAdapter` queries Run Authority
  **accepted outcomes** (accepted decisions and accepted claims) from an
  injected ``RunAuthorityView``-shaped provider;
* :class:`WbcWorkEvidenceAdapter` queries **WBC/work evidence** (attempt
  ledger events, ledger, source cursor, gaps) through the exact
  ``AttemptLedgerStore`` read/query/version API surface;
* :class:`CustodyLeaseHistoryAdapter` (Step 8 / T8) queries the **Custody
  lease store** history through its read/replay surface, retaining
  active-custody availability as a typed flag and locator-only lease/history
  references;
* :class:`NativeProofQualityAdapter` (Step 8 / T8) queries **Native proof
  and quality evidence** through injected read providers, retaining
  sensitive-evidence availability as a typed flag with locator-only
  references and typing missing cost/quality/model coordinates as UNKNOWN.

Both adapters reuse the existing before/after source coordinates from
:mod:`~arnold_pipelines.megaplan.maintenance.sources`
(:class:`~arnold_pipelines.megaplan.maintenance.contracts.SourceVersionVector`,
:class:`~arnold_pipelines.megaplan.maintenance.sources.WbcEventRef`, and
:class:`~arnold_pipelines.megaplan.maintenance.sources.SourceCursorRef`) and
follow the same read-only rules:

* they call ONLY named read/query/version APIs — never an append,
  reservation, cursor-update, lease, or store-creation method;
* they emit only immutable references / digests / cursors — owner payloads
  are never embedded or copied into the read result;
* every read captures source versions **before and after** so a version
  tear is detected exactly (never inferred);
* version tears, cursor gaps, missing records, cross-environment joins, and
  mid-read mutations yield typed :attr:`SourceReadDisposition.UNKNOWN` /
  ``INCOHERENT`` facts with a typed :class:`SourceReadFailure` reason — a
  torn, gapped, missing, or cross-environment read can never support a
  finding or proposal;
* active repair custody is retained only as reference/covariate coordinates
  (``active_custody_refs`` / ``active_lease_ref``), never claimed and never
  altered, and sensitive evidence is retained only as availability plus
  locator-only references — raw payloads are never copied;
* missing cost, quality, and model coordinates are typed UNKNOWN
  (:class:`EvidenceUnknownKind`) — never coerced to zero or to green.

The plan's Step 7/8 rules are locked: reads return immutable locators,
digests, cursors, and before/after source versions; no authority record is
copied.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from arnold_pipelines.megaplan.maintenance import efficiency_analysis as analysis_mod
from arnold_pipelines.megaplan.maintenance.contracts import SourceVersionVector
from arnold_pipelines.megaplan.maintenance.efficiency_contracts import (
    DAILY_EFFICIENCY_CONTRACT_ID,
    DwellFindingKind,
    RobustnessKind,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    MAINTENANCE_SCHEMA_VERSION,
    EnvironmentId,
    ModelId,
    OwnerRef,
    UtcTime,
    canonical_digest,
    canonical_json,
)
from arnold_pipelines.megaplan.maintenance.sources import SourceCursorRef, WbcEventRef

#: Default classifier version used for envelope identity derivation when the
#: caller does not pin one (classifier-version separation is part of the
#: identity material, mirroring the loop-family rule in the analysis module).
DEFAULT_CLASSIFIER_VERSION: str = "cls-v1"

_SHA256_HEX = frozenset("0123456789abcdef")


def _require_sha256(value: str, *, what: str) -> str:
    if len(value) != 64 or any(char not in _SHA256_HEX for char in value):
        raise ValueError(f"{what} must be a 64-character lowercase sha256 hex digest")
    return value


def _to_plain(value: Any) -> Any:
    """Recursively convert owner dataclasses/enums to canonical JSON values."""
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _to_plain(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_plain(item) for key, item in sorted(value.items())}
    if hasattr(value, "value") and not isinstance(value, str):
        return _to_plain(value.value)
    return value


def _record_digest(record: Any) -> str:
    """Deterministic sha256 digest of an owner record without embedding it."""
    if hasattr(record, "digest") and callable(getattr(record, "digest")):
        return _require_sha256(record.digest(), what="owner record digest")
    if hasattr(record, "to_dict") and callable(getattr(record, "to_dict")):
        material = canonical_json(_to_plain(record.to_dict()))
    else:
        material = canonical_json(_to_plain(record))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _sort_refs(refs: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
    """Deterministic (owner, locator, digest, cursor) reference order."""
    return tuple(
        sorted(
            refs,
            key=lambda ref: (ref.owner, ref.locator, ref.digest or "", ref.cursor or ""),
        )
    )


def _environment(value: EnvironmentId | str | None) -> EnvironmentId | None:
    """Coerce an environment coordinate, failing fast on unknown namespaces."""
    if value is None:
        return None
    if isinstance(value, EnvironmentId):
        return value
    return EnvironmentId(value)


# ---------------------------------------------------------------------------
# Fail-closed source-provider admission (G1-F-001)
# ---------------------------------------------------------------------------
# Injected stores and callables are admitted only when they expose the
# declared read surface and no mutation-capable public method.  Adapters
# retain a sealed named-operation object — never the original provider.


class ProviderAdmissionError(TypeError):
    """Construction-time refusal of a mutation-capable or incomplete provider."""


class WbcReadProvider(Protocol):
    """Declared WBC read/query/version surface (no writer methods)."""

    def get_contract_version(self) -> Any: ...

    def get_store_version(self) -> Any: ...

    def read_events(self, attempt_id: str) -> Any: ...

    def read_ledger(self, attempt_id: str) -> Any: ...

    def get_terminal_event(self, attempt_id: str) -> Any: ...

    def query_gaps(self, attempt_id: str) -> Any: ...

    def query_source_cursor(self, attempt_id: str, cursor_key: str) -> Any: ...


class CustodyReadProvider(Protocol):
    """Declared Custody load/replay surface (no writer methods)."""

    def load_history(self, lease_id: str) -> Any: ...

    def replay_history(self, lease_id: str) -> Any: ...


_WBC_READ_OPERATIONS: tuple[str, ...] = (
    "get_contract_version",
    "get_store_version",
    "read_events",
    "read_ledger",
    "get_terminal_event",
    "query_gaps",
    "query_source_cursor",
)

_CUSTODY_READ_OPERATIONS: tuple[str, ...] = (
    "load_history",
    "replay_history",
)

_PROVIDER_MUTATION_VERBS: frozenset[str] = frozenset(
    {
        "append",
        "reserve",
        "update",
        "write",
        "delete",
        "remove",
        "create",
        "acquire",
        "renew",
        "transfer",
        "release",
        "expire",
        "fence",
        "migrate",
        "insert",
        "reclaim",
        "record_event",
    }
)


def _is_writer_named(name: str) -> bool:
    lowered = name.lower().replace("-", "_")
    if lowered in _PROVIDER_MUTATION_VERBS:
        return True
    return any(
        part in _PROVIDER_MUTATION_VERBS for part in lowered.split("_") if part
    )


def _public_callable_names(provider: object) -> tuple[str, ...]:
    names: list[str] = []
    for name in dir(provider):
        if name.startswith("_"):
            continue
        try:
            attr = getattr(provider, name)
        except Exception:
            continue
        if callable(attr):
            names.append(name)
    return tuple(names)


def _reject_writer_methods(
    provider: object,
    *,
    allowed: frozenset[str],
    what: str,
) -> None:
    writers = [
        name
        for name in _public_callable_names(provider)
        if name not in allowed and _is_writer_named(name)
    ]
    if writers:
        raise ProviderAdmissionError(
            f"{what} exposes mutation-capable method(s) {sorted(writers)!r}; "
            "read adapters admit only the declared read surface"
        )


def _require_operations(
    provider: object,
    operations: tuple[str, ...],
    *,
    what: str,
) -> None:
    missing = [
        name
        for name in operations
        if not callable(getattr(provider, name, None))
    ]
    if missing:
        raise ProviderAdmissionError(
            f"{what} is missing required read operation(s) {missing!r}"
        )


def _wrap_operation(operation: Any, name: str) -> Any:
    def _bound(*args: Any, **kwargs: Any) -> Any:
        return operation(*args, **kwargs)

    _bound.__name__ = name
    _bound.__qualname__ = name
    return _bound


def _seal_named_reads(
    provider: object,
    operations: tuple[str, ...],
    *,
    metadata: tuple[str, ...] = (),
    what: str,
) -> Any:
    """Admit *provider* and return a sealed surface with only declared reads."""
    if provider is None:
        raise ProviderAdmissionError(f"{what} is required")
    _require_operations(provider, operations, what=what)
    _reject_writer_methods(provider, allowed=frozenset(operations), what=what)
    sealed_type = type(
        "SealedReadSurface",
        (),
        {"__slots__": operations + metadata, "__module__": __name__},
    )
    sealed = sealed_type.__new__(sealed_type)
    for name in operations:
        object.__setattr__(
            sealed, name, _wrap_operation(getattr(provider, name), name)
        )
    for name in metadata:
        if hasattr(provider, name):
            object.__setattr__(sealed, name, getattr(provider, name))
    return sealed


class _SealedCallable:
    """Sealed callable read provider; original object is not retained."""

    __slots__ = ("_call", "environment")

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return object.__getattribute__(self, "_call")(*args, **kwargs)


def _seal_callable(provider: object, *, what: str) -> _SealedCallable:
    if not callable(provider):
        raise ProviderAdmissionError(f"{what} must be a callable read provider")
    _reject_writer_methods(provider, allowed=frozenset(), what=what)
    sealed = _SealedCallable.__new__(_SealedCallable)
    object.__setattr__(sealed, "_call", _wrap_operation(provider, "__call__"))
    if hasattr(provider, "environment"):
        object.__setattr__(sealed, "environment", getattr(provider, "environment"))
    return sealed


def _seal_optional_callable(
    provider: object | None, *, what: str
) -> _SealedCallable | None:
    if provider is None:
        return None
    return _seal_callable(provider, what=what)


# ---------------------------------------------------------------------------
# Typed read dispositions (fail-closed outcomes)
# ---------------------------------------------------------------------------


class SourceReadDisposition(str, Enum):
    """Closed disposition of one owner read (Step 7 fail-closed rule).

    ``COHERENT`` is the only disposition that may support a finding or
    proposal; ``UNKNOWN`` and ``INCOHERENT`` reads carry a typed
    :class:`SourceReadFailure` reason and can never be treated as evidence.
    """

    COHERENT = "coherent"
    UNKNOWN = "unknown"
    INCOHERENT = "incoherent"


class SourceReadFailure(str, Enum):
    """Closed typed reasons for UNKNOWN / INCOHERENT owner reads."""

    VERSION_TEAR = "version_tear"
    CURSOR_GAP = "cursor_gap"
    MID_READ_MUTATION = "mid_read_mutation"
    SOURCE_UNAVAILABLE = "source_unavailable"
    #: The owner declares an environment that differs from the expected
    #: environment; a cross-environment join is typed UNKNOWN (never mixed).
    CROSS_ENVIRONMENT = "cross_environment"
    #: The referenced owner record is absent (typed unknown availability).
    RECORD_MISSING = "record_missing"
    #: The read high-water cursor does not match the owner file's pre-read
    #: size (a cursor mismatch): the read consumed a different boundary than
    #: the owner advertised, so it is typed UNKNOWN (Step 9 / T9 receipts).
    CURSOR_MISMATCH = "cursor_mismatch"
    #: The coherent join (Step 10 / T10) could not bind every required
    #: coordinate of the normalized task/milestone outcome — a required
    #: identity coordinate or the exact accepted-outcome anchor is missing,
    #: so the page is an incomplete, non-supporting fact.
    INCOMPLETE = "incomplete"
    #: The coherent join (Step 10 / T10) observed an owner source whose
    #: post-read version does not match the expected version supplied by the
    #: caller (the page moved since the authoritative capture): a stale page
    #: is typed UNKNOWN and can never support a finding or proposal.
    STALE = "stale"


class EvidenceUnknownKind(str, Enum):
    """Typed reason a cost/quality/model coordinate is unknown (never guessed).

    A missing coordinate stays explicit ``None`` and may name its typed
    reason; a PRESENT coordinate can never be typed unknown.  This is the
    machine-checked "missing cost, quality, model stays UNKNOWN" contract —
    absent values are never coerced to zero or to green.
    """

    COST = "cost"
    QUALITY = "quality"
    MODEL = "model"


def _check_unknown_evidence(
    *,
    cost: float | None,
    quality: float | None,
    model: ModelId | None,
    unknown_evidence: Sequence[EvidenceUnknownKind],
) -> None:
    """Reject a present coordinate that is simultaneously typed unknown."""
    unknown = set(unknown_evidence)
    if cost is not None and EvidenceUnknownKind.COST in unknown:
        raise ValueError("a present cost cannot be typed unknown")
    if quality is not None and EvidenceUnknownKind.QUALITY in unknown:
        raise ValueError("a present quality cannot be typed unknown")
    if model is not None and EvidenceUnknownKind.MODEL in unknown:
        raise ValueError("a present model cannot be typed unknown")


def _validate_read_disposition(
    *,
    disposition: SourceReadDisposition,
    disposition_reason: SourceReadFailure | None,
    torn: bool,
    before: str | None,
    after: str | None,
    has_refs: bool,
    label: str,
) -> None:
    """Shared fail-closed disposition validation for the Step 8 read models.

    ``COHERENT``/``INCOHERENT`` reads require exact before/after version
    coordinates; ``UNKNOWN`` reads require a typed reason and carry no
    evidence references; ``torn`` requires differing versions typed
    ``INCOHERENT``/``VERSION_TEAR``; cross-environment and missing-record
    reads must be typed ``UNKNOWN``.
    """
    if disposition is SourceReadDisposition.COHERENT:
        if disposition_reason is not None:
            raise ValueError(f"coherent {label} reads cannot carry a disposition_reason")
        if before is None or after is None:
            raise ValueError(
                f"coherent {label} reads require exact before/after versions"
            )
    elif disposition is SourceReadDisposition.INCOHERENT:
        if disposition_reason is None:
            raise ValueError(
                f"incoherent {label} reads require a typed disposition_reason"
            )
        if before is None or after is None:
            raise ValueError(
                f"incoherent {label} reads require exact before/after versions"
            )
    else:  # UNKNOWN
        if disposition_reason is None:
            raise ValueError(f"unknown {label} reads require a typed disposition_reason")
        if has_refs:
            raise ValueError(f"unknown {label} reads cannot carry evidence references")
    if torn:
        if before is None or after is None or before == after:
            raise ValueError("torn=True requires differing before/after versions")
        if (
            disposition is not SourceReadDisposition.INCOHERENT
            or disposition_reason is not SourceReadFailure.VERSION_TEAR
        ):
            raise ValueError("torn reads must be typed INCOHERENT with VERSION_TEAR")
    if disposition_reason is SourceReadFailure.VERSION_TEAR and not torn:
        raise ValueError("VERSION_TEAR requires torn=True")
    if (
        disposition_reason is SourceReadFailure.CROSS_ENVIRONMENT
        and disposition is not SourceReadDisposition.UNKNOWN
    ):
        raise ValueError("CROSS_ENVIRONMENT reads must be typed UNKNOWN")
    if (
        disposition_reason is SourceReadFailure.RECORD_MISSING
        and disposition is not SourceReadDisposition.UNKNOWN
    ):
        raise ValueError("RECORD_MISSING reads must be typed UNKNOWN")


# ---------------------------------------------------------------------------
# Run Authority accepted-outcome read
# ---------------------------------------------------------------------------


class RunAuthorityAcceptedOutcomeRead(BaseModel):
    """Immutable result of one Run Authority accepted-outcome capture.

    Carries the exact before/after view hashes captured around the read
    (``before_view_hash`` / ``after_view_hash`` plus the shared
    :class:`SourceVersionVector`), the journal cursor, and locator-only
    references to the accepted decisions/claims — never the authority
    records themselves.  A version tear (``before != after``) is typed
    ``INCOHERENT`` with :attr:`SourceReadFailure.VERSION_TEAR`; an
    unavailable source is typed ``UNKNOWN`` with ``SOURCE_UNAVAILABLE`` and
    carries no references.  Active repair custody appears only as
    reference/covariate coordinates.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    run_id: StrictStr | None = None
    run_revision: StrictStr | None = None
    environment: EnvironmentId | None = None
    journal_cursor: int | None = Field(default=None, ge=0)
    before_view_hash: StrictStr | None = None
    after_view_hash: StrictStr | None = None
    version_vector: SourceVersionVector
    #: Locator-only refs to accepted decisions and accepted claims.
    accepted_outcome_refs: tuple[OwnerRef, ...] = ()
    #: Active repair custody refs — reference/covariate only, never claimed.
    active_custody_refs: tuple[OwnerRef, ...] = ()
    active_custody_present: bool = False
    disposition: SourceReadDisposition = SourceReadDisposition.COHERENT
    disposition_reason: SourceReadFailure | None = None
    torn: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("before_view_hash", "after_view_hash")
    @classmethod
    def _validate_hashes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_sha256(value, what="run authority view hash")

    @field_validator("accepted_outcome_refs", "active_custody_refs")
    @classmethod
    def _sort_ref_lists(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @model_validator(mode="after")
    def _check_disposition(self) -> RunAuthorityAcceptedOutcomeRead:
        if self.disposition is SourceReadDisposition.COHERENT:
            if self.disposition_reason is not None:
                raise ValueError(
                    "coherent reads cannot carry a disposition_reason"
                )
            self._require_exact_versions("coherent")
        elif self.disposition is SourceReadDisposition.INCOHERENT:
            if self.disposition_reason is None:
                raise ValueError(
                    "incoherent reads require a typed disposition_reason"
                )
            self._require_exact_versions("incoherent")
        else:  # UNKNOWN
            if self.disposition_reason is None:
                raise ValueError("unknown reads require a typed disposition_reason")
            if self.accepted_outcome_refs:
                raise ValueError(
                    "unknown reads cannot carry accepted_outcome_refs"
                )
        if self.torn:
            if (
                self.before_view_hash is None
                or self.after_view_hash is None
                or self.before_view_hash == self.after_view_hash
            ):
                raise ValueError(
                    "torn=True requires differing before/after view hashes"
                )
            if (
                self.disposition is not SourceReadDisposition.INCOHERENT
                or self.disposition_reason is not SourceReadFailure.VERSION_TEAR
            ):
                raise ValueError(
                    "torn reads must be typed INCOHERENT with VERSION_TEAR"
                )
        if (
            self.disposition_reason is SourceReadFailure.VERSION_TEAR
            and not self.torn
        ):
            raise ValueError("VERSION_TEAR requires torn=True")
        return self

    def _require_exact_versions(self, label: str) -> None:
        if (
            self.run_id is None
            or self.run_revision is None
            or self.journal_cursor is None
            or self.before_view_hash is None
            or self.after_view_hash is None
        ):
            raise ValueError(
                f"{label} reads require exact run_id/run_revision/journal_cursor "
                "and before/after view hashes"
            )

    @property
    def digest(self) -> str:
        """Canonical digest of the whole read result (replayable)."""
        return canonical_digest(self)


# ---------------------------------------------------------------------------
# WBC work-evidence read
# ---------------------------------------------------------------------------


class WbcWorkEvidenceRead(BaseModel):
    """Immutable result of one WBC work-evidence capture.

    Carries the exact before/after contract and store versions captured
    around the read, the shared :class:`SourceVersionVector`, and
    locator/digest/cursor-only references to the attempt's events, ledger,
    source cursor, and gaps — never the owner records.  A version tear is
    typed ``INCOHERENT``/``VERSION_TEAR``; a cursor gap (``gap_refs``
    non-empty) is typed ``INCOHERENT``/``CURSOR_GAP``; an unavailable source
    is typed ``UNKNOWN``/``SOURCE_UNAVAILABLE`` and carries no references.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    attempt_id: StrictStr
    environment: EnvironmentId | None = None
    contract_version_before: StrictStr | None = None
    contract_version_after: StrictStr | None = None
    store_version_before: StrictStr | None = None
    store_version_after: StrictStr | None = None
    version_vector: SourceVersionVector
    event_refs: tuple[WbcEventRef, ...] = ()
    ledger_ref: OwnerRef | None = None
    source_cursor: SourceCursorRef | None = None
    gap_refs: tuple[OwnerRef, ...] = ()
    active_custody_refs: tuple[OwnerRef, ...] = ()
    active_custody_present: bool = False
    disposition: SourceReadDisposition = SourceReadDisposition.COHERENT
    disposition_reason: SourceReadFailure | None = None
    torn: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("event_refs")
    @classmethod
    def _sort_event_refs(
        cls, value: Sequence[WbcEventRef]
    ) -> tuple[WbcEventRef, ...]:
        return tuple(sorted(value, key=lambda ref: ref.sequence))

    @field_validator("gap_refs", "active_custody_refs")
    @classmethod
    def _sort_ref_lists(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @model_validator(mode="after")
    def _check_disposition(self) -> WbcWorkEvidenceRead:
        if self.disposition is SourceReadDisposition.COHERENT:
            if self.disposition_reason is not None:
                raise ValueError("coherent reads cannot carry a disposition_reason")
            self._require_exact_versions("coherent")
        elif self.disposition is SourceReadDisposition.INCOHERENT:
            if self.disposition_reason is None:
                raise ValueError(
                    "incoherent reads require a typed disposition_reason"
                )
            self._require_exact_versions("incoherent")
        else:  # UNKNOWN
            if self.disposition_reason is None:
                raise ValueError("unknown reads require a typed disposition_reason")
            if self.event_refs or self.ledger_ref is not None or self.source_cursor is not None:
                raise ValueError(
                    "unknown reads cannot carry event/ledger/cursor references"
                )
        if self.disposition_reason is SourceReadFailure.CURSOR_GAP and not self.gap_refs:
            raise ValueError("CURSOR_GAP requires gap_refs to be non-empty")
        if self.torn:
            if (
                self.contract_version_before is None
                or self.contract_version_after is None
                or self.store_version_before is None
                or self.store_version_after is None
                or (
                    self.contract_version_before == self.contract_version_after
                    and self.store_version_before == self.store_version_after
                )
            ):
                raise ValueError(
                    "torn=True requires differing before/after source versions"
                )
            if (
                self.disposition is not SourceReadDisposition.INCOHERENT
                or self.disposition_reason is not SourceReadFailure.VERSION_TEAR
            ):
                raise ValueError(
                    "torn reads must be typed INCOHERENT with VERSION_TEAR"
                )
        if (
            self.disposition_reason is SourceReadFailure.VERSION_TEAR
            and not self.torn
        ):
            raise ValueError("VERSION_TEAR requires torn=True")
        return self

    def _require_exact_versions(self, label: str) -> None:
        if (
            self.contract_version_before is None
            or self.contract_version_after is None
            or self.store_version_before is None
            or self.store_version_after is None
        ):
            raise ValueError(
                f"{label} reads require exact before/after contract and "
                "store versions"
            )

    @property
    def digest(self) -> str:
        """Canonical digest of the whole read result (replayable)."""
        return canonical_digest(self)


# ---------------------------------------------------------------------------
# Active-custody reference/covariate helper
# ---------------------------------------------------------------------------


def _active_custody_refs(
    provider: Callable[[], Sequence[Any]] | None,
    *,
    cursor: str | None = None,
) -> tuple[OwnerRef, ...]:
    """Locator-only repair-custody references from an injected provider.

    Returns an empty tuple when no provider is injected or no records are
    present.  Records are referenced (locator + digest + cursor), never
    copied; the daily auditor neither claims nor alters custody.
    """
    if provider is None:
        return ()
    refs: list[OwnerRef] = []
    for index, record in enumerate(provider()):
        record_id = (
            getattr(record, "lease_id", None)
            or getattr(record, "record_id", None)
            or f"{index:04d}"
        )
        refs.append(
            OwnerRef(
                owner="repair_custody",
                record_type="active_lease",
                identity=str(record_id),
                schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                locator=f"repair-custody://{record_id}",
                digest=_record_digest(record),
                cursor=cursor,
            )
        )
    return _sort_refs(refs)


# ---------------------------------------------------------------------------
# Run Authority accepted-outcome adapter
# ---------------------------------------------------------------------------


class RunAuthorityAcceptedOutcomeAdapter:
    """Read-only injected query adapter over Run Authority accepted outcomes.

    Holds only a view provider (and optional environment identity and
    active-custody provider); it exposes no mutation method and never
    constructs an owner store.  Each read captures the view hash before and
    after the accepted-outcome query, so a mid-read mutation is detected as
    an exact version tear.
    """

    def __init__(
        self,
        view_provider: Callable[[], Any],
        *,
        environment: EnvironmentId | str | None = None,
        active_custody_provider: Callable[[], Sequence[Any]] | None = None,
    ) -> None:
        self._view_provider = _seal_callable(
            view_provider, what="Run Authority view provider"
        )
        self._environment = _environment(environment)
        self._active_custody_provider = _seal_optional_callable(
            active_custody_provider,
            what="Run Authority active-custody provider",
        )

    def _version_vector(
        self, before: str | None, after: str | None
    ) -> SourceVersionVector:
        return SourceVersionVector(
            owner="run_authority",
            source="run_authority.view",
            environment=self._environment,
            before=before,
            after=after,
        )

    def _unavailable(self) -> RunAuthorityAcceptedOutcomeRead:
        return RunAuthorityAcceptedOutcomeRead(
            environment=self._environment,
            version_vector=self._version_vector(None, None),
            disposition=SourceReadDisposition.UNKNOWN,
            disposition_reason=SourceReadFailure.SOURCE_UNAVAILABLE,
        )

    def read(self) -> RunAuthorityAcceptedOutcomeRead:
        """Capture one version-coherent Run Authority accepted-outcome read.

        Returns immutable locators/digests/cursors and before/after view
        hashes; a version tear between the before and after captures is typed
        ``INCOHERENT``/``VERSION_TEAR`` and an unavailable source is typed
        ``UNKNOWN``/``SOURCE_UNAVAILABLE``.
        """
        try:
            before = self._view_provider()
        except Exception:
            return self._unavailable()
        try:
            after = self._view_provider()
        except Exception:
            return self._unavailable()
        before_hash = before.view_hash
        after_hash = after.view_hash

        accepted_refs = _sort_refs(
            [
                OwnerRef(
                    owner="run_authority",
                    record_type="decision",
                    identity=after.run_id,
                    schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                    locator=f"decision://{decision.decision_id}",
                    digest=_record_digest(decision),
                    cursor=f"journal:{after.journal_cursor}",
                )
                for decision in after.decisions
            ]
            + [
                OwnerRef(
                    owner="run_authority",
                    record_type="claim",
                    identity=after.run_id,
                    schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                    locator=f"claim://{claim.claim_id}",
                    digest=_record_digest(claim),
                    cursor=f"journal:{after.journal_cursor}",
                )
                for claim in after.claims
            ]
        )
        custody_refs = _active_custody_refs(
            self._active_custody_provider,
            cursor=f"journal:{after.journal_cursor}",
        )
        torn = before_hash != after_hash
        if torn:
            disposition = SourceReadDisposition.INCOHERENT
            reason = SourceReadFailure.VERSION_TEAR
        else:
            disposition = SourceReadDisposition.COHERENT
            reason = None
        return RunAuthorityAcceptedOutcomeRead(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            run_id=after.run_id,
            run_revision=after.run_revision,
            environment=self._environment,
            journal_cursor=after.journal_cursor,
            before_view_hash=before_hash,
            after_view_hash=after_hash,
            version_vector=self._version_vector(before_hash, after_hash),
            accepted_outcome_refs=accepted_refs,
            active_custody_refs=custody_refs,
            active_custody_present=bool(custody_refs),
            disposition=disposition,
            disposition_reason=reason,
            torn=torn,
        )


# ---------------------------------------------------------------------------
# WBC work-evidence adapter
# ---------------------------------------------------------------------------


class WbcWorkEvidenceAdapter:
    """Read-only injected query adapter over WBC/work evidence.

    Holds only a store-like object (the exact ``AttemptLedgerStore``
    read/query/version surface) plus optional environment identity and
    active-custody provider.  It calls ONLY read/query/version methods
    (``read_events``, ``read_ledger``, ``get_terminal_event``,
    ``query_gaps``, ``query_source_cursor``, ``get_contract_version``,
    ``get_store_version``) and never appends, reserves, or updates cursors.
    """

    def __init__(
        self,
        store: WbcReadProvider,
        *,
        environment: EnvironmentId | str | None = None,
        active_custody_provider: Callable[[], Sequence[Any]] | None = None,
    ) -> None:
        self._store = _seal_named_reads(
            store,
            _WBC_READ_OPERATIONS,
            what="WBC work-evidence store",
        )
        self._environment = _environment(environment)
        self._active_custody_provider = _seal_optional_callable(
            active_custody_provider,
            what="WBC active-custody provider",
        )

    def _version_vector(
        self, before: str | None, after: str | None
    ) -> SourceVersionVector:
        return SourceVersionVector(
            owner="wbc",
            source="wbc.attempt_ledger_store",
            environment=self._environment,
            before=before,
            after=after,
        )

    def _unavailable(self, attempt_id: str) -> WbcWorkEvidenceRead:
        return WbcWorkEvidenceRead(
            attempt_id=attempt_id,
            environment=self._environment,
            version_vector=self._version_vector(None, None),
            disposition=SourceReadDisposition.UNKNOWN,
            disposition_reason=SourceReadFailure.SOURCE_UNAVAILABLE,
        )

    def read(
        self, attempt_id: str, *, cursor_key: str = "default"
    ) -> WbcWorkEvidenceRead:
        """Capture one version-coherent WBC work-evidence read.

        Returns immutable locators/digests/cursors and before/after contract
        and store versions.  A version tear is typed
        ``INCOHERENT``/``VERSION_TEAR``; a cursor gap is typed
        ``INCOHERENT``/``CURSOR_GAP``; an unavailable source is typed
        ``UNKNOWN``/``SOURCE_UNAVAILABLE``.
        """
        try:
            before_contract = self._store.get_contract_version()
            before_store = self._store.get_store_version()
            events = tuple(self._store.read_events(attempt_id))
            ledger = self._store.read_ledger(attempt_id)
            gaps = tuple(self._store.query_gaps(attempt_id))
            cursor = self._store.query_source_cursor(attempt_id, cursor_key)
            after_contract = self._store.get_contract_version()
            after_store = self._store.get_store_version()
        except Exception:
            return self._unavailable(attempt_id)

        event_refs = tuple(
            WbcEventRef(
                attempt_id=attempt_id,
                sequence=event.sequence,
                event_type=event.event_type.value,
                idempotency_key=event.idempotency_key,
                digest=_record_digest(event),
                locator=f"wbc://{attempt_id}/{event.sequence}",
            )
            for event in events
        )
        ledger_ref = (
            OwnerRef(
                owner="wbc",
                record_type="ledger",
                identity=attempt_id,
                schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                locator=f"ledger://{attempt_id}",
                digest=_record_digest(ledger),
                cursor=(
                    f"sequence:{ledger.last_event.sequence if ledger.last_event else 0}"
                ),
            )
            if ledger is not None
            else None
        )
        cursor_ref = (
            SourceCursorRef(
                attempt_id=attempt_id,
                cursor_key=cursor.cursor_key,
                last_sequence=cursor.last_sequence,
                last_position=cursor.last_position,
                digest=_record_digest(cursor),
            )
            if cursor is not None
            else None
        )
        gap_refs = _sort_refs(
            OwnerRef(
                owner="wbc",
                record_type="gap",
                identity=attempt_id,
                schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                locator=f"gap://{attempt_id}/{gap.gap_start}:{gap.gap_end}",
                digest=_record_digest(gap),
                cursor=f"sequence:{gap.gap_end}",
            )
            for gap in gaps
        )
        custody_refs = _active_custody_refs(
            self._active_custody_provider,
            cursor=f"sequence:{after_store}",
        )

        torn = (
            before_contract != after_contract or before_store != after_store
        )
        if torn:
            disposition = SourceReadDisposition.INCOHERENT
            reason = SourceReadFailure.VERSION_TEAR
        elif gaps:
            disposition = SourceReadDisposition.INCOHERENT
            reason = SourceReadFailure.CURSOR_GAP
        else:
            disposition = SourceReadDisposition.COHERENT
            reason = None
        before_vector = f"contract:{before_contract}|store:{before_store}"
        after_vector = f"contract:{after_contract}|store:{after_store}"
        return WbcWorkEvidenceRead(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            attempt_id=attempt_id,
            environment=self._environment,
            contract_version_before=before_contract,
            contract_version_after=after_contract,
            store_version_before=before_store,
            store_version_after=after_store,
            version_vector=self._version_vector(before_vector, after_vector),
            event_refs=event_refs,
            ledger_ref=ledger_ref,
            source_cursor=cursor_ref,
            gap_refs=gap_refs,
            active_custody_refs=custody_refs,
            active_custody_present=bool(custody_refs),
            disposition=disposition,
            disposition_reason=reason,
            torn=torn,
        )


# ---------------------------------------------------------------------------
# Custody lease/history read (Step 8 / T8)
# ---------------------------------------------------------------------------


class CustodyLeaseHistoryRead(BaseModel):
    """Immutable result of one locator-only Custody lease/history capture.

    Carries the exact before/after history digests captured around the read
    (``history_version_before`` / ``history_version_after`` plus the shared
    :class:`SourceVersionVector`), locator-only references to the current
    lease state (``lease_ref``) and its history events (``history_refs``) —
    never the lease records themselves.  Active-custody availability is
    retained as the typed ``active_lease_present`` flag.  The custody lease
    records carry no cost/quality/model coordinates, so those stay typed
    UNKNOWN (:class:`EvidenceUnknownKind`) — never coerced to zero.  A
    version tear is typed ``INCOHERENT``/``VERSION_TEAR``; a cross-environment
    join or unavailable store is typed ``UNKNOWN`` and carries no references.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    lease_id: StrictStr
    environment: EnvironmentId | None = None
    history_version_before: StrictStr | None = None
    history_version_after: StrictStr | None = None
    version_vector: SourceVersionVector
    #: Locator-only reference to the current lease state (active OR
    #: terminated); ``None`` when no lease exists for the id.
    lease_ref: OwnerRef | None = None
    active_lease_present: bool = False
    history_refs: tuple[OwnerRef, ...] = ()
    conflict_count: int = Field(default=0, ge=0)
    #: Typed-unknown cost/quality/model coordinates (custody records never
    #: carry them; downstream economics must treat them as unknown).
    cost: float | None = Field(default=None, ge=0)
    quality: float | None = None
    model: ModelId | None = None
    unknown_evidence: tuple[EvidenceUnknownKind, ...] = ()
    disposition: SourceReadDisposition = SourceReadDisposition.COHERENT
    disposition_reason: SourceReadFailure | None = None
    torn: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("lease_id")
    @classmethod
    def _validate_lease_id(cls, value: str) -> str:
        if not value:
            raise ValueError("lease_id must be a non-empty string")
        return value

    @field_validator("history_refs")
    @classmethod
    def _sort_history_refs(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @field_validator("unknown_evidence")
    @classmethod
    def _dedupe_unknowns(
        cls, value: Sequence[EvidenceUnknownKind]
    ) -> tuple[EvidenceUnknownKind, ...]:
        return tuple(sorted(set(value), key=lambda kind: kind.value))

    @field_validator("quality")
    @classmethod
    def _validate_quality(cls, value: float | None) -> float | None:
        if value is not None and not 0.0 <= value <= 1.0:
            raise ValueError(f"quality must be in [0, 1], got {value}")
        return value

    @model_validator(mode="after")
    def _check_disposition(self) -> CustodyLeaseHistoryRead:
        _validate_read_disposition(
            disposition=self.disposition,
            disposition_reason=self.disposition_reason,
            torn=self.torn,
            before=self.history_version_before,
            after=self.history_version_after,
            has_refs=self.lease_ref is not None or bool(self.history_refs),
            label="custody",
        )
        if self.active_lease_present and self.lease_ref is None:
            raise ValueError(
                "active_lease_present=True requires an active lease_ref"
            )
        _check_unknown_evidence(
            cost=self.cost,
            quality=self.quality,
            model=self.model,
            unknown_evidence=self.unknown_evidence,
        )
        return self

    @property
    def digest(self) -> str:
        """Canonical digest of the whole read result (replayable)."""
        return canonical_digest(self)


class CustodyLeaseHistoryAdapter:
    """Read-only injected query adapter over the Custody lease store history.

    Holds only a store-like object exposing the exact read surface
    (``load_history`` / ``replay_history``) plus optional environment
    identity.  It calls ONLY read/replay methods — never acquire, renew,
    transfer, release, expire, fence, reclaim, or ``record_event``.  Emits
    locator-only refs to the current lease state and its history events;
    active-custody availability is retained as a typed flag; missing
    cost/quality/model coordinates are typed UNKNOWN; version tears and
    cross-environment joins fail closed.
    """

    #: Terminal lifecycle event types: a lease whose last lifecycle event is
    #: one of these is NOT actively held by any worker.
    _TERMINAL_EVENT_TYPES: frozenset[str] = frozenset(
        {"release", "expire", "fence"}
    )

    def __init__(
        self,
        store: CustodyReadProvider,
        *,
        environment: EnvironmentId | str | None = None,
    ) -> None:
        self._store = _seal_named_reads(
            store,
            _CUSTODY_READ_OPERATIONS,
            metadata=("environment",),
            what="Custody lease-history store",
        )
        self._environment = _environment(environment)

    def _version_vector(
        self, before: str | None, after: str | None
    ) -> SourceVersionVector:
        return SourceVersionVector(
            owner="custody",
            source="custody.lease_store",
            environment=self._environment,
            before=before,
            after=after,
        )

    def _unavailable(self, lease_id: str) -> CustodyLeaseHistoryRead:
        return CustodyLeaseHistoryRead(
            lease_id=lease_id,
            environment=self._environment,
            version_vector=self._version_vector(None, None),
            disposition=SourceReadDisposition.UNKNOWN,
            disposition_reason=SourceReadFailure.SOURCE_UNAVAILABLE,
        )

    def _cross_environment(self, lease_id: str) -> CustodyLeaseHistoryRead:
        return CustodyLeaseHistoryRead(
            lease_id=lease_id,
            environment=self._environment,
            version_vector=self._version_vector(None, None),
            disposition=SourceReadDisposition.UNKNOWN,
            disposition_reason=SourceReadFailure.CROSS_ENVIRONMENT,
        )

    @staticmethod
    def _history_version(events: Sequence[Any]) -> str:
        """Deterministic history version: sha256 of the canonical event set."""
        material = canonical_json([_to_plain(event.to_dict()) for event in events])
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _last_lifecycle_event_type(events: Sequence[Any]) -> str | None:
        """Event type of the last non-conflict lifecycle event (or None)."""
        for event in reversed(events):
            if getattr(event, "event_type", None) != "conflict":
                return event.event_type
        return None

    def read(self, lease_id: str) -> CustodyLeaseHistoryRead:
        """Capture one version-coherent Custody lease/history read.

        Returns immutable locators/digests/cursors and before/after history
        digests.  A version tear is typed ``INCOHERENT``/``VERSION_TEAR``; an
        unavailable store or a cross-environment join is typed ``UNKNOWN``
        with the typed reason and no references.
        """
        declared = getattr(self._store, "environment", None)
        if declared is not None and self._environment is not None:
            try:
                declared_env = (
                    declared
                    if isinstance(declared, EnvironmentId)
                    else _environment(str(declared))
                )
            except ValueError:
                # An unparseable owner-declared environment fails closed.
                return self._cross_environment(lease_id)
            if declared_env != self._environment:
                return self._cross_environment(lease_id)
        try:
            before_events = tuple(self._store.load_history(lease_id))
            before_version = self._history_version(before_events)
            lease = self._store.replay_history(lease_id)
            after_events = tuple(self._store.load_history(lease_id))
            after_version = self._history_version(after_events)
        except Exception:
            return self._unavailable(lease_id)

        last_sequence = after_events[-1].sequence if after_events else 0
        terminal = self._last_lifecycle_event_type(after_events)
        lease_ref: OwnerRef | None = None
        active = False
        if lease is not None:
            active = terminal not in self._TERMINAL_EVENT_TYPES
            lease_ref = OwnerRef(
                owner="custody",
                record_type="lease",
                identity=lease_id,
                schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                locator=f"custody://{lease_id}",
                digest=_record_digest(lease),
                cursor=f"sequence:{last_sequence}",
            )
        history_refs = _sort_refs(
            OwnerRef(
                owner="custody",
                record_type="lease_event",
                identity=lease_id,
                schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                locator=f"custody://{lease_id}/{event.sequence}",
                digest=_record_digest(event),
                cursor=f"sequence:{event.sequence}",
            )
            for event in after_events
        )
        conflict_count = sum(
            1 for event in after_events if getattr(event, "event_type", None) == "conflict"
        )

        torn = before_version != after_version
        if torn:
            disposition = SourceReadDisposition.INCOHERENT
            reason = SourceReadFailure.VERSION_TEAR
        else:
            disposition = SourceReadDisposition.COHERENT
            reason = None
        return CustodyLeaseHistoryRead(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            lease_id=lease_id,
            environment=self._environment,
            history_version_before=before_version,
            history_version_after=after_version,
            version_vector=self._version_vector(before_version, after_version),
            lease_ref=lease_ref,
            active_lease_present=active,
            history_refs=history_refs,
            conflict_count=conflict_count,
            cost=None,
            quality=None,
            model=None,
            unknown_evidence=(
                EvidenceUnknownKind.COST,
                EvidenceUnknownKind.QUALITY,
                EvidenceUnknownKind.MODEL,
            ),
            disposition=disposition,
            disposition_reason=reason,
            torn=torn,
        )


# ---------------------------------------------------------------------------
# Native proof/quality read (Step 8 / T8)
# ---------------------------------------------------------------------------


class NativeProofQualityRead(BaseModel):
    """Immutable result of one locator-only Native proof/quality capture.

    Carries the exact before/after proof digests captured around the read,
    locator-only references to the proof and quality records, and
    sensitive-evidence availability as a typed flag with locator-only
    references (``sensitive_evidence_refs``) — raw prompt/provider payloads
    are never copied.  Missing cost/quality/model coordinates are typed
    UNKNOWN (:class:`EvidenceUnknownKind`); a version tear is typed
    ``INCOHERENT``/``VERSION_TEAR``; a missing proof, unavailable source, or
    cross-environment join is typed ``UNKNOWN`` with no references.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    proof_id: StrictStr
    subject: StrictStr
    environment: EnvironmentId | None = None
    proof_version_before: StrictStr | None = None
    proof_version_after: StrictStr | None = None
    version_vector: SourceVersionVector
    proof_ref: OwnerRef | None = None
    quality_refs: tuple[OwnerRef, ...] = ()
    sensitive_evidence_present: bool = False
    sensitive_evidence_refs: tuple[OwnerRef, ...] = ()
    cost: float | None = Field(default=None, ge=0)
    quality: float | None = None
    model: ModelId | None = None
    unknown_evidence: tuple[EvidenceUnknownKind, ...] = ()
    disposition: SourceReadDisposition = SourceReadDisposition.COHERENT
    disposition_reason: SourceReadFailure | None = None
    torn: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("proof_id", "subject")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("proof_id/subject must be non-empty strings")
        return value

    @field_validator("quality_refs", "sensitive_evidence_refs")
    @classmethod
    def _sort_ref_lists(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @field_validator("unknown_evidence")
    @classmethod
    def _dedupe_unknowns(
        cls, value: Sequence[EvidenceUnknownKind]
    ) -> tuple[EvidenceUnknownKind, ...]:
        return tuple(sorted(set(value), key=lambda kind: kind.value))

    @field_validator("quality")
    @classmethod
    def _validate_quality(cls, value: float | None) -> float | None:
        if value is not None and not 0.0 <= value <= 1.0:
            raise ValueError(f"quality must be in [0, 1], got {value}")
        return value

    @model_validator(mode="after")
    def _check_disposition(self) -> NativeProofQualityRead:
        _validate_read_disposition(
            disposition=self.disposition,
            disposition_reason=self.disposition_reason,
            torn=self.torn,
            before=self.proof_version_before,
            after=self.proof_version_after,
            has_refs=(
                self.proof_ref is not None
                or bool(self.quality_refs)
                or bool(self.sensitive_evidence_refs)
            ),
            label="native",
        )
        if self.sensitive_evidence_present != bool(self.sensitive_evidence_refs):
            raise ValueError(
                "sensitive_evidence_present must match the presence of "
                "sensitive_evidence_refs"
            )
        _check_unknown_evidence(
            cost=self.cost,
            quality=self.quality,
            model=self.model,
            unknown_evidence=self.unknown_evidence,
        )
        return self

    @property
    def digest(self) -> str:
        """Canonical digest of the whole read result (replayable)."""
        return canonical_digest(self)


class NativeProofQualityAdapter:
    """Read-only injected query adapter over Native proof and quality evidence.

    Consumes injected read providers for the proof record, the quality
    record, and (optionally) sensitive evidence records.  It NEVER submits,
    approves, or writes proofs/quality, never instantiates a competing
    completion engine, and never copies sensitive payloads: sensitive
    evidence is retained only as availability plus locator-only references.
    Missing cost/quality/model coordinates are typed UNKNOWN; version tears,
    missing proofs, unavailable sources, and cross-environment joins fail
    closed.
    """

    def __init__(
        self,
        *,
        proof_provider: Callable[[str], Any],
        quality_provider: Callable[[str], Any] | None = None,
        sensitive_provider: Callable[[str], Sequence[Any]] | None = None,
        environment: EnvironmentId | str | None = None,
    ) -> None:
        self._proof_provider = _seal_callable(
            proof_provider, what="Native proof provider"
        )
        self._quality_provider = _seal_optional_callable(
            quality_provider, what="Native quality provider"
        )
        self._sensitive_provider = _seal_optional_callable(
            sensitive_provider, what="Native sensitive-evidence provider"
        )
        self._environment = _environment(environment)

    def _version_vector(
        self, before: str | None, after: str | None
    ) -> SourceVersionVector:
        return SourceVersionVector(
            owner="native_manifest",
            source="native/proof_quality",
            environment=self._environment,
            before=before,
            after=after,
        )

    def _unknown(
        self,
        proof_id: str,
        subject: str,
        reason: SourceReadFailure,
    ) -> NativeProofQualityRead:
        return NativeProofQualityRead(
            proof_id=proof_id,
            subject=subject,
            environment=self._environment,
            version_vector=self._version_vector(None, None),
            disposition=SourceReadDisposition.UNKNOWN,
            disposition_reason=reason,
        )

    def read(self, proof_id: str, subject: str) -> NativeProofQualityRead:
        """Capture one version-coherent Native proof/quality read.

        Returns immutable locators/digests/cursors and before/after proof
        digests.  A version tear is typed ``INCOHERENT``/``VERSION_TEAR``; a
        missing proof, unavailable source, or cross-environment join is typed
        ``UNKNOWN`` with the typed reason and no references.
        """
        declared = getattr(self._proof_provider, "environment", None)
        if declared is not None and self._environment is not None:
            try:
                declared_env = (
                    declared
                    if isinstance(declared, EnvironmentId)
                    else _environment(str(declared))
                )
            except ValueError:
                return self._unknown(
                    proof_id, subject, SourceReadFailure.CROSS_ENVIRONMENT
                )
            if declared_env != self._environment:
                return self._unknown(
                    proof_id, subject, SourceReadFailure.CROSS_ENVIRONMENT
                )
        try:
            before_proof = self._proof_provider(proof_id)
            before_version = _record_digest(before_proof) if before_proof is not None else None
            proof = self._proof_provider(proof_id)
            quality = (
                self._quality_provider(proof_id)
                if self._quality_provider is not None
                else None
            )
            sensitive = (
                tuple(self._sensitive_provider(proof_id))
                if self._sensitive_provider is not None
                else ()
            )
            after_proof = self._proof_provider(proof_id)
            after_version = _record_digest(after_proof) if after_proof is not None else None
        except Exception:
            return self._unknown(proof_id, subject, SourceReadFailure.SOURCE_UNAVAILABLE)

        if proof is None:
            return self._unknown(proof_id, subject, SourceReadFailure.RECORD_MISSING)

        cost = getattr(quality, "cost", None) if quality is not None else None
        quality_score = (
            getattr(quality, "quality_score", None) if quality is not None else None
        )
        if quality_score is None and quality is not None:
            quality_score = getattr(quality, "quality", None)
        model = getattr(quality, "model", None) if quality is not None else None

        proof_ref = OwnerRef(
            owner="native_manifest",
            record_type="negative_control_proof",
            identity=subject,
            schema_version=str(MAINTENANCE_SCHEMA_VERSION),
            locator=f"native/proof_quality//{subject}",
            digest=_record_digest(proof),
            cursor=f"digest:{after_version}",
        )
        quality_refs = _sort_refs(
            [
                OwnerRef(
                    owner="native_manifest",
                    record_type="quality",
                    identity=subject,
                    schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                    locator=f"native/proof_quality//{subject}/quality",
                    digest=_record_digest(quality),
                )
            ]
            if quality is not None
            else []
        )
        sensitive_refs = _sort_refs(
            OwnerRef(
                owner="native_manifest",
                record_type="sensitive_evidence",
                identity=subject,
                schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                locator=f"native/proof_quality//{subject}/sensitive/{index}",
                digest=_record_digest(record),
            )
            for index, record in enumerate(sensitive)
        )

        unknowns: list[EvidenceUnknownKind] = []
        if cost is None:
            unknowns.append(EvidenceUnknownKind.COST)
        if quality_score is None:
            unknowns.append(EvidenceUnknownKind.QUALITY)
        if model is None:
            unknowns.append(EvidenceUnknownKind.MODEL)

        torn = before_version != after_version
        if torn:
            disposition = SourceReadDisposition.INCOHERENT
            reason = SourceReadFailure.VERSION_TEAR
        else:
            disposition = SourceReadDisposition.COHERENT
            reason = None
        return NativeProofQualityRead(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            proof_id=proof_id,
            subject=subject,
            environment=self._environment,
            proof_version_before=before_version,
            proof_version_after=after_version,
            version_vector=self._version_vector(before_version, after_version),
            proof_ref=proof_ref,
            quality_refs=quality_refs,
            sensitive_evidence_present=bool(sensitive_refs),
            sensitive_evidence_refs=sensitive_refs,
            cost=cost,
            quality=quality_score,
            model=model,
            unknown_evidence=tuple(unknowns),
            disposition=disposition,
            disposition_reason=reason,
            torn=torn,
        )


# ---------------------------------------------------------------------------
# Convenience read-only entry points
# ---------------------------------------------------------------------------


def read_run_authority_accepted_outcomes(
    view_provider: Callable[[], Any],
    *,
    environment: EnvironmentId | str | None = None,
    active_custody_provider: Callable[[], Sequence[Any]] | None = None,
) -> RunAuthorityAcceptedOutcomeRead:
    """Convenience Run Authority accepted-outcome capture (see adapter)."""
    return RunAuthorityAcceptedOutcomeAdapter(
        view_provider,
        environment=environment,
        active_custody_provider=active_custody_provider,
    ).read()


def read_wbc_work_evidence(
    store: WbcReadProvider,
    attempt_id: str,
    *,
    environment: EnvironmentId | str | None = None,
    active_custody_provider: Callable[[], Sequence[Any]] | None = None,
    cursor_key: str = "default",
) -> WbcWorkEvidenceRead:
    """Convenience WBC work-evidence capture (see adapter)."""
    return WbcWorkEvidenceAdapter(
        store,
        environment=environment,
        active_custody_provider=active_custody_provider,
    ).read(attempt_id, cursor_key=cursor_key)


def read_custody_lease_history(
    store: CustodyReadProvider,
    lease_id: str,
    *,
    environment: EnvironmentId | str | None = None,
) -> CustodyLeaseHistoryRead:
    """Convenience Custody lease/history capture (see adapter)."""
    return CustodyLeaseHistoryAdapter(
        store,
        environment=environment,
    ).read(lease_id)


def read_native_proof_quality(
    proof_id: str,
    subject: str,
    *,
    proof_provider: Callable[[str], Any],
    quality_provider: Callable[[str], Any] | None = None,
    sensitive_provider: Callable[[str], Sequence[Any]] | None = None,
    environment: EnvironmentId | str | None = None,
) -> NativeProofQualityRead:
    """Convenience Native proof/quality capture (see adapter)."""
    return NativeProofQualityAdapter(
        proof_provider=proof_provider,
        quality_provider=quality_provider,
        sensitive_provider=sensitive_provider,
        environment=environment,
    ).read(proof_id, subject)


# ---------------------------------------------------------------------------
# Open-ticket snapshot read (Step 9 / T9)
# ---------------------------------------------------------------------------
# The open-ticket lookup is an injected read-only exact-version query: the
# lookup provider (tickets.core.snapshot_open_tickets or a store-backed
# equivalent) captures path-stat coordinates, row count, and a content digest
# before/after the read.  A proven no-match carries the explicit stable
# no-match identity; a torn read is typed UNKNOWN and can never authorize a
# false ticket match.  The adapter NEVER creates, edits, or addresses tickets.

#: Explicit stable identity representing a PROVEN no-match open ticket
#: (Step 9): distinct from every real ticket identity and stable across
#: windows so proposal keys that include the open-ticket identity stay
#: deterministic for the no-match case.
NO_MATCH_TICKET_IDENTITY: str = "no_open_ticket_match"


def _snapshot_version(stats: Sequence[tuple[str, int, int]]) -> str:
    """Deterministic version string over path-stat coordinates (never guessed)."""
    return hashlib.sha256(
        canonical_json([list(entry) for entry in stats]).encode("utf-8")
    ).hexdigest()


class OpenTicketSnapshotRead(BaseModel):
    """Immutable result of one scoped open-ticket snapshot read (Step 9 / T9).

    Carries the exact-version ticket identity — the matching open ticket's
    stable identity, or :data:`NO_MATCH_TICKET_IDENTITY` for a proven
    no-match — plus the snapshot coordinates (path-stat-derived version,
    row count, content digest) and a locator-only reference to the matched
    ticket (never the ticket record itself).  A read whose snapshot cannot be
    proven stable (file changed mid-read) is typed ``UNKNOWN`` with
    ``MID_READ_MUTATION`` and carries no ticket reference — a torn read can
    never silently authorize a false ticket match.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    environment: EnvironmentId | None = None
    snapshot_version_before: StrictStr | None = None
    snapshot_version_after: StrictStr | None = None
    version_vector: SourceVersionVector
    #: Matching open-ticket identity or NO_MATCH_TICKET_IDENTITY (stable).
    ticket_identity: StrictStr | None = None
    matched: bool = False
    #: Locator-only reference to the matched open ticket (never copied).
    ticket_ref: OwnerRef | None = None
    row_count: int = Field(default=0, ge=0)
    content_digest: StrictStr | None = None
    disposition: SourceReadDisposition = SourceReadDisposition.COHERENT
    disposition_reason: SourceReadFailure | None = None
    torn: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("ticket_identity")
    @classmethod
    def _validate_ticket_identity(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("ticket_identity must be a non-empty string when present")
        return value

    @field_validator("content_digest")
    @classmethod
    def _validate_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_sha256(value, what="open-ticket content digest")

    @model_validator(mode="after")
    def _check_disposition(self) -> OpenTicketSnapshotRead:
        _validate_read_disposition(
            disposition=self.disposition,
            disposition_reason=self.disposition_reason,
            torn=self.torn,
            before=self.snapshot_version_before,
            after=self.snapshot_version_after,
            has_refs=self.ticket_ref is not None,
            label="open-ticket",
        )
        if self.matched and self.ticket_ref is None:
            raise ValueError("matched=True requires a locator-only ticket_ref")
        if not self.matched and self.disposition is SourceReadDisposition.COHERENT:
            # A proven no-match still carries the stable no-match identity.
            if self.ticket_identity != NO_MATCH_TICKET_IDENTITY:
                raise ValueError(
                    "a coherent no-match read must carry the stable "
                    f"no-match identity {NO_MATCH_TICKET_IDENTITY!r}"
                )
        if self.disposition is SourceReadDisposition.UNKNOWN:
            if self.ticket_identity is not None or self.matched:
                raise ValueError(
                    "unknown open-ticket reads cannot carry a ticket identity"
                )
        return self

    @property
    def digest(self) -> str:
        """Canonical digest of the whole read result (replayable)."""
        return canonical_digest(self)


class OpenTicketLookupAdapter:
    """Read-only injected query adapter over the open-ticket snapshot reader.

    Holds only a lookup provider (the tickets.core snapshot API or a
    store-backed equivalent) plus optional environment identity.  It calls
    ONLY the read-only snapshot API and exposes no mutation method: it never
    creates, edits, addresses, or completes tickets.  A proven no-match
    carries the explicit stable no-match identity; a torn read is typed
    ``UNKNOWN``/``MID_READ_MUTATION`` with no ticket reference.
    """

    def __init__(
        self,
        lookup_provider: Callable[[], Any],
        *,
        environment: EnvironmentId | str | None = None,
    ) -> None:
        self._lookup_provider = _seal_callable(
            lookup_provider, what="Open-ticket lookup provider"
        )
        self._environment = _environment(environment)

    def _version_vector(
        self, before: str | None, after: str | None
    ) -> SourceVersionVector:
        return SourceVersionVector(
            owner="plan",
            source="tickets.open_ticket_snapshot",
            environment=self._environment,
            before=before,
            after=after,
        )

    def read(self) -> OpenTicketSnapshotRead:
        """Capture one version-coherent open-ticket snapshot read.

        Returns the exact-version ticket identity (or the stable no-match
        identity), the snapshot coordinates, and a locator-only ticket
        reference.  A snapshot that cannot be proven stable (file changed
        mid-read) is typed ``UNKNOWN``/``MID_READ_MUTATION`` and carries no
        ticket reference.
        """
        snapshot = self._lookup_provider()
        if not getattr(snapshot, "stable", False):
            return OpenTicketSnapshotRead(
                environment=self._environment,
                version_vector=self._version_vector(None, None),
                disposition=SourceReadDisposition.UNKNOWN,
                disposition_reason=SourceReadFailure.MID_READ_MUTATION,
            )
        before = _snapshot_version(snapshot.file_stats_before)
        after = _snapshot_version(snapshot.file_stats_after)
        matched_id = snapshot.ticket_id
        ticket_ref = None
        if matched_id is not None:
            ticket_ref = OwnerRef(
                owner="plan",
                record_type="open_ticket",
                identity=matched_id,
                schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                locator=f"ticket://{matched_id}",
                digest=snapshot.content_digest,
                cursor=f"rows:{snapshot.row_count}",
            )
        return OpenTicketSnapshotRead(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            environment=self._environment,
            snapshot_version_before=before,
            snapshot_version_after=after,
            version_vector=self._version_vector(before, after),
            ticket_identity=(
                matched_id if matched_id is not None else NO_MATCH_TICKET_IDENTITY
            ),
            matched=matched_id is not None,
            ticket_ref=ticket_ref,
            row_count=snapshot.row_count,
            content_digest=snapshot.content_digest,
            disposition=SourceReadDisposition.COHERENT,
            disposition_reason=None,
            torn=False,
        )


# ---------------------------------------------------------------------------
# Dispatch-receipt high-water read (Step 9 / T9)
# ---------------------------------------------------------------------------


class DispatchReceiptHighWaterRead(BaseModel):
    """Immutable result of one dispatch-receipt high-water capture (Step 9).

    Carries the byte and row high-water coordinates, the whole-file content
    digest, locator-only per-row references (row number + line digest — raw
    receipt payloads are never copied), and the before/after file-stat
    versions captured around the read.  A mid-read mutation is typed
    ``UNKNOWN``/``MID_READ_MUTATION``; a cursor mismatch (the byte high-water
    does not match the pre-read file size) is typed
    ``UNKNOWN``/``CURSOR_MISMATCH``; both carry no references and can never
    support a finding.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    environment: EnvironmentId | None = None
    file_version_before: StrictStr | None = None
    file_version_after: StrictStr | None = None
    version_vector: SourceVersionVector
    byte_high_water: int = Field(default=0, ge=0)
    row_high_water: int = Field(default=0, ge=0)
    content_digest: StrictStr | None = None
    receipt_refs: tuple[OwnerRef, ...] = ()
    disposition: SourceReadDisposition = SourceReadDisposition.COHERENT
    disposition_reason: SourceReadFailure | None = None
    torn: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("receipt_refs")
    @classmethod
    def _sort_receipt_refs(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @field_validator("content_digest")
    @classmethod
    def _validate_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_sha256(value, what="receipt content digest")

    @model_validator(mode="after")
    def _check_disposition(self) -> DispatchReceiptHighWaterRead:
        _validate_read_disposition(
            disposition=self.disposition,
            disposition_reason=self.disposition_reason,
            torn=self.torn,
            before=self.file_version_before,
            after=self.file_version_after,
            has_refs=bool(self.receipt_refs),
            label="dispatch-receipt",
        )
        if self.disposition is SourceReadDisposition.UNKNOWN:
            if self.row_high_water or self.content_digest is not None:
                raise ValueError(
                    "unknown dispatch-receipt reads cannot carry coordinates"
                )
        if (
            self.disposition_reason is SourceReadFailure.CURSOR_MISMATCH
            and self.disposition is not SourceReadDisposition.UNKNOWN
        ):
            raise ValueError("CURSOR_MISMATCH reads must be typed UNKNOWN")
        return self

    @property
    def digest(self) -> str:
        """Canonical digest of the whole read result (replayable)."""
        return canonical_digest(self)


class DispatchReceiptsAdapter:
    """Read-only injected query adapter over the dispatch-receipts reader.

    Holds only a receipt provider (receipts.query.read_receipt_high_water or
    a fake) plus optional environment identity.  It calls ONLY the read-only
    high-water snapshot API and never appends, rewrites, or truncates the
    receipt log.  Emits the byte/row high-water coordinates, the content
    digest, and locator-only per-row references; mid-read mutations and
    cursor mismatches fail closed as typed UNKNOWN reads.
    """

    def __init__(
        self,
        receipt_provider: Callable[[], Any],
        *,
        environment: EnvironmentId | str | None = None,
    ) -> None:
        self._receipt_provider = _seal_callable(
            receipt_provider, what="Dispatch-receipt provider"
        )
        self._environment = _environment(environment)

    def _version_vector(
        self, before: str | None, after: str | None
    ) -> SourceVersionVector:
        return SourceVersionVector(
            owner="plan",
            source="receipts.high_water",
            environment=self._environment,
            before=before,
            after=after,
        )

    def _unknown(
        self, reason: SourceReadFailure
    ) -> DispatchReceiptHighWaterRead:
        return DispatchReceiptHighWaterRead(
            environment=self._environment,
            version_vector=self._version_vector(None, None),
            disposition=SourceReadDisposition.UNKNOWN,
            disposition_reason=reason,
        )

    def read(self) -> DispatchReceiptHighWaterRead:
        """Capture one version-coherent dispatch-receipt high-water read.

        Returns the byte/row high-water coordinates, the content digest, and
        locator-only per-row references.  A mid-read mutation is typed
        ``UNKNOWN``/``MID_READ_MUTATION``; a cursor mismatch is typed
        ``UNKNOWN``/``CURSOR_MISMATCH``.
        """
        high_water = self._receipt_provider()
        if not getattr(high_water, "stable", False):
            reason = getattr(high_water, "reason", None)
            return self._unknown(
                SourceReadFailure.CURSOR_MISMATCH
                if reason == "cursor_mismatch"
                else SourceReadFailure.MID_READ_MUTATION
            )
        before = f"mtime:{high_water.stat_before[0]}|size:{high_water.stat_before[1]}"
        after = f"mtime:{high_water.stat_after[0]}|size:{high_water.stat_after[1]}"
        receipt_refs = _sort_refs(
            OwnerRef(
                owner="plan",
                record_type="dispatch_receipt",
                identity=str(row_number),
                schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                locator=f"receipts.jsonl//{row_number}",
                digest=line_digest,
                cursor=f"bytes:{high_water.byte_high_water}|rows:{high_water.row_high_water}",
            )
            for row_number, line_digest in high_water.row_digests
        )
        return DispatchReceiptHighWaterRead(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            environment=self._environment,
            file_version_before=before,
            file_version_after=after,
            version_vector=self._version_vector(before, after),
            byte_high_water=high_water.byte_high_water,
            row_high_water=high_water.row_high_water,
            content_digest=high_water.content_digest,
            receipt_refs=receipt_refs,
            disposition=SourceReadDisposition.COHERENT,
            disposition_reason=None,
            torn=False,
        )


def read_open_ticket_snapshot(
    *,
    cwd: Any = None,
    environment: EnvironmentId | str | None = None,
    keywords: Sequence[str] | None = None,
) -> OpenTicketSnapshotRead:
    """Convenience open-ticket snapshot capture wired to the real reader.

    Uses ``tickets.core.snapshot_open_tickets`` (local-only file mode); a
    store-configured equivalent can be injected through
    :class:`OpenTicketLookupAdapter` directly.
    """
    from arnold_pipelines.megaplan.tickets.core import snapshot_open_tickets  # noqa: PLC0415

    return OpenTicketLookupAdapter(
        lambda: snapshot_open_tickets(cwd=cwd, status="open", keywords=keywords),
        environment=environment,
    ).read()


def read_dispatch_receipt_high_water(
    path: Any,
    *,
    environment: EnvironmentId | str | None = None,
) -> DispatchReceiptHighWaterRead:
    """Convenience dispatch-receipt high-water capture (see adapter)."""
    from arnold_pipelines.megaplan.receipts.query import (  # noqa: PLC0415
        read_receipt_high_water,
    )

    return DispatchReceiptsAdapter(
        lambda: read_receipt_high_water(path),
        environment=environment,
    ).read()


# ---------------------------------------------------------------------------
# Coherent single-environment ObservationEnvelope join (Step 10 / T10)
# ---------------------------------------------------------------------------
# The join binds the six owner reads (Run Authority accepted outcomes, WBC
# work evidence, Custody lease/history, Native proof/quality, open-ticket
# snapshot, dispatch-receipt high water) into ONE coherent, complete,
# single-environment envelope per normalized task/milestone outcome.  The
# envelope carries the normalized route/robustness/environment/classifier
# coordinates, the exact accepted-outcome identity, the owner version
# vectors (read log), and the immutable references — never owner payloads.
#
# Fail-closed join rules (SC11): a torn, stale, incomplete, cursor-gapped,
# or cross-environment (contaminated) owner page makes the WHOLE envelope a
# typed UNKNOWN/INCOHERENT non-supporting fact that carries NO owner
# versions and NO immutable references, so it can support neither a finding
# nor a proposal.  ``supports_finding`` / ``supports_proposal`` are part of
# the contract and are ``True`` exactly when the envelope is COHERENT.


def _vector_sort_key(vector: SourceVersionVector | dict[str, Any]) -> tuple[Any, ...]:
    """Canonical version-vector sort key (owner, source, env, before, after).

    Accepts both validated :class:`SourceVersionVector` instances and raw
    dicts (strict-decode input) so owner versions stay canonically ordered
    for every constructed or decoded envelope.
    """
    if isinstance(vector, dict):
        owner = vector.get("owner", "")
        source = vector.get("source", "")
        env = vector.get("environment")
        before = vector.get("before")
        after = vector.get("after")
    else:
        owner = vector.owner
        source = vector.source
        env = vector.environment
        before = vector.before
        after = vector.after
    env_root = env.root if hasattr(env, "root") else (env or "")
    return (
        owner,
        source,
        env_root or "",
        before or "",
        after or "",
    )


class CoherentObservationEnvelope(BaseModel):
    """One coherent single-environment M5 observation envelope (Step 10).

    Binds the normalized route (``stage``/``profile``/``expected_model`` /
    ``resolved_model`` / ``provider_actual_model``), ``robustness``,
    ``environment``, ``classifier_version``, the exact
    ``accepted_outcome_identity``, the owner version vectors captured around
    the six reads, and the immutable references — never owner payloads.

    Fail-closed (SC11): ``supports_finding`` and ``supports_proposal`` are
    ``True`` exactly when ``disposition`` is ``COHERENT``.  A torn, stale,
    incomplete, cursor-gapped, or cross-environment (contaminated) page is a
    typed UNKNOWN/INCOHERENT non-supporting fact carrying NO owner versions
    and NO immutable references — it can never back a finding or proposal.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    #: Stable page identity derived from the normalized outcome identity and
    #: the environment/classifier coordinates (never from owner occurrence
    #: IDs); identical normalized pages derive the same envelope identity.
    envelope_id: StrictStr
    task_or_milestone_identity: StrictStr
    stage: StrictStr
    profile: StrictStr | None = None
    expected_model: ModelId | None = None
    resolved_model: ModelId | None = None
    #: Provider-reported actual model from the Native quality read (exact
    #: when present, typed unknown/absent when the owner does not report one).
    provider_actual_model: ModelId | None = None
    robustness: RobustnessKind | None = None
    environment: EnvironmentId | None = None
    classifier_version: StrictStr
    #: Exact accepted-outcome identity (``run_id@run_revision``) of the
    #: accepted decision/claim anchor; every normalized outcome binds one.
    accepted_outcome_identity: StrictStr | None = None
    #: Before/after version vectors of the six owner reads (the read log),
    #: canonically sorted and deduplicated.
    owner_versions: tuple[SourceVersionVector, ...] = ()
    #: Sorted union of the immutable OwnerRefs across the six reads
    #: (accepted outcomes, custody, source records, tickets, receipts).
    immutable_refs: tuple[OwnerRef, ...] = ()
    #: Typed WBC event refs (digest + locator only), kept in their own
    #: reference family (WbcEventRef is not an OwnerRef).
    wbc_event_refs: tuple[WbcEventRef, ...] = ()
    #: Typed WBC source-cursor coordinate (digest only), when present.
    wbc_source_cursor: SourceCursorRef | None = None
    disposition: SourceReadDisposition = SourceReadDisposition.COHERENT
    disposition_reason: SourceReadFailure | None = None
    torn: bool = False
    stale: bool = False
    incomplete: bool = False
    gapped: bool = False
    contaminated: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("envelope_id", "task_or_milestone_identity", "stage",
                     "classifier_version")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "envelope_id/task_or_milestone_identity/stage/classifier_version "
                "must be non-empty strings"
            )
        return value

    @field_validator("immutable_refs")
    @classmethod
    def _sort_ref_lists(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @field_validator("wbc_event_refs")
    @classmethod
    def _sort_wbc_events(
        cls, value: Sequence[WbcEventRef]
    ) -> tuple[WbcEventRef, ...]:
        return tuple(sorted(value, key=lambda ref: (ref.attempt_id, ref.sequence)))

    @field_validator("owner_versions", mode="before")
    @classmethod
    def _sort_versions(cls, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return sorted(value, key=_vector_sort_key)
        return value

    @model_validator(mode="after")
    def _enforce_fail_closed(self) -> CoherentObservationEnvelope:
        if self.disposition is SourceReadDisposition.COHERENT:
            if self.disposition_reason is not None:
                raise ValueError(
                    "coherent envelopes cannot carry a disposition_reason"
                )
            if self.torn or self.stale or self.incomplete or self.gapped or self.contaminated:
                raise ValueError(
                    "coherent envelopes cannot carry torn/stale/incomplete/"
                    "gapped/contaminated flags"
                )
            if self.environment is None:
                raise ValueError(
                    "coherent envelopes require an exact single environment"
                )
            if self.accepted_outcome_identity is None:
                raise ValueError(
                    "coherent envelopes require an exact accepted_outcome_identity"
                )
            if not self.owner_versions:
                raise ValueError(
                    "coherent envelopes require exact owner version vectors"
                )
            if not self.immutable_refs:
                raise ValueError(
                    "coherent envelopes require at least one immutable reference"
                )
        else:  # UNKNOWN / INCOHERENT — a non-supporting fact
            if self.disposition_reason is None:
                raise ValueError(
                    "non-coherent envelopes require a typed disposition_reason"
                )
            if self.owner_versions or self.immutable_refs:
                raise ValueError(
                    "non-coherent envelopes cannot carry owner versions or "
                    "immutable references (non-supporting facts)"
                )
            if self.wbc_event_refs or self.wbc_source_cursor is not None:
                raise ValueError(
                    "non-coherent envelopes cannot carry WBC event/cursor refs"
                )
            if self.torn:
                if (
                    self.disposition is not SourceReadDisposition.INCOHERENT
                    or self.disposition_reason is not SourceReadFailure.VERSION_TEAR
                ):
                    raise ValueError(
                        "torn envelopes must be typed INCOHERENT with VERSION_TEAR"
                    )
            if self.contaminated:
                if self.disposition_reason is not SourceReadFailure.CROSS_ENVIRONMENT:
                    raise ValueError(
                        "contaminated envelopes require CROSS_ENVIRONMENT"
                    )
            if self.stale and self.disposition_reason is not SourceReadFailure.STALE:
                raise ValueError("stale envelopes require STALE")
            if self.incomplete and self.disposition_reason is not SourceReadFailure.INCOMPLETE:
                raise ValueError("incomplete envelopes require INCOMPLETE")
            if self.gapped and self.disposition_reason not in (
                SourceReadFailure.CURSOR_GAP,
                SourceReadFailure.CURSOR_MISMATCH,
                SourceReadFailure.MID_READ_MUTATION,
            ):
                raise ValueError(
                    "gapped envelopes require CURSOR_GAP/CURSOR_MISMATCH/"
                    "MID_READ_MUTATION"
                )
        return self

    @property
    def supports_finding(self) -> bool:
        """True only when the envelope is fully coherent (SC11 fail-closed)."""
        return self.disposition is SourceReadDisposition.COHERENT

    @property
    def supports_proposal(self) -> bool:
        """True only when the envelope is fully coherent (SC11 fail-closed)."""
        return self.disposition is SourceReadDisposition.COHERENT

    @property
    def digest(self) -> str:
        """Canonical digest of the whole envelope (replayable)."""
        return canonical_digest(self)


def _envelope_failure(
    *,
    task_or_milestone_identity: str,
    stage: str,
    classifier_version: str,
    reason: SourceReadFailure,
    disposition: SourceReadDisposition,
    torn: bool = False,
    stale: bool = False,
    incomplete: bool = False,
    gapped: bool = False,
    contaminated: bool = False,
) -> CoherentObservationEnvelope:
    """Build a typed non-supporting envelope (no versions, no refs)."""
    return CoherentObservationEnvelope(
        envelope_id=derive_envelope_id(
            task_or_milestone_identity,
            stage=stage,
            classifier_version=classifier_version,
        ),
        task_or_milestone_identity=task_or_milestone_identity,
        stage=stage,
        classifier_version=classifier_version,
        disposition=disposition,
        disposition_reason=reason,
        torn=torn,
        stale=stale,
        incomplete=incomplete,
        gapped=gapped,
        contaminated=contaminated,
    )


def derive_envelope_id(
    task_or_milestone_identity: str,
    *,
    stage: str,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> str:
    """Deterministic envelope page identity from the normalized identity.

    ``daily_efficiency_envelope|{sha256(task|stage|classifier_version)}``
    over the normalized outcome identity — never over owner occurrence IDs —
    so the same normalized page derives the same envelope identity across
    windows.
    """
    if not task_or_milestone_identity or not stage or not classifier_version:
        raise ValueError(
            "envelope identity requires a task/milestone identity, stage, "
            "and classifier version"
        )
    material = canonical_json(
        {
            "family": "efficiency_observation_envelope",
            "task_or_milestone_identity": task_or_milestone_identity,
            "stage": stage,
            "classifier_version": classifier_version,
        }
    )
    return f"daily_efficiency_envelope|{hashlib.sha256(material.encode('utf-8')).hexdigest()}"


def _model(value: ModelId | str | None) -> ModelId | None:
    """Coerce a model coordinate, failing fast on unknown identities."""
    if value is None:
        return None
    if isinstance(value, ModelId):
        return value
    return ModelId(value)


def _robustness(value: RobustnessKind | str | None) -> RobustnessKind | None:
    """Coerce a robustness coordinate, failing fast on unknown vocab."""
    if value is None:
        return None
    if isinstance(value, RobustnessKind):
        return value
    return RobustnessKind(value)


def join_observation_envelope(
    *,
    task_or_milestone_identity: str,
    stage: str,
    accepted_outcome_read: RunAuthorityAcceptedOutcomeRead,
    wbc_read: WbcWorkEvidenceRead,
    custody_read: CustodyLeaseHistoryRead,
    native_read: NativeProofQualityRead,
    ticket_read: OpenTicketSnapshotRead,
    receipt_read: DispatchReceiptHighWaterRead,
    profile: str | None = None,
    expected_model: ModelId | str | None = None,
    resolved_model: ModelId | str | None = None,
    robustness: RobustnessKind | str | None = None,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
    expected_environment: EnvironmentId | str | None = None,
    expected_versions: Mapping[str, str] | None = None,
) -> CoherentObservationEnvelope:
    """Join the six owner reads into ONE coherent envelope (Step 10 / T10).

    Fail-closed join rules (SC11): ANY torn, cursor-gapped, mid-read-mutated,
    cursor-mismatched, unavailable, missing-record, stale, incomplete, or
    cross-environment owner page makes the WHOLE envelope a typed
    UNKNOWN/INCOHERENT non-supporting fact carrying no owner versions and no
    immutable references.  Such a page can support neither a finding nor a
    proposal.

    * ``expected_environment`` is the authoritative single environment; when
      omitted it is taken from the owner reads, and any disagreement between
      owner-declared environments (or with the expected environment) is a
      typed ``CROSS_ENVIRONMENT`` contamination;
    * ``expected_versions`` maps owner *source* (e.g.
      ``"run_authority.view"``, ``"wbc.attempt_ledger_store"``,
      ``"custody.lease_store"``, ``"native/proof_quality"``,
      ``"tickets.open_ticket_snapshot"``, ``"receipts.high_water"``) to the
      expected post-read version captured at an earlier authoritative
      boundary; a read whose post-read version differs is a stale page
      (``STALE``/UNKNOWN);
    * ``provider_actual_model`` is bound from the Native quality read (typed
      unknown/absent when the owner does not report one) — it is never
      inferred.
    """
    reads: tuple[tuple[str, BaseModel], ...] = (
        ("run_authority", accepted_outcome_read),
        ("wbc", wbc_read),
        ("custody", custody_read),
        ("native_manifest", native_read),
        ("tickets", ticket_read),
        ("receipts", receipt_read),
    )

    def _failure(
        reason: SourceReadFailure,
        *,
        disposition: SourceReadDisposition = SourceReadDisposition.UNKNOWN,
        **flags: bool,
    ) -> CoherentObservationEnvelope:
        return _envelope_failure(
            task_or_milestone_identity=task_or_milestone_identity,
            stage=stage,
            classifier_version=classifier_version,
            reason=reason,
            disposition=disposition,
            **flags,
        )

    # 1. Every owner read must itself be coherent (torn/gapped/missing pages
    #    fail the whole envelope with the first offending owner's typed
    #    reason, in a fixed deterministic owner order).
    for label, read in reads:
        if read.disposition is not SourceReadDisposition.COHERENT:
            reason = read.disposition_reason or SourceReadFailure.SOURCE_UNAVAILABLE
            if reason is SourceReadFailure.VERSION_TEAR:
                return _failure(
                    reason,
                    disposition=SourceReadDisposition.INCOHERENT,
                    torn=True,
                )
            if reason in (
                SourceReadFailure.CURSOR_GAP,
                SourceReadFailure.CURSOR_MISMATCH,
                SourceReadFailure.MID_READ_MUTATION,
            ):
                # CURSOR_GAP reads are typed INCOHERENT at the owner level;
                # the other two are typed UNKNOWN — the envelope preserves
                # the offending read's exact disposition.
                disposition = (
                    SourceReadDisposition.INCOHERENT
                    if reason is SourceReadFailure.CURSOR_GAP
                    else SourceReadDisposition.UNKNOWN
                )
                return _failure(reason, disposition=disposition, gapped=True)
            if reason is SourceReadFailure.CROSS_ENVIRONMENT:
                return _failure(reason, contaminated=True)
            return _failure(reason)

    # 2. Single-environment: the authoritative expected environment must
    #    agree with every owner-declared environment; absent coordinates are
    #    never inferred, and an envelope without any environment coordinate
    #    is incomplete (cannot prove single-environment binding).
    declared = [read.environment for _, read in reads if read.environment is not None]
    expected_env = (
        _environment(expected_environment)
        if expected_environment is not None
        else (_environment(declared[0]) if declared else None)
    )
    if expected_env is None:
        return _failure(SourceReadFailure.INCOMPLETE, incomplete=True)
    for label, read in reads:
        if read.environment is not None and read.environment != expected_env:
            return _failure(SourceReadFailure.CROSS_ENVIRONMENT, contaminated=True)

    # 3. Staleness: an owner source whose post-read version differs from the
    #    caller's expected version (captured at an authoritative boundary)
    #    is a stale page — never mixed into a coherent envelope.
    if expected_versions:
        for label, read in reads:
            vector = read.version_vector
            expected = expected_versions.get(vector.source)
            if expected is not None and vector.after != expected:
                return _failure(SourceReadFailure.STALE, stale=True)

    # 4. Completeness: every normalized outcome binds an exact accepted
    #    outcome, so the Run Authority read must carry accepted-outcome
    #    refs and an exact run identity.
    if not accepted_outcome_read.accepted_outcome_refs:
        return _failure(SourceReadFailure.INCOMPLETE, incomplete=True)
    if (
        accepted_outcome_read.run_id is None
        or accepted_outcome_read.run_revision is None
    ):
        return _failure(SourceReadFailure.INCOMPLETE, incomplete=True)

    # 5. Bind the coherent envelope.
    refs = _sort_refs(
        [
            *accepted_outcome_read.accepted_outcome_refs,
            *accepted_outcome_read.active_custody_refs,
            *wbc_read.gap_refs,
            *( [wbc_read.ledger_ref] if wbc_read.ledger_ref is not None else [] ),
            *wbc_read.active_custody_refs,
            *( [custody_read.lease_ref] if custody_read.lease_ref is not None else [] ),
            *custody_read.history_refs,
            *( [native_read.proof_ref] if native_read.proof_ref is not None else [] ),
            *native_read.quality_refs,
            *native_read.sensitive_evidence_refs,
            *( [ticket_read.ticket_ref] if ticket_read.ticket_ref is not None else [] ),
            *receipt_read.receipt_refs,
        ]
    )
    if not refs:
        return _failure(SourceReadFailure.INCOMPLETE, incomplete=True)

    seen: set[tuple[Any, ...]] = set()
    vectors: list[SourceVersionVector] = []
    for _, read in reads:
        vector = read.version_vector
        key = _vector_sort_key(vector)
        if key not in seen:
            seen.add(key)
            vectors.append(vector)
    owner_versions = tuple(sorted(vectors, key=_vector_sort_key))

    return CoherentObservationEnvelope(
        envelope_id=derive_envelope_id(
            task_or_milestone_identity,
            stage=stage,
            classifier_version=classifier_version,
        ),
        task_or_milestone_identity=task_or_milestone_identity,
        stage=stage,
        profile=profile,
        expected_model=_model(expected_model),
        resolved_model=_model(resolved_model),
        provider_actual_model=native_read.model,
        robustness=_robustness(robustness),
        environment=expected_env,
        classifier_version=classifier_version,
        accepted_outcome_identity=(
            f"{accepted_outcome_read.run_id}@{accepted_outcome_read.run_revision}"
        ),
        owner_versions=owner_versions,
        immutable_refs=refs,
        wbc_event_refs=wbc_read.event_refs,
        wbc_source_cursor=wbc_read.source_cursor,
        disposition=SourceReadDisposition.COHERENT,
        disposition_reason=None,
        torn=False,
        stale=False,
        incomplete=False,
        gapped=False,
        contaminated=False,
    )


# ---------------------------------------------------------------------------
# Plan Step 11 / T11: normalized work-fact layer (non-content features +
# immutable references only)
# ---------------------------------------------------------------------------
# The coherent envelope (Step 10) binds route/robustness/environment/
# classifier/accepted-outcome/owner-version coordinates and the immutable
# references, but it deliberately carries NO work-ledger facts.  This layer
# normalizes the typed NON-CONTENT work-ledger features (event types,
# timestamps, operation/duplicate/failure signatures, stage transitions,
# cost/token/time/quality coordinates) into the pure analyzer fact
# contracts consumed by Steps 13-15 (NormalizedCall /
# NormalizedDwellObservation / NormalizedHandoffObservation /
# NormalizedRepairPatternObservation) plus the per-accepted-outcome
# economics coordinates.
#
# Rules (locked Step 11 policy):
# * only non-content features and immutable references are consumed —
#   prompts, provider payloads, and owner records are never copied;
# * every normalized fact binds the envelope's exact accepted-outcome
#   anchor and the envelope's immutable refs partitioned into the typed
#   reference families (accepted resolution / active custody / source);
# * problem signatures stay separate from operational occurrence IDs;
# * missing and censored measures (elapsed vs lower bound, cost/tokens/
#   time/quality) are preserved WITHOUT zero or completion coercion;
# * a non-coherent envelope yields an EMPTY non-supporting bundle that
#   mirrors the envelope's disposition — torn/stale/gapped/incomplete/
#   contaminated pages never invent facts.


class CallFacts(BaseModel):
    """Non-content features of one work-ledger call/attempt (Step 11 input).

    Carries ONLY normalized non-content coordinates: the operational call
    identity, stage, closed outcome, the normalized failure/operation/
    duplicate problem signatures, and the exact time measures.  Owner
    identity is attached exclusively through the envelope's immutable
    references — never through copied owner records.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    call_id: StrictStr
    stage: StrictStr
    outcome: analysis_mod.CallOutcome
    failure_signature: StrictStr | None = None
    operation_key: StrictStr | None = None
    duplicate_key: StrictStr | None = None
    started_at: UtcTime | None = None
    ended_at: UtcTime | None = None
    elapsed_seconds: float | None = Field(default=None, ge=0)
    no_progress_delta_seconds: float | None = Field(default=None, ge=0)
    censored: bool = False

    @field_validator("call_id", "stage")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        if not value:
            raise ValueError("call_id and stage must be non-empty strings")
        return value

    @field_validator("failure_signature", "operation_key", "duplicate_key")
    @classmethod
    def _validate_signatures(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError(
                "normalized signatures must be non-empty strings when present"
            )
        return value


class DwellLegFacts(BaseModel):
    """Non-content features of one gate/finalize/review dwell leg (Step 11).

    Mirrors the Step 13 leg discipline: a completed leg carries its exact
    ``elapsed_seconds``; a censored leg carries no completion duration and
    an explicit ``lower_bound_seconds`` — never coerced to completion or
    zero.  The exclusion flags are the machine-checkable basis of the
    shared Step 13 exclusion model (SC14).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    observation_id: StrictStr
    kind: DwellFindingKind
    stage: StrictStr
    started_at: UtcTime | None = None
    ended_at: UtcTime | None = None
    elapsed_seconds: float | None = Field(default=None, ge=0)
    censored: bool = False
    lower_bound_seconds: float | None = Field(default=None, ge=0)
    slo_seconds: float | None = Field(default=None, ge=0)
    deep_work: bool = False
    exploration: bool = False
    configured_backoff: bool = False
    human_gate: bool = False
    productive: bool = False

    @field_validator("observation_id", "stage")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        if not value:
            raise ValueError("observation_id and stage must be non-empty strings")
        return value

    @model_validator(mode="after")
    def _check_leg(self) -> DwellLegFacts:
        if self.censored:
            if self.elapsed_seconds is not None:
                raise ValueError(
                    "censored dwell legs cannot carry a completion elapsed_seconds"
                )
            if self.lower_bound_seconds is None:
                raise ValueError(
                    "censored dwell legs require an explicit lower_bound_seconds"
                )
        else:
            if self.elapsed_seconds is None:
                raise ValueError(
                    "completed dwell legs require an exact elapsed_seconds"
                )
            if self.lower_bound_seconds is not None:
                raise ValueError(
                    "completed dwell legs cannot carry a lower_bound_seconds"
                )
        return self


class HandoffFacts(BaseModel):
    """Non-content features of one idle handoff leg (Step 11 input).

    Mirrors the Step 15 handoff discipline: completed handoffs carry an
    exact ``idle_seconds``; censored handoffs carry an explicit
    ``lower_bound_seconds`` and never a completion duration.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    observation_id: StrictStr
    from_stage: StrictStr
    to_stage: StrictStr
    handed_off_at: UtcTime | None = None
    idle_seconds: float | None = Field(default=None, ge=0)
    censored: bool = False
    lower_bound_seconds: float | None = Field(default=None, ge=0)
    deep_work: bool = False
    exploration: bool = False
    configured_backoff: bool = False
    human_gate: bool = False
    productive: bool = False

    @field_validator("observation_id", "from_stage", "to_stage")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        if not value:
            raise ValueError("handoff identity/stages must be non-empty strings")
        return value

    @model_validator(mode="after")
    def _check_handoff(self) -> HandoffFacts:
        if self.from_stage == self.to_stage:
            raise ValueError(
                "idle handoff stages must differ "
                f"({self.from_stage!r} == {self.to_stage!r})"
            )
        if self.censored:
            if self.idle_seconds is not None:
                raise ValueError(
                    "censored handoffs cannot carry an exact idle_seconds"
                )
            if self.lower_bound_seconds is None:
                raise ValueError(
                    "censored handoffs require an explicit lower_bound_seconds"
                )
        else:
            if self.idle_seconds is None:
                raise ValueError("completed handoffs require an exact idle_seconds")
            if self.lower_bound_seconds is not None:
                raise ValueError(
                    "completed handoffs cannot carry a lower_bound_seconds"
                )
        return self


class RepairOccurrenceFacts(BaseModel):
    """Non-content features of one recurring-repair occurrence (Step 11).

    ``repair_signature`` is the normalized non-content problem signature
    (never an occurrence ID); occurrences sharing ``(affected_contract,
    repair_signature)`` group into one repair pattern (Step 15 / SC16).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    observation_id: StrictStr
    affected_contract: StrictStr
    repair_signature: StrictStr
    occurred_at: UtcTime | None = None

    @field_validator("observation_id", "affected_contract", "repair_signature")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "repair-pattern observation identity/contract/signature must "
                "be non-empty strings"
            )
        return value


class WorkEvidenceFacts(BaseModel):
    """Typed non-content work-ledger features for ONE coherent envelope.

    Carries ONLY normalized non-content features — call/leg/handoff/
    repair-occurrence coordinates plus the per-accepted-outcome
    cost/token/time/quality coordinates — never prompts, provider payloads,
    or owner records.  Missing coordinates stay explicit ``None`` and may
    carry their typed :class:`EvidenceUnknownKind` reason; they are never
    coerced to zero.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    calls: tuple[CallFacts, ...] = ()
    dwell_legs: tuple[DwellLegFacts, ...] = ()
    handoffs: tuple[HandoffFacts, ...] = ()
    repair_occurrences: tuple[RepairOccurrenceFacts, ...] = ()
    cost: float | None = Field(default=None, ge=0)
    tokens: int | None = Field(default=None, ge=0)
    time_seconds: float | None = Field(default=None, ge=0)
    quality: float | None = Field(default=None, ge=0)
    unknown_evidence: tuple[EvidenceUnknownKind, ...] = ()

    @field_validator("unknown_evidence")
    @classmethod
    def _dedupe_unknowns(
        cls, value: Sequence[EvidenceUnknownKind]
    ) -> tuple[EvidenceUnknownKind, ...]:
        return tuple(sorted(set(value), key=lambda kind: kind.value))

    @field_validator("quality")
    @classmethod
    def _validate_quality(cls, value: float | None) -> float | None:
        if value is not None and not 0.0 <= value <= 1.0:
            raise ValueError(f"quality must be in [0, 1], got {value}")
        return value

    @model_validator(mode="after")
    def _check_unknown_evidence(self) -> WorkEvidenceFacts:
        _check_unknown_evidence(
            cost=self.cost,
            quality=self.quality,
            model=None,
            unknown_evidence=self.unknown_evidence,
        )
        return self


class NormalizedEconomicsFacts(BaseModel):
    """Normalized per-accepted-outcome cost/tokens/time/quality coordinates.

    ``accepted_outcome_count`` is always exactly 1 — a coherent envelope
    binds exactly one accepted outcome.  Missing coordinates stay explicit
    ``None`` with their typed :class:`EvidenceUnknownKind` reasons; they are
    never coerced to zero (SC12).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    accepted_outcome_count: int = 1
    cost: float | None = Field(default=None, ge=0)
    tokens: int | None = Field(default=None, ge=0)
    time_seconds: float | None = Field(default=None, ge=0)
    quality: float | None = Field(default=None, ge=0)
    unknown_evidence: tuple[EvidenceUnknownKind, ...] = ()

    @field_validator("accepted_outcome_count")
    @classmethod
    def _validate_denominator(cls, value: int) -> int:
        if value != 1:
            raise ValueError(
                "normalized economics facts always bind exactly one accepted "
                f"outcome, got {value}"
            )
        return value

    @field_validator("unknown_evidence")
    @classmethod
    def _dedupe_unknowns(
        cls, value: Sequence[EvidenceUnknownKind]
    ) -> tuple[EvidenceUnknownKind, ...]:
        return tuple(sorted(set(value), key=lambda kind: kind.value))

    @field_validator("quality")
    @classmethod
    def _validate_quality(cls, value: float | None) -> float | None:
        if value is not None and not 0.0 <= value <= 1.0:
            raise ValueError(f"quality must be in [0, 1], got {value}")
        return value

    @model_validator(mode="after")
    def _check_unknown_evidence(self) -> NormalizedEconomicsFacts:
        _check_unknown_evidence(
            cost=self.cost,
            quality=self.quality,
            model=None,
            unknown_evidence=self.unknown_evidence,
        )
        return self


class NormalizedWorkFacts(BaseModel):
    """Step 11 normalized work facts for ONE observation envelope (T11).

    Binds the pure analyzer fact contracts (``NormalizedCall`` /
    ``NormalizedDwellObservation`` / ``NormalizedHandoffObservation`` /
    ``NormalizedRepairPatternObservation``) to the envelope's immutable
    references and preserves the typed economics coordinates.

    Fail-closed (SC11/SC12): ``supports_finding`` is ``True`` exactly when
    the envelope disposition is ``COHERENT``.  A non-coherent envelope
    yields an EMPTY bundle mirroring the envelope's disposition — it never
    invents facts from torn/stale/gapped/incomplete/contaminated pages and
    never copies sensitive content.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    envelope_id: StrictStr
    #: Replayable digest of the source envelope (provenance link).
    envelope_digest: StrictStr
    classifier_version: StrictStr
    disposition: SourceReadDisposition = SourceReadDisposition.COHERENT
    disposition_reason: SourceReadFailure | None = None
    calls: tuple[analysis_mod.NormalizedCall, ...] = ()
    dwell_legs: tuple[analysis_mod.NormalizedDwellObservation, ...] = ()
    handoffs: tuple[analysis_mod.NormalizedHandoffObservation, ...] = ()
    repair_occurrences: tuple[analysis_mod.NormalizedRepairPatternObservation, ...] = ()
    economics: NormalizedEconomicsFacts | None = None

    @field_validator("envelope_id", "envelope_digest", "classifier_version")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "envelope_id/envelope_digest/classifier_version must be "
                "non-empty strings"
            )
        return value

    @field_validator("envelope_digest")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        return _require_sha256(value, what="envelope digest")

    @field_validator("calls")
    @classmethod
    def _sort_calls(
        cls, value: Sequence[analysis_mod.NormalizedCall]
    ) -> tuple[analysis_mod.NormalizedCall, ...]:
        return tuple(sorted(value, key=lambda call: call.call_id))

    @field_validator("dwell_legs")
    @classmethod
    def _sort_dwell_legs(
        cls, value: Sequence[analysis_mod.NormalizedDwellObservation]
    ) -> tuple[analysis_mod.NormalizedDwellObservation, ...]:
        return tuple(sorted(value, key=lambda leg: leg.observation_id))

    @field_validator("handoffs")
    @classmethod
    def _sort_handoffs(
        cls, value: Sequence[analysis_mod.NormalizedHandoffObservation]
    ) -> tuple[analysis_mod.NormalizedHandoffObservation, ...]:
        return tuple(sorted(value, key=lambda handoff: handoff.observation_id))

    @field_validator("repair_occurrences")
    @classmethod
    def _sort_repair_occurrences(
        cls, value: Sequence[analysis_mod.NormalizedRepairPatternObservation]
    ) -> tuple[analysis_mod.NormalizedRepairPatternObservation, ...]:
        return tuple(
            sorted(value, key=lambda occurrence: occurrence.observation_id)
        )

    @model_validator(mode="after")
    def _enforce_fail_closed(self) -> NormalizedWorkFacts:
        if self.disposition is SourceReadDisposition.COHERENT:
            if self.disposition_reason is not None:
                raise ValueError(
                    "coherent normalized work facts cannot carry a "
                    "disposition_reason"
                )
        else:
            if self.disposition_reason is None:
                raise ValueError(
                    "non-coherent normalized work facts require a typed "
                    "disposition_reason"
                )
            if (
                self.calls
                or self.dwell_legs
                or self.handoffs
                or self.repair_occurrences
                or self.economics is not None
            ):
                raise ValueError(
                    "non-coherent normalized work facts cannot carry calls, "
                    "dwell legs, handoffs, repair occurrences, or economics "
                    "(non-supporting facts)"
                )
        return self

    @property
    def supports_finding(self) -> bool:
        """True only when the source envelope is fully coherent (SC11)."""
        return self.disposition is SourceReadDisposition.COHERENT

    @property
    def digest(self) -> str:
        """Canonical digest of the whole normalized bundle (replayable)."""
        return canonical_digest(self)


def _excluded_reason_from_flags(
    *,
    deep_work: bool,
    exploration: bool,
    configured_backoff: bool,
    human_gate: bool,
    productive: bool,
) -> analysis_mod.DwellExclusionReason | None:
    """Map the SC14 exclusion flags to the typed exclusion reason.

    Raises when more than one flag is set (a normalized fact can carry at
    most one typed exclusion reason); returns ``None`` when no flag is set.
    """
    flagged = [
        reason
        for flag, reason in (
            (deep_work, analysis_mod.DwellExclusionReason.LEGITIMATE_DEPTH),
            (exploration, analysis_mod.DwellExclusionReason.EXPLORATION),
            (configured_backoff, analysis_mod.DwellExclusionReason.CONFIGURED_BACKOFF),
            (human_gate, analysis_mod.DwellExclusionReason.HUMAN_GATE),
            (productive, analysis_mod.DwellExclusionReason.PRODUCTIVE),
        )
        if flag
    ]
    if len(flagged) > 1:
        raise ValueError(
            "a normalized fact cannot carry multiple exclusion flags"
        )
    return flagged[0] if flagged else None


def _partition_envelope_refs(
    envelope: CoherentObservationEnvelope,
) -> tuple[tuple[OwnerRef, ...], tuple[OwnerRef, ...], tuple[OwnerRef, ...]]:
    """Partition the envelope's immutable refs into finding-reference families.

    Returns ``(accepted_resolution_refs, active_custody_refs, source_refs)``:

    * accepted resolution — owner ``run_authority`` (the exact accepted
      decision/claim anchors);
    * active custody — owner ``repair_custody`` (reference/covariate only,
      never claimed);
    * source refs — the remaining owner evidence locators (wbc, custody,
      native_manifest, plan) that pin the normalized facts' source evidence.
    """
    accepted: list[OwnerRef] = []
    custody: list[OwnerRef] = []
    sources: list[OwnerRef] = []
    for ref in envelope.immutable_refs:
        if ref.owner == "run_authority":
            accepted.append(ref)
        elif ref.owner == "repair_custody":
            custody.append(ref)
        else:
            sources.append(ref)
    return _sort_refs(accepted), _sort_refs(custody), _sort_refs(sources)


def normalize_observation_facts(
    envelope: CoherentObservationEnvelope,
    facts: WorkEvidenceFacts | None = None,
    *,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> NormalizedWorkFacts:
    """Normalize ONE coherent envelope into pure analyzer facts (Step 11).

    * non-coherent envelopes yield an EMPTY non-supporting bundle that
      mirrors the envelope's disposition — normalization never invents
      facts from torn/stale/gapped/incomplete/contaminated pages;
    * every normalized fact binds the envelope's exact accepted-outcome
      anchor (``accepted_outcome_id`` = the envelope's
      ``accepted_outcome_identity``) and the envelope's immutable
      references partitioned into the typed reference families (accepted
      resolution / active custody / source);
    * problem signatures (failure/operation/duplicate keys) stay separate
      from operational occurrence IDs, and missing or censored measures
      (elapsed vs lower bound, cost/tokens/time/quality) are preserved
      without zero or completion coercion (SC12);
    * only non-content features and immutable references are consumed —
      prompts and provider payloads are never copied.
    """
    facts = facts if facts is not None else WorkEvidenceFacts()
    if not envelope.supports_finding:
        return NormalizedWorkFacts(
            envelope_id=envelope.envelope_id,
            envelope_digest=envelope.digest,
            classifier_version=classifier_version,
            disposition=envelope.disposition,
            disposition_reason=envelope.disposition_reason,
            calls=(),
            dwell_legs=(),
            handoffs=(),
            repair_occurrences=(),
            economics=None,
        )

    accepted_resolution_refs, active_custody_refs, source_refs = (
        _partition_envelope_refs(envelope)
    )

    calls = tuple(
        analysis_mod.NormalizedCall(
            call_id=call.call_id,
            stage=call.stage,
            outcome=call.outcome,
            failure_signature=call.failure_signature,
            operation_key=call.operation_key,
            duplicate_key=call.duplicate_key,
            accepted_outcome_id=envelope.accepted_outcome_identity,
            started_at=call.started_at,
            ended_at=call.ended_at,
            elapsed_seconds=call.elapsed_seconds,
            no_progress_delta_seconds=call.no_progress_delta_seconds,
            censored=call.censored,
            refs=source_refs,
            accepted_resolution_refs=accepted_resolution_refs,
            gate_backoff_refs=(),
            censoring_refs=(),
            active_custody_refs=active_custody_refs,
        )
        for call in facts.calls
    )

    dwell_legs = tuple(
        analysis_mod.NormalizedDwellObservation(
            observation_id=leg.observation_id,
            kind=leg.kind,
            stage=leg.stage,
            started_at=leg.started_at,
            ended_at=leg.ended_at,
            elapsed_seconds=leg.elapsed_seconds,
            censored=leg.censored,
            lower_bound_seconds=leg.lower_bound_seconds,
            slo_seconds=leg.slo_seconds,
            excluded_reason=_excluded_reason_from_flags(
                deep_work=leg.deep_work,
                exploration=leg.exploration,
                configured_backoff=leg.configured_backoff,
                human_gate=leg.human_gate,
                productive=leg.productive,
            ),
            deep_work=leg.deep_work,
            exploration=leg.exploration,
            configured_backoff=leg.configured_backoff,
            human_gate=leg.human_gate,
            productive=leg.productive,
            accepted_outcome_id=envelope.accepted_outcome_identity,
            refs=source_refs,
            accepted_resolution_refs=accepted_resolution_refs,
            gate_backoff_refs=(),
            censoring_refs=(),
            active_custody_refs=active_custody_refs,
        )
        for leg in facts.dwell_legs
    )

    handoffs = tuple(
        analysis_mod.NormalizedHandoffObservation(
            observation_id=handoff.observation_id,
            from_stage=handoff.from_stage,
            to_stage=handoff.to_stage,
            handed_off_at=handoff.handed_off_at,
            idle_seconds=handoff.idle_seconds,
            censored=handoff.censored,
            lower_bound_seconds=handoff.lower_bound_seconds,
            excluded_reason=_excluded_reason_from_flags(
                deep_work=handoff.deep_work,
                exploration=handoff.exploration,
                configured_backoff=handoff.configured_backoff,
                human_gate=handoff.human_gate,
                productive=handoff.productive,
            ),
            deep_work=handoff.deep_work,
            exploration=handoff.exploration,
            configured_backoff=handoff.configured_backoff,
            human_gate=handoff.human_gate,
            productive=handoff.productive,
            accepted_outcome_id=envelope.accepted_outcome_identity,
            refs=source_refs,
            accepted_resolution_refs=accepted_resolution_refs,
            gate_backoff_refs=(),
            censoring_refs=(),
            active_custody_refs=active_custody_refs,
        )
        for handoff in facts.handoffs
    )

    repair_occurrences = tuple(
        analysis_mod.NormalizedRepairPatternObservation(
            observation_id=occurrence.observation_id,
            affected_contract=occurrence.affected_contract,
            repair_signature=occurrence.repair_signature,
            occurred_at=occurrence.occurred_at,
            accepted_outcome_id=envelope.accepted_outcome_identity,
            refs=source_refs,
            accepted_resolution_refs=accepted_resolution_refs,
            gate_backoff_refs=(),
            censoring_refs=(),
            active_custody_refs=active_custody_refs,
        )
        for occurrence in facts.repair_occurrences
    )

    economics = (
        NormalizedEconomicsFacts(
            cost=facts.cost,
            tokens=facts.tokens,
            time_seconds=facts.time_seconds,
            quality=facts.quality,
            unknown_evidence=facts.unknown_evidence,
        )
        if (
            facts.cost is not None
            or facts.tokens is not None
            or facts.time_seconds is not None
            or facts.quality is not None
            or facts.unknown_evidence
        )
        else None
    )

    return NormalizedWorkFacts(
        envelope_id=envelope.envelope_id,
        envelope_digest=envelope.digest,
        classifier_version=classifier_version,
        disposition=SourceReadDisposition.COHERENT,
        disposition_reason=None,
        calls=calls,
        dwell_legs=dwell_legs,
        handoffs=handoffs,
        repair_occurrences=repair_occurrences,
        economics=economics,
    )


__all__ = [
    "CallFacts",
    "CoherentObservationEnvelope",
    "CustodyLeaseHistoryAdapter",
    "CustodyLeaseHistoryRead",
    "CustodyReadProvider",
    "DEFAULT_CLASSIFIER_VERSION",
    "DispatchReceiptHighWaterRead",
    "DispatchReceiptsAdapter",
    "DwellLegFacts",
    "EvidenceUnknownKind",
    "HandoffFacts",
    "NO_MATCH_TICKET_IDENTITY",
    "NativeProofQualityAdapter",
    "NativeProofQualityRead",
    "NormalizedEconomicsFacts",
    "NormalizedWorkFacts",
    "OpenTicketLookupAdapter",
    "OpenTicketSnapshotRead",
    "ProviderAdmissionError",
    "RepairOccurrenceFacts",
    "RunAuthorityAcceptedOutcomeAdapter",
    "RunAuthorityAcceptedOutcomeRead",
    "SourceReadDisposition",
    "SourceReadFailure",
    "WbcReadProvider",
    "WbcWorkEvidenceAdapter",
    "WbcWorkEvidenceRead",
    "WorkEvidenceFacts",
    "derive_envelope_id",
    "join_observation_envelope",
    "normalize_observation_facts",
    "read_custody_lease_history",
    "read_dispatch_receipt_high_water",
    "read_native_proof_quality",
    "read_open_ticket_snapshot",
    "read_run_authority_accepted_outcomes",
    "read_wbc_work_evidence",
]