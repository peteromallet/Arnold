"""Sprint 2 acceptance test #7 — every profile TOML's slots survive the port.

The brief commits to "profile TOMLs unchanged; primitive instances bind
to slots by name." This test loads every shipped profile and asserts
that each profile's slot keys are addressable from the Pipeline view —
specifically, that the slot names match the phase names referenced by
the compiled planning Pipeline stages (initialized → prep → plan →
critique → gate → finalize → execute → review).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megaplan._pipeline.planning import compile_pipeline_for


_PROFILE_DIR = Path(__file__).resolve().parent.parent / "megaplan" / "profiles"

# Slot keys that every profile is expected to expose. Sourced from
# `megaplan/profiles/all-claude.toml` — the canonical full-surface
# profile.
_REQUIRED_SLOT_KEYS = {
    "plan",
    "prep",
    "critique",
    "revise",
    "gate",
    "finalize",
    "execute",
    "feedback",
    "review",
}


def _list_profiles():
    return sorted(p for p in _PROFILE_DIR.glob("*.toml") if p.is_file())


@pytest.mark.parametrize("profile_path", _list_profiles(), ids=lambda p: p.name)
def test_profile_slots_cover_required_phases(profile_path: Path) -> None:
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:  # pragma: no cover - Py3.10 fallback
        import tomli as tomllib  # type: ignore[import-not-found]

    data = tomllib.loads(profile_path.read_text())
    profiles = data.get("profiles", {})
    assert profiles, f"profile file {profile_path.name} has no [profiles.*] table"

    for profile_name, slots in profiles.items():
        slot_keys = set(slots.keys())
        # Every profile must cover at least these phase slots so that
        # primitives binding by name can resolve a model for each.
        missing = _REQUIRED_SLOT_KEYS - slot_keys
        assert not missing, (
            f"profile {profile_name} in {profile_path.name} missing slots: "
            f"{sorted(missing)}"
        )


def test_planning_pipeline_phase_names_are_slot_addressable() -> None:
    """The compiled Pipeline's terminal-style stages must align with
    profile slot keys. This is the abstraction guarantee: primitive
    instances bind to slots by name, not by inventing a new taxonomy.
    """

    pipeline = compile_pipeline_for(robustness="standard")
    # Stages named after live phases — these are the ones a profile slot
    # would resolve a model for. Post-Sprint-5 the canonical Pipeline
    # uses phase-name stages.
    phase_like_stages = {"prep", "plan", "critique", "gate", "finalize", "execute"}
    assert phase_like_stages.issubset(pipeline.stages.keys()), (
        phase_like_stages - pipeline.stages.keys()
    )
