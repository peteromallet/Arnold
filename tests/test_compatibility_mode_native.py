"""Characterization tests verifying CompatibilityMode.NATIVE migration is complete.

All 17 steps registered in STEP_CONTRACTS must declare NATIVE compatibility mode.
The oracle fixture at tests/oracle/fixtures/native_steps.json pins the expected
step set so regressions are caught if new steps are added without a mode declaration.
"""

from __future__ import annotations

import json
from pathlib import Path

from arnold.pipelines.megaplan._compatibility import CompatibilityMode
from arnold.pipelines.megaplan.step_contracts import STEP_CONTRACTS, build_compatibility_mode_by_step
import arnold.pipelines.megaplan.model_seam as model_seam


FIXTURE_DIR = Path(__file__).resolve().parent / "oracle" / "fixtures"


def test_all_step_contracts_are_native() -> None:
    """Every StepContract must declare CompatibilityMode.NATIVE."""
    legacy = [
        name for name, c in STEP_CONTRACTS.items()
        if c.compatibility_mode is not CompatibilityMode.NATIVE
    ]
    assert legacy == [], f"Unexpected LEGACY steps in STEP_CONTRACTS: {legacy}"


def test_compatibility_mode_by_step_all_native() -> None:
    """build_compatibility_mode_by_step() must return NATIVE for every step."""
    modes = build_compatibility_mode_by_step()
    legacy = [s for s, m in modes.items() if m is not CompatibilityMode.NATIVE]
    assert legacy == [], f"LEGACY steps in built compatibility map: {legacy}"


def test_unknown_step_defaults_to_native() -> None:
    """_compatibility_mode_for_step must default to NATIVE for unregistered steps."""
    result = model_seam._compatibility_mode_for_step("__unknown_step_xyzzy__")
    assert result is CompatibilityMode.NATIVE, (
        f"Expected NATIVE for unknown step, got {result!r}. "
        "Flip the .get() default in _compatibility_mode_for_step."
    )


def test_native_characterization_fixture_matches_step_contracts() -> None:
    """Oracle fixture step set must match the current STEP_CONTRACTS keys."""
    fixture = json.loads((FIXTURE_DIR / "native_steps.json").read_text(encoding="utf-8"))
    fixture_steps = set(fixture["steps"])
    contract_steps = set(STEP_CONTRACTS.keys())
    assert fixture_steps == contract_steps, (
        f"Fixture/STEP_CONTRACTS mismatch.\n"
        f"  In fixture but not contracts: {fixture_steps - contract_steps}\n"
        f"  In contracts but not fixture: {contract_steps - fixture_steps}\n"
        "Refresh tests/oracle/fixtures/native_steps.json when STEP_CONTRACTS changes."
    )
    assert fixture["unknown_step_default"] == "native"
