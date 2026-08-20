FAIL

# T1.10 notification UX adversarial review pass 1

Reviewed exactly commit `d060d7ce1b2ac09f36f828c2136dc2e5dacbad62` in
`/private/tmp/arnold-critique-recovery-notification-ux-20260802`. The worktree
was clean and remained unmodified. The implementation does not satisfy the
intended notification-authority contract.

## Defects

### 1. CRITICAL — admission manufactures shadow authority

Location: `arnold_pipelines/megaplan/cloud/incident_notification.py`,
`IncidentNotificationStore.admit()` lines 170–267, especially line 243;
`record_diagnostic_terminal()` lines 309–354, especially line 338.

Reproduction/reasoning: `admit()` constructs
`GrantRef("run-authority:incident-notification-admission")`; terminal recording
constructs another synthetic `GrantRef`. `GrantRef` only requires nonempty
text. This module does not load or validate a current Run Authority decision,
grant capability, coordinator fence, Custody lease/epoch, or WBC evidence, and
does not call the existing action gate. A call with no authority records a
ledger STARTED event and a pending outbox row. The probe printed:
`{'grant_id': 'run-authority:incident-notification-admission'}`.

Minimum root fix: admission and diagnostic terminalization must accept and
persist real current RA/Custody/WBC evidence and pass the conjunctive action
gate; synthetic strings must never satisfy the authority boundary.

### 2. CRITICAL — caller-selected SQLite roots create parallel custody islands

Location: `incident_notification.py`, `IncidentNotificationStore.__init__()`
lines 136–155; `human_review_diagnostic.py`, launch setup lines 391–425 and
CLI arguments lines 702–713.

Reproduction: admitting the same occurrence into two temporary roots produced
two `duplicate=False` admissions, identical `notify-*` IDs, and two separate
databases:
`<root-a>/.incident-notifications.sqlite3` and
`<root-b>/.incident-notifications.sqlite3`, each with a pending outbox row.
The 200-scan test exercises only one root.

Minimum root fix: resolve the trusted owner WBC/Custody store from current
runtime authority; remove caller control over the authoritative store path and
reject store-identity/fence mismatches.

### 3. CRITICAL — diagnostic launch creates a second notification identity

Location: `human_review_diagnostic.py`, `_task_text()` lines 264–331 and
`launch_human_review_diagnostic()` lines 569–587; resident delivery in
`arnold_pipelines/megaplan/resident/subagent.py` lines 4103–4115 and 7206–7213.

Reproduction/reasoning: after admission, a valid-provenance diagnostic launches
`launch_subagent_task()` with a task that tells the resident completion turn to
send the user a notification. The resident path then creates
`resident-subagent-completion:<run_id>` and sends `OutboundMessage`, while the
incident store already owns a separate `notify-*` `notification:discord` outbox
intent. The original incident outbox is not claimed or completed by the
resident delivery. Therefore one incident can have two independently accepted
delivery identities, and the diagnostic/watchdog path is not enqueue-only.

Minimum root fix: make the diagnostic completion worker claim and terminalize
the one canonical incident intent/GLEK, or make diagnostic launch strictly
non-delivery and leave provider calls exclusively to the canonical outbox
worker.

### 4. CRITICAL — provider attempt claims and receipts are not fenced or monotonic

Location: `incident_notification.py`, `record_provider_attempt()` lines 367–396,
`record_provider_receipt()` lines 398–453, and `dispatch_eligible()` lines
455–463.

Reproduction: two calls for the same intent/attempt with request digests
`sha256:req1` and `sha256:req2` both returned `provider-<intent>-1`; the stored
digest remained only `req1`. An unknown intent accepted attempt 99 and an empty
receipt as `SUCCEEDED`. A `SUCCEEDED` receipt was then overwritten by `FAILED`.
After attempt 1 became `INDETERMINATE`, the API still accepted attempt 3. A
second attempt manually marked `FAILED` made `dispatch_eligible()` return
`True` despite the earlier ambiguity. The method examines only the highest
attempt and there is no intent-level sticky terminal/ambiguity row.

Minimum root fix: atomically claim `(intent, attempt, request_digest)` with a
fenced CAS, reject unknown intents and divergent claims, validate receipt
schema/evidence, make terminal outcomes immutable, and make
`INDETERMINATE` sticky across all later attempts until explicit reconciliation.

### 5. CRITICAL — provenance-pending data is stored under a real Discord route

Location: `incident_notification.py`, `_stable_recipient()` lines 102–118 and
outbox construction lines 252–265; provenance validation in
`human_review_diagnostic.py` lines 533–567.

Reproduction: missing provenance produced an outbox row with
`destination='notification:discord'` and
`recipient='discord:provenance-pending:sha256:...'`. The diagnostic then writes
`fallback_delivery.status='not_permitted'`, but does not tombstone or disable
the pending outbox. There is no provider worker in this commit that rejects
this recipient; the repository search found no consumer implementing that
refusal. Thus the safety claim is only a projection/comment, not an enforced
boundary.

Minimum root fix: represent pre-provenance identity as non-dispatchable
custody, and atomically tombstone it on provenance failure; the delivery worker
must reject the marker before any provider call.

### 6. HIGH — acknowledgement/resolution accepts forged callers and regresses state

Location: `incident_notification.py`, `authority_transition()` lines 465–530.

Reproduction: `authority_id='forged'` and `actor_id='forged'` were accepted for
acknowledgement with no owner/current-authority lookup. A resolve followed by
acknowledge accepted both and left `resolved=true` while changing
`authority_state` back to `acknowledged`. Divergent same-action requests are
blocked only by the raw `UNIQUE(occurrence_id, action)` SQLite error; the first
arbitrary caller wins and no typed conflict/fence evidence is recorded.

Minimum root fix: validate the authenticated actor and action-scoped current
RA/Custody authority, use an immutable request digest and legal monotonic CAS
transitions, and record typed conflict/quarantine evidence.

### 7. HIGH — hard-coded version prevents meaningful state transitions

Location: `incident_notification.py`, `admit()` lines 196–214 and 252–264.

Reproduction: replaying the same occurrence with a changed state and payload
raised `DivergentDuplicateError` for the fixed key
`incident-opened:<occurrence>:v1`; it did not enqueue one new versioned
notification. Repeated identical observations do deduplicate, but the state
machine cannot advance because `state_version = 1` is never read from or
incremented in durable authority state.

Minimum root fix: derive the next legal state/version from canonical authority,
bind each transition to its exact request digest, and atomically admit exactly
one new intent for each meaningful transition.

### 8. HIGH — projection/state recovery is not rebuildable

Location: `incident_notification.py`, `write_card()` lines 356–365 and card
update paths lines 432–452 and 509–523; `human_review_diagnostic.py`, state
handling lines 455–498 and 623–648.

The ordinary simulated crash after ledger/outbox commit and before the
`incident_occurrences` transaction was replayable: a later identical admission
returned `duplicate=True` and inserted the missing occurrence. That is the
working case, not a complete recovery implementation. If `state.json` is left
as `launching`, the next launch returns that projection instead of reconciling
or retrying. If `incident-card.json` is deleted or malformed while state is
`launched`, the launched-state path returns without rebuilding it. Receipt and
authority updates silently ignore missing/malformed cards. There is no card
reducer/rebuild function; `write_card()` accepts arbitrary caller-supplied JSON.

Minimum root fix: make launch claims and terminal evidence canonical, add a
deterministic reducer that rebuilds state/card from ledger, outbox, provider
attempt/result, and authority rows, and never let a projection suppress
reconciliation.

### 9. HIGH — outbox duplicate checks omit the outbox payload and commit ambiguity

Location: `arnold/workflow/ledger_outbox.py`,
`SqliteLedgerOutbox.append_event_with_outbox()` lines 376–435 and 533–547.

Reproduction: replaying an exact duplicate event with a different outbox ID,
destination payload, and recipient returned `is_duplicate=True`; the original
outbox payload remained unchanged and no divergent-payload error was raised.
The duplicate comparison covers only the ledger event JSON. The commit handler
also catches any `COMMIT` exception and attempts `ROLLBACK`, with no durable
reconciliation for the case where SQLite committed but reported an ambiguous
error. WAL is enabled by `attempt_ledger_store.py` lines 1147–1155, but this is
not an outbox identity/payload or commit-outcome protocol.

Minimum root fix: bind and compare the canonical outbox payload/destination to
the event identity, and add an explicit commit-ambiguity reconciliation path
that fails closed without losing the ability to discover an already-committed
intent.

### 10. HIGH — fallback result recording can fabricate delivery

Location: `human_review_diagnostic.py`, `record_fallback_delivery()` lines
651–699.

Reproduction/reasoning: the command accepts arbitrary result JSON, sets local
state to `delivered` from `ok` plus arbitrary `message_ids`/`message_count`,
then swallows all provider-attempt/receipt persistence errors. It can therefore
produce a delivered projection without a valid canonical intent or receipt.

Minimum root fix: retire the compatibility command, or make it a canonical
worker operation with validated provider evidence, intent binding, monotonic
receipt CAS, and no state success before durable receipt acceptance.

### 11. HIGH — old direct Discord/JSONL notification paths remain executable

Location: `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop`,
`send_discord_escalation()` lines 8400–8615, including the
`arnold-discord-dm` call at line 8556 and legacy `EscalationLedgerWriter` write
at lines 8469–8482. Sequence assignment remains unlocked whole-file counting
in `arnold_pipelines/megaplan/cloud/repair_contract.py`,
`append_jsonl_record()` lines 3571–3603. The watchdog also writes
`authority-gaps.jsonl` in `arnold-watchdog` lines 183–220.

The changed watchdog itself has no direct `curl`, `arnold-discord-dm`, or
`write_opened` call, and its narrow test passes. However, the sibling repair
wrapper still contains a direct provider path and the legacy JSONL writer; the
tests explicitly extract and exercise that function rather than proving it is
retired. This leaves a stale bypass alongside the new store.

Minimum root fix: remove the direct provider function and legacy notification
ledger from all production wrappers; route any evidence-only JSONL through a
non-authoritative diagnostic surface that cannot dispatch or assign authority.

### 12. HIGH — some failures do not return a stable result/path from the launch API

Location: `human_review_diagnostic.py`, `launch_human_review_diagnostic()` lines
398–412 and `_escalation_id()` lines 225–261.

Reproduction: a malformed payload raised `ValueError` before identity/state
creation; a `stable_human_gate` with an invalid state token also raised
`ValueError` before admission. The direct launch API returned no stable ID or
state path. The CLI catches this later and synthesizes an ID at lines 728–760,
but does not create durable identity/state for the failure.

Minimum root fix: create a stable diagnostic identity/path from bounded raw
input before all validation, persist a typed terminal failure when possible,
and return the same structured result from both API and CLI surfaces.

### 13. MEDIUM — clean cloud materialization omits the diagnostic wrapper

Location: `arnold_pipelines/megaplan/cloud/template.py`,
`materialize_deploy_dir()` lines 385–395.

The explicit shipped-wrapper allowlist includes `arnold-watchdog` and repair
wrappers but not `arnold-human-review-diagnostic`. The watchdog has a source
module fallback, so this is not proof of a local failure, but a clean image has
no dedicated helper executable and deployment behavior depends on the fallback
module being present and importable.

Minimum root fix: include and test the diagnostic wrapper in the materialized
image, or make the module fallback an explicit packaged/runtime contract.

## Verification performed

Commands and results:

```text
PYENV_VERSION=3.11.11 python -m pytest \
  tests/cloud/test_incident_notification_ux.py \
  tests/cloud/test_human_review_diagnostic.py \
  tests/cloud/test_watchdog_wrappers.py -q
397 passed in 461.48s (0:07:41)

PYENV_VERSION=3.11.11 python -m pytest tests/arnold/workflow/test_ledger_outbox.py -q
41 passed in 0.47s

git diff --check d060d7ce1b2ac09f36f828c2136dc2e5dacbad62^ d060d7ce1b2ac09f36f828c2136dc2e5dacbad62
bash -n arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog \
  arnold_pipelines/megaplan/cloud/wrappers/arnold-human-review-diagnostic
PYENV_VERSION=3.11.11 python -m py_compile \
  arnold/workflow/ledger_outbox.py \
  arnold_pipelines/megaplan/cloud/incident_notification.py \
  arnold_pipelines/megaplan/cloud/human_review_diagnostic.py
all passed
```

The focused suite includes the two-process admission race and 200 identical
scans; it passed with one occurrence and one outbox row in one selected root.
Additional ephemeral SQLite probes reproduced the synthetic grant, two-root
split, forged transition, divergent provider digest, terminal overwrite,
post-ambiguity attempt, fabricated receipt, fixed-version divergence,
provenance-pending Discord destination, and outbox divergent-payload behavior.
The invalid-payload/invalid-gate probes reproduced direct API exceptions before
stable identity creation. No provider or external service was contacted.

## Integration/deployment/worker blockers

This review could not prove production behavior because the commit supplies no
canonical notification delivery worker consuming `notification:discord`, no
owner-store locator joining the incident DB to current Run Authority/Custody/WBC,
and no real provider fault/reconciliation harness. Clean-image packaging and
the actual deployed wrapper/module surface still require integration validation.
Those blockers do not soften the verdict: the local implementation itself
persists intents without current authority and permits invalid provider and
transition state.
