"""System prompt loading and versioning."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any


JSONDict = dict[str, Any]
SYSTEM_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "system.md"


def load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def system_prompt_version(content: str | None = None) -> str:
    prompt = load_system_prompt() if content is None else content
    return sha256(prompt.encode("utf-8")).hexdigest()[:8]


def build_system_prompt(hot_context: JSONDict | None = None) -> str:
    prompt = load_system_prompt()
    if not hot_context:
        return prompt

    active_feedback = hot_context.get("active_feedback") or []
    unresolved_observations = hot_context.get("unresolved_observations") or []
    dynamic_sections: list[str] = []
    if active_feedback:
        dynamic_sections.append(
            "\n".join(
                ["# Active Feedback"]
                + [
                    f"- {row.get('kind')}: {row.get('content')} "
                    f"(id: {row.get('id')}, last_applied_at: {row.get('last_applied_at')})"
                    for row in active_feedback
                ]
            )
        )
    if unresolved_observations:
        dynamic_sections.append(
            "\n".join(
                ["# Recent Unresolved Observations"]
                + [
                    f"- {row.get('kind')}: {row.get('content')} (id: {row.get('id')})"
                    for row in unresolved_observations
                ]
            )
        )
    if not dynamic_sections:
        return prompt
    return prompt.rstrip() + "\n\n" + "\n\n".join(dynamic_sections) + "\n"


DEFAULT_PROMPT_VERSION = system_prompt_version()


__all__ = [
    "DEFAULT_PROMPT_VERSION",
    "SYSTEM_PROMPT_PATH",
    "build_system_prompt",
    "load_system_prompt",
    "system_prompt_version",
]
