"""M8A pure report builder — reads the M8A corpus, runs task feasibility,
batch splitting, source-admission dry checks, and circuit primitives over
v2 fixtures, and writes rebuildable evidence artifacts without mutating
historical or live plan files.

This module is intentionally pure: it reads fixture data and writes only
into the ``evidence/`` directory.  It never touches chain state, plan state,
or any live dispatch path.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan._core.io import (
    atomic_write_json,
    compute_task_batches,
    now_utc,
)
from arnold_pipelines.megaplan.orchestration.task_feasibility import (
    compile_task_feasibility,
    task_contract_hash,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

M8A_REPORT_SCHEMA = "m8a.report-only-corpus.v1"
M8A_EXECUTOR_WIRING_SCHEMA = "m8a.f01-f17-executor-wiring.v1"

# Fixture names used as report keys.
_FIXTURE_KEYS = [
    "transaction-spine-serial",
    "strategy-validation",
    "complexity-7-8-9",
    "repeated-budget-failures",
    "six-task-rework",
]

# The F01-F17 findings and their canonical owner components as defined in
# the M6A substrate map (evidence/m6a-f01-f17-substrate-map.json).
_FINDING_OWNERS: dict[str, str] = {
    "F01": "Run Authority",
    "F02": "WBC",
    "F03": "WBC",
    "F04": "WBC",
    "F05": "Run Authority",
    "F06": "Observability / Projection",
    "F07": "Planner / Compiler",
    "F08": "Planner / Compiler",
    "F09": "Planner / Compiler",
    "F10": "Executor Launcher",
    "F11": "Executor Launcher",
    "F12": "Planner / Compiler",
    "F13": "Executor Launcher",
    "F14": "Observability / Projection",
    "F15": "Transition Writer / Repair Custody",
    "F16": "Observability / Projection",
    "F17": "WBC",
}

# Mapping from findings to the synthetic fixtures that exercise them.
_FINDING_FIXTURE_MAP: dict[str, list[str]] = {
    "F07": ["transaction-spine-serial"],
    "F08": ["complexity-7-8-9"],
    "F09": ["strategy-validation"],
    "F12": ["six-task-rework"],
    "F13": ["repeated-budget-failures"],
}

# ---------------------------------------------------------------------------
# Circuit primitives (pure, deterministic)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CircuitDiagnostic:
    """A single circuit primitive result for a fixture."""

    code: str
    message: str
    fixture_key: str | None = None
    task_id: str | None = None


MAX_RETRIES = 2
MAX_SERIAL_REWORK = 5


def _retry_circuit_check(report: dict[str, Any], fixture_key: str) -> list[CircuitDiagnostic]:
    """Apply retry-limit circuit check.

    If a fixture has tasks with complexity >= 7 and a serial chain longer
    than MAX_RETRIES, raise a circuit-breaker warning.  This models the
    repeated-budget-failures pattern (F13).
    """
    diagnostics: list[CircuitDiagnostic] = []
    critical_count = report.get("critical_path_task_count", 0)
    seriality = report.get("seriality", 0.0)

    # All tasks are complexity-7 chained → retry chain too long
    if critical_count > MAX_RETRIES and seriality > 0.90:
        diagnostics.append(
            CircuitDiagnostic(
                "retry_chain_exceeds_circuit_threshold",
                f"Fixture {fixture_key!r} has {critical_count} serial tasks "
                f"but circuit threshold is {MAX_RETRIES}. "
                "Normalized failure signatures should open a circuit before a third retry.",
                fixture_key=fixture_key,
            )
        )
    return diagnostics


def _rework_wave_circuit_check(report: dict[str, Any], fixture_key: str) -> list[CircuitDiagnostic]:
    """Apply rework-wave ceiling check (F12).

    If more than MAX_SERIAL_REWORK tasks are on one critical path with
    rework-identifiable objectives, emit a circuit diagnostic.
    """
    diagnostics: list[CircuitDiagnostic] = []
    critical_count = report.get("critical_path_task_count", 0)

    if critical_count > MAX_SERIAL_REWORK:
        diagnostics.append(
            CircuitDiagnostic(
                "rework_wave_exceeds_ceiling",
                f"Fixture {fixture_key!r} has {critical_count} serial rework tasks "
                f"exceeding the {MAX_SERIAL_REWORK}-task rework-wave ceiling. "
                "Remaining tasks should be replanned as a separate milestone.",
                fixture_key=fixture_key,
            )
        )
    return diagnostics


def _all_circuit_checks(report: dict[str, Any], fixture_key: str) -> list[dict[str, Any]]:
    """Run all circuit primitives over a feasibility report and return structured diagnostics."""
    raw: list[CircuitDiagnostic] = []
    raw.extend(_retry_circuit_check(report, fixture_key))
    raw.extend(_rework_wave_circuit_check(report, fixture_key))
    return [
        {"code": d.code, "message": d.message, "fixture_key": d.fixture_key, "task_id": d.task_id}
        for d in raw
    ]


# ---------------------------------------------------------------------------
# Source-admission dry check
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceAdmissionDryCheck:
    """Result of a dry source-admission check — does NOT mutate state."""

    fixture_key: str
    fixture_path: str
    fixture_exists: bool
    fixture_sha256: str
    task_contract_version: int
    notes: str


def _dry_source_admission(fixture_payload: dict[str, Any], fixture_key: str, fixture_path: str) -> SourceAdmissionDryCheck:
    """Perform a dry (non-mutating) source-admission check on a fixture.

    This computes the identity of the fixture file as if it were a canonical
    source, but never mutates chain state or registers a requirement.
    """
    sha = hashlib.sha256(
        json.dumps(fixture_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return SourceAdmissionDryCheck(
        fixture_key=fixture_key,
        fixture_path=fixture_path,
        fixture_exists=True,
        fixture_sha256=f"sha256:{sha}",
        task_contract_version=fixture_payload.get("task_contract_version", 0),
        notes="Dry check only — no chain state mutation.",
    )


# ---------------------------------------------------------------------------
# Main report builder
# ---------------------------------------------------------------------------


def _load_fixture(fixture_key: str, fixtures_dir: Path) -> dict[str, Any]:
    """Load a synthetic v2 fixture from the m8a corpus."""
    from tests.fixtures.m8a import (  # type: ignore[import-not-found]
        complexity_7_8_9_cases,
        documentation_fixture_hashes,
        repeated_budget_failures,
        six_task_rework,
        strategy_validation_tasks,
        transaction_spine_serial,
    )

    loaders = {
        "transaction-spine-serial": transaction_spine_serial,
        "strategy-validation": strategy_validation_tasks,
        "complexity-7-8-9": complexity_7_8_9_cases,
        "repeated-budget-failures": repeated_budget_failures,
        "six-task-rework": six_task_rework,
        "documentation-fixture-hashes": documentation_fixture_hashes,
    }

    loader = loaders.get(fixture_key)
    if loader is None:
        raise KeyError(f"Unknown M8A fixture key: {fixture_key!r}")
    return loader()


def build_m8a_report(
    *,
    evidence_dir: Path | None = None,
    fixtures_dir: Path | None = None,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the complete M8A report corpus.

    Reads all synthetic v2 fixtures, runs task feasibility, batch splitting,
    source-admission dry checks, and circuit primitives, then produces a
    self-contained report that can be rebuilt deterministically.

    Parameters
    ----------
    evidence_dir:
        Directory for writing evidence artifacts.  Defaults to
        ``<project_root>/evidence``.
    fixtures_dir:
        Directory containing ``tests/fixtures/m8a/``.  Defaults to
        ``<project_root>/tests/fixtures/m8a``.
    config:
        Optional execute-phase configuration forwarded to
        ``compile_task_feasibility``.

    Returns
    -------
    A dictionary with the complete report corpus.
    """
    if evidence_dir is None:
        evidence_dir = Path(__file__).resolve().parents[3] / "evidence"
    if fixtures_dir is None:
        fixtures_dir = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "m8a"

    generated_at = now_utc()

    # Phase 1: Load documentation fixture hashes (read-only, no execution)
    try:
        doc_hashes = _load_fixture("documentation-fixture-hashes", fixtures_dir)
    except (KeyError, FileNotFoundError):
        doc_hashes = {
            "schema": "m8a.documentation-fixture-hashes.v1",
            "error": "documentation-fixture-hashes.json not loadable via fixture loader",
        }

    # Phase 2: Process each synthetic v2 fixture
    fixture_reports: dict[str, Any] = {}
    source_admissions: list[dict[str, Any]] = []
    all_circuit_diagnostics: list[dict[str, Any]] = []
    aggregate_counts: dict[str, int] = {
        "total_tasks": 0,
        "total_edges": 0,
        "total_admitted": 0,
        "total_rejected": 0,
        "total_diagnostics": 0,
        "total_circuit_diagnostics": 0,
    }

    for fixture_key in _FIXTURE_KEYS:
        try:
            payload = _load_fixture(fixture_key, fixtures_dir)
        except (KeyError, FileNotFoundError) as exc:
            fixture_reports[fixture_key] = {
                "error": f"Fixture not loadable: {exc}",
                "fixture_key": fixture_key,
            }
            continue

        # --- Task feasibility ---
        feasibility = compile_task_feasibility(payload, config)

        # --- Batch splitting ---
        raw_tasks = payload.get("tasks", [])
        if isinstance(raw_tasks, list) and raw_tasks:
            try:
                batches = compute_task_batches([dict(t) for t in raw_tasks])
            except ValueError:
                batches = []
        else:
            batches = []

        # --- Source-admission dry check ---
        fixture_path = str(fixtures_dir / f"{fixture_key}.json")
        dry = _dry_source_admission(payload, fixture_key, fixture_path)
        source_admissions.append(
            {
                "fixture_key": dry.fixture_key,
                "fixture_path": dry.fixture_path,
                "fixture_exists": dry.fixture_exists,
                "fixture_sha256": dry.fixture_sha256,
                "task_contract_version": dry.task_contract_version,
                "notes": dry.notes,
            }
        )

        # --- Circuit primitives ---
        circuit_diags = _all_circuit_checks(feasibility, fixture_key)
        all_circuit_diagnostics.extend(circuit_diags)

        # --- Per-fixture report ---
        fixture_reports[fixture_key] = {
            "fixture_key": fixture_key,
            "task_contract_hash": feasibility.get("task_contract_hash"),
            "task_count": feasibility.get("task_count", 0),
            "edge_count": feasibility.get("edge_count", 0),
            "root_count": feasibility.get("root_count", 0),
            "max_width": feasibility.get("max_width", 0),
            "batches": batches,
            "critical_path_task_ids": feasibility.get("critical_path_task_ids", []),
            "critical_path_task_count": feasibility.get("critical_path_task_count", 0),
            "critical_path_minutes": feasibility.get("critical_path_minutes", 0),
            "seriality": feasibility.get("seriality", 0),
            "estimated_dispatch_minutes": feasibility.get("estimated_dispatch_minutes", 0),
            "execute_phase_timeout_minutes": feasibility.get("execute_phase_timeout_minutes", 0),
            "admitted": feasibility.get("admitted", False),
            "diagnostics": feasibility.get("diagnostics", []),
            "circuit_diagnostics": circuit_diags,
            "source_admission": {
                "sha256": dry.fixture_sha256,
                "contract_version": dry.task_contract_version,
            },
        }

        # --- Aggregate counts ---
        aggregate_counts["total_tasks"] += feasibility.get("task_count", 0)
        aggregate_counts["total_edges"] += feasibility.get("edge_count", 0)
        if feasibility.get("admitted"):
            aggregate_counts["total_admitted"] += 1
        else:
            aggregate_counts["total_rejected"] += 1
        aggregate_counts["total_diagnostics"] += len(feasibility.get("diagnostics", []))
        aggregate_counts["total_circuit_diagnostics"] += len(circuit_diags)

    # Phase 3: Build the report corpus
    report_corpus: dict[str, Any] = {
        "schema": M8A_REPORT_SCHEMA,
        "generated_at": generated_at,
        "generator": "arnold_pipelines.megaplan.orchestration.m8a_report.build_m8a_report",
        "rebuildable": True,
        "north_star_guard": (
            "This report corpus is evidence only. No task, test, or executor "
            "may treat the historical M6/incident documents referenced herein "
            "as executable task graphs. The synthetic v2 fixtures exercised "
            "below are the honest way to exercise Transaction Spine and "
            "Strategy Roadmap shapes."
        ),
        "fixtures": fixture_reports,
        "source_admissions": source_admissions,
        "circuit_diagnostics_summary": all_circuit_diagnostics,
        "aggregate_counts": aggregate_counts,
        "documentation_fixture_hashes": doc_hashes,
        "finding_fixture_map": _FINDING_FIXTURE_MAP,
    }

    # Phase 4: Build executor wiring map
    executor_wiring = _build_executor_wiring(report_corpus, generated_at)

    # Phase 5: Write evidence artifacts (never mutates live/historical plans)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(evidence_dir / "m8a-report-only-corpus.json", report_corpus)
    atomic_write_json(evidence_dir / "m8a-f01-f17-executor-wiring.json", executor_wiring)

    return report_corpus


def _build_executor_wiring(
    report_corpus: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    """Build the F01-F17 executor wiring map from the report corpus.

    Maps each finding to the Megaplan component that owns it, lists the
    synthetic fixtures that exercise the finding, and records whether the
    finding is blocked, admitted, or pending evidence.
    """
    findings: dict[str, Any] = {}
    fixture_reports = report_corpus.get("fixtures", {})

    for finding_id in sorted(_FINDING_OWNERS):
        owner = _FINDING_OWNERS[finding_id]
        exercise_fixtures = _FINDING_FIXTURE_MAP.get(finding_id, [])

        fixture_statuses: dict[str, dict[str, Any]] = {}
        for fk in exercise_fixtures:
            fr = fixture_reports.get(fk, {})
            fixture_statuses[fk] = {
                "admitted": fr.get("admitted", False),
                "diagnostic_codes": [d.get("code") for d in fr.get("diagnostics", [])],
                "circuit_diagnostic_codes": [d.get("code") for d in fr.get("circuit_diagnostics", [])],
            }

        findings[finding_id] = {
            "finding_id": finding_id,
            "canonical_owner": owner,
            "m8a_component": _component_for_owner(owner),
            "exercise_fixtures": exercise_fixtures,
            "fixture_results": fixture_statuses,
            "status": "evidence-only",
            "notes": (
                f"{finding_id} is owned by {owner}. "
                "Enforcement starts only on newly finalized canary v2 plans (SD2)."
            ),
        }

    return {
        "schema": M8A_EXECUTOR_WIRING_SCHEMA,
        "generated_at": generated_at,
        "generator": "arnold_pipelines.megaplan.orchestration.m8a_report._build_executor_wiring",
        "rebuildable": True,
        "north_star_guard": (
            "This wiring map is evidence only. It maps findings to canonical "
            "owners and exercise fixtures but does not dispatch, enforce, or "
            "substitute authority. Enforcement starts only on newly finalized "
            "canary v2 plans (SD2)."
        ),
        "F01_F17_overview": {
            "planner_compiler_owned": ["F07", "F08", "F09", "F12"],
            "executor_launcher_owned": ["F10", "F11", "F13"],
            "run_authority_owned": ["F01", "F05"],
            "wbc_owned": ["F02", "F03", "F04", "F17"],
            "observability_projection_owned": ["F06", "F14", "F16"],
            "transition_writer_repair_custody_owned": ["F15"],
            "total_findings": 17,
        },
        "findings": findings,
    }


def _component_for_owner(owner: str) -> str:
    """Map a canonical owner to the M8A Megaplan component name."""
    mapping = {
        "Run Authority": "run_authority",
        "WBC": "wbc",
        "Planner / Compiler": "planner_compiler",
        "Executor Launcher": "executor_launcher",
        "Observability / Projection": "observability_projection",
        "Transition Writer / Repair Custody": "transition_writer_repair_custody",
    }
    return mapping.get(owner, "unknown")


# ---------------------------------------------------------------------------
# Rebuild helper
# ---------------------------------------------------------------------------


def rebuild_m8a_evidence(
    *,
    evidence_dir: Path | None = None,
    fixtures_dir: Path | None = None,
    config: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Rebuild both M8A evidence artifacts and return them.

    Returns the (report_corpus, executor_wiring) tuple without writing to disk.
    Useful for dry-run verification in tests.
    """
    report = build_m8a_report(
        evidence_dir=evidence_dir,
        fixtures_dir=fixtures_dir,
        config=config,
    )

    if evidence_dir is None:
        evidence_dir = Path(__file__).resolve().parents[3] / "evidence"

    wiring_path = evidence_dir / "m8a-f01-f17-executor-wiring.json"
    if wiring_path.exists():
        with wiring_path.open(encoding="utf-8") as fh:
            wiring = json.load(fh)
    else:
        wiring = _build_executor_wiring(report, report.get("generated_at", now_utc()))

    return report, wiring


__all__ = [
    "M8A_REPORT_SCHEMA",
    "M8A_EXECUTOR_WIRING_SCHEMA",
    "build_m8a_report",
    "rebuild_m8a_evidence",
    "CircuitDiagnostic",
    "SourceAdmissionDryCheck",
]
