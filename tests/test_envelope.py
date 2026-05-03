from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from agent_kit.envelope import (
    Envelope,
    EnvelopeError,
    Event,
    StateDelta,
    serialize_for_diff,
)


def test_envelope_serializes_with_stable_json_and_valid_schema() -> None:
    envelope = Envelope(
        turn_id="turn_1",
        epic_id="epic_1",
        epic_state_before="shaping",
        epic_state_after="shaping",
        reply="hello",
        state_delta=StateDelta(),
        questions=[],
        events=[
            Event(
                ts="2026-04-30T00:00:00Z",
                kind="tool_call",
                name="send_message",
                ms=12,
                tool_call_id="tool_1",
            ),
            Event(
                ts="2026-04-30T00:00:01Z",
                kind="activity",
                text="drafting",
                tool_call_id="tool_2",
            ),
            Event(
                ts="2026-04-30T00:00:02Z",
                kind="attached_image",
                name="send_image",
                details={
                    "image_id": "img_1",
                    "caption": "caption",
                    "storage_url": "images/epic_1/generated.png",
                    "reference_key": "img_agent_1",
                    "media_type": "image/png",
                },
            ),
        ],
        tool_call_count=2,
        outcome="completed",
    )
    encoded = envelope.to_json()
    assert encoded == json.dumps(
        json.loads(encoded),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    schema = json.loads(Path("agent_kit/envelope.schema.json").read_text())
    validate(envelope.to_dict(), schema)


def test_envelope_error_shape_validates() -> None:
    envelope = Envelope(
        turn_id="turn_1",
        epic_id="epic_1",
        epic_state_before="shaping",
        epic_state_after="shaping",
        reply="",
        outcome="errored",
        error=EnvelopeError(
            code="provider_error",
            message="Provider failed.",
            retryable=True,
        ),
    )
    schema = json.loads(Path("agent_kit/envelope.schema.json").read_text())
    validate(envelope.to_dict(), schema)


def test_envelope_epic_id_may_be_omitted_or_explicit_null() -> None:
    envelope = Envelope(
        turn_id="turn_1",
        epic_state_before="unknown",
        epic_state_after="unknown",
        reply="",
        epic_id=None,
    )
    schema = json.loads(Path("agent_kit/envelope.schema.json").read_text())

    omitted = json.loads(envelope.to_json())
    assert "epic_id" not in omitted
    validate(omitted, schema)

    explicit_null = {**omitted, "epic_id": None}
    validate(explicit_null, schema)


def test_serialize_for_diff_strips_only_declared_nondeterminism() -> None:
    envelope = Envelope(
        turn_id="turn_1",
        epic_id="epic_1",
        epic_state_before="shaping",
        epic_state_after="planned",
        reply="model prose",
        state_delta=StateDelta(body_diff="diff"),
        events=[
            Event(
                ts="stable",
                kind="activity",
                text="model text",
                started_at="start",
                completed_at="end",
                tool_call_id="tool_1",
            )
        ],
        started_at="start",
        completed_at="end",
    )
    projected = json.loads(serialize_for_diff(envelope))
    assert "reply" not in projected
    assert "started_at" not in projected
    assert "completed_at" not in projected
    assert "text" not in projected["events"][0]
    assert projected["events"][0]["ts"] == "stable"
    assert projected["state_delta"]["body_diff"] == "diff"
