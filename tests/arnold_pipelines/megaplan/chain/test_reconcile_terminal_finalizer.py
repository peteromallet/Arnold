"""P6 terminal finalizer: close+sweep after a terminal ``kind: reconcile``
milestone (merged / intentionally rejected / verified no-op).

The finalizer (``chain._run_reconcile_terminal_finalizer``) runs arnold-close
then arnold-gc-sweep --restore-proven --fixer-branch ONLY when the reconcile
milestone reached a terminal outcome with no PR awaiting.  These tests
exercise it against a throwaway lifecycle sandbox (bare origin + base repo +
real runtime-create/close/gc-sweep wrappers), asserting the *outcomes*
(manifest closed, worktree removed, fixer branch deleted local+remote) and
the fail-closed gates (non-terminal record, PR still bound, no manifest).

The finalizer is unit-driven: we build a ChainSpec with a reconcile milestone
and a ChainState carrying a terminal completed record, bind
``ARNOLD_RUNTIME_MANIFEST`` to the sandbox manifest, and call the function
directly — no full chain run needed.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.chain import _run_reconcile_terminal_finalizer
from arnold_pipelines.megaplan.chain.spec import (
    ChainSpec,
    ChainState,
    MilestoneSpec,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
WRAPPER_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"
CREATE = WRAPPER_DIR / "arnold-runtime-create"


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
    git(base_repo, "config", "user.name", "Finalizer Tests")
    git(base_repo, "config", "user.email", "finalizer@example.invalid")
    git(base_repo, "config", "commit.gpgsign", "false")
    (base_repo / "README.md").write_text("base seed\n")
    git(base_repo, "add", "-A")
    git(base_repo, "commit", "-m", "seed base")
    git(base_repo, "branch", "-M", "main")
    git(base_repo, "push", "-u", "origin", "main")
    git(base_repo, "branch", "base/editable-install")
    git(base_repo, "push", "origin", "base/editable-install")

    base_dir = tmp_path / "base"
    markers = tmp_path / "markers"
    manifest_dir = markers / "runtime-manifests"
    schedule_store = tmp_path / "schedule-store"
    env = os.environ.copy()
    env.update(
        {
            "ARNOLD_BASE_DIR": str(base_dir),
            "ARNOLD_BASE_REPO": str(base_repo),
            "ARNOLD_WORKSPACE_MARKERS": str(markers),
            "ARNOLD_RUNTIME_MANIFEST_DIR": str(manifest_dir),
            "ARNOLD_RUNTIME_MANIFEST": str(manifest_dir / "runtime-manifest.json"),
            "ARNOLD_ORIGIN_URL": str(origin),
            "ARNOLD_PROMOTION_JOURNAL": str(manifest_dir / "promotion-journal.jsonl"),
            "ARNOLD_SCHEDULE_STORE": str(schedule_store),
            "PYTHONPATH": str(REPO_ROOT),
        }
    )

    def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(script), *args],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
        )

    def origin_heads(branch: str) -> str:
        out = _git(None, "ls-remote", str(origin), f"refs/heads/{branch}").stdout.strip()
        return out.split("\t")[0] if out else ""

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
    }


def _create_runtime(sandbox: dict[str, object], slug: str) -> Path:
    proc = sandbox["run"](CREATE, slug, "base/editable-install")
    assert proc.returncode == 0, proc.stderr
    return Path(sandbox["base_dir"]) / "runtime-candidates" / slug


def _manifest_path(sandbox: dict[str, object], slug: str) -> Path:
    return Path(sandbox["manifest_dir"]) / f"{slug}.json"


def _read_manifest(sandbox: dict[str, object], slug: str) -> dict:
    return json.loads(_manifest_path(sandbox, slug).read_text())


def _reconcile_spec(milestone_label: str = "reconcile") -> ChainSpec:
    return ChainSpec(
        milestones=[
            MilestoneSpec(
                label=milestone_label,
                idea="briefs/reconcile.md",
                branch="reconcile/epic-x-20260811",
                kind="reconcile",
                target_branch="main",
                merge_policy="review",
                phase_model=["execute=codex"],
            )
        ],
        base_branch="main",
        on_failure="stop_chain",
        on_escalate="stop_chain",
    )


def _reconcile_record(
    milestone_label: str = "reconcile",
    *,
    status: str = "done",
    pr_state: str = "merged",
    pr_number: int | None = 42,
    reconcile_verification: str | None = None,
) -> dict:
    record: dict = {
        "label": milestone_label,
        "plan": "plan-reconcile",
        "status": status,
        "pr_number": pr_number,
        "pr_state": pr_state,
        "kind": "reconcile",
        "target_branch": "main",
    }
    if status == "rejected" and "rejection_reason" not in record:
        record["rejection_reason"] = "intentionally rejected by operator"
    if reconcile_verification is not None:
        record["reconcile_verification"] = reconcile_verification
    return record


def _finalize(
    sandbox: dict[str, object],
    spec: ChainSpec,
    state: ChainState,
    *,
    slug: str,
) -> dict:
    """Call the terminal finalizer with ARNOLD_RUNTIME_MANIFEST bound to the
    per-epic sandbox manifest (the box-side session binding)."""
    env = dict(sandbox["env"])
    env["ARNOLD_RUNTIME_MANIFEST"] = str(_manifest_path(sandbox, slug))

    def writer(text: str) -> None:
        pass

    events: list[dict] = []

    def log(msg: str, **fields: object) -> None:
        events.append({"msg": msg, **fields})

    old_env = os.environ.copy()
    os.environ.update(env)
    try:
        result = _run_reconcile_terminal_finalizer(
            root=Path(sandbox["base_repo"]),
            spec_path=Path(sandbox["tmp_path"]) / "chain.yaml",
            spec=spec,
            state=state,
            events=events,
            writer=writer,
            log=log,
        )
    finally:
        os.environ.clear()
        os.environ.update(old_env)
    return result or {"status": "ok", "events": events}


def _plant_chain_store_reference(
    sandbox: dict[str, object], engine_root: str
) -> Path:
    """Plant a chain-state file in the workspace-relative reference-census
    chain store carrying an ``engine_root`` path reference.

    The census (runtime_references, T-0012) matches path values by EXACT
    normalized equality with the swept runtime root: a present path is
    REFERENCED, a missing path is DANGLING, corrupt JSON is UNKNOWN — the
    exact fail-closed verdicts ``arnold-gc-sweep`` surfaces as SKIP /
    NEEDS-RECONCILE / exit-5 BLOCK."""
    store_dir = Path(sandbox["base_dir"]) / ".megaplan" / "plans" / ".chains"
    store_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "label": "planted",
        "metadata": {"execution_environment": {"engine_root": engine_root}},
    }
    path = store_dir / "chain-planted.json"
    path.write_text(json.dumps(payload))
    return path


# ── terminal outcomes → close + sweep ────────────────────────────────────────


def test_finalizer_merged_reconcile_closes_and_sweeps(sandbox: dict[str, object]) -> None:
    worktree = _create_runtime(sandbox, "epic-final")
    manifest = _read_manifest(sandbox, "epic-final")
    fixer_branch = manifest["epic"]["branch"]
    assert manifest["state"] == "active"
    assert sandbox["origin_heads"](fixer_branch)

    spec = _reconcile_spec()
    state = ChainState(
        current_milestone_index=1,
        last_state="done",
        pr_number=None,
        pr_state=None,
        completed=[_reconcile_record()],
    )
    result = _finalize(sandbox, spec, state, slug="epic-final")
    assert result["status"] == "ok"
    assert "arnold-close completed" in " ".join(
        event["msg"] for event in result["events"]
    )
    assert "arnold-gc-sweep completed" in " ".join(
        event["msg"] for event in result["events"]
    )
    # manifest closed + worktree removed + fixer branch deleted local+remote
    closed_manifest = json.loads(
        (Path(sandbox["manifest_dir"]) / "archived" / "epic-final.json").read_text()
    )
    assert closed_manifest["state"] == "closed"
    assert not worktree.exists()
    gone = _git(Path(sandbox["base_repo"]), "rev-parse", "--verify", fixer_branch)
    assert gone.returncode != 0
    assert not sandbox["origin_heads"](fixer_branch)
    # durable evidence on chain state: CLEAR sweep → swept:true + completion
    evidence = state.metadata["reconcile_terminal_finalizer"]
    assert evidence["outcome"] == "merged"
    assert evidence["swept"] is True
    assert evidence["sweep_outcome"] == "SWEPT"


def test_finalizer_rejected_reconcile_closes_and_sweeps(
    sandbox: dict[str, object],
) -> None:
    worktree = _create_runtime(sandbox, "epic-reject")
    manifest = _read_manifest(sandbox, "epic-reject")
    fixer_branch = manifest["epic"]["branch"]

    spec = _reconcile_spec()
    state = ChainState(
        current_milestone_index=1,
        last_state="done",
        pr_number=None,
        pr_state=None,
        completed=[
            _reconcile_record(status="rejected", pr_state="closed", pr_number=7)
        ],
    )
    result = _finalize(sandbox, spec, state, slug="epic-reject")
    assert result["status"] == "ok"
    assert not worktree.exists()
    assert not sandbox["origin_heads"](fixer_branch)
    assert state.metadata["reconcile_terminal_finalizer"]["outcome"] == "rejected"


def test_finalizer_noop_reconcile_closes_and_sweeps(sandbox: dict[str, object]) -> None:
    worktree = _create_runtime(sandbox, "epic-noop")
    fixer_branch = _read_manifest(sandbox, "epic-noop")["epic"]["branch"]

    spec = _reconcile_spec()
    state = ChainState(
        current_milestone_index=1,
        last_state="done",
        pr_number=None,
        pr_state=None,
        completed=[
            _reconcile_record(
                pr_number=None,
                pr_state=None,
                reconcile_verification="noop",
            )
        ],
    )
    result = _finalize(sandbox, spec, state, slug="epic-noop")
    assert result["status"] == "ok"
    assert not worktree.exists()
    assert not sandbox["origin_heads"](fixer_branch)
    assert state.metadata["reconcile_terminal_finalizer"]["outcome"] == "noop"


# ── swept truth: CLEAR vs skipped/blocked sweep (G6 round-3 finding 2) ───────


def test_finalizer_referenced_sweep_skip_fails_closed(
    sandbox: dict[str, object],
) -> None:
    """A sweep that exits 0 but SKIPs the runtime (REFERENCED census
    verdict) must record swept:false and BLOCK — the completion guard never
    collapses to terminal completion on top of a live, referenced runtime
    (E5/F collapse-to-success)."""
    worktree = _create_runtime(sandbox, "epic-ref")
    fixer_branch = _read_manifest(sandbox, "epic-ref")["epic"]["branch"]
    _plant_chain_store_reference(sandbox, str(worktree))

    spec = _reconcile_spec()
    state = ChainState(
        current_milestone_index=1,
        last_state="done",
        pr_number=None,
        pr_state=None,
        completed=[_reconcile_record()],
    )
    result = _finalize(sandbox, spec, state, slug="epic-ref")
    assert result["status"] == "blocked"
    assert "did not remove runtime" in result["reason"]
    assert "REFERENCED" in result["reason"]
    # close ran (manifest closed) but the runtime was NOT removed
    assert worktree.is_dir()
    assert _read_manifest(sandbox, "epic-ref")["state"] == "closed"
    assert sandbox["origin_heads"](fixer_branch)
    evidence = state.metadata["reconcile_terminal_finalizer"]
    assert evidence["swept"] is False
    assert "REFERENCED" in evidence["sweep_reason"]


def test_finalizer_dangling_sweep_skip_fails_closed(
    sandbox: dict[str, object],
) -> None:
    """A DANGLING census verdict makes the sweep report NEEDS-RECONCILE
    (exit 0, runtime untouched): swept:false + blocked, never a false
    completion."""
    worktree = _create_runtime(sandbox, "epic-dang")
    fixer_branch = _read_manifest(sandbox, "epic-dang")["epic"]["branch"]
    _plant_chain_store_reference(
        sandbox, str(Path(sandbox["base_dir"]) / "runtime-candidates" / "ghost")
    )

    spec = _reconcile_spec()
    state = ChainState(
        current_milestone_index=1,
        last_state="done",
        pr_number=None,
        pr_state=None,
        completed=[_reconcile_record()],
    )
    result = _finalize(sandbox, spec, state, slug="epic-dang")
    assert result["status"] == "blocked"
    assert "did not remove runtime" in result["reason"]
    assert "DANGLING" in result["reason"]
    assert worktree.is_dir()
    assert sandbox["origin_heads"](fixer_branch)
    evidence = state.metadata["reconcile_terminal_finalizer"]
    assert evidence["swept"] is False
    assert "DANGLING" in evidence["sweep_reason"]


def test_finalizer_unknown_sweep_block_fails_closed(
    sandbox: dict[str, object],
) -> None:
    """An UNKNOWN census verdict (unreadable/corrupt store) makes the sweep
    BLOCK with exit 5: swept:false + blocked, the runtime is never reported
    gone (delete-on-unknown never happens)."""
    worktree = _create_runtime(sandbox, "epic-unk")
    fixer_branch = _read_manifest(sandbox, "epic-unk")["epic"]["branch"]
    store_dir = Path(sandbox["base_dir"]) / ".megaplan" / "plans" / ".chains"
    store_dir.mkdir(parents=True, exist_ok=True)
    (store_dir / "chain-corrupt.json").write_text("{not json")

    spec = _reconcile_spec()
    state = ChainState(
        current_milestone_index=1,
        last_state="done",
        pr_number=None,
        pr_state=None,
        completed=[_reconcile_record()],
    )
    result = _finalize(sandbox, spec, state, slug="epic-unk")
    assert result["status"] == "blocked"
    assert "arnold-gc-sweep failed" in result["reason"]
    assert "exit 5" in result["reason"]
    assert worktree.is_dir()
    assert sandbox["origin_heads"](fixer_branch)
    evidence = state.metadata["reconcile_terminal_finalizer"]
    assert evidence["swept"] is False
    assert evidence["sweep_outcome"] == "UNKNOWN"


# ── idempotency ──────────────────────────────────────────────────────────────


def test_finalizer_is_idempotent_across_close_then_sweep_crash(
    sandbox: dict[str, object],
) -> None:
    """Crash between close and sweep heals: a closed manifest with a surviving
    worktree re-runs close (no-op) and completes the sweep."""
    worktree = _create_runtime(sandbox, "epic-crash")
    fixer_branch = _read_manifest(sandbox, "epic-crash")["epic"]["branch"]

    spec = _reconcile_spec()
    state = ChainState(
        current_milestone_index=1,
        last_state="done",
        pr_number=None,
        pr_state=None,
        completed=[_reconcile_record()],
    )
    # First run: close only (simulate the sweep failing by planting a pull ref
    # that refuses the branch deletion; then remove it and re-run).
    env = dict(sandbox["env"])
    env["ARNOLD_RUNTIME_MANIFEST"] = str(_manifest_path(sandbox, "epic-crash"))
    head = sandbox["origin_heads"](fixer_branch)
    git(Path(sandbox["base_repo"]), "update-ref", "refs/pull/99/head", head)
    git(
        Path(sandbox["base_repo"]),
        "push",
        str(sandbox["origin"]),
        "refs/pull/99/head",
    )

    def writer(text: str) -> None:
        pass

    def log(msg: str, **fields: object) -> None:
        pass

    old_env = os.environ.copy()
    os.environ.update(env)
    try:
        first = _run_reconcile_terminal_finalizer(
            root=Path(sandbox["base_repo"]),
            spec_path=Path(sandbox["tmp_path"]) / "chain.yaml",
            spec=spec,
            state=state,
            events=[],
            writer=writer,
            log=log,
        )
    finally:
        os.environ.clear()
        os.environ.update(old_env)
    # close succeeded but the open-PR gate refused the sweep → blocked
    assert first is not None
    assert first["status"] == "blocked"
    assert "arnold-gc-sweep failed" in first["reason"]
    assert worktree.is_dir()
    assert _read_manifest(sandbox, "epic-crash")["state"] == "closed"

    # resolve the PR (remove the pull ref) and re-run: sweep completes
    git(Path(sandbox["base_repo"]), "update-ref", "-d", "refs/pull/99/head")
    git(
        Path(sandbox["base_repo"]),
        "push",
        str(sandbox["origin"]),
        "--delete",
        "refs/pull/99/head",
    )
    result = _finalize(sandbox, spec, state, slug="epic-crash")
    assert result["status"] == "ok"
    assert not worktree.exists()
    assert not sandbox["origin_heads"](fixer_branch)


def test_finalizer_second_run_after_sweep_is_noop(sandbox: dict[str, object]) -> None:
    """After a full close+sweep the manifest is archived: a re-run skips
    (idempotent) instead of failing."""
    worktree = _create_runtime(sandbox, "epic-twice")
    spec = _reconcile_spec()
    state = ChainState(
        current_milestone_index=1,
        last_state="done",
        pr_number=None,
        pr_state=None,
        completed=[_reconcile_record()],
    )
    first = _finalize(sandbox, spec, state, slug="epic-twice")
    assert first["status"] == "ok"
    assert not worktree.exists()

    second = _finalize(sandbox, spec, state, slug="epic-twice")
    assert second["status"] == "ok"
    assert any("already gone" in event["msg"] for event in second["events"])


# ── manifest presence triage: absent vs present-but-unreadable ──────────────


def test_finalizer_dangling_manifest_symlink_fails_closed(
    sandbox: dict[str, object],
) -> None:
    """G5 round-5 finding 3(a): a DANGLING manifest symlink is PRESENT but
    unreadable.  ``is_file()`` follows the link to its missing target and
    reports False, which the old guard collapsed to 'already gone' and let
    the chain complete (done) on top of a broken runtime.  The finalizer
    must fail CLOSED with a typed blocked result — never an idempotent skip,
    never done — and never run close/sweep."""
    worktree = _create_runtime(sandbox, "epic-sym")
    manifest = _manifest_path(sandbox, "epic-sym")
    manifest.unlink()
    manifest.symlink_to(manifest.parent / "missing-target.json")
    assert manifest.is_symlink()
    assert not manifest.exists()  # stat() follows the link: ENOENT

    spec = _reconcile_spec()
    state = ChainState(
        current_milestone_index=1,
        last_state="done",
        pr_number=None,
        pr_state=None,
        completed=[_reconcile_record()],
    )
    result = _finalize(sandbox, spec, state, slug="epic-sym")
    assert result["status"] == "blocked"
    assert "present but unreadable" in result["reason"]
    assert "reconcile_terminal_finalizer" not in state.metadata
    assert worktree.is_dir()  # nothing was closed or swept
    assert manifest.is_symlink()  # the broken entry is left for the operator


def test_finalizer_absent_manifest_stays_idempotent_skip(
    sandbox: dict[str, object],
) -> None:
    """A GENUINELY absent bound manifest (never created, or archived by a
    previous sweep) is an idempotent skip — 'already gone', chain completes
    done.  Only ENOENT on the entry itself (stat AND lstat) may take this
    path; a dangling symlink cannot."""
    spec = _reconcile_spec()
    state = ChainState(
        current_milestone_index=1,
        last_state="done",
        pr_number=None,
        pr_state=None,
        completed=[_reconcile_record()],
    )
    result = _finalize(sandbox, spec, state, slug="epic-never-existed")
    assert result["status"] == "ok"
    assert any("already gone" in event["msg"] for event in result["events"])
    assert "reconcile_terminal_finalizer" not in state.metadata


# ── fail-closed gates: never close on unknown / awaiting / unbound ──────────


def test_finalizer_refuses_non_terminal_record(sandbox: dict[str, object]) -> None:
    """An open/unknown PR record is NOT terminal — close+sweep must not run."""
    worktree = _create_runtime(sandbox, "epic-unknown")
    fixer_branch = _read_manifest(sandbox, "epic-unknown")["epic"]["branch"]

    spec = _reconcile_spec()
    state = ChainState(
        current_milestone_index=0,
        last_state="blocked",
        pr_number=42,
        pr_state="open",
        completed=[],
    )
    result = _finalize(sandbox, spec, state, slug="epic-unknown")
    assert result["status"] == "ok"
    assert _read_manifest(sandbox, "epic-unknown")["state"] == "active"
    assert worktree.is_dir()
    assert sandbox["origin_heads"](fixer_branch)
    assert "reconcile_terminal_finalizer" not in state.metadata


def test_finalizer_refuses_awaiting_pr_merge(sandbox: dict[str, object]) -> None:
    worktree = _create_runtime(sandbox, "epic-await")
    spec = _reconcile_spec()
    state = ChainState(
        current_milestone_index=0,
        last_state="awaiting_pr_merge",
        pr_number=42,
        pr_state="open",
        completed=[],
    )
    result = _finalize(sandbox, spec, state, slug="epic-await")
    assert result["status"] == "ok"
    assert _read_manifest(sandbox, "epic-await")["state"] == "active"
    assert worktree.is_dir()


def test_finalizer_skips_without_session_manifest(sandbox: dict[str, object]) -> None:
    """No session manifest binding (local dev) ⇒ nothing to close, no-op."""
    worktree = _create_runtime(sandbox, "epic-unbound")
    spec = _reconcile_spec()
    state = ChainState(
        current_milestone_index=1,
        last_state="done",
        pr_number=None,
        pr_state=None,
        completed=[_reconcile_record()],
    )
    env = dict(sandbox["env"])
    env.pop("ARNOLD_RUNTIME_MANIFEST", None)

    def writer(text: str) -> None:
        pass

    def log(msg: str, **fields: object) -> None:
        pass

    old_env = os.environ.copy()
    os.environ.update(env)
    try:
        result = _run_reconcile_terminal_finalizer(
            root=Path(sandbox["base_repo"]),
            spec_path=Path(sandbox["tmp_path"]) / "chain.yaml",
            spec=spec,
            state=state,
            events=[],
            writer=writer,
            log=log,
        )
    finally:
        os.environ.clear()
        os.environ.update(old_env)
    assert result is None
    assert _read_manifest(sandbox, "epic-unbound")["state"] == "active"
    assert worktree.is_dir()


def test_finalizer_noop_without_reconcile_milestone(sandbox: dict[str, object]) -> None:
    """A chain with no kind:reconcile milestone never triggers the finalizer."""
    worktree = _create_runtime(sandbox, "epic-plain")
    spec = ChainSpec(
        milestones=[
            MilestoneSpec(label="m1", idea="brief.md", branch="fixer/m1")
        ],
        base_branch="main",
    )
    state = ChainState(
        current_milestone_index=1,
        last_state="done",
        pr_number=None,
        pr_state=None,
        completed=[{"label": "m1", "status": "done"}],
    )
    result = _finalize(sandbox, spec, state, slug="epic-plain")
    assert result["status"] == "ok"
    assert _read_manifest(sandbox, "epic-plain")["state"] == "active"
    assert worktree.is_dir()
