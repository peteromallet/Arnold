from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.incident.chain_control import (
    ChainControlHold,
    ChainControlJournal,
    ChainStateAdapter,
    DurabilityUnknown,
    build_envelope,
    canonical_json,
    chain_id_for_spec,
    compute_event_hash,
    empty_reservation,
    frame_bytes,
    frame_utf8,
    observed_repo_base_sha256,
    parse_sidecar_bytes,
    physical_record_digest,
    read_physical_lines,
    reservation_digest_for,
    stored_line_sha256,
    verify_bound_state_matches_journal,
    workspace_snapshot_sha256,
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


def test_nonempty_migrated_ledger_multi_append_has_one_exact_physical_sequence(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_nbf01("evt-1"))
    ledger.append_event({**_nbf01("evt-2"), "outcome": "verified", "type": "updated"})
    journal = ChainControlJournal(ledger)
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    journal.mutate(
        chain_id="chain-demo",
        operation_id="op-multi",
        intent_kind="advance",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: {"pre_state_digest": "0" * 64, "post_state_digest": "1" * 64},
    )
    physical = read_physical_lines(ledger.events_path)
    seqs = [item.record["seq"] for item in physical]
    assert seqs == list(range(seqs[0], seqs[0] + len(seqs)))
    for item in physical:
        if str(item.record.get("kind") or "").startswith("chain_control."):
            assert item.record["seq"] == item.record["payload"]["physical_sequence"]
    replay = journal.replay_strict()
    _, sidecar = parse_sidecar_bytes((ledger.ledger_dir / ".events.seq").read_bytes())
    assert sidecar["physical_sequence"] == replay["physical_sequence"]
    assert sidecar["intended_record_sha256"] == stored_line_sha256(physical[-1].raw)


def test_stale_committed_reservation_rejects_before_append(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    journal = ChainControlJournal(ledger)
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    sidecar_path = ledger.ledger_dir / ".events.seq"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["physical_sequence"] -= 1
    sidecar["reservation_digest"] = reservation_digest_for(sidecar)
    sidecar_path.write_bytes(canonical_json(sidecar))
    before_events = ledger.events_path.read_bytes()
    before_sidecar = sidecar_path.read_bytes()
    with pytest.raises(DurabilityUnknown, match="stale"):
        journal.mutate(
            chain_id="chain-demo",
            operation_id="op-stale-sidecar",
            intent_kind="advance",
            actor={"id": "t", "class": "test"},
            effect=lambda _txn: {"pre_state_digest": "0" * 64, "post_state_digest": "1" * 64},
        )
    assert ledger.events_path.read_bytes() == before_events
    assert sidecar_path.read_bytes() == before_sidecar


def _trailing_collision_fixture(tmp_path: Path) -> dict[str, object]:
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_nbf01("evt-1"))
    journal = ChainControlJournal(ledger)
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    prefix_replay = journal.replay_strict()
    prefix_physical = read_physical_lines(ledger.events_path)
    prefix_sequence = prefix_replay["physical_sequence"]
    operation_id = hashlib.sha256(b"offending-intent").hexdigest()
    envelope = build_envelope(
        event_kind="chain_control.intent",
        operation_id=operation_id,
        causation_id=operation_id,
        correlation_id=operation_id,
        recovery_id="none",
        chain_id="chain-demo",
        authority_mode="file",
        ledger_id=journal.ledger_id,
        physical_sequence=prefix_sequence + 1,
        evidence_sequence=prefix_replay["evidence_by_chain"]["chain-demo"] + 1,
        semantic_sequence=prefix_replay["semantic_by_chain"]["chain-demo"],
        previous_physical_digest=prefix_replay["physical_tip_digest"],
        previous_evidence_digest=prefix_replay["evidence_digest_by_chain"]["chain-demo"],
        payload={"intent_kind": "failed_prechain_recovery", "expected_revision": None},
        semantic_effect="no_change",
        claim_class="required",
        actor={"id": "operator", "class": "operator"},
        intent="failed_prechain_recovery",
    )
    outer = {
        "seq": prefix_sequence,
        "schema_version": 1,
        "ts_utc": "2026-09-02T00:00:00+00:00",
        "ts_rel_init_s": None,
        "kind": "chain_control.intent",
        "payload": envelope,
        "idempotency_key": envelope["event_id"],
    }
    offending_line = canonical_json(outer)
    ledger.events_path.write_bytes(ledger.events_path.read_bytes() + offending_line + b"\n")
    sidecar_path = ledger.ledger_dir / ".events.seq"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["status"] = "reserved"
    sidecar["physical_sequence"] = prefix_sequence
    sidecar["previous_physical_digest"] = "0" * 64
    sidecar["reservation_digest"] = reservation_digest_for(sidecar)
    sidecar_path.write_bytes(canonical_json(sidecar))
    marker = tmp_path / "marker.json"
    manifest = tmp_path / "manifest.json"
    spec = tmp_path / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"launch_outcome":{"code":"launch_not_advanced","status":"failed"}}\n')
    manifest.write_text('{"generation":1,"status":"failed"}\n')
    spec.write_text("milestones: []\n", encoding="utf-8")
    custody = tmp_path / "custody"
    receipt = tmp_path / "migration-receipt.json"
    kwargs: dict[str, object] = {
        "expected_journal_sha256": hashlib.sha256(ledger.events_path.read_bytes()).hexdigest(),
        "expected_sidecar_sha256": hashlib.sha256(sidecar_path.read_bytes()).hexdigest(),
        "expected_prefix_sequence": prefix_sequence,
        "expected_prefix_line_sha256": stored_line_sha256(prefix_physical[-1].raw),
        "expected_prefix_digest": prefix_replay["physical_tip_digest"],
        "expected_offending_line_sha256": hashlib.sha256(offending_line).hexdigest(),
        "expected_operation_id": operation_id,
        "expected_event_id": envelope["event_id"],
        "marker_path": marker,
        "expected_marker_sha256": hashlib.sha256(marker.read_bytes()).hexdigest(),
        "manifest_path": manifest,
        "expected_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "spec_path": spec,
        "expected_spec_sha256": hashlib.sha256(spec.read_bytes()).hexdigest(),
        "workspace_path": tmp_path,
        "custody_dir": custody,
        "receipt_path": receipt,
        "actor": "operator",
    }
    kwargs["expected_workspace_sha256"] = workspace_snapshot_sha256(
        tmp_path, excluded=(ledger.ledger_dir, custody, receipt)
    )
    return {
        "ledger": ledger,
        "journal": journal,
        "sidecar": sidecar_path,
        "offending_line": offending_line,
        "kwargs": kwargs,
        "marker": marker,
        "manifest": manifest,
        "spec": spec,
        "custody": custody,
        "receipt": receipt,
    }


def test_guarded_trailing_collision_migration_preserves_custody_and_replays(tmp_path: Path) -> None:
    fixture = _trailing_collision_fixture(tmp_path)
    journal = fixture["journal"]
    kwargs = fixture["kwargs"]
    old_events = fixture["ledger"].events_path.read_bytes()
    old_sidecar = fixture["sidecar"].read_bytes()
    first = journal.quarantine_trailing_sequence_collision(**kwargs)
    assert first["outcome"] == "committed"
    replay = journal.replay_strict()
    assert replay["physical_sequence"] == kwargs["expected_prefix_sequence"] + 1
    assert replay["accepted"][-1]["event_kind"] == "chain_control.trailing_sequence_collision_quarantined"
    receipt = first["receipt"]
    custody_manifest = Path(receipt["custody_manifest"])
    custody_root = custody_manifest.parent
    assert (custody_root / "original-events.jsonl").read_bytes() == old_events
    assert (custody_root / "original-sidecar").read_bytes() == old_sidecar
    assert (custody_root / "offending-line.jsonl").read_bytes() == fixture["offending_line"] + b"\n"
    assert hashlib.sha256(fixture["ledger"].events_path.read_bytes()).hexdigest() == receipt["new_journal_sha256"]
    second = journal.quarantine_trailing_sequence_collision(**kwargs)
    assert second["outcome"] == "replay"
    assert second["receipt"]["migration_event_id"] == receipt["migration_event_id"]


def test_guarded_trailing_collision_replays_after_later_strict_appends(tmp_path: Path) -> None:
    fixture = _trailing_collision_fixture(tmp_path)
    first = fixture["journal"].quarantine_trailing_sequence_collision(**fixture["kwargs"])
    migrated_tip = first["replay"]["physical_sequence"]
    fixture["journal"].mutate(
        chain_id="chain-demo",
        operation_id="op-after-migration",
        intent_kind="advance",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: {"pre_state_digest": "0" * 64, "post_state_digest": "a" * 64},
    )
    replayed = fixture["journal"].quarantine_trailing_sequence_collision(**fixture["kwargs"])
    assert replayed["outcome"] == "replay"
    assert replayed["replay"]["physical_sequence"] > migrated_tip


def test_guarded_trailing_collision_replay_verifies_custody_payloads(tmp_path: Path) -> None:
    fixture = _trailing_collision_fixture(tmp_path)
    first = fixture["journal"].quarantine_trailing_sequence_collision(**fixture["kwargs"])
    preserved = Path(first["receipt"]["custody_manifest"]).parent / "offending-line.jsonl"
    preserved.chmod(0o644)
    preserved.write_bytes(b"tampered\n")
    with pytest.raises(ChainControlHold, match="custody offending line changed"):
        fixture["journal"].quarantine_trailing_sequence_collision(**fixture["kwargs"])


def test_guarded_trailing_collision_cli_commits_exact_guarded_generation(tmp_path: Path) -> None:
    fixture = _trailing_collision_fixture(tmp_path)
    kwargs = fixture["kwargs"]
    cmd = [
        sys.executable,
        "-m",
        "arnold_pipelines.megaplan.incident.chain_control",
        "quarantine-trailing-sequence-collision",
        "--ledger", str(tmp_path),
        "--expected-journal-sha256", str(kwargs["expected_journal_sha256"]),
        "--expected-sidecar-sha256", str(kwargs["expected_sidecar_sha256"]),
        "--expected-prefix-sequence", str(kwargs["expected_prefix_sequence"]),
        "--expected-prefix-line-sha256", str(kwargs["expected_prefix_line_sha256"]),
        "--expected-prefix-digest", str(kwargs["expected_prefix_digest"]),
        "--expected-offending-line-sha256", str(kwargs["expected_offending_line_sha256"]),
        "--expected-operation-id", str(kwargs["expected_operation_id"]),
        "--expected-event-id", str(kwargs["expected_event_id"]),
        "--marker", str(kwargs["marker_path"]),
        "--expected-marker-sha256", str(kwargs["expected_marker_sha256"]),
        "--manifest", str(kwargs["manifest_path"]),
        "--expected-manifest-sha256", str(kwargs["expected_manifest_sha256"]),
        "--spec", str(kwargs["spec_path"]),
        "--expected-spec-sha256", str(kwargs["expected_spec_sha256"]),
        "--workspace", str(kwargs["workspace_path"]),
        "--expected-workspace-sha256", str(kwargs["expected_workspace_sha256"]),
        "--custody-dir", str(kwargs["custody_dir"]),
        "--receipt", str(kwargs["receipt_path"]),
        "--actor", str(kwargs["actor"]),
    ]
    completed = subprocess.run(
        cmd,
        cwd=str(Path(__file__).resolve().parents[3]),
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    receipt = json.loads(completed.stdout)
    assert receipt["outcome"] == "committed"
    assert fixture["journal"].replay_strict()["accepted"][-1]["event_kind"] == "chain_control.trailing_sequence_collision_quarantined"


def test_guarded_trailing_collision_wrong_multiple_and_effectful_inputs_reject(tmp_path: Path) -> None:
    wrong = _trailing_collision_fixture(tmp_path / "wrong")
    before = wrong["ledger"].events_path.read_bytes()
    wrong_kwargs = dict(wrong["kwargs"])
    wrong_kwargs["expected_offending_line_sha256"] = "f" * 64
    with pytest.raises(ChainControlHold):
        wrong["journal"].quarantine_trailing_sequence_collision(**wrong_kwargs)
    assert wrong["ledger"].events_path.read_bytes() == before

    multiple = _trailing_collision_fixture(tmp_path / "multiple")
    multiple["ledger"].events_path.write_bytes(
        multiple["ledger"].events_path.read_bytes() + multiple["offending_line"] + b"\n"
    )
    multiple_kwargs = dict(multiple["kwargs"])
    multiple_kwargs["expected_journal_sha256"] = hashlib.sha256(multiple["ledger"].events_path.read_bytes()).hexdigest()
    with pytest.raises(ChainControlHold, match="prefix"):
        multiple["journal"].quarantine_trailing_sequence_collision(**multiple_kwargs)

    effectful = _trailing_collision_fixture(tmp_path / "effectful")
    effectful["marker"].write_text('{"fixer_owner":"live","launch_outcome":{"status":"failed"}}\n')
    effect_kwargs = dict(effectful["kwargs"])
    effect_kwargs["expected_marker_sha256"] = hashlib.sha256(effectful["marker"].read_bytes()).hexdigest()
    effect_kwargs["expected_workspace_sha256"] = workspace_snapshot_sha256(
        tmp_path / "effectful",
        excluded=(effectful["ledger"].ledger_dir, effectful["custody"], effectful["receipt"]),
    )
    with pytest.raises(ChainControlHold, match="live owner"):
        effectful["journal"].quarantine_trailing_sequence_collision(**effect_kwargs)

    stateful = _trailing_collision_fixture(tmp_path / "stateful")
    state_path = _state_path_for(stateful["spec"])
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text('{"last_state":"running"}\n', encoding="utf-8")
    state_kwargs = dict(stateful["kwargs"])
    state_kwargs["expected_workspace_sha256"] = workspace_snapshot_sha256(
        tmp_path / "stateful",
        excluded=(stateful["ledger"].ledger_dir, stateful["custody"], stateful["receipt"]),
    )
    with pytest.raises(ChainControlHold, match="chain state"):
        stateful["journal"].quarantine_trailing_sequence_collision(**state_kwargs)


@pytest.mark.parametrize("fault_point", ["after_stage", "after_custody_ready", "after_generation_ready", "after_events_switch", "after_sidecar_switch", "after_receipt"])
def test_guarded_trailing_collision_faults_restore_exact_active_bytes(tmp_path: Path, fault_point: str) -> None:
    fixture = _trailing_collision_fixture(tmp_path)
    old_events = fixture["ledger"].events_path.read_bytes()
    old_sidecar = fixture["sidecar"].read_bytes()

    def fail(point: str) -> None:
        if point == fault_point:
            raise RuntimeError("injected migration fault")

    with pytest.raises(RuntimeError, match="injected migration fault"):
        fixture["journal"].quarantine_trailing_sequence_collision(
            **fixture["kwargs"], fault_injector=fail
        )
    assert fixture["ledger"].events_path.read_bytes() == old_events
    assert fixture["sidecar"].read_bytes() == old_sidecar
    assert not fixture["receipt"].exists()
    assert not (fixture["ledger"].ledger_dir / ".active-generation.json").exists()


def test_guarded_trailing_collision_detects_noncooperative_concurrent_write(tmp_path: Path) -> None:
    fixture = _trailing_collision_fixture(tmp_path)
    old_sidecar = fixture["sidecar"].read_bytes()

    def race(point: str) -> None:
        if point == "after_events_switch":
            fixture["ledger"].events_path.write_bytes(
                fixture["ledger"].events_path.read_bytes() + b'{"seq":999,"kind":"racing-writer"}\n'
            )

    with pytest.raises(DurabilityUnknown, match="changed after atomic publication"):
        fixture["journal"].quarantine_trailing_sequence_collision(
            **fixture["kwargs"], fault_injector=race
        )
    assert fixture["ledger"].events_path.read_bytes().endswith(b'"racing-writer"}\n')
    assert fixture["sidecar"].read_bytes() == old_sidecar
    assert not fixture["receipt"].exists()
    assert (fixture["ledger"].ledger_dir / ".active-generation.json").exists()


@pytest.mark.parametrize("fault_point", ["after_custody_ready", "after_generation_ready", "after_events_switch"])
def test_guarded_trailing_collision_sigkill_phase_is_recoverable(tmp_path: Path, fault_point: str) -> None:
    fixture = _trailing_collision_fixture(tmp_path)
    child = os.fork()
    if child == 0:
        def kill(point: str) -> None:
            if point == fault_point:
                os._exit(77)

        fixture["journal"].quarantine_trailing_sequence_collision(
            **fixture["kwargs"], fault_injector=kill
        )
        os._exit(0)
    _, status = os.waitpid(child, 0)
    assert os.waitstatus_to_exitcode(status) == 77
    recovered = fixture["journal"].quarantine_trailing_sequence_collision(**fixture["kwargs"])
    assert recovered["outcome"] in {"committed", "recovered"}
    assert fixture["journal"].replay_strict()["accepted"][-1]["event_kind"] == "chain_control.trailing_sequence_collision_quarantined"


def test_guarded_trailing_collision_rejects_overlapping_paths(tmp_path: Path) -> None:
    fixture = _trailing_collision_fixture(tmp_path)
    kwargs = dict(fixture["kwargs"])
    kwargs["receipt_path"] = fixture["ledger"].ledger_dir / ".active-generation.json"
    with pytest.raises(ChainControlHold, match="receipt"):
        fixture["journal"].quarantine_trailing_sequence_collision(**kwargs)
    kwargs = dict(fixture["kwargs"])
    kwargs["custody_dir"] = tmp_path
    with pytest.raises(ChainControlHold, match="workspace"):
        fixture["journal"].quarantine_trailing_sequence_collision(**kwargs)


def test_reserved_torn_tail_is_preserved_then_replaced_by_tombstone(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_nbf01("evt-1"))
    journal = ChainControlJournal(ledger)
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    physical = read_physical_lines(ledger.events_path)
    replay = journal.replay_strict()
    partial = b'{"seq":3,"schema_version":1'
    reservation = empty_reservation(
        ledger_id=journal.ledger_id,
        physical_sequence=replay["physical_sequence"] + 1,
        status="reserved",
        previous_physical_digest=replay["physical_tip_digest"],
    )
    reservation["reservation_id"] = "torn-reservation"
    reservation["byte_offset"] = ledger.events_path.stat().st_size
    reservation["line_number"] = len(physical) + 1
    reservation["reservation_digest"] = reservation_digest_for(reservation)
    sidecar = ledger.ledger_dir / ".events.seq"
    fd = os.open(str(sidecar), os.O_RDWR)
    try:
        write_reservation_locked(fd, reservation)
        with open(ledger.events_path, "ab") as handle:
            handle.write(partial)
            handle.flush()
            os.fsync(handle.fileno())
        journal.recover_reservations_locked(fd)
    finally:
        os.close(fd)
    assert not any(item.torn for item in read_physical_lines(ledger.events_path))
    assert journal.replay_strict()["accepted"][-1]["event_kind"] == "chain_control.sequence_reserved_tombstone"
    custody = ledger.ledger_dir / ".nbf08-torn-custody"
    assert [path.read_bytes() for path in custody.iterdir()] == [partial]


def test_complete_reserved_line_recovery_verifies_identity_on_first_attempt(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_nbf01("evt-1"))
    journal = ChainControlJournal(ledger)
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    sidecar = ledger.ledger_dir / ".events.seq"
    reservation = json.loads(sidecar.read_text(encoding="utf-8"))
    reservation["status"] = "reserved"
    reservation["reservation_digest"] = reservation_digest_for(reservation)
    fd = os.open(str(sidecar), os.O_RDWR)
    try:
        write_reservation_locked(fd, reservation)
        recovered = journal.recover_reservations_locked(fd)
    finally:
        os.close(fd)
    assert recovered["status"] == "committed"
    stored = json.loads(sidecar.read_text(encoding="utf-8"))
    assert stored["status"] == "committed"
    assert stored["reservation_digest"] == reservation_digest_for(stored)


def test_complete_foreign_line_at_reserved_sequence_is_not_adopted(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_nbf01("evt-1"))
    journal = ChainControlJournal(ledger)
    replay = journal.replay_strict()
    physical = read_physical_lines(ledger.events_path)
    reservation = empty_reservation(
        ledger_id=journal.ledger_id,
        physical_sequence=replay["physical_sequence"] + 1,
        status="reserved",
        previous_physical_digest=replay["physical_tip_digest"],
    )
    reservation.update(
        {
            "event_id": "reserved-event",
            "event_kind": "incident.nbf.detection",
            "byte_offset": ledger.events_path.stat().st_size,
            "line_number": len(physical) + 1,
        }
    )
    reservation["reservation_digest"] = reservation_digest_for(reservation)
    expected_record = {
        "seq": replay["physical_sequence"] + 1,
        "schema_version": 1,
        "ts_utc": "2026-09-02T00:00:00+00:00",
        "ts_rel_init_s": None,
        "kind": "incident.nbf.detection",
        "payload": {"event_id": "reserved-event", "value": "expected"},
        "idempotency_key": "reserved-event",
    }
    reservation["intended_record_sha256"] = hashlib.sha256(canonical_json(expected_record)).hexdigest()
    reservation["reservation_digest"] = reservation_digest_for(reservation)
    foreign_record = dict(expected_record)
    foreign_record["payload"] = {"event_id": "reserved-event", "value": "foreign"}
    foreign = canonical_json(foreign_record)
    with open(ledger.events_path, "ab") as handle:
        handle.write(foreign + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    sidecar = ledger.ledger_dir / ".events.seq"
    fd = os.open(str(sidecar), os.O_RDWR)
    try:
        write_reservation_locked(fd, reservation)
        with pytest.raises(DurabilityUnknown, match="intended_record_sha256"):
            journal.recover_reservations_locked(fd)
    finally:
        os.close(fd)


def test_ordinary_append_after_genesis_and_migration_uses_structured_active_tip(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path / "genesis")
    ledger.append_event(_nbf01("evt-1"))
    journal = ChainControlJournal(ledger)
    journal.ensure_genesis(chain_id="chain-demo", actor={"id": "t", "class": "test"})
    appended = ledger.append_event(_nbf01("evt-2"))
    sidecar = json.loads((ledger.ledger_dir / ".events.seq").read_text(encoding="utf-8"))
    assert sidecar["status"] == "committed"
    assert sidecar["physical_sequence"] == appended["seq"]
    assert sidecar["scope"] == "chainless"
    assert sidecar["chain_id"] is None and sidecar["event_id"] is None and sidecar["operation_id"] is None
    assert journal.replay_strict()["physical_sequence"] == appended["seq"]
    sidecar["status"] = "reserved"
    sidecar["reservation_digest"] = reservation_digest_for(sidecar)
    sidecar_path = ledger.ledger_dir / ".events.seq"
    fd = os.open(str(sidecar_path), os.O_RDWR)
    try:
        write_reservation_locked(fd, sidecar)
        assert journal.recover_reservations_locked(fd)["status"] == "committed"
    finally:
        os.close(fd)

    fixture = _trailing_collision_fixture(tmp_path / "migrated")
    fixture["journal"].quarantine_trailing_sequence_collision(**fixture["kwargs"])
    legacy_bytes = (fixture["ledger"].ledger_dir / "events.jsonl").read_bytes()
    active_before = fixture["ledger"].events_path.read_bytes()
    migrated_append = fixture["ledger"].append_event(_nbf01("evt-after-migration"))
    assert fixture["ledger"].events_path.read_bytes() != active_before
    assert (fixture["ledger"].ledger_dir / "events.jsonl").read_bytes() == legacy_bytes
    assert fixture["journal"].replay_strict()["physical_sequence"] == migrated_append["seq"]


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
