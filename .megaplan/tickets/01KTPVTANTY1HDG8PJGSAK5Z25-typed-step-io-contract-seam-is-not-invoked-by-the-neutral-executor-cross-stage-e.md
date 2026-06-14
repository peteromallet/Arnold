---
id: 01KTPVTANTY1HDG8PJGSAK5Z25
title: Typed step-IO contract seam is not invoked by the neutral executor (cross-stage
  enforcement is opt-in)
status: open
source: human
tags:
- arnold
- pipeline
- step-io
- contracts
- seam
- medium-severity
codebase_id: null
created_at: '2026-06-09T18:55:16.154236+00:00'
last_edited_at: '2026-06-09T18:56:20.630277+00:00'
epics:
- epic_id: aggressive-generalized-pipeline-migration
  resolves_on_complete: false
  linked_at: '2026-06-09T18:56:20.630268+00:00'
---

SEVERITY: MEDIUM — architectural gap. Partly expected mid-migration, but it currently makes a stronger claim than the runtime delivers.

FINDING (independent architecture review, 2026-06-09): the typed Port / contract step-IO layer is sound library code, but the NEUTRAL executor never calls it. Data-contract enforcement between stages is therefore opt-in, done by hand inside steps — not enforced at the seam by the runtime.

EVIDENCE (/private/tmp/arnold-target):
- step_io_handoff.py:60 — evaluate_step_io_handoff does real work: schema validation, accepted-version-range checks, fail-closed-on-write.
- arnold/pipeline/executor.py — grep shows NO reference to step_io / contract_result / ContractResult anywhere in the neutral executor's transition path.
- The only caller of the seam is the MEGAPLAN fork executor: arnold/pipelines/megaplan/_pipeline/executor.py:570.
- arnold/pipelines/evidence_pack/steps.py — the proof-of-genericity app validates contracts INSIDE its steps by hand, not at the seam.

WHY IT MATTERS: the substrate's "typed seams enforce data contracts between stages" property is true for megaplan's fork but NOT for any app on the neutral runtime today. The typed-IO layer presently DESCRIBES contracts more than the runtime ENFORCES them. Genericity of contract enforcement is unproven until a neutral-runtime app gets it for free.

PROPOSED: wire evaluate_step_io_handoff into the neutral executor's stage-transition path so produces/consumes Port contracts are enforced at the seam, gated by a per-stage/per-pipeline strictness policy (apps opt into strict enforcement; lenient stays default for back-compat). Prove it by making evidence_pack rely on seam enforcement rather than hand-rolled in-step validation.

CROSS-REF: builds on m2-step-contract-registry (done) and the .megaplan/briefs/step-io-contract brief. Likely folds into the executor-convergence / megaplan-flagship work (m10) where megaplan migrates off its fork onto the neutral executor — at which point the seam MUST be load-bearing in the neutral runtime.
