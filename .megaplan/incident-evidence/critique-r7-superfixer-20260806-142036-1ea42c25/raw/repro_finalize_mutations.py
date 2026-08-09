"""Read-only in-memory reproduction of finalize candidate rejection.

Replays the handler's task-graph mutations against the persisted raw
candidate and runs the deterministic feasibility pass, printing the exact
diagnostics (expected: 12x dependency_unknown + dependency_graph_invalid).

No files are written; the payload is deep-copied and mutated only in memory.
"""
import copy
import json
import sys
from pathlib import Path

ENGINE = "/workspace/runtime-candidates/arnold-r7-fresh-child-20260805"
PLAN_DIR = Path(
    "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/"
    ".megaplan/plans/cl2-wbc-backed-ledger-20260805-2140"
)
CANDIDATE = PLAN_DIR / ".megaplan/worker_tmp/local-strict-artifacts/finalize-15274aaf2cb2445487647129704dcccd.candidate.json"

sys.path.insert(0, ENGINE)

from arnold_pipelines.megaplan.handlers import finalize as F  # noqa: E402
from arnold_pipelines.megaplan.orchestration.task_feasibility import (  # noqa: E402
    compile_task_feasibility,
)
from arnold_pipelines.megaplan.orchestration.validation_jobs import (  # noqa: E402
    compile_validation_jobs,
)

payload = json.loads(CANDIDATE.read_text())
print(f"raw candidate tasks: {len(payload.get('tasks', []))}")

state = {
    "config": {"mode": "code", "project_dir": str(PLAN_DIR.parent.parent.parent)},
    "plan_versions": payload.get("plan_versions") or {},
    "seed_epoch": None,
}
# A minimal plan_versions so _apply_programmatic_coverage can resolve the plan md.
if not state["plan_versions"]:
    state["plan_versions"] = {"current": {"path": "plan.md"}}

p = copy.deepcopy(payload)
try:
    F._ensure_verification_task(p, state)
    if state["config"].get("mode") not in {"doc", "joke"}:
        F._ensure_user_actions_pre_gate_task(p, state)
        F._ensure_user_actions_post_gate_task(p, state)
    try:
        F._apply_programmatic_coverage(p, PLAN_DIR, state)
    except Exception as exc:  # noqa: BLE001
        print(f"NOTE: programmatic coverage skipped: {type(exc).__name__}: {exc}")
    F._normalize_task_complexity(p)
    splitter = F._split_finalize_tasks(p)
    print(f"splitter diagnostics: {splitter}")
    p["validation_jobs"] = compile_validation_jobs(p)
except Exception as exc:  # noqa: BLE001
    print(f"MUTATION STEP FAILED: {type(exc).__name__}: {exc}")
    raise

print(f"mutated tasks: {len(p.get('tasks', []))}")
feasibility = compile_task_feasibility(p, state.get("config", {}))
diags = feasibility.get("diagnostics", [])
print(f"admitted: {feasibility.get('admitted')}")
print(f"diagnostic count: {len(diags)}")
for d in diags:
    print(json.dumps(d))
