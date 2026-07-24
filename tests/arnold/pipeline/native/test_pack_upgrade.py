"""Focused tests for deliberate pack re-pin planning and application."""

from __future__ import annotations

import pytest

from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.native.pack_metadata import (
    DependencySpec,
    ExportEntry,
    LockfileEntry,
    PackLockfile,
    PackManifest,
    compute_interface_hash,
)
from arnold.pipeline.native.pack_registry import PackRegistry
from arnold.pipeline.native.pack_upgrade import (
    PackUpgradeError,
    apply_pack_repin,
    plan_pack_repin,
)


def _program(
    name: str = "test_program",
    stable_id: str | None = None,
    inputs_schema: dict | None = None,
    outputs_schema: dict | None = None,
) -> NativeProgram:
    return NativeProgram(
        name=name,
        stable_id=stable_id,
        inputs_schema=inputs_schema,
        outputs_schema=outputs_schema,
    )


def _export(
    stable_id: str,
    *,
    kind: str = "step",
    name: str = "",
    inputs_schema: dict | None = None,
    outputs_schema: dict | None = None,
    body_hash: str | None = None,
) -> ExportEntry:
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
    *,
    exports: tuple[ExportEntry, ...] = (),
    dependencies: tuple[DependencySpec, ...] = (),
    stable_id: str | None = None,
) -> PackManifest:
    return PackManifest(
        name=name,
        version=version,
        stable_id=stable_id,
        exports=exports,
        dependencies=dependencies,
    )


def _dep(stable_id: str, version: str = "*") -> DependencySpec:
    return DependencySpec(stable_id=stable_id, version=version)


def _lock_entry(stable_id: str, version: str, interface_hash: str) -> LockfileEntry:
    return LockfileEntry(
        stable_id=stable_id,
        version=version,
        interface_hash=interface_hash,
    )


def _lockfile(*entries: LockfileEntry, manifest_stable_id: str = "consumer", manifest_version: str = "1.0.0") -> PackLockfile:
    return PackLockfile(
        manifest_stable_id=manifest_stable_id,
        manifest_version=manifest_version,
        entries=tuple(entries),
    )


class TestPackUpgradeNonBreakingRepin:
    def test_plan_returns_diff_report_and_proposed_lockfile(self) -> None:
        registry = PackRegistry()
        export_v1 = _export("shared_step")
        export_v2 = _export("shared_step", name="shared_step_v2")
        registry.register_pack(
            _manifest("lib", "1.0.0", exports=(export_v1,)),
            {"shared_step": _program("shared_step_v1", stable_id="shared_step")},
        )
        registry.register_pack(
            _manifest("lib", "1.1.0", exports=(export_v2,)),
            {"shared_step": _program("shared_step_v2", stable_id="shared_step")},
        )

        other_hash = compute_interface_hash(stable_id="other_dep")
        lockfile = _lockfile(
            _lock_entry(
                "shared_step",
                "1.0.0",
                compute_interface_hash(stable_id="shared_step"),
            ),
            _lock_entry("other_dep", "9.9.9", other_hash),
            manifest_stable_id="consumer.pack",
            manifest_version="3.4.5",
        )

        plan = plan_pack_repin(
            registry=registry,
            lockfile=lockfile,
            stable_id="shared_step",
            target_version="1.1.0",
        )

        assert plan.can_apply is True
        assert plan.diff_report.has_breaking_changes is False
        assert plan.current_lockfile_entry.version == "1.0.0"
        assert plan.proposed_lockfile_entry.version == "1.1.0"
        assert plan.proposed_lockfile.manifest_stable_id == "consumer.pack"
        assert plan.proposed_lockfile.manifest_version == "3.4.5"
        assert plan.proposed_lockfile.entries[0] == plan.proposed_lockfile_entry
        assert plan.proposed_lockfile.entries[1] == lockfile.entries[1]
        assert lockfile.entries[0].version == "1.0.0"

    def test_apply_returns_updated_lockfile_without_mutating_original(self) -> None:
        registry = PackRegistry()
        export_v1 = _export("shared_step")
        export_v2 = _export("shared_step", name="shared_step_renamed")
        registry.register_pack(
            _manifest("lib", "1.0.0", exports=(export_v1,)),
            {"shared_step": _program("shared_step_v1", stable_id="shared_step")},
        )
        registry.register_pack(
            _manifest("lib", "1.1.0", exports=(export_v2,)),
            {"shared_step": _program("shared_step_v2", stable_id="shared_step")},
        )
        lockfile = _lockfile(
            _lock_entry(
                "shared_step",
                "1.0.0",
                compute_interface_hash(stable_id="shared_step"),
            )
        )

        upgraded = apply_pack_repin(
            registry=registry,
            lockfile=lockfile,
            stable_id="shared_step",
            target_version="1.1.0",
        )

        assert lockfile.entries[0].version == "1.0.0"
        assert upgraded.entries[0].version == "1.1.0"


class TestPackUpgradeBreakingRepin:
    def test_breaking_repin_is_planned_but_blocked(self) -> None:
        registry = PackRegistry()
        export_v1 = _export(
            "shared_step",
            inputs_schema={"type": "object", "required": [], "properties": {}},
        )
        export_v2 = _export(
            "shared_step",
            inputs_schema={
                "type": "object",
                "required": ["x"],
                "properties": {"x": {"type": "string"}},
            },
        )
        registry.register_pack(
            _manifest("lib", "1.0.0", exports=(export_v1,)),
            {
                "shared_step": _program(
                    "shared_step_v1",
                    stable_id="shared_step",
                    inputs_schema={"type": "object", "required": [], "properties": {}},
                )
            },
        )
        registry.register_pack(
            _manifest("lib", "2.0.0", exports=(export_v2,)),
            {
                "shared_step": _program(
                    "shared_step_v2",
                    stable_id="shared_step",
                    inputs_schema={
                        "type": "object",
                        "required": ["x"],
                        "properties": {"x": {"type": "string"}},
                    },
                )
            },
        )
        lockfile = _lockfile(
            _lock_entry(
                "shared_step",
                "1.0.0",
                compute_interface_hash(
                    stable_id="shared_step",
                    inputs_schema={"type": "object", "required": [], "properties": {}},
                ),
            )
        )

        plan = plan_pack_repin(
            registry=registry,
            lockfile=lockfile,
            stable_id="shared_step",
            target_version="2.0.0",
        )

        assert plan.can_apply is False
        assert plan.diff_report.has_breaking_changes is True
        assert plan.blocked_reason is not None
        assert plan.proposed_lockfile.entries[0].version == "2.0.0"

    def test_apply_breaking_repin_raises(self) -> None:
        registry = PackRegistry()
        export_v1 = _export("shared_step", outputs_schema={"type": "string"})
        export_v2 = _export("shared_step", outputs_schema={"type": "number"})
        registry.register_pack(
            _manifest("lib", "1.0.0", exports=(export_v1,)),
            {
                "shared_step": _program(
                    "shared_step_v1",
                    stable_id="shared_step",
                    outputs_schema={"type": "string"},
                )
            },
        )
        registry.register_pack(
            _manifest("lib", "2.0.0", exports=(export_v2,)),
            {
                "shared_step": _program(
                    "shared_step_v2",
                    stable_id="shared_step",
                    outputs_schema={"type": "number"},
                )
            },
        )
        lockfile = _lockfile(
            _lock_entry(
                "shared_step",
                "1.0.0",
                compute_interface_hash(
                    stable_id="shared_step",
                    outputs_schema={"type": "string"},
                ),
            )
        )

        with pytest.raises(PackUpgradeError, match="breaking changes detected"):
            apply_pack_repin(
                registry=registry,
                lockfile=lockfile,
                stable_id="shared_step",
                target_version="2.0.0",
            )


class TestPackUpgradeTransitiveImpacts:
    def test_transitive_impacts_report_a_to_b_to_c_chain(self) -> None:
        registry = PackRegistry()
        export_c_v1 = _export("pack.c", outputs_schema={"type": "string"})
        export_c_v2 = _export("pack.c", outputs_schema={"type": "number"})
        registry.register_pack(
            _manifest("pack-c", "1.0.0", exports=(export_c_v1,)),
            {"pack.c": _program("pack_c_v1", stable_id="pack.c", outputs_schema={"type": "string"})},
        )
        registry.register_pack(
            _manifest("pack-c", "2.0.0", exports=(export_c_v2,)),
            {"pack.c": _program("pack_c_v2", stable_id="pack.c", outputs_schema={"type": "number"})},
        )

        manifest_b = _manifest(
            "pack-b",
            "1.0.0",
            exports=(_export("pack.b", kind="workflow"),),
            dependencies=(_dep("pack.c"),),
        )
        registry.register_pack(
            manifest_b,
            {"pack.b": _program("pack_b", stable_id="pack.b")},
        )
        manifest_a = _manifest(
            "pack-a",
            "1.0.0",
            exports=(_export("pack.a", kind="workflow"),),
            dependencies=(_dep("pack.b"),),
        )
        registry.register_pack(
            manifest_a,
            {"pack.a": _program("pack_a", stable_id="pack.a")},
        )

        lockfile_b = _lockfile(
            _lock_entry(
                "pack.c",
                "1.0.0",
                compute_interface_hash(
                    stable_id="pack.c",
                    outputs_schema={"type": "string"},
                ),
            ),
            manifest_stable_id="pack-b",
            manifest_version="1.0.0",
        )
        registry.resolve_entry(
            "pack.c",
            lockfile=lockfile_b,
            dependent_name="pack_b",
            dependent_stable_id="pack.b",
            call_site_paths=("root/use-c",),
        )

        lockfile_a = _lockfile(
            _lock_entry(
                "pack.b",
                "1.0.0",
                compute_interface_hash(stable_id="pack.b"),
            ),
            manifest_stable_id="pack-a",
            manifest_version="1.0.0",
        )
        registry.resolve_entry(
            "pack.b",
            lockfile=lockfile_a,
            dependent_name="pack_a",
            dependent_stable_id="pack.a",
            call_site_paths=("root/use-b",),
        )

        plan = plan_pack_repin(
            registry=registry,
            lockfile=lockfile_b,
            stable_id="pack.c",
            target_version="2.0.0",
        )

        assert plan.can_apply is False
        assert [impact.program_stable_id for impact in plan.transitive_impacts] == [
            "pack.b",
            "pack.a",
        ]
        assert plan.transitive_impacts[0].call_site_paths == ("root/use-c",)
        assert plan.transitive_impacts[0].lockfile_entry == lockfile_b.entries[0]
        assert plan.transitive_impacts[1].call_site_paths == ("root/use-b",)
        assert plan.transitive_impacts[1].lockfile_entry == lockfile_a.entries[0]
