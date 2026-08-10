---
id: 01KZEN0EM5T44BTWKDT3KMMTYT
title: 'chain: committed content changes should reconcile state binding instead of
  hard-failing'
status: open
source: human
tags:
- arnold
- engine
- durable-fix
- codex-plan
codebase_id: null
created_at: '2026-08-07T17:40:50.437580+00:00'
last_edited_at: '2026-08-07T17:40:50.437580+00:00'
epics: []
---

DURABLE ROOT FIX (Codex decision-maker A3). Modifying chain.yaml/NORTHSTAR after binding invalidates the execution binding (chain_spec_not_at_intended_revision); assert_execution_binding raises DRIFT_ERROR on any load/drive. Extend _future_source_reconciliation_is_safe() (chain/execution_binding.py:719-774, 978-1002, 1097-1360; chain/__init__.py:6558-6565, 5687-5707) to auto-reconcile content-only drift when milestone_sequence/prefix/cursor match and the changed source is committed; add reconcile_execution_binding_if_safe() before assert_execution_binding(). Retain manual rebind for sequence changes.
