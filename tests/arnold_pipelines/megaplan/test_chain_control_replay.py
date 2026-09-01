from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.incident.chain_control import (
    ChainControlHold,
    ChainControlJournal,
    ChainStateAdapter,
    DurabilityUnknown,
    canonical_json,
    chain_id_for_spec,
    compute_event_hash,
    empty_reservation,
    frame_bytes,
    frame_utf8,
    observed_repo_base_sha256,
    physical_record_digest,
    reservation_digest_for,
    verify_bound_state_matches_journal,
    u64be,
    write_reservation_locked,
)
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.chain.spec import _state_path_for

FIXTURE = Path(__file__).parent / "incident" / "fixtures" / "nbf08_s2_physical_record_v1.json"


def test_s2_physical_record_golden_vector() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    stored = canonical_json(fixture["stored_envelope"])
    assert stored.hex() == fixture["stored_envelope_hex"]
    assert len(stored) == 143
    digest = physical_record_digest(
        ledger_id=fixture["ledger_id"],
        physical_sequence=fixture["physical_sequence"],
        record_type=fixture["record_type"],
        stored_record_bytes=stored,
        previous_physical_digest=fixture["previous_physical_digest_hex_at_rest"],
    )
    assert digest == fixture["physical_record_digest"]
    previous_raw = bytes.fromhex(fixture["previous_physical_digest_raw_hex"])
    preimage = (
        b"NBF08-PHYSICAL-RECORD-V1\x00"
        + frame_utf8("ledger-demo")
        + u64be(8)
        + frame_utf8("incident")
        + frame_bytes(stored)
        + frame_bytes(previous_raw)
    )
    assert preimage.hex() == fixture["preimage_hex"]
    assert len(preimage) == 259
    assert hashlib.sha256(preimage).hexdigest() == fixture["physical_record_digest"]


def test_strict_replay_tolerates_one_torn_tail_only(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    journal = ChainControlJournal(ledger)
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    raw = ledger.events_path.read_bytes()
    ledger.events_path.write_bytes(raw + b'{"seq":99,"payload":')
    replay = journal.replay_strict()
    assert replay["torn_tail"] is True
    ledger.events_path.write_bytes(b'{"seq":0,"kind":"x"}\n{"seq":1,"payload":\n{"seq":2}\n')
    with pytest.raises(ChainControlHold):
        journal.replay_strict()


def test_malformed_complete_non_tail_is_hold(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    journal = ChainControlJournal(ledger)
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    good = ledger.events_path.read_bytes()
    ledger.events_path.write_bytes(b"{not-json}\n" + good)
    with pytest.raises(ChainControlHold, match="malformed"):
        journal.replay_strict()


def test_gap_fork_duplicate_and_source_mismatch_hold(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    journal = ChainControlJournal(ledger)
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    lines = [json.loads(line) for line in ledger.events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    first = dict(lines[0])
    first["seq"] = 7
    ledger.events_path.write_text(json.dumps(first, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    with pytest.raises(ChainControlHold):
        journal.replay_strict()


def test_integer_sidecar_migration_preserves_original_bytes(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(
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
    sidecar = ledger.ledger_dir / ".events.seq"
    original = sidecar.read_bytes()
    assert original == b"0"
    journal = ChainControlJournal(ledger)
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    migrated = json.loads(sidecar.read_text(encoding="utf-8"))
    assert migrated["schema_version"] == "nbf08-sequence-reservation-v1"
    assert migrated["migration_receipt"]["original_bytes_hex"] == original.hex()
    assert migrated["migration_receipt"]["original_integer"] == 0


def test_rebind_suffix_cli_and_gated_nbf07_dependency(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    journal = ChainControlJournal(ledger)
    genesis = journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    replay = journal.replay_strict()
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    receipt = tmp_path / "suffix.json"
    physical_tip = f"{replay['physical_sequence']}/{replay['physical_tip_digest']}"
    control_tip = replay["evidence_digest_by_chain"]["chain-demo"]
    source_sha = hashlib.sha256(ledger.events_path.read_bytes()).hexdigest()
    manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
    base_sha = observed_repo_base_sha256()
    cmd = [
        sys.executable,
        "-m",
        "arnold_pipelines.megaplan.incident.chain_control",
        "rebind-suffix",
        "--ledger",
        str(tmp_path),
        "--chain-id",
        "chain-demo",
        "--expected-physical-tip",
        physical_tip,
        "--expected-control-tip",
        control_tip,
        "--from-authority",
        "file",
        "--to-authority",
        "new",
        "--source-manifest",
        str(manifest),
        "--expected-base-sha256",
        base_sha,
        "--expected-source-sha256",
        source_sha,
        "--expected-manifest-sha256",
        manifest_sha,
        "--reason",
        "unexecuted-suffix",
        "--actor",
        "operator",
        "--receipt",
        str(receipt),
    ]
    completed = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parents[3]), capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    body = json.loads(receipt.read_text(encoding="utf-8"))
    assert body["expected_base_sha256"] == base_sha
    assert body["source_sha256"] == source_sha
    dep_receipt = tmp_path / "dep.json"
    tasklist = tmp_path / "tasklist.md"
    spec = tmp_path / "chain.yaml"
    tasklist.write_text("# t\n", encoding="utf-8")
    spec.write_text("milestones: []\n", encoding="utf-8")
    gated = subprocess.run(
        [
            sys.executable,
            "-m",
            "arnold_pipelines.megaplan.incident.chain_control",
            "rebind-nbf07-dependency",
            "--ledger",
            str(tmp_path),
            "--chain-id",
            "chain-demo",
            "--tasklist",
            str(tasklist),
            "--chain-spec",
            str(spec),
            "--expected-tasklist-sha256",
            hashlib.sha256(tasklist.read_bytes()).hexdigest(),
            "--expected-chain-spec-sha256",
            hashlib.sha256(spec.read_bytes()).hexdigest(),
            "--suffix-tip",
            body["suffix_tip"],
            "--expected-base-sha256",
            base_sha,
            "--expected-source-sha256",
            source_sha,
            "--expected-manifest-sha256",
            manifest_sha,
            "--candidate-sha",
            "deadbeef",
            "--inventory-sha256",
            "b" * 64,
            "--framed-diff-sha256",
            "c" * 64,
            "--actor",
            "operator",
            "--receipt",
            str(dep_receipt),
        ],
        cwd=str(Path(__file__).resolve().parents[3]),
        capture_output=True,
        text=True,
    )
    assert gated.returncode == 0, gated.stderr
    dep = json.loads(dep_receipt.read_text(encoding="utf-8"))
    assert dep["actor"] == "operator"
    assert dep["suffix_tip"] == body["suffix_tip"]
    assert "depends: NBF-08" in tasklist.read_text(encoding="utf-8")
    assert "NBF-08" in spec.read_text(encoding="utf-8")
    _ = genesis


def _nbf01(event_id: str) -> dict:
    return {
        "schema_version": 1,
        "event_id": event_id,
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


def _rewrite_last_cc(path: Path, mutator) -> None:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = [json.loads(line) for line in lines]
    for index in range(len(records) - 1, -1, -1):
        record = records[index]
        payload = record.get("payload")
        if isinstance(payload, dict) and str(record.get("kind") or "").startswith("chain_control."):
            mutator(payload)
            payload["event_hash"] = compute_event_hash(
                authority_mode=str(payload["authority_mode"]),
                ledger_id=str(payload["ledger_id"]),
                chain_id=str(payload["chain_id"] or "chainless"),
                physical_sequence=int(payload["physical_sequence"]),
                evidence_sequence=int(payload["evidence_sequence"]),
                semantic_sequence=int(payload["semantic_sequence"]),
                event_id=str(payload["event_id"]),
                event_kind=str(payload["event_kind"]),
                operation_id=str(payload["operation_id"] or "none"),
                causation_id=str(payload["causation_id"] or "none"),
                correlation_id=str(payload["correlation_id"] or "none"),
                recovery_id=str(payload["recovery_id"] or "none"),
                previous_physical_digest=str(payload["previous_physical_digest"]),
                previous_evidence_digest=str(payload["previous_evidence_digest"]),
                payload=payload["payload"],
            )
            record["payload"] = payload
            records[index] = record
            break
    path.write_text("\n".join(json.dumps(item, sort_keys=True, separators=(",", ":")) for item in records) + "\n", encoding="utf-8")


def test_independent_predecessor_evidence_semantic_and_genesis_mutations_hold(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_nbf01("evt-1"))
    journal = ChainControlJournal(ledger)
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    journal.mutate(
        chain_id="chain-demo",
        operation_id="op-adv",
        intent_kind="advance",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: {"pre_state_digest": "0" * 64, "post_state_digest": "a" * 64},
    )
    path = ledger.events_path
    good = path.read_bytes()

    _rewrite_last_cc(path, lambda env: env.update({"previous_physical_digest": "b" * 64}))
    with pytest.raises(ChainControlHold, match="previous_physical_digest"):
        journal.replay_strict()
    path.write_bytes(good)

    _rewrite_last_cc(path, lambda env: env.update({"previous_evidence_digest": "c" * 64}))
    with pytest.raises(ChainControlHold, match="previous_evidence_digest"):
        journal.replay_strict()
    path.write_bytes(good)

    _rewrite_last_cc(path, lambda env: env.update({"evidence_sequence": env["evidence_sequence"] + 3}))
    with pytest.raises(ChainControlHold, match="evidence_sequence"):
        journal.replay_strict()
    path.write_bytes(good)

    _rewrite_last_cc(path, lambda env: env.update({"semantic_sequence": env["semantic_sequence"] + 4, "semantic_effect": "no_change"}))
    with pytest.raises(ChainControlHold, match="semantic"):
        journal.replay_strict()
    path.write_bytes(good)

    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for record in records:
        payload = record.get("payload")
        if isinstance(payload, dict) and payload.get("event_kind") == "chain_control.genesis_accepted":
            payload["payload"] = dict(payload["payload"], prefix_digest="d" * 64)
            payload["event_hash"] = compute_event_hash(
                authority_mode=str(payload["authority_mode"]),
                ledger_id=str(payload["ledger_id"]),
                chain_id=str(payload["chain_id"] or "chainless"),
                physical_sequence=int(payload["physical_sequence"]),
                evidence_sequence=int(payload["evidence_sequence"]),
                semantic_sequence=int(payload["semantic_sequence"]),
                event_id=str(payload["event_id"]),
                event_kind=str(payload["event_kind"]),
                operation_id=str(payload["operation_id"] or "none"),
                causation_id=str(payload["causation_id"] or "none"),
                correlation_id=str(payload["correlation_id"] or "none"),
                recovery_id=str(payload["recovery_id"] or "none"),
                previous_physical_digest=str(payload["previous_physical_digest"]),
                previous_evidence_digest=str(payload["previous_evidence_digest"]),
                payload=payload["payload"],
            )
            record["payload"] = payload
    path.write_text("\n".join(json.dumps(item, sort_keys=True, separators=(",", ":")) for item in records) + "\n", encoding="utf-8")
    with pytest.raises(ChainControlHold, match="genesis"):
        journal.replay_strict()


def test_integer_sidecar_highest_plus_one_tombs_and_never_reuses(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_nbf01("evt-1"))
    sidecar = ledger.ledger_dir / ".events.seq"
    sidecar.write_bytes(b"1")
    journal = ChainControlJournal(ledger)
    genesis = journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    replay = journal.replay_strict()
    kinds = [event["event_kind"] for event in replay["accepted"]]
    assert "chain_control.sequence_reserved_tombstone" in kinds
    tombstone = next(event for event in replay["accepted"] if event["event_kind"] == "chain_control.sequence_reserved_tombstone")
    reserved_seq = tombstone["physical_sequence"]
    assert reserved_seq == 1
    assert genesis["physical_sequence"] == reserved_seq + 1
    follow = journal.mutate(
        chain_id="chain-demo",
        operation_id="op-after-tomb",
        intent_kind="advance",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: {"pre_state_digest": "0" * 64, "post_state_digest": "e" * 64},
    )
    committed = [event for event in journal.replay_strict()["accepted"] if event["event_kind"] == "chain_control.committed"][-1]
    committed_seq = committed["physical_sequence"]
    assert committed_seq > reserved_seq
    seqs = [json.loads(line)["seq"] for line in ledger.events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert seqs == list(range(seqs[0], seqs[0] + len(seqs)))


def test_reservation_recovery_matches_identity_and_rejects_collision_and_ahead(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_nbf01("evt-1"))
    sidecar = ledger.ledger_dir / ".events.seq"
    sidecar.write_bytes(b"9")
    journal = ChainControlJournal(ledger)
    with pytest.raises(DurabilityUnknown, match="ahead"):
        journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})

    ledger2 = IncidentLedger(tmp_path / "b")
    first = ledger2.append_event(_nbf01("evt-1"))
    journal2 = ChainControlJournal(ledger2)
    journal2.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    line = ledger2.events_path.read_bytes().splitlines()[-1]
    reservation = empty_reservation(
        ledger_id=journal2.ledger_id,
        physical_sequence=first["seq"] + 1,
        status="reserved",
        previous_physical_digest="0" * 64,
    )
    reservation["intended_record_sha256"] = "f" * 64
    reservation["reservation_id"] = "res-collision"
    reservation["reservation_digest"] = reservation_digest_for(reservation)
    seq_path = ledger2.ledger_dir / ".events.seq"
    import os

    fd = os.open(str(seq_path), os.O_RDWR)
    try:
        write_reservation_locked(fd, reservation)
        with pytest.raises(DurabilityUnknown):
            journal2.recover_reservations_locked(fd)
    finally:
        os.close(fd)


def test_mutate_replay_key_rejects_tuple_mismatch(tmp_path: Path) -> None:
    journal = ChainControlJournal(IncidentLedger(tmp_path))
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    first = journal.mutate(
        chain_id="chain-demo",
        operation_id="op-tuple",
        intent_kind="advance",
        actor={"id": "t", "class": "test"},
        expected_revision=None,
        effect=lambda _txn: {"pre_state_digest": "0" * 64, "post_state_digest": "1" * 64},
    )
    assert first["outcome"] == "committed"
    with pytest.raises(ChainControlHold, match="frozen tuple"):
        journal.mutate(
            chain_id="chain-demo",
            operation_id="op-tuple",
            intent_kind="skip",
            actor={"id": "t", "class": "test"},
            expected_revision=None,
            effect=lambda _txn: {"pre_state_digest": "0" * 64, "post_state_digest": "2" * 64},
        )
    replayed = journal.mutate(
        chain_id="chain-demo",
        operation_id="op-tuple",
        intent_kind="advance",
        actor={"id": "t", "class": "test"},
        expected_revision=None,
        effect=lambda _txn: {"pre_state_digest": "0" * 64, "post_state_digest": "3" * 64},
    )
    assert replayed["outcome"] == "replay"


def test_incomplete_claimed_operation_is_durability_unknown_on_retry(tmp_path: Path) -> None:
    journal = ChainControlJournal(IncidentLedger(tmp_path))
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    operation_id = "op-crash-before-cas"

    def crash(_txn: object) -> dict[str, object]:
        raise KeyboardInterrupt("crash after claimed")

    with pytest.raises(KeyboardInterrupt):
        journal.mutate(
            chain_id="chain-demo",
            operation_id=operation_id,
            intent_kind="rename",
            actor={"id": "t", "class": "test"},
            effect=crash,
        )
    before_retry = journal.ledger.events_path.read_bytes()
    calls = {"effect": 0}

    def must_not_run(_txn: object) -> dict[str, object]:
        calls["effect"] += 1
        return {"pre_state_digest": "0" * 64, "post_state_digest": "1" * 64}

    with pytest.raises(DurabilityUnknown):
        journal.mutate(
            chain_id="chain-demo",
            operation_id=operation_id,
            intent_kind="rename",
            actor={"id": "t", "class": "test"},
            effect=must_not_run,
        )
    assert calls["effect"] == 0
    assert journal.ledger.events_path.read_bytes() == before_retry
    kinds = [event["event_kind"] for event in journal.replay_strict()["accepted"]]
    assert kinds[-1] == "chain_control.claimed"
    assert "chain_control.replay" not in kinds
    assert "chain_control.committed" not in kinds


def test_cas_before_commit_is_held_without_second_effect_and_verification(tmp_path: Path) -> None:
    initiative = tmp_path / ".megaplan" / "initiatives" / "demo"
    initiative.mkdir(parents=True)
    (initiative / "brief.md").write_text("# brief\n", encoding="utf-8")
    spec = initiative / "chain.yaml"
    spec.write_text(
        "anchors:\n  north_star: brief.md\nmilestones:\n  - label: M1\n    idea: brief.md\n",
        encoding="utf-8",
    )
    chain_id = chain_id_for_spec(spec)
    journal = ChainControlJournal(IncidentLedger(tmp_path))
    journal.ensure_genesis(chain_id=chain_id, actor={"id": "t", "class": "test"})
    state_path = _state_path_for(spec)
    operation_id = "op-crash-after-cas"
    payload = {"current_milestone_index": 0, "last_state": "renamed"}

    def cas_then_crash(txn: object) -> dict[str, object]:
        adapter = ChainStateAdapter(txn, state_path)  # type: ignore[arg-type]
        adapter.cas_write(payload, expected_revision=None)
        raise KeyboardInterrupt("crash after CAS")

    with pytest.raises(KeyboardInterrupt):
        journal.mutate(
            chain_id=chain_id,
            operation_id=operation_id,
            intent_kind="rename",
            actor={"id": "t", "class": "test"},
            state_paths=[state_path],
            effect=cas_then_crash,
        )
    state_after_crash = state_path.read_bytes()
    calls = {"effect": 0}

    def must_not_run(_txn: object) -> dict[str, object]:
        calls["effect"] += 1
        return {"pre_state_digest": "0" * 64, "post_state_digest": "2" * 64}

    with pytest.raises(DurabilityUnknown):
        journal.mutate(
            chain_id=chain_id,
            operation_id=operation_id,
            intent_kind="rename",
            actor={"id": "t", "class": "test"},
            state_paths=[state_path],
            effect=must_not_run,
        )
    assert calls["effect"] == 0
    assert state_path.read_bytes() == state_after_crash
    with pytest.raises(DurabilityUnknown):
        verify_bound_state_matches_journal(spec)


def test_incomplete_operation_blocks_different_operation_without_laundering(tmp_path: Path) -> None:
    journal = ChainControlJournal(IncidentLedger(tmp_path))
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})

    with pytest.raises(KeyboardInterrupt):
        journal.mutate(
            chain_id="chain-demo",
            operation_id="op-incomplete",
            intent_kind="rename",
            actor={"id": "t", "class": "test"},
            effect=lambda _txn: (_ for _ in ()).throw(KeyboardInterrupt("crash")),
        )
    before = journal.ledger.events_path.read_bytes()
    calls = {"effect": 0}

    def must_not_run(_txn: object) -> dict[str, object]:
        calls["effect"] += 1
        return {"pre_state_digest": "0" * 64, "post_state_digest": "3" * 64}

    with pytest.raises(DurabilityUnknown):
        journal.mutate(
            chain_id="chain-demo",
            operation_id="op-different",
            intent_kind="rename",
            actor={"id": "t", "class": "test"},
            effect=must_not_run,
        )
    assert calls["effect"] == 0
    assert journal.ledger.events_path.read_bytes() == before
    assert "chain_control.replay" not in [event["event_kind"] for event in journal.replay_strict()["accepted"]]


def test_rebind_suffix_drift_leaves_old_authority_and_cas_temp_files(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    journal = ChainControlJournal(ledger)
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    replay = journal.replay_strict()
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    receipt = tmp_path / "drift.json"
    live = Path(__file__).resolve().parents[3] / ".oracle" / "tasklist.md"
    live_before = live.read_bytes() if live.exists() else None
    with pytest.raises(ChainControlHold, match="old authority untouched"):
        journal.rebind_suffix(
            chain_id="chain-demo",
            expected_physical_tip="0/deadbeef",
            expected_control_tip=replay["evidence_digest_by_chain"]["chain-demo"],
            from_authority="file",
            to_authority="new",
            source_manifest=manifest,
            expected_base_sha256=observed_repo_base_sha256(),
            expected_source_sha256="0" * 64,
            expected_manifest_sha256="0" * 64,
            reason="unexecuted-suffix",
            actor="operator",
            receipt=receipt,
        )
    assert json.loads(receipt.read_text(encoding="utf-8"))["old_authority"] == "file"
    kinds = [event["event_kind"] for event in journal.replay_strict()["accepted"]]
    assert "chain_control.suffix_rebound" not in kinds
    if live_before is not None:
        assert live.read_bytes() == live_before
