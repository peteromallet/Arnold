"""Authoritative StepContract registry — single source of truth for all 17 phase identities.

Every megaplan phase identity is registered here with the 9 canonical fields
that were previously scattered across four legacy literals in three files. Factory
helpers produce byte-identical dicts so the cut-over in downstream tasks is a
single-line replacement.

``CompatibilityMode`` is defined in this module (canonical home post-M4 deletion
of ``_compatibility.py``).
``PREMIUM_AGENT`` is imported from ``.types``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, Mapping, TYPE_CHECKING

from arnold.execution.step_invocation import StepInvocation
from arnold_pipelines.megaplan.types import PREMIUM_AGENT


class CompatibilityMode(str, Enum):
    """Whether a step still relies on legacy compatibility repair.

    Canonically defined here (post-M4) after ``_compatibility.py`` was deleted.
    """

    NATIVE = "native"
    LEGACY = "legacy"

if TYPE_CHECKING:
    from arnold_pipelines.megaplan.template_registry import (
        TemplateBuilder,
        TemplateRegistration,
    )

# ---------------------------------------------------------------------------
# Core dataclass
# ---------------------------------------------------------------------------

OutputKind = Literal["produce", "judge", "decide", "subloop"]


@dataclass(frozen=True)
class StepContract:
    """Canonical contract for a single megaplan phase identity.

    All 9 fields are frozen and immutable. The registry below seeds every
    field from the legacy maps so that factory helpers produce byte-identical
    results to the original literals.
    """

    phase_identity: str
    schema_key: str
    capture_schema_key: str
    output_kind: OutputKind
    compatibility_mode: CompatibilityMode = CompatibilityMode.NATIVE
    normalizer: str | None = None
    default_routing: str | None = None
    prompt_key: str | None = None
    slot: str | None = None

    # ------------------------------------------------------------------
    # Template registry helpers
    # ------------------------------------------------------------------

    @property
    def template_registration(self) -> TemplateRegistration | None:
        """Return the :class:`TemplateRegistration` for this contract, or ``None``."""
        from arnold_pipelines.megaplan.template_registry import get_template_registration

        return get_template_registration(self.phase_identity)

    @property
    def template_builder(self) -> TemplateBuilder | None:
        """Return the :data:`TemplateBuilder` for this contract, or ``None``."""
        from arnold_pipelines.megaplan.template_registry import get_template_builder

        return get_template_builder(self.phase_identity)


# ---------------------------------------------------------------------------
# Registry — all 17 phase identities
# ---------------------------------------------------------------------------

STEP_CONTRACTS: dict[str, StepContract] = {
    # ── Primary stages ──────────────────────────────────────────────────
    "execute": StepContract(
        phase_identity="execute",
        schema_key="execution.json",
        capture_schema_key="execution_batch_relaxed.json",
        output_kind="produce",
        compatibility_mode=CompatibilityMode.NATIVE,
        default_routing=PREMIUM_AGENT,
        prompt_key="execute",
        slot="execute",
    ),
    "finalize": StepContract(
        phase_identity="finalize",
        schema_key="finalize_capture.json",
        capture_schema_key="finalize_capture.json",
        output_kind="produce",
        compatibility_mode=CompatibilityMode.NATIVE,
        default_routing=PREMIUM_AGENT,
        prompt_key="finalize",
        slot="finalize",
    ),
    "critique": StepContract(
        phase_identity="critique",
        schema_key="critique.json",
        capture_schema_key="critique.json",
        output_kind="judge",
        compatibility_mode=CompatibilityMode.NATIVE,
        default_routing=PREMIUM_AGENT,
        prompt_key="critique",
        slot="critique",
    ),
    "review": StepContract(
        phase_identity="review",
        schema_key="review.json",
        capture_schema_key="review.json",
        output_kind="judge",
        compatibility_mode=CompatibilityMode.NATIVE,
        default_routing=PREMIUM_AGENT,
        prompt_key="review",
        slot="review",
    ),
    "gate": StepContract(
        phase_identity="gate",
        schema_key="gate.json",
        capture_schema_key="gate.json",
        output_kind="decide",
        compatibility_mode=CompatibilityMode.NATIVE,
        default_routing=PREMIUM_AGENT,
        prompt_key="gate",
        slot="gate",
    ),
    "plan": StepContract(
        phase_identity="plan",
        schema_key="plan.json",
        capture_schema_key="plan.json",
        output_kind="produce",
        compatibility_mode=CompatibilityMode.NATIVE,
        default_routing=PREMIUM_AGENT,
        prompt_key="plan",
        slot="plan",
    ),
    "prep": StepContract(
        phase_identity="prep",
        schema_key="prep.json",
        capture_schema_key="prep.json",
        output_kind="produce",
        compatibility_mode=CompatibilityMode.NATIVE,
        default_routing="hermes",
        prompt_key="prep",
        slot="prep",
    ),
    "critique_evaluator": StepContract(
        phase_identity="critique_evaluator",
        schema_key="critique_evaluator.json",
        capture_schema_key="critique_evaluator.json",
        output_kind="produce",
        compatibility_mode=CompatibilityMode.NATIVE,
        default_routing=PREMIUM_AGENT,
        prompt_key="critique_evaluator",
        slot="critique_evaluator",
    ),
    "revise": StepContract(
        phase_identity="revise",
        schema_key="revise.json",
        capture_schema_key="revise.json",
        output_kind="produce",
        compatibility_mode=CompatibilityMode.NATIVE,
        default_routing=PREMIUM_AGENT,
        prompt_key="revise",
        slot="revise",
    ),
    # ── Prep sub-steps (normalize to 'prep', no default routing) ─────────
    "prep-triage": StepContract(
        phase_identity="prep-triage",
        schema_key="prep_triage.json",
        capture_schema_key="prep_triage.json",
        output_kind="produce",
        compatibility_mode=CompatibilityMode.NATIVE,
        normalizer="prep",
        default_routing=None,
        prompt_key="prep-triage",
        slot="prep-triage",
    ),
    "prep-distill": StepContract(
        phase_identity="prep-distill",
        schema_key="prep.json",
        capture_schema_key="prep.json",
        output_kind="produce",
        compatibility_mode=CompatibilityMode.NATIVE,
        normalizer="prep",
        default_routing=None,
        prompt_key="prep-distill",
        slot="prep-distill",
    ),
    "prep-research": StepContract(
        phase_identity="prep-research",
        schema_key="prep_research_finding.json",
        capture_schema_key="prep_research_finding.json",
        output_kind="produce",
        compatibility_mode=CompatibilityMode.NATIVE,
        normalizer="prep",
        default_routing=None,
        prompt_key="prep-research",
        slot="prep-research",
    ),
    # ── Feedback ────────────────────────────────────────────────────────
    "feedback": StepContract(
        phase_identity="feedback",
        schema_key="feedback.json",
        capture_schema_key="feedback.json",
        output_kind="produce",
        compatibility_mode=CompatibilityMode.NATIVE,
        default_routing=f"{PREMIUM_AGENT}:low",
        prompt_key="feedback",
        slot="feedback",
    ),
    # ── Loop variants ───────────────────────────────────────────────────
    "loop_plan": StepContract(
        phase_identity="loop_plan",
        schema_key="loop_plan.json",
        capture_schema_key="loop_plan.json",
        output_kind="produce",
        compatibility_mode=CompatibilityMode.NATIVE,
        normalizer="plan",
        default_routing=PREMIUM_AGENT,
        prompt_key="plan",
        slot="loop_plan",
    ),
    "loop_execute": StepContract(
        phase_identity="loop_execute",
        schema_key="loop_execute.json",
        capture_schema_key="loop_execute.json",
        output_kind="produce",
        compatibility_mode=CompatibilityMode.NATIVE,
        normalizer="execute",
        default_routing=PREMIUM_AGENT,
        prompt_key="execute",
        slot="loop_execute",
    ),
    # ── Tiebreaker subloop ──────────────────────────────────────────────
    "tiebreaker_researcher": StepContract(
        phase_identity="tiebreaker_researcher",
        schema_key="tiebreaker_researcher.json",
        capture_schema_key="tiebreaker_researcher.json",
        output_kind="subloop",
        compatibility_mode=CompatibilityMode.NATIVE,
        default_routing=PREMIUM_AGENT,
        prompt_key=None,
        slot="tiebreaker_researcher",
    ),
    "tiebreaker_challenger": StepContract(
        phase_identity="tiebreaker_challenger",
        schema_key="tiebreaker_challenger.json",
        capture_schema_key="tiebreaker_challenger.json",
        output_kind="subloop",
        compatibility_mode=CompatibilityMode.NATIVE,
        default_routing=PREMIUM_AGENT,
        prompt_key=None,
        slot="tiebreaker_challenger",
    ),
}


# ---------------------------------------------------------------------------
# Factory helpers — produce byte-identical dicts to legacy counterparts
# ---------------------------------------------------------------------------


def build_step_schema_filenames() -> dict[str, str]:
    """Return a dict keyed by phase_identity mapping to schema_key.

    Byte-identical to ``STEP_SCHEMA_FILENAMES`` at ``workers/_impl.py:93``.
    """
    return {c.phase_identity: c.schema_key for c in STEP_CONTRACTS.values()}


def build_default_agent_routing() -> dict[str, str]:
    """Return a dict keyed by phase_identity mapping to default_routing.

    Prep sub-steps (``default_routing is None``) are skipped so the result
    matches the 14-key legacy ``DEFAULT_AGENT_ROUTING`` exactly.
    """
    return {
        c.phase_identity: c.default_routing
        for c in STEP_CONTRACTS.values()
        if c.default_routing is not None
    }


def build_capture_schema_keys_by_step() -> dict[str, str]:
    """Return a dict keyed by phase_identity mapping to capture_schema_key.

    Byte-identical to ``_CAPTURE_SCHEMA_KEYS_BY_STEP`` at ``model_seam.py:1598``.
    """
    return {c.phase_identity: c.capture_schema_key for c in STEP_CONTRACTS.values()}


def build_compatibility_mode_by_step() -> dict[str, CompatibilityMode]:
    """Return a dict keyed by phase_identity mapping to compatibility_mode.

    Byte-identical to ``_COMPATIBILITY_MODE_BY_STEP`` at ``model_seam.py:1618``.
    """
    return {c.phase_identity: c.compatibility_mode for c in STEP_CONTRACTS.values()}


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------


def contract_to_invocation(
    contract: StepContract,
    *,
    validation_step: str | None = None,
    extra_metadata: Mapping[str, Any] | None = None,
) -> StepInvocation:
    """Build a minimal ``StepInvocation`` from a contract.

    Emits only the legacy ``{'compatibility_validation_step': …}`` shape
    so the result is byte-identical to the ad-hoc construction at
    ``model_seam.py:1544``.  Enriched metadata is future work (SD2).
    """
    step = validation_step if validation_step is not None else contract.phase_identity
    metadata: dict[str, Any] = {"compatibility_validation_step": step}
    if extra_metadata:
        metadata.update(extra_metadata)
    return StepInvocation(kind="model", metadata=metadata)
