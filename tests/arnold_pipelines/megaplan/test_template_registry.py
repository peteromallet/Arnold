"""Tests for TemplateRegistration boundary template bindings and compatibility metadata.

Covers:
- boundary_template_id, boundary_template_version, boundary_contract_ids,
  and compatibility fields on TemplateRegistration instances.
- gate and finalize registrations reference the correct reusable boundary
  templates with appropriate contract_ids and compatibility classification.
- Legacy registrations preserve their defaults (no boundary fields set).
- Mode semantics are preserved.
"""

from __future__ import annotations

import pytest

from arnold.workflow.boundary_evidence import TemplateCompatibility
from arnold_pipelines.megaplan.template_registry import (
    TemplateRegistration,
    get_phases_by_mode,
    get_registered_phases,
    get_template_registration,
    is_registered,
)
from arnold_pipelines.megaplan.workflows.boundary_contracts import (
    TYPED_BOUNDARY_TEMPLATES_BY_ID,
)


# ---------------------------------------------------------------------------
# TemplateRegistration boundary field defaults
# ---------------------------------------------------------------------------


class TestTemplateRegistrationBoundaryDefaults:
    """Legacy registrations should have None/empty boundary fields."""

    def test_default_boundary_template_id_is_none(self) -> None:
        reg = TemplateRegistration(
            phase_identity="test_phase",
            mode="file_fill",
            scratch_filename="test.json",
        )
        assert reg.boundary_template_id is None

    def test_default_boundary_template_version_is_none(self) -> None:
        reg = TemplateRegistration(
            phase_identity="test_phase",
            mode="file_fill",
            scratch_filename="test.json",
        )
        assert reg.boundary_template_version is None

    def test_default_boundary_contract_ids_is_empty_tuple(self) -> None:
        reg = TemplateRegistration(
            phase_identity="test_phase",
            mode="file_fill",
            scratch_filename="test.json",
        )
        assert reg.boundary_contract_ids == ()

    def test_default_compatibility_is_none(self) -> None:
        reg = TemplateRegistration(
            phase_identity="test_phase",
            mode="file_fill",
            scratch_filename="test.json",
        )
        assert reg.compatibility is None

    def test_immutable_boundary_fields(self) -> None:
        reg = TemplateRegistration(
            phase_identity="test_phase",
            mode="file_fill",
            scratch_filename="test.json",
            boundary_template_id="template.test",
        )
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            reg.boundary_template_id = "template.other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Gate registration boundary template binding
# ---------------------------------------------------------------------------


class TestGateRegistrationBoundaryBinding:
    """Gate registration uses template.validation_boundary (ValidationBoundary)."""

    def test_gate_is_registered(self) -> None:
        assert is_registered("gate")

    def test_gate_has_boundary_template_id(self) -> None:
        reg = get_template_registration("gate")
        assert reg is not None
        assert reg.boundary_template_id == "template.validation_boundary"

    def test_gate_boundary_template_version_is_1_0(self) -> None:
        reg = get_template_registration("gate")
        assert reg is not None
        assert reg.boundary_template_version == "1.0"

    def test_gate_boundary_contract_ids_include_gate_to_revise(self) -> None:
        reg = get_template_registration("gate")
        assert reg is not None
        assert "gate_to_revise" in reg.boundary_contract_ids

    def test_gate_compatibility_is_compatible_extension(self) -> None:
        reg = get_template_registration("gate")
        assert reg is not None
        assert reg.compatibility == "compatible_extension"

    def test_gate_boundary_template_id_points_to_valid_template(self) -> None:
        reg = get_template_registration("gate")
        assert reg is not None
        assert reg.boundary_template_id is not None
        assert reg.boundary_template_id in TYPED_BOUNDARY_TEMPLATES_BY_ID

    def test_gate_boundary_template_is_validation_boundary_type(self) -> None:
        reg = get_template_registration("gate")
        assert reg is not None
        template = TYPED_BOUNDARY_TEMPLATES_BY_ID.get(reg.boundary_template_id or "")
        assert template is not None
        assert template.boundary_id == "template.validation_boundary"

    def test_gate_mode_is_file_fill(self) -> None:
        reg = get_template_registration("gate")
        assert reg is not None
        assert reg.mode == "file_fill"


# ---------------------------------------------------------------------------
# Finalize registration boundary template binding
# ---------------------------------------------------------------------------


class TestFinalizeRegistrationBoundaryBinding:
    """Finalize registration uses template.artifact_promotion."""

    def test_finalize_is_registered(self) -> None:
        assert is_registered("finalize")

    def test_finalize_has_boundary_template_id(self) -> None:
        reg = get_template_registration("finalize")
        assert reg is not None
        assert reg.boundary_template_id == "template.artifact_promotion"

    def test_finalize_boundary_template_version_is_1_0(self) -> None:
        reg = get_template_registration("finalize")
        assert reg is not None
        assert reg.boundary_template_version == "1.0"

    def test_finalize_boundary_contract_ids_include_both_artifact_and_fallback(self) -> None:
        reg = get_template_registration("finalize")
        assert reg is not None
        assert "finalize_artifacts" in reg.boundary_contract_ids
        assert "finalize_fallback" in reg.boundary_contract_ids

    def test_finalize_compatibility_is_compatible_extension(self) -> None:
        reg = get_template_registration("finalize")
        assert reg is not None
        assert reg.compatibility == "compatible_extension"

    def test_finalize_boundary_template_id_points_to_valid_template(self) -> None:
        reg = get_template_registration("finalize")
        assert reg is not None
        assert reg.boundary_template_id is not None
        assert reg.boundary_template_id in TYPED_BOUNDARY_TEMPLATES_BY_ID

    def test_finalize_boundary_template_is_artifact_promotion_type(self) -> None:
        reg = get_template_registration("finalize")
        assert reg is not None
        template = TYPED_BOUNDARY_TEMPLATES_BY_ID.get(reg.boundary_template_id or "")
        assert template is not None
        assert template.boundary_id == "template.artifact_promotion"

    def test_finalize_mode_is_file_fill(self) -> None:
        reg = get_template_registration("finalize")
        assert reg is not None
        assert reg.mode == "file_fill"


# ---------------------------------------------------------------------------
# Legacy registrations (no boundary fields)
# ---------------------------------------------------------------------------


class TestLegacyRegistrationNoBoundaryFields:
    """Phases that were not updated with boundary bindings keep defaults."""

    def test_critique_has_no_boundary_template_id(self) -> None:
        reg = get_template_registration("critique")
        assert reg is not None
        assert reg.boundary_template_id is None

    def test_critique_has_empty_boundary_contract_ids(self) -> None:
        reg = get_template_registration("critique")
        assert reg is not None
        assert reg.boundary_contract_ids == ()

    def test_review_has_no_boundary_template_id(self) -> None:
        reg = get_template_registration("review")
        assert reg is not None
        assert reg.boundary_template_id is None

    def test_plan_has_no_boundary_template_id(self) -> None:
        reg = get_template_registration("plan")
        assert reg is not None
        assert reg.boundary_template_id is None

    def test_execute_has_no_boundary_template_id(self) -> None:
        reg = get_template_registration("execute")
        assert reg is not None
        assert reg.boundary_template_id is None

    def test_prep_has_no_boundary_template_id(self) -> None:
        reg = get_template_registration("prep")
        assert reg is not None
        assert reg.boundary_template_id is None


# ---------------------------------------------------------------------------
# Compatibility metadata consistency
# ---------------------------------------------------------------------------


class TestCompatibilityMetadataConsistency:
    """Compatibility strings on registrations match TemplateCompatibility enum values."""

    _VALID_COMPAT_VALUES = frozenset(e.value for e in TemplateCompatibility)

    def test_gate_compatibility_is_valid_enum_value(self) -> None:
        reg = get_template_registration("gate")
        assert reg is not None
        assert reg.compatibility in self._VALID_COMPAT_VALUES

    def test_finalize_compatibility_is_valid_enum_value(self) -> None:
        reg = get_template_registration("finalize")
        assert reg is not None
        assert reg.compatibility in self._VALID_COMPAT_VALUES

    def test_gate_and_finalize_have_same_compatibility(self) -> None:
        gate_reg = get_template_registration("gate")
        finalize_reg = get_template_registration("finalize")
        assert gate_reg is not None
        assert finalize_reg is not None
        assert gate_reg.compatibility == finalize_reg.compatibility

    def test_boundary_template_ids_are_different_for_gate_and_finalize(self) -> None:
        gate_reg = get_template_registration("gate")
        finalize_reg = get_template_registration("finalize")
        assert gate_reg is not None
        assert finalize_reg is not None
        assert gate_reg.boundary_template_id != finalize_reg.boundary_template_id


# ---------------------------------------------------------------------------
# Registry mode semantics preserved
# ---------------------------------------------------------------------------


class TestRegistryModeSemantics:
    """All registrations maintain correct mode assignments."""

    def test_file_fill_phases_are_all_eligible(self) -> None:
        file_fill_phases = get_phases_by_mode("file_fill")
        assert "finalize" in file_fill_phases
        assert "gate" in file_fill_phases
        assert "critique" in file_fill_phases
        assert "review" in file_fill_phases
        assert "critique_evaluator" in file_fill_phases

    def test_batch_assembly_phases(self) -> None:
        batch_phases = get_phases_by_mode("batch_assembly")
        assert "execute" in batch_phases
        assert len(batch_phases) == 1

    def test_markdown_exempt_phases(self) -> None:
        md_phases = get_phases_by_mode("markdown_exempt")
        assert "plan" in md_phases
        assert "revise" in md_phases

    def test_deferred_phases_include_prep_variants(self) -> None:
        deferred = get_phases_by_mode("deferred")
        assert "prep" in deferred
        assert "prep-triage" in deferred
        assert "feedback" in deferred

    def test_all_17_phases_registered(self) -> None:
        all_phases = get_registered_phases()
        assert len(all_phases) == 17

    def test_boundary_bound_phases_stay_file_fill(self) -> None:
        """Gate and finalize remain file_fill despite boundary bindings."""
        gate_reg = get_template_registration("gate")
        finalize_reg = get_template_registration("finalize")
        assert gate_reg is not None
        assert finalize_reg is not None
        assert gate_reg.mode == "file_fill"
        assert finalize_reg.mode == "file_fill"


# ---------------------------------------------------------------------------
# Boundary template ↔ registration cross-reference
# ---------------------------------------------------------------------------


class TestBoundaryTemplateCrossReference:
    """Registrations' boundary_template_ids resolve to actual templates."""

    def test_gate_template_has_required_artifacts(self) -> None:
        reg = get_template_registration("gate")
        assert reg is not None
        template = TYPED_BOUNDARY_TEMPLATES_BY_ID.get(reg.boundary_template_id or "")
        assert template is not None
        assert hasattr(template, "required_artifacts")

    def test_finalize_template_has_required_artifacts(self) -> None:
        reg = get_template_registration("finalize")
        assert reg is not None
        template = TYPED_BOUNDARY_TEMPLATES_BY_ID.get(reg.boundary_template_id or "")
        assert template is not None
        assert hasattr(template, "required_artifacts")

    def test_gate_template_workflow_id_matches(self) -> None:
        reg = get_template_registration("gate")
        assert reg is not None
        template = TYPED_BOUNDARY_TEMPLATES_BY_ID.get(reg.boundary_template_id or "")
        assert template is not None
        assert template.workflow_id == "megaplan-review"

    def test_finalize_template_workflow_id_matches(self) -> None:
        reg = get_template_registration("finalize")
        assert reg is not None
        template = TYPED_BOUNDARY_TEMPLATES_BY_ID.get(reg.boundary_template_id or "")
        assert template is not None
        assert template.workflow_id == "megaplan-review"

    def test_gate_contract_ids_only_gate_to_revise(self) -> None:
        reg = get_template_registration("gate")
        assert reg is not None
        assert reg.boundary_contract_ids == ("gate_to_revise",)

    def test_finalize_contract_ids_both_artifacts_and_fallback(self) -> None:
        reg = get_template_registration("finalize")
        assert reg is not None
        assert set(reg.boundary_contract_ids) == {"finalize_artifacts", "finalize_fallback"}
