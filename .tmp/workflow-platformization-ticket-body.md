## Problem

The Native Parity corrective epic is designed to make Megaplan one readable,
source-authoritative Python workflow. It deliberately does not prove the next
platform-level outcome: that useful steps and subworkflows are packaged,
documented, versioned, and reusable by unrelated workflows without importing or
copying Megaplan.

This should be a separate follow-on epic, not concurrent implementation inside
Native Parity. Native Parity must design for extraction now, but reusable product
patterns should be stabilized only after one correct implementation and a second
real consumer exist.

## North Star

An unrelated workflow package can import reusable steps and subworkflows, bind
its own typed domain objects, policies, capabilities, storage, and effects,
compose them in native `.pypeline` Python, and execute them from a clean installed
package—without importing Megaplan or copying its implementation.

The intended layering is:

```text
Arnold workflow platform
  authoring, lowering, execution, identity, suspension, effects

Reusable workflow patterns
  evaluator panels, bounded refinement, human gates,
  dependency-ready execution, review/rework, effect-safe actions,
  terminal/control arbitration

Product workflows
  Megaplan, a non-Megaplan reference consumer, future workflows
```

The shared layer owns orchestration mechanics. Product packages own domain
meaning, domain outcomes, artifacts, policies, and effect implementations.

## Dependency and handoff

Do not launch until `megaplan-native-parity-corrective` completes with its
content-addressed completion manifest and golden trace proof. Native Parity
should hand off:

- a reusable-candidate inventory and dependency map;
- stable typed ports/outcomes/policy/effect contracts;
- source-to-runtime golden trace adapters;
- proof that generic primitives do not import Megaplan;
- explicit classification of core primitive, stable reusable pattern,
  experimental pattern, or Megaplan-specific behavior.

## Candidate reusable patterns

- Dynamic evaluator panel with runtime children, retry, sequential fallback,
  reducer, and stable item identity.
- Bounded evaluate/decide/revise loop with caps, no-progress detection,
  escalation, and typed exits.
- Typed human decision gate with capability, suspension, durable reentry, and
  drift handling.
- Dependency-ready executor with worker cap, exact child identity, partial
  restart, and aggregation.
- Review/rework/refinalization cycle.
- Effect-safe action with intent/outcome, idempotency, ambiguity, and
  reconciliation.
- Closed terminal arbitration for cancel, publish, deliver, and completion.

Not every Megaplan phase should be generalized. Product-specific planning,
critique, gate, finalization, and task semantics remain in Megaplan unless a
second consumer proves the shared abstraction.

## Proposed epic

### S1 — Platform contract and extraction inventory

- Consume the Native Parity completion manifest.
- Classify all steps/subworkflows and freeze dependency direction.
- Define the reusable step/subworkflow manifest: typed ports/outcomes,
  capabilities, effects/compensations, suspension/reentry, identity, policy,
  boundary version, and extension points.
- Add reverse-import and hidden-global-state checks.

### S2 — Shared package and composition surface

- Establish the reusable-pattern package and stable exports/discovery.
- Support typed policies/effects/capabilities and native `.pypeline`
  composition.
- Generate mechanical Run Authority/Custody/WBC bindings from semantic
  declarations; authors must not handwrite platform IDs.
- Prove a neutral workflow runs from a clean wheel.

### S3 — Extract proven patterns

- Extract the evaluator panel, bounded refinement loop, human gate, and
  effect-safe action first.
- Parameterize domain types and policies without Megaplan defaults.
- Make Megaplan consume the shared implementations with unchanged normalized
  golden traces.

### S4 — Second real consumer

- Build a deliberately non-Megaplan workflow using multiple shared patterns.
- Use different domain types, outcome vocabulary, artifacts, policies, effects,
  and storage layout.
- Prove it imports no Megaplan code and copies no pattern implementation.

### S5 — Stabilization and adoption

- Finalize public exports, versioning, documentation, examples, compatibility,
  deprecation, authoring-readability, and edit-locality rules.
- Produce the reusable-pattern registry and platform completion manifest.

## Blocking completion proof

- Shared packages have zero imports from Megaplan.
- Megaplan and the reference workflow consume the same pattern implementations.
- No copied implementation exists in either consumer.
- Both consumers execute from clean wheels.
- Consumer policies/types/effects can vary without modifying shared internals.
- A consumer-specific outcome does not require shared-package changes unless it
  changes the generic protocol.
- Identity, Run Authority, Custody, WBC, checkpoints, and golden traces remain
  correct under different consumer namespaces.
- Metadata, handlers, adapters, projections, and CLI/auto surfaces cannot own
  shared route semantics.
- Adding a new consumer is possible using only documented public surfaces.

The decisive acceptance test is a second non-Megaplan workflow that imports the
shared patterns, supplies different domain semantics, and runs successfully
without knowing Megaplan internals.

## Non-goals

- Generalizing every Megaplan function.
- Rebuilding Run Authority, Custody, WBC, recovery, or projections.
- Building a workflow marketplace.
- Freezing internal compiler APIs prematurely.
- Inventing abstractions without two concrete consumers.
- Forcing unrelated domains into Megaplan-shaped outcomes.

## References

- `.megaplan/initiatives/megaplan-native-parity-corrective/`
- `.megaplan/initiatives/megaplan-native-parity-corrective/GOLDEN_TRACE_CONTRACT.md`
- `docs/arnold/megaplan-native-parity-corrective-plan.md`
- `docs/arnold/megaplan-native-representation-report.md`
