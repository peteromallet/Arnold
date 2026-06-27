"""Shared vocabulary for VibeComfy harnesses.

These constants are deliberately small so they can be imported by both the
deterministic structural harness and the live agentic harness without pulling
in heavy runtime dependencies.
"""

from __future__ import annotations

from typing import Any, Mapping

# ── flow metadata boundary labels ────────────────────────────────────────────
FLOW_KIND_LIVE_AGENTIC_HEADLESS = "live_agentic_headless"
FLOW_KIND_STRUCTURAL_CONTRACT = "structural_contract"
FLOW_KIND_STRUCTURAL = FLOW_KIND_STRUCTURAL_CONTRACT

DISPATCHER_REAL = "real"
DISPATCHER_FAKE = "fake"
DISPATCHER_FAKING = "faking"
FAKE_DISPATCHERS = frozenset({DISPATCHER_FAKE, DISPATCHER_FAKING})
STRUCTURAL_DISPATCHERS = FAKE_DISPATCHERS

MODEL_BEHAVIOR_AGENTIC = "agentic"
MODEL_BEHAVIOR_DETERMINISTIC = "deterministic"
MODEL_BEHAVIOR_SCRIPTED = "scripted"

FRONTEND_NOT_USED = "not_used"

ENTRYPOINT_HEADLESS_CLI = "headless_cli"
ENTRYPOINT_PYTHON_API = "python_api"
ENTRYPOINT_HTTP = "http"

# ── run statuses ─────────────────────────────────────────────────────────────
STATUS_SUCCESS = "success"
STATUS_DRY_RUN = "dry_run"
STATUS_BLOCKED_PREREQUISITE = "blocked_prerequisite"
STATUS_VALIDATION_FAILURE = "validation_failure"
STATUS_EXECUTOR_FAILURE = "executor_failure"

OUTCOME_PASSED = "passed"
OUTCOME_FAILED = "failed"
OUTCOME_FAKE_NO_OP = "fake_no_op"
OUTCOME_BLOCKED_PREREQUISITE = STATUS_BLOCKED_PREREQUISITE
OUTCOME_SKIPPED_LIVE = "skipped_live"
VIOLATION_OUTCOMES = frozenset(
    {
        OUTCOME_FAILED,
        OUTCOME_BLOCKED_PREREQUISITE,
        OUTCOME_SKIPPED_LIVE,
    }
)

LIVE_AGENTIC_DISPATCHERS = frozenset({DISPATCHER_REAL})
LIVE_AGENTIC_MODEL_BEHAVIORS = frozenset({MODEL_BEHAVIOR_AGENTIC})


def build_flow_metadata(
    *,
    flow_kind: str,
    dispatcher: str,
    model_behavior: str,
    entrypoint: str,
    status: str,
    frontend: str = FRONTEND_NOT_USED,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a standardized flow_metadata dict.

    Raises ValueError if the combination claims live agentic success while using
    a fake/faking dispatcher or non-agentic model behavior.
    """
    metadata: dict[str, Any] = {
        "flow_kind": flow_kind,
        "dispatcher": dispatcher,
        "model_behavior": model_behavior,
        "frontend": frontend,
        "entrypoint": entrypoint,
        "status": status,
    }
    if extra:
        metadata.update(extra)
    validate_live_agentic_metadata(metadata)
    return metadata


def validate_live_agentic_metadata(metadata: Mapping[str, Any]) -> None:
    """Ensure fake/faking determinism cannot masquerade as live agentic success."""
    dispatcher = metadata.get("dispatcher")
    model_behavior = metadata.get("model_behavior")
    if dispatcher in FAKE_DISPATCHERS and model_behavior == MODEL_BEHAVIOR_AGENTIC:
        raise ValueError(
            f"Fake/faking dispatchers cannot produce model_behavior={MODEL_BEHAVIOR_AGENTIC!r}; "
            f"got dispatcher={dispatcher!r}"
        )
    if metadata.get("flow_kind") != FLOW_KIND_LIVE_AGENTIC_HEADLESS:
        return
    if metadata.get("status") != STATUS_SUCCESS:
        return
    if dispatcher not in LIVE_AGENTIC_DISPATCHERS:
        raise ValueError(
            f"Live agentic success requires dispatcher in {LIVE_AGENTIC_DISPATCHERS}, "
            f"got {dispatcher!r}"
        )
    if model_behavior not in LIVE_AGENTIC_MODEL_BEHAVIORS:
        raise ValueError(
            f"Live agentic success requires model_behavior in {LIVE_AGENTIC_MODEL_BEHAVIORS}, "
            f"got {model_behavior!r}"
        )


__all__ = [
    "FLOW_KIND_LIVE_AGENTIC_HEADLESS",
    "FLOW_KIND_STRUCTURAL_CONTRACT",
    "FLOW_KIND_STRUCTURAL",
    "DISPATCHER_REAL",
    "DISPATCHER_FAKE",
    "DISPATCHER_FAKING",
    "FAKE_DISPATCHERS",
    "STRUCTURAL_DISPATCHERS",
    "MODEL_BEHAVIOR_AGENTIC",
    "MODEL_BEHAVIOR_DETERMINISTIC",
    "MODEL_BEHAVIOR_SCRIPTED",
    "FRONTEND_NOT_USED",
    "ENTRYPOINT_HEADLESS_CLI",
    "ENTRYPOINT_PYTHON_API",
    "ENTRYPOINT_HTTP",
    "STATUS_SUCCESS",
    "STATUS_DRY_RUN",
    "STATUS_BLOCKED_PREREQUISITE",
    "STATUS_VALIDATION_FAILURE",
    "STATUS_EXECUTOR_FAILURE",
    "OUTCOME_PASSED",
    "OUTCOME_FAILED",
    "OUTCOME_FAKE_NO_OP",
    "OUTCOME_BLOCKED_PREREQUISITE",
    "OUTCOME_SKIPPED_LIVE",
    "VIOLATION_OUTCOMES",
    "build_flow_metadata",
    "validate_live_agentic_metadata",
]
