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
codebase_id: null
created_at: '2026-07-28T16:59:13.115088+00:00'
last_edited_at: '2026-07-30T12:58:46.713902+00:00'
epics: []
---

Execute-time batch feasibility called assert_admitted_task_feasibility without the plan state config. It discarded the explicit six-hour phase timeout, fell back to 60 minutes, and rejected the same graph finalize had admitted. The effective execution contract changed between finalize and batch dispatch.\n\nSequencing: execute only from a follow-up epic after custody-control-plane M11 plan m11-cross-contract-acceptance-20260728-1035 has completed. Do not execute or fold this ticket into the current epic.\n\nRegression acceptance:\n- Preserve an explicit timeout through serialization, finalize, batch construction, revalidation, and dispatch.\n- Apply the 60-minute default only when no timeout is configured.\n- Test persisted and reloaded plans, unit conversion, and multi-batch execution.\n- Make revalidation side-effect-free and require the admitted graph hash to use the same config.\n- Status and trace report the effective timeout used for each validation and batch.
