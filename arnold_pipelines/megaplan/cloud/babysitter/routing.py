"""Explicit routing choices for the watchdog babysitter.

The omp/DeepSeek path is the default.  A temporary, explicit
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
OMP_MODEL_ENV = "ARNOLD_BABYSITTER_OMP_MODEL"

OMP_ROUTING = "omp"
CODEX_ROUTING = "codex"
OMP_CONTROLLER_MODEL = "omp:deepseek/deepseek-v4-flash"
CODEX_CONTROLLER_MODEL = "codex:gpt-5.6-luna"
CONTINUATION_SESSION_PREFIX = "native-build-forward-c2-c4b0c102-20260902-r2"
CONTINUATION_MUSE_MODEL = "omp:openrouter/meta/muse-spark-1.3-contributor"
CONTINUATION_MUSE_THINKING = "high"
_CONTINUATION_MUSE_INPUT_THINKING = frozenset(
    {"auto", "off", "minimal", "low", "medium", "high", "xhigh", "max"}
)
CONTINUATION_FIXER_ROLES = (
    "controller",
    "researcher",
    "swarm",
    "investigator",
    "implementer",
    "reviewer",
    "xhard",
    "oracle",
    "recommendation",
    "recommender",
)


@dataclass(frozen=True)
class BabysitterRouting:
    """Resolved controller and evidence-investigator route."""

    mode: str
    controller_backend: str
    controller_model: str
    investigator_backend: str
    investigator_model: str
    thinking: str | None = None

    def as_dict(self) -> dict[str, object]:
        payload = {
            "mode": self.mode,
            "controller_backend": self.controller_backend,
            "controller_model": self.controller_model,
            "investigator_backend": self.investigator_backend,
            "investigator_model": self.investigator_model,
        }
        if self.thinking is not None:
            payload["thinking"] = self.thinking
            payload["role_models"] = {
                role: self.controller_model for role in CONTINUATION_FIXER_ROLES
            }
        return payload

    @property
    def closed(self) -> bool:
        return self.mode == "continuation-muse"


def _codex_model(value: str, *, variable: str) -> str:
    model = value.strip() or CODEX_CONTROLLER_MODEL
    if model.startswith("codex:"):
        model = model[len("codex:"):]
    if not model.startswith("gpt-5.6-"):
        raise ValueError(
            f"{variable} must select an explicit Codex GPT-5.6 model, got {value!r}"
        )
    return f"codex:{model}"

def resolve_babysitter_routing(
    env: Mapping[str, str] | None = None,
    *,
    session: str | None = None,
) -> BabysitterRouting:
    """Resolve the babysitter route from an explicit, fail-closed toggle."""

    values = os.environ if env is None else env
    session_value = str(session or values.get("ARNOLD_BABYSITTER_SESSION", "")).strip()
    if session_value.startswith(CONTINUATION_SESSION_PREFIX):
        selected = str(values.get(ROUTING_ENV, "")).strip().lower()
        if selected and selected not in {OMP_ROUTING, "default", "legacy"}:
            raise ValueError(
                f"{session_value} is closed to Muse routing; {ROUTING_ENV}="
                f"{selected!r} is not permitted"
            )
        for variable in (
            OMP_MODEL_ENV,
            "ARNOLD_BABYSITTER_MODEL",
            CODEX_MODEL_ENV,
            CODEX_INVESTIGATOR_MODEL_ENV,
        ):
            requested = str(values.get(variable, "")).strip()
            if requested and requested != CONTINUATION_MUSE_MODEL:
                prefix, separator, suffix = requested.rpartition(":")
                if (
                    prefix != CONTINUATION_MUSE_MODEL
                    or not separator
                    or suffix not in _CONTINUATION_MUSE_INPUT_THINKING
                ):
                    raise ValueError(
                        f"{session_value} is closed to Muse routing; {variable}="
                        f"{requested!r} is not permitted"
                    )
        return BabysitterRouting(
            mode="continuation-muse",
            controller_backend=OMP_ROUTING,
            controller_model=CONTINUATION_MUSE_MODEL,
            investigator_backend=OMP_ROUTING,
            investigator_model=CONTINUATION_MUSE_MODEL,
            thinking=CONTINUATION_MUSE_THINKING,
        )
    selected = str(values.get(ROUTING_ENV, "")).strip().lower() or OMP_ROUTING
    if selected in {OMP_ROUTING, "default", "legacy"}:
        # ``legacy`` remains accepted as a back-compat alias for the omp route.
        return BabysitterRouting(
            mode=OMP_ROUTING,
            controller_backend="omp",
            controller_model=str(values.get(OMP_MODEL_ENV, "")).strip() or OMP_CONTROLLER_MODEL,
            investigator_backend="omp",
            investigator_model=str(values.get(OMP_MODEL_ENV, "")).strip() or OMP_CONTROLLER_MODEL,
        )
    if selected != CODEX_ROUTING:
        raise ValueError(
            f"{ROUTING_ENV} must be unset, 'omp', or 'codex'; got {selected!r}"
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
