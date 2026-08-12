# Raw census command outputs (read-only, box 159.69.51.216)

Captured 2026-08-11T13:20:10Z UTC. Referenced from docs/fixer-recovery-evidence/receipts.md.
Digest of THIS file: computed below (external digest).

## R11 raw — wrapper SHA-256 (bin vs engine tree)

Command (cwd = /workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/cloud/wrappers):
`for w in arnold-watchdog arnold-repair-loop arnold-repair-trigger arnold-meta-repair-loop arnold-runtime-create; do echo -n "$w "; sha256sum /usr/local/bin/$w | awk '{print $1}'; echo -n "$w "; sha256sum $w | awk '{print $1}'; done`

Output (verbatim):
```
arnold-watchdog 985c4e945fb6476d16ae78a09ad593aea5472a99016e8c0c7a253ca13f58fda3
arnold-watchdog f50bbf31dbd45eae5014f43923c56ff151d6c7c125e20c0871d755f0d487cba0
arnold-repair-loop 89debf5899b7b8cfe43459ab3f7b49f0378eba1a649979b73e894feebe941afb
arnold-repair-loop ed02b6ffed09cee7f4ebd2742575dadc50b8642c90d85b80f368d03d8d6dfb53
arnold-repair-trigger c54a2030b071f8070a3996ed65add3f3109322a257bed56108f21689964f5592
arnold-repair-trigger 5906c4bdd691f055fa7ced652eb20a348b5ebd1996a1abdbe1cdaca91b097724
arnold-meta-repair-loop 0900f59ee472d063afc2d60ee34a8fe184d569fb40f64d7e7111abe5f7edd78d
arnold-meta-repair-loop 87aaec10d54ea64e060a7b31a6d3343732d04743f990aa3f5ae9f011a00ac18c
arnold-runtime-create 6525a01104232f70ae97b9f2fbb6b2c0e93631be8b08760142f79d929efacdb6
arnold-runtime-create 6525a01104232f70ae97b9f2fbb6b2c0e93631be8b08760142f79d929efacdb6
```
Exit 0. 4-of-5 MISMATCH (watchdog, repair-loop, repair-trigger, meta-repair-loop differ; runtime-create matches).

## R14 raw — counts

Command:
`ls /workspace/.megaplan/repair-queue/active-claims/ | wc -l; ls /workspace/arnold/.megaplan/resident/scheduled_jobs/ | wc -l; ls /workspace/arnold/.megaplan/resident/schedules/heads/ | wc -l; date -u +%Y-%m-%dT%H:%M:%SZ`

Output (verbatim):
```
66
73
53
2026-08-11T13:20:10Z
```
Exit 0.

## R15 raw — claim-lock breakdown

Command:
`cd /workspace/.megaplan/repair-queue/active-claims && echo total=$(ls | wc -l); echo lockfiles=$(ls | grep -c \.lock$); echo lockdirs=$(find . -maxdepth 1 -type d -name "*.lock" | wc -l); echo managedbind=$(ls | grep -c managed-run-bind); echo nonlock=$(ls | grep -vc \.lock); echo snapshot=$(date -u +%Y-%m-%dT%H:%M:%SZ)`

Output (verbatim, snapshot 2026-08-11T13:19:46Z):
```
total=66
lockfiles=21
lockdirs=0
managedbind=45
nonlock=0
snapshot=2026-08-11T13:19:46Z
```
Exit 0. All 66 files 0-byte (unowned).

## R16 raw — GC schedule-store lines

Command:
`grep -n 'SCHEDULE_STORES\|refs/pull\|_schedule_store_references\|not a reference' /workspace/omp-replaces-hermes/Arnold/arnold_pipelines/megaplan/cloud/wrappers/arnold-gc-sweep`

Output (verbatim, head):
```
79:  SCHEDULE_STORES=("/workspace/arnold/.megaplan/resident/scheduled_jobs" "/workspace/.megaplan/ops/schedules")
84:_schedule_store_references() {
86:  # configured store references either; 1 otherwise. A missing store dir is
87:  # not a reference.
89:  for store in "${SCHEDULE_STORES[@]}"; do
94:  ...
106:  ...
174:  PULL_HEADS="$(git -C "$ROOT" ls-remote "$REMOTE" "refs/pull/*/head" ...)"
185:  ...
```
Exit 0. NOTE: schedule HEADS store (/workspace/arnold/.megaplan/resident/schedules/heads/) is NOT in SCHEDULE_STORES; missing stores are skipped (line 87), grep errors suppressed.

## R1-R10 raw outputs (captured 2026-08-11 09:50-12:15Z, verbatim)

### R1 — manifests inventory
Command: `ls -la /workspace/.megaplan/*.json`
Output: 5 files (9b319e-shannon-b-prepare.json, 9b319e-shannon-b-probe.json, cloud-status-snapshot.json, cloud-status-snapshot.previous.json, megaplan-maintenance.json). Exit 0.

### R2 — session markers
Command: `for f in /workspace/.megaplan/cloud-sessions/*.json; do python3 -c 'json.load ... session/completed_count/milestone_count/current_plan_name/last_state/updated_at'`
Output: 22+ sessions; BLOCKED: custody-control-plane-20260714 (8/10), megaplan-maintenance (0/6); PAUSED: critique-ledger v2/v3/r2/r3/r4/r5 (0/4), m10-stable (0/2), discord-resident-lifecycle-corrective (1/6), vj24-migration (0/1); DONE: extension-foundation-completion (1/1), v3-r7 (3/4), spine (13), runauthority-epic-cloud (3), withings (4), superpom (4). Exit 0.

### R3 — chain engine_roots
Command: `for f in /workspace/*/Arnold/.megaplan/plans/.chains/chain-*.json; do python3 -c 'engine_root/project_root/target_head/target_base'`
Output: 19 chain files; 17 distinct chains; 9 MISSING roots, 1 NULL, 2 SHARED, 1 CONFLICTED, 1 RESIDENT, 4 EMPTY-SHELL, 1 PROJECT-ROOT, 1 PRESENT+SPLIT. Exit 0. (Full table in census-S1-S4 S2.)

### R4 — runtime candidate git state
Command: `for d in /workspace/runtime-candidates/*/; do git -C $d rev-parse HEAD; git -C $d symbolic-ref --short HEAD; git -C $d status --porcelain | wc -l`
Output: 12 candidates (full matrix in census-S9-S12). Exit 0.

### R5 — origin fixer/reconcile refs
Command: `git ls-remote origin | grep -E 'fixer/|reconcile/'`
Output: fixer/critique-epoch-invalidation-20260806 49af598c0; fixer/fixer-unification-20260807 bf18142fc; fixer/megaplan-maintenance-20260811 f410585d56; NO reconcile/* refs. Exit 0.

### R6 — watchdog log + repair queue
Command: `tail -200 /tmp/watchdog.log | grep -A2 -B2 megaplan-maintenance; ls /workspace/.megaplan/repair-queue/requests/ | wc -l; grep -l megaplan-maintenance /workspace/.megaplan/repair-queue/requests/*`
Output: per-sweep 'repair request claim failed; refusing dispatch ... status=missing_identity' + 'mechanical relaunch fenced pending phase-contract repair custody ... dispatch=unavailable'; requests=299; ONE match (stale 346786db8fe6... Jul 11, plan m1-containment-and-truthful-20260711-0021). Exit 0.

### R7 — full manifest
Command: `cat /workspace/.megaplan/megaplan-maintenance.json`
Output: epic_id=megaplan-maintenance, runtime_id=megaplan-maintenance-20260811, state=active, base.commit=f410585d56, editable_install_path="", epic.branch=fixer/megaplan-maintenance-20260811, epic.expected_head=f410585d56, epic.runtime_root=/workspace/runtime-candidates/megaplan-maintenance, epic.repair_bin=<root>/arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop, epic.venv_path=<root>/.venv, generation=1. Exit 0.

### R8 — occurrence-claims / attempts / decisions
Command: `ls /workspace/.megaplan/repair-queue/occurrence-claims/ | wc -l; ls /workspace/.megaplan/repair-queue/attempts/ | wc -l; ls -lat /workspace/.megaplan/repair-queue/attempts/ | head -4; ls -lat /workspace/.megaplan/repair-queue/decisions/ | head -4`
Output: occurrence-claims=0; attempts=137 (latest 20260803T154311Z); decisions latest 20260807T175517Z. Exit 0.

### R9 — superfixer schedule states
Command: `for f in /workspace/arnold/.megaplan/resident/schedules/heads/sched_superfixer_*; do python3 -c 'schedule_id/state/revision'`
Output: sched_superfixer_hourly_global=CANCELLED; sched_superfixer_hourly_v2=CANCELLED; sched_superfixer_r7_reconcile_20260807=EXHAUSTED; sched_superfixer_r7_relaunch_20260807=EXHAUSTED; sched_critique_r7_superfixer_babysit_20260806_v1=PAUSED. Exit 0.

### R10 — reconcile ref count + candidate count
Command: `git for-each-ref | grep -c reconcile; ls /workspace/runtime-candidates/ | wc -l`
Output: 0; 12. Exit 0.
