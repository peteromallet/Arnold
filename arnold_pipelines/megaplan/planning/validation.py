"""Megaplan-owned profile validation for planning/runtime entrypoints."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from arnold.execution.operations import OperationResult


def preflight_or_raise(profile: Mapping[str, Any], **kwargs: Any) -> None:
    """Run the existing Megaplan credential preflight via its observed path."""
    from arnold_pipelines.megaplan import preflight as preflight_module

    preflight_module.preflight_or_raise(dict(profile), **kwargs)


def profile_validate_operation(payload: Mapping[str, Any]) -> OperationResult:
    """Validate a resolved Megaplan profile for runtime use."""
    profile = payload.get("profile")
    if not isinstance(profile, Mapping):
        profile = payload.get("resolved_profile")
    if not isinstance(profile, Mapping):
        return OperationResult(
            ok=False,
            payload={"details": {}},
            errors=("invalid_request", "profile_validate requires payload.profile"),
        )

    pipeline_name = payload.get("pipeline_name")
    profile_name = payload.get("profile_name")
    try:
        preflight_or_raise(
            profile,
            pipeline_name=pipeline_name if isinstance(pipeline_name, str) else "",
            profile_name=profile_name if isinstance(profile_name, str) else "",
        )
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return OperationResult(
            ok=False,
            payload={"exit_code": code},
            errors=("profile_invalid",),
        )
    return OperationResult(ok=True, payload={"validated": True})


__all__ = ["preflight_or_raise", "profile_validate_operation"]
