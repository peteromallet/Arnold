"""Tests for the project_dir tool sandbox.

The sandbox enforces — at the *tool layer* — that an LLM running in a hermes
worker cannot exec or write outside the worktree it was given via
``state["config"]["project_dir"]``.  This is the root-cause guard for the
phase-6 bakeoff regression where a model resolved a conflicting
``Project: ...`` line in user-authored idea text by writing into the main
repo instead of its assigned worktree.

These tests exercise the sandbox without hitting any model:

  * ``validate_terminal_command`` strips a leading ``cd <project>/...`` and
    refuses ``cd`` to anything outside the worktree.
  * ``validate_write_path`` resolves to inside ``project_dir`` or raises.
  * ``install_sandbox`` wraps the tool registry handlers so the same
    refusal/coercion happens when a tool dispatch comes through the agent.

The mock-registry pattern mirrors the live ``tools.registry`` singleton —
each tool has a ``handler`` attribute the wrapper swaps in place.
"""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

import pytest

from megaplan.sandbox import (
    SandboxViolation,
    install_sandbox,
    validate_terminal_command,
    validate_v4a_patch,
    validate_write_path,
)


# ---------------------------------------------------------------------------
# validate_terminal_command
# ---------------------------------------------------------------------------


def test_terminal_command_without_cd_passes_through(tmp_path: Path) -> None:
    cmd = "pytest tests/ -x"
    assert validate_terminal_command(cmd, tmp_path) == cmd


def test_terminal_command_strips_leading_cd_to_project_dir(tmp_path: Path) -> None:
    """A leading ``cd <project_dir> &&`` is redundant once cwd is pinned —
    the sandbox strips it so the rest of the command runs at the right cwd."""
    cmd = f"cd {tmp_path} && ls -la"
    assert validate_terminal_command(cmd, tmp_path) == "ls -la"


def test_terminal_command_keeps_cd_to_subdir(tmp_path: Path) -> None:
    """A ``cd <project_dir>/subdir`` is legitimate scoping — the sandbox
    rewrites it to a relative cd so it works regardless of starting cwd."""
    sub = tmp_path / "src"
    sub.mkdir()
    cmd = f"cd {sub} && pytest"
    assert validate_terminal_command(cmd, tmp_path) == "cd src && pytest"


def test_terminal_command_refuses_cd_outside_project_dir(tmp_path: Path) -> None:
    """The bakeoff regression: model prefixes commands with ``cd <other_repo>``.
    The sandbox MUST refuse, not silently ignore."""
    other = tmp_path.parent / "some-other-repo"
    other.mkdir(exist_ok=True)
    project = tmp_path / "worktree"
    project.mkdir()
    cmd = f"cd {other} && touch f.txt"
    with pytest.raises(SandboxViolation, match="outside the project directory"):
        validate_terminal_command(cmd, project)


def test_terminal_command_refuses_cd_with_traversal(tmp_path: Path) -> None:
    project = tmp_path / "worktree"
    project.mkdir()
    cmd = f"cd {project}/../escape && rm -rf ."
    with pytest.raises(SandboxViolation):
        validate_terminal_command(cmd, project)


def test_terminal_command_refuses_quoted_escape(tmp_path: Path) -> None:
    project = tmp_path / "worktree"
    project.mkdir()
    other = tmp_path / "elsewhere"
    other.mkdir()
    cmd = f'cd "{other}" && echo hi'
    with pytest.raises(SandboxViolation):
        validate_terminal_command(cmd, project)


# ---------------------------------------------------------------------------
# validate_write_path
# ---------------------------------------------------------------------------


def test_write_path_relative_resolves_under_project(tmp_path: Path) -> None:
    safe = validate_write_path("src/foo.py", tmp_path)
    assert Path(safe) == (tmp_path / "src/foo.py").resolve()


def test_write_path_absolute_inside_project_passes(tmp_path: Path) -> None:
    target = tmp_path / "a/b.py"
    safe = validate_write_path(str(target), tmp_path)
    assert Path(safe) == target.resolve()


def test_write_path_absolute_outside_project_refused(tmp_path: Path) -> None:
    project = tmp_path / "worktree"
    project.mkdir()
    other = tmp_path / "elsewhere/file.py"
    with pytest.raises(SandboxViolation, match="outside the project directory"):
        validate_write_path(str(other), project)


def test_write_path_traversal_refused(tmp_path: Path) -> None:
    project = tmp_path / "worktree"
    project.mkdir()
    with pytest.raises(SandboxViolation):
        validate_write_path("../../etc/passwd", project)


def test_write_path_empty_refused(tmp_path: Path) -> None:
    with pytest.raises(SandboxViolation):
        validate_write_path("", tmp_path)


# ---------------------------------------------------------------------------
# validate_v4a_patch
# ---------------------------------------------------------------------------


def test_v4a_patch_inside_project_passes(tmp_path: Path) -> None:
    patch = (
        "*** Begin Patch\n"
        "*** Update File: src/main.py\n"
        "@@\n"
        "-old\n"
        "+new\n"
        "*** End Patch\n"
    )
    validate_v4a_patch(patch, tmp_path)  # no raise


def test_v4a_patch_with_absolute_outside_refused(tmp_path: Path) -> None:
    project = tmp_path / "worktree"
    project.mkdir()
    other = tmp_path / "elsewhere"
    other.mkdir()
    patch = (
        "*** Begin Patch\n"
        f"*** Add File: {other}/leak.py\n"
        "+leaked\n"
        "*** End Patch\n"
    )
    with pytest.raises(SandboxViolation):
        validate_v4a_patch(patch, project)


# ---------------------------------------------------------------------------
# install_sandbox: end-to-end through a fake registry
# ---------------------------------------------------------------------------


class _FakeEntry:
    def __init__(self, handler):
        self.handler = handler


class _FakeRegistry:
    def __init__(self, names):
        self._tools = {name: _FakeEntry(self._make_handler(name)) for name in names}
        self.calls: list[tuple[str, dict]] = []

    def _make_handler(self, name):
        def handler(args, **kw):
            self.calls.append((name, dict(args) if isinstance(args, dict) else args))
            return json.dumps({"ok": True, "tool": name, "args": args})
        return handler


@pytest.fixture
def fake_tools_registry(monkeypatch):
    """Install a fake ``tools.registry`` module so ``install_sandbox`` wraps it.

    The real registry is part of the vendored agent SDK, which pulls in heavy
    deps.  The sandbox is decoupled from the SDK by name — it imports
    ``tools.registry`` lazily — so a stub in sys.modules is enough to test the
    wrapping behavior without bringing in the SDK.
    """
    fake_registry = _FakeRegistry(["terminal", "write_file", "patch", "read_file"])
    fake_module = types.ModuleType("tools.registry")
    fake_module.registry = fake_registry
    fake_tools_pkg = types.ModuleType("tools")
    monkeypatch.setitem(sys.modules, "tools", fake_tools_pkg)
    monkeypatch.setitem(sys.modules, "tools.registry", fake_module)
    return fake_registry


def test_install_sandbox_pins_terminal_cwd(tmp_path, monkeypatch, fake_tools_registry):
    monkeypatch.delenv("TERMINAL_CWD", raising=False)
    with install_sandbox(tmp_path):
        assert os.environ["TERMINAL_CWD"] == str(tmp_path.resolve())
    assert "TERMINAL_CWD" not in os.environ


def test_install_sandbox_restores_prior_terminal_cwd(tmp_path, monkeypatch, fake_tools_registry):
    monkeypatch.setenv("TERMINAL_CWD", "/some/prior/value")
    with install_sandbox(tmp_path):
        assert os.environ["TERMINAL_CWD"] == str(tmp_path.resolve())
    assert os.environ["TERMINAL_CWD"] == "/some/prior/value"


def test_install_sandbox_refuses_terminal_cd_escape(tmp_path, fake_tools_registry):
    """The smoking-gun scenario: model emits ``cd /escape/path && touch f.txt``
    with project_dir set to the worktree.  The sandbox MUST refuse — the
    tool layer does not silently let writes land in the wrong tree."""
    project = tmp_path / "worktree"
    project.mkdir()
    escape = tmp_path / "main-repo"
    escape.mkdir()

    with install_sandbox(project):
        terminal_handler = fake_tools_registry._tools["terminal"].handler
        result = terminal_handler({"command": f"cd {escape} && touch f.txt"})
        # Refusal is a JSON error returned to the model so it can adjust.
        parsed = json.loads(result)
        assert "error" in parsed
        assert "outside the project directory" in parsed["error"]

    # The unwrapped handler was never called — refusal is hard, not silent.
    assert fake_tools_registry.calls == []


def test_install_sandbox_strips_leading_cd_to_project(tmp_path, fake_tools_registry):
    project = tmp_path / "worktree"
    project.mkdir()

    with install_sandbox(project):
        terminal_handler = fake_tools_registry._tools["terminal"].handler
        terminal_handler({"command": f"cd {project} && ls"})

    # The redundant cd was stripped — the underlying handler saw just `ls`.
    assert len(fake_tools_registry.calls) == 1
    name, args = fake_tools_registry.calls[0]
    assert name == "terminal"
    assert args["command"] == "ls"


def test_install_sandbox_refuses_write_outside_project(tmp_path, fake_tools_registry):
    project = tmp_path / "worktree"
    project.mkdir()
    escape = tmp_path / "main-repo"

    with install_sandbox(project):
        wf = fake_tools_registry._tools["write_file"].handler
        result = wf({"path": str(escape / "leaked.py"), "content": "leak"})
        parsed = json.loads(result)
        assert "error" in parsed
        assert "outside the project directory" in parsed["error"]

    assert fake_tools_registry.calls == []


def test_install_sandbox_resolves_relative_write_to_project(tmp_path, fake_tools_registry):
    with install_sandbox(tmp_path):
        wf = fake_tools_registry._tools["write_file"].handler
        wf({"path": "src/foo.py", "content": "hi"})

    assert len(fake_tools_registry.calls) == 1
    name, args = fake_tools_registry.calls[0]
    assert name == "write_file"
    # The handler sees a fully resolved absolute path under project_dir.
    assert args["path"] == str((tmp_path / "src/foo.py").resolve())


def test_install_sandbox_refuses_patch_outside_project(tmp_path, fake_tools_registry):
    project = tmp_path / "worktree"
    project.mkdir()
    escape = tmp_path / "main-repo"

    with install_sandbox(project):
        patch_handler = fake_tools_registry._tools["patch"].handler
        result = patch_handler({
            "mode": "replace",
            "path": str(escape / "f.py"),
            "old_string": "a",
            "new_string": "b",
        })
        parsed = json.loads(result)
        assert "error" in parsed

    assert fake_tools_registry.calls == []


def test_install_sandbox_refuses_v4a_patch_outside_project(tmp_path, fake_tools_registry):
    project = tmp_path / "worktree"
    project.mkdir()
    escape = tmp_path / "main-repo"
    escape.mkdir()

    patch_blob = (
        "*** Begin Patch\n"
        f"*** Add File: {escape}/leaked.py\n"
        "+leaked\n"
        "*** End Patch\n"
    )
    with install_sandbox(project):
        patch_handler = fake_tools_registry._tools["patch"].handler
        result = patch_handler({"mode": "patch", "patch": patch_blob})
        parsed = json.loads(result)
        assert "error" in parsed

    assert fake_tools_registry.calls == []


def test_install_sandbox_does_not_lock_down_reads(tmp_path, fake_tools_registry):
    """Reads outside project_dir are intentionally allowed — the model
    legitimately needs to read /tmp/<idea>.txt and template files."""
    other = tmp_path / "elsewhere/idea.txt"
    other.parent.mkdir()
    other.write_text("idea content")

    project = tmp_path / "worktree"
    project.mkdir()
    with install_sandbox(project):
        read_handler = fake_tools_registry._tools["read_file"].handler
        # Should pass through unmodified, no refusal.
        read_handler({"path": str(other)})

    assert len(fake_tools_registry.calls) == 1
    assert fake_tools_registry.calls[0][0] == "read_file"


def test_install_sandbox_restores_handlers_on_exit(tmp_path, fake_tools_registry):
    original_terminal = fake_tools_registry._tools["terminal"].handler

    with install_sandbox(tmp_path):
        wrapped = fake_tools_registry._tools["terminal"].handler
        assert wrapped is not original_terminal

    assert fake_tools_registry._tools["terminal"].handler is original_terminal


def test_install_sandbox_rejects_missing_project_dir(tmp_path):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(ValueError, match="does not exist"):
        with install_sandbox(missing):
            pass


def test_hermes_worker_installs_sandbox_for_execute(monkeypatch, tmp_path, fake_tools_registry):
    """End-to-end: ``run_hermes_step`` for the execute phase must install the
    sandbox so the agent's tool calls are bounded to project_dir.

    We mock the agent so no model is invoked.  The test checks that:
      * ``TERMINAL_CWD`` is set to project_dir while the agent runs, AND
      * tool registry handlers are wrapped while the agent runs.
    """
    from megaplan import hermes_worker as hw
    from megaplan._core import atomic_write_json, atomic_write_text, schemas_root
    from megaplan.workers import STEP_SCHEMA_FILENAMES

    project_dir = tmp_path / "worktree"
    project_dir.mkdir()
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (project_dir / ".git").mkdir()

    state = {
        "name": "sandbox-test",
        "idea": "test",
        "current_state": "planned",
        "iteration": 1,
        "created_at": "2026-05-01T00:00:00Z",
        "config": {
            "project_dir": str(project_dir),
            "auto_approve": False,
            "robustness": "standard",
            "mode": "code",
        },
        "sessions": {},
        "plan_versions": [
            {"version": 1, "file": "plan_v1.md", "hash": "sha256:test", "timestamp": "2026-05-01T00:00:00Z"}
        ],
        "history": [],
        "meta": {
            "significant_counts": [],
            "weighted_scores": [],
            "plan_deltas": [],
            "recurring_critiques": [],
            "total_cost_usd": 0.0,
            "overrides": [],
            "notes": [],
        },
        "last_gate": {},
    }

    atomic_write_text(plan_dir / "plan_v1.md", "# Plan\n")
    atomic_write_json(
        plan_dir / "plan_v1.meta.json",
        {
            "version": 1,
            "timestamp": "2026-05-01T00:00:00Z",
            "hash": "sha256:test",
            "success_criteria": [{"criterion": "do x", "priority": "must"}],
            "questions": [],
            "assumptions": [],
        },
    )
    atomic_write_json(plan_dir / "faults.json", {"flags": []})

    # Capture sandbox state observed during agent invocation.
    observed: dict = {}

    class FakeSessionDB:
        def get_messages_as_conversation(self, *_a, **_kw):
            return None

    class FakeAIAgent:
        def __init__(self, **kwargs):
            self._print_fn = None

        def set_response_format(self, *a, **kw):
            pass

        def run_conversation(self, **kwargs):
            # Snapshot env + handler identity at the moment the agent runs.
            observed["TERMINAL_CWD"] = os.environ.get("TERMINAL_CWD")
            observed["terminal_handler"] = fake_tools_registry._tools["terminal"].handler
            # Return a payload the parser will accept.  For execute we
            # need files_claimed + summary.
            payload = {
                "files_claimed": [],
                "summary": "did nothing",
                "tasks_completed": [],
                "tests_run": [],
                "issues": [],
                "next_steps": [],
            }
            return {
                "final_response": json.dumps(payload),
                "messages": [{"role": "assistant", "content": json.dumps(payload)}],
                "estimated_cost_usd": 0.0,
            }

    monkeypatch.setitem(sys.modules, "run_agent", types.ModuleType("run_agent"))
    monkeypatch.setitem(sys.modules, "hermes_state", types.ModuleType("hermes_state"))
    sys.modules["run_agent"].AIAgent = FakeAIAgent
    sys.modules["hermes_state"].SessionDB = FakeSessionDB

    # Stub the prompt builder so the test doesn't need the full prompt
    # machinery.  The prompt content doesn't matter — we're checking the
    # sandbox installs around the agent invocation.
    monkeypatch.setattr(hw, "create_hermes_prompt", lambda *a, **kw: "go")
    monkeypatch.setattr(hw, "validate_payload", lambda step, payload: None)
    monkeypatch.setattr(hw, "parse_agent_output", lambda agent, result, **kw: (
        json.loads(result["final_response"]),
        result["final_response"],
    ))
    monkeypatch.setattr(hw, "clean_parsed_payload", lambda *a, **kw: None)

    # Save the original terminal handler so we can confirm it was wrapped
    # *during* the agent run, then restored after.
    original_terminal_handler = fake_tools_registry._tools["terminal"].handler

    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(hw, "read_json", lambda p: {} if "schemas" in str(p) else json.loads(Path(p).read_text()))
    monkeypatch.setattr(hw, "schemas_root", lambda root: repo_root / "megaplan" / "schemas")
    # Bypass the schema-name lookup — execute schema file may not exist on disk in this minimal setup.
    monkeypatch.setattr("megaplan.schemas.get_execution_schema_key", lambda *a, **kw: STEP_SCHEMA_FILENAMES.get("execute", "execute_v2.json"))

    monkeypatch.delenv("MEGAPLAN_MOCK", raising=False)
    monkeypatch.delenv("TERMINAL_CWD", raising=False)

    hw.run_hermes_step(
        "execute",
        state,
        plan_dir,
        root=repo_root,
        fresh=True,
        model="openrouter/anthropic/claude-opus-4.6",
    )

    # The sandbox was active while the agent ran:
    assert observed["TERMINAL_CWD"] == str(project_dir.resolve())
    assert observed["terminal_handler"] is not original_terminal_handler

    # And restored after:
    assert os.environ.get("TERMINAL_CWD") is None
    assert fake_tools_registry._tools["terminal"].handler is original_terminal_handler


def test_install_sandbox_refuses_workdir_arg_escape(tmp_path, fake_tools_registry):
    """The model can also pass an explicit ``workdir`` arg — that path must
    also stay inside project_dir.  Otherwise a benign-looking ``ls`` with
    workdir=/escape/repo would still leak."""
    project = tmp_path / "worktree"
    project.mkdir()
    escape = tmp_path / "main-repo"
    escape.mkdir()

    with install_sandbox(project):
        terminal_handler = fake_tools_registry._tools["terminal"].handler
        result = terminal_handler({"command": "ls", "workdir": str(escape)})
        parsed = json.loads(result)
        assert "error" in parsed

    assert fake_tools_registry.calls == []
