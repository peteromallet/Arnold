"""Runtime settings carriers, source labels, and scoping categories.

IN-SCOPE vs DEFERRED cross-cutting areas for M2a
-------------------------------------------------

=========================  ===========  =====================================================
Cross-cutting area         Status       Notes / Target Milestone
=========================  ===========  =====================================================
control/resume             IN SCOPE     ``InheritableSettings.retry_budget`` and
                                        ``IsolationSettings.isolation_mode``.
recovery/failure           IN SCOPE     ``InheritableSettings.retry_budget`` and
                                        ``InheritableSettings.cost_cap_usd``.
resource/security          IN SCOPE     Timeouts, deadline, cost-cap; all in
                                        ``InheritableSettings``.
                                        Canonical deadline: ``deadline_epoch_s``
                                        (float|None); ``CrossCuttingEnvelope.deadline``
                                        string is metadata only (SD1).
                                        Canonical cancellation: ``cancellation``
                                        bool; ``CrossCuttingEnvelope.cancellation``
                                        string is opaque metadata (SD2).
isolation/environment      IN SCOPE     ``IsolationSettings.isolation_mode``; subprocess-
                                        launch knobs are reserved for later population.
identity/discovery         DEFERRED     Beyond ``plugin_id``/``manifest_hash``;
                                        target M3a.
model/profile routing      DEFERRED     Semantics belong to Megaplan; target M5a.
prompt/context             DEFERRED     Megaplan concern; target M5a.
artifact/dataflow shapes   DEFERRED     Beyond ``artifact_root``; target M3c.
observability/audit        DEFERRED     Target M7.
composition/subpipeline    DEFERRED     Fan-out policy and nesting rules; target M3c.
=========================  ===========  =====================================================

Category ownership
------------------

Each settings key belongs to **exactly one** category.  The four categories are:

* :class:`InheritableSettings` — per-run values that propagate into stages.
* :class:`GloballyAggregatedSettings` — run-wide aggregates that cross-cut all stages.
* :class:`StageLocalSettings` — opaque per-stage overrides keyed by stage id.
* :class:`IsolationSettings` — isolation-mode selection and reserved subprocess-launch knobs.

The settings resolver (M2a Step 7, ``arnold/runtime/settings_resolver.py``) walks
the precedence chain: Arnold default < plugin default < profile < run/CLI override <
env override.  Each resolved value is wrapped in an :class:`EffectiveSetting` that
records which layer supplied it.

Boundary discipline
-------------------

No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

__all__ = [
    "InheritableSettings",
    "GloballyAggregatedSettings",
    "StageLocalSettings",
    "IsolationSettings",
    "SettingSource",
    "EffectiveSetting",
]


# ---------------------------------------------------------------------------
# Source label
# ---------------------------------------------------------------------------


class SettingSource(str, Enum):
    """The five prescribed layers in the settings-precedence chain.

    Listed in ascending override priority (last wins):

    ``arnold_default``  — built-in Arnold default.
    ``plugin_default``  — default declared by the plugin manifest.
    ``profile``         — value from a named profile.
    ``run_override``    — run-level or CLI override supplied by the caller.
    ``env_override``    — env-var override; highest priority, intentionally
                          supported (not accidental).
    """

    ARNOLD_DEFAULT = "arnold_default"
    PLUGIN_DEFAULT = "plugin_default"
    PROFILE = "profile"
    RUN_OVERRIDE = "run_override"
    ENV_OVERRIDE = "env_override"


# ---------------------------------------------------------------------------
# Category 1: Inheritable settings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InheritableSettings:
    """Per-run settings that propagate into stages unless overridden.

    Applies at run level; each stage inherits these values as a base.
    :class:`StageLocalSettings` overrides win for a named stage.

    Fields in this category (exclusive):
    ``wall_timeout_s``, ``idle_timeout_s``, ``heartbeat_interval_s``,
    ``poll_cadence_s``, ``deadline_epoch_s``, ``retry_budget``,
    ``cost_cap_usd``.
    """

    wall_timeout_s: float | None = None
    idle_timeout_s: float | None = None
    heartbeat_interval_s: float | None = None
    poll_cadence_s: float | None = None
    deadline_epoch_s: float | None = None
    retry_budget: Mapping[str, Any] = field(default_factory=dict)
    cost_cap_usd: float | None = None


# ---------------------------------------------------------------------------
# Category 2: Globally aggregated settings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GloballyAggregatedSettings:
    """Run-wide settings that aggregate across the entire run.

    These cross-cut all stages and are not overridable per-stage.

    Fields in this category (exclusive): ``max_workers``, ``cancellation``.
    """

    max_workers: int | None = None
    cancellation: bool = False


# ---------------------------------------------------------------------------
# Category 3: Stage-local settings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageLocalSettings:
    """Opaque per-stage override knob set.

    ``stage_id`` names the target stage within ``Pipeline.stages``.
    ``overrides`` is an opaque ``Mapping`` applied on top of the run-level
    :class:`InheritableSettings` for that stage only.  Unknown stage ids
    are a validation error (caught by the settings resolver, not here).

    Fields in this category (exclusive): ``stage_id``, ``overrides``.
    """

    stage_id: str
    overrides: Mapping[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Category 4: Isolation settings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IsolationSettings:
    """Isolation-mode carrier and reserved subprocess-launch knobs.

    ``isolation_mode`` selects in-process or subprocess execution.  The
    permitted values are the two members of
    :data:`~arnold.runtime.driver.ISOLATION_MODES`
    (``"in_process"`` and ``"subprocess_isolated"``); the settings resolver
    validates membership and rejects anything else.

    Subprocess-launch knobs (process image, env injection, resource limits)
    are intentionally absent — they are reserved for a later milestone.

    Fields in this category (exclusive): ``isolation_mode``.
    """

    isolation_mode: str = "in_process"


# ---------------------------------------------------------------------------
# Effective-setting carrier
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EffectiveSetting:
    """A resolved setting value annotated with its source layer.

    ``key`` names the setting (matches the field name on the owning
    category dataclass).  ``value`` is the resolved value (opaque to
    Arnold except for structural validation).  ``source`` records which
    layer of the precedence chain supplied the value so that dry-run
    output can explain every effective setting.
    """

    key: str
    value: Any
    source: SettingSource
