#!/usr/bin/env python3
"""Merge DeepSeek-authored queries into the 77 staged scenarios.

Reads /tmp/query_results/batch-*.txt (JSON arrays), joins by workflow id
(_tags.source_workflow_id), and rewrites each staged scenario's
query / desired / abstraction with DeepSeek's pick. Falls back to the existing
templated query for any workflow the fan missed. Revalidates everything.
"""
from __future__ import annotations

import glob
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path("/Users/peteromalley/Documents/reigh-workspace/vibecomfy")
# (dir, model_label) in PRIORITY order — earlier wins (Pro beats Flash on overlaps).
RES_DIRS = [
    (Path("/tmp/query_results"), "deepseek-v4-pro"),
    (Path("/tmp/query_results2"), "deepseek-v4-pro"),
    (Path("/tmp/query_results3"), "deepseek-v4-flash"),
    (Path("/tmp/query_results4"), "deepseek-v4-flash"),
]


def extract_array(text: str) -> list:
    """Pull complete JSON objects out of a model response.

    Robust to truncation: DeepSeek-V4-Pro reasoning can exhaust the output
    budget mid-array (``finish_reason: length``), leaving a valid prefix of
    complete ``{...}`` objects followed by a half-written one. We brace-scan and
    recover every COMPLETE object at depth 1, ignoring any trailing fragment.
    """
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()

    objects: list = []
    depth = 0
    in_str = False
    esc = False
    start: int | None = None
    for i, ch in enumerate(t):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                frag = t[start:i + 1]
                try:
                    obj = json.loads(frag)
                    if isinstance(obj, dict):
                        objects.append(obj)
                except json.JSONDecodeError:
                    pass
                start = None
    return objects


def main() -> None:
    authored: dict[str, dict] = {}
    authored_by_model: dict[str, str] = {}
    batches_ok = batches_fail = 0
    for d, label in RES_DIRS:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("batch-*.txt")):
            arr = extract_array(f.read_text())
            if not arr:
                batches_fail += 1
                continue
            batches_ok += 1
            for obj in arr:
                if isinstance(obj, dict) and obj.get("id") and obj.get("query"):
                    wid = str(obj["id"])
                    if wid not in authored:  # priority: first (Pro) dir wins
                        authored[wid] = obj
                        authored_by_model[wid] = label
    print(f"batches parsed ok={batches_ok} fail={batches_fail}; authored entries={len(authored)} "
          f"(pro={sum(1 for v in authored_by_model.values() if v=='deepseek-v4-pro')}, "
          f"flash={sum(1 for v in authored_by_model.values() if v=='deepseek-v4-flash')})")

    files = sorted(HERE.glob("*.json"))
    merged = fallback = missing = 0
    for fp in files:
        d = json.loads(fp.read_text())
        t = d.get("_tags", {})
        wid = t.get("source_workflow_id")
        a = authored.get(wid) if wid else None
        if not a:
            missing += 1
            t["authored_by"] = "template-fallback"
            d["_tags"] = t
            fp.write_text(json.dumps(d, indent=2) + "\n")
            continue
        q = (a.get("query") or "").strip()
        if not q:
            fallback += 1
            t["authored_by"] = "template-fallback-empty"
            d["_tags"] = t
            fp.write_text(json.dumps(d, indent=2) + "\n")
            continue
        d["query"] = q
        if a.get("abstraction") in {"low", "med", "high"}:
            t["abstraction"] = a["abstraction"]
        if isinstance(a.get("desired"), dict) and a["desired"]:
            d["desired"] = a["desired"]
        # else: keep existing templated desired (edit/big have one)
        t["authored_by"] = authored_by_model.get(wid, "deepseek")
        if a.get("rationale"):
            t["author_rationale"] = str(a["rationale"])[:240]
        d["_tags"] = t
        fp.write_text(json.dumps(d, indent=2) + "\n")
        merged += 1

    print(f"merged={merged} fallback={fallback} missing(no match)={missing}")

    # ---- revalidate ----
    import os
    errs = []
    ids = set()
    for fp in files:
        d = json.loads(fp.read_text())
        fid = fp.stem
        if d.get("id") != fid:
            errs.append(f"{fp.name}: id mismatch")
        if d["id"] in ids:
            errs.append(f"{fp.name}: DUPE id")
        ids.add(d["id"])
        wp = d.get("workflow_path")
        if not wp or not (REPO / wp).is_file():
            errs.append(f"{fp.name}: bad workflow_path {wp}")
        egc = (d.get("assessment") or {}).get("expect_graph_changed")
        if d.get("apply") is True and egc is not True:
            errs.append(f"{fp.name}: apply=True but egc={egc}")
        if d.get("apply") is False and egc is not False:
            errs.append(f"{fp.name}: apply=False but egc={egc}")
        if not d.get("query"):
            errs.append(f"{fp.name}: empty query")
    print(f"revalidate: {len(files)} files, {len(errs)} errors")
    for e in errs[:20]:
        print("  ", e)
    print("authored_by:", dict(Counter(json.loads(fp.read_text())["_tags"].get("authored_by") for fp in files)))


if __name__ == "__main__":
    main()
