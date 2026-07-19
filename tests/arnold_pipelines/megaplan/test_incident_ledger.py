from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.incident import IncidentLedger
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
