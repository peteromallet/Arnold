"""Compatibility facade for orchestration evaluation helpers.

Canonical implementations: :mod:`arnold.pipelines.megaplan.orchestration.*`
"""

from __future__ import annotations

import subprocess  # kept as module attribute for monkeypatch compatibility
from arnold.pipelines.megaplan.orchestration.execution_evidence import validate_execution_evidence
from arnold.pipelines.megaplan.orchestration.gate_checks import (
    AGENT_AVAILABILITY_PREFLIGHT_CHECKS,
    build_gate_artifact,
    build_orchestrator_guidance,
    failed_preflight_checks,
    only_agent_availability_preflight_failed,
    run_gate_checks,
)
from arnold.pipelines.megaplan.orchestration.gate_signals import (
    build_gate_signals,
    compute_plan_delta_percent,
    compute_recurring_critiques,
    flag_weight,
)
from arnold.pipelines.megaplan.orchestration.plan_structure import (
    PLAN_STRUCTURE_REQUIRED_STEP_ISSUE,
    PlanSection,
    _strip_fenced_blocks,
    parse_plan_sections,
    reassemble_plan,
    renumber_steps,
    validate_plan_structure,
)
from arnold.pipelines.megaplan.orchestration.rubber_stamp import is_rubber_stamp


from arnold.pipelines.megaplan.loop.git import (  # noqa: E402
    _collect_git_status_paths_with_nested_repos,
    _discover_nested_git_repos,
    _normalize_repo_path,
    _parse_git_status_paths,
    _run_git_status_paths,
)
