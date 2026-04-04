"""Add more workers to a running auto-improve iteration.

Usage:
    # Single key, 3 workers:
    python -m auto_improve.add_workers --iteration 5 --workers 3 --start-id 0

    # Multiple keys (3 workers per key):
    python -m auto_improve.add_workers --iteration 5 --keys-file auto_improve/api_keys.json

api_keys.json format:
    [
      {"key": "abc123...", "base_url": "https://api.z.ai/api/coding/paas/v4"},
      {"key": "def456...", "base_url": "https://api.z.ai/api/coding/paas/v4"}
    ]

Each key gets 3 workers. 2 keys = 6 workers, 3 keys = 9 workers, etc.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

WORKERS_PER_KEY = 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Add workers to a running iteration")
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--keys-file", type=str, help="JSON file with API keys (3 workers per key)")
    parser.add_argument("--workers", type=int, help="Number of workers (single-key mode)")
    parser.add_argument("--start-id", type=int, default=0, help="Starting worker ID")
    args = parser.parse_args(argv)

    results_root = Path(f"auto_improve/iterations/{args.iteration:03d}/results").resolve()
    manifest_path = results_root / "_task_manifest.json"
    predictions_dir = results_root / "_swebench_predictions"
    config_path = results_root / "_run_config.json"
    worker_log_dir = results_root / "_worker_logs"

    if not manifest_path.exists():
        print(f"ERROR: No manifest at {manifest_path}", file=sys.stderr)
        return 1
    if not config_path.exists():
        print(f"ERROR: No config at {config_path}", file=sys.stderr)
        return 1

    worker_log_dir.mkdir(parents=True, exist_ok=True)

    # Build list of (worker_id, api_key, base_url) assignments
    assignments: list[tuple[str, str, str]] = []

    if args.keys_file:
        keys = json.loads(Path(args.keys_file).read_text())
        worker_id = args.start_id
        for key_entry in keys:
            if isinstance(key_entry, str):
                api_key = key_entry
                base_url = os.environ.get("ZHIPU_BASE_URL", "https://api.z.ai/api/coding/paas/v4")
            else:
                api_key = key_entry["key"]
                base_url = key_entry.get("base_url", "https://api.z.ai/api/coding/paas/v4")
            for _ in range(WORKERS_PER_KEY):
                assignments.append((f"worker-{worker_id}", api_key, base_url))
                worker_id += 1
        print(f"{len(keys)} keys × {WORKERS_PER_KEY} workers = {len(assignments)} workers", file=sys.stderr)
    elif args.workers:
        api_key = os.environ.get("ZHIPU_API_KEY", "")
        base_url = os.environ.get("ZHIPU_BASE_URL", "https://api.z.ai/api/coding/paas/v4")
        if not api_key:
            print("ERROR: --workers requires ZHIPU_API_KEY env var", file=sys.stderr)
            return 1
        for i in range(args.workers):
            assignments.append((f"worker-{args.start_id + i}", api_key, base_url))
    else:
        parser.error("Provide either --keys-file or --workers")

    # Register worker IDs in manifest
    from evals.manifest import TaskManifest
    from evals.parallel import _record_pidfile_workers
    manifest = TaskManifest.load(manifest_path)
    new_ids = [wid for wid, _, _ in assignments]
    manifest.reserve_specific_worker_ids(new_ids)

    summary = manifest.summary()
    print(f"Manifest: {summary}", file=sys.stderr)
    print(f"Launching {len(assignments)} workers: {', '.join(new_ids)}", file=sys.stderr)

    # Env setup
    hermes_root = str(Path(__file__).resolve().parent.parent)
    megaplan_root = str(Path(hermes_root).parent / "megaplan")
    worker_procs: list[tuple[str, subprocess.Popen[str], Path]] = []

    for worker_id, api_key, base_url in assignments:
        # Write per-worker config
        original = json.loads(config_path.read_text(encoding="utf-8"))
        original["workers"] = 1
        original["swebench_patch_only"] = True
        original["evals_to_run"] = []
        workspace_dir = Path(original.get("workspace_dir", "evals/workspaces")).expanduser().resolve()
        original["workspace_dir"] = str(workspace_dir / worker_id)
        original["run_name"] = f"{original.get('run_name', 'parallel')}/{worker_id}"
        original["manifest_path"] = str(manifest_path)
        original["worker_id"] = worker_id
        original["claim_batch_size"] = 3
        original["predictions_dir"] = str(predictions_dir)

        temp_config = Path(tempfile.mktemp(suffix=f"-{worker_id}.json", prefix="swebench-"))
        temp_config.write_text(json.dumps(original, indent=2), encoding="utf-8")

        worker_env = os.environ.copy()
        python_paths = [hermes_root, megaplan_root]
        existing = worker_env.get("PYTHONPATH", "")
        if existing:
            python_paths.append(existing)
        worker_env["PYTHONPATH"] = os.pathsep.join(python_paths)

        # Per-worker API key
        worker_env["ZHIPU_API_KEY"] = api_key
        worker_env["ZHIPU_BASE_URL"] = base_url

        worker_workspace = workspace_dir / worker_id
        worker_hermes_home = worker_workspace / "_hermes_home"
        worker_hermes_home.mkdir(parents=True, exist_ok=True)

        # Copy .env but override API key
        real_env_file = Path.home() / ".hermes" / ".env"
        if real_env_file.exists():
            import shutil
            shutil.copy2(real_env_file, worker_hermes_home / ".env")
            # Override key in the copied .env
            env_text = (worker_hermes_home / ".env").read_text()
            import re
            env_text = re.sub(r'ZHIPU_API_KEY=.*', f'ZHIPU_API_KEY={api_key}', env_text)
            env_text = re.sub(r'ZHIPU_BASE_URL=.*', f'ZHIPU_BASE_URL={base_url}', env_text)
            (worker_hermes_home / ".env").write_text(env_text)

        worker_env["HERMES_HOME"] = str(worker_hermes_home)
        worker_env["PIP_USER"] = "1"
        worker_env["PYTHONUSERBASE"] = str(worker_workspace / "_pip_user")

        stdout_log = open(worker_log_dir / f"{worker_id}.stdout.log", "w")
        stderr_log = open(worker_log_dir / f"{worker_id}.stderr.log", "w")

        proc = subprocess.Popen(
            [sys.executable, "-m", "evals.run_evals", "--config", str(temp_config), "-v"],
            env=worker_env,
            stdout=stdout_log,
            stderr=stderr_log,
            cwd=hermes_root,
            start_new_session=True,
        )
        worker_procs.append((worker_id, proc, temp_config))
        key_prefix = api_key[:8] + "..."
        print(f"  {worker_id} started (PID {proc.pid}, key={key_prefix})", file=sys.stderr)

    _record_pidfile_workers(
        results_root,
        worker_procs,
        loop_pid=None,
        replace_workers=False,
    )

    print(f"\n{len(assignments)} workers launched.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
