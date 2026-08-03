# a02-s09-identity-version-provenance-notification-escalation: identity-version-provenance × notification-escalation

## Verdict

FAIL. A durable ledger/outbox foundation exists, but notification admission, authority transitions, provider receipts, and legacy/direct notification paths do not enforce one immutable run/attempt/incarnation/version/launch-provenance tuple.

P0 gaps can mutate authority or cause a stale user notification. P1 gaps can misreport delivery/escalation state or create duplicate provider effects. No P2-only issue was found.

## Intended canonical contract

The canonical foundation should be `SqliteLedgerOutbox`: it atomically commits ledger events and outbox records, rejects divergent idempotency duplicates, and enforces attempt sequencing (`arnold/workflow/ledger_outbox.py:299-313`, `339-360`, `376-465`, `468-555`). Its events already carry attempt identity, provenance, adapter, versions, and grant references (`arnold/workflow/execution_attempt_ledger.py:423-577`, `812-846`).

For this surface, `IncidentNotificationStore` should be the sole incident/escalation facade, extended with a required immutable envelope containing:

- run ID, attempt ID, incarnation/lease identity, graph/code/schema version;
- launch provenance and custody/source identity;
- canonical payload and provider-request digests;
- authority grant and actor identity.

That envelope must be present in the occurrence, ledger event, outbox payload, provider attempt/receipt, and authority transition. Provider delivery must consume only canonical outbox rows. Resident Discord provenance validation is the reusable source-custody implementation (`resident/provenance.py:154-223`), and runner incarnation validation is already implemented (`_core/phase_runtime.py:63-73`, `179-245`).

A complete canonical implementation does not currently exist.

## Evidence and complete path inventory

I searched with `rg --files` for notification, incident, outbox, escalation, review, watchdog, resident, provenance, and Discord files; then searched all Python, shell, schema, documentation, and test files for `incident`, `occurrence`, `outbox`, `dedup`, `escalat`, `notification`, `provenance`, `incarnation`, `attempt_id`, `run_id`, and `version`. I separately searched exact symbols and destinations, including `send_discord_escalation`, `notification:discord`, `record_provider_attempt`, `authority_transition`, and `get_pending`.

Observed writers and callers:

- `IncidentNotificationStore.admit` creates the occurrence, ledger event, and `notification:discord` outbox intent (`cloud/incident_notification.py:170-307`); `human_review_diagnostic` calls it (`cloud/human_review_diagnostic.py:391-453`); watchdog delegates to that launcher (`cloud/wrappers/arnold-watchdog:1135-1151`).
- Provider status writers are `record_provider_attempt` and `record_provider_receipt` (`cloud/incident_notification.py:367-453`), called by compatibility fallback recording (`cloud/human_review_diagnostic.py:651-698`).
- Authority writers are `authority_transition` and the incident authority table (`cloud/incident_notification.py:465-530`, `44-79`).
- M1 incident writers include `append_watchdog_detection`, `append_watchdog_dispatch`, and repair-attempt helpers (`cloud/incident_bridge.py:254-333`, `380-427`), backed by a schema where identity fields are optional (`incident/schema.py:24-53`).
- Legacy sidecar writers include `EscalationLedgerWriter`, progress-auditor escalation, terminal-audit incidents, and JSONL append helpers (`cloud/human_blockers.py:643-711`, `852-905`; `cloud/progress_auditor_controller.py:175-193`; `cloud/terminal_audit.py:136-150`; `cloud/repair_contract.py:3616-3640`).
- Direct notification writers are the repair wrapper’s `send_discord_escalation` (`cloud/wrappers/arnold-repair-loop:8392-8601`) and `send_discord_dm` (`discord_dm.py:63-217`). `agentbox_adapter` can call it without the delivery adapter (`agentbox_adapter.py:934-948`).
- The generic outbox exposes `get_pending`, `mark_dispatched`, and `mark_failed` (`arnold/workflow/ledger_outbox.py:557-590`, `674-690`). No in-repository consumer specifically handles `destination == "notification:discord"`; exact searches found only its construction in `cloud/incident_notification.py:252-267` and generic outbox APIs.

Readers/consumers include `dispatch_eligible` (`cloud/incident_notification.py:455-463`), mutable incident cards (`533-565`), human-review state, M1 projections/summaries (`incident/projection.py:38-110`; `incident/summaries.py:79-129`), and wrapper reports. The existing tests cover same-identity concurrency, restart replay, and indeterminate provider state (`tests/cloud/test_incident_notification_ux.py:54-84`, `134-160`, `197-271`), but not cross-boundary identity rejection.

## Adherence gaps

1. P0 — authority mutation. `authority_transition` accepts only occurrence, action, authority ID, and actor ID; it does not require or validate run, attempt, incarnation, version, launch provenance, or a current authority grant (`cloud/incident_notification.py:465-505`). It then mutates authoritative `authority_state_json` (`487-505`). The unique `(occurrence_id, action)` constraint prevents a second identical action, not a stale action.

   Separately, the admission event uses `run_id=session` (`cloud/incident_notification.py:228-245`), while the terminal event for the same attempt uses `run_id=occurrence_id` (`309-354`). The generic outbox checks attempt ID and sequence, but not stable run identity across events (`arnold/workflow/ledger_outbox.py:362-365`, `452-465`). Inference: stale or cross-run terminal evidence can be accepted into the same attempt stream.

2. P0 — stale notification effect. Admission binds identity to `session`, hardcodes `state_version = 1`, derives the diagnostic attempt only from `occurrence_id`, and has no incarnation or launch-provenance field (`cloud/incident_notification.py:170-234`). The watchdog payload likewise contains session/workspace/plan/failure information but no attempt, incarnation, or launch provenance (`cloud/wrappers/arnold-watchdog:1021-1082`). Inference: an old process or old version can replay a notification into the current notification namespace if the occurrence key is reused or forwarded.

   The legacy repair function bypasses admission and directly invokes `$DISCORD_DM_BIN` (`cloud/wrappers/arnold-repair-loop:8392-8548`). It remains reachable when shell-sourced: the test extracts and invokes it directly (`tests/cloud/test_watchdog_wrappers.py:9585-9627`), and another test explicitly asserts the function remains in the wrapper (`9968-9987`). This is an independently evidenced duplicate provider path.

3. P1 — provider-attempt and receipt misbinding/status misreporting. Provider rows contain intent, attempt number, status, and request digest, but no occurrence/run/incarnation/version/provider identity or launch provenance (`cloud/incident_notification.py:58-67`). `record_provider_attempt` does not verify that the intent exists or that the request digest matches the admitted payload (`367-396`); receipts update any existing `(intent, attempt_number)` row (`398-453`). `dispatch_eligible` is true when no provider row exists (`455-463`). Inference: phantom attempts, mismatched receipts, and stale provider workers can produce false delivery eligibility or status.

4. P1 — non-atomic occurrence projection. The ledger event and outbox commit first; `incident_occurrences` is inserted in a separate transaction (`cloud/incident_notification.py:267-293`). A crash between those commits leaves an outbox/event without the occurrence row. The existing restart test only proves replay repairs the common case (`tests/cloud/test_incident_notification_ux.py:197-219`), not orphan detection or rejection of a provider/authority operation during the gap.

5. P1 — duplicate status authorities. M1 events permit optional session/attempt fields and no incarnation/version/launch-provenance contract (`incident/schema.py:24-53`; `cloud/incident_bridge.py:254-333`). Legacy JSONL sidecars independently record incidents/escalations with session-only lifecycle identity (`cloud/human_blockers.py:852-905`). Their append implementation performs unlocked read-modify-write and derives `_sequence` from the current file length (`cloud/repair_contract.py:3423-3448`, `3571-3603`), so concurrent containers/PID namespaces can lose records or duplicate sequence numbers. This is status/evidence misreporting unless a caller promotes the sidecar to authority.

6. P1 — delivery adapter identity is synthetic and bypassable. `DeliveryEffects` creates `del-*` run IDs and an `m10` version from the delivery target, not from the originating incident/run/attempt (`resident/delivery_effects.py:143-174`). `send_discord_dm` falls through to direct HTTP delivery if adapter routing raises (`discord_dm.py:114-217`). This defeats a single durable notification boundary.

## Incident reachability and severity

Observed path: watchdog → `human_review_diagnostic` → `IncidentNotificationStore.admit` → generic ledger/outbox. That path has durable dedupe, but not the full invariant tuple. A separate observed path is repair wrapper → direct Discord helper. A third is generic agentbox completion → direct Discord helper without an adapter.

The P0 classification is an inference from the authority/effect semantics: the code demonstrably permits authority-table mutation and direct provider invocation without the required fencing; whether production deployment currently exercises the stale-input case is unknown. P1 findings are directly reachable status/evidence inconsistencies and concurrency hazards.

## Minimal generalized remediation

Add one required provenance envelope to `IncidentNotificationStore`; persist it with the occurrence and the same SQLite transaction as the ledger/outbox append. Require exact equality on replay and reject mismatched run, attempt, incarnation, version, launch provenance, or payload digest.

Pass the original run identity into `record_diagnostic_terminal`; validate provider attempt/receipt against the admitted envelope and provider request digest; require authority transitions to carry a current authority grant and the same envelope.

Route all incident notifications through one outbox consumer. Remove direct incident calls to `send_discord_dm`. Migrate legacy sidecars as non-authoritative historical data, then delete `send_discord_escalation`, `EscalationLedgerWriter`, and direct incident/M1 notification writers. This is narrower than a rewrite because the generic transactional/deduplication primitive already exists.

## Required tests and retirement proof

Add deterministic tests for:

- two processes, two containers, and distinct PID namespaces admitting the same and different provenance tuples;
- crash/restart at every boundary between occurrence, ledger, outbox, provider attempt, receipt, and card projection;
- stale run, attempt, incarnation, version, launch-provenance, provider, and request-digest inputs producing no provider call or authority mutation;
- duplicate and divergent idempotency keys, provider success/failure/indeterminate outcomes, and receipt mismatch;
- stale acknowledge/resolve attempts rejected by authority fencing;
- PID reuse, foreign namespace, missing incarnation, and lease-backed observations using `phase_runtime` semantics.

Retirement proof must include `rg`/AST checks showing zero definitions, shell references, imports, and tests for `send_discord_escalation`, `EscalationLedgerWriter`, and incident-sidecar writes; a two-container test must prove no sidecar writer remains reachable. Existing tests currently prove the opposite for the legacy function (`tests/cloud/test_watchdog_wrappers.py:9585-9627`, `9985-9987`).

## Unknowns

No in-repository `notification:discord` worker was found; its deployment may be external or absent. No service or cloud state was launched or inspected. The stale-cross-boundary outcomes are therefore reachability inferences from accepted inputs and missing validation, not an observed production incident.