---
id: 01KTH21EC489596QWBC3419JC9
title: Add compact megaplan monitor command for plan and chain health
status: open
source: human
tags:
- cli
- observability
- operator-experience
- chain
- reliability
codebase_id: null
created_at: '2026-06-07T12:48:34.180619+00:00'
last_edited_at: '2026-06-07T12:48:34.180619+00:00'
epics: []
---

Problem
Long-running phases expose useful health signals in status JSON, events, active-step metadata, and doctor checks, but operators must read a large nested blob to tell healthy progress from a stall. There is no concise plan/chain dashboard; `watch` is effectively status again.

Acceptance criteria
- Add `arnold megaplan monitor` or equivalent with one compact line per plan: health, plan, state, active phase, age, idle time, last activity kind, cost, and lock status.
- Support `--plan`, `--chain SPEC`, `--follow`, `--interval`, and `--json`/JSONL output.
- Reuse existing signals from status view, phase observability, event journal, and lock checks rather than inventing new health logic.
- Include tests for healthy, slow, stale, dead PID, and idle-stale rendering.
- Chain mode resolves milestone plan names and shows each milestone's plan health where available.

Suggested touchpoints
- `arnold/pipelines/megaplan/cli/parser.py`
- `arnold/pipelines/megaplan/cli/monitor.py`
- `arnold/pipelines/megaplan/cli/__init__.py`
- `arnold/pipelines/megaplan/cli/status_view.py`
- `arnold/pipelines/megaplan/chain/__init__.py`
- `tests/test_monitor.py`

