"""Focused contracts for the neutral C2 aggregation algebra."""

from __future__ import annotations

import ast
from pathlib import Path
from types import MappingProxyType

import pytest

from arnold.workflow.completion.aggregation import (
    ADMITTED_CHILD_SET_SCHEMA_VERSION,
    AggregationSignature,
    AdmittedChildSet,
    ChildContribution,
    Multiplicity,
    SelectedPath,
    TotalDispositionMapping,
    TransitiveWaiverTaint,
    UnselectedPath,
    build_multiplicity,
    propagate_waiver_taint,
    validate_multiplicity,
    validate_no_double_count,
    validate_path_selection,
    validate_total_disposition_mapping,
)


def _child_set() -> AdmittedChildSet:
    return AdmittedChildSet(
        parent_id="parent:1",
        child_ids=("child:a", "child:b"),
        binding_hash="sha256:binding",
    )


def _contributions(*, tainted: bool = False) -> tuple[ChildContribution, ...]:
    taint = ("deep-child",) if tainted else ()
    return (
        ChildContribution("child:a", "accepted", {"value": 1}, ("e:a",), taint=taint),
        ChildContribution("child:b", "accepted", {"value": 2}, ("e:b",)),
    )


def _paths() -> tuple[SelectedPath | UnselectedPath, ...]:
    return (
        SelectedPath("path:selected", proof_ids=("decision:1",)),
        UnselectedPath("path:other", proof_ids=("proof:not-applicable",)),
    )


def test_child_set_and_contribution_are_frozen_and_content_addressed() -> None:
    children = _child_set()
    assert children.child_set_hash.startswith("sha256:")
    assert ADMITTED_CHILD_SET_SCHEMA_VERSION in children.to_dict()["schema_version"]
    with pytest.raises((AttributeError, TypeError)):
        children.child_ids += ("child:c",)  # type: ignore[misc]

    contribution = _contributions()[0]
    assert contribution.from_dict(contribution.to_dict()) == contribution
    with pytest.raises(ValueError):
        ChildContribution.from_dict({**contribution.to_dict(), "contribution_hash": "sha256:bad"})


def test_total_mapping_is_total_and_exposes_no_mutable_authority() -> None:
    children = _child_set()
    mapping = TotalDispositionMapping(children, {"child:a": "accepted", "child:b": "blocked"})
    assert validate_total_disposition_mapping(mapping, children)
    assert isinstance(mapping.mapping, MappingProxyType)
    with pytest.raises(TypeError):
        mapping.mapping["child:a"] = "waived"  # type: ignore[index]
    with pytest.raises(ValueError, match="not total"):
        TotalDispositionMapping(children, {"child:a": "accepted"})


def test_contributions_preserve_multiplicity_and_reject_double_counting() -> None:
    children = _child_set()
    contributions = _contributions()
    multiplicity = build_multiplicity(children, contributions)
    assert multiplicity.satisfied
    assert validate_multiplicity(multiplicity, contributions, children)
    duplicate = contributions + (ChildContribution.from_dict(contributions[0].to_dict()),)
    with pytest.raises(ValueError, match="more than once"):
        validate_no_double_count(duplicate)
    short = Multiplicity(expected=2, admitted=2, observed=1)
    with pytest.raises(ValueError, match="not preserved"):
        validate_multiplicity(short)


def test_path_selection_requires_one_choice_and_unselected_proof() -> None:
    paths = _paths()
    assert validate_path_selection(paths)[0].selected
    with pytest.raises(ValueError, match="unselected path"):
        UnselectedPath("path:missing-proof")
    with pytest.raises(ValueError, match="exactly one"):
        validate_path_selection((SelectedPath("a"), SelectedPath("b")))


def test_transitive_taint_survives_and_clean_root_acceptance_is_rejected() -> None:
    contributions = _contributions(tainted=True)
    taint = propagate_waiver_taint(contributions)
    assert taint == frozenset({"deep-child", "waived"})
    record = TransitiveWaiverTaint(taint=taint)
    assert record.from_dict(record.to_dict()) == record
    children = _child_set()
    mapping = TotalDispositionMapping(children, {"child:a": "accepted", "child:b": "accepted"})
    multiplicity = build_multiplicity(children, contributions)
    with pytest.raises(ValueError, match="clean root"):
        AggregationSignature(children, mapping, _paths(), contributions, multiplicity, root_accepted=True)


def test_aggregation_signature_round_trips_and_has_no_concrete_instances() -> None:
    children = _child_set()
    contributions = _contributions()
    mapping = TotalDispositionMapping(children, {child: "accepted" for child in children.child_ids})
    multiplicity = build_multiplicity(children, contributions)
    signature = AggregationSignature(children, mapping, _paths(), contributions, multiplicity)
    assert signature.from_dict(signature.to_dict()) == signature
    source_path = Path(__file__).parents[3] / "arnold" / "workflow" / "completion" / "aggregation.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    class_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    assert not {"MapAggregation", "ReducerAggregation", "RetryAggregation"}.intersection(class_names)
