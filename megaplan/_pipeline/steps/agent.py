"""Single-model markdown step: read inputs, render prompt, call worker, write output.

Writes ``<plan_dir>/<stage_id>/v<n>.md`` with the model's response.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from megaplan._pipeline.types import StepContext, StepResult


def _latest_artifact(stage_dir: Path) -> Path | None:
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


def _next_version(output_dir: Path) -> int:
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


def _interpolate_inputs(prompt: str, inputs: dict[str, Path]) -> str:
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


def _resolve_inputs(
    refs: list[str],
    ctx: StepContext,
    *,
    panel_reviewer_order: dict[str, list[str]] | None = None,
) -> dict[str, Path]:
    """Resolve YAML input refs to concrete artifact paths.

    Rules:
    * Plain name matching a declared input → ``ctx.inputs[name]``.
    * ``stage_id`` → ``<plan_dir>/<stage_id>/v<N>.<ext>`` (latest version).
    * ``stage_id.*`` → all sub-outputs of a panel stage, in YAML
      reviewer-list order.
    """
    resolved: dict[str, Path] = {}
    for ref in refs:
        if ref.endswith(".*"):
            base = ref[:-2]
            if panel_reviewer_order and base in panel_reviewer_order:
                for reviewer_id in panel_reviewer_order[base]:
                    key = f"{base}.{reviewer_id}"
                    path = _latest_artifact(ctx.plan_dir / base / reviewer_id)
                    if path is not None:
                        resolved[key] = path
            continue

        # Try declared inputs first
        if ref in ctx.inputs:
            resolved[ref] = ctx.inputs[ref]
            continue

        # Try stage output
        path = _latest_artifact(ctx.plan_dir / ref)
        if path is not None:
            resolved[ref] = path
            continue

        # Not yet produced — will be resolved on re-read (e.g. loop back)
        resolved[ref] = ctx.plan_dir / ref / "v1.md"

    return resolved


def _resolve_prompt_text(
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


# Worker function type
WorkerFn = Callable[..., str]


@dataclass
class AgentStep:
    """A single-model step: read inputs, render prompt, call worker, write output.

    Writes ``<plan_dir>/<stage_id>/v<n>.md``.
    """

    name: str
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None

    # Compiler-injected config
    _prompt_ref: str = ""
    _pipeline_dir: Path = field(default_factory=Path)
    _pipeline_name: str = ""
    _input_refs: list[str] = field(default_factory=list)
    _produces: str = "markdown"
    _worker: WorkerFn | None = None
    _prompt_registry: Callable[[str], str] | None = None
    _panel_reviewer_order: dict[str, list[str]] = field(default_factory=dict)
    _mode: str = ""

    def run(self, ctx: StepContext) -> StepResult:
        inputs = _resolve_inputs(
            self._input_refs,
            ctx,
            panel_reviewer_order=self._panel_reviewer_order,
        )
        prompt_text = _resolve_prompt_text(
            self._prompt_ref,
            self._pipeline_dir,
            prompt_registry=self._prompt_registry,
        )
        # Interpolate input contents into prompt
        rendered = _interpolate_inputs(prompt_text, inputs)

        output_dir = ctx.plan_dir / self.name
        output_dir.mkdir(parents=True, exist_ok=True)
        version = _next_version(output_dir)
        output_path = output_dir / f"v{version}.md"

        if self._worker is not None:
            worker_inputs = {k: str(v) for k, v in inputs.items()}
            result_text = self._worker(
                prompt=rendered,
                step_name=self.name,
                pipeline_name=self._pipeline_name,
                inputs=worker_inputs,
                mode=self._mode or ctx.mode,
            )
        else:
            result_text = f"[AgentStep {self.name}] prompt: {self._prompt_ref}"

        output_path.write_text(result_text, encoding="utf-8")
        return StepResult(
            outputs={self.name: output_path},
            next="done",
        )
