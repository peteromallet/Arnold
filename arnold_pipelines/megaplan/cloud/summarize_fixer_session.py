#!/usr/bin/env python3
"""After each fixer session, a DeepSeek Flash agent writes a 2-sentence summary
by browsing the session dir, prioritizing the agent's final message in the logs.
Saved to .megaplan/fixer-sessions/summaries/<id>.md + index.md so the last N can
be injected into future fixer prompts (accounting for recurring issues)."""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys
from pathlib import Path

# Frozen B1 provider table: DeepSeek Flash via omp, fresh stateless RPC.
MODEL = "omp:deepseek/deepseek-v4-flash"

def _final_message(run_dir: Path) -> str:
    for f in ("result.md", "recovery-evidence.json"):
        p = run_dir / f
        if p.exists():
            txt = p.read_text(errors="ignore")
            if f.endswith(".json"):
                try:
                    txt = json.dumps(json.loads(txt).get("inference") or txt)
                except Exception:
                    pass
            if txt.strip():
                return txt[:1200]
    log = run_dir / "run.log"
    if log.exists():
        msgs = re.findall(r'"type":"agent_message","text":"((?:[^"\\]|\\.)*)"', log.read_text(errors="ignore"))
        if msgs:
            return msgs[-1].encode().decode("unicode_escape")[:1200]
    return "(no final message captured)"

def summarize(run_dir: Path, store: Path, session_id: str) -> str:
    model = "?"
    try:
        m = json.loads((run_dir / "manifest.json").read_text(errors="ignore"))
        model = m.get("model", "?")
    except Exception:
        pass
    final = _final_message(run_dir)
    brief = f"""You are summarizing a completed fixer session for future fixers.
Browse the session dir: {run_dir}
Read result.md, recovery-evidence.json, and the FINAL message in run.log (the last agent_message). The final message is the most important signal.
Write exactly TWO sentences: (1) what this fixer session did/fixed, (2) its outcome and any unresolved blocker/gate.
Do NOT include the session path. Do NOT speculate beyond the evidence. Keep it to 2 sentences.
Final message excerpt: {final[:800]}"""
    brief_path = Path("/tmp") / f"fixer-summary-brief-{session_id}.md"
    brief_path.write_text(brief)
    provenance = "flash_generated"
    summary = ""
    try:
        from omp_rpc import RpcClient

        client = RpcClient(
            provider="deepseek",
            model="deepseek-v4-flash",
            thinking="minimal",
            cwd=run_dir,
            no_session=True,
            no_skills=True,
            no_rules=True,
            no_title=True,
            startup_timeout=60,
            request_timeout=300,
        )
        client.start()
        try:
            client.set_model("deepseek", "deepseek-v4-flash")
        except Exception:
            pass
        try:
            client.set_thinking_level("minimal")
        except Exception:
            pass
        turn = client.prompt_and_wait(brief, timeout=300)
        try:
            summary = turn.require_assistant_text()
        except Exception:
            summary = ""
        finally:
            try:
                client.stop()
            except Exception:
                pass
        summary = " ".join(summary.split())[-800:]
    except Exception:
        summary = ""
    if not summary or len(summary) < 20:
        provenance = "fallback_unverified_extract"
        summary = " ".join(final.split())[:500]
    prov = "**Fallback: unverified extract** (Flash summary unavailable)" if provenance == "fallback_unverified_extract" else "Flash-generated 2-sentence summary"
    summary = (
        f"Session {session_id} ({model}) [UNTRUSTED HISTORICAL EVIDENCE — verify against current state]\n"
        f"  provenance: {prov}\n"
        f"  evidence: result.md, recovery-evidence.json, run.log (final agent_message)\n"
        f"  summary: {summary}"
    ).strip()
    (store / "summaries").mkdir(parents=True, exist_ok=True)
    (store / "summaries" / f"{session_id}.md").write_text(summary + "\n")
    idx = store / "index.md"
    with idx.open("a") as fh:
        fh.write(f"- [{session_id}](summaries/{session_id}.md) — {summary[:220]}\n")
    return summary

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--store", required=True)
    ap.add_argument("--session-id", required=True)
    a = ap.parse_args()
    print(summarize(Path(a.run_dir), Path(a.store), a.session_id))
