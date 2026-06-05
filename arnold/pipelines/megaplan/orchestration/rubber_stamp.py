"""Rubber-stamp detection helpers for orchestration reviews."""

from __future__ import annotations

from arnold.pipelines.megaplan._core import normalize_text


_GENERIC_ACKS = {
    "ack",
    "checked",
    "confirmed",
    "done",
    "good",
    "looks good",
    "n/a",
    "na",
    "ok",
    "verified",
    "yes",
}
_MIN_VERDICT_CHARS = 20
_MIN_VERDICT_WORDS = 4
_MIN_VERDICT_UNIQUE_WORDS = 3


def is_rubber_stamp(text: str, *, strict: bool = False) -> bool:
    stripped = text.strip()
    normalized = normalize_text(text).strip(" .!?,;:")
    if normalized in _GENERIC_ACKS:
        return True
    if not strict:
        return False
    if len(stripped) <= _MIN_VERDICT_CHARS:
        return True
    words = stripped.split()
    if len(words) < _MIN_VERDICT_WORDS:
        return True
    unique_words = {word.lower() for word in words}
    return len(unique_words) < _MIN_VERDICT_UNIQUE_WORDS


def _is_perfunctory_ack(note: str) -> bool:
    return is_rubber_stamp(note, strict=False)
