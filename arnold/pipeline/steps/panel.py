"""Neutral panel reviewer step: one reviewer within a fan-out panel.

Each reviewer is like an :class:`~arnold.pipeline.steps.agent.AgentStep` but
scoped to a persona identified by ``_reviewer_id``.  The executor runs all
reviewers in a :class:`~concurrent.futures.ThreadPoolExecutor`; output
ordering follows YAML reviewer-list order (handled by the executor, not
this step).

Writes ``<artifact_root>/<stage_id>/<reviewer_id>/v<n>.md`` using the
neutral versioned-artifact helpers from :mod:`arnold.pipeline.artifacts`.

Boundary discipline: no ``megaplan`` imports.  No ``typed_ports_on``.
No ``plan_dir`` references.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from arnold.pipeline.artifacts import artifact_dir, next_version
from arnold.pipeline.resources import PromptSource, resolve_prompt
from arnold.pipeline.media_cost import normalize_usage_extraction
from arnold.pipeline.step_invocation import unwrap_step_invocation_result
from arnold.pipeline.types import StepContext, StepResult

WorkerFn = Callable[..., str]


@dataclass
class PanelReviewerStep:
    """A single reviewer within a panel — like AgentStep but scoped to a persona.

    Writes ``<artifact_root>/<stage_id>/<reviewer_id>/v<n>.md``.

    Output ordering in the panel as a whole is determined by the executor,
    which preserves YAML reviewer-list order regardless of future completion
    order.

    Uses ``ctx.artifact_root`` as the output root — no ``plan_dir``.
    """

    name: str  # e.g. "panel_review.pessimist"
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None

    # -- compiler-injected configuration ---------------------------------
    _prompt_source: PromptSource | None = None
    _pipeline_name: str = ""
    _input_refs: list[str] = field(default_factory=list)
    _reviewer_id: str = ""
    _worker: WorkerFn | None = None
    _mode: str = ""
    _usage_extractor: Callable[..., dict[str, Any]] | None = None

    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        """Execute the reviewer: resolve inputs, resolve prompt, call worker, write artifact.

        Parameters
        ----------
        ctx:
            Arnold step context.  ``ctx.artifact_root`` is used as the
            output root directory.
        """
        # 1. Collect inputs from ctx.inputs
        inputs: dict[str, Any] = {}
        for ref in self._input_refs:
            if ref in ctx.inputs:
                inputs[ref] = ctx.inputs[ref]

        # 2. Resolve the prompt template
        if self._prompt_source is not None:
            prompt_text = resolve_prompt(self._prompt_source, ctx, params=inputs)
        else:
            prompt_text = (
                f"[PanelReviewer {self._reviewer_id}] no prompt source configured"
            )

        # 3. Interpolate {name} placeholders with input values
        rendered = self._interpolate(prompt_text, inputs)

        # 4. Determine output directory: <artifact_root>/<stage_id>/<reviewer_id>/
        stage_id = self.name.rsplit(".", 1)[0] if "." in self.name else self.name
        out_dir = artifact_dir(ctx, stage_id, self._reviewer_id)
        version = next_version(ctx, stage_id, self._reviewer_id, "md")
        output_path = out_dir / f"v{version}.md"

        # 5. Call worker or produce placeholder
        worker_result: Any = None
        if self._worker is not None:
            worker_inputs = {k: str(v) for k, v in inputs.items()}
            worker_result = self._worker(
                prompt=rendered,
                step_name=self.name,
                pipeline_name=self._pipeline_name,
                inputs=worker_inputs,
                mode=self._mode or ctx.mode,
            )
        else:
            # No worker: write the resolved + interpolated prompt as output.
            worker_result = rendered

        # 5a. Unwrap any StepInvocationResult envelope — plain returns pass
        #     through unchanged with empty media_usage.
        payload, media_usage = unwrap_step_invocation_result(worker_result)
        result_text = str(payload)
        output_path.write_text(result_text, encoding="utf-8")

        state_patch: dict[str, Any] = {}
        extracted_media_usage: tuple = ()
        if self._usage_extractor is not None:
            try:
                extracted = self._usage_extractor(
                    step_name=self.name,
                    reviewer_id=self._reviewer_id,
                    result_text=result_text,
                )
                sp, extracted_media_usage = normalize_usage_extraction(extracted)
                state_patch.update(sp)
            except Exception:
                pass  # best-effort: never fail the step due to usage extraction

        # 5b. Merge envelope media_usage with extractor media_usage,
        #     and attach only when non-empty.
        all_media_usage = tuple(media_usage) + tuple(extracted_media_usage)
        hook_metadata: dict[str, Any] = {}
        if all_media_usage:
            hook_metadata["media_usage"] = all_media_usage

        return StepResult(
            outputs={self._reviewer_id: str(output_path)},
            next="halt",
            state_patch=state_patch,
            hook_metadata=hook_metadata,
        )

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _interpolate(prompt: str, inputs: dict[str, Any]) -> str:
        """Replace ``{name}`` placeholders with string representations of input values."""
        result = prompt
        for name, value in inputs.items():
            placeholder = "{" + name + "}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result
