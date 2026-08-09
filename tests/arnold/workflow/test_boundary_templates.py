"""Tests for Megaplan-neutral boundary template profiles and selection helpers.

Covers :mod:`arnold.workflow.boundary_templates` — template instances,
required-field profiles, selection helpers, conformance checking, and
boundary-kind classification.  All tests use only
:class:`BoundaryContract` primitives and must never import from
``arnold_pipelines.megaplan``.
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from arnold.workflow.boundary_evidence import (
    BoundaryContract,
    BoundaryPhase,
    TemplateCompatibility,
)
from arnold.workflow.boundary_templates import (
    DEFAULT_WBC_INVENTORY_PATH,
    InventoryRowAssessment,
    InventoryRowCompleteness,
    TEMPLATES_BY_KIND,
    REQUIRED_FIELDS_BY_KIND,
    REQUIRED_FIELDS_APPROVAL_BOUNDARY,
    REQUIRED_FIELDS_ARTIFACT_HANDOFF_BOUNDARY,
    REQUIRED_FIELDS_ARTIFACT_PROMOTION,
    REQUIRED_FIELDS_EXECUTION_CUSTODY,
    REQUIRED_FIELDS_EXTERNAL_EFFECT,
    REQUIRED_FIELDS_EXTERNAL_WITNESS,
    REQUIRED_FIELDS_GRAPH_JOIN_FANOUT,
    REQUIRED_FIELDS_HUMAN_APPROVAL_WAIVER,
    REQUIRED_FIELDS_REVISION_BOUNDARY,
    REQUIRED_FIELDS_VALIDATION_BOUNDARY,
    BoundaryTemplateKind,
    TemplateSelection,
    TemplateVersionPin,
    WbcInventoryInvariant,
    assess_inventory_rows,
    check_contract_conformance,
    check_template_upgrade,
    classify_boundary_kind,
    deliberate_upgrade_template,
    get_required_fields,
    get_template,
    list_template_kinds,
    load_wbc_boundary_inventory,
    select_inventory_rows,
    pin_template_version,
    select_template,
)


# ── Importability and stability ───────────────────────────────────────────


def test_module_importable_with_all_public_symbols() -> None:
    """All public symbols must be importable from boundary_templates."""
    assert BoundaryTemplateKind.REVISION_BOUNDARY == "revision_boundary"
    assert BoundaryTemplateKind.VALIDATION_BOUNDARY == "validation_boundary"
    assert BoundaryTemplateKind.ARTIFACT_HANDOFF_BOUNDARY == "artifact_handoff_boundary"
    assert BoundaryTemplateKind.ARTIFACT_PROMOTION == "artifact_promotion"
    assert BoundaryTemplateKind.APPROVAL_BOUNDARY == "approval_boundary"
    assert BoundaryTemplateKind.HUMAN_APPROVAL_WAIVER == "human_approval_waiver"
    assert BoundaryTemplateKind.EXTERNAL_EFFECT == "external_effect"
    assert BoundaryTemplateKind.EXECUTION_CUSTODY == "execution_custody"
    assert BoundaryTemplateKind.GRAPH_JOIN_FANOUT == "graph_join_fanout"
    assert BoundaryTemplateKind.EXTERNAL_WITNESS == "external_witness"
    assert WbcInventoryInvariant.START_BEFORE_DISPATCH == "start_before_dispatch"
    assert InventoryRowCompleteness.COMPLETE == "complete"
    assert DEFAULT_WBC_INVENTORY_PATH.name == "wbc-boundary-inventory.json"


def test_no_megaplan_imports_in_module_source() -> None:
    """The boundary_templates module must not import from arnold_pipelines.megaplan."""
    import arnold.workflow.boundary_templates as mod

    source_path = mod.__file__
    assert source_path is not None
    with open(source_path) as fh:
        source = fh.read()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = ""
            if isinstance(node, ast.ImportFrom) and node.module:
                module_name = node.module
            for alias in getattr(node, "names", []):
                full = f"{module_name}.{alias.name}" if module_name else alias.name
                assert "megaplan" not in full.lower(), (
                    f"Megaplan import found in boundary_templates: {full}"
                )


# ── BoundaryTemplateKind ──────────────────────────────────────────────────


def test_template_kind_is_str_enum() -> None:
    """BoundaryTemplateKind is a StrEnum with exactly 10 members."""
    members = list(BoundaryTemplateKind)
    assert len(members) == 10
    for m in members:
        assert isinstance(m, BoundaryTemplateKind)
        assert isinstance(m.value, str)
        assert m.value == str(m)


def test_template_kind_from_string() -> None:
    """BoundaryTemplateKind can be constructed from its string value."""
    assert BoundaryTemplateKind("revision_boundary") is BoundaryTemplateKind.REVISION_BOUNDARY
    assert BoundaryTemplateKind("validation_boundary") is BoundaryTemplateKind.VALIDATION_BOUNDARY


def test_template_kind_invalid_raises() -> None:
    """Constructing BoundaryTemplateKind with an unknown value raises ValueError."""
    with pytest.raises(ValueError):
        BoundaryTemplateKind("nonexistent_kind")


# ── Required-field profiles ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "name, profile",
    [
        ("revision_boundary", REQUIRED_FIELDS_REVISION_BOUNDARY),
        ("validation_boundary", REQUIRED_FIELDS_VALIDATION_BOUNDARY),
        ("artifact_handoff_boundary", REQUIRED_FIELDS_ARTIFACT_HANDOFF_BOUNDARY),
        ("artifact_promotion", REQUIRED_FIELDS_ARTIFACT_PROMOTION),
        ("approval_boundary", REQUIRED_FIELDS_APPROVAL_BOUNDARY),
        ("human_approval_waiver", REQUIRED_FIELDS_HUMAN_APPROVAL_WAIVER),
        ("external_effect", REQUIRED_FIELDS_EXTERNAL_EFFECT),
        ("execution_custody", REQUIRED_FIELDS_EXECUTION_CUSTODY),
        ("graph_join_fanout", REQUIRED_FIELDS_GRAPH_JOIN_FANOUT),
        ("external_witness", REQUIRED_FIELDS_EXTERNAL_WITNESS),
    ],
)
def test_required_fields_profile_is_frozenset(name: str, profile: frozenset[str]) -> None:
    """Every required-field profile is a non-empty frozenset of strings."""
    assert isinstance(profile, frozenset), f"{name} profile is not a frozenset"
    assert len(profile) > 0, f"{name} profile is empty"
    for fld in profile:
        assert isinstance(fld, str), f"{name} profile contains non-string: {fld!r}"
    assert "boundary_id" in profile, f"{name} missing boundary_id"
    assert "workflow_id" in profile, f"{name} missing workflow_id"
    assert "row_id" in profile, f"{name} missing row_id"


def test_required_fields_by_kind_covers_all_kinds() -> None:
    """REQUIRED_FIELDS_BY_KIND must have an entry for every BoundaryTemplateKind."""
    for kind in BoundaryTemplateKind:
        assert kind in REQUIRED_FIELDS_BY_KIND, f"Missing profile for {kind}"
        profile = REQUIRED_FIELDS_BY_KIND[kind]
        assert isinstance(profile, frozenset)
        assert len(profile) > 0


def test_required_fields_by_kind_no_extra_keys() -> None:
    """REQUIRED_FIELDS_BY_KIND must not contain extra keys beyond BoundaryTemplateKind."""
    for key in REQUIRED_FIELDS_BY_KIND:
        assert key in BoundaryTemplateKind, f"Extra key in registry: {key}"


# ── Template instances ───────────────────────────────────────────────────


def test_templates_by_kind_covers_all_kinds() -> None:
    """TEMPLATES_BY_KIND must have an entry for every BoundaryTemplateKind."""
    for kind in BoundaryTemplateKind:
        assert kind in TEMPLATES_BY_KIND, f"Missing template for {kind}"
        template = TEMPLATES_BY_KIND[kind]
        assert isinstance(template, BoundaryContract)


def test_templates_by_kind_no_extra_keys() -> None:
    """TEMPLATES_BY_KIND must not contain extra keys beyond BoundaryTemplateKind."""
    for key in TEMPLATES_BY_KIND:
        assert key in BoundaryTemplateKind, f"Extra key in template registry: {key}"


def test_templates_are_immutable() -> None:
    """Template instances must be frozen (FrozenInstanceError on mutation)."""
    template = TEMPLATES_BY_KIND[BoundaryTemplateKind.REVISION_BOUNDARY]
    with pytest.raises(FrozenInstanceError):
        template.boundary_id = "mutated"  # type: ignore[misc]


def test_templates_use_neutral_workflow_id() -> None:
    """Canonical templates use neutral 'arnold.workflow' workflow_id, not megaplan."""
    for kind, template in TEMPLATES_BY_KIND.items():
        assert template.workflow_id == "arnold.workflow", (
            f"{kind} template has non-neutral workflow_id: {template.workflow_id}"
        )


def test_template_boundary_ids_are_descriptive() -> None:
    """Each template's boundary_id starts with 'template.' and reflects its kind."""
    for kind, template in TEMPLATES_BY_KIND.items():
        assert template.boundary_id.startswith("template."), (
            f"{kind} boundary_id missing 'template.' prefix: {template.boundary_id}"
        )
        assert kind.value in template.boundary_id, (
            f"{kind} boundary_id does not contain kind: {template.boundary_id}"
        )


# ── get_template ─────────────────────────────────────────────────────────


def test_get_template_returns_frozen_contract() -> None:
    """get_template returns a BoundaryContract for each valid kind."""
    for kind in BoundaryTemplateKind:
        tmpl = get_template(kind)
        assert isinstance(tmpl, BoundaryContract)
        assert tmpl.boundary_id.startswith("template.")


def test_get_template_by_string() -> None:
    """get_template accepts string kind values."""
    tmpl = get_template("revision_boundary")
    assert tmpl is get_template(BoundaryTemplateKind.REVISION_BOUNDARY)


def test_get_template_invalid_kind_raises() -> None:
    """get_template raises ValueError/KeyError for unknown kinds."""
    with pytest.raises((ValueError, KeyError)):
        get_template("no_such_kind")


# ── get_required_fields ─────────────────────────────────────────────────


def test_get_required_fields_returns_frozenset() -> None:
    """get_required_fields returns the correct frozenset for each kind."""
    for kind in BoundaryTemplateKind:
        fields = get_required_fields(kind)
        assert isinstance(fields, frozenset)
        assert fields is REQUIRED_FIELDS_BY_KIND[kind]


def test_get_required_fields_by_string() -> None:
    """get_required_fields accepts string kind values."""
    fields = get_required_fields("revision_boundary")
    assert fields is REQUIRED_FIELDS_REVISION_BOUNDARY


def test_get_required_fields_invalid_kind_raises() -> None:
    """get_required_fields raises for unknown kinds."""
    with pytest.raises((ValueError, KeyError)):
        get_required_fields("no_such_kind")


# ── list_template_kinds ──────────────────────────────────────────────────


def test_list_template_kinds_returns_all() -> None:
    """list_template_kinds returns all 10 kinds as a tuple."""
    kinds = list_template_kinds()
    assert isinstance(kinds, tuple)
    assert len(kinds) == 10
    assert set(kinds) == set(BoundaryTemplateKind)


def test_list_template_kinds_stable_order() -> None:
    """list_template_kinds returns the same order on successive calls."""
    a = list_template_kinds()
    b = list_template_kinds()
    assert a == b


# ── Inventory helpers ────────────────────────────────────────────────────


def test_load_wbc_boundary_inventory_missing_returns_none(tmp_path) -> None:
    """Missing generated inventory is treated as unavailable, not fatal."""
    assert load_wbc_boundary_inventory(tmp_path / "missing.json") is None


def test_select_inventory_rows_matches_boundary_id_and_step_id() -> None:
    """Inventory row selection supports both boundary_id and step_id lookups."""
    inventory = {
        "rows": [
            {"row_kind": "boundary_contract", "boundary_id": "prep_to_plan"},
            {"row_kind": "manifest_entry", "step_id": "megaplan.s2.prep_to_plan"},
        ]
    }
    assert len(select_inventory_rows(inventory, boundary_id="prep_to_plan")) == 1
    assert len(select_inventory_rows(inventory, step_id="megaplan.s2.prep_to_plan")) == 1


def test_assess_inventory_rows_manual_emit_is_incomplete() -> None:
    """Manual-emission inventory rows are incomplete adoption state."""
    assessment = assess_inventory_rows(
        (
            {
                "row_kind": "boundary_contract",
                "boundary_id": "execute_approval",
                "producer_category": "manual_emit",
            },
        )
    )
    assert isinstance(assessment, InventoryRowAssessment)
    assert assessment.completeness == InventoryRowCompleteness.INCOMPLETE
    assert "manual-emission" in assessment.reasons


def test_assess_inventory_rows_support_manifest_only_schema_row_is_incomplete() -> None:
    """Manifest-only schema rows remain incomplete even when labeled supported."""
    assessment = assess_inventory_rows(
        (
            {
                "row_kind": "manifest_entry",
                "step_id": "arnold.workflow.execution_attempt_ledger",
                "producer_path": "arnold/workflow/execution_attempt_ledger.py",
                "support_is_non_authoritative": True,
                "support_status": "supported",
            },
        )
    )
    assert assessment.completeness == InventoryRowCompleteness.INCOMPLETE
    assert "schema-only" in assessment.reasons
    assert "support-manifest-only" in assessment.reasons


def test_assess_inventory_rows_auto_matched_with_proof_is_complete() -> None:
    """Auto-matched rows with proven invariants are complete."""
    assessment = assess_inventory_rows(
        (
            {
                "row_kind": "boundary_contract",
                "boundary_id": "prep_to_plan",
                "producer_category": "auto_matched",
                "inventory_proof": {
                    "start_before_dispatch": True,
                    "exactly_one_terminal": True,
                },
            },
        ),
        required_invariants=[
            WbcInventoryInvariant.START_BEFORE_DISPATCH,
            WbcInventoryInvariant.EXACTLY_ONE_TERMINAL,
        ],
    )
    assert assessment.completeness == InventoryRowCompleteness.COMPLETE
    assert assessment.missing_invariants == ()


def test_assess_inventory_rows_missing_required_invariant_is_reported() -> None:
    """Required invariants fail closed when the inventory proof is absent or false."""
    assessment = assess_inventory_rows(
        (
            {
                "row_kind": "boundary_contract",
                "boundary_id": "prep_to_plan",
                "producer_category": "auto_matched",
                "inventory_proof": {"start_before_dispatch": True},
            },
        ),
        required_invariants=[
            WbcInventoryInvariant.START_BEFORE_DISPATCH,
            WbcInventoryInvariant.POST_TRANSITION_REREAD,
        ],
    )
    assert assessment.completeness == InventoryRowCompleteness.INCOMPLETE
    assert assessment.missing_invariants == (
        WbcInventoryInvariant.POST_TRANSITION_REREAD,
    )


# ── check_contract_conformance ───────────────────────────────────────────


def test_conformance_template_passes_its_own_profile() -> None:
    """Every canonical template must be fully conformant with its own profile."""
    for kind in BoundaryTemplateKind:
        template = get_template(kind)
        missing = check_contract_conformance(template, kind)
        assert missing == (), (
            f"{kind} template is not self-conformant; missing: {missing}"
        )


def test_conformance_missing_boundary_id() -> None:
    """A contract whose details keys are missing should report them."""
    # boundary_id and workflow_id are enforced at construction by BoundaryContract,
    # so test missing fields through details keys instead.
    contract = BoundaryContract(
        boundary_id="test.revision",
        workflow_id="test",
        row_id="r1",
        phase=BoundaryPhase.REVISE,
        required_artifacts=("out.json",),
        expected_state_delta={"stage": "done"},
        # intentionally empty details — missing revision_kind, revision_log_ref
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.REVISION_BOUNDARY)
    assert "details.revision_kind" in missing
    assert "details.revision_log_ref" in missing


def test_conformance_missing_workflow_id() -> None:
    """A contract with None row_id should report it as missing."""
    contract = BoundaryContract(
        boundary_id="test.approval",
        workflow_id="test",
        row_id=None,
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.APPROVAL_BOUNDARY)
    assert "row_id" in missing


def test_conformance_missing_details_key() -> None:
    """A contract missing a required details key should report it."""
    contract = BoundaryContract(
        boundary_id="test.revision",
        workflow_id="test",
        row_id="r1",
        phase=BoundaryPhase.REVISE,
        required_artifacts=("out.json",),
        expected_state_delta={"stage": "done"},
        # missing revision_kind and revision_log_ref
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.REVISION_BOUNDARY)
    assert "details.revision_kind" in missing
    assert "details.revision_log_ref" in missing


def test_conformance_all_missing() -> None:
    """A minimally-populated contract should report many required fields as missing."""
    contract = BoundaryContract(
        boundary_id="test.val",
        workflow_id="test",
        # no row_id, no phase, no required_artifacts, no expected_state_delta, etc.
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.VALIDATION_BOUNDARY)
    # At minimum: row_id, phase, required_artifacts, expected_state_delta, details.validation_kind
    assert len(missing) >= 5


def test_conformance_fully_populated_passes() -> None:
    """A fully populated revision boundary contract passes conformance."""
    contract = BoundaryContract(
        boundary_id="test.revision",
        workflow_id="test",
        row_id="r1",
        phase=BoundaryPhase.REVISE,
        required_artifacts=("revised.json",),
        expected_state_delta={"revised": True},
        phase_result_required=True,
        receipt_required=True,
        authority_required=False,
        details={
            "revision_kind": "revision",
            "revision_log_ref": "log.md",
        },
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.REVISION_BOUNDARY)
    assert missing == ()


def test_conformance_empty_required_artifacts_is_missing() -> None:
    """Empty tuple for required_artifacts counts as missing."""
    contract = BoundaryContract(
        boundary_id="test.external",
        workflow_id="test",
        row_id="r1",
        required_artifacts=(),
        details={"witness_ref": "wr", "witness_kind": "att"},
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.EXTERNAL_WITNESS)
    assert "required_artifacts" in missing


def test_conformance_empty_details_value_is_missing() -> None:
    """An empty string for a required details key counts as missing."""
    contract = BoundaryContract(
        boundary_id="test.external",
        workflow_id="test",
        row_id="r1",
        required_artifacts=("out.json",),
        details={"witness_ref": "", "witness_kind": "att"},
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.EXTERNAL_WITNESS)
    assert "details.witness_ref" in missing


def test_conformance_none_details_value_is_missing() -> None:
    """A None value for a required details key counts as missing."""
    contract = BoundaryContract(
        boundary_id="test.external",
        workflow_id="test",
        row_id="r1",
        required_artifacts=("out.json",),
        details={"witness_ref": None, "witness_kind": "att"},  # type: ignore[dict-item]
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.EXTERNAL_WITNESS)
    assert "details.witness_ref" in missing


def test_conformance_authority_required_false_counts_missing() -> None:
    """When a profile requires authority_required, False is reported as missing."""
    contract = BoundaryContract(
        boundary_id="test.custody",
        workflow_id="test",
        row_id="r1",
        phase=BoundaryPhase.EXECUTE,
        required_artifacts=("out.json",),
        authority_required=False,
        details={"custody_scope": "sc", "fresh_session": True},
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.EXECUTION_CUSTODY)
    # authority_required is True in the profile; False should be missing
    assert "authority_required" in missing


def test_conformance_phase_result_required_false_counts_missing() -> None:
    """When a profile requires phase_result_required, False is reported as missing."""
    contract = BoundaryContract(
        boundary_id="test.promo",
        workflow_id="test",
        row_id="r1",
        required_artifacts=("out.json",),
        expected_state_delta={"stage": "done"},
        phase_result_required=False,
        receipt_required=True,
        details={"effect_id": "e", "artifact_policy_ref": "p", "promotion_kind": "k"},
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.ARTIFACT_PROMOTION)
    assert "phase_result_required" in missing


def test_conformance_receipt_required_false_counts_missing() -> None:
    """When a profile requires receipt_required, False is reported as missing."""
    contract = BoundaryContract(
        boundary_id="test.promo",
        workflow_id="test",
        row_id="r1",
        required_artifacts=("out.json",),
        expected_state_delta={"stage": "done"},
        phase_result_required=True,
        receipt_required=False,
        details={"effect_id": "e", "artifact_policy_ref": "p", "promotion_kind": "k"},
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.ARTIFACT_PROMOTION)
    assert "receipt_required" in missing


def test_conformance_returns_stable_sorted_tuple() -> None:
    """Missing fields are returned as a sorted tuple."""
    contract = BoundaryContract(
        boundary_id="test.val",
        workflow_id="test",
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.VALIDATION_BOUNDARY)
    assert missing == tuple(sorted(missing))


# ── classify_boundary_kind ───────────────────────────────────────────────


def test_classify_revision_by_boundary_id_hint() -> None:
    """A contract with 'revision' in boundary_id classifies as revision."""
    contract = BoundaryContract(
        boundary_id="some.revision.gate",
        workflow_id="test",
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.REVISION_BOUNDARY


def test_classify_validation_by_boundary_id_hint() -> None:
    """A contract with 'validation' in boundary_id classifies as validation."""
    contract = BoundaryContract(
        boundary_id="gate.validation.check",
        workflow_id="test",
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.VALIDATION_BOUNDARY


def test_classify_handoff_by_boundary_id_hint() -> None:
    """A contract with 'handoff' in boundary_id classifies as artifact_handoff."""
    contract = BoundaryContract(
        boundary_id="artifact.handoff",
        workflow_id="test",
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.ARTIFACT_HANDOFF_BOUNDARY


def test_classify_promotion_by_boundary_id_hint() -> None:
    """A contract with 'promotion' in boundary_id classifies as artifact_promotion."""
    contract = BoundaryContract(
        boundary_id="artifact.promotion",
        workflow_id="test",
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.ARTIFACT_PROMOTION


def test_classify_approval_by_boundary_id() -> None:
    """A contract with 'approval' in boundary_id classifies as approval."""
    contract = BoundaryContract(
        boundary_id="human.approval",
        workflow_id="test",
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.APPROVAL_BOUNDARY


def test_classify_waiver_by_boundary_id() -> None:
    """A contract with 'waiver' in boundary_id classifies as human_approval_waiver."""
    contract = BoundaryContract(
        boundary_id="human.waiver",
        workflow_id="test",
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.HUMAN_APPROVAL_WAIVER


def test_classify_external_effect_by_boundary_id() -> None:
    """A contract with 'external_effect' in boundary_id classifies correctly."""
    contract = BoundaryContract(
        boundary_id="some.external_effect",
        workflow_id="test",
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.EXTERNAL_EFFECT


def test_classify_custody_by_boundary_id() -> None:
    """A contract with 'custody' in boundary_id classifies as execution_custody."""
    contract = BoundaryContract(
        boundary_id="execution.custody",
        workflow_id="test",
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.EXECUTION_CUSTODY


def test_classify_join_by_boundary_id() -> None:
    """A contract with 'join' in boundary_id classifies as graph_join_fanout."""
    contract = BoundaryContract(
        boundary_id="graph.join",
        workflow_id="test",
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.GRAPH_JOIN_FANOUT


def test_classify_fanout_by_boundary_id() -> None:
    """A contract with 'fanout' in boundary_id classifies as graph_join_fanout."""
    contract = BoundaryContract(
        boundary_id="fanout.graph",
        workflow_id="test",
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.GRAPH_JOIN_FANOUT


def test_classify_witness_by_boundary_id() -> None:
    """A contract with 'witness' in boundary_id classifies as external_witness."""
    contract = BoundaryContract(
        boundary_id="external.witness.proof",
        workflow_id="test",
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.EXTERNAL_WITNESS


def test_classify_by_details_keys_revision() -> None:
    """Classification falls back to details keys when boundary_id has no hint."""
    contract = BoundaryContract(
        boundary_id="unknown.boundary",
        workflow_id="test",
        details={"revision_kind": "rev", "revision_log_ref": "log.md"},
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.REVISION_BOUNDARY


def test_classify_by_details_keys_validation() -> None:
    """Classification by validation_kind in details."""
    contract = BoundaryContract(
        boundary_id="unknown.boundary",
        workflow_id="test",
        details={"validation_kind": "val"},
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.VALIDATION_BOUNDARY


def test_classify_by_details_keys_handoff() -> None:
    """Classification by handoff_from + handoff_to in details."""
    contract = BoundaryContract(
        boundary_id="unknown.boundary",
        workflow_id="test",
        details={"handoff_from": "A", "handoff_to": "B"},
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.ARTIFACT_HANDOFF_BOUNDARY


def test_classify_by_details_keys_promotion() -> None:
    """Classification by promotion_kind + effect_id in details."""
    contract = BoundaryContract(
        boundary_id="unknown.boundary",
        workflow_id="test",
        details={"promotion_kind": "k", "effect_id": "e"},
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.ARTIFACT_PROMOTION


def test_classify_by_details_keys_waiver() -> None:
    """Classification by suspension_route_id + resume_policy_ref in details."""
    contract = BoundaryContract(
        boundary_id="unknown.boundary",
        workflow_id="test",
        details={"suspension_route_id": "s", "resume_policy_ref": "p"},
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.HUMAN_APPROVAL_WAIVER


def test_classify_by_details_keys_approval_no_waiver() -> None:
    """Classification by approval_scope without suspension route is approval, not waiver."""
    contract = BoundaryContract(
        boundary_id="unknown.boundary",
        workflow_id="test",
        details={"approval_scope": "human:check"},
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.APPROVAL_BOUNDARY


def test_classify_by_details_keys_external_effect() -> None:
    """Classification by effect_kind + effect_id in details."""
    contract = BoundaryContract(
        boundary_id="unknown.boundary",
        workflow_id="test",
        details={"effect_kind": "ext", "effect_id": "e1"},
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.EXTERNAL_EFFECT


def test_classify_by_details_keys_custody() -> None:
    """Classification by custody_scope + fresh_session in details."""
    contract = BoundaryContract(
        boundary_id="unknown.boundary",
        workflow_id="test",
        details={"custody_scope": "c", "fresh_session": True},
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.EXECUTION_CUSTODY


def test_classify_by_details_keys_join_fanout() -> None:
    """Classification by fan_out_refs or fan_in_ref in details."""
    contract = BoundaryContract(
        boundary_id="unknown.boundary",
        workflow_id="test",
        details={"fan_in_ref": "f1"},
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.GRAPH_JOIN_FANOUT


def test_classify_by_details_keys_witness() -> None:
    """Classification by witness_ref + witness_kind in details."""
    contract = BoundaryContract(
        boundary_id="unknown.boundary",
        workflow_id="test",
        details={"witness_ref": "w", "witness_kind": "att"},
    )
    assert classify_boundary_kind(contract) is BoundaryTemplateKind.EXTERNAL_WITNESS


def test_classify_none_for_unrecognized() -> None:
    """An unrecognized contract returns None."""
    contract = BoundaryContract(
        boundary_id="something.entirely.different",
        workflow_id="test",
    )
    assert classify_boundary_kind(contract) is None


def test_classify_none_for_empty_details() -> None:
    """A contract with no recognizable boundary_id and empty details returns None."""
    contract = BoundaryContract(
        boundary_id="no_match_here",
        workflow_id="test",
    )
    assert classify_boundary_kind(contract) is None


# ── select_template ──────────────────────────────────────────────────────


def test_select_template_returns_canonical_without_overrides() -> None:
    """select_template returns the canonical template when no overrides given."""
    for kind in BoundaryTemplateKind:
        sel = select_template(kind)
        assert isinstance(sel, TemplateSelection)
        assert sel.kind is kind
        assert sel.template is get_template(kind)
        assert sel.required_fields is get_required_fields(kind)


def test_select_template_with_boundary_id_override() -> None:
    """select_template overrides boundary_id when provided."""
    sel = select_template(
        BoundaryTemplateKind.REVISION_BOUNDARY,
        boundary_id="custom.revision.gate",
    )
    assert sel.template.boundary_id == "custom.revision.gate"
    # Other fields should match canonical
    canonical = get_template(BoundaryTemplateKind.REVISION_BOUNDARY)
    assert sel.template.workflow_id == canonical.workflow_id
    assert sel.template.required_artifacts == canonical.required_artifacts


def test_select_template_with_workflow_id_override() -> None:
    """select_template overrides workflow_id when provided."""
    sel = select_template(
        BoundaryTemplateKind.VALIDATION_BOUNDARY,
        workflow_id="custom-workflow",
    )
    assert sel.template.workflow_id == "custom-workflow"


def test_select_template_with_phase_override() -> None:
    """select_template overrides phase when provided."""
    sel = select_template(
        BoundaryTemplateKind.REVISION_BOUNDARY,
        phase=BoundaryPhase.GATE,
    )
    assert sel.template.phase is BoundaryPhase.GATE


def test_select_template_with_phase_string_override() -> None:
    """select_template accepts a string for the phase override."""
    sel = select_template(
        BoundaryTemplateKind.REVISION_BOUNDARY,
        phase="gate",
    )
    assert sel.template.phase is BoundaryPhase.GATE


def test_select_template_with_required_artifacts_override() -> None:
    """select_template overrides required_artifacts when provided."""
    sel = select_template(
        BoundaryTemplateKind.VALIDATION_BOUNDARY,
        required_artifacts=("a.json", "b.json"),
    )
    assert sel.template.required_artifacts == ("a.json", "b.json")


def test_select_template_with_state_delta_override() -> None:
    """select_template overrides expected_state_delta when provided."""
    sel = select_template(
        BoundaryTemplateKind.ARTIFACT_PROMOTION,
        expected_state_delta={"custom": "value"},
    )
    assert dict(sel.template.expected_state_delta) == {"custom": "value"}


def test_select_template_with_history_entry_override() -> None:
    """select_template overrides expected_history_entry."""
    sel = select_template(
        BoundaryTemplateKind.REVISION_BOUNDARY,
        expected_history_entry="custom_history",
    )
    assert sel.template.expected_history_entry == "custom_history"


def test_select_template_with_bool_overrides() -> None:
    """select_template overrides phase_result_required, receipt_required, authority_required."""
    sel = select_template(
        BoundaryTemplateKind.EXTERNAL_EFFECT,
        phase_result_required=True,
        receipt_required=False,
        authority_required=True,
    )
    assert sel.template.phase_result_required is True
    assert sel.template.receipt_required is False
    assert sel.template.authority_required is True


def test_select_template_with_details_merge() -> None:
    """select_template merges details (shallow merge)."""
    sel = select_template(
        BoundaryTemplateKind.VALIDATION_BOUNDARY,
        details={"extra_key": "extra_value", "validation_kind": "custom_val"},
    )
    assert sel.template.details["validation_kind"] == "custom_val"
    assert sel.template.details["extra_key"] == "extra_value"
    # Original detail not in overrides should be preserved
    assert "description" in sel.template.details


def test_select_template_customized_is_frozen() -> None:
    """Customized templates from select_template are still frozen."""
    sel = select_template(
        BoundaryTemplateKind.REVISION_BOUNDARY,
        boundary_id="custom.id",
    )
    with pytest.raises(FrozenInstanceError):
        sel.template.boundary_id = "mutated"  # type: ignore[misc]


def test_select_template_keeps_kind_and_required_fields() -> None:
    """select_template always returns the correct kind and required_fields."""
    sel = select_template(
        BoundaryTemplateKind.HUMAN_APPROVAL_WAIVER,
        boundary_id="custom.approval",
        workflow_id="custom-wf",
        details={"extra": "field"},
    )
    assert sel.kind is BoundaryTemplateKind.HUMAN_APPROVAL_WAIVER
    assert sel.required_fields is get_required_fields(BoundaryTemplateKind.HUMAN_APPROVAL_WAIVER)


# ── TemplateSelection dataclass ──────────────────────────────────────────


def test_template_selection_is_frozen() -> None:
    """TemplateSelection is a frozen dataclass."""
    sel = select_template(BoundaryTemplateKind.REVISION_BOUNDARY)
    with pytest.raises(FrozenInstanceError):
        sel.kind = BoundaryTemplateKind.VALIDATION_BOUNDARY  # type: ignore[misc]


def test_template_selection_attributes() -> None:
    """TemplateSelection has kind, template, and required_fields."""
    sel = select_template(BoundaryTemplateKind.VALIDATION_BOUNDARY)
    assert isinstance(sel.kind, BoundaryTemplateKind)
    assert isinstance(sel.template, BoundaryContract)
    assert isinstance(sel.required_fields, frozenset)


# ── Cross-kind consistency ───────────────────────────────────────────────


def test_every_template_passes_its_own_conformance() -> None:
    """Every canonical template must be self-conformant (redundant but thorough)."""
    for kind in BoundaryTemplateKind:
        tmpl = get_template(kind)
        missing = check_contract_conformance(tmpl, kind)
        assert missing == (), f"{kind} self-check failed: {missing}"


def test_templates_differ_by_kind() -> None:
    """Templates for different kinds must be distinct instances."""
    tmpls = {kind: get_template(kind) for kind in BoundaryTemplateKind}
    for k1 in BoundaryTemplateKind:
        for k2 in BoundaryTemplateKind:
            if k1 is not k2:
                assert tmpls[k1] is not tmpls[k2], (
                    f"{k1} and {k2} share same template instance"
                )


def test_required_fields_differ_by_kind() -> None:
    """Required-field profiles for different kinds are distinct."""
    profiles = {kind: get_required_fields(kind) for kind in BoundaryTemplateKind}
    unique_profiles = set(map(frozenset, profiles.values()))
    # At minimum, not all 10 profiles are identical
    assert len(unique_profiles) > 1, "All required-field profiles are identical"


# ── Edge cases ────────────────────────────────────────────────────────────


def test_conformance_with_none_row_id() -> None:
    """Contracts with None row_id report it as missing."""
    contract = BoundaryContract(
        boundary_id="test.revision",
        workflow_id="test",
        row_id=None,
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.REVISION_BOUNDARY)
    assert "row_id" in missing


def test_conformance_with_none_phase() -> None:
    """Contracts with None phase report it as missing when required."""
    contract = BoundaryContract(
        boundary_id="test.revision",
        workflow_id="test",
        row_id="r1",
        phase=None,
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.REVISION_BOUNDARY)
    assert "phase" in missing


def test_conformance_graph_join_fanout_empty_tuples() -> None:
    """Graph join/fanout profile requires fan_out_refs/fan_in_ref/join_requirements."""
    contract = BoundaryContract(
        boundary_id="test.graph",
        workflow_id="test",
        row_id="r1",
        details={"fan_out_refs": (), "fan_in_ref": None, "join_requirements": ()},
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.GRAPH_JOIN_FANOUT)
    # fan_out_refs is empty tuple → missing; fan_in_ref is None → missing; join_requirements empty → missing
    assert "details.fan_out_refs" in missing
    assert "details.fan_in_ref" in missing
    assert "details.join_requirements" in missing


def test_conformance_graph_join_fanout_populated() -> None:
    """Graph join/fanout with populated fields passes conformance."""
    contract = BoundaryContract(
        boundary_id="test.graph",
        workflow_id="test",
        row_id="r1",
        details={
            "fan_out_refs": ("f1", "f2"),
            "fan_in_ref": "f_in",
            "join_requirements": ("j1",),
        },
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.GRAPH_JOIN_FANOUT)
    assert missing == ()


def test_conformance_execution_custody_fresh_session_truthy() -> None:
    """Execution custody with fresh_session=True and authority=True passes."""
    contract = BoundaryContract(
        boundary_id="test.custody",
        workflow_id="test",
        row_id="r1",
        phase=BoundaryPhase.EXECUTE,
        required_artifacts=("out.json",),
        authority_required=True,
        details={"custody_scope": "sc", "fresh_session": True},
    )
    missing = check_contract_conformance(contract, BoundaryTemplateKind.EXECUTION_CUSTODY)
    assert missing == ()


def test_classify_ambiguous_returns_first_match() -> None:
    """When boundary_id matches multiple hints, the first in priority wins."""
    # 'approval' comes before 'waiver' in the hint dict
    contract = BoundaryContract(
        boundary_id="approval.waiver.combined",
        workflow_id="test",
    )
    result = classify_boundary_kind(contract)
    assert result in (BoundaryTemplateKind.APPROVAL_BOUNDARY, BoundaryTemplateKind.HUMAN_APPROVAL_WAIVER)


# ── TemplateVersionPin ────────────────────────────────────────────────────


def test_template_version_pin_is_frozen() -> None:
    """TemplateVersionPin is a frozen dataclass."""
    pin = TemplateVersionPin(
        kind=BoundaryTemplateKind.REVISION_BOUNDARY,
        version="1.0.0",
    )
    with pytest.raises(FrozenInstanceError):
        pin.version = "2.0.0"  # type: ignore[misc]


def test_template_version_pin_required_fields_property() -> None:
    """TemplateVersionPin.required_fields returns the profile for its kind."""
    pin = TemplateVersionPin(
        kind=BoundaryTemplateKind.REVISION_BOUNDARY,
        version="1.0.0",
    )
    assert pin.required_fields is get_required_fields(BoundaryTemplateKind.REVISION_BOUNDARY)


def test_template_version_pin_default_template_id() -> None:
    """TemplateVersionPin defaults template_id to kind value."""
    pin = TemplateVersionPin(
        kind=BoundaryTemplateKind.VALIDATION_BOUNDARY,
        version="2.0.0",
    )
    assert pin.template_id is None
    assert pin.pinned_at is None


# ── pin_template_version ─────────────────────────────────────────────────


def test_pin_template_version_creates_pin() -> None:
    """pin_template_version creates a TemplateVersionPin."""
    pin = pin_template_version(BoundaryTemplateKind.REVISION_BOUNDARY, "1.0.0")
    assert isinstance(pin, TemplateVersionPin)
    assert pin.kind is BoundaryTemplateKind.REVISION_BOUNDARY
    assert pin.version == "1.0.0"


def test_pin_template_version_with_template_id() -> None:
    """pin_template_version accepts an explicit template_id."""
    pin = pin_template_version(
        BoundaryTemplateKind.APPROVAL_BOUNDARY,
        "1.0.0",
        template_id="custom.approval.template",
    )
    assert pin.template_id == "custom.approval.template"


def test_pin_template_version_by_string_kind() -> None:
    """pin_template_version accepts string kind."""
    pin = pin_template_version("revision_boundary", "1.0.0")
    assert pin.kind is BoundaryTemplateKind.REVISION_BOUNDARY


def test_pin_template_version_invalid_kind_raises() -> None:
    """pin_template_version raises for unknown kind."""
    with pytest.raises((ValueError, KeyError)):
        pin_template_version("nonexistent", "1.0.0")


# ── check_template_upgrade ────────────────────────────────────────────────


def test_check_template_upgrade_same_version_exact_match() -> None:
    """Upgrading from same version to same version is EXACT_MATCH."""
    result = check_template_upgrade(
        BoundaryTemplateKind.REVISION_BOUNDARY,
        from_version="1.0.0",
        to_version="1.0.0",
    )
    assert result.compatibility == TemplateCompatibility.EXACT_MATCH
    assert result.from_version == "1.0.0"
    assert result.to_version == "1.0.0"


def test_check_template_upgrade_different_version_compatible_extension() -> None:
    """Upgrading between different versions with same fields is COMPATIBLE_EXTENSION."""
    result = check_template_upgrade(
        BoundaryTemplateKind.VALIDATION_BOUNDARY,
        from_version="1.0.0",
        to_version="2.0.0",
    )
    assert result.compatibility == TemplateCompatibility.COMPATIBLE_EXTENSION


def test_check_template_upgrade_uses_template_id() -> None:
    """check_template_upgrade passes template_id through."""
    result = check_template_upgrade(
        BoundaryTemplateKind.APPROVAL_BOUNDARY,
        from_version="1.0.0",
        to_version="1.0.0",
        template_id="custom.id",
    )
    assert result.template_id == "custom.id"


def test_check_template_upgrade_defaults_template_id() -> None:
    """check_template_upgrade defaults template_id to kind value."""
    result = check_template_upgrade(
        BoundaryTemplateKind.REVISION_BOUNDARY,
        from_version="1.0.0",
        to_version="1.0.0",
    )
    assert result.template_id == "revision_boundary"


def test_check_template_upgrade_by_string_kind() -> None:
    """check_template_upgrade accepts string kind."""
    result = check_template_upgrade(
        "execution_custody",
        from_version="1.0.0",
        to_version="1.0.0",
    )
    assert result.compatibility == TemplateCompatibility.EXACT_MATCH


def test_check_template_upgrade_all_kinds_compatible() -> None:
    """Every template kind should be compatible with itself at different versions."""
    for kind in BoundaryTemplateKind:
        result = check_template_upgrade(kind, from_version="1.0.0", to_version="2.0.0")
        assert result.compatibility in (
            TemplateCompatibility.EXACT_MATCH,
            TemplateCompatibility.COMPATIBLE_EXTENSION,
        ), f"{kind} upgrade check failed: {result.compatibility}"


# ── deliberate_upgrade_template ───────────────────────────────────────────


def test_deliberate_upgrade_returns_deliberate_status() -> None:
    """deliberate_upgrade_template returns DELIBERATE_UPGRADE status."""
    result = deliberate_upgrade_template(
        BoundaryTemplateKind.REVISION_BOUNDARY,
        from_version="1.0.0",
        to_version="2.0.0",
    )
    assert result.compatibility == TemplateCompatibility.DELIBERATE_UPGRADE
    assert result.from_version == "1.0.0"
    assert result.to_version == "2.0.0"


def test_deliberate_upgrade_with_reason() -> None:
    """deliberate_upgrade_template includes reason in details."""
    result = deliberate_upgrade_template(
        BoundaryTemplateKind.VALIDATION_BOUNDARY,
        from_version="1.0.0",
        to_version="1.1.0",
        reason="Consumer updated for new required fields",
    )
    assert result.details["reason"] == "Consumer updated for new required fields"


def test_deliberate_upgrade_without_reason() -> None:
    """deliberate_upgrade_template with no reason has empty details."""
    result = deliberate_upgrade_template(
        BoundaryTemplateKind.APPROVAL_BOUNDARY,
        from_version="1.0.0",
        to_version="2.0.0",
    )
    assert result.details == {}
    assert result.compatibility == TemplateCompatibility.DELIBERATE_UPGRADE


def test_deliberate_upgrade_with_template_id() -> None:
    """deliberate_upgrade_template passes template_id through."""
    result = deliberate_upgrade_template(
        BoundaryTemplateKind.GRAPH_JOIN_FANOUT,
        from_version="1.0.0",
        to_version="2.0.0",
        template_id="custom.graph",
        reason="Topology change accepted",
    )
    assert result.template_id == "custom.graph"


def test_deliberate_upgrade_by_string_kind() -> None:
    """deliberate_upgrade_template accepts string kind."""
    result = deliberate_upgrade_template(
        "external_witness",
        from_version="1.0.0",
        to_version="2.0.0",
    )
    assert result.compatibility == TemplateCompatibility.DELIBERATE_UPGRADE


def test_deliberate_upgrade_invalid_kind_raises() -> None:
    """deliberate_upgrade_template raises for unknown kind."""
    with pytest.raises((ValueError, KeyError)):
        deliberate_upgrade_template("nonexistent", "1.0.0", "2.0.0")


# ── arnold.workflow export surface ───────────────────────────────────────


def test_boundary_template_exports_accessible_from_arnold_workflow() -> None:
    """All boundary template symbols are accessible from arnold.workflow."""
    import arnold.workflow as wf

    expected_symbols = [
        "BoundaryTemplateKind",
        "TemplateSelection",
        "TemplateVersionPin",
        "REQUIRED_FIELDS_BY_KIND",
        "TEMPLATES_BY_KIND",
        "REQUIRED_FIELDS_REVISION_BOUNDARY",
        "REQUIRED_FIELDS_VALIDATION_BOUNDARY",
        "REQUIRED_FIELDS_ARTIFACT_HANDOFF_BOUNDARY",
        "REQUIRED_FIELDS_ARTIFACT_PROMOTION",
        "REQUIRED_FIELDS_APPROVAL_BOUNDARY",
        "REQUIRED_FIELDS_HUMAN_APPROVAL_WAIVER",
        "REQUIRED_FIELDS_EXTERNAL_EFFECT",
        "REQUIRED_FIELDS_EXECUTION_CUSTODY",
        "REQUIRED_FIELDS_GRAPH_JOIN_FANOUT",
        "REQUIRED_FIELDS_EXTERNAL_WITNESS",
        "get_template",
        "get_required_fields",
        "list_template_kinds",
        "check_contract_conformance",
        "classify_boundary_kind",
        "select_template",
        "pin_template_version",
        "check_template_upgrade",
        "deliberate_upgrade_template",
    ]
    for name in expected_symbols:
        assert hasattr(wf, name), f"arnold.workflow missing: {name}"


def test_boundary_template_exports_in_workflow_all() -> None:
    """All boundary template exports are listed in arnold.workflow.__all__."""
    import arnold.workflow as wf

    expected_in_all = {
        "BoundaryTemplateKind",
        "TemplateSelection",
        "TemplateVersionPin",
        "REQUIRED_FIELDS_BY_KIND",
        "TEMPLATES_BY_KIND",
        "REQUIRED_FIELDS_REVISION_BOUNDARY",
        "REQUIRED_FIELDS_VALIDATION_BOUNDARY",
        "REQUIRED_FIELDS_ARTIFACT_HANDOFF_BOUNDARY",
        "REQUIRED_FIELDS_ARTIFACT_PROMOTION",
        "REQUIRED_FIELDS_APPROVAL_BOUNDARY",
        "REQUIRED_FIELDS_HUMAN_APPROVAL_WAIVER",
        "REQUIRED_FIELDS_EXTERNAL_EFFECT",
        "REQUIRED_FIELDS_EXECUTION_CUSTODY",
        "REQUIRED_FIELDS_GRAPH_JOIN_FANOUT",
        "REQUIRED_FIELDS_EXTERNAL_WITNESS",
        "get_template",
        "get_required_fields",
        "list_template_kinds",
        "check_contract_conformance",
        "classify_boundary_kind",
        "select_template",
        "pin_template_version",
        "check_template_upgrade",
        "deliberate_upgrade_template",
    }
    missing = expected_in_all - set(wf.__all__)
    assert not missing, f"Symbols missing from arnold.workflow.__all__: {missing}"


# ── Verify generic arnold.workflow modules do not import Megaplan ──────────


def test_arnold_workflow_init_has_no_megaplan_imports() -> None:
    """arnold/workflow/__init__.py must not import from arnold_pipelines.megaplan."""
    import arnold.workflow as mod

    source_path = mod.__file__
    assert source_path is not None
    with open(source_path) as fh:
        source = fh.read()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = ""
            if isinstance(node, ast.ImportFrom) and node.module:
                module_name = node.module
            for alias in getattr(node, "names", []):
                full = f"{module_name}.{alias.name}" if module_name else alias.name
                assert "megaplan" not in full.lower(), (
                    f"Megaplan import found in arnold.workflow.__init__: {full}"
                )


def test_arnold_workflow_boundary_templates_no_megaplan() -> None:
    """boundary_templates module must not import from arnold_pipelines.megaplan."""
    # Re-verify after adding compatibility helpers which import from boundary_evidence
    import arnold.workflow.boundary_templates as mod

    source_path = mod.__file__
    assert source_path is not None
    with open(source_path) as fh:
        source = fh.read()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = ""
            if isinstance(node, ast.ImportFrom) and node.module:
                module_name = node.module
            for alias in getattr(node, "names", []):
                full = f"{module_name}.{alias.name}" if module_name else alias.name
                assert "megaplan" not in full.lower(), (
                    f"Megaplan import found in boundary_templates: {full}"
                )


def test_arnold_workflow_boundary_evidence_no_megaplan() -> None:
    """boundary_evidence module must not import from arnold_pipelines.megaplan."""
    import arnold.workflow.boundary_evidence as mod

    source_path = mod.__file__
    assert source_path is not None
    with open(source_path) as fh:
        source = fh.read()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = ""
            if isinstance(node, ast.ImportFrom) and node.module:
                module_name = node.module
            for alias in getattr(node, "names", []):
                full = f"{module_name}.{alias.name}" if module_name else alias.name
                assert "megaplan" not in full.lower(), (
                    f"Megaplan import found in boundary_evidence: {full}"
                )
