"""Read-only fixture replay and compatibility evaluation for C1 Contract Reality.

This module is intentionally observe-only. It reads checked-in captured fixture
bundles from ``tests/fixtures/workflow_boundary_contracts/`` together with the
contract-to-producer matrix and returns typed ``compatible``, ``incompatible``,
``unknown``, and ``non_conformant`` results with stable diagnostics.

It never normalizes legacy fixtures, rewrites current fixtures, or mutates
any source/run directory. Every compatibility verdict is accompanied by
diagnostic evidence references that downstream semantic-health and matrix
tests can pin against.

Design constraints (C1 observe-only):
* NEVER writes to any fixture file or source directory.
* NEVER normalizes legacy fixture shapes to match current schemas.
* NEVER rewrites current fixtures to make them "more compatible."
* Always uses deterministic ordering (sorted keys, stable iteration).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from arnold.workflow.boundary_templates import (
    DEFAULT_WBC_INVENTORY_PATH,
    WbcInventoryInvariant,
    assess_inventory_rows,
    load_wbc_boundary_inventory,
    select_inventory_rows,
)


# ── Compatibility status vocabulary ──────────────────────────────────────


class CompatibilityStatus(StrEnum):
    """Typed compatibility status for boundary fixture evaluation.

    Each status is a stable semantic label that downstream consumers
    (semantic-health checks, matrix tests, finalize gates) can rely on.
    """

    COMPATIBLE = "compatible"
    """Fixture structure and content align with declared contract expectations."""

    INCOMPATIBLE = "incompatible"
    """Fixture deviates from contract expectations in a meaningful way that
    requires attention but is not a documented non-conformance."""

    UNKNOWN = "unknown"
    """Cannot determine compatibility — fixture has typed unknown markers
    for critical categories (boundary receipts, phase result, state) or
    the fixture is a legacy bundle without structured boundary data."""

    NON_CONFORMANT = "non_conformant"
    """Fixture corresponds to a contract that is documented as visibly
    non-conformant in the contract-to-producer matrix (declared_only,
    unknown producer category, or explicit visible_non_conformant entries)."""


# ── Compatibility diagnostic codes ───────────────────────────────────────


class CompatibilityDiagnosticCode(StrEnum):
    """Stable diagnostic codes for boundary compatibility evaluation."""

    # Structural diagnostics
    MISSING_BOUNDARY_RECEIPTS = "CBC001_MISSING_BOUNDARY_RECEIPTS"
    MISSING_MANIFEST = "CBC002_MISSING_MANIFEST"
    MISSING_PHASE_RESULT = "CBC003_MISSING_PHASE_RESULT"
    MISSING_STATE = "CBC004_MISSING_STATE"

    # Content diagnostics
    BOUNDARY_ID_MISMATCH = "CBC005_BOUNDARY_ID_MISMATCH"
    RECEIPT_WORKFLOW_ID_MISSING = "CBC006_RECEIPT_WORKFLOW_ID_MISSING"
    RECEIPT_INVOCATION_ID_MISSING = "CBC007_RECEIPT_INVOCATION_ID_MISSING"
    RECEIPT_OUTCOME_MISSING = "CBC008_RECEIPT_OUTCOME_MISSING"
    MANIFEST_CAPABILITY_EFFECTS_MISSING = "CBC009_MANIFEST_CAPABILITY_EFFECTS_MISSING"
    PHASE_RESULT_EXIT_KIND_MISSING = "CBC010_PHASE_RESULT_EXIT_KIND_MISSING"

    # Fixture classification
    LEGACY_FIXTURE_UNKNOWN = "CBC011_LEGACY_FIXTURE_UNKNOWN"
    CRITICAL_CATEGORIES_UNKNOWN = "CBC012_CRITICAL_CATEGORIES_UNKNOWN"

    # Contract alignment
    DECLARED_ONLY_NO_PRODUCER = "CBC013_DECLARED_ONLY_NO_PRODUCER"
    UNKNOWN_PRODUCER_CATEGORY = "CBC014_UNKNOWN_PRODUCER_CATEGORY"
    VISIBLE_NON_CONFORMANCE = "CBC015_VISIBLE_NON_CONFORMANCE"
    INCOMPLETE_INVENTORY_ROW = "CBC016_INCOMPLETE_INVENTORY_ROW"
    START_BEFORE_DISPATCH_UNVERIFIED = "CBC017_START_BEFORE_DISPATCH_UNVERIFIED"
    EXACTLY_ONE_TERMINAL_UNVERIFIED = "CBC018_EXACTLY_ONE_TERMINAL_UNVERIFIED"
    GRANT_LEASE_GATE_UNVERIFIED = "CBC019_GRANT_LEASE_GATE_UNVERIFIED"
    EXACT_VERSION_LOOKUP_UNVERIFIED = "CBC020_EXACT_VERSION_LOOKUP_UNVERIFIED"
    CAUSAL_EVIDENCE_UNVERIFIED = "CBC021_CAUSAL_EVIDENCE_UNVERIFIED"
    POST_TRANSITION_REREAD_UNVERIFIED = "CBC022_POST_TRANSITION_REREAD_UNVERIFIED"


# ── Critical categories for compatibility evaluation ─────────────────────

# Categories whose absence via typed unknown markers indicates we cannot
# evaluate compatibility (result should be UNKNOWN rather than INCOMPATIBLE).
_CRITICAL_UNKNOWN_CATEGORIES: frozenset[str] = frozenset(
    {"boundary_receipts", "phase_result", "state", "manifest", "semantic_health"}
)

# Categories that distinguish a legacy fixture from a current one.
# Legacy fixtures (bundles 000-003) only have raw event data and lack
# structured boundary receipts, manifests, and phase results.
_LEGACY_ONLY_ARTIFACT_KEYS: frozenset[str] = frozenset(
    {"events", "events.jsonl"}
)

# Expected artifact keys in a well-formed current fixture bundle.
_EXPECTED_CURRENT_ARTIFACT_KEYS: frozenset[str] = frozenset(
    {"boundary_receipts", "manifest", "phase_result", "semantic_health", "state"}
)


# ── CompatibilityResult ──────────────────────────────────────────────────


@dataclass(frozen=True)
class CompatibilityResult:
    """Typed compatibility verdict for one fixture bundle.

    Each result carries a stable status, diagnostic codes, and structured
    evidence references that pin the evaluation to specific fixture fields
    and matrix entries.
    """

    boundary_id: str
    """Boundary identifier extracted from the fixture (or 'unknown' if
    the fixture has no identifiable boundary)."""

    fixture_id: str
    """Fixture bundle filename stem (e.g. 'captured_bundle_025_prep_to_plan')."""

    status: CompatibilityStatus
    """The typed compatibility status for this fixture."""

    diagnostics: tuple[str, ...] = ()
    """Stable diagnostic codes (CompatibilityDiagnosticCode values) describing
    the evaluation reasoning."""

    contract_refs: tuple[str, ...] = ()
    """References into the contract-to-producer matrix (boundary_id keys)."""

    evidence_refs: tuple[str, ...] = ()
    """Path-like references into the fixture bundle that support the verdict
    (e.g. 'artifacts.boundary_receipts', 'unknown_markers[category=state]')."""

    details: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    """Additional structured detail (always primitive JSON-safe values)."""

    evaluator_version: str = "arnold.workflow.boundary_compatibility.v1"

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe payload with primitive values."""
        payload: dict[str, Any] = {
            "boundary_id": self.boundary_id,
            "fixture_id": self.fixture_id,
            "status": self.status.value,
            "evaluator_version": self.evaluator_version,
        }
        if self.diagnostics:
            payload["diagnostics"] = list(self.diagnostics)
        if self.contract_refs:
            payload["contract_refs"] = list(self.contract_refs)
        if self.evidence_refs:
            payload["evidence_refs"] = list(self.evidence_refs)
        if self.details:
            payload["details"] = dict(self.details)
        return payload


# ── CompatibilityEvaluator ───────────────────────────────────────────────


class CompatibilityEvaluator:
    """Read-only evaluator that replays fixture bundles against declared contracts.

    The evaluator reads captured fixture bundles from the fixtures directory
    and the contract-to-producer matrix, then produces typed compatibility
    results without normalizing, rewriting, or mutating any file.

    Usage::

        evaluator = CompatibilityEvaluator()
        results = evaluator.evaluate_all()
        for r in results:
            print(r.status, r.boundary_id)
    """

    def __init__(
        self,
        fixture_dir: str | Path | None = None,
        contract_matrix_path: str | Path | None = None,
        inventory_path: str | Path | None = None,
    ) -> None:
        """Create a read-only evaluator.

        Args:
            fixture_dir: Path to the directory containing captured bundle
                JSON files. Defaults to ``tests/fixtures/workflow_boundary_contracts/``.
            contract_matrix_path: Path to ``contract_to_producer_matrix.json``.
                Defaults to the checked-in matrix under ``arnold_pipelines/``.
        """
        if fixture_dir is None:
            fixture_dir = Path("tests/fixtures/workflow_boundary_contracts")
        self._fixture_dir = Path(fixture_dir)

        if contract_matrix_path is None:
            contract_matrix_path = Path(
                "arnold_pipelines/megaplan/workflows/contract_to_producer_matrix.json"
            )
        self._contract_matrix_path = Path(contract_matrix_path)
        self._inventory_path = (
            Path(inventory_path)
            if inventory_path is not None
            else DEFAULT_WBC_INVENTORY_PATH
        )

        # Load the contract matrix once (read-only)
        self._contract_matrix: dict[str, Any] = {}
        self._contracts_by_boundary_id: dict[str, dict[str, Any]] = {}
        self._inventory: dict[str, Any] | None = None
        self._load_contract_matrix()
        self._load_inventory()

    # ── public API ────────────────────────────────────────────────────

    def evaluate_all(self) -> tuple[CompatibilityResult, ...]:
        """Evaluate all captured fixture bundles and return typed results.

        Results are returned in deterministic order (sorted by fixture filename).
        Legacy bundles (000-003) are included and evaluated as UNKNOWN.
        """
        fixture_paths = sorted(
            p for p in self._fixture_dir.glob("captured_bundle_*.json")
            if p.is_file()
        )
        results: list[CompatibilityResult] = []
        for path in fixture_paths:
            result = self.evaluate_fixture(path)
            results.append(result)
        return tuple(results)

    def evaluate_fixture(self, fixture_path: str | Path) -> CompatibilityResult:
        """Evaluate a single fixture bundle and return a typed result.

        This is the core read-only evaluation entry point. It reads the
        fixture JSON, classifies it, checks structural alignment, and
        cross-references the contract matrix — all without writing.

        Args:
            fixture_path: Path to a captured bundle JSON file.

        Returns:
            A frozen CompatibilityResult with typed status and stable diagnostics.
        """
        fixture_path = Path(fixture_path)
        fixture_id = fixture_path.stem

        # Read the fixture (read-only)
        bundle = self._read_fixture(fixture_path)
        if bundle is None:
            return CompatibilityResult(
                boundary_id="unknown",
                fixture_id=fixture_id,
                status=CompatibilityStatus.UNKNOWN,
                diagnostics=(CompatibilityDiagnosticCode.CRITICAL_CATEGORIES_UNKNOWN,),
                evidence_refs=(f"fixture_path:{fixture_path}",),
                details=MappingProxyType(
                    {"reason": "Fixture could not be read or parsed as JSON."}
                ),
            )

        unknown_markers: list[dict[str, Any]] = bundle.get("unknown_markers", [])
        artifacts: dict[str, Any] = bundle.get("artifacts", {})

        # ── Step 1: Classify fixture type ──────────────────────────────

        is_legacy = self._is_legacy_fixture(artifacts)
        if is_legacy:
            return self._build_unknown_result(
                fixture_id=fixture_id,
                diagnostic=CompatibilityDiagnosticCode.LEGACY_FIXTURE_UNKNOWN,
                evidence_refs=["artifacts:legacy_event_data_only"],
                reason="Legacy fixture contains only raw event data without "
                "structured boundary receipts, manifest, or phase result.",
            )

        # ── Step 2: Check critical unknown markers ─────────────────────

        critical_unknown = self._check_critical_unknown_markers(unknown_markers)
        if critical_unknown:
            return self._build_unknown_result(
                fixture_id=fixture_id,
                diagnostic=CompatibilityDiagnosticCode.CRITICAL_CATEGORIES_UNKNOWN,
                evidence_refs=[
                    f"unknown_markers[category={cat}]" for cat in critical_unknown
                ],
                reason=f"Critical categories marked as unknown: "
                f"{', '.join(sorted(critical_unknown))}.",
            )

        # ── Step 3: Extract boundary_id ────────────────────────────────

        boundary_id = self._extract_boundary_id(artifacts)
        if boundary_id is None:
            return CompatibilityResult(
                boundary_id="unknown",
                fixture_id=fixture_id,
                status=CompatibilityStatus.UNKNOWN,
                diagnostics=(
                    CompatibilityDiagnosticCode.CRITICAL_CATEGORIES_UNKNOWN,
                ),
                evidence_refs=("artifacts:no_boundary_receipts",),
                details=MappingProxyType(
                    {"reason": "No boundary_id extractable from fixture artifacts."}
                ),
            )

        # ── Step 4: Check structural compatibility ─────────────────────

        structural_issues = self._check_structural_compatibility(
            artifacts, boundary_id
        )

        # ── Step 5: Check contract matrix alignment ────────────────────

        contract = self._contracts_by_boundary_id.get(boundary_id)
        contract_issues, contract_status, contract_detail = self._check_contract_alignment(
            boundary_id, contract
        )

        # ── Step 6: Determine final status ─────────────────────────────

        # Contract-level non-conformance takes precedence
        if contract_status == CompatibilityStatus.NON_CONFORMANT:
            all_diags = tuple(structural_issues + contract_issues)
            return CompatibilityResult(
                boundary_id=boundary_id,
                fixture_id=fixture_id,
                status=CompatibilityStatus.NON_CONFORMANT,
                diagnostics=all_diags if all_diags else contract_issues,
                contract_refs=(f"contract_to_producer:{boundary_id}",),
                evidence_refs=tuple(
                    f"artifacts.{cat}" for cat in sorted(artifacts.keys())
                ),
                details=MappingProxyType(
                    {
                        "producer_category": (
                            contract_detail.get("producer_category", "unknown")
                        ),
                        "structural_issues": list(structural_issues),
                        "contract_issues": list(contract_issues),
                        **contract_detail,
                    }
                ),
            )

        # Contract-level unknown producer
        if contract_status == CompatibilityStatus.UNKNOWN:
            all_diags = tuple(structural_issues + contract_issues)
            return CompatibilityResult(
                boundary_id=boundary_id,
                fixture_id=fixture_id,
                status=CompatibilityStatus.UNKNOWN,
                diagnostics=all_diags if all_diags else contract_issues,
                contract_refs=(f"contract_to_producer:{boundary_id}",),
                evidence_refs=tuple(
                    f"artifacts.{cat}" for cat in sorted(artifacts.keys())
                ),
                details=MappingProxyType(
                    {
                        "producer_category": (
                            contract_detail.get("producer_category", "unknown")
                        ),
                        "structural_issues": list(structural_issues),
                        "contract_issues": list(contract_issues),
                        **contract_detail,
                    }
                ),
            )

        # Structural issues → INCOMPATIBLE
        if structural_issues:
            return CompatibilityResult(
                boundary_id=boundary_id,
                fixture_id=fixture_id,
                status=CompatibilityStatus.INCOMPATIBLE,
                diagnostics=tuple(structural_issues),
                contract_refs=(f"contract_to_producer:{boundary_id}",)
                if contract
                else (),
                evidence_refs=tuple(
                    f"artifacts.{cat}" for cat in sorted(artifacts.keys())
                ),
                details=MappingProxyType(
                    {
                        "structural_issues": list(structural_issues),
                    }
                ),
            )

        # ── All checks passed → COMPATIBLE ────────────────────────────

        return CompatibilityResult(
            boundary_id=boundary_id,
            fixture_id=fixture_id,
            status=CompatibilityStatus.COMPATIBLE,
            contract_refs=(f"contract_to_producer:{boundary_id}",)
            if contract
            else (),
            evidence_refs=tuple(
                f"artifacts.{cat}" for cat in sorted(artifacts.keys())
            ),
            details=MappingProxyType(
                {
                    "producer_category": (
                        contract_detail.get("producer_category", "unknown")
                    ),
                    **contract_detail,
                }
            ),
        )

    # ── internal helpers ──────────────────────────────────────────────

    def _load_contract_matrix(self) -> None:
        """Load the contract-to-producer matrix (read-only)."""
        try:
            with open(self._contract_matrix_path, "r") as f:
                self._contract_matrix = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._contract_matrix = {}

        contracts = self._contract_matrix.get("contracts", [])
        self._contracts_by_boundary_id = {
            c["boundary_id"]: c for c in contracts if "boundary_id" in c
        }

    def _load_inventory(self) -> None:
        """Load the generated inventory (read-only)."""
        self._inventory = load_wbc_boundary_inventory(self._inventory_path)

    @staticmethod
    def _read_fixture(path: Path) -> dict[str, Any] | None:
        """Read a fixture bundle JSON file. Returns None on failure."""
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def _is_legacy_fixture(artifacts: dict[str, Any]) -> bool:
        """Determine if a fixture is a legacy bundle (raw events only).

        Legacy bundles (000-003) have artifact keys that are exclusively
        raw event data (``events``, ``events.jsonl``) and lack structured
        boundary data (boundary_receipts, manifest, phase_result, etc.).
        """
        if not artifacts:
            return False
        artifact_keys = set(artifacts.keys())
        # If any current artifact key is present, it's not a legacy fixture
        if artifact_keys & _EXPECTED_CURRENT_ARTIFACT_KEYS:
            return False
        # If the only artifact keys are legacy-only keys, it IS a legacy fixture
        if artifact_keys and artifact_keys <= _LEGACY_ONLY_ARTIFACT_KEYS:
            return True
        return False

    @staticmethod
    def _check_critical_unknown_markers(
        unknown_markers: list[dict[str, Any]],
    ) -> frozenset[str]:
        """Return the set of critical categories marked as unknown.

        Critical categories are those whose absence makes structural
        compatibility evaluation impossible.
        """
        categories: set[str] = set()
        for marker in unknown_markers:
            cat = marker.get("category", "")
            if cat in _CRITICAL_UNKNOWN_CATEGORIES:
                categories.add(cat)
        return frozenset(categories)

    @staticmethod
    def _extract_boundary_id(artifacts: dict[str, Any]) -> str | None:
        """Extract the boundary_id from a fixture's boundary_receipts or manifest.

        Tries boundary_receipts first (most specific), then manifest.
        """
        boundary_receipts = artifacts.get("boundary_receipts")
        if isinstance(boundary_receipts, dict) and boundary_receipts:
            # Take the boundary_id from the first receipt
            for receipt_key, receipt in boundary_receipts.items():
                if isinstance(receipt, dict) and "boundary_id" in receipt:
                    return str(receipt["boundary_id"])

        manifest = artifacts.get("manifest")
        if isinstance(manifest, dict) and "boundary_id" in manifest:
            return str(manifest["boundary_id"])

        return None

    @staticmethod
    def _check_structural_compatibility(
        artifacts: dict[str, Any], expected_boundary_id: str
    ) -> tuple[str, ...]:
        """Check structural compatibility of a fixture against expected shapes.

        Returns a tuple of diagnostic codes for issues found (empty = compatible).
        """
        issues: list[str] = []

        # Check boundary_receipts
        boundary_receipts = artifacts.get("boundary_receipts")
        if not isinstance(boundary_receipts, dict) or not boundary_receipts:
            issues.append(CompatibilityDiagnosticCode.MISSING_BOUNDARY_RECEIPTS)
            return tuple(issues)  # Cannot check further without receipts

        # Validate first receipt
        for _receipt_key, receipt in boundary_receipts.items():
            if not isinstance(receipt, dict):
                issues.append(CompatibilityDiagnosticCode.MISSING_BOUNDARY_RECEIPTS)
                continue

            # Check boundary_id matches
            actual_bid = receipt.get("boundary_id", "")
            if actual_bid != expected_boundary_id:
                issues.append(CompatibilityDiagnosticCode.BOUNDARY_ID_MISMATCH)

            # Check required receipt fields
            if not receipt.get("workflow_id"):
                issues.append(
                    CompatibilityDiagnosticCode.RECEIPT_WORKFLOW_ID_MISSING
                )
            if not receipt.get("invocation_id"):
                issues.append(
                    CompatibilityDiagnosticCode.RECEIPT_INVOCATION_ID_MISSING
                )
            if not receipt.get("outcome"):
                issues.append(CompatibilityDiagnosticCode.RECEIPT_OUTCOME_MISSING)

            break  # Only validate the first receipt

        # Check manifest
        manifest = artifacts.get("manifest")
        if not isinstance(manifest, dict):
            issues.append(CompatibilityDiagnosticCode.MISSING_MANIFEST)
        else:
            if not manifest.get("capability_effects"):
                issues.append(
                    CompatibilityDiagnosticCode.MANIFEST_CAPABILITY_EFFECTS_MISSING
                )

        # Check phase_result
        phase_result = artifacts.get("phase_result")
        if not isinstance(phase_result, dict):
            issues.append(CompatibilityDiagnosticCode.MISSING_PHASE_RESULT)
        else:
            if "exit_kind" not in phase_result:
                issues.append(
                    CompatibilityDiagnosticCode.PHASE_RESULT_EXIT_KIND_MISSING
                )

        # Check state
        state = artifacts.get("state")
        if not isinstance(state, dict):
            issues.append(CompatibilityDiagnosticCode.MISSING_STATE)

        return tuple(issues)

    def _check_contract_alignment(
        self,
        boundary_id: str,
        contract: dict[str, Any] | None,
    ) -> tuple[tuple[str, ...], CompatibilityStatus | None, Mapping[str, Any]]:
        """Check alignment between a fixture and its contract matrix entry.

        Returns a tuple of (diagnostic_codes, contract_status_or_None).
        contract_status is only set when the contract dictates the overall
        compatibility status (NON_CONFORMANT or UNKNOWN due to producer
        category).
        """
        inventory_rows = select_inventory_rows(self._inventory, boundary_id=boundary_id)
        if inventory_rows:
            assessment = assess_inventory_rows(inventory_rows)
            authoritative = inventory_rows[0]
            detail: dict[str, Any] = {
                "inventory_ref": f"inventory:{boundary_id}",
                "inventory_row_kind": authoritative.get("row_kind"),
                "producer_category": assessment.producer_category or (
                    contract.get("producer_category", "unknown") if contract else "not_found"
                ),
                "inventory_reasons": list(assessment.reasons),
            }
            diags: list[str] = []
            status: CompatibilityStatus | None = None

            if assessment.producer_category == "declared_only":
                diags.append(CompatibilityDiagnosticCode.DECLARED_ONLY_NO_PRODUCER)
                status = CompatibilityStatus.NON_CONFORMANT
            elif assessment.producer_category == "unknown":
                diags.append(CompatibilityDiagnosticCode.UNKNOWN_PRODUCER_CATEGORY)
                status = CompatibilityStatus.UNKNOWN
            elif assessment.reasons:
                diags.append(CompatibilityDiagnosticCode.INCOMPLETE_INVENTORY_ROW)
                status = CompatibilityStatus.NON_CONFORMANT

            invariant_diags = self._diagnostics_for_inventory_invariants(assessment.missing_invariants)
            if invariant_diags:
                diags.extend(invariant_diags)
                status = CompatibilityStatus.NON_CONFORMANT

            visible_non_conformant = contract.get("visible_non_conformant", []) if contract else []
            if visible_non_conformant:
                diags.append(CompatibilityDiagnosticCode.VISIBLE_NON_CONFORMANCE)
                if status is None:
                    status = CompatibilityStatus.NON_CONFORMANT
            detail["visible_non_conformant"] = list(visible_non_conformant)
            return tuple(dict.fromkeys(diags)), status, MappingProxyType(detail)

        if contract is None:
            # Contract not in matrix — unknown alignment
            return (), CompatibilityStatus.UNKNOWN, MappingProxyType({"producer_category": "not_found"})

        diags: list[str] = []
        status: CompatibilityStatus | None = None

        producer_category = contract.get("producer_category", "")
        visible_non_conformant = contract.get("visible_non_conformant", [])

        # Check for declared_only (no producer path)
        if producer_category == "declared_only":
            diags.append(CompatibilityDiagnosticCode.DECLARED_ONLY_NO_PRODUCER)
            status = CompatibilityStatus.NON_CONFORMANT

        # Check for unknown producer category
        elif producer_category == "unknown":
            diags.append(CompatibilityDiagnosticCode.UNKNOWN_PRODUCER_CATEGORY)
            status = CompatibilityStatus.UNKNOWN

        # Check for visible non-conformance entries
        if visible_non_conformant:
            diags.append(CompatibilityDiagnosticCode.VISIBLE_NON_CONFORMANCE)
            # If the contract has visible non-conformance but isn't
            # already declared_only/unknown, it's still non_conformant
            if status is None:
                status = CompatibilityStatus.NON_CONFORMANT

        return (
            tuple(diags),
            status,
            MappingProxyType(
                {
                    "producer_category": producer_category or "not_found",
                    "visible_non_conformant": list(visible_non_conformant),
                }
            ),
        )

    @staticmethod
    def _diagnostics_for_inventory_invariants(
        missing_invariants: tuple[WbcInventoryInvariant, ...],
    ) -> tuple[str, ...]:
        mapping = {
            WbcInventoryInvariant.START_BEFORE_DISPATCH: CompatibilityDiagnosticCode.START_BEFORE_DISPATCH_UNVERIFIED,
            WbcInventoryInvariant.EXACTLY_ONE_TERMINAL: CompatibilityDiagnosticCode.EXACTLY_ONE_TERMINAL_UNVERIFIED,
            WbcInventoryInvariant.GRANT_LEASE_GATE: CompatibilityDiagnosticCode.GRANT_LEASE_GATE_UNVERIFIED,
            WbcInventoryInvariant.EXACT_VERSION_LOOKUP: CompatibilityDiagnosticCode.EXACT_VERSION_LOOKUP_UNVERIFIED,
            WbcInventoryInvariant.CAUSAL_EVIDENCE: CompatibilityDiagnosticCode.CAUSAL_EVIDENCE_UNVERIFIED,
            WbcInventoryInvariant.POST_TRANSITION_REREAD: CompatibilityDiagnosticCode.POST_TRANSITION_REREAD_UNVERIFIED,
        }
        return tuple(mapping[invariant] for invariant in missing_invariants)


    @staticmethod
    def _build_unknown_result(
        fixture_id: str,
        diagnostic: str,
        evidence_refs: list[str],
        reason: str,
    ) -> CompatibilityResult:
        """Build a standard UNKNOWN result for a fixture."""
        return CompatibilityResult(
            boundary_id="unknown",
            fixture_id=fixture_id,
            status=CompatibilityStatus.UNKNOWN,
            diagnostics=(diagnostic,),
            evidence_refs=tuple(evidence_refs),
            details=MappingProxyType({"reason": reason}),
        )


# ── Convenience function ─────────────────────────────────────────────────


def evaluate_boundary_compatibility(
    fixture_dir: str | Path | None = None,
    contract_matrix_path: str | Path | None = None,
    inventory_path: str | Path | None = None,
) -> tuple[CompatibilityResult, ...]:
    """Evaluate all captured fixture bundles for boundary compatibility.

    Convenience wrapper around ``CompatibilityEvaluator.evaluate_all()``.

    Returns a tuple of ``CompatibilityResult`` in deterministic filename order.
    """
    evaluator = CompatibilityEvaluator(
        fixture_dir=fixture_dir,
        contract_matrix_path=contract_matrix_path,
        inventory_path=inventory_path,
    )
    return evaluator.evaluate_all()


__all__ = [
    "CompatibilityDiagnosticCode",
    "CompatibilityEvaluator",
    "CompatibilityResult",
    "CompatibilityStatus",
    "evaluate_boundary_compatibility",
]
