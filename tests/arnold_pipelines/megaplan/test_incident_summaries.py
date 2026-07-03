from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.cloud.redact import REDACTION
from arnold_pipelines.megaplan.incident.summaries import write_projection_summaries


def test_write_projection_summaries_uses_projection_metadata_only(tmp_path: Path) -> None:
    projections = {
        "incidents": {
            "source": {"digest": "sha256:incidents", "last_seq": 9},
            "incidents": [
                {
                    "incident_id": "inc-1",
                    "problem_ids": ["prob-1"],
                    "summary": "Repair stalled with sk-testsecretsecretsecret",
                    "state": "repair_attempt",
                    "outcome": "failed",
                    "latest_actor": "meta_repair",
                    "next_expected_event": "github_sync.publish",
                    "deadline_ts": "2026-07-03T21:00:00Z",
                    "last_seq": 9,
                    "placeholders": {"install_freshness": "stale"},
                    "evidence_refs": [
                        {
                            "kind": "artifact",
                            "path": "artifacts/run.log",
                            "sha256": "abc123",
                            "session_id": "session-1",
                            "artifact_id": "artifact-1",
                            "provider_payload": {"token": "ghp_secretsecretsecret"},
                            "raw_transcript": "do not commit me",
                        }
                    ],
                }
            ],
        },
        "problems": {
            "source": {"digest": "sha256:problems", "last_seq": 9},
            "problems": [
                {
                    "problem_id": "prob-1",
                    "title": "Persistent repair failure",
                    "status": "open",
                    "occurrence_count": 3,
                    "recurred_after_fix": True,
                    "owner_actor": "six_hour_auditor",
                    "next_review_ts": "2026-07-04T00:00:00Z",
                    "linked_incident_ids": ["inc-1"],
                    "fix_commits": ["deadbeef"],
                    "last_seen_seq": 9,
                }
            ],
        },
    }

    manifest = write_projection_summaries(projections=projections, root=tmp_path)

    incident_path = tmp_path / ".megaplan" / "incident-ledger" / "summaries" / "incidents" / "inc-1.json"
    doc = json.loads(incident_path.read_text(encoding="utf-8"))
    serialized = incident_path.read_text(encoding="utf-8")

    assert manifest["incident_count"] == 1
    assert doc["summary_text"].startswith("inc-1:")
    assert REDACTION in doc["summary_text"]
    assert doc["evidence_refs"] == [
        {
            "artifact_id": "artifact-1",
            "kind": "artifact",
            "path": "artifacts/run.log",
            "session_id": "session-1",
            "sha256": "abc123",
        }
    ]
    assert "provider_payload" not in serialized
    assert "raw_transcript" not in serialized
    assert "ghp_secretsecretsecret" not in serialized


def test_write_projection_summaries_enforces_2kb_and_50kb_gates(tmp_path: Path) -> None:
    big_summary = "x" * 4000
    evidence_refs = [
        {
            "kind": "artifact",
            "path": f"artifacts/log-{index}.txt",
            "sha256": f"{index:064x}",
            "session_id": "session-gate",
            "artifact_id": f"artifact-{index}",
        }
        for index in range(500)
    ]
    projections = {
        "incidents": {
            "source": {"digest": "sha256:incidents", "last_seq": 500},
            "incidents": [
                {
                    "incident_id": "inc-gate",
                    "problem_ids": ["prob-gate"],
                    "summary": big_summary,
                    "state": "repair_attempt",
                    "outcome": "failed",
                    "latest_actor": "meta_repair",
                    "next_expected_event": "github_sync.publish",
                    "deadline_ts": None,
                    "last_seq": 500,
                    "placeholders": {"install_freshness": "stale"},
                    "evidence_refs": evidence_refs,
                }
            ],
        },
        "problems": {
            "source": {"digest": "sha256:problems", "last_seq": 500},
            "problems": [],
        },
    }

    write_projection_summaries(projections=projections, root=tmp_path)

    incident_path = tmp_path / ".megaplan" / "incident-ledger" / "summaries" / "incidents" / "inc-gate.json"
    doc = json.loads(incident_path.read_text(encoding="utf-8"))
    assert len(doc["summary_text"].encode("utf-8")) <= 2048
    assert len(incident_path.read_bytes()) <= 50 * 1024
    assert doc["omitted_evidence_ref_count"] > 0
