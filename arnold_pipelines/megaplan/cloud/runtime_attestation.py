"""Content-addressed runtime launch seeds and process attestations."""

from __future__ import annotations

import argparse
import hashlib
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

from arnold_pipelines.megaplan.cloud.runtime_provenance import runtime_provenance
from arnold_pipelines.megaplan.types import CliError


RUNTIME_LAUNCH_SEED_SCHEMA = "arnold.megaplan.runtime_launch_seed.v1"
RUNTIME_PROCESS_ATTESTATION_SCHEMA = "arnold.megaplan.runtime_process_attestation.v1"
RUNTIME_ATTESTATION_ERROR = "runtime_launch_attestation_mismatch"
RUNTIME_SELECTOR_NAMES = (
    "MEGAPLAN_RUNTIME_SRC",
    "MEGAPLAN_LAUNCH_RUNTIME_SRC",
    "MEGAPLAN_SUPERVISOR_SOURCE",
    "CLOUD_WATCHDOG_ARNOLD_SRC",
    "MEGAPLAN_META_ARNOLD_SRC",
    "MEGAPLAN_AUDIT_ARNOLD_SRC",
    "MEGAPLAN_SUPERVISOR_PYTHON",
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


def build_runtime_launch_seed(
    *,
    expected_root: Path,
    expected_revision: str,
    supervisor_receipt_path: Path,
    hot_env_path: Path,
    marker_path: Path,
    chain_spec_path: Path,
    seed_doc_paths: Iterable[Path] = (),
) -> dict[str, Any]:
    """Build one strict release seed from current runtime and durable inputs."""

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
    marker = _json_file(marker_path, label="cloud session marker")
    chain_binding = _chain_binding(chain_spec_path)
    hot_selectors = _parse_hot_env(hot_env_path)
    document_paths = {
        supervisor_receipt_path,
        hot_env_path,
        marker_path,
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
    if str(supervisor_receipt.get("source") or "") != str(root):
        errors.append("supervisor_source_mismatch")
    if str(supervisor_receipt.get("source_revision") or "") != expected_revision:
        errors.append("supervisor_revision_mismatch")
    if not str(supervisor_receipt.get("fingerprint") or ""):
        errors.append("supervisor_fingerprint_missing")
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
    chain_identity = chain_binding.get("runtime_identity")
    chain_identity = chain_identity if isinstance(chain_identity, Mapping) else {}
    if str(chain_identity.get("import_root") or "") != str(root):
        errors.append("chain_runtime_root_mismatch")
    if str(chain_identity.get("source_revision") or "") != expected_revision:
        errors.append("chain_runtime_revision_mismatch")
    core = {
        "schema": RUNTIME_LAUNCH_SEED_SCHEMA,
        "expected_root": str(root),
        "expected_revision": expected_revision,
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
        "hot_env": {
            "file": _file_identity(hot_env_path),
            "selectors": hot_selectors,
        },
        "marker": {
            "file": _file_identity(marker_path),
            "runtime_identity": dict(marker_identity),
        },
        "chain_runtime_binding": chain_binding,
        "seed_document_manifest": seed_manifest,
        "input_paths": {
            "supervisor_receipt": str(supervisor_receipt_path.resolve(strict=False)),
            "hot_env": str(hot_env_path.resolve(strict=False)),
            "marker": str(marker_path.resolve(strict=False)),
            "chain_spec": str(chain_spec_path.resolve(strict=False)),
            "seed_docs": [
                str(path.resolve(strict=False)) for path in sorted(set(seed_doc_paths))
            ],
        },
        "errors": sorted(set(errors)),
        "ready": not errors,
    }
    return {**core, "content_sha256": _canonical_sha256(core)}


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
    modules, module_errors = _module_vector(root)
    if module_errors:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "loaded Arnold modules escaped the expected root: "
            + ", ".join(module_errors),
        )
    expected_modules = seed.get("loaded_modules")
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
    pth, pth_errors = _pth_vector(root)
    if pth_errors or pth != seed.get("site_pth"):
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "active site .pth vector changed or is unsafe: " + ", ".join(pth_errors),
        )
    wrappers, wrapper_errors = _wrapper_vector(root)
    if wrapper_errors or wrappers != seed.get("wrappers"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "runtime wrapper manifest drifted")
    expected_interpreter = seed.get("interpreter")
    current_interpreter = _interpreter_vector(
        direct_url=(
            provenance.get("direct_url")
            if isinstance(provenance.get("direct_url"), Mapping)
            else {}
        )
    )
    if component in _SUPERVISOR_COMPONENTS:
        supervisor = seed.get("supervisor_receipt")
        supervisor = supervisor if isinstance(supervisor, Mapping) else {}
        runtime = str(supervisor.get("runtime") or "")
        if not runtime or Path(sys.prefix).resolve(strict=False) != Path(
            runtime
        ).resolve(strict=False):
            raise CliError(
                RUNTIME_ATTESTATION_ERROR,
                "supervisor interpreter does not match its prepared runtime",
            )
    elif current_interpreter != expected_interpreter:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR, "runtime interpreter identity drifted"
        )
    paths = seed.get("input_paths")
    paths = paths if isinstance(paths, Mapping) else {}
    manifest_paths = [
        Path(str(paths.get(name) or ""))
        for name in ("supervisor_receipt", "hot_env", "marker", "chain_spec")
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
    if _file_identity(Path(str(paths.get("marker") or ""))) != (
        seed.get("marker") or {}
    ).get("file"):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "cloud marker drifted")
    if _chain_binding(Path(str(paths.get("chain_spec") or ""))) != seed.get(
        "chain_runtime_binding"
    ):
        raise CliError(RUNTIME_ATTESTATION_ERROR, "chain runtime binding drifted")
    return {
        "status": "ready",
        "seed_sha256": seed["content_sha256"],
        "expected_root": str(root),
        "expected_revision": revision,
        "runtime_vector_sha256": runtime_vector_sha256(seed),
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
    return os.environ.get("MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED") == "1"


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
) -> dict[str, Any] | None:
    seed_path = configured_seed_path()
    if seed_path is None:
        if configured_runtime_attestation_required():
            raise CliError(
                RUNTIME_ATTESTATION_ERROR,
                "canonical runtime launch seed is required but missing",
            )
        return None
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
    require_configured_runtime_launch(
        args.component,
        target_pid=args.target_pid,
        create=args.action == "startup",
    )
    print(json.dumps({"success": True, "component": args.component}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
