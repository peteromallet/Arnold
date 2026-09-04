from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.incident.chain_control import (
    ABSENT,
    ENVELOPE_FIELDS,
    ChainControlCasConflict,
    ChainControlHold,
    ChainControlJournal,
    LockedChainControlTransaction,
    apply_chain_lifecycle,
    build_envelope,
    canonical_json,
    compute_event_hash,
    event_preimage,
    frame_utf8,
    payload_digest_for,
    u64be,
)
from arnold_pipelines.megaplan.chain.spec import _state_path_for
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

FIXTURE = Path(__file__).parent / "incident" / "fixtures" / "nbf08_s1_event_v1.json"


def test_s1_golden_vector_is_independently_recomputed() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload = fixture["payload"]
    encoded = canonical_json(payload)
    assert encoded.hex() == fixture["canonical_payload_hex"]
    assert len(encoded) == 115
    assert payload_digest_for(payload) == fixture["payload_digest"]
    preimage = event_preimage(
        authority_mode=fixture["authority_mode"],
        ledger_id=fixture["ledger_id"],
        chain_id=fixture["chain_id"],
        physical_sequence=fixture["physical_sequence"],
        evidence_sequence=fixture["evidence_sequence"],
        semantic_sequence=fixture["semantic_sequence"],
        event_id=fixture["event_id"],
        event_kind=fixture["event_kind"],
        operation_id=fixture["operation_id"],
        causation_id=fixture["causation_id"],
        correlation_id=fixture["correlation_id"],
        recovery_id=fixture["recovery_id"],
        previous_physical_digest=fixture["previous_physical_digest"],
        previous_evidence_digest=fixture["previous_evidence_digest"],
        payload=payload,
    )
    assert preimage.hex() == fixture["preimage_hex"]
    assert len(preimage) == 551
    assert hashlib.sha256(preimage).hexdigest() == fixture["event_hash"]
    offset = len(b"NBF08-CHAIN-CONTROL-EVENT-V1\x00")
    mode, offset = _take_f(preimage, offset)
    ledger, offset = _take_f(preimage, offset)
    chain, offset = _take_f(preimage, offset)
    physical, offset = _take_u64(preimage, offset)
    evidence, offset = _take_u64(preimage, offset)
    semantic, offset = _take_u64(preimage, offset)
    assert (mode, ledger, chain) == ("file", "ledger-demo", "chain-demo")
    assert (physical, evidence, semantic) == (7, 3, 2)
    assert compute_event_hash(
        authority_mode="file",
        ledger_id="ledger-demo",
        chain_id="chain-demo",
        physical_sequence=7,
        evidence_sequence=3,
        semantic_sequence=2,
        event_id="evt-0007",
        event_kind="chain_control.committed",
        operation_id="op-0001",
        causation_id="intent-0001",
        correlation_id="corr-0001",
        recovery_id="none",
        previous_physical_digest="0" * 64,
        previous_evidence_digest="1" * 64,
        payload=payload,
    ) == fixture["event_hash"]


def _take_u64(data: bytes, offset: int) -> tuple[int, int]:
    return int.from_bytes(data[offset : offset + 8], "big"), offset + 8


def _take_f(data: bytes, offset: int) -> tuple[str, int]:
    length, offset = _take_u64(data, offset)
    return data[offset : offset + length].decode("utf-8"), offset + length


def test_envelope_emits_every_key_and_rejects_omitted_or_reserved_payload() -> None:
    envelope = build_envelope(
        event_kind="chain_control.intent",
        operation_id="op-1",
        causation_id="op-1",
        correlation_id="op-1",
        recovery_id="none",
        chain_id="chain-a",
        authority_mode="file",
        ledger_id="ledger-a",
        physical_sequence=0,
        evidence_sequence=1,
        semantic_sequence=0,
        previous_physical_digest="0" * 64,
        previous_evidence_digest="0" * 64,
        payload={"ok": True},
        semantic_effect="no_change",
        claim_class="required",
        parent_chain_id=None,
        child_id=ABSENT,
        expected_cursor=None,
    )
    assert set(envelope) >= set(ENVELOPE_FIELDS)
    with pytest.raises(ChainControlHold, match="reserved"):
        build_envelope(
            event_kind="chain_control.intent",
            operation_id="op-1",
            causation_id="op-1",
            correlation_id="op-1",
            recovery_id="none",
            chain_id="chain-a",
            authority_mode="file",
            ledger_id="ledger-a",
            physical_sequence=0,
            evidence_sequence=1,
            semantic_sequence=0,
            previous_physical_digest="0" * 64,
            previous_evidence_digest="0" * 64,
            payload={"__nbf08_absent__": True},
            semantic_effect="no_change",
            claim_class="required",
        )


def test_nbf01_seq_sidecar_bytes_remain_integer(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    first = ledger.append_event(
        {
            "schema_version": 1,
            "event_id": "evt-1",
            "ts": "2026-07-03T19:19:00Z",
            "scope": "repair_system",
            "outcome": "started",
            "incident_id": "inc-123",
            "type": "opened",
            "actor": "system",
            "summary": "incident created",
            "evidence": ["logs/app.log"],
            "next_expected_event": None,
            "deadline_ts": None,
            "parent_event_ids": [],
            "trigger_event_id": None,
        }
    )
    second = ledger.append_event(
        {
            "schema_version": 1,
            "event_id": "evt-2",
            "ts": "2026-07-03T19:19:01Z",
            "scope": "repair_system",
            "outcome": "verified",
            "incident_id": "inc-123",
            "type": "updated",
            "actor": "system",
            "summary": "incident updated",
            "evidence": ["logs/app.log"],
            "next_expected_event": None,
            "deadline_ts": None,
            "parent_event_ids": ["evt-1"],
            "trigger_event_id": None,
        }
    )
    assert [first["seq"], second["seq"]] == [0, 1]
    assert (ledger.ledger_dir / ".events.seq").read_text(encoding="utf-8") == "1"


def test_chain_control_append_uses_one_physical_door(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    journal = ChainControlJournal(ledger)
    genesis = journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    assert genesis["event_kind"] == "chain_control.genesis_accepted"
    result = journal.mutate(
        chain_id="chain-demo",
        operation_id="op-save-1",
        intent_kind="save_chain_state",
        actor={"id": "t", "class": "test"},
        effect=lambda txn: {
            "pre_state_digest": "0" * 64,
            "post_state_digest": "a" * 64,
            "actual_cursor": 0,
        },
    )
    assert result["outcome"] == "committed"
    replay = journal.replay_strict()
    kinds = [event["event_kind"] for event in replay["accepted"]]
    assert kinds[0] == "chain_control.genesis_accepted"
    assert "chain_control.intent" in kinds
    assert "chain_control.claimed" in kinds
    assert "chain_control.committed" in kinds
    lines = ledger.events_path.read_text(encoding="utf-8").splitlines()
    assert any(json.loads(line)["kind"].startswith("chain_control.") for line in lines)


def test_same_operation_key_replays_without_second_effect(tmp_path: Path) -> None:
    journal = ChainControlJournal(IncidentLedger(tmp_path))
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    calls = {"n": 0}

    def effect(_txn: LockedChainControlTransaction) -> dict[str, object]:
        calls["n"] += 1
        return {"pre_state_digest": "0" * 64, "post_state_digest": "b" * 64}

    first = journal.mutate(
        chain_id="chain-demo",
        operation_id="op-idem",
        intent_kind="advance",
        actor={"id": "t", "class": "test"},
        effect=effect,
    )
    second = journal.mutate(
        chain_id="chain-demo",
        operation_id="op-idem",
        intent_kind="advance",
        actor={"id": "t", "class": "test"},
        effect=effect,
    )
    assert first["outcome"] == "committed"
    assert second["outcome"] == "replay"
    assert calls["n"] == 1
    assert second["result"]["event_id"] == first["result"]["event_id"]


def test_runtime_rebound_is_a_replayable_typed_commit(tmp_path: Path) -> None:
    journal = ChainControlJournal(IncidentLedger(tmp_path))
    journal.ensure_genesis(chain_id="chain-runtime", actor={"id": "t", "class": "test"})
    calls = {"n": 0}

    def effect(_txn: LockedChainControlTransaction) -> dict[str, object]:
        calls["n"] += 1
        return {
            "pre_state_digest": "0" * 64,
            "post_state_digest": "c" * 64,
            "runtime_identity": {"from": {"content_sha256": "a" * 64}, "to": {"content_sha256": "b" * 64}},
            "chain_spec_sha256": "d" * 64,
            "provenance_link": "receipt.json",
        }

    first = journal.mutate(
        chain_id="chain-runtime",
        operation_id="op-runtime-rebound",
        intent_kind="runtime-rebind",
        actor={"id": "t", "class": "test"},
        linked_receipts=["receipt.json"],
        committed_event_kind="chain_control.runtime_rebound",
        effect=effect,
    )
    second = journal.mutate(
        chain_id="chain-runtime",
        operation_id="op-runtime-rebound",
        intent_kind="runtime-rebind",
        actor={"id": "t", "class": "test"},
        linked_receipts=["receipt.json"],
        committed_event_kind="chain_control.runtime_rebound",
        effect=effect,
    )
    assert first["outcome"] == "committed"
    assert first["event"]["event_kind"] == "chain_control.runtime_rebound"
    assert first["event"]["semantic_effect"] == "advance"
    assert first["event"]["runtime_identity"]["to"]["content_sha256"] == "b" * 64
    assert second["outcome"] == "replay"
    assert second["result"]["event_id"] == first["result"]["event_id"]
    assert calls["n"] == 1
    kinds = [event["event_kind"] for event in journal.replay_strict()["accepted"]]
    assert kinds.count("chain_control.runtime_rebound") == 1
    assert kinds.count("chain_control.replay") == 1


def test_stale_revision_is_typed_cas_conflict(tmp_path: Path) -> None:
    journal = ChainControlJournal(IncidentLedger(tmp_path))
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"metadata": {"_nbf08_revision": 3}}) + "\n", encoding="utf-8")

    def stale(txn: LockedChainControlTransaction) -> dict[str, object]:
        from arnold_pipelines.megaplan.incident.chain_control import ChainStateAdapter

        adapter = ChainStateAdapter(txn, state_path)
        adapter.cas_write({"metadata": {}}, expected_revision=1)
        return {}

    result = journal.mutate(
        chain_id="chain-demo",
        operation_id="op-cas",
        intent_kind="save_chain_state",
        actor={"id": "t", "class": "test"},
        state_paths=[state_path],
        expected_revision=1,
        effect=stale,
    )
    assert result["outcome"] == "cas_conflict"
    assert isinstance(result["error"], ChainControlCasConflict)


def test_lock_order_is_sequence_then_sorted_chain_then_state(tmp_path: Path) -> None:
    journal = ChainControlJournal(IncidentLedger(tmp_path))
    parent = tmp_path / "parent.json"
    child = tmp_path / "child.json"
    parent.write_text("{}\n", encoding="utf-8")
    child.write_text("{}\n", encoding="utf-8")
    txn = journal.transaction(
        chain_ids=["zeta", "alpha"],
        state_paths=[child, parent],
        operation_id="op-locks",
        actor={"id": "t", "class": "test"},
    )
    with txn:
        assert txn.chain_ids == ("alpha", "zeta")
        assert txn.state_paths == (child.resolve(), parent.resolve())
        assert txn._seq_fd is not None
        assert len(txn._lock_fds) == 4


def test_missing_state_stays_absent_when_effect_fails(tmp_path: Path) -> None:
    journal = ChainControlJournal(IncidentLedger(tmp_path))
    journal.ensure_genesis(chain_id="chain-missing", actor={"id": "t", "class": "test"})
    state_path = tmp_path / "state.json"

    def fail(_txn: LockedChainControlTransaction) -> dict[str, object]:
        raise RuntimeError("simulated pre-write failure")

    with pytest.raises(RuntimeError, match="simulated pre-write failure"):
        journal.mutate(
            chain_id="chain-missing",
            operation_id="op-missing-fail",
            intent_kind="start",
            actor={"id": "t", "class": "test"},
            state_paths=[state_path],
            effect=fail,
        )

    assert not state_path.exists()
    assert (tmp_path / "state.json.lock").exists()


def test_first_state_write_creates_valid_json_after_sidecar_lock(tmp_path: Path) -> None:
    journal = ChainControlJournal(IncidentLedger(tmp_path))
    journal.ensure_genesis(chain_id="chain-first", actor={"id": "t", "class": "test"})
    state_path = tmp_path / "state.json"

    def write(txn: LockedChainControlTransaction) -> dict[str, object]:
        from arnold_pipelines.megaplan.incident.chain_control import ChainStateAdapter

        payload = ChainStateAdapter(txn, state_path).cas_write(
            {"current_milestone_index": 0, "metadata": {}},
            expected_revision=None,
        )
        return {
            "pre_state_digest": "0" * 64,
            "post_state_digest": "1" * 64,
            "actual_cursor": 0,
            "payload": payload,
        }

    result = journal.mutate(
        chain_id="chain-first",
        operation_id="op-first-write",
        intent_kind="start",
        actor={"id": "t", "class": "test"},
        state_paths=[state_path],
        effect=write,
    )

    assert result["outcome"] == "committed"
    assert json.loads(state_path.read_text(encoding="utf-8"))["current_milestone_index"] == 0


def test_lifecycle_prewrite_failure_does_not_materialize_chain_state(tmp_path: Path) -> None:
    spec_path = tmp_path / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    state_path = _state_path_for(spec_path)

    def fail(_txn: LockedChainControlTransaction) -> dict[str, object]:
        raise RuntimeError("simulated lifecycle failure")

    with pytest.raises(RuntimeError, match="simulated lifecycle failure"):
        apply_chain_lifecycle(
            spec_path,
            tmp_path,
            intent_kind="start",
            actor={"id": "t", "class": "test"},
            effect=fail,
        )

    assert not state_path.exists()
    assert state_path.with_name(state_path.name + ".lock").exists()
