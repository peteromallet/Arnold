"""Agent-side client for the security broker protocol."""

from __future__ import annotations

import json
import logging
import os
import socket
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from arnold.security.broker_service import PROTOCOL_VERSION
from arnold.security.llm_proxy import LlmProxyCredential, credential_from_payload
from arnold.security.policy import SecurityPolicy
from arnold.security.redaction import redact_mapping, redact_text
from arnold.security.types import ActionRequest, ActionResult, ActionVerdict, RetentionPolicy

LOGGER = logging.getLogger(__name__)

BROKER_SOCKET_ENV = "ARNOLD_BROKER_SOCKET"
BROKER_URL_ENV = "ARNOLD_BROKER_URL"
DEFAULT_TIMEOUT_SECONDS = 2.0


class BrokerClientError(RuntimeError):
    """Sanitized client-side broker protocol failure."""


@dataclass(frozen=True, slots=True)
class BrokerClient:
    """Evaluate broker-covered actions through a sidecar when configured."""

    socket_path: str | None = None
    url: str | None = None
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    fallback_policy: SecurityPolicy = SecurityPolicy()

    @classmethod
    def from_environment(
        cls,
        *,
        environ: Mapping[str, str] | None = None,
        fallback_policy: SecurityPolicy | None = None,
    ) -> "BrokerClient":
        source = os.environ if environ is None else environ
        return cls(
            socket_path=str(source.get(BROKER_SOCKET_ENV) or "").strip() or None,
            url=str(source.get(BROKER_URL_ENV) or "").strip() or None,
            fallback_policy=fallback_policy or SecurityPolicy(),
        )

    @property
    def broker_mode_enabled(self) -> bool:
        return bool(self.socket_path or self.url)

    def evaluate_action(self, request: ActionRequest) -> ActionResult:
        """Return a broker decision, failing closed when broker mode is unreachable."""

        if not self.broker_mode_enabled:
            return self.fallback_policy.evaluate(request)

        try:
            response = self._send(
                {
                    "version": PROTOCOL_VERSION,
                    "operation": "evaluate_action",
                    "request": _request_to_payload(request),
                }
            )
            return _result_from_response(response)
        except Exception as exc:
            LOGGER.warning("security broker unavailable; denying covered action: %s", redact_text(str(exc)))
            return fail_closed_result(request, reason="Broker unavailable")

    def issue_llm_proxy_credential(
        self,
        *,
        provider: str,
        proxy_base_url: str,
        upstream_base_url: str,
    ) -> LlmProxyCredential:
        """Return a broker-scoped LLM proxy credential for a covered provider."""

        if not self.broker_mode_enabled:
            raise BrokerClientError("broker endpoint is not configured")
        try:
            response = self._send(
                {
                    "version": PROTOCOL_VERSION,
                    "operation": "issue_llm_proxy_credential",
                    "provider": redact_text(provider),
                    "proxy_base_url": redact_text(proxy_base_url),
                    "upstream_base_url": redact_text(upstream_base_url),
                },
                redact_response=False,
            )
        except Exception as exc:
            raise BrokerClientError("broker LLM proxy credential request failed") from exc
        return credential_from_payload(provider, response)

    def _send(self, payload: Mapping[str, Any], *, redact_response: bool = True) -> dict[str, Any]:
        if self.socket_path:
            return self._send_unix(payload, redact_response=redact_response)
        if self.url:
            return self._send_http(payload, redact_response=redact_response)
        raise BrokerClientError("broker endpoint is not configured")

    def _send_unix(self, payload: Mapping[str, Any], *, redact_response: bool = True) -> dict[str, Any]:
        body = (json.dumps(redact_mapping(payload), sort_keys=True) + "\n").encode("utf-8")
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(self.timeout_seconds)
                client.connect(self.socket_path or "")
                client.sendall(body)
                raw = _read_line(client)
        except OSError as exc:
            raise BrokerClientError("broker socket is unreachable") from exc
        return _decode_response(raw, redact_response=redact_response)

    def _send_http(self, payload: Mapping[str, Any], *, redact_response: bool = True) -> dict[str, Any]:
        body = json.dumps(redact_mapping(payload), sort_keys=True).encode("utf-8")
        req = urllib.request.Request(
            self.url or "",
            data=body,
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read(1024 * 1024)
        except (OSError, urllib.error.URLError) as exc:
            raise BrokerClientError("broker URL is unreachable") from exc
        return _decode_response(raw, redact_response=redact_response)


def fail_closed_result(request: ActionRequest, *, reason: str) -> ActionResult:
    return ActionResult(
        verdict=ActionVerdict.DENY,
        summary=f"{reason}; covered action denied",
        metadata={
            "action_type": request.action_type,
            "provider": request.provider,
            "repo": request.repo,
            "branch": request.branch,
            "broker_mode": True,
            "fail_closed": True,
        },
        retention_policy=RetentionPolicy.AUDIT,
    )


def _request_to_payload(request: ActionRequest) -> dict[str, Any]:
    return {
        "action_type": redact_text(request.action_type),
        "provider": redact_text(request.provider) if request.provider is not None else None,
        "repo": redact_text(request.repo) if request.repo is not None else None,
        "branch": redact_text(request.branch) if request.branch is not None else None,
        "command": [redact_text(item) for item in request.command],
        "force": request.force,
        "metadata": redact_mapping(request.metadata),
    }


def _read_line(client: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = client.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    return b"".join(chunks).split(b"\n", 1)[0]


def _decode_response(raw: bytes, *, redact_response: bool = True) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BrokerClientError("broker returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise BrokerClientError("broker returned invalid payload")
    return redact_mapping(payload) if redact_response else payload


def _result_from_response(response: Mapping[str, Any]) -> ActionResult:
    raw_result = response.get("result")
    if not isinstance(raw_result, Mapping):
        raise BrokerClientError("broker response did not include an action result")
    try:
        verdict = ActionVerdict(str(raw_result.get("verdict")))
    except ValueError as exc:
        raise BrokerClientError("broker response included an invalid verdict") from exc
    metadata = raw_result.get("metadata", {})
    if not isinstance(metadata, Mapping):
        metadata = {}
    effect_refs = raw_result.get("effect_refs", ())
    if not isinstance(effect_refs, (list, tuple)):
        effect_refs = ()
    retention_value = raw_result.get("retention_policy") or RetentionPolicy.AUDIT.value
    try:
        retention_policy = RetentionPolicy(str(retention_value))
    except ValueError:
        retention_policy = RetentionPolicy.AUDIT
    return ActionResult(
        verdict=verdict,
        summary=str(raw_result.get("summary") or "Broker returned a decision"),
        action_id=raw_result.get("action_id") if raw_result.get("action_id") is not None else None,
        effect_refs=tuple(str(item) for item in effect_refs),
        metadata=dict(metadata),
        retention_policy=retention_policy,
    )


__all__ = [
    "BROKER_SOCKET_ENV",
    "BROKER_URL_ENV",
    "BrokerClient",
    "BrokerClientError",
    "DEFAULT_TIMEOUT_SECONDS",
    "fail_closed_result",
]
