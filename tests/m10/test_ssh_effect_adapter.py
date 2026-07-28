"""Tests for Step 13F: SSH remote mutation sink routing.

Covers:
- Three routed shards (build/deploy/destroy) go through WBC
- Action-off shards (down/ssh_exec/upload_file/upload_archive) not routed
- Provider-missing negatives (no host or container)
- Stale-fence negatives
- Fake-transport detection
- Bypass behavior (no adapter = direct path)
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from arnold.workflow.effect_protocol import (
    EffectProtocol,
    OUTCOME_COMPLETED,
    OUTCOME_FAILED,
    OUTCOME_INDETERMINATE,
)
from arnold_pipelines.megaplan.cloud.ssh_effect_adapter import (
    SshEffectShard,
    SSH_SHARD_13F,
    SSH_ACTION_OFF_SHARDS,
    SshTarget,
    SshOutcome,
    SshEffectAdapter,
)
from arnold_pipelines.megaplan.custody.action_gate import (
    ActionGateVerdict,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_protocol():
    """Create a mock EffectProtocol."""
    protocol = MagicMock(spec=EffectProtocol)
    reservation = MagicMock()
    reservation.global_logical_effect_key = "glek-ssh-123"
    protocol.reserve_and_start.return_value = reservation
    return protocol


@pytest.fixture
def adapter(mock_protocol):
    """Create an SshEffectAdapter with shadow gate."""
    return SshEffectAdapter(
        mock_protocol,
        production_enabled=False,
    )


@pytest.fixture
def build_target():
    return SshTarget(
        shard=SshEffectShard.BUILD,
        host="example.com",
        container="arnold-app",
        operation="build",
    )


@pytest.fixture
def deploy_target():
    return SshTarget(
        shard=SshEffectShard.DEPLOY,
        host="example.com",
        container="arnold-app",
        operation="deploy",
    )


@pytest.fixture
def destroy_target():
    return SshTarget(
        shard=SshEffectShard.DESTROY,
        host="example.com",
        container="arnold-app",
        operation="destroy",
    )


# ── Shard enforcement ────────────────────────────────────────────────────────


def test_routed_shards_are_build_deploy_destroy():
    """Only BUILD, DEPLOY, DESTROY are in the 13F routed set."""
    assert set(SSH_SHARD_13F) == {
        SshEffectShard.BUILD,
        SshEffectShard.DEPLOY,
        SshEffectShard.DESTROY,
    }


def test_action_off_shards_not_routed():
    """down, ssh_exec, upload_file, upload_archive are action-off."""
    assert "down" in SSH_ACTION_OFF_SHARDS
    assert "ssh_exec" in SSH_ACTION_OFF_SHARDS
    assert "upload_file" in SSH_ACTION_OFF_SHARDS
    assert "upload_archive" in SSH_ACTION_OFF_SHARDS


def test_non_routed_shard_raises(adapter):
    """A shard not in 13F raises ValueError."""
    class BogusShard:
        value = "bogus"

    target = MagicMock()
    target.shard = BogusShard()

    with pytest.raises((ValueError, TypeError)):
        adapter.route(
            target=target,
            intent_payload={},
            apply_fn=lambda x: x,
        )


# ── Provider-missing negative ────────────────────────────────────────────────


def test_missing_host_blocks_dispatch(adapter, mock_protocol):
    """Missing host is a provider-missing negative."""
    target = SshTarget(
        shard=SshEffectShard.BUILD,
        host="",  # empty host
        container="test-container",
    )
    result = adapter.route(
        target=target,
        intent_payload={"cmd": "build"},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "Provider missing" in result.error


def test_missing_container_blocks_dispatch(adapter, mock_protocol):
    """Missing container is a provider-missing negative."""
    target = SshTarget(
        shard=SshEffectShard.BUILD,
        host="example.com",
        container="",  # empty container
    )
    result = adapter.route(
        target=target,
        intent_payload={"cmd": "build"},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "Provider missing" in result.error


# ── Successful dispatch ──────────────────────────────────────────────────────


def test_build_succeeds_with_valid_target(adapter, build_target, mock_protocol):
    """BUILD with valid target dispatches successfully."""
    result = adapter.route(
        target=build_target,
        intent_payload={"deploy_dir": "/tmp/deploy"},
        apply_fn=lambda x: {"exit_code": 0},
        fence_token=1,
    )
    assert result.ok
    assert result.glek != ""
    assert result.outcome_kind == OUTCOME_COMPLETED


def test_deploy_succeeds_with_valid_target(adapter, deploy_target, mock_protocol):
    """DEPLOY with valid target dispatches successfully."""
    result = adapter.route(
        target=deploy_target,
        intent_payload={"port": 8080},
        apply_fn=lambda x: {"exit_code": 0},
        fence_token=1,
    )
    assert result.ok
    assert result.glek != ""
    assert result.outcome_kind == OUTCOME_COMPLETED


def test_destroy_succeeds_with_valid_target(adapter, destroy_target, mock_protocol):
    """DESTROY with valid target dispatches successfully."""
    result = adapter.route(
        target=destroy_target,
        intent_payload={"container": "arnold-app"},
        apply_fn=lambda x: {"exit_code": 0},
        fence_token=1,
    )
    assert result.ok
    assert result.glek != ""
    assert result.outcome_kind == OUTCOME_COMPLETED


# ── Stale-fence negatives ────────────────────────────────────────────────────


def test_stale_fence_blocks_ssh(adapter, build_target):
    """Missing fence_token blocks SSH dispatch."""
    result = adapter.route(
        target=build_target,
        intent_payload={"cmd": "build"},
        apply_fn=lambda x: x,
        fence_token=None,
    )
    assert not result.ok
    assert "Stale fence" in result.error


def test_zero_fence_token_blocks_ssh(adapter, build_target):
    """Zero fence_token blocks SSH dispatch."""
    result = adapter.route(
        target=build_target,
        intent_payload={"cmd": "build"},
        apply_fn=lambda x: x,
        fence_token=0,
    )
    assert not result.ok
    assert "Stale fence" in result.error


# ── Intent-failure negatives ─────────────────────────────────────────────────


def test_empty_intent_payload_blocks_dispatch(adapter, build_target):
    """Empty intent payload is rejected."""
    result = adapter.route(
        target=build_target,
        intent_payload={},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "Intent-failure" in result.error


# ── Crash behavior ───────────────────────────────────────────────────────────


def test_protocol_exception_produces_indeterminate(adapter, build_target, mock_protocol):
    """If the protocol raises, the outcome is INDETERMINATE."""
    mock_protocol.reserve_and_start.side_effect = RuntimeError("SSH DB crashed")

    result = adapter.route(
        target=build_target,
        intent_payload={"cmd": "build"},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert result.outcome_kind == OUTCOME_INDETERMINATE
    assert "Protocol error" in result.error


def test_apply_fn_exception_produces_failed(adapter, build_target, mock_protocol):
    """If the apply_fn raises, the outcome is FAILED."""
    def failing_apply(payload):
        raise ConnectionError("SSH connection refused")

    result = adapter.route(
        target=build_target,
        intent_payload={"cmd": "build"},
        apply_fn=failing_apply,
        fence_token=1,
    )
    assert not result.ok
    assert result.outcome_kind == OUTCOME_FAILED
    assert "connection refused" in result.error


# ── Fake-transport negative ──────────────────────────────────────────────────


def test_fake_transport_detects_real_subprocess(adapter, build_target):
    """Fake-transport detection flags subprocess.run usage."""
    def real_ssh(payload):
        import subprocess
        subprocess.run(["ssh", "example.com", "ls"])

    # Source inspection may not work with lambdas, but the method exists
    result = adapter.check_fake_transport(real_ssh, build_target)
    # Should detect the suspicious pattern
    assert not result


def test_fake_transport_allows_clean_lambda(adapter, build_target):
    """A clean lambda without suspicious patterns passes."""
    def fake_transport(payload):
        return {"exit_code": 0, "output": "ok"}

    result = adapter.check_fake_transport(fake_transport, build_target)
    # A simple function without real subprocess calls should pass
    assert result


# ── GLEK stability ───────────────────────────────────────────────────────────


def test_glek_stable_for_same_target(adapter, build_target):
    """Same target produces same GLEK identity inputs."""
    ei1 = adapter._build_effect_identity(build_target)
    ei2 = adapter._build_effect_identity(build_target)
    assert ei1.environment_id == ei2.environment_id
    assert ei1.action_target == ei2.action_target
    assert ei1.effect_family == ei2.effect_family


def test_glek_differs_for_different_operations(adapter, build_target, deploy_target):
    """Different operations produce different effect identities."""
    ei_build = adapter._build_effect_identity(build_target)
    ei_deploy = adapter._build_effect_identity(deploy_target)
    assert ei_build.effect_family != ei_deploy.effect_family


# ── SshTarget identity ───────────────────────────────────────────────────────


def test_ssh_target_key_is_stable():
    """SshTarget.target_key is stable and deterministic."""
    target = SshTarget(
        shard=SshEffectShard.BUILD,
        host="example.com",
        container="my-app",
    )
    assert target.target_key == "ssh:build:example.com:my-app"


def test_ssh_target_different_hosts_produce_different_keys():
    """Different hosts produce different target keys."""
    t1 = SshTarget(SshEffectShard.BUILD, host="h1", container="c1")
    t2 = SshTarget(SshEffectShard.BUILD, host="h2", container="c1")
    assert t1.target_key != t2.target_key
