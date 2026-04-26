from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from vibecomfy.workflow import VibeWorkflow


@dataclass(frozen=True, slots=True)
class Patch:
    """A targeted, idempotent transformation over a :class:`VibeWorkflow`.

    Patches are free to use *any* :class:`VibeWorkflow` method when mutating a
    workflow. In particular, they may add nodes, change widget/input values,
    splice nodes into existing chains via ``disconnect`` / ``replace_edge``, or
    even manipulate :attr:`VibeWorkflow.edges` directly when the higher-level
    primitives are insufficient. The only contract is that ``apply`` returns
    the (mutated) workflow and that ``applies_to`` is a safe predicate to
    consult on any workflow.
    """

    name: str
    applies_to: Callable[[VibeWorkflow], bool]
    apply: Callable[[VibeWorkflow], VibeWorkflow]
    rationale: Callable[[VibeWorkflow], str]
