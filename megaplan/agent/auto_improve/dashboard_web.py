"""Live SWE-bench comparison dashboard: Open Source vs Closed Source.

Serves the static index.html from swe-bench-challenge repo and generates
data.json on the fly from local experiment results.

Usage:
    python -m auto_improve.dashboard_web 021              # serve iter 021
    python -m auto_improve.dashboard_web 021 --port 3000
"""

import html as html_mod
import json
import sys
import urllib.request
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path("results/auto-improve")
ITERATION = "021"
STATIC_HTML_PATH = Path("/tmp/swe-bench-challenge/index.html")

CLOSED_SOURCE_LEADER = {
    "name": "Claude 4.5 Opus",
    "variant": "high reasoning",
    "score": 76.80,
    "cost_per_task": "$0.75",
    "source": "swebench.com",
}

OPUS_CACHE_PATH = Path("/tmp/opus_per_instance.json")


def _load_opus_per_instance() -> dict[str, bool]:
    """Load Opus per-instance results (download once and cache locally)."""
    if OPUS_CACHE_PATH.exists():
        raw = json.loads(OPUS_CACHE_PATH.read_text())
        return {k: v.get("resolved", False) if isinstance(v, dict) else bool(v) for k, v in raw.items()}

    try:
        url = "https://raw.githubusercontent.com/SWE-bench/swe-bench.github.io/master/data/leaderboards.json"
        data = json.loads(urllib.request.urlopen(url, timeout=30).read())
        opus_results = {}
        for lb in data["leaderboards"]:
            if lb["name"] == "bash-only":
                for r in lb["results"]:
                    if "Claude 4.5 Opus" in r["name"] and "high" in r["name"].lower():
                        opus_results = r.get("per_instance_details", {})
                        break
        OPUS_CACHE_PATH.write_text(json.dumps(opus_results, indent=2))
        return {k: v.get("resolved", False) if isinstance(v, dict) else bool(v) for k, v in opus_results.items()}
    except Exception as e:
        print(f"Warning: could not load Opus per-instance data: {e}")
        return {}


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


# Pricing per token (GLM-5-Code equivalent rates)
_COST_PER_TOKEN = {
    "glm": {"input": 1.20 / 1_000_000, "output": 5.00 / 1_000_000},
    "minimax": {"input": 0.60 / 1_000_000, "output": 2.40 / 1_000_000},
}


def _estimate_task_cost(iter_dir, tid: str) -> float:
    """Estimate cost for a task from trace message character counts."""
    total_cost = 0.0
    for worker_dir in sorted(iter_dir.glob("worker-*")):
        task_dir = worker_dir / tid
        if not task_dir.exists():
            continue
        for run_dir in sorted(task_dir.iterdir()):
            pd = run_dir / "phases"
            if not pd or not pd.exists():
                continue
            for pf in pd.glob("*.json"):
                try:
                    d = json.loads(pf.read_text())
                    model = d.get("model", "")
                    msgs = d.get("trace_messages", [])
                    if not msgs:
                        continue
                    input_chars = sum(len(m.get("content", "") or "") for m in msgs if m.get("role") != "assistant")
                    output_chars = sum(len(m.get("content", "") or "") for m in msgs if m.get("role") == "assistant")
                    for m in msgs:
                        for tc in m.get("tool_calls", []):
                            output_chars += len(str(tc.get("function", {}).get("arguments", "")))
                    input_tokens = input_chars // 4
                    output_tokens = output_chars // 4
                    if "glm" in model.lower() or "zhipu" in model.lower():
                        pricing = _COST_PER_TOKEN["glm"]
                    elif "minimax" in model.lower():
                        pricing = _COST_PER_TOKEN["minimax"]
                    else:
                        pricing = _COST_PER_TOKEN["glm"]
                    total_cost += input_tokens * pricing["input"] + output_tokens * pricing["output"]
                except Exception:
                    pass
    return round(total_cost, 4)


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

        # Estimate cost from trace messages
        task_cost = _estimate_task_cost(iter_dir, tid)

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
            "cost_usd": task_cost,
            "worker": worker,
            "run_path": run_path,
            "scored_at": scored_at,
            "github_url": github_url,
            "issue_description": issue_desc,
            "repo": repo_name,
        })

    # Add unscored tasks from manifest (pending, claimed, escalated, error)
    scored_ids = {t["id"] for t in tasks_data}
    manifest_path = _iter_dir() / "_task_manifest.json"
    preds_dir = _iter_dir() / "_swebench_predictions"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        preds = {p.stem for p in preds_dir.glob("*.jsonl")} if preds_dir.exists() else set()
        for tid, mt in manifest.get("tasks", {}).items():
            if tid in scored_ids:
                continue
            mstatus = mt.get("status", "pending")
            # Determine display status
            if mstatus == "done" and tid not in preds:
                display_status = "retrying"  # was escalated, now requeued
            elif mstatus == "claimed":
                display_status = "running"
            elif mstatus == "error":
                display_status = "error"
            else:
                display_status = "queued"
            # Check if it was previously escalated and build requeue reason
            hist = mt.get("history", [])
            requeue_reasons = []
            for h in hist:
                reason = h.get("reason", "")
                if reason.startswith("retry_escalated"):
                    requeue_reasons.append("Previously escalated (review/gate bug fix)")
                elif reason == "dead_worker" or reason == "dead_pid":
                    requeue_reasons.append("Worker died")
                elif reason == "error_retry":
                    requeue_reasons.append("Error retry")
                elif reason == "escalated_no_patch":
                    requeue_reasons.append("Escalated (no patch)")
            was_escalated = bool(requeue_reasons)
            if was_escalated and display_status == "queued":
                display_status = "retrying"
            requeue_note = requeue_reasons[-1] if requeue_reasons else ""

            tasks_data.append({
                "id": tid,
                "status": display_status,
                "category": requeue_note,
                "explanation": "",
                "pipeline_gap": "",
                "golden_comparison": "",
                "phases": [],
                "total_time_s": 0,
                "gate_iterations": 0,
                "worker": mt.get("worker_id", ""),
                "run_path": "",
                "scored_at": "",
                "github_url": _task_github_url(tid),
                "issue_description": "",
                "repo": _task_repo_name(tid),
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

    last_n = min(5, len(scored_tasks))
    recent = scored_tasks[-last_n:] if last_n else []
    momentum_pct = round(sum(1 for t in recent if t["status"] == "pass") / len(recent) * 100) if recent else 0

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

    recent_pace_hours = 0.0
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

    timed_tasks = [t for t in tasks_data if t["total_time_s"] > 0 and t["status"] in ("pass", "fail")]
    avg_time_s = round(sum(t["total_time_s"] for t in timed_tasks) / len(timed_tasks)) if timed_tasks else 0

    costed_tasks = [t for t in tasks_data if t.get("cost_usd", 0) > 0]
    avg_cost = round(sum(t["cost_usd"] for t in costed_tasks) / len(costed_tasks), 3) if costed_tasks else 0
    total_cost = round(sum(t["cost_usd"] for t in costed_tasks), 2)

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

    # Opus per-task comparison
    opus_per_instance = _load_opus_per_instance()
    our_only = []
    opus_only = []
    both_solved = []
    both_failed = []
    opus_results_map: dict[str, bool] = {}
    for t in tasks_data:
        if t["status"] not in ("pass", "fail"):
            continue
        tid = t["id"]
        we_passed = t["status"] == "pass"
        opus_passed = opus_per_instance.get(tid, False)
        opus_results_map[tid] = opus_passed
        if we_passed and not opus_passed:
            our_only.append(tid)
        elif not we_passed and opus_passed:
            opus_only.append(tid)
        elif we_passed and opus_passed:
            both_solved.append(tid)
        else:
            both_failed.append(tid)

    # Include ALL Opus results (full 500) for chart overlay
    all_opus_results = {tid: bool(v) for tid, v in opus_per_instance.items()}

    opus_comparison = {
        "our_only": our_only,
        "opus_only": opus_only,
        "both_solved": both_solved,
        "both_failed": both_failed,
        "opus_results": all_opus_results,
    }

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
        "avg_cost_usd": avg_cost,
        "total_cost_usd": total_cost,
        "manifest_pending": manifest_pending,
        "manifest_claimed": manifest_claimed,
        "manifest_done": manifest_done,
        "manifest_total": manifest_total,
        "worker_logs": worker_logs,
        "closed_source": CLOSED_SOURCE_LEADER,
        "opus_comparison": opus_comparison,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "probability": _compute_probability(passed, total, 500, CLOSED_SOURCE_LEADER["score"]),
        "probability_task_aware": _compute_task_aware_probability(
            tasks_data, opus_per_instance, manifest_path, 500, CLOSED_SOURCE_LEADER["score"],
        ),
    }


def _compute_probability(passes: int, total: int, target: int, opus_score: float) -> dict:
    """Compute probability of beating Opus using Beta-Binomial Monte Carlo (server-side)."""
    import numpy as np
    if total < 3:
        return {"beat_prob": 0, "p10": 0, "p50": 0, "p90": 0}
    a = passes + 1
    b = (total - passes) + 1
    remaining = target - total
    opus_frac = opus_score / 100
    N = 20000

    rng = np.random.default_rng(42)
    p_samples = rng.beta(a, b, N)
    future_passes = rng.binomial(remaining, p_samples)
    final_rates = (passes + future_passes) / target

    beat_prob = int(np.mean(final_rates > opus_frac) * 100)
    p10 = round(float(np.percentile(final_rates, 10)) * 100, 1)
    p50 = round(float(np.percentile(final_rates, 50)) * 100, 1)
    p90 = round(float(np.percentile(final_rates, 90)) * 100, 1)

    # Histogram for distribution plot
    bins = 50
    hist, edges = np.histogram(final_rates, bins=bins, range=(0.5, 1.0))
    hist_data = [int(x) for x in hist]

    return {"beat_prob": beat_prob, "p10": p10, "p50": p50, "p90": p90, "hist": hist_data}


def _compute_task_aware_probability(
    tasks_data: list, opus_per_instance: dict, manifest_path, target: int, opus_score: float,
) -> dict:
    """Task-aware probability using conditional pass rates based on Opus results.

    Uses our observed pass rate conditional on Opus's result for the same task.
    Opus failing a task is a difficulty signal — regardless of whether we've
    attempted it yet.
    """
    import numpy as np
    scored = [t for t in tasks_data if t["status"] in ("pass", "fail")]
    if len(scored) < 10:
        return {"beat_prob": 0, "p10": 0, "p50": 0, "p90": 0, "hist": []}

    # Split our results by whether Opus passed the same task
    we_pass_opus_pass = sum(1 for t in scored if t["status"] == "pass" and opus_per_instance.get(t["id"], False))
    we_total_opus_pass = sum(1 for t in scored if opus_per_instance.get(t["id"], False))
    we_pass_opus_fail = sum(1 for t in scored if t["status"] == "pass" and not opus_per_instance.get(t["id"], False))
    we_total_opus_fail = sum(1 for t in scored if not opus_per_instance.get(t["id"], False))

    # Count remaining tasks by Opus result
    scored_ids = {t["id"] for t in scored}
    try:
        import json as _json
        manifest = _json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        all_task_ids = set(manifest.get("tasks", {}).keys())
    except Exception:
        all_task_ids = scored_ids
    remaining_ids = all_task_ids - scored_ids
    remaining_opus_pass = sum(1 for tid in remaining_ids if opus_per_instance.get(tid, False))
    remaining_opus_fail = len(remaining_ids) - remaining_opus_pass

    current_passes = sum(1 for t in scored if t["status"] == "pass")
    opus_frac = opus_score / 100
    N = 20000

    rng = np.random.default_rng(42)
    # Beta posteriors for conditional rates
    a1, b1 = we_pass_opus_pass + 1, (we_total_opus_pass - we_pass_opus_pass) + 1
    a2, b2 = we_pass_opus_fail + 1, (we_total_opus_fail - we_pass_opus_fail) + 1

    p_when_opus_pass = rng.beta(a1, b1, N)
    p_when_opus_fail = rng.beta(a2, b2, N)
    future_passes = rng.binomial(remaining_opus_pass, p_when_opus_pass) + rng.binomial(remaining_opus_fail, p_when_opus_fail)
    final_rates = (current_passes + future_passes) / target

    beat_prob = int(np.mean(final_rates > opus_frac) * 100)
    p10 = round(float(np.percentile(final_rates, 10)) * 100, 1)
    p50 = round(float(np.percentile(final_rates, 50)) * 100, 1)
    p90 = round(float(np.percentile(final_rates, 90)) * 100, 1)

    bins = 50
    hist, _ = np.histogram(final_rates, bins=bins, range=(0.5, 1.0))
    hist_data = [int(x) for x in hist]

    return {"beat_prob": beat_prob, "p10": p10, "p50": p50, "p90": p90, "hist": hist_data}


def _read_log(worker_id: str, tail: int = 500) -> str:
    log_file = _iter_dir() / "_worker_logs" / f"{worker_id}.stderr.log"
    if not log_file.exists():
        return f"Log not found: {log_file}"
    lines = log_file.read_text(errors="replace").splitlines()
    return "\n".join(lines[-tail:])


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
            # Serve the static index.html
            if STATIC_HTML_PATH.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(STATIC_HTML_PATH.read_bytes())
            else:
                self.send_error(404, f"Static HTML not found: {STATIC_HTML_PATH}")
            return
        elif path == "/data.json":
            # Generate fresh data on each request
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(_gather_data(), indent=2).encode())
            return
        elif path == "/api/data":
            # Legacy endpoint
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(_gather_data(), indent=2).encode())
            return
        elif path.startswith("/traces/") and path.endswith(".json"):
            # Serve trace files from the swe-bench-challenge repo
            trace_file = STATIC_HTML_PATH.parent / path.lstrip("/")
            if trace_file.exists():
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(trace_file.read_bytes())
            else:
                self.send_error(404, f"Trace not found: {trace_file}")
            return
        elif path.startswith("/log/"):
            html_content = _render_log(path[5:])
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_content.encode())
            return
        else:
            self.send_error(404)

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
    print(f"Serving static HTML from: {STATIC_HTML_PATH}")
    print(f"Data generated live from: {_iter_dir()}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
