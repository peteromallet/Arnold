# M0 - Composition Contract And Examples

## Objective

Define the native composition contract before any broad migration hardens the
wrong shape. This milestone produces the stable conceptual and technical seam:
steps and workflows remain distinct internally, but both are invocable units
with stable identity, declared inputs/outputs, path identity, and validator
rules. It also writes aspirational examples in the target syntax before the
runtime implementation is generalized.

## Prerequisite

Do not start this milestone until `briefs/native-python-pipelines-completion/chain.yaml`
has completed through M7 and the native-first completion branch is clean.

## Files To Change And Instructions

- `docs/arnold/native-composition-contract.md`
  Create the contract document. Define:
  - `@step` / `@workflow` terminology and compatibility aliases for existing
    `@phase` / `@pipeline` names.
  - Explicit stable unit IDs decoupled from Python function names.
  - Declared inputs and outputs for both steps and workflows, including the
    schema formalism used at the invocation boundary and how incompatible
    schema changes are classified.
  - Parent-to-child input mapping and child-to-parent output merge semantics.
  - Call-site path segment rules, including repeated child workflow use.
  - Legacy stage-name alias rules for migrated Megaplan stages. Stable IDs are
    authoritative, but existing public stage names such as `prep`, `plan`,
    `critique`, `gate`, `revise`, `tiebreaker`, `finalize`, `execute`, and
    `review` must remain accepted aliases where users, profiles, overrides,
    status payloads, or legacy cursors currently refer to them.
  - Loop iteration path rules for `while` and supported `for` loops.
  - The static derived graph shape used by tooling.
  - The tree trace schema and per-attempt audit skeleton fields.
  - Routing validator rules: what is allowed in workflow routing and what must
    move into a step.
  - Repeatable-not-deterministic semantics: replay by default; any future
    re-decide behavior must be explicit and excluded from structural golden
    equality.
- `docs/arnold/workflow-authoring-examples.md`
  Write 3-4 aspirational examples before implementation:
  - a single workflow with steps and decisions;
  - a workflow that invokes a child workflow;
  - a workflow that reuses the same child workflow at two call sites;
  - a review/revise loop over recorded state with path-resume comments. The
    examples should show plain decorated Python only: no manual path strings,
    graph node construction, trace schema objects, or validator directives in
    author-written code.
- `arnold/pipeline/native/decorators.py`
  Add or plan the decorator metadata needed by the contract: stable `id`,
  declared `inputs`, declared `outputs`, and public aliases if the project
  chooses `@step` / `@workflow` naming.
- `arnold/pipeline/native/ir.py`
  Add or plan a first-class invocable metadata shape that both native phases and
  native workflows can satisfy. Do not rely only on `subprogram` as an opaque
  implementation detail.
- `tests/arnold/pipeline/native/`
  Add contract-level tests or pending conformance fixtures for the examples.

## Verifiable Completion Criterion

- The composition contract names the invocable interface and makes stable IDs,
  declared inputs/outputs, schema validation, path rules, loop iteration rules,
  and validator rules explicit.
- The contract defines how legacy stage names map to stable IDs during
  migration, including which aliases are public compatibility promises and
  which are internal-only.
- The aspirational examples compile as documentation fixtures or are marked as
  expected-failing fixtures tied to later milestones.
- Each aspirational example reads as plain Python authoring: decorators,
  ordinary control flow, and function calls. Path resume is demonstrated as a
  tooling concern, not by requiring authors to construct path strings manually.
- The follow-up milestones can cite this contract instead of inventing local
  semantics.
- Canonical Megaplan M1 is blocked on this contract and may not introduce
  Megaplan-only semantics that conflict with it.

## Risks And Blockers

- Over-designing the full pack/versioning product here would slow the core
  composition work. This milestone defines metadata foundations, not the pack
  marketplace or re-pin flow.
- The existing `@phase` / `@pipeline` names may remain as compatibility aliases,
  but the contract must present the user-facing two-kind model clearly.

## Dependencies

- First milestone of the native composition follow-up epic.
