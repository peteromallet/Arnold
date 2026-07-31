# Standardized Completion Specifications for Arnold and Megaplan

## Status

Design proposal for oracle review. This document describes the current
completion machinery, identifies the missing abstraction, and proposes a
standard contract shared by dynamically planned tasks, durable workflow steps,
and composed workflows.

The proposal builds on the Step-IO Contract, Evidence-First Pipeline Semantics,
Custody Control Plane, and Megaplan Native Parity work. It does not propose a
second evidence system or a replacement for the existing acceptance
transaction.

## Executive summary

Every **durable semantic step**, every **dynamically admitted task**, and every
**durable workflow invocation** should have a standardized completion
specification.

Pure helpers should not have independent completion specifications. Their code,
dependencies, and behavior digest are part of the containing step or workflow.

The standard should distinguish three things:

1. **CompletionSpec** — the immutable definition of what completion means.
2. **CompletionBinding** — the binding of that definition to one admitted
   task, step invocation, or workflow occurrence.
3. **CompletionVerdict** — the evidence-backed judgment of whether the bound
   obligations were satisfied.

The intended relationship is:

```text
authored source / finalized task
             |
             v
     immutable CompletionSpec
             |
             v
 admission binds source, policy, authority, custody, and evidence window
             |
             v
      CompletionBinding
             |
             v
 execution emits receipts and primary evidence
             |
             v
 evidence providers compute CompletionVerdict
             |
             v
 accepted terminal transition or explicit blocked/waived/quarantined outcome
```

Most of the evidence collection, hashing, admission, custody, and transactional
acceptance machinery already exists. The missing abstraction is one
content-addressed semantic specification that states what a particular subject
must prove.

## 1. Terminology

### Durable semantic step

An explicitly declared `@step`, `@workflow`, registered effect adapter, human
suspension/reentry point, or dynamically admitted task whose invocation receives
an independently meaningful semantic identity.

Examples include a model-backed planning phase, an execution task dispatch, a
human suspension point, an external delivery effect, or a review reducer.

Durability is established by an authored declaration or admission record, then
checked mechanically. It is not inferred afterward merely because a unit
happened to appear in a ledger. The compiler/admission linter must require a
durable declaration when a unit:

- owns a typed product route or terminal outcome;
- declares a registered effect;
- owns suspension, reentry, checkpoint, retry, or durable child identity;
- requires Run Authority or Custody;
- produces an artifact consumed across a durable boundary; or
- becomes an admitted dynamic task.

Conversely, every declared durable unit must appear in the admitted topology,
binding registry, and attempt ledger. Declaration and runtime inventory must
match exactly.

### Pure helper

An implementation detail called inside a durable step. It may parse, normalize,
format, calculate, or serialize, but it does not independently choose workflow
routes, perform undeclared effects, own suspension, or create durable identity.

Pure helpers do not need separate completion specifications.

The static compiler must reject a helper that calls a workflow, invokes another
decorated step, calls an effect adapter, performs direct I/O or unmanaged
concurrency, returns an invocation target or route table, mutates durable state,
or owns retry, suspension, or checkpoint policy. Its transitive code and
dependency digest is folded into its containing durable subject.

### Dynamic task

A unit of work generated during Megaplan finalization or replan. It is not
necessarily an authored Arnold workflow step, but it becomes a durable semantic
subject once admitted for execution.

### Workflow

An authored composition of durable steps and child workflows with declared
branches, loops, fanout/fanin, suspension, reentry, and terminal outcomes.

### Obligation

One stable, independently verifiable condition inside a CompletionSpec.

### Evidence

An immutable or content-addressed fact used to evaluate an obligation. Evidence
may include artifacts, suite results, source and runtime attestations, accepted
authority decisions, custody receipts, effect records, human verification, or
other registered evidence kinds.

## 2. What the current system already has

The present system has several strong contract layers. They solve different
problems and should be retained.

### 2.1 Runtime outcome envelopes

Arnold provides typed result carriers such as `StepResult`, `ContractResult`,
`ExecutionResult`, `NativeExecutionResult`, phase results, suspension records,
and evidence artifact references.

These report what an invocation produced or how it exited. They do not, by
themselves, prove that the invocation achieved its semantic objective. A
`COMPLETED` result is still a claim until corroborated.

Relevant implementation surfaces include:

- `arnold/pipeline/types.py`
- `arnold/execution/result.py`
- `arnold/pipeline/native/runtime.py`
- `arnold_pipelines/megaplan/orchestration/phase_result.py`

### 2.2 Step-IO contracts

The completed Step-IO Contract work standardized typed artifact envelopes,
schema lookup, validation, compatibility behavior, and read/write decisions.

Relevant implementation surfaces include:

- `arnold/pipeline/step_io_contract.py`
- `arnold/pipeline/schema_registry.py`
- `arnold_pipelines/megaplan/runtime/schema_registry_adapter.py`

Step-IO contracts answer:

> Is this input or output shaped correctly and compatible with its declared
> schema?

They do not answer:

> Did this invocation accomplish what it was supposed to accomplish?

### 2.3 Plan-level success criteria

The plan and revise phases produce criteria shaped approximately as:

```json
{
  "criterion": "Changed-code resume rejects before any effect intent",
  "priority": "must",
  "requires": ["filesystem", "command_execution"]
}
```

These criteria are stored with the current plan version and consumed by
verifiability, review, and human-verification logic.

They are useful product-level intent, but they are textual, model-authored,
mutable across revisions, and not a complete per-task or per-step contract.

Relevant implementation surfaces include:

- `arnold_pipelines/megaplan/schemas/runtime.py`
- `arnold_pipelines/megaplan/prompts/planning.py`
- `arnold_pipelines/megaplan/handlers/plan.py`
- `arnold_pipelines/megaplan/orchestration/critique_runtime.py`

### 2.4 Finalized task contracts

The current cloud/M11 finalization path creates a rich effective task contract.
It includes or derives:

- stable task ID;
- objective and description;
- dependencies and dependency reasons;
- routing group;
- complete intended write set;
- narrow test selectors and budgets;
- checkpoint requirements;
- task difficulty and routing evidence;
- sense checks;
- watch items and user actions;
- critique-finding coverage;
- validation jobs;
- feasibility decisions;
- plan and task hashes;
- custody bindings.

The finalizer model proposes the task graph. Deterministic harness logic then
adds or normalizes gate tasks, validation work, proof splits, test selection,
baseline evidence, feasibility, hashes, and custody bindings.

The current effective completion definition is therefore substantial but
distributed. No one stable-ID object gathers the semantic obligations and
their accepted evidence.

Relevant current-cloud surfaces include:

- `arnold_pipelines/megaplan/finalize_contract.py`
- `arnold_pipelines/megaplan/handlers/finalize.py`
- `arnold_pipelines/megaplan/orchestration/task_feasibility.py`
- `arnold_pipelines/megaplan/orchestration/task_splitter.py`
- `arnold_pipelines/megaplan/orchestration/validation_jobs.py`
- `arnold_pipelines/megaplan/orchestration/critique_custody.py`

### 2.5 Workflow Boundary Contracts

The historical Workflow Boundary Contracts initiative standardized durable
effects at workflow boundaries and ordered durable ledgers for supported
step/attempt occurrences. Its North Star is
`.megaplan/initiatives/workflow-boundary-contracts/NORTHSTAR.md`.

It delivered generic primitives including:

- `BoundaryContract`;
- `BoundaryReceipt` and `BoundaryEvidence`;
- `SemanticFinding`;
- boundary templates and conformance helpers;
- durable references and payload policy;
- an execution-attempt ledger;
- Megaplan-specific contract declarations and semantic-health consumers.

Megaplan currently has a declarative registry of these durable boundary
contracts for planning, critique/revision, tiebreaker, execution,
review/rework, finalization, human verification, and overrides.

A boundary contract can declare:

- required artifacts;
- expected state changes;
- expected history entries;
- required phase results;
- required receipts;
- required authority.

The generic type is `BoundaryContract` in
`arnold/workflow/boundary_evidence.py`. The current Megaplan registry is
hand-authored in
`arnold_pipelines/megaplan/workflows/boundary_contracts.py`.

This is valuable evidence vocabulary, but it is not generated from canonical
workflow source and is not a complete per-node semantic completion definition.
Because it is a separate handwritten registry, it can drift from the actual
workflow.

The initiative's durable retirement record explicitly states that the
standalone initiative was retired unfinished and that completion was not
asserted. Remaining inventory, attempt-ledger adoption, and conformance work
moved into the Custody Control Plane. Therefore its delivered primitives are
real and load-bearing, but neither the initiative nor its schema should be
mistaken for a completed universal semantic task-completion standard.

### 2.6 Evidence-first completion verdicts

The Evidence-First work established the rule that `done` is a corroborated
predicate, not a trusted status flag. It introduced or strengthened:

- `EvidenceRef` and artifact references;
- evidence status and trust classes;
- provenance and freshness;
- `CompletionSubject`;
- `CompletionVerdict`;
- evidence providers;
- corroborated task completion;
- durable transition decisions.

The original Evidence-First epic was deliberately shortened after its first
vertical slice. Later work, especially Custody M11, has continued the deferred
transactional acceptance and authority work.

Relevant implementation surfaces include:

- `arnold_pipelines/megaplan/orchestration/evidence_contract.py`
- `arnold_pipelines/megaplan/orchestration/completion_contract.py`
- `arnold_pipelines/megaplan/orchestration/execution_evidence.py`
- `arnold_pipelines/megaplan/orchestration/review_evidence.py`

### 2.7 Transactional acceptance

Custody M5A and the current cloud/M11 code add a content-addressed acceptance
boundary with
candidate identity, invalidation, immutable receipts, provider verdicts, suite
evidence, and source/runtime binding.

Relevant current-cloud surface:

- `arnold_pipelines/megaplan/orchestration/acceptance_transaction.py`

This answers whether the evidence and candidate identity support an accepted
transition. It still relies on completion obligations defined across several
upstream artifacts.

Repository history contains no prior `CompletionSpec` implementation. The
closest per-task work is finalized-task feasibility, deterministic validation
jobs, critique custody, and acceptance binding. Those are foundations for the
proposed standard rather than evidence that the standard already exists.

## 3. The missing abstraction

There is no single canonical object that says:

> For this semantic subject, under this terminal outcome, these exact
> obligations must hold, these evidence kinds and producers may prove them,
> and these authority, custody, effect, waiver, and composition rules apply.

The result is fragmentation:

- Step-IO validates shape, not semantic achievement.
- Runtime results report outcomes, not objective satisfaction.
- Plan success criteria capture intent but are textual and plan-wide.
- Task descriptions, tests, sense checks, and validation jobs jointly imply
  task completion.
- Boundary contracts are handwritten and separate from canonical workflow
  source.
- CompletionVerdict evaluates available evidence but does not itself define the
  full semantic objective.
- Review can safely reopen an existing admitted task, but genuinely new rework
  has no canonical way to become an admitted, executable completion subject
  without returning through replan/finalize.

This is not a reason to replace the existing machinery. It is a reason to give
that machinery one canonical semantic input.

## 4. Proposed standard

### 4.1 One model, three records

#### CompletionSpec

Immutable definition of completion for a subject type.

Suggested fields:

```yaml
schema: arnold.completion_spec.v1
spec_id: megaplan.execute_task.v1
subject_kind: task
dispositions:
  accepted:
    terminal: true
  failed:
    terminal: true
  blocked:
    terminal: false
  suspended:
    terminal: false
  quarantined:
    terminal: false
obligations:
  - id: implementation_present
    candidate_dispositions: [accepted]
    requirement: required
    verifier: arnold.git.claimed_write_set_landed.v1
    proof_mode: presence
    evidence:
      kinds: [landed_diff]
      trusted_producers: [execution_evidence]
  - id: scoped_validation_green
    candidate_dispositions: [accepted]
    requirement: required
    verifier: arnold.validation.jobs_accepted.v1
    proof_mode: presence
    evidence:
      kinds: [validation_job_receipt]
      trusted_producers: [validation_runner]
  - id: blocker_is_current
    candidate_dispositions: [blocked]
    requirement: required
    verifier: megaplan.blocker.current_and_repairable.v1
    proof_mode: presence
    evidence:
      kinds: [blocking_failure_receipt]
      trusted_producers: [completion_evaluator]
authority_policy: arnold.run_authority.current_grant.v1
custody_policy: arnold.custody.current_epoch.v1
waiver_policy: megaplan.explicit_waiver.v1
```

The exact syntax remains an oracle decision. The important properties are
stable obligation identity, explicit outcome applicability, registered
verifiers, accepted evidence producers, and content-addressed versioning.

Evaluation is performed for one proposed candidate disposition:

1. Validate that the disposition is declared by the spec.
2. Select every obligation applicable to that disposition.
3. Evaluate those obligations against the pinned binding and evidence scope.
4. Accept the disposition only when its required obligations and authority
   policy pass.

There is no circular `applies_when: accepted` shortcut. `blocked`, `suspended`,
`waived`, `failed`, `cancelled_pending_reconciliation`, and `quarantined`
require their own evidence and transition rules. Quarantine is a nonterminal
durable holding disposition with a pinned exit contract, not a successful
terminal completion claim.

#### Obligation identity across versions

- `obligation_id` is a semantic name stable across compatible spec revisions.
- It must never be reused for a different semantic requirement.
- Changing verifier/evidence versions, thresholds, or requirement strength
  changes the spec hash even if the semantic obligation ID remains stable.
- Replacing the semantic meaning creates a new obligation ID and tombstones the
  old one.
- Verdict reuse requires the exact `(spec_hash, obligation_id, binding_hash)`
  tuple. A matching human-readable ID alone is never sufficient.

#### CompletionBinding

Immutable binding of a CompletionSpec to one occurrence.

It should include:

- spec ID and hash;
- semantic subject identity and path;
- task/step/workflow occurrence ID;
- authored program/topology digest;
- call-site policy digest;
- dependency and component lock;
- plan-contract digest where relevant;
- Run Authority subject attempt and fence;
- Custody target and epoch;
- WBC contract version and evidence window;
- installed runtime/source identity;
- prompt, tool, and behavior-relevant asset digests;
- child-set or dependency-set digest;
- normative evidence scope;
- admission timestamp and receipt reference.

The evidence scope is a content-addressed coordinate vector, not merely a
wall-clock interval. It includes every applicable coordinate:

- run, plan, milestone, subject, attempt, and generation identity;
- Run Authority fence;
- Custody lease, epoch, and process/runtime incarnation;
- primary-store incarnation and restore generation;
- per-store start cursor and inclusive high-water/end cursor;
- source base/head/tree and installed runtime identity;
- WBC contract version and evidence-scope schema version.

Evidence outside the bound scope is inadmissible regardless of matching
content. Stores without a scalar cursor use an explicit cursor vector. Evidence
is deduplicated by content identity within the binding, but one item may support
multiple obligations when each obligation explicitly cites it. Referencing one
receipt twice cannot prove an event occurred twice.

#### CompletionVerdict

Evaluation result for one binding.

It should include:

- binding hash;
- outcome under evaluation;
- one verdict per obligation;
- exact evidence references;
- verifier identity/version;
- satisfied, unsatisfied, unknown, waived, or not-applicable status;
- accepted terminal result;
- blocking reasons;
- human or operator authority where applicable;
- immutable verdict and acceptance receipt references.

The existing `CompletionVerdict` should evolve into this role rather than being
replaced by a parallel verdict type.

Load-bearing verifier independence is a declared policy. A verifier is not
independent merely because it runs in another process or under another display
name. Independence may require distinct code provenance or implementation
family, producer identity, trust/authority domain, and direct access to primary
evidence. The spec identifies the required independence class, and admission
rejects a producer/verifier pairing that does not satisfy it.

### 4.2 Which subjects receive a spec?

| Subject | CompletionSpec? | Reason |
|---|---:|---|
| Durable workflow invocation | Yes | Owns composed topology and terminal outcome |
| Durable semantic step invocation | Yes | Owns independently meaningful work/effect/outcome |
| Dynamically admitted execution task | Yes | Becomes a durable executable subject |
| Rework task | Yes | Must use the same admission and execution contract as original work |
| Human suspension/reentry | Yes | Owns durable authority and resume semantics |
| External effect | Yes, or a required nested effect contract | Must prove intent/outcome/ambiguity handling |
| Pure helper | No | Covered by containing subject's behavior digest |
| Quarantined occurrence | Existing binding remains nonterminal | Requires a pinned quarantine/exit disposition, not a successful completion spec |
| Generated projection | No authority-bearing spec | Projection is disposable and cannot decide completion |

### 4.3 Source of each obligation

Not every obligation should be model-generated or manually authored.

#### Deterministically generated

The compiler or admission layer can derive:

- semantic identity;
- allowed typed outcomes;
- declared input/output schemas;
- dependency and child sets;
- selected branch applicability;
- loop and fanout membership;
- declared effect requirements;
- suspension/reentry requirements;
- source and policy digests;
- required receipt families;
- standard authority and custody requirements;
- schema compatibility requirements.

The compiler also emits absence obligations when the contract requires proof
that something did not happen, such as no undeclared writes, no unregistered
effects, or no extra dynamic children. Such obligations require a
complete-capture evidence source; missing positive receipts are not proof of
absence.

#### Explicitly authored

Authors should declare only semantics that cannot be inferred safely:

- business acceptance conditions;
- exceptional aggregation policy;
- required human judgment;
- permitted waiver or quarantine conditions;
- domain-specific evidence and verifier selection.

#### Model-proposed

Planning/finalization models may propose:

- dynamic task objectives;
- task-specific semantic obligations;
- candidate verification methods;
- finding-to-task resolution obligations.

Model-proposed obligations are not authoritative merely because they are
well-formed. Admission must check that they are complete, non-circular,
machine-verifiable where claimed, correctly scoped, and bound to registered
verifiers or explicit human authority.

#### Harness-generated

The harness should add:

- standard landed-write obligations;
- narrow validation jobs;
- test baseline/delta obligations;
- evidence freshness and runtime-attestation obligations;
- critique-custody coverage;
- authority/custody/effect joins;
- contract and child-set hashes.

Every obligation declares a `proof_mode`, initially:

- `presence`: one or more admissible positive facts;
- `complete_capture_absence`: a complete evidence surface proving no matching
  event or mutation exists;
- `set_equality`: exact expected and observed membership;
- `aggregate`: deterministic child-obligation reduction.

An absence or set-equality verifier must name the complete-capture producer and
bound evidence scope. An incomplete evidence surface yields `unknown`, never a
successful absence verdict.

### 4.4 When generation occurs

“Generated on the fly” must not mean regenerated from mutable source during
execution or resume.

Safe generation points are:

1. **Compile/install:** derive the workflow and step CompletionSpec templates.
2. **Plan finalization:** propose dynamic task CompletionSpecs.
3. **Admission:** validate, augment, bind, hash, and freeze the exact specs.
4. **Replan/rework admission:** create a new version or new bound subject.

After admission, execution and resume consume the pinned binding. Changed source
or changed completion semantics require the pinned original, an explicit
migration, a new attempt, or quarantine.

## 5. Workflow composition

A workflow CompletionSpec should normally be generated by composing its child
contracts rather than restating them manually.

### Sequence

The workflow may accept only when every admitted required child on the executed
path has an accepted or explicitly permitted terminal disposition.

Composition uses a total mapping over child dispositions. No child disposition
is silently treated as success:

- clean `accepted` may contribute clean acceptance;
- `accepted_with_waiver` or a waived obligation propagates immutable waiver
  taint;
- `not_applicable` requires proof that the child or path was not admitted;
- `blocked`, `suspended`, `quarantined`, and
  `cancelled_pending_reconciliation` keep the parent nonterminal;
- `failed` and rejected terminal dispositions follow the workflow's explicit
  failure policy.

A parent may inherit a child waiver only when its own waiver policy explicitly
permits that obligation, scope, authority, and expiry. The parent verdict
retains the complete transitive waiver set; a deep waiver can never become a
clean root acceptance.

### Branch

Only obligations belonging to the accepted authority decision and selected
branch apply. Unselected branches are `not_applicable`, not silently satisfied.

The branch decision itself must have an accepted authority record and exactly
one matching consumed runtime transition.

### Loop

The contract must bind:

- loop instance identity;
- admitted iteration set;
- carried state;
- exit decision;
- per-iteration child subjects;
- caps and retry generations;
- final loop-ledger disposition.

Every admitted iteration must reach a valid terminal disposition. A loop cannot
claim completion because the most recent iteration passed while earlier
children remain unresolved.

### Fanout/fanin

The contract must freeze the admitted child set and aggregation policy.
Completion must not depend on nondeterministic completion order.

Stage 1 should prefer simple, explicit aggregation such as `all required
children accepted`. Quorum, race, first-wins, and loser cancellation should be
added only with a demonstrated consumer and defined cancellation semantics.

### Suspension and reentry

Suspension is a nonterminal durable outcome with a pinned resume contract.
Reentry must consume the matching authority decision, custody epoch, source
identity, and checkpoint binding.

### Rework

Review should not directly invent an executable task outside admission.

```text
review finding
      |
      v
proposed new or reopened task + proposed CompletionSpec
      |
      v
normal finalize/replan admission
      |
      v
bound task contract
      |
      v
same executable frontier, executor, evidence, and acceptance pathway
```

A reopened task may reuse its stable semantic task identity but must receive a
new attempt/generation binding. A genuinely new task receives a new stable ID
and must satisfy the same feasibility, validation, hashing, custody, and
acceptance requirements as initial work.

## 6. Authoring and completion experience

The ordinary authoring experience must remain much smaller than the runtime
machinery. Authors declare semantic intent; the compiler and admission/runtime
layers generate and enforce the contract records.

### 6.1 Pure helpers require no completion declaration

An undecorated pure helper needs no CompletionSpec:

```python
def normalize_findings(findings):
    ...
```

The compiler statically verifies the helper restrictions and folds its
transitive code and dependency digest into the containing durable subject.

### 6.2 Standard durable steps use generated templates

Most durable steps should select a standard completion template from their
declaration, signature, typed outcomes, effects, and step kind.

Illustrative syntax:

```python
@step
def render_report(ctx: ReportContext) -> ReportResult:
    report = ...
    return accepted(report=artifact(report))
```

The compiler can derive obligations such as:

- the proposed disposition is declared;
- output conforms to `ReportResult`;
- the artifact exists and matches its digest;
- required authority and custody are current;
- the attempt and receipt were durably recorded;
- no undeclared effect, output, write, or dynamic child occurred.

The author does not manually declare those mechanical obligations.

Reusable templates should cover common categories such as:

- code change;
- artifact producer;
- registered external effect;
- human gate;
- typed decision;
- fanout/reducer;
- delivery;
- review.

### 6.3 Domain-specific semantics stay small and explicit

Only acceptance meaning that cannot be inferred safely should require an
explicit declaration:

```python
@step(
    completes={
        "report_is_complete": verify("report.required_sections"),
        "all_sources_are_cited": verify("report.source_coverage"),
    }
)
def render_report(ctx: ReportContext) -> ReportResult:
    ...
```

The syntax is illustrative. The required structure is:

- stable semantic obligation ID;
- registered verifier ID and independence requirement;
- optional human-readable explanation;
- no arbitrary authoritative lambda;
- no manual receipt, evidence-window, authority, or custody plumbing.

A normal step should generally require zero to two explicit semantic
obligations beyond its standard template.

### 6.4 Workflow contracts compose automatically

An ordinary workflow should not restate every child obligation:

```python
@workflow
def delivery_cycle(ctx):
    implementation = execute_tasks(ctx.tasks)
    review = review_changes(implementation)

    while review.requires_rework:
        implementation = execute_tasks(review.rework_tasks)
        review = review_changes(implementation)

    return accepted(review.result)
```

The compiler derives the workflow CompletionSpec from admitted topology and
child specs:

- selected branches and typed decisions;
- loop instances and admitted iterations;
- fanout child sets and aggregation;
- suspension and reentry;
- rework generations;
- child dispositions and waiver taint;
- terminal workflow invariants.

Only exceptional root semantics require an explicit workflow obligation, for
example:

```python
@workflow(
    completes={
        "no_required_findings_remain": verify(
            "review.required_findings_closed"
        )
    }
)
```

### 6.5 Returning an outcome does not mark work complete

There is no authoritative `mark_done()` call. A step may propose a typed
disposition:

```python
return accepted(result)
```

That means only:

> This invocation proposes `accepted` and supplies this output and evidence
> linkage.

The runtime still performs:

```text
typed disposition proposed
        |
        v
output/effect receipts captured
        |
        v
pinned CompletionBinding loaded
        |
        v
registered verifiers evaluate applicable obligations
        |
        v
CompletionVerdict written
        |
        v
atomic acceptance transaction
        |
        v
disposable status projection may finally display done
```

An executor cannot manufacture completion with `done: true`.

### 6.6 Generated artifacts and human-readable views

Each admitted occurrence should produce canonical machine records conceptually
equivalent to:

```text
completion-spec.json
completion-binding.json
completion-verdict.json
acceptance-receipt.json
```

The final storage representation may be a canonical transactional store rather
than four physical files. These records are generated and content-addressed;
authors and executors do not edit them.

Tooling should generate a concise Markdown projection:

```markdown
# Completion: render-report / attempt 3

Disposition: accepted
Spec: sha256:...
Binding: sha256:...

- passed: output matches ReportResult
- passed: report artifact exists
- passed: required sections are present
- passed: cited sources resolve
- passed: no undeclared effects
- passed: authority and custody are current
```

This document is a disposable view of canonical records, not completion
authority. It may be deleted and regenerated without changing the verdict.

### 6.7 Human-only obligations generate focused requests

A genuinely human-only obligation produces a narrow verification request:

```text
Obligation: deployment visually matches approved design
Subject: deploy-preview / attempt 2
Evidence: preview URL, screenshots, build receipt
Required authority: release reviewer
Decision: approve or reject
Expiry: ...
```

The signed decision binds the stable obligation ID, spec hash, binding hash,
evidence scope, authority, scope, and expiry. Humans should not edit runtime
JSON or complete a generic omnibus checklist.

### 6.8 Dynamic Megaplan tasks are generated and admitted

Megaplan finalization proposes a dynamic task CompletionSpec from:

- task objective;
- intended write set;
- dependencies;
- narrow tests;
- plan success criteria;
- critique findings;
- checkpoint requirements;
- selected task template.

The harness validates and augments the proposal before admission. A task such as
“fix authentication” with no evidence capable of proving authentication was
fixed must be rejected before execution.

Review follows the same rule. It may propose a new or reopened task, but only
normal replan/finalize/admission can bind it and make it executable.

### 6.9 Intended author burden

| Authoring case | Manual completion work |
|---|---|
| Pure helper | None |
| Standard durable step | Normally none |
| Domain-specific step | One or two semantic obligations |
| Normal composed workflow | None beyond child composition |
| Workflow with a special root invariant | Declare only that invariant |
| Dynamic Megaplan task | Generated by finalization, then deterministically admitted |
| Human-only acceptance | Complete one focused generated verification request |

The authoring surface is convention over configuration: simple by default,
explicit where semantic meaning cannot be inferred, and rigorous without
exposing ordinary authors to custody, evidence-store, or receipt plumbing.

## 7. Authority boundaries

The completion standard must not collapse existing authorities:

- **Workflow topology** determines what happens next.
- **CompletionSpec** defines what must be proven for a terminal claim.
- **Run Authority** grants permission and accepts authoritative decisions.
- **Custody** determines the current exclusive actor and epoch.
- **WBC/evidence producers** record what crossed durable boundaries.
- **CompletionVerdict** evaluates evidence against the bound specification.
- **Acceptance transaction** atomically accepts or rejects the candidate.
- **Projections** display the result but own no decision.

A CompletionSpec is not permission to execute. A receipt is not proof merely
because it exists. A CompletionVerdict must not become an alternate route
authority.

## 8. Fit with the current roadmap

### Custody M11

M11 should finish its current scope:

- transactional task admission;
- task feasibility;
- deterministic validation-job compilation;
- content-addressed task, source, runtime, and custody bindings;
- evidence windows;
- acceptance transactions;
- immutable receipts;
- recovery-safe reconciliation.

It should not be broadened mid-run into a new authoring/compiler project.

### Megaplan Native Parity Corrective

Native Parity should complete and unify the existing completion architecture:

- **S1:** inventory existing contract carriers and freeze
  `CompletionSpec -> CompletionBinding -> CompletionVerdict`, obligation
  identity, authority ownership, and migration semantics.
- **S2F:** make the `.pype` compiler/linker generate workflow and durable-step
  CompletionSpec templates and include their hashes in manifests, locks, and
  source maps.
- **S2R:** bind those specs to Run Authority, Custody, WBC, checkpoint, source,
  runtime, and asset identity.
- **S3/S4:** migrate planning, gates, loops, execution, suspension, and
  finalization to the standard contract.
- **S5:** migrate review, delivery, and rework; ensure new rework returns through
  normal admission and the same execution path.
- **S6:** migrate overrides, auto-drive, and compatibility paths without
  allowing waivers or repairs to bypass contracts.
- **S7:** prove exact equality among admitted semantic subjects, bound
  contracts, required evidence producers, receipts, verdicts, consumed
  decisions, and terminal outcomes.

Native Parity must reuse the existing evidence and acceptance nucleus. It must
not create a second `CompletionVerdict`, evidence registry, receipt store, or
task scheduler.

### Workflow Platformization

Platformization should turn the proven Megaplan implementation into a reusable
Arnold feature:

- stable public schema and authoring API;
- generic compiler support;
- verifier and evidence-provider registration;
- package/version compatibility;
- generated contract inspection and documentation;
- local test harness;
- reusable workflow composition;
- a non-Megaplan second consumer;
- certification and evolution policy.

## 9. Migration strategy

Avoid a flag-day rewrite.

1. Define the new neutral schema and adapters over existing
   `BoundaryContract`, task contract, and `CompletionVerdict` data.
2. Generate shadow CompletionSpecs for the existing golden scenarios.
3. Before S2F, reproduce at least one concrete false completion or unroutable
   rework scenario that the new specification detects and the current
   distributed contract cannot represent cleanly.
4. Compare generated obligations and verdicts with current accepted behavior.
   Treat every divergence as an inventory item with an explicit disposition:
   old-system defect, generated-system defect, or reviewed intentional semantic
   change. A raw parity count is not an oracle.
5. Make missing, duplicate, stale, and unconsumed contracts visible.
6. Bind one vertical path:
   `finalize/admit -> execute -> evidence/verdict -> review -> reopen existing
   or admit new rework -> execute -> workflow aggregate`. Include landed-write
   and generated validation-job obligations. This exercises deterministic
   generation, model-proposed semantics, harness augmentation, rework identity,
   and the acceptance transaction.
7. Move to fail-closed admission for new durable subjects.
8. Migrate remaining review/rework and recovery paths.
9. Generate the boundary-contract registry from `.pype`; retain the old table
   only as a negative/parity fixture.
10. Remove old independent authority after installed/cloud conformance passes.

The first required exemplar is already available in captured M10/M11 history:
finalized tasks carry legacy `done` status while authority evidence says
`accepted=false` / `no_accepted_attempt`, and review produces a global
`task_id="REVIEW"` finding that cannot safely enter execution as an admitted
task. The golden fixture must prove that:

- legacy `done` remains unsatisfied without an accepted bound verdict;
- a global/new review finding becomes `proposed_new_subject` and returns through
  replan/finalize/admission;
- an existing finding may reopen an existing admitted subject under a new
  attempt binding;
- no pseudo-task such as `REVIEW` enters execute;
- accepted evidence for unrelated tasks is preserved; and
- the workflow cannot terminalize until every admitted binding has an accepted
  or explicitly permitted disposition.

## 10. Trade-offs

### Benefits

- One definition of completion across initial execution, retry, continuation,
  and rework.
- Exact explanations of why a subject is blocked.
- Less handwritten contract drift.
- Deterministic workflow composition.
- Strong changed-code resume rejection.
- Better fixer behavior because failed obligations are stable and addressable.
- Fewer false `done` states.
- Reusable contract inspection, documentation, and testing.
- Cleaner separation between semantic requirements, evidence, permission,
  custody, and acceptance.

### Costs and risks

#### Compiler and admission complexity

The compiler and admission boundary must generate, validate, bind, and version
contracts. This is additional machinery on a load-bearing path.

Mitigation: keep the schema small, reuse current evidence/acceptance types, and
begin with a single vertical slice.

#### False confidence from generated contracts

A mechanically generated contract may be internally consistent while omitting
the real business objective.

Mitigation: distinguish mechanically derived obligations from explicit
semantic obligations; require critique/verifiability coverage; prohibit an
authoring model from being the sole verifier of its own contract.

#### Contract explosion

Attaching durable contracts to every helper or expression would create
unreadable histories and excessive storage.

Mitigation: contract only durable semantic nodes and dynamic admitted subjects.
Fold helpers into behavior digests.

#### Versioning friction

Changing an obligation changes executable completion semantics and may prevent
resume under a new deployment.

Mitigation: make experimentation cheap in preview/sandbox modes; pin production
bindings; provide explicit migration, new-attempt, or quarantine paths.

#### Composition complexity

Loops, fanout, rework, human suspension, and partial failure require precise
aggregation rules.

Mitigation: begin with closed typed outcomes and simple all-required semantics.
Add quorum/race constructs only with demonstrated use cases.

#### Model-generated specification quality

Models can generate vague, circular, redundant, overly broad, or trivially
satisfied obligations.

Mitigation: stable obligation IDs, registered verifier requirements,
deterministic linting, adversarial critique, feasibility checks, and independent
review.

#### Evidence and storage volume

Per-obligation receipts can increase data and operational costs.

Mitigation: content-addressed deduplication, compact indexes, and disposable
projections over immutable primary evidence.

#### Generic-platform leakage

Premature generalization could bake Megaplan policy into Arnold.

Mitigation: Native Parity proves the model in Megaplan; Platformization extracts
only policy-neutral types and behavior proven by a second consumer.

## 11. Oracle sense-check questions

The oracle should answer these against code, schemas, fixtures, and executed
traces—not only against design prose.

### A. Problem definition and non-duplication

1. What exact failure remains after Step-IO contracts, EvidenceRef,
   CompletionVerdict, boundary contracts, and M11 acceptance transactions?
2. Can the proposal identify one concrete current false pass or blocked rework
   that the new CompletionSpec prevents?
3. Does any existing type already express the complete proposed semantics?
4. Is the proposal extending the existing completion nucleus, or accidentally
   creating a second verifier, evidence registry, or acceptance authority?
5. Which current fields become canonical, which become generated projections,
   and which are deleted?

### B. Granularity

6. What mechanically distinguishes a durable semantic step from a pure helper?
7. Can that distinction be checked statically?
8. Does every authority-increasing action have exactly one bound completion
   subject?
9. Are any durable effects hidden inside helpers without their own declared
   effect/completion obligation?
10. Does the proposal avoid per-helper contract explosion?

### C. Contract semantics

11. Is every obligation stable-ID, versioned, and outcome-specific?
12. Are `required`, `advisory`, `waived`, `not_applicable`, `unknown`, and
    `unsatisfied` unambiguous?
13. Can an advisory obligation accidentally influence terminal acceptance?
14. Can `not_applicable` be used to launder a missing required obligation?
15. Does every waiver name its authority, scope, reason, evidence, and expiry?
16. Are verifier identities and versions content-addressed or otherwise pinned?
17. Can arbitrary code or prose become an authoritative predicate?

### D. Generation and inference

18. Which fields are derived from topology, types, policies, and effects?
19. Which semantic obligations must be explicitly authored?
20. Which obligations may a planning model propose?
21. What deterministic checks prevent a model from proposing a circular or
    trivially satisfied contract?
22. Can the authoring model or executor be the sole verifier of its own claim?
23. Does generated output have a human-readable explanation and source map?
24. Can two equivalent source layouts produce the same logical contract
    identity where appropriate?

### E. Identity, admission, and versioning

25. Is the exact CompletionSpec hash bound at admission?
26. Is the binding joined to semantic path, task/step/workflow occurrence,
    source digest, policy digest, dependency lock, runtime, prompt/tool assets,
    authority attempt, custody epoch, and evidence window?
27. What changes preserve logical identity but change provenance?
28. What changes require a new executable identity, explicit migration, new
    attempt, or quarantine?
29. Can a resumed occurrence silently consume a regenerated contract?
30. Can an old completion manifest satisfy a revised contract with the same
    human-readable slug?
31. Are completion proofs bound to merge HEAD and installed/cloud runtime?

### F. Workflow composition

32. How does sequence completion aggregate required children?
33. How are unselected branches distinguished from satisfied branches?
34. Is each selected branch linked to exactly one accepted authority decision
    and one consumed runtime transition?
35. How are loop instance, iteration set, retry generation, exit decision, and
    carried state bound?
36. Can a loop complete while an earlier admitted iteration remains unresolved?
37. Is fanout completion based on a frozen child set and deterministic
    aggregation rather than completion order?
38. Are suspension and reentry nonterminal outcomes with pinned resume
    contracts?
39. Can a parent workflow accept before all applicable child obligations have
    valid dispositions?
40. Can child completion be counted twice?

### G. Dynamic tasks and rework

41. Does every initial execution task receive a CompletionSpec before dispatch?
42. Does every rework task use the same schema, feasibility checks, validation
    compilation, custody binding, executor, and acceptance boundary?
43. Can review directly create runnable work without returning through
    admission?
44. How is a reopened task distinguished from a new task and a new attempt?
45. Is every review finding linked to one or more admitted resolution
    obligations or an independently verified justified non-action?
46. Can accepted tasks be skipped on replay without losing evidence that their
    contracts were satisfied under the current binding?
47. Can a changed finding/task mapping invalidate stale acceptance?

### H. Evidence and trust

48. Does every obligation name acceptable evidence kinds and trusted producers?
49. Can a claim or projection masquerade as primary evidence?
50. Are evidence freshness, source/runtime identity, store incarnation, and
    high-water cursor checked?
51. Can evidence from different attempts or runs be stitched into one false
    completion?
52. Can duplicated receipts satisfy one obligation twice?
53. Are missing, stale, malformed, unknown, and contradictory evidence
    fail-closed in admitted production?
54. Does the verifier inspect raw primary evidence before normalization?
55. Is the verifier independent from the producer for load-bearing obligations?

### I. Authority, custody, and effects

56. Does a CompletionSpec remain non-authoritative for permission and routing?
57. Does every accepted authoritative action require current Run Authority and
    current Custody?
58. Can a stale fence, custody epoch, or process incarnation produce accepted
    completion?
59. Are effect intent, outcome, ambiguity, and idempotency identities bound to
    the completion occurrence?
60. Can an effectful child complete when its effect outcome is unknown?
61. Are WBC evidence and lease ownership prevented from being mistaken for
    permission?

### J. Failure, recovery, and human judgment

62. Does each failed obligation produce a stable diagnostic and supported
    recovery path?
63. Can the fixer identify the failed obligation without interpreting prose?
64. Does retry create a new attempt binding without erasing the previous
    failure?
65. Can repair or override mutate accepted history?
66. Are human-verification records bound to stable obligation IDs rather than
    mutable criterion indexes or text?
67. Can justified non-action decay into unverified boilerplate?
68. Are waiver and human decisions independently auditable and replayable?
69. After backup/restore, can accepted completion be reconstructed and
    revalidated without a side authority store?

### K. Developer experience

70. Can an author understand a workflow's completion behavior by reading its
    `.pype` and nearby typed declarations?
71. Can tooling explain every generated obligation and its source?
72. Can an author add a normal step without manually editing registries,
    receipts, validators, and projections?
73. Does preview mode allow rapid experimentation without making durable
    claims?
74. Does admitted mode fail with source-local, actionable diagnostics?
75. Can a ten-task unfamiliar-author exercise succeed without hidden
    repository knowledge?

### L. Migration and compatibility

76. Can the new model shadow current behavior before taking authority?
77. Is there one vertical slice that proves generation, binding, execution,
    evidence, verdict, and acceptance end to end?
78. Can old artifacts load as legacy/unknown without being treated as accepted?
79. Is the existing handwritten boundary registry retained as a parity/negative
    fixture before deletion?
80. Are old and new workers prevented from ambiguously interpreting the same
    binding?
81. Does rollback restore the previous complete authority set rather than a
    mixture of old and new writers?

### M. Scope and ownership

82. Which parts belong to Arnold as policy-neutral substrate?
83. Which parts remain Megaplan product policy?
84. Is Custody M11 kept focused on current transactional admission and
    acceptance work?
85. Does Native Parity prove the abstraction without prematurely claiming a
    public generic standard?
86. Does Platformization require an unrelated second consumer before
    certification?
87. Are there any new parallel stores, schedulers, route tables, or verdict
    systems that should instead be removed?

## 12. Recommended oracle acceptance conditions

The oracle should recommend adoption only if the design can demonstrate:

1. A single canonical completion vocabulary extends the existing evidence and
   verdict machinery.
2. Every durable semantic subject has exactly one admitted binding.
3. Pure helpers do not create contract noise or hidden authority.
4. Workflow contracts compose mechanically across sequence, branch, loop,
   fanout, suspension, and rework.
5. Dynamic rework returns through the same admission and execution path as
   initial work.
6. Model-proposed obligations cannot become authoritative without deterministic
   admission and independent evidence.
7. Resume consumes the pinned contract and rejects silent semantic drift.
8. Run Authority, Custody, WBC, completion evaluation, and acceptance remain
   separate authorities.
9. The design can migrate through one shadow vertical slice without a flag-day
   rewrite.
10. A non-Megaplan second consumer can use the eventual platformized form
    without importing Megaplan policy.

## 13. Proposed decision

Adopt a standardized hierarchical completion model with:

- one neutral `CompletionSpec` schema;
- one occurrence-level `CompletionBinding`;
- the existing `CompletionVerdict` evolved to evaluate bound obligations;
- deterministic compiler/admission generation where possible;
- explicit semantic declarations where inference is unsafe;
- specs for durable workflows, durable steps, dynamic tasks, rework, human
  suspension, and effects;
- no independent specs for pure helpers or disposable projections;
- Native Parity as the proving migration;
- Workflow Platformization as the public reusable extraction.

This closes the semantic gap left between Step-IO correctness and
evidence-backed terminal acceptance without discarding the substantial contract
and custody work already completed.

## 14. Disposition of the first external oracle review

An external prose review recommended adoption with seven amendments. Code,
current cloud artifacts, historical traces, and Native Parity plans support the
following disposition.

### Accepted, with simplification

1. **Mechanical durability/helper distinction:** genuine gap. Use explicit
   authored/admitted declarations plus compiler checks and exact inventory
   equality. Do not infer durability merely because a unit later appeared in a
   ledger.
2. **Per-candidate disposition evaluation:** genuine gap. Evaluate obligations
   for one proposed disposition; non-success dispositions require their own
   obligations. Quarantine is a nonterminal holding disposition.
3. **Obligation identity:** genuine gap. Use stable `obligation_id` plus
   canonical `spec_hash` and `binding_hash`. Do not add a separate mutable
   semantic-version counter unless a later migration use case requires one.
4. **Waiver propagation:** genuine gap. Reuse existing `AuthorityRecord`
   provenance and require total child-disposition mapping plus transitive waiver
   taint. Do not create another waiver subsystem.
5. **Negative obligations:** genuine gap. Add a small proof-mode vocabulary and
   require complete-capture evidence for absence. Do not create a separate
   negative-logic DSL.
6. **Evidence scope:** genuine ambiguity. Bind a coordinate vector including
   source/runtime, attempt/generation, authority fence, custody epoch, store
   incarnation/restore generation, and per-store cursors.
7. **Verifier independence:** the future Native/Custody plans already state the
   requirement, but the current implementation proves only nominal provenance.
   Enforce independence through code provenance/implementation family,
   producer identity, trust domain, and primary-evidence access.

### Corrections to the review's proposed mechanics

- A fixed four-element evidence-window tuple is too narrow for Git, multiple
  stores, installed runtime identity, and vector cursors.
- One receipt need not be restricted to one obligation. A content-addressed
  suite or attestation may legitimately support several explicitly linked
  obligations. It cannot be double-counted to prove multiplicity.
- Producer identity plus trust class alone does not prove verifier independence;
  two labels may wrap the same implementation and inputs.
- The review referred to the acceptance-condition section as containing eleven
  conditions; it contains ten (now §12 after the authoring section was added).
- “Satisfied by design” should be read only as “directionally addressed in
  prose.” No acceptance condition is satisfied until schemas, code, fixtures,
  and executed traces prove it.

### Empirically confirmed exemplar

The requested concrete failure exists in cloud history:

- M10 recorded `unroutable_review_rework_mixed` for pseudo-task `REVIEW`.
- The same trace contains repeated divergence where raw finalized status is
  `done` but acceptance is false because there is no accepted attempt.
- Current M11 likewise presents all finalized tasks as `done` while review
  acceptance evidence remains false.

This is the first mandatory vertical-slice fixture. It demonstrates both halves
of the missing abstraction: completion cannot derive from a legacy status
projection, and genuinely new review work cannot execute before it becomes a
bound admitted subject.
