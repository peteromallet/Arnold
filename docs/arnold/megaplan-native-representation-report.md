# Megaplan Native Python and Reusable Workflow Platform Representation Report

## 1. Executive summary

In this report, "native" means more than "the workflow is authored in
Python." It means the workflow uses a deterministic, statically validated,
well-fenced subset of Python in which product semantics are visible in control
flow itself: loops are loops, gates are branches, tiebreakers are subworkflows,
review rework is an explicit cycle, human intervention is a durable suspension
point, and task execution fanout is not hidden behind one opaque handler call.
The subset is intentionally smaller than arbitrary Python so topology,
identity, policies, effects, resume, and closed outcomes can be compiled,
inspected, and proved before execution.

That is the first target, not the final platform endpoint. The complete end
state has two ordered stages:

1. **Native Parity:** Megaplan becomes one readable, source-authoritative
   Python workflow. Its lowering and runtime preserve every product decision,
   dynamic child, retry, suspension, effect, reentry, and terminal outcome.
   Run Authority supplies permission, Custody supplies current exclusive
   ownership, WBC supplies exact-version durable boundary/effect evidence, and
   projections remain observational.
2. **Workflow Platformization:** only after Native Parity is proven, stable
   generic primitives and repeated workflow patterns are extracted into
   qualified, contracted, independently packaged components. A normative
   component lifecycle, composition algebra, isolation model, deterministic
   dependency lock, evolution rules, and conformance suite make those
   components safely reusable by unrelated workflows.

The current Megaplan planning workflow is Python-authored, but it is still
largely an explicit-node manifest graph with handler references. The top-level
file `arnold_pipelines/megaplan/workflows/planning.py` defines 13 steps and a
route table, while much of the product behavior is encoded inside handlers in
`arnold_pipelines/megaplan/handlers/`, execution code in
`arnold_pipelines/megaplan/execute/`, and auto-drive/runtime helpers.

The first main finding remains: a truly native Megaplan pipeline should look
like a normal Python program with durable phase calls. Its top-level structure
includes:

- a prep clarification gate;
- adaptive critique evaluation with retry;
- parallel critique lenses with fan-in;
- a bounded critique/gate/revise loop with severity-aware termination;
- a tiebreaker subworkflow with researcher/challenger branches and a human decision;
- finalize fallback routes;
- dependency-aware execution over runtime task batches;
- execute/review/rework loops;
- human override and force-proceed routes;
- explicit timeout, retry, escalation, model-routing, and suspension policies.

The repo already has many ingredients. Existing native pipeline infrastructure
includes `@pipeline`, `@phase`, `@decision`, fixed parallel blocks, native IR
compilation, graph projection, bounded loops, suspension routes, retry policy
slots, control transition slots, and subpipeline references. The largest
original Megaplan gaps are runtime-list iteration, dynamic parallel map,
source-level retry/timeout/model-routing policy, first-class break/continue or
typed loop outcomes, and a top-level way to describe auto-drive/event
transitions without handler state mutation.

The second main finding is newer: sharing the resulting Python functions is not
enough to create a workflow platform. Source reuse and clean-wheel imports do
not establish deterministic resolution, shape-independent recomposition, or
behavioral substitutability. Those require a standard component protocol and
proof that its declared semantics survive changes in parent, nesting shape,
package boundary, host, compatible version, policy binding, and implementation.

The intended architecture is:

```text
Arnold runtime and component protocol
  authoring, lowering, lifecycle, composition, identity, authority,
  custody, WBC evidence, checkpointing, effects, package resolution

Reusable workflow-pattern packages
  evaluator panels, bounded refinement, human gates,
  dependency-ready execution, review/rework, effect-safe actions,
  terminal/control arbitration

Product workflows
  Megaplan, an unrelated reference consumer, future workflows
```

The runtime layer owns generic execution invariants. Pattern packages own
reusable orchestration mechanics. Product packages own domain meaning, domain
outcomes, artifacts, policy values, and effect implementations.

This report was originally produced with five DeepSeek subagents launched
through a patched temporary copy of the Hermes launcher. The unmodified
launcher/fan script failed against this worktree because it expected the older
`arnold.pipelines.megaplan` import path; the temporary launcher changed those
imports to the current `arnold.agent` and
`arnold_pipelines.megaplan.runtime` modules. The research outputs were then
spot-checked against source files before synthesis. It has since been revised
against the Native Parity corrective plan, its golden trace contract, the
Workflow Platformization ticket, and the independent standardization review.

### 1.1 Canonical companion artifacts

- Native Parity execution plan:
  `docs/arnold/megaplan-native-parity-corrective-plan.md`
- Native Parity composition oracle:
  `.megaplan/initiatives/megaplan-native-parity-corrective/GOLDEN_TRACE_CONTRACT.md`
- Workflow Platformization ticket:
  `.megaplan/tickets/01KY2DWSJG0B9YKAJRYA0107XE-build-a-reusable-native-workflow-pattern-platform-after-megaplan-parity.md`
- Prepared Workflow Platformization contract and chain:
  `.megaplan/initiatives/native-workflow-platformization/PLATFORM_CONTRACT.md`
  and `.megaplan/initiatives/native-workflow-platformization/chain.yaml`
- Independent standardization review:
  `.tmp/workflow-standardization-gap/final-report.md`
- Holistic contract-stack audit:
  `.tmp/workflow-standardization-gap/holistic-context-audit.md`
- Adopted `.pype` target contract:
  `docs/arnold/pype-authoring-contract.md`
- Implemented/legacy Python-shaped migration baseline:
  `docs/arnold/python-shaped-authoring-contract.md`
- Generated workflow manifest contract:
  `docs/arnold/workflow-manifest.md`
- Run Authority controlling direction:
  `docs/arnold/runauthority-main-plan.md`
- Workflow Boundary Contracts North Star:
  `.megaplan/initiatives/workflow-boundary-contracts/NORTHSTAR.md`
- State/resume migration contract:
  `docs/arnold/state-authority-migration.md`

### 1.2 Three snapshots, not one

| Snapshot | Source of truth | What is proven |
| --- | --- | --- |
| Current state | Python source plus builder/component/handler/runtime carriers | Useful native syntax exists, but product route and policy authority remain split |
| Post-Native-Parity | `workflow.pype`, named `.pype` subworkflows, declared policies, pure phase bodies | Megaplan semantics are readable, source-authoritative, identity-safe, fenced, durable, and proven across checkout/wheel/cloud |
| Post-Platformization | Qualified component descriptors and locked reusable pattern packages consumed by product workflows | Components can be independently installed, validated, recomposed, upgraded, and substituted within declared compatibility ranges |

### 1.3 Contract stack and source-of-truth map

“Contract” is not one object in Arnold. Each layer owns a different fact. The
critical distinction is:

```text
Python source owns product semantic authorship
  -> static validation and deterministic lowering
generated WorkflowManifest owns admitted runtime/replay coordinates
  -> runtime may not add, erase, or reinterpret product topology
```

The manifest is canonical as serialized runtime input and identity. It is not
a second editable source of product routes. The Python source is canonical as
product semantic authorship. Generated manifests, indexes, locks, bindings,
and projections must all be reproducible from that source plus declared
dependencies and policies.

Manifest evolution is explicit rather than an in-place reinterpretation. The
serialized form carries a schema identifier/version and a canonical content
hash; admission pins both the manifest hash and the decoder/lowering contract
that gives it meaning. A newer worker may read an older manifest only through
a declared backwards-compatible decoder or an accepted provenance-bearing
migration. Otherwise the pinned worker/decoder remains available or the run is
quarantined. Re-serializing old coordinates under a new schema without a
declared conservation mapping is forbidden, and mixed-version workers must
prove identical admitted coordinates before sharing a run.

The Post-Native-Parity source model is one workflow per `.pype`, as frozen in
`pype-authoring-contract.md`. Every durable root or child workflow has its own
file; a `.pype` may also contain only private local steps and pure helpers.
Reusable steps/effects/schemas/policies/helpers live in `.py`, while ordinary
`.py @workflow` is explicit non-durable preview only. Static canonical imports
compose workflows without executing source. Logical identity is distribution
plus workflow name; paths are provenance, and behavior/shape changes require
explicit compatibility or migration disposition.

| Layer / contract | Authored or generated | Owns | Does not own or authorize | Current/future anchor |
| --- | --- | --- | --- | --- |
| `.pype` authoring contract | Authored source under the adopted restricted grammar | Product topology, canonical workflow imports, closed decisions, loops, fanout, stable semantic keys, private/shared boundaries, local policy/effect references | Runtime grants, leases, WBC history, live state, arbitrary Python escape hatches | `pype-authoring-contract.md`; `python-shaped-authoring-contract.md` v2 is current/legacy migration input only |
| Component export/descriptor | Authored typed declaration; richer Stage 2 descriptor is generated/validated with package metadata | Kind, ports, closed outcomes, state schema, dependencies, capabilities, policies, effects, suspension, extension points | Product route decisions outside the component; runtime permission | Current `arnold.workflow.authoring.ComponentContract`; Stage 2 `ComponentDescriptor` in this report is illustrative future API |
| `WorkflowManifest` | Generated compiler output | Stable nodes/edges/refs, policy slots, capabilities, manifest/topology hashes, replay coordinate | Editable product truth, RA decisions, custody, runtime journal | `arnold.workflow.manifest.v1`; `docs/arnold/workflow-manifest.md` |
| Megaplan Plan Contract | Authored/generated product artifact | Inter-milestone `provides`, `assumes`, interface paths/signatures, and `pre_existing` task declarations | Workflow topology, permission, custody, WBC completion, effect truth, terminal acceptance | `arnold_pipelines/megaplan/orchestration/plan_contracts.py` |
| Component/dependency lock | Generated during package resolution | Exact package, component contract/version, implementation, transitive dependency, artifact and conformance selection | Product routes or a grant to execute | Existing native pack metadata is partial precedent; full Stage 2 lock is future scope |
| Run Authority | Runtime decisions | Capability grants, subject attempts, accepted claims/decisions, coordinator fences, CAS/idempotency, quarantine | Renewable ownership, WBC history, scheduling, status, repair custody | `runauthority-main-plan.md`; exact API/version admitted from completed M11 |
| Custody | Runtime lease history | Exclusive current responsibility for an exact action/repair target, owner/process-birth identity, transfer/reclaim/expiry, monotonic epoch | Permission to perform the action or product route selection | Exact-target lease/epoch API admitted from completed M11 |
| WBC | Authored/generated declarations plus runtime history | Exact-version boundary obligations, execution attempts, ordered events, effects, provenance, receipts and findings | Grant, lease, transition, route, retry, resume, or terminal authority | WBC North Star/current v1 types; transactional M11 API admitted by Native Parity |
| Checkpoint/component state | Generated durable execution record | Semantic reentry cursor, local durable state, lineage, pinned executable versions | Route authority by marker existence; permission under an old fence/epoch | Current native/composite cursor precedent plus future enriched envelope |
| Effect history | Generated before/after external action | Intent, idempotency identity, outcome/ambiguity, receipt, compensation/reconciliation lineage | Permission for the action or proof from absence of a product receipt | Kernel effect ledger precedent plus M11 WBC effect history |
| Journal and accepted decisions | Generated append-only history | Durable authoritative decisions and replayable execution facts | Mutable compatibility status | Run Authority/WBC stores and kernel events |
| Projection/explanation | Generated, rebuildable view | Operator observation at declared source cursors and legal repair requests | Any positive action, route, resume, retry, completion, cancellation, publication, or delivery | `docs/reference/arnold-projections.md` and M11 query/projection APIs |

The Plan Contract deserves special care because its name sounds broader than
its implementation. Its current normalized payload is:

```text
provides[]
  name, description, interfaces[{symbol, signature, path}]
assumes[]
  name, upstream_milestone, interfaces[{symbol, signature, path}]
pre_existing[]
  task IDs whose work/evidence is treated as pre-existing in selected checks
```

It is a Megaplan product contract for plan/finalization and milestone-interface
consistency. `pre_existing` affects which execution evidence is required, so
the contract is not merely display metadata. It still does **not** authorize a
route or action, acquire custody, satisfy WBC, prove an effect, or accept a
terminal. Its path/signature comparison also does not perform general semantic
analysis. A “plan-contract failure” in older finalize code may additionally
refer to a separate baseline-test contract; callers should qualify the term.

#### Current-local versus completed-M11 provenance

Native Parity deliberately starts only after the remote Custody Control Plane
reaches its accepted M11 completion state. This checkout contains earlier and
partial contracts with similar names:

- the local `.megaplan/initiatives/custody-control-plane/` is a four-milestone
  resolver/repair-custody chain centered on `resolve_run_state()`;
- `arnold/supervisor/leases.py`, Megaplan capacity leases, and legacy runtime
  envelope fencing are useful but are not the assumed M11 exact-action
  Custody contract;
- local `BoundaryContract`, `BoundaryReceipt`, `AuthorityRecord`, and
  `SemanticFinding` types are current declarative precedent, not the completed
  transactional WBC attempt/effect system;
- the exact Run Authority, Custody, WBC, query, recovery, and validator APIs
  used by Native Parity are pinned from the accepted M11 completion manifest;
- admission also requires completed-M11 disaster-recovery evidence that backup
  restore/store rollback cannot resurrect an older RA fence or Custody epoch as
  current—for example through a monotonic control-plane incarnation or
  fail-closed reissue under strictly newer tokens.

Therefore this report specifies the admitted M11 semantics, not guessed local
API paths. The accepted version inventory and installed-artifact proof decide
which implementation satisfies the contract. Restore-resistant monotonicity is
a prerequisite proof consumed and re-exercised by Native Parity, not a local
Megaplan fence/epoch workaround.

### 1.4 Authoring-to-observation dataflow

The normal path is one-way:

```text
Python source + typed imports + product Plan Contract inputs
  -> static grammar/import/port/outcome/effect/policy validation
  -> deterministic lowering to DSL/WorkflowManifest
  -> component/package resolution and content-addressed dependency lock
  -> admission of exact program, policy, WBC, installed-artifact and lock versions
  -> semantic occurrence + WBC execution-attempt start
  -> accepted RA decision/grant + exact Custody target/lease/epoch
  -> conjunctive action validation
  -> body / checkpoint / effect intent+outcome / typed terminal journal
  -> exact-version WBC and Run Authority queries
  -> rebuildable projection / causal explanation / typed repair request
```

Static failures stop before a run exists. Resolution or version failures stop
before authority or custody acquisition. Stale grants, fences, leases, epochs,
WBC versions, or executable bindings quarantine before product body or effect
intent. Projections and explanations may feed a new typed request into the
front of the authority process; they cannot feed positive authority directly
back into execution.

Current Arnold has several partially overlapping planes: Python-shaped source
can lower to `WorkflowManifest` and run through `arnold.execution`; the native
compiler can produce a separately executed `NativeProgram`; and
`arnold/runtime/CONTRACT.md` describes a separate envelope/driver/settings
surface. Native tracing, manifest execution observability, and Megaplan
observability are also split. Native Parity and Platformization converge these
roles. This report's illustrative component API must not be mistaken for an
already-universal wrapper around every current path.

### 1.5 Qualified glossary

| Term | Meaning in this report |
| --- | --- |
| Semantic occurrence | One authored node/invocation at a deterministic path, including loop, item, retry, and reentry coordinates |
| RA subject attempt | The authorized identity making a claim under a current coordinator fence |
| WBC execution attempt | The ordered durable boundary/effect history of work actually attempted |
| Custody occurrence | Exclusive ownership of an exact action/repair target under a current lease epoch |
| Checkpoint | A durable semantic reentry and component-state record; not a status marker or permission token |
| Terminal | Qualified as component return, WBC attempt terminal, accepted RA terminal decision, root product terminal, or effect outcome |
| Evidence | A named immutable reference, WBC history, observation, or proof item; evidence supports a decision but does not grant authority |
| Reconciliation | Qualified as effect ambiguity resolution, WBC outbox repair, checkpoint/worktree recovery, or projection rebuild |
| Admission | Qualified as M11 prerequisite admission, compile/package admission, action admission, or registry publication admission |

## 2. Current state: explicit-node DSL plus handlers

The current Megaplan source authority is split across several files. The
product-readable authored source is
`arnold_pipelines/megaplan/workflows/workflow.pypeline`;
`arnold_pipelines/megaplan/workflows/workflow.py` is now compatibility glue.
The package-facing builder is
`arnold_pipelines/megaplan/workflows/planning.py`, which lowers/canonicalizes
that source into the explicit-node `arnold.workflow.dsl.Pipeline` shape consumed
by manifest/runtime tooling; `arnold_pipelines/megaplan/workflows/components.py`
binds handler refs and product policy metadata; and
`arnold_pipelines/megaplan/pipeline.py` is the public package facade. This split
is the current problem: the readable Python source exists, but the builder and
component tables still carry a second source of route/policy/handler truth.

The current graph is a declarative step/route graph:

- steps are `Step(...)` objects with ids such as `prep`, `plan`, `critique`, `gate`, `revise`, `tiebreaker_run`, `tiebreaker_decide`, `finalize`, `execute`, `review`, `halt`, and `override`;
- each phase step stores a `metadata["handler_ref"]` pointing back to `arnold_pipelines.megaplan.handlers:*`;
- route labels and condition refs represent the coarse graph branches;
- a few policy slots are attached, such as loop metadata on `revise` and `tiebreaker_decide`, suspension routes on `gate` and `review`, and control transition slots on `gate`, `review`, and `tiebreaker_decide`.

The high-level route comments in `planning.py` show the intended shape:

```text
prep -> plan -> critique -> gate
                          |-- proceed -> finalize -> execute -> review -> halt
                          |-- iterate -> revise -> critique
                          |-- tiebreaker -> tiebreaker_run -> tiebreaker_decide -> critique
                          |-- escalate / abort / suspend / force-proceed -> override
```

Relevant source locations:

| Area | Source |
| --- | --- |
| Product-readable authored workflow | `arnold_pipelines/megaplan/workflows/workflow.pypeline` |
| Compatibility workflow module | `arnold_pipelines/megaplan/workflows/workflow.py` |
| Package facade | `arnold_pipelines/megaplan/pipeline.py` |
| Workflow builder/lowering adapter | `arnold_pipelines/megaplan/workflows/planning.py` |
| Step/component definitions and handler refs | `arnold_pipelines/megaplan/workflows/components.py` |
| Canonical route/policy canonicalization | `arnold_pipelines/megaplan/workflows/planning.py` |
| Legacy state-machine topology | `arnold_pipelines/megaplan/_core/workflow_data.py:45` |
| Canonical state constants | `arnold_pipelines/megaplan/planning/state.py:7` |

The separate state-machine data in `arnold_pipelines/megaplan/_core/workflow_data.py` is simpler than the handler behavior. It defines transitions such as:

- `initialized -> prep -> prepped` and `initialized -> prep -> awaiting_human_verify`;
- `planned -> critique -> critiqued`;
- `critiqued -> gate/revise/tiebreaker/override`;
- `gated -> finalize`;
- `finalized -> execute`;
- `executed -> review -> done`;
- `blocked -> override force-proceed -> finalized`;
- `tiebreaker_pending -> tiebreaker-run -> tiebreaker_ready`;
- `tiebreaker_ready -> tiebreaker-decide -> critiqued`.

It also has robustness overrides. For example, `bare` allows `planned -> finalize`, and `light` bypasses the full review path by emptying `STATE_EXECUTED` transitions (`arnold_pipelines/megaplan/_core/workflow_data.py:95`).

The mismatch is the central issue: the top-level graph contains phase names and broad edges, while the handlers implement most of the actual control flow.

## 3. Product flow in plain English

Megaplan is a plan-and-execute workflow with multiple quality loops. The full product path is:

```text
initialized
  -> prep
  -> plan
  -> critique
  -> gate
  -> revise/gate loop until acceptable
  -> finalize
  -> execute
  -> review
  -> rework loop if needed
  -> done, blocked, aborted, or awaiting human verification
```

### Prep

Prep gathers task context before planning. It can run research orchestration and produce artifacts such as relevant code, test expectations, open questions, and criteria.

The important product decision is the prep clarification gate. `_apply_prep_clarify_gate()` checks prep output for blocking open questions. If blocking questions exist, the plan enters `STATE_AWAITING_HUMAN_VERIFY`; otherwise it enters `STATE_PREPPED` (`arnold_pipelines/megaplan/handlers/plan.py:21`, `arnold_pipelines/megaplan/handlers/plan.py:209`).

In a native pipeline, this is not just an implementation detail. It is:

```python
prep_payload = await prep()
if has_blocking_questions(prep_payload):
    answers = await suspend_for_human("prep_clarification", prep_payload.open_questions)
    await resume_clarify(answers)
```

### Plan

Plan invokes the planner model, writes a versioned plan artifact, merges/imports criteria, and derives planning metadata such as changed surfaces and test blast radius (`arnold_pipelines/megaplan/handlers/plan.py:140`).

This phase is comparatively linear. Most of it can remain a phase implementation, not top-level topology.

### Critique

Critique judges the plan before execution. It may:

- skip on `bare` robustness;
- run adaptive critique evaluator logic;
- select a subset of critique lenses;
- retry the evaluator once;
- fan out parallel critique workers over selected checks;
- fall back to sequential critique if parallel execution fails;
- write scratch and structured critique artifacts.

The retry and fanout are top-level product structure hidden in `handle_critique()` (`arnold_pipelines/megaplan/handlers/critique.py:279`). The evaluator retry loop starts around `_MAX_EVAL_ATTEMPTS = 2` (`arnold_pipelines/megaplan/handlers/critique.py:384`). Parallel critique dispatch is at `run_parallel_critique(...)` (`arnold_pipelines/megaplan/handlers/critique.py:710`).

In native form, critique is a small subworkflow:

```python
if robustness == "bare":
    return SkipCritique()

selection = await retry(critique_evaluator, attempts=2)
findings = await parallel_map(selection.active_checks, run_critique_lens)
critique_payload = await merge_critique(findings)
```

### Gate

Gate is the central plan-quality decision. It builds signals, invokes a gate worker, normalizes or recovers the worker response, validates flag resolution, reprompts once when unresolved blocking flags remain, applies high-complexity unverifiable-check backstops, records debt on accepted tradeoffs, and routes to proceed, iterate, tiebreaker, blocked, abort, or override.

Key source points:

- `_apply_gate_outcome()` starts at `arnold_pipelines/megaplan/handlers/gate.py:494`;
- `handle_gate()` starts at `arnold_pipelines/megaplan/handlers/gate.py:792`;
- high-complexity unverifiable checks are applied after the worker result (`arnold_pipelines/megaplan/handlers/gate.py:879`);
- unresolved blocking flags trigger a gate reprompt (`arnold_pipelines/megaplan/handlers/gate.py:911`);
- the second pass is merged and can still downgrade to iterate (`arnold_pipelines/megaplan/handlers/gate.py:984`).

Gate is where the critique/gate/revise loop is controlled. At a cap or no-progress threshold, critical unresolved flags lead to `STATE_BLOCKED`, while cosmetic-only unresolved work can force-proceed to `STATE_GATED`. That termination policy is product topology, not incidental parsing logic.

### Revise

Revise updates the plan based on gate feedback. It is the body of the critique loop. `handle_revise()` starts at `arnold_pipelines/megaplan/handlers/critique.py:1055`.

The current top-level graph already marks `revise` with a bounded loop policy (`arnold_pipelines/megaplan/workflows/planning.py:191`), but the branch of whether to go back through critique, gate, or terminate is still distributed across handler state mutations and workflow state logic.

### Tiebreaker

Tiebreaker handles split or ambiguous gate judgments. It has two handler phases:

- `handle_tiebreaker_run()` runs the tiebreaker subflow (`arnold_pipelines/megaplan/handlers/_tiebreaker_impl.py:37`);
- `handle_tiebreaker_decide()` applies a human or requested decision (`arnold_pipelines/megaplan/handlers/_tiebreaker_impl.py:76`).

The product semantics are:

```text
gate says TIEBREAKER
  -> researcher and challenger investigate rival interpretations
  -> human/system decision chooses pick, escalate, or replan
  -> pick goes back into revise/critique, escalate waits for human, replan restarts planning
```

The graph knows about `tiebreaker_run` and `tiebreaker_decide`, but the researcher/challenger split and decision routing are hidden behind handlers.

### Finalize

Finalize turns a gated plan into executable tasks, sense checks, watch items, user actions, validation metadata, and baseline/test-selection details. `handle_finalize()` starts at `arnold_pipelines/megaplan/handlers/finalize.py:1661`.

One topology-relevant branch is error fallback: `FinalizeBaselineSelectionError` can route back to revise (`arnold_pipelines/megaplan/handlers/finalize.py:64`, `arnold_pipelines/megaplan/handlers/finalize.py:1713`).

### Execute

Execute runs the finalized task plan. `handle_execute()` starts at `arnold_pipelines/megaplan/handlers/execute.py:134`.

Execution hides a substantial workflow:

- asks for destructive/user-approved confirmation in relevant modes;
- chooses batch or auto-loop execution;
- dispatches tasks by model tier and task complexity;
- forces fresh sessions for review rework or blocked retries;
- tracks blocked tasks and quality-gate failures;
- writes stub reviews when review is skipped;
- transitions directly to done or human verification for no-review robustness levels.

The large auto-execute loop is `handle_execute_auto_loop()` (`arnold_pipelines/megaplan/execute/batch.py:2278`). Single-batch execution starts at `handle_execute_one_batch()` (`arnold_pipelines/megaplan/execute/batch.py:1201`).

### Review

Review judges the completed work. `handle_review()` starts at `arnold_pipelines/megaplan/handlers/review.py:1297`.

Review can:

- approve the work;
- request rework;
- block;
- route to human verification for deferred human criteria;
- retry review on infrastructure failure;
- run parallel review checks for extreme robustness;
- classify rework as blocking or advisory;
- cap rework cycles and decide between blocked and force-proceed.

The main outcome state machine is `_resolve_review_outcome()` (`arnold_pipelines/megaplan/handlers/review.py:722`). Parallel review is dispatched through `run_parallel_review(...)` (`arnold_pipelines/megaplan/handlers/review.py:1466`).

### Override and human gates

Override is a human/control-plane dispatcher. `_OVERRIDE_ACTIONS` is defined at `arnold_pipelines/megaplan/handlers/override.py:1763`; `handle_override()` starts at `arnold_pipelines/megaplan/handlers/override.py:1780`.

Override actions include add-note, abort, force-proceed, replan, recover-blocked, resume-clarify, set-robustness, set-profile, set-model, and set-vendor. Some are side effects; others are hard control-flow edges.

Native topology should model these as named human/control transitions, not as one opaque `override` handler with an action string.

## 4. Inventory of currently hidden logic

| Step / area | Current source | Hidden control flow | Should be top-level? |
| --- | --- | --- | --- |
| `prep` | `arnold_pipelines/megaplan/handlers/plan.py:21`, `:209` | Blocking open questions route to awaiting-human state. | Yes, as a conditional human suspension. |
| `plan` | `arnold_pipelines/megaplan/handlers/plan.py:140` | Mostly linear worker invocation and artifact write. | No, phase body is fine. |
| `critique` | `arnold_pipelines/megaplan/handlers/critique.py:279` | Bare skip, adaptive evaluator, evaluator retry, active-lens selection, parallel critique fanout, sequential fallback. | Yes. |
| Critique evaluator retry | `arnold_pipelines/megaplan/handlers/critique.py:384` | One initial evaluator attempt plus one retry, with raw-output recovery. | Yes, as retry policy on a sub-step. |
| Parallel critique | `arnold_pipelines/megaplan/handlers/critique.py:710` | Multiple checks run concurrently and merge. | Yes, as parallel map/fan-in. |
| `gate` | `arnold_pipelines/megaplan/handlers/gate.py:792` | Signal build, worker call, validation, retry/reprompt, recommendation recovery, debt recording, route selection. | Yes. |
| Gate outcome routing | `arnold_pipelines/megaplan/handlers/gate.py:494` | Proceed/iterate/tiebreaker/escalate/blocked decisions plus cap/no-progress termination. | Yes, as a decision node plus loop policy. |
| Gate reprompt | `arnold_pipelines/megaplan/handlers/gate.py:911` | Re-run gate worker once when blocking unresolved flags remain. | Yes, as retry/repair edge. |
| Gate high-complexity backstop | `arnold_pipelines/megaplan/handlers/gate.py:879` | PROCEED is auto-downgraded to ITERATE if high-complexity unverifiable checks exist. | Yes, as post-gate validation branch. |
| Gate debt recording | `arnold_pipelines/megaplan/handlers/gate.py:78` | Accepted tradeoffs/unresolved concerns become debt entries on PROCEED. | Partial, as an effect on the proceed edge. |
| `revise` | `arnold_pipelines/megaplan/handlers/critique.py:1055` | Updates plan and re-enters critique/gate loop. | Partial; top-level loop already exists, but routing should be clearer. |
| Tiebreaker validation | `arnold_pipelines/megaplan/handlers/critique.py:1194` | Validates tiebreaker eligibility and can reprompt/route. | Yes, as explicit tiebreaker gate. |
| `tiebreaker_run` | `arnold_pipelines/megaplan/handlers/_tiebreaker_impl.py:37` | Researcher/challenger sub-invocations. | Yes, as a subworkflow with fanout. |
| `tiebreaker_decide` | `arnold_pipelines/megaplan/handlers/_tiebreaker_impl.py:76` | Pick/escalate/replan decision routing. | Yes, as human/control decision. |
| `finalize` | `arnold_pipelines/megaplan/handlers/finalize.py:1661` | Baseline-selection failure fallback to revise. | Yes, as error edge. |
| `execute` | `arnold_pipelines/megaplan/handlers/execute.py:134` | Batch vs auto-loop, user/destructive gates, blocked retry, fresh sessions, no-review terminal routing. | Yes. |
| Execute single batch | `arnold_pipelines/megaplan/execute/batch.py:1201` | Batch unit execution and result merge. | Yes, as task batch subworkflow. |
| Execute auto loop | `arnold_pipelines/megaplan/execute/batch.py:2278` | Dependency-aware task scheduling, blocked-task handling, batch iteration. | Yes, as dynamic foreach/map over task batches. |
| `review` | `arnold_pipelines/megaplan/handlers/review.py:1297` | Review mode selection, parallel review, outcome state machine, rework cap, human verification. | Yes. |
| Review outcome | `arnold_pipelines/megaplan/handlers/review.py:722` | Approved/needs-rework/blocked routing, cap behavior, force-proceed vs blocked. | Yes, as decision plus loop. |
| Parallel review | `arnold_pipelines/megaplan/handlers/review.py:1466` | Extreme robustness fanout and merge. | Yes. |
| Override | `arnold_pipelines/megaplan/handlers/override.py:1763`, `:1780` | Action dispatch to abort, force-proceed, replan, resume, recover, profile/model changes. | Yes, at least for routing actions. |
| Phase runtime observability | `arnold_pipelines/megaplan/_core/phase_runtime.py` | Expected durations, stale/dead worker detection, timeout metadata. | Partial, as top-level timing/escalation policy. |
| Auto-drive loop | `arnold_pipelines/megaplan/auto.py` | Re-derives next steps, applies retry/escalation/cost/stall policies. | Yes, as runtime policy and event loop rather than handler side effects. |

The recurring pattern is clear: the graph has phase labels, while handlers are mini-orchestrators. A true native pipeline would lift those mini-orchestrators into named, inspectable topology.

## 5. Stage 1 target: source-authoritative native Megaplan

> **Format note:** the following monolithic `planning_native.py` listing is a
> semantic/topology sketch retained from the earlier design, not the adopted
> file grammar. Implementation splits each shown pipeline/subworkflow region
> into its own one-workflow `.pype` (`workflow.pype`,
> `plan_quality/{cycle,critique,gate,tiebreaker}.pype`, and
> `delivery/{cycle,execute,execute_batch,review}.pype`) and places reusable
> leaves in adjacent `.py` files. Read `@subworkflow` below as “canonical
> workflow invoked as a child,” not a second authored decorator.

Below is an aspirational
`arnold_pipelines/megaplan/workflows/planning_native.py`. It is intentionally
unconstrained by current manifest/compiler restrictions. The syntax uses
ordinary Python plus imagined durable decorators and helpers. It is an
**illustrative target API, not a claim that these exact imports, decorators, or
call signatures exist today**. The goal is to show what the workflow looks like
when everything that belongs at product-topology level is expressible there.

```python
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from arnold.pipeline.native import (
    checkpoint,
    decision,
    effect,
    exit_enclosing_loop,
    foreach,
    human_gate,
    model_route,
    parallel,
    phase,
    pipeline,
    retry,
    subworkflow,
    timeout,
)


GateDecision = Literal[
    "proceed",
    "iterate",
    "tiebreaker",
    "escalate",
    "abort",
    "blocked",
    "blocked_preflight",
    "force_proceed",
]

ReviewDecision = Literal[
    "approved",
    "needs_rework",
    "blocked",
    "human_verify",
]


@dataclass
class MegaplanContext:
    root: Path
    robustness: str
    profile: str
    max_critique_iterations: int = 4
    max_review_rework_cycles: int = 3
    max_gate_reprompts: int = 1
    max_eval_attempts: int = 2
    user_approved: bool = False
    confirm_destructive: bool = False
    auto_approve: bool = False


@phase(model=model_route("prep"), timeout=timeout(minutes=30))
async def prep(ctx: MegaplanContext) -> PrepPayload:
    """Run prep research and return prep payload with questions and criteria."""


@decision(vocabulary={"clear", "needs_human"}, human_gate=True)
def prep_clarification_gate(prep_payload: PrepPayload) -> Literal["clear", "needs_human"]:
    return "needs_human" if prep_payload.has_blocking_questions else "clear"


@human_gate(capability="human:prep-clarification", reentry="resume_clarify")
async def collect_prep_clarification(prep_payload: PrepPayload) -> HumanClarification:
    """Suspend until the user answers blocking prep questions."""


@phase(model=model_route("planner"), timeout=timeout(minutes=45))
async def plan(ctx: MegaplanContext, prep_payload: PrepPayload | None) -> PlanPayload:
    """Produce the initial or replacement plan artifact."""


@phase(model=model_route("critique_evaluator"), timeout=timeout(minutes=15))
async def critique_evaluator(ctx: MegaplanContext, plan_payload: PlanPayload) -> CritiqueSelection:
    """Select critique lenses and model tiers for the current plan."""


@phase(model=model_route("critique", by="check.complexity"))
async def critique_lens(ctx: MegaplanContext, check: CritiqueCheck, plan_payload: PlanPayload) -> CritiqueFinding:
    """Run one critique lens."""


@phase
async def merge_critique(findings: list[CritiqueFinding]) -> CritiquePayload:
    """Merge critique findings into a single critique payload."""


@subworkflow
async def critique(ctx: MegaplanContext, plan_payload: PlanPayload) -> CritiquePayload:
    if ctx.robustness == "bare":
        return CritiquePayload.skipped(reason="bare_robustness")

    selection = await retry(
        critique_evaluator,
        attempts=ctx.max_eval_attempts,
        recover_with="raw_output_json",
    )(ctx, plan_payload)

    if not selection.active_checks:
        return CritiquePayload.empty(reason="no_active_checks")

    findings = await parallel.map(
        selection.active_checks,
        lambda check: critique_lens(ctx, check, plan_payload),
        max_workers=selection.max_workers,
        fallback="sequential",
    )
    return await merge_critique(findings)


@phase
async def build_gate_signals(
    ctx: MegaplanContext,
    plan_payload: PlanPayload,
    critique_payload: CritiquePayload,
) -> GateSignals:
    """Build deterministic signals and preflight evidence for gate."""


@phase(model=model_route("gate"), timeout=timeout(minutes=20))
async def gate_worker(ctx: MegaplanContext, signals: GateSignals) -> GatePayload:
    """Ask the gate model for proceed/iterate/tiebreaker/escalate."""


@phase
async def normalize_gate_payload(raw: GatePayload, signals: GateSignals) -> GatePayload:
    """Recover invalid/empty gate recommendations from deterministic signals."""


@phase
async def validate_flag_resolution(payload: GatePayload, signals: GateSignals) -> FlagValidation:
    """Return unresolved blocking flag ids and resolution quality notes."""


@phase(model=model_route("gate"), timeout=timeout(minutes=20))
async def reprompt_gate_worker(
    ctx: MegaplanContext,
    signals: GateSignals,
    missing_flag_ids: list[str],
) -> GatePayload:
    """Second gate attempt focused on unresolved blocking flags."""


@phase
async def persist_gate_debt(payload: GatePayload, signals: GateSignals) -> None:
    """Record accepted tradeoffs as debt on the proceed edge."""


@decision(
    vocabulary={
        "proceed",
        "iterate",
        "tiebreaker",
        "escalate",
        "abort",
        "blocked",
        "blocked_preflight",
        "force_proceed",
    }
)
def gate_decision(payload: GatePayload, signals: GateSignals, loop: LoopState) -> GateDecision:
    # Precedence is normative: preflight -> exhaustion/no-progress -> severity
    # fallback -> the normalized closed recommendation.
    # no_progress_streak compares only comparable generations and advances when
    # canonical unresolved blocking-flag IDs fail to decrease strictly.
    if signals.has_agent_availability_preflight_block and payload.recommendation == "proceed":
        return "blocked_preflight"
    if loop.exceeded_max or loop.no_progress_streak_exceeded:
        return "blocked" if signals.has_correctness_or_security_blockers else "force_proceed"
    if signals.has_high_complexity_unverifiable_checks and payload.recommendation == "proceed":
        return "iterate"
    return payload.recommendation


@subworkflow
async def gate(
    ctx: MegaplanContext,
    plan_payload: PlanPayload,
    critique_payload: CritiquePayload,
    loop: LoopState,
) -> tuple[GateDecision, GatePayload]:
    signals = await build_gate_signals(ctx, plan_payload, critique_payload)
    payload = await normalize_gate_payload(await gate_worker(ctx, signals), signals)

    validation = await validate_flag_resolution(payload, signals)
    if validation.blocking_unresolved_ids:
        retry_payload = await reprompt_gate_worker(ctx, signals, validation.blocking_unresolved_ids)
        payload = await normalize_gate_payload(payload.merge_retry(retry_payload), signals)
        validation = await validate_flag_resolution(payload, signals)
        if validation.blocking_unresolved_ids:
            payload = payload.downgrade_to_iterate(
                reason="blocking unresolved flags after gate reprompt",
            )

    decision = gate_decision(payload, signals, loop)
    if decision in {"proceed", "force_proceed"}:
        await persist_gate_debt(payload, signals)
    return decision, payload


@phase(model=model_route("planner"), timeout=timeout(minutes=45))
async def revise(
    ctx: MegaplanContext,
    plan_payload: PlanPayload,
    gate_payload: GatePayload,
) -> PlanPayload:
    """Revise the plan using gate feedback."""


@phase(model=model_route("tiebreaker_researcher"))
async def tiebreaker_researcher(ctx: MegaplanContext, gate_payload: GatePayload) -> TiebreakerArgument:
    """Research the case for the contested path."""


@phase(model=model_route("tiebreaker_challenger"))
async def tiebreaker_challenger(ctx: MegaplanContext, gate_payload: GatePayload) -> TiebreakerArgument:
    """Challenge the contested path."""


@human_gate(capability="human:tiebreaker", reentry="tiebreaker_decide")
async def decide_tiebreaker(
    gate_payload: GatePayload,
    arguments: list[TiebreakerArgument],
) -> Literal["pick", "escalate", "replan"]:
    """Suspend or apply a supplied tiebreaker decision."""


@subworkflow
async def tiebreaker(ctx: MegaplanContext, gate_payload: GatePayload) -> TiebreakerDecision:
    researcher, challenger = await parallel.gather(
        tiebreaker_researcher(ctx, gate_payload),
        tiebreaker_challenger(ctx, gate_payload),
    )
    action = await decide_tiebreaker(gate_payload, [researcher, challenger])
    return TiebreakerDecision(action=action, arguments=[researcher, challenger])


@phase(model=model_route("finalize"), timeout=timeout(minutes=45))
async def finalize(ctx: MegaplanContext, plan_payload: PlanPayload, gate_payload: GatePayload) -> FinalizePayload:
    """Turn an accepted plan into executable tasks and validation data."""


@phase
async def recover_finalize_baseline_failure(error: FinalizeBaselineSelectionError) -> GatePayload:
    """Convert finalize baseline failure into revise feedback."""


@human_gate(capability="human:execute-approval", reentry="execute")
async def require_execute_approval(ctx: MegaplanContext, finalize_payload: FinalizePayload) -> None:
    """Suspend until destructive/user-approved execution is allowed."""


@phase(model=model_route("execute", by="task.complexity"))
async def execute_task_batch(ctx: MegaplanContext, batch: TaskBatch) -> BatchResult:
    """Execute one dependency-ready batch."""


@phase
async def merge_execution_results(results: list[BatchResult]) -> ExecutePayload:
    """Merge task batch results, blocked tasks, quality gates, and artifacts."""


@subworkflow
async def execute(ctx: MegaplanContext, finalize_payload: FinalizePayload) -> ExecutePayload:
    if not ctx.auto_approve and not ctx.user_approved:
        await require_execute_approval(ctx, finalize_payload)

    results: list[BatchResult] = []
    async for batch in foreach.dag_batches(
        finalize_payload.tasks,
        depends_on=lambda task: task.depends_on,
        split_oversized=True,
    ):
        batch_result = await execute_task_batch(ctx, batch)
        results.append(batch_result)

        if batch_result.blocked and not batch_result.retryable:
            break

    execute_payload = await merge_execution_results(results)
    if execute_payload.blocked:
        await checkpoint("execution_blocked", execute_payload)
    return execute_payload


@phase(model=model_route("review"), timeout=timeout(minutes=30))
async def review_worker(ctx: MegaplanContext, execute_payload: ExecutePayload) -> ReviewPayload:
    """Single-worker review."""


@phase(model=model_route("review_check", by="check.complexity"))
async def review_check(ctx: MegaplanContext, check: ReviewCheck, execute_payload: ExecutePayload) -> ReviewFinding:
    """One parallel review check."""


@phase
async def merge_review(
    worker_payload: ReviewPayload | None,
    findings: list[ReviewFinding],
) -> ReviewPayload:
    """Merge model review and deterministic/parallel findings."""


@decision(vocabulary={"approved", "needs_rework", "blocked", "human_verify"})
def review_decision(
    ctx: MegaplanContext,
    review_payload: ReviewPayload,
    rework_loop: LoopState,
) -> ReviewDecision:
    if review_payload.deferred_human_musts:
        return "human_verify"
    if review_payload.verdict == "needs_rework" and rework_loop.has_remaining:
        return "needs_rework"
    if review_payload.verdict == "needs_rework" and review_payload.has_blocking_rework:
        return "blocked"
    if review_payload.verdict == "needs_rework":
        return "approved"
    return review_payload.verdict


@subworkflow
async def review(
    ctx: MegaplanContext,
    execute_payload: ExecutePayload,
    rework_loop: LoopState,
) -> tuple[ReviewDecision, ReviewPayload]:
    if ctx.robustness == "extreme":
        findings = await parallel.map(
            ReviewCheck.for_robustness(ctx.robustness),
            lambda check: review_check(ctx, check, execute_payload),
        )
        worker_payload = None
    else:
        findings = []
        worker_payload = await retry(review_worker, attempts=2, retry_on={"infrastructure_failure"})(
            ctx,
            execute_payload,
        )

    payload = await merge_review(worker_payload, findings)
    return review_decision(ctx, payload, rework_loop), payload


@human_gate(capability="human:review-verification", reentry="verify-human")
async def verify_human_criteria(review_payload: ReviewPayload) -> None:
    """Suspend until deferred human criteria are verified."""


@human_gate(capability="human:override", reentry="override")
async def override_control(reason: str, state: object) -> OverrideAction:
    """Human/control-plane intervention: abort, force-proceed, replan, recover, configure."""


@pipeline(name="megaplan-planning-native")
async def planning_native(ctx: MegaplanContext) -> MegaplanResult:
    prep_payload = await prep(ctx)
    if prep_clarification_gate(prep_payload) == "needs_human":
        clarification = await collect_prep_clarification(prep_payload)
        prep_payload = prep_payload.with_clarification(clarification)

    plan_payload = await plan(ctx, prep_payload)

    critique_loop = LoopState(max_iterations=ctx.max_critique_iterations)
    while True:
        critique_payload = await critique(ctx, plan_payload)
        gate_action, gate_payload = await gate(ctx, plan_payload, critique_payload, critique_loop)

        if gate_action in {"proceed", "force_proceed"}:
            break

        if gate_action == "iterate":
            if not critique_loop.can_continue:
                action = await override_control("critique loop exhausted", gate_payload)
                if action.kind == "force-proceed":
                    break
                if action.kind == "abort":
                    return MegaplanResult.aborted(action.reason)
            plan_payload = await revise(ctx, plan_payload, gate_payload)
            critique_loop = critique_loop.next_round(gate_payload)
            continue

        if gate_action == "tiebreaker":
            tb = await tiebreaker(ctx, gate_payload)
            if tb.action == "pick":
                plan_payload = await revise(ctx, plan_payload, gate_payload.with_tiebreaker(tb))
                critique_loop = critique_loop.next_round(gate_payload)
                continue
            if tb.action == "replan":
                plan_payload = await plan(ctx, prep_payload)
                critique_loop = LoopState(max_iterations=ctx.max_critique_iterations)
                continue
            if tb.action == "escalate":
                action = await override_control("tiebreaker escalated", tb)
                if action.kind == "abort":
                    return MegaplanResult.aborted(action.reason)
                if action.kind == "force-proceed":
                    break

        if gate_action in {"escalate", "blocked_preflight", "blocked"}:
            action = await override_control(f"gate {gate_action}", gate_payload)
            if action.kind == "abort":
                return MegaplanResult.aborted(action.reason)
            if action.kind == "replan":
                plan_payload = await plan(ctx, prep_payload)
                critique_loop = LoopState(max_iterations=ctx.max_critique_iterations)
                continue
            if action.kind == "force-proceed":
                break

        if gate_action == "abort":
            return MegaplanResult.aborted("gate aborted")

    try:
        finalize_payload = await finalize(ctx, plan_payload, gate_payload)
    except FinalizeBaselineSelectionError as error:
        fallback_gate = await recover_finalize_baseline_failure(error)
        plan_payload = await revise(ctx, plan_payload, fallback_gate)
        finalize_payload = await finalize(ctx, plan_payload, fallback_gate)

    rework_loop = LoopState(max_iterations=ctx.max_review_rework_cycles)
    while True:
        execute_payload = await execute(ctx, finalize_payload)
        if execute_payload.blocked:
            action = await override_control("execution blocked", execute_payload)
            if action.kind == "recover-blocked":
                continue
            if action.kind == "force-proceed":
                break
            return MegaplanResult.blocked(execute_payload)

        if ctx.robustness in {"bare", "light"} and not execute_payload.requires_human_verify:
            return MegaplanResult.done(execute_payload)

        review_action, review_payload = await review(ctx, execute_payload, rework_loop)

        if review_action == "approved":
            return MegaplanResult.done(review_payload)

        if review_action == "human_verify":
            await verify_human_criteria(review_payload)
            return MegaplanResult.done(review_payload)

        if review_action == "needs_rework":
            finalize_payload = finalize_payload.scope_to_rework(review_payload.rework_items)
            rework_loop = rework_loop.next_round(review_payload)
            continue

        if review_action == "blocked":
            action = await override_control("review blocked", review_payload)
            if action.kind == "force-proceed":
                return MegaplanResult.done(review_payload.force_proceeded())
            if action.kind == "replan":
                # This is a typed multi-level control transfer. It closes the
                # delivery/rework and current planning-cycle ledgers; the
                # enclosing host admits a fresh planning cycle at generation 0.
                await exit_enclosing_loop(
                    target="planning-cycle",
                    outcome="replan",
                    payload=PlanningCycleReplan.from_review(review_payload),
                )
            return MegaplanResult.blocked(review_payload)
```

Important properties of this imagined file:

- There is no route table separate from the product flow.
- The critique loop and review rework loop are visible as loops.
- Human gates are suspension calls with reentry ids.
- Tiebreaker is a subworkflow, not two arbitrary handler names.
- Execute is a dynamic DAG-batch iterator over runtime tasks.
- Gate retry, critique evaluator retry, and review infrastructure retry are policies at the call site.
- Model routing is attached to phases rather than hidden in handler/profile code.
- Edge effects such as debt recording and checkpoints are explicit effects.

The gate vocabulary above is one exact eight-value set shared by its return
type, decorator, implementation, lowering, and every parent handler:
`proceed`, `iterate`, `tiebreaker`, `escalate`, `abort`, `blocked`,
`blocked_preflight`, and `force_proceed`. Gate precedence is likewise part of
the product contract: deterministic preflight rejection, then cap/no-progress
exhaustion, then non-exhausted severity fallback, then the normalized closed
recommendation. “Progress” means a strict decrease in the canonical set of
unresolved blocking-flag IDs between comparable loop generations. A changed
flag description, list order, or non-blocking metadata is not progress;
generations with different admitted flag schemas or scopes require an explicit
comparison/migration rule rather than an ambient heuristic.

Review transport/provider failures never become a `ReviewDecision`. They are
handled by the declared infrastructure retry at the `review_worker` call site;
exhaustion follows its declared lifecycle terminal. Likewise, review-blocked
`replan` is the named enclosing-loop exit described in §5.6: it cannot revise
and finalize inside the delivery loop while bypassing a fresh critique/gate
cycle.

This file is the Stage 1 semantic authority. It is not itself the shared
pattern package. Native Parity must first prove that its authored occurrences,
lowered nodes, accepted Run Authority decisions, Custody histories, WBC
attempt/effect histories, and terminals describe the same run under the
`GOLDEN_TRACE_CONTRACT.md` oracle. Platformization may then extract only the
control structures that have a stable cross-product boundary.

### 5.1 The admitted action envelope

Every authority-increasing action is admitted from one composed envelope. The
identity domains remain related but non-interchangeable:

| Domain | Required coordinates | Owner |
| --- | --- | --- |
| Semantic | Authored path, component instance, loop generation, stable dynamic item key, logical retry generation, reentry generation | Python topology and deterministic lowering |
| Run Authority | Run revision, capability grant/scope, subject attempt, current coordinator fence, accepted decision ID/outcome/CAS when applicable | Run Authority |
| Custody | Exact action/effect/repair target, owner host/process-birth identity, renewable lease, current monotonic epoch | Custody |
| WBC | Boundary ID, exact contract version, execution attempt, parent/child causal joins, required ordered history/evidence | WBC |
| Executable binding | Program/topology digest, call-site-policy digest, normalized applicable product/Plan Contract digest, component contract and implementation digest, installed-artifact digest, component/dependency-lock digest, payload/state schema versions | Compiler, package resolver, admission validator |
| Model/tool invocation | Prompt-template and rendered-input digests or protected refs, model/provider identity, tool-schema set, routing policy, sampling configuration, token/cost budget, memoization/replay key | Product binding under runtime evidence rules |

The positive gate is conjunctive:

```text
current Run Authority grant + current coordinator fence
AND current exact-target Custody lease + current custody epoch
AND applicable exact-version WBC evidence at declared boundaries
AND exact admitted executable/product-contract/model/tool bindings
```

The current grant/fence permits and fences the action. The current lease/epoch
makes one actor the exclusive owner of that exact action. WBC establishes what
has durably crossed required boundaries. Executable bindings prove which code,
policy, component graph, model/tool contract, and package set is about to run.
No single term can substitute for another.

The normalized product-contract digest is required wherever product contract
content can change evidence obligations. For Megaplan this includes semantic
`provides`, `assumes`, and especially `pre_existing` fields. Presentation-only
fields may be explicitly excluded by the canonicalization contract. A mid-run
semantic edit follows the same pin, accepted migration/new-attempt, or
quarantine rule as code and policy drift; it cannot silently waive evidence.

Validation occurs before product body or effect intent. A mismatch yields a
typed rejection, quarantine, or accepted migration/new-attempt path. A WBC
success receipt, a matching path string, a valid old checkpoint, a cached
status, or an extant process never supplies missing permission or custody.

### 5.2 Nesting rules

A nested component is not an in-process helper call with inherited ambient
authority. The component protocol enforces:

1. The authored call site plus stable `instance_key` derives the child semantic
   path. Dynamic children add stable item identity, never list position alone.
2. Parent and child WBC execution attempts are distinct and joined causally.
   Every child execution attempt has one immutable attempt terminal, including
   `retryable_failure`. Retry creates a new attempt generation under the same
   semantic child occurrence. The retry policy eventually accepts one
   immutable aggregate child/component terminal, which the parent consumes
   once by CAS;
   neither an attempt terminal nor that aggregate result is root completion.
3. A parent capability may be narrowed into a child grant, never silently
   widened. Every authority-increasing child action validates its own scoped
   current grant/fence.
4. Custody targets are exact component-instance action/effect/repair targets.
   A broad parent lease does not blanket-authorize child effects. Reused and
   concurrent instances receive disjoint epochs and namespaces unless an
   explicit shared-resource port says otherwise.
5. Parent cancellation, deadline, token/cost budget, retry exhaustion,
   suspension, failure, and compensation propagate only through the declared
   lifecycle rules. A parent retry cannot repeat a child effect with a durable
   terminal outcome.
6. Closed component outcomes must be exhaustively handled by the parent. An
   exception string, handler `next_step`, undeclared effect, or runtime-only
   outcome cannot create a route.

A product-semantic loop cap may deliberately emit a declared business outcome
such as `blocked` when “no acceptable candidate within N product generations”
is part of the component contract and its outcome condition holds. Exhaustion
of a platform resource—deadline, token, cost, call, or infrastructure-retry
budget—remains a lifecycle/control terminal unless the component explicitly
performs a separately declared product decision from durable evidence. Runtime
resource exhaustion must never be relabeled as a convenient business result.

Parent loop state is itself durable composition state. Before admitting a
child, the parent records the loop generation, stable child key, frozen
digest-bound bindings, narrowed capability/deadline/token/cost budgets, and
accumulator version. It consumes one child terminal through CAS, persists the
new accumulator and the typed next/exit decision, and only then admits another
generation. Replay resumes the first incomplete ledger transition.

A retry creates a new execution-attempt generation under the **same semantic
child occurrence** after an accepted retry decision. Earlier attempt terminals
remain immutable, a durable effect outcome is reused rather than repeated, and
the parent still consumes exactly one aggregate child terminal. An explicit
**new child generation** is a new semantic occurrence with a new child key,
authority/custody, and declared repeat policy; it is not another spelling of
retry. Intent-without-outcome reconciles before either path advances.

Cancellation first fences new child admissions, records cancel intent, and
propagates cancellation. Effect ambiguity remains ambiguity: the default
blocks cancellation acceptance until reconciliation. A component may instead
declare `cancelled_pending_reconciliation` as a lifecycle terminal bound to a
durable reconciliation obligation and separate exact Custody target; late
reconciliation may extend history but never rewrite the accepted parent
terminal. The parent follows its declared join/cancellation policy and never
fictionalizes release, child success, effect settlement, or cancellation
completion. If that policy permits parent acceptance after exact-target
Custody expiry without a child aggregate terminal, it retains one typed
`unresolved_child` fact with child/target identity, last epoch and known state,
expiry evidence, and reconciliation obligation. Expiry alone is not resource
settlement.

Human gates are first-class durable components, not special blocking function
calls. A human gate declares its input and answer schemas, required capability,
suspension/reentry ID, and a total typed timeout transition graph. Each timeout
generation either advances to a named escalation/suspension generation, emits
a declared business outcome whose condition holds, or emits a declared
lifecycle terminal. The graph is bounded or has an overall deadline with a
named terminal; it has no implicit `blocked`, `needs_human`, or
`deadline_exhausted` fallback. Suspension writes a checkpoint and WBC event.
Answer-versus-timeout-versus-cancel arbitration is a declared CAS over the
closed participants and policy at that gate. In particular, an accepted but
not yet consumed input racing cancellation cannot be selected by two separate
read/check/write paths: exactly one policy result becomes consumable, while the
non-winning accepted or late fact remains durable with its typed disposition.
The policy may legitimately choose answer or cancellation precedence for that
site; wall-clock arrival or projection order may not choose it. One distinct
winning submission is consumed once, an idempotent replay returns that result,
and a different later answer is retained as `human_answer.rejected_late`
evidence that can never resume or alter the winner. Resume validates schema
and executable pins and reacquires current Run Authority/Custody before the
next product body. An inbox row, approval marker, CLI status, or old lease
cannot resume it.

### 5.3 Checkpoint, resume, and everyday code evolution

A durable checkpoint binds execution state to the version that gave that state
meaning:

| Checkpoint field | Purpose |
| --- | --- |
| Semantic cursor | Exact node/component path plus loop, item, retry, and reentry coordinates |
| Parent/child lineage | Parent cursor and child attempt/instance relationship |
| Four identity domains | Semantic, RA subject/fence, WBC attempt/version, Custody target/epoch |
| Durable component state | Schema-qualified minimal state needed to continue |
| Artifact/payload refs | Content-addressed, schema-qualified refs and hashes for large or sensitive payloads |
| Executable pins | Program/topology, call-site policy, component contract/implementation, installed artifact, dependency lock |
| Product-contract pin | Canonical normalized Plan Contract or other consumer-contract digest wherever it changes evidence/behavior obligations |
| Model/tool pins | Prompt/model/provider/tool/policy identities and budget/memoization coordinates where the next action depends on them |

Checkpoint payloads should be small, canonical, and durable. Large model
outputs, plans, artifacts, transcripts, and external receipts belong in
content-addressed stores; the checkpoint holds typed references, schema
versions, hashes, and retention pins. It must not embed transient handles,
ambient paths, live clients, secrets, unbounded histories, or mutable
projection snapshots.

The user-facing operations around a checkpoint are distinct and must not be
collapsed into one ambiguous "run from here" operation:

| Operation | Identity and meaning |
| --- | --- |
| Resume | Continue the same durable semantic occurrence at its recorded cursor, with compatible executable pins and fresh current admission/Custody. |
| Replay | Reconstruct or verify the recorded execution from durable boundary results; consume recorded model/effect results rather than silently calling or performing them again. |
| Retry | Create a new execution-attempt generation under the same semantic occurrence, through its declared retry policy. |
| Rework | Create a declared new product generation with its own child identity, policy accounting, and admission. |
| Fork | Start new authorized history, with a new run lineage and isolated namespace, using a prior occurrence's admitted inputs/checkpoint state as provenance. |

Changed code can therefore be run immediately as a fresh experiment or fork;
it cannot silently resume or impersonate the admitted occurrence whose state
was produced by the old executable. The shared source path and human idea of
"the same step" are useful grouping labels, not executable identity.

Normal code evolution must account for a run suspended under v1 while v2 is
deployed:

| Observed drift | Allowed disposition |
| --- | --- |
| All pins match | Resume the same semantic occurrence under current RA/Custody |
| v1 installed artifact remains admitted and available | Resume pinned v1; do not silently recompile with v2 |
| Declared compatible state/component migration exists | Accept a typed migration decision, transform once with provenance, create a new subject/WBC attempt, and continue under current custody |
| Policy, topology, WBC, dependency, state, prompt/tool, or implementation change is incompatible | Quarantine or start an explicit new run/attempt; preserve the old history |
| Only a path/name matches | Insufficient; never infer compatibility from spelling |

This is an everyday release discipline, not an edge-case migration project.
Every stable component version needs a checkpoint compatibility statement and
test fixture before publication.

A standing compatibility declaration establishes eligibility, never
permission. Every migration applied to a run or semantic occurrence consumes
one accepted Run Authority migration decision binding the exact from/to
program, policy, component, state, dependency-lock, prompt/tool, Plan Contract,
and WBC versions that apply. The state transform is idempotent and CAS-guarded,
records input/output digests and implementation version, validates current
Custody, and starts the required new subject/WBC attempt. Even automated
policy acceptance produces and consumes this per-run decision; no blanket
compatibility rule silently resumes work.

### 5.4 Effects, model outputs, memoization, and reconciliation

The external-effect sequence is:

```text
validate the complete action envelope
  -> durably record WBC effect intent + exact target + idempotency identity
  -> perform the external action
  -> durably record outcome, or explicit ambiguity
  -> write/rebuild product receipt and projections
  -> reconcile ambiguity under a new current RA/Custody envelope without guessing
```

Current kernel code uses intent/fulfillment/receipt/compensation terminology;
the completed WBC contract adds outcome, ambiguity, and reconciliation. The
mapping must be explicit in the admitted contract version. A durable outcome
followed by a crash before a product receipt means “rebuild the receipt,” not
“repeat the effect.” Intent without a knowable outcome enters reconciliation,
not optimistic success or blind replay.

Cancellation does not resolve an ambiguous effect. The component's declared
policy either waits for reconciliation or accepts the separate
`cancelled_pending_reconciliation` lifecycle disposition described in §5.2,
which transfers the unresolved obligation without terminalizing the effect.
Any later compensation requires a fresh typed decision and current action
envelope.

LLM calls need equally explicit identity even when they do not mutate an
external system. Model output is generally non-repeatable: provider revisions,
sampling, tool availability, and hidden service changes can produce a different
answer. Each invocation records protected prompt/input references or digests,
model/provider, tool schema set, routing/sampling policy, token and cost budget,
attempt identity, and terminal output ref. A pure model invocation therefore
still has one per-call WBC ledger identity and terminal; it is not folded into
an opaque phase log. A retry is a new attempt joined to the same semantic
occurrence; it cannot overwrite the first history.

An agentic phase atomically reserves and charges durable token, cost, time, and
call budgets before every inner model/tool invocation, including retries. No
call starts after exhaustion. A final summary/finalization call is allowed only
from a named reserve declared and admitted at phase entry; unused reserve is
released under the published settlement rule, never by an undeclared hidden
call.

Memoization is allowed only when the component declares it and the cache key
binds every semantic input that the contract says affects the output. A cache
hit is a durable provenance-bearing outcome, not an invisible shortcut.
Replay consumes a recorded terminal output when policy permits; it does not
silently call the model or a tool again. Tool calls with external consequences
also pass through the effect intent/outcome protocol, each with its own exact
effect identity, intent/outcome, and exact Custody target/epoch. A phase-level
lease or WBC attempt cannot blanket-authorize its inner tools.

### 5.5 WBC declaration, evidence, and causal explanation

WBC follows a declaration-to-observation flow, not an authorization flow:

1. Authoring/lowering attaches a named exact-version boundary contract to the
   semantic node, child, reentry, or effect boundary.
2. Admission verifies that the contract version, producer, query adapter,
   executable binding, and controlled writer are the accepted set.
3. Runtime creates a WBC execution attempt joined to the semantic occurrence,
   RA subject attempt/fence, and exact Custody target/epoch.
4. The producer records ordered start, retry, suspend/resume, cancel,
   checkpoint, effect intent/outcome, persistence failure/reconciliation, and
   one terminal as applicable.
5. An evaluator compares the declaration, durable evidence, authority
   decisions, and current reality. A mismatch becomes a typed semantic finding;
   only evaluation of repaired facts clears it.
6. The next action's validator may require specified exact-version boundary
   evidence in addition to current permission and custody. The evidence can
   block or make the boundary indeterminate; it cannot grant the action.
7. Exact-version queries rebuild projections and explanations at declared
   journal/WBC cursors.

The WBC producer registry is governed admission data, not product topology or
route authority. A platform contract may permit adding a versioned producer
entry without changing that platform-contract identity only when its registry
schema says so; admission still pins the exact registry snapshot/entry,
producer executable, query adapter, controlled-writer class, and compatibility
rule. Registry mutation cannot rewrite prior producer identity, weaken a
boundary obligation, or make an unregistered writer authoritative. Native
Parity must capability-probe these registry-evolution semantics against the
accepted M11 revision rather than assuming a locally convenient API.

An accepted RA decision may cite immutable evidence, but the decision and the
evidence are different records. A WBC receipt describes an attempted boundary,
not permission. A projection folds authoritative histories, but is disposable.
The composed explanation may answer “why did this run retry?”, “which owner may
act now?”, “did this effect happen?”, and “which migration is legal?” It may
emit a typed repair request with failed preconditions; it may not dispatch the
repair, choose a route, or change terminal truth.

A repair request is an untrusted proposal. Its cited projection fields and
failed preconditions are hints, not facts. At acceptance, the recovery API
re-reads canonical exact-version journals and current RA/Custody/WBC stores,
recomputes every precondition, accepts or rejects a fresh typed decision, and
runs the normal action validator again immediately before work.

A validator rejection is classified before body/effect intent. Actor-local
placement, stale worker/lease/epoch, or host unavailability may redispatch the
same immutable, unconsumed decision through admitted M11 recovery only while
its canonical validity predicate still holds; the scheduler cannot alter its
route or policy. Changed semantic preconditions, expired capability/grant, or
executable/product/WBC drift atomically record `decision.invalidated` and
require a new typed request and decision. A consumed decision or one whose
body/effect intent began is never redispatched; continuation uses the authored
retry, recovery, or effect-reconciliation protocol with a distinct attempt.

### 5.6 Stage 1 durable-Python boundary

Native Parity needs the following product-proven constructs so ordinary
Megaplan behavior does not leak back into handlers. The agentic boundary is
conditional: Stage 1 implements it only if the current-state inventory proves a
real model-determined inner-call consumer; otherwise Stage 1 freezes its
contract and diagnostic, rejects opaque inner loops, and hands implementation
to experimental Platformization scope:

- **Named enclosing-loop exits.** A typed exit names an enclosing loop and one
  of that loop's declared outcomes. The compiler proves the target is an
  active ancestor loop instance and the parent handles it exhaustively.
  Acceptance terminates that instance rather than implicitly continuing it.
  Every intervening durable control scope records exactly one
  `superseded_by_named_exit` lifecycle terminal in deterministic
  innermost-to-outermost order; the target closes its ledger and emits its
  declared outcome once. A delivery/rework `replan` therefore closes the
  current delivery/rework and planning-cycle instances, then lets the parent
  create a fresh planning-cycle instance at generation zero. Any carried
  accumulator/evidence is named and digest-bound in the exit payload; no
  counter or loop state survives implicitly.
- **Canonical decision values.** Route-bearing decisions consume only
  schema-qualified canonical serialized values. Host-dependent `Path`, wall
  time, mutable identity, arbitrary float behavior, and unordered containers
  are normalized under an explicit schema or rejected. The input digest joins
  the accepted RA decision.
- **Completion-order-independent reducers.** A fanout freezes one admitted
  binding digest for item set, context, policy, prompt/tool bindings, product
  contract, and referenced artifacts. Each child consumes it. Reducers receive
  a canonically keyed multiset of `(declared_item_key, typed_result)` with
  duplicate/missing-key rejection, never completion order.
- **Closed typed phase errors.** Product topology may branch only on declared
  typed error outcomes in the phase port contract. Undeclared exceptions use a
  fixed infrastructure-failure channel and declared retry/recovery policy;
  `except Exception` cannot become an open product outcome vocabulary.
- **Checkpointed typed reconfiguration.** Model/vendor/profile/robustness
  changes accept a schema-versioned delta, checkpoint the current cursor,
  derive new policy/executable/product-contract bindings, and resume that same
  semantic cursor under an explicit reentry generation and current action
  envelope. Ambient context mutation and live route flags are forbidden.
- **Conditional declared durable agentic phase.** Where a proved consumer
  requires it, a model may choose a bounded, runtime
  number of inner tool calls inside one declared phase with typed input, closed
  outer outcomes, named policy/budgets, an explicit WBC attempt/protocol, and a
  durable ordered inner call ledger. Each pure model call retains per-call WBC
  identity; each effectful tool call additionally uses its own effect intent/
  outcome and exact Custody target/epoch. The phase may affect outer topology
  only through a declared closed result/outcome or a declared payload
  discriminant consumed by a declared decision. Undeclared metadata, mutable
  context, exception strings, logs, or helper side channels cannot choose the
  next outer product route.

Open-ended item streams and opaque polling loops are deliberately unsupported
for these stages; diagnostics should point toward a future declared event-queue
port rather than suggesting a handler loop. General all/any/quorum race joins
are Stage 2 composition scope unless a concrete current Megaplan parity path
proves they are product-required. Stage 1 retains only the deterministic joins
its actual topology needs.

## 6. Stage 2 target: contracted, composable workflow components

The Stage 2 snippets below likewise illustrate component semantics, not a
multi-workflow `.py` or `.pype` authoring surface. Every durable workflow shown
would be a canonical workflow in its own `.pype`; shared steps and descriptors
would live in `.py`; ordinary `.py @workflow` remains preview-only.

The platformized representation adds a component boundary around proven
primitives and patterns. A component is not merely an importable callable. It
has a qualified identity, a versioned contract, typed ports, conditioned closed
business outcomes, separate closed lifecycle/control terminals, declared
dependencies and effects, durable-state rules, one standard execution
lifecycle, and a conformance receipt.

The examples in this section are a single coherent sketch of that target. They
are **illustrative API only**. Names such as `ComponentDescriptor`,
`BindingEnvironment`, and `ComponentLock` describe required semantics, not
current Arnold classes.

### 6.1 One reusable contracted subworkflow

The shared package owns review/rework orchestration. It does not know what a
Megaplan plan or an unrelated release candidate means.

```python
# package: arnold_workflow_patterns.review_rework
# Illustrative target API; not a current Arnold import surface.

from arnold.workflow.components import (
    BindingEnvironment,
    BusinessOutcomes,
    ComponentContext,
    ComponentDescriptor,
    EmissionMode,
    EffectSlot,
    LifecycleTerminals,
    OutcomeSpec,
    PolicySlot,
    Port,
    StateSchema,
    component,
)


REVIEW_REWORK = ComponentDescriptor(
    qualified_name="arnold.patterns/review-rework",
    contract_version="1.0",
    kind="subworkflow",
    inputs={
        "candidate": Port.generic("Candidate", durable=True),
        "scope": Port.schema("arnold.patterns/Scope@1"),
    },
    business_outcomes=BusinessOutcomes(
        approved=OutcomeSpec(
            payload=Port.generic("Candidate"),
            condition="review.approved_and_effects_complete@1",
            required_evidence=("review_terminal",),
            emission=EmissionMode.RETURN,
        ),
        blocked=OutcomeSpec(
            payload=Port.schema("arnold.patterns/BlockReason@1"),
            condition="review.blocked_or_cap_exhausted@1",
            required_evidence=("review_terminal", "loop_state"),
            emission=EmissionMode.RETURN,
        ),
    ),
    lifecycle_terminals=LifecycleTerminals(
        "cancelled",
        "deadline_exhausted",
        "budget_exhausted",
        "infrastructure_failed",
        "compensation_failed",
        "contract_violation",
    ),
    policies={
        "rework": PolicySlot.schema("arnold.patterns/ReworkPolicy@1"),
        "review_retry": PolicySlot.schema("arnold.runtime/RetryPolicy@1"),
    },
    effects={
        "review": EffectSlot("Candidate -> ReviewFinding", idempotent=True),
        "revise": EffectSlot("(Candidate, ReviewFinding) -> Candidate"),
    },
    state=StateSchema("arnold.patterns/ReviewReworkState@1", durable=True),
    lifecycle="arnold.component-lifecycle@1",
)


@component(REVIEW_REWORK)
async def review_rework(
    ctx: ComponentContext,
    candidate: Candidate,
    scope: Scope,
    *,
    bindings: BindingEnvironment,
) -> ComponentResult[BusinessOutcome[Candidate, BlockReason], LifecycleTerminal]:
    """Generic bounded review/rework mechanics; no product imports."""

    loop = ctx.bounded_loop(bindings.policy("rework"))
    current = candidate

    async for generation in loop:
        findings = await ctx.invoke_effect(
            bindings.effect("review"),
            current,
            retry=bindings.policy("review_retry"),
        )
        decision = await ctx.accept_typed_decision(findings.action)

        if decision.is_("approved"):
            return ctx.outcome("approved", current)
        if decision.is_("ask_human"):
            answer = await ctx.suspend("review-question", findings.question)
            current = await ctx.resume_with(answer)
            continue
        if decision.is_("blocked") or loop.exhausted:
            return ctx.outcome("blocked", findings.block_reason)

        current = await ctx.invoke_effect(
            bindings.effect("revise"), current, findings
        )

    return ctx.outcome("blocked", BlockReason.cap_exhausted())
```

The descriptor is the reusable contract. The Python body is one conforming
implementation. The lifecycle wraps admission, authority/custody validation,
attempt start, body execution, checkpoint/suspend/retry/effect transitions,
and one local terminal in a fixed protocol.

Business outcomes and lifecycle/control terminals are orthogonal. `approved`
and `blocked` are business results with payload schemas, semantic conditions,
required evidence, and `return` emission mode. Cancellation, deadline/budget
exhaustion, infrastructure failure, and compensation disposition are closed
lifecycle terminals. `contract_violation` is the reserved lifecycle terminal
for a determinately failed component contract; it is not a substitute business
outcome. `ask_human` is an internal decision that causes a durable
`suspend_then_continue` lifecycle transition; it is deliberately **not** also
an exported `needs_human` business outcome. A different component may declare
and return a `needs_human` business outcome, but that has observably different
semantics and must say so in its outcome-condition/emission contract.

A business-outcome proposal freezes one identity, canonical payload, condition
version, evidence references, component/policy versions, and executable
envelope. Its condition is evaluated at the component's local terminal-
acceptance boundary, and the evaluation plus local terminal are accepted by one
idempotent/CAS protocol. Crash/retry consumes the recorded evaluation rather
than recomputing it against changed evidence. A true condition permits the
proposed business result; a determinately false condition accepts
`contract_violation(reason=outcome_condition_failed, attempted_outcome=...)`
and never substitutes another business result. Missing, stale, ambiguous, or
unavailable evidence quarantines/reconciles the proposal until deterministic
evaluation or a declared lifecycle policy resolves it. Parents and root hosts
consume this accepted terminal and provenance; they never re-evaluate the
child's product predicate.

A subworkflow's `approved` is a typed return to its parent, not permission to
accept the root workflow's terminal. Only a root-host adapter may map an
eligible, condition-satisfying local business/lifecycle result to a proposed
root product terminal; that proposal still passes root outcome mapping,
terminal-arbitration CAS, current RA/Custody/WBC validation, and one accepted
root terminal. Nested hosting never invokes the root adapter implicitly.

A root-host adapter has two disjoint, statically typed total maps: every
exported business outcome and every applicable lifecycle/control terminal.
Missing entries, catch-all/default entries, undeclared results, and placing a
nested-only component at root fail composition before authority acquisition.
Many local results may map to one root product terminal, but the accepted root
record retains the original identity, class, and provenance. The mapping only
proposes root truth; it cannot bypass root arbitration or rewrite a lifecycle
terminal as evidence that a business-outcome condition held.

Platformization preserves the Stage 1 root-terminal arbitration role and
accepted root identity. Introducing a reusable root-host adapter may change
the typed source of a terminal proposal and add local-result provenance; it
does not mint a second terminal namespace, replace the admitted arbitration
policy/CAS site, or make an already accepted Stage 1 root terminal eligible for
acceptance again. Any deliberate arbitration-policy or identity migration is a
separate versioned compatibility change with old/new-run and suspended-run
fixtures, never an incidental consequence of component extraction.

### 6.2 Explicit product bindings

Megaplan supplies domain types, policy values, and effect implementations
through a typed binding environment. No shared package imports Megaplan or
looks up product globals.

```python
# package: arnold_pipelines.megaplan

megaplan_review = BindingEnvironment.for_component(REVIEW_REWORK).bind(
    type_arguments={
        "Candidate": "arnold.megaplan/FinalizedPlan@3",
    },
    policies={
        "rework": MegaplanReworkPolicy(max_generations=3, scoped=True),
        "review_retry": RetryPolicy(max_attempts=2, retry_on={"infra"}),
    },
    effects={
        "review": review_finalized_plan,
        "revise": scoped_refinalize_plan,
    },
    capabilities={
        "human:review": megaplan_review_capability,
    },
)


@subworkflow
async def megaplan_delivery_cycle(ctx, finalized_plan):
    execution = await dependency_ready_execute(ctx, finalized_plan.tasks)
    return await ctx.invoke(
        REVIEW_REWORK,
        candidate=execution,
        scope=Scope.from_tasks(finalized_plan.tasks),
        bindings=megaplan_review,
        instance_key="delivery-review",
    )
```

The runtime derives component instance, state, checkpoint, artifact, effect,
and Custody namespaces from the run identity, parent semantic path, qualified
component identity, and explicit `instance_key`. Two invocations do not share
state merely because they call the same Python object. Shared state is possible
only through a declared shared-resource port.

Every authority-increasing component transition uses generated bindings to the
accepted Run Authority, Custody, and WBC protocols. The author declares
semantic identity, capabilities, targets, boundary contracts, and effects;
the platform generates mechanical IDs and validates the current grant/fence,
lease/epoch, exact WBC version, program/policy digest, installed artifact, and
resolved dependency lock before product code or effect intent.

### 6.3 An unrelated consumer

An unrelated release-qualification workflow reuses the same orchestration with
different domain types, policies, effects, and storage. It does not translate
its outcomes into Megaplan vocabulary.

```python
# package: acme_release_qualification

release_review = BindingEnvironment.for_component(REVIEW_REWORK).bind(
    type_arguments={
        "Candidate": "acme.release/BuildCandidate@2",
    },
    policies={
        "rework": ReleaseRepairPolicy(max_generations=1, scoped=False),
        "review_retry": RetryPolicy(max_attempts=4, backoff="exponential"),
    },
    effects={
        "review": run_release_qualification_suite,
        "revise": rebuild_candidate_from_findings,
    },
    capabilities={
        "human:review": release_manager_capability,
    },
)


@pipeline(name="release-qualification")
async def qualify_release(ctx, source_revision: Revision) -> ReleaseOutcome:
    linux, macos = await ctx.fanout_map(
        items={"linux": LinuxTarget(), "macos": MacTarget()},
        item_key=lambda item: item.platform,
        call=lambda target: build_candidate(ctx, source_revision, target),
        reducer=collect_builds,
    )

    # The same component is nested beneath a different product workflow.
    reviews = await ctx.fanout_map(
        items={"linux": linux, "macos": macos},
        item_key=lambda item: item.platform,
        call=lambda build: ctx.invoke(
            REVIEW_REWORK,
            candidate=build,
            scope=Scope.whole_candidate(),
            bindings=release_review,
            instance_key=f"qualification/{build.platform}",
        ),
        reducer=all_platforms_approved,
    )

    return ReleaseOutcome.publishable(reviews)


# Hosting is explicit. This adapter, not the component body, proposes root truth.
release_root_host = RootHostAdapter(
    component=qualify_release,
    business_outcome_map={
        "publishable": "done",
        "rejected": "blocked",
    },
    lifecycle_terminal_map={
        "cancelled": "cancelled",
        "deadline_exhausted": "blocked",
        "budget_exhausted": "blocked",
        "infrastructure_failed": "failed",
        "compensation_failed": "failed",
        "contract_violation": "failed",
    },
    terminal_arbitration="acme.release/terminal-cas@1",
)
```

This is a stronger proof than a neutral toy: the component is nested under a
different root, invoked once per dynamic child, given a different retry/rework
policy, and backed by different effects and durable storage. Stable item keys,
not list positions, keep the two instances isolated. The illustrative adapter
assumes those are the complete declared root result unions; adding another
business or lifecycle result without adding its explicit mapping is a static
error, not a default-to-`failed` route.

### 6.4 One end-to-end component run

Consider the Linux child at
`release-qualification/qualification/linux/review-rework`. This walkthrough
connects the illustrative source to the required runtime facts. Exact class and
event names remain future API; the semantics are normative.

1. **Author and validate.** The developer imports `REVIEW_REWORK`, binds the
   `BuildCandidate@2` type, release policies, review/rebuild effects, and human
   capability, then uses the literal instance key `qualification/linux`.
   Static validation proves all ports and closed outcomes are handled, effects
   and model/tool dependencies are declared, the state is serializable, and
   fanout identity comes from `platform="linux"`. This unrelated product has
   no Megaplan Plan Contract; it supplies its own product inputs. Reusing a
   component does not import Megaplan's `provides`/`assumes` vocabulary.
2. **Lower and lock.** The compiler lowers the source to a generated manifest
   child coordinate and source map. Resolution pins the review/rework contract,
   implementation wheel, transitive dependencies, state schemas, effect
   adapters, prompt/model/tool policy, and conformance receipt. The program and
   dependency-lock digests become admission inputs.
3. **Declare the boundary.** Generated bindings select the exact WBC contract
   for the child invocation and join its execution attempt to the parent Linux
   fanout child. The macOS sibling has a distinct semantic path, WBC attempt,
   state namespace, effect identity, and Custody target.
4. **Admit the action.** Run Authority accepts the scoped decision to review the
   Linux build under the current subject attempt/fence. Custody leases the exact
   `qualification/linux/review` target to one process/host at epoch 7. The
   shared validator checks those current facts, the exact WBC version, and all
   executable bindings before the review body.
5. **Invoke the reviewer.** WBC records the attempt start. The release suite
   records its declared tool/environment identity and output ref. If a consumer
   instead binds an LLM reviewer, that attempt additionally records prompt/input
   refs, model/provider/tool identities, routing/sampling policy, and token/cost
   budget. If an exact declared memoization key hits, cache provenance is
   recorded as the attempt outcome. Otherwise a retry receives a distinct
   attempt identity; it does not erase the first output.
6. **Suspend if needed.** Suppose the internal review decision is
   `ask_human`. This is a lifecycle transition, not a returned business
   outcome. The human-gate component writes a semantic checkpoint and WBC
   suspension record, releases or parks custody according to the admitted
   policy, and exposes a typed question. Its total timeout graph declares each
   escalation generation and final disposition; an answer racing any timeout
   uses the declared CAS. One distinct answer wins, idempotent replay returns
   that result, and another answer is retained as rejected-late evidence. While
   suspended, release-review v1.1 is deployed. Resume uses pinned v1 if
   available, or one declared per-run accepted state-migration decision; it
   never resumes against v1.1 merely because the source path is unchanged. The
   new host reacquires current RA/Custody before continuing.
7. **Perform rework safely.** Rebuilding the release candidate is a declared
   effect. The runtime validates the action envelope, durably writes intent,
   invokes the builder, and records its outcome. If the process crashes before
   the product receipt, a new owner at epoch 8 reconciles the durable outcome
   and rebuilds the receipt without rerunning the build. Intent without a known
   outcome enters ambiguity handling.
8. **Return and reduce.** At local terminal acceptance, the child atomically
   records the pinned outcome-condition evaluation and the closed
   `approved(BuildCandidate)` terminal. A false predicate yields the reserved
   contract-violation lifecycle terminal; a crash reuses the recorded
   evaluation. The accepted parent reducer waits for the exact Linux/macOS
   aggregate-child multiset. Child approval does not directly accept the
   release root terminal. Only `release_root_host` may map a condition-
   satisfying `publishable` business result or declared lifecycle terminal to
   a proposed product terminal, preserving source class and provenance and
   still passing the root accepted-decision and terminal-arbitration boundary.
9. **Explain.** Generic queries join semantic occurrence, accepted decisions,
   historical/current fences and epochs, WBC attempts/effects, checkpoint
   versions, and package/model bindings. A projection can explain “Linux was
   approved after one migrated human suspension and a reconciled rebuild at
   epoch 8.” Deleting and rebuilding that projection changes no action.

The same history is useful from two perspectives:

| Developer sees | Operator sees |
| --- | --- |
| Source call site, typed bindings, closed outcomes, stable item/instance key, declared policy/effects | Accepted RA decision/fence, exact current Custody target/epoch, WBC attempt/effect history, executable pins, checkpoint disposition |
| Static diagnostics and source-mapped normalized trace | Causal explanation, ambiguity, rejected stale actions, legal typed repair/migration requests |
| Local phase/effect fakes and human-gate fast-forward | No direct edit surface that can advance the run |

### 6.5 Shape-independent recomposition

Supported composition shapes have defined control-propagation rules. The same
contract may be called sequentially, nested under another subworkflow, placed
in a bounded loop, or mapped over dynamic children without changing its local
lifecycle semantics:

```python
# Sequential: two distinct namespaces and two explicit outcomes.
design = await ctx.invoke(
    REVIEW_REWORK, candidate=draft, scope=design_scope,
    bindings=design_review, instance_key="design",
)
implementation = await ctx.invoke(
    REVIEW_REWORK, candidate=build(design), scope=implementation_scope,
    bindings=implementation_review, instance_key="implementation",
)

# Nested loop: parent policy decides whether to invoke a new child generation.
async for generation in ctx.bounded_loop(release_candidate_policy):
    result = await ctx.invoke(
        REVIEW_REWORK, candidate=candidate, scope=release_scope,
        bindings=release_review, instance_key=f"candidate/{generation}",
    )
    if result.is_("approved"):
        break
    candidate = await parent_level_rebuild(result)

# Fanout: sibling wall-clock order may vary; identities and multiplicity may not.
results = await ctx.fanout_map(
    items=targets,
    item_key=lambda target: target.stable_id,
    call=lambda target: ctx.invoke(
        REVIEW_REWORK, candidate=target.candidate, scope=target.scope,
        bindings=release_review, instance_key=f"target/{target.stable_id}",
    ),
    reducer=collect_outcomes,
)
```

The component protocol, rather than incidental Python exception behavior,
defines parent cancellation, deadline narrowing, retry scope, sibling failure,
suspension, checkpoint nesting, compensation scope, and typed-outcome
propagation. A parent retry cannot silently repeat a child effect with a
terminal outcome. A child terminal cannot silently terminate the root.

Stage 2 fanout uses a closed `JoinPolicy`, not scheduler timing. The policy is
typed against the exact closed union of child business outcomes and applicable
lifecycle/control terminals. It classifies every member as qualifying,
tolerated non-qualifying, fatal, or another named closed category; defaults are
forbidden. Any payload predicate is canonical and versioned. The policy names
the exact parent result both when its target succeeds and when success becomes
impossible, preserving the business-versus-lifecycle result class:

| Policy | Completion rule | Required loser/late behavior |
| --- | --- | --- |
| `all` | Every admitted child produces a result classified as satisfying the declared all-condition | Fatal/tolerated results, partial results, and the exact unsatisfiable parent result are declared |
| `any` | First accepted explicitly qualifying result wins arbitration | Remaining children receive declared cancellation; completed effects remain history; late results are retained under declared non-winning dispositions |
| `quorum(k)` | `k` results classified by the versioned qualifying predicate satisfy the threshold | Impossibility result, tie precedence, loser cancellation, and late qualifying-result disposition are declared |
| `reducer_threshold` | Canonical keyed reducer emits a declared threshold result | Complete result classification and unsatisfiable result are declared; inputs ignore completion order and preserve exact multiplicity |

Threshold reached, parent cancel, deadline, budget exhaustion, and child
failure all compete through one declared CAS/arbitration order. Parent
completion waits for the policy-required aggregate child result and declared
Custody/resource dispositions; it cannot erase rejected-late facts, completed
effects, or an `unresolved_child` disposition. A lifecycle terminal never
counts as success merely because it is accepted unless the typed policy
explicitly and validly classifies it that way. Omitted child categories,
missing unsatisfiable results, or default/catch-all handling fail composition.

Child resource contexts are narrowed, never widened. Each resource class has a
durable ledger covering reservation, committed charge, unresolved liability,
released/refunded amount, and the resource-specific proof that no further
charge can accrue. At every observable event:

```text
committed charges + unresolved liabilities + live worst-case reservations
  <= admitted parent budget
```

Sending cancellation never releases capacity by itself. Settlement may be an
accepted settled child terminal, provider-confirmed cancellation/fence, or
reconciled final usage record according to the declared resource class.
Custody expiry alone does not settle token, money, tool, or external-effect
liability; unsettled exposure remains reserved or becomes an explicit
liability until reconciliation. A worker/concurrency slot may use expiry only
where its provider contract proves that is settlement. Refunds are durable
ledger events, never inferred from absence of an outcome.

### 6.6 Deterministic resolution, validation, and substitution

Import success is not resolution proof. The complete program is validated and
locked before authority is acquired:

```python
requirements = ComponentRequirements(
    root="acme.release/qualification@2",
    components={
        "arnold.patterns/review-rework": "~=1.2",
        "arnold.patterns/dependency-ready-execute": "^2.0",
    },
)

lock = ComponentLock.resolve(
    requirements,
    registry=trusted_pattern_registry,
    require_conformance=True,
)

validated = validate_composition(
    qualify_release,
    bindings=[release_review],
    lock=lock,
)
validated.raise_for_errors()  # before Run Authority or Custody acquisition

await run(
    qualify_release,
    component_lock=lock,
    program_digest=validated.program_digest,
)
```

The content-addressed lock identifies each package, component contract,
implementation digest, transitive dependency, and conformance receipt. It is
included in program/checkpoint identity. Conflicts, missing components,
unhandled outcomes, undeclared effects, illegal nesting, namespace collisions,
and incompatible durable-state schemas fail before product work.

A compatible implementation or version is substitutable only after black-box
conformance, not because it has the same import name. Certification makes two
separate claims:

```python
candidate_lock = lock.replace(
    component="arnold.patterns/review-rework",
    implementation="arnold.patterns/review-rework-fast@1.3.1",
)

assert_new_instance_compatible(
    contract=REVIEW_REWORK,
    baseline_lock=lock,
    candidate_lock=candidate_lock,
    suites=[
        lifecycle_suite,
        recomposition_suite,
        isolation_suite,
        authority_custody_wbc_suite,
        fault_and_effect_suite,
        partial_order_trace_suite,
    ],
)

assert_resume_compatible(
    contract=REVIEW_REWORK,
    baseline_lock=lock,
    candidate_lock=candidate_lock,
    checkpoint_migrations=[review_rework_v1_to_v1_3],
    suites=[checkpoint_upgrade_suite, effect_reuse_suite],
)
```

`new_instance_compatible` allows the candidate to host newly admitted
instances. It does not authorize the candidate to resume an existing suspended
instance. `resume_compatible` additionally proves identical durable
state/checkpoint/effect semantics or one admitted provenance-bearing migration.
Without that stronger receipt, the original implementation remains pinned or
the run quarantines/restarts explicitly.

Allowed implementation differences, such as sibling scheduling or physical
storage, remain outside the observable contract. Ports, typed outcomes,
lifecycle events, causal decisions, effects, checkpoints, and terminal facts
must remain compatible.

Trace equivalence is normalized partial-order equivalence, not sorted log
equality. It preserves exact event multiplicity, total order within each
component/effect attempt, declared parent/child/effect happens-before edges,
accepted and rejected arbitration facts, and explicitly allowed unordered
sibling sets. Normalization may remove approved volatile fields; it may not
deduplicate events, reverse causality, hide late results, or sort away an
illegal race.

Every portable trace-schema version owns a content-addressed field table that
classifies each observable field as exact, canonically transformed,
relationally compared, or ignorable volatile. The table is part of the golden/
conformance contract and receipt, never comparator-local configuration;
unknown fields fail comparison. Relational host/process values may be
pseudonymized only while preserving equality and change relations. Each raw
event retains source-store identity, cursor, schema version, and raw payload
digest, and every normalized event retains its source-event reference. Raw
identity and multiplicity are verified before normalization; folding,
deduplication, and one-to-many synthesis are forbidden for the lifecycle
vocabulary except for an explicit versioned conservation mapping retaining all
source IDs.

## 7. Required top-level constructs

| Construct | Why Megaplan needs it | Exists today? | Evidence |
| --- | --- | --- | --- |
| Sequential durable phases | All major steps need checkpointed phase calls. | Yes. | `@phase` in `arnold/pipeline/native/decorators.py:16`; runtime in `arnold/pipeline/native/runtime.py:198`. |
| Native pipeline functions | Top-level product flow should be a Python function. | Yes, partially. | `@pipeline` in `arnold/pipeline/native/decorators.py:59`; `compile_pipeline()` in `arnold/pipeline/native/compiler.py:53`. |
| Decisions / branches | Gate, review, prep, tiebreaker, override. | Yes. | `@decision` in `arnold/pipeline/native/decorators.py:93`; branch pattern in `arnold/patterns/control.py:33`. |
| Human suspension | Prep clarification, tiebreaker decide, review human verification, override. | Yes. | Human gate metadata in `@decision` (`arnold/pipeline/native/decorators.py:93`); generic `human_gate()` in `arnold/patterns/control.py:230`; `SuspensionRoute` in `arnold/manifest/manifests.py:216`. |
| Bounded loops | Critique/gate/revise and review/rework need caps. | Yes, but awkward. | `LoopPolicy` in `arnold/manifest/manifests.py:87`; loop pattern in `arnold/patterns/control.py:70`; current `revise` loop in `planning.py:191`. |
| While-until predicates | Loop should stop on gate pass, cap, no progress, or severity branch. | Partial. | `LoopPolicy.until_ref` exists (`arnold/manifest/manifests.py:91`), but source compiler only accepts `while True` with literal policy (`arnold/workflow/source_compiler.py:1451`). |
| Break / continue or typed loop outcomes | Native Megaplan wants ordinary loop control. | Missing in compiler subsets. | Source compiler rejects break/continue (`arnold/workflow/source_compiler.py:1525`); native compiler also rejects them (`arnold/pipeline/native/compiler.py:659`). |
| Static parallel fanout | Fixed review panels and fixed critique panels. | Yes. | `parallel()` in `arnold/pipeline/native/decorators.py:177`; `fanout()`/`panel()` in `arnold/patterns/control.py:105`. |
| Dynamic parallel map over runtime lists | Critique selected lenses, finalize task batches, review checks. | Missing at source level. | Dynamic fanout exists as imperative runtime machinery, but native `parallel()` requires literal branches (`arnold/pipeline/native/decorators.py:177`). |
| Fan-in / reducer | Merge critique, tiebreaker, review, execution results. | Yes. | Reducer support on `parallel()` (`arnold/pipeline/native/decorators.py:180`); `FanoutPolicy.reducer_ref` (`arnold/manifest/manifests.py:96`). |
| Subworkflow invocation | Critique, gate, tiebreaker, execute, review should be nested workflows. | Yes, manifest-level. | `subpipeline()` in `arnold/patterns/base.py:112`; `SubpipelineRef` in `arnold/manifest/manifests.py:208`. |
| Retry policy at call site | Critique evaluator, gate reprompt, review infrastructure, external failures. | Partial. | `RetryPolicy` in `arnold/manifest/manifests.py:78`; `retry()` pattern in `arnold/patterns/control.py:185`; no source-level phase-call retry keyword. |
| Timeout/deadline policy | Phase timeouts, stale/dead process detection, auto-drive phase timeout. | Partial. | `TimingPolicy` in `arnold/manifest/manifests.py:154`; phase runtime policy exists in `_core/phase_runtime.py`; not ergonomic at native call site. |
| Event-driven transitions | Override, resume, cancel, pause, recovery, auto-drive liveness events. | Partial. | `ControlTransitionSlot` in `arnold/manifest/manifests.py:173`; planning graph uses slots at `planning.py:141`; source-level event syntax remains limited. |
| Topology overlays | Runtime route mutations or control overlays. | Exists as metadata slot. | `TopologyOverlaySlot` in `arnold/manifest/manifests.py:185`; `_node_policy()` accepts overlays in `planning.py:21`. |
| Model routing | Tiered model choice by phase, task complexity, robustness, vendor overrides. | Missing from workflow manifest. | Agent-level routing exists elsewhere, but no first-class workflow policy slot was found. |
| Edge effects / compensation | Gate debt recording, checkpoints, failure events, state recovery. | Partial. | Effect/compensation policy slots exist in `arnold/manifest/manifests.py:113`, but current Megaplan side effects remain handler code. |
| Resume cursors | Human gates and long-running loops need durable resume. | Exists. | Suspension route support and native runtime resume support; current graph uses reentry ids in `planning.py:194` and `planning.py:219`. |
| Dynamic DAG scheduling | Execute tasks need dependency-aware batching over finalized runtime data. | Missing at source/topology level. | Current implementation is inside `execute/batch.py:2278`. |
| Closed typed outcomes | Parents must exhaustively handle every route-bearing result; handlers cannot invent outcomes. | Partial. | Decision vocabularies and V2 diagnostics exist, but a universal component lifecycle/outcome checker is Stage 2 scope. |
| Declared effect and model/tool dependencies | Static validation, replay, cost control, and reconciliation require complete declarations. | Partial. | Manifest effect slots and agent routing exist in separate planes; full component/action-envelope identity is not universal. |
| Source-mapped diagnostics and debugger | Restricted Python is usable only when compiler/runtime facts map back to authored lines and component paths. | Partial. | V2 authoring diagnostics and provenance exist in `python-shaped-authoring-contract.md`; one cross-runtime debugger is missing. |
| Fast deterministic local harness | Authors need to test topology without cloud workers, real effects, or waiting for humans. | Missing as one standard surface. | Existing unit/golden fixtures are useful precedent; Platformization must define a component-level harness. |

### 7.1 Authoring, diagnostics, and local test ergonomics

A restricted Python subset creates pressure for escape hatches. If the
compiler says only “unsupported syntax,” authors will move route logic into a
handler, helper, metadata table, or opaque exception—the exact relapse Native
Parity is meant to eliminate. The authoring experience is therefore part of
semantic safety.

Diagnostics should identify the authored source span and normalized component
path, explain which deterministic construct replaces the rejected Python, and
show the relevant lowered manifest/IR node, policy, effect, and closed outcome.
A source-mapped debugger should let an author inspect:

- the current semantic occurrence and parent/child stack;
- bound typed inputs and outcome vocabulary;
- effective policy and its source/precedence;
- remaining retry, loop, token, cost, and deadline budgets;
- declared effect intents/outcomes and model/tool attempt identity;
- the platform agent session, model/tool calls, usage/cost and protected
  log/transcript artifacts for the exact workflow/step attempt, with reverse
  navigation to owning source and any consuming decision/terminal;
- checkpoint and suspension cursor;
- the next legal transitions and why an illegal one was rejected.

The default local test harness should be fast and deterministic. It should
compile the same source and component lock used in production, but allow:

- pure phase fakes with schema-checked outputs;
- effect fakes that exercise intent/outcome/ambiguity without external writes;
- deterministic model outputs, token/cost accounting, memoization hits, and
  non-repeatable-output replay fixtures;
- virtual time and deterministic fanout schedules;
- human-gate fast-forward with typed answers and cross-version resume cases;
- crash injection at every lifecycle boundary;
- normalized trace and source-map assertions.

These fakes must satisfy the same declared contracts and emit the same shape of
lifecycle evidence. A special test runner that bypasses admission, effects, or
resume rules would create false confidence.

The DX safety gates are measurable:

1. **No payload route smuggling.** Non-discriminant payload fields on an
   existing outcome are mutated across the golden corpus and cannot change a
   route. Every observed route divergence is attributable to a declared
   outcome/decision discriminant and canonical decision-input digest.
2. **Every diagnostic has a disposition.** One hundred percent of registered
   rejection codes map to a supported primitive/example or an explicit
   deliberately-unsupported boundary recipe, with expected source span and
   semantic path. A timed ten-task author simulation exercises representative
   legal/illegal edits and records completion and error rates.
3. **Faithful fast local loop.** Every golden family, including race variants,
   produces the same normalized lifecycle/admission partial-order trace locally
   and from the installed artifact when given the same recorded boundary
   results. Compile and no-network local-test p50/p95 budgets are selected from
   a checked-in machine/corpus baseline, frozen in the S1 receipt, and enforced
   thereafter; the report does not guess the numbers.

Local speed never substitutes for installed, cross-host, or cloud release
proof. It makes the safe path the convenient path.

### 7.2 Execution modes and enforcement dispositions

The platform must be strict about the claims an execution makes, not hostile
to experimentation. Editing one step and running it repeatedly against the
same fixture should be an ordinary inner-loop operation. The runtime derives a
new executable digest and fresh experiment/run-or-attempt identity, isolates
state, artifacts, authority and evidence, and invalidates semantic caches as
needed. The author should not have to declare a production migration merely to
try changed working-tree code.

Execution mode determines which claims the result may make:

| Mode | Permitted behavior and claim |
| --- | --- |
| Local authoring / non-durable preview (`authoring_preview`) | Run working-tree code, fixtures, fakes, breakpoints, and repeated trials quickly. Supported deterministic source may use the faithful local harness. Unsupported Python may run only in a conspicuously labelled non-durable preview that makes no resume, replay, conformance, certification, or admitted-evidence claim. |
| Durable sandbox experiment (`durable_sandbox`) | Exercise checkpoints, WBC lifecycle, suspension, crash, retry, and fork semantics with experimental pins and isolated non-production identity. Effects default to fakes or sandbox adapters; any real sandbox target is explicit. |
| Non-authoritative shadow / comparison (`comparison`) | Evaluate candidate code against recorded or duplicated inputs and retain quarantined comparison evidence. It is non-resumable, cannot acquire admitted product authority, and cannot emit admitted effects or terminals. |
| Admitted production (`admitted_production`) | Require exact source/manifest, contract, policy, dependency, state, product, and model/tool pins plus current RA, Custody, WBC and effect protocols. Changed incompatible code uses an explicit migration or a new run/fork; it never impersonates an existing occurrence. |
| Stable certification / publication (`certification`) | Additionally require compatibility statements, clean-install and conformance receipts, supported composition profiles, documentation/DX gates, and the required unrelated-consumer evidence before making stable reuse claims. |

The developer surface may look like the following; the exact API spelling is
illustrative rather than a frozen Stage 2 interface:

```python
fixture = testkit.from_run(
    run_id="R42",
    occurrence="delivery/review/task-T17",
)

trials = await testkit.repeat(
    review_step,
    fixture=fixture,
    attempts=10,
    code="working-tree",
    effects="fake",
)

experiment = await testkit.fork(
    run_id="R42",
    from_occurrence="delivery/review/task-T17",
    code="working-tree",
    effects="sandbox",
)
```

Each trial remains recognizably the same component to the author while having
a distinct experimental attempt identity. The fork records provenance from
`R42` but creates new history; neither operation mutates or resumes `R42`.
Production effect adapters, production idempotency keys, admitted RA/Custody
records, and canonical production journals must be unreachable from these
defaults. Enabling a real sandbox effect requires an explicit target binding
and still cannot reuse a production effect identity.

Every restriction must have one declared enforcement disposition:

| Disposition | Examples |
| --- | --- |
| Always-hard safety invariant (`always_hard`) | No production effect leakage, evidence-as-authority, namespace collision, executable impersonation, or admitted-history mutation. |
| Automatically derived identity/versioning (`automatic`) | Executable digests, fresh experiment identities, isolated namespaces, fork lineage, and cache invalidation follow mechanically from inputs and bindings. |
| Production/admission gate (`production_admission_gate`) | Deterministic supported subset, exact pins, authority/Custody/WBC validation, effect protocol, migration compatibility, and production-store arbitration. |
| Stable-publication gate (`stable_publication_gate`) | Clean-install resolution, compatibility/conformance profiles, second-consumer proof where required, stable docs/examples, and publication SLOs. |
| Authoring advisory (`authoring_advisory`) | Suggested granularity, complexity, naming, candidate reuse classification, documentation completeness, and performance before an SLO is published. |
| Non-durable-preview-only (`non_durable_only`) | Unsupported or nondeterministic Python may execute for exploration only, with an unavoidable marker that the result cannot resume, replay, certify, publish, or enter admitted evidence. |

Diagnostics must name both the violated rule and its disposition. In
particular, "unsupported for durable execution" should offer non-durable
preview or a supported typed-primitive recipe instead of needlessly preventing
the author from running the code at all. Conversely, changing the mode must
never downgrade an always-hard isolation or effect-safety invariant.

## 8. Gap analysis

### What exists today and can be reused

The Arnold native/pipeline substrate already has a credible base:

- lightweight decorators for phases, pipelines, decisions, fixed parallel blocks, and panels (`arnold/pipeline/native/decorators.py:16`);
- AST compilation into native IR (`arnold/pipeline/native/compiler.py:53`);
- native runtime execution (`arnold/pipeline/native/runtime.py:198`);
- graph projection for compatibility and topology hashing (`arnold/pipeline/native/graph_projection.py:124`);
- policy dataclasses for retry, loop, fanout, timing, control transitions, subpipelines, suspension, and topology overlays (`arnold/manifest/manifests.py:78`);
- control pattern constructors for branch, loop, fanout, panel, retry, and human gates (`arnold/patterns/control.py:33`);
- subpipeline references (`arnold/patterns/base.py:112`);
- existing native-first packages such as `arnold/pipelines/folder_audit/native.py` and `arnold/pipelines/deliberation/native.py`.

The current `planning.py` already uses some of the manifest-level policy slots:

- gate control transitions and suspension routes (`arnold_pipelines/megaplan/workflows/planning.py:141`);
- revise loop policy (`arnold_pipelines/megaplan/workflows/planning.py:191`);
- tiebreaker decision loop and transitions (`arnold_pipelines/megaplan/workflows/planning.py:216`);
- review human suspension and control transitions (`arnold_pipelines/megaplan/workflows/planning.py:269`).

This means the migration does not require inventing a runtime from nothing. It requires raising the abstraction from explicit nodes plus opaque handlers to native call-site constructs.

### What is missing or too constrained

The biggest gap is dynamic runtime topology.

Megaplan does not know all critique checks, review checks, task batches, or tiebreaker shape as static literal branches at import time. The current native `parallel()` helper requires a literal list/tuple of `@phase` callables (`arnold/pipeline/native/decorators.py:177`). That works for deliberation-style fixed panels; it is not enough for Megaplan's runtime lists.

The second gap is loop expressiveness.

Both current source/compiler subsets treat loops as bounded control constructs, not ordinary Python loops:

- the source compiler requires `while True` with an adjacent literal loop policy (`arnold/workflow/source_compiler.py:1451`);
- it rejects `break` and `continue` (`arnold/workflow/source_compiler.py:1525`);
- the native compiler also rejects `break` and `continue` inside while (`arnold/pipeline/native/compiler.py:659`).

Megaplan wants loops with semantic exits:

- gate passed;
- gate said iterate;
- tiebreaker requested replan;
- cap exhausted with critical flags;
- cap exhausted with cosmetic-only flags;
- review approved;
- review asked for rework;
- review cap exhausted with blockers;
- review cap exhausted with advisory-only items.

Those can be represented without raw Python `break`/`continue` if the runtime supports typed loop outcomes, but they need a first-class form.

The third gap is policy at the phase call site.

Retries, timeouts, model routing, vendor fallback, human authority, and edge effects exist in scattered forms, but Megaplan authors need to be able to write something like:

```python
payload = await retry(gate_worker, attempts=1, on_still_blocked="iterate")(ctx, signals)
findings = await parallel_map(checks, critique_lens, model_route=lambda check: check.tier)
await effect("record_gate_debt", when=gate_action == "proceed")
```

Today, much of that remains inside handlers or profile/runtime code.

The fourth gap is event/control-plane clarity.

Override actions are real product edges. They should not be opaque action strings consumed by one handler. At minimum, the native representation should make these routes visible:

- abort -> terminal aborted;
- force-proceed -> finalize or done depending context;
- replan -> planning loop;
- resume-clarify -> prep/prepped;
- recover-blocked -> execute resume;
- set-model/vendor/profile/robustness -> configuration effect, then re-enter current phase.

### Post-Native-Parity standardization gap

Completing the four source/runtime gaps above produces a correct native
Megaplan, but it does not by itself produce a reusable component platform. The
remaining platform gap is a missing normative boundary contract:

- one exact-one `.pype` authoring/linking model, including canonical imports,
  private local definitions, shared `.py` leaves, package-owned optional
  default selection, path-independent identity/migrations, import provenance,
  and cycle/recursion/collision rejection without executing author source;
- ordinary Python/third-party import freedom inside shared step bodies under
  exact dependency/environment/feature/plugin pins and declared effect
  boundaries;
- one execution lifecycle for steps and workflows, including workflows hosted
  as subworkflows;
- composition rules for ports, typed outcomes, retry, suspension,
  cancellation, deadline, failure, compensation, and terminal propagation;
- durable state, checkpoint, artifact, identity, effect, and namespace
  isolation for multiple component instances;
- one immutable typed policy envelope with kind/schema, canonical values,
  attachment, provenance, precedence/override and digest, plus explicit
  dependency/effect/capability binding and no ambient mutable route authority;
- canonical serialized port/outcome/state compatibility rather than Python
  annotations alone;
- qualified component identity, content-addressed transitive dependency locks,
  mixed-version rejection, and active-checkpoint evolution rules;
- generic static composition validation;
- portable causal evidence with bidirectional occurrence/attempt ↔
  agent/model/tool/effect/cost/log-artifact joins, rebuildable indexes, and
  black-box conformance certification;
- one source-mapped diagnostic/debugging model and fast deterministic local
  harness across manifest/native execution planes;
- complete prompt/model/tool identity, budget, memoization, replay, and
  non-repeatable-output semantics.

These are not reasons to inflate Native Parity. They are the explicit scope of
the dependent Platformization stage after the first product implementation is
correct.

The principal social/technical risk is **handler relapse**. When the restricted
subset cannot express a legitimate construct or produces poor diagnostics,
authors will be tempted to hide control in helpers, handler returns, metadata,
CLI/auto logic, or exception strings. The platform must respond by either
adding one deterministic, typed primitive with compiler/runtime/conformance
support or rejecting the design clearly. It must not create an untracked
“escape hatch” whose return value becomes route authority.

### Six distinct reuse claims

The platform must report these independently:

| Claim | Meaning | Required proof |
| --- | --- | --- |
| Source reuse | Two products call the same implementation | No copied implementation and no product reverse import |
| Clean-wheel reuse | Independently installed packages can import and execute it | Clean build/install/run for both consumers |
| Deterministic resolution | Every worker selects the same qualified component and transitive dependency graph | Content-addressed lock, provenance, and mixed/conflict failures |
| Shape-independent reuse | Supported nesting, fanout, loop, retry, suspension, and cancellation shapes preserve the component contract | Recomposition and isolation matrix |
| New-instance behavioral substitutability | A compatible implementation/version can host newly admitted instances | Shared black-box lifecycle, outcome-condition, partial-order trace, fault, and effect conformance |
| Resume compatibility | A compatible implementation/version can continue an existing durable instance | Identical durable semantics or admitted checkpoint/state/effect migration, independently certified |

A second consumer is decisive evidence against Megaplan coupling, but it is not
alone sufficient evidence for the last four claims.

## 9. Two-stage implementation recommendation

### 9.1 Stage 1 — execute Native Parity as the load-bearing migration

Follow `megaplan-native-parity-corrective-plan.md`, not the older idea of a
trace-only native shadow as a finish line. A shadow may be used only for
behaviorally inert comparison during a gated cutover.

The work should:

1. bind the accepted completed Custody Control Plane artifacts, pass executable
   M11 capability probes, and freeze the semantic, identity, trace, durable-
   store ownership, and proof model;
2. implement product-neutral typed decisions/outcomes, bounded loops, dynamic
   map/reducer, retry/fallback, human reentry, checkpoints, and call-site policy;
3. migrate prep, critique, gate, revise, tiebreaker, finalize, execute, review,
   rework, override, recovery, effects, and terminal arbitration into the
   canonical source;
4. reduce handlers to pure phase bodies and make components, manifests,
   `_core`, CLI, auto-drive, WBC queries, and projections downstream only;
5. prove the six golden scenario families through an independent static-source
   oracle and raw-level verifier, negative mutations, installed/cloud parity,
   stale-worker rejection, no-dual-write effects, and composed causal
   explanation from one same-run history.

Before the product chain starts, the one-milestone
`megaplan-chain-milestone-gates` bootstrap must add content-addressed
intermediate gates that run before merge and rebind their result to merge HEAD.
It also adds the only legal authority-changing lifecycle: readiness validation
on merge HEAD → declared typed receipt-consuming transition → independent
post-transition verification. The bootstrap itself is certified from an
externally reviewed, CI-verified, manually merged implementation attestation;
it cannot self-authorize through the old local/no-PR runner.
The Native Parity chain then has ten busy milestones. `S2` is split between the
authoring-format/compiler proof and the durable runtime substrate; `S3` is split
at the critique/gate boundary; and `S5` separates non-authoritative, per-effect-
class proof from the first live delivery cutover:

| Ordinal | Milestone | Blocking scope |
| --- | --- | --- |
| 1 | `s1-custody-admission-semantic-preservation` | Executable M11 probes; staged `.pypeline` → `.pype` inventory while the current authoring path remains selected; exact-one format/identity contract and expected-red corpus; identities/rows; durable-store ownership; independent golden/source-oracle and raw mutation contracts. Production runtime integration is deferred. |
| 2 | `s2f-pype-compiler-identity-converter` | Exact-one compiler/linker, converter, conservative executable-closure identity, descriptor/package correspondence, minimal preview and exact-pinned legacy proof; readiness validation, receipt-consuming suffix/admission transition, post-transition **GO-FORMAT**. |
| 3 | `s2r-durable-control-primitives-custody-binding` | Generic durable constructs, neutral runtime, all-plane admission adapter, independent trace integration, store-capability enforcement and restore drills; reconsume GO-FORMAT and close **GO-0**. |
| 4 | `s3a-prep-plan-critique-native-cutover` | Digest-bound execution-plane selection and shared resume gate; land producer relocation and typed legacy-gate seam non-authoritatively; readiness → typed transition → post-transition **GO-1A**. |
| 5 | `s3b-gate-revise-front-half-cutover` | Gate/revise/planning cycle, finite named route discriminants and schema-change comparability; transition producer/seam/fence ownership, then verify remaining front-carrier/scaffold removal; `NP-GT-001/002`; post-transition **GO-1B**, closing GO-1. |
| 6 | `s4-tiebreaker-finalize-durable-reentry` | Per-run migration decisions and duplicate-human arbitration; keep the old path/seam authoritative through merge; readiness → atomic typed producer/seam/fence transition → post-transition verification; `NP-GT-003`. |
| 7 | `s5a-delivery-shadow-effect-class-proof` | Build execute/review/rework topology in non-authoritative shadow mode; make the complete future-live `NP-GT-004/005` behavior matrix green; inventory every external-effect protocol class and prove each class directly or through an independently accepted equivalence; close **GO-2** without live effects. |
| 8 | `s5b-live-delivery-cutover-review-rework` | Validate current readiness, then make one typed live-delivery transition consuming both that receipt and S5A GO-2; post-verify writer fences, named-exit unwind, cancellation/effect ambiguity, review/rework and reconciliation; `NP-GT-004/005`. |
| 9 | `s6-override-auto-control-adoption` | Validate GO-3 readiness, transition control authority once, then post-verify repair validation, the reachable arbitration index, retained-carrier inertness and final-seam removal. |
| 10 | `s7-native-topology-conformance` | Independent raw proof hardening, complete durable-store restore coverage, zero route-capable seams, validator self-mutations, governed allowlist closure, and a completion-manifest-bound Platformization handoff; **GO-4**. |

GO-1 is a composite binary gate. Failure of GO-1A leaves old prep/plan/
critique authoritative. After GO-1A succeeds, GO-1B failure leaves only gate/
revise legacy-authoritative; it does not roll back the accepted S3A cut.

Native Parity is complete when the smallest readable Python topology fully
determines Megaplan behavior and every authoritative action uses current Run
Authority and Custody with applicable exact-version WBC evidence. A receipt,
projection, compatibility graph, or handler cannot choose a route.

#### Migration and compatibility ownership

Each slice follows one binary handoff:

```text
land the authored producer and generated bindings
  -> run behaviorally inert dual-read comparison
  -> pass merge-HEAD readiness validation
  -> run the typed transition: relocate WBC/action producer and cut authority exactly once
  -> pass independent post-transition verification
  -> migrate downstream consumers
  -> prove the old producer inert
  -> hard-fence/delete after installed and cross-host proof
```

External effects may be dual-read or dry-run compared. They are never
dual-written. The old live writer remains authoritative until GO-2 proves the
new production-shaped path, crash after durable outcome, cross-host exactly-once
reconciliation, and old-writer inertness; then authority cuts once.

| Surface | Before cut | During comparison | End state |
| --- | --- | --- | --- |
| `.pypeline` source, target `.pype`, and generated manifest | Detailed `.pypeline` candidate source; not fully load-bearing | Rename to `.pype`; new slices execute behind binary gates while pinned legacy artifacts remain explicit | `.pype` is the only live product-topology source; manifest is a generated runtime coordinate |
| Builder/components/handlers | May still construct routes or return route hints | Old producer remains authoritative until receipt, then becomes inert | Pure bodies/adapters or deleted; cannot select behavior |
| WBC producer | Often handler/component adjacent | Relocated at the exact semantic cut | Canonical lowered node/child boundary |
| `_core`, CLI, auto-drive | May read/mutate route-like state | Consumers migrate only after authority cut | Typed requests, scheduling, compatibility or observation only |
| Legacy state/receipts | Mixed state/authority/projection roles | Read-only comparison and journal parity | Rebuilt projection, archived, or deleted |
| External-effect writer | Old writer only | New dry run/dual read; never dual write | New exact-target writer only after GO-2 |
| Status/watchdog/auditor | Read multiple legacy surfaces | Compare against exact-version queries | Rebuildable projections/findings; no positive authority |

Comparison execution uses a digest-bound, quarantined namespace marked
`non_authoritative`, `non_resumable`, and `non_effect_capable`. It cannot append
to admitted RA decisions, Custody history, WBC attempts/effects, checkpoints,
terminals, resume selectors, or canonical projections. At most it emits a
signed comparison artifact or isolated comparison history. Promotion never
relabels shadow history as authoritative; after cutover the new producer starts
fresh admitted history or consumes an explicit authored migration.

Resume selection is not an editable route registry. Every migrated semantic
scope has one digest-bound `execution_plane_binding` in its admitted run or
migration record. A pure selector combines that binding with the checkpoint's
pinned executable, and one shared resume gate serves CLI, auto, native, and
legacy entry points. Changing the binding requires an accepted migration/
cutover decision; neither selector nor status may change the semantic cursor.

Each partial cut owns one closed typed seam adapter until the next milestone
replaces it: S3A to legacy gate, S3B to legacy tiebreaker/finalize, S4 to legacy
delivery, and S5 to retained control/auto. The upstream decision already names
the downstream target; the adapter only serializes immutable payload/envelope
and records the compatibility handoff. It cannot compute `next_step`, inspect
status to choose an entry, or emit another outcome. Route-capable seams are
registered controlled writers, carry an expiry/removal milestone, and are zero
at GO-4.

At every handoff, the union of old and candidate action/effect-capable paths
across `arnold.execution`, native execution, and retained legacy/runtime-envelope
surfaces is registered behind the same enforce-mode M11 action validator.
Exactly one producer may consume an accepted decision or write admitted
history. An unregistered old or candidate writer fails before product body or
effect intent.

“Scheduling” is deliberately narrow. After topology and an accepted decision
have selected the exact transition, retry generation, and declared policy, the
scheduler may choose an eligible worker, queue, and dispatch/wakeup time for
that immutable typed action request. It cannot create or reinterpret an
outcome, retry, escalation, cap, cost/stall response, reconfiguration, resume,
or terminal. The worker revalidates the complete current action envelope
immediately before work.

The Native Parity plan carries the executable detail. At a glance: GO-0 proves
generic ordered/multiset/decision/digest semantics before product migration;
GO-1A and GO-1B make the two front-half cuts independently explicit; GO-2
gates live effects; GO-3 proves stale-worker, repair classification, complete
reachable arbitration, and projection-forgery rejection before control-
consumer demotion; GO-4 consumes the complete proof map and blocks completion.

### 9.2 Stage 2 — platformize only proven boundaries

After the Native Parity completion manifest and its content-addressed
Platformization handoff manifest are accepted:

1. classify each construct as core primitive, stable reusable pattern,
   experimental pattern, or Megaplan-specific behavior;
2. freeze the component descriptor, lifecycle, composition, binding,
   isolation, evidence, and compatibility contracts;
3. create independently versioned reusable-pattern packages and deterministic
   dependency resolution;
4. extract the first proven patterns while preserving Megaplan's normalized
   golden traces;
5. make an unrelated consumer use multiple patterns in different composition
   shapes, with different types, outcomes, policies, effects, and storage;
6. certify static validity, clean-wheel execution, recomposition, isolation,
   fault recovery, upgrade, and implementation substitution;
7. publish only components with content-addressed conformance manifests.

Native Parity classifies each implemented construct as a core runtime
primitive, stable reusable-pattern candidate, experimental/two-consumer-
unproven candidate, or Megaplan-specific behavior. Its S7 handoff binds the
candidate/dependency inventory; exact typed port, outcome, policy, effect, and
state contract snapshots; source/runtime golden adapters; generic primitives'
zero-Megaplan-import proof; coupling evidence; exclusions; and classification
rationale. The seven-milestone Platformization work consumes this evidence but
independently freezes, implements, productizes, challenges, and certifies the
generic contract.

The milestones are: S1 freezes the candidate result/lifecycle/composition/
proof contract and invalid corpus; S2A implements and fault-tests the
product-neutral runtime/admission/authority substrate; S2B productizes the
adopted `.pype` compiler/linker, package correspondence, identity-aware
converter, and transactional refactors; S3 completes the CLI/editor,
format/lint/navigation/topology/preview/test surface and proves unfamiliar-
author usability; S4 proves the first extracted pattern set; S5 forces an
unrelated consumer to vary declared policies/shapes and prove substitution plus
separate new-instance/resume evolution; S6 alone publishes capability profiles
and content-addressed stable conformance manifests.

S1 through S5 each have pre-merge/post-merge stage gates. S2A's canonical
runtime selection and S4's active Megaplan binding/lock migration remain
non-authoritative through merge, execute only in their typed transitions, and
must pass separate post-transition gates. S6 alone runs cumulative readiness
certification, executes stable publication as a typed transition, and reruns
final conformance against the published state.

The S1 “freeze” is a candidate/experimental standard, not a stable public
compatibility promise. It may become stable only after the unrelated S5
consumer has exercised the same contract under materially different bindings
and S6 certification has accepted the corresponding conformance manifest.
Failure of that evidence narrows or revises the candidate; it is not papered
over by declaring the first Megaplan-shaped version stable.

Platformization also extends the Native Parity authoring/diagnostic/local-
harness corpus instead of refreezing a separate DX contract. Every Stage 2
diagnostic, fake, crash/race fixture, and source-mapped debugger assertion is a
strict extension or explicitly versioned successor of the Stage 1 corpus, and
the combined corpus remains runnable against Megaplan and the unrelated
consumer. A component package must not pass a friendlier test-only execution
path that omits the admission or durability behavior proven in Native Parity.

Platformization should continue the same sequencing discipline. Do not freeze
a “generic” planning, critique, review, or task abstraction merely because
Megaplan has one. Extract mechanics only after Native Parity provides one
correct implementation and the unrelated consumer demonstrates a genuinely
different binding. Until then, classify the candidate as experimental and keep
its public compatibility promise narrow.

The first likely pattern set remains evaluator panel, bounded refinement loop,
human gate, dependency-ready executor, review/rework/refinalization,
effect-safe action, and terminal arbitration. Product-specific planning,
critique meaning, finalization, and task semantics remain in Megaplan unless a
second real consumer demonstrates the abstraction.

## 10. Standardization closure contract

Platformization is incomplete unless all eleven clauses are true:

1. **Descriptor:** every exported step and workflow—including a workflow hosted
   as a subworkflow—has a qualified, versioned descriptor declaring its kind, typed input/output/
   state schemas, business outcomes with conditions/evidence/emission modes,
   applicable lifecycle/control terminals, hostability, dependencies,
   capabilities, policies,
   effects/compensations, suspension, identity, prompt/model/tool and budget/
   memoization dependencies where applicable, total root-hostability maps,
   timeout transitions, applicable trace-field table, and extension points.
2. **Lifecycle:** every component kind executes through one closed protocol;
   legal admission, start, retry, suspend/resume, cancel, compensate, and
   local-terminal transitions are explicit and enforced. Business outcomes
   remain distinct from lifecycle/control terminals; outcome conditions are
   accepted atomically with their local terminal and false conditions use the
   reserved contract-violation lifecycle terminal. Human gates use this same
   durable protocol and a total timeout graph rather than an out-of-band wait
   path. Only the root-host adapter may propose a root product terminal.
3. **Composition:** module exports, logical roots, static imports, bindings and
   control propagation are explicit; port, outcome, named-loop exit,
   reconfiguration, same-child retry/new generation, durable parent-loop state,
   total child-result join classification, exact success/impossibility results,
   scope, deadline, cancellation, resource settlement, budget, and namespace
   rules are statically checkable for every supported shape.
4. **Isolation:** component instances own disjoint state, checkpoint, artifact,
   identity, custody, and effect namespaces unless an explicit shared-resource
   port declares otherwise; no ambient mutable route or authority exists.
   Parent cancellation has an explicit epoch-checked child Custody disposition,
   resource-class settlement rule, effect-ambiguity policy, and typed
   unresolved-child fact whenever expiry permits acceptance without a child
   terminal.
5. **Authority and evidence:** every authority-increasing boundary uses the
   generated Run Authority/Custody/WBC integration and exact executable and
   dependency/product-contract digests; evidence and repair requests remain
   non-authoritative.
6. **Resolution:** execution uses a content-addressed component/dependency lock;
   incompatible, conflicting, or unavailable contracts fail before product
   work.
7. **Evolution:** compatible and breaking changes are defined for Python API,
   descriptor, serialized state, checkpoints, effects, prompt/model/tool
   bindings, and traces; active runs stay pinned or take an explicit accepted
   per-run migration/new-attempt path. New-instance compatibility never implies
   resume compatibility.
8. **Observation:** a product-neutral event envelope explains component-local
   and parent/child causality across consumers without importing product code;
   trace equivalence preserves multiplicity, per-instance order, declared
   happens-before edges, arbitration facts, and allowed unordered sibling sets.
   A content-addressed field-classification table fails unknown fields and raw
   event provenance is conserved before normalization.
9. **Conformance:** every stable component passes static, lifecycle, isolation,
   recomposition, fault, clean-wheel, upgrade, substitution, and deterministic
   local-harness tests with source-mapped failures.
10. **Variability:** domain meaning, policy values, implementations, and storage
    remain consumer-owned only through declared bindings; they cannot mutate
    shared internals or hidden global defaults.
11. **Execution modes:** preview, durable sandbox, comparison, admitted
    production, and certification share one compiler/lifecycle/event model but
    retain explicit claim boundaries; working-tree edits are easy fresh
    experiments and can never impersonate admitted history.

### 10.1 Minimum acceptance suite

The blocking Platformization proof should include:

1. **Descriptor/static negatives:** missing ports, unhandled outcomes,
   undeclared effects, illegal cycles/nesting, namespace collision,
   incompatible contracts, hidden product imports/globals, and unserializable
   durable state fail before authority acquisition.
2. **Decompose/reinsert:** extracting a nested section to a subworkflow and
   inlining it again preserves normalized behavior modulo the declared
   namespace boundary.
3. **Recomposition:** the same component runs at root, nested, sequentially,
   under a bounded loop, in fanout/fanin, across human suspension, and under
   parent cancellation/retry.
4. **Isolation:** duplicate and concurrent instances with different bindings
   cannot cross-read state, checkpoints, effects, custody, or outcomes.
5. **Lifecycle fault injection:** crashes around admission, body, checkpoint,
   effect intent/outcome, suspension, resume, compensation, and terminal
   acceptance yield only declared histories.
6. **Authority/Custody/WBC negatives:** stale or missing grants, fences, leases,
   epochs, boundary versions, executable digests, and dependency locks fail
   before action; projections and receipts cannot authorize.
7. **Resolution:** checkout, clean wheels, and cloud select the same locked
   component graph; transitive conflicts and mixed workers fail closed.
8. **Checkpoint evolution:** compatible resume, pinned-old resume, explicit
   migration, and breaking-change quarantine take their declared paths.
9. **Substitution:** a conforming implementation and compatible version preserve
   declared ports, lifecycle, decisions, effects, checkpoints, and terminals.
10. **Cross-consumer evidence:** generic tooling reconstructs causal component
    history for Megaplan and the unrelated workflow without product imports.
11. **Policy variability:** consumer policies, effects, and types change only
    declared outcomes and digests; shared protocol invariants remain fixed.
12. **Registry governance:** only content-addressed artifacts with valid
    conformance manifests can be stable; deprecated, withdrawn, or
    incompatible versions give deterministic diagnostics.
13. **Authoring/escape-hatch negatives:** unsupported syntax points to the
    authored source and the supported typed construct; handler returns,
    metadata, helpers, exceptions, CLI, and auto-drive cannot smuggle an
    undeclared route, outcome, effect, or policy into execution.
14. **Model/tool reproducibility:** prompt/model/provider/tool/policy and
    token/cost budgets are digest-bound; retries, memoization, replay, tool
    effects, and non-repeatable outputs follow the declared attempt/effect
    semantics.
15. **Local/production parity:** phase/effect fakes, virtual time, deterministic
    fanout, crash injection, and human-gate fast-forward produce the same
    lifecycle/event schemas and admission decisions as installed execution.
16. **Host/result separation:** component-local results cannot bypass the
    root-host adapter; business outcome conditions/evidence/emission modes and
    lifecycle/control terminals are independently mutation-tested.
17. **Parent durability/retry:** crashes at every loop-ledger edge preserve
    generation and aggregate-terminal consumption CAS; same-child retry adds
    an immutable execution-attempt terminal and reuses durable effect outcomes,
    while explicit new child generations receive new semantic identity.
18. **Join/cancel/resources:** all/any/quorum/reducer-threshold policies resolve
    success/failure/cancel/deadline/budget races deterministically, retain loser/
    late facts, classify the complete result union, narrow child budgets, and
    preserve unsettled liabilities until resource-specific settlement proof.
19. **Compatibility split:** `new_instance_compatible` and
    `resume_compatible` receive separate content-addressed receipts; an old
    checkpoint without identical durable semantics or admitted migration
    rejects the substitute.
20. **Partial-order traces:** mutations that duplicate, drop, causally invert,
    or falsely normalize events fail even when aggregate outputs match.
21. **Outcome-condition atomicity:** crash/retry around local condition
    evaluation accepts at most one pinned evaluation and terminal; false
    conditions yield only the reserved contract-violation lifecycle terminal,
    while missing/ambiguous evidence quarantines or follows declared lifecycle
    policy.
22. **Human timeout, cancellation, and duplicate answers:** every timeout/
    escalation generation has one typed transition; answer/timeout/cancel and
    accepted-but-unconsumed-answer/cancel release orders produce the declared
    CAS result, idempotent replay is inert, and distinct non-winning or late
    answers remain durable typed evidence.
23. **Total root hosting:** missing/default business or lifecycle maps and
    nested-only roots fail statically; many-to-one mappings preserve source
    result class, identity, and provenance.
24. **Total joins:** every child result class, qualifying predicate,
    unsatisfiable parent result, loser, late, failure, and simultaneous-event
    disposition is declared and mutation-tested.
25. **Resource settlement:** cancellation dispatch and Custody expiry cannot
    release token/money/tool/effect liability without resource-specific durable
    settlement; the budget invariant holds after every ledger event.
26. **Expired unresolved child:** any policy that accepts a parent terminal
    after child Custody expiry retains one typed `unresolved_child` fact and
    reconciliation obligation through trace, explanation, and projection
    rebuild.
27. **Trace conservation:** versioned field classification fails unknowns, raw
    identity/multiplicity is checked before normalization, and an independent
    verifier catches drop, duplicate, fold, reorder, and forged-source
    mutations without importing production filtering/cardinality logic.
28. **Production atomicity:** every lowered arbitration/consumption site binds
    to a certified linearizable store/service conditional mutation; independent
    production clients prove one accepted winner, and receipts bind store,
    adapter, key-schema, consistency, and deployment provenance. Application
    read/check/write and in-process locks cannot satisfy this clause.
29. **Manifest evolution:** manifest schema/version/hash and decoder identity are
    pinned; backwards decoding, migration, mixed-worker rejection, and old-run
    quarantine fixtures prohibit silent coordinate reinterpretation.
30. **WBC registry evolution:** every producer is admitted through an exact
    governed versioned registry entry. Registry changes retain prior producer
    provenance, cannot weaken obligations, and follow the mutability rules of
    the pinned platform contract.
31. **Experimental-to-stable promotion:** a candidate Stage 2 contract remains
    experimental until an unrelated consumer and stable conformance
    certification pass; its DX/conformance corpus extends, rather than bypasses
    or independently refreezes, the Native Parity corpus.

## 11. Developer and operator mental models

### 11.1 Developer

The developer authors:

- deterministic Python topology inside the supported subset;
- typed component ports, state, and closed outcomes;
- stable semantic and dynamic item keys;
- local policies, capabilities, deadlines and budgets;
- declared effects/compensations and model/tool/prompt dependencies;
- human-gate schemas and reentry meaning;
- product bindings and compatibility/migration declarations.

The developer does **not** hand-author manifest hashes, RA grants or decision
IDs, Custody leases/epochs, WBC attempt IDs, installed-artifact digests,
dependency locks, event sequences, or projection routes. Compilation,
resolution, admission, and runtime generate those mechanical coordinates.

The everyday loop should be:

```text
edit source/component contract
  -> static check with source-mapped diagnostics
  -> deterministic local run with phase/effect/model/human fakes
  -> inspect normalized lifecycle trace and checkpoint compatibility
  -> build clean wheel and locked composition
  -> run conformance before publication or rollout
```

When the subset is missing a legitimate construct, the response is a reviewed
typed primitive and compiler/runtime extension. Hiding orchestration in a
handler is not an acceptable workaround.

### 11.2 Operator

The operator inspects:

- the accepted RA decision, scope, subject attempt, and current fence;
- the exact current Custody target, owner, lease, and epoch;
- WBC boundary/attempt/effect history and any ambiguity/finding;
- pinned source/manifest, policy, component, artifact, dependency, state, and
  model/tool versions;
- checkpoint/reentry lineage and the journal/projection source cursor;
- legal typed migration, retry, reclaim, reconciliation, or quarantine
  requests and their failed preconditions.

The operator may request one of those typed actions. The operator never
advances a run by editing `state.json`, a receipt, checkpoint, projection,
status field, task artifact, process marker, or compatibility route. A causal
explanation is trustworthy because it joins authoritative histories; it
remains behaviorally inert.

## 12. Deliberate variability and non-goals

The standard is a boundary and execution protocol, not a universal product
ontology. These should remain variable:

- product domain types, business meaning, artifacts, and outcome vocabulary;
- retry counts, model choices, timeouts, worker caps, review thresholds,
  escalation policy, and other policy values;
- effect implementations, external systems, storage layout, and artifact
  formats behind typed contracts;
- scheduler implementation, worker placement, transport, and parallel sibling
  wall-clock interleaving, provided causal and multiplicity invariants hold;
- UUID formats, physical tables, deterministic hash algorithm choice,
  decorator spelling, process/container boundaries, and projection UI;
- internal compiler APIs until explicitly promoted to public composition
  surfaces;
- whether a product phase becomes a reusable pattern at all;
- performance and cost unless a component publishes an explicit resource/SLO
  contract.

The platform standardizes where variability is declared, how it is bound, and
which invariants it may not violate. It should not generalize every Megaplan
function, force unrelated domains into Megaplan outcomes, rebuild Run
Authority/Custody/WBC, or invent abstractions without two concrete consumers.

## 13. Conclusion

The original diagnosis remains correct: Megaplan's graph currently exposes
phase labels while handlers and runtime helpers act as hidden
mini-orchestrators. The Native Parity endpoint is a readable, durable Python
program in which product routes, loops, fanout, reentry, policy, effects, and
terminals are authored once and proven against the same authority, custody,
WBC, checkpoint, and installed-runtime history.

The broader platform endpoint is stricter. It is not reached when the same
callable can be imported twice. It is reached when a qualified, contracted
component retains its declared semantics as its parent, composition shape,
package boundary, host, compatible version, policy binding, and implementation
vary within explicitly supported ranges.

That yields the intended foundation:

```text
one correct product topology
  -> proven generic primitives and patterns
  -> contracted packages with deterministic resolution
  -> unrelated product compositions
  -> black-box conformance and behavioral substitutability
```

Native Parity establishes semantic truth. Platformization turns the proven
parts of that truth into reusable infrastructure without erasing the domain
distinctions that made the original workflow correct.

## 14. How to audit this design

This section is the audit entry point, not a substitute for the detailed
matrices and challenges in the Oracle packet and companion artifacts. An
auditor should first classify every claim, then trace each normative invariant
to independently verified runtime evidence.

### 14.1 Status legend

| Status | Meaning |
|---|---|
| **Normative contract** | Required end-state behavior. Implementations and plans must conform. |
| **Controlling plan** | Approved sequencing, gates, and evidence obligations for reaching a normative contract. It does not redefine the contract. |
| **Current-state fact** | Describes observed source, runtime, or infrastructure today; it is not automatically desirable or stable. |
| **Illustrative API** | Example spelling or shape used to make the contract concrete. Names, decorators, modules, and class layouts may change while observable semantics do not. |
| **Audit input** | Oracle packet, critique, inventory, or analysis used to challenge the design. It becomes normative only when incorporated into a contract or controlling plan. |

### 14.2 Compact contract and source index

| Concern | Controlling source | Audit use |
|---|---|---|
| Holistic target representation | This report | Defines the combined product, execution, authority, proof, and platform endpoint. |
| Stage 1 native parity | `megaplan-native-parity-corrective-plan.md` and `GOLDEN_TRACE_CONTRACT.md` | Controls parity gates and the minimum observable trace contract. |
| Stage 2 reusable platform | Prepared Platformization `PLATFORM_CONTRACT.md`, milestone briefs, and `chain.yaml`; ticket retained as provenance | Controls the seven-milestone S1/S2A/S2B/S3/S4/S5/S6 runtime, authoring-core, developer-tooling, extraction, challenge, and certification sequence. |
| Python authoring and manifest boundaries | `pype-authoring-contract.md` and `workflow-manifest.md`; `python-shaped-authoring-contract.md` is migration baseline | Constrains target authored syntax, lowering, validation, identity, packaging, migration, and generated-manifest identity. |
| Execution authority and workflow boundaries | `runauthority-main-plan.md`, Workflow Boundary Contracts north star, and `state-authority-migration.md` | Constrains action admission, leases, evidence, state ownership, and migration. |
| Current implementation | Cited source/compiler/runtime files and accepted completion artifacts | Establishes feasibility and actual behavior; source citations are descriptive unless a normative source adopts them. |
| Adversarial audit | Oracle packet and companion audit artifacts | Supplies challenges, omissions, and matrices. It cannot itself authorize execution or declare conformance. |

If sources conflict, the more specific normative contract governs its own
boundary; an approved controlling plan governs delivery order but cannot relax
that contract silently. Conflicts must be recorded and resolved explicitly,
not inferred from whichever implementation already exists.

### 14.3 Observable compatibility and allowed variability

Compatibility must compare all contractually observable dimensions:

- typed ports and business-outcome payloads;
- outcome conditions, required evidence, and emission mode;
- lifecycle and control terminals;
- per-instance event multiplicity and total order;
- cross-instance happens-before relations, including which siblings are
  deliberately unordered;
- accepted and rejected arbitration facts;
- semantic, Run Authority, WBC, and Custody identity joins;
- checkpoint, state, and effect histories;
- resource ledgers, settlement/liability, budget, cancellation, expiry,
  unresolved-child, and deadline semantics;
- total root-host terminal mapping with retained local result class/provenance;
- trace-schema field classification and one-to-one raw-event provenance; and
- installed component, dependency, model, tool, and product-contract pins when
  the contract makes them observable.

Allowed variability is limited to physical storage, UUID spelling, worker
placement, transport, legal sibling wall-clock interleaving, scheduler
implementation, performance or cost without a published SLO, internal
compiler APIs, and product-specific types, policies, and effects supplied
through declared bindings. None of those freedoms may change an observable
dimension above.

### 14.4 Arbitration policy index

Every family of competing transitions must name one versioned arbitration
policy and its compare-and-set or precedence rules. The required index maps:

```text
semantic site
  -> policy id and version
  -> closed participants and precondition/CAS key
  -> precedence rule and retained facts
  -> winner, loser, and late-arrival disposition
  -> owning cutover/gate and emitted evidence
  -> positive, negative, and forced-race fixture ids
```

At minimum it covers root cancellation versus publish/deliver/done; `all`,
`any`, `quorum`, and reducer joins; parent cancellation/deadline/budget versus
child outcome; ambiguous effects and duplicate intent/outcome; accepted
decision consumption and same-child versus new-generation reentry; and any
competing human answer/timeout/escalation, outcome-condition acceptance,
resource settlement, repair invalidation/redispatch, reconfiguration, resume,
or migration transition. Wall-clock arrival order and projection order are
never implicit arbitration policies.

“CAS” here means a linearizable conditional mutation enforced by the admitted
production persistence service/store against one authoritative key and
expected version—not an application-level read, check, then write, and not an
in-process mutex. Every lowered arbitration, decision-consumption, aggregate-
terminal, and loop-ledger site joins to one certified persistence primitive.
Its receipt binds service/store implementation and version, adapter
implementation and version, key schema, isolation/consistency mode, and the
production topology actually exercised. Two independent clients contending at
the pre-commit barrier must prove that at most one conditional mutation is
accepted and that the loser observes the durable winner. An in-memory or
serialized harness remains useful for semantic tests but cannot certify this
atomicity claim.

Closure is exact set equality among arbitration sites emitted by lowered
semantic transition metadata, the normative policy index, forced-race fixture
receipts, and runtime-observed sites for the admitted program. Each cutover
must close the subset it makes live rather than postponing discovery to GO-3;
GO-4 proves complete equality. For every participant pair, both release orders
at the barrier immediately before authoritative CAS must produce the same
policy result and retained loser facts. Pairwise coverage is sufficient unless
a policy declares non-associative multi-party behavior.

### 14.5 Invariant traceability and proof-system trust

Every normative invariant must have one traceability row:

```text
invariant id and text
  -> owning sprint and gate (GO-0..GO-4 or platform S1..S5)
  -> executable evidence artifact or receipt, bound to exact run/commit/lock
  -> authoritative producer
  -> independent verifier
  -> negative-mutation id
  -> status derived from execution
```

The final proof map must consume every row. A proof generator cannot certify a
fact merely because its own prose, fixture, hash, or predeclared status says the
fact is implemented.

`GOLDEN_TRACE_CONTRACT.md` is the human-reviewed normative scenario/invariant
contract, not an executable route table. An independent static source oracle
derives semantic occurrences, source spans, named policies, and structured-
control relations from canonical `.pype` source and scenario inputs without
calling the production lowerer or treating runtime output as expected output.
Runtime adapters export raw primary-store facts. Before semantic comparison, a
separately implemented raw verifier proves cursor continuity and multiset
conservation from raw event IDs to normalized source references. The verifier
may share normative schemas, parsers, hashing, and canonical serialization, but
must not import or share production event selection, filtering, folding,
deduplication, cardinality, causality, or verdict logic. Raw export and both
executable digests are bound into the proof receipt.

The trusted roots are the accepted source, manifest, and lock; append-only Run
Authority decisions; current Custody leases and epochs; transactional WBC
history; immutable artifacts and evidence; an independent verifier; and a
proof-map binding to the exact run, commit, and lock. Generated reports,
projections, WBC receipts in isolation, legacy state, shadow-comparison
history, handler/CLI/auto metadata, self-declared implementation rows, and
whole-file hashes alone are non-authoritative. A producer cannot be the sole
verifier of its own claim: the verifier must replay or query the relevant
primary stores. Proof fixtures and Oracle material remain inert and never
become execution authority.

Every durable record also appears in a restore/ownership matrix as exactly one
of: M11 canonical/transactional authority state; Native route-relevant state
transactionally joined to M11 acceptance or a fail-closed M11 restore/
incarnation token; immutable content-addressed artifact; rebuildable non-
authoritative view; or forbidden Native-local authority state. Native-local
grant/decision consumption, lease/epoch, WBC/effect truth, or action-admission
stores are architecture violations, not alternative restore schemes. Generic
route-state classes are rollback/replay drilled at GO-0, concrete classes
before their owning cutover, and the complete inventory at GO-4.

### 14.6 Feasibility inputs and the M11 caveat

Implementation feasibility cannot be confirmed from target prose alone. Before
execution, the plan must bind to the exact current substrate:

- authoring grammar, compiler, manifest versions, and diagnostics;
- NativeProgram and WorkflowManifest runners and their convergence path;
- accepted M11 APIs, versions, controlled-writer inventory, and action
  validator;
- WBC producer/query registry, store, effect, and recovery contracts;
- Run Authority grant, decision, and fence contracts;
- Custody lease, epoch, target, reclaim, and restore proof;
- package/lock/installed-artifact resolution;
- checkpoint, state, artifact, and error schema registries;
- agent runtime, model/tool dispatch, prompt schemas, budgets, and cache;
- local deterministic harness and cloud/installed execution environments; and
- migration inventory for handler, component, `_core`, CLI, auto, status,
  projection, reader, and writer paths.

This checkout does not by itself prove the accepted, completed M11 substrate.
The canonical M11 API paths, versions, writer inventory, and proof references
must come from its accepted completion manifest and proof map. Locally similar
lease or control-plane code must not be treated as equivalent by name. Because
M11 is assumed complete before this work proceeds, the implementation plan must
consume those completed artifacts rather than redesigning or guessing them.

S1 nevertheless runs version-bound executable capability probes against that
exact accepted revision. They must prove: all execution-plane writer classes
can be registered behind one fail-closed validator; accepted decisions are
single-consumption and restore-safe through linearizable production-store CAS
exercised by independent clients, with service/store and adapter provenance;
the envelope can equality-bind opaque
program/policy/WBC/artifact/lock/prompt/tool/product-contract digests; exact
Custody targets, transfer/reclaim, and production-scale fanout capacity exist;
WBC attempt/checkpoint/effect ambiguity/reconciliation/causal-query/terminal
semantics are exact-versioned; the admitted WBC registry supports the required
governed versioned producer registration and pins the effective registry entry
without silently changing platform-contract meaning; manifest schema/hash
evolution supports pinned old decoders or explicit migration and rejects
incompatible mixed workers; fences, epochs, and Native route-relevant state are
rollback safe; repair preconditions and rejection classes are canonical; and
pinned artifacts support installed/cross-host handoff. Comparison either
uses a proven M11 comparison class excluded from canonical queries or, preferably,
has no RA/Custody/admitted WBC/effect capability and writes only an inert
separate artifact. A failed probe yields typed
`blocked_on_m11_capability`/`blocked_on_m11_point_release`; Native Parity does
not add a local facade or side store.

### 14.7 Known unknowns

The round-three Oracle adjudications resolve the previously omitted proof and
determinacy questions incorporated above. The following remain explicit audit
items rather than silently resolved facts:

- numerical thresholds for the DX and conformance gates, which must be fixed
  before a gate can pass rather than chosen after results are known;
- the canonical accepted M11 completion-manifest and proof-map path; and
- open-stream semantics, which are outside the Stage 1 surface and remain
  future scope unless a product requirement promotes them with a defined
  lifecycle, custody, arbitration, checkpoint, and evidence contract.

An audit is complete only when these unknowns are either resolved in a
versioned normative artifact or retained as explicit non-goals with no hidden
dependency from an acceptance gate.
