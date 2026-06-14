"""Verified engine/target write-isolation provider."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from arnold.pipelines.megaplan.runtime.execution_environment import (
    ExecutionEnvironment,
    isolation_cli_error,
)
from arnold.pipelines.megaplan.types import CliError


@dataclass(frozen=True, slots=True)
class EngineIsolationProof:
    provider: str
    trusted_container: bool
    engine_write_denied: bool
    target_write_allowed: bool
    same_user_chmod_accepted: bool
    diagnostic: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def select_provider(env_vars: dict[str, str] | None = None) -> str:
    env_vars = env_vars or os.environ
    explicit = env_vars.get("MEGAPLAN_ENGINE_ISOLATION_PROVIDER", "").strip()
    if explicit in {"local_immutable_probe", "trusted_container_probe"}:
        return explicit
    if env_vars.get("MEGAPLAN_TRUSTED_CONTAINER") in {"1", "true", "TRUE", "yes", "YES"}:
        return "trusted_container_probe"
    return "none"


def validate_trusted_container_by_probe(env: ExecutionEnvironment) -> EngineIsolationProof:
    """Probe that target is writable and engine is not writable."""

    return _validate_by_probe(env, provider="trusted_container_probe", trusted_container=True)


def validate_local_immutable_by_probe(env: ExecutionEnvironment) -> EngineIsolationProof:
    """Probe local filesystem isolation without disabling worker sandboxing."""

    return _validate_by_probe(env, provider="local_immutable_probe", trusted_container=False)


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
    """Fail closed unless a provider proves engine-deny and target-allow."""

    provider = select_provider(env_vars)
    if provider == "trusted_container_probe":
        proof = validate_trusted_container_by_probe(env)
    elif provider == "local_immutable_probe":
        proof = validate_local_immutable_by_probe(env)
    else:
        proof = EngineIsolationProof(
            provider=provider,
            trusted_container=False,
            engine_write_denied=False,
            target_write_allowed=False,
            same_user_chmod_accepted=False,
            diagnostic="same_user_chmod_is_diagnostic_only_not_m0_proof",
        )
    if not (proof.engine_write_denied and proof.target_write_allowed):
        raise isolation_cli_error(
            "engine_write_isolation_unverified",
            "engine write isolation is not verified; same-user chmod is not accepted as M0 proof",
            env=env,
            extra={"phase": phase, "proof": proof.to_dict()},
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
    "validate_trusted_container_by_probe",
]
