# Revised Native Megaplan parity epic — hierarchical end-state audit

**Audit date:** 2026-07-21  
**Mode:** read-only adversarial plan audit; only round-2 audit artifacts were written  
**Locked sequencing premise:** a complete, clean, accepted `custody-control-plane` M11 end state exists before this epic starts. Current local/cloud M11 publication incompleteness is not scored as a Native Parity defect.

## Verdict

**Adheres with bounded amendments.**

The revision is no longer merely vocabulary-compatible. Its North Star, corrective plan, and active S1–S7 briefs correctly divide ownership among authored topology, Run Authority, Custody, WBC, and projections; preserve the four non-interchangeable identity domains; relocate WBC producers before deleting their legacy carriers; require current fence and epoch at positive-action boundaries; and make projection/evidence non-authority a negative-test obligation. The m1–m10 to S1–S7 compression did not lose a whole semantic domain.

It is not yet safe to launch unchanged. Four bounded defects remain:

1. The only schema-executable final gate does not pass or validate the declared `proof_map`; the current validator still accepts the old row/hash/boundary-fixture evidence model. The chain can therefore execute a blocking command and still validate the wrong proposition.
2. The plan assigns accepted decisions to Run Authority, but the sprint deliverables and S7 set-equality proof cover subject attempts and authority-increasing actions—not one accepted Run Authority decision for every typed product decision and consumed route transition. A parallel or incomplete decision history can survive.
3. Suspension/reentry identity is not explicitly bound to the authored program/call-site-policy digest and original WBC contract version. The same semantic path can otherwise resume after source, model policy, or boundary-version drift without an explicit migration/new-attempt decision.
4. Compression removed the historical real-Megaplan builder vertical-slice proof before broad extraction. S3 now combines the first load-bearing `build_pipeline()` seam, the whole front half, WBC producer relocation, and legacy-carrier deletion. That is feasible, but it lacks an internal stop/go boundary before the broad migration and deletion work.

A smaller scope-loss issue also remains: the representation report and historical M8 brief include `add-note`/non-routing annotation effects, while the active S6 action list omits them.

These are bounded because they do not require redesigning the seven-sprint architecture or duplicating Custody M11. They require hardening the existing final validator/proof-map path, adding one decision-history invariant, version-binding reentry, restoring one intra-sprint builder gate, and closing one action-list omission.

### Direct answer to the end-state challenge

If “execute exactly as written” means every brief obligation is behaviorally implemented, then the semantic text would eliminate hidden route authority, stale authority/custody, and evidence-as-authority. But the actual chain’s definition of successful execution does not yet prove that happened. **Yes: as the chain and validator stand, hidden semantic authority or evidence-as-authority can survive while the epic reports success; stale authority/custody can survive through version-drift reentry or missing decision-history joins.** The amendments below close that discrepancy between faithful implementation and machine-reported success.

## Method and disagreement reconciliation

Six isolated Hermes reviewers inspected the repository under non-overlapping lenses. Inventory work used MiMo/DeepSeek Flash; architectural lenses used DeepSeek Pro. Raw briefs, responses, metadata, and the aggregate report are retained in `briefs/` and `reviewer-results/` beside this audit. No reviewer saw another reviewer’s result before completion.

I rejected several reviewer findings after checking primary sources:

- Current Custody M11 incompleteness is outside scope under the locked premise. Findings that treated the checked-in M1–M4 chain or missing current completion manifest as a Native Parity design defect were discarded.
- `completion_contract_mode="shadow"` does **not** make the declared `final_conformance_gate` nonblocking. `_run_milestone_validations_blocking()` returns a blocking reason on validator failure and every milestone-advance path checks it (`arnold_pipelines/megaplan/chain/__init__.py:1126-1176,5042-5059,5277-5294,5882-5899`). The separate generic completion contract may be shadow, but the explicit final validator is hard-blocking.
- `final-proof-map.json` being absent before S7 is not itself a gap: S7 explicitly produces it (`briefs/s7-final-conformance-rollout.md:34-36`), and the runner requires it at validation time (`chain/__init__.py:953-967`). The real gap is that the validator command omits it.
- Revised S2 already enumerates dynamic collection schema, worker cap, reducer, child paths, per-item retry/fallback, sequential fallback, and runtime cardinality (`s2:12-21`). Revised S4 already requires true parallel tiebreaker children and the full decision vocabulary (`s4:11-17,35-40`). Revised S6 already requires explicit config-effect reentry (`s6:14-15,38-43`). Those earlier gaps are closed.
- Gate signal construction, normalization, and deterministic merging may remain inside pure phase bodies. Treating every such computation as a mandatory separate graph node would violate the plan’s justified semantic-compression rule (`NORTHSTAR.md:60-73`; corrective plan `:132-158`). The route, retry, cap, effect, and terminal distinctions remain explicit.

## Stable requirement matrix

Abbreviations: `NS` = active `NORTHSTAR.md`; `CP` = `docs/arnold/megaplan-native-parity-corrective-plan.md`; `S#` = active sprint brief; `RR` = representation report; `FA` = prior final audit; `CO` = custody-overlap audit. “Executable proof” names the proof the revised epic promises, not proof already present in today’s tree.

### A. Prior Native Parity requirements (stable NP IDs retained)

| ID | Requirement | Revised-plan location | Sprint | Executable proof | Status | Exact evidence |
|---|---|---|---|---|---|---|
| NP-01 | Canonical source is the sole product-topology authority. | NS ownership/done; CP machinery/final gates | S1, S3–S7 | Old-pattern negative fixture; source/lowering/runtime equality; hidden-carrier mutation/deletion | **Covered, final-gate amendment needed** | NS `:3-17,91-105`; CP `:181-205,420-439`; S1 `:30-49`; S7 `:40-46` |
| NP-02 | Prep/plan plus blocking clarification are typed source constructs with durable same-point resume. | CP semantic matrix; S3 front half; S4 durable reentry | S3–S4 | Clarification kill/restart, stale marker/fence/epoch negatives | **Covered** | S3 `:11-18,39-56`; S4 `:17,25-33,43-50` |
| NP-03 | Critique bare skip, selection, retry, dynamic lenses, sequential fallback, reducer. | S2 generic primitives; S3 product scope | S2–S3 | Runtime 0/1/N child sets, fallback/retry, source mutation, installed run | **Covered** | S2 `:12-21,36-43`; S3 `:12-18,43-47` |
| NP-04 | Gate signals, worker, normalize/validate, one reprompt/downgrade, backstops, debt, closed decision. | S3 product scope; pure-body rule | S3 | Split outcomes, cap severity, debt-effect trace, legacy mutation | **Justified semantic compression** | S3 `:15-21,39-47`; CP `:145-158,253-268` |
| NP-05 | Bounded critique/gate/revise loop with severity/no-progress exits. | NS; S2 loop primitive; S3 source slice | S2–S3 | Loop/cap/no-progress split outcomes and topology trace | **Covered** | NS `:21-22,70-73`; S2 `:12-15,38-41`; S3 `:18,43-47` |
| NP-06 | Parallel tiebreaker, synthesis, pick/reiterate/replan/escalate/abort/suspend, ordinary-path rejoin. | S4 product and gates | S4 | Parallel-child/reducer trace; all decision routes; replan reset/rejoin; kill/resume | **Covered** | S4 `:11-17,21-33,35-50`; CP `:270-282` |
| NP-07 | Typed finalize with baseline-failure fallback, retry, scoped refinalization. | S4 and reusable S5 cycle | S4–S5 | Finalize failure/recovery, scoped rework/refinalize trace | **Covered** | S4 `:14-16,29-41`; S5 `:7-10,23-25,46-55` |
| NP-08 | Approval, dependency-ready dynamic batches, complexity routing, fresh sessions, merge, no-review/human routes. | S5 product scope | S5 | Approval allow/deny, batch ordering, no-review, deferred-human, fresh-child trace | **Covered; fresh-session assertion is sprint detail** | S5 `:17-25,46-55`; CP `:284-304` |
| NP-09 | Path-addressed checkpoint/resume reruns only incomplete children. | S2 coordinates; S5 exact child identity/effect recovery | S2, S5 | Batch 2-of-4 restart; crash intent/outcome; partial resume | **Covered** | S2 `:22-34`; S5 `:29-44,50-65` |
| NP-10 | Review worker/check fanout, reducer, infra retry, typed decision, human verify. | S5 product scope | S5 | Review fanout/reducer, retry, human verify, split outcomes | **Covered** | S5 `:23-25,48-55` |
| NP-11 | One bounded finalize/execute/review/rework cycle, not duplicate passes. | S5 objective and gate | S5 | One reusable subworkflow; rework/re-review/cap traces | **Covered** | S5 `:5-13,48-55,67-73` |
| NP-12 | Exhaustive override/recovery/control surface with typed target/effect/reentry. | S6 | S6 | Per-action runtime scenarios, unknown denial, auto/CLI mutation | **Partial—non-routing annotation omission** | S6 `:9-25,38-44`; RR `:225-231`; historical M8 `:18-22` |
| NP-13 | Config changes are authored effects followed by exact current-phase reentry. | S6 product/gates; CP | S6 | Model/vendor/profile/robustness change/reentry scenarios | **Covered** | S6 `:14-15,21-25,40-43,59`; CP `:306-318` |
| NP-14 | Every human suspension has capability, durable semantic reentry, current RA and Custody. | S2 generic; S4 product | S2, S4 | Process death, stale approval/marker/fence/epoch/wrong target | **Covered; version-binding amendment needed** | S2 `:12-15,27-34`; S4 `:23-33,43-50` |
| NP-15 | Child identity uses task ID + batch identity + item path, not list index. | S5; S7 regression | S5, S7 | Collision, cardinality, cross-host and partial-resume tests | **Covered** | S5 `:29-36,59-65`; S7 `:66-68` |
| NP-16 | Closed typed outcomes/interfaces; raw strings cannot steer runtime. | S1 checker; S2 constructs; S7 deletion proof | S1–S3, S7 | Unsupported outcome fails; handler/runtime string mutation inert | **Covered** | S1 `:30-40`; S2 `:12-18`; S7 `:24-28,45-46` |
| NP-17 | Retry/timeout/model/fallback/effect policy is attached at authored call sites. | NS; S2; S3/S5 | S2–S5 | Policy mutation changes runtime; old defaults do not | **Covered** | NS `:21-22,66-73`; S2 `:12-20`; S3 `:20-27`; S5 `:17-25` |
| NP-18 | Retained phase bodies and transitive helpers are computationally pure. | NS compression rule; CP final gates | S1, S3–S7 | Transitive purity scan plus mutation; all failures blocking | **Covered, final-gate amendment needed** | NS `:60-68,93-97`; CP `:145-158,425-426`; S7 `:24-28` |
| NP-19 | Generic compiler/lowerer/runtime is product-neutral. | S2; S7 zero-coupling proof | S2, S7 | Neutral reference pipeline; forbidden-import/canonical-path mutations | **Covered** | S2 `:16-18,42-43,55-58`; CP `:189-191,424`; S7 `:24-25` |
| NP-20 | `build_pipeline()` consumes the full lowered graph without component overlay/reconstruction. | CP machinery; S3 work | S3 | Lowered/canonical set equality; source mutation; legacy mutation | **Covered but unsafe first-slice bundling** | CP `:183-187`; S3 `:25-36`; historical M3 `:24-34` |
| NP-21 | Runtime-sized fanout preserves item schema, worker cap, retry/fallback, reducer and names. | S2; S3/S5 application | S2–S5 | Neutral 0/1/N/collision/reducer proof then product traces | **Covered** | S2 `:12-21,38-43`; S3 `:12-14`; S5 `:17-24` |
| NP-22 | Auto-drive consumes events and requests authored actions; it does not derive routes/policy/resume. | S6 | S6 | Auto/status mutation cannot change product routes; projection forgery | **Covered** | S6 `:5-7,26-36,38-53` |
| NP-23 | Compatibility, manifest, CLI and projections are downstream adapters only. | NS; CP; S6/S7 | S3–S7 | Dead-delete/quarantine and compatibility mutation; no row cites them | **Covered** | NS `:93-105`; CP `:193-205`; S6 `:32-36`; S7 `:24-33,45-46` |
| NP-24 | Checkout, wheel/sdist and pinned cloud execute identical semantics. | NS; S1/S4/S7 | S1, S4, S7 | Clean installed/full split-outcome traces and loaded provenance | **Covered** | NS `:100-105`; S1 `:37`; S4 `:32-33`; S7 `:5-8,29-30,71` |
| NP-25 | Bare/light/extreme robustness changes authored critique/review/human behavior. | CP normative matrix; S3/S5; S7 | S3, S5, S7 | Robustness split-outcome matrix in installed/cloud runs | **Covered** | CP `:358-360,410-414`; S3 `:13,43-45`; S5 `:18-25,50-53`; S7 `:29-30` |
| NP-26 | Effects/checkpoints/final projections are explicit and runtime-derived, not synthesized evidence. | S2/S3/S5/S7 | S2–S7 | Effect intent/outcome, ambiguity/reconcile, generated runtime trace | **Covered, final-gate amendment needed** | S2 `:25-34`; S5 `:40-41,59-63`; S7 `:20-28` |
| NP-27 | Legacy carriers are deleted/hard-fenced only after consumers/producers move. | S3/S4/S5/S6/S7 | S3–S7 | Per-slice legacy mutation; final deletion/rollback gate | **Covered; S3 intra-sprint gate needed** | S3 `:29-36,46-56`; S4 `:29-33`; S5 `:42-44`; S6 `:32-36`; S7 `:31-33` |

### B. Custody/WBC/authority composition requirements

| ID | Requirement | Revised-plan location | Sprint | Executable proof | Status | Exact evidence |
|---|---|---|---|---|---|---|
| CP-01 | Admit only complete accepted M11 with exact source/installed/contracts/enforcement/proof pins. | README; chain prerequisite; S1 | Launch, S1 | `chain_completed` manifest validation plus immutable admission inventory | **Covered under locked premise** | README `:8-15`; chain `:5-9`; S1 `:5-23,51-65`; chain spec `:1724-1944` |
| CP-02 | Reuse M11 stores/APIs/queries/recovery/projections/proof; no parallel implementation. | NS non-duplication; S1 inventory | S1–S7 | Dependency inventory and absence scan; M11 fixtures reused | **Covered** | NS `:75-87`; S1 `:21-23,53-56`; CP `:160-179` |
| CP-03 | Keep semantic, RA, WBC and Custody identities distinct with causal/cardinality joins. | NS identity; S1 row schema; S2 mapping; S7 evidence | S1–S7 | Generated four-domain matrix and set equality | **Covered** | NS `:47-58`; S1 `:24-29,57-60`; S2 `:22-24`; S7 `:20-23` |
| CP-04 | Every positive action requires current RA grant/fence + current lease/epoch + required exact-version WBC evidence. | NS action rule; S2 validator binding; all product sprints | S2–S7 | Missing/stale grant/fence/lease/epoch/target/version negatives | **Covered; decision-history amendment needed** | NS `:33-45`; S2 `:25-34,45-53`; S7 `:50-52,62-64` |
| CP-05 | WBC evidence is durable history/conformance, never permission. | README/NS; every adoption gate | S1–S7 | Forged/historical WBC success cannot dispatch/resume/complete | **Covered** | README `:32-34`; NS `:33-45`; S2 `:49-50`; S4 `:47-50`; S7 `:53-56` |
| CP-06 | Custody lease is exclusive responsibility, never permission; exact target/epoch required. | NS; S2; S5 exact target | S2, S5–S7 | Broad-target and stale-epoch negatives; transfer increments epoch | **Covered** | NS `:25-27,33-41`; S5 `:29-36,59-65`; S6 `:48-49` |
| CP-07 | Relocate WBC producers from handler/phase names to canonical lowered node/children before deletion. | NS done; S3/S4; S7 equality | S3–S7 | Producer registry equals authored/lowered/executed child set | **Covered** | NS `:96-97`; S3 `:29-30,51-54`; S4 `:29-30`; S7 `:12-15,60-65` |
| CP-08 | Human suspension releases indefinite custody and resumes only at same semantic target with current fence/epoch. | S4 | S4, S7 | Expiry/transfer/reclaim/cancel/duplicate-decision and cross-host resume | **Covered; program/version binding partial** | S4 `:23-33,43-50`; S7 `:67-68` |
| CP-09 | Crash/effect ambiguity/retry uses M11 intent/outcome/idempotency/reconciliation and never duplicates accepted effects. | S2 neutral; S5 cycle | S2, S5, S7 | Crash before/after intent/outcome, persistence failure, reconciliation | **Covered** | S2 `:25-34,51-53`; S5 `:40-41,59-63`; S7 `:16-19,65` |
| CP-10 | Projection deletion/rebuild/forgery/replay cannot increase authority. | S6/S7 | S6–S7 | Stale-cursor/forgery/deletion/rebuild/replay negative suite | **Covered** | S6 `:30-36,46-53`; S7 `:55-56,70` |
| CP-11 | Cross-host transfer/reclaim preserves all identities and increments epoch. | S2/S5/S7 | S2, S5, S7 | Neutral and product cross-host handoff traces | **Covered** | S2 `:32-34,51-53`; S5 `:33-41,59-65`; S7 `:68` |
| CP-12 | Exact-version WBC queries/evidence and installed-runtime version equivalence. | S1 pins; S6 queries; S7 row evidence | S1, S6, S7 | Wrong/missing version, installed/cloud and receipt provenance | **Partial—mid-run version drift unspecified** | S1 `:14-17`; S6 `:30-31,48-53`; S7 `:20-23,50-56` |
| CP-13 | One exact accepted Run Authority decision history corresponds to authored decisions and consumed transitions. | NS ownership only; partial S4/S5 delivery | S2–S7 | Decision/transition set equality, no orphan/duplicate/unaccepted decision | **Missing delivery/proof** | NS `:23-24`; S4 `:23,49`; S5 `:37`; S7 currently only actions `:12-15` |
| CP-14 | Final proof consumes pinned M11 proof and adds Native topology proof without substitution. | S7 | S7 | Full proof-map closure, validator receipt and completion manifest | **Partial—proof map not validator input** | S7 `:34-36,53-54,72-73`; chain runner `:974-983`; validator `:1093-1110` |

## Ranked gap register

| Rank | Severity | Confidence | Gap | Consequence | Exact smallest amendment |
|---:|---|---|---|---|---|
| 1 | **Critical** | Very high | `validate.proof_map` is required as a file and later added to completion evidence, but `_run_milestone_validations()` invokes the validator with only `--conformance`, `--traceability`, and `--repo-root`. The current validator has no `--proof-map` argument and validates the legacy evidence bundle of checker-shaped hashes/boundary fixtures. | S1–S6 can contribute arbitrary existing files; the current false-pass ledger can be made green without executing the North Star’s set equality, mutation, installed-runtime, RA/Custody/WBC, or negative-authority matrix. Evidence-as-authority or hidden carriers can survive a hard-blocking command. | In **S1 brief** add the proof-map/receipt schema and a known-old-false-pass rejection fixture. In **S7 brief** require the landed validator to consume the declared full proof map and reject missing, extra, unknown, stale, non-executed, non-commit-bound, or red receipts. In `chain/__init__.py`, pass `--proof-map <validation.proof_map>` and record/check its hash in the validation receipt before completion. No new YAML field is needed. |
| 2 | **High** | High | RA subject-attempt/fence mapping is explicit, but exact accepted-decision history is not. Only human actions (S4) and accepted batch/review/final results (S5) are explicitly bound to RA decisions; S7 proves authority-increasing actions, not every typed decision-to-transition occurrence. | Gate/tiebreaker/finalize/retry/cap/override route decisions may be persisted elsewhere, duplicated, or inferred from runtime state while still having valid grants/fences. The destination’s “one exact authority-decision history” is not proved. | Amend **S2 Required work**: every closed typed decision and terminal acceptance emits/links exactly one accepted RA Decision under its subject attempt/current fence, and the route transition consumes that decision. Amend **S7 set equality** to include authored decision occurrences ↔ accepted RA decisions ↔ consumed runtime transitions/actions, with orphan, duplicate, stale-fence and outcome-mismatch negatives. Add decision ID/outcome/CAS sequence to CP row evidence (`CP:364-375`). |
| 3 | **High** | High | Reentry identity names the semantic path and external identities but does not explicitly bind a run-level authored topology/call-site-policy digest or define behavior when source/policy/WBC contract version changes during suspension. | A cross-host or later resume can reach the same path under different model routing, retry/cap policy, topology, or WBC schema. All IDs may be syntactically valid while semantics changed. | Amend **S2** checkpoint/reentry contract to include immutable authored program/topology digest, call-site-policy digest, and exact WBC contract version. Amend **S4/S6**: resume must use the pinned version or enter an explicit typed migration/new-attempt/quarantine path; a config change is an authored effect creating the declared reentry semantics. Add **S7** source/policy/contract-drift negative scenarios. |
| 4 | **High delivery risk** | High | Historical M3 required a real lowered Megaplan builder slice before broad migration; revised S1/S2 prove checker and neutral machinery, while revised S3 bundles first `build_pipeline()` seam, the whole prep→revise front half, producer relocation, and deletion/quarantine. | S3 can become a big-bang integration sprint. If the builder seam is wrong, broad source work and deletion proceed without an independently green load-bearing product slice. | Keep seven sprints, but add an **ordered blocking sub-gate at the start of S3**: migrate one real edge (recommended prep→plan/clarification) through lowering, M11 action/WBC binding, checkout+installed execution, and old-carrier mutation. Broad critique/gate/revise migration and any deletion cannot begin until that receipt is green. This restores historical M3’s boundary without adding a sprint. |
| 5 | **Medium** | High | `add-note` and other non-routing annotations appear in RR and historical M8 but are absent from active S6’s exhaustive product list. | A surviving handler/CLI can still own an effectful control action, or the effect can disappear without deliberate narrowing proof. | Add to **S6 Product scope**: `add-note` and supported non-routing annotations as typed effect-only actions with exact target, WBC effect history, and an explicit “no route/reentry change” outcome. Add a mutation proving they cannot steer topology. |
| 6 | **Medium** | Very high | `prerequisite_policy` and `validation_policy` are parsed and displayed as required policies, but they do not themselves require a precondition or validator; explicit `launch_preconditions` and `milestone.validate` do the actual work. Nested milestone/driver mappings also do not reject every unknown key. | The YAML reads more enforceable than it is, and a later edit could retain the policy labels while deleting the actual enforcement entries. This epic currently has both, so there is no immediate bypass. | Amend **CP chain-schema limitation** to say these policy fields are operator/status metadata and that the explicit entries are the gates. Add a small chain-schema test (or loader invariant) that `required` implies at least one launch precondition / final validation. This is harness hardening, not Native topology scope. |

## Chain field, precondition, and validation semantics audit

The current `chain.yaml` parses successfully as seven milestones with one final validation. Unknown top-level keys fail, and every field used by this file is recognized. The table distinguishes parsing from actual blocking semantics.

| YAML field | Loader/validation | Runtime meaning | Finding / false-pass risk | Exact evidence |
|---|---|---|---|---|
| `base_branch: main` | Non-empty string | Base refresh/validation target | Supported and meaningful | chain `:1`; spec `:766-769`; runner `:1140-1158` |
| `anchors.north_star` | Only supported anchor key; non-empty path | Path checked and hashed into completion manifest | Sound | chain `:2-3`; spec `:302-320`; runner `:1245-1255` |
| `launch_preconditions[0].kind: chain_completed` | Only `artifact`, `chain_completed`, `git_tracked` accepted | Loads prerequisite spec/state; requires all current milestone labels done; checks spec path/hash and no active plan | Sound under locked M11 premise | chain `:5-9`; spec `:333-384,1947-2022` |
| `require_manifest: true` | Strict boolean | Validates schema, chain/NS/brief hashes, milestone order/status, proof artifact hashes, and final validation receipts | Strong content addressing, but proof semantics remain whatever upstream validator proved; accepted M11 premise supplies that | spec `:372-383,1724-1944` |
| Four `contains_text` artifact preconditions | `artifact` default; check mapping validated | Reads target and searches literal title | Existence/title only, intentionally anchors rather than proves content; initiative/plan separately clean-tracked | chain `:10-29`; spec `:407-473,2055-2091` |
| Two `git_tracked` preconditions | Requires path in HEAD and clean porcelain status | Blocks dirty/uncommitted initiative and corrective plan | Sound launch hygiene | chain `:30-35`; spec `:386-405,1422-1471` |
| `milestones[].label/idea` | Required strings; idea file checked | Creates serial milestone plans from active S briefs | Sound; historical m briefs are not referenced and cannot narrow work | chain `:37-100`; spec `:565-710,2094-2105` |
| `profile`, `robustness`, `depth` | Types checked; depth choice checked; profile/robustness are free strings | Passed to plan initialization and escalation bumps | Meaningful; profile validity is deferred downstream | spec `:607-620,5464-5495` |
| S5 `phase_model` | String/list of strings | Passed to plan initialization; execute/loop_execute pins become worker routing | Supported; loader does not fully decode syntax at parse time | chain `:73-75`; spec `:647-655`; runner `:5494` |
| `depends_on` | Labels must exist and be listed earlier | Topological assertion only; chain remains serial | Sound and accurately documented in code | chain `:49-50,57-58,65-66,76-77,84-85,92-93`; spec `:583-591,783-807` |
| `notes` | String | Prompt/context metadata | Not a gate; no plan claim relies on notes alone | spec `:659-661` |
| S7 `validate.kind` | Only `final_conformance_gate`; only final milestone may declare it | Validator subprocess is hard blocking | Sound blocking hook | chain `:94-100`; spec `:521-560,785-789`; runner `:934-1040,1126-1176` |
| `validator`, `conformance`, `traceability` | Required paths at validation time | Script invoked with conformance and traceability; exit 0 required; hashes written to receipt | Supported; current script validates old weak evidence unless S1/S7 replace it | runner `:953-1039`; validator `:19-38,103-110,963-1028` |
| `proof_map` | Required path at validation time and in receipt/completion manifest | File existence checked; receipt appended after validator; proof artifacts later hashed | **Not passed to validator; not semantically consumed by final command** | runner `:953-983,1021-1029,1043-1096`; validator args `:1093-1110` |
| `on_failure` / `on_escalate` | Mapping actions validated | Retry/profile bump/abort ladder | Supported | chain `:102-107`; spec `:260-289,820-827` |
| `merge_policy: auto` | Enum checked | Milestones land serially without per-sprint PR review | Supported; increases reliance on S7 proof | chain `:108`; spec `:829-845` |
| `prerequisite_policy: required` | Enum parsed | Written to plan/status metadata; status classifier can show awaiting approval | Does not create/strengthen preconditions; explicit entries do | chain `:109`; spec `:847-852`; status `:285-291` |
| `validation_policy: required` | Enum parsed | Written to plan/status metadata; status classifier can show quality gate | Does not create validators; explicit S7 `validate` does | chain `:110`; spec `:853-858`; status `:292-297` |
| `driver.auto_approve` | Coerced to bool | Plan agents auto-approve | Supported; per-sprint prose gates are not chain commands | chain `:111-116`; spec `:870-905` |
| `driver.max_iterations`, `poll_sleep`, `robustness`, `require_clean_base` | Numeric/string/bool parsing | Driver liveness, tier and base hygiene | Supported and meaningful | spec `:870-900` |

### Final-gate false-pass trace

1. S7 must create `final-proof-map.json`; its absence before S7 is expected.
2. Before advancing S7, the runner checks that validator, conformance, traceability, and proof-map files exist (`chain/__init__.py:953-967`).
3. It invokes the validator **without** the proof map (`:974-983`).
4. The current validator accepts `--conformance`, `--traceability`, and a default legacy evidence bundle only (`scripts/validate_native_representation_conformance.py:1093-1129`). Its implemented row proof remains matching file/checker hashes and old boundary record shapes (`:238-316,963-1081`), not the new four-domain/action/decision/set-equality contract.
5. If that command returns 0, the receipt is written. Only afterward does the runner append the receipt path to the proof map and use the proof map to build the completion manifest (`chain/__init__.py:1043-1096,1218-1332`). The manifest checks file existence and hashes, not the unconsumed artifacts’ semantics.

Therefore the hook is genuinely blocking, but it can block on the wrong predicate. This is the highest-ranked amendment.

## Sprint-by-sprint load, dependency, and deletion risk

| Sprint | Coherence and vertical result | Load | Dependency assessment | Deletion risk | Assessment / amendment |
|---|---|---|---|---|---|
| S1 | Immutable M11 admission + four-domain row model + old-pattern fail-closed checker/proof schema | **Very high** | Correct first step; no product migration should precede it | None | Viable as a busy infrastructure sprint if it emits one immutable admission-lock and proof-schema receipt. Add the final-proof-map/old-false-pass validator contract here. |
| S2 | Product-neutral decisions/loops/dynamic map/reducer/suspension/checkpoints bound to admitted M11 APIs, proven by neutral pipeline | **Very high platform work** | Correctly depends on S1 identity/API inventory; protects product work from special cases | None | Coherent. “Implement or finish” is acceptable at epic level; sprint planning must inventory existing primitives. Add RA-decision and program/version-bound reentry contracts. |
| S3 | Prep→revise load-bearing product slice + builder seam + WBC producer relocation + old-carrier quarantine/deletion | **Highest** | Correctly depends on S2; however historical M3’s product builder proof is no longer an independent boundary | **High inside sprint** | Keep sprint but require the one-edge prep→plan builder/adoption receipt before broad migration or any deletion. Producer relocation must precede handler/carrier removal. |
| S4 | Parallel tiebreaker, finalize and all named human decisions with durable reentry | High but cohesive | Correctly depends on ordinary front-half path so replan can rejoin it | Medium | Sound. Explicitly bind cursor to program/policy/WBC version and define drift quarantine/migration. |
| S5 | One reusable approval/execute/review/rework cycle with exact task/batch/item identities and effect recovery | **Very high** | Correctly depends on S4 finalize and S2 dynamic/runtime primitives | Medium-high | Cohesive despite load; splitting would duplicate cycle reasoning. Do not begin deletion until dynamic 0/1/N, crash and partial-resume gates pass. |
| S6 | Exhaustive controls/config/recovery/publication/delivery and auto/CLI/projection demotion | High | Correctly follows full delivery cycle; actions need real target/reentry destinations | High for alternate brains | Sound. Add effect-only `add-note`/annotations and ensure auto/CLI/status mutations are behaviorally inert before deletion. |
| S7 | Aggregate proof on M11 framework; remaining deletion only after rollback/negative gates | High only if proof was produced incrementally | Correct terminal aggregation | Correctly delayed | Architecturally sound. It becomes a dangerous implementation sprint if S1–S6 did not emit mandatory receipts. Harden final proof-map consumption and RA decision equality. |

The serial dependency chain is correct (`chain.yaml:49-50,57-58,65-66,76-77,84-85,92-93`). S4 needs S3’s ordinary rejoin path; S5 needs S4 finalize; S6 needs S5 targets; S7 needs all carriers demoted. There is no hidden ordering inversion. The key delivery problem is not the seven-sprint count itself; it is the missing internal builder seam before S3’s broad migration/deletion.

## Current-state migration feasibility and carrier ownership

The current tree confirms the plan is necessary and that its migration order is technically plausible, but it also identifies the exact seam S3 must prove.

| Current carrier/route brain | Current evidence | Planned disposition | Audit |
|---|---|---|---|
| `build_pipeline()` filters lowered nodes through `PIPELINE_STEP_COMPONENTS_BY_ID`, reconstructs component kind/policy/metadata, and overlays canonical metadata after lowered metadata. | `workflows/planning.py:237-296,643-721` | S3 makes it consume lowered structure; S7 set equality/deletion | Feasible only with explicit mixed/first-slice proof; this is Gap 4. |
| Runtime translates handler `next_step`, recommendation, verdict and route strings through component bindings/hard-coded maps; unknown gate output defaults to finalize. | `runtime/manifest_backend.py:146-189,227-322` | S3–S6 delete/hard-fence route ownership; S7 hidden-authority mutation | Correctly in scope. Calling it a projection without deleting its decision translation would fail S7. |
| Generic router materializes fanout only when static `width` is non-`None`; current dynamic lowering can therefore disappear at this seam. | `arnold/execution/routing.py:59-63,383-420` | S2 implements/finishes runtime-sized map; S3/S5 product adoption | S2 neutral 0/1/N gate is the right prerequisite. |
| Auto’s “native” phase path consumes a compiled shell/native program and retains an explicit compatibility fallback. | `auto.py:640-667,670-727,730-755` | S6 reduces auto to event/request consumer; S7 compatibility deletion/mutation | Feasible as a strangler only if the fallback is expiry-bound and behaviorally inert for corrected paths. |
| Current final conformance validator checks legacy row/hash/boundary evidence and currently fails only five stale/coherence records when run. | validator `:19-38,103-110,963-1089`; direct audit run | S1 redesigns proof schema; S7 final replay | Current failure is not proof of semantic strength; the revised validator must reject the old false-pass even when hashes are refreshed. |

The plan’s producer order is sound: S2 binds generic runtime boundaries; S3/S4/S5 move WBC producers to lowered nodes/children while each product slice becomes load-bearing; only then do those sprints quarantine/delete their corresponding handler/component routes; S6 demotes global auto/CLI/projection consumers; S7 deletes residues after rollback/negative proof (`S3:29-36`; `S4:29-33`; `S5:40-44`; `S6:26-36`; `S7:31-33`). No big-bang gap is required if the S3 internal seam is restored.

## Concrete text-level amendment set

These changes target the smallest authoritative assets. They do not add Custody implementation to Native Parity.

### 1. S1 brief — proof-map and accepted-decision schema

Add after `s1-checker-outcomes-builder-slice.md:38-40`:

> Define a mandatory per-sprint validation-receipt registry in `final-proof-map.json`. Each receipt binds command/tool version, exit status, audited commit/tree, installed artifact, exact M11 admission-lock digest, semantic/identity sets, runtime trace, and all blocking subchecks. The final validator must consume the complete map, reject missing/extra/unknown/unconsumed/red records, and fail on the retained old self-declared/hash-only false-pass fixture.
>
> Extend each row with the accepted Run Authority decision ID/outcome/CAS sequence where the construct produces or consumes a typed product decision; subject attempt/fence alone is insufficient.

### 2. S2 brief — decision history and version-bound reentry

Add after `s2-front-half-native-loop.md:27-31`:

> Every closed typed decision and terminal acceptance creates or links exactly one accepted Run Authority Decision under the current subject attempt/fence; the runtime transition must consume that exact decision. No handler/status/projection may independently persist or infer the accepted route.
>
> Every checkpoint/reentry envelope binds the authored program/topology digest, call-site-policy digest, and exact WBC boundary-contract version. Resume under drift must use the pinned original or enter an explicit typed migration/new-attempt/quarantine path; silently recompiling the same semantic path under changed policy is forbidden.

### 3. S3 brief — restore the product builder stop/go boundary

Add before broad Product scope work:

> Ordered prerequisite inside S3: first migrate one real canonical Megaplan edge (prep→plan including clarification reentry) through source lowering, runtime, M11 action validation, relocated WBC producer identity, checkout execution, and clean installed-package execution. Mutating the source must change the trace; mutating the old carrier must not. No remaining front-half migration or carrier deletion/quarantine begins until this receipt is green.

### 4. S4/S6 briefs — drift and effect-only control actions

Add to S4 adoption gate:

> Source/program digest, call-site policy, or WBC contract-version drift during suspension cannot silently resume. The path must use the pinned version or an accepted typed migration/new-attempt/quarantine decision, with new subject/WBC attempt and current custody epoch as applicable.

Add to S6 Product scope:

> `add-note` and supported non-routing annotations are typed effect-only actions: exact target, current required authority/custody, durable WBC effect history, and an explicit no-route-change outcome.

### 5. S7 brief/plan — exact final equality and proof-map execution

Expand `s7-final-conformance-rollout.md:12-15`:

> Generate exact set equality across authored typed decision occurrences, accepted Run Authority decisions, and consumed runtime transitions/actions, in addition to node/child/producer/checkpoint/projection sets. Reject orphan, duplicate, stale-fence, unaccepted, or outcome-mismatched decisions.

Add after `:34-36`:

> The chain validator must receive and consume the declared `final-proof-map.json`; a green conformance/traceability ledger without complete proof-map closure is a blocking failure. The validation receipt binds the proof-map hash before its own receipt is appended. The retained old current-tree ledger/evidence bundle is a mandatory negative fixture and must fail even when all path/hash records are refreshed.

Update CP’s chain-schema limitation (`CP:473-489`) to state that `prerequisite_policy`/`validation_policy` are metadata and that explicit `launch_preconditions`/`validate` entries carry enforcement. Add the existing proof-map argument plumbing to the S1/S7 harness work; no generic arbitrary per-milestone command feature is required.

## Important areas already sound

- **Ownership is precise.** The action rule is conjunctive; WBC can make a boundary incomplete/indeterminate but cannot grant action; leases confer responsibility, not permission (`NS:19-45`).
- **The four identity domains are not collapsed.** The plan explicitly rejects generic `attempt_id`, requires cardinality/causality, and carries three external joins from the semantic coordinate (`NS:47-58`; S1 `:24-29`; CP `:113-130`).
- **Custody scope is not duplicated.** M11 stores, queries, action validator, lease/recovery, outbox/reconciliation, projections and generic fixtures are reuse-only; Native Parity owns topology-specific binding and producer relocation (`NS:75-87`; CP `:160-179`; S1 `:21-23`).
- **Current incomplete cloud publication is correctly excluded.** README and S1 reject M8/M9/shadow/status/autopublish evidence, while the locked premise supplies accepted M11 (`README:8-15`; S1 `:12-20,62-65`).
- **Semantic compression is justified.** Parsing, normalization, lens selection, merging and serialization may stay in pure bodies, while routes, loops, retry/cap/model policy, effects, checkpoint identity and terminal outcomes remain authored/typed (`NS:60-73`; CP `:132-158`).
- **Dynamic work is explicit enough.** S2 covers runtime collections, schema, cap, reducer, cancellation/orphans, retry/fallback and child paths; S5 supplies task/batch/item identity and exact-target custody (`S2:12-21`; S5:17-36).
- **Producer relocation precedes deletion in the intended sequence.** S3–S5 state relocation/binding before corresponding delete/fence clauses; S7 reserves final deletion until negative/rollback gates pass.
- **Suspension semantics are not marker-based.** S4 requires accepted RA human decisions, current fence, reacquired/validated exact lease/epoch, no indefinite lease, and stale marker/receipt rejection (`S4:23-33,43-50`).
- **Effect/recovery responsibilities remain in M11.** S5 explicitly reuses intent/outcome, ambiguity, idempotency, persistence, reconciliation, queries and recovery rather than recreating them (`S5:40-41,57-65`).
- **Projection non-authority is unusually strong.** S6 and S7 require forgery, stale cursor, deletion, rebuild and replay negatives, including internally consistent forged views (`S6:30-36,46-53`; S7:55-56,70`).
- **Installed/runtime equivalence is a first-class closeout condition.** Checkout, wheel/sdist and pinned cloud must agree on topology, decisions, WBC history and identity joins (`NS:100-105`; S7:5-8,29-30,71`).
- **Historical m1–m10 files are correctly demoted.** Every old domain has an active sprint home; README explicitly makes them non-authoritative appendices (`README:38-49`). The only meaningful compression loss is the independent builder seam and the omitted effect-only override item, not a lost phase domain.

## Final position

The revised epic is architecturally credible and substantially meets the requested destination. It should not be expanded into a second Custody/control-plane epic, nor split back into ten historical milestones by default. Apply the bounded amendments, especially the proof-map execution and RA decision-history equality. Then a successful chain can mean the desired composed fact rather than a refreshed version of the previous false-pass:

> One authored semantic topology; one exact authority-decision history; one current exclusive custody owner; one durable boundary/effect history; any number of disposable projections.

Without those amendments, the answer to the final adversarial question remains **yes**: the epic can report success while proving only that a mutable validator accepted a legacy ledger and that proof-map files existed, not that hidden semantic authority, stale reentry authority, or evidence-as-authority was impossible.
