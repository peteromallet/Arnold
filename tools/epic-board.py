#!/usr/bin/env python3
"""epic-board: find all megaplan epics (local Mac + remote box) and show them;
epic-board deep <epic>: deep diagnosis of one epic's chain + fixer.

Usage:
  epic-board                      # all epics everywhere (local + box)
  epic-board --json               # machine-readable
  epic-board deep <epic>          # deep diagnosis for one epic
  epic-board deep <epic> --json

Local epics: scanned under ~/Documents/*/.megaplan/plans/.chains/chain-*.json.
Box epics:  ssh root@<box> docker exec megaplan-cloud-agent-resident-only
            fixer-status <epic> --json  (reuses the box-side snapshot tool).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BOX_HOST = "root@159.69.51.216"
BOX_CONTAINER = "megaplan-cloud-agent-resident-only"
LOCAL_ROOTS = [Path("/Users/peteromalley/Documents")]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _short(sha, n=14):
    return str(sha or "")[:n]


# ---------------------------------------------------------------------------
# Local epic discovery
# ---------------------------------------------------------------------------

def _local_epics() -> list[dict]:
    epics: list[dict] = []
    for root in LOCAL_ROOTS:
        if not root.is_dir():
            continue
        for chain in sorted(root.glob("*/.megaplan/plans/.chains/chain-*.json")):
            project = chain.parents[3]
            try:
                d = json.load(open(chain, encoding="utf-8"))
            except Exception:
                continue
            epics.append(
                {
                    "epic": project.name,
                    "location": "local",
                    "project": str(project),
                    "chain_file": chain.name,
                    "last_state": d.get("last_state"),
                    "idx": d.get("current_milestone_index"),
                    "plan": d.get("current_plan_name"),
                    "done": len(d.get("completed") or []),
                }
            )
    return epics


# ---------------------------------------------------------------------------
# Box epic snapshot (via the box-side fixer-status tool)
# ---------------------------------------------------------------------------

def _box_snapshot(epics: list[str] | None = None) -> list[dict]:
    cmd = ["ssh", "-o", "ConnectTimeout=30", BOX_HOST,
           "docker", "exec", BOX_CONTAINER, "fixer-status"]
    if epics:
        cmd.extend(epics)
    cmd.append("--json")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        out = r.stdout.strip()
        # fixer-status prints nothing else to stdout; tolerate stray lines.
        start = out.find("[")
        if start < 0:
            return []
        return json.loads(out[start:])
    except Exception:
        return []


def _box_epic_names() -> list[str]:
    snaps = _box_snapshot()
    return [s.get("epic") for s in snaps if s.get("epic")]


# ---------------------------------------------------------------------------
# Deep diagnosis (works local or box; box via ssh docker exec)
# ---------------------------------------------------------------------------

def _run_on_box(script: str) -> str:
    # Quote the script for the remote shell so ssh doesn't re-split it.
    # The script itself runs inside `docker exec ... bash -lc <script>`.
    inner = script.replace("'", "'\\''")
    cmd = [
        "ssh", "-o", "ConnectTimeout=30", BOX_HOST,
        f"docker exec {BOX_CONTAINER} bash -lc '{inner}'",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return f"<ssh error: {e}>"


def deep_local(epic: str) -> dict:
    out: dict = {"epic": epic, "location": "local"}
    for root in LOCAL_ROOTS:
        if not root.is_dir():
            continue
        for chain in root.glob(f"{epic}/.megaplan/plans/.chains/chain-*.json"):
            project = chain.parents[3]
            try:
                d = json.load(open(chain, encoding="utf-8"))
            except Exception:
                continue
            out["chain"] = {
                "file": chain.name,
                "last_state": d.get("last_state"),
                "idx": d.get("current_milestone_index"),
                "plan": d.get("current_plan_name"),
                "done": len(d.get("completed") or []),
            }
            plan_name = out["chain"]["plan"]
            if plan_name:
                plan_dir = project / ".megaplan" / "plans" / plan_name
                if plan_dir.is_dir():
                    st = json.load(open(plan_dir / "state.json", encoding="utf-8"))
                    lf = st.get("latest_failure") or {}
                    rc = st.get("resume_cursor") or {}
                    out["plan"] = {
                        "state": st.get("current_state"),
                        "phase": st.get("active_phase"),
                        "worker": st.get("active_worker"),
                        "failure": lf.get("kind"),
                        "failure_at": str(lf.get("recorded_at"))[:19],
                        "cursor": f"{rc.get('phase')}/{rc.get('retry_strategy')}",
                    }
            break
    return out


def deep_box(epic: str) -> dict:
    snap = _box_snapshot([epic])
    out = snap[0] if snap else {"epic": epic, "location": "box"}
    out["location"] = "box"
    # Engine head + origin/main
    engine = _run_on_box(
        "cd /workspace/runtime-candidates/arnold-4a830c6ac9a0 2>/dev/null && "
        "git rev-parse HEAD | cut -c1-14 && git log --oneline origin/main -3 2>/dev/null | cut -c1-50"
    )
    out["engine"] = [ln for ln in engine.strip().splitlines() if ln][:4]
    # Latest events
    if out.get("plan") and out["plan"].get("name"):
        plan = out["plan"]["name"]
        ev = _run_on_box(
            "P="
            + (
                "/workspace/astrid-first-ce15b5a3/astrid/.megaplan/plans/"
                if epic == "astrid-first"
                else "/workspace/megaplan-maintenance/Arnold/.megaplan/plans/"
            )
            + f"{plan}/events.ndjson; "
            'tail -5 "$P" 2>/dev/null | '
            "python3 -c \"import sys,json; [print(str(json.loads(l).get(\\\"ts_utc\\\"))[11:19], "
            "json.loads(l).get(\\\"type\\\") or json.loads(l).get(\\\"kind\\\") or \\\"state\\\", "
            "str(json.loads(l).get(\\\"payload\\\") or \\\"\\\")[:60]) "
            "for l in sys.stdin]\""
        )
        out["recent_events"] = [ln for ln in ev.strip().splitlines() if ln][:5]
        # Fixer round tail
        fixer = _run_on_box(
            f"D=$(ls -td /workspace/.megaplan/cloud-sessions/repair-data/babysitter-runs/"
            f"sched_superfixer_status_{epic}_* 2>/dev/null | head -1); "
            f"tail -4 $D/babysitter.stdout.log 2>/dev/null | cut -c1-110"
        )
        out["fixer_tail"] = [ln for ln in fixer.strip().splitlines() if ln][-4:]
    return out


def render_board(epics: list[dict]) -> str:
    lines = []
    lines.append(f"Epic board @ {_now()} — {len(epics)} epics")
    lines.append("=" * 60)
    for e in sorted(epics, key=lambda x: (x.get("location"), x.get("epic") or "")):
        loc = e.get("location", "?")
        name = e.get("epic") or "?"
        state = e.get("chain", {}).get("last_state") or e.get("last_state") or "?"
        idx = e.get("chain", {}).get("idx") or e.get("idx")
        done = e.get("chain", {}).get("done") or e.get("done")
        plan = e.get("chain", {}).get("plan") or e.get("plan")
        fixer_age = None
        if e.get("fixer"):
            fixer_age = e["fixer"].get("log_age_min")
        age_s = f"{fixer_age}min" if fixer_age is not None else "-"
        agents = len(e.get("fixer", {}).get("agents") or [])
        line = (
            f"[{loc}] {name}: {state} | idx={idx} done={done} | "
            f"plan={plan} | fixer={age_s} agents={agents}"
        )
        lines.append(line)
    lines.append("=" * 60)
    lines.append("deep: epic-board deep <epic>")
    return "\n".join(lines)


def render_deep(out: dict) -> str:
    lines = []
    lines.append(f"=== {out.get('epic')} ({out.get('location')}) deep @ {_now()} ===")
    c = out.get("chain") or {}
    if c:
        lines.append(
            f"chain: {c.get('last_state')} | idx={c.get('idx')} done={c.get('done')} "
            f"| plan={c.get('plan')} | rev={_short(c.get('chain_rev'))}"
        )
    p = out.get("plan") or {}
    if p:
        cursor = p.get("cursor") or (
            f"{p.get('cursor_phase')}/{p.get('cursor_strategy')}"
            if p.get("cursor_phase") or p.get("cursor_strategy")
            else None
        )
        lines.append(
            f"plan: {p.get('state')} | phase={p.get('phase')} | worker={p.get('worker')} "
            f"| fail={p.get('failure')}@{p.get('failure_at')} | cursor={cursor}"
        )
        if p.get("raw_error"):
            lines.append(f"raw: {p.get('raw_error')}")
    s = out.get("seed") or {}
    if s:
        lines.append(
            f"seed: {s.get('file')} ready={s.get('ready')} rev={s.get('seed_rev')} "
            f"gen={s.get('manifest_gen')}"
        )
    if out.get("manifest"):
        m = out["manifest"]
        lines.append(f"manifest: gen={m.get('generation')} head={m.get('head')}")
    f = out.get("fixer") or {}
    if f:
        age = f.get("log_age_min")
        age_s = f"{age}min" if age is not None else "?"
        agents = ", ".join(f"{a['pid']}@{a['cpu']}%" for a in (f.get("agents") or [])) or "none"
        lines.append(f"fixer: log_age={age_s} agents=[{agents}]")
    if out.get("watchdog"):
        lines.append(f"watchdog: {out['watchdog'].get('procs')} procs")
    if out.get("engine"):
        lines.append("engine:")
        for ln in out["engine"]:
            if ln.strip():
                lines.append(f"  {ln}")
    if out.get("recent_events"):
        lines.append("recent events:")
        for ln in out["recent_events"]:
            lines.append(f"  {ln}")
    if out.get("fixer_tail"):
        lines.append("fixer tail:")
        for ln in out["fixer_tail"]:
            lines.append(f"  {ln}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Find all megaplan epics + deep-diagnose one")
    sub = ap.add_subparsers(dest="cmd")
    board_p = sub.add_parser("board", help="all epics everywhere")
    board_p.add_argument("--json", action="store_true")
    deep_p = sub.add_parser("deep", help="deep diagnosis for one epic")
    deep_p.add_argument("epic")
    deep_p.add_argument("--json", action="store_true")
    args = ap.parse_args()

    want_json = getattr(args, "json", False)

    if args.cmd == "deep":
        epic = args.epic
        # try box first (epics run there), fall back to local
        box_names = _box_epic_names()
        if epic in box_names:
            out = deep_box(epic)
        else:
            out = deep_local(epic)
        if want_json:
            print(json.dumps(out, indent=2, default=str))
        else:
            print(render_deep(out))
        return 0

    # board: merge local + box
    epics = _local_epics()
    box = _box_snapshot()
    for b in box:
        epics.append(
            {
                "epic": b.get("epic"),
                "location": "box",
                "chain": b.get("chain") or {},
                "plan": (b.get("plan") or {}).get("name"),
                "fixer": b.get("fixer") or {},
                "watchdog": b.get("watchdog") or {},
            }
        )
    if want_json:
        print(json.dumps(epics, indent=2, default=str))
    else:
        print(render_board(epics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
