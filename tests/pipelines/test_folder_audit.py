"""Tests for the ``folder-audit`` pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def sample_dir(tmp_path: Path) -> Path:
    """Create a small directory tree for audit tests."""
    root = tmp_path / "sample"
    root.mkdir()
    (root / "README.md").write_text("# Sample")
    (root / "script.py").write_text("print('hello')")
    (root / "build").mkdir()
    (root / "build" / "artifact.bin").write_text("data")
    (root / ".hidden").mkdir()
    (root / ".hidden" / "secret.txt").write_text("secret")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "cache.pyc").write_text("cache")
    gitignore = root / ".gitignore"
    gitignore.write_text("__pycache__\nbuild/\n")
    return root


def test_build_tree_respects_gitignore_and_hidden(sample_dir: Path) -> None:
    from arnold.pipelines.folder_audit import _build_tree

    tree = _build_tree(sample_dir, max_depth=2, respect_gitignore=True, skip_hidden=True)
    paths = {f["path"] for f in tree}
    assert "." in paths
    assert "build" not in paths
    assert "__pycache__" not in paths
    assert ".hidden" not in paths

    root = next(f for f in tree if f["path"] == ".")
    names = {c["name"] for c in root["children"]}
    assert "README.md" in names
    assert "script.py" in names
    assert "build" not in names
    assert "__pycache__" not in names


def test_build_tree_includes_all_when_not_ignored(sample_dir: Path) -> None:
    from arnold.pipelines.folder_audit import _build_tree

    tree = _build_tree(sample_dir, max_depth=2, respect_gitignore=False, skip_hidden=False)
    paths = {f["path"] for f in tree}
    assert "build" in paths
    assert "__pycache__" in paths
    assert ".hidden" in paths


def test_summarize_children_caps_files() -> None:
    from arnold.pipelines.folder_audit import _summarize_children

    children = [{"name": f"file_{i}.txt", "type": "file"} for i in range(100)]
    children.insert(0, {"name": "subdir", "type": "dir"})
    summarized = _summarize_children(children, max_files=10)
    assert len(summarized) == 12  # 1 dir + 10 files + placeholder
    assert summarized[0]["name"] == "subdir"
    assert summarized[-1]["name"] == "... (90 more files)"


def test_compute_summary_counts_classifications() -> None:
    from arnold.pipelines.folder_audit import _compute_summary

    folders: list[dict[str, Any]] = [
        {
            "path": ".",
            "level": 0,
            "items": [
                {"name": "a", "type": "file", "fits": True, "classification": "fit"},
                {"name": "b", "type": "file", "fits": False, "classification": "misplaced"},
            ],
        },
        {
            "path": "sub",
            "level": 1,
            "items": [
                {"name": "c", "type": "dir", "fits": False, "classification": "duplicate"},
            ],
        },
    ]
    summary = _compute_summary(folders)
    assert summary["total_folders"] == 2
    assert summary["total_items"] == 3
    assert summary["fit"] == 1
    assert summary["misplaced"] == 1
    assert summary["duplicate"] == 1


def test_build_pipeline_returns_expected_stages() -> None:
    from arnold.pipelines.folder_audit import build_pipeline

    pipeline = build_pipeline()
    assert set(pipeline.stages.keys()) == {"ingest", "audit", "emit"}
    assert pipeline.entry == "ingest"


def test_emit_step_renders_nested_tree(tmp_path: Path) -> None:
    from arnold.pipelines.folder_audit import EmitStep
    from arnold.pipeline.types import StepContext

    ctx = StepContext(
        artifact_root=str(tmp_path),
        state={
            "target_dir": str(tmp_path),
            "tree": [
                {
                    "path": ".",
                    "level": 0,
                    "children": [
                        {"name": "README.md", "type": "file"},
                        {"name": "sub", "type": "dir"},
                    ],
                },
                {
                    "path": "sub",
                    "level": 1,
                    "children": [
                        {"name": "nested.txt", "type": "file"},
                    ],
                },
            ],
            "audit": {
                "folders": [
                    {
                        "path": ".",
                        "level": 0,
                        "inferred_purpose": "Root",
                        "items": [
                            {"name": "README.md", "type": "file", "fits": True, "classification": "fit"},
                            {"name": "sub", "type": "dir", "fits": False, "classification": "too_granular"},
                        ],
                    },
                    {
                        "path": "sub",
                        "level": 1,
                        "inferred_purpose": "Subfolder",
                        "items": [
                            {"name": "nested.txt", "type": "file", "fits": True, "classification": "fit"},
                        ],
                    },
                ],
                "summary": {},
                "settled_decisions": [],
            },
        },
        inputs={},
        mode="code",
    )
    result = EmitStep().run(ctx)
    md_path = result.outputs["audit_md"]
    md = md_path.read_text()
    assert "# Folder Audit" in md
    assert "- `.` — Root" in md
    assert "- README.md (file)" in md
    assert "- sub (dir) † too_granular" in md
    assert "- `sub` — Subfolder" in md
    assert "- nested.txt (file)" in md

    json_path = result.outputs["audit_json"]
    data = json.loads(json_path.read_text())
    assert data["folders"][0]["path"] == "."


def test_build_pipeline_passes_worker_to_audit_step() -> None:
    from arnold.pipelines.folder_audit import AuditStep, build_pipeline

    def fake_worker(*, prompt: str, **kwargs: Any) -> str:
        return "ignored"

    pipeline = build_pipeline(worker=fake_worker)
    audit_step = pipeline.stages["audit"].step
    assert isinstance(audit_step, AuditStep)
    assert audit_step._worker is fake_worker


def test_audit_step_calls_worker_and_parses_json(tmp_path: Path) -> None:
    from arnold.pipelines.folder_audit import AuditStep
    from arnold.pipeline.types import StepContext

    calls: list[tuple[str, str]] = []

    def fake_worker(*, prompt: str, spec: str = "", **kwargs: Any) -> str:
        calls.append((prompt, spec))
        return json.dumps({
            "folders": [
                {
                    "path": ".",
                    "level": 0,
                    "inferred_purpose": "root",
                    "items": [
                        {"name": "a.txt", "type": "file", "fits": True, "classification": "fit"},
                    ],
                }
            ]
        })

    step = AuditStep(
        _worker=fake_worker,
        _pipeline_name="folder-audit",
        _chunk_size=10,
        _max_workers=1,
    )
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    ctx = StepContext(
        artifact_root=str(plan_dir),
        state={
            "target_dir": str(tmp_path),
            "tree": [
                {
                    "path": ".",
                    "level": 0,
                    "children": [{"name": "a.txt", "type": "file"}],
                }
            ],
            "profile": {"audit": "codex:gpt-5.5"},
        },
        inputs={"chunk_size": "10", "max_workers": "1"},
        mode="code",
    )
    result = step.run(ctx)

    assert len(calls) == 1
    assert calls[0][1] == "codex:gpt-5.5"
    assert result.next == "done"
    assert result.state_patch["audit"]["folders"][0]["path"] == "."
    assert result.state_patch["audit"]["summary"]["total_folders"] == 1
    assert (plan_dir / "audit_raw" / "v1.md").exists()


def test_audit_step_without_worker_raises() -> None:
    from arnold.pipelines.folder_audit import AuditStep
    from arnold.pipeline.types import StepContext

    step = AuditStep(_pipeline_name="folder-audit")
    ctx = StepContext(
        artifact_root=str("/tmp/folder-audit-test-plan"),
        state={
            "target_dir": "/tmp",
            "tree": [{"path": ".", "level": 0, "children": []}],
        },
        inputs={},
        mode="code",
    )
    with pytest.raises(RuntimeError, match="no worker"):
        step.run(ctx)


# ── Native pipeline tests ────────────────────────────────────────────────


def test_native_phases_are_discoverable_via_is_phase() -> None:
    """Prove that the native ``@phase``-decorated adapters are discoverable."""
    from arnold.pipeline.native.decorators import is_phase, get_phase_meta
    from arnold.pipelines.folder_audit.native import ingest, audit, emit

    assert is_phase(ingest), "ingest should be a @phase"
    assert is_phase(audit), "audit should be a @phase"
    assert is_phase(emit), "emit should be a @phase"

    assert get_phase_meta(ingest)["name"] == "ingest"
    assert get_phase_meta(audit)["name"] == "audit"
    assert get_phase_meta(emit)["name"] == "emit"


def test_native_phases_are_reusable_callables() -> None:
    """Prove that the native phases are callable with a dict context."""
    from arnold.pipelines.folder_audit.native import ingest, audit, emit

    # Each phase should be callable and accept a dict context.
    assert callable(ingest)
    assert callable(audit)
    assert callable(emit)

    # Verify function signatures accept a dict.
    import inspect
    for phase_fn in (ingest, audit, emit):
        sig = inspect.signature(phase_fn)
        params = list(sig.parameters.keys())
        assert "ctx" in params, f"{phase_fn.__name__} should accept 'ctx' parameter"


def test_native_pipeline_generator_is_discoverable() -> None:
    """Prove the ``@pipeline(name=\"folder_audit\")`` generator is discoverable."""
    from arnold.pipeline.native.decorators import is_pipeline, get_pipeline_meta
    from arnold.pipelines.folder_audit.native import folder_audit_native

    assert is_pipeline(folder_audit_native), (
        "folder_audit_native should be a @pipeline"
    )
    meta = get_pipeline_meta(folder_audit_native)
    assert meta is not None
    assert meta["name"] == "folder-audit"
    assert "Native linear folder-audit pipeline" in meta["description"]


def test_native_pipeline_compiles_to_sequential_program() -> None:
    """Prove the ``@pipeline`` generator compiles to a sequential program."""
    from arnold.pipeline.native.compiler import compile_pipeline
    from arnold.pipelines.folder_audit.native import (
        folder_audit_native,
        ingest,
        audit,
        emit,
    )

    # The compiler resolves phase/decision names from the calling frame's
    # globals/locals, so the phase callables must be importable in this scope.
    program = compile_pipeline(folder_audit_native)
    assert program.name == "folder-audit"

    # Should have 4 instructions: ingest, audit, emit, halt
    assert len(program.instructions) == 4

    phase_instructions = [i for i in program.instructions if i.op == "phase"]
    assert len(phase_instructions) == 3
    assert [i.name for i in phase_instructions] == ["ingest", "audit", "emit"]

    # Verify sequential PCs
    for i, instr in enumerate(phase_instructions):
        assert instr.pc == i
        assert instr.next_pc == i + 1

    # Verify halt is last
    halt_instr = program.instructions[-1]
    assert halt_instr.op == "halt"

    # Verify phases are tracked
    assert [p.name for p in program.phases] == ["ingest", "audit", "emit"]


def test_build_pipeline_is_native_backed() -> None:
    """``build_pipeline()`` returns a native-backed projected shell."""
    from arnold.pipeline import Pipeline
    from arnold.pipeline.native import NativeProgram
    from arnold.pipelines.folder_audit import build_pipeline

    pipeline = build_pipeline()
    assert isinstance(pipeline, Pipeline)
    assert set(pipeline.stages.keys()) == {"ingest", "audit", "emit"}
    assert pipeline.entry == "ingest"
    assert isinstance(pipeline.native_program, NativeProgram)
    assert pipeline.native_program.name == "folder-audit"
    assert tuple(pipeline.resource_bundles) == ()

    # Verify edges form a linear chain: ingest → audit → emit → halt
    ingest_stage = pipeline.stages["ingest"]
    audit_stage = pipeline.stages["audit"]
    emit_stage = pipeline.stages["emit"]

    assert len(ingest_stage.edges) == 1
    assert ingest_stage.edges[0].target == "audit"

    assert len(audit_stage.edges) == 1
    assert audit_stage.edges[0].target == "emit"

    assert len(emit_stage.edges) == 1
    assert emit_stage.edges[0].target == "halt"


def test_package_metadata_advertises_native_execution() -> None:
    """Package metadata advertises native execution."""
    from arnold.pipelines import folder_audit as pkg

    assert pkg.driver[0] == "native"
    assert "native" in pkg.supported_modes
    assert pkg.entrypoint == "build_pipeline"
    assert callable(pkg.build_pipeline)

    result = pkg.build_pipeline()
    assert hasattr(result, "stages")
    assert hasattr(result, "entry")

    assert pkg.name == "folder-audit"
    assert "audit" in pkg.capabilities

    # Native pipeline generator should NOT be the entrypoint.
    assert not hasattr(pkg, "folder_audit_native") or (
        pkg.entrypoint != "folder_audit_native"
    )


# ── Native runtime tests ─────────────────────────────────────────────────


def test_run_native_succeeds(
    tmp_path: Path,
) -> None:
    """``run_native()`` executes the native program end-to-end."""
    from arnold.pipelines.folder_audit.native import run_native
    from arnold.pipeline.native import NativeExecutionResult

    sample = tmp_path / "sample"
    sample.mkdir()
    (sample / "README.md").write_text("# test")

    result = run_native(target_dir=sample)

    assert isinstance(result, NativeExecutionResult)
    assert not result.suspended
    assert len(result.stages) == 3
    assert any("ingest" in s for s in result.stages)
    assert any("audit" in s for s in result.stages)
    assert any("emit" in s for s in result.stages)

    native_dir = sample / ".arnold" / "folder-audit" / "native"
    assert (native_dir / "audit.json").exists()
    assert (native_dir / "audit.md").exists()


def test_build_pipeline_unchanged_regardless_of_native_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``build_pipeline()`` returns the same native-backed shell regardless of env."""
    from arnold.pipelines.folder_audit import build_pipeline

    monkeypatch.delenv("ARNOLD_NATIVE_RUNTIME", raising=False)
    pipeline_off = build_pipeline()
    assert set(pipeline_off.stages.keys()) == {"ingest", "audit", "emit"}
    assert pipeline_off.entry == "ingest"
    assert pipeline_off.native_program is not None

    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    pipeline_on = build_pipeline()
    assert set(pipeline_on.stages.keys()) == {"ingest", "audit", "emit"}
    assert pipeline_on.entry == "ingest"
    assert pipeline_on.native_program is not None


def test_package_metadata_advertises_native_regardless_of_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Package metadata is native-first regardless of the native-runtime env flag."""
    import importlib

    monkeypatch.delenv("ARNOLD_NATIVE_RUNTIME", raising=False)
    from arnold.pipelines import folder_audit as pkg_off
    assert pkg_off.driver[0] == "native"
    assert pkg_off.entrypoint == "build_pipeline"

    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
    importlib.reload(pkg_off)
    from arnold.pipelines import folder_audit as pkg_on
    assert pkg_on.driver[0] == "native"
    assert pkg_on.entrypoint == "build_pipeline"
