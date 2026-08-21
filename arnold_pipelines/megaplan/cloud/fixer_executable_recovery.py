"""FIXER-EXECUTABLE recovery contract fixtures (T4.2).

Operator item 4 / T3.2 emission: land patch on import_root → expected_head
telemetry update WITHOUT ``advance_generation`` (telemetry only) →
runtime-rebind with milestone identity LABEL ``m7``, never sequence index
``6`` → recover-blocked with ``--repair-commit`` + ``--failure-fingerprint``
+ ``--repair-scope engine_runtime`` + ``--user-approved`` → ``chain start
--one``, all under the seed/import environment.

T4.3 deleted seed/launch-seed/receipt-byte-equality as AUTHORITY. Same
import_root after cutover is a non-event: no rebind, no generation bump.
Live-box recovery is out of scope (SD-009).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch


from arnold_pipelines.megaplan.blocker_recovery import (
    compact_failure_identity,
    validated_deterministic_phase_repair,
)
from arnold_pipelines.megaplan.cloud.current_target_liveness import (
    MutationCapability,
    MutationDenied,
    attach_mutation_capability,
    mint_mutation_capability,
    process_import_root,
    require_mutation_capability,
)
from arnold_pipelines.megaplan.cloud.occurrence_adoption import (
    assert_disposable_root,
    bind_operator_intent,
)
from arnold_pipelines.megaplan.cloud.target_rebind import (
    MILESTONE_LABEL_M7,
    REBIND_ACTION,
    SEQUENCE_INDEX_FORBIDDEN,
    require_milestone_identity_label,
    runtime_rebind,
)
from arnold_pipelines.megaplan.types import CliError

FIXER_CONTRACT = "fixer_executable_recovery_v1"
RECOVER_BLOCKED_ACTION = "recover-blocked"
CHAIN_START_ACTION = "chain_start"
REPAIR_SCOPE = "engine_runtime"
AUTHORITY = "explicit_repair_commit_bound_to_engine_runtime"
SEED_ENV_KEYS = ("PYTHONPATH", "ARNOLD_RUNTIME_MANIFEST")


def seed_import_environment(*, import_root: Path, manifest_path: Path) -> dict[str, str]:
    """Return the seed/import env; ambient megaplan_engine_root is not authority."""

    root = Path(import_root).expanduser().resolve()
    manifest = Path(manifest_path).expanduser().resolve()
    return {
        "PYTHONPATH": str(root),
        "ARNOLD_RUNTIME_MANIFEST": str(manifest),
    }


def require_seed_import_env(env: Mapping[str, str], *, import_root: Path) -> None:
    raw = str(env.get("PYTHONPATH") or "")
    first = raw.split(os.pathsep)[0] if raw else ""
    pythonpath = Path(first).expanduser().resolve() if first else Path()
    if pythonpath != Path(import_root).expanduser().resolve():
        raise MutationDenied(
            "operator recovery commands that admit engine_runtime refuse unless "
            "process import_root equals the manifest tree selector; ambient "
            "megaplan_engine_root() is not authority",
            code="import_root_mismatch",
        )
    if not str(env.get("ARNOLD_RUNTIME_MANIFEST") or "").strip():
        raise MutationDenied(
            "seed/import environment requires ARNOLD_RUNTIME_MANIFEST",
            code="identity_incomplete",
        )


def update_expected_head_telemetry(
    manifest_path: Path,
    new_head: str,
    *,
    binding_root: Path,
) -> dict[str, Any]:
    """Update manifest expected_head as telemetry only. Never advance_generation."""

    assert_disposable_root(binding_root)
    path = Path(manifest_path).expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    epic = payload.setdefault("epic", {})
    previous = str(epic.get("expected_head") or "")
    generation_before = payload.get("generation")
    epic["expected_head"] = new_head
    payload["epic"] = epic
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    generation_after = json.loads(path.read_text(encoding="utf-8")).get("generation")
    if generation_after != generation_before:
        raise CliError(
            "advance_generation_forbidden",
            "expected_head telemetry update must not call advance_generation",
        )
    return {
        "previous_expected_head": previous,
        "expected_head": new_head,
        "generation": generation_after,
        "advance_generation": False,
    }


def recover_blocked_argv(
    *,
    repair_commit: str,
    failure_fingerprint: str,
    repair_scope: str = REPAIR_SCOPE,
    user_approved: bool = True,
    plan: str = "",
    reason: str = "fixer-executable recovery",
) -> list[str]:
    argv = [
        "override",
        "recover-blocked",
        "--repair-commit",
        repair_commit,
        "--failure-fingerprint",
        failure_fingerprint,
        "--repair-scope",
        repair_scope,
        "--reason",
        reason,
    ]
    if plan:
        argv.extend(["--plan", plan])
    if user_approved:
        argv.append("--user-approved")
    return argv


def chain_start_argv(*, spec: str, project_dir: str) -> list[str]:
    return [
        "chain",
        "start",
        "--spec",
        spec,
        "--project-dir",
        project_dir,
        "--one",
    ]


def runtime_rebind_argv(*, milestone: str, spec: str) -> list[str]:
    require_milestone_identity_label(milestone)
    return [
        "chain",
        "runtime-rebind",
        "--spec",
        spec,
        "--expected-current-milestone",
        milestone,
    ]


def execute_fixer_recovery_contract(
    *,
    capability: MutationCapability,
    occurrence: str,
    target: str,
    fence_epoch: int,
    binding_root: Path,
    import_root: Path,
    interpreter: Path,
    manifest_path: Path,
    repair_commit: str,
    failure_fingerprint: str,
    plan_state: Mapping[str, Any],
    resume_cursor: Mapping[str, Any],
    env: Mapping[str, str],
    to_import_root: Path | None = None,
    to_interpreter: Path | None = None,
    process_root: Path | None = None,
    seed_gates_present: bool = False,
) -> dict[str, Any]:
    """Execute the documented fixer verbs against a disposable fixture.

    Does not mutate a live epic. ``seed_gates_present`` is leftover tax
    modeling only. T4.3 production default is False: same-import_root is a
    non-event (no expected_head dance, no content-digest rebind).
    """

    root = assert_disposable_root(binding_root)
    require_seed_import_env(env, import_root=import_root)
    live_process = process_root or process_import_root()
    if Path(live_process).resolve() != Path(import_root).resolve() and str(
        env.get("PYTHONPATH")
    ) != str(Path(import_root).resolve()):
        raise MutationDenied(
            "ambient import_root is not the seed tree",
            code="ambient_engine_root_rejected",
        )
    bind_operator_intent(
        capability,
        action=RECOVER_BLOCKED_ACTION,
        occurrence=occurrence,
        target=target,
        fence_epoch=fence_epoch,
        scope=REPAIR_SCOPE,
    )
    attach_mutation_capability(capability, identity=occurrence)
    require_mutation_capability(
        capability,
        action=RECOVER_BLOCKED_ACTION,
        occurrence=occurrence,
        scope=REPAIR_SCOPE,
    )

    steps: list[str] = ["land_patch_on_import_root"]
    telemetry = None
    rebind_result = None
    if seed_gates_present:
        telemetry = update_expected_head_telemetry(
            manifest_path,
            repair_commit,
            binding_root=root,
        )
        steps.append("expected_head_telemetry_only")
        dest_root = to_import_root or import_root
        dest_python = to_interpreter or interpreter
        rebind_result = runtime_rebind(
            capability=capability,
            occurrence=occurrence,
            target=target,
            fence_epoch=fence_epoch,
            expected_current_milestone=MILESTONE_LABEL_M7,
            binding_root=root,
            from_import_root=str(import_root),
            from_interpreter=str(interpreter),
            to_import_root=str(dest_root),
            to_interpreter=str(dest_python),
            direction="cutover",
            identity={
                "milestone_sequence": [{"index": 0, "label": MILESTONE_LABEL_M7}],
            },
        )
        steps.append("runtime_rebind_with_milestone_label_m7")

    else:
        # Post T4.3: same import_root is a non-event.
        steps.append("same_import_root_non_event")

    cursor = dict(resume_cursor)
    cursor["mutation_capability"] = capability
    cursor["mutation_capability_handle"] = occurrence
    # Seed/import env: PYTHONPATH=<import_root> is the live tree. Ambient
    # process_import_root() from the test interpreter is not authority.
    with patch(
        "arnold_pipelines.megaplan.blocker_recovery.process_import_root",
        create=True,
        return_value=Path(import_root).resolve(),
    ), patch(
        "arnold_pipelines.megaplan.cloud.current_target_liveness.process_import_root",
        return_value=Path(import_root).resolve(),
    ):
        evidence = validated_deterministic_phase_repair(
            Path(import_root),
            dict(plan_state),
            cursor,
            repair_commit,
            failure_fingerprint,
            REPAIR_SCOPE,
        )

    if evidence is None:
        raise CliError(
            "missing_phase_result",
            "fixer recovery requires deterministic_phase_failure / repair_phase_contract",
        )
    if evidence.get("authority") != AUTHORITY:
        raise CliError(
            "authority_mismatch",
            f"recover receipt authority must be {AUTHORITY}",
        )
    steps.append("recover_blocked_with_explicit_repair_commit")
    steps.append("chain_start_one")
    argv = {
        "runtime_rebind": runtime_rebind_argv(
            milestone=MILESTONE_LABEL_M7,
            spec="chain.yaml",
        ),
        "recover_blocked": recover_blocked_argv(
            repair_commit=repair_commit,
            failure_fingerprint=failure_fingerprint,
        ),
        "chain_start": chain_start_argv(spec="chain.yaml", project_dir=str(root)),
    }
    return {
        "contract": FIXER_CONTRACT,
        "automatic": False,
        "authority": AUTHORITY,
        "steps": steps,
        "argv": argv,
        "telemetry": telemetry,
        "rebind": rebind_result,
        "recover_evidence": evidence,
        "env": dict(env),
        "seed_gates_present": seed_gates_present,
    }


def mint_recover_capability(
    *,
    occurrence: str,
    fence_epoch: int,
    import_root: Path,
    interpreter: Path,
    extra: Mapping[str, Any] | None = None,
) -> MutationCapability:
    evidence: dict[str, Any] = {
        "occurrence": occurrence,
        "target": occurrence,
        "cursor": "critique",
        "fence_epoch": fence_epoch,
        "evidence_digest": hashlib.sha256(occurrence.encode()).hexdigest(),
        "scope": REPAIR_SCOPE,
        "repair_scope": REPAIR_SCOPE,
        "custody": {
            "identity": f"custody:{occurrence}",
            "occurrence": occurrence,
            "occurrence_fingerprint": occurrence,
        },
        "import_root": str(import_root),
        "interpreter": str(interpreter),
        "runtime_manifest": {
            "epic": {
                "runtime_root": str(import_root),
                "dependency_generation": {"interpreter_path": str(interpreter)},
            }
        },
    }
    if extra:
        evidence.update(dict(extra))
    return mint_mutation_capability(
        action=RECOVER_BLOCKED_ACTION,
        evidence=evidence,
        process_root=import_root,
        process_python=interpreter,
    )


__all__ = [
    "AUTHORITY",
    "CHAIN_START_ACTION",
    "FIXER_CONTRACT",
    "MILESTONE_LABEL_M7",
    "RECOVER_BLOCKED_ACTION",
    "REPAIR_SCOPE",
    "SEQUENCE_INDEX_FORBIDDEN",
    "chain_start_argv",
    "compact_failure_identity",
    "execute_fixer_recovery_contract",
    "mint_recover_capability",
    "recover_blocked_argv",
    "require_seed_import_env",
    "runtime_rebind_argv",
    "seed_import_environment",
    "update_expected_head_telemetry",
]
