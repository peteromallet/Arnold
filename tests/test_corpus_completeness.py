"""Step 22 (T27) — corpus completeness gate.

Invokes ``fold_equivalence_oracle`` over the flag-ON MANIFEST
(``tests/corpus/flag_on/MANIFEST.json``), asserting that every flag-ON
golden's driver-level state transitions fold to the recorded
``outcome.final_state``.

This test uses the SAME ``fold_equivalence_oracle`` callable as
``test_hinge_fold_equivalence.py`` (no reimplementation), wired to the
flag-ON MANIFEST.  The 3-entry flag-ON MANIFEST + the 35-entry M2.5
baseline MANIFEST = 38 goldens validated across the test suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.observability.fold import OracleResult, fold_equivalence_oracle

# ---------------------------------------------------------------------------
# MANIFEST paths
# ---------------------------------------------------------------------------

FLAG_ON_MANIFEST = Path(__file__).parent / "corpus" / "flag_on" / "MANIFEST.json"


# ---------------------------------------------------------------------------
# Gate tests
# ---------------------------------------------------------------------------


@pytest.mark.hinge_gate
def test_flag_on_manifest_has_three_entries() -> None:
    """Flag-ON MANIFEST registers exactly 3 goldens."""
    manifest = json.loads(FLAG_ON_MANIFEST.read_text(encoding="utf-8"))
    assert len(manifest["goldens"]) == 3


@pytest.mark.hinge_gate
def test_fold_equivalence_oracle_passes_flag_on_manifest() -> None:
    """All 3 flag-ON goldens pass fold_equivalence_oracle (same callable, no reimplementation)."""
    result = fold_equivalence_oracle(FLAG_ON_MANIFEST)
    assert isinstance(result, OracleResult)
    assert result.total == 3
    assert result.ok, (
        f"oracle failed on {result.failed}/{result.total} flag-ON goldens: "
        + ", ".join(
            f"{f.name}: expected={f.expected!r} actual={f.actual!r} ({f.reason})"
            for f in result.failures
        )
    )
    assert result.passed == 3
