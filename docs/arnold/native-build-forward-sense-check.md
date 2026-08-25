# Native Build Forward — Plan Sense-Check

## Verdict

The 22-position sequence is architecturally coherent and covers both destinations: Native S1–S7 closes source-authoritative Stage 1, then Platform S1–S6 extracts, challenges, and certifies the reusable platform. The linear order in `chain.yaml` matches the reconciliation exactly (`docs/arnold/native-plan-reconciliation-2026-08-24.md:9-25`; `.megaplan/initiatives/native-build-forward/chain.yaml:7-157`). C1/C2 remain shadows before S2R, S2R is the sole completion-kernel enablement, S5A precedes the live S5B writer cut, S7 precedes all Platform work, and S5 supplies the unrelated consumer before S6 publication.

The plan is not launch-ready unchanged. The milestone briefs are coherent, but the consolidated executable chain drops the fail-closed machinery carried by the corrective and Platformization chains. As written it can advance on agent completion rather than validator-green evidence.

## Blocking findings

### B1 — P1 cannot both close and leave one of its stated six results unresolved

The P1 outcome says it resolves all six NO-GO gates (`.megaplan/initiatives/native-build-forward/briefs/p1-custody-m11-admission.md:3-6`), but its constraints and done criteria validate only gates 1–5 and deliberately emit gate 6 as unsatisfied (`:23-34`). The initiative README confirms that conditional behavior (`.megaplan/initiatives/native-build-forward/README.md:23-25`). This sequencing is sensible—P2 must produce gate 6—but the P1 completion contract is not.

Required correction before launch: define P1's terminal as `custody-admissible / bootstrap-pending`, not “six gates resolved”; define Native S1 admission as the first terminal that can assert all six. The existing order remains P1 → P2 → S1.

### B2 — Custody correction has no executable ownership or checkout handoff

P1 may discover that accepted artifacts do not exist and then says to “execute only Custody-owned corrective re-acceptance” (`.megaplan/initiatives/native-build-forward/briefs/p1-custody-m11-admission.md:7-10`). The reconciliation says the exact evidence may live in another authoritative checkout and absence is a stop condition for Native (`docs/arnold/native-plan-reconciliation-2026-08-24.md:53-63`). Yet the active chain is one auto-merged chain on one base branch and gives P1 only a linear dependency (`.megaplan/initiatives/native-build-forward/chain.yaml:1-24`, `159-169`). It does not name a prerequisite Custody chain, completion manifest, authoritative checkout, import protocol, or resumable external-result handoff.

This is an authority bug if P1 mutates Custody from the Native chain and a liveness bug if P1 merely stops. Make P1 result-only in this chain: either verify/import canonical accepted artifacts, or emit a typed blocked result naming the Custody-owned chain/session and exact missing artifacts. Resume P1 only from a content-addressed Custody completion handoff.

### B3 — The consolidated chain drops the executable gates

Every brief says predecessor hashes must be preserved and outputs must be content-addressed, validator-green, and consumed by the next milestone (for example Native S7 at `.megaplan/initiatives/native-build-forward/briefs/native-s7-conformance.md:23-34`). The consolidated `chain.yaml` encodes only labels, profiles, auto-merge, and `depends_on` edges (`.megaplan/initiatives/native-build-forward/chain.yaml:7-169`). It has no `launch_preconditions`, milestone `validate` gates, proof maps, validation receipts, or receipt-consuming transitions.

That is a regression from the executable sources it consolidates. The corrective Native chain requires completed bootstrap and Custody chains with exact proof artifacts, then binds every milestone to a conformance gate, traceability file, proof map, and receipt (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:5-19`, `52-64`). The Platformization chain likewise requires the validated Native completion and exact handoff artifacts (`.megaplan/initiatives/native-workflow-platformization/chain.yaml:6-25`). P2's promise is therefore not attached to P1, S1, or later cuts. With `auto_approve: true`, prose is the only barrier to false advancement.

Before launch, either preserve those executable chains and make this initiative an orchestrating chain-of-chains, or port their launch preconditions, conformance validators, proof maps, receipts, and transitions without weakening them. Label-level dependency completion is insufficient.

### B4 — The declared “milestone 23/reconcile” does not exist in the corpus

The initiative explicitly defines a 22-position chain (`.megaplan/initiatives/native-build-forward/README.md:16-20`), and `chain.yaml` ends at Platform S6 (`.megaplan/initiatives/native-build-forward/chain.yaml:152-169`). Neither the plan nor briefs define a twenty-third reconciliation/closure milestone. Platform S6 already owns the final proof map, completion manifest, publication, and post-transition receipt (`.megaplan/initiatives/native-build-forward/briefs/platform-s6-certification.md:29-34`).

Choose one contract before execution: either Platform S6 is terminal closure and references to “milestone 23/reconcile” are removed, or add a result-only reconciliation milestone that verifies the final aggregate without republishing or self-certifying. Do not leave an implied post-chain closure outside executable authority.

### B5 — Executable authority is duplicated and the new spec is not bootstrap-bound

The new README calls this initiative the “single cloud-epic source” (`.megaplan/initiatives/native-build-forward/README.md:3-12`), while the corrective Native and Platformization chains still contain richer executable authority. The controlling plan and reconciliation identify those active chain specs as authority but do not identify the new consolidated initiative as their replacement (`docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md:38-47`; `docs/arnold/native-plan-reconciliation-2026-08-24.md:27-33`). The bootstrap contract's downstream binding was authored for the corrective and Platformization specs, not this new `chain.yaml` (`.megaplan/initiatives/megaplan-chain-milestone-gates/briefs/s1-premerge-content-addressed-conformance-gates.md:5-13`).

Record an explicit supersession/aggregation decision and regenerate `downstream-spec-readiness.json` against the exact selected chain. Until then, there are three plausible executable authorities and no proof that P2 attests this one.

## High risks and missing decisions

### H1 — Auto-merge is configured before principals are identified

All milestones use `merge_policy: auto`, and the driver uses `auto_approve: true` (`.megaplan/initiatives/native-build-forward/chain.yaml:7-169`). P2 still has no named trusted verifier or merge-readiness principal (`.megaplan/initiatives/native-build-forward/briefs/p2-milestone-gate-bootstrap.md:18-26`). The plan also leaves exception authority, every GO transition principal, and review routing open (`docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md:525-536`). Auto-merging code after an independent machine review is compatible with the plan; auto-selecting an authority principal is not. Record principals and identity-separation rules before the affected milestone starts.

### H2 — P2 omits the bootstrap's concrete independent attestation

P2 says the bootstrap may not authorize itself, but its brief names only independent verification and three readiness files (`.megaplan/initiatives/native-build-forward/briefs/p2-milestone-gate-bootstrap.md:18-34`). The bootstrap's own contract additionally requires external PR CI and `bootstrap-independent-attestation.json` binding the proposed tree, CI suite/digest, verifier trust class, disposition, merge commit, and implementation diff; branch protection must block auto-merge when it is missing (`.megaplan/initiatives/megaplan-chain-milestone-gates/briefs/s1-premerge-content-addressed-conformance-gates.md:15-35`). The cloud spec contains no PR-CI wiring (`.megaplan/initiatives/native-build-forward/cloud.yaml:1-16`). Carry that attestation and trust configuration into P2 acceptance explicitly.

### H3 — Open decisions have no explicit decision checkpoints

Every brief forbids executors from implicitly resolving authority, order, or must-level criteria, but several questions determine implementation contracts: legacy reader horizon (S2F), duplicate-human arbitration (S4), package namespaces (Platform S1), usability thresholds (Platform S3), and the actual unrelated consumer (Platform S5). The plan itself lists ten unresolved choices (`docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md:525-536`). Assign each to a named decision record, owner, and latest closing milestone; otherwise the unattended chain can only guess or stop.

### H4 — P1 corrective work precedes the gate intended to protect authority-changing milestones

The reconciliation intentionally orders P1 before P2, but P1 may perform corrective re-acceptance while P2 is the milestone that establishes non-self-hosted pre/post-merge gates. This is safe only if P1 is a result gate and any correction runs under Custody's already-valid independent controls. It is unsafe if the Native chain performs authority-changing correction inline. B2's result-only boundary is therefore load-bearing.

### H5 — Base-branch and editable-runtime lineage disagree

The consolidated chain and cloud workspace target `integration/goal-maintenance-runtime-20260820` (`.megaplan/initiatives/native-build-forward/chain.yaml:1`; `.megaplan/initiatives/native-build-forward/cloud.yaml:3-11`). Both detailed executable chains target `editible-install` (`.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml:1`; `.megaplan/initiatives/native-workflow-platformization/chain.yaml:1`), and bootstrap acceptance includes `editable-runtime-readiness.json`. No crosswalk proves these branches contain the same admitted runtime, validators, transition handlers, and evidence paths. Bind P0/P2 to the selected base tree and fail on drift.

### H6 — Required handoff detail was collapsed

The consolidated S7 brief asks only for a handoff digest (`.megaplan/initiatives/native-build-forward/briefs/native-s7-conformance.md:29-34`). The prepared Platformization contract requires a full `platformization-handoff-manifest.json` containing candidate/coupling maps, contract snapshots, golden adapters, DX/numeric baselines, CAS/adapter provenance, C1/C2 manifests, S2R enablement receipt, divergence ledger, decoder matrix, false-done fixture, legacy-writer retirement, and the Custody bounded-projection/57k benchmark receipt (`.megaplan/initiatives/native-workflow-platformization/README.md:10-33`). Restore the exact artifact list to S7 and Platform S1 preconditions; a generic digest is not equivalent.

### H7 — Documentation governance contains one stale authority claim

The documentation map says the audit “invalidates” the prior M11 claim (`docs/arnold/native-megaplan-build-forward-documentation-map.md:3-8`). The controlling reconciliation says the audit makes the claim non-admissible but does not establish that Run Authority appended the canonical invalidation (`docs/arnold/native-plan-reconciliation-2026-08-24.md:53-63`). Mark the sentence superseded before operational use.

### H8 — Brief structure and alignment ownership remain partially stale

The documentation map requires each active brief to carry explicit MRC reuse, evidence-pack, Native alignment, false-pass, and deferral-owner sections (`docs/arnold/native-megaplan-build-forward-documentation-map.md:299-326`). The new briefs compress these into generic bullets and often omit a named deferral owner. They also cite the unamended alignment matrix, whose active rows still name old Completion/Composition milestones and `.pypeline` (`docs/arnold/megaplan-native-representation-alignment-plan.md:99-120`, `154`). Update the ledger and restore explicit ownership before its rows are used as executable proof obligations.

### H9 — Quantitative acceptance baselines are deferred but not scheduled

The plan requires numeric compile, replay, fanout, projection, clean-install, and editor baselines (`docs/arnold/native-megaplan-build-forward-plan-2026-08-24.md:513-523`). Platform S3 asks which tasks and thresholds define usability (`.megaplan/initiatives/native-build-forward/briefs/platform-s3-developer-tooling.md:18-34`). Capture Stage-1 runtime baselines by S1/S2R and freeze Platform usability thresholds before S3 implementation; otherwise “no regression” and “usable” remain retrospective judgments.

## Coverage assessment

### Stage 1

Coverage is complete if the stated evidence gates are made executable. S2F establishes the `.pype` frontend, identity, conversion, package, and legacy boundary; C1/C2 prove completion identity and wire evaluation in shadow; S2R provides durable loops, fanout, reducers, suspension, checkpoints, policy, and the sole kernel; S3A/S3B/S4/S5A/S5B/S6 migrate D1–D15 product semantics and effects; S7 requires every alignment row, H0–H9, zero live compatibility authority, restore coverage, install equivalence, and the Platform handoff (`.megaplan/initiatives/native-build-forward/briefs/native-s2f-pype-format.md:3-34`; `native-s2r-durable-primitives.md:3-34`; `native-s7-conformance.md:3-34`).

No Stage-1 semantic area from the representation report's target is unowned. The main risk is false advancement from prose-only gates, not missing product scope.

### Platformization

Coverage reaches the two-stage destination. S1 freezes candidate boundaries; S2A generalizes runtime/admission without a second kernel; S2B productizes the same authoring contract; S3 delivers same-path tooling; S4 proves isolated extraction and the first four reuse claims; S5 provides the unrelated consumer and separate substitution/resume verdicts; S6 alone publishes certified components with compatibility, evolution, migration, rollback, and both-consumer proof (`.megaplan/initiatives/native-build-forward/briefs/platform-s1-inventory.md:3-34`; `platform-s4-recomposition.md:3-34`; `platform-s5-second-consumer.md:3-34`; `platform-s6-certification.md:3-34`).

The plan correctly does not promise that every candidate becomes stable. Failed or one-consumer-only candidates remain internal/experimental.

## Admission assessment

P0's intended crosswalk is adequate, but its named `mrc-native-intake-manifest.json` is not an explicit P1 input. P1 correctly enumerates gates 1–5 and the P2-owned blocker; P2 describes merge-HEAD proof; S1 says it re-admits all six. None of those checks is wired into the consolidated chain, and P2 omits the bootstrap attestation described above.

Therefore P0/P1/P2 de-risk the start at the design level only. They do not yet fail closed at the executable level. The correct launch verdict remains NO-GO at P1 until B1–B3 and B5 are resolved and the exact base/spec/attestation lineage is bound.