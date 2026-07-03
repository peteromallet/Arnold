"""Megaplan native workflow interfaces with stable IDs and legacy aliases.

Defines the canonical interface contracts for every Megaplan workflow path.
Each interface carries a stable semantic identity, declared input/output
names, and subordinate legacy aliases that map old identifiers (step IDs,
handler refs, kind strings) to the authoritative stable ID.

Design principles
-----------------
* **Stable IDs are authoritative.**  They are versioned, deterministic, and
  never repurposed.  Aliases are compatibility metadata only.
* **Aliases are subordinate.**  Every alias resolves to exactly one stable ID.
  The reverse mapping is *not* guaranteed to be unique (one stable ID may
  have many legacy aliases).
* **Declared inputs/outputs.**  Each interface explicitly names the data it
  consumes and produces, providing a contract for later native workflow
  decomposition.

These interfaces are *metadata only* — they carry no runtime logic.  Later
workflow source (T12+) will reference stable IDs to wire native phases and
decisions.  The existing handler dispatch in ``handlers/`` and the step
components in ``workflows/components.py`` remain the canonical
implementation; these interfaces describe the contract those implementations
fulfill.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import FrozenSet, Mapping


# ── Interface definition type ────────────────────────────────────────────


@dataclass(frozen=True)
class NativeInterface:
    """A canonical native workflow interface for a Megaplan path.

    Do not instantiate directly — use the module-level constants below.
    """

    stable_id: str
    """Stable semantic identity (e.g. ``'megaplan.native.prep.v1'``).
    Immutable; never repurposed across versions."""

    path_group: str
    """Logical grouping label (e.g. ``'prep'``, ``'planning'``, ``'gate/tiebreaker'``)."""

    description: str
    """Human-readable description of what this interface represents."""

    inputs: Mapping[str, str] = field(default_factory=dict)
    """Declared input names mapped to type hints (Python type names as strings)."""

    outputs: Mapping[str, str] = field(default_factory=dict)
    """Declared output names mapped to type hints."""

    legacy_aliases: FrozenSet[str] = field(default_factory=frozenset)
    """Legacy identifiers that resolve to this stable ID.
    Includes step IDs (``megaplan:prep``), handler refs
    (``arnold_pipelines.megaplan.handlers:handle_prep``), and
    kind strings (``megaplan:prep``).  Subordinate to ``stable_id``."""

    handler_ref: str = ""
    """Canonical handler reference (e.g. ``'arnold_pipelines.megaplan.handlers:handle_prep'``).
    Empty for terminal/structural paths like ``halt``."""

    step_id: str = ""
    """Canonical step ID suffix (e.g. ``'prep'``), without the ``megaplan:`` prefix.
    May differ from the ``path_group`` for composite groups."""

    terminal: bool = False
    """``True`` if this path is terminal (ends the workflow)."""


# ── Interface definitions ────────────────────────────────────────────────


# ── Prep ─────────────────────────────────────────────────────────────────

PREP = NativeInterface(
    stable_id="megaplan.native.prep.v1",
    path_group="prep",
    description="Surface ambiguities and generate a structured briefing for planning.",
    inputs={},
    outputs={"prep_payload": "dict[str, Any]"},
    legacy_aliases=frozenset({
        "megaplan:prep",
        "handle_prep",
        "arnold_pipelines.megaplan.handlers:handle_prep",
        "PREP",
    }),
    handler_ref="arnold_pipelines.megaplan.handlers:handle_prep",
    step_id="prep",
    terminal=False,
)

# ── Planning ─────────────────────────────────────────────────────────────

PLAN = NativeInterface(
    stable_id="megaplan.native.plan.v1",
    path_group="planning",
    description="Generate a structured execution plan from the prep briefing.",
    inputs={"prep_payload": "dict[str, Any]"},
    outputs={"plan_payload": "dict[str, Any]"},
    legacy_aliases=frozenset({
        "megaplan:plan",
        "handle_plan",
        "arnold_pipelines.megaplan.handlers:handle_plan",
        "PLAN",
    }),
    handler_ref="arnold_pipelines.megaplan.handlers:handle_plan",
    step_id="plan",
    terminal=False,
)

# ── Critique / Revise ────────────────────────────────────────────────────

CRITIQUE = NativeInterface(
    stable_id="megaplan.native.critique.v1",
    path_group="critique/revise",
    description="Evaluate the plan against quality criteria and produce a critique payload.",
    inputs={"plan_payload": "dict[str, Any]"},
    outputs={"critique_payload": "dict[str, Any]"},
    legacy_aliases=frozenset({
        "megaplan:critique",
        "handle_critique",
        "arnold_pipelines.megaplan.handlers:handle_critique",
        "CRITIQUE",
    }),
    handler_ref="arnold_pipelines.megaplan.handlers:handle_critique",
    step_id="critique",
    terminal=False,
)

REVISE = NativeInterface(
    stable_id="megaplan.native.revise.v1",
    path_group="critique/revise",
    description="Revise the plan in response to gate feedback, looping until the critique gate passes.",
    inputs={"gate_payload": "dict[str, Any]"},
    outputs={"revise_payload": "dict[str, Any]"},
    legacy_aliases=frozenset({
        "megaplan:revise",
        "handle_revise",
        "arnold_pipelines.megaplan.handlers:handle_revise",
        "REVISE",
    }),
    handler_ref="arnold_pipelines.megaplan.handlers:handle_revise",
    step_id="revise",
    terminal=False,
)

# ── Gate / Tiebreaker ────────────────────────────────────────────────────

GATE = NativeInterface(
    stable_id="megaplan.native.gate.v1",
    path_group="gate/tiebreaker",
    description="Human-in-the-loop gate: review the critique, produce a recommendation "
    "(proceed/iterate/tiebreaker/escalate/abort/suspend), and route accordingly.",
    inputs={"critique_payload": "dict[str, Any]"},
    outputs={"gate_payload": "dict[str, Any]", "recommendation": "str"},
    legacy_aliases=frozenset({
        "megaplan:gate",
        "handle_gate",
        "arnold_pipelines.megaplan.handlers:handle_gate",
        "GATE",
    }),
    handler_ref="arnold_pipelines.megaplan.handlers:handle_gate",
    step_id="gate",
    terminal=False,
)

TIEBREAKER_RUN = NativeInterface(
    stable_id="megaplan.native.tiebreaker-run.v1",
    path_group="gate/tiebreaker",
    description="Run the tiebreaker research phase when the gate cannot resolve a deadlock.",
    inputs={"gate_payload": "dict[str, Any]"},
    outputs={"tiebreaker_payload": "dict[str, Any]"},
    legacy_aliases=frozenset({
        "megaplan:tiebreaker_run",
        "handle_tiebreaker_run",
        "arnold_pipelines.megaplan.handlers:handle_tiebreaker_run",
        "TIEBREAKER_RUN",
    }),
    handler_ref="arnold_pipelines.megaplan.handlers:handle_tiebreaker_run",
    step_id="tiebreaker_run",
    terminal=False,
)

TIEBREAKER_DECIDE = NativeInterface(
    stable_id="megaplan.native.tiebreaker-decide.v1",
    path_group="gate/tiebreaker",
    description="Decide the tiebreaker outcome (iterate/proceed/escalate) from the research payload.",
    inputs={"tiebreaker_payload": "dict[str, Any]"},
    outputs={"decision": "str"},
    legacy_aliases=frozenset({
        "megaplan:tiebreaker_decide",
        "handle_tiebreaker_decide",
        "arnold_pipelines.megaplan.handlers:handle_tiebreaker_decide",
        "TIEBREAKER_DECIDE",
    }),
    handler_ref="arnold_pipelines.megaplan.handlers:handle_tiebreaker_decide",
    step_id="tiebreaker_decide",
    terminal=False,
)

# ── Finalize / Execute / Review ──────────────────────────────────────────

FINALIZE = NativeInterface(
    stable_id="megaplan.native.finalize.v1",
    path_group="finalize/execute/review",
    description="Finalize the approved plan: validate, capture baselines, produce execution artifacts.",
    inputs={"gate_payload": "dict[str, Any]"},
    outputs={"finalize_payload": "dict[str, Any]"},
    legacy_aliases=frozenset({
        "megaplan:finalize",
        "handle_finalize",
        "arnold_pipelines.megaplan.handlers:handle_finalize",
        "FINALIZE",
    }),
    handler_ref="arnold_pipelines.megaplan.handlers:handle_finalize",
    step_id="finalize",
    terminal=False,
)

EXECUTE = NativeInterface(
    stable_id="megaplan.native.execute.v1",
    path_group="finalize/execute/review",
    description="Execute the finalized plan: dispatch tasks to agents, collect results.",
    inputs={"finalize_payload": "dict[str, Any]"},
    outputs={"execute_payload": "dict[str, Any]"},
    legacy_aliases=frozenset({
        "megaplan:execute",
        "handle_execute",
        "arnold_pipelines.megaplan.handlers:handle_execute",
        "EXECUTE",
    }),
    handler_ref="arnold_pipelines.megaplan.handlers:handle_execute",
    step_id="execute",
    terminal=False,
)

REVIEW = NativeInterface(
    stable_id="megaplan.native.review.v1",
    path_group="finalize/execute/review",
    description="Human-in-the-loop review of execution results: pass or rework.",
    inputs={"execute_payload": "dict[str, Any]"},
    outputs={"review_payload": "dict[str, Any]"},
    legacy_aliases=frozenset({
        "megaplan:review",
        "handle_review",
        "arnold_pipelines.megaplan.handlers:handle_review",
        "REVIEW",
    }),
    handler_ref="arnold_pipelines.megaplan.handlers:handle_review",
    step_id="review",
    terminal=False,
)

# ── Override ─────────────────────────────────────────────────────────────

OVERRIDE = NativeInterface(
    stable_id="megaplan.native.override.v1",
    path_group="override",
    description="Human override path: abort, force-proceed past the gate, or replan.",
    inputs={"gate_payload": "dict[str, Any]"},
    outputs={"override_result": "dict[str, Any]"},
    legacy_aliases=frozenset({
        "megaplan:override",
        "handle_override",
        "arnold_pipelines.megaplan.handlers:handle_override",
        "OVERRIDE",
    }),
    handler_ref="arnold_pipelines.megaplan.handlers:handle_override",
    step_id="override",
    terminal=False,
)

# ── Halt ─────────────────────────────────────────────────────────────────

HALT = NativeInterface(
    stable_id="megaplan.native.halt.v1",
    path_group="halt",
    description="Terminal halt: workflow ends (completed, aborted, or suspended).",
    inputs={},
    outputs={"status": "str"},
    legacy_aliases=frozenset({
        "megaplan:halt",
        "HALT",
    }),
    handler_ref="",
    step_id="halt",
    terminal=True,
)


# ── Aggregate collections ────────────────────────────────────────────────

ALL_INTERFACES: tuple[NativeInterface, ...] = (
    PREP,
    PLAN,
    CRITIQUE,
    REVISE,
    GATE,
    TIEBREAKER_RUN,
    TIEBREAKER_DECIDE,
    FINALIZE,
    EXECUTE,
    REVIEW,
    OVERRIDE,
    HALT,
)
"""Every defined Megaplan native interface, in logical workflow order."""

INTERFACES_BY_STABLE_ID: Mapping[str, NativeInterface] = MappingProxyType({
    iface.stable_id: iface for iface in ALL_INTERFACES
})
"""Lookup from stable ID to the corresponding :class:`NativeInterface`."""

INTERFACES_BY_PATH_GROUP: Mapping[str, tuple[NativeInterface, ...]] = MappingProxyType({
    "prep": (PREP,),
    "planning": (PLAN,),
    "critique/revise": (CRITIQUE, REVISE),
    "gate/tiebreaker": (GATE, TIEBREAKER_RUN, TIEBREAKER_DECIDE),
    "finalize/execute/review": (FINALIZE, EXECUTE, REVIEW),
    "override": (OVERRIDE,),
    "halt": (HALT,),
})
"""Lookup from path group label to the interfaces in that group."""


# ── Alias resolution ─────────────────────────────────────────────────────

def _build_alias_map() -> Mapping[str, str]:
    """Build a read-only alias→stable_id resolution map.

    Every legacy alias in every interface resolves to exactly one stable ID.
    If two interfaces declare the same alias (contract violation), the last
    definition wins — but the module-level constants guarantee uniqueness
    by construction.
    """
    mapping: dict[str, str] = {}
    for iface in ALL_INTERFACES:
        for alias in iface.legacy_aliases:
            mapping[alias] = iface.stable_id
    return MappingProxyType(mapping)


ALIAS_TO_STABLE_ID: Mapping[str, str] = _build_alias_map()
"""Read-only mapping from any legacy alias (step ID, handler ref, export name)
to the authoritative stable ID.  Aliases are subordinate to stable IDs:
they exist for backward compatibility only and must never be used as
primary identifiers in new code.

Example::

    >>> ALIAS_TO_STABLE_ID["megaplan:prep"]
    'megaplan.native.prep.v1'
    >>> ALIAS_TO_STABLE_ID["handle_prep"]
    'megaplan.native.prep.v1'
"""


def resolve_stable_id(identifier: str) -> str | None:
    """Resolve any identifier (alias or stable ID) to the canonical stable ID.

    If *identifier* is already a known stable ID it is returned unchanged.
    If it is a legacy alias the corresponding stable ID is returned.
    Returns ``None`` if the identifier is unknown.
    """
    # Fast path: already a known stable ID.
    if identifier in INTERFACES_BY_STABLE_ID:
        return identifier
    return ALIAS_TO_STABLE_ID.get(identifier)


def resolve_interface(identifier: str) -> NativeInterface | None:
    """Resolve any identifier to its :class:`NativeInterface`.

    Accepts stable IDs and legacy aliases.  Returns ``None`` when
    *identifier* is unknown.
    """
    stable_id = resolve_stable_id(identifier)
    if stable_id is None:
        return None
    return INTERFACES_BY_STABLE_ID[stable_id]


# ── Public surface ───────────────────────────────────────────────────────

__all__ = [
    "ALIAS_TO_STABLE_ID",
    "ALL_INTERFACES",
    "CRITIQUE",
    "EXECUTE",
    "FINALIZE",
    "GATE",
    "HALT",
    "INTERFACES_BY_PATH_GROUP",
    "INTERFACES_BY_STABLE_ID",
    "NativeInterface",
    "OVERRIDE",
    "PLAN",
    "PREP",
    "REVIEW",
    "REVISE",
    "TIEBREAKER_DECIDE",
    "TIEBREAKER_RUN",
    "resolve_interface",
    "resolve_stable_id",
]
