# Custody control plane Superfixer recovery plan — 2026-07-16

**Canonical initiative:** `megaplan-maintenance`

**Incident session:** `custody-control-plane-20260714`

**Evidence cutoff for the initial plan:** 2026-07-16T12:18:02Z

**Execution target at plan creation:** `refs/heads/consolidate/arnold-runtime-activation-20260714` at `f8bdd3729b1a2b50f392b288e9f58b36aace37e5`

**Scope:** watchdog observation and dispatch, L1 goal repair, L2 meta-repair, L3 progress audit, terminal chain reconciliation, deployment, automated retrigger, and durable original-chain recovery proof.

## Outcome and non-negotiable acceptance rule

Repair the Superfixer stack that lost custody after M5a. Do not hand-advance the epic and do not weaken the milestone completion guard. Success requires all of the following at the same observation checkpoint:

1. The deployed runtime revision is identified and contains the verified fixes.
2. The automated watchdog/L1/L2 path, not a human state edit, takes custody of the current blocker.
3. The old frozen goal is terminally superseded or retargeted to the current chain cursor.
4. The original chain's raw chain JSON records M6 (`m6-authority-contract-and-residual-inventory`) as the current initialized/executing plan, or a later authoritative milestone.
5. A live matching runner exists and fresh plan/event evidence advances after initialization, or M6 has already completed authoritatively.
6. L3 deterministically detects the same failure class from a retroactive fixture.

A launch receipt, PID, agent narrative, `status=done`, or a single normalized label is insufficient.

## Canonical ownership and document reconciliation

Rough-title and description search found three related scopes:

- `.megaplan/initiatives/megaplan-maintenance/` is the canonical operational owner for watchdog, repair custody, L2, the six-hour unblocker, and the daily auditor.
- `.megaplan/initiatives/custody-control-plane/` owns the run-authority and chain-transition contracts consumed by this repair.
- `.megaplan/initiatives/superfixer-repair-custody/` is a retired design set. Its `.retired` marker points to `custody-control-plane`; its custody invariants remain useful background but are not a third executable initiative.

This plan therefore lives under Megaplan Maintenance, links rather than copies the retired material, and treats Custody Control Plane as the contract provider and live incident target.

## Observation-path health and six-source ground truth

The local process is already on the AgentBox shared workspace. At 2026-07-16T12:17:41.385781Z, the pinned runtime imported from `/workspace/arnold-consolidation-20260714/arnold_pipelines/megaplan/__init__.py` and `megaplan cloud status --all --compact` read the live marker registry successfully. The separate SSH `cloud exec` transport failed public-key authentication at 2026-07-16T12:18Z, so destructive or deployment operations must use the canonical on-box seam; this does not block direct read-only access to `/workspace`.

| Trust order | Observation at 2026-07-16T12:18Z | Evidence | Verdict |
| --- | --- | --- | --- |
| 1. Live process | Watchdog supervisor exists; no matching chain runner, L1 repair owner, L2 meta-repair worker, or L3 auditor process exists for the incident. | process table; tmux supervisor PID 169 started 2026-07-13T21:43:21Z | Original chain has no live custody. |
| 2. Session marker | Marker says launch success and records `started_at=2026-07-16T11:52:54.407523+00:00`, but it is a launch receipt, not current liveness. | `/workspace/.megaplan/cloud-sessions/custody-control-plane-20260714.json`, mtime 2026-07-16T11:52:55.096678Z | Healthy identity/workspace mapping; stale for outcome. |
| 3. Chain JSON | `current_milestone_index=2`, `current_plan_name=null`, `last_state=pr_closed`, two completed records; M5a has `pr_number=null`, `local_commit_sha=b9867f7c...`, `publication_evidence=local_no_push_reconciliation`. | `/workspace/custody-control-plane-20260714/Arnold/.megaplan/plans/.chains/chain-1e998199f544.json`, mtime 2026-07-16T12:00:26.585447Z | Stranded between M5a and M6. M6 is not initialized. |
| 4. Plan state | M5a is `done`; review phase result is `success`; no active worker or latest failure. | `.../plans/m5a-atomic-fail-closed-20260715-0149/state.json`, `phase_result.json`, `events.ndjson` | M5a terminal plan truth supersedes the old quality-block goal. |
| 5. Log tail | After terminal M5a completion, the driver ran `gh pr view None`, treated missing PR metadata as a closed PR, and stopped. | `.../.megaplan/cloud-chain-custody-control-plane-20260714.log`, lines 23094–23113; log mtime 2026-07-16T12:00:26.587447Z | Confirmed no-PR terminal transition defect. |
| 6. External PR/CI | PR #255 is OPEN/CLEAN at head `5ece35918...`; `test`, `docker-test`, and `merge-result-conformance` completed successfully by 2026-07-16T12:08:31Z. | `gh pr view 255 --repo peteromallet/Arnold`; durable prior snapshots under `/workspace/.megaplan/cloud-sessions/repair-data/meta/evidence/` | External state contradicts the synthetic `PR #None closed` conclusion. Current head does not contain exact ancestor `0beb5e8d...`; this must not be silently rewritten into success. |

The status projection's recent chain heartbeat is not proof of a runner. The process table and marker/process observation agree that the chain is stopped.

## Causal timeline

| UTC time | Event and authoritative consequence | Evidence |
| --- | --- | --- |
| 2026-07-15T14:45:44.475783Z | Durable goal `repair-goal-570fda35570797c632f75703` froze M5a at completed/index 1, plan/chain `blocked`, quality error `quality_gate_blocked`. | `/workspace/.megaplan/cloud-sessions/repair-goals/custody-control-plane-20260714/goal-be9c803900e485470237.json`; later contexts cite checkpoint `a7aabcf9...`. |
| 2026-07-15T15:58:29Z | Attempt 16 resolved the stale quality blocker and recovered the plan to `executed`, but the frozen goal remained active. | repair-data attempt 16; `/workspace/kimi-goal-operator/20260715T155113Z-custody-control-plane-20260714/`. |
| 2026-07-15T16:03:16Z–22:25:18Z | Repeated investigators correctly observed goal/current-state divergence and recommended `replan`, but L2 did not terminally supersede the old goal or establish an owned successor. | run directories `20260715T160316Z...` through `20260715T222518Z...`; L2 logs under `/workspace/.megaplan/meta-runs/`. |
| 2026-07-15T22:38:51Z | Fresh external CI failure became the real blocker; L1 repaired target/package defects, eventually producing `203f00aab...` and green CI. | `20260715T223851Z...`; repair-data attempt 17. |
| 2026-07-15T23:37:28Z–2026-07-16T05:57:48Z | Recovery repeatedly reattached the same frozen goal. Several exact CLI launches returned stopped/blocked without accepted progress. Deterministic retry budget was not keyed to the unchanged checkpoint/action/result. | repair-data attempts 18–19; goal-operator runs `20260715T233449Z...` through `20260716T055748Z...`. |
| 2026-07-16T03:59:03Z | Attempt 19 fixed the wrapper acceptance-gate source defect as `0beb5e8d...`; broad wrapper suite still had unrelated failures. | repair-data attempt 19; `/workspace/kimi-goal-operator/20260716T035721Z.../`. |
| 2026-07-16T06:34:48Z–06:55:10Z | M5a review/plan reached terminal `done`, while the chain remained at completed/index 1 and `awaiting_pr_merge`. | M5a state/events; `/workspace/audit-reports/20260716T073516Z-audit.md`. |
| 2026-07-16T08:02:27Z–08:12:32Z | L1 investigator produced invalid JSON, one bounded correction also failed schema validation, and the run exited without a valid handoff. | `/workspace/kimi-goal-operator/20260716T080227Z.../repair-investigator-receipt.invalid-1.json`, validation error, correction prompt, final receipt; `/workspace/.megaplan/meta-runs/20260716T080050Z...log`. |
| 2026-07-16T08:28:53Z–08:30:59Z | L2 accepted a replan and retriggered L1; L1 attached the same old goal/checkpoint, selected `recover_state`, hit an internal `IndexError`, and returned `failed:awaiting_pr_merge:rc=0`. | `/workspace/.megaplan/meta-runs/20260716T082649Z...log`; `/workspace/kimi-goal-operator/20260716T082855Z.../`. |
| 2026-07-16T08:41:29Z | Attempt 20 supplied exact-ancestor custody in a temporary target head `25cbaaf8...`; later ordinary publication produced head `5ece3591...`, which no longer contains `0beb5e8d...` as an ancestor. | repair-data attempt 20; current local git ancestry probe at 2026-07-16T12:18Z. |
| 2026-07-16T11:50:55Z | A new L3-triggered run observed chain completed/index 2 with no current plan but still reasoned from the old commit/context-mismatch failure. Its corrected receipt chose `recover_state`; repair-data ended `fixer_infrastructure_failure` at 2026-07-16T11:54:04.169927Z. | `/workspace/kimi-goal-operator/20260716T115055Z.../`; current repair-data. |
| 2026-07-16T11:52:54Z–12:00:26Z | Supported chain relaunch accepted M5a locally, then queried `PR #None`, wrote `pr_closed`, and stopped before M6 initialization. | marker start time, log and chain JSON mtimes/lines. |
| 2026-07-16T12:17:41Z | Canonical status: attention, no runner/repair owner, completed 2/10, M6 absent, stale repair projection, attempt budget exhausted. | `megaplan cloud status --all --compact`. |

## Actual repair-session groups

The aggregate `request/claim/attempt=39/0/55` status label does not mean 55 identical attempts. At the evidence cutoff there are 52 goal-operator run directories, 39 central queue requests, seven central queue launch receipts, and 19 persisted completed repair records (attempt IDs 1 and 3–20; ID 2 is absent). Groups below use a deterministic semantic signature: current/frozen cursor, exact failure kind, recommended action, schema result, and mechanical/mutation result.

| Group | Representative and duplicate run IDs | What the worker saw and goal | What it did / divergence | Missing instruction or evidence |
| --- | --- | --- | --- | --- |
| G1 — early M5 binding/quality repair | `20260714T190719Z`, `191847Z`, `202919Z`, `235536Z`, `20260715T003120Z` and early no-context exits | M5 blocked on binding drift, compatibility/collection and review metadata failures. Legacy prompts were ~0.5 MB and lacked the later typed investigator envelope. | Some runs made real target/source fixes; others exited before a report. These are not duplicates of the later stale-goal incident. | Typed current-target envelope and durable outcome receipt. |
| G2 — M5 recovery into M5a | `20260715T102055Z`, `112336Z`, `113325Z`, `113948Z`, `114339Z`, `120346Z` | Current M5a execute was live/finalized while the frozen checkpoint still described a blocked predecessor. | Alternated `preserve_live` and `recover_state`; one dev fix addressed execution prompt/test drift. | Explicit terminal supersession when the chain cursor/plan changes. |
| G3 — real M5a quality defect | `20260715T144546Z` and `155113Z` | Same blocked checkpoint and live quality failure; attempt 15 found missing wrapper extraction dependency, attempt 16 verified the fix and recovered the plan. | Correct `repair_target` then `recover_state`; this was productive work. | After recovery, close the old goal and mint a successor epoch. |
| G4 — frozen goal active and unowned | duplicates `20260715T160316Z`, `160901Z`, `163753Z`, `194114Z`, `201715Z`, `212043Z`, `220540Z`, `221557Z`, `222518Z` | Plan `executed`, latest failure cleared, chain still blocked; old goal still asserted `quality_gate_blocked`, `current_attempt_id=null`. | Investigators repeatedly recommended `replan`; no owner performed a terminal goal transition, so the next run reattached the same goal. | L2 must enforce `old_goal.status=superseded`, cite successor goal ID/current cursor, and reject reattachment. |
| G5 — new external CI blocker | `20260715T223851Z` | Current external `test` check failed at PR #255; old goal remained stale but a real new blocker existed. | Correctly chose `repair_target`; attempt 17 repaired packaging/conformance and restored green CI. | New blocker identity must supersede, not coexist under, the old semantic goal. |
| G6 — recovery with no accepted progress | `20260715T233449Z`, `235252Z`, `20260716T000513Z`, `002950Z`, `020754Z`, `024346Z` | Current plan/chain executed; no runner; old goal active; exact supported CLI had not produced accepted progress. | Repeated `recover_state` or `replan`; launch receipts often said stopped/failed while derived state changed. | A circuit breaker keyed to `(goal, checkpoint, action, launch-result, accepted-progress-token)` after at most three identical results. |
| G7 — deterministic quality/relaunch churn | duplicates `20260716T032958Z`, `033910Z`, `034601Z`, `043049Z`, `050833Z`, `052358Z`, `053927Z`, `054932Z`, `055748Z`; repair-source run `035721Z` | Same blocked M5a quality fingerprint and same frozen checkpoint. | Eight near-identical `recover_state` runs plus one useful source repair; the system spent general iteration budget after the deterministic failure was established. | Separate deterministic budget from productive repair budget; escalate to L2 with raw stderr/receipt after result 2–3. |
| G8 — stale live-worker inference | `20260716T061412Z` | A review PID existed but had no accepted progress beyond review rank 7. | Chose `preserve_live`, so liveness delayed escalation even though acceptance progress was stale. | `alive && fresh accepted progress`, not PID liveness, is the preservation predicate. |
| G9 — plan done, old goal still active | `20260716T064514Z`, `072736Z`, `073130Z`, `074626Z` | M5a `done`; chain `executed` then `awaiting_pr_merge`; old quality goal active/unowned; commit-custody evidence inconsistent. | Correctly diagnosed custody failure and asked L2 to replan, but no enforced goal transfer occurred. | Goal retarget rule for terminal plan/cursor changes and an owned successor deadline. |
| G10 — schema and exact-commit detour | `20260716T080227Z`, `082148Z`, `082855Z`, `083812Z` | Same plan-done/awaiting-PR condition. Some snapshots had no valid external PR; others saw PR #255. | Three runs emitted invalid v2 JSON before bounded correction; one corrected to `recover_state`, one to `repair_target`. An `IndexError` then defeated the authorized CLI path. | Pass pre-collected observations, validate before release, preserve validation error in L2 context, and require one executable handoff after correction. |
| G11 — stranded between milestones | `20260716T115055Z` | Current raw cursor was completed/index 2, no plan, `last_state=done`; frozen checkpoint remained completed/index 1 with M5a executed. | Even after correction it narrated the earlier commit-ancestry problem and chose generic `recover_state`; it did not name M6 initialization or `PR #None`. | The context must expose `stranded_between_milestones`, old/current cursor delta, no-PR publication evidence, next milestone, and the exact terminal-reconciliation action. |

## What the fixer knew versus should have known

| Layer | It knew | It should have been required to conclude |
| --- | --- | --- |
| Watchdog/dispatch | Marker tracked the correct workspace/spec; no runner; chain incomplete; repeated repair churn. | A terminal plan with completed/index 2, no current plan, and no runner is a current `terminal_reconciliation` blocker even when a stale repair goal exists. |
| L1 | Rich plan, chain, queue, external, goal, and prior-attempt context; later contexts showed current/frozen cursor separately. | If current cursor or terminal state advances beyond the frozen goal, stop mutating under that goal, supersede it, and request a new goal bound to the current blocker. |
| L2 | Repeated valid `replan` receipts, active-unowned goal, context mismatches, invalid L1 receipts, and ordinary retrigger failures. | A replan is incomplete until it creates/owns a successor goal, proves the old goal cannot reattach, and verifies one ordinary retrigger against the new cursor. |
| L3 | `stale_l1_l2_cycle`, meta launch failures, no-verdict records, retry budget overrun, liveness without acceptance progress, and repair churn. | Treat active goal + no owner + unchanged frozen checkpoint + no original-chain advance as a Superfixer failure; dispatch repair of L1/L2 and verify raw chain movement. After completed/index changes, re-gather instead of reusing the old finding. |

## Root cause and tested hypotheses

**First broken layer:** L1 goal operator, **CONTEXT/INTENT plus deterministic-budget failure**. The transport contained current observations, but the durable goal contract kept an old semantic blocker authoritative after the plan/cursor advanced. L1 could recommend `replan` but had no enforced custody-transfer transaction; later runs reattached the same checkpoint and acted on proxies (`quality commit`, `awaiting_pr_merge`) instead of the new between-milestones blocker.

**Backstop failure:** L2, **FIXED/CONTEXT failure**. L2 observed the mismatch and repeatedly retriggered, but did not require a terminal old-goal transition plus an owned successor. L3 detected several symptoms but did not deterministically identify or repair the final completed/index 2, no-owner, no-M6 state.

| Hypothesis | Status | Evidence |
| --- | --- | --- |
| Frozen goal/checkpoint stayed active after M5a advanced | Confirmed | Goal `repair-goal-570f...` frozen at blocked/completed 1; 2026-07-16T11:50:55Z context current completed/index 2 still carries old checkpoint. |
| L1 could not retarget to `PR #None` / between milestones | Confirmed for the observed run | `20260716T115055Z` receipt discusses old commit ancestry and generic recovery; chain log later writes `PR #None closed`; M6 absent. |
| Invalid investigator JSON caused bounded exits | Confirmed, not universal | Invalid/correction artifacts at 08:02:27Z, 08:21:48Z, 08:38:12Z, and 11:50:55Z; earlier runs had valid receipts. |
| An unresolved semantic goal became unowned | Confirmed | Multiple contexts report active goal, `current_attempt_id=null`, no runner/owner; L3 reports `stale_l1_l2_cycle`. |
| Retry churn was deterministic | Confirmed for several groups, not all 52 runs | G4, G6, and G7 repeat unchanged checkpoint/action/result; G1/G3/G5 contain distinct productive repairs. |
| No-PR completion transition stopped the chain | Confirmed | Log lines 23106–23113 query `None`, synthesize closed, and stop; raw record has local publication evidence and no PR number. |
| L3 was blind to the complete symptom set | Partially confirmed | L3 detected stale L1/L2, no verdict, churn, and liveness-without-progress before 09:03Z. No post-12:00 report proves detection of completed/index 2 + no current plan + unchanged goal + M6 absent. The deterministic final-state gather reason was missing. |
| Current exact external publication authority is fully known | Unknown/contradictory at the initial cutoff; resolved during execution | At 2026-07-16T12:18Z PR #255 was open and green while chain completion was explicitly local/no-push and queried `None`; the contradiction was preserved. PR #255 later merged at 2026-07-16T12:57:39Z and the execution record below distinguishes that external fact from the local/no-push completion record. |

## Required design and implementation

### 1. Terminal chain reconciliation and no-PR completion

- Model a valid local/no-push completion as publication evidence, never as `PR #None`.
- After a guarded completion append clears `current_plan_name` and PR metadata, skip all PR lookup and closed-PR stop logic for that completed milestone.
- Continue through the ordinary chain state machine to initialize the next milestone. Do not write M6 state directly.
- Preserve any observed external PR as contradictory evidence; do not fabricate `merged`, `closed`, or a PR number on the local completion record.
- Regression: a terminal M5a plan with `publication_evidence=local_no_push_reconciliation` must end with M6 initialized and no `PR #None` log.

### 2. Goal retargeting and custody-transfer invariant

Invariant:

> At every nonterminal incident instant, exactly one current goal owns the current blocker and current chain cursor. If plan state, plan identity, completed prefix, milestone index, or current plan changes beyond the frozen checkpoint, the old goal may only be observed or terminally superseded; it may not authorize another mutation.

Rules:

1. Compute a semantic checkpoint from session, plan identity/state, chain completed prefix/index/current plan/last state, current exact failure fingerprint, publication state, and next milestone.
2. If the semantic checkpoint changes, write a terminal supersession record with old goal ID, old/current checkpoints, reason, successor goal ID, and custody owner/lease.
3. Retarget in place only for evidence refresh that does not change blocker identity or permitted action.
4. A plan becoming terminal, a cursor advance, or entry into `between_milestones` always creates a new goal epoch.
5. L1 must fail closed if invoked with a superseded goal or if current checkpoint differs from the goal after investigation.
6. L2 `replan` success requires old goal terminal, successor accepted and owned, and one ordinary retrigger bound to the successor.

### 3. Prompt, context, and evidence contract

Every L1/L2 prompt must inline a bounded machine-readable envelope containing:

- all six custody sources with capture time, mtime, digest, and contradictions;
- current and frozen semantic checkpoints plus field-level delta;
- `stranded_between_milestones`, next milestone label, and no-PR/local publication evidence;
- exact last command, exit code, stderr tail, validation error, and durable launch receipt;
- active goal status/owner/lease, prior semantically identical results, remaining deterministic and productive budgets;
- allowed mutation for the selected action and the authoritative verification predicate.

Investigator output is schema-validated before any handoff. One bounded correction is permitted. If correction fails, L2 receives the invalid artifact and validator error and must either create a valid replacement or close/escalate the goal; it may not silently retrigger the same prompt.

### 4. Deterministic failure circuit breaker

- Fingerprint `(goal_id, semantic_checkpoint, recommended_action, exact command, exit classification, accepted-progress-token)`.
- Two identical failures force re-observation and a reasoned decision; a third forbids the same action under the same goal.
- The breaker consumes a separate budget from productive source/target fixes.
- Breaker trip must transfer custody to L2 with raw evidence and close the L1 owner lease.
- L2 may retry only after changing the goal epoch, evidence envelope, action, or verified implementation revision.
- L3 flags any fourth identical result, any negative remaining budget, or repair-data `repairing` with no owner.

### 5. L2/meta-repair enforcement

- Treat `replan` as a custody transaction, not agent advice.
- Reject `replan` completion unless old goal is terminal and successor is accepted/owned.
- Reject an ordinary retrigger that reattaches the old goal/checkpoint.
- A schema-invalid L1 receipt, context-target mismatch, or bounded worker exit is itself an L2-owned infrastructure blocker.
- Verify L2 success with raw chain/plan progress and blocker clearance; PID or `live_with_fresh_activity` alone remains provisional.

### 6. L3 retroactive detection

Add the deterministic gather reason:

`stranded_between_milestones = completed_count < total && milestone_index == completed_count && current_plan is empty && no matching runner && terminal_or_between_milestones_last_state`

Enrich it with:

- active repair goal older than the current semantic checkpoint;
- goal has no live owner/lease;
- current/frozen completed count or index differs;
- no plan directory for the next milestone;
- same checkpoint unchanged across two audits;
- original chain has not advanced since repair/audit dispatch.

The finding must route to Superfixer repair, not human gating, unless an independently typed human gate exists. Its acceptance probe is raw M6 initialization/progress and old-goal terminalization.

## Tests and verification gates

Required before integration:

1. `python -m pytest tests/test_chain_completion_guard.py -q`
2. `python -m pytest tests/cloud/test_repair_goal.py -q`
3. `python -m pytest tests/cloud/test_repair_recurrence.py -q`
4. `python -m pytest tests/cloud/test_progress_auditor.py -q`
5. Focused wrapper tests in `tests/cloud/test_watchdog_wrappers.py` for no-PR completion, goal supersession, L2 replan enforcement, invalid receipt, and deterministic breaker.
6. `bash -n` for every changed wrapper.
7. `git diff --check`, full diff review, and negative tests proving no direct chain JSON edit, no fabricated PR metadata, no guard weakening, and no fourth identical L1 retry.
8. Synthetic end-to-end fixture copied from the raw M5a/chain/goal state: current completed/index 2, no current plan, old frozen goal at 1, no runner, local publication evidence, optional contradictory open PR.

## Deployment, revision reconciliation, and rollback

Integration is permitted only from a clean isolated worktree based on the recorded target. Immediately before integration:

- verify target ref still exists and is a descendant of the recorded base;
- rebase the feature commit if the target advanced;
- rerun tests and diff review;
- integrate locally using fast-forward-only or the repository's documented non-destructive method;
- record base, commit, target before/after, clean worktree, and ancestry in the resident git-custody receipt.

Supported deployment must record:

- installed runtime import root and exact revision;
- wrapper source and `/usr/local/bin` hashes where a wrapper changed;
- deployment/activation receipt and service/supervisor health;
- no restart of a progressing chain;
- canonical scoped AgentBox restart/activation command only, never broad `pkill`, `killall`, or tmux cleanup.

Rollback is revision-based: reinstall the prior verified runtime and wrapper hashes using the same supported activation seam. Rollback must not delete repair goals, queue records, audit reports, or original chain evidence. If the new automated repair repeats the same semantic signature twice without accepted progress, stop further mutation, retain evidence, and roll back only the Superfixer runtime—not the live chain state.

## Final operational step — deploy, automatically retrigger, and observe

This is the final plan step and the only completion path:

1. Confirm the original chain has no live progressing runner. If it is progressing, do not restart it; observe only.
2. Deploy the verified integrated revision through the canonical on-box runtime activation operation. Capture installed revision, wrapper hashes/copy receipt if applicable, supervisor health, and deployment time.
3. Trigger the ordinary automated fixer for `custody-control-plane-20260714` through the supported watchdog/repair dispatch seam. Do not run a manual M6 initialization or edit chain JSON.
4. Capture repair request, claim, attempt, goal, and managed run IDs. Verify the new goal names the current between-milestones/no-PR blocker and the old goal is superseded/closed.
5. Observe at bounded checkpoints: immediately, +2 minutes, +5 minutes, +15 minutes, then every 15 minutes while a fresh runner is making accepted progress. At each checkpoint read all six custody sources.
6. Pass only when raw chain JSON identifies M6 (or later), its plan state/events show fresh accepted activity, the matching process is live or the milestone is authoritatively terminal, and no old-goal retry remains active.
7. Fail closed if: the same semantic failure repeats twice after deployment; a third identical action is attempted; the old goal reattaches; only a launch receipt/PID changes; PR metadata is fabricated; chain state advances without the normal driver evidence; installed revision differs from the receipt; or the original chain remains unchanged at the +15-minute checkpoint with no active owner. Route that evidence to L2 and L3, retain custody, and do not claim recovery.

## Execution record to append after the operational step

Record the final source base/commit/target, test commands, deployment receipt, installed revision, service health, automated repair request/goal/run IDs, observation timestamps, old-goal disposition, and the raw original-chain outcome. Explicitly state whether M6 initialized/executed or whether only labels changed.

## Execution record — completed 2026-07-16

### Automated repair and causal verification

The first post-deployment watchdog sweep began at 2026-07-16T12:43:25Z. L2 run `managed-automatic-meta-repair-4f2064d05b4cf6efb9fb` and investigator `managed-automatic-research-subagent-cbbd472f9c13ca62d3e4` correctly identified the `pr_closed`/open-PR contradiction and recommended `replan`; the effect boundary then failed closed at 2026-07-16T12:45:20Z because the default-off master autonomy gate was absent. This was diagnostic success, not recovery. Raw evidence: `/workspace/.megaplan/meta-runs/20260716T124350Z-custody-control-plane-20260714.log` and its investigator receipt.

Revision `d500f182130570ac1efe7d973576add4e859a20f` changed terminal cursor supersession so the old target no longer required its successor runner to exist before closing. The next watchdog sweep changed goal `repair-goal-b96cdbb5a57136c39b273b88` to `progressed`, `semantic_completion=true`, and `recovery_gate_not_applicable=superseded_target` at 2026-07-16T12:47:00.407307Z. Its L2 run `managed-automatic-meta-repair-1ef2fdf6323e19404a62` and investigator `managed-automatic-research-subagent-a184b0276a12643a1542` again diagnosed the current contradiction; mutation again failed closed at 2026-07-16T12:48:22Z. Revision `facd3623a0528b4785e44c3906d13589d552003c` then prevented historical L1-failure routing from intercepting the ordinary successor relaunch after same-sweep goal completion.

Live re-drive exposed two additional deterministic chain defects rather than being counted as success:

1. The 2026-07-16T12:50:30Z relaunch rewound an accepted local/no-push M5a completion during startup reconciliation. Revision `7a79c0d64c75225e68a3d3987c3e11a7050ec616` made guarded local completion records survive restart and reject unguarded PR-less records.
2. After external PR #255 merged at 2026-07-16T12:57:39Z and M5a was reconciled, the inherited `awaiting_pr_merge` label was applied to M6 with no plan name. The driver failed closed with `completion record has no plan name` at 2026-07-16T13:00:01Z. Revision `a17e594cd1f13ad2da335fd2458504aeac852f9f` now writes `between_milestones` after a non-final reconciled advance, preventing a successor from inheriting the predecessor's merge wait.

These runs confirm that the initial failure was not one defect or 55 identical attempts. The causal stack was: no-PR fall-through, frozen goal identity, missing deterministic recurrence signature, impossible old-goal recovery gate, historical-failure routing after supersession, startup loss of accepted local completion, and inherited merge-wait state. L3's missing composite stranded-cursor check was the backstop failure.

### Source, integration, tests, and deployment

The implementation owner used clean isolated worktree `/workspace/arnold-superfixer-terminal-reconcile-20260716` on `refs/heads/fix/superfixer-terminal-reconcile-20260716`, based at `7e09e33ed6acb187aa43158224bb08b5bbf2d215`. The locally integrated target `refs/heads/consolidate/arnold-runtime-activation-20260714` advanced through:

- `d747fd7d43fdfa4ee7a87a1db3add62871cf44e3` — terminal local completion, goal ordering, recurrence signature, L3 detection;
- `20f35a104323834e8d4f71dbf4144c1388ffeab0` — auditor milestone-count source;
- `d500f182130570ac1efe7d973576add4e859a20f` — close superseded goals before successor launch;
- `facd3623a0528b4785e44c3906d13589d552003c` — bypass historical failure routing after goal supersession;
- `7a79c0d64c75225e68a3d3987c3e11a7050ec616` — preserve guarded local completion on restart;
- `a17e594cd1f13ad2da335fd2458504aeac852f9f` — clear predecessor merge wait before successor initialization.

The target was revalidated immediately before each fast-forward integration. The final feature worktree and target both contain `a17e594cd1`; the feature worktree is clean and the launch checkout was preserved. Durable custody receipt: `/workspace/arnold/.megaplan/plans/resident-subagents/subagent-20260716-120729-4d2eac6d/git-custody-evidence.json`. No runtime-source remote push was required or performed.

Focused and proportional verification passed: 164 chain tests, 145 auditor tests, 37 repair/Superfixer tests, changed-module compilation, changed-wrapper `bash -n`, `git diff --check`, local/no-push restart, no-PR sync, goal supersession, successor relaunch, deterministic recurrence, stranded-cursor L3 routing, and inherited merge-wait regressions. The broad wrapper aggregate's 29 failures were reproduced at the launch base and classified as pre-existing baseline drift; none was introduced by this diff.

Supported activation installed the editable runtime at `/workspace/arnold-superfixer-terminal-reconcile-20260716`. The provenance probe from `/tmp` returned `ok=true`, import root equal to that worktree, and both runtime/source revision `a17e594cd1f13ad2da335fd2458504aeac852f9f`. Installed wrapper hashes match source:

- `arnold-watchdog`: `3b5b50231173206632d5d485525e40010a770e40506e65f31a6c685994bfe557`;
- `arnold-progress-auditor`: `1bebdff11e1276fac489c52e625867aba46ed33b3eaa8cf2287e620672fd38df`.

The canonical watchdog tmux supervisor remained PID 169; no resident restart, broad process kill, direct chain JSON edit, or fabricated PR metadata was used. The final scoped chain process, PID 2012436, is parented by the watchdog tmux supervisor and runs the supported no-push chain command against the installed revision.

### Bounded outcome observations

| Observation UTC | Raw result |
| --- | --- |
| 2026-07-16T12:47:00.407307Z | Old goal became durably `progressed` and semantically complete with a superseded blocker. |
| 2026-07-16T12:57:39Z | Real PR #255 merged as commit `a5f92fadcfe3fb3f798bca00aab64bb16590d824`; all three CI checks were successful. |
| 2026-07-16T13:00:01Z | M5a was durably completed, but M6's first transition failed closed on the inherited merge-wait defect; no false success was claimed. |
| 2026-07-16T13:03:24Z | Supported chain process started under watchdog supervisor custody at final revision `a17e594cd1`. |
| 2026-07-16T13:03:28Z | Original chain initialized M6 as `m6-exact-contract-and-20260716-1303`; raw cursor remained index 2 with two completed predecessors. |
| 2026-07-16T13:06:59Z | M6 plan events continued to advance in `prep`; the live matching runner emitted fresh token/reasoning heartbeats well beyond the initialization receipt. |
| 2026-07-16T13:11:25.832123Z | More than eight minutes after launch, PID 2012436 remained live under watchdog custody and M6 event sequence 982 recorded fresh `prep-distill` token activity; no latest failure was present. |

Acceptance passed because three independent sources agree: raw chain JSON names M6 as the current plan; M6's own state/events show an initialized plan with a live, fresh `prep` worker; and the matching process is alive under watchdog supervisor custody. The chain-level `last_state=done` projection remained stale-looking at the checkpoint and is explicitly not used as success evidence. M6 had initialized and was actively executing prep; it had not yet completed. Rollback was not invoked. If the live M6 worker loses fresh activity without authoritative state progress, the ordinary watchdog/L3 path remains responsible for the new M6 blocker rather than reopening the superseded M5a goal.
