"""Disposable canary sandbox for promote-adjacent runtime flows (T7.4a).

Two installed surfaces back the T7.4 canary contract (mrc reject receipt
``mrc-2bf46765…``, blocking findings 1-4):

``arnold-canary-build``
    Builds a COMPLETE canary environment under ONE fresh temp root: a source
    checkout cloned from a LOCAL disposable git remote the builder creates
    (never the real origin), the dependency-generation store, manifest /
    marker / lock / journal roots, and redirected caches, temp, HOME and XDG
    state. It then runs the minimal promote-adjacent flow INSIDE that root —
    ``arnold-runtime-create`` followed by ``runtime_manifest
    append_promotion`` + ``advance_generation`` against the disposable
    manifest — never against any live path.

``arnold-canary-restore``
    Restores the complete selected-state tuple from a snapshot the builder
    took before the mutation (manifest pointer + retention siblings + marker
    identity + chain runtime binding/engine_root + rebind store + delivery
    journal + creation/promotion journals + generation store/build locks +
    runtime-root checkout state), verifying byte-exact reconstruction.

``arnold-canary-build build --supervise``
    Finding 4: in-process ERR/EXIT handling cannot fire on SIGKILL, container
    death or power loss, so ``--supervise`` runs the flow in a setsid'd
    worker with THIS process as an external supervisor. Any worker death
    without the done marker triggers restore() from the pre-mutation
    snapshot; a wedged flow is SIGKILLed at ``--supervisor-timeout`` (whole
    process group). If the container itself dies, the supervisor dies too —
    the durable recovery-on-restart path is then ``arnold-canary-restore``,
    which liveness-probes the recorded worker pid and refuses to touch state
    while a canary might still be running.

Assertion honesty (finding 3/4): the builder NEVER claims "zero writes".
It reports ``no durable protected-state delta in named paths`` — before/after
recursive SHA-256 digests of the enumerated live protected roots — and states
explicitly what that does and does not prove.

Containment (finding 3): every redirected variable is forced under the
sandbox root. The builder REFUSES to start when the ambient environment
carries any ``ARNOLD_*`` variable from the protected set (a live routing
leak), and the final subprocess environment is audited so every redirected
path resolves inside the root. A redirected var pointing outside the root is
a hard refusal, not a silent correction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

SANDBOX_SCHEMA = "arnold.megaplan.cloud.canary_sandbox.v1"
SNAPSHOT_SCHEMA = "arnold.megaplan.cloud.canary_snapshot.v1"

# Liveness / supervision bookkeeping, all INSIDE the sandbox root (finding 4:
# durable crash recovery supervised outside the canary process).
PHASE_FILE = ".canary-phase"
HEARTBEAT_FILE = ".canary-heartbeat"
PID_FILE = ".canary-pid"
WORKER_SPEC_FILE = "worker-spec.json"
PHASE_DONE = "done"
PHASE_RECOVERED = "recovered-by-supervisor"
PHASE_PREPARED = "prepared"
# Supervised staging (G7.4-PRE-2 item 2): preparation and mutation run as
# separately supervised worker stages so the supervisor can anchor the
# snapshot manifest/tar digest in SUPERVISOR-owned state between them.
STAGE_CONTEXT_FILE = "stage-context.json"
SUPERVISOR_DIR_SUFFIX = ".supervisor"
SNAPSHOT_ANCHOR_FILE = "snapshot-anchor.json"
RESTORE_REPORT = "restore-report.json"
# TEST-ONLY hooks (never set in production): the flow SIGKILLs itself after
# writing the named phase (real uncatchable kill), or pauses there forever
# so a test can deliver an EXTERNAL kill -9 mid-flow.
TEST_CRASH_PHASE_ENV = "ARNOLD_CANARY_TEST_CRASH_AFTER_PHASE"
TEST_PAUSE_PHASE_ENV = "ARNOLD_CANARY_TEST_PAUSE_AT_PHASE"

# The COMPLETE selected-state tuple (reject receipt finding 2), relative to
# the sandbox root. The pre-mutation snapshot covers exactly these paths;
# restore reconstructs exactly these paths and verifies byte-exactness.
TUPLE_PATHS: tuple[str, ...] = (
    # manifest pointer + retention siblings + pointer lock + per-slug
    # manifests + promotion/creation journals + creation lock
    "manifests",
    # marker runtime identity (cloud-session marker fixture)
    "markers",
    # chain runtime binding / metadata.execution_environment.engine_root
    # fixture + rebind store fixture
    "chain",
    # delivery journal
    "journals",
    # content-addressed dependency-generation store incl. .build.lock proofs
    os.path.join("base", "runtime-venvs"),
    # runtime-root checkout state (epic worktrees, incl. their .git files)
    os.path.join("base", "runtime-candidates"),
    # disposable remote refs/objects (creation + probe branch pushes)
    "remote.git",
    # source-side git mutation surfaces (worktree admin, refs, reflogs);
    # objects are excluded — remote.git retains authoritative copies and
    # git never rewrites existing object bytes in place.
    os.path.join("src", ".git", "HEAD"),
    os.path.join("src", ".git", "index"),
    os.path.join("src", ".git", "refs"),
    os.path.join("src", ".git", "logs"),
    os.path.join("src", ".git", "worktrees"),
    os.path.join("src", ".git", "ORIG_HEAD"),
)
# Coverage invariant (G7.4-PRE-2 item 2): cutover rollback receipts
# (``<manifest>.cutover-rollback.json``), pointer/slug lock files
# (``<name>.lock``), retention siblings, and registry/ownership state (the
# manifest ``owner`` field inside the JSON; runtime-root ownership markers
# under the venv/candidate roots) co-locate UNDER these tuple roots by
# construction — runtime_manifest writes receipts and locks NEXT TO the
# pointer, never elsewhere. The canary flow never invokes ``cutover``, so
# no receipt writer runs; if such state is present anyway, it is snapshotted,
# restored and verified byte-exactly like every other tuple entry.

# The redirect set from the reject receipt (finding 3): every location the
# canary flow could plausibly write durably outside its root. Each entry is
# forced under the sandbox root and audited for containment.
REDIRECTED_ENV_VARS: tuple[str, ...] = (
    "PYTHONDONTWRITEBYTECODE",
    "HOME",
    "TMPDIR",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_STATE_HOME",
    "PIP_CACHE_DIR",
    "UV_CACHE_DIR",
    "ARNOLD_BASE_DIR",
    "ARNOLD_BASE_REPO",
    "ARNOLD_ORIGIN_URL",
    "ARNOLD_RUNTIME_VENVS_DIR",
    "ARNOLD_RUNTIME_MANIFEST",
    "ARNOLD_RUNTIME_MANIFEST_DIR",
    "ARNOLD_WORKSPACE_MARKERS",
    "ARNOLD_PROMOTION_JOURNAL",
)

# Ambient ARNOLD_* variables whose presence in the caller's environment means
# live runtime routing could leak into (or out of) the canary. Any of these
# set at build start is a hard refusal.
_AMBIENT_CONFLICT_VARS: tuple[str, ...] = tuple(
    v for v in REDIRECTED_ENV_VARS if v.startswith("ARNOLD_")
)

# Subprocess env passthrough allowlist: everything else is dropped so no
# ambient state (PYTHONPATH, ARNOLD_*, proxy vars, ...) reaches the flow.
_ENV_PASSTHROUGH: tuple[str, ...] = ("PATH", "LANG", "LC_ALL")

DEFAULT_LIVE_BASE_DIR = "/workspace"


class CanaryError(RuntimeError):
    """Refusal or failure surfaced to the CLI as exit code 2."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ── environment spec + containment ──────────────────────────────────────────


def sandbox_env_spec(root: Path) -> dict[str, str]:
    """The redirected environment for the canary flow, all under *root*."""

    return {
        "PYTHONDONTWRITEBYTECODE": "1",
        "HOME": str(root / "home"),
        "TMPDIR": str(root / "tmp"),
        "XDG_CACHE_HOME": str(root / "xdg" / "cache"),
        "XDG_CONFIG_HOME": str(root / "xdg" / "config"),
        "XDG_DATA_HOME": str(root / "xdg" / "data"),
        "XDG_STATE_HOME": str(root / "xdg" / "state"),
        "PIP_CACHE_DIR": str(root / "cache" / "pip"),
        "UV_CACHE_DIR": str(root / "cache" / "uv"),
        "ARNOLD_BASE_DIR": str(root / "base"),
        "ARNOLD_BASE_REPO": str(root / "src"),
        "ARNOLD_ORIGIN_URL": str(root / "remote.git"),
        "ARNOLD_RUNTIME_VENVS_DIR": str(root / "base" / "runtime-venvs"),
        "ARNOLD_RUNTIME_MANIFEST": str(root / "manifests" / "runtime-manifest.json"),
        "ARNOLD_RUNTIME_MANIFEST_DIR": str(root / "manifests"),
        "ARNOLD_WORKSPACE_MARKERS": str(root / "markers"),
        "ARNOLD_PROMOTION_JOURNAL": str(
            root / "manifests" / "promotion-journal.jsonl"
        ),
    }


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def containment_violations(env: dict[str, str], root: Path) -> list[str]:
    """Audit *env*: every redirected path var MUST resolve inside *root*.

    PYTHONDONTWRITEBYTECODE is a flag, not a path — it must simply be set to
    "1". Everything else in :data:`REDIRECTED_ENV_VARS` is a filesystem path
    and is resolved (symlinks followed) before the containment check.
    """

    violations: list[str] = []
    for var in REDIRECTED_ENV_VARS:
        value = env.get(var, "")
        if not value:
            violations.append(f"{var}: missing from sandbox environment")
            continue
        if var == "PYTHONDONTWRITEBYTECODE":
            if value != "1":
                violations.append(f"{var}: must be '1', got {value!r}")
            continue
        resolved = Path(value).expanduser().resolve(strict=False)
        if not _is_under(resolved, root):
            violations.append(
                f"{var}: {value!r} resolves outside sandbox root {root}"
            )
    return violations


def ambient_conflicts(environ: dict[str, str] | None = None) -> list[str]:
    """ARNOLD_* protected variables set in the ambient environment."""

    env = os.environ if environ is None else environ
    return [v for v in _AMBIENT_CONFLICT_VARS if env.get(v, "").strip()]


# ── path audit + digests ────────────────────────────────────────────────────


def path_audit(root: Path, env: dict[str, str]) -> dict[str, Any]:
    """Verify every redirected path exists under *root* post-layout."""

    entries: dict[str, str] = {}
    violations: list[str] = []
    for var in REDIRECTED_ENV_VARS:
        value = env.get(var, "")
        entries[var] = value
        if var == "PYTHONDONTWRITEBYTECODE":
            continue
        p = Path(value)
        if not _is_under(p, root):
            violations.append(f"{var} outside root: {value}")
        elif not p.exists():
            violations.append(f"{var} missing on disk: {value}")
    return {
        "ok": not violations,
        "entries": entries,
        "violations": violations,
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def digest_tree(
    path: Path | str,
    *,
    exclude_subdirs: tuple[str, ...] = (),
    only_relpaths: list[str] | None = None,
) -> dict[str, Any]:
    """Recursive byte digest of a directory tree (deterministic order).

    Returns ``{"present", "file_count", "digest", "files"}``. ``digest`` is a
    SHA-256 over the sorted ``relpath:sha256`` lines, so any byte change in
    any covered file flips it. ``exclude_subdirs`` prunes named subtrees
    (recorded by the caller — exclusions are part of the named-roots claim).
    ``only_relpaths`` restricts coverage to exactly those relative paths
    (missing files are skipped); used for git-tracked-file digests.
    """

    root = Path(path)
    if not root.exists():
        return {"present": False, "file_count": 0, "digest": "", "files": {}}
    if only_relpaths is not None:
        wanted = sorted(set(only_relpaths))
        files: dict[str, str] = {}
        for rel in wanted:
            fp = root / rel
            if fp.is_file() and not fp.is_symlink():
                files[rel] = _sha256_file(fp)
    else:
        files = {}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in exclude_subdirs)
            for fn in sorted(filenames):
                fp = Path(dirpath) / fn
                if fp.is_symlink() or not fp.is_file():
                    continue
                files[str(fp.relative_to(root))] = _sha256_file(fp)
    blob = "\n".join(f"{rel}:{sha}" for rel, sha in sorted(files.items()))
    return {
        "present": True,
        "file_count": len(files),
        "digest": hashlib.sha256(blob.encode()).hexdigest(),
        "files": files,
    }


def default_protected_roots(
    source_repo: Path, env: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """The NAMED live protected roots the delta assertion covers.

    These are the default (unredirected) resolutions of the protected state
    on this host plus the real source repo the builder clones from. Each
    entry records its digest scope so the report's claim is exactly named.
    """

    git_dir = source_repo / ".git"
    tracked = ""
    if git_dir.exists():
        proc = subprocess.run(
            ["git", "-C", str(source_repo), "ls-files", "-z"],
            capture_output=True,
            check=False,
            env=env,
        )
        if proc.returncode == 0:
            tracked = proc.stdout.decode()
    tracked_rel = [rel for rel in tracked.split("\0") if rel]
    return [
        {
            "name": "live-manifest-dir",
            "path": f"{DEFAULT_LIVE_BASE_DIR}/.megaplan",
            "scope": "full recursive byte digest",
        },
        {
            "name": "live-markers",
            "path": f"{DEFAULT_LIVE_BASE_DIR}/markers",
            "scope": "full recursive byte digest",
        },
        {
            "name": "live-generations",
            "path": f"{DEFAULT_LIVE_BASE_DIR}/runtime-venvs",
            "scope": "full recursive byte digest",
        },
        {
            "name": "source-repo-git-metadata",
            "path": str(git_dir),
            "exclude": ["objects"],
            "scope": "recursive byte digest excluding .git/objects "
            "(content-addressed, immutable by design; refs/logs/worktrees/"
            "index are the mutation surfaces)",
        },
        {
            "name": "source-repo-tracked-files",
            "path": str(source_repo),
            "scope": f"byte digest of {len(tracked_rel)} git-tracked files",
            "tracked_relpaths": tracked_rel,
        },
    ]


def protected_state_delta(
    roots: list[dict[str, Any]], before: dict[str, Any]
) -> dict[str, Any]:
    """Re-digest the named roots and diff against *before* (honest form)."""

    per_root: dict[str, Any] = {}
    changed: list[str] = []
    for spec in roots:
        name = spec["name"]
        kwargs: dict[str, Any] = {}
        if spec.get("exclude"):
            kwargs["exclude_subdirs"] = tuple(spec["exclude"])
        if spec.get("tracked_relpaths") is not None:
            kwargs["only_relpaths"] = spec["tracked_relpaths"]
        after = digest_tree(spec["path"], **kwargs)
        delta = after != before.get(name)
        if delta:
            changed.append(name)
        per_root[name] = {
            "path": spec["path"],
            "before": {k: before.get(name, {}).get(k) for k in ("present", "file_count", "digest")},
            "after": {k: after[k] for k in ("present", "file_count", "digest")},
            "durable_delta": delta,
        }
    return {
        "assertion": "no durable protected-state delta in named paths",
        "ok": not changed,
        "changed_roots": changed,
        "roots": per_root,
        "proves": [
            "no durable net byte delta, between the two snapshots, in the "
            "enumerated protected roots"
        ],
        "does_not_prove": [
            "zero writes (files created and deleted between snapshots are "
            "invisible to before/after digests)",
            "absence of writes outside the enumerated roots",
            "absence of transient lock/cache/temp writes inside the roots",
            "metadata-only changes (xattrs/ACLs/ownership) are not digested",
            "behaviour under concurrent live writers",
        ],
    }


# ── git helpers ─────────────────────────────────────────────────────────────


def _run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        argv, cwd=str(cwd) if cwd else None, env=env,
        capture_output=True, text=True, check=False,
    )
    if check and proc.returncode != 0:
        raise CanaryError(
            "command_failed",
            f"{' '.join(argv)} failed (exit {proc.returncode}):\n{proc.stderr.strip()}",
        )
    return proc


def _git(
    cwd: Path | None,
    *args: str,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> str:
    proc = _run(
        ["git", "-C", str(cwd), *args] if cwd else ["git", *args],
        check=check,
        env=env,
    )
    return proc.stdout.strip()


# ── build flow ──────────────────────────────────────────────────────────────

_FLOW_ENV_ALLOWLIST = frozenset(_ENV_PASSTHROUGH)


def _sanitized_base_env() -> dict[str, str]:
    """The ONLY ambient state any subprocess in this module may inherit.

    Everything else — PYTHONPATH, HOME, XDG_*, GIT_*, proxy vars, ARNOLD_* —
    is dropped so poisoned caller state cannot reach any git/python child
    (reject finding 1). Callers layer the redirected spec on top.
    """

    return {k: v for k, v in os.environ.items() if k in _FLOW_ENV_ALLOWLIST}


def _flow_env(spec: dict[str, str], src: Path) -> dict[str, str]:
    env = _sanitized_base_env()
    env.update(spec)
    env["PYTHONPATH"] = str(src)
    env["ARNOLD_GENERATION_PYTHON"] = sys.executable
    env.setdefault("ARNOLD_GENERATION_BUILD_STRATEGY", "pip")
    env["GIT_CONFIG_GLOBAL"] = str(Path(spec["HOME"]) / ".gitconfig")
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def _system_temp_dir() -> Path:
    """The OS default temp dir, deliberately IGNORING ambient TMPDIR.

    A poisoned caller TMPDIR must not relocate implicit canary roots or
    fool the disposability check (reject finding 1 applies to parent-side
    decisions too). tempfile.gettempdir() cannot be used here: it honours
    and then CACHES ambient TMPDIR, so the first poisoned caller would pin
    the poison for the process lifetime.
    """

    for cand in ("/tmp", "/var/tmp", "/usr/tmp"):
        p = Path(cand)
        try:
            if p.is_dir():
                return p.resolve(strict=False)
        except OSError:
            continue
    return Path("/tmp")

def _allocate_root(explicit: str | None, allow_non_tmp: bool) -> Path:
    if explicit:
        root = Path(explicit).expanduser()
        if root.exists() and any(root.iterdir()):
            raise CanaryError(
                "root_not_fresh",
                f"--root {root} exists and is not empty — the canary needs a "
                "fresh root (refusing to mix with prior state)",
            )
        root.mkdir(parents=True, exist_ok=True)
    else:
        root = Path(
            tempfile.mkdtemp(prefix="arnold-canary-", dir=str(_system_temp_dir()))
        )
    resolved = root.resolve(strict=False)
    # Disposability reference points: the ambient temp dir (so test/CI
    # roots under a caller-provided TMPDIR keep working) OR the true system
    # default. A poisoned TMPDIR can neither relocate IMPLICIT roots (they
    # are placed under _system_temp_dir()) nor force refusal of a genuinely
    # disposable explicit root; it also cannot smuggle a root OUTSIDE both
    # references past the check.
    refs = {Path(tempfile.gettempdir()).resolve(strict=False), _system_temp_dir()}
    if not allow_non_tmp and not any(_is_under(resolved, r) for r in refs):
        raise CanaryError(
            "root_not_disposable",
            f"root {resolved} is not under any system temp dir ({sorted(refs)}) — "
            "canary roots must be disposable (pass --allow-non-tmp-root to override)",
        )
    return resolved

def _make_disposable_remote(
    root: Path, source_repo: Path, env: dict[str, str]
) -> Path:
    remote = root / "remote.git"
    # --no-local for the same inode-cascade reason as _clone_source below.
    _run(
        ["git", "clone", "--bare", "--quiet", "--no-local", str(source_repo), str(remote)],
        env=env,
    )
    # Sever the clone's back-reference to the real repo: after this, the
    # disposable remote has NO configured remote at all, so nothing in the
    # sandbox can accidentally fetch/push toward the real origin.
    _git(remote, "remote", "remove", "origin", check=False, env=env)
    _git(remote, "config", "gc.auto", "0", env=env)
    leftovers = _git(remote, "remote", "-v", check=False, env=env)
    if leftovers:
        raise CanaryError(
            "remote_not_severed",
            f"disposable remote still configures remotes:\n{leftovers}",
        )
    return remote


def _clone_source(
    root: Path, remote: Path, base_sha: str, env: dict[str, str]
) -> Path:
    src = root / "src"
    # --no-local: a hardlinked local clone shares inodes with the source
    # object store, and destination-side git housekeeping (auto-gc after
    # clone) can then cascade writes into the ORIGINAL repo's .git when the
    # shared store holds many loose objects (observed on this host). A
    # --no-local clone copies objects into the sandbox; the real repo is
    # never touched again.
    _run(
        ["git", "clone", "--quiet", "--no-local", str(remote), str(src)],
        env=env,
    )
    _git(src, "config", "user.name", "arnold-canary", env=env)
    _git(src, "config", "user.email", "canary@sandbox.invalid", env=env)
    _git(src, "config", "commit.gpgsign", "false", env=env)
    _git(src, "config", "tag.gpgsign", "false", env=env)
    _git(src, "config", "gc.auto", "0", env=env)
    _git(src, "config", "advice.detachedHead", "false", env=env)
    origin = _git(src, "config", "--get", "remote.origin.url", env=env)
    _git(src, "checkout", "--detach", base_sha, env=env)
    if Path(origin).resolve(strict=False) != remote.resolve(strict=False):
        raise CanaryError(
            "clone_origin_violation",
            f"source clone origin is {origin!r}, not the disposable remote {remote}",
        )
    return src


def _seed_selection_fixtures(
    root: Path, env: dict[str, str], worktree: Path, branch: str, head: str
) -> None:
    """Seed the selection-state tuple elements the flow itself doesn't write.

    The canary must snapshot/restore the COMPLETE selected-state tuple, so
    the builder materializes disposable fixtures for the elements that only
    live launches write (marker identity, chain runtime binding/engine_root,
    rebind store, delivery journal). These are sandbox fixtures, not live
    state; they exist so the restore surface covers the full tuple.
    """

    markers = Path(env["ARNOLD_WORKSPACE_MARKERS"])
    (markers / "cloud-session-marker.json").write_text(
        json.dumps(
            {
                "schema": "arnold.megaplan.cloud_session_marker.v1.canary_fixture",
                "note": "disposable canary fixture — never a live marker",
                "active_runtime_identity": {
                    "runtime_root": str(worktree),
                    "branch": branch,
                    "head": head,
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    chain = root / "chain"
    chain.mkdir(exist_ok=True)
    (chain / "chain-state.json").write_text(
        json.dumps(
            {
                "schema": "arnold.megaplan.chain_state.v1.canary_fixture",
                "note": "disposable canary fixture — never a live chain state",
                "metadata": {
                    "execution_environment": {"engine_root": str(worktree)},
                    "runtime_binding": {
                        "runtime_root": str(worktree),
                        "branch": branch,
                        "head": head,
                    },
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (chain / "rebind-store.json").write_text(
        json.dumps(
            {
                "schema": "arnold.megaplan.rebind_store.v1.canary_fixture",
                "note": "disposable canary fixture",
                "events": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    journals = root / "journals"
    journals.mkdir(exist_ok=True)
    (journals / "delivery-journal.jsonl").write_text("", encoding="utf-8")


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def _candidate_module_argv(env: dict[str, str], *args: str) -> list[str]:
    return [sys.executable, "-m", "arnold_pipelines.megaplan.cloud.runtime_manifest", *args]


def _phase(root: Path, name: str) -> None:
    """Advance the durable phase marker + heartbeat; honor TEST hooks."""

    heartbeat_line = f"{name} {time.time()}\n"
    (root / PHASE_FILE).write_text(name + "\n", encoding="utf-8")
    (root / HEARTBEAT_FILE).write_text(heartbeat_line, encoding="utf-8")
    crash_after = os.environ.get(TEST_CRASH_PHASE_ENV)
    if crash_after == name:
        # Real SIGKILL: no cleanup handler, trap or atexit runs — the exact
        # uncatachable-death class the supervisor must recover from.
        os.kill(os.getpid(), signal.SIGKILL)
    pause_at = os.environ.get(TEST_PAUSE_PHASE_ENV)
    if pause_at == name:
        # Park mid-flow so a test can deliver an EXTERNAL kill -9.
        while True:
            time.sleep(0.2)
            (root / HEARTBEAT_FILE).write_text(heartbeat_line, encoding="utf-8")


def liveness(root: Path) -> dict[str, Any]:
    """Liveness of the canary process recorded for *root* (finding 4).

    ``alive`` probes the recorded pid with ``os.kill(pid, 0)``. PID reuse
    cannot be distinguished, so the check is deliberately FAIL-CLOSED: a
    possibly-alive pid REFUSES restore; only a confirmed-dead pid lets the
    restart recovery proceed.
    """

    pid: int | None = None
    pid_file = root / PID_FILE
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
        except ValueError:
            pid = None
    alive = False
    if pid is not None:
        try:
            os.kill(pid, 0)
            alive = True
        except ProcessLookupError:
            alive = False
        except PermissionError:
            alive = True  # process exists, owned by another user
    phase = ""
    phase_file = root / PHASE_FILE
    if phase_file.is_file():
        phase = phase_file.read_text(encoding="utf-8").strip()
    heartbeat_age = None
    heartbeat = root / HEARTBEAT_FILE
    if heartbeat.is_file():
        heartbeat_age = round(time.time() - heartbeat.stat().st_mtime, 3)
    return {
        "pid": pid,
        "alive": alive,
        "phase": phase,
        "heartbeat_age_seconds": heartbeat_age,
        "caveat": "os.kill(pid, 0) cannot distinguish PID reuse; an "
        "'alive' verdict refuses restore rather than risk a live writer",
    }


def build(
    *,
    source_repo: Path,
    root: Path,
    slug: str,
    base_ref: str,
    generation_build_strategy: str | None,
    allow_non_tmp: bool,
    supervise: bool = False,
    supervisor_timeout: float = 900.0,
) -> dict[str, Any]:
    """Run the disposable canary build, optionally under external supervision."""

    conflicts = ambient_conflicts()
    if conflicts:
        raise CanaryError(
            "ambient_arnold_env",
            "refusing: ambient environment carries protected ARNOLD_* "
            "variables (live runtime routing would leak into the canary): "
            + ", ".join(f"{v}={os.environ[v]}" for v in conflicts),
        )
    if supervise:
        return _build_supervised(
            source_repo=source_repo,
            root=root,
            slug=slug,
            base_ref=base_ref,
            generation_build_strategy=generation_build_strategy,
            allow_non_tmp=allow_non_tmp,
            supervisor_timeout=supervisor_timeout,
        )
    allocated = _allocate_root(str(root) if root else None, allow_non_tmp)
    return _build_flow(
        source_repo=source_repo,
        root=allocated,
        slug=slug,
        base_ref=base_ref,
        generation_build_strategy=generation_build_strategy,
    )


def _build_flow(
    *,
    source_repo: Path,
    root: Path,
    slug: str,
    base_ref: str,
    generation_build_strategy: str | None,
    stage: str = "all",
) -> dict[str, Any]:
    """The promote-adjacent flow itself; *root* is already allocated/fresh.

    ``stage="all"``     unsupervised single-process run (prepare+mutate).
    ``stage="prepare"`` supervised stage 1: layout, fixtures, pre-mutation
                        snapshot; persists ``stage-context.json`` for stage
                        2 and stops at phase ``prepared``.
    ``stage="mutate"``  supervised stage 2: probe commit + promotion-adjacent
                        mutations against the prepared baseline.

    Splitting preparation from mutation (G7.4-PRE-2 item 2) is what lets the
    supervisor anchor the snapshot digest OUTSIDE worker-controlled state
    between the two stages.
    """

    t0 = time.time()
    root = Path(root)
    ctx: dict[str, Any] = {}
    if stage == "mutate":
        ctx = json.loads((root / STAGE_CONTEXT_FILE).read_text(encoding="utf-8"))
        source_repo = Path(ctx["source_repo"])
        slug = ctx["slug"]
        base_ref = ctx["base_ref"]
        generation_build_strategy = ctx.get("generation_build_strategy") or None
    else:
        source_repo = source_repo.resolve(strict=True)
        if not (source_repo / ".git").exists():
            raise CanaryError("source_repo_invalid", f"{source_repo} is not a git checkout")

    # Sanitized environment FIRST (reject finding 1): no Git/Python
    # subprocess may run before this point. Everything below — rev-parse,
    # remote creation, clone, candidate-module calls — inherits ONLY the
    # redirected spec, never ambient HOME/TMPDIR/XDG/Git-config/PYTHONPATH.
    root = Path(root)
    spec = sandbox_env_spec(root)
    flow_env = _flow_env(spec, root / "src")
    if generation_build_strategy:
        flow_env["ARNOLD_GENERATION_BUILD_STRATEGY"] = generation_build_strategy

    head = _git(source_repo, "rev-parse", "HEAD", env=flow_env)
    tree = _git(source_repo, "rev-parse", "HEAD^{tree}", env=flow_env)
    if base_ref in ("HEAD", ""):
        base_ref = head

    # Liveness record FIRST: any crash leaves a pid a supervisor or a
    # restart-time restore can probe before touching state.
    (root / PID_FILE).write_text(f"{os.getpid()}\n", encoding="utf-8")

    for sub in ("home", "tmp", "xdg/cache", "xdg/config", "xdg/data", "xdg/state",
                "cache/pip", "cache/uv", "base", "manifests", "markers",
                "journals", "logs"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    # Journals exist from birth so the path audit and the pre-mutation
    # snapshot cover concrete files (arnold-promote's default journal paths).
    for journal in (
        "manifests/promotion-journal.jsonl",
        "manifests/creation-journal.jsonl",
    ):
        (root / journal).touch()
    (root / "sandbox-env.json").write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _phase(root, "containment-audit")

    violations = containment_violations(spec, root)
    if violations:
        raise CanaryError(
            "containment_violation",
            "sandbox environment failed containment audit:\n"
            + "\n".join(f"  - {v}" for v in violations),
        )

    protected_roots = default_protected_roots(source_repo, env=flow_env)
    before: dict[str, Any] = {}
    for spec_entry in protected_roots:
        kwargs: dict[str, Any] = {}
        if spec_entry.get("exclude"):
            kwargs["exclude_subdirs"] = tuple(spec_entry["exclude"])
        if spec_entry.get("tracked_relpaths") is not None:
            kwargs["only_relpaths"] = spec_entry["tracked_relpaths"]
        before[spec_entry["name"]] = digest_tree(spec_entry["path"], **kwargs)

    if stage == "mutate":
        # Stage 2 reuses the prepared layout; heavy/side-effectful setup
        # (remote, clone, runtime-create, journal append, fixtures) ran in
        # stage 1 and MUST NOT run twice.
        src = root / "src"
        wrapper = Path(ctx["wrapper"])
    else:
        _phase(root, "disposable-remote")
        remote = _make_disposable_remote(root, source_repo, flow_env)
        _phase(root, "source-clone")
        src = _clone_source(root, remote, base_ref, flow_env)

        _phase(root, "runtime-create")
        wrapper = src / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers" / "arnold-runtime-create"
        if not wrapper.is_file():
            raise CanaryError(
                "wrapper_missing", f"candidate runtime-create wrapper missing: {wrapper}"
            )
        proc = _run([str(wrapper), slug, base_ref], cwd=root, env=flow_env, check=False)
        if proc.returncode != 0:
            raise CanaryError(
                "runtime_create_failed",
                f"arnold-runtime-create failed (exit {proc.returncode}):\n{proc.stderr}",
            )

    manifest_dir = Path(spec["ARNOLD_RUNTIME_MANIFEST_DIR"])
    slug_manifest = manifest_dir / f"{slug}.json"
    pointer = Path(spec["ARNOLD_RUNTIME_MANIFEST"])
    worktree = Path(spec["ARNOLD_BASE_DIR"]) / "runtime-candidates" / slug
    if stage == "mutate":
        branch = ctx["branch"]
    else:
        branch = _git(worktree, "branch", "--show-current", env=flow_env)
        _append_jsonl(
            manifest_dir / "creation-journal.jsonl",
            {
                "event": "canary_runtime_create",
                "slug": slug,
                "branch": branch,
                "head": base_ref,
                "manifest": str(slug_manifest),
                "runtime_root": str(worktree),
            },
        )
        _seed_selection_fixtures(root, spec, worktree, branch, base_ref)

    if stage == "mutate":
        # NEVER retake the snapshot here: the supervisor anchored the
        # prepare-stage tar digest and gzip is not deterministic — a second
        # tar would false-positive as tamper. Reuse the recorded info.
        snapshot_info = ctx["snapshot"]
    else:
        # Pre-mutation snapshot: the prepared baseline the restore CLI (and
        # the supervisor) reconstructs byte-exactly after any flow outcome.
        _phase(root, "snapshot")
        snapshot_info = take_snapshot(root)

    if stage == "prepare":
        # Hand stage 2 its full working context. The supervisor reads the
        # snapshot manifest BETWEEN the stages and anchors its digest in
        # supervisor-owned state outside this root before mutation starts.
        (root / STAGE_CONTEXT_FILE).write_text(
            json.dumps(
                {
                    "source_repo": str(source_repo),
                    "head": head,
                    "tree": tree,
                    "base_ref": base_ref,
                    "slug": slug,
                    "wrapper": str(wrapper),
                    "branch": branch,
                    "spec": spec,
                    "protected_roots": protected_roots,
                    "before": before,
                    "generation_build_strategy": generation_build_strategy or "",
                    "snapshot": snapshot_info,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        _phase(root, PHASE_PREPARED)
        return {"mode": "build-prepare", "root": str(root), "snapshot": snapshot_info}

    _phase(root, "probe-commit")
    (src / "canary-probe.txt").write_text(
        f"canary probe at {time.time()}\n", encoding="utf-8"
    )
    _git(src, "add", "canary-probe.txt", env=flow_env)
    _git(src, "commit", "-m", "canary: probe commit (scratch, not promoted code)", env=flow_env)
    probe_sha = _git(src, "rev-parse", "HEAD", env=flow_env)
    _git(src, "push", "origin", f"HEAD:refs/heads/canary/{slug}-probe", env=flow_env)

    _phase(root, "promotion-adjacent-mutation")
    promotion_record = {
        "slug": slug,
        "from_sha": base_ref,
        "to_sha": probe_sha,
        "reason": f"canary promote-adjacent flow for {slug}",
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _append_jsonl(Path(spec["ARNOLD_PROMOTION_JOURNAL"]), promotion_record)
    _run(
        _candidate_module_argv(
            flow_env,
            "append_promotion",
            str(slug_manifest),
            json.dumps(
                {
                    "previous_generation": 1,
                    "previous_commit": base_ref,
                    "reason": promotion_record["reason"],
                    "at": promotion_record["at"],
                }
            ),
        ),
        cwd=src,
        env=flow_env,
    )
    _run(
        _candidate_module_argv(
            flow_env,
            "advance_generation",
            str(slug_manifest),
            probe_sha,
            "--reason",
            f"canary advance_generation for {slug} (disposable root {root})",
        ),
        cwd=src,
        env=flow_env,
    )

    _phase(root, "post-verify")
    advanced = json.loads(slug_manifest.read_text(encoding="utf-8"))
    pointer_now = json.loads(pointer.read_text(encoding="utf-8"))
    retention = sorted(manifest_dir.glob(f"{pointer.name}.previous-*.json"))
    if int(advanced.get("generation", 0)) != 2:
        raise CanaryError(
            "advance_not_observed",
            f"slug manifest generation is {advanced.get('generation')!r}, expected 2",
        )
    if int(pointer_now.get("generation", 0)) != 2:
        raise CanaryError(
            "pointer_not_advanced",
            f"active pointer generation is {pointer_now.get('generation')!r}, expected 2",
        )
    if not retention:
        raise CanaryError(
            "retention_missing",
            f"no retention sibling written next to the pointer in {manifest_dir}",
        )

    _phase(root, "protected-delta-assertion")
    delta = protected_state_delta(protected_roots, before)
    audit = path_audit(root, spec)
    if not audit["ok"]:
        raise CanaryError(
            "path_audit_failed",
            "post-build path audit failed:\n"
            + "\n".join(f"  - {v}" for v in audit["violations"]),
        )

    report: dict[str, Any] = {
        "schema": SANDBOX_SCHEMA,
        "mode": "build",
        "root": str(root),
        "candidate": {
            "source_repo": str(source_repo),
            "source_head": head,
            "source_tree": tree,
            "note": "source_head is the commit; source_tree is the tree object "
            "(distinct objects — do not conflate)",
            "interpreter": {
                "path": sys.executable,
                "sha256": _sha256_file(Path(sys.executable).resolve())
                if Path(sys.executable).resolve().is_file()
                else "",
                "version": sys.version.split()[0],
            },
            "runtime_create_wrapper": str(wrapper),
        },
        "slug": slug,
        "base_ref": base_ref,
        "probe_commit": probe_sha,
        "flow": {
            "runtime_create": "ok",
            "append_promotion": "ok",
            "advance_generation": "ok",
            "pointer_generation": pointer_now.get("generation"),
            "slug_generation": advanced.get("generation"),
            "retention_siblings": [p.name for p in retention],
        },
        "sandbox_env": str(root / "sandbox-env.json"),
        "path_audit": audit,
        "snapshot": snapshot_info,
        "protected_state": delta,
        "duration_seconds": round(time.time() - t0, 3),
    }
    (root / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _phase(root, "done")
    return report

def _worker_main(spec_path: str) -> int:
    """Entry point of the supervised flow worker (see _build_supervised)."""

    cfg = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    _build_flow(
        source_repo=Path(cfg["source_repo"]),
        root=Path(cfg["root"]),
        slug=cfg["slug"],
        base_ref=cfg.get("base_ref") or "HEAD",
        generation_build_strategy=cfg.get("generation_build_strategy") or None,
        stage=cfg.get("stage", "all"),
    )
    return 0


def _run_supervised_worker(
    spec_path: Path,
    log_path: Path,
    worker_env: dict[str, str],
    timeout: float,
) -> tuple[int | None, bool]:
    """Run ONE setsid'd worker stage; returns ``(returncode, timed_out)``.

    The worker is its own process-group leader (start_new_session), so the
    watchdog timeout SIGKILLs the whole group — git/pip children included.
    """

    module = "arnold_pipelines.megaplan.cloud.canary_sandbox"
    worker_rc: int | None = None
    timed_out = False
    with open(log_path, "ab") as log_fh:
        worker = subprocess.Popen(
            [sys.executable, "-m", module, "_worker", str(spec_path)],
            cwd=str(spec_path.parent),
            env=worker_env,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # setsid: worker leads its own pgroup
        )
        deadline = time.monotonic() + timeout
        while True:
            worker_rc = worker.poll()
            if worker_rc is not None:
                break
            if time.monotonic() >= deadline:
                timed_out = True
                try:
                    os.killpg(worker.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                worker_rc = worker.wait(timeout=30)
                break
            time.sleep(0.25)
    return worker_rc, timed_out


def _outcome_label(worker_rc: int | None, timed_out: bool) -> str:
    if timed_out:
        return "supervisor_timeout_sigkill"
    if isinstance(worker_rc, int) and worker_rc < 0:
        return f"killed_by_signal_{-worker_rc}"
    return f"exit_{worker_rc}"


def _build_supervised(
    *,
    source_repo: Path,
    root: Path,
    slug: str,
    base_ref: str,
    generation_build_strategy: str | None,
    allow_non_tmp: bool,
    supervisor_timeout: float,
) -> dict[str, Any]:
    """The flow under an EXTERNAL supervisor, split into two stages.

    Stage ``prepare`` builds the layout + fixtures and takes the
    pre-mutation snapshot, then exits. THIS process then records the
    snapshot manifest/tar digests in supervisor-owned state OUTSIDE the
    sandbox root (:func:`supervisor_dir`) — state the mutation-stage worker
    is neither told about nor points at via its redirected environment.
    Only then does stage ``mutate`` run. On any unclean mutate outcome the
    anchor is re-verified against the on-disk snapshot BEFORE restore; a
    coordinated tamper (tar bytes AND manifest bookkeeping edited together)
    cannot pass both the anchored manifest digest and the anchored tar
    digest, so rollback-denial is detected instead of silently obeyed.

    Pre-snapshot death is handled explicitly: an unclean PREPARE stage has
    NO baseline to restore, so restore is NOT attempted — the report says
    so and the restart path is a fresh build. Container/host death kills
    the supervisor too; recovery-on-restart remains ``arnold-canary-restore
    --root <root>``, which liveness-probes the recorded pid and honours the
    same anchor when present.

    Honest scope note: supervisor and worker share a uid. The anchor
    defends against corruption / rollback-denial by the flow's own write
    surface (everything its environment points at), not against a
    deliberately hostile process that guesses sibling paths.
    """

    root = _allocate_root(str(root) if root else None, allow_non_tmp)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    builder_root = str(Path(__file__).resolve().parents[3])
    # SANITIZED worker env (reject finding 1): allowlisted passthrough plus
    # the redirected spec only; ONLY the test-only hooks are forwarded.
    worker_env = _flow_env(sandbox_env_spec(root), Path(builder_root))
    for hook in (TEST_CRASH_PHASE_ENV, TEST_PAUSE_PHASE_ENV):
        if hook in os.environ:
            worker_env[hook] = os.environ[hook]

    def spec_for(stage: str) -> Path:
        spec_path = root / WORKER_SPEC_FILE
        spec_path.write_text(
            json.dumps(
                {
                    "source_repo": str(source_repo),
                    "root": str(root),
                    "slug": slug,
                    "base_ref": base_ref or "HEAD",
                    "generation_build_strategy": generation_build_strategy or "",
                    "stage": stage,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return spec_path

    log_path = root / "logs" / "worker.log"
    stages: dict[str, Any] = {}

    def finish(result: dict[str, Any], phase: str | None = None) -> dict[str, Any]:
        result["stages"] = stages
        result["supervisor_anchor"] = str(supervisor_dir(root))
        (root / "report.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if phase:
            _phase(root, phase)
        return result

    # ── stage 1: prepare ────────────────────────────────────────────────
    prep_rc, prep_timed_out = _run_supervised_worker(
        spec_for("prepare"), log_path, worker_env, supervisor_timeout
    )
    stages["prepare"] = {"returncode": prep_rc, "timed_out": prep_timed_out}

    snap_dir = root / SNAPSHOT_DIR
    manifest_path = snap_dir / SNAPSHOT_MANIFEST
    tar_file = snap_dir / SNAPSHOT_TAR
    prepared_clean = (
        not prep_timed_out
        and prep_rc == 0
        and manifest_path.is_file()
        and tar_file.is_file()
    )
    if not prepared_clean:
        # EXPLICIT pre-snapshot death handling: there is no prepared
        # baseline, so calling restore here would be blind — refuse loudly
        # and leave the scene for a fresh build.
        outcome = _outcome_label(prep_rc, prep_timed_out)
        return finish(
            {
                "schema": SANDBOX_SCHEMA,
                "mode": "build-supervised",
                "root": str(root),
                "outcome": f"failed_before_snapshot ({outcome})",
                "worker_returncode": prep_rc,
                "phase_at_death": (
                    (root / PHASE_FILE).read_text().strip()
                    if (root / PHASE_FILE).is_file()
                    else ""
                ),
                "recovery": {
                    "attempted": False,
                    "reason": "no prepared snapshot exists; restore would be "
                    "a blind call — rerun arnold-canary-build with a fresh root",
                },
                "note": "prepare stage died before taking the pre-mutation "
                "snapshot; nothing was mutated, so no rollback is needed.",
            },
            phase="failed-before-snapshot",
        )

    data = load_snapshot(snap_dir)
    actual_tar_sha = _sha256_file(tar_file)
    if actual_tar_sha != data["tar_sha256"]:
        return finish(
            {
                "schema": SANDBOX_SCHEMA,
                "mode": "build-supervised",
                "root": str(root),
                "outcome": "snapshot_inconsistent_after_prepare",
                "recovery": {
                    "attempted": False,
                    "reason": "snapshot manifest/tar disagree immediately "
                    "after prepare; refusing to anchor untrusted bytes",
                },
            },
            phase="failed-before-snapshot",
        )
    anchor_path = supervisor_dir(root) / SNAPSHOT_ANCHOR_FILE
    anchor_path.parent.mkdir(parents=True, exist_ok=True)
    anchor_path.write_text(
        json.dumps(
            {
                "root": str(root),
                "manifest_sha256": _sha256_file(manifest_path),
                "tar_sha256": actual_tar_sha,
                "entry_count": data.get("entry_count"),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "writer": "supervisor between prepare and mutate stages",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    # ── stage 2: mutate ─────────────────────────────────────────────────
    mut_rc, mut_timed_out = _run_supervised_worker(
        spec_for("mutate"), log_path, worker_env, supervisor_timeout
    )
    stages["mutate"] = {"returncode": mut_rc, "timed_out": mut_timed_out}

    phase_at_death = ""
    phase_file = root / PHASE_FILE
    if phase_file.is_file():
        phase_at_death = phase_file.read_text(encoding="utf-8").strip()

    if (
        not mut_timed_out
        and mut_rc == 0
        and phase_at_death == PHASE_DONE
        and (root / "report.json").is_file()
    ):
        report = json.loads((root / "report.json").read_text(encoding="utf-8"))
        report["supervision"] = {
            "used": True,
            "outcome": "clean_exit",
            "worker_returncode": mut_rc,
            "anchor": "verified-at-restore-time-if-used",
            "note": "flow completed under supervision; the pre-mutation "
            "snapshot is retained for arnold-canary-restore --verify-only",
        }
        (root / "report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return finish(report)

    # Unclean mutate outcome. Re-verify the anchor BEFORE trusting the
    # snapshot: coordinated tar/manifest tamper is rollback-denial, not a
    # baseline.
    anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
    if (
        _sha256_file(manifest_path) != anchor["manifest_sha256"]
        or _sha256_file(tar_file) != anchor["tar_sha256"]
    ):
        result = finish(
            {
                "schema": SANDBOX_SCHEMA,
                "mode": "build-supervised",
                "root": str(root),
                "outcome": "snapshot_anchor_mismatch",
                "worker_returncode": mut_rc,
                "phase_at_death": phase_at_death,
                "liveness": liveness(root),
                "recovery": {
                    "attempted": False,
                    "reason": "snapshot changed after the supervisor anchored "
                    "it — refusing to restore untrusted bytes",
                },
            }
        )
        raise CanaryError(
            "snapshot_anchor_mismatch",
            "snapshot manifest/tar no longer match the supervisor's anchor; "
            f"report at {root / 'report.json'}",
        )

    outcome = _outcome_label(mut_rc, mut_timed_out)
    recovery = restore(root)
    result: dict[str, Any] = {
        "schema": SANDBOX_SCHEMA,
        "mode": "build-supervised",
        "root": str(root),
        "outcome": outcome,
        "worker_returncode": mut_rc,
        "phase_at_death": phase_at_death,
        "liveness": liveness(root),
        "recovery": {
            "attempted": True,
            "ok": recovery["ok"],
            "verified_entries": recovery["verified_entries"],
            "extra_entries": recovery.get("extra_entries", []),
            "report": str(root / "snapshot" / RESTORE_REPORT),
        },
        "note": "worker ran setsid'd under this supervisor in two stages; "
        "unclean mutation triggered anchor-verified restore of the "
        "pre-mutation snapshot. Container/host death kills the supervisor "
        "too — the restart path is arnold-canary-restore --root <root>.",
    }
    return finish(result, phase=PHASE_RECOVERED)


# ── snapshot / restore ──────────────────────────────────────────────────────

SNAPSHOT_DIR = "snapshot"
SNAPSHOT_TAR = "state.tar.gz"
SNAPSHOT_MANIFEST = "snapshot.json"


def supervisor_dir(root: Path) -> Path:
    """Supervisor-owned state OUTSIDE the sandbox root.

    The flow worker is never told this path and its redirected environment
    contains no reference to it, so the flow's write surface cannot reach
    it. This is where the snapshot manifest/tar digest is ANCHORED between
    the supervised prepare and mutate stages, and where restart recovery
    looks for it. Honest scope note: supervisor and worker share a uid —
    the anchor defends against corruption/rollback-denial by the flow's own
    write surface, not against a hostile process that guesses sibling paths.
    """

    return Path(str(Path(root).resolve(strict=False)) + SUPERVISOR_DIR_SUFFIX)


def read_snapshot_anchor(root: Path) -> dict[str, Any] | None:
    """The supervisor's anchored snapshot digests, when present."""

    anchor_path = supervisor_dir(root) / SNAPSHOT_ANCHOR_FILE
    if not anchor_path.is_file():
        return None
    return json.loads(anchor_path.read_text(encoding="utf-8"))

# Dimensions the restore VERIFIES vs. dimensions it explicitly does NOT
# cover. Recorded verbatim in every snapshot.json and restore report.
RESTORED_DIMENSIONS = (
    "existence",
    "object type (file/dir/symlink)",
    "file bytes (SHA-256)",
    "symlink target",
    "mode (permission bits)",
)
NOT_COVERED_DIMENSIONS = (
    "xattrs",
    "ACLs",
    "uid/gid ownership",
    "atime/mtime timestamps",
    "hardlink identity: a hardlinked FILE at snapshot time is refused "
    "loudly rather than restored wrongly; symlinks are preserved as such",
    "FIFO/socket/device nodes: recorded and existence-checked only, no "
    "content semantics",
)


def _entry_for(path: Path) -> dict[str, Any]:
    import stat as stat_mod

    st = path.lstat()
    mode = stat_mod.S_IMODE(st.st_mode)
    entry: dict[str, Any] = {
        "path": str(path),
        "mode": mode,
        "size": st.st_size,
    }
    if stat_mod.S_ISLNK(st.st_mode):
        entry["type"] = "symlink"
        entry["target"] = os.readlink(path)
    elif stat_mod.S_ISDIR(st.st_mode):
        entry["type"] = "dir"
    elif stat_mod.S_ISREG(st.st_mode):
        entry["type"] = "file"
        if st.st_nlink > 1:
            raise CanaryError(
                "hardlink_unsupported",
                f"{path} is a hardlink (nlink={st.st_nlink}); the snapshot "
                "refuses state it could not faithfully restore — reconcile "
                "the sandbox before re-snapshotting",
            )
        entry["sha256"] = _sha256_file(path)
    else:
        entry["type"] = "special"
    return entry


def take_snapshot(root: Path) -> dict[str, Any]:
    """Snapshot the selected-state tuple under *root* before mutation.

    Produces ``<root>/snapshot/state.tar.gz`` plus ``snapshot.json`` whose
    per-entry SHA-256 records make restore a VERIFIED reconstruction rather
    than a blind untar. A covered path that is itself a file (e.g.
    ``src/.git/HEAD``) or symlink is snapshotted as its own entry.
    """

    root = Path(root).resolve(strict=False)
    snap_dir = root / SNAPSHOT_DIR
    snap_dir.mkdir(parents=True, exist_ok=True)
    tar_path = snap_dir / SNAPSHOT_TAR

    entries: list[dict[str, Any]] = []
    coverage: dict[str, bool] = {}
    with tarfile.open(tar_path, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        for rel in TUPLE_PATHS:
            base = root / rel
            exists = base.exists() or base.is_symlink()
            coverage[rel] = exists
            if not exists:
                continue
            # The covered path itself (file/symlink/dir), then children.
            entries.append(_entry_for(base))
            arcname = rel
            info = tar.gettarinfo(str(base), arcname=arcname)
            if info.isfile():
                with open(base, "rb") as fh:
                    tar.addfile(info, fh)
            else:
                tar.addfile(info)
            if base.is_dir() and not base.is_symlink():
                for dirpath, dirnames, filenames in os.walk(base):
                    dirnames.sort()
                    for name in sorted(dirnames) + sorted(filenames):
                        p = Path(dirpath) / name
                        entries.append(_entry_for(p))
                        minfo = tar.gettarinfo(
                            str(p), arcname=str(p.relative_to(root))
                        )
                        if minfo.isfile():
                            with open(p, "rb") as fh:
                                tar.addfile(minfo, fh)
                        elif minfo.isdir() or minfo.issym():
                            tar.addfile(minfo)
                        # special nodes: recorded, never archived

    manifest = {
        "schema": SNAPSHOT_SCHEMA,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "root": str(root),
        "coverage": coverage,
        "entries": entries,
        "entry_count": len(entries),
        "tar": SNAPSHOT_TAR,
        "tar_sha256": _sha256_file(tar_path),
        "restored_dimensions": list(RESTORED_DIMENSIONS),
        "not_covered_dimensions": list(NOT_COVERED_DIMENSIONS),
        "note": "restore is verified byte-exact for the listed dimensions "
        "over the enumerated tuple paths; relocation to another root is "
        "refused because worktree admin embeds absolute paths. Symlink "
        "TARGETS are preserved verbatim and may legitimately point outside "
        "the root (e.g. a venv interpreter link to the host interpreter); "
        "only member PATHS are containment-audited.",
    }
    tmp = snap_dir / (SNAPSHOT_MANIFEST + ".tmp")
    tmp.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(tmp, snap_dir / SNAPSHOT_MANIFEST)
    return {
        "taken": True,
        "dir": str(snap_dir),
        "manifest": str(snap_dir / SNAPSHOT_MANIFEST),
        "tar_sha256": manifest["tar_sha256"],
        "entry_count": len(entries),
        "coverage": coverage,
    }


def load_snapshot(snapshot_dir: Path) -> dict[str, Any]:
    """Load + validate a snapshot manifest."""

    manifest_path = Path(snapshot_dir) / SNAPSHOT_MANIFEST
    if not manifest_path.is_file():
        raise CanaryError(
            "snapshot_missing", f"no snapshot manifest at {manifest_path}"
        )
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("schema") != SNAPSHOT_SCHEMA:
        raise CanaryError(
            "snapshot_schema_unknown",
            f"snapshot schema {data.get('schema')!r} is not {SNAPSHOT_SCHEMA}",
        )
    return data


def verify_against_entries(
    root: Path, entries: list[dict[str, Any]]
) -> list[str]:
    """Check current disk state against snapshot entries; return mismatches."""

    mismatches: list[str] = []
    for e in entries:
        p = Path(e["path"])
        if not p.exists() and not p.is_symlink():
            mismatches.append(f"{e['path']}: missing")
            continue
        try:
            cur = _entry_for(p)
        except CanaryError:
            cur = None
            mismatches.append(f"{e['path']}: became a hardlink (uncovered)")
        except OSError as exc:
            cur = None
            mismatches.append(f"{e['path']}: unreadable ({exc})")
        if cur is None:
            continue
        if cur["type"] != e["type"]:
            mismatches.append(f"{e['path']}: type {e['type']} -> {cur['type']}")
            continue
        if e["type"] == "file":
            if cur.get("sha256") != e.get("sha256"):
                mismatches.append(f"{e['path']}: bytes differ")
            if cur.get("mode") != e.get("mode"):
                mismatches.append(f"{e['path']}: mode changed")
        elif e["type"] == "dir":
            if cur.get("mode") != e.get("mode"):
                mismatches.append(f"{e['path']}: mode changed")
        elif e["type"] == "symlink":
            if cur.get("target") != e.get("target"):
                mismatches.append(f"{e['path']}: symlink target changed")
    return mismatches


def _extra_entries(root: Path, data: dict[str, Any]) -> list[str]:
    """Current entries under BASELINE-PRESENT tuple roots that the snapshot
    does not know about — unexpected additions (G7.4-PRE-2 item 2).

    Only roots present at snapshot time are walked: a root absent from the
    prepared baseline is handled by the coverage-absence check instead.
    """

    known = {e["path"] for e in data.get("entries", [])}
    extras: list[str] = []
    for rel, existed in sorted(data.get("coverage", {}).items()):
        if not existed:
            continue
        base = Path(root) / rel
        if not (base.is_dir() and not base.is_symlink()):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames.sort()
            for name in sorted(dirnames) + sorted(filenames):
                p = Path(dirpath) / name
                if str(p) not in known:
                    extras.append(
                        f"{p}: extra entry not in the prepared baseline"
                    )
    return extras


def restore(root: Path, *, verify_only: bool = False) -> dict[str, Any]:
    """Restore the complete selected-state tuple from the builder's snapshot.

    Liveness-gated (finding 4): refuses MID-FLOW while the recorded canary
    pid might still be running; a confirmed-dead pid with a non-done phase
    is reported as ``restart_recovery_detected`` (container death →
    next-start rollback). Refuses relocation to a different root, verifies
    the tar digest against the snapshot manifest, wipes the current state of
    each covered tuple path, extracts with a traversal-safe member filter,
    then verifies EVERY entry (existence, type, bytes, symlink target,
    mode). Raises :class:`CanaryError` on any verification failure.
    """

    root = Path(root).expanduser().resolve(strict=False)
    snap_dir = root / SNAPSHOT_DIR
    data = load_snapshot(snap_dir)
    if Path(data["root"]).resolve(strict=False) != root:
        raise CanaryError(
            "relocation_refused",
            f"snapshot was taken at root {data['root']}; restoring into "
            f"{root} is refused (worktree admin embeds absolute paths)",
        )
    liv = liveness(root)
    restart_recovery_detected = bool(liv["pid"]) and not liv["alive"] and (
        liv["phase"] not in (PHASE_DONE, PHASE_RECOVERED)
    )
    # Fail-closed ONLY mid-flow: a possibly-live writer during the mutation
    # blocks restore. A done/recovered phase means no flow is running — a
    # stale (possibly PID-reused) pid must not block re-baselining.
    if (
        liv["pid"] is not None
        and liv["alive"]
        and liv["phase"] not in (PHASE_DONE, PHASE_RECOVERED)
        and not verify_only
    ):
        raise CanaryError(
            "canary_still_running",
            f"liveness check: canary process pid {liv['pid']} appears ALIVE "
            f"mid-flow (phase={liv['phase']!r}); refusing to restore under "
            "a live writer — let it exit or kill it first",
        )
    tar_path = snap_dir / data["tar"]
    actual_tar_sha = _sha256_file(tar_path)
    if actual_tar_sha != data["tar_sha256"]:
        raise CanaryError(
            "snapshot_digest_mismatch",
            f"snapshot tar digest mismatch (expected {data['tar_sha256']}, "
            f"got {actual_tar_sha}) — refusing to restore untrusted bytes",
        )
    # Supervisor anchor gate (G7.4-PRE-2 item 2): when the supervisor has
    # anchored the snapshot OUTSIDE worker-controlled state, BOTH digests
    # must still match — a coordinated tamper that edits tar bytes AND the
    # manifest's bookkeeping together fails the anchored MANIFEST digest.
    anchor = read_snapshot_anchor(root)
    if anchor is not None:
        anchored_problems: list[str] = []
        if anchor.get("manifest_sha256") != _sha256_file(
            snap_dir / SNAPSHOT_MANIFEST
        ):
            anchored_problems.append("manifest")
        if anchor.get("tar_sha256") != actual_tar_sha:
            anchored_problems.append("tar")
        if anchored_problems:
            raise CanaryError(
                "snapshot_anchor_mismatch",
                "snapshot " + " and ".join(anchored_problems)
                + " no longer match the supervisor's anchor at "
                f"{supervisor_dir(root) / SNAPSHOT_ANCHOR_FILE} — refusing "
                "to trust tampered snapshot state",
            )

    extras = _extra_entries(root, data)
    if verify_only:
        mismatches = verify_against_entries(root, data["entries"])
        mismatches.extend(extras)
        result = {
            "schema": SANDBOX_SCHEMA,
            "mode": "verify_only",
            "root": str(root),
            "ok": not mismatches,
            "mismatches": mismatches[:50],
            "extra_entries": extras[:50],
            "snapshot_anchor": "verified" if anchor is not None else "absent",
            "verified_entries": len(data["entries"]) - len(mismatches),
            "liveness": liv,
            "restart_recovery_detected": restart_recovery_detected,
            "restored_dimensions": list(RESTORED_DIMENSIONS),
            "not_covered_dimensions": list(NOT_COVERED_DIMENSIONS),
        }
        return result
    # Wipe the current state of every tuple path, then extract. Paths ABSENT
    # at snapshot time (coverage=false) are wiped too: byte-exactness vs the
    # prepared baseline means they must not exist after the restore.
    wiped: list[str] = []
    for rel in TUPLE_PATHS:
        target = root / rel
        if target.is_symlink() or (target.exists() and not target.is_dir()):
            target.unlink()
            wiped.append(rel)
        elif target.is_dir():
            shutil.rmtree(target)
            wiped.append(rel)

    def _covered(name: str) -> bool:
        for rel in data["coverage"]:
            if name == rel or name.startswith(rel.rstrip("/") + "/"):
                return True
        return False

    extracted = 0
    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getmembers()
        for m in members:
            parts = Path(m.name).parts
            if m.name.startswith("/") or ".." in parts:
                raise CanaryError(
                    "unsafe_member", f"refusing unsafe tar member {m.name!r}"
                )
            if not _covered(m.name):
                raise CanaryError(
                    "member_outside_coverage",
                    f"tar member {m.name!r} is outside declared coverage — "
                    "snapshot integrity violated",
                )
            if not (m.isfile() or m.isdir() or m.issym()):
                raise CanaryError(
                    "special_node_unsupported",
                    f"tar member {m.name!r} is neither a file, directory nor "
                    "symlink — the snapshot never archives special nodes",
                )
        for m in members:
            # filter=None: symlink targets are preserved VERBATIM, including
            # targets outside the root (a venv interpreter link pointing at
            # the host interpreter is legitimate sandbox state). Traversal
            # safety is enforced by the explicit member audit above.
            try:
                tar.extract(m, path=root, filter=None)
            except TypeError:  # python < 3.11.4 has no filter kwarg
                tar.extract(m, path=root)
            extracted += 1
    mismatches = verify_against_entries(root, data["entries"])
    # Tar-smuggled additions (members present in the tar but NOT in the
    # manifest entries) surface here as unexpected post-restore entries.
    extras = _extra_entries(root, data)
    mismatches.extend(extras)
    for rel, existed in sorted(data["coverage"].items()):
        if not existed and ((root / rel).exists() or (root / rel).is_symlink()):
            mismatches.append(
                f"{rel}: absent from the prepared baseline but present after restore"
            )
    result = {
        "schema": SANDBOX_SCHEMA,
        "mode": "restore",
        "root": str(root),
        "ok": not mismatches,
        "mismatches": mismatches[:50],
        "extra_entries": extras[:50],
        "snapshot_anchor": "verified" if anchor is not None else "absent",
        "extracted_members": extracted,
        "verified_entries": len(data["entries"]) - len(mismatches),
        "liveness": liv,
        "restart_recovery_detected": restart_recovery_detected,
        "wiped_paths": wiped,
        "coverage": data["coverage"],
        "restored_dimensions": list(RESTORED_DIMENSIONS),
        "not_covered_dimensions": list(NOT_COVERED_DIMENSIONS),
    }
    tmp = snap_dir / (RESTORE_REPORT + ".tmp")
    tmp.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(tmp, snap_dir / RESTORE_REPORT)
    if mismatches:
        raise CanaryError(
            "restore_not_byte_exact",
            "restore verification FAILED:\n"
            + "\n".join(f"  - {m}" for m in mismatches[:20]),
        )
    return result

# ── CLI ─────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="arnold-canary-build", description=__doc__.splitlines()[0]
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build_p = sub.add_parser(
        "build", help="build the disposable canary and run the flow"
    )
    build_p.add_argument("--source-repo", required=True, type=Path)
    build_p.add_argument("--root", default="", help="fresh root (default: new mkdtemp)")
    build_p.add_argument("--slug", default="canary")
    build_p.add_argument("--base-ref", default="HEAD")
    build_p.add_argument("--generation-build-strategy", default="")
    build_p.add_argument("--allow-non-tmp-root", action="store_true")
    build_p.add_argument(
        "--supervise",
        action="store_true",
        help="run the flow in a setsid'd worker under THIS process as an "
        "external supervisor; restore the snapshot on unclean death "
        "(SIGKILL/timeout/container-death restart via arnold-canary-restore)",
    )
    build_p.add_argument(
        "--supervisor-timeout",
        type=float,
        default=900.0,
        help="seconds before the supervisor SIGKILLs a wedged flow (default 900)",
    )

    # Hidden: entry point of the supervised worker (never user-facing).
    worker_p = sub.add_parser("_worker")
    worker_p.add_argument("spec")

    restore_p = sub.add_parser(
        "restore",
        help="restore the complete selected-state tuple from the snapshot",
    )
    restore_p.add_argument(
        "--root", required=True, type=Path, help="sandbox root to restore into"
    )
    restore_p.add_argument(
        "--verify-only",
        action="store_true",
        help="verify current state against the snapshot WITHOUT modifying it",
    )

    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            report = build(
                source_repo=args.source_repo,
                root=Path(args.root) if args.root else None,
                slug=args.slug,
                base_ref=args.base_ref,
                generation_build_strategy=args.generation_build_strategy or None,
                allow_non_tmp=args.allow_non_tmp_root,
                supervise=args.supervise,
                supervisor_timeout=args.supervisor_timeout,
            )
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0
        if args.command == "_worker":
            return _worker_main(args.spec)
        if args.command == "restore":
            result = restore(args.root, verify_only=args.verify_only)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
    except CanaryError as exc:
        prog = "arnold-canary-restore" if args.command == "restore" else "arnold-canary-build"
        print(f"{prog}: error [{exc.code}]: {exc.message}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
