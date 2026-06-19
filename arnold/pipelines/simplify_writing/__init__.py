"""simplify-writing pipeline.

Fans out up to 10 DeepSeek Pro critics, each with a distinct perspective,
then asks Kimi 2.7 to revise the writing. Opens the result and loops on
user feedback, turning the feedback into new critique perspectives.

Usage:
    python -m arnold run simplify-writing path/to/draft.md
    python -m arnold run simplify-writing path/to/draft.md \
        --inputs perspectives="word choice;succinctness"
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arnold.pipelines.megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)


# ── Module-level contract fields ─────────────────────────────────────────

name: str = "simplify-writing"
description: str = (
    "Fan out DeepSeek Pro critics and a Kimi 2.7 editor to iteratively "
    "simplify a piece of writing."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ()
driver: tuple[str, str] = ("graph", "dispatch+emit")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("writing", "critique", "revision")


# ── Constants ────────────────────────────────────────────────────────────

DEFAULT_PERSPECTIVES: tuple[str, ...] = (
    "word choice and vocabulary",
    "ordering and flow of ideas",
    "sequencing and logical progression",
    "succinctness and removing redundancy",
    "clarity of purpose and main point",
    "tone and voice consistency",
    "jargon and accessibility",
    "transitions between sentences and paragraphs",
    "overall structure",
    "reader engagement and momentum",
)

_LAUNCHER_DIR = Path.home() / ".agents" / "skills" / "subagent-launcher"
_FAN_PY = _LAUNCHER_DIR / "fan.py"
_LAUNCH_HERMES_PY = _LAUNCHER_DIR / "launch_hermes_agent.py"


# ── Helpers ──────────────────────────────────────────────────────────────


def _get_perspectives(ctx: StepContext) -> tuple[str, ...]:
    """Return perspectives from inputs/state, falling back to defaults."""
    raw = ctx.inputs.get("perspectives") or ctx.state.get("perspectives") or ""
    if raw:
        parts = [p.strip() for p in re.split(r"[,;]", str(raw)) if p.strip()]
        if parts:
            return tuple(parts)
    return DEFAULT_PERSPECTIVES


def _run_subprocess(cmd: list[str], *, cwd: Path | None = None, timeout: float = 600.0) -> str:
    """Run a shell command and return stdout, raising on failure."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Subcommand failed (exit {result.returncode}):\n"
            f"cmd: {' '.join(cmd)}\n"
            f"stderr: {result.stderr[-2000:]}\n"
            f"stdout: {result.stdout[-2000:]}"
        )
    return result.stdout


def _build_critique_brief(perspective: str, text: str, word_limit: int = 800) -> str:
    return (
        f"You are a sharp, concise writing critic. Look at the following piece of "
        f"writing **only from the perspective of {perspective}** and give concrete, "
        f"actionable feedback. Be specific: quote weak spots and suggest improvements. "
        f"Keep your response under {word_limit} words.\n\n"
        f"---\n{text}\n---\n"
    )


def _build_revision_prompt(text: str, critiques: dict[str, str]) -> str:
    lines = ["You are an expert editor. Revise the following writing to make it clearer, more concise, and more compelling."]
    lines.append("You do NOT have to follow every critique blindly; use your judgment and preserve the author's intent.")
    lines.append("\n--- ORIGINAL ---\n")
    lines.append(text)
    lines.append("\n--- CRITIQUES ---\n")
    for perspective, critique in critiques.items():
        lines.append(f"\n[{perspective}]\n{critique}\n")
    lines.append("\n--- REVISED VERSION ---\n")
    return "\n".join(lines)


def _derive_perspectives_from_feedback(feedback: str, old_perspectives: tuple[str, ...]) -> tuple[str, ...]:
    """Turn user feedback into a small set of new critique perspectives."""
    # Keep a couple of defaults and add the user's feedback as a lens.
    kept = list(old_perspectives[:2]) if len(old_perspectives) >= 2 else list(DEFAULT_PERSPECTIVES[:2])
    kept.append(f"user feedback: {feedback}")
    # If the feedback mentions common issues, add targeted lenses.
    lowered = feedback.lower()
    if any(w in lowered for w in ("short", "concise", "long", "verbose")):
        kept.append("succinctness and cutting fluff")
    if any(w in lowered for w in ("clear", "confusing", "understand", "jargon")):
        kept.append("clarity and accessibility")
    if any(w in lowered for w in ("tone", "voice", "style")):
        kept.append("tone and voice")
    if any(w in lowered for w in ("structure", "order", "flow", "reorder")):
        kept.append("structure and flow")
    return tuple(dict.fromkeys(kept))  # dedupe, keep order


# ── Steps ────────────────────────────────────────────────────────────────


@dataclass
class IngestStep:
    name: str = "ingest"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        draft_path = ctx.inputs.get("draft")
        if not draft_path:
            raise ValueError("No draft provided. Pass a file path to 'arnold run simplify-writing <file>'.")
        source = Path(str(draft_path)).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Draft not found: {source}")

        working_draft = ctx.plan_dir / "current.md"
        shutil.copy2(source, working_draft)
        text = working_draft.read_text(encoding="utf-8")

        return StepResult(
            next="critique",
            state_patch={
                "current_draft_path": str(working_draft),
                "current_draft": text,
                "original_path": str(source),
                "perspectives": _get_perspectives(ctx),
                "revision_count": 0,
            },
        )


@dataclass
class CritiqueStep:
    name: str = "critique"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        text = ctx.state["current_draft"]
        perspectives = tuple(ctx.state.get("perspectives", DEFAULT_PERSPECTIVES))
        plan_dir = ctx.plan_dir

        briefs_dir = plan_dir / "critique_briefs"
        results_dir = plan_dir / "critique_results"
        briefs_dir.mkdir(parents=True, exist_ok=True)
        results_dir.mkdir(parents=True, exist_ok=True)

        # Write one brief per perspective.
        for i, perspective in enumerate(perspectives):
            brief_path = briefs_dir / f"{i:02d}_{perspective.replace(' ', '_').replace('/', '_')[:40]}.md"
            brief_path.write_text(_build_critique_brief(perspective, text), encoding="utf-8")

        if not _FAN_PY.exists():
            raise FileNotFoundError(f"fan.py not found at {_FAN_PY}")

        cmd = [
            sys.executable,
            str(_FAN_PY),
            f"--briefs-dir={briefs_dir.resolve()}",
            f"--output-dir={results_dir.resolve()}",
            "--max-workers=10",
            "--model=deepseek:deepseek-v4-pro",
            "--toolsets=file,web,terminal",
            "--task-timeout=300",
            f"--project-dir={plan_dir.resolve()}",
        ]
        _run_subprocess(cmd, timeout=900.0)

        critiques: dict[str, str] = {}
        for i, perspective in enumerate(perspectives):
            stem = f"{i:02d}_{perspective.replace(' ', '_').replace('/', '_')[:40]}"
            result_file = results_dir / f"{stem}.txt"
            if result_file.exists():
                critiques[perspective] = result_file.read_text(encoding="utf-8").strip()
            else:
                critiques[perspective] = f"[No response for {perspective}]"

        return StepResult(
            next="revise",
            state_patch={"critiques": critiques},
        )


@dataclass
class ReviseStep:
    name: str = "revise"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        text = ctx.state["current_draft"]
        critiques = ctx.state.get("critiques", {})
        plan_dir = ctx.plan_dir

        prompt = _build_revision_prompt(text, critiques)
        query_file = plan_dir / "revise_prompt.md"
        query_file.write_text(prompt, encoding="utf-8")

        if not _LAUNCH_HERMES_PY.exists():
            raise FileNotFoundError(f"launch_hermes_agent.py not found at {_LAUNCH_HERMES_PY}")

        cmd = [
            sys.executable,
            str(_LAUNCH_HERMES_PY),
            "--model=kimi:kimi-k2.7-code",
            "--toolsets=",
            f"--query-file={query_file.resolve()}",
            f"--project-dir={plan_dir.resolve()}",
        ]
        revised = _run_subprocess(cmd, timeout=600.0)

        revised_path = plan_dir / "revised.md"
        revised_path.write_text(revised, encoding="utf-8")

        count = int(ctx.state.get("revision_count", 0)) + 1
        return StepResult(
            next="open",
            state_patch={
                "current_draft": revised,
                "current_draft_path": str(revised_path),
                "revision_count": count,
            },
            outputs={"revised": str(revised_path)},
        )


@dataclass
class OpenStep:
    name: str = "open"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        path = Path(ctx.state["current_draft_path"])
        if not path.exists():
            raise FileNotFoundError(f"Revised draft missing: {path}")

        # macOS-specific open. On other platforms this step is a no-op.
        if sys.platform == "darwin":
            try:
                subprocess.run(["open", str(path)], check=False)
            except Exception as exc:  # pragma: no cover
                print(f"Could not open document: {exc}")
        else:
            print(f"Revised document written to: {path}")

        return StepResult(next="feedback")


@dataclass
class FeedbackStep:
    name: str = "feedback"
    kind: str = "decide"

    def run(self, ctx: StepContext) -> StepResult:
        path = Path(ctx.state["current_draft_path"])
        count = int(ctx.state.get("revision_count", 0))

        print(f"\n=== simplify-writing revision #{count} ===")
        print(f"Revised draft: {path}")
        print("Please review the opened document.")

        # Allow non-interactive runs to bail out gracefully.
        if os.environ.get("SIMPLIFY_WRITING_AUTO_HAPPY"):
            print("SIMPLIFY_WRITING_AUTO_HAPPY set; finishing.")
            return StepResult(next="halt")

        try:
            answer = input("Are you happy with it? (yes / no / feedback): ").strip()
        except EOFError:
            print("No input received; finishing.")
            return StepResult(next="halt")

        lowered = answer.lower()
        if lowered in ("yes", "y", "happy", "done"):
            return StepResult(next="halt")

        if not answer:
            answer = "Make it better."

        new_perspectives = _derive_perspectives_from_feedback(
            answer,
            tuple(ctx.state.get("perspectives", DEFAULT_PERSPECTIVES)),
        )
        print(f"Running another round with perspectives: {new_perspectives}")
        return StepResult(
            next="critique",
            state_patch={
                "perspectives": new_perspectives,
                "last_feedback": answer,
            },
        )


# ── Pipeline assembly ────────────────────────────────────────────────────

def build_pipeline() -> Pipeline:
    ingest_stage = Stage(
        name="ingest",
        step=IngestStep(),
        edges=(Edge(label="critique", target="critique"),),
    )
    critique_stage = Stage(
        name="critique",
        step=CritiqueStep(),
        edges=(Edge(label="revise", target="revise"),),
    )
    revise_stage = Stage(
        name="revise",
        step=ReviseStep(),
        edges=(Edge(label="open", target="open"),),
    )
    open_stage = Stage(
        name="open",
        step=OpenStep(),
        edges=(Edge(label="feedback", target="feedback"),),
    )
    feedback_stage = Stage(
        name="feedback",
        step=FeedbackStep(),
        edges=(
            Edge(label="halt", target="halt"),
            Edge(label="critique", target="critique"),
        ),
        loop_condition=lambda loop_state: int(
            getattr(loop_state, "revision_count", 0) or 0
        )
        >= 5,
    )

    return Pipeline(
        stages={
            "ingest": ingest_stage,
            "critique": critique_stage,
            "revise": revise_stage,
            "open": open_stage,
            "feedback": feedback_stage,
        },
        entry="ingest",
    )


__all__ = [
    "build_pipeline",
    "name",
    "description",
    "default_profile",
    "supported_modes",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
]
