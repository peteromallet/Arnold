## Architectural position

This was not fundamentally a VJ8 test failure. The systemic root cause is an unversioned, non-hermetic cloud control plane: orchestration can invoke the wrong CLI/runtime, suppress launch failures, and then report ambiguous or stale evidence as current truth. VJ8 correctly prevented dispatch, but exposed the broader identity and observability failure.

### (a) Root-cause tree

```text
Cloud megaplan cannot safely progress
├─ Immediate gate failure: VJ8 rejected execution
│  └─ Four stale expectations around ledger divergence/retry canonicalization
│     └─ Resolved: exact suite now passes 130/130
│
├─ Current recovery failure: wrong executable on remote PATH
│  ├─ Wrapper invokes bare `arnold status`
│  ├─ pyenv shim resolves to an incompatible legacy arnold.cli
│  └─ Intended CLI exists only through an explicit pinned venv/module invocation
│
└─ Shared architectural failure: orchestration lacks authoritative identities
   ├─ Runtime identity
   │  ├─ Bare command names and mutable PATH
   │  └─ Resident and chain may use different dirty/pinned code lineages
   ├─ Process identity
   │  ├─ Lease startup errors can be swallowed
   │  └─ tmux/state presence can be misreported as successful launch
   ├─ Evidence identity
   │  ├─ Stale phase_result can outrank newer latest_failure
   │  ├─ Watchdog snapshots may be stale/unreadable
   │  └─ Prior recovery evidence was insufficiently occurrence-bound
   ├─ Configuration identity
   │  ├─ No remote provider-key preflight
   │  └─ Alias/auth allowlists have multiple authorities
   └─ Observation safety
      └─ Status endpoints perform unbounded work and may time out
```

### (b) Root-level fixes versus local mitigation

The ledger implementation/test repair is root-level for the specific VJ8 semantic defect: the passing 130-test suite shows the contract and expectations now agree.

Occurrence-bound recovery is also a genuine root-level design improvement within validation recovery. Binding fingerprint, occurrence, job, source revision, test result, and runtime hash prevents evidence replay and cross-runtime recovery. Preserving U1/quality blockers is correct fail-closed behavior. Projecting `finalized` into execute is a valid state-model correction.

However, these do not repair the shared cloud execution architecture. They secure the validation gate while the dispatch path still resolves an uncontrolled executable. Invoking the explicit venv manually would be a safe tactical bypass, not the general fix. Until every remote operation is bound to one verified runtime, revision, lease, and evidence authority, the system remains vulnerable to equivalent failures elsewhere.

### (c) Ranked independent Luna audit directions

1. **Hermetic runtime and CLI identity**  
   Audit every cloud entry point—resume, status, resident, chain, watchdog, repair—for bare executables, PATH lookup, dirty imports, and revision drift. Require one immutable runtime descriptor containing interpreter path, module, source revision, environment hash, and CLI contract version.

2. **Lease-bound dispatch and liveness**  
   Trace startup errors end to end. Dispatch success must require a fresh lease plus matching live process identity and command/runtime hash. tmux sessions, marker files, or state transitions are never sufficient.

3. **Authoritative state/evidence ordering**  
   Define a single monotonic precedence model across `latest_failure`, phase results, receipts, watchdog snapshots, and terminal state. Audit timestamps, occurrence IDs, atomic publication, corruption behavior, and stale-data labeling.

4. **Resident/chain lineage equivalence**  
   Prove resident orchestration and chain execution import the same immutable source. Treat dirty workspace imports or mismatched revisions as pre-dispatch failures.

5. **Provider configuration authority**  
   Consolidate provider aliases, authentication requirements, and allowlists. Preflight the selected provider key remotely before acquiring a worker lease.

6. **Bounded observer behavior**  
   Make status and `/whats-cooking` read bounded snapshots. Expensive refresh must be asynchronous, deadline-controlled, and incapable of hiding the last known state.

### (d) Shortest safe immediate recovery

Do not create a new chain and do not dispatch while U1/quality blockers remain.

The shortest safe path is:

1. Perform the real work needed to resolve the authoritative U1/quality blockers; record their normal evidence.
2. On the existing session and plan, run status using the explicit intended interpreter/module, never bare `arnold`.
3. Verify the returned plan, source revision, runtime hash, latest failure occurrence, and readiness projection.
4. Resume the same plan through that same explicit interpreter/module.
5. Accept dispatch only after observing a newly issued lease and a live process whose identity is bound to that lease and runtime.

If the explicit runtime cannot prove those identities, stop at `ready`; do not infer launch from tmux or markers.

### (e) Shared-system hardening and acceptance tests

Adopt one immutable `ExecutionEnvelope` for every cloud megaplan operation:

- plan/session/job and failure occurrence;
- pinned source revision and runtime/code hash;
- absolute interpreter plus module entry point;
- provider identity and successful credential preflight;
- lease ID, process identity, and launch timestamp;
- monotonic state/evidence generation.

All control-plane components must validate the envelope and fail closed on mismatch.

Required acceptance tests:

1. A hostile PATH containing an incompatible `arnold` cannot affect status, resume, resident, or watchdog behavior.
2. Resident and chain with different revisions or code hashes fail before dispatch.
3. Missing/invalid provider credentials fail preflight before lease acquisition.
4. A swallowed launcher exception produces explicit dispatch failure, never launch success.
5. tmux/state/marker presence without a matching fresh lease-bound process reports “not live.”
6. Stale phase results and snapshots cannot outrank a newer `latest_failure`.
7. Recovery receipts fail under any fingerprint, occurrence, job, revision, test-result, or runtime-hash mismatch.
8. Successful recovery removes only its matching validation blocker; U1 and quality blockers remain authoritative.
9. Corrupt or timed-out snapshots return bounded responses labeled stale/unavailable.
10. The same conformance suite passes for every cloud megaplan pipeline and provider, not merely this plan.
