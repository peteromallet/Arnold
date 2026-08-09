from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import pytest

from arnold.security import (
    BROKER_SOCKET_ENV,
    REDACTED,
    ActionRequest,
    ActionVerdict,
    BrokerClient,
    BrokerClientError,
    BrokerSecretStore,
    BrokerService,
    BrokerServiceError,
    UnixBrokerServer,
)


def test_broker_service_loads_secret_status_without_exposing_values(monkeypatch) -> None:
    secret_value = "sk-service-secret-token-1234567890"
    monkeypatch.setenv("OPENAI_API_KEY", secret_value)

    service = BrokerService(secrets=BrokerSecretStore.from_environment())
    response = service.handle_payload({"version": 1, "operation": "credential_status"})
    serialized = json.dumps(response, sort_keys=True)

    assert response["ok"] is True
    assert "OPENAI_API_KEY" in response["broker_status"]["configured_names"]
    assert secret_value not in serialized


def test_broker_round_trip_sanitizes_supplied_secret_values() -> None:
    supplied_secret = "sk-supplied-secret-token-1234567890"
    service = BrokerService()
    response = service.handle_payload(
        {
            "version": 1,
            "operation": "evaluate_action",
            "request": {
                "action_type": "git_push",
                "repo": "acme/service",
                "branch": "feature/demo",
                "metadata": {
                    "api_key": supplied_secret,
                    "note": f"token={supplied_secret}",
                    "nested": {"authorization": f"Bearer {supplied_secret}"},
                },
            },
        }
    )
    serialized = json.dumps(response, sort_keys=True)

    assert response["ok"] is True
    assert response["result"]["verdict"] == ActionVerdict.ALLOW.value
    assert supplied_secret not in serialized
    assert response["result"]["metadata"]["action_type"] == "git_push"


def test_broker_client_server_unix_round_trip_without_secret_echo(
    short_broker_socket_path: Path,
) -> None:
    supplied_secret = "sk-unix-secret-token-1234567890"
    socket_path = short_broker_socket_path
    server = UnixBrokerServer(str(socket_path), service=BrokerService())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = ActionRequest(
            action_type="git_push",
            repo="acme/service",
            branch="feature/demo",
            command=("git", "push", f"https://token={supplied_secret}@example.test/repo.git"),
            metadata={"api_key": supplied_secret, "detail": f"token={supplied_secret}"},
        )

        result = BrokerClient(socket_path=str(socket_path)).evaluate_action(request)
        serialized = json.dumps(result.to_json(), sort_keys=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result.verdict is ActionVerdict.ALLOW
    assert supplied_secret not in serialized


def test_broker_server_rejects_overlong_socket_path_with_actionable_error() -> None:
    socket_path = "/tmp/" + ("overlong-broker-segment-" * 20) + ".sock"
    with pytest.raises(
        BrokerServiceError,
        match="configure a shorter ARNOLD_BROKER_SOCKET path",
    ):
        UnixBrokerServer(socket_path, service=BrokerService())


def test_broker_client_rejects_overlong_socket_path_with_actionable_error() -> None:
    socket_path = "/tmp/" + ("overlong-broker-segment-" * 20) + ".sock"
    client = BrokerClient(socket_path=socket_path)
    with pytest.raises(
        BrokerClientError,
        match="configure a shorter ARNOLD_BROKER_SOCKET path",
    ):
        client._send({"version": 1, "operation": "credential_status"})


def test_broker_client_fails_closed_when_configured_socket_unreachable(
    tmp_path,
    monkeypatch,
    caplog,
) -> None:
    supplied_secret = "sk-unreachable-secret-token-1234567890"
    missing_socket = tmp_path / "missing-broker.sock"
    monkeypatch.setenv(BROKER_SOCKET_ENV, str(missing_socket))
    caplog.set_level(logging.WARNING, logger="arnold.security.broker_client")

    request = ActionRequest(
        action_type="git_push",
        repo="acme/service",
        branch="feature/demo",
        metadata={"api_key": supplied_secret, "detail": f"token={supplied_secret}"},
    )
    result = BrokerClient.from_environment().evaluate_action(request)
    serialized = json.dumps(result.to_json(), sort_keys=True)
    logged = "\n".join(record.getMessage() for record in caplog.records)

    assert result.verdict is ActionVerdict.DENY
    assert result.metadata["fail_closed"] is True
    assert supplied_secret not in serialized
    assert supplied_secret not in logged


def test_broker_service_error_response_does_not_echo_malformed_secret_payload() -> None:
    supplied_secret = "sk-malformed-secret-token-1234567890"
    service = BrokerService()

    response = service.handle_payload(
        {
            "version": 1,
            "operation": "evaluate_action",
            "request": {
                "action_type": "",
                "metadata": {"api_key": supplied_secret},
            },
        }
    )
    serialized = json.dumps(response, sort_keys=True)

    assert response["ok"] is False
    assert response["result"]["verdict"] == ActionVerdict.DENY.value
    assert response["result"]["metadata"]["error_code"] == "broker_error"
    assert supplied_secret not in serialized
    assert REDACTED not in response["error"]["message"]
