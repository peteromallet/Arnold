# NBF-08 mutation-gap sweep

Read-only source census recorded 2026-08-31. This artifact does not change the
brief, addendum, surface inventory, tasklist, or source. Its comparison against
the 62 CC rows in `nbf08-control-surface-inventory.md` is the historical
pre-integration baseline; it is not the current authoritative census. The
current authoritative inventory is the 83-row `CC-001..CC-083` surface
inventory, with `MG-001..MG-015` integrated as `CC-069..CC-083`.

## Method and conclusion

The review used AST/function-definition enumeration plus targeted inspection of
calls to Store mutators, `write_plan_state`, atomic file writes, SQL `INSERT`/
`UPDATE`, provider effects, process launch/teardown, and scheduler dispatch.
Exact symbol presence was required; a row covering an underlying implementation
does not make an omitted public facade or route disappear.

Conclusion: **confirmed census gaps exist beyond the prior reviewer list**.
They are mostly public adapters/routes whose authority is already described by
an adjacent CC row, but their exact symbols are absent. They should be added to
the generated S6/S7 route matrix or explicitly listed as linked-domain adapters
before coverage is claimed. No claim is made here that these are second journal
authorities.

## Confirmed missing candidates

| Gap | Exact source symbols | Evidence of mutation/control | Nearest current row | Required treatment |
|---|---|---|---|---|
| MG-001 | `store/multi.py`: `MultiStore.append_telemetry_event` (569–576) | Delegates a telemetry append to the file store. | Exclusion mentions store telemetry; no exact facade symbol. | Mark `LINK`/non-authoritative telemetry, require chain-operation link when bound, or explicitly exclude this facade. |
| MG-002 | `store/multi.py`: `MultiStore.create_ticket`, `update_ticket`, `link_ticket_to_epic`, `unlink_ticket_from_epic`, `address_tickets_resolved_by_epic` (904–906, 935–942, 951–952) | Routes ticket creation/status/relationships to the owning backend. | CC-027 covers ticket domain; CC-036 covers compatibility wrappers, not `MultiStore`. | Add exact MultiStore route symbols to CC-027/CC-033 coverage and test backend routing plus idempotency. |
| MG-003 | `store/multi.py`: `acquire_execution_lease`, `heartbeat_lease`, `release_lease`, `acquire_lock`, `release_lock` (1060–1100) | Routes lease/lock acquire, heartbeat, and release; these gate execution and migration. | CC-006 covers occurrence leases, but not execution leases; no exact MultiStore lock facade. | Add linked lease/lock adapter coverage with holder, target, fencing/revision, and replay tests; preserve domain authority. |
| MG-004 | `store/multi.py`: `recover_stale_control_messages`, `upsert_resident_conversation`, `update_resident_conversation`, `upsert_resident_user_preference`, `append_progress_event`, `create_automation_actor`, `update_automation_actor` (1112–1113, 1118–1143, 1179–1180, 1189–1195) | Public facade routes recovery, resident persistence, progress append, and actor mutation. | CC-024, CC-035, CC-042, and CC-047 cover underlying domains, but omit this facade. | Add exact adapter route coverage or state a single linked-domain adapter rule that names these symbols. Actor changes must retain CC-035 authorization. |
| MG-005 | `store/_db/runtime.py`: `DBRuntimeMixin.insert_pending`, `mark_confirmed`, `mark_failed`, `mark_orphaned`, `create_image`, `attach_image`, `update_image`, `deactivate_active_image_reference`, `create_second_opinion`, `set_second_opinion_checklist_items`, `record_tool_call`, `log_system_event` | Direct SQL `INSERT`/`UPDATE` through `conn.execute`; examples at lines 14–79, 120–163, 249–302, 304–362, 364–388, 425+. | CC-036 names compatibility wrappers and CC-039 names some DB operation files, but this runtime mixin path is not named. | Add exact DB runtime symbols under CC-039/CC-036 linkage, with operation/idempotency and file/DB parity tests. |
| MG-006 | `cli/run.py`: public `cli_run` and mutation path `_run_pipeline` (177–226, 229+, 401–405) | Pipeline execution route persists `state.json` via `write_plan_state` before dispatch. | CC-033/CC-051 cover generic CLI/runtime routes but omit `cli/run.py`. | Add route matrix entry and test explicit plan/chain context, state-write receipt, and failure/replay behavior. |
| MG-007 | `resident/cli.py`: `run_resident_cli` and action routes `_resident_schedule`, `_resident_queue_subagent_successor`, `_resident_supersede_todo` (237–253, 296+, 323+, 499+) | Public dispatcher reaches schedule create/update/state/replay/run-once, queue launch, and TODO mutation. | CC-023, CC-047, CC-048 cover underlying service/profile paths, not CLI route/admission. | Add exact route symbols and tests that missing target/context rejects before mutation. |
| MG-008 | `resident/runtime.py`: `ResidentRuntime.recover_abandoned_turns`, `recover_restart_interrupted_turns`, `run_managed_completion_turn`, `_persist_inbound_event`, `_record_tool_calls`, `_handle_escalation_resolution`; `EmitProtocol.log_system_event`/`append_progress_event` (492–535, 680–740, 908–930, 1300–1310, 1394+) | Updates turns/messages/conversations/tool-call records, emits progress/system events, and can resume managed work. | CC-036/CC-042/CC-047 cover domains but do not identify this runtime admission/dispatch surface. | Add resident runtime route symbols as linked-domain controls; require provenance, operation IDs, and no inferred chain authority. |
| MG-009 | `resident/scheduler.py`: `proactive_seam_dispatch`, `StoreScheduledJobBackend.claim_due_jobs`, `mark_fired`, `mark_failed`, `ResidentScheduler.run_due_once`, `handle_cloud_check`, `handle_deferred_turn`, `handle_heartbeat`, `handle_confirmation_expiry`, `handle_superfixer_proactive`, `_launch_superfixer_managed`, `_record_superfixer_launch_receipt` (248–286, 327–365, 391+, 451–530, 907–970) | Claims/updates scheduled jobs, launches managed work, persists cloud results and occurrence transitions, and emits events. | CC-023/CC-047 mention schedules/profile actions but omit scheduler consumer/launch symbols. | Add exact scheduler consumer/launch coverage with claim fencing, occurrence linkage, and no duplicate dispatch. |
| MG-010 | `runtime/resume.py`: `save_composite_resume_cursor`, `ResumeCursor.save` (122–150, 278–305) | Directly calls `write_plan_state` and dual-writes resume cursor state. | CC-051 covers bridge resume, but not these public persistence callables. | Add exact resume-write symbols under CC-051/CC-061; require accepted-boundary context and CAS/replay tests. |
| MG-011 | `runtime/step_io_policy_adapter.py`: `write_megaplan_step_io_policy`, `record_megaplan_step_io_self_validation_marker` (57–70, 170–187) | Writes policy and self-validation marker JSON under project policy state. | No row names this adapter; CC-061 only names generic `_core/io.py` and state persistence. | Add as linked policy/artifact writes or explicitly exclude as non-chain policy state; if bound, require actor/context and digest evidence. |
| MG-012 | `runtime/memory_headroom.py`: `record_dispatch_memory_marker` (383–414) | Atomic replacement of per-plan dispatch/OOM marker. | No exact runtime marker symbol; CC-038 only lists selected marker/projection writes. | Add linked runtime-evidence symbol or explicit evidence-only exclusion, preserving best-effort semantics and digest/recovery provenance. |
| MG-013 | `runtime/budget_authority.py`: `BudgetAuthority.charge`, `install`, `reserve_tenant_quota`; `runtime/capacity_lease.py`: `CapacityLease.write`, `release`, `acquire`, `force_steal` (123+, 192+, 220+; 100+, 180+, 193+, 269+) | Durable budget ledger and fencing-token files are mutated; leases gate dispatch. | No exact runtime authority rows. | Either add linked-domain rows with independent authority/replay contracts or explicitly exclude as external runtime authorities. They must never silently become chain-journal authority. |
| MG-014 | `runtime/process.py`: `ProcessGroup.teardown`, `ProcessCustodyRegistry.register`, `release`, `runtime/batch.py`: `scatter_gather_processes` | Process teardown/registration and child launch/cleanup control. | NBF04/05 physical custody is only mentioned in exclusions; no exact runtime callables. | Add explicit linked physical-custody boundary and require validated identity/no-resignal tests, or name these as NBF04/05-owned exclusions. |
| MG-015 | `cloud/providers/base.py`: `Provider.build`, `deploy`, `ssh_exec`, `upload_file`, `upload_archive`; `local.py`, `on_box.py`, `ssh.py` overrides; `ssh.py`: `resident_recover`, `resident_down`, `resident_reconcile_down`, `apply_zero_recovery_bootstrap_reclaim`, `execute_zero_recovery_canary` | Provider build/deploy/upload and resident/zero-recovery operations produce remote effects. | CC-040 names only `down`/`destroy` and the SSH adapter; CC-043 names CLI actions, not provider symbols. | Expand exact provider effect matrix with intent/claim/result/reconcile links, or explicitly bind these to CC-040/CC-043 as linked adapters. |

## Deliberate exclusions / false positives

These were inspected and are not new NBF08 chain mutation gaps when treated as
the stated domain or evidence boundary:

- `runtime/discovery.py`, `runtime/judge_manifest_discovery.py`,
  `runtime/capabilities.py`, and read portions of `runtime/resume.py` only
  inspect or parse inputs; they are `READ`.
- `cloud/providers/ssh_preflight.py` command builders/parsers and provider
  `inspect`, `observe_*`, `status_payload`, `read_remote_file`, `attach`, and
  `logs` are observation/transport helpers. Their effectful callers remain
  covered by MG-015 or CC-040.
- `runtime/engine_isolation.py` temporary probe writes are bounded test/evidence
  probes, not chain state. They require cleanup but not chain journal entries.
- `runtime/doc_assembly.assemble_doc` writes assembled artifacts; this is a
  plan/document domain artifact and should link to CC-012/CC-028/CC-061 rather
  than create a new authority.
- `runtime/budget_authority.py` and `capacity_lease.py` are not false positives
  as writes; they are deliberate *separate-authority* candidates (MG-013) and
  must be explicitly linked or excluded.
- `runtime/process.py` identity conversion, `pane_pids`, `detect_orphans`, and
  custody receipt serialization are reads/metadata. Only teardown/registration
  and process-batch launch belong to the physical-custody boundary (MG-014).
- `_core/scheduler/topo.py:schedule_batches` and `_core/scheduler/run.py`'s
  `run_scheduler` coordinate supplied callbacks; the durable/job effects are
  in the resident scheduler and Store routes (MG-009). If scheduler callbacks
  are admitted as chain operations, add them to the same route matrix.
- `cli/setup.py` (`handle_setup_global`, `handle_setup_hooks`,
  `handle_setup_hook_check`) installs user/editor hooks and is environment setup,
  not an admitted chain mutation. Keep as an explicit operator-environment
  exclusion; do not infer chain authority from its file writes.

## Acceptance implication

The existing 62-row inventory is a useful domain census, but it cannot claim
complete public-route coverage while MG-001–MG-015 remain only implicit. The
narrowest safe next step is to extend the S6/S7 generator/route matrix with the
confirmed symbols, assigning each either a linked-domain authority and exact
receipt contract or a named READ/external-authority exclusion. No source
changes are proposed by this sweep.
