"""Central template registry for structured-output template builders.

Every megaplan phase that produces model-generated structured output
registers a :class:`TemplateRegistration` keyed by
:attr:`StepContract.phase_identity`.  The registry owns mode metadata
(``file_fill``, ``batch_assembly``, ``markdown_exempt``, ``subloop_exempt``,
``deferred``) and the corresponding :data:`TemplateBuilder` callable.

Import contract
    This module may import prompt builders but must **not** import handlers
    or workers.  It is a leaf dependency for ``workers/hermes.py`` and the
    handler layer; an import cycle through handlers/workers would deadlock
    the process.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

# ---------------------------------------------------------------------------
# TemplateBuilder protocol
# ---------------------------------------------------------------------------

#: Signature for a template builder: accepts whatever context it needs and
#: returns the absolute :class:`~pathlib.Path` to the written scratch file.
#:
#: Concrete builders MUST write an idempotent seed file so the harness can
#: compare the model-filled result against the seed to decide whether the
#: model actually filled the template.
TemplateBuilder = Callable[..., Path]


# ---------------------------------------------------------------------------
# Registry mode
# ---------------------------------------------------------------------------

#: Supported registry modes.
#:
#: ``file_fill``
#:     The phase has a scratch template builder.  Hermes/file-tool workers
#:     write the seed before invocation; handlers promote filled scratch
#:     files to canonical artifacts.
#: ``batch_assembly``
#:     The phase output is assembled from multiple batch outputs (e.g.
#:     ``execute``).  A builder exists for parity/documentation but handlers
#:     do not route through single-file scratch promotion.
#: ``markdown_exempt``
#:     The phase output is Markdown, not structured JSON (e.g. ``plan``,
#:     ``revise``).  No template builder is required.
#: ``subloop_exempt``
#:     The phase is a subloop step whose output is not a single
#:     model-generated structured contract (e.g. tiebreaker phases).
#: ``deferred``
#:     A scratch filename is reserved for parity, but active builder and
#:     handler integration are deferred to a follow-up sprint.  Current
#:     handler behavior is preserved unchanged.
RegistryMode = Literal[
    "file_fill",
    "batch_assembly",
    "markdown_exempt",
    "subloop_exempt",
    "deferred",
]


# ---------------------------------------------------------------------------
# TemplateRegistration dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TemplateRegistration:
    """Registration metadata for one phase's template builder.

    Kept separate from :class:`~arnold_pipelines.megaplan.step_contracts.StepContract`
    so that registry modes and builder references do not pollute the
    phase-identity contract.  ``StepContract`` remains focused on schema
    contracts and phase routing; ``TemplateRegistration`` adds build-time
    and handler-integration metadata.
    """

    #: Phase identity — matches :attr:`StepContract.phase_identity`.
    phase_identity: str

    #: Registry mode governing how the template is used at build time and
    #: during handler promotion.
    mode: RegistryMode

    #: Scratch filename written by the builder (e.g. ``"gate_output.json"``).
    #: Must be an absolute or plan-dir-relative path.
    scratch_filename: str

    #: The builder callable that writes the seed template and returns its
    #: absolute path.  ``None`` for modes where no builder is required
    #: (``markdown_exempt``, ``subloop_exempt``).
    builder: TemplateBuilder | None = None

    #: Whether the builder writes a template already populated with IDs the
    #: model must fill in.  Workers use this metadata without phase-specific
    #: branching.
    pre_populated: bool = False

    #: Human-readable note explaining why the mode was chosen or why
    #: integration is deferred.  Used by parity tests.
    note: str = ""

    # ── optional boundary template / contract references ────────────────
    # These fields allow a TemplateRegistration to cross-reference the
    # declarative boundary contract registry so that structured-output
    # promotion, semantic-health checks, and receipt emission can read
    # template/profile metadata without reaching into handler-private
    # surfaces.

    #: Optional reference to a typed boundary template id (e.g.
    #: ``\"template.validation_boundary\"``).  When set, consumers can
    #: retrieve the canonical :class:`BoundaryContract` template from
    #: :data:`~arnold_pipelines.megaplan.workflows.boundary_contracts.TYPED_BOUNDARY_TEMPLATES_BY_ID`.
    boundary_template_id: str | None = None

    #: Optional version string for the referenced boundary template
    #: (e.g. ``\"1.0\"``).  Paired with *boundary_template_id* for
    #: compatibility-pinning checks.
    boundary_template_version: str | None = None

    #: Optional tuple of :class:`BoundaryContract` ``boundary_id`` values
    #: that this registration satisfies or bridges (e.g.
    #: ``(\"gate_to_revise\",)`` for the gate phase).  Used by
    #: semantic-health to cross-reference template registrations with
    #: boundary contracts.
    boundary_contract_ids: tuple[str, ...] = ()

    #: Optional compatibility classification when this registration
    #: references a boundary template.  Uses the
    #: :class:`~arnold.workflow.boundary_evidence.TemplateCompatibility`
    #: enum values (``\"exact_match\"``, ``\"compatible_extension\"``, etc.).
    compatibility: str | None = None


# ---------------------------------------------------------------------------
# Registry storage
# ---------------------------------------------------------------------------

#: Central registry mapping phase identity → TemplateRegistration.
#: Populated by T2; every enforced model-generated structured contract has an entry.
_TEMPLATE_REGISTRY: dict[str, TemplateRegistration] = {}


def _write_critique_template_from_state(plan_dir: Path, state: Any) -> Path:
    """Write critique template using active checks resolved from plan state."""

    from arnold_pipelines.megaplan._core import configured_robustness
    from arnold_pipelines.megaplan.forms.provocations import select_active_checks
    from arnold_pipelines.megaplan.prompts.critique import _write_critique_template

    robustness = configured_robustness(state)
    checks = select_active_checks(state, robustness, plan_dir=plan_dir)
    return _write_critique_template(plan_dir, state, checks)


def _write_finalize_template_from_state(plan_dir: Path, state: Any) -> Path:
    from arnold_pipelines.megaplan.prompts.finalize import _write_finalize_template

    return _write_finalize_template(plan_dir, state)


def _write_review_template_from_state(plan_dir: Path, state: Any) -> Path:
    from arnold_pipelines.megaplan.prompts.review import _write_review_template

    return _write_review_template(plan_dir, state)


def _write_gate_template_from_state(plan_dir: Path, state: Any) -> Path:
    from arnold_pipelines.megaplan.prompts.gate import _write_gate_template

    return _write_gate_template(plan_dir, state)


def _write_critique_evaluator_template_from_state(plan_dir: Path, state: Any) -> Path:
    from arnold_pipelines.megaplan.prompts.critique_evaluator import (
        _write_critique_evaluator_template,
    )

    return _write_critique_evaluator_template(plan_dir, state)


def _write_execute_template_from_state(plan_dir: Path, state: Any) -> Path:
    from arnold_pipelines.megaplan.prompts.execute import _write_execute_template

    return _write_execute_template(plan_dir, state)

# ---------------------------------------------------------------------------
# Auto-register all 17 phases on import
# ---------------------------------------------------------------------------
# The registry is populated eagerly so parity tests can validate coverage
# immediately.

for _reg in [
    # ── file_fill: structured JSON phases ────────────────────────────────
    TemplateRegistration(
        phase_identity="finalize",
        mode="file_fill",
        scratch_filename="finalize_output.json",
        builder=_write_finalize_template_from_state,
        boundary_template_id="template.artifact_promotion",
        boundary_template_version="1.0",
        boundary_contract_ids=("finalize_artifacts", "finalize_fallback"),
        compatibility="compatible_extension",
        note="File-fill template builder and handler promotion are wired. "
        "References template.artifact_promotion as its declarative boundary "
        "template for artifact promotion semantics.",
    ),
    TemplateRegistration(
        phase_identity="critique",
        mode="file_fill",
        scratch_filename="critique_output.json",
        builder=_write_critique_template_from_state,
        pre_populated=True,
        note="File-fill template builder resolves active critique checks from plan state.",
    ),
    TemplateRegistration(
        phase_identity="review",
        mode="file_fill",
        scratch_filename="review_output.json",
        builder=_write_review_template_from_state,
        pre_populated=True,
        note="File-fill template builder pre-populates task and sense-check IDs.",
    ),
    TemplateRegistration(
        phase_identity="gate",
        mode="file_fill",
        scratch_filename="gate_output.json",
        builder=_write_gate_template_from_state,
        boundary_template_id="template.validation_boundary",
        boundary_template_version="1.0",
        boundary_contract_ids=("gate_to_revise",),
        compatibility="compatible_extension",
        note="File-fill template builder and reprompt scratch reuse are wired. "
        "References template.validation_boundary (ValidationBoundary) as its "
        "declarative boundary template.",
    ),
    TemplateRegistration(
        phase_identity="critique_evaluator",
        mode="file_fill",
        scratch_filename="critique_evaluator_output.json",
        builder=_write_critique_evaluator_template_from_state,
        note="File-fill template builder is wired for adaptive critique evaluation.",
    ),
    # ── batch_assembly: execute assembles from batch outputs ──────────────
    TemplateRegistration(
        phase_identity="execute",
        mode="batch_assembly",
        scratch_filename="execute_output.json",
        builder=_write_execute_template_from_state,
        note="Execute output is assembled from multiple batch outputs. "
        "The builder exists for parity/documentation but handlers do not "
        "route through single-file scratch promotion. Confirmed in T12.",
    ),
    # ── markdown_exempt: plan and revise are Markdown, not structured JSON ─
    TemplateRegistration(
        phase_identity="plan",
        mode="markdown_exempt",
        scratch_filename="",
        builder=None,
        note="Plan output is Markdown, not structured JSON. No template builder required.",
    ),
    TemplateRegistration(
        phase_identity="revise",
        mode="markdown_exempt",
        scratch_filename="",
        builder=None,
        note="Revise output is Markdown, not structured JSON. No template builder required.",
    ),
    # ── subloop_exempt: tiebreaker subloop phases ─────────────────────────
    TemplateRegistration(
        phase_identity="tiebreaker_researcher",
        mode="subloop_exempt",
        scratch_filename="",
        builder=None,
        note="Subloop step whose output is not a single model-generated "
        "structured contract. No template builder required.",
    ),
    TemplateRegistration(
        phase_identity="tiebreaker_challenger",
        mode="subloop_exempt",
        scratch_filename="",
        builder=None,
        note="Subloop step whose output is not a single model-generated "
        "structured contract. No template builder required.",
    ),
    # ── deferred: builder exists for parity, handler integration deferred ─
    TemplateRegistration(
        phase_identity="prep",
        mode="deferred",
        scratch_filename="prep_output.json",
        builder=None,
        note="Handler integration deferred to follow-up sprint. "
        "Current prep generic template behavior preserved unchanged.",
    ),
    TemplateRegistration(
        phase_identity="prep-triage",
        mode="deferred",
        scratch_filename="prep_triage_output.json",
        builder=None,
        note="Prep sub-step; handler integration deferred. "
        "Current behavior preserved unchanged.",
    ),
    TemplateRegistration(
        phase_identity="prep-distill",
        mode="deferred",
        scratch_filename="prep_distill_output.json",
        builder=None,
        note="Prep sub-step; handler integration deferred. "
        "Current behavior preserved unchanged.",
    ),
    TemplateRegistration(
        phase_identity="prep-research",
        mode="deferred",
        scratch_filename="prep_research_output.json",
        builder=None,
        note="Prep sub-step; handler integration deferred. "
        "Current behavior preserved unchanged.",
    ),
    TemplateRegistration(
        phase_identity="feedback",
        mode="deferred",
        scratch_filename="feedback_output.json",
        builder=None,
        note="Handler integration deferred to follow-up sprint. "
        "Current feedback handler behavior preserved unchanged.",
    ),
    TemplateRegistration(
        phase_identity="loop_plan",
        mode="deferred",
        scratch_filename="loop_plan_output.json",
        builder=None,
        note="Loop variant; normalizer=plan. Handler integration deferred. "
        "Current behavior preserved unchanged.",
    ),
    TemplateRegistration(
        phase_identity="loop_execute",
        mode="deferred",
        scratch_filename="loop_execute_output.json",
        builder=None,
        note="Loop variant; normalizer=execute. Handler integration deferred. "
        "Current behavior preserved unchanged.",
    ),
]:
    _reg_id = _reg.phase_identity
    if _reg_id in _TEMPLATE_REGISTRY:
        raise KeyError(
            f"TemplateRegistration for {_reg_id!r} already exists; "
            f"duplicate registrations are not allowed"
        )
    _TEMPLATE_REGISTRY[_reg_id] = _reg


def _validate_builder_contracts() -> None:
    """Validate registry modes against builder metadata at import time."""

    for phase, reg in _TEMPLATE_REGISTRY.items():
        if reg.mode in {"file_fill", "batch_assembly"} and reg.builder is None:
            raise ValueError(f"{phase}: {reg.mode} registration requires a builder")
        if reg.mode in {"markdown_exempt", "subloop_exempt"} and reg.builder is not None:
            raise ValueError(f"{phase}: {reg.mode} registration must not have a builder")
        if reg.pre_populated and reg.mode != "file_fill":
            raise ValueError(f"{phase}: pre_populated is only valid for file_fill phases")


_validate_builder_contracts()


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def register(registration: TemplateRegistration) -> None:
    """Register a template builder for a phase identity.

    Raises :class:`KeyError` if *registration.phase_identity* is already
    registered (duplicate registrations are a configuration error).
    """
    key = registration.phase_identity
    if key in _TEMPLATE_REGISTRY:
        raise KeyError(
            f"TemplateRegistration for {key!r} already exists; "
            f"duplicate registrations are not allowed"
        )
    _TEMPLATE_REGISTRY[key] = registration


def get_template_registration(phase_identity: str) -> TemplateRegistration | None:
    """Return the :class:`TemplateRegistration` for *phase_identity*, or ``None``."""
    return _TEMPLATE_REGISTRY.get(phase_identity)


def get_template_builder(phase_identity: str) -> TemplateBuilder | None:
    """Return the :data:`TemplateBuilder` for *phase_identity*, or ``None``."""
    reg = _TEMPLATE_REGISTRY.get(phase_identity)
    return reg.builder if reg is not None else None


def get_registered_phases() -> frozenset[str]:
    """Return the set of all registered phase identities."""
    return frozenset(_TEMPLATE_REGISTRY)


def get_phases_by_mode(mode: RegistryMode) -> frozenset[str]:
    """Return the set of registered phase identities matching *mode*."""
    return frozenset(
        key
        for key, reg in _TEMPLATE_REGISTRY.items()
        if reg.mode == mode
    )


def is_registered(phase_identity: str) -> bool:
    """Return ``True`` if *phase_identity* has a template registration."""
    return phase_identity in _TEMPLATE_REGISTRY
