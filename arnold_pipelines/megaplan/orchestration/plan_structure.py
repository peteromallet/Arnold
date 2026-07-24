"""Plan-structure parsing and validation helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass


PLAN_STRUCTURE_REQUIRED_STEP_ISSUE = "Plan must include at least one step section (`## Step N:` or `### Step N:` under a phase)."
_PLAN_HEADING_RE = re.compile(r"^##\s+.+$")
_PLAN_PHASE_HEADING_RE = re.compile(r"^###\s+.+$")
_PLAN_STEP_RE = re.compile(r"^##\s+Step\s+(\d+):\s+.+$")
_PLAN_PHASE_STEP_RE = re.compile(r"^###\s+Step\s+(\d+):\s+.+$")


@dataclass(frozen=True)
class PlanSection:
    heading: str
    body: str
    id: str | None
    start_line: int
    end_line: int


def _strip_fenced_blocks(text: str) -> str:
    kept_lines: list[str] = []
    inside_fence = False
    for line in text.splitlines(keepends=True):
        if line.startswith("```"):
            inside_fence = not inside_fence
            continue
        if not inside_fence:
            kept_lines.append(line)
    if inside_fence:
        return text
    return "".join(kept_lines)


def _match_section_boundary(line: str) -> tuple[bool, str | None]:
    step_match = _PLAN_STEP_RE.match(line) or _PLAN_PHASE_STEP_RE.match(line)
    if step_match:
        return True, f"S{step_match.group(1)}"
    if _PLAN_HEADING_RE.match(line) or _PLAN_PHASE_HEADING_RE.match(line):
        return True, None
    return False, None


def parse_plan_sections(plan_text: str) -> list[PlanSection]:
    lines = plan_text.splitlines(keepends=True)
    if not lines:
        return [PlanSection(heading="", body="", id=None, start_line=1, end_line=0)]

    boundaries: list[tuple[int, int, str, str | None]] = []
    inside_fence = False
    for index, line in enumerate(lines):
        if line.startswith("```"):
            inside_fence = not inside_fence
            continue
        if inside_fence:
            continue
        is_boundary, section_id = _match_section_boundary(line)
        if is_boundary:
            boundaries.append((index, index + 1, line.rstrip("\n"), section_id))

    if inside_fence:
        boundaries = []
        for index, line in enumerate(lines):
            is_boundary, section_id = _match_section_boundary(line)
            if is_boundary:
                boundaries.append((index, index + 1, line.rstrip("\n"), section_id))

    if not boundaries:
        return [PlanSection(heading="", body=plan_text, id=None, start_line=1, end_line=len(lines))]

    sections: list[PlanSection] = []
    first_index, first_line, _, _ = boundaries[0]
    if first_index > 0:
        sections.append(
            PlanSection(
                heading="",
                body="".join(lines[:first_index]),
                id=None,
                start_line=1,
                end_line=first_line - 1,
            )
        )

    for boundary_index, (start_index, start_line, heading, section_id) in enumerate(boundaries):
        next_start_index = boundaries[boundary_index + 1][0] if boundary_index + 1 < len(boundaries) else len(lines)
        sections.append(
            PlanSection(
                heading=heading,
                body="".join(lines[start_index:next_start_index]),
                id=section_id,
                start_line=start_line,
                end_line=next_start_index,
            )
        )
    return sections


def reassemble_plan(sections: list[PlanSection]) -> str:
    return "".join(section.body for section in sections)


def renumber_steps(sections: list[PlanSection]) -> list[PlanSection]:
    renumbered: list[PlanSection] = []
    step_number = 1
    for section in sections:
        if section.id is None:
            renumbered.append(section)
            continue
        step_prefix_match = re.match(r"^(#{2,3})\s+Step\s+\d+:", section.heading)
        if not step_prefix_match:
            renumbered.append(section)
            continue
        hashes = step_prefix_match.group(1)
        new_heading = re.sub(rf"^{hashes}\s+Step\s+\d+:", f"{hashes} Step {step_number}:", section.heading, count=1)
        new_body = re.sub(rf"^{hashes}\s+Step\s+\d+:", f"{hashes} Step {step_number}:", section.body, count=1, flags=re.MULTILINE)
        renumbered.append(
            PlanSection(
                heading=new_heading,
                body=new_body,
                id=f"S{step_number}",
                start_line=section.start_line,
                end_line=section.end_line,
            )
        )
        step_number += 1
    return renumbered


def validate_plan_structure(plan_text: str) -> list[str]:
    issues: list[str] = []
    stripped = _strip_fenced_blocks(plan_text)

    if len(re.findall(r"(?mi)^#\s+.+$", stripped)) != 1:
        issues.append("Plan should have exactly one H1 title.")
    if not re.search(r"(?mi)^##\s+Overview\s*$", stripped):
        issues.append("Plan should include a `## Overview` section.")

    step_matches = list(re.finditer(r"(?im)^#{2,3}\s+Step\s+\d+:\s+.+$", stripped))
    if not step_matches:
        issues.append(PLAN_STRUCTURE_REQUIRED_STEP_ISSUE)
        return issues

    if not (
        re.search(r"(?mi)^##\s+Execution Order\s*$", stripped)
        or re.search(r"(?mi)^##\s+Validation Order\s*$", stripped)
    ):
        issues.append("Plan should include `## Execution Order` or `## Validation Order`.")

    missing_substeps = False
    missing_file_refs = False
    for match in step_matches:
        start = match.end()
        next_heading = re.search(r"(?im)^#{2,3}\s+.+$", stripped[start:])
        end = start + next_heading.start() if next_heading else len(stripped)
        section = stripped[match.start():end]
        if not re.search(r"(?m)^\d+\.\s+", stripped[start:end]):
            missing_substeps = True
        if not re.search(r"`[^`]+`", section):
            missing_file_refs = True

    if missing_substeps:
        issues.append("Each step section should include at least one numbered substep.")
    if missing_file_refs:
        issues.append("Each step section should reference at least one file in backticks.")
    return issues
