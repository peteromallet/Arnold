"""North Star action contract and strict severity normalization.

This module owns the *single* wire/contract shape for North Star actions and
their addressed counterparts, plus the strict normalization every later hook
(gate carry, revise addressing, finalize/review closeout blocking) must route
through.

Design invariants (settled decisions):

* **Schema-sourced blocking severity for dangerous categories.** A small,
  enumerated set of concern categories is *dangerous*: any action in one of
  them is blocking by schema rule regardless of what the gate/review worker or
  reviewer labels it. Its normalized ``severity`` is ``"blocking"`` and its
  ``severity_source`` is ``"schema"``. This is the contract-level guarantee the
  closeout blockers rely on — it cannot be downgraded by producer judgement.
* **Strict normalization (fail-loud).** Malformed actions are never silently
  dropped: a blocking action that cannot be normalized (missing id / concern /
  action_type / evidence, unknown category or action type) raises
  :class:`NorthStarActionValidationError` at normalization time. This closes
  the producer-is-graceful / consumer-is-absolute mismatch flagged in
  prerequisite-ordering review: by the time actions reach carry/closeout they
  are well-formed, so the absolute checks see a complete picture.

The shapes are intentionally narrow: they carry identity, the actionable
concern, the category/type that drives enforcement, normalized severity with
its provenance, supporting evidence, and optional concrete plan references.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence, TypedDict

__all__ = [
    "NorthStarAction",
    "NorthStarActionAddressed",
    "NORTH_STAR_ACTION_CATEGORIES",
    "NORTH_STAR_DANGEROUS_CATEGORIES",
    "NORTH_STAR_ACTION_TYPES",
    "NORTH_STAR_SEVERITIES",
    "NORTH_STAR_SEVERITY_SOURCES",
    "NORTH_STAR_ACTION_SCHEMA",
    "NORTH_STAR_ACTION_ADDRESSED_SCHEMA",
    "SEVERITY_BLOCKING",
    "SEVERITY_ADVISORY",
    "SEVERITY_SOURCE_SCHEMA",
    "SEVERITY_SOURCE_WORKER",
    "SEVERITY_SOURCE_REVIEWER",
    "SEVERITY_SOURCE_EXPLICIT",
    "NorthStarActionValidationError",
    "is_blocking_category",
    "is_blocking_action",
    "normalize_north_star_action",
    "normalize_north_star_actions",
    "blocking_north_star_actions",
    "normalize_north_star_action_addressed",
    "normalize_north_star_actions_addressed",
]

# --------------------------------------------------------------------------- #
# Severity vocabulary
# --------------------------------------------------------------------------- #

SEVERITY_BLOCKING: str = "blocking"
SEVERITY_ADVISORY: str = "advisory"
NORTH_STAR_SEVERITIES: tuple[str, ...] = (SEVERITY_BLOCKING, SEVERITY_ADVISORY)

# Provenance of a severity assignment. ``schema`` wins for dangerous categories
# and is authoritative; the others record an explicit producer judgement for
# non-dangerous actions that were marked blocking.
SEVERITY_SOURCE_SCHEMA: str = "schema"
SEVERITY_SOURCE_WORKER: str = "worker"
SEVERITY_SOURCE_REVIEWER: str = "reviewer"
SEVERITY_SOURCE_EXPLICIT: str = "explicit"
NORTH_STAR_SEVERITY_SOURCES: tuple[str, ...] = (
    SEVERITY_SOURCE_SCHEMA,
    SEVERITY_SOURCE_WORKER,
    SEVERITY_SOURCE_REVIEWER,
    SEVERITY_SOURCE_EXPLICIT,
)

# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #

# Dangerous categories are blocking by schema rule (see module docstring). These
# map 1:1 to the brief's enumerated set: route authority, baselines,
# row/carrier exemptions, target narrowing, generated conformance authority,
# and live-plan topology/resume risk.
NORTH_STAR_DANGEROUS_CATEGORIES: frozenset[str] = frozenset(
    {
        "route_authority",
        "baselines",
        "row_carrier_exemptions",
        "target_narrowing",
        "generated_conformance_authority",
        "live_plan_topology_resume_risk",
    }
)

# Advisory-capable concern areas that an action *may* belong to without being
# schema-forced to blocking. They are still blocking if a producer explicitly
# labels them so; only the dangerous set is schema-authoritative for blocking.
_ADVISORY_CATEGORIES: tuple[str, ...] = (
    "correctness",
    "completeness",
    "scope",
    "verification",
    "conventions",
    "other",
)

# Full ordered enum of valid categories (dangerous first, then advisory).
NORTH_STAR_ACTION_CATEGORIES: tuple[str, ...] = tuple(
    sorted(NORTH_STAR_DANGEROUS_CATEGORIES)
) + _ADVISORY_CATEGORIES

# --------------------------------------------------------------------------- #
# Action types
# --------------------------------------------------------------------------- #

# The enforcement targets the revise worker / reviewer can act on, mirroring
# the brief's vocabulary: change the plan, add a gate/scenario/checker,
# dead-delete something, or explicitly halt for a human.
NORTH_STAR_ACTION_TYPES: tuple[str, ...] = (
    "change_plan",
    "add_gate",
    "add_scenario",
    "add_checker",
    "dead_delete",
    "add_human_halt",
)

# Resolution vocabulary for addressed actions (mirrors flags_addressed plus the
# explicit human-halt outcome produced by the pre-worker halt path).
NORTH_STAR_ACTION_RESOLUTIONS: tuple[str, ...] = (
    "addressed",
    "halted",
    "rejected",
)


class NorthStarAction(TypedDict, total=False):
    id: str
    question_id: str
    question: str
    concern: str
    category: str
    action_type: str
    severity: str
    severity_source: str
    evidence: str
    plan_refs: list[str]
    required_change: str


class NorthStarActionAddressed(TypedDict, total=False):
    action_id: str
    resolution: str
    reason: str
    where: str
    plan_refs: list[str]
    action_type: str


def is_blocking_category(category: Any) -> bool:
    """Return ``True`` if *category* is one of the schema-blocking categories."""
    return category in NORTH_STAR_DANGEROUS_CATEGORIES


def is_blocking_action(action: Mapping[str, Any]) -> bool:
    """Return ``True`` if a *normalized* action is blocking."""
    return action.get("severity") == SEVERITY_BLOCKING


# --------------------------------------------------------------------------- #
# Validation error
# --------------------------------------------------------------------------- #


class NorthStarActionValidationError(ValueError):
    """Raised when a North Star action cannot be strictly normalized.

    Carrying a blocking action that fails shape validation would let a
    malformed blocker be silently dropped downstream, so normalization raises
    rather than degrades. Subclassing :class:`ValueError` keeps it catchable
    by existing generic handlers.
    """


# --------------------------------------------------------------------------- #
# JSON schema fragments (worker-facing structured output + audit)
# --------------------------------------------------------------------------- #
#
# These are the canonical shapes embedded into gate.json / review.json /
# revise.json. They use ``x-preserve-explicit-required`` so that, under
# ``strict_schema``/OpenAI strict mode, only the explicitly-listed ``required``
# keys are mandatory — letting optional identity/reference fields stay optional
# while still forbidding additional properties.

NORTH_STAR_ACTION_SCHEMA: dict[str, Any] = {
    "x-preserve-explicit-required": True,
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "question_id": {"type": "string"},
        "question": {"type": "string"},
        "concern": {"type": "string"},
        "category": {"type": "string", "enum": list(NORTH_STAR_ACTION_CATEGORIES)},
        "action_type": {
            "type": "string",
            "enum": list(NORTH_STAR_ACTION_TYPES),
        },
        "severity": {"type": "string", "enum": list(NORTH_STAR_SEVERITIES)},
        "severity_source": {
            "type": "string",
            "enum": list(NORTH_STAR_SEVERITY_SOURCES),
        },
        "evidence": {"type": "string"},
        "plan_refs": {"type": "array", "items": {"type": "string"}},
        "required_change": {"type": "string"},
    },
    # The worker must always emit identity + the actionable core + evidence;
    # the normalizer then enforces non-empty evidence for blocking actions.
    "required": ["id", "concern", "category", "action_type", "evidence"],
}

NORTH_STAR_ACTION_ADDRESSED_SCHEMA: dict[str, Any] = {
    "x-preserve-explicit-required": True,
    "type": "object",
    "properties": {
        "action_id": {"type": "string"},
        "resolution": {
            "type": "string",
            "enum": list(NORTH_STAR_ACTION_RESOLUTIONS),
        },
        "reason": {"type": "string"},
        "where": {"type": "string"},
        "plan_refs": {"type": "array", "items": {"type": "string"}},
        "action_type": {
            "type": "string",
            "enum": list(NORTH_STAR_ACTION_TYPES),
        },
    },
    "required": ["action_id", "resolution", "reason"],
}


# --------------------------------------------------------------------------- #
# Normalization
# --------------------------------------------------------------------------- #


def _location(index: int | None, action_id: str | None) -> str:
    if index is not None:
        base = f"north_star_actions[{index}]"
    else:
        base = "north_star_action"
    return f"{base} ({action_id})" if action_id else base


def normalize_north_star_action(
    raw: Any, *, index: int | None = None
) -> dict[str, Any]:
    """Strictly normalize a single raw North Star action into the carried shape.

    Raises :class:`NorthStarActionValidationError` for any structurally
    malformed action (blocking or advisory). For blocking actions this is
    mandatory — a malformed blocker must never be silently dropped, because
    closeout checks treat the carried set as complete.

    Normalization rules:

    * ``id`` / ``concern`` / ``category`` / ``action_type`` are required and
      validated against the known enums (category/action_type).
    * Dangerous categories are forced to ``severity="blocking"`` /
      ``severity_source="schema"`` regardless of any producer label.
    * Non-dangerous actions are blocking only when the producer explicitly
      labels them so (``severity="blocking"``); otherwise advisory. The
      provenance ``severity_source`` is preserved when it is a known source,
      else recorded as ``"explicit"``.
    * Blocking actions require non-empty ``evidence``.
    * ``question_id`` / ``question`` / ``plan_refs`` / ``required_change`` are
      preserved verbatim when well-formed.
    """
    if not isinstance(raw, Mapping):
        raise NorthStarActionValidationError(
            f"north star action must be an object, got {type(raw).__name__}"
        )

    # --- id (stable identity) ---
    action_id = raw.get("id")
    if isinstance(action_id, str):
        action_id = action_id.strip()
    if not isinstance(action_id, str) or not action_id:
        raise NorthStarActionValidationError(
            f"{_location(index, None)}: missing or empty 'id'"
        )

    loc = _location(index, action_id)

    # --- concern (required actionable content) ---
    concern = raw.get("concern")
    if isinstance(concern, str):
        concern = concern.strip()
    if not concern:
        raise NorthStarActionValidationError(f"{loc}: missing or empty 'concern'")

    # --- category (required, enum-checked) ---
    category = raw.get("category")
    if category not in NORTH_STAR_ACTION_CATEGORIES:
        raise NorthStarActionValidationError(
            f"{loc}: invalid or missing 'category' {category!r}; "
            f"expected one of {list(NORTH_STAR_ACTION_CATEGORIES)}"
        )

    # --- action_type (required, enum-checked) ---
    action_type = raw.get("action_type")
    if action_type not in NORTH_STAR_ACTION_TYPES:
        raise NorthStarActionValidationError(
            f"{loc}: invalid or missing 'action_type' {action_type!r}; "
            f"expected one of {list(NORTH_STAR_ACTION_TYPES)}"
        )

    # --- severity normalization (schema authority for dangerous categories) ---
    if category in NORTH_STAR_DANGEROUS_CATEGORIES:
        severity = SEVERITY_BLOCKING
        severity_source = SEVERITY_SOURCE_SCHEMA
    else:
        provided_severity = raw.get("severity")
        provided_source = raw.get("severity_source")
        if provided_severity == SEVERITY_BLOCKING:
            severity = SEVERITY_BLOCKING
        else:
            severity = SEVERITY_ADVISORY
        severity_source = (
            provided_source
            if provided_source in NORTH_STAR_SEVERITY_SOURCES
            and provided_source != SEVERITY_SOURCE_SCHEMA
            else SEVERITY_SOURCE_EXPLICIT
        )

    blocking = severity == SEVERITY_BLOCKING

    # --- evidence (required non-empty for blocking actions) ---
    evidence = raw.get("evidence")
    if isinstance(evidence, str):
        evidence = evidence.strip()
    else:
        evidence = ""
    if blocking and not evidence:
        raise NorthStarActionValidationError(
            f"{loc}: blocking action (category={category!r}) "
            "missing non-empty 'evidence'"
        )

    normalized: dict[str, Any] = {
        "id": action_id,
        "concern": concern,
        "category": category,
        "action_type": action_type,
        "severity": severity,
        "severity_source": severity_source,
        "evidence": evidence,
    }

    # --- source-question linkage (preserved when present) ---
    question_id = raw.get("question_id")
    if isinstance(question_id, str) and question_id.strip():
        normalized["question_id"] = question_id.strip()
    question = raw.get("question")
    if isinstance(question, str) and question.strip():
        normalized["question"] = question.strip()

    # --- optional concrete plan references / required change ---
    plan_refs = raw.get("plan_refs")
    if isinstance(plan_refs, Sequence) and not isinstance(plan_refs, (str, bytes)):
        normalized["plan_refs"] = [str(ref) for ref in plan_refs]
    required_change = raw.get("required_change")
    if isinstance(required_change, str) and required_change.strip():
        normalized["required_change"] = required_change.strip()

    return normalized


def normalize_north_star_actions(raw: Any) -> list[dict[str, Any]]:
    """Normalize a ``north_star_actions[]`` payload into carried form.

    A non-list / missing value normalizes to an empty list (no actions). Each
    element is strictly normalized via :func:`normalize_north_star_action`;
    malformed actions raise and abort the whole batch so the caller can fail
    the step loudly rather than carry a partial set.
    """
    if raw is None:
        return []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise NorthStarActionValidationError(
            "north_star_actions must be a list of action objects, "
            f"got {type(raw).__name__}"
        )
    return [
        normalize_north_star_action(item, index=index)
        for index, item in enumerate(raw)
    ]


def blocking_north_star_actions(
    actions: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return the subset of *normalized* actions that are blocking."""
    return [
        dict(action)
        for action in actions
        if isinstance(action, Mapping) and action.get("severity") == SEVERITY_BLOCKING
    ]


def normalize_north_star_action_addressed(
    raw: Any, *, index: int | None = None
) -> dict[str, Any]:
    """Strictly normalize a single addressed-action record.

    The deep requirement that a blocking addressed action cite concrete plan
    refs (not just prose) is enforced later by the revise closeout validation
    (Step 6). Here we guarantee structural well-formedness — identity link,
    valid resolution, non-empty reason — so the addressed metadata that
    finalize/review rely on can never be silently malformed.
    """
    if not isinstance(raw, Mapping):
        raise NorthStarActionValidationError(
            "north star addressed action must be an object, "
            f"got {type(raw).__name__}"
        )

    action_id = raw.get("action_id")
    if isinstance(action_id, str):
        action_id = action_id.strip()
    if not isinstance(action_id, str) or not action_id:
        raise NorthStarActionValidationError(
            f"{_location(index, None)}: addressed action missing 'action_id'"
        )

    loc = f"north_star_actions_addressed[{index}] ({action_id})" if index is not None else f"north_star_actions_addressed ({action_id})"

    resolution = raw.get("resolution")
    if resolution not in NORTH_STAR_ACTION_RESOLUTIONS:
        raise NorthStarActionValidationError(
            f"{loc}: invalid or missing 'resolution' {resolution!r}; "
            f"expected one of {list(NORTH_STAR_ACTION_RESOLUTIONS)}"
        )

    reason = raw.get("reason")
    if isinstance(reason, str):
        reason = reason.strip()
    if not reason:
        raise NorthStarActionValidationError(f"{loc}: missing or empty 'reason'")

    normalized: dict[str, Any] = {
        "action_id": action_id,
        "resolution": resolution,
        "reason": reason,
    }

    where = raw.get("where")
    if isinstance(where, str) and where.strip():
        normalized["where"] = where.strip()
    plan_refs = raw.get("plan_refs")
    if isinstance(plan_refs, Sequence) and not isinstance(plan_refs, (str, bytes)):
        normalized["plan_refs"] = [str(ref) for ref in plan_refs]
    action_type = raw.get("action_type")
    if action_type in NORTH_STAR_ACTION_TYPES:
        normalized["action_type"] = action_type

    return normalized


def normalize_north_star_actions_addressed(raw: Any) -> list[dict[str, Any]]:
    """Normalize a ``north_star_actions_addressed[]`` payload."""
    if raw is None:
        return []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise NorthStarActionValidationError(
            "north_star_actions_addressed must be a list of addressed-action "
            f"objects, got {type(raw).__name__}"
        )
    return [
        normalize_north_star_action_addressed(item, index=index)
        for index, item in enumerate(raw)
    ]
