# Native Megaplan Build-Forward Documentation Map

## 1. Documentation decision

Do not rewrite the 173KB representation report. Preserve it as architectural evidence and add a dated amendment that points to current execution authorities. The report itself says its older milestone totals are superseded by the 2026-07-30 sequence and must not be used to rewrite chain sources (`docs/arnold/megaplan-native-representation-report.md:3-9`). Its three-snapshot model remains correct: current split authority, Post-Native-Parity `.pype` source authority, and Post-Platformization qualified reusable components (`docs/arnold/megaplan-native-representation-report.md:135-141`).

The first amendment must not describe Custody M11 as settled. A later audit invalidates the prior completion/promotion claim and requires superseding Run Authority quarantine plus fresh zero-blocker acceptance evidence (`.megaplan/audits/critique-ledger-incident-sol-review-20260802.md:70-78`); the post-M11 release evidence remains explicitly in progress (`docs/megaplan/post-m11-release-evidence-20260731.md:3-12`, `124-141`). Documentation must distinguish claimed historical completion, invalidation, corrective re-acceptance, and the eventual content-addressed completion manifest.

The documentation set needs four different classes with explicit owners:

1. **Normative architecture/contract** — durable destination and invariants.
2. **Executable initiative source** — chain, briefs, transition handlers, validators and proof-map schemas.
3. **Current-state/build-forward guidance** — dated audits and sequencing amendments.
4. **Generated evidence/projections** — immutable proof manifests, receipts, inventories and rendered reports.

Generated evidence must never become editable product truth. The report assigns product semantics to source, runtime/replay coordinates to generated manifests, and observation to rebuildable projections (`docs/arnold/megaplan-native-representation-report.md:143-178`, `180-193`).

## 2. Authority map

| Artifact | Classification | Current role | Action | Owner |
|---|---|---|---|---|
| `docs/arnold/megaplan-native-representation-report.md` | Normative architecture + historical evidence | Defines end-state, contract separation, gap analysis and two-stage destination; execution counts are amended (`:3-9`, `:135-193`, `:2299-2462`). | **Amend, do not rewrite.** Add a short dated “2026-08-24 build-forward amendment” linking this plan, MRC intake/crosswalk, `.pype` authority and active initiative sources. | Native architecture owner; operator approves load-bearing changes. |
| `docs/arnold/megaplan-native-representation-alignment-plan.md` | Normative enforcement ledger | Defines doctrine precedence, 31 row statuses, false-pass tests, H0–H9 and D1–D15 (`:38-73`, `:99-154`, `:156-196`). | **Amend in place after approval.** Change target suffix/path doctrine from `.pypeline` to `.pype`; point owning milestones to corrective S1–S7 and Platform S1–S6; preserve old status/history in a changelog section. | Native conformance owner. |
| `docs/arnold/pype-authoring-contract.md` | Normative authoring contract | Adopted shared Native/Platform contract and ownership schedule (`:1-20`); defines layers, exact-one file rule, imports/composition and leaf law (`:26-67`, `:69-105`, `:128-213`). | **Keep authoritative.** Update only through explicit decision records and versioned compatibility changes. | Native S1/S2F/S2R until GO-FORMAT; Platform S2B/S3/S6 after handoff. |
| `.megaplan/initiatives/megaplan-native-parity-corrective/NORTHSTAR.md` | Normative Stage-1 destination | Governs the twelve-milestone corrective chain. | **Keep authoritative; amend only for accepted operator decisions.** Add MRC crosswalk/evidence standard references, not MRC product semantics. | Native Parity epic owner. |
| `.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml` | Executable Stage-1 sequence | Enforces Custody/bootstrap prerequisites and S1–S7 gates/transitions (`:5-19`, `:52-217`). | **Keep executable authority.** Add only exact new artifact prerequisites produced by approved brief amendments. | Native Parity chain owner. |
| `.megaplan/initiatives/native-workflow-platformization/NORTHSTAR.md` and `decisions/PLATFORM_CONTRACT.md` | Normative Stage-2 destination/contract | Governs post-parity component standard. README says prepared/not launched and requires exact handoff (`README.md:1-43`). | **Keep authoritative.** Add MRC-derived evidence/canary conventions only where product-neutral. | Platformization epic owner. |
| `.megaplan/initiatives/native-workflow-platformization/chain.yaml` | Executable Stage-2 sequence | Prepared seven-milestone chain; absent proof map/completion manifest is intentional (`README.md:63-105`, `115-149`). | **Do not launch or generate terminal evidence before Native S7 handoff.** | Platformization chain owner. |
| `docs/arnold/maintenance-runtime-consolidation-execution-plan-2026-08-20.md` | Normative MRC execution record | Defines MRC selection, evidence, migration, canary and closure discipline (`:740-809`, `:827-841`). | **Freeze as MRC provenance.** Native references patterns through a crosswalk rather than editing this plan. | MRC owner. |
| `docs/arnold/maintenance-runtime-consolidation-execution-log-2026-08-20.md` | Immutable operational evidence narrative | Records halts, adjudications, canary completion and deviations (`:492-527`, `:546-553`). | **Append-only/frozen per MRC policy.** Do not normalize its exceptions into Native acceptance. | MRC evidence custodian. |
| `docs/arnold/maintenance-runtime-consolidation-evidence/manifest.json` + validator | Generated evidence contract | Binds tasks/gates/receipts/shards/allowances/candidates/canary/broad suite; semantic validator checks references/digests/routing/review/allowances (`scripts/validate_maintenance_runtime_consolidation_evidence.py:174-245`, `247-358`, `387-433`). | **Reuse schema patterns, not the manifest itself.** Create Native-specific schemas and validators. | MRC evidence custodian; Native S1 consumes read-only. |
| `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md` | Dated current-state/build plan | Audits current code, applies MRC deltas, and orders prerequisites/Native/Platform milestones. | **New; authoritative for 2026-08-24 build-forward interpretation.** Supersede with a later dated plan, never silently rewrite historical claims. | Lead architect; operator resolves open questions. |
| This file | Documentation governance map | Defines document ownership, update triggers and TOCs. | **New.** Update only when authority classes or deliverables change. | Documentation/conformance owner. |

## 3. New documents to create

### D1. `docs/arnold/megaplan-native-representation-amendment-2026-08-24.md`

**Why new instead of editing the report deeply:** the report is architectural evidence and explicitly preserves superseded counts (`docs/arnold/megaplan-native-representation-report.md:3-9`). A short amendment prevents a second 100KB fork.

**Owner:** Native architecture owner. **Approver:** operator.

**Suggested TOC:**

1. Status and effective date.
2. Documents amended and precedence.
3. What remains unchanged: three snapshots, source/manifest/authority/projection separation.
4. Sequencing now in force: M11 → bootstrap → twelve Native milestones → seven Platform milestones.
5. Authoring change: `.pypeline` baseline → `.pype` adopted target.
6. MRC intake: reusable mechanisms, non-substitution for M11.
7. Current implementation snapshot.
8. Active initiative and validator links.
9. Superseded passages/claims table.
10. Operator decisions and effective receipts.

**Update trigger:** accepted operator disposition on MRC↔M11, completion of prerequisite manifests, or any change to the active chain.

### D2. `.megaplan/initiatives/megaplan-native-parity-corrective/research/mrc-to-m11-native-crosswalk.md`

**Owner:** Native S1 evidence lead with Custody M11 owner sign-off.

**Suggested TOC:**

1. Frozen MRC source/evidence identities.
2. Accepted M11 source/evidence identities.
3. Contract-by-contract table: claim/CAS, RA grant/decision, Custody lease/epoch, WBC attempt/effect, repair, query/projection, migration, adoption/rebind, cutover/rollback, canary, validator.
4. Disposition: identical accepted API / M11 adapter / pattern-only / missing.
5. Negative authority tests.
6. Missing prerequisites and owner.
7. S1 admission conclusion.

**Update trigger:** MRC superseding receipt, M11 version change, or Native S1 probe result.

### D3. `.megaplan/initiatives/megaplan-native-parity-corrective/decisions/EVIDENCE_PACK_CONTRACT.md`

**Owner:** Native conformance owner. **Inputs:** MRC manifest/validator and milestone-gate bootstrap.

**Suggested TOC:**

1. Schema/version/identity.
2. Immutable inputs and source SHA.
3. Inventory and ownership rows.
4. Invocation receipts and process identity.
5. Focused tests and elapsed-budget v2.
6. Static source/carrier scans and mutation corpus.
7. Runtime traces/decisions/effects/checkpoints.
8. Candidate install/runtime/decoder/lowerer provenance.
9. Readiness/transition/post-transition receipts.
10. Canary snapshot/restore/rollback census.
11. Allowance and bounded-exception registry.
12. Review/revision/re-review/supersession.
13. Validator issue codes and stable ordering.
14. Required negative controls.
15. Completion and handoff binding.

**Update trigger:** S1 freeze; later changes require versioned schema migration, never in-place reinterpretation.

### D4. `docs/arnold/megaplan-native-current-state-2026-08-24.md`

**Owner:** Native S1 inventory lead.

**Purpose:** a concise, generated-from-evidence snapshot that replaces stale prose as the launch baseline without replacing the report.

**Suggested TOC:**

1. Frozen HEAD/runtime identities.
2. Canonical source and suffix inventory.
3. D1–D15 carrier inventory.
4. Handler purity table.
5. Compiler/runtime primitive inventory.
6. Package/checkout/wheel/cloud surface inventory.
7. M11/bootstrap prerequisite state.
8. Matrix row status snapshot.
9. Known unknowns and exact measurement commands.
10. Manifest/proof-map digest.

**Update trigger:** Native S1 only. Later milestones generate deltas rather than rewriting the baseline.

### D5. `.megaplan/initiatives/megaplan-native-parity-corrective/decisions/ALLOWANCE_AND_EXCEPTION_POLICY.md`

**Owner:** Native conformance owner; operator owns exception principal.

**Suggested TOC:**

1. Definitions: allowance, waiver, historical exception, environmental deviation, supersession.
2. Allowed classes and categorization.
3. Non-waivable musts.
4. Required identity/digest/evidence/judge fields.
5. Taint and prohibited inferences.
6. Scope overlap rules.
7. Expiry/removal milestone and retest triggers.
8. Superseding receipt chain.
9. Validator rules and negative fixtures.
10. Operator approval procedure.

**Update trigger:** before S1 launch; any new class requires operator-approved version bump.

### D6. `.megaplan/initiatives/megaplan-native-parity-corrective/decisions/CANARY_AND_ROLLBACK_CONTRACT.md`

**Owner:** Native runtime/cutover owner.

**Suggested TOC:**

1. Canary threat model.
2. Production transition under test.
3. Disposable root/origin/environment containment.
4. Selected-state tuple derived from write inventory.
5. Immutable baseline and immediate pre/post/rollback snapshots.
6. External supervision, PGID/start identity and restart recovery.
7. Crash injection points.
8. Protected-state claims and limitations.
9. Pointer/binding rollback; no history rewrite.
10. Candidate provenance and dual-candidate isolation.
11. Stop conditions.
12. Receipt schema and post-transition verifier.

**Update trigger:** S1 contract freeze; each authority-changing milestone instantiates it with a milestone-specific card.

### D7. `docs/arnold/native-parity-operator-runbook.md`

**Owner:** Native operations owner. **Approver:** operator.

**Suggested TOC:**

1. Preconditions and launch refusal reasons.
2. How to verify Custody/bootstrap manifests.
3. How to inspect stage evidence packs.
4. Transition approval principals and commands.
5. Canary launch/observe/stop/restore.
6. Rollback and supersession.
7. Bounded exception escalation.
8. Stale/superseded receipt handling.
9. Incident containment and evidence preservation.
10. GO-0/1A/1B/2/3/4 checklist.

**Update trigger:** before the first authority-changing transition, not at S7 closeout.

### D8. `docs/arnold/native-parity-developer-guide.md`

**Owner:** Native S2F authoring owner; Platform S3 later extends it.

**Suggested TOC:**

1. `.pype` mental model.
2. One workflow per file.
3. Static imports and private/shared boundaries.
4. Typed route discriminants.
5. Bounded loops and named exits.
6. Dynamic map/reducer and deterministic keys.
7. Child workflow calls and path identity.
8. Steps/effects/policies and leaf law.
9. Suspension/reentry/checkpoints.
10. Diagnostics, preview and local harness.
11. Converter/refactor workflow.
12. Anti-patterns: handler refs, route tables, hidden state, ambient authority.

**Update trigger:** GO-FORMAT; Platform S2B/S3 may version/extend, not independently refreeze it.

### D9. `.megaplan/initiatives/megaplan-native-parity-corrective/research/SEMANTICS_CARRIER_LEDGER.md`

**Owner:** Native D15/handler-extraction reviewer.

**Suggested TOC/table columns:**

- Report/matrix requirement.
- Current carrier(s).
- Current authority status.
- Target source/policy/pure-body carrier.
- Owning milestone.
- Cutover receipt.
- Legacy seam and expiry.
- Static invariant.
- False-pass mutation.
- Final evidence path.

**Update trigger:** every Native milestone; S7 closes with zero route-capable legacy seams. The requirement follows the report's hidden-logic inventory and the alignment plan's H6/D15 review (`docs/arnold/megaplan-native-representation-report.md:500-529`; `docs/arnold/megaplan-native-representation-alignment-plan.md:170-171`, `195-196`).

### D10. `.megaplan/initiatives/megaplan-native-parity-corrective/research/EFFECT_PROTOCOL_CLASS_INVENTORY.md`

**Owner:** Native S5A effect/reconciliation owner.

**Suggested TOC/table columns:**

- Effect class and all call sites.
- Intent/idempotency identity.
- Required RA/Custody/WBC envelope.
- Outcome/ambiguity model.
- Adoption/reconcile/compensation path.
- Shadow proof/equivalence judgment.
- Crash injection points.
- Live writer and old-writer fence.
- GO-2 evidence.
- S5B post-cutover receipt.

**Update trigger:** S5A; any new effect after GO-2 reopens the gate.

### D11. `.megaplan/initiatives/megaplan-native-parity-corrective/platformization-handoff-manifest.md` plus machine JSON

**Owner:** Native S7; consumed by Platform S1.

**Suggested sections/fields:**

1. Native completion manifest/proof-map identity.
2. Candidate classification inventory.
3. Typed port/outcome/state/policy/effect/capability snapshots.
4. Source/runtime golden adapters.
5. Zero-Megaplan-import proof for generic primitives.
6. Coupling/exclusion evidence.
7. C1/C2/S2R completion-kernel identities.
8. `.pype` sole-live-suffix proof.
9. DX/diagnostic/local-harness corpus and baselines.
10. CAS/transition/adapter provenance.
11. Outstanding experimental candidates and owners.

The Platform initiative already requires this exact class of handoff and rejects existence-only proof (`.megaplan/initiatives/native-workflow-platformization/README.md:10-43`).

### D12. Platformization documentation set

**Owner:** Platform S1–S6 according to the prepared chain.

Create/version these after Native S7 only:

- `docs/arnold/workflow-component-standard.md` — descriptor/lifecycle/composition contract.
- `docs/arnold/workflow-component-compatibility.md` — resolution, graph lock, version/evolution/substitution/resume.
- `docs/arnold/workflow-component-authoring.md` — shared authoring/package core extending `.pype`.
- `docs/arnold/workflow-component-testing.md` — deterministic harness, fault/recomposition/isolation matrix.
- `docs/arnold/workflow-component-certification.md` — capability profiles, evidence manifest and publication rules.
- `docs/arnold/workflow-component-operations.md` — install, inspect, upgrade, rollback and incident response.

Each document must report source reuse, clean-wheel reuse, deterministic resolution, shape-independent reuse, new-instance substitutability and resume compatibility separately (`docs/arnold/megaplan-native-representation-report.md:2283-2297`).

## 4. Existing documents to amend

### A1. Representation report: small pointer amendment only

Add at the top, after the 2026-07-30 amendment:

- 2026-08-24 status.
- Link to build-forward plan and documentation map.
- `.pype` adopted target superseding `.pypeline` references.
- MRC completed as pattern/input, not M11 substitute.
- Current prerequisite state.
- Active chain paths.

Do not rewrite old line citations, milestone tables or evidence narrative; identify superseded passages in the new amendment document.

### A2. Alignment plan: versioned row migration

Required changes:

- Replace target `workflow.pypeline` with `workflow.pype` and named child files.
- Preserve a “pre-corrective baseline” column or appendix.
- Remap `Completion M* / Composition M* / Platform M*` ownership to corrective S1/S2F/C1/C2/S2R/S3A/S3B/S4/S5A/S5B/S6/S7 and Platform S1/S2A/S2B/S3/S4/S5/S6.
- Add MRC reuse/anti-reuse and evidence-pack fields.
- Add allowance/exception owner and expiry fields.
- Add transition/canary/post-verification evidence fields.
- Keep all 31 requirements and H0–H9/D1–D15; do not collapse them (`docs/arnold/megaplan-native-representation-alignment-plan.md:122-196`).

### A3. Corrective milestone briefs

Add a uniform section to every active brief:

```text
## MRC Pattern Reuse
- reused mechanisms
- adapted schemas
- explicitly excluded maintenance semantics

## Evidence Pack
- manifest/schema/validator
- source and inventory identities
- focused tests + elapsed budget
- mutation/negative corpus
- readiness/transition/post-transition receipts
- canary/rollback evidence
- allowance/exception rows
- review/supersession chain

## Native Representation Alignment
- matrix rows and D/H waves
- status change
- false-pass tests
- deferrals and owner
```

The alignment plan already requires a Native Representation Alignment section and row status/proof/false-pass ownership (`docs/arnold/megaplan-native-representation-alignment-plan.md:198-204`).

### A4. Platformization briefs

Add the same evidence/canary/supersession skeleton, but prohibit:

- redefinition of `.pype` grammar;
- duplicate M11 stores or completion kernel;
- Megaplan reverse imports;
- certification before S5's unrelated consumer;
- combined verdicts that hide the six distinct reuse claims.

The prepared README assigns exact S1–S6 roles and makes S6 the only stable publication point (`.megaplan/initiatives/native-workflow-platformization/README.md:115-141`).

### A5. Workflow authoring/runtime/manifest docs

Update after GO-FORMAT/GO-0, not before:

- `docs/arnold/workflow-authoring.md` — `.pype` canonical usage and preview boundary.
- `docs/arnold/workflow-runtime.md` — admitted manifest/decoder/lowerer/runtime identity and action envelope.
- `docs/arnold/workflow-manifest.md` — retain manifest-as-generated-runtime doctrine; add versioned `.pype` lowering provenance without making manifest editable truth (`docs/arnold/workflow-manifest.md:1-12`, `46-48`, `103-167`).
- `docs/arnold/workflow-migration.md` — `.pypeline` pinned-reader retention, converter identity map, suspended-run migration/quarantine and rollback.
- `docs/arnold/workflow-boundary-contracts.md` — exact RA/Custody/WBC/effect/transition receipt joins.

**Owners:** S2F for authoring/migration, S2R for runtime/manifest/boundaries, S7 for final conformance consistency.

### A6. Operations/security/tooling docs

Update at the milestone that changes behavior:

- security: capability minting/narrowing, no ambient authority, credentials/effects, transition principals;
- operations: readiness/transition/post-verification, canary/rollback, superseded receipts;
- tooling: OMP-backed launcher, requested/resolved model provenance, process-group containment, elapsed budgets;
- state authority migration: no status/liveness/projection route authority, guarded adoption/rebind and immutable resume binding.

MRC demonstrates the required mechanism separation: `MutationCapability` is mint-only/narrow-only (`arnold_pipelines/megaplan/cloud/current_target_liveness.py:408-481`), while its invocation wrapper records resolved model and process/output digests (`scripts/run_maintenance_consolidation_agent.py:399-445`, `477-532`).

## 5. Documents to freeze or mark historical

| Document/artifact class | Disposition | Reason |
|---|---|---|
| Old Native completion/composition/platform completion manifests | Freeze as predecessor evidence. | They prove earlier chains, not corrective Native Parity (`.megaplan/initiatives/native-python-pipelines-completion/completion-manifest.json:7-120`; `.megaplan/initiatives/native-composition-followup/completion-manifest.json:7-103`; `.megaplan/initiatives/native-platform-followup/completion-manifest.json:7-118`). |
| `megaplan-native-representation-conformance-report.md`, its conformance YAML, and generated evidence bundle | Mark **historical false-pass evidence** with a prominent banner; never overwrite or cite as current closure. | The report claims 31 implemented rows (`docs/arnold/megaplan-native-representation-conformance-report.md:8-17`), but the later strict audit records nine `AWF245_ROW_EVIDENCE_INSUFFICIENCY` failures and explicitly calls the report false (`docs/arnold/megaplan-native-semantic-parity-master-plan.md:183-210`). S7 creates the corrective conformance/traceability/validator set (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:140-145`). |
| MRC execution plan/log/evidence | Freeze under MRC custody; reference by digest. | Native consumes patterns and accepted receipts, not editable copies. |
| Older `briefs/m*.md` under corrective initiative | Mark historical pre-custody appendices. | Corrective README says active launch contracts are `s1-*` through `s7-*` and old briefs cannot narrow them (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:112-117`, `238-239`). |
| `python-shaped-authoring-contract.md` | Mark implemented migration baseline, not target authority. | `.pype` contract names it as current implemented baseline and assigns target implementation to S1/S2F/S2R (`docs/arnold/pype-authoring-contract.md:3-15`). |
| `workflow-manifest.md` | Keep runtime contract, explicitly not authoring end-state. | Manifest is neutral generated data and compiler output (`docs/arnold/workflow-manifest.md:1-12`, `46-48`). |

## 6. Generated documentation and evidence rules

Generated artifacts require headers/fields that state:

- schema and schema version;
- authoritative or observational classification;
- producer and owning milestone;
- immutable input identities;
- generated-at timestamp only where semantically required;
- canonical content digest;
- supersedes/superseded-by chain;
- validator and validator digest;
- whether the artifact can authorize any transition (default `false`);
- retention and expiry/removal owner.

Never hand-edit generated manifests, proof maps, receipts, inventories or rendered topology. Correct the source/producer and regenerate with a new content digest; preserve the superseded artifact. This follows the report's source→lowering→manifest one-way model (`docs/arnold/megaplan-native-representation-report.md:148-169`) and MRC's digest/cross-reference validation practice (`scripts/validate_maintenance_runtime_consolidation_evidence.py:145-159`, `174-245`).

## 7. Documentation gates by milestone

| Gate | Required documentation closure |
|---|---|
| P0 | MRC→M11→Native crosswalk; build-forward amendment approved. |
| P1 | Custody M11 completion manifest/proof map/bounded-projection handoff/runbook links. |
| P2 | Milestone-gate bootstrap contract, transition receipt schema, downstream readiness docs. |
| S1 | Current-state baseline, evidence-pack contract, allowance/exception policy, carrier ledger initialized. |
| GO-FORMAT | `.pype` developer guide, compiler/linker/converter/identity docs, `.pypeline` retention/migration doc. |
| GO-0 | Runtime/admission/action-envelope, checkpoint/effect/decoder compatibility docs. |
| GO-1A/B | Prep/plan/critique/gate/revise source maps, handler-purity ledger updates, operator transition records. |
| S4 | Tiebreaker/finalize/human suspension/reentry docs. |
| GO-2 | Complete effect protocol class inventory and shadow proof report. |
| S5B | Live delivery cutover/rollback/reconciliation runbook and post-transition report. |
| GO-3 | Override/recovery/auto-drive policy and read-only projection docs. |
| GO-4 | Corrective conformance report, completion manifest, closed carrier/allowance ledgers, Platformization handoff. |
| Platform S1 | Component standard draft and classification inventory. |
| Platform S2A/B | Runtime/admission and authoring/package core docs. |
| Platform S3 | Public DX/tooling/local-harness docs and usability report. |
| Platform S4 | Extraction/recomposition/isolation report. |
| Platform S5 | Unrelated-consumer and six-claim substitutability/resume report. |
| Platform S6 | Stable certification, compatibility/evolution, operations and publication docs. |

## 8. Documentation review checklist

A document is acceptable only if:

1. its authority class is explicit;
2. it points to the controlling source rather than duplicating it;
3. every current-state assertion cites current file/line or a digest-bound evidence row;
4. historical evidence is not silently rewritten;
5. `.pype`, `.pypeline`, manifest, handler, runtime, RA, Custody, WBC, checkpoint/effect and projection roles are not conflated;
6. completion, conformance, publication and operational readiness are separate verdicts;
7. every deferral names an owner, blocking gate and proof trigger;
8. every exception names taint, prohibited inferences, expiry/retest and supersession;
9. every authority transition points to readiness, transition and independent post-transition receipts;
10. every reusable-component claim reports all six reuse dimensions independently (`docs/arnold/megaplan-native-representation-report.md:2283-2297`).

## 9. Immediate documentation work order

1. Approve and land this map plus the dated build-forward plan.
2. Author the short representation-report amendment.
3. Create the MRC→M11→Native crosswalk before changing S1 scope.
4. Create/version the Native evidence-pack, allowance/exception and canary/rollback contracts.
5. Amend the alignment ledger and all active corrective briefs to `.pype`, corrective milestone ownership and MRC evidence discipline.
6. Do not update general authoring/runtime/operations docs until the corresponding GO gate changes the admitted behavior.
7. Generate, never hand-author, milestone proof maps/receipts/conformance reports from the frozen contracts.
