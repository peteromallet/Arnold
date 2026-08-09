# M9 — WBC Boundary Adoption Matrix: Reader Consumer Inventory

Generated: 2026-07-22
Scope: M9 rebuildable projections and liveness consumer cutover
Schema: m9.wbc-boundary-adoption-matrix.v1

## Summary

This matrix enumerates **every named M9 consumer** across five reader domains
and classifies each as **observer-only**, **negative-gate-only**, or
**positive-control-path**.  Positive-control-path consumers carry explicit
reread obligations because they are the only consumers whose projection reads
could influence bearer-authority decisions (dispatch, repair, retry,
completion, cancellation, publication).

The North Star invariant (SD2) is:

> Projections may deny, block, diagnose, emit drift, or surface uncertainty,
> but they are never bearer authority for dispatch, repair, retry, completion,
> cancellation, publication.

Positive-control-path consumers MUST perform a post-projection-exact-cursor
reread before authorizing any bearer action.

---

## Classification Legend

| Classification | Meaning | Reread obligation |
|---|---|---|
| `observer-only` | Reads projections purely for display, diagnostics, or logging. Never influences control flow. | None |
| `negative-gate-only` | Reads projections to block/deny/suppress actions (fail-closed). Never positively authorizes. | None (fail-closed is safe without reread) |
| `positive-control-path` | Reads projections to positively authorize dispatch, repair, retry, or completion. | **MUST reread with exact cursor before authorizing** |

---

## 1. CLI Status View (`cli/status_view.py`)

| # | Consumer | Classification | Evidence |
|---|---|---|---|
| C01 | `handle_status` (megaplan status) | observer-only | Reads state.json, finalize.json; produces display payload. Non-authoritative `legacy_route_hints` explicitly labeled `display_only_non_authoritative`. |
| C02 | `handle_audit` (megaplan audit) | observer-only | Reads state.json for audit payload; `handle_audit_query` and `handle_audit_report` delegate to receipt readers. |
| C03 | `handle_progress` (megaplan progress) | observer-only | Reads finalize.json + batch artifacts for progress summary. |
| C04 | `handle_watch` (megaplan watch) | observer-only | Delegates to `handle_status`; identical observer contract. |
| C05 | `_build_status_payload` | observer-only | Core payload builder: consumes `plan_status_presentation`, `anchor_summary`, `read_valid_targets`, `workflow_cursor`. Returns `status_route_authority: "workflow_source_only"`. |
| C06 | `_build_progress_payload` | observer-only | Reads finalize.json + `execution_batch_*.json` overlays; pure progress projection. |
| C07 | `_build_blocker_recovery_context` | observer-only | Reads `phase_result.json` for diagnostic blocker enumeration. Does not authorize repair. |
| C08 | `_build_blocked_tasks_context` | observer-only | Diagnostic blocked-task enumeration from shared recovery data. |
| C09 | `_compute_user_action_blockers` | observer-only | Computes user-action blocker details for progress/status payloads. |
| C10 | `_build_active_step` | observer-only | Phase observability (stale detection, idle timeout, orphan detection). Diagnostic only. |
| C11 | `_observed_workflow_phase` | observer-only | Derives workflow phase from state history. |
| C12 | `_recovery_projection_state` | observer-only | Projects recovery phase from resume_cursor. |
| C13 | `_projected_outcome` (local) | observer-only | Local RunOutcome projection from current_state string. |
| C14 | `_projected_valid_next` | observer-only | Projects valid next steps from state history. |

## 2. Observability / Introspect (`observability/introspect.py`)

| # | Consumer | Classification | Evidence |
|---|---|---|---|
| C15 | `build_introspect_payload` | observer-only | Structured JSON snapshot: now_utc, rubric drift, liveness, block details, evidence window, cost. Pure observation. |
| C16 | `_compute_liveness` | observer-only | Tri-state liveness (progressing/quiet/stalled/timeout-imminent) from events + active_step. |
| C17 | `_compute_block_details` | observer-only | Block details with `recoverable_via` enumeration. The `recoverable_via` list is **diagnostic**, not authoritative — consumer must resolve through control_interface. |
| C18 | `_compute_rubric_drift` | observer-only | Drift between prep_skill.md and installed profiles. |
| C19 | `_process_tree` | observer-only | Process tree enumeration via psutil. |
| C20 | `_git_info` | observer-only | Git branch, dirty flag, head hash. |
| C21 | `_load_state` | observer-only | Loads state.json from plan_dir. Cache-tolerant probe. |
| C22 | `_projected_outcome` (local) | observer-only | Local RunOutcome projection (duplicate of C13). |

## 3. Cloud Readers

| # | Consumer | Classification | Evidence |
|---|---|---|---|
| C23 | `cloud/status_snapshot.py:build_cloud_status` | observer-only | Canonical cloud-status.json builder. Reads session markers, chain-health sidecars, watchdog reports, plan states. The snapshot is a **diagnostic projection** — consumers that act on it carry their own classification. |
| C24 | `cloud/status_snapshot.py:build_and_write_snapshot` | observer-only | Builds + writes snapshot with cursor-checked projection events (M7+). Supplemental evidence, not authority. |
| C25 | `cloud/status_snapshot.py:load_cloud_status_snapshot` | observer-only | Loads snapshot with optional staleness check. Legacy readers accept file as authority without cursor validation. |
| C26 | `cloud/status_snapshot.py:rebuild_status_snapshot_projection` | observer-only | Rebuilds projection from append-only history. |
| C27 | `cloud/watchdog.py:check_watchdog_dispatch_acceptance_gate` | **negative-gate-only** | Checks acceptance gate before watchdog dispatch. Blocks dispatch when acceptance absent; never positively authorizes. Emits typed blocker events. |
| C28 | `cloud/watchdog.py:assess_watchdog_accepted_progress` | observer-only | Classifies snapshot entry activity (accepted_progress / waiting / fixer_infra / auto_continuation / idle). Escalation decision is downstream. |
| C29 | `cloud/watchdog.py:_shadow_validate_watchdog_boundary` | observer-only | M7 shadow validation during dispatch gating. Non-blocking; enforcement always disabled. |
| C30 | `cloud/progress_auditor_liveness.py:classify_runner_liveness` | observer-only | Tri-state `alive|dead|unknown` from tmux + active_step + watchdog statuses. |
| C31 | `cloud/progress_auditor_controller.py` | **positive-control-path** | Durable effect controller. **Launches managed repairs** via `plan_dispatch` → subprocess trigger. This is bearer-authority: the controller positively authorizes repair dispatch based on projection reads. **REREAD OBLIGATION: must reread stall evidence with exact cursor before launching.** |
| C32 | `cloud/progress_auditor_escalation.py:classify_true_stall` | **negative-gate-only** | Determines if a stall finding qualifies as "true stall" (validated gate). Blocks escalation for non-true stalls. |
| C33 | `cloud/progress_auditor_escalation.py:validate_managed_launch` | **negative-gate-only** | Validates managed-launch preconditions (session, spec, workspace). Blocks launch when invalid. |
| C34 | `cloud/progress_auditor_escalation.py:plan_dispatch` | **positive-control-path** | Plans dispatch parameters for managed repair launch. **REREAD OBLIGATION: must reread chain state with exact cursor before planning dispatch.** |
| C35 | `cloud/progress_auditor_ownership.py:launch_suppressed_by_existing_owner` | **negative-gate-only** | Checks if existing managed-agent owner overlaps repair objective. Suppresses launch when aligned owner exists. |
| C36 | `cloud/six_hour_auditor.py:build_audit_input` | observer-only | Assembles deterministic audit input from incident ledger. |
| C37 | `cloud/six_hour_auditor.py:assemble_audit_report` | observer-only | Assembles audit report from layered findings. |
| C38 | `cloud/six_hour_auditor.py:enqueue_audit_repair_request` | **positive-control-path** | Enqueues repair request into durable repair queue. **REREAD OBLIGATION: must reread finding evidence with exact cursor before enqueuing.** |
| C39 | `cloud/terminal_audit.py:run_terminal_audit` | **positive-control-path** | Runs deterministic L2 terminal audit; **retriggers repair** via subprocess when pre-snapshot is accepted. **REREAD OBLIGATION: must reread terminal snapshot with exact cursor before retriggering.** |
| C40 | `cloud/terminal_audit.py:capture_terminal_snapshot` | observer-only | Captures authoritative terminal snapshot from session marker + chain state + plan state. |
| C41 | `cloud/auditor_external_evidence.py` | observer-only | Read-only external evidence collectors (GitHub PR state, CI checks, engine tree consumers). |
| C42 | `cloud/wrapper_acceptance_gate.py:check_wrapper_acceptance_gate` | **negative-gate-only** | Checks acceptance gate for cloud wrapper restart/relaunch. Blocks when acceptance absent in fail-closed mode. |
| C43 | `cloud/repair_contract.py:classify_cloud_custody` | observer-only | Classifies cloud custody state. Diagnostic only. |
| C44 | `cloud/repair_contract.py:classify_repair_dispatch` | observer-only | Classifies repair dispatch state. Diagnostic only. |
| C45 | `cloud/repair_contract.py:project_repair_custody` | observer-only | Projects repair custody from durable state. |
| C46 | `cloud/repair_contract.py:durable_repair_active` | observer-only | Checks if durable repair is active. |
| C47 | `cloud/human_blockers.py:classify_needs_human_blocker` | observer-only | Reads needs-human markers; classifies blocker state. |
| C48 | `cloud/current_target.py:resolve_current_target` | observer-only | Resolves current target (session, plan, chain). Reads state, doesn't authorize. |
| C49 | `cloud/repair_requests.py:enqueue_repair_request` | **positive-control-path** | Enqueues repair request into durable queue. **REREAD OBLIGATION: must reread before enqueuing.** |
| C50 | `cloud/repair_lock.py` | **negative-gate-only** | Repair lock acquisition/release. Lock is a negative gate — blocks concurrent repair. |
| C51 | `cloud/meta_repair.py` | **positive-control-path** | Meta-repair orchestration: coordinates L2/L3 repair retrigger, evidence collection, retry decisions. **REREAD OBLIGATION: must reread before orchestrating repair.** |
| C52 | `cloud/source_initiative_repair.py` | **positive-control-path** | Source-initiative repair launch. **REREAD OBLIGATION: must reread before launching.** |
| C53 | `cloud/dependency_manifest_repair.py` | **positive-control-path** | Dependency manifest repair dispatch. **REREAD OBLIGATION: must reread before dispatching.** |
| C54 | `cloud/supervise.py` | observer-only | Reads cloud status for supervision; does not authorize dispatch. |
| C55 | `cloud/cli.py` (status/supervise commands) | observer-only | CLI entry points for status display and supervision. |
| C56 | `cloud/operator_control.py` | observer-only | Operator control surface (reads status). |
| C57 | `cloud/incident_bridge.py` | observer-only | Incident bridge (reads incident state). |
| C58 | `cloud/preflight.py` | observer-only | Preflight checks (reads environment). |
| C59 | `cloud/status_retirement.py` | observer-only | Status retirement matching. |
| C60 | `cloud/session_retirement.py` | observer-only | Session retirement. |
| C61 | `cloud/session_markers.py` | observer-only | Session marker path classification. |
| C62 | `cloud/spec.py` | observer-only | Cloud spec loading. |
| C63 | `cloud/repair_recurrence.py` | observer-only | Recurrence tracking (reads history). |
| C64 | `cloud/repair_revalidation.py` | observer-only | Revalidation (reads repair state). |
| C65 | `cloud/semantic_findings.py` | observer-only | Semantic findings (reads incident ledger). |
| C66 | `cloud/repair_investigation.py` | observer-only | Repair investigation (reads evidence). |
| C67 | `cloud/redact.py` | observer-only | Redaction utility. |
| C68 | `cloud/meta_repair_policy.py` | observer-only | Meta repair policy (read-only classification). |
| C69 | `cloud/fixer_prompt_policy.py` | observer-only | Fixer prompt policy (read-only). |
| C70 | `cloud/feature_flags.py` | observer-only | Feature flag reads. |
| C71 | `cloud/status_format.py` | observer-only | Status formatting for display. |
| C72 | `cloud/github_sync.py` | observer-only | GitHub sync (reads state for sync decisions; sync itself is independent authority). |
| C73 | `cloud/install_sync.py` | observer-only | Install sync. |
| C74 | `cloud/manual_repair_trigger.py` | observer-only | Manual repair trigger (reads state; human authorizes). |
| C75 | `cloud/superfixer_episodes.py` | observer-only | Superfixer episode tracking. |

## 4. Resident Readers

| # | Consumer | Classification | Evidence |
|---|---|---|---|
| C76 | `resident/profile.py` (MegaplanResidentProfile) | **positive-control-path** | Resident bot profile: consumes `plan_status_presentation`, `cloud status_snapshot`. The resident can **launch subagents**, manage operations, and dispatch cloud runs. **REREAD OBLIGATION: must reread status snapshot with exact cursor before launching subagent or dispatching cloud run.** |
| C77 | `resident/status_tree.py:compact_cloud_status_snapshot` | observer-only | Compacts snapshot for bounded resident hot context. |
| C78 | `resident/status_tree.py:read_cloud_status_node` | observer-only | Reads specific status node for targeted inspection. |
| C79 | `resident/context_tree.py:build_context_root` | observer-only | Builds context root for resident prompts. |
| C80 | `resident/context_tree.py:read_context_node` | observer-only | Reads context node. |
| C81 | `resident/knowledge_context.py:build_knowledge_context` | observer-only | Builds knowledge context. |
| C82 | `resident/reply_chain.py:reply_chain_page` | observer-only | Reply chain paging. |
| C83 | `resident/query_relationship.py:correlate_semantic_follow_up` | observer-only | Semantic follow-up correlation. |
| C84 | `resident/subagent.py:launch_subagent_task` | **positive-control-path** | Launches subagent tasks (delegated task kinds: cloud run, repair investigation, etc.). **REREAD OBLIGATION: must reread run state before launching subagent.** |
| C85 | `resident/subagent.py:list_managed_resident_agents` | observer-only | Lists managed resident agents. |
| C86 | `resident/agent_loop.py` | observer-only | Agent loop: reads state for context; action decisions come from model, not projection reads. |
| C87 | `resident/cloud.py:CloudToolBackend` | observer-only | Cloud tool backend: reads cloud status; actual dispatch is via separate control path. |
| C88 | `resident/cloud.py:cloud_run_status_for_classification` | observer-only | Status classification for cloud runs. |
| C89 | `resident/cloud.py:progress_kind_for_classification` | observer-only | Progress kind classification. |
| C90 | `resident/provenance.py:normalize_delegation_provenance` | observer-only | Normalizes delegation provenance. |
| C91 | `resident/scheduler.py` | observer-only | Scheduler: reads state for job scheduling. |
| C92 | `resident/currently_running.py` | observer-only | Currently-running enumeration. |
| C93 | `resident/coalescing.py` | observer-only | Message coalescing. |
| C94 | `resident/dropped_threads.py` | observer-only | Dropped thread detection. |
| C95 | `resident/discord.py` | observer-only | Discord integration (reads status for messages). |
| C96 | `resident/discord_reactions.py` | observer-only | Discord reaction handling. |
| C97 | `resident/request_summary.py` | observer-only | Request summary generation. |
| C98 | `resident/vp_todo.py` | observer-only | VP todo list. |
| C99 | `resident/escalations.py` | observer-only | Escalation tracking. |
| C100 | `resident/transcription.py` | observer-only | Transcription. |
| C101 | `resident/timezone.py` | observer-only | Timezone service. |
| C102 | `resident/git_custody.py` | observer-only | Git custody. |
| C103 | `resident/config.py` | observer-only | Resident config reads. |
| C104 | `resident/auth.py:ResidentAuthorizer` | **negative-gate-only** | Authorization gating for resident actions. Blocks unauthorized actions; never positively authorizes (authorization comes from human confirmation). |
| C105 | `resident/cli.py` | observer-only | Resident CLI. |
| C106 | `resident/runtime.py` | observer-only | Resident runtime. |
| C107 | `resident/tool_registry.py` | observer-only | Tool registry. |
| C108 | `resident/tool_schemas.py` | observer-only | Tool schema definitions. |
| C109 | `resident/restart_resident.py` | observer-only | Restart resident. |
| C110 | `resident/profile.py:initiative_compact_index` | observer-only | Initiative index reads. |

## 5. Watchdog / Auditor Readers

| # | Consumer | Classification | Evidence |
|---|---|---|---|
| C111 | `cloud/watchdog.py:check_watchdog_dispatch_acceptance_gate` | **negative-gate-only** | Duplicate of C27. Blocks watchdog dispatch. |
| C112 | `cloud/watchdog.py:assess_watchdog_accepted_progress` | observer-only | Duplicate of C28. Activity classification for escalation. |
| C113 | `cloud/progress_auditor_liveness.py:classify_runner_liveness` | observer-only | Duplicate of C30. |
| C114 | `cloud/progress_auditor_controller.py` | **positive-control-path** | Duplicate of C31. Launches managed repairs. |
| C115 | `cloud/progress_auditor_escalation.py:classify_true_stall` | **negative-gate-only** | Duplicate of C32. |
| C116 | `cloud/progress_auditor_ownership.py:launch_suppressed_by_existing_owner` | **negative-gate-only** | Duplicate of C35. |
| C117 | `cloud/six_hour_auditor.py` | **positive-control-path** | Duplicate of C36-C38 context. The auditor escalates and enqueues repairs. |
| C118 | `cloud/terminal_audit.py:run_terminal_audit` | **positive-control-path** | Duplicate of C39. |
| C119 | `cloud/auditor_external_evidence.py` | observer-only | Duplicate of C41. |
| C120 | `cloud/wrappers/arnold-progress-auditor` (shell) | **positive-control-path** | Shell wrapper that invokes six_hour_auditor + progress_auditor_controller. Delegates repair launch authority. **REREAD OBLIGATION: wrapper must verify gate signals before dispatching.** |
| C121 | `cloud/wrappers/arnold-watchdog` (shell) | **negative-gate-only** | Shell wrapper that invokes watchdog dispatch gating. Blocks on closed acceptance gate. |
| C122 | `watchdog/processes.py:scan_processes` | observer-only | Process scanning for watchdog. |

## 6. Additional Observability Consumers

| # | Consumer | Classification | Evidence |
|---|---|---|---|
| C123 | `observability/doctor.py` | observer-only | Diagnostic surface: stale lock, phase timeout, LLM heartbeat, cost trajectory, orphan subprocesses, rubric drift. |
| C124 | `observability/trace.py` | observer-only | Trace tool for plan events. |
| C125 | `observability/cost.py` | observer-only | Cost tracking and reporting. |
| C126 | `observability/events_projection.py` | observer-only | Events projection from Store to NDJSON. |
| C127 | `observability/liveness.py` | observer-only | Liveness utilities (`has_active_in_flight_llm`, `unmatched_llm_starts`). |
| C128 | `observability/events.py:read_events` | observer-only | Event stream reader. |

---

## 7. Positive-Control-Path Summary (Reread Obligations)

These consumers MUST perform a post-projection exact-cursor reread before
authorizing any bearer action:

| Consumer ID | Module | Bearer Action | Reread Target |
|---|---|---|---|
| C31 | `cloud/progress_auditor_controller.py` | Launch managed repair | Stall evidence + chain state |
| C34 | `cloud/progress_auditor_escalation.py:plan_dispatch` | Plan dispatch parameters | Chain state |
| C38 | `cloud/six_hour_auditor.py:enqueue_audit_repair_request` | Enqueue repair request | Finding evidence |
| C39 | `cloud/terminal_audit.py:run_terminal_audit` | Retrigger repair | Terminal snapshot |
| C49 | `cloud/repair_requests.py:enqueue_repair_request` | Enqueue repair request | Repair state |
| C51 | `cloud/meta_repair.py` | Orchestrate repair | Chain + repair state |
| C52 | `cloud/source_initiative_repair.py` | Launch source repair | Initiative state |
| C53 | `cloud/dependency_manifest_repair.py` | Dispatch manifest repair | Manifest state |
| C76 | `resident/profile.py` (MegaplanResidentProfile) | Launch subagent / dispatch cloud run | Cloud status snapshot |
| C84 | `resident/subagent.py:launch_subagent_task` | Launch subagent task | Run state |
| C117 | `cloud/six_hour_auditor.py` | Escalate + enqueue repair | Audit findings |
| C118 | `cloud/terminal_audit.py:run_terminal_audit` | Retrigger repair | Terminal snapshot |
| C120 | `cloud/wrappers/arnold-progress-auditor` | Dispatch repair via controller | Gate signals |

---

## 8. Negative-Gate-Only Summary

These consumers block or deny actions but never positively authorize:

| Consumer ID | Module | Gate Action |
|---|---|---|
| C27 | `cloud/watchdog.py:check_watchdog_dispatch_acceptance_gate` | Blocks dispatch when acceptance absent |
| C32 | `cloud/progress_auditor_escalation.py:classify_true_stall` | Blocks escalation for non-true stalls |
| C33 | `cloud/progress_auditor_escalation.py:validate_managed_launch` | Blocks launch when preconditions invalid |
| C35 | `cloud/progress_auditor_ownership.py:launch_suppressed_by_existing_owner` | Suppresses launch when owner exists |
| C42 | `cloud/wrapper_acceptance_gate.py:check_wrapper_acceptance_gate` | Blocks wrapper restart when acceptance absent |
| C50 | `cloud/repair_lock.py` | Blocks concurrent repair via lock |
| C104 | `resident/auth.py:ResidentAuthorizer` | Blocks unauthorized resident actions |
| C121 | `cloud/wrappers/arnold-watchdog` | Blocks dispatch on closed gate |

---

## 9. Observer-Only Count

Total observer-only consumers: **103** (C01–C14, C15–C22, C23–C26, C28–C30, C36–C37, C40–C41, C43–C48, C54–C75, C77–C83, C85–C103, C105–C110, C112–C113, C119, C122–C128)

These consumers require no reread obligations. They may read projections
freely because their reads never influence bearer-authority decisions.

---

## Notes

1. **Duplicate entries**: Some consumers appear in multiple categories because
   the inventory cross-references them (e.g., watchdog.py appears in both
   Cloud Readers and Watchdog/Auditor Readers). The classification is
   consistent across sections.

2. **Compatibility bridges**: Per SD3, compatibility bridges (legacy
   `execution_batch_N.json`, etc.) remain allowed when explicitly
   non-authoritative, source-versioned, expiry-scoped, and backed by
   reader-count or zero-reader deletion gates.

3. **Shell wrappers**: `cloud/wrappers/arnold-progress-auditor` and
   `cloud/wrappers/arnold-watchdog` are shell scripts that delegate to Python
   modules. Their classification matches the modules they invoke.

4. **Uncertainty**: When a consumer could be classified either way, the more
   conservative classification (positive-control-path) is used to ensure
   reread obligations are not missed.

---

## 10. WBC Read-Path Classification: M6A API vs Raw/Prose/JSON Fallback

This section audits every in-scope WBC query consumer and raw receipt reader
against the M6A boundary.  "M6A API" means the consumer reads through the
typed, cursor-bound, content-addressed query/store surface
(``wbc_queries.py``, ``SqliteAttemptLedgerStore``, ``LedgerPayloadStore``,
``LedgerStoreAdapter``).  "Raw/JSON/Prose Fallback" means the consumer reads
mutable files directly (``.json``, ``.jsonl``, ``.ndjson``, prose text)
without going through the M6A API.

### 10.1 Read-Path Legend

| Path | Description | Risk |
|---|---|---|
| `M6A_API` | Reads through typed cursor-bound store/query surface with content-addressed evidence. | Minimal — evidence is durable and version-bound. |
| `RAW_JSON` | Reads mutable JSON files directly via `json.loads()` / `json.load()`. | Medium — raw files can be rewritten, and positive status can be derived from mutable evidence. |
| `RAW_JSONL` | Reads mutable JSONL/NDJSON files directly. | Medium — same as RAW_JSON but line-at-a-time; join gaps can suppress evidence. |
| `RAW_PROSE` | Parses unstructured prose text. | High — prose is the most mutable evidence form; derived status can drift silently. |
| `MIXED` | Uses a mix of M6A API and raw fallback within the same consumer. | Medium-High — the raw fallback path can produce positive status without version binding. |
| `STATIC_DISCOVERY` | Reads static source files (Python AST, JSON manifests) for inventory/metadata. | Low — discovery is observe-only and does not derive runtime status. |
| `REFERENCE_ONLY` | Carries WBC reference strings but does not read WBC data directly. | Low — no WBC data is read; references are pointers only. |

### 10.2 WBC Consumer Read-Path Inventory

#### WBC Runtime (`arnold/workflow/`)

| # | Consumer | Read Path | Evidence |
|---|---|---|---|
| W01 | `wbc_queries.py:WbcVerifiedResult` | `M6A_API` | Defines the M6A query contract. Exact-version results over durable source evidence. Requires `SourceCursor`, typed `WbcEventRef`, content-addressed digest. |
| W02 | `attempt_ledger_store.py:SqliteAttemptLedgerStore` | `M6A_API` | Core M6A store. All reads go through SQLite WAL with contract-version binding, monotonic sequence enforcement, idempotency-key dedup, and terminal-event gating. |
| W03 | `ledger_payload_store.py:LedgerPayloadStore` | `M6A_API` | Durable payload store enforcing `wbc.inline.v1` and `wbc.retention.v1`. Every read/write passes inline-threshold, redaction, secret-key, digest-only, and encryption checks. |
| W04 | `ledger_outbox.py` | `M6A_API` | Transactional outbox atomically joined to `SqliteAttemptLedgerStore`. Reads/writes happen inside the same SQLite transaction as the parent ledger event. |
| W05 | `ledger_trace.py:LedgerTrace` | `M6A_API` | Machine-readable traces over `LedgerEvent` data. Content-addressed, non-authoritative projection. Reads from store, not raw files. |
| W06 | `ledger_migrations.py:SqliteLedgerMigrator` | `M6A_API` | Schema migrations operate on the SQLite store. Reads/writes are transactional and version-bound. |

#### WBC Adapters and CLI

| # | Consumer | Read Path | Evidence |
|---|---|---|---|
| W07 | `adapters/ledger_store_adapter.py:LedgerStoreAdapter` | `M6A_API` | Process-safe wrapper around `SqliteAttemptLedgerStore`. Delegates all reads to the M6A store with retry/backoff for transient locks only. |
| W08 | `tools/wbc_ledger_cli.py` | `M6A_API` | JSON stdin/stdout shell adapter. All operations (append/read/query/reconcile/migrate) route through `LedgerStoreAdapter` → `SqliteAttemptLedgerStore`. Typed exit codes. |

#### Custody (reads WBC references, writes to own stores)

| # | Consumer | Read Path | Evidence |
|---|---|---|---|
| W09 | `custody/repair_receipt.py:RepairReceipt` | `MIXED` | Content-addressed custody receipt. References WBC attempt IDs as read-only pointers. Does not read WBC data directly, but carries `wbc_attempt_reference` strings. |
| W10 | `custody/repair_adoption.py` | `REFERENCE_ONLY` | Verify-only adoption decision. Compares receipt fields to current context. Carries WBC attempt references but does not read WBC store. |
| W11 | `custody/action_validator.py:validate_action_boundary` | `MIXED` | Conjunctive gate rereading Run Authority, Custody, and WBC attempt status. WBC reads are reference-resolution only (no direct store read); custody side reads from lease_store (RAW_JSONL). |
| W12 | `custody/lease_store.py:CustodyLeaseStore` | `RAW_JSONL` | Reads/writes `.history.jsonl` and `.state.json` directly. No M6A API. Custody-owned state; WBC references are read-only pointers. |
| W13 | `custody/outbox.py:CustodyOutbox` | `RAW_JSON` | Reads/writes `.record.json` and `.history.jsonl` directly. Carries cross-owner references (WBC attempt IDs) as pointers. No M6A API. |
| W14 | `custody/writer_map.py` | `STATIC_DISCOVERY` | Read-only provenance map. Reads static registries and manifest JSON. Does not read WBC data. |

#### Receipt Readers (raw JSON/JSONL fallback)

| # | Consumer | Read Path | Evidence |
|---|---|---|---|
| W15 | `receipts/query.py:handle_audit_query` | `RAW_JSONL` | Reads `receipts.jsonl` line-by-line via `json.loads()`. No M6A API. Filters by model/phase/profile/since, computes aggregations. Positive status (verdict, duration, cost) derived from mutable JSONL. |
| W16 | `receipts/extractors.py` | `RAW_JSON / RAW_PROSE` | Reads artifact JSON files via `_read_json_if_exists`, parses prose text via regex. Derives plan_metrics, critique_metrics, review_metrics from mutable text. No M6A API. |
| W17 | `receipts/writer.py:write_boundary_receipt` | `RAW_JSON` | Writes boundary receipts to JSON files. Not a reader per se, but produces mutable evidence consumed by raw readers. |
| W18 | `receipts/schema.py` | `STATIC_DISCOVERY` | Schema definitions only. No WBC reads. |

#### Observability / Events

| # | Consumer | Read Path | Evidence |
|---|---|---|---|
| W19 | `observability/events_projection.py` | `MIXED` | Reads from typed `Store` API (not WBC), projects to `events.ndjson`. The Store is typed; the output NDJSON is raw. |
| W20 | `observability/work_ledger.py` | `MIXED` | Reads from typed Store. Produces projection data. Writes to work-ledger JSON. |
| W21 | `observability/events.py:read_events` | `MIXED` | Event stream reader. Reads from Store API. |
| W22 | `observability/routing_ledger.py` | `RAW_JSONL` | Reads/writes `routing_ledger.jsonl`. No M6A API. |
| W23 | `observability/effect_enforcement.py` | `RAW_JSONL` | Reads/writes NDJSON journals and Store events for effect at-most-once enforcement. |
| W24 | `observability/cost.py` | `RAW_JSON` | Reads cost data from JSON files. No M6A API. |
| W25 | `observability/trace.py` | `RAW_JSONL` | Reads trace events from NDJSON. No M6A API. |
| W26 | `observability/evaluand.py` | `RAW_JSONL` | Reads evaluand data from JSONL. No M6A API. |
| W27 | `observability/fold.py` | `RAW_JSON` | Reads fold data from JSON. No M6A API. |
| W28 | `observability/liveness.py` | `RAW_PROSE` | Reads liveness signals from process/tmux evidence. Correlated evidence only. |

#### Cloud / Run State (raw evidence readers)

| # | Consumer | Read Path | Evidence |
|---|---|---|---|
| W29 | `run_state/evidence.py:NormalizedEvidence` | `RAW_JSON` | Consumes raw evidence dict from `resolve_current_target`. Reads tmux_process, active_step, plan_state, chain_state, needs_human, repair_progress, event_cursors, stale_evidence directly from mutable dicts. |
| W30 | `cloud/incident_bridge.py` | `RAW_JSONL` | Reads/writes `events.jsonl`. Incident and repair attempt events. No M6A API. |
| W31 | `cloud/manual_repair_trigger.py` | `RAW_JSON / RAW_JSONL` | Reads plan state via `_read_json_object`, reads JSONL lines via `json.loads()`. No M6A API. |
| W32 | `cloud/repair_investigation.py` | `RAW_JSON` | Reads JSON files via `json.loads()` at multiple call sites. No M6A API. |
| W33 | `cloud/repair_contract.py` | `REFERENCE_ONLY` | Carries `wbc_attempt_reference` strings. Resolves WBC refs from chain state, target refs, and signatures. Does not read WBC store directly. |
| W34 | `cloud/repair_requests.py` | `REFERENCE_ONLY` | Carries `wbc_attempt_reference` strings. Reference pointer only. |
| W35 | `cloud/operator_control.py` | `RAW_JSON` | Reads JSON files via `json.loads()`. No M6A API. |
| W36 | `cloud/human_blockers.py` | `RAW_JSONL` | Reads `events.ndjson` for error signatures. No M6A API. |
| W37 | `cloud/status_retirement.py` | `RAW_JSON` | Reads status records via `json.loads()`. No M6A API. |
| W38 | `cloud/github_sync.py` | `RAW_JSONL` | Reads/writes `events.jsonl`. Copies `events.ndjson`. No M6A API. |
| W39 | `cloud/dependency_manifest_repair.py` | `RAW_JSON` | Reads JSON files via `json.loads()`. No M6A API. |
| W40 | `cloud/auditor_external_evidence.py` | `RAW_JSON` | Reads JSON from subprocess stdout via `json.loads()`. No M6A API. |

#### Tools (static discovery or mixed)

| # | Consumer | Read Path | Evidence |
|---|---|---|---|
| W41 | `tools/generate_wbc_boundary_inventory.py` | `STATIC_DISCOVERY` | Reads Python AST and static manifest JSON. Produces `wbc-boundary-inventory.json`. Observe-only; no WBC API reads. |
| W42 | `tools/capture_wbc_contract_reality_fixtures.py` | `RAW_JSON / RAW_JSONL / RAW_PROSE` | Reads plan/run directories: `state.json`, `phase_result.json`, `events.ndjson`, `*.jsonl`, `execution.json`, `boundary_receipts/*.json`. Redacts prose bodies. Pure raw-file reading. |
| W43 | `tools/generate_m6_controlled_registries.py` | `STATIC_DISCOVERY` | Reads static registries and manifests. No WBC API reads. |
| W44 | `tools/generate_m6_replay_fixtures.py` | `STATIC_DISCOVERY` | Reads committed source files. Produces replay fixtures. No WBC API reads. |
| W45 | `tools/reconcile_m6_migration_matrix.py` | `STATIC_DISCOVERY` | Reads migration matrix, prerequisite verification, WBC inventory, controlled registries. Joins static data. No WBC API reads. |
| W46 | `tools/validate_m6_evidence.py` | `STATIC_DISCOVERY` | Validates static evidence files. No WBC API reads. |

#### Execution / Orchestration (mixed readers)

| # | Consumer | Read Path | Evidence |
|---|---|---|---|
| W47 | `execute/batch.py` | `MIXED` | Reads `boundary_evidence` (typed). Also reads artifacts via `read_json`, `sha256_file`. Uses `write_boundary_receipt` (RAW_JSON write). |
| W48 | `orchestration/completion_contract.py` | `RAW_JSON` | Reads `execution.json`, `review.json`, batch artifacts via `json.loads()`. Derives completion verdict from mutable files. |
| W49 | `orchestration/acceptance_transaction.py` | `MIXED` | Reads acceptance boundary snapshots. Mix of typed schemas and raw reads. |
| W50 | `orchestration/m8a_report.py` | `STATIC_DISCOVERY` | Pure report builder. Reads fixture data, writes evidence artifacts. No WBC API reads. |

---

## 11. Negative Fixture Rows: Positive Status Derived from Raw Mutable Evidence

These rows document every consumer whose **positive status** (verdict,
completion, progress, cost, liveness, repair eligibility, dispatch
authorization) is derived from raw mutable evidence (JSON, JSONL, NDJSON,
prose) rather than from the M6A typed durable store.  Each row is a
negative fixture — it records a risk that must be resolved before the
consumer can be promoted to a control path.

### 11.1 Negative Fixture Legend

| Risk Level | Meaning |
|---|---|
| `HIGH` | Positive status (completion, dispatch, repair authorization) derived from raw mutable files. The M6A store holds the same data but the consumer bypasses it. |
| `MEDIUM` | Diagnostic/projection status derived from raw mutable files. May suppress or misrepresent evidence without blocking control flow. |
| `LOW` | Observe-only static discovery. No positive status derived. |
| `RESOLVED` | Consumer already uses M6A API for all positive-status reads. |

### 11.2 Negative Fixture Table

| Fixture ID | Consumer (W##) | Risk | Positive Status Derived From | Raw Evidence Source | Resolution Path |
|---|---|---|---|---|---|
| NF01 | W15 (`receipts/query.py`) | `MEDIUM` | `verdict`, `duration_ms`, `cost_usd`, `scope_drift_severity` | `receipts.jsonl` (mutable JSONL) | Adopt `WbcQueryResult` from `wbc_queries.py` for all positive-status fields; keep raw JSONL for display-only projection. |
| NF02 | W16 (`receipts/extractors.py`) | `MEDIUM` | `plan_metrics`, `critique_metrics`, `review_metrics`, task/file counts | Artifact JSON files + prose text parsing | Route through `WbcEventRef`-bound store reads; prose parsing must produce `QualityOccurrence` not derived status. |
| NF03 | W29 (`run_state/evidence.py`) | `HIGH` | `is_live`, `liveness_status`, terminal completion, active repair | Raw evidence dict from `resolve_current_target` (mutable plan/chain/tmux state) | Adopt `WorkerLiveness` from `worker_identity.py`; use `SourceCursorVector` for terminal completion status. |
| NF04 | W12 (`custody/lease_store.py`) | `MEDIUM` | Lease state (acquired/released/expired/fenced) | `.history.jsonl` + `.state.json` (mutable JSONL) | Custody-owned state is acceptable as raw JSONL for custody's own domain, but cross-owner references must go through WBC store. |
| NF05 | W13 (`custody/outbox.py`) | `MEDIUM` | Outbox record status, reconciliation verdict | `.record.json` + `.history.jsonl` (mutable JSON) | Same as NF04 — custody-owned; cross-owner refs need WBC store validation. |
| NF06 | W48 (`orchestration/completion_contract.py`) | `HIGH` | `CompletionVerdict` (done/blocked/indeterminate) | `execution.json`, `review.json`, batch artifacts (mutable JSON) | Must cross-validate completion against `WbcVerifiedResult` from attempt ledger before publishing verdict. |
| NF07 | W23 (`observability/effect_enforcement.py`) | `MEDIUM` | At-most-once idempotency (journaled effects) | NDJSON journals + Store events (mutable files) | Effect journal uses typed Store backend; the NDJSON is a projection. Risk is moderate because the Store is the source of truth. |
| NF08 | W30 (`cloud/incident_bridge.py`) | `MEDIUM` | Incident events, repair attempts | `events.jsonl` (mutable JSONL) | Incident bridge should route repair attempt events through `SqliteAttemptLedgerStore.append` to get durable WBC evidence. |
| NF09 | W36 (`cloud/human_blockers.py`) | `MEDIUM` | Blocker state, error signatures | `events.ndjson` (mutable NDJSON) | Human blocker reads should use `WbcQueryResult` for attempt evidence; NDJSON is a projection only. |
| NF10 | W31 (`cloud/manual_repair_trigger.py`) | `HIGH` | Plan state, repair dispatch eligibility | `state.json` + JSONL lines (mutable JSON/JSONL) | Repair dispatch must validate against WBC attempt store before triggering. Raw plan state is not authority. |
| NF11 | W32 (`cloud/repair_investigation.py`) | `MEDIUM` | Investigation evidence | JSON files via `json.loads()` (mutable) | Investigation reads are diagnostic; risk is moderate. Should prefer store-backed reads for evidence integrity. |
| NF12 | W39 (`cloud/dependency_manifest_repair.py`) | `MEDIUM` | Manifest repair dispatch | JSON files via `json.loads()` (mutable) | Dependency manifest repair should confirm WBC attempt status before dispatch. |
| NF13 | W42 (`tools/capture_wbc_contract_reality_fixtures.py`) | `LOW` | None — observe-only fixture capture | Raw files from plan/run directories | This is a fixture generator; it does not derive runtime status. Low risk. |
| NF14 | W28 (`observability/liveness.py`) | `MEDIUM` | `has_active_in_flight_llm`, `unmatched_llm_starts` | Process/tmux evidence (mutable prose) | Liveness signals are correlated evidence per T6/T32; must use `WorkerLiveness` with typed uncertainty. |
| NF15 | W01 (`wbc_queries.py`) | `RESOLVED` | N/A — this is the M6A API itself | Durable SQLite store with content-addressed digests | No raw evidence path. The query API is the source of authority for WBC reads. |

### 11.3 Summary

| Risk Level | Count | Fixture IDs |
|---|---|---|
| `HIGH` | 3 | NF03, NF06, NF10 |
| `MEDIUM` | 10 | NF01, NF02, NF04, NF05, NF07, NF08, NF09, NF11, NF12, NF14 |
| `LOW` | 1 | NF13 |
| `RESOLVED` | 1 | NF15 |

**Total negative fixtures**: 15

**Key finding**: The M6A query API (`wbc_queries.py`) is currently only
imported by tests.  Zero production consumers use `WbcVerifiedResult` or
`WbcQueryResult`.  All production WBC reads either go through the lower-level
`SqliteAttemptLedgerStore` (which is M6A-adjacent but not the query contract)
or bypass the WBC store entirely via raw JSON/JSONL/prose reads.  The
adoption gap is the gap between raw-file readers and the typed query surface.

### 11.4 M6A Query API Adoption Status

| API Surface | Production Consumers | Test Consumers | Gap |
|---|---|---|---|
| `wbc_queries.py` (WbcVerifiedResult, WbcQueryResult) | **0** | 1 (`test_wbc_queries.py`) | Critical — the query contract exists but no production code uses it. |
| `SqliteAttemptLedgerStore` (direct) | 4 (W02, W04, W06, W07/W08) | 6 test files | Acceptable — direct store access is the M6A storage layer. |
| `LedgerPayloadStore` | 0 | 1 (`test_ledger_payload_enforcement.py`) | Gap — payload policy enforcement exists but no production writer uses `LedgerPayloadStore`. |
| Raw JSON/JSONL readers (bypass WBC store) | **21** (W12-W42) | N/A | Critical — 21 consumers derive status from mutable files. |
