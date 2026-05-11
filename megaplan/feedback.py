"""External user feedback for completed megaplan runs.

A `feedback.md` file lives in each plan directory and is owned by the user:
they fill in per-stage ratings (0-10) and optional comments after a run
finishes. Megaplan only scaffolds the template and parses it back on load —
it never overwrites user edits.

Old plans without a feedback file simply have ``Plan.feedback`` set to None;
running ``megaplan feedback <plan>`` scaffolds the template on demand.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

FEEDBACK_FILENAME = "feedback.md"

# Canonical workflow stages in pipeline order. Mirrors the transitions in
# megaplan/_core/workflow.py; "overall" is rendered separately at the top.
STAGES: tuple[str, ...] = (
    "prep",
    "plan",
    "critique",
    "revise",
    "gate",
    "tiebreaker",
    "finalize",
    "execute",
    "review",
)

_STAGE_BLURBS: dict[str, str] = {
    "prep": "Pre-plan research / scoping",
    "plan": "Initial plan generation",
    "critique": "Parallel critique passes",
    "revise": "Plan revisions in response to critique",
    "gate": "Quality gate decision",
    "tiebreaker": "Tiebreaker orchestration when gates disagreed",
    "finalize": "Final plan consolidation",
    "execute": "Implementation by the executor",
    "review": "Post-execution review",
}


@dataclass
class StageFeedback:
    rating: int | None = None
    comment: str | None = None

    def is_empty(self) -> bool:
        return self.rating is None and not (self.comment and self.comment.strip())


@dataclass
class PlanFeedback:
    overall: StageFeedback = field(default_factory=StageFeedback)
    stages: dict[str, StageFeedback] = field(default_factory=dict)

    def to_dict(self) -> dict[str, dict[str, int | str | None]]:
        def _one(sf: StageFeedback) -> dict[str, int | str | None]:
            return {"rating": sf.rating, "comment": sf.comment}

        return {
            "overall": _one(self.overall),
            "stages": {name: _one(sf) for name, sf in self.stages.items()},
        }

    def is_empty(self) -> bool:
        return self.overall.is_empty() and all(sf.is_empty() for sf in self.stages.values())


def feedback_path(plan_dir: Path) -> Path:
    return Path(plan_dir) / FEEDBACK_FILENAME


def render_template(plan_name: str, *, idea: str | None = None) -> str:
    """Render a fresh feedback.md template with all stage fields blank."""

    lines: list[str] = [
        f"# Feedback for plan: {plan_name}",
        "",
        "Fill in any fields you want — leave the rest blank. `rating:` is",
        "an integer 0–10 (or blank). `comment:` is free text and may span",
        "multiple lines (everything until the next `##` heading is the",
        "comment body).",
        "",
    ]
    if idea:
        lines.extend([f"> {idea.strip()}", ""])

    lines.extend(
        [
            "## Overall",
            "",
            "rating:",
            "comment:",
            "",
        ]
    )

    for stage in STAGES:
        blurb = _STAGE_BLURBS.get(stage, "")
        heading = f"## {stage}"
        if blurb:
            heading = f"{heading}  <!-- {blurb} -->"
        lines.extend([heading, "", "rating:", "comment:", ""])

    return "\n".join(lines).rstrip() + "\n"


_HEADING_RE = re.compile(r"^##\s+(\S+)", re.MULTILINE)
_RATING_RE = re.compile(r"^rating\s*:\s*(.*?)\s*$", re.IGNORECASE | re.MULTILINE)


def _parse_rating(raw: str) -> int | None:
    raw = raw.strip()
    if not raw:
        return None
    # Accept "8", "8/10", "8 out of 10"
    match = re.match(r"^(-?\d+)", raw)
    if not match:
        return None
    try:
        value = int(match.group(1))
    except ValueError:
        return None
    if value < 0 or value > 10:
        return None
    return value


def _parse_section(body: str) -> StageFeedback:
    """Parse the body under a single `## <name>` heading."""

    rating: int | None = None
    rating_match = _RATING_RE.search(body)
    rating_end = 0
    if rating_match is not None:
        rating = _parse_rating(rating_match.group(1))
        rating_end = rating_match.end()

    # Comment: everything after `comment:` until end of section. If `comment:`
    # is missing, treat the section as no comment.
    comment: str | None = None
    comment_match = re.search(
        r"^comment\s*:\s*(.*)$",
        body[rating_end:],
        re.IGNORECASE | re.MULTILINE,
    )
    if comment_match is not None:
        first_line = comment_match.group(1).strip()
        rest_start = rating_end + comment_match.end()
        rest = body[rest_start:].strip("\n")
        parts: list[str] = []
        if first_line:
            parts.append(first_line)
        if rest:
            parts.append(rest)
        joined = "\n".join(parts).strip()
        comment = joined or None

    return StageFeedback(rating=rating, comment=comment)


def parse_feedback(text: str) -> PlanFeedback:
    """Parse a feedback.md document. Unknown headings are kept under stages."""

    fb = PlanFeedback()
    # Split on `## <heading>` lines while keeping the body that follows each.
    parts = re.split(r"^##\s+(\S+).*$", text, flags=re.MULTILINE)
    # parts == [preamble, name1, body1, name2, body2, ...]
    for i in range(1, len(parts), 2):
        name = parts[i].strip().lower()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        section = _parse_section(body)
        if section.is_empty():
            continue
        if name == "overall":
            fb.overall = section
        else:
            fb.stages[name] = section
    return fb


def load_feedback(plan_dir: Path) -> PlanFeedback | None:
    """Read and parse feedback.md from a plan directory, if it exists."""

    path = feedback_path(plan_dir)
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    fb = parse_feedback(text)
    return fb if not fb.is_empty() else PlanFeedback()


def format_summary(fb: PlanFeedback) -> str:
    """Render a short human-readable summary of parsed feedback."""

    lines: list[str] = []

    def _fmt(name: str, sf: StageFeedback) -> None:
        rating = f"{sf.rating}/10" if sf.rating is not None else "—"
        lines.append(f"  {name:<10} {rating}")
        if sf.comment:
            for cline in sf.comment.splitlines():
                lines.append(f"             {cline}")

    lines.append("Overall:")
    _fmt("rating", fb.overall)
    if fb.stages:
        lines.append("")
        lines.append("Stages:")
        for stage in STAGES:
            if stage in fb.stages:
                _fmt(stage, fb.stages[stage])
        # Any non-canonical stage names the user added
        extras = sorted(k for k in fb.stages if k not in STAGES)
        for stage in extras:
            _fmt(stage, fb.stages[stage])
    return "\n".join(lines) + "\n"
