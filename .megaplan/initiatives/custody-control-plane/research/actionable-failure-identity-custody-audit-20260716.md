---
type: research
date: 2026-07-16
schema: custody-control-plane-actionable-failure-identity-audit-v1
status: complete
classification: independent-class-wide-audit
raw_run: subagent-20260716-141251-24e3b08c
source_message: msg_38f029a87998
---

# Actionable failure identity and claimability audit

## Result

The class is confirmed. The codebase has strong, tested identity custody inside
critique, Run Authority execute aggregation, active repair claims, incident
projection, and resident delivery. The seam between an actionable finding and
repair-queue acceptance is not equivalently protected.

`enqueue_repair_request` can durably accept a record that has neither a
canonical blocker/occurrence identity nor required evidence and retry metadata.
`iter_repair_requests` validates only four top-level fields. Later,
`project_repair_custody` mechanically reconstructs a blocker fingerprint from
the request's lossy problem signature plus mutable current plan/target state.
`claim_active_repair_request`, correctly, refuses an empty blocker ID. An
accepted request can therefore be actionable yet intrinsically unclaimable.

There is a second confirmed identity defect: pending-request coalescing compares
only `problem_signature_key`, while `request_id_for` includes `session`.
Equivalent signatures from different sessions can coalesce across custody
targets. The second request marker is not written; only a coalescing decision
for its computed request ID remains. This can suppress one session's actionable
failure behind another session's request.

The target advanced during this audit through
`9ed382d09c98633663d9220a9891bf7b48c87e7c`. Concrete M6 commits
`0feaa9e2475cda4e84c78eff6cc826319710bd8a` and `98333caae5` protect
one important subtype: a deterministic phase-contract failure with a phase but
no task now receives `blocked_task_id=phase:<phase>`, and watchdog mechanical
relaunch is fenced until repair custody is acquired; replay also retains the
phase retry strategy after mutable latest-failure state clears. The class-wide defects
below remain reproducible after those changes, including cross-session
coalescing and accepted sparse requests with no blocker identity.

No runtime code was changed in this audit. These surfaces are explicitly owned
by the concrete M6/superfixer implementation in
`workflow-boundary-contracts/handoff/superfixer-stack-closure-task-20260713.md`
and by Custody Control Plane M6/M8/M10. Competing edits would violate the
non-overlap constraint. The exact migration and conformance suite are recorded
in the accompanying decision and handoff.

## Method and canonical artifacts reused

This audit searched initiative slugs, titles, descriptions, tickets, docs,
source, wrappers, and tests for repair, blocker, flag, finding, claim, evidence,
identity, custody, replay, and aggregation vocabulary. The ticket CLI itself
could not complete because a legacy ticket has invalid YAML frontmatter, so the
18 ticket files were searched directly. Related canonical artifacts were:

- `custody-control-plane/research/critique-custody-contract-20260715.md` — the
  landed critique/gate/finalize/execute identity contract.
- `custody-control-plane/briefs/m6-authority-contract-and-residual-inventory.md`
  and `research/wbc-boundary-adoption-matrix.md` — canonical universal inventory
  and ownership rules.
- `workflow-boundary-contracts/handoff/superfixer-stack-closure-task-20260713.md`
  — concrete M6 incident owner and the original accepted/unclaimed request.
- `progress-auditor-stage-metrics/research/auditor_signal_swarm_synthesis_20260704.md`
  — missing-evidence and false-green telemetry requirements.
- Tickets `01KTPVSH8X04XE0D122M0V0712` (silent neutral-executor halt),
  `01KTPVTANTY1HDG8PJGSAK5Z25` (typed seam not universally invoked), and
  `01KTH21D7XAKZDHNJQPHKZ5QTD` (registry/schema-normalizer drift).

Raw delegation evidence is this resident run,
`subagent-20260716-141251-24e3b08c`, launched from source message
`msg_38f029a87998` in conversation `rconv_85a1c2bfd5f1`.

The final audit tree is based on target revision
`9ed382d09c98633663d9220a9891bf7b48c87e7c`; the recorded launch base was
`056e8160e410007186e984459b005ef2fe080ef3`.

## Identity model required at every boundary

These identities are related but must not be collapsed:

| Identity | Meaning | Stability requirement |
| --- | --- | --- |
| `finding_id` | One producer observation | Stable for the same producer fact and version; includes producer provenance. |
| `action_target_id` / `blocker_id` | The exact thing on which custody is serialized | Canonical before persistence; never reconstructed from a later projection. |
| `occurrence_id` | One actionable occurrence of a target | Includes run/session, target snapshot, predicate/evidence digest, and causal predecessor. |
| `request_id` | One durable request to acquire repair custody | Deterministic from occurrence plus policy version; not prose or timestamp. |
| `claim_id` / `custody_epoch` | One fenced lease on the action target | Unique, renewable, and tied to request, actor, and fence. |
| `attempt_id` | One execution attempt under a claim | Exactly one terminal outcome; replay-idempotent. |
| `decision_id` | One acceptance/coalesce/reject/terminal decision | Idempotent from request, decision kind, and causal input, not wall-clock time. |

An actionable record is claimable only if the persisted record itself contains
all identity and claim-policy inputs. A reader may verify them against current
state; it may not manufacture them.

## Evidence-led producer/consumer inventory

Classification is one of `CONFIRMED DEFECT`, `PROTECTED`, or
`UNKNOWN / MISSING TELEMETRY`.

| Boundary | Producers -> consumers | Classification | Evidence and consequence |
| --- | --- | --- | --- |
| Critique worker output | focused workers -> parallel reducer | PROTECTED | `parallel_critique._source_flags_with_id_map` assigns canonical IDs, retains producer IDs/source lens, rejects blank evidence and duplicate local/canonical identities. |
| Critique aggregation | parallel reducer -> `critique.json` / custody receipt | PROTECTED | The reducer preserves flags and writes producer artifacts; `critique_custody` binds exact hashes and zero-loss counts. Tamper, missing receipt, and duplicate/partial mappings are covered by `test_parallel_critique.py` and `test_critique_custody.py`. |
| Gate and revise | critique receipt/flag registry -> gate/revise | PROTECTED | Gate validates receipt and registry membership before dispatch; clearance requires evidence-backed invalidation or a verified plan mutation. |
| Finalize and execute admission | clearance -> final graph -> execute | PROTECTED | Final coverage binds every finding to tasks and exact graph hash; mutated/missing custody blocks execute. |
| Execute fanout/aggregation | batch workers -> Run Authority reducer | PROTECTED | `DispatchIdentity`, attempt, evidence, claim, idempotency, fence, and result envelopes are typed. Duplicate/conflicting claims are quarantined and crash/replay projections are deterministic in Run Authority tests. |
| Review parallel worker identity | review workers -> review reducer | CONFIRMED DEFECT | `review.parallel._parse_parallel_review_result` accepts the worker-returned check ID without rebinding it to `unit.extra.check_id`, unlike critique. Verified/disputed IDs are merged as strings without producer-map validation. A worker-local/mistyped ID can survive aggregation. |
| Review blocker materialization | review payload -> rework routing | CONFIRMED DEFECT | Review normalization creates several actionable rework targets with `id: None`; `_normalize_review_blockers` permits blocker identity to be only an optional `flag_id` and otherwise routes on evidence-shaped content. The record can block/rework without a canonical durable blocker ID. |
| Semantic-health findings | boundary checker -> cloud projection | CONFIRMED DEFECT | `SemanticFinding` requires finding/boundary/description but makes `evidence_ref`, `contract_ref`, and `authority_ref` optional even for severity `error`. Thus an actionable semantic finding can lack claim evidence. |
| Semantic aggregation | finding list -> fingerprint/counts/status/meta-repair | CONFIRMED DEFECT | `compute_finding_fingerprint` hashes ID, boundary, severity, and diagnostic code only. It does not reject duplicate IDs or bind evidence/provenance/contract version. Evidence changes can look like unchanged recurrence; duplicate/lost producer rows are not distinguished from legitimate aggregation. |
| Lifecycle failure capture | `auto._record_lifecycle_failure` -> repair queue | CONFIRMED DEFECT | `_enqueue_lifecycle_failure_request` catches every exception and emits only a best-effort warning. The plan can be durably blocked while required repair custody persistence failed. |
| Human-gate producer | neutral human gate -> repair queue | CONFIRMED DEFECT | `enqueue_human_gate_repair_request` intentionally emits empty gate/task fields and no durable blocker/evidence cursor. Queue intake still returns accepted. Human-required may be correct policy, but the accepted record does not prove its target or claimability. |
| Supervisor-exit producer | `cloud.supervise` -> repair queue | CONFIRMED DEFECT | Resolver errors deliberately fall back to empty plan identity; the request can have empty milestone and blocked-task fields and no evidence cursor. This is safe from wrong-target mutation only if intake quarantines it, which it currently does not. |
| Watchdog producer | plan/current-target projection -> repair queue | CONFIRMED DEFECT | The wrapper enqueues from `latest_failure` with several fields allowed empty, then reruns projection to reconstruct identity. This makes a projection a prerequisite for claimability instead of verification. |
| Deterministic phase-contract subtype | phase failure -> custody classifier/watchdog/replay | PROTECTED FOR THIS SUBTYPE | Target commits `0feaa9e247` and `98333caae5` synthesize the explicit canonical scope `phase:<phase>` when task identity is inapplicable, fence mechanical relaunch pending a claim, and retain the retry strategy after replay clears mutable failure state. Focused classifier and watchdog regressions cover it. This does not validate general sparse requests or queue schema. |
| Manual terminal retrigger | frozen plan evidence -> repair queue/trigger | PROTECTED LOCALLY / DEFECT AT QUEUE | The manual trigger verifies authoritative target, state hash, history index, and review artifact hash and writes a receipt. The canonical queue stores the evidence cursor only under unvalidated `target`; claimability is not enforced by the request schema. |
| Six-hour true-stall producer | deterministic auditor + L3 gate -> repair queue | PROTECTED LOCALLY / DEFECT AT QUEUE | It requires a session and escalation ID and supplies evidence cursor/retry budget. These fields are nested under `target`, not required by queue intake and not part of the canonical request/occurrence identity. |
| Repair request identity | all producers -> queue persistence | CONFIRMED DEFECT | `request_id_for` hashes session, normalized signature, and redacted hint hash; the record contains no blocker/occurrence ID. Prose variants fragment request identity even when the action target is unchanged. |
| Request schema/read | JSON marker -> queue consumers | CONFIRMED DEFECT | `iter_repair_requests` checks only `schema_version`, `kind`, `request_id`, and `problem_signature`; it does not validate version value, canonical hash, target, blocker, evidence cursor, retry policy, provenance, or claimability. |
| Pending coalescing | new request -> existing pending marker | CONFIRMED DEFECT | `find_pending_by_signature` compares signature key only, not session/action target/occurrence. Cross-session same-signature work can be suppressed. The coalesced request marker is never written. |
| Custody projection | requests + mutable plan/current target -> classifier | CONFIRMED DEFECT | `project_repair_custody` fabricates a request-specific plan/target view, calls `blocker_fingerprint_from_evidence`, and may adopt the first reconstructed blocker when the live blocker is absent. It also derives retry max (`1` or `3`) rather than consuming a persisted policy. |
| Blocker fingerprint v2 | compatibility artifacts -> blocker ID | CONFIRMED DEFECT | The v2 TypedDict documents acceptance, evidence, runtime, custody, retry, and predecessor fields as optional with empty defaults. Only v1 fields are required, so `v2` does not guarantee the metadata its version claims to carry. |
| Active repair claim | custody projection -> claim lock | PROTECTED | `claim_active_repair_request` requires non-empty blocker/request/actor/session, keys the lock by blocker, records both identities, detects contention/staleness, and fences managed-run binding. |
| Watchdog claim handoff | classifier -> wrapper -> managed agent | PROTECTED WHEN CANONICAL FUNCTION PRESENT | Production `claim_active_repair_launch` rejects missing blocker/request identity; managed launch is later matched to both links. Extracted test/compatibility harnesses can omit the function, and the dispatch case treats empty status as historical success; universal wrapper adoption remains unproven. |
| Dispatch attempt | claim -> managed child | PROTECTED | `write_dispatch_attempt` requires request, blocker, actor, layer, command, positive PID, managed run, and manifest. Active-claim binding checks request/blocker/run/PID under a lock. |
| Unclaimed handling | accepted request -> retry/alert decisions | PROTECTED BUT NOT SELF-STARTING | Bounded `claim_retry` and `claim_alert` records exist. They only help after a consumer observes the request; malformed/unclaimable markers have no guaranteed scheduler-owned transition into this path. |
| Meta-repair recurrence | repair data/projections -> L2 classifier | UNKNOWN / MISSING TELEMETRY | Recurrence logic has tests for unchanged semantic fingerprints and stale evidence, but no end-to-end proof that every actionable finding maps to one canonical occurrence/request/claim across wrapper, resident, and cloud runtime revisions. |
| Repair verdict | attempt -> queue decision | CONFIRMED DEFECT | `write_repair_verdict_decision` accepts an empty blocker ID and embeds identity/path in a reason string rather than typed fields. A terminal disposition can therefore be unjoinable except by prose parsing. |
| Incident ledger/projection | watchdog/repair events -> incident/problem projections | PROTECTED AS PROJECTION | Incident/problem IDs, malformed/dangling detection, replay stability, and projection rebuild are tested. The projection is correctly not repair authority, so it cannot repair missing queue identity. |
| Local/resident/cloud status | canonical state + repair projection -> operator views | UNKNOWN / MISSING TELEMETRY | Status exposes accepted-unclaimed and missing-custody signals, but no denominator proves all actionable producers entered the queue. Absence can still render as zero rather than `producer_coverage_unknown`. |
| Resident message/turn/outbox | Discord event -> turn -> outbound/provider | PROTECTED | Resident store identities and deterministic idempotency keys, restart claims, provider acceptance ambiguity, immutable delegation provenance, and delivery replay are heavily tested. |
| Resident escalation resume | escalation ledger -> resident confirmation -> repair lock | UNKNOWN / MISSING TELEMETRY | Escalation ID and confirmation request exist, but the default lock is session-scoped and there is no proof joining escalation occurrence, blocker, claim epoch, and resumed repair attempt to the cloud request contract. Do not collapse this with the repair queue without a migration row. |
| Restart/replay of queue decisions | marker/decision files -> consumers | UNKNOWN / MISSING TELEMETRY | Request files are write-once and ordered. Decision IDs include `created_at`, so replay of the same semantic decision can append a distinct decision. No property test proves identical projection under prefix-crash + duplicate/reordered request/decision/attempt streams. |
| Repair dispatch conformance harness | central queue API -> classifier fixtures | UNKNOWN / MISSING TELEMETRY | On final target `9ed382d09c`, the three new phase-identity/replay/watchdog tests pass, but 12 older tests in `test_repair_dispatch_classifier.py` fail because they still call `enqueue_repair_request` without required `queue_root`. The invariant is implemented for the new subtype, but class-wide classifier conformance is not currently a green gate. |

## Confirmed suppression chains

### Accepted but unclaimable

1. A producer emits a sparse problem signature and queue intake writes
   `accepted`.
2. The request has no persisted blocker/occurrence identity.
3. Custody projection attempts to reconstruct a v1 fingerprint from current
   state. Any empty required field makes normalization return `None`.
4. The classifier has no canonical blocker ID, while active claim rejects an
   empty ID.
5. Unless a later auditor notices accepted-unclaimed state, automation stops.

### Cross-session coalescing suppression

1. Session A has a pending request for signature S.
2. Session B emits the same signature S; its canonical request ID differs
   because request hashing includes session.
3. `find_pending_by_signature` ignores session and returns A.
4. B is marked `coalesced`, but its request marker is not written.
5. Consumers scoped to B cannot claim A, while B has no persisted claimable
   request. A decision can look like successful dedupe even though custody was
   lost.

### False recovery through projections

1. A semantic finding retains the same ID while evidence or target revision
   changes.
2. The semantic fingerprint remains unchanged because evidence/provenance are
   excluded.
3. A status/meta-repair consumer sees recurrence or apparent stable recovery
   without knowing whether evidence coverage is complete.
4. Missing producer coverage has no mandatory `UNKNOWN` signal, so suppression
   can be indistinguishable from an empty/healthy finding set.

## Required telemetry

Every producer and consumer should emit counters or durable events keyed by
contract version and runtime revision:

- `actionable_produced_total`
- `actionable_persisted_total`
- `actionable_quarantined_total{reason}`
- `actionable_claimable_total`
- `claim_attempted_total`, `claim_acquired_total`, `claim_terminal_total`
- `coalesced_total{same_occurrence=true|false}`
- `projection_reconstruction_attempt_total` (must reach zero after migration)
- `schema_unknown_total`, `missing_evidence_total`, `producer_coverage_unknown`
- age histograms from production -> persistence -> claim -> attempt -> terminal

The invariant is a conservation equation per producer/runtime revision:

`produced = persisted_claimable + explicitly_quarantined`

and, for every accepted request older than the dispatch SLO:

`accepted = claimed_or_terminal + durable_claim_alert`.

An empty producer coverage set is `UNKNOWN`, never healthy zero.

## Concrete repair-intake implementation follow-up

The authorized implementation run rooted at source message `msg_38f029a87998`
confirmed the audit's queue-boundary diagnosis against the raw M6 plan
`/workspace/custody-control-plane-20260714/Arnold/.megaplan/plans/m6-exact-contract-and-20260716-1303/`.
The phase state (captured SHA-256
`71f6737808c524f9058e4fc0ae82a9345bff2577f443f4730d75fbde83cb57db`)
records the third identical critique contract failure. The accepted queue marker
`844ad06e9a0dd0bd2af37b53e5c8f4021b9117adfae2b8d4756164281450bdd2`
(captured SHA-256
`ac2b43d6613d4ad06de53b8b6b15f8cdf7c66b1670b9a8c7e452c6d442e5652c`)
contains an empty `blocked_task_id` and no blocker fingerprint/ID. Its two later
claim decisions at 2026-07-16T14:24:48Z and 2026-07-16T14:27:58Z both say
`canonical blocker_id missing`; no matching claim or attempt exists. The full
evidence/inference/telemetry split and individual producer-artifact hashes are
curated in
`../../megaplan-maintenance/research/custody-control-plane-superfixer-recovery-plan-20260716.md#M6-critique-repair-identity-follow-up--2026-07-16`.

The concrete implementation closes the authoritative intake invariant without
claiming the broader proposed `ActionableRecordV2` migration complete:

- queue intake canonicalizes missing task scope to `phase:<phase>` or
  `plan:<plan>`, allocates and persists a deterministic blocker fingerprint/ID
  before acceptance, and rejects direct identity-free `accepted` decisions;
- lifecycle failure capture carries the persisted retry strategy into the
  immutable request target;
- projection prefers the accepted record's persisted identity and fails closed
  on conflicting active identities instead of manufacturing claim authority;
- identity-free legacy markers remain byte-preserved and non-authoritative for
  dedupe; replay creates a deterministic claimable successor rather than
  rewriting or coalescing onto the legacy marker;
- pending coalescing requires matching session and blocker identity, closing
  the audit's confirmed cross-session suppression chain;
- the exact deterministic phase-contract shape is machine-repairable only with
  current-target evidence, and the real trigger wrapper proves the persisted
  blocker ID reaches claim and managed autofixer launch.

Focused regression coverage includes parallel critique aggregation, repeated
worker-local flag IDs, blank/missing evidence, lifecycle intake, immutable
persistence/reload, deterministic replay, legacy successor allocation,
cross-session non-coalescing, blocker-scoped claim, and end-to-end trigger
launch. The broader review/semantic/ActionableRecordV2 gaps inventoried above
remain sequenced work; this implementation neither reconstructs the historical
M6 record nor treats it as newly claimable.
