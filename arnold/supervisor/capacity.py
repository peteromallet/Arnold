"""In-memory capacity gates for supervisor worker pools."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from threading import Lock
from typing import Mapping

__all__ = [
    "CapacityDecision",
    "CapacityGate",
    "CapacityGrant",
    "CapacityPool",
    "CapacityPoolConfig",
    "CapacityStatus",
]


class CapacityStatus(StrEnum):
    GRANTED = "granted"
    DUPLICATE = "duplicate"
    RELEASED = "released"
    WAIT = "wait"
    REJECT = "reject"


@dataclass(frozen=True)
class CapacityPoolConfig:
    name: str
    limit: int
    wait: bool = True
    retry_after_seconds: float | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("capacity pool name is required")
        if self.limit < 1:
            raise ValueError("capacity pool limit must be at least 1")
        if self.retry_after_seconds is not None and self.retry_after_seconds < 0:
            raise ValueError("retry_after_seconds must be non-negative")


@dataclass(frozen=True)
class CapacityGrant:
    pool: str
    lease_id: str
    fencing_token: int
    units: int = 1

    @property
    def identity(self) -> tuple[str, int]:
        return (self.lease_id, self.fencing_token)

    def to_envelope_fields(self) -> dict[str, int | str]:
        return {
            "lease_id": self.lease_id,
            "fencing_token": self.fencing_token,
            "capacity_grant": self.units,
        }


@dataclass(frozen=True)
class CapacityDecision:
    status: CapacityStatus
    pool: str
    lease_id: str | None = None
    fencing_token: int | None = None
    granted_units: int = 0
    used_units: int = 0
    limit: int = 0
    retry_after_seconds: float | None = None
    reason: str | None = None

    @property
    def granted(self) -> bool:
        return self.status in {CapacityStatus.GRANTED, CapacityStatus.DUPLICATE}

    @property
    def should_wait(self) -> bool:
        return self.status is CapacityStatus.WAIT

    @property
    def rejected(self) -> bool:
        return self.status is CapacityStatus.REJECT


@dataclass
class CapacityPool:
    config: CapacityPoolConfig
    grants: dict[tuple[str, int], CapacityGrant] = field(default_factory=dict)

    @property
    def used_units(self) -> int:
        return sum(grant.units for grant in self.grants.values())


class CapacityGate:
    """Thread-safe configured pool capacity gate."""

    def __init__(self, pools: Mapping[str, CapacityPoolConfig] | None = None) -> None:
        configs = pools or {"default": CapacityPoolConfig(name="default", limit=1)}
        self._pools = {
            name: CapacityPool(config=config)
            for name, config in configs.items()
        }
        self._lock = Lock()

    def acquire(
        self,
        pool: str,
        *,
        lease_id: str,
        fencing_token: int,
        units: int = 1,
    ) -> CapacityDecision:
        if not lease_id:
            raise ValueError("lease_id is required")
        if fencing_token < 0:
            raise ValueError("fencing_token must be non-negative")
        if units < 1:
            raise ValueError("capacity units must be at least 1")
        with self._lock:
            capacity_pool = self._pool(pool)
            identity = (lease_id, fencing_token)
            existing = capacity_pool.grants.get(identity)
            if existing is not None:
                return self._decision(
                    CapacityStatus.DUPLICATE,
                    capacity_pool,
                    existing,
                    reason="duplicate_grant_suppressed",
                )
            used = capacity_pool.used_units
            if used + units <= capacity_pool.config.limit:
                grant = CapacityGrant(pool, lease_id, fencing_token, units)
                capacity_pool.grants[identity] = grant
                return self._decision(CapacityStatus.GRANTED, capacity_pool, grant)
            status = (
                CapacityStatus.WAIT if capacity_pool.config.wait else CapacityStatus.REJECT
            )
            return CapacityDecision(
                status=status,
                pool=pool,
                lease_id=lease_id,
                fencing_token=fencing_token,
                used_units=used,
                limit=capacity_pool.config.limit,
                retry_after_seconds=capacity_pool.config.retry_after_seconds,
                reason="capacity_exhausted",
            )

    def release(
        self,
        pool: str,
        *,
        lease_id: str,
        fencing_token: int,
    ) -> CapacityDecision:
        with self._lock:
            capacity_pool = self._pool(pool)
            grant = capacity_pool.grants.pop((lease_id, fencing_token), None)
            if grant is None:
                return CapacityDecision(
                    status=CapacityStatus.RELEASED,
                    pool=pool,
                    lease_id=lease_id,
                    fencing_token=fencing_token,
                    used_units=capacity_pool.used_units,
                    limit=capacity_pool.config.limit,
                    reason="grant_absent",
                )
            return self._decision(CapacityStatus.RELEASED, capacity_pool, grant)

    def usage(self, pool: str) -> CapacityDecision:
        with self._lock:
            capacity_pool = self._pool(pool)
            return CapacityDecision(
                status=CapacityStatus.GRANTED,
                pool=pool,
                used_units=capacity_pool.used_units,
                limit=capacity_pool.config.limit,
            )

    def _pool(self, pool: str) -> CapacityPool:
        try:
            return self._pools[pool]
        except KeyError as exc:
            raise ValueError(f"unknown capacity pool: {pool}") from exc

    @staticmethod
    def _decision(
        status: CapacityStatus,
        pool: CapacityPool,
        grant: CapacityGrant,
        *,
        reason: str | None = None,
    ) -> CapacityDecision:
        return CapacityDecision(
            status=status,
            pool=grant.pool,
            lease_id=grant.lease_id,
            fencing_token=grant.fencing_token,
            granted_units=grant.units,
            used_units=pool.used_units,
            limit=pool.config.limit,
            retry_after_seconds=pool.config.retry_after_seconds,
            reason=reason,
        )
