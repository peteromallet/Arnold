from __future__ import annotations

from dataclasses import fields

from arnold.pipeline import Port, PortCardinality, PortRef
from arnold.pipeline.schema_registry import AcceptedVersionRange


def test_port_two_argument_constructor_defaults_to_singleton_metadata() -> None:
    port = Port("result", "application/json")

    assert port.name == "result"
    assert port.content_type == "application/json"
    assert port.taint == frozenset()
    assert port.cardinality == "singleton"
    assert port.logical_type is None
    assert port.accepted_version_range is None


def test_port_ref_two_argument_constructor_defaults_to_singleton_metadata() -> None:
    ref = PortRef("result", "application/json")

    assert ref.port_name == "result"
    assert ref.content_type == "application/json"
    assert ref.cardinality == "singleton"
    assert ref.logical_type is None
    assert ref.accepted_version_range is None


def test_port_and_port_ref_accept_collection_stream_and_logical_versions() -> None:
    accepted_range = AcceptedVersionRange(
        logical_type="review",
        min_version="sha256:" + "0" * 64,
        max_version="sha256:" + "f" * 64,
    )

    collection_port = Port(
        "reviews",
        "application/x-contract-result+json",
        cardinality="collection",
        logical_type="review",
        accepted_version_range=accepted_range,
    )
    stream_ref = PortRef(
        "live_reviews",
        "application/x-contract-result+json",
        cardinality="stream",
        logical_type="review",
        accepted_version_range=accepted_range,
    )

    assert collection_port.cardinality == "collection"
    assert collection_port.logical_type == "review"
    assert collection_port.accepted_version_range is accepted_range
    assert stream_ref.cardinality == "stream"
    assert stream_ref.logical_type == "review"
    assert stream_ref.accepted_version_range is accepted_range


def test_port_legacy_three_argument_constructor_still_accepts_taint() -> None:
    taint = frozenset({"user"})

    port = Port("result", "application/json", taint)

    assert port.taint is taint
    assert port.cardinality == "singleton"
    assert port.logical_type is None
    assert port.accepted_version_range is None


def test_port_cardinality_public_alias_includes_reserved_stream() -> None:
    assert PortCardinality.__args__ == ("singleton", "collection", "stream")


def test_port_metadata_fields_are_append_only_after_legacy_fields() -> None:
    port_field_names = tuple(field.name for field in fields(Port))
    ref_field_names = tuple(field.name for field in fields(PortRef))

    assert port_field_names[:3] == ("name", "content_type", "taint")
    assert port_field_names[3:] == (
        "cardinality",
        "logical_type",
        "accepted_version_range",
    )
    assert ref_field_names[:2] == ("port_name", "content_type")
    assert ref_field_names[2:] == (
        "cardinality",
        "logical_type",
        "accepted_version_range",
    )
