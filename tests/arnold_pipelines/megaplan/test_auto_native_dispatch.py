from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arnold.execution.operations import OperationResult
from arnold.pipeline.native.ir import NativeProgram

from arnold_pipelines.megaplan import auto
from arnold_pipelines.megaplan._compatibility import build_compatibility_shell
from arnold_pipelines.megaplan.workflows.planning import build_pipeline


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
