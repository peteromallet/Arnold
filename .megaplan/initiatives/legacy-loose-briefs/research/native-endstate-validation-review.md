# Native End-State Validation Review

## Inputs

- Original design doc: `/Users/peteromalley/Downloads/agentic-workflow-design-doc.md`
- Current completion epic: `briefs/native-python-pipelines-completion/chain.yaml`
- Composition follow-up: `briefs/native-composition-followup/chain.yaml`
- Platform follow-up: `briefs/native-platform-followup/chain.yaml`

## Review Method

- One Codex read-only architecture review over the full plan.
- Thirty DeepSeek component reviews, one per end-state component, under
  `/tmp/native_endstate_validation/outputs`.

## Overall Verdict

The reviewers broadly converged on **yes-if**: executing the current completion
epic plus both follow-up epics should fulfill the spirit of the design doc if
the platform acceptance criteria are strengthened enough that the later epic
cannot land as mostly interfaces, prototypes, or documented deferrals.

The composition direction is sound: contract first, Megaplan as the first hard
proof, then general nested invocation, derived graph, tree traces, path resume,
validator, and conformance. The main risk is not the composition model. The main
risk is under-specifying the production platform layer.

## Accepted Changes

- Current M7 now distinguishes graph-era compatibility shims from legitimate
  internal projection/interface boundaries.
- Composition north star now names the derived composition graph as a
  first-class artifact.
- M0 now requires a schema formalism and boundary validation for declared
  inputs/outputs, plus authoring examples that do not expose path strings or
  graph/trace internals.
- M1 now requires temporary Megaplan-only paths to use M0 metadata, avoid
  semantic side channels, carry a mechanical marker, and be checked against a
  non-Megaplan example before M2.
- M4 now clarifies pre-execution static graph derivation and path identity
  stability across display-label changes.
- Composition M6 now requires replay-consistency conformance.
- Platform north star now requires a real DB-backed production-capable backend
  path, not only backend-swappable preparation.
- Platform M2 now hardens the credential broker boundary, provider credential
  coverage, durable approval waits, and forensic audit refs.
- Platform M3 now requires transitive pack/version tests, cycle detection, and
  refusal on missing or ambiguous pins.
- Platform M4 now requires real DB-backed durable execution primitives, not only
  storage CRUD or an adapter sketch.
- Platform M5 now requires stuck-run escalation and concurrency gate criteria.
- Platform M6 now strengthens the end-to-end conformance scenario and requires
  a design-doc reconciliation table.

## Judgement Calls

I did not add a new epic or reshuffle the composition chain. The critiques that
survived were acceptance-criteria problems, not a reason to abandon the current
sequence. The one sequencing risk, Megaplan before general nesting, is handled
by tightening M1 so it cannot bypass the M0 contract or leave hidden
Megaplan-only semantics for later.

The only material scope increase is in the platform epic: it now needs a real
DB-backed backend path and real broker/audit coverage for production-covered
credential paths. That is consistent with the original design doc's spirit and
prevents the platform follow-up from becoming a thin abstraction layer.
