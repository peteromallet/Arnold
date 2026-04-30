"""Markdown body parsing and section-level editing helpers."""

from __future__ import annotations

from dataclasses import dataclass, replace
import difflib
import re


HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
ANY_SECTION_HEADING_RE = re.compile(r"^(#{2,6})\s+(.+?)\s*$")
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
    section_spans = _section_line_spans(body_text)
    return {
        "title": parsed.title,
        "goal": parsed.goal_first_paragraph,
        "total_lines": _line_count(body_text),
        "sections": [
            {
                "name": section.name,
                "line_count": _line_count(section.raw),
                "line_start": span["line_start"],
                "line_end": span["line_end"],
                "subheadings": _nested_subheadings(
                    section_spans,
                    span["line_start"],
                    span["line_end"],
                ),
            }
            for section, span in zip(parsed.sections, section_spans)
        ],
    }


def search(parsed: ParsedBody, query: str, context_lines: int = 2) -> dict[str, object]:
    body_text = serialize(parsed)
    needle = str(query or "").casefold()
    context_size = max(int(context_lines), 0)
    lines = body_text.splitlines()
    section_spans = _section_line_spans(body_text)
    results: list[dict[str, object]] = []
    if not needle:
        return {"query": query, "results": []}

    for index, line in enumerate(lines):
        if needle not in line.casefold():
            continue
        line_number = index + 1
        start = max(0, index - context_size)
        end = min(len(lines), index + context_size + 1)
        results.append(
            {
                "line_number": line_number,
                "line": line,
                "section": _section_name_for_line(section_spans, line_number),
                "subheading_path": _subheading_path_for_line(section_spans, line_number),
                "context_before": [
                    {"line_number": item + 1, "line": lines[item]}
                    for item in range(start, index)
                ],
                "context_after": [
                    {"line_number": item + 1, "line": lines[item]}
                    for item in range(index + 1, end)
                ],
            }
        )
    return {"query": query, "results": results}


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


def _section_line_spans(text: str) -> list[dict[str, object]]:
    headings = _heading_infos(text)
    top_level = [heading for heading in headings if heading["level"] == 2]
    spans: list[dict[str, object]] = []
    total_lines = _line_count(text)
    for index, heading in enumerate(top_level):
        next_start = (
            int(top_level[index + 1]["line_number"])
            if index + 1 < len(top_level)
            else total_lines + 1
        )
        spans.append(
            {
                "name": heading["name"],
                "line_start": heading["line_number"],
                "line_end": max(int(heading["line_number"]), next_start - 1),
                "headings": [
                    item
                    for item in headings
                    if int(heading["line_number"]) <= int(item["line_number"]) < next_start
                ],
            }
        )
    return spans


def _nested_subheadings(
    section_spans: list[dict[str, object]],
    line_start: object,
    line_end: object,
) -> list[dict[str, object]]:
    section = next(
        (
            span
            for span in section_spans
            if span["line_start"] == line_start and span["line_end"] == line_end
        ),
        None,
    )
    if not section:
        return []
    headings = [
        dict(item)
        for item in section["headings"]  # type: ignore[index]
        if int(item["level"]) > 2
    ]
    for index, heading in enumerate(headings):
        next_line = int(line_end) + 1
        for candidate in headings[index + 1 :]:
            if int(candidate["level"]) <= int(heading["level"]):
                next_line = int(candidate["line_number"])
                break
        heading["line_count"] = max(1, next_line - int(heading["line_number"]))
        heading["children"] = []

    roots: list[dict[str, object]] = []
    stack: list[dict[str, object]] = []
    for heading in headings:
        while stack and int(stack[-1]["level"]) >= int(heading["level"]):
            stack.pop()
        if stack:
            stack[-1]["children"].append(heading)  # type: ignore[index, union-attr]
        else:
            roots.append(heading)
        stack.append(heading)
    return roots


def _heading_infos(text: str) -> list[dict[str, object]]:
    headings: list[dict[str, object]] = []
    fence: str | None = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if fence:
            if stripped.startswith(fence):
                fence = None
            continue
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            fence = fence_match.group(1)
            continue
        match = ANY_SECTION_HEADING_RE.match(line)
        if not match:
            continue
        headings.append(
            {
                "level": len(match.group(1)),
                "name": match.group(2).strip(),
                "line_number": line_number,
            }
        )
    return headings


def _section_name_for_line(section_spans: list[dict[str, object]], line_number: int) -> str:
    for section in section_spans:
        if int(section["line_start"]) <= line_number <= int(section["line_end"]):
            return str(section["name"])
    return _PREAMBLE


def _subheading_path_for_line(section_spans: list[dict[str, object]], line_number: int) -> list[str]:
    for section in section_spans:
        if not (int(section["line_start"]) <= line_number <= int(section["line_end"])):
            continue
        path: list[str] = []
        for heading in section["headings"]:  # type: ignore[index]
            if int(heading["level"]) <= 2 or int(heading["line_number"]) > line_number:
                continue
            while len(path) >= int(heading["level"]) - 2:
                path.pop()
            path.append(str(heading["name"]))
        return path
    return []


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
