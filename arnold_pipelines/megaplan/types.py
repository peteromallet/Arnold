"""Type definitions, constants, and exceptions for megaplan."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, NotRequired, TypedDict

from arnold.runtime.errors import ArnoldError

# Re-export AgentSpec, format_agent_spec, and parse_agent_spec from the SSoT
# so that identity holds across the megaplan/arnold.agent boundary.
from arnold.agent.contracts import AgentMode, AgentSpec, format_agent_spec, parse_agent_spec

if TYPE_CHECKING:
    from arnold_pipelines.megaplan.planning.state import PlanCurrentState

# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------
DriverOutcomeStatus = Literal[
    "done",
    "finalized",
    "paused",
    "stalled",
    "escalated",
    "failed",
    "aborted",
    "cancelled",
    "cap",
    "blocked",
    "cost_cap_exceeded",
    "context_retry_exhausted",
    "worker_blocked",
    "infrastructure_error",
    "human_required",
    "awaiting_human",
    "tiebreaker_pending",
    "tiebreaker_ready",
]


# ---------------------------------------------------------------------------
# TypedDicts
# ---------------------------------------------------------------------------

class PlanConfig(TypedDict, total=False):
    project_dir: str
    auto_approve: bool
    robustness: str
    mode: str
    output_path: str
    from_doc: str
    agents: dict[str, str]
    workers: NotRequired[dict[str, Any]]
    max_tiebreakers_per_plan: int
    tiebreaker_blocklist: list[str]
    allow_tiebreaker: bool
    tiebreaker_token_budget: int
    tiebreaker_time_budget_minutes: int
    strict_notes: NotRequired[bool]
    prep_clarify: NotRequired[bool]
    # Completion-verification contract mode: off | shadow | warn | enforce.
    # Default "shadow" = compute + persist + log a verdict, never block, never
    # run the suite. warn/enforce are not yet implemented (behave like shadow +
    # a logged WARNING). See megaplan/orchestration/completion_contract.py.
    completion_contract_mode: NotRequired[str]
    # Full-suite backstop mode: off | shadow | enforce.
    # Default "shadow" = run and record one unscoped suite before milestone
    # advance, never block. enforce blocks only on computed suite failures.
    full_suite_backstop_mode: NotRequired[str]
    # Shell command the harness uses to run the test suite (e.g. "pytest").
    test_command: NotRequired[str]
    # Timeout in seconds for the baseline-capture / verification test run.
    test_baseline_timeout: NotRequired[int]


class PlanMeta(TypedDict, total=False):
    significant_counts: list[int]
    weighted_scores: list[float]
    plan_deltas: list[float | None]
    recurring_critiques: list[str]
    total_cost_usd: float
    overrides: list[dict[str, Any]]
    notes: list[dict[str, Any]]
    imported_decisions: list["SettledDecisionFromDoc"]
    user_approved_gate: bool
    anchors: NotRequired["AnchorsMeta"]


class AnchorDocumentMeta(TypedDict, total=False):
    scope: str
    source_kind: str
    source_path: str
    source_spec_path: str
    artifact_path: str
    title: str
    sha256: str
    size_bytes: int
    captured_at: str
    label: str


class AnchorTypeMeta(TypedDict, total=False):
    anchor_type: str
    documents: list[AnchorDocumentMeta]
    combined_artifact_path: str


class AnchorsMeta(TypedDict, total=False):
    schema_version: int
    by_type: dict[str, AnchorTypeMeta]


class SessionInfo(TypedDict, total=False):
    id: str
    mode: str
    created_at: str
    last_used_at: str
    refreshed: bool
    # Fingerprint of the sandbox-affecting config captured when this session
    # was created (see megaplan.workers._sandbox_fingerprint). At resume
    # time we refuse to reuse a session whose fingerprint no longer matches
    # the current invocation — otherwise codex silently keeps the old
    # sandbox when the operator toggles MEGAPLAN_TRUSTED_CONTAINER or
    # changes --work-dir, leading to repeated invisible failures.
    sandbox_hash: str


class ActivePhase(TypedDict, total=False):
    phase: str
    agent: str
    mode: str
    model: str
    run_id: str
    session_id: str
    started_at: str
    attempt: int
    last_activity_at: str
    last_activity_kind: str
    last_activity_detail: str
    configured_specs: list[str]
    attempted_specs: list[str]
    selected_spec_index: int
    selected_spec_total: int
    fallback_trigger: str | None
    failed_attempt_reasons: list[str]


class PlanVersionRecord(TypedDict, total=False):
    version: int
    file: str
    hash: str
    timestamp: str


class HistoryEntry(TypedDict, total=False):
    step: str
    timestamp: str
    duration_ms: int
    cost_usd: float
    cost_pricing: str
    result: str
    session_mode: str
    session_id: str
    agent: str
    output_file: str
    artifact_hash: str
    finalize_hash: str
    raw_output_file: str
    message: str
    flags_count: int
    flags_addressed: list[Any]
    recommendation: str
    approval_mode: str
    environment: dict[str, bool]
    configured_specs: list[str]
    attempted_specs: list[str]
    selected_spec_index: int
    selected_spec_total: int
    fallback_trigger: str | None
    failed_attempt_reasons: list[str]


class ClarificationRecord(TypedDict, total=False):
    refined_idea: str
    intent_summary: str
    questions: list[str]
    # 'prep' when halt is from prep ambiguity; absent for criteria-verification halts.
    # Convention: gate serializes blocking items as human-readable strings
    # (e.g. "[blocking] <question>"); structured data (severity/assumption) lives
    # only in prep.json, not here.
    source: str


class LastGateRecord(TypedDict, total=False):
    """Deprecated legacy state cache; prefer plan_dir/gate_carry.json."""

    recommendation: str
    rationale: str
    signals_assessment: str
    warnings: list[str]
    settled_decisions: list["SettledDecision"]
    passed: bool
    preflight_results: dict[str, bool]
    orchestrator_guidance: str


class PlanState(TypedDict):
    name: str
    idea: str
    idea_snapshot_path: NotRequired[str]
    current_state: "PlanCurrentState"
    iteration: int
    created_at: str
    config: PlanConfig
    sessions: dict[str, SessionInfo]
    plan_versions: list[PlanVersionRecord]
    history: list[HistoryEntry]
    meta: PlanMeta
    active_step: NotRequired[ActivePhase]
    clarification: NotRequired[ClarificationRecord]
    latest_failure: NotRequired[dict[str, Any] | None]
    resume_cursor: NotRequired[dict[str, Any] | None]


class _FlagRecordRequired(TypedDict):
    id: str
    concern: str
    category: str
    status: str


class FlagRecord(_FlagRecordRequired, total=False):
    severity_hint: str
    evidence: str
    raised_in: str
    severity: str
    verified: bool
    verified_in: str
    addressed_in: str
    settled_by_tiebreaker: str
    resolution: dict[str, Any]
    verify_rationale: str


class FlagRegistry(TypedDict):
    flags: list[FlagRecord]


class GateCheckResult(TypedDict):
    passed: bool
    criteria_check: dict[str, Any]
    preflight_results: dict[str, bool]
    unresolved_flags: list[FlagRecord]


class SettledDecision(TypedDict, total=False):
    id: str
    decision: str
    rationale: str


class SettledDecisionFromDoc(TypedDict, total=False):
    id: str
    decision: str
    rationale: str
    load_bearing: bool


class StepResponse(TypedDict, total=False):
    success: bool
    step: str
    summary: str
    artifacts: list[str]
    next_step: str | None
    state: str
    auto_approve: bool
    robustness: str
    iteration: int
    plan: str
    plan_dir: str
    questions: list[str]
    verified_flags: list[str]
    open_flags: list[str]
    scope_creep_flags: list[str]
    warnings: list[str]
    files_changed: list[str]
    deviations: list[str]
    user_approved_gate: bool
    issues: list[str]
    valid_next: list[str]
    mode: str
    installed: list[dict[str, Any]]
    config_path: str
    routing: dict[str, str]
    raw_config: dict[str, Any]
    action: str
    key: str
    value: str
    skipped: bool
    file: str
    plans: list[dict[str, Any]]
    recommendation: str
    signals: dict[str, Any]
    rationale: str
    signals_assessment: str
    orchestrator_guidance: str
    passed: bool
    criteria_check: dict[str, Any]
    preflight_results: dict[str, bool]
    unresolved_flags: list[Any]
    prep_signal: dict[str, Any]
    route_signal: str
    gate_signal: dict[str, Any]
    debt_payload: dict[str, Any]
    fallback_payload: dict[str, Any]
    error: str
    message: str
    details: dict[str, Any]
    agent_fallback: dict[str, str]


class DebtEntry(TypedDict):
    id: str
    subsystem: str
    concern: str
    flag_ids: list[str]
    plan_ids: list[str]
    occurrence_count: int
    created_at: str
    updated_at: str
    resolved: bool
    resolved_by: str | None
    resolved_at: str | None


class DebtRegistry(TypedDict):
    entries: list[DebtEntry]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FLAG_BLOCKING_STATUSES = {"open", "disputed", "addressed"}
FLAG_VALID_STATUSES = {
    "open", "addressed", "disputed", "verified",
    "accepted_tradeoff", "gate_disputed",
}
DEBT_ESCALATION_THRESHOLD = 3
MOCK_ENV_VAR = "MEGAPLAN_MOCK_WORKERS"
PREMIUM_AGENT = "premium"


# ---------------------------------------------------------------------------
# Agent spec parsing
# ---------------------------------------------------------------------------

# Premium agent vendors that support model:effort three-part specs.
_PREMIUM_VENDORS = frozenset({"claude", "codex"})

# Canonical per-vendor valid effort sets — the SINGLE source of truth for
# what an effort token may be in an agent spec. These are the *spec-layer*
# effort tokens (the thinking-depth ladder applied by --depth / --phase-model),
# The Codex CLI dispatch layer accepts the same full ladder and passes explicit
# xhigh/max requests through unchanged; it must not silently clamp them.
#
# Both premium vendors accept the full depth ladder at the spec layer because
# --depth (VALID_DEPTH_CHOICES) can produce e.g. ``codex:max`` / ``claude:minimal``.
_VALID_CLAUDE_SPEC_EFFORTS: frozenset[str] = frozenset(
    {"minimal", "low", "medium", "high", "xhigh", "max"}
)
_VALID_CODEX_SPEC_EFFORTS: frozenset[str] = frozenset(
    {"minimal", "low", "medium", "high", "xhigh", "max"}
)

_VALID_PREMIUM_EFFORTS: dict[str, frozenset[str]] = {
    "claude": _VALID_CLAUDE_SPEC_EFFORTS,
    "codex": _VALID_CODEX_SPEC_EFFORTS,
}

# All known effort tokens across both premium agents — used for
# disambiguation in parse_agent_spec (reserved tokens can never be
# interpreted as model-only strings for premium agents).
_PREMIUM_EFFORT_TOKENS: frozenset[str] = (
    _VALID_CLAUDE_SPEC_EFFORTS | _VALID_CODEX_SPEC_EFFORTS
)


def is_premium_placeholder_agent(agent: str) -> bool:
    """True when *agent* is the symbolic premium placeholder."""
    return agent == PREMIUM_AGENT


def is_premium_placeholder_spec(spec: str | "AgentSpec") -> bool:
    """True when *spec* is the symbolic premium placeholder spec."""
    parsed = spec if isinstance(spec, AgentSpec) else parse_agent_spec(spec)
    return is_premium_placeholder_agent(parsed.agent)


def resolve_premium_placeholder_agent(agent: str, vendor: str) -> str:
    """Resolve the symbolic premium placeholder agent to a concrete vendor."""
    return vendor if is_premium_placeholder_agent(agent) else agent


def resolve_premium_placeholder_spec(spec: str | "AgentSpec", vendor: str) -> "AgentSpec":
    """Resolve a symbolic premium placeholder spec to a concrete vendor spec."""
    parsed = spec if isinstance(spec, AgentSpec) else parse_agent_spec(spec)
    if not is_premium_placeholder_agent(parsed.agent):
        return parsed
    return AgentSpec(
        agent=resolve_premium_placeholder_agent(parsed.agent, vendor),
        model=parsed.model,
        effort=parsed.effort,
    )


def _is_codex_model_name(name: str) -> bool:
    """True if *name* names a Codex / GPT-5.x model.

    Accepts ``gpt-5.5``, ``gpt-5.4``, ``gpt-5.3-codex``, ``gpt-5.1-codex-max``,
    and ``openai/gpt-5*`` forms.
    """
    lowered = name.lower()
    return lowered.startswith("gpt-5") or "/gpt-5" in lowered or "codex" in lowered




# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class CliError(ArnoldError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        valid_next: list[str] | None = None,
        extra: dict[str, Any] | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(code, message, exit_code=exit_code)
        self.valid_next = valid_next or []
        self.extra = extra or {}


_ROBUSTNESS_ACCEPTED = (
    "bare",
    "light",
    "full",
    "thorough",
    "extreme",
    "tiny",
    "standard",
    "robust",
    "superrobust",
)


def legacy_agent_model(spec: AgentSpec) -> tuple[str, str | None]:
    """Return ``(agent, model)`` from an AgentSpec for legacy callers.

    For premium agents the *model* field may be ``None`` (when only effort
    was specified).  Legacy callers that previously used the two-tuple
    ``(agent, model)`` should migrate to :class:`AgentSpec` accessors,
    but this helper bridges the gap.
    """
    return (spec.agent, spec.model)


def resolved_default_model_for_agent(agent: str) -> str | None:
    """Return the pinned default model for *agent*, or ``None``.

    >>> resolved_default_model_for_agent("claude")
    'claude-opus-4-7'
    >>> resolved_default_model_for_agent("codex")
    'gpt-5.5'
    >>> resolved_default_model_for_agent("hermes") is None
    True
    """
    from arnold_pipelines.megaplan.defaults import CLAUDE_DEFAULT_MODEL, CODEX_DEFAULT_MODEL

    if agent == "claude":
        return CLAUDE_DEFAULT_MODEL
    if agent == "codex":
        return CODEX_DEFAULT_MODEL
    return None


# PR sync state classifications — used by ChainState to report whether
# the milestone branch/PR is up-to-date with local and remote heads.
SYNC_CLEAN = "clean"      # branch head, PR head, and last pushed commit all agree; worktree clean
SYNC_STALE = "stale"      # local branch head is behind remote/PR head (needs fetch/rebase)
SYNC_DIRTY = "dirty"      # uncommitted changes in worktree or diverged from pushed commit

SCOPE_CREEP_TERMS = (
    "scope creep",
    "out of scope",
    "beyond the original idea",
    "beyond original idea",
    "beyond user intent",
    "expanded scope",
)

DEFAULTS = {
    "execution.auto_approve": False,
    "execution.robustness": "full",
    "execution.strict_notes": False,
    "execution.worker_timeout_seconds": 7200,
    "execution.max_review_rework_cycles": 3,
    "execution.max_robust_review_rework_cycles": 2,
    "execution.max_execute_no_progress": 3,
    # Plan-critique loop cap (mirrors the execute-review rework cap). Counts
    # ITERATE rounds; full/light use max_critique_iterations, thorough/extreme
    # use max_robust_critique_iterations. max_critique_no_progress is the
    # trailing-window length for the no-net-progress early stop. Defaults are
    # generous: a healthy plan converges in 1-2 rounds, well under the cap.
    "execution.max_critique_iterations": 4,
    "execution.max_robust_critique_iterations": 6,
    "execution.max_critique_no_progress": 2,
    "execution.max_tasks_per_batch": 5,
    # When True, the execute auto-loop starts a FRESH worker session for every
    # batch instead of carrying one persistent session across all batches. Each
    # batch prompt already embeds the completed-task context it needs, so a fresh
    # session loses nothing essential — but it bounds per-batch context to a
    # single batch (~tens of K tokens) instead of letting the persistent session
    # history snowball across batches (observed at 2-3M cumulative input tokens
    # on large plans, which both blew up cost on high-context models and wedged
    # Claude turns past the stream-idle bound). Default True to make execution of
    # large plans converge; set False to restore cross-batch session continuity.
    "execution.fresh_session_per_batch": True,
    "orchestration.max_critique_concurrency": 6,
    "orchestration.mode": "subagent",
    "execution.adaptive_critique": False,
    "execution.critic_model": "",
    # When True AND adaptive_critique resolves True, the critique handler will
    # raise AdaptiveCritiqueDegradedError instead of silently downgrading to
    # static lenses. Default False for backward compatibility. Recommended for
    # production / CI / important runs. See docs/critique.md.
    "execution.strict_adaptive_critique": False,
    # Completion-verification contract mode. "shadow" (default) computes +
    # persists + logs a verdict at every terminal transition but NEVER blocks
    # and NEVER runs the test suite. "off" disables it; "warn"/"enforce" are
    # stubs that currently behave like shadow + a logged WARNING (the
    # fail-closed behaviour is a documented TODO). See
    # megaplan/orchestration/completion_contract.py.
    "execution.completion_contract_mode": "shadow",
    # One full unscoped suite before milestone advance. Shadow records the
    # result without blocking; enforce blocks only on computed full-suite
    # failures, not runner errors.
    "execution.full_suite_backstop_mode": "shadow",
    # Test command the harness invokes for baseline capture / verification.
    "execution.test_command": None,
    # Timeout in seconds for the baseline-capture / verification test run.
    "execution.test_baseline_timeout": 900,
    # Opt-in per-worker filesystem-state isolation. A list of env var names;
    # for EACH worker spawn megaplan mints a fresh unique temp dir per listed
    # var (under the OS temp dir) and exports VAR=<that tmpdir> into the
    # worker subprocess env, so concurrent workers don't share per-user state
    # behind those vars. Default [] = no isolation (env built as before). See
    # _apply_worker_state_isolation in megaplan/workers/_impl.py.
    "execution.worker_isolated_env_vars": [],
    "signing.warrant_key": "",
}

# Valid pin values for execution.critic_model. Mirrors CRITIC_MODEL_ROSTER in
# megaplan.audits.critique_evaluator (kept in sync by hand — both are short and
# stable). "" disables the pin so the adaptive evaluator assigns critics
# dynamically per lens.
CRITIC_MODEL_CHOICES = (
    "",
    "claude-opus-4-7",
    "gpt-5.5",
    "claude-sonnet-4-6",
    "deepseek-v4-pro",
    "deepseek-v4-flash",
)

_SETTABLE_BOOL = {
    "execution.auto_approve",
    "execution.adaptive_critique",
    "execution.strict_adaptive_critique",
    "execution.strict_notes",
    "execution.fresh_session_per_batch",
}

_SETTABLE_ENUM = {
    "execution.robustness": _ROBUSTNESS_ACCEPTED,
    "execution.critic_model": CRITIC_MODEL_CHOICES,
    "execution.completion_contract_mode": ("off", "shadow", "warn", "enforce"),
    "execution.full_suite_backstop_mode": ("off", "shadow", "enforce"),
}

_SETTABLE_NUMERIC = {
    "execution.worker_timeout_seconds",
    "execution.max_review_rework_cycles",
    "execution.max_robust_review_rework_cycles",
    "execution.max_execute_no_progress",
    "execution.max_tasks_per_batch",
    "execution.max_critique_iterations",
    "execution.max_robust_critique_iterations",
    "execution.max_critique_no_progress",
    "orchestration.max_critique_concurrency",
    "execution.test_baseline_timeout",
}

_SETTABLE_STRING = {
    "execution.test_command",
}


class AdaptiveCritiqueMisconfiguredError(RuntimeError):
    """Raised at ``init`` when adaptive_critique is requested but the runtime
    wiring (step schema, schema dict entry, prompt template) is incomplete.

    Fails fast so no execute-time cost is paid before the operator sees the
    misconfiguration. The layered defense added in PR #52 (May 2026) checks
    these probes at init so the silent KeyError fallback that hid the
    original adaptive-critique bug for every ``partnered`` / ``premium`` /
    ``apex`` run cannot recur.
    """

    def __init__(self, message: str, *, missing: list[str] | None = None) -> None:
        super().__init__(message)
        self.missing = list(missing or [])


class AdaptiveCritiqueDegradedError(RuntimeError):
    """Raised by the critique handler when adaptive critique would silently
    fall back to static lenses AND ``execution.strict_adaptive_critique`` is
    True.

    The default (non-strict) behaviour is to log a loud stderr warning and
    proceed with static lenses. Strict mode is the recommended setting for
    production / CI / important runs — see docs/critique.md.
    """

    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason


# Re-export runtime exceptions for convenience (SD3).
from arnold_pipelines.megaplan.runtime.process import OrphanDetectedError  # noqa: E402, F401
