# Agent Edit Transaction Spine retry root-cause investigation

Snapshot: **July 14, 2026 10:25:31 UTC (+00:00)**

Scope: exact cloud session `agent-edit-verifiable-transaction-spine` and plan
`sprint-2-transactional-apply-20260714-0336`. This record distinguishes durable
observations from inference and missing telemetry. No active chain, service, or
unrelated checkout state was changed.

## Outcome

The epic was still executing attempt 4 at the snapshot (81% epic, 62% plan), not
complete. Its three blocked execute attempts consumed **3h27m40.174s of metered
execution, $3.12684198492, 40,735,907 input tokens, and 411,560 output tokens**.
Those attempts produced substantial implementation progress, so this is not all
waste. Two externally repaired retries added **1h49m35.933s block-to-restart
latency**, dominated by **1h38m43.535s waiting for hourly watchdog detection**.

The immediate repeated cause was deterministic: two complexity-7 tasks, T7 and
T12, reached the same 90-tool-iteration ceiling after implementation work but
before their proof-test contracts were complete. The systemic causes were a
fully serial 30-task plan admitted without a turn-budget feasibility gate,
hourly rather than event-driven recovery, repair results that cannot become
verified task checkpoints, stale repair-request identity, incomplete repair
terminalization, and ambiguous terminal/control-plane projections.

A separate systemic control-plane defect was reproduced: every event, including
heartbeats, rewrote the complete compatibility `events.ndjson` projection with a
non-atomic write. On this plan, about 12,316 events and a 26.13 MB projection
imply roughly **137.125 GiB of cumulative compatibility-projection writes**.
During one rewrite, introspection read a partial 2,570-event prefix and falsely
reported a stalled plan; a later read saw 12,296 events and progressing liveness.
Exact wall-time attributable to this I/O is not instrumented.

## Exact failure and retry chain

| Attempt | UTC interval | Metered duration | Cost | Durable stop | Recovery |
|---|---|---:|---:|---|---|
| 1 | July 14, 2026 04:01:51–04:38:53 UTC (+00:00) | 36m59.230s | $0.250969451 | T4 quality/task-update gate; two compile tests failed | Internal auto-retry began 13s later |
| 2 | July 14, 2026 04:39:06–05:20:49 UTC (+00:00) | 41m33.382s | $0.92232109484 | T7 exhausted 90 iterations before required tests | Request at 06:09:38; dispatch 06:10:15; execute resumed 06:16:41 |
| 3 | July 14, 2026 06:16:41–08:26:14 UTC (+00:00) | 2h09m07.562s | $1.95355143908 | T12 exhausted 90 iterations before fixed-point tests | Request at 09:15:14; dispatch 09:15:32; execute resumed 09:19:58 |

Attempt 2 block-to-request was about 48m52s; attempt 3 block-to-request was about
49m05s. L1 repairs were correctly targeted and pushed T7 commit `c212755` and T12
commit `5671bb4`; later advancement proves both fixes took. The standard executor
nevertheless reran both high-complexity tasks because the repair result is not an
authoritative, adoptable task receipt. Conservative executor overlap was at least
**$1.3234 and about 65 minutes**; it was duplicate workflow, though it also
provided authoritative verification.

Attempt 4 was live on batch 16 at July 14, 2026 10:23:03 UTC (+00:00). It had
advanced through T15, so recovery is evidenced as progress, not completion.

## Observed instance-specific causes

1. The plan is 30 tasks connected by 29 dependencies: a completely serial graph.
   `max_tasks_per_batch=5` therefore provides no execution parallelism.
2. T7 and T12 are complexity-7 tasks and both exhausted the same 90-iteration
   worker budget. T19, T21, T26, and T28 remain high-complexity recurrence risks.
3. Prep could not read two requested research paths and recorded a structural
   audit failure. The critique marked all five high-complexity checks
   unverifiable, including an oversized lifecycle/storage task, yet the gate
   still produced `PROCEED` without resolving those warnings.
4. Attempt 1's baseline classification was weak: repair evidence records runner
   exit code 4 while execution described the two failures as pre-existing.
5. Nine Sprint-2 context-summary operations failed because the provider received
   an empty model name, allowing persistent-session context volume to grow.
6. Earlier Sprint-1 repair attempts 1–3 failed mechanically with return code 2;
   the preserved repair investigation attributes this to a deployed watchdog
   invocation missing required managed-agent origin arguments. Attempt 4
   succeeded. Some original live logs are no longer available.

## Observed systemic control-plane failures

- **Detection cadence:** blocked execution waited for hourly watchdog scans.
- **Request identity drift:** the old T7 request `9502fb...` was dispatched at
  09:14:52 against the current T12 blocker. Its attempt contains a T7 request ID
  and T12 blocker ID; the correct T12 request `474da5...` remained accepted but
  undispatched. Same-plan coalescing did not revalidate the complete live failure
  signature.
- **Unclosed custody:** the repair attempt remained `launched`, claims remained
  zero, `repair-data/index.json` had no attempt IDs, and three requests remained
  active after execution had advanced. The resident view therefore said both
  `status=repairing` and `display_state=executing`.
- **Terminality ambiguity:** live execution coexists with plan/chain
  `current_state/last_state=finalized`; active process and heartbeat are not
  consistently dominant. Structured `latest_failure` is cleared after a block,
  forcing repair to triangulate logs and chain state.
- **Lossy retry evidence:** `phase_result.json`, `execution.json`, and batch
  outputs are overwritten on retry. Append-only history/logs are the remaining
  durable source for earlier attempts.
- **Recurrence blind spot:** L2 keys by exact task identity, so T7 and T12 appear
  unrelated instead of the normalized class `worker_budget_exhausted`.
- **Auditor misdirection:** L3 emphasized GitHub publication rather than repeated
  budget exhaustion, retry cost, and detection delay. Its artifact lookup also
  matched unrelated sessions through the generic basename `vibecomfy`.
- **Source-plane ambiguity:** installed wrappers match supervisor source revision
  `405eb641`; resident source is `612b139`; the chain runtime mirror is
  `7644f55`. Evidence does not consistently record all three provenance values.

## Inference

- Oversized task contracts relative to the 90-iteration cap are the primary
  repeated execution cause; both independent stops have the same mechanism.
- Full-journal rewrites likely added I/O contention and control-plane latency,
  but the system has no instrumentation to assign an exact duration to them.
- Hourly scheduling caused the two roughly 49-minute detection waits because the
  request timestamps align with the scheduled scans.

## Missing telemetry

- Tokens, dollars, and reliable durations for GPT developer repairs and Kimi
  relaunch turns.
- One reconciled plan ledger including planning, blocked attempts, repair, and
  in-flight attempt-4 calls; state and introspection totals disagree.
- Tool-iteration counts per task and productive-versus-replayed token attribution.
- Immutable terminal timestamps/reasons for repair attempts and request retirement.
- Immutable phase-attempt receipts for attempts 1 and 2.
- Direct measurements of event projection bytes, fsync time, and reader retries.
- Complete original Sprint-1 mechanical-launch logs.

## Safe corrective work completed

An isolated clean worktree based on the chain runtime revision `7644f55` contains
commit **`3221870c965f086691610321b41b126f4aff3266`**, `Avoid quadratic event
projection rewrites`.

The Store remains authoritative. The compatibility projection now performs one
atomic full rebuild when absent or cursor-mismatched, then cursor-checked
O(event-size) appends. A `.events.projection.seq` cursor provides crash recovery,
and atomic replacement prevents readers from observing truncated rebuilds.

Verification:

- Focused projection, concurrent-ordering, phase-liveness, and doctor suite:
  **18 passed in 0.65s** on July 14, 2026 10:25:31 UTC (+00:00).
- Full `tests/observability`: **14 passed in 0.62s**.
- `compileall` passed; `git diff --check` was clean.
- Ruff was unavailable in the environment (`No module named ruff`).

The fix is committed but deliberately **not pushed, deployed, hot-loaded, or
used to restart the active chain**. The dirty resident checkout was untouched.

## Root prevention plan

### P0 — high impact, bounded effort

1. Validate repair identity at dispatch using session, plan revision, blocked
   task, failure kind, and phase-result hash. Supersede stale requests. Regression:
   T7-to-T12 transition must never pair a T7 request with a T12 blocker.
2. Terminalize every request/claim/attempt, populate `attempt_ids`, and only
   record repair progress after `blocker_cleared && task_advanced`. Test successful,
   superseded, failed, and abandoned paths.
3. Require exact normalized session/plan/incident identifiers in auditor evidence;
   ban basename-substring joins. Regression: two sessions named `vibecomfy`.
4. Review and land `3221870c`, canary it on an idle runtime, and benchmark a
   synthetic 10k-heartbeat plan. Repeated concurrent introspection must observe
   monotonic event counts and never false `stalled`.

### P1 — execution-path controls

5. Trigger deterministic repair from a durable blocked event with a less-than-5m
   detection SLO; retain hourly scanning only for reconciliation. Test process-exit
   and blocked-phase delivery, deduplication, and missed-event fallback.
6. Normalize `worker_budget_exhausted` across tasks and open a plan-level circuit
   after two consecutive occurrences. The circuit must split work or explicitly
   raise the iteration budget; it must not blindly replay.
7. Add plan feasibility checks for dependency depth, expected model turns,
   touchpoints, and proof-test count. Complexity >=7 tasks must split implementation
   from proof or receive an explicit larger budget. A degraded/unverifiable
   high-complexity critique cannot silently become clean `PROCEED`.
8. Emit a signed L1 task-repair receipt containing commit, tests, task contract,
   and plan revision. The executor may adopt it only through a cheaper verify-only
   path; mismatched receipts fall back safely to normal execution.
9. Resolve summary-model defaults and test empty-model compaction failure with a
   bounded fresh-session fallback.

### P2 — observability and rollout

10. Emit per-attempt productive/replay/idle/repair/verify durations, calls, tokens,
    dollars, iteration counts, recovery cursor, and git head. Reconcile them into
    one authoritative cost ledger.
11. Add deterministic auditor reasons for consecutive blocks, signature drift,
    unclosed attempts, index mismatch, detection-SLO breach, executor/repair
    overlap, cross-session evidence pollution, and projection write amplification.
12. Record wrapper SHA, supervisor source root/revision, resident revision, and
    target runtime revision on every repair attempt.
13. Roll out in order: unit/contract tests; shadow auditor reasons; projection
    canary and 10k-event benchmark; controlled wrapper/runtime install; provenance
    verification; then one real blocked-run acceptance proving detection under 5m,
    exact custody closure, monotonic telemetry, and no full task replay.

## Evidence and reproducibility

Primary immutable/current evidence:

- `/workspace/agent-edit-verifiable-transaction-spine/vibecomfy/.megaplan/plans/sprint-2-transactional-apply-20260714-0336/{state.json,events.ndjson,execution.json,phase_result.json,step_receipt_execute_v1.json,execute_batches/}`
- `/workspace/agent-edit-verifiable-transaction-spine/vibecomfy/.megaplan/plans/.chains/chain-e2e81558e8a3.json`
- `/workspace/agent-edit-verifiable-transaction-spine/vibecomfy/.megaplan/cloud-chain-agent-edit-verifiable-transaction-spine.log`
- `/workspace/.megaplan/cloud-sessions/agent-edit-verifiable-transaction-spine{.json,.chain-health.progress.json,.repair-progress.json}`
- `/workspace/.megaplan/cloud-sessions/repair-data/agent-edit-verifiable-transaction-spine.repair-data.json`
- `/workspace/.megaplan/repair-queue/{requests,attempts,decisions}/`
- `/workspace/watchdog-reports/20260714T{061044,091616}Z.json`
- `/workspace/audit-reports/20260714T073501Z-audit.{json,md}`
- `/workspace/kimi-goal-operator/20260714T{060941,091453}Z-agent-edit-verifiable-transaction-spine/`
- `/workspace/arnold/.megaplan/tmp-superfixer-agent-edit/results/03-l1-repair-loop.txt`

Representative commands (all read-only except the isolated patch/commit):

```text
date -u '+%Y-%m-%d %H:%M:%S UTC (+00:00)'
git rev-parse HEAD origin/main; git status --short --branch
python -P -m arnold_pipelines.megaplan resident context --node root --store-root "$MEGAPLAN_RESIDENT_STORE_ROOT"
python -P -m arnold_pipelines.megaplan resident status-tree --node 'session/agent-edit-verifiable-transaction-spine' --store-root "$MEGAPLAN_RESIDENT_STORE_ROOT"
python -P -m arnold_pipelines.megaplan introspect --plan /workspace/agent-edit-verifiable-transaction-spine/vibecomfy/.megaplan/plans/sprint-2-transactional-apply-20260714-0336
jq ... state.json chain-e2e81558e8a3.json repair-data.json requests/*.json attempts/*.json decisions/*.json
rg -n -C 4 'blocked|90 iterations|T7|T12|repair' cloud-chain-agent-edit-verifiable-transaction-spine.log
ps -eo pid,lstart,etime,args
sha256sum /usr/local/bin/arnold-* arnold_pipelines/megaplan/cloud/wrappers/arnold-*
python -m pytest -q tests/observability
python -m compileall -q arnold_pipelines/megaplan/observability
git diff --check
```

Repository reconciliation at the final snapshot: the resident checkout remained
at `612b139971e1a65d2a40f9e387a5e8ff3e2ab960`, one commit ahead and eight behind
its local `origin/main`, with extensive unrelated dirty work. The clean corrective
worktree is based on `7644f55dd9be75632670f990268e045d3ee1c2f7`, matching the
active chain runtime mirror.
