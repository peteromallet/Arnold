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
    sprints = hot_context.get("sprints") or []
    codebases = hot_context.get("codebases") or []
    recent_code_artifacts = hot_context.get("recent_code_artifacts") or []
    response_policy = hot_context.get("response_policy") or {}
    resolved_reference = hot_context.get("resolved_reference") or {}
    dynamic_sections: list[str] = []
    if sprints:
        dynamic_sections.append(
            "\n".join(
                ["# Sprint Snapshot"]
                + [
                    f"- Sprint {row.get('sprint_number')}: {row.get('name')} "
                    f"[{row.get('status')}], queue_position={row.get('queue_position')}, "
                    f"pending_reason={row.get('pending_reason')}"
                    for row in sprints
                ]
            )
        )
    if hot_context.get("all_sprints_pending_no_queued"):
        dynamic_sections.append(
            "# Sprint Warning\nAll sprints are pending and no sprint is queued."
        )
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
    if codebases:
        dynamic_sections.append(
            "\n".join(
                ["# Available Codebases"]
                + [
                    f"- {row.get('owner')}/{row.get('name')} "
                    f"(id: {row.get('id')}, scope: {row.get('scope')}, "
                    f"group: {row.get('group_name') or 'none'}, notes: {row.get('notes') or 'none'})"
                    for row in codebases
                ]
            )
        )
    if recent_code_artifacts:
        dynamic_sections.append(
            "\n".join(
                ["# Recent Code Artifacts"]
                + [
                    f"- {row.get('kind')} {row.get('file_path') or row.get('scope') or 'artifact'}: "
                    f"{row.get('content_summary') or row.get('metadata') or row.get('id')}"
                    for row in recent_code_artifacts
                ]
            )
        )
    if response_policy:
        lines = ["# Response Policy"]
        mode = response_policy.get("mode")
        if mode:
            lines.append(f"- User mode: {mode}")
        if response_policy.get("conversation_gap_acknowledgment", {}).get("should_acknowledge"):
            hours = response_policy["conversation_gap_acknowledgment"].get("hours")
            lines.append(f"- Briefly acknowledge the conversation gap ({hours} hours) before continuing.")
        if mode == "deep-thinking":
            lines.append("- Be measured and substantive; include reasoning where it changes the decision.")
        elif mode == "brainstorming":
            lines.append("- Be exploratory; offer alternatives without over-settling too early.")
        elif mode == "executing":
            lines.append("- Be direct; take a position and keep elaboration minimal.")
        dynamic_sections.append("\n".join(lines))
    if resolved_reference:
        if resolved_reference.get("resolved"):
            dynamic_sections.append(
                "# Resolved User Reference\n"
                f"- Target: {resolved_reference.get('target')}"
            )
        elif resolved_reference.get("reason") == "ambiguous_deictic":
            dynamic_sections.append(
                "# Reference Ambiguity\n"
                "- The user's reference to the previous bot output is ambiguous; ask a focused clarification."
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
