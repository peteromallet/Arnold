from __future__ import annotations

import pytest

from arnold.workflow import (
    EdgeRef,
    NodeRef,
    SourceRef,
    SourceSpan,
    ValueRef,
    manifest_coordinate,
)

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def test_node_and_edge_refs_have_stable_canonical_keys() -> None:
    start = NodeRef("plan")
    review = NodeRef("review")
    edge = EdgeRef(source=start, target=review, label="approved")

    assert str(start) == "node:plan"
    assert start.key == "node:plan"
    assert str(edge) == "edge:plan->review:approved"
    assert edge == EdgeRef(NodeRef("plan"), NodeRef("review"), "approved")


def test_source_refs_preserve_authored_span_identity() -> None:
    span = SourceSpan(
        path="pipelines/example.py",
        start_line=12,
        start_column=5,
        end_line=14,
        end_column=9,
    )
    ref = SourceRef("build_pipeline", span=span)

    assert span.key == "source:pipelines/example.py:12:5-14:9"
    assert ref.key == "source-ref:build_pipeline@source:pipelines/example.py:12:5-14:9"


def test_value_refs_are_node_scoped_and_schema_hash_normalized() -> None:
    ref = ValueRef(NodeRef("reduce"), "verdict", schema_hash="SHA256:" + "C" * 64)

    assert ref.schema_hash == "sha256:" + "c" * 64
    assert ref.key == f"value:reduce.verdict@{ref.schema_hash}"
    assert ValueRef(NodeRef("reduce"), "verdict") != ref


def test_runtime_coordinate_derives_from_human_alias_and_manifest_hash() -> None:
    first = manifest_coordinate("planning", HASH_A)
    same = manifest_coordinate("planning", HASH_A.upper())
    different_alias = manifest_coordinate("review", HASH_A)
    different_hash = manifest_coordinate("planning", HASH_B)

    assert first == same
    assert first.key == f"workflow:planning@{HASH_A}"
    assert first != different_alias
    assert first != different_hash


def test_manifest_cursor_composes_coordinate_with_refs() -> None:
    coordinate = manifest_coordinate("planning", HASH_A)
    node = NodeRef("human_gate")
    cursor = coordinate.cursor(
        node=node,
        edge=EdgeRef(node, NodeRef("finalize"), "approved"),
        value=ValueRef(node, "answer"),
        reentry_id="resume-1",
    )

    assert cursor.key == (
        f"workflow:planning@{HASH_A}"
        "#node:human_gate"
        "#edge:human_gate->finalize:approved"
        "#value:human_gate.answer"
        "#reentry:resume-1"
    )


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: NodeRef("bad/id"), "ref alphabet"),
        (lambda: EdgeRef(NodeRef("a"), NodeRef("b"), ""), "edge label"),
        (lambda: SourceSpan("", 1), "source path"),
        (lambda: SourceSpan("x.py", 0), "start_line"),
        (lambda: ValueRef(NodeRef("a"), "payload", schema_hash="sha256:not-a-hash"), "manifest_hash"),
        (lambda: manifest_coordinate("1-invalid", HASH_A), "workflow alias"),
    ],
)
def test_refs_fail_closed_on_ambiguous_identity(factory, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        factory()
