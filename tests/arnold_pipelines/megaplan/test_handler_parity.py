"""Handler semantic parity tests.

These tests exercise relocated product handler helpers directly with controlled
inputs. They are cheap, do not require LLM calls, and lock behavioral semantics
that must survive the move from ``arnold_pipelines.megaplan`` to
``arnold_pipelines.megaplan``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.handlers.structured_output import (
    _strip_unknown_keys,
    classify_scratch,
    promote_scratch,
)
from arnold_pipelines.megaplan.workers import WorkerResult


class TestAdaptiveCritiqueRouting:
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
    def test_apply_gate_outcome_proceed_when_passed(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.gate import _apply_gate_outcome
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
        result, next_step, msg, blocking = _apply_gate_outcome(
            state, summary, robustness="standard", plan_dir=tmp_path
        )
        assert result == "success"
        assert next_step == "finalize"
        assert state["current_state"] == STATE_GATED

    def test_apply_gate_outcome_iterate_routes_to_revise(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.gate import _apply_gate_outcome

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
        result, next_step, msg, blocking = _apply_gate_outcome(
            state, summary, robustness="standard", plan_dir=tmp_path
        )
        assert result == "success"
        assert next_step == "revise"

    def test_apply_gate_outcome_auto_downgrade_proceed_to_iterate(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.handlers.gate import _apply_gate_outcome

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
        result, next_step, msg, blocking = _apply_gate_outcome(
            state, summary, robustness="standard", plan_dir=tmp_path
        )
        assert result == "unresolved_flags"
        assert next_step == "gate"
        assert blocking


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

    def test_none_finalize_baseline_scope_skips_capture(
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

        finalize._write_finalize_artifacts(plan_dir, payload, self._state(plan_dir, repo))

        assert payload["test_selection"]["mode"] == "none"
        assert payload["baseline_test_failures"] == []
        assert payload["baseline_test_command"] is None

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
        assert (plan_dir / "gate.json").exists()
        assert (plan_dir / "gate_carry.json").exists()
        assert (plan_dir / "finalize_revise_feedback.json").exists()
        assert infer_next_steps(state)[0] == "revise"

        persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        assert persisted["current_state"] == "critiqued"
        assert persisted["last_gate"]["recommendation"] == "ITERATE"


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
