"""Megaplan-owned adapters for Step IO policy compatibility."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.step_io_contract import StepIOEnvelope
from arnold.pipeline.step_io_policy import (
    CONTRACT_MODE_ENFORCE,
    CONTRACT_MODE_OFF,
    CONTRACT_MODE_SHADOW,
    CONTRACT_MODE_WARN,
    SELF_VALIDATION_KEY,
    STEP_IO_POLICY_DIRNAME,
    STEP_IO_POLICY_FILENAME,
    StepIOPolicy,
    is_step_io_enforcement_eligible,
    normalize_contract_mode,
)

STEP_IO_POLICY_ENV = "MEGAPLAN_STEP_IO_CONTRACT_MODE"
STEP_IO_READ_LENIENT_ENV = "MEGAPLAN_STEP_IO_CONTRACTS_OFF"


def megaplan_step_io_policy_path(plan_dir: str | os.PathLike[str]) -> Path:
    """Return the project-level Step IO policy path for a Megaplan plan dir."""

    plan_path = Path(plan_dir)
    for parent in (plan_path, *plan_path.parents):
        if parent.name == "plans" and parent.parent.name == ".megaplan":
            return parent.parent / STEP_IO_POLICY_DIRNAME / STEP_IO_POLICY_FILENAME
    return plan_path / ".megaplan" / STEP_IO_POLICY_DIRNAME / STEP_IO_POLICY_FILENAME


def load_megaplan_step_io_policy(plan_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Load the persisted Megaplan Step IO policy for *plan_dir*."""

    return load_megaplan_step_io_policy_path(megaplan_step_io_policy_path(plan_dir))


def load_megaplan_step_io_policy_path(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load a Step IO policy from an explicit path."""

    policy_path = Path(path)
    if not policy_path.exists():
        return {}
    try:
        data = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(data) if isinstance(data, dict) else {}


def write_megaplan_step_io_policy(
    plan_dir: str | os.PathLike[str],
    policy: StepIOPolicy,
) -> Path:
    """Persist a resolved Megaplan Step IO policy under the project policy dir."""

    path = megaplan_step_io_policy_path(plan_dir)
    existing = load_megaplan_step_io_policy_path(path)
    data = policy.to_json()
    if isinstance(existing.get(SELF_VALIDATION_KEY), dict):
        data[SELF_VALIDATION_KEY] = existing[SELF_VALIDATION_KEY]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def resolve_megaplan_step_io_policy(
    *,
    configured_mode: Any = None,
    plan_dir: str | os.PathLike[str] | None = None,
    state_config: Mapping[str, Any] | None = None,
    policy_data: Mapping[str, Any] | None = None,
    policy_path: str | os.PathLike[str] | None = None,
    binding: Any = None,
    producer_typed: bool | None = None,
    consumer_typed: bool | None = None,
    read_lenient_escape: bool | None = None,
) -> StepIOPolicy:
    """Resolve Megaplan Step IO policy from explicit, persisted, state, and env inputs."""

    raw_mode = configured_mode
    if raw_mode is None:
        if policy_data is not None:
            raw_mode = policy_data.get("configured_mode")
        elif policy_path is not None:
            raw_mode = load_megaplan_step_io_policy_path(policy_path).get("configured_mode")
        elif plan_dir is not None:
            raw_mode = load_megaplan_step_io_policy(plan_dir).get("configured_mode")
    if raw_mode is None and state_config is not None:
        raw_mode = state_config.get("step_io_contract_mode")
    if raw_mode is None:
        raw_mode = os.getenv(STEP_IO_POLICY_ENV)

    configured = normalize_contract_mode(raw_mode)
    producer, consumer, reason = _resolve_typed_sides(
        binding=binding,
        producer_typed=producer_typed,
        consumer_typed=consumer_typed,
    )
    eligible = is_step_io_enforcement_eligible(
        producer_typed=producer,
        consumer_typed=consumer,
    )

    effective = configured
    if configured in {CONTRACT_MODE_WARN, CONTRACT_MODE_ENFORCE} and not eligible:
        effective = CONTRACT_MODE_SHADOW
        reason = reason or "typed declarations are required on both sides"
    lenient = (
        megaplan_step_io_read_lenient_escape_on()
        if read_lenient_escape is None
        else bool(read_lenient_escape)
    )
    if lenient and effective != CONTRACT_MODE_OFF:
        effective = CONTRACT_MODE_SHADOW
        reason = reason or f"{STEP_IO_READ_LENIENT_ENV}=1 forces read-lenient mode"

    return StepIOPolicy(
        configured_mode=configured,
        effective_mode=effective,
        producer_typed=producer,
        consumer_typed=consumer,
        enforcement_eligible=eligible,
        reason=reason,
    )


def megaplan_policy_for_envelope(
    envelope: StepIOEnvelope | None,
    *,
    configured_mode: Any = None,
    plan_dir: str | os.PathLike[str] | None = None,
    state_config: Mapping[str, Any] | None = None,
    policy_data: Mapping[str, Any] | None = None,
    policy_path: str | os.PathLike[str] | None = None,
    binding: Any = None,
    read_lenient_escape: bool | None = None,
) -> StepIOPolicy:
    """Resolve Megaplan policy with producer typing inferred from an envelope."""

    return resolve_megaplan_step_io_policy(
        configured_mode=configured_mode,
        plan_dir=plan_dir,
        state_config=state_config,
        policy_data=policy_data,
        policy_path=policy_path,
        binding=binding,
        producer_typed=envelope is not None,
        consumer_typed=_binding_consumer_typed(binding),
        read_lenient_escape=read_lenient_escape,
    )


def has_megaplan_step_io_self_validation_marker(plan_dir: str | os.PathLike[str]) -> bool:
    """Return whether Megaplan self-validation recorded a typed artifact round trip."""

    marker = load_megaplan_step_io_policy(plan_dir).get(SELF_VALIDATION_KEY)
    if not isinstance(marker, Mapping):
        return False
    artifacts = marker.get("typed_artifacts")
    return bool(marker.get("validated") is True and isinstance(artifacts, list) and artifacts)


def record_megaplan_step_io_self_validation_marker(
    plan_dir: str | os.PathLike[str],
    *,
    typed_artifacts: list[str],
) -> Path:
    """Record Megaplan Step IO self-validation for at least one typed artifact."""

    if not typed_artifacts:
        raise ValueError("self-validation marker requires at least one typed artifact")
    path = megaplan_step_io_policy_path(plan_dir)
    data = load_megaplan_step_io_policy_path(path)
    data[SELF_VALIDATION_KEY] = {
        "validated": True,
        "typed_artifacts": sorted(set(typed_artifacts)),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def megaplan_step_io_read_lenient_escape_on() -> bool:
    """Return whether Megaplan's global read-lenient escape is enabled."""

    return os.getenv(STEP_IO_READ_LENIENT_ENV) == "1"


def _resolve_typed_sides(
    *,
    binding: Any,
    producer_typed: bool | None,
    consumer_typed: bool | None,
) -> tuple[bool, bool, str]:
    reason = ""
    if producer_typed is None:
        producer_typed = _binding_producer_typed(binding)
        if producer_typed is None:
            producer_typed = False
            reason = "binding lookup unavailable"
    if consumer_typed is None:
        consumer_typed = _binding_consumer_typed(binding)
        if consumer_typed is None:
            consumer_typed = False
            reason = reason or "binding lookup unavailable"
    return bool(producer_typed), bool(consumer_typed), reason


def _binding_producer_typed(binding: Any) -> bool | None:
    return _binding_bool(binding, "producer_typed", "source_typed", "upstream_typed", "both_sides_typed")


def _binding_consumer_typed(binding: Any) -> bool | None:
    return _binding_bool(binding, "consumer_typed", "sink_typed", "downstream_typed", "both_sides_typed")


def _binding_bool(binding: Any, *names: str) -> bool | None:
    if binding is None:
        return None
    for name in names:
        if isinstance(binding, Mapping) and name in binding:
            return bool(binding[name])
        if hasattr(binding, name):
            return bool(getattr(binding, name))
    return None
