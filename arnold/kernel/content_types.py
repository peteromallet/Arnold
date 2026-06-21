"""Content type registration contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class RetentionPolicy(StrEnum):
    """Neutral retention policy labels."""

    EPHEMERAL = "ephemeral"
    RUN = "run"
    AUDIT = "audit"
    LEGAL_HOLD = "legal_hold"


@dataclass(frozen=True)
class RetentionPin:
    """Reason a generated artifact must be retained."""

    policy: RetentionPolicy
    reason: str


@dataclass(frozen=True)
class ContentTypeRegistration:
    """Content type schema registration."""

    type_id: str
    schema_version: str
    schema_hash: str
    retention_policy: RetentionPolicy = RetentionPolicy.RUN


def schema_hash(schema: Mapping[str, object]) -> str:
    """Return the canonical hash for a content-type schema document."""

    payload = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ContentTypeRegistry:
    """Immutable-by-default registry for neutral content-type declarations."""

    def __init__(
        self, registrations: Mapping[str, ContentTypeRegistration] | None = None
    ) -> None:
        self._registrations: dict[str, ContentTypeRegistration] = dict(
            registrations or {}
        )

    def register(
        self, registration: ContentTypeRegistration
    ) -> ContentTypeRegistration:
        existing = self._registrations.get(registration.type_id)
        if existing is not None and existing != registration:
            raise ValueError(f"content type already registered: {registration.type_id}")
        self._registrations[registration.type_id] = registration
        return registration

    def require(self, type_id: str) -> ContentTypeRegistration:
        try:
            return self._registrations[type_id]
        except KeyError as exc:
            raise KeyError(f"unknown content type: {type_id}") from exc

    def as_mapping(self) -> Mapping[str, ContentTypeRegistration]:
        return MappingProxyType(dict(self._registrations))
