"""Python composition of the first-class ``creative`` pipeline.

Linear explicit-node workflow:

    prep -> execute_creative -> critique_creative -> revise_creative -> finalize

``--form`` is a first-class input validated against
:func:`arnold_pipelines.megaplan.forms.available_form_ids`; ``--primary-criterion``
threads through as pipeline metadata. Per-stage prompt keys are carried in step
metadata and resolve through the canonical creative prompt bundle.
"""

from __future__ import annotations

from arnold_pipelines.megaplan.forms import available_form_ids
from arnold_pipelines.megaplan.types import CliError
from arnold.workflow.dsl import Capability, Input, Output, Pipeline, Route, Step


name: str = "creative"
description: str = (
    "Creative-form pipeline: form-aware prep → execute → critique → "
    "revise → finalize. Forms registry validates --form; "
    "--primary-criterion threads through as a first-class input."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ()
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("subprocess_isolated", "linear")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("creative",)


def _prompt_key(prompt_key: str | None, form: str) -> str | None:
    if prompt_key is None:
        return None
    if form == "joke":
        return f"{prompt_key}:joke"
    return prompt_key


def build_pipeline(
    form: str = "joke",
    primary_criterion: str | None = None,
) -> Pipeline:
    """Return the canonical ``creative`` explicit-node pipeline for *form*.

    *form* is validated against :func:`available_form_ids` so the CLI surface
    and any registry discovery stay aligned. The default ``form='joke'`` keeps
    :func:`build_pipeline` callable with zero arguments.
    """

    valid_forms = available_form_ids()
    if form not in valid_forms:
        raise CliError(
            "invalid_args",
            f"Unknown creative form: {form!r}. Available: "
            f"{', '.join(valid_forms)}",
            exit_code=2,
        )

    stage_meta: tuple[tuple[str, str | None, str], ...] = (
        ("prep", "prep", "execute_creative"),
        ("execute_creative", "execute_creative", "critique_creative"),
        ("critique_creative", "critique_creative", "revise_creative"),
        ("revise_creative", "revise_creative", "finalize"),
        ("finalize", None, "halt"),
    )

    steps: list[Step] = []
    routes: list[Route] = []
    for index, (step_id, prompt_key, next_label) in enumerate(stage_meta):
        is_terminal = next_label == "halt"
        resolved_prompt = _prompt_key(prompt_key, form)
        step = Step(
            id=step_id,
            kind="agent" if step_id != "finalize" else "emit",
            label=step_id.replace("_", " ").title(),
            inputs=() if index == 0 else (Input(name="previous_artifact"),),
            outputs=(Output(name=f"{step_id}_artifact"), Output(name=f"{step_id}_prompt")),
            capabilities=(Capability(id="creative", route=form or "default"),),
            metadata={
                "prompt_key": resolved_prompt,
                "form": form,
                "primary_criterion": primary_criterion,
                "stage": step_id,
                "terminal": is_terminal,
            },
        )
        steps.append(step)
        if not is_terminal:
            routes.append(
                Route(
                    id=f"{step_id}:{next_label}",
                    source=step_id,
                    target=next_label,
                    label=next_label,
                )
            )

    return Pipeline(
        id="creative",
        version="m5-phase3",
        steps=tuple(steps),
        routes=tuple(routes),
        capabilities=(Capability(id="creative", route=form or "default"),),
        metadata={
            "name": name,
            "description": description,
            "driver": driver,
            "entrypoint": entrypoint,
            "arnold_api_version": arnold_api_version,
            "capabilities": capabilities,
            "default_profile": default_profile,
            "supported_modes": supported_modes,
            "recommended_profiles": recommended_profiles,
            "form": form,
            "primary_criterion": primary_criterion,
            "resource_bundles": ("creative",),
        },
    )


__all__ = [
    "build_pipeline",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
    "driver",
    "arnold_api_version",
    "capabilities",
]
