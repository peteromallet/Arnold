"""Python composition of the first-class ``creative`` pipeline.

``--form`` is a first-class input on the pipeline (validated against
:func:`megaplan.forms.available_form_ids` — the canonical registry the
init handler also consults at ``megaplan/handlers/init.py:62-64``);
``--primary-criterion`` is a first-class creative-pipeline input (it is
already exposed via the existing ``--primary-criterion`` CLI flag).

Topology (linear, single-pass — no gate loop):

    prep (form-aware) → execute_creative → critique_creative → revise_creative → finalize

The ``megaplan/forms/`` package stays canonical and is consumed by 25+
non-creative modules — the creative pipeline imports from
``megaplan.forms`` like any other consumer; the package is NOT
relocated. Provocations + director's-notes sidecar wiring lives in the
per-stage prompt modules (relocated under
``megaplan/pipelines/creative/prompts/``). The default joke form uses
runnable joke-specialised prompt keys. Non-joke forms use the generic
creative keys and pass the form id through stage params/state.
"""

from __future__ import annotations

from megaplan.forms import available_form_ids
from megaplan.types import CliError
from megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Stage,
)
from megaplan.pipelines.creative.steps import CreativeStep

# Import the prompts sub-package for its register_pipeline_prompt side-effects.
from megaplan.pipelines.creative import prompts as _prompts  # noqa: F401, E402


# ── Module-level metadata surfaced via PipelineRegistry ────────────────

description: str = (
    "Creative-form pipeline: form-aware prep → execute → critique → "
    "revise → finalize. Forms registry validates --form; "
    "--primary-criterion threads through as a first-class input."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ()
recommended_profiles: tuple[str, ...] = ()


STAGE_SPECS: tuple[tuple[str, str | None, str], ...] = (
    ("prep", "prep", "execute_creative"),
    ("execute_creative", "execute_creative", "critique_creative"),
    ("critique_creative", "critique_creative", "revise_creative"),
    ("revise_creative", "revise_creative", "finalize"),
    ("finalize", None, "halt"),
)


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

    return Pipeline(stages=stages, entry="prep")


__all__ = [
    "build_pipeline",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
]
