"""T26 / Step 21 — hinge-gate fold-equivalence oracle test.

Drives ``fold_equivalence_oracle`` across the M2.5 35-entry baseline corpus
MANIFEST, asserting that lifting each golden's driver-level events into
shadow-WAL ``STATE_WRITTEN`` form and folding them reproduces the recorded
driver outcome's ``final_state``. Marked ``hinge_gate`` so the chain CI hook
picks it up alongside the other M3 hinge oracles.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.observability.fold import (
    OracleResult,
    fold_equivalence_oracle,
    fold_events,
    lift_driver_events_to_wal,
    rebuild_state_from_wal,
)


MANIFEST = (
    Path(__file__).parent
    / "characterization"
    / "auto_drive_corpus"
    / "MANIFEST.json"
)


@pytest.mark.hinge_gate
def test_manifest_has_thirty_five_baseline_entries() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(manifest["goldens"]) == 35


@pytest.mark.hinge_gate
def test_fold_equivalence_oracle_passes_baseline_manifest() -> None:
    result = fold_equivalence_oracle(MANIFEST)
    assert isinstance(result, OracleResult)
    assert result.total == 35
    assert result.ok, (
        f"oracle failed on {result.failed}/{result.total} goldens: "
        + ", ".join(
            f"{f.name}: expected={f.expected!r} actual={f.actual!r} ({f.reason})"
            for f in result.failures
        )
    )
    assert result.passed == 35


@pytest.mark.hinge_gate
def test_lift_driver_events_to_wal_emits_state_written_only_for_transitions() -> None:
    events = [
        {"iteration": 1, "state": "executing", "next_step": "execute", "valid_next": ["execute"]},
        {"msg": "running: megaplan execute", "phase": "execute", "timeout": 3600},
        {"iteration": 2, "state": "done", "next_step": None, "valid_next": []},
        {"msg": "terminal state reached: done"},
    ]
    wal = lift_driver_events_to_wal(events)
    assert len(wal) == 2
    assert [e["kind"] for e in wal] == ["state_written", "state_written"]
    assert [e["seq"] for e in wal] == [1, 2]
    assert wal[0]["payload"]["state"]["current_state"] == "executing"
    assert wal[-1]["payload"]["state"]["current_state"] == "done"


@pytest.mark.hinge_gate
def test_lifted_wal_folds_to_last_transition_state() -> None:
    events = [
        {"iteration": 1, "state": "planning"},
        {"iteration": 2, "state": "executing"},
        {"iteration": 3, "state": "done"},
    ]
    folded = fold_events(lift_driver_events_to_wal(events))
    assert folded["current_state"] == "done"


@pytest.mark.hinge_gate
def test_lift_skips_non_dict_and_no_state_events() -> None:
    events = [
        None,
        {"msg": "no-state"},
        {"iteration": 1, "state": "executing"},
        "garbage",
    ]
    wal = lift_driver_events_to_wal(events)  # type: ignore[arg-type]
    assert len(wal) == 1
    assert wal[0]["payload"]["state"]["current_state"] == "executing"


@pytest.mark.hinge_gate
def test_oracle_reports_failure_when_outcome_diverges(tmp_path: Path) -> None:
    corpus = {
        "events": [
            {"iteration": 1, "state": "executing"},
            {"iteration": 2, "state": "executing"},
        ],
        "outcome": {"final_state": "done"},
    }
    corpus_file = tmp_path / "diverge.json"
    corpus_file.write_text(json.dumps(corpus), encoding="utf-8")
    manifest = {
        "goldens": [
            {
                "name": "diverge",
                "corpus_filename": "diverge.json",
                "branch_ref": "synthetic",
                "oracle_role": "synthetic",
            }
        ]
    }
    manifest_path = tmp_path / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = fold_equivalence_oracle(manifest_path)
    assert not result.ok
    assert result.failed == 1
    assert result.failures[0].expected == {"current_state": "done"}
    assert result.failures[0].actual == {"current_state": "executing"}


@pytest.mark.hinge_gate
def test_oracle_extension_seams_are_parameterized(tmp_path: Path) -> None:
    """Custom lift/fold/projection callables are honored end-to-end."""
    corpus = {"events": [{"x": 1}], "outcome": {"final_state": "anything"}}
    corpus_file = tmp_path / "synthetic.json"
    corpus_file.write_text(json.dumps(corpus), encoding="utf-8")
    manifest_path = tmp_path / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps(
            {"goldens": [{"name": "syn", "corpus_filename": "synthetic.json"}]}
        ),
        encoding="utf-8",
    )

    def lift(events):
        return [{"seq": 1, "kind": "state_written", "payload": {"state": {"x": 42}}}]

    def expected_from_corpus(corpus):
        return {"x": 42}

    def observed_from_fold(folded):
        return {"x": folded.get("x")}

    result = fold_equivalence_oracle(
        manifest_path,
        lift=lift,
        expected_from_corpus=expected_from_corpus,
        observed_from_fold=observed_from_fold,
    )
    assert result.ok
    assert result.passed == 1


@pytest.mark.hinge_gate
def test_rebuild_state_from_wal_still_callable() -> None:
    # Sanity: T25's rebuild alias is unchanged by T26.
    assert callable(rebuild_state_from_wal)
