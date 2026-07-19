"""Input contract for the resident ``/dropped-threads`` review command."""

from __future__ import annotations

from datetime import timedelta
import re


DROPPED_THREADS_COMMAND = "dropped-threads"
DROPPED_THREADS_DESCRIPTION = "Find dropped commitments and evidence-backed strategic action gaps."
DEFAULT_DROPPED_THREADS_LOOKBACK = timedelta(hours=6)
MAX_DROPPED_THREADS_LOOKBACK = timedelta(days=7)
_DURATION_RE = re.compile(r"^(?P<amount>[1-9][0-9]*)\s*(?P<unit>[mhdMHD])$")

# These values are part of the resident prompt/output contract.  Keep them
# stable so downstream prose consumers can distinguish an explicit promise
# that went missing from an implication that was never turned into owned work.
DROPPED_THREAD_CLASSIFICATIONS = (
    "explicit_dropped_thread",
    "strategic_action_gap",
)
STRATEGIC_ACTION_GAP_CATEGORIES = (
    "identified_defect_or_risk",
    "necessary_follow_up",
    "actionable_evidence_or_recommendation",
    "partial_fix_residual_risk",
)
DROPPED_THREADS_OUTPUT_FIELDS = (
    "classification",
    "category",
    "thread",
    "evidence",
    "why_action_was_expected",
    "missing_disposition_evidence",
    "confidence",
    "recommended_next_action",
)


class InvalidLookback(ValueError):
    """The supplied lookback is not a safe bounded duration."""


def parse_dropped_threads_lookback(value: str | None) -> timedelta:
    """Parse a compact, positive duration for a conversation review."""

    if value is None or not value.strip():
        return DEFAULT_DROPPED_THREADS_LOOKBACK
    match = _DURATION_RE.fullmatch(value.strip())
    if match is None:
        raise InvalidLookback("use a positive duration such as `30m`, `6h`, or `1d`")
    amount = int(match.group("amount"))
    unit = match.group("unit").lower()
    duration = timedelta(**{"m": {"minutes": amount}, "h": {"hours": amount}, "d": {"days": amount}}[unit])
    if duration > MAX_DROPPED_THREADS_LOOKBACK:
        raise InvalidLookback("lookback must be no longer than `7d`")
    return duration


def format_dropped_threads_lookback(duration: timedelta) -> str:
    seconds = int(duration.total_seconds())
    if seconds % 86_400 == 0:
        return f"{seconds // 86_400}d"
    if seconds % 3_600 == 0:
        return f"{seconds // 3_600}h"
    return f"{seconds // 60}m"


def dropped_threads_prompt(lookback: timedelta) -> str:
    """Render the durable evidence and precision contract for a normal turn."""

    rendered = format_dropped_threads_lookback(lookback)
    return (
        f"Review the authoritative persisted conversation and relevant execution evidence for the last {rendered}. "
        "Do not rely only on hot-context excerpts or model history: use search_messages and the authoritative "
        "conversation search/context routes for the current conversation, and follow relevant execution evidence. "
        "Identify only evidence-backed findings in exactly these classifications: "
        "(1) explicit_dropped_thread: an explicit request, commitment, or owned action was not completed or "
        "adequately closed; (2) strategic_action_gap: no explicit promise is required, but the evidence made "
        "material action reasonably expected and no satisfactory disposition followed. Strategic action gaps are "
        "bounded to these categories: identified_defect_or_risk, where a concrete bug, defect, failure, or material "
        "risk was identified but no investigation, fix, or explicit disposition followed; necessary_follow_up, "
        "where completed work created an obvious necessary follow-up but no action, owner, durable todo/ticket/plan, "
        "or explicit deferral followed; actionable_evidence_or_recommendation, where evidence or a recommendation "
        "called for action but the thread ended with acknowledgement or reporting only; and partial_fix_residual_risk, "
        "where a partial fix or workaround left a stated root cause or residual risk untreated. "
        "A finding qualifies only when evidence supports both (a) a materially actionable implication, tied to a "
        "concrete consequence, risk, or necessary outcome, and (b) absence of a satisfactory disposition after "
        "checking later conversation and relevant execution records. Acknowledgement or reporting alone is not a "
        "disposition. Verified execution, explicit rejection, reasoned deferral, delegation to a durable owner, "
        "capture in a durable ticket/todo/initiative/plan, or supersession is a disposition. "
        "Preserve precision: do not flag a suggestion, hypothetical, optional enhancement, observation, open question, "
        "pending or conditional work that is not due, or intentionally deferred work unless separate evidence meets "
        "both qualification requirements. Do not invent intent, follow-ups, commitments, owners, or deadlines. "
        "For every genuine finding, preserve the existing thread/why/next-action shape and report these fields: "
        "classification; category (for strategic_action_gap); thread; linked or otherwise identifiable evidence with "
        "relevant timestamps; why_action_was_expected; missing_disposition_evidence, including what later scope was "
        "checked and any uncertainty; confidence (high/medium/low with a brief rationale); and the smallest "
        "recommended_next_action. Prefer omitting low-confidence candidates; never turn uncertainty into an assertion "
        "about intent or absence. Distinguish pending or conditional work from work actually due now. Include absolute "
        "user-visible timestamps in the configured user timezone with local date/time, timezone abbreviation, and "
        "numeric UTC offset; retain relative durations as relative. If nothing qualifies, say so plainly. Answer concisely."
    )


__all__ = [
    "DEFAULT_DROPPED_THREADS_LOOKBACK",
    "DROPPED_THREADS_COMMAND",
    "DROPPED_THREADS_DESCRIPTION",
    "DROPPED_THREAD_CLASSIFICATIONS",
    "DROPPED_THREADS_OUTPUT_FIELDS",
    "InvalidLookback",
    "STRATEGIC_ACTION_GAP_CATEGORIES",
    "dropped_threads_prompt",
    "format_dropped_threads_lookback",
    "parse_dropped_threads_lookback",
]
