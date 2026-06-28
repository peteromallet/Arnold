#!/usr/bin/env python3
"""Fan out DeepSeek-V4-Pro to author the 77 staged-scenario queries via the
repo's native model client (vibecomfy.comfy_nodes.agent.provider.run_model_turn).

This replaces the templated queries with creative, model-authored ones:
for each workflow, DeepSeek brainstorms 5 candidate queries of varying
complexity (conforming to the assigned query_type), picks the best, and writes a
`desired` rubric. Same model/intent as the subagent-launcher hermes pathway; we
drive it through the repo client because that Arnold-runtime discovery actually
resolves in this checkout (the watchdog uses the same path).

Usage:
  python3 _author_queries.py --smoke     # one batch, validate shape
  python3 _author_queries.py             # all 11 batches, 5 concurrent
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path("/Users/peteromalley/Documents/reigh-workspace/vibecomfy")
sys.path.insert(0, str(REPO))
os.environ.setdefault("VIBECOMFY_HEADLESS", "1")
os.environ.setdefault("VIBECOMFY_OPENROUTER_BASE_URL", "https://api.deepseek.com/v1")
if not os.environ.get("DEEPSEEK_API_KEY"):
    envf = Path.home() / "Documents" / "banodoco-workspace" / "brain-of-bndc" / ".env"
    if envf.is_file():
        for line in envf.read_text().splitlines():
            if line.startswith("DEEPSEEK_API_KEY="):
                os.environ["DEEPSEEK_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")

from vibecomfy.comfy_nodes.agent.provider import run_model_turn  # noqa: E402

SEL_PATH = Path("/tmp/agentic_selected.json")
OUT = Path("/tmp/query_results")

INSTRUCTIONS = """You are authoring high-quality test prompts for an AI coding agent that edits ComfyUI image/video/3D/audio generation workflows. For EACH workflow below you will write the single best natural-language user request (a "query") that a real user would type.

These queries drive a live agentic test harness: the agent receives the query plus the workflow and must respond. GOOD QUERIES ARE SPECIFIC, NATURAL, AND REQUIRE GENUINE REASONING. They must be grounded in what the workflow ACTUALLY does — its real techniques, nodes, and stages, per the description and tags — NEVER generic boilerplate ("improve the quality", "make it better", "enhance the output").

For EACH workflow:
1. Study its title, description, tags, flags, task_type, and complexity.
2. Brainstorm FIVE distinct candidate queries spanning a range of complexity:
   - 1-2 SIMPLE/specific (an exact parameter, setting, count, or small concrete target),
   - 1-2 MEDIUM (a named technique, component, or stage-level change),
   - 1 AMBITIOUS (a vague goal, a structural rework, or a problem needing diagnosis/interpretation).
   All five MUST conform to the workflow's assigned query_type (defined below).
3. Pick the SINGLE BEST candidate: the one most specific, most natural, most genuinely agentic (forces real reasoning, not a trivial edit), and best-scoped to THIS particular workflow. Avoid cliches. Avoid inventing fake exact parameter values the workflow probably doesn't have, UNLESS they are plausible for its stated techniques.

query_type definitions (every candidate must conform):
- edit: a concrete change or tweak — a parameter, a setting, a small fix, or a "this looks wrong, fix it" symptom.
- big_adjustment: a STRUCTURAL change — swap the model backbone, add/remove/split a stage, reroute data flow, restructure the pipeline.
- research: INVESTIGATE AND ADVISE ONLY — ask for options, alternatives, tradeoffs, or state-of-the-art. The agent must NOT edit; it researches and reports. Phrase as a question / request for information.
- diagnose: the workflow produces a bad result; ask the agent to find the ROOT CAUSE (which node/setting is misconfigured) WITHOUT editing yet. Give a concrete, plausible symptom grounded in the workflow's domain.
- explain: ask the agent to explain/understand the workflow end-to-end WITHOUT editing. Tests comprehension.

Calibrate ambition to complexity_bucket: low -> favor simple/specific; high -> favor ambitious/structural; med -> a balanced medium.

For edit and big_adjustment ONLY, also write a `desired` rubric. NON-PRESCRIPTIVE: describe the OUTCOME and what "complete/correct" means, NOT exact nodes/params. Be TERSE — ONE sentence each:
- outcome: what a good result achieves,
- quality: what makes it complete (fully wired, no dangling nodes, original function preserved).
For research/diagnose/explain, set desired to null.

OUTPUT: Return ONLY a JSON array (no prose, no markdown fences). One object per workflow, in any order:
{"id": "<workflow id>", "query": "<chosen query>", "abstraction": "low|med|high", "desired": {"outcome": "...", "quality": "...", "alternatives_ok": true} | null, "rationale": "<one short sentence: why this beat the other four>"}"""


def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


MODEL = "deepseek-v4-pro"


def run_batch(bi: int, items: list[dict], retries: int = 2) -> tuple[int, bool, str]:
    user = "Workflows for this batch, as JSON. Each carries its assigned query_type and complexity_bucket — honor them.\n```json\n" + json.dumps(items, indent=2) + "\n```"
    last_err = ""
    for attempt in range(retries + 1):
        try:
            resp = run_model_turn(
                f"author agentic test queries batch {bi}",
                messages=[{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": user}],
                route="deepseek",
                model=MODEL,
                response_contract="json",
            )
            content = (resp.get("content") or "").strip()
            if content:
                (OUT / f"batch-{bi:02d}.txt").write_text(content)
                (OUT / f"batch-{bi:02d}.meta.json").write_text(json.dumps({
                    "ok": True, "len": len(content),
                    "elapsed_ms": (resp.get("_profiling") or {}).get("elapsed_ms"),
                }))
                return bi, True, ""
            last_err = "empty content"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {str(e)[:200]}"
            if "429" in last_err or "rate" in last_err.lower():
                time.sleep(8 * (attempt + 1))
        time.sleep(2)
    (OUT / f"batch-{bi:02d}.meta.json").write_text(json.dumps({"ok": False, "error": last_err}))
    return bi, False, last_err


def main() -> None:
    global OUT, MODEL
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--batch-size", type=int, default=3)
    ap.add_argument("--model", default="deepseek-v4-pro", help="deepseek-v4-pro | deepseek-v4-flash")
    ap.add_argument("--input", default=str(SEL_PATH), help="selection JSON to read workflows from")
    ap.add_argument("--out-dir", default="/tmp/query_results", help="where to write batch-*.txt")
    args = ap.parse_args()
    MODEL = args.model

    sel = json.loads(Path(args.input).read_text())
    OUT = Path(args.out_dir)
    OUT.mkdir(parents=True, exist_ok=True)

    batches = list(enumerate(chunk(sel, args.batch_size)))
    if args.smoke:
        batches = batches[:1]

    if args.smoke:
        bi, items = batches[0]
        t0 = time.time()
        _, ok, err = run_batch(bi, items)
        print(f"smoke batch-{bi:02d}: ok={ok} err={err} ({time.time()-t0:.1f}s)")
        if ok:
            txt = (OUT / f"batch-{bi:02d}.txt").read_text()
            print("--- first 1800 chars ---")
            print(txt[:1800])
        return

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_batch, bi, items): bi for bi, items in batches}
        for fut in as_completed(futs):
            bi, ok, err = fut.result()
            print(f"batch-{bi:02d}: {'OK' if ok else 'FAIL '+err}", flush=True)
    print(f"done in {time.time()-t0:.1f}s; outputs in {OUT}")


if __name__ == "__main__":
    main()
