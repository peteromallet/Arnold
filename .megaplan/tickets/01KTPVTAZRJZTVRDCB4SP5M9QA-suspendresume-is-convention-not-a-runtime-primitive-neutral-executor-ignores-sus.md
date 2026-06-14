---
id: 01KTPVTAZRJZTVRDCB4SP5M9QA
title: Suspend/resume is convention, not a runtime primitive — neutral executor ignores
  Suspension/SUSPENDED
status: open
source: human
tags:
- arnold
- pipeline
- suspend-resume
- state-lifecycle
- medium-severity
codebase_id: null
created_at: '2026-06-09T18:55:16.472996+00:00'
last_edited_at: '2026-06-09T18:56:37.689914+00:00'
epics:
- epic_id: aggressive-generalized-pipeline-migration
  resolves_on_complete: false
  linked_at: '2026-06-09T18:56:37.689904+00:00'
---

SEVERITY: MEDIUM — expected to be closed by m8-state-lifecycle-runtime, but today it mis-presents as first-class.

FINDING (independent architecture review, 2026-06-09): suspend/resume looks like a first-class primitive but is actually convention — write a checkpoint artifact and accidentally halt; resume by running a fresh pipeline with a different entry. The neutral executor has no SUSPENDED handling.

EVIDENCE (/private/tmp/arnold-target):
- arnold/pipelines/evidence_pack/steps.py:551-564 — HumanReviewStep builds a rich typed Suspension envelope (deadline, on_timeout, resume_input_schema) and returns next="suspended".
- The initial pipeline's review stage has only a "completed" edge, so "suspended" matches NO edge and falls through the SAME lenient break as the silent-routing gap (see ticket 01KTPVSH8X04XE0D122M0V0712).
- The neutral executor has no ContractStatus.SUSPENDED terminal exit; the Suspension dataclass is persisted to disk and then IGNORED by the runtime.
- tests/.../test_end_to_end.py asserts suspension via PERSISTED ARTIFACTS precisely because the executor discards the StepResult.

WHY IT MATTERS: on_timeout / deadline / resume_input_schema are inert — nothing in the runtime honors them. Human-gate (and any long-suspend) apps depend on artifact side-effects plus an accidental halt, and "resume" re-runs a fresh pipeline rather than rehydrating suspended state. The advertised suspend/resume capability is not actually wired.

PROPOSED (squarely m8-state-lifecycle-runtime):
- Make SUSPENDED a first-class executor terminal exit, DISTINCT from halt (and from the unresolvable-label halt in ticket 01KTPVSH8X04XE0D122M0V0712).
- Persist + HONOR the Suspension envelope: enforce deadline/on_timeout, validate resume payloads against resume_input_schema.
- Provide a real resume entrypoint that rehydrates suspended pipeline state instead of constructing a fresh pipeline with a different entry.

CROSS-REF: m8-state-lifecycle-runtime (epic-2 / aggressive-generalized-pipeline-migration) and .megaplan/briefs/evidence-first-pipeline-semantics. Interacts with ticket 01KTPVSH8X04XE0D122M0V0712 — fixing the silent-halt routing must not break (and should formalize) the suspend exit.
