"""Dispatch helpers: tier→spec resolution and tier→agent resolution.

Tier is treated as an **opaque ordinal** — this module deliberately avoids
any rubric-shaped tokens (no numeric-range, tier-digit, or model-family-name
literals).  Callers supply a ``tier_models`` mapping that is used as a
simple key→value lookup.
"""

from __future__ import annotations

import argparse
import copy
import logging
from typing import Any

from arnold_pipelines.megaplan.fallback_chains import select_fallback_spec

log = logging.getLogger(__name__)


def resolve_dispatch_spec(
    tier_models: dict[str, dict[int, str | list[str]]] | None,
    slot: str,
    tier_ordinal: int,
    default: str | None = None,
) -> str | None:
    """Resolve *tier_ordinal* → tier-spec string from *tier_models*.

    Args:
        tier_models: Top-level tier table (e.g. ``{"execute": {1: "model-name=think", …}}``).
        slot: Phase key in *tier_models* (e.g. ``"execute"``).
        tier_ordinal: Opaque ordinal to look up.
        default: Value returned when the ordinal is missing from the table.

    Returns:
        The tier-spec string for *tier_ordinal*, or *default*.
    """
    if not isinstance(tier_models, dict):
        return default
    slot_table = tier_models.get(slot)
    if not isinstance(slot_table, dict):
        return default
    selected = slot_table.get(tier_ordinal)
    if selected is None:
        return default
    if isinstance(selected, str):
        return selected
    return select_fallback_spec(selected, 0, path=f"tier_models.{slot}.{tier_ordinal}")


def resolve_dispatch_agent(
    args: argparse.Namespace,
    tier_spec: str | list[str],
) -> tuple[str, str, str | None]:
    """Resolve a tier-spec string to *(agent, mode, model)* without mutating *args*.

    Copies *args*, sets ``phase_model=["execute=<tier_spec>"]`` on the
    copy, and calls ``resolve_agent_mode``.  Does not prepend ahead of a
    user CLI override — the override guard in ``apply_profile_expansion``
    already strips ``tier_models.execute`` when ``--phase-model execute=…``
    is present, so this helper is only called when tier routing is active.
    """
    import arnold_pipelines.megaplan.workers as worker_module

    selected_spec = (
        tier_spec
        if isinstance(tier_spec, str)
        else select_fallback_spec(tier_spec, 0, path="tier_models.execute")
    )
    tier_args = copy.copy(args)
    tier_args.phase_model = [f"execute={selected_spec}"]
    resolved = worker_module.resolve_agent_mode("execute", tier_args)
    resolved_model = resolved.resolved_model if hasattr(resolved, "resolved_model") else None
    return resolved.agent, resolved.mode, resolved_model if resolved_model is not None else resolved.model
