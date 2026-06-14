"""3× critique → revise loop on a document, built on the Sprint-1 primitives.

Sprint 2 secondary demo, refined in Sprint 3 to demonstrate the
elegantly-composable architecture:

- **Loops fall out of edges.** ``critique → revise → critique``
  (backwards edge) plus ``critique → halt`` (under a max-iter gate
  condition encoded in the next-label) — no new combinator.
- **Prompts are pluggable per mode** via
  :mod:`megaplan._pipeline.prompts`. ``mode="doc"`` resolves a
  documentation-reviewer prompt; ``mode="joke"`` resolves a punch-up
  prompt — same Step, different output.
- **Critic ↔ reviser interact via typed PipelineVerdict.** The critic returns
  a :class:`PipelineVerdict` whose ``flags`` tuple carries structured issue
  identifiers; the reviser reads ``ctx.state['last_verdict_flags']``
  and applies them deterministically. Output of one step is wired into
  the input of the next through ``state_patch``, not via shared
  globals.
- **Step.prompt_key is honored at runtime.** The critic's
  ``prompt_key='critique'`` is rendered via
  :func:`resolve_prompt(ctx, 'critique')`. A new mode overriding the
  rubric only needs to register ``'critique:<mode>'`` — no Step
  subclass.

Hermetic — no network, no model calls. The Steps deterministically
score the doc on a rubric and append a marker on revise.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
from arnold.pipelines.megaplan._pipeline.prompts import register_demo_prompts, resolve_prompt

# Register demo prompts at import time so prompt resolution works when
# this module is run directly.  Must happen before any Step.run() call.
register_demo_prompts()
from arnold.pipelines.megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
    PipelineVerdict,
)


_DEFAULT_FIXTURE = """\
This document describes the doc-critique demo loop. The critic reads the
current document version and emits a deterministic verdict. The reviser
then appends a revision pass marker to produce the next version. The
loop terminates after three iterations.
"""

_MAX_ITER = 3


def _latest_doc_path(ctx: StepContext) -> Path:
    """Latest revision the critic should read.

    Resolution order:
    1. ctx.state['latest_doc'] — set by the reviser on each pass.
    2. ctx.inputs['doc'] — the input fixture for iteration 0.
    """
    state = ctx.state if isinstance(ctx.state, dict) else {}
    latest = state.get("latest_doc")
    if isinstance(latest, str) and latest:
        candidate = Path(latest)
        if candidate.exists():
            return candidate
    return Path(ctx.inputs["doc"])


class DocCritic:
    name = "critique"
    kind = "judge"
    prompt_key = "critique"
    slot = "critique"
    produces: tuple = ()
    consumes: tuple = ()

    def run(self, ctx: StepContext) -> StepResult:
        state = dict(ctx.state) if isinstance(ctx.state, dict) else {}
        iteration = int(state.get("critique_iter", 0))

        doc_path = _latest_doc_path(ctx)
        body = doc_path.read_text() if doc_path.exists() else ""

        # The Step's behaviour resolves the mode-aware prompt at
        # runtime; the prompt itself isn't used by this hermetic
        # rubric, but the resolve call exercises the registry and
        # raises if a mode forgets to register an override.
        prompt = resolve_prompt(ctx, self.prompt_key)
        assert "rate" in prompt.lower() or "review" in prompt.lower(), prompt

        sentences = [s for s in body.replace("\n", " ").split(".") if s.strip()]
        short = sum(1 for s in sentences if len(s.split()) < 6)
        upper = sum(1 for w in body.split() if w.isupper())
        score = max(0.0, 1.0 - (short + upper) / max(1, len(sentences)))

        critique_dir = Path(ctx.plan_dir) / "critique_versions"
        critique_dir.mkdir(parents=True, exist_ok=True)
        out_path = critique_dir / f"critique_v{iteration + 1}.json"
        flags = tuple([f"short:{short}", f"upper:{upper}"])
        out_path.write_text(
            json.dumps(
                {
                    "iteration": iteration + 1,
                    "score": score,
                    "flags": list(flags),
                    "doc_read": str(doc_path),
                    "prompt_used": prompt[:64],
                },
                indent=2,
            )
        )

        verdict = PipelineVerdict(
            score=score,
            flags=flags,
            payload={"iteration": iteration + 1, "critique_path": str(out_path)},
        )

        # Encode the loop termination in the edge label: while
        # iteration < MAX, take the iterate path; otherwise halt.
        next_label = "to_revise" if iteration + 1 < _MAX_ITER else "to_done"
        return StepResult(
            outputs={"critique": out_path},
            verdict=verdict,
            next=next_label,
            state_patch={
                "critique_iter": iteration + 1,
                "last_score": score,
                # ⬇️ critique → revise data flow: flags get threaded
                # into the revise Step via state_patch (a Mapping that
                # the executor merges into state.json before the next
                # step's ctx is built).
                "last_verdict_flags": list(flags),
                "last_critique_path": str(out_path),
            },
        )


class DocReviser:
    name = "revise"
    kind = "produce"
    prompt_key = "revise"
    slot = "revise"
    produces: tuple = ()
    consumes: tuple = ()

    def run(self, ctx: StepContext) -> StepResult:
        state = dict(ctx.state) if isinstance(ctx.state, dict) else {}
        iteration = int(state.get("critique_iter", 0))

        # Pull the prior critique's flags directly from state.
        flags = state.get("last_verdict_flags", [])
        prompt = resolve_prompt(ctx, self.prompt_key, params={"flags": flags})
        assert "Revise" in prompt, prompt

        # Revise reads the latest doc the critic just judged (the
        # fixture for iter==1, the previous revision otherwise).
        prev_path = _latest_doc_path(ctx)
        prev_body = prev_path.read_text() if prev_path.exists() else ""
        flag_summary = ", ".join(str(f) for f in flags) or "no flags"
        next_body = (
            prev_body.rstrip()
            + f"\n\nRevision pass {iteration} (resolving {flag_summary}): "
            "edits applied.\n"
        )

        versions_dir = Path(ctx.plan_dir) / "doc_versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        new_path = versions_dir / f"doc_v{iteration}.md"
        new_path.write_text(next_body)

        return StepResult(
            outputs={"doc": new_path},
            next="to_critique",
            state_patch={
                "latest_doc": str(new_path),
                # Clear consumed flags so a subsequent critique sees a
                # fresh state — no leaking between iterations.
                "last_verdict_flags": [],
            },
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


def run_demo(fixture_path: Path, artifact_root: Path, *, mode: str = "code") -> dict[str, Any]:
    fixture_path = Path(fixture_path)
    artifact_root = Path(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)

    pipeline = build_pipeline()
    ctx = StepContext(
        plan_dir=artifact_root,
        state={"critique_iter": 0},
        profile=None,
        mode=mode,
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
    mode = sys.argv[2] if len(sys.argv) > 2 else "code"
    result = run_demo(fixture_path, artifact_root, mode=mode)
    print(
        json.dumps(
            {
                "artifact_root": str(artifact_root),
                "mode": mode,
                "final_stage": result.get("final_stage"),
                "iterations": result.get("state", {}).get("critique_iter"),
            },
            indent=2,
        )
    )
