"""Mode helpers shared across workflow, prompts, and handlers.

TODO(0.24): These helpers (`is_creative_mode`, `creative_form_id`,
`is_prose_mode`) encode the legacy mode-as-state.config-key shape. The
0.23 doc/creative pipelines route via `state['config']['pipeline']`
and `state['config']['form']` instead. These helpers are retained for
the legacy `--auto-start` planning + mode-overlay path (USER DECISION 2)
and for 0.22 plan-state compatibility; they are scheduled for removal
in 0.24 alongside `compile_pipeline_for`'s creative/joke branch.
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
