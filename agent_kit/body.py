"""Markdown body parsing and section-level editing helpers."""

from __future__ import annotations

from dataclasses import dataclass, replace
import difflib
import re


HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
TITLE_RE = re.compile(r"^#\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_PREAMBLE = "_preamble"


class BodyValidationError(ValueError):
    pass


class SectionNotFound(ValueError):
    pass


class SectionExists(ValueError):
    pass


class InvalidPosition(ValueError):
    pass


@dataclass(frozen=True)
class Section:
    name: str
    heading: str
    content: str

    @property
    def raw(self) -> str:
        return f"{self.heading}{self.content}"


@dataclass(frozen=True)
class ParsedBody:
    title: str | None
    goal_first_paragraph: str | None
    preamble: str
    sections: list[Section]


def parse(body: str) -> ParsedBody:
    """Parse markdown into title, preamble, and top-level ## sections.

    This function is deliberately lenient and never raises for malformed body
    text. Validation for writes is handled by ``validate_for_write``.
    """

    try:
        text = "" if body is None else str(body)
        boundaries = _section_boundaries(text)
        if not boundaries:
            preamble = text
            sections: list[Section] = []
        else:
            preamble = text[: boundaries[0][0]]
            sections = []
            for index, (start, end, name, heading) in enumerate(boundaries):
                next_start = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(text)
                sections.append(Section(name=name, heading=heading, content=text[end:next_start]))
        return ParsedBody(
            title=_extract_title(preamble),
            goal_first_paragraph=_extract_goal(sections),
            preamble=preamble,
            sections=sections,
        )
    except Exception:
        return ParsedBody(title=None, goal_first_paragraph=None, preamble="" if body is None else str(body), sections=[])


def serialize(parsed: ParsedBody) -> str:
    return parsed.preamble + "".join(section.raw for section in parsed.sections)


def validate_for_write(parsed: ParsedBody) -> None:
    if not parsed.title:
        raise BodyValidationError("body_missing_required_section: title")
    if not parsed.goal_first_paragraph:
        raise BodyValidationError("body_missing_required_section: goal")


def outline(parsed: ParsedBody) -> dict[str, object]:
    body_text = serialize(parsed)
    return {
        "title": parsed.title,
        "goal": parsed.goal_first_paragraph,
        "total_lines": _line_count(body_text),
        "sections": [
            {
                "name": section.name,
                "line_count": _line_count(section.raw),
            }
            for section in parsed.sections
        ],
    }


def replace_section(parsed: ParsedBody, name: str, content: str) -> ParsedBody:
    if name == _PREAMBLE:
        return parse(str(content) + "".join(section.raw for section in parsed.sections))
    index = _section_index(parsed, name)
    sections = list(parsed.sections)
    sections[index] = replace(sections[index], content=str(content))
    return parse(parsed.preamble + "".join(section.raw for section in sections))


def append_to_section(parsed: ParsedBody, name: str, content: str) -> ParsedBody:
    if name == _PREAMBLE:
        return replace_section(parsed, name, parsed.preamble + str(content))
    index = _section_index(parsed, name)
    sections = list(parsed.sections)
    sections[index] = replace(sections[index], content=sections[index].content + str(content))
    return parse(parsed.preamble + "".join(section.raw for section in sections))


def add_section(parsed: ParsedBody, name: str, content: str, position: str = "end") -> ParsedBody:
    if name == _PREAMBLE:
        raise SectionExists(_PREAMBLE)
    if any(section.name == name for section in parsed.sections):
        raise SectionExists(name)
    sections = list(parsed.sections)
    section = Section(name=name, heading=f"## {name}\n", content=str(content))
    index = _position_index(parsed, position)
    sections.insert(index, section)
    return parse(parsed.preamble + "".join(item.raw for item in sections))


def remove_section(parsed: ParsedBody, name: str) -> ParsedBody:
    if name == _PREAMBLE:
        return parse("".join(section.raw for section in parsed.sections))
    index = _section_index(parsed, name)
    sections = list(parsed.sections)
    del sections[index]
    return parse(parsed.preamble + "".join(section.raw for section in sections))


def rename_section(parsed: ParsedBody, old_name: str, new_name: str) -> ParsedBody:
    if old_name == _PREAMBLE or new_name == _PREAMBLE:
        raise InvalidPosition("_preamble cannot be renamed")
    index = _section_index(parsed, old_name)
    if any(section.name == new_name for section in parsed.sections):
        raise SectionExists(new_name)
    sections = list(parsed.sections)
    ending = "\r\n" if sections[index].heading.endswith("\r\n") else "\n" if sections[index].heading.endswith("\n") else ""
    sections[index] = replace(sections[index], name=new_name, heading=f"## {new_name}{ending}")
    return parse(parsed.preamble + "".join(section.raw for section in sections))


def reorder(parsed: ParsedBody, names: list[str]) -> ParsedBody:
    current = [section.name for section in parsed.sections]
    if sorted(names) != sorted(current) or len(names) != len(current):
        missing = next((name for name in current if name not in names), None)
        raise SectionNotFound(missing or "section")
    by_name = {section.name: section for section in parsed.sections}
    return parse(parsed.preamble + "".join(by_name[name].raw for name in names))


def compute_diff(before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="before",
            tofile="after",
            n=3,
        )
    )


def diffs_equivalent(left: str, right: str) -> bool:
    return _normalize_diff(left) == _normalize_diff(right)


def _section_boundaries(text: str) -> list[tuple[int, int, str, str]]:
    boundaries: list[tuple[int, int, str, str]] = []
    offset = 0
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if fence:
            if stripped.startswith(fence):
                fence = None
        else:
            fence_match = _FENCE_RE.match(line)
            if fence_match:
                fence = fence_match.group(1)
            else:
                heading_text = line[:-1] if line.endswith("\n") else line
                if heading_text.endswith("\r"):
                    heading_text = heading_text[:-1]
                match = HEADING_RE.match(heading_text)
                if match:
                    boundaries.append((offset, offset + len(line), match.group(1), line))
        offset += len(line)
    return boundaries


def _extract_title(preamble: str) -> str | None:
    for line in preamble.splitlines():
        match = TITLE_RE.match(line)
        if match:
            return match.group(1).strip() or None
    return None


def _extract_goal(sections: list[Section]) -> str | None:
    for section in sections:
        if section.name == "Goal":
            paragraphs = re.split(r"\n\s*\n", section.content.strip())
            if paragraphs and paragraphs[0].strip():
                return " ".join(line.strip() for line in paragraphs[0].splitlines()).strip() or None
            return None
    return None


def _section_index(parsed: ParsedBody, name: str) -> int:
    for index, section in enumerate(parsed.sections):
        if section.name == name:
            return index
    raise SectionNotFound(name)


def _position_index(parsed: ParsedBody, position: str) -> int:
    if position == "start":
        return 0
    if position == "end":
        return len(parsed.sections)
    if position.startswith("after:"):
        return _section_index(parsed, position.removeprefix("after:")) + 1
    if position.startswith("before:"):
        return _section_index(parsed, position.removeprefix("before:"))
    raise InvalidPosition(position)


def _line_count(text: str) -> int:
    return len(text.splitlines()) if text else 0


def _normalize_diff(value: str) -> str:
    lines = value.replace("\r\n", "\n").split("\n")
    lines = [line.rstrip() for line in lines]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)
