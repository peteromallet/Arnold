"""M4 T4 — Generate graph-executor golden traces for the M4 Megaplan fixture catalog.

For every scenario in the native-parity catalog that is runnable with the
current test infrastructure (mock workers, in-process handlers), this module:

1. Runs the scenario through the graph executor (:func:`run_pipeline`).
2. Captures a normalized golden trace: stage sequence, final state, envelope,
   resume cursor, artifact inventory, and artifact content digests.
3. Persists the golden trace under ``data/native_parity/<scenario_id>_golden_graph_trace.json``.

Scenarios that cannot be executed are recorded with a ``blocked`` field
naming the missing precondition.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from tests.arnold.pipelines.megaplan.data.native_parity.scenarios import (
    PARITY_SCENARIOS,
    ParityScenario,
)


# ═══════════════════════════════════════════════════════════════════════════
# Golden trace schema (version 1)
# ═══════════════════════════════════════════════════════════════════════════

GOLDEN_TRACE_SCHEMA_VERSION = 1


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_hex(path.read_bytes())


def _artifact_inventory(artifact_root: Path, plan_dir: Path) -> dict[str, Any]:
    """Return an inventory of all files under *artifact_root* and *plan_dir*."""
    inventory: dict[str, Any] = {"artifact_root_files": {}, "plan_dir_files": {}}

    for root, label in ((artifact_root, "artifact_root_files"), (plan_dir, "plan_dir_files")):
        root_path = Path(root)
        if not root_path.is_dir():
            continue
        for file_path in sorted(root_path.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(root_path).as_posix()
            try:
                inventory[label][rel] = _sha256_file(file_path)
            except OSError:
                inventory[label][rel] = None  # unreadable
    return inventory


def _normalize_state_for_golden(state: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *state* with non-deterministic fields stripped or
    normalized so the golden trace is stable across runs.

    Fields stripped:
    - Timestamps, UUIDs, invocation IDs, session IDs
    - Absolute paths (replaced with placeholder)
    """
    result = _strip_ephemeral_fields(dict(state))
    return result


_EPHEMERAL_KEYS: frozenset[str] = frozenset({
    "invocation_id",
    "session_id",
    "started_at",
    "finished_at",
    "timestamp",
    "created_at",
    "updated_at",
})


def _strip_ephemeral_fields(obj: Any) -> Any:
    """Recursively remove ephemeral fields and normalize absolute paths."""
    if isinstance(obj, dict):
        cleaned: dict[str, Any] = {}
        for key, value in obj.items():
            if key in _EPHEMERAL_KEYS:
                continue
            # Normalize absolute paths
            if isinstance(value, str) and value.startswith("/"):
                cleaned[key] = "<absolute-path>"
            else:
                cleaned[key] = _strip_ephemeral_fields(value)
        return cleaned
    if isinstance(obj, list):
        return [_strip_ephemeral_fields(v) for v in obj]
    return obj


def _serialize_envelope(envelope: Any) -> dict[str, Any] | None:
    """Serialize a RunEnvelope to a JSON-compatible dict."""
    if envelope is None:
        return None
    if hasattr(envelope, "to_json"):
        return envelope.to_json()
    if hasattr(envelope, "__dataclass_fields__"):
        from dataclasses import asdict
        return asdict(envelope)
    return {"repr": repr(envelope)}


def _build_golden_trace(
    scenario: ParityScenario,
    *,
    stage_sequence: list[str],
    final_result: dict[str, Any],
    artifact_root: Path,
    plan_dir: Path,
    blocked: str | None = None,
) -> dict[str, Any]:
    """Assemble a normalized golden trace dict."""
    trace: dict[str, Any] = {
        "schema_version": GOLDEN_TRACE_SCHEMA_VERSION,
        "scenario_id": scenario.scenario_id,
        "generated_by": "graph_executor",
    }

    if blocked is not None:
        trace["blocked"] = True
        trace["blocked_reason"] = blocked
        trace["stage_sequence"] = []
        trace["final_stage"] = None
        trace["state"] = None
        trace["envelope"] = None
        trace["resume_cursor"] = None
        trace["artifact_inventory"] = {}
        return trace

    state = final_result.get("state", {})
    envelope = final_result.get("envelope")

    trace["blocked"] = False
    trace["stage_sequence"] = stage_sequence
    trace["final_stage"] = final_result.get("final_stage")
    trace["halt_reason"] = final_result.get("halt_reason")
    trace["state"] = _normalize_state_for_golden(
        state if isinstance(state, dict) else {}
    )
    trace["envelope"] = _serialize_envelope(envelope)
    trace["resume_cursor"] = state.get("resume_cursor") if isinstance(state, dict) else None

    if isinstance(trace["resume_cursor"], dict):
        # Normalize cursor for golden stability
        trace["resume_cursor"] = _normalize_state_for_golden(trace["resume_cursor"])

    trace["artifact_inventory"] = _artifact_inventory(artifact_root, plan_dir)
    return trace


# ═══════════════════════════════════════════════════════════════════════════
# Pipeline runner helper
# ═══════════════════════════════════════════════════════════════════════════


def _run_graph_executor_on_plan(
    plan_name: str,
    plan_dir: Path,
    root: Path,
    project_dir: Path,
    artifact_root: Path,
    *,
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Run the Megaplan graph executor on an initialized plan.

    Returns (stage_sequence, final_result).
    """
    from arnold.pipelines.megaplan.pipeline import build_pipeline
    from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
    from arnold.pipelines.megaplan._pipeline.types import StepContext

    pipeline = build_pipeline()

    # Read current state from disk
    try:
        live_state = json.loads((plan_dir / "state.json").read_text())
    except (OSError, json.JSONDecodeError):
        live_state = {}

    ctx = StepContext(
        plan_dir=plan_dir,
        state={"name": plan_name, **live_state},
        profile={"root": root, "project_dir": str(project_dir)},
        mode="code",
        inputs={},
        budget=None,
    )

    result = run_pipeline(pipeline, ctx, artifact_root=artifact_root)

    # Reconstruct stage sequence from plan directory artifacts and state
    state = result.get("state", {})
    stage_sequence = _reconstruct_stage_sequence(plan_dir, state if isinstance(state, dict) else {})

    return stage_sequence, result


def _reconstruct_stage_sequence(plan_dir: Path, state: dict[str, Any]) -> list[str]:
    """Reconstruct the stage visitation order from plan artifacts and state.

    Strategy: reconstruct the execution order by examining the versioned
    critique/gate artifact files and the state iteration counter. This
    handles repeated stage visits (critique/gate loops) correctly.
    """
    visited: list[str] = []

    # Phase 1: always starts with prep → plan
    if (plan_dir / "prep.json").exists():
        visited.append("prep")
    if (plan_dir / "plan_v1.md").exists():
        visited.append("plan")

    # Phase 2: critique/gate loop detection
    # Count how many critique versions exist
    critique_versions = sorted(
        int(p.stem.split("_v")[-1])
        for p in plan_dir.glob("critique_v*.json")
        if p.stem.startswith("critique_v") and p.stem.split("_v")[-1].isdigit()
    )
    gate_versions = sorted(
        int(p.stem.split("_v")[-1])
        for p in plan_dir.glob("gate_signals_v*.json")
        if p.stem.startswith("gate_signals_v") and p.stem.split("_v")[-1].isdigit()
    )

    max_critique = max(critique_versions) if critique_versions else 0
    max_gate = max(gate_versions) if gate_versions else 0

    # Reconstruct critique → gate → (revise → critique → gate)*
    for i in range(1, max(max_critique, max_gate) + 1):
        if i in critique_versions or (plan_dir / f"critique_v{i}.json").exists():
            visited.append("critique")
        if i in gate_versions or (i == 1 and (plan_dir / "gate.json").exists()):
            visited.append("gate")
        # If there's a next critique version, revise must have happened
        if i + 1 in critique_versions:
            visited.append("revise")

    # Phase 3: post-gate stages
    if (plan_dir / "final.md").exists():
        visited.append("finalize")
    if (plan_dir / "execution.json").exists():
        visited.append("execute")
    if (plan_dir / "review.json").exists():
        visited.append("review")

    # tiebreaker detection: check state or artifact
    if isinstance(state, dict):
        history = state.get("history", []) or []
        for entry in history:
            if isinstance(entry, dict) and entry.get("phase") == "tiebreaker":
                if "tiebreaker" not in visited:
                    visited.append("tiebreaker")
                break

    return visited


# ═══════════════════════════════════════════════════════════════════════════
# Per-scenario golden trace generation
# ═══════════════════════════════════════════════════════════════════════════


class TestGenerateGoldenTraces:
    """Generate and persist graph-executor golden traces for each scenario.

    Each test function drives one scenario and writes the corresponding
    golden trace file to ``data/native_parity/``.  Scenarios that cannot
    be executed are recorded with a ``blocked`` marker.
    """

    # ═══════════════════════════════════════════════════════════════════
    # Runnable scenarios
    # ═══════════════════════════════════════════════════════════════════

    def test_golden_trace_happy_finalize(
        self,
        tmp_path: Path,
        bootstrap_fixture: tuple[Path, Path],
    ) -> None:
        """happy_finalize: gate recommends proceed → finalize → execute → review → halt."""
        self._generate_trace_for_scenario(
            "happy_finalize",
            tmp_path,
            bootstrap_fixture,
        )

    # ═══════════════════════════════════════════════════════════════════
    # Blocked scenarios
    # ═══════════════════════════════════════════════════════════════════

    def test_golden_trace_revise_loop_blocked(
        self,
        tmp_path: Path,
        bootstrap_fixture: tuple[Path, Path],
    ) -> None:
        """revise_loop: blocked — requires gate to return 'iterate' then 'proceed'."""
        self._write_blocked_trace(
            "revise_loop",
            "Requires gate worker mock returning 'iterate' then 'proceed'; "
            "default mock workers only produce 'proceed'.",
        )

    def test_golden_trace_tiebreaker_blocked(
        self,
        tmp_path: Path,
        bootstrap_fixture: tuple[Path, Path],
    ) -> None:
        """tiebreaker: blocked — requires gate to return 'tiebreaker'."""
        self._write_blocked_trace(
            "tiebreaker",
            "Requires gate worker mock returning 'tiebreaker'; "
            "default mock workers only produce 'proceed'.",
        )

    def test_golden_trace_escalate_blocked(
        self,
        tmp_path: Path,
        bootstrap_fixture: tuple[Path, Path],
    ) -> None:
        """escalate: blocked — requires gate to return 'escalate'."""
        self._write_blocked_trace(
            "escalate",
            "Requires gate worker mock returning 'escalate'; "
            "default mock workers only produce 'proceed'.",
        )

    def test_golden_trace_override_force_proceed_blocked(
        self,
        tmp_path: Path,
        bootstrap_fixture: tuple[Path, Path],
    ) -> None:
        """override force-proceed: blocked — requires gate override dispatch."""
        self._write_blocked_trace(
            "override_force_proceed",
            "Requires gate override infrastructure ('override force-proceed' edge dispatch); "
            "not reproducible with default mock worker output.",
        )

    def test_golden_trace_override_abort_blocked(
        self,
        tmp_path: Path,
        bootstrap_fixture: tuple[Path, Path],
    ) -> None:
        """override abort: blocked — requires gate override abort dispatch."""
        self._write_blocked_trace(
            "override_abort",
            "Requires gate override abort infrastructure ('override abort' edge dispatch); "
            "not reproducible with default mock worker output.",
        )

    def test_golden_trace_suspension_resume_blocked(
        self,
        tmp_path: Path,
        bootstrap_fixture: tuple[Path, Path],
    ) -> None:
        """suspension_resume: blocked — requires suspension mid-execution and resume."""
        self._write_blocked_trace(
            "suspension_resume",
            "Requires suspension mid-execution (human gate awaiting user) and resume path; "
            "default mock path does not trigger suspension.",
        )

    def test_golden_trace_execute_review_artifact_blocked(
        self,
        tmp_path: Path,
        bootstrap_fixture: tuple[Path, Path],
    ) -> None:
        """execute_review_artifact: blocked — requires execute to produce verifiable artifacts."""
        self._write_blocked_trace(
            "execute_review_artifact",
            "Requires execute phase to produce distinct artifacts for review consumption; "
            "default mock workers produce minimal output. "
            "Artifact content verification deferred to native execution path.",
        )

    # ═══════════════════════════════════════════════════════════════════
    # Internal helpers
    # ═══════════════════════════════════════════════════════════════════

    def _generate_trace_for_scenario(
        self,
        scenario_id: str,
        tmp_path: Path,
        bootstrap_fixture: tuple[Path, Path],
    ) -> None:
        """Run the graph executor for a scenario and persist the golden trace."""
        from tests.arnold.pipelines.megaplan.data.native_parity.scenarios import (
            PARITY_SCENARIO_BY_ID,
        )

        scenario = PARITY_SCENARIO_BY_ID[scenario_id]
        root, project_dir = bootstrap_fixture

        import arnold.pipelines.megaplan as megaplan
        from tests.conftest import make_args_factory

        make_args = make_args_factory(project_dir)

        # Initialize a fresh plan
        init_args = make_args(plan_name=f"golden-{scenario_id}", robustness="standard")
        response = megaplan.handle_init(root, init_args)
        plan_name = response["plan"]
        plan_dir = megaplan.plans_root(root) / plan_name

        artifact_root = tmp_path / "artifact_root"
        artifact_root.mkdir()

        stage_sequence, final_result = _run_graph_executor_on_plan(
            plan_name=plan_name,
            plan_dir=plan_dir,
            root=root,
            project_dir=project_dir,
            artifact_root=artifact_root,
        )

        trace = _build_golden_trace(
            scenario,
            stage_sequence=stage_sequence,
            final_result=final_result,
            artifact_root=artifact_root,
            plan_dir=plan_dir,
        )

        golden_path = scenario.golden_graph_trace_path
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(json.dumps(trace, indent=2, sort_keys=True, default=str))

        # Basic assertions on the golden trace
        assert trace["blocked"] is False
        assert len(trace["stage_sequence"]) > 0
        assert trace["final_stage"] is not None
        assert isinstance(trace["state"], dict)

    def _write_blocked_trace(
        self,
        scenario_id: str,
        reason: str,
    ) -> None:
        """Write a blocked golden trace marker for a non-runnable scenario."""
        from tests.arnold.pipelines.megaplan.data.native_parity.scenarios import (
            PARITY_SCENARIO_BY_ID,
        )

        scenario = PARITY_SCENARIO_BY_ID[scenario_id]
        trace = _build_golden_trace(
            scenario,
            stage_sequence=[],
            final_result={},
            artifact_root=Path(),
            plan_dir=Path(),
            blocked=reason,
        )

        golden_path = scenario.golden_graph_trace_path
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(json.dumps(trace, indent=2, sort_keys=True, default=str))

        assert trace["blocked"] is True
        assert trace["blocked_reason"] == reason
