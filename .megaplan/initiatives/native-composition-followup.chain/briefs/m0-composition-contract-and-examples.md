# M0 - Composition Contract And Examples

## Objective

Define the native composition contract before any broad migration hardens the
wrong shape. This milestone produces the stable conceptual and technical seam:
steps and workflows remain distinct internally, but both are invocable units
with stable identity, declared inputs/outputs, path identity, and validator
rules. It also writes aspirational examples in the target syntax before the
runtime implementation is generalized.

## Prerequisite

Do not start this milestone until
`.megaplan/initiatives/native-python-pipelines-completion/chain.yaml` has
completed through M7 and the native-first completion branch is clean.

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
  - First-class native constructs required before report-owned Megaplan rows
    can be marked implemented: runtime-list `parallel_map` or equivalent typed
    dynamic map, typed loop outcomes or an accepted `break`/`continue`
    substitute, declared policy-call metadata at call sites, nested workflow
    invocation, and explicit rejection rules for Megaplan-only escape hatches.
- `docs/arnold/python-shaped-authoring-contract.md`
  Add the V2 authoring-contract scope for compositional source. Define syntax
  examples and accepted/rejected fixtures for nested workflow invocation,
  runtime-list `parallel_map`, typed loop outcomes or accepted loop exits,
  declared policy-call metadata, stable path identity, and wrapper rejection.
  V2 must make clear that Megaplan conformance cannot depend on direct manifest
  authoring, `Pipeline.native_program` shell projection, or Megaplan-only
  compiler/runtime helpers.
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
- The contract states that Megaplan fanout, execute DAG, review checks, policy
  calls, and loop exits cannot be marked report-conformant until the general
  native constructs above exist or the row is explicitly deferred.
- The Python-shaped authoring contract has a V2 section or follow-up contract
  entry that owns the accepted source syntax, diagnostics, and rejection
  fixtures for composition features needed by Megaplan.

## Native Representation Alignment

- Matrix rows owned or affected: Runtime-list iteration; Dynamic parallel map; Typed loop outcomes or break/continue; Path-addressed checkpoints; Trace-only native shadow topology; Bounded critique/gate/revise loop.
- Expected status change: `enabled` by defining the authoring language and shadow-topology contract M1 must satisfy.
- Proof artifacts: native composition contract, aspirational examples, expected-failing or compiling fixtures, stable ID/path rules, accepted/rejected syntax fixtures, and explicit fixtures for runtime-list fanout, typed loop exits, policy calls, nested invocation, and Megaplan-only helper rejection.
- False-pass guard: examples that require manual graph nodes, path strings, validator directives, or Megaplan-only helpers do not satisfy the report.
- Doctrine gate: M0 must explicitly define the source/manifest/native_program
  relationship. Author-written compositional Python source owns Megaplan
  semantics; `WorkflowManifest` is compiled runtime/replay/inspection output;
  `Pipeline.native_program` is dispatch compatibility substrate. Examples must
  not hand-author manifests or treat flat manifest graphs as source truth.
- Deferrals: actual Megaplan migration and conformance proofs remain owned by M1-M6; DB-backed durability remains owned by platform M4.
- Canonical source paths/imports: M0 must name the canonical source/import surface that M1 will migrate and the legacy stage-name aliases it must preserve.

## Risks And Blockers

- Over-designing the full pack/versioning product here would slow the core
  composition work. This milestone defines metadata foundations, not the pack
  marketplace or re-pin flow.
- The existing `@phase` / `@pipeline` names may remain as compatibility aliases,
  but the contract must present the user-facing two-kind model clearly.

## Dependencies

- First milestone of the native composition follow-up epic.
