#!/usr/bin/env python3
"""Write a 2-sentence summary for one fixer session, prioritizing the agent's
final message. Saves to <project>/.megaplan/fixer-sessions/summaries/<id>.md and
appends to index.md so the last N summaries can be injected into future fixers.
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

def _final_message(run_dir: Path) -> str:
    # 1) result.md (agent's final user-facing summary)
    for f in ("result.md", "recovery-evidence.json"):
        p = run_dir / f
        if p.exists():
            txt = p.read_text(errors="ignore")
            if f.endswith(".json"):
                try:
                    d = json.loads(txt)
                    # prefer a summary-ish field, else the raw
                    txt = json.dumps(d.get("inference") or d, indent=1)
                except Exception:
                    pass
            if txt.strip():
                return txt[:1200]
    # 2) last agent_message in run.log
    log = run_dir / "run.log"
    if log.exists():
        msgs = re.findall(r'"type":"agent_message","text":"((?:[^"\\]|\\.)*)"', log.read_text(errors="ignore"))
        if msgs:
            return msgs[-1].encode().decode("unicode_escape")[:1200]
    return "(no final message captured)"

def summarize(run_dir: Path, store: Path, session_id: str) -> str:
    final = _final_message(run_dir)
    model = "?"
    try:
        m = json.loads((run_dir / "manifest.json").read_text(errors="ignore"))
        model = m.get("model", "?")
    except Exception:
        pass
    # 2-sentence summary: model + what it concluded
    first = " ".join(final.split())[:500]
    summary = (f"Session {session_id} ({model}): {first}").strip()
    if len(summary) > 700:
        summary = summary[:700] + "…"
    (store / "summaries").mkdir(parents=True, exist_ok=True)
    (store / "summaries" / f"{session_id}.md").write_text(summary + "\n")
    # append to index
    idx = store / "index.md"
    with idx.open("a") as fh:
        fh.write(f"- [{session_id}](summaries/{session_id}.md) — {summary}\n")
    return summary

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--store", required=True)
    ap.add_argument("--session-id", required=True)
    a = ap.parse_args()
    print(summarize(Path(a.run_dir), Path(a.store), a.session_id))
