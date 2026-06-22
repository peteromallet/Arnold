"""Routing identity/cache helpers plus Megaplan planning routing helpers."""

from __future__ import annotations

from typing import Mapping

from arnold_pipelines.megaplan.routing.cache import cache_get, cache_set, identity_cache_key
from arnold_pipelines.megaplan.routing.identity import (
    MODEL_PARAM_KEYS,
    ModelIdentity,
    compute_identity,
    params_hash,
    prompt_hash,
)
from arnold.pipeline.types import Edge

PLAN_PROCEED: str = "proceed"
PLAN_ITERATE: str = "iterate"
PLAN_TIEBREAKER: str = "tiebreaker"
PLAN_ESCALATE: str = "escalate"

PLANNING_DECISIONS: tuple[str, str, str, str] = (
    PLAN_PROCEED,
    PLAN_ITERATE,
    PLAN_TIEBREAKER,
    PLAN_ESCALATE,
)

OVERRIDE_FORCE_PROCEED: str = "force_proceed"
OVERRIDE_FORCE_PROCEED_CLI: str = "force-proceed"

OVERRIDE_SPELLING: dict[str, str] = {
    OVERRIDE_FORCE_PROCEED: OVERRIDE_FORCE_PROCEED_CLI,
}

_OVERRIDE_SPELLING_REVERSE: dict[str, str] = {
    v: k for k, v in OVERRIDE_SPELLING.items()
}


def cli_to_internal_override(cli_label: str) -> str:
    return _OVERRIDE_SPELLING_REVERSE.get(cli_label, cli_label)


def internal_to_cli_override(internal_id: str) -> str:
    return OVERRIDE_SPELLING.get(internal_id, internal_id)


def planning_gate_edges(
    *,
    on_proceed: str,
    on_iterate: str,
    on_tiebreaker: str,
    on_escalate: str,
    gate_extra_edges: tuple[Edge, ...] = (),
) -> tuple[Edge, ...]:
    return _decision_edges(
        decisions={
            PLAN_PROCEED: on_proceed,
            PLAN_ITERATE: on_iterate,
            PLAN_TIEBREAKER: on_tiebreaker,
            PLAN_ESCALATE: on_escalate,
        },
        fallback_edges=gate_extra_edges,
    )


def tiebreaker_edges(
    *,
    on_iterate: str,
    on_proceed: str,
    on_escalate: str,
) -> tuple[Edge, ...]:
    return _decision_edges(
        decisions={
            PLAN_ITERATE: on_iterate,
            PLAN_PROCEED: on_proceed,
            PLAN_ESCALATE: on_escalate,
        },
    )


def planning_override_edges(overrides: Mapping[str, str]) -> tuple[Edge, ...]:
    return _decision_edges(decisions={}, overrides=overrides)


def _decision_edges(
    *,
    decisions: Mapping[str, str],
    overrides: Mapping[str, str] | None = None,
    fallback_edges: tuple[Edge, ...] = (),
) -> tuple[Edge, ...]:
    result = [
        Edge(label=key, target=target, kind="decision")
        for key, target in decisions.items()
    ]
    if overrides:
        result.extend(
            Edge(label=f"override {action}", target=target, kind="override")
            for action, target in overrides.items()
        )
    result.extend(fallback_edges)
    return tuple(result)


def critique_revise_gate_routing(
    *,
    on_proceed: str,
    on_iterate: str,
    on_tiebreaker: str,
    on_escalate: str,
    on_revise: str = "critique",
    gate_extra_edges: tuple[Edge, ...] = (),
) -> dict[str, tuple[Edge, ...]]:
    return {
        "critique": (Edge(label="gate", target="gate", kind="normal"),),
        "gate": planning_gate_edges(
            on_proceed=on_proceed,
            on_iterate=on_iterate,
            on_tiebreaker=on_tiebreaker,
            on_escalate=on_escalate,
            gate_extra_edges=gate_extra_edges,
        ),
        "revise": (Edge(label="critique", target=on_revise, kind="normal"),),
    }

__all__ = [
    "MODEL_PARAM_KEYS",
    "ModelIdentity",
    "OVERRIDE_FORCE_PROCEED",
    "OVERRIDE_FORCE_PROCEED_CLI",
    "OVERRIDE_SPELLING",
    "PLANNING_DECISIONS",
    "PLAN_ESCALATE",
    "PLAN_ITERATE",
    "PLAN_PROCEED",
    "PLAN_TIEBREAKER",
    "cache_get",
    "cache_set",
    "cli_to_internal_override",
    "compute_identity",
    "critique_revise_gate_routing",
    "identity_cache_key",
    "internal_to_cli_override",
    "params_hash",
    "planning_gate_edges",
    "planning_override_edges",
    "prompt_hash",
    "tiebreaker_edges",
]
