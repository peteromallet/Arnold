"""Default editorial body and checklist templates."""

from __future__ import annotations


DEFAULT_CHECKLIST_SEED: list[str] = [
    "Validate the premise — should we be planning this at all?",
    'Clarify goal and scope — what counts as "done"',
    "Surface the non-technical critical question — is there a question (relational, organizational, ethical, legal) that matters more than any technical decision here?",
    "Identify foundational principles and major decisions — the 3–5 stances that propagate through everything",
    "Identify constraints, context, and unknowns",
    "Codebase research (when applicable) — understand existing code before designing changes",
    "Work the structural design — whatever skeleton this epic needs",
    "Work the behavioral / operational details — how it actually works in practice",
    "Scope reduction — what's the smallest valuable version?",
    "Pruning pass — within the chosen scope, cut what's overloaded",
    "Disambiguation pass — would a PM with domain context execute on this without chasing down ambiguities?",
    "Identify failure modes — what happens when things go wrong",
    "Pre-mortem — six months from now this epic didn't work; what went wrong?",
    "PM-handoff readiness test — could a project manager pick this up cold, understand the goal/approach/tradeoffs, and start breaking sprints into coder tasks without coming back with clarifying questions?",
    "Elegance pass — does this hang together as one coherent thing?",
    "Second opinion check — audit by a non-Anthropic model",
    "Decide build order / sequencing",
    "Sprint organization (final phase) — each sprint at PM-task level, not coder-task level",
]


def DEFAULT_BODY_TEMPLATE(title: str, goal: str) -> str:
    return (
        f"# {title}\n"
        "\n"
        "## Goal\n"
        "\n"
        f"{goal}\n"
        "\n"
        "## Principles\n"
        "\n"
        "- TBD\n"
        "\n"
        "## Context\n"
        "\n"
        "TBD\n"
        "\n"
        "## Key Decisions\n"
        "\n"
        "- TBD\n"
        "\n"
        "## Open Questions\n"
        "\n"
        "- TBD\n"
        "\n"
        "## Deliverable\n"
        "\n"
        "TBD\n"
    )
