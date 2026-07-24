"""User-level TOML config loader for megaplan.

Reads `~/.config/megaplan/config.toml` (XDG-aware via ``config_dir``).

Currently exposes only ``default_vendor()`` for the ``--vendor`` flag's
config default. Kept minimal on purpose: scope-creep here is how config
loaders end up trying to be the schema of record. New keys should
graduate from here to ``types.DEFAULTS`` (with explicit JSON-config
plumbing) once they have more than one consumer.

Separate from the existing ``config.json`` loader in ``io.py`` because:
  * The rubric proposal pins the file name to ``config.toml`` so users
    can hand-edit it without quoting JSON.
  * The JSON config is read+written by ``megaplan config set`` and
    persists ephemeral state alongside user prefs; the TOML config is
    a hand-edited, read-only-from-megaplan's-perspective file.

If we later want a single unified user-config surface, this module is
the place to fold ``config.json`` into. For now keep them separate.
"""
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from . import io

VALID_VENDORS = ("claude", "codex")


def config_dir(home: Path | None = None) -> Path:
    return io.config_dir(home)


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        # Fail open: a malformed user config shouldn't break every CLI
        # invocation. The `--vendor` CLI flag remains usable as an
        # explicit override.
        return {}


def load_user_config_toml(home: Path | None = None) -> dict[str, Any]:
    """Return the parsed contents of ``~/.config/megaplan/config.toml``.

    Returns ``{}`` if the file is missing or malformed. ``home`` is for
    test injection — production callers should rely on the default.
    """
    path = config_dir(home) / "config.toml"
    data = _load_toml(path)
    if not isinstance(data, dict):
        return {}
    return data


def default_vendor(home: Path | None = None) -> str:
    """Return the configured default vendor, falling back to ``"codex"``.

    Reads ``[defaults].vendor`` from the user's ``config.toml``. Invalid
    or missing values fall back to ``"codex"`` silently — ``codex`` is the
    universal default unless a config overrides it. The CLI flag is the
    authoritative override, and this is a "set and forget" convenience.
    """
    data = load_user_config_toml(home)
    defaults = data.get("defaults")
    if not isinstance(defaults, dict):
        return "codex"
    vendor = defaults.get("vendor")
    if isinstance(vendor, str) and vendor in VALID_VENDORS:
        return vendor
    return "codex"


def default_prep_clarify(home: Path | None = None) -> bool:
    """Return the configured default for prep_clarify, falling back to ``True``.

    Reads ``[defaults].prep_clarify`` from the user's ``config.toml``.
    Only boolean values are accepted; anything else falls back to ``True``.
    """
    data = load_user_config_toml(home)
    defaults = data.get("defaults")
    if not isinstance(defaults, dict):
        return True
    prep_clarify = defaults.get("prep_clarify")
    if isinstance(prep_clarify, bool):
        return prep_clarify
    return True


__all__ = ["VALID_VENDORS", "default_prep_clarify", "default_vendor", "load_user_config_toml"]
