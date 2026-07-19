from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.run_state.decision_contract import (
    HUMAN_REQUIRED_STATE_TOKENS,
    is_human_required_state,
    typed_human_gate_for_state,
)
from arnold_pipelines.megaplan.run_state.model import TypedHumanGate


@pytest.mark.parametrize(
    ("token", "gate"),
    [
        ("awaiting_human", TypedHumanGate.USER_ACTION),
        ("awaiting_human_verify", TypedHumanGate.VERIFICATION),
        ("human_prerequisite", TypedHumanGate.USER_ACTION),
        ("awaiting_pr_merge", TypedHumanGate.EXPLICIT_APPROVAL),
        ("manual_required", TypedHumanGate.USER_ACTION),
        ("human_required", TypedHumanGate.USER_ACTION),
    ],
)
def test_concrete_human_gate_tokens_have_one_shared_typed_mapping(
    token: str, gate: TypedHumanGate
) -> None:
    assert HUMAN_REQUIRED_STATE_TOKENS[token] is gate
    assert typed_human_gate_for_state(token) is gate
    assert is_human_required_state(token) is True


@pytest.mark.parametrize("token", ["blocked", "failed", "manual_review", "", None])
def test_generic_or_unknown_blocks_are_not_silently_promoted_to_human_gates(
    token: object,
) -> None:
    assert typed_human_gate_for_state(token) is None
    assert is_human_required_state(token) is False
