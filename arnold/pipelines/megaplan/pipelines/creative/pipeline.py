"""Native declaration and projected shell for the first-class ``creative`` pipeline.

``--form`` is a first-class input on the pipeline (validated against
:func:`megaplan.forms.available_form_ids` — the canonical registry the
init handler also consults at ``megaplan/handlers/init.py:62-64``);
``--primary-criterion`` is a first-class creative-pipeline input (it is
already exposed via the existing ``--primary-criterion`` CLI flag).

Native order (linear, single-pass — no gate loop):

    prep (form-aware) → execute_creative → critique_creative → revise_creative → finalize

The ``megaplan/forms/`` package stays canonical and is consumed by 25+
non-creative modules — the creative pipeline imports from
``megaplan.forms`` like any other consumer; the package is NOT
relocated. Provocations + director's-notes sidecar wiring lives in the
per-stage prompt modules (relocated under
``megaplan/pipelines/creative/prompts/``). The default joke form uses
runnable joke-specialised prompt keys. Non-joke forms use the generic
creative keys and pass the form id through stage params/state.

The ``@phase`` wrappers delegate to the existing :class:`CreativeStep`
implementations. ``build_pipeline`` returns the native-backed Arnold
``Pipeline`` shell used by discovery, docs, and runtime execution.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.native import (
    compile_pipeline,
    phase,
    pipeline,
)
from arnold.pipeline import Edge, Pipeline, Stage
from arnold.pipelines.megaplan._pipeline.types import StepContext, StepResult
from arnold.pipelines.megaplan.forms import available_form_ids
from arnold.pipelines.megaplan.types import CliError

from arnold.pipelines.megaplan.pipelines.creative.steps import CreativeStep


# ── Module-level metadata surfaced via PipelineRegistry ────────────────

name: str = "creative"
description: str = (
    "Creative-form pipeline: form-aware prep → execute → critique → "
    "revise → finalize. Forms registry validates --form; "
    "--primary-criterion threads through as a first-class input."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native",)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "linear")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("creative",)


STAGE_SPECS: tuple[tuple[str, str | None, str], ...] = (
    ("prep", "prep", "execute_creative"),
    ("execute_creative", "execute_creative", "critique_creative"),
    ("critique_creative", "critique_creative", "revise_creative"),
    ("revise_creative", "revise_creative", "finalize"),
    ("finalize", None, "halt"),
)


# ── Native helpers ─────────────────────────────────────────────────────


def _ctx_from_native(raw_ctx: object) -> StepContext:
    """Adapt the native runtime's dict context to a Megaplan StepContext."""
    if isinstance(raw_ctx, dict):
        raw_inputs = raw_ctx.get("inputs") or {}
        inputs = (
            {str(key): value for key, value in raw_inputs.items()}
            if isinstance(raw_inputs, Mapping)
            else {}
        )
        return StepContext(
            plan_dir=Path(
                raw_ctx.get("plan_dir") or raw_ctx.get("artifact_root") or "."
            ),
            state=raw_ctx.get("state", {}),
            profile=raw_ctx.get("profile"),
            mode=str(raw_ctx.get("mode") or "creative"),
            inputs=inputs,
            envelope=raw_ctx.get("envelope"),
        )
    plan_dir = getattr(raw_ctx, "plan_dir", None) or getattr(
        raw_ctx,
        "artifact_root",
        ".",
    )
    raw_inputs = getattr(raw_ctx, "inputs", {}) or {}
    inputs = (
        {str(key): value for key, value in raw_inputs.items()}
        if isinstance(raw_inputs, Mapping)
        else {}
    )
    state = getattr(raw_ctx, "state", {}) or {}
    mode = str(getattr(raw_ctx, "mode", None) or "creative")
    return StepContext(
        plan_dir=Path(plan_dir),
        state=state,
        profile=getattr(raw_ctx, "profile", None),
        mode=mode,
        inputs=inputs,
        envelope=getattr(raw_ctx, "envelope", None),
    )


def _form_from_state(state: Any) -> str:
    """Extract the creative form id from state, defaulting to ``"joke"``."""
    if isinstance(state, Mapping):
        config = state.get("config")
        if isinstance(config, Mapping):
            form = config.get("form")
            if isinstance(form, str) and form:
                return form
    return "joke"


def _primary_criterion_from_state(state: Any) -> str | None:
    """Extract ``primary_criterion`` from state config, if set."""
    if isinstance(state, Mapping):
        config = state.get("config")
        if isinstance(config, Mapping):
            raw = config.get("primary_criterion")
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    return None


def _json_safe_step_result(result: StepResult) -> StepResult:
    """Keep native state and resume cursors JSON-serializable."""
    return replace(
        result,
        outputs={key: str(value) for key, value in result.outputs.items()},
    )


# ── Native phase wrappers ────────────────────────────────────────────────


@phase(name="prep")
def _native_prep(ctx: object) -> StepResult:
    step_ctx = _ctx_from_native(ctx)
    form = _form_from_state(step_ctx.state)
    primary_criterion = _primary_criterion_from_state(step_ctx.state)
    result = CreativeStep(
        name="prep",
        prompt_key=_prompt_key_for_form("prep", form),
        form=form,
        primary_criterion=primary_criterion,
        next_label="execute_creative",
    ).run(step_ctx)
    return _json_safe_step_result(result)


@phase(name="execute_creative")
def _native_execute_creative(ctx: object) -> StepResult:
    step_ctx = _ctx_from_native(ctx)
    form = _form_from_state(step_ctx.state)
    primary_criterion = _primary_criterion_from_state(step_ctx.state)
    result = CreativeStep(
        name="execute_creative",
        prompt_key=_prompt_key_for_form("execute_creative", form),
        form=form,
        primary_criterion=primary_criterion,
        next_label="critique_creative",
    ).run(step_ctx)
    return _json_safe_step_result(result)


@phase(name="critique_creative")
def _native_critique_creative(ctx: object) -> StepResult:
    step_ctx = _ctx_from_native(ctx)
    form = _form_from_state(step_ctx.state)
    primary_criterion = _primary_criterion_from_state(step_ctx.state)
    result = CreativeStep(
        name="critique_creative",
        prompt_key=_prompt_key_for_form("critique_creative", form),
        form=form,
        primary_criterion=primary_criterion,
        next_label="revise_creative",
    ).run(step_ctx)
    return _json_safe_step_result(result)


@phase(name="revise_creative")
def _native_revise_creative(ctx: object) -> StepResult:
    step_ctx = _ctx_from_native(ctx)
    form = _form_from_state(step_ctx.state)
    primary_criterion = _primary_criterion_from_state(step_ctx.state)
    result = CreativeStep(
        name="revise_creative",
        prompt_key=_prompt_key_for_form("revise_creative", form),
        form=form,
        primary_criterion=primary_criterion,
        next_label="finalize",
    ).run(step_ctx)
    return _json_safe_step_result(result)


@phase(name="finalize")
def _native_finalize(ctx: object) -> StepResult:
    step_ctx = _ctx_from_native(ctx)
    form = _form_from_state(step_ctx.state)
    primary_criterion = _primary_criterion_from_state(step_ctx.state)
    result = CreativeStep(
        name="finalize",
        prompt_key=None,
        form=form,
        primary_criterion=primary_criterion,
        next_label="halt",
    ).run(step_ctx)
    return _json_safe_step_result(result)


# ── Native pipeline bundle ───────────────────────────────────────────────


@pipeline("creative")
def creative_native(ctx: object) -> Any:
    state = yield _native_prep(ctx)
    state = yield _native_execute_creative(ctx)
    state = yield _native_critique_creative(ctx)
    state = yield _native_revise_creative(ctx)
    state = yield _native_finalize(ctx)
    return state


def _native_bundle() -> Any:
    return compile_pipeline(creative_native)


# ── Pipeline assembly ──────────────────────────────────────────────────


def _stage(
    name: str,
    *,
    prompt_key: str | None,
    next_label: str,
    form: str,
    primary_criterion: str | None,
) -> Stage:
    target = "halt" if next_label == "halt" else next_label
    edges = () if next_label == "halt" else (Edge(label=next_label, target=target),)
    return Stage(
        name=name,
        step=CreativeStep(
            name=name,
            prompt_key=prompt_key,
            form=form,
            primary_criterion=primary_criterion,
            next_label=next_label,
        ),
        edges=edges,
    )


def _prompt_key_for_form(prompt_key: str | None, form: str) -> str | None:
    if prompt_key is None:
        return None
    if form == "joke":
        return f"{prompt_key}:joke"
    return prompt_key


def build_pipeline(
    form: str = "joke",
    primary_criterion: str | None = None,
) -> Pipeline:
    """Return the canonical ``creative`` :class:`Pipeline` for *form*.

    *form* is validated against :func:`available_form_ids` — unknown
    forms raise ``CliError('invalid_args')`` so the CLI surface and the
    init handler stay aligned on the same registry.

    *primary_criterion*, when set, is threaded through to each stage as
    a dataclass field so prompt modules can render it into the
    form-specific prompt body.

    The default *form='joke'* keeps :func:`build_pipeline` callable
    with zero arguments — required so the pipeline registry's discovery
    pass (which calls ``builder()`` with no kwargs) can register the
    creative pipeline without raising. CLI invocations always supply
    an explicit form via ``--form``.

    The native program is compiled and attached directly to the returned
    :class:`Pipeline`; ``resource_bundles`` is left empty because prompts are
    resolved through the native declaration and module-level constants.
    """

    valid_forms = available_form_ids()
    if form not in valid_forms:
        raise CliError(
            "invalid_args",
            f"Unknown creative form: {form!r}. Available: "
            f"{', '.join(valid_forms)}",
            exit_code=2,
        )

    stages = {
        name: _stage(
            name,
            prompt_key=_prompt_key_for_form(prompt_key, form),
            next_label=next_label,
            form=form,
            primary_criterion=primary_criterion,
        )
        for name, prompt_key, next_label in STAGE_SPECS
    }

    projected = Pipeline(stages=stages, entry="prep")
    return replace(
        projected,
        native_program=_native_bundle(),
        resource_bundles=(),
    )


__all__ = [
    "arnold_api_version",
    "build_pipeline",
    "capabilities",
    "default_profile",
    "description",
    "driver",
    "entrypoint",
    "name",
    "recommended_profiles",
    "supported_modes",
]
