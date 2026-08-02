# Critique Ledger Recovery TODO: Root Fix, Cloud Deployment, and Durable Epic Restart

**Date:** 2026-08-02

**Status:** Active execution checklist; current recovery gate is **NO-GO**

**Incident session:** `critique-ledger-accountability-v2-20260728`

**Blocked plan:** `cl2-wbc-backed-ledger-20260731-1411`

**Epic:** Critique Loop / Cumulative Finding Ledger (`critique-ledger`)

## Task-list UX

This section is the operating surface. The incident analysis, design rationale,
full runbook, tests, and evidence index below are supporting reference.

### How to use this checklist

- Work top to bottom. Do not start a task whose dependencies are unchecked.
- `[ ]` means not proven, even if code appears to exist. `[x]` requires an
  accepted evidence link/hash in the task's evidence line.
- `— **BLOCKED**` after an unchecked item means its required authoritative
  interface or prerequisite does not yet exist.
- Every mutating task names its authority. A model, shell session, tmux process,
  commit, queue row, log, or status projection cannot grant permission.
- Keep the old v2 incident immutable. This checklist creates a fenced recovery
  generation and an entirely fresh v3 successor.
- Update **Current next action** whenever a checkbox changes. There must be only
  one next mutating action.

### Current dashboard

| Outcome | State | Proof required to turn green |
| --- | --- | --- |
| Root cause understood | **documented; not owner-accepted** | signed evidence manifest plus accepted incident finding receipt |
| Nested Sol → Luna delegation | **PASS; durably receipted** | `.megaplan/subagents/critique-ledger-recovery/delegation-smoke/sol-to-luna-gpt56-pass4-receipt.json` (`3353bc0bc3942c342e089ad6b146d75efc18d96193612c08600edf6e311cd302`) binds parent/child transcript hashes and model/runtime identities |
| Incident contained | **not proven; off-volume evidence verified** | old mutation/effects frozen |
| Root fixes implemented | **implementation in progress; not accepted** | T1 tasks and installed-entrypoint tests accepted |
| Recovery candidate deployable | **blocked** | T2.6 candidate-deploy-eligible receipt plus accepted `GEN-DEPLOY` interface |
| Recovery generation deployed and accepted | **not started** | T3.6 exact installed receipt and both release tickets independently closed |
| Poisoned v2 run fenced | **not started** | Run Authority/Custody/WBC/CAS receipts |
| Fresh CL2 successor running | **blocked** | T0–T5 complete and authorized launch transaction accepted |
| Epic producing work | **not started** | accepted CL2 finalize/execute receipts and feature commits |
| Epic deployed and working | **not started** | ordinary push/PR/merge/deployment receipts plus post-deploy canary |

**Current next action:** T0.0 — obtain and record the exact Run Authority
containment decision/interface for the poisoned tuple. T0.1 is blocked until
that decision exists; do not improvise containment with shell/tmux/marker edits.

### Completion evidence format

For every checked task, append a line in this form:

```text
Evidence: <owner> | <accepted receipt ID> | <artifact URI/path> |
SHA-256 <digest> | captured <UTC> | runtime/generation <digest>
```

Do not check a task based on “tests passed,” “commit exists,” “process is
running,” or “status says done” without the named owner's accepted receipt.

### Interface and evidence registry

The task table uses these interface names:

- `DEV-PR`: isolated implementation worktree/branch and review PR under a
  repo-scoped implementation grant; the task manifest records exact edit/test
  commands and touched paths. It carries no cloud authority.
- `READ-ATTESTED`: read-only commands invoked through the generation's exact
  `RUNTIME_PYTHON -P`; outputs are hashed into the evidence directory.
- `RA-CONTAIN`, `RA-FENCE`, `CUSTODY-FENCE`, `WBC-RECONCILE`,
  `GEN-DEPLOY`, `LAUNCH-TXN`, `STOP-TXN`, and `PRODUCT-DEPLOY`:
  authoritative mutation interfaces. Any one not delivered and accepted by the
  recovery release is **BLOCKED**; shell/tmux/marker/queue fallbacks are forbidden.
- `VERIFY`: independent verifier reading frozen owner evidence; the repair,
  launch, or deployment actor cannot self-verify.

`E/` below means `evidence/critique-ledger-recovery/`. Every destination holds a
signed `completion-manifest.json` with all child receipts for composite tasks.

| Task | Depends on | Assignee / owner | Mutation and grant | Interface | Evidence destination |
| --- | --- | --- | --- | --- | --- |
| T0.0 | none | Incident commander + Run Authority | yes; containment decision | `RA-CONTAIN` — **BLOCKED until named** | `E/T0.0/` |
| T0.1 | T0.0 | Run Authority + WBC | yes; containment grant | `RA-CONTAIN` | `E/T0.1/` |
| T0.2 | T0.1 | Evidence custodian | evidence writes only | `READ-ATTESTED` + off-volume writer | `E/T0.2/` |
| T0.3 | T0.2 | Cloud-storage owner | yes; per-target cleanup grant | approved cleanup manifest — **BLOCKED until named** | `E/T0.3/` |
| T0.4 | T0.2 | Incident projector owner | projection/evidence only | `READ-ATTESTED` | `E/T0.4/` |
| T1.1 | T0.2 | Admission domain + Run Authority | repo only; implementation grant | `DEV-PR` | `E/T1.1/` |
| T1.2 | T1.3 interface freeze | Critique domain | repo only; implementation grant | `DEV-PR` | `E/T1.2/` |
| T1.3 | T0.2 | Contract-bundle + release owners | repo only; implementation grant | `DEV-PR` | `E/T1.3/` |
| T1.4 | T1.1 | Planning domain + Run Authority | repo only; implementation grant | `DEV-PR` | `E/T1.4/` |
| T1.5 | T0.2 | M11 recovery owner | repo only; implementation grant | `DEV-PR` | `E/T1.5/` |
| T1.6 | T0.2 | WBC + integration owners | repo only; implementation grant | `DEV-PR` | `E/T1.6/` |
| T1.7 | T0.2 | Owner-store + cloud-storage owners | repo only; implementation grant | `DEV-PR` | `E/T1.7/` |
| T1.8 | T0.2 | Release Authority implementation owner | repo only; implementation grant | `DEV-PR` | `E/T1.8/` |
| T1.9 | T1.5, T1.6, T1.8 | Run Authority + Custody + WBC + cloud launcher | repo only until isolated canary | `DEV-PR`; produces `LAUNCH-TXN`/`STOP-TXN` | `E/T1.9/` |
| T1.10 | T1.5, T1.6 | Incident UX + WBC delivery owners | repo only; implementation grant | `DEV-PR` | `E/T1.10/` |
| T2.1 | T0.4 | Run Authority | yes; superseding decision | `RA-FENCE` decision surface | `E/T2.1/` |
| T2.2 | T1.1–T1.10 | Release owner | isolated evidence only | `READ-ATTESTED` + candidate suite | `E/T2.2/` |
| T2.3 | T2.2 | Canary owner + verifier | isolated evidence only | candidate `admit/run/verify` | `E/T2.3/` |
| T2.4 | T2.5 | Acceptance-suite owner | isolated fault effects only | `READ-ATTESTED` suite runner | `E/T2.4/` |
| T2.5 | T2.3 | Routing domain + WBC | provider calls under canary grant | WBC route-canary surface | `E/T2.5/` |
| T2.6 | T2.1–T2.5 | Release Authority + verifier | yes; candidate decision | deploy-eligibility decision surface | `E/T2.6/` |
| T3.1 | T2.6 | Cloud-storage + evidence owners | read/evidence only | `READ-ATTESTED` | `E/T3.1/` |
| T3.2 | T3.1 | Run Authority + WBC | yes; deployment fence | `RA-FENCE` + WBC effect denial | `E/T3.2/` |
| T3.3 | T3.2 | Release Authority | yes; deployment grant | `GEN-DEPLOY` — **BLOCKED until accepted** | `E/T3.3/` |
| T3.4 | T3.3 | Independent verifier | no production mutation | `VERIFY` + `READ-ATTESTED` | `E/T3.4/` |
| T3.5 | T3.4 | Recovery/canary owners + verifier | bounded canary effects | accepted canary interfaces | `E/T3.5/` |
| T3.6 | T3.5 | Release Authority + verifier | yes; final release/ticket decisions | accepted release decision surface | `E/T3.6/` |
| T4.1 | T0.4, T3.6 | Run Authority | yes; exact-tuple quarantine | `RA-FENCE` | `E/T4.1/` |
| T4.2 | T4.1 | Run Authority | yes; revoke old actions | `RA-FENCE` | `E/T4.2/` |
| T4.3 | T4.2 | Custody owner | yes; advance fence/epoch | `CUSTODY-FENCE` | `E/T4.3/` |
| T4.4 | T4.3 | WBC owner | yes; reconcile/no-redispatch | `WBC-RECONCILE` | `E/T4.4/` |
| T4.5 | T4.2–T4.4 | Chain-selection owner | yes; selection CAS | `RA-FENCE` selection CAS | `E/T4.5/` |
| T4.6 | T4.5 | Evidence custodian | permissions/evidence mutation | approved evidence-freeze surface | `E/T4.6/` |
| T5.1 | T0.2 | CL1 domain owners | source/evidence decisions | domain acceptance interfaces | `E/T5.1/` |
| T5.2 | T1.1, T1.3, T3.6, T5.1 | CL1 domain + verifier | evidence writes only | raw predicate + `VERIFY` | `E/T5.2/` |
| T5.3 | T4.6, T5.2 | Critique Ledger implementation owner | repo only; implementation grant | `DEV-PR` | `E/T5.3/` |
| T5.4 | T5.3 | Run Authority/Custody/WBC/Git owners | identity allocation; no launch | accepted identity-allocation surfaces | `E/T5.4/` |
| T5.5 | T5.4 | Release/operator verifier | read-only | R4 `READ-ATTESTED` commands | `E/T5.5/` |
| T5.6 | T5.5 | Run Authority + verifier | grant preparation only | `LAUNCH-TXN` envelope builder | `E/T5.6/` |
| T6.1 | T1.9, T3.6, T4.6, T5.6 | Run Authority/Custody/WBC launcher | yes; scoped launch grant | `LAUNCH-TXN` — **BLOCKED until installed** | `E/T6.1/` |
| T6.2 | T6.1 | Independent verifier + Run Authority | verification then grant expansion | `VERIFY` + `RA-FENCE` | `E/T6.2/` |
| T6.3 | T6.2 | Megaplan domain | bounded model/repair effects | ordinary owner interfaces | `E/T6.3/` |
| T6.4 | T6.3 | Execute owner + verifier | code execution under grant | ordinary Run Authority/Custody/WBC | `E/T6.4/` |
| T6.5 | T6.4 | Git/WBC publication owner | push/PR effects | WBC publication interface | `E/T6.5/` |
| T6.6 | T6.5 | Chain owner + verifier | milestone actions under grants | ordinary chain owner interfaces | `E/T6.6/` |
| T7.1 | T6.6 | Git/Run Authority owners | merge effect | WBC publication interface | `E/T7.1/` |
| T7.2 | T7.1 | Product release owner | build/evidence writes | product generation builder | `E/T7.2/` |
| T7.3 | T7.2 | Product Release Authority | yes; product deploy grant | `PRODUCT-DEPLOY` — **BLOCKED until named** | `E/T7.3/` |
| T7.4 | T7.3 | Product verifier | bounded production canary effects | accepted product canary interfaces | `E/T7.4/` |
| T7.5 | T7.4 | Independent production verifier | observation/evidence only | `VERIFY` | `E/T7.5/` |
| T8.1 | T7.5 | Chain owner + verifier | evidence writes only | completion-manifest generator | `E/T8.1/` |
| T8.2 | T8.1 | Run Authority + incident owner | yes; incident closure | accepted closure decision | `E/T8.2/` |
| T8.3 | T7.5 | Release-gate owner | repo/test mutation | `DEV-PR` | `E/T8.3/` |
| T8.4 | T7.5 | Incident UX owner | docs/config mutation | `DEV-PR` | `E/T8.4/` |
| T8.5 | T8.2–T8.4 | Independent verifier + Run Authority | observation then final closure | `VERIFY` + closure decision | `E/T8.5/` |

### Parallel execution plan

`🔥 VERY HARD` marks tasks with high cross-owner, migration, concurrency,
ambiguity, or production-blast-radius risk. Give them the strongest implementer
and an independent reviewer; do not equate more agents with faster completion.

Concurrency rules:

- Run at most four mutating code lanes at once, each in an isolated worktree
  with disjoint declared ownership. Read-only/evidence work may run alongside.
- One integrator owns shared contracts. Freeze interface digests before a
  downstream lane codes against them; never let two lanes independently invent
  the same schema or authority transition.
- Only one authoritative validation process runs at a time. Parallel test
  shards are allowed for disposable prechecks, but the release acceptance run
  is exclusive, hermetic, and uses the frozen exact inventory.
- Serialize mutations to the same Run Authority revision, Custody occurrence,
  WBC attempt/GLEK, chain selection, runtime generation, or product target.
- Generation deployment, cloud process cutover, v2 fencing, first-transition
  launch canary, publication, and product deployment are single-flight.

| Wave | Can run together | Join/exit condition |
| --- | --- | --- |
| W0 — containment | T0.0 → T0.1 → T0.2 are sequential | effects denied and evidence copied off-volume |
| W1 — first fan-out | T0.3; T0.4 → T2.1; T1.1; T1.3; T1.5; T1.7; T1.8; early T5.1 raw-blocker inventory/resolution | preserved incident plus initial owner interfaces frozen |
| W2 — dependent code lanes | T1.2 after T1.3; T1.4 after T1.1; T1.6 against frozen M11/WBC interfaces | contract and authority suites pass per lane |
| W3 — integration | T1.9 and T1.10 may run together after T1.5/T1.6; one integrator resolves shared surfaces | one clean candidate lineage and no duplicate owner |
| W4 — candidate proof | disposable prechecks for T2.2/T2.3/T2.5 may fan out; authoritative evidence is rerun and frozen serially as T2.2 → T2.3 → T2.5 → exclusive T2.4 | T2.6 deploy-eligible decision |
| W5 — cloud release | T3.1 → T3.2 → T3.3 → T3.4 → T3.5 → T3.6 strictly serial | exact installed release receipt and both tickets closed |
| W6 — poisoned-run retirement | T4.1 → T4.2 → T4.3 Custody fence/late-writer proof → T4.4 WBC reconciliation/no-redispatch → T4.5 → T4.6; use one joined transaction only if its cross-owner saga is accepted | every late v2 writer/effect rejects |
| W7 — successor preparation | T5.1 began in W1; after T1.1/T1.3 and T3.6, run authoritative T5.2, then T5.3 → T5.4 → T5.5 → T5.6 | scoped launch envelope independently verified |
| W8 — first launch | T6.1 → T6.2 strictly serial; keep authority scoped to one transition | verifier accepts real forward movement |
| W9 — epic work | T6.3 → T6.4 → T6.5; milestones in T6.6 remain dependency-ordered, not parallel | CL2–CL5 manifests and ordinary publication receipts |
| W10 — product release | T7.1 → T7.2 → T7.3 → T7.4 → T7.5 strictly serial | production canary window accepted |
| W11 — closure fan-out | after T7.5, T8.1, T8.3, and T8.4 may run together; T8.2 then T8.5 close | 24h/72h/7d verification accepted |

Fastest safe critical path:

```text
T0.0 → T0.1 → T0.2
  → [W1/W2 root-fix fan-out]
  → T1.9 → T2.2 → T2.3 → T2.5 → T2.4 → T2.6
  → T3.1…T3.6
  → [T4.1…T4.6 || authoritative T5.2 after T3.6]
  → T5.3…T5.6
  → T6.1…T6.6
  → T7.1…T7.5
  → T8.2 → T8.5
```

Efficiency comes from starting CL1 blocker resolution, M11 invalidation,
storage recovery, and disjoint root-fix lanes immediately after the evidence
snapshot—not from overlapping authority-changing deployment operations.

## Master execution checklist

### T0 — Contain and preserve before fixing

Owner: Incident commander plus Run Authority/Custody/WBC/cloud-storage owners.

- [ ] **T0.0 Record the canonical incident-containment decision.** — **BLOCKED**
  - Name the exact Run Authority interface and decision type that can deny all
    new effects for the poisoned tuple while preserving reads.
  - If that interface does not exist, authorize a minimal containment release;
    do not substitute a shell kill, tmux command, marker edit, or queue rewrite.
  - Mutation: yes; only an accepted Run Authority incident decision may write.
  - Done when: decision ID, scope, TTL/termination, and revoke/audit path exist.
  - Evidence: `evidence/critique-ledger-recovery/T0.0/`.

- [ ] **T0.1 Freeze the poisoned session's effects.** — **BLOCKED by T0.0**
  - Block new repair, execute, notify, publish, and deployment effects for
    session `critique-ledger-accountability-v2-20260728`.
  - Preserve read-only observation.
  - Do not edit markers, kill tmux, clear `manual_review`, or delete state as a
    substitute for authoritative containment.
  - Done when: owner queries prove zero current mutation/effect authority.
  - Evidence: `evidence/critique-ledger-recovery/T0.1/`.

- [x] **T0.2 Capture the off-volume evidence manifest.**
  - Hash the old session, spec, workspace, plan, chain state, events, model raw
    outputs, critique attempts, finalizer candidates, repair records, runtime
    vector, notification receipts, disk facts, Git state, and provider facts.
  - Each claim records path/URI, digest, size, capture time, collector version,
    clock basis, runtime/commit, and minimal query/excerpt.
  - Done when: the manifest verifies from an independent filesystem.
  - Evidence: root independent verifier | `T0.2-C45030BD-20260802T143207Z` |
    `evidence/critique-ledger-recovery/T0.2/manifest.json` |
    SHA-256 `c45030bd29c57d1eb0d1694c705aebb3dd55ca04fa3b612ad0d287e32e4dc791` |
    captured `2026-08-02T14:24:00Z`; verified `2026-08-02T14:32:07Z` |
    collector runtime `t02-off-volume-collector/1.0`, local commit
    `36a10988717f9dfb0ab31d49baf05cc89bcfa989`.
  - Verification: 319 claims, 230 unique objects, 83,611,704 unique bytes,
    zero hash failures, three explicit unavailable/blocked records. Independent
    credential scan found no credential material; its sole lexical hit was the
    non-secret filename substring `task-contract-...`.

- [ ] **T0.3 Restore safe control-plane capacity.** — 🔥 **VERY HARD**
  - Obtain a cloud-storage/cleanup grant bound to an explicit per-target
    cleanup manifest. Verify the off-volume copy independently first.
  - Prefer recoverable moves and policy-backed retention. Abort on target,
    digest, mount, or scope drift; no broad recursive cleanup is authorized.
  - Recover bytes and inodes only after T0.2.
  - Validate authoritative stores, SQLite/WAL or equivalent indexes, fsync,
    checkpoint, backup restore, and unknown provider outcomes.
  - Install byte/inode reserve watermarks that stop effects before intent or
    receipt persistence is unsafe.
  - Done when: storage admission and ENOSPC fault receipts pass.
  - Evidence: `evidence/critique-ledger-recovery/T0.3/`.

- [x] **T0.4 Publish one authoritative incident inventory.**
  - Join, without replacing, Run Authority, Custody, WBC, plan, runtime,
    notification, storage, and verifier records.
  - List every old grant, fence, lease, epoch, occurrence, GLEK, branch,
    worktree, marker, process, publication intent, and ambiguous provider effect.
  - Done when: every later fence/reconciliation task has an exact target.
  - Evidence: root independent verifier | `t04-receipt-2984a983ae7a307d02b6d36c` |
    `evidence/critique-ledger-recovery/T0.4/inventory.json` |
    SHA-256 `2984a983ae7a307d02b6d36cb53ab42122e5d9ad63d5d5eb0ff8d0c89ff5bff8` |
    captured and verified `2026-08-02T14:52:30Z` | source manifest
    `c45030bd29c57d1eb0d1694c705aebb3dd55ca04fa3b612ad0d287e32e4dc791`.
  - Verification: 342 unique rows/targets, 389 source references rehashed,
    all T4.1–T4.6 actions mapped, 14 unresolved records explicitly
    fail-closed, zero credential-pattern hits.

### T1 — Implement the root fixes on one clean lineage

Owner: Megaplan domain, Run Authority, Custody, WBC, storage, and release owners
as named below. No cloud promotion in this phase.

- [ ] **T1.1 Make CL2 admission derive from raw evidence.** — 🔥 **VERY HARD**
  - Owner: Megaplan domain plus Run Authority.
  - Implement versioned, allowlisted, target-bound predicate derivation from raw
    hashed CL1 evidence.
  - Re-evaluate under fence immediately before plan creation.
  - Make false, missing, stale, wrong-target, unknown, or throwing predicates
    reject. Auto-approval cannot absorb machine prerequisites.
  - Done when: all admission and two-initializer CAS tests pass through installed
    entrypoints.
  - Evidence: _pending_.

- [ ] **T1.2 Separate critique attempt health from semantic results.** — 🔥 **VERY HARD**
  - Owner: critique domain.
  - Implement attempt states `SUCCEEDED`, `PROVIDER_FAILED`,
    `PRODUCER_CONTRACT_FAILED`, `PARSER_FAILED`, `SANDBOX_FAILED`, `CANCELLED`.
  - Emit `FINDING`, `NO_FINDING`, or policy-scoped
    `EXTERNAL_UNVERIFIABLE` only after `SUCCEEDED`.
  - Bind an exact lens-selection manifest and require every mandatory lens at
    thorough/high robustness.
  - Done when: six failed critics cannot become admitted zero findings.
  - Evidence: _pending_.

- [ ] **T1.3 Ship immutable producer/consumer contract bundles.**
  - Owner: Megaplan domain plus release owner.
  - Bind prompt, transport/capture schema, parser ABI, normalizer, semantic
    validator, fixtures, and provider assumptions by content digest.
  - Forbid required-field synthesis/discard and mutable `latest` lookup.
  - Permit one invalid-pointer-only repair in the same object/bundle, followed
    by full revalidation.
  - Done when: repair cannot alter valid fields or change bundles.
  - Evidence: _pending_.

- [ ] **T1.4 Route deterministic graph rejection to one narrow repair.**
  - Owner: planning/finalizer domain plus Run Authority.
  - Emit typed `planner_repair_required` with stable semantic fingerprint.
  - Keep fingerprint/budget with domain policy, occurrence with Custody, effect
    attempts with WBC, and transition acceptance with Run Authority.
  - Forbid execute/publish while graph admission is rejected.
  - Done when: prose/model/restart changes cannot reset the domain budget.
  - Evidence: _pending_.

- [ ] **T1.5 Replace recovery loops with binding M11 `simple_fixer`.** — 🔥 **VERY HARD**
  - Owner: M11 recovery owner.
  - One durable occurrence, immediate non-agent trigger, singleton
    `simple_fixer`, at most one canonical runner, three-hour missed-event
    reconciler using the same occurrence claim.
  - Invalid identity is terminal non-claimable intake plus a linked obligation;
    it is never queued work.
  - Remove watchdog, L1/L2/L3 investigator, meta-repair, repair-loop,
    periodic-audit-agent, and managed-child recovery authority.
  - Done when: immediate/delayed triggers converge and fixer failure creates no
    child or alternative scheduler.
  - Evidence: _pending_.

- [ ] **T1.6 Close every production effect boundary through WBC.** — 🔥 **VERY HARD**
  - Owner: WBC plus integration owners.
  - Require current Run Authority grant/fence, Custody lease/epoch, and WBC GLEK
    before Discord, webhook, Git, PR, model, cloud, or deployment effects.
  - Remove direct fallback, shadow/synthetic authorization, and fake success.
  - Represent provider-applied/ack-lost as `INDETERMINATE`; prohibit resend.
  - Derive stable child GLEKs for message chunks.
  - Done when: bypass and ambiguity tests prove zero calls or no redispatch.
  - Evidence: _pending_.

- [ ] **T1.7 Make owner-local storage crash/concurrency safe.** — 🔥 **VERY HARD**
  - Owner: owner-store and cloud-storage owners.
  - Replace whole-file JSONL rewrite and unsafe sequence derivation.
  - Treat read error as error, never empty authority.
  - Isolate canonical stores from logs/artifacts/projections; make projections
    disposable and bounded.
  - Done when: concurrent writer, crash, WAL/fsync, byte/inode, corrupt
    projection, and large-journal tests pass.
  - Evidence: _pending_.

- [ ] **T1.8 Implement a fenced generation migration.** — 🔥 **VERY HARD**
  - Owner: Release Authority.
  - Manifest source tree, image/base, interpreter/venv, locks, installed
    provenance, `.pth`/imports, wrappers, services, environment, schemas,
    migrations, contract bundle, and routes.
  - Fence old writers/effects before CAS switch; attest live PIDs and reject old
    writers after switch.
  - Test backup restore and migration-compatible rollback or forward-fix.
  - Done when: installed vector equals tested vector byte for byte.
  - Evidence: _pending_.

- [ ] **T1.9 Implement the missing authorized launch/stop transaction.** — 🔥 **VERY HARD**
  - Owner: Run Authority, Custody, WBC, cloud launcher, and Release Authority.
  - This is the current critical code blocker.
  - Consume launch seed, grant/revision/fence, occurrence/lease/epoch, WBC
    attempt/intent, runtime generation, absence/collision proof, and scoped TTL.
  - Start at most one canonical runner with no runtime/source refresh and no
    watchdog tracking.
  - Ship a pre-issued revoke/fence/stop capability for the same identity.
  - Fail on collisions; never reset/delete them. Do not wrap current
    `cloud chain --fresh` and call it compliant.
  - Done when: installed CLI/API contract, negative tests, help digest, and
    isolated/non-production contract canary receipts exist. Production launch
    evidence belongs to T3/T6.
  - Evidence: _pending_.

- [ ] **T1.10 Make incident/notification UX quiet and useful.**
  - Owner: incident projection and WBC delivery owners.
  - Create incident and diagnostic identity before provenance validation.
  - Show one current incident card with state, owner, last accepted transition,
    fixer result, ambiguity, storage health, runtime generation, and next action.
  - Notify only on meaningful state-version transitions or a genuine human
    decision; repeated observation updates the card without sending another DM.
  - Include acknowledgement/resolution controls backed by authority, not UI
    booleans.
  - Done when: two observers and 200 identical scans produce at most one
    accepted notification outcome.
  - Evidence: _pending_.

### T2 — Prove the recovery candidate before cloud mutation

Owner: Release Authority and independent verifier.

- [ ] **T2.1 Invalidate the prior M11 completion/promotion claim.**
  - Append a superseding Run Authority decision; do not rewrite history.
  - Record why direct effects, shadow authorization, recovery topology, and
    deployed-canary gaps invalidate promotion evidence.
  - Evidence: _pending_.

- [ ] **T2.2 Complete offline candidate evidence for release ticket `01KYSBGRHM1S8R6RQ1DGZ7843Y`.**
  - Produce the frozen no-debt inventory and exact-revision candidate evidence.
  - Keep the ticket open: its production/runtime acceptance closes only at T3.6.
  - Evidence: _pending_.

- [ ] **T2.3 Complete the isolated deployed-canary implementation for ticket `01KYVJ7A47TMH4BRGEV9JFTK10`.**
  - Prove its `admit`, `run`, and independent `verify` contract in isolated
    scope. Keep the ticket open until the exact installed T3 canary succeeds.
  - Evidence: _pending_.

- [ ] **T2.4 Run the complete installed-entrypoint replay/fault suite.** — 🔥 **VERY HARD**
  - Cover admission, critique, graph repair, every torn Run
    Authority/Custody/WBC order, recovery triggers, provider ambiguity, partial
    chunks, concurrency, ENOSPC, generation migration, old-writer rejection,
    successor isolation, Git/PR ack loss, and independent closure.
  - Use the named regression list later in this document.
  - Evidence: _pending_.

- [ ] **T2.5 Prove every configured model route is contract-compatible.**
  - Owner: model-routing domain plus WBC.
  - For every allowed tier, verify exact model availability/auth, request and
    response transport, capture schema, truncation/termination, immutable
    parser/normalizer bundle, timeout, and provider ambiguity handling.
  - A failed route becomes inadmissible, never `NO_FINDING`. Fallback is a fresh
    pre-approved attempt under the same owner budgets.
  - Evidence: `evidence/critique-ledger-recovery/T2.5/`.

- [ ] **T2.6 Approve a deploy-eligible zero-blocker ownership/M11 candidate decision.**
  - Require complete contract portfolio, zero bypass scan, proof map,
    content-addressed completion manifest, rollback/forward-fix evidence, and
    independent approval.
  - This authorizes the controlled T3 canary deployment, not epic launch.
  - Done when: mutation gate changes from NO-GO to candidate-deploy-eligible.
  - Evidence: _pending_.

### T3 — Deploy the approved recovery generation to the cloud machine

Owner: Release Authority; mutation requires a separate accepted deployment
grant.

- [ ] **T3.1 Re-run T0 storage and evidence checks immediately before deploy.**
  - Abort on changed hashes, unhealthy stores/WAL, insufficient byte/inode
    reserve, or unresolved effect ambiguity outside policy.
  - Evidence: _pending_.

- [ ] **T3.2 Fence old writers and effects.**
  - Verify no process can mutate while generation CAS is in flight.
  - Evidence: _pending_.

- [ ] **T3.3 Promote the exact tested generation.** — 🔥 **VERY HARD**
  - Use only the newly accepted Release Authority deployment surface.
  - Do not reinstall opportunistically, refresh editable source, or use legacy
    cloud/watchdog deployment commands.
  - Execute one explicit cutover atom: expected-old selector digest → generation
    CAS → controlled restart of the exact canonical services → process-birth
    and runtime-vector receipts → old PID/writer rejection.
  - Bind a rollback token or explicit forward-fix decision before CAS. Legacy
    watchdog/resident restart commands are forbidden.
  - Evidence: _pending_.

- [ ] **T3.4 Attest the live cloud vector.**
  - Independently read PIDs, executable, interpreter, imports, `.pth`, source
    tree, wrappers/services, schemas, contract bundle, routes, and config.
  - Compare with the generation manifest byte for byte.
  - Evidence: _pending_.

- [ ] **T3.5 Run production recovery and rollback canaries.**
  - Immediate trigger and missed-event reconciler share one fixer occurrence.
  - Old writers reject; effects require WBC; backup restore works; rollback is
    compatible or forward-fix is proven.
  - Evidence: _pending_.

- [ ] **T3.6 Independently close both release tickets and issue the exact-revision release receipt.**
  - Run the exact installed `admit`, `run`, and independent `verify` scenarios.
  - Close `01KYSBGRHM1S8R6RQ1DGZ7843Y` and
    `01KYVJ7A47TMH4BRGEV9JFTK10` only when all their production obligations are
    re-derived from frozen owner evidence.
  - Issue the final zero-blocker M11/release receipt required by T4–T6.
  - Evidence: `evidence/critique-ledger-recovery/T3.6/`.

### T4 — Permanently fence the poisoned v2 epic

Owner: Run Authority, Custody, WBC, chain selection owner.

- [ ] **T4.1 Supersede/quarantine the exact v2 selection/session/spec/workspace/plan/branch/runtime tuple.** — 🔥 **VERY HARD**
  - Evidence: _pending_.
- [ ] **T4.2 Revoke old grants and make `resume/repair/execute/publish/notify` inadmissible.**
  - Evidence: _pending_.
- [ ] **T4.3 Revoke/expire old leases under an advanced fence/epoch; never plain-release or reuse the target key.**
  - Prove every late v2 writer rejects before any successor lease is issued.
  - Evidence: _pending_.
- [ ] **T4.4 Reconcile old GLEKs; preserve `INDETERMINATE` as unresolved and no-redispatchable.**
  - Evidence: _pending_.
- [ ] **T4.5 CAS chain selection away from v2 and project `should_run=false` without editing its marker.**
  - Evidence: _pending_.
- [ ] **T4.6 Freeze old workspace/branch/worktree/plan/artifacts as read-only evidence.**
  - Evidence: _pending_.

### T5 — Build and admit an entirely fresh v3 successor

Owner: Critique Ledger domain plus Run Authority.

- [ ] **T5.1 Resolve the raw CL1 reviewer/coherence/proof/ownership/portfolio blockers.**
  - Evidence: _pending_.
- [ ] **T5.2 Regenerate and independently recompute the target-bound CL1 handoff.**
  - Evidence: _pending_.
- [ ] **T5.3 Commit a new v3 initiative, North Star, briefs, chain spec, cloud spec, and completion preconditions.**
  - Copy no generated state, budget, GLEK, notification ID, mutable artifact, or
    old branch/worktree/PR identity.
  - Evidence: _pending_.
- [ ] **T5.4 Allocate fresh launch identity and publication namespace.**
  - WBC derives GLEKs; the provider-assigned PR identity is recorded only after
    its effect receipt.
  - Evidence: _pending_.
- [ ] **T5.5 Run attested-runtime local preflight and read-only remote dependency probe.**
  - Use R4 below; absence/collision checks are performed by the new launch
    transaction, not by deleting existing state.
  - Evidence: _pending_.
- [ ] **T5.6 Prepare and independently verify the scoped one-transition canary envelope.**
  - Bind the grant scope, TTL, launch seed, occurrence, expected first
    transition, stop capability, and verifier query. Do not launch or transition
    yet; T6.1 launches and T6.2 proves the transition.
  - Evidence: _pending_.

### T6 — Launch and durably move the epic

Owner: Run Authority/Custody/WBC launch transaction and independent verifier.

- [ ] **T6.1 Launch through the new M11-authorized transaction.** — 🔥 **VERY HARD** — **BLOCKED**
  - Blocked by: T1.9 and all preceding tasks.
  - Do not use current `cloud chain --fresh`, raw `chain start`, tmux,
    `launch-epic`, marker edits, or watchdog relaunch.
  - Replace this blocked label only when the installed command/API syntax and
    contract digest have been added to R6 below.
  - Evidence: _pending_.

- [ ] **T6.2 Verify the first accepted CL2 transition before expanding authority.**
  - Check owner records, not status/log prose.
  - Evidence: _pending_.

- [ ] **T6.3 Run ordinary plan → critique → gate → finalize.**
  - Require exact critique completeness.
  - If graph admission rejects, permit one authority-accepted narrow repair for
    the same occurrence; forbid implementation dispatch until admitted.
  - Evidence: _pending_.

- [ ] **T6.4 Execute CL2 and prove real feature work.** — 🔥 **VERY HARD**
  - Require accepted execute receipts, feature commits, current dependency
    closure, and authoritative chain cursor advancement.
  - Evidence: _pending_.

- [ ] **T6.5 Publish through ordinary WBC custody.**
  - Durable publication intent precedes push/PR effect.
  - Provider acknowledgement ambiguity becomes `INDETERMINATE`; do not create a
    second PR.
  - Evidence: _pending_.

- [ ] **T6.6 Advance CL3–CL5 from predecessor completion manifests.** — 🔥 **VERY HARD**
  - Check each milestone at first transition, 10–15 minutes, boundary, and
    authority expansion.
  - Evidence: _pending_.

### T7 — Deploy the Critique Ledger work and prove it works

Owner: product Release Authority and independent production verifier.

- [ ] **T7.1 Accept and merge the successor implementation PR through ordinary publication custody.**
  - Evidence: _pending_.
- [ ] **T7.2 Build a content-addressed product deployment generation.**
  - Bind implementation source, migration, config, runtime, contract bundle,
    fixtures, rollback/forward-fix, and target environment.
  - Evidence: _pending_.
- [ ] **T7.3 Deploy with old product writers/effects fenced.** — 🔥 **VERY HARD** — **BLOCKED**
  - Name the exact installed product Release Authority API/command, contract and
    help digest, rollback token, and stop capability—or explicitly prove the
    accepted T3 generation transaction is the product deployment owner.
  - Epic launch, merge, process liveness, or a generic deployment script does
    not authorize product deployment.
  - Evidence: _pending_.
- [ ] **T7.4 Run real production acceptance scenarios.** — 🔥 **VERY HARD**
  - Valid critics produce exact-set findings/no-findings.
  - Failed critic attempts block clean critique.
  - Findings persist/replay correctly across rounds and restart.
  - Reconciliation/gate consumes every disposition exactly once.
  - One induced eligible failure invokes one `simple_fixer` occurrence.
  - Two hundred unchanged observations send no duplicate notification.
  - Provider ambiguity and ENOSPC fail closed without resend or lost authority.
  - Evidence: _pending_.
- [ ] **T7.5 Observe for the declared canary window and independently accept.**
  - No old writer/effect path, duplicate incident, stalled authority, projection
    disagreement, or storage reserve breach.
  - Evidence: _pending_.

### T8 — Close the incident and institutionalize the prevention

Owner: Run Authority plus incident owner.

- [ ] **T8.1 Generate the final successor completion manifest and proof map.**
  - Evidence: _pending_.
- [ ] **T8.2 Mark the v2 incident resolved only after v3/product verification.**
  - Preserve v2 as immutable evidence; do not rewrite it as completed.
  - Evidence: _pending_.
- [ ] **T8.3 Keep this exact incident replay as a permanent release gate.**
  - Evidence: _pending_.
- [ ] **T8.4 Publish the operator incident card/runbook and notification policy.**
  - One card, one genuine-decision notification, visible indeterminacy, named
    owner, precise next action.
  - Evidence: _pending_.
- [ ] **T8.5 Review 24h/72h/7d health and close only with no regression.**
  - Evidence: _pending_.

## Executive verdict

The replacement Critique Ledger epic did not complete CL2. The plan is stopped
at `gated -> finalize -> manual_review`; execution never started, no CL2 feature
work was produced, and there is no implementation PR to recover.

This was not one bad-model incident. Several models produced invalid or
incomplete evidence, but the decisive system failure was that the control plane
made those failures admissible and then split recovery across records that did
not form one obligatory state machine.

The root failure has two halves:

1. **Fail-open admission:** `unknown`, `unverifiable`, `rejected`, and
   `accepted_for_cl2=false` could be projected into permission to continue.
2. **Split effect custody:** detection, request acceptance, exact occurrence
   identity, claim, launch, runtime promotion, retrigger, recovery verification,
   and user notification were separate transitions with no canonical owner that
   guaranteed the next transition or a terminal receipt.

The result was paradoxical: individual safety checks failed closed for
mutation, while the system failed open operationally. It repeatedly observed,
retried, logged, and notified without advancing or terminating the incident.

The durable answer is not another watchdog, retry ledger, generalized agent, or
meta-fixer. It is to enforce the existing Run Authority / Custody / WBC design
at every admission and effect boundary, use the binding M11 singleton
`simple_fixer` topology, and prove production adoption with an executable replay
of this exact incident.

This document was adversarially reviewed by GPT-5.6 Sol at high reasoning. The
review's initial verdict was **NO-GO** because the first draft conflicted with
M11 and claimed cross-system atomicity that cannot be guaranteed. This revision
adopts those corrections. The preserved review is
`.megaplan/audits/critique-ledger-incident-sol-review-20260802.md`.

## Scope and evidence standard

This document covers four linked failures:

- poisoned CL2 admission and phase progression;
- model-output contract and critique-completeness failures;
- repair, recovery-topology, and runtime-custody failure;
- notification, persistence, projection, and disk-exhaustion failure.

Evidence is labeled as follows:

- **R — repository proof:** code, tests, or Git history directly inspected in
  the Arnold repository;
- **C — cloud artifact:** durable state or logs inspected in the cloud workspace
  on 2026-08-02. Until captured in the P0 evidence manifest, cloud counts and
  absence claims remain incident evidence, not release-grade proof;
- **I — inference:** a conclusion obtained by joining independent R/C records;
  it is called out where attribution is not directly recorded.

The absence of one normalized incident record is itself a finding. The
postmortem is definitive enough to contain the incident. It is not yet
sufficient authority for mutation or release: those require the off-volume,
content-addressed evidence manifest and go/no-go receipts defined below.

## Outcome and concise timeline

| UTC on 2026-07-31 | Outcome | Evidence |
| --- | --- | --- |
| 14:11 | CL2 plan launched. | C: plan history and chain log |
| 14:21 | DeepSeek V4 Pro prep completed with incomplete research; it surfaced blocking prerequisite questions. Auto-approval converted them into assumptions. | C: prep output and state history |
| 14:29–15:41 | GLM-5.2 repeatedly failed plan structural contracts. Interim runtime changes advanced the phase; planning eventually completed. | C: output audits, routing/events; R: commits `a7565c2e`, `70cae1d6ad` |
| 15:41–15:54 | Six selected critique checks failed their required result contract. They were projected as unverifiable/non-flagging, the ledger recorded zero findings, and the gate proceeded. | C: critique artifacts; R: `parallel_critique.py`, `flags.py`, critique custody/gate code |
| 16:07–16:45 | GLM-5.2 failed finalization structural conformance three times. | C: finalizer audits and raw outputs |
| 16:46 | Finalizer changed to `codex:gpt-5.6-sol:high`. | C: override history |
| 16:54–18:42 | Seven finalizer candidates were rejected by deterministic feasibility checks for invalid/unknown dependencies, unordered write overlaps, critical-path, or dispatch-budget infeasibility. | C: candidate and feasibility receipts |
| 18:42 | Plan stalled at `gated/finalize`; retry policy became `manual_review`. | C: `state.json` |
| 18:43 onward | The same escalation occurrence repeatedly attempted resident diagnostic launch and sent fallback Discord DMs. | C: escalation ledger; R: diagnostic/watchdog code |

## Model attribution: what failed, and what did not

| Route/model | Observed failure | Correct attribution |
| --- | --- | --- |
| DeepSeek V4 Pro prep | Incomplete research plus explicit blocking prerequisite questions | The model did not establish readiness. The control plane caused the unsafe progression by converting blockers into assumptions under auto-approval. |
| GLM-5.2 planning/finalization | Repeated malformed or incomplete structured outputs; later finalizer candidates were deterministically infeasible | Producer-contract and semantic-planning failures. Broad retry and contract drift made them expensive; deterministic rejection correctly prevented dispatch. |
| GPT-5.6 Sol finalizer | Seven candidates failed deterministic dependency/overlap/critical-path/dispatch-budget checks | Not a transport failure and not evidence that Sol “broke” the run. It failed to produce an admissible graph; the graph gate worked, but routing after rejection did not. |
| DeepSeek Flash, DeepSeek Pro, and GLM escalation tiers | The incident summary records all three as tried without advancing the gated failure | Tier changes did not cure a control-plane state/identity problem. The record does not justify blaming one of these models for the notification loop. |
| Six selected critic attempts | Required critique result contracts were not completed reliably | Attempt failures should have made critique incomplete. The system bug was projecting them to non-flagging `unverifiable` results and then recording zero findings. Exact provider/model attribution must come from the P0 attempt-receipt manifest. |

No single model caused the incident. Model outputs were imperfect, but a robust
harness must reject or narrowly repair those outputs. The root failure was the
harness turning invalid evidence into progress and then lacking one lawful,
bounded recovery continuation.

No durable fixer launch was confirmed. The accepted/queued record is not proof
of execution: there is no claim/attempt/result chain, and provenance validation
failed before durable diagnostic state existed. The safe conclusion is that no
fixer should be assumed to have run.

## What failed at heart

```text
invalid predecessor evidence
        |
        v
generic admission + auto-approve
        |
        v
prompt/schema/runtime drift -----> broad retries
        |                              |
        v                              v
invalid critique projected       infeasible finalizer candidates
as zero findings                       |
        |                              v
        +----------> gated/finalize stall
                              |
                              v
                repair request accepted without
                one claimable occurrence lifecycle
                              |
                    missing identity/provenance
                              |
             +----------------+----------------+
             |                                 |
       no claimable singleton             fallback DM sent
       simple_fixer occurrence            without effect custody
             |                                 |
             +------------> repeat <-----------+
                              |
                      unbounded artifacts
                      and disk exhaustion
```

## Finding 1 — CL2 should not have been admitted

### Evidence

- **C:** The authoritative CL1 handoff
  `docs/critique-ledger/handoffs/cl1-contract-oracle.json` recorded reviewer
  pending, M6 `INCOHERENT`, proof `FAILED`, unresolved ownership/portfolio
  blockers, and `accepted_for_cl2.value=false`.
- **R:** The CL1 handoff tests prove internal derivation and consistency of the
  artifact, not consumption by generic chain admission.
- **R:** `chain/source_admission.py` validates source identity and hashes.
  `epic_chain.py` validates declared generic handoff/file predicates. CL2 did
  not declare a typed `accepted_for_cl2` prerequisite.
- **R/C:** The chain enabled `driver.auto_approve`; the prep model's blocking
  clarification was converted into conservative assumptions.

### Root cause

A domain-owned prerequisite existed only as evidence, not as a mandatory
admission predicate. Human phase auto-approval was allowed to substitute for a
failed machine prerequisite.

### Permanent prevention

- Every milestone declares a typed, target-bound prerequisite predicate.
- Admission recomputes the predicate from content-addressed evidence; it never
  trusts a stored boolean by itself.
- Admission runs before plan creation and before any model call.
- `auto_approve` may approve an allowed human transition. It cannot override a
  false or unknown machine predicate.

## Finding 2 — producer and consumer contracts drifted

### Evidence

- **R:** Tool-enabled Hermes does not use a provider-native `response_format`
  for these calls; large structured results are prompt-constrained.
- **R:** Plan schemas embed substantial markdown structure inside free strings,
  while normalizers can synthesize permissive markdown.
- **C:** GLM-5.2 repeatedly omitted or malformed required plan, critique, and
  finalizer fields. Retries generally repeated the whole task with prose
  feedback rather than issuing one bounded, pointer-specific repair.
- **R/I:** Prompt, schema, normalizer, parser, adapter, model route, and installed
  runtime were not bound into one immutable attempt contract.

### Root cause

The model contract had several owners. A prompt described one shape, transport
enforced another or none, normalization tolerated a third, and a pinned runtime
could execute an older contract.

### Permanent prevention

- Each release binds one immutable, content-addressed contract bundle containing
  prompt fragments, transport/capture schema, parser ABI, normalizer, semantic
  validator, fixtures, and provider assumptions. A registry may locate bundles;
  it is not authority and there is no mutable `latest`.
- Prefer typed plan/finalizer ASTs to markdown embedded in JSON strings.
- Each attempt receipt binds source, runtime, prompt, schema, adapter, model,
  provider, and credential-set digests.
- Required fields cannot be synthesized or discarded. A structural error may
  receive one repair of only the invalid JSON pointers in the same object and
  bundle, followed by full revalidation. Semantic infeasibility is not a
  structural repair. Recurrence becomes `PRODUCER_CONTRACT_FAILED`, not another
  full retry.

## Finding 3 — invalid critique became “zero findings”

### Evidence

- **R:** `parallel_critique.py` converts exhausted structural failures and
  broad worker exceptions into synthetic `status=unverifiable`,
  `flagged=false` results.
- **R:** `flags.py` skips unverifiable checks.
- **R/C:** Critique custody then wrote `finding_count=0` and admitted the round;
  the gate proceeded despite no trustworthy evidence from the six selected
  lenses.
- **R:** Historical gate tests explicitly allow some operationally
  unverifiable checks not to block `PROCEED`. That policy was applied too
  broadly to contract/parser/provider failures.

### Root cause

One representation covered at least four different meanings:

- a valid check with no finding;
- a genuinely external dependency that could not be verified;
- a model/transport contract failure;
- a provider, parser, sandbox, or worker failure.

Completeness was not independently represented. `finding_count=0` could
therefore mean either “six valid checks found nothing” or “zero valid checks
ran.”

### Permanent prevention

- Use two axes. Attempt status is one of `SUCCEEDED`, `PROVIDER_FAILED`,
  `PRODUCER_CONTRACT_FAILED`, `PARSER_FAILED`, `SANDBOX_FAILED`, or `CANCELLED`.
  Semantic result exists only after `SUCCEEDED` and is `FINDING`, `NO_FINDING`,
  or policy-scoped `EXTERNAL_UNVERIFIABLE`.
- Wrong/multiple IDs, field rewriting, flag coercion, missing output, and prose
  inference are contract failures, never semantic results.
- Record a content-addressed selection manifest binding every mandatory lens
  occurrence, plan hash, contract-bundle hash, and attempt/result receipt.
- Every mandatory lens must succeed before critique can be admitted at
  thorough/high robustness. External unverifiability is never evidence of a
  clean critique.
- Contract/provider/parser failures route to bounded repair and cannot be
  projected into a clean critique.

## Finding 4 — deterministic graph rejection entered a generic retry loop

### Evidence

- **C:** GPT-5.6 Sol produced seven candidate task graphs; deterministic checks
  consistently prohibited implementation dispatch.
- **R:** Older finalizer routing wrote rejection/repair artifacts and then
  returned to broad revise/retry behavior.
- **R:** Retry counters were fragmented across phase, auto-loop, watchdog, and
  restart scopes.
- **R:** Commit `f72c9653d7` is a strong partial correction: it journals
  content-addressed candidates off-side, preserves admitted authority, forbids
  dispatch, and circuits repeated fingerprints. It does not by itself create
  one global repair occurrence across all layers and restarts.

### Root cause

Detection was correct, but the phase result was not a typed routing decision.
Equivalent semantic failures could acquire new attempt identities and budgets
at each orchestration layer.

### Permanent prevention

- Deterministic graph rejection emits `planner_repair_required` with a stable
  candidate/failure fingerprint.
- Preserve existing ownership: domain policy owns graph fingerprints and repair
  budgets; Custody owns occurrences, leases, and reclaim; WBC owns effect
  attempts and budget evidence; Run Authority accepts repair, replan,
  quarantine, or supersession. Do not create a global retry-ledger owner.
- At most two equivalent rejected fingerprints are allowed.
- The only legal continuation is one narrow graph repair or typed quarantine;
  ordinary revise/execute is forbidden.

## Finding 5 — accepted repair was not an obligatory lifecycle

### Evidence

- **R:** The repair request path can durably record `accepted/queued` before a
  claimable exact occurrence identity or attempt exists.
- **R:** Existing tests explicitly permit accepted requests with zero attempts,
  claims, or launches.
- **C:** The terminal repair request was accepted/queued, but no durable attempt
  or result receipt proves a fixer launched.
- **C/R:** The deployed watchdog later reported
  `request=unknown status=missing_identity`. The refusal was not durably
  transformed into one claimable recovery obligation for the canonical
  singleton `simple_fixer`.
- **R:** The progress auditor can verify that fixer, backstop, install,
  retrigger, and original advancement all occurred. It is a verifier, not the
  missing transition owner.

### Root cause

Queue persistence was mistaken for autonomous custody. Intake, identity
admission, claim, launch, terminal result, runtime promotion, retrigger, and
independent advancement were independent records without a canonical successor
rule.

### Permanent prevention

- Accept a repair only when its exact occurrence is claimable. Invalid or
  missing identity is terminal, non-claimable intake plus a linked recovery
  obligation; it must never be recorded as queued work.
- The immediate non-agent trigger and the three-hour missed-event reconciler
  invoke the same singleton `simple_fixer` implementation and share the same
  occurrence claim. They are two triggers, not two repair attempts.
- At most one canonical target runner and one ordinary retrigger are allowed.
  Fixer failure terminalizes; further release mutation requires a separately
  authorized release actor or a genuine human decision.
- Do not restore watchdog, L1/L2/L3 investigator, meta-repair, repair-loop,
  periodic audit-agent, or managed-child fanout. M11 explicitly retired them.
- Repair closes only after an independent verifier proves the original
  authoritative cursor advanced under the promoted runtime.

## Finding 6 — runtime fixes were not promoted as one complete identity

### Evidence

- **R/C:** The run encountered runtime-binding mismatches while interim commits
  were installed.
- **R:** `a7565c2e` corrected planner changed-surface/test normalization.
- **R:** `70cae1d6ad` propagated canonical runtime policy into worker preflight.
- **R/I:** These changes could advance individual phases, but neither record
  proves one fenced generation migration covering source ref, source checkout,
  installed code, interpreter/imports, wrappers, marker, and chain binding.
- **R:** Other partial hardening exists in history, including candidate graph
  admission, phase/cursor custody, restart pinning, worker binding, and stale
  relaunch screening. Component existence is not runtime adoption.

### Root cause

Source, installed runtime, wrapper/process runtime, and chain target could drift
independently. A hotfix could be locally correct without becoming the one
authoritative runtime used by every subsequent action.

### Permanent prevention

Require one immutable, content-addressed generation manifest covering:

```text
target branch and commit
source checkout and tree
installed package / editable source
interpreter, imports, direct_url and .pth files
profile, prompt, schema and model routing
wrapper, supervisor, service and trigger revisions
marker, session, plan and chain binding
schema and state migrations
```

Fence old writers and effects before a CAS generation switch, then attest live
PIDs, executables, imports, wrappers, and configuration. Any false or unknown
equality blocks before dispatch. Binary rollback is legal only if the old
generation can read post-migration state; otherwise forward-fix. Backup restore
must be tested. The interim commits `a7565c2e`, `70cae1d6ad`, and `c5b613a441`
are descendants of deployed `c7bcb06af536`; their existence does not prove
runtime adoption.

## Finding 7 — notification delivery was outside durable effect custody

### Evidence

- **R:** At deployed commit `c7bcb06af536`,
  `launch_human_review_diagnostic()` resolves resident provenance before
  computing the escalation identity or creating diagnostic state
  (`human_review_diagnostic.py`, approximately lines 391–405).
- **R:** A pre-state exception returns `escalation_id=""`, `state_path=""`, and
  `fallback_delivery_required=true` (approximately lines 632–647).
- **C:** The cloud marker had no `resident_delegation`, so provenance resolution
  raised `DelegationProvenanceError`.
- **R:** The deployed watchdog appends `opened`, sends fallback Discord directly, and can
  record fallback reconciliation only when `state_path` is nonempty.
- **C:** The same stable escalation ID accumulated 203 `opened` and 201
  `delivered` records, each delivered record carrying a distinct Discord
  message ID.
- **R:** The escalation ledger is appended but is not consulted as effect
  admission. The direct Discord path bypasses WBC; the inspected delivery path
  also contains optional adapter fallthrough, shadow authorization, and
  synthetic identity behavior.
- **R:** The JSONL append implementation rereads and rewrites the whole file and
  derives a sequence from its current length without a process-safe append
  claim, amplifying I/O and risking lost concurrent updates.

### Root cause

Observation, diagnostic launch, and user notification did not share one durable
incident/effect state machine. A stable escalation ID existed, but delivery did
not require a uniquely claimed durable intent.

The repeat loop was deterministic:

1. an observer saw the same `manual_review/gated` state;
2. it appended another `opened` event without a send-once admission check;
3. diagnostic launch validated resident provenance before creating durable
   diagnostic identity/state;
4. missing provenance raised `DelegationProvenanceError` and returned blank
   state coordinates with fallback requested;
5. the fallback Discord call succeeded;
6. blank diagnostic state prevented durable reconciliation of that send; and
7. the next observation found no authoritative accepted effect outcome and
   repeated the sequence.

### Permanent prevention

- Create incident occurrence and diagnostic-attempt identity before validating
  provenance. Missing provenance becomes one durable terminal diagnostic result.
- Retire the watchdog as a recovery scheduler. The immediate event trigger and
  three-hour reconciler may observe/enqueue the same `simple_fixer` occurrence;
  neither calls Discord or any provider directly.
- Every production effect requires a real current Run Authority grant/fence,
  current Custody lease/epoch, and canonical WBC GLEK. Missing adapters or auth,
  shadow/synthetic identity, fake success, and local adapter exceptions fail
  closed with zero provider calls; no direct fallback is permitted.
- Cross-owner work is a saga, not one transaction: validate coherent authority
  and custody cursors; durably reserve/start WBC; perform the effect; persist
  the WBC outcome; reread and reconcile owner records.
- WBC delivery workers use leases and persist attempts and provider receipts.
  Ambiguous provider application is `INDETERMINATE` and prohibits redispatch;
  it is never converted to `FAILED` and blindly resent.
- Notification tuple fields are request material, not a parallel idempotency
  owner. Chunked payloads use stable child GLEKs derived from parent GLEK,
  chunk index, and digest.

## Finding 8 — observability and storage shared the failure domain

### Evidence

- **C:** Incident evidence reports that the cloud volume reached `601G/601G`
  and returned `ENOSPC` during state and projection writes. The exact count and
  capacity must be captured in the P0 manifest before becoming release proof.
- **C:** Incident evidence reports some later watchdog outputs as zero-byte
  files; these require the same manifest treatment.
- **C:** Detailed truth was fragmented across `state.json`, a roughly 15.9 MB
  `events.ndjson`, chain logs, routing records, output audits, candidate
  receipts, repair queues, Git commits, watchdog reports, and escalation logs.
- **C/R:** Event sequence/rebuild behavior became difficult to interpret across
  runtime cutover. Partial projection fixes exist outside the deployed/main
  runtime.
- **R:** Retention paths do not consistently target the actual accumulating
  escalation JSONL, and control state shares storage with large artifacts/logs.

### Root cause

The system had many raw evidence stores but no single joinable canonical
incident projection. Persistence growth was unbounded, append paths amplified
writes, and control-plane survival did not have reserved capacity.

### Permanent prevention

- Preserve owner-specific append-only histories, but expose one rebuildable
  `incident brief` projector joining plan, model, critique, repair, runtime,
  retrigger, notification, storage, and verification records.
- Reference large raw artifacts by path, hash, size, and retention class rather
  than embedding repeated state snapshots.
- Use transactional owner stores with process-safe identifiers. Projection
  sequence gaps are legal; a read error never means an empty authoritative
  store.
- Bound and compact rebuildable projections; maintain chronological-tail
  semantics across restart epochs.
- Reserve bytes and inodes on an isolated or quota-controlled owner-store
  volume. Watermarks cover the worst-case transaction, WAL/fsync, checkpoint,
  and rebuild. Block execution and external effects before durable intent or
  receipts become unsafe. Logs, artifacts, and disposable projections cannot
  consume the canonical-store reserve.
- Before cleanup, write an off-volume content-addressed evidence manifest.
  Provider application followed by receipt `ENOSPC` is `INDETERMINATE`; “zero
  unreceipted effects after provider dispatch” is not a defensible promise.

## The invariant that prevents this class permanently

No phase, repair, deployment, notification, publication, or completion may
advance unless the authoritative owners durably prove and reconcile all of the
following:

1. the input and prerequisites are current and admissible;
2. the actor holds the current Run Authority grant/fence and Custody
   lease/epoch;
3. WBC durably started the exact GLEK before any effect;
4. the source/runtime/process vector matches the declared target;
5. the outcome is accepted terminal or explicitly `PENDING`, `INCOHERENT`, or
   `INDETERMINATE`, with redispatch prohibited where provider application is
   ambiguous;
6. recovery claims are independently verified against the original condition.

`unknown` can deny or quarantine. It can never grant, complete, notify again,
or project success. Atomicity is claimed only inside an owner store. Across Run
Authority, Custody, WBC, incident state, Git, Discord, and cloud processes, the
guarantee is a reconciled, fail-closed saga—not a distributed transaction.

## Target control loop

```text
detected
  -> coherent evidence snapshot
  -> typed classification
  -> exact occurrence admitted, or invalid intake terminalized
  -> authority + custody acquired
  -> durable WBC attempt_started before effect
  -> bounded simple_fixer / delivery / transition
  -> accepted terminal outcome or visible indeterminate outcome
  -> fenced runtime generation promoted where needed
  -> ordinary work retriggered once
  -> independent original-condition verification
  -> resolved, superseded, quarantined, indeterminate, or one human decision
```

One immediate non-agent event trigger and one three-hour missed-event reconciler
invoke the same singleton `simple_fixer` implementation and share the same
occurrence claim. Repeated observation is cheap; it creates neither a new repair
attempt nor a new external effect.

## Implementation and acceptance plan

### P0 — Contain and preserve the incident

**Actions**

1. Freeze every mutation and external effect for the affected session.
2. Capture an off-volume, content-addressed evidence manifest before cleanup.
   Every material cloud claim receives a claim ID, URI/path, SHA-256, size,
   capture time, collector/tool version, runtime/commit, clock basis, and minimal
   query/excerpt.
3. Recover byte and inode headroom without deleting custody evidence; validate
   filesystem, authoritative stores, WAL/indexes, projections, and all unknown
   provider effects.
4. Have Run Authority append a superseding decision that invalidates/quarantines
   the prior M11 completion/promotion evidence and the old CL2 revision.
5. Revoke old grants; revoke/expire Custody leases under an advanced
   fence/epoch without reusing the target key; reconcile old WBC GLEKs to
   accepted terminal or `INDETERMINATE`; CAS-disable old-plan resume.

**Exit criteria**

- no new notification or repair effect from unchanged state;
- off-volume evidence manifest exists and verifies;
- control-plane storage is writable with enforced reserve;
- the old plan cannot execute, publish, notify, or be silently resumed;
- ambiguous prior provider effects cannot be resent.

### P1 — Close admission and semantic-completeness holes

**Actions**

1. Add target-bound, recomputed handoff predicates to chain admission.
2. Make machine prerequisites non-overridable by auto-approval.
3. Introduce the typed critique result algebra and completeness cardinality.
4. Make gate and critique custody fail closed when selected evidence is missing,
   contract-failed, or operationally invalid.
5. Bind an immutable content-addressed contract bundle for plan, critique, and
   finalizer outputs.

**Exit criteria**

- false CL1 handoff cannot initialize CL2;
- six invalid critique workers cannot produce admitted zero findings;
- prompt/transport/parser/normalizer/validator/provider-assumption hashes agree
  in attempt receipts;
- structural failures route to one bounded typed repair.

### P2 — Implement the binding recovery and effect topology

**Actions**

1. Require exact repair occurrence identity at intake. Terminalize invalid
   intake and create a linked recovery obligation without pretending work was
   queued.
2. Implement one singleton `simple_fixer`, one canonical target runner, an
   immediate non-agent trigger, and a three-hour reconciler using the same
   implementation and occurrence claim.
3. Persist incident/diagnostic attempt identity before provenance validation.
4. Remove direct Discord/webhook/Git/PR/model/cloud fallthrough and every
   shadow/synthetic/fake-success route. All production effects require current
   Run Authority, Custody, and WBC GLEK.
5. Implement the cross-owner saga and explicit `PENDING`, `INCOHERENT`, and
   `INDETERMINATE` outcomes; never blindly redispatch ambiguous effects.
6. Keep budgets with their existing owners: domain graph policy, Custody
   occurrences, WBC effect attempts, and Run Authority transition acceptance.

**Exit criteria**

- invalid identity cannot produce accepted/queued work;
- each accepted WBC attempt/GLEK has at most one accepted terminal outcome;
- 200 identical observations create at most one accepted notification outcome;
- crash or `ENOSPC` before durable WBC start creates zero provider calls;
- provider-applied/ack-lost remains visible and non-redispatchable;
- missing provenance/identity produces one terminal typed record and one
  singleton-fixer obligation, never an observation loop;
- no watchdog/L2/meta-repair/managed-child recovery path is reachable.

### P3 — Re-establish M11 and promote one fenced generation

**Actions**

1. Reconcile—not blindly cherry-pick—the relevant partial fixes on one clean
   lineage.
2. Produce a new zero-blocker ownership decision, complete contract portfolio,
   approval, full cross-contract/M11 suite, and production-vector canary.
3. Generate the complete generation manifest and require equality at preflight,
   worker launch, repair launch, promotion, retrigger, and verification.
4. Fence old writers/effects before CAS promotion; attest live PIDs,
   executables, imports, wrappers, services, routes, and old-writer rejection.
5. Test backup restoration. Permit binary rollback only when schema/state
   compatibility is proven; otherwise exercise forward-fix.
6. Prove owner-store recovery, projection rebuild, retention, byte/inode
   watermarks, and isolated capacity.

**Exit criteria**

- one content-addressed release contains every required prevention control;
- source/ref/install/import/wrapper/process/marker/chain identities agree;
- backup restore and rollback/forward-fix are tested;
- no loose commit or mutable path is treated as deployed authority.

### P4 — Turn this incident into the release gate

The installed production entrypoints must replay, at minimum:

1. `accepted_for_cl2=false` with `auto_approve=true` still blocks before plan
   creation;
2. the handoff is recomputed and bound to the exact CL1 evidence;
3. six structural critic failures yield `critique_incomplete`, not zero
   findings;
4. provider/parser/sandbox/contract failures remain distinguishable;
5. the exact rejected finalizer graph cannot publish or dispatch;
6. semantically identical candidates across prose changes and restart consume
   the domain-owned fingerprint budget and open at most one graph repair;
7. runtime vector mismatch prevents worker or fixer launch;
8. identity-free repair creates one typed refusal plus one singleton-fixer
   obligation, never queued work;
9. crash before/after request, claim, launch, commit, install, retrigger,
   notification intent, provider send, and receipt converges without duplicate
   effects;
10. immediate and three-hour triggers share one `simple_fixer` occurrence;
11. two concurrent observers and 200 unchanged scans cause at most one accepted
    notification outcome;
12. provider-applied/ack-lost plus `ENOSPC` becomes `INDETERMINATE` without
    resend and preserves the incident brief;
13. independent verification is the only transition that can close recovery.

**Exit criteria**

- clean baseline and candidate both run the full replay;
- the candidate prevents or safely contains every injected fault;
- evidence is generated by production code paths, not hand-authored fixtures;
- installed-runtime canary matches the tested revision.

### P5 — Start a clean CL2 successor and prove advancement

The existing plan must not be resumed. It carries a false predecessor premise,
mixed runtime history, degraded critique admission, and fragmented retry state.

**Actions**

1. Complete P0 fencing: supersede/quarantine the old revision, revoke its Run
   Authority grants, revoke/expire Custody leases under an advanced fence/epoch
   without reusing the target key, reconcile old GLEKs, and CAS
   chain selection away from the old plan.
2. Resolve the actual CL1 reviewer, coherence, proof, ownership, and portfolio
   blockers from raw evidence.
3. Regenerate and independently recompute a target-bound accepted CL1 handoff;
   Run Authority grants the successor only after the predicate is true.
4. Create fresh plan/revision, subject-attempt, Custody/WBC, branch/worktree,
   and PR identities. Inherit no gate/finalizer state, budget, notification ID,
   GLEK, or mutable artifact from the old plan.
5. Launch only under the P3 recovery generation and P4 acceptance receipts.
6. Run ordinary plan → critique → gate → finalize. If graph admission rejects,
   Run Authority may accept exactly one narrow structural repair of the frozen
   candidate under the same Custody occurrence and WBC evidence.
7. Execute, commit, push, and open a PR only through ordinary
   Run Authority/Custody/WBC paths. Independently verify chain advancement and
   the publication receipt.

**Exit criteria**

- prerequisite receipt is accepted and target-bound;
- runtime vector is exact and independently reread;
- critique completeness and graph admission are green;
- plan advances to `finalized` and then into execution under authoritative
  custody;
- CL2 produces feature commits and a PR through the ordinary chain path;
- no human notification is emitted unless one typed, genuine human decision
  remains.

## Go/no-go gate for cloud mutation

The current state is **NO-GO**. Mutation begins only when every item below has
durable evidence:

- old mutation/effects are stopped and fenced;
- the off-volume evidence manifest verifies;
- byte/inode reserve and authoritative stores/WAL are healthy;
- old grants/leases are revoked and old provider effects are terminal or
  indeterminate with redispatch prohibited;
- prior M11 completion/promotion is invalidated and a new zero-blocker ownership
  decision is approved;
- an immutable recovery generation and complete installed runtime vector exist;
- no direct effect fallthrough, shadow/synthetic authorization, fake success,
  watchdog/L2/meta-repair/managed-child recovery path is reachable;
- installed-entrypoint fault, concurrency, storage, provider ambiguity, and
  successor tests pass;
- migration, backup, rollback/forward-fix, and old-writer rejection pass;
- old CL2 cannot resume, the raw CL1 predicate is independently satisfied, and
  the successor grant/lease/WBC start are coherent.

After the gate: canary the generation; perform one ordinary CL2 action;
independently verify it; then broaden execution. PR publication is prohibited
until execution receipts and WBC publication intent are durable.

## Complete restart/relaunch runbook

This is a **successor launch**, not a resume. Never clear `manual_review`, delete
the old state until it looks fresh, or run `--fresh` against the old v2
initiative. The old session, plan, workspace, branch identities, Custody
occurrences, WBC GLEKs, notification identities, and mutable artifacts remain
quarantined evidence.

The historical `megaplan-cloud` skill is explicitly zero-authority under M11.
The commands below were checked against the installed CLI; they do not grant
authority. Run Authority, Custody, WBC, and Release Authority receipts remain
mandatory.

### R0 — Name and bind the successor

Choose all identities once and record them in the Run Authority launch grant:

| Identity | Requirement |
| --- | --- |
| successor initiative | new path, for example `.megaplan/initiatives/critique-ledger-v3-<UTC>/`; never the old v2 spec path |
| source base | exact approved recovery commit/tree, not a floating branch |
| runtime generation | exact approved generation manifest and installed-vector digest |
| workspace | new isolated path, not `/workspace/critique-ledger-accountability-v2-20260728/Arnold` |
| cloud session | new unique `chain_session`, not `critique-ledger-accountability-v2-20260728` |
| chain revision | new chain-spec hash and Run Authority revision |
| CL2 plan/subject attempt | new identities allocated after admission |
| Custody/WBC | new occurrence/lease/epoch; WBC derives GLEKs from the fresh occurrence/attempt/effect |
| Git publication | new branch/worktree namespace and publication intent; the provider-assigned PR identity is recorded only after the WBC effect receipt |

Use one launch record to bind these identities to the accepted CL1 predicate,
contract-bundle digest, M11 completion manifest, generation manifest, and
evidence-manifest digest. A mismatch is a stop, not a runtime repair.

### R1 — Permanently fence the poisoned run

Before creating the successor, bind and fence the complete poisoned tuple:

```text
selection/session: critique-ledger-accountability-v2-20260728
spec: .megaplan/initiatives/critique-ledger/chain.yaml at its captured hash
workspace: /workspace/critique-ledger-accountability-v2-20260728/Arnold
plan: cl2-wbc-backed-ledger-20260731-1411
branch/runtime: exact values from the P0 evidence manifest
```

1. Run Authority supersedes/quarantines old plan
   `cl2-wbc-backed-ledger-20260731-1411`, revokes every grant for its revision,
   and records that `resume`, `repair`, `execute`, `publish`, and `notify` are
   forbidden.
2. Custody revokes/expires every old lease under an advanced fence/epoch,
   never plain-releases or reuses the target key, and proves late old writers
   reject before issuing any successor lease.
3. WBC reconciles every old GLEK. Accepted terminal outcomes remain terminal;
   `INDETERMINATE` effects remain unresolved and no-redispatchable pending
   reconciliation—they are not relabeled as accepted terminal.
4. Chain selection uses CAS to remove the old plan/session as the selected
   runnable target.
5. Canonical authority makes the old marker project `should_run=false`; nobody
   edits the marker directly.
6. The old branch/worktree, workspace, marker, plan directory, and artifacts
   become read-only evidence. Do not delete them to manufacture freshness.

The Run Authority/Custody/WBC implementation delivered by the recovery release
must expose canonical commands or APIs for these five operations. Their exact
syntax cannot honestly be specified before that release is installed. If the
release exposes no authoritative fence/revoke/reconcile/CAS interface, relaunch
remains **NO-GO**.

### R2 — Establish clean control-plane capacity and runtime

1. Keep release ticket `01KYSBGRHM1S8R6RQ1DGZ7843Y` open until the exact
   recovery revision has an accepted release receipt.
2. Keep deployed-canary ticket `01KYVJ7A47TMH4BRGEV9JFTK10` open until its
   exact installed-runtime canary is independently verified. Both tickets are
   still `status: open` on `origin/main` at
   `25e407d78339cc6f13112aec770188997577e85a`; ancestry or a c7 tag cannot close
   them.
3. Verify the off-volume evidence manifest before any cleanup.
4. Verify byte and inode reserves, authoritative stores, WAL/indexes, and
   backup restoration.
5. Promote the approved generation under a separate Release Authority grant.
   Fence old writers/effects before CAS promotion.
6. Attest source tree, interpreter/venv, installed provenance, `.pth` and import
   roots, wrappers/services, environment policy, schemas/migrations, contract
   bundle, provider routes, and live process command lines.
7. Prove old processes cannot write. Test migration-compatible rollback; if the
   old binary cannot read post-migration state, prove forward-fix instead.
8. Run the M11 production canaries: immediate trigger and dropped-immediate
   three-hour reconciliation must claim the same singleton `simple_fixer`
   occurrence, with no watchdog/L2/meta-repair/child path.

No `cloud chain` launch is allowed to update the installed runtime as a side
effect. Runtime promotion finishes before chain launch.

### R3 — Materialize fresh durable epic inputs

Create and commit a new successor initiative containing only reviewed durable
inputs:

```text
.megaplan/initiatives/critique-ledger-v3-<UTC>/NORTHSTAR.md
.megaplan/initiatives/critique-ledger-v3-<UTC>/chain.yaml
.megaplan/initiatives/critique-ledger-v3-<UTC>/cloud.yaml
.megaplan/initiatives/critique-ledger-v3-<UTC>/briefs/*.md
.megaplan/initiatives/critique-ledger-v3-<UTC>/completion-preconditions/*
```

Rules:

- Copy no generated `.megaplan/plans`, chain state, locks, logs, projections,
  retry counters, session markers, or mutable artifacts.
- Keep the North Star and CL2–CL5 intent only after reconciling them against the
  corrected ownership and effect contracts.
- Add launch preconditions for the independently recomputed CL1 handoff, the new
  zero-blocker M11/ownership decision, the recovery completion manifest, and the
  approved generation manifest.
- The CL1 predicate derives from raw hashed evidence and is evaluated again
  under fence immediately before CL2 initialization. A stored
  `accepted_for_cl2=true` field alone is insufficient.
- Use `stop_chain` for failure/escalation. `auto_approve` may cover only a
  closed allowlist of human transitions; machine prerequisites are never
  overridable. Resolve genuine human decisions before unattended launch.
- Bind each milestone to the immutable contract bundle and approved runtime
  generation. Model routes may vary only within the approved policy; route
  changes cannot reset domain, Custody, or WBC budgets.
- Use a new Git branch/worktree/PR namespace derived from the successor launch
  identity. Do not reuse the v2 branch names.

### R4 — Read-only preflight

From a clean checkout, set variables from the accepted generation and launch
seed. Invoke the attested interpreter with isolated import-path handling; do
not use ambient `python`:

```bash
APPROVED_RECOVERY_SHA=REPLACE_WITH_ACCEPTED_COMMIT
APPROVED_RECOVERY_TREE=REPLACE_WITH_ACCEPTED_TREE
CRITIQUE_RUNTIME_PYTHON=/ABSOLUTE/PATH/TO/ATTESTED/RUNTIME/python
CRITIQUE_SUCCESSOR_SPEC=.megaplan/initiatives/critique-ledger-v3-YYYYMMDDTHHMMSSZ/chain.yaml
CRITIQUE_SUCCESSOR_CLOUD=.megaplan/initiatives/critique-ledger-v3-YYYYMMDDTHHMMSSZ/cloud.yaml

test "$(git rev-parse HEAD)" = "$APPROVED_RECOVERY_SHA"
test "$(git rev-parse 'HEAD^{tree}')" = "$APPROVED_RECOVERY_TREE"
test -z "$(git status --porcelain=v1)"

"$CRITIQUE_RUNTIME_PYTHON" -P -c \
  'import arnold_pipelines,sys; print(sys.executable); print(arnold_pipelines.__file__)'

"$CRITIQUE_RUNTIME_PYTHON" -P -m arnold_pipelines.megaplan cloud preflight \
  "$CRITIQUE_SUCCESSOR_SPEC" \
  --cloud-yaml "$CRITIQUE_SUCCESSOR_CLOUD" \
  --skip-remote
```

That command is the guaranteed local/read-only preflight. Then run the same
preflight without `--skip-remote` as a separately labelled read-only remote
dependency/import probe. It does not upload the successor spec and does not
prove workspace, authority, or launch admission.

Do not use `--allow-loose-chain-spec`, `--allow-template-placeholders`, or
`--allow-human-gates` to make preflight green. Confirm separately that:

- the cloud workspace and `chain_session` are new and unique;
- repo branch and runtime generation resolve to exact approved commits;
- the expected remote spec path is deterministically derived but absent before
  launch; the future launch transaction must collision-check it and the
  post-launch verifier must compare its uploaded blob/hash with the launch seed;
- auth resolves to the intended provider route without exposing credentials;
- owner cursors are coherent and the old session has no current grant/lease;
- there is no existing successor chain state, plan directory, marker, branch,
  worktree, GLEK, or PR identity;
- live installed-vector attestation matches the tested generation byte for byte.

Any unexpected pre-existing successor identity is a collision and aborts the
launch. Do not delete it and retry under the same name.

### R5 — Grant a one-transition canary

Run Authority initially grants only the successor initialization and first
ordinary CL2 transition. Custody allocates the new occurrence/lease/epoch; WBC
records any required attempt before an effect. If the installed release cannot
scope authority narrowly enough to stop after this canary, relaunch is
**NO-GO**.

The canary must prove:

1. raw CL1 evidence recomputes to accepted and binds the exact target;
2. the fresh plan/revision contains none of the old gate/finalizer/retry state;
3. installed runtime and contract-bundle digests match the launch grant;
4. one accepted transition occurs under current Run Authority and Custody;
5. no external effect occurs without a prior WBC start;
6. the old plan and old writer processes remain rejected;
7. the incident projector agrees with owner records without authorizing them.

An independent verifier accepts this canary before broader authority is
granted.

### R6 — Install and use the missing M11-authorized launch transaction

There is **no safe executable launch command in the current installed CLI**.
Current `cloud chain` directly ensures/uploads a checkout, starts tmux, has no
Run Authority grant/fence or Custody lease/epoch inputs, permits compatibility
effect paths, and requires legacy watchdog tracking verification. Its `--fresh`
mode can force-stop/reset an identity and therefore masks collisions. It must
not be used to restart this epic, even with a new name.

The recovery release must add one fail-closed launch transaction that consumes
and durably joins:

- the content-addressed launch seed and expected remote spec blob;
- current Run Authority grant/revision/fence and scoped canary TTL;
- current Custody occurrence/lease/epoch;
- WBC attempt/action intent before upload, process start, or publication;
- exact approved runtime generation and `no runtime/source refresh` policy;
- absent/collision-free workspace, session, spec, plan, branch, worktree, and
  publication namespace;
- one canonical target runner and the binding singleton-`simple_fixer`
  topology, with no watchdog/L2/meta-repair/managed-child path;
- pre-issued revoke/fence/stop capability for the same launch identity.

It must fail on any existing successor identity instead of resetting or
deleting it. The release owner must add the exact installed command/API syntax
and its help/contract digest to this runbook after that surface passes M11.
Until then R6 is **BLOCKED** and the overall launch remains **NO-GO**.

Raw `cloud chain`, `chain start`, tmux, compatibility `launch-epic`, `--fresh`,
`--force-clean-editable-install`, and old watchdog/relaunch paths are not
substitutes.

### R7 — Verify launch and controlled expansion

Immediately after the future authorized launch, the following commands may be
used as observations only:

```bash
"$CRITIQUE_RUNTIME_PYTHON" -P -m arnold_pipelines.megaplan cloud status \
  --cloud-yaml "$CRITIQUE_SUCCESSOR_CLOUD" \
  --chain

"$CRITIQUE_RUNTIME_PYTHON" -P -m arnold_pipelines.megaplan cloud status \
  --cloud-yaml "$CRITIQUE_SUCCESSOR_CLOUD" \
  --all --compact --since 1h

"$CRITIQUE_RUNTIME_PYTHON" -P -m arnold_pipelines.megaplan cloud logs \
  --cloud-yaml "$CRITIQUE_SUCCESSOR_CLOUD" \
  --no-follow
```

`status --all` may consume legacy watchdog snapshot/fallback data. None of these
commands are acceptance evidence. Query authoritative owners and verify:

- marker/spec/workspace/session point to the new identity;
- current plan/revision, grant/fence, lease/epoch, GLEKs, branch/worktree, and
  runtime generation equal the launch record;
- one plan was initialized and no duplicate runner/fixer exists;
- critique selected-set completeness is exact and attempt failures cannot
  project to `NO_FINDING`;
- a deterministic graph rejection can only request one narrow domain repair;
- no direct notification/publication/provider fallback is reachable;
- old-plan late writes, effects, and publication attempts continue to reject.

Check again after the first transition, after 10–15 minutes, at each milestone
boundary, and before every authority expansion. Broaden the Run Authority grant
only after the independent verifier accepts the preceding slice.

### R8 — Completion proof

The epic is durably moving only when the chain has authoritative forward
movement, not merely a live process or changing event cursor. CL2 success
requires accepted finalize and execution receipts, feature commits, durable WBC
publication intent, push/PR receipt, and chain cursor advancement. Each later
milestone requires the same proof plus its declared predecessor completion
manifest.

Final completion requires:

- all successor milestones accepted under the new identity;
- content-addressed completion manifest and proof map;
- merged publication evidence under ordinary WBC/Run Authority/Custody paths;
- independent projection agreement;
- no reachable old writer/effect/recovery path;
- no unresolved `PENDING`, `INCOHERENT`, or `INDETERMINATE` occurrence that the
  completion policy requires resolved.

### R9 — Immediate stop conditions

The recovery release must pre-issue one canonical revoke/fence/stop capability
bound to the launch grant TTL. Current pause, tmux-kill, marker-edit, and legacy
retire commands are not authorized substitutes. On any condition below, invoke
that capability, stop admitting WBC effects, and preserve evidence:

- source/install/process/contract/generation mismatch;
- false or unknown CL1 predicate;
- duplicate runner, fixer, occurrence, GLEK, branch, worktree, or PR identity;
- old-plan writer/effect accepted after fencing;
- critique attempt failure projected as semantic success;
- direct provider fallback, shadow/synthetic authorization, or effect without
  durable WBC start;
- provider ambiguity followed by redispatch;
- byte/inode/WAL reserve breach or owner-store read/write uncertainty;
- repeated graph fingerprint outside its domain budget;
- status-only churn without accepted task/phase progress;
- missing independent verification or projection disagreement.

Rollback must not restore a legacy writer or bypass. Use binary rollback only
when post-migration state compatibility is proven; otherwise keep effects
disabled and forward-fix under a new Release Authority grant. Never resume the
poisoned v2 plan as rollback. If the canonical stop capability is unavailable,
keep all effects fail-closed and treat the system as an operational incident;
do not improvise a tmux or marker mutation.

## Mandatory regression tests

The implementation should contain named tests equivalent to:

- `test_initial_cl2_admission_rejects_false_handoff_with_auto_approve`
- `test_admission_recomputes_raw_evidence_not_stored_true_boolean`
- `test_admission_rejects_stale_wrong_target_missing_and_throwing_predicate`
- `test_admission_rereads_under_fence_before_plan_creation`
- `test_two_initializers_cas_to_one_successor`
- `test_six_failed_attempts_are_incomplete_not_zero_findings`
- `test_wrong_or_multiple_lens_ids_are_producer_contract_failures`
- `test_schema_valid_empty_and_unresolvable_evidence_fail_semantics`
- `test_normalizer_cannot_synthesize_or_drop_required_fields`
- `test_pointer_repair_cannot_change_valid_fields_or_contract_bundle`
- `test_gate_cannot_proceed_with_structural_unverifiable_checks`
- `test_all_worker_transport_failures_block_critique`
- `test_phase_result_maps_graph_infeasibility_to_typed_repair`
- `test_identical_finalizer_candidate_opens_one_bounded_planner_repair`
- `test_domain_fingerprint_budget_survives_restart_and_model_change`
- `test_accepted_repair_requires_claimable_occurrence_or_linked_quarantine`
- `test_missing_identity_routes_once_to_singleton_simple_fixer_obligation`
- `test_immediate_and_three_hour_triggers_share_one_occurrence`
- `test_simple_fixer_failure_creates_no_l2_watchdog_or_managed_child`
- `test_missing_provenance_persists_terminal_diagnostic_before_effect`
- `test_two_observers_two_hundred_ticks_accept_one_notification_outcome`
- `test_missing_adapter_shadow_or_synthetic_auth_makes_zero_provider_calls`
- `test_adapter_exception_has_no_direct_fallback`
- `test_enospc_before_wbc_start_produces_zero_provider_calls`
- `test_provider_applied_ack_lost_is_indeterminate_and_not_resent`
- `test_partial_chunks_use_stable_child_gleks_and_do_not_duplicate`
- `test_every_torn_run_authority_custody_wbc_write_order_fails_closed`
- `test_concurrent_owner_writers_and_corrupt_projection_preserve_authority`
- `test_runtime_vector_mismatch_prevents_worker_launch`
- `test_stale_pth_and_old_process_writer_reject_after_generation_switch`
- `test_migration_then_binary_failure_obeys_rollback_compatibility`
- `test_backup_restore_and_forward_fix_are_executable`
- `test_successor_inherits_no_old_ids_budgets_gleks_or_mutable_artifacts`
- `test_old_plan_late_outcome_and_publication_are_fenced`
- `test_git_push_or_pr_ack_lost_does_not_duplicate_publication`
- `test_repair_closes_only_after_independent_cursor_advancement`

## Explicit non-solutions

- Do not merely change the finalizer model again.
- Do not increase retry counts.
- Do not suppress Discord messages without effect custody.
- Do not add another parallel incident ledger or repair queue.
- Do not restore watchdog, L1/L2/L3 investigator, meta-repair, repair-loop,
  periodic audit-agent, or managed-child recovery topology.
- Do not fabricate resident/Discord provenance for an unattended system repair.
- Do not call a registry, queue, projector, notification key, or global retry
  ledger an authoritative owner.
- Do not declare a fix deployed because a commit exists or tests pass locally.
- Do not resume the old CL2 plan after clearing its `manual_review` field.
- Do not let the repair actor verify its own success.
- Do not blindly resend an effect whose provider outcome is ambiguous.

## Ownership map

| Concern | Authoritative owner |
| --- | --- |
| Prerequisite and phase grants, fences, accepted transitions | Run Authority |
| Exact action/repair occurrence identity, exclusive lease/epoch | Custody |
| Attempt/effect evidence, GLEKs, receipts, ambiguity and payload/reference policy | WBC |
| Plan/critique/finalizer semantic validity and routing policy | Megaplan domain handlers/compiler |
| Joined explanation and status | Rebuildable incident projector |
| Recovery evidence | Independent verifier consuming current owner records; Run Authority accepts the resulting transition |

No projection, marker, queue label, process heartbeat, log line, model claim, or
provider response may substitute for these owners.

## Definition of “prevent forever”

No system can promise that models, providers, disks, or new code will never
fail. The enforceable promise is stronger and more useful:

- the known failure states are mechanically inadmissible;
- every accepted obligation has a bounded lifecycle; ambiguous external
  application becomes visible `INDETERMINATE` and cannot be redispatched;
- repeated observation cannot create another accepted repair occurrence or WBC
  effect attempt;
- unknown failures fail closed for authority and effects while remaining
  visible in one canonical incident brief;
- this exact incident is a permanent release-blocking replay fixture.

That prevents recurrence of this known failure class. It also converts novel
failures into bounded, queryable, non-redispatchable states rather than another
endless loop. It does not—and no honest design can—guarantee that all future
models, providers, disks, migrations, or code are bug-free.

## Accountable deliverables

| Deliverable | Accountable authority | Completion evidence |
| --- | --- | --- |
| Incident freeze, supersession, old grants revoked | Run Authority owner | accepted supersession/fence receipts |
| Old leases and occurrences fenced | Custody owner | current epoch/lease queries and late-writer rejection |
| Old external effects reconciled | WBC owner | terminal/indeterminate GLEK report with redispatch denied |
| Evidence manifest and storage reserve | Cloud operations owner | verified off-volume manifest, byte/inode/WAL admission receipts |
| Raw-evidence admission and critique contract bundle | Megaplan domain owner | installed-entrypoint negative and exact-set tests |
| Singleton `simple_fixer` topology | M11 recovery owner | immediate/three-hour same-occurrence conformance receipts |
| Effect-boundary closure | WBC/integration owners | zero-call bypass tests and ambiguity replay |
| Fenced recovery generation | Release Authority | generation manifest, CAS/fence, live-vector attestation, backup/rollback/forward-fix receipts |
| Fresh CL2 successor | Critique Ledger Run Authority | target-bound grant plus new identity inventory |
| Durable epic advancement | Independent verifier and Run Authority | accepted finalized/execution/commit/push/PR receipts and chain cursor advancement |

## Evidence index

### Cloud incident artifacts

- `/opt/megaplan-cloud/workspace/critique-ledger-accountability-v2-20260728/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260731-1411/state.json`
- same plan directory: `events.ndjson`, phase outputs, output audits,
  finalizer candidates, and feasibility/repair receipts
- `.megaplan/plans/.chains/chain-501c561132ce.json`
- `.megaplan/cloud-chain-critique-ledger-accountability-v2-20260728.log`
- global `.megaplan/repair-queue`
- `.megaplan/cloud-sessions/repair-data`
- `.megaplan/cloud-sessions/repair-data/escalations/escalations.jsonl`
- cloud session marker
  `.megaplan/cloud-sessions/critique-ledger-accountability-v2-20260728.json`

### Repository architecture and supporting history

- `.megaplan/initiatives/custody-control-plane/NORTHSTAR.md`
- `.megaplan/initiatives/custody-control-plane/briefs/m7-controlled-authoritative-writers.md`
- `.megaplan/initiatives/custody-control-plane/briefs/m10-safe-retry-recovery-and-effects.md`
- current-workspace M11 brief
  `.megaplan/initiatives/custody-control-plane/briefs/m11-conformance-and-legacy-retirement.md`
  (SHA-256
  `98d189f5fa23cbf40bfdce723a50f91c75b2052c2630046c9d7d61211557e5f3`)
- current-workspace runtime decision
  `.megaplan/initiatives/custody-control-plane/decisions/single-authoritative-runtime-history.md`
  (SHA-256
  `332208b824ffc0b8b98cfa7e6bcb5a4e04646b891316081b0ea731d3ee758540`)
- `origin/main` commit `25e407d78339cc6f13112aec770188997577e85a`,
  blob `evidence/ownership-decision-record.json` at
  `3899f1ca64395eb3550c64ba3543b2e2156e273d`
- superseded lineage:
  `.megaplan/initiatives/incident-control-plane/NORTHSTAR.md`
- deployed runtime anchor: `c7bcb06af536`
- planner normalization: `a7565c2e`
- runtime policy propagation: `70cae1d6ad`
- candidate graph admission/repeated-fingerprint circuit: `f72c9653d7`
- stale relaunch admission: `c5b613a441`
- adversarial review:
  `.megaplan/audits/critique-ledger-incident-sol-review-20260802.md`

## Adversarial-review disposition

GPT-5.6 Sol's initial verdict was **NO-GO**. Every blocking correction is
adopted in this revision:

- L2/meta-fixer/watchdog recovery was removed in favor of binding M11
  singleton-`simple_fixer` topology;
- cross-system atomicity and universal exactly-once claims were replaced with
  owner-local transactions, a reconciled saga, and first-class indeterminacy;
- prior M11 completion/promotion must be invalidated and re-proven;
- effect fallthrough, shadow/synthetic authorization, and blind provider retry
  are release blockers;
- admission now derives from raw target-bound evidence;
- storage admission precedes dispatch and reserves both bytes and inodes;
- critique uses separate attempt and semantic-result axes;
- the contract is an immutable release bundle, not a mutable registry;
- promotion is a fenced generation migration with migration-compatible
  rollback or forward-fix;
- a fresh successor is permitted only after old authority, leases, GLEKs,
  publication paths, and resume paths are fenced;
- evidence claims and installed-entrypoint tests are strengthened.

Three independent GPT-5.6 Luna forensic lanes also converged on the same root
account: fail-open admission, critique failure collapsed into zero findings,
accepted repair without claimable custody, runtime identity drift, and direct
notification fallback without durable effect custody. Their most important
correction to the operational story is explicit here: the many Discord
messages were a control-plane loop, not behavior produced by the critique
models themselves.
