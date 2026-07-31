---
id: 01KYMTN1TTYKRMBXA9759G0JX0
title: Execute feasibility revalidation must preserve configured timeout
status: open
source: human
tags:
- bug
- execute
- timeout
- configuration
- feasibility
- regression
- post-m11
- blocked-by-m11
- execution-transaction-integrity
- immediate-residual
codebase_id: null
created_at: '2026-07-28T16:59:13.115088+00:00'
last_edited_at: '2026-07-31T03:17:11+00:00'
epics:
- epic_id: megaplan-native-parity-corrective
  resolves_on_complete: false
  kind: associated
  provenance: post-m11-ticket-reconciliation-20260731
  linked_at: '2026-07-31T03:17:11+00:00'
---

Execute-time batch feasibility called assert_admitted_task_feasibility without the plan state config. It discarded the explicit six-hour phase timeout, fell back to 60 minutes, and rejected the same graph finalize had admitted. The effective execution contract changed between finalize and batch dispatch.\n\nSequencing: execute only from a follow-up epic after custody-control-plane M11 plan m11-cross-contract-acceptance-20260728-1035 has completed. Do not execute or fold this ticket into the current epic.\n\nRegression acceptance:\n- Preserve an explicit timeout through serialization, finalize, batch construction, revalidation, and dispatch.\n- Apply the 60-minute default only when no timeout is configured.\n- Test persisted and reloaded plans, unit conversion, and multi-batch execution.\n- Make revalidation side-effect-free and require the admitted graph hash to use the same config.\n- Status and trace report the effective timeout used for each validation and batch.

## 2026-07-31 reconciliation

The original call-site defect is fixed in the consolidated M10/M11 lineage:
both execute entry and batch admission pass `state.config`, and
`test_guard_threads_config_phase_timeout_into_admission` protects the configured
timeout. Keep this ticket open as an immediate residual because persisted
reload, multi-batch/unit-conversion, admitted-graph-hash, and status/trace
acceptance are not yet proved. Native Parity is associated because its finalize
and execute cutovers must preserve the fixture, but its completion must not
auto-address this pre-launch residual.
