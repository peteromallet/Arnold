from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.orchestration.completion_contract import (
    ArtifactRef,
    CompletionSubject,
    EvidenceRef,
    EvidenceStatus,
    TrustClass,
)
from arnold.pipelines.megaplan.orchestration.review_evidence import (
    REVIEW_EVIDENCE_FILENAME,
    REVIEW_EVIDENCE_SCHEMA,
    collect_review_evidence,
)


def _subject(name: str = "plan-x") -> CompletionSubject:
    return CompletionSubject(kind="plan", name=name, to_state="done", plan_name=name, phase="review")


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=path, check=True)


def test_collect_review_evidence_persists_metadata_and_round_trippable_refs(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    _init_git_repo(project_dir)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    class _Provider:
        kind = "fresh_review"

        def collect(self, ctx):
            return EvidenceRef(
                kind="fresh_review",
                status=EvidenceStatus.satisfied,
                summary="reviewed current repo state",
                details={"observed": True},
                trust_class=TrustClass.evidence,
                provider="fresh_review",
                provider_version="1",
                artifact=ArtifactRef(path="review_evidence.json", artifact_type="plan_artifact"),
                artifacts=(
                    ArtifactRef(path="review_evidence.json", artifact_type="plan_artifact"),
                    ArtifactRef(path="notes.txt", artifact_type="auxiliary"),
                ),
                source="fake-provider",
                subject="plan-x",
                observed_at="2026-06-08T00:00:00Z",
                code_hash="abc123",
            )

    state = {
        "meta": {
            "current_invocation_id": "inv-123",
            "chain_policy": {"milestone_base_sha": "base-from-state"},
        }
    }
    payload = collect_review_evidence(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state,
        subject=_subject(),
        iteration=4,
        providers=(_Provider(),),
    )

    persisted = json.loads((plan_dir / REVIEW_EVIDENCE_FILENAME).read_text(encoding="utf-8"))
    assert persisted["schema"] == REVIEW_EVIDENCE_SCHEMA
    assert persisted["subject"] == _subject().to_dict()
    assert payload["artifact"] == REVIEW_EVIDENCE_FILENAME
    assert payload["phase"] == "review"
    assert payload["iteration"] == 4
    assert payload["base_sha"] == "base-from-state"
    assert payload["head_sha"]
    assert payload["invocation_id"] == "inv-123"
    assert payload["providers_used"] == ["fresh_review"]
    assert payload["provider_diagnostics"]["fresh_review"] == {"ok": True}
    assert payload["diagnostics"]["base_sha"]["source"] == "state.meta.chain_policy.milestone_base_sha"
    assert persisted["provider_diagnostics"] == payload["provider_diagnostics"]
    assert persisted["evidence"][0] == payload["evidence"][0]

    loaded_from_payload = EvidenceRef.from_dict(payload["evidence"][0])
    loaded_from_disk_once = EvidenceRef.from_dict(persisted["evidence"][0])
    loaded_from_disk_twice = EvidenceRef.from_dict(persisted["evidence"][0])
    assert loaded_from_payload == loaded_from_disk_once == loaded_from_disk_twice
    assert loaded_from_disk_once.kind == "fresh_review"
    assert loaded_from_disk_once.artifact == ArtifactRef(
        path="review_evidence.json",
        artifact_type="plan_artifact",
    )
    assert loaded_from_disk_once.artifacts == (
        ArtifactRef(path="review_evidence.json", artifact_type="plan_artifact"),
        ArtifactRef(path="notes.txt", artifact_type="auxiliary"),
    )
    assert loaded_from_disk_once.source == "fake-provider"
    assert loaded_from_disk_once.subject == "plan-x"
    assert loaded_from_disk_once.observed_at == "2026-06-08T00:00:00Z"
    assert loaded_from_disk_once.code_hash == "abc123"


def test_collect_review_evidence_records_provider_failures_without_aborting(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    _init_git_repo(project_dir)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    class _Boom:
        kind = "boom"

        def collect(self, ctx):
            raise RuntimeError("kaboom")

    payload = collect_review_evidence(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state={},
        subject=_subject(),
        providers=(_Boom(),),
    )
    persisted = json.loads((plan_dir / REVIEW_EVIDENCE_FILENAME).read_text(encoding="utf-8"))

    assert payload["accepted"] is True
    assert payload["provider_diagnostics"]["boom"]["ok"] is False
    assert payload["provider_diagnostics"]["boom"]["exception_type"] == "RuntimeError"
    assert persisted["provider_diagnostics"] == payload["provider_diagnostics"]
    assert payload["evidence"][0]["status"] == "unknown"
    assert "provider crashed: kaboom" in payload["evidence"][0]["summary"]
    assert EvidenceRef.from_dict(persisted["evidence"][0]).status is EvidenceStatus.unknown


def test_collect_review_evidence_fails_soft_for_git_and_invocation_lookup(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    class _Provider:
        kind = "noop"

        def collect(self, ctx):
            return EvidenceRef("noop", EvidenceStatus.unknown, "noop", {})

    payload = collect_review_evidence(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state={},
        subject=_subject(),
        providers=(_Provider(),),
    )

    assert payload["base_sha"] is None
    assert payload["head_sha"] is None
    assert payload["invocation_id"] is None
    assert payload["diagnostics"]["base_sha"]["ok"] is False
    assert payload["diagnostics"]["head_sha"]["ok"] is False
    assert payload["diagnostics"]["invocation_id"]["ok"] is False
    assert payload["diagnostics"]["base_sha"]["source"] == "git_rev_parse_head_fallback"
    assert payload["diagnostics"]["head_sha"]["source"] == "git_rev_parse_head"
    assert payload["diagnostics"]["base_sha"]["command"] == ["git", "rev-parse", "HEAD"]
    assert payload["diagnostics"]["head_sha"]["command"] == ["git", "rev-parse", "HEAD"]
    assert payload["diagnostics"]["base_sha"]["exception_type"] == "CalledProcessError"
    assert payload["diagnostics"]["head_sha"]["exception_type"] == "CalledProcessError"
    assert payload["diagnostics"]["invocation_id"]["source"] == "state.meta.current_invocation_id"
    assert payload["diagnostics"]["invocation_id"]["error"] == "missing invocation id"


def test_collect_review_evidence_keeps_json_write_failure_hard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    _init_git_repo(project_dir)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    class _Provider:
        kind = "noop"

        def collect(self, ctx):
            return EvidenceRef("noop", EvidenceStatus.satisfied, "ok", {})

    def _boom(path, data):
        raise OSError("disk full")

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.orchestration.review_evidence.atomic_write_json",
        _boom,
    )

    with pytest.raises(OSError, match="disk full"):
        collect_review_evidence(
            plan_dir=plan_dir,
            project_dir=project_dir,
            state={},
            subject=_subject(),
            providers=(_Provider(),),
        )
