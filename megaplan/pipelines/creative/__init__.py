"""Python composition of the ``creative`` pipeline (0.23, T7).

First-class creative pipeline replacing the legacy ``--mode creative``
and ``--mode joke`` overlays on ``planning``. ``--form`` is a
first-class input on the pipeline (validated against
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
``megaplan/pipelines/creative/prompts/`` in T8) and is preserved by
passing the form id through to each stage's ``prompt_key`` (the
PromptRegistry resolves form-specialised slots via the
``<key>:<form>`` convention introduced in T8).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from megaplan.forms import available_form_ids
from megaplan.types import CliError
from megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)

# Import the prompts sub-package for its register_pipeline_prompt side-effects.
from megaplan.pipelines.creative import prompts as _prompts  # noqa: F401, E402


_PIPELINE_DIR: Path = Path(__file__).parent / "creative"


# ── Module-level metadata surfaced via PipelineRegistry ────────────────

description: str = (
    "Creative-form pipeline: form-aware prep → execute → critique → "
    "revise → finalize. Forms registry validates --form; "
    "--primary-criterion threads through as a first-class input."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ()
recommended_profiles: tuple[str, ...] = ()


# ── Stage step shells ─────────────────────────────────────────────────


@dataclass(frozen=True)
class _CreativeStep:
    """Form-aware stage shell.

    Each stage carries the form id and (optional) primary_criterion as
    dataclass fields so that the prompt-rendering layer relocated in T8
    can resolve form-specialised prompts via ``prompt_key`` lookups
    keyed off ``{base_key}:{form}``. The shell here writes an empty
    artifact placeholder so the pipeline can be exercised end-to-end
    against a mocked worker (T9 test path).
    """

    name: str = ""
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    form: str = ""
    primary_criterion: str | None = None
    next_label: str = "halt"

    def run(self, ctx: StepContext) -> StepResult:
        out_dir = Path(ctx.plan_dir) / self.name
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "v1.md"
        if not out.exists():
            out.write_text("")
        return StepResult(outputs={self.name: out}, next=self.next_label)


# ── Pipeline assembly ──────────────────────────────────────────────────


def build_pipeline(
    form: str = "joke",
    primary_criterion: str | None = None,
) -> Pipeline:
    """Return the canonical ``creative`` :class:`Pipeline` for *form*.

    *form* is validated against :func:`available_form_ids` — unknown
    forms raise ``CliError('invalid_args')`` so the CLI surface and the
    init handler stay aligned on the same registry.

    *primary_criterion*, when set, is threaded through to each stage as
    a dataclass field so the relocated prompt modules (T8) can render
    it into the form-specific prompt body.

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
        )

    common: Mapping[str, object] = {
        "form": form,
        "primary_criterion": primary_criterion,
    }

    stages: dict[str, Stage] = {
        "prep": Stage(
            name="prep",
            step=_CreativeStep(
                name="prep",
                prompt_key=f"prep:{form}",
                next_label="execute_creative",
                **common,  # type: ignore[arg-type]
            ),
            edges=(Edge(label="execute_creative", target="execute_creative"),),
        ),
        "execute_creative": Stage(
            name="execute_creative",
            step=_CreativeStep(
                name="execute_creative",
                prompt_key=f"execute_creative:{form}",
                next_label="critique_creative",
                **common,  # type: ignore[arg-type]
            ),
            edges=(
                Edge(label="critique_creative", target="critique_creative"),
            ),
        ),
        "critique_creative": Stage(
            name="critique_creative",
            step=_CreativeStep(
                name="critique_creative",
                prompt_key=f"critique_creative:{form}",
                next_label="revise_creative",
                **common,  # type: ignore[arg-type]
            ),
            edges=(
                Edge(label="revise_creative", target="revise_creative"),
            ),
        ),
        "revise_creative": Stage(
            name="revise_creative",
            step=_CreativeStep(
                name="revise_creative",
                prompt_key=f"revise_creative:{form}",
                next_label="finalize",
                **common,  # type: ignore[arg-type]
            ),
            edges=(Edge(label="finalize", target="finalize"),),
        ),
        "finalize": Stage(
            name="finalize",
            step=_CreativeStep(
                name="finalize",
                prompt_key=None,
                next_label="halt",
                **common,  # type: ignore[arg-type]
            ),
            edges=(),
        ),
    }

    return Pipeline(stages=stages, entry="prep")


__all__ = [
    "build_pipeline",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
]
