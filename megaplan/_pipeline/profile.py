"""Profile binding — a Step's ``slot`` resolves a model at dispatch time.

The :class:`Profile` value here is the smallest interface that
satisfies the :attr:`Step.slot` contract from
``megaplan/_pipeline/types.py``. Existing profile TOMLs at
``megaplan/profiles/*.toml`` are wrappable into a :class:`Profile`
without any TOML changes — the slot keys stay phase-named (``plan``,
``critique``, ``revise``, ``gate``, ``finalize``, ``execute``,
``feedback``, ``review``, ``tiebreaker_researcher``,
``tiebreaker_challenger``, ``loop_plan``, ``loop_execute``).

The executor never resolves a slot itself — that's the Step's job.
:meth:`Profile.model_for` is the canonical lookup; Steps call it
inside ``run`` whenever they need to dispatch a worker. This keeps
the executor agnostic of model selection, which is the brief's
"primitives that can power many modes" requirement.

Profile swapping mid-flight is a first-class primitive: pass a new
:class:`Profile` instance in ``StepContext.profile`` for any
subsequent stage, and that stage resolves its slot against the new
profile. The executor refreshes ctx.state on each tick (Sprint-2
fix), so profile-bearing patches in ``state_patch`` propagate the
same way.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Profile:
    """Lookup table mapping a slot name (e.g. ``"plan"``) to a model spec.

    A model spec is whatever string the production worker dispatch
    expects — e.g. ``"claude"``, ``"claude:high"``, ``"hermes:openai/gpt-5"``,
    ``"hermes:deepseek:deepseek-v4-pro"``. The :class:`Profile` doesn't
    validate the spec — that's the worker's job.
    """

    name: str
    slots: Mapping[str, str] = field(default_factory=dict)

    def model_for(self, slot: str, *, default: str | None = None) -> str:
        spec = self.slots.get(slot)
        if spec is not None:
            return spec
        if default is not None:
            return default
        raise KeyError(
            f"Profile {self.name!r} has no slot {slot!r}; "
            f"available slots: {sorted(self.slots)}"
        )

    def with_slot(self, slot: str, model: str) -> "Profile":
        """Return a new Profile with one slot rebound — on-the-fly swap."""
        new_slots = dict(self.slots)
        new_slots[slot] = model
        return Profile(name=self.name, slots=new_slots)

    def with_overrides(self, **slot_overrides: str) -> "Profile":
        """Return a new Profile with multiple slots rebound."""
        new_slots = {**self.slots, **slot_overrides}
        return Profile(name=self.name, slots=new_slots)


_PROFILE_DIR = Path(__file__).resolve().parent.parent / "profiles"


def load_profile(name: str) -> Profile:
    """Load a named profile from ``megaplan/profiles/<name>.toml``.

    The TOML schema is ``[profiles.<name>] key = "spec"``. If the file
    holds multiple profile tables (some shipped TOMLs do), the first
    matching ``[profiles.<name>]`` wins.
    """

    for candidate in _PROFILE_DIR.glob("*.toml"):
        data = tomllib.loads(candidate.read_text())
        profiles = data.get("profiles", {})
        if name in profiles and isinstance(profiles[name], dict):
            return Profile(name=name, slots={k: v for k, v in profiles[name].items() if isinstance(v, str)})
    raise FileNotFoundError(f"no profile named {name!r} in {_PROFILE_DIR}")


def list_profile_names() -> tuple[str, ...]:
    names: list[str] = []
    for candidate in _PROFILE_DIR.glob("*.toml"):
        data = tomllib.loads(candidate.read_text())
        for key, value in (data.get("profiles", {}) or {}).items():
            if isinstance(value, dict):
                names.append(key)
    return tuple(sorted(set(names)))


def empty_profile(name: str = "empty") -> Profile:
    """Return a Profile with no slots — for hermetic tests."""
    return Profile(name=name)


def _from_env(name: str) -> Profile:
    """Build a Profile from env vars of the form ``MEGAPLAN_SLOT_<name>``.

    Used by tests / runtime configs that want to ad-hoc override slots
    without touching a TOML. Example::

        MEGAPLAN_SLOT_critique=hermes:openai/gpt-5 \\
        python -m megaplan ...
    """

    prefix = "MEGAPLAN_SLOT_"
    slots = {
        key[len(prefix):].lower(): value
        for key, value in os.environ.items()
        if key.startswith(prefix)
    }
    return Profile(name=name, slots=slots)
