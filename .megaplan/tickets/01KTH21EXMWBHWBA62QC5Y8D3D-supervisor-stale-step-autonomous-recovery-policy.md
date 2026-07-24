---
id: 01KTH21EXMWBHWBA62QC5Y8D3D
title: Supervisor stale-step autonomous recovery policy
status: open
source: human
tags:
- supervisor
- recovery
- stale-detection
- autonomy-ladder
- reliability
codebase_id: null
created_at: '2026-06-07T12:48:34.740779+00:00'
last_edited_at: '2026-06-07T12:48:34.740779+00:00'
epics: []
---

Problem
The harness has active-step metadata, heartbeat/liveness signals, an autonomy ladder, and some blocked-execute recovery, but common stalls still require manual lock/state/PID diagnosis. Dead workers, stale heartbeats, repeated schema failures, and healthy long-running phases are not handled by a deterministic in-driver recovery policy.

Acceptance criteria
- Classify active phases into healthy wait, stale heartbeat retry, dead PID unlock/resume, repeated schema failure, and terminal exhaustion.
- Stale heartbeat recovery: after bounded consecutive stale windows, kill and resume from the last safe cursor, with a strict per-phase retry cap.
- Dead PID recovery: if PID is gone but `active_step` remains, clear the active lock/state safely and resume from the last completed phase, with a strict per-plan cap.
- Repeated identical schema/contract failures bypass model tier bumps and file a diagnostic terminal ticket.
- State lock files carry structured lease content: PID, timestamp, TTL, plan name, and phase.
- Golden/characterization tests cover stale heartbeat, dead PID, repeated schema failure, and terminal ticket trace.

Suggested touchpoints
- `arnold/pipelines/megaplan/auto.py`
- `arnold/pipelines/megaplan/supervisor/ladder.py`
- `arnold/pipelines/megaplan/supervisor/chain_runner.py`
- `arnold/pipelines/megaplan/control_interface.py`
- `arnold/runtime/resume.py`
- `tests/test_supervisor_ladder.py`

