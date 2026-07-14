"""M5 evidence reconciliation through Megaplan's durable artifact APIs.

This utility never edits a completion receipt.  It runs exact-head checks,
writes a new S4 execution batch with the resulting task evidence, and runs the
current canonical full-suite command through ``suite_runner`` so the same
content-addressed result can be admitted by the receipt provider.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
from typing import Any

from arnold_pipelines.megaplan._core.io import (
    atomic_write_json,
    batch_artifact_index,
    execute_batch_artifact_path,
    list_batch_artifacts,
)
from arnold_pipelines.megaplan.orchestration.suite_runner import (
    append_suite_run,
    latest_run_for_phase,
    run_suite,
)


HANDOFF = Path(__file__).resolve().parent
PROJECT = HANDOFF.parents[4]
PLANS = PROJECT / ".megaplan" / "plans"
WORKTREE_ROOT = Path("/workspace")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run_current_suite() -> int:
    command = f"{shlex.quote(sys.executable)} -m pytest --tb=no -q --no-header -rA"
    # ``suite_runner`` deliberately preserves the caller environment.  A
    # resident/cloud operator normally has the editable engine checkout on
    # PYTHONPATH, which would make this subject suite import a different tree.
    # Pin the subject checkout for the duration of the spawned suite and then
    # restore the operator environment.
    previous_pythonpath = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = str(PROJECT)
    try:
        result = run_suite(
            PROJECT,
            {
                "plan_dir": str(HANDOFF),
                "test_command": command,
                "test_verification_timeout": 3600,
            },
            phase="verification",
            deadline_seconds=time.monotonic() + 3600,
            idle_seconds=600,
        )
    finally:
        if previous_pythonpath is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = previous_pythonpath
    append_suite_run(HANDOFF, result)
    record = latest_run_for_phase(HANDOFF, "verification") or {}
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if result.status == "passed" else 1


def _git(*args: str, cwd: Path = PROJECT) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def _ensure_worktree(label: str, head: str) -> Path:
    worktree = WORKTREE_ROOT / f"custody-ra-evidence-{label}"
    if not worktree.exists():
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree), head],
            cwd=PROJECT,
            check=True,
        )
    actual = _git("rev-parse", "HEAD", cwd=worktree)
    if actual != head:
        raise RuntimeError(f"{worktree}: expected {head}, found {actual}")
    if _git("status", "--porcelain", cwd=worktree):
        raise RuntimeError(f"{worktree}: exact-head evidence worktree is dirty")
    return worktree


def _task_specs() -> list[dict[str, Any]]:
    py = shlex.quote(sys.executable)
    return [
        {
            "label": "m1",
            "plan": "sprint-1-authority-freeze-and-20260710-1935",
            "head": "ea93131022012be309107db2a9bf686554b03a4c",
            "tasks": {
                "T15": [
                    f"{py} -c \"from pathlib import Path; t=Path('.megaplan/initiatives/runauthority-epic/notes/sprint-1-enforcement-handoff.md').read_text(); assert all(x in t for x in ('compatibility', 'dispatch', 'recovery', 'Sprint 2'))\"",
                    "git diff --name-only df95784af96d367f6bb2e6942c89ec62c6a3bcb3..ea93131022012be309107db2a9bf686554b03a4c",
                ],
                "T16": [
                    f"{py} -m py_compile arnold_pipelines/megaplan/authority/__init__.py arnold_pipelines/megaplan/authority/batch_scope.py arnold_pipelines/megaplan/authority/binding.py arnold_pipelines/megaplan/authority/inventory.py arnold_pipelines/megaplan/authority/views.py arnold_pipelines/megaplan/cli/__init__.py arnold_pipelines/megaplan/cloud/status_format.py arnold_pipelines/megaplan/cloud/status_snapshot.py arnold_pipelines/megaplan/execute/batch.py arnold_pipelines/megaplan/execute/merge.py arnold_pipelines/run_authority/__init__.py arnold_pipelines/run_authority/contracts.py arnold_pipelines/run_authority/reducer.py",
                ],
                "T17": [
                    f"{py} -m pytest -q tests/arnold_pipelines/megaplan/test_authority_batch_scope.py tests/arnold_pipelines/megaplan/test_authority_inventory.py tests/arnold_pipelines/megaplan/test_authority_inventory_cli.py tests/arnold_pipelines/megaplan/test_authority_views.py tests/arnold_pipelines/run_authority/test_contracts.py tests/arnold_pipelines/run_authority/test_reducer.py tests/cloud/test_status_snapshot.py tests/execute/test_merge_scope.py",
                    "git diff --name-only df95784af96d367f6bb2e6942c89ec62c6a3bcb3..ea93131022012be309107db2a9bf686554b03a4c",
                ],
            },
        },
        {
            "label": "m2",
            "plan": "sprint-2-dispatch-grants-and-20260710-2200",
            "head": "710a4609d53c78038e39f9167c09487912da5ba2",
            "tasks": {
                "T17": [
                    f"{py} -m pytest -q tests/arnold_pipelines/megaplan/test_authority_dispatch_grants.py tests/execute/test_authority_dispatch_validation.py tests/arnold_pipelines/megaplan/test_authority_batch_scope.py tests/execute/test_merge_scope.py",
                    f"{py} -m pytest -q tests/arnold_pipelines/megaplan/test_authority_views.py tests/execute/test_execute_frontier_authority.py tests/arnold_pipelines/megaplan/test_cloud_status_authority_shadow.py tests/arnold_pipelines/megaplan/test_chain_authority_shadow.py",
                ],
            },
        },
        {
            "label": "m3",
            "plan": "sprint-3-consumer-migration-20260711-0130",
            "head": "432760d13abb69a32a77e7bb1e79c1136d4ce533",
            "tasks": {
                "T16": [
                    f"{py} -m pytest -v tests/arnold_pipelines/run_authority/test_reducer.py",
                ],
            },
        },
    ]


def _run_historical_tasks() -> int:
    for spec in _task_specs():
        worktree = _ensure_worktree(spec["label"], spec["head"])
        plan_dir = PLANS / spec["plan"]
        task_ids = sorted(spec["tasks"])
        existing = [batch_artifact_index(path) or 0 for path in list_batch_artifacts(plan_dir)]
        batch_index = max(existing, default=0) + 1
        artifact_path = execute_batch_artifact_path(plan_dir, batch_index, task_ids)
        evidence_dir = plan_dir / "verification" / "m5-reconciliation"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        updates: list[dict[str, Any]] = []
        all_commands: list[str] = []
        for task_id, commands in spec["tasks"].items():
            started = _utc_now()
            chunks: list[str] = []
            for command in commands:
                env = os.environ.copy()
                env["PYTHONPATH"] = str(worktree)
                completed = subprocess.run(
                    ["bash", "-lc", command],
                    cwd=worktree,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                chunks.append(
                    "\n".join(
                        [
                            f"$ {command}",
                            f"exit_code={completed.returncode}",
                            completed.stdout,
                            completed.stderr,
                        ]
                    )
                )
                if completed.returncode != 0:
                    raise RuntimeError(
                        f"{spec['label']} {task_id} failed ({completed.returncode}): {command}"
                    )
            log_path = evidence_dir / f"{task_id.lower()}-{spec['head'][:12]}.log"
            log_path.write_text(
                "\n".join(
                    [
                        f"started_at={started}",
                        f"finished_at={_utc_now()}",
                        f"cwd={worktree}",
                        f"head_sha={spec['head']}",
                        *chunks,
                    ]
                ),
                encoding="utf-8",
            )
            relative_log = log_path.relative_to(plan_dir).as_posix()
            updates.append(
                {
                    "task_id": task_id,
                    "status": "done",
                    "executor_notes": (
                        "M5 exact-head reconciliation reran the declared obligation "
                        f"against landed revision {spec['head']}."
                    ),
                    "files_changed": [],
                    "commands_run": list(commands),
                    "evidence_files": [relative_log],
                    "head_sha": spec["head"],
                }
            )
            all_commands.extend(commands)
        payload = {
            "schema_version": 1,
            "output": "M5 exact-head historical task evidence reconciled successfully.",
            "files_changed": [],
            "commands_run": all_commands,
            "deviations": [],
            "task_updates": updates,
            "sense_check_acknowledgments": [],
            "head_sha": spec["head"],
            "reconciled_at": _utc_now(),
            "reconciliation_kind": "m5_exact_landed_head",
        }
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(artifact_path, payload, _plan_dir=plan_dir)
        print(artifact_path)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run-current-suite", "run-historical-tasks"))
    args = parser.parse_args()
    if args.action == "run-current-suite":
        return _run_current_suite()
    return _run_historical_tasks()


if __name__ == "__main__":
    raise SystemExit(main())
