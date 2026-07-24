"""Prepare a chain-scoped runtime seed before starting a cloud chain.

The resident hot environment is machine-wide, while chain markers and execution
bindings are session-owned.  A chain must therefore derive its own launch seed
instead of inheriting another session's marker/spec binding.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shlex
import time
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.chain.execution_binding import (
    bind_execution_identity,
    binding_policy,
    execution_binding_report,
)
from arnold_pipelines.megaplan.cloud.runtime_attestation import (
    RUNTIME_ATTESTATION_ERROR,
    _atomic_write,
    build_runtime_launch_seed,
    validate_runtime_launch_seed,
    verify_runtime_launch_seed_document,
)
from arnold_pipelines.megaplan.cloud.runtime_cutover import (
    MARKER_RUNTIME_SCHEMA,
    normalize_runtime_identity,
)
from arnold_pipelines.megaplan.types import CliError


SESSION_RUNTIME_ENV = "runtime-session.env"
SESSION_RUNTIME_SEED = "runtime-launch-seed.json"
SESSION_PROCESS_ATTESTATION = "worker.runtime-process-attestation.json"


def _json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            f"cannot read {label}: {path}",
        ) from exc
    if not isinstance(value, dict):
        raise CliError(RUNTIME_ATTESTATION_ERROR, f"{label} must be a JSON object")
    return value


def _write_session_env(
    path: Path,
    *,
    selectors: Mapping[str, Any],
    runtime_python: Path,
    seed_path: Path,
    process_attestation_path: Path,
) -> None:
    values = {
        str(name): str(value)
        for name, value in selectors.items()
        if str(name).strip() and str(value).strip()
    }
    values.update(
        {
            "MEGAPLAN_RUNTIME_PYTHON": str(runtime_python.resolve(strict=False)),
            "MEGAPLAN_RUNTIME_LAUNCH_SEED": str(seed_path.resolve(strict=False)),
            "MEGAPLAN_RUNTIME_PROCESS_ATTESTATION": str(
                process_attestation_path.resolve(strict=False)
            ),
            "MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED": "1",
        }
    )
    encoded = "".join(
        f"export {name}={shlex.quote(value)}\n"
        for name, value in sorted(values.items())
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(encoded, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _bind_marker_runtime(
    marker_path: Path,
    *,
    spec_path: Path,
    project_dir: Path,
    runtime_identity: Mapping[str, Any],
) -> dict[str, Any]:
    expected = normalize_runtime_identity(runtime_identity)
    lock_path = marker_path.with_suffix(marker_path.suffix + ".runtime-session.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        marker = _json(marker_path, label="cloud session marker")
        marker_workspace = Path(str(marker.get("workspace") or "")).resolve(
            strict=False
        )
        marker_spec = Path(str(marker.get("remote_spec") or "")).resolve(strict=False)
        if marker_workspace != project_dir or marker_spec != spec_path:
            raise CliError(
                RUNTIME_ATTESTATION_ERROR,
                "cloud session marker does not own the requested workspace/spec",
            )
        binding = marker.get("runtime_binding")
        binding = binding if isinstance(binding, Mapping) else {}
        current = binding.get("current_identity")
        current = current if isinstance(current, Mapping) else {}
        if current:
            observed = normalize_runtime_identity(current)
            if observed["content_sha256"] != expected["content_sha256"]:
                raise CliError(
                    RUNTIME_ATTESTATION_ERROR,
                    "cloud session marker belongs to a different runtime",
                )
            return marker
        bound_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        marker["runtime_binding"] = {
            "schema": MARKER_RUNTIME_SCHEMA,
            "current_identity": expected,
            "last_rebound_at": bound_at,
            "rebind_events": [],
        }
        marker["editable_source_head"] = expected["source_revision"]
        marker["updated_at"] = bound_at
        _atomic_write(marker_path, marker)
        return marker


def _prepared_runtime_identity(report: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact runtime identity admitted by execution binding.

    ``driver.execution_binding=required`` does not imply that editable runtime
    matching is required.  In that legitimate policy shape the outer
    execution binding must still match, while ``runtime_binding_report``
    returns ``not_required`` by design.  Treat only that explicit
    ``required=False`` result as admitted; real drift/missing/invalid results
    remain fail-closed.
    """

    if report.get("status") != "match":
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "chain execution binding was not ready after preparation",
        )
    runtime_report = report.get("runtime_binding")
    runtime_report = (
        runtime_report if isinstance(runtime_report, Mapping) else {}
    )
    runtime_status = runtime_report.get("status")
    runtime_required = runtime_report.get("required")
    admitted = runtime_status == "match" or (
        runtime_status == "not_required" and runtime_required is False
    )
    expected = runtime_report.get("expected")
    active = runtime_report.get("active")
    if (
        not admitted
        or not isinstance(expected, Mapping)
        or not expected
        or not isinstance(active, Mapping)
        or not active
    ):
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "chain runtime binding was not ready after preparation",
        )
    normalized_expected = normalize_runtime_identity(expected)
    normalized_active = normalize_runtime_identity(active)
    if (
        normalized_expected["content_sha256"]
        != normalized_active["content_sha256"]
    ):
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "chain runtime identity drifted during preparation",
        )
    return normalized_expected


def prepare_session_runtime(
    *,
    marker_path: Path,
    spec_path: Path,
    project_dir: Path,
    base_seed_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Bind a fresh chain and derive an exact marker/spec-scoped launch seed."""

    marker_path = marker_path.resolve(strict=False)
    spec_path = spec_path.resolve(strict=False)
    project_dir = project_dir.resolve(strict=False)
    base_seed_path = base_seed_path.resolve(strict=False)
    output_dir = output_dir.resolve(strict=False)

    base_seed = _json(base_seed_path, label="base runtime launch seed")
    # The machine-wide seed authenticates the release, but its marker/spec are
    # owned by the session that promoted it.  Do not require those foreign,
    # mutable inputs to remain current when deriving this session's seed.
    verify_runtime_launch_seed_document(base_seed)
    if not binding_policy(spec_path)["required"]:
        raise CliError(
            RUNTIME_ATTESTATION_ERROR,
            "attested cloud launch requires driver.execution_binding=required",
        )

    state = chain_spec.load_chain_state(spec_path, verify_execution_binding=False)
    bind_execution_identity(spec_path, state)
    chain_spec.save_chain_state(spec_path, state)
    report = execution_binding_report(spec_path, state)
    runtime_identity = _prepared_runtime_identity(report)
    _bind_marker_runtime(
        marker_path,
        spec_path=spec_path,
        project_dir=project_dir,
        runtime_identity=runtime_identity,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    env_path = output_dir / SESSION_RUNTIME_ENV
    seed_path = output_dir / SESSION_RUNTIME_SEED
    process_path = output_dir / SESSION_PROCESS_ATTESTATION
    selectors = (base_seed.get("hot_env") or {}).get("selectors") or {}
    _write_session_env(
        env_path,
        selectors=selectors,
        runtime_python=Path(os.sys.executable),
        seed_path=seed_path,
        process_attestation_path=process_path,
    )
    input_paths = base_seed.get("input_paths")
    input_paths = input_paths if isinstance(input_paths, Mapping) else {}
    seed = build_runtime_launch_seed(
        expected_root=Path(str(base_seed.get("expected_root") or "")),
        expected_revision=str(base_seed.get("expected_revision") or ""),
        supervisor_receipt_path=Path(str(input_paths.get("supervisor_receipt") or "")),
        hot_env_path=env_path,
        marker_path=marker_path,
        chain_spec_path=spec_path,
    )
    _atomic_write(seed_path, seed)
    validate_runtime_launch_seed(seed, component="worker")
    return {
        "success": True,
        "session_env": str(env_path),
        "session_seed": str(seed_path),
        "runtime_revision": seed["expected_revision"],
        "runtime_root": seed["expected_root"],
        "chain_spec": str(spec_path),
        "marker": str(marker_path),
        "seed_sha256": seed["content_sha256"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--base-seed", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare_session_runtime(
            marker_path=args.marker,
            spec_path=args.spec,
            project_dir=args.project_dir,
            base_seed_path=args.base_seed,
            output_dir=args.output_dir,
        )
    except CliError as exc:
        print(json.dumps({"success": False, "error": exc.code, "message": exc.message}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
