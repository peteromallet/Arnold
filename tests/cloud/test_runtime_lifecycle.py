"""Tests for the per-epic runtime lifecycle wrappers (fixer-unification design
Phases 4-5; docs/runtime-and-fixer-unification-design-20260807.md rows 12-15).

The wrappers are bash candidates, exercised against a throwaway sandbox:
a bare git repo plays 'origin', a seeded clone plays the base source repo,
and ARNOLD_* env overrides redirect every path the scripts touch. The tests
assert the *outcomes* (worktree created/pushed, manifest state, journal lines,
worktree removed) rather than which writer path the scripts took, so they pass
whether or not the runtime_manifest module is present.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"

CREATE = WRAPPER_DIR / "arnold-runtime-create"
PROMOTE = WRAPPER_DIR / "arnold-promote"
CLOSE = WRAPPER_DIR / "arnold-close"
GC_SWEEP = WRAPPER_DIR / "arnold-gc-sweep"


def _git(cwd: Path | None, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *(("-C", str(cwd)) if cwd else ()), *args],
        capture_output=True,
        text=True,
    )


def git(cwd: Path | None, *args: str) -> str:
    proc = _git(cwd, *args)
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return proc.stdout.strip()


@pytest.fixture
def sandbox(tmp_path: Path) -> dict[str, object]:
    origin = tmp_path / "origin.git"
    git(None, "init", "--bare", str(origin))
    base_repo = tmp_path / "base-repo"
    base_repo.mkdir()
    git(None, "init", str(base_repo))
    git(base_repo, "remote", "add", "origin", str(origin))
    git(base_repo, "config", "user.name", "Lifecycle Tests")
    git(base_repo, "config", "user.email", "lifecycle@example.invalid")
    git(base_repo, "config", "commit.gpgsign", "false")
    (base_repo / "README.md").write_text("base seed\n")
    git(base_repo, "add", "-A")
    git(base_repo, "commit", "-m", "seed base")
    git(base_repo, "branch", "-M", "main")
    git(base_repo, "push", "-u", "origin", "main")
    git(base_repo, "branch", "base/editable-install")
    git(base_repo, "push", "origin", "base/editable-install")
    seed_sha = git(base_repo, "rev-parse", "base/editable-install")

    base_dir = tmp_path / "base"
    markers = tmp_path / "markers"
    manifest_dir = markers / "runtime-manifests"
    env = os.environ.copy()
    env.update(
        {
            "ARNOLD_BASE_DIR": str(base_dir),
            "ARNOLD_BASE_REPO": str(base_repo),
            "ARNOLD_WORKSPACE_MARKERS": str(markers),
            "ARNOLD_RUNTIME_MANIFEST_DIR": str(manifest_dir),
            "ARNOLD_ORIGIN_URL": str(origin),
            "ARNOLD_PROMOTION_JOURNAL": str(manifest_dir / "promotion-journal.jsonl"),
            "PYTHONPATH": str(REPO_ROOT),
        }
    )

    def run(
        script: Path,
        *args: str,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        full_env = dict(env)
        if extra_env:
            full_env.update(extra_env)
        return subprocess.run(
            [str(script), *args],
            cwd=str(REPO_ROOT),
            env=full_env,
            capture_output=True,
            text=True,
        )

    def origin_heads(branch: str) -> str:
        out = _git(None, "ls-remote", str(origin), f"refs/heads/{branch}").stdout.strip()
        return out.split("\t")[0] if out else ""

    def create(slug: str, base_ref: str = "base/editable-install") -> Path:
        proc = run(CREATE, slug, base_ref)
        assert proc.returncode == 0, proc.stderr
        return base_dir / "runtime-candidates" / slug

    return {
        "tmp_path": tmp_path,
        "origin": origin,
        "base_repo": base_repo,
        "base_dir": base_dir,
        "markers": markers,
        "manifest_dir": manifest_dir,
        "env": env,
        "run": run,
        "origin_heads": origin_heads,
        "create": create,
        "seed_sha": seed_sha,
    }


def manifest_path(sandbox: dict[str, object], slug: str) -> Path:
    return Path(sandbox["manifest_dir"]) / f"{slug}.json"


def read_manifest(sandbox: dict[str, object], slug: str) -> dict:
    return json.loads(manifest_path(sandbox, slug).read_text())


def epic_commit(worktree: Path, filename: str, content: str, message: str) -> str:
    (worktree / filename).write_text(content)
    git(worktree, "add", "-A")
    git(worktree, "commit", "-m", message)
    return git(worktree, "rev-parse", "HEAD")


# ── arnold-runtime-create ────────────────────────────────────────────────────


def test_runtime_create_worktree_pushed_manifest(sandbox: dict[str, object]) -> None:
    worktree = sandbox["create"]("epic-a")
    assert worktree.is_dir()
    assert (worktree / ".git").exists()
    branch = git(worktree, "branch", "--show-current")
    assert branch.startswith("fixer/epic-a-")
    local_head = git(worktree, "rev-parse", "HEAD")
    # branch pushed to origin at creation (design rule 4)
    assert sandbox["origin_heads"](branch) == local_head
    # manifest written with the full mandatory field set
    m = read_manifest(sandbox, "epic-a")
    assert m["epic_id"] == "epic-a"
    assert m["state"] == "active"
    assert m["schema"] == "1"
    assert m["generation"] >= 1
    assert m["runtime_id"].startswith("epic-a-")
    assert m["epic"]["runtime_root"] == str(worktree)
    assert m["epic"]["worktree_path"] == str(worktree)
    assert m["epic"]["branch"] == branch
    assert m["epic"]["expected_head"] == local_head
    assert m["base"]["commit"] == local_head
    assert m["base"]["ref"] == "base/editable-install"
    assert m["timestamps"]["created"]
    assert isinstance(m["promotions"], list)
    # guard: same slug refuses with exit 2
    again = sandbox["run"](CREATE, "epic-a", "base/editable-install")
    assert again.returncode == 2


def test_runtime_create_fails_loudly_on_push_failure(sandbox: dict[str, object]) -> None:
    proc = sandbox["run"](
        CREATE,
        "epic-push-fail",
        "base/editable-install",
        extra_env={
            "ARNOLD_ORIGIN_URL": str(Path(sandbox["tmp_path"]) / "missing-origin.git")
        },
    )
    assert proc.returncode != 0
    assert "push" in proc.stderr.lower()
    # manifest must NOT be written: push precedes the manifest write
    assert not manifest_path(sandbox, "epic-push-fail").exists()


# ── arnold-close ─────────────────────────────────────────────────────────────


def test_close_phase1_fails_on_dirty_tree(sandbox: dict[str, object]) -> None:
    worktree = sandbox["create"]("epic-dirty")
    (worktree / "uncommitted.txt").write_text("dirty\n")
    proc = sandbox["run"](CLOSE, "epic-dirty", str(manifest_path(sandbox, "epic-dirty")))
    assert proc.returncode != 0
    assert "phase-1" in proc.stderr.lower()
    assert read_manifest(sandbox, "epic-dirty")["state"] == "active"  # unchanged


def test_close_phase1_fails_on_open_lock_file(sandbox: dict[str, object]) -> None:
    sandbox["create"]("epic-locked")
    (Path(sandbox["markers"]) / "repair.lock").mkdir(parents=True, exist_ok=True)
    proc = sandbox["run"](CLOSE, "epic-locked", str(manifest_path(sandbox, "epic-locked")))
    assert proc.returncode != 0
    assert "lock" in proc.stderr.lower()
    assert read_manifest(sandbox, "epic-locked")["state"] == "active"


def test_close_closes_clean_pushed_epic(sandbox: dict[str, object]) -> None:
    sandbox["create"]("epic-clean")
    proc = sandbox["run"](CLOSE, "epic-clean", str(manifest_path(sandbox, "epic-clean")))
    assert proc.returncode == 0, proc.stderr
    m = read_manifest(sandbox, "epic-clean")
    assert m["state"] == "closed"
    assert m["timestamps"]["closed"]
    assert "box-snapshot" in proc.stdout  # backstop-tag instruction printed, not run


# ── arnold-gc-sweep ──────────────────────────────────────────────────────────


def test_gc_sweep_dry_run_then_restore_proven_removes(sandbox: dict[str, object]) -> None:
    worktree = sandbox["create"]("epic-gc")
    close = sandbox["run"](CLOSE, "epic-gc", str(manifest_path(sandbox, "epic-gc")))
    assert close.returncode == 0, close.stderr

    dry = sandbox["run"](GC_SWEEP, "--dry-run", str(sandbox["manifest_dir"]))
    assert dry.returncode == 0, dry.stderr
    assert "WOULD-SWEEP" in dry.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-gc").exists()

    no_proof = sandbox["run"](GC_SWEEP, str(sandbox["manifest_dir"]))
    assert no_proof.returncode == 0, no_proof.stderr
    assert "restore" in no_proof.stdout.lower()  # SKIP: not restore-proven
    assert worktree.is_dir()

    (Path(sandbox["manifest_dir"]) / "restore-proven.txt").write_text(
        "clean-room restore drilled 2026-08-07\n"
    )
    sweep = sandbox["run"](GC_SWEEP, "--restore-proven", str(sandbox["manifest_dir"]))
    assert sweep.returncode == 0, sweep.stderr
    assert "SWEPT" in sweep.stdout
    assert not worktree.exists()
    assert not manifest_path(sandbox, "epic-gc").exists()
    assert (Path(sandbox["manifest_dir"]) / "archived" / "epic-gc.json").exists()


def test_gc_sweep_never_removes_active_manifest_tree(sandbox: dict[str, object]) -> None:
    worktree = sandbox["create"]("epic-live")
    (Path(sandbox["manifest_dir"]) / "restore-proven.txt").write_text("proof\n")
    proc = sandbox["run"](GC_SWEEP, "--restore-proven", str(sandbox["manifest_dir"]))
    assert proc.returncode == 0, proc.stderr
    assert "SKIP" in proc.stdout
    assert "active" in proc.stdout.lower()
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-live").exists()


def test_gc_sweep_lists_manifestless_tree_as_needs_reconcile(
    sandbox: dict[str, object],
) -> None:
    # runner death mid-epic: a tree with no manifest must never be deleted
    stray = Path(sandbox["base_dir"]) / "runtime-candidates" / "orphan-tree"
    git(
        Path(sandbox["base_repo"]),
        "worktree",
        "add",
        "-b",
        "fixer/orphan-tree-20260807",
        str(stray),
        "base/editable-install",
    )
    proc = sandbox["run"](GC_SWEEP, "--restore-proven", str(sandbox["manifest_dir"]))
    assert proc.returncode == 0, proc.stderr
    assert "NEEDS-RECONCILE" in proc.stdout
    assert stray.is_dir()  # never deleted


# ── arnold-promote ───────────────────────────────────────────────────────────


def test_promote_fails_when_epic_branch_unpushed(sandbox: dict[str, object]) -> None:
    worktree = sandbox["create"]("epic-unpushed")
    epic_commit(worktree, "fix.txt", "fix\n", "epic fix (unpushed)")
    proc = sandbox["run"](
        PROMOTE,
        "--force-gate",
        "epic-unpushed",
        str(manifest_path(sandbox, "epic-unpushed")),
    )
    assert proc.returncode != 0
    assert "push" in proc.stderr.lower()


def test_promote_gate_blocks_without_marker_or_flag(sandbox: dict[str, object]) -> None:
    sandbox["create"]("epic-gated")
    proc = sandbox["run"](PROMOTE, "epic-gated", str(manifest_path(sandbox, "epic-gated")))
    assert proc.returncode != 0
    assert "gate" in proc.stderr.lower()
    assert sandbox["origin_heads"]("base/editable-install")  # base untouched


def test_promote_cas_push_journal_warning(sandbox: dict[str, object]) -> None:
    worktree = sandbox["create"]("epic-promo")
    branch = git(worktree, "branch", "--show-current")
    head = epic_commit(worktree, "fix.txt", "durable fix\n", "durable fix")
    git(worktree, "push", "origin", f"HEAD:refs/heads/{branch}")
    from_sha = sandbox["origin_heads"]("base/editable-install")

    proc = sandbox["run"](
        PROMOTE,
        "--force-gate",
        "epic-promo",
        str(manifest_path(sandbox, "epic-promo")),
    )
    assert proc.returncode == 0, proc.stderr
    # compare-and-swap push landed on the base branch (no force involved)
    assert sandbox["origin_heads"]("base/editable-install") == head
    # design warning: a successful push is NOT a safe cutover
    assert "NOT a safe cutover" in proc.stdout
    # promotion journal line appended
    journal = Path(str(sandbox["env"]["ARNOLD_PROMOTION_JOURNAL"]))
    lines = [json.loads(line) for line in journal.read_text().splitlines()]
    assert lines and lines[-1]["slug"] == "epic-promo"
    assert lines[-1]["from_sha"] == from_sha
    assert lines[-1]["to_sha"] == head
    assert lines[-1]["result"] == "pushed"
    assert lines[-1]["at"]
    # manifest promotions[] mirror updated
    m = read_manifest(sandbox, "epic-promo")
    assert m["promotions"] and m["promotions"][-1]["to_sha"] == head


def test_promote_cas_rejection_exits_3(sandbox: dict[str, object]) -> None:
    wt_a = sandbox["create"]("epic-a")
    branch_a = git(wt_a, "branch", "--show-current")
    head_a = epic_commit(wt_a, "a.txt", "a\n", "epic-a fix")
    git(wt_a, "push", "origin", f"HEAD:refs/heads/{branch_a}")
    proc_a = sandbox["run"](PROMOTE, "--force-gate", "epic-a", str(manifest_path(sandbox, "epic-a")))
    assert proc_a.returncode == 0, proc_a.stderr
    assert sandbox["origin_heads"]("base/editable-install") == head_a

    # a concurrent promotion advances base behind our back (fast-forward from origin)
    git(Path(sandbox["base_repo"]), "fetch", "origin")
    git(
        Path(sandbox["base_repo"]),
        "checkout",
        "-B",
        "base/editable-install",
        "origin/base/editable-install",
    )
    (Path(sandbox["base_repo"]) / "competing.txt").write_text("competing\n")
    git(Path(sandbox["base_repo"]), "add", "-A")
    git(Path(sandbox["base_repo"]), "commit", "-m", "competing promotion")
    competing = git(Path(sandbox["base_repo"]), "rev-parse", "HEAD")
    git(Path(sandbox["base_repo"]), "push", "origin", "base/editable-install")
    assert sandbox["origin_heads"]("base/editable-install") == competing

    # a second epic forked from the PRE-competition base: promoting it cannot
    # fast-forward onto the competing base -> CAS push must be rejected
    wt_b = sandbox["create"]("epic-b", base_ref=str(sandbox["seed_sha"]))
    branch_b = git(wt_b, "branch", "--show-current")
    epic_commit(wt_b, "b.txt", "b\n", "epic-b fix")
    git(wt_b, "push", "origin", f"HEAD:refs/heads/{branch_b}")
    proc_b = sandbox["run"](
        PROMOTE,
        "--force-gate",
        "epic-b",
        str(manifest_path(sandbox, "epic-b")),
    )
    assert proc_b.returncode == 3
    assert "rejected" in proc_b.stderr.lower() or "cas" in proc_b.stderr.lower()
    # base unchanged by the rejected push
    assert sandbox["origin_heads"]("base/editable-install") == competing
