"""C1 Contract Reality preflight validators and diagnostic codes.

This module is intentionally observe-only. It defines stable diagnostic codes
and read-only validators for the C1 prerequisite gates:

* Run Authority completion manifest hash / base SHA
* Authority route migration disposition
* Dual mutating ownership detection
* Fixture replay mutability
* Producer mapping completeness
* Migration milestone coverage
* Hash-without-retained-payload design

Every validator emits stable diagnostics and evidence references without
requesting approval, generating waivers, or mutating lifecycle/authority state.

The diagnostic codes and spec registry defined here gate C1 acceptance;
downstream code should not silently pass authority gaps represented by
these failure conditions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


# ── C1 diagnostic code vocabulary ────────────────────────────────────────


class C1RealityDiagnosticCode(StrEnum):
    """Stable diagnostic codes for C1 preflight prerequisite checks.

    Every automatic failure condition in the C1 North Star must map to
    exactly one code. These codes are referenced by evidence documents
    and must not be renamed or repurposed.
    """

    # Run Authority preflight
    RUN_AUTHORITY_MANIFEST_MISMATCH = "C1R001_RUN_AUTHORITY_MANIFEST_MISMATCH"
    RUN_AUTHORITY_BASE_SHA_MISMATCH = "C1R002_RUN_AUTHORITY_BASE_SHA_MISMATCH"

    # Route migration disposition
    ROUTE_MIGRATION_DISPOSITION_MISSING = "C1R003_ROUTE_MIGRATION_DISPOSITION_MISSING"
    ROUTE_MIGRATION_WARN_ONLY_NON_CONFORMANT = (
        "C1R004_ROUTE_MIGRATION_WARN_ONLY_NON_CONFORMANT"
    )

    # Dual mutating ownership
    DUAL_MUTATING_OWNERSHIP = "C1R005_DUAL_MUTATING_OWNERSHIP"

    # Fixture replay mutability
    FIXTURE_REPLAY_MUTABILITY = "C1R006_FIXTURE_REPLAY_MUTABILITY"

    # Producer mapping completeness
    PRODUCER_MAPPING_INCOMPLETE = "C1R007_PRODUCER_MAPPING_INCOMPLETE"

    # Migration coverage
    MIGRATION_COVERAGE_GAP = "C1R008_MIGRATION_COVERAGE_GAP"
    MIGRATION_MILESTONE_MISSING = "C1R009_MIGRATION_MILESTONE_MISSING"

    # Hash-without-retained-payload
    HASH_WITHOUT_RETAINED_PAYLOAD = "C1R010_HASH_WITHOUT_RETAINED_PAYLOAD"


class C1DiagnosticSeverity(StrEnum):
    """C1 preflight diagnostic severity levels."""

    ERROR = "error"
    WARNING = "warning"


# ── Diagnostic spec registry ─────────────────────────────────────────────


@dataclass(frozen=True)
class C1DiagnosticSpec:
    """Machine-readable metadata for one stable C1 diagnostic code."""

    code: C1RealityDiagnosticCode
    severity: C1DiagnosticSeverity
    message_template: str
    remediation: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", C1RealityDiagnosticCode(self.code))
        object.__setattr__(self, "severity", C1DiagnosticSeverity(self.severity))


C1_DIAGNOSTIC_SPECS: tuple[C1DiagnosticSpec, ...] = (
    C1DiagnosticSpec(
        code=C1RealityDiagnosticCode.RUN_AUTHORITY_MANIFEST_MISMATCH,
        severity=C1DiagnosticSeverity.ERROR,
        message_template=(
            "Run Authority completion manifest hash does not match the pinned "
            "prerequisite value; manifest may be stale or tampered"
        ),
        remediation=(
            "verify the manifest against the pinned prerequisite hash "
            "2ed830c5a from the C1 handoff record"
        ),
    ),
    C1DiagnosticSpec(
        code=C1RealityDiagnosticCode.RUN_AUTHORITY_BASE_SHA_MISMATCH,
        severity=C1DiagnosticSeverity.ERROR,
        message_template=(
            "current base SHA does not match the pinned C1 prerequisite base "
            "SHA 432760d13a"
        ),
        remediation=(
            "rebase on the pinned prerequisite base SHA before running C1 "
            "preflight checks"
        ),
    ),
    C1DiagnosticSpec(
        code=C1RealityDiagnosticCode.ROUTE_MIGRATION_DISPOSITION_MISSING,
        severity=C1DiagnosticSeverity.ERROR,
        message_template=(
            "authority route {route_id} has no migration disposition; every "
            "authority-increasing consumer must declare a disposition"
        ),
        remediation=(
            "assign one of enforced, warn-only, shadow-only, informational, "
            "or deferred with an owner/reason"
        ),
    ),
    C1DiagnosticSpec(
        code=C1RealityDiagnosticCode.ROUTE_MIGRATION_WARN_ONLY_NON_CONFORMANT,
        severity=C1DiagnosticSeverity.ERROR,
        message_template=(
            "authority route {route_id} is warn-only for authority-increasing "
            "transitions without a durable prerequisite-owned migration "
            "disposition; warning metadata alone is not acceptance"
        ),
        remediation=(
            "either promote the route to enforced with owner-supplied "
            "migration disposition or defer with an explicit milestone"
        ),
    ),
    C1DiagnosticSpec(
        code=C1RealityDiagnosticCode.DUAL_MUTATING_OWNERSHIP,
        severity=C1DiagnosticSeverity.ERROR,
        message_template=(
            "surface {surface_name} has multiple claimed mutating owners: "
            "{owners}; exactly one mutating owner is required per shared surface"
        ),
        remediation=(
            "assign exactly one mutating owner from Run Authority, "
            "Maintenance, or WBC per the source-to-owner matrix"
        ),
    ),
    C1DiagnosticSpec(
        code=C1RealityDiagnosticCode.FIXTURE_REPLAY_MUTABILITY,
        severity=C1DiagnosticSeverity.ERROR,
        message_template=(
            "fixture replay requires mutation or hidden fallback for "
            "{fixture_ref}; replay must be read-only with typed results"
        ),
        remediation=(
            "ensure fixture replay returns typed compatible/incompatible/"
            "unknown/non_conformant results without rewriting fixtures"
        ),
    ),
    C1DiagnosticSpec(
        code=C1RealityDiagnosticCode.PRODUCER_MAPPING_INCOMPLETE,
        severity=C1DiagnosticSeverity.ERROR,
        message_template=(
            "contract {contract_id} cannot be mapped to a real producer "
            "without inventing filenames or authority evidence"
        ),
        remediation=(
            "map each boundary contract to a real producer path, handler, "
            "and artifact pattern; use typed unknown markers for gaps"
        ),
    ),
    C1DiagnosticSpec(
        code=C1RealityDiagnosticCode.MIGRATION_COVERAGE_GAP,
        severity=C1DiagnosticSeverity.ERROR,
        message_template=(
            "supported producer {producer_ref} is not classified in the "
            "support manifest; 100% coverage is required"
        ),
        remediation=(
            "add an entry to the support manifest with owner, support "
            "status, and C2-C6 migration milestone"
        ),
    ),
    C1DiagnosticSpec(
        code=C1RealityDiagnosticCode.MIGRATION_MILESTONE_MISSING,
        severity=C1DiagnosticSeverity.ERROR,
        message_template=(
            "supported producer {producer_ref} lacks a migration milestone; "
            "every supported step/attempt transition requires a C2-C6 gate"
        ),
        remediation=(
            "assign a migration milestone between C2 and C6; temporary "
            "exceptions require owner, reason, and expiry milestone"
        ),
    ),
    C1DiagnosticSpec(
        code=C1RealityDiagnosticCode.HASH_WITHOUT_RETAINED_PAYLOAD,
        severity=C1DiagnosticSeverity.ERROR,
        message_template=(
            "design relies on hash {hash_ref} without durable payload "
            "retention/retrieval; a digest without retained retrievable "
            "bytes is integrity evidence, not result preservation"
        ),
        remediation=(
            "ensure every hash used for result preservation is accompanied "
            "by a durable object reference with store identity, locator, "
            "digest, and retention class"
        ),
    ),
)

C1_DIAGNOSTIC_SPECS_BY_CODE: Mapping[str, C1DiagnosticSpec] = MappingProxyType(
    {spec.code.value: spec for spec in C1_DIAGNOSTIC_SPECS}
)

# Assert every code has exactly one spec entry.
assert len(C1_DIAGNOSTIC_SPECS_BY_CODE) == len(C1_DIAGNOSTIC_SPECS), (
    "C1 diagnostic spec registry has duplicate codes"
)

# ── C1 preflight diagnostic data shape ───────────────────────────────────


@dataclass(frozen=True)
class C1PreflightDiagnostic:
    """A single read-only C1 preflight finding.

    This is a diagnostic, not a waiver or approval request. Consumers
    must not mutate lifecycle or authority state based on these records.
    """

    code: C1RealityDiagnosticCode
    severity: C1DiagnosticSeverity
    message: str
    evidence_ref: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", C1RealityDiagnosticCode(self.code))
        object.__setattr__(self, "severity", C1DiagnosticSeverity(self.severity))
        if not self.message.strip():
            raise ValueError("C1PreflightDiagnostic.message must be non-empty")
        if not self.evidence_ref.strip():
            raise ValueError("C1PreflightDiagnostic.evidence_ref must be non-empty")

    @property
    def is_error(self) -> bool:
        return self.severity == C1DiagnosticSeverity.ERROR

    @property
    def is_warning(self) -> bool:
        return self.severity == C1DiagnosticSeverity.WARNING


# ── C1 preflight result ──────────────────────────────────────────────────


@dataclass(frozen=True)
class C1PreflightResult:
    """Aggregate result of running all C1 preflight validators.

    The ``passed`` field is True only when every diagnostic is a warning
    (i.e. there are zero error-severity diagnostics).
    """

    diagnostics: tuple[C1PreflightDiagnostic, ...]
    validator_count: int
    total_diagnostics: int
    error_count: int
    warning_count: int

    @property
    def passed(self) -> bool:
        return self.error_count == 0


# ── Validator 1: Run Authority manifest / base SHA ────────────────────────


# Pinned prerequisite values from the C1 handoff record.
C1_PINNED_RUN_AUTHORITY_MANIFEST_HASH = "2ed830c5a"
C1_PINNED_BASE_SHA = "432760d13a"


def validate_run_authority_manifest(
    *,
    manifest_hash: str | None = None,
    base_sha: str | None = None,
) -> list[C1PreflightDiagnostic]:
    """Validate Run Authority manifest hash and base SHA against pinned C1 prerequisites.

    Args:
        manifest_hash: The observed Run Authority completion manifest hash.
        base_sha: The observed git base SHA.

    Returns:
        A list of zero or more diagnostics. An empty list means the
        prerequisite is satisfied.
    """
    diagnostics: list[C1PreflightDiagnostic] = []

    if manifest_hash is None or manifest_hash != C1_PINNED_RUN_AUTHORITY_MANIFEST_HASH:
        spec = C1_DIAGNOSTIC_SPECS_BY_CODE[
            C1RealityDiagnosticCode.RUN_AUTHORITY_MANIFEST_MISMATCH.value
        ]
        diagnostics.append(
            C1PreflightDiagnostic(
                code=C1RealityDiagnosticCode.RUN_AUTHORITY_MANIFEST_MISMATCH,
                severity=C1DiagnosticSeverity.ERROR,
                message=(
                    f"Run Authority manifest hash {manifest_hash!r} does not match "
                    f"pinned prerequisite {C1_PINNED_RUN_AUTHORITY_MANIFEST_HASH!r}"
                ),
                evidence_ref="c1.handoff.run_authority.manifest_hash",
                details={
                    "expected": C1_PINNED_RUN_AUTHORITY_MANIFEST_HASH,
                    "observed": manifest_hash,
                },
            )
        )

    if base_sha is None or base_sha != C1_PINNED_BASE_SHA:
        spec = C1_DIAGNOSTIC_SPECS_BY_CODE[
            C1RealityDiagnosticCode.RUN_AUTHORITY_BASE_SHA_MISMATCH.value
        ]
        diagnostics.append(
            C1PreflightDiagnostic(
                code=C1RealityDiagnosticCode.RUN_AUTHORITY_BASE_SHA_MISMATCH,
                severity=C1DiagnosticSeverity.ERROR,
                message=(
                    f"base SHA {base_sha!r} does not match pinned prerequisite "
                    f"{C1_PINNED_BASE_SHA!r}"
                ),
                evidence_ref="c1.handoff.run_authority.base_sha",
                details={
                    "expected": C1_PINNED_BASE_SHA,
                    "observed": base_sha,
                },
            )
        )

    return diagnostics


# ── Validator 2: Route migration disposition ──────────────────────────────


# Accepted route dispositions.
_VALID_DISPOSITIONS = frozenset(
    {"enforced", "warn-only", "shadow-only", "informational", "deferred"}
)

# Dispositions that are non-conformant for authority-increasing transitions.
_AUTHORITY_INCREASING_DISPOSITIONS = frozenset({"enforced"})
_NON_CONFORMANT_DISPOSITIONS = frozenset({"warn-only"})


def validate_route_migration_dispositions(
    routes: tuple[Mapping[str, Any], ...],
) -> list[C1PreflightDiagnostic]:
    """Validate that every authority route has a proper migration disposition.

    Authority-increasing routes with ``warn-only`` disposition are flagged
    as non-conformant unless the route includes an explicit prerequisite-owned
    migration disposition.

    Args:
        routes: A sequence of route dicts, each with at least ``id``,
            ``disposition``, and ``route_family`` keys.

    Returns:
        A list of zero or more diagnostics.
    """
    diagnostics: list[C1PreflightDiagnostic] = []

    for route in routes:
        route_id = route.get("id", "<unknown>")
        disposition = route.get("disposition", "")
        route_family = route.get("route_family", "")

        if not disposition or disposition not in _VALID_DISPOSITIONS:
            spec = C1_DIAGNOSTIC_SPECS_BY_CODE[
                C1RealityDiagnosticCode.ROUTE_MIGRATION_DISPOSITION_MISSING.value
            ]
            diagnostics.append(
                C1PreflightDiagnostic(
                    code=C1RealityDiagnosticCode.ROUTE_MIGRATION_DISPOSITION_MISSING,
                    severity=C1DiagnosticSeverity.ERROR,
                    message=spec.message_template.format(route_id=route_id),
                    evidence_ref=f"c1.route.{route_id}.disposition",
                    details={
                        "route_id": route_id,
                        "disposition": disposition,
                        "route_family": route_family,
                    },
                )
            )
            continue

        # Authority-increasing routes (execute, resume, chain, supervisor)
        # must not be warn-only without explicit migration disposition.
        is_authority_increasing = route_family in {
            "execute",
            "resume",
            "chain",
            "supervisor",
        }
        if (
            is_authority_increasing
            and disposition in _NON_CONFORMANT_DISPOSITIONS
        ):
            has_migration_disposition = bool(
                route.get("owner_or_reason", "").strip()
            )
            if not has_migration_disposition:
                spec = C1_DIAGNOSTIC_SPECS_BY_CODE[
                    C1RealityDiagnosticCode.ROUTE_MIGRATION_WARN_ONLY_NON_CONFORMANT.value
                ]
                diagnostics.append(
                    C1PreflightDiagnostic(
                        code=C1RealityDiagnosticCode.ROUTE_MIGRATION_WARN_ONLY_NON_CONFORMANT,
                        severity=C1DiagnosticSeverity.ERROR,
                        message=spec.message_template.format(route_id=route_id),
                        evidence_ref=f"c1.route.{route_id}.warn_only_non_conformant",
                        details={
                            "route_id": route_id,
                            "disposition": disposition,
                            "route_family": route_family,
                        },
                    )
                )

    return diagnostics


# ── Validator 3: Dual mutating ownership ──────────────────────────────────


# Known mutating owner domains per the locked ownership contract.
_MUTATING_OWNER_DOMAINS = frozenset(
    {"run_authority", "maintenance", "wbc"}
)


def validate_dual_mutating_ownership(
    surface_owners: tuple[Mapping[str, Any], ...],
) -> list[C1PreflightDiagnostic]:
    """Validate that no shared surface has multiple mutating owners.

    Args:
        surface_owners: A sequence of surface-owner dicts, each with at least
            ``surface_name`` and ``mutating_owners`` keys.

    Returns:
        A list of zero or more diagnostics.
    """
    diagnostics: list[C1PreflightDiagnostic] = []

    for entry in surface_owners:
        surface_name = entry.get("surface_name", "<unknown>")
        mutating_owners = entry.get("mutating_owners", [])

        if not isinstance(mutating_owners, (list, tuple)):
            mutating_owners = [mutating_owners]

        # Filter to known mutating owner domains.
        effective_owners = [
            o for o in mutating_owners if o in _MUTATING_OWNER_DOMAINS
        ]

        if len(effective_owners) > 1:
            spec = C1_DIAGNOSTIC_SPECS_BY_CODE[
                C1RealityDiagnosticCode.DUAL_MUTATING_OWNERSHIP.value
            ]
            diagnostics.append(
                C1PreflightDiagnostic(
                    code=C1RealityDiagnosticCode.DUAL_MUTATING_OWNERSHIP,
                    severity=C1DiagnosticSeverity.ERROR,
                    message=spec.message_template.format(
                        surface_name=surface_name,
                        owners=sorted(effective_owners),
                    ),
                    evidence_ref=f"c1.ownership.{surface_name}.dual_mutating",
                    details={
                        "surface_name": surface_name,
                        "mutating_owners": sorted(effective_owners),
                    },
                )
            )

    return diagnostics


# ── Validator 4: Fixture replay mutability ────────────────────────────────


def validate_fixture_replay_mutability(
    fixtures: tuple[Mapping[str, Any], ...],
) -> list[C1PreflightDiagnostic]:
    """Validate that fixture replay does not require mutation.

    Args:
        fixtures: A sequence of fixture dicts, each with at least ``ref``
            and ``requires_mutation`` keys.

    Returns:
        A list of zero or more diagnostics.
    """
    diagnostics: list[C1PreflightDiagnostic] = []

    for fixture in fixtures:
        fixture_ref = fixture.get("ref", "<unknown>")
        requires_mutation = fixture.get("requires_mutation", False)
        has_hidden_fallback = fixture.get("has_hidden_fallback", False)

        if requires_mutation or has_hidden_fallback:
            spec = C1_DIAGNOSTIC_SPECS_BY_CODE[
                C1RealityDiagnosticCode.FIXTURE_REPLAY_MUTABILITY.value
            ]
            diagnostics.append(
                C1PreflightDiagnostic(
                    code=C1RealityDiagnosticCode.FIXTURE_REPLAY_MUTABILITY,
                    severity=C1DiagnosticSeverity.ERROR,
                    message=spec.message_template.format(fixture_ref=fixture_ref),
                    evidence_ref=f"c1.fixture.{fixture_ref}.mutability",
                    details={
                        "fixture_ref": fixture_ref,
                        "requires_mutation": requires_mutation,
                        "has_hidden_fallback": has_hidden_fallback,
                    },
                )
            )

    return diagnostics


# ── Validator 5: Producer mapping completeness ────────────────────────────


def validate_producer_mapping_completeness(
    contracts: tuple[Mapping[str, Any], ...],
    producers: tuple[Mapping[str, Any], ...],
) -> list[C1PreflightDiagnostic]:
    """Validate that every boundary contract maps to a real producer.

    Args:
        contracts: A sequence of contract dicts with at least ``contract_id``.
        producers: A sequence of producer dicts with at least ``contract_id``
            and ``producer_path``.

    Returns:
        A list of zero or more diagnostics.
    """
    diagnostics: list[C1PreflightDiagnostic] = []

    mapped_contract_ids = {
        p.get("contract_id", "") for p in producers if p.get("contract_id")
    }

    for contract in contracts:
        contract_id = contract.get("contract_id", "<unknown>")
        if contract_id not in mapped_contract_ids:
            spec = C1_DIAGNOSTIC_SPECS_BY_CODE[
                C1RealityDiagnosticCode.PRODUCER_MAPPING_INCOMPLETE.value
            ]
            diagnostics.append(
                C1PreflightDiagnostic(
                    code=C1RealityDiagnosticCode.PRODUCER_MAPPING_INCOMPLETE,
                    severity=C1DiagnosticSeverity.ERROR,
                    message=spec.message_template.format(contract_id=contract_id),
                    evidence_ref=f"c1.producer.{contract_id}.unmapped",
                    details={
                        "contract_id": contract_id,
                    },
                )
            )

    return diagnostics


# ── Validator 6: Migration coverage ───────────────────────────────────────


# Valid migration milestones (C2 through C6).
_VALID_MILESTONES = frozenset({"C2", "C3", "C4", "C5", "C6"})


def validate_migration_coverage(
    supported_producers: tuple[Mapping[str, Any], ...],
) -> list[C1PreflightDiagnostic]:
    """Validate that every supported producer has a migration milestone.

    Args:
        supported_producers: A sequence of producer dicts, each with at least
            ``producer_ref`` and ``migration_milestone`` keys.

    Returns:
        A list of zero or more diagnostics.
    """
    diagnostics: list[C1PreflightDiagnostic] = []

    for producer in supported_producers:
        producer_ref = producer.get("producer_ref", "<unknown>")
        milestone = producer.get("migration_milestone", "")

        if not producer_ref or producer_ref == "<unknown>":
            spec = C1_DIAGNOSTIC_SPECS_BY_CODE[
                C1RealityDiagnosticCode.MIGRATION_COVERAGE_GAP.value
            ]
            diagnostics.append(
                C1PreflightDiagnostic(
                    code=C1RealityDiagnosticCode.MIGRATION_COVERAGE_GAP,
                    severity=C1DiagnosticSeverity.ERROR,
                    message=spec.message_template.format(
                        producer_ref=producer_ref,
                    ),
                    evidence_ref="c1.migration.coverage_gap",
                    details={
                        "producer_ref": producer_ref,
                    },
                )
            )
            continue

        if not milestone or milestone not in _VALID_MILESTONES:
            spec = C1_DIAGNOSTIC_SPECS_BY_CODE[
                C1RealityDiagnosticCode.MIGRATION_MILESTONE_MISSING.value
            ]
            diagnostics.append(
                C1PreflightDiagnostic(
                    code=C1RealityDiagnosticCode.MIGRATION_MILESTONE_MISSING,
                    severity=C1DiagnosticSeverity.ERROR,
                    message=spec.message_template.format(
                        producer_ref=producer_ref,
                    ),
                    evidence_ref=f"c1.migration.{producer_ref}.milestone_missing",
                    details={
                        "producer_ref": producer_ref,
                        "migration_milestone": milestone,
                    },
                )
            )

    return diagnostics


# ── Validator 7: Hash-without-retained-payload ────────────────────────────


def validate_hash_without_retained_payload(
    payload_refs: tuple[Mapping[str, Any], ...],
) -> list[C1PreflightDiagnostic]:
    """Validate that no design point relies on hashes without durable payload retention.

    Args:
        payload_refs: A sequence of payload-ref dicts, each with at least
            ``hash_ref`` and ``has_retained_payload`` keys.

    Returns:
        A list of zero or more diagnostics.
    """
    diagnostics: list[C1PreflightDiagnostic] = []

    for ref in payload_refs:
        hash_ref = ref.get("hash_ref", "<unknown>")
        has_retained_payload = ref.get("has_retained_payload", True)

        if not has_retained_payload:
            spec = C1_DIAGNOSTIC_SPECS_BY_CODE[
                C1RealityDiagnosticCode.HASH_WITHOUT_RETAINED_PAYLOAD.value
            ]
            diagnostics.append(
                C1PreflightDiagnostic(
                    code=C1RealityDiagnosticCode.HASH_WITHOUT_RETAINED_PAYLOAD,
                    severity=C1DiagnosticSeverity.ERROR,
                    message=spec.message_template.format(hash_ref=hash_ref),
                    evidence_ref=f"c1.payload.{hash_ref}.hash_without_retention",
                    details={
                        "hash_ref": hash_ref,
                        "has_retained_payload": has_retained_payload,
                    },
                )
            )

    return diagnostics


# ── Composite preflight runner ────────────────────────────────────────────


def run_c1_preflight(
    *,
    manifest_hash: str | None = None,
    base_sha: str | None = None,
    routes: tuple[Mapping[str, Any], ...] = (),
    surface_owners: tuple[Mapping[str, Any], ...] = (),
    fixtures: tuple[Mapping[str, Any], ...] = (),
    contracts: tuple[Mapping[str, Any], ...] = (),
    producers: tuple[Mapping[str, Any], ...] = (),
    supported_producers: tuple[Mapping[str, Any], ...] = (),
    payload_refs: tuple[Mapping[str, Any], ...] = (),
) -> C1PreflightResult:
    """Run all C1 preflight validators and return an aggregate result.

    This is the primary entry point for C1 gating. Every validator runs
    even if earlier validators produce errors; the aggregate result
    includes all diagnostics.

    The result ``passed`` is True only when zero error-severity diagnostics
    are emitted.
    """
    all_diagnostics: list[C1PreflightDiagnostic] = []
    validator_count = 7

    all_diagnostics.extend(
        validate_run_authority_manifest(
            manifest_hash=manifest_hash,
            base_sha=base_sha,
        )
    )

    all_diagnostics.extend(
        validate_route_migration_dispositions(routes=routes)
    )

    all_diagnostics.extend(
        validate_dual_mutating_ownership(surface_owners=surface_owners)
    )

    all_diagnostics.extend(
        validate_fixture_replay_mutability(fixtures=fixtures)
    )

    all_diagnostics.extend(
        validate_producer_mapping_completeness(
            contracts=contracts,
            producers=producers,
        )
    )

    all_diagnostics.extend(
        validate_migration_coverage(
            supported_producers=supported_producers,
        )
    )

    all_diagnostics.extend(
        validate_hash_without_retained_payload(payload_refs=payload_refs)
    )

    error_count = sum(1 for d in all_diagnostics if d.is_error)
    warning_count = sum(1 for d in all_diagnostics if d.is_warning)

    return C1PreflightResult(
        diagnostics=tuple(all_diagnostics),
        validator_count=validator_count,
        total_diagnostics=len(all_diagnostics),
        error_count=error_count,
        warning_count=warning_count,
    )


# ── Public surface ────────────────────────────────────────────────────────

__all__ = [
    "C1RealityDiagnosticCode",
    "C1DiagnosticSeverity",
    "C1DiagnosticSpec",
    "C1PreflightDiagnostic",
    "C1PreflightResult",
    "C1_DIAGNOSTIC_SPECS",
    "C1_DIAGNOSTIC_SPECS_BY_CODE",
    "C1_PINNED_RUN_AUTHORITY_MANIFEST_HASH",
    "C1_PINNED_BASE_SHA",
    "run_c1_preflight",
    "validate_run_authority_manifest",
    "validate_route_migration_dispositions",
    "validate_dual_mutating_ownership",
    "validate_fixture_replay_mutability",
    "validate_producer_mapping_completeness",
    "validate_migration_coverage",
    "validate_hash_without_retained_payload",
]
