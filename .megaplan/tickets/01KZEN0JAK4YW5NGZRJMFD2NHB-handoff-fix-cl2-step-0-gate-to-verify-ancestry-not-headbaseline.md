---
id: 01KZEN0JAK4YW5NGZRJMFD2NHB
title: 'handoff: fix CL2 step_0 gate to verify ancestry, not HEAD==baseline'
status: open
source: human
tags:
- arnold
- engine
- durable-fix
- codex-plan
codebase_id: null
created_at: '2026-08-07T17:40:54.227962+00:00'
last_edited_at: '2026-08-07T17:40:54.227962+00:00'
epics: []
---

DURABLE ROOT FIX (Codex decision-maker A6). docs/critique-ledger/handoffs/cl2-ledger-replay.json enforcement_points.step_0 requires HEAD==baseline + clean worktree, which can never hold once any commit lands; step_15 correctly requires only ancestry. This blocked T0 (baseline gate) and cascaded accepted_attempt_dependency_unresolved to all 16 downstream tasks. Replace step_0 with git merge-base --is-ancestor <baseline> HEAD + clean-worktree-at-verification-time, mirroring step_15.
