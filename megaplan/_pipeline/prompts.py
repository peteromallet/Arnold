"""Pluggable prompt registry for ``_pipeline`` Steps.

Each Step carries a ``prompt_key`` (declared on the frozen ``Step``
Protocol in ``megaplan/_pipeline/types.py``). At dispatch time the
executor resolves that key against the registry to fetch a prompt
template; the Step's ``run`` calls
:func:`resolve_prompt(ctx, key)` to get a fully-rendered prompt
string. A new mode (joke/doc/etc.) just registers an alternate
template under the same key — no Step subclassing.

Defaults are deliberately minimal — production handlers under
``megaplan/handlers/`` keep their own per-phase prompts and ignore
this registry. The registry exists for demo + Sprint-3-follow-up
Steps that want a single source for their prompt text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from megaplan._pipeline.types import StepContext


PromptRenderer = Callable[[StepContext, Mapping[str, Any]], str]


@dataclass
class PromptRegistry:
    """Pipeline + mode aware mapping of ``prompt_key`` → ``PromptRenderer``.

    Lookup precedence (most → least specific):

    1. ``"<pipeline>/<key>:<mode>"`` — pipeline-scoped, mode-specific.
    2. ``"<pipeline>/<key>"``       — pipeline-scoped default.
    3. ``"<key>:<mode>"``           — global mode-specific.
    4. ``"<key>"``                  — global default.

    Pipeline-scoped registration lets two pipelines share a Step
    class (e.g. ``CritiqueStep``) but use different prompts without
    renaming the step. The pipeline name comes from
    ``ctx.inputs['_pipeline']`` when set (the registry helper injects
    it on each ``run_pipeline_by_name`` invocation).
    """

    renderers: dict[str, PromptRenderer] = field(default_factory=dict)

    def register(self, key: str, renderer: PromptRenderer) -> None:
        self.renderers[key] = renderer

    def resolve(
        self,
        key: str,
        mode: str | None = None,
        pipeline: str | None = None,
    ) -> PromptRenderer:
        if pipeline and mode:
            candidate = f"{pipeline}/{key}:{mode}"
            if candidate in self.renderers:
                return self.renderers[candidate]
        if pipeline:
            candidate = f"{pipeline}/{key}"
            if candidate in self.renderers:
                return self.renderers[candidate]
        if mode:
            candidate = f"{key}:{mode}"
            if candidate in self.renderers:
                return self.renderers[candidate]
        if key in self.renderers:
            return self.renderers[key]
        raise KeyError(
            f"no prompt registered for key={key!r} mode={mode!r} pipeline={pipeline!r}"
        )

    def render(
        self,
        ctx: StepContext,
        key: str,
        params: Mapping[str, Any] | None = None,
    ) -> str:
        pipeline = None
        if isinstance(ctx.inputs, Mapping):
            pipeline_value = ctx.inputs.get("_pipeline")
            if isinstance(pipeline_value, str):
                pipeline = pipeline_value
        renderer = self.resolve(key, mode=ctx.mode, pipeline=pipeline)
        return renderer(ctx, params or {})


_GLOBAL_REGISTRY = PromptRegistry()


def register_prompt(key: str, renderer: PromptRenderer) -> None:
    _GLOBAL_REGISTRY.register(key, renderer)


def resolve_prompt(
    ctx: StepContext, key: str, params: Mapping[str, Any] | None = None
) -> str:
    return _GLOBAL_REGISTRY.render(ctx, key, params)


def register_pipeline_prompt(
    pipeline: str,
    key: str,
    renderer: PromptRenderer,
    *,
    mode: str | None = None,
) -> None:
    """Register a prompt scoped to a specific pipeline (and optionally mode).

    Lets two pipelines share a Step class but use different prompts
    for it. Equivalent to ``register_prompt(f'{pipeline}/{key}[:{mode}]', renderer)``
    but explicit about the scope.
    """

    suffix = f":{mode}" if mode else ""
    register_prompt(f"{pipeline}/{key}{suffix}", renderer)


def registered_keys() -> tuple[str, ...]:
    return tuple(sorted(_GLOBAL_REGISTRY.renderers.keys()))


# ---------------------------------------------------------------------------
# Default prompts for demo Steps. New modes can override by registering a
# `"<key>:<mode>"` entry.
# ---------------------------------------------------------------------------


def _critique_default(ctx: StepContext, params: Mapping[str, Any]) -> str:
    rubric = params.get("rubric", "clarity, concreteness, brevity")
    return (
        f"You are a document critic. Rate this draft on: {rubric}. "
        "Emit JSON: {\"score\": float in [0,1], \"flags\": [str, ...]}"
    )


def _critique_doc(ctx: StepContext, params: Mapping[str, Any]) -> str:
    return (
        "You are a documentation reviewer. The audience is a software "
        "engineer skimming. Flag every place a sentence buries the lede or "
        "uses a vague verb. JSON: {\"score\": float, \"flags\": [str]}"
    )


def _critique_joke(ctx: StepContext, params: Mapping[str, Any]) -> str:
    return (
        "You are a punch-up writer. Rate this joke draft on: setup-payoff "
        "tightness, surprise, brevity. JSON: {\"score\": float, "
        "\"flags\": [str]}"
    )


def _revise_default(ctx: StepContext, params: Mapping[str, Any]) -> str:
    flags = params.get("flags", [])
    return (
        "Revise the draft below to resolve these flags: "
        + "; ".join(str(f) for f in flags)
        + ". Preserve voice. Output the full revised draft."
    )


register_prompt("critique", _critique_default)
register_prompt("critique:doc", _critique_doc)
register_prompt("critique:joke", _critique_joke)
register_prompt("revise", _revise_default)
