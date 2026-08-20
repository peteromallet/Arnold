from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from arnold_pipelines.megaplan._core.state import write_plan_state
from arnold_pipelines.megaplan.store import write_plan_artifact_json


PLAN_DIR = Path(
    "/workspace/critique-ledger-m9-glm-20260723/Arnold/.megaplan/plans/"
    "cl1-contract-ownership-and-m6-20260723-1920"
)
TASK_ID = "T11"
PRIOR_FINALIZE_SHA256 = (
    "296ec2a909c564a6e91d0db6c3d879699ba88f2a09d1d064a588762a0542b2ea"
)
ENVELOPE_DIGEST = (
    "e602d16b035065124f6f4c0a57d1f90f79c1b73f0ae8ec1ab45ac0dad8bdd6dc"
)
QUALITY_BLOCKER_ID = "quality:global:dec573c81401"
VALIDATION_PATH = Path("verification/validation_VJ8_8be4641b95cc.json")
VALIDATION_SHA256 = (
    "85a559fa000f7fd9ec60053e39f3e608ea40c000d4ca61be8c7398fdc784c259"
)
REVIEW_SHA256 = (
    "f1a38ac5ee8b67cd1d899437b4fee0587d6c93e59d71c5900e7b241d7d4573f7"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


state_path = PLAN_DIR / "state.json"
finalize_path = PLAN_DIR / "finalize.json"
review_path = PLAN_DIR / "review.json"
validation_path = PLAN_DIR / VALIDATION_PATH
batch_path = PLAN_DIR / "execute_batches/batch_4/tasks_691802e8547e.json"

state = json.loads(state_path.read_text(encoding="utf-8"))
finalize = json.loads(finalize_path.read_text(encoding="utf-8"))
review = json.loads(review_path.read_text(encoding="utf-8"))
validation = json.loads(validation_path.read_text(encoding="utf-8"))
batch = json.loads(batch_path.read_text(encoding="utf-8"))

assert state.get("current_state") == "done"
assert sha256(finalize_path) == PRIOR_FINALIZE_SHA256
assert sha256(review_path) == REVIEW_SHA256
assert sha256(validation_path) == VALIDATION_SHA256
assert validation.get("status") == "passed" and validation.get("exit_code") == 0

quality = next(
    item
    for item in state["meta"]["quality_gate_resolutions"]
    if item.get("blocker_id") == QUALITY_BLOCKER_ID
)
assert quality.get("resolution") == "fixed"
review_verdict = next(
    item for item in review["task_verdicts"] if item.get("task_id") == TASK_ID
)
assert str(review_verdict.get("reviewer_verdict") or "").lower().startswith("pass")
batch_update = next(
    item for item in batch["task_updates"] if item.get("task_id") == TASK_ID
)
assert batch_update["authority_validation"]["outcome"] == "accepted"
assert batch_update["authority_validation"]["envelope_digest"] == ENVELOPE_DIGEST

core = {
    "schema": "arnold.megaplan.chain_task_projection_reconciliation.v1",
    "task_id": TASK_ID,
    "stale_status": "blocked",
    "reconciled_status": "done",
    "authority_envelope_digest": ENVELOPE_DIGEST,
    "quality_resolution_blocker_id": QUALITY_BLOCKER_ID,
    "validation": {
        "path": str(VALIDATION_PATH),
        "sha256": VALIDATION_SHA256,
    },
    "review_sha256": REVIEW_SHA256,
    "prior_finalize_sha256": PRIOR_FINALIZE_SHA256,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "created_by": "codex-critique-chain-recovery",
    "reason": (
        "Reconcile the stale worker-only blocked projection after the accepted "
        "fenced attempt, passing authoritative VJ8, fixed quality resolution, "
        "and passing final-review task verdict."
    ),
}
receipt = {
    **core,
    "content_sha256": hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest(),
}


def append_receipt(current: dict) -> bool:
    assert current.get("current_state") == "done"
    meta = current.setdefault("meta", {})
    records = meta.setdefault("chain_task_projection_reconciliations", [])
    records[:] = [
        item for item in records if isinstance(item, dict) and item.get("task_id") != TASK_ID
    ]
    records.append(receipt)
    return True


write_plan_state(PLAN_DIR, mode="patch-many", patch={}, mutation=append_receipt)
task = next(item for item in finalize["tasks"] if item.get("id") == TASK_ID)
assert task.get("status") == "blocked"
assert task["authority_validation"]["outcome"] == "accepted"
assert task["authority_validation"]["envelope_digest"] == ENVELOPE_DIGEST
task["status"] = "done"
task["status_reconciliation"] = {
    "schema": receipt["schema"],
    "receipt_sha256": receipt["content_sha256"],
    "stale_status": receipt["stale_status"],
    "reconciled_status": receipt["reconciled_status"],
}
write_plan_artifact_json(PLAN_DIR, "finalize.json", finalize, contract_context=None)

result = {
    "plan_state": json.loads(state_path.read_text(encoding="utf-8"))["current_state"],
    "task_id": TASK_ID,
    "task_status": next(
        item["status"]
        for item in json.loads(finalize_path.read_text(encoding="utf-8"))["tasks"]
        if item.get("id") == TASK_ID
    ),
    "receipt_sha256": receipt["content_sha256"],
    "finalize_sha256": sha256(finalize_path),
}
print(json.dumps(result, sort_keys=True))
