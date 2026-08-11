"""B5 oracle tests — agentbox trusted-container decision, relocated sandbox
validators, and fork-clean omp release.

Covers:

* trusted-container mode evidence (``MEGAPLAN_TRUSTED_CONTAINER``);
* relocated in-process path validators (``runtime.sandbox`` — not
  (not the deleted agent SDK): terminal-command cwd, write-path, v4a-patch, symlink
  escapes, and ``SandboxViolation`` inheritance;
* empty-cache agent discovery (fresh processes);
* exact fork cleanup (no bundled resident agent, no ``src/`` delta, allowed
  diff limited to docs/examples/launcher).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from arnold.runtime.errors import ArnoldError
from arnold_pipelines.megaplan.runtime.sandbox import (
    SANDBOX_CWD,
    SANDBOXED_EXEC_TOOLS,
    SANDBOXED_WRITE_TOOLS,
    SandboxViolation,
    get_sandbox_cwd,
    validate_terminal_command,
    validate_v4a_patch,
    validate_write_path,
)

ARNOLD_ROOT = Path(__file__).resolve().parents[2]
OMP_CHECKOUT = ARNOLD_ROOT.parent / "oh-my-pi"
AGENT_SCRIPT = OMP_CHECKOUT / "packages/coding-agent/scripts/agent"


class TestTrustedContainerEvidence:
    def test_trusted_container_flag_on(self, monkeypatch):
        from arnold_pipelines.megaplan.workers._impl import _trusted_container

        for value in ("1", "true", "yes", "on"):
            monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", value)
            assert _trusted_container() is True

    def test_trusted_container_flag_off(self, monkeypatch):
        from arnold_pipelines.megaplan.workers._impl import _trusted_container

        monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)
        assert _trusted_container() is False
        for value in ("0", "false", "no", "off", ""):
            monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", value)
            assert _trusted_container() is False

    def test_sandbox_decision_doc_exists(self):
        doc = ARNOLD_ROOT / "docs/agentbox-sandbox-decision.md"
        assert doc.exists(), "B5 security decision doc must be recorded"
        text = doc.read_text(encoding="utf-8")
        assert "bwrap is not viable" in text
        assert "MEGAPLAN_TRUSTED_CONTAINER" in text
        assert "writable roots" in text.lower()


class TestRelocatedValidators:
    def test_validators_come_from_megaplan_runtime_not_agent(self):
        # The megaplan runtime must own the primitives (B11 vendoring edge);
        # importing them here must not pull in the deleted agent SDK.
        import arnold_pipelines.megaplan.runtime.sandbox as runtime_sandbox

        for name in (
            "SANDBOX_CWD",
            "SANDBOXED_EXEC_TOOLS",
            "SANDBOXED_WRITE_TOOLS",
            "SandboxViolation",
            "get_sandbox_cwd",
            "validate_terminal_command",
            "validate_v4a_patch",
            "validate_write_path",
        ):
            assert hasattr(runtime_sandbox, name), f"runtime.sandbox missing {name}"

    def test_sandbox_violation_inherits_arnold_error(self):
        assert issubclass(SandboxViolation, ArnoldError)
        error = SandboxViolation("escaped")
        assert error.code == "sandbox_violation"

    def test_sandbox_cwd_contextvar(self):
        assert SANDBOX_CWD is not None
        assert get_sandbox_cwd() is None
        token = SANDBOX_CWD.set(Path("/tmp/proj"))
        try:
            assert get_sandbox_cwd() == Path("/tmp/proj")
        finally:
            SANDBOX_CWD.reset(token)

    def test_sandboxed_tool_lists(self):
        assert SANDBOXED_EXEC_TOOLS == ("terminal",)
        assert SANDBOXED_WRITE_TOOLS == ("write_file", "patch")


class TestTerminalCommand:
    def test_no_leading_cd_passthrough(self, tmp_path):
        assert validate_terminal_command("pytest -q", tmp_path) == "pytest -q"

    def test_leading_cd_inside_rewrites_relative(self, tmp_path):
        (tmp_path / "sub").mkdir()
        result = validate_terminal_command(
            f"cd {tmp_path}/sub && pytest -q", tmp_path
        )
        assert result == "cd sub && pytest -q"

    def test_leading_cd_project_dir_returns_rest(self, tmp_path):
        result = validate_terminal_command(f"cd {tmp_path} && pytest -q", tmp_path)
        assert result == "pytest -q"

    def test_leading_cd_escape_rejected(self, tmp_path):
        outside = tmp_path.parent / "outside"
        with pytest.raises(SandboxViolation, match="outside the sandbox"):
            validate_terminal_command(f"cd {outside} && rm -rf .", tmp_path)

    def test_leading_cd_parent_escape_rejected(self, tmp_path):
        with pytest.raises(SandboxViolation, match="outside the sandbox"):
            validate_terminal_command("cd .. && pwd", tmp_path)

    def test_non_string_rejected(self, tmp_path):
        with pytest.raises(SandboxViolation):
            validate_terminal_command(123, tmp_path)  # type: ignore[arg-type]


class TestWritePath:
    def test_relative_path_ok(self, tmp_path):
        assert validate_write_path("src/foo.py", tmp_path) == str(
            (tmp_path / "src/foo.py").resolve()
        )

    def test_absolute_inside_ok(self, tmp_path):
        target = tmp_path / "out.json"
        assert validate_write_path(str(target), tmp_path) == str(target.resolve())

    def test_parent_escape_rejected(self, tmp_path):
        with pytest.raises(SandboxViolation, match="outside the sandbox"):
            validate_write_path("../evil.txt", tmp_path)

    def test_absolute_outside_rejected(self, tmp_path):
        with pytest.raises(SandboxViolation, match="outside the sandbox"):
            validate_write_path("/etc/cron.d/evil", tmp_path)

    def test_symlink_escape_rejected(self, tmp_path):
        outside = tmp_path.parent / "secret.txt"
        outside.write_text("secret", encoding="utf-8")
        link = tmp_path / "link.txt"
        link.symlink_to(outside)
        with pytest.raises(SandboxViolation, match="outside the sandbox"):
            validate_write_path(str(link), tmp_path)

    def test_empty_path_rejected(self, tmp_path):
        with pytest.raises(SandboxViolation, match="non-empty"):
            validate_write_path("", tmp_path)


class TestV4aPatch:
    def test_internal_directives_ok(self, tmp_path):
        validate_v4a_patch(
            "*** Update File: src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n",
            tmp_path,
        )

    def test_escaping_directive_rejected(self, tmp_path):
        with pytest.raises(SandboxViolation, match="outside the sandbox"):
            validate_v4a_patch(
                "*** Add File: /etc/evil\n+++ b/etc/evil\n",
                tmp_path,
            )

    def test_parent_escape_directive_rejected(self, tmp_path):
        with pytest.raises(SandboxViolation, match="outside the sandbox"):
            validate_v4a_patch("*** Delete File: ../sibling.txt\n", tmp_path)


class TestEmptyCacheDiscovery:
    """Fresh-process agent launcher smoke from empty caches."""

    @pytest.fixture
    def smoke_env(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        fake_omp = tmp_path / "fake-omp"
        fake_omp.write_text(
            "#!/bin/bash\necho \"ARGS: $*\" > %s\n" % (tmp_path / "captured.txt"),
            encoding="utf-8",
        )
        fake_omp.chmod(0o755)
        env = dict(os.environ)
        env["HOME"] = str(home)
        env["OMP_BIN"] = str(fake_omp)
        return tmp_path, home, env

    def _run_omp_agent(self, env, *args, cwd):
        proc = subprocess.run(
            ["bash", str(AGENT_SCRIPT), *args],
            env=env,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=120,
        )
        return proc

    def test_empty_cache_project_agent_discovers_and_materializes(self, smoke_env):
        tmp_path, home, env = smoke_env
        project = tmp_path / "proj"
        project.mkdir()
        agents = project / ".omp" / "agents"
        agents.mkdir(parents=True)
        (agents / "pagent.md").write_text(
            "---\nname: pagent\ndescription: Project agent\n---\n\nYou are pagent.\n",
            encoding="utf-8",
        )
        proc = self._run_omp_agent(env, "run", "pagent", "hi", cwd=project)
        assert proc.returncode == 0, proc.stderr
        captured = (tmp_path / "captured.txt").read_text(encoding="utf-8")
        assert "--system-prompt" in captured
        # Hash-pinned cache materialized from the empty ~/.omp.
        assert ".prompts/pagent." in captured
        prompts = home / ".omp" / "agent" / ".prompts"
        assert list(prompts.glob("pagent.*.md")), "hash-pinned prompt missing"

    def test_cache_invalidated_on_source_change(self, smoke_env):
        tmp_path, home, env = smoke_env
        project = tmp_path / "proj"
        project.mkdir()
        agents = project / ".omp" / "agents"
        agents.mkdir(parents=True)
        agent_file = agents / "pagent.md"
        agent_file.write_text(
            "---\nname: pagent\ndescription: v1\n---\n\nYou are v1.\n",
            encoding="utf-8",
        )
        self._run_omp_agent(env, "run", "pagent", "hi", cwd=project)
        prompts = home / ".omp" / "agent" / ".prompts"
        first = list(prompts.glob("pagent.*.md"))
        assert len(first) == 1
        # Change the source: a new hash-pinned cache must appear, old pruned.
        agent_file.write_text(
            "---\nname: pagent\ndescription: v2\n---\n\nYou are v2.\n",
            encoding="utf-8",
        )
        self._run_omp_agent(env, "run", "pagent", "hi", cwd=project)
        second = list(prompts.glob("pagent.*.md"))
        assert len(second) == 1
        assert second[0].name != first[0].name
        assert "You are v2." in second[0].read_text(encoding="utf-8")

    def test_project_over_user_precedence(self, smoke_env):
        tmp_path, home, env = smoke_env
        project = tmp_path / "proj"
        project.mkdir()
        agents = project / ".omp" / "agents"
        agents.mkdir(parents=True)
        (agents / "pagent.md").write_text(
            "---\nname: pagent\ndescription: project copy\n---\n\nYou are PROJECT.\n",
            encoding="utf-8",
        )
        user_agents = home / ".omp" / "agent" / "agents"
        user_agents.mkdir(parents=True)
        (user_agents / "pagent.md").write_text(
            "---\nname: pagent\ndescription: user copy\n---\n\nYou are USER.\n",
            encoding="utf-8",
        )
        self._run_omp_agent(env, "run", "pagent", "hi", cwd=project)
        prompts = home / ".omp" / "agent" / ".prompts"
        cached = list(prompts.glob("pagent.*.md"))[0]
        assert "You are PROJECT." in cached.read_text(encoding="utf-8")


class TestForkClean:
    @pytest.mark.skipif(not OMP_CHECKOUT.exists(), reason="omp checkout missing")
    def test_no_bundled_resident_prompt(self):
        resident = (
            OMP_CHECKOUT
            / "packages/coding-agent/src/prompts/agents/resident.md"
        )
        assert not resident.exists(), "bundled resident prompt must be removed"

    @pytest.mark.skipif(not OMP_CHECKOUT.exists(), reason="omp checkout missing")
    def test_agents_ts_has_no_resident_lines(self):
        agents_ts = OMP_CHECKOUT / "packages/coding-agent/src/task/agents.ts"
        text = agents_ts.read_text(encoding="utf-8")
        assert "resident.md" not in text
        assert "residentMd" not in text

    @pytest.mark.skipif(not OMP_CHECKOUT.exists(), reason="omp checkout missing")
    def test_fork_diff_limited_to_allowed_paths(self):
        proc = subprocess.run(
            ["git", "-C", str(OMP_CHECKOUT), "diff", "--name-only", "FETCH_HEAD"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        changed = [line for line in proc.stdout.splitlines() if line.strip()]
        allowed = {
            "docs/agents.md",
            "packages/coding-agent/scripts/agent",
        }
        for path in changed:
            assert path in allowed, f"fork diff touches unallowed path {path}"
        # Byte-identical src/: nothing under packages/coding-agent/src/.
        src_changes = [p for p in changed if "src/" in p]
        assert src_changes == []

    @pytest.mark.skipif(not OMP_CHECKOUT.exists(), reason="omp checkout missing")
    def test_upstream_head_recorded(self):
        proc = subprocess.run(
            ["git", "-C", str(OMP_CHECKOUT), "rev-parse", "FETCH_HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0
        assert len(proc.stdout.strip()) == 40
