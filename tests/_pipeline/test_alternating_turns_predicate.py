"""T9c — alternating_turns stores until_condition on terminal Stage."""
from __future__ import annotations

from megaplan._pipeline.pattern_topology import alternating_turns
from megaplan._pipeline.types import StepContext, StepResult


class _RoleStep:
    kind = "produce"
    prompt_key = None
    slot = None
    produces = ()
    consumes = ()

    def __init__(self, n):
        self.name = n

    def run(self, ctx: StepContext) -> StepResult:  # pragma: no cover
        return StepResult(next="halt")


def test_until_condition_set_on_terminal_stage():
    cond = lambda s: True  # noqa: E731
    roles = (
        ("alice", _RoleStep("alice")),
        ("bob", _RoleStep("bob")),
    )
    stages = alternating_turns(roles, until_condition=cond)
    assert stages["alice"].loop_condition is None
    assert stages["bob"].loop_condition is cond


def test_until_condition_default_none():
    roles = (("a", _RoleStep("a")),)
    stages = alternating_turns(roles)
    assert stages["a"].loop_condition is None
