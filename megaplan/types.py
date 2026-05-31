"""Type definitions, constants, and exceptions for megaplan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, NotRequired, TypedDict


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
STATE_AWAITING_HUMAN_VERIFY = "awaiting_human_verify"
STATE_AWAITING_HUMAN = STATE_AWAITING_HUMAN_VERIFY
STATE_TIEBREAKER_PENDING = "tiebreaker_pending"
STATE_TIEBREAKER_READY = "tiebreaker_ready"
PlanCurrentState = Literal[
    "initialized",
    "prepped",
    "planned",
    "critiqued",
    "gated",
    "finalized",
    "executed",
    "reviewed",
    "done",
    "aborted",
    "failed",
    "blocked",
    "paused",
    "cancelled",
    "awaiting_pr_merge",
    "awaiting_human_verify",
    "tiebreaker_pending",
    "tiebreaker_ready",
]
CANONICAL_PLAN_STATES: frozenset[str] = frozenset(
    {
        STATE_INITIALIZED,
        STATE_PREPPED,
        STATE_PLANNED,
        STATE_CRITIQUED,
        STATE_GATED,
        STATE_FINALIZED,
        STATE_EXECUTED,
        STATE_REVIEWED,
        STATE_DONE,
        STATE_ABORTED,
        STATE_FAILED,
        STATE_BLOCKED,
        STATE_PAUSED,
        STATE_CANCELLED,
        STATE_AWAITING_PR_MERGE,
        STATE_AWAITING_HUMAN_VERIFY,
        STATE_TIEBREAKER_PENDING,
        STATE_TIEBREAKER_READY,
    }
)
TERMINAL_STATES = {STATE_DONE, STATE_ABORTED, STATE_FAILED, STATE_BLOCKED, STATE_CANCELLED}
AUTOMATION_TERMINAL_STATES = TERMINAL_STATES | {
    STATE_PAUSED,
    STATE_AWAITING_HUMAN_VERIFY,
    STATE_TIEBREAKER_PENDING,
    STATE_TIEBREAKER_READY,
}


def validate_plan_current_state(value: Any) -> str:
    """Return a canonical plan state or raise for invalid persisted state."""

    if value not in CANONICAL_PLAN_STATES:
        raise ValueError(f"invalid current_state {value!r}")
    return str(value)


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
    current_state: PlanCurrentState
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
    "critique_evaluator": "claude",
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
# Canonical robustness names — match docs/megaplan-prep.md.
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

# Canonical per-vendor valid effort sets — the SINGLE source of truth for
# what an effort token may be in an agent spec. These are the *spec-layer*
# effort tokens (the thinking-depth ladder applied by --depth / --phase-model),
# NOT the narrower codex-CLI reasoning-effort set in
# megaplan.workers._impl (_VALID_CODEX_EFFORTS), which is a downstream concern
# where xhigh/max get clamped before the codex binary is invoked.
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


def _is_claude_model_name(name: str) -> bool:
    """True if *name* names a Claude model.

    Accepts the full pins used across profiles/tier_models/tests
    (``claude-sonnet-4-6``, ``claude-opus-4-7``), the shorthand model
    pins (``sonnet-4.6``, ``sonnet``, ``opus``), and any
    ``anthropic/claude-*`` / ``claude/`` form.
    """
    lowered = name.lower()
    return (
        "claude" in lowered
        or "sonnet" in lowered
        or "opus" in lowered
        or "haiku" in lowered
    )


def _is_codex_model_name(name: str) -> bool:
    """True if *name* names a Codex / GPT-5.x model.

    Accepts ``gpt-5.5``, ``gpt-5.4``, ``gpt-5.3-codex``, ``gpt-5.1-codex-max``,
    and ``openai/gpt-5*`` forms.
    """
    lowered = name.lower()
    return lowered.startswith("gpt-5") or "/gpt-5" in lowered or "codex" in lowered


_PREMIUM_MODEL_PREDICATES = {
    "claude": _is_claude_model_name,
    "codex": _is_codex_model_name,
}


def _validate_premium_spec(agent: str, model: str | None, effort: str | None, spec: str) -> None:
    """Reject semantically-malformed premium (claude/codex) specs.

    The grammar is syntactically closed but historically semantically open:
    ANY token was accepted in the model/effort slot. This is the single
    chokepoint that closes it. A premium spec must be one of:

    * bare agent (``codex``)
    * ``agent:effort`` (effort in that agent's valid set)
    * ``agent:model`` (model in that agent's family)
    * ``agent:model:effort`` (both valid)

    A token that is NEITHER a valid effort NOR a recognised model for that
    agent raises ``CliError`` naming the offending spec. This is what turns
    ``codex:claude:sonnet`` (model='claude', effort='sonnet') from a silent
    mis-parse into a loud failure.
    """
    valid_efforts = _VALID_PREMIUM_EFFORTS[agent]
    model_ok = _PREMIUM_MODEL_PREDICATES[agent]

    if effort is not None and effort not in valid_efforts:
        raise CliError(
            "invalid_agent_spec",
            f"Invalid {agent} agent spec {spec!r}: effort token {effort!r} is not a "
            f"valid {agent} effort ({', '.join(sorted(valid_efforts))}) "
            f"and the spec is not a recognised {agent} model.",
        )
    if model is not None and not model_ok(model):
        raise CliError(
            "invalid_agent_spec",
            f"Invalid {agent} agent spec {spec!r}: {model!r} is neither a valid "
            f"{agent} effort ({', '.join(sorted(valid_efforts))}) nor a recognised "
            f"{agent} model. A {agent} spec must be a bare agent, "
            f"{agent}:<effort>, or {agent}:<model>[:<effort>].",
        )


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
        _validate_premium_spec(agent, None, rest, spec)
        return AgentSpec(agent=agent, effort=rest)

    # Everything after the first colon could be <model> or <model>:<effort>.
    if ":" in rest:
        model, effort = rest.split(":", 1)
        # Effort may be empty string if spec ends with colon; normalize to None.
        if not effort:
            effort = None
        _validate_premium_spec(agent, model, effort, spec)
        return AgentSpec(agent=agent, model=model, effort=effort)

    # Single token that is not a reserved effort token → model-only.
    _validate_premium_spec(agent, rest, None, spec)
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
    # Opt-in per-worker filesystem-state isolation. A list of env var names;
    # for EACH worker spawn megaplan mints a fresh unique temp dir per listed
    # var (under the OS temp dir) and exports VAR=<that tmpdir> into the
    # worker subprocess env, so concurrent workers don't share per-user state
    # behind those vars. Default [] = no isolation (env built as before). See
    # _apply_worker_state_isolation in megaplan/workers/_impl.py.
    "execution.worker_isolated_env_vars": [],
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
    "execution.robustness": ROBUSTNESS_ACCEPTED,
    "execution.critic_model": CRITIC_MODEL_CHOICES,
    "execution.completion_contract_mode": ("off", "shadow", "warn", "enforce"),
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
from megaplan.runtime.process import OrphanDetectedError  # noqa: E402, F401
