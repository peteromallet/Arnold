#!/usr/bin/env python3
"""Rewrite canonical __init__.py files to import build_pipeline locally."""

from __future__ import annotations

from pathlib import Path


INIT_TEMPLATE = '''"""Canonical public surface for the ``{pkg}`` pipeline package."""

from __future__ import annotations

from .pipeline import build_pipeline

name: str = {name!r}
description: str = {description!r}
default_profile: str | None = {default_profile!r}
supported_modes: tuple[str, ...] = {supported_modes!r}
recommended_profiles: tuple[str, ...] = {recommended_profiles!r}
driver: tuple[str, str] = {driver!r}
entrypoint: str = {entrypoint!r}
arnold_api_version: str = {arnold_api_version!r}
capabilities: tuple[str, ...] = {capabilities!r}

__all__ = [
    "arnold_api_version",
    "build_pipeline",
    "capabilities",
    "default_profile",
    "description",
    "driver",
    "entrypoint",
    "name",
    "recommended_profiles",
    "supported_modes",
]
'''


SELECT_TOURNAMENT_TEMPLATE = '''"""Canonical public surface for the ``select-tournament`` pipeline package."""

from __future__ import annotations

from collections.abc import Sequence

from arnold.pipeline import Pipeline

from .pipeline import DEFAULT_CANDIDATES, build_pipeline as _build_pipeline


name: str = "select-tournament"
description: str = (
    "Selection tournament pipeline: fan out per-candidate scoring, reduce "
    "scores through a pairwise bracket, then emit a winner artifact."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native",)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "fanout+pairwise-reduce")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("review",)


def build_pipeline(
    candidates: Sequence[str] = DEFAULT_CANDIDATES,
) -> Pipeline:
    """Return the canonical native-projected ``select-tournament`` pipeline."""

    return _build_pipeline(candidates=candidates)


__all__ = [
    "DEFAULT_CANDIDATES",
    "build_pipeline",
    "name",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
]
'''


PACKAGES: dict[str, dict[str, object]] = {
    "creative": {
        "name": "creative",
        "description": (
            "Creative-form pipeline: form-aware prep -> execute -> critique -> "
            "revise -> finalize. Forms registry validates --form; "
            "--primary-criterion threads through as a first-class input."
        ),
        "default_profile": None,
        "supported_modes": ("native",),
        "recommended_profiles": (),
        "driver": ("native", "linear"),
        "entrypoint": "build_pipeline",
        "arnold_api_version": "1.0",
        "capabilities": ("creative",),
    },
    "doc": {
        "name": "doc",
        "description": (
            "Linear doc pipeline: outline -> per-section drafts (dynamic fanout) "
            "-> critique -> revise -> assembly. Single-pass; no gate."
        ),
        "default_profile": None,
        "supported_modes": ("native",),
        "recommended_profiles": (),
        "driver": ("native", "dynamic-fanout"),
        "entrypoint": "build_pipeline",
        "arnold_api_version": "1.0",
        "capabilities": ("doc",),
    },
    "jokes": {
        "name": "jokes",
        "description": (
            "Joke pipeline: drafts a joke, tightens the beat, and emits the final artifact "
            "through a direct native program."
        ),
        "default_profile": None,
        "supported_modes": ("native", "joke"),
        "recommended_profiles": (),
        "driver": ("native", "linear"),
        "entrypoint": "build_pipeline",
        "arnold_api_version": "1.0",
        "capabilities": ("creative", "joke"),
    },
    "live_supervisor": {
        "name": "live-supervisor",
        "description": (
            "Megaplan Live Watchdog Supervisor: classify, diagnose, and decide "
            "safe repair actions for likely-live Megaplan/Arnold runs."
        ),
        "default_profile": None,
        "supported_modes": ("supervise", "native"),
        "recommended_profiles": (),
        "driver": ("native", "linear"),
        "entrypoint": "build_pipeline",
        "arnold_api_version": "1.0",
        "capabilities": (
            "plan_supervision",
            "incident_classification",
            "repair_dispatch",
        ),
    },
    "writing_panel_strict": {
        "name": "writing-panel-strict",
        "description": (
            "Adversarial review of prose drafts by N reviewers, then revise. "
            "Not for code."
        ),
        "default_profile": "@writing-panel-strict:standard",
        "supported_modes": ("native",),
        "recommended_profiles": (
            "@writing-panel-strict:premium",
            "@writing-panel-strict:standard",
            "@writing-panel-strict:cheap",
        ),
        "driver": ("native", "panel"),
        "entrypoint": "build_pipeline",
        "arnold_api_version": "1.0",
        "capabilities": ("writing", "critique", "revise"),
    },
}


def write_init(pkg: str) -> None:
    path = Path(f"arnold_pipelines/megaplan/pipelines/{pkg}/__init__.py")
    if pkg == "select_tournament":
        path.write_text(SELECT_TOURNAMENT_TEMPLATE, encoding="utf-8")
        print(f"wrote {path}")
        return
    text = INIT_TEMPLATE.format(pkg=pkg, **PACKAGES[pkg])
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path}")


if __name__ == "__main__":
    for pkg in ["creative", "doc", "jokes", "live_supervisor", "select_tournament", "writing_panel_strict"]:
        write_init(pkg)
