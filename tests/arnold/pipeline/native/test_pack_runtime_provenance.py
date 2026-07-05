from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.pipeline.native import (
    AuditHooks,
    DependencySpec,
    ExportEntry,
    LockfileEntry,
    NativeProgram,
    NativeRuntimeError,
    PackLockfile,
    PackManifest,
    PackRegistry,
    compile_pipeline,
    phase,
    pipeline,
    read_native_cursor,
    resolved_versions_by_stable_id_for_run,
    run_native_pipeline,
)


@pytest.fixture(autouse=True)
def _enable_native_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")


def _export(stable_id: str, *, name: str | None = None) -> ExportEntry:
    return ExportEntry(
        stable_id=stable_id,
        kind="step",
        name=name or stable_id.replace(".", "_"),
    )


def _dep(stable_id: str) -> DependencySpec:
    return DependencySpec(stable_id=stable_id)


def _manifest(
    name: str,
    version: str,
    *,
    exports: tuple[ExportEntry, ...],
    dependencies: tuple[DependencySpec, ...] = (),
    stable_id: str | None = None,
) -> PackManifest:
    return PackManifest(
        name=name,
        version=version,
        stable_id=stable_id or name,
        exports=exports,
        dependencies=dependencies,
    )


def _lockfile(*entries: LockfileEntry, manifest_stable_id: str = "consumer", manifest_version: str = "1.0.0") -> PackLockfile:
    return PackLockfile(
        manifest_stable_id=manifest_stable_id,
        manifest_version=manifest_version,
        entries=entries,
    )


def _provider(stable_id: str) -> NativeProgram:
    return NativeProgram(name=stable_id.replace(".", "_"), stable_id=stable_id)


def _read_audit(audit_dir: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (audit_dir / "audit.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_events(trace_dir: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (trace_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _consumer_program(*, steps: int = 1):
    @phase
    def first(ctx: dict) -> dict:
        return {"first": True}

    if steps > 1:
        @phase
        def second(ctx: dict) -> dict:
            return {"second": True}

        @pipeline
        def consumer(ctx: dict) -> dict:
            state = yield first(ctx)
            state = yield second(ctx)
            return state
    else:
        @pipeline
        def consumer(ctx: dict) -> dict:
            state = yield first(ctx)
            return state

    return compile_pipeline(consumer)


def _nested_registry() -> tuple[PackRegistry, PackManifest, PackLockfile]:
    registry = PackRegistry()

    export_c = _export("pack.c")
    manifest_c = _manifest("pack-c", "1.0.0", exports=(export_c,), stable_id="pack.c.lib")
    registry.register_pack(manifest_c, {"pack.c": _provider("pack.c")})

    export_b = _export("pack.b")
    manifest_b = _manifest(
        "pack-b",
        "2.0.0",
        exports=(export_b,),
        dependencies=(_dep("pack.c"),),
        stable_id="pack.b.lib",
    )
    registry.register_pack(manifest_b, {"pack.b": _provider("pack.b")})

    consumer_manifest = _manifest(
        "consumer-pack",
        "3.0.0",
        exports=(_export("consumer.root"),),
        dependencies=(_dep("pack.b"),),
        stable_id="consumer.pack",
    )
    lockfile = _lockfile(
        LockfileEntry(
            stable_id="pack.b",
            version="2.0.0",
            interface_hash=registry.resolve_entry("pack.b").registration.to_lockfile_entry().interface_hash,
        ),
        LockfileEntry(
            stable_id="pack.c",
            version="1.0.0",
            interface_hash=registry.resolve_entry("pack.c").registration.to_lockfile_entry().interface_hash,
        ),
        manifest_stable_id="consumer.pack",
        manifest_version="3.0.0",
    )
    return registry, consumer_manifest, lockfile


class TestPackRuntimeProvenance:
    def test_missing_pin_refuses_before_any_step_runs(self) -> None:
        calls: list[str] = []

        @phase
        def step(ctx: dict) -> dict:
            calls.append("ran")
            return {"ok": True}

        @pipeline
        def consumer(ctx: dict) -> dict:
            state = yield step(ctx)
            return state

        registry = PackRegistry()
        manifest_b = _manifest("pack-b", "1.0.0", exports=(_export("pack.b"),), stable_id="pack.b.lib")
        registry.register_pack(manifest_b, {"pack.b": _provider("pack.b")})
        consumer_manifest = _manifest(
            "consumer-pack",
            "1.0.0",
            exports=(_export("consumer.root"),),
            dependencies=(_dep("pack.b"),),
            stable_id="consumer.pack",
        )

        with pytest.raises(NativeRuntimeError, match="missing lockfile entry"):
            run_native_pipeline(
                compile_pipeline(consumer),
                pack_manifest=consumer_manifest,
                pack_lockfile=PackLockfile(),
                pack_registry=registry,
            )

        assert calls == []

    def test_ambiguous_pin_refuses_before_any_step_runs(self) -> None:
        calls: list[str] = []
        registry, consumer_manifest, lockfile = _nested_registry()
        ambiguous = PackLockfile(
            manifest_stable_id=lockfile.manifest_stable_id,
            manifest_version=lockfile.manifest_version,
            entries=(
                lockfile.entries[0],
                lockfile.entries[0],
                lockfile.entries[1],
            ),
        )

        @phase
        def marker(ctx: dict) -> dict:
            calls.append("ran")
            return {"ok": True}

        @pipeline
        def actual(ctx: dict) -> dict:
            state = yield marker(ctx)
            return state

        with pytest.raises(NativeRuntimeError, match="ambiguous lockfile entries"):
            run_native_pipeline(
                compile_pipeline(actual),
                pack_manifest=consumer_manifest,
                pack_lockfile=ambiguous,
                pack_registry=registry,
            )

        assert calls == []

    def test_audit_run_init_and_helper_report_nested_versions(self, tmp_path: Path) -> None:
        audit_dir = tmp_path / "audit"
        hooks = AuditHooks(audit_dir=audit_dir)
        registry, consumer_manifest, lockfile = _nested_registry()

        run_native_pipeline(
            _consumer_program(),
            hooks=hooks,
            pack_manifest=consumer_manifest,
            pack_lockfile=lockfile,
            pack_registry=registry,
        )

        records = _read_audit(audit_dir)
        run_init = records[0]
        assert run_init["event"] == "run.init"
        assert run_init["pack_provenance"]["manifest_stable_id"] == "consumer.pack"
        assert run_init["pack_provenance"]["manifest_version"] == "3.0.0"
        assert [
            (entry["stable_id"], entry["version"])
            for entry in run_init["pack_provenance"]["dependencies"]
        ] == [("pack.b", "2.0.0"), ("pack.c", "1.0.0")]
        assert resolved_versions_by_stable_id_for_run(
            audit_dir,
            run_id=hooks._run_id,
        ) == {
            "pack.b": "2.0.0",
            "pack.c": "1.0.0",
        }

    def test_trace_run_enter_metadata_includes_pack_provenance(self, tmp_path: Path) -> None:
        trace_dir = tmp_path / "trace"
        registry, consumer_manifest, lockfile = _nested_registry()

        run_native_pipeline(
            _consumer_program(),
            trace_dir=trace_dir,
            pack_manifest=consumer_manifest,
            pack_lockfile=lockfile,
            pack_registry=registry,
        )

        run_enter = next(
            event for event in _read_events(trace_dir) if event["kind"] == "run.enter"
        )
        dependencies = run_enter["payload"]["trace"]["metadata"]["pack_provenance"]["dependencies"]
        assert [(entry["stable_id"], entry["version"]) for entry in dependencies] == [
            ("pack.b", "2.0.0"),
            ("pack.c", "1.0.0"),
        ]

    def test_checkpoint_cursor_native_extra_includes_pack_provenance(self, tmp_path: Path) -> None:
        registry, consumer_manifest, lockfile = _nested_registry()

        result = run_native_pipeline(
            _consumer_program(steps=2),
            artifact_root=tmp_path,
            max_phases=1,
            pack_manifest=consumer_manifest,
            pack_lockfile=lockfile,
            pack_registry=registry,
        )

        assert result.suspended is True
        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        dependencies = cursor["native"]["pack_provenance"]["dependencies"]
        assert [(entry["stable_id"], entry["version"]) for entry in dependencies] == [
            ("pack.b", "2.0.0"),
            ("pack.c", "1.0.0"),
        ]
