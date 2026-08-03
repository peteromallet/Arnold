# a02-s08-identity-version-provenance-repair-fixer: identity-version-provenance × repair-fixer

## Verdict

Nonconformant. Two P0 authority gaps are reachable, plus P1 status/admission gaps.

The repository has canonical components, but no single end-to-end contract binding queue request, claim, fixer mutation, managed launch, meta-repair, retrigger, and terminal verification to the same run, attempt, incarnation, version, and launch provenance.

## Intended canonical contract

Every effect should carry one immutable `RepairOccurrenceKey`: F01 target plus `run_id`, `run_revision`, `coordinator_attempt_id`, `fence_token`, and `wbc_attempt_reference` (`custody/contracts.py:653-683`). Claims additionally require the current custody lease, grant, epoch, and owner process-incarnation identity.

The canonical mutation funnel is `simple_fixer.CanonicalRunner` (`simple_fixer.py:789-803`), reached through `RepairDelegation` (`wrappers/repair_delegation.py:74-126`, `218-340`). The managed launch canonicalizer is `managed_agent`, whose manifest binds run ID, command hash, launch contract hash, model, backend, route, launch provenance, and sealed input (`managed_agent.py:448-526`), and validates those fields before launch (`managed_agent.py:157-212`).

The mkdir lock is admission evidence only; authoritative mutation requires lease validation (`repair_lock.py:1-19`).

## Evidence and complete path inventory

Search method: I used `rg --files` to enumerate repair/fixer/meta/lock/provenance files, then `rg -n` over production code and tests for `enqueue_repair_request`, `claim_active_repair_request`, `bind_managed_run_to_active_claim`, `RepairOccurrenceKey`, `repair_identity`, `managed_run_id`, `launch_provenance`, `retrigger`, subprocess calls, and all delegation symbols. I manually traced each production hit and its tests.

Writers:

- Lifecycle and supervisor producers use the occurrence-bound adapter (`auto.py:2344-2360`; `cloud/supervise.py:316-330`).
- Manual trigger writes directly through legacy `enqueue_repair_request` without `repair_identity` (`manual_repair_trigger.py:401-459`).
- Six-hour auditor passes an F01-shaped mapping as `repair_identity` (`six_hour_auditor.py:408-456`).
- Queue records, decisions, dispatch attempts, claims, and managed-run binds are written by `repair_requests.py:973-1045`, `1474-1535`, `1596-1704`, and `1723-1825`.
- Meta records and verdicts are written by `meta_repair.py:1730-1859`, `1945-2001`, and the shell wrapper (`wrappers/arnold-meta-repair-loop:1811-1847`).

Readers/callers/consumers:

- `arnold-repair-trigger` reads all request markers (`wrappers/arnold-repair-trigger:185-220`, `283-365`), claims them (`:594-613`), then either launches a managed child or delegates to `simple_fixer` (`:1080-1105`).
- `arnold-watchdog` independently claims repair ownership without passing `repair_identity` (`wrappers/arnold-watchdog:5257-5327`).
- `managed_agent` binds claims to a manifest run (`managed_agent.py:574-626`).
- Meta-repair recursion consumes session/blocker records (`meta_repair_policy.py:141-232`).
- Terminal audit delegates and verifies retrigger status (`terminal_audit.py:162-333`).
- `find_pending_by_signature` only compares identity when the caller supplies a nonempty identity key (`repair_requests.py:1392-1419`).

## Adherence gaps

1. **P0 — authority mutation: canonical fixer identity is incomplete.**  
   Observed: `SimpleFixerOccurrence` and `RepairDelegation` contain only the ten F01 fields (`simple_fixer.py:114-167`; `wrappers/repair_delegation.py:74-126`). Singleton claims are keyed only by the F01 fingerprint and store actor/session/request metadata (`simple_fixer.py:306-367`). They do not bind `run_id`, `run_revision`, coordinator attempt, WBC reference, custody epoch, provider/runtime version, or launch contract.

   Inference: two runs sharing the same F01 projection can reach the same mutation claim despite differing run incarnation or launch provenance. `RunnerReceipt` adds source/environment hashes but explicitly remains evidence-only and still lacks those identity fields (`simple_fixer.py:546-606`).

   Bypasses/duplicates: manual enqueue omits identity (`manual_repair_trigger.py:449-459`); six-hour identity is not accepted by `normalize_repair_identity`, which only accepts current nested keys or legacy ten-field names (`repair_requests.py:57-97`); watchdog derives fallback attempt `"1"` and fence data while building a fixer target (`wrappers/arnold-repair-trigger:1019-1054`; `wrappers/arnold-watchdog:5316-5327`).

2. **P0 — authority mutation: queue/claim admission accepts unbound evidence.**  
   Observed: `repair_request_contract_violations` validates blocker, producer/session, and signature evidence but never requires a valid `repair_identity` (`repair_requests.py:788-857`). Legacy identity-free enqueue is deliberately tested as accepted (`tests/cloud/test_repair_enqueue_producers.py:219-245`). The watchdog then calls `claim_active_repair_request` with no identity (`wrappers/arnold-watchdog:5316-5327`), and the claim API accepts the optional field (`repair_requests.py:1596-1661`).

   The projection layer can mark such records unclaimable (`tests/cloud/test_repair_custody.py:364-409`), but the watchdog’s direct claim path bypasses that protection. This is a reachable stale-evidence-to-claim path.

3. **P0 — authority mutation: lease authority drops process incarnation.**  
   Observed: lock metadata records PID namespace and process start ticks (`repair_lock.py:145-152`), and lock inspection rejects foreign namespaces and PID reuse (`repair_lock.py:652-673`; `tests/cloud/test_repair_lock_namespace_fencing.py:18-67`). However authoritative lease validation compares only hostname and PID (`repair_lock.py:405-464`), despite lease ownership being described as host/PID/boot identity (`custody/lease_store.py:156-162`). Therefore a two-container or PID-reuse collision can pass the lease gate when host/PID coincide. Existing tests cover host/PID mismatch but not namespace/start-tick mismatch at this authority boundary (`tests/cloud/test_repair_lock.py:852-964`).

4. **P1 — status misreporting: in-process fixer is recorded as a managed launch.**  
   `arnold-repair-trigger` delegates to the in-process fixer, then writes a `repair_request_attempt` with `child_pid=os.getpid()`, `managed_run_id=request_id`, and a manifest path (`wrappers/arnold-repair-trigger:1080-1098`). The writer unconditionally labels the record `status="launched"` (`repair_requests.py:1491-1518`). No managed child or validated manifest exists on this path. The same trigger mutation returns the unchanged occurrence fingerprint (`wrappers/arnold-repair-trigger:1577-1610`), so the canonical runner classifies it as unchanged (`simple_fixer.py:499-532`) and the truth firewall rejects delegation (`wrappers/repair_delegation.py:316-338`).

5. **P1 — status misreporting: terminal audit has no target and fabricates independence.**  
   `capture_terminal_snapshot` returns no `repair_target` (`terminal_audit.py:115-133`), while `run_terminal_audit` reads `pre_snapshot.get("repair_target")`, making delegation unreachable in this implementation (`terminal_audit.py:208-233`). It then constructs observation fields `independent=True`, `fresh_progress_beyond_checkpoint=True`, and `continued_progress=True` without comparing occurrence-bound pre/post evidence (`terminal_audit.py:242-282`). This is status-only today, but would become an acceptance bypass if the return-code bug were corrected.

6. **P1 — status/admission: meta-repair recursion is session-scoped.**  
   `MetaRepairRecord` and `MetaRepairVerdict` have session/request/blocker fields but no run, attempt, incarnation, version, or launch provenance (`meta_repair.py:1730-1772`, `1945-2001`). Recursion counts records by session and optional blocker (`meta_repair_policy.py:179-232`), while legacy/manual callers explicitly retain a session-scoped fallback (`meta_repair_policy.py:58-63`). Restarted or provider-failed records can therefore suppress or misclassify a later incarnation.

## Incident reachability and severity

Observed reachability is strongest through the watchdog direct claim, legacy/manual/six-hour enqueue paths, and lease release/renewal. The lock tests prove cross-container/PID-namespace conditions are realistic; the missing lease comparison is an inference from the authority code.

The first three gaps can authorize mutation or custody release across stale boundaries: P0. The latter three produce false launch, verification, or recursion state and can block or misclassify recovery: P1. No evidence here establishes that a particular external incident used every path.

## Minimal generalized remediation

- Extend one delegation envelope to carry a validated `RepairOccurrenceKey`, custody lease/grant/epoch, owner namespace/start ticks, runtime revision, provider/model/backend/route, and managed launch-contract digest. Make `simple_fixer`, claims, and dispatch attempts consume that envelope.
- Make `enqueue_repair_request` reject missing/invalid identity at the effect boundary; retire the additive fallback in `repair_requests.py:1009-1045`. Migrate existing identity-free records to terminal `stale/unclaimable` decisions and re-enqueue exact successors.
- Delete direct legacy calls in `manual_repair_trigger.py:449-459` and `six_hour_auditor.py:424-456`; use one adapter that constructs the current occurrence key. Remove watchdog fallback target construction and require request identity during claim.
- Update lease owner schema/validation to compare namespace, process start ticks, and nonempty boot identity; fail closed when unavailable.
- Record in-process fixer effects separately from managed-child launch attempts. Only write `repair_request_attempt` after a validated manifest exists.
- Make terminal audit return and reread the exact target/provenance; remove hardcoded independence/freshness claims. Bind meta records and recursion keys to the same full identity.
- Retire `retrigger_ordinary_repair` as a public subprocess authority; repository search found only its definition and tests, not a production caller (`meta_repair.py:2296-2375`).

## Required tests and retirement proof

Add deterministic tests for:

- differing run, revision, attempt, fence, WBC reference, provider/model/version, launch digest, and process incarnation;
- concurrent same-key and different-key claims, restart, stale lock, and two-container/PID-namespace collisions;
- lease validation with foreign namespace, reused PID, changed start ticks, and empty boot ID;
- legacy/partial queue records rejected and unable to claim, retrigger, or coalesce;
- no-op fixer action never produces dispatch status; managed launch status requires a matching manifest;
- terminal verification requiring an independently reread, occurrence-bound post-delta;
- meta recursion isolation across restart, blocker, attempt, and provider failure.

Retirement proof should include AST/`rg` assertions that production code has no direct legacy enqueue, no `claim_active_repair_request` call without the full envelope, no fallback F01/default attempt construction, no fake managed attempt writes, and no production caller of `retrigger_ordinary_repair`.

## Unknowns

No services, cloud state, or runtime execution were used. The exact deployment relationship between container hostname and shared lease store is unknown. The source proves six-hour F01-shaped input is not normalized; live audit payloads were not available to determine frequency. External callers outside this repository may still invoke public legacy APIs.