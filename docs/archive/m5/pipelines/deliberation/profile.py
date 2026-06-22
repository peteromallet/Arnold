"""Deliberation-specific profile validators.

The abstraction-level validator accepts either a plain string
(``'high'`` / ``'mid'`` / ``'low'``) or a dict with an
``abstraction_level`` key.  It is registered as a
``stage_value_validator`` so that profile TOML documents can
express panel composition as structured dicts rather than
flat agent-spec strings.
"""

from __future__ import annotations

from typing import Any

_VALID_ABSTRACTION_LEVELS = frozenset({"high", "mid", "low"})


def abstraction_level_validator(value: Any) -> str:
    """Validate an abstraction-level profile value.

    Accepts:
    * A plain string: ``'high'``, ``'mid'``, or ``'low'``.
    * A dict with an ``abstraction_level`` key whose value is one of
      the three valid levels.  The dict may carry additional keys
      (e.g. panel composition hints), which are preserved in the
      returned canonical string.

    Returns a canonical string representation:
    * For a plain string, the level itself (e.g. ``'high'``).
    * For a dict, ``{abstraction_level}:{remaining kv pairs sorted}``
      (e.g. ``'high:critics=5,model=opus'``).

    Raises :exc:`ValueError` for any unrecognised value shape or level.
    """
    if isinstance(value, str):
        stripped = value.strip()
        if stripped not in _VALID_ABSTRACTION_LEVELS:
            raise ValueError(
                f"unknown abstraction level {stripped!r}; "
                f"expected one of {sorted(_VALID_ABSTRACTION_LEVELS)}"
            )
        return stripped

    if isinstance(value, dict):
        level = value.get("abstraction_level")
        if not isinstance(level, str) or level.strip() not in _VALID_ABSTRACTION_LEVELS:
            raise ValueError(
                f"dict value missing valid 'abstraction_level' key; "
                f"got {level!r}, expected one of {sorted(_VALID_ABSTRACTION_LEVELS)}"
            )
        extras = sorted(
            (k, v) for k, v in value.items() if k != "abstraction_level"
        )
        if extras:
            extra_str = ",".join(f"{k}={v}" for k, v in extras)
            return f"{level.strip()}:{extra_str}"
        return level.strip()

    raise ValueError(
        f"expected str or dict, got {type(value).__name__}"
    )


__all__ = [
    "abstraction_level_validator",
]
