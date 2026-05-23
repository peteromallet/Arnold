# Epic adversarial review

This document describes a proposed "mega plan sequence" for critiquing an
epic before the epic is decomposed into sprint-sized megaplans and run through
`megaplan chain`.

The goal is not to make the planning loop more agreeable. The goal is to attack
the epic from progressively lower levels of abstraction, revise it with senior
engineering judgment after each attack, and end with an epic that is either
ready to execute or clearly marked as not ready.

## Summary

The sequence has three critique/revise rounds:

```text
draft epic
  -> high-abstraction critique panel
  -> senior revision
  -> mid-abstraction critique panel
  -> senior revision
  -> low-abstraction critique panel
  -> senior revision / final recommendation
```

Each critique panel has five independent critics. Each critic gets one lens and
one job: find concrete reasons the epic may be wrong, weak, duplicated,
over-built, under-specified, or misaligned with the codebase.

Each revision pass is deliberately different. The reviser is not a mechanical
patch applicator. The reviser reads the findings, checks them against the repo
and the epic's intent, and decides which critiques to accept, reject, defer,
clarify, or escalate.

## Why this is different from a normal plan critique

The current megaplan critique loop is optimized for a single sprint plan:

```text
plan -> critique -> gate -> revise -> critique -> gate -> finalize
```

That loop works well once the unit of work is already the right size and shape.
An epic needs a more architectural preflight before it becomes a chain spec,
because the expensive mistakes are different:

- The epic may duplicate a system that already exists.
- The milestone decomposition may be wrong.
- The abstraction boundary may be missing or misplaced.
- The plan may be strategically sound but technically awkward.
- The individual steps may be executable, but the cross-milestone handoffs may
  fail.

Epic adversarial review sits before the normal `megaplan chain` run. It reviews
the epic artifact itself, not the implementation diff.

## Current-system fit

Megaplan already has most of the pieces needed for this shape:

- `--mode metaplan` can produce a document artifact instead of code. An epic
  review can be modeled as a document-mode run whose output is a revised epic
  document or chain spec.
- `critique` already supports a list of active checks. At higher robustness
  levels, multiple checks can run through parallel critique.
- `revise` already consumes critique and gate feedback, writes a new plan
  version, and records `flags_addressed`.
- `gate` already distinguishes "iterate", "proceed", "tiebreaker", and
  "escalate" instead of forcing every critique into a change.
- The pipeline framework already has the right topology concepts:
  `ParallelStage` for critique panels and a critique/revise loop pattern for
  repeated rounds.

The missing piece is a first-class epic-review profile or pipeline variant that
uses custom critique panels instead of the current sprint-plan critique checks.

## Round 1: high-abstraction critique

This round asks whether the epic is the right thing at all. Critics should be
allowed to challenge the premise, not just the implementation.

### Critics

| Critic | Question |
|---|---|
| Existing system reuse | Does the codebase already have concepts, commands, schemas, workflows, or artifacts that solve this? Is the epic duplicating them? |
| Conceptual fit | Does this belong in megaplan's current model, or is it forcing a new concept where an existing one should be extended? |
| Missing abstraction | Is there a shared abstraction that would simplify multiple milestones or avoid repeated custom logic? |
| Epic decomposition | Are the milestones sliced at the right boundaries, with real dependencies and sprint-sized deliverables? |
| Strategic risk | Is the epic solving the right problem, or is it optimizing around a temporary pain, unclear user value, or accidental workflow? |

### Expected findings

High-abstraction critics should produce findings like:

- "This already exists under X; the epic should extend it instead of creating Y."
- "Milestones 2 and 3 are inverted because the storage contract is not settled."
- "The proposed concept is too narrow; this is really a general panel-review
  primitive."
- "The epic should start with a metaplan discovery sprint instead of a chain."

### Revision stance

The senior reviser should be opinionated. It should not rewrite the epic just
because five critics produced five opinions.

For each finding, it should classify the response:

- `accept`: real issue; revise the epic.
- `reject`: critique is wrong, too speculative, or too expensive relative to
  the goal.
- `defer`: real issue, but belongs in a later milestone or follow-up.
- `clarify`: the epic needs clearer text, not a different shape.
- `escalate`: a human decision is required.

Round 1 revision should mostly change scope, concepts, milestone boundaries,
and settled decisions.

## Round 2: mid-abstraction critique

This round assumes the epic is directionally right and attacks the technical
approach.

### Critics

| Critic | Question |
|---|---|
| Codebase convention fit | Does the proposed implementation match how nearby code handles similar handlers, prompts, schemas, configs, artifacts, and state transitions? |
| Data and artifact model | Are the proposed files, state fields, schemas, and persisted artifacts shaped correctly? Will they be inspectable and resumable? |
| Orchestration semantics | Do phase transitions, retries, failures, resume behavior, and partial panel failures make sense? |
| Agent and model assignment | Are the right agents doing the right jobs? Are cheap critics being asked for deep synthesis, or premium models doing mechanical checks? |
| Blast radius | What shared behavior could this accidentally change? Which existing commands, robustness modes, profiles, tests, or chains might regress? |

### Expected findings

Mid-abstraction critics should produce findings like:

- "This should be a critique-check registry extension, not a new handler."
- "The artifact names are not versioned, so resumed runs may overwrite panel
  output."
- "The revise pass needs to preserve rejected critiques for audit, not only
  accepted changes."
- "This changes thorough critique behavior for normal plans unless the epic
  mode is isolated."

### Revision stance

Round 2 revision should mostly change interfaces, ownership boundaries,
artifact names, profile defaults, and state semantics. It should avoid reopening
Round 1 scope decisions unless the technical critique proves the earlier
decision was based on a false premise.

## Round 3: low-abstraction critique

This round assumes the concept and approach are mostly right. It attacks
executability.

### Critics

| Critic | Question |
|---|---|
| Implementation feasibility | Can an implementation agent execute each milestone from the written instructions without guessing? |
| Testability | Are there concrete unit, integration, fixture, or golden-output tests for the new behavior? |
| Edge cases | What happens on empty findings, malformed output, partial critic failure, repeated flags, resumed runs, stale versions, and interrupted revision? |
| CLI and UX details | Are command names, flags, output summaries, artifact names, and failure messages clear and consistent? |
| Migration and backcompat | Does this preserve existing plan directories, critique schemas, robustness behavior, profile resolution, and chain specs? |

### Expected findings

Low-abstraction critics should produce findings like:

- "The chain spec example omits the field that carries the reviewed epic
  artifact into milestone briefs."
- "There is no test proving a rejected critique remains visible in the audit
  trail."
- "The CLI should reject `--epic-review` without `--mode metaplan`, otherwise
  users may expect a code diff."
- "A failed critic should produce a structured panel error and let the senior
  reviser decide whether to continue."

### Revision stance

Round 3 revision should make the epic implementation-ready. It should tighten
steps, add test requirements, clarify artifacts, and mark unresolved decisions.
It should not reopen broad architecture unless a low-level detail proves the
architecture cannot work.

## Reviser contract

The reviser is the load-bearing part of the sequence. Without a strong reviser,
three rounds of critique become noise.

The reviser should receive:

- The current epic document or chain spec.
- The prior revision summary.
- All findings from the current panel.
- Any accepted, rejected, deferred, clarified, or escalated findings from prior
  rounds.
- The repo path and enough context to inspect current code.

The reviser should output:

- The revised epic document.
- A `changes_summary`.
- A decision table for every finding.
- Any new or changed settled decisions.
- Open questions that require human input.
- A readiness recommendation: `proceed`, `iterate`, or `escalate`.

The reviser should follow these rules:

- Prefer preserving the epic when the critique is weak.
- Change the epic when the critique exposes a real failure mode.
- Reject critiques explicitly instead of silently ignoring them.
- Defer valid but non-blocking work into follow-up notes.
- Avoid scope growth unless the broader work is required for correctness.

## Artifacts

A concrete implementation should persist panel and revision artifacts. One
possible layout:

```text
.megaplan/plans/<epic-review-plan>/
  epic_v1.md
  high_critique/
    existing_system_reuse.json
    conceptual_fit.json
    missing_abstraction.json
    epic_decomposition.json
    strategic_risk.json
    panel_summary.json
  epic_v2.md
  revision_high.json
  mid_critique/
    codebase_convention_fit.json
    data_artifact_model.json
    orchestration_semantics.json
    agent_model_assignment.json
    blast_radius.json
    panel_summary.json
  epic_v3.md
  revision_mid.json
  low_critique/
    implementation_feasibility.json
    testability.json
    edge_cases.json
    cli_ux_details.json
    migration_backcompat.json
    panel_summary.json
  epic_v4.md
  revision_low.json
  readiness.json
```

This does not have to replace existing `plan_vN.md` artifacts. A first version
could map `epic_vN.md` onto normal plan versions and keep panel outputs as
additional artifacts.

## Relationship to `megaplan chain`

Epic adversarial review should happen before `megaplan chain start`.

The expected flow is:

1. Write or generate an initial epic document.
2. Run epic adversarial review in metaplan mode.
3. Produce a final reviewed epic document with settled decisions.
4. Convert the reviewed epic into `chain.yaml` plus milestone briefs.
5. Run `megaplan chain start --spec chain.yaml`.

The reviewed epic should become context for each milestone. Today, that can be
done manually by referencing the reviewed document in each milestone brief. A
future implementation could make this first-class with a `reviewed_epic` or
`source_doc` field in the chain spec.

## Relationship to current critique checks

The current sprint-plan critique checks are:

- issue hints
- correctness
- scope
- all locations
- callers
- conventions
- verification
- criteria quality

Those checks remain right for implementation plans. Epic adversarial review
needs a different check registry because it is judging the epic artifact, not a
patch or sprint plan.

The two registries should be separate:

```text
sprint critique checks -> plan implementation quality
epic critique checks   -> epic shape, decomposition, architecture, readiness
```

They can share machinery:

- structured check specs
- parallel execution
- finding validation
- flag registry / decision registry
- revise output schema
- gate recommendations

They should not share the same prompt wording by default.

## Possible pipeline shape

In the Python pipeline framework, the clean shape is a sequence of parallel
panels and revise stages:

```text
draft_epic
  -> high_panel
  -> revise_high
  -> mid_panel
  -> revise_mid
  -> low_panel
  -> revise_low
  -> readiness_gate
```

Each panel is a `ParallelStage`. Each reviewer emits structured findings. The
join step collects the panel outputs in reviewer order and writes a panel
summary. The revise step is a `produce` step. The readiness gate emits a typed
recommendation:

- `proceed`: epic is ready to become a chain.
- `iterate`: another targeted revision is needed.
- `escalate`: human decision required.

This can be implemented without changing the normal planning pipeline if it is
registered as a separate pipeline or metaplan-mode variant.

## Minimal first implementation

A pragmatic first version should avoid over-building the orchestration.

1. Add an epic-review critique check registry with the 15 checks above grouped
   into three rounds.
2. Add prompt builders for:
   - one epic critic
   - one senior epic reviser
   - final readiness gate
3. Reuse the existing parallel critique runner shape for each five-critic panel.
4. Persist panel outputs as explicit artifacts.
5. Keep the revised epic as normal versioned markdown.
6. Document that the output is an input to `megaplan chain`, not an automatic
   chain run.

The first implementation does not need automatic chain-spec generation. That is
useful, but it is a separate risk surface. The core value is better epic
judgment before decomposition and execution.

## Open questions

- Should epic adversarial review be a new pipeline name, a `--mode metaplan`
  variant, or a new `megaplan epic review` command?
- Should each critic be allowed to inspect the repository independently, or
  should a prep phase produce a shared codebase map first?
- Should the same model run all five critics in a panel, or should panels mix
  model families to reduce correlated blind spots?
- Should rejected critiques become permanent audit records that later critics
  are told not to re-raise?
- Should the reviewed epic automatically emit `chain.yaml`, or should that stay
  a separate explicit conversion step?
