"""Handler behavioral tests.

These tests exercise relocated product handler helpers directly with controlled
inputs. They are cheap, do not require LLM calls, and lock behavioral semantics
that must survive relocation within ``arnold_pipelines.megaplan``.
"""

from __future__ import annotations

import argparse
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.handlers.override import (
    _override_replan,
    _override_set_model,
    _override_set_profile,
)
from arnold_pipelines.megaplan.handlers.structured_output import (
    _strip_unknown_keys,
    classify_scratch,
    promote_scratch,
)
from arnold_pipelines.megaplan.workers import WorkerResult


def test_evaluator_promotion_does_not_erase_nonempty_worker_verdict() -> None:
    from arnold_pipelines.megaplan.orchestration.critique_runtime import (
        _prefer_nonempty_evaluator_payload,
    )

    worker = {"selections": [{"check_id": "correctness"}], "skipped": []}
    promoted_empty = {"selections": [], "skipped": [{"check_id": "correctness"}]}

    assert _prefer_nonempty_evaluator_payload(worker, promoted_empty) == worker


class TestAdaptiveCritiqueRouting:
    def test_complexity_seven_routes_when_the_profile_declares_tier_seven(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from arnold_pipelines.megaplan.execute import batch
        from arnold_pipelines.megaplan.handlers.critique import _apply_adaptive_critique_routing

        def fake_resolve_tier_spec(args: argparse.Namespace, spec: str, *, phase: str = "execute"):
            assert phase == "critique"
            agent, model = spec.split(":", 1)
            return agent, "fresh", model

        monkeypatch.setattr(batch, "_resolve_tier_spec", fake_resolve_tier_spec)
        checks = [{"id": "correctness", "question": "Correct?", "complexity": 7}]

        assert _apply_adaptive_critique_routing(
            {"config": {}},
            argparse.Namespace(tier_models={"critique": {7: "codex:gpt-5.5"}}),
            checks,
        ) is None

        assert checks[0]["_routing_tier"] == 7
        assert checks[0]["_routing_selected_spec"] == "codex:gpt-5.5"

    def test_high_complexity_uses_highest_configured_legacy_critique_tier(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from arnold_pipelines.megaplan.execute import batch
        from arnold_pipelines.megaplan.handlers.critique import _apply_adaptive_critique_routing

        def fake_resolve_tier_spec(args: argparse.Namespace, spec: str, *, phase: str = "execute"):
            assert phase == "critique"
            agent, model = spec.split(":", 1)
            return agent, "fresh", model

        monkeypatch.setattr(batch, "_resolve_tier_spec", fake_resolve_tier_spec)
        checks = [{"id": "correctness", "question": "Correct?", "complexity": 7}]

        assert _apply_adaptive_critique_routing(
            {"config": {}},
            argparse.Namespace(
                tier_models={
                    "critique": {
                        1: "hermes:deepseek:deepseek-v4-flash",
                        2: "hermes:deepseek:deepseek-v4-flash",
                        3: "hermes:deepseek:deepseek-v4-flash",
                        4: "codex:gpt-5.4",
                        5: "codex:gpt-5.5",
                    }
                }
            ),
            checks,
        ) is None

        assert checks[0]["_routing_tier"] == 7
        assert checks[0]["_routing_selected_spec"] == "codex:gpt-5.5"

    @pytest.mark.parametrize("complexity", [0, 11, True, "7"])
    def test_malformed_or_out_of_range_complexity_remains_an_invariant_error(
        self, complexity: object
    ) -> None:
        from arnold_pipelines.megaplan.handlers.critique import _apply_adaptive_critique_routing
        from arnold_pipelines.megaplan.types import CliError

        with pytest.raises(CliError) as exc_info:
            _apply_adaptive_critique_routing(
                {"config": {}},
                argparse.Namespace(tier_models={"critique": {7: "codex:gpt-5.5"}}),
                [{"id": "correctness", "question": "Correct?", "complexity": complexity}],
            )
        assert exc_info.value.code == "critique_complexity_invariant"

    def test_tier_chain_selects_first_spec_for_routing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from arnold_pipelines.megaplan.execute import batch
        from arnold_pipelines.megaplan.handlers.critique import _apply_adaptive_critique_routing

        def fake_resolve_tier_spec(args: argparse.Namespace, spec: str, *, phase: str = "execute"):
            assert phase == "critique"
            agent, model = spec.split(":", 1)
            return agent, "fresh", model

        monkeypatch.setattr(batch, "_resolve_tier_spec", fake_resolve_tier_spec)

        state = {"config": {}}
        args = argparse.Namespace(
            tier_models={
                "critique": {
                    4: ["codex:gpt-5.5", "claude:claude-sonnet-4-6"],
                }
            }
        )
        checks = [{"id": "hard", "question": "Hard?", "complexity": 4}]

        assert _apply_adaptive_critique_routing(state, args, checks) is None

        hard_mode = checks[0]["_resolved_agent_mode"]
        assert hard_mode.agent == "codex"
        assert hard_mode.resolved_model == "gpt-5.5"
        assert checks[0]["_routing_selected_spec"] == "codex:gpt-5.5"
        assert checks[0]["_routing_tier_active"] is True

    def test_tier_models_win_over_global_pin_with_pin_as_missing_tier_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from arnold_pipelines.megaplan.execute import batch
        from arnold_pipelines.megaplan.handlers.critique import _apply_adaptive_critique_routing

        def fake_resolve_tier_spec(args: argparse.Namespace, spec: str, *, phase: str = "execute"):
            assert phase == "critique"
            agent, model = spec.split(":", 1)
            return agent, "fresh", model

        monkeypatch.setattr(batch, "_resolve_tier_spec", fake_resolve_tier_spec)

        state = {
            "config": {
                "critic_model_explicit": True,
                "critic_model": "deepseek-v4-pro",
            }
        }
        args = argparse.Namespace(
            tier_models={
                "critique": {
                    4: "codex:gpt-5.5",
                    2: "hermes:deepseek:deepseek-v4-flash",
                }
            }
        )
        checks = [
            {"id": "hard", "question": "Hard?", "complexity": 4},
            {"id": "fallback", "question": "Fallback?", "complexity": 5},
        ]

        assert _apply_adaptive_critique_routing(state, args, checks) is None

        hard_mode = checks[0]["_resolved_agent_mode"]
        fallback_mode = checks[1]["_resolved_agent_mode"]
        assert hard_mode.agent == "codex"
        assert hard_mode.resolved_model == "gpt-5.5"
        assert checks[0]["_routing_selected_spec"] == "codex:gpt-5.5"
        assert fallback_mode.agent == "hermes"
        assert fallback_mode.model == "deepseek:deepseek-v4-pro"
        assert checks[1]["_routing_selected_spec"] == "critic_model:deepseek-v4-pro"
        assert all(check["_routing_tier_active"] is True for check in checks)

    def test_missing_tier_without_pin_still_fails(self) -> None:
        from arnold_pipelines.megaplan.handlers.critique import _apply_adaptive_critique_routing
        from arnold_pipelines.megaplan.types import CliError

        state = {"config": {}}
        args = argparse.Namespace(tier_models={"critique": {4: "codex:gpt-5.5"}})
        checks = [{"id": "missing", "question": "Missing?", "complexity": 5}]

        with pytest.raises(CliError, match="No tier spec for complexity 5"):
            _apply_adaptive_critique_routing(state, args, checks)

    def test_persisted_state_tier_models_survive_stripped_args(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from arnold_pipelines.megaplan.execute import batch
        from arnold_pipelines.megaplan.handlers.critique import _apply_adaptive_critique_routing

        def fake_resolve_tier_spec(args: argparse.Namespace, spec: str, *, phase: str = "execute"):
            assert phase == "critique"
            agent, model = spec.split(":", 1)
            return agent, "fresh", model

        monkeypatch.setattr(batch, "_resolve_tier_spec", fake_resolve_tier_spec)

        state = {
            "config": {
                "profile": "partnered-5",
                "phase_model": ["critique=hermes:deepseek:deepseek-v4-pro"],
                "tier_models": {
                    "critique": {
                        "3": "hermes:deepseek:deepseek-v4-pro",
                        "4": "codex:gpt-5.4",
                        "5": "codex:gpt-5.5",
                    }
                },
            }
        }
        args = argparse.Namespace(
            profile="partnered-5",
            phase_model=["critique=hermes:deepseek:deepseek-v4-pro"],
            tier_models=None,
        )
        checks = [
            {"id": "scope", "question": "Scope?", "complexity": 3},
            {"id": "correctness", "question": "Correct?", "complexity": 4},
        ]

        assert _apply_adaptive_critique_routing(state, args, checks) is None

        scope_mode = checks[0]["_resolved_agent_mode"]
        correctness_mode = checks[1]["_resolved_agent_mode"]
        assert scope_mode.agent == "hermes"
        assert scope_mode.resolved_model == "deepseek:deepseek-v4-pro"
        assert checks[0]["_routing_selected_spec"] == "hermes:deepseek:deepseek-v4-pro"
        assert correctness_mode.agent == "codex"
        assert correctness_mode.resolved_model == "gpt-5.4"
        assert checks[1]["_routing_selected_spec"] == "codex:gpt-5.4"
        assert all(check["_routing_tier_active"] is True for check in checks)


class TestCritiqueScratchPromotion:
    def test_strip_unknown_keys_drops_injected_commentary(self) -> None:
        payload = {
            "checks": [{"id": "c1"}],
            "flags": [{"id": "f1"}],
            "extra_thoughts": "should be stripped",
            "unknown_key": 123,
        }
        known = frozenset({"checks", "flags", "verified_flag_ids", "disputed_flag_ids"})
        stripped = _strip_unknown_keys(payload, known)
        assert set(stripped.keys()) == {"checks", "flags"}

    def test_promote_scratch_falls_back_to_worker_payload_when_unmodified(self, tmp_path: Path) -> None:
        scratch = tmp_path / "critique_output.json"
        seed = json.dumps({"checks": [], "flags": []})
        scratch.write_text(seed, encoding="utf-8")
        worker = WorkerResult(
            payload={"checks": [{"id": "c1"}], "flags": []},
            raw_output="",
            duration_ms=0,
            cost_usd=0.0,
        )

        status, payload = promote_scratch(
            tmp_path,
            "critique_output.json",
            frozenset({"checks", "flags", "verified_flag_ids", "disputed_flag_ids"}),
            worker,
            seed_json=seed,
            file_fill_instructed=False,
        )
        assert status == "unmodified"
        assert payload == {"checks": [{"id": "c1"}], "flags": []}


class TestGateOutcomeSemantics:
    def test_build_gate_route_signal_proceed_when_passed(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.gate import _build_gate_route_signal
        from arnold_pipelines.megaplan.planning.state import STATE_GATED

        state: dict[str, Any] = {
            "name": "p",
            "iteration": 1,
            "config": {},
            "meta": {},
            "current_state": "critiqued",
        }
        summary = {
            "recommendation": "PROCEED",
            "passed": True,
            "rationale": "ok",
            "signals_assessment": "ok",
            "warnings": [],
            "criteria_check": {},
            "preflight_results": {},
            "unresolved_flags": [],
            "orchestrator_guidance": "",
        }
        outcome = _build_gate_route_signal(
            state, summary, robustness="standard", plan_dir=tmp_path
        )
        assert outcome["result"] == "success"
        assert outcome["route_signal"] == "proceed"
        assert state["current_state"] == STATE_GATED

    def test_build_gate_route_signal_iterate_routes_without_target_names(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.gate import _build_gate_route_signal

        state: dict[str, Any] = {
            "name": "p",
            "iteration": 1,
            "config": {},
            "meta": {},
            "current_state": "critiqued",
            "history": [],
        }
        summary = {
            "recommendation": "ITERATE",
            "passed": False,
            "rationale": "fix it",
            "signals_assessment": "needs work",
            "warnings": [],
            "criteria_check": {},
            "preflight_results": {},
            "unresolved_flags": [],
            "orchestrator_guidance": "",
        }
        outcome = _build_gate_route_signal(
            state, summary, robustness="standard", plan_dir=tmp_path
        )
        assert outcome["result"] == "success"
        assert outcome["route_signal"] == "iterate"

    def test_build_gate_route_signal_retries_gate_for_unresolved_flags(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.gate import _build_gate_route_signal

        state: dict[str, Any] = {
            "name": "p",
            "iteration": 1,
            "config": {},
            "meta": {},
            "current_state": "critiqued",
        }
        summary = {
            "recommendation": "PROCEED",
            "passed": False,
            "rationale": "Looks good",
            "signals_assessment": "ok",
            "warnings": [],
            "criteria_check": {},
            "preflight_results": {},
            "unresolved_flags": [{"id": "f1", "severity": "significant", "status": "open", "concern": "x"}],
            "orchestrator_guidance": "",
        }
        outcome = _build_gate_route_signal(
            state, summary, robustness="standard", plan_dir=tmp_path
        )
        assert outcome["result"] == "unresolved_flags"
        assert outcome["route_signal"] == "retry_gate"
        assert outcome["blocking_unresolved_ids"]


class TestTiebreakerOutcomeSemantics:
    def test_pick_promotes_proceed_signal(self) -> None:
        from arnold_pipelines.megaplan.handlers._tiebreaker_impl import _route_signal_for_tiebreaker_action

        assert _route_signal_for_tiebreaker_action("pick") == "proceed"

    def test_replan_promotes_iterate_signal(self) -> None:
        from arnold_pipelines.megaplan.handlers._tiebreaker_impl import _route_signal_for_tiebreaker_action

        assert _route_signal_for_tiebreaker_action("replan") == "iterate"

    def test_canonical_researcher_bridge_emits_typed_output_without_next_step(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import arnold_pipelines.megaplan.orchestration.tiebreaker_runtime as runtime
        from arnold_pipelines.megaplan.handlers._tiebreaker_impl import handle_tiebreaker_run
        from arnold_pipelines.megaplan.planning.state import STATE_TIEBREAKER_PENDING, STATE_TIEBREAKER_READY

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        (plan_dir / "gate.json").write_text(
            json.dumps({"tiebreaker_question": "Which plan?", "tiebreaker_flag_ids": ["F1"]}),
            encoding="utf-8",
        )
        state = {"name": "demo", "current_state": STATE_TIEBREAKER_PENDING}

        @contextmanager
        def fake_load_plan_locked(root: Path, plan: str | None, *, step: str):
            assert step == "tiebreaker-researcher"
            yield plan_dir, state

        def fake_run_tiebreaker(root: Path, current_plan_dir: Path, current_state: dict[str, Any], args: argparse.Namespace) -> int:
            assert args.question == "Which plan?"
            (current_plan_dir / "tiebreaker_researcher.json").write_text(
                json.dumps({"recommendation": "option-a", "summary": "research"}),
                encoding="utf-8",
            )
            (current_plan_dir / "tiebreaker_challenger.json").write_text(
                json.dumps({"recommendation": "option-b", "summary": "challenge"}),
                encoding="utf-8",
            )
            (current_plan_dir / "tiebreaker.md").write_text("winner", encoding="utf-8")
            return 0

        monkeypatch.setattr(runtime, "load_plan_locked", fake_load_plan_locked)
        monkeypatch.setattr("arnold_pipelines.megaplan._core.workflow_transition", lambda current_state, step: argparse.Namespace(next_state=STATE_TIEBREAKER_READY))
        monkeypatch.setattr("arnold_pipelines.megaplan.prompts.tiebreaker_orchestrator._run_tiebreaker", fake_run_tiebreaker)

        response = handle_tiebreaker_run(
            tmp_path,
            argparse.Namespace(
                plan="demo",
                node_id="tiebreaker_researcher",
                phase_model=[],
                agent=None,
                hermes=None,
                profile=None,
                fresh=False,
                persist=False,
                ephemeral=False,
            ),
        )

        assert response["step"] == "tiebreaker_researcher"
        assert response["route_signal"] == "default"
        assert response["research_findings"]["recommendation"] == "option-a"
        assert "next_step" not in response
        assert state["current_state"] == STATE_TIEBREAKER_READY

    def test_canonical_decision_bridge_emits_lowercase_decision_without_next_step(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import arnold_pipelines.megaplan.orchestration.tiebreaker_runtime as runtime
        from arnold_pipelines.megaplan.handlers._tiebreaker_impl import handle_tiebreaker_decide
        from arnold_pipelines.megaplan.planning.state import STATE_CRITIQUED, STATE_TIEBREAKER_READY

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        (plan_dir / "gate.json").write_text(
            json.dumps({"tiebreaker_question": "Which plan?", "tiebreaker_flag_ids": []}),
            encoding="utf-8",
        )
        (plan_dir / "tiebreaker_researcher.json").write_text(
            json.dumps({"recommendation": "option-a"}),
            encoding="utf-8",
        )
        (plan_dir / "tiebreaker_challenger.json").write_text(
            json.dumps({"recommendation": "option-b"}),
            encoding="utf-8",
        )
        state = {
            "name": "demo",
            "current_state": STATE_TIEBREAKER_READY,
            "plan_versions": [
                {
                    "version": 1,
                    "file": "plan_v1.md",
                    "hash": "sha256:plan",
                    "timestamp": "2026-01-02T03:04:05Z",
                }
            ],
        }
        (plan_dir / "plan_v1.md").write_text("# plan\n", encoding="utf-8")

        @contextmanager
        def fake_load_plan_locked(root: Path, plan: str | None, *, step: str):
            assert step == "tiebreaker-decision"
            yield plan_dir, state

        monkeypatch.setattr(runtime, "load_plan_locked", fake_load_plan_locked)
        monkeypatch.setattr("arnold_pipelines.megaplan.audits.audit_engine.record_tiebreaker_audit", lambda *args, **kwargs: None)

        response = handle_tiebreaker_decide(
            tmp_path,
            argparse.Namespace(
                plan="demo",
                node_id="tiebreaker_decision",
                pick="option-a",
                escalate=False,
                replan=False,
                rationale="pick it",
            ),
        )

        assert response["step"] == "tiebreaker_decision"
        assert response["route_signal"] == "proceed"
        assert response["decision"] == "proceed"
        assert "next_step" not in response
        assert state["current_state"] == STATE_CRITIQUED

    def test_legacy_decision_bridge_resolves_iterate_via_lowered_topology(self) -> None:
        from arnold_pipelines.megaplan.handlers._tiebreaker_impl import _bridge_tiebreaker_next_step

        assert _bridge_tiebreaker_next_step("tiebreaker_decide", "iterate") == "revise"
        assert _bridge_tiebreaker_next_step("tiebreaker_decide", "escalate") == "override add-note"
        assert _bridge_tiebreaker_next_step("tiebreaker_decision", "proceed") is None

    def test_tiebreaker_replan_clears_stale_loop_state_without_promoting_parent_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import arnold_pipelines.megaplan.orchestration.tiebreaker_runtime as runtime
        from arnold_pipelines.megaplan.handlers._tiebreaker_impl import handle_tiebreaker_decide
        from arnold_pipelines.megaplan.planning.state import STATE_CRITIQUED, STATE_TIEBREAKER_READY

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        (plan_dir / "plan_v3.md").write_text("# plan\n", encoding="utf-8")
        (plan_dir / "gate.json").write_text(
            json.dumps({"tiebreaker_question": "Which plan?", "tiebreaker_flag_ids": []}),
            encoding="utf-8",
        )
        (plan_dir / "tiebreaker_researcher.json").write_text(
            json.dumps({"recommendation": "option-a"}),
            encoding="utf-8",
        )
        (plan_dir / "tiebreaker_challenger.json").write_text(
            json.dumps({"recommendation": "option-b"}),
            encoding="utf-8",
        )
        state = {
            "name": "demo",
            "current_state": STATE_TIEBREAKER_READY,
            "iteration": 3,
            "plan_versions": [
                {
                    "version": 3,
                    "file": "plan_v3.md",
                    "hash": "sha256:plan",
                    "timestamp": "2026-01-02T03:04:05Z",
                }
            ],
            "meta": {"tiebreaker_count": 2, "user_approved_gate": True},
            "last_gate": {"recommendation": "TIEBREAKER"},
            "latest_failure": {"kind": "phase_failed"},
            "resume_cursor": {"phase": "gate", "retry_strategy": "rerun_phase"},
            "active_step": {"phase": "tiebreaker_decision"},
        }

        @contextmanager
        def fake_load_plan_locked(root: Path, plan: str | None, *, step: str):
            assert step == "tiebreaker-decision"
            yield plan_dir, state

        monkeypatch.setattr(runtime, "load_plan_locked", fake_load_plan_locked)
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.audits.audit_engine.record_tiebreaker_audit",
            lambda *args, **kwargs: None,
        )

        response = handle_tiebreaker_decide(
            tmp_path,
            argparse.Namespace(
                plan="demo",
                node_id="tiebreaker_decision",
                pick=None,
                escalate=False,
                replan=True,
                rationale="start over with the same latest plan",
            ),
        )

        decision_data = json.loads(
            (plan_dir / "tiebreaker_decisions.json").read_text(encoding="utf-8")
        )

        assert response["route_signal"] == "iterate"
        assert response["decision"] == "iterate"
        assert state["current_state"] == STATE_CRITIQUED
        assert state["last_gate"] == {}
        assert state["meta"] == {}
        assert "latest_failure" not in state
        assert "resume_cursor" not in state
        assert "active_step" not in state
        assert decision_data[-1]["plan_file"] == "plan_v3.md"
        assert decision_data[-1]["plan_iteration"] == 3


class TestTiebreakerScenarioOutcomes:
    """Split-outcome workflow scenarios that coordinate handlers, runtime state,
    and finalization expectations.

    These tests prove that every tiebreaker branch (proceed, iterate,
    escalate, replan) lands on the expected ordinary path and that
    replan rejoins the ordinary planning/critique/gate/finalize path
    without bypassing finalize semantics after a subsequent proceed.
    """

    def test_proceed_decision_positions_for_gate_finalize_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tiebreaker proceed → gate PROCEED → finalize chain intact."""
        import arnold_pipelines.megaplan.orchestration.tiebreaker_runtime as runtime
        from arnold_pipelines.megaplan.handlers._tiebreaker_impl import handle_tiebreaker_decide
        from arnold_pipelines.megaplan.handlers.gate import _build_gate_route_signal
        from arnold_pipelines.megaplan.planning.state import (
            STATE_CRITIQUED,
            STATE_GATED,
            STATE_TIEBREAKER_READY,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        (plan_dir / "gate.json").write_text(
            json.dumps({"tiebreaker_question": "Which plan?", "tiebreaker_flag_ids": []}),
            encoding="utf-8",
        )
        (plan_dir / "tiebreaker_researcher.json").write_text(
            json.dumps({"recommendation": "option-a"}),
            encoding="utf-8",
        )
        (plan_dir / "tiebreaker_challenger.json").write_text(
            json.dumps({"recommendation": "option-b"}),
            encoding="utf-8",
        )
        state = {
            "name": "demo",
            "current_state": STATE_TIEBREAKER_READY,
            "iteration": 1,
            "config": {},
            "meta": {},
            "plan_versions": [
                {
                    "version": 1,
                    "file": "plan_v1.md",
                    "hash": "sha256:plan",
                    "timestamp": "2026-01-02T03:04:05Z",
                }
            ],
        }
        (plan_dir / "plan_v1.md").write_text("# plan\n", encoding="utf-8")

        @contextmanager
        def fake_load_plan_locked(root: Path, plan: str | None, *, step: str):
            assert step == "tiebreaker-decision"
            yield plan_dir, state

        monkeypatch.setattr(runtime, "load_plan_locked", fake_load_plan_locked)
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.audits.audit_engine.record_tiebreaker_audit",
            lambda *args, **kwargs: None,
        )

        # Step 1: Tiebreaker picks "proceed"
        response = handle_tiebreaker_decide(
            tmp_path,
            argparse.Namespace(
                plan="demo",
                node_id="tiebreaker_decision",
                pick="option-a",
                escalate=False,
                replan=False,
                rationale="pick it",
            ),
        )

        assert response["route_signal"] == "proceed"
        assert response["decision"] == "proceed"
        assert state["current_state"] == STATE_CRITIQUED

        # Step 2: Gate with PROCEED — verify finalize path is reachable
        gate_summary = {
            "recommendation": "PROCEED",
            "passed": True,
            "rationale": "ok",
            "signals_assessment": "ok",
            "warnings": [],
            "criteria_check": {},
            "preflight_results": {},
            "unresolved_flags": [],
            "orchestrator_guidance": "",
        }
        gate_outcome = _build_gate_route_signal(
            state, gate_summary, robustness="standard", plan_dir=tmp_path
        )
        assert gate_outcome["result"] == "success"
        assert gate_outcome["route_signal"] == "proceed"
        assert state["current_state"] == STATE_GATED

    def test_iterate_signal_from_replan_positions_for_revise_rejoin(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tiebreaker replan produces iterate signal → state positioned for
        revise → critique → gate. The 'iterate' route_signal is the canonical
        signal emitted when the operator triggers replan."""
        import arnold_pipelines.megaplan.orchestration.tiebreaker_runtime as runtime
        from arnold_pipelines.megaplan.handlers._tiebreaker_impl import handle_tiebreaker_decide
        from arnold_pipelines.megaplan.planning.state import (
            STATE_CRITIQUED,
            STATE_TIEBREAKER_READY,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        (plan_dir / "gate.json").write_text(
            json.dumps({"tiebreaker_question": "Which plan?", "tiebreaker_flag_ids": []}),
            encoding="utf-8",
        )
        (plan_dir / "tiebreaker_researcher.json").write_text(
            json.dumps({"recommendation": "option-a"}),
            encoding="utf-8",
        )
        (plan_dir / "tiebreaker_challenger.json").write_text(
            json.dumps({"recommendation": "option-b"}),
            encoding="utf-8",
        )
        state = {
            "name": "demo",
            "current_state": STATE_TIEBREAKER_READY,
            "iteration": 1,
            "config": {},
            "meta": {},
            "plan_versions": [
                {
                    "version": 1,
                    "file": "plan_v1.md",
                    "hash": "sha256:plan",
                    "timestamp": "2026-01-02T03:04:05Z",
                }
            ],
        }
        (plan_dir / "plan_v1.md").write_text("# plan\n", encoding="utf-8")

        @contextmanager
        def fake_load_plan_locked(root: Path, plan: str | None, *, step: str):
            assert step == "tiebreaker-decision"
            yield plan_dir, state

        monkeypatch.setattr(runtime, "load_plan_locked", fake_load_plan_locked)
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.audits.audit_engine.record_tiebreaker_audit",
            lambda *args, **kwargs: None,
        )

        # replan action → iterate route_signal
        response = handle_tiebreaker_decide(
            tmp_path,
            argparse.Namespace(
                plan="demo",
                node_id="tiebreaker_decision",
                pick=None,
                escalate=False,
                replan=True,
                rationale="iterate back through critique/gate",
            ),
        )

        assert response["route_signal"] == "iterate"
        assert response["decision"] == "iterate"
        assert state["current_state"] == STATE_CRITIQUED
        # The iterate signal resolves to "revise" in the lowered topology,
        # so the workflow is positioned for the normal revise→critique→gate chain.

    def test_escalate_decision_routes_to_awaiting_human(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tiebreaker escalate → AWAITING_HUMAN_VERIFY state."""
        import arnold_pipelines.megaplan.orchestration.tiebreaker_runtime as runtime
        from arnold_pipelines.megaplan.handlers._tiebreaker_impl import handle_tiebreaker_decide
        from arnold_pipelines.megaplan.planning.state import (
            STATE_AWAITING_HUMAN_VERIFY,
            STATE_TIEBREAKER_READY,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        (plan_dir / "gate.json").write_text(
            json.dumps({"tiebreaker_question": "Which plan?", "tiebreaker_flag_ids": []}),
            encoding="utf-8",
        )
        (plan_dir / "tiebreaker_researcher.json").write_text(
            json.dumps({"recommendation": "option-a"}),
            encoding="utf-8",
        )
        (plan_dir / "tiebreaker_challenger.json").write_text(
            json.dumps({"recommendation": "option-b"}),
            encoding="utf-8",
        )
        state = {
            "name": "demo",
            "current_state": STATE_TIEBREAKER_READY,
            "iteration": 1,
            "config": {},
            "meta": {},
            "plan_versions": [
                {
                    "version": 1,
                    "file": "plan_v1.md",
                    "hash": "sha256:plan",
                    "timestamp": "2026-01-02T03:04:05Z",
                }
            ],
        }
        (plan_dir / "plan_v1.md").write_text("# plan\n", encoding="utf-8")

        @contextmanager
        def fake_load_plan_locked(root: Path, plan: str | None, *, step: str):
            assert step == "tiebreaker-decision"
            yield plan_dir, state

        monkeypatch.setattr(runtime, "load_plan_locked", fake_load_plan_locked)
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.audits.audit_engine.record_tiebreaker_audit",
            lambda *args, **kwargs: None,
        )

        response = handle_tiebreaker_decide(
            tmp_path,
            argparse.Namespace(
                plan="demo",
                node_id="tiebreaker_decision",
                pick=None,
                escalate=True,
                replan=False,
                rationale="escalate to human",
            ),
        )

        assert response["route_signal"] == "escalate"
        assert response["decision"] == "escalate"
        assert state["current_state"] == STATE_AWAITING_HUMAN_VERIFY

    def test_tiebreaker_replan_rejoins_ordinary_path_and_does_not_bypass_finalize(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tiebreaker replan → iterate → positioned at critiqued → gate PROCEED →
        finalize path is reachable, not bypassed."""
        import arnold_pipelines.megaplan.orchestration.tiebreaker_runtime as runtime
        from arnold_pipelines.megaplan.handlers._tiebreaker_impl import handle_tiebreaker_decide
        from arnold_pipelines.megaplan.handlers.gate import _build_gate_route_signal
        from arnold_pipelines.megaplan.planning.state import (
            STATE_CRITIQUED,
            STATE_GATED,
            STATE_TIEBREAKER_READY,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        (plan_dir / "plan_v3.md").write_text("# plan\n", encoding="utf-8")
        (plan_dir / "gate.json").write_text(
            json.dumps({"tiebreaker_question": "Which plan?", "tiebreaker_flag_ids": []}),
            encoding="utf-8",
        )
        (plan_dir / "tiebreaker_researcher.json").write_text(
            json.dumps({"recommendation": "option-a"}),
            encoding="utf-8",
        )
        (plan_dir / "tiebreaker_challenger.json").write_text(
            json.dumps({"recommendation": "option-b"}),
            encoding="utf-8",
        )
        state = {
            "name": "demo",
            "current_state": STATE_TIEBREAKER_READY,
            "iteration": 3,
            "config": {},
            "plan_versions": [
                {
                    "version": 3,
                    "file": "plan_v3.md",
                    "hash": "sha256:plan",
                    "timestamp": "2026-01-02T03:04:05Z",
                }
            ],
            "meta": {"tiebreaker_count": 2, "user_approved_gate": True},
            "last_gate": {"recommendation": "TIEBREAKER"},
            "latest_failure": {"kind": "phase_failed"},
            "resume_cursor": {"phase": "gate", "retry_strategy": "rerun_phase"},
            "active_step": {"phase": "tiebreaker_decision"},
        }

        @contextmanager
        def fake_load_plan_locked(root: Path, plan: str | None, *, step: str):
            assert step == "tiebreaker-decision"
            yield plan_dir, state

        monkeypatch.setattr(runtime, "load_plan_locked", fake_load_plan_locked)
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.audits.audit_engine.record_tiebreaker_audit",
            lambda *args, **kwargs: None,
        )

        # Step 1: Tiebreaker replan
        response = handle_tiebreaker_decide(
            tmp_path,
            argparse.Namespace(
                plan="demo",
                node_id="tiebreaker_decision",
                pick=None,
                escalate=False,
                replan=True,
                rationale="start over",
            ),
        )

        assert response["route_signal"] == "iterate"
        assert response["decision"] == "iterate"
        assert state["current_state"] == STATE_CRITIQUED

        # Stale loop state is cleared
        assert state["last_gate"] == {}
        assert state["meta"] == {}
        assert "latest_failure" not in state
        assert "resume_cursor" not in state
        assert "active_step" not in state

        # Step 2: Gate with PROCEED — prove finalize path is reachable, not bypassed
        gate_summary = {
            "recommendation": "PROCEED",
            "passed": True,
            "rationale": "good plan",
            "signals_assessment": "ok",
            "warnings": [],
            "criteria_check": {},
            "preflight_results": {},
            "unresolved_flags": [],
            "orchestrator_guidance": "",
        }
        gate_outcome = _build_gate_route_signal(
            state, gate_summary, robustness="standard", plan_dir=tmp_path
        )
        assert gate_outcome["result"] == "success"
        assert gate_outcome["route_signal"] == "proceed"
        assert state["current_state"] == STATE_GATED
        # The ordinary finalize path follows STATE_GATED — the replan did not
        # bypass finalize semantics.

    def test_override_replan_rejoins_ordinary_planning_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Override replan → STATE_PLANNED, ready for ordinary
        planning → critique → gate → finalize."""
        from arnold_pipelines.megaplan.handlers.override import _override_replan
        from arnold_pipelines.megaplan.planning.state import STATE_PLANNED

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan_v2.md"
        plan_file.write_text("# plan\n", encoding="utf-8")

        state = {
            "name": "demo",
            "current_state": "gated",
            "iteration": 2,
            "config": {},
            "plan_versions": [
                {
                    "version": 2,
                    "file": "plan_v2.md",
                    "hash": "sha256:plan",
                    "timestamp": "2026-01-02T03:04:05Z",
                }
            ],
            "meta": {"tiebreaker_count": 1, "user_approved_gate": True},
            "last_gate": {"recommendation": "ITERATE"},
            "latest_failure": {"kind": "phase_failed"},
            "resume_cursor": {"phase": "execute", "retry_strategy": "fresh_session"},
            "active_step": {"phase": "execute"},
        }

        monkeypatch.setattr(
            "arnold_pipelines.megaplan.handlers.override.save_state_merge_meta",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.handlers.override.now_utc",
            lambda: "2026-01-02T03:04:05Z",
        )
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.handlers.override.latest_plan_path",
            lambda *args, **kwargs: plan_file,
        )
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.handlers.override._warn_best_effort_emit_failure",
            lambda *args, **kwargs: None,
        )

        response = _override_replan(
            tmp_path,
            plan_dir,
            state,
            argparse.Namespace(reason="reset loop", note="preserve current plan"),
        )

        # Override replan positions at STATE_PLANNED
        assert response["state"] == STATE_PLANNED
        assert state["current_state"] == STATE_PLANNED

        # Stale loop state is cleared
        assert state["last_gate"] == {}
        assert "latest_failure" not in state
        assert "resume_cursor" not in state
        assert "active_step" not in state

        # Plan file is preserved
        assert response["plan_file"] == str(plan_file)
        assert state["meta"]["overrides"][-1]["from_state"] == "gated"
        assert state["meta"]["overrides"][-1]["plan_file"] == "plan_v2.md"

        # From STATE_PLANNED, the ordinary path is:
        # planned → critique → gate → (proceed) → finalize → execute → review

    def test_override_replan_then_gate_finalize_does_not_bypass_finalize(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Override replan → planned → critique → gate PROCEED → finalize
        path is reachable. Proves override replan does not bypass finalize
        semantics after a subsequent proceed."""
        from arnold_pipelines.megaplan.handlers.override import _override_replan
        from arnold_pipelines.megaplan.handlers.gate import _build_gate_route_signal
        from arnold_pipelines.megaplan.planning.state import (
            STATE_GATED,
            STATE_PLANNED,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan_v2.md"
        plan_file.write_text("# plan\n", encoding="utf-8")

        state = {
            "name": "demo",
            "current_state": "gated",
            "iteration": 2,
            "config": {},
            "plan_versions": [
                {
                    "version": 2,
                    "file": "plan_v2.md",
                    "hash": "sha256:plan",
                    "timestamp": "2026-01-02T03:04:05Z",
                }
            ],
            "meta": {},
            "last_gate": {"recommendation": "PROCEED"},
            "latest_failure": {"kind": "phase_failed"},
            "resume_cursor": {"phase": "execute", "retry_strategy": "fresh_session"},
            "active_step": {"phase": "execute"},
        }

        monkeypatch.setattr(
            "arnold_pipelines.megaplan.handlers.override.save_state_merge_meta",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.handlers.override.now_utc",
            lambda: "2026-01-02T03:04:05Z",
        )
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.handlers.override.latest_plan_path",
            lambda *args, **kwargs: plan_file,
        )
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.handlers.override._warn_best_effort_emit_failure",
            lambda *args, **kwargs: None,
        )

        # Step 1: Override replan → STATE_PLANNED
        replan_response = _override_replan(
            tmp_path,
            plan_dir,
            state,
            argparse.Namespace(reason="replan from gated", note=None),
        )

        assert replan_response["state"] == STATE_PLANNED
        assert state["current_state"] == STATE_PLANNED
        assert "latest_failure" not in state
        assert "resume_cursor" not in state
        assert "active_step" not in state

        # Step 2: After planning/critique, gate with PROCEED —
        # prove finalize path is reachable, not bypassed
        state["current_state"] = "critiqued"
        gate_summary = {
            "recommendation": "PROCEED",
            "passed": True,
            "rationale": "good plan after replan",
            "signals_assessment": "ok",
            "warnings": [],
            "criteria_check": {},
            "preflight_results": {},
            "unresolved_flags": [],
            "orchestrator_guidance": "",
        }
        gate_outcome = _build_gate_route_signal(
            state, gate_summary, robustness="standard", plan_dir=tmp_path
        )
        assert gate_outcome["result"] == "success"
        assert gate_outcome["route_signal"] == "proceed"
        assert state["current_state"] == STATE_GATED
        # The ordinary finalize path follows — replan did not bypass finalize.


class TestOverrideReplanBehavior:
    def test_override_replan_clears_stale_loop_state_and_records_plan_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan_v2.md"
        plan_file.write_text("# plan\n", encoding="utf-8")

        state = {
            "name": "demo",
            "current_state": "failed",
            "iteration": 2,
            "plan_versions": [
                {
                    "version": 2,
                    "file": "plan_v2.md",
                    "hash": "sha256:plan",
                    "timestamp": "2026-01-02T03:04:05Z",
                }
            ],
            "meta": {"tiebreaker_count": 1, "user_approved_gate": True},
            "last_gate": {"recommendation": "ITERATE"},
            "latest_failure": {"kind": "phase_failed"},
            "resume_cursor": {"phase": "execute", "retry_strategy": "fresh_session"},
            "active_step": {"phase": "execute"},
        }

        monkeypatch.setattr(
            "arnold_pipelines.megaplan.handlers.override.save_state_merge_meta",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.handlers.override.now_utc",
            lambda: "2026-01-02T03:04:05Z",
        )
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.handlers.override.latest_plan_path",
            lambda *args, **kwargs: plan_file,
        )

        response = _override_replan(
            tmp_path,
            plan_dir,
            state,
            argparse.Namespace(reason="reset loop", note="preserve current plan"),
        )

        assert response["state"] == "planned"
        assert response["plan_file"] == str(plan_file)
        assert state["current_state"] == "planned"
        assert state["last_gate"] == {}
        assert state["meta"]["overrides"][-1]["from_state"] == "failed"
        assert state["meta"]["overrides"][-1]["plan_file"] == "plan_v2.md"
        assert state["meta"]["notes"][-1]["note"] == "preserve current plan"
        assert "tiebreaker_count" not in state["meta"]
        assert "user_approved_gate" not in state["meta"]
        assert "latest_failure" not in state
        assert "resume_cursor" not in state
        assert "active_step" not in state


class TestOverrideFallbackChains:
    def test_set_profile_preserves_encoded_phase_model_chain(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import arnold_pipelines.megaplan.profiles as profiles_module

        monkeypatch.setattr(profiles_module, "load_profiles", lambda project_dir=None: {"demo": {}})
        monkeypatch.setattr(
            profiles_module,
            "resolve_profile",
            lambda profile_name, profiles: {
                "execute": [
                    "hermes:deepseek:deepseek-v4-pro",
                    "hermes:fireworks:accounts/fireworks/models/kimi-k2p6",
                ],
                "plan": "codex:gpt-5.5",
            },
        )

        state = {
            "name": "demo",
            "current_state": "planned",
            "config": {"project_dir": str(tmp_path), "profile": "old", "vendor": "claude"},
            "meta": {},
            "history": [],
            "iteration": 1,
        }
        args = argparse.Namespace(profile="demo", reason="switch")

        response = _override_set_profile(tmp_path, tmp_path, state, args)

        assert response["success"] is True
        assert state["config"]["phase_model"] == [
            'execute=__fallback_json__:["hermes:deepseek:deepseek-v4-pro","hermes:fireworks:accounts/fireworks/models/kimi-k2p6"]',
            "plan=claude:claude-opus-4-7",
        ]

    def test_set_profile_persists_profile_tier_models(self, tmp_path: Path) -> None:
        state = {
            "name": "demo",
            "current_state": "planned",
            "config": {"project_dir": str(tmp_path), "profile": "old", "vendor": "codex"},
            "meta": {},
            "history": [],
            "iteration": 1,
        }
        args = argparse.Namespace(profile="partnered-5", reason="switch")

        response = _override_set_profile(tmp_path, tmp_path, state, args)

        assert response["success"] is True
        assert state["config"]["profile"] == "partnered-5"
        assert "tier_models" in state["config"]
        assert state["config"]["tier_models"]["execute"]["4"]
        assert state["config"]["tier_models"]["critique"]["4"]

    def test_set_profile_clears_stale_vendor_for_non_premium_profile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import arnold_pipelines.megaplan.profiles as profiles_module

        monkeypatch.setattr(profiles_module, "load_profiles", lambda project_dir=None: {"demo": {}})
        monkeypatch.setattr(profiles_module, "load_profile_metadata", lambda project_dir=None: {"demo": {}})
        monkeypatch.setattr(
            profiles_module,
            "resolve_profile",
            lambda profile_name, profiles: {
                "plan": "hermes:deepseek:deepseek-v4-pro",
                "execute": "hermes:deepseek:deepseek-v4-pro",
            },
        )
        monkeypatch.setattr(
            profiles_module,
            "_resolve_tier_models_with_inheritance",
            lambda *args, **kwargs: {},
        )

        state = {
            "name": "demo",
            "current_state": "planned",
            "config": {"project_dir": str(tmp_path), "profile": "old", "vendor": "claude"},
            "meta": {},
            "history": [],
            "iteration": 1,
        }
        args = argparse.Namespace(profile="demo", reason="switch")

        response = _override_set_profile(tmp_path, tmp_path, state, args)

        assert response["success"] is True
        assert state["config"]["phase_model"] == [
            "plan=hermes:deepseek:deepseek-v4-pro",
            "execute=hermes:deepseek:deepseek-v4-pro",
        ]
        assert "vendor" not in state["config"]

    def test_set_profile_rewrites_stale_prep_metadata_for_non_premium_profile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import arnold_pipelines.megaplan.profiles as profiles_module

        monkeypatch.setattr(profiles_module, "load_profiles", lambda project_dir=None: {"demo": {}})
        monkeypatch.setattr(profiles_module, "load_profile_metadata", lambda project_dir=None: {"demo": {}})
        monkeypatch.setattr(
            profiles_module,
            "resolve_profile",
            lambda profile_name, profiles: {
                "plan": "hermes:deepseek:deepseek-v4-pro",
                "execute": "hermes:deepseek:deepseek-v4-pro",
            },
        )
        monkeypatch.setattr(
            profiles_module,
            "_resolve_tier_models_with_inheritance",
            lambda *args, **kwargs: {},
        )
        monkeypatch.setattr(
            profiles_module,
            "_resolve_prep_models_with_inheritance",
            lambda *args, **kwargs: {},
        )

        state = {
            "name": "demo",
            "current_state": "planned",
            "config": {
                "project_dir": str(tmp_path),
                "profile": "old",
                "vendor": "claude",
                "prep_models": {
                    "triage": "claude:claude-sonnet-4-6",
                    "fanout": "claude:claude-sonnet-4-6",
                    "distill": "claude:claude-sonnet-4-6",
                },
                "prep_model_resolver_trace": {
                    "flat_prep_input": "claude",
                    "explicit_prep_models": {
                        "triage": "claude:claude-sonnet-4-6",
                    },
                    "resolved_stage_models": {
                        "triage": "claude:claude-sonnet-4-6",
                    },
                    "canonical_fallback_used": {"triage": False},
                },
            },
            "meta": {},
            "history": [],
            "iteration": 1,
        }
        args = argparse.Namespace(profile="demo", reason="switch")

        response = _override_set_profile(tmp_path, tmp_path, state, args)

        assert response["success"] is True
        assert state["config"]["prep_models"] == {
            "triage": "hermes:deepseek:deepseek-v4-pro",
            "fanout": "hermes:deepseek:deepseek-v4-pro",
            "distill": "hermes:deepseek:deepseek-v4-pro",
        }
        assert state["config"]["prep_model_resolver_trace"]["flat_prep_input"] is None
        assert state["config"]["prep_model_resolver_trace"]["explicit_prep_models"] == {}

    def test_set_model_replaces_encoded_chain_with_scalar_spec(self, tmp_path: Path) -> None:
        state = {
            "name": "demo",
            "current_state": "planned",
            "config": {
                "project_dir": str(tmp_path),
                "phase_model": ['execute=__fallback_json__:["codex:gpt-5.5","claude:claude-sonnet-4-6"]'],
            },
            "meta": {},
            "history": [],
            "iteration": 1,
        }
        args = argparse.Namespace(phase="execute", model="gpt-5.4", effort=None, reason="pin")

        response = _override_set_model(tmp_path, tmp_path, state, args)

        assert response["success"] is True
        assert state["config"]["phase_model"] == ["execute=codex:gpt-5.4"]
        assert response["previous_spec"] == '__fallback_json__:["codex:gpt-5.5","claude:claude-sonnet-4-6"]'
        assert response["new_spec"] == "codex:gpt-5.4"

    def test_escalate_stays_escalate_signal(self) -> None:
        from arnold_pipelines.megaplan.handlers._tiebreaker_impl import _route_signal_for_tiebreaker_action

        assert _route_signal_for_tiebreaker_action("escalate") == "escalate"


class TestReviewOutcomeSemantics:
    def test_resolve_review_outcome_emits_rework_signal(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.review import _resolve_review_outcome

        decision = _resolve_review_outcome(
            tmp_path,
            "needs_rework",
            verdict_count=1,
            total_tasks=1,
            check_count=0,
            total_checks=0,
            missing_evidence=[],
            robustness="full",
            state={"history": [], "config": {}, "current_state": "executed"},
            issues=[],
            criteria=[],
            infrastructure_failure=False,
            rework_items=[{"issue": "x", "deterministic_check": {"command": "pytest", "baseline_status": "failed", "post_status": "failed"}}],
        )

        assert decision.route_signal == "rework"
        assert decision.result == "needs_rework"

    def test_resolve_review_outcome_emits_deferred_human_signal(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.review import _resolve_review_outcome
        from arnold_pipelines.megaplan.planning.state import STATE_AWAITING_HUMAN_VERIFY

        decision = _resolve_review_outcome(
            tmp_path,
            "approved",
            verdict_count=1,
            total_tasks=1,
            check_count=0,
            total_checks=0,
            missing_evidence=[],
            robustness="full",
            state={"history": [], "config": {}, "current_state": "executed"},
            issues=[],
            criteria=[{"priority": "must", "pass": "deferred_human"}],
            infrastructure_failure=False,
            rework_items=[],
        )

        assert decision.route_signal == "deferred_human"
        assert decision.next_state == STATE_AWAITING_HUMAN_VERIFY


class TestOverrideOutcomeSemantics:
    def test_build_override_action_output_marks_additive_actions_without_branch_targets(self) -> None:
        from arnold_pipelines.megaplan.handlers.override import _build_override_action_output

        state = {"config": {}, "meta": {}, "current_state": "critiqued"}
        args = argparse.Namespace()
        output = _build_override_action_output(
            "add-note",
            plan_dir=Path("."),
            state=state,
            args=args,
        )

        assert output.route_signal == "add_note"
        assert output.state == "critiqued"
        assert output.next_step not in {"finalize", "revise", "halt"}

    def test_build_override_action_output_preserves_force_proceed_priority(self) -> None:
        from arnold_pipelines.megaplan.handlers.override import _build_override_action_output
        from arnold_pipelines.megaplan.planning.state import STATE_DONE

        state = {
            "config": {},
            "current_state": STATE_DONE,
            "meta": {"overrides": [{"action": "force-proceed", "debt_entries_added": 7}]},
        }
        output = _build_override_action_output(
            "force-proceed",
            plan_dir=Path("."),
            state=state,
            args=argparse.Namespace(reason="ship it"),
            artifacts={"orchestrator_guidance": "ignored", "debt_entries_added": 99},
        )

        assert output.state == STATE_DONE
        assert output.route_signal == "force_proceed"
        assert output.next_step is None

    def test_build_override_action_output_raises_unknown_error(self) -> None:
        from arnold_pipelines.megaplan.handlers.override import (
            UnknownOverrideActionError,
            _build_override_action_output,
        )

        with pytest.raises(UnknownOverrideActionError, match="Unknown override action: nope"):
            _build_override_action_output(
                "nope",
                plan_dir=Path("."),
                state={"config": {}, "meta": {}, "current_state": "critiqued"},
                args=argparse.Namespace(),
            )

    def test_normalize_override_response_adds_route_signal_and_action(self) -> None:
        from arnold_pipelines.megaplan.handlers.override import _normalize_override_response

        response = _normalize_override_response("set-profile", {"success": True, "step": "override"})
        assert response["override_action"] == "set-profile"
        assert response["route_signal"] == "set_profile"


class TestFinalizeSemanticChecks:
    def test_finalize_payload_requires_pending_status(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.finalize import _finalize_semantic_postcheck
        from arnold_pipelines.megaplan.workers import WorkerResult

        worker = WorkerResult(
            payload={
                "tasks": [
                    {
                        "id": "T1",
                        "description": "do thing",
                        "status": "done",
                        "complexity": 3,
                        "complexity_justification": "ok",
                    }
                ],
                "sense_checks": [],
                "watch_items": [],
            },
            raw_output="",
            duration_ms=0,
            cost_usd=0.0,
        )
        state: dict[str, Any] = {"iteration": 1, "config": {"mode": "code"}}
        errors: list[str] = []

        def _reject(msg: str) -> None:
            errors.append(msg)

        _finalize_semantic_postcheck(tmp_path, state, worker, _reject)
        assert any("status `pending`" in e for e in errors)

    def test_finalize_payload_accepts_pending_tasks(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.finalize import _finalize_semantic_postcheck
        from arnold_pipelines.megaplan.workers import WorkerResult

        worker = WorkerResult(
            payload={
                "tasks": [
                    {
                        "id": "T1",
                        "description": "do thing",
                        "status": "pending",
                        "complexity": 3,
                        "complexity_justification": "ok",
                    }
                ],
                "sense_checks": [],
                "watch_items": [],
            },
            raw_output="",
            duration_ms=0,
            cost_usd=0.0,
        )
        state: dict[str, Any] = {"iteration": 1, "config": {"mode": "code"}}
        errors: list[str] = []

        def _reject(msg: str) -> None:
            errors.append(msg)

        _finalize_semantic_postcheck(tmp_path, state, worker, _reject)
        assert errors == []

    def test_write_finalize_uses_task_pytest_command_for_baseline_capture(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from arnold_pipelines.megaplan.handlers import finalize

        project_dir = tmp_path / "repo"
        plan_dir = project_dir / ".megaplan" / "plans" / "p"
        plan_dir.mkdir(parents=True)
        state: dict[str, Any] = {
            "name": "p",
            "idea": "i",
            "current_state": "gated",
            "iteration": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "config": {
                "mode": "code",
                "project_dir": str(project_dir),
                "test_selection": "scoped",
            },
            "sessions": {},
            "plan_versions": [],
            "history": [],
            "meta": {},
            "last_gate": {},
        }
        payload = {
            "tasks": [
                {
                    "id": "T1",
                    "description": "Update code and run the focused regression tests.",
                    "depends_on": [],
                    "status": "pending",
                    "executor_notes": "",
                    "reviewer_verdict": "",
                    "kind": "test",
                    "complexity": 2,
                    "complexity_justification": "Focused regression coverage.",
                    "files_changed": ["tests/test_contract.py"],
                    "commands_run": ["pytest tests/test_contract.py -q"],
                }
            ],
            "sense_checks": [{"id": "SC1", "question": "Check T1", "task_id": "T1"}],
            "watch_items": [],
            "provides": [],
            "assumes": [],
            "pre_existing": [],
        }
        seen_config: dict[str, Any] = {}

        def fake_capture(
            captured_plan_dir: Path,
            captured_project_dir: Path,
            config: dict[str, Any],
        ) -> dict[str, Any]:
            assert captured_plan_dir == plan_dir
            assert captured_project_dir == project_dir
            seen_config.update(config)
            return {
                "baseline_test_failures": [],
                "baseline_test_command": config.get("test_command"),
            }

        monkeypatch.setattr(finalize, "_capture_test_baseline_for_plan", fake_capture)

        finalize._write_finalize_artifacts(plan_dir, payload, state)

        assert seen_config["test_command"] == "pytest tests/test_contract.py"
        assert payload["test_selection"]["mode"] == "scoped"
        assert payload["test_selection"]["fallback_source"] == "finalize_task_commands_run"
        assert payload["baseline_test_command"] == "pytest tests/test_contract.py"

    def test_write_finalize_preserves_user_action_gate_after_verification_rewrite(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from arnold_pipelines.megaplan.handlers import finalize

        project_dir = tmp_path / "repo"
        plan_dir = project_dir / ".megaplan" / "plans" / "p"
        plan_dir.mkdir(parents=True)
        state: dict[str, Any] = {
            "name": "p",
            "idea": "i",
            "current_state": "gated",
            "iteration": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "config": {
                "mode": "code",
                "project_dir": str(project_dir),
                "test_selection": "scoped",
            },
            "sessions": {},
            "plan_versions": [],
            "history": [],
            "meta": {},
            "last_gate": {},
        }
        payload = {
            "tasks": [
                {
                    "id": "T1",
                    "description": "Update code and run the focused regression tests.",
                    "depends_on": [],
                    "status": "pending",
                    "executor_notes": "",
                    "reviewer_verdict": "",
                    "kind": "test",
                    "complexity": 2,
                    "complexity_justification": "Focused regression coverage.",
                    "files_changed": ["tests/test_contract.py"],
                    "commands_run": ["pytest tests/test_contract.py -q"],
                }
            ],
            "sense_checks": [],
            "watch_items": [],
            "provides": [],
            "assumes": [],
            "pre_existing": [],
            "user_actions": [
                {
                    "id": "ua-01",
                    "description": "Confirm the contract assumption is still authoritative.",
                    "phase": "before_execute",
                    "blocks_task_ids": ["T1"],
                    "rationale": "Need an explicit resolution before execution proceeds.",
                    "requires_human_only_reason": "Maintainer decision.",
                }
            ],
        }

        def fake_capture(
            captured_plan_dir: Path,
            captured_project_dir: Path,
            config: dict[str, Any],
        ) -> dict[str, Any]:
            assert captured_plan_dir == plan_dir
            assert captured_project_dir == project_dir
            return {
                "baseline_test_failures": [],
                "baseline_test_command": config.get("test_command"),
            }

        monkeypatch.setattr(finalize, "_capture_test_baseline_for_plan", fake_capture)

        finalize._write_finalize_artifacts(plan_dir, payload, state)

        gate_task = payload["tasks"][0]
        assert gate_task["id"] == "T2"
        assert gate_task["description"].startswith("Read user_actions.md.")
        assert "megaplan user-action resolve" in gate_task["description"]
        assert payload["tasks"][1]["id"] == "T1"
        assert payload["tasks"][1]["description"].startswith(
            "Introduce no new failures vs the recorded baseline;"
        )
        assert payload["tasks"][1]["depends_on"][0] == "T2"
        assert payload["sense_checks"][-1]["task_id"] == "T2"


class TestReviewPayloadDefaults:
    def test_prepare_review_payload_fills_defaults(self) -> None:
        from arnold_pipelines.megaplan.handlers.review import _prepare_review_payload

        payload = {"review_verdict": "approved"}
        result = _prepare_review_payload(payload, pre_check_flags=None)
        assert result["checks"] == []
        assert result["pre_check_flags"] == []
        assert result["verified_flag_ids"] == []
        assert result["disputed_flag_ids"] == []

    def test_review_infrastructure_failure_detects_incomplete_status(self) -> None:
        from arnold_pipelines.megaplan.handlers.review import _review_infrastructure_failure

        payload = {
            "review_completion_status": "incomplete",
            "rework_items": [],
            "criteria": [],
        }
        assert _review_infrastructure_failure(payload, issues=[], total_tasks=0, total_checks=0)

    def test_raw_review_output_needs_rework_cannot_be_normalized_to_approved(
        self, tmp_path: Path
    ) -> None:
        from arnold_pipelines.megaplan.handlers.review import (
            _normalize_review_blockers,
            _promote_authoritative_review_output,
            _preserve_raw_review_rework_verdict,
        )

        (tmp_path / "review_output.json").write_text(
            json.dumps(
                {
                    "review_verdict": "needs_rework",
                    "review_completion_status": "complete",
                    "summary": "raw reviewer caught missing work",
                    "issues": ["T3 was not implemented"],
                    "task_verdicts": [
                        {
                            "task_id": "T3",
                            "reviewer_verdict": "Fail. Missing implementation.",
                            "evidence_files": ["execution.json"],
                        }
                    ],
                    "sense_check_verdicts": [
                        {"sense_check_id": "SC3", "verdict": "Not satisfied."}
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        payload = {
            "review_verdict": "approved",
            "review_completion_status": "complete",
            "summary": "wrapper payload",
            "issues": [],
            "task_verdicts": [],
            "sense_check_verdicts": [],
        }
        assert _promote_authoritative_review_output(
            plan_dir=tmp_path,
            payload=payload,
        )
        issues: list[str] = []

        changed = _preserve_raw_review_rework_verdict(
            plan_dir=tmp_path,
            payload=payload,
            issues=issues,
        )
        raw_rework_preserved = changed

        if not raw_rework_preserved:
            _normalize_review_blockers(payload, issues)

        assert payload["review_verdict"] == "needs_rework"
        assert payload["task_verdicts"][0]["task_id"] == "T3"
        assert payload["raw_review_output_promoted"] is True

    def test_raw_review_rework_preservation_skips_blocker_demotion(
        self, tmp_path: Path
    ) -> None:
        from arnold_pipelines.megaplan.handlers.review import (
            _normalize_review_blockers,
            _preserve_raw_review_rework_verdict,
        )

        (tmp_path / "review_output.json").write_text(
            json.dumps(
                {
                    "review_verdict": "needs_rework",
                    "review_completion_status": "complete",
                    "issues": ["must rework"],
                    "rework_items": [
                        {
                            "task_id": "T3",
                            "issue": "Reviewer found incomplete work.",
                            "source": "review_success_criterion",
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        payload = {
            "review_verdict": "approved",
            "review_completion_status": "complete",
            "issues": [],
            "rework_items": [],
            "task_verdicts": [],
            "sense_check_verdicts": [],
        }
        issues: list[str] = []

        raw_rework_preserved = _preserve_raw_review_rework_verdict(
            plan_dir=tmp_path,
            payload=payload,
            issues=issues,
        )
        if not raw_rework_preserved:
            _normalize_review_blockers(payload, issues)

        assert raw_rework_preserved is True
        assert payload["review_verdict"] == "needs_rework"
        assert payload["raw_review_verdict_preserved"] is True
        assert any("review_output.json returned needs_rework" in issue for issue in issues)

    def test_newly_failing_deterministic_check_is_blocking(self) -> None:
        from arnold_pipelines.megaplan.handlers.review import (
            _has_grounded_deterministic_failure,
        )

        assert _has_grounded_deterministic_failure(
            {
                "deterministic_check": {
                    "command": "python -m pytest tests/example.py -q",
                    "baseline_status": "passed at base (2 passed)",
                    "post_status": "failed at current HEAD (2 failed)",
                }
            }
        )

    def test_promoted_raw_needs_rework_not_demoted_by_normalizer(
        self, tmp_path: Path
    ) -> None:
        from arnold_pipelines.megaplan.handlers.review import (
            _normalize_review_blockers,
            _promote_authoritative_review_output,
        )

        (tmp_path / "review_output.json").write_text(
            json.dumps(
                {
                    "review_verdict": "needs_rework",
                    "review_completion_status": "complete",
                    "issues": ["regression"],
                    "rework_items": [
                        {
                            "task_id": "T2",
                            "issue": "new regression",
                            "deterministic_check": {
                                "command": "python -m pytest tests/example.py -q",
                                "baseline_status": "passed at base",
                                "post_status": "failed at current",
                            },
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        payload = {"review_verdict": "approved", "rework_items": []}
        promoted = _promote_authoritative_review_output(
            plan_dir=tmp_path,
            payload=payload,
        )
        issues = list(payload.get("issues", []))
        if not (promoted and payload.get("review_verdict") == "needs_rework"):
            _normalize_review_blockers(payload, issues)

        assert promoted is True
        assert payload["review_verdict"] == "needs_rework"
        assert payload["rework_items"]

    def test_review_approval_fails_when_finalize_tasks_lack_execute_authority(
        self, tmp_path: Path
    ) -> None:
        from arnold_pipelines.megaplan.handlers.review import (
            _enforce_review_execute_authority,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        finalize_data = {
            "tasks": [
                {
                    "id": "T1",
                    "status": "pending",
                    "description": "Implement the required checker hook.",
                }
            ]
        }
        payload = {
            "review_verdict": "approved",
            "review_completion_status": "complete",
            "issues": [],
            "rework_items": [],
            "criteria": [],
        }
        state: dict[str, Any] = {"config": {"project_dir": str(tmp_path)}}
        issues: list[str] = []

        changed = _enforce_review_execute_authority(
            payload=payload,
            finalize_data=finalize_data,
            plan_dir=plan_dir,
            project_dir=tmp_path,
            state=state,
            issues=issues,
        )

        assert changed is True
        assert payload["review_verdict"] == "needs_rework"
        assert payload["execute_authority_missing"] == ["T1:not_executed:pending"]
        assert payload["rework_items"][0]["source"] == "execute_authority"
        assert payload["criteria"][0]["pass"] is False


class TestTaskSatisfactionStaleHead:
    def test_is_task_satisfied_flags_stale_ancestor_head(self) -> None:
        from arnold_pipelines.megaplan.orchestration.evidence_contract import (
            EvidenceRef,
            EvidenceStatus,
        )
        from arnold_pipelines.megaplan.orchestration.task_satisfaction import (
            EvidenceExecutionWindow,
            is_task_satisfied,
        )

        task = {"task_id": "T1", "files_changed": ["src/foo.py"]}
        evidence = EvidenceRef(
            kind="task",
            status=EvidenceStatus.satisfied,
            summary="done",
            subject="T1",
            details={"head_sha": "oldsha"},
        )
        window = EvidenceExecutionWindow(
            project_dir=Path("/tmp"),
            base_sha="basesha",
            head_sha="newsha",
        )
        result = is_task_satisfied(task, evidence, execution_window=window)
        assert not result.satisfied
        assert any("head_mismatch" in s for s in result.stale_evidence)

    def test_is_task_satisfied_prefers_fresh_linked_evidence_over_stale_finalize_copy(
        self,
    ) -> None:
        from arnold_pipelines.megaplan.orchestration.evidence_contract import (
            EvidenceRef,
            EvidenceStatus,
        )
        from arnold_pipelines.megaplan.orchestration.task_satisfaction import (
            is_task_satisfied,
        )

        task = {"task_id": "T1", "commands_run": ["pytest tests/test_example.py -q"]}
        evidence = (
            EvidenceRef(
                kind="task_commands_run",
                status=EvidenceStatus.satisfied,
                summary="stale finalize evidence",
                subject="T1",
                details={
                    "task_id": "T1",
                    "commands_run": ["pytest tests/test_example.py -q"],
                    "head_sha": "stale-head",
                },
            ),
            EvidenceRef(
                kind="task_commands_run",
                status=EvidenceStatus.satisfied,
                summary="fresh execution evidence",
                subject="T1",
                details={
                    "task_id": "T1",
                    "commands_run": ["pytest tests/test_example.py -q"],
                    "head_sha": "fresh-head",
                },
            ),
        )

        result = is_task_satisfied(task, evidence, current_head="fresh-head")

        assert result.satisfied is True
        assert result.stale_evidence == ()
        assert len(result.evidence) == 1


class TestBlastRadiusFallback:
    def test_compute_default_blast_radius_falls_back_when_no_mirror(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.orchestration.test_selection import (
            compute_default_blast_radius,
        )

        # A Python file with no mirror test file forces full suite via import-graph degraded.
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "orphan.py").write_text("x = 1")
        (tmp_path / "tests").mkdir()

        result = compute_default_blast_radius(["src/orphan.py"], tmp_path)
        # No mirror test file exists, so the default stays on the full-suite path.
        assert result["strategy"] == "full"
        assert result["full_suite_fallback"] is True


class TestFinalizeSemanticPostcheck:
    def test_rejects_finalize_meta_work_as_task_output(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.finalize import (
            _finalize_semantic_postcheck,
        )
        from arnold_pipelines.megaplan.workers import WorkerResult

        worker = WorkerResult(
            payload={
                "tasks": [
                    {
                        "id": "T0",
                        "description": "Finalize the plan artifact.",
                        "depends_on": [],
                        "status": "pending",
                        "kind": "docs",
                        "executor_notes": "Wrote finalize_output.json.",
                        "files_changed": [
                            str(tmp_path / ".megaplan/plans/p/finalize_output.json")
                        ],
                        "commands_run": [],
                        "auto_attributed_files": None,
                        "evidence_files": [],
                        "reviewer_verdict": "",
                        "complexity": 1,
                        "complexity_justification": "small",
                    }
                ],
                "user_actions": [],
                "sense_checks": [],
                "watch_items": [],
            },
            raw_output="",
            duration_ms=0,
            cost_usd=0.0,
        )

        def reject(message: str) -> None:
            raise AssertionError(message)

        with pytest.raises(AssertionError, match="harness artifact path"):
            _finalize_semantic_postcheck(
                tmp_path,
                {"config": {"mode": "code"}},
                worker,
                reject,
            )


class TestFinalizeBaselineSelectionRecovery:
    def _state(self, plan_dir: Path, repo: Path) -> dict[str, Any]:
        return {
            "name": "p",
            "iteration": 1,
            "current_state": "gated",
            "config": {"mode": "code", "project_dir": str(repo), "robustness": "extreme"},
            "meta": {},
            "history": [],
            "plan_versions": [
                {
                    "version": 1,
                    "file": "plan_v1.md",
                    "hash": "sha256:old",
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            ],
            "last_gate": {"recommendation": "PROCEED", "passed": True},
            "sessions": {},
        }

    def _payload(self) -> dict[str, Any]:
        return {
            "tasks": [
                {
                    "id": "T1",
                    "description": "Touch docs only.",
                    "depends_on": [],
                    "status": "pending",
                    "files_changed": ["docs/notes.md"],
                    "commands_run": [],
                    "complexity": 1,
                    "complexity_justification": "small",
                }
            ],
            "user_actions": [],
            "sense_checks": [],
            "watch_items": [],
        }

    def test_unresolved_finalize_baseline_scope_does_not_capture_full_suite(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from arnold_pipelines.megaplan.handlers import finalize

        repo = tmp_path / "repo"
        plan_dir = repo / ".megaplan" / "plans" / "p"
        plan_dir.mkdir(parents=True)
        (plan_dir / "plan_v1.md").write_text("## Step 1: Docs\n", encoding="utf-8")
        (plan_dir / "plan_v1.meta.json").write_text("{}", encoding="utf-8")
        (repo / "docs").mkdir()
        (repo / "docs" / "notes.md").write_text("notes\n", encoding="utf-8")

        def fail_capture(*args: Any, **kwargs: Any) -> dict[str, Any]:
            raise AssertionError("baseline capture must not run")

        monkeypatch.setattr(finalize, "_capture_test_baseline_for_plan", fail_capture)

        with pytest.raises(finalize.FinalizeBaselineSelectionError):
            finalize._write_finalize_artifacts(plan_dir, self._payload(), self._state(plan_dir, repo))

    def test_none_finalize_baseline_scope_is_revise_contract_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from arnold_pipelines.megaplan.handlers import finalize

        repo = tmp_path / "repo"
        plan_dir = repo / ".megaplan" / "plans" / "p"
        plan_dir.mkdir(parents=True)
        (plan_dir / "plan_v1.md").write_text("## Step 1: Docs\n", encoding="utf-8")
        (plan_dir / "plan_v1.meta.json").write_text(
            json.dumps(
                {
                    "test_blast_radius": {
                        "strategy": "none",
                        "confidence": "medium",
                        "selectors": [],
                        "changed_surfaces": [],
                        "always_run": [],
                        "full_suite_fallback": True,
                        "rationale": "No code or test surfaces changed.",
                    }
                }
            ),
            encoding="utf-8",
        )

        def fail_capture(*args: Any, **kwargs: Any) -> dict[str, Any]:
            raise AssertionError("baseline capture must not run for none scope")

        payload = self._payload()
        monkeypatch.setattr(finalize, "_capture_test_baseline_for_plan", fail_capture)

        with pytest.raises(finalize.FinalizeBaselineSelectionError):
            finalize._write_finalize_artifacts(plan_dir, payload, self._state(plan_dir, repo))

    def test_unresolved_finalize_baseline_scope_routes_to_revise(
        self,
        tmp_path: Path,
    ) -> None:
        from arnold_pipelines.megaplan._core import infer_next_steps
        from arnold_pipelines.megaplan.handlers import finalize
        from arnold_pipelines.megaplan.workers import WorkerResult

        repo = tmp_path / "repo"
        plan_dir = repo / ".megaplan" / "plans" / "p"
        plan_dir.mkdir(parents=True)
        state = self._state(plan_dir, repo)
        (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        worker = WorkerResult(
            payload=self._payload(),
            raw_output='{"tasks": []}',
            duration_ms=12,
            cost_usd=0.0,
        )
        error = finalize.FinalizeBaselineSelectionError(
            {
                "mode": "unresolved",
                "reason": "No test_blast_radius in plan metadata",
                "command_override": None,
            }
        )

        response = finalize._route_finalize_baseline_selection_failure_to_revise(
            plan_dir,
            state,
            worker,
            error,
        )

        assert response["success"] is False
        assert response["result"] == "plan_contract_revise_needed"
        assert response["next_step"] == "revise"
        assert state["current_state"] == "critiqued"
        assert state["last_gate"]["recommendation"] == "ITERATE"
        assert state["last_gate"]["north_star_actions"] == []
        assert (plan_dir / "gate.json").exists()
        assert (plan_dir / "gate_carry.json").exists()
        assert (plan_dir / "finalize_revise_feedback.json").exists()
        assert infer_next_steps(state)[0] == "revise"

        persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        assert persisted["current_state"] == "critiqued"
        assert persisted["last_gate"]["recommendation"] == "ITERATE"
        assert persisted["last_gate"]["north_star_actions"] == []
        assert json.loads(
            (plan_dir / "gate_carry.json").read_text(encoding="utf-8")
        )["north_star_actions"] == []


class TestExecuteTimeoutHardening:
    def test_reset_timeout_invalid_tasks_resets_done_to_pending(self) -> None:
        from arnold_pipelines.megaplan.execute.timeout import _reset_timeout_invalid_tasks

        finalize_data = {
            "tasks": [
                {
                    "id": "T1",
                    "status": "done",
                    "executor_notes": "",
                    "files_changed": [],
                    "commands_run": [],
                }
            ]
        }
        issues: list[str] = []
        reset = _reset_timeout_invalid_tasks(
            finalize_data,
            execution_audit={"skipped": False, "files_in_diff": []},
            issues=issues,
            mode="code",
        )
        assert "T1" in reset
        assert finalize_data["tasks"][0]["status"] == "pending"
        assert "Timeout recovery" in finalize_data["tasks"][0]["executor_notes"]


class TestAutoExecuteRecovery:
    def test_completed_gate_artifact_is_adopted_after_worker_failure(
        self, tmp_path: Path
    ) -> None:
        from arnold_pipelines.megaplan.auto import (
            _recover_completed_gate_artifact_after_failure,
        )

        plan_dir = tmp_path / ".megaplan" / "plans" / "p"
        plan_dir.mkdir(parents=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "current_state": "critiqued",
                    "active_step": {"phase": "gate"},
                    "meta": {},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (plan_dir / "gate.json").write_text(
            json.dumps(
                {
                    "recommendation": "PROCEED",
                    "passed": True,
                    "unresolved_flags": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )

        assert _recover_completed_gate_artifact_after_failure(plan_dir) is True

        state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        assert state["current_state"] == "gated"
        assert "active_step" not in state
        assert state["last_gate"]["recommendation"] == "PROCEED"
        assert state["history"][-1]["step"] == "gate"
        assert state["history"][-1]["result"] == "success"
        assert state["history"][-1]["recovered_from_artifact"] is True
        assert state["history"][-1]["artifact_hash"].startswith("sha256:")
        assert state["meta"]["gate_artifact_recovery"]["gate_recommendation"] == "PROCEED"

    def test_stale_gate_artifact_is_not_adopted_after_same_iteration_replan(
        self, tmp_path: Path
    ) -> None:
        from arnold_pipelines.megaplan.auto import (
            _recover_completed_gate_artifact_after_failure,
        )

        plan_dir = tmp_path / ".megaplan" / "plans" / "p"
        plan_dir.mkdir(parents=True)
        gate_path = plan_dir / "gate.json"
        gate_path.write_text(
            json.dumps(
                {
                    "recommendation": "PROCEED",
                    "passed": True,
                    "unresolved_flags": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        plan_path = plan_dir / "plan_v3a.md"
        plan_path.write_text("# corrected plan\n", encoding="utf-8")
        critique_path = plan_dir / "critique_v3.json"
        critique_path.write_text("{}\n", encoding="utf-8")
        gate_path.touch()
        os.utime(gate_path, ns=(1_000_000_000, 1_000_000_000))
        os.utime(plan_path, ns=(2_000_000_000, 2_000_000_000))
        os.utime(critique_path, ns=(3_000_000_000, 3_000_000_000))
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "current_state": "critiqued",
                    "active_step": {"phase": "gate"},
                    "plan_versions": [{"version": 3, "file": plan_path.name}],
                    "history": [
                        {
                            "step": "critique",
                            "result": "success",
                            "output_file": critique_path.name,
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )

        assert _recover_completed_gate_artifact_after_failure(plan_dir) is False

        state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        assert state["current_state"] == "critiqued"
        assert state["history"][-1]["step"] == "critique"

    def test_non_proceed_gate_artifact_is_not_adopted_after_worker_failure(
        self, tmp_path: Path
    ) -> None:
        from arnold_pipelines.megaplan.auto import (
            _recover_completed_gate_artifact_after_failure,
        )

        plan_dir = tmp_path / ".megaplan" / "plans" / "p"
        plan_dir.mkdir(parents=True)
        (plan_dir / "state.json").write_text(
            json.dumps({"current_state": "critiqued", "active_step": {"phase": "gate"}})
            + "\n",
            encoding="utf-8",
        )
        (plan_dir / "gate.json").write_text(
            json.dumps({"recommendation": "ITERATE", "passed": False}) + "\n",
            encoding="utf-8",
        )

        assert _recover_completed_gate_artifact_after_failure(plan_dir) is False

        state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        assert state["current_state"] == "critiqued"

    def test_completed_execution_not_adopted_after_newer_needs_rework_review(
        self, tmp_path: Path
    ) -> None:
        from arnold_pipelines.megaplan.auto import (
            _recover_completed_execute_artifacts_after_failure,
        )

        plan_dir = tmp_path / "plans" / "example-plan"
        plan_dir.mkdir(parents=True)
        (plan_dir / "state.json").write_text(
            json.dumps({"current_state": "finalized"}) + "\n",
            encoding="utf-8",
        )
        execution_path = plan_dir / "execution.json"
        execution_path.write_text(
            json.dumps({"output": "old complete execution"}) + "\n",
            encoding="utf-8",
        )
        review_path = plan_dir / "review.json"
        review_path.write_text(
            json.dumps(
                {
                    "review_verdict": "needs_rework",
                    "rework_items": [{"task_id": "T2", "issue": "fix this"}],
                }
            )
            + "\n",
            encoding="utf-8",
        )

        assert review_path.stat().st_mtime >= execution_path.stat().st_mtime
        assert _recover_completed_execute_artifacts_after_failure(plan_dir) is False


# ---------------------------------------------------------------------------
# Promotion evidence tests (T9/T10)
# ---------------------------------------------------------------------------


class TestPromotionEvidenceScratchMissing:
    """build_promotion_evidence when scratch is missing."""

    def test_missing_scratch_produces_missing_fallback_evidence(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        evidence = build_promotion_evidence(
            plan_dir,
            "missing",
            phase_identity="gate",
            scratch_filename="gate_output.json",
            worker_payload_used=True,
        )
        assert len(evidence) >= 1
        missing_records = [
            r for r in evidence if r["promotion_state"] == "scratch-missing-fallback"
        ]
        assert len(missing_records) == 1
        rec = missing_records[0]
        assert rec["phase_identity"] == "gate"
        assert rec["scratch_status"] == "missing"
        assert rec["scratch_filename"] == "gate_output.json"
        assert rec["boundary_id"] == "gate_to_revise"
        assert rec["workflow_id"] == "megaplan-review"
        assert rec["details"]["fallback_source"] == "worker.payload"

    def test_missing_scratch_without_worker_payload_sets_fallback_none(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        evidence = build_promotion_evidence(
            plan_dir,
            "missing",
            phase_identity="finalize",
            scratch_filename="finalize_output.json",
            worker_payload_used=False,
        )
        missing_records = [
            r for r in evidence if r["promotion_state"] == "scratch-missing-fallback"
        ]
        assert len(missing_records) == 1
        assert missing_records[0]["details"]["fallback_source"] == "none"

    def test_missing_scratch_for_finalize_uses_artifacts_boundary_id(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        evidence = build_promotion_evidence(
            plan_dir,
            "missing",
            phase_identity="finalize",
            scratch_filename="finalize_output.json",
            worker_payload_used=True,
        )
        missing_records = [
            r for r in evidence if r["promotion_state"] == "scratch-missing-fallback"
        ]
        assert len(missing_records) == 1
        assert missing_records[0]["boundary_id"] == "finalize_artifacts"


class TestPromotionEvidenceScratchUnmodified:
    """build_promotion_evidence when scratch is unmodified."""

    def test_unmodified_scratch_produces_unmodified_fallback_evidence(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        scratch = plan_dir / "gate_output.json"
        scratch.write_text('{"unchanged": true}', encoding="utf-8")
        evidence = build_promotion_evidence(
            plan_dir,
            "unmodified",
            phase_identity="gate",
            scratch_filename="gate_output.json",
            worker_payload_used=True,
        )
        unmod_records = [
            r for r in evidence if r["promotion_state"] == "scratch-unmodified-fallback"
        ]
        assert len(unmod_records) == 1
        rec = unmod_records[0]
        assert rec["phase_identity"] == "gate"
        assert rec["scratch_status"] == "unmodified"
        assert rec["details"]["scratch_exists"] is True
        assert rec["details"]["fallback_source"] == "worker.payload"

    def test_unmodified_scratch_does_not_produce_missing_evidence(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        scratch = plan_dir / "finalize_output.json"
        scratch.write_text("{}", encoding="utf-8")
        evidence = build_promotion_evidence(
            plan_dir,
            "unmodified",
            phase_identity="finalize",
            scratch_filename="finalize_output.json",
            worker_payload_used=True,
        )
        missing_records = [
            r for r in evidence if "missing" in r.get("promotion_state", "")
            and "receipt" not in r.get("promotion_state", "")
        ]
        assert len(missing_records) == 0


class TestPromotionEvidenceScratchFilled:
    """build_promotion_evidence when scratch is filled (successful promotion)."""

    def test_filled_scratch_produces_no_scratch_fallback_evidence(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        scratch = plan_dir / "gate_output.json"
        scratch.write_text('{"checks": [], "flags": []}', encoding="utf-8")
        evidence = build_promotion_evidence(
            plan_dir,
            "filled",
            phase_identity="gate",
            scratch_filename="gate_output.json",
        )
        # Filled should NOT produce missing/unmodified/invalid fallback evidence
        fallback_states = {"scratch-missing-fallback", "scratch-unmodified-fallback", "scratch-invalid-fallback"}
        fallback_records = [r for r in evidence if r.get("promotion_state") in fallback_states]
        assert len(fallback_records) == 0

    def test_filled_with_canonical_without_receipt_produces_evidence(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        scratch = plan_dir / "gate_output.json"
        scratch.write_text('{"checks": [], "flags": []}', encoding="utf-8")
        # Also create canonical artifact without receipt
        canonical = plan_dir / "gate.json"
        canonical.write_text('{"checks": [], "flags": []}', encoding="utf-8")
        evidence = build_promotion_evidence(
            plan_dir,
            "filled",
            phase_identity="gate",
            scratch_filename="gate_output.json",
        )
        cwr = [r for r in evidence if r.get("promotion_state") == "canonical-without-receipt"]
        assert len(cwr) >= 1
        assert cwr[0]["details"]["canonical_exists"] is True
        assert cwr[0]["details"]["receipt_exists"] is False


class TestPromotionEvidenceScratchInvalid:
    """build_promotion_evidence when scratch is invalid."""

    def test_invalid_scratch_produces_invalid_fallback_evidence(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        scratch = plan_dir / "gate_output.json"
        scratch.write_text("not valid json at all {{{", encoding="utf-8")
        evidence = build_promotion_evidence(
            plan_dir,
            "invalid",
            phase_identity="gate",
            scratch_filename="gate_output.json",
            worker_payload_used=True,
        )
        invalid_records = [
            r for r in evidence if r["promotion_state"] == "scratch-invalid-fallback"
        ]
        assert len(invalid_records) == 1
        rec = invalid_records[0]
        assert rec["phase_identity"] == "gate"
        assert rec["scratch_status"] == "invalid"
        assert rec["details"]["scratch_exists"] is True

    def test_invalid_scratch_without_worker_payload(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        scratch = plan_dir / "finalize_output.json"
        scratch.write_text("{broken", encoding="utf-8")
        evidence = build_promotion_evidence(
            plan_dir,
            "invalid",
            phase_identity="finalize",
            scratch_filename="finalize_output.json",
            worker_payload_used=False,
        )
        invalid_records = [
            r for r in evidence if r["promotion_state"] == "scratch-invalid-fallback"
        ]
        assert len(invalid_records) == 1
        assert invalid_records[0]["details"]["fallback_source"] == "none"


class TestPromotionEvidenceWrongPath:
    """build_promotion_evidence when model wrote to wrong path."""

    def test_model_wrote_canonical_not_scratch_produces_wrong_path_evidence(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        # Model wrote to canonical path (gate.json) but NOT scratch (gate_output.json)
        canonical = plan_dir / "gate.json"
        canonical.write_text('{"checks": [], "flags": []}', encoding="utf-8")
        evidence = build_promotion_evidence(
            plan_dir,
            "missing",
            phase_identity="gate",
            scratch_filename="gate_output.json",
            worker_payload_used=True,
        )
        wrong_path_records = [
            r for r in evidence if r.get("promotion_state") == "model-wrote-wrong-path"
        ]
        assert len(wrong_path_records) == 1
        rec = wrong_path_records[0]
        assert rec["details"]["scratch_exists"] is False
        assert rec["details"]["canonical_exists"] is True
        assert "expected-path-only" in rec["details"]["note"]

    def test_wrong_path_also_produces_missing_fallback(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        canonical = plan_dir / "finalize.json"
        canonical.write_text('{"tasks": []}', encoding="utf-8")
        evidence = build_promotion_evidence(
            plan_dir,
            "missing",
            phase_identity="finalize",
            scratch_filename="finalize_output.json",
            worker_payload_used=True,
        )
        # Should have both missing-fallback and wrong-path evidence
        states = {r["promotion_state"] for r in evidence}
        assert "scratch-missing-fallback" in states
        assert "model-wrote-wrong-path" in states

    def test_filled_scratch_no_wrong_path_even_if_canonical_exists(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        scratch = plan_dir / "gate_output.json"
        scratch.write_text('{"checks": []}', encoding="utf-8")
        canonical = plan_dir / "gate.json"
        canonical.write_text('{"checks": []}', encoding="utf-8")
        evidence = build_promotion_evidence(
            plan_dir,
            "filled",
            phase_identity="gate",
            scratch_filename="gate_output.json",
        )
        wrong_path_records = [
            r for r in evidence if r.get("promotion_state") == "model-wrote-wrong-path"
        ]
        assert len(wrong_path_records) == 0


class TestPromotionEvidenceReceiptPhaseResult:
    """build_promotion_evidence receipt-without-phase_result detection."""

    def test_receipt_exists_but_no_phase_result(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        scratch = plan_dir / "gate_output.json"
        scratch.write_text('{"checks": []}', encoding="utf-8")
        canonical = plan_dir / "gate.json"
        canonical.write_text('{"checks": []}', encoding="utf-8")
        # Create receipt
        receipt_dir = plan_dir / "boundary_receipts"
        receipt_dir.mkdir(parents=True)
        (receipt_dir / "gate_to_revise.json").write_text("{}", encoding="utf-8")
        # No phase_result.json
        evidence = build_promotion_evidence(
            plan_dir,
            "filled",
            phase_identity="gate",
            scratch_filename="gate_output.json",
        )
        rwp = [r for r in evidence if "receipt-without-phase-result" in r.get("promotion_state", "")]
        assert len(rwp) >= 1
        assert rwp[0]["details"]["phase_result_missing"] is True
        assert rwp[0]["details"]["receipt_exists"] is True

    def test_receipt_exists_with_stale_phase_result(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        scratch = plan_dir / "finalize_output.json"
        scratch.write_text('{"tasks": []}', encoding="utf-8")
        canonical = plan_dir / "finalize.json"
        canonical.write_text('{"tasks": []}', encoding="utf-8")
        receipt_dir = plan_dir / "boundary_receipts"
        receipt_dir.mkdir(parents=True)
        (receipt_dir / "finalize_artifacts.json").write_text("{}", encoding="utf-8")
        # phase_result.json with different phase
        (plan_dir / "phase_result.json").write_text(
            '{"phase": "gate", "result": "success"}', encoding="utf-8"
        )
        evidence = build_promotion_evidence(
            plan_dir,
            "filled",
            phase_identity="finalize",
            scratch_filename="finalize_output.json",
        )
        rwp = [r for r in evidence if "receipt-without-phase-result" in r.get("promotion_state", "")]
        assert len(rwp) >= 1
        assert rwp[0]["details"]["phase_result_stale"] is True
        assert rwp[0]["details"]["expected_phase"] == "finalize"

    def test_receipt_and_phase_result_both_present_no_evidence(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        scratch = plan_dir / "gate_output.json"
        scratch.write_text('{"checks": []}', encoding="utf-8")
        canonical = plan_dir / "gate.json"
        canonical.write_text('{"checks": []}', encoding="utf-8")
        receipt_dir = plan_dir / "boundary_receipts"
        receipt_dir.mkdir(parents=True)
        (receipt_dir / "gate_to_revise.json").write_text("{}", encoding="utf-8")
        (plan_dir / "phase_result.json").write_text(
            '{"phase": "gate", "result": "success"}', encoding="utf-8"
        )
        evidence = build_promotion_evidence(
            plan_dir,
            "filled",
            phase_identity="gate",
            scratch_filename="gate_output.json",
        )
        rwp = [r for r in evidence if "receipt-without-phase-result" in r.get("promotion_state", "")]
        assert len(rwp) == 0


class TestPromotionEvidenceEmptyCanonical:
    """build_promotion_evidence when no canonical artifact exists."""

    def test_filled_without_canonical_produces_no_canonical_receipt_evidence(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        scratch = plan_dir / "gate_output.json"
        scratch.write_text('{"checks": []}', encoding="utf-8")
        evidence = build_promotion_evidence(
            plan_dir,
            "filled",
            phase_identity="gate",
            scratch_filename="gate_output.json",
        )
        cwr = [r for r in evidence if r.get("promotion_state") == "canonical-without-receipt"]
        assert len(cwr) == 0


# ---------------------------------------------------------------------------
# Gate and finalize explicit boundary template use tests
# ---------------------------------------------------------------------------


class TestGateBoundaryTemplateUse:
    """Gate phase explicitly uses reusable boundary template."""

    def test_gate_registration_references_validation_boundary(self) -> None:
        from arnold_pipelines.megaplan.template_registry import get_template_registration

        reg = get_template_registration("gate")
        assert reg is not None
        assert reg.boundary_template_id == "template.validation_boundary"

    def test_gate_boundary_template_has_phase_none(self) -> None:
        from arnold_pipelines.megaplan.workflows.boundary_contracts import (
            TYPED_BOUNDARY_TEMPLATES_BY_ID,
        )

        template = TYPED_BOUNDARY_TEMPLATES_BY_ID.get("template.validation_boundary")
        assert template is not None
        # Templates are reusable and should have phase=None
        assert template.phase is None

    def test_gate_boundary_template_is_validation_boundary_instance(self) -> None:
        from arnold_pipelines.megaplan.workflows.boundary_contracts import (
            TYPED_BOUNDARY_TEMPLATES_BY_ID,
            ValidationBoundary,
        )

        template = TYPED_BOUNDARY_TEMPLATES_BY_ID.get("template.validation_boundary")
        assert template is not None
        assert template is ValidationBoundary

    def test_gate_registration_contract_ids_match_boundary_contracts(self) -> None:
        from arnold_pipelines.megaplan.template_registry import get_template_registration
        from arnold_pipelines.megaplan.workflows.boundary_contracts import (
            get_contract_by_id,
        )

        reg = get_template_registration("gate")
        assert reg is not None
        for cid in reg.boundary_contract_ids:
            contract = get_contract_by_id(cid)
            assert contract is not None, f"Contract {cid!r} not found"

    def test_gate_promotion_evidence_scoped_to_gate_phase(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        scratch = plan_dir / "gate_output.json"
        scratch.write_text('{"checks": [], "flags": []}', encoding="utf-8")
        evidence = build_promotion_evidence(
            plan_dir,
            "filled",
            phase_identity="gate",
            scratch_filename="gate_output.json",
        )
        # All evidence records should be scoped to gate
        for rec in evidence:
            assert rec["phase_identity"] == "gate"


class TestFinalizeBoundaryTemplateUse:
    """Finalize phase explicitly uses reusable boundary template."""

    def test_finalize_registration_references_artifact_promotion(self) -> None:
        from arnold_pipelines.megaplan.template_registry import get_template_registration

        reg = get_template_registration("finalize")
        assert reg is not None
        assert reg.boundary_template_id == "template.artifact_promotion"

    def test_finalize_boundary_template_has_phase_none(self) -> None:
        from arnold_pipelines.megaplan.workflows.boundary_contracts import (
            TYPED_BOUNDARY_TEMPLATES_BY_ID,
        )

        template = TYPED_BOUNDARY_TEMPLATES_BY_ID.get("template.artifact_promotion")
        assert template is not None
        assert template.phase is None

    def test_finalize_boundary_template_is_artifact_promotion_instance(self) -> None:
        from arnold_pipelines.megaplan.workflows.boundary_contracts import (
            TYPED_BOUNDARY_TEMPLATES_BY_ID,
            artifact_promotion_template,
        )

        template = TYPED_BOUNDARY_TEMPLATES_BY_ID.get("template.artifact_promotion")
        assert template is not None
        assert template is artifact_promotion_template

    def test_finalize_registration_contract_ids_match_boundary_contracts(self) -> None:
        from arnold_pipelines.megaplan.template_registry import get_template_registration
        from arnold_pipelines.megaplan.workflows.boundary_contracts import (
            get_contract_by_id,
        )

        reg = get_template_registration("finalize")
        assert reg is not None
        for cid in reg.boundary_contract_ids:
            contract = get_contract_by_id(cid)
            assert contract is not None, f"Contract {cid!r} not found"

    def test_finalize_promotion_evidence_scoped_to_finalize_phase(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
        )

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        scratch = plan_dir / "finalize_output.json"
        scratch.write_text('{"tasks": [], "sense_checks": [], "watch_items": []}', encoding="utf-8")
        evidence = build_promotion_evidence(
            plan_dir,
            "filled",
            phase_identity="finalize",
            scratch_filename="finalize_output.json",
        )
        for rec in evidence:
            assert rec["phase_identity"] == "finalize"
