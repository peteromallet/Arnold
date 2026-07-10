#!/usr/bin/env python3
"""Build CATALOG.md categorizing all 100 live-agentic scenarios
(23 existing in-repo + 77 staged outside the repo).

Output: ./CATALOG.md (in this sibling dir, outside the repo working tree).
"""
from __future__ import annotations

import glob
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path("/Users/peteromalley/Documents/reigh-workspace/vibecomfy")
EXISTING_DIR = REPO / "tests" / "live_agentic_harness" / "scenarios"

# manifest metadata lookup (id -> {media, complexity, task, tags, rcn})
cands = json.loads(Path("/tmp/agentic_candidates.json").read_text())
META = {c["id"]: c for c in cands}


def classify_existing(d: dict) -> dict:
    sid = d.get("id")
    q = (d.get("query") or "").lower()
    wp = d.get("workflow_path")
    wid = os.path.basename(wp)[:-5] if wp else None
    meta = META.get(wid, {})
    media = meta.get("media") or (
        "3d" if sid.startswith("3d") else "audio" if sid.startswith("audio")
        else "video" if sid.startswith("video") else "multi" if sid.startswith("multi")
        else "image"
    )
    # query type
    if sid == "speed-distillation-research":
        qt = "research"
    elif sid == "live-graph-explanation-smoke":
        qt = "explain"
    elif sid in {"image-two-stage-qwen-image-generation", "multi-wan-vace-video-retargeting-driven",
                 "multi-image-to-video-generation-with-2"}:
        qt = "big_adjustment"  # multi-stage structural fixes
    else:
        qt = "edit"
    # abstraction
    if any(k in q for k in ["reduce", "switch", "set the", "arrange", "switch to generating"]):
        abstr = "low"
    elif qt in ("research", "explain"):
        abstr = "med"
    else:
        abstr = "high"
    cx = meta.get("complexity")
    cxb = "low" if cx in (1, 2) else "med" if cx == 3 else "high" if cx else "n/a"
    return {
        "id": sid, "modality": media, "query_type": qt, "abstraction": abstr,
        "complexity": cxb, "manifest_cx": cx, "wid": wid,
        "requires_custom_nodes": meta.get("rcn"), "ref": wp or "inline/none",
        "query": d.get("query", ""),
    }


def main() -> None:
    existing = []
    for f in sorted(EXISTING_DIR.glob("*.json")):
        d = json.loads(f.read_text())
        existing.append(classify_existing(d))

    staged = []
    for f in sorted(HERE.glob("*.json")):
        d = json.loads(f.read_text())
        t = d["_tags"]
        staged.append({
            "id": d["id"], "modality": t["modality"], "query_type": t["query_type"],
            "abstraction": t["abstraction"], "complexity": t["complexity"],
            "manifest_cx": t.get("manifest_complexity"), "wid": t.get("source_workflow_id"),
            "requires_custom_nodes": t.get("requires_custom_nodes"),
            "ref": d.get("workflow_path"), "query": d.get("query", ""),
            "apply": d.get("apply"), "task_type": t.get("task_type"),
            "title_hint": Path(d.get("workflow_path", "")).stem,
            "author": (t.get("authored_by") or "").replace("deepseek-v4-", ""),
        })

    allrows = existing + staged

    def c(*, which):
        rows = allrows if which == "all" else (existing if which == "ex" else staged)
        return rows

    L = []
    push = L.append

    push("# Live Agentic Scenarios — Catalog (100 total)\n")
    push("Generated categorization of the live-agentic test suite: **23 existing** scenarios in")
    push("`tests/live_agentic_harness/scenarios/` (auto-run by the harness) plus **77 new** scenarios")
    push("staged in this directory (NOT auto-run).\n")

    push("## How discovery & activation work\n")
    push("- The runner (`tests/live_agentic_harness/runner.py:18`) globs **every** `*.json` in")
    push("  `tests/live_agentic_harness/scenarios/`. No manifest, no registration — `id` defaults to")
    push("  the filename stem. **Anything dropped in that folder runs on the next suite.**")
    push("- The 77 new scenarios live in this **sibling directory, outside the repo**, so they do")
    push("  **not** auto-run and (importantly) so the running `live_agentic_watchdog`'s git-tree")
    push("  safety gate cannot sweep them — it treats new files under `tests/` as off-limits and")
    push("  reverts/cleans them.")
    push("- **To activate any subset:** copy its `.json` into")
    push("  `tests/live_agentic_harness/scenarios/`. Each `workflow_path` is repo-relative and")
    push("  resolves when the harness runs from the repo root.\n")

    push("## Dimensions\n")
    push("- **Modality:** image · video · 3d · audio · multi (multi-image / multi-video / mixed)")
    push("- **Query type:** `edit` (targeted change/tweak) · `big_adjustment` (structural: swap backbone,")
    push("  add/split a stage, reroute) · `research` (investigate options, no change) · `diagnose`")
    push("  (find the root cause, don't edit) · `explain` (understand the graph, no change)")
    push("- **Abstraction:** `low` (specific node/param/value) · `med` (named technique/component) ·")
    push("  `high` (vague goal/symptom — agent must interpret & decide)")
    push("- **Complexity:** `low` (1–2) · `med` (3) · `high` (4–5), from the manifest's own rating\n")

    # ---- Distribution summary ----
    push("## Distribution summary (all 100)\n")
    def dist(field):
        return dict(Counter(r[field] for r in allrows))
    push("| Dimension | Values |")
    push("|---|---|")
    push(f"| Modality | {dist('modality')} |")
    push(f"| Query type | {dist('query_type')} |")
    push(f"| Abstraction | {dist('abstraction')} |")
    push(f"| Complexity | {dist('complexity')} |")
    push("")
    # modality x query_type matrix
    push("### Modality × Query-type matrix (all 100)\n")
    qts = ["edit", "big_adjustment", "research", "diagnose", "explain"]
    mods = ["image", "video", "multi", "audio", "3d"]
    push("| modality | " + " | ".join(qts) + " | total |")
    push("|" + "---|" * (len(qts) + 2))
    for m in mods:
        cells = [sum(1 for r in allrows if r["modality"] == m and r["query_type"] == q) for q in qts]
        push(f"| {m} | " + " | ".join(str(x) for x in cells) + f" | {sum(cells)} |")
    push("")

    push("### Complexity × Query-type matrix (all 100)\n")
    cxs = ["low", "med", "high", "n/a"]
    push("| complexity | " + " | ".join(qts) + " | total |")
    push("|" + "---|" * (len(qts) + 2))
    for cxk in cxs:
        cells = [sum(1 for r in allrows if r["complexity"] == cxk and r["query_type"] == q) for q in qts]
        if sum(cells) == 0:
            continue
        push(f"| {cxk} | " + " | ".join(str(x) for x in cells) + f" | {sum(cells)} |")
    push("")

    # ---- Existing 23 ----
    push("## A. Existing 23 (in-repo, auto-run)\n")
    push("Note the skew: **edit-heavy (symptom fixes), high-abstraction, zero diagnose, one research,")
    push("one explain** — the gaps the 77 new scenarios are designed to fill.\n")
    push("| # | id | modality | query type | abstraction | complexity | ref |")
    push("|---|---|---|---|---|---|---|")
    for i, r in enumerate(existing, 1):
        ref = "inline" if r["ref"] in ("inline/none",) else "…" + os.path.basename(r["ref"])
        push(f"| {i} | `{r['id']}` | {r['modality']} | {r['query_type']} | {r['abstraction']} | {r['complexity']} | {ref} |")
    push("")

    # ---- Staged 77 ----
    push("## B. New 77 (staged here, not auto-run)\n")
    push("Each query is **DeepSeek-authored** (model: `deepseek-v4-pro` for 48, `deepseek-v4-flash`")
    push("for 29). For every workflow, DeepSeek brainstormed 5 candidate queries spanning simple →")
    push("ambitious complexity, then picked the single best one grounded in the workflow's real")
    push("metadata (nodes, techniques, flags) — never generic boilerplate. `desired` rubrics are")
    push("attached to `edit`/`big_adjustment` scenarios to ground the LLM intent judge on outcomes")
    push("(not exact nodes). Workflows are drawn from the `external_workflows` corpus (2,735 real")
    push("workflows; Hivemind-searchable via `vibecomfy/executor/research.py` for even more recent ones).\n")

    # author split
    pro = sum(1 for f in sorted((HERE).glob("*.json")) if json.loads(f.read_text()).get("_tags", {}).get("authored_by") == "deepseek-v4-pro")
    fl = sum(1 for f in sorted((HERE).glob("*.json")) if json.loads(f.read_text()).get("_tags", {}).get("authored_by") == "deepseek-v4-flash")
    push(f"> Authoring split: **{pro} by DeepSeek-V4-Pro**, **{fl} by DeepSeek-V4-Flash** (Flash filled")
    push("> gaps where Pro's reasoning starved the output budget). `_tags.authored_by` records which.\n")

    # grouped by query type, then modality
    by_qt = defaultdict(list)
    for r in staged:
        by_qt[r["query_type"]].append(r)
    for qt in qts:
        rows = sorted(by_qt.get(qt, []), key=lambda r: (r["modality"], r["id"]))
        if not rows:
            continue
        push(f"### {qt} ({len(rows)})\n")
        push("| id | mod | cx | abst | auth | task | query |")
        push("|---|---|---|---|---|---|---|")
        for r in rows:
            q = r["query"].replace("|", "\\|").replace("\n", " ")
            if len(q) > 160:
                q = q[:157] + "…"
            push(f"| `{r['id']}` | {r['modality']} | {r['complexity']} | {r['abstraction']} | "
                 f"{r.get('author','?')} | {r.get('task_type') or '-'} | {q} |")
        push("")

    push("---\n")
    push("## Activation & operations\n")
    push("- **Activate a subset:** `cp <files> " + str(EXISTING_DIR).replace(str(REPO) + "/", "") + "/`")
    push("  (move them in to run; the runner picks them up automatically next suite).")
    push("- **Before scaling the live suite to ~100 all-run:** note the running watchdog reports")
    push("  ~25–30 min/round at 23 scenarios. 100 all-run would be ~2 h/round. Recommended path: keep")
    push("  a ~23-scenario **core** tag hammered each round and run the extended set on a slower")
    push("  cadence (the runner supports `--scenarios-dir` + `--tag`). The runner now executes scenarios")
    push("  concurrently with a per-scenario kill timeout, so a 100-scenario suite is feasible — but it is")
    push("  still multi-hour per full round, so a ~23 core tag per round + extended on a slower cadence is the")
    push("  recommended operating mode.")
    push("- **Reliability filter:** 2693/2735 workflows require custom nodes; only 42 are")
    push("  custom-node-free (all image). For trustworthy green scenarios, filter staged files by")
    push("  `_tags.requires_custom_nodes == false`.")
    push("- **Regenerate / retune:** `python3 _generator.py` (selection seed in the selector; query")
    push("  seed in the generator). Selection inputs live in `/tmp/agentic_selected.json`.\n")
    push(f"_Built from {len(existing)} existing + {len(staged)} staged = {len(allrows)} scenarios._\n")

    (HERE / "CATALOG.md").write_text("\n".join(L))
    print(f"wrote CATALOG.md ({len(allrows)} scenarios: {len(existing)} existing + {len(staged)} staged)")


if __name__ == "__main__":
    main()
