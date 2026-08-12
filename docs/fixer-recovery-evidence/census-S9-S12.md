# Census S9–S12 — dependency, GC, schedule, reconciliation references

Collected: 2026-08-11 (UTC, read-only). No mutations performed.

## S9 — Declared venv/dependency fields vs existence

| Declared path | Exists? |
|---|---|
| /workspace/runtime-candidates/megaplan-maintenance/.venv (manifest epic.venv_path + base.venv_path) | NO |
| /workspace/runtime-candidates/*/.venv (any tree) | NO — zero per-epic venvs anywhere |
| /workspace/runtime-venvs/arnold-4ed98585...-live (shared supervisor venv) | YES — the only venv; watchdog/resident use it |
| Empty editable-engine shells: discord-resident-lifecycle-corrective-20260710, megaplan-maintenance, megaplan-native-parity-corrective, omp-replaces-hermes, repository-strategy-roadmap, runauthority-epic-cloud, runauthority-epic, runauthority-sprint-1 (`.megaplan/runtime/editable-engine`) | EMPTY dirs (legacy editable-install locations, retired P4) |

Schema contradiction (B6): runtime_manifest.py:81-88 makes `venv_path` REQUIRED; arnold-runtime-create:283-289 writes the field but never builds a venv; the design mandates ONE shared frozen venv (end-state doc:34-39, "not yet implemented":74-76). install_sync.py:299-365 is dormant-but-armed (sync_policy {} → not disabled → would exec a missing venv python if called; zero callers today).

## S10 — Runtime-root reference union (dangling detection)

**Per-store root-reference matrix** (store → references → coverage):

| Store | Path | Root refs inspected | Status |
|---|---|---|---|
| Manifests | /workspace/.megaplan/*.json | megaplan-maintenance.json (epic.runtime_root, expected_head); others not runtime manifests | 1 real manifest; covered |
| Chain states | /workspace/*/Arnold/.megaplan/plans/.chains/chain-*.json | metadata.execution_environment.engine_root (17 chains listed in S2) | 9 dangling, 1 shared-split, 1 conflicted, 1 resident, 3 empty-shell, 1 project-root |
| Cloud-session markers | /workspace/.megaplan/cloud-sessions/*.json | session, workspace, relaunch_command (ENGINE_DIR derivation) | covered (S1/S5-S8); relaunch commands reference manifest runtime_root w/ shared fallback |
| Health markers | /workspace/.megaplan/cloud-sessions/*.chain-health.progress.json | chain_complete, current_plan_name, last_state | covered (S8) |
| Liveness leases/fences | /workspace/.megaplan/cloud-sessions/*.liveness-{lease,fence}.json | status, expires_at | covered (S5): stopped/expired, 0 valid |
| Schedules | /workspace/arnold/.megaplan/resident/schedules/heads/*.json | schedule_id, state (cancelled/paused/exhausted) | covered (S11): all superfixer schedules cancelled/paused/exhausted |
| Scheduled jobs | /workspace/arnold/.megaplan/resident/scheduled_jobs/*.json (73 files) | job_type (vp_todo_sweep only), status, interval | covered (S11): 73 stale, no fixer jobs |
| Repair requests | /workspace/.megaplan/repair-queue/requests/*.json (299) | session, plan_name, failure_kind, created_at | covered (S6): only 1 stale request (Jul 11, wrong plan); none for current run |
| Repair decisions | /workspace/.megaplan/repair-queue/decisions/*.json | decision, request_id, timestamp | covered (S6): latest Aug 7, none for current run |
| Claims | /workspace/.megaplan/repair-queue/active-claims/*.json | session, blocker_id, owner pid | covered (S6): no megaplan-maintenance claim |
| Occurrence claims | /workspace/.megaplan/repair-queue/occurrence-claims/ | count = 0 | covered (S6): empty |
| Attempts | /workspace/.megaplan/repair-queue/attempts/*.json (137) | attempt records | covered (S6): latest Aug 3, none for current run |
| Repair leases/locks | /workspace/.megaplan/repair-queue/active-claims/ — 66 entries @ 2026-08-11T13:19:46Z (21 `.lock` + 45 `.managed-run-bind`, all 0-byte; 0 non-lock owner files) | owner.json content, expiry, root ref | EXHAUSTIVELY inventoried (S6/R15): ALL EMPTY/unowned; no lease content, no owner, no expiry, no root ref exists in any file. Also occurrence-claims/ = 0 entries; decisions/ latest 2026-08-07; attempts/ 137, latest 2026-08-03 |
| Global ops schedules | /workspace/.megaplan/ops/schedules/ | two-chain-bc0-babysit-grant-v1.json (grant_codex_two_chain_three_hour_babysit_20260723, expires null) + prompt md | 2 files, Jul 23, grant-only (no fixer jobs) |
| Canonical status snapshot | /workspace/.megaplan/status/cloud-status.json | 1,799,215 bytes, mtime 2026-08-11T12:53:12Z (FRESH) | covered (W2): watchdog-owned; one unguarded reader (repair-loop:5670) |
| PR refs | refs/pull/*/head (engine repo) | count = 0 | no open PR refs |
| Repair claim locks | /workspace/.megaplan/repair-queue/active-claims/ (66 entries @ 2026-08-11T13:19:46Z: 21 .lock + 45 .managed-run-bind, all 0-byte) | owner/lock files incl. .managed-run-bind suffixes | inventoried (S6): all EMPTY/unowned; no megaplan-maintenance lock; 0 non-lock owner files |

**All 12 runtime-candidate paths (head/state/reference):**

| Candidate | HEAD | Branch | Dirty | Class |
|---|---|---|---|---|
| arnold-4ed98585...-live | 4ed98585f | detached | 0 | supervisor venv source |
| arnold-c60bfe61... | c60bfe61e | detached | 0 | legacy |
| arnold-r7-fresh-child-20260805-77b76e3a4 | 77b76e3a4 | detached | 0 | legacy |
| arnold-r7-fresh-child-20260805-a-fix | 079927677 | fix/r7-critique-custody-compat | 0 | legacy |
| **arnold-r7-fresh-child-20260805** | **7f6abcbe42** | **main** | **7 (.bak-*)** | **EXECUTED engine (shared v3-r7 + megaplan-maintenance)** |
| arnold-r7-immutable-20260805 | 0a4369db2 | detached | 0 | immutable candidate |
| arnold-wbc-83d26e77cf | 83d26e77c | detached | 0 | legacy |
| arnold-wbc-full-20260804 | c116f38cc | fix/isolated-chain-runner-20260803 | 0 (porcelain clean; CONFLICT via UU/DU) | v3-r5 engine, UNRESOLVED MERGE |
| arnold-wbc-r5-full-20260804 | 5a64bdd10 | detached | 8 | legacy dirty |
| critique-session-binding-20260723 | BROKEN gitdir (parent GC'd) | — | 1 | BROKEN WORKTREE |
| **megaplan-maintenance** | **f410585d56** | **fixer/megaplan-maintenance-20260811** | 0 | manifest-bound epic runtime (NOT executed; .venv missing) |
| preserved-arnold-megaplan-vendor-pre-m11-20260731 | NOT a git repo | — | 2 | vendor snapshot |

**Dangling targets (reference exists, target dir gone):** 9 engine roots (S2 table) +
broken worktree gitdir (critique-session-binding-20260723 → arnold-bc0c600c GC'd parent).

**Chain count reconciliation (single snapshot 2026-08-11T13:19:46Z):** S2 enumerates 17 DISTINCT chains across 19 chain-*.json files (the 19 includes two custody-control-plane-20260714 chain records both referencing runauthority's editable-engine, plus 1 null record v3-20260803). The root-union classes: 9 MISSING, 1 NULL (v3-20260803), 2 SHARED refs (v3-r7 + megaplan-maintenance → arnold-r7-fresh-child-20260805), 1 CONFLICTED (v3-r5), 1 RESIDENT-bound (megaplan-native-parity-corrective), 4 EMPTY-SHELL refs (discord-resident-lifecycle-corrective, runauthority-epic-cloud, runauthority-epic, runauthority-sprint-1), 1 PROJECT-ROOT (runauthority-epic-all-codex), 1 PRESENT+SPLIT (megaplan-maintenance). Empty-shell refs: 4 total (discord-resident-lifecycle-corrective, runauthority-epic-cloud, runauthority-epic, runauthority-sprint-1) — the S2 dump shows 4 DISTINCT chains; the earlier '3 shells' figure omitted runauthority-sprint-1.

**Schedule/job exact totals (R14):** 53 schedule heads in `/workspace/arnold/.megaplan/resident/schedules/heads/`; 73 scheduled jobs in `scheduled_jobs/` (all `vp_todo_sweep`); 2 files in `/workspace/.megaplan/ops/schedules/` (grant + prompt). Superfixer schedules: sched_superfixer_hourly_global=CANCELLED, sched_superfixer_hourly_v2=CANCELLED, sched_superfixer_r7_reconcile_20260807=EXHAUSTED, sched_superfixer_r7_relaunch_20260807=EXHAUSTED, sched_critique_r7_superfixer_babysit_20260806_v1=PAUSED; remaining ~48 heads are legacy critique/custody babysit schedules (paused/cancelled/exhausted, Jul 16–Aug 8). No due-job consumer exists; `superfixer_proactive` (scheduler.py:479-545) raises `PlannedOutcome` with no launch consumer.

**Unreadable/corrupt/absent stores:** cloud-status-snapshot.json (Jul 6, zero readers — inert); empty editable-engine dirs (4 used as engine_root — discord-resident-lifecycle-corrective, runauthority-epic-cloud, runauthority-epic, runauthority-sprint-1; executing from an empty dir would fail at import); v3-r5 engine (arnold-wbc-full-20260804) present but CONFLICTED (UU/DU) — executing from a conflicted tree. All classified NON-GREEN.

**GC coverage correction (G1):** arnold-gc-sweep checks schedule stores — but ONLY scheduled_jobs + ops/schedules (`SCHEDULE_STORES=("/workspace/arnold/.megaplan/resident/scheduled_jobs" "/workspace/.megaplan/ops/schedules")`, gc-sweep:79-89) — NOT the resident schedule HEADS store (schedules/heads/, where the 53 superfixer schedule definitions live). Missing stores are SKIPPED (`if missing ... not a reference`, gc-sweep:86-87) and unreadable `grep` errors are suppressed (gc-sweep:94,106) — a FAIL-OPEN reference condition, classified UNKNOWN/NON-GREEN here. It also probes `refs/pull/*/head` (gc-sweep:174-185). Correct claim: **chain/queue/status/schedule-heads-reference-blind, with fail-open on missing/unreadable stores**.

## S11 — Hourly job state

- Schedules (resident store /workspace/arnold/.megaplan/resident/schedules/heads/):
  - sched_superfixer_hourly_global — CANCELLED (rev 2)
  - sched_superfixer_hourly_v2 — CANCELLED (rev 3)
  - sched_superfixer_r7_reconcile_20260807 — EXHAUSTED
  - sched_superfixer_r7_relaunch_20260807 — EXHAUSTED
  - sched_critique_r7_superfixer_babysit_20260806_v1 — PAUSED
  - 48 legacy critique/custody babysit schedules (paused/cancelled/exhausted, Jul 16–Aug 8) [53 heads − 5 superfixer]
- scheduled_jobs store (/workspace/arnold/.megaplan/resident/scheduled_jobs/): 73 stale `vp_todo_sweep` jobs (all fired, 6h interval, Jul 7-20).
- Resident container runs `--listener-only` → scheduler worker NEVER built (cli.py:1056 `if not listener_only`).
- **Due-job consumer: NONE.** `superfixer_proactive` (scheduler.py:479-545) writes a dispatch plan and raises `PlannedOutcome` — no launch consumer exists. Launch receipt: NONE.

## S12 — Reconcile / close / GC / branches

- **P6 live successes: 0.** No `kind: reconcile` milestone in ANY chain.yaml; `git for-each-ref | grep -c reconcile` on the box = 0; no reconcile-verification.json / reconcile_inputs.json / reconcile-skip.json on disk or in git history. All 8 "done" epics completed via the pre-P6 legacy path (milestone done → chain complete), exempt from the P6 guard by design (chain/__init__.py:9236-9240).
- **TRAP:** ensure_reconcile_milestone (chain/__init__.py:6805-6995, called unconditionally at run_chain:6996) appends a new kind:reconcile milestone to any spec lacking one with NO chain_complete guard — a completed legacy epic re-run under P6 code regresses to a pending reconcile milestone requiring a fail-closed gh PR.
- **Orphan fixer branches on origin:** fixer/critique-epoch-invalidation-20260806 @ 49af598c0 (content IN main via manual merges, ref never deleted); fixer/fixer-unification-20260807 @ bf18142fc (same); fixer/megaplan-maintenance-20260811 @ f410585d56 (0 unique commits — scaffolded from main, epic never wrote to it, 2 commits behind main).
- **Legacy editible-install:** @ 8c4b2c9561, 67 commits never in main, still referenced by .megaplan/initiatives/canonical-run-state-control-plane/cloud.yaml megaplan.ref + custody-control-plane evidence.
- **GC receipts:** arnold-gc-sweep checks schedule stores (`_schedule_store_references`, gc-sweep:84-89, stores at :79-81) and probes `refs/pull/*/head` (gc-sweep:174-185) but is CHAIN/QUEUE/STATUS-reference-blind — it never checks recorded chain engine_roots, cloud-session markers, repair-queue records/leases, or the canonical status snapshot. No close/restore/GC receipts exist for any epic (no arnold-close ever ran on completed chains). 9 dangling roots + 1 broken worktree prove the gap.

## Verdict

Dependency model is a false contract (venvs declared, never built); GC is chain/queue/status-reference-blind (9 dangling roots); hourly backstop is cancelled + consumerless; reconcile/merge-into-main has zero live instances; orphan branches survive without cleanup.
