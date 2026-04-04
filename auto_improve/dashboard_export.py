"""Export dashboard data to the swe-bench-challenge GitHub Pages repo.

Usage:
    python -m auto_improve.dashboard_export 021
    python -m auto_improve.dashboard_export 021 --push
"""

import json
import subprocess
import sys
from pathlib import Path


def main():
    args = sys.argv[1:]
    push = "--push" in args
    args = [a for a in args if not a.startswith("--")]

    # Set iteration
    if args:
        from auto_improve import dashboard_web
        dashboard_web.ITERATION = args[0]

    from auto_improve.dashboard_web import _gather_data, CLOSED_SOURCE_LEADER

    data = _gather_data()
    # Strip local paths
    for t in data.get("tasks", []):
        t.pop("run_path", None)
    data.pop("worker_logs", None)
    data["closed_source"] = CLOSED_SOURCE_LEADER

    repo_path = Path("/tmp/swe-bench-challenge")
    if not repo_path.exists():
        subprocess.run(["git", "clone", "https://github.com/peteromallet/swe-bench-challenge.git", str(repo_path)], check=True)

    out = repo_path / "data.json"
    out.write_text(json.dumps(data, indent=2))
    print(f"Exported {len(data.get('tasks', []))} tasks to {out}")

    if push:
        subprocess.run(["git", "add", "data.json"], cwd=repo_path, check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo_path)
        if result.returncode != 0:
            subprocess.run(["git", "commit", "-m", f"update scores: {data['passed']}/{data['total_scored']} ({data['pass_rate']}%)"], cwd=repo_path, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=repo_path, check=True)
            print("Pushed to GitHub Pages")
        else:
            print("No changes to push")


if __name__ == "__main__":
    main()
