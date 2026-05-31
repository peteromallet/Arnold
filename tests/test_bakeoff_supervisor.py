"""Tests for the bakeoff control binding.

All bakeoff callers use direct ``ControlBinding`` injection (passing a
``BakeoffControlBinding`` instance via ``bakeoff_control_binding()``).
No string dispatch (``binding="bakeoff"``) is added; the control interface's
``_resolve_binding_and_state`` only supports the legacy ``"planning"`` string
path.
"""

from __future__ import annotations

from megaplan.control_interface import (
    CONTROL_TARGET_ABORT,
    ControlTarget,
    ControlTargetRef,
    ControlTransitionRequest,
    apply_transition,
    read_valid_targets,
)
from megaplan.run_outcome import RunOutcome
from megaplan.supervisor.bakeoff_binding import (
    BAKEOFF_TARGET_COMPARE,
    BAKEOFF_TARGET_MERGE,
    BAKEOFF_TARGET_RUN_PROFILES,
    BAKEOFF_TARGET_SELECT,
    bakeoff_control_binding,
    bakeoff_run_state_view,
)


def _state(*, phase: str = "running", chosen_profile: str | None = None, terminal: bool = False) -> dict[str, object]:
    profiles: list[dict[str, object]] = [
        {
            "name": "alpha",
            "worktree": "/tmp/alpha",
            "plan_id": "alpha-plan",
            "pid": None,
            "launched_at": None,
            "terminated_at": None,
            "log_path": "/tmp/alpha.log",
            "outcome_path": "/tmp/alpha.json",
            "outcome": {"status": "done"} if terminal else None,
        },
        {
            "name": "beta",
            "worktree": "/tmp/beta",
            "plan_id": "beta-plan",
            "pid": None,
            "launched_at": None,
            "terminated_at": None,
            "log_path": "/tmp/beta.log",
            "outcome_path": "/tmp/beta.json",
            "outcome": {"status": "failed"} if terminal else None,
        },
    ]
    return {
        "experiment_id": "exp-1",
        "phase": phase,
        "profiles": profiles,
        "chosen_profile": chosen_profile,
    }


def test_bakeoff_run_state_view_projects_supervisor_metadata() -> None:
    merged = bakeoff_run_state_view(_state(phase="merged", terminal=True))
    compared = bakeoff_run_state_view(_state(phase="compared", terminal=True))
    abandoned = bakeoff_run_state_view(_state(phase="abandoned", terminal=True))
    running = bakeoff_run_state_view(_state())

    assert merged.run_id == "exp-1"
    assert merged.outcome == RunOutcome.SUCCEEDED
    assert merged.cursor == "merged"
    assert merged.metadata["projection_surface"] == "supervisor"
    assert compared.outcome == RunOutcome.AWAITING_HUMAN
    assert abandoned.outcome == RunOutcome.FAILED
    assert running.outcome is None
    assert running.metadata["has_terminal_profile_set"] is False


def test_bakeoff_binding_projects_running_targets_without_planning_conversion(
    monkeypatch,
) -> None:
    def _boom(*_args, **_kwargs):
        raise AssertionError("planning conversion should not be used for bakeoff state")

    monkeypatch.setattr("megaplan.planning.planning_run_state_view", _boom)

    run_state = bakeoff_run_state_view(_state())
    projection = read_valid_targets(run_state, bakeoff_control_binding())
    recovery = read_valid_targets(run_state, bakeoff_control_binding(), recovery=True)

    assert [target.id for target in projection] == [
        BAKEOFF_TARGET_RUN_PROFILES,
        CONTROL_TARGET_ABORT,
    ]
    assert [target.id for target in recovery] == [BAKEOFF_TARGET_RUN_PROFILES]


def test_bakeoff_binding_projects_compare_once_profiles_are_terminal() -> None:
    projection = read_valid_targets(
        bakeoff_run_state_view(_state(terminal=True)),
        bakeoff_control_binding(),
    )

    assert [target.id for target in projection] == [
        BAKEOFF_TARGET_COMPARE,
        CONTROL_TARGET_ABORT,
    ]


def test_bakeoff_binding_projects_select_then_merge_targets() -> None:
    compared = read_valid_targets(
        bakeoff_run_state_view(_state(phase="compared", terminal=True)),
        bakeoff_control_binding(),
    )
    compared_with_choice = read_valid_targets(
        bakeoff_run_state_view(_state(phase="compared", chosen_profile="alpha", terminal=True)),
        bakeoff_control_binding(),
    )
    picked = read_valid_targets(
        bakeoff_run_state_view(_state(phase="picked", chosen_profile="alpha", terminal=True)),
        bakeoff_control_binding(),
    )

    assert [target.id for target in compared] == [
        BAKEOFF_TARGET_SELECT,
        CONTROL_TARGET_ABORT,
    ]
    assert [target.id for target in compared_with_choice] == [
        BAKEOFF_TARGET_SELECT,
        BAKEOFF_TARGET_MERGE,
        CONTROL_TARGET_ABORT,
    ]
    assert [target.id for target in picked] == [
        BAKEOFF_TARGET_MERGE,
        CONTROL_TARGET_ABORT,
    ]


def test_bakeoff_binding_terminal_phases_expose_no_targets() -> None:
    merged = read_valid_targets(
        bakeoff_run_state_view(_state(phase="merged", chosen_profile="alpha", terminal=True)),
        bakeoff_control_binding(),
    )
    abandoned = read_valid_targets(
        bakeoff_run_state_view(_state(phase="abandoned", terminal=True)),
        bakeoff_control_binding(),
    )

    assert tuple(merged) == ()
    assert tuple(abandoned) == ()


def test_bakeoff_binding_apply_transition_projects_internal_bakeoff_action() -> None:
    run_state = bakeoff_run_state_view(_state(phase="picked", chosen_profile="alpha", terminal=True))

    result = apply_transition(
        run_state,
        ControlTransitionRequest(action=BAKEOFF_TARGET_MERGE, target_id=BAKEOFF_TARGET_MERGE),
        bakeoff_control_binding(),
    )

    assert result.accepted is True
    assert result.mutated is False
    assert result.reason == "bakeoff:merge"
    assert result.artifacts == {
        "target_id": BAKEOFF_TARGET_MERGE,
        "bakeoff_action": "merge",
        "experiment_id": "exp-1",
    }


def test_bakeoff_binding_select_transition_carries_chosen_profile() -> None:
    run_state = bakeoff_run_state_view(
        _state(phase="compared", chosen_profile="alpha", terminal=True)
    )

    result = apply_transition(
        run_state,
        ControlTransitionRequest(action=BAKEOFF_TARGET_SELECT, target_id=BAKEOFF_TARGET_SELECT),
        bakeoff_control_binding(),
    )

    assert result.accepted is True
    assert result.artifacts["bakeoff_action"] == "pick"
    assert result.artifacts["profile"] == "alpha"


# ── raw-state coercion ───────────────────────────────────────────────


def test_raw_state_coercion_empty_dict_yields_safe_defaults() -> None:
    """Empty bakeoff state coerces to safe RunStateView defaults without error."""
    view = bakeoff_run_state_view({})
    assert view.run_id == "bakeoff-run"
    assert view.outcome is None
    assert view.cursor is None
    assert view.metadata["projection_surface"] == "supervisor"
    assert view.metadata["has_terminal_profile_set"] is False


def test_raw_state_coercion_non_dict_is_wrapped() -> None:
    """Non-dict raw state is wrapped via dict() and coerced."""
    # dict([("phase", "merged")]) -> {"phase": "merged"} so bakeoff phase is found
    view = bakeoff_run_state_view([("phase", "merged")])  # type: ignore[arg-type]
    assert view.run_id == "bakeoff-run"
    assert view.cursor == "merged"
    assert view.outcome == RunOutcome.SUCCEEDED


def test_raw_state_coercion_run_id_override() -> None:
    """Caller-supplied run_id overrides experiment_id from state."""
    view = bakeoff_run_state_view(
        {"experiment_id": "exp-2", "phase": "merged"}, run_id="custom-id"
    )
    assert view.run_id == "custom-id"
    assert view.outcome == RunOutcome.SUCCEEDED


def test_raw_state_coercion_missing_phase() -> None:
    """Bakeoff state with no phase key yields None cursor/outcome."""
    view = bakeoff_run_state_view({"experiment_id": "exp-3", "profiles": []})
    assert view.cursor is None
    assert view.outcome is None
    assert view.run_id == "exp-3"


def test_raw_state_coercion_non_string_phase() -> None:
    """Non-string phase value is treated as absent (None)."""
    view = bakeoff_run_state_view({"phase": 42, "experiment_id": "exp-4"})
    assert view.cursor is None
    assert view.outcome is None


def test_raw_state_coercion_unknown_phase() -> None:
    """Unknown bakeoff phase yields None outcome but preserves cursor."""
    view = bakeoff_run_state_view({"phase": "unknown-phase", "experiment_id": "exp-5"})
    assert view.cursor == "unknown-phase"
    assert view.outcome is None


def test_raw_state_coercion_preserves_raw_state_bidirectionally() -> None:
    """RunStateView.raw_state is a dict copy with the same key/values as the input."""
    raw = {"phase": "running", "experiment_id": "exp-6", "profiles": []}
    view = bakeoff_run_state_view(raw)
    assert view.raw_state == raw  # value equality — dict(raw_state) creates a copy
    assert view.raw_state is not raw  # not the same object, but equal


def test_raw_state_coercion_missing_profiles_key() -> None:
    """State without 'profiles' key defaults to has_terminal_profile_set=False."""
    view = bakeoff_run_state_view({"phase": "running", "experiment_id": "exp-7"})
    assert view.metadata["has_terminal_profile_set"] is False


def test_raw_state_coercion_non_list_profiles() -> None:
    """When profiles is not a list, has_terminal_profile_set is False."""
    view = bakeoff_run_state_view(
        {"phase": "running", "experiment_id": "exp-8", "profiles": "not-a-list"}
    )
    assert view.metadata["has_terminal_profile_set"] is False


def test_raw_state_coercion_non_mapping_profile_entry() -> None:
    """A profile entry that is not a Mapping makes has_terminal_profile_set False."""
    view = bakeoff_run_state_view(
        {
            "phase": "running",
            "experiment_id": "exp-9",
            "profiles": ["not-a-dict", {"name": "ok", "outcome": {"status": "done"}}],
        }
    )
    assert view.metadata["has_terminal_profile_set"] is False


def test_raw_state_coercion_missing_outcome_on_profile() -> None:
    """Profile without 'outcome' key is not terminal."""
    view = bakeoff_run_state_view(
        {
            "phase": "running",
            "experiment_id": "exp-10",
            "profiles": [{"name": "alpha", "pid": None, "launched_at": None}],
        }
    )
    assert view.metadata["has_terminal_profile_set"] is False


def test_raw_state_coercion_non_dict_outcome_on_profile() -> None:
    """Profile with non-Mapping outcome is not terminal."""
    view = bakeoff_run_state_view(
        {
            "phase": "running",
            "experiment_id": "exp-11",
            "profiles": [{"name": "alpha", "outcome": "done"}],
        }
    )
    assert view.metadata["has_terminal_profile_set"] is False


def test_raw_state_coercion_non_string_status_in_outcome() -> None:
    """Profile outcome with non-string status is not terminal."""
    view = bakeoff_run_state_view(
        {
            "phase": "running",
            "experiment_id": "exp-12",
            "profiles": [{"name": "alpha", "outcome": {"status": 1}}],
        }
    )
    assert view.metadata["has_terminal_profile_set"] is False


def test_raw_state_coercion_unknown_status_is_not_terminal() -> None:
    """Profile outcome with unknown status string is not terminal."""
    view = bakeoff_run_state_view(
        {
            "phase": "running",
            "experiment_id": "exp-13",
            "profiles": [{"name": "alpha", "outcome": {"status": "in-progress"}}],
        }
    )
    assert view.metadata["has_terminal_profile_set"] is False


def test_raw_state_coercion_mixed_terminal_profiles() -> None:
    """When one profile is terminal and the other isn't, has_terminal_profile_set is False."""
    view = bakeoff_run_state_view(
        {
            "phase": "running",
            "experiment_id": "exp-14",
            "profiles": [
                {"name": "alpha", "outcome": {"status": "done"}},
                {"name": "beta", "outcome": {"status": "running"}},
            ],
        }
    )
    assert view.metadata["has_terminal_profile_set"] is False


# ── neutral projections ──────────────────────────────────────────────

_EXPECTED_NEUTRAL_IDS = frozenset(
    {
        BAKEOFF_TARGET_RUN_PROFILES,
        BAKEOFF_TARGET_COMPARE,
        BAKEOFF_TARGET_SELECT,
        BAKEOFF_TARGET_MERGE,
        CONTROL_TARGET_ABORT,
    }
)

_PLANNING_SPECIFIC_IDS = frozenset(
    {"force-advance", "re-route", "recover-from-stuck", "force-proceed", "replan"}
)


def _all_target_ids(view: RunStateView) -> frozenset[str]:
    binding = bakeoff_control_binding()
    fwd = {t.id for t in binding.valid_targets(view)}
    rev = {t.id for t in binding.recover_targets(view)}
    return fwd | rev


def test_neutral_projection_all_targets_are_neutral() -> None:
    """Every target id exposed by bakeoff binding is from the neutral set."""
    for raw_state in [
        _state(),
        _state(terminal=True),
        _state(phase="compared", terminal=True),
        _state(phase="compared", chosen_profile="alpha", terminal=True),
        _state(phase="picked", chosen_profile="alpha", terminal=True),
        _state(phase="merged", terminal=True),
        _state(phase="abandoned", terminal=True),
    ]:
        view = bakeoff_run_state_view(raw_state)
        ids = _all_target_ids(view)
        assert ids.issubset(_EXPECTED_NEUTRAL_IDS), (
            f"phase={raw_state.get('phase')}: got non-neutral ids {ids - _EXPECTED_NEUTRAL_IDS}"
        )


def test_neutral_projection_no_planning_specific_ids_leak() -> None:
    """No planning-specific target ids leak into bakeoff projections."""
    for raw_state in [
        _state(),
        _state(terminal=True),
        _state(phase="compared", terminal=True),
        _state(phase="compared", chosen_profile="alpha", terminal=True),
        _state(phase="picked", chosen_profile="alpha", terminal=True),
        _state(phase="merged", terminal=True),
        _state(phase="abandoned", terminal=True),
    ]:
        view = bakeoff_run_state_view(raw_state)
        ids = _all_target_ids(view)
        leak = ids & _PLANNING_SPECIFIC_IDS
        assert not leak, f"phase={raw_state.get('phase')}: leaked planning ids {leak}"


def test_neutral_projection_target_metadata_is_consistent() -> None:
    """Every neutral target carries supervisor-surface metadata."""
    view = bakeoff_run_state_view(_state())
    binding = bakeoff_control_binding()
    for target in binding.valid_targets(view):
        assert target.metadata.get("kind") == "control_target"
        assert target.metadata.get("actionable") is True
        assert target.metadata.get("surface") == "supervisor"
        assert "bakeoff_phase" in target.metadata


def test_neutral_projection_recovery_only_returns_run_profiles() -> None:
    """Recovery targets are only run-profiles for running phase; non-running uses forward targets."""
    view = bakeoff_run_state_view(_state())
    binding = bakeoff_control_binding()
    recover = {t.id for t in binding.recover_targets(view)}
    assert recover == {BAKEOFF_TARGET_RUN_PROFILES}

    # For non-running phases, recover_targets returns the same targets as valid_targets
    # (the binding only has recovery-specific logic for the 'running' phase)
    for phase in ("compared", "picked", "merged", "abandoned"):
        phase_view = bakeoff_run_state_view(_state(phase=phase, terminal=True))
        fwd = {t.id for t in binding.valid_targets(phase_view)}
        rev = {t.id for t in binding.recover_targets(phase_view)}
        assert rev == fwd, f"phase={phase}: recovery should match forward targets"


def test_neutral_projection_abort_is_always_present_in_forward_targets() -> None:
    """Abort is available as a forward target in all non-terminal phases."""
    for raw_state in [
        _state(),
        _state(terminal=True),
        _state(phase="compared", terminal=True),
        _state(phase="compared", chosen_profile="alpha", terminal=True),
        _state(phase="picked", chosen_profile="alpha", terminal=True),
    ]:
        view = bakeoff_run_state_view(raw_state)
        binding = bakeoff_control_binding()
        ids = {t.id for t in binding.valid_targets(view)}
        assert CONTROL_TARGET_ABORT in ids, (
            f"phase={raw_state.get('phase')}: abort not in {ids}"
        )


# ── ControlBinding protocol completeness ─────────────────────────────


def test_binding_valid_targets_returns_only_control_targets() -> None:
    """valid_targets returns only ControlTarget instances."""
    view = bakeoff_run_state_view(_state(terminal=True))
    binding = bakeoff_control_binding()
    targets = tuple(binding.valid_targets(view))
    assert all(isinstance(t, (ControlTarget, ControlTargetRef)) for t in targets)
    assert len(targets) >= 1


def test_binding_recover_targets_returns_only_control_targets() -> None:
    """recover_targets returns only ControlTarget instances."""
    view = bakeoff_run_state_view(_state())
    binding = bakeoff_control_binding()
    targets = tuple(binding.recover_targets(view))
    assert all(isinstance(t, (ControlTarget, ControlTargetRef)) for t in targets)


def test_binding_apply_transition_rejects_unknown_target() -> None:
    """Unknown target id is rejected."""
    view = bakeoff_run_state_view(_state())
    result = apply_transition(
        view,
        ControlTransitionRequest(action="unknown-target", target_id="unknown-target"),
        bakeoff_control_binding(),
    )
    assert result.accepted is False
    assert "unimplemented" in (result.reason or "")


def test_binding_apply_transition_rejects_unavailable_target() -> None:
    """A known target id that's not valid for the current phase is rejected."""
    # 'merge' is not available during 'running' phase
    view = bakeoff_run_state_view(_state())
    result = apply_transition(
        view,
        ControlTransitionRequest(action=BAKEOFF_TARGET_MERGE, target_id=BAKEOFF_TARGET_MERGE),
        bakeoff_control_binding(),
    )
    assert result.accepted is False
    assert "unavailable" in (result.reason or "")


def test_binding_synthesize_artifacts_unknown_target_returns_empty() -> None:
    """synthesize_artifacts for unknown target returns empty dict."""
    binding = bakeoff_control_binding()
    view = bakeoff_run_state_view(_state())
    artifacts = binding.synthesize_artifacts(
        view,
        ControlTransitionRequest(action="unknown", target_id="unknown"),
    )
    assert artifacts == {}


def test_binding_synthesize_artifacts_run_profiles_returns_resume() -> None:
    """synthesize_artifacts for run-profiles returns bakeoff_action='resume'."""
    binding = bakeoff_control_binding()
    view = bakeoff_run_state_view(_state())
    artifacts = binding.synthesize_artifacts(
        view,
        ControlTransitionRequest(
            action=BAKEOFF_TARGET_RUN_PROFILES, target_id=BAKEOFF_TARGET_RUN_PROFILES
        ),
    )
    assert artifacts["bakeoff_action"] == "resume"
    assert artifacts["target_id"] == BAKEOFF_TARGET_RUN_PROFILES


def test_binding_synthesize_artifacts_compare_returns_compare() -> None:
    """synthesize_artifacts for compare returns bakeoff_action='compare'."""
    binding = bakeoff_control_binding()
    view = bakeoff_run_state_view(_state(terminal=True))
    artifacts = binding.synthesize_artifacts(
        view,
        ControlTransitionRequest(action=BAKEOFF_TARGET_COMPARE, target_id=BAKEOFF_TARGET_COMPARE),
    )
    assert artifacts["bakeoff_action"] == "compare"


def test_binding_synthesize_artifacts_abort_returns_abandon() -> None:
    """synthesize_artifacts for abort returns bakeoff_action='abandon'."""
    binding = bakeoff_control_binding()
    view = bakeoff_run_state_view(_state())
    artifacts = binding.synthesize_artifacts(
        view,
        ControlTransitionRequest(action=CONTROL_TARGET_ABORT, target_id=CONTROL_TARGET_ABORT),
    )
    assert artifacts["bakeoff_action"] == "abandon"


def test_binding_synthesize_artifacts_select_without_chosen_profile() -> None:
    """synthesize_artifacts for select without chosen_profile omits profile key."""
    binding = bakeoff_control_binding()
    view = bakeoff_run_state_view(_state(phase="compared", terminal=True))
    artifacts = binding.synthesize_artifacts(
        view,
        ControlTransitionRequest(action=BAKEOFF_TARGET_SELECT, target_id=BAKEOFF_TARGET_SELECT),
    )
    assert artifacts["bakeoff_action"] == "pick"
    assert "profile" not in artifacts


def test_binding_apply_transition_via_control_transition() -> None:
    """ControlTransition (not ControlTransitionRequest) also works."""
    from megaplan.control_interface import ControlTransition

    view = bakeoff_run_state_view(_state(phase="picked", chosen_profile="alpha", terminal=True))
    transition = ControlTransition(op=BAKEOFF_TARGET_MERGE, target_id=BAKEOFF_TARGET_MERGE)
    result = apply_transition(view, transition, bakeoff_control_binding())
    assert result.accepted is True
    assert result.artifacts["bakeoff_action"] == "merge"


# ── no planning-specific state conversion ────────────────────────────


def test_no_planning_conversion_all_binding_methods(monkeypatch) -> None:
    """No method on BakeoffControlBinding triggers planning state conversion."""

    call_count = 0

    def _count_calls(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        raise AssertionError("planning_run_state_view must not be called for bakeoff")

    monkeypatch.setattr("megaplan.planning.planning_run_state_view", _count_calls)
    monkeypatch.setattr("megaplan.planning.planning_control_binding", _count_calls)

    binding = bakeoff_control_binding()
    view = bakeoff_run_state_view(_state(terminal=True))

    # valid_targets
    _ = tuple(binding.valid_targets(view))
    # recover_targets
    _ = tuple(binding.recover_targets(view))
    # apply_transition
    _ = binding.apply_transition(
        view,
        ControlTransitionRequest(action=BAKEOFF_TARGET_MERGE, target_id=BAKEOFF_TARGET_MERGE),
    )
    # synthesize_artifacts
    _ = binding.synthesize_artifacts(
        view,
        ControlTransitionRequest(action=BAKEOFF_TARGET_MERGE, target_id=BAKEOFF_TARGET_MERGE),
    )

    assert call_count == 0, f"planning was called {call_count} times"


def test_no_planning_conversion_even_with_planning_like_state(monkeypatch) -> None:
    """Raw state that looks like planning state is still treated as bakeoff state."""

    def _boom(*_args, **_kwargs):
        raise AssertionError("planning must not be invoked for bakeoff")

    monkeypatch.setattr("megaplan.planning.planning_run_state_view", _boom)
    monkeypatch.setattr("megaplan.planning.planning_control_binding", _boom)

    # State that resembles planning state but is passed through bakeoff binding
    planning_like_state = {
        "plan": "some-plan",
        "state": "executing",
        "meta": {"total_cost_usd": 1.5},
    }
    view = bakeoff_run_state_view(planning_like_state)
    assert view.outcome is None  # no bakeoff phase → no outcome
    assert view.cursor is None


def test_no_string_dispatch_bakeoff_raises_value_error() -> None:
    """Attempting binding='bakeoff' raises ValueError — no string dispatch."""
    import pytest as _pytest

    with _pytest.raises(ValueError, match="unknown control binding"):
        read_valid_targets(_state(), "bakeoff")  # type: ignore[arg-type]


def test_direct_injection_via_read_valid_targets() -> None:
    """read_valid_targets works with direct BakeoffControlBinding injection."""
    projection = read_valid_targets(
        bakeoff_run_state_view(_state(terminal=True)), bakeoff_control_binding()
    )
    assert len(projection) == 2  # compare + abort
    assert {t.id for t in projection} == {BAKEOFF_TARGET_COMPARE, CONTROL_TARGET_ABORT}


def test_direct_injection_via_apply_transition() -> None:
    """apply_transition works with direct BakeoffControlBinding injection."""
    result = apply_transition(
        bakeoff_run_state_view(_state(phase="compared", chosen_profile="alpha", terminal=True)),
        ControlTransitionRequest(action=BAKEOFF_TARGET_SELECT, target_id=BAKEOFF_TARGET_SELECT),
        bakeoff_control_binding(),
    )
    assert result.accepted is True
    assert result.artifacts["bakeoff_action"] == "pick"


def test_direct_injection_via_synthesize_artifacts() -> None:
    """synthesize_artifacts works with direct BakeoffControlBinding injection."""
    from megaplan.control_interface import synthesize_artifacts as synth

    artifacts = synth(
        bakeoff_run_state_view(_state(terminal=True)),
        ControlTransitionRequest(action=BAKEOFF_TARGET_COMPARE, target_id=BAKEOFF_TARGET_COMPARE),
        bakeoff_control_binding(),
    )
    assert artifacts["bakeoff_action"] == "compare"


# ── full integration: projection→transition round-trip ────────────────


def test_full_projection_transition_round_trip_per_phase() -> None:
    """For every actionable phase, read valid targets and apply each accepted transition."""
    scenarios = [
        (_state(), "resume"),
        (_state(terminal=True), "compare"),
        (_state(phase="compared", chosen_profile="alpha", terminal=True), "pick"),
        (_state(phase="picked", chosen_profile="alpha", terminal=True), "merge"),
    ]
    for raw_state, expected_action in scenarios:
        view = bakeoff_run_state_view(raw_state)
        projection = read_valid_targets(view, bakeoff_control_binding())
        # Apply the first non-abort target
        for target in projection:
            if target.id == CONTROL_TARGET_ABORT:
                continue
            result = apply_transition(
                view,
                ControlTransitionRequest(action=target.id, target_id=target.id),
                bakeoff_control_binding(),
            )
            assert result.accepted is True, (
                f"phase={raw_state.get('phase')} target={target.id}: {result.reason}"
            )
            assert result.artifacts["bakeoff_action"] == expected_action, (
                f"phase={raw_state.get('phase')} target={target.id}: got {result.artifacts.get('bakeoff_action')}"
            )
            break  # only test the first non-abort target
        else:
            # No non-abort targets — this is fine for terminal phases
            pass


def test_bakeoff_control_binding_is_reusable() -> None:
    """The same BakeoffControlBinding instance can be used across multiple run states."""
    binding = bakeoff_control_binding()

    running_view = bakeoff_run_state_view(_state())
    terminal_view = bakeoff_run_state_view(_state(terminal=True))
    merged_view = bakeoff_run_state_view(_state(phase="merged", terminal=True))

    # running
    assert {t.id for t in binding.valid_targets(running_view)} == {
        BAKEOFF_TARGET_RUN_PROFILES,
        CONTROL_TARGET_ABORT,
    }
    # terminal → compare
    assert {t.id for t in binding.valid_targets(terminal_view)} == {
        BAKEOFF_TARGET_COMPARE,
        CONTROL_TARGET_ABORT,
    }
    # merged → no targets
    assert tuple(binding.valid_targets(merged_view)) == ()

    # Reuse same instance again — should produce identical results
    assert {t.id for t in binding.valid_targets(running_view)} == {
        BAKEOFF_TARGET_RUN_PROFILES,
        CONTROL_TARGET_ABORT,
    }
