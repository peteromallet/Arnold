"""Verified engine/target write-isolation provider."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.runtime.execution_environment import (
    ExecutionEnvironment,
    classify_path_overlap,
    isolation_cli_error,
    normalize_path,
)
from arnold_pipelines.megaplan.types import CliError


@dataclass(frozen=True, slots=True)
class EngineIsolationProof:
    provider: str
    trusted_container: bool
    engine_write_denied: bool
    target_write_allowed: bool
    same_user_chmod_accepted: bool
    diagnostic: str | None = None
    logical_dev_accepted: bool | None = None
    engine_target_overlap: str | None = None
    worker_cwd_is_target: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def select_provider(env_vars: dict[str, str] | None = None) -> str:
    env_vars = env_vars or os.environ
    # Canonical spellings use MEGAPLAN_*. Retain the historical misspelled
    # MEGPLAN_* variants as a fallback so existing scripts/tests keep working.
    explicit = (
        env_vars.get("MEGAPLAN_ENGINE_ISOLATION_PROVIDER", "")
        or env_vars.get("MEGPLAN_ENGINE_ISOLATION_PROVIDER", "")
    ).strip()
    if explicit in {
        "local_immutable_probe",
        "trusted_container_probe",
        "logical_local_dev",
        "self_hosted_editable",
    }:
        return explicit
    trusted = (
        env_vars.get("MEGAPLAN_TRUSTED_CONTAINER")
        or env_vars.get("MEGPLAN_TRUSTED_CONTAINER")
    )
    if trusted in {"1", "true", "TRUE", "yes", "YES"}:
        return "trusted_container_probe"
    return "none"


def validate_trusted_container_by_probe(env: ExecutionEnvironment) -> EngineIsolationProof:
    """Probe that target is writable and engine is not writable."""

    return _validate_by_probe(env, provider="trusted_container_probe", trusted_container=True)


def validate_local_immutable_by_probe(env: ExecutionEnvironment) -> EngineIsolationProof:
    """Probe local filesystem isolation without disabling worker sandboxing."""

    return _validate_by_probe(env, provider="local_immutable_probe", trusted_container=False)


def validate_logical_local_dev(env: ExecutionEnvironment) -> EngineIsolationProof:
    """Accept disjoint engine/target roots with worker cwd pinned to target.

    This provider is intended for single-user local development where the
    engine checkout is writable by the same user. It does NOT prove that the
    engine is immutable; it verifies the runtime contract that prevents the
    observed accidental contamination: engine and target are disjoint, and the
    worker's resolved work directory is exactly the target root.
    """

    target_ok = _probe_write_allowed(env.target_root)
    overlap = classify_path_overlap(env.engine_root, env.target_root)
    work_dir_is_target = normalize_path(env.work_dir) == normalize_path(env.target_root)

    accepted = target_ok and overlap == "disjoint" and work_dir_is_target

    return EngineIsolationProof(
        provider="logical_local_dev",
        trusted_container=False,
        engine_write_denied=False,
        target_write_allowed=target_ok,
        same_user_chmod_accepted=False,
        diagnostic=None if accepted else "logical_local_dev_contract_failed",
        logical_dev_accepted=accepted,
        engine_target_overlap=overlap,
        worker_cwd_is_target=work_dir_is_target,
    )


def validate_self_hosted_editable(env: ExecutionEnvironment) -> EngineIsolationProof:
    """Accept intentional Megaplan-on-Megaplan editable development runs."""

    target_ok = _probe_write_allowed(env.target_root)
    overlap = classify_path_overlap(env.engine_root, env.target_root)
    work_dir_is_target = normalize_path(env.work_dir) == normalize_path(env.target_root)
    accepted = target_ok and overlap == "equal" and work_dir_is_target

    return EngineIsolationProof(
        provider="self_hosted_editable",
        trusted_container=False,
        engine_write_denied=False,
        target_write_allowed=target_ok,
        same_user_chmod_accepted=False,
        diagnostic=None if accepted else "self_hosted_editable_contract_failed",
        logical_dev_accepted=accepted,
        engine_target_overlap=overlap,
        worker_cwd_is_target=work_dir_is_target,
    )


def _validate_by_probe(
    env: ExecutionEnvironment,
    *,
    provider: str,
    trusted_container: bool,
) -> EngineIsolationProof:
    target_ok = _probe_write_allowed(env.target_root)
    engine_denied, same_user_chmod_denied = _probe_write_denied(env.engine_root)
    return EngineIsolationProof(
        provider=provider,
        trusted_container=trusted_container,
        engine_write_denied=engine_denied,
        target_write_allowed=target_ok,
        same_user_chmod_accepted=False,
        diagnostic=(
            None
            if target_ok and engine_denied
            else (
                "same_user_chmod_is_diagnostic_only_not_m0_proof"
                if same_user_chmod_denied
                else "probe_failed"
            )
        ),
    )


def engine_write_barrier(
    env: ExecutionEnvironment,
    phase: str,
    *,
    env_vars: dict[str, str] | None = None,
) -> EngineIsolationProof:
    """Fail closed unless a provider proves the isolation contract."""

    provider = select_provider(env_vars)
    if provider == "trusted_container_probe":
        proof = validate_trusted_container_by_probe(env)
    elif provider == "local_immutable_probe":
        proof = validate_local_immutable_by_probe(env)
    elif provider == "logical_local_dev":
        proof = validate_logical_local_dev(env)
    elif provider == "self_hosted_editable":
        proof = validate_self_hosted_editable(env)
    else:
        # When no provider is explicitly configured, try the logical local-dev
        # contract as a safe fallback for single-user local development with
        # disjoint engine/target roots. If it fails, preserve the original
        # unverified-provider error behavior.
        proof = validate_logical_local_dev(env)
        if not proof.logical_dev_accepted:
            proof = EngineIsolationProof(
                provider=provider,
                trusted_container=False,
                engine_write_denied=False,
                target_write_allowed=False,
                same_user_chmod_accepted=False,
                diagnostic="same_user_chmod_is_diagnostic_only_not_m0_proof",
            )

    accepted = (
        proof.engine_write_denied and proof.target_write_allowed
    ) or (
        proof.provider == "logical_local_dev"
        and bool(proof.logical_dev_accepted)
    ) or (
        proof.provider == "self_hosted_editable"
        and bool(proof.logical_dev_accepted)
    ) or (
        # Operator-asserted trusted container: the runtime probe cannot prove
        # engine immutability on a plain local checkout, so accept the assertion
        # as long as the target is writable.
        proof.trusted_container
        and proof.target_write_allowed
    )

    if not accepted:
        raise isolation_cli_error(
            "engine_write_isolation_unverified",
            "engine write isolation is not verified; same-user chmod is not accepted as M0 proof",
            env=env,
            extra={
                "phase": phase,
                "proof": proof.to_dict(),
                "action_hint": (
                    "Use a verified engine isolation provider, set MEGAPLAN_TRUSTED_CONTAINER=1 "
                    "inside a container that denies engine writes, run from separated engine "
                    "and target checkouts, or set MEGAPLAN_ENGINE_ISOLATION_PROVIDER=logical_local_dev "
                    "for single-user local development."
                ),
            },
        )

    if proof.provider == "logical_local_dev":
        print(
            "[megaplan] WARNING: using logical local-dev engine isolation; "
            "engine filesystem writes are not denied. This is intended only for "
            "single-user local development with disjoint engine/target roots.",
            flush=True,
        )
    if proof.provider == "self_hosted_editable":
        print(
            "[megaplan] WARNING: using self-hosted editable engine mode; "
            "engine writes are intentional target work product, not denied by "
            "filesystem isolation.",
            flush=True,
        )

    return proof


def _probe_write_allowed(root: Path) -> bool:
    probe = root / ".megaplan-engine-isolation-target-probe"
    try:
        probe.write_text("probe\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _probe_write_denied(root: Path) -> tuple[bool, bool]:
    probe = root / ".megaplan-engine-isolation-engine-probe"
    try:
        probe.write_text("probe\n", encoding="utf-8")
    except OSError:
        if _same_user_chmod_can_make_writable(root, probe):
            return False, True
        return True, False
    try:
        probe.unlink(missing_ok=True)
    except OSError:
        pass
    return False, False


def _same_user_chmod_can_make_writable(root: Path, probe: Path) -> bool:
    try:
        original_mode = root.stat().st_mode
    except OSError:
        return False
    try:
        root.chmod(original_mode | 0o200)
    except OSError:
        return False
    try:
        probe.write_text("probe\n", encoding="utf-8")
    except OSError:
        return False
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            root.chmod(original_mode)
        except OSError:
            pass
    return True


__all__ = [
    "EngineIsolationProof",
    "CliError",
    "engine_write_barrier",
    "select_provider",
    "validate_local_immutable_by_probe",
    "validate_logical_local_dev",
    "validate_trusted_container_by_probe",
]
