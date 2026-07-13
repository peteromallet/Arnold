# Source Context

> Historical source note. Its incident evidence remains useful, but milestone
> numbering and sequencing are superseded by the 2026-07-10 corrective reshape
> decision and C1-C6 chain.

This epic merges conclusions from the July 2026 cloud prep-state incident and
the existing boundary/transition plans.

## Incident Lesson

The real failure was not that prep artifacts were absent. Prep artifacts existed,
but durable lifecycle evidence did not advance:

- `state.json.current_state` stayed `initialized`;
- `history` lacked prep success;
- `phase_result.json` was missing/stale;
- status/watchdog over-weighted live activity.

Immediate repair infrastructure already exists through the repair queue and
systemd path trigger. The missing piece was a producer of semantic repair
requests for success-contract violations.

## Cloud Custody Drift Lesson

The `progress-auditor-stage-metrics` incident showed a related cloud-process
boundary class:

- plan state retained an `active_step` from a dead worker PID;
- tmux/session custody was missing;
- watchdog could treat the run as mechanically restartable;
- repair could restore execution as a background process rather than the
  expected managed session;
- status could still infer running from process evidence even though custody was
  weaker than intended.

This should be modeled as a cloud custody boundary contract in M9, not as an M1
prep semantic-health concern. M8 should only ensure repair/status/auditor can
consume and render custody findings once M9 produces them.

## Existing Plans To Align

- Structured output template boundaries:
  `.megaplan/initiatives/legacy-loose-briefs/notes/structured-output-template-boundaries.md`
- BoundaryTurn end-to-end:
  `.megaplan/initiatives/boundary-turn-end-to-end`
- Transition validator routing:
  `.megaplan/initiatives/evidence-first-pipeline-semantics/briefs/m7-transition-validator-routing.md`

## Sense-Check Adjustments

The plan was narrowed after review:

- Start with prep, not a giant semantic-health engine.
- Store structured findings; do not rely on `root_cause_hint` because it is
  hashed.
- Keep chain-plan drift separate until its repair domain is explicit.
- Use observe/dispatch flags separately.
- Prefer parent/controller-side post-boundary verification before broad
  producer hooks.
- Treat race/read-stability and active work suppression as first-order design
  constraints.
