"""Tests for the Phase-0 runtime census (process execution map)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.runtime_attestation import _git_revision, _sha256_file
from arnold_pipelines.megaplan.cloud.runtime_census import (
    GitTreeState,
    MountRecord,
    RuntimeProcess,
    _collect_process,
    census_git_trees,
    main,
    mask_cmdline,
    render_census_markdown,
)


def _make_git_repo(
    root: Path,
    files: dict[str, str] | None = None,
    *,
    commit: bool = True,
) -> None:
    """Initialize a real git repo at *root* (optionally committing *files*)."""
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(root), "init", "-q", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "census@test"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "census"], check=True)
    paths = dict(files or {})
    paths.setdefault("README.md", "census test\n")
    for rel, content in paths.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    if commit:
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(root), "-c", "commit.gpgsign=false", "commit", "-q", "-m", "seed"],
            check=True,
        )


def _sample_process(**overrides: object) -> RuntimeProcess:
    values = {
        "pid": 4242,
        "ppid": 1,
        "cmdline": "python3 arnold-watchdog",
        "cwd": "/workspace/arnold",
        "exe": "/usr/bin/python3",
        "environ": ("ARNOLD_API_KEY",),
        "tree_path": "/workspace/arnold",
        "tree_head": "a" * 40,
        "tree_branch": "main",
        "tree_dirty_count": 0,
        "module_file": "/workspace/arnold/arnold_pipelines/megaplan/cloud/current_target.py",
        "module_digest": "d" * 64,
    }
    values.update(overrides)
    return RuntimeProcess(**values)  # type: ignore[arg-type]


# ── census_git_trees ────────────────────────────────────────────────────────


def test_census_git_trees_lists_repo_and_non_repo(tmp_path: Path) -> None:
    root = tmp_path / "candidates"
    tree_a = root / "tree-a"
    _make_git_repo(tree_a)
    (root / "not-a-repo").mkdir(parents=True)

    states = census_git_trees(root)
    by_name = {state.tree_name: state for state in states}
    assert set(by_name) == {"tree-a", "not-a-repo"}

    repo = by_name["tree-a"]
    expected_head = subprocess.run(
        ["git", "-C", str(tree_a), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert repo.is_git is True
    assert repo.head_sha == expected_head
    assert repo.branch == "main"
    assert repo.dirty_count == 0

    plain = by_name["not-a-repo"]
    assert plain.is_git is False
    assert plain.head_sha == ""
    assert plain.branch == ""
    assert plain.dirty_count == -1


def test_census_git_trees_dirty_count_covers_modified_and_untracked(tmp_path: Path) -> None:
    root = tmp_path / "candidates"
    tree = root / "tree"
    _make_git_repo(tree, {"README.md": "seed\n"})

    assert census_git_trees(root)[0].dirty_count == 0

    (tree / "untracked.txt").write_text("new\n", encoding="utf-8")
    (tree / "README.md").write_text("modified\n", encoding="utf-8")
    assert census_git_trees(root)[0].dirty_count == 2


def test_census_git_trees_missing_root_is_empty(tmp_path: Path) -> None:
    assert census_git_trees(tmp_path / "nope") == []


def test_census_git_trees_does_not_flag_subdirs_inside_a_repo(tmp_path: Path) -> None:
    """A subdir of an enclosing repo is not a candidate tree of its own."""
    root = tmp_path / "candidates"
    _make_git_repo(root)
    inner = root / "inner-dir"
    inner.mkdir()

    states = census_git_trees(root)
    assert {state.tree_name for state in states} == {"inner-dir"}
    assert states[0].is_git is False
    assert states[0].head_sha == ""


# ── process collection (injected /proc seam) ────────────────────────────────


def _make_fake_proc_dir(proc_root: Path, pid: int, tree: Path) -> Path:
    pid_dir = proc_root / str(pid)
    pid_dir.mkdir(parents=True)
    (pid_dir / "cmdline").write_bytes(f"python3 arnold-watchdog\0".encode())
    (pid_dir / "environ").write_bytes(
        f"MEGAPLAN_RUNTIME_SRC={tree}\0ARNOLD_API_KEY=sekrit\0".encode()
    )
    (pid_dir / "stat").write_text(
        f"{pid} (arnold-watchdog) S 1 {pid} 1 34816 {pid} 4194304 0\n",
        encoding="utf-8",
    )
    (pid_dir / "cwd").symlink_to(tree, target_is_directory=True)
    (pid_dir / "exe").symlink_to("/usr/bin/python3")
    (pid_dir / "maps").write_text(
        "00000000-00001000 r-xp 00000000 00:00 0 /usr/bin/python3\n"
        f"00001000-00002000 r-xp 00000000 00:00 0 "
        f"{tree}/arnold_pipelines/megaplan/cloud/current_target.py\n",
        encoding="utf-8",
    )
    return pid_dir


def test_collect_process_resolves_tree_and_module(tmp_path: Path) -> None:
    tree = (tmp_path / "candidates" / "tree").resolve()
    module = tree / "arnold_pipelines" / "megaplan" / "cloud" / "current_target.py"
    _make_git_repo(
        tree,
        {"arnold_pipelines/megaplan/cloud/current_target.py": "def resolve():\n    pass\n"},
    )

    pid_dir = _make_fake_proc_dir(tmp_path / "proc", 4242, tree)
    proc = _collect_process(pid_dir)

    assert proc is not None
    assert proc.pid == 4242
    assert proc.ppid == 1
    assert proc.cwd == str(tree)
    assert proc.exe == "/usr/bin/python3"
    assert proc.tree_path == str(tree)
    assert proc.tree_head == _git_revision(tree)
    assert proc.tree_branch == "main"
    assert proc.tree_dirty_count == 0
    assert proc.module_file == str(module)
    assert proc.module_digest == _sha256_file(module)
    # environ carries NAMES only by default; values never leak
    assert "ARNOLD_API_KEY" in proc.environ
    assert "MEGAPLAN_RUNTIME_SRC" in proc.environ
    assert "sekrit" not in " ".join(proc.environ)


def test_collect_process_include_values_keeps_values_for_debugging(tmp_path: Path) -> None:
    tree = (tmp_path / "candidates" / "tree").resolve()
    _make_git_repo(tree, {"README.md": "seed\n"})
    pid_dir = _make_fake_proc_dir(tmp_path / "proc", 7, tree)

    proc = _collect_process(pid_dir, include_values=True)
    assert proc is not None
    entries = dict(entry.split("=", 1) for entry in proc.environ)
    assert entries["ARNOLD_API_KEY"] == "sekrit"
    assert entries["MEGAPLAN_RUNTIME_SRC"] == str(tree)


# ── masking ─────────────────────────────────────────────────────────────────


def test_mask_cmdline_redacts_keylike_flags_and_assignments() -> None:
    assert mask_cmdline("export GITHUB_TOKEN=ghp_abc123 run") == (
        "export GITHUB_TOKEN=<redacted> run"
    )
    assert mask_cmdline("arnold-run --api-key=abc --plan-name demo") == (
        "arnold-run --api-key=<redacted> --plan-name demo"
    )
    assert mask_cmdline("run --verbose --token 123456") == (
        "run --verbose --token <redacted>"
    )
    assert mask_cmdline("--password='hunter2'") == "--password=<redacted>"
    # non-secret content is untouched
    assert mask_cmdline("python arnold-watchdog --chain demo") == (
        "python arnold-watchdog --chain demo"
    )


def test_render_masks_environ_values_and_keylike_cmdline() -> None:
    proc = _sample_process(
        cmdline="python3 arnold-watchdog --api-key=sekrit123 --token abc456",
        environ=("ARNOLD_API_KEY=sekrit123", "MEGAPLAN_RUNTIME_SRC=/hidden-value-xyz"),
        include_values=True,
    )
    out = render_census_markdown([proc], [], [])
    assert "sekrit123" not in out
    assert "abc456" not in out
    assert "hidden-value-xyz" not in out
    assert "=sekrit123" not in out
    assert "<redacted>" in out
    # variable NAMES are shown; values never are
    assert "ARNOLD_API_KEY" in out
    assert "MEGAPLAN_RUNTIME_SRC" in out


# ── render determinism ──────────────────────────────────────────────────────


def test_render_census_markdown_is_deterministic() -> None:
    a = _sample_process(pid=10, cmdline="python arnold-watchdog")
    b = _sample_process(pid=5, cmdline="python megaplan-supervise")
    c = _sample_process(pid=7, cmdline="python arnold-repair-loop")
    trees = [
        GitTreeState("t1", "a" * 40, "main", 0, True),
        GitTreeState("t2", "", "", -1, False),
    ]
    mounts = [MountRecord("/workspace/arnold", "/mnt/ro/arnold", True, "ext4")]

    first = render_census_markdown([a, b, c], trees, mounts)
    second = render_census_markdown(list(reversed([a, b, c])), list(reversed(trees)), list(reversed(mounts)))
    assert first == second
    assert first == render_census_markdown([a, b, c], trees, mounts)
    # processes render sorted by pid
    assert first.index("| 5 |") < first.index("| 7 |") < first.index("| 10 |")


# ── CLI ─────────────────────────────────────────────────────────────────────


def test_main_exit_zero_with_no_git_repos(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = tmp_path / "candidates"
    (root / "plain-dir").mkdir(parents=True)

    rc = main(["--trees-root", str(root)])
    out = capsys.readouterr().out

    assert rc == 0
    assert "# Runtime Census" in out
    assert "plain-dir" in out
    assert "not a git repository" in out
