# Native Megaplan parity: green-but-wrong implementation pre-mortem

Date: 2026-07-21  
Posture: read-only Sol synthesis  
Verdict: **determinate with bounded sharpening**

## Executive judgment

The revised seven-sprint plan is no longer materially open to the obvious false-pass implementations. It explicitly makes `workflow.pypeline` plus named native subworkflows the only product-topology authority, separates the four identity domains, requires exact accepted-decision consumption, binds source/policy/WBC drift at checkpoints and reentry, forbids handler/auto/CLI/projection route authority, and requires source mutation plus dead-carrier proof (`docs/arnold/megaplan-native-parity-corrective-plan.md:66-87`, `:113-145`, `:455-519`). A competent team following those words cannot honestly retain the present route brain wholesale.

The plan can nevertheless close green around six bounded seams and deliver a system that is locally conformant but compositionally or operationally wrong:

1. its normative proof is row- and set-oriented, not an ordered, multiplicity-preserving, same-run source-to-terminal trace;
2. version/digest binding is explicit at checkpoint/reentry but not at every subsequently dispatched Native action, while installed parity is tested only as homogeneous environments;
3. S5 has no stop/go boundary before the first authoritative external effect is cut over;
4. S6 names cancellation, publication, delivery, and terminal outcomes but does not define their mutual exclusion and race precedence;
5. “smallest readable” has no retention test, so a technically authoritative but high-ceremony source can encourage the next bypass;
6. the composed history can be complete in storage yet lack a Native-specific causal explanation and safe repair preflight for an operator.

These do not require a new sprint, a new authority layer, or reopening M11. They require a golden-trace asset, two cutover/action checks, one closed control-arbitration table, an extension/readability contract, and a read-only Native incident view. With those additions, the plan is operationally determinate.

## Standard applied

The target is not syntax parity. The report's aspirational workflow makes the critique and review/rework cycles visible, expresses suspension/reentry and dynamic execution in the authored program, attaches retry/model policy to call sites, and declares edge effects (`docs/arnold/megaplan-native-representation-report.md:613-731`). The corrective plan sharpens the goal to the minimum readable workflow that completely determines behavior (`docs/arnold/megaplan-native-parity-corrective-plan.md:72-87`).

I therefore treated a finding as material only if it could leave one of these facts outside the authored topology or make the topology cease to be the practical long-term authority:

- product branch, loop, fanout/fanin, retry/cap, suspension/reentry, effect, or terminal ordering;
- the exact accepted authority decision consumed by an action;
- current exact-target custody;
- the WBC attempt/effect/checkpoint lineage;
- the ability to extend or diagnose those facts without consulting a hidden route carrier.

M11's generic grant, custody, WBC, recovery, query, projection, and proof implementation is accepted and not audited here.

## Independent review and reconciliation

Six isolated reviewers inspected the primary documents and code through the repository's `subagent-launcher` fan-out. Their raw, mutually isolated reports and execution metadata are retained under `.tmp/native-parity-pre-mortem/reviews/`.

| Review lens | Useful conclusion retained | Conclusion rejected or narrowed |
|---|---|---|
| Adversarial minimal implementer | Present aliases, route maps, handler state, and auto routing show the cheapest bypass shapes are realistic | Most proposed exploits are already explicitly blocked by current mutation, identity, purity, reentry, and proof-map language |
| PR/migration sequencer | Producer-before-consumer strangler, hard-fence before delete, and explicit receipts | The plan already permits hard fencing and expressly defers generic per-milestone chain validators; those are not new amendments |
| Golden trace designer | Stable fixture schema, ordered causal events, and six scenario families | Child identity, exact decision consumption, digest binding, add-note, reusable-cycle uniqueness, and S3 gating are already specified; they are not fatal gaps |
| Future author | Extension tests are necessary to keep the Python topology the natural edit point | Current evidence-pack/native APIs are precedents, not necessarily the S7 end state; only the retention contract is carried forward |
| Incident responder | Mixed-version execution and cross-store causal explanation are the surviving Native-specific risks | Generic custody, WBC transactions, quarantine, recovery, and projection mechanics remain accepted M11 scope |
| Python ergonomics critic | Generate mechanical bindings, prohibit parallel topology declarations, and test edit locality | Specific module deletions, decorator syntax, line counts, and handler refactors are implementation choices rather than epic requirements |

The prior round-two audit was read only after the independent position was frozen. Its bounded amendments were then checked against the current plan; all five are present, as documented near the end of this report.

## Ranked green-but-wrong exploit catalogue

### 1. Row-green, whole-workflow-wrong

**Permitting text.** The normative matrix is defined “for each product semantic” and the evidence contract says “Every implemented row has generated evidence” (`docs/arnold/megaplan-native-parity-corrective-plan.md:394-437`). The blocking identity checks require generated **set equality** (`:127-130`, `:455-464`). S7 does mention “end-to-end compositions” (`:367-374`), but neither their ordered event relation nor their requirement to come from the same run history is specified.

**Cheapest plausible green implementation.** Implement a proof generator that independently demonstrates:

- each source/lowered/runtime node name exists;
- each decision has one accepted and one consumed record in its row fixture;
- each split outcome works in a focused test;
- one happy-path end-to-end run reaches `done`.

The actual runtime can still misorder a gate decision and checkpoint, collapse two same-path invocations into one set member, join a retry twice, take an untested cross-row branch, or stitch evidence from separate runs. The current tests show why this is realistic: the golden manifest maps coarse D1–D8 evidence to several runners (`tests/arnold_pipelines/megaplan/test_native_golden_traces.py:40-184`), while compositional tests use a fake backend and coarse route selections (`tests/arnold_pipelines/megaplan/test_compositional_workflow.py:25-36`, `:100-280`). The new plan replaces those proofs, but its wording still permits the same *shape* of row-local evidence.

**Why current proof can miss it.** A set does not preserve occurrence count, loop generation, sibling/join causality, or order. Separate row traces do not prove that the accepted decision, custody epoch, WBC effect, checkpoint, and terminal belonged to one execution.

**Exact amendment.** Make `.tmp/native-parity-pre-mortem/golden-trace-contract.md` (moved into the durable initiative during S1) a normative S1 asset and S7 input. Require six stable scenarios, ordered causal events with explicitly unordered parallel siblings, multiset occurrence equality, all four identity joins, forbidden observations, and mutation assertions. S3–S6 fill it incrementally; S7 executes the same fixtures against checkout, wheel/sdist, and cloud and consumes traces from one composed history. This is one new proof dimension, not another topology.

### 2. A valid current fence executes stale Native semantics

**Permitting text.** “Every checkpoint/reentry envelope” binds the program/topology, call-site-policy, and WBC contract digests (`docs/arnold/megaplan-native-parity-corrective-plan.md:140-145`). The action conjunction itself names current grant/fence, custody/epoch, and required WBC evidence (`:99-111`). Installed parity requires checkout, wheel/sdist, and pinned cloud to produce the same result (`:483-484`), but does not require a mixed-version negative run.

**Cheapest plausible green implementation.** All checkpoints and resumes correctly verify digests. Homogeneous checkout, wheel, and cloud jobs are green. During a rolling deployment, however, an old worker receives a post-checkpoint task under a valid current grant and custody epoch. Its local source/policy artifact differs but the dispatch/action envelope does not compare the admitted Native program, policy, WBC contract, and installed-artifact digests. It executes old call-site policy or old terminal behavior while satisfying M11 authority and custody.

**Why current proof can miss it.** Three homogeneous environments prove reproducibility, not rejection of a heterogeneous run. Resume-drift tests do not exercise a stale executor dispatched between checkpoints.

**Exact amendment.** At every Native authority-increasing dispatch/action boundary, bind and validate the admitted program/topology digest, call-site-policy digest, exact WBC contract version, and installed-artifact digest before the product body or effect intent. Add a mixed-host fixture: one stale worker in an otherwise current run must quarantine/reject before execution; an explicit accepted migration/new-attempt decision is the only continuation. This is Native binding to M11's validator, not a new version or authority service.

### 3. The first live external effect becomes the migration experiment

**Permitting text.** S5 requires M11 effect intent/outcome, ambiguity, idempotency, and reconciliation and has strong final semantic/adoption gates (`.megaplan/initiatives/megaplan-native-parity-corrective/briefs/s5-review-rework-finalize.md:27-65`). Unlike S3, it has no internal stop/go receipt before legacy effect writers are fenced and the first corrected path is allowed to produce a real effect.

**Cheapest plausible green implementation.** Build the authored delivery cycle and pass crash tests using an in-memory or fake effect adapter. Switch execute/review consumers and effect producers in one large PR or feature-flag flip. The final code can pass its tests while the migration briefly admits dual writers, a legacy retry path, or an installed artifact whose effect idempotency binding was never exercised. The team later removes the evidence of the bad interval and closes the sprint green.

**Why current proof can miss it.** The exit gate proves the landed state, not that the cutover boundary was safe and binary. A test double can demonstrate intent/outcome semantics without proving that exactly one production-shaped writer owns the admitted effect target.

**Exact amendment.** Add an S5 internal **no-delete/no-disable stop/go** after the new producer and action envelope exist but before any legacy producer is fenced. The receipt must execute one non-destructive task and one idempotent production-shaped external effect through checkout and installed artifact, inject a crash after durable effect outcome but before product receipt, resume cross-host without replay, prove source mutation changes the trace, and prove the old producer is inert. Only then may the cutover/fence PR proceed. Never dual-write an external effect; dual-read comparison is allowed.

### 4. Individually valid cancellation, publication, delivery, and terminal decisions race to two truths

**Permitting text.** S6 enumerates cancel, terminal halt, publication, and delivery routes and requires each to execute from lowered topology (`.megaplan/initiatives/megaplan-native-parity-corrective/briefs/s6-override-auto-compat-collapse.md:9-25`, `:41-57`). The plan requires terminal uniqueness in the WBC lifecycle (`docs/arnold/megaplan-native-parity-corrective-plan.md:470-471`) but does not state product-level precedence among a cancel accepted during publication, a publication outcome, delivery, and `done`.

**Cheapest plausible green implementation.** Model all four as typed source decisions, consume each exact Run Authority decision once, and test each split outcome separately. In a race, publication and cancellation can both be valid under their own preconditions; one projection reports cancelled while another worker proceeds to delivery, or a late cancel rewrites a completed terminal. Every row and individual decision mapping remains green.

**Why current proof can miss it.** Exact one-to-one decision consumption prevents forged or duplicated decisions; it does not decide which mutually incompatible decision is admissible first. WBC terminal uniqueness does not itself define Megaplan's product semantics for an already-completed publication followed by cancellation.

**Exact amendment.** In S6, add a closed authored control-arbitration table (or equivalent source branches) with CAS preconditions for cancel, publish, deliver, and terminal acceptance. Add the three `NP-GT-006` variants: cancel before publication; publication outcome before cancel but delivery not started; delivery/done before a late cancel. The expected outcomes may differ from the proposed contract, but the order, preserved effect history, and rejection behavior must be explicit and mutation-tested.

### 5. Authoritative today, bypassed by the next ordinary extension

**Permitting text.** The final gate is that “A reviewer can understand the entire product flow from canonical source” (`docs/arnold/megaplan-native-parity-corrective-plan.md:518-519`). No objective retention or extension proof accompanies “minimum readable workflow” (`:79-87`).

**Cheapest plausible green implementation.** Delete the hidden carriers but replace them with a 700-line canonical source containing repeated delivery blocks, manual interface/route/policy dictionaries, and handwritten mappings among semantic IDs, handler refs, stable IDs, and runtime kinds. It is technically authoritative. Six months later, adding a gate outcome naturally requires synchronized changes in source, vocabulary, interface metadata, compatibility registrations, and tests. A competent maintainer edits the familiar handler or auto path and recreates dual truth.

This is not hypothetical pressure. Today the workflow repeats major execute/review blocks (`arnold_pipelines/megaplan/workflows/workflow.pypeline:388-754`), lowering maintains aliases and overlays (`arnold_pipelines/megaplan/workflows/planning.py:110-139`, `:583-721`), and `_core/workflow_data.py:45-117` remains another route representation. The plan correctly deletes or derives those surfaces; it does not yet test that ordinary future changes stay one-source.

**Why current proof can miss it.** Mutation tests establish present authority, not edit locality. A reviewer can call a file “readable” even when adding one semantic requires six manual declarations. File deletion alone does not prevent a generated-looking but hand-maintained parallel registry from returning.

**Exact amendment.** Add an S7 authoring-retention suite with six extension mutations: gate outcome, dynamic review lens, retry policy, human decision, override, and external effect. Each must be expressible at the Python topology or a declared call-site policy/effect vocabulary; derived bindings update mechanically; handler/auto/metadata-only additions fail conformance. Adopt the readability contract below. Do not require a particular decorator syntax or literal line count when the structural conditions hold.

### 6. One complete history that an operator still cannot safely use

**Permitting text.** The end state says projections are disposable and the definition of done says “projections only explain” (`docs/arnold/megaplan-native-parity-corrective-plan.md:68-70`, `:593-603`). The plan requires all causal facts to exist but does not require one Native-specific explanation or repair preflight that joins source occurrence, accepted decision, custody epoch, WBC attempt/effect, checkpoint/reentry, and terminal conflict.

**Cheapest plausible green implementation.** Persist every required M11 record and generate all conformance receipts. During an incident, `status` shows blocked, WBC shows an effect outcome, custody shows a reassignment, and the source shows a reentry—but no read-only view joins them or says whether replay, resume, migration, cancel, or adoption is currently legal. The operator consults handler-local state or a stale status projection and issues an unsafe repair request.

**Why current proof can miss it.** Machine set equality and scenario pass/fail do not prove a human can reconstruct causality or distinguish “effect outcome before receipt,” “stale worker,” “suspended under drift,” and “terminal conflict.” Projection non-authority prevents one class of bug but does not guarantee an adequate explanation.

**Exact amendment.** Require a Native composed-run explanation and repair preflight built only from admitted M11 queries. For any scenario it must display semantic occurrence/retry/reentry coordinate, exact accepted and consumed decision, current versus historical fence/epoch, WBC attempt/effect ambiguity, pinned versus current digests, terminal arbitration state, and the legal request-only repairs with failed preconditions. Deleting and rebuilding this view must not change behavior. Its output is observational and cannot authorize or dispatch anything.

## Sprint/PR migration dependency graph

The safest implementation is a strangler in which the new semantic producer is proven before the corresponding old producer is fenced. Read compatibility may temporarily compare old and new views; effect paths must never dual-write.

```text
accepted M11
   |
   v
P1  S1 proof schema + golden-trace skeleton + admission locks
   |
   v
P2  S2 generic typed decisions/loops/map-reduce/reentry/policy bindings
   |
   +--> P3 neutral reference pipeline runtime receipt
   |          |
   |          v
   |     [GO-0: generic constructs prove no Megaplan coupling]
   |          |
   v          v
P4  S3 prep->plan native producer + dual-read comparison
   |
   v
[GO-1: existing S3 internal source/load-bearing/installed receipt]
   |
   v
P5  S3 critique/gate/revise consumers move; old front-half carriers hard-fenced
   |
   v
P6  S4 tiebreaker/finalize/human suspension and reentry
   |
   v
P7  S5 delivery cycle in shadow/dry-run; exact child/effect bindings
   |
   v
[GO-2: first production-shaped effect, crash-after-outcome, cross-host receipt]
   |
   v
P8  S5 authoritative delivery cutover; all consumers move; legacy writers fenced
   |
   v
P9  S6 controls/config/note/cancel-publish-deliver arbitration
   |
   v
[GO-3: mixed-version rejection + terminal-race family]
   |
   v
P10 S6 auto/CLI/status/watchdog/projections reduced to request/observation
   |
   v
P11 S7 delete remaining quarantined carriers; checkout/wheel/cloud composed proof
   |
   v
[GO-4: final proof-map consumption and old-ledger negative]
```

### Stop/go receipts

| Boundary | Binary go condition | No-go consequence |
|---|---|---|
| GO-0 generic constructs | Neutral pipeline proves ordered/multiset trace, exact decision binding, retry/fallback, reentry, and no Megaplan imports/special cases | Do not begin product migration |
| GO-1 front half | Source mutation changes runtime; old carrier mutation is inert; checkout and installed artifact agree; exact decision/custody/WBC joins exist | Keep old producer authoritative; do not fence it |
| GO-2 first effect | One admitted production-shaped effect survives outcome-before-receipt crash and cross-host reconciliation exactly once; old writer is inert | No live effect cutover and no old-writer fence |
| GO-3 controls | Closed race variants pass; stale installed worker rejects before action; projection forgery is inert | Do not reduce old control consumers or enable heterogeneous rollout |
| GO-4 final | All six golden fixtures and mutations consume the complete proof map from one composed history in checkout, wheel/sdist, and cloud; refreshed old ledger stays red | Epic cannot close |

### Producer/consumer ordering rules

1. Land and test the new authored producer and generated bindings.
2. Permit dual-read comparison only where reading cannot influence behavior.
3. Relocate the authoritative WBC/action producer through the admitted M11 boundary.
4. Cut authority once, at an explicit receipt boundary; never permit two external-effect writers.
5. Move every consumer to canonical events/queries.
6. Prove old producer mutation is inert, then hard-fence it.
7. Delete quarantined carriers only after installed and cross-host receipts are green.

The current plan already permits “deleted or hard-fenced” carriers and states that producer relocation precedes removal; converting every deletion to a new epic requirement is unnecessary. Likewise, the chain explicitly cannot run arbitrary per-milestone validators (`docs/arnold/megaplan-native-parity-corrective-plan.md:553-579`); the receipts above belong to sprint acceptance tests and the S7 registry, not invented `chain.yaml` fields.

## Future-extension test

| Six-month change | Intended authoritative edit point | Attractive bypass to reject | Anti-bypass acceptance proof |
|---|---|---|---|
| New gate outcome | Closed decision vocabulary and branch in Python topology | Add handler recommendation / component route constant | Compile-time exhaustiveness; source mutation changes trace; handler-only outcome is unknown and fails |
| New dynamic review lens | Declared lens provider/item schema plus source `map`/reducer call site | Register a validator function that runs outside topology | Child appears with stable item identity in source/lowered/runtime/WBC multiset; registry-only lens cannot execute |
| New retry policy | Named policy attached at exact phase/subworkflow call site | Add a handler loop, global auto retry, or buried cap | Policy mutation changes attempts/cap; transitive purity scan rejects hidden retry ownership |
| New human decision | Source-visible typed human gate, capability, suspension and reentry edge | Return a generic suspension from a phase/CLI | Checkpoint includes semantic cursor and all bindings; direct suspension without authored gate fails lowering/conformance |
| New override | Closed control subworkflow/action vocabulary and semantic target | Extend CLI/override matrix or auto status interpretation | CLI can request only; unknown action denied; only source addition creates accepted route/effect |
| New external effect | Explicit source edge/call-site effect declaration with target and idempotency policy | Call service/file write inside an undeclared handler | Static/transitive effect scan plus crash matrix; undeclared effect fails before release |

This table is a retention proof, not a mandate that all six changes become product features.

## Incident and repair observability

| Incident | Plan disposition | Assessment / bounded addition |
|---|---|---|
| Stale coordinator or expired/reassigned custody | Current grant/fence and exact lease/epoch required for every action (`corrective-plan.md:99-111`) | Covered by accepted M11 plus Native action binding; do not redesign custody |
| Suspension under source/policy/WBC drift | Checkpoint/reentry binds all three and requires explicit drift decision (`:140-145`, `:474-478`) | Already closed by the revised plan; golden scenario 3 verifies it |
| Crash before/after effect intent/outcome | S5 requires ambiguity, reconciliation, idempotency and crash scenarios (`s5...md:40-65`) | Covered semantically; GO-2 makes the live cutover safe |
| Cross-host handoff | S4/S5 and blocking regressions require current identities and transfer/reclaim | Covered; composed explainer must show old/new epochs and causal join |
| Forged/stale projections | Explicitly observational and mutation-tested (`corrective-plan.md:468-484`) | Covered; no new projection authority |
| Partial installed-version skew | Only homogeneous installed parity is explicit | Material gap: bind executable digests at dispatch/action and reject one stale worker |
| Accepted publication/cancellation/delivery race | Individual routes and terminal uniqueness are explicit | Material gap: authored arbitration/CAS table and three race fixtures |
| Effect succeeded but product receipt is absent | Durable WBC outcome exists; product projection may lag | Operator gap: explainer must say “reconcile/rebuild receipt; do not repeat effect” |
| Repair request during ambiguity/drift | M11 owns generic recovery/action validation | Native view must show legal request and failed preconditions; it remains read-only |

A human should be able to answer five questions without reading handler state: Which semantic occurrence was active? Which exact decision was accepted and consumed? Who currently owns the exact target? What durable boundary/effect facts exist or remain ambiguous? Which authored transition or request-only repair is currently admissible? If the composed history cannot answer all five, Native parity is operationally incomplete even if raw records exist.

## Python authoring ergonomics and readability contract

### Assessment

The aspirational surface is directionally right: ordinary Python control flow plus a small set of durable primitives makes loops, fanout, human gates, policy, and effects inspectable (`docs/arnold/megaplan-native-representation-report.md:264-360`, `:613-755`). The danger is not too little abstraction; it is retaining multiple declarative registries and identity plumbing beside the authored flow.

Justified compression includes typed phase/subworkflow calls, closed decisions, bounded loops, dynamic map/reducer, human gate/reentry, explicit effects, terminals, and named call-site policies. Dangerous hiding includes route predicate names whose implementation contains business logic, suffix-based ID aliases, handwritten route/interface/override matrices, handler-local retry/cap/model selection, and helpers that mutate workflow state or select a terminal.

### Proposed readability contract

1. **One topology representation.** Runtime graphs, compatibility views, handler indexes, route labels, and projection schemas are generated from the lowered Python topology or are pure downstream consumers. No manually maintained parallel route graph is permitted.
2. **One authored reusable delivery cycle.** Every entry route calls the same source construct. Copy/paste-equivalent branch bodies fail an AST/IR duplication check.
3. **Small primitive set.** The public authoring vocabulary is phase/subworkflow call, closed decision, bounded loop, dynamic map/reducer, human gate/reentry, checkpoint, explicit effect/compensation, terminal, and named policy. Adding a second way to express route ownership requires a conformance rule.
4. **Generated mechanical bindings.** Authors declare semantic keys, typed ports/outcomes, targets, and policy/effect references. Lowering generates runtime handler indexes, stable external binding records, projection metadata, and the cardinality joins among the four identity domains. Product source does not handwrite Run Authority, WBC, or custody IDs.
5. **Local policy.** Retry, timeout, model, cap, fallback, suspension, and effect policy is adjacent to its call site or referenced by one plainly named policy object. No transitive callee owns it.
6. **Closed vocabulary and exhaustiveness.** Adding an outcome in one authoritative vocabulary makes incomplete source branches fail compilation. Runtime or handler-only outcomes fail closed.
7. **Structural complexity budget.** Top-level source should read as an index of named semantic subflows: target at most three nested control levels, one visible call per major semantic, and no route/interface/policy dictionaries embedded beside the flow. As an advisory review trigger, target roughly ≤120 nonblank semantic lines for the top-level function and ≤80 per named subworkflow; exceeding it is acceptable only with an AST/IR report showing no duplicated route/effect/policy authority and an approved readability receipt. The semantics, not the number, remain binding.
8. **Edit-locality budget.** Each future-extension test above changes the topology/policy/effect declaration plus its product body/test; generated artifacts do not count. Requiring manual edits to more than two authoritative declarations is a failure.
9. **Examples and linting.** Ship one complete small example for each primitive and lints for route-bearing handler returns, status/auto route reads, suffix ID heuristics, undeclared effects, hidden retries/caps, manual alias maps, and non-generated projection topology.

This contract intentionally does not optimize away semantic child identity, accepted decision linkage, custody targets, WBC attempts, checkpoint drift bindings, or explicit effects. It removes author ceremony around those facts by generating bindings, not hiding semantics.

## Bounded amendment set

Only these six changes materially increase the probability of reaching and retaining the intended Python-authored system:

| ID | Sprint insertion | Amendment | Closure receipt |
|---|---|---|---|
| A1 | S1, accumulated S3–S7 | Adopt the ordered/multiset golden-trace contract and six scenario families | Same-run composed trace plus mutations in checkout/wheel/cloud |
| A2 | S2 binding, S6/S7 rollout | Validate topology, call-site policy, WBC contract, and installed artifact at every Native action dispatch | One stale worker rejects before body/effect |
| A3 | S5 | Add first-live-effect stop/go before authoritative cutover | Outcome-before-receipt crash reconciles exactly once; legacy writer inert |
| A4 | S6 | Author cancel/publish/deliver/terminal arbitration with CAS preconditions | `NP-GT-006A/B/C` pass and conflicting terminal is rejected |
| A5 | S1 rule, S7 gate | Add readability/edit-locality contract and six extension mutations | Correct edit point is sufficient; handler/auto/metadata-only edit cannot act |
| A6 | S6/S7 | Add rebuildable Native composed-history explanation and repair preflight | All six scenarios explainable; deleting/rebuilding view is behaviorally inert |

No sprint renumbering or scope expansion beyond Native binding is needed.

## Findings deliberately left as sprint-planning detail

The following are useful implementation choices but should not lengthen the epic contract:

- exact decorator/helper spelling, use of `break`/`continue` versus typed loop outcomes, or specific module layout;
- UUID formats, hash canonicalization algorithm, database/table names, event transport, or fixture alias spelling;
- exact PR size, feature-flag implementation, or whether a legacy carrier is deleted immediately versus hard-fenced and quarantined until S7;
- compiler/parser refactors and handler file-size targets beyond the structural readability contract;
- moving individual constants, generating particular registries, or deleting a named metadata module when the one-topology and extension proofs already enforce the result;
- adding generic chain support for per-milestone validators—the plan explicitly records that limitation and correctly uses mandatory receipts replayed by S7;
- arbitrary true concurrency optimization; deterministic dynamic batching and sequential fallback remain valid;
- graph visualization or a new operator UI—the required incident view may be CLI/JSON and is a disposable projection;
- all generic Run Authority, Custody, WBC, recovery, query, projection, and conformance substrate mechanics accepted with M11.

## Findings rejected after comparison with the prior audit

I formed the assessment above before reading `.tmp/native-parity-sensecheck-round2/final-audit.md`. Its five bounded amendments are present in the current plan and are not repeated as new findings:

- the validator consumes the complete proof map and binds its pre-receipt hash (`corrective-plan.md:450-453`, `:488-490`);
- every typed decision maps to the exact accepted Run Authority decision and consumed action (`:132-138`, `:461-464`);
- checkpoint/reentry binds program, policy, and WBC contract drift (`:140-145`, `:474-477`);
- S3 has an internal prep→plan stop/go/adoption receipt (current S3 brief and plan `:287-311`);
- `add-note`/annotation is an exact-target, authority/custody-checked, durable WBC effect with explicit `no_route_change` (`s6...md:14-18`, `:59-65`).

I also reject as already bounded: index-only child identity (`corrective-plan.md:472-473`), a sequential tiebreaker masquerading as parallel, a one-pass duplicated review cycle (`s5...md:48-55`, `:67-72`), auto/status routing (`s6...md:29-32`, `:59-65`), handler/component mutation authority (`corrective-plan.md:479-480`), and proof records manufactured from pre-labelled rows (`:439-448`).

Finally, reviewer proposals to redesign generic M11 quarantine, WBC transactions, custody leases, projection infrastructure, or chain validation are out of scope. Native Parity must bind to and prove the accepted substrate; it must not recreate it.

## Final position

This is not a gameable architecture in need of another corrective epic. It is a strong plan whose remaining risk is **composition and retention**, not requirements coverage. Adopt A1–A6, preserve the safe strangler order, and the written gates become difficult to satisfy without actually delivering the desired end state:

> one readable Python-authored semantic topology; one exact authority-decision history; one current exclusive custody owner; one durable boundary/effect history; disposable explanations that never become authority.
