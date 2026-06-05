"""Shared canonical projection bytes, hashes, and HMAC helpers."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import hmac
import json
from typing import Any, Mapping


WARRANT_HMAC_ALGORITHM = "hmac-sha256"


def _canonicalize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _canonicalize(value.model_dump(mode="json"))
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, Mapping):
        return {str(key): _canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    return value


def canonical_projection_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes for a projection-like value."""
    return json.dumps(
        _canonicalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_hex(value: bytes | bytearray | memoryview) -> str:
    """Return the bare SHA-256 hex digest for bytes."""
    return hashlib.sha256(bytes(value)).hexdigest()


def canonical_projection_sha256(value: Any) -> str:
    """Return the bare SHA-256 hex digest for canonical projection bytes."""
    return sha256_hex(canonical_projection_bytes(value))


def sha256_uri(value: bytes | bytearray | memoryview) -> str:
    """Return the `sha256:<hex>` URI for bytes."""
    return f"sha256:{sha256_hex(value)}"


def canonical_projection_sha256_uri(value: Any) -> str:
    """Return the `sha256:<hex>` URI for canonical projection bytes."""
    return sha256_uri(canonical_projection_bytes(value))


def _key_bytes(key: str | bytes | bytearray | memoryview) -> bytes:
    raw = key.encode("utf-8") if isinstance(key, str) else bytes(key)
    if not raw:
        raise ValueError("warrant signing key must be non-empty")
    return raw


def hmac_sha256_hex(
    key: str | bytes | bytearray | memoryview,
    payload: bytes | bytearray | memoryview,
) -> str:
    """Return a hex HMAC-SHA256 signature, rejecting empty keys loudly."""
    return hmac.new(_key_bytes(key), bytes(payload), hashlib.sha256).hexdigest()


def sign_canonical_projection(
    value: Any,
    *,
    warrant_key: str | bytes | bytearray | memoryview,
    key_id: str | None = None,
    signed_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Sign canonical projection bytes and return a WarrantSignature payload."""
    payload = canonical_projection_bytes(value)
    signature: dict[str, Any] = {
        "algorithm": WARRANT_HMAC_ALGORITHM,
        "signed_payload_sha256": sha256_uri(payload),
        "signature": hmac_sha256_hex(warrant_key, payload),
    }
    if key_id is not None:
        signature["key_id"] = key_id
    if signed_at is not None:
        if isinstance(signed_at, datetime):
            signature["signed_at"] = (
                signed_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
            )
        else:
            signature["signed_at"] = signed_at
    return signature


def verify_canonical_projection_signature(
    value: Any,
    signature: Mapping[str, Any],
    *,
    warrant_key: str | bytes | bytearray | memoryview,
) -> bool:
    """Verify a WarrantSignature-like mapping against canonical projection bytes."""
    if signature.get("algorithm", WARRANT_HMAC_ALGORITHM) != WARRANT_HMAC_ALGORITHM:
        return False
    payload = canonical_projection_bytes(value)
    expected_sha = sha256_uri(payload)
    if signature.get("signed_payload_sha256") != expected_sha:
        return False
    expected_signature = hmac_sha256_hex(warrant_key, payload)
    actual_signature = signature.get("signature")
    return isinstance(actual_signature, str) and hmac.compare_digest(
        actual_signature,
        expected_signature,
    )


__all__ = [
    "WARRANT_HMAC_ALGORITHM",
    "canonical_projection_bytes",
    "canonical_projection_sha256",
    "canonical_projection_sha256_uri",
    "hmac_sha256_hex",
    "sha256_hex",
    "sha256_uri",
    "sign_canonical_projection",
    "verify_canonical_projection_signature",
]
