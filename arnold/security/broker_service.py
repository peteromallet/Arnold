"""Security broker sidecar protocol handler.

The broker process is the only M2 component that may load covered production
secrets. Agent-visible protocol responses are restricted to sanitized
``ActionResult`` payloads and non-secret credential status metadata.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import socketserver
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from arnold.security.policy import SecurityPolicy
from arnold.security.redaction import redact_mapping, redact_text
from arnold.security.types import ActionRequest, ActionResult, ActionVerdict

LOGGER = logging.getLogger(__name__)

PROTOCOL_VERSION = 1
DEFAULT_COVERED_SECRET_NAMES: tuple[str, ...] = (
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GIT_ASKPASS_TOKEN",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "FIREWORKS_API_KEY",
    "FIREWORKS_AI_API_KEY",
    "ZHIPU_API_KEY",
    "GLM_API_KEY",
    "ZAI_API_KEY",
    "KIMI_API_KEY",
    "MINIMAX_API_KEY",
    "MIMO_API_KEY",
    "ANTHROPIC_API_KEY",
)


class BrokerServiceError(RuntimeError):
    """Raised for sanitized broker protocol errors."""


@dataclass(frozen=True, slots=True)
class BrokerSecretStore:
    """Broker-owned view of covered secrets loaded from the process environment."""

    _configured_names: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_environment(
        cls,
        names: tuple[str, ...] = DEFAULT_COVERED_SECRET_NAMES,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> "BrokerSecretStore":
        source = os.environ if environ is None else environ
        configured = frozenset(name for name in names if str(source.get(name, "")).strip())
        return cls(configured)

    def is_configured(self, name: str) -> bool:
        return name in self._configured_names

    def status_payload(self) -> dict[str, Any]:
        """Return non-secret credential status for diagnostics."""

        return {
            "configured_names": sorted(self._configured_names),
            "configured_count": len(self._configured_names),
        }


@dataclass(slots=True)
class BrokerService:
    """Handle sanitized broker protocol requests."""

    policy: SecurityPolicy = field(default_factory=SecurityPolicy)
    secrets: BrokerSecretStore = field(default_factory=BrokerSecretStore.from_environment)

    def handle_payload(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Process one JSON-compatible protocol payload."""

        try:
            response = self._handle_payload(payload)
        except Exception as exc:  # pragma: no cover - defensive boundary
            LOGGER.warning("broker request failed: %s", redact_text(str(exc)))
            return _error_response("broker_error", "Broker request failed")
        return redact_mapping(response)

    def _handle_payload(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if payload.get("version") != PROTOCOL_VERSION:
            return _error_response("unsupported_version", "Unsupported broker protocol version")

        operation = payload.get("operation")
        if operation == "evaluate_action":
            raw_request = payload.get("request")
            if not isinstance(raw_request, Mapping):
                return _error_response("invalid_request", "Broker request must include an action")
            request = _action_request_from_mapping(raw_request)
            result = self.policy.evaluate(request)
            return {
                "ok": True,
                "version": PROTOCOL_VERSION,
                "result": result.to_json(),
                "broker_status": self.secrets.status_payload(),
            }

        if operation == "credential_status":
            return {
                "ok": True,
                "version": PROTOCOL_VERSION,
                "broker_status": self.secrets.status_payload(),
            }

        if operation == "issue_llm_proxy_credential":
            provider = _optional_string(payload.get("provider")) or "unknown"
            proxy_base_url = _optional_string(payload.get("proxy_base_url"))
            upstream_base_url = _optional_string(payload.get("upstream_base_url"))
            if not proxy_base_url or not upstream_base_url:
                return _error_response("invalid_request", "LLM proxy credential request is incomplete")
            return {
                "ok": True,
                "version": PROTOCOL_VERSION,
                "proxy": {
                    "provider": provider,
                    "base_url": proxy_base_url.rstrip("/"),
                    "broker_auth": f"arnold-broker-{uuid.uuid4().hex}",
                    "upstream_base_url": upstream_base_url.rstrip("/"),
                    "expires_at": int(time.time()) + 900,
                },
                "broker_status": self.secrets.status_payload(),
            }

        return _error_response("unknown_operation", "Unknown broker operation")


class _UnixBrokerHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline(1024 * 1024)
        service: BrokerService = self.server.service  # type: ignore[attr-defined]
        try:
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, Mapping):
                raise BrokerServiceError("payload must be a JSON object")
            response = service.handle_payload(payload)
        except Exception as exc:  # pragma: no cover - exercised through client tests
            LOGGER.warning("broker protocol decode failed: %s", redact_text(str(exc)))
            response = _error_response("invalid_json", "Invalid broker payload")
        self.wfile.write((json.dumps(response, sort_keys=True) + "\n").encode("utf-8"))


class UnixBrokerServer(socketserver.ThreadingUnixStreamServer):
    """Small Unix-domain sidecar server for local broker deployments."""

    allow_reuse_address = True

    def __init__(self, socket_path: str, service: BrokerService | None = None) -> None:
        self.service = service or BrokerService()
        super().__init__(socket_path, _UnixBrokerHandler)


def _action_request_from_mapping(payload: Mapping[str, Any]) -> ActionRequest:
    command = payload.get("command", ())
    if not isinstance(command, (list, tuple)):
        command = ()
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, Mapping):
        metadata = {}
    return ActionRequest(
        action_type=str(payload.get("action_type") or ""),
        provider=_optional_string(payload.get("provider")),
        repo=_optional_string(payload.get("repo")),
        branch=_optional_string(payload.get("branch")),
        command=tuple(str(item) for item in command),
        force=bool(payload.get("force", False)),
        metadata=dict(metadata),
    )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _error_response(code: str, message: str) -> dict[str, Any]:
    result = ActionResult(
        verdict=ActionVerdict.DENY,
        summary=message,
        metadata={"error_code": code},
    )
    return {
        "ok": False,
        "version": PROTOCOL_VERSION,
        "error": {"code": code, "message": redact_text(message)},
        "result": result.to_json(),
    }


def serve_unix(socket_path: str) -> None:
    """Run a blocking Unix-domain broker sidecar."""

    if os.path.exists(socket_path):
        os.unlink(socket_path)
    with UnixBrokerServer(socket_path) as server:
        LOGGER.info("broker listening on unix socket %s", socket_path)
        server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Arnold security broker sidecar")
    parser.add_argument("--socket", required=True, help="Unix-domain socket path to listen on")
    args = parser.parse_args(argv)
    serve_unix(args.socket)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "BrokerSecretStore",
    "BrokerService",
    "BrokerServiceError",
    "DEFAULT_COVERED_SECRET_NAMES",
    "PROTOCOL_VERSION",
    "UnixBrokerServer",
    "serve_unix",
]
