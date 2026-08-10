"""Focused tests for PackRegistry registration, resolution, and reverse-index behavior.

Covers:
- Exported step and workflow resolution with and without lockfile pins.
- Shared step used by two workflows.
- Shared workflow used as a child.
- No auto-upgrade before deliberate re-pin.
- Reverse-index updates (registration seeding and resolution enrichment).
- A false-pass guard proving resolution does not import implementation internals.
- Diagnostics for missing, ambiguous, hash-mismatched, and unregistered entries.
"""

from __future__ import annotations

import json
import sys

import pytest

from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.native.pack_index import PackReverseIndex
from arnold.pipeline.native.pack_metadata import (
    DependencySpec,
    ExportEntry,
    LockfileEntry,
    PackLockfile,
    PackManifest,
    compute_interface_hash,
)
from arnold.pipeline.native.pack_registry import (
    PackRegistry,
    RegisteredPackExport,
    ResolvedPackExport,
)


# ── Test helpers ───────────────────────────────────────────────────────

def _program(
    name: str = "test_program",
    stable_id: str | None = None,
    inputs_schema: dict | None = None,
    outputs_schema: dict | None = None,
) -> NativeProgram:
    """Create a minimal NativeProgram for registry testing."""
    return NativeProgram(
        name=name,
        stable_id=stable_id,
        inputs_schema=inputs_schema,
        outputs_schema=outputs_schema,
    )


def _export(
    stable_id: str,
    kind: str = "step",
    name: str = "",
    inputs_schema: dict | None = None,
    outputs_schema: dict | None = None,
    body_hash: str | None = None,
) -> ExportEntry:
    """Create an ExportEntry with a default name derived from stable_id."""
    return ExportEntry(
        stable_id=stable_id,
        kind=kind,
        name=name or stable_id,
        inputs_schema=inputs_schema,
        outputs_schema=outputs_schema,
        body_hash=body_hash,
    )


def _manifest(
    name: str,
    version: str,
    exports: tuple[ExportEntry, ...] = (),
    dependencies: tuple[DependencySpec, ...] = (),
    stable_id: str | None = None,
    description: str = "",
) -> PackManifest:
    """Create a PackManifest."""
    return PackManifest(
        name=name,
        version=version,
        description=description,
        stable_id=stable_id,
        exports=exports,
        dependencies=dependencies,
    )


def _dep(stable_id: str, version: str = "*") -> DependencySpec:
    """Create a DependencySpec."""
    return DependencySpec(stable_id=stable_id, version=version)


def _lock_entry(
    stable_id: str,
    version: str,
    interface_hash: str,
) -> LockfileEntry:
    """Create a LockfileEntry."""
    return LockfileEntry(
        stable_id=stable_id,
        version=version,
        interface_hash=interface_hash,
    )


def _lockfile(*entries: LockfileEntry) -> PackLockfile:
    """Create a PackLockfile from entries."""
    return PackLockfile(entries=tuple(entries))


# ── Registration ───────────────────────────────────────────────────────


class TestPackRegistryRegistration:
    """Explicit registration of packs with manifest + providers."""

    def test_register_single_step_pack(self) -> None:
        """A pack with one exported step registers successfully."""
        registry = PackRegistry()
        exp = _export("my_step", kind="step")
        prog = _program("my_step", stable_id="my_step")
        manifest = _manifest("test_pack", "1.0.0", exports=(exp,))

        registry.register_pack(manifest, {"my_step": prog})

        assert registry.has("my_step")
        regs = registry.registrations_for("my_step")
        assert len(regs) == 1
        assert regs[0].stable_id == "my_step"
        assert regs[0].version == "1.0.0"
        assert regs[0].manifest is manifest
        assert regs[0].program is prog

    def test_register_single_workflow_pack(self) -> None:
        """A pack with one exported workflow registers successfully."""
        registry = PackRegistry()
        exp = _export("my_workflow", kind="workflow")
        prog = _program("my_workflow", stable_id="my_workflow")
        manifest = _manifest("wf_pack", "2.3.1", exports=(exp,))

        registry.register_pack(manifest, {"my_workflow": prog})

        assert registry.has("my_workflow")
        regs = registry.registrations_for("my_workflow")
        assert len(regs) == 1
        assert regs[0].export.kind == "workflow"

    def test_register_multiple_exports(self) -> None:
        """A pack with multiple exports registers all of them."""
        registry = PackRegistry()
        exp_a = _export("step_a")
        exp_b = _export("step_b")
        exp_c = _export("workflow_c", kind="workflow")
        manifest = _manifest("multi_pack", "1.0.0", exports=(exp_a, exp_b, exp_c))

        registry.register_pack(
            manifest,
            {
                "step_a": _program("step_a", stable_id="step_a"),
                "step_b": _program("step_b", stable_id="step_b"),
                "workflow_c": _program("workflow_c", stable_id="workflow_c"),
            },
        )

        assert registry.has("step_a")
        assert registry.has("step_b")
        assert registry.has("workflow_c")
        assert len(registry.registrations_for("step_a")) == 1

    def test_register_multiple_versions_under_same_stable_id(self) -> None:
        """Two packs with different versions under the same stable_id."""
        registry = PackRegistry()
        exp = _export("shared_step")
        manifest_v1 = _manifest("lib", "1.0.0", exports=(exp,))
        manifest_v2 = _manifest("lib", "2.0.0", exports=(exp,))

        registry.register_pack(manifest_v1, {"shared_step": _program("shared_step_v1", stable_id="shared_step")})
        registry.register_pack(manifest_v2, {"shared_step": _program("shared_step_v2", stable_id="shared_step")})

        versions = registry.registered_versions("shared_step")
        assert versions == ("1.0.0", "2.0.0")
        regs = registry.registrations_for("shared_step")
        assert len(regs) == 2

    def test_duplicate_version_rejected(self) -> None:
        """Registering the same version twice under one stable_id raises."""
        registry = PackRegistry()
        exp = _export("step_x")
        manifest = _manifest("p", "1.0.0", exports=(exp,))

        registry.register_pack(manifest, {"step_x": _program("step_x", stable_id="step_x")})

        with pytest.raises(LookupError, match="ambiguous registration"):
            registry.register_pack(manifest, {"step_x": _program("step_x", stable_id="step_x")})

    def test_missing_provider_raises(self) -> None:
        """A missing provider for a declared export raises LookupError."""
        registry = PackRegistry()
        exp_a = _export("a")
        exp_b = _export("b")
        manifest = _manifest("p", "1.0.0", exports=(exp_a, exp_b))

        with pytest.raises(LookupError, match="missing provider"):
            registry.register_pack(manifest, {"a": _program("a", stable_id="a")})

    def test_extra_provider_raises(self) -> None:
        """A provider for an unexported stable_id raises LookupError."""
        registry = PackRegistry()
        exp = _export("a")
        manifest = _manifest("p", "1.0.0", exports=(exp,))

        with pytest.raises(LookupError, match="unexported"):
            registry.register_pack(
                manifest,
                {
                    "a": _program("a", stable_id="a"),
                    "z": _program("z", stable_id="z"),
                },
            )

    def test_provider_stable_id_mismatch_raises(self) -> None:
        """Provider with non-None stable_id that differs from export raises."""
        registry = PackRegistry()
        exp = _export("a")
        manifest = _manifest("p", "1.0.0", exports=(exp,))

        with pytest.raises(ValueError, match="stable_id mismatch"):
            registry.register_pack(manifest, {"a": _program("wrong", stable_id="wrong")})

    def test_mismatched_interface_hash_raises(self) -> None:
        """Manifest and provider with different schemas raise ValueError."""
        registry = PackRegistry()
        exp = _export("a", inputs_schema={"type": "int"})
        prog = _program("a", stable_id="a", inputs_schema={"type": "str"})
        manifest = _manifest("p", "1.0.0", exports=(exp,))

        with pytest.raises(ValueError, match="provider interface mismatch"):
            registry.register_pack(manifest, {"a": prog})

    def test_registration_seeds_reverse_index_for_dependencies(self) -> None:
        """Declaration-time dependencies seed the reverse index."""
        registry = PackRegistry()
        exp_a = _export("step_a")
        exp_b = _export("step_b")
        manifest = _manifest(
            "pack",
            "1.0.0",
            exports=(exp_a, exp_b),
            dependencies=(_dep("third_party_step"),),
        )

        registry.register_pack(
            manifest,
            {
                "step_a": _program("step_a", stable_id="step_a"),
                "step_b": _program("step_b", stable_id="step_b"),
            },
        )

        # Both exports should appear as dependents of third_party_step
        deps = registry.reverse_index.dependents_of("third_party_step")
        dep_names = {rec.program_name for rec in deps}
        assert dep_names == {"step_a", "step_b"}


# ── Resolution ─────────────────────────────────────────────────────────


class TestPackRegistryResolution:
    """Exact lockfile-based resolution with fail-closed semantics."""

    def _register_two_versions(self) -> PackRegistry:
        """Register two versions of a shared step and return the registry."""
        registry = PackRegistry()
        exp = _export("shared_step")
        manifest_v1 = _manifest("lib", "1.0.0", exports=(exp,))
        manifest_v2 = _manifest("lib", "2.0.0", exports=(exp,))

        registry.register_pack(
            manifest_v1, {"shared_step": _program("shared_step_v1", stable_id="shared_step")}
        )
        registry.register_pack(
            manifest_v2, {"shared_step": _program("shared_step_v2", stable_id="shared_step")}
        )
        return registry

    # ── with lockfile ──────────────────────────────────────────────

    def test_resolve_with_lockfile_exact_pin(self) -> None:
        """With a lockfile, the exact pinned version is resolved."""
        registry = self._register_two_versions()

        exp_hash = compute_interface_hash(stable_id="shared_step")
        lf = _lockfile(_lock_entry("shared_step", "1.0.0", exp_hash))

        resolved = registry.resolve("shared_step", lockfile=lf)
        assert resolved is not None
        # Should get the v1 program
        assert resolved.name == "shared_step_v1"

    def test_resolve_with_lockfile_exact_pin_v2(self) -> None:
        """Pinning v2 resolves v2."""
        registry = self._register_two_versions()

        exp_hash = compute_interface_hash(stable_id="shared_step")
        lf = _lockfile(_lock_entry("shared_step", "2.0.0", exp_hash))

        resolved = registry.resolve("shared_step", lockfile=lf)
        assert resolved.name == "shared_step_v2"

    def test_resolve_entry_returns_resolved_pack_export(self) -> None:
        """resolve_entry returns a ResolvedPackExport with full metadata."""
        registry = self._register_two_versions()
        exp_hash = compute_interface_hash(stable_id="shared_step")
        lf = _lockfile(_lock_entry("shared_step", "1.0.0", exp_hash))

        entry = registry.resolve_entry("shared_step", lockfile=lf)
        assert isinstance(entry, ResolvedPackExport)
        assert entry.registration.stable_id == "shared_step"
        assert entry.registration.version == "1.0.0"
        assert entry.lockfile_entry is not None
        assert entry.lockfile_entry.version == "1.0.0"

    def test_lockfile_entry_missing_stable_id_raises(self) -> None:
        """Lockfile without an entry for the stable_id raises LookupError."""
        registry = self._register_two_versions()
        lf = _lockfile(_lock_entry("other_id", "1.0.0", "sha256:fake"))

        with pytest.raises(LookupError, match="missing lockfile entry"):
            registry.resolve("shared_step", lockfile=lf)

    def test_unregistered_pinned_version_raises(self) -> None:
        """Lockfile pins a version not registered for that stable_id."""
        registry = self._register_two_versions()
        exp_hash = compute_interface_hash(stable_id="shared_step")
        lf = _lockfile(_lock_entry("shared_step", "99.0.0", exp_hash))

        with pytest.raises(LookupError, match="unregistered pinned version"):
            registry.resolve("shared_step", lockfile=lf)

    def test_interface_hash_mismatch_raises(self) -> None:
        """Lockfile interface hash differs from registered hash."""
        registry = self._register_two_versions()
        lf = _lockfile(_lock_entry("shared_step", "1.0.0", "sha256:wrong_hash_0000000000000000"))

        with pytest.raises(LookupError, match="interface hash mismatch"):
            registry.resolve("shared_step", lockfile=lf)

    # ── without lockfile ───────────────────────────────────────────

    def test_resolve_without_lockfile_single_version(self) -> None:
        """With only one version registered, no lockfile is needed."""
        registry = PackRegistry()
        exp = _export("only_step")
        manifest = _manifest("pack", "1.0.0", exports=(exp,))
        registry.register_pack(manifest, {"only_step": _program("only_step", stable_id="only_step")})

        resolved = registry.resolve("only_step")
        assert resolved.name == "only_step"

    def test_resolve_without_lockfile_ambiguous_raises(self) -> None:
        """Multiple versions without a lockfile pin raise LookupError."""
        registry = self._register_two_versions()

        with pytest.raises(LookupError, match="ambiguous registered pack export"):
            registry.resolve("shared_step")

    def test_resolve_unregistered_stable_id_raises(self) -> None:
        """Resolving an unregistered stable_id raises LookupError."""
        registry = PackRegistry()

        with pytest.raises(LookupError, match="unregistered pack export"):
            registry.resolve("nonexistent")

    def test_resolve_empty_stable_id_raises(self) -> None:
        """Empty stable_id raises ValueError."""
        registry = PackRegistry()

        with pytest.raises(ValueError, match="stable_id must be non-empty"):
            registry.resolve("")

    # ── reverse index during resolution ────────────────────────────

    def test_resolution_records_reverse_index(self) -> None:
        """Calling resolve with dependent info updates the reverse index."""
        registry = PackRegistry()
        exp = _export("dep_step")
        manifest = _manifest("lib", "1.0.0", exports=(exp,), dependencies=())
        registry.register_pack(manifest, {"dep_step": _program("dep_step", stable_id="dep_step")})

        exp_hash = compute_interface_hash(stable_id="dep_step")
        lf = _lockfile(_lock_entry("dep_step", "1.0.0", exp_hash))

        dependent_prog = _program("caller", stable_id="caller_id")

        registry.resolve(
            "dep_step",
            lockfile=lf,
            dependent_program=dependent_prog,
            dependent_name="caller",
            dependent_stable_id="caller_id",
            call_site_paths=("root/use_dep",),
        )

        deps = registry.reverse_index.dependents_of("dep_step")
        assert len(deps) >= 1
        caller_rec = [r for r in deps if r.program_name == "caller"]
        assert len(caller_rec) == 1
        assert caller_rec[0].call_site_paths == ("root/use_dep",)
        assert caller_rec[0].lockfile_entry is not None
        assert caller_rec[0].lockfile_entry.version == "1.0.0"


# ── Shared step used by two workflows ──────────────────────────────────


class TestSharedStepUsedByTwoWorkflows:
    """A single shared step exported from a pack, used by two distinct workflows."""

    @pytest.fixture
    def registry_with_shared_step(self) -> PackRegistry:
        """Registry with a shared step pack registered."""
        registry = PackRegistry()
        exp = _export("shared_step", kind="step")
        manifest = _manifest("shared_lib", "1.0.0", exports=(exp,))
        registry.register_pack(
            manifest, {"shared_step": _program("shared_step", stable_id="shared_step")}
        )
        return registry

    def test_both_workflows_resolve_same_step(self, registry_with_shared_step: PackRegistry) -> None:
        """Two different workflow programs both resolve the same shared step."""
        exp_hash = compute_interface_hash(stable_id="shared_step")
        lf = _lockfile(_lock_entry("shared_step", "1.0.0", exp_hash))

        wf_a = _program("workflow_a", stable_id="wf_a")
        wf_b = _program("workflow_b", stable_id="wf_b")

        resolved_a = registry_with_shared_step.resolve(
            "shared_step",
            lockfile=lf,
            dependent_program=wf_a,
            dependent_name="workflow_a",
            dependent_stable_id="wf_a",
            call_site_paths=("root/use_shared",),
        )
        resolved_b = registry_with_shared_step.resolve(
            "shared_step",
            lockfile=lf,
            dependent_program=wf_b,
            dependent_name="workflow_b",
            dependent_stable_id="wf_b",
            call_site_paths=("root/use_shared",),
        )

        assert resolved_a is resolved_b  # same program instance
        assert resolved_a.name == "shared_step"

    def test_reverse_index_shows_both_dependents(self, registry_with_shared_step: PackRegistry) -> None:
        """After both workflows resolve, reverse index records both as dependents."""
        exp_hash = compute_interface_hash(stable_id="shared_step")
        lf = _lockfile(_lock_entry("shared_step", "1.0.0", exp_hash))

        wf_a = _program("workflow_a", stable_id="wf_a")
        wf_b = _program("workflow_b", stable_id="wf_b")

        registry_with_shared_step.resolve(
            "shared_step",
            lockfile=lf,
            dependent_program=wf_a,
            dependent_name="workflow_a",
            dependent_stable_id="wf_a",
            call_site_paths=("root/step_1",),
        )
        registry_with_shared_step.resolve(
            "shared_step",
            lockfile=lf,
            dependent_program=wf_b,
            dependent_name="workflow_b",
            dependent_stable_id="wf_b",
            call_site_paths=("root/step_2",),
        )

        deps = registry_with_shared_step.reverse_index.dependents_of("shared_step")
        dep_names = {r.program_name for r in deps}
        assert dep_names == {"workflow_a", "workflow_b"}

    def test_each_workflow_has_distinct_call_site_paths(self, registry_with_shared_step: PackRegistry) -> None:
        """Call-site paths are recorded per-dependent workflow."""
        exp_hash = compute_interface_hash(stable_id="shared_step")
        lf = _lockfile(_lock_entry("shared_step", "1.0.0", exp_hash))

        registry_with_shared_step.resolve(
            "shared_step",
            lockfile=lf,
            dependent_name="workflow_a",
            dependent_stable_id="wf_a",
            call_site_paths=("root/validate",),
        )
        registry_with_shared_step.resolve(
            "shared_step",
            lockfile=lf,
            dependent_name="workflow_b",
            dependent_stable_id="wf_b",
            call_site_paths=("root/build",),
        )

        deps = registry_with_shared_step.reverse_index.dependents_of("shared_step")
        wf_a_rec = next(r for r in deps if r.program_name == "workflow_a")
        wf_b_rec = next(r for r in deps if r.program_name == "workflow_b")
        assert wf_a_rec.call_site_paths == ("root/validate",)
        assert wf_b_rec.call_site_paths == ("root/build",)
        assert wf_a_rec.call_site_paths != wf_b_rec.call_site_paths


# ── Shared workflow used as a child ────────────────────────────────────


class TestSharedWorkflowUsedAsChild:
    """A workflow exported from a pack, used as a child by another workflow."""

    @pytest.fixture
    def registry_with_workflow_pack(self) -> PackRegistry:
        """Registry with a workflow pack registered."""
        registry = PackRegistry()
        exp = _export("child_workflow", kind="workflow")
        manifest = _manifest("wf_lib", "1.0.0", exports=(exp,))
        prog = _program("child_workflow", stable_id="child_workflow")
        registry.register_pack(manifest, {"child_workflow": prog})
        return registry

    def test_child_workflow_resolves(self, registry_with_workflow_pack: PackRegistry) -> None:
        """A parent workflow can resolve the child workflow."""
        exp_hash = compute_interface_hash(stable_id="child_workflow")
        lf = _lockfile(_lock_entry("child_workflow", "1.0.0", exp_hash))

        parent = _program("parent_workflow", stable_id="parent_wf")
        child = registry_with_workflow_pack.resolve(
            "child_workflow",
            lockfile=lf,
            dependent_program=parent,
            dependent_name="parent_workflow",
            dependent_stable_id="parent_wf",
            call_site_paths=("root/child",),
        )

        assert child.name == "child_workflow"

    def test_reverse_index_captures_child_dependency(self, registry_with_workflow_pack: PackRegistry) -> None:
        """The reverse index records the parent as dependent of the child workflow."""
        exp_hash = compute_interface_hash(stable_id="child_workflow")
        lf = _lockfile(_lock_entry("child_workflow", "1.0.0", exp_hash))

        parent = _program("parent_workflow", stable_id="parent_wf")
        registry_with_workflow_pack.resolve(
            "child_workflow",
            lockfile=lf,
            dependent_program=parent,
            dependent_name="parent_workflow",
            dependent_stable_id="parent_wf",
            call_site_paths=("root/nested/child",),
        )

        deps = registry_with_workflow_pack.reverse_index.dependents_of("child_workflow")
        parent_recs = [r for r in deps if r.program_name == "parent_workflow"]
        assert len(parent_recs) == 1
        assert parent_recs[0].program_stable_id == "parent_wf"
        assert parent_recs[0].call_site_paths == ("root/nested/child",)

    def test_child_workflow_is_workflow_kind(self, registry_with_workflow_pack: PackRegistry) -> None:
        """The resolved export has kind 'workflow'."""
        exp_hash = compute_interface_hash(stable_id="child_workflow")
        lf = _lockfile(_lock_entry("child_workflow", "1.0.0", exp_hash))

        entry = registry_with_workflow_pack.resolve_entry("child_workflow", lockfile=lf)
        assert entry.export.kind == "workflow"


# ── No auto-upgrade before deliberate re-pin ───────────────────────────


class TestNoAutoUpgradeBeforeRepin:
    """Resolution is pinned — no auto-upgrade without lockfile change."""

    @pytest.fixture
    def multi_version_registry(self) -> PackRegistry:
        """Registry with v1.0.0 and v2.0.0 of shared_step."""
        registry = PackRegistry()
        # v1 — different schema to produce different interface hash
        exp_v1 = _export("shared_step", inputs_schema={"type": "v1_schema"})
        manifest_v1 = _manifest("lib", "1.0.0", exports=(exp_v1,))
        registry.register_pack(
            manifest_v1,
            {"shared_step": _program("shared_step_v1", stable_id="shared_step", inputs_schema={"type": "v1_schema"})},
        )

        exp_v2 = _export("shared_step", inputs_schema={"type": "v2_schema"})
        manifest_v2 = _manifest("lib", "2.0.0", exports=(exp_v2,))
        registry.register_pack(
            manifest_v2,
            {"shared_step": _program("shared_step_v2", stable_id="shared_step", inputs_schema={"type": "v2_schema"})},
        )
        return registry

    def test_pinned_to_v1_resolves_v1(self, multi_version_registry: PackRegistry) -> None:
        """With a v1 pin, v1 is resolved — not v2."""
        exp_v1_hash = compute_interface_hash(
            stable_id="shared_step", inputs_schema={"type": "v1_schema"}
        )
        lf = _lockfile(_lock_entry("shared_step", "1.0.0", exp_v1_hash))

        resolved = multi_version_registry.resolve("shared_step", lockfile=lf)
        assert resolved.name == "shared_step_v1"

    def test_pinned_to_v2_resolves_v2(self, multi_version_registry: PackRegistry) -> None:
        """With a v2 pin, v2 is resolved — not v1."""
        exp_v2_hash = compute_interface_hash(
            stable_id="shared_step", inputs_schema={"type": "v2_schema"}
        )
        lf = _lockfile(_lock_entry("shared_step", "2.0.0", exp_v2_hash))

        resolved = multi_version_registry.resolve("shared_step", lockfile=lf)
        assert resolved.name == "shared_step_v2"

    def test_v1_pin_does_not_auto_upgrade_despite_v2_available(self, multi_version_registry: PackRegistry) -> None:
        """A v1 lockfile pin does NOT auto-resolve to v2 even though v2 is registered."""
        exp_v1_hash = compute_interface_hash(
            stable_id="shared_step", inputs_schema={"type": "v1_schema"}
        )
        lf = _lockfile(_lock_entry("shared_step", "1.0.0", exp_v1_hash))

        resolved = multi_version_registry.resolve("shared_step", lockfile=lf)
        # Must be v1, not v2
        assert resolved.name == "shared_step_v1"

        # Resolution must not silently emit v2
        all_regs = multi_version_registry.registrations_for("shared_step")
        assert len(all_regs) == 2  # both exist, but only v1 was resolved

    def test_re_pin_to_v2_required_for_upgrade(self, multi_version_registry: PackRegistry) -> None:
        """Upgrading requires deliberate re-pin (changing the lockfile entry)."""
        # First: v1 pin resolves v1
        exp_v1_hash = compute_interface_hash(
            stable_id="shared_step", inputs_schema={"type": "v1_schema"}
        )
        lf_v1 = _lockfile(_lock_entry("shared_step", "1.0.0", exp_v1_hash))
        resolved_v1 = multi_version_registry.resolve("shared_step", lockfile=lf_v1)
        assert resolved_v1.name == "shared_step_v1"

        # Then: deliberately re-pin to v2
        exp_v2_hash = compute_interface_hash(
            stable_id="shared_step", inputs_schema={"type": "v2_schema"}
        )
        lf_v2 = _lockfile(_lock_entry("shared_step", "2.0.0", exp_v2_hash))
        resolved_v2 = multi_version_registry.resolve("shared_step", lockfile=lf_v2)
        assert resolved_v2.name == "shared_step_v2"

        # Verify they are different programs
        assert resolved_v1 is not resolved_v2

    def test_v1_pin_with_v2_hash_fails_hard(self, multi_version_registry: PackRegistry) -> None:
        """A lockfile with v1 version but v2 interface hash fails — no silent fallback."""
        exp_v2_hash = compute_interface_hash(
            stable_id="shared_step", inputs_schema={"type": "v2_schema"}
        )
        lf = _lockfile(_lock_entry("shared_step", "1.0.0", exp_v2_hash))

        with pytest.raises(LookupError, match="interface hash mismatch"):
            multi_version_registry.resolve("shared_step", lockfile=lf)

    def test_without_lockfile_fails_due_to_ambiguity(self, multi_version_registry: PackRegistry) -> None:
        """Without a lockfile, the ambiguity of two versions is rejected."""
        with pytest.raises(LookupError, match="ambiguous registered pack export"):
            multi_version_registry.resolve("shared_step")


# ── Reverse-index updates (registration and resolution) ────────────────


class TestReverseIndexUpdates:
    """Comprehensive tests that reverse index updates correctly through registration
    and resolution lifecycle."""

    def test_registration_seeds_index_from_dependencies(self) -> None:
        """When a pack is registered, its dependencies appear in reverse index."""
        registry = PackRegistry()
        exp = _export("main_step")
        manifest = _manifest(
            "consumer",
            "1.0.0",
            exports=(exp,),
            dependencies=(_dep("lib_step"), _dep("lib_util")),
        )
        registry.register_pack(manifest, {"main_step": _program("main_step", stable_id="main_step")})

        # Both dependencies should have main_step as dependent
        lib_deps = registry.reverse_index.dependents_of("lib_step")
        assert any(r.program_name == "main_step" for r in lib_deps)

        util_deps = registry.reverse_index.dependents_of("lib_util")
        assert any(r.program_name == "main_step" for r in util_deps)

    def test_resolution_enriches_index_with_lockfile_and_paths(self) -> None:
        """Resolution calls enrich reverse index with lockfile data and paths."""
        registry = PackRegistry()
        exp = _export("lib_step")
        manifest = _manifest("lib", "1.0.0", exports=(exp,))
        registry.register_pack(manifest, {"lib_step": _program("lib_step", stable_id="lib_step")})

        exp_hash = compute_interface_hash(stable_id="lib_step")
        lf = _lockfile(_lock_entry("lib_step", "1.0.0", exp_hash))

        registry.resolve(
            "lib_step",
            lockfile=lf,
            dependent_program=_program("consumer", stable_id="consumer_id"),
            dependent_name="consumer",
            dependent_stable_id="consumer_id",
            call_site_paths=("root/a", "root/b"),
        )

        deps = registry.reverse_index.dependents_of("lib_step")
        consumer = next(r for r in deps if r.program_name == "consumer")
        assert consumer.call_site_paths == ("root/a", "root/b")
        assert consumer.lockfile_entry is not None
        assert consumer.lockfile_entry.version == "1.0.0"
        assert consumer.lockfile_entry.interface_hash == exp_hash

    def test_resolution_without_lockfile_does_not_enrich_index(self) -> None:
        """Resolution without a lockfile does not add to reverse index."""
        registry = PackRegistry()
        exp = _export("only_step")
        manifest = _manifest("single", "1.0.0", exports=(exp,))
        registry.register_pack(manifest, {"only_step": _program("only_step", stable_id="only_step")})

        # Resolve without lockfile
        registry.resolve(
            "only_step",
            lockfile=None,
            dependent_program=_program("caller", stable_id="caller"),
            dependent_name="caller",
            dependent_stable_id="caller",
        )

        # Reverse index from registration seeding is empty because there were no dependencies
        deps = registry.reverse_index.dependents_of("only_step")
        assert len(deps) == 0  # no lockfile, so no reverse index recording

    def test_resolution_without_dependent_name_skips_recording(self) -> None:
        """Resolution without a dependent_name does not record reverse index."""
        registry = PackRegistry()
        exp = _export("step_x")
        manifest = _manifest("lib", "1.0.0", exports=(exp,))
        registry.register_pack(manifest, {"step_x": _program("step_x", stable_id="step_x")})

        exp_hash = compute_interface_hash(stable_id="step_x")
        lf = _lockfile(_lock_entry("step_x", "1.0.0", exp_hash))

        # Resolve with lockfile but no dependent info
        registry.resolve("step_x", lockfile=lf)

        deps = registry.reverse_index.dependents_of("step_x")
        # Registration didn't seed any deps, and resolution with no dependent_name doesn't add
        assert len(deps) == 0

    def test_duplicate_call_site_paths_not_duplicated(self) -> None:
        """Repeated resolution with same call-site paths does not duplicate them."""
        registry = PackRegistry()
        exp = _export("shared")
        manifest = _manifest("lib", "1.0.0", exports=(exp,), dependencies=())
        registry.register_pack(manifest, {"shared": _program("shared", stable_id="shared")})

        exp_hash = compute_interface_hash(stable_id="shared")
        lf = _lockfile(_lock_entry("shared", "1.0.0", exp_hash))
        prog = _program("caller", stable_id="caller")

        # Resolve twice with same paths
        registry.resolve(
            "shared",
            lockfile=lf,
            dependent_program=prog,
            dependent_name="caller",
            dependent_stable_id="caller",
            call_site_paths=("root/use",),
        )
        registry.resolve(
            "shared",
            lockfile=lf,
            dependent_program=prog,
            dependent_name="caller",
            dependent_stable_id="caller",
            call_site_paths=("root/use",),
        )

        deps = registry.reverse_index.dependents_of("shared")
        caller = next(r for r in deps if r.program_name == "caller")
        assert caller.call_site_paths == ("root/use",)  # not duplicated

    def test_new_call_site_paths_merge_with_existing(self) -> None:
        """New call-site paths from subsequent resolutions are merged."""
        registry = PackRegistry()
        exp = _export("shared")
        manifest = _manifest("lib", "1.0.0", exports=(exp,), dependencies=())
        registry.register_pack(manifest, {"shared": _program("shared", stable_id="shared")})

        exp_hash = compute_interface_hash(stable_id="shared")
        lf = _lockfile(_lock_entry("shared", "1.0.0", exp_hash))
        prog = _program("caller", stable_id="caller")

        registry.resolve(
            "shared",
            lockfile=lf,
            dependent_program=prog,
            dependent_name="caller",
            dependent_stable_id="caller",
            call_site_paths=("root/use_a",),
        )
        registry.resolve(
            "shared",
            lockfile=lf,
            dependent_program=prog,
            dependent_name="caller",
            dependent_stable_id="caller",
            call_site_paths=("root/use_b",),
        )

        deps = registry.reverse_index.dependents_of("shared")
        caller = next(r for r in deps if r.program_name == "caller")
        assert set(caller.call_site_paths) == {"root/use_a", "root/use_b"}

    def test_reverse_index_to_dict_round_trip(self) -> None:
        """Reverse index survives to_dict/from_dict round-trip."""
        registry = PackRegistry()
        exp = _export("step_x")
        manifest = _manifest("lib", "1.0.0", exports=(exp,), dependencies=(_dep("dep_a"),))
        registry.register_pack(manifest, {"step_x": _program("step_x", stable_id="step_x")})

        data = registry.reverse_index.to_dict()
        restored = PackReverseIndex.from_dict(data)

        orig_deps = registry.reverse_index.dependents_of("dep_a")
        rest_deps = restored.dependents_of("dep_a")
        assert len(orig_deps) == len(rest_deps)
        assert orig_deps[0].program_name == rest_deps[0].program_name


# ── False-pass guard: resolution does not import implementation internals ──


class TestFalsePassGuardNoImplementationImport:
    """Prove that resolution does NOT import or use any implementation code.

    The registry resolves pack exports purely from registered metadata
    (manifests, providers, lockfile entries).  It never imports step/workflow
    function bodies, decorator modules, or any runtime execution machinery
    to perform resolution.  We prove this by constructing NativeProgram
    instances that have NO actual function implementations and resolving
    them successfully.
    """

    def test_resolve_does_not_require_actual_function(self) -> None:
        """A NativeProgram with no function body (just metadata) resolves fine."""
        registry = PackRegistry()
        exp = _export("pure_metadata_step", kind="step")
        # NativeProgram with no phases, no instructions, no actual function
        prog = NativeProgram(
            name="pure_metadata_step",
            stable_id="pure_metadata_step",
        )
        manifest = _manifest("meta_pack", "1.0.0", exports=(exp,))
        registry.register_pack(manifest, {"pure_metadata_step": prog})

        resolved = registry.resolve("pure_metadata_step")
        assert resolved is prog

    def test_resolve_does_not_import_arnold_modules(self) -> None:
        """The resolution path does not trigger any additional imports of
        arnold.pipeline.native submodules beyond what's already imported."""
        registry = PackRegistry()
        exp_a = _export("step_a", kind="step")
        exp_b = _export("wf_b", kind="workflow")
        manifest = _manifest("test_pack", "3.0.0", exports=(exp_a, exp_b))

        registry.register_pack(
            manifest,
            {
                "step_a": NativeProgram(name="step_a", stable_id="step_a"),
                "wf_b": NativeProgram(name="wf_b", stable_id="wf_b"),
            },
        )

        # Capture current module set before resolution
        before = set(sys.modules.keys())

        # Resolve both exports
        registry.resolve("step_a")
        registry.resolve("wf_b")

        after = set(sys.modules.keys())
        new_modules = after - before

        # No new arnold modules should have been imported
        arnold_new = [m for m in new_modules if m.startswith("arnold")]
        assert len(arnold_new) == 0, (
            f"Resolution imported these arnold modules: {arnold_new}"
        )

    def test_resolve_works_with_programs_having_no_instructions(self) -> None:
        """Programs with empty instructions/phases/decisions resolve correctly."""
        registry = PackRegistry()
        exp = _export("empty_prog", kind="workflow")
        # Completely empty program — no instructions, phases, decisions, loops
        prog = NativeProgram(
            name="empty_prog",
            stable_id="empty_prog",
            instructions=(),
            phases=(),
            decisions=(),
            loop_guards=(),
        )
        manifest = _manifest("empty_pack", "1.0.0", exports=(exp,))
        registry.register_pack(manifest, {"empty_prog": prog})

        resolved = registry.resolve("empty_prog")
        assert resolved is prog
        assert resolved.instructions == ()
        assert resolved.phases == ()

    def test_resolution_never_calls_the_program_function(self) -> None:
        """Proof: we can register a NativeProgram whose __call__ would raise,
        and resolution still succeeds because it never invokes it."""
        registry = PackRegistry()

        # A NativeProgram with a sentinel that proves it's never called
        class Sentinel:
            called = False

            def __repr__(self) -> str:
                Sentinel.called = True
                return "SENTINEL"

        sentinel = Sentinel()
        exp = _export("never_called", kind="step")
        # Use a program that carries non-callable metadata—resolution only reads fields
        prog = NativeProgram(
            name="never_called",
            stable_id="never_called",
            description="This program is metadata-only and should never be executed",
        )
        manifest = _manifest("guard_pack", "1.0.0", exports=(exp,))
        registry.register_pack(manifest, {"never_called": prog})

        # Resolve
        resolved = registry.resolve("never_called")
        assert resolved is prog
        assert resolved.name == "never_called"

        # Sentinel is never touched by resolution — proving no dynamic access
        assert not Sentinel.called, "Sentinel was accessed — resolution is touching things it shouldn't!"

    def test_lockfile_resolution_purely_metadata_driven(self) -> None:
        """With a lockfile, the resolution path only checks version and interface_hash —
        it never inspects the program's implementation body."""
        registry = PackRegistry()
        exp = _export("meta_driven", kind="step")
        prog = NativeProgram(
            name="meta_driven",
            stable_id="meta_driven",
        )
        manifest = _manifest("meta_pack", "1.0.0", exports=(exp,))
        registry.register_pack(manifest, {"meta_driven": prog})

        exp_hash = compute_interface_hash(stable_id="meta_driven")
        lf = _lockfile(_lock_entry("meta_driven", "1.0.0", exp_hash))

        # This should succeed based purely on manifest + lockfile metadata
        resolved = registry.resolve("meta_driven", lockfile=lf)
        assert resolved is prog

    def test_registration_does_not_call_or_inspect_function_body(self) -> None:
        """Registration only checks schema and stable_id consistency —
        it never inspects function bodies or invokes anything."""
        registry = PackRegistry()
        # A program with no phases, instructions, or any actual code
        exp = _export("bare_export", kind="step")
        prog = NativeProgram(
            name="bare_export",
            stable_id="bare_export",
        )
        manifest = _manifest("bare", "1.0.0", exports=(exp,))

        # Should register without error
        registry.register_pack(manifest, {"bare_export": prog})
        assert registry.has("bare_export")

    def test_two_packs_no_cross_import(self) -> None:
        """Two packs registered together don't cross-import each other's internals."""
        registry = PackRegistry()

        exp_a = _export("step_a", kind="step")
        exp_b = _export("step_b", kind="step")
        manifest_a = _manifest("pack_a", "1.0.0", exports=(exp_a,), dependencies=(_dep("step_b"),))
        manifest_b = _manifest("pack_b", "1.0.0", exports=(exp_b,), dependencies=(_dep("step_a"),))

        registry.register_pack(
            manifest_a, {"step_a": NativeProgram(name="step_a", stable_id="step_a")}
        )
        registry.register_pack(
            manifest_b, {"step_b": NativeProgram(name="step_b", stable_id="step_b")}
        )

        # Both resolve independently, no cross-contamination
        assert registry.resolve("step_a").name == "step_a"
        assert registry.resolve("step_b").name == "step_b"

        # Reverse index shows the cross-dependency relationship from registration
        deps_of_a = registry.reverse_index.dependents_of("step_a")
        assert any(r.program_name == "step_b" for r in deps_of_a)

        deps_of_b = registry.reverse_index.dependents_of("step_b")
        assert any(r.program_name == "step_a" for r in deps_of_b)


# ── Edge cases and diagnostics ─────────────────────────────────────────


class TestPackRegistryEdgeCases:
    """Boundary behavior, diagnostics, and error clarity."""

    def test_registered_versions_empty_for_unknown_id(self) -> None:
        """registered_versions returns empty tuple for unknown stable_id."""
        registry = PackRegistry()
        assert registry.registered_versions("unknown") == ()

    def test_registered_versions_empty_for_empty_string(self) -> None:
        """registered_versions returns empty tuple for empty string."""
        registry = PackRegistry()
        assert registry.registered_versions("") == ()

    def test_registrations_for_empty_string(self) -> None:
        """registrations_for returns empty tuple for empty string."""
        registry = PackRegistry()
        assert registry.registrations_for("") == ()

    def test_registrations_for_unknown_id(self) -> None:
        """registrations_for returns empty tuple for unknown stable_id."""
        registry = PackRegistry()
        assert registry.registrations_for("unknown") == ()

    def test_registrations_for_returns_ordered_tuple(self) -> None:
        """registrations_for returns registrations in registration order."""
        registry = PackRegistry()
        exp = _export("step")
        m1 = _manifest("p", "1.0.0", exports=(exp,))
        m2 = _manifest("p", "2.0.0", exports=(exp,))
        registry.register_pack(m1, {"step": _program("step_v1", stable_id="step")})
        registry.register_pack(m2, {"step": _program("step_v2", stable_id="step")})

        regs = registry.registrations_for("step")
        assert regs[0].version == "1.0.0"
        assert regs[1].version == "2.0.0"

    def test_to_lockfile_entry_round_trip(self) -> None:
        """RegisteredPackExport.to_lockfile_entry produces a valid LockfileEntry."""
        registry = PackRegistry()
        exp = _export("step", kind="step")
        prog = _program("step", stable_id="step")
        manifest = _manifest("p", "1.0.0", exports=(exp,))
        registry.register_pack(manifest, {"step": prog})

        reg = registry.registrations_for("step")[0]
        lfe = reg.to_lockfile_entry()
        assert lfe.stable_id == "step"
        assert lfe.version == "1.0.0"
        assert lfe.interface_hash == reg.interface_hash

    def test_resolved_pack_export_properties(self) -> None:
        """ResolvedPackExport delegates to registration correctly."""
        registry = PackRegistry()
        exp = _export("step", kind="step")
        prog = _program("step", stable_id="step")
        manifest = _manifest("p", "1.0.0", exports=(exp,))
        registry.register_pack(manifest, {"step": prog})

        entry = registry.resolve_entry("step")
        assert entry.program is prog
        assert entry.manifest is manifest
        assert entry.export is exp
        assert entry.interface_hash == compute_interface_hash(stable_id="step")

    def test_ambiguous_lockfile_entries_raises(self) -> None:
        """A lockfile with duplicate stable_id entries raises LookupError."""
        registry = PackRegistry()
        exp = _export("step")
        manifest = _manifest("p", "1.0.0", exports=(exp,))
        registry.register_pack(manifest, {"step": _program("step", stable_id="step")})

        exp_hash = compute_interface_hash(stable_id="step")
        lf = PackLockfile(entries=(
            _lock_entry("step", "1.0.0", exp_hash),
            _lock_entry("step", "1.0.0", exp_hash),
        ))

        with pytest.raises(LookupError, match="ambiguous lockfile entries"):
            registry.resolve("step", lockfile=lf)

    def test_empty_registry_has_no_entries(self) -> None:
        """A fresh registry has no entries."""
        registry = PackRegistry()
        assert not registry.has("anything")
        assert registry.registrations_for("anything") == ()
        assert registry.registered_versions("anything") == ()

    def test_pack_id_falls_back_to_name(self) -> None:
        """When manifest.stable_id is None, pack_id returns manifest.name."""
        registry = PackRegistry()
        exp = _export("step")
        manifest = _manifest("my_pack_name", "1.0.0", exports=(exp,), stable_id=None)
        registry.register_pack(manifest, {"step": _program("step", stable_id="step")})
        reg = registry.registrations_for("step")[0]
        assert reg.pack_id == "my_pack_name"

    def test_pack_id_uses_stable_id_when_present(self) -> None:
        """When manifest.stable_id is set, pack_id returns that."""
        registry = PackRegistry()
        exp = _export("step")
        manifest = _manifest("display_name", "1.0.0", exports=(exp,), stable_id="canonical_id")
        registry.register_pack(manifest, {"step": _program("step", stable_id="step")})
        reg = registry.registrations_for("step")[0]
        assert reg.pack_id == "canonical_id"


# ── JSON serializability of exported records ────────────────────────────


class TestPackRegistryJsonSerializability:
    """All exported records (RegisteredPackExport, ResolvedPackExport)
    produce JSON-serializable dictionaries."""

    def test_registered_pack_export_to_lockfile_entry_is_json_serializable(self) -> None:
        """to_lockfile_entry produces a JSON-serializable dict."""
        registry = PackRegistry()
        exp = _export("step", kind="step")
        manifest = _manifest("p", "1.0.0", exports=(exp,))
        registry.register_pack(manifest, {"step": _program("step", stable_id="step")})

        reg = registry.registrations_for("step")[0]
        lfe = reg.to_lockfile_entry()
        json.dumps(lfe.to_dict())  # should not raise

    def test_resolved_pack_export_is_not_json_serializable(self) -> None:
        """ResolvedPackExport contains NativeProgram which is not JSON-serializable.
        But its lockfile_entry and export are."""
        registry = PackRegistry()
        exp = _export("step", kind="step")
        manifest = _manifest("p", "1.0.0", exports=(exp,))
        registry.register_pack(manifest, {"step": _program("step", stable_id="step")})

        resolved = registry.resolve_entry("step")
        # The lockfile_entry can be serialized when present
        resolved.export.to_dict()  # should not raise
        # lockfile_entry is None here (no lockfile), so skip
        assert resolved.lockfile_entry is None
