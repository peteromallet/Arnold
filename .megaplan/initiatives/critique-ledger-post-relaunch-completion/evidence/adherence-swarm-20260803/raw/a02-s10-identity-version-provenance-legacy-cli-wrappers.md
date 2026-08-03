# a02-s10-identity-version-provenance-legacy-cli-wrappers: identity-version-provenance × legacy-cli-wrappers

## Verdict

Not adherent. No P0 was observed; the highest findings are P1.

The main P1 is an authority-mutation path: legacy producers can write accepted repair requests with empty or non-canonical occurrence identity, and `arnold-repair-trigger` can read, claim, reconstruct, and delegate them. Separate P1 status/provenance gaps remain in the legacy CLI and shell reducers.

Search performed: `rg --files`, then repository-wide `rg` searches across `arnold`, `arnold_pipelines`, `tests`, `scripts`, and `tools` for `legacy`, `compat`, `fallback`, `wrapper`, `run_id`, `run_revision`, `incarnation`, `provenance`, `latest_failure`, `enqueue_repair_request`, `iter_repair_*`, `write_decision`, `write_dispatch_attempt`, and `resolve_run_state`; every production hit was inspected with numbered source context and its callers traced.

## Intended canonical contract

The canonical authority contract is `arnold_pipelines/run_authority/contracts.py:100-134`: versioned, typed serialization with strict fields and schema validation. Claims and decisions must carry run, revision, subject, attempt, grant, coordinator, fence, evidence, and idempotency data (`:271-337`), and `validate_relationships` rejects run/revision/coordinator/fence/evidence mismatches (`:432-483`).

The canonical repair-side mutation funnel is `arnold_pipelines/megaplan/cloud/wrappers/repair_delegation.py:74-126,218-245`, which validates an exact F01 occurrence and funnels effects through `simple_fixer`. However, it carries only caller/F01 identity, not the complete Run Authority, provider, runtime, incarnation, and launch-provenance chain. There is therefore no single end-to-end canonical implementation for this invariant×surface boundary.

`arnold_pipelines/megaplan/run_state/resolver.py:1-11,42-70` is the canonical status reducer and is pure/read-only. Legacy consumers should supply it authoritative evidence rather than independently reducing `state.json`, logs, process lists, or repair projections.

## Evidence and complete path inventory

Writers:

- `arnold_pipelines/megaplan/cloud/repair_requests.py:860-888,960-1103` writes queue requests and accepted decisions. `manual_repair_trigger.py:449-459` calls this generic path without `repair_identity`; `six_hour_auditor.py:424-457` also calls it, although it supplies a non-canonical F01-shaped identity. `supervise.py:316-335` uses the stricter occurrence-bound entrypoint.
- Legacy CLI handlers remain reachable through `arnold_pipelines/megaplan/__main__.py:1-7` and `cli/__main__.py:1-5`. The parser exposes phase commands, status, and override (`cli/__init__.py:165-171,236-298`); override mutates state and emits a receipt (`handlers/override.py:2158-2175`); resume directly clears pause fields, writes `state.json`, and dispatches execution (`cli/__init__.py:2281-2329`).
- Shell wrappers launch or classify work: `cloud/wrappers/arnold-chain:9-48`, `arnold-run:7-20`, `arnold-supervise:83-165,173-220`, `arnold-repair-loop:1208-1293,3411-3561`, and `arnold-cloud-discover:153-208`.

Readers:

- Queue readers only shape-check records: `repair_requests.py:1289-1389` validates minimal keys but not the schema value, complete identity, provenance, or cross-contract relationships.
- The legacy CLI loads raw plan state (`cli/status_view.py:1292-1300`) and derives status from `latest_failure` (`:399-405,1203-1208`), without calling the canonical resolver.
- `arnold-repair-trigger` reads requests (`cloud/wrappers/arnold-repair-trigger:185-220,299-318`), claims them (`:594-610`), and reconstructs target identity with fallback/default values (`:1019-1053`).
- Wrappers independently read logs, chain files, `state.json`, repair-data, process tables, and event tails (`arnold-supervise:113-158`; `arnold-repair-loop:1250-1293,3411-3561`; `arnold-progress-auditor:2665-2689,2790-2830`; `arnold-cloud-discover:153-208`).

Consumers:

- `arnold-repair-trigger` delegates to simple_fixer and records dispatch/decision artifacts (`arnold-repair-trigger:1080-1105`).
- `repair_delegation.py:218-340` is the intended mutation funnel.
- Recovery/status projections consume unbound events and queue records (`recovery_events.py:64-102,263-393`).

## Adherence gaps

1. **P1 — authority mutation: generic legacy enqueue accepts unbound evidence.**  
   `repair_request_contract_violations` checks blocker, source/session provenance, and signature evidence, but never requires `repair_identity` or Run Authority identity (`repair_requests.py:788-857`). The generic writer explicitly preserves an empty identity for legacy callers (`:1009-1045`). The test makes this behavior contractual: `tests/cloud/test_repair_enqueue_producers.py:219-245` asserts a request without occurrence identity is queued.

   Because the trigger shape-reader accepts it (`repair_requests.py:1289-1318`), then claims it (`arnold-repair-trigger:594-607`) and reconstructs missing fields from signatures/defaults (`:1019-1053`), stale evidence can reach an effect boundary. This is an authority mutation gap, not merely reporting.

2. **P1 — authority mutation: “occurrence-bound” identity is not the canonical occurrence contract.**  
   `enqueue_occurrence_bound_repair_request` requires ten F01 strings but passes them as fields named `environment`, `session`, `chain`, etc. (`repair_requests.py:2430-2520`). The actual `normalize_repair_occurrence_key` accepts either the old names (`environment_id`, `session_id`, etc.) or a current `{target, run_id, run_revision, ...}` object (`custody/contracts.py:712-751`). Consequently, the generic fallback copies arbitrary F01 fields without producing a canonical occurrence key or deterministic identity key (`repair_requests.py:57-114,1009-1045`).

   The downstream delegation validates F01 only (`repair_delegation.py:101-117`), so run revision, coordinator attempt, grant, incarnation, provider, and launch provenance remain unbound.

3. **P1 — authority mutation: heuristic identity derivation in the supervised wrapper.**  
   `supervise.py:291-335` derives identity from log path, marker files, and current plan. Its “fence” is log `mtime_ns:size` (`:343-350`), plan revision falls back to a marker/path hash (`:352-374`), and attempt is approximated from `st_nlink` (`:377-385`). These are rebuildable filesystem observations, not run/attempt/incarnation/version provenance. The wrapper then queues the result (`arnold-supervise:173-198`).

4. **P1 — status misreporting, with launch consequences: duplicate reducers bypass the resolver.**  
   `arnold-supervise` selects the newest chain by mtime and reads `latest_failure` directly (`:113-158`). `arnold-repair-loop` first classifies raw logs, chain summaries, state, and event tails, then consults the resolver afterward (`:3411-3455`), retaining independent fallback classifications (`:3519-3561`). The auditor also has a bounded event-tail compatibility reader (`arnold-progress-auditor:2804-2829`). These readers can disagree across restart or stale-state boundaries.

5. **P1 — status/provenance: recovery events are time-identified and unbound.**  
   `RecoveryEvent` has no typed run, revision, attempt, incarnation, provider, or launch fields (`recovery_events.py:64-102`). Blocker and process-exit IDs include wall-clock microseconds (`:263-309`), and subsequent event IDs do the same (`:311-393`). `persist_failure_occurrence` writes such events into repair evidence without exact occurrence identity (`repair_requests.py:2303-2373`). This permits duplicate/replayed status and SLO evidence to be mistaken for a new occurrence.

6. **P1 — authority mutation: launcher acceptance is fail-open.**  
   `arnold-chain` treats missing or malformed acceptance-gate output as open (`:24-30`) and starts `chain start` without run/attempt/version/launch identity (`:43-48`). `arnold-repair-trigger` likewise makes dedicated runtime selection optional by default (`arnold-repair-trigger:45-64`). The shared runtime library has strong checks when used (`arnold-supervisor-runtime-lib:65-131`), but the trigger can bypass that attestation path.

7. **P2 — legacy retirement incomplete.**  
   The M6 deletion list says legacy CLI surfaces and phase commands are deleted (`arnold/conformance/deleted_surfaces.py:53-57`), but the Megaplan CLI remains executable and exposes them. Deprecated aliases remain reachable: `mp-chain`, `mp-run`, and `mp-supervise` delegate, while `mp-heartbeat` drops arguments (`cloud/wrappers/mp-*:1-4`). Legacy custody constructors also remain constructible and serialize predecessor shapes (`custody/contracts.py:322-380,437-449,557-683,825-901`).

## Incident reachability and severity

Observed path: legacy CLI/wrapper reader or producer → generic queue request → `accepted` decision → trigger shape-read and claim → fallback target reconstruction → simple_fixer delegation/dispatch (`repair_requests.py:1097-1103`; `arnold-repair-trigger:594-610,1019-1105`).

Inference: if mutation feature flags are enabled and no later custody check rejects the reconstructed target, stale or cross-attempt evidence can cause a repair against the wrong occurrence. Existing simple_fixer F01 validation and namespace-aware repair lock reduce the blast radius (`repair_delegation.py:101-117`; `repair_lock.py:145-152,652-673`), so this audit rates the reachable gaps P1 rather than P0.

## Minimal generalized remediation

- Make the generic enqueue function reject absent or non-canonical identity. Migrate `manual_repair_trigger.py` and every remaining producer to one adapter that accepts a fully decoded `RepairOccurrenceKey` plus Run Authority grant/fence/attempt and runtime/launch receipt.
- Make accepted/dispatched queue records projections only; before claim or mutation, decode and validate the complete Run Authority relationship chain. Remove all defaulting and reconstruction in `arnold-repair-trigger:1019-1053`.
- Replace wrapper/CLI reducers with `resolve_current_target` + `resolve_run_state`; retain raw files only as evidence inputs, never as independent status or launch authority.
- Make runtime receipt, provider route, source revision, wrapper digest, process birth, PID namespace, and container identity mandatory at launch.
- Delete or hard-fail old CLI/`mp-*` entrypoints after call-site migration. Do not retain compatibility constructors on active mutation paths.

## Required tests and retirement proof

- Reject missing, partial, F01-only, wrong-run, wrong-revision, wrong-attempt, wrong-fence, stale-version, provider-mismatch, and missing-launch-receipt records at enqueue, read, claim, and mutation boundaries.
- Concurrency/restart: two producers and two triggers for the same identity; replay after restart; deterministic decision/attempt IDs without wall-clock entropy; stale evidence after a newer revision.
- Provider/runtime: selected provider/model/profile, actual interpreter/import root, source revision, wrapper hash, and launch argv must round-trip and mismatches must fail closed.
- Mutation: accepted queue evidence alone must never mutate; only a validated Run Authority + Custody + simple_fixer chain may do so.
- Two-container/PID namespace: shared-volume lock ownership, PID reuse, boot-id changes, namespace mismatch, and cross-container release/reclaim. The existing lock implementation is the model (`repair_lock.py:381-395,652-673`).
- Retirement proof: repository-wide `rg` shows zero production callers of generic enqueue, old CLI modules, or direct fallback reducers; subprocess tests show old entrypoints exit typed failure and write no state, queue, decision, or dispatch artifacts.

## Unknowns

No services, cloud state, or installed deployment images were inspected. The repository cannot establish which legacy aliases are deployed externally. Feature-flag activation in production is also unknown. The durable repair lock and exact fallback digest checks appear guarded, but their runtime deployment parity remains unverified (`arnold-supervisor-runtime-lib:205-228`).