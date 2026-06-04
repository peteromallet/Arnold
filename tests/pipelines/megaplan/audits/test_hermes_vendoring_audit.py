from __future__ import annotations

import subprocess
from pathlib import Path

from arnold.pipelines.megaplan.audits.hermes_vendoring import (
    JOB_B_SCOPE_FENCE_ENTRIES,
    RUNTIME_REQUIRED_ENTRIES,
    audit_vendored_agent_history,
    audit_vendored_agent_tree,
    find_retention_import_sites,
)


def _init_git_repo(repo_root: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.name", "Megaplan Tests"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "tests@example.com"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def test_audit_vendored_agent_tree_flags_missing_entries_and_dead_weight(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    agent_root = repo_root / "megaplan" / "agent"
    agent_root.mkdir(parents=True)

    for entry in RUNTIME_REQUIRED_ENTRIES:
        target = agent_root / entry
        if "." in target.name:
            target.write_text("# runtime\n", encoding="utf-8")
        else:
            target.mkdir()

    for entry in JOB_B_SCOPE_FENCE_ENTRIES:
        target = agent_root / entry
        if not target.exists():
            target.mkdir()

    (agent_root / "demo").mkdir()
    (agent_root / "benchmark-output.json").write_text("{}", encoding="utf-8")
    (agent_root / "run_agent.py").unlink()

    audit = audit_vendored_agent_tree(repo_root)

    assert audit.missing_runtime_entries == ["run_agent.py"]
    assert audit.missing_scope_fence_entries == []
    assert audit.unexpected_dead_weight == ["demo"]
    assert audit.root_json_files == ["benchmark-output.json"]


def test_find_retention_import_sites_tracks_runtime_references_outside_retained_dirs(tmp_path: Path) -> None:
    agent_root = tmp_path / "megaplan" / "agent"
    (agent_root / "tools").mkdir(parents=True)
    (agent_root / "tests").mkdir(parents=True)

    (agent_root / "run_agent.py").write_text(
        "from honcho_integration.client import HonchoClient\n",
        encoding="utf-8",
    )
    (agent_root / "tools" / "cronjob_tools.py").write_text(
        "from cron.scheduler import tick\n",
        encoding="utf-8",
    )
    (agent_root / "tools" / "send_message_tool.py").write_text(
        "from gateway.config import load_gateway_config\n",
        encoding="utf-8",
    )
    (agent_root / "tests" / "test_runtime.py").write_text(
        "from gateway.run import GatewayRunner\n",
        encoding="utf-8",
    )

    findings = find_retention_import_sites(agent_root)

    assert findings["honcho_integration"] == ["run_agent.py:1"]
    assert findings["cron"] == ["tools/cronjob_tools.py:1"]
    assert findings["gateway"] == ["tools/send_message_tool.py:1"]


def test_audit_vendored_agent_history_passes_for_multi_commit_git_history(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_git_repo(repo_root)

    tracked_file = repo_root / "megaplan" / "agent" / "run_agent.py"
    tracked_file.parent.mkdir(parents=True)
    tracked_file.write_text("print('v1')\n", encoding="utf-8")
    subprocess.run(["git", "add", "megaplan/agent/run_agent.py"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "add vendored agent"], cwd=repo_root, check=True, capture_output=True, text=True)

    tracked_file.write_text("print('v2')\n", encoding="utf-8")
    subprocess.run(["git", "add", "megaplan/agent/run_agent.py"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "update vendored agent"], cwd=repo_root, check=True, capture_output=True, text=True)

    audit = audit_vendored_agent_history(repo_root)

    assert audit.error is None
    assert audit.tracked is True
    assert audit.preserved_history is True
    assert len(audit.commit_lines) == 2


def test_audit_vendored_agent_history_reports_untracked_copy(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_git_repo(repo_root)

    readme = repo_root / "README.md"
    readme.write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_root, check=True, capture_output=True, text=True)

    untracked_file = repo_root / "megaplan" / "agent" / "run_agent.py"
    untracked_file.parent.mkdir(parents=True)
    untracked_file.write_text("print('copy')\n", encoding="utf-8")

    audit = audit_vendored_agent_history(repo_root)

    assert audit.error is None
    assert audit.tracked is False
    assert audit.preserved_history is False
    assert audit.commit_lines == []
