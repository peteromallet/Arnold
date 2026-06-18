"""Megaplan-specific native runtime hooks.

This module implements the :class:`~arnold.pipeline.native.hooks.NativeRuntimeHooks`
protocol with Megaplan semantics for state merge, overrides, step-IO policy,
envelope joining, subloop promotion/suspension-lift, and loop guards.

Milestone: m3-megaplan-runtime-hooks
"""

from __future__ import annotations

from typing import Any

from arnold.pipeline.native.hooks import (
    NativeRuntimeHooks,
    NullNativeRuntimeHooks,
)
from arnold.pipeline.native.ir import NativeInstruction


class MegaplanNativeHooks(NullNativeRuntimeHooks):
    """Megaplan-specific native runtime hooks.

    Extends :class:`NullNativeRuntimeHooks` with Megaplan semantics for
    state merge (typed-port CAS when active, legacy ``dict.update`` otherwise),
    overrides, step-IO policy, envelope joining, subloop promotion/suspension-lift,
    and loop guards.

    Each callback is implemented incrementally per the M3 milestone schedule.
    """

    def merge_state(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        outputs: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> tuple[dict[str, Any], frozenset[str]]:
        """Merge phase outputs into working state with Megaplan CAS semantics.

        Normalises native outputs into key/value patches, maintains executor-owned
        produced keys, and applies typed-port updates through
        :class:`~arnold.pipelines.megaplan._pipeline.types.StateDelta` /
        :func:`~arnold.pipelines.megaplan._pipeline.types.apply_delta` using
        current ``_state_meta`` CAS versions when ``MEGAPLAN_TYPED_PORTS=1``.

        When typed ports are inactive (the default), falls back to legacy
        ``dict.update`` — matching the ``executor-key-merge`` write path in
        :func:`~arnold.pipelines.megaplan._core.state.write_plan_state`.
        """
        if not outputs:
            return state, owned_keys

        try:
            from arnold.pipelines.megaplan._pipeline.flags import typed_ports_on
            from arnold.pipelines.megaplan._pipeline.types import (
                StateDelta,
                StateDeltaConflict,
                apply_delta,
            )
            _flag_on = typed_ports_on()
        except Exception:
            _flag_on = False

        # Build the new owned_keys set: executor now owns every key it has
        # produced in this phase, unioned with previously owned keys.
        new_owned_keys = frozenset(owned_keys | frozenset(outputs.keys()))

        if _flag_on:
            # ── Typed-port CAS path ──────────────────────────────────
            # Apply each output key through StateDelta/apply_delta using
            # the current _state_meta CAS version for that key.
            _state = dict(state)
            for key, value in outputs.items():
                _versions = (
                    _state.get("_state_meta", {}).get("versions", {})
                )
                _current_version = int(_versions.get(key, 0))
                try:
                    _state, _ = apply_delta(
                        _state,
                        StateDelta(
                            op="replace",
                            key=key,
                            value=value,
                            version=_current_version,
                        ),
                    )
                except StateDeltaConflict:
                    # If a conflict is detected (stale version), fall back
                    # to last-writer-wins for this key (matching the
                    # executor-key-merge behaviour on the persistence side).
                    _state[key] = value
            return _state, new_owned_keys
        else:
            # ── Legacy dict.update path ─────────────────────────────
            # When typed ports are inactive, merge all outputs into
            # state via plain dict.update.
            next_state = dict(state)
            next_state.update(outputs)
            return next_state, new_owned_keys


__all__ = [
    "MegaplanNativeHooks",
]
