"""Settings resolver for the Arnold runtime precedence chain.

Walks five input layers in ascending priority order and produces one
:class:`EffectiveSetting` per key, recording which layer won.  Errors are
**returned** in :attr:`ResolvedSettings.errors` — never raised — so callers
decide whether any failure is fatal.

Five validation rules
---------------------

1. **unknown_stage_key** — a ``stage_id`` in ``stage_local`` is not a member
   of the declared ``pipeline_stages``.
2. **idle_exceeds_wall_timeout** — ``idle_timeout_s > wall_timeout_s`` in the
   resolved effective settings.
3. **negative_timeout** — any timeout key (``wall_timeout_s``,
   ``idle_timeout_s``, ``heartbeat_interval_s``, ``poll_cadence_s``) resolves
   to a negative number.
4. **isolation_mode_invalid** — the resolved ``isolation_mode`` is not a
   member of :data:`~arnold.runtime.driver.ISOLATION_MODES`.
5. **max_workers_nonpositive** — the resolved ``max_workers`` is <= 0.

Boundary discipline
-------------------
No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from arnold.runtime.driver import ISOLATION_MODES
from arnold.runtime.settings import EffectiveSetting, SettingSource

__all__ = ["ValidationError", "ResolvedSettings", "resolve_settings"]


# ---------------------------------------------------------------------------
# Output carriers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationError:
    """A single settings-validation failure.

    ``code`` is a machine-readable error class (stable across versions).
    ``message`` is a human-readable description.
    """

    code: str
    message: str


@dataclass
class ResolvedSettings:
    """Output of :func:`resolve_settings`.

    ``effective`` maps each resolved key to its :class:`EffectiveSetting`
    (including the winning :class:`~arnold.runtime.settings.SettingSource`).
    ``stage_effective`` carries per-stage resolved settings (run-level base +
    stage-local overrides) keyed by ``stage_id``.
    ``child_scope_effective`` carries per-child-scope resolved settings
    (run-level base + child-scope overrides) keyed by scope name.
    ``errors`` collects all validation failures; callers decide whether any
    error is fatal.
    """

    effective: dict[str, EffectiveSetting] = field(default_factory=dict)
    stage_effective: dict[str, dict[str, EffectiveSetting]] = field(default_factory=dict)
    child_scope_effective: dict[str, dict[str, EffectiveSetting]] = field(default_factory=dict)
    errors: tuple[ValidationError, ...] = ()


# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

_PRECEDENCE: tuple[SettingSource, ...] = (
    SettingSource.ARNOLD_DEFAULT,
    SettingSource.PLUGIN_DEFAULT,
    SettingSource.PROFILE,
    SettingSource.RUN_OVERRIDE,
    SettingSource.ENV_OVERRIDE,
)

_TIMEOUT_KEYS: frozenset[str] = frozenset(
    {"wall_timeout_s", "idle_timeout_s", "heartbeat_interval_s", "poll_cadence_s"}
)


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


def resolve_settings(
    arnold_defaults: Mapping[str, Any] | None = None,
    plugin_defaults: Mapping[str, Any] | None = None,
    profile: Mapping[str, Any] | None = None,
    run_overrides: Mapping[str, Any] | None = None,
    env_overrides: Mapping[str, Any] | None = None,
    pipeline_stages: frozenset[str] | None = None,
    stage_local: Sequence[Mapping[str, Any]] | None = None,
    child_scope_overrides: Mapping[str, Mapping[str, Any]] | None = None,
) -> ResolvedSettings:
    """Resolve settings by walking the five-layer precedence chain.

    Precedence (ascending priority — last layer wins per key):

        arnold_default < plugin_default < profile < run_override < env_override

    Parameters
    ----------
    arnold_defaults:
        Built-in Arnold defaults (lowest priority).
    plugin_defaults:
        Defaults declared by the plugin manifest.
    profile:
        Values from a named profile.
    run_overrides:
        Run-level or CLI overrides supplied by the caller.
    env_overrides:
        Environment-variable overrides (highest priority).
    pipeline_stages:
        Known stage identifiers for the current pipeline.  When provided,
        any ``stage_id`` in ``stage_local`` that is absent from this set
        produces an ``unknown_stage_key`` validation error.
    stage_local:
        A sequence of per-stage override records, each a mapping with at
        least a ``\"stage_id\"`` key and an ``\"overrides\"`` mapping.
        Run-level inheritables flow into each stage as base values; the
        stage's overrides win for that stage.
    child_scope_overrides:
        Per-child-scope override maps keyed by child scope name (e.g.
        ``\"panels\"``, ``\"fanouts\"``).  Run-level inheritables flow into
        each child scope as base values; the child-scope overrides win for
        that scope.
    """
    layers: list[tuple[SettingSource, Mapping[str, Any]]] = [
        (SettingSource.ARNOLD_DEFAULT, arnold_defaults or {}),
        (SettingSource.PLUGIN_DEFAULT, plugin_defaults or {}),
        (SettingSource.PROFILE, profile or {}),
        (SettingSource.RUN_OVERRIDE, run_overrides or {}),
        (SettingSource.ENV_OVERRIDE, env_overrides or {}),
    ]

    # Precedence walk: later layers overwrite earlier ones for the same key.
    effective: dict[str, EffectiveSetting] = {}
    for source, layer in layers:
        for key, value in layer.items():
            effective[key] = EffectiveSetting(key=key, value=value, source=source)

    vals: dict[str, Any] = {k: v.value for k, v in effective.items()}
    errors: list[ValidationError] = []

    # Rule 1: unknown stage keys.
    if pipeline_stages is not None and stage_local:
        for entry in stage_local:
            sid = entry.get("stage_id")
            if isinstance(sid, str) and sid not in pipeline_stages:
                errors.append(
                    ValidationError(
                        code="unknown_stage_key",
                        message=(
                            f"stage_id {sid!r} is not in "
                            f"pipeline_stages {sorted(pipeline_stages)}"
                        ),
                    )
                )

    # Rule 2: idle_timeout_s > wall_timeout_s.
    wall = vals.get("wall_timeout_s")
    idle = vals.get("idle_timeout_s")
    if (
        wall is not None
        and idle is not None
        and idle > wall
    ):
        errors.append(
            ValidationError(
                code="idle_exceeds_wall_timeout",
                message=(
                    f"idle_timeout_s ({idle}) must not exceed "
                    f"wall_timeout_s ({wall})"
                ),
            )
        )

    # Rule 3: negative timeout values.
    for key in sorted(_TIMEOUT_KEYS):
        v = vals.get(key)
        if v is not None and v < 0:
            errors.append(
                ValidationError(
                    code="negative_timeout",
                    message=f"{key} must not be negative, got {v!r}",
                )
            )

    # Rule 4: isolation_mode not in ISOLATION_MODES.
    mode = vals.get("isolation_mode")
    if mode is not None and mode not in ISOLATION_MODES:
        errors.append(
            ValidationError(
                code="isolation_mode_invalid",
                message=(
                    f"isolation_mode {mode!r} is not in "
                    f"{sorted(ISOLATION_MODES)}"
                ),
            )
        )

    # Rule 5: max_workers <= 0.
    mw = vals.get("max_workers")
    if mw is not None and mw <= 0:
        errors.append(
            ValidationError(
                code="max_workers_nonpositive",
                message=f"max_workers must be >= 1, got {mw!r}",
            )
        )

    # -------------------------------------------------------------------
    # Stage inheritance (T8): run-level effective are the base;
    # stage-local overrides win for the named stage.
    # -------------------------------------------------------------------
    stage_effective: dict[str, dict[str, EffectiveSetting]] = {}
    if stage_local:
        for entry in stage_local:
            sid = entry.get("stage_id")
            if not isinstance(sid, str):
                continue
            # Start from run-level base
            merged: dict[str, EffectiveSetting] = dict(effective)
            overrides = entry.get("overrides")
            if isinstance(overrides, Mapping):
                for key, value in overrides.items():
                    merged[key] = EffectiveSetting(
                        key=key, value=value, source=SettingSource.RUN_OVERRIDE,
                    )
            stage_effective[sid] = merged

    # -------------------------------------------------------------------
    # Child-scope overrides (T8): run-level effective are the base;
    # child-scope overrides win for the named child scope.
    # -------------------------------------------------------------------
    child_scope_effective: dict[str, dict[str, EffectiveSetting]] = {}
    if child_scope_overrides:
        for scope_name, overrides in child_scope_overrides.items():
            merged: dict[str, EffectiveSetting] = dict(effective)
            for key, value in overrides.items():
                merged[key] = EffectiveSetting(
                    key=key, value=value, source=SettingSource.RUN_OVERRIDE,
                )
            child_scope_effective[scope_name] = merged

    return ResolvedSettings(
        effective=effective,
        stage_effective=stage_effective,
        child_scope_effective=child_scope_effective,
        errors=tuple(errors),
    )
