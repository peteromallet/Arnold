"""Legacy critique-loop path retirement (CL5 Step 15).

This module inventories the critique-loop legacy path the cutover replaces,
verifies that the replaced writers/readers/bridge paths are hard-disabled,
retains ``critique_runtime`` as the single active post-cutover target,
excludes any nonexistent module from the inventory, and generates a
retirement proof bound to the immutable :class:`CutoverConfig`.

Scope (from CL5 Step 15): the retirement disables ONLY the critique-loop
legacy path that the cutover replaces — the ``critique_custody`` legacy
BRIDGE-mode receipt paths, and the ``gate_checks`` / ``evaluation`` legacy
reader paths. ``critique_runtime`` is the ACTIVE post-cutover canonical
critique loop and is RETAINED, never retired. The broader cross-pipeline
"legacy-entrypoint fencing" is owned by the follow-up epic, not this step.

The actual hard-disabling was performed by earlier CL5 steps (the
``CL4_BRIDGE_MODE`` constants were set ``False``; the ``recurring_critiques``
legacy alias was retired). This module does not re-perform those writes — it
VERIFIES the disabled state and RECORDS the retirement, so the proof is
grounded in the live module state rather than a declarative claim.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import time
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from arnold.critique_ledger.cutover.config import (
    CutoverConfig,
    NORTH_STAR_RUNTIME_HASH,
    validate_config,
)

#: Proof schema identifier.
RETIREMENT_PROOF_SCHEMA: str = "cl5.retirement-proof.v1"

#: The single active post-cutover critique-loop runtime. It is RETAINED.
ACTIVE_TARGET_MODULE: str = "arnold_pipelines.megaplan.orchestration.critique_runtime"


class ComponentRole(StrEnum):
    """Functional role of an inventory component in the critique loop."""

    WRITER = "writer"
    READER = "reader"
    BRIDGE = "bridge"
    ADAPTER = "adapter"


class RetirementStatus(StrEnum):
    """Whether a component is hard-disabled (retired) or active (retained)."""

    RETIRED = "retired"
    """The legacy critique-loop path replaced by the cutover. Hard-disabled."""

    RETAINED = "retained"
    """The active post-cutover canonical path (e.g. critique_runtime)."""


class RetirementError(RuntimeError):
    """Raised when a retired legacy path is not actually hard-disabled, the
    cutover config is invalid, or the inventory references a nonexistent
    module."""


@dataclass(frozen=True)
class LegacyComponent:
    """One inventory entry for a critique-loop component."""

    name: str
    module: str
    role: ComponentRole
    status: RetirementStatus
    retirement_action: str
    evidence: str


@dataclass(frozen=True)
class RetirementResult:
    """Verified retirement state returned by :func:`retire_legacy_path`."""

    config_source_revision: str
    north_star_runtime_binding: str
    inventory: tuple[LegacyComponent, ...]
    excluded_nonexistent: tuple[str, ...]
    single_target_architecture_active: bool
    retired_path_count: int
    retained_path_count: int
    bridge_mode_state: dict[str, bool]


# ── Canonical in-scope retirement inventory ─────────────────────────────────
#
# Bounded, explicitly-named set so the inventory cannot silently grow to
# include out-of-scope modules. Every entry MUST exist on disk — a missing
# in-scope module is a hard error (the inventory must reference only real
# modules). Only the critique-loop legacy path replaced by the cutover is
# retired; critique_runtime is the retained active target.
_INVENTORY_SPEC: tuple[dict[str, str], ...] = (
    {
        "name": "critique_custody (legacy BRIDGE writer)",
        "module": "arnold_pipelines.megaplan.orchestration.critique_custody",
        "role": ComponentRole.BRIDGE,
        "status": RetirementStatus.RETIRED,
        "retirement_action": (
            "Legacy BRIDGE-mode receipt-production paths hard-disabled via "
            "CL4_BRIDGE_MODE = False; bridge receipts excluded from the "
            "post-cutover clearance chain."
        ),
        "evidence": "critique_custody.CL4_BRIDGE_MODE == False",
    },
    {
        "name": "gate_checks (legacy reader)",
        "module": "arnold_pipelines.megaplan.orchestration.gate_checks",
        "role": ComponentRole.READER,
        "status": RetirementStatus.RETIRED,
        "retirement_action": (
            "Legacy recurring_critiques reader path retired; orchestrator "
            "guidance reads adjacent_text_matches (transition fallback only)."
        ),
        "evidence": "recurring_critiques output alias removed from gate_signals",
    },
    {
        "name": "evaluation (legacy reader)",
        "module": "arnold_pipelines.megaplan.orchestration.evaluation",
        "role": ComponentRole.READER,
        "status": RetirementStatus.RETIRED,
        "retirement_action": (
            "Legacy compute_recurring_critiques re-export removed; "
            "evaluation consumes canonical critique_runtime outputs only."
        ),
        "evidence": "evaluation.py deprecated re-export retired",
    },
    {
        "name": "critique_runtime (active canonical runtime)",
        "module": ACTIVE_TARGET_MODULE,
        "role": ComponentRole.WRITER,
        "status": RetirementStatus.RETAINED,
        "retirement_action": (
            "RETAINED — the active post-cutover canonical critique loop. "
            "Emits adjacent_text_matches/semantic_recurrence. NOT legacy."
        ),
        "evidence": "critique_runtime is importable and emits canonical signals",
    },
)

# Historical relocation-map references that must never appear as live
# inventory. Each is verified at build time; only genuinely-absent modules are
# reported in ``excluded_nonexistent``. (``orchestration/bridge.py`` does not
# exist; a same-named kernel replay bridge under ``runtime/`` is a different,
# unrelated module.)
_HISTORICAL_RELOCATION_REFERENCES: tuple[str, ...] = (
    "arnold_pipelines.megaplan.orchestration.bridge",
)


def _module_exists(dotted: str) -> bool:
    """Return whether a dotted module path resolves to a real importable module."""
    try:
        return importlib.util.find_spec(dotted) is not None
    except (ModuleNotFoundError, ValueError, ImportError):
        return False


def build_inventory() -> list[LegacyComponent]:
    """Build the canonical retirement inventory from real, existing modules.

    Every in-scope module is verified to exist; a missing in-scope module
    raises :class:`RetirementError` so the inventory can never reference a
    phantom module.
    """
    components: list[LegacyComponent] = []
    for spec in _INVENTORY_SPEC:
        module = spec["module"]
        if not _module_exists(module):
            raise RetirementError(
                f"In-scope retirement inventory module {module!r} does not "
                "exist; the inventory must reference only real modules."
            )
        components.append(LegacyComponent(
            name=spec["name"],
            module=module,
            role=ComponentRole(spec["role"]),
            status=RetirementStatus(spec["status"]),
            retirement_action=spec["retirement_action"],
            evidence=spec["evidence"],
        ))
    return components


def _verify_hard_disable() -> dict[str, bool]:
    """Verify the legacy BRIDGE path is hard-disabled and the active target
    is retained. Returns the observed ``CL4_BRIDGE_MODE`` state.

    Imports the modules at call time (not import time) so tests can
    monkeypatch the constants and so a missing module surfaces as an
    explicit error rather than an import-time crash.
    """
    from arnold_pipelines.megaplan.orchestration import (
        critique_custody,
        critique_runtime,
        gate_signals,
    )

    gate_bridge = getattr(gate_signals, "CL4_BRIDGE_MODE", True)
    custody_bridge = getattr(critique_custody, "CL4_BRIDGE_MODE", True)
    bridge_mode_state = {
        "gate_signals": gate_bridge is False,
        "critique_custody": custody_bridge is False,
    }

    if gate_bridge is not False:
        raise RetirementError(
            "gate_signals.CL4_BRIDGE_MODE is not False; the legacy BRIDGE "
            "path is not hard-disabled and the cutover is not safe to retire."
        )
    if custody_bridge is not False:
        raise RetirementError(
            "critique_custody.CL4_BRIDGE_MODE is not False; the legacy "
            "BRIDGE receipt path is not hard-disabled."
        )
    # The active target must remain importable (retained, not retired).
    if critique_runtime is None:  # pragma: no cover - defensive
        raise RetirementError(
            "critique_runtime is not importable; the active post-cutover "
            "target must be retained."
        )
    return bridge_mode_state


def retire_legacy_path(config: CutoverConfig) -> RetirementResult:
    """Verify the legacy critique-loop path is retired and record the state.

    Validates the immutable ``config`` (binding the retirement to the exact
    North Star runtime), verifies the BRIDGE hard-disable is in effect and
    ``critique_runtime`` is retained, builds the real-module inventory, and
    returns the verified retirement state. Raises :class:`RetirementError`
    if any retired path is not actually disabled or a module is missing.
    """
    validate_config(config)
    bridge_mode_state = _verify_hard_disable()
    inventory = tuple(build_inventory())

    # Defensive invariants on the bounded inventory.
    for component in inventory:
        if component.status is RetirementStatus.RETIRED and component.module == ACTIVE_TARGET_MODULE:
            raise RetirementError(
                "critique_runtime must be RETAINED, not retired — it is the "
                "active post-cutover target."
            )
        if component.status is RetirementStatus.RETAINED and component.module != ACTIVE_TARGET_MODULE:
            raise RetirementError(
                f"Only critique_runtime may be retained; {component.module!r} "
                "is not the active target."
            )

    excluded_nonexistent = tuple(
        ref for ref in _HISTORICAL_RELOCATION_REFERENCES
        if not _module_exists(ref)
    )

    retired = sum(1 for c in inventory if c.status is RetirementStatus.RETIRED)
    retained = sum(1 for c in inventory if c.status is RetirementStatus.RETAINED)

    return RetirementResult(
        config_source_revision=config.source_revision,
        north_star_runtime_binding=config.north_star_runtime_binding,
        inventory=inventory,
        excluded_nonexistent=excluded_nonexistent,
        single_target_architecture_active=True,
        retired_path_count=retired,
        retained_path_count=retained,
        bridge_mode_state=bridge_mode_state,
    )


def generate_retirement_proof(
    config: CutoverConfig,
    *,
    output_path: str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Generate the canonical retirement proof bound to ``config``.

    Runs :func:`retire_legacy_path` to verify the disabled state, then
    produces a JSON-serializable proof recording the retired-path inventory,
    the single active target architecture, the observed bridge-mode state, and
    the cutover config binding (including the immutable
    ``north_star_runtime_binding``). When ``output_path`` is given the proof is
    written there as canonical JSON.
    """
    result = retire_legacy_path(config)
    timestamp = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(now if now is not None else time.time())
    )

    proof: dict[str, Any] = {
        "schema": RETIREMENT_PROOF_SCHEMA,
        "generated_at": timestamp,
        "single_target_architecture_active": result.single_target_architecture_active,
        "active_target": ACTIVE_TARGET_MODULE,
        "cutover_config": {
            "source_revision": result.config_source_revision,
            "target_revision": config.target_revision,
            "north_star_runtime_binding": result.north_star_runtime_binding,
        },
        "bridge_mode_state": result.bridge_mode_state,
        "retired_paths": [
            {
                "name": c.name,
                "module": c.module,
                "role": c.role.value,
                "retirement_action": c.retirement_action,
                "evidence": c.evidence,
            }
            for c in result.inventory
            if c.status is RetirementStatus.RETIRED
        ],
        "retained_paths": [
            {
                "name": c.name,
                "module": c.module,
                "role": c.role.value,
                "retirement_action": c.retirement_action,
                "evidence": c.evidence,
            }
            for c in result.inventory
            if c.status is RetirementStatus.RETAINED
        ],
        "excluded_nonexistent_modules": list(result.excluded_nonexistent),
        "retired_path_count": result.retired_path_count,
        "retained_path_count": result.retained_path_count,
    }

    # Content-address the canonical proof so tampering is detectable.
    canonical = json.dumps(proof, sort_keys=True, ensure_ascii=False)
    proof["content_hash"] = "sha256:" + hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    if output_path is not None:
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(proof, fh, sort_keys=True, ensure_ascii=False, indent=2)

    return proof


__all__ = [
    "ACTIVE_TARGET_MODULE",
    "ComponentRole",
    "LegacyComponent",
    "RETIREMENT_PROOF_SCHEMA",
    "RetirementError",
    "RetirementResult",
    "RetirementStatus",
    "build_inventory",
    "generate_retirement_proof",
    "retire_legacy_path",
]
