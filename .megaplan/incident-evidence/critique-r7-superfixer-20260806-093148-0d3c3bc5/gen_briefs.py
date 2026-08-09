#!/usr/bin/env python3
"""Generate the 10 Flash investigator briefs for the r7 superfixer swarm."""
import os

EVID = "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5"
BRIEFS = EVID + "/briefs"
os.makedirs(BRIEFS, exist_ok=True)

PREAMBLE = """You are a READ-ONLY DeepSeek V4 Flash evidence investigator for one bounded
question in an R7 Superfixer swarm. You may NOT mutate anything.

INCIDENT IDENTITY (repeat in your report):
- session: critique-ledger-accountability-v3-r7-launch-20260805
- workspace: /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold
- chain spec: .megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/chain.yaml
- plan: cl2-wbc-backed-ledger-20260805-2140 (plan dir: /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140)
- chain state: /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/.chains/chain-880bd6e04632.json
- occurrence: occ_critique_r7_superfixer_retry_20260806_v1_70c522f651d6859e134250ee
- evidence pack (read first): {EVID}/evidence-pack.md
- Sol stage-1 (report contract): {EVID}/sol-stage1.md

PROHIBITIONS (absolute): no mutation of any file; no SSH writes; no launch,
resume, rebind, restart, retry, fork, notify, enqueue, claim, or acknowledge;
no credential exposure (never print tokens/env secrets); no agent delegation;
no megaplan/git/chain lifecycle commands; no package installs; no network
writes. Read-only inspection only, using only the allowlisted commands below
(plus stat/sha256sum/sed/rg/git show/diff in read-only form, GIT_OPTIONAL_LOCKS=0).

REPORT CONTRACT: follow Sol stage-1 section D exactly (FLASH REPORT fields
1..18: question_id, verdict supported|refuted|undetermined, investigated_claim,
vantage, utc_window, artifacts with exists/type/size/mtime/sha256/role,
commands with cwd/command/exit, producer->consumer->persistence->policy trace,
adherence_classification ADHERENCE|MISSING_STRUCTURE, missing_or_contradictory
_structure, evidence for/against, confidence high|medium|low + basis,
immediate_decision_informed, durable_decision_informed, safety_observations,
unresolved_questions). Verdict rules: supported = affirmative evidence;
refuted = affirmative contradictory evidence; absence/ambiguity = undetermined.
Hash every inspected artifact. Report UTC times exactly. Never claim ancestry,
code equivalence, or a passing reproduction is execution authority.
"""

QUESTIONS = {
"fq-01": {
 "claim": "Plan v5 has a complete, unambiguous mapping from every selector to its producer, declared task output, persisted artifact, and finalize consumer (selector/task-output declaration integrity).",
 "artifacts": [
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/plan_v1.md .. plan_v5.md",
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/faults.json",
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/gate_carry.json",
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/state.json (plan_versions, history)",
 ],
 "commands": [
   "rg --files /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140",
   "rg -n --hidden 'selector|task[_ -]?output|declared[_ -]?output|producer|consumer|artifact|CF-0B506E1EDCD92E90C192' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140",
   "sed -n '1,320p' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/plan_v5.md",
   "sha256sum <each enumerated file>; stat --format='%n|%s|%y' <each enumerated file>",
 ],
 "decision": "Whether Horizon A may preserve the accepted plan or must stop for structural plan adjudication (missing selector/output structure).",
},
"fq-02": {
 "claim": "Commit 77b76e3a4 is the complete and uniquely relevant behavioral delta for the finalize critique_finding_unresolved exception (runtime A vs B custody path).",
 "artifacts": [
   "/workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/orchestration/critique_custody.py (runtime A)",
   "/workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines/megaplan/orchestration/critique_custody.py (runtime B)",
   "commits d5848010695e and 77b76e3a4 in /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/.git",
 ],
 "commands": [
   "rg -n '_resolution_for_finding|accepted_tradeoff|gate_expected|fixed_claim|verified_plan_mutation' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/orchestration/critique_custody.py",
   "rg -n '_resolution_for_finding|accepted_tradeoff|gate_expected|fixed_claim|verified_plan_mutation' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines/megaplan/orchestration/critique_custody.py",
   "GIT_OPTIONAL_LOCKS=0 git -C /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4 show --format=fuller --stat --name-only 77b76e3a4",
   "GIT_OPTIONAL_LOCKS=0 git -C /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4 diff --no-ext-diff d5848010695e 77b76e3a4 -- arnold_pipelines/megaplan/orchestration/critique_custody.py",
   "sed -n '1,120p' <the test changed by 77b76e3a4 (find via the commit --stat)>",
 ],
 "decision": "Whether the original failure is conclusively version-bound and whether runtime B is behaviorally sufficient at the custody layer (does NOT decide execution authority).",
},
"fq-03": {
 "claim": "The chain driver stop (liveness lease status=stopped at 00:53:46.682Z) was a clean terminal handoff with no retained authority or partially committed effects from the three failed finalize attempts.",
 "artifacts": [
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/.chains/chain-880bd6e04632.json",
   "/workspace/.megaplan/cloud-sessions/critique-ledger-accountability-v3-r7-launch-20260805.liveness-lease.json",
   "/workspace/.megaplan/cloud-sessions/critique-ledger-accountability-v3-r7-launch-20260805.liveness-fence.json",
   "/workspace/.megaplan/cloud-sessions/critique-ledger-accountability-v3-r7-launch-20260805.json",
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/cloud-chain-critique-ledger-accountability-v3-r7-launch-20260805.log",
   "events.ndjson under the plan dir (seq 3087..3098 zone)",
 ],
 "commands": [
   "ps -p 629623 -o pid=,ppid=,lstart=,etime=,stat=,args= (expect empty output)",
   "sed -n '1,340p' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/.chains/chain-880bd6e04632.json",
   "rg -n --hidden '629623|stopped|lease|finalize|00:53:46|authoritative|runner' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan",
   "rg -n 'status.?=.stopped|lease|finalize|shutdown|resume|retry' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan",
   "stat/sha256sum on each artifact above",
 ],
 "decision": "Whether same-occurrence finalize can be considered at all, or whether stale authority/partial effects require quarantine or migration.",
},
"fq-04": {
 "claim": "Repair request 74403266d5cb0592770cffe5f8c0d31c627dff7ef62577994808df588c603bd7 followed a complete, closed lifecycle for the earlier revise-phase failure, and no authority seam/reuse conflict blocks a NEW blocker-specific repair request for the finalize failure.",
 "artifacts": [
   "/workspace/.megaplan/repair-queue/requests/74403266d5cb0592770cffe5f8c0d31c627dff7ef62577994808df588c603bd7.json",
   "/workspace/.megaplan/repair-queue/decisions/20260806T001308Z-b416ed0172abd76b4f519d29a4b035f6367487b4313030499808eb7af1ce9a4d.json",
   "/workspace/.megaplan/repair-queue/occurrence-claims/ and /attempts/ (search for this request and the r7 session)",
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/authority/ (run-authority.sqlite3, wbc.sqlite3, custody/)",
 ],
 "commands": [
   "rg -n --hidden '74403266|repair[_ -]?request|run_authority|run-authority|custody|wbc|work.?based' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan /workspace/.megaplan/repair-queue",
   "rg -n 'repair[_ -]?request|run_authority|custody|WBC|work.?based' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines/megaplan/cloud",
   "stat/sha256sum/sed on each request/decision/claim/attempt artifact found",
 ],
 "decision": "Whether Horizon A must mint a fresh blocker-specific repair request through the canonical producer, or a valid existing authority record covers the finalize blocker.",
},
"fq-05": {
 "claim": "The v5 gate PROCEED state (00:53:17Z) is CAS-protected/immutable, and finalize is occurrence-idempotent and re-entrant for the same occurrence after the three failed invocations (no committed side effects).",
 "artifacts": [
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/gate.json (and gate_v5.json, gate_carry.json, gate_output.json)",
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/phase_result.json",
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/state.json",
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/events.ndjson (seq 3087..3098)",
   "finalize/custody/idempotency source under /workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan",
 ],
 "commands": [
   "rg -n --hidden 'PROCEED|00:53:17|occurrence|compare.?and.?swap|CAS|expected[_ -]?version|generation|idempot|finalize|attempt' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140 /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/.chains/chain-880bd6e04632.json",
   "rg -n 'compare.?and.?swap|CAS|expected[_ -]?version|occurrence|idempot|finalize' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan",
   "stat/sha256sum/sed on gate+finalize artifacts; tail -c 20000 events.ndjson",
 ],
 "decision": "Same-occurrence resume vs authority-approved migrated child vs quarantine (CAS/idempotency proof is required for same-occurrence).",
},
"fq-06": {
 "claim": "No notification intent or effect was persisted for this session's blocker, and the dedupe/key state that would govern any later authorized notification is unambiguous.",
 "artifacts": [
   "/workspace/.megaplan/cloud-sessions/critique-ledger-accountability-v3-r7-launch-20260805.json (and sibling r7 marker files)",
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/.chains/chain-880bd6e04632.json",
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/cloud-chain-critique-ledger-accountability-v3-r7-launch-20260805.log",
   "notification/outbox source under runtime A and B arnold_pipelines/megaplan",
 ],
 "commands": [
   "rg -n --hidden 'notif|notify|outbox|intent|effect|dedup|idempotency.?key|delivery|recipient' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan /workspace/.megaplan/cloud-sessions",
   "rg -n 'notif|notify|outbox|intent|effect|dedup|delivery' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines/megaplan",
   "stat/sha256sum/sed on any notification artifact found",
 ],
 "decision": "Whether notification must remain suppressed (no new notification on this poll) and whether future exactly-once delivery is possible.",
},
"fq-07": {
 "claim": "Runtime B (77b76e3a4, the currently installed runtime) does NOT satisfy the chain's require_editable_runtime_match policy as recorded in chain state, and no canonical rebind/migration record authorizes A->B for this session.",
 "artifacts": [
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/.chains/chain-880bd6e04632.json (metadata.execution_binding, runtime_binding, execution_environment)",
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/chain.yaml (driver.require_editable_runtime_match)",
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/fresh_child_admission.json",
   "runtime binding source under /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines/megaplan",
 ],
 "commands": [
   "GIT_OPTIONAL_LOCKS=0 git -C /workspace/runtime-candidates/arnold-r7-fresh-child-20260805 rev-parse HEAD",
   "GIT_OPTIONAL_LOCKS=0 git -C /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4 rev-parse HEAD",
   "GIT_OPTIONAL_LOCKS=0 git -C /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4 merge-base --is-ancestor d5848010695e 77b76e3a4",
   "rg -n --hidden 'require_editable_runtime_match|runtime|d5848010695e|77b76e3a4|e8b12504130bd283333891ffd5e14f126bb5cd6558892153b4b533a2417fe5e6|rebind|migrat|child' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan",
   "rg -n 'require_editable_runtime_match|runtime.?match|rebind|migrat' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines/megaplan",
 ],
 "decision": "Horizon A in-place consideration vs authority-approved runtime migration/rebind record; ancestry alone is NOT authorization.",
},
"fq-08": {
 "claim": "The CF-0B506E1EDCD92E90C192 / critique_finding_unresolved / accepted_tradeoff finalize failure is isolated to this session and no sibling session shows the same failure signature or a proven recovery precedent.",
 "artifacts": [
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/ (the whole launch tree, bounded search)",
   "commit 77b76e3a4 metadata and its test in runtime B",
 ],
 "commands": [
   "rg -n --hidden 'CF-0B506E1EDCD92E90C192|critique_finding_unresolved|remains .accepted_tradeoff.|carry verified tradeoffs across gate iterations' /workspace/critique-ledger-accountability-v3-r7-launch-20260805",
   "GIT_OPTIONAL_LOCKS=0 git -C /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4 show --format=fuller --stat 77b76e3a4",
   "stat/sha256sum on any matching sibling artifact",
 ],
 "decision": "Isolated occurrence vs systemic defect; whether a recovery precedent with explicit authority exists (a sibling precedent is NOT authority for this chain).",
},
"fq-09": {
 "claim": "The 'TypeError: emit_transition() got multiple values for keyword argument transition' lines in the chain log are non-fatal telemetry/error-recording noise, NOT a separate integrity blocker; the finalize failure is fully explained by the custody resolver.",
 "artifacts": [
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/cloud-chain-critique-ledger-accountability-v3-r7-launch-20260805.log (search around the TypeError lines and the finalize attempts)",
   "work_ledger source: /workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/observability/work_ledger.py and the B copy",
 ],
 "commands": [
   "rg -n --hidden -C 12 'work_ledger|emit_transition|TypeError' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan",
   "rg -n -C 10 'def emit_transition|emit_transition\\(' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines",
   "stat/sha256sum on the chain log and work_ledger files",
 ],
 "decision": "Whether ledger integrity is a separate stop gate or whether custody success makes a bounded retry safe (causal classification).",
},
"fq-10": {
 "claim": "No persisted quota, fence, lock, lease, reservation, or concurrency-owner record owned by a live process blocks a bounded retry of finalize for this occurrence.",
 "artifacts": [
   "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan (locks, fences, leases, .plan.lock, boundary_receipts)",
   "/workspace/.megaplan/cloud-sessions/ (r7 marker/liveness files)",
   "/workspace/.megaplan/repair-queue/active-claims/ and occurrence-claims/",
   "policy source under /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines/megaplan",
 ],
 "commands": [
   "rg --files /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan | rg 'lock|fence|lease|quota|reservation|claim'",
   "rg -n --hidden 'quota|fence|lock|lease|owner|reservation|budget|attempt.?limit|retry.?limit|expires|stale' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan /workspace/.megaplan/cloud-sessions",
   "rg -n 'quota|fence|lock|lease|reservation|attempt.?limit|retry.?limit' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines/megaplan",
   "stat/sha256sum/sed on each relevant control artifact; check whether any lock owner PID is alive",
 ],
 "decision": "Whether a bounded retry is administratively admissible or must stop for authority/lock ownership resolution.",
},
}

for stem, q in QUESTIONS.items():
    body = PREAMBLE.format(EVID=EVID)
    body += "\n\nQUESTION: " + stem.upper() + "\n"
    body += "investigated_claim: " + q["claim"] + "\n\n"
    body += "ARTIFACTS TO INSPECT:\n" + "\n".join("- " + a for a in q["artifacts"]) + "\n\n"
    body += "ALLOWED READ-ONLY COMMANDS:\n" + "\n".join("- " + c for c in q["commands"]) + "\n\n"
    body += "DECISION THIS REPORT INFORMS: " + q["decision"] + "\n"
    body += "\nRemember: report only evidence; never propose or execute a patch; do not dispatch other agents; never expose credentials; classify adherence vs missing structure; give confidence and both immediate and durable decisions."
    with open(f"{BRIEFS}/{stem}.md", "w") as f:
        f.write(body)
    print("wrote", stem, len(body))
