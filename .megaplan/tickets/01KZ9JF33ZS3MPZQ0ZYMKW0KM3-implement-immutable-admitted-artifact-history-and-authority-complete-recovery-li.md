---
id: 01KZ9JF33ZS3MPZQ0ZYMKW0KM3
title: Implement immutable admitted-artifact history and authority-complete recovery
  lifecycle
status: open
source: human
tags:
- bug
- architecture
- custody
- recovery
- observability
codebase_id: null
created_at: '2026-08-05T18:20:12.287689+00:00'
last_edited_at: '2026-08-05T18:55:53.547475+00:00'
epics: []
---

## Problem and evidence

The first broken contract is `admitted_plan_generation_must_be_immutable`: an admitted content identity was later represented by the mutable pathname `plan_v2.md`, whose bytes changed after admission. The validator correctly failed closed during whole-history replay; it compared the v2 custody receipt's admitted SHA-256 `39f221cf6c0b73ee081e92a9c0a0c6cfb9a3e6f88b69cfda2d8567f1bd6859e9` with the observed SHA-256 `afbdadd27605ea77c1399f3a99855ceb574e317539a2f0222b9bbed97721edc1` and rejected the broken edge `critique_custody_v2.json -> plan_v2.md`.

Canonical evidence:

- `.megaplan/incident-evidence/superfixer-r6-20260805T1719Z/handoff.md`
- `.megaplan/incident-evidence/superfixer-r6-20260805T1719Z/blocked-receipt.json`
- `.megaplan/incident-evidence/superfixer-r6-20260805T1719Z/swarm-index.md`
- Admitted receipt: `.megaplan/plans/cl2-wbc-backed-ledger-20260805-1351/critique_custody_v2.json`
- Drifted projection: `.megaplan/plans/cl2-wbc-backed-ledger-20260805-1351/plan_v2.md`

The ordinary fixer also correctly stopped. The terminal path persisted neither one normalized repair identity nor one occurrence-bound repair request joining Run Authority → Custody → WBC. Same-occurrence continuation is forbidden, the parent and chain are terminally blocked, retries are exhausted, and the stopped runner lease is liveness evidence rather than Run Authority. With no accepted authority decision, exclusive custody claim/epoch, WBC attempt/GLEK, exact failed-history cursor, or supported request-to-migration adapter, acting would risk duplicate or unauthorized effects. Keep occurrence `occ-r6-launch-20260805-finalize-custody-20260805T1609Z` and Horizon A quarantined.

Writer identity is indeterminate. The evidence establishes an iteration-3 drafting content lineage and a bounded mutation window, but it does not bind the write to a unique process, PID, model, invocation, or tool.

## Checker philosophy and minimum data contract

Keep one control loop: **observe canonical state → decide → read the minimum authoritative recovery identity → submit one idempotent request → ordinary fixer → authoritative proof**. The checker is an observer and request client, not a second lifecycle database or a source of authority. Model output may explain or rank causes, but it must never supply an identity, fence, cursor, claim, decision, or success proof.

The hard recovery contract is intentionally small:

- target and parent: session/chain/plan plus parent run, revision/incarnation, and current Run Authority cursor/fence;
- occurrence: one deterministic terminal-event identity and its exact failure evidence cursor/digest;
- authority: one accepted Run Authority recovery decision, including current-source check, retry/migration selector, runtime digest, and contract digest;
- exclusivity and effects: one Custody claim/lease with positive epoch/fence and one WBC attempt/GLEK, all joined to the same request and occurrence;
- execution and proof: one idempotency key, accepted task/result envelopes, validator result, and CAS-protected cursor or milestone advancement.

The checker derives those facts from the lifecycle store, Run Authority journal, Custody lease store, WBC attempt ledger, runtime binding, and canonical plan/chain state. It does not demand them from Sol/Flash prose or copy them from a stale projection.

Diagnostic fields are useful but optional: exact writer/PID/model/tool attribution, provider invocation, host/container detail, free-form analysis, expanded telemetry, and stale observer projections. Persist absent values as `unknown`. They become a hard stop only if a named runtime/contract or authoritative identity cannot otherwise be established.

## Horizon A — make deterministic terminal failures repairable

1. At the terminal lifecycle seam, persist the normalized occurrence/parent repair identity and exact failed-event cursor before clearing `active_step`; idempotently call the existing occurrence-bound request producer. Re-entry returns the same request.
2. Let the checker reread canonical state and call that same producer. If the identity already exists, missing forensic detail does not block enqueue. If it does not exist, the producer returns a typed authority gate; the checker must not reconstruct it from a stopped lease or history labels.
3. Run Authority decides whether the accepted request permits a same-boundary retry or an occurrence-preserving migrated child. Custody and WBC then supply the exclusive claim/epoch/fence and single attempt/GLEK.
4. Add the genuinely missing production adapter: consume an accepted migration request in the ordinary fixer and bind it to the existing `MigrationCoordinator` plus production owner adapters. The checker must not call the coordinator directly.
5. Verify the fixer result against the bound runtime/contract, complete validator result, accepted envelopes, and canonical cursor/milestone CAS. Only then may notification custody admit one intent/effect.

The r6 occurrence remains quarantined at step 1. Its plan has no `active_step`, persisted repair identity, or failed-history cursor; the canonical owners have no occurrence-bound Run Authority decision, Custody epoch, WBC attempt, or request. The fence-3 stopped runner lease is not Run Authority. No supported action may mint these records retrospectively from the available files.

Checker plumbing should remain small:

- enforce a CAS/lease for a stable target key `(session, chain, plan/current occurrence)` in the existing schedule repository so interval and immediate schedules cannot overlap;
- bind every evidence/Sol/Flash child to the managed occurrence manifest and owned process group, with a terminal custody receipt on success, failure, or interruption;
- treat a schema-valid blocked/quarantined receipt as a successful checker diagnosis (`blocked`), distinct from worker/import/provider failure; neither classification means the plan advanced;
- dedupe notifications by `(target, occurrence, decision/state-transition digest)` in the existing notification intent/effect store, and stay silent for healthy/no-change polls;
- write an after-proof bundle joining request, decision, claim, attempt/effect, runtime/contract, accepted result, validator result, and before/after canonical cursor. PID, heartbeat, launch acknowledgement, and prose are never proof.

## Horizon B — immutable admitted artifacts and durable lifecycle

Make `arnold.megaplan.custodied_artifact_history.v1` the canonical admitted-artifact contract. Admission compare-and-creates immutable content-addressed bytes and appends a generation manifest containing only the required identity: artifact digest, logical role/generation, parent/history-head digest, occurrence/admission receipt, and runtime/contract binding. Human-readable `plan_vN.md` files become replaceable projections. Drafts and admitted objects use separate write roots, and every revision admits a new generation. Validators replay manifest/object identities, not mutable pathnames.

Writer/provider/process attribution is optional diagnostic metadata and may be `unknown`; its absence does not invalidate an otherwise content-addressed, authority-bound generation. Legacy migration seals only byte-matching generations through explicit migration receipts and quarantines mismatches without inventing provenance.

Roll out minimally: freeze the schema and contract digest; shadow-build/read manifests; migrate byte-matching history; cut writers and validators together; then enable the lifecycle request-to-fixer adapter. Roll back by stopping new admission and restoring the prior bound runtime/configuration while preserving append-only evidence—never by rewriting history.

## Acceptance and closure tests

- Frozen r6 fixture: the v2 admitted digest and drifted pathname reproduce the validator failure; the historical parent stays byte-for-byte unchanged.
- Admission: direct overwrite, explicit-filename rewrite, rename/copy-back, formatter, retry, and concurrent publication cannot alter an admitted object; identical retry returns the same generation.
- Minimum-data recovery: recovery succeeds when required owner records exist even if writer/PID/model/provider diagnostics are `unknown`; it blocks when parent/occurrence/current-source/fence, claim, WBC attempt, runtime/contract, or result/cursor proof is absent or divergent.
- Idempotency/concurrency: repeated polls, interval-plus-immediate firing, concurrent enqueue, crash/recovery, and stale observer replay produce one occurrence, request, accepted decision, claim/epoch, WBC attempt/GLEK, fixer effect, and notification intent, with at most one provider effect.
- Managed completion: healthy/no-action is silent; a valid blocked receipt is classified `blocked`, not generic worker failure; import/provider/child failure remains a worker failure.
- After-proof: success requires validator admission plus accepted task/result envelopes and canonical cursor or milestone advancement under the bound runtime/contract.

## Non-goals

- No in-place rewrite of the parent artifact, custody receipt, manifest, plan/chain state, or historical evidence.
- No attribution to or blame of any PID, process, model, agent, invocation, or tool without authoritative provenance.
- No direct state edits, hand-minted repair requests, bypass of Run Authority/Custody/WBC, same-occurrence resume, critique relaunch, or notification before verified advancement.
