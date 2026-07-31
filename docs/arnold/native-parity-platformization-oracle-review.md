# Oracle Review Guide — Native Parity and Workflow Platformization

> **Sequencing amendment — 2026-07-30.** Sections that show the pre-C1/C2
> Native sequence are historical review context. The controlling execution and
> ownership strategy is
> `docs/arnold/completion-spec-sequencing-and-ownership.md`: bootstrap first,
> then Native `S1,S2F,C1,C2,S2R,...,S7`, then Platformization. Oracle findings
> remain inputs, but old milestone counts must not overwrite the prepared
> initiatives.

## Purpose

This is the entry point for an outside technical oracle reviewing two prepared,
not-yet-launched Arnold epics and one small prerequisite bootstrap:

1. **Megaplan Native Parity Corrective** makes Megaplan's authored `.pype`
   topology the complete product-control-flow authority while preserving its
   accepted behavior and binding execution to the existing Run Authority,
   Custody, and Workflow Boundary Contracts substrate.
2. **Native Workflow Platformization** turns the format, runtime boundaries,
   and selected proven patterns into a product-neutral workflow-component
   platform suitable for third-party developers.

The first oracle review accepted the architecture and found proof-timing,
classifier, and milestone-sizing gaps. This revision incorporates those
findings: a generic pre-merge/post-merge milestone-gate bootstrap; receipt
consumption at cutover APIs; split Native compiler/runtime and shadow/live
effect milestones; split Platform compiler-core/DX milestones; decidable
executable-closure hashing; finite route discriminants; bounded incomparable
progress; effect-class proof; namespace/fork authority; store-capability
isolation; governed trace-field amendments; independent profile derivation;
and executable unrelated-consumer independence proof.

The review is not asking whether the documents are detailed. It is asking:

- Is the target architecture coherent?
- Are the irreversible authoring, identity, packaging, and lifecycle decisions
  the right ones?
- Do the two executable chains, in their declared order, actually reach that
  target?
- Can either chain become “green” while retaining hidden topology, ambiguous
  identity, dual authority, product coupling, or unproven durability?
- Are any responsibilities missing, duplicated, sequenced too late, or too
  large for their assigned milestone?

## Requested oracle output

Return:

1. an overall verdict: **execute as written**, **execute after named edits**,
   **resequence/split named milestones**, or **reject the direction**;
2. the five strongest decisions in the design and why they survive challenge;
3. every material ambiguity where two incompatible implementations could both
   claim compliance;
4. every “green but wrong” implementation that could pass the planned gates;
5. a milestone-by-milestone reachability assessment, including hidden
   prerequisites and unrealistic workload;
6. the smallest concrete edits needed before launch, with exact packet-relative
   file and section references;
7. decisions that must be frozen before third-party publication versus those
   that should remain conventions; and
8. any additional proof the oracle needs before it can reach a firm verdict.

Distinguish throughout:

- the **currently proven pre-corrective baseline**;
- the **Native Parity target and future evidence**;
- the **Platformization experimental candidate**; and
- the **eventual stable platform claim**.

Plans and contracts are not evidence.

## Packet reading order

| File | Why it is present |
| --- | --- |
| `00_READ_ME_AND_QUESTIONS.md` | This guide: end state, two-chain map, conformance delta, review questions, and requested verdict shape. |
| `01_FULL_PIPELINE_AND_END_STATE.md` | Holistic representation of Megaplan's product flow, runtime, authority, durable state, effects, observability, migration, and platform endpoint. |
| `02_PYPE_AUTHORING_CONTRACT.md` | Sole normative `.pype` file/import/step/helper/identity/package/migration/preview/tooling contract shared by both epics. |
| `03_PYPE_DECISION_RECORD.md` | Design history, rejected alternatives, adversarial cases, and the rationale behind one workflow per `.pype`. |
| `04_NATIVE_PARITY_EXECUTION_PLAN.md` | Full Native migration sequence, partial cutovers, races, rollback conditions, proof gates, and final acceptance. |
| `05_NATIVE_PARITY_CHAIN.yaml` | Exact executable Native milestone ordering and dependencies. |
| `06_NATIVE_GOLDEN_TRACE_CONTRACT.md` | Independent semantic/trace oracle used to prove parity and detect hidden route ownership. |
| `07_PLATFORMIZATION_CONTRACT.md` | Product-neutral component, lifecycle, composition, evolution, execution-mode, proof, and publication contract. |
| `08_PLATFORMIZATION_CHAIN.yaml` | Exact executable Platformization ordering and final conformance gate. |

The milestone briefs are deliberately not bundled. The execution plan and
platform contract state their obligations; the chain files show the actual
owners and ordering. Briefs are available for drill-down if the oracle
identifies a milestone-specific concern.

## One-page target end state

### Authored truth

```text
Megaplan / third-party package
  .pype files
    exactly one canonical @workflow per file
    optional private file-local @step definitions
    optional digest-bound deterministic helpers
    static imports of canonical workflows and typed shared .py definitions

  .py files
    reusable typed steps with ordinary Python/third-party imports
    declared effect adapters
    schemas, immutable typed policies, prompts, types, deterministic helpers
    no admitted workflow topology
```

Every durable root or child workflow has its own `.pype`. “Subworkflow” is only
the hosting role of a workflow invoked by another workflow. It is not another
decorator, source kind, identity system, or publication surface.

### Compilation and package truth

```text
.pype source
  -> static parser/index/linker (never executes author source)
  -> typed product-neutral workflow IR
  -> generated WorkflowManifest + exact source map
  -> canonical package descriptor + transitive lock
  -> one frozen logical workflow key + executable contract digest
```

The existing canonical Arnold descriptor owns:

- optional `default_pipeline`;
- cross-package visibility/allowlisting of canonical workflows;
- source/resource/descriptor correspondence;
- component and dependency locks; and
- the append-only identity migration log.

The executable digest uses a versioned conservative canonical closure:
normalized compiler IR/AST plus every statically reachable declared
dependency, constant, schema, policy, prompt, model/tool binding, and
private/shared behavior slice, minus only a closed syntactic exclusion list.
It does not attempt undecidable semantic equivalence.

A component digest covers its own canonical closure and direct dependency
contract requirements. A separate transitive graph-lock digest pins the exact
selected executable digest of every child/shared dependency. Admission,
actions, effects, checkpoints, replay, source maps, and proof bind both, so a
compatible child substitution does not cascade component identity through all
ancestors but can never silently change a pinned run.

Registry governance owns distribution coordinates and authorized fork lineage.
A legitimate new package version may retain its logical key with a new digest;
ambiguous candidates under one resolved coordinate/lock fail.

`default_pipeline` selects a workflow, not a root-result mapping. The invoking
admission binding supplies exactly one total adapter unless the producer
descriptor explicitly names a default adapter.

There is no file export table, multi-workflow `.pype`, library-only `.pype`,
`__all__`, declaration-order root, filename-derived identity, workflow
re-export, or import-time registration.

### Runtime and authority truth

```text
admitted manifest + lock + executable digest
  -> Run Authority: permission, accepted decisions, coordinator fences
  -> Custody: current exact-target lease and epoch
  -> WBC: exact-version execution/effect history
  -> checkpoints: semantic reentry and durable local state
  -> effect intent/outcome/reconciliation
  -> raw causal events
  -> disposable projections and explanations
```

Source owns product routes. Generated artifacts preserve but do not author
routes. Run Authority grants and accepts decisions. Custody owns temporary
exclusive action rights. WBC and effect records preserve durable boundary
truth. Evidence, status, logs, projections, handlers, CLI, schedulers, and
repair systems never grant authority or select a product route.

Policies use one canonical envelope—kind/schema, recursively immutable values,
scope/attachment, source provenance, precedence/override and digest. Inline or
call-site policy requirements affect the caller component digest; imported
policies have their own executable identity and exact selection in the graph
lock. Shared step internals retain normal Python import freedom under pinned
dependencies/environment/features/plugins and declared effect boundaries.

Raw events also carry stable run, occurrence, generation, attempt,
platform-agent-session, model/tool/effect, trace/span, usage/cost and protected
log/transcript correlation keys. Operators can navigate from source/step
attempt to agent records and back to the owning occurrence/source and optional
consuming decision/terminal. Reverse indexes are rebuildable projections;
complete audit means durable-boundary causality, not every Python instruction.

### Identity truth

Logical workflow identity is:

```text
(distribution_name, logical_workflow_name)
```

The logical name is explicit `@workflow(id=...)` when present, otherwise the
decorated function name. Paths, filenames, wheel resources, and aliases are
provenance.

Executable identity adds ports/outcomes, hostability, topology, policies,
child/shared references, private code/helper slices, and behavior-relevant
prompt/model/tool bindings.

- Pure physical relocation with the same logical key and behavior digest is a
  provenance update.
- Rename, extraction, inline, hostability change, private/shared promotion, or
  behavior drift requires explicit compatibility, migration, new-run, or
  quarantine disposition.
- Exact pinned legacy artifacts remain read-only resolvable while live
  occurrences require them; they cannot create new durable work.

### Developer experience truth

The platform is strict about durable claims, not experimentation:

- ordinary `.py @workflow` may run only in explicit ephemeral preview;
- preview uses fresh identity and fake/ephemeral-only effects; durable sandbox
  is a separate explicit mode with isolated non-production history;
- preview cannot checkpoint, resume, admit, compare authoritatively, promote,
  publish, or certify;
- unsupported hidden topology/effects reject in durable modes;
- every diagnostic names source spans, the violated responsibility, the claim
  that cannot be made, and a supported rewrite;
- extract child, inline child, and promote-private-step refactors update source,
  descriptors, locks, provenance, and migrations atomically; and
- editor/navigation/format/lint/topology tools use the production parser rather
  than maintaining a second route model.

## Target Megaplan organization

```text
arnold_pipelines/megaplan/workflows/
  workflow.pype
  plan_quality/
    cycle.pype
    critique.pype
    gate.pype
    tiebreaker.pype
    steps.py
    policies.py
    types.py
  delivery/
    cycle.pype
    execute.pype
    execute_batch.pype
    review.pype
    steps.py
    policies.py
    types.py
  control/
    steps.py
    policies.py
```

Each `.pype` contains one workflow. `control/` intentionally contains no
workflow: control operations are typed leaves whose resulting routes remain
visible in `plan_quality/gate.pype` or `delivery/cycle.pype`.

A region is extracted into its own workflow when it has any one of:

- declared outcomes the parent routes on;
- its own suspension/checkpoint/retry lifecycle;
- reuse;
- independent testing or provenance needs; or
- semantic child identity that must survive parent refactoring.

Directory taxonomy, filename matching, line counts, and file-count heuristics
remain guidance rather than identity or admission rules.

## Why this format was selected

The adopted model is hardened Alternative A: one workflow per `.pype`, private
local steps permitted, and `.py` workflows confined to non-durable preview.

Its central benefit is that authors, reviewers, the compiler, and the replay
engine find durable topology by the same operation: enumerate `.pype` files and
follow static canonical imports. A source-file diff normally corresponds to one
workflow identity plus its explicit importers.

The acknowledged cost is boundary ceremony and possible file proliferation.
Private local steps reduce small-app ceremony; domain directories reduce
navigation cost; preview supports migration/exploration; and identity-aware
extract/inline/promote refactors are treated as platform viability
requirements, not optional polish.

The oracle should reject this choice if those mitigations are insufficient or
if a multi-workflow format can preserve equally mechanical topology, identity,
review, packaging, and replay semantics without a hidden semantic index or
second production authoring surface.

## Current baseline → Native Parity → Platformization

| Concern | Proven/current baseline | Native Parity target | Platformization target |
| --- | --- | --- | --- |
| Source suffix | `.pypeline` and implemented Python-shaped v2 baseline | `.pype` is the sole live durable suffix; legacy exact-pin reader only | Stable public `.pype` authoring/package surface |
| File meaning | Current compiler/runtime behavior; old representation ledger | Exactly one canonical workflow per `.pype` | Same rule across unrelated packages |
| Workflow placement | Legacy authored subflow and Python-shaped forms exist | Every durable root/child split into one `.pype` | Generic converter and semantic refactors |
| Local/shared leaves | Existing boundaries are incomplete | Private local steps/helpers plus shared `.py` leaf law | Public SDK, editor, and package enforcement |
| Identity | Existing path/component/manifest precedents | Logical key, executable digest, provenance, migration log | Cross-package evolution and compatibility |
| Runtime meaning | Existing native/M11 substrate | Product-neutral constructs bound to RA/Custody/WBC | Shared lifecycle/composition runtime |
| Product topology | Builder/handler/metadata residue remains a risk | Megaplan `.pype` topology becomes load-bearing; old carriers fenced | Extracted patterns have no Megaplan reverse imports |
| Reuse proof | Megaplan-only | Candidate inventory and exact handoff | First extraction, unrelated consumer, substitution and resume proof |
| Stability | Prior baseline conformance only | No new stable platform claim | S6 alone may promote proven surfaces |

## Two-epic execution map

### Epic 1 — Megaplan Native Parity Corrective

Before the ten-milestone chain, a one-sprint generic bootstrap adds
`conformance_gate`: validate the proposed tree before merge eligibility, rerun
against merge HEAD, and content-address every binding. It also adds a typed
post-validation transition slot, giving one fixed order: pre-merge validation
→ merge → merge-HEAD readiness validation → receipt-consuming transition →
post-transition verification → completion. Authority-changing milestones must
use that slot; milestone validation alone is not authority.
The bootstrap cannot self-host that new guarantee: its one PR uses required
external pre-merge CI, independent review, and manual merge, with the current
post-merge final gate retained only as a backstop. Its launch requires a trusted
bootstrap-PR attestation binding the PR/head/merged tree, CI check/suite,
reviewer approval, and implementation diff; local or no-PR execution cannot
substitute a self-authored marker.

| Milestone | Owns | Blocking output |
| --- | --- | --- |
| S1 | Admit exact M11 substrate; inventory/stage `.pypeline` → `.pype` while keeping the current authoring path selected; freeze format, identity, helper/step/import, typed-policy, audit-correlation, mode, semantic, and expected-red contracts | Executable baseline and target corpus; no local authority substitute |
| S2F | Implement exact-one compiler/linker, ordinary-step dependency locking, typed policy lowering, conservative executable-closure identity, descriptor/namespace integration, converter, diagnostics, and minimal preview; select `.pype` only through the typed transition after readiness proof | Readiness, transition, and post-transition GO-FORMAT receipts |
| S2R | Implement generic durable constructs, portable event/correlation history, and admitted RA/Custody/WBC, CAS, checkpoint/effect, and restore semantics | GO-0; neutral runtime and bidirectional audit proof |
| S3A | Land prep/plan/critique non-authoritatively, then cut over through the typed transition | GO-1A readiness, transition, post-transition verification, and exclusive resume-plane binding |
| S3B | Land gate/revise/cycle, then transition producer/seam/fence ownership and remove the temporary front-half scaffold | GO-1B readiness, transition, post-transition verification, and complete front-half authority |
| S4 | Land tiebreaker/finalize/human durable reentry, then transition the producer/seam/fence set | S4 readiness, transition and post-transition receipts; outgoing delivery seam |
| S5A | Build delivery in shadow; inventory every effect-protocol class; prove each directly or by independently verified equivalence | Per-class GO-2; no live cutover |
| S5B | Make the typed transition consume current readiness plus S5A GO-2; cut over execute/review/rework and reconciliation once | Transition receipt, post-transition live delivery proof, and old writers fenced |
| S6 | Land override/reconfigure/auto/recovery leaves, then transition control authority and demote downstream consumers | GO-3 readiness, transition and post-transition proof; no hidden control topology |
| S7 | Cumulative checkout/wheel/cloud conformance and removal/inertness proof | GO-4, final proof map, completion manifest, Native→Platformization handoff |

At each partial cut:

- exactly one old/candidate writer and decision consumer is authoritative;
- candidate comparison is quarantined, non-resumable, and effect-inert;
- action/effect acceptance requires current RA fence and exact Custody epoch;
- WBC evidence cannot grant;
- failure before a gate leaves the old scoped carrier authoritative;
- accepted earlier cuts are not silently rolled back by later failures; and
- seams have explicit expiry/deletion owners.

### Handoff

Platformization cannot launch from a nominally completed Native chain. It
requires a content-addressed completion manifest and handoff binding:

- candidate/dependency classification;
- exact typed ports/outcomes/state/policy/effect contracts;
- adopted `.pype` contract/compiler/diagnostic/converter/minimal-preview
  versions;
- accepted GO-FORMAT, source/package, identity/migration, and legacy receipts;
- source-to-runtime golden adapters and raw trace schema;
- diagnostic/DX corpus and measured baselines;
- certified production CAS/adapter/producer/proof-registry provenance;
- zero-Megaplan-import proof for generic primitives;
- coupling and exclusion evidence; and
- every temporary seam's expiry/inertness proof.

Platformization consumes and genericizes those surfaces. It does not redo the
Megaplan product migration or manufacture a second proof baseline.
Its launch uses the bootstrap-added
`chain_completed + require_manifest + required_proof_artifacts` assertion to
match the exact handoff path and current hash to one validated predecessor
proof row; text presence and standalone existence are not evidence.

### Epic 2 — Native Workflow Platformization

| Milestone | Owns | Blocking output |
| --- | --- | --- |
| S1 | Verify Native handoff; freeze experimental component/lifecycle/composition/evolution/mode/proof, typed-policy, dependency-pin and portable-correlation standard plus invalid corpus | Reproducible candidate; explicit S2A vs S2B ownership |
| S2A | Implement product-neutral runtime, lifecycle, admission, authority, state, effects, traces, locks, portable event/correlation indexes, and faithful local-kit semantics | Readiness receipt, typed canonical-runtime transition, and post-transition proof; S2B need not invent runtime or authority meaning |
| S2B | Productize `.pype` frontend/linker, ordinary step-dependency locking, typed policy envelope/lowering, package correspondence, identity, converter, and transactional refactors | Core authoring/package SDK; S3 need not invent compiler semantics |
| S3 | Complete CLI/SDK, formatter/linter, editor/navigation/tracebacks, bidirectional occurrence↔agent/log inspection, full corpus, install equivalence, and pinned DX benchmarks | Viable developer and audit-navigation surface; S4 need not invent tooling |
| S4 | Extract first reusable patterns, prove them while non-authoritative, then use the typed transition and post-transition verifier to migrate Megaplan's binding/lock | One correct product uses shared implementations |
| S5 | Build unrelated consumer, vary domain and composition shape, substitute implementation, and separately test new-instance and resume evolution | Product leakage exposed or removed; no stable claim |
| S6 | Incorporate S5 findings, run cumulative readiness conformance, publish through the typed transition, then rerun final conformance on the published state | Only proven versions become stable; verified completion manifest and registry |

## Milestone audit digest

This is the compact substitute for the seventeen epic milestone briefs plus the
one bootstrap brief. The oracle
may request a specific brief after identifying a concern, but the ZIP should be
sufficient for a first reachability and sequencing verdict.

### Native Parity

| Milestone | Critical inputs | Major work bundles | Machine evidence / artifacts | Do not close when | Declared load and review concern |
| --- | --- | --- | --- | --- | --- |
| S1 | Exact completed M11 manifest/proof, installed revision, current compiler/runtime/source inventory | Capability probes; staged suffix/package/source-map inventory; exact-one format and identity contract; semantic checker/golden/proof schemas; expected-red and DX corpus | M11 intake and S1 stage receipts; staged migration; target corpus; diagnostic and proof-map schemas | M11 is nominal/shadow-only; local RA/Custody/WBC substitute exists; S1 prematurely changes the selected suffix; live `.pypeline` authoring remains unclassified; evidence is labels/hashes rather than executed behavior | `partnered-5 / extreme / max`; broad contract-freeze milestone with prerequisite-audit risk |
| S2F | S1 format/identity corpus and staged migration | Parser/linker; private/shared and leaf laws; converter; minimal preview; conservative closure digest; descriptor/namespace/root-adapter integration; receipt-consuming suffix/admission transition | GO-FORMAT readiness, transition, post-transition conformance/traceability/proof receipts | Discovery executes source; digest classifier is curated; path becomes identity; fork authority is ambiguous; preview reaches admitted capabilities; suffix selects before readiness or post-transition verification | `partnered-5 / extreme / max`; format/identity sprint now isolated from runtime |
| S2R | Accepted GO-FORMAT plus admitted M11 adapters | Typed decisions/loops/fanout/retry/humans/checkpoints/effects; faithful sandbox; production CAS/restore and three-plane binding | GO-0; neutral reference traces; store-capability, restore and contention receipts | It forks the compiler; generic code imports Megaplan; fake CAS proves authority; GO-FORMAT is not revalidated; GO-0 is stale/self-declared | `partnered-5 / extreme / max`; runtime/fault matrix remains broad but coherent |
| S3A | Green GO-FORMAT and GO-0; S2R runtime; old/candidate prefix inventory | Root plus critique files; prep/clarification/plan/critique candidate; exclusive resume-plane binding; WBC producer relocation; quarantined comparison; typed transition | GO-1A readiness, transition, and post-transition proof; partial golden trace; old-carrier reachability | Both planes can resume/write; comparison can acquire effects/authority; route reconstruction remains in builder/handler; transition or verifier is skipped | `partnered-5 / extreme / max`; first live authority cut and highest rollback sensitivity |
| S3B | Accepted post-transition GO-1A and typed gate seam | `gate.pype` and `cycle.pype`; gate/revise/planning loop; total outcomes/precedence; typed producer/seam/fence transition; post-transition carrier/scaffold retirement | GO-1B readiness, transition, post-transition proof; complete front-half golden rows; arbitration race/restore receipts | Any front-half carrier or scaffold remains route-capable; gate outcomes/defaults are incomplete; old and new writers overlap; deletion precedes transition | `partnered-5 / extreme / max`; dense policy and race semantics after an irreversible prefix cut |
| S4 | Accepted post-transition GO-1B and tiebreaker/finalize seam | `tiebreaker.pype`; bounded synthesis/decision; human suspension/reentry; finalization/escalation; migration decisions; typed atomic producer/seam/fence transition | Tiebreaker/finalize golden rows; duplicate-human and drift receipts; readiness/transition/post-transition S4 receipts; delivery seam | Resume lacks exact RA/Custody/WBC binding; duplicate human decisions can both win; pinned drift silently resumes; old path is removed before transition; effects repeat | `partnered-5 / extreme / max`; durable human and migration semantics dominate |
| S5A | Accepted S4 seam and generic delivery primitives | Delivery workflow files in shadow; complete future-live `NP-GT-004/005` route/cancellation/rework matrix; exhaustive effect-protocol inventory and equivalence classes | Per-class and full-behavior GO-2; shadow traces; crash/reconciliation/equivalence and old-reader reachability receipts | Any live effect occurs; a harmless proxy authorizes a stronger class; effect or scenario inventory is incomplete; first-time behavior is deferred to S5B; shadow promotes | `partnered-5 / extreme / max`; proof-only split makes the irreversible boundary reviewable |
| S5B | Accepted GO-2 plus current readiness proof | Typed transition consuming both receipts; admitted execute/review/rework; cancellation and reconciliation; old-writer fence | Transition and post-transition delivery golden/cutover/adoption/partial-restart receipts | Transition does not validate both exact receipts; dual-write occurs; old readers can influence action; accepted effects repeat | `partnered-5 / extreme / max`; live adoption remains high-risk but no longer shares its proof sprint |
| S6 | Accepted delivery cut and control action inventory | Typed override/reconfigure/human/auto/recovery leaves; visible caller routes; typed control-authority transition; remove final seam; make CLI/auto/projections downstream | GO-3 readiness, transition and post-transition proof; route-mutation, writer/repair/restore receipts | Auto, status, projection, `_core`, handler, or repair code can choose routes/grant; a control step invokes topology; transition/verification is bypassed | `partnered-5 / extreme / max`; cross-surface deletion/inertness proof is the main risk |
| S7 | All accepted cuts, golden contract, old/current source inventory | Cumulative source/lowered/runtime/action/effect equality; package/install/cloud proof; legacy reader expiry; seam/dead-carrier proof; final handoff | New Native Parity conformance/traceability/validator, final proof map, GO-4, completion and Platformization handoff manifests | Final gate uses the old `.pypeline` ledger; any live legacy/hidden route remains; evidence is normalized-only/self-certified/stitched; handoff omits exact compiler/identity/legacy receipts | `partnered-5 / extreme / max`; evidence integration is large but should not become first-time implementation |

### Platformization

| Milestone | Critical inputs | Major work bundles | Machine evidence / artifacts | Do not close when | Declared load and review concern |
| --- | --- | --- | --- | --- | --- |
| S1 | Accepted Native completion/handoff and reusable-candidate inventory | Verify handoff; freeze experimental descriptor/lifecycle/composition/evolution/mode/profile standard; reference models; invalid/mutation/DX corpus; extraction classification | Intake receipt; candidate schemas; conformance/traceability skeletons; proof-map schema | Any rule is prose-only; S2A/S2B ownership is ambiguous; fake CAS becomes production proof; candidate is called stable | `apex / extreme / max +prep`; foundational contract breadth and inherited-evidence verification |
| S2A | S1 candidate and admitted Native/M11 runtime substrate | Product-neutral validation/lowering interfaces; lifecycle/admission/authority/state/effects/checkpoints/locks/traces; faithful local kit; real-store contention; typed canonical-selection transition | Runtime conformance rows; crash/race/CAS/restore receipts; readiness/transition/post-transition receipts; S2A handoff | It creates a second parser/package model; local fakes diverge from production; authority/lifecycle meaning remains for S2B to invent; candidate becomes selectable before verified transition | `apex / extreme / max`; broad runtime kernel and fault matrix |
| S2B | Native frontend, S1 corpus, S2A runtime handoff | Productize parser/linker/index; package/source correspondence; canonical identity/namespace; converter and transactional refactors | Core format families; refactor atomicity; install/source correspondence; S2B handoff | It forks Native compiler/runtime/descriptor; private members leak; S3 must invent core semantics | `apex / extreme / max +prep`; core is deliberately limited to S4-blocking capabilities |
| S3 | S2B core and S2A faithful local kit | Public CLI/SDK; preview/test; formatter/linter; editor/navigation/traceback; full corpus; install forms; timed DX | Complete format/DX families, benchmark and unfamiliar-author receipts, S3 handoff | Editor/CLI uses alternate compiler; refactors need manual generated edits; baselines are set after results; S4 must invent tooling | `apex / extreme / max +prep`; separate product-quality milestone |
| S4 | S2B/S3 experimental SDK and selected Native candidates | Extract evaluator/refinement/human/effect-safe patterns; remove Megaplan defaults; prove while inactive; migrate the active binding/lock through the typed S4 transition; prove isolation/recomposition and post-transition state | Golden equivalence, concurrency/isolation, install, local-kit, readiness/transition/post-transition extraction/adoption receipts | Reverse imports/copies remain; identity/layout/migration is redefined during extraction; only one composition shape passes; new binding becomes authoritative before verified transition | `partnered-5 / thorough / xhigh`; first consumer proof is narrower but migration-sensitive |
| S5 | S4 patterns and all experimental contracts/tooling | Build unrelated domain; novel shapes/bindings; independent implementation; new-instance substitution; separate pinned resume/migration/quarantine; cross-consumer explanation | Challenge report; compatibility receipts; migration/quarantine evidence; amended cumulative proof | Consumer is renamed Megaplan; new-instance proof is reused for resume; compatibility shims hide divergent topology; leakage is deferred | `apex / extreme / max +prep`; adversarial scope is intentionally large and must remain genuinely independent |
| S6 | Accepted S5 amendments and cumulative proof | Freeze only proven public surfaces; evolution/retention/GC; docs/DX/SLOs; registry governance; full closure/acceptance suite; final-readiness gate; typed stable-publication transition; post-transition final verification | Readiness/transition/final receipts, validator, conformance/traceability, proof map, component manifests, registry, completion manifest | Any applicable row is red/missing/fake/self-certified; effective profiles exclude failures; transition precedes S5/readiness or post-verification is skipped; old pinned artifacts disappear | `premium / thorough / xhigh`; certification must aggregate rather than invent missing functionality |

## Concrete implementation ownership

| Surface | Native S2F/S2R | Platform S2A | Platform S2B/S3 | Steady-state owner |
| --- | --- | --- | --- | --- |
| Parser/lowerer | S2F implements adopted grammar and Megaplan-required lowering | Consume typed IR; no parallel parser | S2B productizes same frontend/linker | Arnold workflow platform |
| Runtime/lifecycle | S2R binds generic constructs to admitted substrate | Promote and own shared lifecycle/admission/state/effect meaning | Consume; no second runtime | Arnold workflow platform |
| Diagnostics/source maps | S2F ships the GO-FORMAT catalog | Runtime/admission faults | S2B core; S3 completes editor/navigation/traceback | Arnold workflow platform |
| Descriptor/discovery/lock | S2F extends canonical owner after inventory | Enforce frozen identity/lock | S2B productizes selection/correspondence | Arnold workflow platform |
| Identity/migration | S2F implements keys/digests/legacy mapping; S2R enforces runtime pins | Enforce compatibility/migration semantics | S2B productizes refactors/APIs | Arnold workflow platform |
| Converter/preview | S2F ships converter/minimal preview | Faithful sandbox/fork hooks | S2B refactors; S3 public preview/test SDK | Arnold workflow platform |
| CLI/editor | S2F makes check/compile/inspect work for cutover | Expose runtime inspection | S3 owns generic CLI/editor/format/lint | Arnold workflow platform |
| Megaplan sources/bindings | Own split, migration, parity, handoff | Conformance client only | Tooling regression client only | Megaplan package |

A milestone is wrong if it creates a second compiler, descriptor, lock format,
identity registry, migration log, route catalogue, lifecycle engine, or local
test semantics.

## Conformance and evidence delta

### What the earlier chain proved for its own baseline

The repository contains:

- `docs/arnold/megaplan-native-representation-conformance.yaml`;
- `docs/arnold/megaplan-native-representation-traceability.yaml`;
- `docs/arnold/megaplan-native-representation-conformance-report.md`; and
- `scripts/validate_native_representation_conformance.py`.

These are content-addressed closeout evidence for the older
`native-platform-followup` baseline. They intentionally identify `.pypeline` as
the canonical source suffix and close earlier composition/platform milestones.
They are historical baseline/audit evidence, not declared launch prerequisites
and not proof of the target described in this packet. Only exact compatible
rows that a new gate independently reconsumes may satisfy a new obligation.

They are not bundled because presenting them beside the target without this
distinction invites a false conclusion that the corrective work is already
implemented. They must not be rewritten to manufacture `.pype` proof.

### What Native Parity must newly prove

S2F is required to create:

```text
docs/arnold/pype-authoring-conformance.yaml
scripts/validate_pype_authoring_contract.py
.megaplan/initiatives/megaplan-native-parity-corrective/
  go-format-receipt.json
```

The receipt schema is `arnold.megaplan.go_format_receipt.v1`. S2R is required
to reconsume it independently. The validator must recompute rather than trust
declared status.

The chain-engine gap is now an explicit pre-epic bootstrap, not deferred work:
`.megaplan/initiatives/megaplan-chain-milestone-gates/chain.yaml`. It must add a
typed non-shell `conformance_gate`, run it before PR readiness/auto-merge,
rerun against merge HEAD, and reject stale/unbound evidence. The Native chain
declares intermediate gates, while Platformization declares those gates plus
the bootstrap-added exact predecessor-artifact assertion. Both chains are
intentionally not runnable by the old final-only parser. Native's
`chain_completed + require_manifest` precondition makes the bootstrap
mandatory, and Platformization's
`required_proof_artifacts` field binds its exact handoff. Irreversible cutovers
additionally occupy the bootstrap-defined typed transition phase and must pass
its post-transition verifier. S5A/S5B separates GO-2 proof from live adoption.

S7 creates and consumes:

```text
docs/arnold/megaplan-native-parity-conformance.yaml
docs/arnold/megaplan-native-parity-traceability.yaml
scripts/validate_megaplan_native_parity_conformance.py
.megaplan/initiatives/megaplan-native-parity-corrective/final-proof-map.json
```

That new gate produces the final-conformance receipt, completion manifest, and
Native→Platformization handoff. It proves:

- `.pype` is the sole live durable authoring/package suffix;
- exact-one, privacy, leaf-law, import, recursion, helper-effect, identity,
  migration, descriptor-correspondence, preview, and legacy negatives;
- source → lowered topology → runtime occurrence → accepted decision/action/
  effect set equality;
- raw multiplicity/causality before normalization;
- checkout/editable/wheel/sdist/cloud equivalence;
- old carriers and temporary seams are deleted or structurally inert;
- every authority/effect boundary uses admitted production substrate; and
- every target semantic row passes its negative mutation.

### What Platformization must newly prove

S1 creates the product-neutral conformance/traceability skeletons, the stage
validator, and honest red rows. S1–S5 each run a typed pre-merge/post-merge
`conformance_gate` over the rows owned so far. S2A, S2B, and S3 populate
runtime, core-authoring, and DX/tooling evidence. S2A's canonical runtime
selection and S4's active Megaplan binding migration run in declared typed
transitions and pass separate post-transition gates. S4 and S5 add extraction
and unrelated-consumer proof. S6 runs final readiness, performs stable
publication as its typed transition, and reruns final conformance on the
published state. S6 alone produces:

```text
docs/arnold/native-workflow-platform-conformance.yaml
docs/arnold/native-workflow-platform-traceability.yaml
scripts/validate_native_workflow_platform_conformance.py
.megaplan/initiatives/native-workflow-platformization/final-proof-map.json
.megaplan/initiatives/native-workflow-platformization/completion-manifest.json
```

The final validator must consume all 11 closure clauses and all mechanically
applicable 37 acceptance families. Megaplan-only, fake-CAS, normalized-only,
self-certified, hash-only, preview/comparison, or incomplete-profile evidence
cannot certify stability.

## Principal technical risks to challenge

1. One workflow per file may impose too much ceremony without the S2B refactors.
2. “Private step” could become ambiguous unless addressability, testing, digest
   folding, and promotion are mechanically exact.
3. Static canonical imports across editable/wheel/sdist installs may require a
   semantic module resolver that accidentally becomes a second identity layer.
4. Registry-owned distribution coordinates and fork lineage may still be
   insufficient under package rename, ambiguous locks, or multi-version
   installation.
5. The canonical descriptor owner may remain unclear in the current pack/lock
   implementation, inviting a parallel package format.
6. Preview-only `.py` workflows may leak durable-shaped artifacts or effects.
7. The P0 gate bootstrap could validate at the wrong lifecycle point, skip the
   typed transition/post-transition verifier, or let a handler accept a
   filename/status instead of the exact receipt.
   Its own non-self-hosted external-CI/manual-merge exception could also become
   ceremony rather than a manifest-bound check and review record.
8. Partial product cutovers could leave dual writers, resumable comparison
   history, or ambiguous rollback after an accepted prefix cut.
9. Golden trace normalization could hide multiplicity, race, or causal loss.
10. S2A/S2B/S3 could drift into two compilers or local execution models despite
    the promote-in-place contract.
11. First-wave extracted “patterns” may encode Megaplan policy despite zero
    direct imports.
12. Platform S5 may be too easy to game with a ceremonial second consumer or
    new-instance compatibility presented as resume compatibility.
13. S6's effective-profile derivation could exclude the very tests that would
    fail a candidate.
14. A digest exclusion, open route discriminant, effect-class equivalence, or
    field-table amendment may be authored by the same producer it benefits.
15. The total combined workload may be larger than the declared milestone
    sizing even when the dependency order is sound.

## Remaining execution inputs, not unresolved design choices

Native S1 must close several evidence inputs before it freezes its corpus: the
exact accepted M11 completion/capability receipt, generated exhaustive
`.pypeline` and route-carrier inventory, current canonical pack/lock owner,
pre-result DX baseline, and the determination of whether Megaplan has a real
model-directed durable inner-call consumer. The earlier oracle also referenced
numbered transitions 2, 3, 5, and 7 whose source text was absent. S1 must obtain
and map that source or issue a content-addressed source-gap disposition that
forbids dependent claims; it must not invent scenarios.

These are first-milestone intake evidence, not reasons to reopen the authoring
architecture. Milestone labels are proof boundaries rather than calendar
promises. If prep shows an owner cannot close its semantic and adoption proof
coherently, split before implementation and preserve the same receipt order;
do not defer half a gate to a later milestone.

## Questions for the oracle

### Authoring, composition, and identity

1. Is one workflow per `.pype` the correct long-term tradeoff for both small
   applications and Megaplan-scale/third-party packages, given that refactoring
   and editor tooling are prerequisites?
2. Are private file-local steps semantically crisp enough—identity, digest
   folding, testing, source mapping, promotion to shared `.py`, and migration?
3. Can every durable root/child be mechanically enumerated from `.pype` files,
   with no `.py`, handler, descriptor, registry, generated manifest, callback,
   or convenience API able to add topology?
4. Is canonical-only importing enforceable across relative, absolute,
   editable, wheel/sdist, and installed-package resolution without executing
   author source or creating path-based identity?
5. Is the canonical descriptor concretely owned once, including
   `default_pipeline`, cross-package visibility, source correspondence, locks,
   and migration history?
6. Is the registry-owned distribution-coordinate/fork-lineage model sufficient
   under physical moves, renames, legitimate version evolution, unauthorized
   forks, ambiguous locks, extraction/inline, and multi-version installs?
7. Is the versioned conservative executable-closure algorithm decidable,
   complete, and appropriately biased toward false drift rather than silent
   under-digesting?
8. Does separating `default_pipeline` selection from the invoking
   root-result-adapter binding prevent hidden hosting semantics without making
   direct invocation needlessly awkward?
9. Can preview-only `.py @workflow` and durable sandbox be impermeable to
   comparison, admission, resume, publication, effects, and evidence promotion?

### Native migration, authority, and proof

10. Is the bootstrap itself safely non-self-hosted—required external CI,
    independent review, manual merge, and a manifest binding those records—and
    does its implemented pre-merge validation plus post-merge rebinding then
    block bad code in later chains without turning YAML into an arbitrary
    command runner?
11. Does the fixed chain lifecycle—merge-HEAD readiness validation, declared
    typed receipt-consuming transition, immutable transition receipt, and
    independent post-transition verification—close the timing gap without
    creating an arbitrary command-execution surface?
12. Does Native prove source → lowered graph → runtime occurrence → accepted
    decision/action/effect equality, rather than only output parity?
13. Are Run Authority, Custody, WBC, checkpoints/effects, and projections
    separated so that evidence, lease, status, or scheduler timing can never
    grant permission or choose a route?
14. At every partial cutover, is exactly one writer/decision consumer
    authoritative, with no dual external writes and an explicit rollback,
    retention, and deletion point?
15. Are finite route keys/named predicates and bounded
    `progress_incomparable` handling sufficient to prevent payload routing and
    silent no-progress resets across schema changes?
16. Does GO-2's exhaustive effect-protocol inventory plus independently
    verified equivalence records prevent a harmless proxy from authorizing a
    materially different effect?
17. Are human answer/timeout/cancel, terminal cancel/publish/deliver,
    retry/new-generation, and ambiguous-effect races closed by production CAS
    rather than timing or projection order?
18. Is the golden trace oracle independent, raw-first on multiplicity and
    causality, and strong enough to catch handler relapse, stitched histories,
    missing losers, reader-path authority, or normalization laundering,
    including field-table amendments?

### Platformization and chain reachability

19. Does S7 hand off enough exact compiler/contract/GO-FORMAT/golden/coupling
    evidence that Platformization cannot silently reinvent Native semantics?
20. Is the S2A/S2B/S3 split precise enough to promote the Native runtime and
    compiler in place, prevent duplicates, and deliver transactional refactors
    plus viable DX before S4 extraction?
21. Does S5's machine-readable independence manifest, dependency/lineage scan,
    two novel shapes, Megaplan-uninstalled build, and independent profile
    re-derivation prove a genuinely unrelated consumer without forbidding
    legitimate generic platform imports?
22. Is S6's stable-publication gate impossible to satisfy with Megaplan-only,
    fake-CAS, normalized-only, self-certified, hash-only, preview, or incomplete
    capability-profile evidence?
23. Which milestone, if any, cannot realistically close within its assigned
    size without moving work earlier, splitting work, or adding a prerequisite?
24. If both chains execute exactly as written and all gates honestly pass, what
    important property of the stated end state is still not proven?
25. Can a stable third-party `.pype` package survive grammar/compiler/
    descriptor/manifest evolution without reinterpretation—through exact
    retained decoders/artifacts or explicit migration—and do mixed workers fail
    before authority whenever those versions disagree?

## Decisions the oracle should not reopen without a counterexample

The following are adopted, but may be challenged with a concrete incompatible
or green-but-wrong implementation:

- `.pype` replaces `.pypeline` for live durable authoring;
- one canonical workflow per `.pype`;
- subworkflow is a hosting role;
- private local steps are allowed and folded into workflow identity;
- shared steps/effects/support definitions live in `.py`;
- ordinary `.py` workflows are preview-only;
- steps are leaves and helpers return data rather than invocation targets;
- static discovery never executes author source;
- paths are provenance, not logical identity;
- one canonical package descriptor owns defaults/visibility/locks/migrations;
- legacy readers only resolve exact pinned artifacts for already admitted
  occurrences and cannot admit, reinterpret, or author new work;
- Native product migration precedes generic platform extraction;
- S2A runtime meaning precedes S2B authoring core, which precedes S3 public
  developer tooling;
- real unrelated-consumer evidence precedes stable publication; and
- only Platformization S6 may certify stability.

Directory names, filename matching, extraction heuristics, lint severity, and
editor implementation details remain revisable conventions unless they affect
identity, package compatibility, or durable claims.
