# T1.8 / T0 bootstrap — fenced GEN-DEPLOY Release Authority

You are the GPT-5.6 Sol high-reasoning implementer for `🔥 VERY HARD` task T1.8, brought forward as a local-only bootstrap prerequisite because the current repository has no accepted `GEN-DEPLOY` writer and T0.0 cannot lawfully install RA-CONTAIN without it.

Work only in the isolated clean worktree:

`/private/tmp/arnold-critique-recovery-gen-deploy-bootstrap-20260802`

Base commit: `6787d6363e8fc0603092913ae877db14f3b9fff8`.

Do not touch the dirty main checkout. Do not SSH, deploy, push, publish, mutate cloud, edit live selectors, restart processes, or claim an accepted owner grant. Do not wrap legacy `cloud chain --fresh`, tmux, watchdog, marker, `.pth` editing, direct copy, or arbitrary shell transport and call it authority. This lane may implement and locally prove the authority surface only.

Read completely before acting:

- `/Users/peteromalley/Documents/Arnold/docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md` (especially T1.8, T2.6, T3.1–T3.6, interface registry, concurrency rules)
- `/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/release-authority-path-research.md`
- `.megaplan/initiatives/custody-control-plane/briefs/m11-conformance-and-legacy-retirement.md`
- `docs/megaplan/final-cloud-runtime-promotion-runbook-2026-07-31.md` and related runtime/provenance/canary modules only as historical evidence; preserve useful attestations but do not inherit their authority assumptions.

Take a strong architectural position and implement the smallest complete Release Authority substrate that makes a fenced generation deployment representable, fail-closed, and independently verifiable. It must support the later full T1.8/T3 path and a narrowly scoped bootstrap installation of RA-CONTAIN without weakening the same invariants.

Required contract and implementation outcomes:

1. **Immutable generation vector.** Canonical schema/digest covering source commit/tree, image/base digest, interpreter and venv, lockfiles, installed provenance, `.pth` and imports, wrappers/services, environment/config digests, schemas/migrations, contract bundle, routes, and role-specific runtime bindings. No omitted member may be inferred from another.
2. **Owner-controlled decisions.** Typed candidate, deploy-eligibility, deployment-grant, deploy-accepted/rejected/indeterminate, rollback/forward-fix, and supersession records. Every mutation consumes exact owner identity/capability, expected selector revision/CAS, fence, generation digest, target, TTL, and idempotency identity. Caller-supplied strings are not authority.
3. **Fenced cutover transaction.** Exact sequence: verify accepted candidate and eligibility → prove old writer/effect fence → verify backup/rollback compatibility or explicit forward-fix → CAS expected old selector to new immutable generation → controlled start of only declared services → attest process birth/runtime vector → prove old PIDs/writers reject → accept or enter durable indeterminate/recovery state. No implicit reinstall/source refresh.
4. **Bootstrap without bypass.** Define how a minimal RA-CONTAIN-containing generation can be installed when no prior GEN-DEPLOY service exists. This must be an explicit one-time owner-signed bootstrap decision with stricter scope, pinned source/tree/runtime/target, expiry, offline-verifiable receipt, one-use nonce, and automatic retirement once the ordinary GEN-DEPLOY surface is live. It may not be self-issued by the model or ordinary CLI caller. Make re-use and broader target/source changes fail.
5. **Transport separation.** Authority decides; a bounded executor consumes a fully accepted envelope. No general shell string. Use typed operations/allowlisted target paths/services and an injected adapter. Provide a fake/hermetic adapter for tests. Production adapter must fail closed if absent; do not secretly implement SSH fallback.
6. **Durable custody.** Append/CAS/idempotency/concurrency/crash semantics must make duplicate mutation, split-brain selector, partial cutover, stale writer, and unknown outcome explicit. Reuse canonical repository custody/owner-store primitives if sound; otherwise add a narrow transactional store with WAL/fsync/locking and deterministic replay. Projection/log/process state never grants authority.
7. **Independent verifier.** Read-only verifier must compare installed vector to tested vector byte-for-byte, verify decision/capability/fence/CAS lineage, process executable/interpreter/import roots/`.pth`/services/routes/config, rejected old writers, and accepted rollback/forward-fix. It cannot trust the deploy actor's summary.
8. **Machine-readable CLI/API.** Provide candidate/validate/prepare-bootstrap/deploy-envelope/status/verify interfaces as appropriate. Help, schemas, exit codes, and errors are deterministic and traceback-free. Mutating commands must require real external signed owner inputs; tests use generated ephemeral keys, never repository secrets.
9. **Tests.** Add exhaustive positive/negative/fault tests: manifest omission/tamper, signature/capability/TTL/scope failures, stale CAS, duplicate/divergent idempotency, two deployers racing, crash at every cutover boundary, old writer still alive, vector mismatch, rollback incompatibility, missing production adapter, bootstrap nonce reuse, bootstrap scope expansion, restart/replay, and independent verifier disagreement. Include installed-entrypoint/API tests with a hermetic target.
10. **Legacy retirement.** No new code may treat the old cloud skill/runbook, tmux, markers, watchdogs, editable source, or process existence as deployment authority. Add deterministic tests/search assertions where appropriate.

Use `apply_patch` for edits. Keep changes cohesive and production-readable. Run focused and broader relevant tests, repeat race/fault paths, run `git diff --check`, and inspect the final diff for accidental legacy authority. Commit the implementation as one or more intentional commits on this branch; do not push.

Write the final handoff to:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.8/gen-deploy-bootstrap-sol-result.md`

The handoff must state exact commits, schemas/interfaces, test commands/results, known integration points, and the precise owner artifact still required before any bootstrap/deploy can occur. Do not check T1.8 complete: incident evidence T0.2, independent review, integration, and accepted owner/cloud receipts remain future gates.
