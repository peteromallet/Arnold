"""Override-action authority matrix.

The matrix records each canonical override action and whether it is a
terminal route-affecting action or an additive/config effect, plus the
workflow/policy surface that owns its dispatch.
"""

from __future__ import annotations

from typing import Mapping, NamedTuple

_OVERRIDE_ACTION_KEYS: frozenset[str] = frozenset(
    {
        "abort",
        "add-note",
        "adopt-execution",
        "force-proceed",
        "recover-blocked",
        "replan",
        "resume-clarify",
        "set-model",
        "set-profile",
        "set-robustness",
        "set-vendor",
    }
)


class OverrideActionClassificationError(ValueError):
    """Raised when an override action lacks a declared route/effect surface."""

    def __init__(self, action: str) -> None:
        super().__init__(
            f"Override action '{action}' lacks a declared route or effect; "
            "it must declare matrix authority before the handler can dispatch it."
        )


class OverrideActionEntry(NamedTuple):
    """A single row in the override action authority matrix."""

    action: str
    family: str
    description: str
    route_signal: str | None
    target_ref: str | None
    effect_id: str | None
    dispatch_surface: str
    control_routed: bool


_DECLARED_OVERRIDE_AUTHORITY: Mapping[str, Mapping[str, object]] = {
    "abort": {
        "family": "terminal_route",
        "description": "Terminate the plan immediately via the halt node.",
        "route_signal": "abort",
        "target_ref": "halt",
        "dispatch_surface": "workflow.route_binding",
        "control_routed": True,
    },
    "add-note": {
        "family": "additive_config",
        "description": "Attach a free-text note to the plan state.",
        "route_signal": "add_note",
        "effect_id": "override.add_note",
        "dispatch_surface": "policy.effect",
        "control_routed": True,
    },
    "adopt-execution": {
        "family": "terminal_route",
        "description": "Adopt an already-complete execution artifact and resume at review.",
        "route_signal": "adopt_execution",
        "target_ref": "review",
        "dispatch_surface": "workflow.state_resume",
        "control_routed": False,
    },
    "force-proceed": {
        "family": "terminal_route",
        "description": "Skip gate or review blockers and proceed directly to finalize or done.",
        "route_signal": "force_proceed",
        "target_ref": "finalize",
        "dispatch_surface": "workflow.route_binding",
        "control_routed": True,
    },
    "recover-blocked": {
        "family": "terminal_route",
        "description": "Recover from a blocked state by restoring the declared recovery predecessor.",
        "route_signal": "recover_blocked",
        "dispatch_surface": "policy.recovery_resume",
        "control_routed": True,
    },
    "replan": {
        "family": "terminal_route",
        "description": "Re-enter the planning loop via revise.",
        "route_signal": "replan",
        "target_ref": "revise",
        "dispatch_surface": "workflow.route_binding",
        "control_routed": True,
    },
    "resume-clarify": {
        "family": "terminal_route",
        "description": "Resume from a prep clarification halt and continue at the plan step.",
        "route_signal": "resume_clarify",
        "target_ref": "plan",
        "dispatch_surface": "workflow.state_resume",
        "control_routed": True,
    },
    "set-model": {
        "family": "additive_config",
        "description": "Override the model used by one or more phases.",
        "route_signal": "set_model",
        "effect_id": "override.set_model",
        "dispatch_surface": "policy.effect",
        "control_routed": True,
    },
    "set-profile": {
        "family": "additive_config",
        "description": "Switch the active Megaplan profile.",
        "route_signal": "set_profile",
        "effect_id": "override.set_profile",
        "dispatch_surface": "policy.effect",
        "control_routed": True,
    },
    "set-robustness": {
        "family": "additive_config",
        "description": "Change the robustness level for subsequent phases.",
        "route_signal": "set_robustness",
        "effect_id": "override.set_robustness",
        "dispatch_surface": "policy.effect",
        "control_routed": True,
    },
    "set-vendor": {
        "family": "additive_config",
        "description": "Override the vendor/provider used by one or more phases.",
        "route_signal": "set_vendor",
        "effect_id": "override.set_vendor",
        "dispatch_surface": "policy.effect",
        "control_routed": True,
    },
}


def _build_matrix() -> tuple[OverrideActionEntry, ...]:
    entries: list[OverrideActionEntry] = []
    for action in sorted(_OVERRIDE_ACTION_KEYS):
        declared = _DECLARED_OVERRIDE_AUTHORITY.get(action)
        if declared is None:
            raise OverrideActionClassificationError(action)
        entries.append(
            OverrideActionEntry(
                action=action,
                family=str(declared["family"]),
                description=str(declared["description"]),
                route_signal=(
                    str(declared["route_signal"])
                    if declared.get("route_signal") is not None
                    else None
                ),
                target_ref=(
                    str(declared["target_ref"])
                    if declared.get("target_ref") is not None
                    else None
                ),
                effect_id=(
                    str(declared["effect_id"])
                    if declared.get("effect_id") is not None
                    else None
                ),
                dispatch_surface=str(declared["dispatch_surface"]),
                control_routed=bool(declared["control_routed"]),
            )
        )
    return tuple(entries)


OVERRIDE_ACTION_MATRIX: tuple[OverrideActionEntry, ...] = _build_matrix()
_ENTRIES_BY_ACTION: Mapping[str, OverrideActionEntry] = {
    entry.action: entry for entry in OVERRIDE_ACTION_MATRIX
}

TERMINAL_ROUTE_ACTIONS: tuple[str, ...] = tuple(
    entry.action for entry in OVERRIDE_ACTION_MATRIX if entry.family == "terminal_route"
)
ADDITIVE_CONFIG_ACTIONS: tuple[str, ...] = tuple(
    entry.action for entry in OVERRIDE_ACTION_MATRIX if entry.family == "additive_config"
)
CONTROL_ROUTED_ACTIONS: frozenset[str] = frozenset(
    entry.action for entry in OVERRIDE_ACTION_MATRIX if entry.control_routed
)
ROUTE_SIGNAL_BY_ACTION: Mapping[str, str] = {
    entry.action: entry.route_signal
    for entry in OVERRIDE_ACTION_MATRIX
    if entry.route_signal is not None
}


def get_entry(action: str) -> OverrideActionEntry:
    return _ENTRIES_BY_ACTION[action]


__all__ = [
    "ADDITIVE_CONFIG_ACTIONS",
    "CONTROL_ROUTED_ACTIONS",
    "OverrideActionClassificationError",
    "OverrideActionEntry",
    "OVERRIDE_ACTION_MATRIX",
    "ROUTE_SIGNAL_BY_ACTION",
    "TERMINAL_ROUTE_ACTIONS",
    "get_entry",
]
