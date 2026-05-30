"""Panel reviewer step: one reviewer within a fan-out panel.

Each reviewer is like an AgentStep but scoped to a persona. The executor
runs all reviewers in a ThreadPoolExecutor; output ordering follows YAML
reviewer-list order (handled by the executor, not this step).

Writes ``<plan_dir>/<stage_id>/<reviewer_id>/v<n>.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from megaplan._pipeline.step_helpers import (
    interpolate_inputs,
    next_version,
    resolve_inputs,
    resolve_prompt_text,
)
from megaplan._pipeline.types import StepContext, StepResult

WorkerFn = Callable[..., str]


@dataclass
class PanelReviewerStep:
    """A single reviewer within a panel — like AgentStep but scoped to a persona.

    Writes ``<plan_dir>/<stage_id>/<reviewer_id>/v<n>.md``.

    Output ordering in the panel as a whole is determined by the executor,
    which preserves YAML reviewer-list order regardless of future completion
    order.
    """

    name: str  # e.g. "panel_review.pessimist"
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None

    _prompt_ref: str = ""
    _pipeline_dir: Path = field(default_factory=Path)
    _pipeline_name: str = ""
    _input_refs: list[str] = field(default_factory=list)
    _reviewer_id: str = ""
    _worker: WorkerFn | None = None
    _prompt_registry: Callable[[str], str] | None = None
    _panel_reviewer_order: dict[str, list[str]] = field(default_factory=dict)
    _mode: str = ""

    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        inputs = resolve_inputs(
            self._input_refs,
            ctx,
            panel_reviewer_order=self._panel_reviewer_order,
        )
        prompt_text = resolve_prompt_text(
            self._prompt_ref,
            self._pipeline_dir,
            prompt_registry=self._prompt_registry,
        )
        rendered = interpolate_inputs(prompt_text, inputs)

        # Write to <plan_dir>/<stage_id>/<reviewer_id>/v<n>.md per convention
        stage_id = self.name.rsplit(".", 1)[0] if "." in self.name else self.name
        output_dir = ctx.plan_dir / stage_id / self._reviewer_id
        output_dir.mkdir(parents=True, exist_ok=True)
        version = next_version(output_dir)
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
            result_text = (
                f"[PanelReviewer {self._reviewer_id}] prompt: {self._prompt_ref}"
            )

        output_path.write_text(result_text, encoding="utf-8")
        return StepResult(
            outputs={self._reviewer_id: output_path},
            next="halt",
        )
