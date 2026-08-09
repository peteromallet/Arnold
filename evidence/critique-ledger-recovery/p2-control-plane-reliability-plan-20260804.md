# P2 control-plane reliability plan — 2026-08-04

This plan is the final Sol synthesis of the existing recovery plan, the VJ9
review, and seven Luna implementation audits. It is a follow-up reliability
plan for every Megaplan/cloud pipeline, not a prerequisite to recovering the
current critique run.

## Root diagnosis

The recurring failure is **distributed authority without transactional
custody**. Commands, source trees, providers, leases, failures, repair
receipts, artifacts, chain state, and observer snapshots can refer to different
executions, yet still be combined into one transition:

1. An entry point launches or replays work without a complete identity envelope.
2. Independently writable evidence crosses revision, attempt, or generation
   boundaries.
3. A permissive transition selects stale or partial evidence.
4. State advances before provider, ownership, or process identity is proven.
5. Observers and notifications amplify the incorrect projection.
6. Recovery clears more than the exact failure it repaired.

The VJ9 test failure is the validation-side manifestation: implementation and
test contracts crossed a source/runtime boundary without authoritative custody.

## North star and authority rule

Build a versioned **ExecutionAttempt ledger** and one admission/transition
controller used by wrappers, resident mode, chain and epic-chain, bootstrap,
supervisor, AgentBox, cloud resume/recovery, watchdog, status, overrides,
artifact adoption, and future pipeline SDK entry points.

This is a control journal and commit authority, not a second copy of chain
state, phase results, gates, or business artifacts. Workers, validators, fixers,
and humans can produce staged artifacts and attestations; only the controller
CAS-commits control transitions and current pointers.

### Immutable custody envelope

- `pipeline_id`, `session_id`, `plan_id`, `job_id`, `phase`, `entry_point`
- `attempt_id`, monotonic `generation`
- `occurrence_id`, semantic `fingerprint`, failure kind
- repository/worktree revision and dirty/untracked digest
- interpreter realpath/hash, Python ABI, exact argv/cwd
- environment/PYTHONPATH digest and runtime-tree manifest
- resolved module paths/hashes for engine, validator, and tests
- exact validation command and test/input hashes
- container/resource identity
- role-scoped provider authority records
- policy/schema versions and human-gate IDs

Append-only attestations bind lease/fence, PID/start identity, process
acknowledgement, heartbeats, artifact hashes, recovery receipts, resolutions,
and terminal results.

State transitions:

`prepared → admitted → leased → launched → verified/executing → terminal | blocked`

Failures before verification are `blocked`, never `executing`. Markers, tmux,
snapshots, phase results, and notifications are projections. Batch receipts
remain model-execution evidence, attached by hash to the attempt.

## Ordered work

### P0 — current-run recovery guardrails

Keep this surgical and independent of P2:

- pinned absolute runtime for status/resume;
- exact source/runtime/worktree/test identity;
- current-failure precedence over stale phase results;
- occurrence-scoped VJ9 repair;
- role-correct remote provider preflight;
- fresh fenced lease and verified process identity before `executing`.

The current critique run still preserves VJ9, repairs the adapter contract,
verifies canonical store/outbox behavior, runs the bounded suites, and keeps
U1/quality blockers authoritative.

### P1 — fleet containment before migration

Interlock known unsafe bypasses before introducing a new ledger:

- `cloud resume` cannot execute a remote `next_step` directly;
- `force-proceed` and `resume-clarify` cannot clear typed validation or human
  gates;
- `adopt-execution` requires originating attempt and hash proof;
- bootstrap auto-start and epic-chain stop on preflight/editable-refresh failure;
- AgentBox command replay requires a versioned binding;
- `cloud exec` is read-only/allowlisted or explicit break-glass;
- raw SSH mutation taints managed state and requires gated re-adoption.

P1 may temporarily disable unsafe operations; it need not implement the full
ledger.

### M0 — authority contract (sequential, human-gated)

Approve the envelope, transitions, evidence precedence, recovery types, provider
roles, and complete mutation/entry-point inventory. No unknown writer may
remain.

### M1 — reference kernel

Implement the append-only journal, CAS transition API, admission tokens,
fencing, artifact registration, and conformance harness. This is the dependency
for adapters.

### M2 — parallel adapters

After M1 stabilizes, these workstreams can run in parallel:

- runtime/source/test custody;
- evidence ordering and typed recovery;
- leases, process acknowledgement, and liveness;
- provider authority and preflight;
- snapshot, observer, notification, and outbox projections.

Provider validation precedes leasing; leasing precedes launch; process
attestation precedes `executing`.

### M3 — entry-point cutover

Adopt all managed entry points and state-changing overrides. Shadow comparison is
allowed, but dual authoritative writing is not. Cut over one mutation family at
a time with rollback to its previous adapter.

### M4 — legacy migration and certification

Classify legacy sessions, perform gated adoption, and run the full fault suite
against every entry point and pipeline.

## Rough sizing

These are engineering estimates, not promises about model/runtime wall-clock:

- Current VJ9 recovery and safe resume: roughly **0.5–2 working days** once the
  source/runtime identity is verified; U1/quality human gates can extend the
  calendar time.
- Existing P0/P1 hardening plan for the current cloud path: roughly **3–7
  working days** with focused parallel work; **1–2 weeks** if one person carries
  it sequentially.
- Full P2 (M0–M4) across all entry points: roughly **4–8 calendar weeks** with
  parallel adapters and certification; **8–12 weeks** if effectively
  single-threaded. Legacy ambiguity and human approvals are open-ended by
  design.

## Fail-closed boundaries

- **Launch:** reject before mutation if admission token, generation, custody,
  provider, gate, or ownership cannot be proven.
- **Resume:** treat as new admission; reject dirty/divergent lineage, changed
  tests, stale generation, provider drift, or ambiguous ownership.
- **Recovery:** require exact plan/attempt/occurrence/fingerprint/generation,
  repair type, and artifact hashes. Mismatch returns `stale_occurrence` without
  writing; exact receipt replay is idempotent; changed payload conflicts.
- **Provider:** resolve `orchestration`, `task`, and `validation` roles before
  resource/lease acquisition and again on resume. Record requested/canonical
  provider/model/endpoint, logical credential reference, alias trace, provider
  identity, policy version, and fingerprint. Missing/ambiguous/conflicting
  records fail closed.
- **Liveness:** `running` requires current fence, PID/start identity, exact
  command/runtime/source/session/container match, process acknowledgement, and
  fresh heartbeat. PID, tmux, marker, or timestamp alone yields `unknown`.
- **Artifact adoption:** require originating attempt, generation, producer,
  schema/type, content hash, and expected transition.
- **Takeover:** lease expiry alone never proves the old owner cannot write.

## Observer and notification contract

Observers are snapshot-first and bounded. The result includes ledger cursor,
attempt/generation, current occurrence/failure, integrity, freshness, and
verified process proof. A 2–5 second live fallback is optional; timeout or
corruption preserves the last valid snapshot and labels it `stale`,
`unavailable`, or `unknown`.

Notifications use the durable dedupe key:

`(session, plan/job, occurrence, fingerprint, material_state)`

Emit once, then only for a new occurrence, material transition, or resolution.
Persist dedupe/classification before enqueueing delivery.

Automatic fixers may repair deterministic validation defects and submit typed,
hash-bound receipts. They may not decide provider substitutions, source-lineage
changes, U1/quality acceptance, uncertain ownership, takeover, or ambiguous
artifact adoption.

## Acceptance and fault-injection matrix

| Injection | Required result | Proof |
|---|---|---|
| Hostile PATH/stale editable import | Reject before mutation | Interpreter/module manifest |
| Dirty revision/changed test hash | Reject admission | Custody diff + receipt |
| Older phase result after newer failure | Current failure unchanged | Journal precedence trace |
| Wrong occurrence/fingerprint/generation | No failure cleared | `stale_occurrence` receipt |
| Lease error/PID reuse/tmux-only marker | Never publish `executing` | Fence/process transcript |
| Provider alias/auth/endpoint drift | No lease/resource | Role authority + preflight receipt |
| Late worker write after terminal/takeover | CAS/fence rejection | Rejected-write record |
| Hung live query | Bounded cached response | Deadline + snapshot cursor |
| Corrupt snapshot/write failure | Preserve last valid view | Integrity/write-error sidecar |
| Duplicate incident inputs | One notification | Durable dedupe/outbox record |
| Legacy ambiguous owner | Quarantine/human gate | Classification report |
| Every entry point | Exactly one admission | Coverage manifest + conformance report |

“No bypass remains” requires a reviewed mutation inventory plus instrumentation
at the execution-side-effect and managed-state commit boundaries. Every managed
command must present one valid admission token; an unrecognized caller fails.
Raw shell remains break-glass, not a conforming managed entry point.

## Legacy migration

A session is adoptable only with consistent session/plan/job/occurrence,
artifact hashes, clean source/runtime identity, provider preflight, and either
an attested live owner or proof the old owner cannot write. Otherwise classify
`quarantine_restart` (history preserved, new attempt/worktree) or `ambiguous`
(human gate). Never rewrite history or steal from expiry, timestamps, tmux,
markers, or PID alone. Dry-run migration must not call loaders that normalize or
write state.

## Human gates and residual risk

Human approval is mandatory for schema/precedence/migration policy, changing
pinned source/runtime/provider identity, substantive U1/quality resolution,
uncertain takeover, contradictory legacy adoption, and converting break-glass
mutations back into managed state.

The architecture is pipeline-neutral: Megaplan is the first certification
target, while each pipeline supplies typed phase, gate, artifact, and recovery
adapters.

P2 is complete when every managed entry point and state-changing override admits
exactly one custody-complete attempt; only the controller commits transitions;
stale, contradictory, late, or unaffiliated evidence cannot advance state; and
the full fault matrix passes across every Megaplan/cloud pipeline.

Residual risks: host loss, network partitions, compromised pinned artifacts,
post-dispatch provider outages, and inherently ambiguous legacy ownership.
Those belong to later retry, integrity, disaster-recovery, and SLO work.
