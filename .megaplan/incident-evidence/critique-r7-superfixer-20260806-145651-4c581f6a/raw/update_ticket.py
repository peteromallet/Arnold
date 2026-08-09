import json, sys, hashlib

TICKET = '/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/follow-up-superfixer-v4-20260806-1329.json'

with open(TICKET) as fh:
    ticket = json.load(fh)

# Preserve v4 content; append the two new categories (splitter reference closure, planner-repair recoverability).
appended = [
    {
        "category": "splitter-finalize-task-reference-closure",
        "first_broken_contract": "arnold_pipelines.megaplan.orchestration.task_splitter.split_high_complexity_tasks removes a finalized task ID but publishes neither a typed replacement map nor a reference-closed payload; downstream consumers observe identifiers outside the transformed task set.",
        "missed_backstop": "Finalize has no single pre-publication task-reference-closure assertion across graph, critique custody, validation coverage, sense checks, and user-action fields; feasibility validates only dependency edges and task_feasibility.json can be written before late custody rejection.",
        "evidence": "failure fingerprint 382e25a279dbb2b7784f56d8a0b59eae9422a0625d48c9bb1185aa3fec4a33df (12x dependency_unknown + dependency_graph_invalid, occurrences 2, circuit open); byte-identical read-only reproduction on candidate cfc7d701c18c070ba15679d5279cc943119ec9d4fa412b8ef4d02115a75c76c8.",
        "canonical_owner": "Megaplan finalize contract owner: orchestration/task_splitter.py transform, handlers/finalize.py mutation/publication order, orchestration/task_feasibility.py and critique_custody.py consumers.",
        "machine_readable_contract": "arnold.megaplan.task_reference_closure.v1 (versioned split map: original_id, impl_id, proof_id, per-field mapping semantics, source runtime content/revision, collision diagnostics, closure digest over every typed task-reference family).",
    },
    {
        "category": "planner-repair-circuit-recoverability",
        "first_broken_contract": "handlers/finalize.py::_route_finalize_task_feasibility_failure_to_revise projects circuit_open to blocked without atomically persisting latest_failure.kind=deterministic_phase_failure / resume_cursor={phase:finalize,retry_strategy:repair_phase_contract}, so its own recover-blocked next step lacks the required cursor.",
        "missed_backstop": "No narrow plan-lock/CAS migration exists to re-arm the missing latest_failure/resume_cursor for an already-preserved circuit-open occurrence after an engine-runtime repair; direct state edits are forbidden.",
        "canonical_owner": "graph_admission/control_interface circuit transition owner plus Run Authority/Custody/WBC recovery admission.",
    },
]

ticket['appended_categories_v2'] = appended
ticket['updated_at'] = '2026-08-06T15:40:00Z'
ticket['updated_by_occurrence'] = 'subagent-20260806-145651-4c581f6a'
ticket['superseding_handoff_id'] = 'sha256:bd4967a0f7693eca86061fab0fc3a4943c7a6402d2837a9f666efee7a0c6f0cf'
ticket['prior_content_hash'] = 'sha256:13e0aceb2ccc21dbdf66a75357a66381b8b175b1aa1f2102dc0d66a65507946f'

# semantic content hash: canonical JSON (sorted keys) of the full updated ticket
canon = json.dumps(ticket, sort_keys=True, separators=(',', ':')).encode('utf-8')
semantic = 'sha256:' + hashlib.sha256(canon).hexdigest()
ticket['content_hash'] = semantic
with open(TICKET, 'w') as fh:
    json.dump(ticket, fh, indent=2, sort_keys=True)
    fh.write('\n')

file_sha = 'sha256:' + hashlib.sha256(open(TICKET, 'rb').read()).hexdigest()
print('semantic content hash:', semantic)
print('file sha256:', file_sha)
