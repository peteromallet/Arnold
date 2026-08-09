"""Tests for the Phase-2 per-runtime manifest (post-bootstrap resolver)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import shadow_attestation
from arnold_pipelines.megaplan.cloud.runtime_manifest import (
    MANIFEST_SCHEMA_VERSION,
    ManifestError,
    RuntimeManifest,
    advance_generation,
    append_promotion,
    attest_runtime,
    bootstrap_manifest,
    list_manifests,
    load_manifest,
    load_manifest_by_epic,
    main,
    set_state,
    write_manifest,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _make_manifest(**overrides: object) -> dict[str, object]:
    manifest: dict[str, object] = {
        "runtime_id": "runtime-test-1",
        "schema": MANIFEST_SCHEMA_VERSION,
        "generation": 3,
        "epic_id": "epic-demo",
        "state": "active",
        "owner": "superfixer",
        "base": {
            "ref": "refs/heads/base/editable-install",
            "commit": "87a912beb",
            "editable_install_path": "/opt/arnold/base",
            "venv_path": "/opt/arnold/base/venv",
        },
        "epic": {
            "branch": "fixer/epic-demo-20260807",
            "worktree_path": "/opt/arnold/runtime-candidates/epic-demo",
            "venv_path": "/opt/arnold/runtime-candidates/epic-demo/venv",
            "runtime_root": "/opt/arnold/runtime-candidates/epic-demo/runtime",
            "expected_head": "abc123def",
            "repair_bin": "/opt/arnold/runtime-candidates/epic-demo/venv/bin/arnold-repair-loop",
            "deps_lockfile": "/opt/arnold/base/uv.lock",
        },
        "indirection": {
            "host_path": "/opt/arnold/runtime-candidates/epic-demo",
            "container_path": "/workspace/epic-demo",
            "mount_table": [],
            "execution_namespace": "epic-demo-ns",
            "verified_head": "abc123def",
            "last_verified_at": "2026-08-07T00:00:00+00:00",
            "attestation": {
                "module_file": "/opt/arnold/runtime-candidates/epic-demo/arnold_pipelines/__init__.py",
                "module_digest": "d41d8cd98f00b204e9800998ecf8427e",
                "mount_id": "0:42",
            },
        },
        "policy": {
            "policy_sha": "policy-sha-1",
            "model_policy_sha": "model-sha-1",
            "sync_policy": "push-on-promote",
        },
        "promotions": [],
        "timestamps": {
            "created": "2026-08-07T00:00:00+00:00",
            "updated": "2026-08-07T00:00:00+00:00",
            "closed": "",
        },
        "gc_policy": "closed-only",
        "commands": ["megaplan chain"],
    }
    for key, value in overrides.items():
        if (
            key in ("base", "epic", "indirection", "policy", "timestamps")
            and isinstance(manifest[key], dict)
            and isinstance(value, dict)
        ):
            merged = dict(manifest[key])  # type: ignore[arg-type]
            merged.update(value)
            manifest[key] = merged
        else:
            manifest[key] = value
    return manifest


def _make_manifest_obj(**overrides: object) -> RuntimeManifest:
    return RuntimeManifest.from_dict(_make_manifest(**overrides))


def _make_attestation_tree(tmp_path: Path) -> Path:
    """Minimal importable-layout tree so the tree-search fallback resolves the
    module file inside the tree (mirrors test_shadow_attestation)."""
    tree = tmp_path / "tree"
    cloud = tree / "arnold_pipelines" / "megaplan" / "cloud"
    cloud.mkdir(parents=True)
    (tree / "arnold_pipelines" / "__init__.py").write_text("# pkg\n", encoding="utf-8")
    (tree / "arnold_pipelines" / "megaplan" / "__init__.py").write_text(
        "# megaplan\n", encoding="utf-8"
    )
    (cloud / "__init__.py").write_text("# cloud\n", encoding="utf-8")
    (cloud / "alpha.py").write_text("ALPHA = 1\n", encoding="utf-8")
    return tree


def _not_importable(module_name: str) -> str:
    """Stand-in for ``find_spec`` returning nothing (module not importable)."""
    return ""


# ── round trip / validation ────────────────────────────────────────────────


def test_write_load_round_trip(tmp_path: Path) -> None:
    manifest = _make_manifest_obj()
    path = tmp_path / "manifests" / "runtime-manifest.json"
    write_manifest(manifest, path)
    loaded = load_manifest(path)
    assert loaded == manifest
    assert loaded.to_dict() == manifest.to_dict()
    assert loaded.schema == MANIFEST_SCHEMA_VERSION
    assert loaded.epic["repair_bin"].endswith("arnold-repair-loop")


def test_load_rejects_schema_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "old-schema.json"
    _write_json(path, _make_manifest(schema="0"))
    with pytest.raises(ManifestError, match="schema"):
        load_manifest(path)


def test_load_rejects_missing_required_field(tmp_path: Path) -> None:
    data = _make_manifest()
    del data["epic"]["repair_bin"]  # type: ignore[typeddict-item]
    path = tmp_path / "incomplete.json"
    _write_json(path, data)
    with pytest.raises(ManifestError, match="repair_bin"):
        load_manifest(path)


def test_load_rejects_missing_top_level_field(tmp_path: Path) -> None:
    data = _make_manifest()
    del data["owner"]
    path = tmp_path / "incomplete.json"
    _write_json(path, data)
    with pytest.raises(ManifestError, match="owner"):
        load_manifest(path)


def test_load_rejects_corrupt_json(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ManifestError, match="corrupt"):
        load_manifest(path)


def test_manifest_rejects_generation_below_one() -> None:
    with pytest.raises(ManifestError, match="generation"):
        _make_manifest_obj(generation=0)


def test_manifest_rejects_invalid_state() -> None:
    with pytest.raises(ManifestError, match="state"):
        _make_manifest_obj(state="destroyed")


def test_write_is_atomic_and_leaves_valid_json_on_disk(tmp_path: Path) -> None:
    path = tmp_path / "manifests" / "runtime-manifest.json"
    write_manifest(_make_manifest_obj(runtime_id="first"), path)
    write_manifest(_make_manifest_obj(runtime_id="second"), path)
    raw = path.read_text(encoding="utf-8")
    loaded = json.loads(raw)
    assert loaded["runtime_id"] == "second"
    assert RuntimeManifest.from_dict(loaded).runtime_id == "second"
    # no partial/tmp files left behind (only the persistent sibling lock file)
    leftovers = [
        p.name
        for p in path.parent.glob(f"{path.name}.*")
        if p.name != f"{path.name}.lock"
    ]
    assert leftovers == []


# ── index ───────────────────────────────────────────────────────────────────


def test_load_manifest_by_epic_finds_by_epic_id_and_none_when_absent(
    tmp_path: Path,
) -> None:
    write_manifest(
        _make_manifest_obj(runtime_id="r1", epic_id="epic-a"), tmp_path / "a.json"
    )
    write_manifest(
        _make_manifest_obj(runtime_id="r2", epic_id="epic-b"), tmp_path / "b.json"
    )
    found = load_manifest_by_epic("epic-b", tmp_path)
    assert found is not None
    assert found.runtime_id == "r2"
    assert load_manifest_by_epic("epic-absent", tmp_path) is None


def test_list_manifests_sorted_by_runtime_id(tmp_path: Path) -> None:
    write_manifest(
        _make_manifest_obj(runtime_id="r-zulu", epic_id="e1"), tmp_path / "z.json"
    )
    write_manifest(
        _make_manifest_obj(runtime_id="r-alpha", epic_id="e2"), tmp_path / "a.json"
    )
    write_manifest(
        _make_manifest_obj(runtime_id="r-mid", epic_id="e3"), tmp_path / "m.json"
    )
    names = [manifest.runtime_id for manifest in list_manifests(tmp_path)]
    assert names == ["r-alpha", "r-mid", "r-zulu"]
    assert names == sorted(names)


def test_index_skips_non_manifest_json(tmp_path: Path) -> None:
    write_manifest(_make_manifest_obj(runtime_id="r1"), tmp_path / "r1.json")
    _write_json(tmp_path / "stray.json", {"not": "a manifest"})
    assert [m.runtime_id for m in list_manifests(tmp_path)] == ["r1"]


# ── transitions ─────────────────────────────────────────────────────────────


def test_advance_generation_bumps_and_records_promotion() -> None:
    manifest = _make_manifest_obj(
        generation=2,
        epic={"expected_head": "aaaa1111"},
        indirection={"verified_head": "aaaa1111"},
    )
    advanced = advance_generation(manifest, "bbbb2222", reason="promote durable fix")
    assert advanced is not manifest
    assert advanced.generation == 3
    assert advanced.epic["expected_head"] == "bbbb2222"
    assert advanced.indirection["verified_head"] == "bbbb2222"
    assert advanced.timestamps["updated"]
    assert len(advanced.promotions) == 1
    record = advanced.promotions[0]
    assert record["previous_generation"] == 2
    assert record["previous_commit"] == "aaaa1111"
    assert record["reason"] == "promote durable fix"
    assert record["at"]
    # original manifest untouched (rollback source retained on the new one)
    assert manifest.generation == 2
    assert manifest.epic["expected_head"] == "aaaa1111"
    assert manifest.promotions == []


def test_set_state_validates_and_stamps_closed_timestamp() -> None:
    manifest = _make_manifest_obj(state="active")
    with pytest.raises(ManifestError, match="state"):
        set_state(manifest, "destroyed")
    closed = set_state(manifest, "closed")
    assert closed.state == "closed"
    assert closed.timestamps["closed"]
    # reopening preserves the historical closed timestamp
    reopened = set_state(closed, "active")
    assert reopened.state == "active"
    assert reopened.timestamps["closed"] == closed.timestamps["closed"]


def test_append_promotion() -> None:
    manifest = _make_manifest_obj()
    record = {
        "previous_generation": 1,
        "previous_commit": "c1",
        "reason": "manual rollback record",
        "at": "2026-08-07T12:00:00+00:00",
    }
    updated = append_promotion(manifest, record)
    assert updated.promotions == [record]
    assert manifest.promotions == []
    with pytest.raises(ManifestError, match="record"):
        append_promotion(manifest, ["not", "a", "dict"])


# ── attestation ─────────────────────────────────────────────────────────────


def test_attest_runtime_returns_expected_keys_with_tree_search_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = _make_attestation_tree(tmp_path)
    manifest = _make_manifest_obj(
        epic={"runtime_root": str(tree)},
    )
    # force the tree-search fallback (module not importable from the temp tree)
    monkeypatch.setattr(shadow_attestation, "_find_spec_origin", _not_importable)
    result = attest_runtime(manifest)
    assert set(result) == {
        "module_file",
        "module_digest",
        "mount_id",
        "declared_vs_observed_match",
        "errors",
    }
    assert result["module_file"] == str(tree / "arnold_pipelines" / "__init__.py")
    assert result["module_digest"]
    assert result["declared_vs_observed_match"] is True
    if sys.platform == "linux":
        assert result["errors"] == []
    else:
        # non-Linux: only the expected mount probe is unavailable; no module/tree errors
        assert [
            entry
            for entry in result["errors"]
            if not entry.startswith("mount_id_unavailable")
        ] == []


def test_attest_runtime_never_raises_on_broken_runtime_root(tmp_path: Path) -> None:
    manifest = _make_manifest_obj(
        epic={"runtime_root": str(tmp_path / "does-not-exist")},
    )
    result = attest_runtime(manifest)
    assert set(result) == {
        "module_file",
        "module_digest",
        "mount_id",
        "declared_vs_observed_match",
        "errors",
    }
    assert result["declared_vs_observed_match"] is False
    assert result["errors"]


def test_attest_runtime_never_raises_when_probe_blows_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _make_manifest_obj(epic={"runtime_root": str(tmp_path)})
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.runtime_manifest.attest_target_content",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    result = attest_runtime(manifest)
    assert result["errors"] == ["attestation_failed:boom"]
    assert result["declared_vs_observed_match"] is False


# ── bootstrap ───────────────────────────────────────────────────────────────


def test_bootstrap_manifest_from_pointer_file(tmp_path: Path) -> None:
    manifest = _make_manifest_obj(runtime_id="booted")
    manifest_path = tmp_path / "manifests" / "runtime-manifest.json"
    write_manifest(manifest, manifest_path)
    pointer = tmp_path / "bootstrap"
    pointer.write_text(f"# active runtime\n{manifest_path}\n", encoding="utf-8")
    loaded = bootstrap_manifest(pointer)
    assert loaded.runtime_id == "booted"
    assert loaded == manifest


def test_bootstrap_manifest_from_directory(tmp_path: Path) -> None:
    manifest = _make_manifest_obj(runtime_id="dir-booted")
    write_manifest(manifest, tmp_path / "manifests" / "runtime-manifest.json")
    loaded = bootstrap_manifest(tmp_path / "manifests")
    assert loaded == manifest


def test_bootstrap_manifest_from_json_file_directly(tmp_path: Path) -> None:
    manifest = _make_manifest_obj(runtime_id="json-booted")
    path = tmp_path / "runtime-manifest.json"
    write_manifest(manifest, path)
    assert bootstrap_manifest(path) == manifest


def test_bootstrap_manifest_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="does not exist"):
        bootstrap_manifest(tmp_path / "nope")


def test_bootstrap_manifest_empty_pointer_raises(tmp_path: Path) -> None:
    pointer = tmp_path / "bootstrap"
    pointer.write_text("# nothing here\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="no manifest path"):
        bootstrap_manifest(pointer)


# ── CLI ─────────────────────────────────────────────────────────────────────


def test_main_write_read_attest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    manifest = _make_manifest_obj(runtime_id="cli-booted")
    src = tmp_path / "src.json"
    src.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
    path = tmp_path / "runtime-manifest.json"
    assert main(["write", str(path), "--from", str(src)]) == 0
    assert path.exists()
    capsys.readouterr()  # drain the write subcommand's stdout
    assert main(["read", str(path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["runtime_id"] == "cli-booted"
    assert main(["attest", str(path)]) == 0
    attest_out = json.loads(capsys.readouterr().out)
    assert set(attest_out) == {
        "module_file",
        "module_digest",
        "mount_id",
        "declared_vs_observed_match",
        "errors",
    }


def test_main_read_rejects_invalid_manifest(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    _write_json(path, _make_manifest(schema="0"))
    assert main(["read", str(path)]) == 2
