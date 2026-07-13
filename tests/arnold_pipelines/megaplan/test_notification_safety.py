from __future__ import annotations

from arnold_pipelines.megaplan.notification_safety import classify_user_notification


def test_pytest_fixture_workspace_is_never_user_notifiable() -> None:
    decision = classify_user_notification(
        workspace="/tmp/pytest-of-root/pytest-411/test_watchdog_gate0/ws",
        env={},
    )

    assert decision.allowed is False
    assert decision.reason == "pytest_workspace"


def test_explicit_test_bot_identity_is_never_user_notifiable() -> None:
    decision = classify_user_notification(
        payload={"execution_context": {"actor_id": "test-bot"}}, env={}
    )

    assert decision.allowed is False
    assert decision.reason == "test_identity:actor_id"


def test_live_pytest_environment_is_never_user_notifiable() -> None:
    decision = classify_user_notification(
        workspace="/workspace/real-chain",
        env={"PYTEST_CURRENT_TEST": "tests/test_alerts.py::test_gate (call)"},
    )

    assert decision.allowed is False
    assert decision.reason == "pytest_environment"


def test_genuine_demo_chain_workspace_remains_user_notifiable() -> None:
    decision = classify_user_notification(
        payload={"session": "demo-chain", "workspace": "/workspace/demo-chain"},
        env={},
    )

    assert decision.allowed is True
    assert decision.reason == ""
