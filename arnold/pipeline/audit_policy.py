"""Deterministic audit-mode selection for size-threshold policy seams."""

from __future__ import annotations

from typing import Literal, Protocol


AuditMode = Literal["full", "manifest"]


class AuditPolicyHook(Protocol):
    """Optional policy hook that may keep or adjust the selected audit mode."""

    def __call__(
        self,
        size_bytes: int,
        threshold_bytes: int,
        selected_mode: AuditMode,
    ) -> AuditMode: ...


def select_audit_mode(
    size_bytes: int,
    threshold_bytes: int,
    policy_hook: AuditPolicyHook | None = None,
) -> AuditMode:
    """Choose ``full`` up to the threshold and ``manifest`` above it."""

    mode: AuditMode = "full" if size_bytes <= threshold_bytes else "manifest"
    if policy_hook is not None:
        mode = policy_hook(size_bytes, threshold_bytes, mode)
    if mode not in ("full", "manifest"):
        raise ValueError(f"unsupported audit mode {mode!r}")
    return mode
