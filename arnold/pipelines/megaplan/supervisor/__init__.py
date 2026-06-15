"""M5d — Supervisor tier: general cross-run orchestration.

The supervisor tier sits below cloud's operator loop and provides
cross-run outcome normalization, chain orchestration, and run-state
projection.  It consumes the shared ``RunOutcome`` vocabulary from
``megaplan.run_outcome`` and preserves driver-level diagnostic metadata.

.. note::
    The cloud tier (``megaplan/cloud/supervise.py``) remains the long-lived
    tick host above the supervisor and is explicitly anti-scope for M5d.
"""

from arnold.pipelines.megaplan.supervisor.outcomes import (
    NORMALIZED_FROM_DRIVER_SOURCE,
    NormalizedOutcome,
    normalize_driver_outcome,
    normalize_driver_outcome_from_dict,
)
from arnold.pipelines.megaplan.supervisor.driver import (
    DEFAULT_ESCALATE_ACTION,
    DefaultRunDriver,
    PackRunner,
    PhaseCompleteHook,
    RunDriver,
    RunRequest,
    RunWriter,
)
from arnold.pipelines.megaplan.supervisor.model import (
    BakeoffParallelGroup,
    DependencyAssertion,
    RunNode,
    RunRecord,
    SupervisorState,
    SupervisorVariantKind,
    dependency_assertions_for_nodes,
)
from arnold.pipelines.megaplan.supervisor.state import (
    load_supervisor_state,
    save_supervisor_state,
    supervisor_state_path,
    supervisor_state_root,
    validate_supervisor_state,
)
from arnold.pipelines.megaplan.supervisor.ladder import (
    APEX_EXTREME_RETRY_LIMIT,
    DEFAULT_RETRY_LIMIT,
    DEPTH_BUMP_ORDER,
    LadderAction,
    LadderDecision,
    PROFILE_BUMP_ORDER,
    ROBUSTNESS_BUMP_ORDER,
    SupervisorLadderPolicy,
    apply_ladder,
    bump_one_tier,
    emit_terminal_ticket,
    select_neutral_target,
)
from arnold.pipelines.megaplan.supervisor.chain_runner import ChainMilestonePackRunner, run_chain
from arnold.pipelines.megaplan.supervisor.bakeoff_binding import (
    BAKEOFF_TARGET_COMPARE,
    BAKEOFF_TARGET_MERGE,
    BAKEOFF_TARGET_RUN_PROFILES,
    BAKEOFF_TARGET_SELECT,
    BakeoffControlBinding,
    bakeoff_control_binding,
    bakeoff_run_state_view,
)
from arnold.pipelines.megaplan.supervisor.bakeoff_runner import run_bakeoff as run_supervisor_bakeoff

__all__ = [
    "APEX_EXTREME_RETRY_LIMIT",
    "BAKEOFF_TARGET_COMPARE",
    "BAKEOFF_TARGET_MERGE",
    "BAKEOFF_TARGET_RUN_PROFILES",
    "BAKEOFF_TARGET_SELECT",
    "DEFAULT_ESCALATE_ACTION",
    "DEFAULT_RETRY_LIMIT",
    "DEPTH_BUMP_ORDER",
    "BakeoffParallelGroup",
    "BakeoffControlBinding",
    "ChainMilestonePackRunner",
    "DefaultRunDriver",
    "DependencyAssertion",
    "LadderAction",
    "LadderDecision",
    "NORMALIZED_FROM_DRIVER_SOURCE",
    "NormalizedOutcome",
    "PackRunner",
    "PhaseCompleteHook",
    "PROFILE_BUMP_ORDER",
    "ROBUSTNESS_BUMP_ORDER",
    "RunNode",
    "RunDriver",
    "RunRecord",
    "RunRequest",
    "RunWriter",
    "SupervisorState",
    "SupervisorLadderPolicy",
    "SupervisorVariantKind",
    "apply_ladder",
    "bakeoff_control_binding",
    "bakeoff_run_state_view",
    "bump_one_tier",
    "dependency_assertions_for_nodes",
    "emit_terminal_ticket",
    "load_supervisor_state",
    "normalize_driver_outcome",
    "normalize_driver_outcome_from_dict",
    "run_chain",
    "run_supervisor_bakeoff",
    "save_supervisor_state",
    "select_neutral_target",
    "supervisor_state_path",
    "supervisor_state_root",
    "validate_supervisor_state",
]
