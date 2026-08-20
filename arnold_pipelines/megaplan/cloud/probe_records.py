"""Phase-0 verification probes, recorded as structured data.

Part of the evidence-and-restore gate (docs/runtime-and-fixer-unification-
design-20260807.md, Phase 0, "probes recorded"). The probes encode the
2026-08-07 box-census answers so the recoverability doc can embed them and
later phases can re-run them mechanically instead of re-deriving them from
prose. The five records are hard-coded census findings; nothing here probes
the live box at import time.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Sequence

#: Allowed values for :attr:`ProbeRecord.method`.
PROBE_METHODS: tuple[str, ...] = ("census", "code-inventory", "code", "manual")


@dataclass(frozen=True)
class ProbeRecord:
    """One verification probe and its recorded answer."""

    id: str
    title: str
    question: str
    answer: str
    evidence: list[str]
    verified_at: str
    method: str

    def __post_init__(self) -> None:
        if self.method not in PROBE_METHODS:
            raise ValueError(f"probe {self.id!r}: unknown method {self.method!r}")
        if not (
            self.id
            and self.title
            and self.question
            and self.answer
            and self.evidence
            and self.verified_at
        ):
            raise ValueError(f"probe {self.id!r}: empty required field")


#: The five Phase-0 verification probes (census answers, 2026-08-07).
VERIFICATION_PROBES: tuple[ProbeRecord, ...] = (
    ProbeRecord(
        id="probe-1",
        title="Box trees wire repair_lock.py",
        question="Do the box trees wire repair_lock.py?",
        answer="YES — repair_lock.py is present in both box runtime trees and "
        "used by the watchdog / repair-trigger paths (cloud.repair_lock).",
        evidence=[
            "arnold_pipelines/megaplan/cloud/repair_lock.py present in runtime tree "
            "arnold-r7-fresh-child-20260805",
            "repair_lock.py present in the -live runtime tree "
            "(arnold-r7-fresh-child-20260805-live)",
            "watchdog and repair-trigger paths use cloud.repair_lock",
        ],
        verified_at="2026-08-07",
        method="census",
    ),
    ProbeRecord(
        id="probe-2",
        title="Both fixer flows register in one marker store",
        question="Do the two fixer flows register active in the SAME marker store?",
        answer="NO — the reactive and the proactive (hourly superfixer) flows "
        "use different store roots; not proven shared.",
        evidence=[
            "reactive flow markers: /workspace/.megaplan/cloud-sessions (+ repair-data)",
            "proactive flow (hourly superfixer) schedule store: "
            "/workspace/arnold/.megaplan/resident (store-root)",
            "proactive also touches /workspace/.megaplan/ops/schedules and schedule-inputs",
            "different roots observed; no shared marker store proven",
        ],
        verified_at="2026-08-07",
        method="census",
    ),
    ProbeRecord(
        id="probe-3",
        title="Hourly superfixer renders policy through fixer_prompt_policy.py",
        question="Does the hourly superfixer render policy through fixer_prompt_policy.py?",
        answer="NO — fixer_prompt_policy.py is used only by the reactive flow; "
        "zero hits in the resident / subagent / worker paths.",
        evidence=[
            "arnold_pipelines/megaplan/cloud/meta_repair.py:42-45 uses fixer_prompt_policy",
            "zero fixer_prompt_policy references in resident / subagent / worker paths",
        ],
        verified_at="2026-08-07",
        method="code-inventory",
    ),
    ProbeRecord(
        id="probe-4",
        title="Schedule-store non-live refs are the only must-not-GC candidates",
        question="Which schedule-store-referenced trees must not be GC'd, and "
        "are they the only such candidates?",
        answer="YES — exactly four candidate trees are referenced by the "
        "schedule store; all four are must-not-GC candidates.",
        evidence=[
            "arnold-2bd0b2d3450 (dirty=12)",
            "arnold-6ce6d4eb487 (branch repair/runtime-successor-20260724, dirty=2)",
            "arnold-74b4e6b992 (HEAD 972e78a1dd, dirty=2)",
            "arnold-bc0c600c41 (branch megaplan/custody-control-plane/"
            "m10-safe-retry-recovery-and-effects, dirty=23)",
        ],
        verified_at="2026-08-07",
        method="census",
    ),
    ProbeRecord(
        id="probe-5",
        title="Live concurrency and per-epic environment size",
        question="How many concurrent epics does the box actually run, and what "
        "is the real per-epic environment size?",
        answer="2 running containers with 2 distinct live runtime trees; "
        "per-runtime env ≈ 2.2G; 114 candidate trees ≈ 57G total.",
        evidence=[
            "running containers: megaplan-cloud-agent-resident-only, "
            "megaplan-cloud-agent-critique-ledger-v3",
            "distinct runtime trees with live PIDs: arnold-r7-fresh-child-20260805 "
            "and its -live tree; /workspace/arnold is the data root",
            "per-runtime env size ≈ 2.2G (tree ≈ 975M-998M + venv ≈ 1.2G at "
            "/workspace/runtime-venvs/)",
            "114 candidate trees ≈ 57G total",
        ],
        verified_at="2026-08-07",
        method="census",
    ),
)


def render_probes_markdown(
    probes: Sequence[ProbeRecord] = VERIFICATION_PROBES,
) -> str:
    """Render the probes as deterministic markdown (summary table + sections).

    Deterministic: records are emitted in ``id`` order and no wall-clock
    timestamps or other volatile state enters the output.
    """
    ordered = sorted(probes, key=lambda p: p.id)
    lines: list[str] = [
        "# Verification probes (Phase 0 census, 2026-08-07)",
        "",
        "| id | title | answer | method |",
        "|---|---|---|---|",
    ]
    for probe in ordered:
        answer_flat = " ".join(probe.answer.split())
        lines.append(f"| {probe.id} | {probe.title} | {answer_flat} | {probe.method} |")
    lines.append("")
    for probe in ordered:
        lines.extend(
            [
                f"## {probe.id} — {probe.title}",
                "",
                f"**Question:** {probe.question}",
                f"**Answer:** {probe.answer}",
                f"**Method:** {probe.method}",
                f"**Verified at:** {probe.verified_at}",
                "",
                "**Evidence:**",
                "",
            ]
        )
        lines.extend(f"- {item}" for item in probe.evidence)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: print the probes as markdown; exit 0.

    Usage: ``python -m arnold_pipelines.megaplan.cloud.probe_records``
    """
    del argv
    sys.stdout.write(render_probes_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
