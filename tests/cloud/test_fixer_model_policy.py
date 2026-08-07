from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

import pytest

from arnold_pipelines.megaplan.cloud.fixer_model_policy import (
    MODEL_POLICY_TABLE,
    MODEL_POLICY_SHA_ALGORITHM,
    PolicyError,
    PolicyRow,
    main,
    model_policy_sha,
    resolve_model_policy,
    validate_hot_env_credentials_only,
)

GATED_FLASH_MODE_RUNGS = (
    "reactive_investigator",
    "reactive_mutator",
    "proactive",
    "l2",
)
ALL_MODE_RUNGS = GATED_FLASH_MODE_RUNGS + ("l3_orchestrator",)


def test_table_has_all_five_mode_rungs() -> None:
    assert {row.mode_rung for row in MODEL_POLICY_TABLE} == set(ALL_MODE_RUNGS)
    by_rung = {row.mode_rung: row for row in MODEL_POLICY_TABLE}
    for rung in GATED_FLASH_MODE_RUNGS:
        assert by_rung[rung].status == "gated"
        assert by_rung[rung].model == "deepseek:deepseek-v4-flash"
    l3 = by_rung["l3_orchestrator"]
    assert l3.status == "default"
    assert l3.agent_backend == "codex"
    assert l3.model == "deepseek:deepseek-v4-pro"


@pytest.mark.parametrize("mode_rung", GATED_FLASH_MODE_RUNGS)
def test_gated_rows_raise_policy_error_without_replay_approval(mode_rung: str) -> None:
    with pytest.raises(PolicyError):
        resolve_model_policy(mode_rung)


@pytest.mark.parametrize("mode_rung", GATED_FLASH_MODE_RUNGS)
def test_replay_approved_returns_flash_row(mode_rung: str) -> None:
    row = resolve_model_policy(mode_rung, replay_approved=True)
    assert isinstance(row, PolicyRow)
    assert row.mode_rung == mode_rung
    assert row.model == "deepseek:deepseek-v4-flash"
    assert row.agent_backend == "deepseek"
    assert row.provider_spec == "deepseek"


def test_l3_orchestrator_resolves_without_replay_approval() -> None:
    row = resolve_model_policy("l3_orchestrator")
    assert row.status == "default"
    assert row.model == "deepseek:deepseek-v4-pro"


def test_unknown_mode_rung_raises_policy_error() -> None:
    with pytest.raises(PolicyError):
        resolve_model_policy("no_such_rung")
    with pytest.raises(PolicyError):
        resolve_model_policy("no_such_rung", replay_approved=True)


def test_validate_hot_env_flags_model_overrides() -> None:
    env = {
        "MEGAPLAN_AUDIT_MODEL": "deepseek:deepseek-v4-flash",
        "CLOUD_WATCHDOG_REPAIR_BROKERED_INVESTIGATOR_MODEL": "deepseek:deepseek-v4-pro",
        "MODEL": "some:model",
    }
    violations = validate_hot_env_credentials_only(env)
    assert sorted(violations) == [
        "CLOUD_WATCHDOG_REPAIR_BROKERED_INVESTIGATOR_MODEL",
        "MEGAPLAN_AUDIT_MODEL",
        "MODEL",
    ]


def test_validate_hot_env_passes_credentials_only_env() -> None:
    env = {
        "DEEPSEEK_API_KEY": "sk-...",
        "OPENROUTER_API_KEY": "or-...",
        "ZHIPU_API_TOKEN": "zp-...",
        "DEEPSEEK_API_TOKEN": "tok",
        "SOME_OTHER_SECRET": "s",
        "PATH": "/usr/bin",
    }
    assert validate_hot_env_credentials_only(env) == []


def test_model_policy_sha_deterministic() -> None:
    first = model_policy_sha()
    second = model_policy_sha()
    assert first == second
    assert len(first) == 64
    int(first, 16)  # hex digest


def test_model_policy_sha_matches_canonical_serialization() -> None:
    rows = sorted(
        (asdict(row) for row in MODEL_POLICY_TABLE),
        key=lambda row: row["mode_rung"],
    )
    canonical = json.dumps(rows, sort_keys=True, ensure_ascii=True)
    expected = hashlib.new(
        MODEL_POLICY_SHA_ALGORITHM, canonical.encode("utf-8")
    ).hexdigest()
    assert model_policy_sha() == expected


def test_main_prints_table_and_sha_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    for rung in ALL_MODE_RUNGS:
        assert rung in out
    assert "deepseek:deepseek-v4-flash" in out
    assert "deepseek:deepseek-v4-pro" in out
    assert f"model_policy_sha={model_policy_sha()}" in out
