# Final implementation plan

## 1. Minimum repair before touching the current session

Do not resume through the current `cloud resume` path until these P0 repairs are deployed:

1. **Make remote CLI identity hermetic.** Replace every remote `arnold status`/`arnold resume` invocation with the absolute pinned command:

   `/workspace/runtime-venvs/arnold-wbc-full-20260804/bin/python -P -m arnold_pipelines.megaplan`

   Status and resume must use the same interpreter, module, workspace, plan ID, source revision, and runtime hash. `PATH`, shell aliases, and `/root/.pyenv/shims/arnold` must be irrelevant.

2. **Fail before dispatch on identity disagreement.** The wrapper must compare the expected runtime/source binding with the remote runtime and reject dirty, legacy, missing, or mismatched lineage.

3. **Enforce authoritative evidence ordering.** For this session, `state.latest_failure` and its occurrence/fingerprint must outrank stale `phase_result.json`. The occurrence-bound VJ8 repair receipt may clear only the matching deterministic VJ8 failure. It must not clear U1 or quality blockers.

4. **Require a real provider preflight.** Before lease acquisition, verify the effective provider, model alias, base URL, and authentication remotely and without exposing secrets. A hint that credentials might exist is insufficient.

5. **Make dispatch fail closed.** No executing state or success marker may be published until a fresh lease and matching live process identity have been verified.

These are prerequisites, not optional hardening. Without them, the current session can again fail before dispatch or falsely appear live.

## 2. Exact safe resumption sequence

Use the existing session `critique-ledger-accountability-v3-r5-20260803` and existing plan `cl2-wbc-backed-ledger-20260803-1357`. Do not create a replacement chain.

1. Run status through the newly pinned command and verify:

   - `state=finalized`
   - `execution_state=ready`
   - `next_step=execute`
   - latest VJ8 failure occurrence and fingerprint match the recovery receipt
   - the recorded 130-test result and runtime code hash match
   - U1 and quality blockers remain unresolved

2. Quarantine older `phase_result.json`, watchdog, marker, or snapshot evidence logically: retain it for audit, but do not let it determine current failure, readiness, or liveness.

3. Validate the immutable execution envelope: session, plan, job, occurrence/fingerprint, container, source revision, runtime hash, provider identity, and intended command.

4. Run the bounded remote provider preflight. Any alias, credential, authentication, or endpoint failure stops resumption before lease acquisition.

5. Acquire a **new fenced lease** for this dispatch attempt. If an existing lease cannot be proven dead using PID plus process start identity, command, runtime, revision, and session, stop for human review. Never infer death or life from tmux, markers, or state alone.

6. Launch through the pinned runtime. Within a fixed deadline, verify that the live process matches the lease ID and complete execution envelope.

7. Only after successful verification may the system publish dispatch success or an executing projection.

8. Resume to the execute boundary, but leave U1/quality gating authoritative. The plan must wait for genuine, independently supplied U1/quality resolutions. Do not fabricate CL1/U1 handoffs, reinterpret VJ8 recovery as quality approval, or override blockers merely to advance state.

9. Confirm status from both the authoritative state and a fresh lease-bound process observation. Observer output must distinguish “blocked awaiting U1/quality” from “executing.”

## 3. Shared control-plane changes to ship next

Establish one versioned execution-envelope contract first. Then deliver these workstreams:

1. **Runtime identity and lineage**

   - One absolute interpreter/module constructor for wrappers, resident, chain templates, supervisor, status, resume, and watchdog.
   - Bind source revision and runtime hash.
   - Reject dirty or divergent resident/chain imports before dispatch.

2. **Lease and liveness**

   - Lease IDs with fencing generations.
   - PID plus process-start identity, exact command, runtime, revision, session, and container verification.
   - Propagate launcher and lease exceptions; never swallow them.
   - Require fenced takeover after expiry or uncertain ownership.

3. **Evidence ordering**

   - Monotonic evidence generations, with occurrence-bound failures and receipts.
   - `state.latest_failure` outranks older phase results and snapshots.
   - Recovery clears only its exact failure class.
   - Terminal states quarantine stale telemetry rather than inheriting it.

4. **Lineage custody**

   - Carry the envelope through every transition and artifact.
   - Template, resident, chain, recovery, and observer paths must reject partial or conflicting custody data.

5. **Provider authority**

   - One provider registry for aliases, supported models, endpoints, auth rules, adapters, and Hermes.
   - Secret-safe, deadline-bounded remote authentication preflight before leasing.

6. **Observer bounds**

   - Snapshot-first responses.
   - Live queries are optional, deadline-bounded fallbacks.
   - Explicit stale/unavailable labeling based on generation, heartbeat, corruption, and write-error sidecars.
   - A failed fallback can never replace a valid cached snapshot.

## 4. Concurrency, high-risk decisions, and human gates

After the execution-envelope schema is fixed, runtime/lineage, lease/liveness, evidence ordering, provider authority, and observer work can proceed in parallel. Integration must converge through the envelope and a single dispatch state machine.

The very-hard judgment call is **fenced takeover of legacy sessions that lack trustworthy process identity**. Never automate takeover from an expired timestamp, missing tmux session, or stale marker alone.

Human approval remains mandatory for:

- accepting substantive U1/quality resolutions;
- taking over when prior lease ownership cannot be disproved;
- changing a session’s pinned source/runtime after recovery;
- overriding a provider identity or lineage mismatch.

## 5. Conformance and rollback matrix

| Area | Required proof | Failure/rollback expectation |
|---|---|---|
| Runtime | Hostile `PATH` still runs pinned status/resume | Reject before mutation; restore prior wrapper |
| Evidence | Old external phase result cannot outrank newer VJ8 | Preserve state and blockers |
| Recovery | Wrong occurrence, hash, job, or revision rejected | No failure cleared |
| Quality | VJ8 receipt leaves U1/quality unresolved | No dispatch past quality gate |
| Lease | Injected acquisition/launcher error | No executing state or success marker |
| Liveness | tmux/marker-only and PID-reuse cases fail | Report unknown/stale, not live |
| Lineage | Dirty resident or divergent chain revision | Fail before dispatch |
| Provider | Missing key, bad auth, alias disagreement, timeout | No lease acquired |
| Observer | Hung backend returns cached snapshot within deadline | Label stale/unavailable |
| Corruption | Bad snapshot or write-error sidecar | Preserve last valid snapshot |
| Takeover | Old process identity still matches | Refuse takeover |
| Generalization | Run the suite against every cloud pipeline entry point | Roll back shared control plane if any bypass exists |

The combined work **prevents recurrence of the identified pre-dispatch identity, stale-evidence, false-liveness, lineage, and provider-configuration failures when all entry points conform**. Observer changes primarily improve bounded detection and recovery.

Residual risks remain: post-dispatch provider outages, network partitions, host loss, compromised pinned artifacts, and legacy sessions without sufficient identity evidence. Those require fenced retries, artifact integrity controls, and human-gated recovery—not optimistic state projection.
