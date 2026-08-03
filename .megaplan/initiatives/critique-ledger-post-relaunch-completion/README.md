# Critique Ledger post-relaunch completion epic

This epic begins only after the fresh v3 successor has passed the independently
verified finite-slice safe-canary gate (recovery task T6.2): fresh initialization
through the first owner-accepted transition strictly beyond v2's
`gated/finalize` cursor, followed by envelope expiry/stop.

It preserves the remainder of the 55-task recovery checklist, including deferred
platform-wide hardening, without making that generalization, product completion,
archival closeout, or 24h/72h/7d observation prerequisites for the bounded v3
finalize canary.

Canonical source:
`docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`.
The tracked copy is the complete 55-task source checklist, preserved as evidence
and work custody. Its original all-predecessors launch cut is not current launch
authority; the bounded zero-recovery cut and this epic's typed handoff are.

Sequencing audit:
`.megaplan/subagents/critique-ledger-recovery/SEQUENCING/relaunch-cutline-luna-audit.md`.
That audit is retained for task-by-task rationale but its conclusion that the
entire T1/T2/T3/T4/T5 portfolio blocks the finite canary is superseded. See
`supersession-index.json`.

Do not launch this chain until its content-addressed T6.2 handoff exists and all
launch preconditions pass through the installed authority boundary.
The parseable launch preconditions establish file/tracking presence only; F0
performs the strict semantic handoff admission before any F1 work. F0 completes
none of F1-F8. Incident operators must follow [`RUNBOOK.md`](RUNBOOK.md); generic
cloud deploy/chain/supervision routes are forbidden for this recovery.

## Operational-relaunch recut handoff — 2026-08-02

The supervised v3 canary is intentionally limited to the operational route
recorded in
`.megaplan/subagents/critique-ledger-recovery/INTEGRATION/minimal-operational-relaunch-map-sol.md`
(original SHA-256
`fd1a33ba58566aa126e170643f59a39bca13972e5919d0a338403b50c169312e`),
as corrected by the post-T1.5-failure route adjudication. The original
four-commit wording is superseded: T1.5 operational pass 3 is **rejected**, not
accepted, and a typed SSH lifecycle/capacity/durability preflight is now a
direct prelaunch dependency.

Corrected launch-route authority:
`.megaplan/initiatives/critique-ledger-post-relaunch-completion/finite-canary-operational-route.json`
(SHA-256 `b7bd81ddf77642f5dc220b2977e5ee07865484189f6c9f97758105f6e3396478`).
It consumes the earlier post-T1.5 shortest-route rationale only together with
the newer non-root privilege, mount, resource, effect and honest model-evidence
bindings. The rationale document alone has no launch authority.

The supervised canary must run with automatic fixer effects and notification
provider effects disabled fail-closed unless a later independently accepted
candidate proves them. The installed canary execution surface must make those
paths unreachable: no recovery/notification capability or credential is passed
to the finite runner, and no recovery worker, timer, resident, watchdog, direct
fallback, or notification provider is started. The finite image may still
contain dormant shared-package source; physical package minimization is F1
follow-up work and is not claimed by the canary. Deny-before-mutation and
process/credential absence proofs remain prelaunch requirements. Runner failure
fences and stops; it never invokes T1.5 or T1.10. Direct observation by the recovery
operator is allowed;
absence of automatic repair is not evidence that recovery is complete. The
canary handoff must record the exact disabled-effect posture and must not claim
T1.5, T1.4 notification custody, or production-owner completion.

The complete inventory of preserved and unfinished work is
[`UNFINISHED_WORK.md`](UNFINISHED_WORK.md). No dirty worktree, rejected commit,
or deferred interface may be silently consumed by the canary or dropped by this
epic.

Machine-readable custody is frozen in [`custody-manifest.json`](custody-manifest.json),
including immutable B8-B25 failure history, B26's independent Sol GO, the
failed no-canary live transaction, and B27's passing smoke pending independent
Sol acceptance. Terminal-operation and live-receipt reconciliation remain
pending.
Conflicting or stale launch instructions are retired by
[`supersession-index.json`](supersession-index.json). Human prose never
overrides those typed dispositions.

F1 explicitly inherits:

- the T1.5 pass-3 deletion/rollback failure: coordinated erasure of all mutable
  attempt/claim/effect projections can mint a second attempt and effect;
- a production effect-owner/WBC monotonic consumed-grant/idempotency authority
  outside caller-writable SQLite, including authenticated reconciliation of
  missing local state and no redispatch after deletion or rollback;
- the production fixed-socket owner operations missing from the bounded model:
  owner-issued occurrence target/ref, quiet transition, due selection,
  `accepted_state_version`, and exact-occurrence wrapper handoff;
- generic T1.5 dynamic recovery-topology closure beyond the installed
  operational resident/fixer path;
- restoration of meaningful subject-specific retirement/no-side-effect proofs
  for all 28 historical modules / 674 functions / 741 cases;
- platform T1.7 storage adoption and remaining T1.8/T1.9 owner/store
  generalization; and
- full T1.10 notification key rotation, reminder/chunk/child-key policy and
  auxiliary-writer retirement.

F2 explicitly inherits:

- the paused T1.1 universal admission repair and its remaining validation;
- the paused T1.2 typed critic-attempt implementation;
- provider/server-attested model identity. The finite canary may bind the exact
  requested argv and root-custodied Codex CLI `turn_context`, but must label it
  `codex_cli_turn_context`; it is not cryptographic proof of the backend model;
- integration/generalization of the independently accepted bounded Stage-A
  T1.3 authenticated raw target-bound transport component at
  `2f1500aea1d03fbf13df5c796b17bd03d17bb79c`; this is not T1.2 attempt/model
  completion, installed production authority, release authority, or cloud
  launch authority;
- generalized T1.4 graph repair and retry policy; and
- universal T1.6 effect-family migration plus the full release evidence matrix.

The operational candidate must record these as typed
`NOT_CONSUMED_OPERATIONAL_CANARY` exclusions with no capability or completion
claim. The T6.2 handoff must bind their exact deferred status and preserved
worktree/evidence locations so the epic cannot silently drop them.

## Capacity and isolation cut

T0.3 is intentionally split rather than silently waived:

- **Prelaunch bootstrap:** re-observe the stopped predecessor and exact runtime,
  fence every background path, reclaim only typed dangling builder cache, prove
  the receipt reserve/free-space floor, and create one fresh mode-0700 canary
  bind source. Mount only that child at `/workspace`; never expose the preserved
  parent or sibling workspaces to the model. The trusted runner remains root,
  but every model/tool subprocess runs as a dedicated unprivileged UID with
  no-new-privileges, no effective capabilities, fresh phase-local Codex state,
  root-owned non-writable source/engine/state, and only one precreated output
  inode writable. Bind the exact host source, access identity, privilege vector,
  and container destination into deploy/run/stop receipts.
- **F1 follow-up:** durable reserved-capacity ownership, quotas/watermarks,
  ENOSPC/corruption/crash behavior, lifecycle retention, broad Docker/storage
  reclamation, and physical minimal-image enforcement.

The bootstrap may not delete the stopped predecessor, historical workspace,
images, named volumes, or arbitrary cache. A capacity failure remains a hard
NO-GO and the predecessor remains stopped and recoverable.

## Prelaunch and stable-exit cut

The closed-schema `prelaunch_release_gates` in `custody-manifest.json` are
T6.2 prerequisites, not F1 work. They require an independently accepted exact
finite-canary candidate whose implementation/manifest identities live only in
the gate's accepted evidence; a fixed root-owned symlink-free host control-state
directory;
bounded all-eight-unit settlement and crash-safe fencing before reclaim;
durable failure/reconciliation evidence; the built-image four-phase smoke;
fresh live capacity/predeploy authority; a finalized-then-stopped finite canary;
and remotely anchored custody reconstructed from a fresh clone. Pending null
evidence is deliberately non-authoritative and keeps the route closed.

The global containment marker v2 is deliberately transaction-independent. It
contains exactly `schema/profile/scope/active` and is published only after
durable unit/job/session/process proof. The same canonical marker may support a
fresh retry only after that containment is durably re-proved. Transaction
identity belongs instead to each attempt's intent and apply/verify/failure
receipts, which bind `transaction_id/transaction_digest/action`. Before the
trusted directory opens and the intent persists, failure performs no mutation,
fails closed and is captured by the supported caller error path; after intent,
every partial or post-prune failure requires a durable O_EXCL host receipt.

The follow-up chain may start only after both the strict finite-canary receipt
and `stable-exit-receipt.json` exist. Stable exit means the exact v2 predecessor
is preserved, stopped and persistently fenced; the exact v3 successor reached
`finalized` and then stopped; no recovery/notifier/resident/watchdog/timer job,
session or process remains; the exact source/tree/image and live receipt set are
bound; and the updated follow-up authority is pushed under namespaced custody,
prelaunch/postcanary tags and a runnable integration ref with an independently
accepted fresh-clone reconstruction receipt.
