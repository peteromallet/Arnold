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

The P2 control-plane findings are captured as the tracked, initiative-local
planning input [`evidence/p2-control-plane-mapping-20260804.md`](evidence/p2-control-plane-mapping-20260804.md).
F1, F2, and the custody ledger carry the corresponding acceptance items. The
source digest is recorded in that file; the broad recovery evidence tree is
intentionally not staged as a runtime or proof-map shortcut.

The relaunch-specific gaps are made explicit in the
[`incident-specific-control-amendment-20260804.md`](evidence/incident-specific-control-amendment-20260804.md)
(`incident-specific-control-amendment.v1`): all cloud/replay entry-point
containment, one WBC + Run Authority + Custody admission token,
occurrence/generation fencing, provider/credential and pinned-runtime
attestation, snapshot-first status and notification dedupe, projection
reconciliation, and legacy-session takeover rules.

Sequencing audit:
`.megaplan/subagents/critique-ledger-recovery/SEQUENCING/relaunch-cutline-luna-audit.md`.

Do not launch this chain until its content-addressed T6.2 handoff exists and all
launch preconditions pass through the installed authority boundary.

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
`.megaplan/subagents/critique-ledger-recovery/INTEGRATION/post-t1-5-fail-shortest-launch-route-luna.md`
(SHA-256 `abe9d64aeb0a35f81ec5fa72b804471a2b2307e34210b993163575a7090e2f47`).

The supervised canary must run with automatic fixer effects and notification
provider effects disabled fail-closed unless a later independently accepted
candidate proves them. The installed canary profile must also omit recovery and
notification capabilities, GLEKs, credentials, workers, timers, and direct
fallbacks, and must prove denial before mutation. Runner failure fences and
stops; it never invokes T1.5 or T1.10. Direct observation by the recovery
operator is allowed;
absence of automatic repair is not evidence that recovery is complete. The
canary handoff must record the exact disabled-effect posture and must not claim
T1.5, T1.4 notification custody, or production-owner completion.

The complete inventory of preserved and unfinished work is
[`UNFINISHED_WORK.md`](UNFINISHED_WORK.md). No dirty worktree, rejected commit,
or deferred interface may be silently consumed by the canary or dropped by this
epic.

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
- integration/generalization of the independently accepted T1.3 transport
  authority commit `2f1500aea1d03fbf13df5c796b17bd03d17bb79c`;
- generalized T1.4 graph repair and retry policy; and
- universal T1.6 effect-family migration plus the full release evidence matrix.

The operational candidate must record these as typed
`NOT_CONSUMED_OPERATIONAL_CANARY` exclusions with no capability or completion
claim. The T6.2 handoff must bind their exact deferred status and preserved
worktree/evidence locations so the epic cannot silently drop them.

## Launch and cloud-readiness boundary

This directory is a launch-ready *definition* only after the preconditions in
`chain.yaml` pass. In particular, a caller must supply and commit the
independently accepted T6.2 handoff and acceptance evidence; this epic does not
manufacture either artifact. The chain keeps `prerequisite_policy` and
`validation_policy` required, uses explicit F1→F8 dependencies, and stops on
failure or escalation. A cloud operator must separately select the canonical
project `cloud.yaml`/installed generation and run the normal cloud preflight;
the absence of an initiative-local cloud file is intentional until that
operator decision is made, so this epic cannot silently select a stale or dirty
checkout.
