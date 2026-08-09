---
id: 01KZEN0DCPZBBAC7VA3ZKT2ZC7
title: 'watchdog: done-plan auto-advance its chain even when liveness is unknown'
status: open
source: human
tags:
- arnold
- engine
- durable-fix
- codex-plan
codebase_id: null
created_at: '2026-08-07T17:40:49.174486+00:00'
last_edited_at: '2026-08-07T17:40:49.174486+00:00'
epics: []
---

DURABLE ROOT FIX (Codex decision-maker A1, highest leverage). A done plan leaves its chain parked at milestone 0 when the session is liveness-fenced. Add terminal_stale_chain_relaunch_bypass_eligible() to arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog (regions 7935-8043, 8225-8242, 8533, 8557, 8745-8753, 9039, 9115-9148): when liveness unknown, current_target_marks_terminal_stale_chain true, plan terminal, no live lease/bound PID, health not alive -> append --one --no-git-refresh --no-push to resolve_relaunch_command(). Regression: fixture done plan + parked chain + UNKNOWN liveness; assert relaunch; assert no relaunch for nonterminal/live-lease/live-PID. Observed: r7 chain parked with plan done.
