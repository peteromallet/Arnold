# Oracle Review Guide — Native Parity and Workflow Platformization

## Purpose

This is the entry point for an outside technical oracle reviewing two prepared,
not-yet-launched Arnold epics:

1. **Megaplan Native Parity Corrective** makes Megaplan's authored `.pype`
   topology the complete product-control-flow authority while preserving its
   accepted behavior and binding execution to the existing Run Authority,
   Custody, and Workflow Boundary Contracts substrate.
2. **Native Workflow Platformization** turns the format, runtime boundaries,
   and selected proven patterns into a product-neutral workflow-component
   platform suitable for third-party developers.

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
    reusable typed steps
    declared effect adapters
    schemas, policies, prompts, types, deterministic helpers
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
- preview uses fresh identity and fake/sandbox effects;
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

The chain has eight milestones; `GO-FORMAT` is a blocking machine gate within
S2, not a ninth milestone.

| Milestone | Owns | Blocking output |
| --- | --- | --- |
| S1 | Admit exact M11 substrate; inventory `.pypeline` → `.pype`; freeze format, identity, helper/step, mode, semantic, and expected-red contracts | Executable baseline and target corpus; no local authority substitute |
| S2 | Implement exact-one compiler/linker, converter, minimal preview, logical identity/package integration, generic durable constructs and runtime binding | Planned independently validated `go-format-receipt.json`; then GO-0 |
| S3A | Cut over prep, plan, and critique using `workflow.pype` and `plan_quality/critique.pype` | GO-1A and exclusive resume-plane binding |
| S3B | Cut over gate/revise/cycle; remove S3A seam and temporary front-half scaffold | GO-1B and complete front-half authority |
| S4 | Cut over tiebreaker/finalize/human durable reentry | `plan_quality/tiebreaker.pype`; outgoing delivery seam |
| S5 | Cut over finalize/approve/execute/review/rework delivery cycle | Delivery workflow files; GO-2; old delivery carriers fenced |
| S6 | Move override/reconfigure/auto/recovery to typed leaves and downstream consumers | No hidden control topology; GO-3 |
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

### Epic 2 — Native Workflow Platformization

| Milestone | Owns | Blocking output |
| --- | --- | --- |
| S1 | Verify Native handoff; freeze experimental component/lifecycle/composition/evolution/mode/proof standard and invalid corpus | Reproducible candidate; explicit S2A vs S2B ownership |
| S2A | Implement product-neutral runtime, lifecycle, admission, authority, state, effects, traces, locks, and faithful local-kit semantics | S2B need not invent runtime or authority meaning |
| S2B | Productize `.pype` frontend/linker, package correspondence, identity-aware refactors, converter, CLI/editor, diagnostics, and install-form equivalence | S4 need not invent authoring, identity, migration, package, or tooling rules |
| S4 | Extract first reusable patterns and make Megaplan consume them under isolation/recomposition/golden proof | One correct product uses shared implementations |
| S5 | Build unrelated consumer, vary domain and composition shape, substitute implementation, and separately test new-instance and resume evolution | Product leakage exposed or removed; no stable claim |
| S6 | Incorporate S5 findings and run cumulative conformance/publication gate | Only proven versions become stable; completion manifest and registry |

## Milestone audit digest

This is the compact substitute for the fourteen milestone briefs. The oracle
may request a specific brief after identifying a concern, but the ZIP should be
sufficient for a first reachability and sequencing verdict.

### Native Parity

| Milestone | Critical inputs | Major work bundles | Machine evidence / artifacts | Do not close when | Declared load and review concern |
| --- | --- | --- | --- | --- | --- |
| S1 | Exact completed M11 manifest/proof, installed revision, current compiler/runtime/source inventory | Capability probes; suffix/package/source-map inventory; exact-one format and identity contract; semantic checker/golden/proof schemas; expected-red and DX corpus | M11 intake receipt; inventory; target corpus; diagnostic and proof-map schemas | M11 is nominal/shadow-only; local RA/Custody/WBC substitute exists; live `.pypeline` authoring remains unclassified; evidence is labels/hashes rather than executed behavior | `partnered-5 / extreme / max`; broad contract-freeze milestone with prerequisite-audit risk |
| S2 | S1 contract/corpus plus admitted M11 adapters | Parser/linker; private/shared and leaf laws; converter; preview; identity/descriptor/locks; typed decisions/loops/fanout/retry/humans/checkpoints/effects; production CAS/restore proof | Planned GO-FORMAT index/validator/receipt; GO-0; neutral reference traces; restore and contention receipts | Discovery executes source; generic code imports Megaplan; fake CAS proves authority; hidden durable Python survives; GO-FORMAT is stale/red/self-declared | `partnered-5 / extreme / max`; largest overload risk because format migration and generic runtime primitives share one milestone |
| S3A | Green GO-FORMAT and GO-0; S2 runtime; old/candidate prefix inventory | Root plus critique files; prep/clarification/plan/critique cutover; exclusive resume-plane binding; WBC producer relocation; quarantined comparison | Reconsumed GO-FORMAT; GO-1A; partial golden trace; old-carrier inertness | Both planes can resume/write; comparison can acquire effects/authority; route reconstruction remains in builder/handler; outgoing seam can choose routes | `partnered-5 / extreme / max`; first live authority cut and highest rollback sensitivity |
| S3B | Accepted GO-1A and typed gate seam | `gate.pype` and `cycle.pype`; gate/revise/planning loop; total outcomes/precedence; front-half carrier removal; temporary scaffold retirement | GO-1B; complete front-half golden rows; arbitration race/restore receipts | Any front-half carrier or scaffold remains route-capable; gate outcomes/defaults are incomplete; old and new writers overlap | `partnered-5 / extreme / max`; dense policy and race semantics after an irreversible prefix cut |
| S4 | Accepted GO-1B and tiebreaker/finalize seam | `tiebreaker.pype`; bounded synthesis/decision; human suspension/reentry; finalization/escalation; migration decisions | Tiebreaker/finalize golden rows; duplicate-human and drift receipts; delivery seam | Resume lacks exact RA/Custody/WBC binding; duplicate human decisions can both win; pinned drift silently resumes; effects repeat | `partnered-5 / extreme / max`; durable human and migration semantics dominate |
| S5 | Accepted S4 seam and generic delivery primitives | Delivery `cycle/execute/execute_batch/review.pype`; dependency batching; approval; review/rework; cancellation/resource/effect reconciliation | GO-2; delivery golden rows; live/shadow external-effect proof; child-identity and partial-restart receipts | List position defines identity; accepted work repeats; review/rework escapes the bounded cycle; old carriers can act; unresolved effects are treated as terminal truth | `partnered-5 / extreme / max`; multiple product phases and external-effect cutover create size risk |
| S6 | Accepted delivery cut and control action inventory | Typed override/reconfigure/human/auto/recovery leaves; control routes remain visible in callers; remove final seam; make CLI/auto/projections downstream | GO-3; route-mutation negatives; writer/repair/restore receipts | Auto, status, projection, `_core`, handler, or repair code can choose routes/grant; a control step invokes topology; final seam remains active | `partnered-5 / extreme / max`; cross-surface deletion/inertness proof is the main risk |
| S7 | All accepted cuts, golden contract, old/current source inventory | Cumulative source/lowered/runtime/action/effect equality; package/install/cloud proof; legacy reader expiry; seam/dead-carrier proof; final handoff | New Native Parity conformance/traceability/validator, final proof map, GO-4, completion and Platformization handoff manifests | Final gate uses the old `.pypeline` ledger; any live legacy/hidden route remains; evidence is normalized-only/self-certified/stitched; handoff omits exact compiler/identity/legacy receipts | `partnered-5 / extreme / max`; evidence integration is large but should not become first-time implementation |

### Platformization

| Milestone | Critical inputs | Major work bundles | Machine evidence / artifacts | Do not close when | Declared load and review concern |
| --- | --- | --- | --- | --- | --- |
| S1 | Accepted Native completion/handoff and reusable-candidate inventory | Verify handoff; freeze experimental descriptor/lifecycle/composition/evolution/mode/profile standard; reference models; invalid/mutation/DX corpus; extraction classification | Intake receipt; candidate schemas; conformance/traceability skeletons; proof-map schema | Any rule is prose-only; S2A/S2B ownership is ambiguous; fake CAS becomes production proof; candidate is called stable | `apex / extreme / max +prep`; foundational contract breadth and inherited-evidence verification |
| S2A | S1 candidate and admitted Native/M11 runtime substrate | Product-neutral validation/lowering interfaces; lifecycle/admission/authority/state/effects/checkpoints/locks/traces; faithful local kit; real-store contention | Runtime conformance rows; crash/race/CAS/restore receipts; S2A handoff | It creates a second parser/package model; local fakes diverge from production; authority/lifecycle meaning remains for S2B to invent | `apex / extreme / max`; broad runtime kernel and fault matrix |
| S2B | Native format surfaces, S1 corpus, S2A runtime handoff | Public parser/linker/index; package/source correspondence; identity/migration; converter and transactional refactors; CLI/editor/format/lint/preview/test SDK; install-form equivalence | All 17 format families; refactor atomicity; DX benchmarks; S2B handoff | It forks Native compiler/runtime/descriptor; private members leak; editor uses alternate semantics; S4 must invent an authoring/package rule | `apex / extreme / max +prep`; arguably a full product/toolchain release and a major sizing risk |
| S4 | S2B experimental SDK and selected Native candidates | Extract evaluator/refinement/human/effect-safe patterns; remove Megaplan defaults; make Megaplan consume clean-wheel implementations; prove isolation/recomposition | Golden equivalence, concurrency/isolation, install, local-kit, extraction disposition receipts | Reverse imports/copies remain; identity/layout/migration is redefined during extraction; only one composition shape passes | `partnered-5 / thorough / xhigh`; first consumer proof is narrower but migration-sensitive |
| S5 | S4 patterns and all experimental contracts/tooling | Build unrelated domain; novel shapes/bindings; independent implementation; new-instance substitution; separate pinned resume/migration/quarantine; cross-consumer explanation | Challenge report; compatibility receipts; migration/quarantine evidence; amended cumulative proof | Consumer is renamed Megaplan; new-instance proof is reused for resume; compatibility shims hide divergent topology; leakage is deferred | `apex / extreme / max +prep`; adversarial scope is intentionally large and must remain genuinely independent |
| S6 | Accepted S5 amendments and cumulative proof | Freeze only proven public surfaces; evolution/retention/GC; docs/DX/SLOs; registry governance; full closure/acceptance suite; stable publication | Final validator, conformance/traceability, proof map, component manifests, registry, completion manifest | Any applicable row is red/missing/fake/self-certified; effective profiles exclude failures; stable precedes S5; old pinned artifacts can disappear | `premium / thorough / xhigh`; certification must aggregate rather than invent missing functionality |

## Concrete implementation ownership

| Surface | Native Parity S2 | Platform S2A | Platform S2B | Steady-state owner |
| --- | --- | --- | --- | --- |
| Parser/lowerer | Implement adopted grammar and Megaplan-required lowering | Consume typed IR; no parallel parser | Productize same frontend/linker | Arnold workflow platform |
| Runtime/lifecycle | Bind generic constructs to admitted substrate | Own shared lifecycle/admission/state/effect meaning | Consume; no second runtime | Arnold workflow platform |
| Diagnostics/source maps | Minimum stable catalog for GO-FORMAT | Runtime/admission faults | Cross-package/editor/navigation/traceback completion | Arnold workflow platform |
| Descriptor/discovery/lock | Extend canonical existing owner after inventory | Enforce frozen identity/lock | Productize package selection/correspondence | Arnold workflow platform |
| Identity/migration | Implement keys, digests, legacy mapping, Megaplan records | Enforce compatibility/migration semantics | Productize refactors and APIs | Arnold workflow platform |
| Converter/preview | Mechanical legacy converter and minimal preview | Faithful sandbox/fork hooks | Public converter/refactors/preview/test SDK | Arnold workflow platform |
| CLI/editor | Make check/compile/inspect work for cutover | Expose runtime inspection | Own generic CLI/editor/format/lint | Arnold workflow platform |
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

S2 is required to create:

```text
docs/arnold/pype-authoring-conformance.yaml
scripts/validate_pype_authoring_contract.py
.megaplan/initiatives/megaplan-native-parity-corrective/
  go-format-receipt.json
```

The receipt schema is `arnold.megaplan.go_format_receipt.v1`. S3A is required
to reconsume it independently. The validator must recompute rather than trust
declared status.

The current chain engine exposes a typed `final_conformance_gate` hook only for
the final milestone. Therefore GO-FORMAT is specified in the S2/S3A plans and
chain notes, but is not yet a typed intermediate `validate` stanza in
`05_NATIVE_PARITY_CHAIN.yaml`. This is a real enforcement gap: the oracle
should decide whether the chain engine must gain a machine intermediate-gate
primitive before launch, or whether another content-addressed prerequisite
mechanism can make S2 closure/S3A start mechanically impossible on stale,
missing, or red evidence.

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

S1 creates the product-neutral conformance/traceability skeletons with honest
red rows. S2A and S2B populate runtime and authoring/tooling evidence. S4 and S5
add extraction and unrelated-consumer proof. S6 alone produces:

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
4. Distribution-plus-logical-name identity may be insufficient under package
   rename/fork, namespace collision, or multi-version installation.
5. The canonical descriptor owner may remain unclear in the current pack/lock
   implementation, inviting a parallel package format.
6. Preview-only `.py` workflows may leak durable-shaped artifacts or effects.
7. S2 combines a large format/compiler migration with generic durable runtime
   primitives and could be too broad even though GO-FORMAT is internal.
8. Partial product cutovers could leave dual writers, resumable comparison
   history, or ambiguous rollback after an accepted prefix cut.
9. Golden trace normalization could hide multiplicity, race, or causal loss.
10. S2A/S2B could drift into two compilers or two local execution models.
11. First-wave extracted “patterns” may encode Megaplan policy despite zero
    direct imports.
12. S5 may be too easy to game with a ceremonial second consumer or
    new-instance compatibility presented as resume compatibility.
13. S6's effective-profile derivation could exclude the very tests that would
    fail a candidate.
14. The total combined workload may be larger than the declared milestone
    sizing even when the dependency order is sound.

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
6. Is `(distribution_name, logical_workflow_name)` sufficient under physical
   moves, repository/package renames, forks, collisions, extraction/inline, and
   independently installed versions?
7. Is the provenance-only versus identity/behavior-drift boundary complete and
   teachable?
8. Can preview-only `.py @workflow` be made impermeable to durable sandbox,
   comparison, admission, resume, publication, effects, and evidence promotion?

### Native migration, authority, and proof

9. Is GO-FORMAT sufficiently machine-bound that S2 cannot close and S3A cannot
   start through prose compliance or a self-declared receipt?
10. Does Native prove source → lowered graph → runtime occurrence → accepted
    decision/action/effect equality, rather than only output parity?
11. Are Run Authority, Custody, WBC, checkpoints/effects, and projections
    separated so that evidence, lease, status, or scheduler timing can never
    grant permission or choose a route?
12. At every partial cutover, is exactly one writer/decision consumer
    authoritative, with no dual external writes and an explicit rollback,
    retention, and deletion point?
13. Are human answer/timeout/cancel, terminal cancel/publish/deliver,
    retry/new-generation, and ambiguous-effect races closed by production CAS
    rather than timing or projection order?
14. Is the golden trace oracle independent, raw-first on multiplicity and
    causality, and strong enough to catch handler relapse, stitched histories,
    missing losers, or normalization laundering?

### Platformization and chain reachability

15. Does S7 hand off enough exact compiler/contract/GO-FORMAT/golden/coupling
    evidence that Platformization cannot silently reinvent Native semantics?
16. Is the S2A/S2B split precise enough at the concrete source-tree level to
    prevent a second compiler, descriptor, identity registry, migration log, or
    local runtime?
17. Do S4 and S5 prove real shape-independent reuse and product neutrality,
    including an independent implementation and separate new-instance versus
    suspended-run resume compatibility?
18. Is S6's stable-publication gate impossible to satisfy with Megaplan-only,
    fake-CAS, normalized-only, self-certified, hash-only, preview, or incomplete
    capability-profile evidence?
19. Which milestone, if any, cannot realistically close within its assigned
    size without moving work earlier, splitting work, or adding a prerequisite?
20. If both chains execute exactly as written and all gates honestly pass, what
    important property of the stated end state is still not proven?
21. Can a stable third-party `.pype` package survive grammar/compiler/
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
- legacy readers are exact-pin and read-only;
- Native product migration precedes generic platform extraction;
- S2A runtime meaning precedes S2B public authoring/tooling;
- real unrelated-consumer evidence precedes stable publication; and
- only Platformization S6 may certify stability.

Directory names, filename matching, extraction heuristics, lint severity, and
editor implementation details remain revisable conventions unless they affect
identity, package compatibility, or durable claims.
