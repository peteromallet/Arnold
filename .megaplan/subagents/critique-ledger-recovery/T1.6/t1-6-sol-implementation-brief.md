# GPT-5.6 Sol-high implementation — T1.6 exclusive effect custody

This is a 🔥 VERY HARD task. Start only after the T1.5 owner port and T1.1
admission authority contracts are clean candidate interfaces, with a free
mutation slot and adequate disk. Base a fresh isolated worktree on the accepted
recovery integration lineage that contains those frozen interfaces; do not fork
a second owner port from `6787d636` or use dirty/diverged main.

Read completely before editing:

- full T1.6, invariants F01/F03/F04/F06/F07/F10/F11/F12, evidence contract and
  regression list in the recovery plan;
- Luna's exact inventory and design at
  `/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.6/t1-6-sol-preparation-luna-result.md`
  (SHA-256 `0d63fe1481f051788c4191d53bf2ae4ed69126900de2cf9678c732a90f82fcfc`);
- the accepted/frozen T1.1/T1.5 interfaces and current T1.7/T1.8 candidate
  contracts. Do not silently copy or reinterpret them.

Root condition: WBC is currently optional/observational rather than exclusive.
Adapters and callers still admit shadow/synthetic authorization, arbitrary
`apply_fn`, direct provider fallthrough, environment-selected sinks, and
`exception => FAILED`; this permits an applied-but-unacknowledged effect to be
redispatched. The same pattern exists across Discord/messages/webhooks, Git/
push/PR, model/provider calls, cloud/SSH/deployment, subprocess/runners and
native/non-Megaplan pipelines.

Required end state:

1. Implement one neutral Arnold effect-custody dispatcher outside Megaplan
   policy. Every irreversible effect requires an accepted current Run Authority
   grant/revision/fence, exact Custody occurrence/lease/epoch, immutable runtime
   generation, and WBC GLEK before a durable intent is accepted. Pipeline
   adapters may add typed policy but cannot mint, downgrade or bypass authority.
2. Durable owner records cover occurrence, parent/child GLEK, request and payload
   digest, exact target/recipient/provider/repository/runtime, claim/lease/fence,
   intent-before-effect, attempt, provider request/nonce, raw response, typed
   result, receipt, ambiguity and reconciliation. One atomic singleton claim
   owns each GLEK across processes/restarts. Local labels, markers, queues,
   projections, WBC receipts, callbacks and environment never create authority.
3. Outcome classification is closed: `SUCCEEDED` only from independently
   verifiable exact provider acknowledgement; proven pre-effect rejection may be
   retryable only under domain policy; response loss, timeout, exception after
   dispatch, malformed/unknown receipt and provider-applied/ack-lost are
   `INDETERMINATE` and permanently non-redispatchable until authoritative
   reconciliation. An exception must never be collapsed to ordinary `FAILED`.
4. Derive stable child GLEKs for message chunks, multipart uploads, Git+PR,
   deployment stages and any composite effect from parent GLEK + canonical child
   index/type/target/content digest. Persist the complete child plan before any
   call. Ambiguous child state blocks only safe, explicitly modeled successors;
   no duplicate chunk/message/PR/deployment effect is possible.
5. Replace or retire every direct sink and fallback enumerated in the Luna
   inventory. Installed CLI/module/API, wrappers, resident/watchdog/auditor,
   AgentBox, native workflows and non-Megaplan pipelines must call the dispatcher
   or return typed unavailable/retired. Arbitrary `apply_fn`, monkeypatch/import,
   environment token/URL/host, exception fallback, alternate queue and direct
   library/client usage cannot reach a provider. Static inventory is enforced in
   tests and packaging.
6. Production construction requires owner-installed RA/Custody/WBC/reconciliation
   adapters, signed trust roots, runtime generation and supervised worker.
   Hermetic fakes are visibly non-production and cannot cross this constructor by
   import, path, label, environment or local receipt. Owner absence fails closed
   before intent/effect. Installed wheel/materialized runtime bind exact code,
   schemas, routes and help digests.
7. Integrate with T1.7 transactional storage and T1.8 generation identity; no
   owner store, artifact source, package installation or generation may fork.
   Provide migration/retirement for old intents and prove late legacy writers
   reject. Keep projections/read APIs rebuildable and effect-free.

Adversarial proof must cover every sink in the inventory; two threads/processes;
200 observers; crash before/after intent, claim, call, response, receipt and
reconciliation; response loss, timeout and effect-then-error; stale/forked grant,
lease, epoch, fence, runtime or GLEK; wrong target/provider/recipient/repo;
partial chunks/composites; forged/replayed/substituted receipts; ENOSPC/read/
corruption; restart; exact replay; direct/env/import/callback/queue/wrapper and
non-Megaplan bypasses; installed wheel/materialized parity; late old writers;
and production-owner absence. Prove zero calls on rejection, at most one call per
GLEK, and no redispatch of ambiguity.

Run focused, dependency-closure, concurrency/crash/fault, installed entrypoint,
wheel/materialized, static/diff/compile and exhaustive sink-inventory suites.
Large validation is single-flight and reproducible scratch is removed after
capture.

Do not contact providers/cloud, deploy, push, send messages, create PRs, or
mutate owner/runtime/checklist state. Commit scoped work, leave clean, and write
exact commit/tree/files/tests/limitations to:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.6/t1-6-sol-implementation-result.md`.
Do not claim formal completion without independent Sol review, integration, and
accepted production owner receipts.
