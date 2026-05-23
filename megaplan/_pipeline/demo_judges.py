"""Hermetic fan-out judges demo for the megaplan ``_pipeline`` package.

Three deterministic 'rubric' judges (no model calls, no network, no env-var
reads, no imports of ``key_pool`` / Hermes / Claude / Codex modules) score a
fixture document in parallel under a :class:`ParallelStage`. A synthesize
:class:`Stage` then merges the three verdicts into a templated markdown
report.

Final artifact set under ``artifact_root`` is EXACTLY:

    judges/judge_clarity/verdict.json
    judges/judge_concreteness/verdict.json
    judges/judge_brevity/verdict.json
    synthesis/synthesis.md
    state.json   # written by the executor after each stage

The :class:`ParallelStage` ``join`` deliberately writes NO aggregate file
(eliminates extra-artifact ambiguity vs. the brief's literal 3+1 count).
The synthesize Step locates the three judge verdicts via
``StepResult.outputs['verdict']`` from each judge, passed through the
state patch emitted by the ``judges`` join.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
    Verdict,
)


_DEFAULT_FIXTURE = """\
The pipeline executor walks stages and dispatches steps in order.
Each step writes artifacts under the plan directory it was handed.
Judges score the fixture document along independent rubric axes.
The synthesis stage merges every judge verdict into a single report.
Sprint One freezes the dataclass shapes for downstream Sprint Two ports.
"""


_CLARITY_STDEV_THRESHOLD = 10.0
_BREVITY_TARGET_WORDS = 200


def _read_doc(ctx: StepContext) -> str:
    return Path(ctx.inputs["doc"]).read_text()


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]


def _write_verdict(
    ctx: StepContext, judge_name: str, score: float, detail: dict[str, Any]
) -> Path:
    verdict_path = Path(ctx.plan_dir) / "judges" / judge_name / "verdict.json"
    verdict_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"judge": judge_name, "score": float(score)}
    payload.update(detail)
    verdict_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return verdict_path


class JudgeClarity:
    """Deterministic clarity judge: lower sentence-length variance scores higher."""

    name = "judge_clarity"
    kind = "judge"
    prompt_key = None
    slot = None

    def run(self, ctx: StepContext) -> StepResult:
        sentences = _split_sentences(_read_doc(ctx))
        lengths = [len(s.split()) for s in sentences]
        if len(lengths) < 2:
            stdev_val = 0.0
            score = 1.0
        else:
            stdev_val = statistics.stdev(lengths)
            score = 1.0 - min(1.0, stdev_val / _CLARITY_STDEV_THRESHOLD)
        verdict_path = _write_verdict(
            ctx,
            self.name,
            score,
            {"sentence_count": len(lengths), "stdev": stdev_val},
        )
        return StepResult(
            outputs={"verdict": verdict_path},
            verdict=Verdict(score=float(score), payload={"judge": self.name}),
            next="done",
        )


class JudgeConcreteness:
    """Deterministic concreteness judge: ratio of capitalized words."""

    name = "judge_concreteness"
    kind = "judge"
    prompt_key = None
    slot = None

    def run(self, ctx: StepContext) -> StepResult:
        text = _read_doc(ctx)
        words = re.findall(r"[A-Za-z]+", text)
        if not words:
            ratio = 0.0
        else:
            capitalized = sum(1 for w in words if w[:1].isupper())
            ratio = capitalized / len(words)
        score = float(min(1.0, ratio))
        verdict_path = _write_verdict(
            ctx, self.name, score, {"word_count": len(words)}
        )
        return StepResult(
            outputs={"verdict": verdict_path},
            verdict=Verdict(score=score, payload={"judge": self.name}),
            next="done",
        )


class JudgeBrevity:
    """Deterministic brevity judge: ``min(1.0, target_words / word_count)``."""

    name = "judge_brevity"
    kind = "judge"
    prompt_key = None
    slot = None

    target_words: int = _BREVITY_TARGET_WORDS

    def run(self, ctx: StepContext) -> StepResult:
        text = _read_doc(ctx)
        word_count = len(text.split())
        score = min(1.0, self.target_words / max(1, word_count))
        verdict_path = _write_verdict(
            ctx,
            self.name,
            score,
            {"word_count": word_count, "target_words": self.target_words},
        )
        return StepResult(
            outputs={"verdict": verdict_path},
            verdict=Verdict(score=float(score), payload={"judge": self.name}),
            next="done",
        )


def _join_judges(results: list[StepResult], ctx: StepContext) -> StepResult:
    """Barrier-join for the judges fan-out. Writes NO aggregate file."""

    judges: dict[str, float] = {}
    paths: list[str] = []
    scores: list[float] = []
    for r in results:
        verdict_path = r.outputs["verdict"]
        name: str | None = None
        if r.verdict is not None:
            payload = r.verdict.payload
            if isinstance(payload, dict):
                value = payload.get("judge")
                if isinstance(value, str):
                    name = value
        if name is None:
            name = Path(verdict_path).parent.name
        score = float(r.verdict.score) if r.verdict is not None else 0.0
        judges[name] = score
        scores.append(score)
        paths.append(str(verdict_path))
    mean = sum(scores) / len(scores) if scores else 0.0
    return StepResult(
        outputs={},
        verdict=Verdict(score=mean),
        next="to_synthesis",
        state_patch={"judges": judges, "judge_verdict_paths": paths},
    )


class Synthesize:
    """Merges the three judge verdicts into a templated markdown report."""

    name = "synthesize"
    kind = "produce"
    prompt_key = None
    slot = None

    def run(self, ctx: StepContext) -> StepResult:
        raw_paths = ctx.state.get("judge_verdict_paths", [])
        verdict_paths = [Path(path) for path in raw_paths]
        scores: dict[str, float] = {}
        lines: list[str] = ["# Synthesis", ""]
        for vpath in verdict_paths:
            data = json.loads(vpath.read_text())
            judge_name = str(data.get("judge") or vpath.parent.name)
            score = float(data.get("score", 0.0))
            scores[judge_name] = score
            lines.append(f"- **{judge_name}**: {score:.4f}")
        mean = sum(scores.values()) / len(scores) if scores else 0.0
        lines.extend(
            [
                "",
                f"**Aggregate (mean of {len(scores)} judges):** {mean:.4f}",
                "",
            ]
        )
        out_path = Path(ctx.plan_dir) / "synthesis" / "synthesis.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines))
        return StepResult(outputs={"synthesis": out_path}, next="done")


def build_pipeline() -> Pipeline:
    """Build the ``judges -> synthesis`` pipeline used by :func:`run_demo`."""

    judge_clarity = JudgeClarity()
    judge_concreteness = JudgeConcreteness()
    judge_brevity = JudgeBrevity()
    synthesize = Synthesize()
    stages: dict[str, Stage | ParallelStage] = {
        "judges": ParallelStage(
            name="judges",
            steps=(judge_clarity, judge_concreteness, judge_brevity),
            join=_join_judges,
            edges=(Edge("to_synthesis", "synthesis"),),
        ),
        "synthesis": Stage(
            name="synthesis",
            step=synthesize,
            edges=(Edge("done", "halt"),),
        ),
    }
    return Pipeline(stages=stages, entry="judges")


def run_demo(fixture_path: Path, artifact_root: Path) -> dict[str, Any]:
    """Run the fan-out judges demo on ``fixture_path`` under ``artifact_root``."""

    fixture_path = Path(fixture_path)
    artifact_root = Path(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)
    pipeline = build_pipeline()
    ctx = StepContext(
        plan_dir=artifact_root,
        state={},
        profile=None,
        mode="demo",
        inputs={"doc": fixture_path},
        budget=None,
    )
    return run_pipeline(pipeline, ctx, artifact_root=artifact_root)


def _default_fixture_path() -> Path:
    tmp_dir = Path(tempfile.mkdtemp(prefix="demo_judges_fixture_"))
    fixture = tmp_dir / "fixture.md"
    fixture.write_text(_DEFAULT_FIXTURE)
    return fixture


if __name__ == "__main__":
    artifact_root = Path(".megaplan/demos/judges") / datetime.now().strftime(
        "%Y%m%dT%H%M%S"
    )
    if len(sys.argv) > 1:
        fixture_path = Path(sys.argv[1])
    else:
        fixture_path = _default_fixture_path()
    result = run_demo(fixture_path, artifact_root)
    print(
        json.dumps(
            {
                "artifact_root": str(artifact_root),
                "final_stage": result.get("final_stage"),
                "state": result.get("state"),
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
