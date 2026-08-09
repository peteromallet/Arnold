from __future__ import annotations

import hashlib

from arnold_pipelines.megaplan.cloud.fixer_prompt_policy import (
    FAST_PATH_POLICY,
    POLICY_SHA_ALGORITHM,
    PROCESS_CUSTODY_FAIL_CLOSED_POLICY,
    PROFILE_INTEGRITY_POLICY,
    policy_sha,
    render_fast_path_policy,
    render_policy_briefing,
    render_process_custody_policy,
    render_profile_integrity_policy,
)

_FRAGMENTS_IN_ORDER = (
    PROCESS_CUSTODY_FAIL_CLOSED_POLICY,
    PROFILE_INTEGRITY_POLICY,
    FAST_PATH_POLICY,
)


def test_policy_sha_deterministic_and_stable_across_calls() -> None:
    first = policy_sha()
    second = policy_sha()
    third = policy_sha()
    assert first == second == third
    assert len(first) == 64
    int(first, 16)  # hex digest


def test_policy_sha_matches_fixed_order_concatenation() -> None:
    canonical = "\n\n".join(_FRAGMENTS_IN_ORDER)
    expected = hashlib.new(
        POLICY_SHA_ALGORITHM, canonical.encode("utf-8")
    ).hexdigest()
    assert policy_sha() == expected


def test_render_policy_briefing_contains_all_three_fragments() -> None:
    briefing = render_policy_briefing()
    for fragment in _FRAGMENTS_IN_ORDER:
        assert fragment in briefing
    assert "Process custody" in briefing
    assert "Profile integrity" in briefing
    assert "Obvious-fix fast path" in briefing


def test_render_policy_briefing_is_full_canonical_block() -> None:
    assert render_policy_briefing() == "\n\n".join(_FRAGMENTS_IN_ORDER)


def test_existing_render_functions_unchanged() -> None:
    assert render_process_custody_policy() == PROCESS_CUSTODY_FAIL_CLOSED_POLICY
    assert render_profile_integrity_policy() == PROFILE_INTEGRITY_POLICY
    assert render_fast_path_policy() == FAST_PATH_POLICY
