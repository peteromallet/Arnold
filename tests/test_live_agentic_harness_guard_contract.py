from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.live_agentic_harness.guard import guard_output_dir
from tests.harness_common import (
    DISPATCHER_FAKE,
    DISPATCHER_FAKING,
    DISPATCHER_REAL,
    FLOW_KIND_LIVE_AGENTIC_HEADLESS,
    MODEL_BEHAVIOR_AGENTIC,
    MODEL_BEHAVIOR_DETERMINISTIC,
    MODEL_BEHAVIOR_SCRIPTED,
    STATUS_BLOCKED_PREREQUISITE,
    STATUS_SUCCESS,
)


def _write_flow_metadata(output_dir: Path, **overrides: object) -> None:
    metadata = {
        "flow_kind": FLOW_KIND_LIVE_AGENTIC_HEADLESS,
        "dispatcher": DISPATCHER_REAL,
        "model_behavior": MODEL_BEHAVIOR_AGENTIC,
        "status": STATUS_SUCCESS,
    }
    metadata.update(overrides)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "flow_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")


@pytest.mark.parametrize("dispatcher", [DISPATCHER_FAKE, DISPATCHER_FAKING])
def test_agentic_guard_rejects_fake_dispatchers(tmp_path: Path, dispatcher: str) -> None:
    output_dir = tmp_path / dispatcher
    _write_flow_metadata(output_dir, dispatcher=dispatcher)

    with pytest.raises(ValueError, match="fake/faking dispatcher"):
        guard_output_dir(output_dir)


@pytest.mark.parametrize("model_behavior", [MODEL_BEHAVIOR_DETERMINISTIC, MODEL_BEHAVIOR_SCRIPTED, None])
def test_agentic_guard_rejects_non_agentic_model_behavior(
    tmp_path: Path,
    model_behavior: str | None,
) -> None:
    output_dir = tmp_path / str(model_behavior)
    _write_flow_metadata(output_dir, model_behavior=model_behavior)

    with pytest.raises(ValueError, match="agentic model behavior"):
        guard_output_dir(output_dir)


def test_agentic_guard_allows_blocked_real_agentic_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "blocked"
    _write_flow_metadata(output_dir, status=STATUS_BLOCKED_PREREQUISITE)

    verdict = guard_output_dir(output_dir)

    assert verdict["live_agentic_success"] is False
    assert verdict["dispatcher"] == DISPATCHER_REAL
    assert verdict["model_behavior"] == MODEL_BEHAVIOR_AGENTIC
