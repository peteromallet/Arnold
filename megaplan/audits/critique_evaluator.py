"""Critique evaluator — model roster, ranking, verdict schema, and validation.

The evaluator selects a critic model for a run and must guarantee
*rader ≥ dispatchee*: the chosen critic ranks at least as high as the
strongest model that could be dispatched for execution.  The roster is
the single source of truth for model strength ordering.

v1 roster: ranked list of {model, rank, cost_hint}.  Rank 1 = strongest.
claude (opus-4-7) and codex (gpt-5.5) are co-ranked at rank 1 (SD2).
"""

from __future__ import annotations

from typing import Any, Final, TypedDict

# ---------------------------------------------------------------------------
# Roster — ordered by rank (strongest first).  Co-ranked entries share a rank.
# ---------------------------------------------------------------------------

_KNOWN_EFFORT_TOKENS: Final[frozenset[str]] = frozenset({"low", "medium", "high"})


class _RosterEntry:
    __slots__ = ("model", "rank", "cost_hint")

    def __init__(self, model: str, rank: int, cost_hint: str) -> None:
        self.model = model
        self.rank = rank
        self.cost_hint = cost_hint


CRITIC_MODEL_ROSTER: Final[tuple[_RosterEntry, ...]] = (
    _RosterEntry("claude-opus-4-7", 1, "$$$$"),
    _RosterEntry("gpt-5.5", 1, "$$$$"),
    _RosterEntry("claude-sonnet-4-6", 2, "$$$"),
    _RosterEntry("deepseek-v4-pro", 3, "$$"),
    _RosterEntry("deepseek-v4-flash", 4, "$"),
)

# ---------------------------------------------------------------------------
# Internal lookup built once at import time.
# ---------------------------------------------------------------------------

_ROSTER_BY_MODEL: Final[dict[str, _RosterEntry]] = {
    entry.model: entry for entry in CRITIC_MODEL_ROSTER
}


def _normalize_hermes_spec(spec: str) -> str:
    """Extract the model name from a hermes provider spec.

    ``hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro`` → ``deepseek-v4-pro``
    ``hermes:deepseek:deepseek-v4-flash``              → ``deepseek-v4-flash``
    ``hermes:glm-5.1``                                 → ``glm-5.1``

    The last ``/``-delimited segment wins; if there is no ``/`` the last
    ``:``-delimited segment is used.
    """
    rest = spec.split(":", 1)[1] if ":" in spec else spec
    if "/" in rest:
        return rest.rsplit("/", 1)[-1]
    return rest.rsplit(":", 1)[-1]


def _normalize_premium_spec(agent: str, rest: str) -> str:
    """Normalize a ``claude:…`` or ``codex:…`` spec.

    * Effort-only suffixes (``low``, ``medium``, ``high``) are stripped so
      the bare agent name resolves to its default model.
    * Fully-qualified model names (e.g. ``claude:claude-opus-4-7``) are
      returned directly.
    """
    if rest.lower() in _KNOWN_EFFORT_TOKENS:
        # ``claude:low`` → ``claude`` (default model), etc.
        return agent
    # ``claude:claude-opus-4-7`` → ``claude-opus-4-7``
    return rest


#: Mapping from bare agent name to the roster key for that agent's default model.
_AGENT_DEFAULT_MODEL: Final[dict[str, str]] = {
    "claude": "claude-opus-4-7",
    "codex": "gpt-5.5",
}

#: Provider prefixes that may appear before a model name in a spec
#: (e.g. ``deepseek:deepseek-v4-pro``).  These are not agents
#: themselves; the part after the colon is the model name.
_KNOWN_NATIVE_PROVIDERS: Final[frozenset[str]] = frozenset({
    "deepseek", "fireworks", "zhipu", "google", "minimax",
})


def roster_rank(model: str) -> int:
    """Return the roster rank (1 = strongest) for *model*.

    Accepts every legitimate profile model string and normalises it to a
    roster key:

    * Thinking-mode / effort suffixes are stripped: ``claude:low`` → ``claude``.
    * Bare family names resolve to the default model for that agent:
      ``claude`` → ``claude-opus-4-7``, ``codex`` → ``gpt-5.5``.
    * Fully-qualified premium specs pass through the model component:
      ``claude:claude-opus-4-7`` → ``claude-opus-4-7``.
    * Hermes provider specs extract the trailing model name:
      ``hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro`` → ``deepseek-v4-pro``,
      ``hermes:deepseek:deepseek-v4-flash`` → ``deepseek-v4-flash``.

    Raises:
        ValueError: *model* does not normalise to a known roster entry.
    """
    if not model or not isinstance(model, str):
        raise ValueError(f"Invalid model spec: {model!r}")

    stripped = model.strip()
    if not stripped:
        raise ValueError(f"Empty model spec: {model!r}")

    # ── already a roster key ───────────────────────────────────────────
    # The roster's own model names (e.g. ``claude-opus-4-7``, ``gpt-5.5``)
    # are passed back as ``evaluator_model`` by the call site, so accept
    # them directly before attempting agent/provider normalization.
    direct = _ROSTER_BY_MODEL.get(stripped)
    if direct is not None:
        return direct.rank

    # ── hermes provider specs ──────────────────────────────────────────
    if stripped.startswith("hermes:"):
        normalized = _normalize_hermes_spec(stripped)
    elif ":" in stripped:
        agent, rest = stripped.split(":", 1)
        agent = agent.lower()
        if agent in ("claude", "codex"):
            normalized = _normalize_premium_spec(agent, rest)
            # Resolve bare agent names (e.g. ``claude`` → ``claude-opus-4-7``).
            if normalized in _AGENT_DEFAULT_MODEL:
                normalized = _AGENT_DEFAULT_MODEL[normalized]
        elif agent in _KNOWN_NATIVE_PROVIDERS:
            # ``deepseek:deepseek-v4-pro`` → ``deepseek-v4-pro``, etc.
            # The rest after the provider prefix IS the model name.
            normalized = rest
        else:
            raise ValueError(
                f"Unknown agent {agent!r} in model spec {model!r}"
            )
    else:
        # Bare agent name (e.g. ``claude``, ``codex``).
        agent = stripped.lower()
        if agent in _AGENT_DEFAULT_MODEL:
            normalized = _AGENT_DEFAULT_MODEL[agent]
        else:
            raise ValueError(
                f"Unknown model spec {model!r} — not a recognised agent or "
                f"provider spec"
            )

    entry = _ROSTER_BY_MODEL.get(normalized)
    if entry is None:
        raise ValueError(
            f"Model {model!r} normalised to {normalized!r}, which is not in "
            f"CRITIC_MODEL_ROSTER. Known roster keys: "
            f"{sorted(_ROSTER_BY_MODEL.keys())}"
        )
    return entry.rank


def roster_dispatch_spec(model: str) -> str:
    """Map a bare roster model name to a fully-resolved agent spec string.

    The roster stores *ranking tokens* (``deepseek-v4-pro``), not dispatchable
    specs. Splicing such a token onto an inherited agent (as the critique
    handler used to do) produces incoherent routes — a Claude/Codex worker
    handed a DeepSeek model name — and even in the hermes case a bare
    ``deepseek-v4-pro`` carries no provider, so dispatch falls through to
    OpenRouter instead of DeepSeek's direct API. This returns the complete
    ``<agent>[:<provider>]:<model>`` spec so a farmed-out critic routes to the
    right vendor. DeepSeek critics go to DeepSeek's **direct** API.

    Raises:
        ValueError: *model* is not a known roster entry.
    """
    from megaplan.profiles import (
        DIRECT_DEEPSEEK_V4_FLASH_SPEC,
        DIRECT_DEEPSEEK_V4_PRO_SPEC,
    )
    from megaplan.types import KNOWN_AGENTS, parse_agent_spec

    mapping = {
        "claude-opus-4-7": "claude:claude-opus-4-7",
        "gpt-5.5": "codex:gpt-5.5",
        "claude-sonnet-4-6": "claude:claude-sonnet-4-6",
        "deepseek-v4-pro": DIRECT_DEEPSEEK_V4_PRO_SPEC,
        "deepseek-v4-flash": DIRECT_DEEPSEEK_V4_FLASH_SPEC,
    }
    if model in mapping:
        return mapping[model]

    # The evaluator may also emit an already-dispatchable spec — a bare agent
    # name ("claude"/"codex"), a premium spec ("claude:claude-sonnet-4-6"), or
    # a hermes provider spec. Pass those through untouched; only the bare
    # roster tokens above (which are not valid agent specs on their own) need
    # rewriting.
    if parse_agent_spec(model).agent in KNOWN_AGENTS:
        return model

    raise ValueError(
        f"No dispatch spec for critic model {model!r}. Known roster keys: "
        f"{sorted(mapping.keys())}; or a spec for one of {KNOWN_AGENTS}."
    )


# ---------------------------------------------------------------------------
# Verdict schema
# ---------------------------------------------------------------------------


class CritiqueSelection(TypedDict):
    check_id: str
    critic_model: str
    why: str


class CritiqueSkip(TypedDict):
    check_id: str
    why: str


class FlagVerification(TypedDict):
    """A per-flag verification entry produced during the verify step."""

    flag_id: str
    lens: str
    outcome: str  # "verified" | "open" | "accepted_tradeoff"
    rationale: str


class EvaluatorVerdict(TypedDict, total=False):
    """Schema for the critique evaluator's output payload."""

    selections: list[CritiqueSelection]
    skipped: list[CritiqueSkip]
    evaluator_model: str
    flag_verifications: list[FlagVerification]


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def validate_evaluator_verdict(
    payload: dict[str, Any], *, evaluator_model: str
) -> None:
    """Validate a critique evaluator payload with hard-reject discipline.

    Raises:
        ValueError: on any schema or invariant violation.
    """

    def _reject(message: str) -> None:
        raise ValueError(f"critique_evaluator verdict rejected: {message}")

    # ── top-level shape ─────────────────────────────────────────────────
    selections: list[dict[str, Any]] = payload.get("selections", [])
    skipped: list[dict[str, Any]] = payload.get("skipped", [])

    if not isinstance(selections, list):
        _reject("`selections` must be a list.")
    if not isinstance(skipped, list):
        _reject("`skipped` must be a list.")

    # ── collect known check ids ─────────────────────────────────────────
    # Late import to avoid circular dependency at module scope.
    from megaplan.audits.robustness import CRITIQUE_CHECKS

    all_check_ids: set[str] = {check["id"] for check in CRITIQUE_CHECKS}

    # ── selections validation ──────────────────────────────────────────
    selected_ids: set[str] = set()
    for idx, sel in enumerate(selections, start=1):
        if not isinstance(sel, dict):
            _reject(f"selection {idx} must be an object.")
        cid = sel.get("check_id")
        if not isinstance(cid, str) or not cid.strip():
            _reject(f"selection {idx} is missing a non-empty `check_id`.")
        if cid not in all_check_ids:
            _reject(
                f"selection {idx}: unknown check_id {cid!r}. "
                f"Known ids: {sorted(all_check_ids)}"
            )
        if cid in selected_ids:
            _reject(f"selection {idx}: duplicate check_id {cid!r}.")
        selected_ids.add(cid)

        critic_model = sel.get("critic_model")
        if not isinstance(critic_model, str) or not critic_model.strip():
            _reject(f"selection {idx} ({cid}): missing non-empty `critic_model`.")

        # critic must be in roster
        try:
            critic_rank = roster_rank(critic_model)
        except ValueError as exc:
            _reject(
                f"selection {idx} ({cid}): critic_model {critic_model!r} "
                f"not in CRITIC_MODEL_ROSTER: {exc}"
            )

        # critic must be no stronger than evaluator (rank >= evaluator rank)
        try:
            evaluator_rank = roster_rank(evaluator_model)
        except ValueError as exc:
            _reject(f"evaluator_model {evaluator_model!r} not in roster: {exc}")

        if critic_rank < evaluator_rank:
            _reject(
                f"selection {idx} ({cid}): critic_model {critic_model!r} "
                f"(rank {critic_rank}) is stronger than evaluator "
                f"{evaluator_model!r} (rank {evaluator_rank}). "
                f"Critic must be no stronger than evaluator "
                f"(roster_rank(critic) >= roster_rank(evaluator))."
            )

        # why is not required per schema but we note it

    # ── skipped validation ──────────────────────────────────────────────
    skipped_ids: set[str] = set()
    for idx, sk in enumerate(skipped, start=1):
        if not isinstance(sk, dict):
            _reject(f"skip entry {idx} must be an object.")
        cid = sk.get("check_id")
        if not isinstance(cid, str) or not cid.strip():
            _reject(f"skip entry {idx} is missing a non-empty `check_id`.")
        if cid not in all_check_ids:
            _reject(
                f"skip entry {idx}: unknown check_id {cid!r}. "
                f"Known ids: {sorted(all_check_ids)}"
            )
        if cid in skipped_ids:
            _reject(f"skip entry {idx}: duplicate check_id {cid!r}.")
        skipped_ids.add(cid)

        why = sk.get("why")
        if not isinstance(why, str) or not why.strip():
            _reject(
                f"skip entry {idx} ({cid}): every skip must have a "
                f"non-empty `why` justification."
            )

    # ── coverage: union must be all check ids, no overlap ───────────────
    if selected_ids & skipped_ids:
        overlap = selected_ids & skipped_ids
        _reject(
            f"Overlap between selections and skipped: {sorted(overlap)}. "
            f"Every lens must be either selected or skipped, not both."
        )

    union = selected_ids | skipped_ids
    if union != all_check_ids:
        missing = all_check_ids - union
        _reject(
            f"Not all lenses covered. Missing: {sorted(missing)}. "
            f"The union of selections + skipped must equal all "
            f"{len(all_check_ids)} lens ids."
        )

    # ── at least one selection ──────────────────────────────────────────
    if len(selections) == 0:
        _reject(
            "At least one lens must be selected (len(selections) >= 1). "
            "An all-skip verdict is rejected."
        )

    # ── flag_verifications (optional) ───────────────────────────────────
    _ALLOWED_VERIFY_OUTCOMES: Final[frozenset[str]] = frozenset(
        {"verified", "open", "accepted_tradeoff"}
    )
    flag_verifications: list[dict[str, Any]] = payload.get("flag_verifications", [])
    if flag_verifications:
        if not isinstance(flag_verifications, list):
            _reject("`flag_verifications` must be a list when present.")
        seen_fv: set[str] = set()
        for idx, fv in enumerate(flag_verifications, start=1):
            if not isinstance(fv, dict):
                _reject(f"flag_verification {idx} must be an object.")
            fid = fv.get("flag_id")
            if not isinstance(fid, str) or not fid.strip():
                _reject(
                    f"flag_verification {idx} is missing a non-empty `flag_id`."
                )
            lens = fv.get("lens")
            if not isinstance(lens, str) or not lens.strip():
                _reject(
                    f"flag_verification {idx} ({fid!r}): "
                    f"missing non-empty `lens`."
                )
            if lens not in all_check_ids:
                _reject(
                    f"flag_verification {idx} ({fid!r}): unknown lens {lens!r}. "
                    f"Known ids: {sorted(all_check_ids)}"
                )
            outcome = fv.get("outcome")
            if not isinstance(outcome, str) or outcome not in _ALLOWED_VERIFY_OUTCOMES:
                _reject(
                    f"flag_verification {idx} ({fid!r}): `outcome` must be one of "
                    f"{sorted(_ALLOWED_VERIFY_OUTCOMES)}, got {outcome!r}."
                )
            rationale = fv.get("rationale")
            if not isinstance(rationale, str) or not rationale.strip():
                _reject(
                    f"flag_verification {idx} ({fid!r}): "
                    f"missing non-empty `rationale`."
                )
            # duplicate flag_id within the same payload
            if fid in seen_fv:
                _reject(
                    f"flag_verification {idx}: duplicate flag_id {fid!r}."
                )
            seen_fv.add(fid)


# ---------------------------------------------------------------------------
# Wiring probes — used by init-time startup validation and `megaplan doctor
# --adaptive-critique`. Each probe returns a 3-tuple
# (label, passed, detail) so callers can render either a green/red status
# line (doctor) or assemble a structured AdaptiveCritiqueMisconfiguredError
# (init). The probes are deliberately offline + read-only.
# ---------------------------------------------------------------------------


def probe_adaptive_critique_wiring() -> list[tuple[str, bool, str]]:
    """Probe every load-bearing piece of the adaptive critique path.

    Returns a list of ``(label, passed, detail)`` tuples. ``passed`` is the
    only authoritative field; ``detail`` is for human surface and may be
    empty on success. A failing probe means adaptive critique would
    KeyError or otherwise fall back at runtime — the exact bug class the
    layered defense is built to prevent.

    Probes:

    1. ``"critique_evaluator"`` is registered in ``STEP_SCHEMA_FILENAMES``.
    2. The mapped schema filename is in the ``SCHEMAS`` dict.
    3. The ``critique_evaluator`` prompt template loads (and is callable).
    4. ``_STEP_REQUIRED_KEYS`` derives sensible keys for the step (the
       required-keys table is built from the schema; a missing schema
       silently produces an empty required-keys set).
    """
    results: list[tuple[str, bool, str]] = []

    # Probe 1: step → schema filename dispatch
    try:
        from megaplan.workers._impl import STEP_SCHEMA_FILENAMES
    except ImportError as exc:  # pragma: no cover — defensive
        results.append((
            "STEP_SCHEMA_FILENAMES importable",
            False,
            f"ImportError: {exc}",
        ))
        return results

    if "critique_evaluator" not in STEP_SCHEMA_FILENAMES:
        results.append((
            "critique_evaluator registered in STEP_SCHEMA_FILENAMES",
            False,
            "missing key — adaptive critique will KeyError at dispatch and "
            "fall back to static lenses",
        ))
        return results
    schema_filename = STEP_SCHEMA_FILENAMES["critique_evaluator"]
    results.append((
        "critique_evaluator registered in STEP_SCHEMA_FILENAMES",
        True,
        f"→ {schema_filename}",
    ))

    # Probe 2: schema filename → SCHEMAS dict entry
    try:
        from megaplan.schemas import SCHEMAS
    except ImportError as exc:  # pragma: no cover — defensive
        results.append((
            "SCHEMAS importable",
            False,
            f"ImportError: {exc}",
        ))
        return results

    if schema_filename not in SCHEMAS:
        results.append((
            f"{schema_filename} registered in SCHEMAS",
            False,
            "schema is dispatched-to but not registered; "
            "ensure_runtime_layout would not render it to disk",
        ))
    else:
        results.append((
            f"{schema_filename} registered in SCHEMAS",
            True,
            "",
        ))

    # Probe 3: prompt template
    try:
        from megaplan.prompts import create_prompt  # type: ignore
        from megaplan.prompts.critique_evaluator import _critique_evaluator_prompt
    except ImportError as exc:
        results.append((
            "critique_evaluator prompt template importable",
            False,
            f"ImportError: {exc}",
        ))
        return results
    results.append((
        "critique_evaluator prompt template importable",
        bool(callable(_critique_evaluator_prompt)),
        "",
    ))

    # Probe 4: required-keys table populated
    try:
        from megaplan.workers._impl import _STEP_REQUIRED_KEYS
        required = set(_STEP_REQUIRED_KEYS.get("critique_evaluator", set()))
    except ImportError as exc:  # pragma: no cover — defensive
        results.append((
            "_STEP_REQUIRED_KEYS importable",
            False,
            f"ImportError: {exc}",
        ))
        return results
    expected = {"selections", "skipped", "evaluator_model"}
    missing = expected - required
    results.append((
        "_STEP_REQUIRED_KEYS covers selections/skipped/evaluator_model",
        not missing,
        "" if not missing else f"missing: {sorted(missing)}",
    ))

    return results


def assert_adaptive_critique_wired() -> None:
    """Run :func:`probe_adaptive_critique_wiring` and raise
    :class:`AdaptiveCritiqueMisconfiguredError` if any probe fails.

    Called from ``handlers/init.py`` after ``adaptive_critique`` resolves
    True so misconfigurations fail at init, not after planning cost.
    """
    from megaplan.types import AdaptiveCritiqueMisconfiguredError

    results = probe_adaptive_critique_wiring()
    failures = [(label, detail) for label, passed, detail in results if not passed]
    if failures:
        lines = ["adaptive critique is misconfigured:"]
        for label, detail in failures:
            lines.append(f"  - {label}: {detail}")
        lines.append(
            "Run `megaplan doctor --adaptive-critique` for a full status, "
            "or set `[execution] adaptive_critique = false` to disable."
        )
        raise AdaptiveCritiqueMisconfiguredError(
            "\n".join(lines),
            missing=[label for label, _ in failures],
        )
