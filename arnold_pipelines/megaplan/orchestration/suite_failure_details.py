"""Failure-detail extraction for suite verification prompts."""

from __future__ import annotations

import re
from pathlib import Path

_FAILED_LINE_RE = re.compile(
    r"^FAILED\s+(?P<nodeid>\S+)(?:\s+-\s+(?P<detail>.+))?$",
    re.MULTILINE,
)
_TRACEBACK_HEADER_RE_TEMPLATE = r"_{{10,}}\s+{nodeid_pattern}\s+_{{10,}}"


def extract_failure_details(
    raw_log_path: Path, nodeids: list[str],
) -> list[dict[str, str]]:
    sentinel = {
        "error_type": "<unknown>",
        "message": "<unparsed>",
        "traceback_head": "<could not extract>",
    }
    try:
        content = raw_log_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [{"nodeid": nid, **sentinel} for nid in nodeids]

    failed_by_nodeid = {
        m.group("nodeid"): m.group("detail") or ""
        for m in _FAILED_LINE_RE.finditer(content)
        if m.group("nodeid")
    }
    return [
        _failure_detail(content, nid, failed_by_nodeid.get(nid), sentinel)
        for nid in nodeids
    ]


def _failure_detail(
    content: str,
    nodeid: str,
    summary_detail: str | None,
    sentinel: dict[str, str],
) -> dict[str, str]:
    detail = {"nodeid": nodeid, **sentinel}
    if summary_detail is not None:
        parts = summary_detail.split(": ", 1)
        if len(parts) == 2 and parts[0]:
            detail["error_type"] = parts[0].strip()
            detail["message"] = parts[1].strip()
        elif summary_detail.strip():
            detail["message"] = summary_detail.strip()

    tb_header_pat = _TRACEBACK_HEADER_RE_TEMPLATE.format(
        nodeid_pattern=re.escape(nodeid)
    )
    tb_match = re.search(tb_header_pat, content)
    if not tb_match:
        return detail
    tb_rest = content[tb_match.end():]
    end_pos = len(tb_rest)
    for pattern in (r"\n=+", r"\n_{10,}", r"\nFAILED\s+", r"\nPASSED\s+", r"\n\n[^\s]"):
        match = re.search(pattern, tb_rest)
        if match is not None and match.start() < end_pos:
            end_pos = match.start()
    tb_slice = tb_rest[:end_pos].strip()
    if tb_slice:
        detail["traceback_head"] = tb_slice[:500]
    return detail
