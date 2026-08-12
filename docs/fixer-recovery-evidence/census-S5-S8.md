# Census S5–S8 — liveness, repair identity, queue relations, mutation gates

Collected: 2026-08-11 (UTC, read-only). No mutations performed. Credentials/tokens redacted.

## S5 — Liveness / fences / runner leases

- Latest watchdog report `/workspace/watchdog-reports/20260811T130059Z.json` (13:00:59Z, 17,483 bytes; also `/workspace/watchdog-report.json`): `alive_sessions=0`, `codex_repair_enabled=true`, `issue_count=13`, `push_repairs_enabled=false`, `reaped_repairs=0`, `restarted_sessions=0`. megaplan-maintenance: action=repair, status=repair_unavailable. (Earlier report 20260811T102230Z also read; the 13:00:59Z report is the latest per R14.)
- megaplan-maintenance liveness lease (`.megaplan/cloud-sessions/megaplan-maintenance.liveness-lease.json`): FULL identity present —
  `attempt_id=63a83b24-a191-4e0b-915c-538e5d852c25`, `incarnation_id=289fae7e-ccf8-4921-80df-5e2f38ef4aba`,
  `lease_id=1aac8fc2-9d73-4f92-b687-5471cce9e931`, `authority=runner-owned-liveness-only`,
  `publisher_pid=5598`, `pid_namespace_id=pid:[4026532694]`, `marker_binding=sha256:22a76197...`,
  `record_digest=sha256:d0f95029...`, `generated_at=2026-08-11T06:40:31.092472Z`,
  `expires_at=2026-08-11T06:40:31.092472Z` — EXPIRED (lease lifetime was instantaneous).
  Fence: `runner_fence=1` (schema arnold.megaplan.runner_liveness_fence.v1). Runner: stopped.
- Liveness lease/fence sidecar files present for 8 sessions (megaplan-maintenance, critique-ledger v3/v3-r5/v3-r6/v3-r7, bigbang, vj24-migration); ALL report stopped/expired or empty (per S8, alive_sessions=0).
- All other sessions: liveness UNKNOWN — watchdog:8522-8536 fences every mutation path on canonical liveness (`legacy PID/tmux evidence remains diagnostic-only`). `alive_sessions=0` is global.
- Watchdog process itself alive (tmux `watchdog`, sweeps ~every 5-9 min, reports in /workspace/watchdog-reports/).

## S6 — Repair identity join (request → decision → claim → attempt)

- **Request:** `/workspace/.megaplan/repair-queue/requests/` has 299 files. ONLY ONE mentions megaplan-maintenance: `346786db8fe6bca667d6beea9c4c13010852b63026f07636c5a5b926ab385dbe.json` — STALE (created 2026-07-11T02:18:04Z, targets plan m1-containment-and-truthful-20260711-0021, failure_kind=iteration_cap, state=finalized). NO request exists for the CURRENT run (m1-containment-and-truthful-20260811-0640).
- **Decision:** `/workspace/.megaplan/repair-queue/decisions/` — latest 2026-08-07T175517Z (3 days before this epic's launch). No decision for the current run.
- **Claim:** `/workspace/.megaplan/repair-queue/active-claims/` — no megaplan-maintenance entry. `occurrence-claims/` — 0 entries.
- **Attempt:** `/workspace/.megaplan/repair-queue/attempts/` — 137 files, latest 2026-08-03T154311Z. None for this epic's current run.
- **Identity outcome: `claimable: no`.** Watchdog per-sweep: `repair request claim failed; refusing dispatch session=megaplan-maintenance request=unknown status=missing_identity` then `mechanical relaunch fenced pending phase-contract repair custody session=megaplan-maintenance phase=gate dispatch=unavailable`.
- Classifier (dual path, verified at repair_contract.py:2040-2068): (i) a CANONICAL machine-actionable block with NO active request yields `decision=DISPATCH_DECISION_NO_ACTION`, `dispatch_intent=DISPATCH_INTENT_QUEUE_ONLY` (repair_contract.py:2053-2060, rationale "canonical machine-actionable block without active request"); (ii) `CanonicalState.UNKNOWN` yields `BROKEN_SUPERFIXER` (repair_contract.py:2064-2068, `if state is CanonicalState.UNKNOWN: ... decision=DISPATCH_DECISION_BROKEN_SUPERFIXER`). The live watchdog status showed broken_superfixer because it classified the session's canonical state as UNKNOWN (chain state=dead, liveness UNKNOWN fences). BOTH attributions are consistent: no actionable request exists (NO_ACTION branch), and the session state is UNKNOWN (BROKEN_SUPERFIXER branch). Claim auto-fill only fires when decision == `dispatch_l1_repair` (arnold-watchdog:5125); claim_active_repair_launch (arnold-watchdog:5532) returns `missing_identity` (5543-5546) when blocker/request empty.
- **Claim locks: 66 entries in active-claims/, ALL EMPTY/unowned** (single snapshot 2026-08-11T13:19:46Z: 21 `.lock` files + 45 `.managed-run-bind` files, 0 non-lock owner files, 0 dirs, all 0-byte). No active claim exists for any session.
- Enqueue site: `arnold-watchdog:1648` calls `enqueue_occurrence_bound_repair_request(...)` WITHOUT capturing the return (W2) — `zero_authority_rejected` (repair_requests.py:939-949) silently dropped. Six `repair_unavailable` branches (watchdog:7952,8099,8583,8842,8886,9090) exit BEFORE the enqueue site — no path ever materializes a request for this run. NOTE: `zero_authority_rejected` as the mechanism is an INFERENCE from code reading (repair_requests.py:939-949); the live enqueue return value is not captured anywhere, so no runtime evidence proves it fired — the fact is that NO request exists for the current run, which is direct evidence.

## S7 — Mutation gates (values present, secrets redacted)

| Gate | Env var | Box value | Effect |
|---|---|---|---|
| Master autonomy | ARNOLD_AUTONOMY | 1 | mutation_authorized(path) = autonomy AND path_gate (feature_flags.py) |
| L1 repair trigger | ARNOLD_REPAIR_TRIGGER_ENABLED | 1 | L1 path gate ON |
| L2 meta-repair | ARNOLD_META_REPAIR_ENABLED | 0 | L2 path gate OFF (deliberate 07-27 pause) |
| L2 commit | ARNOLD_META_REPAIR_COMMIT_ENABLED | 0 | off |
| L3 audit autofix | ARNOLD_AUDIT_AUTOFIX_ENABLED | 1 | L3 path gate ON |
| L3 commit | ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED | 0 | GHOST — read into flag passed to argument-ignoring heredoc (W2) |
| Audit recovery | MEGAPLAN_AUDIT_RECOVERY_ENABLED | 1 | lets audit invoke watchdog --audit-sweep when L3 authorized |
| Attestation | ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT | (absent) | defaults ON (deny-by-default) |

**Contradiction (W2):** the "durable supervisor pause (2026-07-27)" comment says "prevent it, the watchdog, or repair triggers from launching" — but with AUTONOMY=1 + TRIGGER=1 + AUDIT_AUTOFIX=1, L1 and L3 ARE authorized; only L2 is blocked. `ARNOLD_REPAIR_TRIGGER_SESSION_ALLOWLIST` does NOT exist in code (refuted again). `MEGAPLAN_AUDIT_SESSION_ALLOWLIST`/`PLAN_ALLOWLIST` are audit-report row filters only.

## S8 — Sessions inventory

- BLOCKED: megaplan-maintenance (0/6, deterministic `blocked_no_lease`, latest live failure at phase GATE 07:35:34Z, chain ground-truth says phase plan 07:21:26Z, count 3, supervisor loop stopped 07:40:52Z rc=20 streak ×5); custody-control-plane-20260714 (8/10, plan m10-safe-retry-recovery-and-20260723-1122).
- PAUSED (durable): critique-ledger v2/v3/v3-r2/r3/r4/r5 (0/4 each; r5 pr_state=open), custody-control-plane-m10-stable (0/2), discord-resident-lifecycle-corrective (1/6), critique-ledger-vj24-migration (0/1 initialized).
- DONE/COMPLETE: extension-foundation-completion, v3-r7-launch (3/4 last_state=done), megaplan-chain-reigh-extension-composition-spine (13), runauthority-epic-cloud (3), withings (4), superpom (4), repository-strategy-roadmap, megaplan-native-parity-corrective (per watchdog "chain complete" lines).
- Current failure signature (megaplan-maintenance): `deterministic_phase_failure`, phase gate/plan, `ActionBoundaryDeniedError: dispatch not authorized: blocked_no_lease`, count 3.
- Approved canonical request path: NO occurrence-bound request exists for any blocked/paused session; `claimable: no` for the only blocked active epic. Classifier yields NO_ACTION/QUEUE_ONLY for the canonical actionable block (repair_contract.py:2057).

## Verdict

Fixer is inert box-wide: alive_sessions=0, no valid liveness records, no occurrence-bound request, L1 claim dies at missing_identity, L2 disabled, hourly cancelled/consumerless. Exclusions are purely state/identity fences (paused/liveness-unknown), not allowlists.
