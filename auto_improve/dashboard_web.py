"""Live SWE-bench comparison dashboard: Open Source vs Closed Source.

Usage:
    python -m auto_improve.dashboard_web 021              # serve iter 021
    python -m auto_improve.dashboard_web 021 --port 3000
"""

import html
import json
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path("results/auto-improve")
ITERATION = "021"

CLOSED_SOURCE_LEADER = {
    "name": "Claude 4.5 Opus",
    "variant": "high reasoning",
    "score": 76.80,
    "cost_per_task": "$0.75",
    "source": "swebench.com",
}


def _iter_dir() -> Path:
    name = ITERATION if ITERATION.startswith("iteration-") else f"iteration-{ITERATION}"
    return BASE_DIR / name


def _task_github_url(tid: str) -> str:
    """Derive GitHub issue URL from SWE-bench task ID like django__django-14011."""
    try:
        owner, repo_issue = tid.split("__", 1)
        repo, issue = repo_issue.rsplit("-", 1)
        return f"https://github.com/{owner}/{repo}/issues/{issue}"
    except (ValueError, IndexError):
        return ""


def _task_repo_name(tid: str) -> str:
    """Extract repo name like 'django' from django__django-14011."""
    try:
        _, repo_issue = tid.split("__", 1)
        repo, _ = repo_issue.rsplit("-", 1)
        return repo
    except (ValueError, IndexError):
        return "unknown"


def _task_issue_description(iter_dir: Path, tid: str) -> str:
    """Extract issue description from the task's summary.json prompt field."""
    for worker_dir in sorted(iter_dir.glob("worker-*")):
        task_dir = worker_dir / tid
        if not task_dir.exists():
            continue
        for run_dir in sorted(task_dir.iterdir()):
            summary = run_dir / "summary.json"
            if summary.exists():
                try:
                    data = json.loads(summary.read_text())
                    prompt = data.get("prompt", "")
                    start = prompt.find("## Issue Description")
                    if start == -1:
                        continue
                    start = prompt.find("\n", start) + 1
                    end = prompt.find("## Hints", start)
                    if end == -1:
                        end = prompt.find("## Instructions", start)
                    if end == -1:
                        end = start + 500
                    desc = prompt[start:end].strip()
                    if len(desc) > 400:
                        desc = desc[:400] + "…"
                    return desc
                except Exception:
                    pass
    return ""


def _gather_data() -> dict:
    iter_dir = _iter_dir()
    config_path = iter_dir / "_run_config.json"
    robustness = "?"
    models = {}
    if config_path.exists():
        config = json.loads(config_path.read_text())
        robustness = config.get("robustness", "?")
        models = config.get("models", {})

    scores = {}
    scores_path = iter_dir / "_watch_scores.json"
    if scores_path.exists():
        scores = json.loads(scores_path.read_text())

    tasks_data = []
    for tid, t in sorted(scores.get("tasks", {}).items()):
        r = t.get("resolved")
        review = t.get("review", {}) if isinstance(t, dict) else {}
        cat = review.get("category", "") if isinstance(review, dict) else ""
        explanation = review.get("explanation", "") if isinstance(review, dict) else ""
        gap = review.get("pipeline_gap", "") if isinstance(review, dict) else ""
        golden = review.get("golden_comparison", "") if isinstance(review, dict) else ""
        scored_at = t.get("scored_at", "")

        if r is True:
            status = "pass"
        elif r is False:
            status = "fail"
        elif isinstance(review, dict) and (review.get("reviewed_by") == "human" or review.get("category") == "scoring_exhausted"):
            status = "skip"
        else:
            status = "pending"

        phases = []
        run_path = ""
        worker = ""
        for worker_dir in sorted(iter_dir.glob("worker-*")):
            task_dir = worker_dir / tid
            if task_dir.exists():
                for run_dir in sorted(task_dir.iterdir()):
                    pd = run_dir / "phases"
                    if pd.exists():
                        worker = worker_dir.name
                        run_path = str(run_dir.relative_to(iter_dir))
                        for pf in sorted(pd.glob("*.json")):
                            try:
                                d = json.loads(pf.read_text())
                                dur = d.get("duration_ms", 0) / 1000
                                phase_name = d.get("phase", pf.stem)
                                model = d.get("model", "")
                                phases.append({
                                    "name": phase_name,
                                    "duration_s": round(dur),
                                    "model": model,
                                    "file": pf.name,
                                })
                            except Exception:
                                pass

        total_time = sum(p["duration_s"] for p in phases)
        gate_iterations = sum(1 for p in phases if p["name"] == "gate")

        issue_desc = _task_issue_description(iter_dir, tid)
        github_url = _task_github_url(tid)
        repo_name = _task_repo_name(tid)

        tasks_data.append({
            "id": tid,
            "status": status,
            "category": cat,
            "explanation": explanation,
            "pipeline_gap": gap,
            "golden_comparison": golden,
            "phases": phases,
            "total_time_s": total_time,
            "gate_iterations": gate_iterations,
            "worker": worker,
            "run_path": run_path,
            "scored_at": scored_at,
            "github_url": github_url,
            "issue_description": issue_desc,
            "repo": repo_name,
        })

    passed = sum(1 for t in tasks_data if t["status"] == "pass")
    failed = sum(1 for t in tasks_data if t["status"] == "fail")
    total = passed + failed
    pct = (passed / total * 100) if total else 0

    # Build score progression (ordered by scored_at time)
    scored_tasks = [t for t in tasks_data if t["status"] in ("pass", "fail") and t["scored_at"]]
    scored_tasks.sort(key=lambda t: t["scored_at"])
    progression = []
    running_pass = 0
    running_total = 0
    for t in scored_tasks:
        running_total += 1
        if t["status"] == "pass":
            running_pass += 1
        progression.append({
            "n": running_total,
            "pass_rate": round(running_pass / running_total * 100, 1),
            "task_id": t["id"],
            "result": t["status"],
            "scored_at": t["scored_at"],
        })

    # Compute stats
    streak = 0
    for t in reversed(scored_tasks):
        if t["status"] == "pass":
            streak += 1
        else:
            break

    # Momentum: last 5 tasks pass rate
    last_n = min(5, len(scored_tasks))
    recent = scored_tasks[-last_n:] if last_n else []
    momentum_pct = round(sum(1 for t in recent if t["status"] == "pass") / len(recent) * 100) if recent else 0

    # Tasks per hour — overall average
    tasks_per_hour = 0.0
    if len(scored_tasks) >= 2:
        try:
            first = datetime.fromisoformat(scored_tasks[0]["scored_at"])
            last = datetime.fromisoformat(scored_tasks[-1]["scored_at"])
            hours = (last - first).total_seconds() / 3600
            if hours > 0:
                tasks_per_hour = round(len(scored_tasks) / hours, 1)
        except Exception:
            pass

    # Recent pace: time per task based on last 5 completions (for ETA)
    recent_pace_hours = 0.0  # hours per task
    if len(scored_tasks) >= 2:
        window = min(5, len(scored_tasks))
        try:
            t_start = datetime.fromisoformat(scored_tasks[-window]["scored_at"])
            t_end = datetime.fromisoformat(scored_tasks[-1]["scored_at"])
            span_hours = (t_end - t_start).total_seconds() / 3600
            if span_hours > 0 and window > 1:
                recent_pace_hours = span_hours / (window - 1)
        except Exception:
            pass

    # Per-repo breakdown
    repo_stats: dict[str, dict] = {}
    for t in tasks_data:
        if t["status"] not in ("pass", "fail"):
            continue
        repo = t["repo"]
        if repo not in repo_stats:
            repo_stats[repo] = {"passed": 0, "failed": 0, "total": 0}
        repo_stats[repo]["total"] += 1
        if t["status"] == "pass":
            repo_stats[repo]["passed"] += 1
        else:
            repo_stats[repo]["failed"] += 1

    # Average time per task
    timed_tasks = [t for t in tasks_data if t["total_time_s"] > 0 and t["status"] in ("pass", "fail")]
    avg_time_s = round(sum(t["total_time_s"] for t in timed_tasks) / len(timed_tasks)) if timed_tasks else 0

    # Manifest data
    manifest_path = _iter_dir() / "_task_manifest.json"
    manifest_pending = 0
    manifest_claimed = 0
    manifest_done = 0
    manifest_total = 0
    if manifest_path.exists():
        try:
            m = json.loads(manifest_path.read_text())
            for t in m.get("tasks", {}).values():
                s = t.get("status", "")
                manifest_total += 1
                if s == "pending":
                    manifest_pending += 1
                elif s == "claimed":
                    manifest_claimed += 1
                elif s == "done":
                    manifest_done += 1
        except Exception:
            pass

    logs_dir = iter_dir / "_worker_logs"
    worker_logs = {}
    if logs_dir.exists():
        for lf in sorted(logs_dir.glob("*.stderr.log")):
            worker_logs[lf.stem.replace(".stderr", "")] = lf.name

    return {
        "iteration": iter_dir.name,
        "robustness": robustness,
        "models": models,
        "passed": passed,
        "failed": failed,
        "total_scored": total,
        "total_target": 500,
        "pass_rate": round(pct, 1),
        "tasks": tasks_data,
        "progression": progression,
        "streak": streak,
        "momentum_pct": momentum_pct,
        "tasks_per_hour": tasks_per_hour,
        "recent_pace_hours": round(recent_pace_hours, 2),
        "repo_stats": repo_stats,
        "avg_time_s": avg_time_s,
        "manifest_pending": manifest_pending,
        "manifest_claimed": manifest_claimed,
        "manifest_done": manifest_done,
        "manifest_total": manifest_total,
        "worker_logs": worker_logs,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _read_log(worker_id: str, tail: int = 500) -> str:
    log_file = _iter_dir() / "_worker_logs" / f"{worker_id}.stderr.log"
    if not log_file.exists():
        return f"Log not found: {log_file}"
    lines = log_file.read_text(errors="replace").splitlines()
    return "\n".join(lines[-tail:])


def _render_html(data: dict) -> str:
    pct = data["pass_rate"]
    our_score = pct
    their_score = CLOSED_SOURCE_LEADER["score"]
    winning = our_score > their_score
    delta = our_score - their_score
    delta_str = f"+{delta:.1f}" if delta > 0 else f"{delta:.1f}"

    execute_model = data["models"].get("execute", "?").replace("zhipu:", "")
    critique_model = data["models"].get("critique", "?").replace("minimax:", "")

    # Progression data as JSON for the JS chart
    progression_json = json.dumps(data["progression"])

    # Stats
    streak = data["streak"]
    momentum = data["momentum_pct"]
    tph = data["tasks_per_hour"]
    remaining = data["total_target"] - data["total_scored"]
    pace = data["recent_pace_hours"]
    if pace > 0:
        eta_hours = round(remaining * pace, 1)
        if eta_hours > 48:
            eta_str = f"{round(eta_hours / 24, 1)}d"
        else:
            eta_str = f"{eta_hours}h"
    else:
        eta_str = "—"

    avg_time = data["avg_time_s"]
    avg_time_str = f"{avg_time // 60}m{avg_time % 60}s" if avg_time else "—"

    stats_html = f"""
    <div class="stats-bar">
        <div class="stat">
            <div class="stat-value">{'🔥 ' if streak >= 5 else ''}{streak}</div>
            <div class="stat-label">streak</div>
        </div>
        <div class="stat">
            <div class="stat-value">{momentum}%</div>
            <div class="stat-label">last 5</div>
        </div>
        <div class="stat">
            <div class="stat-value">{tph}</div>
            <div class="stat-label">tasks/hr</div>
        </div>
        <div class="stat">
            <div class="stat-value">{avg_time_str}</div>
            <div class="stat-label">avg time</div>
        </div>
        <div class="stat">
            <div class="stat-value">{data['manifest_claimed']}</div>
            <div class="stat-label">in flight</div>
        </div>
        <div class="stat">
            <div class="stat-value">{remaining}</div>
            <div class="stat-label">remaining</div>
        </div>
        <div class="stat">
            <div class="stat-value">{eta_str}</div>
            <div class="stat-label">ETA (last 5 pace)</div>
        </div>
    </div>"""

    # Per-repo breakdown
    repo_rows = ""
    for repo, rs in sorted(data["repo_stats"].items(), key=lambda x: x[1]["total"], reverse=True):
        rp = round(rs["passed"] / rs["total"] * 100) if rs["total"] else 0
        bar_w = max(rp, 2)
        color = "#22c55e" if rp >= 80 else "#f59e0b" if rp >= 60 else "#ef4444"
        repo_rows += f"""
        <div class="repo-row">
            <span class="repo-name">{html.escape(repo)}</span>
            <span class="repo-bar-wrap"><span class="repo-bar" style="width:{bar_w}%;background:{color}"></span></span>
            <span class="repo-stat">{rs['passed']}/{rs['total']} ({rp}%)</span>
        </div>"""

    # Live activity feed — last 8 scored tasks in reverse chronological order
    recent_scored = sorted(
        [t for t in data["tasks"] if t["status"] in ("pass", "fail") and t["scored_at"]],
        key=lambda t: t["scored_at"],
        reverse=True,
    )[:8]
    feed_rows = ""
    for t in recent_scored:
        icon = "✓" if t["status"] == "pass" else "✗"
        cls = "pass" if t["status"] == "pass" else "fail"
        try:
            dt = datetime.fromisoformat(t["scored_at"])
            ago = (datetime.now(timezone.utc) - dt).total_seconds()
            if ago < 3600:
                time_ago = f"{int(ago // 60)}m ago"
            elif ago < 86400:
                time_ago = f"{int(ago // 3600)}h ago"
            else:
                time_ago = f"{int(ago // 86400)}d ago"
        except Exception:
            time_ago = ""
        time_str = f"{t['total_time_s'] // 60}m{t['total_time_s'] % 60}s" if t["total_time_s"] else ""
        feed_rows += f"""
        <div class="feed-row {cls}">
            <span class="feed-icon">{icon}</span>
            <span class="feed-tid">{html.escape(t['id'])}</span>
            <span class="feed-time">{time_str}</span>
            <span class="feed-ago">{time_ago}</span>
        </div>"""

    # Task rows — sorted newest first by scored_at (unscored at bottom)
    sorted_tasks = sorted(
        data["tasks"],
        key=lambda t: t.get("scored_at") or "",
        reverse=True,
    )
    task_rows = ""
    for t in sorted_tasks:
        if t["status"] == "pass":
            icon, cls = "✓", "pass"
        elif t["status"] == "fail":
            icon, cls = "✗", "fail"
        elif t["status"] == "skip":
            icon, cls = "⊘", "skip"
        else:
            icon, cls = "…", "pending"

        cat_html = f'<span class="tag fail-tag">{html.escape(t["category"])}</span>' if t["category"] else ""
        gap_html = f'<span class="tag gap-tag">{html.escape(t["pipeline_gap"])}</span>' if t["pipeline_gap"] else ""
        golden_html = f'<span class="tag golden-tag">vs golden: {html.escape(t["golden_comparison"])}</span>' if t["golden_comparison"] else ""

        time_str = ""
        if t["total_time_s"]:
            m, s = divmod(t["total_time_s"], 60)
            time_str = f"{m}m{s}s"
        iter_str = f' ({t["gate_iterations"]} iteration{"s" if t["gate_iterations"] != 1 else ""})' if t["gate_iterations"] > 1 else ""

        # Phase timeline as visual bar
        phase_bar = ""
        if t["phases"]:
            max_time = max(t["total_time_s"], 1)
            for p in t["phases"]:
                pct_width = max(p["duration_s"] / max_time * 100, 2) if max_time else 5
                phase_cls = "phase-" + p["name"].split("_")[0]
                pm, ps = divmod(p["duration_s"], 60)
                dur_str = f"{pm}m{ps}s" if pm else f"{ps}s"
                phase_bar += f'<div class="phase-bar-seg {phase_cls}" style="width:{pct_width}%" title="{html.escape(p["name"])}: {dur_str} ({html.escape(p["model"])})">{p["name"][:3]}</div>'

        # Issue description
        issue_html = ""
        if t["issue_description"]:
            escaped = html.escape(t["issue_description"]).replace("\n", "<br>")
            issue_html = f'<div class="issue-desc">{escaped}</div>'

        # GitHub link
        gh_link = ""
        if t["github_url"]:
            gh_link = f'<a href="{t["github_url"]}" target="_blank" class="gh-link" onclick="event.stopPropagation()">View on GitHub →</a>'

        # Explanation
        expl = ""
        if t["explanation"]:
            expl = f'<div class="expl">{html.escape(t["explanation"])}</div>'

        # Deep link to artifacts
        artifacts_link = ""
        if t["run_path"]:
            artifacts_link = f'<div class="artifacts-link">📂 <code>{html.escape(t["run_path"])}/phases/</code></div>'

        task_rows += f"""
        <div class="task-row {cls}" onclick="this.querySelector('.task-expand')?.classList.toggle('show')">
            <div class="task-main">
                <span class="icon">{icon}</span>
                <span class="tid">{html.escape(t['id'])}</span>
                <span class="task-meta">{time_str}{iter_str}</span>
                {cat_html}{gap_html}{golden_html}
                <span class="expand-hint">▸</span>
            </div>
            <div class="task-expand">
                {gh_link}
                {issue_html}
                {expl}
                <div class="phase-bar">{phase_bar}</div>
                {artifacts_link}
            </div>
        </div>"""

    worker_links = "".join(f'<a href="/log/{wid}" class="log-link">{wid}</a>' for wid in sorted(data["worker_logs"].keys()))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Open Source vs Closed Source — SWE-bench Verified</title>
<meta http-equiv="refresh" content="30">
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #050505; color: #e5e5e5; }}

    .hero {{ padding: 3rem 2rem 2rem; text-align: center; border-bottom: 1px solid #1a1a1a; }}
    .hero-label {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.15em; color: #525252; margin-bottom: 0.75rem; }}
    .hero-title {{ font-size: 1.6rem; font-weight: 300; color: #d4d4d4; margin-bottom: 0.5rem; max-width: 700px; margin-left: auto; margin-right: auto; }}
    .hero-title strong {{ font-weight: 700; color: #fff; }}
    .hero-sub {{ font-size: 0.8rem; color: #525252; max-width: 650px; margin: 0.5rem auto 0.75rem; line-height: 1.6; }}
    .hero-sub a {{ color: #60a5fa; text-decoration: none; }}
    .hero-sub a:hover {{ text-decoration: underline; }}

    .versus {{ display: flex; justify-content: center; align-items: stretch; gap: 1.5rem; flex-wrap: wrap; padding: 1.5rem 1rem; }}
    .side {{ flex: 1; min-width: 260px; max-width: 360px; padding: 1.5rem; border-radius: 14px; text-align: center; }}
    .side-open {{ background: linear-gradient(135deg, #022c22 0%, #0a0a0a 100%); border: 1px solid #166534; }}
    .side-closed {{ background: linear-gradient(135deg, #1e1b4b 0%, #0a0a0a 100%); border: 1px solid #4338ca; }}
    .side-label {{ font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.5rem; }}
    .side-open .side-label {{ color: #4ade80; }}
    .side-closed .side-label {{ color: #818cf8; }}
    .side-models {{ font-size: 0.7rem; color: #525252; margin-bottom: 0.75rem; line-height: 1.4; }}
    .side-score {{ font-size: 3.5rem; font-weight: 800; line-height: 1; }}
    .side-open .side-score {{ color: {'#22c55e' if winning else '#a3a3a3'}; }}
    .side-closed .side-score {{ color: {'#a3a3a3' if winning else '#818cf8'}; }}
    .side-detail {{ font-size: 0.8rem; color: #737373; margin-top: 0.25rem; }}
    .side-progress {{ font-size: 0.65rem; color: #404040; margin-top: 0.4rem; }}
    .live-dot {{ display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #22c55e; margin-right: 4px; animation: pulse 2s infinite; }}
    @keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} }}

    .vs-badge {{ display: flex; align-items: center; justify-content: center; margin: 1rem 0 0.5rem; }}
    .vs-text {{ font-size: 0.8rem; padding: 0.2rem 0.75rem; border-radius: 9999px; font-weight: 700; }}
    .vs-winning {{ background: #22c55e22; color: #4ade80; border: 1px solid #22c55e44; }}
    .vs-losing {{ background: #ef444422; color: #fca5a5; border: 1px solid #ef444444; }}

    /* Chart */
    .chart-section {{ max-width: 800px; margin: 1.5rem auto 0; padding: 0 1rem; }}
    .chart-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem; }}
    .chart-header h3 {{ font-size: 0.75rem; color: #404040; text-transform: uppercase; letter-spacing: 0.05em; }}
    .zoom-btns {{ display: flex; gap: 4px; }}
    .zoom-btn {{ background: #111; border: 1px solid #222; color: #666; font-size: 0.6rem; padding: 3px 10px; border-radius: 4px; cursor: pointer; transition: all 0.15s; }}
    .zoom-btn:hover {{ background: #1a1a1a; color: #999; }}
    .zoom-btn.active {{ background: #1a1a1a; color: #e5e5e5; border-color: #333; }}
    .chart-wrap {{ position: relative; }}
    .chart-wrap canvas {{ width: 100%; height: 240px; border-radius: 8px; }}
    .chart-tooltip {{ position: absolute; display: none; background: #1a1a1a; border: 1px solid #333; border-radius: 6px; padding: 6px 10px; font-size: 0.65rem; color: #e5e5e5; pointer-events: none; z-index: 10; white-space: nowrap; }}

    /* Stats bar */
    .stats-bar {{ display: flex; justify-content: center; gap: 1.5rem; padding: 1rem; flex-wrap: wrap; max-width: 800px; margin: 0 auto; }}
    .stat {{ text-align: center; min-width: 60px; }}
    .stat-value {{ font-size: 1.3rem; font-weight: 700; color: #e5e5e5; }}
    .stat-label {{ font-size: 0.6rem; color: #404040; text-transform: uppercase; letter-spacing: 0.05em; }}

    /* Two-column layout for repo + feed */
    .mid-section {{ display: flex; gap: 1.5rem; max-width: 800px; margin: 1rem auto 0; padding: 0 1rem; flex-wrap: wrap; }}
    .mid-col {{ flex: 1; min-width: 300px; }}
    .mid-col h3 {{ font-size: 0.75rem; color: #404040; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }}

    /* Repo breakdown */
    .repo-row {{ display: flex; align-items: center; gap: 0.5rem; padding: 3px 0; }}
    .repo-name {{ font-size: 0.7rem; color: #a3a3a3; font-family: monospace; min-width: 80px; }}
    .repo-bar-wrap {{ flex: 1; height: 10px; background: #111; border-radius: 3px; overflow: hidden; }}
    .repo-bar {{ height: 100%; border-radius: 3px; transition: width 0.3s; }}
    .repo-stat {{ font-size: 0.65rem; color: #525252; min-width: 70px; text-align: right; }}

    /* Activity feed */
    .feed-row {{ display: flex; align-items: center; gap: 0.5rem; padding: 4px 0; border-bottom: 1px solid #0a0a0a; }}
    .feed-icon {{ font-size: 0.8rem; width: 1rem; }}
    .feed-row.pass .feed-icon {{ color: #22c55e; }}
    .feed-row.fail .feed-icon {{ color: #ef4444; }}
    .feed-tid {{ font-size: 0.65rem; color: #a3a3a3; font-family: monospace; flex: 1; }}
    .feed-time {{ font-size: 0.6rem; color: #404040; }}
    .feed-ago {{ font-size: 0.6rem; color: #333; min-width: 50px; text-align: right; }}

    .content {{ max-width: 800px; margin: 0 auto; padding: 1.5rem; }}
    .section {{ margin-top: 1.5rem; }}
    .section h3 {{ font-size: 0.75rem; color: #404040; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }}
    .section-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem; }}

    .task-row {{ padding: 0.5rem; border-bottom: 1px solid #111; cursor: pointer; transition: background 0.15s; }}
    .task-row:hover {{ background: #0d0d0d; }}
    .task-main {{ display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }}
    .task-row.pass .icon {{ color: #22c55e; }}
    .task-row.fail .icon {{ color: #ef4444; }}
    .task-row.skip .icon {{ color: #404040; }}
    .task-row.pending .icon {{ color: #eab308; }}
    .icon {{ width: 1rem; flex-shrink: 0; font-size: 0.9rem; }}
    .tid {{ font-size: 0.75rem; color: #a3a3a3; font-family: monospace; }}
    .task-meta {{ font-size: 0.65rem; color: #333; margin-left: auto; }}
    .expand-hint {{ font-size: 0.6rem; color: #262626; transition: transform 0.2s; }}
    .task-row:has(.task-expand.show) .expand-hint {{ transform: rotate(90deg); color: #404040; }}
    .tag {{ font-size: 0.6rem; padding: 1px 5px; border-radius: 3px; margin-left: 0.25rem; }}
    .fail-tag {{ background: #ef444415; color: #f87171; }}
    .gap-tag {{ background: #eab30815; color: #fde047; }}
    .golden-tag {{ background: #3b82f615; color: #93c5fd; }}

    .task-expand {{ display: none; padding: 0.75rem 0 0.5rem 1.5rem; }}
    .task-expand.show {{ display: block; }}

    .gh-link {{ display: inline-block; font-size: 0.7rem; color: #60a5fa; text-decoration: none; margin-bottom: 0.5rem; }}
    .gh-link:hover {{ text-decoration: underline; }}

    .issue-desc {{ font-size: 0.7rem; color: #525252; margin-bottom: 0.5rem; line-height: 1.5; padding: 0.5rem; background: #0a0a0a; border-left: 2px solid #1a1a1a; border-radius: 0 4px 4px 0; max-height: 120px; overflow-y: auto; }}
    .expl {{ font-size: 0.7rem; color: #525252; margin-bottom: 0.4rem; line-height: 1.4; }}

    .phase-bar {{ display: flex; gap: 1px; margin: 0.5rem 0; height: 20px; border-radius: 4px; overflow: hidden; }}
    .phase-bar-seg {{ font-size: 0.5rem; color: #a3a3a3; display: flex; align-items: center; justify-content: center; overflow: hidden; min-width: 0; }}
    .phase-prep {{ background: #1e293b; }}
    .phase-plan {{ background: #1e3a5f; }}
    .phase-critique {{ background: #3b1f4b; }}
    .phase-gate {{ background: #4a3728; }}
    .phase-revise {{ background: #2d3b28; }}
    .phase-finalize {{ background: #1e3a3a; }}
    .phase-execute {{ background: #164e2e; }}
    .phase-review {{ background: #3b3b1e; }}

    .artifacts-link {{ font-size: 0.65rem; color: #333; margin-top: 0.4rem; }}
    .artifacts-link code {{ color: #525252; }}

    .logs {{ margin-top: 1rem; }}
    .log-link {{ display: inline-block; margin: 0.15rem; padding: 0.15rem 0.5rem; background: #0d0d0d; border: 1px solid #1a1a1a; border-radius: 4px; color: #525252; text-decoration: none; font-size: 0.7rem; }}
    .log-link:hover {{ background: #1a1a1a; color: #a3a3a3; }}

    .footer {{ text-align: center; padding: 2rem; font-size: 0.6rem; color: #1a1a1a; }}
    .footer a {{ color: #262626; }}
</style>
</head>
<body>

<div class="hero">
    <div class="hero-label">SWE-bench Verified — Live Experiment</div>
    <div class="hero-title">Can <strong>open-source models</strong> beat the best closed-source<br>using a generalised harness?</div>
    <div class="hero-sub">
        <a href="https://github.com/peteromallet/megaplan">Megaplan</a> is a general-purpose harness that helps LLMs
        execute complex tasks through structured phases. It boosts the practical performance of models significantly
        — but not yet measurably. Here, two open-weight models — <strong>{execute_model}</strong> (execution &amp; planning) and
        <strong>{critique_model}</strong> (critique &amp; review) — are working together through Megaplan
        to solve real GitHub issues from the <a href="https://www.swebench.com">SWE-bench Verified</a> benchmark.
        Our goal: beat <strong>Claude Opus 4.5</strong>, the best-ranked Claude model, at this benchmark.
        You can follow the progress live — all data is open source below.
    </div>

    <div class="versus">
        <div class="side side-open">
            <div class="side-label"><span class="live-dot"></span> Open Source + Megaplan</div>
            <div class="side-models">{execute_model} + {critique_model}<br>{data['robustness']} robustness</div>
            <div class="side-score">{our_score:.1f}%</div>
            <div class="side-detail">{data['passed']}/{data['total_scored']} resolved</div>
            <div class="side-progress">{data['total_scored']} of {data['total_target']} tasks &middot; live results</div>
        </div>

        <div class="side side-closed">
            <div class="side-label">Closed Source</div>
            <div class="side-models">{CLOSED_SOURCE_LEADER['name']}<br>{CLOSED_SOURCE_LEADER['variant']} &middot; {CLOSED_SOURCE_LEADER['cost_per_task']}/task</div>
            <div class="side-score">{their_score}%</div>
            <div class="side-detail">SWE-bench Verified</div>
            <div class="side-progress">500 of 500 tasks &middot; <a href="https://www.swebench.com" style="color:#525252">benchmark</a></div>
        </div>
    </div>

    <div class="vs-badge">
        <span class="vs-text {'vs-winning' if winning else 'vs-losing'}">
            {'▲' if winning else '▼'} {delta_str}% {'ahead' if winning else 'behind'}
        </span>
    </div>
</div>

<div class="chart-section">
    <div class="chart-header">
        <h3>Score progression ({data['total_scored']} / {data['total_target']} tasks)</h3>
        <div class="zoom-btns">
            <button class="zoom-btn active" onclick="setZoom(500)">All (500)</button>
            <button class="zoom-btn" onclick="setZoom(100)">Last 100</button>
            <button class="zoom-btn" onclick="setZoom(50)">Last 50</button>
            <button class="zoom-btn" onclick="setZoom(20)">Last 20</button>
        </div>
    </div>
    <div class="chart-wrap">
        <canvas id="chart" width="760" height="240"></canvas>
        <div class="chart-tooltip" id="tooltip"></div>
    </div>
</div>

{stats_html}

<div class="mid-section">
    <div class="mid-col">
        <h3>Pass rate by repo</h3>
        {repo_rows}
    </div>
    <div class="mid-col">
        <h3>Latest results</h3>
        {feed_rows}
    </div>
</div>

<div class="content">
    <div class="section">
        <div class="section-header">
            <h3>Tasks ({data['total_scored']} scored — click to expand)</h3>
            <button class="zoom-btn" onclick="toggleTaskSort()" id="sort-btn">Oldest first</button>
        </div>
        <div id="task-list">{task_rows}</div>
    </div>

    <div class="section logs">
        <h3>Live Worker Logs</h3>
        {worker_links}
    </div>
</div>

<div class="footer">
    Auto-refreshes every 30s &middot; {data['generated_at'][:19]}Z &middot;
    <a href="https://github.com/peteromallet/megaplan">Megaplan on GitHub</a> &middot;
    <a href="https://www.swebench.com">SWE-bench</a> &middot;
    <a href="/api/data">API</a>
</div>

<script>
const DATA = {progression_json};
const TARGET = {data['total_target']};
const THEIR_SCORE = {their_score};
let currentZoom = 500;

function setZoom(n) {{
    currentZoom = n;
    document.querySelectorAll('.zoom-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    drawChart();
}}

function drawChart() {{
    const canvas = document.getElementById('chart');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    const W = rect.width, H = rect.height;

    const padL = 40, padR = 15, padT = 15, padB = 25;
    const cW = W - padL - padR, cH = H - padT - padB;

    // Determine visible range
    let visData = DATA;
    let xMin = 0, xMax = TARGET;
    if (currentZoom < TARGET && DATA.length > 0) {{
        const lastN = DATA[DATA.length - 1].n;
        xMin = Math.max(0, lastN - currentZoom);
        xMax = Math.max(lastN, currentZoom);
        visData = DATA.filter(d => d.n > xMin);
    }}

    const xRange = xMax - xMin || 1;
    const x = n => padL + ((n - xMin) / xRange) * cW;
    const y = pct => padT + cH - (pct / 100) * cH;

    // Clear
    ctx.fillStyle = '#050505';
    ctx.fillRect(0, 0, W, H);

    // Grid
    ctx.strokeStyle = '#1a1a1a';
    ctx.lineWidth = 1;
    ctx.font = '9px -apple-system, sans-serif';
    ctx.textAlign = 'right';
    for (const pct of [0, 25, 50, 75, 100]) {{
        const yy = y(pct);
        ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(W - padR, yy); ctx.stroke();
        ctx.fillStyle = '#404040';
        ctx.fillText(pct + '%', padL - 4, yy + 3);
    }}

    // X-axis labels
    ctx.textAlign = 'center';
    ctx.fillStyle = '#404040';
    const step = xRange <= 25 ? 5 : xRange <= 60 ? 10 : xRange <= 150 ? 25 : 100;
    for (let n = Math.ceil(xMin / step) * step; n <= xMax; n += step) {{
        ctx.fillText(n, x(n), H - 5);
    }}

    // Reference line (closed source)
    const theirY = y(THEIR_SCORE);
    ctx.strokeStyle = '#4338ca';
    ctx.lineWidth = 1;
    ctx.setLineDash([6, 4]);
    ctx.globalAlpha = 0.6;
    ctx.beginPath(); ctx.moveTo(padL, theirY); ctx.lineTo(W - padR, theirY); ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha = 0.8;
    ctx.fillStyle = '#818cf8';
    ctx.font = '8px -apple-system, sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText('Claude 4.5 Opus (' + THEIR_SCORE + '%)', W - padR - 2, theirY - 5);
    ctx.globalAlpha = 1;

    if (visData.length === 0) {{
        ctx.fillStyle = '#404040';
        ctx.font = '12px -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Waiting for results…', W / 2, H / 2);
        return;
    }}

    const last = visData[visData.length - 1];
    const above = last.pass_rate > THEIR_SCORE;
    const lineColor = above ? '#22c55e' : '#f59e0b';

    // Gradient fill
    const grad = ctx.createLinearGradient(0, padT, 0, padT + cH);
    grad.addColorStop(0, above ? 'rgba(34,197,94,0.12)' : 'rgba(245,158,11,0.12)');
    grad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(x(visData[0].n), y(visData[0].pass_rate));
    visData.forEach(d => ctx.lineTo(x(d.n), y(d.pass_rate)));
    ctx.lineTo(x(visData[visData.length - 1].n), y(0));
    ctx.lineTo(x(visData[0].n), y(0));
    ctx.closePath();
    ctx.fill();

    // Score line
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    visData.forEach((d, i) => {{
        const px = x(d.n), py = y(d.pass_rate);
        if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }});
    ctx.stroke();

    // Dots
    visData.forEach(d => {{
        const px = x(d.n), py = y(d.pass_rate);
        ctx.beginPath();
        ctx.arc(px, py, currentZoom <= 50 ? 4 : 2.5, 0, Math.PI * 2);
        ctx.fillStyle = d.result === 'pass' ? 'rgba(34,197,94,0.6)' : 'rgba(239,68,68,0.6)';
        ctx.fill();
    }});

    // Current score label
    const lx = x(last.n), ly = y(last.pass_rate);
    ctx.beginPath();
    ctx.arc(lx, ly, 5, 0, Math.PI * 2);
    ctx.fillStyle = lineColor;
    ctx.fill();
    ctx.strokeStyle = '#050505';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = lineColor;
    ctx.font = 'bold 11px -apple-system, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(last.pass_rate + '%', lx + 9, ly + 4);

    // Store dot positions for tooltip
    canvas._dots = visData.map(d => ({{ x: x(d.n), y: y(d.pass_rate), d }}));
}}

// Tooltip
const canvas = document.getElementById('chart');
const tooltip = document.getElementById('tooltip');
canvas.addEventListener('mousemove', e => {{
    if (!canvas._dots) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    let closest = null, minDist = 30;
    canvas._dots.forEach(dot => {{
        const dist = Math.hypot(dot.x - mx, dot.y - my);
        if (dist < minDist) {{ minDist = dist; closest = dot; }}
    }});
    if (closest) {{
        const d = closest.d;
        const icon = d.result === 'pass' ? '✓' : '✗';
        const color = d.result === 'pass' ? '#22c55e' : '#ef4444';
        tooltip.innerHTML = '<span style="color:' + color + '">' + icon + '</span> #' + d.n + ' ' + d.task_id + '<br><span style="color:#888">Pass rate: ' + d.pass_rate + '%</span>';
        tooltip.style.display = 'block';
        tooltip.style.left = Math.min(closest.x + 12, rect.width - 180) + 'px';
        tooltip.style.top = (closest.y - 10) + 'px';
    }} else {{
        tooltip.style.display = 'none';
    }}
}});
canvas.addEventListener('mouseleave', () => {{ tooltip.style.display = 'none'; }});

// Initial draw
drawChart();
window.addEventListener('resize', drawChart);

function toggleTaskSort() {{
    const list = document.getElementById('task-list');
    const btn = document.getElementById('sort-btn');
    const rows = Array.from(list.children);
    rows.reverse();
    list.innerHTML = '';
    rows.forEach(r => list.appendChild(r));
    btn.textContent = btn.textContent === 'Oldest first' ? 'Newest first' : 'Oldest first';
}}
</script>

</body>
</html>"""


def _render_log(worker_id: str) -> str:
    log_text = _read_log(worker_id, tail=500)
    log_text = log_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{worker_id}</title>
<meta http-equiv="refresh" content="10">
<style>body {{ font-family: monospace; background: #050505; color: #525252; padding: 1rem; font-size: 0.7rem; line-height: 1.4; }}
a {{ color: #60a5fa; }} pre {{ white-space: pre-wrap; word-break: break-all; }}</style>
</head><body><a href="/">← dashboard</a> &middot; {worker_id} (last 500 lines, refreshes every 10s)<pre>{log_text}</pre></body></html>"""


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            html_content = _render_html(_gather_data())
        elif path.startswith("/log/"):
            html_content = _render_log(path[5:])
        elif path == "/api/data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(_gather_data(), indent=2).encode())
            return
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html_content.encode())

    def log_message(self, *a):
        pass


def main():
    global ITERATION
    port = 8080
    args = sys.argv[1:]
    skip = False
    for i, arg in enumerate(args):
        if skip:
            skip = False
            continue
        if arg == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            skip = True
        elif not arg.startswith("--"):
            ITERATION = arg

    print(f"Dashboard: http://localhost:{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
