from __future__ import annotations

import pytest

from arnold.pipeline import Pipeline, Port, PortRef, SeamId, Stage, resolve_seam_from_binding_map


def test_seam_id_round_trips_format_and_parse() -> None:
    seam = SeamId(
        pipeline_id="pipe_a",
        consumer_step="review",
        consumer_port="input",
        producer_step="execute",
        producer_port="output",
    )

    encoded = str(seam)

    assert encoded == "pipe_a::review.input<=execute.output"
    assert SeamId.parse(encoded) == seam


def test_seam_id_equality_and_set_uniqueness_deduplicate_identical_bindings() -> None:
    first = SeamId(
        pipeline_id="pipe_a",
        consumer_step="review",
        consumer_port="input",
        producer_step="execute",
        producer_port="output",
    )
    duplicate = SeamId.parse("pipe_a::review.input<=execute.output")

    assert first == duplicate
    assert len({first, duplicate}) == 1


def test_seam_id_uniqueness_includes_pipeline_id() -> None:
    left = SeamId.parse("pipe_a::review.input<=execute.output")
    right = SeamId.parse("pipe_b::review.input<=execute.output")

    assert left != right
    assert len({left, right}) == 2


def test_seam_id_parse_rejects_malformed_strings() -> None:
    with pytest.raises(ValueError, match="Invalid SeamId"):
        SeamId.parse("review.input<=execute.output")

    with pytest.raises(ValueError, match="Invalid SeamId"):
        SeamId.parse("pipe_a::review.input=>execute.output")


def test_seam_id_rejects_reserved_delimiters_in_fields() -> None:
    with pytest.raises(ValueError, match="reserved seam delimiter"):
        SeamId(
            pipeline_id="pipe_a",
            consumer_step="review.bad",
            consumer_port="input",
            producer_step="execute",
            producer_port="output",
        )


def test_resolve_seam_from_binding_map_returns_typed_producer_consumer_pair() -> None:
    pipeline = Pipeline(
        stages={
            "execute": Stage(
                name="execute",
                step=object(),
                produces=(Port(name="result", content_type="application/json"),),
            ),
            "review": Stage(
                name="review",
                step=object(),
                consumes=(PortRef(port_name="result", content_type="application/json"),),
            ),
        },
        entry="execute",
        binding_map={("review", "result"): ("execute", "result")},
    )

    resolution = resolve_seam_from_binding_map(
        pipeline,
        pipeline_id="pipe_a",
        consumer_step="review",
        consumer_port="result",
    )

    assert resolution.seam_id == SeamId.parse("pipe_a::review.result<=execute.result")
    assert resolution.producer_typed is True
    assert resolution.consumer_typed is True
    assert resolution.both_sides_typed is True
    assert resolution.binding_found is True


def test_resolve_seam_from_binding_map_marks_partial_typing_not_both_sides_typed() -> None:
    pipeline = Pipeline(
        stages={
            "execute": Stage(
                name="execute",
                step=object(),
                produces=(Port(name="result", content_type="application/json"),),
            ),
            "review": Stage(name="review", step=object()),
        },
        entry="execute",
        binding_map={("review", "result"): ("execute", "result")},
    )

    resolution = resolve_seam_from_binding_map(
        pipeline,
        pipeline_id="pipe_a",
        consumer_step="review",
        consumer_port="result",
    )

    assert resolution.producer_typed is True
    assert resolution.consumer_typed is False
    assert resolution.both_sides_typed is False


def test_resolve_seam_from_binding_map_lookup_failure_returns_legacy_non_enforceable() -> None:
    pipeline = Pipeline(
        stages={
            "execute": Stage(
                name="execute",
                step=object(),
                produces=(Port(name="result", content_type="application/json"),),
            ),
            "review": Stage(
                name="review",
                step=object(),
                consumes=(PortRef(port_name="result", content_type="application/json"),),
            ),
        },
        entry="execute",
        binding_map={},
    )

    resolution = resolve_seam_from_binding_map(
        pipeline,
        pipeline_id="pipe_a",
        consumer_step="review",
        consumer_port="result",
    )

    assert resolution.seam_id is None
    assert resolution.producer_typed is False
    assert resolution.consumer_typed is False
    assert resolution.both_sides_typed is False
    assert resolution.binding_found is False
    assert resolution.reason == "binding lookup unavailable"
