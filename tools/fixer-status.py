#!/usr/bin/env python3
"""fixer-status: one-command snapshot of a megaplan chain + its fixer.

Usage:
  fixer-status [EPIC ...]        # one or more epics (default: all known)
  fixer-status --json [EPIC ...] # machine-readable output

Prints, per epic:
  chain: last_state | milestone idx | done count | current plan | chain rev
  plan:  state | active phase | worker pid | latest failure kind/time | events count
  seed:  pointer target + ready/errors + revision match vs manifest
  fixer: babysitter log freshness | hermes agent pids (alive) | latest round dir
  watchdog: process count | latest report time
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BOX = "/workspace"
SESSIONS = "/workspace/.megaplan/cloud-sessions"
SEED_ROOTS = "/workspace/.megaplan/runtime-launch-seeds"
REPAIR_DATA = "/workspace/.megaplan/cloud-sessions/repair-data/babysitter-runs"


def _read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _short(sha: str | None, n: int = 14) -> str:
    return str(sha or "")[:n]


# Known epic -> project root mapping (extend as epics are created).
EPIC_PROJECTS: dict[str, str] = {
    "megaplan-maintenance": "/workspace/megaplan-maintenance/Arnold",
    "astrid-first": "/workspace/astrid-first-ce15b5a3/astrid",
}


def _find_epics() -> list[str]:
    epics: list[str] = []
    for f in sorted(Path("/workspace/.megaplan").glob("*.json")):
        # Only the canonical per-epic manifest (no .previous-N, .lock,
        # .rollback, .cutover, or other suffix files).
        if any(suffix in f.name for suffix in (".previous", ".lock", ".rollback", ".cutover")):
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict) and d.get("epic") and d.get("generation") is not None:
            epics.append(f.stem)
    return epics


def _chain_file(epic: str) -> Path | None:
    project = EPIC_PROJECTS.get(epic)
    if not project:
        return None
    chains = Path(project) / ".megaplan" / "plans" / ".chains"
    if not chains.is_dir():
        return None
    for f in sorted(chains.glob("chain-*.json")):
        if f.name.startswith("chain-"):
            return f
    return None


def _resolve_project(epic: str) -> str | None:
    return EPIC_PROJECTS.get(epic)


def epic_status(epic: str) -> dict:
    out: dict = {"epic": epic}
    # Runtime manifest lives at /workspace/.megaplan/{epic}.json (the session
    # JSON under cloud-sessions/ is the MARKER, not the manifest).
    manifest = _read_json(f"/workspace/.megaplan/{epic}.json")
    out["manifest"] = {
        "generation": manifest.get("generation"),
        "head": _short((manifest.get("epic") or {}).get("expected_head")),
    }
    # chain
    chain_path = _chain_file(epic)
    chain: dict = {}
    if chain_path:
        d = _read_json(str(chain_path))
        ci = ((d.get("metadata") or {}).get("execution_binding") or {}).get("runtime_binding") or {}
        cur = ci.get("current_identity") or {}
        chain = {
            "file": chain_path.name,
            "last_state": d.get("last_state"),
            "idx": d.get("current_milestone_index"),
            "plan": d.get("current_plan_name"),
            "done": len(d.get("completed") or []),
            "chain_rev": _short(cur.get("source_revision")),
            "chain_digest": _short(cur.get("content_sha256")),
        }
        # Milestone denominator from THIS epic's chain.yaml (top-level
        # "- label:" entries incl. the terminal reconcile milestone).
        # Without it, `done=6` reads as 6/6 when the true total is 9
        # (2026-08-20 astrid-first m7 park misread by the babysitter).
        # Exact per-epic path: initiatives/{epic}/chain.yaml — globbing the
        # first initiative with a count is wrong in multi-epic projects.
        total = None
        project = _resolve_project(epic)
        if project:
            spec_candidate = Path(project) / ".megaplan" / "initiatives" / epic / "chain.yaml"
            if spec_candidate.is_file():
                try:
                    spec_text = spec_candidate.read_text(encoding="utf-8")
                except OSError:
                    spec_text = ""
                n = sum(
                    1
                    for line in spec_text.splitlines()
                    if line.lstrip() == line and line.startswith("- label:")
                )
                if n:
                    total = n
        chain["total"] = total
    out["chain"] = chain
    # plan + events
    project = _resolve_project(epic)
    plan_name = chain.get("plan")
    if project and plan_name:
        plan_dir = Path(project) / ".megaplan" / "plans" / str(plan_name)
        if plan_dir.is_dir():
            st = _read_json(str(plan_dir / "state.json"))
            lf = st.get("latest_failure") or {}
            rc = st.get("resume_cursor") or {}
            events = plan_dir / "events.ndjson"
            ev_count = sum(1 for _ in open(events, encoding="utf-8")) if events.exists() else 0
            out["plan"] = {
                "name": plan_name,
                "state": st.get("current_state"),
                "phase": st.get("active_phase"),
                "worker": st.get("active_worker"),
                "failure": lf.get("kind"),
                "failure_at": str(lf.get("recorded_at"))[:19],
                "cursor_phase": rc.get("phase"),
                "cursor_strategy": rc.get("retry_strategy"),
                "events": ev_count,
            }
            raw = plan_dir / "plan_v1_raw.txt"
            if raw.exists():
                out["plan"]["raw_error"] = raw.read_text(encoding="utf-8").strip()[:80]
    # seed
    seed_root = Path(SEED_ROOTS)
    pointer = None
    for d in sorted(seed_root.iterdir()) if seed_root.is_dir() else []:
        if d.is_dir() and epic in d.name:
            p = d / "dispatch-current.json"
            if p.exists():
                pointer = _read_json(str(p))
                break
    if pointer:
        sp = pointer.get("seed_path", "")
        seed = _read_json(str(sp)) if os.path.exists(str(sp)) else {}
        out["seed"] = {
            "file": str(sp).split("/")[-1][:40],
            "ready": seed.get("ready"),
            "errors": seed.get("errors"),
            "seed_rev": _short(seed.get("expected_revision")),
            "manifest_gen": seed.get("manifest_generation"),
        }
    # fixer
    fixer: dict = {}
    run_dirs = sorted(Path(REPAIR_DATA).glob(f"sched_superfixer_status_{epic}_*")) if Path(REPAIR_DATA).is_dir() else []
    if run_dirs:
        latest = max(run_dirs, key=lambda p: p.stat().st_mtime if p.exists() else 0)
        log = latest / "babysitter.stdout.log"
        if log.exists():
            mtime = datetime.fromtimestamp(log.stat().st_mtime, tz=timezone.utc)
            fixer["log_age_min"] = round((datetime.now(timezone.utc) - mtime).total_seconds() / 60, 1)
            fixer["log_mtime"] = mtime.strftime("%H:%M:%S")
        fixer["run_dir"] = latest.name
    # hermes agents
    try:
        ps = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=10
        ).stdout
        agents = []
        for line in ps.splitlines():
            if "launch_hermes" in line:
                parts = line.split()
                if len(parts) >= 9:
                    agents.append({"pid": parts[1], "cpu": parts[2], "start": parts[8]})
        fixer["agents"] = agents
    except Exception:
        fixer["agents"] = []
    out["fixer"] = fixer
    # watchdog
    try:
        ps = subprocess.run(
            ["ps", "-ef"], capture_output=True, text=True, timeout=10
        ).stdout
        wd = sum(1 for line in ps.splitlines() if "arnold-watchdog" in line and "grep" not in line)
        out["watchdog"] = {"procs": wd}
    except Exception:
        out["watchdog"] = {"procs": -1}
    out["checked_at"] = _now()
    return out


def render(epics: list[dict]) -> str:
    lines = []
    for e in epics:
        lines.append(f"=== {e['epic']} @ {e.get('checked_at', '')} ===")
        m = e.get("manifest") or {}
        lines.append(f"  manifest: gen={m.get('generation')} head={m.get('head')}")
        c = e.get("chain") or {}
        if c:
            _done = c.get('done')
            _total = c.get('total')
            _done_str = f"{_done}/{_total}" if (_done is not None and _total) else str(_done)
            lines.append(
                f"  chain: {c.get('last_state')} | idx={c.get('idx')} | done={_done_str} "
                f"| plan={c.get('plan')} | rev={c.get('chain_rev')}"
            )
        p = e.get("plan") or {}
        if p:
            lines.append(
                f"  plan: {p.get('state')} | phase={p.get('phase')} | worker={p.get('worker')} "
                f"| fail={p.get('failure')}@{p.get('failure_at')} | events={p.get('events')}"
            )
            if p.get("cursor_strategy"):
                lines.append(f"    cursor: {p.get('cursor_phase')}/{p.get('cursor_strategy')}")
            if p.get("raw_error"):
                lines.append(f"    raw: {p.get('raw_error')}")
        s = e.get("seed") or {}
        if s:
            lines.append(
                f"  seed: {s.get('file')} ready={s.get('ready')} err={s.get('errors')} "
                f"rev={s.get('seed_rev')} gen={s.get('manifest_gen')}"
            )
        f = e.get("fixer") or {}
        if f:
            age = f.get("log_age_min")
            age_s = f"{age}min" if age is not None else "?"
            agents = ", ".join(f"{a['pid']}@{a['cpu']}%" for a in (f.get("agents") or [])) or "none"
            lines.append(f"  fixer: log_age={age_s} agents=[{agents}]")
        w = e.get("watchdog") or {}
        if w:
            lines.append(f"  watchdog: {w.get('procs')} procs")
        lines.append("")
    return "\n".join(lines).rstrip()


def main() -> int:
    ap = argparse.ArgumentParser(description="One-command chain + fixer status snapshot")
    ap.add_argument("epics", nargs="*", help="epic names (default: all)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()
    epics = args.epics or _find_epics()
    if not epics:
        print("no epics found under " + SESSIONS, file=sys.stderr)
        return 1
    results = [epic_status(e) for e in epics]
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(render(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
