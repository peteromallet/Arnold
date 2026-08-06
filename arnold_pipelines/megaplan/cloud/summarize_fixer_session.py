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

def _structured_summary(run_dir: Path) -> dict:
    """Deterministic evidence-linked summary (Sol-sense-checked)."""
    out = {"objective": "", "actions": "", "verification": "", "unresolved": "", "outcome": "", "evidence_paths": ""}
    rev = run_dir / "recovery-evidence.json"
    if rev.exists():
        try:
            d = json.loads(rev.read_text(errors="ignore"))
            ev = d.get("evidence") or {}
            ob = ev.get("original_blocker") or {}
            after = ob.get("after") or {}
            out["objective"] = " ".join(str(ob.get("before", {}).get("diagnostics", ""))[:200].split())
            out["actions"] = " ".join(str(ev.get("source_repair", {}).get("fail_closed_commit", ""))[:200].split())
            out["outcome"] = f"original_blocker_cleared={after.get('original_blocker_cleared')} cursor={after.get('cursor')}"
            out["unresolved"] = " ".join(str(d.get("terminal_gate", {}).get("reason", ""))[:250].split())
            out["evidence_paths"] = "recovery-evidence.json"
        except Exception:
            pass
    # fall back to final message excerpt (optional field)
    final = _final_message(run_dir)
    if final and "(no final message" not in final:
        out["verification"] = " ".join(final.split())[:300]
    return out


def summarize(run_dir: Path, store: Path, session_id: str) -> str:
    model = "?"
    try:
        m = json.loads((run_dir / "manifest.json").read_text(errors="ignore"))
        model = m.get("model", "?")
    except Exception:
        pass
    s = _structured_summary(run_dir)
    summary = (
        f"Session {session_id} ({model}) [UNTRUSTED HISTORICAL EVIDENCE — verify against current state]\n"
        f"  objective: {s['objective']}\n"
        f"  actions/changes: {s['actions']}\n"
        f"  verification: {s['verification']}\n"
        f"  unresolved/blocker: {s['unresolved']}\n"
        f"  outcome: {s['outcome']}\n"
        f"  evidence: {s['evidence_paths']}"
    ).strip()
    if len(summary) > 900:
        summary = summary[:900] + "…"
    (store / "summaries").mkdir(parents=True, exist_ok=True)
    (store / "summaries" / f"{session_id}.md").write_text(summary + "\n")
    idx = store / "index.md"
    with idx.open("a") as fh:
        fh.write(f"- [{session_id}](summaries/{session_id}.md) — {model} :: {s['outcome']} :: {s['unresolved'][:120]}\n")
    return summary

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--store", required=True)
    ap.add_argument("--session-id", required=True)
    a = ap.parse_args()
    print(summarize(Path(a.run_dir), Path(a.store), a.session_id))
