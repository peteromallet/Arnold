from __future__ import annotations

import pytest

from tests.harness_common import (
    DISPATCHER_FAKE,
    DISPATCHER_FAKING,
    DISPATCHER_REAL,
    FLOW_KIND_LIVE_AGENTIC_HEADLESS,
    MODEL_BEHAVIOR_AGENTIC,
    MODEL_BEHAVIOR_DETERMINISTIC,
    STATUS_BLOCKED_PREREQUISITE,
    STATUS_SUCCESS,
    build_flow_metadata,
    validate_live_agentic_metadata,
)


def test_build_live_agentic_metadata() -> None:
    metadata = build_flow_metadata(
        flow_kind=FLOW_KIND_LIVE_AGENTIC_HEADLESS,
        dispatcher=DISPATCHER_REAL,
        model_behavior=MODEL_BEHAVIOR_AGENTIC,
        entrypoint="headless_cli",
        status=STATUS_SUCCESS,
    )
    assert metadata["flow_kind"] == FLOW_KIND_LIVE_AGENTIC_HEADLESS
    assert metadata["dispatcher"] == DISPATCHER_REAL
    assert metadata["model_behavior"] == MODEL_BEHAVIOR_AGENTIC


def test_fake_dispatcher_cannot_claim_live_success() -> None:
    for dispatcher in (DISPATCHER_FAKE, DISPATCHER_FAKING):
        with pytest.raises(ValueError, match="Fake/faking dispatchers cannot produce"):
            build_flow_metadata(
                flow_kind=FLOW_KIND_LIVE_AGENTIC_HEADLESS,
                dispatcher=dispatcher,
                model_behavior=MODEL_BEHAVIOR_AGENTIC,
                entrypoint="headless_cli",
                status=STATUS_SUCCESS,
            )


def test_fake_dispatcher_cannot_claim_agentic_model_behavior_for_any_status() -> None:
    for dispatcher in (DISPATCHER_FAKE, DISPATCHER_FAKING):
        with pytest.raises(ValueError, match="Fake/faking dispatchers cannot produce"):
            build_flow_metadata(
                flow_kind="structural_contract",
                dispatcher=dispatcher,
                model_behavior=MODEL_BEHAVIOR_AGENTIC,
                entrypoint="structural_harness",
                status=STATUS_BLOCKED_PREREQUISITE,
            )


def test_non_agentic_model_behavior_cannot_claim_live_success() -> None:
    with pytest.raises(ValueError, match="Live agentic success requires model_behavior"):
        build_flow_metadata(
            flow_kind=FLOW_KIND_LIVE_AGENTIC_HEADLESS,
            dispatcher=DISPATCHER_REAL,
            model_behavior=MODEL_BEHAVIOR_DETERMINISTIC,
            entrypoint="headless_cli",
            status=STATUS_SUCCESS,
        )


def test_blocked_status_does_not_require_agentic_validation() -> None:
    metadata = build_flow_metadata(
        flow_kind=FLOW_KIND_LIVE_AGENTIC_HEADLESS,
        dispatcher=DISPATCHER_FAKE,
        model_behavior=MODEL_BEHAVIOR_DETERMINISTIC,
        entrypoint="headless_cli",
        status=STATUS_BLOCKED_PREREQUISITE,
    )
    assert metadata["dispatcher"] == DISPATCHER_FAKE
