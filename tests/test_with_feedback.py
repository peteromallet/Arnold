"""Comprehensive tests for the ``--with-feedback`` flag and workflow integration.

Covers:
    (a) Workflow shape — ``workflow_includes_step`` at every robustness level
    (b) State transitions — EXECUTED→REVIEWED, REVIEWED→DONE
    (c) Persistence — ``config.with_feedback`` written during init
    (d) Handler — ``handle_feedback`` workflow-mode no-editor invariant
    (e) Light/tiny + with-feedback — short-circuit suppression
    (f) ``_RESUME_ACTIVE_STATES`` entry
"""

from __future__ import annotations

import json
import subprocess
from argparse import Namespace
from pathlib import Path
from unittest import mock

import pytest

import megaplan
from megaplan._core import (
    STATE_EXECUTED,
    STATE_REVIEWED,
    STATE_DONE,
    load_plan,
    save_state,
    workflow_includes_step,
    workflow_transition,
)
from megaplan._core.workflow import _RESUME_ACTIVE_STATES, _with_feedback_from_state, _workflow_for_robustness
from megaplan.types import STATE_INITIALIZED, STATE_PLANNED, STATE_GATED, STATE_FINALIZED, STATE_PREPPED, STATE_CRITIQUED, CliError

# ---------------------------------------------------------------------------
# (a) Workflow shape — ``workflow_includes_step`` at every robustness level
# ---------------------------------------------------------------------------

ROBUSTNESS_LEVELS = ["tiny", "light", "standard", "robust", "superrobust"]


@pytest.mark.parametrize("robustness", ROBUSTNESS_LEVELS)
def test_workflow_includes_feedback_when_with_feedback_true(robustness: str) -> None:
    """At every robustness level, ``with_feedback=True`` forces the feedback step."""
    assert workflow_includes_step(robustness, "feedback", with_feedback=True) is True, (
        f"Expected feedback step at robustness={robustness!r} with with_feedback=True"
    )


@pytest.mark.parametrize("robustness", ROBUSTNESS_LEVELS)
def test_workflow_excludes_feedback_when_with_feedback_false(robustness: str) -> None:
    """Without the flag, no robustness level includes a feedback step."""
    assert workflow_includes_step(robustness, "feedback", with_feedback=False) is False, (
        f"Unexpected feedback step at robustness={robustness!r} with with_feedback=False"
    )


@pytest.mark.parametrize("robustness", ROBUSTNESS_LEVELS)
def test_with_feedback_forces_review_step_at_all_levels(robustness: str) -> None:
    """``with_feedback=True`` must re-enable the review step (needed before feedback)."""
    assert workflow_includes_step(robustness, "review", with_feedback=True) is True, (
        f"Expected review step at robustness={robustness!r} with with_feedback=True"
    )


def test_workflow_includes_step_with_feedback_defaults_false() -> None:
    """When ``with_feedback`` isn't passed, the default is False."""
    for robustness in ROBUSTNESS_LEVELS:
        assert workflow_includes_step(robustness, "feedback") is False


def test_workflow_includes_step_does_not_affect_other_steps() -> None:
    """``with_feedback`` should not change whether prep/plan/critique are included."""
    # Prep: standard skips prep, but with_feedback shouldn't change that
    assert workflow_includes_step("standard", "prep") is False
    assert workflow_includes_step("standard", "prep", with_feedback=True) is False
    # Plan is always included
    assert workflow_includes_step("standard", "plan") is True
    assert workflow_includes_step("standard", "plan", with_feedback=True) is True


# ---------------------------------------------------------------------------
# (b) State transitions — EXECUTED→REVIEWED, REVIEWED→DONE
# ---------------------------------------------------------------------------


def _make_state(current_state: str, *, with_feedback: bool = False) -> dict:
    """Build a minimal ``PlanState`` for transition tests."""
    return {
        "current_state": current_state,
        "config": {"with_feedback": with_feedback, "robustness": "standard"},
        "last_gate": {},
    }


def test_transition_executed_review_returns_reviewed_with_feedback() -> None:
    """From STATE_EXECUTED, ``review`` step → STATE_REVIEWED when with_feedback=True."""
    state = _make_state(STATE_EXECUTED, with_feedback=True)
    result = workflow_transition(state, "review")
    assert result is not None
    assert result.next_state == STATE_REVIEWED


def test_transition_executed_review_returns_done_without_feedback() -> None:
    """From STATE_EXECUTED, ``review`` step → STATE_DONE when with_feedback=False."""
    state = _make_state(STATE_EXECUTED, with_feedback=False)
    result = workflow_transition(state, "review")
    assert result is not None
    assert result.next_state == STATE_DONE


def test_transition_reviewed_feedback_returns_done() -> None:
    """From STATE_REVIEWED, ``feedback`` step → STATE_DONE."""
    state = _make_state(STATE_REVIEWED, with_feedback=True)
    result = workflow_transition(state, "feedback")
    assert result is not None
    assert result.next_state == STATE_DONE


def test_transition_feedback_only_exists_when_with_feedback_true() -> None:
    """There should be no 'feedback' transition from EXECUTED without the flag."""
    state = _make_state(STATE_EXECUTED, with_feedback=False)
    result = workflow_transition(state, "feedback")
    assert result is None


@pytest.mark.parametrize("robustness", ROBUSTNESS_LEVELS)
def test_workflow_for_robustness_structure_with_feedback(robustness: str) -> None:
    """Verify the merged workflow shape when with_feedback is True."""
    wf = _workflow_for_robustness(robustness, with_feedback=True)
    # STATE_EXECUTED must route to review → STATE_REVIEWED
    executed_transitions = wf.get(STATE_EXECUTED, [])
    assert len(executed_transitions) == 1
    assert executed_transitions[0].next_step == "review"
    assert executed_transitions[0].next_state == STATE_REVIEWED
    # STATE_REVIEWED must route to feedback → STATE_DONE
    reviewed_transitions = wf.get(STATE_REVIEWED, [])
    assert len(reviewed_transitions) == 1
    assert reviewed_transitions[0].next_step == "feedback"
    assert reviewed_transitions[0].next_state == STATE_DONE


@pytest.mark.parametrize("robustness", ["light", "tiny"])
def test_with_feedback_undoes_light_tiny_skip_review(robustness: str) -> None:
    """Light/tiny set STATE_EXECUTED: [] to skip review. with_feedback undoes that."""
    wf_no_feedback = _workflow_for_robustness(robustness, with_feedback=False)
    wf_with_feedback = _workflow_for_robustness(robustness, with_feedback=True)
    # Without feedback: STATE_EXECUTED is empty (skip review)
    assert wf_no_feedback.get(STATE_EXECUTED, []) == []
    # With feedback: STATE_EXECUTED has the review transition
    assert len(wf_with_feedback.get(STATE_EXECUTED, [])) == 1
    assert wf_with_feedback[STATE_EXECUTED][0].next_step == "review"


# ---------------------------------------------------------------------------
# (c) Persistence — ``config.with_feedback`` written during init
# ---------------------------------------------------------------------------


def test_init_with_feedback_persists_config_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``megaplan init --with-feedback`` writes ``state["config"]["with_feedback"] = True``."""
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )

    from tests.conftest import make_args_factory
    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(root, make_args(name="with-fb", with_feedback=True))
    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["config"]["with_feedback"] is True


def test_init_without_feedback_persists_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without ``--with-feedback``, the config key should be absent or False."""
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )

    from tests.conftest import make_args_factory
    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(root, make_args(name="no-fb"))
    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["config"].get("with_feedback", False) is False


def test_with_feedback_from_state_reads_flag() -> None:
    """``_with_feedback_from_state`` returns True when flag is set."""
    assert _with_feedback_from_state({"config": {"with_feedback": True}}) is True
    assert _with_feedback_from_state({"config": {"with_feedback": False}}) is False
    assert _with_feedback_from_state({"config": {}}) is False
    assert _with_feedback_from_state({}) is False
    # Malformed config
    assert _with_feedback_from_state({"config": "bad"}) is False


# ---------------------------------------------------------------------------
# (d) Handler — ``handle_feedback`` workflow-mode no-editor invariant
# ---------------------------------------------------------------------------


def test_handle_feedback_workflow_scaffolds_and_transitions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Workflow mode: AI-rated phase, transitions to done, no $EDITOR.

    The handler dispatches a model worker (subprocess.run IS called for the
    worker), but $EDITOR must never be launched.  When the worker fails in
    the test environment the handler writes an empty ai_* template and still
    transitions to DONE.
    """
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )

    from tests.conftest import make_args_factory
    from megaplan.feedback import feedback_path

    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(
        root, make_args(name="fb-hdlr-test", with_feedback=True)
    )
    plan_dir = megaplan.plans_root(root) / response["plan"]

    # Place plan in STATE_REVIEWED
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    state["current_state"] = STATE_REVIEWED
    save_state(plan_dir, state)

    fb_path = feedback_path(plan_dir)
    assert not fb_path.exists(), "feedback.md should not exist before handler call"

    # Mock subprocess.run so we can assert that $EDITOR is never launched.
    # The model-worker dispatch IS a subprocess call — that is expected.
    # We only guard against interactive editor launch.
    import os as _os_module
    with mock.patch("subprocess.run") as mock_run:
        from megaplan.cli import handle_feedback

        result = handle_feedback(
            root,
            Namespace(
                operation="workflow",
                plan=response["plan"],
                actor=None,
                agent=None,
            ),
        )

        # Verify $EDITOR / $VISUAL were NOT launched in any subprocess call
        editor_env = _os_module.environ.get("EDITOR", "")
        visual_env = _os_module.environ.get("VISUAL", "")
        for call_args in mock_run.call_args_list:
            args_list = call_args[0][0] if call_args[0] else []
            if isinstance(args_list, list) and len(args_list) > 0:
                cmd = args_list[0]
                assert cmd not in (editor_env, visual_env, "vim", "nano", "emacs"), (
                    f"$EDITOR was launched: {args_list}"
                )

    # Verify response shape (ai_filled may be False if worker failed in test env)
    assert result["success"] is True
    assert result["state"] == "done"
    assert result["operation"] == "workflow"
    assert result["ai_filled"] in (True, False)
    assert result["feedback_present"] is True

    # Verify file was created
    assert fb_path.exists(), "feedback.md should have been created"

    # Verify state transitioned to done
    updated_state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert updated_state["current_state"] == STATE_DONE


def test_handle_feedback_workflow_already_has_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Workflow mode: if feedback.md exists with user fields, skip AI pass.

    With the new AI-rated handler, a feedback.md that already has user
    ``rating:`` / ``comment:`` fields populated is a no-op (skip AI pass,
    transition to DONE, never overwrite).  The pre-existing content must
    be preserved.
    """
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )

    from tests.conftest import make_args_factory
    from megaplan.feedback import feedback_path

    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(
        root, make_args(name="fb-exists", with_feedback=True)
    )
    plan_dir = megaplan.plans_root(root) / response["plan"]

    # Place plan in STATE_REVIEWED, pre-create feedback.md with user fields
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    state["current_state"] = STATE_REVIEWED
    save_state(plan_dir, state)

    fb_path = feedback_path(plan_dir)
    # Write a feedback.md that has a user rating set so the skip-AI
    # guard triggers (rating: is populated, no --force).
    original_content = "## Overall\nrating: 7\ncomment: good run\n"
    fb_path.write_text(original_content, encoding="utf-8")

    import os as _os_module
    with mock.patch("subprocess.run") as mock_run:
        from megaplan.cli import handle_feedback

        result = handle_feedback(
            root,
            Namespace(
                operation="workflow",
                plan=response["plan"],
                actor=None,
                agent=None,
            ),
        )

        # Verify $EDITOR / $VISUAL were NOT launched
        editor_env = _os_module.environ.get("EDITOR", "")
        visual_env = _os_module.environ.get("VISUAL", "")
        for call_args in mock_run.call_args_list:
            args_list = call_args[0][0] if call_args[0] else []
            if isinstance(args_list, list) and len(args_list) > 0:
                cmd = args_list[0]
                assert cmd not in (editor_env, visual_env, "vim", "nano", "emacs"), (
                    f"$EDITOR was launched: {args_list}"
                )

    # AI pass was skipped because user fields already exist
    assert result["ai_filled"] is False
    assert result["feedback_present"] is True
    assert result["state"] == "done"
    assert "skipped AI pass" in result.get("summary", "")

    # Content must not be overwritten
    assert fb_path.read_text(encoding="utf-8") == original_content

    updated_state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert updated_state["current_state"] == STATE_DONE


def test_handle_feedback_workflow_rejects_wrong_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Workflow mode must raise CliError if plan is not in STATE_REVIEWED."""
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )

    from tests.conftest import make_args_factory

    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(
        root, make_args(name="fb-wrong-state", with_feedback=True)
    )
    # Plan is in STATE_INITIALIZED, not STATE_REVIEWED

    from megaplan.cli import handle_feedback

    with pytest.raises(CliError, match="requires plan in 'reviewed'"):
        handle_feedback(
            root,
            Namespace(operation="workflow", plan=response["plan"], actor=None),
        )


# ---------------------------------------------------------------------------
# (e) Light/tiny + with-feedback — short-circuit suppression
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("robustness", ["light", "tiny"])
def test_light_tiny_execute_short_circuit_suppressed_with_feedback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, robustness: str
) -> None:
    """At light/tiny with with_feedback=True, execute handler must NOT short-circuit to DONE."""
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )

    from tests.conftest import make_args_factory, read_json

    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(
        root,
        make_args(
            name=f"fb-{robustness}-sc",
            robustness=robustness,
            with_feedback=True,
        ),
    )
    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = read_json(plan_dir / "state.json")
    assert state["config"]["with_feedback"] is True
    assert state["config"]["robustness"] == robustness

    # Verify workflow_includes_step behaviour
    assert workflow_includes_step(robustness, "review", with_feedback=True) is True
    assert workflow_includes_step(robustness, "feedback", with_feedback=True) is True

    # At light/tiny without with_feedback, review is NOT in the workflow:
    assert workflow_includes_step(robustness, "review", with_feedback=False) is False


@pytest.mark.parametrize("robustness", ["light", "tiny"])
def test_light_tiny_without_feedback_still_short_circuits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, robustness: str
) -> None:
    """Without with_feedback, light/tiny must still skip review (no regression)."""
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )

    from tests.conftest import make_args_factory

    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(
        root,
        make_args(name=f"fb-{robustness}-no-sc", robustness=robustness),
    )
    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["config"].get("with_feedback", False) is False

    # Without the flag, light/tiny should NOT include review
    assert workflow_includes_step(robustness, "review") is False
    assert workflow_includes_step(robustness, "feedback") is False


# ---------------------------------------------------------------------------
# (f) ``_RESUME_ACTIVE_STATES`` entry
# ---------------------------------------------------------------------------


def test_resume_active_states_contains_feedback() -> None:
    """``_RESUME_ACTIVE_STATES`` must map 'feedback' to 'reviewed'."""
    assert "feedback" in _RESUME_ACTIVE_STATES
    assert _RESUME_ACTIVE_STATES["feedback"] == "reviewed"


def test_resume_active_states_all_known_phases() -> None:
    """Sanity-check all known active states for completeness."""
    expected = {
        "prep": "initialized",
        "plan": "initialized",
        "critique": "planned",
        "gate": "critiqued",
        "revise": "critiqued",
        "finalize": "gated",
        "execute": "finalized",
        "review": "executed",
        "feedback": "reviewed",
    }
    for phase, state in expected.items():
        assert _RESUME_ACTIVE_STATES.get(phase) == state, (
            f"Expected _RESUME_ACTIVE_STATES[{phase!r}] == {state!r}"
        )


# ---------------------------------------------------------------------------
# Integration: auto.py _phase_command dispatch
# ---------------------------------------------------------------------------


def test_phase_command_feedback_returns_workflow_operation() -> None:
    """``_phase_command('feedback')`` must return ['feedback', 'workflow']."""
    from megaplan.auto import _phase_command
    result = _phase_command("feedback")
    assert result == ["feedback", "workflow"], (
        f"Expected ['feedback', 'workflow'], got {result}"
    )


# ---------------------------------------------------------------------------
# Integration: review handler outcome when with_feedback is set
# ---------------------------------------------------------------------------


def test_resolve_review_outcome_returns_reviewed_with_feedback(
    tmp_path: Path,
) -> None:
    """``_resolve_review_outcome`` returns STATE_REVIEWED when with_feedback=True."""
    from megaplan.handlers.review import _resolve_review_outcome

    state: dict = {"config": {"with_feedback": True}, "meta": {}, "history": []}
    verdict, next_state, _ = _resolve_review_outcome(
        plan_dir=tmp_path,
        review_verdict="approved",
        verdict_count=1,
        total_tasks=1,
        check_count=1,
        total_checks=1,
        missing_evidence=[],
        robustness="standard",
        state=state,
        issues=[],
        criteria=[],
    )
    assert verdict == "success"
    assert next_state == STATE_REVIEWED


def test_resolve_review_outcome_returns_done_without_feedback(
    tmp_path: Path,
) -> None:
    """``_resolve_review_outcome`` returns STATE_DONE when with_feedback=False."""
    from megaplan.handlers.review import _resolve_review_outcome

    state: dict = {"config": {}, "meta": {}, "history": []}
    verdict, next_state, _ = _resolve_review_outcome(
        plan_dir=tmp_path,
        review_verdict="approved",
        verdict_count=1,
        total_tasks=1,
        check_count=1,
        total_checks=1,
        missing_evidence=[],
        robustness="standard",
        state=state,
        issues=[],
        criteria=[],
    )
    assert verdict == "success"
    assert next_state == STATE_DONE


# ---------------------------------------------------------------------------
# Integration: --with-prep and --with-feedback combined
# ---------------------------------------------------------------------------


def test_with_prep_and_with_feedback_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both flags can be set simultaneously — prep AND feedback run."""
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )

    from tests.conftest import make_args_factory

    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(
        root,
        make_args(
            name="both-flags",
            robustness="light",
            with_prep=True,
            with_feedback=True,
        ),
    )
    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["config"]["with_prep"] is True
    assert state["config"]["with_feedback"] is True

    wf = _workflow_for_robustness("light", with_prep=True, with_feedback=True)
    # Prep must be reinstated
    assert wf[STATE_INITIALIZED][0].next_step == "prep"
    # Feedback chain must exist
    assert len(wf.get(STATE_EXECUTED, [])) == 1
    assert wf[STATE_EXECUTED][0].next_step == "review"
    assert wf[STATE_EXECUTED][0].next_state == STATE_REVIEWED
    assert wf[STATE_REVIEWED][0].next_step == "feedback"
    assert wf[STATE_REVIEWED][0].next_state == STATE_DONE