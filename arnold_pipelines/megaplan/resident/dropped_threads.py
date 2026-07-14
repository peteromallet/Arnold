"""Input contract for the resident ``/dropped-threads`` review command."""

from __future__ import annotations

from datetime import timedelta
import re


DROPPED_THREADS_COMMAND = "dropped-threads"
DROPPED_THREADS_DESCRIPTION = "Review recent conversation for dropped or action-worthy threads."
DEFAULT_DROPPED_THREADS_LOOKBACK = timedelta(hours=6)
MAX_DROPPED_THREADS_LOOKBACK = timedelta(days=7)
_DURATION_RE = re.compile(r"^(?P<amount>[1-9][0-9]*)\s*(?P<unit>[mhdMHD])$")


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
    """Render the durable, evidence-led request sent through a normal turn."""

    rendered = format_dropped_threads_lookback(lookback)
    return (
        f"Review the authoritative persisted conversation for the last {rendered} and identify "
        "only threads that were dropped, insufficiently closed, or now action-worthy. "
        "Do not rely only on hot-context excerpts or model history: use the authoritative persisted "
        "conversation search/context routes for the relevant scope, then ground every finding in evidence. "
        "Distinguish pending or conditional work from work that is actually due now; do not invent "
        "follow-ups, commitments, or deadlines. For each genuine finding, state the thread, why it "
        "needs attention, and the smallest appropriate next action. Include relevant absolute timestamps "
        "in the configured user timezone (with date/time, timezone abbreviation, and UTC offset); retain "
        "relative durations as relative. If nothing qualifies, say so plainly. Answer concisely."
    )


__all__ = [
    "DEFAULT_DROPPED_THREADS_LOOKBACK",
    "DROPPED_THREADS_COMMAND",
    "DROPPED_THREADS_DESCRIPTION",
    "InvalidLookback",
    "dropped_threads_prompt",
    "format_dropped_threads_lookback",
    "parse_dropped_threads_lookback",
]
