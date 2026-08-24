# Native Megaplan Plan Reconciliation — 2026-08-24

## 1. Verdict

Execute a **hybrid of Plan B and the already-amended Plan A**, with one material correction to Plan B's Custody wording.

The two plans do **not** define competing post-Custody implementations. Plan A's 2026-07-30 sequencing amendment already supersedes its older milestone totals and names the same executable spine as Plan B: accepted Custody M11, milestone-gate bootstrap, twelve Native Parity milestones with C1/C2 between S2F and S2R, then seven Platformization milestones (`docs/arnold/megaplan-native-representation-report.md:3-9`; `docs/arnold/DEPRECATED-completion-spec-sequencing-and-ownership.md:5-32`). Plan B mostly restates that spine with current-state evidence, MRC-derived proof discipline, owners, and acceptance detail.

The hybrid's controlling sequence is:

```text
P0  MRC closeout intake and MRC→M11→Native crosswalk (read-only; no authority change)
P1  Custody M11 admission resolution:
      locate/import and validate any canonical superseding Run Authority decision,
      accepted completion manifest, proof map, bounded-projection handoff, and
      production-vector acceptance; if they do not exist, Custody—not Native—
      performs the corrective work required to produce them
P2  milestone-gate bootstrap and its three readiness artifacts

Native S1 -> S2F -> C1 -> C2 -> S2R -> S3A -> S3B -> S4 -> S5A -> S5B -> S6 -> S7

Platform S1 -> S2A -> S2B -> S3 -> S4 -> S5 -> S6
```

This is the 22-position Plan B sequence, but P1 is an **admission/result gate**, not an unsupported instruction to rerun all nine Custody milestones. The exact corrective path depends on canonical Custody/Run Authority evidence that is not present in this checkout.

Authority after this adjudication:

1. `docs/arnold/megaplan-native-representation-report.md` remains authoritative for architecture, contract separation, and the two-stage destination.
2. The active `chain.yaml`, North Star, milestone briefs, validators, transition handlers, proof maps, and accepted receipts remain executable authority.
3. This reconciliation is the controlling dated adjudication of conflicts between Plan A and Plan B.
4. `docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md` is the preferred current-state implementation guide **subject to the Custody qualification and evidence-tier limits in this document**.
5. The completed `native-python-pipelines-completion`, `native-composition-followup`, and `native-platform-followup` initiatives remain historical substrate/evidence. They are not launch targets for the corrective destination.

## 2. Custody M11 claim check

### 2.1 What is real

The historical completion claim is real. Commit `d10b0fef2b6` exists and is titled `feat(megaplan): complete custody M11 acceptance and recovery control plane`.

The adverse review is also real. The 2026-08-02 Sol audit found effect bypasses and shadow authorization, observed that the binding decision was still `proposed-human-gate`, and required Run Authority to append a superseding quarantine decision plus new zero-blocker acceptance evidence (`.megaplan/audits/critique-ledger-incident-sol-review-20260802.md:70-78`). Its overall verdict is NO-GO for mutation (`:1-32`, `:248-265`).

Current repository state corroborates the NO-GO:

- the controlling ownership decision is still `status: proposed-human-gate` with `approval_record: pending` (`.megaplan/initiatives/custody-control-plane/decisions/single-authoritative-runtime-history.md:1-10`);
- the generated ownership record reports `blocker_count: 4` (`evidence/ownership-decision-record.json:58-61`);
- the Custody README says the nine-milestone chain is deliberately unlaunched and fail-closed (`.megaplan/initiatives/custody-control-plane/README.md:51-87`, `125-146`);
- the post-M11 release evidence is explicitly `in progress` and says final integrated validation, release/promotion, runtime canary, and downstream launch remain pending (`docs/megaplan/post-m11-release-evidence-20260731.md:1-12`, `124-141`);
- the Native chain requires a content-addressed Custody completion manifest and `bounded-incident-projection-handoff.json` (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:14-19`), while neither required artifact exists at the initiative root in this checkout.

Therefore the old completion/promotion claim is **not admissible as Native Parity's prerequisite today**.

### 2.2 What Plan B overstates

Plan B says the audit “explicitly invalidates” the completion/promotion claim (`docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md:109-115`). The audit's actual language is prospective: “Run Authority must append a superseding decision” (`.megaplan/audits/critique-ledger-incident-sol-review-20260802.md:70-78`). The same audit makes an approved zero-blocker decision a future go condition (`:223-260`).

No canonical superseding Run Authority invalidation/quarantine decision was found in the repository. The decision record remains proposed/pending, not superseded/approved. Thus:

- **Correct:** the old M11 completion claim is currently unusable, contradicted by later evidence, and must not satisfy Native admission.
- **Not established here:** that Run Authority has already recorded the canonical invalidation event.
- **Required P1 result:** either import and verify that canonical superseding record and subsequent re-acceptance artifacts from the authoritative checkout, or have Custody produce them. Absence is a stop condition, never permission for Native to infer acceptance.

This distinction matters because the report assigns permission and quarantine to Run Authority, not to an audit document or status projection (`docs/arnold/megaplan-native-representation-report.md:180-193`).

## 3. Milestone-by-milestone diff

Legend: **Same** = same executable milestone; **Presentational** = same work regrouped or described with more evidence/ownership detail; **Real** = changed order, scope, acceptance, or owner.

| # | Plan B milestone | Plan A / prior decomposition | Verdict | Difference |
|---:|---|---|---|---|
| 1 | P0 MRC intake/crosswalk | No standalone milestone; Plan A predates MRC | **Real** | New read-only prerequisite. It freezes MRC provenance and prevents MRC receipts/capabilities from being mistaken for accepted M11 authority. Separate milestone packaging is discretionary; the crosswalk before M11 acceptance is necessary. |
| 2 | P1 complete/accept Custody M11 | Plan A assumes accepted/manifested M11 before the sequence | **Real** | Status changed. Current evidence does not satisfy the assumption. P1 must resolve admission or perform Custody-owned corrective re-acceptance. Plan B's unconditional “finish nine residual milestones” is too specific without the authoritative Custody state. |
| 3 | P2 milestone-gate bootstrap | Same one-sprint prerequisite | **Same** | Same order, owner, and purpose: non-self-hosted pre/post-merge gates, exact predecessor artifacts, receipt-consuming transitions (`docs/arnold/DEPRECATED-completion-spec-sequencing-and-ownership.md:34-48`). B adds MRC evidence conventions. |
| 4 | Native S1 custody admission / semantic baseline | Corrective S1 | **Same + acceptance expansion** | Same scope and owner. B adds MRC crosswalk, allowance, invocation-receipt, and evidence-pack details. |
| 5 | Native S2F `.pype` compiler/identity/converter | Corrective S2F | **Same** | Same GO-FORMAT transition and post-transition proof. `.pype` is already adopted by the amended report and corrective initiative; only the older alignment text remains stale. |
| 6 | Native C1 completion contract/identity shadow | Corrective C1; redistributed Completion M1 | **Same / presentational** | Same position, non-authoritative status, false-done fixture, and divergence ledger (`.megaplan/initiatives/megaplan-native-parity-corrective/README.md:172-196`). |
| 7 | Native C2 completion binding/evaluation shadow | Corrective C2; redistributed Completion M2 | **Same / presentational** | Same position, wire/decoder proof, restore/projection invariance, and no-authoritative-writer rule. |
| 8 | Native S2R durable primitives/custody binding | Corrective S2R | **Same** | Same sole GO-0 kernel enablement. B makes MRC capability/elapsed-budget/canary patterns explicit. |
| 9 | Native S3A prep/plan/critique cutover | Corrective S3A | **Same** | Same GO-1A boundary and same D1/D2 semantics. |
| 10 | Native S3B gate/revise cutover | Corrective S3B | **Same** | Same GO-1B boundary and same ban on state/status-derived route authority. |
| 11 | Native S4 tiebreaker/finalize/human reentry | Corrective S4 | **Same** | Same child-workflow and durable-reentry cut. B adds current launcher provenance requirements. |
| 12 | Native S5A delivery shadow/effect-class proof | Corrective S5A | **Same** | Same zero-live-write GO-2 shadow and exhaustive effect-class proof. |
| 13 | Native S5B live delivery/review-rework cutover | Corrective S5B | **Same** | Same single-writer cut, reconciliation, rollback, and post-transition proof. |
| 14 | Native S6 override/recovery/auto-drive/projections | Corrective S6 | **Same** | Same GO-3 authority move and observer demotion. MRC semantics remain explicitly excluded. |
| 15 | Native S7 independent conformance / GO-4 | Corrective S7 | **Same + acceptance expansion** | Same terminal corrective gate. B adds a uniform MRC-shaped pack, but the Native validator and all 31 rows/D1-D15 remain controlling. |
| 16 | Platform S1 candidate inventory/contract freeze | Prepared Platform S1 | **Same** | Same candidate classification, exclusions, invalid corpus, and handoff intake. |
| 17 | Platform S2A neutral runtime/admission/authority | Prepared Platform S2A | **Same** | Same in-place generalization without a second completion kernel or owner store. |
| 18 | Platform S2B neutral `.pype` authoring/package core | Prepared Platform S2B | **Same** | Same compiler/linker/package/refactor productization. |
| 19 | Platform S3 developer tooling | Prepared Platform S3 | **Same** | Same format/lint/preview/test/editor/usability work. |
| 20 | Platform S4 first isolated extraction/recomposition | Prepared Platform S4 | **Same** | Same first four reuse claims and Megaplan consumption without duplicate writer. |
| 21 | Platform S5 unrelated adversarial consumer | Prepared Platform S5 | **Same** | Same second-consumer challenge and separate new-instance/resume verdicts. |
| 22 | Platform S6 certification/evolution/adoption | Prepared Platform S6 | **Same** | Same sole stable-publication point and final content-addressed conformance. |

### 3.1 How the older initiative decomposition maps

The older initiatives are not missing work; their useful outputs are substrate consumed by the corrective chain. Their milestone boundaries are not the active boundaries.

| Historical initiative/milestones | Active disposition |
|---|---|
| `native-python-pipelines` M2–M7 | Historical first native runtime/pilot/default-flip migration. Its graph/native parity techniques feed S1/S2F/S2R; it cannot prove source authority because the current compiler and canonical file still use `.pypeline` and handler/route metadata (`arnold/workflow/source_compiler.py:98-124`; `arnold_pipelines/megaplan/workflows/workflow.pypeline:94-400`). |
| `native-python-pipelines-completion` M1–M7 | Completed substrate for platform contract, layout, migration, evidence, goldens, docs, and purge. Its manifest marks every milestone done (`.megaplan/initiatives/native-python-pipelines-completion/completion-manifest.json:7-120`). Those results are inputs to corrective S1/S2F/S2R/S7, not substitutes for them. |
| `native-composition-followup` M0 contract | Input to corrective S1/S2F/S2R contract and invalid-corpus work. |
| Composition M1 Megaplan migration | Redistributed across Native S3A–S6, where authority cuts are explicit. |
| Composition M2 routing/authoring boundary | Redistributed across S2F, S2R, S3B, and S7. |
| Composition M3 nested invocation | Redistributed across S2R and S4, then generalized in Platform S2A/S2B. |
| Composition M4 trace/audit | Redistributed across S2R, S4–S6, and S7 proof. |
| Composition M5 resume/path | Redistributed across S2R, S3A, S4, and S5B. |
| Composition M6 docs/conformance | Replaced as terminal truth by corrective S7. The historical completion manifest proves the old chain completed, not that the corrective endpoint exists (`.megaplan/initiatives/native-composition-followup/completion-manifest.json:7-103`). |
| `native-platform-followup` M1 effects/idempotency | Useful substrate for Custody/MRC and Native S5A/S5B; not the reusable-component standard. |
| Historical Platform M2 security/approval | Useful substrate for Custody, Native S2R/S5/S6, and Platform S2A. |
| Historical Platform M3 packs/versioning | Input to Platform S1/S2A/S2B, but not cross-product substitutability proof. |
| Historical Platform M4 durability/checkpoints | Input to Native S2R/S4/S5B and Platform S2A. |
| Historical Platform M5 worker supervision/cancellation | Input to MRC/Custody and Native S5/S6. |
| Historical Platform M6 docs/conformance | Historical proof bound to `.pypeline`, `planning.py`, and handlers (`.megaplan/initiatives/native-platform-followup/completion-manifest.json:114-218`). It cannot replace corrective S7 or new Platform S6. |

This mapping follows the alignment plan's own rule: `enabled` substrate is not `implemented` report conformance while route/loop/retry/fanout/suspension semantics remain in handlers (`docs/arnold/megaplan-native-representation-alignment-plan.md:99-120`).

## 4. Real divergences and adjudication

| ID | Real divergence | Necessary or discretionary | Evidence and ruling |
|---|---|---|---|
| D1 | Add MRC→M11→Native intake before Custody admission | **Necessary content; discretionary milestone packaging** | MRC landed reusable receipt/capability/canary patterns, but its domain schemas and authority are not M11. The wrapper now records requested route, resolved model, process identity, output digests, and elapsed time (`scripts/run_maintenance_consolidation_agent.py:19-31`, `399-531`). A crosswalk is required to prevent false substitution. It may be P0 or a mandatory first gate inside P1; keeping P0 is clearer and read-only. |
| D2 | Replace “M11 already complete” with a blocking admission/re-acceptance step | **Necessary** | No required completion manifest/handoff is present; the ownership decision is pending; blockers and unfinished release gates remain. The old claim cannot launch Native. |
| D3 | Describe the 2026-08-02 audit as an already-recorded Run Authority invalidation | **Incorrect, must be corrected** | The audit orders Run Authority to append the superseding decision; it does not show that decision was appended. Treat the old claim as non-admissible now, while P1 obtains canonical invalidation/re-acceptance evidence. |
| D4 | Require all nine residual Custody milestones to run | **Discretionary and currently unsupported** | The local Custody README describes a nine-milestone corrective chain, but Plan B itself asks whether accepted remote artifacts exist (`docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md:503-506`). P1 should specify outputs and owner, not pre-decide the recovery path. |
| D5 | Move target suffix from `.pypeline` to `.pype` | **Necessary, but not new against amended Plan A** | The report already adopts one workflow per `.pype` (`docs/arnold/megaplan-native-representation-report.md:171-178`); the current compiler still supports only `.py`/`.pypeline` and hard-codes `workflow.pypeline` (`arnold/workflow/source_compiler.py:98-124`). The alignment plan's `.pypeline` wording is stale and needs a supersede note. |
| D6 | Apply MRC evidence-pack conventions | **Necessary at authority/effect/publication cuts; discretionary as an identical pack for every milestone** | Content-addressed inputs, stable validator codes, allowance lineage, independent review, and pre/transition/post receipts directly defend S2F/S2R/S3A/S3B/S4/S5B/S6/S7 and Platform S2A/S4/S6. Requiring canary/rollback/process evidence where a milestone makes no authority/effect change adds cost without stronger proof. Each milestone should use the applicable subset plus the Native-specific row/mutation contract. |
| D7 | Record OMP launcher/resolved-model provenance | **Necessary for worker evidence; not product authority** | The current MRC wrapper dispatches through `launch_omp_agent.py` and binds resolved-model/process/output evidence (`scripts/run_maintenance_consolidation_agent.py:19-31`, `154-163`, `477-531`). Native evidence must describe the actual launcher. The workflow must not encode the MRC role-to-model table as semantic policy. |
| D8 | Reclassify old completion/composition/platform manifests as historical substrate | **Necessary** | Their manifests are real and completed, but they bind the pre-corrective `.pypeline`/handler surface. The new Platform README expressly distinguishes historical hardening from the new component standard (`.megaplan/initiatives/native-workflow-platformization/README.md:45-61`). |
| D9 | Add checkout/branch locality as a launch constraint | **Necessary operationally** | Completion state/manifests are checkout-local and the deprecated sequencing analysis records serial execution in the Custody checkout from the then-durable `editible-install` source (`docs/arnold/DEPRECATED-completion-spec-sequencing-and-ownership.md:50-61`). The present worktree may author plans but cannot infer launch authority. |
| D10 | Expand document owners and deferral owners | **Mostly presentational; ownership separations are necessary** | Naming owners improves auditability. The load-bearing parts are that Custody alone resolves missing M11 capabilities, the bootstrap owns generic chain enforcement, Native owns product semantics, and Platform owns only post-S7 neutral extraction. Document-role labels themselves do not change order. |

## 5. Agreement that should not be relitigated

Both plans agree on these load-bearing decisions:

- Native Parity precedes generic Platformization.
- The accepted M11 control-plane contract is a prerequisite, not something Native may emulate locally.
- The milestone-gate bootstrap precedes every authority-changing Native milestone.
- C1/C2 remain non-authoritative between S2F and S2R; S2R is the sole completion-kernel enablement.
- `.pype` source owns product topology; generated manifests own admitted runtime/replay coordinates, not editable semantic truth.
- Each cut follows inert landing/comparison, merge-HEAD readiness, one typed transition, independent post-verification, old-producer inertness, then fence/delete.
- External effects may be compared or dry-run, never dual-written.
- Native S7, not historical chain completion or current source readability, closes Stage 1.
- Platform S5 supplies the unrelated consumer; Platform S6 alone may publish a stable standard.

## 6. Required supersede notes; no rewrites

### 6.1 Plan A report

Add a short dated note after the 2026-07-30 sequencing amendment:

- point to this reconciliation and Plan B;
- state that accepted Custody M11 remains the prerequisite, but this checkout does not currently contain admissible proof of that acceptance;
- identify P0 as the read-only MRC crosswalk and P1 as admission resolution/corrective re-acceptance;
- retain the architecture and existing historical text unchanged.

### 6.2 Plan A alignment plan

Add a versioned supersession note, not a rewrite:

- replace the active target reference `workflow.pypeline` with the adopted one-workflow-per-file `.pype` contract while preserving the old baseline text as history;
- remap ownership from Completion/Composition/Historical Platform milestones to corrective S1/S2F/C1/C2/S2R/S3A/S3B/S4/S5A/S5B/S6/S7 and new Platform S1/S2A/S2B/S3/S4/S5/S6;
- preserve all 31 rows, H0–H9, D1–D15, false-pass scenarios, and negative invariants;
- add applicable MRC provenance/allowance/transition evidence fields without allowing MRC artifacts to satisfy M11 or Native semantic proof.

### 6.3 Plan B

Add a supersede note at the top:

- replace “the audit explicitly invalidates” with “the audit makes the old claim non-admissible and requires a canonical Run Authority invalidation/quarantine decision; that canonical decision is not evidenced in this checkout”;
- redefine P1 as output-based Custody admission resolution, with local nine-milestone execution only if canonical current state requires it;
- distinguish mandatory evidence at authority/effect/publication cuts from proportional evidence at read-only/compiler/tooling milestones;
- state that this reconciliation controls where its wording differs.

### 6.4 Initiative documents

Do not rewrite completed manifests or historical briefs. Add only status/supersession banners where absent:

- `native-python-pipelines`, `native-python-pipelines-completion`, `native-composition-followup`, and `native-platform-followup`: historical substrate; no relaunch; completion is not corrective conformance.
- `megaplan-native-parity-corrective`: active Stage-1 executable authority after P1/P2 proofs exist.
- `native-workflow-platformization`: prepared Stage-2 executable authority after Native S7 handoff.

## 7. Launch decision

**NO-GO at P1 in this checkout.** P0 may run read-only. Native S1 may not start until all of the following are content-addressed and validator-green:

1. canonical Run Authority disposition of the prior M11 completion/promotion evidence;
2. approved zero-blocker ownership decision;
3. accepted Custody M11 completion manifest and proof map;
4. accepted `bounded-incident-projection-handoff.json`;
5. complete installed/runtime/production-vector and canary acceptance required by the current Custody contract;
6. accepted milestone-gate bootstrap manifest and all three readiness artifacts.

Once those gates are met, execute the exact merged sequence in §1. No reordering of C1/C2, no jump to S3A based on the current visible `.pypeline` topology, and no credit from historical completion manifests beyond their declared substrate proofs.
