from __future__ import annotations

from arnold_pipelines.megaplan.orchestration.phase_result import ExternalError
from arnold_pipelines.megaplan.orchestration.recovery_policy import (
    EXTERNAL_PERMANENT_ERROR_KINDS,
)
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.workers import _diagnose_codex_failure


def test_hard_codex_quota_waits_for_capacity_before_one_retry() -> None:
    raw = (
        "You've hit your usage limit. Purchase credits to continue, or try again at "
        "2026-08-04 04:17:00 UTC."
    )

    code, message = _diagnose_codex_failure(raw, 1)

    assert code == "quota_exceeded"
    assert message == (
        "Codex usage limit reached. Do not retry immediately. Restore Codex "
        "credits/capacity or wait until the provider-stated reset, then re-run the "
        "same step on Codex exactly once."
    )
    assert "2026-08-04" not in message
    assert "04:17:00" not in message

    external = ExternalError.from_exception(CliError(code, message), provider="codex")
    assert external is not None
    assert external.error_kind == "quota"
    assert external.provider_error_code == "quota_exceeded"
    assert external.error_kind in EXTERNAL_PERMANENT_ERROR_KINDS


def test_generic_codex_rate_limit_preserves_transient_retry_guidance() -> None:
    code, message = _diagnose_codex_failure(
        "request failed: rate limit exceeded; slow down",
        1,
    )

    assert code == "rate_limit"
    assert message == (
        "Codex hit a rate limit. Re-run the same step on Codex once before changing "
        "agent."
    )
    assert "Do not retry immediately" not in message
