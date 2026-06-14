"""Neutral LLM JSON extraction — robust parse from raw model output.

Provides :func:`parse_llm_json` implementing a 4-strategy resolution
for extracting JSON dict(s) from messy LLM output text.

Strategy order:
1. Direct ``json.loads`` — ideal case, clean JSON.
2. `` ```json ... ``` `` fenced block extraction.
3. First ``{...}`` object scan via ``JSONDecoder.raw_decode``.
4. Return ``None`` (or ``[]`` when *multiple* is ``True``) when no
   dict can be extracted.

No Megaplan imports; this is a neutral pipeline utility.
"""

from __future__ import annotations

import json
import re
from typing import Any

__all__ = ["parse_llm_json"]

_JSON_FENCE_RE = re.compile(r"```json\s*\n(.*?)```", re.DOTALL)


def parse_llm_json(
    text: str,
    *,
    multiple: bool = False,
) -> dict[str, Any] | list[dict[str, Any]] | None:
    """Parse JSON dict(s) from raw LLM output.

    Parameters
    ----------
    text:
        Raw model output string — may contain prose, markdown fences,
        or embedded JSON.
    multiple:
        When ``False`` (default), returns the first ``dict`` found or
        ``None`` when no dict can be extracted.
        When ``True``, returns a ``list`` of all ``dict`` values found
        (empty list when none).

    Returns
    -------
    dict | list[dict] | None
        Extracted JSON value(s), or ``None`` / ``[]`` when nothing
        found.
    """
    stripped = text.strip()
    if not stripped:
        return [] if multiple else None

    # ── Strategy 1 — direct parse ──────────────────────────────────────
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        pass
    else:
        # json.loads succeeded — do not fall through to weaker strategies.
        if multiple:
            if isinstance(parsed, list):
                if all(isinstance(item, dict) for item in parsed):
                    return parsed
            elif isinstance(parsed, dict):
                return [parsed]
            return []  # valid JSON but wrong shape
        elif isinstance(parsed, dict):
            return parsed
        return None  # valid JSON but wrong shape (array / scalar)

    # ── Strategy 2 — ```json fenced block ──────────────────────────────
    fenced_blocks = _JSON_FENCE_RE.findall(stripped)
    fenced_dicts: list[dict[str, Any]] = []
    for block in fenced_blocks:
        try:
            parsed = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            if not multiple:
                return parsed
            fenced_dicts.append(parsed)
        elif isinstance(parsed, list) and all(
            isinstance(item, dict) for item in parsed
        ):
            if not multiple:
                return parsed[0] if parsed else None  # type: ignore[return-value]
            fenced_dicts.extend(parsed)

    # ── Strategy 3 — embedded {}-scan ──────────────────────────────────
    # Remove fenced blocks from the text so the embedded scan doesn't
    # re-find dicts already captured by strategy 2.
    scan_text = _JSON_FENCE_RE.sub("", stripped) if fenced_blocks else stripped
    decoder = json.JSONDecoder()
    cursor = 0
    embedded_dicts: list[dict[str, Any]] = []

    while True:
        brace = scan_text.find("{", cursor)
        if brace < 0:
            break
        try:
            parsed, end = decoder.raw_decode(scan_text[brace:])
        except json.JSONDecodeError:
            cursor = brace + 1
            continue
        if isinstance(parsed, dict):
            if not multiple:
                return parsed
            embedded_dicts.append(parsed)
        cursor = brace + end

    # ── Combine & return (multiple mode) / fall through (single mode) ──
    if multiple:
        all_dicts = fenced_dicts + embedded_dicts
        return all_dicts

    # ── Strategy 4 — no dict found ─────────────────────────────────────
    return None
