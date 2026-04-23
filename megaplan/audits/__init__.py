"""Audits subpackage — audit engine, verifiability, iteration pressure, quality gates, robustness checks, and capabilities.

This ``__init__`` re-exports every name historically imported from the
pre-refactor top-level modules (``megaplan.audit``, ``megaplan.verifiability``,
``megaplan.iteration_pressure``, ``megaplan.quality``, ``megaplan.checks``,
``megaplan.capabilities``) so that any lingering ``from megaplan.audits import X``
style callers keep working. The canonical import paths are now
``megaplan.audits.audit_engine``, ``megaplan.audits.verifiability``,
``megaplan.audits.iteration``, ``megaplan.audits.quality_gates``,
``megaplan.audits.robustness``, and ``megaplan.audits.capabilities``.
"""

from megaplan.audits.audit_engine import (
    AUDIT_FILE,
    _compute_totals,
    _empty_totals,
    _next_index,
    aggregate_tiebreaker_audit,
    load_tiebreaker_audit,
    record_tiebreaker_audit,
    render_audit_report,
    resolve_plan_dir,
)
from megaplan.audits.verifiability import (
    ALL_CAPABILITIES as _AUDITS_ALL_CAPABILITIES,  # re-export also lives in .capabilities
    CriterionAudit,
    HUMAN_CAPABILITIES as _AUDITS_HUMAN_CAPABILITIES,
    audit_criteria,
    classify_criteria,
    validate_requires,
)
from megaplan.audits.iteration import (
    IterationPressureEntry,
    _concern_word_set,
    _jaccard_similarity as _iteration_jaccard_similarity,
    compute_flag_history,
    compute_fuzzy_groups,
    compute_iteration_pressure,
    has_mechanical_recurrence,
    render_pressure_table,
)
from megaplan.audits.quality_gates import (
    DEFAULT_DUPLICATE_MAX_FILE_LINES,
    DEFAULT_DUPLICATE_SIMILARITY_THRESHOLD,
    DEFAULT_FILE_GROWTH_THRESHOLD,
    DEFAULT_TIME_BUDGET_SECONDS,
    capture_before_line_counts,
    run_quality_checks,
)
from megaplan.audits.robustness import (
    CRITIQUE_CHECKS,
    CritiqueCheckSpec,
    JOKE_CRITIQUE_CHECKS,
    VALID_SEVERITY_HINTS,
    build_check_category_map,
    build_empty_template,
    checks_for_robustness,
    get_check_by_id,
    get_check_ids,
    joke_checks_for_robustness,
    validate_critique_checks,
)
from megaplan.audits.capabilities import (
    ALL_CAPABILITIES,
    CONTAINER_CAPABILITIES,
    DEFAULT_AGENT_ROUTING,
    DEFAULT_CONTAINER_CAPABILITIES,
    DEFAULT_HUMAN_CAPABILITIES,
    HUMAN_CAPABILITIES,
    get_worker_capabilities,
    union_verifies,
    validate_capabilities,
)
from megaplan.audits.hermes_vendoring import (
    CONDITIONAL_RETENTION_DIRS,
    DEAD_WEIGHT_PATTERNS,
    JOB_B_SCOPE_FENCE_ENTRIES,
    RUNTIME_REQUIRED_ENTRIES,
    VendoredAgentHistoryAudit,
    VendoredAgentTreeAudit,
    audit_vendored_agent_history,
    audit_vendored_agent_tree,
    find_retention_import_sites,
)

__all__ = [
    # audit_engine
    "AUDIT_FILE",
    "aggregate_tiebreaker_audit",
    "load_tiebreaker_audit",
    "record_tiebreaker_audit",
    "render_audit_report",
    "resolve_plan_dir",
    # verifiability
    "CriterionAudit",
    "audit_criteria",
    "classify_criteria",
    "validate_requires",
    # iteration
    "IterationPressureEntry",
    "compute_flag_history",
    "compute_fuzzy_groups",
    "compute_iteration_pressure",
    "has_mechanical_recurrence",
    "render_pressure_table",
    # quality_gates
    "DEFAULT_DUPLICATE_MAX_FILE_LINES",
    "DEFAULT_DUPLICATE_SIMILARITY_THRESHOLD",
    "DEFAULT_FILE_GROWTH_THRESHOLD",
    "DEFAULT_TIME_BUDGET_SECONDS",
    "capture_before_line_counts",
    "run_quality_checks",
    # robustness
    "CRITIQUE_CHECKS",
    "CritiqueCheckSpec",
    "JOKE_CRITIQUE_CHECKS",
    "VALID_SEVERITY_HINTS",
    "build_check_category_map",
    "build_empty_template",
    "checks_for_robustness",
    "get_check_by_id",
    "get_check_ids",
    "joke_checks_for_robustness",
    "validate_critique_checks",
    # capabilities
    "ALL_CAPABILITIES",
    "CONTAINER_CAPABILITIES",
    "DEFAULT_AGENT_ROUTING",
    "DEFAULT_CONTAINER_CAPABILITIES",
    "DEFAULT_HUMAN_CAPABILITIES",
    "HUMAN_CAPABILITIES",
    "get_worker_capabilities",
    "union_verifies",
    "validate_capabilities",
    # hermes_vendoring
    "CONDITIONAL_RETENTION_DIRS",
    "DEAD_WEIGHT_PATTERNS",
    "JOB_B_SCOPE_FENCE_ENTRIES",
    "RUNTIME_REQUIRED_ENTRIES",
    "VendoredAgentHistoryAudit",
    "VendoredAgentTreeAudit",
    "audit_vendored_agent_history",
    "audit_vendored_agent_tree",
    "find_retention_import_sites",
]
