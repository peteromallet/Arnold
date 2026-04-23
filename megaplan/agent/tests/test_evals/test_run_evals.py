import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

from evals.audit import EvalAudit
from evals.benchmarks import VerifyResult
from evals.config import EvalConfig
from evals.run_evals import (
    _diagnose_verify_failure,
    _inject_feedback,
    _inject_verify_feedback,
    prepare_workspace,
    run_megaplan_loop,
    _session_key_for,
)


def _hybrid_runner(command: list[str], cwd: Path, timeout_seconds: int | None):
    if command[0] == "npm":
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


class FakeMegaplanRunner:
    def __init__(self, workspace: Path, config: EvalConfig, gate_recommendations: list[str]):
        self.workspace = workspace
        self.config = config
        self.gate_recommendations = list(gate_recommendations)
        self.plan_dir: Path | None = None
        self.sessions: dict[str, dict[str, str]] = {}

    def __call__(self, command, cwd, timeout_seconds, env):
        phase = command[1]
        if phase == "init":
            return self._handle_init(command), json.dumps({"success": True})
        return self._handle_phase(phase), json.dumps({"success": True})

    def _handle_init(self, command):
        plan_name = command[command.index("--name") + 1]
        self.plan_dir = self.workspace / ".megaplan" / "plans" / plan_name
        self.plan_dir.mkdir(parents=True, exist_ok=True)
        self.sessions = {
            _session_key_for("prep", "hermes", self.config.models["prep"]): {"id": "prepper"},
            _session_key_for("plan", "hermes", self.config.models["plan"]): {"id": "planner"},
            _session_key_for("research", "hermes", self.config.models["research"]): {"id": "researcher"},
            _session_key_for("critique", "hermes", self.config.models["critique"]): {"id": "critic"},
            _session_key_for("gate", "hermes", self.config.models["gate"]): {"id": "gate"},
            _session_key_for("finalize", "hermes", self.config.models["finalize"]): {"id": "finalizer"},
            _session_key_for("execute", "hermes", self.config.models["execute"]): {"id": "executor"},
            _session_key_for("review", "hermes", self.config.models["review"]): {"id": "reviewer"},
        }
        for entry in self.sessions.values():
            self._write_session(entry["id"], [])
        self._write_state({"current_state": "planning", "iteration": 1, "sessions": self.sessions, "history": []})
        return {"success": True}

    def _handle_phase(self, phase: str):
        assert self.plan_dir is not None
        state = self._read_state()
        iteration = int(state.get("iteration", 1) or 1)
        history = list(state.get("history", []))
        session_id = self._session_id_for_phase(phase)
        messages = self._read_session(session_id)
        message = {"role": "assistant", "content": f"{phase}-{iteration}"}
        self._write_session(session_id, [*messages, message])
        history.append(
            {
                "step": phase,
                "duration_ms": 100,
                "cost_usd": 0.01,
                "session_id": session_id,
            }
        )
        state["history"] = history

        response = {"success": True}
        if phase == "prep":
            self._write_json(self.plan_dir / "prep.json", {"skip": False, "task_summary": "ready"})
        elif phase == "plan":
            self._write_json(self.plan_dir / f"plan_v{iteration}.meta.json", {"phase": phase})
            (self.plan_dir / f"plan_v{iteration}.md").write_text("plan\n", encoding="utf-8")
        elif phase == "research":
            self._write_json(self.plan_dir / "research.json", {"considerations": [], "summary": "ok"})
        elif phase == "critique":
            self._write_json(self.plan_dir / f"critique_v{iteration}.json", {"phase": phase})
        elif phase == "gate":
            recommendation = self.gate_recommendations.pop(0)
            response["recommendation"] = recommendation
            self._write_json(self.plan_dir / "gate.json", {"recommendation": recommendation})
            self._write_json(
                self.plan_dir / f"gate_signals_v{iteration}.json",
                {"recommendation": recommendation},
            )
        elif phase == "revise":
            iteration += 1
            state["iteration"] = iteration
            (self.plan_dir / f"plan_v{iteration}.md").write_text("revised plan\n", encoding="utf-8")
            self._write_json(self.plan_dir / f"plan_v{iteration}.meta.json", {"phase": phase})
        elif phase == "finalize":
            self._write_json(self.plan_dir / "finalize.json", {"phase": phase})
        elif phase == "execute":
            self._write_json(self.plan_dir / "execution.json", {"phase": phase})
        elif phase == "review":
            self._write_json(self.plan_dir / "review.json", {"phase": phase})

        self._write_state(state)
        return response

    def _session_id_for_phase(self, phase: str) -> str:
        model = self.config.models[phase]
        if phase == "revise":
            key = _session_key_for("plan", "hermes", self.config.models["plan"])
        else:
            key = _session_key_for(phase, "hermes", model)
        return self.sessions[key]["id"]

    def _state_path(self) -> Path:
        assert self.plan_dir is not None
        return self.plan_dir / "state.json"

    def _read_state(self) -> dict:
        return json.loads(self._state_path().read_text(encoding="utf-8"))

    def _write_state(self, payload: dict) -> None:
        self._write_json(self._state_path(), payload)

    def _read_session(self, session_id: str) -> list[dict]:
        path = Path(os.environ["HERMES_HOME"]) / "sessions" / f"session_{session_id}.json"
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("messages", [])

    def _write_session(self, session_id: str, messages: list[dict]) -> None:
        path = Path(os.environ["HERMES_HOME"]) / "sessions" / f"session_{session_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(path, {"session_id": session_id, "messages": messages})

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")


class VerifyPathMegaplanRunner(FakeMegaplanRunner):
    def _handle_phase(self, phase: str):
        response = super()._handle_phase(phase)
        state = self._read_state()
        if phase in {"finalize", "execute"}:
            state["current_state"] = "finalized"
        elif phase == "review":
            state["current_state"] = "done"
        self._write_state(state)
        return response


def _make_eval_config() -> EvalConfig:
    return EvalConfig(
        models={
            "prep": "prep-model",
            "plan": "plan-model",
            "research": "research-model",
            "critique": "critique-model",
            "revise": "plan-model",
            "gate": "gate-model",
            "finalize": "finalize-model",
            "execute": "execute-model",
            "review": "review-model",
        }
    )


def test_prepare_workspace_creates_git_repo_and_returns_initial_commit_sha(tmp_path):
    eval_dir = tmp_path / "source-eval"
    eval_dir.mkdir()
    (eval_dir / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    (eval_dir / "PROMPT.md").write_text("demo prompt\n", encoding="utf-8")
    (eval_dir / "index.ts").write_text("export const value = 1;\n", encoding="utf-8")

    prepared = prepare_workspace(eval_dir, tmp_path / "workspaces", runner=_hybrid_runner)

    repo_path = Path(prepared.path)
    assert (repo_path / ".git").exists()
    current_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert prepared.initial_commit_sha == current_sha
    assert prepared.eval_name == "source-eval"


def test_run_megaplan_loop_iterates_to_revise_then_proceeds(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = _make_eval_config()
    audit = EvalAudit(eval_name="demo")
    runner = FakeMegaplanRunner(workspace, config, ["ITERATE", "PROCEED"])

    result = run_megaplan_loop("ship it", workspace, config, audit, runner=runner)

    assert result.escalated is False
    assert result.gate_recommendation == "PROCEED"
    assert result.phase_order == [
        "init",
        "prep",
        "plan",
        "critique",
        "gate",
        "revise",
        "critique",
        "gate",
        "finalize",
        "execute",
        "review",
    ]
    revise_record = next(record for record in audit.phase_records if record.phase == "revise")
    assert revise_record.trace_messages == [{"role": "assistant", "content": "revise-1"}]
    critique_records = [record for record in audit.phase_records if record.phase == "critique"]
    assert critique_records[0].trace_messages == [{"role": "assistant", "content": "critique-1"}]
    assert critique_records[1].trace_messages == [{"role": "assistant", "content": "critique-2"}]


def test_run_megaplan_loop_escalate_stops_before_finalize(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = _make_eval_config()
    audit = EvalAudit(eval_name="demo")
    runner = FakeMegaplanRunner(workspace, config, ["ESCALATE"])

    result = run_megaplan_loop("ship it", workspace, config, audit, runner=runner)

    assert result.escalated is True
    assert result.gate_recommendation == "ESCALATE"
    assert result.phase_order == ["init", "prep", "plan", "critique", "gate"]
    assert all(record.phase not in {"finalize", "execute", "review"} for record in audit.phase_records)


def test_run_megaplan_loop_with_verify(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = _make_eval_config()
    audit = EvalAudit(eval_name="demo")
    runner = VerifyPathMegaplanRunner(workspace, config, ["PROCEED"])
    verify_results = [
        VerifyResult(passed=False, test_output="first failure", tests_run=["t1"], duration_seconds=1.0),
        VerifyResult(passed=True, test_output="second pass", tests_run=["t1"], duration_seconds=0.5),
    ]
    injected_feedback = []

    def verify_fn():
        return verify_results.pop(0)

    with patch("evals.run_evals._all_tasks_done", return_value=True), patch(
        "evals.run_evals._inject_verify_feedback",
        side_effect=lambda config, plan_name, workspace_path, verify_result: injected_feedback.append(
            verify_result.test_output
        ),
    ):
        result = run_megaplan_loop(
            "ship it",
            workspace,
            config,
            audit,
            runner=runner,
            verify_fn=verify_fn,
            max_verify_attempts=2,
        )

    assert result.phase_order == [
        "init",
        "prep",
        "plan",
        "critique",
        "gate",
        "finalize",
        "execute",
        "verify",
        "execute",
        "verify",
    ]
    assert injected_feedback == ["first failure"]
    verify_records = [record for record in audit.phase_records if record.phase == "verify"]
    assert len(verify_records) == 2
    assert verify_records[0].artifact_payload["passed"] is False
    assert verify_records[1].artifact_payload["passed"] is True


def test_run_megaplan_loop_verify_max_attempts(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = _make_eval_config()
    audit = EvalAudit(eval_name="demo")
    runner = VerifyPathMegaplanRunner(workspace, config, ["PROCEED"])
    verify_results = [
        VerifyResult(passed=False, test_output="first failure", tests_run=["t1"], duration_seconds=1.0),
        VerifyResult(passed=False, test_output="second failure", tests_run=["t1"], duration_seconds=0.5),
    ]
    injected_feedback = []

    def verify_fn():
        return verify_results.pop(0)

    with patch("evals.run_evals._all_tasks_done", return_value=True), patch(
        "evals.run_evals._inject_verify_feedback",
        side_effect=lambda config, plan_name, workspace_path, verify_result: injected_feedback.append(
            verify_result.test_output
        ),
    ):
        result = run_megaplan_loop(
            "ship it",
            workspace,
            config,
            audit,
            runner=runner,
            verify_fn=verify_fn,
            max_verify_attempts=2,
        )

    assert result.phase_order == [
        "init",
        "prep",
        "plan",
        "critique",
        "gate",
        "finalize",
        "execute",
        "verify",
        "execute",
        "verify",
    ]
    assert injected_feedback == ["first failure"]
    assert audit.notes[-1] == "verify_failed_after_2_attempts"
    verify_records = [record for record in audit.phase_records if record.phase == "verify"]
    assert len(verify_records) == 2
    assert all(record.artifact_payload["passed"] is False for record in verify_records)


def test_run_megaplan_loop_no_verify(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = _make_eval_config()
    audit = EvalAudit(eval_name="demo")
    runner = FakeMegaplanRunner(workspace, config, ["PROCEED"])

    result = run_megaplan_loop("ship it", workspace, config, audit, runner=runner, verify_fn=None)

    assert "verify" not in result.phase_order
    assert result.phase_order == [
        "init",
        "prep",
        "plan",
        "critique",
        "gate",
        "finalize",
        "execute",
        "review",
    ]
    assert all(record.phase != "verify" for record in audit.phase_records)


def test_diagnose_verify_failure_extracts_structure():
    verify_result = VerifyResult(
        passed=False,
        tests_run=["pkg/test_mod.py::test_example"],
        test_output=(
            "FAILED pkg/test_mod.py::test_example - AssertionError: expected 1 == 2\n"
            "Traceback (most recent call last):\n"
            "  File \"/tmp/test_mod.py\", line 10, in test_example\n"
            "    assert actual == expected\n"
            "AssertionError: expected 1 == 2\n"
        ),
        duration_seconds=1.0,
    )

    diagnosis = _diagnose_verify_failure(verify_result)

    assert diagnosis["error_type"] == "assertion_error"
    assert diagnosis["failing_tests"] == ["pkg/test_mod.py::test_example"]
    assert "Traceback (most recent call last):" in diagnosis["traceback_summary"]


def test_inject_verify_feedback_includes_structured_diagnosis(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = _make_eval_config()
    captured_notes: list[str] = []

    def fake_megaplan_command(_config, args):
        note = args[args.index("--note") + 1]
        captured_notes.append(note)
        return ["megaplan", *args]

    with patch("evals.run_evals._megaplan_command", side_effect=fake_megaplan_command), patch(
        "evals.run_evals._run_megaplan_json",
        return_value={},
    ):
        _inject_verify_feedback(
            config,
            "demo-plan",
            workspace,
            VerifyResult(
                passed=False,
                tests_run=["pkg/test_mod.py::test_example"],
                test_output=(
                    "FAILED pkg/test_mod.py::test_example - AttributeError: thing\n"
                    "Traceback (most recent call last):\n"
                    "  File \"/tmp/test_mod.py\", line 10, in test_example\n"
                    "AttributeError: thing\n"
                ),
                duration_seconds=1.0,
            ),
        )

    assert len(captured_notes) == 1
    note = captured_notes[0]
    assert "error_type: attribute_error" in note
    assert "failing_tests: pkg/test_mod.py::test_example" in note
    assert "traceback_summary:" in note
    assert "Diagnose the root cause from the traceback before making changes." in note


def test_inject_feedback_formats_rework_items(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = _make_eval_config()
    captured_notes: list[str] = []

    def fake_megaplan_command(_config, args):
        note = args[args.index("--note") + 1]
        captured_notes.append(note)
        return ["megaplan", *args]

    with patch("evals.run_evals._megaplan_command", side_effect=fake_megaplan_command), patch(
        "evals.run_evals._run_megaplan_json",
        return_value={},
    ):
        _inject_feedback(
            config,
            "demo-plan",
            workspace,
            "review",
            {
                "summary": "Needs rework",
                "rework_items": [
                    {
                        "task_id": "T8",
                        "issue": "x" * 250,
                        "expected": "Expected behavior",
                        "actual": "Actual behavior",
                        "evidence_file": "review.json",
                    }
                ],
                "issues": ["legacy fallback should not appear"],
            },
        )

    assert len(captured_notes) == 1
    note = captured_notes[0]
    assert "[rework] task: T8" in note
    assert "  expected: Expected behavior" in note
    assert "  actual: Actual behavior" in note
    assert "  evidence: review.json" in note
    assert "issues: legacy fallback should not appear" not in note
    rework_issue_line = next(line for line in note.splitlines() if line.startswith("  issue: "))
    assert len(rework_issue_line.removeprefix("  issue: ")) == 200


def test_inject_feedback_falls_back_to_issues_when_rework_items_missing(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = _make_eval_config()
    captured_notes: list[str] = []

    def fake_megaplan_command(_config, args):
        note = args[args.index("--note") + 1]
        captured_notes.append(note)
        return ["megaplan", *args]

    with patch("evals.run_evals._megaplan_command", side_effect=fake_megaplan_command), patch(
        "evals.run_evals._run_megaplan_json",
        return_value={},
    ):
        _inject_feedback(
            config,
            "demo-plan",
            workspace,
            "review",
            {
                "summary": "Needs rework",
                "issues": ["first issue", "second issue"],
            },
        )

    assert len(captured_notes) == 1
    note = captured_notes[0]
    assert "issues: first issue; second issue" in note
    assert "[rework] task:" not in note
