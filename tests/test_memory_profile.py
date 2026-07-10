from __future__ import annotations

import pytest

from vibecomfy.memory_profile import (
    MemoryProfile,
    apply_memory_profile_overrides,
    memory_profile_telemetry,
    parse_memory_profile,
    serialize_memory_profile,
    session_overrides_for_memory_profile,
)
from vibecomfy.runtime.session import SessionConfig


def test_memory_profiles_parse_integer_values_and_expose_labels() -> None:
    expected = {
        1: "Low RAM",
        2: "High RAM",
        3: "Low VRAM",
        4: "Very Low VRAM",
        5: "Minimum",
    }

    for value, label in expected.items():
        profile = parse_memory_profile(value)
        assert profile.serialize() == value
        assert serialize_memory_profile(profile) == value
        assert profile.label == label


@pytest.mark.parametrize("value", [0, 6, -1, 1.0, "1", None, True, False])
def test_memory_profile_rejects_non_integer_or_out_of_range_values(value: object) -> None:
    with pytest.raises(ValueError, match="integer from 1 to 5"):
        parse_memory_profile(value)  # type: ignore[arg-type]


def test_memory_profile_session_overrides_match_sprint_1_mapping() -> None:
    assert session_overrides_for_memory_profile(1) == {"vram_policy": "high", "cache_policy": "smart"}
    assert session_overrides_for_memory_profile(2) == {"vram_policy": "high", "cache_policy": "lru:32"}
    assert session_overrides_for_memory_profile(3) == {"vram_policy": "normal", "cache_policy": "smart"}
    assert session_overrides_for_memory_profile(4) == {
        "vram_policy": "low",
        "cache_policy": "classic",
        "reserve_vram_gb": 2.0,
    }
    assert session_overrides_for_memory_profile(5) == {
        "vram_policy": "low",
        "cache_policy": "lru:1",
        "disable_smart_memory": True,
        "reserve_vram_gb": 4.0,
    }


def test_memory_profile_telemetry_uses_public_label() -> None:
    assert memory_profile_telemetry(4) == {
        "memory_profile": 4,
        "memory_profile_label": "Very Low VRAM",
    }


def test_apply_memory_profile_overrides_with_profile_precedence_is_non_mutating() -> None:
    config = SessionConfig(vram_policy="normal", cache_policy="none", reserve_vram_gb=8.0)

    resolved = apply_memory_profile_overrides(config, MemoryProfile.MINIMUM, precedence="profile")

    assert config == SessionConfig(vram_policy="normal", cache_policy="none", reserve_vram_gb=8.0)
    assert resolved == SessionConfig(
        vram_policy="low",
        cache_policy="lru:1",
        reserve_vram_gb=4.0,
        disable_smart_memory=True,
    )


def test_apply_memory_profile_overrides_with_config_precedence_preserves_explicit_fields() -> None:
    config = SessionConfig(vram_policy="normal", cache_policy="none", reserve_vram_gb=8.0)

    resolved = apply_memory_profile_overrides(config, MemoryProfile.MINIMUM, precedence="config")

    assert resolved == SessionConfig(
        vram_policy="normal",
        cache_policy="none",
        reserve_vram_gb=8.0,
        disable_smart_memory=True,
    )


def test_apply_memory_profile_overrides_with_config_precedence_fills_default_fields() -> None:
    config = SessionConfig(port=8200)

    resolved = apply_memory_profile_overrides(config, 4, precedence="config")

    assert resolved == SessionConfig(
        port=8200,
        vram_policy="low",
        cache_policy="classic",
        reserve_vram_gb=2.0,
    )
