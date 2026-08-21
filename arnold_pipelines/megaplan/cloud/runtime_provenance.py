"""Fail-closed provenance check for editable Megaplan runtimes."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import unquote, urlparse


RUNTIME_PROVENANCE_RECEIPT_SCHEMA = "arnold.megaplan.runtime_provenance_receipt.v1"

# Rollback receipt emitted by ``runtime_manifest cutover`` (T-0101d): captures
# the pre-cutover manifest SHA-256 + FULL old field set so an operator can
# re-assert the previous runtime after a failed cutover. Independent from the
# (weaker) supervisor-runtime ``last-prepare.json`` receipt.
RUNTIME_MANIFEST_CUTOVER_ROLLBACK_SCHEMA = (
    "arnold.megaplan.runtime_manifest_cutover_rollback.v1"
)
_RUNTIME_IDENTITY_KEYS = (
    "import_root",
    "source_revision",
    "editable_root",
    "editable_revision",
    "direct_url",
    "pth",
    "imports",
)


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


def _git_revision(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_is_clean(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and not result.stdout.strip()


def _safe_path_enabled() -> bool:
    return bool(getattr(sys.flags, "safe_path", False))


def _distribution() -> importlib.metadata.Distribution | None:
    try:
        return importlib.metadata.distribution("arnold")
    except importlib.metadata.PackageNotFoundError:
        return None


def _direct_url_identity() -> tuple[Path | None, dict[str, Any]]:
    distribution = _distribution()
    if distribution is None:
        return None, {}
    try:
        direct_url = distribution.read_text("direct_url.json")
        payload = json.loads(direct_url or "{}")
    except (json.JSONDecodeError, OSError):
        return None, {}
    if not bool((payload.get("dir_info") or {}).get("editable")):
        return None, payload
    parsed = urlparse(str(payload.get("url") or ""))
    if parsed.scheme != "file":
        return None, payload
    return Path(unquote(parsed.path)).resolve(), payload


def _editable_root() -> Path | None:
    root, _payload = _direct_url_identity()
    return root


def _pth_identity() -> list[dict[str, Any]]:
    """Return path-bearing ``.pth`` entries owned by the Arnold distribution."""

    distribution = _distribution()
    if distribution is None:
        return []
    records: list[dict[str, Any]] = []
    for relative in distribution.files or ():
        if not str(relative).endswith(".pth"):
            continue
        path = Path(distribution.locate_file(relative)).resolve(strict=False)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            records.append({"path": str(path), "entries": [], "readable": False})
            continue
        entries: list[str] = []
        for raw in lines:
            value = raw.strip()
            if not value or value.startswith(("#", "import ")):
                continue
            candidate = Path(value).expanduser()
            if not candidate.is_absolute():
                candidate = path.parent / candidate
            entries.append(str(candidate.resolve(strict=False)))
        records.append(
            {
                "path": str(path),
                "sha256": _sha256_file(path),
                "entries": entries,
                "readable": True,
            }
        )
    return records


def runtime_provenance(
    *,
    expected_root: Path | None = None,
    expected_revision: str = "",
) -> dict[str, Any]:
    import arnold
    import arnold_pipelines

    import_root = Path(arnold_pipelines.__file__).resolve().parents[1]
    megaplan_init = import_root / "arnold_pipelines" / "megaplan" / "__init__.py"
    editable_root, direct_url = _direct_url_identity()
    pth = _pth_identity()
    source_revision = _git_revision(import_root)
    expected = expected_root.resolve() if expected_root is not None else None
    imports = {
        "arnold": str(Path(arnold.__file__).resolve()),
        "arnold_pipelines": str(Path(arnold_pipelines.__file__).resolve()),
        # Provenance must remain inspectable for an independently receipted
        # rollback checkout even when importing that older package would run
        # incompatible registration side effects.
        "megaplan": str(megaplan_init.resolve()),
    }
    errors: list[str] = []
    if expected is not None and import_root != expected:
        errors.append("import_root_mismatch")
    # T-0301 generation: no pip editable install exists (worktree-first
    # PYTHONPATH). `editable_root` is only meaningful when a direct-url
    # editable distribution is actually present; otherwise the import-root
    # check above is the authoritative provenance gate.
    if (
        expected is not None
        and editable_root is not None
        and editable_root != expected
    ):
        errors.append("editable_metadata_mismatch")
    if expected is not None:
        mismatched_imports = [
            name
            for name, value in imports.items()
            if not Path(value).is_relative_to(expected)
        ]
        if mismatched_imports:
            errors.append("module_import_root_mismatch")
        pth_entries = [
            entry
            for record in pth
            for entry in record.get("entries", [])
            if isinstance(entry, str)
        ]
        # T-0301 generation: the executing runtime is a worktree-first
        # PYTHONPATH root, not a pip editable install. When imports already
        # resolve to the expected root, the legacy .pth requirement does not
        # apply. A .pth that DOES exist must still point at the expected root.
        imports_match = not mismatched_imports
        if not imports_match and (not pth or not pth_entries):
            errors.append("editable_pth_missing")
        elif pth_entries and any(
            Path(entry).resolve(strict=False) != expected for entry in pth_entries
        ):
            errors.append("editable_pth_mismatch")
        if any(not bool(record.get("readable")) for record in pth):
            errors.append("editable_pth_unreadable")
    # G4-001: Git SHA is telemetry, not launch authority. Live Tree Authority
    # is import_root + generation interpreter. A same-import_root commit after
    # cutover must not fail-close provenance. Record source_revision_mismatch
    # as an observation only; never append it to errors.
    revision_mismatch = bool(expected_revision and source_revision != expected_revision)
    return {
        "ok": not errors,
        "errors": errors,
        "expected_root": str(expected) if expected is not None else "",
        "expected_revision": expected_revision,
        "import_root": str(import_root),
        "editable_root": str(editable_root) if editable_root is not None else "",
        "direct_url": direct_url,
        "pth": pth,
        "source_revision": source_revision,
        "runtime_revision": source_revision,
        "imports": imports,
        "source_revision_mismatch": revision_mismatch,
    }


def normalized_runtime_identity(provenance: Mapping[str, Any]) -> dict[str, Any]:
    """Project strict provenance into the content-addressed runtime identity."""

    identity = {key: provenance.get(key) for key in _RUNTIME_IDENTITY_KEYS}
    # T-0301 worktree-first runtime has no pip editable install, so
    # editable_revision must stay EMPTY (matching active_execution_identity,
    # which derives it from the editable root only). Falling back to
    # source_revision here made the seed identity disagree with the chain
    # binding identity and broke ensure_runtime_launch_seed's equality check.
    #
    # For an EDITABLE-installed runtime, active_execution_identity derives
    # editable_revision from the editable root's git revision; mirror that
    # exactly so the launch-seed live identity equals the chain-bound
    # identity (runtime_provenance() itself does not emit editable_revision,
    # so fall back to the editable root's git revision when one exists).
    editable_root_text = str(provenance.get("editable_root") or "")
    identity["editable_revision"] = str(provenance.get("editable_revision") or "")
    if not identity["editable_revision"] and editable_root_text:
        identity["editable_revision"] = _git_revision(
            Path(editable_root_text).expanduser()
        )
    identity["content_sha256"] = _canonical_sha256(_identity_digest_core(identity))
    return identity


def _identity_digest_core(identity: Mapping[str, Any]) -> dict[str, Any]:
    """Env-independent identity digest (grok consult, occurrence d58701026410).

    editable_root / editable_revision / direct_url / pth / imports all derive
    from the probing interpreter's view (importlib.metadata dist-info,
    resolved module paths) and drift between the generation-interpreter launch
    recipe and a leftover candidate .venv. An identity pin that changes with
    the probing interpreter is not an identity. The launch-relevant identity
    is import_root + source_revision — the only fields determined by the tree
    itself.
    """
    core = {key: identity.get(key) for key in _RUNTIME_IDENTITY_KEYS}
    for key in ("editable_root", "editable_revision", "direct_url", "pth", "imports"):
        core[key] = None
    return core


def runtime_provenance_receipt(provenance: Mapping[str, Any]) -> dict[str, Any]:
    """Bind one runtime observation to the interpreter that made it."""

    executable = Path(sys.executable).resolve(strict=True)
    core = {
        "schema": RUNTIME_PROVENANCE_RECEIPT_SCHEMA,
        "interpreter": {
            "executable": str(executable),
            "sha256": _sha256_file(executable),
            "prefix": str(Path(sys.prefix).resolve(strict=True)),
            "base_prefix": str(Path(sys.base_prefix).resolve(strict=True)),
        },
        "provenance": dict(provenance),
        "runtime_identity": normalized_runtime_identity(provenance),
    }
    return {**core, "content_sha256": _canonical_sha256(core)}


M11_BOUND_IDENTITY_SCHEMA = "arnold.megaplan.m11_bound_runtime_identity.v1"

_M11_IDENTITY_COMPONENTS = (
    "interpreter",
    "editable_checkout",
    "pth_files",
    "imports",
    "source_lineage",
    "wrappers",
    "supervisor_command",
    "target_marker",
)


def m11_bound_runtime_identity(
    *,
    expected_root: Path | None = None,
    expected_revision: str = "",
    expected_interpreter: Path | None = None,
    expected_interpreter_sha256: str = "",
    expected_pth_hashes: Mapping[str, str] | None = None,
    expected_import_paths: Mapping[str, str] | None = None,
    supervisor_python: Path | None = None,
    supervisor_argv: Sequence[str] | None = None,
    expected_supervisor_argv: Sequence[str] | None = None,
    wrapper_dir: Path | None = None,
    expected_wrapper_hashes: Mapping[str, str] | None = None,
    target_marker_path: Path | None = None,
    expected_target_marker_sha256: str = "",
    expected_target_fields: Mapping[str, Any] | None = None,
    require_clean_checkout: bool = False,
    require_safe_path: bool = False,
    strict: bool = False,
) -> dict[str, Any]:
    """Validate bound runtime identity for M11 acceptance joins.

    Validates all eight runtime identity components at init/resume:
    interpreter, editable checkout, .pth files, imports, source lineage,
    wrappers, supervisor command, and target marker.

    Returns a content-addressed identity receipt with per-component
    ``ok`` flags and ``errors`` lists.  An identity is ``valid`` only
    when every component is ``ok`` — a single stale component makes the
    whole identity invalid for M11 acceptance.
    """
    errors: list[str] = []
    components: dict[str, dict[str, Any]] = {}
    expected = expected_root.resolve() if expected_root is not None else None

    if strict:
        missing = []
        for name, value in (
            ("expected_root", expected_root),
            ("expected_revision", expected_revision),
            ("expected_interpreter", expected_interpreter),
            ("expected_interpreter_sha256", expected_interpreter_sha256),
            ("expected_pth_hashes", expected_pth_hashes),
            ("expected_import_paths", expected_import_paths),
            ("expected_wrapper_hashes", expected_wrapper_hashes),
            ("supervisor_argv", supervisor_argv),
            ("expected_supervisor_argv", expected_supervisor_argv),
            ("target_marker_path", target_marker_path),
            ("expected_target_marker_sha256", expected_target_marker_sha256),
            ("expected_target_fields", expected_target_fields),
        ):
            if value is None or value == "" or value == {} or value == ():
                missing.append(name)
        if missing:
            errors.append("strict_expectations_missing:" + ",".join(missing))
        require_clean_checkout = True
        require_safe_path = True

    # --- 1. Interpreter ----------------------------------------------------
    executable = Path(sys.executable).resolve(strict=True)
    prefix = Path(sys.prefix).resolve(strict=True)
    base_prefix = Path(sys.base_prefix).resolve(strict=True)
    interpreter_ok = True
    interpreter_errors: list[str] = []
    if not executable.exists():
        interpreter_ok = False
        interpreter_errors.append("interpreter_executable_missing")
    executable_sha256 = _sha256_file(executable) if executable.exists() else ""
    if expected_interpreter is not None:
        expected_executable = expected_interpreter.resolve(strict=False)
        if executable != expected_executable:
            interpreter_ok = False
            interpreter_errors.append("interpreter_path_mismatch")
    if expected_interpreter_sha256 and executable_sha256 != expected_interpreter_sha256:
        interpreter_ok = False
        interpreter_errors.append("interpreter_sha256_mismatch")
    safe_path = _safe_path_enabled()
    if require_safe_path and not safe_path:
        interpreter_ok = False
        interpreter_errors.append("python_safe_path_disabled")
    components["interpreter"] = {
        "executable": str(executable),
        "sha256": executable_sha256,
        "expected_executable": (
            str(expected_interpreter.resolve(strict=False))
            if expected_interpreter is not None
            else ""
        ),
        "expected_sha256": expected_interpreter_sha256,
        "prefix": str(prefix),
        "base_prefix": str(base_prefix),
        "venv": str(prefix) if prefix != base_prefix else "",
        "safe_path": safe_path,
        "ok": interpreter_ok,
        "errors": interpreter_errors,
    }
    if not interpreter_ok:
        errors.append("interpreter_invalid")

    # --- 2. Editable checkout ----------------------------------------------
    editable_root, direct_url = _direct_url_identity()
    editable_ok = True
    editable_errors: list[str] = []
    if editable_root is None:
        editable_ok = False
        editable_errors.append("not_editable_install")
    elif expected is not None:
        import arnold_pipelines as _ap

        actual_import_root = Path(_ap.__file__).resolve().parents[1]
        if strict and editable_root != expected:
            editable_ok = False
            editable_errors.append("editable_root_mismatch")
        elif not strict and editable_root != expected and actual_import_root != expected:
            editable_ok = False
            editable_errors.append("editable_root_mismatch")
    components["editable_checkout"] = {
        "root": str(editable_root) if editable_root is not None else "",
        "direct_url": direct_url,
        "ok": editable_ok,
        "errors": editable_errors,
    }
    if not editable_ok:
        errors.append("editable_checkout_invalid")

    # --- 3. .pth files -----------------------------------------------------
    pth = _pth_identity()
    pth_ok = True
    pth_errors: list[str] = []
    if not pth:
        pth_ok = False
        pth_errors.append("no_pth_entries")
    else:
        for record in pth:
            if not record.get("readable"):
                pth_ok = False
                pth_errors.append(f"pth_unreadable:{record.get('path')}")
        # Verify pth entries point to valid directories (existence check)
        # rather than requiring exact path matches, because editable installs
        # may record metadata paths that differ from the actual import root.
        if pth_ok:
            pth_entries = [
                entry
                for record in pth
                for entry in record.get("entries", [])
                if isinstance(entry, str)
            ]
            if not pth_entries:
                pth_ok = False
                pth_errors.append("pth_no_path_entries")
            elif not any(
                Path(entry).resolve(strict=False).is_dir()
                for entry in pth_entries
            ):
                pth_ok = False
                pth_errors.append("pth_entry_dirs_missing")
    observed_pth_hashes = {
        str(Path(str(record.get("path") or "")).resolve(strict=False)): str(
            record.get("sha256") or ""
        )
        for record in pth
    }
    if expected is not None and (strict or expected_pth_hashes is not None):
        for record in pth:
            for entry in record.get("entries", []):
                if Path(str(entry)).resolve(strict=False) != expected:
                    pth_ok = False
                    pth_errors.append(f"pth_entry_root_mismatch:{entry}")
    if expected_pth_hashes is not None:
        normalized_expected_pth = {
            str(Path(path).resolve(strict=False)): digest
            for path, digest in expected_pth_hashes.items()
        }
        if observed_pth_hashes != normalized_expected_pth:
            pth_ok = False
            pth_errors.append("pth_set_or_hash_mismatch")
    components["pth_files"] = {
        "records": pth,
        "observed_hashes": observed_pth_hashes,
        "expected_hashes": dict(expected_pth_hashes or {}),
        "ok": pth_ok,
        "errors": pth_errors,
    }
    if not pth_ok:
        errors.append("pth_files_invalid")

    # --- 4. Imports --------------------------------------------------------
    import arnold
    import arnold_pipelines

    imports_ok = True
    imports_errors: list[str] = []
    import_map = {
        "arnold": str(Path(arnold.__file__).resolve()),
        "arnold_pipelines": str(Path(arnold_pipelines.__file__).resolve()),
        "megaplan": str(
            (
                Path(arnold_pipelines.__file__).resolve().parents[1]
                / "arnold_pipelines"
                / "megaplan"
                / "__init__.py"
            ).resolve()
        ),
    }
    actual_import_root = Path(arnold_pipelines.__file__).resolve().parents[1]
    for name, path_str in import_map.items():
        if not Path(path_str).is_relative_to(actual_import_root):
            imports_ok = False
            imports_errors.append(f"import_not_relative_to_import_root:{name}")
    # Also check against expected_root when it differs (cross-check)
    if expected is not None:
        if expected != actual_import_root:
            for name, path_str in import_map.items():
                if not Path(path_str).is_relative_to(expected):
                    imports_ok = False
                    imports_errors.append(f"import_not_relative_to_expected_root:{name}")
    if expected_import_paths is not None:
        normalized_expected_imports = {
            name: str(Path(path).resolve(strict=False))
            for name, path in expected_import_paths.items()
        }
        if import_map != normalized_expected_imports:
            imports_ok = False
            imports_errors.append("import_path_map_mismatch")
    components["imports"] = {
        "paths": import_map,
        "expected_paths": dict(expected_import_paths or {}),
        "ok": imports_ok,
        "errors": imports_errors,
    }
    if not imports_ok:
        errors.append("imports_invalid")

    # --- 5. Source lineage -------------------------------------------------
    import_root = Path(arnold_pipelines.__file__).resolve().parents[1]
    source_revision = _git_revision(import_root)
    source_ok = True
    source_errors: list[str] = []
    if not source_revision:
        source_ok = False
        source_errors.append("no_git_revision")
    elif expected_revision and source_revision != expected_revision:
        source_ok = False
        source_errors.append("revision_mismatch")
    source_clean = _git_is_clean(import_root)
    if require_clean_checkout and not source_clean:
        source_ok = False
        source_errors.append("source_checkout_dirty")
    components["source_lineage"] = {
        "import_root": str(import_root),
        "revision": source_revision,
        "expected_revision": expected_revision,
        "clean": source_clean,
        "ok": source_ok,
        "errors": source_errors,
    }
    if not source_ok:
        errors.append("source_lineage_invalid")

    # --- 6. Wrappers -------------------------------------------------------
    wrappers_ok = True
    wrappers_errors: list[str] = []
    wrapper_entries: list[dict[str, Any]] = []
    if wrapper_dir is not None and wrapper_dir.is_dir():
        for path in sorted(wrapper_dir.glob("arnold-*")):
            if path.is_file():
                try:
                    sha = _sha256_file(path)
                except OSError:
                    sha = ""
                    wrappers_ok = False
                    wrappers_errors.append(f"wrapper_unreadable:{path.name}")
                wrapper_entries.append({
                    "name": path.name,
                    "path": str(path),
                    "sha256": sha,
                    "executable": os.access(path, os.X_OK),
                })
        if not wrapper_entries:
            wrappers_ok = False
            wrappers_errors.append("no_wrappers_found")
    else:
        wrappers_ok = False
        wrappers_errors.append("wrapper_dir_not_configured")
    observed_wrapper_hashes = {
        entry["path"]: entry["sha256"] for entry in wrapper_entries
    }
    if expected_wrapper_hashes is not None:
        normalized_expected_wrappers = {
            str(Path(path).resolve(strict=False)): digest
            for path, digest in expected_wrapper_hashes.items()
        }
        if observed_wrapper_hashes != normalized_expected_wrappers:
            wrappers_ok = False
            wrappers_errors.append("wrapper_set_or_hash_mismatch")
        if any(not bool(entry["executable"]) for entry in wrapper_entries):
            wrappers_ok = False
            wrappers_errors.append("wrapper_not_executable")
    components["wrappers"] = {
        "entries": wrapper_entries,
        "wrapper_dir": str(wrapper_dir) if wrapper_dir is not None else "",
        "observed_hashes": observed_wrapper_hashes,
        "expected_hashes": dict(expected_wrapper_hashes or {}),
        "ok": wrappers_ok,
        "errors": wrappers_errors,
    }
    if not wrappers_ok:
        errors.append("wrappers_invalid")

    # --- 7. Supervisor command ---------------------------------------------
    supervisor_ok = True
    supervisor_errors: list[str] = []
    supervisor_info: dict[str, Any] = {
        "python": "",
        "exists": False,
        "sha256": "",
        "argv": list(supervisor_argv or ()),
        "expected_argv": list(expected_supervisor_argv or ()),
    }
    if supervisor_python is not None:
        sp = supervisor_python.resolve(strict=False)
        supervisor_info["python"] = str(sp)
        if sp.exists():
            supervisor_info["exists"] = True
            supervisor_info["sha256"] = _sha256_file(sp)
        else:
            supervisor_ok = False
            supervisor_errors.append("supervisor_python_missing")
    else:
        supervisor_ok = False
        supervisor_errors.append("supervisor_python_not_configured")
    if expected_supervisor_argv is not None:
        if tuple(supervisor_argv or ()) != tuple(expected_supervisor_argv):
            supervisor_ok = False
            supervisor_errors.append("supervisor_argv_mismatch")
    if supervisor_python is not None and supervisor_argv:
        argv_python = Path(supervisor_argv[0]).resolve(strict=False)
        if argv_python != supervisor_python.resolve(strict=False):
            supervisor_ok = False
            supervisor_errors.append("supervisor_argv_python_mismatch")
    components["supervisor_command"] = {
        **supervisor_info,
        "ok": supervisor_ok,
        "errors": supervisor_errors,
    }
    if not supervisor_ok:
        errors.append("supervisor_command_invalid")

    # --- 8. Target marker --------------------------------------------------
    target_ok = True
    target_errors: list[str] = []
    target_info: dict[str, Any] = {
        "path": "",
        "exists": False,
        "sha256": "",
        "fields": {},
    }
    if target_marker_path is not None:
        tmp = target_marker_path.resolve(strict=False)
        target_info["path"] = str(tmp)
        if tmp.is_file():
            target_info["exists"] = True
            try:
                target_info["sha256"] = _sha256_file(tmp)
                payload = json.loads(tmp.read_text(encoding="utf-8"))
                parsed_fields = (
                    payload if isinstance(payload, dict) else {"_value": payload}
                )
                target_info["fields"] = (
                    {
                        key: parsed_fields.get(key)
                        for key in (expected_target_fields or {})
                    }
                    if strict
                    else parsed_fields
                )
            except (OSError, json.JSONDecodeError):
                target_ok = False
                target_errors.append("target_marker_unreadable_or_invalid_json")
        else:
            target_ok = False
            target_errors.append("target_marker_missing")
    else:
        target_ok = False
        target_errors.append("target_marker_not_configured")
    if (
        expected_target_marker_sha256
        and target_info["sha256"] != expected_target_marker_sha256
    ):
        target_ok = False
        target_errors.append("target_marker_sha256_mismatch")
    for key, expected_value in (expected_target_fields or {}).items():
        if target_info["fields"].get(key) != expected_value:
            target_ok = False
            target_errors.append(f"target_marker_field_mismatch:{key}")
    components["target_marker"] = {
        **target_info,
        "ok": target_ok,
        "errors": target_errors,
    }
    if not target_ok:
        errors.append("target_marker_invalid")

    # --- Assemble identity -------------------------------------------------
    identity_core = {
        "strict": strict,
        "expected_root": str(expected) if expected is not None else "",
        "expected_revision": expected_revision,
        "components": components,
        "component_names": list(_M11_IDENTITY_COMPONENTS),
    }
    valid = not errors
    result: dict[str, Any] = {
        "schema": M11_BOUND_IDENTITY_SCHEMA,
        "valid": valid,
        "errors": errors,
        **identity_core,
    }
    result["content_sha256"] = _canonical_sha256(result)
    return result


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = path.resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _write_receipt_durably(receipt_path: Path, receipt: Mapping[str, Any]) -> None:
    """Atomically create *receipt_path* with hardened durability semantics.

    Mirrors the occurrence-join receipt write (T-0101h round-5 blocker 3):
    the payload goes to an UNPREDICTABLE sibling temp name
    (``.<name>.<random-hex>.tmp``) opened with
    ``O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW`` — a pre-seeded symlink at the temp
    name can never be followed into protected state (a collision fails closed
    with ``EEXIST`` instead of writing through the link) — the file is
    ``os.fsync``-ed BEFORE ``os.replace`` to the final path, and the parent
    directory is ``os.fsync``-ed AFTER the rename, so the receipt is durable
    across power loss.  ``os.replace`` replaces the final directory entry
    itself, so a pre-seeded symlink AT the receipt path is replaced, never
    followed: the receipt lands at the literal path and whatever the link
    pointed at is untouched.  The final path is deliberately NOT resolved
    first (resolving would follow a pre-seeded link into its target).
    """
    parent = receipt_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp = parent / f".{receipt_path.name}.{uuid.uuid4().hex}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, receipt_path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    dir_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def emit_runtime_manifest_cutover_rollback_receipt(
    receipt_path: Path,
    *,
    manifest_path: Path,
    manifest_before_sha256: str,
    manifest_after_sha256: str,
    generation_before: int,
    generation_after: int,
    from_runtime_root: str,
    from_expected_head: str,
    to_runtime_root: str,
    to_expected_head: str,
    to_venv_path: str,
    to_repair_bin: str,
    previous_manifest: Mapping[str, Any],
    runtime_identity_sha256: str,
    actor: str,
    reason: str,
    at: str | None = None,
) -> dict[str, Any]:
    """Atomically write a ``runtime_manifest cutover`` rollback receipt.

    The receipt binds the pre-cutover manifest (old file SHA-256 + FULL old
    field set in ``previous_manifest``) with the to-values and a
    ``content_sha256`` self-digest, so a rollback can re-assert the exact
    previous bytes. Returns the written payload.
    """
    core = {
        "schema": RUNTIME_MANIFEST_CUTOVER_ROLLBACK_SCHEMA,
        "at": at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "actor": actor,
        "reason": reason,
        "manifest_path": str(manifest_path),
        "manifest_before_sha256": manifest_before_sha256,
        "manifest_after_sha256": manifest_after_sha256,
        "generation_before": generation_before,
        "generation_after": generation_after,
        "from": {
            "runtime_root": from_runtime_root,
            "expected_head": from_expected_head,
        },
        "to": {
            "runtime_root": to_runtime_root,
            "expected_head": to_expected_head,
            "venv_path": to_venv_path,
            "repair_bin": to_repair_bin,
        },
        "runtime_identity_sha256": runtime_identity_sha256,
        "previous_manifest": dict(previous_manifest),
    }
    receipt = {**core, "content_sha256": _canonical_sha256(core)}
    _write_receipt_durably(receipt_path, receipt)
    return receipt


def verify_runtime_manifest_cutover_rollback_receipt(
    path: Path,
    *,
    expected_manifest_before_sha256: str = "",
) -> dict[str, Any]:
    """Validate a ``runtime_manifest cutover`` rollback receipt on disk.

    Raises :class:`ValueError` on any mismatch: unreadable/invalid JSON,
    non-object payload, schema mismatch, or a ``content_sha256`` that does not
    cover the payload. When *expected_manifest_before_sha256* is given it must
    equal the recorded pre-cutover manifest SHA-256. Returns the receipt
    payload on success.
    """
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"rollback receipt is unreadable or invalid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("rollback receipt must be a JSON object")
    if payload.get("schema") != RUNTIME_MANIFEST_CUTOVER_ROLLBACK_SCHEMA:
        raise ValueError(
            f"rollback receipt schema mismatch: {payload.get('schema')!r}"
        )
    digest = str(payload.get("content_sha256") or "")
    core = {key: payload[key] for key in payload if key != "content_sha256"}
    if not digest or _canonical_sha256(core) != digest:
        raise ValueError("rollback receipt digest is invalid")
    expected = expected_manifest_before_sha256.strip()
    if expected and str(payload.get("manifest_before_sha256") or "") != expected:
        raise ValueError(
            "rollback receipt does not match the expected pre-cutover "
            "manifest SHA-256"
        )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-root", type=Path)
    parser.add_argument("--expected-revision", default="")
    parser.add_argument("--emit-receipt", action="store_true")
    parser.add_argument("--receipt-out", type=Path)
    parser.add_argument("--identity-out", type=Path)
    args = parser.parse_args(argv)
    payload = runtime_provenance(
        expected_root=args.expected_root,
        expected_revision=args.expected_revision,
    )
    receipt = runtime_provenance_receipt(payload)
    if args.receipt_out is not None:
        _atomic_write_json(args.receipt_out, receipt)
    if args.identity_out is not None:
        _atomic_write_json(args.identity_out, receipt["runtime_identity"])
    print(json.dumps(receipt if args.emit_receipt else payload, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
