# S6 - Override, Auto, Compatibility Collapse

## Objective

Extract routing override actions into native source, remove auto-drive as a
second route brain, and collapse/quarantine remaining component, handler,
manifest, and compatibility paths that formerly owned report-level semantics.

## Legacy 10-Sprint Source Mapping

- Absorbs `m8-override-control-surface.md`.
- Absorbs `m9-component-collapse-compat-quarantine.md`.
- Includes the "delete as you extract" refinement from the oracle synthesis:
  any carrier replaced in earlier sprints must already be deleted or fenced;
  this sprint finishes what remains and proves the global fence.

## Work Required

- Make routing overrides source-visible:
  abort, force proceed, replan, resume/recover paths, terminal halt behavior.
- Leave config/effect-only overrides as audited effects only when they cannot
  route: set model/profile/vendor/robustness, add note, non-routing state
  annotations.
- Declare authority requirements at routing control gates.
- Emit authority records for routing overrides, suspensions, resumes,
  recoveries, waivers, and force-proceed/abort decisions, with checked evidence
  refs and stale-input rejection.
- Remove or fence `LEGACY_ALIASES` into handler-private routing functions.
- Remove report-owned route bindings, topology contracts, fanout/reducer
  contracts, handler refs, and override dispatch metadata from `components.py`,
  or mark them compatibility-only with tests proving no influence over corrected
  flow.
- Delete decision translators in `manifest_backend.py`, `route_dispatch.py`,
  `auto.py`, and CLI dispatch, or quarantine as explicit legacy paths.
- Ensure auto-drive may emit operational events only; it must consume canonical
  workflow events and must not derive product routes from state.
- Ensure semantic-health/status/repair consumers can observe override authority
  records without becoming route authorities.
- Prove compatibility shells and projected native programs consume canonical
  source-derived semantics or cannot satisfy traceability rows.

## Verifiable Completion Criterion

- Scenarios pass:
  - force-proceed from blocked reaches finalization/done;
  - abort mid-loop reaches terminal aborted;
  - recover/resume routes do not depend on handler-private dispatch.
- Deleting/quarantining semantic metadata from `components.py` does not change
  deterministic corrected product-routing traces.
- Adapters that translate decisions are gone or legacy-fenced. Adapters that
  translate data may remain.
- No implemented row cites components, handler refs, route bindings, manifest
  backend routing, auto next-step derivation, CLI handlers, or projected-native
  shells as proof.
- Override/auto compatibility tests fail when an authority-increasing
  transition lacks a durable authority record or when an authority record points
  at stale/mismatched evidence.

## Do Not Close If

- Auto-drive still derives the next product step from state.
- A compatibility bridge can satisfy semantic evidence without going through
  canonical source.
- Repair/status/semantic-health code can force a route that is not present in
  `.pypeline` or declared native policy.
