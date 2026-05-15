"""3× critique → revise loop on a document, built on the Sprint-1 primitives.

Sprint 2 secondary demo. Hermetic — no network, no model calls, no
imports of ``key_pool`` / Hermes / Claude / Codex modules.

The loop is expressed as a backwards edge under a gate condition, exactly
as the brief specifies (loops are not a primitive — they fall out of
labelled edges):

    critique ──to_revise──▶ revise ──to_critique──▶ critique
    critique ──to_done──▶ halt   (when state['critique_iter'] >= max_iter)

A trivial rubric-based critic counts uppercase letters and short sentences
and emits a verdict; the reviser appends a "Revision pass N" line to the
document and writes a new version. The gate decision is encoded directly
in the critic's returned ``next`` label so we don't need a separate Decide
step for the demo. (Sprint 2's real planning port keeps Decide as a
distinct primitive.)
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
    Verdict,
)


_DEFAULT_FIXTURE = """\
This document describes the doc-critique demo loop. The critic reads the
current document version and emits a deterministic verdict. The reviser
then appends a revision pass marker to produce the next version. The
loop terminates after three iterations.
"""

_MAX_ITER = 3


def _current_doc_path(ctx: StepContext) -> Path:
    state = ctx.state if isinstance(ctx.state, dict) else {}
    iteration = state.get("critique_iter", 0)
    if iteration == 0:
        return Path(ctx.inputs["doc"])
    return Path(ctx.plan_dir) / "doc_versions" / f"doc_v{iteration}.md"


class DocCritic:
    name = "critique"
    kind = "judge"
    prompt_key = None
    slot = None

    def run(self, ctx: StepContext) -> StepResult:
        state = dict(ctx.state) if isinstance(ctx.state, dict) else {}
        iteration = int(state.get("critique_iter", 0))

        doc_path = _current_doc_path(ctx)
        body = doc_path.read_text() if doc_path.exists() else ""

        sentences = [s for s in body.replace("\n", " ").split(".") if s.strip()]
        short = sum(1 for s in sentences if len(s.split()) < 6)
        upper = sum(1 for w in body.split() if w.isupper())
        score = max(0.0, 1.0 - (short + upper) / max(1, len(sentences)))

        critique_dir = Path(ctx.plan_dir) / "critique_versions"
        critique_dir.mkdir(parents=True, exist_ok=True)
        out_path = critique_dir / f"critique_v{iteration + 1}.json"
        out_path.write_text(
            json.dumps(
                {
                    "iteration": iteration + 1,
                    "score": score,
                    "flags": [f"short:{short}", f"upper:{upper}"],
                    "doc_read": str(doc_path),
                },
                indent=2,
            )
        )

        verdict = Verdict(
            score=score,
            flags=(f"short:{short}", f"upper:{upper}"),
            payload={"iteration": iteration + 1},
        )

        next_label = "to_revise" if iteration + 1 < _MAX_ITER else "to_done"
        return StepResult(
            outputs={"critique": out_path},
            verdict=verdict,
            next=next_label,
            state_patch={"critique_iter": iteration + 1, "last_score": score},
        )


class DocReviser:
    name = "revise"
    kind = "produce"
    prompt_key = None
    slot = None

    def run(self, ctx: StepContext) -> StepResult:
        state = dict(ctx.state) if isinstance(ctx.state, dict) else {}
        iteration = int(state.get("critique_iter", 0))

        prev_path = _current_doc_path(ctx)
        prev_body = prev_path.read_text() if prev_path.exists() else ""
        next_body = prev_body.rstrip() + f"\n\nRevision pass {iteration}: edits applied.\n"

        versions_dir = Path(ctx.plan_dir) / "doc_versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        new_path = versions_dir / f"doc_v{iteration}.md"
        new_path.write_text(next_body)

        return StepResult(
            outputs={"doc": new_path},
            next="to_critique",
            state_patch={"latest_doc": str(new_path)},
        )


def build_pipeline() -> Pipeline:
    critique = DocCritic()
    revise = DocReviser()
    stages: dict[str, Stage] = {
        "critique": Stage(
            name="critique",
            step=critique,
            edges=(
                Edge("to_revise", "revise"),
                Edge("to_done", "halt"),
            ),
        ),
        "revise": Stage(
            name="revise",
            step=revise,
            edges=(Edge("to_critique", "critique"),),
        ),
    }
    return Pipeline(stages=stages, entry="critique")


def run_demo(fixture_path: Path, artifact_root: Path) -> dict[str, Any]:
    fixture_path = Path(fixture_path)
    artifact_root = Path(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)

    pipeline = build_pipeline()
    ctx = StepContext(
        plan_dir=artifact_root,
        state={"critique_iter": 0},
        profile=None,
        mode="demo",
        inputs={"doc": fixture_path},
        budget=None,
    )
    return run_pipeline(pipeline, ctx, artifact_root=artifact_root)


def _default_fixture_path() -> Path:
    tmp_dir = Path(tempfile.mkdtemp(prefix="doc_critique_fixture_"))
    fixture = tmp_dir / "fixture.md"
    fixture.write_text(_DEFAULT_FIXTURE)
    return fixture


if __name__ == "__main__":
    import sys

    artifact_root = Path(".megaplan/demos/doc_critique") / datetime.now().strftime(
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
                "iterations": result.get("state", {}).get("critique_iter"),
            },
            indent=2,
        )
    )
