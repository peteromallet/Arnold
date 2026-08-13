#!/usr/bin/env python3
"""Reference census for runtime GC: fail-closed before every deletion (T-0012).

``arnold-gc-sweep`` consults this module before ANY worktree, branch, or
dependency (venv) deletion.  The census normalizes EXACT runtime-root paths
from every runtime truth store and classifies the deletion target:

  CLEAR       no live, dangling, or unreadable reference — the wrapper's
              remaining gates (closed-only, origin, schedule slug/sha,
              open-PR, restore-proven) decide
  REFERENCED  at least one store references the exact root — deletion is
              HARD-SKIPPED (a live reference is load-bearing)
  DANGLING    a store references a runtime root that no longer exists — the
              census cannot attest completeness, so the sweep reports
              NEEDS-RECONCILE and never deletes
  UNKNOWN     a reference store is unreadable/corrupt — the census cannot
              attest completeness, so deletion is BLOCKED (delete-on-unknown
              never happens)

References are exact normalized absolute paths (expanduser + abspath,
trailing slash stripped, NO symlink resolution) extracted from curated
path-bearing keys inside each store's JSON / JSON-lines documents.  slug/SHA
substring matching is never a predicate here — the wrapper's legacy schedule-store
grep gate still covers slug/sha references; this census covers exact runtime-root
paths on top.

Stores (each injectable via CLI flag / env var; a missing store dir is NOT a
reference, but an EXISTING store that cannot be read — permission denied, a
file squatting on the store path, a DANGLING SYMLINK at the store path, or
any os error — is UNKNOWN, fail-closed):

  * manifest     per-slug runtime manifest files in the sweep's manifest
                 store.  The manifest currently being swept is excluded (its
                 reference dies with the sweep); the compatibility-only
                 active-pointer family (``runtime-manifest.json*``) is
                 non-authoritative telemetry that no resolver admits, so it
                 is never scanned.
  * chain        active/paused/blocked chain state JSON carrying
                 ``metadata.execution_environment.engine_root``.  Chains
                 store per-workspace state (spec layout
                 ``<workspace>/.megaplan/plans/.chains/chain-*.json``) AND
                 per-project state under each project checkout
                 (``<workspace>/<project>/.megaplan/plans/.chains`` AND
                 ``<workspace>/<project>/<repo>/.megaplan/plans/.chains``
                 — the box keeps one workspace dir per chain with the repo
                 checkout under it, so live state sits at
                 ``/workspace/<epic>/Arnold/.megaplan/plans/.chains`` and
                 BOTH glob depths are scanned), so the flat
                 workspace-relative store plus every matching per-project
                 dir at either depth are scanned IN ADDITION to the fixed
                 store.
  * marker       cloud-session and chain-health marker JSON — fixed store
                 plus the workspace-relative
                 ``<workspace>/.megaplan/cloud-sessions`` and the matching
                 per-project dirs at both glob depths (same two-level scan
                 as chains).
  * schedule     resident scheduled-jobs, resident schedule heads, and ops
                 schedule stores.
  * repair-queue requests / decisions / attempts / active-claims /
                 occurrence-claims.  Active and occurrence claim locks live
                 in nested ``<token>.lock/`` dirs with runtime-root
                 references in their ``owner.json`` — the scan recurses one
                 level into every ``*.lock/`` dir (a corrupt/unreadable
                 nested file is UNKNOWN, fail-closed).
  * lease        the custody lease store (append-only lease events; real
                 files are <lease_id>.history.jsonl + <lease_id>.state.json).
  * plan-lease   per-plan custody lease stores, one store per plan at
                 ``<chain-workspace>/.megaplan/plans/<plan>/custody/leases``
                 (the paths worker_dispatch_wbc.py:613 and phase_wbc.py:937
                 open).  The ``<plan>/custody/leases`` dirs are globbed from
                 --plan-lease-root AND — when --workspace is given — at the
                 same three layouts as chain state (workspace root,
                 per-project, nested checkout).  THE STORE ITSELF IS THE
                 REFERENCE: a store holding at least one lease file
                 (``*.json`` / ``*.jsonl`` / ``<lease_id>.history.jsonl``)
                 references its own plan dir even though the real lease
                 records carry no path field (G6).  An empty store is not a
                 reference; corrupt/unreadable lease files are UNKNOWN
                 (fail-closed).
  * managed-run  managed-subagent run manifests at
                 ``<project>/.megaplan/plans/resident-subagents/<run_id>/
                 manifest.json`` (DEFAULT_MANAGED_RUN_ROOT in
                 resident/subagent.py) plus the fixer-session store
                 (``<project>/.megaplan/fixer-sessions``).  Run manifests
                 are ONE level deep, so this store recurses into every
                 subdir.  Fixed store plus the same three workspace layouts.
  * status       the canonical cloud status snapshot dir
                 (``/workspace/.megaplan/status`` — cloud-status.json,
                 cloud-status.previous.json, progress-history.jsonl;
                 status_snapshot.py).
  * ops          ops schedule stores ``/workspace/.megaplan/ops/schedules``
                 and ``/workspace/.megaplan/schedule-inputs`` (per-input
                 dirs, scanned two levels deep; probe_records.py).
  * generation   the content-addressed dependency-generation store root
                 (``/workspace/runtime-venvs`` — T-0301).  A missing store
                 is NOT a reference; a PRESENT hex-named generation dir that
                 cannot be attested (corrupt/missing ``.generation.json``,
                 proof id != dir name, missing interpreter) is UNKNOWN
                 (fail-closed).  References to a generation come from the
                 other stores' path-bearing keys (``venv_path``), so a
                 generation with zero references is deletable.

CLI (used by arnold-gc-sweep):

  python3 -m arnold_pipelines.megaplan.cloud.runtime_references census \\
      --root <root> [--workspace <dir>] [--manifest-store <dir>] \\
      [--current-manifest <path>] [--chain-store <d1:d2>] \\
      [--marker-store <d1:d2>] [--schedule-store <d1:d2>] \\
      [--repair-queue <dir>] [--lease-store <dir>] \\
      [--plan-lease-root <dir>] [--managed-run-store <d1:d2>] \\
      [--status-dir <dir>] [--ops-store <d1:d2>] \\
      [--generation-root <dir>]

Prints ``STATUS <verdict>`` plus ``REASON <...>`` lines and always exits 0;
the WRAPPER decides how to act on the verdict (REFERENCED -> hard skip,
DANGLING -> needs-reconcile, UNKNOWN -> block).  A failing census is
fail-closed in the wrapper.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import stat
import sys
from pathlib import Path

# Path-bearing keys whose value is a candidate runtime-root reference.  The
# list is curated to the field names the runtime truth stores actually use;
# values are only compared by EXACT normalized path equality with the target.
# Leaf entries (e.g. "runtime_root") match that key at any nesting depth;
# dotted entries (e.g. "context_directory.resident_runtime_source") match
# only that EXACT path, for nested structures like the managed-subagent run
# manifest's context_directory block (resident/subagent.py
# _delegated_context_directory).
_PATH_KEYS = frozenset(
    {
        "engine_root",
        "runtime_root",
        "project_root",
        "project_dir",
        "target_root",
        "work_dir",
        "venv_path",
        "source_root",
        "writable_roots",
        "cwd",
        "launch_dir",
        "directory",
        "context_directory.project_worktree",
        "context_directory.resident_runtime_source",
    }
)

# Keys whose value is a RUNTIME ANCHOR: when one of these points at a path
# that no longer exists the store is stale/incoherent (dangling).  venv_path
# is deliberately excluded — venvs are lazily created and a missing venv is
# normal, not incoherence.
_DANGLING_KEYS = frozenset({"engine_root", "runtime_root", "source_root", "launch_dir"})

# The active-pointer family is compatibility-only telemetry (bootstrap_manifest
# refuses it), so it holds no load-bearing reference and is never scanned.
_POINTER_NAME_PREFIX = "runtime-manifest.json"

_QUEUE_SUBDIRS = (
    "requests",
    "decisions",
    "attempts",
    "active-claims",
    "occurrence-claims",
)

DEFAULT_CHAIN_STORE = os.environ.get(
    "ARNOLD_REFERENCE_CHAIN_STORE", "/workspace/.megaplan/plans/.chains"
)
DEFAULT_MARKER_STORE = os.environ.get(
    "ARNOLD_REFERENCE_MARKER_STORE",
    "/workspace/.megaplan/cloud-sessions:/workspace/watchdog-reports",
)
DEFAULT_SCHEDULE_STORE = os.environ.get(
    "ARNOLD_REFERENCE_SCHEDULE_STORES",
    "/workspace/arnold/.megaplan/resident/scheduled_jobs:"
    "/workspace/arnold/.megaplan/resident/schedules/heads:"
    "/workspace/.megaplan/ops/schedules",
)
DEFAULT_REPAIR_QUEUE = os.environ.get(
    "ARNOLD_REFERENCE_REPAIR_QUEUE", "/workspace/.megaplan/repair-queue"
)
DEFAULT_LEASE_STORE = os.environ.get(
    "ARNOLD_REFERENCE_LEASE_STORE", os.path.expanduser("~/.megaplan/custody/leases")
)
# Root globbed for per-plan custody lease stores: <root>/<plan>/custody/leases
# (the paths worker_dispatch_wbc.py:613 and phase_wbc.py:937 open).
DEFAULT_PLAN_LEASE_ROOT = os.environ.get(
    "ARNOLD_REFERENCE_PLAN_LEASE_ROOT", "/workspace/.megaplan/plans"
)
# Managed-subagent run store (DEFAULT_MANAGED_RUN_ROOT in
# resident/subagent.py is project-relative: <project>/.megaplan/plans/
# resident-subagents) plus the fixer-session store
# (<project>/.megaplan/fixer-sessions).  On the box the resident's project
# checkout is /workspace/arnold; per-chain workspaces carry their own copies
# at both glob depths (added in run_census from --workspace).
DEFAULT_MANAGED_RUN_STORE = os.environ.get(
    "ARNOLD_REFERENCE_MANAGED_RUN_STORE",
    "/workspace/arnold/.megaplan/plans/resident-subagents:"
    "/workspace/arnold/.megaplan/fixer-sessions",
)
# Canonical status snapshot dir (status_snapshot.py): cloud-status.json,
# cloud-status.previous.json, progress-history.jsonl.
DEFAULT_STATUS_DIR = os.environ.get(
    "ARNOLD_REFERENCE_STATUS_DIR", "/workspace/.megaplan/status"
)
# Ops schedule stores (probe_records.py / recoverability-20260807.md: the
# proactive superfixer touches both /workspace/.megaplan/ops/schedules and
# /workspace/.megaplan/schedule-inputs — the latter holds one nested dir per
# input, e.g. <input-id>/SKILL.md payloads).
DEFAULT_OPS_STORE = os.environ.get(
    "ARNOLD_REFERENCE_OPS_STORE",
    "/workspace/.megaplan/ops/schedules:/workspace/.megaplan/schedule-inputs",
)
# Content-addressed dependency-generation store root (T-0301): one immutable
# venv per frozen-spec digest at <root>/<sha256> with a .generation.json
# proof.  Matches the arnold-runtime-create default
# ($ARNOLD_RUNTIME_VENVS_DIR or <base>/runtime-venvs) and the legacy
# /workspace/runtime-venvs/arnold-<sha>-live pattern.
DEFAULT_GENERATION_ROOT = os.environ.get(
    "ARNOLD_REFERENCE_RUNTIME_VENVS_DIR", "/workspace/runtime-venvs"
)

# Content-addressed generation dir names are 64-char hex spec digests; the
# legacy /workspace/runtime-venvs/arnold-<sha>-live venvs predate T-0301 and
# carry no generation proof, so only hex-named dirs are generation-store
# entries (a legacy venv is still a reference via venv_path path-keys).
_GENERATION_NAME = re.compile(r"^[0-9a-f]{64}$")


def normalize_root(value: object) -> str:
    """Normalize one candidate path for exact comparison.

    expanduser + abspath, trailing slash stripped, NO symlink resolution
    (resolving symlinks would alias distinct roots like /tmp vs /private/tmp).
    Empty or relative values are not runtime-root references.
    """
    text = str(value).strip()
    if not text or not (text.startswith("/") or text.startswith("~")):
        return ""
    expanded = os.path.abspath(os.path.expanduser(text))
    stripped = expanded.rstrip("/")
    return stripped or "/"


def _iter_path_values(data: object) -> list[tuple[str, str, str]]:
    """Yield (key, dotted, value) for every curated path-bearing key in *data*.

    Recurses through dicts and lists; a curated key holding a list of strings
    (e.g. ``writable_roots``) yields each string with that key.
    """

    def walk(node: object, ancestors: tuple[str, ...]) -> list[tuple[str, str, str]]:
        found: list[tuple[str, str, str]] = []
        if isinstance(node, dict):
            for key, value in node.items():
                key_text = str(key)
                dotted = ".".join((*ancestors, key_text))
                if key in _PATH_KEYS or dotted in _PATH_KEYS:
                    if isinstance(value, str):
                        found.append((key_text, dotted, value))
                    elif isinstance(value, list):
                        for index, item in enumerate(value):
                            if isinstance(item, str):
                                found.append((key_text, f"{dotted}[{index}]", item))
                found.extend(walk(value, (*ancestors, key_text)))
        elif isinstance(node, list):
            for index, item in enumerate(node):
                found.extend(walk(item, (*ancestors, str(index))))
        return found

    return walk(data, ())


def _excluded_manifest(path: Path, current_manifest: str) -> bool:
    """Exclude the manifest being swept and the compatibility-only pointer
    family from the manifest-store scan."""
    if path.name.startswith(_POINTER_NAME_PREFIX):
        return True
    if current_manifest:
        try:
            if path.resolve() == Path(current_manifest).resolve():
                return True
        except OSError:
            return False
    return False


def _iter_store_files(store_dir: Path, *, nested: int = 0) -> list[Path]:
    """Yield JSON / JSON-lines files in *store_dir*, recursing ONE level
    into every ``*.lock/`` directory (repair claims) or — when *nested* is
    positive — *nested* subdirectory levels into EVERY subdir
    (managed-subagent run manifests live one level deep at
    ``<run_root>/<run_id>/manifest.json``; ops schedule-inputs carry per-input
    dirs two levels deep at ``<store>/<input-id>/<payload>.json``).

    Real repair claims store their runtime-root references in nested owner
    metadata: ``repair_requests.active_repair_claim_lock_dir`` /
    ``singleton_occurrence_claim_lock_dir`` build
    ``<queue>/active-claims/<token>.lock/`` and
    ``repair_lock.owner_metadata_path`` writes the holder's runtime root
    (``cwd`` and any ``extra`` path keys) into ``owner.json`` inside that
    lock dir.  A top-level-only scan would silently miss every live claim;
    unreadable/corrupt nested files fall through to the caller's UNKNOWN
    handling (fail-closed)."""
    files = [p for pattern in ("*.json", "*.jsonl") for p in store_dir.glob(pattern)]
    if nested:
        level_dirs = [store_dir]
        for _ in range(nested):
            level_dirs = [
                sub for d in level_dirs for sub in d.iterdir() if sub.is_dir()
            ]
            for d in level_dirs:
                files.extend(
                    p for pattern in ("*.json", "*.jsonl") for p in d.glob(pattern)
                )
    else:
        for lock_dir in store_dir.glob("*.lock"):
            if not lock_dir.is_dir():
                continue
            files.extend(
                p for pattern in ("*.json", "*.jsonl") for p in lock_dir.glob(pattern)
            )
    return sorted(files)


def _scan_store(
    name: str,
    dirs: tuple[str, ...],
    root: str,
    *,
    manifest_mode: bool = False,
    current_manifest: str = "",
    nested: int = 0,
    plan_lease_mode: bool = False,
) -> tuple[str, list[str]]:
    """Scan one reference store (one or more dirs) for *root*.

    Returns (verdict, reasons): CLEAR / REFERENCED / DANGLING / UNKNOWN.
    A live exact reference wins over a dangling one; any unreadable or
    corrupt file — or a store dir that exists but cannot be read (missing
    dirs are simply not references; a DANGLING SYMLINK on the store path is
    present-but-broken and IS UNKNOWN, fail-closed) — makes the whole store
    UNKNOWN (fail-closed).

    In *plan_lease_mode* the per-plan custody lease STORE ITSELF is the
    reference: a store dir at ``<plan>/custody/leases`` holding at least one
    lease file references its own plan dir (``<plan>``) even though the real
    lease records carry no path field (worker_dispatch_wbc.py:613 /
    phase_wbc.py:937 open the store at ``<plan_dir>/custody/leases``).  An
    empty store is not a reference; corrupt/unreadable lease files still make
    the store UNKNOWN (fail-closed, checked before the presence reference).
    Path-value matching runs as well, so lease records that DO carry a path
    key are also exact references.
    """
    refs: list[tuple[str, str, str, str]] = []  # (key, dotted, norm, source)
    for dirname in dirs:
        store_dir = Path(dirname)
        try:
            st = store_dir.stat()
        except FileNotFoundError:
            # Distinguish a GENUINELY absent store dir (not a reference)
            # from a DANGLING SYMLINK squatting on the store path (G6
            # finding 5): stat() FOLLOWS links, so a broken link raises
            # ENOENT here even though the link ENTRY exists — a
            # present-but-broken store path the census cannot attest.  A
            # dangling symlink must be UNKNOWN (fail-closed), never
            # collapsed to absence; os.path.islink() does NOT follow, so
            # it sees the link entry and disambiguates.
            if os.path.islink(str(store_dir)):
                return (
                    "UNKNOWN",
                    [f"{name} store path {store_dir} is a dangling symlink"],
                )
            # A genuinely missing store dir is not a reference.
            continue
        except OSError as exc:
            # Present-but-unreadable (e.g. a parent path without permission):
            # the census cannot attest completeness — fail closed.
            return "UNKNOWN", [f"unreadable {name} store dir {store_dir}: {exc}"]
        if not stat.S_ISDIR(st.st_mode):
            # Present but not a directory (e.g. a file squatting on the store
            # path): the store cannot be read as a store — fail closed.
            return (
                "UNKNOWN",
                [f"{name} store path {store_dir} exists but is not a directory"],
            )
        try:
            store_files = _iter_store_files(store_dir, nested=nested)
        except OSError as exc:
            # Exists as a dir but its entries cannot be enumerated (no read
            # permission): fail closed rather than silently skipping.
            return "UNKNOWN", [f"unreadable {name} store dir {store_dir}: {exc}"]
        store_plan = ""
        if plan_lease_mode:
            # The per-plan custody lease store is keyed by its OWN location:
            # <plan>/custody/leases references the plan dir two levels up
            # (worker_dispatch_wbc.py:613 / phase_wbc.py:937 open the store
            # at <plan_dir>/custody/leases).  Whether it actually references
            # *root* is decided after the files parse (a corrupt/unreadable
            # store is UNKNOWN, fail-closed, never REFERENCED).
            store_plan = normalize_root(os.path.abspath(str(store_dir.parent.parent)))
        for path in store_files:
            if manifest_mode and _excluded_manifest(path, current_manifest):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                return "UNKNOWN", [f"unreadable {name} store file {path}: {exc}"]
            try:
                if path.suffix == ".jsonl":
                    # JSON-lines document: one JSON object per line.  This is
                    # the REAL lease format (<lease_id>.history.jsonl — the
                    # append-only custody event stream); scanning only *.json
                    # silently missed every live lease history.  A non-empty
                    # line that is not a complete JSON object is corrupt
                    # (fail-closed: delete-on-unknown never happens).
                    records = [
                        json.loads(line)
                        for line in text.splitlines()
                        if line.strip()
                    ]
                else:
                    records = [json.loads(text)]
            except (json.JSONDecodeError, TypeError) as exc:
                return "UNKNOWN", [f"corrupt {name} store file {path}: {exc}"]
            for data in records:
                for key, dotted, value in _iter_path_values(data):
                    norm = normalize_root(value)
                    if norm:
                        refs.append((key, dotted, norm, str(path)))
        if store_plan and store_plan == root and store_files:
            # The per-plan custody lease STORE is the reference: any plan
            # dir whose custody/leases store holds lease files is REFERENCED
            # even when the lease records carry no path field (G6 — the
            # census previously matched only JSON path values, so chain
            # reset could rmtree(plan_dir) with a live lease).  The files
            # parsed cleanly above; an empty store falls through to CLEAR.
            return (
                "REFERENCED",
                [
                    f"plan-lease store {store_dir} holds lease files for plan "
                    f"dir {root} (per-plan custody leases carry no path field "
                    f"— store presence is the reference)"
                ],
            )
    for key, dotted, norm, source in refs:
        if norm == root:
            return (
                "REFERENCED",
                [
                    f"{name} store references {root} (exact runtime root) via "
                    f"{dotted} in {source}"
                ],
            )
    for key, dotted, norm, source in refs:
        if key in _DANGLING_KEYS and not os.path.exists(norm):
            return (
                "DANGLING",
                [
                    f"{name} store references missing runtime root {norm} via "
                    f"{dotted} in {source}"
                ],
            )
    return "CLEAR", []


def _scan_generation_store(
    root: str,
    dirs: tuple[str, ...],
) -> tuple[str, list[str]]:
    """Scan the content-addressed dependency-generation store (T-0301).

    The generation store holds ONE dir per frozen-spec digest
    (``<root>/<sha256>``) with a ``.generation.json`` proof.  A missing
    generation root is NOT a reference (the store is lazily created); a
    PRESENT hex-named generation dir that cannot be attested — unreadable,
    missing/corrupt ``.generation.json``, a proof whose ``id`` does not
    match the dir name, or a missing interpreter — is UNKNOWN (fail-closed:
    the census cannot attest the generation's integrity, so no deletion
    happens anywhere in the sweep).  Non-hex subdirs (the legacy
    ``arnold-<sha>-live`` venvs) are ignored: they predate T-0301 and carry
    no generation proof.

    References to a generation come from the manifest store (``venv_path``
    key) and every other path-bearing store — the store itself never makes
    a generation REFERENCED by mere existence (an orphan generation with
    zero references is deletable).
    """
    for dirname in dirs:
        store_dir = Path(dirname)
        try:
            st = store_dir.stat()
        except FileNotFoundError:
            if os.path.islink(str(store_dir)):
                return (
                    "UNKNOWN",
                    [f"generation store path {store_dir} is a dangling symlink"],
                )
            # A genuinely missing generation store is not a reference.
            continue
        except OSError as exc:
            return "UNKNOWN", [f"unreadable generation store dir {store_dir}: {exc}"]
        if not stat.S_ISDIR(st.st_mode):
            return (
                "UNKNOWN",
                [f"generation store path {store_dir} exists but is not a directory"],
            )
        try:
            entries = sorted(store_dir.iterdir())
        except OSError as exc:
            return "UNKNOWN", [f"unreadable generation store dir {store_dir}: {exc}"]
        for entry in entries:
            if not _GENERATION_NAME.match(entry.name):
                continue  # legacy / unrelated content, not a generation entry
            if not entry.is_dir():
                return (
                    "UNKNOWN",
                    [
                        f"generation store path {entry} exists but is not a directory"
                    ],
                )
            proof_file = entry / ".generation.json"
            if not proof_file.is_file():
                return (
                    "UNKNOWN",
                    [
                        f"generation {entry} is present but carries no "
                        ".generation.json proof"
                    ],
                )
            try:
                raw = proof_file.read_text(encoding="utf-8")
                proof = json.loads(raw)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                return "UNKNOWN", [f"generation proof unreadable/corrupt at {proof_file}: {exc}"]
            if (
                not isinstance(proof, dict)
                or not isinstance(proof.get("id"), str)
                or proof.get("id") != entry.name
            ):
                return (
                    "UNKNOWN",
                    [
                        f"generation proof at {proof_file} does not match its "
                        "content-addressed dir name"
                    ],
                )
            if not (entry / "bin" / "python").is_file():
                return (
                    "UNKNOWN",
                    [f"generation {entry} is missing its interpreter"],
                )
    return "CLEAR", []


def run_census(
    *,
    root: str,
    workspace: str = "",
    manifest_store: str,
    current_manifest: str,
    chain_store: str,
    marker_store: str,
    schedule_store: str,
    repair_queue: str,
    lease_store: str,
    plan_lease_root: str = DEFAULT_PLAN_LEASE_ROOT,
    managed_run_store: str = DEFAULT_MANAGED_RUN_STORE,
    status_dir: str = DEFAULT_STATUS_DIR,
    ops_store: str = DEFAULT_OPS_STORE,
    generation_root: str = DEFAULT_GENERATION_ROOT,
) -> tuple[str, list[str]]:
    """Classify *root* against every configured reference store.

    *workspace* is the workspace root: chains store per-workspace state at
    ``<workspace>/.megaplan/plans/.chains/chain-*.json`` (spec layout) AND
    per-project state at ``<workspace>/<project>/.megaplan/plans/.chains``
    and ``<workspace>/<project>/<repo>/.megaplan/plans/.chains`` (the box
    keeps one workspace dir per chain with the repo checkout under it, so
    live chain state sits at ``/workspace/<epic>/Arnold/.megaplan/plans/
    .chains`` — the checkout is a SUBDIR of the chain's workspace dir and
    BOTH glob depths are scanned), so when given the flat workspace chain
    store, every matching per-project chain store at either depth, and the
    cloud-session marker dirs (``<workspace>/.megaplan/cloud-sessions``
    plus the same two-level per-project globs) are scanned IN ADDITION to
    the fixed chain/marker stores (a missing dir is not a reference).

    Store order is fixed; the first non-CLEAR verdict wins.  Any
    unreadable/corrupt store yields UNKNOWN for the whole census.  The
    configured plan-lease root is validated BEFORE globbing beneath it: a
    dangling symlink, stat-inaccessible, or non-directory root is UNKNOWN
    (fail-closed, never an empty-glob CLEAR); a genuinely absent root is
    not a reference.
    """
    chain_dirs = list(chain_store.split(":"))
    marker_dirs = list(marker_store.split(":"))
    if workspace:
        # Flat workspace-relative chain state (spec layout) …
        chain_dirs.append(os.path.join(workspace, ".megaplan", "plans", ".chains"))
        # … AND per-project chain state: on the box each chain runs in its
        # own workspace dir with the repo checkout under it, so chain state
        # lives at <workspace>/<project>/.megaplan/plans/.chains AND under
        # the nested checkout <workspace>/<project>/<repo>/.megaplan/
        # plans/.chains (live state is /workspace/<epic>/Arnold/.megaplan/
        # plans/.chains — the checkout is a SUBDIR of the chain's workspace
        # dir).  Glob BOTH depths, sorted; a missing dir is not a reference
        # (consistent with the flat paths above).
        for depth in ("*", os.path.join("*", "*")):
            chain_dirs.extend(
                sorted(
                    glob.glob(os.path.join(workspace, depth, ".megaplan", "plans", ".chains"))
                )
            )
        marker_dirs.append(os.path.join(workspace, ".megaplan", "cloud-sessions"))
        # Cloud-session markers are flat at the workspace root, but the
        # per-project and nested-checkout layouts carry their own
        # .megaplan/cloud-sessions dirs too — scan both depths, sorted.
        for depth in ("*", os.path.join("*", "*")):
            marker_dirs.extend(
                sorted(
                    glob.glob(os.path.join(workspace, depth, ".megaplan", "cloud-sessions"))
                )
            )
    queue_dirs = tuple(os.path.join(repair_queue, sub) for sub in _QUEUE_SUBDIRS)
    # Per-plan custody lease stores: worker_dispatch_wbc.py:613 and
    # phase_wbc.py:937 open <plan_dir>/custody/leases where plan_dir is
    # <chain-workspace>/.megaplan/plans/<plan> — glob the <plan> level under
    # the fixed root AND, when workspace is given, the same three layouts as
    # chain state (workspace root, per-project, nested checkout).
    # Validate the CONFIGURED plan-lease root before globbing beneath it
    # (G6 finding 5): globbing a dangling root symlink silently yields an
    # empty list, collapsing a present-but-broken root to CLEAR absence.
    # stat() follows links and raises ENOENT on a broken one;
    # os.path.islink() (no follow) disambiguates from a genuinely absent
    # root (which, like a missing store dir, is not a reference).  A
    # dangling/stat-inaccessible/non-directory root is UNKNOWN (fail-closed),
    # reported when the plan-lease store slot is reached so the fixed
    # store-order ("first non-CLEAR verdict wins") is preserved.
    plan_lease_dirs: list[str] = []
    plan_lease_problem = ""
    plan_lease_root_path = Path(plan_lease_root)
    try:
        root_stat = plan_lease_root_path.stat()
    except FileNotFoundError:
        if os.path.islink(str(plan_lease_root_path)):
            plan_lease_problem = (
                f"plan-lease root {plan_lease_root_path} is a dangling symlink"
            )
        # A genuinely absent root is not a reference (empty glob).
    except OSError as exc:
        plan_lease_problem = f"unreadable plan-lease root {plan_lease_root_path}: {exc}"
    else:
        if not stat.S_ISDIR(root_stat.st_mode):
            plan_lease_problem = (
                f"plan-lease root {plan_lease_root_path} exists but is not a directory"
            )
    if not plan_lease_problem:
        plan_lease_dirs = sorted(
            glob.glob(os.path.join(plan_lease_root, "*", "custody", "leases"))
        )
    # Managed-subagent run root (resident/subagent.py DEFAULT_MANAGED_RUN_ROOT
    # is project-relative: <project>/.megaplan/plans/resident-subagents with
    # per-run manifest.json one level deep) and the fixer-session store
    # (<project>/.megaplan/fixer-sessions) — same three workspace layouts.
    managed_dirs = list(managed_run_store.split(":"))
    if workspace:
        for depth in ("", os.path.join("*"), os.path.join("*", "*")):
            plan_lease_dirs.extend(
                sorted(
                    glob.glob(
                        os.path.join(
                            workspace,
                            depth,
                            ".megaplan",
                            "plans",
                            "*",
                            "custody",
                            "leases",
                        )
                    )
                )
            )
        for rel in (
            os.path.join(".megaplan", "plans", "resident-subagents"),
            os.path.join(".megaplan", "fixer-sessions"),
        ):
            managed_dirs.append(os.path.join(workspace, rel))
            for depth in ("*", os.path.join("*", "*")):
                managed_dirs.extend(
                    sorted(glob.glob(os.path.join(workspace, depth, rel)))
                )
    # Tuples: (name, dirs, manifest_mode, nested, plan_lease_mode).  The
    # plan-lease store is the ONLY store whose presence is itself the
    # reference (per-plan custody leases carry no path field — G6).
    stores = (
        ("manifest", (manifest_store,), True, False, False),
        ("chain", tuple(chain_dirs), False, False, False),
        ("marker", tuple(marker_dirs), False, False, False),
        ("schedule", tuple(schedule_store.split(":")), False, False, False),
        ("repair-queue", queue_dirs, False, False, False),
        ("lease", (lease_store,), False, False, False),
        ("plan-lease", tuple(plan_lease_dirs), False, False, True),
        ("managed-run", tuple(managed_dirs), False, True, False),
        ("status", (status_dir,), False, False, False),
        # schedule-inputs holds one nested dir per input (e.g.
        # <input-id>/SKILL.md payloads), so the ops store recurses TWO
        # levels to reach JSON payloads inside each input dir.
        ("ops", tuple(ops_store.split(":")), False, 2, False),
    )
    for name, dirs, manifest_mode, nested, plan_lease_mode in stores:
        if name == "plan-lease" and plan_lease_problem:
            return "UNKNOWN", [plan_lease_problem]
        verdict, reasons = _scan_store(
            name,
            dirs,
            root,
            manifest_mode=manifest_mode,
            current_manifest=current_manifest,
            nested=nested,
            plan_lease_mode=plan_lease_mode,
        )
        if verdict != "CLEAR":
            return verdict, reasons
    # T-0301: the content-addressed dependency-generation store.  Corrupt
    # or unverifiable generation dirs make the whole census UNKNOWN
    # (fail-closed — delete-on-unknown never happens); a missing store is
    # not a reference; references to a generation are found via the
    # path-bearing keys (venv_path) in the stores above.
    verdict, reasons = _scan_generation_store(root, (generation_root,))
    if verdict != "CLEAR":
        return verdict, reasons
    return "CLEAR", []


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arnold-pipelines.megaplan.cloud.runtime_references",
        description="Reference census for runtime GC (fail-closed).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    census = sub.add_parser("census", help="classify a runtime root against every reference store")
    census.add_argument("--root", required=True, help="exact runtime root path under consideration")
    census.add_argument(
        "--workspace",
        default=os.environ.get("ARNOLD_BASE_DIR", ""),
        help="workspace root; workspace-relative chain state "
        "(<workspace>/.megaplan/plans/.chains), per-project chain state at "
        "BOTH depths (<workspace>/<project>/.megaplan/plans/.chains and "
        "<workspace>/<project>/<repo>/.megaplan/plans/.chains), and "
        "cloud-session markers (<workspace>/.megaplan/cloud-sessions plus "
        "the same two-level per-project globs) are scanned in addition to "
        "the fixed chain/marker stores",
    )
    census.add_argument(
        "--manifest-store",
        default=os.environ.get("ARNOLD_RUNTIME_MANIFEST_DIR", "/workspace/.megaplan"),
        help="per-slug runtime manifest store dir",
    )
    census.add_argument("--current-manifest", default="", help="manifest being swept (excluded)")
    census.add_argument("--chain-store", default=DEFAULT_CHAIN_STORE)
    census.add_argument("--marker-store", default=DEFAULT_MARKER_STORE)
    census.add_argument("--schedule-store", default=DEFAULT_SCHEDULE_STORE)
    census.add_argument("--repair-queue", default=DEFAULT_REPAIR_QUEUE)
    census.add_argument("--lease-store", default=DEFAULT_LEASE_STORE)
    census.add_argument("--plan-lease-root", default=DEFAULT_PLAN_LEASE_ROOT)
    census.add_argument("--managed-run-store", default=DEFAULT_MANAGED_RUN_STORE)
    census.add_argument("--status-dir", default=DEFAULT_STATUS_DIR)
    census.add_argument("--ops-store", default=DEFAULT_OPS_STORE)
    census.add_argument(
        "--generation-root",
        default=DEFAULT_GENERATION_ROOT,
        help="content-addressed dependency-generation store root (T-0301); "
        "corrupt/unverifiable generations are UNKNOWN (fail-closed)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command != "census":
        print(f"runtime_references: unknown command {args.command!r}", file=sys.stderr)
        return 2
    root = normalize_root(args.root)
    if not root:
        print("STATUS UNKNOWN")
        print("REASON empty or non-absolute runtime root under consideration")
        return 0
    verdict, reasons = run_census(
        root=root,
        workspace=args.workspace,
        manifest_store=args.manifest_store,
        current_manifest=args.current_manifest,
        chain_store=args.chain_store,
        marker_store=args.marker_store,
        schedule_store=args.schedule_store,
        repair_queue=args.repair_queue,
        lease_store=args.lease_store,
        plan_lease_root=args.plan_lease_root,
        managed_run_store=args.managed_run_store,
        status_dir=args.status_dir,
        ops_store=args.ops_store,
        generation_root=args.generation_root,
    )
    print(f"STATUS {verdict}")
    for reason in reasons:
        print(f"REASON {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
