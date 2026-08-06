## A. BROKEN vs HYPOTHESIZED

This adjudication uses the supplied evidence record without executing commands or touching artifacts.

### Definitely broken

1. **Finalize is deterministically incompatible with the chain’s bound runtime A.**

   - Runtime A:
     `/workspace/runtime-candidates/arnold-r7-fresh-child-20260805`
     at `d5848010695e`.
   - Its `arnold_pipelines/megaplan/orchestration/critique_custody.py` lacks the relaxation for:
     `status == "accepted_tradeoff" && gate_expected && fixed_claim`.
   - A read-only reproduction against the real plan data raises the observed `critique_finding_unresolved` for `CF-0B506E1EDCD92E90C192`.
   - The same failure occurred three times after the v5 `PROCEED` result.
   - Primary evidence:
     [evidence-pack.md](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/evidence-pack.md).

2. **Custody persistence for the finding is not closed under runtime A’s policy.**

   - [faults.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/faults.json) records:
     `accepted_tradeoff`, `severity=significant`, `addressed_in=plan_v2.md`,
     `resolution.kind=fixed`, but no `gate_resolution` and `verified=false`.
   - The v5 gate’s `accepted_tradeoffs` does not carry the finding.
   - [gate_carry.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/gate_carry.json) has no entry for it.
   - The plan mutation claim therefore exists, but the exact verification/carry structure expected by A does not.

3. **The chain has no live authoritative executor.**

   - [chain-880bd6e04632.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/.chains/chain-880bd6e04632.json) and the evidence pack place the driver, PID `629623`, dead.
   - The liveness lease became `stopped` at `2026-08-06T00:53:46.682Z`.
   - No fresh activity exists after approximately `00:53:46Z`.

4. **There is no recovery authority in flight for this blocker.**

   - No repair request was created for the finalize failure.
   - Request `74403266...` belongs to an earlier revise-phase failure, predates the blocker, and completed its useful lifecycle when the run self-recovered.
   - It cannot silently confer authority over this later finalize occurrence.

5. **The accepted plan is stranded despite a successful gate.**

   - The final gate returned `PROCEED` at `2026-08-06T00:53:17Z`.
   - Finalize then failed repeatedly and the only runner stopped.
   - Thus “accepted” is durable evidence of the gate result, but not evidence of completed finalize custody.

### Hypothesized or not yet established

1. **Runtime B is eligible to continue this exact chain occurrence.**

   Runtime B resolves all 95 findings, but missing evidence includes the execution-binding policy result, `require_editable_runtime_match` evaluation, and an authorized rebind/migration record.

2. **Finalize can safely be re-invoked for the same occurrence.**

   Missing evidence: occurrence/CAS keys, completed side effects from the three failed attempts, idempotency guarantees, and atomicity boundaries between custody, ledger, WBC, and notification persistence.

3. **The plan’s selector and task-output declarations are complete.**

   A v5 `PROCEED` supports semantic acceptance, but does not by itself prove every selector, declared output, producer edge, and persisted artifact is structurally intact.

4. **The `work_ledger.emit_transition` TypeError is causal.**

   Its exact stack, arguments, handling boundary, and temporal relationship to the custody exception have not been established here. It may be fatal, secondary, or telemetry-only.

5. **No fence, quota, stale lock, or notification dedupe state would block or distort a retry.**

   The supplied facts do not inventory those artifacts.

6. **Runtime A’s defect is the only blocker.**

   B’s zero-failure custody sweep strongly supports this for finding resolution, but does not exercise chain authority, CAS, ledger, notification, locking, or finalize side effects.

## B. ROOT HYPOTHESES

### 1. Runtime A’s custody implementation is the direct cause

**Support:** The exact missing branch is identified; the real data reproduces the observed exception under A; B adds that branch and resolves all 95 findings.

**Falsifier:** A bounded source/commit comparison shows A already executes an equivalent branch on this path, or a side-effect-free reproduction using the exact persisted inputs still fails under B with the same exception and finding.

### 2. The gate-to-finalize carry seam persisted insufficient verification structure

**Support:** The registry says `accepted_tradeoff` with a fixed claim, while `verified=false`, `gate_resolution` is absent, and neither the v5 accepted-tradeoff list nor `gate_carry.json` contains the flag. Runtime A cannot reconcile that combination.

**Falsifier:** The exact canonical artifact consumed by finalize contains a valid gate resolution or carry entry for `CF-0B506E1EDCD92E90C192`, with provenance proving A read it during each failed attempt.

### 3. The chain remains stuck because its authority loop stopped and no recovery request replaced it

**Support:** The driver is dead, its lease is stopped, activity ceased immediately after the failures, and no blocker-specific repair request exists.

**Falsifier:** A fresh authoritative lease, runner record, or post-blocker repair request is found with a valid Run Authority/Custody/WBC handoff and activity after `00:53:46.682Z`.

### 4. Runtime identity policy prevents directly substituting B for A

**Support:** The chain launched under A’s content identity. B is A plus one commit, but ancestry and behavioral compatibility do not prove authority-equivalent identity.

**Falsifier:** The binding policy and persisted chain records explicitly permit B for this occurrence, or an already-authorized canonical rebind/migration record names B’s commit and content identity.

### 5. A second re-entry or orchestration blocker would survive the custody fix

**Support:** Three failed finalize attempts, a stopped lease, the reported ledger TypeError anomaly, and unknown lock/quota/notification state create unverified side-effect and re-entry boundaries.

**Falsifier:** Read-only traces prove finalize is occurrence-idempotent and CAS-protected; all prior attempts stopped before effects; the ledger anomaly is non-causal; and all relevant fences, quotas, locks, and notification records are clear.

## C. FLASH QUESTIONS

All commands below are an allowlist for investigators, not commands executed in this pass. No redirection, file creation, package execution, cache generation, network access, or lifecycle command is permitted.

### FQ-01 — Selector and task-output declaration integrity

**Question:** Does plan v5 have a complete, unambiguous mapping from every selector to its producer, declared task output, persisted artifact, and finalize consumer?

**Inspect:**

- `/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/`
- `plan_v1.md` through `plan_v5.md`
- `faults.json`
- `gate_carry.json`
- Every selector/task/output manifest enumerated inside that directory.

**Allowed commands:**

```text
rg --files /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140
rg -n --hidden 'selector|task[_ -]?output|declared[_ -]?output|producer|consumer|artifact|CF-0B506E1EDCD92E90C192' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140
sed -n '1,260p' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/plan_v5.md
stat --format='%n|%s|%y' <each-enumerated-file>
sha256sum <each-enumerated-file>
```

**Decision:** Whether Horizon A may preserve the accepted plan or must stop for structural plan adjudication.

**Report contract:** Section D, plus a row per selector containing selector, producer, declared output, persisted path, consumer, and missing/contradictory edge.

### FQ-02 — Runtime A/B finalize custody path

**Question:** Is commit `77b76e3a4` the complete and uniquely relevant behavioral delta for this finalize exception?

**Inspect:**

- Runtime A and B copies of:
  `arnold_pipelines/megaplan/orchestration/critique_custody.py`
- Commit `d5848010695e`
- Commit `77b76e3a4`
- The exact test changed by `77b76e3a4`, identified from that commit.

**Allowed commands:**

```text
rg -n '_resolution_for_finding|accepted_tradeoff|gate_expected|fixed_claim|verified_plan_mutation' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/orchestration/critique_custody.py
rg -n '_resolution_for_finding|accepted_tradeoff|gate_expected|fixed_claim|verified_plan_mutation' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines/megaplan/orchestration/critique_custody.py
GIT_OPTIONAL_LOCKS=0 git -C /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4 show --format=fuller --stat --name-only 77b76e3a4
GIT_OPTIONAL_LOCKS=0 git -C /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4 diff --no-ext-diff d5848010695e 77b76e3a4 -- arnold_pipelines/megaplan/orchestration/critique_custody.py
sed -n '<bounded-range>' <exact-test-path-from-commit>
```

**Decision:** Whether the original failure is conclusively version-bound and whether B is behaviorally sufficient at the custody layer. It does not decide execution authority.

**Report contract:** Section D, plus branch predicate, input fields, returned resolution under A/B, and changed-test coverage.

### FQ-03 — Driver stop semantics and retry safety

**Question:** Was `stopped` a clean terminal handoff after finalize failure, or can the old occurrence retain authority or partially completed effects?

**Inspect:**

- [chain-880bd6e04632.json](/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/.chains/chain-880bd6e04632.json)
- Lease artifacts referenced by that chain record.
- The exact chain log path recorded in the chain state or evidence pack.
- A/B orchestration code implementing driver shutdown, lease states, finalize, and recovery.

**Allowed commands:**

```text
stat --format='%n|%s|%y' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/.chains/chain-880bd6e04632.json
sha256sum /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/.chains/chain-880bd6e04632.json
sed -n '1,320p' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/.chains/chain-880bd6e04632.json
rg -n --hidden '629623|stopped|lease|finalize|00:53:46|authoritative|runner' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan
rg -n 'status.?=.stopped|lease|finalize|shutdown|resume|retry' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan
ps -p 629623 -o pid=,ppid=,lstart=,etime=,stat=,args=
```

**Decision:** Whether same-occurrence finalize could even be considered, or whether stale authority/partial effects require quarantine or migration.

**Report contract:** Section D, plus a UTC event timeline and an effect-boundary table for each failed finalize attempt.

### FQ-04 — Repair queue, Run Authority, Custody, and WBC seam

**Question:** What exact lifecycle did request `74403266...` follow, and is there a supported authority seam for a new finalize blocker without reusing that request?

**Inspect:**

- All `.megaplan` records containing `74403266`.
- Repair queue/index/request/effect records found by that lookup.
- Chain state and plan custody/WBC artifacts.
- A/B source implementing repair requests, Run Authority, Custody, and WBC handoffs.

**Allowed commands:**

```text
rg -n --hidden '74403266|repair[_ -]?request|Run Authority|run_authority|Custody|custody|WBC|work.?based' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan
rg -n 'repair[_ -]?request|run_authority|custody|WBC|work.?based' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines/megaplan
stat --format='%n|%s|%y' <each-request-and-seam-artifact>
sha256sum <each-request-and-seam-artifact>
sed -n '<bounded-range>' <each-request-and-seam-artifact>
```

**Decision:** Whether stage 2 must request freshly minted authority, or whether a valid existing blocker-specific authority record exists.

**Report contract:** Section D, plus request ID, occurrence, phase, created/claimed/completed timestamps, authority holder, custody input/output, WBC persistence, and terminal status.

### FQ-05 — Accepted-state CAS and finalize re-entrancy

**Question:** Is the v5 `PROCEED` state immutable/CAS-protected, and is finalize idempotent for the same occurrence after three failed invocations?

**Inspect:**

- Chain state.
- v5 gate result identified under the plan directory.
- Gate/carry/custody artifacts.
- A/B finalize, occurrence, CAS, idempotency, and transition code.

**Allowed commands:**

```text
rg -n --hidden 'PROCEED|00:53:17|occurrence|compare.?and.?swap|CAS|expected[_ -]?version|generation|idempot|finalize|attempt' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140 /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/.chains/chain-880bd6e04632.json
rg -n 'compare.?and.?swap|CAS|expected[_ -]?version|occurrence|idempot|finalize' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines/megaplan
stat --format='%n|%s|%y' <gate-and-finalize-artifacts>
sha256sum <gate-and-finalize-artifacts>
sed -n '<bounded-range>' <gate-and-finalize-artifacts-and-source>
```

**Decision:** Same-occurrence resume versus authority-approved migrated child versus quarantine.

**Report contract:** Section D, plus CAS key, expected/current version, occurrence ID, idempotency key, committed effects per attempt, and rollback/abandon semantics.

### FQ-06 — Notification intent, effects, and dedupe custody

**Question:** Did any attempt persist notification intent or effect, and what dedupe key would govern a later authorized notification?

**Inspect:**

- Session `.megaplan` records.
- Chain state.
- Chain log named by the evidence.
- Notification/outbox/custody source in runtime A and B.

**Allowed commands:**

```text
rg -n --hidden 'notif|notify|outbox|intent|effect|dedup|idempotency.?key|delivery|recipient' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan
rg -n 'notif|notify|outbox|intent|effect|dedup|delivery' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines/megaplan
stat --format='%n|%s|%y' <each-notification-artifact>
sha256sum <each-notification-artifact>
sed -n '<bounded-range>' <each-notification-artifact>
```

**Decision:** Whether notification must remain suppressed, is already complete, or could later occur exactly once under fresh authority.

**Report contract:** Section D, plus intent ID, effect ID, dedupe key, occurrence, recipient class, timestamps, and proof of intent-to-effect linkage.

### FQ-07 — Runtime execution binding and migration/rebind authority

**Question:** Does B satisfy `require_editable_runtime_match` for this chain, or does the A→B boundary require an explicit migrated-child/rebind record?

**Inspect:**

- Chain state and runtime identity fields.
- Any binding, runtime-selection, rebind, migration, or child-chain records in session `.megaplan`.
- A/B Git identities.
- Source implementing `require_editable_runtime_match`.

**Allowed commands:**

```text
GIT_OPTIONAL_LOCKS=0 git -C /workspace/runtime-candidates/arnold-r7-fresh-child-20260805 rev-parse HEAD
GIT_OPTIONAL_LOCKS=0 git -C /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4 rev-parse HEAD
GIT_OPTIONAL_LOCKS=0 git -C /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4 merge-base --is-ancestor d5848010695e 77b76e3a4
rg -n --hidden 'require_editable_runtime_match|runtime|d5848010695e|77b76e3a4|e8b12504130bd283333891ffd5e14f126bb5cd6558892153b4b533a2417fe5e6|rebind|migrat|child' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan
rg -n 'require_editable_runtime_match|runtime.?match|rebind|migrat' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines/megaplan
```

**Decision:** Horizon A in-place consideration versus authority-approved runtime migration. Ancestry alone must not be reported as authorization.

**Report contract:** Section D, plus launched identity, installed identity, policy predicate, evaluated inputs, result, and any rebind/migration authority record.

### FQ-08 — Sibling-session incidence

**Question:** Is this same finding/error combination isolated, or has another session encountered the same accepted-tradeoff finalize failure?

**Inspect:**

- `/workspace/critique-ledger-accountability-v3-r7-launch-20260805/`
- Its `.megaplan` chain states, logs, plans, and incident-evidence directories only.
- Runtime B commit/test history for the defect signature.

**Allowed commands:**

```text
rg -n --hidden 'CF-0B506E1EDCD92E90C192|critique_finding_unresolved|remains .accepted_tradeoff.|carry verified tradeoffs across gate iterations' /workspace/critique-ledger-accountability-v3-r7-launch-20260805
GIT_OPTIONAL_LOCKS=0 git -C /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4 show --format=fuller --stat 77b76e3a4
stat --format='%n|%s|%y' <each-matching-sibling-artifact>
sha256sum <each-matching-sibling-artifact>
```

**Decision:** Isolated occurrence versus systemic defect, and whether any proven recovery precedent exists. A sibling action is not authority for this chain.

**Report contract:** Section D, plus one row per sibling session: session, chain, runtime, phase, exact signature, outcome, and whether its recovery had explicit authority.

### FQ-09 — `work_ledger.emit_transition` TypeError

**Question:** What exact call caused the TypeError, and was it causal, secondary during error recording, or non-fatal telemetry?

**Inspect:**

- The exact chain log referenced by chain state/evidence pack.
- Chain state around the three finalize attempts.
- Every A/B source file defining or invoking `work_ledger.emit_transition`.

**Allowed commands:**

```text
rg -n --hidden -C 12 'work_ledger|emit_transition|TypeError' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan
rg --files /workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines
rg -n -C 10 'def emit_transition|emit_transition\(' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines
stat --format='%n|%s|%y' <exact-chain-log-and-ledger-artifacts>
sha256sum <exact-chain-log-and-ledger-artifacts>
```

**Decision:** Whether ledger integrity is a separate stop gate and whether custody success alone could ever make a bounded retry safe.

**Report contract:** Section D, plus full exception type/message, bounded stack frames, call arguments by field name, handling boundary, preceding custody result, subsequent persisted transition, and causal classification.

### FQ-10 — Quotas, fences, locks, and stale ownership

**Question:** Does any persisted quota, fence, lock, lease, reservation, or concurrency-owner record prohibit a bounded retry?

**Inspect:**

- Session `.megaplan`.
- `.megaplan/plans/.chains/`.
- Lease and repair-queue locations referenced by chain state/source.
- A/B policy code interpreting those artifacts.

**Allowed commands:**

```text
rg --files /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan
rg -n --hidden 'quota|fence|lock|lease|owner|reservation|budget|attempt.?limit|retry.?limit|expires|stale' /workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan
rg -n 'quota|fence|lock|lease|reservation|attempt.?limit|retry.?limit' /workspace/runtime-candidates/arnold-r7-fresh-child-20260805-77b76e3a4/arnold_pipelines/megaplan
stat --format='%n|%s|%y' <each-relevant-control-artifact>
sha256sum <each-relevant-control-artifact>
sed -n '<bounded-range>' <each-relevant-control-artifact-and-policy-source>
```

**Decision:** Whether retry consideration is administratively admissible or must stop for authority/lock ownership resolution.

**Report contract:** Section D, plus control type, scope, owner, generation, acquired/expires UTC, policy interpretation, and whether clearing it would require mutation.

## D. COMPARABLE-REPORT CONTRACT

Every Flash report must use this exact field order:

```text
FLASH REPORT
1. question_id:
2. verdict: supported | refuted | undetermined
3. investigated_claim:
4. vantage:
   - hostname/container:
   - workspace:
   - runtime_or_commit:
   - investigator:
5. utc_window:
   - started:
   - ended:
6. artifacts:
   - absolute_path:
     exists: yes | no
     type:
     size_bytes:
     mtime_utc:
     sha256:
     role: producer | consumer | persistence | policy | log | authority
7. commands:
   - cwd:
     exact_command:
     started_utc:
     ended_utc:
     exit_code:
     stdout_summary:
     stderr_summary:
8. trace:
   - producer:
     produced_value_or_key:
     consumer:
     consumed_value_or_key:
     persistence:
     persisted_value_or_key:
     policy:
     predicate_and_result:
9. adherence_classification: ADHERENCE | MISSING_STRUCTURE
10. missing_or_contradictory_structure:
11. evidence_supporting_verdict:
12. evidence_against_verdict:
13. confidence: high | medium | low
14. confidence_basis:
15. immediate_decision_informed:
16. durable_decision_informed:
17. safety_observations:
18. unresolved_questions:
```

Rules:

- `supported` means the inspected evidence affirmatively supports the question’s investigated claim.
- `refuted` requires affirmative contradictory evidence.
- Absence, inaccessible artifacts, ambiguous producers, or incomplete provenance require `undetermined`, not `refuted`.
- `ADHERENCE` requires a complete producer → consumer → persistence → policy trace with matching identity and occurrence.
- Any absent or untraceable required edge is `MISSING_STRUCTURE`, even if the final value appears plausible.
- Hash every inspected persistent artifact. For a missing path, report `exists: no`, and use `size_bytes`, `mtime_utc`, and `sha256` as `not-applicable`.
- Record commands verbatim, including working directory and nonzero exits.
- Do not normalize timestamps across occurrences; report UTC values exactly.
- Separate immediate incident admissibility from durable design/remediation conclusions.
- No report may characterize ancestry, code equivalence, or a passing reproduction as execution authority.

## E. SAFETY CONSTRAINTS AND SOL-ONLY JUDGEMENT CALLS

### Immutable scope

The following must remain untouched:

- The complete plan directory and every plan version.
- Chain state, chain logs, leases, fences, locks, quotas, and attempt records.
- Repair queues and request lifecycle records.
- Fault registry, gate results, `gate_carry.json`, custody, WBC, and work-ledger records.
- Notification intent, outbox, effect, and dedupe records.
- Runtime A and B, including their Git metadata, indexes, worktrees, and caches.
- The incident evidence directory.
- Driver/process state and all external services.

No investigator may launch, resume, retry, restart, fork, notify, enqueue, claim, acknowledge, expire, clear, rebind, migrate, edit, patch, fetch, checkout, commit, or run Megaplan/chain lifecycle code.

### Stage-2 Sol-only judgments

Only the stage-2 scoping adjudicator may decide:

1. Whether the original causal finding is conclusively runtime-A custody behavior or a compound persistence failure.
2. Whether v5 `PROCEED` remains authoritative without another gate.
3. Whether finalize is safe for the same occurrence.
4. Whether the admissible horizon is:
   - same-occurrence continuation,
   - authority-approved migrated child under B, or
   - quarantine.
5. Whether A→B crosses the chain’s runtime identity boundary.
6. Whether a canonical rebind/migration record is required.
7. Whether a new blocker-specific repair request must be minted. An investigator may establish need; it may not create one.
8. Whether the three failed attempts produced effects that prohibit re-entry.
9. Whether the ledger TypeError is a separate integrity blocker.
10. Whether notification custody is complete, suppressible, or requires future exactly-once handling.

### Mandatory stop gates

Stop without recovery action if any of the following holds:

- A live or ambiguously live authoritative runner/lease is found.
- The evidence fingerprint or a material artifact changes during investigation.
- Runtime binding to B is absent, ambiguous, or unauthorized.
- Same-occurrence CAS/idempotency is not affirmatively proven.
- A failed attempt may have committed an unaccounted effect.
- Selector/output producer-consumer integrity is incomplete.
- Work-ledger transition integrity is unresolved.
- A quota, fence, lock, reservation, or repair claim remains owned.
- Notification intent/effect or dedupe state is ambiguous.
- A sibling pattern suggests a systemic failure beyond this bounded occurrence.
- Any needed action would require mutation or authority not already present.

sha256:f606c1a81311e3d4109e3343dcb43d230d9a0fe411560e08605fd1c83a3e25e9