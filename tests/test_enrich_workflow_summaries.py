from __future__ import annotations

import json
from typing import Any
from pathlib import Path

import pytest

from scripts import enrich_workflow_summaries as enrich


def _sample_manifest_row(**overrides: Any) -> dict[str, Any]:
    return {
        "workflow_id": "abc123",
        "canonical_workflow_hash": "abcdef1234567890",
        "corpus_path": "external_workflows/corpus/abc123.json",
        "primary_source": {
            "source": "banodoco-discord-archive",
            "source_url": "https://cdn.discordapp.com/attachments/1/1/workflow.json",
            "source_type": "discord_attachment",
            "authority_tier": "community",
            "filename": "workflow.json",
            "channel_name": "comfyui",
            "canonical_workflow_hash": "abcdef1234567890",
            "node_count": 5,
            "node_class_multiset": {"KSampler": 1, "LoadCheckpoint": 2},
            "discovered_by": "scanner",
            "discovered_at": "2026-06-24T00:00:00Z",
            "ingested_at": "2026-06-24T01:00:00Z",
        },
        **overrides,
    }


def _sample_summary() -> dict[str, Any]:
    return {
        "title": "Test workflow title",
        "description": "A test workflow that does things.",
        "tags": ["test", "image-generation"],
        "task_type": "text_to_image",
        "media_type": "image",
        "flags": {"is_animated": False, "requires_custom_nodes": True},
        "complexity": 2,
    }


def _make_corpus(corpus_dir: Path) -> None:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "abc123.json").write_text(
        json.dumps({"nodes": {}, "edges": []}, indent=2),
        encoding="utf-8",
    )


def _make_manifest(manifest_path: Path, row: dict[str, Any] | None = None) -> None:
    manifest_path.write_text(
        json.dumps({"workflows": [row or _sample_manifest_row()]}, indent=2),
        encoding="utf-8",
    )


def test_upload_flag_uploads_new_rows(monkeypatch, tmp_path: Path) -> None:
    corpus_dir = tmp_path / "external_workflows" / "corpus"
    manifest_path = tmp_path / "external_workflows" / "manifest.json"
    _make_corpus(corpus_dir)
    _make_manifest(manifest_path)

    monkeypatch.setattr(enrich, "summarize_workflow", lambda *_a, **_kw: _sample_summary())
    monkeypatch.setattr(
        enrich, "_find_existing_resource", lambda *_a, **_kw: {"exists": False}
    )

    posted: list[dict[str, Any]] = []

    def fake_post(envelope: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        posted.append(envelope)
        return {"id": 42, "status": "ok"}

    monkeypatch.setattr(enrich, "_post", fake_post)

    counts = enrich.enrich(
        corpus_dir=corpus_dir,
        manifest_path=manifest_path,
        upload=True,
        upload_sleep=0,
    )

    assert counts["processed"] == 1
    assert counts["uploaded"] == 1
    assert counts["upload_skipped"] == 0
    assert counts["upload_errors"] == 0
    assert len(posted) == 1
    assert posted[0]["data"]["source"] == "vibecomfy-external"
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert persisted["workflows"][0]["hivemind_upload"]["status"] == "uploaded"


def test_upload_flag_skips_existing_rows(monkeypatch, tmp_path: Path) -> None:
    corpus_dir = tmp_path / "external_workflows" / "corpus"
    manifest_path = tmp_path / "external_workflows" / "manifest.json"
    _make_corpus(corpus_dir)
    _make_manifest(manifest_path)

    monkeypatch.setattr(enrich, "summarize_workflow", lambda *_a, **_kw: _sample_summary())
    monkeypatch.setattr(
        enrich,
        "_find_existing_resource",
        lambda *_a, **_kw: {
            "exists": True,
            "source": "vibecomfy-external",
            "external_id": "vibecomfy:external_workflow:abcdef1234567890",
            "resource_id": 123,
            "duplicate_count": 1,
        },
    )

    posted: list[dict[str, Any]] = []
    monkeypatch.setattr(enrich, "_post", lambda envelope, **kw: posted.append(envelope))

    counts = enrich.enrich(
        corpus_dir=corpus_dir,
        manifest_path=manifest_path,
        upload=True,
        upload_sleep=0,
    )

    assert counts["processed"] == 1
    assert counts["uploaded"] == 0
    assert counts["upload_skipped"] == 1
    assert counts["upload_errors"] == 0
    assert posted == []


def test_upload_flag_records_errors(monkeypatch, tmp_path: Path) -> None:
    corpus_dir = tmp_path / "external_workflows" / "corpus"
    manifest_path = tmp_path / "external_workflows" / "manifest.json"
    _make_corpus(corpus_dir)
    _make_manifest(manifest_path)

    monkeypatch.setattr(enrich, "summarize_workflow", lambda *_a, **_kw: _sample_summary())
    monkeypatch.setattr(
        enrich, "_find_existing_resource", lambda *_a, **_kw: {"exists": False}
    )
    monkeypatch.setattr(enrich, "_post", lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("boom")))

    counts = enrich.enrich(
        corpus_dir=corpus_dir,
        manifest_path=manifest_path,
        upload=True,
        upload_sleep=0,
    )

    assert counts["processed"] == 1
    assert counts["uploaded"] == 0
    assert counts["upload_skipped"] == 0
    assert counts["upload_errors"] == 1
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert persisted["workflows"][0]["hivemind_upload"]["status"] == "error"
    assert "boom" in persisted["workflows"][0]["hivemind_upload"]["error"]


def test_upload_only_touches_processed_rows(monkeypatch, tmp_path: Path) -> None:
    corpus_dir = tmp_path / "external_workflows" / "corpus"
    manifest_path = tmp_path / "external_workflows" / "manifest.json"
    corpus_dir.mkdir(parents=True, exist_ok=True)

    # Two workflows. "old" already has a current summary and should be skipped.
    old_wf = {"nodes": {"1": {"class_type": "KSampler"}}, "edges": []}
    new_wf = {"nodes": {"1": {"class_type": "LoadCheckpoint"}}, "edges": []}

    (corpus_dir / "old.json").write_text(json.dumps(old_wf), encoding="utf-8")
    (corpus_dir / "new.json").write_text(json.dumps(new_wf), encoding="utf-8")

    old_hash = enrich._content_hash(old_wf)
    old_wf["metadata"] = {"summary": {**_sample_summary(), "_content_hash": old_hash}}
    (corpus_dir / "old.json").write_text(json.dumps(old_wf), encoding="utf-8")

    rows = [
        _sample_manifest_row(
            workflow_id="old",
            canonical_workflow_hash="oldhash",
            corpus_path="external_workflows/corpus/old.json",
        ),
        _sample_manifest_row(
            workflow_id="new",
            canonical_workflow_hash="newhash",
            corpus_path="external_workflows/corpus/new.json",
        ),
    ]
    manifest_path.write_text(
        json.dumps({"workflows": rows}, indent=2),
        encoding="utf-8",
    )

    monkeypatch.setattr(enrich, "summarize_workflow", lambda *_a, **_kw: _sample_summary())
    monkeypatch.setattr(
        enrich, "_find_existing_resource", lambda *_a, **_kw: {"exists": False}
    )

    posted: list[str] = []

    def fake_post(envelope: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        posted.append(envelope["data"]["external_id"])
        return {"id": 42, "status": "ok"}

    monkeypatch.setattr(enrich, "_post", fake_post)

    counts = enrich.enrich(
        corpus_dir=corpus_dir,
        manifest_path=manifest_path,
        upload=True,
        upload_sleep=0,
    )

    assert counts["processed"] == 1
    assert counts["skipped"] == 1
    assert counts["uploaded"] == 1
    assert posted == ["vibecomfy:external_workflow:newhash"]


def test_cli_accepts_upload_flags() -> None:
    # Just ensure the argument parser does not reject the new flags.
    argv = [
        "--manifest", "external_workflows/manifest.json",
        "--corpus-dir", "external_workflows/corpus",
        "--upload",
        "--contribute-url", "https://example.com/contribute",
        "--no-skip-existing-uploads",
        "--upload-sleep", "0.5",
        "--upload-workers", "4",
    ]
    args = enrich._parse_args(argv)
    assert args.upload is True
    assert args.contribute_url == "https://example.com/contribute"
    assert args.skip_existing_uploads is False
    assert args.upload_sleep == 0.5
    assert args.upload_workers == 4


def test_content_hash_includes_requirements_dict() -> None:
    workflow = {
        "nodes": {"1": {"class_type": "KSampler"}},
        "outputs": [],
        "edges": [],
        "requirements": {"models": ["a.safetensors"], "custom_nodes": ["PackA"]},
    }
    changed = {
        **workflow,
        "requirements": {"models": ["b.safetensors"], "custom_nodes": ["PackA"]},
    }

    assert enrich._content_hash(workflow) != enrich._content_hash(changed)
