from __future__ import annotations

import base64
import json
import os
import re
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping


DEFAULT_HIVEMIND_EDGE_URL = (
    "https://ujlwuvkrxlvoswwkerdf.supabase.co/functions/v1/submit-vibecomfy-rating"
)
DEFAULT_MAX_ZIP_BYTES = 10 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 10.0

EDGE_URL_ENV = "HIVEMIND_SUBMIT_RATING_URL"
CONTRIBUTOR_KEY_ENV = "HIVEMIND_CONTRIBUTOR_KEY"
ANON_KEY_ENV = "HIVEMIND_ANON_KEY"
MAX_ZIP_BYTES_ENV = "VIBECOMFY_RATING_MAX_ZIP_BYTES"
DEFAULT_MAX_COMMENT_LENGTH = 2000
DEFAULT_MAX_PACK_COMMENT_LENGTH = 2000

_CONTRIBUTOR_KEY_RE = re.compile(r"^hm_[0-9a-f]{64}$")
_ID_PART_RE = re.compile(r"^[A-Za-z0-9._~-]+$")
_BASE64_RE = re.compile(
    r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$"
)


class HivemindFeedbackError(RuntimeError):
    def __init__(self, code: str, detail: str, *, status: int = 400) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status

    def to_response(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": self.code,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class HivemindFeedbackConfig:
    edge_url: str
    contributor_key: str
    anon_key: str = ""
    max_zip_bytes: int = DEFAULT_MAX_ZIP_BYTES
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS


@dataclass(frozen=True)
class ProxyHTTPResponse:
    status: int
    body: bytes
    headers: Mapping[str, str] | None = None


Transport = Callable[[str, bytes, Mapping[str, str], float], ProxyHTTPResponse]


def _positive_int(value: str | None, *, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _read_required_string(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or value == "":
        raise HivemindFeedbackError(
            "validation",
            f"field '{field}' is required and must be a non-empty string.",
        )
    return value


def _read_optional_string(payload: Mapping[str, Any], field: str, max_length: int) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise HivemindFeedbackError(
            "validation",
            f"field '{field}' must be a string when provided.",
        )
    if len(value) > max_length:
        raise HivemindFeedbackError(
            "validation",
            f"field '{field}' must be at most {max_length} characters.",
        )
    return value


def _validate_response_ids(response_id: str, session_id: str, turn_id: str) -> None:
    if not _ID_PART_RE.fullmatch(session_id):
        raise HivemindFeedbackError(
            "validation",
            "field 'session_id' must be a non-empty URL-safe id.",
        )
    if not _ID_PART_RE.fullmatch(turn_id):
        raise HivemindFeedbackError(
            "validation",
            "field 'turn_id' must be a non-empty URL-safe id.",
        )
    if response_id != f"{session_id}/{turn_id}":
        raise HivemindFeedbackError(
            "validation",
            "field 'response_id' must be formatted as '<session_id>/<turn_id>'.",
        )


def normalize_contributor_key(value: str | None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HivemindFeedbackError(
            "configuration",
            f"{CONTRIBUTOR_KEY_ENV} is required on the server.",
            status=503,
        )
    normalized = value.strip().lower()
    if not _CONTRIBUTOR_KEY_RE.fullmatch(normalized):
        raise HivemindFeedbackError(
            "configuration",
            f"{CONTRIBUTOR_KEY_ENV} must be hm_<64 hex chars>.",
            status=503,
        )
    return normalized


def normalize_anon_key(value: str | None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HivemindFeedbackError(
            "configuration",
            f"{ANON_KEY_ENV} is required on the server.",
            status=503,
        )
    return value.strip()


def load_hivemind_feedback_config(
    env: Mapping[str, str] | None = None,
) -> HivemindFeedbackConfig:
    source = env if env is not None else os.environ
    edge_url = str(source.get(EDGE_URL_ENV) or DEFAULT_HIVEMIND_EDGE_URL).strip()
    if not edge_url:
        raise HivemindFeedbackError(
            "configuration",
            f"{EDGE_URL_ENV} must not be empty.",
            status=503,
        )
    return HivemindFeedbackConfig(
        edge_url=edge_url,
        contributor_key=normalize_contributor_key(source.get(CONTRIBUTOR_KEY_ENV)),
        anon_key=normalize_anon_key(source.get(ANON_KEY_ENV)),
        max_zip_bytes=_positive_int(source.get(MAX_ZIP_BYTES_ENV), default=DEFAULT_MAX_ZIP_BYTES),
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )


def _validated_config(config: HivemindFeedbackConfig) -> HivemindFeedbackConfig:
    edge_url = str(config.edge_url or "").strip()
    if not edge_url:
        raise HivemindFeedbackError(
            "configuration",
            f"{EDGE_URL_ENV} must not be empty.",
            status=503,
        )
    return HivemindFeedbackConfig(
        edge_url=edge_url,
        contributor_key=normalize_contributor_key(config.contributor_key),
        anon_key=normalize_anon_key(config.anon_key),
        max_zip_bytes=config.max_zip_bytes,
        timeout_seconds=config.timeout_seconds,
    )


def _decoded_zip_bytes(pack_zip_base64: str) -> bytes:
    if not pack_zip_base64 or len(pack_zip_base64) % 4 != 0:
        raise HivemindFeedbackError(
            "validation",
            "field 'pack_zip_base64' must be valid base64.",
        )
    if not _BASE64_RE.fullmatch(pack_zip_base64):
        raise HivemindFeedbackError(
            "validation",
            "field 'pack_zip_base64' must be valid base64.",
        )
    try:
        return base64.b64decode(pack_zip_base64, validate=True)
    except Exception as exc:
        raise HivemindFeedbackError(
            "validation",
            "field 'pack_zip_base64' must be valid base64.",
        ) from exc


def _has_zip_signature(decoded: bytes) -> bool:
    return decoded.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))


def _validate_payload(payload: Any, *, max_zip_bytes: int) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HivemindFeedbackError("validation", "Request body must be a JSON object.")
    forwarded = dict(payload)
    response_id = _read_required_string(forwarded, "response_id")
    session_id = _read_required_string(forwarded, "session_id")
    turn_id = _read_required_string(forwarded, "turn_id")
    _validate_response_ids(response_id, session_id, turn_id)
    rating = forwarded.get("rating")
    if not isinstance(rating, int) or isinstance(rating, bool):
        raise HivemindFeedbackError(
            "validation",
            "field 'rating' is required and must be an integer.",
        )
    if rating < 1 or rating > 10:
        raise HivemindFeedbackError(
            "validation",
            "field 'rating' must be between 1 and 10.",
        )
    _read_optional_string(forwarded, "comment", DEFAULT_MAX_COMMENT_LENGTH)
    pack_shared = forwarded.get("pack_shared")
    if not isinstance(pack_shared, bool):
        raise HivemindFeedbackError(
            "validation",
            "field 'pack_shared' is required and must be a boolean.",
        )
    pack_comment = _read_optional_string(
        forwarded,
        "pack_comment",
        DEFAULT_MAX_PACK_COMMENT_LENGTH,
    )
    pack_zip = forwarded.get("pack_zip_base64")
    if not pack_shared:
        if pack_zip is not None:
            raise HivemindFeedbackError(
                "validation",
                "field 'pack_zip_base64' is only allowed when pack_shared is true.",
            )
        if pack_comment is not None:
            raise HivemindFeedbackError(
                "validation",
                "field 'pack_comment' is only allowed when pack_shared is true.",
            )
        return forwarded
    if not isinstance(pack_zip, str):
        raise HivemindFeedbackError(
            "validation",
            "field 'pack_zip_base64' is required when pack_shared is true.",
        )
    decoded = _decoded_zip_bytes(pack_zip)
    if len(decoded) > max_zip_bytes:
        raise HivemindFeedbackError(
            "validation",
            f"field 'pack_zip_base64' decodes to more than {max_zip_bytes} bytes.",
            status=413,
        )
    if not _has_zip_signature(decoded):
        raise HivemindFeedbackError(
            "validation",
            "field 'pack_zip_base64' must decode to a ZIP file.",
        )
    return forwarded


def _default_transport(
    url: str,
    body: bytes,
    headers: Mapping[str, str],
    timeout_seconds: float,
) -> ProxyHTTPResponse:
    request = urllib.request.Request(
        url,
        data=body,
        headers=dict(headers),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return ProxyHTTPResponse(
            status=response.status,
            body=response.read(),
            headers=dict(response.headers.items()),
        )


def _parse_json_response(body: bytes) -> Any:
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return None


def submit_hivemind_feedback(
    payload: Any,
    *,
    config: HivemindFeedbackConfig | None = None,
    transport: Transport | None = None,
) -> tuple[dict[str, Any], int]:
    try:
        resolved_config = _validated_config(config or load_hivemind_feedback_config())
        forwarded = _validate_payload(
            payload,
            max_zip_bytes=resolved_config.max_zip_bytes,
        )
        body = json.dumps(forwarded, separators=(",", ":"), sort_keys=True).encode("utf-8")
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {resolved_config.anon_key}",
            "x-contributor-key": resolved_config.contributor_key,
        }
        response = (transport or _default_transport)(
            resolved_config.edge_url,
            body,
            headers,
            resolved_config.timeout_seconds,
        )
    except HivemindFeedbackError as exc:
        return exc.to_response(), exc.status
    except urllib.error.HTTPError as exc:
        parsed = _parse_json_response(exc.read())
        if isinstance(parsed, dict):
            return {"ok": False, **parsed}, exc.code
        return {"ok": False, "error": "upstream", "detail": "Hivemind rejected the request."}, exc.code
    except (TimeoutError, socket.timeout) as exc:
        return {"ok": False, "error": "timeout", "detail": str(exc) or "Hivemind request timed out."}, 504
    except urllib.error.URLError:
        return {"ok": False, "error": "upstream", "detail": "Could not reach Hivemind."}, 502
    except Exception:
        return {"ok": False, "error": "upstream", "detail": "Hivemind rating submission failed."}, 502

    parsed = _parse_json_response(response.body)
    if not isinstance(parsed, dict):
        parsed = {}
    if 200 <= response.status < 300:
        return {"ok": True, **parsed}, response.status
    return {"ok": False, **parsed}, response.status
