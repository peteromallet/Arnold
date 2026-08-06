import json, hashlib, sys
sys.path.insert(0, "/workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4")
from arnold_pipelines.megaplan.cloud.wrappers.repair_delegation import build_repair_delegation

failure_payload = ("critique_finding_unresolved: finding CF-0B506E1EDCD92E90C192 / flag CF-0B506E1EDCD92E90C192 "
                   "remains 'accepted_tradeoff'; it needs a traceable plan mutation plus verification, "
                   "or an evidence-backed invalidation")
blocker_hash = "sha256:" + hashlib.sha256(failure_payload.encode()).hexdigest()

target = {
    "environment": "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold",
    "session": "critique-ledger-accountability-v3-r7-launch-20260805",
    "chain": "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140",
    "plan_revision": "sha256:4537c985a9e8f1258af71d97d1d631b8ba6d0bcfc83b9a56fbd29cb327160f46",
    "phase": "finalize",
    "task": "phase:finalize",
    "attempt": "",  # no canonical finalize attempt record exists (phase_result.json is gate; no finalize step receipt)
    "normalized_failure_kind": "phase_failed",
    "blocker_or_phase_result_hash": blocker_hash,
    "fence": "runner-fence:1",
    "chain_identity": "sha256:37112335cf82d55cc9ca4edd2a51105f8511713faeef16ee964dccba735fa168",
}

delegation = build_repair_delegation(
    caller_kind="operator_trigger",
    caller_id="occ_critique_r7_superfixer_retry_20260806_v1_70c522f651d6859e134250ee",
    target=target,
)
result = {
    "outcome": "zero_authority_rejected" if delegation is None else "delegation_built",
    "delegation_built": delegation is not None,
    "reason_if_rejected": "exact F01 repair-occurrence tuple cannot be completed from canonical owners: "
                          "no canonical finalize attempt record exists (attempt field empty); per "
                          "arnold_pipelines/megaplan/cloud/wrappers/repair_delegation.py every F01 field "
                          "must be a non-empty string from a canonical owner; labels/liveness/projection "
                          "are not authority.",
    "target_attempted": target,
    "occurrence": "occ_critique_r7_superfixer_retry_20260806_v1_70c522f651d6859e134250ee",
}
with open("/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/repair-producer-attempt.json", "w") as f:
    json.dump(result, f, indent=1, sort_keys=True)
print(json.dumps(result, indent=1))
