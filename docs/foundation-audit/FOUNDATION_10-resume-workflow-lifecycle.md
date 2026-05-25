First read `FOUNDATION_PREAMBLE.md` (shared context + output rules). Obey it.

## YOUR SUBSYSTEM: resume, lifecycle & fault state — `_core/workflow.py`, `resume.py`, `plan_repository.py`, FaultRegistry

The refactor must keep plans RESUMABLE across the cutover and reconcile THREE external `current_state`
writers. Resume + lifecycle is foundational: if a plan can't reliably resume, the unified path is
unshippable. The brief's hazards 3/5/9 touch this; go deeper into whether the resume/lifecycle model
is internally coherent BEFORE adding a migration shim on top.

Investigate (cite path:line):
- The three external state writers: `chain.py:_mark_blocked_execute_as_executed` (~1517),
  `_core/workflow.py:resume_plan` (~352), `store/plan_repository.py:record_lifecycle_failure` (~392,
  called from `auto.py:563`). Do they agree on the state machine, or each have their own notion of
  valid transitions? Is there ANY single definition of the plan lifecycle state machine?
- Resume read paths: pipeline reads `_pipeline_paused_stage` (`run_cli.py:261`), legacy
  `handle_resume` reads `current_state`/`next_step`/`resume_cursor`; human-gate pauses converge on
  `awaiting_user.json::stage`. Map ALL pause/resume entry points. Are there pause types neither
  path handles? What about resume after a crash mid-write (ties to state atomicity)?
- `FaultRegistry` (`_pipeline/faults.py`): the brief calls it "most reusable structure" — verify.
  Is it actually clean, or does it have planning-specific leakage (`addressed_then_reopened_count`)?
- `plan_repository.py` / `store/`: what IS the plan store? A directory convention, a DB, JSON files?
  Is lifecycle state authoritative there or in `state.json`? Two sources of truth?

Key question: is there a single coherent plan lifecycle state machine anywhere, or is "valid plan
state + valid transitions" an emergent property scattered across 3+ writers and 2+ resume readers
with no central definition? If the latter, defining that state machine is a fix-first foundation the
brief treats as a migration-shim afterthought. Find the transition disagreements between the writers.
