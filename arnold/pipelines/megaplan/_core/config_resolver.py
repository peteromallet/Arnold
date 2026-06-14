"""N-layer ConfigResolver — M4 T13 (Step 9).

Strangler scaffold that generalises the existing 2-layer
``get_effective`` / ``setting_is_explicit`` (megaplan/_core/io.py:842, :855)
into a layered, environment-aware resolver.

Layer precedence (highest to lowest)::

    env > args > state.config(override) > profile > robustness > DEFAULTS

The resolver is **read-only**: writers must go through
:func:`set_state_override` (the single writer helper) which mutates the
``state['config']['override']`` plain-dict slot.  Reading the override
through the resolver never mutates state.

This module is **flag-gated**.  ``megaplan/_core/io.py``'s
:func:`get_effective` / :func:`setting_is_explicit` delegate here only
when ``UNIFIED_CONFIG=1`` (via :func:`megaplan._pipeline.flags.unified_config_on`).
Flag-OFF retains the existing 2-layer behaviour byte-identically for the
30+ existing callers.

Layers
------
* ``env``        — process environment, ``MEGAPLAN_<SECTION>_<KEY>`` (upper-snake)
* ``args``       — bound argparse Namespace (the "args bus" from handlers/execute.py)
* ``override``   — ``state['config']['override']`` plain dict, ``{section: {key: value}}``
* ``profile``    — ``state['config']['profile_settings']`` plain dict, same shape
* ``robustness`` — ``state['config']['robustness_settings']`` plain dict, same shape
* ``DEFAULTS``   — ``megaplan.types.DEFAULTS`` (``"section.key"`` string keys)

ResidentConfig.from_env (megaplan/resident/config.py:65) can pre-seed an
``env`` mapping via :meth:`ConfigResolver.with_resident_env` for callers
that don't want to peek at ``os.environ`` directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

Layer = Literal["env", "args", "override", "profile", "robustness", "defaults"]

# Ordered tuple — first match wins; the order pins the contract.
_LAYER_ORDER: tuple[Layer, ...] = (
    "env",
    "args",
    "override",
    "profile",
    "robustness",
    "defaults",
)

# Sentinel for "no value at this layer" — None is a legitimate value.
_MISSING: Any = object()


def _env_var_name(section: str, key: str) -> str:
    return f"MEGAPLAN_{section.upper()}_{key.upper()}"


def state_override_slot(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return (and lazily create) ``state['config']['override']``.

    The slot is a plain ``dict[section, dict[key, value]]``.  This is the
    single writer-friendly helper; the resolver itself never mutates it.
    """
    config = state.setdefault("config", {})
    override = config.get("override")
    if not isinstance(override, dict):
        override = {}
        config["override"] = override
    return override


def set_state_override(state: dict[str, Any], section: str, key: str, value: Any) -> None:
    """Writer-side helper for ``state.config.override``.

    Resolver consumers must treat the slot as read-only; mutation goes
    through this function so the contract surface stays one-way.
    """
    slot = state_override_slot(state)
    sect = slot.get(section)
    if not isinstance(sect, dict):
        sect = {}
        slot[section] = sect
    sect[key] = value


@dataclass
class ConfigResolver:
    """Layered configuration resolver.

    Construct one per resolution scope.  All bindings are optional —
    missing layers are silently skipped (they yield ``_MISSING``).
    """

    state: Optional[dict[str, Any]] = None
    args: Any = None  # argparse.Namespace or any attribute-bearing object
    env: Optional[dict[str, str]] = None
    _defaults: Optional[dict[str, Any]] = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # Layer readers — each returns _MISSING when the layer has no entry.
    # ------------------------------------------------------------------

    def _read_env(self, section: str, key: str) -> Any:
        env = self.env if self.env is not None else os.environ
        var = _env_var_name(section, key)
        if var in env:
            return env[var]
        return _MISSING

    def _read_args(self, section: str, key: str) -> Any:
        if self.args is None:
            return _MISSING
        # argparse namespaces flatten by key (no section); the args bus in
        # handlers/execute.py is keyed by the leaf option name. Section is
        # ignored except as a fallback for explicit "<section>_<key>".
        flat = key
        prefixed = f"{section}_{key}"
        for attr in (flat, prefixed):
            if hasattr(self.args, attr):
                val = getattr(self.args, attr)
                if val is not None:
                    return val
        return _MISSING

    def _read_state_dict(
        self, slot_name: str, section: str, key: str
    ) -> Any:
        if self.state is None:
            return _MISSING
        config = self.state.get("config")
        if not isinstance(config, dict):
            return _MISSING
        slot = config.get(slot_name)
        if not isinstance(slot, dict):
            return _MISSING
        sect = slot.get(section)
        if not isinstance(sect, dict):
            return _MISSING
        if key not in sect:
            return _MISSING
        return sect[key]

    def _read_override(self, section: str, key: str) -> Any:
        return self._read_state_dict("override", section, key)

    def _read_profile(self, section: str, key: str) -> Any:
        return self._read_state_dict("profile_settings", section, key)

    def _read_robustness(self, section: str, key: str) -> Any:
        return self._read_state_dict("robustness_settings", section, key)

    def _read_defaults(self, section: str, key: str) -> Any:
        defaults = self._defaults
        if defaults is None:
            from arnold.pipelines.megaplan.types import DEFAULTS  # local import: avoid cycle

            defaults = DEFAULTS
        full = f"{section}.{key}"
        if full not in defaults:
            raise KeyError(full)
        return defaults[full]

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------

    def _lookup(self, section: str, key: str) -> tuple[Layer, Any]:
        for layer in _LAYER_ORDER:
            reader = getattr(self, f"_read_{layer if layer != 'defaults' else 'defaults'}")
            value = reader(section, key)
            if value is not _MISSING:
                return layer, value
        # _read_defaults raises KeyError if section.key is not registered;
        # reaching here means defaults silently returned _MISSING, which
        # the implementation above never does — so this is unreachable.
        raise KeyError(f"{section}.{key}")  # pragma: no cover - defensive

    def effective(self, section: str, key: str) -> Any:
        """Return the effective value at the highest-precedence layer present."""
        _layer, value = self._lookup(section, key)
        return value

    def explicit_at(self, section: str, key: str) -> Layer | None:
        """Return the layer that supplied the effective value, or None for defaults.

        ``None`` indicates the fallback to ``DEFAULTS`` was used — i.e. the
        setting is *not* explicitly set anywhere upstream of defaults.
        """
        layer, _ = self._lookup(section, key)
        return None if layer == "defaults" else layer

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def with_resident_env(
        cls, *, resident_env: dict[str, str], state: dict[str, Any] | None = None, args: Any = None
    ) -> "ConfigResolver":
        """Build a resolver pre-seeded with a ResidentConfig.from_env env map."""
        return cls(state=state, args=args, env=dict(resident_env))


__all__ = [
    "ConfigResolver",
    "Layer",
    "set_state_override",
    "state_override_slot",
]
