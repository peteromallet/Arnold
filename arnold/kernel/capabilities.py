"""Capability identity and dispatch contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class CapabilityId:
    """Neutral capability identifier."""

    namespace: str
    name: str

    @property
    def value(self) -> str:
        return f"{self.namespace}:{self.name}"


@dataclass(frozen=True)
class DispatchKey:
    """Policy-neutral dispatch key for later execution registries."""

    capability_id: CapabilityId
    route: str = "default"


@dataclass(frozen=True)
class CapabilityCheck:
    """Result carrier for capability guard evaluation."""

    capability_id: CapabilityId
    allowed: bool
    reason: str | None = None
