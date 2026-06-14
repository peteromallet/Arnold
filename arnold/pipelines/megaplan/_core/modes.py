"""Mode helpers shared across workflow, prompts, and handlers.

These helpers read the persisted ``state['config']['mode']`` shape used
by init-time mode selection and prompt rendering. First-class pipelines
such as ``doc`` and ``creative`` carry their own pipeline/form metadata;
planning graph compilation no longer has a mode-specific overlay layer.
"""

from __future__ import annotations

from typing import Any, Mapping


def _config(state: Mapping[str, Any]) -> Mapping[str, Any]:
    config = state.get("config", {})
    return config if isinstance(config, Mapping) else {}


def is_creative_mode(state: Mapping[str, Any]) -> bool:
    """Return whether state represents creative-work mode or legacy joke mode."""
    return _config(state).get("mode", "code") in {"creative", "joke"}


def creative_form_id(state: Mapping[str, Any]) -> str | None:
    """Return the active creative form id, including legacy joke fallback."""
    config = _config(state)
    mode = config.get("mode", "code")
    if mode not in {"creative", "joke"}:
        return None
    form = config.get("form")
    if isinstance(form, str) and form:
        return form
    if mode == "joke":
        return "joke"
    return None


def is_prose_mode(state: Mapping[str, Any]) -> bool:
    """Return whether the mode produces a prose artifact instead of code."""
    return _config(state).get("mode", "code") in {"doc", "joke", "creative"}
