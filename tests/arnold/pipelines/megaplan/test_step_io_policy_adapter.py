from __future__ import annotations

import json

import pytest

from arnold.pipeline.step_io_contract import StepIOEnvelope
from arnold.pipeline.step_io_policy import (
    CONTRACT_MODE_ENFORCE,
    CONTRACT_MODE_SHADOW,
    CONTRACT_MODE_WARN,
    StepIOPolicy,
)
from arnold.pipelines.megaplan._pipeline.step_io_policy_adapter import (
    STEP_IO_POLICY_ENV,
    STEP_IO_READ_LENIENT_ENV,
    has_megaplan_step_io_self_validation_marker,
    load_megaplan_step_io_policy,
    megaplan_policy_for_envelope,
    megaplan_step_io_policy_path,
    megaplan_step_io_read_lenient_escape_on,
    record_megaplan_step_io_self_validation_marker,
    resolve_megaplan_step_io_policy,
    write_megaplan_step_io_policy,
)


def test_policy_path_derives_project_policy_path_from_plan_directory(tmp_path) -> None:
    project_root = tmp_path / "project"
    plan_dir = project_root / ".megaplan" / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True)

    assert megaplan_step_io_policy_path(plan_dir) == (
        project_root / ".megaplan" / "policies" / "step_io_contract_modes.json"
    )


def test_policy_path_falls_back_to_local_megaplan_policy_dir(tmp_path) -> None:
    plan_dir = tmp_path / "standalone-plan"

    assert megaplan_step_io_policy_path(plan_dir) == (
        plan_dir / ".megaplan" / "policies" / "step_io_contract_modes.json"
    )


def test_env_compatibility_resolves_contract_mode_and_lenient_escape(tmp_path, monkeypatch) -> None:
    plan_dir = tmp_path / "project" / ".megaplan" / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True)
    monkeypatch.setenv(STEP_IO_POLICY_ENV, CONTRACT_MODE_ENFORCE)
    monkeypatch.setenv(STEP_IO_READ_LENIENT_ENV, "1")

    policy = resolve_megaplan_step_io_policy(
        plan_dir=plan_dir,
        producer_typed=True,
        consumer_typed=True,
    )

    assert megaplan_step_io_read_lenient_escape_on() is True
    assert policy.configured_mode == CONTRACT_MODE_ENFORCE
    assert policy.effective_mode == CONTRACT_MODE_SHADOW
    assert policy.reason == f"{STEP_IO_READ_LENIENT_ENV}=1 forces read-lenient mode"


def test_policy_file_takes_precedence_over_state_and_env(tmp_path, monkeypatch) -> None:
    plan_dir = tmp_path / "project" / ".megaplan" / "plans" / "demo-plan"
    policy_path = megaplan_step_io_policy_path(plan_dir)
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(json.dumps({"configured_mode": CONTRACT_MODE_WARN}), encoding="utf-8")
    monkeypatch.setenv(STEP_IO_POLICY_ENV, CONTRACT_MODE_ENFORCE)

    policy = resolve_megaplan_step_io_policy(
        plan_dir=plan_dir,
        state_config={"step_io_contract_mode": CONTRACT_MODE_SHADOW},
        producer_typed=True,
        consumer_typed=True,
    )

    assert policy.configured_mode == CONTRACT_MODE_WARN
    assert policy.effective_mode == CONTRACT_MODE_WARN


def test_envelope_policy_infers_typed_producer_and_binding_consumer(tmp_path) -> None:
    envelope = StepIOEnvelope(
        logical_type="demo.payload",
        schema_version="demo.payload.v1",
        payload={"ok": True},
    )

    policy = megaplan_policy_for_envelope(
        envelope,
        configured_mode=CONTRACT_MODE_ENFORCE,
        binding={"consumer_typed": True},
    )

    assert policy.configured_mode == CONTRACT_MODE_ENFORCE
    assert policy.effective_mode == CONTRACT_MODE_ENFORCE
    assert policy.producer_typed is True
    assert policy.consumer_typed is True


def test_envelope_policy_requires_consumer_typing_for_enforcement() -> None:
    envelope = StepIOEnvelope(
        logical_type="demo.payload",
        schema_version="demo.payload.v1",
        payload={"ok": True},
    )

    policy = megaplan_policy_for_envelope(
        envelope,
        configured_mode=CONTRACT_MODE_ENFORCE,
        binding={"consumer_typed": False},
    )

    assert policy.configured_mode == CONTRACT_MODE_ENFORCE
    assert policy.effective_mode == CONTRACT_MODE_SHADOW
    assert policy.enforcement_eligible is False


def test_write_policy_preserves_self_validation_marker(tmp_path) -> None:
    plan_dir = tmp_path / "project" / ".megaplan" / "plans" / "demo-plan"
    record_megaplan_step_io_self_validation_marker(
        plan_dir,
        typed_artifacts=["beta", "alpha", "alpha"],
    )

    write_megaplan_step_io_policy(
        plan_dir,
        StepIOPolicy(
            configured_mode=CONTRACT_MODE_ENFORCE,
            effective_mode=CONTRACT_MODE_ENFORCE,
            producer_typed=True,
            consumer_typed=True,
            enforcement_eligible=True,
        ),
    )

    data = load_megaplan_step_io_policy(plan_dir)
    assert data["configured_mode"] == CONTRACT_MODE_ENFORCE
    assert data["self_validation"] == {
        "validated": True,
        "typed_artifacts": ["alpha", "beta"],
    }
    assert has_megaplan_step_io_self_validation_marker(plan_dir) is True


def test_self_validation_marker_rejects_empty_artifact_list(tmp_path) -> None:
    with pytest.raises(ValueError, match="at least one typed artifact"):
        record_megaplan_step_io_self_validation_marker(tmp_path / "plan", typed_artifacts=[])
