---
id: 01KTH21FH1DM7X5VC3R8SPJJHT
title: Formalize engine-target isolation and mutation protection
status: open
source: human
tags:
- engine-isolation
- safety
- sandbox
- m0
- reliability
codebase_id: null
created_at: '2026-06-07T12:48:35.361376+00:00'
last_edited_at: '2026-06-07T12:48:35.361376+00:00'
epics: []
---

Problem
The driver engine and target workspace are not formalized as separate protected roots. Worker subprocesses can inherit engine-oriented cwd/package resolution, and the sandbox protects target boundaries but does not treat the engine as immutable. Current M0 is addressing this, but the reliability ticket should preserve the broader invariant and regression requirements.

Acceptance criteria
- Persist an execution environment contract with engine root, project/target root, engine commit/pin, and waiver id when applicable.
- Detect engine/target path overlap before mutating phases and refuse without a durable local-dev waiver.
- Mutating subprocesses run from the resolved target work dir, not ambient `Path.cwd()` or engine root.
- The engine root is a protected root for sandbox/write validation and is excluded from auto-writable roots.
- Detect engine mutation before/after worker invocation and fail loudly with changed paths.
- Tests cover separated roots, overlap refusal, waiver allowance, engine mutation detection, sandbox protected-root behavior, and chain subprocess cwd.

Suggested touchpoints
- `arnold/pipelines/megaplan/runtime/process.py`
- `arnold/pipelines/megaplan/runtime/sandbox.py`
- `arnold/pipelines/megaplan/workers/_impl.py`
- `arnold/pipelines/megaplan/workers/shannon.py`
- `arnold/pipelines/megaplan/handlers/execute.py`
- `arnold/pipelines/megaplan/handlers/review.py`
- `arnold/pipelines/megaplan/chain/__init__.py`
- `tests/test_engine_isolation.py`

