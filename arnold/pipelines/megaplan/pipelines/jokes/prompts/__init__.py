"""Prompt content for the standalone ``jokes`` pipeline."""

from __future__ import annotations

from typing import Mapping


PROMPTS: dict[str, str] = {
    "draft_joke": (
        "Draft a concise joke about {topic}. Keep the setup clear and leave "
        "room for a sharper final beat."
    ),
    "tighten_joke": (
        "Tighten the joke about {topic}. Prefer one setup, one turn, and no "
        "extra explanation. Prior artifacts: {previous_artifacts}"
    ),
    "emit_joke": (
        "Emit the final joke about {topic}. Return only the polished joke. "
        "Prior artifacts: {previous_artifacts}"
    ),
}


def render_prompt(
    key: str,
    *,
    topic: str,
    previous: Mapping[str, str],
) -> str:
    template = PROMPTS.get(key)
    if template is None:
        raise KeyError(f"unknown jokes prompt key: {key}")
    previous_artifacts = ", ".join(
        f"{name}={path}" for name, path in sorted(previous.items())
    ) or "none"
    return template.format(topic=topic, previous_artifacts=previous_artifacts)


__all__ = ["PROMPTS", "render_prompt"]
