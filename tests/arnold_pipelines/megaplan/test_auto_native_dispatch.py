from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arnold.execution.operations import OperationResult
from arnold.execution.operations import OperationKind, OperationRequest
from arnold.pipeline.native.ir import NativeProgram

from arnold_pipelines.megaplan import auto
from arnold_pipelines.megaplan._compatibility import build_compatibility_shell
from arnold_pipelines.megaplan.pipeline import build_pipeline


def test_run_planning_phase_prefers_compiled_native_program_for_canonical_phase(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_plan(root: Path, args: argparse.Namespace) -> dict[str, Any]:
        calls.append(
            {
                "root": root,
                "plan": args.plan,
                "fresh": args.fresh,
                "confirm_destructive": args.confirm_destructive,
            }
        )
        return {"success": True, "step": "plan"}

    import arnold_pipelines.megaplan.cli as cli
    import arnold_pipelines.megaplan.registry as registry

    monkeypatch.setitem(cli.COMMAND_HANDLERS, "plan", fake_plan)
    monkeypatch.setattr(
        registry,
        "dispatch_operation_for",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("operation registry fallback must not run")
        ),
    )

    exit_code, stdout, stderr = auto._run_planning_phase(
        ["plan", "--fresh", "--plan", "demo"],
        cwd=tmp_path,
        liveness_plan_dir=tmp_path / ".megaplan" / "plans" / "demo",
    )

    assert exit_code == 0
    assert stderr == ""
    assert json.loads(stdout)["step"] == "plan"
    assert calls == [
        {
            "root": tmp_path,
            "plan": "demo",
            "fresh": True,
            "confirm_destructive": False,
        }
    ]


def test_run_planning_phase_keeps_registry_fallback_explicit_for_unsupported_native(
    monkeypatch,
    tmp_path: Path,
) -> None:
    @dataclass
    class ShellWithoutNativeProgram:
        native_program: object | None = None

    import arnold_pipelines.megaplan.pipeline as pipeline_mod
    import arnold_pipelines.megaplan.registry as registry

    monkeypatch.setattr(
        pipeline_mod,
        "build_and_compile_pipeline",
        lambda: ShellWithoutNativeProgram(),
    )

    dispatched: list[dict[str, Any]] = []

    def fake_dispatch(_plugin_id: str, request: Any) -> OperationResult:
        dispatched.append(dict(request.payload))
        return OperationResult(
            ok=True,
            payload={"exit_code": 0, "stdout": "fallback", "stderr": ""},
            errors=(),
        )

    monkeypatch.setattr(registry, "dispatch_operation_for", fake_dispatch)

    exit_code, stdout, stderr = auto._run_planning_phase(
        ["plan", "--plan", "demo"],
        cwd=tmp_path,
        liveness_plan_dir=tmp_path / ".megaplan" / "plans" / "demo",
    )

    assert (exit_code, stdout, stderr) == (0, "fallback", "")
    assert dispatched == [
        {
            "phase": "plan",
            "plan": "demo",
            "cwd": tmp_path,
            "plan_dir": tmp_path / ".megaplan" / "plans" / "demo",
            "argv": ["plan", "--plan", "demo"],
            "progress_env": {},
        }
    ]


def test_run_planning_phase_keeps_override_on_control_dispatch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    override_calls: list[list[str]] = []

    monkeypatch.setattr(
        auto,
        "_run_native_planning_phase",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("override commands are not native phase dispatch")
        ),
    )

    def fake_override(args: list[str], *, cwd: Path | None = None) -> tuple[int, str, str]:
        override_calls.append(list(args))
        return 0, "override", ""

    monkeypatch.setattr(auto, "_run_override_command", fake_override)

    result = auto._run_planning_phase(
        ["override", "force-proceed", "--plan", "demo", "--reason", "test"],
        cwd=tmp_path,
    )

    assert result == (0, "override", "")
    assert override_calls == [
        ["override", "force-proceed", "--plan", "demo", "--reason", "test"]
    ]


def test_builtin_megaplan_registry_supports_override_apply() -> None:
    from arnold_pipelines.megaplan.registry import (
        dispatch_operation_for,
        supported_operations_for,
    )
    from arnold_pipelines.megaplan.runtime.discovery import CANONICAL_BUILTIN_PIPELINE

    supported = supported_operations_for(CANONICAL_BUILTIN_PIPELINE)

    assert OperationKind.OVERRIDE_APPLY in supported
    result = dispatch_operation_for(
        CANONICAL_BUILTIN_PIPELINE,
        OperationRequest(kind=OperationKind.OVERRIDE_APPLY, payload={}),
    )
    assert result.ok is False
    assert result.errors[0] == "invalid_request"
    assert "payload.state" in result.errors[1]


def test_compiled_native_phase_functions_execute_handler_payload(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import arnold_pipelines.megaplan.cli as cli

    seen: list[tuple[Path, argparse.Namespace]] = []

    def fake_execute(root: Path, args: argparse.Namespace) -> dict[str, Any]:
        seen.append((root, args))
        return {"success": True, "step": "execute", "batch": args.batch}

    monkeypatch.setitem(cli.COMMAND_HANDLERS, "execute", fake_execute)
    shell = build_compatibility_shell(build_pipeline())
    assert isinstance(shell.native_program, NativeProgram)
    phase = next(item for item in shell.native_program.phases if item.name == "execute")

    payload = phase.func(
        {
            "__megaplan_auto_phase__": True,
            "cwd": tmp_path,
            "plan": "demo",
            "argv": [
                "execute",
                "--confirm-destructive",
                "--user-approved",
                "--retry-blocked-tasks",
                "--batch",
                "2",
                "--plan",
                "demo",
            ],
        }
    )

    assert payload["exit_code"] == 0
    assert json.loads(payload["stdout"]) == {
        "success": True,
        "step": "execute",
        "batch": 2,
    }
    assert payload["stderr"] == ""
    assert seen[0][0] == tmp_path
    assert seen[0][1].confirm_destructive is True
    assert seen[0][1].user_approved is True
    assert seen[0][1].retry_blocked_tasks is True
    assert seen[0][1].batch == 2


# ── Stable ID dispatch ───────────────────────────────────────────────────


def test_stable_id_resolution_resolves_megaplan_prefixed_ids(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """_resolve_phase_name maps stable IDs to flat phase names."""
    from arnold_pipelines.megaplan.auto import _resolve_phase_name

    assert _resolve_phase_name("megaplan:prep") == "prep"
    assert _resolve_phase_name("megaplan:plan") == "plan"
    assert _resolve_phase_name("megaplan:critique") == "critique"
    assert _resolve_phase_name("megaplan:gate") == "gate"
    assert _resolve_phase_name("megaplan:revise") == "revise"
    assert _resolve_phase_name("megaplan:finalize") == "finalize"
    assert _resolve_phase_name("megaplan:execute") == "execute"
    assert _resolve_phase_name("megaplan:review") == "review"


def test_stable_id_resolution_passes_through_flat_names() -> None:
    """Flat phase names pass through _resolve_phase_name unchanged."""
    from arnold_pipelines.megaplan.auto import _resolve_phase_name

    assert _resolve_phase_name("prep") == "prep"
    assert _resolve_phase_name("plan") == "plan"
    assert _resolve_phase_name("execute") == "execute"


def test_stable_id_resolution_passes_through_unknown() -> None:
    """Unknown strings pass through unchanged."""
    from arnold_pipelines.megaplan.auto import _resolve_phase_name

    assert _resolve_phase_name("override") == "override"
    assert _resolve_phase_name("") == ""


def test_stable_id_resolution_passes_through_non_megaplan_prefixed() -> None:
    """Non-megaplan prefixed IDs pass through unchanged."""
    from arnold_pipelines.megaplan.auto import _resolve_phase_name

    assert _resolve_phase_name("something:prep") == "something:prep"
    assert _resolve_phase_name("other:plan") == "other:plan"


def test_native_planning_phase_accepts_stable_id(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """_run_native_planning_phase accepts stable IDs like 'megaplan:execute'."""
    import arnold_pipelines.megaplan.cli as cli

    seen: list[tuple[Path, object]] = []

    def fake_execute(root: Path, args: object) -> dict[str, Any]:
        seen.append((root, args))
        return {"success": True, "step": "execute"}

    monkeypatch.setitem(cli.COMMAND_HANDLERS, "execute", fake_execute)

    from arnold_pipelines.megaplan.auto import _run_native_planning_phase

    result = _run_native_planning_phase(
        ["megaplan:execute", "--plan", "demo"],
        plan="demo",
        cwd=tmp_path,
        progress_env=None,
        liveness_plan_dir=tmp_path / ".megaplan" / "plans" / "demo",
    )

    assert result is not None
    exit_code, stdout, _stderr = result
    assert exit_code == 0
    assert "execute" in json.loads(stdout)["step"]


def test_phase_names_stable_id_mapping_is_complete() -> None:
    """Every flat phase in PHASE_NAMES has a corresponding stable ID mapping."""
    from arnold_pipelines.megaplan.auto import PHASE_NAMES, _STABLE_ID_TO_PHASE

    resolved_flat_names = set(_STABLE_ID_TO_PHASE.values())
    for phase_name in PHASE_NAMES:
        assert phase_name in resolved_flat_names, (
            f"PHASE_NAME {phase_name!r} has no stable ID mapping"
        )
