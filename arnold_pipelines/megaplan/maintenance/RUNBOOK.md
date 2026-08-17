# Maintenance canary and rollback runbook (M3 Step 14)

> **Current posture — read first.** This runbook does **not** imply current approval.
> Every handoff row in
> `arnold_pipelines/megaplan/maintenance/handoffs.json` is
> `pending_human_approval`, the M3 enforcement gates are **default-off**, and
> automatic effects remain **disabled**. All procedures below are report-only
> until the human gates in [Promotion](#promotion) are individually satisfied
> and an approved operator signs the controlled installed-runtime canary.
> Observation, ledger append, replay, and reporting remain available while
> action is disabled; a projection, receipt, or report never authorizes an
> effect by itself.

## Purpose

This runbook is owned by Maintenance and codifies how the M3 installed-runtime
canary is rehearsed (report-only), promoted (only after human approval), run
(checkpoints), rolled back (forced rollback and kill-switch), and evidenced —
entirely through the EXISTING owner seams. It consumes, and never recreates:
M7 occurrence/lease/epoch and action validator, M6A WBC attempts, M10
recovery/effect allowlist and ledger, M11 installed-runtime identity and
verifier evidence, and the `delegate_to_simple_fixer` unified fixer seam
(SD1). Only the cloud adapter (`maintenance_recovery`,
`maintenance_canary`) may call the canonical owner seams; the Maintenance
domain modules remain reference-only.

## Prerequisites

Before any canary procedure, ALL of the following must hold. A missing
prerequisite is a stop condition; never guess an open value.

1. **Approved handoff digests (open human gate).** Every consumed source must
   resolve `ACCEPTED` from `handoffs.json` with a recorded content digest,
   recorded `ApprovalEvidence` (approver, UTC instant, evidence ref, digest),
   and — for M6A — approved WBC incarnation/restore/high-water coordinates.
   Today all rows are `pending_human_approval` (see
   [Exact handoff digest reporting](#exact-handoff-digest-reporting)); the
   occurrence-bound request additionally requires the `M7` and `M6A` rows
   (`REQUEST_HANDOFF_IDS`) to resolve `ACCEPTED`.
2. **Distinct verifier principal (open human gate).** The approved service
   principal that authors verification events, with durable
   `VerifierProvenance` (principal, runtime/source digests, observation time,
   direct owner-source read references). The verifier must be distinct from
   every repair producer; process separation or a self-declared label is
   insufficient.
3. **Inherited lease policy (open human gate).** The M7 lease duration and
   renewal-grace policy is INHERITED from the canonical M7 lease store — M3
   never hard-codes a competing lease policy and never reimplements a lease
   store. The approved policy values are an open human gate; until supplied,
   the scheduler only carries the inherited lease id/epoch/fencing token
   verbatim and every authority-increasing edge re-reads current authority.
4. **Safe-repair allowlist (open human gate).** The approved M10 repair-effect
   allowlist entries for the canary target's effect classes (claim, source
   change, installation, retrigger). An unapproved or unknown effect class is
   never dispatched (`ACTION_OFF`/`NON_DISPATCHABLE`/`UNKNOWN`).
5. **Canary target and owners (open human gates).** The approved canary
   occurrence/target, the rollback owner, the unresolved-escalation owner, and
   the verifier owner. An unresolved owner is a stop condition.
6. **Gates (see [Gates](#gates)).** Master gate off by default; path gates
   necessary, never sufficient; fresh M7 action-validator verdict; handoff
   gate; allowlist; human approvals.

## Exact handoff digest reporting

The handoff registry (`handoffs.json`, loaded by `handoffs.py`) is the
explicit trust gate for every consumed source. Each row records the EXACT
owner coordinates:

| Field | Meaning |
| --- | --- |
| `id` | Fixed handoff id: `M6A`, `M7`, `M10`, `M11`, `C1`, `C2`, `S1`, `S2R` |
| `source_path` | Owner artifact path the Maintenance adapters read |
| `schema_identity` | Owner schema identity, ending in `.` + `schema_version` |
| `owner_api_identity` | Exact owner API identity (the seam Maintenance calls) |
| `schema_version` | Exact owner schema version |
| `digest` | Content digest (sha256 hex). `null` while pending — never guessed |
| `approval` | `approved` / `pending_human_approval` / `unknown` |
| `requires_wbc_coordinates` | `true` only for M6A |
| `wbc_coordinates` | WBC incarnation/restore/high-water (required for M6A acceptance) |
| `approval_evidence` | Approver, UTC `approved_at`, `evidence_ref`, optional `digest` |

Resolution is fail-closed and typed (`HandoffResolutionReason`): a row that
is missing (`MISSING_HANDOFF`), unapproved (`PENDING_HUMAN_APPROVAL`),
approved but incomplete (`MISSING_FIELD`), or mismatched on path/schema/
digest/identity (`PATH_MISMATCH`, `SCHEMA_MISMATCH`, `DIGEST_MISMATCH`,
`IDENTITY_MISMATCH`) resolves to typed `UNKNOWN` and is **non-dispatchable**.
Only a complete AND approved row resolves `ACCEPTED`.

Reporting procedure (report-only, every step is a read):

1. Load the registry (`HandoffRegistry` / `default_handoff_registry`) and
   print the frozen `registry_digest()` (content-addressed canonical digest).
2. Resolve every id (`resolve_all`) and report state/approval/reason per row;
   the accepted vector (`accepted_vector()`) is EMPTY while any row is
   pending — an empty vector is the truthful current report.
3. Report drift: `recorded_drift()` (baseline, `matches=False` without a live
   read) plus `verify_handoff_drift` live digests. A live digest that differs
   from the recorded digest is reported as **data** — it is never promoted and
   never silently accepted.
4. Report the M3 view identity (`m3.handoff.v1`) and the frozen schema/fixture
   digest tables (`FROZEN_SCHEMA_DIGESTS`, `FROZEN_FIXTURE_DIGESTS`); any live
   recomputation that differs is drift, reported as data.

## Verifier and inherited lease policy

- **Verifier.** Independent verification is authored ONLY by the approved
  distinct verifier principal (`ProducerRole.VERIFIER`), with durable
  provenance and direct owner-source reads. The canary fences the verifier
  against the admitted M11 installed runtime: `canary_verifier_binding_matches`
  requires the verifier's runtime digest AND source digest to equal the
  admission's; a mismatch rejects the run with `VERIFIER_DIGEST_MISMATCH`
  before any lifecycle edge. The repair producer can never author terminal
  verification, and a self-declared verifier label or separate PID is
  insufficient (`SELF_VERIFICATION`, `REPAIR_PRODUCER_AUTHORED`,
  `MISSING_PROVENANCE`).
- **Inherited lease policy.** The canary inherits the M7 lease duration,
  renewal grace, epoch, and fencing token from the canonical M7 lease store.
  Maintenance never defines, stores, or reimplements a lease policy. Every
  due checkpoint item carries the inherited lease id/epoch/fence verbatim ONLY
  so the executor must reacquire current authority before acting; the schedule
  projection never authorizes an edge by itself. The approved lease
  duration/renewal-grace values are an open human gate (see
  [Promotion](#promotion)).
- **Checkpoint policy.** The complete policy-required set through
  `next_three_hour` must pass before terminal verification may be considered;
  `immediate`, `five_minute`, and `one_hour` results are durable nonterminal
  evidence.

## Allowlist

Effects are routed through `route_allowlisted_effect` ONLY when the effect
class passes the M10 repair-effect allowlist (`check_effect_class` →
`AllowlistVerdict.APPROVED`). Approved effect classes for the controlled
canary are claim, source change, installation, and retrigger — each mapped to
an allowlisted repair family with reconciliation capability and evidence
predicates. `ACTION_OFF`, `NON_DISPATCHABLE`, or `UNKNOWN` verdicts are
rejected with typed reasons and nothing is appended. The approved canary
effect classes are an open human gate.

## Target and owners

| Role | Current value | Status |
| --- | --- | --- |
| Canary occurrence/target | — | OPEN human gate (U2) |
| Verifier owner (service principal) | — | OPEN human gate (U2) |
| Rollback owner | — | OPEN human gate (U2) |
| Unresolved-escalation owner | — | OPEN human gate (U2) |
| Inherited lease duration/renewal grace | — | OPEN human gate (U2) |
| Final independent-verification horizon (six-hour vs `next_three_hour`) | `next_three_hour` canonical | OPEN human decision (U1) |

An unresolved owner or horizon decision is a stop condition for promotion;
escalation references are created WITHOUT waiver and custody stays open.

## Gates

Every authority-increasing edge (request, claim, source change, installation,
retrigger, checkpoint, terminal) requires ALL of:

1. **Handoff gate.** The required handoff ids (`M7`, `M6A` for the request;
   the full accepted vector for verification sources) resolve `ACCEPTED`
   (`PENDING_HANDOFF` rejects otherwise).
2. **Coherent direct owner-source re-read.** A fresh capture over the
   injected sources with the decision's occurrence/target/lease/fence identity
   dimensions declared; torn, cross-environment, cross-occurrence,
   stale-epoch, and stale-fence reads fail closed.
3. **Eligibility.** Dispatchable capture with a WBC attempt reference and a
   current lease capture matching the pinned lease digest.
4. **Master gate.** `ARNOLD_AUTONOMY` — default OFF (`"0"`). This is the
   master authority; mutation is disabled while it is off.
5. **Path gates.** `MUTATION_PATH_L1` (and L2/L3 for their paths) — necessary
   and NEVER sufficient; callers must use `mutation_authorized(path)` at the
   effect boundary.
6. **M10 allowlist.** The effect class resolves `APPROVED`
   ([Allowlist](#allowlist)).
7. **Fresh M7 action-validator verdict.** `validate_action_boundary` re-read
   at each authority-increasing edge; a stale/expired/reclaimed result rejects.
8. **Human approvals.** All approved handoff digests, verifier principal,
   lease policy, allowlist, target, and owners supplied, and — for the
   terminal edge — the final action-validator reread (`final_boundary_fn`)
   returns authorized.

Any gate that fails is a stop condition: the stage is rejected with typed
reasons, nothing further runs, and canonical custody stays OPEN.

## Rehearsal (report-only, default)

The default canary run is a report-only rehearsal and is the ONLY mode
available today (no approvals supplied, gates default-off):

1. Prepare a private `maintenance-canary-*` root under the M11 canary base
   (`validate_maintenance_canary_root`; global runtime roots are forbidden).
2. Admit the canary: `admit_maintenance_canary` binds the run to the EXACT M11
   installed-runtime identity — strict runtime tuple, expected revision,
   runtime digest, source-lineage digest — and writes the admission artifact
   append-only and content-addressed. A digest mismatch fails closed
   (`runtime_digest_mismatch` / `source_runtime_digest_mismatch`) and nothing
   is written.
3. Run with `authorizing=False` (the default): `run_maintenance_canary` drives
   ONE occurrence-bound request, ONE allowlisted effect, and ALL due
   checkpoints, then evaluates terminal verification WITHOUT submitting it.
4. Verify the truthful non-authorizing outcome: `outcome=completed`,
   `terminal.pending_signoff=True`, `terminal_submitted=False`, and
   `custody_open=True`. A rehearsal NEVER closes custody and NEVER enables
   effects.
5. Collect the run artifact (content-addressed, append-only) as evidence.

A rehearsal is repeatable: each run writes its own append-only artifact under
the private root; nothing is ever overwritten.

## Promotion

Promotion (enabling automatic effects for the controlled canary) is **not**
authorized today. It requires, in order:

1. **U1 decision.** The milestone owner records whether the final
   independent-verification horizon remains six hours as stated by the epic
   or is intentionally `next_three_hour`, with milestone-owner approval.
2. **U2 approvals supplied.** Approved handoff digests for M6A/M7/M10/M11/
   C1/C2/S1/S2R, verifier principal, inherited lease policy, effect
   allowlist, canary target, rollback owner, and escalation owner are recorded
   in `handoffs.json` (rows resolve `ACCEPTED` with `approval_evidence`) and
   the accepted vector is non-empty.
3. **Gates verified.** Master gate enabled by an operator with authority,
   path gates confirmed, allowlist verdict `APPROVED`, fresh action-validator
   verdict current, and the report-only rehearsal has passed.
4. **Approved operator executes and signs** the controlled installed-runtime
   canary: an `authorizing=True` run with the complete checkpoint set and a
   verified terminal result submits the terminal event EXACTLY ONCE and closes
   custody. The verifier, canary, rollback, and escalation-owner sign-off is
   recorded as evidence before automatic effects are enabled.

Any unresolved approval, drift, stale authority, or missing owner stops
promotion with custody open.

## Checkpoint

Canonical windows (in event-time order, smallest delay first): `immediate`,
`five_minute`, `one_hour`, `next_three_hour` — half-open intervals
`[anchor + delta_k, anchor + delta_{k+1})` anchored to the DURABLE effect
receipt, with `next_three_hour` the unbounded canonical horizon. The legacy
`six_hour` name is a READ ALIAS for `next_three_hour` only and never schedules
a separate six-hour authority window.

- Each due window takes a FRESH coherent owner-source capture and evaluates
  independent (non-terminal) verification; a verified window appends its
  `checkpoint_verification` event BEFORE any closure decision.
- Overdue windows return exactly once as delayed catch-up, in event-time
  order, from persisted events (replay-safe; completed windows are never
  re-emitted).
- The journal admits exactly ONE `checkpoint_verification` per occurrence
  (strict action key); a later window's identical action key is rejected as a
  DIVERGENT reuse with nothing appended — the canary records the rejection
  truthfully (`append_reason="divergent_reuse"`) and continues driving the
  remaining windows.
- Custody stays OPEN until the complete policy-required set through
  `next_three_hour` passes; earlier checkpoints are nonterminal evidence.

## Rollback

Forced rollback (`rollback_maintenance_canary`) records a truthful,
non-authorizing rollback receipt:

1. The kill switch requires effects DISABLED: if a mutation-gate predicate
   authorizes the L1 path, the rollback is REFUSED
   (`MaintenanceCanaryError` `rollback_refused`) — a rollback while effects
   are still authorized would be a lie.
2. The receipt records `effects_disabled=True`, the Maintenance ledger event
   count, dead-letter replay counts (idempotent, append-only), and
   `custody_open=True` — observation, ledger append, and replay remain
   available; nothing is deleted.
3. The receipt is reference-only (`OwnerRef` `rollback_receipt`,
   `receipt_digest`): it never closes custody and never waives a gate.

Trigger: any forced install/retrigger failure with `rollback_on_failure=True`
produces `outcome=rolled_back` with the typed reject reason
(`EFFECT_REJECTED`) and the rollback receipt.

## Kill-switch

The kill switch is verified by proving the canary cannot act while it is
engaged:

1. Disable the master gate (`ARNOLD_AUTONOMY=0`) and confirm
   `mutation_authorized("l1")` is False.
2. Trigger a forced failure; confirm the run stops with typed reasons and the
   rollback receipt records `effects_disabled=True` and `custody_open=True`.
3. Confirm the receipt is non-authorizing: no terminal event was submitted,
   no gate was waived, and no plan/chain truth was written.
4. Confirm observation, ledger, and replay remain available (the rollback
   receipt's replay counts are read from the preserved ledger).

A rollback attempt while the L1 path still authorizes mutation is REFUSED —
that refusal is itself the kill-switch guarantee.

## Evidence procedures

Every canary stage appends its durable result BEFORE any closure decision,
and every artifact is content-addressed and append-only (exclusive writes):

- **Admission artifact** — `maintenance-canary/admission.json` (schema
  `arnold.megaplan.maintenance_canary.v1`): job/deployment identity, runtime
  receipt path + sha256, `runtime_identity` (`sha256:<digest>`), runtime and
  source digests, required checkpoints, `content_sha256`.
- **Run artifact** — `maintenance-canary/run/<run_id>.json`: `CanaryRunResult`
  with admission digest, request/effect results, per-window
  `CheckpointCanaryOutcome` (verification result, appended flag,
  `append_reason`, event id/digest, envelope digest), `TerminalCanaryOutcome`
  (submitted/pending sign-off), rollback receipt, `custody_open`,
  `terminal_submitted`, `authorizing`.
- **Rollback receipt** — `maintenance-canary/rollback/<run_id>.json`.
- **Ledger events** — each request/effect/checkpoint/terminal event is
  appended to the Maintenance ledger with its canonical digest and immutable
  `OwnerRef` receipts (`repair_custody` owner); receipts never authorize the
  next edge.
- **Verifier evidence** — `VerifierProvenance` with runtime/source digests and
  direct owner-source read references; negative-control references are
  included in every verification event's `evidence_refs`.

Evidence reporting is read-only: `MaintenanceLedger` replay,
`ProjectionEngine` reads, and the shadow comparison API remain available and
never mutate.

## Stop conditions

STOP the procedure, keep canonical custody OPEN, append nothing further, and
report the typed reason whenever ANY of the following is observed:

- **Stale authority** — expired/reclaimed M7 lease, stale custody epoch,
  stale fencing token, stale WBC attempt, or stale verifier capture
  (`STALE_AUTHORITY`). The scheduler carries inherited coordinates verbatim
  but NEVER trusts them; re-read current authority before every edge.
- **Torn evidence** — a version-tear across the owner-source reads
  (`TORN_ENVELOPE`) or any incoherent envelope (`INCOHERENT_EVIDENCE`);
  missing/incomplete/unknown evidence (`UNKNOWN_EVIDENCE`).
- **Digest mismatch** — handoff path/schema/digest/identity mismatch
  (`PATH_MISMATCH`, `SCHEMA_MISMATCH`, `DIGEST_MISMATCH`,
  `IDENTITY_MISMATCH`); live drift vs recorded digest; canary
  runtime/source digest mismatch (`runtime_digest_mismatch`,
  `source_runtime_digest_mismatch`, `VERIFIER_DIGEST_MISMATCH`); a wrong installation hash
  (`EFFECT_REJECTED` with an install-digest reason).
- **Lost independence** — the repair producer authored the verification,
  same-principal self-verification (`SELF_VERIFICATION`,
  `REPAIR_PRODUCER_AUTHORED`), missing provenance
  (`MISSING_PROVENANCE`), liveness-only evidence (`LIVENESS_ONLY`), or a
  missing/failed negative control (`MISSING_NEGATIVE_CONTROL`,
  `FAILED_CONTROL`). PID/tmux health, activity, local tests, commits, and
  terminal labels are corroboration only.
- **Unresolved ownership** — any handoff pending/missing/unknown (request
  rejects `PENDING_HANDOFF`), a missing approved verifier, rollback, or
  unresolved escalation owner; unresolved human gates U1/U2. Escalation
  creates immutable escalation-owner references WITHOUT waiver; custody stays
  open.
- **Recurrence without fresh authority** — a recurrence that reuses the prior
  occurrence action key, claim, lease/epoch, or verification receipt, or that
  lacks a new canonical occurrence/lease/epoch with a fresh bounded budget
  linked to the predecessor closure/root-cause cluster. Verified recurrence
  only ever creates a fresh occurrence.
- **Direct write** — any request to write plan/chain truth directly from
  Maintenance (e.g. `write_plan_state`, `save_chain_state`,
  `TransitionWriter`, or any raw plan/chain writer) is refused by the M7
  mutation boundary (`M7BypassFinding`, `mutation_attempted=False`); only the
  cloud adapter may call the canonical owner seams, and only through
  `enqueue_occurrence_bound_repair_request`, the allowlisted effect route, and
  `delegate_to_simple_fixer`.
- **Divergent reuse** — an exact retry deduplicates; a divergent reuse of an
  occurrence action key is rejected (`MaintenanceEventConflict` /
  `DIVERGENT_REUSE`) with nothing appended and no journal advance.
- **Rollback lie** — kill-switch rollback requested while the L1 path still
  authorizes mutation (`rollback_refused`).

Never force-proceed past a stop condition; never waive a gate; never close
custody on UNKNOWN or INCOHERENT evidence; never let a receipt or projection
authorize the next edge.

## Static contract assertions

The following statements are asserted mechanically by
`tests/cloud/test_maintenance_canary.py` (T15):

1. The runbook exists at `arnold_pipelines/megaplan/maintenance/RUNBOOK.md`.
2. It documents prerequisites, exact handoff digest reporting, verifier and
   inherited lease policy, allowlist, target and owners, gates, rehearsal,
   promotion, checkpoint, rollback, kill-switch, and evidence procedures.
3. It states every stop condition family: stale, torn, digest, independence,
   ownership, recurrence, and direct-write.
4. It does not imply current approval: it states the registry rows are
   `pending_human_approval`, effects are default-off, and promotion is not authorized today.
5. It matches the implemented canary API (`admit_maintenance_canary`,
   `run_maintenance_canary`, `rollback_maintenance_canary`,
   `CanaryOutcome`, `CanaryRejectReason`, schema
   `arnold.megaplan.maintenance_canary.v1`) and the canonical checkpoint
   schedule (`immediate`, `five_minute`, `one_hour`, `next_three_hour` with
   `six_hour` as a read alias).
