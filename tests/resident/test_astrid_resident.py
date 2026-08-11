"""Tests for the Astrid resident contract (B12).

Verifies that the checked-in example files are exactly the generator's
output for the Astrid domain, that the contract carries the Astrid-specific
clauses (gateway loop, ``--engine arnold``, credentials, typed media,
``MediaUsage``), and that typed-media evidence emission writes store records.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.resident.astrid_domain import build_astrid_domain
from arnold_pipelines.megaplan.resident.generator import generate_domain_contracts
from arnold_pipelines.megaplan.resident.media_evidence import (
    MEDIA_EVIDENCE_CATEGORY,
    MediaEvidence,
    compute_file_digest,
    default_media_usage,
    emit_media_evidence,
    list_media_evidence,
)
from arnold_pipelines.megaplan.store.file import FileStore

REPO_ROOT = Path(__file__).resolve().parents[2]

ASTRID_AGENT_PATH = REPO_ROOT / "examples" / "agents" / "astrid-resident.md"
ASTRID_CONTRACTS_DIR = REPO_ROOT / "examples" / "resident" / "astrid"


# ── Checked-in examples are exactly the generated output ───────────────────


def test_checked_in_astrid_agent_matches_generator_output() -> None:
    contracts = generate_domain_contracts(build_astrid_domain())
    expected = contracts["astrid-resident.md"]
    actual = ASTRID_AGENT_PATH.read_text(encoding="utf-8")
    assert actual == expected
    assert "astrid-resident.md" in contracts
    assert "astrid-policy.yaml" in contracts
    assert "astrid-session.yaml" in contracts
    assert "astrid-evidence.yaml" in contracts


def test_checked_in_astrid_contracts_match_generator_output() -> None:
    contracts = generate_domain_contracts(build_astrid_domain())
    for name in ("astrid-policy.yaml", "astrid-session.yaml", "astrid-evidence.yaml"):
        expected = contracts[name]
        actual = (ASTRID_CONTRACTS_DIR / name).read_text(encoding="utf-8")
        assert actual == expected, f"{name} drifted from generator output"


# ── Astrid-specific contract clauses ────────────────────────────────────────


def test_astrid_agent_prompt_gateway_contract() -> None:
    text = ASTRID_AGENT_PATH.read_text(encoding="utf-8")
    assert "astrid next" in text
    assert "`bootstrap`, `run: ...`, or `ack ...`" in text
    assert "NEVER freelance" in text
    assert "`astrid status`" in text
    assert "--engine arnold" in text
    assert "writer-epoch" in text
    assert "session takeover protocol" in text
    assert ".env.local" in text
    assert "video/mp4" in text and "audio/wav" in text and "x-astrid-timeline" in text
    assert "MediaUsage" in text


def test_astrid_policy_contract_credentials_and_cwd() -> None:
    text = (ASTRID_CONTRACTS_DIR / "astrid-policy.yaml").read_text(encoding="utf-8")
    for var in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "REIGH_SUPABASE_URL",
        "REIGH_SUPABASE_SERVICE_ROLE_KEY",
        "REIGH_SUPABASE_JWKS_URL",
        "REIGH_PAT",
        "HF_TOKEN",
        "FAL_KEY",
        "REPLICATE_API_TOKEN",
        "RUNPOD_API_KEY",
        "SUPABASE_URL",
    ):
        assert var in text, f"missing credential {var}"
    assert "projects/<slug>/runs/<run-id>" in text
    assert "file tools constrained to the run directory" in text


def test_astrid_session_contract_identity() -> None:
    text = (ASTRID_CONTRACTS_DIR / "astrid-session.yaml").read_text(encoding="utf-8")
    assert "agent:astrid-resident" in text
    assert "projects/<slug>/" in text
    assert "runs/<slug>/" in text
    assert "writer_epoch" in text
    assert "takeover" in text
    assert "astrid status" in text


def test_astrid_evidence_contract_typed_media() -> None:
    text = (ASTRID_CONTRACTS_DIR / "astrid-evidence.yaml").read_text(encoding="utf-8")
    assert "video/mp4" in text
    assert "audio/wav" in text
    assert "x-astrid-timeline" in text
    assert "MediaUsage" in text
    assert "timeline_document" in text
    assert "video_second" in text and "audio_second" in text
    assert "restart_recovery" in text
    assert "heartbeat" in text
    assert "watchdog" in text


# ── Typed-media evidence emission into the resident store ──────────────────


def _store(tmp_path: Path) -> FileStore:
    return FileStore(root=tmp_path / "store")


def _evidence(tmp_path: Path, *, content_type: str) -> tuple[MediaEvidence, Path]:
    artifact = tmp_path / "artifacts" / ("out" + Path(content_type).suffix or ".bin")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"typed-media-bytes" * 10)
    evidence = MediaEvidence(
        artifact_path=str(artifact),
        content_type=content_type,
        size_bytes=artifact.stat().st_size,
        digest=compute_file_digest(artifact),
        producer_tool="astrid-gateway",
        run_id="arnold-test-run",
        stage_id="write_summary",
    )
    return evidence, artifact


def test_emit_media_evidence_records_evidence_and_cost(tmp_path: Path) -> None:
    store = _store(tmp_path)
    evidence, _ = _evidence(tmp_path, content_type="x-astrid-timeline")
    result = emit_media_evidence(store, evidence=evidence)

    assert result["evidence"]["content_type"] == "x-astrid-timeline"
    assert result["evidence"]["digest"] == evidence.digest
    assert result["evidence"]["media_usage"]["unit"] == "timeline_document"

    logs = store._system_logs()
    event_types = {log.event_type for log in logs}
    assert "typed_media_evidence" in event_types
    assert "media_usage_cost" in event_types


def test_emit_media_evidence_stable_idempotency_key(tmp_path: Path) -> None:
    store = _store(tmp_path)
    evidence, _ = _evidence(tmp_path, content_type="audio/wav")
    first = emit_media_evidence(store, evidence=evidence)
    second = emit_media_evidence(store, evidence=evidence)
    # Same digest -> identical evidence payload and stable idempotency key
    # derivation (upstream stores dedupe by that key).
    assert first["evidence"]["digest"] == second["evidence"]["digest"] == evidence.digest
    assert first["evidence"]["media_usage"]["unit"] == "audio_second"
    logs = [
        log
        for log in store._system_logs()
        if log.event_type == "typed_media_evidence"
    ]
    assert len(logs) == 2
    assert {log.details["digest"] for log in logs} == {evidence.digest}


def test_default_media_usage_maps_content_types() -> None:
    assert default_media_usage(_evidence(tmp_path := Path("/tmp"), content_type="video/mp4")[0]).unit == "video_second"
    assert default_media_usage(_evidence(Path("/tmp"), content_type="audio/wav")[0]).unit == "audio_second"
    assert default_media_usage(_evidence(Path("/tmp"), content_type="x-astrid-timeline")[0]).unit == "timeline_document"


def test_list_media_evidence_returns_records(tmp_path: Path) -> None:
    store = _store(tmp_path)
    evidence, _ = _evidence(tmp_path, content_type="video/mp4")
    emit_media_evidence(store, evidence=evidence)
    records = list_media_evidence(store)
    assert len(records) == 1
    assert records[0]["content_type"] == "video/mp4"


def test_unsupported_content_type_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    evidence = MediaEvidence(
        artifact_path="/tmp/x.bin",
        content_type="application/x-unknown",
        size_bytes=1,
        digest="abc",
        producer_tool="astrid-gateway",
    )
    with pytest.raises(Exception):
        emit_media_evidence(store, evidence=evidence)
