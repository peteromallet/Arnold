"""Neutral control import-surface checks."""

from __future__ import annotations

from dataclasses import is_dataclass
from typing import Protocol

import pytest

from arnold.runtime.outcome import RunOutcome


NEUTRAL_PUBLIC_NAMES = [
    "ControlBinding",
    "CONTROL_TARGET_ABORT",
    "CONTROL_TARGET_FORCE_ADVANCE",
    "CONTROL_TARGET_RECOVER_FROM_STUCK",
    "CONTROL_TARGET_REROUTE",
    "ArtifactRequest",
    "ControlProjection",
    "ControlInterfaceTarget",
    "ControlTarget",
    "ControlTargetRef",
    "ControlTransition",
    "ControlTransitionRequest",
    "ControlTransitionResult",
    "RunOutcome",
    "RunStateView",
]

INTERFACE_PUBLIC_NAMES = [
    "ControlBinding",
    "CONTROL_TARGET_ABORT",
    "CONTROL_TARGET_FORCE_ADVANCE",
    "CONTROL_TARGET_RECOVER_FROM_STUCK",
    "CONTROL_TARGET_REROUTE",
    "ArtifactRequest",
    "ControlProjection",
    "ControlInterfaceTarget",
    "ControlTarget",
    "ControlTargetRef",
    "ControlTransition",
    "ControlTransitionConflict",
    "ControlTransitionRequest",
    "ControlTransitionResult",
    "RunOutcome",
    "RunStateView",
]


def test_control_package_re_exports_exact_neutral_public_names() -> None:
    import arnold.control as control

    assert control.__all__ == NEUTRAL_PUBLIC_NAMES


def test_control_interface_exports_expected_neutral_names_plus_conflict() -> None:
    import arnold.control.interface as interface

    assert interface.__all__ == INTERFACE_PUBLIC_NAMES


def test_control_package_excludes_control_transition_conflict() -> None:
    import arnold.control as control

    assert "ControlTransitionConflict" not in control.__all__
    assert not hasattr(control, "ControlTransitionConflict")


@pytest.mark.parametrize("module_name", ["arnold.control", "arnold.control.interface"])
@pytest.mark.parametrize("symbol", NEUTRAL_PUBLIC_NAMES)
def test_required_neutral_symbols_are_available(module_name: str, symbol: str) -> None:
    module = __import__(module_name, fromlist=[symbol])

    assert getattr(module, symbol) is not None


def test_control_transition_conflict_is_available_from_interface_only() -> None:
    from arnold.control.interface import ControlTransitionConflict

    assert is_dataclass(ControlTransitionConflict)


def test_control_target_aliases_re_export_the_same_type() -> None:
    from arnold.control import ControlInterfaceTarget, ControlTarget, ControlTargetRef

    assert ControlInterfaceTarget is ControlTarget
    assert ControlTargetRef is ControlTarget


def test_control_binding_is_protocol_on_both_surfaces() -> None:
    from arnold.control import ControlBinding as package_binding
    from arnold.control.interface import ControlBinding as interface_binding

    assert package_binding is interface_binding
    assert getattr(package_binding, "_is_protocol", False) is True
    assert issubclass(package_binding, Protocol)


def test_neutral_control_constants_are_stable() -> None:
    from arnold.control import (
        CONTROL_TARGET_ABORT,
        CONTROL_TARGET_FORCE_ADVANCE,
        CONTROL_TARGET_RECOVER_FROM_STUCK,
        CONTROL_TARGET_REROUTE,
    )

    assert CONTROL_TARGET_FORCE_ADVANCE == "force-advance"
    assert CONTROL_TARGET_REROUTE == "re-route"
    assert CONTROL_TARGET_RECOVER_FROM_STUCK == "recover-from-stuck"
    assert CONTROL_TARGET_ABORT == "abort"


def test_neutral_carrier_shapes_are_available_from_package_surface() -> None:
    from arnold.control import (
        ArtifactRequest,
        ControlProjection,
        ControlTarget,
        ControlTransition,
        ControlTransitionRequest,
        ControlTransitionResult,
        RunStateView,
    )

    target = ControlTarget(id="step-1")
    transition = ControlTransition(op="recover", target_id="step-0")
    request = ControlTransitionRequest(action="recover", target_id="step-0")
    projection = ControlProjection(valid_targets=(target,))
    artifact = ArtifactRequest(artifact_type="report", transition=transition)
    result = ControlTransitionResult(accepted=True)
    state_view = RunStateView(run_id="run-1", outcome=RunOutcome.BLOCKED)

    assert is_dataclass(ControlTarget)
    assert target.kind == "workflow_step"
    assert request.op == "recover"
    assert projection.targets == (target,)
    assert artifact.transition is transition
    assert result.events == ()
    assert state_view.outcome is RunOutcome.BLOCKED
