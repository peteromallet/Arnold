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

from dataclasses import dataclass, field
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
#:     A builder exists for parity, but handler integration is deferred to
#:     a follow-up sprint.  Current handler behavior is preserved unchanged.
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

    Kept separate from :class:`~arnold.pipelines.megaplan.step_contracts.StepContract`
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

    #: Human-readable note explaining why the mode was chosen or why
    #: integration is deferred.  Used by parity tests.
    note: str = ""


# ---------------------------------------------------------------------------
# Registry storage
# ---------------------------------------------------------------------------

#: Central registry mapping phase identity → TemplateRegistration.
#: Populated by T2; every enforced model-generated structured contract has an entry.
_TEMPLATE_REGISTRY: dict[str, TemplateRegistration] = {}

# ---------------------------------------------------------------------------
# Auto-register all 17 phases on import
# ---------------------------------------------------------------------------
# NOTE: Builders are None for now (added in T3).  The registry is populated
# eagerly so parity tests can validate coverage immediately.

for _reg in [
    # ── file_fill: structured JSON phases (builders added in T3) ──────────
    TemplateRegistration(
        phase_identity="finalize",
        mode="file_fill",
        scratch_filename="finalize_output.json",
        builder=None,
        note="Builder added in T3; handler promotion wired in T8.",
    ),
    TemplateRegistration(
        phase_identity="critique",
        mode="file_fill",
        scratch_filename="critique_output.json",
        builder=None,
        note="Builder added in T3; handler migration in T11.",
    ),
    TemplateRegistration(
        phase_identity="review",
        mode="file_fill",
        scratch_filename="review_output.json",
        builder=None,
        note="Builder added in T3; handler migration in T11.",
    ),
    TemplateRegistration(
        phase_identity="gate",
        mode="file_fill",
        scratch_filename="gate_output.json",
        builder=None,
        note="Builder added in T3; handler wiring in T10 (includes reprompt semantics).",
    ),
    TemplateRegistration(
        phase_identity="critique_evaluator",
        mode="file_fill",
        scratch_filename="critique_evaluator_output.json",
        builder=None,
        note="Builder added in T3; handler wiring in T9.",
    ),
    # ── batch_assembly: execute assembles from batch outputs ──────────────
    TemplateRegistration(
        phase_identity="execute",
        mode="batch_assembly",
        scratch_filename="execute_output.json",
        builder=None,
        note="Execute output is assembled from multiple batch outputs. "
        "A builder exists for parity/documentation but handlers do not "
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
