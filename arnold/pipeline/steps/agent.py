"""Neutral single-model step: read inputs, render prompt, call worker, write output.

Uses ``artifact_root`` from Arnold :class:`StepContext` — no ``plan_dir``.
Prompt resolution goes through :class:`~arnold.pipeline.resources.PipelineResourceBundle`
and :func:`~arnold.pipeline.resources.resolve_prompt`.

Writes ``<artifact_root>/<stage_name>/<label>/v<n>.<suffix>`` with the model's
response using the neutral versioned-artifact helpers from
:mod:`arnold.pipeline.artifacts`.

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
from arnold.pipeline.types import ContractResult, StepContext, StepResult

#: Signature for a callable that accepts keyword arguments and returns any value.
#: write_text coerces to str() so non-string returns (int, dict, etc.) are safe.
WorkerFn = Callable[..., Any]


@dataclass
class AgentStep:
    """A neutral single-model step that writes versioned artifacts.

    Uses ``ctx.artifact_root`` as the output root.  Prompt resolution is
    delegated to :func:`arnold.pipeline.resources.resolve_prompt` via an
    optional :class:`~arnold.pipeline.resources.PipelineResourceBundle`.

    Compiler-injected fields (prefixed with ``_``) are set by the pipeline
    builder at construction time and consumed by :meth:`run`.
    """

    name: str
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None

    # -- compiler-injected configuration ---------------------------------
    _prompt_source: PromptSource | None = None
    _input_refs: list[str] = field(default_factory=list)
    _output_label: str = "markdown"
    _output_suffix: str = "md"
    _worker: WorkerFn | None = None
    _pipeline_name: str = ""
    _mode: str = ""
    _usage_extractor: Callable[..., dict[str, Any]] | None = None

    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        """Execute the step: resolve inputs, resolve prompt, call worker, write artifact.

        Parameters
        ----------
        ctx:
            Arnold step context.  ``ctx.artifact_root`` is used as the
            output root directory.  ``ctx.inputs`` provides resolved
            upstream artifact paths.
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
            prompt_text = f"[AgentStep {self.name}] no prompt source configured"

        # 3. Interpolate {name} placeholders with input values
        rendered = self._interpolate(prompt_text, inputs)

        # 4. Determine output directory and version via neutral helpers
        out_dir = artifact_dir(ctx, self.name, self._output_label)
        version = next_version(ctx, self.name, self._output_label, self._output_suffix)
        output_path = out_dir / f"v{version}.{self._output_suffix}"

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
            # This preserves the rendered content for inspection in no-worker
            # pipelines (e.g. tests without a model backend).
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

        contract = ContractResult(
            payload={"artifact_path": str(output_path), "label": self._output_label},
            schema_version="",  # __post_init__ fills CONTRACT_RESULT_SCHEMA_VERSION
        )
        return StepResult(
            outputs={},
            contract_result=contract,
            next="done",
            state_patch=state_patch,
            hook_metadata=hook_metadata,
        )

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _interpolate(prompt: str, inputs: dict[str, Any]) -> str:
        """Replace ``{name}`` placeholders with string representations of input values.

        Does NOT read file contents — that is the caller's responsibility
        before passing values into this method.  This keeps the neutral
        step free of filesystem access beyond the artifact helpers.
        """
        result = prompt
        for name, value in inputs.items():
            placeholder = "{" + name + "}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result
