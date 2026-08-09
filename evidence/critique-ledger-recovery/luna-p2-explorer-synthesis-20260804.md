# Luna P2 explorer synthesis — 2026-08-04

Seven bounded Luna audits (with tight reruns for entry-point and provider
authority) reviewed the Sol framing against the implementation. No agent edited
code or cloud state.

## Cross-cutting verdict

The P2 diagnosis is confirmed: the system has distributed, independently
writable authorities without a shared attempt/occurrence/generation fence.
The ExecutionAttempt ledger and admission controller are the right abstraction,
but adoption must include all override and bootstrap paths, not only normal
chain launch.

## 1. Entry-point and mutation boundaries

Concrete bypasses found:

- `cloud exec` accepts arbitrary remote commands without admission.
- `cloud resume` trusts remote `next_step` and executes it directly.
- `bootstrap` runs `arnold init --auto-start` without chain preflight.
- `epic-chain` skips normal preflight and has a non-blocking editable-install
  refresh (`|| true`) before start.
- `adopt-execution` accepts complete-shaped `execution.json`/`finalize.json`
  without originating invocation/attempt proof.
- `force-proceed` can advance state directly; `resume-clarify` can promote
  state with warnings rather than authoritative answers.
- AgentBox launch/resume stores and replays commands without a versioned attempt
  binding.
- Raw SSH `docker exec ... bash -lc` remains a policy bypass sink.

The smallest boundary is immediately before every execution side effect and
state-changing override. The admitted `attempt_id` must be passed into the
side effect; artifact adoption and state promotion require matching attempt and
hashes. `cloud exec` must be restricted or require an admission token.

## 2. Runtime/source custody

Two stages can claim one attempt while executing different code. Marker
`identity_digest` covers chain/seed/milestone labels, not source, runtime,
imports, or tests. Chain/epic-chain and AgentBox constructors still use bare
`python -P`; validation derives `sys.executable` and imported source at runtime.
Generated failure metadata also records bare `python -m` commands. Editable
`PYTHONPATH` can make a stale package win. Import checks only test module
presence, not resolved `__file__` or hashes. Epic-chain refresh can fail while
start proceeds.

Minimum custody must include: attempt/occurrence/generation; repo/worktree
revision and dirty/untracked digest; absolute interpreter realpath/hash and
Python ABI; exact argv/cwd and environment/PYTHONPATH digest; runtime tree
manifest; resolved module paths/hashes for engine, validator, and tests; exact
test/input hashes; provider/container; lease/PID/start identity; and a terminal
receipt binding all fields.

## 3. Evidence ordering and recovery

`phase_result.json`, `state.latest_failure`, history, artifacts, resume cursors,
and status projections are independently writable. `phase_result` has no
attempt/occurrence/generation fence and is treated as current by recovery and
status. `_external_error_requires_resume()` can let an old external-error
result outrank a newer VJ9 failure. `recover-blocked` can clear
`latest_failure` without matching occurrence/receipt/generation. Multiple
handlers, auto, chain completion, replanning, and resolution paths clear
failures without occurrence matching. State writes are lock-serialized but not
consistently CAS-bound. Cloud status, chain status, repository history, and the
pure run-state resolver use different precedence rules.

Required ledger fields: `plan_id`, `attempt_id`, `phase`, monotonic `generation`,
`occurrence_id`, canonical semantic `fingerprint`, kind, producer, and artifact
hash. Only a typed transition may update the current failure pointer. Recovery
must require exact plan/attempt/occurrence/fingerprint/expected generation and a
repair receipt; mismatches return `stale_occurrence` without writing. Terminal
transitions fence late telemetry. Exact receipt replay is idempotent; altered
payloads conflict. Generic resume must be unavailable for typed validation
blocks.

## 4. Lease and liveness

Current leases lack lease ID/generation, process-start identity, command/runtime
and source custody. Cloud launch writes markers and starts tmux before proving a
managed lease-bound process. Verification can return `warning` while callers
still emit success/provenance. Watchdog and status reduce liveness to PID/tmux/
recent activity; heartbeat tracks output mtime, not ownership.

The fenced protocol must acquire a lease before side effects, launch the exact
recorded command, verify PID plus start identity, exact argv, runtime/source,
session/container/plan/job, and process acknowledgement of lease generation,
then publish `live`/`executing`. Renewal and all writes are generation-fenced;
takeover requires proving the old owner cannot write. Use monotonic deadlines.

## 5. Provider authority

Provider identity is split across spec, marker, preflight, runtime key pool,
AgentBox, and batch receipts. `_provider_consistency_check()` is effectively
not applicable; preflight checks local env names while key-pool normalization
can reinterpret aliases (including fallback providers). Credential presence and
provider identity are not compared. Orchestration and task models are only
implicitly distinguished by location/context, not explicit role.

Create one immutable authority record per role (`orchestration`, `task`,
`validation`) containing requested and canonical provider/model/endpoint,
logical credential reference, alias-resolution trace, provider identity, policy
version, and authority fingerprint. Produce it with the same resolver used at
runtime; validate it before lease/resource acquisition and again on resume.
Legitimate role differences pass only when each role record independently
matches policy; missing/ambiguous/conflicting records fail closed.

## 6. Observer and notification projections

Snapshot validation checks `generated_at` but ignores heartbeat/write-error
sidecars. Snapshot writing rotates the valid file before replacement, so a write
failure can destroy the current view. Resident/live queries can block before
loading the cache; laptop fallback can replace a valid stale cache with an
unbounded live query. Status hides `latest_failure` except in a narrow path.
LLM telemetry correlates by phase/model without attempt/generation. Notification
dedupe persists messages before checking whether the classification already
exists.

Observers need a snapshot-first envelope with authoritative ledger cursor,
attempt/occurrence, state/latest failure, freshness, integrity, and verified
process proof. `running` requires same-attempt lease/process proof and fresh
heartbeat. Live fallback is optional with a 2–5s deadline; cached state survives
timeouts and is labelled stale/unavailable. Write new snapshots via temp file +
`os.replace` before rotation. Durable notification key:
`(session, plan/job, occurrence, fingerprint, material_state)`; emit once,
again only for a new occurrence/generation/material transition/resolution.

## 7. Legacy migration and takeover

Legacy state, receipts, chain manifests, markers, and leases do not jointly
prove runtime/provider/process identity. No automatic takeover is safe from the
local checkout alone. A session is adoptable only with mutually consistent
session/plan/job/occurrence, artifact hashes, clean source/runtime identity,
provider preflight, and either an attested live owner or proof the old owner
cannot write. Otherwise classify `quarantine_restart` (history preserved,
new attempt/worktree) or `ambiguous` (human gate). Never rewrite history or
steal from expiry/timestamp/tmux/marker/PID alone. `load_chain_state()` must be
excluded from dry-run migration if it can normalize/write state.

## Consolidated acceptance set

P2 must prove: every entry point admits exactly one attempt; hostile PATH,
dirty/divergent imports, and changed test hashes fail before mutation; wrong or
stale recovery receipts cannot clear a newer occurrence; lease/PID/tmux faults
never publish `executing`; role-scoped provider disagreement fails before lease;
hung/corrupt/stale observers remain bounded and explicit; repeated incident
notifications collapse; and legacy sessions classify without rewriting history.
