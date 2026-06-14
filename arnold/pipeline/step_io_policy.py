"""Policy resolution for step IO contract decisions.

The contract module classifies artifacts; this module decides how strongly a
caller should act on that classification for one typed seam.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.step_io_contract import (
    StepIOClassification,
    StepIOContractDecision,
    StepIOEnvelope,
)

STEP_IO_POLICY_DIRNAME = "policies"
STEP_IO_POLICY_FILENAME = "step_io_contract_modes.json"
SELF_VALIDATION_KEY = "self_validation"
CONTRACT_MODE_OFF = "off"
CONTRACT_MODE_SHADOW = "shadow"
CONTRACT_MODE_WARN = "warn"
CONTRACT_MODE_ENFORCE = "enforce"
_CONTRACT_MODES = {
    CONTRACT_MODE_OFF,
    CONTRACT_MODE_SHADOW,
    CONTRACT_MODE_WARN,
    CONTRACT_MODE_ENFORCE,
}


def normalize_contract_mode(value: Any) -> str:
    """Normalize step-IO policy modes without importing megaplan orchestration."""

    if value is None:
        return CONTRACT_MODE_SHADOW
    mode = str(value).strip().lower()
    return mode if mode in _CONTRACT_MODES else CONTRACT_MODE_SHADOW


@dataclass(frozen=True)
class StepIOPolicy:
    """Resolved policy for one artifact IO seam."""

    configured_mode: str
    effective_mode: str
    producer_typed: bool
    consumer_typed: bool
    enforcement_eligible: bool
    reason: str = ""

    @property
    def enabled(self) -> bool:
        return self.effective_mode != CONTRACT_MODE_OFF

    @property
    def warns(self) -> bool:
        return self.effective_mode == CONTRACT_MODE_WARN

    @property
    def enforces(self) -> bool:
        return self.effective_mode == CONTRACT_MODE_ENFORCE

    def to_json(self) -> dict[str, Any]:
        return {
            "configured_mode": self.configured_mode,
            "effective_mode": self.effective_mode,
            "producer_typed": self.producer_typed,
            "consumer_typed": self.consumer_typed,
            "enforcement_eligible": self.enforcement_eligible,
            "reason": self.reason,
        }


def is_step_io_enforcement_eligible(
    *,
    producer_typed: bool,
    consumer_typed: bool,
) -> bool:
    """Return whether a seam has typed declarations on both sides."""

    return producer_typed and consumer_typed


def resolve_step_io_policy(
    *,
    configured_mode: Any = None,
    policy_data: Mapping[str, Any] | None = None,
    policy_path: str | Path | None = None,
    binding: Any = None,
    producer_typed: bool | None = None,
    consumer_typed: bool | None = None,
    read_lenient_escape: bool = False,
) -> StepIOPolicy:
    """Resolve configured and effective step-IO policy.

    Precedence is explicit ``configured_mode``, explicit policy data, explicit
    policy file, then the shared contract default from
    ``normalize_contract_mode(None)``.
    """

    raw_mode = configured_mode
    if raw_mode is None and policy_data is not None:
        raw_mode = policy_data.get("configured_mode")
    if raw_mode is None and policy_path is not None:
        raw_mode = load_step_io_policy(policy_path=policy_path).get("configured_mode")

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
    if read_lenient_escape and effective != CONTRACT_MODE_OFF:
        effective = CONTRACT_MODE_SHADOW
        reason = reason or "read-lenient mode requested"

    return StepIOPolicy(
        configured_mode=configured,
        effective_mode=effective,
        producer_typed=producer,
        consumer_typed=consumer,
        enforcement_eligible=eligible,
        reason=reason,
    )


def load_step_io_policy(
    policy_path: str | Path | None = None,
    *,
    policy_data: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load explicit policy data or a policy file, returning an empty mapping when absent."""

    if policy_data is not None:
        return dict(policy_data)
    if policy_path is None:
        return {}
    path = Path(policy_path)
    if not path.exists():
        return {}
    elif path.is_dir():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(data) if isinstance(data, dict) else {}


def write_step_io_policy(policy_path: str | Path, policy: StepIOPolicy) -> Path:
    """Persist a resolved policy to an explicit file path."""

    path = Path(policy_path)
    existing = load_step_io_policy(policy_path)
    data = policy.to_json()
    if isinstance(existing.get(SELF_VALIDATION_KEY), dict):
        data[SELF_VALIDATION_KEY] = existing[SELF_VALIDATION_KEY]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def has_step_io_self_validation_marker(marker_path: str | Path) -> bool:
    """Return whether at least one typed artifact round trip succeeded."""

    marker = load_step_io_policy(marker_path).get(SELF_VALIDATION_KEY)
    if not isinstance(marker, Mapping):
        return False
    artifacts = marker.get("typed_artifacts")
    return bool(marker.get("validated") is True and isinstance(artifacts, list) and artifacts)


def record_step_io_self_validation_marker(
    marker_path: str | Path,
    *,
    typed_artifacts: list[str],
) -> Path:
    """Record that self-validation proved at least one typed artifact round trip."""

    if not typed_artifacts:
        raise ValueError("self-validation marker requires at least one typed artifact")
    path = Path(marker_path)
    data = load_step_io_policy(marker_path)
    data[SELF_VALIDATION_KEY] = {
        "validated": True,
        "typed_artifacts": sorted(set(typed_artifacts)),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def decision_blocks_read(
    decision: StepIOContractDecision,
    policy: StepIOPolicy,
) -> bool:
    """Return whether a read decision should block under *policy*."""

    if not policy.enforces:
        return False
    return decision.classification in {
        StepIOClassification.TYPED_INVALID,
        StepIOClassification.SCHEMA_UNAVAILABLE,
        StepIOClassification.BINDING_UNAVAILABLE,
    }


def decision_blocks_write(
    decision: StepIOContractDecision,
    policy: StepIOPolicy,
) -> bool:
    """Return whether a write decision should block under *policy*."""

    if decision.blocks_write:
        return True
    if not policy.enforces:
        return False
    return decision.classification in {
        StepIOClassification.TYPED_INVALID,
        StepIOClassification.SCHEMA_UNAVAILABLE,
        StepIOClassification.BINDING_UNAVAILABLE,
    }


def effective_blocks_read(
    decision: StepIOContractDecision,
    policy: StepIOPolicy,
) -> bool:
    """Return True only when *policy* enforces AND the read decision blocks.

    Additive helper that gives warn mode distinct non-blocking semantics
    without modifying ``decision_blocks_read`` (DC8: mode-ladder preserved).
    """

    return policy.enforces and decision_blocks_read(decision, policy)


def effective_blocks_write(
    decision: StepIOContractDecision,
    policy: StepIOPolicy,
) -> bool:
    """Return True only when *policy* enforces AND the write decision blocks.

    Additive helper that gives warn mode distinct non-blocking semantics
    without modifying ``decision_blocks_write`` (DC8: mode-ladder preserved).
    """

    return policy.enforces and decision_blocks_write(decision, policy)


def policy_for_envelope(
    envelope: StepIOEnvelope | None,
    *,
    configured_mode: Any = None,
    policy_data: Mapping[str, Any] | None = None,
    policy_path: str | Path | None = None,
    binding: Any = None,
    read_lenient_escape: bool = False,
) -> StepIOPolicy:
    """Resolve policy with a typed-producer fallback from the artifact envelope."""

    producer_typed = envelope is not None
    return resolve_step_io_policy(
        configured_mode=configured_mode,
        policy_data=policy_data,
        policy_path=policy_path,
        binding=binding,
        producer_typed=producer_typed,
        consumer_typed=_binding_consumer_typed(binding),
        read_lenient_escape=read_lenient_escape,
    )


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
