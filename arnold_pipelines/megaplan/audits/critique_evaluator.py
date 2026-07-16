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

#: Maximum number of bespoke "other" custom critique areas the evaluator may
#: add on top of the 9-lens catalog. These are additive — they do not
#: participate in the 9-lens coverage invariant.
MAX_OTHER_AREAS: Final[int] = 2


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

#: Map each premium roster model to the ``--vendor`` value that owns it. Models
#: not listed here (the DeepSeek tiers) are vendor-independent and appear in
#: every per-vendor roster view.
_PREMIUM_ROSTER_MODEL_VENDOR: Final[dict[str, str]] = {
    "claude-opus-4-7": "claude",
    "claude-sonnet-4-6": "claude",
    "gpt-5.5": "codex",
    "gpt-5.4": "codex",
}


def roster_for_vendor(vendor: str) -> tuple[_RosterEntry, ...]:
    """Return the roster entries visible under ``vendor``.

    Premium entries owned by the *other* premium vendor are dropped so the
    evaluator is only ever offered strong critics it can actually dispatch
    under the active ``--vendor``. DeepSeek tiers (vendor-independent) always
    appear. Unknown vendors fall back to the full roster.
    """
    if vendor not in ("claude", "codex"):
        return CRITIC_MODEL_ROSTER
    return tuple(
        entry
        for entry in CRITIC_MODEL_ROSTER
        if _PREMIUM_ROSTER_MODEL_VENDOR.get(entry.model, vendor) == vendor
    )


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
    "premium": "claude-opus-4-7",
}


def _resolve_canonical(model: str) -> str:
    """Resolve a model spec to its canonical roster key.

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
    if stripped in _ROSTER_BY_MODEL:
        return stripped

    # ── hermes provider specs ──────────────────────────────────────────
    if stripped.startswith("hermes:"):
        normalized = _normalize_hermes_spec(stripped)
    elif ":" in stripped:
        agent, rest = stripped.split(":", 1)
        agent = agent.lower()
        if agent in ("claude", "codex", "premium"):
            normalized = _normalize_premium_spec(agent, rest)
            # Resolve bare agent names (e.g. ``claude`` -> ``claude-opus-4-7``).
            # Symbolic ``premium`` normalizes to its effective vendor (claude
            # by default), so ``premium:low`` -> ``claude`` -> ``claude-opus-4-7``.
            if normalized in _AGENT_DEFAULT_MODEL:
                normalized = _AGENT_DEFAULT_MODEL[normalized]
        else:
            # Provider-prefixed spec without an explicit ``hermes:`` prefix
            # (e.g. ``deepseek:deepseek-v4-pro``, which is how a DeepSeek-only
            # profile's evaluator reports its own model, or
            # ``fireworks:accounts/.../deepseek-v4-pro``). The roster ranks by
            # model family, so extract the trailing model component the same
            # way hermes specs are normalized. An unknown model still raises
            # below when it is not found in the roster.
            normalized = _normalize_hermes_spec(stripped)
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

    if normalized not in _ROSTER_BY_MODEL:
        raise ValueError(
            f"Model {model!r} normalised to {normalized!r}, which is not in "
            f"CRITIC_MODEL_ROSTER. Known roster keys: "
            f"{sorted(_ROSTER_BY_MODEL.keys())}"
        )
    return normalized


def roster_rank(model: str) -> int:
    """Return the roster rank (1 = strongest) for *model*.

    Accepts every legitimate profile model string and normalises it to a
    roster key via :func:`_resolve_canonical`.

    Raises:
        ValueError: *model* does not normalise to a known roster entry.
    """
    return _ROSTER_BY_MODEL[_resolve_canonical(model)].rank


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
    from arnold_pipelines.megaplan.profiles import (
        DIRECT_DEEPSEEK_V4_FLASH_SPEC,
        DIRECT_DEEPSEEK_V4_PRO_SPEC,
    )
    from arnold_pipelines.megaplan.profiles import KNOWN_AGENTS
    from arnold_pipelines.megaplan.types import parse_agent_spec

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
    complexity: int
    complexity_justification: str
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
    payload: dict[str, Any], *, evaluator_model: str, vendor: str | None = None,
) -> list[str]:
    """Validate a critique evaluator payload with hard-reject discipline.

    A *consistent* duplicate selection — the same ``check_id`` listed more
    than once with an identical complexity assignment — is **deduped in place**
    (the first occurrence wins; later twins are dropped from ``payload``)
    and a human-readable warning is returned rather than triggering a full
    hard-reject. A *conflicting* duplicate remains a hard reject because the
    evaluator's intent for that lens is genuinely ambiguous.

    Genuine integrity violations — unknown ids, coverage gaps, overlap,
    unjustified skips, invalid complexity assignments — remain hard rejects.

    ``vendor`` is retained as a deprecated no-op compatibility parameter while
    live evaluator verdicts migrate from per-lens ``critic_model`` selections
    to complexity-only routing (now 1-10 scale for execute). The roster constants remain available for
    operator-pin paths elsewhere; this validator no longer performs live
    per-lens roster/vendor/strength checks.

    Returns:
        A list of human-readable warning strings (empty when the verdict was
        clean). Currently only consistent-duplicate dedupes are reported.

    Raises:
        ValueError: on any schema or invariant violation.
    """

    warnings: list[str] = []
    _ = evaluator_model, vendor

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
    from arnold_pipelines.megaplan.audits.robustness import CRITIQUE_CHECKS

    all_check_ids: set[str] = {check["id"] for check in CRITIQUE_CHECKS}

    # ── selections validation ──────────────────────────────────────────
    # First occurrence of each check_id wins; consistent duplicates are
    # dropped (and reported), conflicting duplicates hard-reject.
    selected_complexities: dict[str, tuple[int, str]] = {}
    deduped_selections: list[dict[str, Any]] = []
    # Bespoke "other" custom areas are ADDITIVE — they never enter
    # selected_ids and so never participate in the 9-lens coverage union.
    custom_selections: list[dict[str, Any]] = []
    custom_area_keys: set[str] = set()
    for idx, sel in enumerate(selections, start=1):
        if not isinstance(sel, dict):
            _reject(f"selection {idx} must be an object.")
        cid = sel.get("check_id")
        if not isinstance(cid, str) or not cid.strip():
            _reject(f"selection {idx} is missing a non-empty `check_id`.")
        if cid not in all_check_ids and cid != "other":
            _reject(
                f"selection {idx}: unknown check_id {cid!r}. "
                f"Known ids: {sorted(all_check_ids)}"
            )

        if "critic_model" in sel:
            _reject(
                f"selection {idx} ({cid}): live evaluator selections must not "
                "include `critic_model`; route by `complexity` instead."
            )
        complexity = sel.get("complexity")
        if (
            not isinstance(complexity, int)
            or isinstance(complexity, bool)
            or not 1 <= complexity <= 10
        ):
            _reject(
                f"selection {idx} ({cid}): must include an integer `complexity` "
                f"score in 1..10 (got {complexity!r})."
            )
        justification = sel.get("complexity_justification")
        if not isinstance(justification, str) or not justification.strip():
            _reject(
                f"selection {idx} ({cid}): missing non-empty "
                "`complexity_justification`."
            )
        if cid in {"correctness", "prerequisite_ordering"} and complexity < 4:
            warnings.append(
                f"selection {idx} ({cid}): {cid!r} complexity {complexity} "
                "was raised to the hard floor 4."
            )
            complexity = 4
            sel["complexity"] = complexity
        normalized_justification = justification.strip()

        # ── bespoke "other" custom area ──────────────────────────────────
        # An "other" selection is NOT a catalog lens: it carries its own
        # `area` name and its `why` doubles as the critic's probe. It is
        # additive — it must stay OUT of selected_models / selected_ids so
        # the coverage union (selected_ids | skipped_ids == all_check_ids)
        # keeps computing over the 9 catalog lenses only.
        if cid == "other":
            area = sel.get("area")
            if not isinstance(area, str) or not area.strip():
                _reject(
                    f'selection {idx}: an "other" selection needs a '
                    f"non-empty `area` naming the custom critique area"
                )
            why = sel.get("why")
            if not isinstance(why, str) or not why.strip():
                _reject(
                    f'selection {idx} ("other" / {area!r}): an "other" '
                    f"selection needs a non-empty `why` (it is the probe)."
                )
            area_key = area.strip().lower()
            if area_key in custom_area_keys:
                # Consistent duplicate custom area: dedupe + warn, mirroring
                # the catalog consistent-duplicate policy.
                warnings.append(
                    f'selection {idx}: duplicate "other" area {area!r} — '
                    f"deduped (kept first occurrence)."
                )
                continue
            custom_area_keys.add(area_key)
            custom_selections.append(sel)
            deduped_selections.append(sel)
            if len(custom_selections) > MAX_OTHER_AREAS:
                _reject(
                    f"at most {MAX_OTHER_AREAS} 'other' custom areas allowed"
                )
            continue

        if cid in selected_complexities:
            prior_complexity = selected_complexities[cid]
            if prior_complexity == (complexity, normalized_justification):
                # Consistent duplicate: the model assigned the same lens to the
                # same complexity twice. Dedupe (keep the first) and warn.
                warnings.append(
                    f"selection {idx}: duplicate check_id {cid!r} with the same "
                    f"complexity {complexity!r} — deduped (kept first "
                    f"occurrence)."
                )
                continue
            # Conflicting duplicate: same lens, different critic. Intent is
            # ambiguous; keep this a hard reject.
            _reject(
                f"selection {idx}: conflicting duplicate check_id {cid!r} — "
                f"already assigned to {prior_complexity!r}, now "
                f"{(complexity, normalized_justification)!r}. A lens may "
                "appear at most once; resolve the conflicting complexity "
                "assignment."
            )
        selected_complexities[cid] = (complexity, normalized_justification)
        deduped_selections.append(sel)

        # why is not required per schema but we note it

    selected_ids: set[str] = set(selected_complexities)
    # Persist the deduped selection list so the caller sees each lens once.
    if len(deduped_selections) != len(selections):
        payload["selections"] = deduped_selections

    # ── skipped validation ──────────────────────────────────────────────
    # A skip carries no complexity payload, so any repeat of a skipped check_id is a
    # consistent duplicate (same lens, same intent: skip it). Dedupe + warn
    # rather than hard-reject, mirroring the selections policy.
    skipped_ids: set[str] = set()
    deduped_skipped: list[dict[str, Any]] = []
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

        why = sk.get("why")
        if not isinstance(why, str) or not why.strip():
            warnings.append(
                f"skip entry {idx} ({cid}): `why` was empty; coercing to a "
                f"placeholder justification."
            )
            sk["why"] = "(no justification provided by evaluator)"

        if cid in skipped_ids:
            warnings.append(
                f"skip entry {idx}: duplicate check_id {cid!r} — deduped "
                f"(kept first occurrence)."
            )
            continue
        skipped_ids.add(cid)
        deduped_skipped.append(sk)

    if len(deduped_skipped) != len(skipped) or any(sk.get("why") == "(no justification provided by evaluator)" for sk in deduped_skipped):
        payload["skipped"] = deduped_skipped

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
    # An all-skip-of-9 verdict is allowed only when it carries ≥1 bespoke
    # "other" custom area (which is additive and never enters selected_ids).
    if len(selected_ids) == 0 and not custom_selections:
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

    return warnings


# ---------------------------------------------------------------------------
# Wiring probes — used by init-time startup validation and `megaplan doctor
# --adaptive-critique`. Each probe returns a 3-tuple
# (label, passed, detail) so callers can render either a green/red status
# line (doctor) or assemble a structured AdaptiveCritiqueMisconfiguredError
# (init). The probes are deliberately offline + read-only.
# ---------------------------------------------------------------------------


def probe_adaptive_critique_wiring() -> list[tuple[str, bool, str]]:
    """Probe every load-bearing piece of the adaptive critique path."""
    results: list[tuple[str, bool, str]] = []

    try:
        from arnold_pipelines.megaplan.workers._impl import STEP_SCHEMA_FILENAMES
    except ImportError as exc:  # pragma: no cover - defensive
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
            "missing key - adaptive critique will KeyError at dispatch",
        ))
        return results
    schema_filename = STEP_SCHEMA_FILENAMES["critique_evaluator"]
    results.append((
        "critique_evaluator registered in STEP_SCHEMA_FILENAMES",
        True,
        f"-> {schema_filename}",
    ))

    try:
        from arnold_pipelines.megaplan.schemas import SCHEMAS
    except ImportError as exc:  # pragma: no cover - defensive
        results.append(("SCHEMAS importable", False, f"ImportError: {exc}"))
        return results

    if schema_filename not in SCHEMAS:
        results.append((
            f"{schema_filename} registered in SCHEMAS",
            False,
            "schema is dispatched-to but not registered",
        ))
    else:
        results.append((f"{schema_filename} registered in SCHEMAS", True, ""))

    try:
        from arnold_pipelines.megaplan.prompts.critique_evaluator import _critique_evaluator_prompt
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

    try:
        from arnold_pipelines.megaplan.workers._impl import _STEP_REQUIRED_KEYS
        required = set(_STEP_REQUIRED_KEYS.get("critique_evaluator", set()))
    except ImportError as exc:  # pragma: no cover - defensive
        results.append(("_STEP_REQUIRED_KEYS importable", False, f"ImportError: {exc}"))
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
    """Raise if any static adaptive-critique wiring probe fails."""
    from arnold_pipelines.megaplan.types import AdaptiveCritiqueMisconfiguredError

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
            missing=[label for label, _detail in failures],
        )
