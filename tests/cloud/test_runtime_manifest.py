"""Tests for the Phase-2 per-runtime manifest (post-bootstrap resolver)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
from arnold_pipelines.megaplan.cloud import shadow_attestation
from arnold_pipelines.megaplan.cloud.runtime_manifest import (
    COMPATIBILITY_ONLY_KEY,
    MANIFEST_FILENAME,
    MANIFEST_SCHEMA_VERSION,
    ManifestError,
    RuntimeManifest,
    active_manifest_path,
    add_deviation,
    advance_generation,
    append_promotion,
    attest_runtime,
    bootstrap_manifest,
    has_valid_allow_manifestless_permit,
    is_compatibility_only_pointer,
    list_manifests,
    load_manifest,
    load_manifest_by_epic,
    main,
    manifest_present,
    set_state,
    validate_deviation,
    write_active_pointer,
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


def _make_deviation(**overrides: object) -> dict[str, object]:
    """A structurally valid, currently-unexpired deviation record (defaults to
    ``kind=allow_manifestless``, issued now, expiring in 1h)."""
    now = datetime.now(timezone.utc)
    record: dict[str, object] = {
        "kind": "allow_manifestless",
        "id": "perm-0001",
        "issued_at": now.isoformat(timespec="seconds"),
        "expires_at": (now + timedelta(hours=1)).isoformat(timespec="seconds"),
        "actor": "operator",
        "reason": "box migration window",
        "evidence": ["incident-42", "approval-email"],
        "chain_digest": "sha256:deadbeef",
    }
    record.update(overrides)
    return record


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


# ── deviations (expiring exception records) ─────────────────────────────────


def test_from_dict_defaults_deviations_to_empty_list() -> None:
    manifest = _make_manifest_obj()
    assert manifest.deviations == []
    # the fixture itself carries no deviations key (old-manifest shape)
    assert "deviations" not in _make_manifest()


def test_deviations_round_trip_preserved(tmp_path: Path) -> None:
    record = _make_deviation()
    manifest = _make_manifest_obj(deviations=[record])
    assert manifest.deviations == [record]
    path = tmp_path / "m.json"
    write_manifest(manifest, path)
    loaded = load_manifest(path)
    assert loaded == manifest
    assert loaded.deviations == [record]
    # the serialized JSON on disk actually carries the list
    assert json.loads(path.read_text(encoding="utf-8"))["deviations"] == [record]
    # a second read→write cycle preserves it as well
    write_manifest(loaded, path)
    assert load_manifest(path).deviations == [record]


def test_all_transitions_preserve_deviations() -> None:
    record = _make_deviation()
    manifest = _make_manifest_obj(deviations=[record])
    closed = set_state(manifest, "closed")
    assert closed.deviations == [record]
    advanced = advance_generation(manifest, "newsha001", reason="preserve check")
    assert advanced.deviations == [record]
    promoted = append_promotion(
        manifest,
        {
            "previous_generation": 1,
            "previous_commit": "c1",
            "reason": "rollback record",
            "at": "2026-08-07T12:00:00+00:00",
        },
    )
    assert promoted.deviations == [record]
    assert manifest.deviations == [record]  # original untouched


def test_manifest_rejects_non_list_deviations() -> None:
    with pytest.raises(ManifestError, match="deviations"):
        _make_manifest_obj(deviations="not-a-list")
    with pytest.raises(ManifestError, match="deviations"):
        _make_manifest_obj(deviations={"kind": "allow_manifestless"})


def test_manifest_rejects_non_object_deviation_entries() -> None:
    with pytest.raises(ManifestError, match="deviations"):
        _make_manifest_obj(deviations=[_make_deviation(), "not-an-object"])


def test_validate_deviation_rejects_non_object_record() -> None:
    with pytest.raises(ManifestError, match="object"):
        validate_deviation("not-a-dict")
    with pytest.raises(ManifestError, match="object"):
        validate_deviation(["not", "a", "dict"])


def test_validate_deviation_rejects_missing_fields() -> None:
    for field_name in (
        "kind",
        "id",
        "issued_at",
        "expires_at",
        "actor",
        "reason",
        "evidence",
        "chain_digest",
    ):
        bad = dict(_make_deviation())
        del bad[field_name]
        with pytest.raises(ManifestError, match=field_name):
            validate_deviation(bad)


def test_validate_deviation_rejects_empty_string_fields() -> None:
    for field_name in ("kind", "id", "actor", "reason", "chain_digest"):
        bad = _make_deviation(**{field_name: ""})
        with pytest.raises(ManifestError, match=field_name):
            validate_deviation(bad)


def test_validate_deviation_rejects_non_utc_timestamps() -> None:
    naive = _make_deviation(issued_at="2026-08-07T00:00:00")  # no tz info
    with pytest.raises(ManifestError, match="UTC"):
        validate_deviation(naive)
    offset = _make_deviation(expires_at="2026-08-07T00:00:00+05:00")  # wrong offset
    with pytest.raises(ManifestError, match="UTC"):
        validate_deviation(offset)
    unparsable = _make_deviation(issued_at="not-a-date")
    with pytest.raises(ManifestError, match="ISO8601"):
        validate_deviation(unparsable)
    empty = _make_deviation(expires_at="")
    with pytest.raises(ManifestError, match="expires_at"):
        validate_deviation(empty)


def test_validate_deviation_rejects_bad_evidence() -> None:
    not_list = _make_deviation(evidence="not-a-list")
    with pytest.raises(ManifestError, match="evidence"):
        validate_deviation(not_list)
    non_strings = _make_deviation(evidence=["ok", 42])
    with pytest.raises(ManifestError, match="evidence"):
        validate_deviation(non_strings)


def test_validate_deviation_accepts_empty_evidence() -> None:
    # contract: evidence is a list of strings; an empty list is structurally valid
    record = _make_deviation(evidence=[])
    assert validate_deviation(record) == record


def test_validate_deviation_rejects_expired() -> None:
    now = datetime.now(timezone.utc)
    record = _make_deviation(
        issued_at=(now - timedelta(hours=2)).isoformat(timespec="seconds"),
        expires_at=(now - timedelta(hours=1)).isoformat(timespec="seconds"),
    )
    with pytest.raises(ManifestError, match="expired"):
        validate_deviation(record)


def test_validate_deviation_rejects_lifetime_outside_bounds() -> None:
    now = datetime.now(timezone.utc)
    too_long = _make_deviation(
        issued_at=now.isoformat(timespec="seconds"),
        expires_at=(now + timedelta(hours=25)).isoformat(timespec="seconds"),
    )
    with pytest.raises(ManifestError, match="24h"):
        validate_deviation(too_long)
    zero = _make_deviation(
        issued_at=now.isoformat(timespec="seconds"),
        expires_at=now.isoformat(timespec="seconds"),
    )
    with pytest.raises(ManifestError, match="24h"):
        validate_deviation(zero)
    backwards = _make_deviation(
        issued_at=now.isoformat(timespec="seconds"),
        expires_at=(now - timedelta(hours=1)).isoformat(timespec="seconds"),
    )
    with pytest.raises(ManifestError, match="24h"):
        validate_deviation(backwards)


def test_validate_deviation_returns_record_unchanged_on_success() -> None:
    record = _make_deviation()
    assert validate_deviation(record) is record
    # extra keys (e.g. a revoked_at tombstone) are tolerated + preserved
    tombstoned = _make_deviation(revoked_at="2026-08-07T00:00:00+00:00")
    assert validate_deviation(tombstoned) == tombstoned


def test_has_valid_allow_manifestless_permit() -> None:
    now = datetime.now(timezone.utc)
    valid = _make_deviation()
    assert (
        has_valid_allow_manifestless_permit(
            _make_manifest_obj(deviations=[valid])
        )
        is True
    )
    # no deviations at all -> no permit
    assert has_valid_allow_manifestless_permit(_make_manifest_obj()) is False
    # wrong kind does not admit
    wrong_kind = dict(valid, kind="manifest_missing")
    assert (
        has_valid_allow_manifestless_permit(
            _make_manifest_obj(deviations=[wrong_kind])
        )
        is False
    )
    # expired permit does not admit
    expired = _make_deviation(
        issued_at=(now - timedelta(hours=2)).isoformat(timespec="seconds"),
        expires_at=(now - timedelta(hours=1)).isoformat(timespec="seconds"),
    )
    assert (
        has_valid_allow_manifestless_permit(
            _make_manifest_obj(deviations=[expired])
        )
        is False
    )
    # revoked permit (auditable tombstone) does not admit
    revoked = dict(valid, revoked_at="2026-08-07T00:00:00+00:00")
    assert (
        has_valid_allow_manifestless_permit(
            _make_manifest_obj(deviations=[revoked])
        )
        is False
    )
    # one valid permit wins even among invalid/expired records; a bad record
    # cannot poison admission
    mixed = _make_manifest_obj(deviations=[expired, {"kind": "garbage"}, valid])
    assert has_valid_allow_manifestless_permit(mixed) is True
    # a malformed record alone never admits
    malformed = _make_manifest_obj(deviations=[{"kind": "allow_manifestless"}])
    assert has_valid_allow_manifestless_permit(malformed) is False


def test_add_deviation_appends_immutably() -> None:
    manifest = _make_manifest_obj()
    record = _make_deviation()
    updated = add_deviation(manifest, record)
    assert updated is not manifest
    assert updated.deviations == [record]
    assert manifest.deviations == []  # original untouched
    second = _make_deviation(id="perm-0002")
    again = add_deviation(updated, second)
    assert again.deviations == [record, second]
    assert updated.deviations == [record]  # intermediate also untouched


def test_add_deviation_rejects_invalid_record_and_leaves_manifest_untouched() -> None:
    manifest = _make_manifest_obj()
    now = datetime.now(timezone.utc)
    expired = _make_deviation(
        issued_at=(now - timedelta(hours=2)).isoformat(timespec="seconds"),
        expires_at=(now - timedelta(hours=1)).isoformat(timespec="seconds"),
    )
    with pytest.raises(ManifestError, match="expired"):
        add_deviation(manifest, expired)
    missing = dict(_make_deviation())
    del missing["chain_digest"]
    with pytest.raises(ManifestError, match="chain_digest"):
        add_deviation(manifest, missing)
    assert manifest.deviations == []


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


# ── compatibility_only pointer (G2 correction 1) ───────────────────────────


def _compatibility_pointer(path: Path) -> Path:
    """A full manifest JSON additionally marked ``compatibility_only: true`` —
    the exact shape arnold-runtime-create writes as compatibility telemetry."""
    payload = dict(_make_manifest(runtime_id="telemetry-pointer"))
    payload[COMPATIBILITY_ONLY_KEY] = True
    _write_json(path, payload)
    return path


def test_is_compatibility_only_pointer_detects_marker(tmp_path: Path) -> None:
    pointer = _compatibility_pointer(tmp_path / "pointer.json")
    assert is_compatibility_only_pointer(pointer) is True
    # a plain valid manifest (no marker) is NOT compatibility telemetry
    real = tmp_path / "real.json"
    write_manifest(_make_manifest_obj(), real)
    assert is_compatibility_only_pointer(real) is False
    # absent / non-JSON files are not compatibility pointers (they fail on
    # their own as absent/invalid)
    assert is_compatibility_only_pointer(tmp_path / "missing.json") is False
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json", encoding="utf-8")
    assert is_compatibility_only_pointer(corrupt) is False
    # marker must be the literal boolean true
    falsy = tmp_path / "falsy.json"
    _write_json(falsy, {**dict(_make_manifest()), COMPATIBILITY_ONLY_KEY: "true"})
    assert is_compatibility_only_pointer(falsy) is False


def test_bootstrap_manifest_rejects_compatibility_only_pointer(
    tmp_path: Path,
) -> None:
    """A compatibility_only pointer is NON-AUTHORITATIVE: the resolver treats
    it as ABSENT (raises) so it can never select a runtime."""
    pointer = _compatibility_pointer(tmp_path / "runtime-manifest.json")
    with pytest.raises(ManifestError, match="compatibility_only"):
        bootstrap_manifest(pointer)
    # same rejection through a directory bootstrap (canonical filename)
    directory = tmp_path / "manifest-dir"
    _compatibility_pointer(directory / MANIFEST_FILENAME)
    with pytest.raises(ManifestError, match="compatibility_only"):
        bootstrap_manifest(directory)
    # same rejection through a legacy pointer file naming the marked target
    legacy = tmp_path / "bootstrap"
    legacy.write_text(f"{pointer}\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="compatibility_only"):
        bootstrap_manifest(legacy)


def test_manifest_present_treats_compatibility_only_as_absent(
    tmp_path: Path,
) -> None:
    """Admission probe: present+valid+authoritative is True; everything else
    (missing, corrupt, schema-invalid, or a compatibility_only pointer) is
    ABSENT (False)."""
    real = tmp_path / "real.json"
    write_manifest(_make_manifest_obj(), real)
    assert manifest_present(real) is True
    assert manifest_present(tmp_path / "missing.json") is False
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json", encoding="utf-8")
    assert manifest_present(corrupt) is False
    invalid = tmp_path / "invalid.json"
    _write_json(invalid, _make_manifest(schema="99"))
    assert manifest_present(invalid) is False
    pointer = _compatibility_pointer(tmp_path / "pointer.json")
    assert manifest_present(pointer) is False


# ── compatibility_only as a preserved manifest field (G2 second re-run) ──────


def test_from_dict_defaults_compatibility_only_false() -> None:
    """Old manifests (schema "1", no marker) load with compatibility_only False
    — authoritative; only the explicit boolean True demotes a pointer."""
    manifest = _make_manifest_obj()
    assert manifest.compatibility_only is False
    assert COMPATIBILITY_ONLY_KEY not in _make_manifest()
    loaded = RuntimeManifest.from_dict(
        dict(_make_manifest(), compatibility_only=True)
    )
    assert loaded.compatibility_only is True


def test_manifest_rejects_non_bool_compatibility_only() -> None:
    with pytest.raises(ManifestError, match="compatibility_only"):
        _make_manifest_obj(compatibility_only="true")


def test_to_dict_round_trip_preserves_compatibility_only() -> None:
    marked = _make_manifest_obj(compatibility_only=True)
    payload = marked.to_dict()
    assert payload[COMPATIBILITY_ONLY_KEY] is True
    # serialized JSON round trip (the write_manifest path) keeps the marker
    round_tripped = RuntimeManifest.from_dict(json.loads(json.dumps(payload)))
    assert round_tripped.compatibility_only is True
    assert round_tripped.to_dict()[COMPATIBILITY_ONLY_KEY] is True


def test_write_active_pointer_carries_marker_and_demotion_is_durable(
    tmp_path: Path,
) -> None:
    """The pointer is written with the marker as part of the manifest payload,
    and once demoted it STAYS demoted across every subsequent pointer write —
    a promote/close transition can never re-admit the global pointer."""
    pointer = tmp_path / "pointer.json"
    marked = _make_manifest_obj(generation=1, compatibility_only=True)
    write_active_pointer(marked, pointer)
    payload = json.loads(pointer.read_text())
    assert payload[COMPATIBILITY_ONLY_KEY] is True
    assert is_compatibility_only_pointer(pointer) is True
    # the marker is a preserved field: the pointer reads back as a manifest
    # (resolvers refuse it) and a generation switch keeps it demoted
    assert load_manifest(pointer).compatibility_only is True
    write_active_pointer(_make_manifest_obj(generation=2), pointer)
    payload = json.loads(pointer.read_text())
    assert payload[COMPATIBILITY_ONLY_KEY] is True
    assert payload["generation"] == 2
    assert is_compatibility_only_pointer(pointer) is True


def test_generic_write_manifest_cannot_readmit_demoted_active_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G2 final fix: the generic write_manifest() path can target the active
    pointer — an AUTHORITATIVE manifest (compatibility_only False/absent)
    written over a demoted pointer must NOT re-admit it. The demotion
    invariant lives in the lowest-level writer, so no writer can strip the
    marker from the active pointer."""
    pointer = tmp_path / "runtime-manifest.json"
    _compatibility_pointer(pointer)  # demoted active pointer
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(pointer))
    assert is_compatibility_only_pointer(pointer) is True

    # the generic write path with a fully authoritative manifest payload
    write_manifest(_make_manifest_obj(runtime_id="readmit-attempt"), pointer)

    # the pointer still carries the marker in the WRITTEN payload …
    assert is_compatibility_only_pointer(pointer) is True
    payload = json.loads(pointer.read_text())
    assert payload[COMPATIBILITY_ONLY_KEY] is True
    assert payload["runtime_id"] == "readmit-attempt"  # content was written
    # … the manifest reads back demoted, …
    assert load_manifest(pointer).compatibility_only is True
    # … admission treats it as ABSENT, …
    assert manifest_present(pointer) is False
    # … and bootstrap refuses to select a runtime from it.
    with pytest.raises(ManifestError, match="compatibility_only"):
        bootstrap_manifest(active_manifest_path())


def test_write_manifest_does_not_force_marker_on_per_slug_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the ACTIVE POINTER path is protected: a per-slug authoritative
    manifest written to a DIFFERENT path is never forced to carry the
    compatibility_only marker, even while the active pointer is demoted."""
    pointer = tmp_path / "runtime-manifest.json"
    _compatibility_pointer(pointer)  # demoted active pointer
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(pointer))

    slug = tmp_path / "slugs" / "epic-demo" / "runtime-manifest.json"
    write_manifest(_make_manifest_obj(runtime_id="per-slug"), slug)

    # the per-slug manifest is authoritative — no marker was forced
    assert is_compatibility_only_pointer(slug) is False
    assert manifest_present(slug) is True
    assert load_manifest(slug).compatibility_only is False
    assert json.loads(slug.read_text()).get(COMPATIBILITY_ONLY_KEY, False) is False
    # and the active pointer is untouched (still demoted)
    assert is_compatibility_only_pointer(pointer) is True


def test_reconstruct_preserves_compatibility_only() -> None:
    """Every immutable transition (advance_generation / set_state) carries the
    marker — promote and close cannot strip it from the pointer."""
    marked = _make_manifest_obj(compatibility_only=True)
    advanced = advance_generation(marked, "newsha001", reason="preserve marker")
    assert advanced.compatibility_only is True
    closed = set_state(advanced, "closed")
    assert closed.compatibility_only is True
    assert closed.to_dict()[COMPATIBILITY_ONLY_KEY] is True


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


# ── active-generation pointer ───────────────────────────────────────────────


def test_active_manifest_path_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    assert active_manifest_path() == Path("/workspace/.megaplan") / MANIFEST_FILENAME
    pointer = tmp_path / "custom" / "pointer.json"
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(pointer))
    assert active_manifest_path() == pointer


def test_write_active_pointer_first_write_and_retention(tmp_path: Path) -> None:
    pointer = tmp_path / "pointer.json"
    assert write_active_pointer(_make_manifest_obj(generation=1), pointer) == pointer
    assert load_manifest(pointer).generation == 1
    assert not list(tmp_path.glob("pointer.json.previous-*"))
    # same-generation rewrite (e.g. set_state): no retention
    write_active_pointer(_make_manifest_obj(generation=1, state="closed"), pointer)
    assert not list(tmp_path.glob("pointer.json.previous-*"))
    # strict generation bump: previous generation retained for rollback
    write_active_pointer(_make_manifest_obj(generation=2), pointer)
    assert load_manifest(pointer).generation == 2
    retained = tmp_path / "pointer.json.previous-1.json"
    assert retained.exists()
    assert load_manifest(retained).generation == 1


def test_write_active_pointer_refuses_invalid_existing_pointer(tmp_path: Path) -> None:
    pointer = tmp_path / "pointer.json"
    pointer.write_text("{not json", encoding="utf-8")
    with pytest.raises(ManifestError, match="fail-closed"):
        write_active_pointer(_make_manifest_obj(), pointer)
    assert pointer.read_text() == "{not json"  # untouched


def test_bootstrap_manifest_resolves_through_active_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pointer = tmp_path / "pointer.json"
    manifest = _make_manifest_obj(runtime_id="ptr-booted")
    write_active_pointer(manifest, pointer)
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(pointer))
    # the pointer IS the active generation: bootstrap resolves it directly
    assert bootstrap_manifest(active_manifest_path()) == manifest


# ── CLI subcommands (subprocess round trips) ────────────────────────────────


def _cli_env(
    tmp_path: Path, extra_env: dict[str, str] | None = None
) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["ARNOLD_RUNTIME_MANIFEST"] = str(tmp_path / "runtime-manifest.json")
    if extra_env:
        env.update(extra_env)
    return env


def _run_cli(
    env: dict[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "arnold_pipelines.megaplan.cloud.runtime_manifest",
            *args,
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_set_state_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    write_manifest(_make_manifest_obj(), path)
    env = _cli_env(tmp_path)
    proc = _run_cli(env, "set_state", str(path), "closed")
    assert proc.returncode == 0, proc.stderr
    closed = load_manifest(path)
    assert closed.state == "closed"
    assert closed.timestamps["closed"]
    # the manifest survives a re-read round trip
    assert _run_cli(env, "read", str(path)).returncode == 0


def test_cli_set_state_rejects_unknown_state(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    write_manifest(_make_manifest_obj(), path)
    proc = _run_cli(_cli_env(tmp_path), "set_state", str(path), "destroyed")
    assert proc.returncode == 2
    assert load_manifest(path).state == "active"  # unchanged


def test_cli_append_promotion_inline_and_file(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    write_manifest(_make_manifest_obj(), path)
    env = _cli_env(tmp_path)
    record = '{"from_sha": "abc123", "to_sha": "def456", "result": "pushed"}'
    proc = _run_cli(env, "append_promotion", str(path), record)
    assert proc.returncode == 0, proc.stderr
    record_file = tmp_path / "record.json"
    record_file.write_text(record, encoding="utf-8")
    proc_file = _run_cli(env, "append_promotion", str(path), f"@{record_file}")
    assert proc_file.returncode == 0, proc_file.stderr
    manifest = load_manifest(path)
    assert [p["to_sha"] for p in manifest.promotions] == ["def456", "def456"]


def test_cli_append_promotion_rejects_bad_record(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    write_manifest(_make_manifest_obj(), path)
    env = _cli_env(tmp_path)
    assert _run_cli(env, "append_promotion", str(path), "not-json").returncode == 2
    assert _run_cli(env, "append_promotion", str(path), "[1, 2]").returncode == 2
    assert _run_cli(
        env, "append_promotion", str(path), f"@{tmp_path / 'missing.json'}"
    ).returncode == 2
    assert load_manifest(path).promotions == []


def test_cli_advance_generation_switches_pointer_and_retains_previous(
    tmp_path: Path,
) -> None:
    pointer = tmp_path / "runtime-manifest.json"
    path = tmp_path / "m.json"
    manifest = _make_manifest_obj(generation=1, epic={"expected_head": "abc123def"})
    write_manifest(manifest, path)
    # pointer already holds gen 1 (as runtime-create writes it at creation)
    write_active_pointer(manifest, pointer)
    env = _cli_env(tmp_path)
    proc = _run_cli(
        env, "advance_generation", str(path), "newsha001", "--reason", "cli test"
    )
    assert proc.returncode == 0, proc.stderr
    advanced = load_manifest(path)
    assert advanced.generation == 2
    assert advanced.epic["expected_head"] == "newsha001"
    # pointer switched to the new generation
    pointer_manifest = load_manifest(pointer)
    assert pointer_manifest.generation == 2
    assert pointer_manifest.epic["expected_head"] == "newsha001"
    # previous generation retained for rollback
    retention = tmp_path / "runtime-manifest.json.previous-1.json"
    assert retention.exists()
    assert load_manifest(retention).generation == 1
    assert load_manifest(retention).epic["expected_head"] == "abc123def"
    # bootstrap resolves through the pointer to the ACTIVE generation
    assert bootstrap_manifest(pointer) == advanced


def test_cli_advance_generation_creates_pointer_when_absent(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    write_manifest(_make_manifest_obj(), path)
    env = _cli_env(tmp_path)
    proc = _run_cli(
        env, "advance_generation", str(path), "newsha002", "--reason", "first promotion"
    )
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "runtime-manifest.json").exists()
    assert not list(tmp_path.glob("runtime-manifest.json.previous-*"))
    assert load_manifest(path).generation == 4  # default fixture generation is 3


def test_cli_advance_generation_requires_reason(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    write_manifest(_make_manifest_obj(), path)
    proc = _run_cli(_cli_env(tmp_path), "advance_generation", str(path), "newsha003")
    assert proc.returncode == 2  # argparse usage error


def test_cli_advance_generation_exits_2_on_missing_manifest(tmp_path: Path) -> None:
    proc = _run_cli(
        _cli_env(tmp_path),
        "advance_generation",
        str(tmp_path / "missing.json"),
        "newsha004",
        "--reason",
        "r",
    )
    assert proc.returncode == 2


def test_cli_add_deviation_round_trip_inline_and_file(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    write_manifest(_make_manifest_obj(), path)
    env = _cli_env(tmp_path)
    record = json.dumps(_make_deviation(id="cli-perm-1"))
    proc = _run_cli(env, "add_deviation", str(path), record)
    assert proc.returncode == 0, proc.stderr
    manifest = load_manifest(path)
    assert [d["id"] for d in manifest.deviations] == ["cli-perm-1"]
    assert manifest.deviations[0]["kind"] == "allow_manifestless"
    # @FILE form appends a second record
    record_file = tmp_path / "deviation.json"
    record_file.write_text(json.dumps(_make_deviation(id="cli-perm-2")), encoding="utf-8")
    proc_file = _run_cli(env, "add_deviation", str(path), f"@{record_file}")
    assert proc_file.returncode == 0, proc_file.stderr
    assert [d["id"] for d in load_manifest(path).deviations] == [
        "cli-perm-1",
        "cli-perm-2",
    ]
    # the manifest with deviations survives a re-read round trip
    assert _run_cli(env, "read", str(path)).returncode == 0
    read_out = json.loads(_run_cli(env, "read", str(path)).stdout)
    assert [d["id"] for d in read_out["deviations"]] == [
        "cli-perm-1",
        "cli-perm-2",
    ]


def test_cli_add_deviation_rejects_bad_record(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    write_manifest(_make_manifest_obj(), path)
    env = _cli_env(tmp_path)
    assert _run_cli(env, "add_deviation", str(path), "not-json").returncode == 2
    missing_field = json.dumps(dict(_make_deviation(), reason=""))
    assert _run_cli(env, "add_deviation", str(path), missing_field).returncode == 2
    now = datetime.now(timezone.utc)
    expired = json.dumps(
        _make_deviation(
            issued_at=(now - timedelta(hours=2)).isoformat(timespec="seconds"),
            expires_at=(now - timedelta(hours=1)).isoformat(timespec="seconds"),
        )
    )
    assert _run_cli(env, "add_deviation", str(path), expired).returncode == 2
    assert _run_cli(
        env, "add_deviation", str(path), f"@{tmp_path / 'missing.json'}"
    ).returncode == 2
    assert load_manifest(path).deviations == []  # nothing was appended


# ── T-0013 regression locks: per-session binding, lifecycle, attestation ────


def test_per_session_manifest_binding_has_no_global_pointer_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Per-session manifest binding (``ARNOLD_RUNTIME_MANIFEST``) is the ONLY
    resolver: the global active pointer at the default path is never
    consulted or selected, and a bound-but-missing session path fails closed
    instead of falling back to it (G1 correction 1/2)."""
    global_path = Path("/workspace/.megaplan") / MANIFEST_FILENAME
    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    # Unbound: the default path is only ever visible as the UNBOUND default —
    # the moment a session binds, that path is the session path.
    assert active_manifest_path() == global_path

    session_a = tmp_path / "sessions" / "epic-a" / "runtime-manifest.json"
    session_b = tmp_path / "sessions" / "epic-b" / "runtime-manifest.json"
    manifest_a = _make_manifest_obj(runtime_id="runtime-a", epic_id="epic-a")
    manifest_b = _make_manifest_obj(runtime_id="runtime-b", epic_id="epic-b")
    write_active_pointer(manifest_a, session_a)
    write_active_pointer(manifest_b, session_b)

    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(session_a))
    # Bound session A: the active pointer IS the session path — never the
    # global default — and resolves exactly session A's manifest.
    assert active_manifest_path() == session_a
    assert bootstrap_manifest(active_manifest_path()) == manifest_a
    assert bootstrap_manifest(active_manifest_path()).runtime_id == "runtime-a"

    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(session_b))
    # Session B binds independently: no cross-selection with session A.
    assert bootstrap_manifest(active_manifest_path()) == manifest_b
    assert bootstrap_manifest(active_manifest_path()).runtime_id == "runtime-b"

    # A bound-but-missing path fails closed (ManifestError) — there is NO
    # fallback to the global active pointer for per-session resolution.
    missing = tmp_path / "sessions" / "epic-missing" / "runtime-manifest.json"
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(missing))
    with pytest.raises(ManifestError, match="does not exist"):
        bootstrap_manifest(active_manifest_path())
    # The global default pointer was never created or written by any of the
    # per-session operations above.
    assert not global_path.exists()


def test_compatibility_only_survives_create_promote_close_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runtime-create -> promote -> close lifecycle can never re-admit
    the active pointer: the ``compatibility_only`` marker written at create
    survives promote (``advance_generation``) and close (``set_state``)
    through the real CLI pointer path, and the pointer stays
    NON-AUTHORITATIVE at every step (G2 correction 1 + second re-run)."""
    pointer = tmp_path / "runtime-manifest.json"
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(pointer))

    # create: arnold-runtime-create writes the pointer as compatibility
    # telemetry (compatibility_only=True).
    created = _make_manifest_obj(generation=1, compatibility_only=True)
    write_active_pointer(created, pointer)
    assert is_compatibility_only_pointer(pointer) is True

    # promote: advance_generation through the active pointer (CLI path) —
    # generation bumps but the marker survives and admission stays absent.
    assert (
        main(["advance_generation", str(pointer), "newsha001", "--reason", "promote"])
        == 0
    )
    promoted = load_manifest(pointer)
    assert promoted.generation == 2
    assert promoted.epic["expected_head"] == "newsha001"
    assert promoted.compatibility_only is True
    assert is_compatibility_only_pointer(pointer) is True
    assert manifest_present(pointer) is False
    with pytest.raises(ManifestError, match="compatibility_only"):
        bootstrap_manifest(pointer)

    # close: set_state closed through the active pointer (CLI path) — the
    # closed state is stamped but the pointer remains non-authoritative.
    assert main(["set_state", str(pointer), "closed"]) == 0
    closed = load_manifest(pointer)
    assert closed.state == "closed"
    assert closed.timestamps["closed"]
    assert closed.compatibility_only is True
    assert is_compatibility_only_pointer(pointer) is True
    assert manifest_present(pointer) is False
    with pytest.raises(ManifestError, match="compatibility_only"):
        bootstrap_manifest(pointer)

    # The serialized pointer on disk carries the marker after every step.
    payload = json.loads(pointer.read_text(encoding="utf-8"))
    assert payload[COMPATIBILITY_ONLY_KEY] is True
    assert payload["state"] == "closed"
    assert payload["generation"] == 2


def test_missing_runtime_attestation_never_authorizes(tmp_path: Path) -> None:
    """Content attestation of a manifest whose runtime root is missing is
    NEVER green: ``declared_vs_observed_match`` is False with errors and no
    module identity, so no dispatch path can treat the runtime as attested
    (design rule 7 content attestation; T-0013 regression lock)."""
    manifest = _make_manifest_obj(
        epic={"runtime_root": str(tmp_path / "no-such-runtime")},
    )
    result = attest_runtime(manifest)
    # Missing runtime root => NEVER a green attestation: the declared tree
    # cannot match, so declared_vs_observed_match is False with errors.
    assert result["declared_vs_observed_match"] is False
    assert result["errors"]
    # The probed module identity must NOT come from the declared (missing)
    # runtime root — no attestation payload can select that tree.
    assert result["module_file"] != str(
        (tmp_path / "no-such-runtime" / "arnold_pipelines" / "__init__.py").resolve()
    )
    assert all(
        key in result
        for key in (
            "module_file",
            "module_digest",
            "mount_id",
            "declared_vs_observed_match",
            "errors",
        )
    )
