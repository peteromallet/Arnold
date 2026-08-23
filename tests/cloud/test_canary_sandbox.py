"""Focused tests for the disposable canary builder/restore CLIs (T7.4a).

The builder is exercised against a REAL candidate tree (git archive of this
repo at HEAD) whose frozen dependency spec is overridden to a zero-dependency
pair so the generation build stays hermetic/offline — proving:

- every redirected path (env list from the reject receipt) lives under ONE
  fresh root inside the system temp dir (path audit);
- containment REFUSES: ambient protected ARNOLD_* vars, any redirected var
  resolving outside the root, non-fresh roots, non-temp roots;
- the promote-adjacent flow (runtime-create -> append_promotion ->
  advance_generation) mutates ONLY the disposable manifest/pointer/store;
- the protected-state assertion uses the honest wording and covers the named
  live roots without a durable delta;
- the restore CLI reconstructs the complete selected-state tuple byte-exactly
  after clean completion and refuses tampered/relocated snapshots;
- special-node tar members are refused and baseline-absent state is removed.
"""

from __future__ import annotations
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.canary_sandbox import (
    PID_IDENTITY_FILE,
    SNAPSHOT_ANCHOR_FILE,
    CanaryError,
    PHASE_FILE,
    PID_FILE,
    REDIRECTED_ENV_VARS,
    build,
    containment_violations,
    liveness,
    read_snapshot_anchor,
    restore,
    sandbox_env_spec,
    supervisor_dir,
    take_snapshot,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _git(cwd: Path | None, *args: str) -> str:
    proc = subprocess.run(
        ["git", *(("-C", str(cwd)) if cwd else ()), *args],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return proc.stdout.strip()


@pytest.fixture(scope="module")
def source_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """REAL candidate tree + zero-dep frozen spec: hermetic canary source."""

    tmp_path = tmp_path_factory.mktemp("canary-src")
    repo = tmp_path / "candidate-src"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _git(repo, "config", "user.name", "Canary Tests")
    _git(repo, "config", "user.email", "canary@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    archive = subprocess.run(
        ["git", "archive", "HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        check=True,
    )
    subprocess.run(["tar", "-x", "-C", str(repo)], input=archive.stdout, check=True)
    # Keep only the runtime package surface: the canary needs the wrappers
    # and modules, not docs/evidence — keeps every sandbox lightweight.
    keep = {"arnold_pipelines", "pyproject.toml", "uv.lock", "README.md"}
    for entry in repo.iterdir():
        if entry.name not in keep and entry.name != ".git":
            subprocess.run(["rm", "-rf", str(entry)], check=True)
    (repo / "pyproject.toml").write_text(
        "[project]\n"
        'name = "sandbox-arnold"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.9"\n'
        "dependencies = []\n",
        encoding="utf-8",
    )
    (repo / "uv.lock").write_text(
        "version = 1\n"
        'requires-python = ">=3.9"\n'
        "\n"
        "[[package]]\n"
        'name = "sandbox-arnold"\n'
        'version = "0.1.0"\n'
        'source = { editable = "." }\n',
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "canary fixture: real candidate tree, zero-dep spec")
    return repo


def do_build(
    tmp_path: Path,
    source_repo: Path,
    *,
    root: Path | None = None,
    allow_non_tmp: bool = False,
) -> tuple[Path, dict]:
    root = root if root is not None else tmp_path / "canary-root"
    report = build(
        source_repo=source_repo,
        root=root,
        slug="canary",
        base_ref="HEAD",
        generation_build_strategy=None,
        allow_non_tmp=allow_non_tmp,
    )
    return root, report


# ── path audit: everything rooted under one fresh tmp dir ───────────────────


@pytest.mark.integration
def test_build_roots_everything_under_one_fresh_tmp_dir(
    tmp_path: Path, source_repo: Path
) -> None:
    root, report = do_build(tmp_path, source_repo)

    assert root.is_dir()
    assert report["path_audit"]["ok"] is True, report["path_audit"]

    # Every redirected var points inside the root AND exists on disk.
    env_spec = json.loads((root / "sandbox-env.json").read_text())
    assert set(env_spec) == set(REDIRECTED_ENV_VARS)
    for var, value in env_spec.items():
        if var == "PYTHONDONTWRITEBYTECODE":
            continue  # flag, not a filesystem path (asserted below)
        resolved = Path(value).resolve(strict=False)
        assert str(resolved).startswith(str(root.resolve())), (
            f"{var}={value} escaped the sandbox root"
        )
    assert env_spec["PYTHONDONTWRITEBYTECODE"] == "1"

    # The named layout exists under the single root.
    for rel in (
        "home",
        "tmp",
        "xdg/cache",
        "xdg/config",
        "xdg/data",
        "xdg/state",
        "cache/pip",
        "cache/uv",
        "base/runtime-candidates/canary",
        "base/runtime-venvs",
        "markers",
        "manifests",
        "journals",
        "chain",
        "remote.git",
        "src",
    ):
        assert (root / rel).exists(), f"missing sandbox element: {rel}"

    # Disposable remote: created locally, origin reference severed, and the
    # source clone's origin IS that remote — never the real origin.
    assert _git(root / "remote.git", "remote", "-v") == ""
    origin = _git(root / "src", "config", "--get", "remote.origin.url")
    assert Path(origin).resolve() == (root / "remote.git").resolve()

    # The flow ran against the DISPOSABLE manifest only.
    slug_manifest = json.loads((root / "manifests" / "canary.json").read_text())
    pointer = json.loads((root / "manifests" / "runtime-manifest.json").read_text())
    assert slug_manifest["generation"] == 2
    assert pointer["generation"] == 2
    assert slug_manifest["epic"]["runtime_root"] == str(
        root / "base" / "runtime-candidates" / "canary"
    )
    retention = sorted(
        (root / "manifests").glob("runtime-manifest.json.previous-*.json")
    )
    assert len(retention) == 1
    # Journals live in the sandbox, populated by the flow.
    creation_lines = (root / "manifests" / "creation-journal.jsonl").read_text().splitlines()
    promotion_lines = (root / "manifests" / "promotion-journal.jsonl").read_text().splitlines()
    assert len(creation_lines) == 1
    assert len(promotion_lines) == 1


@pytest.mark.integration
def test_build_asserts_no_durable_protected_state_delta_with_honest_wording(
    tmp_path: Path, source_repo: Path
) -> None:
    _, report = do_build(tmp_path, source_repo)

    delta = report["protected_state"]
    # EXACT honest wording — never "zero writes".
    assert delta["assertion"] == "no durable protected-state delta in named paths"
    assert delta["ok"] is True, delta["changed_roots"]
    assert delta["changed_roots"] == []
    assert any("zero writes" in claim for claim in delta["does_not_prove"])
    named = set(delta["roots"])
    assert {
        "live-manifest-dir",
        "live-markers",
        "live-generations",
        "source-repo-git-metadata",
        "source-repo-tracked-files",
    } <= named
    # The real source repo was read (--no-local clone) but never mutated —
    # this catches the hardlink/auto-gc cascade class of writes too.
    assert delta["roots"]["source-repo-git-metadata"]["durable_delta"] is False
    assert delta["roots"]["source-repo-tracked-files"]["durable_delta"] is False


# ── containment refusals ────────────────────────────────────────────────────


def test_containment_unit_any_redirected_var_outside_root_is_listed(
    tmp_path: Path,
) -> None:
    spec = sandbox_env_spec(tmp_path / "root")
    spec["ARNOLD_BASE_DIR"] = "/workspace"
    spec["TMPDIR"] = str(tmp_path / "elsewhere")
    violations = containment_violations(spec, tmp_path / "root")
    joined = "\n".join(violations)
    assert "ARNOLD_BASE_DIR" in joined and "/workspace" in joined
    assert "TMPDIR" in joined
    # A clean spec has no violations.
    clean = containment_violations(sandbox_env_spec(tmp_path / "root"), tmp_path / "root")
    assert clean == []


def test_containment_symlink_escape_is_caught(tmp_path: Path) -> None:
    """A redirected path that RESOLVES outside the root is a violation."""

    root = tmp_path / "r"
    (root / "tmp").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "tmp" / "escape").symlink_to(outside)
    spec = sandbox_env_spec(root)
    spec["TMPDIR"] = str(root / "tmp" / "escape")
    violations = containment_violations(spec, root)
    assert any(v.startswith("TMPDIR:") for v in violations), violations


def test_build_refuses_ambient_protected_arnold_env(
    tmp_path: Path, source_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARNOLD_BASE_DIR", "/workspace")
    monkeypatch.setenv(
        "ARNOLD_RUNTIME_MANIFEST", "/workspace/.megaplan/runtime-manifest.json"
    )
    with pytest.raises(CanaryError) as excinfo:
        do_build(tmp_path, source_repo)
    assert excinfo.value.code == "ambient_arnold_env"
    assert "ARNOLD_BASE_DIR" in excinfo.value.message
    # Refusal precedes any sandbox work.
    assert not (tmp_path / "canary-root").exists()


def test_build_refuses_non_fresh_root(tmp_path: Path, source_repo: Path) -> None:
    dirty = tmp_path / "dirty-root"
    dirty.mkdir()
    (dirty / "prior-state.txt").write_text("not empty\n", encoding="utf-8")
    with pytest.raises(CanaryError) as excinfo:
        do_build(tmp_path, source_repo, root=dirty)
    assert excinfo.value.code == "root_not_fresh"


def test_build_refuses_root_outside_system_tmp_dir(
    tmp_path: Path, source_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_tmp = tmp_path / "fake-tmp"
    fake_tmp.mkdir()
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.canary_sandbox.tempfile.gettempdir",
        lambda: str(fake_tmp),
    )
    with pytest.raises(CanaryError) as excinfo:
        do_build(tmp_path, source_repo, root=tmp_path / "elsewhere-root")
    assert excinfo.value.code == "root_not_disposable"
    # Escape hatch permits it explicitly.
    root, _ = do_build(
        tmp_path, source_repo, root=tmp_path / "allowed-root", allow_non_tmp=True
    )
    assert (root / "sandbox-env.json").exists()


# ── end-to-end environment containment (reject finding 1) ───────────────────


def _poisoned_env(tmp_path: Path) -> tuple[dict[str, str], Path]:
    """A maximally hostile ambient environment + its tripwire dir.

    - HOME, XDG_* and GIT_CONFIG_GLOBAL all carry git config poisoning the
      commit author identity if ANY git subprocess inherits them;
    - TMPDIR points at a directory that must receive zero writes;
    - PYTHONPATH carries a sitecustomize that touches a per-pid tripwire in
      EVERY python interpreter that inherits it.
    """

    poison = tmp_path / "poison"
    home = poison / "home"
    xdg = poison / "xdg"
    pypath = poison / "pypath"
    badtmp = poison / "badtmp"
    for d in (home / ".config" / "git", xdg / "git", pypath, badtmp):
        d.mkdir(parents=True)
    (home / ".gitconfig").write_text(
        "[user]\n\temail = poisoned-home@evil.invalid\n"
    )
    (xdg / "git" / "config").write_text(
        "[user]\n\temail = poisoned-xdg@evil.invalid\n"
    )
    (poison / "global-gitconfig").write_text(
        "[user]\n\temail = poisoned-global@evil.invalid\n"
    )
    (pypath / "sitecustomize.py").write_text(
        "import os\n"
        "d = os.environ.get('CANARY_TRIPWIRE_DIR', '')\n"
        "if d:\n"
        "    from pathlib import Path\n"
        "    Path(d, 'ran-%d' % os.getpid()).touch()\n"
    )
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL")}
    env.update(
        {
            "HOME": str(home),
            "TMPDIR": str(badtmp),
            "XDG_CONFIG_HOME": str(xdg),
            "XDG_CACHE_HOME": str(xdg / "cache"),
            "GIT_CONFIG_GLOBAL": str(poison / "global-gitconfig"),
            "PYTHONPATH": str(pypath),
            "CANARY_TRIPWIRE_DIR": str(poison),
        }
    )
    return env, poison


def _tripwire_pids(poison: Path) -> set[int]:
    return {
        int(p.name.split("-")[1]) for p in poison.glob("ran-*")
    }


def _probe_author_email(root: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root / "src"), "log", "-1", "--format=%ae"],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


@pytest.mark.integration
def test_poisoned_ambient_env_cannot_influence_setup_subprocesses(
    tmp_path: Path, source_repo: Path
) -> None:
    """Poisoned HOME/TMPDIR/XDG/Git-config/PYTHONPATH cannot reach ANY setup
    Git/Python subprocess — including through the installed wrapper, which
    must REPLACE (never append) PYTHONPATH."""

    env, poison = _poisoned_env(tmp_path)
    root = tmp_path / "canary-root"
    wrapper = (
        REPO_ROOT
        / "arnold_pipelines/megaplan/cloud/wrappers/arnold-canary-build"
    )
    proc = subprocess.run(
        [
            str(wrapper),
            # Poisoned TMPDIR legitimately disables ambient-tempdir
            # validation of EXPLICIT roots (fail-closed); the operator
            # override vouches for disposability while every SUBPROCESS
            # containment property below stays fully asserted.
            "--allow-non-tmp-root",
            "--source-repo",
            str(source_repo),
            "--root",
            str(root),
        ],
        cwd=tmp_path,  # outside any checkout: only PYTHONPATH imports the module
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, (proc.stdout + proc.stderr)[-4000:]
    report = json.loads(proc.stdout)
    assert report["path_audit"]["ok"] is True, report["path_audit"]["violations"]
    assert report["protected_state"]["ok"] is True
    # No python subprocess inherited the poisoned PYTHONPATH.
    assert _tripwire_pids(poison) == set(), list(poison.glob("ran-*"))
    # No ambient git config reached the probe commit.
    assert _probe_author_email(root) == "canary@sandbox.invalid"
    # Nothing was written into the poisoned TMPDIR.
    assert list((poison / "badtmp").iterdir()) == []


@pytest.mark.integration
def test_poisoned_ambient_env_cannot_reach_supervised_worker(
    tmp_path: Path, source_repo: Path
) -> None:
    """The supervisor builds the worker env from the sanitized allowlist:
    the setsid'd worker (and every candidate-module child it spawns) runs
    without the poisoned PYTHONPATH/HOME/Git-config state. Only the
    supervisor interpreter itself may have fired the tripwire at startup —
    it is launched by the test with the poisoned env by construction."""

    env, poison = _poisoned_env(tmp_path)
    root = tmp_path / "canary-root"
    supervisor = subprocess.Popen(
        _canary_argv(
            "build",
            "--supervise",
            "--allow-non-tmp-root",
            "--source-repo",
            str(source_repo),
            "--root",
            str(root),
        ),
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        out, _ = supervisor.communicate(timeout=600)
    finally:
        if supervisor.poll() is None:
            supervisor.kill()
            supervisor.communicate()
    assert supervisor.returncode == 0, out[-4000:]
    report = json.loads(out)
    assert report["supervision"]["outcome"] == "clean_exit", out[-4000:]
    assert report["path_audit"]["ok"] is True
    worker_pid = int((root / PID_FILE).read_text().strip())
    fired = _tripwire_pids(poison)
    assert worker_pid not in fired, (
        f"worker pid {worker_pid} inherited the poisoned PYTHONPATH"
    )
    assert fired <= {supervisor.pid}, (
        f"a non-supervisor subprocess fired the PYTHONPATH tripwire: {fired}"
    )
    assert _probe_author_email(root) == "canary@sandbox.invalid"


# ── snapshot / restore (deliverable 2) ──────────────────────────────────────


@pytest.fixture(scope="module")
def built_root(tmp_path_factory: pytest.TempPathFactory, source_repo: Path) -> Path:
    """One full build shared by the restore tests (post-flow, gen-2 state)."""

    base = tmp_path_factory.mktemp("canary-restore")
    root = base / "canary-root"
    build(
        source_repo=source_repo,
        root=root,
        slug="canary",
        base_ref="HEAD",
        generation_build_strategy=None,
        allow_non_tmp=False,
    )
    return root


@pytest.fixture(scope="module")
def restore_root(
    tmp_path_factory: pytest.TempPathFactory, source_repo: Path
) -> Path:
    """Dedicated full build for the in-place clean-completion restore test.

    Restore is deliberately in-place-only (relocation is refused: worktree
    admin embeds absolute paths), so this test needs its own root to mutate
    and reconstruct without disturbing ``built_root`` consumers.
    """

    base = tmp_path_factory.mktemp("canary-restore-clean")
    root = base / "canary-root"
    build(
        source_repo=source_repo,
        root=root,
        slug="canary",
        base_ref="HEAD",
        generation_build_strategy=None,
        allow_non_tmp=False,
    )
    return root



@pytest.mark.integration
def test_snapshot_covers_complete_selected_state_tuple(built_root: Path) -> None:
    manifest = json.loads(
        (built_root / "snapshot" / "snapshot.json").read_text()
    )
    assert manifest["schema"] == "arnold.megaplan.cloud.canary_snapshot.v1"
    # Every tuple path that exists at snapshot time is covered; the source
    # worktrees dir exists because runtime-create ran before the snapshot.
    coverage = manifest["coverage"]
    for rel in (
        "manifests",
        "markers",
        "chain",
        "journals",
        "base/runtime-venvs",
        "base/runtime-candidates",
        "remote.git",
        "src/.git/HEAD",
        "src/.git/index",
        "src/.git/refs",
        "src/.git/logs",
        "src/.git/worktrees",
    ):
        assert coverage.get(rel) is True, f"tuple element not covered: {rel}"

    paths = {e["path"] for e in manifest["entries"]}
    root_str = str(built_root)
    for required in (
        "manifests/runtime-manifest.json",  # pointer
        "manifests/canary.json",  # per-slug manifest
        "manifests/promotion-journal.jsonl",
        "manifests/creation-journal.jsonl",
        "markers/cloud-session-marker.json",  # marker identity
        "chain/chain-state.json",  # runtime binding / engine_root
        "chain/rebind-store.json",
        "journals/delivery-journal.jsonl",
    ):
        assert f"{root_str}/{required}" in paths, f"missing entry: {required}"
    # generation store + build lock + worktree admin are in the entries
    assert any(p.endswith("/.build.lock") for p in paths)
    assert any("/src/.git/worktrees/" in p for p in paths)
    assert any("/remote.git/refs/heads/" in p for p in paths)
    assert manifest["restored_dimensions"]
    assert "xattrs" in manifest["not_covered_dimensions"]


@pytest.mark.integration
def test_restore_reconstructs_byte_exact_after_clean_completion(
    restore_root: Path,
) -> None:
    # In-place restore: the snapshot refuses relocation (worktree admin
    # embeds absolute paths), so the post-flow drift happens in THIS root
    # and the restore reconstructs the prepared baseline here.
    root = restore_root

    # Pre-state: the flow advanced to generation 2.
    pointer = json.loads(
        (root / "manifests" / "runtime-manifest.json").read_text()
    )
    assert pointer["generation"] == 2
    # verify_only detects the post-flow divergence from the baseline.
    verdict = restore(root, verify_only=True)
    assert verdict["ok"] is False
    assert any("bytes differ" in m for m in verdict["mismatches"])

    result = restore(root)
    assert result["ok"] is True, result["mismatches"]

    # Semantic reconstruction: back at the prepared baseline (gen 1).
    pointer_after = json.loads(
        (root / "manifests" / "runtime-manifest.json").read_text()
    )
    slug_after = json.loads((root / "manifests" / "canary.json").read_text())
    assert pointer_after["generation"] == 1
    assert slug_after["generation"] == 1
    # Retention sibling is GONE (baseline had none) and journals are baseline.
    assert not list((root / "manifests").glob("runtime-manifest.json.previous-*.json"))
    assert (root / "manifests" / "promotion-journal.jsonl").read_text() == ""
    # Creation journal line survives (it predates the snapshot).
    assert len((root / "manifests" / "creation-journal.jsonl").read_text().splitlines()) == 1
    # Generation store proof intact and bound to the restored manifest.
    venvs = list((root / "base" / "runtime-venvs").glob("*/.generation.json"))
    assert venvs, "generation proof missing after restore"
    proof = json.loads(venvs[0].read_text())
    assert slug_after["epic"]["dependency_generation"]["id"] == proof["id"]
    # Marker + chain binding fixtures byte-present.
    marker = json.loads((root / "markers" / "cloud-session-marker.json").read_text())
    chain = json.loads((root / "chain" / "chain-state.json").read_text())
    assert marker["active_runtime_identity"]["runtime_root"] == str(
        root / "base" / "runtime-candidates" / "canary"
    )
    assert chain["metadata"]["execution_environment"]["engine_root"] == str(
        root / "base" / "runtime-candidates" / "canary"
    )
    # The restored worktree is a functioning git worktree again.
    head = _git(root / "base" / "runtime-candidates" / "canary", "rev-parse", "HEAD")
    assert head == slug_after["epic"]["expected_head"]


def _fake_state_root(tmp_path: Path) -> Path:
    """Minimal state tuple + snapshot WITHOUT a full flow build (fast).

    Refusal-path tests only need a valid snapshot manifest + tar; the
    end-to-end byte-exactness proof lives in the full-build tests above.
    """

    root = tmp_path / "fake-root"
    manifests = root / "manifests"
    manifests.mkdir(parents=True)
    (manifests / "runtime-manifest.json").write_text('{"generation": 1}\n')
    markers = root / "markers"
    markers.mkdir()
    (markers / "cloud-session-marker.json").write_text('{"fixture": true}\n')
    take_snapshot(root)
    return root


def test_restore_refuses_tampered_snapshot_tar(tmp_path: Path) -> None:
    root = _fake_state_root(tmp_path)
    tar_path = root / "snapshot" / "state.tar.gz"
    blob = bytearray(tar_path.read_bytes())
    blob[len(blob) // 2] ^= 0xFF
    tar_path.write_bytes(bytes(blob))
    with pytest.raises(CanaryError) as excinfo:
        restore(root)
    assert excinfo.value.code == "snapshot_digest_mismatch"


def test_restore_refuses_relocation_to_another_root(tmp_path: Path) -> None:
    import shutil

    root = _fake_state_root(tmp_path)
    elsewhere = shutil.copytree(root, tmp_path / "elsewhere", symlinks=True)
    with pytest.raises(CanaryError) as excinfo:
        restore(elsewhere)
    assert excinfo.value.code == "relocation_refused"


def test_restore_removes_state_absent_from_prepared_baseline(
    tmp_path: Path,
) -> None:
    """Post-snapshot drift (retention sibling) must NOT survive a restore."""

    root = _fake_state_root(tmp_path)
    drift = root / "manifests" / "runtime-manifest.json.previous-0.json"
    drift.write_text('{"generation": 0}\n')
    result = restore(root)
    assert result["ok"] is True, result["mismatches"]
    assert not drift.exists()
    assert "manifests" in result["wiped_paths"]


def test_restore_refuses_special_node_tar_member(tmp_path: Path) -> None:
    """A crafted snapshot smuggling a FIFO member is refused, not extracted."""

    import hashlib
    import tarfile as tarfile_mod

    root = _fake_state_root(tmp_path)
    snap_dir = root / "snapshot"
    tar_path = snap_dir / "state.tar.gz"
    with tarfile_mod.open(tar_path, "r:gz") as src:
        members = src.getmembers()
        payloads = {
            m.name: (src.extractfile(m).read() if m.isfile() else None)
            for m in members
        }
    smuggle = tarfile_mod.TarInfo("manifests/fifo")
    smuggle.type = tarfile_mod.FIFOTYPE
    with tarfile_mod.open(tar_path, "w:gz", format=tarfile_mod.PAX_FORMAT) as dst:
        for m in members:
            if m.isfile():
                import io

                dst.addfile(m, io.BytesIO(payloads[m.name]))
            else:
                dst.addfile(m)
        dst.addfile(smuggle)
    manifest = json.loads((snap_dir / "snapshot.json").read_text())
    manifest["tar_sha256"] = hashlib.sha256(tar_path.read_bytes()).hexdigest()
    (snap_dir / "snapshot.json").write_text(json.dumps(manifest))

    with pytest.raises(CanaryError) as excinfo:
        restore(root)
    assert excinfo.value.code == "special_node_unsupported"
    assert not (root / "manifests" / "fifo").exists()


def test_restore_cli_wrapper_end_to_end(tmp_path: Path, source_repo: Path) -> None:
    """The installed surface: wrapper -> module restore subcommand."""
    wrapper = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers" / "arnold-canary-restore"
    root, _ = do_build(tmp_path, source_repo)
    proc = subprocess.run(
        [str(wrapper), "--root", str(root), "--verify-only"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    assert proc.returncode == 0, proc.stderr
    verdict = json.loads(proc.stdout)
    assert verdict["mode"] == "verify_only"
    assert verdict["ok"] is False  # post-flow state differs from baseline


# ── snapshot/restore truthfulness (G7.4-PRE-2 item 2) ──


def test_verify_only_flags_directory_mode_change(tmp_path: Path) -> None:
    """RESTORED_DIMENSIONS claims mode verification for DIRECTORIES too."""

    root = _fake_state_root(tmp_path)
    (root / "manifests").chmod(0o700)
    result = restore(root, verify_only=True)
    assert result["ok"] is False
    assert any(
        "mode changed" in m and str(root / "manifests") in m
        for m in result["mismatches"]
    ), result["mismatches"]
    # A real restore repairs the mode back to the snapshotted one.
    fixed = restore(root)
    assert fixed["ok"] is True, fixed["mismatches"]


def test_verify_only_detects_unexpected_extra_entries(tmp_path: Path) -> None:
    """Extra entries under baseline-present tuple roots are DETECTED by
    --verify-only and REMOVED by a real restore (baseline-absent state)."""

    root = _fake_state_root(tmp_path)
    extra_file = root / "markers" / "extra-marker.json"
    extra_file.write_text("{\"smuggled\": true}\n")
    extra_dir = root / "manifests" / "unexpected-subdir"
    extra_dir.mkdir()
    (extra_dir / "junk.json").write_text("{}\n")

    verdict = restore(root, verify_only=True)
    assert verdict["ok"] is False
    assert any("extra-marker.json" in m for m in verdict["mismatches"]), (
        verdict["mismatches"]
    )
    assert any("unexpected-subdir" in m for m in verdict["mismatches"])

    repaired = restore(root)
    assert repaired["ok"] is True, repaired["mismatches"]
    assert not extra_file.exists() and not extra_dir.exists()
    after = restore(root, verify_only=True)
    assert after["ok"] is True, after["mismatches"]


def test_cutover_receipt_lock_and_registry_state_is_covered(tmp_path: Path) -> None:
    """Coverage invariant: cutover rollback receipts (<manifest>.cutover-
    rollback.json), pointer lock files (<name>.lock), and registry-shaped
    state co-locate under the manifests tuple root by construction, so they
    are snapshotted, restored and verified byte-exactly like every other
    entry — documented in canary_sandbox.TUPLE_PATHS commentary."""

    root = tmp_path / "fake-root"
    manifests = root / "manifests"
    manifests.mkdir(parents=True)
    pointer = manifests / "runtime-manifest.json"
    pointer.write_text('{"generation": 1, "owner": "canary-owner"}\n')
    receipt = manifests / "runtime-manifest.json.cutover-rollback.json"
    receipt.write_text('{"schema": "cutover.rollback.receipt", "pre_sha": "abc"}\n')
    lock = manifests / "runtime-manifest.json.lock"
    lock.write_text("")
    registry = manifests / "registry.json"
    registry.write_text('{"owners": {"canary": "owner-token"}}\n')
    markers = root / "markers"
    markers.mkdir()
    (markers / "cloud-session-marker.json").write_text('{"fixture": true}\n')
    take_snapshot(root)

    # Drift exactly the kind of state a live cutover would touch.
    receipt.write_text('{"schema": "cutover.rollback.receipt", "pre_sha": "TAMPERED"}\n')
    lock.unlink()
    registry.write_text('{"owners": {}}\n')

    result = restore(root)
    assert result["ok"] is True, result["mismatches"]
    assert json.loads(receipt.read_text())["pre_sha"] == "abc"
    assert lock.exists()
    assert json.loads(registry.read_text())["owners"]["canary"] == "owner-token"


def test_coordinated_tar_and_manifest_tamper_is_refused_via_anchor(
    tmp_path: Path,
) -> None:
    """A tamper that edits tar bytes AND patches the manifest's recorded tar
    digest together cannot pass: the supervisor's anchor holds the digest of
    the MANIFEST ITSELF, which such a coordinated edit necessarily changes."""

    root = _fake_state_root(tmp_path)
    snap_dir = root / "snapshot"
    manifest = snap_dir / "snapshot.json"
    tar_path = snap_dir / "state.tar.gz"

    def current_digests() -> dict:
        import hashlib

        return {
            "root": str(root),
            "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "tar_sha256": hashlib.sha256(tar_path.read_bytes()).hexdigest(),
        }

    # Happy path first: a faithful anchor lets restore proceed.
    anchor_dir = supervisor_dir(root)
    anchor_dir.mkdir(parents=True)
    (anchor_dir / SNAPSHOT_ANCHOR_FILE).write_text(json.dumps(current_digests()))
    ok_result = restore(root)
    assert ok_result["ok"] is True
    assert ok_result["snapshot_anchor"] == "verified"

    # Coordinated tamper: flip tar bytes, then patch the manifest so its
    # internal bookkeeping agrees with the new tar bytes.
    blob = bytearray(tar_path.read_bytes())
    blob[len(blob) // 2] ^= 0xFF
    tar_path.write_bytes(bytes(blob))
    import hashlib as _hl

    data = json.loads(manifest.read_text())
    data["tar_sha256"] = _hl.sha256(tar_path.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(data))

    with pytest.raises(CanaryError) as excinfo:
        restore(root)
    assert excinfo.value.code == "snapshot_anchor_mismatch"


def test_restore_without_anchor_reports_absent(tmp_path: Path) -> None:
    root = _fake_state_root(tmp_path)
    result = restore(root)
    assert result["ok"] is True
    assert result["snapshot_anchor"] == "absent"


@pytest.mark.integration
def test_supervised_stages_anchor_snapshot_and_restore_after_kill(
    tmp_path: Path, source_repo: Path
) -> None:
    """Two-stage supervision: prepare anchors the snapshot OUTSIDE worker
    state; an external kill -9 during mutation triggers an ANCHOR-VERIFIED
    restore; prepare/mutate stages are individually visible in the report."""

    root = tmp_path / "canary-root"
    env = {
        **os.environ,
        "ARNOLD_CANARY_TEST_PAUSE_AT_PHASE": "promotion-adjacent-mutation",
    }
    supervisor = subprocess.Popen(
        _canary_argv(
            "build",
            "--supervise",
            "--source-repo",
            str(source_repo),
            "--root",
            str(root),
            "--supervisor-timeout",
            "240",
        ),
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        assert _wait_for_phase(root, "promotion-adjacent-mutation"), (
            (root / "logs" / "worker.log").read_text()[-4000:]
            if (root / "logs" / "worker.log").is_file()
            else "worker never reached the pause phase"
        )
        worker_pid = int((root / PID_FILE).read_text().strip())
        os.kill(worker_pid, signal.SIGKILL)
        out, _ = supervisor.communicate(timeout=240)
    finally:
        if supervisor.poll() is None:
            supervisor.kill()
            supervisor.communicate()
    assert supervisor.returncode == 0, out[-4000:]

    report = json.loads((root / "report.json").read_text())
    assert report["outcome"] == "killed_by_signal_9", report["outcome"]
    # Staged run: prepare completed cleanly, mutate was killed mid-flow.
    assert report["stages"]["prepare"]["returncode"] == 0
    assert report["stages"]["mutate"]["returncode"] == -signal.SIGKILL
    assert report["recovery"]["attempted"] is True
    assert report["recovery"]["ok"] is True
    # The anchor exists OUTSIDE the sandbox root...
    anchor_path = supervisor_dir(root) / SNAPSHOT_ANCHOR_FILE
    assert anchor_path.is_file()
    anchored = read_snapshot_anchor(root)
    assert anchored is not None and anchored["entry_count"] > 0
    # ...and the independent verdict used it.
    verdict = restore(root, verify_only=True)
    assert verdict["ok"] is True, verdict["mismatches"]
    assert verdict["snapshot_anchor"] == "verified"
    pointer = json.loads((root / "manifests" / "runtime-manifest.json").read_text())
    assert pointer["generation"] == 1



@pytest.mark.integration
def test_prepare_stage_failure_does_not_blindly_restore(
    tmp_path: Path, source_repo: Path
) -> None:
    """Pre-snapshot death is handled EXPLICITLY: no baseline exists, so the
    supervisor must NOT call restore — it reports failed_before_snapshot
    with recovery.attempted=False instead of blindly restoring nothing."""

    root = tmp_path / "canary-root"
    env = {
        **os.environ,
        "ARNOLD_CANARY_TEST_CRASH_AFTER_PHASE": "disposable-remote",
    }
    supervisor = subprocess.Popen(
        _canary_argv(
            "build",
            "--supervise",
            "--source-repo",
            str(source_repo),
            "--root",
            str(root),
            "--supervisor-timeout",
            "240",
        ),
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        out, _ = supervisor.communicate(timeout=240)
    finally:
        if supervisor.poll() is None:
            supervisor.kill()
            supervisor.communicate()
    assert supervisor.returncode == 0, out[-4000:]
    report = json.loads((root / "report.json").read_text())
    assert report["outcome"].startswith("failed_before_snapshot"), report["outcome"]
    assert report["recovery"]["attempted"] is False
    assert "no prepared snapshot" in report["recovery"]["reason"]
    assert not (root / "snapshot" / "snapshot.json").exists()


# ── supervision + crash recovery (deliverable 3) ────────────────────────────

_MODULE = "arnold_pipelines.megaplan.cloud.canary_sandbox"


def _wait_for_phase(root: Path, phase: str, timeout: float = 300.0) -> bool:
    deadline = time.monotonic() + timeout
    phase_file = root / PHASE_FILE
    while time.monotonic() < deadline:
        if phase_file.is_file() and phase_file.read_text().strip() == phase:
            return True
        time.sleep(0.25)
    return False


def _canary_argv(*args: str) -> list[str]:
    return [sys.executable, "-m", _MODULE, *args]


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


@pytest.mark.integration
def test_unclean_worker_death_reaps_surviving_child_subprocess(
    tmp_path: Path, source_repo: Path
) -> None:
    """FAILURE INJECTION (G7.4-PRE-2 item 3): the worker leaves a REAL child
    subprocess alive inside its process group; an external SIGKILL of the
    WORKER ONLY must not let restore race that child — the supervisor kills
    the whole recorded group and PROVES it gone before restoring."""

    root = tmp_path / "canary-root"
    env = {
        **os.environ,
        "ARNOLD_CANARY_TEST_PAUSE_AT_PHASE": "promotion-adjacent-mutation",
        "ARNOLD_CANARY_TEST_SPAWN_CHILD_AT_PHASE": "promotion-adjacent-mutation",
    }
    supervisor = subprocess.Popen(
        _canary_argv(
            "build",
            "--supervise",
            "--source-repo",
            str(source_repo),
            "--root",
            str(root),
            "--supervisor-timeout",
            "240",
        ),
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        assert _wait_for_phase(root, "promotion-adjacent-mutation"), (
            (root / "logs" / "worker.log").read_text()[-4000:]
            if (root / "logs" / "worker.log").is_file()
            else "worker never reached the pause phase"
        )
        worker_pid = int((root / PID_FILE).read_text().strip())
        child_pid = int((root / ".canary-test-child-pid").read_text().strip())
        assert _pid_alive(child_pid), "injected child should be alive mid-flow"
        os.kill(worker_pid, signal.SIGKILL)  # kill the LEADER only
        out, _ = supervisor.communicate(timeout=240)
    finally:
        if supervisor.poll() is None:
            supervisor.kill()
            supervisor.communicate()
    assert supervisor.returncode == 0, out[-4000:]

    report = json.loads((root / "report.json").read_text())
    assert report["outcome"] == "killed_by_signal_9", report["outcome"]
    reaping = report["stages"]["mutate"]["process_group"]
    assert reaping is not None and reaping["sigkill_delivered"] is True
    assert reaping["group_proven_gone"] is True
    assert report["recovery"]["attempted"] is True
    assert report["recovery"]["ok"] is True
    # The surviving child was reaped WITH the group before restore ran.
    assert not _pid_alive(child_pid), (
        f"child pid {child_pid} survived the supervised recovery"
    )
    # Supervisor persisted PGID + start identity outside the sandbox root.
    sup_record = json.loads(
        (supervisor_dir(root) / "supervisor.json").read_text()
    )
    mutate_workers = [w for w in sup_record["workers"] if w["stage"] == "mutate"]
    assert mutate_workers and mutate_workers[-1]["identity"]["pgid"] == worker_pid
    assert mutate_workers[-1]["identity"]["lstart"]


def test_restart_liveness_checks_pgid_and_start_identity(tmp_path: Path) -> None:
    """A live PID alone must NOT wedge recovery forever: with recorded
    PGID+start identity MISMATCHING the live process (PID reuse), restore
    proceeds; with MATCHING identity it stays fail-closed; with NO recorded
    identity (legacy PID file) it stays fail-closed."""

    root = _fake_state_root(tmp_path)
    holder = subprocess.Popen(["sleep", "30"])
    try:
        import arnold_pipelines.megaplan.cloud.canary_sandbox as cs

        real_identity = cs._process_identity(holder.pid)
        # 1) Matching identity -> definitely our old writer -> refuse.
        (root / PID_FILE).write_text(f"{holder.pid}\n")
        (root / PID_IDENTITY_FILE).write_text(json.dumps(real_identity))
        liv = liveness(root)
        assert liv["alive"] is True and liv["identity_match"] is True
        with pytest.raises(CanaryError) as excinfo:
            restore(root)
        assert excinfo.value.code == "canary_still_running"

        # 2) Mismatching identity -> PID reuse -> restore proceeds.
        (root / PID_IDENTITY_FILE).write_text(
            json.dumps(
                {
                    "pid": holder.pid,
                    "pgid": (real_identity["pgid"] or 0) + 5_000_000,
                    "lstart": "Thu Jan  1 00:00:00 2026",
                }
            )
        )
        liv = liveness(root)
        assert liv["alive"] is True and liv["identity_match"] is False
        result = restore(root)
        assert result["ok"] is True, result["mismatches"]
        assert result["liveness"]["identity_match"] is False
    finally:
        holder.kill()
        holder.wait(timeout=10)

    # 3) Legacy bare-pid record, no identity file -> fail closed while alive.
    root2 = tmp_path / "fake-root-legacy"
    (root2 / "manifests").mkdir(parents=True)
    (root2 / "manifests" / "runtime-manifest.json").write_text('{"generation": 1}\n')
    take_snapshot(root2)
    holder2 = subprocess.Popen(["sleep", "30"])
    try:
        (root2 / PID_FILE).write_text(f"{holder2.pid}\n")
        liv = liveness(root2)
        assert liv["identity_match"] is None
        with pytest.raises(CanaryError) as excinfo2:
            restore(root2)
        assert excinfo2.value.code == "canary_still_running"
    finally:
        holder2.kill()
        holder2.wait(timeout=10)


@pytest.mark.integration
def test_supervisor_restores_after_external_kill_9_mid_flow(
    tmp_path: Path, source_repo: Path
) -> None:
    """kill -9 mid-flow -> the EXTERNAL supervisor rolls the state back."""

    root = tmp_path / "canary-root"
    env = {
        **os.environ,
        "ARNOLD_CANARY_TEST_PAUSE_AT_PHASE": "promotion-adjacent-mutation",
    }
    supervisor = subprocess.Popen(
        _canary_argv(
            "build",
            "--supervise",
            "--source-repo",
            str(source_repo),
            "--root",
            str(root),
            "--supervisor-timeout",
            "240",
        ),
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        assert _wait_for_phase(root, "promotion-adjacent-mutation"), (
            (root / "logs" / "worker.log").read_text()[-4000:]
            if (root / "logs" / "worker.log").is_file()
            else "worker never reached the pause phase"
        )
        worker_pid = int((root / PID_FILE).read_text().strip())
        os.kill(worker_pid, signal.SIGKILL)  # REAL external kill -9
        out, _ = supervisor.communicate(timeout=240)
    finally:
        if supervisor.poll() is None:
            supervisor.kill()
            supervisor.communicate()
    assert supervisor.returncode == 0, out[-4000:]

    report = json.loads((root / "report.json").read_text())
    assert report["mode"] == "build-supervised"
    assert report["outcome"] == "killed_by_signal_9", report["outcome"]
    assert report["recovery"]["ok"] is True
    # State is back at the prepared baseline: gen-1 pointer, no retention.
    pointer = json.loads((root / "manifests" / "runtime-manifest.json").read_text())
    assert pointer["generation"] == 1
    assert not list((root / "manifests").glob("runtime-manifest.json.previous-*.json"))
    assert (root / PHASE_FILE).read_text().strip() == "recovered-by-supervisor"
    # Independent verification agrees with the supervisor's verdict.
    verdict = restore(root, verify_only=True)
    assert verdict["ok"] is True, verdict["mismatches"]


@pytest.mark.integration
def test_restart_recovery_after_container_death(
    tmp_path: Path, source_repo: Path
) -> None:
    """Container death kills flow AND any supervisor: rollback on NEXT start."""

    root = tmp_path / "canary-root"
    env = {**os.environ, "ARNOLD_CANARY_TEST_PAUSE_AT_PHASE": "probe-commit"}
    flow = subprocess.Popen(
        _canary_argv("build", "--source-repo", str(source_repo), "--root", str(root)),
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    assert _wait_for_phase(root, "probe-commit"), (
        "flow never reached probe-commit (snapshot already taken)"
    )
    flow_pid = int((root / PID_FILE).read_text().strip())
    assert flow_pid == flow.pid  # unsupervised build: flow IS this process
    os.kill(flow_pid, signal.SIGKILL)
    assert flow.wait(timeout=30) == -signal.SIGKILL
    midflow_phase = (root / PHASE_FILE).read_text().strip()
    assert midflow_phase != "done"

    # Nothing survived (container-death analogue). NEXT START: the standalone
    # restore liveness-probes the recorded pid and performs the rollback.
    proc = subprocess.run(
        _canary_argv("restore", "--root", str(root)),
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr[-4000:]
    result = json.loads(proc.stdout)
    assert result["ok"] is True, result["mismatches"]
    assert result["restart_recovery_detected"] is True
    assert result["liveness"]["alive"] is False
    assert result["liveness"]["phase"] == midflow_phase
    pointer = json.loads((root / "manifests" / "runtime-manifest.json").read_text())
    assert pointer["generation"] == 1


def test_restore_refuses_while_canary_process_alive(tmp_path: Path) -> None:
    """Fail-closed liveness gate: a possibly-live writer blocks restore."""

    root = _fake_state_root(tmp_path)
    holder = subprocess.Popen(["sleep", "30"])
    try:
        (root / PID_FILE).write_text(f"{holder.pid}\n")
        with pytest.raises(CanaryError) as excinfo:
            restore(root)
        assert excinfo.value.code == "canary_still_running"
    finally:
        holder.terminate()
        holder.wait(timeout=10)
    # Once the process is gone, restore proceeds.
    result = restore(root)
    assert result["ok"] is True


def test_liveness_tracks_real_process_exit(tmp_path: Path) -> None:
    holder = subprocess.Popen(["sleep", "30"])
    (tmp_path / PID_FILE).write_text(f"{holder.pid}\n")
    live = liveness(tmp_path)
    assert live["pid"] == holder.pid and live["alive"] is True
    holder.kill()
    holder.wait(timeout=10)
    dead = liveness(tmp_path)
    assert dead["pid"] == holder.pid and dead["alive"] is False
