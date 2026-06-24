from __future__ import annotations

import importlib
import json

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "arnold.pipelines.megaplan.auto",
        "arnold_pipelines.megaplan.auto",
    ],
)
def test_host_turn_cap_cli_payload_becomes_retryable_external_error(module_name: str) -> None:
    auto = importlib.import_module(module_name)
    payload = {
        "success": False,
        "error": "rate_limit",
        "message": "Host premium-turn cap exhausted (3/3 slots active).",
        "details": {
            "source": "host_turn_cap",
            "retryable": True,
            "cap": 3,
        },
    }

    extracted = auto._extract_cli_error_payload(json.dumps(payload, indent=2), "")
    external_error = auto._external_error_from_cli_payload(extracted)

    assert external_error is not None
    assert external_error.provider == "host_turn_cap"
    assert external_error.error_kind == "rate_limit"
    assert external_error.source == "host_turn_cap"
    assert auto._is_retryable_external_error("plan", external_error) is True
    assert auto._is_host_turn_cap_external_error(external_error) is True


def test_non_host_rate_limit_cli_payload_is_not_auto_retryable() -> None:
    auto = importlib.import_module("arnold_pipelines.megaplan.auto")
    payload = {
        "success": False,
        "error": "rate_limit",
        "message": "Provider quota exhausted.",
        "details": {"source": "provider"},
    }

    extracted = auto._extract_cli_error_payload(json.dumps(payload), "")

    assert auto._external_error_from_cli_payload(extracted) is None
