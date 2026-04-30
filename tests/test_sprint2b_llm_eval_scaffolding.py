from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sprint2b_llm_eval.json"


def _load_fixtures() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_sprint2b_llm_eval_fixture_shape_is_deterministic() -> None:
    fixtures = _load_fixtures()

    assert len(fixtures["style_violation_turns"]) == 20
    assert len(fixtures["body_filler_turns"]) == 20
    for group_name in ("style_violation_turns", "body_filler_turns"):
        ids = [item["id"] for item in fixtures[group_name]]
        assert len(ids) == len(set(ids))
        assert all(item["expected_behavior"] for item in fixtures[group_name])


@pytest.mark.llm_eval
def test_optional_sprint2b_llm_eval_is_env_gated() -> None:
    if os.getenv("ARNOLD_RUN_LLM_EVALS") != "1":
        pytest.skip("Set ARNOLD_RUN_LLM_EVALS=1 to run live Sprint 2b LLM evals.")

    fixtures = _load_fixtures()
    assert fixtures["style_violation_turns"]
    assert fixtures["body_filler_turns"]
