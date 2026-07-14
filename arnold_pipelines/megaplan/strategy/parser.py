"""Deterministic line-aware parser and canonical serializer for v1 strategy documents.

Parse
-----

:func:`parse_strategy` reads a v1 ``.megaplan/STRATEGY.md`` source string and
returns a :class:`StrategyDocument`.  Every construct — sections, roadmap
bullets, diagnostics — carries a :class:`SourceLocation` so automation can act
safely on validation results.

Serialize
---------

:func:`serialize_strategy` writes a :class:`StrategyDocument` back to canonical
Markdown.  The serializer is *deterministic*: given the same parsed document it
produces byte-for-byte equivalent output.  It preserves stable-direction body
text as-authored and never normalises display titles.
"""

from __future__ import annotations

import re

import yaml

from arnold_pipelines.megaplan.strategy.contract import (
    SCHEMA_VERSION,
    REQUIRED_ROADMAP_SECTIONS,
    REQUIRED_STABLE_SECTIONS,
    RoadmapEntry,
    RoadmapHorizon,
    SourceLocation,
    StrategyDiagnostic,
    StrategyDocument,
    StrategyIdentity,
    StrategySection,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Regex for a roadmap bullet:  ``- [type:ref] <display title>``
# Group 1 = type, Group 2 = ref, Group 3 = display title.
# Ref may be empty (malformed), which we diagnose separately.
_BULLET_RE = re.compile(r"^- \[([a-z][a-z_]*):([^\]]*)\]\s+(.*)$")

# Additional diagnostics regex: detect *typed* bullet-like lines (starts with
# ``- [word:...]``) outside of roadmap sections or inside with empty refs.
_TYPED_BULLET_HINT_RE = re.compile(r"^- \[([a-z][a-z_]*):[^\]]*\]")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_strategy(source: str, path: str) -> StrategyDocument:
    """Parse *source* as a v1 strategy Markdown document.

    Parameters
    ----------
    source:
        The raw text of ``.megaplan/STRATEGY.md``.
    path:
        An identifier for the source file used in every
        :class:`SourceLocation` (typically the repo-relative path).

    Returns
    -------
    StrategyDocument
        The parsed document.  Check ``document.diagnostics`` — an empty
        list means the document is clean.
    """
    diagnostics: list[StrategyDiagnostic] = []
    lines = source.split("\n")

    # ---- frontmatter -------------------------------------------------------
    schema_version, body_start_line, fm_diags = _parse_frontmatter(
        lines, path
    )
    diagnostics.extend(fm_diags)

    # ---- sections ----------------------------------------------------------
    raw_sections = _scan_sections(lines, body_start_line)
    stable_sections, roadmap_entries, sec_diags = _classify_sections(
        raw_sections, lines, path
    )
    diagnostics.extend(sec_diags)

    # ---- schema version diagnostic (deferred so it appears after frontmatter errors) ----
    if schema_version != SCHEMA_VERSION:
        diagnostics.append(
            StrategyDiagnostic(
                level="error",
                message=(
                    f"Unsupported schema_version: expected "
                    f"'{SCHEMA_VERSION}', got '{schema_version or '<missing>'}'"
                ),
                source_location=SourceLocation(path=path, line=1, column=1),
            )
        )

    # ---- build roadmap dict -------------------------------------------------
    roadmap: dict[RoadmapHorizon, list[RoadmapEntry]] = {
        "Now": [],
        "Next": [],
        "Later": [],
    }
    for entry in roadmap_entries:
        roadmap[entry.horizon].append(entry)

    return StrategyDocument(
        schema_version=schema_version,
        stable_direction=stable_sections,
        roadmap=roadmap,
        diagnostics=diagnostics,
    )


def serialize_strategy(document: StrategyDocument) -> str:
    """Serialize *document* back to canonical v1 Markdown.

    The output round-trips without semantic loss:
    ``parse_strategy(serialize_strategy(doc), doc_path)`` produces an
    equivalent :class:`StrategyDocument` (identical identity, horizon,
    stable-direction bodies, and display titles).
    """
    parts: list[str] = []

    # Frontmatter
    parts.append("---")
    parts.append(f"schema_version: {SCHEMA_VERSION}")
    parts.append("---")
    parts.append("")  # blank line after frontmatter

    # Stable direction sections
    for section in document.stable_direction:
        parts.append(f"## {section.title}")
        parts.append("")
        body = section.body.strip()
        if body:
            parts.append(body)
            parts.append("")

    # Roadmap sections
    for horizon in REQUIRED_ROADMAP_SECTIONS:
        entries = document.roadmap.get(horizon, [])
        parts.append(f"## {horizon}")
        parts.append("")
        if entries:
            for entry in entries:
                parts.append(
                    f"- [{entry.identity.type}:{entry.identity.ref}]"
                    f" {entry.display_title}"
                )
            parts.append("")

    # Join with single newlines; final output ends with a single newline.
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


def _parse_frontmatter(
    lines: list[str], path: str
) -> tuple[str, int, list[StrategyDiagnostic]]:
    """Parse YAML frontmatter.

    Returns ``(schema_version, body_start_line, diagnostics)`` where
    *body_start_line* is 1-indexed.
    """
    diagnostics: list[StrategyDiagnostic] = []

    if not lines or lines[0].strip() != "---":
        return (
            "",
            1,
            [
                StrategyDiagnostic(
                    level="error",
                    message="Missing frontmatter: document must start with '---'",
                    source_location=SourceLocation(path=path, line=1, column=1),
                )
            ],
        )

    # Find closing ``---``
    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return (
            "",
            1,
            [
                StrategyDiagnostic(
                    level="error",
                    message="Unclosed frontmatter: missing closing '---'",
                    source_location=SourceLocation(path=path, line=1, column=1),
                )
            ],
        )

    # Parse YAML between the ``---`` fences.
    fm_text = "\n".join(lines[1:end_idx])
    try:
        metadata = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as exc:
        return (
            "",
            end_idx + 2,
            [
                StrategyDiagnostic(
                    level="error",
                    message=f"Invalid YAML in frontmatter: {exc}",
                    source_location=SourceLocation(path=path, line=2, column=1),
                )
            ],
        )

    if not isinstance(metadata, dict):
        return (
            "",
            end_idx + 2,
            [
                StrategyDiagnostic(
                    level="error",
                    message="Frontmatter must be a YAML mapping",
                    source_location=SourceLocation(path=path, line=2, column=1),
                )
            ],
        )

    schema_version = str(metadata.get("schema_version", ""))

    # Body starts on the line *after* the closing ``---``.
    body_start_line = end_idx + 2  # +1 for 0→1-index, +1 for next line

    return schema_version, body_start_line, diagnostics


# ---------------------------------------------------------------------------
# Section scanning
# ---------------------------------------------------------------------------


class _RawSection:
    """Intermediate representation of a scanned ``## Title`` section."""

    __slots__ = ("title", "heading_line", "body_start_line", "body_end_line")

    def __init__(
        self,
        title: str,
        heading_line: int,
        body_start_line: int,
        body_end_line: int,
    ) -> None:
        self.title = title
        self.heading_line = heading_line  # 1-indexed
        self.body_start_line = body_start_line  # 1-indexed (inclusive)
        self.body_end_line = body_end_line  # 1-indexed (exclusive)


def _scan_sections(
    lines: list[str], body_start_line: int
) -> list[_RawSection]:
    """Scan *lines* starting at *body_start_line* (1-indexed) for ``## Title`` sections.

    Returns ordered :class:`_RawSection` objects.  Preamble text before the
    first ``##`` heading is silently skipped.
    """
    sections: list[_RawSection] = []
    i = body_start_line - 1  # convert to 0-indexed
    n = len(lines)

    # Skip preamble: everything before the first ``## `` heading.
    while i < n and not lines[i].startswith("## "):
        i += 1

    while i < n:
        line = lines[i]
        if not line.startswith("## "):
            i += 1
            continue

        title = line[3:].strip()
        heading_line = i + 1  # 1-indexed
        body_start = i + 2  # 1-indexed, first line after heading

        # Advance to the next ``## `` heading (or EOF).
        i += 1
        while i < n and not lines[i].startswith("## "):
            i += 1

        body_end = i + 1  # 1-indexed, exclusive (points to next heading or past EOF)

        sections.append(
            _RawSection(
                title=title,
                heading_line=heading_line,
                body_start_line=body_start,
                body_end_line=body_end,
            )
        )

    return sections


# ---------------------------------------------------------------------------
# Section classification
# ---------------------------------------------------------------------------

# Recognised section titles (case-sensitive).
_STABLE_SET: set[str] = set(REQUIRED_STABLE_SECTIONS)
_ROADMAP_SET: set[str] = set(REQUIRED_ROADMAP_SECTIONS)
_ALL_RECOGNIZED: set[str] = _STABLE_SET | _ROADMAP_SET


def _classify_sections(
    raw_sections: list[_RawSection],
    lines: list[str],
    path: str,
) -> tuple[
    list[StrategySection], list[RoadmapEntry], list[StrategyDiagnostic]
]:
    """Classify raw sections into stable-direction sections and roadmap entries.

    Returns ``(stable_sections, roadmap_entries, diagnostics)``.
    """
    diagnostics: list[StrategyDiagnostic] = []
    stable_sections: list[StrategySection] = []
    roadmap_entries: list[RoadmapEntry] = []

    seen_stable: list[str] = []
    seen_roadmap: list[str] = []
    in_roadmap = False  # True once we've seen the first roadmap section

    for raw in raw_sections:
        title = raw.title

        if title in _STABLE_SET:
            if in_roadmap:
                diagnostics.append(
                    StrategyDiagnostic(
                        level="error",
                        message=(
                            f"Stable-direction section '## {title}' must appear "
                            f"before roadmap sections"
                        ),
                        source_location=SourceLocation(
                            path=path, line=raw.heading_line, column=1
                        ),
                    )
                )
                continue

            seen_stable.append(title)
            body = _extract_body(raw, lines)
            # Check for typed bullets in stable-direction bodies
            _check_typed_bullets_outside_roadmap(
                lines, raw, body, path, diagnostics
            )

            stable_sections.append(
                StrategySection(
                    title=title,
                    body=body,
                    source_location=SourceLocation(
                        path=path, line=raw.heading_line, column=1
                    ),
                )
            )

        elif title in _ROADMAP_SET:
            in_roadmap = True
            seen_roadmap.append(title)
            entries, bullet_diags = _parse_roadmap_section(
                lines, raw, title, path
            )
            roadmap_entries.extend(entries)
            diagnostics.extend(bullet_diags)

        else:
            # Unrecognised section heading
            diagnostics.append(
                StrategyDiagnostic(
                    level="error",
                    message=(
                        f"Unsupported section '## {title}'. "
                        f"v1 supports stable-direction sections "
                        f"({', '.join(REQUIRED_STABLE_SECTIONS)}) and "
                        f"roadmap sections ({', '.join(REQUIRED_ROADMAP_SECTIONS)})."
                    ),
                    source_location=SourceLocation(
                        path=path, line=raw.heading_line, column=1
                    ),
                )
            )

    # Validate required sections are present and in order.
    _validate_section_ordering(
        seen_stable,
        list(REQUIRED_STABLE_SECTIONS),
        "stable-direction",
        path,
        diagnostics,
    )
    _validate_section_ordering(
        seen_roadmap,
        list(REQUIRED_ROADMAP_SECTIONS),
        "roadmap",
        path,
        diagnostics,
    )

    return stable_sections, roadmap_entries, diagnostics


def _extract_body(raw: _RawSection, lines: list[str]) -> str:
    """Extract the body text of a stable-direction section.

    Leading and trailing blank lines are stripped so the body is clean,
    but internal blank lines are preserved exactly.
    """
    body_lines = lines[raw.body_start_line - 1 : raw.body_end_line - 1]
    # Strip leading blank lines
    while body_lines and body_lines[0].strip() == "":
        body_lines.pop(0)
    # Strip trailing blank lines
    while body_lines and body_lines[-1].strip() == "":
        body_lines.pop()
    return "\n".join(body_lines)


# ---------------------------------------------------------------------------
# Roadmap bullet parsing
# ---------------------------------------------------------------------------

_VALID_TYPES: set[str] = {"ticket", "epic"}


def _parse_roadmap_section(
    lines: list[str],
    raw: _RawSection,
    horizon_title: str,
    path: str,
) -> tuple[list[RoadmapEntry], list[StrategyDiagnostic]]:
    """Parse roadmap bullets from a single horizon section.

    The *horizon_title* must be one of ``Now``, ``Next``, ``Later``.
    """
    diagnostics: list[StrategyDiagnostic] = []
    entries: list[RoadmapEntry] = []
    horizon: RoadmapHorizon = horizon_title  # type: ignore[assignment]

    # Iterate over lines in this section's body range.
    for line_idx in range(raw.body_start_line - 1, raw.body_end_line - 1):
        line = lines[line_idx]
        stripped = line.strip()
        line_no = line_idx + 1  # 1-indexed

        # Skip blank lines and non-bullet lines.
        if not stripped.startswith("- "):
            continue

        # Try the narrow bullet grammar: ``- [type:ref] title``
        match = _BULLET_RE.match(stripped)
        if match is None:
            # Check if it looks like a typed bullet with a malformed pattern.
            if _TYPED_BULLET_HINT_RE.match(stripped):
                diagnostics.append(
                    StrategyDiagnostic(
                        level="error",
                        message=(
                            f"Malformed roadmap bullet: '{stripped}'. "
                            f"Expected format: '- [ticket:ULID] Display title' "
                            f"or '- [epic:slug] Display title'"
                        ),
                        source_location=SourceLocation(
                            path=path, line=line_no, column=1
                        ),
                    )
                )
            # Non-typed bullets (regular list items) inside roadmap sections
            # are fine — they're just part of the section prose.
            continue

        item_type = match.group(1)
        ref = match.group(2)
        display_title = match.group(3)

        # Empty ref is malformed.
        if not ref.strip():
            diagnostics.append(
                StrategyDiagnostic(
                    level="error",
                    message=(
                        f"Malformed roadmap bullet: '{stripped}'. "
                        f"Missing reference after ':' in '[{item_type}:]'."
                    ),
                    source_location=SourceLocation(
                        path=path, line=line_no, column=1
                    ),
                )
            )
            continue

        # Validate item type.
        if item_type not in _VALID_TYPES:
            diagnostics.append(
                StrategyDiagnostic(
                    level="error",
                    message=(
                        f"Unsupported item type '{item_type}' in roadmap bullet. "
                        f"Only 'ticket' and 'epic' are valid in v1."
                    ),
                    source_location=SourceLocation(
                        path=path, line=line_no, column=1
                    ),
                )
            )
            continue

        entries.append(
            RoadmapEntry(
                identity=StrategyIdentity(
                    type=item_type,  # type: ignore[arg-type]
                    ref=ref,
                ),
                display_title=display_title,
                horizon=horizon,
                source_location=SourceLocation(
                    path=path, line=line_no, column=1
                ),
            )
        )

    return entries, diagnostics


def _check_typed_bullets_outside_roadmap(
    lines: list[str],
    raw: _RawSection,
    _body: str,
    path: str,
    diagnostics: list[StrategyDiagnostic],
) -> None:
    """Scan a stable-direction section body for typed bullets and emit diagnostics."""
    for line_idx in range(raw.body_start_line - 1, raw.body_end_line - 1):
        line = lines[line_idx]
        stripped = line.strip()
        if _TYPED_BULLET_HINT_RE.match(stripped):
            line_no = line_idx + 1
            diagnostics.append(
                StrategyDiagnostic(
                    level="error",
                    message=(
                        f"Typed bullet '{stripped}' found outside a roadmap "
                        f"section. Roadmap bullets may only appear under "
                        f"'## Now', '## Next', or '## Later'."
                    ),
                    source_location=SourceLocation(
                        path=path, line=line_no, column=1
                    ),
                )
            )


# ---------------------------------------------------------------------------
# Section ordering validation
# ---------------------------------------------------------------------------


def _validate_section_ordering(
    seen: list[str],
    required: list[str],
    kind_label: str,
    path: str,
    diagnostics: list[StrategyDiagnostic],
) -> None:
    """Validate that *required* sections appear in order in *seen*.

    Missing sections and out-of-order sections both produce hard errors.
    """
    # Build a map from section title to its position in *seen*.
    seen_positions: dict[str, int] = {}
    for idx, title in enumerate(seen):
        if title not in seen_positions:
            seen_positions[title] = idx

    # Check ordering: each required section must appear before any later
    # required section (if present), and after any earlier required section.
    prev_pos = -1
    for title in required:
        if title not in seen_positions:
            diagnostics.append(
                StrategyDiagnostic(
                    level="error",
                    message=f"Missing required {kind_label} section: '## {title}'",
                    source_location=SourceLocation(path=path, line=1, column=1),
                )
            )
            continue

        pos = seen_positions[title]
        if pos <= prev_pos:
            diagnostics.append(
                StrategyDiagnostic(
                    level="error",
                    message=(
                        f"Out-of-order {kind_label} section: "
                        f"'## {title}' must appear after earlier "
                        f"{kind_label} sections"
                    ),
                    source_location=SourceLocation(path=path, line=1, column=1),
                )
            )
        prev_pos = pos
