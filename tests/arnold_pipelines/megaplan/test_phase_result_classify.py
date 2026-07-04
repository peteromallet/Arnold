from __future__ import annotations

from arnold_pipelines.megaplan.orchestration.phase_result import ExternalError
from arnold_pipelines.megaplan.types import CliError


def test_codex_usage_limit_classifies_as_provider_quota() -> None:
    error = ExternalError.from_exception(
        CliError(
            "quota_exceeded",
            "Codex usage limit reached. Re-run the same execute step on Codex once before changing agent.",
        ),
        provider="codex",
    )

    assert error is not None
    assert error.provider == "codex"
    assert error.error_kind == "quota"
    assert error.provider_error_code == "quota_exceeded"
    assert error.error_layer == "provider_quota"
