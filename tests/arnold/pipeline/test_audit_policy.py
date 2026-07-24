from __future__ import annotations

import pytest

from arnold.pipeline.audit_policy import select_audit_mode


def test_select_audit_mode_uses_threshold_default() -> None:
    assert select_audit_mode(10, 10) == "full"
    assert select_audit_mode(11, 10) == "manifest"


def test_select_audit_mode_split_is_deterministic_at_threshold_boundary() -> None:
    sizes = [9, 10, 11, 12]

    assert [select_audit_mode(size, 10) for size in sizes] == [
        "full",
        "full",
        "manifest",
        "manifest",
    ]


def test_select_audit_mode_allows_hook_adjustment_with_validation() -> None:
    assert (
        select_audit_mode(
            11,
            10,
            policy_hook=lambda size_bytes, threshold_bytes, selected_mode: (
                "full"
                if size_bytes > threshold_bytes and selected_mode == "manifest"
                else selected_mode
            ),
        )
        == "full"
    )


def test_select_audit_mode_rejects_absent_or_unsupported_hook_modes() -> None:
    with pytest.raises(ValueError, match="unsupported audit mode"):
        select_audit_mode(1, 10, policy_hook=lambda *_: None)
    with pytest.raises(ValueError, match="unsupported audit mode"):
        select_audit_mode(1, 10, policy_hook=lambda *_: "receipt")
    with pytest.raises(ValueError, match="unsupported audit mode"):
        select_audit_mode(1, 10, policy_hook=lambda *_: "sampled")
