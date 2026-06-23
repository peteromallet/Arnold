from __future__ import annotations

from pathlib import Path

from scripts.check_workflow_pipeline_inventory import (
    PIPELINE_DISPOSITION,
    main as inventory_main,
)
from scripts.check_pipeline_id_registry import (
    build_manifest_identity_report,
    check_manifest_identity_report,
    check_registry_hashes,
    check_survivor_only_refs,
    discover_registry_files,
    main as registry_main,
    render_manifest_identity_report,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_inventory_main_passes() -> None:
    assert inventory_main([]) == 0


def test_inventory_flags_unknown_status(tmp_path: Path, monkeypatch) -> None:
    from scripts import check_workflow_pipeline_inventory as mod

    original = mod.PIPELINE_DISPOSITION
    monkeypatch.setattr(
        mod,
        "PIPELINE_DISPOSITION",
        {"test/root": {"status": "unknown"}},
    )
    assert inventory_main([]) == 1


def test_inventory_detects_forbidden_pattern_in_migrated_root(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts import check_workflow_pipeline_inventory as mod

    fake_root = tmp_path / "fake_root"
    fake_root.mkdir()
    (fake_root / "pipeline.py").write_text(
        "from arnold.pipeline import PipelineBuilder\n", encoding="utf-8"
    )

    fake_disposition = {
        "fake_root": {"status": "migrate", "registry_id": "fake", "migrated": True},
    }
    monkeypatch.setattr(mod, "PIPELINE_DISPOSITION", fake_disposition)

    def fake_discover() -> list[Path]:
        return [fake_root]

    monkeypatch.setattr(mod, "_discover_shipped_roots", fake_discover)
    monkeypatch.setattr(mod, "_normalize_root", lambda _path: "fake_root")

    assert inventory_main([]) == 1


def test_registry_main_passes() -> None:
    assert registry_main([]) == 0


def test_registry_identity_report_is_derived_from_current_manifests() -> None:
    report = build_manifest_identity_report(root=REPO_ROOT)
    identities = {
        item["registry_id"]: item for item in report["identities"]
    }

    evidence = identities["evidence_pack.verifier"]
    assert evidence["package_path"] == "arnold_pipelines/evidence_pack"
    assert evidence["skill_docs"] == {
        "path": "arnold_pipelines/evidence_pack/SKILL.md",
        "exists": True,
    }
    assert evidence["example_docs"] == {
        "path": "docs/arnold/examples/evidence-pack-verifier.md",
        "exists": True,
    }
    assert evidence["registry_manifest_hash"] == evidence["compiled_manifest_hash"]
    assert evidence["registry_entry"]["manifest_hash"] == evidence["compiled_manifest_hash"]


def test_registry_identity_report_check_detects_stale_output(tmp_path: Path) -> None:
    report = build_manifest_identity_report(root=REPO_ROOT)
    report_path = tmp_path / "manifest-identity-report.json"
    report_path.write_text(render_manifest_identity_report(report), encoding="utf-8")
    assert check_manifest_identity_report(report_path, report) == []

    report_path.write_text('{"stale": true}\n', encoding="utf-8")
    assert check_manifest_identity_report(report_path, report)


def test_registry_hash_check_rejects_invalid_hash(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        '{"version": 1, "pipelines": [{"name": "x", "stable_id": "x", "manifest_hash": "not-a-hash"}]}',
        encoding="utf-8",
    )
    errors = check_registry_hashes([path])
    assert errors


def test_registry_survivor_check_rejects_unknown_stable_id(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        '{"version": 1, "pipelines": [{"name": "x", "stable_id": "deleted.legacy"}]}',
        encoding="utf-8",
    )
    errors = check_survivor_only_refs([path])
    assert errors


def test_registry_discover_filters_legacy_duplicate() -> None:
    paths = discover_registry_files(REPO_ROOT)
    relative = [p.relative_to(REPO_ROOT).as_posix() for p in paths]
    # The old Megaplan registry artifacts should not be rediscovered after M5
    # cleanup; surviving source-controlled registries stay under arnold_pipelines.
    assert "arnold/pipelines/megaplan/_pipeline/pipeline_ids.json" not in relative
    assert "arnold_pipelines/evidence_pack/pipeline_ids.json" in relative


def test_pipeline_disposition_has_no_unknown_status() -> None:
    valid = {"migrate", "delete", "archive", "whitelist"}
    for root, info in PIPELINE_DISPOSITION.items():
        assert info.get("status") in valid, f"{root} has invalid status"
