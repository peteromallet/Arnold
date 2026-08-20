"""Explicit routing choices for the watchdog babysitter.

The legacy Hermes/DeepSeek path remains the default.  A temporary, explicit
environment toggle is the only way to select the Codex recovery path; an
unknown value fails closed instead of silently choosing a provider.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

ROUTING_ENV = "ARNOLD_BABYSITTER_ROUTING"
CODEX_MODEL_ENV = "ARNOLD_BABYSITTER_CODEX_MODEL"
CODEX_INVESTIGATOR_MODEL_ENV = "ARNOLD_BABYSITTER_CODEX_INVESTIGATOR_MODEL"

LEGACY_ROUTING = "legacy"
CODEX_ROUTING = "codex"
LEGACY_CONTROLLER_MODEL = "hermes:deepseek:deepseek-v4-flash"
CODEX_CONTROLLER_MODEL = "codex:gpt-5.6-luna"


@dataclass(frozen=True)
class BabysitterRouting:
    """Resolved controller and evidence-investigator route."""

    mode: str
    controller_backend: str
    controller_model: str
    investigator_backend: str
    investigator_model: str

    def as_dict(self) -> dict[str, str]:
        return {
            "mode": self.mode,
            "controller_backend": self.controller_backend,
            "controller_model": self.controller_model,
            "investigator_backend": self.investigator_backend,
            "investigator_model": self.investigator_model,
        }


def _codex_model(value: str, *, variable: str) -> str:
    model = value.strip() or CODEX_CONTROLLER_MODEL
    if model.startswith("codex:"):
        model = model[len("codex:"):]
    if not model.startswith("gpt-5.6-"):
        raise ValueError(
            f"{variable} must select an explicit Codex GPT-5.6 model, got {value!r}"
        )
    return f"codex:{model}"

def resolve_babysitter_routing(env: Mapping[str, str] | None = None) -> BabysitterRouting:
    """Resolve the babysitter route from an explicit, fail-closed toggle."""

    values = os.environ if env is None else env
    selected = str(values.get(ROUTING_ENV, "")).strip().lower() or LEGACY_ROUTING
    if selected in {LEGACY_ROUTING, "default"}:
        return BabysitterRouting(
            mode=LEGACY_ROUTING,
            controller_backend="hermes",
            controller_model=LEGACY_CONTROLLER_MODEL,
            investigator_backend="hermes",
            investigator_model=LEGACY_CONTROLLER_MODEL,
        )
    if selected != CODEX_ROUTING:
        raise ValueError(
            f"{ROUTING_ENV} must be unset, 'legacy', or 'codex'; got {selected!r}"
        )
    controller = _codex_model(
        str(values.get(CODEX_MODEL_ENV, CODEX_CONTROLLER_MODEL)),
        variable=CODEX_MODEL_ENV,
    )
    investigator = _codex_model(
        str(values.get(CODEX_INVESTIGATOR_MODEL_ENV, controller)),
        variable=CODEX_INVESTIGATOR_MODEL_ENV,
    )
    return BabysitterRouting(
        mode=CODEX_ROUTING,
        controller_backend="codex",
        controller_model=controller,
        investigator_backend="codex",
        investigator_model=investigator,
    )


def cli_model(model: str) -> str:
    """Return the provider-free model name required by the Codex CLI."""

    return model[len("codex:"):] if model.startswith("codex:") else model
