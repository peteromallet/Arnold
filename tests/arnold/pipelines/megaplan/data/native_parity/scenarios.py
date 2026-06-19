"""Stable scenario descriptors for the M4 Megaplan native parity matrix.

Each scenario is a lightweight dataclass with:
- ``scenario_id``: stable identifier used as golden file stem
- ``description``: human-readable summary of the branch path
- ``expected_branch_labels``: ordered list of gate recommendations expected on the path
- ``expected_stage_sequence``: ordered list of stage names expected on the path
- ``golden_output_stem``: path stem under ``data/native_parity/`` for golden files
- ``blocked``: optional reason the scenario cannot yet run (e.g., missing infrastructure)

These are **assertion-free descriptors** — the parity runner (T4+) consumes them.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import ClassVar


@dataclasses.dataclass(frozen=True)
class ParityScenario:
    """Descriptor for one Megaplan parity scenario.

    Immutable so the catalog cannot be mutated by a runner mid-execution.
    """

    scenario_id: str
    description: str
    expected_branch_labels: tuple[str, ...]
    expected_stage_sequence: tuple[str, ...]
    blocked: str | None = None

    # ── derived golden output locations ──────────────────────────
    _DATA_DIR: ClassVar[Path] = Path(__file__).resolve().parent

    @property
    def golden_graph_trace_path(self) -> Path:
        """Path where the graph-executor golden trace will be stored."""
        return self._DATA_DIR / f"{self.scenario_id}_golden_graph_trace.json"

    @property
    def golden_native_trace_path(self) -> Path:
        """Path where the native-executor golden trace will be stored."""
        return self._DATA_DIR / f"{self.scenario_id}_golden_native_trace.json"

    @property
    def golden_cursor_path(self) -> Path:
        """Path where the golden composite cursor will be stored."""
        return self._DATA_DIR / f"{self.scenario_id}_golden_composite_cursor.json"


# ═══════════════════════════════════════════════════════════════════════
# Scenario inventory — the eight agreed parity scenarios
# ═══════════════════════════════════════════════════════════════════════

SCENARIO_HAPPY_FINALIZE = ParityScenario(
    scenario_id="happy_finalize",
    description="Gate recommends proceed → finalize → execute → review → halt",
    expected_branch_labels=("proceed",),
    expected_stage_sequence=(
        "prep", "plan", "critique", "gate",
        "finalize", "execute", "review",
    ),
)

SCENARIO_REVISE_LOOP = ParityScenario(
    scenario_id="revise_loop",
    description="Gate recommends iterate → revise → critique → gate (loop then proceed)",
    expected_branch_labels=("iterate", "proceed"),
    expected_stage_sequence=(
        "prep", "plan", "critique", "gate",
        "revise", "critique", "gate",
        "finalize", "execute", "review",
    ),
)

SCENARIO_TIEBREAKER = ParityScenario(
    scenario_id="tiebreaker",
    description="Gate recommends tiebreaker → tiebreaker stage resolves → critique → proceed",
    expected_branch_labels=("tiebreaker", "proceed"),
    expected_stage_sequence=(
        "prep", "plan", "critique", "gate",
        "tiebreaker", "critique", "gate",
        "finalize", "execute", "review",
    ),
)

SCENARIO_ESCALATE = ParityScenario(
    scenario_id="escalate",
    description="Gate recommends escalate → escalates to finalize (no tiebreaker stage)",
    expected_branch_labels=("escalate",),
    expected_stage_sequence=(
        "prep", "plan", "critique", "gate",
        "finalize", "execute", "review",
    ),
)

SCENARIO_OVERRIDE_FORCE_PROCEED = ParityScenario(
    scenario_id="override_force_proceed",
    description="Gate override force-proceed bypasses normal decision → finalize",
    expected_branch_labels=("override force-proceed",),
    expected_stage_sequence=(
        "prep", "plan", "critique", "gate",
        "finalize", "execute", "review",
    ),
)

SCENARIO_OVERRIDE_ABORT = ParityScenario(
    scenario_id="override_abort",
    description="Gate override abort → halt (pipeline terminates at gate)",
    expected_branch_labels=("override abort",),
    expected_stage_sequence=(
        "prep", "plan", "critique", "gate",
    ),
)

SCENARIO_SUSPENSION_RESUME = ParityScenario(
    scenario_id="suspension_resume",
    description="Suspend mid-execution after finalize, resume, complete execute → review",
    expected_branch_labels=("proceed",),
    expected_stage_sequence=(
        "prep", "plan", "critique", "gate",
        "finalize",
        # suspension/resume boundary
        "execute", "review",
    ),
)

SCENARIO_EXECUTE_REVIEW_ARTIFACT = ParityScenario(
    scenario_id="execute_review_artifact",
    description="Execute produces artifacts, review consumes and validates them",
    expected_branch_labels=("proceed",),
    expected_stage_sequence=(
        "prep", "plan", "critique", "gate",
        "finalize", "execute", "review",
    ),
)

# ═══════════════════════════════════════════════════════════════════════
# Ordered catalog — consumers iterate this to discover all scenarios
# ═══════════════════════════════════════════════════════════════════════

PARITY_SCENARIOS: tuple[ParityScenario, ...] = (
    SCENARIO_HAPPY_FINALIZE,
    SCENARIO_REVISE_LOOP,
    SCENARIO_TIEBREAKER,
    SCENARIO_ESCALATE,
    SCENARIO_OVERRIDE_FORCE_PROCEED,
    SCENARIO_OVERRIDE_ABORT,
    SCENARIO_SUSPENSION_RESUME,
    SCENARIO_EXECUTE_REVIEW_ARTIFACT,
)

# Lookup by scenario_id for convenience
PARITY_SCENARIO_BY_ID: dict[str, ParityScenario] = {
    s.scenario_id: s for s in PARITY_SCENARIOS
}
