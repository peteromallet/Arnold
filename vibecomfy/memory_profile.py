from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from enum import IntEnum
from typing import Any, Literal, Mapping, TypeVar


PROFILE_LABELS: Mapping[int, str] = {
    1: "Low RAM",
    2: "High RAM",
    3: "Low VRAM",
    4: "Very Low VRAM",
    5: "Minimum",
}

_SESSION_OVERRIDES: Mapping[int, Mapping[str, object]] = {
    1: {"vram_policy": "high", "cache_policy": "smart"},
    2: {"vram_policy": "high", "cache_policy": "lru:32"},
    3: {"vram_policy": "normal", "cache_policy": "smart"},
    4: {"vram_policy": "low", "cache_policy": "classic", "reserve_vram_gb": 2.0},
    5: {
        "vram_policy": "low",
        "cache_policy": "lru:1",
        "disable_smart_memory": True,
        "reserve_vram_gb": 4.0,
    },
}

Precedence = Literal["profile", "config"]
T = TypeVar("T")


class MemoryProfile(IntEnum):
    LOW_RAM = 1
    MAX_PERFORMANCE = 1
    HIGH_RAM = 2
    LOW_VRAM = 3
    BALANCED = 3
    VERY_LOW_VRAM = 4
    CONSERVATIVE = 4
    MINIMUM = 5

    @classmethod
    def parse(cls, value: int | "MemoryProfile") -> "MemoryProfile":
        if isinstance(value, cls):
            return value
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("memory profile must be an integer from 1 to 5")
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError("memory profile must be an integer from 1 to 5") from exc

    @property
    def label(self) -> str:
        return PROFILE_LABELS[int(self)]

    def serialize(self) -> int:
        return int(self)

    def to_session_overrides(self) -> dict[str, object]:
        return dict(_SESSION_OVERRIDES[int(self)])

    def to_telemetry(self) -> dict[str, object]:
        return {"memory_profile": int(self), "memory_profile_label": self.label}


def parse_memory_profile(value: int | MemoryProfile) -> MemoryProfile:
    return MemoryProfile.parse(value)


def serialize_memory_profile(value: int | MemoryProfile) -> int:
    return MemoryProfile.parse(value).serialize()


def memory_profile_telemetry(value: int | MemoryProfile) -> dict[str, object]:
    return MemoryProfile.parse(value).to_telemetry()


def session_overrides_for_memory_profile(value: int | MemoryProfile) -> dict[str, object]:
    return MemoryProfile.parse(value).to_session_overrides()


def apply_memory_profile_overrides(
    config: T,
    profile: int | MemoryProfile,
    *,
    precedence: Precedence,
    default_config: T | None = None,
) -> T:
    if precedence not in {"profile", "config"}:
        raise ValueError("precedence must be 'profile' or 'config'")
    if not is_dataclass(config) or isinstance(config, type):
        raise TypeError("config must be a dataclass instance")

    parsed = MemoryProfile.parse(profile)
    overrides = parsed.to_session_overrides()
    if precedence == "config":
        base = default_config if default_config is not None else type(config)()
        defaults_by_name = {field.name: getattr(base, field.name) for field in fields(base)}
        overrides = {
            key: value
            for key, value in overrides.items()
            if getattr(config, key, None) == defaults_by_name.get(key)
        }
    return replace(config, **overrides)


__all__ = [
    "MemoryProfile",
    "Precedence",
    "PROFILE_LABELS",
    "apply_memory_profile_overrides",
    "memory_profile_telemetry",
    "parse_memory_profile",
    "serialize_memory_profile",
    "session_overrides_for_memory_profile",
]
