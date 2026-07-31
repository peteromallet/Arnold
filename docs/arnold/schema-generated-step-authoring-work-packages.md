# Proposal: Schema-Generated Step Authoring Work Packages

## Recommendation

Add a standard authoring protocol for every durable model-driven workflow step:
the runtime materializes an attempt-local typed work package, the agent edits one
designated response document, and the harness compiles that document into the
canonical step result. The agent's final chat response is never authoritative.

Implement the first product-local vertical slice in Native Parity S3A for
Megaplan's `prep -> plan -> critique` front half. Extend it through the later
Native Parity phase migrations, then make the mechanism reusable in
Platformization S2B and pleasant to use in Platformization S3.

This is an authoring protocol, not a replacement for Step-IO, CompletionSpec,
Workflow Boundary Contracts, Custody, or the attempt ledger. It connects those
systems through one generated, typed boundary.

## Problem

The current model path has two outputs:

1. the agent may write a useful artifact such as `plan.md`; and
2. it must separately reconstruct a machine response envelope at the end of a
   long tool-using call.

Prompts and JSON schemas describe that envelope, but some providers do not make
the schema mechanically unavoidable. A model can therefore write the substantive
plan correctly and omit machine fields from its final response. Post-response
structural audit catches the omission, but only after spending the full call.

The deeper problem is ownership. Model-authored semantic content, optional model
hints, harness-derived facts, and admission-bound identity currently meet in one
response shape without one standard compilation protocol.

## Target model

Every durable model-driven step declares one `StepAuthoringSpec` alongside its
typed input, canonical output, prompt asset, and completion specification.

Fields have explicit ownership:

- `model_required`: semantic content the agent must supply;
- `model_hint`: optional advice that cannot narrow a deterministic floor;
- `derived`: computed by the harness from source, receipts, or admitted inputs;
- `protected`: immutable identity, authority, schema, evidence-window, and
  provenance fields;
- `body`: the primary human-readable Markdown content, when applicable.

Pure helpers have no authoring package. Deterministic durable steps execute
without a model response form. Human gates use the same compilation pattern but
with separately authorized human ownership.

An illustrative declaration:

```python
class PlanResponse(AuthoringDocument):
    questions: list[str] = model_required(default_factory=list)
    assumptions: list[str] = model_required(default_factory=list)
    success_criteria: list[SuccessCriterion] = model_required()
    changed_surfaces: list[str] = model_hint(default_factory=list)
    test_selection: TestSelectionHint = model_hint(
        default_factory=TestSelectionHint.neutral,
    )
    runtime_binding: RuntimeIdentity = protected()
    test_blast_radius: TestBlastRadius = derived(derive_test_blast_radius)
    body: MarkdownBody = model_required()


plan_step = agent_step(
    id="megaplan.plan",
    input=PlanInput,
    response=PlanResponse,
    view=typed_markdown(frontmatter="typed_fields", body="body"),
    prompt="prompts/plan.md",
    completion=PlanCompletionSpec,
)
```

The exact API should use the adopted Arnold authoring vocabulary rather than
introducing a parallel decorator or schema framework. The example shows the
required semantics, not a frozen public API.

## Attempt-local work package

Before agent dispatch, the runtime creates:

```text
attempts/plan/attempt-12/
├── instructions.md          # generated protocol, read-only
├── context/
│   ├── manifest.json        # hashes and admitted references
│   ├── brief.md             # immutable input projection
│   ├── prep.md
│   └── prior-response.md
├── response.md              # only agent-editable result
├── snapshots/               # immutable submitted drafts
├── compiled.json            # harness-generated canonical candidate
├── validation.json          # stable diagnostics
└── verdict.json             # completion/custody result
```

`response.md` combines typed frontmatter and the human-readable body:

```markdown
---
schema: megaplan.plan-response.v2
step_identity: megaplan.plan
attempt: 12

questions: []
assumptions: []
success_criteria: []
changed_surfaces: []
test_selection:
  strategy: unspecified
  selectors: []

# Protected: edits reject
runtime_binding: sha256:abc123
evidence_window: sha256:def456
---

# Implementation Plan

## Overview

TODO

## Step 1: ...

TODO

## Validation Order

TODO
```

The editable document is an authoring input to a compiler. It does not become
authority merely because an agent wrote it.

## Generated prompt protocol

The handwritten prompt should contain domain guidance only. The runtime appends
a protocol generated from `StepAuthoringSpec`, the admitted binding, and the
current attempt:

```markdown
## Step authoring protocol

Complete `attempts/plan/attempt-12/response.md`.

Read-only inputs are listed in `context/manifest.json`.
You may edit only the declared model-owned fields and Markdown body.
Harness-derived and protected fields are not yours to author.
Your final chat response is informational; it cannot complete this step.
The step completes only when the response document compiles and its completion
specification is accepted.
```

Large ledgers and source artifacts remain path-addressed and hash-bound rather
than copied wholesale into the prompt. A small hot-context projection may be
inlined. The prompt, template, JSON Schema, parser, repair instructions, editor
hints, and completion mapping are all generated from the same declaration.

## Compilation and acceptance

The lifecycle is:

```text
admit step and freeze inputs
  -> materialize work package
  -> dispatch agent with bounded write grant
  -> snapshot submitted response
  -> parse and enforce field ownership
  -> derive harness-owned fields
  -> compile canonical candidate
  -> validate Step-IO and semantic constraints
  -> evaluate CompletionSpec
  -> publish through WBC/Custody acceptance transaction
```

The compiler must reject protected-field mutation, unknown fields, stale schema
versions, cross-attempt evidence, and changes outside the admitted write scope.
It must never silently restore or ignore an unauthorized mutation.

The canonical candidate and verdict are immutable. A later repair creates a new
snapshot or generation; it does not rewrite accepted history.

## Repair, retry, and recovery

Use graduated recovery rather than restarting the entire intellectual task:

1. **Optional hint omitted:** materialize a neutral value and derive the
   authoritative floor. Record that the model supplied no hint.
2. **Small syntax/completeness error:** run a narrow repair turn against the
   same package with stable path-addressed diagnostics. Preserve accepted fields.
3. **Semantic contradiction:** freeze the failed submission and open a new
   generation with the conflict and relevant evidence.
4. **Crash or timeout:** resume the same attempt only when its binding,
   checkpoint, lease, schema, and writable snapshot remain valid; otherwise
   create a new generation seeded from the last valid draft.
5. **Repeated identical failure:** stop blind replay, emit a deterministic
   failure receipt, and route the exact work package to the fixer.

Repair turns should have their own attempt identities and receipts while
remaining linked to the originating step occurrence. A chat message, liveness
label, or edited projection cannot manufacture completion.

## What to build

### 1. Authoring contract

Define an internal `StepAuthoringSpec` that references existing Step-IO schemas,
canonical workflow/step identity, prompt assets, field ownership, render/parse
format, derivations, and CompletionSpec. Do not create a second schema registry.

### 2. Materializer and compiler

Build deterministic schema-to-form and form-to-canonical compilation with:

- canonical serialization and content hashes;
- typed Markdown/YAML frontmatter support;
- protected-field comparison;
- derivation ordering and dependency-cycle rejection;
- stable source-located diagnostics;
- snapshot and schema migration rules; and
- checkout/editable/wheel/cloud equivalence.

### 3. Prompt integration

Generate the authoring protocol, allowed paths, ownership summary, completion
summary, and repair diagnostics at dispatch time. Pin the exact prompt asset,
form schema, compiler version, context manifest, and writable-path grant.

### 4. Attempt and custody integration

Bind packages to occurrence, attempt, generation, evidence window, custody
epoch, runtime identity, and store incarnation. Record materialization,
submission, compilation, repair, rejection, acceptance, crash, and supersession
as chronological events.

### 5. Migration adapters

Adapt existing Megaplan response schemas incrementally. During migration,
compare the compiled candidate with the legacy response-normalization result.
Every divergence receives an explicit disposition; parity counts are not an
oracle. Remove the legacy final-response authority after each phase cuts over.

### 6. Tooling

Provide inspect, validate, repair, explain, and render commands. Platform editor
support should expose writable versus protected fields, schema diagnostics,
source context, and completion status without making the view authoritative.

## Epic integration

### Immediate stop-bleeding work

Keep the current planner correction: omitted optional test hints receive neutral
values and the harness derives the authoritative test floor. This prevents
today's failure but is not the generalized architecture.

### Native Parity S3A — first vertical slice

Amend `s3a-prep-plan-critique-native-cutover` to require:

- `StepAuthoringSpec` for `prep`, `plan`, and `critique`;
- attempt-local typed response packages;
- generated prompt protocol and bounded file grants;
- deterministic compilation into the existing canonical phase records;
- shadow comparison against legacy response parsing;
- targeted repair/reentry fixtures;
- exact-pinned crash/resume tests; and
- removal of legacy final-chat authority for the migrated phases at GO-1A.

This is the smallest valuable slice because it covers research context, a large
Markdown artifact, structured machine fields, and critique occurrences.

### Later Native Parity milestones

Extend the same protocol as those phases migrate:

- S3B: revise and gate, including per-finding accountability;
- S4: tiebreaker and finalize, including durable reentry;
- S5A/S5B: effect-safe delivery, review, and rework;
- S6/S7: overrides, compatibility collapse, inventory equality, and proof that
  no legacy response writer remains reachable.

Execution forms must not invite agents to self-report facts the harness can
observe. Git changes, commands, tests, effects, timestamps, and receipts remain
derived; agents author only intent, decisions, explanations, and blockers.

### Platformization S2B — reusable core

Amend the `.pype` authoring-core milestone to productize:

- schema/identity-to-`StepAuthoringSpec` derivation;
- reusable form materialization and compilation;
- package/install correspondence;
- transactional schema/refactor migrations;
- one generated field-ownership and diagnostic catalog; and
- conformance proving every durable model step has exactly one authoring
  contract while pure helpers have none.

Completion templates and step authoring forms must remain distinct products:
completion templates define what must be proven; authoring forms collect a
model's candidate contribution.

### Platformization S3 — developer and agent experience

Amend the DX milestone to provide:

- editor and CLI support for generated response forms;
- source-located validation and targeted repair;
- navigation from response field to schema, source input, derived value, and
  completion obligation;
- unfamiliar-agent authoring tasks;
- format/lint stability and latency budgets; and
- deletion/rebuild proof for every non-authoritative view.

### Platformization S4–S6

Require extracted Megaplan patterns and the adversarial second consumer to use
the same authoring protocol without importing Megaplan. Stabilize only after the
second consumer demonstrates genuinely different forms, derivations, effects,
human boundaries, and rework behavior.

## Implications and trade-offs

### Benefits

- Eliminates final-envelope memory failures.
- Makes field ownership explicit and mechanically enforceable.
- Enables narrow repairs instead of repeating expensive research calls.
- Makes crashes and retries replayable and legible.
- Keeps model suggestions from narrowing deterministic safety floors.
- Reduces prompt/schema/parser drift through generation from one declaration.
- Produces a natural editor and agent interface for new workflow steps.

### Costs and risks

- More attempt-local artifacts and schema-version compatibility obligations.
- Frontmatter is awkward for very large or deeply nested records; some steps
  may need a small response directory rather than one file.
- Models may still damage templates, so compilation and ownership enforcement
  remain mandatory.
- Concurrent agents require isolated packages and explicit merge/join rules.
- Repair loops can become infinite unless identical-failure detection and
  attempt budgets are deterministic.
- A generic form DSL could become a second workflow language. Keep topology in
  `.pype`, reusable types/derivations in `.py`, and forms as generated views.
- Persisted authoring schemas become an internal compatibility promise before
  the public API stabilizes.

## Acceptance conditions

Do not call the capability complete until:

1. A model can omit optional hints and still produce a safe derived candidate.
2. A missing required semantic field produces a narrow repair, not a full
   research replay.
3. Protected-field mutation fails visibly.
4. Crash/reentry never stitches incompatible attempts or evidence windows.
5. The final chat response can be deleted without affecting the result.
6. The editable draft can be deleted after accepted publication and rebuilt as
   a non-authoritative view without changing authority.
7. Checkout, editable install, wheel, and cloud runs compile identically.
8. Two structurally different consumers use the same mechanism.
9. Every migrated phase has no reachable legacy response writer.
10. A chronological timeline joins materialization, edits, diagnostics, repair,
    compilation, acceptance, failure, and resolution with UTC timestamps.

## Questions for an oracle

### Architecture and ownership

1. Is `StepAuthoringSpec` genuinely a projection/adapter over Step-IO and
   CompletionSpec, or does it accidentally become a third contract system?
2. Which existing package should own it without creating an Arnold-to-Megaplan
   reverse dependency?
3. Is the model/derived/protected ownership algebra complete, including fields
   jointly proposed by a model but conservatively widened by the harness?
4. Should the canonical authoring source be typed Markdown, a response
   directory, or a typed object rendered into multiple views?
5. Can every supported step be represented without embedding workflow topology
   or authority rules in the form declaration?

### Authority and lifecycle

6. At precisely which transaction does a draft stop being unauthoritative and
   become an admitted candidate?
7. Are materialization, submission, compilation, verdict, and publication
   distinct occurrences or events within one occurrence?
8. What prevents an edited protected field, forged compiled record, or stale
   validation projection from influencing acceptance?
9. Are repair turns new attempts within one occurrence, or new occurrences
   linked by rework/reentry provenance?
10. What exact tuple bounds admissible evidence during resume?

### Failure and repair

11. Which omissions may receive deterministic defaults, and which must always
    fail closed?
12. How is semantic equivalence proven before preserving accepted fields across
    a repair?
13. What deterministic fingerprint identifies a repeated identical failure?
14. When should the system repair one document, restart one step, invoke the
    fixer, or block the workflow?
15. Can a repair agent observe enough context to succeed without receiving the
    original unbounded prompt transcript?

### Format and usability

16. Does YAML frontmatter remain robust for nested critique, rework, and
    execution records, or should complex fields be referenced child files?
17. Can common agents reliably edit the form using existing file tools without
    introducing partial-write races?
18. Should the runtime preload the editable form, or merely provide paths and a
    compact manifest?
19. How do editor diagnostics and agent repair prompts share one stable error
    catalog?
20. Can an unfamiliar author define a new step without manually synchronizing
    prompt text, schema, parser, template, and completion mapping?

### Sequencing and migration

21. Is Native Parity S3A the correct first authority cut, or must a smaller
    pre-S3A shadow milestone prove the compiler first?
22. Does adding the first vertical slice to S3A overload its GO-1A migration
    scope enough to justify a separate inserted milestone?
23. Which exact legacy normalizers/writers become unreachable after each phase
    cutover?
24. How should divergences between legacy parsing and form compilation be
    adjudicated when neither side is automatically correct?
25. Does Platformization S2B own enough compiler/identity machinery to
    generalize the feature without reopening Native Parity's format decisions?

### Adversarial proof

26. Show one current false failure this prevents and one unsafe false success it
    prevents.
27. Demonstrate a crash after draft write, after compilation, and during
    publication without duplicate effects or cross-attempt evidence stitching.
28. Demonstrate that a malicious model cannot turn a hint into a narrowed test
    floor or mutate runtime identity.
29. Demonstrate that deleting or forging every generated view cannot change the
    accepted result.
30. What second consumer is different enough to reveal falsely Megaplan-specific
    assumptions in the form/compiler design?

## Decision requested

Approve the architecture in principle, then amend Native Parity S3A and
Platformization S2B/S3 before those milestones execute. If the S3A scope becomes
too broad, insert one shadow-only authoring-package milestone immediately before
S3A; do not postpone the first real Megaplan slice until Platformization.
