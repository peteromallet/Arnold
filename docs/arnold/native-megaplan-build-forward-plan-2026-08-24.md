# Native Megaplan Build-Forward Plan — 2026-08-24

## Revision 2026-08-24 (post-reconciliation)

The operator-accepted adjudication in `docs/arnold/native-plan-reconciliation-2026-08-24.md` controls wherever this plan's earlier wording differs. The controlling hybrid sequence is:

```text
P0 MRC closeout intake and MRC→M11→Native crosswalk (read-only)
  -> P1 Custody M11 admission resolution (result gate, not a presumed rerun)
  -> P2 milestone-gate bootstrap plus all three readiness artifacts
  -> Native S1 -> S2F -> C1 -> C2 -> S2R -> S3A -> S3B -> S4 -> S5A -> S5B -> S6 -> S7
  -> Platform S1 -> S2A -> S2B -> S3 -> S4 -> S5 -> S6
```

P1 resolves outputs, not a predetermined recovery procedure. It must locate/import and validate any canonical superseding Run Authority disposition and subsequent accepted artifacts from the authoritative Custody checkout; only if those artifacts do not exist does Custody perform the corrective work required to produce them. The earlier instruction in §5 to unconditionally finish nine residual Custody milestones is **superseded by this revision**. Native may neither infer acceptance nor implement a substitute.

**NO-GO at P1.** Native S1 cannot start until all six gates are content-addressed and validator-green: (1) canonical Run Authority disposition of the prior M11 completion/promotion evidence; (2) approved zero-blocker ownership decision; (3) accepted Custody M11 completion manifest and proof map; (4) accepted `bounded-incident-projection-handoff.json`; (5) complete installed/runtime/production-vector and canary acceptance required by the current Custody contract; and (6) accepted milestone-gate bootstrap manifest with `downstream-spec-readiness.json`, `completion-crosswalk-readiness.json`, and `editable-runtime-readiness.json`.

Authority is split deliberately. `docs/arnold/megaplan-native-representation-report.md` remains architecture authority for contract separation and the Native-Parity-then-Platformization destination. Active chain specs, North Stars, milestone briefs, validators, transition handlers, proof maps, and accepted receipts are executable authority. The reconciliation is the controlling dated adjudication. This forward plan is the preferred implementation guide subject to the Custody qualification and evidence-tier limits above. Historical completion manifests remain substrate evidence, not corrective admission or conformance.

Evidence is proportional: content addressing, stable validator issues, allowance lineage, independent review, and pre/transition/post receipts are mandatory at authority, effect, and publication cuts; read-only, compiler, and tooling milestones apply the subset needed for their actual claims. No MRC receipt, capability, canary, or status projection may satisfy M11 or Native semantic proof.

## 0. Decision and executive position

**Decision:** preserve the representation report as the architectural end-state, but execute the already-prepared corrective sequence rather than the report's older decomposition. The active dependency graph remains:

```text
accepted Custody M11
  -> accepted milestone-gate bootstrap
  -> Native Parity: S1 -> S2F -> C1 -> C2 -> S2R -> S3A -> S3B -> S4 -> S5A -> S5B -> S6 -> S7
  -> Platformization: S1 -> S2A -> S2B -> S3 -> S4 -> S5 -> S6
```

That order is explicit in the report amendment and corrective initiative (`docs/arnold/megaplan-native-representation-report.md:3-9`; `.megaplan/initiatives/megaplan-native-parity-corrective/README.md:172-180`). The current checkout has useful compositional substrate, but it is still the report's **current-state snapshot**, not Post-Native-Parity: product routes are visible in `workflow.pypeline`, yet that file remains `.pypeline`, declares handler references and route tables, and delegates load-bearing decisions to handler/runtime carriers (`arnold_pipelines/megaplan/workflows/workflow.pypeline:94-294`, `403-778`). The adopted endpoint instead requires one workflow per `.pype`, static canonical imports, visible branches/loops/fanout/child calls, and leaf steps that cannot own topology (`docs/arnold/pype-authoring-contract.md:26-67`, `69-105`, `128-193`).

**MRC changes the implementation method, not the product destination.** Maintenance Runtime Consolidation (MRC) supplies proven operational patterns: narrow evidence-bound capabilities, report/effect receipt separation, read-only observation, append-only records, elapsed-deadline enforcement, guarded adoption/rebind, digest-bound evidence packs, explicit allowances, supervised disposable canaries, and honest exception adjudication (`arnold_pipelines/megaplan/cloud/current_target_liveness.py:408-481`; `arnold_pipelines/megaplan/cloud/maintenance_dispatch.py:89-173`, `280-364`; `scripts/validate_maintenance_runtime_consolidation_evidence.py:174-245`, `247-358`, `387-425`; `arnold_pipelines/megaplan/cloud/canary_sandbox.py:1-45`). It does **not** prove the missing Custody M11 prerequisite: the corrective chain requires content-addressed completion manifests from both Custody M11 and the milestone-gate bootstrap, and neither required manifest/readiness set exists in this checkout (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:5-19`; `.megaplan/initiatives/custody-control-plane/README.md:125-146`).

## 1. Authority and precedence

Use this precedence order during implementation and review:

1. The active sequencing amendment and corrective chain govern execution order (`docs/arnold/megaplan-native-representation-report.md:3-9`; `.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:52-217`).
2. The representation report governs the two end-state snapshots and contract separation (`docs/arnold/megaplan-native-representation-report.md:135-193`).
3. The `.pype` contract governs authoring grammar, file boundaries, composition, and leaf law (`docs/arnold/pype-authoring-contract.md:17-24`, `26-67`, `69-105`, `128-193`, `195-213`).
4. The corrective North Star, briefs, stage validators, transition handlers, and proof maps govern milestone acceptance (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:112-170`; `.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:52-217`).
5. The alignment matrix is the row-level anti-false-pass ledger. `enabled` means owned substrate, not implemented report conformance (`docs/arnold/megaplan-native-representation-alignment-plan.md:99-120`).
6. Existing completion manifests prove earlier substrate epics, not the new corrective endpoint. The old completion, composition, and platform chains record their milestones as done (`.megaplan/initiatives/native-python-pipelines-completion/completion-manifest.json:7-120`; `.megaplan/initiatives/native-composition-followup/completion-manifest.json:7-103`; `.megaplan/initiatives/native-platform-followup/completion-manifest.json:7-118`), while the new Platformization initiative explicitly labels the prior platform chain historical and its own chain prepared/not launched (`.megaplan/initiatives/native-workflow-platformization/README.md:1-8`, `45-61`).

## 2. Current-approach audit against Stage 1

### 2.1 Snapshot verdict

| Report snapshot dimension | Current status | Current evidence | Required move |
|---|---|---|---|
| Canonical authored source | **Partial** | `workflow.pypeline` is named canonical and `workflow.py` is compatibility-only (`arnold_pipelines/megaplan/workflows/workflow.py:1-16`; `arnold_pipelines/megaplan/workflows/planning.py:46-53`). | Migrate the entire live surface to `.pype`; prohibit new `.pypeline` admission; split durable child workflows one-per-file (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:66-85`, `207-236`). |
| Adopted `.pype` frontend/toolchain | **Missing** | The live compiler accepts only `.py` and `.pypeline`, hard-codes `workflow.pypeline` as the Megaplan authoring source, and still recognizes handler metadata exports (`arnold/workflow/source_compiler.py:98-125`). The adopted contract assigns grammar/schema freeze to S1, frontend/identity/converter implementation and GO-FORMAT to S2F, and durable-runtime consumption to S2R (`docs/arnold/pype-authoring-contract.md:3-15`). | S1 inventories/stages the cut; S2F implements and selects the frontend, converter and validator under GO-FORMAT. |
| Visible product topology | **Partial, materially advanced** | The root source contains a bounded planning loop, dynamic critique/execute/review maps, gate branches, tiebreaker sequence, review/rework, override, and terminals (`arnold_pipelines/megaplan/workflows/workflow.pypeline:403-479`, `480-675`, `676-778`). | Remove duplication and convert logical regions into named child `.pype` workflows; make suspension, reentry, typed exits, policy, effects, and terminal proposals durable first-class constructs. |
| Source authority | **Missing** | The authoring file still contains `DECLARED_STEP_INTERFACES`, `handler_ref`, `route_bindings`, and `DECLARED_WORKFLOW_TOPOLOGY_CONTRACTS` (`arnold_pipelines/megaplan/workflows/workflow.pypeline:94-294`, `296-400`). The alignment doctrine explicitly rejects generic stage dispatch, handler refs, route-label tables, and component constants as final carriers (`docs/arnold/megaplan-native-representation-alignment-plan.md:19-33`, `38-65`). | Cut authority slice-by-slice with receipt-consuming transitions; handlers become typed pure leaves/adapters or are deleted. |
| Route consumers and auto-drive | **Missing source authority** | The strict parity audit finds `planning.py` still merges lowered source with component route bindings, the manifest backend still maps handler response fields to branches, route dispatch falls back to component bindings, and state mutation remains across handlers/execute (`docs/arnold/megaplan-native-semantic-parity-master-plan.md:214-223`). Gate code states auto-drive re-derives the next step from state and ignores the handler's returned `next_step` (`arnold_pipelines/megaplan/handlers/gate.py:619-628`). | S3A–S6 must migrate both producers **and every consumer/re-deriver**; S7 requires zero route-capable compatibility seams. |
| Generated runtime contract | **Exists as substrate** | `WorkflowManifest` already owns deterministic nodes, edges, policy slots, source spans, and hashes, while remaining compiler output rather than hand-authored truth (`docs/arnold/workflow-manifest.md:1-12`, `14-48`, `103-167`). | Preserve the manifest as generated runtime/replay coordinates; bind schema, decoder/lowerer, topology hash, and executable closure at admission. |
| Dynamic topology | **Implemented as substrate and source shape; parity incomplete** | `workflow.pypeline` uses `parallel_map` for critique, execute batches and review (`arnold_pipelines/megaplan/workflows/workflow.pypeline:408-434`); `ParallelMapInstruction` distinguishes runtime-list fanout from static parallel branches (`arnold/pipeline/native/ir.py:315-368`), and the runtime resolves live items/path coordinates (`arnold/pipeline/native/runtime.py:451-512`). The matrix nevertheless keeps product fanout/reducer rows enabled pending handler-purity and final conformance (`docs/arnold/megaplan-native-representation-alignment-plan.md:128-129`, `136`, `139`, `144-146`). | Prove frozen bindings, keyed completion-order-independent reduction, nested path identity, partial failure, retry and resume while removing handler-owned selection/reduction/routes. |
| Typed loop exits and durable reentry | **Partial** | The source has `while True`, enum comparisons, and explicit returns (`arnold_pipelines/megaplan/workflows/workflow.pypeline:408-419`, `435-479`), but the adopted contract requires named enclosing-loop exits, terminalized intervening scopes, and fresh loop-instance reentry (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:95-103`). | Implement and validate typed named-exit/unwind/reentry semantics in S2R, then consume them in S3A–S5B. |
| Named child workflows | **Enabled, not final** | Current source imports component-backed `CRITIQUE_PANEL_WORKFLOW`, `EXECUTE_BATCH_WORKFLOW`, and `REVIEW_PANEL_WORKFLOW` (`arnold_pipelines/megaplan/workflows/workflow.pypeline:14-34`) but the target layout has separate `.pype` files for plan-quality and delivery lifecycles (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:207-236`). | S3A/S3B/S4/S5A create and cut over the named files; `control/` stays leaf-only. |
| Effects and authority envelope | **Substrate exists; Native binding missing** | The report requires separate Run Authority, Custody, WBC, checkpoint, effect, and projection ownership (`docs/arnold/megaplan-native-representation-report.md:180-193`). Current authoring still names generic capability/policy metadata rather than demonstrating every live action consumes the complete envelope (`arnold_pipelines/megaplan/workflows/workflow.pypeline:113-157`, `220-257`). | S1 probes accepted M11 APIs; S2R binds occurrence identities; S5A proves each effect class; S5B is the only live delivery transition. |
| Durable identity and evolution | **Partial** | Manifest alias/full/topology hashes and stable node/edge coordinates exist (`docs/arnold/workflow-manifest.md:14-31`, `33-48`, `69-101`). The target additionally requires distribution+workflow logical identity, exact executable closure, explicit migration, pinned decoders, and no path-only resume (`docs/arnold/megaplan-native-representation-report.md:161-178`). | S2F freezes compiler/linker/converter/identity and closes GO-FORMAT; S2R admits durable state and decoder compatibility. |
| Handler purity | **Missing** | The report inventories prep/critique/gate/finalize/execute/review/override/auto as mini-orchestrators (`docs/arnold/megaplan-native-representation-report.md:500-529`). Current source still delegates those exact nodes to handlers (`arnold_pipelines/megaplan/workflows/workflow.pypeline:94-294`). | Maintain a complete carrier inventory; add structural scans and mutations that fail when handlers recover route, loop, fanout, suspension, retry, cap, or terminal authority. |
| Checkout/wheel/cloud equivalence | **Earlier proof only** | Earlier platform completion bound current `.pypeline`, planning, handler and installed-package artifacts (`.megaplan/initiatives/native-platform-followup/completion-manifest.json:114-202`). That proves the older surface, not `.pype` corrective parity. | Re-run equivalent proofs against `.pype`, exact package locks, selected decoder/lowerer, and current M11 envelopes at GO-FORMAT and GO-4. |
| Independent conformance | **Historical false pass; corrective proof prepared, not run** | The old report claims 31 implemented rows (`docs/arnold/megaplan-native-representation-conformance-report.md:8-17`), while the later strict audit records nine `AWF245_ROW_EVIDENCE_INSUFFICIENCY` failures and a CLI closure bypass (`docs/arnold/megaplan-native-semantic-parity-master-plan.md:183-211`). S7 creates a new corrective conformance/traceability/validator set and keeps the old ledger immutable (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:140-159`). | Banner the old artifacts as historical false-pass evidence; completion requires the new raw proof, mutation suite, allowance closure, completion manifest and Platformization handoff. |

### 2.2 Audit by report section

#### §3 product flow

The current source visibly models the broad phase order and major branches: prep/plan, bounded critique/gate/revise, tiebreaker, finalize, dynamic execute batches, review fan-in/rework, override, and terminal outcomes (`arnold_pipelines/megaplan/workflows/workflow.pypeline:403-479`, `480-675`, `676-778`). This is meaningful progress over the report's original diagnosis.

It is not parity because phase-local decisions still live behind handler references. The report's hidden-logic inventory identifies clarification waits, adaptive-evaluator retry/fallback, gate normalization/reprompt/backstop/debt, finalize fallback, execute admission/batching/retry, review fanout/caps/human verification, full override dispatch, and auto-drive policy as top-level semantics (`docs/arnold/megaplan-native-representation-report.md:502-529`). The matrix rows for those surfaces remain `enabled`, not `implemented` (`docs/arnold/megaplan-native-representation-alignment-plan.md:122-154`).

#### §4 hidden-logic inventory

Use all fifteen detail waves as the extraction checklist, not only the visible happy path: D1 Prep/Plan, D2 Critique, D3 Gate Preflight, D4 Gate/Revise, D5 Tiebreaker, D6 Finalize, D7 Execute DAG, D8 Execute Gates, D9 Review Fanout, D10 Review Caps, D11 Human/Control, D12 Runtime/Trace, D13 Policy/Platform, D14 Compiler/Authoring, and D15 Handler Extraction (`docs/arnold/megaplan-native-representation-alignment-plan.md:175-196`). A milestone cannot claim parity for a wave merely because its root branch appears in `workflow.pypeline`; its retries, malformed-output routes, caps, external waits, effect boundaries, reentry and negative mutations must also be source/policy visible.

#### §5 source-authoritative target

The report's monolithic `planning_native.py` is explicitly an illustrative topology/API sketch; the adopted implementation is split one-workflow `.pype` files (`docs/arnold/megaplan-native-representation-report.md:531-548`). The build must therefore avoid “completing” the current 778-line `.pypeline` by adding more route dictionaries. The exact target layout is `workflow.pype`, plan-quality child workflows, delivery child workflows, and `.py` leaves/policies/types; `control/` has no workflow file because control outcomes remain visible in callers (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:207-236`).

#### §§8–9 gap and migration

The four original gaps remain the right categories—dynamic topology, loop expressiveness, call-site policy, and event/control-plane clarity (`docs/arnold/megaplan-native-representation-report.md:2185-2235`)—but current code has partially closed the first two at a source-shape level. The corrective build must now close their durable semantics and authority binding. A shadow is comparison-only; it is not a finish line (`docs/arnold/megaplan-native-representation-report.md:2299-2322`). Each slice follows land → inert compare → merge-HEAD readiness → typed transition → independent post-transition verification → consumer migration → old-producer inertness → hard fence/delete (`docs/arnold/megaplan-native-representation-report.md:2359-2377`).

#### Full §1–§14 disposition

| Report section | 2026-08-24 status | Build-forward consequence |
|---|---|---|
| §1 Executive summary / contract stack | **Still controlling, with one prerequisite caveat.** The three snapshots and source→manifest→runtime ownership model remain valid (`docs/arnold/megaplan-native-representation-report.md:135-193`). The report's “completed M11” assumption is not evidenced by the required local completion manifest (`docs/arnold/megaplan-native-representation-report.md:215-240`; `.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:14-19`). | Preserve architecture; insert P0/P1 crosswalk and M11 admission before Native S1. |
| §2 Current state | **Partially superseded in detail, still correct in diagnosis.** Canonical `workflow.pypeline` and visible topology now exist, but handler refs, route bindings and compatibility lowering still split semantic authority (`arnold_pipelines/megaplan/workflows/workflow.pypeline:94-400`; `arnold_pipelines/megaplan/workflows/planning.py:46-53`, `95-154`). | Refresh the current-state map at S1; do not treat source-shape progress as authority cutover. |
| §3 Product flow | **Visible at root, incomplete at inner decisions.** The root source shows major loops/branches/fanout (`arnold_pipelines/megaplan/workflows/workflow.pypeline:403-778`), while the alignment rows remain enabled rather than implemented (`docs/arnold/megaplan-native-representation-alignment-plan.md:122-154`). | Migrate D1–D11 semantics and prove each false-pass guard. |
| §4 Hidden logic | **Still the extraction ledger.** The listed handler mini-orchestrators remain represented by handler refs and policy/route metadata (`docs/arnold/megaplan-native-representation-report.md:500-529`; `arnold_pipelines/megaplan/workflows/workflow.pypeline:94-400`). | Maintain a live semantics-carrier ledger through S7. |
| §5 Stage-1 target | **Architecturally controlling; syntax sketch superseded by adopted file grammar.** The report says the listing is illustrative and implementation is split one-workflow `.pype` files (`docs/arnold/megaplan-native-representation-report.md:531-548`). | Implement the corrective file layout and `.pype` contract, not the monolithic sketch. |
| §6 Stage-2 component target | **Deferred and still controlling after parity.** Platformization must preserve root terminal arbitration and bind product types/policies/effects explicitly (`docs/arnold/megaplan-native-representation-report.md:1588-1607`). | No generic extraction before Native S7's handoff; Platform S4/S5 must prove independent use. |
| §7 Required constructs / ergonomics | **Mixed substrate, no complete product proof.** The report itself marks source diagnostics partial and one fast deterministic harness missing (`docs/arnold/megaplan-native-representation-report.md:2002-2028`). | Close product-required primitives in S2F/S2R and extend the same corpus in Platform S2B/S3. |
| §8 Gap analysis | **Categories stand; implementation moved.** Dynamic map and visible loops now have source forms, but durable exits, call-site policy, effect/reentry identity and event/control authority remain incomplete (`docs/arnold/megaplan-native-representation-report.md:2185-2235`; `arnold_pipelines/megaplan/workflows/workflow.pypeline:403-778`). | Reclassify from “missing syntax” to “partial syntax, missing durable/authority proof” where current code warrants it. |
| §9 Two-stage recommendation | **Superseded only in milestone detail.** The corrective README/chain now carries twelve Native milestones and the prepared Platform chain carries seven (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:112-180`; `.megaplan/initiatives/native-workflow-platformization/README.md:115-141`). | Execute those chains with P0/P1/P2 prerequisites and MRC evidence discipline. |
| §10 Standardization closure | **Unstarted as a stable standard.** Platformization is explicitly prepared/not launched and S6 alone may certify stable publication (`.megaplan/initiatives/native-workflow-platformization/README.md:1-8`, `115-141`). | Preserve all closure clauses for Platform S6; do not credit historical platform completion as this standard. |
| §11 Mental models | **Target remains valid, operational tooling changed.** Authors should own `.pype` topology while operators inspect manifests/receipts/projections; OMP-backed wrappers now provide resolved-model/process/output provenance (`docs/arnold/megaplan-native-representation-report.md:2679-2731`; `scripts/run_maintenance_consolidation_agent.py:399-445`, `477-532`). | Update guides/runbooks at GO-FORMAT/GO-0 without moving semantics into tooling. |
| §12 Variability/non-goals | **Still controlling.** Product types/policies/effects may vary, but source authority, deterministic lowering and admitted boundaries may not (`docs/arnold/megaplan-native-representation-report.md:2732-2756`). | Keep maintenance analytics/schedules and model-route tables out of the generic workflow standard. |
| §13 Conclusion | **Diagnosis remains true.** The target is readable durable Python with product routes/loops/fanout/reentry/policy/effects/terminals authored once (`docs/arnold/megaplan-native-representation-report.md:2757-2784`). | Native S7—not current source readability alone—is the closure point. |
| §14 Audit design | **Must be refreshed, not discarded.** It names the corrective plan/golden contract, Platformization contract, authoring/manifest and authority sources, plus known M11 unknowns (`docs/arnold/megaplan-native-representation-report.md:2803-2812`, `2945-3004`). | S1 binds exact current implementations; S7 emits the new corrective traceability/conformance set and closes known unknowns or assigns owners. |

## 3. What changed after the report

### 3.1 MRC landed a coherent successor operational runtime

The 2026-08-24 branch head records MRC closure after a supervised canary and post-review must closure; the implementation/evidence files show the resulting contracts. The relevant build-forward deltas are:

| New fact | Evidence | Adjusted Native guidance |
|---|---|---|
| One narrow claim/CAS seam exists for scheduled maintenance occurrences. | `ScheduleService.claim()` is the schedule claim API, while scheduler consumers state they use the one claim seam (`arnold_pipelines/megaplan/resident/schedules.py:711-714`, `1061-1065`; `arnold_pipelines/megaplan/resident/scheduler.py:99-102`, `1178-1182`). | Reuse the **single-writer/single-CAS discipline**, not the maintenance schedule schema. Native semantic occurrences must consume accepted RA/Custody decisions at one admitted transition seam; do not create a second scheduler-owned route decision. |
| Report and effect receipts are different frozen schemas. | Report receipts reject effect coordinates; effect receipts require exact occurrence/request/effect/evidence identity; reconciliation is read-only and cross-kind-safe (`arnold_pipelines/megaplan/cloud/maintenance_dispatch.py:89-173`, `280-364`). | Define Native transition/effect receipts per boundary. Keep diagnostics/projections non-authoritative; never let “report present” satisfy effect or terminal evidence. |
| Mutation authority is mint-only, typed, narrowable, evidence-bound, and non-reconstructible. | `MutationCapability` cannot be directly constructed, binds action/occurrence/target/cursor/fence/evidence/scope/expiry/runtime/custody, and prevents scope widening (`arnold_pipelines/megaplan/cloud/current_target_liveness.py:408-481`, `498-535`). | Reuse the capability shape for authority-changing transition handlers. Do not expose ambient `ctx.can_mutate`; each transition consumes a current accepted receipt and exact occurrence envelope. |
| Observation is explicitly powerless. | MRC adapters call only read/query/version APIs and expose no owner-store mutation (`arnold_pipelines/megaplan/maintenance/sources.py:1-17`, `194-200`, `520-545`, `794-798`). | Native status, trace, auditor and comparison tools remain rebuildable views; “looks current” cannot choose route, resume, retry, adoption, or completion. |
| Evidence packs are executable contracts, not folders of prose. | The validator checks schema, immutable source digests, cross-record IDs, route/model receipts, artifact digests, reviewer independence, one deciding review, judgment receipts, allowances, overlap and shard identity (`scripts/validate_maintenance_runtime_consolidation_evidence.py:174-245`, `247-358`, `378-425`). | Every Native milestone gets a manifest schema, semantic validator, stable issue ordering, proof map, receipt, negative fixtures, and inventory equality. Do not copy MRC role names or fixed route roster; parameterize by Native milestone contract. |
| Allowances are explicit, typed, digest-bound and overlap-rejected. | The wrapper canonicalizes categorized allowances, computes a digest, and rejects overlap with active registry rows (`scripts/run_maintenance_consolidation_agent.py:86-134`); the validator requires exactly one allowance per task and detects overlap (`scripts/validate_maintenance_runtime_consolidation_evidence.py:387-421`). | Use an expiry-bound Native exception/allowance register for legacy readers, temporary route seams, historical `.pypeline` references, generated outputs and environment deviations. Every allowance names owner, scope, justification, expiry/removal milestone and false-pass test. |
| Agent dispatch now produces content-addressed receipts and bounded recovery. | The wrapper binds command/brief/allowance digests, resolved model, process identity, stdout/stderr/result digests and elapsed time (`scripts/run_maintenance_consolidation_agent.py:399-445`, `477-532`). It starts a new process group, kills the group on timeout, and retries exactly one silent zero-output death (`scripts/run_maintenance_consolidation_agent.py:451-495`). | Reuse the receipt envelope and process-group containment for Native research/review/validator workers. Retry only transport-class silent death; semantic/schema failures remain visible and superseded by a fresh receipt rather than overwritten. |
| Test budgets now mean elapsed time. | New task contracts use `elapsed_wall_clock_v2`; the production seam computes remaining elapsed budget and bounds subprocess timeout (`arnold_pipelines/megaplan/execute/test_budget.py:1-4`, `580-584`; `docs/arnold/maintenance-runtime-consolidation-execution-plan-2026-08-20.md:587-605`). | Require v2 elapsed budgets in all newly finalized Native milestones and validators. Preserve v1 only for pinned historical artifacts; do not refreeze static timeout-sum logic into `.pype` policy. |
| Cutover rehearsal is a supervised disposable-system proof. | The canary builds all mutable surfaces under one fresh root, uses local disposable origin/state, snapshots the selected-state tuple, supervises with external process-group kill/restart recovery, and claims only named protected-state invariants (`arnold_pipelines/megaplan/cloud/canary_sandbox.py:1-45`, `63-113`). | Use this discipline at GO-FORMAT, GO-1A/B, GO-2/GO-3 and GO-4 with milestone-specific mutation sets. The canary must test exact Native transition handlers, never a friendlier test-only path. |
| Bounded judged exceptions can remain honest without weakening invariants. | MRC's final log records accepted historical OOM treatment, deterministic halts, explicit deviations, and a protected-state churn adjudication rather than silently rewriting evidence (`docs/arnold/maintenance-runtime-consolidation-execution-log-2026-08-20.md:492-527`, `546-553`). | Introduce a closed adjudication schema: exact failed clause, immutable raw evidence, bounded exception rule, judge receipt, taint, prohibited inferences, expiry/retest trigger, and superseding receipt. Exceptions cannot satisfy authority, effect, source-authority, or zero-bypass musts. |
| Candidate provenance and rollback are first-class. | MRC requires install receipts for both candidates and a pointer-only rollback with before/post comparisons (`docs/arnold/maintenance-runtime-consolidation-execution-plan-2026-08-20.md:744-785`). | Every Native cut records old/new producer digests, selected decoder/lowerer/runtime, transition receipt, post-state proof, rollback target and supersession chain. Rollback selects a prior verified binding; it never rewrites admitted history. |

### 3.2 MRC must not be mistaken for Custody M11

The report already warned that similarly named local contracts are not accepted M11 and that Native must pin exact Run Authority, Custody, WBC, query, recovery and validator APIs from the accepted completion manifest (`docs/arnold/megaplan-native-representation-report.md:215-240`). The current Custody initiative still describes its nine residual milestones and states its chain is deliberately unlaunched/fail-closed (`.megaplan/initiatives/custody-control-plane/README.md:51-83`, `125-146`). MRC consolidates a successor operational runtime; it does not mint the missing `custody-control-plane/completion-manifest.json` or `bounded-incident-projection-handoff.json` required by the Native chain (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:14-19`).

The state is stronger than “manifest absent”: the independent 2026-08-02 audit explicitly invalidates commit `d10b0fef2b6`'s M11 completion/promotion claim because effect bypasses and shadow authorization remained; it requires a superseding Run Authority quarantine decision, a zero-blocker ownership decision, a complete portfolio, approval, full M11 suite and production-vector canary (`.megaplan/audits/critique-ledger-incident-sol-review-20260802.md:70-78`). The post-M11 release record is also still labeled **in progress**, with final integrated validation, release/promotion, runtime canary and downstream launch gates outstanding (`docs/megaplan/post-m11-release-evidence-20260731.md:3-12`, `124-141`). Therefore P1 is corrective re-acceptance, not clerical manifest generation.

**Adjusted rule:** run an explicit MRC-to-M11 capability crosswalk before Native S1. Rows may be `identical accepted API`, `compatible adapter owned by M11`, `MRC-only operational pattern`, or `missing M11 proof`. No local facade, report receipt, maintenance capability or canary verdict may be relabeled as the M11 admission artifact.

### 3.3 Earlier native epics are substrate/history, not the active finish line

The earlier Native Python completion and composition manifests list all milestones done (`.megaplan/initiatives/native-python-pipelines-completion/completion-manifest.json:7-120`; `.megaplan/initiatives/native-composition-followup/completion-manifest.json:7-103`). The earlier platform manifest likewise lists M1–M6 done and binds the old `.pypeline`/planning/handler surface (`.megaplan/initiatives/native-platform-followup/completion-manifest.json:7-118`, `114-202`). The alignment plan warns that completion truth is not report conformance and requires visible source plus false-pass guards (`docs/arnold/megaplan-native-representation-alignment-plan.md:91-120`, `170-173`). The new corrective README explicitly retires the old standalone completion chain as a launch target, while preserving its contracts/briefs as normative inputs (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:182-205`).

### 3.4 The authoring endpoint changed from `.pypeline` to `.pype`

The alignment baseline still names `.pypeline` as the target (`docs/arnold/megaplan-native-representation-alignment-plan.md:27-33`), but the later adopted contract and corrective initiative make `.pype` the sole live durable suffix and permit `.pypeline` only as historical text or an expiry-bound reader for pinned pre-cutover artifacts (`docs/arnold/pype-authoring-contract.md:1-20`; `.megaplan/initiatives/megaplan-native-parity-corrective/README.md:66-85`). This is a documentation and validator delta: every matrix row, source-path invariant, generated example, package-data rule, editor integration, converter and clean-install test must be amended to `.pype` without rewriting old evidence.

### 3.5 Infrastructure changed from direct/Hermes dispatch to OMP-backed launchers

MRC's wrapper routes agent roles through `launch_omp_agent.py` and records the actual resolved model (`scripts/run_maintenance_consolidation_agent.py:19-31`, `137-163`, `477-532`). Native evidence schemas must therefore record requested route, resolved model, launcher digest, process identity and output digests rather than inferring model identity from a profile label. Routing is infrastructure metadata, not product route authority.

### 3.6 Completion evidence is checkout-local and the durable launch branch differs

The deprecated sequencing analysis records that all three prepared chains targeted the same Custody checkout because `chain_completed` state and completion manifests are checkout-local; unrelated workspaces can make a genuinely completed predecessor invisible (`docs/arnold/DEPRECATED-completion-spec-sequencing-and-ownership.md:50-55`). It also records `editible-install` as the then-durable source branch and exact initiative/spec hash verification as a launch requirement (`docs/arnold/DEPRECATED-completion-spec-sequencing-and-ownership.md:57-61`). The reconciliation now controls execution order and requires authoritative-checkout evidence rather than inferred launch authority.

## 4. Reuse policy: import patterns, not maintenance semantics

### Reuse directly

- Canonical JSON/digest helpers, immutable invocation receipt shape, artifact digest verification, reviewer-process independence, allowance registry mechanics, stable validator issue ordering, and receipt supersession (`scripts/run_maintenance_consolidation_agent.py:35-59`, `86-134`, `399-445`, `477-532`; `scripts/validate_maintenance_runtime_consolidation_evidence.py:59-100`, `127-159`, `247-358`).
- Mint-only/narrow-only capability mechanics for transition handlers, provided Native binds accepted RA/Custody/WBC identities rather than maintenance-local evidence (`arnold_pipelines/megaplan/cloud/current_target_liveness.py:408-535`).
- External supervisor, process-group containment, complete selected-state snapshot/restore, disposable origins and environment containment (`arnold_pipelines/megaplan/cloud/canary_sandbox.py:1-45`, `63-113`).
- Elapsed-budget v2 and one production enforcement seam (`arnold_pipelines/megaplan/execute/test_budget.py:1-4`, `580-584`).

### Adapt behind Native-owned schemas

- Report/effect receipt separation becomes diagnostic/transition/effect/terminal receipt separation; exact required coordinates differ by boundary (`arnold_pipelines/megaplan/cloud/maintenance_dispatch.py:89-173`).
- Allowances gain Native-specific classes: pinned legacy reader, transitional route seam, generated projection, environmental deviation, adjudicated historical exception, and validator-tooling bootstrap.
- Canary steps are generated from each milestone's declared transition and selected-state inventory. MRC's specific S1–S14 card is evidence precedent, not a universal workflow.
- Wrapper retry remains transport-only and records attempt/supersession lineage. It must not retry a transition or effect whose idempotency/adoption state is unknown.

### Do not import

- Maintenance schedule occurrence schemas, efficiency thresholds, report cadences, ticket recommendations, daily-observer topology or maintenance product routes. These remain maintenance-domain behavior (`arnold_pipelines/megaplan/maintenance/operational_policy.py:9-16`, `136-150`; `arnold_pipelines/megaplan/maintenance/daily_runner.py:7-49`).
- MRC's role-to-model table as a workflow policy. It is execution infrastructure and may change independently (`scripts/run_maintenance_consolidation_agent.py:19-31`).
- Report-only receipts as authority, existence-as-completion, liveness-as-permission, or projection/status as route truth. MRC itself forbids those interpretations (`arnold_pipelines/megaplan/cloud/maintenance_dispatch.py:89-173`, `280-364`; `docs/arnold/maintenance-runtime-consolidation-execution-plan-2026-08-20.md:827-841`).
- MRC's local `MutationCapability` as a substitute for accepted M11 grants/leases/WBC. It is a useful mechanism; Native admission still consumes the predecessor manifest required by its chain (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:14-19`).
- Broad-suite-once policy as a universal development rule. Use it only at explicit final closure gates; milestone validators should run focused deterministic contracts first (`docs/arnold/maintenance-runtime-consolidation-execution-plan-2026-08-20.md:787-809`).
- MRC's generated evidence bodies, failed-publication state, superseded identity code or broad automation. The MRC goal explicitly excludes those from the successor (`docs/goal-execute-maintenance-runtime-consolidation.md:10-15`). Native should reuse schema/validator mechanics and content-addressed references, not copy the corpus.
- Canary rehearsal tests as green regression coverage. Two central rehearsal nodes are registered as pre-existing identical failures with unassigned debt and next-major revalidation (`docs/arnold/maintenance-runtime-consolidation-evidence/preexisting-waiver-register.json:175-196`). Native canary acceptance must add its own green production-path tests plus runtime artifacts; MRC's artifact proof is precedent, not inherited coverage.
- The MRC broad-suite receipt as authoritative Native closure. The current manifest marks its broad-suite receipt `authoritative: false` (`docs/arnold/maintenance-runtime-consolidation-evidence/manifest.json:623-628`). Native S7 and Platform S6 must produce their own admitted final-suite receipts.
- “MRC completed” as authorization for live promotion. MRC intentionally stops before live promotion and leaves that as a separate operator decision (`docs/goal-execute-maintenance-runtime-consolidation.md:17-28`). Native may consume the verified candidate and patterns without claiming that any production pointer or M11 authority moved.

## 5. Adjusted ordered milestone plan

### Prerequisite P0 — MRC closeout intake and authority crosswalk

**Scope.** Freeze the exact MRC candidate/head, validate its evidence manifest, inventory APIs and receipts relevant to Native, and create an MRC→M11→Native crosswalk. Do not modify Native runtime authority. The crosswalk must explicitly show that MRC completion is not Custody completion (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:14-19`; `.megaplan/initiatives/custody-control-plane/README.md:125-146`).

**MRC reuse.** Evidence manifest/validator, invocation receipts, allowance registry, supersession chain, candidate provenance.

**Acceptance evidence.** `mrc-native-intake-manifest.json`, source SHA/digests, validated MRC manifest receipt, API inventory, ownership/disposition table, and negative test proving an MRC receipt cannot satisfy the Custody launch precondition.

**Alignment rows/waves.** H0, H2, H4, H8; D12–D13 (`docs/arnold/megaplan-native-representation-alignment-plan.md:162-173`, `193-196`).

**Risk.** False equivalence between operational runtime consolidation and accepted cross-contract authority.

**Deferral owner.** Any missing RA/Custody/WBC capability returns to Custody M11; Native may not implement a substitute.

### Prerequisite P1 — Custody M11 admission resolution

**Superseded-by-revision note.** The pre-reconciliation instruction to finish all nine local residual milestones is historical guidance, not the controlling recovery path.

**Scope.** Resolve Native admission against canonical Custody and Run Authority outputs. Locate/import and validate any superseding Run Authority disposition, accepted zero-blocker ownership decision, content-addressed completion manifest and proof map, bounded-projection handoff, and installed/runtime/production-vector canary acceptance from the authoritative checkout. If any required output does not exist, Custody—not Native—performs the corrective re-acceptance work needed to produce it. P1 is an admission/result gate, not a rerun directive (`docs/arnold/native-plan-reconciliation-2026-08-24.md:35-63`, `184-195`).

**MRC reuse.** Typed capabilities, read-only adapters, report/effect receipt separation, supervised canary, and evidence-validator discipline may inform Custody-owned corrective work; they confer no M11 authority.

**Acceptance evidence.** P1 validates and content-addresses the first five revision NO-GO gates: canonical Run Authority disposition, approved zero-blocker ownership, accepted Custody `completion-manifest.json` and proof map, accepted `bounded-incident-projection-handoff.json`, and complete production-vector/canary acceptance. Its admission result also encodes the sixth gate—the P2 bootstrap manifest plus its three readiness artifacts—as an explicit unsatisfied blocker owned by P2. Native admission becomes GO only after P2 satisfies that final row; P1 does not fabricate or pre-consume its successor's output.

**Alignment rows/waves.** H2, H5, H9; D8, D11–D13.

**Risk.** Treating an audit, local facade, MRC pattern, report receipt, status projection, or historical completion claim as the canonical accepted M11 result.

**Deferral owner.** Custody Control Plane and Run Authority only; absence is a stop condition.

### Prerequisite P2 — Milestone-gate bootstrap

**Scope.** Implement generic pre-merge content-addressed conformance gates, merge-HEAD revalidation, exact predecessor-artifact assertions, typed receipt-consuming transitions and independent post-transition verification (`.megaplan/initiatives/megaplan-chain-milestone-gates/README.md:1-31`).

**MRC reuse.** Manifest validator, one deciding independent review, exact artifact digests, receipt supersession and process identity.

**Acceptance evidence.** Bootstrap completion manifest plus `downstream-spec-readiness.json`, `completion-crosswalk-readiness.json`, and `editable-runtime-readiness.json`, exactly as required by Native (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:5-13`).

**Alignment rows/waves.** H0, H2, H5; all D waves indirectly.

**Risk.** Self-certification by the gate implementation under test; stale pre-merge evidence accepted after merge.

**Deferral owner.** Generic chain engine/bootstrap initiative.

### Native S1 — Custody admission and semantic-preservation baseline

**Scope.** Execute M11 probes; freeze semantic/identity/trace/store/proof inventories; stage `.pypeline`→`.pype` without selection; freeze fixed scenarios, source oracle, raw verifier and mutation corpus (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:119-123`; `.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:52-65`).

**MRC reuse.** Baseline manifest, inventory equality, allowance registry, read-only source intake, invocation receipts.

**Acceptance evidence.** S1 conformance/traceability/proof map/receipt; full carrier inventory; exact M11 version pins; expected-red corpus; no runtime selection change.

**Alignment rows/waves.** Canonical source path, trace-only shadow, golden regeneration guard, behavior parity; H0–H8; D14–D15 (`docs/arnold/megaplan-native-representation-alignment-plan.md:149-154`).

**Risk.** Editing the candidate while measuring baseline; silently converting historical `.pypeline` evidence.

**Deferral owner.** S2F owns compiler/converter; M11 owns missing APIs.

### Native S2F — `.pype` compiler, linker, identity and converter; GO-FORMAT

**Scope.** Implement exact-one `.pype`, private/shared boundary rules, static imports without source execution, canonical identity/executable closure, package correspondence, converter, diagnostics, preview and pinned legacy reader. Then readiness → suffix/admission transition → post-transition GO-FORMAT (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:66-95`; `docs/arnold/pype-authoring-contract.md:69-105`, `128-193`).

**MRC reuse.** Candidate provenance receipts, guarded transition capability, complete disposable canary, allowance expiry/supersession.

**Acceptance evidence.** Positive/negative grammar corpus; source-map diagnostics; checkout/wheel/cloud equality; converter identity map; transition and post-transition receipts; zero new `.pypeline` admission.

**Alignment rows/waves.** Runtime-list iteration, dynamic map, typed loop outcomes, source readability, canonical path; H6–H8; D14–D15.

**Risk.** Rename-only migration; import-time execution; path-derived identity; preview path gaining durability.

**Deferral owner.** Platform S2B/S3 owns product-neutral core/tooling publication, not Native correctness.

### Native C1 — Completion contract and identity shadow

**Scope.** Land experimental neutral completion contracts, immutable spec/identity/serialization, candidate outcome registry, named-exit terminal, shadow generation, false-done/`REVIEW` fixture and divergence ledger (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:96-110`).

**MRC reuse.** Typed immutable receipts, manifest digests, judged exception taint, read-only shadow comparison.

**Acceptance evidence.** C1 proof pack, negative false-done fixture, append-only divergence ledger, no authority/effect capability in shadow.

**Alignment rows/waves.** Bounded loops, review outcomes, behavior parity; D10, D12, D14.

**Risk.** Shadow “green” treated as completion; product-specific completion types leak into neutral kernel.

**Deferral owner.** S2R owns live enablement; Platform S2A/S6 owns public stability.

### Native C2 — Completion binding/evaluation shadow

**Scope.** Implement immutable binding/evaluation schemas, proof modes, aggregation signatures, persisted-wire decoder matrix, restore/projection invariance and shadow atomic acceptance (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:111-125`).

**MRC reuse.** Evidence-bound exact identity, effect/report separation, restore snapshots, superseding receipts.

**Acceptance evidence.** C2 proof pack; cross-version decoder positives/negatives; projection delete/rebuild/forgery fixtures; no authoritative writer.

**Alignment rows/waves.** Path checkpoints, golden guard, behavior parity; D10, D12–D14.

**Risk.** Python type compatibility mistaken for wire compatibility; projection existence treated as acceptance.

**Deferral owner.** S2R owns first authoritative decoder promise.

### Native S2R — Durable primitives and custody binding; GO-0

**Scope.** Reconsume GO-FORMAT/C1/C2; implement typed decisions/outcomes, named loop exits, bounded loops, keyed reducers, frozen fanout bindings, retry/fallback, suspensions/reentry, checkpoints, call-site policy, typed errors and agentic-phase boundary; bind complete M11 action envelope; run the only kernel-enablement transition (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:126-156`; `.megaplan/initiatives/megaplan-native-parity-corrective/README.md:95-103`, `147-159`).

**MRC reuse.** Mint-only capability, one CAS/transition seam, elapsed budgets, append-only events, read-only projections, supervised crash/restore canary.

**Acceptance evidence.** Generic primitive corpus; ordered/multiset/decision/digest proofs; stale fence/epoch negatives; checkpoint restore; GO-0 transition/post-verification receipts; exactly one enabled completion kernel.

**Alignment rows/waves.** Bounded loop, runtime iteration/map, typed loop outcomes, path checkpoints, timeout/model policy; H7, H9; D12–D14.

**Risk.** Generic runtime reinterprets product routes; ambient policy/config becomes authority.

**Deferral owner.** Open streams remain unsupported unless separately chartered (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:95-103`).

### Native S3A — Prep/plan/critique cutover; GO-1A

**Scope.** Create `workflow.pype` and plan-quality critique child; move prep clarification, plan boundary, robustness skip, evaluator retry, dynamic lens fanout/reducer and fallback into source/policy; bind execution plane and shared resume gate; transition prep/plan/critique once (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:157-186`).

**MRC reuse.** Transition receipt, current capability revalidation, wrapper transport retry, evidence manifest and allowances for temporary legacy gate seam.

**Acceptance evidence.** D1/D2 golden traces; malformed/evaluator retry fixtures; human clarification death/resume; handler-purity mutations; old front-half producer inert; GO-1A receipt.

**Alignment rows/waves.** Prep clarification, plan artifacts, critique skip/retry/fanout, human suspension, model routing, handler purity; D1–D2, D11, D15 (`docs/arnold/megaplan-native-representation-alignment-plan.md:124-129`, `134`, `143`, `150`).

**Risk.** A visible `parallel_map` wraps a handler that still selects lenses/retries/routes.

**Deferral owner.** S3B owns gate/revise; S4 owns tiebreaker/finalize.

### Native S3B — Gate/revise cutover; GO-1B

**Scope.** Move gate preflight, payload recovery, signal build, reprompt, downgrade, debt/fallback, route decision and critique/gate/revise loop into source/policy; transition legacy gate seam and prove remaining carrier inertness (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:187-217`).

**MRC reuse.** Typed diagnostic vs effect receipt, append-only debt event, evidence-bound transition, judged exception schema.

**Acceptance evidence.** D3/D4 goldens; malformed input, unavailable worker, reprompt, downgrade, cap/severity and debt fixtures; GO-1B receipt; no handler route authority.

**Alignment rows/waves.** Bounded critique/gate/revise, gate preflight, signal/reprompt, debt/fallback, timeout policy, handler purity (`docs/arnold/megaplan-native-representation-alignment-plan.md:129-132`, `142`, `150`).

**Risk.** State/status-derived `next_step` survives as hidden authority.

**Deferral owner.** S6 owns auto-drive/control projection demotion.

### Native S4 — Tiebreaker, finalize and durable human reentry

**Scope.** Split tiebreaker into named child workflow with researcher/challenger/synthesis/decision; expose finalize fallback/test-selection outcomes; make all human waits durable suspension/reentry points; transition producer/seam/fence atomically.

**MRC reuse.** Invocation receipts with requested/resolved model, process identity, supersession; process-group containment; capability-bound transition.

**Acceptance evidence.** D5/D6/D11 traces; tiebreaker pick/iterate/escalate/replan; finalize failure/baseline selection; duplicate-human arbitration; process-death resume; post-transition receipt and old seam inertness.

**Alignment rows/waves.** Tiebreaker path, human suspension, finalize fallback, path checkpoints, model routing (`docs/arnold/megaplan-native-representation-alignment-plan.md:133-135`, `143`, `148`).

**Risk.** Child workflow is a component constant or shared handler rather than one canonical `.pype` with stable call-site identity.

**Deferral owner.** Platform S3 owns generalized editor/navigation UX.

### Native S5A — Delivery shadow and per-effect-class GO-2 proof

**Scope.** Build execute DAG/batch, approval gates, review fanout/reducer, review/rework loop, infra retry, cap and human outcomes in non-authoritative/no-effect shadow. Inventory every external-effect protocol class and prove it directly or by accepted equivalence (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:127-138`, `161-170`).

**MRC reuse.** Report/effect separation, exact effect identity, disposable canary, elapsed budgets, one deciding review, allowance/exception taint.

**Acceptance evidence.** D7–D10 goldens; DAG partial resume; cancellation races; ambiguous-effect reconciliation; old/new dry-run comparison; effect-class inventory equality; GO-2 receipt; zero live writes.

**Alignment rows/waves.** Execute batches/gates, execute-review loop, review fanout/caps, behavior parity (`docs/arnold/megaplan-native-representation-alignment-plan.md:136-140`, `153`).

**Risk.** Incomplete effect inventory or “equivalent” classes with different idempotency/reconciliation semantics.

**Deferral owner.** Missing protocol class blocks S5B; it is not waived by narrative.

### Native S5B — Live delivery cutover and review/rework

**Scope.** Consume current readiness and GO-2; atomically cut the sole live delivery writer; post-verify exact writer fences, named-exit unwind, cancellation, effect ambiguity, review/rework, reconciliation and bounded projection consumption (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:132-170`).

**MRC reuse.** Candidate install/provenance receipts, guarded rebind, pointer-only rollback, supervised full selected-state snapshot/restore, whole-process-group kill.

**Acceptance evidence.** Transition/post-transition receipt; no dual write; crash after intent/outcome fixtures; stale worker refusal; rollback returns selected binding without rewriting admitted history; installed/cross-host proof.

**Alignment rows/waves.** D7–D10, D12–D13; H5, H9.

**Risk.** Dual writer, rollback by state rewrite, or canary path differing from production transition.

**Deferral owner.** M11 owns missing action/effect API; S6 owns control plane.

### Native S6 — Override, recovery, auto-drive and projection adoption; GO-3

**Scope.** Move full override action meanings, recovery, auto-drive liveness/retry/cap/escalation and reconfiguration routes into product source/declared policy; demote status/watchdog/auditor to read-only projections; prove reachable arbitration and retained carriers inert.

**MRC reuse.** Evidence-bound repair classification, operator-only locked migration, read-only auditor, root capability, guarded adoption/rebind, append-only fenced events.

**Acceptance evidence.** Every override action fixture; stale/superseded request negatives; repair revalidation; projection delete/rebuild/forgery; reachable arbitration index; zero route selection from liveness/status; GO-3 receipt.

**Alignment rows/waves.** Override full surface, auto-drive/liveness, handler purity, behavior parity (`docs/arnold/megaplan-native-representation-alignment-plan.md:141`, `147`, `150`, `153`); D11–D13, D15.

**Risk.** Importing maintenance repair policy into product semantics; observer recommendations gaining mutation capability.

**Deferral owner.** Platform may generalize stable mechanics only after S7 classification.

### Native S7 — Independent topology conformance and GO-4

**Scope.** Run independent source/raw proof, complete restore coverage, zero route-capable seam scan, validator self-mutations, allowance closure, inventory equality, clean checkout/wheel/cloud proof, completion manifest and content-addressed Platformization handoff (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:137-159`).

**MRC reuse.** Final evidence-pack validator, immutable baseline plus immediate pre/post snapshots, independent review, broad-suite once lock, superseding receipts, honest bounded exceptions.

**Acceptance evidence.** New corrective conformance/traceability files and validator; all 31 alignment requirements dispositioned; all D waves green; no live `.pypeline`; no handler/runtime/CLI route authority; completion manifest and handoff digest; GO-4.

**Alignment rows/waves.** Every matrix row; H0–H9; D1–D15 (`docs/arnold/megaplan-native-representation-alignment-plan.md:122-196`).

**Risk.** Validator validates its own generated assertions; stale goldens overwritten; exception used to waive source-authority/zero-bypass.

**Deferral owner.** Only explicit Stage-2 candidates move to Platformization; unresolved Stage-1 musts block completion.

### Platform S1 — Candidate inventory and contract freeze

**Scope.** Consume S7 handoff; classify each construct core/stable/experimental/Megaplan-specific; freeze descriptors, ports/outcomes/state/policy/effect/capability/evidence contracts and invalid corpus (`docs/arnold/megaplan-native-representation-report.md:2435-2462`; `.megaplan/initiatives/native-workflow-platformization/README.md:63-77`, `115-135`).

**MRC reuse.** Inventory/evidence manifest and allowance discipline.

**Acceptance evidence.** Candidate/coupling inventory, zero-Megaplan-import proof, exclusions, contract snapshots, invalid corpus, stage receipt.

**Alignment rows/waves.** Product/neutral boundary, handler purity, source readability, golden guard; H0–H4, H6, H9; D13–D15 (`docs/arnold/megaplan-native-representation-alignment-plan.md:150-154`, `162-173`, `193-196`).


**Risk.** Premature abstraction from one consumer.

**Deferral owner.** Experimental registry until S5 two-consumer proof.

### Platform S2A — Product-neutral runtime/admission/authority

**Scope.** Generalize only proven runtime lifecycle, resolution, authority admission, isolation, completion binding/evaluation, attempt/session continuation and failure semantics without a second kernel enablement (`.megaplan/initiatives/native-workflow-platformization/README.md:78-81`, `125-141`).

**MRC reuse.** Narrow capabilities, receipt separation, append-only evidence, guarded adoption/rebind.

**Acceptance evidence.** Neutral package, fault/race/restore suite, no product reverse imports, Native golden adapter parity, transition/post-verification receipt.

**Alignment rows/waves.** Gate debt/effects, human suspension, execute gates, review caps, timeout and path checkpoints; H3, H5, H9; D8, D10–D13 (`docs/arnold/megaplan-native-representation-alignment-plan.md:132-142`, `148`).

**Risk.** New generic runtime changes Native semantics or duplicates M11 stores.

**Deferral owner.** S6 owns stable publication.

### Platform S2B — Product-neutral `.pype` authoring/package core

**Scope.** Productize compiler/linker, package correspondence, graph locks, converter/refactors, static diagnostics, identity and completion templates (`.megaplan/initiatives/native-workflow-platformization/README.md:82-86`).

**MRC reuse.** Provenance/installation receipts and deterministic manifests.

**Acceptance evidence.** Clean-wheel builds, mixed-version rejection, transactional refactor rollback, source/runtime golden adapters, Native parity unchanged.

**Alignment rows/waves.** Runtime iteration/map, typed loop outcomes, canonical source path and readability; H3, H6–H7; D14–D15 (`docs/arnold/megaplan-native-representation-alignment-plan.md:144-146`, `152`, `154`).

**Risk.** Refreezing a second authoring contract instead of extending the Stage-1 corpus.

**Deferral owner.** S3 owns full public DX; S6 stable promise.

### Platform S3 — Developer tooling

**Scope.** Build format/lint/topology/preview/test, editor/navigation, package editing, concise prompts, normalized parse/repair, completion inspection and usability benchmarks (`.megaplan/initiatives/native-workflow-platformization/README.md:87-91`, `125-135`).

**MRC reuse.** Bounded wrappers, resolved-model receipts, elapsed budgets, process containment.

**Acceptance evidence.** Unfamiliar-author tasks, source-mapped diagnostics, deterministic local harness, crash-safe transactional edits, performance baselines.

**Alignment rows/waves.** Source-mapped diagnostics/local harness and canonical source readability; H5–H7; D14–D15 (`docs/arnold/megaplan-native-representation-report.md:2002-2028`; `docs/arnold/megaplan-native-representation-alignment-plan.md:154`, `169-172`, `195-196`).

**Risk.** Tooling path executes a weaker admission/runtime contract.

**Deferral owner.** S6 publication criteria.

### Platform S4 — First isolated extraction/recomposition

**Scope.** Extract first proven patterns; make Megaplan consume them without duplicate completion writer; prove namespace/state/effect/dependency isolation (`.megaplan/initiatives/native-workflow-platformization/README.md:92-93`, `125-135`).

**MRC reuse.** Candidate provenance, guarded transition, disposable canary and rollback.

**Acceptance evidence.** Source reuse, clean-wheel reuse, deterministic resolution and supported-shape recomposition proofs—the first four distinct reuse claims (`docs/arnold/megaplan-native-representation-report.md:2283-2297`).

**Alignment rows/waves.** Tiebreaker/execute/review child topology, path checkpoints, behavior parity and handler purity; H1, H3, H5–H9; D5, D7, D9, D12–D15 (`docs/arnold/megaplan-native-representation-alignment-plan.md:133`, `136`, `139`, `148`, `150`, `153`, `164-173`, `186`, `188`, `190`, `193-196`).

**Risk.** Copy-based extraction or friendlier test-only hosting.

**Deferral owner.** S5 owns substitutability/resume challenge.

### Platform S5 — Adversarial unrelated consumer

**Scope.** Use the same packages from a mechanically independent product with different types, outcomes, policies, effects, storage, nesting, human gate and concurrent attempts (`.megaplan/initiatives/native-workflow-platformization/README.md:94-95`, `125-135`).

**MRC reuse.** Independent candidate environments, receipt/evidence isolation, crash/rollback canary.

**Acceptance evidence.** All six reuse claims separately reported; new-instance substitution and resume compatibility are distinct verdicts (`docs/arnold/megaplan-native-representation-report.md:2283-2297`).

**Alignment rows/waves.** Product/neutral boundary, platform preservation, behavior parity and golden guard; H1, H3, H5, H9; D12–D15 (`docs/arnold/megaplan-native-representation-alignment-plan.md:151`, `153`, `165`, `167`, `169`, `173`, `193-196`).

**Risk.** A contrived second consumer that preserves Megaplan assumptions.

**Deferral owner.** Failed candidates remain experimental.

### Platform S6 — Certification, evolution and adoption

**Scope.** Publish only capability profiles and components that pass descriptor, static validation, clean install, recomposition, isolation, fault, upgrade, substitution, causal evidence and combined Stage-1/Stage-2 corpus (`.megaplan/initiatives/native-workflow-platformization/README.md:96-105`, `115-141`).

**MRC reuse.** Final content-addressed evidence manifest, independent review, supersession/evolution receipts, pointer rollback.

**Acceptance evidence.** Final proof map/completion manifest, stable package descriptors, compatibility ranges, migration/rollback proofs, Native and unrelated-consumer certification.

**Alignment rows/waves.** Every row affected by extracted components, with emphasis on golden guard, canonical path, behavior parity, readability and handler purity; H0–H9; D1–D15 (`docs/arnold/megaplan-native-representation-alignment-plan.md:122-196`).

**Risk.** Publication based on import success or one consumer; accidental semantic change during extraction.

**Deferral owner.** Uncertified components remain internal/experimental; no compatibility claim.

## 6. Evidence-pack standard for every milestone

Every milestone proof pack should contain:

1. immutable inputs: source SHA, predecessor manifest/proof rows, brief/North Star/contract digests;
2. selected-surface inventory and exact owning milestone;
3. implementation invocation receipts with requested/resolved model, launcher/brief/command/output digests and process identity;
4. focused test receipts and elapsed-budget state;
5. static source/carrier scan plus expected-red mutations;
6. runtime golden traces and raw events/decisions/effects/checkpoints;
7. candidate install/runtime/decoder/lowerer identities;
8. pre-transition readiness receipt, transition receipt and independent post-transition receipt where authority changes;
9. canary pre/post/rollback selected-state census;
10. allowance/exception registry with owner, scope, taint, expiry/removal milestone and overlap checks;
11. independent review receipt and any revision/re-review supersession chain;
12. machine validator output with stable issue codes and zero dangling references.

This extends MRC's manifest discipline, whose semantic validator checks schema/digests/cross-record references/routing/reviewer independence/allowances/shards (`scripts/validate_maintenance_runtime_consolidation_evidence.py:174-245`, `247-358`, `387-433`), while preserving Native-specific authority and semantic checks.

## 7. Measurements required before launch

Unknowns must be measured, not guessed:

- **Exact M11 state:** run chain verification against the Custody chain and record the first missing/stale proof row. Required output is the accepted completion manifest and bounded-projection handoff, not a status label (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:14-19`).
- **Milestone-gate state:** verify its chain and require all three readiness artifacts (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:5-13`).
- **Current handler control inventory:** AST/source scan every D1–D15 carrier for state transitions, route strings, loop/cap decisions, fanout, waits, effect admission and terminal acceptance; compare to the matrix's required false-pass tests (`docs/arnold/megaplan-native-representation-alignment-plan.md:122-196`).
- **`.pypeline` live surface:** enumerate loader/compiler/package/editor/example/test references; classify historical, pinned-reader, generated, or live. S7 acceptance is zero live authoring/admission (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:66-77`, `137-145`).
- **Effect protocol classes:** trace every production external action through intent, idempotency, effect, outcome/ambiguity, adoption/reconcile and compensation before GO-2.
- **Selected-state canary tuple:** derive it from actual writes of each transition and verify restore byte-exactness; do not copy MRC's tuple blindly (`arnold_pipelines/megaplan/cloud/canary_sandbox.py:93-113`).
- **Performance baselines:** compile/lower, local harness, checkpoint/replay, dynamic fanout/reducer, query/projection, clean install and editor/diagnostic latency must have numeric baselines before Platformization claims no regression.

## 8. Open questions for the operator

1. **Custody M11 disposition:** is there an accepted remote completion manifest not yet imported into this branch, or must the local nine-milestone Custody chain run? The current checkout contains no artifact satisfying Native's required path (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:14-19`).
2. **MRC relationship:** should MRC become an admitted implementation candidate inside Custody M11, or remain a sibling operational-runtime precedent consumed only by crosswalk? No Native milestone should decide this implicitly.
3. **Bootstrap launch:** which trusted external CI/verifier and merge-readiness principal will certify the non-self-hosted milestone-gate bootstrap (`.megaplan/initiatives/megaplan-chain-milestone-gates/README.md:14-22`)?
4. **Exception authority:** who may approve bounded historical/environmental exceptions, and which must-level classes are categorically non-waivable? Recommended non-waivable classes: source authority, exact M11 admission, no dual writer, effect identity, terminal arbitration, restore-resistant fence/epoch, and zero live route-capable seams.
5. **Canary promotion principal:** who owns GO-FORMAT, GO-0, GO-1A/B, GO-2, GO-3 and GO-4 transition approval? The principal must be distinct from report/auditor surfaces.
6. **Legacy retention horizon:** how long must exact pinned `.pypeline` readers and old decoder/runtime artifacts remain resolvable for suspended runs? The answer drives retention, migration and rollback storage.
7. **Platform publication namespace:** which distribution(s) own runtime primitives, authoring core and reusable patterns? Decide before Platform S1 descriptor freeze, not during S4 extraction.
8. **Second consumer:** which real product will serve as the adversarial Platform S5 consumer? It must differ materially in types, policies, storage, effects, human gates and concurrency (`.megaplan/initiatives/native-workflow-platformization/README.md:125-135`).
9. **Review routing:** should Native reuse MRC's one-deciding-review cadence or require separate pre/post reviewers at authority transitions? Recommendation: one implementation review plus a mechanically independent post-transition verifier; never use the same process identity for both evidence roles (`scripts/validate_maintenance_runtime_consolidation_evidence.py:316-358`).
10. **Broad-suite policy:** retain MRC's exactly-once broad suite only at S7/Platform S6, or at additional authority cuts? Focused semantic and mutation suites remain mandatory at every milestone.

## 9. Immediate next actions

1. Import or generate the accepted Custody M11 completion manifest and bounded projection handoff; otherwise stop at P1.
2. Complete/verify the milestone-gate bootstrap and its three readiness artifacts; otherwise stop at P2.
3. Add the MRC→M11→Native capability crosswalk and Native-specific evidence-pack schema/validator to S1's brief before launch.
4. Amend the alignment ledger's target suffix and authoritative initiative references without rewriting old evidence.
5. Run S1 exactly as prepared. Do not start implementation at S3A merely because the current `.pypeline` already renders a plausible topology.
