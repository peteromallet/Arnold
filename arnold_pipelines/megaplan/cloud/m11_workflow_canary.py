"""Admission and CLI for the honest deployed M11 workflow canary.

The producer and verifier deliberately live in separate modules.  The runner
can create and freeze canonical workflow evidence but cannot author a verdict;
the verifier is read-only over that evidence and alone owns ``verdict.json``.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.cloud.m11_live_canary import (
    CANARY_BASE,
    SCHEMA,
    CanarySafetyError,
    _atomic_json,
    _digest,
    _inside,
    _load_json,
    _load_runtime_json,
    _sha256_file,
    _utc_now,
)


WORKFLOW_CANARY_PREFIX = "m11-workflow-"
ADMISSION_KIND = "deployed_workflow_canary_admission"
REQUIRED_SCENARIOS = (
    "fresh_plan",
    "resume_from_suspension",
    "three_gate_iterations",
    "tiebreaker",
)
_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")


def validate_workflow_canary_root(
    root: str | Path, *, base_root: str | Path = CANARY_BASE
) -> Path:
    base = Path(base_root).resolve(strict=False)
    candidate = Path(root).resolve(strict=False)
    if candidate.parent != base or not candidate.name.startswith(
        WORKFLOW_CANARY_PREFIX
    ):
        raise CanarySafetyError(
            f"workflow canary root must be one direct "
            f"{WORKFLOW_CANARY_PREFIX!r} child of {base}"
        )
    return candidate


def _strict_runtime_binding(
    runtime_path: Path,
    *,
    expected_revision: str,
    deployment_target: str,
    deployment_id: str,
) -> dict[str, Any]:
    runtime = _load_runtime_json(runtime_path)
    components = runtime.get("components")
    required = {
        "interpreter",
        "editable_checkout",
        "pth_files",
        "imports",
        "source_lineage",
        "wrappers",
        "supervisor_command",
        "target_marker",
    }
    if (
        runtime.get("schema")
        != "arnold.megaplan.m11_bound_runtime_identity.v1"
        or runtime.get("valid") is not True
        or runtime.get("strict") is not True
        or runtime.get("expected_revision") != expected_revision
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(runtime.get("content_sha256") or "")
        )
        or not isinstance(components, Mapping)
        or set(components) != required
        or any(
            not isinstance(components[name], Mapping)
            or components[name].get("ok") is not True
            for name in required
        )
        or components["source_lineage"].get("revision") != expected_revision
        or components["source_lineage"].get("expected_revision")
        != expected_revision
        or components["target_marker"].get("fields")
        != {
            "deployment_target": deployment_target,
            "deployment_id": deployment_id,
        }
    ):
        raise CanarySafetyError(
            "workflow canary requires the full strict revision/deployment "
            "runtime tuple"
        )
    return runtime


def admit_deployed_workflow_canary(
    *,
    root: str | Path,
    job_id: str,
    deployment_target: str,
    deployment_id: str,
    expected_revision: str,
    runtime_receipt_path: str | Path,
    base_root: str | Path = CANARY_BASE,
) -> dict[str, Any]:
    """Pin an exact live obligation without claiming executable proof."""

    private_root = validate_workflow_canary_root(root, base_root=base_root)
    private_root.mkdir(parents=True, exist_ok=True)
    if not all(
        value.strip() for value in (job_id, deployment_target, deployment_id)
    ):
        raise CanarySafetyError("job and deployment identities are required")
    if not _REVISION_RE.fullmatch(expected_revision):
        raise CanarySafetyError("expected revision must be a full lowercase git SHA")
    runtime_path = _inside(private_root, runtime_receipt_path, name="runtime receipt")
    runtime = _strict_runtime_binding(
        runtime_path,
        expected_revision=expected_revision,
        deployment_target=deployment_target,
        deployment_id=deployment_id,
    )
    admission = {
        "schema": SCHEMA,
        "kind": ADMISSION_KIND,
        "job_id": job_id,
        "deployment": {
            "target": deployment_target,
            "id": deployment_id,
            "expected_revision": expected_revision,
        },
        "runtime_receipt": {
            "path": str(runtime_path),
            "sha256": _sha256_file(runtime_path),
            "runtime_identity": f"sha256:{runtime['content_sha256']}",
        },
        "required_scenarios": list(REQUIRED_SCENARIOS),
        "admitted_at": _utc_now(),
        "status": "admitted",
    }
    admission["content_sha256"] = _digest(admission)
    _atomic_json(
        private_root / "workflow-canary" / "admission.json",
        admission,
        exclusive=True,
    )
    return admission


def verify_deployed_workflow_canary(
    *,
    root: str | Path,
    base_root: str | Path = CANARY_BASE,
) -> dict[str, Any]:
    """Independently rederive and write the verifier-owned verdict."""

    private_root = validate_workflow_canary_root(root, base_root=base_root)
    from .m11_workflow_canary_verifier import (
        verify_and_write_deployed_workflow_canary,
    )

    return verify_and_write_deployed_workflow_canary(root=private_root)


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    admit = commands.add_parser("admit")
    admit.add_argument("--root", type=Path, required=True)
    admit.add_argument("--config", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--root", type=Path, required=True)
    run.add_argument("--project-dir", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    private_root = validate_workflow_canary_root(args.root)
    if args.command == "admit":
        config = _load_json(_inside(private_root, args.config, name="admission config"))
        payload = admit_deployed_workflow_canary(root=private_root, **config)
        exit_code = 0
    elif args.command == "run":
        from .m11_workflow_canary_runner import run_deployed_workflow_canary

        payload = run_deployed_workflow_canary(
            root=private_root,
            project_dir=args.project_dir.resolve(),
        )
        exit_code = 0
    else:
        payload = verify_deployed_workflow_canary(root=private_root)
        exit_code = 0
    print(json.dumps(payload, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(_main())
