"""Type definitions, constants, and exceptions for megaplan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NotRequired, TypedDict


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------

STATE_INITIALIZED = "initialized"
STATE_PREPPED = "prepped"
STATE_PLANNED = "planned"
STATE_CRITIQUED = "critiqued"
STATE_GATED = "gated"
STATE_FINALIZED = "finalized"
STATE_EXECUTED = "executed"
STATE_REVIEWED = "reviewed"
STATE_DONE = "done"
STATE_ABORTED = "aborted"
STATE_FAILED = "failed"
STATE_BLOCKED = "blocked"
STATE_PAUSED = "paused"
STATE_CANCELLED = "cancelled"
STATE_AWAITING_PR_MERGE = "awaiting_pr_merge"
STATE_AWAITING_HUMAN = "awaiting_human_verify"
STATE_TIEBREAKER_PENDING = "tiebreaker_pending"
STATE_TIEBREAKER_READY = "tiebreaker_ready"
TERMINAL_STATES = {STATE_DONE, STATE_ABORTED, STATE_FAILED, STATE_BLOCKED, STATE_CANCELLED}
AUTOMATION_TERMINAL_STATES = TERMINAL_STATES | {
    STATE_PAUSED,
    STATE_AWAITING_HUMAN,
    STATE_TIEBREAKER_PENDING,
    STATE_TIEBREAKER_READY,
}


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


class ActiveStep(TypedDict, total=False):
    step: str
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


class ClarificationRecord(TypedDict, total=False):
    refined_idea: str
    intent_summary: str
    questions: list[str]


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
    current_state: str
    iteration: int
    created_at: str
    config: PlanConfig
    sessions: dict[str, SessionInfo]
    plan_versions: list[PlanVersionRecord]
    history: list[HistoryEntry]
    meta: PlanMeta
    active_step: NotRequired[ActiveStep]
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


class TiebreakerDecision(TypedDict, total=False):
    fuzzy_group_id: str
    flag_ids: list[str]
    question: str
    researcher_pick: str
    challenger_pick: str
    human_pick: str
    action: str
    rationale: str
    timestamp: str


class GatePayload(TypedDict):
    recommendation: str
    rationale: str
    signals_assessment: str
    warnings: list[str]
    settled_decisions: list[SettledDecision]


class GateArtifact(TypedDict, total=False):
    passed: bool
    criteria_check: dict[str, Any]
    preflight_results: dict[str, bool]
    unresolved_flags: list[FlagRecord]
    recommendation: str
    rationale: str
    signals_assessment: str
    warnings: list[str]
    settled_decisions: list[SettledDecision]
    override_forced: bool
    orchestrator_guidance: str
    robustness: str
    signals: dict[str, Any]


class GateSignals(TypedDict, total=False):
    robustness: str
    signals: dict[str, Any]
    warnings: list[str]


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

DEFAULT_AGENT_ROUTING: dict[str, str] = {
    "plan": "claude",
    "prep": "claude",
    "critique": "codex",
    "revise": "claude",
    "gate": "claude",
    "feedback": "claude:low",
    "finalize": "claude",
    "execute": "codex",
    "loop_plan": "claude",
    "loop_execute": "codex",
    "review": "codex",
    "tiebreaker_researcher": "codex",
    "tiebreaker_challenger": "codex",
}
KNOWN_AGENTS = ["claude", "codex", "hermes", "shannon"]
# Canonical robustness names — match docs/megaplan-decision.md.
ROBUSTNESS_LEVELS = ("bare", "light", "full", "thorough", "extreme")
# Legacy → canonical alias map. Old names remain accepted on the CLI and
# in stored state for backward compatibility; ``normalize_robustness``
# resolves them. The canonical name set above is what internal code
# (set comparisons, etc.) should always compare against.
ROBUSTNESS_ALIASES: dict[str, str] = {
    "tiny": "bare",
    "standard": "full",
    "robust": "thorough",
    "superrobust": "extreme",
}
# All accepted spellings on the CLI / config layer (canonical + legacy).
ROBUSTNESS_ACCEPTED = tuple(ROBUSTNESS_LEVELS) + tuple(ROBUSTNESS_ALIASES.keys())


def normalize_robustness(value: Any) -> str:
    """Return the canonical robustness name for ``value``.

    Accepts canonical names (``bare|light|full|thorough|extreme``) and
    the legacy ``tiny|light|standard|robust|superrobust`` aliases. Any
    other input — including ``None`` — falls back to the canonical
    default (``"full"``).
    """
    if isinstance(value, str):
        if value in ROBUSTNESS_LEVELS:
            return value
        if value in ROBUSTNESS_ALIASES:
            return ROBUSTNESS_ALIASES[value]
    return "full"


# ---------------------------------------------------------------------------
# Agent spec parsing
# ---------------------------------------------------------------------------

# Premium agent vendors that support model:effort three-part specs.
_PREMIUM_VENDORS = frozenset({"claude", "codex"})

# All known effort tokens across both premium agents — used for
# disambiguation in parse_agent_spec (reserved tokens can never be
# interpreted as model-only strings for premium agents).
_PREMIUM_EFFORT_TOKENS: frozenset[str] = frozenset({
    # Claude effort tokens
    "low", "medium", "high", "xhigh", "max",
    # Codex effort tokens
    "minimal",
})


@dataclass(frozen=True, slots=True)
class AgentSpec:
    """Parsed representation of an agent spec string.

    Supports unpacking as ``(agent, model)`` and equality comparison with
    plain tuples for backward compatibility with callers that predate
    the three-part ``claude/codex`` model syntax.
    """

    agent: str
    model: str | None = None
    effort: str | None = None

    def __iter__(self):
        """Backward compat: ``agent, model = spec`` ignores effort."""
        return iter((self.agent, self.model))

    def __eq__(self, other):
        if isinstance(other, AgentSpec):
            return (
                self.agent == other.agent
                and self.model == other.model
                and self.effort == other.effort
            )
        if isinstance(other, tuple):
            return (self.agent, self.model) == other
        return NotImplemented

    def __hash__(self):
        return hash((self.agent, self.model, self.effort))

    def __repr__(self):
        parts = [f"agent={self.agent!r}"]
        if self.model is not None:
            parts.append(f"model={self.model!r}")
        if self.effort is not None:
            parts.append(f"effort={self.effort!r}")
        return f"AgentSpec({', '.join(parts)})"


def parse_agent_spec(spec: str) -> AgentSpec:
    """Parse an agent spec string into an :class:`AgentSpec`.

    Spec syntax ::

        <agent>[:<model>][:<effort>]

    For **claude** and **codex** (premium agents), the first post-colon
    token is checked against reserved effort tokens; if it matches, the
    spec is treated as the legacy effort-only shape.  Otherwise it is
    treated as a model name, with an optional second ``:<effort>``
    segment.

    For **hermes** and **shannon**, the entire string after the first
    colon is the model — colons in the model name are preserved
    unchanged.

    Examples
    --------

    >>> parse_agent_spec("claude")
    AgentSpec(agent='claude', model=None, effort=None)
    >>> parse_agent_spec("claude:low")
    AgentSpec(agent='claude', model=None, effort='low')
    >>> parse_agent_spec("claude:sonnet-4.6:medium")
    AgentSpec(agent='claude', model='sonnet-4.6', effort='medium')
    >>> parse_agent_spec("codex:gpt-5.3-codex:high")
    AgentSpec(agent='codex', model='gpt-5.3-codex', effort='high')
    >>> parse_agent_spec("hermes:fireworks:accounts/foo")
    AgentSpec(agent='hermes', model='fireworks:accounts/foo', effort=None)
    """
    if ":" not in spec:
        return AgentSpec(agent=spec)

    agent, rest = spec.split(":", 1)

    # Non-premium agents (hermes, shannon): everything after the first
    # colon is the model — colons in the model string are preserved.
    if agent not in _PREMIUM_VENDORS:
        return AgentSpec(agent=agent, model=rest)

    # Premium agents (claude, codex): disambiguate effort vs model.
    # If the first token after ':' is a reserved effort token, treat
    # this as the legacy effort-only shape (claude:low, codex:high, etc.).
    if rest in _PREMIUM_EFFORT_TOKENS:
        return AgentSpec(agent=agent, effort=rest)

    # Everything after the first colon could be <model> or <model>:<effort>.
    if ":" in rest:
        model, effort = rest.split(":", 1)
        # Effort may be empty string if spec ends with colon; normalize to None.
        if not effort:
            effort = None
        return AgentSpec(agent=agent, model=model, effort=effort)

    # Single token that is not a reserved effort token → model-only.
    return AgentSpec(agent=agent, model=rest)


def format_agent_spec(spec: AgentSpec) -> str:
    """Format an :class:`AgentSpec` back to its canonical string form.

    >>> format_agent_spec(AgentSpec("claude"))
    'claude'
    >>> format_agent_spec(AgentSpec("claude", effort="low"))
    'claude:low'
    >>> format_agent_spec(AgentSpec("codex", model="gpt-5.3-codex", effort="high"))
    'codex:gpt-5.3-codex:high'
    >>> format_agent_spec(AgentSpec("hermes", model="fireworks:accounts/foo"))
    'hermes:fireworks:accounts/foo'
    """
    if spec.model is not None:
        base = f"{spec.agent}:{spec.model}"
    elif spec.effort is not None:
        base = f"{spec.agent}:{spec.effort}"
    else:
        base = spec.agent

    if spec.model is not None and spec.effort is not None:
        base = f"{base}:{spec.effort}"

    return base


def legacy_agent_model(spec: AgentSpec) -> tuple[str, str | None]:
    """Return ``(agent, model)`` from an AgentSpec for legacy callers.

    For premium agents the *model* field may be ``None`` (when only effort
    was specified).  Legacy callers that previously used the two-tuple
    ``(agent, model)`` should migrate to :class:`AgentSpec` accessors,
    but this helper bridges the gap.
    """
    return (spec.agent, spec.model)


@dataclass(frozen=True, slots=True)
class AgentMode:
    """Resolved agent mode returned by :func:`resolve_agent_mode`.

    Replaces the old ``(agent, mode, refreshed, model)`` tuple with
    explicit named fields plus resolved model defaults.

    Supports positional unpacking for backward compatibility during
    migration, but new callers should use named accessors.
    """

    agent: str
    mode: str
    refreshed: bool
    model: str | None = None
    effort: str | None = None
    resolved_model: str | None = None

    def __iter__(self):
        """Backward-compat: unpack as (agent, mode, refreshed, model)."""
        return iter((self.agent, self.mode, self.refreshed, self.model))

    def __eq__(self, other):
        if isinstance(other, AgentMode):
            return (
                self.agent == other.agent
                and self.mode == other.mode
                and self.refreshed == other.refreshed
                and self.model == other.model
                and self.effort == other.effort
                and self.resolved_model == other.resolved_model
            )
        if isinstance(other, tuple):
            return (self.agent, self.mode, self.refreshed, self.model) == other
        return NotImplemented

    def __hash__(self):
        return hash(
            (self.agent, self.mode, self.refreshed, self.model, self.effort, self.resolved_model)
        )

    def __repr__(self):
        return (
            f"AgentMode(agent={self.agent!r}, mode={self.mode!r}, "
            f"refreshed={self.refreshed}, model={self.model!r}, "
            f"effort={self.effort!r}, resolved_model={self.resolved_model!r})"
        )


def resolved_default_model_for_agent(agent: str) -> str | None:
    """Return the pinned default model for *agent*, or ``None``.

    >>> resolved_default_model_for_agent("claude")
    'claude-opus-4-7'
    >>> resolved_default_model_for_agent("codex")
    'gpt-5.5'
    >>> resolved_default_model_for_agent("hermes") is None
    True
    """
    from megaplan._pipeline.defaults import CLAUDE_DEFAULT_MODEL, CODEX_DEFAULT_MODEL

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
    "execution.max_tasks_per_batch": 5,
    "orchestration.max_critique_concurrency": 5,
    "orchestration.mode": "subagent",
}

_SETTABLE_BOOL = {
    "execution.auto_approve",
    "execution.strict_notes",
}

_SETTABLE_ENUM = {
    "execution.robustness": ROBUSTNESS_ACCEPTED,
}

_SETTABLE_NUMERIC = {
    "execution.worker_timeout_seconds",
    "execution.max_review_rework_cycles",
    "execution.max_robust_review_rework_cycles",
    "execution.max_execute_no_progress",
    "execution.max_tasks_per_batch",
    "orchestration.max_critique_concurrency",
}


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class CliError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        valid_next: list[str] | None = None,
        extra: dict[str, Any] | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.valid_next = valid_next or []
        self.extra = extra or {}
        self.exit_code = exit_code
