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
last_edited_at: '2026-08-05T18:20:12.287689+00:00'
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

## Required contract: `arnold.megaplan.custodied_artifact_history.v1`

Make the append-only history manifest the sole positive identity of every admitted plan or critique generation:

- Content and lineage: `artifact_id = sha256(bytes)`, media type, logical role, `generation_id`, iteration, `parent_generation_id`, predecessor-manifest digest, and history-head digest.
- Writer/runtime/provider provenance: source revision/tree digest, runtime content digest, run/revision, authenticated actor, host/container identity, process-birth identity, and provider invocation identity when model-produced.
- Authority provenance: occurrence/request identity, accepted Run Authority decision and fence, Custody lease/claim and positive epoch, WBC attempt and global logical effect key.
- Admission: create-only compare-and-create into an immutable content-addressed store; a receipt binds the object locator, artifact/generation/history digests, provenance, contract digest, and admission time. Retries may return the identical generation but never replace it.
- Projection: a human-readable pathname such as `plan_v2.md` is projection-only and non-authoritative. It binds a projected artifact digest and is rebuilt or verified from the manifest; it never defines identity.
- Isolation and validation: drafts and admitted objects have disjoint write roots; file tools cannot write admitted objects or projections; every revision creates a child generation; validators replay the complete content-addressed parent chain and fail closed on missing, deferred, mismatched, or indeterminate fields.

## Exactly-once recovery lifecycle

For each deterministic terminal occurrence key, enforce uniqueness/CAS constraints and this order:

1. The canonical lifecycle-failure owner persists exactly one normalized repair identity and idempotently creates exactly one occurrence-bound request carrying the terminal-event/adjudication digest and content-addressed migration selector.
2. Run Authority accepts or denies exactly one decision binding the parent cursor/fence, source and target revisions, runtime and contract digests, child selector, retry budget, and notification key.
3. After an accepted decision, Custody acquires exactly one exclusive claim, new epoch, and fence for that request.
4. WBC reserves exactly one attempt and one global logical effect key under that claim.
5. The ordinary fixer consumes the same request, decision, claim/epoch/fence, and attempt; it invokes only the supported occurrence-child migration adapter. Transport retries replay those identities and never mint another request, attempt, child, or effect.
6. An authoritative verifier admits the child only after real validator success and schema-valid, content-addressed task/result envelopes. Otherwise it quarantines the attempt and preserves append-only evidence.
7. Only verified canonical advancement may create one notification intent; delivery admits at most one provider effect. An ambiguous outcome remains indeterminate and is never resent.

Any stale cursor, conflicting claim, runtime/contract mismatch, missing global ownership observation, ambiguous commit/provider effect, or incomplete provenance must stop and quarantine. Partial migration recovery reuses the identical prepared transaction.

## Owner boundaries

- Artifact admission and custody owns the content-addressed object store, create-only generation API, history manifest, receipts, projections, and whole-history validator.
- Planning/critique/revise workers own writable drafts and structured result envelopes only; they cannot publish or mutate admitted paths.
- The terminal lifecycle owner owns normalized repair identity and the single canonical request producer; dispatchers/backstops may only call that idempotent producer and cannot synthesize authority.
- Run Authority alone owns recovery/migration decisions, current-source/fence validation, and retry limits.
- Custody owns exclusive claims, epochs, and fencing. WBC owns attempt reservation, GLEK uniqueness, and effect admission.
- The ordinary fixer owns execution only after consuming the complete joined identities; it does not directly edit parent state.
- Observer and notification adapters own projections and post-verification intents/effects only. Local processes, leases, markers, and cached status are corroboration, never authority.

## Migration, cutover, and closure proof

Freeze the v1 schema, owner matrix, threat model, and contract digest first. Shadow-build manifests in read-only replay, create a content-addressed backup, and prove isolated restore. Classify legacy rows without inventing history: seal only byte-matching artifacts via new migration records; quarantine missing or mismatched rows. Retain the r6 matching forensic material as evidence only.

At one coordinated cutover boundary, switch writers, validators, repair lifecycle, migration adapter, observers, and notification consumers to the same contract digest. Retire mutable-path authority and legacy effect emitters only after the cutover receipt is accepted. Rollback is whole-cutover: stop admission, preserve append-only failure evidence, restore the verified prior runtime/configuration and backup in isolation, rebuild projections, and revalidate hashes and WBC receipts.

Closure requires a frozen r6 fixture containing events 0..1948, all three receipts, admitted and drifted v2 bytes, the stopped fence-3 lease, and zero r6 repair/notification records. Under the exact cutover runtime and contract digest, prove:

- every direct, file-tool, explicit-filename, rename/link/copy-back, retry, formatter, and concurrent overwrite is rejected before admitted bytes change;
- repeated/concurrent/crash/stale-observer terminal replay resolves to exactly one repair identity, request, accepted Run Authority decision, Custody claim/epoch, WBC attempt/GLEK, child/effect, and notification intent, with at most one notification provider effect;
- recovery runs only through the ordinary fixer and supported lifecycle adapter, validates real task/result envelopes and the complete history, advances the canonical child cursor/milestone, and leaves the frozen parent byte-for-byte unchanged;
- runtime mismatch, malicious writes, stale observation, crash injection, and ambiguous delivery all fail closed; and
- the single cutover/restore receipt is accepted.

## Non-goals

- No in-place rewrite of the parent artifact, custody receipt, manifest, plan/chain state, or historical evidence.
- No attribution to or blame of any PID, process, model, agent, invocation, or tool without authoritative provenance.
- No direct state edits, hand-minted repair requests, bypass of Run Authority/Custody/WBC, same-occurrence resume, critique relaunch, or notification before verified advancement.

