"""Gate and tiebreaker parity tests for the manifest-backed Megaplan pipeline.

These tests drive the canonical compiled manifest with in-memory fake handlers
and verify that gate decisions, escalation, suspension, blocked preflight, and
tiebreaker routing behave deterministically under the M3 manifest runtime.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pytest

from arnold.execution import run as run_manifest
from arnold.execution.result import ExecutionState
from arnold.kernel import read_event_journal

from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline
from tests.arnold_pipelines.megaplan.test_parity_harness import (
    FakeMegaplanBackend,
    branch_selections,
    completed_nodes,
    control_transitions,
    make_simple_handler,
    suspension_points,
)


def _run_gate_scenario(
    tmp_path: Path,
    gate_response: dict[str, Any],
    extra_handlers: dict[str, Any] | None = None,
    tiebreaker_decide_response: dict[str, Any] | None = None,
    review_response: dict[str, Any] | None = None,
) -> tuple[Any, list[Any]]:
    """Run the manifest with a configurable gate response."""

    manifest = build_and_compile_pipeline()
    plan_dir = tmp_path / "plans" / "gate-parity"
    plan_dir.mkdir(parents=True)
    artifact_root = tmp_path / "artifacts"

    handlers: dict[str, Any] = {
        "prep": make_simple_handler({"success": True, "next_step": "plan"}),
        "plan": make_simple_handler({"success": True, "next_step": "critique"}),
        "critique": make_simple_handler({"success": True, "next_step": "gate"}),
        "gate": make_simple_handler(gate_response),
        "finalize": make_simple_handler({"success": True, "next_step": "execute"}),
        "execute": make_simple_handler({"success": True, "next_step": "review"}),
        "review": make_simple_handler(review_response or {"success": True, "verdict": "pass"}),
    }
    if tiebreaker_decide_response:
        handlers["tiebreaker_run"] = make_simple_handler(
            {"success": True, "next_step": "tiebreaker_decide"}
        )
        handlers["tiebreaker_decide"] = make_simple_handler(tiebreaker_decide_response)
    handlers.update(extra_handlers or {})

    backend = FakeMegaplanBackend(
        plan_dir=plan_dir,
        handlers=handlers,
    )
    result = run_manifest(
        manifest,
        artifact_root=artifact_root,
        backend=backend,
    )
    events = list(read_event_journal(artifact_root))
    return result, events


class TestGateBranchParity:
    def test_gate_proceed_routes_to_finalize(self, tmp_path: Path) -> None:
        result, events = _run_gate_scenario(
            tmp_path,
            gate_response={"success": True, "recommendation": "PROCEED"},
        )
        assert result.state == ExecutionState.COMPLETED
        assert branch_selections(events) == [
            ("gate", "gate:finalize"),
            ("review", "review:halt"),
        ]
        assert completed_nodes(events) == [
            "prep", "plan", "critique", "gate", "finalize", "execute", "review", "halt"
        ]

    def test_gate_iterate_routes_to_revise_then_loops_back(self, tmp_path: Path) -> None:
        result, events = _run_gate_scenario(
            tmp_path,
            gate_response={"success": True, "recommendation": "ITERATE"},
        )
        assert result.state == ExecutionState.COMPLETED
        # The M3 runtime executes one bounded pass through the revise branch.
        assert branch_selections(events) == [
            ("gate", "gate:revise"),
            ("revise", "revise:critique"),
        ]
        assert completed_nodes(events).count("gate") == 1
        assert completed_nodes(events).count("revise") == 1

    def test_gate_abort_routes_to_halt(self, tmp_path: Path) -> None:
        result, events = _run_gate_scenario(
            tmp_path,
            gate_response={"success": True, "recommendation": "ABORT"},
        )
        assert result.state == ExecutionState.COMPLETED
        assert branch_selections(events) == [("gate", "gate:halt")]
        assert completed_nodes(events) == ["prep", "plan", "critique", "gate", "halt"]

    def test_gate_escalate_emits_control_transition(self, tmp_path: Path) -> None:
        result, events = _run_gate_scenario(
            tmp_path,
            gate_response={"success": True, "recommendation": "ESCALATE"},
            extra_handlers={
                "override": make_simple_handler(
                    {"success": True, "override_action": "finalize", "next_step": "finalize"}
                ),
            },
        )
        assert result.state == ExecutionState.COMPLETED
        assert branch_selections(events) == [
            ("gate", "gate:override"),
            ("override", "override:finalize"),
            ("review", "review:halt"),
        ]
        transitions = control_transitions(events)
        assert any(t.get("trigger") == "gate:escalate" for t in transitions)

    def test_gate_suspend_routes_to_suspension(self, tmp_path: Path) -> None:
        result, events = _run_gate_scenario(
            tmp_path,
            gate_response={"success": True, "state": "awaiting_human", "next_step": "suspend"},
        )
        assert result.state == ExecutionState.SUSPENDED
        assert suspension_points(events) == [("gate", "gate:human")]


class TestBlockedPreflightParity:
    def test_blocked_agent_preflight_force_proceed(self, tmp_path: Path) -> None:
        result, events = _run_gate_scenario(
            tmp_path,
            gate_response={
                "success": True,
                "recommendation": "PROCEED",
                "next_step": "override force-proceed",
            },
            extra_handlers={
                "override": make_simple_handler(
                    {"success": True, "override_action": "finalize", "next_step": "finalize"}
                ),
            },
        )
        assert result.state == ExecutionState.COMPLETED
        assert branch_selections(events) == [
            ("gate", "gate:force_proceed"),
            ("review", "review:halt"),
        ]
        assert completed_nodes(events) == [
            "prep", "plan", "critique", "gate", "finalize", "execute", "review", "halt"
        ]

    def test_blocked_non_agent_preflight_escalates(self, tmp_path: Path) -> None:
        result, events = _run_gate_scenario(
            tmp_path,
            gate_response={
                "success": True,
                "recommendation": "ESCALATE",
                "next_step": "override add-note",
            },
            extra_handlers={
                "override": make_simple_handler(
                    {"success": True, "override_action": "finalize", "next_step": "finalize"}
                ),
            },
        )
        assert result.state == ExecutionState.COMPLETED
        assert branch_selections(events) == [
            ("gate", "gate:override"),
            ("override", "override:finalize"),
            ("review", "review:halt"),
        ]


class TestForceProceedPaths:
    def test_gate_force_proceed_directly_to_finalize(self, tmp_path: Path) -> None:
        result, events = _run_gate_scenario(
            tmp_path,
            gate_response={"success": True, "next_step": "force_proceed"},
        )
        assert result.state == ExecutionState.COMPLETED
        assert branch_selections(events) == [
            ("gate", "gate:force_proceed"),
            ("review", "review:halt"),
        ]

    def test_override_force_proceed_after_escalation(self, tmp_path: Path) -> None:
        result, events = _run_gate_scenario(
            tmp_path,
            gate_response={"success": True, "recommendation": "ESCALATE"},
            extra_handlers={
                "override": make_simple_handler(
                    {"success": True, "override_action": "finalize", "next_step": "finalize"}
                ),
            },
        )
        assert result.state == ExecutionState.COMPLETED
        assert branch_selections(events) == [
            ("gate", "gate:override"),
            ("override", "override:finalize"),
            ("review", "review:halt"),
        ]


class TestAutoDowngrade:
    def test_auto_downgrade_proceed_to_iterate_with_rationale(self, tmp_path: Path) -> None:
        # Simulates the legacy handler's auto-downgrade path: gate returns PROCEED
        # but the harness rewrites to ITERATE with a rationale marker.
        def downgrade_handler(root: Path, args: argparse.Namespace) -> dict[str, Any]:
            return {
                "success": True,
                "recommendation": "ITERATE",
                "passed": False,
                "rationale": (
                    "Looks good [Auto-downgraded from PROCEED: high-complexity "
                    "unverifiable check(s) HC1 must be resolved before finalizing.]"
                ),
            }

        result, events = _run_gate_scenario(
            tmp_path,
            gate_response={},
            extra_handlers={"gate": downgrade_handler},
        )
        assert result.state == ExecutionState.COMPLETED
        assert branch_selections(events) == [
            ("gate", "gate:revise"),
            ("revise", "revise:critique"),
        ]


class TestTiebreakerParity:
    def test_tiebreaker_routes_through_decide_to_proceed(self, tmp_path: Path) -> None:
        """Tiebreaker gate routes to the tiebreaker branch and a decision is made.

        Note: recursive tiebreaker loops require a resumed or re-entrant cursor in
        the M3 runtime because ``critique`` is already completed on the first pass.
        This test verifies the initial tiebreaker path is wired correctly.
        """
        manifest = build_and_compile_pipeline()
        plan_dir = tmp_path / "plans" / "tiebreaker"
        plan_dir.mkdir(parents=True)
        artifact_root = tmp_path / "artifacts"

        handlers = {
            "prep": make_simple_handler({"success": True, "next_step": "plan"}),
            "plan": make_simple_handler({"success": True, "next_step": "critique"}),
            "critique": make_simple_handler({"success": True, "next_step": "gate"}),
            "gate": make_simple_handler({"success": True, "recommendation": "TIEBREAKER"}),
            "tiebreaker_run": make_simple_handler({"success": True, "next_step": "tiebreaker_decide"}),
            "tiebreaker_decide": make_simple_handler({"success": True, "decision": "PROCEED", "next_step": "proceed"}),
            "finalize": make_simple_handler({"success": True, "next_step": "execute"}),
            "execute": make_simple_handler({"success": True, "next_step": "review"}),
            "review": make_simple_handler({"success": True, "verdict": "pass"}),
        }

        backend = FakeMegaplanBackend(plan_dir=plan_dir, handlers=handlers)
        result = run_manifest(manifest, artifact_root=artifact_root, backend=backend)
        events = list(read_event_journal(artifact_root))

        assert result.state == ExecutionState.COMPLETED
        branches = branch_selections(events)
        assert ("gate", "gate:tiebreaker") in branches
        assert ("tiebreaker_decide", "tiebreaker_decide:finalize") in branches
        assert completed_nodes(events) == [
            "prep", "plan", "critique", "gate", "tiebreaker_run", "tiebreaker_decide",
            "finalize", "execute", "review", "halt",
        ]
