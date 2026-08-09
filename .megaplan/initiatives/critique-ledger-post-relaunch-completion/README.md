# Critique Ledger post-relaunch completion epic

This epic begins only after the fresh v3 successor has passed the independently
verified finite-slice safe-canary gate (recovery task T6.2): fresh initialization
through the first owner-accepted transition strictly beyond v2's
`gated/finalize` cursor, followed by envelope expiry/stop.

It preserves the remainder of the 55-task recovery checklist without making
broad platform generalization, product completion, archival closeout, or
24h/72h/7d observation prerequisites for the bounded v3 finalize canary. F1/F2
block ordinary Critique authority only on the enabled-surface VJ24 failure
category; unrelated historical platform work remains explicitly deferred in
`UNFINISHED_WORK.md` and with the Custody Control Plane.

Canonical source:
`docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`.

The P2 control-plane findings are captured as the tracked, initiative-local
planning input [`evidence/p2-control-plane-mapping-20260804.md`](evidence/p2-control-plane-mapping-20260804.md).
F1, F2, and the custody ledger carry the corresponding acceptance items. The
source digest is recorded in that file; the broad recovery evidence tree is
intentionally not staged as a runtime or proof-map shortcut.

The evidence-first superfixer handoff for the current VJ24 occurrence is
[`evidence/immediate-fix-and-category-hardening-20260805.md`](evidence/immediate-fix-and-category-hardening-20260805.md).
It is canonical planning input for F1/F2: it defines the safe immediate route
(authoritative reconciliation, quarantine, and accepted migration) and asks the
epic to close the whole selector/binding/custody/observation/effect failure
category. It does not authorize a cloud launch and does not replace the T6.2
handoff preconditions.

The current r5 occurrence may advance only through an independently accepted,
content-addressed migrated-child/new-attempt receipt embedded in the T6.2
handoff. The prelaunch receipt must preserve r5/VJ24 as
`QUARANTINED_IMMUTABLE`, set `same_occurrence_resume=false`, join fresh Run
Authority, Custody and WBC identities to the parent, bind the selector/result
contract, and prove the CAS cursor advance. The migrated child subsequently
produces accepted VJ24 plus T18/T23 envelopes; those post-launch results are
also required in the final T6.2 handoff. Generic resume is forbidden.

The relaunch-specific gaps are made explicit in the
[`incident-specific-control-amendment-20260804.md`](evidence/incident-specific-control-amendment-20260804.md)
(`incident-specific-control-amendment.v1`): all cloud/replay entry-point
containment, one non-bearer admission receipt over the WBC + Run Authority + Custody action envelope,
occurrence/generation fencing, provider/credential and pinned-runtime
attestation, snapshot-first status and notification dedupe, projection
reconciliation, and legacy-session takeover rules.

The anti-overbuild boundary is explicit in the
[`architecture-fit-and-minimality-gate-20260804.md`](evidence/architecture-fit-and-minimality-gate-20260804.md)
(`architecture-fit-minimality-gate.v1`). It makes the existing Custody Control
Plane the substrate, assigns ownership before implementation, requires one
thin end-to-end failure proof per sprint, and requires retirement/expiry for
compatibility paths. It deliberately adds a gate, not another milestone or
authority system.

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

F1 category-blocking scope is limited to:

- the T1.5 pass-3 deletion/rollback failure: coordinated erasure of all mutable
  attempt/claim/effect projections can mint a second attempt and effect;
- Run Authority-owned one-shot grant/CAS/idempotency, Custody-owned occurrence/
  lease/epoch and WBC-owned attempt/effect evidence outside caller projections;
- an authenticated fixed-socket adapter that consumes those owners and
  lifecycle-owned accepted-state/due semantics without minting a fourth owner;
- immutable execution binding plus accepted migrated-child lineage;
- host-side coherent owner observation with UNKNOWN/no-action semantics; and
- occurrence/state-version notification intent/effect custody with no blind
  redispatch.

F2 category-blocking scope is limited to:

- one content-addressed selector/task-output and accepted-result contract;
- one non-bearer canonical action-envelope receipt on every retained
  state-mutating Critique entry point/effect class;
- role-scoped provider-route/credential capability attestation and pinned
  runtime identity; and
- the exact VJ24 cardinality replay and category release decision.

The 28-module/741-case retirement sweep, platform-wide T1.7 capacity/ENOSPC,
full T1.10 rotation/reminder/child-key policy, universal unrelated route/effect
migration, exhaustive provider canaries and broad zero-debt release matrix are
preserved as `DEFERRED_NONBLOCKING` custody items. They are neither r5/T6.2
relaunch gates nor prerequisites for F3 while affected surfaces remain denied.

The operational candidate must record these as typed
`NOT_CONSUMED_OPERATIONAL_CANARY` exclusions with no capability or completion
claim. The T6.2 handoff must bind their exact deferred status and preserved
worktree/evidence locations so the epic cannot silently drop them.

## Launch and cloud-readiness boundary

This directory is a launch-ready *definition* only after the preconditions in
`chain.yaml` pass. In particular, a caller must supply and commit the
independently accepted T6.2 handoff and acceptance evidence, including the r5
quarantine/migrated-lineage receipt; this epic does not manufacture those
artifacts. `contains_text` checks are only fail-fast guards: installed authority
validation must verify the schema, identities, digests, signatures, owner
revisions and causal joins before launch. The chain keeps `prerequisite_policy` and
`validation_policy` required, uses explicit F1→F8 dependencies, and stops on
failure or escalation. A cloud operator must separately select the canonical
project `cloud.yaml`/installed generation and run the normal cloud preflight;
the absence of an initiative-local cloud file is intentional until that
operator decision is made, so this epic cannot silently select a stale or dirty
checkout.

## Sol epic review record — 2026-08-05

Verdict: the root diagnosis is correct, but the prior draft was too broad in its
pre-F3 historical-debt cutline and too narrow in executable VJ24/migration
acceptance. This review:

- machine-gated immutable r5 quarantine, prohibited same-occurrence resume and
  independently accepted migrated lineage in `chain.yaml`;
- assigned grants/CAS to Run Authority, occurrences/epochs to Custody, boundary
  and attempt/effect evidence to WBC, and kept adapters/observers non-authoritative;
- put exact binding/repair/observer/notification criteria in F1 and exact
  selector/result/admission/replay criteria in F2;
- superseded the historical attempt-9 same-session runbook without deleting it;
  and
- preserved broad historical platform and durability work as explicit deferred
  custody rather than immediate relaunch or ordinary-execution blockers.

The epic is a chain-ready definition after these documentation edits, but it is
not currently launchable: the authoritative migrated-lineage and T6.2
acceptance artifacts do not yet exist.

## Sol launch-cutline review — 2026-08-05

The second Sol review is recorded at
`.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-sol-launch-cutline.md`.
It makes the immediate boundary explicit:

- the first child may use the existing `task_contract_hash`; the full
  cross-consumer `selector_task_output_contract.v1` belongs to F2;
- missing selectors explicitly declared in a finalized task write-set may defer,
  but missing undeclared selectors must fail, and deferred validation must rerun
  after an accepted task result;
- the first-child migration needs a real Run Authority integer journal writer
  and atomic compare-and-append, canonical Custody/WBC writes, deterministic
  idempotency, and crash recovery; synthetic owner records and the generic
  override workflow are forbidden;
- the prelaunch receipt proves parent quarantine/admission and the integer
  parent CAS; T6.2 separately proves the child lifecycle advance and accepted
  VJ24/T18/T23 results.

The aborted migration sprint remains evidence only. F1 owns generalized
lineage/recovery/observer/notification custody; F2 owns shared selector/result
enforcement, entry-point containment, provider/runtime parity, and exact replay.
The follow-up chain now requires separate `parent_ra_journal_cas` and
`child_lifecycle_advance` acceptance fields so these two horizons cannot be
conflated.
