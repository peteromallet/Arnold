from __future__ import annotations

from pathlib import Path

import pytest

import megaplan
import megaplan.handlers
import megaplan.workers
from megaplan._core import load_plan
from megaplan.workers import WorkerResult, _build_mock_payload
from tests.conftest import PlanFixture, _make_plan_fixture_with_robustness, load_state


def test_tiny_critique_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """At tiny robustness, calling critique manually errors — the phase is skipped
    in the workflow, so plan -> finalize is the canonical path."""
    from megaplan.types import CliError

    fixture = _make_plan_fixture_with_robustness(tmp_path, monkeypatch, robustness="tiny")
    megaplan.handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))

    with pytest.raises(CliError, match="bare robustness skips critique"):
        megaplan.handle_critique(fixture.root, fixture.make_args(plan=fixture.plan_name))


def test_light_critique_routes_to_revise(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_fixture = _make_plan_fixture_with_robustness(tmp_path, monkeypatch, robustness="light")
    make_args = plan_fixture.make_args

    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)

    assert response["next_step"] == "revise"
    assert state["last_gate"]["recommendation"] == "ITERATE"


def test_handle_critique_rejects_invalid_check_payload(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    worker = WorkerResult(
        payload=_build_mock_payload(
            "critique",
            load_state(plan_fixture.plan_dir),
            plan_fixture.plan_dir,
            checks=[],
        ),
        raw_output="invalid critique payload",
        duration_ms=1,
        cost_usd=0.0,
        session_id="critique-invalid",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )
    monkeypatch.setattr(
        megaplan.handlers,
        "validate_critique_checks",
        lambda payload, **kwargs: ["correctness"],
    )

    with pytest.raises(megaplan.CliError, match="Critique output failed check validation"):
        megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    state = load_state(plan_fixture.plan_dir)
    assert state["history"][-1]["result"] == "error"
    assert state.get("active_step") is None
    assert not (plan_fixture.plan_dir / "critique_v1.json").exists()


def test_handle_critique_accepts_validated_checks(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        megaplan.handlers.critique,
        "validate_critique_checks",
        lambda payload, **kwargs: [],
    )

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    assert response["success"] is True
    assert (plan_fixture.plan_dir / "critique_v1.json").exists()


def test_parallel_critique_sets_and_clears_active_step(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After removing the Hermes gate (T19), the multi-check parallel
    critique branch no longer calls set_active_step / clear_active_step.
    This test verifies that run_parallel_critique is dispatched for any
    agent type (not just Hermes) and that no active_step session state
    is leaked."""
    monkeypatch.setattr(
        megaplan.handlers.critique,
        "validate_critique_checks",
        lambda payload, **kwargs: [],
    )
    monkeypatch.setattr(
        megaplan.handlers,
        "resolve_agent_mode",
        lambda step, args: ("codex", "thinking", False, "openai:codex-3"),
    )

    parallel_called: list[bool] = [False]

    def fake_parallel(state, plan_dir, *, root, model, checks, max_concurrent=None, **kwargs):
        parallel_called[0] = True
        return WorkerResult(
            payload={
                "checks": [
                    {
                        "id": check["id"],
                        "summary": "ok",
                        "findings": [],
                    }
                    for check in checks
                ],
                "flags": [],
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
            },
            raw_output="parallel",
            duration_ms=1,
            cost_usd=0.0,
            session_id=None,
        )

    monkeypatch.setattr(megaplan.handlers.critique, "run_parallel_critique", fake_parallel)

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)

    assert response["success"] is True
    assert parallel_called[0] is True, "run_parallel_critique should be dispatched for multi-check, any agent type"
    assert "active_step" not in state, "no Hermes session state should leak"


def test_parallel_critique_fallback_logs_warning(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        megaplan.handlers.critique,
        "validate_critique_checks",
        lambda payload, **kwargs: [],
    )
    monkeypatch.setattr(
        megaplan.handlers,
        "resolve_agent_mode",
        lambda step, args: ("hermes", "persistent", False, "fireworks:model"),
    )
    monkeypatch.setattr(
        megaplan.handlers.critique,
        "run_parallel_critique",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("parallel failed")),
    )

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    caplog.set_level("WARNING", logger="megaplan")
    response = megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    assert response["success"] is True
    assert any("M3A_WARN_PARALLEL_CRITIQUE_FALLBACK" in record.getMessage() for record in caplog.records)


def test_critique_evaluator_model_assignment_does_not_drive_dispatch(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    monkeypatch.setattr(megaplan.handlers.critique, "adaptive_critique_enabled", lambda state: True)
    monkeypatch.setattr(megaplan.handlers.critique, "is_creative_mode", lambda state: False)
    monkeypatch.setattr(
        megaplan.handlers,
        "resolve_agent_mode",
        lambda step, args: ("claude", "persistent", False, "unknown-model"),
    )
    monkeypatch.setattr(
        megaplan.handlers.critique,
        "validate_critique_checks",
        lambda payload, **kwargs: [],
    )

    def fake_run_step(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, **kwargs):
        if step == "critique_evaluator":
            return (
                WorkerResult(
                    payload={
                        "selections": [
                            {
                                "check_id": "correctness",
                                "complexity": 4,
                                "complexity_justification": "Rank parsing fallback probe stays at the correctness floor.",
                                "why": "exercise rank parse fallback",
                            }
                        ],
                        "skipped": [
                            {"check_id": "scope", "why": "test"},
                            {"check_id": "integration", "why": "test"},
                            {"check_id": "risks", "why": "test"},
                            {"check_id": "acceptance", "why": "test"},
                            {"check_id": "human_actions", "why": "test"},
                            {"check_id": "source_touch", "why": "test"},
                            {"check_id": "adjacent_calls", "why": "test"},
                            {"check_id": "overreach", "why": "test"},
                        ],
                        "flag_verifications": [],
                    },
                    raw_output="{}",
                    duration_ms=1,
                    cost_usd=0.0,
                    session_id="eval",
                ),
                "claude",
                "persistent",
                False,
            )
        return (
            WorkerResult(
                payload={"checks": [], "flags": [], "verified_flag_ids": [], "disputed_flag_ids": []},
                raw_output="{}",
                duration_ms=1,
                cost_usd=0.0,
                session_id="critique",
            ),
            "claude",
            "persistent",
            False,
        )

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step)
    monkeypatch.setattr(
        "megaplan.audits.critique_evaluator.roster_rank",
        lambda _model: (_ for _ in ()).throw(ValueError("unknown model")),
    )
    monkeypatch.setattr(
        "megaplan.audits.critique_evaluator.validate_evaluator_verdict",
        lambda payload, **kwargs: None,
    )

    caplog.set_level("WARNING", logger="megaplan")
    response = megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    assert response["success"] is True
    assert not any("M3A_WARN_CRITIQUE_RANK_PARSE" in record.getMessage() for record in caplog.records)


def test_critique_dispatch_carries_effort_into_agentmode(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression (specfix): the non-adaptive critique dispatch must forward the
    resolved effort to the worker. Previously it rebuilt a bare 4-tuple
    ``(agent, mode, refreshed, model)`` and dropped effort, so a `critique`
    slot's effort never reached the codex-effort gate. The handler now hands
    ``_run_worker`` an :class:`AgentMode` carrying ``effort`` and
    ``resolved_model``."""
    from megaplan.types import AgentMode

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    monkeypatch.setattr(megaplan.handlers.critique, "adaptive_critique_enabled", lambda state: False)
    monkeypatch.setattr(megaplan.handlers.critique, "is_creative_mode", lambda state: False)
    monkeypatch.setattr(
        megaplan.handlers,
        "resolve_agent_mode",
        lambda step, args: AgentMode(
            agent="codex",
            mode="persistent",
            refreshed=False,
            model="gpt-5.5",
            effort="high",
            resolved_model="gpt-5.5",
        ),
    )
    monkeypatch.setattr(
        megaplan.handlers.critique,
        "validate_critique_checks",
        lambda payload, **kwargs: [],
    )

    captured: dict[str, object] = {}

    def fake_run_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_kwargs=None, **kwargs):
        captured["resolved"] = resolved
        return (
            WorkerResult(
                payload={"checks": [], "flags": [], "verified_flag_ids": [], "disputed_flag_ids": []},
                raw_output="{}",
                duration_ms=1,
                cost_usd=0.0,
                session_id="critique",
            ),
            "codex",
            "persistent",
            False,
        )

    monkeypatch.setattr(megaplan.handlers, "_run_worker", fake_run_worker)

    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    resolved = captured["resolved"]
    assert isinstance(resolved, AgentMode), "dispatch must pass an AgentMode, not a bare tuple that drops effort"
    assert resolved.effort == "high"
    assert resolved.resolved_model == "gpt-5.5"


def test_critique_prompt_contains_robustness_instruction(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    _, state = load_plan(plan_fixture.root, plan_fixture.plan_name)
    from megaplan.prompts import create_claude_prompt

    prompt = create_claude_prompt("critique", state, plan_fixture.plan_dir)
    assert "Robustness level" in prompt
    assert "standard" in prompt


def test_handle_critique_preserves_verdict_on_recovery(
    plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When validation fails but recovery from critique_output.json succeeds,
    the evaluator verdict is preserved in state metadata and the raw_output note."""
    import json

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    # Build a complete critique_output.json matching the 5 core checks for
    # standard robustness: issue_hints, correctness, scope, all_locations, callers.
    critique_output = {
        "checks": [
            {
                "id": "issue_hints",
                "question": "Did the work fully address the issue hints, user notes, and approved plan requirements?",
                "findings": [{
                    "detail": "Mock finding for issue_hints — sufficiently detailed description to pass validation length check.",
                    "flagged": False,
                }],
            },
            {
                "id": "correctness",
                "question": "Are the proposed changes technically correct?",
                "findings": [{
                    "detail": "Mock finding for correctness — sufficiently detailed description to pass validation length check.",
                    "flagged": False,
                }],
            },
            {
                "id": "scope",
                "question": "Search for related code that handles the same concept. Is the reported issue a symptom of something broader?",
                "findings": [{
                    "detail": "Mock finding for scope — sufficiently detailed description to pass the validation length requirement.",
                    "flagged": False,
                }],
            },
            {
                "id": "all_locations",
                "question": "Does the change touch all locations AND supporting infrastructure?",
                "findings": [{
                    "detail": "Mock finding for all_locations — sufficiently detailed description to pass validation length check.",
                    "flagged": False,
                }],
            },
            {
                "id": "callers",
                "question": "Find the callers of the changed function. What arguments do they actually pass? Does the fix handle all of them?",
                "findings": [{
                    "detail": "Mock finding for callers — sufficiently detailed description for passing the validation length requirement.",
                    "flagged": False,
                }],
            },
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    (plan_fixture.plan_dir / "critique_output.json").write_text(
        json.dumps(critique_output, indent=2) + "\n", encoding="utf-8"
    )

    # Stateful stub: first call -> ["correctness"] (for L97), subsequent -> [] (for L206)
    call_count = [0]

    def stateful_validator(payload, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return ["correctness"]
        return []

    monkeypatch.setattr(
        megaplan.handlers.critique,
        "validate_critique_checks",
        stateful_validator,
    )

    response = megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)

    # (a) Step succeeds
    assert response["success"] is True

    # (b) critique_v1.json exists
    assert (plan_fixture.plan_dir / "critique_v1.json").exists()

    # (c) state["meta"]["critique_validation_warnings"] contains an entry whose
    #     invalid_checks includes "correctness"
    warnings = state["meta"]["critique_validation_warnings"]
    assert len(warnings) >= 1
    assert "correctness" in warnings[-1]["invalid_checks"]

    # (d) The recovered payload names "correctness" — the critique_v1.json
    #     written from the recovered payload must include the correctness check.
    critique_payload = json.loads((plan_fixture.plan_dir / "critique_v1.json").read_text(encoding="utf-8"))
    check_ids = [c["id"] for c in critique_payload.get("checks", [])]
    assert "correctness" in check_ids


def test_handle_critique_adaptive_flag_off_uses_select_active_checks(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression guard: with adaptive_critique=False (default), handle_critique uses
    select_active_checks for active_checks, dispatches no evaluator worker, and
    writes no evaluator_verdict.json — locking the off-path byte-for-byte."""
    import megaplan.handlers as handlers_mod
    import megaplan.handlers.critique as critique_mod

    monkeypatch.setattr(
        critique_mod,
        "validate_critique_checks",
        lambda payload, **kwargs: [],
    )

    select_calls: list = []
    original_select = critique_mod.select_active_checks

    def spy_select(state, robustness, *, plan_dir=None):
        result = original_select(state, robustness, plan_dir=plan_dir)
        select_calls.append(result)
        return result

    monkeypatch.setattr(critique_mod, "select_active_checks", spy_select)

    evaluator_steps: list[str] = []
    original_run_worker = handlers_mod._run_worker

    def spy_run_worker(step, *args, **kwargs):
        if step == "critique_evaluator":
            evaluator_steps.append(step)
        return original_run_worker(step, *args, **kwargs)

    monkeypatch.setattr(handlers_mod, "_run_worker", spy_run_worker)

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    state = load_state(plan_fixture.plan_dir)
    assert state["config"]["adaptive_critique"] is False

    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    assert len(select_calls) >= 1, "select_active_checks must be called on the default off-path"
    assert not evaluator_steps, "critique_evaluator must not be dispatched when adaptive_critique=False"
    assert not (plan_fixture.plan_dir / "evaluator_verdict.json").exists()


# ---------------------------------------------------------------------------
# T7: apply_flag_verifications — outcome state machine
# ---------------------------------------------------------------------------

def test_apply_flag_verifications_verified_sets_status_and_verified_fields(
    tmp_path: Path,
) -> None:
    """'verified' outcome sets status=verified, verified=True, verified_in, and verify_rationale."""
    from megaplan._core import save_flag_registry
    from megaplan.flags import apply_flag_verifications

    registry = {
        "flags": [
            {"id": "FLAG-001", "status": "addressed", "verified": False, "concern": "c1"},
        ]
    }
    save_flag_registry(tmp_path, registry)

    adjudicated = apply_flag_verifications(
        tmp_path,
        [{"flag_id": "FLAG-001", "lens": "correctness", "outcome": "verified", "rationale": "diff supports fix"}],
    )

    from megaplan._core import load_flag_registry
    result = load_flag_registry(tmp_path)
    flag = result["flags"][0]

    assert adjudicated == {"FLAG-001"}
    assert flag["status"] == "verified"
    assert flag["verified"] is True
    assert flag["verified_in"] == "evaluator_verdict.json"
    assert flag["verify_rationale"] == "diff supports fix"


def test_apply_flag_verifications_open_resets_verified_fields(
    tmp_path: Path,
) -> None:
    """'open' outcome resets status=open, clears verified=False and removes verified_in."""
    from megaplan._core import load_flag_registry, save_flag_registry
    from megaplan.flags import apply_flag_verifications

    registry = {
        "flags": [
            {
                "id": "FLAG-002",
                "status": "verified",
                "verified": True,
                "verified_in": "critique_v2.json",
                "concern": "stale verify",
            },
        ]
    }
    save_flag_registry(tmp_path, registry)

    adjudicated = apply_flag_verifications(
        tmp_path,
        [{"flag_id": "FLAG-002", "lens": "scope", "outcome": "open", "rationale": "no-op change"}],
    )

    result = load_flag_registry(tmp_path)
    flag = result["flags"][0]

    assert adjudicated == {"FLAG-002"}
    assert flag["status"] == "open"
    assert flag["verified"] is False
    assert "verified_in" not in flag
    assert flag["verify_rationale"] == "no-op change"


def test_apply_flag_verifications_accepted_tradeoff(tmp_path: Path) -> None:
    """'accepted_tradeoff' outcome sets status=accepted_tradeoff and writes rationale."""
    from megaplan._core import load_flag_registry, save_flag_registry
    from megaplan.flags import apply_flag_verifications

    registry = {
        "flags": [
            {"id": "FLAG-003", "status": "open", "verified": False, "concern": "rejection stands"},
        ]
    }
    save_flag_registry(tmp_path, registry)

    adjudicated = apply_flag_verifications(
        tmp_path,
        [{"flag_id": "FLAG-003", "lens": "callers", "outcome": "accepted_tradeoff", "rationale": "rejection valid"}],
    )

    result = load_flag_registry(tmp_path)
    flag = result["flags"][0]

    assert adjudicated == {"FLAG-003"}
    assert flag["status"] == "accepted_tradeoff"
    assert flag["verify_rationale"] == "rejection valid"


def test_apply_flag_verifications_unknown_flag_ignored(tmp_path: Path) -> None:
    """Verifications for unknown flag_ids are silently skipped and not returned."""
    from megaplan._core import save_flag_registry
    from megaplan.flags import apply_flag_verifications

    save_flag_registry(tmp_path, {"flags": []})

    adjudicated = apply_flag_verifications(
        tmp_path,
        [{"flag_id": "FLAG-999", "lens": "correctness", "outcome": "verified", "rationale": "x"}],
    )

    assert adjudicated == set()


def test_apply_flag_verifications_empty_list(tmp_path: Path) -> None:
    """Empty verifications list returns empty set without touching the registry."""
    from megaplan._core import load_flag_registry, save_flag_registry
    from megaplan.flags import apply_flag_verifications

    registry = {"flags": [{"id": "FLAG-001", "status": "open", "concern": "c"}]}
    save_flag_registry(tmp_path, registry)

    adjudicated = apply_flag_verifications(tmp_path, [])

    assert adjudicated == set()
    result = load_flag_registry(tmp_path)
    assert result["flags"][0]["status"] == "open"


# ---------------------------------------------------------------------------
# T7: _apply_flag_updates skip_flag_ids — all three mutation loops
# ---------------------------------------------------------------------------

def test_apply_flag_updates_skip_verified_flag_ids_loop(tmp_path: Path) -> None:
    """skip_flag_ids prevents the critic's verified_flag_ids loop from overwriting evaluator state."""
    from megaplan._core import load_flag_registry, save_flag_registry
    from megaplan.flags import _apply_flag_updates

    registry = {
        "flags": [{"id": "FLAG-001", "status": "accepted_tradeoff", "verified": False, "concern": "x", "severity": "significant"}],
    }
    save_flag_registry(tmp_path, registry)

    _apply_flag_updates(
        {"verified_flag_ids": ["FLAG-001"], "disputed_flag_ids": [], "flags": []},
        plan_dir=tmp_path,
        iteration=2,
        artifact_prefix="critique",
        skip_flag_ids=frozenset({"FLAG-001"}),
    )

    result = load_flag_registry(tmp_path)
    assert result["flags"][0]["status"] == "accepted_tradeoff"


def test_apply_flag_updates_skip_disputed_flag_ids_loop(tmp_path: Path) -> None:
    """skip_flag_ids prevents the critic's disputed_flag_ids loop from overwriting evaluator state."""
    from megaplan._core import load_flag_registry, save_flag_registry
    from megaplan.flags import _apply_flag_updates

    registry = {
        "flags": [{"id": "FLAG-002", "status": "verified", "verified": True, "concern": "x", "severity": "significant"}],
    }
    save_flag_registry(tmp_path, registry)

    _apply_flag_updates(
        {"verified_flag_ids": [], "disputed_flag_ids": ["FLAG-002"], "flags": []},
        plan_dir=tmp_path,
        iteration=2,
        artifact_prefix="critique",
        skip_flag_ids=frozenset({"FLAG-002"}),
    )

    result = load_flag_registry(tmp_path)
    assert result["flags"][0]["status"] == "verified"


def test_apply_flag_updates_skip_flags_reraise_loop(tmp_path: Path) -> None:
    """skip_flag_ids prevents the flags[] re-raise loop from flipping an evaluator-set status back to open."""
    from megaplan._core import load_flag_registry, save_flag_registry
    from megaplan.flags import _apply_flag_updates

    registry = {
        "flags": [
            {
                "id": "FLAG-003",
                "status": "accepted_tradeoff",
                "verified": False,
                "concern": "original",
                "evidence": "e",
                "category": "correctness",
                "severity": "significant",
                "severity_hint": "likely-significant",
            }
        ],
    }
    save_flag_registry(tmp_path, registry)

    _apply_flag_updates(
        {
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
            "flags": [{"id": "FLAG-003", "concern": "re-raise", "category": "correctness", "severity_hint": "likely-significant", "evidence": "e2"}],
        },
        plan_dir=tmp_path,
        iteration=2,
        artifact_prefix="critique",
        skip_flag_ids=frozenset({"FLAG-003"}),
    )

    result = load_flag_registry(tmp_path)
    assert result["flags"][0]["status"] == "accepted_tradeoff"


# ---------------------------------------------------------------------------
# T7: selection_why renders in critique prompt
# ---------------------------------------------------------------------------

def test_critique_prompt_renders_selection_why(plan_fixture: PlanFixture) -> None:
    """When selection_why is non-empty, the evaluator targeting notes appear in the prompt."""
    from megaplan._core import load_plan
    from megaplan.prompts import create_claude_prompt

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    _, state = load_plan(plan_fixture.root, plan_fixture.plan_name)

    from megaplan.audits.robustness import CRITIQUE_CHECKS
    subset = [c for c in CRITIQUE_CHECKS if c["id"] in {"correctness", "scope"}]

    prompt_with_why = create_claude_prompt(
        "critique",
        state,
        plan_fixture.plan_dir,
        root=plan_fixture.root,
        active_checks=subset,
        expected_ids=["correctness", "scope"],
        selection_why={"correctness": "re-examine edge case", "scope": "check broader impact"},
    )

    assert "Evaluator targeting notes" in prompt_with_why
    assert "re-examine edge case" in prompt_with_why
    assert "check broader impact" in prompt_with_why


def test_critique_prompt_no_why_block_when_selection_why_empty(plan_fixture: PlanFixture) -> None:
    """When selection_why is empty or None, no targeting notes block is rendered."""
    from megaplan._core import load_plan
    from megaplan.prompts import create_claude_prompt

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    _, state = load_plan(plan_fixture.root, plan_fixture.plan_name)

    prompt_no_why = create_claude_prompt(
        "critique",
        state,
        plan_fixture.plan_dir,
        root=plan_fixture.root,
    )

    assert "Evaluator targeting notes" not in prompt_no_why


# ---------------------------------------------------------------------------
# T7: integration — adaptive handle_critique applies verifications before critic
# ---------------------------------------------------------------------------

def test_handle_critique_adaptive_applies_verifications_and_skips_reraise(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When evaluator returns flag_verifications, apply_flag_verifications runs before the
    critic and the verified flag cannot be overridden by the critic's re-raise."""
    import json

    import megaplan.handlers as handlers_mod
    import megaplan.handlers.critique as critique_mod
    from megaplan.audits.robustness import CRITIQUE_CHECKS
    from megaplan.workers import WorkerResult

    monkeypatch.setattr(critique_mod, "validate_critique_checks", lambda payload, **kw: [])

    # Enable adaptive critique.
    state_path = plan_fixture.plan_dir / "state.json"
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    # Pre-seed a flag in the registry so the evaluator can verify it.
    from megaplan._core import load_flag_registry, save_flag_registry
    registry = load_flag_registry(plan_fixture.plan_dir)
    registry["flags"].append({
        "id": "FLAG-T7", "status": "addressed", "verified": False,
        "concern": "some concern", "evidence": "e", "category": "correctness",
        "severity": "significant", "severity_hint": "likely-significant",
        "raised_in": "critique_v1.json",
    })
    save_flag_registry(plan_fixture.plan_dir, registry)

    all_check_ids = [c["id"] for c in CRITIQUE_CHECKS]
    selected_cid = all_check_ids[0]
    verdict = {
        "selections": [{
            "check_id": selected_cid,
            "complexity": 4 if selected_cid in {"correctness", "prerequisite_ordering"} else 3,
            "complexity_justification": f"{selected_cid} needs live routing scrutiny.",
            "why": "check it",
        }],
        "skipped": [{"check_id": cid, "why": "skip"} for cid in all_check_ids if cid != selected_cid],
        "evaluator_model": "claude-opus-4-7",
        "flag_verifications": [
            {"flag_id": "FLAG-T7", "lens": selected_cid, "outcome": "verified", "rationale": "diff confirms fix"},
        ],
    }

    def fake_run_step(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, **kwargs):
        if step == "critique_evaluator":
            return (
                WorkerResult(payload=verdict, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="ev"),
                "claude", "persistent", False,
            )
        # Critic re-raises FLAG-T7 as open — the skip-set must block this.
        payload = {
            "checks": [{"id": selected_cid, "summary": "ok", "findings": [{"detail": "d", "flagged": False}]}],
            "flags": [{"id": "FLAG-T7", "concern": "re-raised", "category": "correctness", "severity_hint": "likely-significant", "evidence": "e2"}],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        }
        return (
            WorkerResult(payload=payload, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="cr"),
            "claude", "persistent", False,
        )

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step)
    monkeypatch.setattr(
        handlers_mod,
        "resolve_agent_mode",
        lambda step, args: ("claude", "persistent", False, "claude-opus-4-7"),
    )

    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    result_registry = load_flag_registry(plan_fixture.plan_dir)
    flag = next((f for f in result_registry["flags"] if f["id"] == "FLAG-T7"), None)
    assert flag is not None, "FLAG-T7 missing from registry"
    assert flag["status"] == "verified", f"Expected 'verified' but got {flag['status']!r} — critic re-raise must be blocked by skip-set"
    assert flag.get("verify_rationale") == "diff confirms fix"


def test_handle_critique_pin_forces_critic_model_over_evaluator_assignment(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """execution.critic_model pins the farmed-out critic: the Opus evaluator
    still picks lenses, but its premium per-lens assignment is overridden and
    the critic dispatches to DeepSeek's direct API."""
    import json

    import megaplan.handlers as handlers_mod
    import megaplan.handlers.critique as critique_mod
    from megaplan.audits.robustness import CRITIQUE_CHECKS
    from megaplan.workers import WorkerResult

    monkeypatch.setattr(critique_mod, "validate_critique_checks", lambda payload, **kw: [])

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state_path = plan_fixture.plan_dir / "state.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    persisted["config"]["critic_model"] = "deepseek-v4-pro"
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    all_check_ids = [c["id"] for c in CRITIQUE_CHECKS]
    selected_cid = all_check_ids[0]
    # Evaluator escalates this lens to a premium critic — the pin must win.
    verdict = {
        "selections": [{
            "check_id": selected_cid,
            "complexity": 4 if selected_cid in {"correctness", "prerequisite_ordering"} else 3,
            "complexity_justification": f"{selected_cid} needs live routing scrutiny.",
            "why": "x",
        }],
        "skipped": [{"check_id": cid, "why": "skip"} for cid in all_check_ids if cid != selected_cid],
        "evaluator_model": "claude-opus-4-7",
    }

    captured: dict[str, object] = {}

    def fake_run_step(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, resolved=None, **kwargs):
        if step == "critique_evaluator":
            return (
                WorkerResult(payload=verdict, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="ev"),
                "claude", "persistent", False,
            )
        captured["critic_resolved"] = resolved
        payload = {
            "checks": [{"id": selected_cid, "summary": "ok", "findings": []}],
            "flags": [], "verified_flag_ids": [], "disputed_flag_ids": [],
        }
        # ``resolved`` is now an AgentMode (carries effort/resolved_model) — it
        # is iterable as (agent, mode, refreshed, model) but not subscriptable.
        resolved_agent = next(iter(resolved)) if resolved else "hermes"
        return (
            WorkerResult(payload=payload, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="cr"),
            resolved_agent, "persistent", False,
        )

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step)
    # Critique slot is premium; without the pin the critic would inherit it.
    monkeypatch.setattr(
        handlers_mod,
        "resolve_agent_mode",
        lambda step, args: ("claude", "persistent", False, "claude-opus-4-7"),
    )

    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    agent, _mode, _refreshed, model = captured["critic_resolved"]
    assert agent == "hermes", f"pin must route critic to hermes, got {agent!r}"
    assert model == "deepseek:deepseek-v4-pro", (
        f"pin must force direct-DeepSeek model, got {model!r}"
    )


# ---------------------------------------------------------------------------
# T8(a): regression — non-adaptive path does NOT fire verify/diff/why wiring
# ---------------------------------------------------------------------------


def test_regression_non_adaptive_prompt_has_no_revise_context_or_selection_why(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With --adaptive-critique absent (default), the critique prompt on iteration>=2
    must NOT contain revise_context or selection_why blocks — byte-for-byte unchanged."""
    import json

    from megaplan._core import load_plan
    from megaplan.prompts import create_claude_prompt

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    # Advance to iteration 2 by writing a fake critique and plan version.
    state = load_state(plan_fixture.plan_dir)
    state["iteration"] = 2
    (plan_fixture.plan_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

    # Create plan_v1.md and plan_v2.md so _plan_version_unified_diff would produce a diff
    # if it were called (but it should NOT be on the non-adaptive path).
    (plan_fixture.plan_dir / "plan_v1.md").write_text("# Plan v1\nStep 1\n", encoding="utf-8")
    (plan_fixture.plan_dir / "plan_v2.md").write_text("# Plan v2\nStep 1\nStep 2\n", encoding="utf-8")

    # Force adaptive_critique OFF.
    persisted = json.loads((plan_fixture.plan_dir / "state.json").read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = False
    (plan_fixture.plan_dir / "state.json").write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    _, state = load_plan(plan_fixture.root, plan_fixture.plan_name)
    assert state["config"]["adaptive_critique"] is False
    assert state["iteration"] == 2

    prompt = create_claude_prompt("critique", state, plan_fixture.plan_dir, root=plan_fixture.root)

    # Must NOT contain adaptive-only blocks.
    assert "Revise context (what changed since the last plan version)" not in prompt
    assert "Evaluator targeting notes" not in prompt
    assert "Unified diff between plan versions" not in prompt
    assert "Per-flag resolution claims" not in prompt


# ---------------------------------------------------------------------------
# T8(e): back-compat — old faults.json with no resolution still loads
# ---------------------------------------------------------------------------


def test_back_compat_old_faults_without_resolution_loads(
    plan_fixture: PlanFixture,
) -> None:
    """A faults.json with flags that have no `resolution` field loads cleanly
    through load_flag_registry and survives the verify-flow context path."""
    import json

    from megaplan._core import load_flag_registry
    from megaplan.flags import flag_resolution_summary

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    # Write an old-style faults.json — no resolution field on any flag.
    old_registry = {
        "flags": [
            {
                "id": "FLAG-001",
                "status": "open",
                "concern": "off-by-one error",
                "evidence": "line 42 uses < instead of <=",
                "category": "correctness",
                "severity": "significant",
                "severity_hint": "likely-significant",
                "verified": False,
            },
            {
                "id": "FLAG-002",
                "status": "verified",
                "concern": "missing null check",
                "evidence": "pointer deref without guard at util.c:128",
                "category": "security",
                "severity": "significant",
                "severity_hint": "likely-significant",
                "verified": True,
                "verified_in": "critique_v1.json",
            },
        ]
    }
    (plan_fixture.plan_dir / "faults.json").write_text(
        json.dumps(old_registry, indent=2) + "\n", encoding="utf-8"
    )

    # (a) load_flag_registry loads without error.
    loaded = load_flag_registry(plan_fixture.plan_dir)
    assert len(loaded["flags"]) == 2
    assert loaded["flags"][0]["concern"] == "off-by-one error"
    assert "resolution" not in loaded["flags"][0]

    # (b) flag_resolution_summary falls back to evidence when resolution absent.
    summary = flag_resolution_summary(loaded["flags"][0])
    assert summary == "line 42 uses < instead of <="


# ---------------------------------------------------------------------------
# T8: evidence-survival — concern and evidence survive update_flags_after_revise
# ---------------------------------------------------------------------------


def test_evidence_survival_concern_and_evidence_preserved_after_revise(
    plan_fixture: PlanFixture,
) -> None:
    """After update_flags_after_revise, the original concern and evidence fields
    are preserved — not overwritten by the revise summary."""
    from megaplan._core import load_flag_registry, save_flag_registry
    from megaplan.flags import update_flags_after_revise

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    # Seed a flag with known concern and evidence.
    registry = load_flag_registry(plan_fixture.plan_dir)
    registry["flags"].append({
        "id": "FLAG-EV",
        "status": "open",
        "concern": "original concern text",
        "evidence": "original evidence detail",
        "category": "correctness",
        "severity": "significant",
        "severity_hint": "likely-significant",
        "verified": False,
    })
    save_flag_registry(plan_fixture.plan_dir, registry)

    # Simulate a revise that addresses FLAG-EV with a new summary.
    flags_addressed = [
        {
            "id": "FLAG-EV",
            "resolution": "addressed",
            "reason": "fixed the issue by adding a guard clause",
            "where": "Phase 2 — Step 3",
        }
    ]
    update_flags_after_revise(
        plan_fixture.plan_dir,
        flags_addressed,
        plan_file="plan_v2.md",
        summary="Revised plan to add guard clauses throughout the module.",
    )

    result = load_flag_registry(plan_fixture.plan_dir)
    flag = next((f for f in result["flags"] if f["id"] == "FLAG-EV"), None)
    assert flag is not None

    # Original concern and evidence MUST survive.
    assert flag["concern"] == "original concern text"
    assert flag["evidence"] == "original evidence detail"

    # Resolution slot is additive.
    assert flag.get("resolution") == {
        "kind": "fixed",
        "claim": "fixed the issue by adding a guard clause",
        "where": "Phase 2 — Step 3",
    }

    # Status updated to addressed.
    assert flag["status"] == "addressed"


# ---------------------------------------------------------------------------
# T8: consumer-migration — build_gate_signals and gate prompt surface
#      revise summary via flag_resolution_summary;
#      is_scope_creep_flag keys on original critique evidence
# ---------------------------------------------------------------------------


def test_consumer_migration_build_gate_signals_uses_flag_resolution_summary(
    plan_fixture: PlanFixture,
) -> None:
    """build_gate_signals populated the 'resolution' field via flag_resolution_summary."""
    import json

    from megaplan._core import load_flag_registry, save_flag_registry

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    # Seed a verified flag with both evidence and resolution.
    registry = load_flag_registry(plan_fixture.plan_dir)
    registry["flags"].append({
        "id": "FLAG-CM",
        "status": "verified",
        "concern": "race condition",
        "evidence": "two goroutines write to the same map without synchronization",
        "category": "correctness",
        "severity": "significant",
        "severity_hint": "likely-significant",
        "verified": True,
        "verified_in": "critique_v1.json",
        "resolution": {
            "kind": "fixed",
            "claim": "added sync.Mutex around map writes",
            "where": "Phase 1 — Step 2",
        },
    })
    save_flag_registry(plan_fixture.plan_dir, registry)

    # Need to advance state to make build_gate_signals work.
    state = load_state(plan_fixture.plan_dir)
    state["iteration"] = 2
    (plan_fixture.plan_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

    # Create plan_v1.md and plan_v2.md for build_gate_signals.
    (plan_fixture.plan_dir / "plan_v1.md").write_text("# Plan v1\n", encoding="utf-8")
    (plan_fixture.plan_dir / "plan_v2.md").write_text("# Plan v2\n", encoding="utf-8")

    # Create minimal critique files so compute_recurring_critiques can read them.
    for v in (1, 2):
        (plan_fixture.plan_dir / f"critique_v{v}.json").write_text(json.dumps({
            "checks": [],
            "flags": [],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        }, indent=2) + "\n", encoding="utf-8")

    from megaplan.orchestration.evaluation import build_gate_signals

    signals = build_gate_signals(plan_fixture.plan_dir, state, root=plan_fixture.root)
    resolved = signals["signals"].get("resolved_flags", [])
    flag_cm = next((r for r in resolved if r["id"] == "FLAG-CM"), None)
    assert flag_cm is not None, "FLAG-CM should appear in resolved_flags (status=verified)"
    # resolution field should be the resolution claim, not the raw evidence.
    assert flag_cm["resolution"] == "added sync.Mutex around map writes"


def test_consumer_migration_is_scope_creep_flag_keys_on_evidence(
    plan_fixture: PlanFixture,
) -> None:
    """is_scope_creep_flag keys on the original critique evidence — the scope-creep
    detector reads flag['concern'] + flag['evidence'] to detect scope creep terms."""
    from megaplan._core import is_scope_creep_flag

    # A flag whose evidence contains a scope-creep term should match.
    scope_flag = {
        "id": "FLAG-SC1",
        "concern": "the plan does too much",
        "evidence": "this feature is out of scope for the current iteration",
        "category": "completeness",
        "status": "open",
        "severity": "significant",
    }
    assert is_scope_creep_flag(scope_flag) is True, (
        "flag with 'out of scope' in evidence should be detected as scope creep"
    )

    # A flag without scope-creep terms should not match.
    normal_flag = {
        "id": "FLAG-N1",
        "concern": "off-by-one error in loop",
        "evidence": "line 42 iterates one too few times",
        "category": "correctness",
        "status": "open",
        "severity": "significant",
    }
    assert is_scope_creep_flag(normal_flag) is False, (
        "flag with no scope-creep terms should not be detected"
    )


# ---------------------------------------------------------------------------
# T8: reconciliation — verify `open` outcome not overwritten by critic's
#      verified_flag_ids in the same iteration
# ---------------------------------------------------------------------------


def test_reconciliation_open_flag_not_overwritten_by_critic_verified(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the evaluator adjudicates a flag as 'open' (cosmetic/no-op change),
    the critic's verified_flag_ids in the same iteration MUST NOT flip it back
    to verified. The skip-set must cover verified_flag_ids too."""
    import json

    import megaplan.handlers as handlers_mod
    import megaplan.handlers.critique as critique_mod
    from megaplan.audits.robustness import CRITIQUE_CHECKS
    from megaplan.workers import WorkerResult

    monkeypatch.setattr(critique_mod, "validate_critique_checks", lambda payload, **kw: [])

    # Enable adaptive critique.
    state_path = plan_fixture.plan_dir / "state.json"
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    # Pre-seed a flag that the evaluator will reopen.
    from megaplan._core import load_flag_registry, save_flag_registry
    registry = load_flag_registry(plan_fixture.plan_dir)
    registry["flags"].append({
        "id": "FLAG-RECON",
        "status": "addressed",
        "verified": True,
        "verified_in": "critique_v1.json",
        "concern": "some concern",
        "evidence": "e",
        "category": "correctness",
        "severity": "significant",
        "severity_hint": "likely-significant",
        "raised_in": "critique_v1.json",
    })
    save_flag_registry(plan_fixture.plan_dir, registry)

    all_check_ids = [c["id"] for c in CRITIQUE_CHECKS]
    selected_cid = all_check_ids[0]
    verdict = {
        "selections": [{
            "check_id": selected_cid,
            "complexity": 4 if selected_cid in {"correctness", "prerequisite_ordering"} else 3,
            "complexity_justification": f"{selected_cid} needs live routing scrutiny.",
            "why": "check it",
        }],
        "skipped": [{"check_id": cid, "why": "skip"} for cid in all_check_ids if cid != selected_cid],
        "evaluator_model": "claude-opus-4-7",
        "flag_verifications": [
            # Evaluator reopens this flag — fix was cosmetic/no-op.
            {"flag_id": "FLAG-RECON", "lens": selected_cid, "outcome": "open", "rationale": "diff is a no-op rename"},
        ],
    }

    def fake_run_step(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, **kwargs):
        if step == "critique_evaluator":
            return (
                WorkerResult(payload=verdict, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="ev"),
                "claude", "persistent", False,
            )
        # Critic tries to re-verify FLAG-RECON — the skip-set MUST block this.
        payload = {
            "checks": [{"id": selected_cid, "summary": "ok", "findings": [{"detail": "d", "flagged": False}]}],
            "flags": [],
            "verified_flag_ids": ["FLAG-RECON"],  # Critic claims it's verified
            "disputed_flag_ids": [],
        }
        return (
            WorkerResult(payload=payload, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="cr"),
            "claude", "persistent", False,
        )

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step)
    monkeypatch.setattr(
        handlers_mod,
        "resolve_agent_mode",
        lambda step, args: ("claude", "persistent", False, "claude-opus-4-7"),
    )

    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    result_registry = load_flag_registry(plan_fixture.plan_dir)
    flag = next((f for f in result_registry["flags"] if f["id"] == "FLAG-RECON"), None)
    assert flag is not None, "FLAG-RECON missing from registry"
    assert flag["status"] == "open", (
        f"Expected 'open' but got {flag['status']!r} — critic verified_flag_ids "
        f"must be blocked by skip-set, open outcome must not be overwritten"
    )
    assert flag["verified"] is False
    assert "verified_in" not in flag
    assert flag.get("verify_rationale") == "diff is a no-op rename"


# ---------------------------------------------------------------------------
# T14: Metadata preservation — catalog checks preserve complexity and
#      complexity_justification, other checks preserve separate probe why and
#      routing justification, and sequential fallback receives useful
#      targeting notes after the metadata migration.
# ---------------------------------------------------------------------------


def test_catalog_checks_preserve_complexity_and_justification(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catalog (built-in) lens selections must attach complexity and
    complexity_justification to each active check dict, and the
    _selection_why for that check must be the complexity_justification."""
    import json

    import megaplan.handlers as handlers_mod
    import megaplan.handlers.critique as critique_mod
    from megaplan.audits.robustness import CRITIQUE_CHECKS
    from megaplan.workers import WorkerResult

    monkeypatch.setattr(critique_mod, "validate_critique_checks", lambda payload, **kw: [])
    monkeypatch.setattr(critique_mod, "adaptive_critique_enabled", lambda state: True)
    monkeypatch.setattr(critique_mod, "is_creative_mode", lambda state: False)
    monkeypatch.setattr(
        "megaplan.audits.critique_evaluator.validate_evaluator_verdict",
        lambda payload, **kwargs: None,
    )

    # Enable adaptive critique in persisted state.
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state_path = plan_fixture.plan_dir / "state.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    all_check_ids = [c["id"] for c in CRITIQUE_CHECKS]
    # Select two catalog checks so len(active_checks) > 1 and the hermes
    # parallel path is taken.  correctness carries a known complexity and
    # justification; scope is a second lens to satisfy >1.
    verdict = {
        "selections": [
            {
                "check_id": "correctness",
                "complexity": 4,
                "complexity_justification": "Correctness lens targets edge-case validation at complexity 4.",
                "why": "legacy why field",
            },
            {
                "check_id": "scope",
                "complexity": 3,
                "complexity_justification": "Scope check at moderate complexity.",
            },
        ],
        "skipped": [
            {"check_id": cid, "why": "skip"}
            for cid in all_check_ids
            if cid not in {"correctness", "scope"}
        ],
        "evaluator_model": "claude-opus-4-7",
        "flag_verifications": [],
    }

    captured_checks: list[dict] = []

    def fake_parallel(state, plan_dir, *, root, model, checks, max_concurrent=None, effort=None, **kwargs):
        captured_checks.extend(checks)
        return WorkerResult(
            payload={
                "checks": [
                    {"id": c["id"], "summary": "ok", "findings": [{"detail": "d", "flagged": False}]}
                    for c in checks
                ],
                "flags": [],
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
            },
            raw_output="{}",
            duration_ms=1,
            cost_usd=0.0,
            session_id="critique",
        )

    monkeypatch.setattr(critique_mod, "run_parallel_critique", fake_parallel)

    def fake_run_step(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, **kwargs):
        if step == "critique_evaluator":
            return (
                WorkerResult(payload=verdict, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="ev"),
                "hermes", "persistent", False,
            )
        # Should not reach here — parallel handles the critic.
        raise AssertionError(f"unexpected run_step call for {step}")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step)
    # The critique slot must resolve to hermes so the parallel path fires.
    monkeypatch.setattr(
        handlers_mod,
        "resolve_agent_mode",
        lambda step, args: ("hermes", "persistent", False, "fireworks:model"),
    )

    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    # Find the correctness check in captured checks.
    corr = next((c for c in captured_checks if c["id"] == "correctness"), None)
    assert corr is not None, "correctness check must be in active checks"
    assert corr["complexity"] == 4, (
        f"catalog check must preserve complexity; got {corr['complexity']!r}"
    )
    assert corr["complexity_justification"] == (
        "Correctness lens targets edge-case validation at complexity 4."
    ), f"catalog check must preserve complexity_justification; got {corr['complexity_justification']!r}"


def test_other_checks_preserve_separate_probe_why_and_routing_justification(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bespoke 'other' custom area must use `why` as the critic question/probe
    while keeping `complexity` and `complexity_justification` on the check dict
    as routing/targeting metadata — separate semantics."""
    import json

    import megaplan.handlers as handlers_mod
    import megaplan.handlers.critique as critique_mod
    from megaplan.audits.robustness import CRITIQUE_CHECKS
    from megaplan.workers import WorkerResult

    monkeypatch.setattr(critique_mod, "validate_critique_checks", lambda payload, **kw: [])
    monkeypatch.setattr(critique_mod, "adaptive_critique_enabled", lambda state: True)
    monkeypatch.setattr(critique_mod, "is_creative_mode", lambda state: False)
    monkeypatch.setattr(
        "megaplan.audits.critique_evaluator.validate_evaluator_verdict",
        lambda payload, **kwargs: None,
    )

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state_path = plan_fixture.plan_dir / "state.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    all_check_ids = [c["id"] for c in CRITIQUE_CHECKS]
    verdict = {
        "selections": [
            # One catalog check so the verdict union isn't empty.
            {
                "check_id": "correctness",
                "complexity": 4,
                "complexity_justification": "catalog reason",
            },
            # One 'other' custom area.
            {
                "check_id": "other",
                "area": "Security review",
                "why": "Check for SQL injection vulnerabilities in user input handling.",
                "complexity": 5,
                "complexity_justification": "Security probing routes at high complexity due to criticality.",
            },
        ],
        "skipped": [
            {"check_id": cid, "why": "skip"} for cid in all_check_ids if cid not in {"correctness"}
        ],
        "evaluator_model": "claude-opus-4-7",
        "flag_verifications": [],
    }

    captured_checks: list[dict] = []

    def fake_parallel(state, plan_dir, *, root, model, checks, max_concurrent=None, effort=None, **kwargs):
        captured_checks.extend(checks)
        return WorkerResult(
            payload={
                "checks": [
                    {"id": c["id"], "summary": "ok", "findings": [{"detail": "d", "flagged": False}]}
                    for c in checks
                ],
                "flags": [],
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
            },
            raw_output="{}",
            duration_ms=1,
            cost_usd=0.0,
            session_id="critique",
        )

    monkeypatch.setattr(critique_mod, "run_parallel_critique", fake_parallel)

    def fake_run_step(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, **kwargs):
        if step == "critique_evaluator":
            return (
                WorkerResult(payload=verdict, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="ev"),
                "hermes", "persistent", False,
            )
        raise AssertionError(f"unexpected run_step call for {step}")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step)
    # The critique slot must resolve to hermes so the parallel path fires.
    monkeypatch.setattr(
        handlers_mod,
        "resolve_agent_mode",
        lambda step, args: ("hermes", "persistent", False, "fireworks:model"),
    )

    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    # Find the 'other' synthetic check by its derived id.
    other_check = next((c for c in captured_checks if c.get("id", "").startswith("other_")), None)
    assert other_check is not None, "other custom area must produce a synthetic check"

    # Probe (question) must be the evaluator's `why`.
    assert other_check["question"] == (
        "Check for SQL injection vulnerabilities in user input handling."
    ), f"other probe must be why; got {other_check['question']!r}"

    # Routing/targeting metadata must be preserved on the check dict.
    assert other_check["complexity"] == 5, (
        f"other check must preserve complexity for routing; got {other_check['complexity']!r}"
    )
    assert other_check["complexity_justification"] == (
        "Security probing routes at high complexity due to criticality."
    ), f"other check must preserve complexity_justification; got {other_check['complexity_justification']!r}"


def test_sequential_fallback_receives_targeting_notes(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When parallel critique fails and falls back to sequential, the
    `selection_why` passed in prompt_kwargs must include catalog check
    complexity_justification and other check probe `why`, so the sequential
    critic receives readable evaluator targeting notes."""
    import json

    import megaplan.handlers as handlers_mod
    import megaplan.handlers.critique as critique_mod
    from megaplan.audits.robustness import CRITIQUE_CHECKS
    from megaplan.workers import WorkerResult

    monkeypatch.setattr(critique_mod, "validate_critique_checks", lambda payload, **kw: [])
    monkeypatch.setattr(critique_mod, "adaptive_critique_enabled", lambda state: True)
    monkeypatch.setattr(critique_mod, "is_creative_mode", lambda state: False)
    monkeypatch.setattr(
        "megaplan.audits.critique_evaluator.validate_evaluator_verdict",
        lambda payload, **kwargs: None,
    )

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state_path = plan_fixture.plan_dir / "state.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    all_check_ids = [c["id"] for c in CRITIQUE_CHECKS]
    verdict = {
        "selections": [
            {
                "check_id": "correctness",
                "complexity": 4,
                "complexity_justification": "Catalog: edge-case validation.",
            },
            {
                "check_id": "other",
                "area": "Performance audit",
                "why": "Check for O(n²) patterns in data processing loops.",
                "complexity": 3,
                "complexity_justification": "Performance audit is moderate complexity.",
            },
        ],
        "skipped": [
            {"check_id": cid, "why": "skip"} for cid in all_check_ids if cid not in {"correctness"}
        ],
        "evaluator_model": "claude-opus-4-7",
        "flag_verifications": [],
    }

    captured_prompt_kwargs: dict = {}

    def fake_run_step(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, resolved=None, **kwargs):
        if step == "critique_evaluator":
            return (
                WorkerResult(payload=verdict, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="ev"),
                "claude", "persistent", False,
            )
        # Sequential fallback: capture the prompt_kwargs.
        captured_prompt_kwargs.update(prompt_kwargs or {})
        return (
            WorkerResult(
                payload={
                    "checks": [
                        {"id": cid, "summary": "ok", "findings": [{"detail": "d", "flagged": False}]}
                        for cid in ["correctness", "other_performance_audit"]
                    ],
                    "flags": [],
                    "verified_flag_ids": [],
                    "disputed_flag_ids": [],
                },
                raw_output="{}",
                duration_ms=1,
                cost_usd=0.0,
                session_id="critique",
            ),
            "claude",
            "persistent",
            False,
        )

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step)
    # Force parallel to fail so we exercise the fallback path.
    monkeypatch.setattr(
        critique_mod,
        "run_parallel_critique",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("parallel failed")),
    )
    monkeypatch.setattr(
        handlers_mod,
        "resolve_agent_mode",
        lambda step, args: ("hermes", "persistent", False, "fireworks:model"),
    )

    caplog.set_level("WARNING", logger="megaplan")
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    # Fallback must have fired.
    assert any(
        "M3A_WARN_PARALLEL_CRITIQUE_FALLBACK" in record.getMessage()
        for record in caplog.records
    ), "parallel critique must fall back"

    sel_why = captured_prompt_kwargs.get("selection_why", {})
    assert isinstance(sel_why, dict), "selection_why must be a dict"

    # Catalog check: _selection_why[id] == complexity_justification.
    assert sel_why.get("correctness") == "Catalog: edge-case validation.", (
        f"catalog check _selection_why must be complexity_justification; got {sel_why.get('correctness')!r}"
    )

    # Other check: _selection_why[oid] == why (the probe/question).
    oid_key = next((k for k in sel_why if k.startswith("other_")), None)
    assert oid_key is not None, "other check must have a selection_why entry"
    assert sel_why[oid_key] == "Check for O(n²) patterns in data processing loops.", (
        f"other _selection_why must be the probe why; got {sel_why[oid_key]!r}"
    )

    # active_checks must also be in the prompt kwargs (for the sequential critic).
    assert "active_checks" in captured_prompt_kwargs, (
        "sequential fallback must pass active_checks to the critic"
    )


# ---------------------------------------------------------------------------
# T16: Critique routing — evaluator complexity drives per-lens tier
#      resolution, _resolve_tier_spec is called once per distinct complexity,
#      missing complexity is treated as an invariant failure, and operator-
#      pinned critic_model overrides all per-lens complexity routing with one
#      resolved model.
# ---------------------------------------------------------------------------


def test_evaluator_complexity_drives_per_lens_tier_resolution(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the evaluator selects lenses at different complexity tiers, each
    active check receives a ``_resolved_agent_mode`` matching its complexity
    via the tier_models.critique lookup."""
    import json

    import megaplan.handlers as handlers_mod
    import megaplan.handlers.critique as critique_mod
    from megaplan.audits.robustness import CRITIQUE_CHECKS
    from megaplan.workers import WorkerResult

    monkeypatch.setattr(critique_mod, "validate_critique_checks", lambda payload, **kw: [])
    monkeypatch.setattr(critique_mod, "adaptive_critique_enabled", lambda state: True)
    monkeypatch.setattr(critique_mod, "is_creative_mode", lambda state: False)
    monkeypatch.setattr(
        "megaplan.audits.critique_evaluator.validate_evaluator_verdict",
        lambda payload, **kwargs: None,
    )

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state_path = plan_fixture.plan_dir / "state.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    all_check_ids = [c["id"] for c in CRITIQUE_CHECKS]
    verdict = {
        "selections": [
            {
                "check_id": "correctness",
                "complexity": 3,
                "complexity_justification": "Standard correctness check at tier 3.",
            },
            {
                "check_id": "scope",
                "complexity": 5,
                "complexity_justification": "Scope analysis needs depth at complexity 5.",
            },
        ],
        "skipped": [
            {"check_id": cid, "why": "skip"}
            for cid in all_check_ids
            if cid not in {"correctness", "scope"}
        ],
        "evaluator_model": "claude-opus-4-7",
        "flag_verifications": [],
    }

    captured_checks: list[dict] = []

    def fake_parallel(state, plan_dir, *, root, model, checks, max_concurrent=None, effort=None, **kwargs):
        captured_checks.extend(checks)
        return WorkerResult(
            payload={
                "checks": [
                    {"id": c["id"], "summary": "ok", "findings": [{"detail": "d", "flagged": False}]}
                    for c in checks
                ],
                "flags": [],
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
            },
            raw_output="{}",
            duration_ms=1,
            cost_usd=0.0,
            session_id="critique",
        )

    monkeypatch.setattr(critique_mod, "run_parallel_critique", fake_parallel)

    def fake_run_step(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, **kwargs):
        if step == "critique_evaluator":
            return (
                WorkerResult(payload=verdict, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="ev"),
                "hermes", "persistent", False,
            )
        raise AssertionError(f"unexpected run_step call for {step}")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step)
    monkeypatch.setattr(
        handlers_mod,
        "resolve_agent_mode",
        lambda step, args: ("hermes", "persistent", False, "fireworks:model"),
    )

    # Mock _resolve_tier_spec in its source module so the handler's local
    # ``from megaplan.execute.batch import _resolve_tier_spec`` picks it up.
    def fake_resolve_tier_spec(args, spec, *, phase="execute"):
        if "deepseek" in spec:
            return ("hermes", "persistent", "deepseek-v4-pro")
        if "claude" in spec:
            return ("claude", "persistent", "claude-opus-4-7")
        return ("hermes", "persistent", spec)

    monkeypatch.setattr(
        "megaplan.execute.batch._resolve_tier_spec", fake_resolve_tier_spec
    )

    # Provide a critique tier ladder so the routing block activates.
    args = plan_fixture.make_args(
        plan=plan_fixture.plan_name,
        tier_models={
            "critique": {
                3: "deepseek:deepseek-v4-pro",
                5: "claude:claude-opus-4-7",
            },
        },
    )

    megaplan.handle_critique(plan_fixture.root, args)

    # Verify each check got the right _resolved_agent_mode attached (SD1).
    corr = next((c for c in captured_checks if c["id"] == "correctness"), None)
    assert corr is not None, "correctness must be in active checks"
    assert "_resolved_agent_mode" in corr, (
        "complexity-driven tier resolution must attach _resolved_agent_mode to each check"
    )
    assert corr["_resolved_agent_mode"].model == "deepseek-v4-pro", (
        f"complexity 3 should resolve to deepseek-v4-pro; got {corr['_resolved_agent_mode'].model!r}"
    )

    scope = next((c for c in captured_checks if c["id"] == "scope"), None)
    assert scope is not None, "scope must be in active checks"
    assert "_resolved_agent_mode" in scope
    assert scope["_resolved_agent_mode"].model == "claude-opus-4-7", (
        f"complexity 5 should resolve to claude-opus-4-7; got {scope['_resolved_agent_mode'].model!r}"
    )


def test_resolve_tier_spec_called_once_per_distinct_complexity(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When multiple active checks share the same complexity, ``_resolve_tier_spec``
    is called exactly once for that complexity (cache hit on subsequent checks)."""
    import json

    import megaplan.handlers as handlers_mod
    import megaplan.handlers.critique as critique_mod
    from megaplan.audits.robustness import CRITIQUE_CHECKS
    from megaplan.workers import WorkerResult

    monkeypatch.setattr(critique_mod, "validate_critique_checks", lambda payload, **kw: [])
    monkeypatch.setattr(critique_mod, "adaptive_critique_enabled", lambda state: True)
    monkeypatch.setattr(critique_mod, "is_creative_mode", lambda state: False)
    monkeypatch.setattr(
        "megaplan.audits.critique_evaluator.validate_evaluator_verdict",
        lambda payload, **kwargs: None,
    )

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state_path = plan_fixture.plan_dir / "state.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    all_check_ids = [c["id"] for c in CRITIQUE_CHECKS]
    # Select three lenses: two at complexity 3, one at complexity 5.
    verdict = {
        "selections": [
            {
                "check_id": "correctness",
                "complexity": 3,
                "complexity_justification": "Standard check.",
            },
            {
                "check_id": "scope",
                "complexity": 3,
                "complexity_justification": "Also at standard complexity.",
            },
            {
                "check_id": "prerequisite_ordering",
                "complexity": 5,
                "complexity_justification": "Prerequisite analysis needs depth.",
            },
        ],
        "skipped": [
            {"check_id": cid, "why": "skip"}
            for cid in all_check_ids
            if cid not in {"correctness", "scope", "prerequisite_ordering"}
        ],
        "evaluator_model": "claude-opus-4-7",
        "flag_verifications": [],
    }

    resolve_calls: list[tuple] = []

    def fake_resolve_tier_spec(args, spec, *, phase="execute"):
        resolve_calls.append((spec, phase))
        if "deepseek" in spec:
            return ("hermes", "persistent", "deepseek-v4-pro")
        if "claude" in spec:
            return ("claude", "persistent", "claude-opus-4-7")
        return ("hermes", "persistent", spec)

    monkeypatch.setattr(
        "megaplan.execute.batch._resolve_tier_spec", fake_resolve_tier_spec
    )

    captured_checks: list[dict] = []

    def fake_parallel(state, plan_dir, *, root, model, checks, max_concurrent=None, effort=None, **kwargs):
        captured_checks.extend(checks)
        return WorkerResult(
            payload={
                "checks": [
                    {"id": c["id"], "summary": "ok", "findings": [{"detail": "d", "flagged": False}]}
                    for c in checks
                ],
                "flags": [],
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
            },
            raw_output="{}",
            duration_ms=1,
            cost_usd=0.0,
            session_id="critique",
        )

    monkeypatch.setattr(critique_mod, "run_parallel_critique", fake_parallel)

    def fake_run_step(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, **kwargs):
        if step == "critique_evaluator":
            return (
                WorkerResult(payload=verdict, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="ev"),
                "hermes", "persistent", False,
            )
        raise AssertionError(f"unexpected run_step call for {step}")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step)
    monkeypatch.setattr(
        handlers_mod,
        "resolve_agent_mode",
        lambda step, args: ("hermes", "persistent", False, "fireworks:model"),
    )

    args = plan_fixture.make_args(
        plan=plan_fixture.plan_name,
        tier_models={
            "critique": {
                3: "deepseek:deepseek-v4-pro",
                5: "claude:claude-opus-4-7",
            },
        },
    )

    megaplan.handle_critique(plan_fixture.root, args)

    # Complexity 3 appears twice in selections; _resolve_tier_spec must be
    # called exactly once for spec "deepseek:deepseek-v4-pro" (cached).
    c3_calls = [c for c in resolve_calls if c[0] == "deepseek:deepseek-v4-pro"]
    assert len(c3_calls) == 1, (
        f"_resolve_tier_spec should be called exactly once for complexity 3 "
        f"(two checks share it, cache hit expected); got {len(c3_calls)} calls"
    )

    # Complexity 5 appears once; must be called exactly once.
    c5_calls = [c for c in resolve_calls if c[0] == "claude:claude-opus-4-7"]
    assert len(c5_calls) == 1, (
        f"_resolve_tier_spec should be called exactly once for complexity 5; "
        f"got {len(c5_calls)} calls"
    )

    # Total calls: 2 distinct complexities = 2 calls (not 3).
    assert len(resolve_calls) == 2, (
        f"expected 2 distinct _resolve_tier_spec calls (one per complexity); "
        f"got {len(resolve_calls)}"
    )

    # All three checks must have _resolved_agent_mode attached.
    assert len(captured_checks) == 3, f"expected 3 active checks; got {len(captured_checks)}"
    for c in captured_checks:
        assert "_resolved_agent_mode" in c, (
            f"check '{c['id']}' missing _resolved_agent_mode"
        )


def test_missing_complexity_is_invariant_failure(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a selected check has missing, non-int, or out-of-range complexity,
    the handler raises ``CliError`` ('critique_complexity_invariant') rather
    than defaulting to a tier."""
    import json

    import megaplan.handlers as handlers_mod
    import megaplan.handlers.critique as critique_mod
    from megaplan.audits.robustness import CRITIQUE_CHECKS
    from megaplan.workers import WorkerResult

    monkeypatch.setattr(critique_mod, "validate_critique_checks", lambda payload, **kw: [])
    monkeypatch.setattr(critique_mod, "adaptive_critique_enabled", lambda state: True)
    monkeypatch.setattr(critique_mod, "is_creative_mode", lambda state: False)
    monkeypatch.setattr(
        "megaplan.audits.critique_evaluator.validate_evaluator_verdict",
        lambda payload, **kwargs: None,
    )

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state_path = plan_fixture.plan_dir / "state.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    all_check_ids = [c["id"] for c in CRITIQUE_CHECKS]

    # Test a few invalid complexity values.
    # Note: True is excluded because bool is a subclass of int and
    # True == 1 passes the range check.  False == 0 fails < 1.
    invalid_complexities = [
        (None, "missing"),
        (False, "bool False → 0 out of range"),
        ("high", "string"),
        (0, "out of range low"),
        (6, "out of range high"),
    ]

    for cx_val, cx_label in invalid_complexities:
        verdict = {
            "selections": [
                {
                    "check_id": "correctness",
                    "complexity": cx_val,
                    "complexity_justification": "Some justification.",
                },
            ],
            "skipped": [
                {"check_id": cid, "why": "skip"}
                for cid in all_check_ids
                if cid != "correctness"
            ],
            "evaluator_model": "claude-opus-4-7",
            "flag_verifications": [],
        }

        captured_checks: list[dict] = []

        def fake_parallel(state, plan_dir, *, root, model, checks, max_concurrent=None, effort=None, **kwargs):
            captured_checks.extend(checks)
            return WorkerResult(
                payload={
                    "checks": [
                        {"id": c["id"], "summary": "ok", "findings": [{"detail": "d", "flagged": False}]}
                        for c in checks
                    ],
                    "flags": [],
                    "verified_flag_ids": [],
                    "disputed_flag_ids": [],
                },
                raw_output="{}",
                duration_ms=1,
                cost_usd=0.0,
                session_id="critique",
            )

        monkeypatch.setattr(critique_mod, "run_parallel_critique", fake_parallel)

        def fake_run_step(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, **kwargs):
            if step == "critique_evaluator":
                return (
                    WorkerResult(payload=verdict, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="ev"),
                    "hermes", "persistent", False,
                )
            raise AssertionError(f"unexpected run_step call for {step}")

        monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step)
        monkeypatch.setattr(
            handlers_mod,
            "resolve_agent_mode",
            lambda step, args: ("hermes", "persistent", False, "fireworks:model"),
        )

        args = plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            tier_models={
                "critique": {
                    3: "deepseek:deepseek-v4-pro",
                    4: "claude:claude-sonnet-4-7",
                },
            },
        )

        from megaplan.types import CliError

        with pytest.raises(CliError, match="missing or invalid complexity"):
            megaplan.handle_critique(plan_fixture.root, args)

        # No checks should have reached the parallel dispatch.
        assert len(captured_checks) == 0, (
            f"no checks should reach dispatch with {cx_label} complexity"
        )


def test_operator_pin_overrides_all_per_lens_complexity_routing(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``execution.critic_model`` is pinned, the operator pin overrides
    every selected lens: no ``_resolved_agent_mode`` is attached to checks,
    and the critic dispatches to the pinned model instead of using complexity-
    based tier routing — even when ``tier_models.critique`` is available."""
    import json

    import megaplan.handlers as handlers_mod
    import megaplan.handlers.critique as critique_mod
    from megaplan.audits.robustness import CRITIQUE_CHECKS
    from megaplan.workers import WorkerResult

    monkeypatch.setattr(critique_mod, "validate_critique_checks", lambda payload, **kw: [])
    monkeypatch.setattr(critique_mod, "adaptive_critique_enabled", lambda state: True)
    monkeypatch.setattr(critique_mod, "is_creative_mode", lambda state: False)
    monkeypatch.setattr(
        "megaplan.audits.critique_evaluator.validate_evaluator_verdict",
        lambda payload, **kwargs: None,
    )

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state_path = plan_fixture.plan_dir / "state.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    # Set the operator pin — this must override complexity routing.
    persisted["config"]["critic_model"] = "deepseek-v4-pro"
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    all_check_ids = [c["id"] for c in CRITIQUE_CHECKS]
    verdict = {
        "selections": [
            {
                "check_id": "correctness",
                "complexity": 5,
                "complexity_justification": "High-complexity correctness probe.",
            },
            {
                "check_id": "scope",
                "complexity": 3,
                "complexity_justification": "Standard scope analysis.",
            },
        ],
        "skipped": [
            {"check_id": cid, "why": "skip"}
            for cid in all_check_ids
            if cid not in {"correctness", "scope"}
        ],
        "evaluator_model": "claude-opus-4-7",
        "flag_verifications": [],
    }

    captured_checks: list[dict] = []
    captured_model: list[str] = []

    def fake_parallel(state, plan_dir, *, root, model, checks, max_concurrent=None, effort=None, **kwargs):
        captured_checks.extend(checks)
        captured_model.append(model)
        return WorkerResult(
            payload={
                "checks": [
                    {"id": c["id"], "summary": "ok", "findings": [{"detail": "d", "flagged": False}]}
                    for c in checks
                ],
                "flags": [],
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
            },
            raw_output="{}",
            duration_ms=1,
            cost_usd=0.0,
            session_id="critique",
        )

    monkeypatch.setattr(critique_mod, "run_parallel_critique", fake_parallel)

    def fake_run_step(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, **kwargs):
        if step == "critique_evaluator":
            return (
                WorkerResult(payload=verdict, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="ev"),
                "hermes", "persistent", False,
            )
        raise AssertionError(f"unexpected run_step call for {step}")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step)
    monkeypatch.setattr(
        handlers_mod,
        "resolve_agent_mode",
        lambda step, args: ("hermes", "persistent", False, "fireworks:model"),
    )

    # Provide tier_models.critique — the pin must suppress tier routing.
    args = plan_fixture.make_args(
        plan=plan_fixture.plan_name,
        tier_models={
            "critique": {
                3: "deepseek:deepseek-v4-pro",
                5: "claude:claude-opus-4-7",
            },
        },
    )

    megaplan.handle_critique(plan_fixture.root, args)

    # (a) No _resolved_agent_mode on any check — the pin suppresses tier routing.
    for c in captured_checks:
        assert "_resolved_agent_mode" not in c, (
            f"operator pin must suppress per-check _resolved_agent_mode; "
            f"check '{c['id']}' has it"
        )

    # (b) The checks still flow through (correctness + scope = 2 lenses).
    assert len(captured_checks) == 2, (
        f"pin must not drop checks; expected 2, got {len(captured_checks)}"
    )

    # (c) The pinned model is dispatched: model passed to parallel critique
    # is the resolved pin, not any tier-spec model.
    # parse_agent_spec("hermes:deepseek:deepseek-v4-pro").model == "deepseek:deepseek-v4-pro"
    assert len(captured_model) == 1, "parallel critique must be called once"
    assert captured_model[0] == "deepseek:deepseek-v4-pro", (
        f"operator pin must dispatch critic to deepseek:deepseek-v4-pro; "
        f"got {captured_model[0]!r}"
    )


# ---------------------------------------------------------------------------
# T20: Integration tests — non-Hermes multi-check fan-out, fan-out failure
#      fallback, and operator pin after Hermes-only gate removal.
# ---------------------------------------------------------------------------


def test_non_hermes_adaptive_multi_check_can_fan_out(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After the Hermes-only gate removal (T19), non-Hermes agents (Claude,
    Codex) must enter the multi-check parallel branch in the adaptive path,
    receiving per-check ``_resolved_agent_mode`` from ``tier_models.critique``.

    This is an integration test: the full pipeline from evaluator verdict
    through complexity-based tier resolution to parallel dispatch is exercised
    with a non-Hermes critique agent.
    """
    import json

    import megaplan.handlers as handlers_mod
    import megaplan.handlers.critique as critique_mod
    from megaplan.audits.robustness import CRITIQUE_CHECKS
    from megaplan.workers import WorkerResult

    monkeypatch.setattr(critique_mod, "validate_critique_checks", lambda payload, **kw: [])
    monkeypatch.setattr(critique_mod, "adaptive_critique_enabled", lambda state: True)
    monkeypatch.setattr(critique_mod, "is_creative_mode", lambda state: False)
    monkeypatch.setattr(
        "megaplan.audits.critique_evaluator.validate_evaluator_verdict",
        lambda payload, **kwargs: None,
    )

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state_path = plan_fixture.plan_dir / "state.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    all_check_ids = [c["id"] for c in CRITIQUE_CHECKS]
    verdict = {
        "selections": [
            {
                "check_id": "correctness",
                "complexity": 4,
                "complexity_justification": "Correctness needs tier-4 scrutiny.",
            },
            {
                "check_id": "scope",
                "complexity": 3,
                "complexity_justification": "Scope check at standard tier 3.",
            },
        ],
        "skipped": [
            {"check_id": cid, "why": "skip"}
            for cid in all_check_ids
            if cid not in {"correctness", "scope"}
        ],
        "evaluator_model": "claude-opus-4-7",
        "flag_verifications": [],
    }

    captured_checks: list[dict] = []
    parallel_called: list[bool] = [False]

    def fake_parallel(state, plan_dir, *, root, model, checks, max_concurrent=None, effort=None, **kwargs):
        parallel_called[0] = True
        captured_checks.extend(checks)
        return WorkerResult(
            payload={
                "checks": [
                    {"id": c["id"], "summary": "ok", "findings": [{"detail": "d", "flagged": False}]}
                    for c in checks
                ],
                "flags": [],
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
            },
            raw_output="{}",
            duration_ms=1,
            cost_usd=0.0,
            session_id="critique",
        )

    monkeypatch.setattr(critique_mod, "run_parallel_critique", fake_parallel)

    def fake_run_step(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, **kwargs):
        if step == "critique_evaluator":
            return (
                WorkerResult(payload=verdict, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="ev"),
                "claude", "persistent", False,
            )
        raise AssertionError(f"unexpected run_step call for {step}")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step)
    # Critique slot resolves to Claude (non-Hermes) — the removed gate must
    # still let this enter the parallel branch.
    monkeypatch.setattr(
        handlers_mod,
        "resolve_agent_mode",
        lambda step, args: ("claude", "persistent", False, "claude-sonnet-4-7"),
    )

    def fake_resolve_tier_spec(args, spec, *, phase="execute"):
        if "deepseek" in spec:
            return ("hermes", "persistent", "deepseek-v4-pro")
        if "claude" in spec:
            return ("claude", "persistent", "claude-sonnet-4-7")
        return ("hermes", "persistent", spec)

    monkeypatch.setattr(
        "megaplan.execute.batch._resolve_tier_spec", fake_resolve_tier_spec
    )

    args = plan_fixture.make_args(
        plan=plan_fixture.plan_name,
        tier_models={
            "critique": {
                3: "deepseek:deepseek-v4-pro",
                4: "claude:claude-sonnet-4-7",
            },
        },
    )

    megaplan.handle_critique(plan_fixture.root, args)

    # (a) Parallel branch was entered.
    assert parallel_called[0] is True, (
        "non-Hermes adaptive multi-check must enter parallel branch after gate removal"
    )

    # (b) Both checks reached the parallel dispatcher.
    assert len(captured_checks) == 2, (
        f"expected 2 checks in parallel dispatch; got {len(captured_checks)}"
    )

    # (c) Each check carries _resolved_agent_mode from complexity-based routing.
    corr = next((c for c in captured_checks if c["id"] == "correctness"), None)
    assert corr is not None, "correctness must be in captured checks"
    assert "_resolved_agent_mode" in corr, (
        "non-Hermes adaptive path must attach _resolved_agent_mode to catalog checks"
    )
    assert corr["_resolved_agent_mode"].model == "claude-sonnet-4-7", (
        f"complexity 4 → claude-sonnet-4-7; got {corr['_resolved_agent_mode'].model!r}"
    )

    scope = next((c for c in captured_checks if c["id"] == "scope"), None)
    assert scope is not None, "scope must be in captured checks"
    assert "_resolved_agent_mode" in scope
    assert scope["_resolved_agent_mode"].model == "deepseek-v4-pro", (
        f"complexity 3 → deepseek-v4-pro; got {scope['_resolved_agent_mode'].model!r}"
    )


def test_non_hermes_adaptive_fan_out_failure_falls_back_sequentially(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When the parallel fan-out fails for a non-Hermes agent (Claude/Codex),
    the handler must fall back to the sequential critic path and pass
    ``selection_why`` targeting notes — the removed Hermes gate must NOT
    suppress fallback for non-Hermes agents.
    """
    import json

    import megaplan.handlers as handlers_mod
    import megaplan.handlers.critique as critique_mod
    from megaplan.audits.robustness import CRITIQUE_CHECKS
    from megaplan.workers import WorkerResult

    monkeypatch.setattr(critique_mod, "validate_critique_checks", lambda payload, **kw: [])
    monkeypatch.setattr(critique_mod, "adaptive_critique_enabled", lambda state: True)
    monkeypatch.setattr(critique_mod, "is_creative_mode", lambda state: False)
    monkeypatch.setattr(
        "megaplan.audits.critique_evaluator.validate_evaluator_verdict",
        lambda payload, **kwargs: None,
    )

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state_path = plan_fixture.plan_dir / "state.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    all_check_ids = [c["id"] for c in CRITIQUE_CHECKS]
    verdict = {
        "selections": [
            {
                "check_id": "correctness",
                "complexity": 4,
                "complexity_justification": "Edge-case validation needed.",
            },
            {
                "check_id": "scope",
                "complexity": 3,
                "complexity_justification": "Standard scope analysis.",
            },
        ],
        "skipped": [
            {"check_id": cid, "why": "skip"}
            for cid in all_check_ids
            if cid not in {"correctness", "scope"}
        ],
        "evaluator_model": "claude-opus-4-7",
        "flag_verifications": [],
    }

    captured_prompt_kwargs: dict = {}

    def fake_run_step(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, resolved=None, **kwargs):
        if step == "critique_evaluator":
            return (
                WorkerResult(payload=verdict, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="ev"),
                "codex", "persistent", False,
            )
        # Sequential fallback: capture the prompt_kwargs.
        captured_prompt_kwargs.update(prompt_kwargs or {})
        return (
            WorkerResult(
                payload={
                    "checks": [
                        {"id": cid, "summary": "ok", "findings": [{"detail": "d", "flagged": False}]}
                        for cid in ["correctness", "scope"]
                    ],
                    "flags": [],
                    "verified_flag_ids": [],
                    "disputed_flag_ids": [],
                },
                raw_output="{}",
                duration_ms=1,
                cost_usd=0.0,
                session_id="critique",
            ),
            "codex",
            "persistent",
            False,
        )

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step)

    # Force parallel to fail — this must trigger the sequential fallback even
    # when the agent is non-Hermes (Codex in this case).
    monkeypatch.setattr(
        critique_mod,
        "run_parallel_critique",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("parallel fan-out failed")),
    )

    # Critique slot resolves to Codex (non-Hermes).
    monkeypatch.setattr(
        handlers_mod,
        "resolve_agent_mode",
        lambda step, args: ("codex", "persistent", False, "openai:codex-3"),
    )

    def fake_resolve_tier_spec(args, spec, *, phase="execute"):
        if "deepseek" in spec:
            return ("hermes", "persistent", "deepseek-v4-pro")
        if "claude" in spec:
            return ("claude", "persistent", "claude-sonnet-4-7")
        return ("hermes", "persistent", spec)

    monkeypatch.setattr(
        "megaplan.execute.batch._resolve_tier_spec", fake_resolve_tier_spec
    )

    caplog.set_level("WARNING", logger="megaplan")

    args = plan_fixture.make_args(
        plan=plan_fixture.plan_name,
        tier_models={
            "critique": {
                3: "deepseek:deepseek-v4-pro",
                4: "claude:claude-sonnet-4-7",
            },
        },
    )

    megaplan.handle_critique(plan_fixture.root, args)

    # (a) Fallback warning must be logged.
    assert any(
        "M3A_WARN_PARALLEL_CRITIQUE_FALLBACK" in record.getMessage()
        for record in caplog.records
    ), "parallel critique fallback must fire for non-Hermes agents"

    # (b) Sequential critic received selection_why targeting notes.
    sel_why = captured_prompt_kwargs.get("selection_why", {})
    assert isinstance(sel_why, dict), "selection_why must be a dict"
    assert sel_why.get("correctness") == "Edge-case validation needed.", (
        f"catalog check _selection_why must be complexity_justification; "
        f"got {sel_why.get('correctness')!r}"
    )
    assert sel_why.get("scope") == "Standard scope analysis.", (
        f"_selection_why for scope must be complexity_justification; "
        f"got {sel_why.get('scope')!r}"
    )

    # (c) active_checks must be passed to the sequential critic.
    assert "active_checks" in captured_prompt_kwargs, (
        "sequential fallback must pass active_checks to the critic"
    )
    assert len(captured_prompt_kwargs["active_checks"]) == 2, (
        "sequential fallback must pass both selected checks"
    )


def test_operator_pin_forces_same_resolved_model_across_all_lenses_with_non_hermes(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After the Hermes-only gate removal, an operator pin must still force
    the same resolved model across ALL selected lenses regardless of the
    critique agent type (non-Hermes included).  No per-check
    ``_resolved_agent_mode`` is attached, and the pinned model is dispatched
    through the parallel (or sequential) branch.

    This is the integration complement to the T16 pin test: it proves the
    pin works end-to-end when the critique agent is Claude/Codex rather than
    Hermes.
    """
    import json

    import megaplan.handlers as handlers_mod
    import megaplan.handlers.critique as critique_mod
    from megaplan.audits.robustness import CRITIQUE_CHECKS
    from megaplan.workers import WorkerResult

    monkeypatch.setattr(critique_mod, "validate_critique_checks", lambda payload, **kw: [])
    monkeypatch.setattr(critique_mod, "adaptive_critique_enabled", lambda state: True)
    monkeypatch.setattr(critique_mod, "is_creative_mode", lambda state: False)
    monkeypatch.setattr(
        "megaplan.audits.critique_evaluator.validate_evaluator_verdict",
        lambda payload, **kwargs: None,
    )

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state_path = plan_fixture.plan_dir / "state.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    # Operator pin to deepseek-v4-pro — must override all complexity routing.
    persisted["config"]["critic_model"] = "deepseek-v4-pro"
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    all_check_ids = [c["id"] for c in CRITIQUE_CHECKS]
    verdict = {
        "selections": [
            {
                "check_id": "correctness",
                "complexity": 5,
                "complexity_justification": "High-complexity probe.",
            },
            {
                "check_id": "scope",
                "complexity": 3,
                "complexity_justification": "Standard analysis.",
            },
            {
                "check_id": "prerequisite_ordering",
                "complexity": 4,
                "complexity_justification": "Mid-tier ordering check.",
            },
        ],
        "skipped": [
            {"check_id": cid, "why": "skip"}
            for cid in all_check_ids
            if cid not in {"correctness", "scope", "prerequisite_ordering"}
        ],
        "evaluator_model": "claude-opus-4-7",
        "flag_verifications": [],
    }

    captured_checks: list[dict] = []
    captured_model: list[str] = []

    def fake_parallel(state, plan_dir, *, root, model, checks, max_concurrent=None, effort=None, **kwargs):
        captured_checks.extend(checks)
        captured_model.append(model)
        return WorkerResult(
            payload={
                "checks": [
                    {"id": c["id"], "summary": "ok", "findings": [{"detail": "d", "flagged": False}]}
                    for c in checks
                ],
                "flags": [],
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
            },
            raw_output="{}",
            duration_ms=1,
            cost_usd=0.0,
            session_id="critique",
        )

    monkeypatch.setattr(critique_mod, "run_parallel_critique", fake_parallel)

    def fake_run_step(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, **kwargs):
        if step == "critique_evaluator":
            return (
                WorkerResult(payload=verdict, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="ev"),
                "claude", "persistent", False,
            )
        raise AssertionError(f"unexpected run_step call for {step}")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step)
    # Critique slot resolves to Claude (non-Hermes) — the pin must still win.
    monkeypatch.setattr(
        handlers_mod,
        "resolve_agent_mode",
        lambda step, args: ("claude", "persistent", False, "claude-opus-4-7"),
    )

    # Provide tier_models.critique — the pin must suppress tier routing.
    args = plan_fixture.make_args(
        plan=plan_fixture.plan_name,
        tier_models={
            "critique": {
                3: "deepseek:deepseek-v4-pro",
                4: "claude:claude-sonnet-4-7",
                5: "claude:claude-opus-4-7",
            },
        },
    )

    megaplan.handle_critique(plan_fixture.root, args)

    # (a) All three checks reach the parallel dispatcher.
    assert len(captured_checks) == 3, (
        f"pin must not drop checks; expected 3, got {len(captured_checks)}"
    )

    # (b) No _resolved_agent_mode on any check — the pin suppresses tier routing
    # even when the critique agent is non-Hermes.
    for c in captured_checks:
        assert "_resolved_agent_mode" not in c, (
            f"operator pin must suppress per-check _resolved_agent_mode with "
            f"non-Hermes agent; check '{c['id']}' has it"
        )

    # (c) The pinned model is dispatched: model passed to parallel critique
    # is the resolved pin (deepseek:deepseek-v4-pro), not any tier-spec model
    # and not the critique slot's model (claude-opus-4-7).
    assert len(captured_model) == 1, "parallel critique must be called exactly once"
    assert captured_model[0] == "deepseek:deepseek-v4-pro", (
        f"operator pin must dispatch to deepseek:deepseek-v4-pro regardless "
        f"of agent type; got {captured_model[0]!r}"
    )
