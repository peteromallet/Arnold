---
id: 01KZEN0FV6XGAD6RWS33ZJ6KHT
title: 'runtime: converge RT1 as the single executable source (kill split-brain)'
status: open
source: human
tags:
- arnold
- engine
- durable-fix
- codex-plan
codebase_id: null
created_at: '2026-08-07T17:40:51.686255+00:00'
last_edited_at: '2026-08-07T17:40:51.686255+00:00'
epics: []
---

DURABLE ROOT FIX (Codex decision-maker A4). Three trees run different code: RT1 (fixed), RT2 (resident PYTHONPATH, unfixed, read-only), /workspace/arnold (cwd-shadow, unfixed). Replace stale RT2 runtime/supervisor references with an RT1-built environment; add a startup import assertion (resolve arnold_pipelines.megaplan.__file__ root vs MEGAPLAN_RUNTIME_SRC, abort on mismatch). Push RT1 first (needs GitHub auth), then replace/retire /workspace/arnold after non--P launchers are moved. Restart resident/watchdog after the assertion deploys.
