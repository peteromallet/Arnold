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

import hashlib
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
    # T-0301: the frozen dependency spec (pyproject.toml + uv.lock pair) that
    # every created runtime's dependency generation is content-addressed
    # from.  Zero dependencies and a project-only (editable-sourced) lock so
    # the pip build path installs nothing and stays hermetic/offline.
    (base_repo / "pyproject.toml").write_text(
        "[project]\n"
        'name = "sandbox-arnold"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.9"\n'
        "dependencies = []\n",
        encoding="utf-8",
    )
    (base_repo / "uv.lock").write_text(
        'version = 1\n'
        'requires-python = ">=3.9"\n'
        "\n"
        "[[package]]\n"
        'name = "sandbox-arnold"\n'
        'version = "0.1.0"\n'
        'source = { editable = "." }\n',
        encoding="utf-8",
    )
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
    schedule_store = tmp_path / "schedule-store"
    # T-0301: the shared content-addressed dependency-generation store root
    # (one immutable venv per frozen-spec digest; every runtime resolving the
    # same spec shares the venv).  The build strategy is pinned to pip so the
    # sandbox builds are hermetic/offline (the sandbox uv.lock has zero
    # installable packages).
    gen_dir = base_dir / "runtime-venvs"
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
            "ARNOLD_RUNTIME_VENVS_DIR": str(gen_dir),
            "ARNOLD_REFERENCE_RUNTIME_VENVS_DIR": str(gen_dir),
            "ARNOLD_GENERATION_BUILD_STRATEGY": "pip",
            # Reference-census stores (T-0012): sandbox-scoped so the sweep's
            # census never reads host stores.  These dirs are absent unless a
            # fixture populates them (a missing store is not a reference).
            "ARNOLD_REFERENCE_CHAIN_STORE": str(tmp_path / "ref-chains"),
            "ARNOLD_REFERENCE_MARKER_STORE": str(tmp_path / "ref-markers"),
            "ARNOLD_REFERENCE_REPAIR_QUEUE": str(tmp_path / "ref-repair-queue"),
            "ARNOLD_REFERENCE_LEASE_STORE": str(tmp_path / "ref-leases"),
            "ARNOLD_REFERENCE_PLAN_LEASE_ROOT": str(tmp_path / "ref-plan-leases"),
            "ARNOLD_REFERENCE_MANAGED_RUN_STORE": str(tmp_path / "ref-managed-runs"),
            "ARNOLD_REFERENCE_STATUS_DIR": str(tmp_path / "ref-status"),
            "ARNOLD_REFERENCE_OPS_STORE": str(tmp_path / "ref-ops"),
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


@pytest.fixture
def git_spy(tmp_path: Path) -> dict[str, object]:
    """PATH shim: fake `git` AND `rm` binaries that log every invocation then
    pass through to the real ones.  Lets the GC tests prove destructive calls
    (worktree remove, branch -D, push --delete, AND the epic-venv `rm -rf`)
    are never issued on a referenced or unknown runtime root / venv."""
    spy_dir = tmp_path / "git-spy"
    spy_dir.mkdir()
    real_git = subprocess.run(
        ["bash", "-lc", "command -v git"], capture_output=True, text=True
    ).stdout.strip()
    assert real_git, "real git not resolvable for the spy shim"
    (spy_dir / "git").write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"${GIT_SPY_LOG:?}\"\n"
        f'exec "{real_git}" "$@"\n'
    )
    (spy_dir / "git").chmod(0o755)
    real_rm = subprocess.run(
        ["bash", "-lc", "command -v rm"], capture_output=True, text=True
    ).stdout.strip()
    assert real_rm, "real rm not resolvable for the spy shim"
    (spy_dir / "rm").write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"${RM_SPY_LOG:?}\"\n"
        f'exec "{real_rm}" "$@"\n'
    )
    (spy_dir / "rm").chmod(0o755)
    log = tmp_path / "git-spy.log"
    rm_log = tmp_path / "rm-spy.log"
    return {"dir": spy_dir, "log": log, "rm_log": rm_log, "real_git": real_git}


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
    # T-0301: NO per-worktree .venv fiction — the venv is the SHARED
    # content-addressed dependency generation, and the manifest binds its
    # complete proof (id = frozen-spec digest).
    gen_dir = Path(str(sandbox["env"]["ARNOLD_RUNTIME_VENVS_DIR"]))
    assert m["epic"]["venv_path"] != f"{worktree}/.venv"
    assert not str(m["epic"]["venv_path"]).startswith(str(worktree))
    assert m["base"]["venv_path"] == m["epic"]["venv_path"]
    assert str(m["epic"]["venv_path"]).startswith(str(gen_dir))
    generation = m["epic"]["dependency_generation"]
    assert set(generation) >= {
        "id",
        "frozen_spec_sha256",
        "interpreter_path",
        "venv_digest",
        "created",
    }
    assert generation["id"] == generation["frozen_spec_sha256"]
    assert generation["interpreter_path"] == f"{m['epic']['venv_path']}/bin/python"
    assert Path(generation["interpreter_path"]).is_file()
    # the generation dir is the content-addressed store entry
    assert Path(m["epic"]["venv_path"]).name == generation["id"]
    assert (
        m["epic"]["repair_bin"]
        == f"{worktree}/arnold_pipelines/megaplan/cloud/wrappers/arnold-babysitter"
    )
    assert m["epic"]["deps_lockfile"] == f"{worktree}/uv.lock"
    # policy SHAs computed from the canonical policy modules (best-effort)
    assert m["policy"]["policy_sha"]
    assert m["policy"]["model_policy_sha"]
    # content attestation keys present (schema-required; probe may be empty)
    assert set(m["indirection"]["attestation"]) >= {
        "module_file",
        "module_digest",
        "mount_id",
    }
    # ACTIVE POINTER written as compatibility telemetry ONLY (G1
    # no-global-pointer fallback): it reflects this epic but is demoted and
    # never bootstraps — the per-slug manifest is authoritative
    pointer = Path(str(sandbox["env"]["ARNOLD_RUNTIME_MANIFEST"]))
    assert pointer.exists()
    p = json.loads(pointer.read_text())
    assert p["epic_id"] == "epic-a"
    assert p["state"] == "active"
    assert p["generation"] == 1
    assert p["compatibility_only"] is True
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


# ── P1 admission kernel: deviations + compatibility-only pointer ─────────────


def _valid_permit(**overrides: str) -> dict:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    permit = {
        "kind": "allow_manifestless",
        "id": "permit-abc123",
        "issued_at": (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actor": "operator@example.invalid",
        "reason": "manifestless admission permit for lifecycle tests",
        "evidence": ["chain override --allow-manifestless --reason lifecycle-test"],
        "chain_digest": "deadbeefdeadbeef",
    }
    permit.update(overrides)
    return permit


def _write_policy_sidecar(sandbox: dict[str, object], permit: dict) -> Path:
    policy_path = Path(sandbox["tmp_path"]) / "runtime-policy.json"
    policy_path.write_text(json.dumps({"allow_manifestless": permit}, sort_keys=True) + "\n")
    return policy_path


def test_runtime_create_deviations_empty_and_pointer_compatibility_only(
    sandbox: dict[str, object],
) -> None:
    sandbox["create"]("epic-plain")
    # deviations defaults to [] when no ARNOLD_RUNTIME_POLICY sidecar is set
    m = read_manifest(sandbox, "epic-plain")
    assert m["deviations"] == []
    # the global active pointer is demoted to compatibility-only (G1
    # no-global-pointer fallback): it is written ONCE with the marker in the
    # same payload (G2 second re-run) and NEVER bootstraps — every resolver
    # treats it as ABSENT for admission
    pointer = Path(str(sandbox["env"]["ARNOLD_RUNTIME_MANIFEST"]))
    assert pointer.exists()
    p = json.loads(pointer.read_text())
    assert p["epic_id"] == "epic-plain"
    assert p["compatibility_only"] is True


def test_pointer_compatibility_only_survives_promote_and_close(
    sandbox: dict[str, object],
) -> None:
    """G2 second re-run: the global pointer's compatibility_only demotion is
    DURABLE — the marker survives create -> promote (advance_generation) ->
    close (set_state), so no resolver can ever admit the pointer."""
    from arnold_pipelines.megaplan.cloud.runtime_manifest import (
        ManifestError,
        bootstrap_manifest,
        is_compatibility_only_pointer,
        manifest_present,
    )

    worktree = sandbox["create"]("epic-durable")
    branch = git(worktree, "branch", "--show-current")
    head = epic_commit(worktree, "fix.txt", "durable fix\n", "durable fix")
    git(worktree, "push", "origin", f"HEAD:refs/heads/{branch}")
    pointer = Path(str(sandbox["env"]["ARNOLD_RUNTIME_MANIFEST"]))

    # create: pointer carries the marker from the FIRST (only) pointer write
    assert json.loads(pointer.read_text())["compatibility_only"] is True
    assert is_compatibility_only_pointer(pointer) is True

    # promote: advance_generation rewrites the pointer — the marker survives
    proc = sandbox["run"](
        PROMOTE,
        "--force-gate",
        "epic-durable",
        str(manifest_path(sandbox, "epic-durable")),
        extra_env={"ARNOLD_PROMOTE_SKIP_CANARY": "1"},
    )
    assert proc.returncode == 0, proc.stderr
    p = json.loads(pointer.read_text())
    assert p["compatibility_only"] is True
    assert p["generation"] == 2
    assert p["epic"]["expected_head"] == head

    # close: pointer set_state keeps the marker AND the closed state
    close = sandbox["run"](
        CLOSE, "epic-durable", str(manifest_path(sandbox, "epic-durable"))
    )
    assert close.returncode == 0, close.stderr
    p = json.loads(pointer.read_text())
    assert p["compatibility_only"] is True
    assert p["state"] == "closed"

    # no resolver admits the pointer: the lib gate treats it as ABSENT
    assert manifest_present(pointer) is False
    with pytest.raises(ManifestError, match="compatibility_only"):
        bootstrap_manifest(pointer)


def test_runtime_create_stamps_allow_manifestless_permit_into_deviations(
    sandbox: dict[str, object],
) -> None:
    permit = _valid_permit()
    policy_path = _write_policy_sidecar(sandbox, permit)
    proc = sandbox["run"](
        CREATE,
        "epic-permitted",
        "base/editable-install",
        extra_env={"ARNOLD_RUNTIME_POLICY": str(policy_path)},
    )
    assert proc.returncode == 0, proc.stderr
    m = read_manifest(sandbox, "epic-permitted")
    assert len(m["deviations"]) == 1
    stamped = m["deviations"][0]
    assert stamped["kind"] == "allow_manifestless"
    assert stamped["id"] == permit["id"]
    assert stamped["actor"] == permit["actor"]
    assert stamped["reason"] == permit["reason"]
    assert stamped["chain_digest"] == permit["chain_digest"]
    assert stamped["issued_at"] == permit["issued_at"]
    assert stamped["expires_at"] == permit["expires_at"]
    assert stamped["evidence"] == permit["evidence"]


def test_runtime_create_fails_loudly_on_expired_permit(sandbox: dict[str, object]) -> None:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    expired = _valid_permit(
        id="permit-expired",
        issued_at=(now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        expires_at=(now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    policy_path = _write_policy_sidecar(sandbox, expired)
    proc = sandbox["run"](
        CREATE,
        "epic-expired",
        "base/editable-install",
        extra_env={"ARNOLD_RUNTIME_POLICY": str(policy_path)},
    )
    assert proc.returncode != 0
    assert "permit" in proc.stderr.lower()
    # deny-by-default: creation must not proceed without recording the
    # declared deviation — the manifest is never written
    assert not manifest_path(sandbox, "epic-expired").exists()


def test_runtime_create_fails_loudly_on_invalid_permit_duration(
    sandbox: dict[str, object],
) -> None:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    too_long = _valid_permit(
        id="permit-too-long",
        issued_at=(now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        expires_at=(now + timedelta(hours=25)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    policy_path = _write_policy_sidecar(sandbox, too_long)
    proc = sandbox["run"](
        CREATE,
        "epic-duration",
        "base/editable-install",
        extra_env={"ARNOLD_RUNTIME_POLICY": str(policy_path)},
    )
    assert proc.returncode != 0
    assert "permit" in proc.stderr.lower()
    assert not manifest_path(sandbox, "epic-duration").exists()


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
    worktree = sandbox["create"]("epic-clean")
    proc = sandbox["run"](CLOSE, "epic-clean", str(manifest_path(sandbox, "epic-clean")))
    assert proc.returncode == 0, proc.stderr
    m = read_manifest(sandbox, "epic-clean")
    assert m["state"] == "closed"
    assert m["timestamps"]["closed"]
    # backstop tag EXECUTED: present locally AND on the origin (fail-loud push)
    assert "box-snapshot" in proc.stdout
    assert "pushed" in proc.stdout
    local_tags = _git(worktree, "tag", "--list", "box-snapshot/epic-clean-*").stdout.strip()
    assert local_tags
    remote_tags = _git(
        None, "ls-remote", str(sandbox["origin"]), "refs/tags/box-snapshot/epic-clean-*"
    ).stdout.strip()
    assert remote_tags
    # the active pointer (compatibility-only telemetry held by this epic at
    # creation) is closed too AND stays demoted — pointer set_state must not
    # strip the marker (G2 second re-run)
    pointer = Path(str(sandbox["env"]["ARNOLD_RUNTIME_MANIFEST"]))
    p = json.loads(pointer.read_text())
    assert p["state"] == "closed"
    assert p["compatibility_only"] is True
    # close wrote the content-addressed restore receipt binding the
    # manifest's content-addressed identities to the closed HEAD (close
    # structurally PRECEDES restore-proven GC)
    receipt = _restore_receipt_path(sandbox, "epic-clean")
    assert receipt.exists()
    payload = json.loads(receipt.read_text())
    assert payload["schema"] == "restore-receipt/v1"
    assert payload["epic_id"] == "epic-clean"
    assert payload["runtime_id"] == m["runtime_id"]
    assert payload["runtime_root"] == m["epic"]["runtime_root"]
    assert (
        payload["dependency_generation_id"]
        == m["epic"]["dependency_generation"]["id"]
    )
    assert payload["closed_head"] == git(worktree, "rev-parse", "HEAD")
    digest = hashlib.sha256(
        json.dumps(
            {k: v for k, v in payload.items() if k != "content_sha256"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert payload["content_sha256"] == digest


def test_close_refuses_unresolved_reconcile_branch_on_origin(
    sandbox: dict[str, object],
) -> None:
    """P6 terminal-state rules: standalone close REFUSES while a
    ``refs/heads/reconcile/<slug>-*`` branch still exists on the remote — the
    generated reconcile milestone's PR branch was never merged or
    intentionally rejected, so reconcile work is still pending.  Nothing is
    mutated: no backstop tag, no state change, no receipt."""
    worktree = sandbox["create"]("epic-recopen")
    git(worktree, "checkout", "-b", "reconcile/epic-recopen-20260812")
    epic_commit(worktree, "pending.txt", "pending\n", "reconcile work (unresolved)")
    git(
        worktree,
        "push",
        "origin",
        "HEAD:refs/heads/reconcile/epic-recopen-20260812",
    )
    assert sandbox["origin_heads"]("reconcile/epic-recopen-20260812")

    proc = sandbox["run"](
        CLOSE, "epic-recopen", str(manifest_path(sandbox, "epic-recopen"))
    )
    assert proc.returncode != 0
    assert "unresolved reconcile" in proc.stderr.lower()
    assert read_manifest(sandbox, "epic-recopen")["state"] == "active"
    assert worktree.is_dir()
    assert not _restore_receipt_path(sandbox, "epic-recopen").exists()
    # no backstop tag was created or pushed
    assert not _git(
        None, "ls-remote", str(sandbox["origin"]), "refs/tags/box-snapshot/epic-recopen-*"
    ).stdout.strip()


def test_close_refuses_open_pull_ref_on_fixer_branch(
    sandbox: dict[str, object],
) -> None:
    """Standalone close REFUSES while an open pull ref on the remote points
    at the manifest-declared fixer branch head (the epic's PR is still open
    and load-bearing) — close mutates nothing."""
    worktree = sandbox["create"]("epic-propen")
    branch = read_manifest(sandbox, "epic-propen")["epic"]["branch"]
    head = sandbox["origin_heads"](branch)
    assert head
    git(Path(sandbox["base_repo"]), "update-ref", "refs/pull/321/head", head)
    git(Path(sandbox["base_repo"]), "push", str(sandbox["origin"]), "refs/pull/321/head")

    proc = sandbox["run"](
        CLOSE, "epic-propen", str(manifest_path(sandbox, "epic-propen"))
    )
    assert proc.returncode != 0
    assert "pull ref" in proc.stderr.lower()
    assert read_manifest(sandbox, "epic-propen")["state"] == "active"
    assert worktree.is_dir()
    assert not _restore_receipt_path(sandbox, "epic-propen").exists()


def test_close_proceeds_once_reconcile_resolved(sandbox: dict[str, object]) -> None:
    """Once the reconcile is RESOLVED (the PR branch deleted on origin after
    merge or intentional rejection), standalone close succeeds even while
    the worktree still sits on the (now-remote-less) reconcile branch — the
    fixer branch is verified as a ref, and close writes the receipt."""
    worktree = sandbox["create"]("epic-recdone")
    git(worktree, "checkout", "-b", "reconcile/epic-recdone-20260812")
    epic_commit(worktree, "done.txt", "done\n", "reconcile work (resolved)")
    git(worktree, "push", "origin", "HEAD:refs/heads/reconcile/epic-recdone-20260812")
    # merged / intentionally rejected: the P6 flow deletes the PR branch
    git(
        Path(sandbox["base_repo"]),
        "push",
        str(sandbox["origin"]),
        "--delete",
        "refs/heads/reconcile/epic-recdone-20260812",
    )
    assert not sandbox["origin_heads"]("reconcile/epic-recdone-20260812")

    proc = sandbox["run"](
        CLOSE, "epic-recdone", str(manifest_path(sandbox, "epic-recdone"))
    )
    assert proc.returncode == 0, proc.stderr
    assert read_manifest(sandbox, "epic-recdone")["state"] == "closed"
    assert _restore_receipt_path(sandbox, "epic-recdone").exists()


def test_close_phase1_fails_on_live_pidfile(sandbox: dict[str, object]) -> None:
    sandbox["create"]("epic-livepid")
    pidfile = Path(sandbox["markers"]) / "epic-livepid.repair-loop.pid"
    pidfile.write_text(str(os.getpid()))  # the pytest process is live
    proc = sandbox["run"](
        CLOSE, "epic-livepid", str(manifest_path(sandbox, "epic-livepid"))
    )
    assert proc.returncode != 0
    assert "live" in proc.stderr.lower()
    assert read_manifest(sandbox, "epic-livepid")["state"] == "active"


def test_close_ignores_dead_pidfile(sandbox: dict[str, object]) -> None:
    worktree = sandbox["create"]("epic-deadpid")
    pidfile = Path(sandbox["markers"]) / "epic-deadpid.repair-loop.pid"
    pidfile.write_text("2147483647\n")  # no such process (best-effort liveness)
    proc = sandbox["run"](
        CLOSE, "epic-deadpid", str(manifest_path(sandbox, "epic-deadpid"))
    )
    assert proc.returncode == 0, proc.stderr
    assert read_manifest(sandbox, "epic-deadpid")["state"] == "closed"


def test_close_fails_loud_when_backstop_tag_push_fails(sandbox: dict[str, object]) -> None:
    from datetime import datetime

    worktree = sandbox["create"]("epic-tagfail")
    branch = git(worktree, "branch", "--show-current")
    head = epic_commit(worktree, "fix.txt", "fix\n", "epic fix")
    git(worktree, "push", "origin", f"HEAD:refs/heads/{branch}")
    # plant a CONFLICTING tag on origin: same name as the backstop, other sha
    stamp = datetime.now().strftime("%Y%m%d")
    tag = f"box-snapshot/epic-tagfail-{stamp}"
    git(Path(sandbox["base_repo"]), "tag", tag, str(sandbox["seed_sha"]))
    git(Path(sandbox["base_repo"]), "push", "origin", tag)
    proc = sandbox["run"](
        CLOSE, "epic-tagfail", str(manifest_path(sandbox, "epic-tagfail"))
    )
    assert proc.returncode != 0
    assert "backstop" in proc.stderr.lower()
    # close aborted: the epic is NOT closed without an origin-resolvable backstop
    assert read_manifest(sandbox, "epic-tagfail")["state"] == "active"


def test_close_refuses_present_but_corrupt_manifest(sandbox: dict[str, object]) -> None:
    """T-0024: arnold-close reads the manifest with raw field reads but fails
    closed on a PRESENT-but-corrupt manifest — it must refuse (non-zero)
    before touching state, never treat the corrupt manifest as empty/absent
    and proceed with a close."""
    worktree = sandbox["create"]("epic-closecorrupt")
    manifest = manifest_path(sandbox, "epic-closecorrupt")
    original = manifest.read_text(encoding="utf-8")
    manifest.write_text("{not valid json", encoding="utf-8")
    proc = sandbox["run"](
        CLOSE, "epic-closecorrupt", str(manifest)
    )
    assert proc.returncode != 0
    assert worktree.is_dir()
    # the on-disk manifest is untouched: close neither rewrote nor archived it
    assert manifest.read_text(encoding="utf-8") == "{not valid json"
    manifest.write_text(original, encoding="utf-8")
    assert read_manifest(sandbox, "epic-closecorrupt")["state"] == "active"


# ── arnold-gc-sweep ──────────────────────────────────────────────────────────


def test_gc_sweep_dry_run_then_restore_proven_removes(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """T-0027 discipline: a CLI flag is NEVER restore evidence.  After close
    (which itself writes the content-addressed restore receipt), the sweep
    proceeds WITHOUT any flag.  But with the receipt LOST, neither
    ``--restore-proven`` alone nor a ``restore-proven.txt`` marker alone may
    delete anything — only a validating content-addressed receipt does."""
    worktree = sandbox["create"]("epic-gc")
    close = sandbox["run"](CLOSE, "epic-gc", str(manifest_path(sandbox, "epic-gc")))
    assert close.returncode == 0, close.stderr
    assert _restore_receipt_path(sandbox, "epic-gc").exists()

    dry = sandbox["run"](GC_SWEEP, "--dry-run", str(sandbox["manifest_dir"]))
    assert dry.returncode == 0, dry.stderr
    assert "WOULD-SWEEP" in dry.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-gc").exists()

    # the receipt (written by close) IS the evidence: a plain sweep — no
    # --restore-proven flag — removes the closed, receipt-proven runtime
    no_flag = _sweep_with_spy(
        sandbox, git_spy, str(sandbox["manifest_dir"])
    )
    assert no_flag.returncode == 0, no_flag.stderr
    assert "SWEPT=YES 'epic-gc'" in no_flag.stdout
    assert not worktree.exists()
    assert not manifest_path(sandbox, "epic-gc").exists()
    assert (Path(sandbox["manifest_dir"]) / "archived" / "epic-gc.json").exists()


def test_gc_sweep_flag_alone_is_not_restore_evidence(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """A CLI flag alone (--restore-proven) with NO content-addressed receipt
    must SKIP with ZERO deletion — the flag is intent, not evidence."""
    worktree = sandbox["create"]("epic-flagonly")
    close = sandbox["run"](
        CLOSE, "epic-flagonly", str(manifest_path(sandbox, "epic-flagonly"))
    )
    assert close.returncode == 0, close.stderr
    # lose the restore evidence: the receipt never made it durable
    _delete_restore_receipt(sandbox, "epic-flagonly")

    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "not restore-proven" in proc.stdout
    assert "SWEPT=YES" not in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-flagonly").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_text_marker_is_not_restore_evidence(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """A restore-proven.txt marker (the legacy evidence) with NO
    content-addressed receipt must ALSO SKIP with zero deletion — only the
    per-slug receipt validates (T-0504: flag/txt alone are never evidence)."""
    worktree = sandbox["create"]("epic-markeronly")
    close = sandbox["run"](
        CLOSE, "epic-markeronly", str(manifest_path(sandbox, "epic-markeronly"))
    )
    assert close.returncode == 0, close.stderr
    _delete_restore_receipt(sandbox, "epic-markeronly")
    (Path(sandbox["manifest_dir"]) / "restore-proven.txt").write_text(
        "clean-room restore drilled 2026-08-07\n"
    )

    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "not restore-proven" in proc.stdout
    assert "SWEPT=YES" not in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-markeronly").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_torn_receipt_is_not_restore_evidence(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """A receipt whose content no longer matches its self-digest (torn after
    close, or hand-edited) is NOT restore evidence — SKIP, zero deletion."""
    worktree = sandbox["create"]("epic-torn")
    close = sandbox["run"](
        CLOSE, "epic-torn", str(manifest_path(sandbox, "epic-torn"))
    )
    assert close.returncode == 0, close.stderr
    receipt = _restore_receipt_path(sandbox, "epic-torn")
    assert receipt.exists()
    payload = json.loads(receipt.read_text())
    payload["restore_drill"] = "tampered after close"
    receipt.write_text(json.dumps(payload), encoding="utf-8")  # digest now stale

    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "not restore-proven" in proc.stdout
    assert "SWEPT=YES" not in proc.stdout
    assert worktree.is_dir()
    _assert_no_destructive(git_spy)


def test_gc_sweep_receipt_bound_to_other_epic_is_not_restore_evidence(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """A receipt bound to a DIFFERENT epic (epic_id mismatch) is not
    evidence for this manifest — SKIP, zero deletion."""
    worktree = sandbox["create"]("epic-otherrec")
    close = sandbox["run"](
        CLOSE, "epic-otherrec", str(manifest_path(sandbox, "epic-otherrec"))
    )
    assert close.returncode == 0, close.stderr
    _delete_restore_receipt(sandbox, "epic-otherrec")
    _write_restore_receipt(
        sandbox, "epic-otherrec", worktree=worktree, epic_id="epic-someone-else"
    )

    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "not restore-proven" in proc.stdout
    assert "SWEPT=YES" not in proc.stdout
    assert worktree.is_dir()
    _assert_no_destructive(git_spy)


def test_gc_sweep_stale_closed_head_receipt_is_not_restore_evidence(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """A receipt whose closed_head no longer matches the LIVE worktree HEAD
    (the tree moved after close) is stale evidence — SKIP, zero deletion."""
    worktree = sandbox["create"]("epic-stalehead")
    close = sandbox["run"](
        CLOSE, "epic-stalehead", str(manifest_path(sandbox, "epic-stalehead"))
    )
    assert close.returncode == 0, close.stderr
    closed_head = git(worktree, "rev-parse", "HEAD")
    _delete_restore_receipt(sandbox, "epic-stalehead")
    # a receipt bound to the CLOSED head exists...
    _write_restore_receipt(
        sandbox, "epic-stalehead", worktree=worktree, closed_head=closed_head
    )
    # ...but the tree advances after close AND is pushed (origin-resolvable,
    # so the receipt's closed_head binding is the only remaining gate): the
    # receipt is stale evidence
    branch = read_manifest(sandbox, "epic-stalehead")["epic"]["branch"]
    epic_commit(worktree, "late.txt", "late\n", "post-close commit")
    git(worktree, "push", "origin", f"HEAD:refs/heads/{branch}")

    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "not restore-proven" in proc.stdout
    assert "closed_head" in proc.stdout
    assert "SWEPT=YES" not in proc.stdout
    assert worktree.is_dir()
    _assert_no_destructive(git_spy)


def test_gc_sweep_never_removes_active_manifest_tree(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """Close PRECEDES restore-proven GC: even a VALID content-addressed
    restore receipt cannot sweep an ACTIVE (never-closed) manifest — the
    sweep never runs before close, no matter how strong the receipt looks
    (design rule 0/6: an executing/editable runtime is never deleted)."""
    worktree = sandbox["create"]("epic-live")
    _write_restore_receipt(sandbox, "epic-live", worktree=worktree)
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "SKIP" in proc.stdout
    assert "active" in proc.stdout.lower()
    assert "SWEPT=YES" not in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-live").exists()
    _assert_no_destructive(git_spy)


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


def test_gc_sweep_corrupt_manifest_needs_reconcile_never_deletes(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """T-0024: a PRESENT-but-corrupt manifest is not an empty state and not
    absent — the tree it names must be listed NEEDS-RECONCILE (never
    deletable) and the sweep must keep going instead of aborting or
    collapsing to an empty STATE that could look sweepable."""
    worktree = sandbox["create"]("epic-corruptmanifest")
    corrupt = manifest_path(sandbox, "epic-corruptmanifest")
    corrupt.write_text("{not valid json", encoding="utf-8")
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "NEEDS-RECONCILE" in proc.stdout
    assert "corrupt" in proc.stdout.lower()
    assert "SWEPT" not in proc.stdout
    assert worktree.is_dir()  # the corrupt-manifest tree is never deleted
    assert corrupt.exists()
    _assert_no_destructive(git_spy)
    # dry-run reports the same NEEDS-RECONCILE verdict for the same tree
    dry = _sweep_with_spy(
        sandbox, git_spy, "--dry-run", "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert dry.returncode == 0, dry.stderr
    assert "NEEDS-RECONCILE" in dry.stdout
    assert worktree.is_dir()


def test_gc_sweep_schema_invalid_manifest_needs_reconcile_never_deletes(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G5 round-2 finding 4: a PRESENT manifest that is valid JSON but
    schema-invalid (missing required fields) must fail closed EXACTLY like a
    corrupt manifest — NEEDS-RECONCILE, never deletable.  The payload keeps
    all four fields the old raw json.load read (epic_id / state /
    epic.runtime_root / epic.branch, with a real origin-resolvable branch and
    an existing worktree) so the old code would have swept it; only the
    canonical load_manifest gate stands between it and deletion."""
    worktree = sandbox["create"]("epic-schemainvalid")
    real = read_manifest(sandbox, "epic-schemainvalid")
    schema_invalid = manifest_path(sandbox, "epic-schemainvalid")
    # valid JSON, wrong structure: field-bearing but missing the required
    # top-level fields (runtime_id, schema, generation, owner, base, ...)
    schema_invalid.write_text(
        json.dumps(
            {
                "epic_id": "epic-schemainvalid",
                "state": "closed",
                "epic": {
                    "runtime_root": str(worktree),
                    "branch": real["epic"]["branch"],
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "NEEDS-RECONCILE" in proc.stdout
    assert "SWEPT" not in proc.stdout
    assert worktree.is_dir()  # the schema-invalid manifest's tree is never deleted
    assert schema_invalid.exists()
    _assert_no_destructive(git_spy)
    # dry-run reports the same NEEDS-RECONCILE verdict for the same tree
    dry = _sweep_with_spy(
        sandbox, git_spy, "--dry-run", "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert dry.returncode == 0, dry.stderr
    assert "NEEDS-RECONCILE" in dry.stdout
    assert worktree.is_dir()


def test_gc_sweep_dangling_manifest_symlink_needs_reconcile(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G5 round-5 finding 3(b): a DANGLING manifest symlink is PRESENT but
    unreadable.  ``[[ -f ]]``/``[[ -e ]]`` follow the link to its missing
    target and report false, so the old ``[[ -f ]] || continue`` guard
    silently skipped the manifest (and its tree was never accounted).  The
    sweep must report NEEDS-RECONCILE for the manifest — only a GENUINELY
    absent manifest (ENOENT) may be skipped."""
    worktree = sandbox["create"]("epic-symmanifest")
    dangling = manifest_path(sandbox, "epic-symmanifest")
    dangling.unlink()
    dangling.symlink_to(dangling.parent / "missing-target.json")
    assert dangling.is_symlink()
    assert not dangling.exists()  # -f / -e follow the link: false

    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "NEEDS-RECONCILE manifest" in proc.stdout
    assert "SWEPT" not in proc.stdout
    assert worktree.is_dir()  # the dangling manifest's tree is never deleted
    assert dangling.is_symlink()
    _assert_no_destructive(git_spy)
    # dry-run reports the same NEEDS-RECONCILE verdict for the same tree
    dry = _sweep_with_spy(
        sandbox, git_spy, "--dry-run", "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert dry.returncode == 0, dry.stderr
    assert "NEEDS-RECONCILE manifest" in dry.stdout
    assert worktree.is_dir()


def test_gc_sweep_absent_manifests_are_not_needs_reconcile(
    sandbox: dict[str, object],
) -> None:
    """G5 round-5 finding 3(b) absent side: a manifest dir with no *.json
    files (nothing ever created, or all archived by previous sweeps) is NOT
    a needs-reconcile signal — the sweep completes cleanly.  Only a
    PRESENT-but-unreadable entry is NEEDS-RECONCILE."""
    proc = sandbox["run"](
        GC_SWEEP, "--dry-run", "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "NEEDS-RECONCILE" not in proc.stdout
    assert "done" in proc.stdout


# ── T-0301 / G10 B2: generation-store negative controls ─────────────────────


def test_gc_sweep_corrupt_generation_store_blocks_deletion_with_exit5(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G10 B2 (b): a PRESENT hex-named generation dir without a valid
    .generation.json proof makes the reference census UNKNOWN, and the sweep
    must BLOCK with exit 5 and ZERO deletions — delete-on-unknown never
    happens, even for a closed, origin-resolvable, restore-proven runtime.
    Deleting the generation-store scan from the census turns this into a
    successful sweep and the test fails."""
    worktree = sandbox["create"]("epic-genunknown")
    close = sandbox["run"](
        CLOSE, "epic-genunknown", str(manifest_path(sandbox, "epic-genunknown"))
    )
    assert close.returncode == 0, close.stderr
    # Plant a hex-named generation entry with NO proof beside the real one.
    gen_root = Path(str(sandbox["env"]["ARNOLD_RUNTIME_VENVS_DIR"]))
    assert gen_root.is_dir()
    corrupt_entry = gen_root / ("b" * 64)
    corrupt_entry.mkdir(parents=True)
    assert not (corrupt_entry / ".generation.json").exists()

    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 5, (proc.stdout, proc.stderr)
    assert "UNKNOWN" in proc.stderr, proc.stderr
    assert "generation" in proc.stderr.lower(), proc.stderr
    assert "SWEPT=YES" not in proc.stdout, proc.stdout
    assert worktree.is_dir()  # the tree is never deleted
    assert manifest_path(sandbox, "epic-genunknown").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_manifest_without_generation_proof_needs_reconcile_never_deletes(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G10 B2 (c): a CLOSED manifest whose dependency-generation proof is
    missing cannot attest its dependency state — the sweep must report
    NEEDS-RECONCILE for it (T-0301 fail-closed) and never delete the tree,
    even with --restore-proven and a healthy generation store."""
    worktree = sandbox["create"]("epic-nodepgen")
    close = sandbox["run"](
        CLOSE, "epic-nodepgen", str(manifest_path(sandbox, "epic-nodepgen"))
    )
    assert close.returncode == 0, close.stderr
    mf = manifest_path(sandbox, "epic-nodepgen")
    payload = json.loads(mf.read_text())
    del payload["epic"]["dependency_generation"]
    mf.write_text(json.dumps(payload), encoding="utf-8")

    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "NEEDS-RECONCILE" in proc.stdout
    assert "dependency generation proof missing or incomplete" in proc.stdout
    # No deletion anywhere: the only SWEPT tokens are SWEPT=NO:REFERENCED
    # skip markers (the proof-less per-slug manifest stays in the store and
    # keeps the tree referenced); SWEPT=YES never appears.
    assert "SWEPT=YES" not in proc.stdout, proc.stdout
    assert worktree.is_dir()  # the proof-less manifest's tree is never deleted
    assert mf.exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_skips_schedule_store_referenced_closed_tree(
    sandbox: dict[str, object],
) -> None:
    worktree = sandbox["create"]("epic-schedref")
    close = sandbox["run"](
        CLOSE, "epic-schedref", str(manifest_path(sandbox, "epic-schedref"))
    )
    assert close.returncode == 0, close.stderr
    # the schedule store references this tree (probe-4 trees must never be swept)
    store = Path(str(sandbox["env"]["ARNOLD_SCHEDULE_STORE"]))
    store.mkdir(parents=True, exist_ok=True)
    (store / "scheduled_jobs.json").write_text(
        json.dumps({"epic": "epic-schedref", "ref": "some-sha"}), encoding="utf-8"
    )
    proc = sandbox["run"](
        GC_SWEEP, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "schedule-store-referenced" in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-schedref").exists()
    # dry-run reports the same hard gate
    dry = sandbox["run"](GC_SWEEP, "--dry-run", str(sandbox["manifest_dir"]))
    assert dry.returncode == 0, dry.stderr
    assert "WOULD-SKIP" in dry.stdout
    assert "schedule-store-referenced" in dry.stdout


# ── reference census (T-0012): fail-closed before every deletion ────────────


def _restore_receipt_path(sandbox: dict[str, object], slug: str) -> Path:
    """The content-addressed restore receipt arnold-close writes for a slug."""
    return Path(sandbox["manifest_dir"]) / "restore-receipts" / f"{slug}.json"


def _delete_restore_receipt(sandbox: dict[str, object], slug: str) -> None:
    """Remove the restore receipt (simulate the restore evidence being lost
    after close) so a sweep must SKIP — a CLI flag is never evidence."""
    receipt = _restore_receipt_path(sandbox, slug)
    if receipt.exists():
        receipt.unlink()


def _write_restore_receipt(
    sandbox: dict[str, object],
    slug: str,
    *,
    worktree: Path,
    **overrides: object,
) -> Path:
    """Write a content-addressed restore receipt for a slug, mirroring
    arnold-close phase 3b exactly: schema ``restore-receipt/v1``, bound to
    the manifest's runtime_id / dependency_generation.id / runtime_root and
    the worktree HEAD, with a self-digest ``content_sha256`` over the
    canonical JSON body (``sort_keys``, compact separators).  ``overrides``
    lets a fixture forge a mismatched/torn receipt for the fail-closed
    tests (the self-digest is always recomputed over the forged body, so a
    torn receipt's digest stops matching)."""
    manifest = read_manifest(sandbox, slug)
    receipt_dir = Path(sandbox["manifest_dir"]) / "restore-receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    body: dict[str, object] = {
        "schema": "restore-receipt/v1",
        "epic_id": slug,
        "runtime_id": manifest["runtime_id"],
        "runtime_root": manifest["epic"]["runtime_root"],
        "dependency_generation_id": manifest["epic"]["dependency_generation"]["id"],
        "closed_head": git(worktree, "rev-parse", "HEAD"),
        "restored_at": "2026-08-12T00:00:00+00:00",
        "restore_drill": "clean-room restore drill (fixture)",
    }
    body.update(overrides)
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    body["content_sha256"] = digest
    path = receipt_dir / f"{slug}.json"
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _close_epic_and_prove(sandbox: dict[str, object], slug: str) -> Path:
    """Close an epic; close itself writes the content-addressed restore
    receipt (close PRECEDES restore-proven GC), so the sweep's restore gate
    passes without any flag."""
    worktree = sandbox["create"](slug)
    close = sandbox["run"](CLOSE, slug, str(manifest_path(sandbox, slug)))
    assert close.returncode == 0, close.stderr
    assert _restore_receipt_path(sandbox, slug).exists(), close.stdout + close.stderr
    return worktree


def _sweep_with_spy(
    sandbox: dict[str, object],
    git_spy: dict[str, object],
    *args: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": str(git_spy["dir"]) + os.pathsep + os.environ.get("PATH", ""),
        "GIT_SPY_LOG": str(git_spy["log"]),
        "RM_SPY_LOG": str(git_spy["rm_log"]),
    }
    if extra_env:
        env.update(extra_env)
    return sandbox["run"](GC_SWEEP, *args, extra_env=env)


def _spy_log(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text().splitlines()


def _assert_no_destructive(git_spy: dict[str, object]) -> None:
    """No destructive call of any kind was issued: no git worktree remove /
    branch -D / push --delete AND no venv `rm -rf` (a referenced or unknown
    runtime root OR venv is never deleted)."""
    log = _spy_log(Path(git_spy["log"]))
    assert not any("worktree remove" in line for line in log), log
    assert not any("branch -D" in line for line in log), log
    assert not any("--delete" in line for line in log), log
    rm_log = _spy_log(Path(git_spy["rm_log"]))
    assert not any("-rf" in line for line in rm_log), rm_log


def _assert_no_venv_rm(git_spy: dict[str, object], venv: Path) -> None:
    """The rm spy must never have been pointed at *venv*: a referenced venv
    is not deleted even when the sweep proceeds with the worktree itself."""
    rm_log = _spy_log(Path(git_spy["rm_log"]))
    assert not any(str(venv) in line for line in rm_log), rm_log


def _write_reference(root: Path, relpath: str, payload: object) -> Path:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_gc_sweep_referenced_by_other_manifest_skips_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """Reference class: runtime manifests.  A second (active) manifest
    referencing the SAME exact runtime root makes the root load-bearing —
    the sweep must hard-skip and never call git worktree remove."""
    worktree = _close_epic_and_prove(sandbox, "epic-refmf")
    holder = manifest_path(sandbox, "epic-holder")
    holder.write_text(
        json.dumps(
            {
                "epic_id": "epic-holder",
                "state": "active",
                "epic": {"runtime_root": str(worktree)},
            }
        ),
        encoding="utf-8",
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "reference census" in proc.stdout
    assert "REFERENCED" in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-refmf").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_referenced_by_chain_engine_root_skips_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """Reference class: active/paused/blocked chain metadata
    metadata.execution_environment.engine_root — an exact path reference
    hard-skips deletion."""
    worktree = _close_epic_and_prove(sandbox, "epic-refchain")
    _write_reference(
        Path(sandbox["tmp_path"]),
        "ref-chains/chain-ref.json",
        {
            "metadata": {"execution_environment": {"engine_root": str(worktree)}},
            "state": "active",
        },
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "reference census" in proc.stdout
    assert "REFERENCED" in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-refchain").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_referenced_by_marker_skips_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """Reference class: cloud-session / chain-health markers."""
    worktree = _close_epic_and_prove(sandbox, "epic-refmarker")
    _write_reference(
        Path(sandbox["tmp_path"]),
        "ref-markers/session-ref.json",
        {"session": "s1", "engine_root": str(worktree)},
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "reference census" in proc.stdout
    assert "REFERENCED" in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-refmarker").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_referenced_by_schedule_job_skips_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """Reference class: resident/ops schedules and jobs — an exact
    runtime-root path in the schedule store hard-skips (on top of the legacy
    slug/sha grep gate)."""
    worktree = _close_epic_and_prove(sandbox, "epic-refsched")
    store = Path(str(sandbox["env"]["ARNOLD_SCHEDULE_STORE"]))
    store.mkdir(parents=True, exist_ok=True)
    (store / "jobs.json").write_text(
        json.dumps({"job": "probe-4", "runtime_root": str(worktree)}), encoding="utf-8"
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "reference census" in proc.stdout
    assert "REFERENCED" in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-refsched").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_referenced_by_repair_queue_skips_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """Reference class: occurrence requests, decisions, active claims, and
    attempts — any one of the queue sub-stores referencing the exact root
    hard-skips deletion."""
    worktree = _close_epic_and_prove(sandbox, "epic-refqueue")
    queue = Path(sandbox["tmp_path"]) / "ref-repair-queue"
    for sub in ("requests", "decisions", "attempts", "active-claims", "occurrence-claims"):
        _write_reference(
            queue, f"{sub}/ref-{sub}.json", {"runtime_root": str(worktree)}
        )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "reference census" in proc.stdout
    assert "REFERENCED" in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-refqueue").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_referenced_by_lease_skips_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """Reference class: custody leases.  Uses the REAL lease suffix —
    <lease_id>.history.jsonl, the append-only custody event stream (G2: the
    census previously scanned only *.json and silently missed every lease
    history; <lease_id>.state.json is covered by the *.json glob)."""
    worktree = _close_epic_and_prove(sandbox, "epic-reflease")
    _write_reference(
        Path(sandbox["tmp_path"]),
        "ref-leases/lease-ref.history.jsonl",
        {
            "lease_id": "lease-ref",
            "event_type": "acquire",
            "payload": {"engine_root": str(worktree)},
        },
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "reference census" in proc.stdout
    assert "REFERENCED" in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-reflease").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_venv_referenced_by_lease_history_keeps_venv(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G2 (a)+(b): the epic venv path goes through the SAME reference census
    as the worktree.  A custody lease history (.history.jsonl — the real
    append-only lease suffix) referencing the exact external venv path must
    block the venv's rm -rf even though the worktree itself is swept."""
    worktree = _close_epic_and_prove(sandbox, "epic-venvref")
    # external venv: lives OUTSIDE the tree (and outside runtime-candidates),
    # so the sweep would rm -rf it
    venv = Path(sandbox["tmp_path"]) / "venvs" / "epic-venvref"
    venv.mkdir(parents=True, exist_ok=True)
    m = read_manifest(sandbox, "epic-venvref")
    m["epic"]["venv_path"] = str(venv)
    manifest_path(sandbox, "epic-venvref").write_text(json.dumps(m), encoding="utf-8")
    _write_reference(
        Path(sandbox["tmp_path"]),
        "ref-leases/lease-venv.history.jsonl",
        {
            "lease_id": "lease-venv",
            "event_type": "acquire",
            "payload": {"engine_root": str(venv)},
        },
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "SWEPT" in proc.stdout
    assert "SKIP venv" in proc.stdout
    assert "REFERENCED" in proc.stdout
    assert not worktree.exists()  # the worktree itself was swept
    assert venv.is_dir()  # the referenced venv was never deleted
    _assert_no_venv_rm(git_spy, venv)


def test_gc_sweep_corrupt_lease_history_blocks_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G2 (b) fail-closed on the REAL lease suffix: a corrupt .history.jsonl
    in the lease store makes the census UNKNOWN and BLOCKS deletion (exit 5).
    Previously *.jsonl lease histories were never scanned at all, so a
    corrupt lease history could not block anything."""
    worktree = _close_epic_and_prove(sandbox, "epic-corruptlease")
    lease_store = Path(sandbox["tmp_path"]) / "ref-leases"
    lease_store.mkdir(parents=True, exist_ok=True)
    (lease_store / "lease-corrupt.history.jsonl").write_text(
        '{"lease_id": "lease-corrupt", "event_type": "acquire", '
        '"payload": {"engine_root": "',
        encoding="utf-8",
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 5, proc.stdout
    assert "UNKNOWN" in proc.stderr
    assert "BLOCKED" in proc.stderr
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-corruptlease").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_referenced_by_plan_lease_skips_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """Reference class (T-0027): per-plan custody lease stores
    (<workspace>/.megaplan/plans/<plan>/custody/leases — the paths
    worker_dispatch_wbc.py:613 and phase_wbc.py:937 open).  Uses the REAL
    lease suffix <lease_id>.history.jsonl; an exact runtime root in any
    per-plan lease store hard-skips deletion."""
    worktree = _close_epic_and_prove(sandbox, "epic-refplanlease")
    _write_reference(
        Path(sandbox["tmp_path"]),
        "ref-plan-leases/plan-ref/custody/leases/lease-ref.history.jsonl",
        {
            "lease_id": "lease-ref",
            "event_type": "acquire",
            "payload": {"engine_root": str(worktree)},
        },
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "reference census" in proc.stdout
    assert "REFERENCED" in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-refplanlease").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_referenced_by_managed_run_skips_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """Reference class (T-0027): managed-subagent run manifests
    (<project>/.megaplan/plans/resident-subagents/<run_id>/manifest.json —
    resident/subagent.py DEFAULT_MANAGED_RUN_ROOT).  Run manifests are ONE
    level deep, so the store scan recurses into run dirs.  G6: the REAL
    manifest carries the runtime root NESTED at
    context_directory.resident_runtime_source (resident/subagent.py
    _delegated_context_directory) — an exact-path reference that hard-skips
    deletion even though project_dir/project_worktree point at a different
    (project) checkout."""
    worktree = _close_epic_and_prove(sandbox, "epic-refmanaged")
    project_dir = Path(sandbox["tmp_path"]) / "managed-project"
    _write_reference(
        Path(sandbox["tmp_path"]),
        "ref-managed-runs/run-ref/manifest.json",
        {
            "run_id": "run-ref",
            "schema_version": "arnold-resident-managed-run-v1",
            "project_dir": str(project_dir),
            "context_directory": {
                "project_worktree": str(project_dir),
                "resident_runtime_source": str(worktree),
                "resident_runtime_revision": "abc1234",
                "project_equals_runtime_source": False,
                "resident_conversation_id": "rconv_run-ref",
                "routes": {
                    "context_root": "python -P -m arnold_pipelines.megaplan resident context --node root",
                    "context_search": (
                        "python -P -m arnold_pipelines.megaplan resident "
                        "context-search --scope '<scope>' --query '<query>'"
                    ),
                },
            },
        },
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "reference census" in proc.stdout
    assert "REFERENCED" in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-refmanaged").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_managed_run_without_runtime_source_is_not_reference(
    sandbox: dict[str, object],
) -> None:
    """G6 absent side: a managed-run manifest that does NOT carry
    context_directory.resident_runtime_source (or any other path equal to the
    swept root) is not a reference — the census stays CLEAR and the closed
    tree is swept."""
    worktree = _close_epic_and_prove(sandbox, "epic-norefmanaged")
    _write_reference(
        Path(sandbox["tmp_path"]),
        "ref-managed-runs/run-noref/manifest.json",
        {
            "run_id": "run-noref",
            "schema_version": "arnold-resident-managed-run-v1",
            "project_dir": str(Path(sandbox["tmp_path"]) / "managed-project"),
            "context_directory": {
                "project_worktree": str(Path(sandbox["tmp_path"]) / "managed-project"),
                "resident_conversation_id": "rconv_run-noref",
                "routes": {
                    "context_root": "python -P -m arnold_pipelines.megaplan resident context --node root"
                },
            },
        },
    )
    proc = sandbox["run"](GC_SWEEP, "--restore-proven", str(sandbox["manifest_dir"]))
    assert proc.returncode == 0, proc.stderr
    assert "REFERENCED" not in proc.stdout
    assert "SWEPT" in proc.stdout
    assert not worktree.exists()
    assert not manifest_path(sandbox, "epic-norefmanaged").exists()


def test_gc_sweep_referenced_by_status_snapshot_skips_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """Reference class (T-0027): the canonical status snapshot
    (/workspace/.megaplan/status/cloud-status.json — status_snapshot.py).  A
    runtime root inside the snapshot is load-bearing and hard-skips
    deletion."""
    worktree = _close_epic_and_prove(sandbox, "epic-refstatus")
    _write_reference(
        Path(sandbox["tmp_path"]),
        "ref-status/cloud-status.json",
        {
            "generated_at": "2026-08-12T00:00:00Z",
            "snapshot": {"runtime_root": str(worktree)},
        },
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "reference census" in proc.stdout
    assert "REFERENCED" in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-refstatus").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_referenced_by_ops_schedule_input_skips_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """Reference class (T-0027): ops schedule-inputs
    (/workspace/.megaplan/ops/schedules + schedule-inputs —
    probe_records.py).  schedule-inputs holds one nested dir per input, so
    the store scan recurses one level; an exact runtime root inside an input
    hard-skips deletion."""
    worktree = _close_epic_and_prove(sandbox, "epic-refops")
    _write_reference(
        Path(sandbox["tmp_path"]),
        "ref-ops/schedule-inputs/input-ref/payload.json",
        {"engine_root": str(worktree)},
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "reference census" in proc.stdout
    assert "REFERENCED" in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-refops").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_corrupt_plan_lease_store_blocks_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """T-0027 fail-closed on the per-plan custody lease store: a corrupt
    .history.jsonl under .megaplan/plans/<plan>/custody/leases makes the
    census UNKNOWN and BLOCKS deletion (exit 5) — delete-on-unknown never
    happens."""
    worktree = _close_epic_and_prove(sandbox, "epic-corruptplanlease")
    lease_store = (
        Path(sandbox["tmp_path"]) / "ref-plan-leases" / "plan-x" / "custody" / "leases"
    )
    lease_store.mkdir(parents=True, exist_ok=True)
    (lease_store / "lease-corrupt.history.jsonl").write_text(
        '{"lease_id": "lease-corrupt", "event_type": "acquire", '
        '"payload": {"engine_root": "',
        encoding="utf-8",
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 5, proc.stdout
    assert "UNKNOWN" in proc.stderr
    assert "BLOCKED" in proc.stderr
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-corruptplanlease").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_dangling_reference_needs_reconcile(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """A store referencing a runtime root that no longer exists is incoherent:
    the sweep reports NEEDS-RECONCILE and never deletes."""
    worktree = _close_epic_and_prove(sandbox, "epic-dangle")
    missing = Path(sandbox["tmp_path"]) / "missing-runtime-candidates" / "vanished-tree"
    _write_reference(
        Path(sandbox["tmp_path"]),
        "ref-chains/chain-dangling.json",
        {
            "metadata": {"execution_environment": {"engine_root": str(missing)}},
            "state": "active",
        },
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "NEEDS-RECONCILE" in proc.stdout
    assert "dangling" in proc.stdout.lower()
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-dangle").exists()
    _assert_no_destructive(git_spy)


# ── SWEPT= outcome protocol (G6 round-3 finding 1) ──────────────────────────


def test_gc_sweep_referenced_skip_emits_swept_no_marker(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G6 round-3 finding 1: a REFERENCED skip must be observable as
    skipped-but-alive — the sweep prints a per-slug SWEPT=NO:REFERENCED
    marker inside the decision line so callers never infer deletion from
    the exit-0 sweep.  Exit stays 0 (a multi-manifest sweep may reclaim
    OTHER trees); the marker, not the exit code, is the swept:false signal."""
    worktree = _close_epic_and_prove(sandbox, "epic-refmark")
    holder = manifest_path(sandbox, "epic-holder2")
    holder.write_text(
        json.dumps(
            {
                "epic_id": "epic-holder2",
                "state": "active",
                "epic": {"runtime_root": str(worktree)},
            }
        ),
        encoding="utf-8",
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "SKIP 'epic-refmark'" in proc.stdout
    assert "SWEPT=NO:REFERENCED" in proc.stdout
    assert "REFERENCED" in proc.stdout
    assert worktree.is_dir()  # skipped-but-alive: never deleted
    assert manifest_path(sandbox, "epic-refmark").exists()
    _assert_no_destructive(git_spy)
    # dry-run previews the same gate without any swept marker (nothing was
    # attempted, so nothing is skipped-but-alive for real)
    dry = _sweep_with_spy(
        sandbox,
        git_spy,
        "--dry-run",
        "--restore-proven",
        str(sandbox["manifest_dir"]),
    )
    assert dry.returncode == 0, dry.stderr
    assert "WOULD-SKIP" in dry.stdout
    assert "SWEPT=" not in dry.stdout


def test_gc_sweep_dangling_skip_emits_swept_no_marker(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G6 round-3 finding 1: a DANGLING skip emits SWEPT=NO:DANGLING — the
    tree is never deleted and the exit-0 sweep is observable as
    skipped-but-alive (the NEEDS-RECONCILE verdict wording is preserved)."""
    worktree = _close_epic_and_prove(sandbox, "epic-dangmark")
    missing = Path(sandbox["tmp_path"]) / "missing-runtime-candidates" / "vanished-tree"
    _write_reference(
        Path(sandbox["tmp_path"]),
        "ref-chains/chain-dangling-mark.json",
        {
            "metadata": {"execution_environment": {"engine_root": str(missing)}},
            "state": "active",
        },
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "NEEDS-RECONCILE 'epic-dangmark'" in proc.stdout
    assert "SWEPT=NO:DANGLING" in proc.stdout
    assert "NEEDS-RECONCILE" in proc.stdout
    assert "dangling" in proc.stdout.lower()
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-dangmark").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_clear_sweep_emits_swept_yes(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G6 round-3 finding 1: a CLEAR deletion exits 0 AND prints the
    per-slug SWEPT=YES marker — 'swept' is recorded true only here, and a
    clean sweep never emits a SWEPT=NO: marker."""
    worktree = _close_epic_and_prove(sandbox, "epic-clearmark")
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "SWEPT=YES 'epic-clearmark'" in proc.stdout
    assert "SWEPT=NO:" not in proc.stdout
    assert not worktree.exists()
    assert (Path(sandbox["manifest_dir"]) / "archived" / "epic-clearmark.json").exists()


def test_gc_sweep_corrupt_reference_store_blocks_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """An unreadable/corrupt reference store makes the census UNKNOWN and
    BLOCKS deletion (exit 5, fail-closed — delete-on-unknown never happens);
    dry-run previews the block without failing."""
    worktree = _close_epic_and_prove(sandbox, "epic-corrupt")
    corrupt = Path(sandbox["tmp_path"]) / "ref-chains" / "chain-corrupt.json"
    corrupt.parent.mkdir(parents=True, exist_ok=True)
    corrupt.write_text('{"metadata": {"execution_environment": {"engine_root": "', encoding="utf-8")
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 5, proc.stdout
    assert "UNKNOWN" in proc.stderr
    assert "BLOCKED" in proc.stderr
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-corrupt").exists()
    _assert_no_destructive(git_spy)
    dry = _sweep_with_spy(
        sandbox, git_spy, "--dry-run", "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert dry.returncode == 0, dry.stderr
    assert "WOULD-BLOCK" in dry.stdout
    assert worktree.is_dir()


def test_gc_sweep_referenced_by_nested_owner_claim_skips_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G2 finding 4(a): real repair claims live under NESTED
    ``<queue>/active-claims/<token>.lock/owner.json`` (repair_requests
    ``active_repair_claim_lock_dir`` / repair_lock ``owner_metadata_path``),
    not top-level JSON.  The census must recurse into ``*.lock/`` dirs — a
    claim whose owner.json references the exact root hard-skips deletion."""
    worktree = _close_epic_and_prove(sandbox, "epic-refclaim")
    for sub, token in (
        ("active-claims", "claim-ref"),
        ("occurrence-claims", "occ-ref"),
    ):
        _write_reference(
            Path(sandbox["tmp_path"]),
            f"ref-repair-queue/{sub}/{token}.lock/owner.json",
            {"session": "s1", "cwd": str(worktree)},
        )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "reference census" in proc.stdout
    assert "REFERENCED" in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-refclaim").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_referenced_by_workspace_chain_state_skips_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G2 finding 4(b): chains store per-workspace state at
    ``<workspace>/.megaplan/plans/.chains/chain-*.json`` (spec.py chain-state
    layout) — NOT only the fixed default store.  A workspace-relative chain
    state referencing the exact engine_root hard-skips deletion."""
    worktree = _close_epic_and_prove(sandbox, "epic-refwschain")
    _write_reference(
        Path(sandbox["base_dir"]),
        ".megaplan/plans/.chains/chain-ws.json",
        {
            "metadata": {"execution_environment": {"engine_root": str(worktree)}},
            "state": "active",
        },
    )
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 0, proc.stderr
    assert "reference census" in proc.stdout
    assert "REFERENCED" in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-refwschain").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_referenced_by_per_project_chain_state_skips_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G2 round-3 (criterion 4) + round-5 finding 4(a): the canonical
    chain-state layout is PER-PROJECT — ``<workspace>/<project>/Arnold/
    .megaplan/plans/.chains/chain-*.json`` (the box keeps one workspace dir
    per chain with the repo checkout — the ``Arnold`` SUBDIR — under it; the
    flat ``<workspace>/.megaplan/plans/.chains`` holds nothing).  A
    per-project chain state referencing the exact engine_root hard-skips
    deletion — the census must glob the per-project chain dirs at TWO
    depths (``<workspace>/*/.megaplan`` and
    ``<workspace>/*/*/.megaplan``) against the REAL
    ``ARNOLD_BASE_DIR=<base>`` workspace, not a masked per-project root."""
    worktree = _close_epic_and_prove(sandbox, "epic-projchain")
    _write_reference(
        Path(sandbox["base_dir"]) / "proj" / "Arnold",
        ".megaplan/plans/.chains/chain-ws.json",
        {
            "metadata": {"execution_environment": {"engine_root": str(worktree)}},
            "state": "active",
        },
    )
    # The sweep runs with the DEFAULT workspace (<base>, ARNOLD_BASE_DIR
    # from the sandbox env — no per-project masking); the census's two-level
    # per-project glob must find <base>/proj/Arnold/.megaplan/plans/.chains.
    proc = _sweep_with_spy(
        sandbox,
        git_spy,
        "--restore-proven",
        str(sandbox["manifest_dir"]),
    )
    assert proc.returncode == 0, proc.stderr
    assert "reference census" in proc.stdout
    assert "REFERENCED" in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-projchain").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_dangling_per_project_chain_reference_needs_reconcile(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G2 round-3 (criterion 4) fail-closed: a per-project chain state whose
    engine_root no longer exists is DANGLING — the census cannot attest
    completeness, so the sweep reports NEEDS-RECONCILE and never deletes.
    The two-level per-project glob (round-5 finding 4(a)) must find the
    store at <base>/proj/Arnold/.megaplan/plans/.chains for the dangling
    verdict just like it does for a live reference — with the default
    workspace (<base>), no ARNOLD_BASE_DIR masking."""
    worktree = _close_epic_and_prove(sandbox, "epic-projchain-dangling")
    _write_reference(
        Path(sandbox["base_dir"]) / "proj" / "Arnold",
        ".megaplan/plans/.chains/chain-ws.json",
        {
            "metadata": {
                "execution_environment": {"engine_root": f"{worktree}-gone"}
            },
            "state": "active",
        },
    )
    proc = _sweep_with_spy(
        sandbox,
        git_spy,
        "--restore-proven",
        str(sandbox["manifest_dir"]),
    )
    assert proc.returncode == 0, proc.stderr
    assert "NEEDS-RECONCILE" in proc.stdout
    assert "DANGLING" in proc.stdout
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-projchain-dangling").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_present_but_inaccessible_store_blocks_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G2 round-5 finding 4(b) fail-closed: a reference store PATH that
    EXISTS but cannot be read as a store directory (here: a file squatting
    on the configured chain store path) makes the census UNKNOWN and BLOCKS
    deletion (exit 5).  A GENUINELY missing store is not a reference
    (existing semantics — every other fixture relies on it); only
    present-but-inaccessible is UNKNOWN, so delete-on-unknown never
    happens."""
    worktree = _close_epic_and_prove(sandbox, "epic-blocked-store")
    # The configured chain store (<tmp>/ref-chains) is absent by default;
    # plant a FILE there: present, but not a readable store directory.
    chain_store = Path(sandbox["tmp_path"]) / "ref-chains"
    chain_store.write_text("not a directory\n", encoding="utf-8")
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 5, proc.stdout
    assert "UNKNOWN" in proc.stderr
    assert "BLOCKED" in proc.stderr
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-blocked-store").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_dangling_store_symlink_blocks_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G6 finding 5 fail-closed: a DANGLING SYMLINK squatting on a reference
    store path is PRESENT but broken — stat() follows the link to its
    missing target and raises ENOENT, so the old
    ``except FileNotFoundError: continue`` collapsed it to CLEAR absence and
    the sweep could delete.  The census must treat the dangling store path
    as UNKNOWN (fail-closed) and BLOCK deletion (exit 5)."""
    worktree = _close_epic_and_prove(sandbox, "epic-dangle-store")
    store = Path(sandbox["tmp_path"]) / "ref-chains"
    store.symlink_to(store.parent / "ref-chains-target-missing")
    assert store.is_symlink()
    assert not store.exists()  # stat follows the link: ENOENT

    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 5, proc.stdout + proc.stderr
    assert "UNKNOWN" in proc.stderr
    assert "BLOCKED" in proc.stderr
    assert "dangling symlink" in proc.stderr
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-dangle-store").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_dangling_plan_lease_root_symlink_blocks_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G6 finding 5 fail-closed: the CONFIGURED plan-lease root
    (<workspace>/.megaplan/plans) is validated BEFORE globbing beneath it.
    A dangling root symlink makes the per-plan lease glob return an empty
    list, so the old code collapsed the broken root to CLEAR absence and
    the sweep could delete.  The dangling root must be UNKNOWN (fail-closed)
    and BLOCK deletion (exit 5)."""
    worktree = _close_epic_and_prove(sandbox, "epic-dangle-planroot")
    root = Path(sandbox["tmp_path"]) / "ref-plan-leases"
    root.symlink_to(root.parent / "ref-plan-leases-target-missing")
    assert root.is_symlink()
    assert not root.exists()  # glob beneath it would silently return []

    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 5, proc.stdout + proc.stderr
    assert "UNKNOWN" in proc.stderr
    assert "BLOCKED" in proc.stderr
    assert "dangling symlink" in proc.stderr
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-dangle-planroot").exists()
    _assert_no_destructive(git_spy)


def test_gc_sweep_genuinely_missing_store_is_not_reference(
    sandbox: dict[str, object],
) -> None:
    """G6 finding 5 absent side: a GENUINELY missing store dir is not a
    reference (existing semantics — every sandbox fixture relies on it).
    The dangling-vs-absent triage must NOT turn plain absence into UNKNOWN:
    with every reference store absent the census is CLEAR and the closed,
    restore-proven tree is swept."""
    worktree = _close_epic_and_prove(sandbox, "epic-nomissing-store")
    # No ref store exists anywhere under <tmp> (sandbox env points every
    # ARNOLD_REFERENCE_* at absent dirs).
    proc = sandbox["run"](GC_SWEEP, "--restore-proven", str(sandbox["manifest_dir"]))
    assert proc.returncode == 0, proc.stderr
    assert "SWEPT" in proc.stdout
    assert "UNKNOWN" not in proc.stdout
    assert not worktree.exists()
    assert not manifest_path(sandbox, "epic-nomissing-store").exists()


def test_gc_sweep_corrupt_nested_owner_json_blocks_deletion(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """G2 finding 4(a) fail-closed on the REAL claim layout: a corrupt
    owner.json inside a nested ``*.lock/`` claim dir makes the census
    UNKNOWN and BLOCKS deletion (exit 5).  A top-level-only scan never saw
    nested claim locks at all, so a corrupt claim could not block anything."""
    worktree = _close_epic_and_prove(sandbox, "epic-corruptclaim")
    owner = (
        Path(sandbox["tmp_path"])
        / "ref-repair-queue"
        / "active-claims"
        / "claim-corrupt.lock"
        / "owner.json"
    )
    owner.parent.mkdir(parents=True, exist_ok=True)
    owner.write_text('{"cwd": "', encoding="utf-8")
    proc = _sweep_with_spy(
        sandbox, git_spy, "--restore-proven", str(sandbox["manifest_dir"])
    )
    assert proc.returncode == 5, proc.stdout
    assert "UNKNOWN" in proc.stderr
    assert "BLOCKED" in proc.stderr
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-corruptclaim").exists()
    _assert_no_destructive(git_spy)


# ── P6 terminal finalizer: fixer-branch deletion ────────────────────────────


def test_gc_sweep_deletes_fixer_branch_after_restore_proof(
    sandbox: dict[str, object],
) -> None:
    """P6: arnold-gc-sweep --fixer-branch <branch> deletes the manifest-
    declared fixer branch local + remote after a restore-proven sweep."""
    worktree = sandbox["create"]("epic-fixer")
    branch = read_manifest(sandbox, "epic-fixer")["epic"]["branch"]
    close = sandbox["run"](CLOSE, "epic-fixer", str(manifest_path(sandbox, "epic-fixer")))
    assert close.returncode == 0, close.stderr

    # branch exists local + remote before the sweep
    assert git(Path(sandbox["base_repo"]), "rev-parse", "--verify", branch)
    assert sandbox["origin_heads"](branch)

    sweep = sandbox["run"](
        GC_SWEEP,
        "--restore-proven",
        "--fixer-branch",
        branch,
        str(sandbox["manifest_dir"]),
    )
    assert sweep.returncode == 0, sweep.stderr
    assert "SWEPT" in sweep.stdout
    assert "deleted local fixer branch" in sweep.stdout
    assert "deleted remote fixer branch" in sweep.stdout
    assert not worktree.exists()
    assert (Path(sandbox["manifest_dir"]) / "archived" / "epic-fixer.json").exists()
    # branch gone local AND remote
    gone = subprocess.run(
        ["git", "-C", str(sandbox["base_repo"]), "rev-parse", "--verify", branch],
        capture_output=True,
        text=True,
    )
    assert gone.returncode != 0
    assert not sandbox["origin_heads"](branch)


def test_gc_sweep_refuses_fixer_branch_deletion_when_pr_still_open(
    sandbox: dict[str, object],
) -> None:
    """P6 terminal-state rules: the sweep REFUSES while a pull ref on the
    remote still points at the fixer branch head (an open PR is load-bearing;
    never delete a branch under an open PR)."""
    worktree = sandbox["create"]("epic-fixerpr")
    branch = read_manifest(sandbox, "epic-fixerpr")["epic"]["branch"]
    close = sandbox["run"](
        CLOSE, "epic-fixerpr", str(manifest_path(sandbox, "epic-fixerpr"))
    )
    assert close.returncode == 0, close.stderr
    branch_head = sandbox["origin_heads"](branch)
    assert branch_head
    # simulate an open PR: a refs/pull/*/head ref on the remote pointing at
    # the fixer branch head (GitHub exposes open PR heads this way)
    git(
        Path(sandbox["base_repo"]),
        "update-ref",
        "refs/pull/42/head",
        branch_head,
    )
    git(
        Path(sandbox["base_repo"]),
        "push",
        str(sandbox["origin"]),
        "refs/pull/42/head",
    )

    sweep = sandbox["run"](
        GC_SWEEP,
        "--restore-proven",
        "--fixer-branch",
        branch,
        str(sandbox["manifest_dir"]),
    )
    # fail-closed: REFUSE exits 3 (detectable by the P6 terminal finalizer)
    assert sweep.returncode == 3, sweep.stdout
    assert "REFUSE" in sweep.stderr
    assert "open pull ref" in sweep.stderr
    # nothing deleted: worktree + manifest + branch all survive
    assert worktree.is_dir()
    assert manifest_path(sandbox, "epic-fixerpr").exists()
    assert sandbox["origin_heads"](branch)
    # dry-run previews the same refusal (gate checked before the preview)
    dry = sandbox["run"](
        GC_SWEEP,
        "--dry-run",
        "--restore-proven",
        "--fixer-branch",
        branch,
        str(sandbox["manifest_dir"]),
    )
    assert dry.returncode == 0, dry.stderr
    assert "WOULD-REFUSE" in dry.stdout
    assert worktree.is_dir()


def test_close_verifies_fixer_branch_pushed_before_backstop_tag(
    sandbox: dict[str, object],
) -> None:
    """P6: arnold-close verifies the manifest-declared fixer branch
    (epic.branch) is pushed BEFORE the backstop tag — an unpushed fixer
    branch means the runtime's own line is box-only and close must fail."""
    worktree = sandbox["create"]("epic-fixerunpushed")
    branch = read_manifest(sandbox, "epic-fixerunpushed")["epic"]["branch"]
    # advance the fixer branch locally WITHOUT pushing
    epic_commit(worktree, "unpushed.txt", "unpushed\n", "unpushed fixer line")
    proc = sandbox["run"](
        CLOSE, "epic-fixerunpushed", str(manifest_path(sandbox, "epic-fixerunpushed"))
    )
    assert proc.returncode != 0
    assert "fixer branch" in proc.stderr.lower()
    assert read_manifest(sandbox, "epic-fixerunpushed")["state"] == "active"


def test_close_passes_when_worktree_on_other_branch_but_fixer_pushed(
    sandbox: dict[str, object],
) -> None:
    """The fixer branch is verified as a REF, not via the checked-out HEAD:
    close must pass when the runtime worktree sits on a milestone-style
    branch while the manifest-declared fixer branch stays pushed (the P6
    reconcile-flow shape).  The branch MUST NOT carry the ``reconcile/<slug>-*``
    prefix — any such remote branch is an UNRESOLVED reconcile and close
    refuses by design (P6 terminal-state rules)."""
    worktree = sandbox["create"]("epic-fixerother")
    branch = read_manifest(sandbox, "epic-fixerother")["epic"]["branch"]
    # move the worktree onto a milestone-style branch + push it
    git(worktree, "checkout", "-b", "milestone/epic-fixerother-20260811")
    epic_commit(worktree, "work.txt", "milestone work\n", "milestone work")
    git(worktree, "push", "origin", "HEAD:refs/heads/milestone/epic-fixerother-20260811")
    # the fixer branch itself is still pushed (unmoved since creation)
    assert sandbox["origin_heads"](branch)
    proc = sandbox["run"](
        CLOSE, "epic-fixerother", str(manifest_path(sandbox, "epic-fixerother"))
    )
    assert proc.returncode == 0, proc.stderr
    assert read_manifest(sandbox, "epic-fixerother")["state"] == "closed"
    # close wrote the content-addressed restore receipt (close precedes GC)
    assert _restore_receipt_path(sandbox, "epic-fixerother").exists()


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


def test_promote_refuses_present_but_corrupt_manifest(sandbox: dict[str, object]) -> None:
    """T-0024: arnold-promote reads the manifest with raw field reads but
    fails closed on a PRESENT-but-corrupt manifest — it must refuse
    (non-zero) before touching state, never promote an epic whose manifest
    cannot be read."""
    worktree = sandbox["create"]("epic-promocorrupt")
    manifest = manifest_path(sandbox, "epic-promocorrupt")
    manifest.write_text("{not valid json", encoding="utf-8")
    proc = sandbox["run"](PROMOTE, "--force-gate", "epic-promocorrupt", str(manifest))
    assert proc.returncode != 0
    assert worktree.is_dir()
    # promote neither rewrote nor advanced the corrupt manifest
    assert manifest.read_text(encoding="utf-8") == "{not valid json"
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


def test_promote_without_canary_flag_keeps_pointer(sandbox: dict[str, object]) -> None:
    worktree = sandbox["create"]("epic-canary")
    branch = git(worktree, "branch", "--show-current")
    head = epic_commit(worktree, "fix.txt", "fix\n", "durable fix")
    git(worktree, "push", "origin", f"HEAD:refs/heads/{branch}")
    pointer = Path(str(sandbox["env"]["ARNOLD_RUNTIME_MANIFEST"]))
    assert json.loads(pointer.read_text())["generation"] == 1

    proc = sandbox["run"](
        PROMOTE,
        "--force-gate",
        "epic-canary",
        str(manifest_path(sandbox, "epic-canary")),
    )
    assert proc.returncode == 0, proc.stderr
    # the canary gate is structural: steps printed, push journaled, pointer NOT
    # advanced — a successful push is NOT a safe cutover (design rule 5)
    assert "canary" in proc.stdout.lower()
    assert "NOT a safe cutover" in proc.stdout
    assert "NOT advanced" in proc.stdout
    assert sandbox["origin_heads"]("base/editable-install") == head  # CAS push landed
    pointer_after = json.loads(pointer.read_text())
    assert pointer_after["generation"] == 1  # pointer unchanged
    assert pointer_after["epic"]["expected_head"] != head
    assert not list(pointer.parent.glob("runtime-manifest.json.previous-*"))


def test_promote_with_canary_flag_advances_pointer(sandbox: dict[str, object]) -> None:
    worktree = sandbox["create"]("epic-canary2")
    branch = git(worktree, "branch", "--show-current")
    head = epic_commit(worktree, "fix.txt", "fix\n", "durable fix")
    git(worktree, "push", "origin", f"HEAD:refs/heads/{branch}")
    pointer_path = str(sandbox["env"]["ARNOLD_RUNTIME_MANIFEST"])

    proc = sandbox["run"](
        PROMOTE,
        "--force-gate",
        "epic-canary2",
        str(manifest_path(sandbox, "epic-canary2")),
        extra_env={"ARNOLD_PROMOTE_SKIP_CANARY": "1"},
    )
    assert proc.returncode == 0, proc.stderr
    assert "advanced" in proc.stdout.lower()
    pointer = json.loads(Path(pointer_path).read_text())
    assert pointer["generation"] == 2
    assert pointer["epic"]["expected_head"] == head
    # advance_generation rewrote the pointer — the compatibility_only demotion
    # survives (G2 second re-run: the marker is a preserved manifest field)
    assert pointer["compatibility_only"] is True
    # previous generation retained for rollback
    retention = Path(pointer_path + ".previous-1.json")
    assert retention.exists()
    previous = json.loads(retention.read_text())
    assert previous["generation"] == 1
    assert previous["epic"]["expected_head"] != head
    # the per-slug manifest advanced with the rollback record
    m = read_manifest(sandbox, "epic-canary2")
    assert m["generation"] == 2
    assert m["promotions"][-1]["previous_generation"] == 1
    assert m["promotions"][-1]["previous_commit"] != head
    assert m["promotions"][-1]["reason"]


# ── T-0027 destructive-route census (wrapper + cli routes) ───────────────────


SUPERVISOR_RUNTIME = WRAPPER_DIR / "arnold-supervisor-runtime"


def _census_tmp_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point every reference-census store at (absent) sandbox dirs so the
    census is hermetic and injectable per test."""
    for var, sub in (
        ("ARNOLD_BASE_DIR", "base"),
        ("ARNOLD_RUNTIME_MANIFEST_DIR", "manifests"),
        ("ARNOLD_REFERENCE_CHAIN_STORE", "ref-chains"),
        ("ARNOLD_REFERENCE_MARKER_STORE", "ref-markers"),
        ("ARNOLD_REFERENCE_SCHEDULE_STORES", "ref-schedules"),
        ("ARNOLD_REFERENCE_REPAIR_QUEUE", "ref-repair-queue"),
        ("ARNOLD_REFERENCE_LEASE_STORE", "ref-leases"),
    ):
        monkeypatch.setenv(var, str(tmp_path / sub))


def _supervisor_source(tmp_path: Path) -> Path:
    """Sandbox 'Arnold source' for the supervisor wrapper.  The wrapper's
    SOURCE is the fixed literal /workspace/arnold (G4: no env selector may
    re-select it), which does not exist on developer machines, so the tests
    substitute that literal with a sandbox path via text rewrite and run the
    REAL wrapper logic.  The source must be a real git repo: the fingerprint
    pipeline runs ``git diff HEAD`` under ``pipefail`` (production source is
    always a repo)."""
    src = tmp_path / "arnold-source"
    src.mkdir()
    (src / "pyproject.toml").write_text(
        "[build-system]\nrequires = ['setuptools>=61']\nbuild-backend = 'setuptools.build_meta'\n\n"
        "[project]\nname = 'arnold'\nversion = '0.0.0'\n",
        encoding="utf-8",
    )
    git(None, "init", str(src))
    git(src, "config", "user.email", "lifecycle@example.invalid")
    git(src, "config", "user.name", "Lifecycle Tests")
    git(src, "config", "commit.gpgsign", "false")
    git(src, "add", "-A")
    git(src, "commit", "-m", "seed source")
    return src


def _supervisor_fake_python(tmp_path: Path) -> Path:
    """Fake python3 that satisfies the wrapper's venv plumbing (venv
    creation, pip install, readiness probes, receipt write) without a real
    pip install.  The reference census itself runs on the REAL python3 from
    PATH (same as arnold-gc-sweep)."""
    fake = tmp_path / "fake-python3"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        'args=("$@")\n'
        'if [[ "${args[0]}" == "-P" ]]; then\n'
        '  args=("${args[@]:1}")\n'
        "fi\n"
        'case "${args[0]}" in\n'
        "  -m)\n"
        '    if [[ "${args[1]}" == "venv" ]]; then\n'
        '      stage="${args[3]}"\n'
        '      mkdir -p "$stage/bin"\n'
        '      cp "$0" "$stage/bin/python3"\n'
        '      chmod +x "$stage/bin/python3"\n'
        "    fi\n"
        "    exit 0\n"
        "    ;;\n"
        "  -c)\n"
        "    exit 0\n"
        "    ;;\n"
        "  -)\n"
        "    printf '%s\\n' '{\"schema_version\":\"arnold-supervisor-runtime-receipt-v1\",\"status\":\"ready\"}' > \"${args[1]}\"\n"
        "    exit 0\n"
        "    ;;\n"
        "  *)\n"
        "    exit 0\n"
        "    ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake


def _supervisor_wrapper(tmp_path: Path, source: Path) -> Path:
    """The supervisor wrapper with its fixed source literal rewritten to a
    sandbox path (see _supervisor_source)."""
    text = SUPERVISOR_RUNTIME.read_text(encoding="utf-8")
    rewritten = text.replace('SOURCE="/workspace/arnold"', f'SOURCE="{source}"')
    assert rewritten != text, "supervisor wrapper source literal not found"
    wrapper = tmp_path / "arnold-supervisor-runtime"
    wrapper.write_text(rewritten, encoding="utf-8")
    wrapper.chmod(0o755)
    return wrapper


def _supervisor_env(
    tmp: Path, git_spy: dict[str, object], root: Path, fake: Path
) -> dict[str, str]:
    """PATH shims (git/rm spies, a no-op flock, and a GNU-style mv: BSD
    macOS ships no flock and its mv has no -T) plus supervisor env overrides
    for one wrapper run."""
    shims = tmp / "supervisor-shims"
    shims.mkdir(exist_ok=True)
    flock = shims / "flock"
    if not flock.exists():
        flock.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        flock.chmod(0o755)
    mv = shims / "mv"
    if not mv.exists():
        mv.write_text(
            "#!/usr/bin/env bash\n"
            "# GNU-style mv for BSD: strip -T/-Tf and unlink a symlink\n"
            "# destination first so the rename replaces it (GNU -T\n"
            "# --no-target-directory semantics).\n"
            'while [[ "$1" == -T* ]]; do shift; done\n'
            'args=("$@")\n'
            'if [[ "${#args[@]}" -ge 2 ]]; then\n'
            '  dest="${args[${#args[@]}-1]}"\n'
            '  if [[ -L "$dest" ]]; then unlink -- "$dest"; fi\n'
            "fi\n"
            'exec /bin/mv "$@"\n',
            encoding="utf-8",
        )
        mv.chmod(0o755)
    return {
        "PATH": (
            str(git_spy["dir"])
            + os.pathsep
            + str(shims)
            + os.pathsep
            + os.environ.get("PATH", "")
        ),
        "GIT_SPY_LOG": str(git_spy["log"]),
        "RM_SPY_LOG": str(git_spy["rm_log"]),
        "MEGAPLAN_SUPERVISOR_RUNTIME_ROOT": str(root),
        "MEGAPLAN_SUPERVISOR_BASE_PYTHON": str(fake),
        "ARNOLD_REFERENCE_SCHEDULE_STORES": str(tmp / "ref-schedules"),
    }


def test_supervisor_runtime_refuses_rebuild_when_runtime_referenced(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """T-0027: the venv-rebuild rm -rf is behind the reference census.  A
    custody lease referencing the exact fingerprint runtime root refuses the
    rebuild (exit 5) BEFORE the rm -rf — the rm spy sees zero -rf calls and
    the stale runtime stays on disk."""
    tmp = Path(sandbox["tmp_path"])
    wrapper = _supervisor_wrapper(tmp, _supervisor_source(tmp))
    fake = _supervisor_fake_python(tmp)
    root = tmp / "supervisor-root"
    env = _supervisor_env(tmp, git_spy, root, fake)

    # First build (no references yet) so the fingerprint runtime dir exists.
    proc = sandbox["run"](wrapper, extra_env=env)
    assert proc.returncode == 0, proc.stderr
    runtimes = list((root / "runtimes").iterdir())
    assert len(runtimes) == 1, runtimes
    runtime = runtimes[0]
    # Break the runtime so the rebuild path (and its rm -rf) is reached.
    (runtime / "bin" / "python3").chmod(0o644)

    # A custody lease references the exact runtime root.
    lease_store = tmp / "ref-leases"
    lease_store.mkdir(parents=True)
    (lease_store / "lease-1.history.jsonl").write_text(
        json.dumps({"cwd": str(runtime)}) + "\n", encoding="utf-8"
    )

    proc = sandbox["run"](wrapper, extra_env=env)
    assert proc.returncode == 5, proc.stdout + proc.stderr
    assert "REFERENCED" in proc.stderr
    assert runtime.is_dir()
    rm_log = _spy_log(Path(git_spy["rm_log"]))
    assert not any("-rf" in line for line in rm_log), rm_log


def test_supervisor_runtime_refuses_rebuild_when_census_unknown(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """T-0027 fail-closed: an unreadable/corrupt reference store makes the
    census UNKNOWN and the rebuild (rm -rf) is refused (exit 5) — delete-on-
    unknown never happens."""
    tmp = Path(sandbox["tmp_path"])
    wrapper = _supervisor_wrapper(tmp, _supervisor_source(tmp))
    fake = _supervisor_fake_python(tmp)
    root = tmp / "supervisor-root"
    env = _supervisor_env(tmp, git_spy, root, fake)

    proc = sandbox["run"](wrapper, extra_env=env)
    assert proc.returncode == 0, proc.stderr
    runtime = list((root / "runtimes").iterdir())[0]
    (runtime / "bin" / "python3").chmod(0o644)

    # A file squatting on the configured chain store path => UNKNOWN.
    chain_store = tmp / "ref-chains"
    chain_store.write_text("not a directory\n", encoding="utf-8")

    proc = sandbox["run"](wrapper, extra_env=env)
    assert proc.returncode == 5, proc.stdout + proc.stderr
    assert "UNKNOWN" in proc.stderr
    assert runtime.is_dir()
    rm_log = _spy_log(Path(git_spy["rm_log"]))
    assert not any("-rf" in line for line in rm_log), rm_log


def test_supervisor_runtime_rebuilds_stale_runtime_on_clear_census(
    sandbox: dict[str, object], git_spy: dict[str, object]
) -> None:
    """T-0027: with a CLEAR census verdict the stale runtime IS rm -rf'd and
    rebuilt (the rm spy sees the exact runtime path) and the wrapper
    completes successfully."""
    tmp = Path(sandbox["tmp_path"])
    wrapper = _supervisor_wrapper(tmp, _supervisor_source(tmp))
    fake = _supervisor_fake_python(tmp)
    root = tmp / "supervisor-root"
    env = _supervisor_env(tmp, git_spy, root, fake)

    proc = sandbox["run"](wrapper, extra_env=env)
    assert proc.returncode == 0, proc.stderr
    runtime = list((root / "runtimes").iterdir())[0]
    (runtime / "bin" / "python3").chmod(0o644)

    proc = sandbox["run"](wrapper, extra_env=env)
    assert proc.returncode == 0, proc.stderr
    rm_log = _spy_log(Path(git_spy["rm_log"]))
    assert any(str(runtime) in line for line in rm_log), rm_log
    assert runtime.is_dir()  # rebuilt in place


# ── T-0027: cli --fresh worktree reset behind the census ─────────────────────


def _fresh_worktree_registered(repo: Path, target: Path) -> bool:
    proc = _git(repo, "worktree", "list", "--porcelain")
    return any(
        line.removeprefix("worktree ").strip() == str(target)
        for line in proc.stdout.splitlines()
        if line.startswith("worktree ")
    )


def _fresh_reset_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "fresh-app"
    git(None, "init", str(repo))
    git(repo, "config", "user.email", "lifecycle@example.invalid")
    git(repo, "config", "user.name", "Lifecycle Tests")
    git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "seed")
    git(repo, "branch", "-M", "main")
    target = tmp_path / "chain-worktree"
    git(repo, "worktree", "add", "-b", "chain-fresh", str(target), "HEAD")
    return repo, target


def test_fresh_reset_refuses_when_worktree_referenced_by_lease(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """T-0027: --fresh worktree remove --force + branch -D are behind the
    reference census.  A lease referencing the exact worktree root refuses
    the reset with the worktree and branch intact (--fresh is NOT evidence)."""
    from arnold_pipelines.megaplan.cli import _reset_chain_worktree_target
    from arnold_pipelines.megaplan.types import CliError

    repo, target = _fresh_reset_repo(tmp_path)
    _census_tmp_env(monkeypatch, tmp_path)
    lease_store = tmp_path / "ref-leases"
    lease_store.mkdir(parents=True)
    (lease_store / "lease-1.history.jsonl").write_text(
        json.dumps({"cwd": str(target)}) + "\n", encoding="utf-8"
    )

    with pytest.raises(CliError) as exc_info:
        _reset_chain_worktree_target(
            repo, target, "chain-fresh", worktree_registered=_fresh_worktree_registered
        )

    assert exc_info.value.code == "worktree_reset_refused"
    assert "reference census" in str(exc_info.value)
    assert _fresh_worktree_registered(repo, target)
    assert target.exists()


def test_fresh_reset_refuses_when_census_store_corrupt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """T-0027 fail-closed: an unreadable/corrupt reference store makes the
    census UNKNOWN and the --fresh reset refuses — delete-on-unknown never
    happens."""
    from arnold_pipelines.megaplan.cli import _reset_chain_worktree_target
    from arnold_pipelines.megaplan.types import CliError

    repo, target = _fresh_reset_repo(tmp_path)
    _census_tmp_env(monkeypatch, tmp_path)
    chain_store = tmp_path / "ref-chains"
    chain_store.write_text("not a directory\n", encoding="utf-8")

    with pytest.raises(CliError) as exc_info:
        _reset_chain_worktree_target(
            repo, target, "chain-fresh", worktree_registered=_fresh_worktree_registered
        )

    assert exc_info.value.code == "worktree_reset_refused"
    assert "UNKNOWN" in str(exc_info.value)
    assert _fresh_worktree_registered(repo, target)
    assert target.exists()


def test_fresh_reset_proceeds_on_clear_census(tmp_path: Path) -> None:
    """T-0027: with a CLEAR census verdict the --fresh reset proceeds: the
    registered worktree is removed and the branch is deleted."""
    from arnold_pipelines.megaplan.cli import _reset_chain_worktree_target

    repo, target = _fresh_reset_repo(tmp_path)
    _reset_chain_worktree_target(
        repo, target, "chain-fresh", worktree_registered=_fresh_worktree_registered
    )

    assert not _fresh_worktree_registered(repo, target)
    assert not target.exists()
    show = _git(repo, "show-ref", "--verify", "--quiet", "refs/heads/chain-fresh")
    assert show.returncode != 0


def test_fresh_reset_refuses_when_active_manifest_references_worktree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """G6 round-4: the --fresh census must NOT exclude the ACTIVE manifest
    (ARNOLD_RUNTIME_MANIFEST) from its scan.  An active manifest whose
    epic.runtime_root IS the worktree refuses the reset (REFERENCED; the
    worktree and branch stay intact — --fresh is NOT evidence of safety)."""
    from arnold_pipelines.megaplan.cli import _reset_chain_worktree_target
    from arnold_pipelines.megaplan.types import CliError

    repo, target = _fresh_reset_repo(tmp_path)
    _census_tmp_env(monkeypatch, tmp_path)
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir(parents=True)
    active = manifest_dir / "epic-live.json"
    active.write_text(
        json.dumps({"epic": {"runtime_root": str(target)}}), encoding="utf-8"
    )
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(active))

    with pytest.raises(CliError) as exc_info:
        _reset_chain_worktree_target(
            repo, target, "chain-fresh", worktree_registered=_fresh_worktree_registered
        )

    assert exc_info.value.code == "worktree_reset_refused"
    assert "REFERENCED" in str(exc_info.value)
    assert _fresh_worktree_registered(repo, target)
    assert target.exists()


def test_fresh_reset_refuses_when_active_manifest_corrupt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """G6 round-4: a corrupt ACTIVE manifest makes the --fresh census UNKNOWN
    and the reset refuses — delete-on-unknown never happens (previously the
    active manifest was excluded as ``current_manifest``, collapsing UNKNOWN
    to CLEAR)."""
    from arnold_pipelines.megaplan.cli import _reset_chain_worktree_target
    from arnold_pipelines.megaplan.types import CliError

    repo, target = _fresh_reset_repo(tmp_path)
    _census_tmp_env(monkeypatch, tmp_path)
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir(parents=True)
    active = manifest_dir / "epic-live.json"
    active.write_text("{not valid json\n", encoding="utf-8")
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(active))

    with pytest.raises(CliError) as exc_info:
        _reset_chain_worktree_target(
            repo, target, "chain-fresh", worktree_registered=_fresh_worktree_registered
        )

    assert exc_info.value.code == "worktree_reset_refused"
    assert "UNKNOWN" in str(exc_info.value)
    assert _fresh_worktree_registered(repo, target)
    assert target.exists()


# ── T-0027: chain-reset plan-dir removal behind the census ───────────────────


def _chain_reset_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(REPO_ROOT),
            "ARNOLD_BASE_DIR": str(tmp_path / "base"),
            "ARNOLD_RUNTIME_MANIFEST_DIR": str(tmp_path / "manifests"),
            # No active manifest (equivalent to env unset): the census scans
            # every manifest in the (sandbox) store and an absent/corrupt
            # store is not a reference.  Tests that need an active manifest
            # override this key with the sandbox manifest path.
            "ARNOLD_RUNTIME_MANIFEST": "",
            "ARNOLD_REFERENCE_CHAIN_STORE": str(tmp_path / "ref-chains"),
            "ARNOLD_REFERENCE_MARKER_STORE": str(tmp_path / "ref-markers"),
            "ARNOLD_REFERENCE_SCHEDULE_STORES": str(tmp_path / "ref-schedules"),
            "ARNOLD_REFERENCE_REPAIR_QUEUE": str(tmp_path / "ref-repair-queue"),
            "ARNOLD_REFERENCE_LEASE_STORE": str(tmp_path / "ref-leases"),
            # Per-plan custody lease stores live under the reset's own plan
            # root: <ws>/.megaplan/plans/<plan>/custody/leases (mirrors
            # DEFAULT_PLAN_LEASE_ROOT on the box).
            "ARNOLD_REFERENCE_PLAN_LEASE_ROOT": str(
                tmp_path / "ws" / ".megaplan" / "plans"
            ),
        }
    )
    return env


def _chain_reset_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    from arnold_pipelines.megaplan.cloud.cli import _chain_state_reset_command

    workspace = tmp_path / "ws"
    plan_dir = workspace / ".megaplan" / "plans" / "epic-a"
    plan_dir.mkdir(parents=True)
    (plan_dir / "chain.yaml").write_text("milestones: []\n", encoding="utf-8")
    state_path = workspace / ".megaplan" / "plans" / ".epic_chains" / "epic-a.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "completed": [],
                "last_state": "stalled",
                "current_plan_name": "epic-a",
                "current_milestone_index": 0,
            }
        ),
        encoding="utf-8",
    )
    cmd = _chain_state_reset_command(
        workspace=str(workspace),
        state_path=str(state_path),
        log_relative="reset.log",
        force=False,
    )
    return workspace, plan_dir, state_path, cmd


def test_chain_state_reset_blocks_plan_dir_removal_when_referenced(
    tmp_path: Path,
) -> None:
    """T-0027: chain-reset's rmtree(plan_dir) is behind the reference census.
    A plan dir holding referenced custody/leases is not removed and the chain
    state is preserved; the reset reports a blocked status."""
    workspace, plan_dir, state_path, cmd = _chain_reset_fixture(tmp_path)

    lease_store = tmp_path / "ref-leases"
    lease_store.mkdir(parents=True)
    (lease_store / "lease-1.history.jsonl").write_text(
        json.dumps({"cwd": str(plan_dir)}) + "\n", encoding="utf-8"
    )

    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=_chain_reset_env(tmp_path),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads((workspace / "reset.log").read_text(encoding="utf-8"))
    assert out["status"] == "blocked"
    assert out["reason"] == "reference-census-REFERENCED"
    assert plan_dir.exists()
    assert state_path.exists()


def test_chain_state_reset_blocks_plan_dir_removal_when_census_corrupt(
    tmp_path: Path,
) -> None:
    """T-0027 fail-closed: an unreadable/corrupt reference store makes the
    census UNKNOWN and the plan dir is not removed — delete-on-unknown never
    happens."""
    workspace, plan_dir, state_path, cmd = _chain_reset_fixture(tmp_path)
    chain_store = tmp_path / "ref-chains"
    chain_store.write_text("not a directory\n", encoding="utf-8")

    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=_chain_reset_env(tmp_path),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads((workspace / "reset.log").read_text(encoding="utf-8"))
    assert out["status"] == "blocked"
    assert out["reason"] == "reference-census-UNKNOWN"
    assert plan_dir.exists()
    assert state_path.exists()


def test_chain_state_reset_removes_plan_dir_on_clear_census(tmp_path: Path) -> None:
    """T-0027: with a CLEAR census verdict the chain-reset proceeds: the
    state file and the plan dir are removed and the reset reports success."""
    workspace, plan_dir, state_path, cmd = _chain_reset_fixture(tmp_path)

    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=_chain_reset_env(tmp_path),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads((workspace / "reset.log").read_text(encoding="utf-8"))
    assert out["status"] == "reset"
    assert str(state_path) in out["removed"]
    assert str(plan_dir) in out["removed"]
    assert not plan_dir.exists()
    assert not state_path.exists()


def test_chain_state_reset_blocks_when_active_manifest_references_plan_dir(
    tmp_path: Path,
) -> None:
    """G6 round-4: the chain-reset census must NOT exclude the ACTIVE
    manifest (ARNOLD_RUNTIME_MANIFEST) from its scan.  An active manifest
    whose epic.runtime_root IS the plan dir makes the reset refuse
    (REFERENCED — zero rmtree/unlink)."""
    workspace, plan_dir, state_path, cmd = _chain_reset_fixture(tmp_path)

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir(parents=True)
    active = manifest_dir / "epic-live.json"
    active.write_text(
        json.dumps({"epic": {"runtime_root": str(plan_dir)}}), encoding="utf-8"
    )

    env = _chain_reset_env(tmp_path)
    env["ARNOLD_RUNTIME_MANIFEST"] = str(active)
    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads((workspace / "reset.log").read_text(encoding="utf-8"))
    assert out["status"] == "blocked"
    assert out["reason"] == "reference-census-REFERENCED"
    assert plan_dir.exists()
    assert state_path.exists()


def test_chain_state_reset_blocks_when_active_manifest_corrupt(
    tmp_path: Path,
) -> None:
    """G6 round-4: a corrupt ACTIVE manifest makes the census UNKNOWN — it
    was previously excluded as ``current_manifest`` so the corruption
    collapsed to CLEAR and the reset removed the plan dir (delete-on-unknown
    violated)."""
    workspace, plan_dir, state_path, cmd = _chain_reset_fixture(tmp_path)

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir(parents=True)
    active = manifest_dir / "epic-live.json"
    active.write_text("{not valid json\n", encoding="utf-8")

    env = _chain_reset_env(tmp_path)
    env["ARNOLD_RUNTIME_MANIFEST"] = str(active)
    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads((workspace / "reset.log").read_text(encoding="utf-8"))
    assert out["status"] == "blocked"
    assert out["reason"] == "reference-census-UNKNOWN"
    assert plan_dir.exists()
    assert state_path.exists()


def test_chain_state_reset_blocks_when_state_file_corrupt(tmp_path: Path) -> None:
    """G6 round-6: a corrupt/unreadable chain state file means the true
    plan/target is UNKNOWN — the reset BLOCKS and preserves the state file
    and plan dir (zero unlink/rmtree) instead of collapsing to CLEAR and
    deleting the state."""
    workspace, plan_dir, state_path, cmd = _chain_reset_fixture(tmp_path)
    state_path.write_text("{not valid json\n", encoding="utf-8")

    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=_chain_reset_env(tmp_path),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads((workspace / "reset.log").read_text(encoding="utf-8"))
    assert out["status"] == "blocked"
    assert out["reason"].startswith("state_unreadable:")
    assert out["plan_dir"] is None
    assert "removed" not in out
    assert plan_dir.exists()
    assert state_path.exists()
    assert state_path.read_text(encoding="utf-8") == "{not valid json\n"


# ── G6: epic-chain --fresh reset behind the reference census ─────────────────


def _epic_chain_reset_fixture(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    from arnold_pipelines.megaplan.cloud.cli import _epic_chain_state_reset_command

    workspace = tmp_path / "ws"
    child_spec = workspace / "epic-chain" / "child-a.yaml"
    child_spec.parent.mkdir(parents=True)
    child_spec.write_text("milestones: []\n", encoding="utf-8")
    plan_dir = workspace / ".megaplan" / "plans" / "epic-a"
    plan_dir.mkdir(parents=True)
    (plan_dir / "chain.yaml").write_text("milestones: []\n", encoding="utf-8")
    child_digest = hashlib.sha1(str(child_spec.resolve()).encode("utf-8")).hexdigest()[:12]
    child_state_path = (
        child_spec.parent
        / ".megaplan"
        / "plans"
        / ".chains"
        / f"child-a-{child_digest}.json"
    )
    child_state_path.parent.mkdir(parents=True)
    child_state_path.write_text(
        json.dumps({"current_plan_name": "epic-a"}), encoding="utf-8"
    )
    state_path = (
        child_spec.parent / ".megaplan" / "plans" / ".epic_chains" / "epic-chain.json"
    )
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps({"current_spec_path": str(child_spec), "last_state": "stalled"}),
        encoding="utf-8",
    )
    cmd = _epic_chain_state_reset_command(
        workspace=str(workspace),
        state_path=str(state_path),
        force=True,
    )
    return workspace, plan_dir, state_path, cmd


def test_epic_chain_state_reset_blocks_when_child_plan_referenced(
    tmp_path: Path,
) -> None:
    """G6: epic-chain --fresh's state unlink / plan-dir rmtree is behind the
    reference census.  A plan dir holding referenced custody/leases is not
    removed and the epic-chain state file is preserved (zero unlink/rmtree)."""
    workspace, plan_dir, state_path, cmd = _epic_chain_reset_fixture(tmp_path)

    lease_store = tmp_path / "ref-leases"
    lease_store.mkdir(parents=True)
    (lease_store / "lease-1.history.jsonl").write_text(
        json.dumps({"cwd": str(plan_dir)}) + "\n", encoding="utf-8"
    )

    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=_chain_reset_env(tmp_path),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"] == "blocked"
    assert out["reason"] == "reference-census-REFERENCED"
    assert plan_dir.exists()
    assert state_path.exists()


def test_epic_chain_state_reset_blocks_when_census_corrupt(tmp_path: Path) -> None:
    """G6 fail-closed: an unreadable/corrupt reference store makes the census
    UNKNOWN and the epic-chain state unlink / plan-dir rmtree never happens —
    delete-on-unknown never happens."""
    workspace, plan_dir, state_path, cmd = _epic_chain_reset_fixture(tmp_path)
    chain_store = tmp_path / "ref-chains"
    chain_store.write_text("not a directory\n", encoding="utf-8")

    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=_chain_reset_env(tmp_path),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"] == "blocked"
    assert out["reason"] == "reference-census-UNKNOWN"
    assert plan_dir.exists()
    assert state_path.exists()


def test_epic_chain_state_reset_removes_state_and_plan_on_clear_census(
    tmp_path: Path,
) -> None:
    """G6: with a CLEAR census verdict the epic-chain --fresh reset proceeds:
    the state file and the current child's plan dir are removed."""
    workspace, plan_dir, state_path, cmd = _epic_chain_reset_fixture(tmp_path)

    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=_chain_reset_env(tmp_path),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"] == "reset"
    assert str(state_path) in out["removed"]
    assert str(plan_dir) in out["removed"]
    assert not plan_dir.exists()
    assert not state_path.exists()


def test_epic_chain_state_reset_blocks_when_active_manifest_references_plan_dir(
    tmp_path: Path,
) -> None:
    """G6 round-4: the epic-chain --fresh census must NOT exclude the ACTIVE
    manifest (ARNOLD_RUNTIME_MANIFEST) from its scan.  An active manifest
    whose epic.runtime_root IS the child plan dir makes the reset refuse
    (REFERENCED — zero rmtree/unlink)."""
    workspace, plan_dir, state_path, cmd = _epic_chain_reset_fixture(tmp_path)

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir(parents=True)
    active = manifest_dir / "epic-live.json"
    active.write_text(
        json.dumps({"epic": {"runtime_root": str(plan_dir)}}), encoding="utf-8"
    )

    env = _chain_reset_env(tmp_path)
    env["ARNOLD_RUNTIME_MANIFEST"] = str(active)
    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"] == "blocked"
    assert out["reason"] == "reference-census-REFERENCED"
    assert plan_dir.exists()
    assert state_path.exists()


def test_epic_chain_state_reset_blocks_when_active_manifest_corrupt(
    tmp_path: Path,
) -> None:
    """G6 round-4: a corrupt ACTIVE manifest makes the epic-chain census
    UNKNOWN and the --fresh reset refuses — delete-on-unknown never happens
    (previously the active manifest was excluded as ``current_manifest``,
    collapsing UNKNOWN to CLEAR)."""
    workspace, plan_dir, state_path, cmd = _epic_chain_reset_fixture(tmp_path)

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir(parents=True)
    active = manifest_dir / "epic-live.json"
    active.write_text("{not valid json\n", encoding="utf-8")

    env = _chain_reset_env(tmp_path)
    env["ARNOLD_RUNTIME_MANIFEST"] = str(active)
    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"] == "blocked"
    assert out["reason"] == "reference-census-UNKNOWN"
    assert plan_dir.exists()
    assert state_path.exists()


def test_epic_chain_state_reset_blocks_when_state_file_corrupt(
    tmp_path: Path,
) -> None:
    """G6 round-6: a corrupt epic-chain state file makes the --fresh reset
    BLOCK — the state file and child plan dir are preserved (zero
    unlink/rmtree) instead of an empty-derived CLEAR deleting them."""
    workspace, plan_dir, state_path, cmd = _epic_chain_reset_fixture(tmp_path)
    state_path.write_text("{not valid json\n", encoding="utf-8")

    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=_chain_reset_env(tmp_path),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"] == "blocked"
    assert out["reason"].startswith("state_unreadable:")
    assert out["plan_dir"] is None
    assert "removed" not in out
    assert plan_dir.exists()
    assert state_path.exists()
    assert state_path.read_text(encoding="utf-8") == "{not valid json\n"


def test_epic_chain_state_reset_blocks_when_child_state_file_corrupt(
    tmp_path: Path,
) -> None:
    """G6 round-8: a corrupt/unreadable CHILD chain state file makes the
    --fresh reset BLOCK — the parent epic-chain state and the child plan dir
    are preserved (zero unlink/rmtree) instead of child_raw={} degrading to
    plan_dir=None -> CLEAR -> parent state unlink.  Covers both corrupt JSON
    and a non-object JSON root (mirrors the parent-state P4 handling)."""
    workspace, plan_dir, state_path, cmd = _epic_chain_reset_fixture(tmp_path)

    child_spec = workspace / "epic-chain" / "child-a.yaml"
    child_digest = hashlib.sha1(str(child_spec.resolve()).encode("utf-8")).hexdigest()[:12]
    child_state_path = (
        child_spec.parent
        / ".megaplan"
        / "plans"
        / ".chains"
        / f"child-a-{child_digest}.json"
    )
    original_parent_state = state_path.read_text(encoding="utf-8")

    for payload in ("{not valid json\n", "[]"):
        child_state_path.write_text(payload, encoding="utf-8")
        proc = subprocess.run(
            ["bash", "-c", cmd],
            env=_chain_reset_env(tmp_path),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        out = json.loads(proc.stdout)
        assert out["status"] == "blocked"
        assert out["reason"].startswith("child_state_unreadable:")
        assert out["plan_dir"] is None
        assert "removed" not in out
        assert plan_dir.exists()
        assert state_path.read_text(encoding="utf-8") == original_parent_state


def _plan_lease_event() -> dict:
    """A REAL dispatch custody-lease acquire event (worker_dispatch_wbc.py
    open_lease_store(plan_dir / "custody" / "leases") -> acquire): owner
    identity triple + grant refs, NO path field of any kind."""
    return {
        "event_id": "acquire-custody-lease-abc123",
        "lease_id": "custody-lease-abc123",
        "sequence": 1,
        "event_type": "acquire",
        "occurred_at": "2026-08-12T00:00:00+00:00",
        "custody_epoch": 1,
        "owner_host": "agentbox",
        "owner_pid": "4242",
        "owner_boot_id": "boot-1",
        "run_authority_grant_id": "attempt-1",
        "coordinator_fence_token": 0,
        "wbc_attempt_reference": "attempt-1",
        "occurrence_digest": "sha256:abc123",
        "idempotency_key": "attempt-1:start",
        "payload": {"expires_at": "2026-08-12T01:00:00+00:00"},
    }


def test_chain_state_reset_blocks_plan_dir_removal_when_plan_lease_store_present(
    tmp_path: Path,
) -> None:
    """G6: the per-plan custody lease STORE is the reference.  A plan dir
    whose <plan>/custody/leases store holds a lease file is REFERENCED even
    though the real lease records carry NO path field — the census previously
    matched only JSON path values, so chain reset could rmtree(plan_dir) with
    a live lease.  The reset must refuse (zero rmtree) and preserve the plan
    dir and chain state."""
    workspace, plan_dir, state_path, cmd = _chain_reset_fixture(tmp_path)

    lease_store = plan_dir / "custody" / "leases"
    lease_store.mkdir(parents=True)
    (lease_store / "custody-lease-abc123.history.jsonl").write_text(
        json.dumps(_plan_lease_event()) + "\n", encoding="utf-8"
    )
    # Prove the record carries NO curated path-bearing key: the reference
    # comes from STORE PRESENCE, not from any JSON path value.
    from arnold_pipelines.megaplan.cloud.runtime_references import _PATH_KEYS

    assert _PATH_KEYS.isdisjoint(_plan_lease_event().keys())
    assert _PATH_KEYS.isdisjoint(_plan_lease_event()["payload"].keys())

    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=_chain_reset_env(tmp_path),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads((workspace / "reset.log").read_text(encoding="utf-8"))
    assert out["status"] == "blocked"
    assert out["reason"] == "reference-census-REFERENCED"
    assert plan_dir.exists()  # zero rmtree
    assert lease_store.exists()
    assert state_path.exists()


def test_chain_state_reset_proceeds_when_plan_lease_store_empty(
    tmp_path: Path,
) -> None:
    """G6 empty side: a plan dir whose custody/leases store exists but holds
    no lease files is NOT referenced — the reset proceeds and removes the
    plan dir."""
    workspace, plan_dir, state_path, cmd = _chain_reset_fixture(tmp_path)
    (plan_dir / "custody" / "leases").mkdir(parents=True)

    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=_chain_reset_env(tmp_path),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads((workspace / "reset.log").read_text(encoding="utf-8"))
    assert out["status"] == "reset"
    assert str(plan_dir) in out["removed"]
    assert not plan_dir.exists()
    assert not state_path.exists()


def test_chain_state_reset_blocks_plan_dir_removal_when_plan_lease_store_corrupt(
    tmp_path: Path,
) -> None:
    """G6 fail-closed: a corrupt lease file in the plan's OWN custody/leases
    store makes the census UNKNOWN and the reset is blocked — the plan dir is
    never removed (delete-on-unknown never happens)."""
    workspace, plan_dir, state_path, cmd = _chain_reset_fixture(tmp_path)

    lease_store = plan_dir / "custody" / "leases"
    lease_store.mkdir(parents=True)
    (lease_store / "lease-corrupt.history.jsonl").write_text(
        '{"lease_id": "lease-corrupt", "event_type": "acquire", '
        '"payload": {"expires_at": "',
        encoding="utf-8",
    )

    proc = subprocess.run(
        ["bash", "-c", cmd],
        env=_chain_reset_env(tmp_path),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads((workspace / "reset.log").read_text(encoding="utf-8"))
    assert out["status"] == "blocked"
    assert out["reason"] == "reference-census-UNKNOWN"
    assert plan_dir.exists()
    assert state_path.exists()
