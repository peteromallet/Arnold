"""Focused regression: CAS-fenced legacy deterministic-phase recovery admission.

Covers the canonical immediate repair from the content-addressed recovery
handoff (arnold.superfixer.recovery_handoff.v1): a structurally incomplete
legacy/synthetic plan-state record (``current_state=blocked`` with a
``deterministic_phase_failure`` but NO ``resume_cursor``/retry metadata) must
be admitted through recover-blocked when the caller binds the exact occurrence
digest (watchdog ``_failure_digest_src`` reconstruction) and the handoff id —
atomically materializing the missing repair identity and cursor WITHOUT
clearing the failure or changing ``current_state`` — and must otherwise keep
the existing fail-closed ``missing_resume_cursor`` behavior.

The exact minimal p1 state from the occurrence (9d6eb33c9c29) is used verbatim:
``{"name": "p1", "current_state": "blocked", "latest_failure":
{"kind": "deterministic_phase_failure", "phase": "critique",
 "message": "critique contract failed three times"}}``
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.handlers.override import (
    _materialize_legacy_deterministic_phase_cursor,
    _override_recover_blocked,
    _reconstruct_failure_occurrence_digest,
)
from arnold_pipelines.megaplan.types import CliError

EXACT_P1_STATE = {
    "name": "p1",
    "current_state": "blocked",
    "latest_failure": {
        "kind": "deterministic_phase_failure",
        "phase": "critique",
        "message": "critique contract failed three times",
    },
}

OCCURRENCE = "9d6eb33c9c29"
HANDOFF_ID = "sha256:a75bfefffafa0cccd7e39692e26dabc96620d562bd66ad96330feeef334fbd86"
EXPECTED_FINGERPRINT = "902d0a46817c00f84de6e8026ae60023632b2cb1eaf009d2c98f3375b2ce120d"


def _write_exact_p1_state(plan_dir: Path) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(
        json.dumps(EXACT_P1_STATE, separators=(",", ":")), encoding="utf-8"
    )


def _repair_args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "reason": "legacy deterministic critique contract failure admitted via handoff",
        "repair_commit": "a" * 40,
        "failure_fingerprint": EXPECTED_FINGERPRINT,
        "repair_scope": "engine_runtime",
        "occurrence": OCCURRENCE,
        "handoff_id": HANDOFF_ID,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


class TestDigestReconstruction:
    def test_reconstructs_watchdog_occurrence_digest(self) -> None:
        """The exact p1 latest_failure reconstructs to 9d6eb33c9c29."""
        assert (
            _reconstruct_failure_occurrence_digest(EXACT_P1_STATE["latest_failure"])
            == OCCURRENCE
        )

    def test_reconstruction_uses_failure_metadata_fields(self) -> None:
        failure = {
            "kind": "deterministic_phase_failure",
            "phase": "critique",
            "message": "critique contract failed three times",
            "metadata": {"phase_or_step": "critique", "blocked_task_id": "T1"},
        }
        digest = _reconstruct_failure_occurrence_digest(failure)
        assert isinstance(digest, str) and len(digest) == 12
        assert digest != OCCURRENCE


class TestAdmissionUnit:
    def test_materializes_cursor_without_clearing_failure(
        self, tmp_path: Path
    ) -> None:
        """Admission alone materializes resume_cursor + repair identity and
        preserves the failure and current_state."""
        plan_dir = tmp_path / "p1"
        _write_exact_p1_state(plan_dir)
        state = dict(EXACT_P1_STATE)

        admission = _materialize_legacy_deterministic_phase_cursor(
            plan_dir, state, _repair_args(), root=tmp_path
        )

        assert admission is not None
        assert admission["occurrence_digest"] == OCCURRENCE
        assert admission["handoff_id"] == HANDOFF_ID
        assert admission["failure_fingerprint"] == EXPECTED_FINGERPRINT
        assert admission["materialized"]["resume_cursor"] == {
            "phase": "critique",
            "retry_strategy": "repair_phase_contract",
        }
        # Failure preserved, current_state unchanged.
        assert state["current_state"] == "blocked"
        assert state["latest_failure"] == EXACT_P1_STATE["latest_failure"]
        # Cursor materialized for the supported seam.
        assert state["resume_cursor"] == {
            "phase": "critique",
            "retry_strategy": "repair_phase_contract",
        }
        assert state["meta"]["phase_repair_admissions"][0] == admission
        # The minimal config the worker preflight requires is materialized.
        assert state["config"]["project_dir"] == str(tmp_path)
        assert admission["materialized"]["project_dir"] == str(tmp_path)

    def test_rejects_occurrence_mismatch(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "p1"
        _write_exact_p1_state(plan_dir)
        state = dict(EXACT_P1_STATE)

        with pytest.raises(CliError) as excinfo:
            _materialize_legacy_deterministic_phase_cursor(
                plan_dir, state, _repair_args(occurrence="deadbeef000")
            )
        assert excinfo.value.code == "occurrence_digest_mismatch"
        # Nothing was materialized.
        assert "resume_cursor" not in state

    def test_fails_closed_without_fence(self, tmp_path: Path) -> None:
        """Without the occurrence/handoff fence the admission does NOT apply;
        the caller keeps the original missing_resume_cursor behavior."""
        plan_dir = tmp_path / "p1"
        _write_exact_p1_state(plan_dir)
        state = dict(EXACT_P1_STATE)

        assert (
            _materialize_legacy_deterministic_phase_cursor(
                plan_dir, state, _repair_args(occurrence=None, handoff_id=None)
            )
            is None
        )
        assert "resume_cursor" not in state

    def test_rejects_state_drift(self, tmp_path: Path) -> None:
        """A concurrent writer that already repaired the cursor on disk must
        not be double-admitted."""
        plan_dir = tmp_path / "p1"
        _write_exact_p1_state(plan_dir)
        state = dict(EXACT_P1_STATE)
        # On-disk state now carries a cursor (concurrent repair landed).
        drifted = dict(EXACT_P1_STATE)
        drifted["resume_cursor"] = {
            "phase": "critique",
            "retry_strategy": "repair_phase_contract",
        }
        (plan_dir / "state.json").write_text(
            json.dumps(drifted, separators=(",", ":")), encoding="utf-8"
        )

        with pytest.raises(CliError) as excinfo:
            _materialize_legacy_deterministic_phase_cursor(
                plan_dir, state, _repair_args()
            )
        assert excinfo.value.code == "admission_state_drift"

    def test_does_not_apply_to_non_deterministic_failure(
        self, tmp_path: Path
    ) -> None:
        plan_dir = tmp_path / "p1"
        _write_exact_p1_state(plan_dir)
        state = {
            "name": "p1",
            "current_state": "blocked",
            "latest_failure": {
                "kind": "repeated_failure_signature",
                "phase": "critique",
                "message": "same semantic failure repeated 3 times",
            },
        }
        assert (
            _materialize_legacy_deterministic_phase_cursor(
                plan_dir, state, _repair_args()
            )
            is None
        )
        assert "resume_cursor" not in state


class TestRecoverBlockedIntegration:
    def test_recover_blocked_advances_exact_p1_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Full recover-blocked path on the exact minimal p1 state: admission
        materializes the cursor, the deterministic repair gate binds the
        fingerprint/commit, and the plan advances to the recovery predecessor
        (planned) with the occurrence preserved in durable custody records."""
        plan_dir = tmp_path / "p1"
        _write_exact_p1_state(plan_dir)
        repair_evidence = {
            "failure_kind": "deterministic_phase_failure",
            "phase": "critique",
            "repair_commit": "a" * 40,
            "failure_fingerprint": EXPECTED_FINGERPRINT,
            "repair_scope": "engine_runtime",
        }
        monkeypatch.setattr(
            "arnold_pipelines.megaplan.handlers.override.validated_deterministic_phase_repair",
            lambda *args, **kwargs: repair_evidence,
        )

        response = _override_recover_blocked(
            tmp_path,
            plan_dir,
            dict(EXACT_P1_STATE),
            _repair_args(),
        )

        assert response["success"] is True
        assert response["state"] == "planned"
        assert response["phase"] == "critique"

        persisted = json.loads(
            (plan_dir / "state.json").read_text(encoding="utf-8")
        )
        # The canonical cursor advanced off blocked.
        assert persisted["current_state"] == "planned"
        assert persisted["resume_cursor"] == {
            "phase": "critique",
            "retry_strategy": "repair_phase_contract",
        }
        overrides = persisted["meta"]["overrides"]
        assert overrides[-1]["action"] == "recover-blocked"
        assert overrides[-1]["from_state"] == "blocked"
        assert overrides[-1]["to_state"] == "planned"
        # Occurrence-bound custody records carry the handoff id.
        admissions = persisted["meta"]["phase_repair_admissions"]
        assert admissions[-1]["occurrence_digest"] == OCCURRENCE
        assert admissions[-1]["handoff_id"] == HANDOFF_ID
        assert admissions[-1]["failure"]["phase"] == "critique"
        assert (
            admissions[-1]["materialized"]["resume_cursor"]["retry_strategy"]
            == "repair_phase_contract"
        )
        # The failed occurrence is preserved durably (admission + override).
        assert admissions[-1]["failure"]["message"] == (
            "critique contract failed three times"
        )

    def test_missing_resume_cursor_still_fails_closed_without_fence(
        self, tmp_path: Path
    ) -> None:
        """Without the occurrence fence the legacy state keeps the exact
        original fail-closed error — no silent auto-admission."""
        plan_dir = tmp_path / "p1"
        _write_exact_p1_state(plan_dir)
        args = _repair_args(occurrence=None, handoff_id=None)

        with pytest.raises(CliError) as excinfo:
            _override_recover_blocked(tmp_path, plan_dir, dict(EXACT_P1_STATE), args)
        assert excinfo.value.code == "missing_resume_cursor"


class TestStage4MovementProof:
    def _chain_movement_evidence(self, workspace: Path, plan: str) -> dict[str, object]:
        """Content-addressed plan-state + journal + incident-ledger snapshot.

        Local stand-in for the deleted coded orchestrator's evidence helpers:
        the babysitter is prompt-driven, so movement proof reads the durable
        plan state, plan event journal, and incident ledger directly.
        """
        plan_dir = workspace / ".megaplan" / "plans" / plan
        state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        state_bytes = json.dumps(
            state, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        events_path = plan_dir / "events.ndjson"
        seq_path = plan_dir / ".events.seq"
        ledger_dir = workspace / ".megaplan" / "incident-ledger"
        ledger_path = ledger_dir / "events.jsonl"
        ledger_seq_path = ledger_dir / ".events.seq"

        def _seq(path: Path) -> int:
            if not path.exists():
                return 0
            try:
                return int(path.read_text(encoding="utf-8").strip() or "0")
            except ValueError:
                return 0

        return {
            "plan_state_sha256": hashlib.sha256(state_bytes).hexdigest(),
            "plan_current_state": str(state.get("current_state") or ""),
            "plan_events_seq": _seq(seq_path),
            "plan_events_lines": (
                len(events_path.read_text(encoding="utf-8").splitlines())
                if events_path.exists()
                else 0
            ),
            "incident_ledger_seq": _seq(ledger_seq_path),
            "incident_ledger_lines": (
                len(ledger_path.read_text(encoding="utf-8").splitlines())
                if ledger_path.exists()
                else 0
            ),
        }

    def _advance_key(self, evidence: dict[str, object]) -> str:
        return ":".join(
            str(evidence[key])
            for key in (
                "plan_events_seq",
                "plan_events_lines",
                "incident_ledger_seq",
                "incident_ledger_lines",
                "plan_current_state",
                "plan_state_sha256",
            )
        )

    def test_movement_evidence_is_content_addressed_and_journal_aware(
        self, tmp_path: Path
    ) -> None:
        """Stage 4 local-plan proof compares content-addressed before/after
        plan state plus the plan's real event journal and the incident ledger."""
        workspace = tmp_path / "ws"
        plan_dir = workspace / ".megaplan" / "plans" / "p1"
        _write_exact_p1_state(plan_dir)

        before = self._chain_movement_evidence(workspace, "p1")
        before_key = self._advance_key(before)
        assert "plan_state_sha256" in before
        assert before["plan_current_state"] == "blocked"

        # Real recovery movement: state advances, plan event journal advances,
        # incident ledger advances with one terminal event.
        recovered = dict(EXACT_P1_STATE)
        recovered["current_state"] = "planned"
        recovered["resume_cursor"] = {
            "phase": "critique",
            "retry_strategy": "repair_phase_contract",
        }
        recovered["meta"] = {"overrides": [{"action": "recover-blocked"}]}
        (plan_dir / "state.json").write_text(
            json.dumps(recovered, separators=(",", ":")), encoding="utf-8"
        )
        (plan_dir / "events.ndjson").write_text(
            '{"seq": 1, "kind": "override_applied"}\n', encoding="utf-8"
        )
        (plan_dir / ".events.seq").write_text("1", encoding="utf-8")
        ledger = workspace / ".megaplan" / "incident-ledger"
        ledger.mkdir(parents=True, exist_ok=True)
        (ledger / "events.jsonl").write_text(
            '{"seq": 0}\n{"seq": 1}\n{"seq": 2}\n', encoding="utf-8"
        )
        (ledger / ".events.seq").write_text("2", encoding="utf-8")

        after = self._chain_movement_evidence(workspace, "p1")
        after_key = self._advance_key(after)

        assert after["plan_state_sha256"] != before["plan_state_sha256"]
        assert after["plan_current_state"] == "planned"
        assert after["plan_events_seq"] == 1
        assert after["plan_events_lines"] == 1
        assert after["incident_ledger_seq"] == 2
        assert after["incident_ledger_lines"] == 3
        assert after_key > before_key
