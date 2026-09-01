# NBF-06 provider-resilience architecture: adversarial research

Date: 2026-08-31  
Branch: `reconcile/nbf-attempt4-2297`  
Base under review: `7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`  
Mode: read-only source/tasklist audit; no production or tasklist edits

## Executive verdict

NBF-06's ownership boundary is directionally sound: provider resilience should
be a policy layered over the NBF-01 ledger/projection and NBF-02
admission/scheduling seams. The current tree, however, has a strict
`provider_exhausted` transport contract and several ledger primitives without a
single integrated T8 producer. The implementation must close that seam before
claiming acceptance. In particular, the existing configured fallback loop and
the ambient runtime-agent fallback are two potentially competing routing
doors, while provider observation/probe helpers are presently callable without
the full terminal/reservation linkage required by the task.

This is an architecture/rework finding, not evidence that the current NBF-04 or
NBF-05 candidate is unsafe. NBF-06 should begin only after the tasklist's hard
Batch 1--3 synchronization barrier and the committed NBF-01--05 authority
contracts are available.

## Source-backed findings

| Evidence | Current contract | Adversarial consequence | Required closure |
|---|---|---|---|
| `arnold_pipelines/megaplan/orchestration/phase_result.py:213-229` | `DispatchOutcome(provider_exhausted)` requires accepted launch plus seven classes of structured provider evidence, including observation ID, terminal evidence ID, precondition identity, provider epoch, failure key, and attempt count. | The transport is fail-closed, but a producer must actually construct every field from one accepted reservation/worker outcome. A generic provider exception cannot be promoted by inference. | Add one production producer at the accepted dispatch/terminal seam; test missing, stale, cross-reservation, and ordinary-error evidence as unresolved/ordinary failure with no provider transition. |
| `arnold_pipelines/megaplan/cloud/worker_dispatch.py:312-350` | `_outcome_from_terminal_exception` translates only explicit typed exceptions/mappings; provider exhaustion needs `provider_evidence` and `worker_identity`. | This is the natural adapter door, but the current code does not itself derive the canonical observation or invoke the provider policy. A managed caller can then receive an integer failure after translation (`cloud/babysitter/launch.py:611-643`) unless terminalization is durable first. | Keep translation pure and make T8 consume its typed result before compatibility conversion. Persist terminal + observation exactly once, then return/convert. |
| `workers/_impl.py:7777-7828` | `_advance_configured_spec_fallback` advances only for configured specs, blocks execute steps and post-tool writes, and uses provider-family classification. | It is currently the actual configured fallback door, but `step in _EXECUTE_STEPS` returns `None`; the `ExecuteFallbackUnsafe` type exists but is not the universal enforcement path. Silent refusal can be mistaken for an ordinary failure and can lose the explicit prohibition evidence. | Make the door's result typed and durable: either raise `ExecuteFallbackUnsafe` with attempt metadata or return a distinct no-transition decision that callers must record. Assert zero second dispatch/client/WBC/RPC for execute and loop-execute. |
| `workers/_impl.py:8663-8730` | After configured fallback declines, an ambient `_runtime_fallback_candidates(agent)` path can retry auth/connection errors unless `explicit_agent` or `_suppress_ambient_agent_fallback` is set. | This is a second routing authority. An explicit configured chain does not obviously suppress it by itself, and the ambient route is agent-based rather than provider-family/ledger-bound. It can bypass T8 streak, observation, route-child, and execute safety. | Suppress ambient fallback whenever a configured chain is present; preferably make it unavailable on the T8 path. Require any legacy compatibility path to emit an explicit no-transition/legacy event and prove it cannot run after an accepted worker outcome. |
| `fallback_chains.py:256-270` | `configured_fallback_chain_for_phase` scans entries and silently skips non-strings or entries without `=`; duplicate phase entries return the first match. | A malformed or duplicated phase configuration can silently select a different chain than the operator intended. This is especially dangerous when the durable admission only stores a chain identity. | Validate the complete phase-model list, reject malformed/duplicate phase entries, and bind normalized chain bytes plus config/profile identity to admission and every child reservation. |
| `fallback_chains.py:322-338,422-490` | Provider family is derived from parsed specs with OMP aliases; classification uses structured fields plus normalized tokens and status precedence. | Family behavior is plausible, but token classification is a policy boundary. Unknown, conflicting, or provider-specific text must not become a provider exhaustion observation. Rate-limit is intentionally excluded from cross-family fallback while quota is included. | Require typed provider evidence from adapters. Test direct/OMP alias equivalence, same-family rate-limit/unsupported behavior, cross-family availability/infrastructure/quota, and all conflicting/unknown cases as fail-closed. Never classify raw stderr as T8 policy. |
| `incident/ledger.py:570-670` | Provider streak projection is derived from accepted `worker_terminal_outcome` records carrying a failure key. Success resets; ordinary failure/disposition breaks; changed precondition can rekey. | The projection is the useful streak authority, but it does not consume `provider_observation` events. A separately appended observation can be orphaned or disagree with the terminal-derived streak. | Decide explicitly: terminal outcome is the semantic observation source and `provider_observation` is a linked evidence event, or observation becomes a single atomic projection input. Enforce one-to-one terminal/observation linkage and reject orphan/duplicate observations. |
| `incident/ledger.py:1326-1378` and `incident/schema.py:1083-1085` | Observation append accepts only observation/key/spec/phase/class/epoch. Probe leases have key/expiry and optional parent/phase/route; same-key lease creation is rejected if any prior lease exists. | These helpers are not sufficient by themselves for replay, source reservation binding, provider epoch fencing, or lease recovery. A failed/expired lease can permanently prevent another lease for the key, while a direct observation call can omit its parent terminal. | Extend the existing generic ledger API (not a new journal) with exact parent reservation/terminal, chain identity, provider epoch, evidence digest, and deterministic replay identity. Define expiry/failure/recovery semantics and a bounded single-use lease invariant. |
| `incident/ledger.py:1072-1133` | `reserve_provider_route_child` requires a provider terminal parent, same provider key, passed probe, producer-derived changed precondition, and one composite child reservation event. | This is the right composite door, but all callers must route through it. It must also bind target epoch/key, configuration identity, and source/child receipts; otherwise a healthy target can inherit a source route or cross a reservation. | Add cross-reservation, wrong-epoch, reused-authorizer, crash-after-append, CAS race, and replay tests. Rejected target must cause zero launch-side effects. |
| `incident/schema.py:1083-1085,1190-1217` | Schema distinguishes provider observation/probe events and rejects provider exhaustion mixed with ordinary failure, disposition, or success evidence. | Typed distinctions are good, but the schema fields do not expose enough linkage to prove one accepted logical dispatch generated exactly one observation. | Add only additive fields/versions through the existing schema authority, with compatibility rules and a migration test for old NBF-01 records. |
| `cloud/babysitter/launch.py:611-643` | Typed dispatch outcomes are stored/returned, but callers map terminal kinds to integer status. | A compatibility surface can erase provider-specific semantics if policy/ledger work is deferred until after conversion. | Verify the durable terminal and provider observation precede any integer/API compatibility result; test managed and cloud paths separately. |
| `auto.py` execute/recovery paths (multiple recovery/escalation branches) | Existing execute recovery/escalation can reopen or retry work for artifact/agent reasons. | This is not necessarily provider fallback, but it is a likely bypass of the execute/loop-execute prohibition if it re-enters the same dispatch door. | Classify it explicitly as non-T8 behavior, add a negative test that provider failure cannot trigger it, and ensure its recovery events cannot alter provider streaks. |

Static search found no production call site in the megaplan package that
connects `append_provider_observation`, `create_probe_lease`, or
`append_probe_result` to a typed accepted `provider_exhausted` dispatch and no
call that makes `reserve_provider_route_child` the sole route-selection door.
The existing route-projection and transaction tests exercise the primitives,
but that is not integration evidence.

## Ownership and implementation DAG

1. **A — typed evidence producer (T8 owner).** At the accepted dispatch/worker
   terminal seam, turn only an adapter-supplied structured provider exhaustion
   into the frozen `DispatchOutcome`. Bind reservation, logical dispatch,
   receipt, selected spec, provider epoch, failure key, and terminal evidence.
   Do not inspect stderr or infer exhaustion from ordinary failures.

2. **B — ledger transaction extension (NBF-01 seam, T8 policy owner).** Extend
   the existing `IncidentLedger`/schema/CAS APIs only as needed for atomic
   terminal + linked observation, probe lease/result, changed-precondition
   consumption, and route-child reservation. NBF-06 owns policy decisions;
   NBF-01 remains the storage/lock/projection authority. No provider-specific
   second ledger or projection.

3. **C — chain/config policy.** Harden `fallback_chains.py` and reconcile
   `_advance_configured_spec_fallback` with the single alternate-selection
   door. Normalize chain identity once, persist it with admission, enforce
   provider-family rules, and suppress ambient fallback when configured specs
   exist. Keep scalar pins scalar; do not widen to historical last-known-good.

4. **D — scheduling conditions.** Add the provider hold/degraded/probe
   conditions through the existing orchestration result/classification path.
   Scheduler code may consume typed conditions but must not own provider
   streaks, route selection, or terminal writes. Provider scheduling must not
   enter generic failure/breaker accounting.

5. **E — replay/race/compatibility gate.** Exercise local/cloud/managed paths,
   multiprocess CAS races, torn writes, cache loss, process restart, probe
   expiry/failure, and execute/loop-execute. Only after these pass should the
   NBF-06 checkpoint commit be considered.

The ownership matrix is therefore: T8 policy and evidence production in
NBF-06; generic ledger/schema/CAS in NBF-01; generic launch/admission and
scheduling seams in NBF-02; no provider policy copied into NBF-02/NBF-03; API
compatibility adapters remain consumers and cannot become a third policy door.

## Semantic invariants to freeze before coding

- One accepted exhausted logical dispatch produces one canonical terminal and
  one linked observation. Internal retries are evidence only.
- Only accepted canonical exhausted worker outcomes advance a keyed consecutive
  streak. Probes, waits, probe success, recovery authorization, ordinary
  failures, and dispositions cannot increment or reset it.
- The key is phase + normalized selected spec + typed provider failure class +
  authoritative provider epoch. A provider epoch change is not an implicit
  success; it is an explicit changed-precondition transition.
- First matching exhaustion is streak one and hold/probe. The passed probe and
  its single-use recovery authorization preserve the key/streak. Only the
  authorized child’s accepted matching exhaustion can be observation two.
- Same-family rate-limit/operational behavior and cross-family
  availability/infrastructure/quota behavior must be tested independently;
  unsupported-model semantics must be explicit. Unknown/conflicting evidence
  fails closed.
- A rejected fallback target writes no transition, reservation, WBC attempt,
  provider client/RPC, or launch. A child receipt is derived only after the
  composite reservation append and is replay-stable.
- Execute and loop-execute never advance a configured fallback chain. This
  prohibition is an observable typed decision, not a silent ordinary failure.
- Replay after crash or cache loss reads the ledger and preserves one terminal,
  one observation, one lease, and at most one authorized child. Two processes
  racing on the same projection produce one winner and a typed CAS loser.

## Backwards compatibility and migration

Read old NBF-01 records as immutable history. Missing provider fields mean
“not a provider observation,” never “unknown provider exhaustion.” Additive
schema versions may accept legacy ordinary terminals, but cannot synthesize a
provider key, epoch, observation, or route authorization. Any ambiguous legacy
provider record must become a held/unresolved state with a repair reason.

Keep the existing encoded chain form
`__fallback_json__:[...]` for compatibility, while binding its normalized
bytes, phase, profile/source digest, and provider-family interpretation to the
admission/child receipt. Reject malformed, duplicate, or conflicting phase
entries instead of silently selecting the first valid-looking entry.

The managed/cloud integer return contract may remain, but only after the typed
outcome and ledger records are durably committed. Replay of a completed
provider terminal must return the original typed receipt/decision, not launch a
new worker because a compatibility caller lost in-memory metadata.

## Forbidden scope

- A second scheduler, provider breaker, rotator, journal, projection, cache, or
  admission/terminal authority.
- Raw stderr or English-message policy; generic ordinary failures promoted to
  provider exhaustion.
- Fallback advancement from execute/loop-execute, post-tool writes, or any
  path that can duplicate a side effect.
- Changes to NBF-04/05 signal custody, shell authority, or unrelated provider
  transport behavior except a typed evidence adapter contract.
- Historical last-known-good widening, time/sleep-only streak resets, probe
  success as a streak reset, or a direct provider route switch outside the
  composite ledger door.
- Treating `auto.py` artifact recovery/escalation as T8 provider policy.

## Hidden blockers and focused closure tests

The first implementation review should require these named tests, in addition
to the tasklist's focused command:

1. **Producer linkage:** typed exhaustion with every receipt field yields one
   terminal + one observation; missing/unknown/ordinary evidence yields no T8
   observation.
2. **Observation cardinality:** duplicate terminal callback, crash after
   terminal append, and replay return the same observation; orphan direct
   observation is rejected.
3. **Streak transitions:** first match, second authorized-child match,
   success reset, different-key rekey, intervening ordinary/disposition break,
   and key-preserving versus key-changing precondition.
4. **Probe authority:** one active lease, expiry/recovery behavior, failed
   probe launches nothing, passed probe preserves the key, and stale/wrong
   epoch/parent/route evidence is rejected.
5. **Route CAS:** two processes race for fallback/return; one composite event
   and one child win, with zero effects from the loser. Replay and torn-write
   recovery remain idempotent.
6. **Configuration:** malformed/duplicate phase entries fail loudly; direct and
   OMP aliases have the expected family; chain identity changes invalidate
   stale child/fallback metadata.
7. **Ambient isolation:** explicit configured chains suppress agent-level
   `_runtime_fallback_candidates`; legacy ambient fallback cannot occur after an
   accepted worker outcome or without a ledger decision.
8. **Side-effect safety:** execute and loop-execute raise/return the typed
   prohibition before a second provider client, WBC, RPC, or worker launch.
9. **Cloud/managed parity:** typed provider outcome is durably recorded before
   babysitter/managed integer conversion; provider scheduling never becomes a
   generic blocked/breaker result.

Run the tasklist command plus these static traces as the initial audit:

```bash
rg -n "append_provider_observation|create_probe_lease|append_probe_result|reserve_provider_route_child" arnold_pipelines/megaplan
rg -n "_advance_configured_spec_fallback|_runtime_fallback_candidates|ExecuteFallbackUnsafe" arnold_pipelines/megaplan/workers/_impl.py arnold_pipelines/megaplan/fallback_chains.py
rg -n "provider_exhausted|provider_observation_wait|provider_degraded|provider_probe" arnold_pipelines/megaplan
pytest -q tests/arnold_pipelines/megaplan/test_fallback_chains.py tests/arnold_pipelines/megaplan/test_provider_route_projection.py
```

The final focused gate must additionally include the full NBF-06 list in
`.oracle/tasklist.md`, with new provider-scheduling tests and explicit replay,
race, cache-loss, and execute-prohibition evidence paths. No broad repository
pass should substitute for those authority-specific proofs.

## Recommendation

Proceed with NBF-06 only as a staged integration of the existing typed outcome,
ledger/CAS, fallback-chain, and scheduling seams. The highest-risk first slice
is not the streak arithmetic; it is proving that there is exactly one accepted
provider-exhaustion producer and exactly one configured route-selection door.
Resolve that ownership ambiguity, then make observation/terminal linkage and
probe/child replay atomic. Until those are demonstrated, the existing unit
fixtures show useful primitives but do not establish the tasklist's T8
acceptance criteria.
