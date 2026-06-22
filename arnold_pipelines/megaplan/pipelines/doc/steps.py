"""Step shells for the first-class ``doc`` pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from arnold.pipeline import StepContext
from arnold_pipelines.megaplan.step_types import StepResult


def _root_dir(ctx: StepContext) -> Path:
    """Return the pipeline root directory from either Arnold or Megaplan context.

    Arnold StepContext has ``artifact_root``; Megaplan has ``plan_dir``.
    This bridge helper keeps the doc pipeline compatible with both runtimes.
    """
    root = getattr(ctx, 'artifact_root', None)
    if root is not None:
        return Path(root)
    return getattr(ctx, 'plan_dir')  # type: ignore[no-any-return]


@dataclass(frozen=True)
class OutlineStep:
    name: str = "outline"
    kind: str = "produce"
    prompt_key: str | None = "outline_doc"
    slot: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        out = _root_dir(ctx) / "outline" / "sections.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists():
            out.write_text(json.dumps([]))
        return StepResult(outputs={"sections": out}, next="section_drafts")


@dataclass(frozen=True)
class OutlineArtifactReader:
    name: str = "outline_artifact_reader"
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    artifact_label: str = "sections"

    def run(self, ctx: StepContext) -> StepResult:
        path: Path | None = None
        if isinstance(ctx.inputs, Mapping):
            raw = ctx.inputs.get(self.artifact_label)
            if raw is not None:
                path = Path(raw)
        if path is None:
            path = _root_dir(ctx) / "outline" / "sections.json"
        if not path.exists():
            return StepResult(state_patch={"specs": []}, next="done")
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            data = []
        if not isinstance(data, list):
            data = []
        return StepResult(state_patch={"specs": list(data)}, next="done")


@dataclass(frozen=True)
class SectionDraftStep:
    name: str = "section_draft"
    kind: str = "produce"
    prompt_key: str | None = "execute_doc"
    slot: str | None = None
    section_id: str = ""
    section_title: str = ""

    def run(self, ctx: StepContext) -> StepResult:
        sid = self.section_id or "section"
        out = _root_dir(ctx) / "section_drafts" / f"{sid}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists():
            out.write_text(f"# {self.section_title or sid}\n")
        return StepResult(outputs={sid: out}, next="done")


def concat_sections_join(results: list[StepResult], ctx: StepContext) -> StepResult:
    del ctx
    merged: dict[str, Path] = {}
    for result in results:
        if isinstance(result.outputs, Mapping):
            for key, value in result.outputs.items():
                merged[key] = Path(value)
    return StepResult(outputs=merged, next="critique")


@dataclass(frozen=True)
class CritiqueStep:
    name: str = "critique"
    kind: str = "produce"
    prompt_key: str | None = "critique_doc"
    slot: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        out = _root_dir(ctx) / "critique" / "v1.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists():
            out.write_text("")
        return StepResult(outputs={"critique": out}, next="revise")


@dataclass(frozen=True)
class ReviseStep:
    name: str = "revise"
    kind: str = "produce"
    prompt_key: str | None = "revise_doc"
    slot: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        out = _root_dir(ctx) / "revise" / "v1.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists():
            out.write_text("")
        return StepResult(outputs={"revise": out}, next="assembly")


@dataclass(frozen=True)
class AssemblyStep:
    name: str = "assembly"
    kind: str = "produce"
    prompt_key: str | None = "assemble_doc"
    slot: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        out = _root_dir(ctx) / "assembly" / "final.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists():
            out.write_text("")
        return StepResult(outputs={"final": out}, next="halt")
