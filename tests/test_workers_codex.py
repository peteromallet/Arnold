"""Direct Codex worker tests for megaplan.workers."""

from __future__ import annotations

import json
import subprocess
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold.pipelines.megaplan.types import CliError
from arnold.pipelines.megaplan.workers import CommandResult, _build_mock_payload, run_codex_prep_step
from tests._workers_helpers import _mock_state, _write_codex_rollout


def test_run_codex_step_passes_effort_flag(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    captured: dict[str, list[str]] = {}

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        captured["command"] = command
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=10,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        run_codex_step(
            "plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True, effort="low",
        )
    invoked_cmd = captured["command"]
    assert "model_reasoning_effort=low" in invoked_cmd
    idx = invoked_cmd.index("model_reasoning_effort=low")
    assert invoked_cmd[idx - 1] == "-c"


def test_run_codex_step_fresh_uses_enforced_render_and_capture_legacy_payload(
    tmp_path: Path,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    observed_tiers: list[str] = []

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(command=command, cwd=tmp_path, returncode=0, stdout="", stderr="", duration_ms=10)

    real_render = __import__(
        "arnold.pipelines.megaplan.workers._impl",
        fromlist=["render_prompt_for_dispatch"],
    ).render_prompt_for_dispatch
    real_capture = __import__(
        "arnold.pipelines.megaplan.workers._impl",
        fromlist=["capture_step_output"],
    ).capture_step_output

    def spy_render(*args, **kwargs):
        observed_tiers.append(kwargs.get("tier").value)
        return real_render(*args, **kwargs)

    def spy_capture(invocation, output):
        observed_tiers.append(invocation.metadata["tier"])
        outcome = real_capture(invocation, output)
        return outcome.__class__(
            contract_result=outcome.contract_result,
            legacy_payload={**dict(outcome.legacy_payload), "plan": "# Captured"},
            telemetry=outcome.telemetry,
        )

    with (
        patch("arnold.pipelines.megaplan.workers._impl.render_prompt_for_dispatch", side_effect=spy_render),
        patch("arnold.pipelines.megaplan.workers._impl.capture_step_output", side_effect=spy_capture),
        patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command),
    ):
        result = run_codex_step("plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert observed_tiers == ["enforced", "enforced"]
    assert result.payload["plan"] == "# Captured"


def test_run_codex_step_execute_resume_uses_non_enforced_render(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    monkeypatch.setenv("MEGAPLAN_CODEX_EXECUTE_PERSIST_SESSION", "1")
    state["sessions"]["codex_executor"] = {"id": "sess-keep"}
    execute_payload = {"task_updates": [], "sense_check_acknowledgments": []}
    observed_tiers: list[str] = []

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_text(json.dumps(execute_payload), encoding="utf-8")
        return CommandResult(command=command, cwd=tmp_path, returncode=0, stdout="", stderr="", duration_ms=10)

    real_render = __import__(
        "arnold.pipelines.megaplan.workers._impl",
        fromlist=["render_prompt_for_dispatch"],
    ).render_prompt_for_dispatch

    def spy_render(*args, **kwargs):
        observed_tiers.append(kwargs.get("tier").value)
        return real_render(*args, **kwargs)

    with (
        patch("arnold.pipelines.megaplan.workers._impl.render_prompt_for_dispatch", side_effect=spy_render),
        patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command),
    ):
        result = run_codex_step("execute", state, plan_dir, root=tmp_path, persistent=True, fresh=False)

    assert observed_tiers == ["non_enforced"]
    assert result.payload == execute_payload


def test_run_codex_step_clamps_spec_layer_max_effort(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    captured: dict[str, list[str]] = {}

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        captured["command"] = command
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=10,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        run_codex_step(
            "plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True, effort="max",
        )
    invoked_cmd = captured["command"]
    assert "model_reasoning_effort=high" in invoked_cmd
    assert "model_reasoning_effort=max" not in invoked_cmd


def test_run_codex_step_rejects_invalid_effort(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    with pytest.raises(CliError, match="Unsupported codex effort level"):
        run_codex_step(
            "plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True, effort="bogus",
        )

def test_run_codex_step_uses_prompt_override_without_builder(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    output_path = tmp_path / "codex-output.json"

    def fake_named_tempfile(*args: object, **kwargs: object):
        class _TempFile:
            name = str(output_path)

            def close(self) -> None:
                return None

        return _TempFile()

    def fake_run_command(*args: object, **kwargs: object) -> CommandResult:
        output_path.write_text(
            json.dumps({"plan": "# Plan", "questions": [], "success_criteria": [{"criterion": "test", "priority": "must"}], "assumptions": []}),
            encoding="utf-8",
        )
        return CommandResult(
            command=["codex"],
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=10,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.create_codex_prompt", side_effect=AssertionError("builder should not run")):
        with patch("arnold.pipelines.megaplan.workers._impl.tempfile.NamedTemporaryFile", side_effect=fake_named_tempfile):
            with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
                run_codex_step(
                    "plan",
                    state,
                    plan_dir,
                    root=tmp_path,
                    persistent=False,
                    prompt_override="custom prompt",
                )

def test_run_step_with_worker_passes_prompt_override(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.types import AgentMode
    from arnold.pipelines.megaplan.workers import run_step_with_worker

    plan_dir, state = _mock_state(tmp_path)
    payload = {"output": "done", "files_changed": [], "commands_run": [], "deviations": [], "task_updates": [], "sense_check_acknowledgments": []}
    am = AgentMode(
        agent="codex",
        mode="persistent",
        refreshed=False,
        model=None,
        effort="medium",
        resolved_model="gpt-5.5",
    )
    with patch(
        "arnold.pipelines.megaplan.workers._impl.run_codex_step",
        return_value=type("Result", (), {"payload": payload, "raw_output": "", "duration_ms": 1, "cost_usd": 0.0, "session_id": "sess", "trace_output": None})(),
    ) as run_codex:
        run_step_with_worker(
            "execute",
            state,
            plan_dir,
            Namespace(agent="codex", ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]),
            root=tmp_path,
            resolved=am,
            prompt_override="custom execute prompt",
        )
    assert run_codex.call_args.kwargs["prompt_override"] == "custom execute prompt"
    # The resolved model + effort must reach run_codex_step. Before the fix
    # (see /tmp/codex_wedge_diagnostic.md), a 4-tuple ``resolved=`` dropped
    # both fields and codex was invoked with model=None / effort=None.
    assert run_codex.call_args.kwargs["model"] == "gpt-5.5"
    assert run_codex.call_args.kwargs["effort"] == "medium"

def test_run_step_with_worker_codex_backstops_resolved_model_from_4tuple(tmp_path: Path) -> None:
    """Regression: 4-tuple ``resolved=`` with model=None used to silently drop
    the resolved default, causing codex to launch without ``-c model=...`` and
    hang at startup. The dispatcher now backstops resolved_model via
    ``resolved_default_model_for_agent`` so codex gets an explicit model.
    """
    from arnold.pipelines.megaplan.workers import run_step_with_worker

    plan_dir, state = _mock_state(tmp_path)
    payload = {"plan": "x", "questions": [], "success_criteria": [{"criterion": "c", "priority": "must"}], "assumptions": []}
    fake_result = type(
        "Result",
        (),
        {
            "payload": payload,
            "raw_output": "",
            "duration_ms": 1,
            "cost_usd": 0.0,
            "session_id": "sess-1",
            "trace_output": None,
        },
    )()
    with patch(
        "arnold.pipelines.megaplan.workers._impl.run_codex_step",
        return_value=fake_result,
    ) as run_codex:
        run_step_with_worker(
            "plan",
            state,
            plan_dir,
            Namespace(agent="codex", ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]),
            root=tmp_path,
            resolved=("codex", "persistent", False, None),
        )
    # Backstop should have filled in the pinned default ("gpt-5.5") so codex
    # never sees model=None.
    assert run_codex.call_args.kwargs["model"] == "gpt-5.5"

def test_run_step_with_worker_codex_asserts_when_backstop_also_fails(tmp_path: Path) -> None:
    """Assert-of-last-resort: if even the default-model backstop returns None
    (e.g. configuration corruption), fail loudly rather than launch codex
    without a model.
    """
    from arnold.pipelines.megaplan.workers import run_step_with_worker

    plan_dir, state = _mock_state(tmp_path)
    with patch(
        "arnold.pipelines.megaplan.workers._impl.resolved_default_model_for_agent",
        return_value=None,
    ):
        with pytest.raises(AssertionError, match="resolved_model"):
            run_step_with_worker(
                "execute",
                state,
                plan_dir,
                Namespace(agent="codex", ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]),
                root=tmp_path,
                resolved=("codex", "persistent", False, None),
                prompt_override="any",
            )

def test_handlers_execute_resolves_codex_model_into_command(tmp_path: Path) -> None:
    """End-to-end (handler -> dispatcher -> _run_and_merge_batch -> worker)
    assertion that the codex command-line carries the resolved model + effort.

    Before the fix, ``handlers/execute.py`` only forwarded ``(agent, mode,
    refreshed, model)`` to the dispatcher and the dispatcher built a 4-tuple
    ``resolved=`` for ``run_step_with_worker``. Both ``effort`` and
    ``resolved_model`` were dropped on that boundary, so codex was invoked
    with no ``-c model='gpt-5.5'`` / ``-c model_reasoning_effort=medium``.
    """
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.types import AgentMode
    from arnold.pipelines.megaplan.workers import CommandResult, run_step_with_worker

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    # parse_agent_spec("codex:medium") returns (agent='codex', model=None,
    # effort='medium'); resolved_default_model_for_agent('codex') then
    # produces 'gpt-5.5'. Simulate that AgentMode here.
    am = AgentMode(
        agent="codex",
        mode="persistent",
        refreshed=True,
        model=None,
        effort="medium",
        resolved_model="gpt-5.5",
    )
    payload = {"plan": "x", "questions": [], "success_criteria": [{"criterion": "c", "priority": "must"}], "assumptions": []}
    fake_result = type(
        "Result",
        (),
        {
            "payload": payload,
            "raw_output": "",
            "duration_ms": 1,
            "cost_usd": 0.0,
            "session_id": "sess-1",
            "trace_output": None,
        },
    )()
    with patch(
        "arnold.pipelines.megaplan.workers._impl.run_codex_step",
        return_value=fake_result,
    ) as run_codex:
        run_step_with_worker(
            "plan",
            state,
            plan_dir,
            Namespace(agent="codex", ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]),
            root=tmp_path,
            resolved=am,
        )
    assert run_codex.call_args.kwargs["model"] == "gpt-5.5"
    assert run_codex.call_args.kwargs["effort"] == "medium"

def test_run_codex_step_emits_model_and_effort_flags(tmp_path: Path) -> None:
    """When ``run_codex_step`` is invoked with an explicit model + effort, the
    resulting codex CLI command must contain both ``-c model='<model>'`` and
    ``-c model_reasoning_effort=<effort>``. The wedge in the diagnostic
    happened because both flags were missing.
    """
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    captured: dict[str, list[str]] = {}

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        captured["command"] = command
        output_idx = command.index("-o") + 1
        Path(command[output_idx]).write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        run_codex_step(
            "plan",
            state,
            plan_dir,
            root=tmp_path,
            persistent=False,
            fresh=True,
            model="gpt-5.5",
            effort="medium",
        )
    cmd = captured["command"]
    # The codex command builder appends both ``-c model='gpt-5.5'`` and
    # ``-c model_reasoning_effort=medium`` (see _impl.py:2231-2234).
    assert "model='gpt-5.5'" in cmd, f"missing model flag in {cmd}"
    assert "model_reasoning_effort=medium" in cmd, f"missing effort flag in {cmd}"

def test_run_codex_step_parses_output_file(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        # Codex writes output to -o file; find the output path in the command
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=300,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "plan",
            state,
            plan_dir,
            root=tmp_path,
            persistent=False,
            fresh=True,
            model="gpt-5.4",
        )
    assert result.payload == plan_payload
    assert result.duration_ms == 300
    assert result.cost_usd == 0.0
    assert result.model_actual == "gpt-5.4"

def test_run_codex_step_reports_schema_validation_error_for_json_payload(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        # Required string key `plan` is omitted — array keys default; the
        # missing string key is what surfaces.
        output_path.write_text(
            json.dumps({"questions": ["?"], "success_criteria": ["ok"], "assumptions": ["x"]}),
            encoding="utf-8",
        )
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=300,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        with pytest.raises(CliError) as exc_info:
            run_codex_step(
                "plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True,
            )

    assert "plan output missing required keys" in exc_info.value.message
    assert "not valid JSON" not in exc_info.value.message

def test_run_codex_step_uses_full_auto_for_critique_template_writes(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    critique_payload = {
        "checks": [
            {
                "id": "correctness",
                "question": "Is the plan correct?",
                "guidance": "",
                "findings": [
                    {
                        "detail": "Checked the plan and found a concrete risk.",
                        "flagged": True,
                    }
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        assert "--full-auto" in command
        add_dir_idx = command.index("--add-dir") + 1
        assert Path(command[add_dir_idx]) == plan_dir
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(critique_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    with patch("arnold.pipelines.megaplan.workers._impl._trusted_container", return_value=False), \
         patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step("critique", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert result.payload == critique_payload

def test_run_codex_step_trusted_container_bypasses_sandbox_for_critique(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", "1")
    critique_payload = {
        "checks": [
            {
                "id": "correctness",
                "question": "Is the plan correct?",
                "guidance": "",
                "findings": [
                    {
                        "detail": "Checked the plan and found no issue in the trusted-container command path.",
                        "flagged": False,
                    }
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        assert "--dangerously-bypass-approvals-and-sandbox" in command
        assert "--full-auto" not in command
        assert not any(str(arg).startswith("sandbox_workspace_write.writable_roots") for arg in command)
        output_idx = command.index("-o") + 1
        Path(command[output_idx]).write_text(json.dumps(critique_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step("critique", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert result.payload == critique_payload

def test_run_codex_step_grants_plan_dir_when_project_dir_differs(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step, set_work_dir_override

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    # Pin the work dir to the plan's project_dir so this test continues to
    # exercise the "grant plan_dir via --add-dir" path without also triggering
    # the worktree warning.
    set_work_dir_override(Path(state["config"]["project_dir"]))
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        cd_idx = command.index("-C") + 1
        add_dir_idx = command.index("--add-dir") + 1
        assert Path(command[cd_idx]) == Path(state["config"]["project_dir"])
        assert Path(command[add_dir_idx]) == plan_dir
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    try:
        with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
            result = run_codex_step("plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True)
    finally:
        set_work_dir_override(None)

    assert result.payload == plan_payload


def test_run_codex_execute_runs_subprocess_in_work_dir(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import run_codex_step
    from arnold.pipelines.megaplan.workers._impl import resolve_work_dir

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    target_dir = resolve_work_dir(state)
    assert target_dir == Path(state["config"]["project_dir"])
    assert target_dir != Path.cwd()
    execute_payload = _build_mock_payload("execute", state, plan_dir, output="done")
    captured: dict[str, object] = {}

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        captured["command"] = command
        captured["cwd"] = kwargs["cwd"]
        output_idx = command.index("-o") + 1
        Path(command[output_idx]).write_text(json.dumps(execute_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=Path(kwargs["cwd"]),
            returncode=0,
            stdout=json.dumps({"type": "thread.started", "thread_id": "execute-session-1"}),
            stderr="",
            duration_ms=1,
        )

    with patch.dict("os.environ", {"MEGAPLAN_CODEX_EXECUTE_PERSIST_SESSION": "1"}), \
         patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "execute",
            state,
            plan_dir,
            root=tmp_path,
            persistent=True,
            fresh=True,
        )

    command = captured["command"]
    assert result.payload == execute_payload
    assert captured["cwd"] == target_dir
    cd_idx = command.index("-C") + 1
    assert Path(command[cd_idx]) == target_dir
    assert Path(command[cd_idx]) != Path.cwd()


def test_run_codex_step_accepts_empty_light_critique_payload(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    critique_payload = {
        "checks": [],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(critique_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step("critique", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert result.payload == critique_payload

def test_run_codex_step_normalizes_revise_payload_missing_changes_summary(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    revise_payload = {
        "plan": "# Revised Plan\nDo it.",
        "flags_addressed": [],
        "assumptions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "questions": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(revise_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step("revise", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert result.payload["changes_summary"] == "No critique flags were raised; refined the plan for execution."

def test_run_codex_step_raises_on_nonzero_exit(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=1,
            stdout="",
            stderr="Something went wrong",
            duration_ms=100,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        with pytest.raises(CliError, match="failed with exit code"):
            run_codex_step(
                "plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True,
            )

def test_run_codex_step_extracts_session_id_from_timeout_output(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    timeout_error = CliError(
        "worker_timeout",
        "Codex timed out",
        extra={"raw_output": '{"type":"thread.started","thread_id":"codex-timeout-session"}\n'},
    )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=timeout_error):
        with pytest.raises(CliError) as exc_info:
            run_codex_step("execute", state, plan_dir, root=tmp_path, persistent=True, fresh=True, json_trace=True)

    assert exc_info.value.extra["session_id"] == "codex-timeout-session"

def test_run_command_decodes_timeout_byte_streams(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.workers import run_command

    timeout_error = subprocess.TimeoutExpired(
        cmd=["codex", "exec", "-"],
        timeout=300,
        output=b'prefix\n```json\n{"checks":[],"flags":[],"verified_flag_ids":[],"disputed_flag_ids":[]}\n```',
        stderr=b"\nextra stderr",
    )

    with patch("arnold.pipelines.megaplan.workers._impl.subprocess.run", side_effect=timeout_error):
        with pytest.raises(CliError) as exc_info:
            run_command(["codex", "exec", "-"], cwd=tmp_path, stdin_text="prompt", timeout=300)

    raw_output = exc_info.value.extra["raw_output"]
    assert isinstance(raw_output, str)
    assert "```json" in raw_output
    assert raw_output.startswith("prefix")
    assert "extra stderr" in raw_output

def test_run_codex_step_recovers_critique_payload_from_timeout_raw_output(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    critique_payload = {
        "checks": [
            {
                "id": "correctness",
                "question": "Is the plan correct?",
                "guidance": "Check the real code.",
                "findings": [
                    {
                        "detail": "Checked the repository path and found missing propagation for shot metadata.",
                        "flagged": True,
                    }
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    timeout_error = CliError(
        "worker_timeout",
        "Codex timed out",
        extra={
            "raw_output": (
                "OpenAI Codex v0.118.0\n"
                '{"type":"thread.started","thread_id":"codex-timeout-session"}\n'
                f"```json\n{json.dumps(critique_payload)}\n```"
            ),
        },
    )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=timeout_error):
        result = run_codex_step("critique", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert result.payload == critique_payload
    assert result.duration_ms == 0
    assert result.cost_usd == 0.0

def test_run_codex_step_recovers_gate_payload_from_mixed_raw_output(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    state["sessions"]["codex_gatekeeper"] = {
        "id": "gate-session-1",
        "created_at": "2026-01-01T00:00:00Z",
        "last_used_at": "2026-01-01T00:00:00Z",
        "mode": "persistent",
        "refreshed": False,
    }
    gate_payload = {
        "recommendation": "PROCEED",
        "rationale": "The revised plan is ready.",
        "signals_assessment": "Score dropped and preflight remains healthy.",
        "warnings": [],
        "settled_decisions": [],
        "flag_resolutions": [
            {
                "flag_id": "FLAG-001",
                "action": "dispute",
                "evidence": "Verified in workers.py: resolve_agent_mode is already the single routing source of truth.",
                "rationale": "",
            }
        ],
        "accepted_tradeoffs": [],
    }
    raw_output = (
        json.dumps(gate_payload)
        + "\nOpenAI Codex v0.118.0 (research preview)\n--------\n"
        + "user\nExtra transcript text with braces later: {not-json}\n"
    )

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=raw_output,
            stderr="",
            duration_ms=25,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "gate",
            state,
            plan_dir,
            root=tmp_path,
            persistent=True,
            fresh=False,
            prompt_override="gate prompt",
        )

    assert result.payload == gate_payload
    assert result.session_id == "gate-session-1"
    assert result.duration_ms == 25

def test_run_codex_step_recovers_execute_payload_from_jsonl_agent_message(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    state["sessions"]["codex_executor"] = {
        "id": "execute-session-1",
        "created_at": "2026-01-01T00:00:00Z",
        "last_used_at": "2026-01-01T00:00:00Z",
        "mode": "persistent",
        "refreshed": False,
    }
    execute_payload = {
        "output": "Implemented batch 2 tasks.",
        "files_changed": ["reigh-worker/source/task_handlers/queue/task_queue.py"],
        "commands_run": ["pytest tests/test_workers.py -k jsonl_agent_message"],
        "deviations": [],
        "task_updates": [
            {
                "task_id": "T6",
                "status": "done",
                "executor_notes": "Recovered from Codex JSONL agent message output.",
                "files_changed": ["reigh-worker/source/task_handlers/queue/task_queue.py"],
                "commands_run": ["pytest tests/test_workers.py -k jsonl_agent_message"],
            }
        ],
        "sense_check_acknowledgments": [
            {"sense_check_id": "SC6", "executor_note": "Confirmed."}
        ],
    }
    raw_output = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "execute-session-1"}),
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item_0",
                        "type": "agent_message",
                        "text": json.dumps(execute_payload),
                    },
                }
            ),
            json.dumps({"type": "turn.completed"}),
        ]
    )

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text("{not-json}", encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=raw_output,
            stderr="",
            duration_ms=25,
        )

    with patch.dict("os.environ", {"MEGAPLAN_CODEX_EXECUTE_PERSIST_SESSION": "1"}), \
         patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "execute",
            state,
            plan_dir,
            root=tmp_path,
            persistent=True,
            fresh=False,
            json_trace=True,
            prompt_override="execute prompt",
        )

    assert result.payload == execute_payload
    assert result.session_id == "execute-session-1"
    assert result.trace_output == raw_output
    assert result.duration_ms == 25

def test_run_codex_step_recovers_execute_batch_payload_from_jsonl_agent_message(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    state["sessions"]["codex_executor"] = {
        "id": "execute-session-2",
        "created_at": "2026-01-01T00:00:00Z",
        "last_used_at": "2026-01-01T00:00:00Z",
        "mode": "persistent",
        "refreshed": False,
    }
    execute_payload = {
        "task_updates": [
            {
                "task_id": "T8",
                "status": "done",
                "executor_notes": "Recovered batch payload from Codex JSONL agent message output.",
                "files_changed": ["reigh-worker/tests/test_preview_harness.py"],
                "commands_run": ["pytest tests/test_preview_harness.py -v"],
            }
        ],
        "sense_check_acknowledgments": [
            {"sense_check_id": "SC8", "executor_note": "Confirmed."}
        ],
    }
    raw_output = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "execute-session-2"}),
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item_0",
                        "type": "agent_message",
                        "text": json.dumps(execute_payload),
                    },
                }
            ),
            json.dumps({"type": "turn.completed"}),
        ]
    )

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text("{not-json}", encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=raw_output,
            stderr="",
            duration_ms=25,
        )

    with patch.dict("os.environ", {"MEGAPLAN_CODEX_EXECUTE_PERSIST_SESSION": "1"}), \
         patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "execute",
            state,
            plan_dir,
            root=tmp_path,
            persistent=True,
            fresh=False,
            json_trace=True,
            prompt_override="Only produce `task_updates` for these tasks: [T8]",
        )

    assert result.payload == execute_payload
    assert result.session_id == "execute-session-2"
    assert result.trace_output == raw_output
    assert result.duration_ms == 25

def test_run_codex_step_execute_resume_omits_add_dir_for_current_codex_cli(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    state["sessions"]["codex_executor"] = {
        "id": "execute-session-2",
        "created_at": "2026-01-01T00:00:00Z",
        "last_used_at": "2026-01-01T00:00:00Z",
        "mode": "persistent",
        "refreshed": False,
    }
    execute_payload = _build_mock_payload("execute", state, plan_dir, output="done")

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        assert command[:3] == ["codex", "exec", "resume"]
        assert "--add-dir" not in command
        assert "--skip-git-repo-check" in command
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(execute_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=12,
        )

    with patch.dict("os.environ", {"MEGAPLAN_CODEX_EXECUTE_PERSIST_SESSION": "1"}), \
         patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "execute",
            state,
            plan_dir,
            root=tmp_path,
            persistent=True,
            fresh=False,
            prompt_override="execute prompt",
        )

    assert result.payload == execute_payload
    assert result.session_id == "execute-session-2"
    assert result.duration_ms == 12


def test_run_codex_step_execute_defaults_to_fresh_session(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    state["sessions"]["codex_executor"] = {
        "id": "execute-session-2",
        "created_at": "2026-01-01T00:00:00Z",
        "last_used_at": "2026-01-01T00:00:00Z",
        "mode": "persistent",
        "refreshed": False,
    }
    execute_payload = _build_mock_payload("execute", state, plan_dir, output="done")

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        assert command[:3] == ["codex", "exec", "--skip-git-repo-check"]
        assert "resume" not in command
        assert "--add-dir" in command
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(execute_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout='{"type":"thread.started","thread_id":"execute-session-fresh"}\n',
            stderr="",
            duration_ms=12,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "execute",
            state,
            plan_dir,
            root=tmp_path,
            persistent=True,
            fresh=False,
            prompt_override="execute prompt",
        )

    assert result.payload == execute_payload
    assert result.session_id == "execute-session-fresh"
    assert "codex_executor" not in state["sessions"]


def test_diagnose_codex_failure_prefers_connection_errors_over_thread_id_numbers() -> None:
    from arnold.pipelines.megaplan.workers import _diagnose_codex_failure

    raw = (
        "thread 'reqwest-internal-sync-runtime' (42967821) panicked\n"
        "failed to connect to websocket: IO error: failed to lookup address information: "
        "nodename nor servname provided, or not known\n"
        "stream disconnected before completion: error sending request for url "
        "(https://chatgpt.com/backend-api/codex/responses)\n"
    )

    code, message = _diagnose_codex_failure(raw, 1)

    assert code == "connection_error"
    assert "connect" in message.lower() or "resolve" in message.lower()

def test_diagnose_codex_failure_detects_real_http_429() -> None:
    from arnold.pipelines.megaplan.workers import _diagnose_codex_failure

    code, message = _diagnose_codex_failure("request failed with HTTP 429 rate limit exceeded", 1)

    assert code == "rate_limit"
    assert "rate limit" in message.lower()

def test_diagnose_codex_failure_detects_usage_limit() -> None:
    from arnold.pipelines.megaplan.workers import _diagnose_codex_failure

    raw = (
        "{\"type\":\"error\",\"message\":\"You've hit your usage limit. "
        "Visit https://chatgpt.com/codex/settings/usage to purchase more credits "
        "or try again at 12:37 AM.\"}"
    )

    code, message = _diagnose_codex_failure(raw, 1)

    assert code == "quota_exceeded"
    assert "usage limit" in message.lower()

def test_run_codex_step_classifies_nonzero_json_trace_usage_limit(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        out_path = Path(command[command.index("-o") + 1])
        raw = (
            "{\"type\":\"error\",\"message\":\"You've hit your usage limit. "
            "Visit https://chatgpt.com/codex/settings/usage to purchase more credits "
            "or try again at 12:37 AM.\"}\n"
            "{\"type\":\"turn.failed\",\"error\":{\"message\":\"You've hit your usage limit.\"}}\n"
        )
        out_path.write_text(raw, encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=1,
            stdout=raw,
            stderr="",
            duration_ms=100,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        with pytest.raises(CliError) as exc_info:
            run_codex_step(
                "plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True,
            )

    assert exc_info.value.code == "quota_exceeded"
    assert "usage limit" in str(exc_info.value).lower()

def test_run_codex_step_uses_step_timeout_for_plan(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        assert kwargs["timeout"] == 900
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step("plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert result.payload == plan_payload

def test_run_codex_step_reclassifies_timeout_connection_errors(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    timeout_error = CliError(
        "worker_timeout",
        "Codex timed out",
        extra={"raw_output": "failed to connect to websocket: failed to lookup address information"},
    )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=timeout_error):
        with pytest.raises(CliError) as exc_info:
            run_codex_step("plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert exc_info.value.code == "connection_error"
    assert "connect" in exc_info.value.message.lower() or "resolve" in exc_info.value.message.lower()
    assert "--agent claude" not in exc_info.value.message

def test_run_codex_step_timeout_guidance_prefers_same_step_retry(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    timeout_error = CliError(
        "worker_timeout",
        "Codex timed out",
        extra={"raw_output": ""},
    )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=timeout_error):
        with pytest.raises(CliError) as exc_info:
            run_codex_step("plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert exc_info.value.code == "worker_timeout"
    assert "re-run the same step on codex once" in exc_info.value.message.lower()
    assert "--agent claude" not in exc_info.value.message

def test_run_step_with_worker_retries_non_execute_codex_timeout_once(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import WorkerResult, run_step_with_worker

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    timeout_error = CliError(
        "worker_timeout",
        "Codex timed out",
        extra={"raw_output": "", "session_id": "retry-session"},
    )
    worker = WorkerResult(
        payload=payload,
        raw_output="",
        duration_ms=1,
        cost_usd=0.0,
        session_id="retry-session",
    )

    with patch("arnold.pipelines.megaplan.workers._impl.run_codex_step", side_effect=[timeout_error, worker]) as mocked:
        result, agent, mode, refreshed = run_step_with_worker(
            "plan",
            state,
            plan_dir,
            Namespace(agent="codex", ephemeral=False, fresh=False, persist=False, model=None),
            root=tmp_path,
        )

    assert mocked.call_count == 2
    assert result == worker
    assert agent == "codex"
    assert mode == "persistent"
    assert refreshed is True
    import hashlib

    expected_key = "codex_planner_" + hashlib.sha256("gpt-5.5".encode()).hexdigest()[:8]
    assert state["sessions"][expected_key]["id"] == "retry-session"

def test_run_step_with_worker_does_not_retry_execute_codex_timeout(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import run_step_with_worker

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    timeout_error = CliError(
        "worker_timeout",
        "Codex timed out",
        extra={"raw_output": "", "session_id": "execute-session"},
    )

    with patch("arnold.pipelines.megaplan.workers._impl.run_codex_step", side_effect=timeout_error) as mocked:
        with pytest.raises(CliError) as exc_info:
            run_step_with_worker(
                "execute",
                state,
                plan_dir,
                Namespace(agent="codex", ephemeral=False, fresh=False, persist=False, model=None),
                root=tmp_path,
            )

    assert mocked.call_count == 1
    assert exc_info.value.code == "worker_timeout"

def test_run_step_with_worker_does_not_fallback_for_explicit_agent_runtime_error(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.workers import run_step_with_worker

    plan_dir, state = _mock_state(tmp_path)
    args = Namespace(agent="codex", ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[])
    connection_error = CliError(
        "connection_error",
        "Codex could not resolve the backend host. Re-run the same step on Codex once before changing agent.",
        extra={"raw_output": "failed to lookup address information"},
    )

    with patch("arnold.pipelines.megaplan.workers._impl.resolve_agent_mode", return_value=("codex", "persistent", False, None)):
        with patch("arnold.pipelines.megaplan.workers._impl.run_codex_step", side_effect=connection_error) as mocked_codex:
            with pytest.raises(CliError) as exc_info:
                run_step_with_worker(
                    "plan",
                    state,
                    plan_dir,
                    args,
                    root=tmp_path,
                )

    assert mocked_codex.call_count == 2
    assert exc_info.value.code == "connection_error"
    assert not hasattr(args, "_agent_fallback")

def test_run_codex_step_sanitizes_codex_child_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    monkeypatch.setenv("CODEX_THREAD_ID", "outer-thread")
    monkeypatch.setenv("CODEX_CI", "1")
    monkeypatch.setenv("CODEX_MANAGED_BY_NPM", "1")

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        env = kwargs["env"]
        assert isinstance(env, dict)
        assert "CODEX_THREAD_ID" not in env
        assert "CODEX_CI" not in env
        assert env["CODEX_MANAGED_BY_NPM"] == "1"
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step("plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert result.payload == plan_payload

def test_is_poisoned_environmental_failure_matches_bwrap_namespace_error() -> None:
    from arnold.pipelines.megaplan.workers import _is_poisoned_environmental_failure

    raw = "something happened\nbwrap: Creating new namespace failed: Permission denied\nmore"
    assert _is_poisoned_environmental_failure(raw) is True

def test_is_poisoned_environmental_failure_matches_permission_denied_sandbox() -> None:
    from arnold.pipelines.megaplan.workers import _is_poisoned_environmental_failure

    raw = "error: Permission denied while trying to start the sandbox. cannot start sandbox."
    assert _is_poisoned_environmental_failure(raw) is True

def test_is_poisoned_environmental_failure_matches_repo_cmd_unavailable_sandbox() -> None:
    from arnold.pipelines.megaplan.workers import _is_poisoned_environmental_failure

    raw = (
        "Repository command execution is currently unavailable because the sandbox "
        "could not be initialized."
    )
    assert _is_poisoned_environmental_failure(raw) is True

def test_is_poisoned_environmental_failure_ignores_unrelated_errors() -> None:
    from arnold.pipelines.megaplan.workers import _is_poisoned_environmental_failure

    assert _is_poisoned_environmental_failure("") is False
    assert _is_poisoned_environmental_failure("TypeError: foo is not callable") is False
    # A lone "Permission denied" without sandbox context must not trip patterns.
    assert _is_poisoned_environmental_failure("Permission denied: /root/.cache") is False

def test_is_session_too_large_for_compact_matches_real_codex_error() -> None:
    from arnold.pipelines.megaplan.workers import _is_session_too_large_for_compact

    raw = (
        '{"type":"error","message":"Error running remote compact task: '
        'exceeded retry limit, last status: 429 Too Many Requests, '
        'request id: req_e45c8eddc3204adbb0ce791f23557be9"}'
    )
    assert _is_session_too_large_for_compact(raw) is True

def test_is_session_too_large_for_compact_ignores_unrelated_errors() -> None:
    from arnold.pipelines.megaplan.workers import _is_session_too_large_for_compact

    assert _is_session_too_large_for_compact("") is False
    # 429 alone (without remote-compact context) is generic rate limiting.
    assert _is_session_too_large_for_compact("429 Too Many Requests on /chat") is False
    # remote compact mention without 429 is not the failure mode.
    assert _is_session_too_large_for_compact("remote compact task succeeded") is False

def test_run_codex_step_resumed_session_retries_fresh_on_poisoned_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resumed Codex session whose output contains a stale bwrap failure line
    should cause run_codex_step to drop the session id and recursively
    re-invoke itself with fresh=True."""
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    state["sessions"] = {
        "codex_executor": {
            "id": "sess-poisoned",
            "mode": "persistent",
            "created_at": "2026-04-15T00:00:00Z",
            "last_used_at": "2026-04-15T00:00:00Z",
            "refreshed": False,
        }
    }
    monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", "1")

    poisoned_raw = (
        "bwrap: Creating new namespace failed: Permission denied\n"
        "cannot continue\n"
    )
    call_counter = {"n": 0}

    def fake_run_command(command, **kwargs):
        call_counter["n"] += 1
        if call_counter["n"] == 1:
            return CommandResult(
                command=command,
                cwd=tmp_path,
                returncode=1,
                stdout="",
                stderr=poisoned_raw,
                duration_ms=5,
            )
        out_idx = command.index("-o") + 1
        output_path = Path(command[out_idx])
        payload = {
            "output": "done",
            "files_changed": [],
            "commands_run": [],
            "deviations": [],
            "task_updates": [],
            "sense_check_acknowledgments": [],
        }
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=json.dumps({"type": "thread.started", "thread_id": "sess-fresh"}) + "\n",
            stderr="",
            duration_ms=5,
        )

    with patch.dict("os.environ", {"MEGAPLAN_CODEX_EXECUTE_PERSIST_SESSION": "1"}), \
         patch("arnold.pipelines.megaplan.workers._impl.create_codex_prompt", return_value="prompt"), \
         patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
            result = run_codex_step(
                "execute",
                state,
                plan_dir,
                root=tmp_path,
                persistent=True,
                fresh=False,
            )

    assert call_counter["n"] == 2
    assert result.payload.get("output") == "done"
    assert result.session_id == "sess-fresh"
    # Stale session id must have been dropped from state before the recursive
    # call; the new session id is installed by the caller (apply_session_update).
    assert state["sessions"].get("codex_executor", {}).get("id") != "sess-poisoned"

def test_run_codex_step_skips_poison_retry_when_fresh_already(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With fresh=True the poisoned-session branch must not engage."""
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", "1")
    monkeypatch.setenv("MEGAPLAN_CODEX_EXECUTE_PERSIST_SESSION", "1")

    poisoned_raw = "bwrap: Creating new namespace failed: Permission denied\n"

    def fake_run_command(command, **kwargs):
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=1,
            stdout="",
            stderr=poisoned_raw,
            duration_ms=1,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.create_codex_prompt", return_value="prompt"):
        with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
            with pytest.raises(CliError):
                run_codex_step(
                    "execute",
                    state,
                    plan_dir,
                    root=tmp_path,
                    persistent=False,
                    fresh=True,
                )

def test_codex_pricing_table() -> None:
    from arnold.pipelines.megaplan.pricing.codex import (
        DEFAULT_MODEL,
        PRICING,
        cost_from_codex_usage_dict,
        cost_from_usage,
    )

    # Spec example: 66607 in (4864 cached), 1089 out, 230 reasoning -> $0.350717
    usage = {
        "input_tokens": 66607,
        "cached_input_tokens": 4864,
        "output_tokens": 1089,
        "reasoning_output_tokens": 230,
    }
    expected = (
        (66607 - 4864) * 5.00
        + 4864 * 0.50
        + (1089 + 230) * 30.00
    ) / 1_000_000
    # Dict-form helper preserves the old API for callers with the raw blob.
    assert cost_from_codex_usage_dict(usage, "gpt-5.5") == pytest.approx(expected)
    # Unknown model falls back to default rates.
    assert cost_from_codex_usage_dict(usage, "totally-made-up") == pytest.approx(expected)
    # Default model resolves the same way.
    assert DEFAULT_MODEL in PRICING
    assert cost_from_codex_usage_dict(usage) == pytest.approx(expected)
    # Empty / None usage -> 0.
    assert cost_from_codex_usage_dict(None) == 0.0
    assert cost_from_codex_usage_dict({}) == 0.0
    # gpt-5 cheaper rates apply.
    cheap = cost_from_codex_usage_dict(usage, "gpt-5")
    assert 0 < cheap < expected

    # Unified signature matches claude/fireworks shape.
    via_unified = cost_from_usage(
        prompt_tokens=66607,
        completion_tokens=1089 + 230,
        model="gpt-5.5",
        cached_prompt_tokens=4864,
    )
    assert via_unified == pytest.approx(expected)
    # Defaults: no cached tokens, unknown model falls back to default rate.
    assert cost_from_usage(0, 0, None) == 0.0
    assert cost_from_usage(1_000_000, 0, "gpt-5.5") == pytest.approx(5.0)

def test_codex_step_extracts_token_usage_from_session_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)

    codex_home = tmp_path / "codex_home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    session_id = "019df78d-2a47-7981-a7d1-fadf79f5b240"
    total_usage = {
        "input_tokens": 66607,
        "cached_input_tokens": 4864,
        "output_tokens": 1089,
        "reasoning_output_tokens": 230,
        "total_tokens": 67696,
    }
    _write_codex_rollout(codex_home, session_id, total_usage)

    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        Path(command[output_idx]).write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=f'{{"type":"thread.started","thread_id":"{session_id}"}}\n',
            stderr="",
            duration_ms=300,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "plan", state, plan_dir, root=tmp_path, persistent=True, fresh=True,
        )

    expected_cost = (
        (66607 - 4864) * 5.00
        + 4864 * 0.50
        + (1089 + 230) * 30.00
    ) / 1_000_000
    assert result.cost_usd == pytest.approx(expected_cost)
    assert result.prompt_tokens == 66607
    assert result.completion_tokens == 1089 + 230
    assert result.total_tokens == 66607 + 1089 + 230
    assert result.session_id == session_id

def test_codex_step_handles_missing_session_jsonl_gracefully(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)

    # Point CODEX_HOME at an empty dir so no rollout matches.
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "empty_codex_home"))

    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        Path(command[output_idx]).write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout='{"type":"thread.started","thread_id":"abc-1234-no-rollout"}\n',
            stderr="",
            duration_ms=300,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "plan", state, plan_dir, root=tmp_path, persistent=True, fresh=True,
        )

    assert result.cost_usd == 0.0
    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0
    captured = capsys.readouterr()
    assert "Could not locate codex rollout" in captured.out

def test_codex_step_incremental_cost_within_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)

    codex_home = tmp_path / "codex_home2"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    session_id = "session-incr-0001"
    # First step: cumulative totals after step 1.
    first_total = {
        "input_tokens": 1000,
        "cached_input_tokens": 0,
        "output_tokens": 500,
        "reasoning_output_tokens": 0,
        "total_tokens": 1500,
    }
    rollout_path = _write_codex_rollout(codex_home, session_id, first_total)

    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        Path(command[output_idx]).write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=f'{{"type":"thread.started","thread_id":"{session_id}"}}\n',
            stderr="",
            duration_ms=200,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        first = run_codex_step(
            "plan", state, plan_dir, root=tmp_path, persistent=True, fresh=True,
        )

    expected_first = (1000 * 5.00 + 500 * 30.00) / 1_000_000
    assert first.cost_usd == pytest.approx(expected_first)
    # Session entry should now carry the running totals.
    session_key = "codex_planner"
    assert state["sessions"][session_key]["last_total_tokens"]["input_tokens"] == 1000

    # Second step: rollout grows. Rewrite the file with a larger cumulative.
    second_total = {
        "input_tokens": 3000,
        "cached_input_tokens": 200,
        "output_tokens": 1500,
        "reasoning_output_tokens": 100,
        "total_tokens": 4600,
    }
    rollout_path.unlink()
    _write_codex_rollout(codex_home, session_id, second_total)

    # Pre-seed session id so the second call resumes (mirroring real flow).
    state["sessions"][session_key]["id"] = session_id

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        second = run_codex_step(
            "plan", state, plan_dir, root=tmp_path, persistent=True, fresh=False,
        )

    delta_input = 3000 - 1000  # 2000 new input tokens
    delta_cached = 200  # all new
    delta_full_input = delta_input - delta_cached  # 1800
    delta_output = (1500 + 100) - (500 + 0)  # 1100
    expected_second = (
        delta_full_input * 5.00 + delta_cached * 0.50 + delta_output * 30.00
    ) / 1_000_000
    assert second.cost_usd == pytest.approx(expected_second)
    # Cumulative bookkeeping advanced.
    assert state["sessions"][session_key]["last_total_tokens"]["input_tokens"] == 3000

def test_codex_fresh_step_accounts_against_new_session_not_stored_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)

    codex_home = tmp_path / "codex_home_fresh"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    old_session = "old-review-session"
    new_session = "new-review-session"
    state["sessions"]["codex_planner"] = {"id": old_session}
    _write_codex_rollout(
        codex_home,
        old_session,
        {
            "input_tokens": 900000,
            "cached_input_tokens": 0,
            "output_tokens": 90000,
            "reasoning_output_tokens": 0,
            "total_tokens": 990000,
        },
    )
    _write_codex_rollout(
        codex_home,
        new_session,
        {
            "input_tokens": 1000,
            "cached_input_tokens": 0,
            "output_tokens": 100,
            "reasoning_output_tokens": 0,
            "total_tokens": 1100,
        },
    )
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        Path(command[output_idx]).write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=f'{{"type":"thread.started","thread_id":"{new_session}"}}\n',
            stderr="",
            duration_ms=200,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "plan",
            state,
            plan_dir,
            root=tmp_path,
            persistent=True,
            fresh=True,
        )

    assert result.session_id == new_session
    assert result.prompt_tokens == 1000
    assert result.completion_tokens == 100
    assert state["sessions"]["codex_planner"]["id"] == new_session
    assert state["sessions"]["codex_planner"]["last_total_tokens"]["input_tokens"] == 1000

def test_codex_execute_headroom_guard_forces_fresh_before_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    monkeypatch.setenv("MEGAPLAN_CODEX_EXECUTOR_SESSION_HEADROOM_TOKENS", "1000")
    state["sessions"]["codex_executor"] = {
        "id": "old-execute-session",
        "created_at": "2026-01-01T00:00:00Z",
        "last_used_at": "2026-01-01T00:00:00Z",
        "mode": "persistent",
        "refreshed": False,
        "last_total_tokens": {"total_tokens": 1001},
    }
    execute_payload = {
        "output": "Implemented the batch.",
        "files_changed": ["src/example.py"],
        "commands_run": ["pytest tests/test_workers.py"],
        "deviations": [],
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "Done.",
                "files_changed": ["src/example.py"],
                "commands_run": ["pytest tests/test_workers.py"],
            }
        ],
        "sense_check_acknowledgments": [],
    }
    commands: list[list[str]] = []

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        del kwargs
        commands.append(command)
        output_idx = command.index("-o") + 1
        Path(command[output_idx]).write_text(json.dumps(execute_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout='{"type":"thread.started","thread_id":"new-execute-session"}\n',
            stderr="",
            duration_ms=25,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "execute",
            state,
            plan_dir,
            root=tmp_path,
            persistent=True,
            fresh=False,
            json_trace=True,
            prompt_override="execute prompt",
        )

    assert result.session_id == "new-execute-session"
    assert commands
    assert commands[0][:3] == ["codex", "exec", "--skip-git-repo-check"]
    assert "resume" not in commands[0]
    assert "old-execute-session" not in commands[0]

def test_run_codex_prep_step_uses_readonly_command_without_write_grants(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    payload = {"triage_framing": "No fanout needed.", "areas": []}
    commands: list[list[str]] = []

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        commands.append(command)
        output_idx = command.index("-o") + 1
        Path(command[output_idx]).write_text(json.dumps(payload), encoding="utf-8")
        return CommandResult(command=command, cwd=tmp_path, returncode=0, stdout="", stderr="", duration_ms=12)

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_prep_step(
            "prep-triage",
            state,
            plan_dir,
            root=tmp_path,
            prompt_override="triage prompt",
            model="gpt-5.5",
        )

    command = commands[0]
    assert result.payload == payload
    assert "--ephemeral" in command
    assert "sandbox_mode='read-only'" in command
    assert "--add-dir" not in command
    assert "-C" not in command
    assert "--full-auto" not in command
    assert "--dangerously-bypass-approvals-and-sandbox" not in command
    assert not any("writable_roots" in part for part in command)

def test_apply_session_update_preserves_codex_last_total_tokens_after_worker_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan._core.state import apply_session_update
    from arnold.pipelines.megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)

    codex_home = tmp_path / "codex_home_apply"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    session_id = "session-apply-0001"
    _write_codex_rollout(
        codex_home,
        session_id,
        {
            "input_tokens": 1000,
            "cached_input_tokens": 0,
            "output_tokens": 100,
            "reasoning_output_tokens": 0,
            "total_tokens": 1100,
        },
    )
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        Path(command[output_idx]).write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=f'{{"type":"thread.started","thread_id":"{session_id}"}}\n',
            stderr="",
            duration_ms=200,
        )

    with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "plan",
            state,
            plan_dir,
            root=tmp_path,
            persistent=True,
            fresh=True,
        )

    apply_session_update(
        state,
        "plan",
        "codex",
        result.session_id,
        mode="persistent",
        refreshed=True,
    )
    assert state["sessions"]["codex_planner"]["last_total_tokens"]["input_tokens"] == 1000


# ---------------------------------------------------------------------------
# Codex-model dispatch guard (specfix)
# ---------------------------------------------------------------------------


def test_codex_model_flag_accepts_valid_models() -> None:
    """Recognised codex/GPT-5.x models build a clean -c model='...' flag."""
    from arnold.pipelines.megaplan.workers._impl import _codex_model_flag

    assert _codex_model_flag(None) == []
    assert _codex_model_flag("gpt-5.5") == ["-c", "model='gpt-5.5'"]
    assert _codex_model_flag("gpt-5.3-codex") == ["-c", "model='gpt-5.3-codex'"]
    assert _codex_model_flag("gpt-5.1-codex-max") == ["-c", "model='gpt-5.1-codex-max'"]


@pytest.mark.parametrize("bad_model", ["claude", "claude-sonnet-4-6", "sonnet", "deepseek-v4-pro"])
def test_codex_model_flag_rejects_non_codex_models(bad_model: str) -> None:
    """A non-codex model (e.g. from a malformed 'codex:claude:sonnet' spec) must
    never be passed verbatim to the codex CLI as -c model='...'."""
    from arnold.pipelines.megaplan.workers._impl import _codex_model_flag

    with pytest.raises(CliError) as exc:
        _codex_model_flag(bad_model)
    assert exc.value.code == "invalid_codex_model"
    assert bad_model in str(exc.value)
