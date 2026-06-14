"""Acceptance tests for the unified agent dispatcher (m11).

Covers:
* WorkerResult ↔ AgentResult round-trip identity
* Flag-gated dispatch parity (flag OFF vs ON) for all three backends
* record_step_routing arg parity between flag OFF and ON paths
* sys.modules zero-leak re-confirmation
"""

from __future__ import annotations

import json
import os
from argparse import Namespace
from pathlib import Path
from unittest import mock

import pytest

from arnold.agent.contracts import AgentRequest, AgentResult
from arnold.agent.dispatcher import ArnoldDispatcher
from arnold.pipelines.megaplan.types import AgentMode
from arnold.pipelines.megaplan.workers._impl import WorkerResult


# ---------------------------------------------------------------------------
# Inline state helper (avoids the pre-existing _workers_helpers import chain
# that resolves to the stale main-repo copy when running from a worktree).
# ---------------------------------------------------------------------------


def _mock_state(tmp_path: Path, *, iteration: int = 1) -> tuple[Path, dict]:
    """Create a minimal PlanState fixture on disk and return (plan_dir, state_dict)."""
    try:
        from arnold.pipelines.megaplan.workers import _build_mock_payload  # type: ignore[attr-defined]
    except ImportError:
        _build_mock_payload = None  # type: ignore[assignment]

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    state = {
        "name": "test-plan",
        "idea": "test the mock workers",
        "current_state": "critiqued",
        "iteration": iteration,
        "created_at": "2026-03-20T00:00:00Z",
        "config": {
            "project_dir": str(project_dir),
            "auto_approve": False,
            "robustness": "standard",
        },
        "sessions": {},
        "plan_versions": [
            {
                "version": iteration,
                "file": f"plan_v{iteration}.md",
                "hash": "sha256:test",
                "timestamp": "2026-03-20T00:00:00Z",
            }
        ],
        "history": [],
        "meta": {
            "significant_counts": [],
            "weighted_scores": [],
            "plan_deltas": [],
            "recurring_critiques": [],
            "total_cost_usd": 0.0,
            "overrides": [],
            "notes": [],
        },
        "last_gate": {},
    }
    (plan_dir / f"plan_v{iteration}.md").write_text("# Plan\nDo it.\n", encoding="utf-8")
    (plan_dir / f"plan_v{iteration}.meta.json").write_text(
        json.dumps(
            {
                "version": iteration,
                "timestamp": "2026-03-20T00:00:00Z",
                "hash": "sha256:test",
                "success_criteria": [
                    {"criterion": "criterion", "priority": "must", "requires": []}
                ],
                "questions": [],
                "assumptions": [],
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "faults.json").write_text(json.dumps({"flags": []}), encoding="utf-8")
    (plan_dir / "gate.json").write_text(
        json.dumps(
            {
                "passed": True,
                "recommendation": "PROCEED",
                "rationale": "ok",
                "signals_assessment": "ok",
                "warnings": [],
                "settled_decisions": [],
                "criteria_check": {},
                "preflight_results": {},
                "unresolved_flags": [],
                "override_forced": False,
            }
        ),
        encoding="utf-8",
    )
    if _build_mock_payload is not None:
        (plan_dir / "execution.json").write_text(
            json.dumps(_build_mock_payload("execute", state, plan_dir, output="done")),
            encoding="utf-8",
        )
        (plan_dir / "finalize.json").write_text(
            json.dumps(
                _build_mock_payload(
                    "finalize",
                    state,
                    plan_dir,
                    watch_items=["Watch repository assumptions."],
                    tasks=[
                        {
                            "id": "T1",
                            "description": "Do work",
                            "depends_on": [],
                            "status": "pending",
                            "executor_notes": "",
                            "files_changed": [],
                            "commands_run": [],
                            "evidence_files": [],
                            "reviewer_verdict": "",
                        },
                        {
                            "id": "T2",
                            "description": "Verify work",
                            "depends_on": ["T1"],
                            "status": "pending",
                            "executor_notes": "",
                            "files_changed": [],
                            "commands_run": [],
                            "evidence_files": [],
                            "reviewer_verdict": "",
                        },
                    ],
                    sense_checks=[
                        {
                            "id": "SC1",
                            "task_id": "T1",
                            "question": "Did it work?",
                            "executor_note": "",
                            "verdict": "",
                        },
                        {
                            "id": "SC2",
                            "task_id": "T2",
                            "question": "Was it verified?",
                            "executor_note": "",
                            "verdict": "",
                        },
                    ],
                    meta_commentary="Mock finalize output.",
                )
            ),
            encoding="utf-8",
        )
    return plan_dir, state


# ---------------------------------------------------------------------------
# Canned WorkerResult factory
# ---------------------------------------------------------------------------


def _canned_worker(**overrides: object) -> WorkerResult:
    """Return a WorkerResult with full fields set for round-trip testing."""
    base = {
        "payload": {"response": "Hello, world!", "completed": True},
        "raw_output": "Hello, world!",
        "duration_ms": 420,
        "cost_usd": 0.0042,
        "session_id": "sess-canary",
        "trace_output": "trace-data",
        "rendered_prompt": "What is the answer?",
        "model_actual": "deepseek/deepseek-chat",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "shannon_plan": {"kind": "plan-review", "session_id": "sess-canary"},
    }
    base.update(overrides)  # type: ignore[arg-type]
    return WorkerResult(**base)  # type: ignore[arg-type]


def _canned_agent_result() -> AgentResult:
    """Return an AgentResult matching _canned_worker()."""
    return _canned_worker().to_agent_result()


# ---------------------------------------------------------------------------
# Round-trip identity
# ---------------------------------------------------------------------------


class TestRoundTripIdentity:
    """WorkerResult → AgentResult → WorkerResult preserves all fields."""

    def test_full_worker_to_agent_and_back_preserves_all_fields(self):
        """Round-trip through to_agent_result / from_agent_result is lossless."""
        original = _canned_worker()
        agent_result = original.to_agent_result()
        assert isinstance(agent_result, AgentResult)

        round_tripped = WorkerResult.from_agent_result(agent_result)
        assert isinstance(round_tripped, WorkerResult)

        for field_name in (
            "payload",
            "raw_output",
            "duration_ms",
            "cost_usd",
            "session_id",
            "trace_output",
            "rendered_prompt",
            "model_actual",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "shannon_plan",
        ):
            original_val = getattr(original, field_name)
            rt_val = getattr(round_tripped, field_name)
            assert rt_val == original_val, (
                f"Field '{field_name}' diverged: {rt_val!r} != {original_val!r}"
            )

    def test_round_trip_with_minimal_worker(self):
        """Minimal WorkerResult (defaults) round-trips correctly."""
        minimal = WorkerResult(
            payload={},
            raw_output="",
            duration_ms=0,
            cost_usd=0.0,
        )
        agent_result = minimal.to_agent_result()
        round_tripped = WorkerResult.from_agent_result(agent_result)

        assert round_tripped.payload == {}
        assert round_tripped.raw_output == ""
        assert round_tripped.duration_ms == 0
        assert round_tripped.cost_usd == 0.0
        assert round_tripped.session_id is None
        assert round_tripped.prompt_tokens == 0
        assert round_tripped.completion_tokens == 0
        assert round_tripped.total_tokens == 0

    def test_round_trip_with_none_session_id(self):
        """WorkerResult with session_id=None round-trips correctly."""
        original = _canned_worker(session_id=None)
        agent_result = original.to_agent_result()
        round_tripped = WorkerResult.from_agent_result(agent_result)
        assert round_tripped.session_id is None

    def test_round_trip_with_none_shannon_plan(self):
        """WorkerResult with shannon_plan=None round-trips correctly."""
        original = _canned_worker(shannon_plan=None)
        agent_result = original.to_agent_result()
        round_tripped = WorkerResult.from_agent_result(agent_result)
        assert round_tripped.shannon_plan is None


# ---------------------------------------------------------------------------
# Flag-gated dispatch parity: hermes
# ---------------------------------------------------------------------------


class _FakeDeepSeekAdapter:
    """A callable fake that returns a canned AgentResult without touching AIAgent."""

    def __init__(self, canned: AgentResult):
        self._canned = canned

    def __call__(self, request: AgentRequest) -> AgentResult:
        return self._canned


class TestFlagGateHermesParity:
    """Verify flag OFF and flag ON produce identical WorkerResult +
    identical record_step_routing args for the hermes backend."""

    def test_hermes_flag_off_on_parity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        from arnold.pipelines.megaplan.workers import run_step_with_worker

        plan_dir, state = _mock_state(tmp_path)
        args = Namespace(
            agent=None,
            ephemeral=False,
            fresh=False,
            persist=False,
            confirm_self_review=False,
            hermes=None,
            phase_model=[],
        )
        canned_wr = _canned_worker()
        canned_ar = _canned_agent_result()

        # --- Flag OFF ---
        monkeypatch.delenv("MEGAPLAN_USE_AGENT_DISPATCHER", raising=False)
        with mock.patch(
            "arnold.pipelines.megaplan.workers.hermes.run_hermes_step",
            return_value=canned_wr,
        ) as mock_hermes:
            result_off, agent_off, mode_off, refreshed_off = run_step_with_worker(
                "review",
                state,
                plan_dir,
                args,
                root=tmp_path,
                resolved=AgentMode(
                    agent="hermes",
                    mode="default",
                    refreshed=False,
                    model="deepseek/deepseek-chat",
                ),
                record_routing=False,
            )

        assert result_off.payload == canned_wr.payload
        assert result_off.raw_output == canned_wr.raw_output
        mock_hermes.assert_called_once()

        # --- Flag ON ---
        monkeypatch.setenv("MEGAPLAN_USE_AGENT_DISPATCHER", "1")
        # Replace DeepSeekAdapter with a fake so we don't need a real AIAgent
        fake_adapter = _FakeDeepSeekAdapter(canned_ar)
        with mock.patch(
            "arnold.agent.adapters.deepseek.DeepSeekAdapter",
            return_value=fake_adapter,
        ):
            result_on, agent_on, mode_on, refreshed_on = run_step_with_worker(
                "review",
                state,
                plan_dir,
                args,
                root=tmp_path,
                resolved=AgentMode(
                    agent="hermes",
                    mode="default",
                    refreshed=False,
                    model="deepseek/deepseek-chat",
                ),
                record_routing=False,
            )

        assert result_on.payload == canned_wr.payload
        assert result_on.raw_output == canned_wr.raw_output

        # Both paths should return the same effective agent/mode
        assert agent_off == agent_on == "hermes"
        assert mode_off == mode_on

    def test_hermes_flag_parity_record_routing_args(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """record_step_routing receives identical args on both code paths."""
        from arnold.pipelines.megaplan.workers import run_step_with_worker

        plan_dir, state = _mock_state(tmp_path)
        args = Namespace(
            agent=None,
            ephemeral=False,
            fresh=False,
            persist=False,
            confirm_self_review=False,
            hermes=None,
            phase_model=[],
        )
        canned_wr = _canned_worker()
        canned_ar = _canned_agent_result()
        fake_adapter = _FakeDeepSeekAdapter(canned_ar)

        routing_calls_off: list[dict] = []
        routing_calls_on: list[dict] = []

        # record_step_routing(plan_dir, *, phase=..., ...) — positional plan_dir
        def _capture_off(*args: object, **kwargs: object) -> None:
            routing_calls_off.append({"plan_dir": args[0], **kwargs})

        def _capture_on(*args: object, **kwargs: object) -> None:
            routing_calls_on.append({"plan_dir": args[0], **kwargs})

        # --- Flag OFF ---
        monkeypatch.delenv("MEGAPLAN_USE_AGENT_DISPATCHER", raising=False)
        with mock.patch(
            "arnold.pipelines.megaplan.workers.hermes.run_hermes_step",
            return_value=canned_wr,
        ):
            with mock.patch(
                "arnold.pipelines.megaplan.workers._impl.record_step_routing",
                side_effect=_capture_off,
            ):
                run_step_with_worker(
                    "review",
                    state,
                    plan_dir,
                    args,
                    root=tmp_path,
                    resolved=AgentMode(
                        agent="hermes",
                        mode="default",
                        refreshed=False,
                        model="deepseek/deepseek-chat",
                    ),
                    record_routing=True,
                    ledger_phase="review",
                    ledger_step_label="review-step",
                )

        # --- Flag ON ---
        monkeypatch.setenv("MEGAPLAN_USE_AGENT_DISPATCHER", "1")
        with mock.patch(
            "arnold.agent.adapters.deepseek.DeepSeekAdapter",
            return_value=fake_adapter,
        ):
            with mock.patch(
                "arnold.pipelines.megaplan.workers._impl.record_step_routing",
                side_effect=_capture_on,
            ):
                run_step_with_worker(
                    "review",
                    state,
                    plan_dir,
                    args,
                    root=tmp_path,
                    resolved=AgentMode(
                        agent="hermes",
                        mode="default",
                        refreshed=False,
                        model="deepseek/deepseek-chat",
                    ),
                    record_routing=True,
                    ledger_phase="review",
                    ledger_step_label="review-step",
                )

        assert len(routing_calls_off) == 1
        assert len(routing_calls_on) == 1

        off = routing_calls_off[0]
        on = routing_calls_on[0]

        for key in (
            "phase",
            "step_label",
            "agent",
            "selected_spec",
            "resolved_model",
            "tier",
            "complexity",
            "tier_routing_active",
        ):
            assert on.get(key) == off.get(key), (
                f"record_step_routing '{key}' differs: "
                f"ON={on.get(key)!r} OFF={off.get(key)!r}"
            )
        assert str(on["plan_dir"]) == str(off["plan_dir"])


# ---------------------------------------------------------------------------
# Flag-gated dispatch parity: codex
# ---------------------------------------------------------------------------


class TestFlagGateCodexParity:
    """Verify flag OFF and flag ON produce identical WorkerResult +
    identical record_step_routing args for the codex backend."""

    def test_codex_flag_off_on_parity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        from arnold.pipelines.megaplan.workers import run_step_with_worker

        plan_dir, state = _mock_state(tmp_path)
        args = Namespace(
            agent=None,
            ephemeral=False,
            fresh=False,
            persist=False,
            confirm_self_review=False,
            hermes=None,
            phase_model=[],
        )
        canned = _canned_worker(
            model_actual="gpt-5.5",
            session_id="codex-sess",
        )

        # --- Flag OFF ---
        monkeypatch.delenv("MEGAPLAN_USE_AGENT_DISPATCHER", raising=False)
        with mock.patch(
            "arnold.pipelines.megaplan.workers._impl.run_codex_step",
            return_value=canned,
        ) as mock_codex:
            result_off, agent_off, mode_off, refreshed_off = run_step_with_worker(
                "execute",
                state,
                plan_dir,
                args,
                root=tmp_path,
                resolved=AgentMode(
                    agent="codex",
                    mode="default",
                    refreshed=False,
                    model="codex:gpt-5.5",
                    resolved_model="gpt-5.5",
                ),
                record_routing=False,
            )

        assert result_off.payload == canned.payload
        assert result_off.raw_output == canned.raw_output
        mock_codex.assert_called_once()

        # --- Flag ON ---
        monkeypatch.setenv("MEGAPLAN_USE_AGENT_DISPATCHER", "1")
        with mock.patch(
            "arnold.pipelines.megaplan.workers._impl.run_codex_step",
            return_value=canned,
        ) as mock_codex_on:
            result_on, agent_on, mode_on, refreshed_on = run_step_with_worker(
                "execute",
                state,
                plan_dir,
                args,
                root=tmp_path,
                resolved=AgentMode(
                    agent="codex",
                    mode="default",
                    refreshed=False,
                    model="codex:gpt-5.5",
                    resolved_model="gpt-5.5",
                ),
                record_routing=False,
            )

        assert result_on.payload == canned.payload
        assert result_on.raw_output == canned.raw_output
        assert agent_off == agent_on == "codex"

    def test_codex_flag_parity_record_routing_args(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """record_step_routing receives identical args on both code paths for codex."""
        from arnold.pipelines.megaplan.workers import run_step_with_worker

        plan_dir, state = _mock_state(tmp_path)
        args = Namespace(
            agent=None,
            ephemeral=False,
            fresh=False,
            persist=False,
            confirm_self_review=False,
            hermes=None,
            phase_model=[],
        )
        canned = _canned_worker(
            model_actual="gpt-5.5",
            session_id="codex-sess",
        )

        routing_calls_off: list[dict] = []
        routing_calls_on: list[dict] = []

        def _capture_off(*args: object, **kwargs: object) -> None:
            routing_calls_off.append({"plan_dir": args[0], **kwargs})

        def _capture_on(*args: object, **kwargs: object) -> None:
            routing_calls_on.append({"plan_dir": args[0], **kwargs})

        # --- Flag OFF ---
        monkeypatch.delenv("MEGAPLAN_USE_AGENT_DISPATCHER", raising=False)
        with mock.patch(
            "arnold.pipelines.megaplan.workers._impl.run_codex_step",
            return_value=canned,
        ):
            with mock.patch(
                "arnold.pipelines.megaplan.workers._impl.record_step_routing",
                side_effect=_capture_off,
            ):
                run_step_with_worker(
                    "execute",
                    state,
                    plan_dir,
                    args,
                    root=tmp_path,
                    resolved=AgentMode(
                        agent="codex",
                        mode="default",
                        refreshed=False,
                        model="codex:gpt-5.5",
                        resolved_model="gpt-5.5",
                    ),
                    record_routing=True,
                    ledger_phase="execute",
                    ledger_step_label="execute-step",
                )

        # --- Flag ON ---
        monkeypatch.setenv("MEGAPLAN_USE_AGENT_DISPATCHER", "1")
        with mock.patch(
            "arnold.pipelines.megaplan.workers._impl.run_codex_step",
            return_value=canned,
        ):
            with mock.patch(
                "arnold.pipelines.megaplan.workers._impl.record_step_routing",
                side_effect=_capture_on,
            ):
                run_step_with_worker(
                    "execute",
                    state,
                    plan_dir,
                    args,
                    root=tmp_path,
                    resolved=AgentMode(
                        agent="codex",
                        mode="default",
                        refreshed=False,
                        model="codex:gpt-5.5",
                        resolved_model="gpt-5.5",
                    ),
                    record_routing=True,
                    ledger_phase="execute",
                    ledger_step_label="execute-step",
                )

        assert len(routing_calls_off) == 1
        assert len(routing_calls_on) == 1

        off = routing_calls_off[0]
        on = routing_calls_on[0]

        for key in (
            "phase",
            "step_label",
            "agent",
            "selected_spec",
            "resolved_model",
            "tier",
            "complexity",
            "tier_routing_active",
        ):
            assert on.get(key) == off.get(key), (
                f"record_step_routing '{key}' differs: "
                f"ON={on.get(key)!r} OFF={off.get(key)!r}"
            )
        assert str(on["plan_dir"]) == str(off["plan_dir"])


# ---------------------------------------------------------------------------
# Flag-gated dispatch parity: claude (shannon)
# ---------------------------------------------------------------------------


class TestFlagGateClaudeParity:
    """Verify flag OFF and flag ON produce identical WorkerResult +
    identical record_step_routing args for the claude (shannon) backend."""

    def test_claude_flag_off_on_parity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        from arnold.pipelines.megaplan.workers import run_step_with_worker

        plan_dir, state = _mock_state(tmp_path)
        args = Namespace(
            agent=None,
            ephemeral=False,
            fresh=False,
            persist=False,
            confirm_self_review=False,
            hermes=None,
            phase_model=[],
        )
        canned = _canned_worker(
            model_actual="anthropic/claude-sonnet-4-20250514",
            session_id="claude-sess",
            shannon_plan={"kind": "plan", "session_id": "claude-sess"},
        )

        # --- Flag OFF ---
        monkeypatch.delenv("MEGAPLAN_USE_AGENT_DISPATCHER", raising=False)
        with mock.patch(
            "arnold.pipelines.megaplan.workers.shannon.run_shannon_step",
            return_value=canned,
        ) as mock_shannon:
            result_off, agent_off, mode_off, refreshed_off = run_step_with_worker(
                "plan",
                state,
                plan_dir,
                args,
                root=tmp_path,
                resolved=AgentMode(
                    agent="claude",
                    mode="default",
                    refreshed=False,
                    model="anthropic:claude-sonnet-4-20250514",
                    resolved_model="claude-sonnet-4-20250514",
                ),
                record_routing=False,
            )

        assert result_off.payload == canned.payload
        assert result_off.raw_output == canned.raw_output
        mock_shannon.assert_called_once()

        # --- Flag ON ---
        monkeypatch.setenv("MEGAPLAN_USE_AGENT_DISPATCHER", "1")
        with mock.patch(
            "arnold.pipelines.megaplan.workers.shannon.run_shannon_step",
            return_value=canned,
        ) as mock_shannon_on:
            result_on, agent_on, mode_on, refreshed_on = run_step_with_worker(
                "plan",
                state,
                plan_dir,
                args,
                root=tmp_path,
                resolved=AgentMode(
                    agent="claude",
                    mode="default",
                    refreshed=False,
                    model="anthropic:claude-sonnet-4-20250514",
                    resolved_model="claude-sonnet-4-20250514",
                ),
                record_routing=False,
            )

        assert result_on.payload == canned.payload
        assert result_on.raw_output == canned.raw_output
        assert agent_off == agent_on == "claude"

    def test_claude_flag_parity_record_routing_args(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """record_step_routing receives identical args on both code paths for claude."""
        from arnold.pipelines.megaplan.workers import run_step_with_worker

        plan_dir, state = _mock_state(tmp_path)
        args = Namespace(
            agent=None,
            ephemeral=False,
            fresh=False,
            persist=False,
            confirm_self_review=False,
            hermes=None,
            phase_model=[],
        )
        canned = _canned_worker(
            model_actual="anthropic/claude-sonnet-4-20250514",
            session_id="claude-sess",
        )

        routing_calls_off: list[dict] = []
        routing_calls_on: list[dict] = []

        def _capture_off(*args: object, **kwargs: object) -> None:
            routing_calls_off.append({"plan_dir": args[0], **kwargs})

        def _capture_on(*args: object, **kwargs: object) -> None:
            routing_calls_on.append({"plan_dir": args[0], **kwargs})

        # --- Flag OFF ---
        monkeypatch.delenv("MEGAPLAN_USE_AGENT_DISPATCHER", raising=False)
        with mock.patch(
            "arnold.pipelines.megaplan.workers.shannon.run_shannon_step",
            return_value=canned,
        ):
            with mock.patch(
                "arnold.pipelines.megaplan.workers._impl.record_step_routing",
                side_effect=_capture_off,
            ):
                run_step_with_worker(
                    "plan",
                    state,
                    plan_dir,
                    args,
                    root=tmp_path,
                    resolved=AgentMode(
                        agent="claude",
                        mode="default",
                        refreshed=False,
                        model="anthropic:claude-sonnet-4-20250514",
                        resolved_model="claude-sonnet-4-20250514",
                    ),
                    record_routing=True,
                    ledger_phase="plan",
                    ledger_step_label="plan-step",
                )

        # --- Flag ON ---
        monkeypatch.setenv("MEGAPLAN_USE_AGENT_DISPATCHER", "1")
        with mock.patch(
            "arnold.pipelines.megaplan.workers.shannon.run_shannon_step",
            return_value=canned,
        ):
            with mock.patch(
                "arnold.pipelines.megaplan.workers._impl.record_step_routing",
                side_effect=_capture_on,
            ):
                run_step_with_worker(
                    "plan",
                    state,
                    plan_dir,
                    args,
                    root=tmp_path,
                    resolved=AgentMode(
                        agent="claude",
                        mode="default",
                        refreshed=False,
                        model="anthropic:claude-sonnet-4-20250514",
                        resolved_model="claude-sonnet-4-20250514",
                    ),
                    record_routing=True,
                    ledger_phase="plan",
                    ledger_step_label="plan-step",
                )

        assert len(routing_calls_off) == 1
        assert len(routing_calls_on) == 1

        off = routing_calls_off[0]
        on = routing_calls_on[0]

        for key in (
            "phase",
            "step_label",
            "agent",
            "selected_spec",
            "resolved_model",
            "tier",
            "complexity",
            "tier_routing_active",
        ):
            assert on.get(key) == off.get(key), (
                f"record_step_routing '{key}' differs: "
                f"ON={on.get(key)!r} OFF={off.get(key)!r}"
            )
        assert str(on["plan_dir"]) == str(off["plan_dir"])


# ---------------------------------------------------------------------------
# Flag-gated dispatch parity: shannon (explicit)
# ---------------------------------------------------------------------------


class TestFlagGateShannonParity:
    """Verify flag OFF and flag ON produce identical results for the
    explicit 'shannon' backend."""

    def test_shannon_flag_off_on_parity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        from arnold.pipelines.megaplan.workers import run_step_with_worker

        plan_dir, state = _mock_state(tmp_path)
        args = Namespace(
            agent=None,
            ephemeral=False,
            fresh=False,
            persist=False,
            confirm_self_review=False,
            hermes=None,
            phase_model=[],
        )
        canned = _canned_worker(
            model_actual="anthropic/claude-opus-4-20250514",
            session_id="shannon-sess",
        )

        # --- Flag OFF ---
        monkeypatch.delenv("MEGAPLAN_USE_AGENT_DISPATCHER", raising=False)
        with mock.patch(
            "arnold.pipelines.megaplan.workers.shannon.run_shannon_step",
            return_value=canned,
        ) as mock_shannon:
            result_off, agent_off, mode_off, refreshed_off = run_step_with_worker(
                "plan",
                state,
                plan_dir,
                args,
                root=tmp_path,
                resolved=AgentMode(
                    agent="shannon",
                    mode="default",
                    refreshed=False,
                    model="anthropic:claude-opus-4-20250514",
                    resolved_model="claude-opus-4-20250514",
                ),
                record_routing=False,
            )

        assert result_off.payload == canned.payload
        assert agent_off == "shannon"
        mock_shannon.assert_called_once()

        # --- Flag ON ---
        monkeypatch.setenv("MEGAPLAN_USE_AGENT_DISPATCHER", "1")
        with mock.patch(
            "arnold.pipelines.megaplan.workers.shannon.run_shannon_step",
            return_value=canned,
        ) as mock_shannon_on:
            result_on, agent_on, mode_on, refreshed_on = run_step_with_worker(
                "plan",
                state,
                plan_dir,
                args,
                root=tmp_path,
                resolved=AgentMode(
                    agent="shannon",
                    mode="default",
                    refreshed=False,
                    model="anthropic:claude-opus-4-20250514",
                    resolved_model="claude-opus-4-20250514",
                ),
                record_routing=False,
            )

        assert result_on.payload == canned.payload
        assert agent_on == "shannon"


# ---------------------------------------------------------------------------
# Flag-ON dispatcher structure verification
# ---------------------------------------------------------------------------


class TestFlagOnDispatcherStructure:
    """Verify the dispatcher structure when flag is ON."""

    def test_dispatcher_is_fresh_per_call(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Each invocation creates a new ArnoldDispatcher (no module-level cache)."""
        from arnold.pipelines.megaplan.workers import run_step_with_worker

        plan_dir, state = _mock_state(tmp_path)
        args = Namespace(
            agent=None,
            ephemeral=False,
            fresh=False,
            persist=False,
            confirm_self_review=False,
            hermes=None,
            phase_model=[],
        )
        canned_wr = _canned_worker()
        canned_ar = _canned_agent_result()
        fake_adapter = _FakeDeepSeekAdapter(canned_ar)

        dispatcher_ids: list[int] = []

        class TrackingDispatcher(ArnoldDispatcher):
            def __init__(self):
                super().__init__()
                dispatcher_ids.append(id(self))

        monkeypatch.setenv("MEGAPLAN_USE_AGENT_DISPATCHER", "1")
        with mock.patch(
            "arnold.agent.adapters.deepseek.DeepSeekAdapter",
            return_value=fake_adapter,
        ):
            with mock.patch(
                "arnold.agent.ArnoldDispatcher",
                TrackingDispatcher,
            ):
                run_step_with_worker(
                    "review",
                    state,
                    plan_dir,
                    args,
                    root=tmp_path,
                    resolved=AgentMode(
                        agent="hermes",
                        mode="default",
                        refreshed=False,
                        model="deepseek/deepseek-chat",
                    ),
                    record_routing=False,
                )
                run_step_with_worker(
                    "review",
                    state,
                    plan_dir,
                    args,
                    root=tmp_path,
                    resolved=AgentMode(
                        agent="hermes",
                        mode="default",
                        refreshed=False,
                        model="deepseek/deepseek-chat",
                    ),
                    record_routing=False,
                )

        # Two calls should produce two distinct dispatcher instances
        assert len(dispatcher_ids) == 2
        assert dispatcher_ids[0] != dispatcher_ids[1]

    def test_all_three_backends_registered_on_flag_on(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """When flag is ON, hermes dispatches without LookupError."""
        from arnold.pipelines.megaplan.workers import run_step_with_worker

        plan_dir, state = _mock_state(tmp_path)
        args = Namespace(
            agent=None,
            ephemeral=False,
            fresh=False,
            persist=False,
            confirm_self_review=False,
            hermes=None,
            phase_model=[],
        )
        canned_ar = _canned_agent_result()
        fake_adapter = _FakeDeepSeekAdapter(canned_ar)

        monkeypatch.setenv("MEGAPLAN_USE_AGENT_DISPATCHER", "1")
        with mock.patch(
            "arnold.agent.adapters.deepseek.DeepSeekAdapter",
            return_value=fake_adapter,
        ):
            result, agent, mode, refreshed = run_step_with_worker(
                "review",
                state,
                plan_dir,
                args,
                root=tmp_path,
                resolved=AgentMode(
                    agent="hermes",
                    mode="default",
                    refreshed=False,
                    model="deepseek/deepseek-chat",
                ),
                record_routing=False,
            )

        assert result is not None
        assert agent == "hermes"

    def test_codex_does_not_raise_lookuperror(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """codex dispatch on flag-ON does not raise LookupError."""
        from arnold.pipelines.megaplan.workers import run_step_with_worker

        plan_dir, state = _mock_state(tmp_path)
        args = Namespace(
            agent=None,
            ephemeral=False,
            fresh=False,
            persist=False,
            confirm_self_review=False,
            hermes=None,
            phase_model=[],
        )
        canned = _canned_worker(
            model_actual="gpt-5.5",
            session_id="codex-sess",
        )

        monkeypatch.setenv("MEGAPLAN_USE_AGENT_DISPATCHER", "1")
        with mock.patch(
            "arnold.pipelines.megaplan.workers._impl.run_codex_step",
            return_value=canned,
        ):
            result, agent, mode, refreshed = run_step_with_worker(
                "execute",
                state,
                plan_dir,
                args,
                root=tmp_path,
                resolved=AgentMode(
                    agent="codex",
                    mode="default",
                    refreshed=False,
                    model="codex:gpt-5.5",
                    resolved_model="gpt-5.5",
                ),
                record_routing=False,
            )

        assert result is not None
        assert agent == "codex"

    def test_claude_does_not_raise_lookuperror(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """claude dispatch on flag-ON does not raise LookupError."""
        from arnold.pipelines.megaplan.workers import run_step_with_worker

        plan_dir, state = _mock_state(tmp_path)
        args = Namespace(
            agent=None,
            ephemeral=False,
            fresh=False,
            persist=False,
            confirm_self_review=False,
            hermes=None,
            phase_model=[],
        )
        canned = _canned_worker(
            model_actual="anthropic/claude-sonnet-4-20250514",
            session_id="claude-sess",
        )

        monkeypatch.setenv("MEGAPLAN_USE_AGENT_DISPATCHER", "1")
        with mock.patch(
            "arnold.pipelines.megaplan.workers.shannon.run_shannon_step",
            return_value=canned,
        ):
            result, agent, mode, refreshed = run_step_with_worker(
                "plan",
                state,
                plan_dir,
                args,
                root=tmp_path,
                resolved=AgentMode(
                    agent="claude",
                    mode="default",
                    refreshed=False,
                    model="anthropic:claude-sonnet-4-20250514",
                    resolved_model="claude-sonnet-4-20250514",
                ),
                record_routing=False,
            )

        assert result is not None
        assert agent == "claude"


# ---------------------------------------------------------------------------
# Zero-leak re-confirmation
# ---------------------------------------------------------------------------


class TestZeroLeakAcceptance:
    """Acceptance-level zero-leak checks."""

    def test_no_megaplan_imports_in_arnold_agent_package(self):
        """Confirm the zero-leak gate holds across the entire arnold.agent package."""
        import ast
        import inspect
        from pathlib import Path

        import arnold.agent

        megaplan_ref = "arnold.pipelines.megaplan"
        agent_dir = Path(inspect.getfile(arnold.agent)).parent

        py_files = list(agent_dir.rglob("*.py"))
        assert len(py_files) > 0, "Expected .py files in arnold/agent/"

        violations: list[str] = []
        for path in py_files:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.ImportFrom):
                        if node.module and megaplan_ref in node.module:
                            violations.append(f"{path}: from {node.module}")
                    else:
                        for alias in node.names:
                            if megaplan_ref in alias.name:
                                violations.append(f"{path}: import {alias.name}")

        if violations:
            raise AssertionError(
                "Zero-leak gate violated:\n" + "\n".join(violations)
            )

    def test_agent_package_exports_are_importable(self):
        """All key public surface names are importable from arnold.agent."""
        from arnold.agent import (
            AgentDispatcher,
            AgentMode,
            AgentRequest,
            AgentResult,
            ArnoldDispatcher,
            BackendAdapter,
            DeepSeekAdapter,
            dispatch,
            register,
        )

        # Verify the default dispatcher is functional
        assert callable(dispatch)
        assert callable(register)
        assert isinstance(ArnoldDispatcher(), AgentDispatcher)
