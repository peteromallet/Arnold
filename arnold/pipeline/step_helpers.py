"""Shared helpers for Python-composition Step implementations.

These helpers are independent of any particular Step class — they resolve
input refs, interpolate input contents into prompts, pick the next /
latest versioned artifact in a stage directory, and resolve prompt refs
to text. They are used by AgentStep / PanelReviewerStep / GateStep /
HumanDecisionStep and by the run_cli human-gate resume path.

``panel_reviewer_order`` is the mapping
``{panel_stage_name: tuple_of_reviewer_ids_in_order}`` used to expand
``<panel>.*`` references; in Python pipelines the builder plumbs it onto
each AgentStep at construction time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from megaplan._pipeline.flags import typed_ports_on
from megaplan._pipeline.types import StepContext


def latest_artifact(stage_dir: Path) -> Path | None:
    """Return the highest-versioned artifact in *stage_dir*, or None."""
    if not stage_dir.is_dir():
        return None
    candidates: list[tuple[int, Path]] = []
    for child in stage_dir.iterdir():
        if child.is_file() and child.name.startswith("v"):
            stem = child.stem
            if stem[1:].isdigit():
                candidates.append((int(stem[1:]), child))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def next_version(output_dir: Path) -> int:
    """Return the next version number for *output_dir*."""
    if not output_dir.is_dir():
        return 1
    max_v = 0
    for child in output_dir.iterdir():
        if child.is_file() and child.name.startswith("v"):
            stem = child.stem
            if stem[1:].isdigit():
                max_v = max(max_v, int(stem[1:]))
    return max_v + 1


def interpolate_inputs(prompt: str, inputs: dict[str, Path]) -> str:
    """Interpolate ``{input_name}`` placeholders with file contents."""
    result = prompt
    for name, path in inputs.items():
        placeholder = "{" + name + "}"
        if placeholder in result:
            try:
                content = Path(path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                content = f"[could not read: {path}]"
            result = result.replace(placeholder, content)
    return result


def resolve_inputs(
    refs: list[str],
    ctx: StepContext,
    *,
    panel_reviewer_order: dict[str, list[str]] | None = None,
) -> dict[str, Path]:
    """Resolve input refs to concrete artifact paths.

    Rules:
    * Plain name matching a declared input → ``ctx.inputs[name]``.
    * ``stage_id`` → ``<plan_dir>/<stage_id>/v<N>.<ext>`` (latest version).
    * ``stage_id.*`` → all sub-outputs of a panel stage, in
      reviewer-list order (from *panel_reviewer_order*).
    """
    resolved: dict[str, Path] = {}
    for ref in refs:
        if ref.endswith(".*"):
            base = ref[:-2]
            if panel_reviewer_order and base in panel_reviewer_order:
                for reviewer_id in panel_reviewer_order[base]:
                    key = f"{base}.{reviewer_id}"
                    path = latest_artifact(ctx.plan_dir / base / reviewer_id)
                    if path is not None:
                        resolved[key] = path
            continue

        # Try declared inputs first
        if ref in ctx.inputs:
            resolved[ref] = ctx.inputs[ref]
            continue

        # Try stage output
        path = latest_artifact(ctx.plan_dir / ref)
        if path is not None:
            resolved[ref] = path
            continue

        # Not yet produced — will be resolved on re-read (e.g. loop back).
        # Flag-ON (M2 / T11b): unresolved refs are a runtime port-binding
        # failure — raise PortBindError instead of fabricating a path.
        if typed_ports_on():
            from megaplan._pipeline.contracts import PortBindError

            raise PortBindError(
                step_id=getattr(ctx, "step_id", "<unknown>"),
                consume_name=ref,
                detail=(
                    f"no upstream artifact under {ctx.plan_dir / ref} "
                    "and ref not in ctx.inputs"
                ),
            )
        resolved[ref] = ctx.plan_dir / ref / "v1.md"

    return resolved


def resolve_prompt_text(
    prompt_ref: str,
    pipeline_dir: Path,
    *,
    prompt_registry: Callable[[str], str] | None = None,
) -> str:
    """Resolve a prompt reference to its text content.

    * If *prompt_ref* ends with ``.md`` → read from *pipeline_dir* / *prompt_ref*.
    * Otherwise → look up in *prompt_registry*.
    """
    if prompt_ref.endswith(".md"):
        prompt_path = (pipeline_dir / prompt_ref).resolve()
        if not prompt_path.is_file():
            raise FileNotFoundError(
                f"Prompt file not found: {prompt_path}"
            )
        return prompt_path.read_text(encoding="utf-8")
    if prompt_registry is not None:
        return prompt_registry(prompt_ref)
    raise ValueError(
        f"Cannot resolve prompt {prompt_ref!r}: not a .md path and no "
        f"prompt_registry provided"
    )

__all__ = [
    "latest_artifact",
    "next_version",
    "resolve_inputs",
    "interpolate_inputs",
    "resolve_prompt_text",
]

