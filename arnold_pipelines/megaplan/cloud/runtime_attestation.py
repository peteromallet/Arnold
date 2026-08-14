"""Content-addressed runtime launch seeds and process attestations."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import site
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import unquote, urlparse

from arnold_pipelines.megaplan.cloud.runtime_provenance import runtime_provenance
from arnold_pipelines.megaplan.types import CliError


RUNTIME_LAUNCH_SEED_SCHEMA = "arnold.megaplan.runtime_launch_seed.v1"
RUNTIME_PROCESS_ATTESTATION_SCHEMA = "arnold.megaplan.runtime_process_attestation.v1"
RUNTIME_ATTESTATION_ERROR = "runtime_launch_attestation_mismatch"
# Canonical box-side paths for the per-epic launch-seed build (G14): the
# supervisor prepare receipt, the box hot-env file, and the launch-seed store
# (mirrors ARNOLD_RUNTIME_MANIFEST_DIR, which defaults to /workspace/.megaplan).
SUPERVISOR_RECEIPT_DEFAULT_PATH = Path("/workspace/.megaplan/supervisor-python/last-prepare.json")
CLOUD_HOT_ENV_DEFAULT_PATH = Path("/workspace/.cloud-hot-env")
CLOUD_SESSION_MARKER_DIR_DEFAULT = Path("/workspace/.megaplan/cloud-sessions")
RUNTIME_SELECTOR_NAMES = (
    "MEGAPLAN_RUNTIME_SRC",
    "MEGAPLAN_LAUNCH_RUNTIME_SRC",
    "MEGAPLAN_SUPERVISOR_SOURCE",
    "CLOUD_WATCHDOG_ARNOLD_SRC",
    "MEGAPLAN_META_ARNOLD_SRC",
    "MEGAPLAN_AUDIT_ARNOLD_SRC",
    "MEGAPLAN_SUPERVISOR_PYTHON",
    # Retired selectors (T-0023/G5): kept on the deny-list so any
    # re-introduced read is flagged; production derives these from the
    # per-session manifest (ARNOLD_RUNTIME_MANIFEST -> epic.runtime_root).
    "KIMI_GOAL_ARNOLD_SRC",
    "MEGAPLAN_DISCORD_DM_ARNOLD_SRC",
    "MEGAPLAN_DISCOVER_ARNOLD_SRC",
)
_ARNOLD_MODULE_PREFIXES = ("arnold", "arnold_pipelines", "agentbox")
_SUPERVISOR_COMPONENTS = {
    "watchdog",
    "supervisor",
    "repair-loop",
    "meta-repair-loop",
    "progress-auditor",
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    return _sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def _file_identity(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve(strict=False)
    try:
        info = resolved.stat()
        data = resolved.read_bytes()
    except OSError:
        return {
            "path": str(resolved),
            "exists": False,
            "sha256": "",
            "size": 0,
            "mode": "",
        }
    return {
        "path": str(resolved),
        "exists": True,
        "sha256": _sha256_bytes(data),
        "size": len(data),
        "mode": stat.filemode(info.st_mode),
    }


def _json_file(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            f"{label} is unreadable or invalid JSON: {path}",
        ) from exc
    if not isinstance(value, dict):
        raise CliError(RUNTIME_ATTESTATION_ERROR, f"{label} must be a JSON object")
    return value


def _git_revision(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_branch(root: Path) -> str:
    """Return the current branch name, or empty string on failure."""
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_ancestry(root: Path, ancestor: str, descendant: str) -> bool:
    """Return True if *ancestor* is reachable from *descendant* (i.e., descendant contains ancestor)."""
    if not ancestor or not descendant:
        return False
    result = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", ancestor, descendant],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _git_remote_origin(root: Path) -> str:
    """Return the origin remote URL, or empty string."""
    result = subprocess.run(
        ["git", "-C", str(root), "remote", "get-url", "origin"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _collect_revision_components(root: Path) -> dict[str, Any]:
    """Collect complete revision identity: branch, HEAD, ancestry base, and remote origin."""
    head = _git_revision(root)
    branch = _git_branch(root)
    remote = _git_remote_origin(root)
    return {
        "branch": branch,
        "head": head,
        "remote_origin": remote,
    }


def _module_vector(expected_root: Path) -> tuple[list[dict[str, str]], list[str]]:
    entries: list[dict[str, str]] = []
    errors: list[str] = []
    expected = expected_root.resolve(strict=False)
    for name, module in sorted(sys.modules.items()):
        if not any(
            name == prefix or name.startswith(prefix + ".")
            for prefix in _ARNOLD_MODULE_PREFIXES
        ):
            continue
        raw_file = getattr(module, "__file__", None)
        if not isinstance(raw_file, str) or not raw_file:
            continue
        path = Path(raw_file).resolve(strict=False)
        entry = {
            "module": name,
            "path": str(path),
            "root": str(expected) if path.is_relative_to(expected) else "",
        }
        entries.append(entry)
        if not path.is_relative_to(expected):
            errors.append(f"mixed_module_root:{name}")
    return entries, errors


def _supervisor_module_vector(
    expected_runtime: Path,
) -> tuple[list[dict[str, str]], list[str]]:
    """Return the fixed supervisor import contract, independent of CLI imports."""

    import arnold
    import arnold_pipelines
    import arnold_pipelines.megaplan

    runtime_attestation_module = importlib.import_module(
        "arnold_pipelines.megaplan.cloud.runtime_attestation"
    )
    modules = {
        "arnold": arnold,
        "arnold_pipelines": arnold_pipelines,
        "arnold_pipelines.megaplan": arnold_pipelines.megaplan,
        "arnold_pipelines.megaplan.cloud.runtime_attestation": runtime_attestation_module,
    }
    runtime = expected_runtime.resolve(strict=False)
    entries: list[dict[str, str]] = []
    errors: list[str] = []
    for name, module in sorted(modules.items()):
        path = Path(str(module.__file__)).resolve(strict=False)
        inside = path.is_relative_to(runtime)
        entries.append(
            {
                "module": name,
                "path": str(path),
                "root": str(runtime) if inside else "",
            }
        )
        if not inside:
            errors.append(f"mixed_module_root:{name}")
    return entries, errors


def _active_site_dirs() -> list[Path]:
    values: set[Path] = set()
    active_paths = {
        Path(item).expanduser().resolve(strict=False)
        for item in sys.path
        if isinstance(item, str) and item
    }
    candidates: list[str] = []
    try:
        candidates.extend(site.getsitepackages())
    except AttributeError:
        pass
    try:
        user_site = site.getusersitepackages()
        candidates.extend([user_site] if isinstance(user_site, str) else user_site)
    except AttributeError:
        pass
    candidates.extend(
        item
        for item in sys.path
        if isinstance(item, str)
        and ("site-packages" in item or "dist-packages" in item)
    )
    for item in candidates:
        path = Path(item).expanduser().resolve(strict=False)
        if path.is_dir() and path in active_paths:
            values.add(path)
    return sorted(values)


def _pth_owners(site_dir: Path) -> dict[Path, list[str]]:
    owners: dict[Path, list[str]] = {}
    for distribution in importlib.metadata.distributions(path=[str(site_dir)]):
        name = str(distribution.metadata.get("Name") or "unknown")
        for relative in distribution.files or ():
            if not str(relative).endswith(".pth"):
                continue
            path = Path(distribution.locate_file(relative)).resolve(strict=False)
            owners.setdefault(path, []).append(name)
    return owners


def _pth_vector(expected_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    expected = expected_root.resolve(strict=False)
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for site_dir in _active_site_dirs():
        owners = _pth_owners(site_dir)
        for path in sorted(site_dir.glob("*.pth")):
            identity = _file_identity(path)
            try:
                raw_lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                raw_lines = []
                errors.append(f"pth_unreadable:{path}")
            lines: list[dict[str, str]] = []
            for raw in raw_lines:
                value = raw.strip()
                if not value:
                    kind = "blank"
                    resolved = ""
                elif value.startswith("#"):
                    kind = "comment"
                    resolved = ""
                elif value.startswith(("import ", "import\t")):
                    kind = "executable"
                    resolved = ""
                else:
                    kind = "path"
                    candidate = Path(value).expanduser()
                    if not candidate.is_absolute():
                        candidate = site_dir / candidate
                    resolved = str(candidate.resolve(strict=False))
                lines.append({"kind": kind, "raw": raw, "resolved": resolved})
                if kind == "executable" and not owners.get(path):
                    errors.append(f"unowned_executable_pth:{path}")
                if kind == "path" and resolved:
                    candidate = Path(resolved)
                    if candidate != expected and (
                        (candidate / "arnold").exists()
                        or (candidate / "arnold_pipelines").exists()
                    ):
                        errors.append(f"pth_mixed_arnold_root:{path}")
            records.append(
                {
                    **identity,
                    "site_dir": str(site_dir),
                    "owners": sorted(owners.get(path, [])),
                    "lines": lines,
                }
            )
    return records, errors


def _interpreter_vector(
    *,
    direct_url: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    executable = Path(sys.executable).resolve(strict=True)
    prefix = Path(sys.prefix).resolve(strict=True)
    base_prefix = Path(sys.base_prefix).resolve(strict=True)
    return {
        "executable": str(executable),
        "sha256": _sha256_file(executable),
        "prefix": str(prefix),
        "base_prefix": str(base_prefix),
        "venv": str(prefix) if prefix != base_prefix else "",
        "direct_url": dict(direct_url or {}),
    }


def _distribution_direct_url() -> dict[str, Any]:
    try:
        distribution = importlib.metadata.distribution("arnold")
        return json.loads(distribution.read_text("direct_url.json") or "{}")
    except (
        importlib.metadata.PackageNotFoundError,
        json.JSONDecodeError,
        OSError,
    ):
        return {}


def supervisor_runtime_vector(
    *,
    expected_source: Path,
    expected_revision: str,
    expected_runtime: Path,
    expected_fingerprint: str,
) -> dict[str, Any]:
    """Describe the dedicated, noneditable supervisor interpreter.

    This intentionally does not use :func:`runtime_provenance`: the launch,
    worker, and resident runtimes are editable checkouts, while the supervisor
    is an immutable wheel install in a separate venv.
    """

    source = expected_source.resolve(strict=False)
    runtime = expected_runtime.resolve(strict=False)
    direct_url = _distribution_direct_url()
    modules, module_errors = _supervisor_module_vector(runtime)
    pth, pth_errors = _pth_vector(runtime)
    errors = [*module_errors, *pth_errors]
    interpreter = _interpreter_vector(direct_url=direct_url)
    if Path(sys.prefix).resolve(strict=False) != runtime:
        errors.append("supervisor_runtime_prefix_mismatch")
    parsed = urlparse(str(direct_url.get("url") or ""))
    direct_source = (
        Path(unquote(parsed.path)).resolve(strict=False)
        if parsed.scheme == "file"
        else None
    )
    if direct_source != source:
        errors.append("supervisor_direct_url_source_mismatch")
    if bool((direct_url.get("dir_info") or {}).get("editable")):
        errors.append("supervisor_runtime_is_editable")
    if not modules:
        errors.append("supervisor_module_vector_empty")
    core = {
        "source": str(source),
        "source_revision": expected_revision,
        "source_fingerprint": expected_fingerprint,
        "runtime": str(runtime),
        "runtime_provenance": {
            "install_mode": "noneditable",
            "direct_url": direct_url,
        },
        "loaded_modules": modules,
        "interpreter": interpreter,
        "site_pth": pth,
        "errors": sorted(set(errors)),
        "ready": not errors,
    }
    return {**core, "content_sha256": _canonical_sha256(core)}


def _probe_supervisor_runtime(receipt: Mapping[str, Any]) -> dict[str, Any]:
    runtime = Path(str(receipt.get("runtime") or "")).resolve(strict=False)
    interpreter = runtime / "bin" / "python3"
    command = [
        str(interpreter),
        "-P",
        "-m",
        "arnold_pipelines.megaplan.cloud.runtime_attestation",
        "probe-supervisor",
        "--expected-source",
        str(receipt.get("source") or ""),
        "--expected-revision",
        str(receipt.get("source_revision") or ""),
        "--expected-runtime",
        str(runtime),
        "--expected-fingerprint",
        str(receipt.get("fingerprint") or ""),
    ]
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONSAFEPATH"] = "1"
    try:
        process = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
            env=environment,
        )
        payload = json.loads(process.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "could not inspect the dedicated supervisor runtime",
        ) from exc
    if process.returncode != 0 or not isinstance(payload, dict):
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "dedicated supervisor runtime is not release-ready: "
            + (process.stderr.strip() or str(payload.get("errors") or [])),
        )
    return payload


def _wrapper_vector(expected_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    wrapper_dir = expected_root / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"
    wrappers = [
        _file_identity(path)
        for path in sorted(wrapper_dir.glob("arnold-*"))
        if path.is_file()
    ]
    return wrappers, ([] if wrappers else ["wrapper_manifest_empty"])


def _parse_hot_env(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    values: dict[str, str] = {}
    for line in lines:
        value = line.strip()
        if value.startswith("export ") and "=" in value:
            name, raw = value[7:].split("=", 1)
            if name in RUNTIME_SELECTOR_NAMES:
                values[name] = raw.strip().strip("'\"")
    return values


def _chain_binding_runtime_identity(spec_path: Path) -> dict[str, Any]:
    """Extract the immutable runtime identity from the live chain binding.

    The seed pins the RUNTIME (import_root/source_revision), not the mutable
    milestone/plan fields — those legitimately advance while a chain runs, so
    comparing the full binding would false-drift after the first plan is
    created after seed build.
    """
    return dict(_chain_binding(spec_path).get("runtime_identity") or {})


def _chain_binding(spec_path: Path) -> dict[str, Any]:
    from arnold_pipelines.megaplan.chain.spec import load_chain_state

    state = load_chain_state(spec_path, verify_execution_binding=False)
    execution = (state.metadata or {}).get("execution_binding")
    execution = execution if isinstance(execution, Mapping) else {}
    runtime = execution.get("runtime_binding")
    runtime = runtime if isinstance(runtime, Mapping) else {}
    current = runtime.get("current_identity")
    current = current if isinstance(current, Mapping) else {}
    core = {
        "spec_path": str(spec_path.resolve(strict=False)),
        "current_milestone_index": state.current_milestone_index,
        "current_plan_name": state.current_plan_name or "",
        "runtime_identity": dict(current),
    }
    return {**core, "content_sha256": _canonical_sha256(core)}


def _manifest(paths: Iterable[Path]) -> dict[str, Any]:
    entries = [_file_identity(path) for path in sorted(set(paths))]
    core = {"entries": entries}
    return {**core, "content_sha256": _canonical_sha256(core)}


def _marker_launch_binding(marker: Mapping[str, Any]) -> dict[str, Any]:
    """Return the immutable launch identity carried by a lifecycle marker.

    Session markers are live control-plane documents: pause/resume, launch
    outcomes, timestamps, and notification state all change during an ordinary
    launch.  A release seed therefore binds only the fields that select which
    runtime and durable chain may be launched.
    """

    runtime = marker.get("runtime_binding")
    runtime = runtime if isinstance(runtime, Mapping) else {}
    identity = runtime.get("current_identity")
    identity = identity if isinstance(identity, Mapping) else {}
    return {
        "session": str(marker.get("session") or ""),
        "workspace": str(marker.get("workspace") or ""),
        "remote_spec": str(marker.get("remote_spec") or ""),
        "identity_digest": str(marker.get("identity_digest") or ""),
        "run_kind": str(marker.get("run_kind") or ""),
        "relaunch_command": str(
            marker.get("relaunch_command") or marker.get("launch_command") or ""
        ),
        "editable_source_branch": str(marker.get("editable_source_branch") or ""),
        "editable_source_head": str(marker.get("editable_source_head") or ""),
        "runtime_identity": dict(identity),
    }


def build_runtime_launch_seed(
    *,
    expected_root: Path,
    expected_revision: str,
    supervisor_receipt_path: Path,
    hot_env_path: Path,
    marker_path: Path,
    chain_spec_path: Path,
    seed_doc_paths: Iterable[Path] = (),
    expected_branch: str | None = None,
    expected_ancestry_base: str | None = None,
    manifest_path: Path | None = None,
    chain_runtime_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one strict release seed from current runtime and durable inputs.

    When *expected_branch* is provided, the current branch must match exactly.
    When *expected_ancestry_base* is provided, the current HEAD must descend
    from it (ancestry check).  Mixed-revision modules — where any loaded
    Arnold module originates from a different root — are always blocked.

    The supervisor receipt is attested INDEPENDENTLY of the per-epic runtime:
    the receipt's ``source`` / ``source_revision`` legitimately differ from
    *expected_root* / *expected_revision* (the supervisor wheel is prepared
    from its own consolidated source), so only the probe-ready state,
    fingerprint, import-receipt self-consistency, and runtime-prefix checks
    gate it.

    *manifest_path*, when provided, is the per-session runtime-manifest pin
    that SELECTS this runtime (G4); the six retired SRC selectors in hot-env
    are then recorded but not enforced.  *chain_runtime_identity*, when
    provided, is the freshly bound execution identity (already in memory by
    the time a chain start seeds the runtime); it replaces the persisted
    chain-state read, which is not yet saved on a first launch.
    """

    root = expected_root.resolve(strict=False)
    seed_doc_paths = tuple(seed_doc_paths)
    provenance = runtime_provenance(
        expected_root=root,
        expected_revision=expected_revision,
    )
    modules, module_errors = _module_vector(root)
    pth, pth_errors = _pth_vector(root)
    wrappers, wrapper_errors = _wrapper_vector(root)
    supervisor_receipt = _json_file(
        supervisor_receipt_path,
        label="supervisor receipt",
    )
    supervisor_vector = _probe_supervisor_runtime(supervisor_receipt)
    marker = _json_file(marker_path, label="cloud session marker")
    chain_binding = _chain_binding(chain_spec_path)
    hot_selectors = _parse_hot_env(hot_env_path)
    # ── Step 5A: collect revision components (branch, HEAD, origin) ────
    revision_components = _collect_revision_components(root)
    document_paths = {
        supervisor_receipt_path,
        hot_env_path,
        chain_spec_path,
        *seed_doc_paths,
    }
    seed_manifest = _manifest(document_paths)
    errors = [
        *list(provenance.get("errors") or []),
        *module_errors,
        *pth_errors,
        *wrapper_errors,
    ]
    for path in document_paths:
        if not _file_identity(path).get("exists"):
            errors.append(f"seed_document_missing:{path}")
    # Independent supervisor attestation: the receipt's source/revision need
    # NOT equal the per-epic worker root (the Jul-31 supervisor wheel is
    # prepared from its own consolidated source).  What IS required: the
    # receipt carries a fingerprint, the probe of the dedicated supervisor
    # runtime is ready (runtime prefix + noneditable direct-url source checks
    # live inside the probe vector), and the receipt's import list is
    # self-consistent with the probed loaded modules.
    if not str(supervisor_receipt.get("fingerprint") or ""):
        errors.append("supervisor_fingerprint_missing")
    if not supervisor_vector.get("ready"):
        errors.extend(
            f"supervisor:{item}" for item in supervisor_vector.get("errors") or []
        )
    receipt_imports = supervisor_receipt.get("imports")
    vector_imports = {
        str(item.get("module")): str(item.get("path"))
        for item in supervisor_vector.get("loaded_modules") or []
        if isinstance(item, Mapping)
        and str(item.get("module")) in {"arnold", "arnold_pipelines", "arnold_pipelines.megaplan"}
    }
    expected_imports = {
        "arnold": vector_imports.get("arnold", ""),
        "arnold_pipelines": vector_imports.get("arnold_pipelines", ""),
        "megaplan": vector_imports.get("arnold_pipelines.megaplan", ""),
    }
    if receipt_imports != expected_imports:
        errors.append("supervisor_import_receipt_mismatch")
    # The per-session runtime manifest is the runtime selector (G4); the six
    # retired SRC selectors in hot-env are inert documentation.  A manifest-
    # pinned build (production path) records them but does not enforce them;
    # the manifestless CLI build still fails closed on a selector that
    # disagrees with the expected root.
    if manifest_path is None:
        for name in RUNTIME_SELECTOR_NAMES[:6]:
            value = hot_selectors.get(name)
            if value and Path(value).resolve(strict=False) != root:
                errors.append(f"hot_env_selector_mismatch:{name}")
    marker_runtime = marker.get("runtime_binding")
    marker_runtime = marker_runtime if isinstance(marker_runtime, Mapping) else {}
    marker_identity = marker_runtime.get("current_identity")
    marker_identity = marker_identity if isinstance(marker_identity, Mapping) else {}
    if str(marker_identity.get("import_root") or "") != str(root):
        errors.append("marker_runtime_root_mismatch")
    if str(marker_identity.get("source_revision") or "") != expected_revision:
        errors.append("marker_runtime_revision_mismatch")
    if chain_runtime_identity is not None:
        chain_identity = dict(chain_runtime_identity)
        chain_binding_record = {
            **chain_binding,
            "runtime_identity": dict(chain_identity),
        }
        chain_binding_record["content_sha256"] = _canonical_sha256(
            {
                key: value
                for key, value in chain_binding_record.items()
                if key != "content_sha256"
            }
        )
    else:
        chain_identity = chain_binding.get("runtime_identity")
        chain_identity = chain_identity if isinstance(chain_identity, Mapping) else {}
        chain_binding_record = chain_binding
    if str(chain_identity.get("import_root") or "") != str(root):
        errors.append("chain_runtime_root_mismatch")
    if str(chain_identity.get("source_revision") or "") != expected_revision:
        errors.append("chain_runtime_revision_mismatch")
    if dict(marker_identity) != dict(chain_identity):
        errors.append("marker_chain_runtime_identity_mismatch")
    # ── Step 5A: branch binding ─────────────────────────────────────────
    if expected_branch is not None:
        current_branch = revision_components["branch"]
        if current_branch != expected_branch:
            errors.append(
                f"branch_mismatch:expected={expected_branch},actual={current_branch}"
            )
    # ── Step 5A: ancestry binding ───────────────────────────────────────
    if expected_ancestry_base is not None:
        current_head = revision_components["head"]
        if not _git_ancestry(root, expected_ancestry_base, current_head):
            errors.append(
                f"ancestry_mismatch:base={expected_ancestry_base},head={current_head}"
            )
    # ── Step 5A: mixed-revision blocking ────────────────────────────────
    for mod in modules:
        mod_root = mod.get("root", "")
        if mod_root and mod_root != str(root):
            errors.append(f"mixed_revision_module:{mod.get('module')}")
    core = {
        "schema": RUNTIME_LAUNCH_SEED_SCHEMA,
        "expected_root": str(root),
        "expected_revision": expected_revision,
        "revision_components": revision_components,
        "expected_branch": expected_branch,
        "expected_ancestry_base": expected_ancestry_base,
        "runtime_provenance": provenance,
        "loaded_modules": modules,
        "interpreter": _interpreter_vector(
            direct_url=(
                provenance.get("direct_url")
                if isinstance(provenance.get("direct_url"), Mapping)
                else {}
            )
        ),
        "site_pth": pth,
        "wrappers": wrappers,
        "supervisor_receipt": {
            "file": _file_identity(supervisor_receipt_path),
            "fingerprint": supervisor_receipt.get("fingerprint"),
            "runtime": supervisor_receipt.get("runtime"),
            "source": supervisor_receipt.get("source"),
            "source_revision": supervisor_receipt.get("source_revision"),
            "imports": supervisor_receipt.get("imports"),
        },
        "supervisor_runtime": supervisor_vector,
        "hot_env": {
            "file": _file_identity(hot_env_path),
            "selectors": hot_selectors,
        },
        "marker": {
            "path": str(marker_path.resolve(strict=False)),
            "launch_binding": _marker_launch_binding(marker),
            "runtime_identity": dict(marker_identity),
        },
        "chain_runtime_binding": chain_binding_record,
        "seed_document_manifest": seed_manifest,
        "input_paths": {
            "supervisor_receipt": str(supervisor_receipt_path.resolve(strict=False)),
            "hot_env": str(hot_env_path.resolve(strict=False)),
            "marker": str(marker_path.resolve(strict=False)),
            "chain_spec": str(chain_spec_path.resolve(strict=False)),
            "manifest": (
                str(manifest_path.resolve(strict=False))
                if manifest_path is not None
                else ""
            ),
            "seed_docs": [
                str(path.resolve(strict=False)) for path in sorted(set(seed_doc_paths))
            ],
        },
        "errors": sorted(set(errors)),
        "ready": not errors,
    }
    return {**core, "content_sha256": _canonical_sha256(core)}


def _launch_seed_store_dir() -> Path:
    return (
        Path(os.environ.get("ARNOLD_RUNTIME_MANIFEST_DIR", "/workspace/.megaplan"))
        / "runtime-launch-seeds"
    )


def _live_runtime_identity(*, root: Path, expected_revision: str) -> dict[str, Any]:
    """Content-addressed identity of the live runtime at the pinned revision."""
    from arnold_pipelines.megaplan.cloud.runtime_provenance import (
        normalized_runtime_identity,
    )

    provenance = runtime_provenance(
        expected_root=root,
        expected_revision=expected_revision,
    )
    if not provenance.get("ok"):
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "live runtime does not satisfy the manifest pin: "
            + ", ".join(str(item) for item in provenance.get("errors") or []),
        )
    return normalized_runtime_identity(provenance)


def _rebind_marker_if_stale(
    marker_path: Path,
    marker: Mapping[str, Any],
    *,
    live_identity: Mapping[str, Any],
    source_branch: str,
) -> None:
    """CAS-rebind the cloud-session marker when its runtime identity is stale.

    Uses the CAS-protected marker/runtime cutover helper (never hand-edited
    JSON): the marker file SHA-256 and the previous runtime identity SHA-256
    are both guarded, and any concurrent change fails the CAS with a typed
    error instead of being overwritten.
    """
    from arnold_pipelines.megaplan.cloud.runtime_cutover import (
        marker_runtime_identity,
        update_marker_runtime,
    )

    marker_identity = marker_runtime_identity(marker)
    if marker_identity is None:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "cloud session marker has no content-addressable runtime identity",
        )
    if marker_identity == live_identity:
        return
    relaunch_command = str(
        marker.get("relaunch_command") or marker.get("launch_command") or ""
    ).strip()
    if not relaunch_command:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "cloud session marker drift requires a relaunch command for rebinding",
        )
    update_marker_runtime(
        marker_path,
        expected_marker_sha256=_sha256_file(marker_path),
        expected_previous_runtime_sha256=str(marker_identity["content_sha256"]),
        active_runtime_identity=live_identity,
        relaunch_command=relaunch_command,
        reason="chain-start launch-seed marker rebind",
        actor="chain",
        direction="cutover",
        source_branch=source_branch,
    )


def _launch_seed_current(
    seed_path: Path,
    *,
    root: Path,
    expected_revision: str,
) -> bool:
    """True when the on-disk seed is release-ready and still pinned to root/revision."""
    try:
        seed = _json_file(seed_path, label="runtime launch seed")
        _verify_seed_digest(seed)
    except CliError:
        return False
    return (
        bool(seed.get("ready"))
        and str(seed.get("expected_root") or "") == str(root)
        and str(seed.get("expected_revision") or "") == expected_revision
    )


def ensure_runtime_launch_seed(
    *,
    manifest_path: Path,
    chain_spec_path: Path,
    marker_path: Path,
    chain_runtime_identity: Mapping[str, Any] | None = None,
    seed_dir: Path | None = None,
    supervisor_receipt_path: Path | None = None,
    hot_env_path: Path | None = None,
    expected_branch: str | None = None,
    expected_ancestry_base: str | None = None,
) -> Path:
    """Build or refresh the canonical runtime launch seed for one per-epic runtime.

    The per-session runtime manifest (``ARNOLD_RUNTIME_MANIFEST``) is the
    runtime selector (G4): ``epic.runtime_root`` and ``epic.expected_head``
    pin the seeded runtime, and the live checkout HEAD MUST equal the pin
    (else :class:`CliError`).  The marker's
    ``runtime_binding.current_identity`` must agree with the live provenance
    at the expected revision and with the chain execution binding; a stale
    marker is rebound through the CAS-protected marker/runtime cutover helper
    (never hand-edited).  The seed is rebuilt whenever it is missing, not
    release-ready, content-digest-invalid, or pinned to a different
    root/revision.  On success returns the seed path; the caller exports it
    as ``MEGAPLAN_RUNTIME_LAUNCH_SEED`` for every child worker/watchdog.
    """
    from arnold_pipelines.megaplan.cloud.runtime_manifest import (
        ManifestError,
        load_manifest,
    )

    try:
        manifest = load_manifest(manifest_path)
    except ManifestError as exc:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            f"runtime manifest {manifest_path} is invalid: {exc}",
        ) from exc
    epic = manifest.epic
    runtime_root = str(epic.get("runtime_root") or "").strip()
    expected_revision = str(epic.get("expected_head") or "").strip()
    if not runtime_root or not expected_revision:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "runtime manifest lacks nonempty epic.runtime_root and epic.expected_head",
        )
    root = Path(runtime_root).expanduser().resolve()
    live_head = _git_revision(root)
    if not live_head or live_head != expected_revision:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            f"runtime root HEAD does not match the manifest pin: "
            f"expected {expected_revision}, live {live_head or '<unreadable>'}",
        )
    live_identity = _live_runtime_identity(
        root=root,
        expected_revision=expected_revision,
    )
    if chain_runtime_identity is not None:
        from arnold_pipelines.megaplan.cloud.runtime_cutover import (
            normalize_runtime_identity,
        )

        chain_identity = normalize_runtime_identity(chain_runtime_identity)
        # Compare the launch-relevant identity (grok consult, d58701026410):
        # import_root + source_revision, resolved. The digest is a derived
        # view; root+rev are the facts the tree determines. Equal root+rev
        # with different diagnostic shapes (editable/pth/imports populated vs
        # None depending on which writer stored them) is the same runtime.
        # Fail closed on root or revision mismatch only.
        chain_root = str(
            (chain_identity.get("import_root") or "").rstrip("/")
        )
        live_root = str((live_identity.get("import_root") or "").rstrip("/"))
        chain_rev = str(chain_identity.get("source_revision") or "")
        live_rev = str(live_identity.get("source_revision") or "")
        if chain_root != live_root or chain_rev != live_rev:
            raise CliError(
                RUNTIME_ATTESTATION_ERROR,
                "chain execution binding does not match the live manifest-pinned runtime",
            )
        bound_identity = chain_identity
    else:
        bound_identity = live_identity
    marker = _json_file(marker_path, label="cloud session marker")
    _rebind_marker_if_stale(
        marker_path,
        marker,
        live_identity=live_identity,
        source_branch=str(epic.get("branch") or ""),
    )
    seed_path = (seed_dir or _launch_seed_store_dir()) / f"{manifest.runtime_id}.json"
    seed_path = seed_path.resolve(strict=False)
    if _launch_seed_current(seed_path, root=root, expected_revision=expected_revision):
        return seed_path
    payload = build_runtime_launch_seed(
        expected_root=root,
        expected_revision=expected_revision,
        supervisor_receipt_path=supervisor_receipt_path
        or SUPERVISOR_RECEIPT_DEFAULT_PATH,
        hot_env_path=hot_env_path or CLOUD_HOT_ENV_DEFAULT_PATH,
        marker_path=marker_path,
        chain_spec_path=chain_spec_path,
        seed_doc_paths=(),
        expected_branch=expected_branch,
        expected_ancestry_base=expected_ancestry_base,
        manifest_path=manifest_path,
        chain_runtime_identity=bound_identity,
    )
    if not bool(payload.get("ready")):
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "runtime launch seed is not release-ready: "
            + ", ".join(str(item) for item in payload.get("errors") or []),
        )
    _atomic_write(seed_path, payload)
    return seed_path


def _verify_seed_digest(seed: Mapping[str, Any]) -> None:
    core = {key: value for key, value in seed.items() if key != "content_sha256"}
    if seed.get("schema") != RUNTIME_LAUNCH_SEED_SCHEMA or seed.get(
        "content_sha256"
    ) != _canonical_sha256(core):
        raise CliError(
            RUNTIME_ATTESTATION_ERROR, "runtime launch seed digest is invalid"
        )


def runtime_vector_sha256(seed: Mapping[str, Any]) -> str:
    """Hash the complete loaded-code vector carried by a verified launch seed."""

    return _canonical_sha256(
        {
            "modules": seed.get("loaded_modules"),
            "interpreter": seed.get("interpreter"),
            "pth": seed.get("site_pth"),
            "wrappers": seed.get("wrappers"),
        }
    )


def _component_runtime_vector_sha256(
    seed: Mapping[str, Any],
    *,
    component: str,
) -> str:
    if component in _SUPERVISOR_COMPONENTS:
        return _canonical_sha256(
            {
                "runtime": seed.get("supervisor_runtime"),
                "wrappers": seed.get("wrappers"),
            }
        )
    return runtime_vector_sha256(seed)


def validate_runtime_launch_seed(
    seed: Mapping[str, Any],
    *,
    component: str,
) -> dict[str, Any]:
    """Revalidate a launch seed against files, imports, and current interpreter."""

    _verify_seed_digest(seed)
    if not bool(seed.get("ready")) or seed.get("errors"):
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "runtime launch seed was not release-ready",
        )
    root = Path(str(seed.get("expected_root") or "")).resolve(strict=False)
    revision = str(seed.get("expected_revision") or "")
    is_supervisor = component in _SUPERVISOR_COMPONENTS
    supervisor = seed.get("supervisor_receipt")
    supervisor = supervisor if isinstance(supervisor, Mapping) else {}
    if is_supervisor:
        current_runtime = supervisor_runtime_vector(
            expected_source=root,
            expected_revision=revision,
            expected_runtime=Path(str(supervisor.get("runtime") or "")),
            expected_fingerprint=str(supervisor.get("fingerprint") or ""),
        )
        if current_runtime != seed.get("supervisor_runtime"):
            raise CliError(
                RUNTIME_ATTESTATION_ERROR,
                "dedicated supervisor runtime vector drifted",
            )
        expected_runtime = seed.get("supervisor_runtime")
        expected_runtime = expected_runtime if isinstance(expected_runtime, Mapping) else {}
        expected_modules = expected_runtime.get("loaded_modules")
        module_root = Path(str(supervisor.get("runtime") or "")).resolve(strict=False)
    else:
        provenance = runtime_provenance(expected_root=root, expected_revision=revision)
        if not provenance.get("ok"):
            raise CliError(
                RUNTIME_ATTESTATION_ERROR,
                f"runtime provenance changed: {provenance.get('errors')}",
            )
        if provenance != seed.get("runtime_provenance"):
            raise CliError(
                RUNTIME_ATTESTATION_ERROR,
                "runtime provenance or direct_url identity drifted",
            )
        expected_modules = seed.get("loaded_modules")
        module_root = root
    modules, module_errors = (
        _supervisor_module_vector(module_root)
        if is_supervisor
        else _module_vector(module_root)
    )
    if module_errors:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "loaded Arnold modules escaped the expected root: "
            + ", ".join(module_errors),
        )
    if not isinstance(expected_modules, list):
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "runtime launch seed has no loaded Arnold module vector",
        )
    current_by_name = {item["module"]: item for item in modules}
    for expected_module in expected_modules:
        if not isinstance(expected_module, Mapping):
            raise CliError(
                RUNTIME_ATTESTATION_ERROR,
                "runtime launch seed contains an invalid module identity",
            )
        name = str(expected_module.get("module") or "")
        if current_by_name.get(name) != expected_module:
            raise CliError(
                RUNTIME_ATTESTATION_ERROR,
                f"loaded module identity changed: {name or '<missing>'}",
            )
    pth, pth_errors = _pth_vector(module_root)
    expected_pth = (
        (seed.get("supervisor_runtime") or {}).get("site_pth")
        if is_supervisor
        else seed.get("site_pth")
    )
    if pth_errors or pth != expected_pth:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "active site .pth vector changed or is unsafe: " + ", ".join(pth_errors),
        )
    wrappers, wrapper_errors = _wrapper_vector(root)
    if wrapper_errors or wrappers != seed.get("wrappers"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "runtime wrapper manifest drifted")
    expected_interpreter = seed.get("interpreter")
    if is_supervisor:
        runtime = str(supervisor.get("runtime") or "")
        if not runtime or Path(sys.prefix).resolve(strict=False) != Path(
            runtime
        ).resolve(strict=False):
            raise CliError(
                RUNTIME_ATTESTATION_ERROR,
                "supervisor interpreter does not match its prepared runtime",
            )
    else:
        current_interpreter = _interpreter_vector(
            direct_url=(
                provenance.get("direct_url")
                if isinstance(provenance.get("direct_url"), Mapping)
                else {}
            )
        )
        if current_interpreter != expected_interpreter:
            raise CliError(
                RUNTIME_ATTESTATION_ERROR, "runtime interpreter identity drifted"
            )
    paths = seed.get("input_paths")
    paths = paths if isinstance(paths, Mapping) else {}
    manifest_paths = [
        Path(str(paths.get(name) or ""))
        for name in ("supervisor_receipt", "hot_env", "chain_spec")
    ]
    manifest_paths.extend(Path(str(path)) for path in paths.get("seed_docs") or [])
    if _manifest(manifest_paths) != seed.get("seed_document_manifest"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "seed document manifest drifted")
    if _file_identity(Path(str(paths.get("supervisor_receipt") or ""))) != (
        seed.get("supervisor_receipt") or {}
    ).get("file"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "supervisor receipt drifted")
    if _file_identity(Path(str(paths.get("hot_env") or ""))) != (
        seed.get("hot_env") or {}
    ).get("file"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "hot-env selector file drifted")
    marker_path = Path(str(paths.get("marker") or ""))
    marker = _json_file(marker_path, label="cloud session marker")
    expected_marker = seed.get("marker")
    expected_marker = expected_marker if isinstance(expected_marker, Mapping) else {}
    if (
        str(marker_path.resolve(strict=False)) != str(expected_marker.get("path") or "")
        or _marker_launch_binding(marker) != expected_marker.get("launch_binding")
    ):
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "cloud marker launch binding drifted",
        )
    live_binding_runtime = _chain_binding_runtime_identity(
        Path(str(paths.get("chain_spec") or ""))
    )
    seed_binding_runtime = (seed.get("chain_runtime_binding") or {}).get(
        "runtime_identity"
    ) or {}
    # Compare the launch-relevant identity (grok consult, d58701026410):
    # import_root + source_revision, resolved — the fields the seed actually
    # pins (see _chain_binding_runtime_identity docstring). Diagnostic shape
    # (editable/pth/imports) legitimately differs between writers; root+rev
    # are the tree-determined facts.
    if (
        str(live_binding_runtime.get("import_root") or "").rstrip("/")
        != str(seed_binding_runtime.get("import_root") or "").rstrip("/")
        or str(live_binding_runtime.get("source_revision") or "")
        != str(seed_binding_runtime.get("source_revision") or "")
    ):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "chain runtime binding drifted")
    return {
        "status": "ready",
        "seed_sha256": seed["content_sha256"],
        "expected_root": str(root),
        "expected_revision": revision,
        "runtime_vector_sha256": _component_runtime_vector_sha256(
            seed,
            component=component,
        ),
    }


def _proc_identity(pid: int) -> dict[str, Any]:
    proc = Path("/proc") / str(pid)
    try:
        stat_fields = (proc / "stat").read_text(encoding="utf-8").split()
        start_ticks = stat_fields[21]
        executable = (proc / "exe").resolve(strict=True)
        environ_raw = (proc / "environ").read_bytes()
    except (OSError, IndexError) as exc:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            f"cannot inspect target process {pid}",
        ) from exc
    environ: dict[str, str] = {}
    for item in environ_raw.split(b"\0"):
        if b"=" not in item:
            continue
        name, value = item.split(b"=", 1)
        decoded_name = name.decode("utf-8", errors="replace")
        if decoded_name in RUNTIME_SELECTOR_NAMES:
            environ[decoded_name] = value.decode("utf-8", errors="replace")
    return {
        "pid": pid,
        "start_ticks": start_ticks,
        "executable": str(executable),
        "executable_sha256": _sha256_file(executable),
        "selectors": environ,
    }


def create_runtime_process_attestation(
    seed: Mapping[str, Any],
    *,
    component: str,
    target_pid: int,
) -> dict[str, Any]:
    validation = validate_runtime_launch_seed(seed, component=component)
    process = _proc_identity(target_pid)
    expected_selectors = (seed.get("hot_env") or {}).get("selectors") or {}
    mismatches = {
        name: {"expected": expected, "actual": process["selectors"].get(name, "")}
        for name, expected in expected_selectors.items()
        if process["selectors"].get(name) != expected
    }
    if mismatches:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            f"process inherited stale runtime selectors: {sorted(mismatches)}",
        )
    core = {
        "schema": RUNTIME_PROCESS_ATTESTATION_SCHEMA,
        "component": component,
        "seed_sha256": validation["seed_sha256"],
        "runtime_vector_sha256": validation["runtime_vector_sha256"],
        "process": process,
    }
    return {**core, "content_sha256": _canonical_sha256(core)}


def validate_runtime_process_attestation(
    seed: Mapping[str, Any],
    attestation: Mapping[str, Any],
    *,
    component: str,
    target_pid: int,
) -> dict[str, Any]:
    validation = validate_runtime_launch_seed(seed, component=component)
    core = {
        key: attestation.get(key)
        for key in (
            "schema",
            "component",
            "seed_sha256",
            "runtime_vector_sha256",
            "process",
        )
    }
    if (
        attestation.get("schema") != RUNTIME_PROCESS_ATTESTATION_SCHEMA
        or attestation.get("content_sha256") != _canonical_sha256(core)
        or attestation.get("component") != component
        or attestation.get("seed_sha256") != validation["seed_sha256"]
        or attestation.get("runtime_vector_sha256")
        != validation["runtime_vector_sha256"]
        or attestation.get("process") != _proc_identity(target_pid)
    ):
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "runtime process attestation is stale or belongs to another process",
        )
    return validation


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path = path.resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def configured_runtime_attestation_required() -> bool:
    """Return ``True`` unless runtime attestation is explicitly disabled.

    Deny-by-default: runtime attestation is REQUIRED when
    ``MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED`` is absent or any value other
    than ``"0"``.  Only an explicit ``"0"`` opts out.

    Note: the flag cannot waive the launch-seed requirement — a production
    launch always needs ``MEGAPLAN_RUNTIME_LAUNCH_SEED`` (see
    :func:`require_configured_runtime_launch`, which fails closed on a
    missing seed regardless of this flag).
    """
    return os.environ.get("MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED") != "0"


def configured_seed_path() -> Path | None:
    value = str(os.environ.get("MEGAPLAN_RUNTIME_LAUNCH_SEED") or "").strip()
    return Path(value).expanduser().resolve(strict=False) if value else None


def configured_process_attestation_path(component: str) -> Path:
    value = str(os.environ.get("MEGAPLAN_RUNTIME_PROCESS_ATTESTATION") or "").strip()
    if value:
        return Path(value).expanduser().resolve(strict=False)
    return (
        Path("/workspace/.megaplan/status")
        / f"{component}.runtime-process-attestation.json"
    )


def require_configured_runtime_launch(
    component: str,
    *,
    target_pid: int | None = None,
    create: bool = False,
) -> dict[str, Any]:
    seed_path = configured_seed_path()
    if seed_path is None:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "canonical runtime launch seed is required but missing",
        )
    seed = _json_file(seed_path, label="runtime launch seed")
    pid = target_pid or os.getpid()
    attestation_path = configured_process_attestation_path(component)
    if create:
        attestation = create_runtime_process_attestation(
            seed,
            component=component,
            target_pid=pid,
        )
        _atomic_write(attestation_path, attestation)
    else:
        attestation = _json_file(
            attestation_path,
            label="runtime process attestation",
        )
        validate_runtime_process_attestation(
            seed,
            attestation,
            component=component,
            target_pid=pid,
        )
    return seed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    build = sub.add_parser("build")
    build.add_argument("--expected-root", type=Path, required=True)
    build.add_argument("--expected-revision", required=True)
    build.add_argument("--supervisor-receipt", type=Path, required=True)
    build.add_argument("--hot-env", type=Path, required=True)
    build.add_argument("--marker", type=Path, required=True)
    build.add_argument("--chain-spec", type=Path, required=True)
    build.add_argument("--seed-doc", type=Path, action="append", default=[])
    build.add_argument("--output", type=Path, required=True)
    startup = sub.add_parser("startup")
    startup.add_argument("--component", required=True)
    startup.add_argument("--target-pid", type=int, required=True)
    verify = sub.add_parser("verify-process")
    verify.add_argument("--component", required=True)
    verify.add_argument("--target-pid", type=int, required=True)
    probe = sub.add_parser("probe-supervisor")
    probe.add_argument("--expected-source", type=Path, required=True)
    probe.add_argument("--expected-revision", required=True)
    probe.add_argument("--expected-runtime", type=Path, required=True)
    probe.add_argument("--expected-fingerprint", required=True)
    args = parser.parse_args(argv)
    if args.action == "build":
        payload = build_runtime_launch_seed(
            expected_root=args.expected_root,
            expected_revision=args.expected_revision,
            supervisor_receipt_path=args.supervisor_receipt,
            hot_env_path=args.hot_env,
            marker_path=args.marker,
            chain_spec_path=args.chain_spec,
            seed_doc_paths=args.seed_doc,
        )
        _atomic_write(args.output, payload)
        print(json.dumps(payload, sort_keys=True))
        return 0 if payload["ready"] else 2
    if args.action == "probe-supervisor":
        payload = supervisor_runtime_vector(
            expected_source=args.expected_source,
            expected_revision=args.expected_revision,
            expected_runtime=args.expected_runtime,
            expected_fingerprint=args.expected_fingerprint,
        )
        print(json.dumps(payload, sort_keys=True))
        return 0 if payload["ready"] else 2
    require_configured_runtime_launch(
        args.component,
        target_pid=args.target_pid,
        create=args.action == "startup",
    )
    print(json.dumps({"success": True, "component": args.component}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
