"""Focused gate-to-revise tests for North Star action carry and halt behavior.

Proves: (1) ``gate.json`` / ``gate_carry.json`` preserve normalized North Star actions,
(2) the revise prompt/context includes carried actions from gate_carry with gate.json
fallback, and (3) the pre-worker revise guard halts before worker invocation when
``add_human_halt`` or unmappable blocking actions are present.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.north_star_actions import (
    SEVERITY_ADVISORY,
    SEVERITY_BLOCKING,
    SEVERITY_SOURCE_SCHEMA,
    SEVERITY_SOURCE_WORKER,
    NORTH_STAR_DANGEROUS_CATEGORIES,
    NorthStarActionValidationError,
    normalize_north_star_action,
    normalize_north_star_actions,
)
from arnold_pipelines.megaplan.orchestration.gate_checks import build_gate_artifact
from arnold_pipelines.megaplan.orchestration.critique_runtime import (
    _carried_north_star_actions,
    _revise_north_star_halt_actions,
)
from arnold_pipelines.megaplan.handlers.gate import _build_gate_carry


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def _minimal_signals(**overrides: Any) -> dict[str, Any]:
    """Return a well-formed gate signals dict the artifact builder accepts."""
    defaults: dict[str, Any] = {
        "signals": {"addressed_flags": []},
        "preflight_results": {"project_dir_exists": True, "project_dir_writable": True},
        "criteria_check": {"count": 3, "items": ["c1", "c2", "c3"]},
        "unresolved_flags": [],
        "warnings": [],
        "robustness": "standard",
    }
    defaults.update(overrides)
    return defaults


def _minimal_gate_payload(**overrides: Any) -> dict[str, Any]:
    """Return a minimal gate payload for build_gate_artifact."""
    defaults: dict[str, Any] = {
        "recommendation": "ITERATE",
        "rationale": "Needs revision.",
        "signals_assessment": "ok",
        "warnings": [],
        "settled_decisions": [],
        "flag_resolutions": [],
        "accepted_tradeoffs": [],
        "north_star_actions": [],
        "resolved_flag_ids": [],
        "resolution_summary": "",
    }
    defaults.update(overrides)
    return defaults


def _ns_action(**overrides: Any) -> dict[str, Any]:
    """Return a well-formed advisory North Star action for gate payloads."""
    action: dict[str, Any] = {
        "id": "ns-test-001",
        "concern": "The plan lacks a rollback step.",
        "category": "completeness",
        "action_type": "change_plan",
        "severity": SEVERITY_ADVISORY,
        "severity_source": SEVERITY_SOURCE_WORKER,
        "evidence": "Step 3 has no undo mechanism.",
    }
    action.update(overrides)
    return action


def _blocking_ns_action(**overrides: Any) -> dict[str, Any]:
    """Return a blocking North Star action (dangerous category)."""
    return _ns_action(
        category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[0],  # baselines
        severity=SEVERITY_BLOCKING,
        severity_source=SEVERITY_SOURCE_SCHEMA,
        evidence=overrides.pop("evidence", "Route authority bypass detected."),
        **overrides,
    )


# --------------------------------------------------------------------------- #
# Gate artifact tests — normalized actions survive the build
# --------------------------------------------------------------------------- #


class TestGateArtifactNormalizedActions:
    """Build the gate artifact and inspect its ``north_star_actions`` field."""

    def test_missing_north_star_actions_fails_closed(self) -> None:
        """Persistence cannot turn an absent required action list into []."""
        signals = _minimal_signals()
        payload = _minimal_gate_payload()
        payload.pop("north_star_actions")
        with pytest.raises(RuntimeError, match="north_star_actions"):
            build_gate_artifact(signals, payload, override_forced=False)

    def test_payload_north_star_actions_are_normalized(self) -> None:
        """When the payload carries raw actions, they are normalized in the artifact."""
        raw_action = _ns_action(
            id="ns-01",
            category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[0],
            severity=SEVERITY_ADVISORY,  # will be overridden
        )
        signals = _minimal_signals()
        payload = _minimal_gate_payload(north_star_actions=[raw_action])
        artifact = build_gate_artifact(signals, payload, override_forced=False)

        actions = artifact["north_star_actions"]
        assert len(actions) == 1
        # Dangerous category must be forced to blocking/schema.
        assert actions[0]["severity"] == SEVERITY_BLOCKING
        assert actions[0]["severity_source"] == SEVERITY_SOURCE_SCHEMA
        assert actions[0]["id"] == "ns-01"

    def test_multiple_actions_all_normalized(self) -> None:
        """A mix of dangerous and advisory actions all get normalized."""
        raw_actions = [
            _ns_action(
                id="ns-advisory",
                category="completeness",
                severity=SEVERITY_ADVISORY,
            ),
            _ns_action(
                id="ns-dangerous",
                category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[2],
                severity=SEVERITY_ADVISORY,
            ),
        ]
        signals = _minimal_signals()
        payload = _minimal_gate_payload(north_star_actions=raw_actions)
        artifact = build_gate_artifact(signals, payload, override_forced=False)

        actions = artifact["north_star_actions"]
        assert len(actions) == 2

        advisory = next(a for a in actions if a["id"] == "ns-advisory")
        dangerous = next(a for a in actions if a["id"] == "ns-dangerous")

        assert advisory["severity"] == SEVERITY_ADVISORY
        assert dangerous["severity"] == SEVERITY_BLOCKING
        assert dangerous["severity_source"] == SEVERITY_SOURCE_SCHEMA

    def test_null_north_star_actions_fails_closed(self) -> None:
        """An invalid null required field cannot become an empty list."""
        signals = _minimal_signals()
        payload = _minimal_gate_payload(north_star_actions=None)
        with pytest.raises(RuntimeError, match="north_star_actions must be a list"):
            build_gate_artifact(signals, payload, override_forced=False)

    def test_normalized_actions_include_all_required_fields(self) -> None:
        """Normalized actions carry id, concern, category, action_type, severity,
        severity_source, and evidence."""
        raw_action = _ns_action(
            id="ns-full",
            question_id="q-1",
            question="Is there a rollback?",
            plan_refs=["plan.md#step-3"],
            required_change="Add rollback step.",
        )
        signals = _minimal_signals()
        payload = _minimal_gate_payload(north_star_actions=[raw_action])
        artifact = build_gate_artifact(signals, payload, override_forced=False)

        actions = artifact["north_star_actions"]
        assert len(actions) == 1
        a = actions[0]
        assert a["id"] == "ns-full"
        assert a["concern"] == raw_action["concern"]
        assert a["category"] == "completeness"
        assert a["action_type"] == "change_plan"
        assert a["evidence"] == raw_action["evidence"]
        assert a.get("question_id") == "q-1"
        assert a.get("question") == "Is there a rollback?"
        assert a.get("plan_refs") == ["plan.md#step-3"]
        assert a.get("required_change") == "Add rollback step."


# --------------------------------------------------------------------------- #
# Gate carry tests — normalized actions survive into gate_carry.json
# --------------------------------------------------------------------------- #


class TestGateCarryPreservesNormalizedActions:
    """Prove that ``_build_gate_carry`` carries North Star actions forward."""

    def test_carry_includes_north_star_actions_from_gate_summary(self) -> None:
        """When gate_summary already has north_star_actions, carry preserves them."""
        normalized_actions = [
            normalize_north_star_action(
                _ns_action(id="ns-c1", category="correctness", severity=SEVERITY_BLOCKING)
            ),
        ]
        gate_summary: dict[str, Any] = {
            "recommendation": "ITERATE",
            "passed": False,
            "rationale": "Needs work.",
            "signals_assessment": "Needs work.",
            "settled_decisions": [],
            "warnings": [],
            "accepted_tradeoffs": [],
            "orchestrator_guidance": "Revise the plan.",
            "unresolved_flags": [],
            "flag_resolutions": [],
            "north_star_actions": normalized_actions,
        }
        carry = _build_gate_carry(gate_summary, iteration=2)
        assert "north_star_actions" in carry
        assert carry["north_star_actions"] == normalized_actions

    def test_carry_missing_north_star_actions_fails_closed(self) -> None:
        """Carry persistence cannot hide an absent required action list."""
        gate_summary: dict[str, Any] = {
            "recommendation": "PROCEED",
            "passed": True,
            "rationale": "Good.",
            "signals_assessment": "Good.",
            "settled_decisions": [],
            "warnings": [],
            "accepted_tradeoffs": [],
            "orchestrator_guidance": "Proceed to finalize.",
            "unresolved_flags": [],
            "flag_resolutions": [],
        }
        with pytest.raises(RuntimeError, match="north_star_actions"):
            _build_gate_carry(gate_summary, iteration=1)

    def test_carry_preserves_severity_source(self) -> None:
        """Blocking actions with schema-sourced severity survive carry."""
        normalized_actions = [
            normalize_north_star_action(
                _ns_action(
                    id="ns-block",
                    category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[1],
                    severity=SEVERITY_ADVISORY,
                )
            ),
        ]
        gate_summary: dict[str, Any] = {
            "recommendation": "ITERATE",
            "passed": False,
            "rationale": "",
            "signals_assessment": "",
            "settled_decisions": [],
            "warnings": [],
            "accepted_tradeoffs": [],
            "orchestrator_guidance": "",
            "unresolved_flags": [],
            "flag_resolutions": [],
            "north_star_actions": normalized_actions,
        }
        carry = _build_gate_carry(gate_summary, iteration=2)
        carried = carry["north_star_actions"]
        assert len(carried) == 1
        assert carried[0]["severity"] == SEVERITY_BLOCKING
        assert carried[0]["severity_source"] == SEVERITY_SOURCE_SCHEMA

    def test_carry_preserves_iteration_and_version(self) -> None:
        """carry includes iteration and version metadata."""
        gate_summary: dict[str, Any] = {
            "recommendation": "ITERATE",
            "passed": False,
            "rationale": "",
            "signals_assessment": "",
            "settled_decisions": [],
            "warnings": [],
            "accepted_tradeoffs": [],
            "orchestrator_guidance": "",
            "unresolved_flags": [],
            "flag_resolutions": [],
            "north_star_actions": [],
        }
        carry = _build_gate_carry(gate_summary, iteration=3)
        assert carry["iteration"] == 3
        assert carry["version"] == 1

    def test_carry_normalized_actions_are_not_dropped(self) -> None:
        """Multiple normalized actions all survive the carry round-trip."""
        raw_actions = [
            _ns_action(id=f"ns-multi-{i}", category="completeness") for i in range(5)
        ]
        normalized = normalize_north_star_actions(raw_actions)
        gate_summary: dict[str, Any] = {
            "recommendation": "ITERATE",
            "passed": False,
            "rationale": "",
            "signals_assessment": "",
            "settled_decisions": [],
            "warnings": [],
            "accepted_tradeoffs": [],
            "orchestrator_guidance": "",
            "unresolved_flags": [],
            "flag_resolutions": [],
            "north_star_actions": normalized,
        }
        carry = _build_gate_carry(gate_summary, iteration=2)
        assert len(carry["north_star_actions"]) == 5
        ids = {a["id"] for a in carry["north_star_actions"]}
        assert ids == {f"ns-multi-{i}" for i in range(5)}


# --------------------------------------------------------------------------- #
# Carried actions reader — gate_carry.json then gate.json fallback
# --------------------------------------------------------------------------- #


class TestCarriedNorthStarActionsReader:
    """Prove ``_carried_north_star_actions`` reads actions from both sources."""

    def test_reads_from_gate_carry_when_present(self) -> None:
        """When gate_carry.json exists, it is the preferred source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            carry_path = plan_dir / "gate_carry.json"
            actions = [
                _ns_action(
                    id="ns-from-carry",
                    category="completeness",
                    severity=SEVERITY_BLOCKING,
                    evidence="Evidence from carry.",
                ),
            ]
            carry_data = {"north_star_actions": actions, "recommendation": "ITERATE"}
            carry_path.write_text(json.dumps(carry_data), encoding="utf-8")

            # Also write a gate.json with different actions to prove preference.
            gate_path = plan_dir / "gate.json"
            gate_data = {
                "north_star_actions": [
                    _ns_action(id="ns-from-gate", category="correctness"),
                ]
            }
            gate_path.write_text(json.dumps(gate_data), encoding="utf-8")

            result = _carried_north_star_actions(plan_dir)
            assert len(result) == 1
            assert result[0]["id"] == "ns-from-carry"

    def test_falls_back_to_gate_json_when_carry_missing(self) -> None:
        """When gate_carry.json is absent, gate.json is the fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            gate_path = plan_dir / "gate.json"
            actions = [
                _ns_action(
                    id="ns-from-gate-only",
                    category="correctness",
                    severity=SEVERITY_ADVISORY,
                ),
            ]
            gate_data = {"north_star_actions": actions}
            gate_path.write_text(json.dumps(gate_data), encoding="utf-8")

            result = _carried_north_star_actions(plan_dir)
            assert len(result) == 1
            assert result[0]["id"] == "ns-from-gate-only"

    def test_explicit_empty_carry_is_authoritative(self) -> None:
        """An explicit empty carry must not revive stale gate actions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            carry_path = plan_dir / "gate_carry.json"
            carry_data = {"north_star_actions": [], "recommendation": "ITERATE"}
            carry_path.write_text(json.dumps(carry_data), encoding="utf-8")

            gate_path = plan_dir / "gate.json"
            gate_data = {
                "north_star_actions": [
                    _ns_action(id="ns-from-gate-fallback", category="completeness"),
                ]
            }
            gate_path.write_text(json.dumps(gate_data), encoding="utf-8")

            result = _carried_north_star_actions(plan_dir)
            assert result == []

    def test_returns_empty_list_when_both_files_missing(self) -> None:
        """When neither gate_carry.json nor gate.json exist, returns []."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            result = _carried_north_star_actions(plan_dir)
            assert result == []

    def test_missing_required_actions_in_carry_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            (plan_dir / "gate_carry.json").write_text(
                json.dumps({"recommendation": "ITERATE"}), encoding="utf-8"
            )
            (plan_dir / "gate.json").write_text(
                json.dumps({"recommendation": "ITERATE"}), encoding="utf-8"
            )
            with pytest.raises(NorthStarActionValidationError, match="missing required"):
                _carried_north_star_actions(plan_dir)

    def test_carry_with_null_actions_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            carry_path = plan_dir / "gate_carry.json"
            carry_data = {"north_star_actions": None, "recommendation": "ITERATE"}
            carry_path.write_text(json.dumps(carry_data), encoding="utf-8")

            gate_path = plan_dir / "gate.json"
            gate_data = {
                "north_star_actions": [
                    _ns_action(id="ns-gate-from-null-carry", category="scope"),
                ]
            }
            gate_path.write_text(json.dumps(gate_data), encoding="utf-8")

            with pytest.raises(NorthStarActionValidationError, match="must be a list"):
                _carried_north_star_actions(plan_dir)


# --------------------------------------------------------------------------- #
# Revise prompt tests — carried North Star actions appear in prompt context
# --------------------------------------------------------------------------- #


class TestRevisePromptIncludesNorthStarActions:
    """Prove that the revise prompt renders carried North Star actions.

    We test the renderer (_build_north_star_actions_block) directly because
    the full _revise_prompt function requires a complete plan directory with
    all supporting files (plan, meta, gate, flags, etc.).
    """

    def _import_block_builder(self) -> Any:
        from arnold_pipelines.megaplan.prompts.critique import _build_north_star_actions_block
        return _build_north_star_actions_block

    def test_empty_actions_produces_empty_string(self) -> None:
        """When there are no carried actions, the block is empty."""
        builder = self._import_block_builder()
        block = builder([])
        assert block == ""

    def test_single_action_rendered_with_type_and_severity(self) -> None:
        """A single carried action is rendered with id, category, type, severity."""
        builder = self._import_block_builder()
        action = normalize_north_star_action(
            _ns_action(
                id="ns-r1",
                concern="Add input validation.",
                category="correctness",
                action_type="add_gate",
            )
        )
        block = builder([action])
        assert "ns-r1" in block
        assert "correctness" in block
        assert "add_gate" in block
        assert "Add input validation" in block
        # Must include instructions for all action types.
        assert "Add an explicit gate requirement" in block

    def test_blocking_action_shows_blocking_severity(self) -> None:
        """A blocking action shows severity=blocking in the prompt."""
        builder = self._import_block_builder()
        action = normalize_north_star_action(
            _ns_action(
                id="ns-block-r",
                category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[3],
                evidence="Target narrowed without authorization.",
            )
        )
        block = builder([action])
        assert SEVERITY_BLOCKING in block

    def test_multiple_actions_all_listed(self) -> None:
        """Multiple carried actions are all listed in the prompt."""
        builder = self._import_block_builder()
        actions = normalize_north_star_actions([
            _ns_action(id=f"ns-bulk-{i}", category="completeness") for i in range(3)
        ])
        block = builder(actions)
        for i in range(3):
            assert f"ns-bulk-{i}" in block

    def test_evidence_truncated_when_long(self) -> None:
        """Long evidence strings are truncated in the prompt."""
        builder = self._import_block_builder()
        long_evidence = "x" * 500
        action = normalize_north_star_action(
            _ns_action(id="ns-long", evidence=long_evidence)
        )
        block = builder([action])
        # Evidence over 300 chars should be truncated with "..."
        assert len(long_evidence) > 300
        assert block.count("...") >= 1

    def test_required_change_rendered_when_present(self) -> None:
        """required_change is rendered in the prompt when provided."""
        builder = self._import_block_builder()
        action = normalize_north_star_action(
            _ns_action(
                id="ns-req-change",
                category="completeness",
                required_change="Add a CI pipeline validation step.",
            )
        )
        block = builder([action])
        assert "required_change: Add a CI pipeline validation step" in block

    def test_plan_refs_rendered_when_present(self) -> None:
        """plan_refs is rendered in the prompt when non-empty."""
        builder = self._import_block_builder()
        action = normalize_north_star_action(
            _ns_action(
                id="ns-plan-refs",
                plan_refs=["plan.md#step-3", "README.md#api"],
            )
        )
        block = builder([action])
        assert "plan_refs: plan.md#step-3, README.md#api" in block

    def test_add_human_halt_instruction_is_rendered(self) -> None:
        """When add_human_halt is present, its instruction tells worker to halt."""
        builder = self._import_block_builder()
        action = normalize_north_star_action(
            _ns_action(
                id="ns-halt",
                action_type="add_human_halt",
                evidence="Human decision required.",
            )
        )
        block = builder([action])
        assert "add_human_halt" in block
        assert "halted" in block.lower()

    def test_north_star_actions_addressed_output_schema_mentioned(self) -> None:
        """Prompt instructs worker to record results in north_star_actions_addressed."""
        builder = self._import_block_builder()
        action = normalize_north_star_action(
            _ns_action(id="ns-addressed-test")
        )
        block = builder([action])
        assert "north_star_actions_addressed" in block
        assert "action_id" in block
        assert "resolution" in block


# --------------------------------------------------------------------------- #
# Pre-worker halt guard tests
# --------------------------------------------------------------------------- #


class TestReviseNorthStarHaltActions:
    """Prove ``_revise_north_star_halt_actions`` correctly identifies actions
    that must halt the revise worker before invocation."""

    def test_add_human_halt_blocking_triggers_halt(self) -> None:
        """A blocking add_human_halt action always triggers a halt."""
        action = _ns_action(
            id="ns-halt-1",
            action_type="add_human_halt",
            severity=SEVERITY_BLOCKING,
            severity_source=SEVERITY_SOURCE_WORKER,
            evidence="Needs human decision.",
        )
        halted = _revise_north_star_halt_actions([action])
        assert len(halted) == 1
        assert halted[0]["id"] == "ns-halt-1"

    def test_add_human_halt_advisory_does_not_trigger_halt(self) -> None:
        """An advisory add_human_halt does NOT trigger the halt (only blocking)."""
        action = _ns_action(
            id="ns-halt-advisory",
            action_type="add_human_halt",
            severity=SEVERITY_ADVISORY,
        )
        halted = _revise_north_star_halt_actions([action])
        assert len(halted) == 0

    def test_blocking_unmappable_action_type_halts(self) -> None:
        """A blocking action whose action_type is not in the mappable set halts."""
        # add_human_halt is already tested; use an action_type that doesn't exist
        # in NORTH_STAR_ACTION_TYPES at all. This simulates a corrupted/malformed
        # action that passed normalization but has an unknown type (purely for test).
        action = dict(
            _ns_action(
                id="ns-unknown-type",
                action_type="unknown_type",
                severity=SEVERITY_BLOCKING,
                severity_source=SEVERITY_SOURCE_WORKER,
                evidence="Unknown action.",
            )
        )
        # Must use a dict directly since _ns_action would reject this action_type
        # during normalization. We skip normalization for this edge case.
        halted = _revise_north_star_halt_actions([action])
        assert len(halted) == 1
        assert halted[0]["id"] == "ns-unknown-type"

    def test_blocking_mappable_action_does_not_halt(self) -> None:
        """A blocking change_plan action with plan_refs does NOT halt."""
        action = normalize_north_star_action(
            _ns_action(
                id="ns-mappable",
                category="correctness",
                action_type="change_plan",
                severity=SEVERITY_BLOCKING,
                severity_source=SEVERITY_SOURCE_WORKER,
                evidence="Concrete concern.",
                plan_refs=["plan.md#phase-2"],
            )
        )
        halted = _revise_north_star_halt_actions([action])
        assert len(halted) == 0

    def test_dangerous_category_without_concrete_target_halts(self) -> None:
        """A dangerous-category blocking action WITHOUT plan_refs or required_change halts."""
        action = normalize_north_star_action(
            _ns_action(
                id="ns-dang-no-target",
                category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[4],
                evidence="Blocking but no target given.",
            )
        )
        halted = _revise_north_star_halt_actions([action])
        assert len(halted) == 1
        assert halted[0]["id"] == "ns-dang-no-target"

    def test_dangerous_category_with_plan_refs_does_not_halt(self) -> None:
        """A dangerous-category blocking action WITH plan_refs passes."""
        action = normalize_north_star_action(
            _ns_action(
                id="ns-dang-with-refs",
                category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[0],
                evidence="Route authority concern.",
                plan_refs=["plan.md"],
            )
        )
        halted = _revise_north_star_halt_actions([action])
        assert len(halted) == 0

    def test_dangerous_category_with_required_change_does_not_halt(self) -> None:
        """A dangerous-category blocking action WITH required_change passes."""
        action = normalize_north_star_action(
            _ns_action(
                id="ns-dang-with-change",
                category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[1],
                evidence="Baseline drift.",
                required_change="Lock baseline in automation gate.",
            )
        )
        halted = _revise_north_star_halt_actions([action])
        assert len(halted) == 0

    def test_dangerous_category_with_empty_plan_refs_halts(self) -> None:
        """Empty plan_refs list does not count as a concrete target."""
        action = normalize_north_star_action(
            _ns_action(
                id="ns-empty-refs",
                category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[2],
                evidence="Row exemption concern.",
                plan_refs=[],
            )
        )
        halted = _revise_north_star_halt_actions([action])
        assert len(halted) == 1
        assert halted[0]["id"] == "ns-empty-refs"

    def test_dangerous_category_with_whitespace_required_change_halts(self) -> None:
        """A whitespace-only required_change is not a concrete target."""
        action = normalize_north_star_action(
            _ns_action(
                id="ns-ws-change",
                category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[3],
                evidence="Target narrowing.",
                required_change="   ",
            )
        )
        halted = _revise_north_star_halt_actions([action])
        assert len(halted) == 1
        assert halted[0]["id"] == "ns-ws-change"

    def test_dangerous_category_with_whitespace_only_plan_refs_halts(self) -> None:
        """A plan_refs list with a single whitespace-only ref is not concrete.

        Mirrors the post-revise concrete-ref rule: at least one ref must be a
        non-blank string. ``plan_refs=['   ']`` must halt, even though it is a
        truthy non-empty list.
        """
        action = normalize_north_star_action(
            _ns_action(
                id="ns-ws-refs",
                category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[5],
                evidence="Live plan topology resume risk concern.",
                plan_refs=["   "],
            )
        )
        # Normalization preserves whitespace refs verbatim (no stripping).
        assert action.get("plan_refs") == ["   "]
        halted = _revise_north_star_halt_actions([action])
        assert len(halted) == 1
        assert halted[0]["id"] == "ns-ws-refs"

    def test_dangerous_category_with_all_blank_plan_refs_halts(self) -> None:
        """Every-blank plan_refs (spaces, tabs, empty) is not concrete."""
        action = normalize_north_star_action(
            _ns_action(
                id="ns-all-blank-refs",
                category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[0],
                evidence="Route authority bypass.",
                plan_refs=["   ", "\t", ""],
            )
        )
        halted = _revise_north_star_halt_actions([action])
        assert len(halted) == 1
        assert halted[0]["id"] == "ns-all-blank-refs"

    def test_dangerous_category_with_mixed_blank_and_concrete_plan_refs_passes(self) -> None:
        """At least one non-blank ref is sufficient even when blanks are mixed in."""
        action = normalize_north_star_action(
            _ns_action(
                id="ns-mixed-refs",
                category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[1],
                evidence="Baseline drift concern.",
                plan_refs=["   ", "plan.md#baselines", ""],
            )
        )
        halted = _revise_north_star_halt_actions([action])
        assert len(halted) == 0

    def test_non_dangerous_blocking_without_target_does_not_halt(self) -> None:
        """A non-dangerous blocking action without plan_refs still passes
        (it's the worker's job to find the target)."""
        action = normalize_north_star_action(
            _ns_action(
                id="ns-non-danger",
                category="correctness",
                severity=SEVERITY_BLOCKING,
                severity_source=SEVERITY_SOURCE_WORKER,
                evidence="Logic error in step 2.",
            )
        )
        halted = _revise_north_star_halt_actions([action])
        assert len(halted) == 0

    def test_advisory_action_never_halts(self) -> None:
        """Advisory actions of any type never trigger halt.

        Uses only non-dangerous categories so normalization does not force the
        actions to blocking/schema. A dangerous category advisory would be
        upgraded to blocking and could halt if lacking a concrete target."""
        actions = normalize_north_star_actions([
            _ns_action(id="ns-adv-1", action_type="add_human_halt", severity=SEVERITY_ADVISORY),
            _ns_action(
                id="ns-adv-2",
                action_type="change_plan",
                severity=SEVERITY_ADVISORY,
                category="completeness",
            ),
            _ns_action(
                id="ns-adv-3",
                action_type="dead_delete",
                severity=SEVERITY_ADVISORY,
                category="conventions",
            ),
        ])
        halted = _revise_north_star_halt_actions(actions)
        assert len(halted) == 0

    def test_multiple_halt_actions_all_returned(self) -> None:
        """When multiple halt-trigger actions are present, all are returned."""
        actions: list[dict[str, Any]] = [
            normalize_north_star_action(
                _ns_action(
                    id="ns-halt-a",
                    action_type="add_human_halt",
                    severity=SEVERITY_BLOCKING,
                    severity_source=SEVERITY_SOURCE_WORKER,
                    evidence="A needs human.",
                )
            ),
            normalize_north_star_action(
                _ns_action(
                    id="ns-halt-b",
                    category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[5],
                    evidence="B: no target.",
                )
            ),
            normalize_north_star_action(
                _ns_action(
                    id="ns-mappable",
                    category="correctness",
                    severity=SEVERITY_BLOCKING,
                    severity_source=SEVERITY_SOURCE_WORKER,
                    evidence="Mappable.",
                    plan_refs=["plan.md"],
                )
            ),
        ]
        halted = _revise_north_star_halt_actions(actions)
        assert len(halted) == 2
        halted_ids = {a["id"] for a in halted}
        assert halted_ids == {"ns-halt-a", "ns-halt-b"}

    def test_mixed_advisory_and_blocking_only_halts_blocking(self) -> None:
        """Advisory add_human_halt + blocking add_human_halt: only blocking."""
        actions = normalize_north_star_actions([
            _ns_action(
                id="ns-adv-halt",
                action_type="add_human_halt",
                severity=SEVERITY_ADVISORY,
            ),
            _ns_action(
                id="ns-block-halt",
                action_type="add_human_halt",
                severity=SEVERITY_BLOCKING,
                severity_source=SEVERITY_SOURCE_WORKER,
                evidence="Real halt.",
            ),
        ])
        halted = _revise_north_star_halt_actions(actions)
        assert len(halted) == 1
        assert halted[0]["id"] == "ns-block-halt"

    def test_all_concrete_mappable_types_pass(self) -> None:
        """All 5 concrete mappable types (change_plan, add_gate, add_scenario,
        add_checker, dead_delete) pass when non-dangerous blocking."""
        mappable_types = ["change_plan", "add_gate", "add_scenario", "add_checker", "dead_delete"]
        actions = [
            normalize_north_star_action(
                _ns_action(
                    id=f"ns-{t}",
                    action_type=t,
                    category="completeness",
                    severity=SEVERITY_BLOCKING,
                    severity_source=SEVERITY_SOURCE_WORKER,
                    evidence=f"Evidence for {t}.",
                    plan_refs=["plan.md"],
                )
            )
            for t in mappable_types
        ]
        halted = _revise_north_star_halt_actions(actions)
        assert len(halted) == 0, f"Expected no halts but got: {[a['id'] for a in halted]}"


# --------------------------------------------------------------------------- #
# End-to-end gate to carry to halt integration
# --------------------------------------------------------------------------- #


class TestGateToReviseEndToEnd:
    """Integration-style tests crossing gate artifact, carry, and halt guard."""

    def test_gate_artifact_to_carry_to_reader_round_trip(self) -> None:
        """Build gate artifact, write carry, read it back — actions survive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)

            # Build gate artifact with normalized actions
            raw_actions = [
                _ns_action(
                    id="ns-e2e-1",
                    category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[0],
                    evidence="Dangerous action from gate.",
                ),
                _ns_action(
                    id="ns-e2e-2",
                    category="completeness",
                    severity=SEVERITY_ADVISORY,
                ),
            ]
            signals = _minimal_signals()
            payload = _minimal_gate_payload(north_star_actions=raw_actions)
            artifact = build_gate_artifact(signals, payload, override_forced=False)

            # Build carry from the artifact
            carry = _build_gate_carry(artifact, iteration=2)

            # Write carry to disk
            (plan_dir / "gate_carry.json").write_text(
                json.dumps(carry), encoding="utf-8"
            )

            # Also write gate.json for completeness
            (plan_dir / "gate.json").write_text(
                json.dumps(artifact), encoding="utf-8"
            )

            # Read back with _carried_north_star_actions
            carried = _carried_north_star_actions(plan_dir)
            assert len(carried) == 2

            # Check dangerous action is still blocking
            dangerous = next(a for a in carried if a["id"] == "ns-e2e-1")
            assert dangerous["severity"] == SEVERITY_BLOCKING
            assert dangerous["severity_source"] == SEVERITY_SOURCE_SCHEMA

            # Check advisory action is still advisory
            advisory = next(a for a in carried if a["id"] == "ns-e2e-2")
            assert advisory["severity"] == SEVERITY_ADVISORY

    def test_full_halt_guard_with_carried_actions(self) -> None:
        """Carried actions with add_human_halt trigger the halt guard."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            # Create a gate.json with a human-halt blocking action
            actions = [
                _ns_action(
                    id="ns-human-halt",
                    action_type="add_human_halt",
                    severity=SEVERITY_BLOCKING,
                    severity_source=SEVERITY_SOURCE_WORKER,
                    evidence="Requires human sign-off.",
                ),
            ]
            gate_data = {"north_star_actions": actions, "recommendation": "ITERATE"}
            (plan_dir / "gate.json").write_text(json.dumps(gate_data), encoding="utf-8")

            carried = _carried_north_star_actions(plan_dir)
            halted = _revise_north_star_halt_actions(carried)
            assert len(halted) == 1
            assert halted[0]["action_type"] == "add_human_halt"

    def test_gate_carry_survives_schema_authority_roundtrip(self) -> None:
        """Dangerous category actions forced to blocking in gate.json stay
        blocking through carry and halt guard."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)

            # Build a full gate artifact with dangerous category action that
            # was labeled advisory by the worker — normalization must fix it.
            raw_action = _ns_action(
                id="ns-wrong-label",
                category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[0],
                severity=SEVERITY_ADVISORY,
                severity_source=SEVERITY_SOURCE_WORKER,
                evidence="Route authority bypass.",
                plan_refs=["deploy.yaml"],
            )
            signals = _minimal_signals()
            payload = _minimal_gate_payload(north_star_actions=[raw_action])
            artifact = build_gate_artifact(signals, payload, override_forced=False)

            # Write gate.json, build carry, write carry
            (plan_dir / "gate.json").write_text(json.dumps(artifact), encoding="utf-8")
            carry = _build_gate_carry(artifact, iteration=1)
            (plan_dir / "gate_carry.json").write_text(json.dumps(carry), encoding="utf-8")

            # Read back and verify
            carried = _carried_north_star_actions(plan_dir)
            assert len(carried) == 1
            assert carried[0]["severity"] == SEVERITY_BLOCKING
            assert carried[0]["severity_source"] == SEVERITY_SOURCE_SCHEMA

            # With plan_refs present, this dangerous action should NOT halt
            halted = _revise_north_star_halt_actions(carried)
            assert len(halted) == 0

    def test_dangerous_action_without_target_halts_end_to_end(self) -> None:
        """Build gate artifact with dangerous action lacking target,
        carry it through, verify halt guard catches it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)

            raw_action = _ns_action(
                id="ns-no-target",
                category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[4],
                evidence="Generated conformance authority bypass.",
            )
            signals = _minimal_signals()
            payload = _minimal_gate_payload(north_star_actions=[raw_action])
            artifact = build_gate_artifact(signals, payload, override_forced=False)

            (plan_dir / "gate.json").write_text(json.dumps(artifact), encoding="utf-8")
            carry = _build_gate_carry(artifact, iteration=1)
            (plan_dir / "gate_carry.json").write_text(json.dumps(carry), encoding="utf-8")

            carried = _carried_north_star_actions(plan_dir)
            assert len(carried) == 1
            assert carried[0]["severity"] == SEVERITY_BLOCKING

            halted = _revise_north_star_halt_actions(carried)
            assert len(halted) == 1
            assert halted[0]["id"] == "ns-no-target"


# --------------------------------------------------------------------------- #
# Blocking action validation — evidence required
# --------------------------------------------------------------------------- #


class TestBlockingActionEvidenceValidation:
    """Prove blocking actions require non-empty evidence at normalization time,
    which affects what reaches the gate artifact."""

    def test_blocking_action_without_evidence_raises(self) -> None:
        """A blocking action (dangerous category) without evidence is rejected."""
        raw_action = _ns_action(
            id="ns-no-evidence",
            category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[0],
            evidence="",  # empty
        )
        with pytest.raises(NorthStarActionValidationError, match="evidence"):
            normalize_north_star_action(raw_action)

    def test_blocking_action_with_missing_evidence_raises(self) -> None:
        """A blocking action without an evidence key raises."""
        raw_action = _ns_action(
            id="ns-missing-ev",
            category=sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[0],
        )
        del raw_action["evidence"]
        with pytest.raises(NorthStarActionValidationError, match="evidence"):
            normalize_north_star_action(raw_action)

    def test_advisory_action_without_evidence_is_ok(self) -> None:
        """An advisory action without evidence normalizes fine."""
        raw_action = _ns_action(
            id="ns-adv-no-ev",
            evidence="",
        )
        result = normalize_north_star_action(raw_action)
        assert result["severity"] == SEVERITY_ADVISORY
