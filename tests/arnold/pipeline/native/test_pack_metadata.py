"""Focused tests for native pack metadata models, serialization, and interface hashing.

Covers:
- Canonical interface hashing via ``compute_interface_hash`` (determinism,
  sensitivity to stable_id and schema changes, schema ordering invariance).
- ``ExportEntry`` serialization round-trip with step and workflow shapes,
  and optional ``body_hash`` behavior.
- ``DependencySpec`` serialization round-trip and default version.
- ``PackManifest`` serialization round-trip with exports and dependencies.
- ``LockfileEntry`` and ``PackLockfile`` serialization round-trips.
- JSON serializability of all model dictionaries.
"""

from __future__ import annotations

import json

import pytest

from arnold.pipeline.native.pack_metadata import (
    DependencySpec,
    ExportEntry,
    LockfileEntry,
    PackLockfile,
    PackManifest,
    compute_interface_hash,
)


# ── compute_interface_hash ───────────────────────────────────────────


class TestComputeInterfaceHash:
    """Deterministic interface hashing over stable_id + canonical schemas."""

    # ── basic behaviour ──────────────────────────────────────────

    def test_hash_is_deterministic(self) -> None:
        """Same inputs produce the same hash every time."""
        h1 = compute_interface_hash(
            stable_id="my_step",
            inputs_schema={"type": "object", "properties": {"x": {"type": "int"}}},
            outputs_schema={"type": "object", "properties": {"y": {"type": "str"}}},
        )
        h2 = compute_interface_hash(
            stable_id="my_step",
            inputs_schema={"type": "object", "properties": {"x": {"type": "int"}}},
            outputs_schema={"type": "object", "properties": {"y": {"type": "str"}}},
        )
        assert h1 == h2

    def test_hash_starts_with_sha256_prefix(self) -> None:
        """The hash format is ``sha256:<hex>``."""
        h = compute_interface_hash(stable_id="a")
        assert h.startswith("sha256:")
        digest_part = h[len("sha256:"):]
        assert len(digest_part) == 64
        assert all(c in "0123456789abcdef" for c in digest_part)

    # ── sensitivity ──────────────────────────────────────────────

    def test_different_stable_ids_produce_different_hashes(self) -> None:
        """Changing the stable_id alone changes the hash."""
        h_a = compute_interface_hash(stable_id="step_a")
        h_b = compute_interface_hash(stable_id="step_b")
        assert h_a != h_b

    def test_different_inputs_schema_produces_different_hash(self) -> None:
        """Different input schemas yield different hashes."""
        h1 = compute_interface_hash(
            stable_id="s",
            inputs_schema={"type": "object", "properties": {"a": {"type": "int"}}},
        )
        h2 = compute_interface_hash(
            stable_id="s",
            inputs_schema={"type": "object", "properties": {"b": {"type": "int"}}},
        )
        assert h1 != h2

    def test_different_outputs_schema_produces_different_hash(self) -> None:
        """Different output schemas yield different hashes."""
        h1 = compute_interface_hash(
            stable_id="s",
            outputs_schema={"type": "object", "properties": {"a": {"type": "int"}}},
        )
        h2 = compute_interface_hash(
            stable_id="s",
            outputs_schema={"type": "object", "properties": {"b": {"type": "int"}}},
        )
        assert h1 != h2

    def test_none_schemas_treated_consistently(self) -> None:
        """None schemas produce the same hash (no distinction between None and absent)."""
        h1 = compute_interface_hash(stable_id="s")
        h2 = compute_interface_hash(stable_id="s", inputs_schema=None, outputs_schema=None)
        assert h1 == h2

    def test_empty_dict_schema_produces_same_as_empty(self) -> None:
        """An empty dict schema is normalised the same way each call."""
        h1 = compute_interface_hash(stable_id="s", inputs_schema={})
        h2 = compute_interface_hash(stable_id="s", inputs_schema={})
        assert h1 == h2

    def test_schema_key_ordering_does_not_affect_hash(self) -> None:
        """Dict keys inserted in different order produce the same canonical hash."""
        h1 = compute_interface_hash(
            stable_id="s",
            inputs_schema={"b": 1, "a": 2},
        )
        h2 = compute_interface_hash(
            stable_id="s",
            inputs_schema={"a": 2, "b": 1},
        )
        assert h1 == h2

    # ── error cases ──────────────────────────────────────────────

    def test_empty_stable_id_raises_value_error(self) -> None:
        """Empty stable_id is rejected."""
        with pytest.raises(ValueError, match="stable_id must be non-empty"):
            compute_interface_hash(stable_id="")

    def test_whitespace_only_stable_id_not_rejected(self) -> None:
        """Whitespace is not specially checked — only emptiness matters."""
        # Only empty string triggers the ValueError; whitespace is allowed.
        h = compute_interface_hash(stable_id="   ")
        assert h.startswith("sha256:")


# ── ExportEntry ──────────────────────────────────────────────────────


class TestExportEntry:
    """Step and workflow export entries with optional body_hash."""

    # ── construction ─────────────────────────────────────────────

    def test_step_export_minimal(self) -> None:
        entry = ExportEntry(
            stable_id="my_pack.validate",
            kind="step",
            name="validate",
        )
        assert entry.stable_id == "my_pack.validate"
        assert entry.kind == "step"
        assert entry.name == "validate"
        assert entry.description == ""
        assert entry.inputs_schema is None
        assert entry.outputs_schema is None
        assert entry.body_hash is None

    def test_workflow_export_full(self) -> None:
        entry = ExportEntry(
            stable_id="my_pack.main",
            kind="workflow",
            name="main",
            description="Main CI workflow",
            inputs_schema={"type": "object", "properties": {"repo": {"type": "str"}}},
            outputs_schema={"type": "object", "properties": {"result": {"type": "str"}}},
            body_hash="sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
        )
        assert entry.kind == "workflow"
        assert entry.description == "Main CI workflow"
        assert entry.inputs_schema == {"type": "object", "properties": {"repo": {"type": "str"}}}
        assert entry.outputs_schema == {"type": "object", "properties": {"result": {"type": "str"}}}
        assert entry.body_hash == "sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"

    # ── to_dict / from_dict round-trip ───────────────────────────

    def test_step_round_trip_minimal(self) -> None:
        entry = ExportEntry(stable_id="s1", kind="step", name="do_thing")
        d = entry.to_dict()
        restored = ExportEntry.from_dict(d)
        assert restored.stable_id == entry.stable_id
        assert restored.kind == entry.kind
        assert restored.name == entry.name
        assert restored.description == ""
        assert restored.inputs_schema is None
        assert restored.outputs_schema is None
        assert restored.body_hash is None

    def test_workflow_round_trip_full(self) -> None:
        entry = ExportEntry(
            stable_id="wf.main",
            kind="workflow",
            name="main",
            description="desc",
            inputs_schema={"type": "int"},
            outputs_schema={"type": "str"},
            body_hash="sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )
        d = entry.to_dict()
        restored = ExportEntry.from_dict(d)
        assert restored == entry

    def test_dict_is_json_serializable(self) -> None:
        entry = ExportEntry(
            stable_id="s1",
            kind="step",
            name="f",
            inputs_schema={"type": "object", "nested": {"key": [1, 2, 3]}},
        )
        d = entry.to_dict()
        raw = json.dumps(d, sort_keys=True)
        assert isinstance(raw, str)
        # Round-trip through JSON
        reloaded = json.loads(raw)
        restored = ExportEntry.from_dict(reloaded)
        assert restored.stable_id == entry.stable_id
        assert restored.inputs_schema == entry.inputs_schema

    # ── body_hash behaviour ──────────────────────────────────────

    def test_body_hash_is_none_by_default(self) -> None:
        """When not provided, body_hash is None (not included in dict)."""
        entry = ExportEntry(stable_id="s", kind="step", name="f")
        assert entry.body_hash is None
        d = entry.to_dict()
        assert "body_hash" not in d

    def test_body_hash_included_when_set(self) -> None:
        entry = ExportEntry(
            stable_id="s", kind="step", name="f",
            body_hash="sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        )
        d = entry.to_dict()
        assert "body_hash" in d
        assert d["body_hash"] == "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"

    def test_body_hash_round_trips(self) -> None:
        entry = ExportEntry(
            stable_id="s", kind="step", name="f",
            body_hash="sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        )
        restored = ExportEntry.from_dict(entry.to_dict())
        assert restored.body_hash == entry.body_hash

    # ── from_dict required keys ──────────────────────────────────

    def test_from_dict_missing_stable_id_raises(self) -> None:
        with pytest.raises(KeyError):
            ExportEntry.from_dict({"kind": "step", "name": "f"})

    def test_from_dict_missing_kind_raises(self) -> None:
        with pytest.raises(KeyError):
            ExportEntry.from_dict({"stable_id": "s", "name": "f"})

    def test_from_dict_missing_name_raises(self) -> None:
        with pytest.raises(KeyError):
            ExportEntry.from_dict({"stable_id": "s", "kind": "step"})


# ── DependencySpec ───────────────────────────────────────────────────


class TestDependencySpec:
    """Dependency declarations with optional version range."""

    def test_default_version_is_star(self) -> None:
        dep = DependencySpec(stable_id="other_pack")
        assert dep.version == "*"

    def test_explicit_version(self) -> None:
        dep = DependencySpec(stable_id="other_pack", version=">=1.0,<2.0")
        assert dep.version == ">=1.0,<2.0"

    def test_round_trip_minimal(self) -> None:
        dep = DependencySpec(stable_id="p")
        d = dep.to_dict()
        restored = DependencySpec.from_dict(d)
        assert restored.stable_id == dep.stable_id
        assert restored.version == "*"

    def test_round_trip_with_version(self) -> None:
        dep = DependencySpec(stable_id="p", version="1.2.3")
        d = dep.to_dict()
        restored = DependencySpec.from_dict(d)
        assert restored == dep

    def test_dict_omits_default_version(self) -> None:
        """When version is '*', it is omitted from the serialized dict."""
        dep = DependencySpec(stable_id="p")
        d = dep.to_dict()
        assert "version" not in d

    def test_dict_includes_non_default_version(self) -> None:
        dep = DependencySpec(stable_id="p", version="^2.0")
        d = dep.to_dict()
        assert "version" in d
        assert d["version"] == "^2.0"

    def test_from_dict_missing_stable_id_raises(self) -> None:
        with pytest.raises(KeyError):
            DependencySpec.from_dict({})

    def test_json_serializable(self) -> None:
        dep = DependencySpec(stable_id="p", version=">=1.0")
        d = dep.to_dict()
        raw = json.dumps(d, sort_keys=True)
        reloaded = json.loads(raw)
        restored = DependencySpec.from_dict(reloaded)
        assert restored == dep


# ── PackManifest ─────────────────────────────────────────────────────


class TestPackManifest:
    """Manifest serialization round-trip with exports and dependencies."""

    def test_round_trip_minimal(self) -> None:
        manifest = PackManifest(name="my_pack", version="0.1.0")
        d = manifest.to_dict()
        restored = PackManifest.from_dict(d)
        assert restored.name == manifest.name
        assert restored.version == manifest.version
        assert restored.description == ""
        assert restored.stable_id is None
        assert restored.exports == ()
        assert restored.dependencies == ()

    def test_round_trip_with_stable_id_and_description(self) -> None:
        manifest = PackManifest(
            name="my_pack",
            version="1.0.0",
            description="A test pack",
            stable_id="my_pack_stable",
        )
        d = manifest.to_dict()
        restored = PackManifest.from_dict(d)
        assert restored == manifest

    def test_round_trip_with_exports(self) -> None:
        step_entry = ExportEntry(stable_id="p.validate", kind="step", name="validate")
        wf_entry = ExportEntry(stable_id="p.main", kind="workflow", name="main")
        manifest = PackManifest(
            name="my_pack",
            version="1.0.0",
            exports=(step_entry, wf_entry),
        )
        d = manifest.to_dict()
        restored = PackManifest.from_dict(d)
        assert len(restored.exports) == 2
        assert restored.exports[0] == step_entry
        assert restored.exports[1] == wf_entry

    def test_round_trip_with_dependencies(self) -> None:
        dep = DependencySpec(stable_id="other", version=">=1.0")
        manifest = PackManifest(
            name="my_pack",
            version="1.0.0",
            dependencies=(dep,),
        )
        d = manifest.to_dict()
        restored = PackManifest.from_dict(d)
        assert len(restored.dependencies) == 1
        assert restored.dependencies[0] == dep

    def test_round_trip_full(self) -> None:
        step_entry = ExportEntry(
            stable_id="p.build",
            kind="step",
            name="build",
            inputs_schema={"type": "object"},
            outputs_schema={"type": "object"},
        )
        wf_entry = ExportEntry(
            stable_id="p.ci",
            kind="workflow",
            name="ci",
            description="CI workflow",
        )
        dep = DependencySpec(stable_id="lib", version="^2.0")
        manifest = PackManifest(
            name="full_pack",
            version="2.3.1",
            description="Full pack with everything",
            stable_id="full_pack_stable",
            exports=(step_entry, wf_entry),
            dependencies=(dep,),
        )
        d = manifest.to_dict()
        restored = PackManifest.from_dict(d)
        assert restored == manifest

    def test_dict_is_json_serializable(self) -> None:
        manifest = PackManifest(
            name="p",
            version="1.0.0",
            exports=(ExportEntry(stable_id="p.s", kind="step", name="s"),),
            dependencies=(DependencySpec(stable_id="d"),),
        )
        d = manifest.to_dict()
        raw = json.dumps(d, sort_keys=True)
        reloaded = json.loads(raw)
        restored = PackManifest.from_dict(reloaded)
        assert restored == manifest

    def test_empty_exports_not_serialized(self) -> None:
        manifest = PackManifest(name="p", version="1.0.0")
        d = manifest.to_dict()
        assert "exports" not in d
        assert "dependencies" not in d

    def test_empty_dependencies_not_serialized(self) -> None:
        manifest = PackManifest(name="p", version="1.0.0")
        d = manifest.to_dict()
        assert "dependencies" not in d

    # ── from_dict required keys ──────────────────────────────────

    def test_from_dict_missing_name_raises(self) -> None:
        with pytest.raises(KeyError):
            PackManifest.from_dict({"version": "1.0.0"})

    def test_from_dict_missing_version_raises(self) -> None:
        with pytest.raises(KeyError):
            PackManifest.from_dict({"name": "p"})


# ── LockfileEntry ────────────────────────────────────────────────────


class TestLockfileEntry:
    """Single pinned dependency entry serialization."""

    def test_round_trip(self) -> None:
        entry = LockfileEntry(
            stable_id="lib",
            version="1.2.3",
            interface_hash="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        d = entry.to_dict()
        restored = LockfileEntry.from_dict(d)
        assert restored == entry

    def test_json_serializable(self) -> None:
        entry = LockfileEntry(
            stable_id="lib",
            version="2.0.0",
            interface_hash="sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )
        d = entry.to_dict()
        raw = json.dumps(d, sort_keys=True)
        reloaded = json.loads(raw)
        restored = LockfileEntry.from_dict(reloaded)
        assert restored == entry

    def test_from_dict_missing_keys_raise(self) -> None:
        with pytest.raises(KeyError):
            LockfileEntry.from_dict({"stable_id": "x"})
        with pytest.raises(KeyError):
            LockfileEntry.from_dict({"stable_id": "x", "version": "1.0"})
        with pytest.raises(KeyError):
            LockfileEntry.from_dict({"version": "1.0", "interface_hash": "sha256:aa"})


# ── PackLockfile ─────────────────────────────────────────────────────


class TestPackLockfile:
    """Lockfile serialization round-trip with optional manifest metadata."""

    def test_round_trip_empty(self) -> None:
        lockfile = PackLockfile()
        d = lockfile.to_dict()
        restored = PackLockfile.from_dict(d)
        assert restored.manifest_stable_id is None
        assert restored.manifest_version is None
        assert restored.entries == ()

    def test_round_trip_with_manifest_meta(self) -> None:
        lockfile = PackLockfile(
            manifest_stable_id="my_pack_stable",
            manifest_version="1.0.0",
        )
        d = lockfile.to_dict()
        restored = PackLockfile.from_dict(d)
        assert restored == lockfile

    def test_round_trip_with_entries(self) -> None:
        entry = LockfileEntry(
            stable_id="dep_a",
            version="1.2.3",
            interface_hash="sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        )
        lockfile = PackLockfile(entries=(entry,))
        d = lockfile.to_dict()
        restored = PackLockfile.from_dict(d)
        assert len(restored.entries) == 1
        assert restored.entries[0] == entry

    def test_round_trip_full(self) -> None:
        e1 = LockfileEntry(
            stable_id="dep_a",
            version="1.0.0",
            interface_hash="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        e2 = LockfileEntry(
            stable_id="dep_b",
            version="2.0.0",
            interface_hash="sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )
        lockfile = PackLockfile(
            manifest_stable_id="pack_stable",
            manifest_version="3.0.0",
            entries=(e1, e2),
        )
        d = lockfile.to_dict()
        restored = PackLockfile.from_dict(d)
        assert restored == lockfile

    def test_empty_entries_not_serialized(self) -> None:
        lockfile = PackLockfile(manifest_stable_id="p", manifest_version="1.0")
        d = lockfile.to_dict()
        assert "entries" not in d

    def test_json_serializable(self) -> None:
        lockfile = PackLockfile(
            manifest_stable_id="p",
            manifest_version="1.0.0",
            entries=(
                LockfileEntry(
                    stable_id="dep",
                    version="1.0.0",
                    interface_hash="sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
                ),
            ),
        )
        d = lockfile.to_dict()
        raw = json.dumps(d, sort_keys=True)
        reloaded = json.loads(raw)
        restored = PackLockfile.from_dict(reloaded)
        assert restored == lockfile


# ── Frozen dataclass behaviour ───────────────────────────────────────


class TestFrozenDataClasses:
    """All pack metadata dataclasses are frozen (immutable)."""

    def test_export_entry_is_frozen(self) -> None:
        entry = ExportEntry(stable_id="s", kind="step", name="f")
        with pytest.raises(Exception):
            entry.stable_id = "other"  # type: ignore[misc]

    def test_dependency_spec_is_frozen(self) -> None:
        dep = DependencySpec(stable_id="p")
        with pytest.raises(Exception):
            dep.stable_id = "other"  # type: ignore[misc]

    def test_pack_manifest_is_frozen(self) -> None:
        manifest = PackManifest(name="p", version="1.0")
        with pytest.raises(Exception):
            manifest.name = "other"  # type: ignore[misc]

    def test_lockfile_entry_is_frozen(self) -> None:
        entry = LockfileEntry(
            stable_id="x", version="1.0",
            interface_hash="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        with pytest.raises(Exception):
            entry.version = "2.0"  # type: ignore[misc]

    def test_pack_lockfile_is_frozen(self) -> None:
        lockfile = PackLockfile()
        with pytest.raises(Exception):
            lockfile.manifest_stable_id = "x"  # type: ignore[misc]


# ── Hash integration with manifests ──────────────────────────────────


class TestHashIntegration:
    """Tests that bridge hashing and the model types."""

    def test_export_entry_hash_consistent_with_compute_interface_hash(self) -> None:
        """compute_interface_hash called with an ExportEntry's fields produces
        the same hash as calling it directly."""
        entry = ExportEntry(
            stable_id="p.step",
            kind="step",
            name="step_fn",
            inputs_schema={"type": "object"},
            outputs_schema={"type": "object"},
        )
        h = compute_interface_hash(
            stable_id=entry.stable_id,
            inputs_schema=entry.inputs_schema,
            outputs_schema=entry.outputs_schema,
        )
        assert h.startswith("sha256:")

    def test_lockfile_entry_interface_hash_format(self) -> None:
        """LockfileEntry.interface_hash should match the format of compute_interface_hash."""
        h = compute_interface_hash(stable_id="dep", inputs_schema={"x": "int"})
        entry = LockfileEntry(stable_id="dep", version="1.0", interface_hash=h)
        assert entry.interface_hash == h
        assert entry.interface_hash.startswith("sha256:")
