"""Byte-parity tests: step_contracts factories must produce results identical
to the legacy literals that they will replace.

These tests gate every cut-over in downstream tasks — each replacement
is safe ONLY while these four equalities and the invocation metadata
assertion stay green.
"""

from __future__ import annotations

from arnold.pipelines.megaplan.model_seam import (
    _CAPTURE_SCHEMA_KEYS_BY_STEP,
    _COMPATIBILITY_MODE_BY_STEP,
)
from arnold.pipelines.megaplan.profiles.policy import DEFAULT_AGENT_ROUTING
from arnold.pipelines.megaplan.step_contracts import (
    STEP_CONTRACTS,
    build_capture_schema_keys_by_step,
    build_compatibility_mode_by_step,
    build_default_agent_routing,
    build_step_schema_filenames,
    contract_to_invocation,
)
from arnold.pipelines.megaplan.workers._impl import STEP_SCHEMA_FILENAMES


def test_step_schema_filenames_parity() -> None:
    """``build_step_schema_filenames()`` must be byte-identical to the legacy literal."""
    assert build_step_schema_filenames() == STEP_SCHEMA_FILENAMES


def test_default_agent_routing_parity() -> None:
    """``build_default_agent_routing()`` must be byte-identical to the legacy literal
    (14 keys; feedback='premium:low' included; prep sub-steps excluded)."""
    result = build_default_agent_routing()
    assert result == DEFAULT_AGENT_ROUTING
    # Extra guard: exactly 14 keys
    assert len(result) == 14, f"expected 14 keys, got {len(result)}"
    # feedback must be present with the correct value
    assert "feedback" in result
    assert result["feedback"] == "premium:low"


def test_capture_schema_keys_by_step_parity() -> None:
    """``build_capture_schema_keys_by_step()`` must be byte-identical to the legacy literal."""
    assert build_capture_schema_keys_by_step() == _CAPTURE_SCHEMA_KEYS_BY_STEP


def test_compatibility_mode_by_step_parity() -> None:
    """``build_compatibility_mode_by_step()`` must be byte-identical to the legacy literal."""
    assert build_compatibility_mode_by_step() == _COMPATIBILITY_MODE_BY_STEP


def test_contract_to_invocation_metadata() -> None:
    """The ``StepInvocation`` produced by ``contract_to_invocation`` must carry
    the minimal ``{'compatibility_validation_step': …}`` metadata, matching
    the ad-hoc literal at ``model_seam.py:1544`` byte-for-byte."""
    inv = contract_to_invocation(STEP_CONTRACTS["execute"])
    assert inv.kind == "model"
    assert inv.metadata == {"compatibility_validation_step": "execute"}
