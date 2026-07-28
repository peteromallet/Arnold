"""M10 fault-matrix validation.

Validates the F01-F17 fault-matrix artifact: scenario identity, injection
edge, expected assertion, provider/query behavior, custody precondition,
replay expectation, and inventory-row references.

After Step 18A reconciliation, the matrix is no longer provisional: every
supported mutating/provider inventory row must have applicable fault and
replay coverage, every referenced row must exist in the inventory, and no
deferred row may appear in a scenario's coverage set.

All scenarios are action-off in M10.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


# ── Known valid field values ────────────────────────────────────────────────

VALID_INJECTION_EDGES: frozenset[str] = frozenset({
    "prerecord",
    "mark_fulfilled",
    "dispatch",
    "query",
    "admit",
    "acquire",
    "fold",
    "gate",
})

VALID_PROVIDER_BEHAVIORS: frozenset[str] = frozenset({
    "storage_full",
    "applied",
    "applied_then_kill",
    "not_called",
})

VALID_QUERY_BEHAVIORS: frozenset[str] = frozenset({
    "not_applied",
    "applied",
    "query_failure",
})

VALID_CUSTODY_PRECONDITIONS: frozenset[str] = frozenset({
    "lease_active",
    "lease_expired",
    "stale_epoch",
    "n/a",
})

VALID_REPLAY_EXPECTATIONS: frozenset[str] = frozenset({
    "indeterminate",
    "fulfilled",
    "conflict_quarantined",
    "terminal_state_error",
    "ttl_clamped",
    "suppressed",
    "action_off",
    "fenced",
    "first_terminal_preserved",
    "rejected",
})

REQUIRED_SCENARIO_FIELDS: tuple[str, ...] = (
    "id",
    "label",
    "injection_edge",
    "expected_assertion",
    "provider_behavior",
    "query_behavior",
    "custody_precondition",
    "replay_expectation",
    "inventory_row_refs",
    "action_off",
)


@dataclass
class ScenarioValidationError:
    """A single validation error for a fault-matrix scenario."""

    scenario_id: str
    field: str
    message: str


@dataclass
class FaultMatrixReport:
    """Aggregated validation report for the fault matrix."""

    scenarios_validated: int = 0
    errors: list[ScenarioValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0 and self.scenarios_validated > 0

    @property
    def error_count(self) -> int:
        return len(self.errors)


def _load_matrix(path: Path | str) -> dict[str, Any]:
    """Load and parse the fault-matrix JSON artifact."""
    with open(str(path), "r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_scenario(
    scenario: Mapping[str, Any],
    *,
    scenario_index: int = 0,
) -> list[ScenarioValidationError]:
    """Validate a single fault-matrix scenario.

    Returns a list of :class:`ScenarioValidationError` objects (empty when valid).
    """
    errors: list[ScenarioValidationError] = []
    scenario_id = str(scenario.get("id", f"scenario-{scenario_index}"))

    # Required fields
    for field in REQUIRED_SCENARIO_FIELDS:
        if field not in scenario:
            errors.append(
                ScenarioValidationError(
                    scenario_id=scenario_id,
                    field=field,
                    message=f"Missing required field '{field}'.",
                )
            )

    if errors:
        return errors

    # Identity
    sid = str(scenario["id"])
    if not sid.strip():
        errors.append(
            ScenarioValidationError(
                scenario_id=scenario_id,
                field="id",
                message="Scenario id must be a non-empty string.",
            )
        )
    if not sid.startswith("F") or not sid[1:].isdigit():
        errors.append(
            ScenarioValidationError(
                scenario_id=scenario_id,
                field="id",
                message=f"Scenario id '{sid}' must match pattern Fnn.",
            )
        )

    # Label
    label = str(scenario.get("label", ""))
    if not label.strip():
        errors.append(
            ScenarioValidationError(
                scenario_id=scenario_id,
                field="label",
                message="Label must be a non-empty string.",
            )
        )

    # Injection edge
    injection_edge = str(scenario.get("injection_edge", ""))
    if injection_edge not in VALID_INJECTION_EDGES:
        errors.append(
            ScenarioValidationError(
                scenario_id=scenario_id,
                field="injection_edge",
                message=(
                    f"Injection edge '{injection_edge}' is not in "
                    f"known set: {sorted(VALID_INJECTION_EDGES)}."
                ),
            )
        )

    # Expected assertion
    expected_assertion = str(scenario.get("expected_assertion", ""))
    if not expected_assertion.strip():
        errors.append(
            ScenarioValidationError(
                scenario_id=scenario_id,
                field="expected_assertion",
                message="Expected assertion must be a non-empty string.",
            )
        )

    # Provider behavior
    provider_behavior = str(scenario.get("provider_behavior", ""))
    if provider_behavior not in VALID_PROVIDER_BEHAVIORS:
        errors.append(
            ScenarioValidationError(
                scenario_id=scenario_id,
                field="provider_behavior",
                message=(
                    f"Provider behavior '{provider_behavior}' is not in "
                    f"known set: {sorted(VALID_PROVIDER_BEHAVIORS)}."
                ),
            )
        )

    # Query behavior
    query_behavior = str(scenario.get("query_behavior", ""))
    if query_behavior not in VALID_QUERY_BEHAVIORS:
        errors.append(
            ScenarioValidationError(
                scenario_id=scenario_id,
                field="query_behavior",
                message=(
                    f"Query behavior '{query_behavior}' is not in "
                    f"known set: {sorted(VALID_QUERY_BEHAVIORS)}."
                ),
            )
        )

    # Custody precondition
    custody_precondition = str(scenario.get("custody_precondition", ""))
    if custody_precondition not in VALID_CUSTODY_PRECONDITIONS:
        errors.append(
            ScenarioValidationError(
                scenario_id=scenario_id,
                field="custody_precondition",
                message=(
                    f"Custody precondition '{custody_precondition}' is not in "
                    f"known set: {sorted(VALID_CUSTODY_PRECONDITIONS)}."
                ),
            )
        )

    # Replay expectation
    replay_expectation = str(scenario.get("replay_expectation", ""))
    if replay_expectation not in VALID_REPLAY_EXPECTATIONS:
        errors.append(
            ScenarioValidationError(
                scenario_id=scenario_id,
                field="replay_expectation",
                message=(
                    f"Replay expectation '{replay_expectation}' is not in "
                    f"known set: {sorted(VALID_REPLAY_EXPECTATIONS)}."
                ),
            )
        )

    # Inventory row refs
    inventory_row_refs = scenario.get("inventory_row_refs")
    if not isinstance(inventory_row_refs, list):
        errors.append(
            ScenarioValidationError(
                scenario_id=scenario_id,
                field="inventory_row_refs",
                message="Inventory row refs must be a list.",
            )
        )

    # Action-off
    if not isinstance(scenario.get("action_off"), bool):
        errors.append(
            ScenarioValidationError(
                scenario_id=scenario_id,
                field="action_off",
                message="Action-off must be a boolean.",
            )
        )

    # In M10, all scenarios must be action-off
    if scenario.get("action_off") is False:
        errors.append(
            ScenarioValidationError(
                scenario_id=scenario_id,
                field="action_off",
                message="All M10 scenarios must be action-off (action_off=true).",
            )
        )

    return errors


def validate_fault_matrix(
    path: Path | str,
) -> FaultMatrixReport:
    """Validate the fault-matrix JSON artifact at *path*.

    Returns a :class:`FaultMatrixReport` with validation results.
    """
    report = FaultMatrixReport()

    try:
        data = _load_matrix(path)
    except (OSError, json.JSONDecodeError) as exc:
        report.errors.append(
            ScenarioValidationError(
                scenario_id="<matrix>",
                field="<file>",
                message=f"Failed to load fault matrix: {exc}",
            )
        )
        return report

    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list):
        report.errors.append(
            ScenarioValidationError(
                scenario_id="<matrix>",
                field="scenarios",
                message="Fault matrix must contain a 'scenarios' list.",
            )
        )
        return report

    if not scenarios:
        report.errors.append(
            ScenarioValidationError(
                scenario_id="<matrix>",
                field="scenarios",
                message="Fault matrix scenarios list is empty.",
            )
        )
        return report

    # Validate schema version
    schema_version = data.get("schema_version")
    if not isinstance(schema_version, int) or schema_version < 1:
        report.errors.append(
            ScenarioValidationError(
                scenario_id="<matrix>",
                field="schema_version",
                message="Schema version must be a positive integer.",
            )
        )

    # Validate each scenario
    for idx, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            report.errors.append(
                ScenarioValidationError(
                    scenario_id=f"scenario-{idx}",
                    field="<entry>",
                    message=f"Scenario at index {idx} is not a dict.",
                )
            )
            continue
        errors = validate_scenario(scenario, scenario_index=idx)
        report.errors.extend(errors)

    report.scenarios_validated = len(scenarios)
    return report


def load_and_validate_fault_matrix(
    path: Path | str | None = None,
) -> FaultMatrixReport:
    """Load and validate the default fault-matrix artifact.

    When *path* is None, uses the default path relative to the project root.
    """
    if path is None:
        # Default path relative to this module's location
        # arnold/workflow/effect_fault_matrix.py -> project root is 3 levels up
        default = Path(__file__).resolve().parent.parent.parent / "evidence" / "m10-f01-f17-fault-matrix.json"
        path = str(default)
    return validate_fault_matrix(path)


# ── Step 18A: inventory-row coverage join ─────────────────────────────────


def _load_json(path: Path | str) -> Any:
    """Load and parse a JSON artifact (used for inventory/supported files)."""
    with open(str(path), "r", encoding="utf-8") as fh:
        return json.load(fh)


def _collect_inventory_identities(inventory_rows: Iterable[Mapping[str, Any]]) -> set[str]:
    """Collect the set of valid inventory row identities.

    Each row may carry one or more of the identity fields ``identity``,
    ``boundary_id`` (composed as ``bc:<id>``), or ``step_id`` (composed as
    ``me:<id>``).  All discovered identities are returned as a set so that a
    scenario reference may target either form.
    """
    identities: set[str] = set()
    for row in inventory_rows:
        if not isinstance(row, Mapping):
            continue
        ident = row.get("identity")
        if isinstance(ident, str) and ident:
            identities.add(ident)
        bc = row.get("boundary_id")
        if isinstance(bc, str) and bc:
            identities.add(f"bc:{bc}")
        sid = row.get("step_id")
        if isinstance(sid, str) and sid:
            identities.add(f"me:{sid}")
    return identities


def validate_inventory_coverage(
    matrix_path: Path | str,
    inventory_path: Path | str,
    supported_boundaries_path: Path | str,
) -> FaultMatrixReport:
    """Step 18A — reconcile final inventory rows with F01-F17 scenarios.

    Joins the fault-matrix scenario ``inventory_row_refs`` against the
    boundary inventory and the M10 supported-boundaries artifact.  A valid
    join requires:

    1. Every referenced row exists in the inventory (no orphans).
    2. Every supported mutating/provider boundary contract is referenced by
       at least one scenario (no missing coverage).
    3. No deferred row appears in any scenario's coverage set (deferred rows
       are action-off and must not be claimed as fault evidence).
    4. No reference resolves to a non-supported inventory row (unsupported
       rows are not fault evidence for M10 supported coverage).

    Returns a :class:`FaultMatrixReport` with any join errors.
    """
    report = FaultMatrixReport()

    try:
        matrix_data = _load_matrix(matrix_path)
    except (OSError, json.JSONDecodeError) as exc:
        report.errors.append(
            ScenarioValidationError(
                scenario_id="<matrix>",
                field="<file>",
                message=f"Failed to load fault matrix: {exc}",
            )
        )
        return report

    try:
        inventory_data = _load_json(inventory_path)
    except (OSError, json.JSONDecodeError) as exc:
        report.errors.append(
            ScenarioValidationError(
                scenario_id="<matrix>",
                field="<inventory>",
                message=f"Failed to load boundary inventory: {exc}",
            )
        )
        return report

    try:
        supported_data = _load_json(supported_boundaries_path)
    except (OSError, json.JSONDecodeError) as exc:
        report.errors.append(
            ScenarioValidationError(
                scenario_id="<matrix>",
                field="<supported>",
                message=f"Failed to load supported-boundaries artifact: {exc}",
            )
        )
        return report

    inventory_rows = inventory_data.get("rows", []) if isinstance(inventory_data, Mapping) else []
    inventory_identities = _collect_inventory_identities(inventory_rows)

    supported_rows = supported_data.get("supported", []) if isinstance(supported_data, Mapping) else []
    deferred_rows = supported_data.get("deferred", []) if isinstance(supported_data, Mapping) else []

    supported_identities = {r.get("identity") for r in supported_rows if isinstance(r, Mapping)}
    deferred_identities = {r.get("identity") for r in deferred_rows if isinstance(r, Mapping)}

    # The supported mutating/provider boundary contracts (row_kind ==
    # "boundary_contract") are the rows that *must* have fault coverage.
    required_coverage = {
        r.get("identity")
        for r in supported_rows
        if isinstance(r, Mapping) and r.get("row_kind") == "boundary_contract"
    }

    scenarios = matrix_data.get("scenarios", []) if isinstance(matrix_data.get("scenarios"), list) else []

    # Collect every ref mentioned by any scenario.
    referenced: dict[str, list[str]] = {}
    for scenario in scenarios:
        if not isinstance(scenario, Mapping):
            continue
        sid = str(scenario.get("id", "<unknown>"))
        refs = scenario.get("inventory_row_refs", [])
        if not isinstance(refs, list):
            continue
        for ref in refs:
            ref_str = str(ref)
            referenced.setdefault(ref_str, []).append(sid)

    # (1) Orphan refs — referenced but absent from the inventory.
    referenced_identities = set(referenced.keys())
    orphan_refs = referenced_identities - inventory_identities
    for ref in sorted(orphan_refs):
        report.errors.append(
            ScenarioValidationError(
                scenario_id="<matrix>",
                field="inventory_row_refs",
                message=(
                    f"Scenario ref '{ref}' is not present in the boundary "
                    f"inventory (orphan reference). Referenced by "
                    f"{referenced[ref]}."
                ),
            )
        )

    # (2) Missing coverage — required boundary contract with no scenario.
    covered_identities = referenced_identities & inventory_identities
    missing_coverage = required_coverage - covered_identities
    for ident in sorted(missing_coverage):
        report.errors.append(
            ScenarioValidationError(
                scenario_id="<matrix>",
                field="inventory_row_refs",
                message=(
                    f"Supported boundary contract '{ident}' has no fault-matrix "
                    f"coverage (no scenario references it)."
                ),
            )
        )

    # (3) Deferred rows referenced — action-off rows must not be claimed.
    referenced_deferred = referenced_identities & deferred_identities
    for ref in sorted(referenced_deferred):
        report.errors.append(
            ScenarioValidationError(
                scenario_id="<matrix>",
                field="inventory_row_refs",
                message=(
                    f"Scenario ref '{ref}' is a deferred (action-off) row and "
                    f"must not appear in fault-matrix coverage. Referenced by "
                    f"{referenced[ref]}."
                ),
            )
        )

    # (4) Unsupported rows referenced — must not be claimed as coverage.
    referenced_unsupported = covered_identities - supported_identities
    for ref in sorted(referenced_unsupported):
        report.errors.append(
            ScenarioValidationError(
                scenario_id="<matrix>",
                field="inventory_row_refs",
                message=(
                    f"Scenario ref '{ref}' resolves to a non-supported inventory "
                    f"row and must not appear in fault-matrix coverage. "
                    f"Referenced by {referenced[ref]}."
                ),
            )
        )

    report.scenarios_validated = len(scenarios)
    return report


def load_and_validate_inventory_coverage(
    matrix_path: Path | str | None = None,
    inventory_path: Path | str | None = None,
    supported_boundaries_path: Path | str | None = None,
) -> FaultMatrixReport:
    """Step 18A convenience wrapper using the default evidence paths.

    Defaults resolve relative to this module's location (project root is
    three levels up).
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    if matrix_path is None:
        matrix_path = project_root / "evidence" / "m10-f01-f17-fault-matrix.json"
    if inventory_path is None:
        inventory_path = project_root / "evidence" / "wbc-boundary-inventory.json"
    if supported_boundaries_path is None:
        supported_boundaries_path = project_root / "evidence" / "m10-supported-boundaries.json"
    return validate_inventory_coverage(matrix_path, inventory_path, supported_boundaries_path)


__all__ = [
    "FaultMatrixReport",
    "ScenarioValidationError",
    "VALID_CUSTODY_PRECONDITIONS",
    "VALID_INJECTION_EDGES",
    "VALID_PROVIDER_BEHAVIORS",
    "VALID_QUERY_BEHAVIORS",
    "VALID_REPLAY_EXPECTATIONS",
    "load_and_validate_fault_matrix",
    "load_and_validate_inventory_coverage",
    "validate_fault_matrix",
    "validate_inventory_coverage",
    "validate_scenario",
]
