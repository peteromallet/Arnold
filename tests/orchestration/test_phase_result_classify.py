from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.orchestration.phase_result import ExternalError


@pytest.mark.parametrize(
    ("message", "provider"),
    [
        (
            "resolve_provider_client: openrouter requested but OPENROUTER_API_KEY not set",
            "openrouter",
        ),
        (
            "Failed to initialize OpenAI client: Missing credentials. Please pass an `api_key`.",
            "openai",
        ),
    ],
)
def test_from_exception_classifies_missing_credentials_as_auth(
    message: str,
    provider: str,
) -> None:
    error = ExternalError.from_exception(RuntimeError(message), provider=provider)

    assert error is not None
    assert error.provider == provider
    assert error.error_kind == "auth"
