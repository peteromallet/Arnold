from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.incident import IncidentLedger, RuntimeTransitionWriter
from arnold_pipelines.megaplan.incident.ledger import (
    EVENT_DEVIATION_DECLARED,
    EVENT_FALLBACK_CONSIDERED,
    EVENT_FALLBACK_REJECTED,
    EVENT_FALLBACK_TAKEN,
    EVENT_MANIFEST_SELECTED,
    KNOWN_FAILURE_CLASSES,
    NON_RETRYABLE_FAILURE_CLASSES,
    RETRYABLE_FAILURE_CLASSES,
    RUNTIME_TRANSITION_EVENT_TYPES,
    is_retryable_failure_class,
    main,
)
from arnold_pipelines.megaplan.incident.schema import (
    MAX_COMMITTED_OUTPUT_BYTES,
    MAX_STRUCTURED_FIELD_BYTES,
    cap_committed_output_text,
)


def _event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
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
    event.update(overrides)
    return event


def test_incident_ledger_appends_validated_events_to_events_jsonl(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)

    appended = ledger.append_event(_event(extra_field={"kept": True}))

    assert ledger.events_path == tmp_path / ".megaplan" / "incident-ledger" / "events.jsonl"
    assert ledger.events_path.exists()
    assert not (ledger.ledger_dir / "events.ndjson").exists()
    assert not (ledger.ledger_dir / "incidents.json").exists()
    assert not (ledger.ledger_dir / "problems.json").exists()
    assert appended["seq"] == 0
    assert appended["kind"] == "incident.opened"
    assert appended["payload"]["extra_field"] == {"kept": True}

    records = [
        json.loads(line)
        for line in ledger.events_path.read_text(encoding="utf-8").splitlines()
    ]
    assert records == [appended]


def test_incident_ledger_preserves_runtime_seq_assignment_across_appends(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)

    first = ledger.append_event(_event())
    second = ledger.append_event(
        _event(
            event_id="evt-2",
            type="updated",
            summary="incident updated",
            outcome="verified",
            parent_event_ids=["evt-1"],
        )
    )

    assert [first["seq"], second["seq"]] == [0, 1]
    assert (ledger.ledger_dir / ".events.seq").read_text(encoding="utf-8") == "1"
    assert (ledger.ledger_dir / ".events.init_ts").exists()


def test_incident_ledger_rejects_invalid_events_before_writing(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)

    with pytest.raises(ValueError, match="incident event 'summary' must be <= 2048"):
        ledger.append_event(_event(summary="x" * 2049))

    assert not ledger.events_path.exists()


def test_authorized_lifecycle_event_requires_current_owner_grant_and_custody(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)

    with pytest.raises(ValueError, match="Run Authority"):
        ledger.append_authorized_lifecycle_event(
            occurrence_id="occ-1",
            transition="acknowledged",
            owner="forged-owner",
            grant_id="forged-grant",
            custody_epoch=1,
            run_authority_check=lambda _grant, _owner: False,
            custody_check=lambda _owner, _epoch, _occurrence: True,
        )
    assert not ledger.events_path.exists()

    appended = ledger.append_authorized_lifecycle_event(
        occurrence_id="occ-1",
        transition="acknowledged",
        owner="resident-owner",
        grant_id="grant-current",
        custody_epoch=7,
        run_authority_check=lambda grant, owner: (grant, owner) == ("grant-current", "resident-owner"),
        custody_check=lambda owner, epoch, occurrence: (owner, epoch, occurrence) == ("resident-owner", 7, "occ-1"),
    )
    assert appended["payload"]["type"] == "acknowledged"
    assert appended["payload"]["run_authority_grant_id"] == "grant-current"
    assert appended["payload"]["custody_epoch"] == 7


def test_incident_ledger_rejects_expanding_decision_before_redaction(
    tmp_path: Path,
) -> None:
    ledger = IncidentLedger(tmp_path)

    with pytest.raises(ValueError, match="incident event 'decision'.*bytes"):
        ledger.append_event(
            _event(decision={"recursive_audit_response": "x" * (MAX_STRUCTURED_FIELD_BYTES + 1)})
        )

    assert not ledger.events_path.exists()


def test_incident_ledger_redacts_secret_shaped_strings_before_persisting(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    private_key = (
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        "private-material\n"
        "-----END OPENSSH PRIVATE KEY-----"
    )

    appended = ledger.append_event(
        _event(
            summary="Authorization: Bearer bearer-secret-token-value sk-proj-secretsecretsecretsecret",
            evidence=[
                "ghp_secretgithubpat1234567890",
                {
                    "kind": "log",
                    "detail": "aws_access_key_id = AKIAIOSFODNN7EXAMPLE",
                },
            ],
            links={
                "dashboard": "https://example.test/hook?access_token=ghu_secretgithubpat1234567890",
            },
            decision={
                "why": "Authorization: Bearer bearer-secret-token-value",
            },
            actions=[
                {
                    "kind": "command",
                    "command": private_key,
                }
            ],
        )
    )

    raw_text = ledger.events_path.read_text(encoding="utf-8")

    for secret in (
        "bearer-secret-token-value",
        "sk-proj-secretsecretsecretsecret",
        "ghp_secretgithubpat1234567890",
        "ghu_secretgithubpat1234567890",
        "AKIAIOSFODNN7EXAMPLE",
        "OPENSSH PRIVATE KEY",
    ):
        assert secret not in raw_text

    payload = appended["payload"]
    assert "***REDACTED***" in payload["summary"]
    assert "***REDACTED***" in json.dumps(payload["evidence"])
    assert "***REDACTED***" in json.dumps(payload["links"])
    assert "***REDACTED***" in json.dumps(payload["decision"])
    assert "***REDACTED***" in json.dumps(payload["actions"])


def test_incident_ledger_validates_summary_length_after_redaction(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)

    appended = ledger.append_event(
        _event(
            summary="Authorization: Bearer " + ("x" * 3000),
        )
    )

    assert len(appended["payload"]["summary"]) <= 2048
    assert appended["payload"]["summary"] == "Authorization: Bearer ***REDACTED***"


def test_cap_committed_output_text_enforces_50kb_utf8_limit() -> None:
    text = "a" * (MAX_COMMITTED_OUTPUT_BYTES + 128)

    capped = cap_committed_output_text(text)

    assert len(capped.encode("utf-8")) <= MAX_COMMITTED_OUTPUT_BYTES
    assert capped.endswith("50KB committed-output cap]")
    assert capped != text


# ---------------------------------------------------------------------------
# P2 — typed runtime transition writer
# ---------------------------------------------------------------------------

_DIGEST = "sha256:" + "a" * 64


def _read_records(ledger: IncidentLedger) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in ledger.events_path.read_text(encoding="utf-8").splitlines()
    ]


def test_runtime_transition_writer_emits_manifest_selected(tmp_path: Path) -> None:
    writer = RuntimeTransitionWriter(tmp_path)

    appended = writer.emit_manifest_selected(
        scope="chain:session-7",
        candidate_to="runtime-r7-20260805",
        candidate_from="runtime-legacy-20260701",
        chain_spec_sha256=_DIGEST,
        evidence=["supervisor/launch.log"],
        session_id="session-7",
    )

    assert appended["seq"] == 0
    assert appended["kind"] == "incident.runtime.manifest_selected"
    payload = appended["payload"]
    assert payload["type"] == EVENT_MANIFEST_SELECTED
    assert payload["outcome"] == "selected"
    assert payload["scope"] == "chain:session-7"
    assert payload["candidate_to"] == "runtime-r7-20260805"
    assert payload["candidate_from"] == "runtime-legacy-20260701"
    assert payload["chain_spec_sha256"] == _DIGEST
    assert payload["session_id"] == "session-7"
    assert payload["failure_class"] is None
    assert payload["error"] == ""
    assert payload["attempt"] == ""


def test_runtime_transition_writer_emits_deviation_declared(tmp_path: Path) -> None:
    writer = RuntimeTransitionWriter(tmp_path)

    appended = writer.emit_deviation_declared(
        scope="chain:session-7",
        failure_class="config",
        error="runtime manifest missing epic.branch",
        chain_spec_sha256=_DIGEST,
        attempt=2,
        evidence=["chain.yaml:12", "runtime-manifest.json"],
    )

    assert appended["kind"] == "incident.runtime.deviation_declared"
    payload = appended["payload"]
    assert payload["type"] == EVENT_DEVIATION_DECLARED
    assert payload["outcome"] == "declared"
    assert payload["failure_class"] == "config"
    assert payload["error"] == "runtime manifest missing epic.branch"
    assert payload["attempt"] == 2
    assert payload["chain_spec_sha256"] == _DIGEST
    assert "failure_class=config" in payload["summary"]


def test_runtime_transition_writer_emits_fallback_considered(tmp_path: Path) -> None:
    writer = RuntimeTransitionWriter(tmp_path)

    appended = writer.emit_fallback_considered(
        scope="chain:session-7",
        failure_class="infrastructure",
        chain_spec_sha256=_DIGEST,
        candidate_from="runtime-r7-20260805",
        candidate_to="runtime-r7-fresh-child-20260805",
        attempt=3,
        error="runner transport timeout",
        evidence=["run_logs/session-7.log"],
    )

    assert appended["kind"] == "incident.runtime.fallback_considered"
    payload = appended["payload"]
    assert payload["type"] == EVENT_FALLBACK_CONSIDERED
    assert payload["outcome"] == "considered"
    assert payload["failure_class"] == "infrastructure"
    assert payload["candidate_to"] == "runtime-r7-fresh-child-20260805"
    assert payload["attempt"] == 3
    assert payload["error"] == "runner transport timeout"


def test_runtime_transition_writer_emits_fallback_taken(tmp_path: Path) -> None:
    writer = RuntimeTransitionWriter(tmp_path)

    appended = writer.emit_fallback_taken(
        scope="chain:session-7",
        failure_class="availability",
        chain_spec_sha256=_DIGEST,
        candidate_to={"branch": "fixer/session-7-20260810", "runtime_root": "/workspace/rt-7"},
        attempt=4,
        evidence=["claim/session-7.json"],
    )

    assert appended["kind"] == "incident.runtime.fallback_taken"
    payload = appended["payload"]
    assert payload["type"] == EVENT_FALLBACK_TAKEN
    assert payload["outcome"] == "taken"
    assert payload["failure_class"] == "availability"
    assert payload["candidate_to"] == {
        "branch": "fixer/session-7-20260810",
        "runtime_root": "/workspace/rt-7",
    }
    assert payload["attempt"] == 4
    assert payload["chain_spec_sha256"] == _DIGEST


def test_runtime_transition_writer_emits_fallback_rejected(tmp_path: Path) -> None:
    writer = RuntimeTransitionWriter(tmp_path)

    appended = writer.emit_fallback_rejected(
        scope="chain:session-7",
        failure_class="evidence",
        chain_spec_sha256=_DIGEST,
        candidate_to="fallback-branch",
        attempt=2,
        error="no verifiable recovery receipt",
        evidence=["receipts/"],
    )

    assert appended["kind"] == "incident.runtime.fallback_rejected"
    payload = appended["payload"]
    assert payload["type"] == EVENT_FALLBACK_REJECTED
    assert payload["outcome"] == "rejected"
    assert payload["failure_class"] == "evidence"
    assert payload["error"] == "no verifiable recovery receipt"
    assert "failure_class=evidence" in payload["summary"]


def test_runtime_transition_writer_payload_shape(tmp_path: Path) -> None:
    writer = RuntimeTransitionWriter(tmp_path)

    appended = writer.emit_fallback_taken(
        scope="chain:session-7",
        failure_class="infrastructure",
        chain_spec_sha256=_DIGEST,
        candidate_from="candidate-a",
        candidate_to="candidate-b",
        error="network blip",
        attempt=1,
        evidence=["evidence/one"],
        actor="watchdog",
        session_id="session-7",
    )

    payload = appended["payload"]
    expected_keys = {
        "schema_version",
        "event_id",
        "ts",
        "type",
        "actor",
        "scope",
        "outcome",
        "summary",
        "evidence",
        "parent_event_ids",
        "next_expected_event",
        "deadline_ts",
        "trigger_event_id",
        "candidate_from",
        "candidate_to",
        "error",
        "attempt",
        "chain_spec_sha256",
        "failure_class",
        "session_id",
    }
    assert set(payload) == expected_keys
    assert payload["schema_version"] == 1
    assert payload["actor"] == "watchdog"
    assert payload["parent_event_ids"] == []
    assert payload["next_expected_event"] is None
    assert payload["deadline_ts"] is None
    assert payload["trigger_event_id"] is None
    assert appended["seq"] == 0
    assert appended["kind"] == "incident.runtime.fallback_taken"


@pytest.mark.parametrize(
    "failure_class", sorted(NON_RETRYABLE_FAILURE_CLASSES)
)
def test_fallback_taken_rejects_non_retryable_failure_classes(
    tmp_path: Path, failure_class: str
) -> None:
    writer = RuntimeTransitionWriter(tmp_path)

    with pytest.raises(ValueError, match="fallback_taken requires a retryable failure class"):
        writer.emit_fallback_taken(
            scope="chain:session-7",
            failure_class=failure_class,
            chain_spec_sha256=_DIGEST,
        )

    # Fail-before-dispatch: nothing was written for the rejected transition.
    assert not writer._ledger.events_path.exists()


def test_fallback_taken_rejects_missing_failure_class(tmp_path: Path) -> None:
    writer = RuntimeTransitionWriter(tmp_path)

    with pytest.raises(ValueError, match="requires a failure_class"):
        writer.emit_fallback_taken(
            scope="chain:session-7",
            failure_class=None,
            chain_spec_sha256=_DIGEST,
        )

    assert not writer._ledger.events_path.exists()


def test_fallback_rejected_rejects_unknown_failure_class(tmp_path: Path) -> None:
    writer = RuntimeTransitionWriter(tmp_path)

    with pytest.raises(ValueError, match="failure_class must be one of"):
        writer.emit_fallback_rejected(
            scope="chain:session-7",
            failure_class="made_up_class",
            chain_spec_sha256=_DIGEST,
        )

    assert not writer._ledger.events_path.exists()


def test_runtime_transition_writer_rejects_malformed_chain_digest(tmp_path: Path) -> None:
    writer = RuntimeTransitionWriter(tmp_path)

    with pytest.raises(ValueError, match="chain_spec_sha256"):
        writer.emit_deviation_declared(
            scope="chain:session-7",
            failure_class="semantic",
            error="boom",
            chain_spec_sha256="sha256:nothex",
        )

    assert not writer._ledger.events_path.exists()


def test_runtime_transition_writer_propagates_ledger_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = IncidentLedger(tmp_path)

    def _disk_full(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise OSError("disk full")

    monkeypatch.setattr(ledger._journal, "emit", _disk_full)
    writer = RuntimeTransitionWriter(ledger=ledger)

    with pytest.raises(OSError, match="disk full"):
        writer.emit_fallback_taken(
            scope="chain:session-7",
            failure_class="infrastructure",
            chain_spec_sha256=_DIGEST,
        )

    assert not ledger.events_path.exists()


def test_runtime_transition_cli_round_trip(tmp_path: Path) -> None:
    exit_code = main(
        [
            "fallback_taken",
            "--root",
            str(tmp_path),
            "--scope",
            "chain:session-9",
            "--actor",
            "watchdog",
            "--session-id",
            "session-9",
            "--candidate-from",
            "runtime-a",
            "--candidate-to",
            '{"branch": "fixer/x"}',
            "--error",
            "transport timeout",
            "--attempt",
            "3",
            "--chain-spec-sha256",
            _DIGEST,
            "--failure-class",
            "availability",
            "--evidence",
            '["evidence/one"]',
        ]
    )

    assert exit_code == 0
    ledger = IncidentLedger(tmp_path)
    records = _read_records(ledger)
    assert len(records) == 1
    payload = records[0]["payload"]
    assert payload["type"] == EVENT_FALLBACK_TAKEN
    assert payload["scope"] == "chain:session-9"
    assert payload["actor"] == "watchdog"
    assert payload["session_id"] == "session-9"
    assert payload["failure_class"] == "availability"
    assert payload["attempt"] == "3"
    assert payload["candidate_to"] == {"branch": "fixer/x"}
    assert payload["candidate_from"] == "runtime-a"
    assert payload["chain_spec_sha256"] == _DIGEST
    assert payload["evidence"] == ["evidence/one"]


def test_runtime_transition_cli_blocks_dispatch_on_policy_rejection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        [
            "fallback_taken",
            "--root",
            str(tmp_path),
            "--scope",
            "chain:session-9",
            "--chain-spec-sha256",
            _DIGEST,
            "--failure-class",
            "semantic",
        ]
    )

    assert exit_code == 1
    assert "runtime transition not recorded" in capsys.readouterr().err
    # Fail-before-dispatch: the rejected transition must not reach the ledger.
    assert not (tmp_path / ".megaplan" / "incident-ledger" / "events.jsonl").exists()


def test_runtime_transition_constants_and_policy() -> None:
    assert RUNTIME_TRANSITION_EVENT_TYPES == (
        EVENT_MANIFEST_SELECTED,
        EVENT_DEVIATION_DECLARED,
        EVENT_FALLBACK_CONSIDERED,
        EVENT_FALLBACK_TAKEN,
        EVENT_FALLBACK_REJECTED,
    )
    assert RETRYABLE_FAILURE_CLASSES == frozenset({"availability", "infrastructure"})
    assert KNOWN_FAILURE_CLASSES == RETRYABLE_FAILURE_CLASSES | NON_RETRYABLE_FAILURE_CLASSES
    assert all(is_retryable_failure_class(c) for c in RETRYABLE_FAILURE_CLASSES)
    assert not any(is_retryable_failure_class(c) for c in NON_RETRYABLE_FAILURE_CLASSES)
    assert is_retryable_failure_class(None) is False
