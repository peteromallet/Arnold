FAIL

# T1.10 notification UX adversarial review — pass 3

## Verdict

**FAIL — critical authority/custody and effect-uniqueness blockers remain.**

Reviewed exactly commit `109d2a38bf6da210f650d5bf480967a19d9a09a8` in
`/private/tmp/arnold-critique-recovery-notification-ux-20260802`.

`git rev-parse HEAD` matched the required commit and `git status --porcelain=v1`
was empty before review. I read the complete prior FAIL reports:

- `/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.10/notification-ux-review-pass1-result.md`
- `/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.10/notification-ux-review-pass2-result.md`

No provider, Discord, cloud, SSH, network, or deployment effect was contacted.

## Critical blockers

### P0 — the owner boundary is forgeable, replaceable, and root-splitting

Code fact: `incident_notification.py:88-129` uses a mutable module-global
`_OWNER_AUTHORITY_PROVIDER`; `install_owner_notification_authority_provider()`
can be called repeatedly, and the resolver accepts any `NotificationAuthority`
whose `_seal` is the module object `_OWNER_AUTHORITY_SEAL`. The private Python
object is not an installation or owner boundary. `IncidentNotificationStore`
only checks caller root equality with that caller-supplied authority at
`incident_notification.py:408-427`.

Probe: imported the module’s private seal, converted the valid test authority
to an owner-sealed authority with `dataclasses.replace`, installed it, and
opened a normal `IncidentNotificationStore`. Result:

```text
forged_production_store_accepted True forged-owner-a
```

The same process then reinstalled the resolver with a second caller-selected
owner-sealed authority rooted at another directory. Both stores initialized:

```text
provider_reinstalled_rotated forged-owner-b .../b/.incident-notifications.sqlite3 True
two_db_roots True True
```

This independently reproduces blockers 1 and 2. A true owner-resolved,
one-time installation boundary and one canonical WBC/Custody root are absent.

### P0 — one durable provider attempt does not mean one provider effect

`record_provider_attempt()` fences durable slot numbers at
`incident_notification.py:1032-1107`, but a duplicate same-digest caller gets
the existing attempt ID at `:1063-1067` and then every
`CanonicalNotificationDeliveryWorker.run_once()` caller proceeds to the
provider at `:1395-1400`. There is no exclusive in-flight claim, worker token,
lease, or CAS transition from claimed to executing.

Probe: two threads, separate SQLite connections, same intent/attempt/digest,
and a barrier inside the provider. Both workers returned `SUCCEEDED`; the
provider callback was entered twice:

```text
worker_outcome SUCCEEDED
worker_outcome SUCCEEDED
provider_invocations 2 durable_attempt_rows SUCCEEDED
```

The existing race test proves one durable row, not one provider-accepted
effect. This fails the single-active CAS-fenced claim and the two-observer /
200-scan at-most-one-provider-accepted invariant.

### P0 — recipient routing is both nonfunctional for real provenance and
dispatchable for unvalidated provenance

`_stable_recipient()` at `incident_notification.py:327-387` accepts a raw marker
shape and only looks for `discord_user_id`/`user_id`. The canonical resident
normalizer emits `dm_user_id` or `channel_id`, not those fields
(`arnold_pipelines/megaplan/resident/provenance.py:154-223`).

Probe with a valid normalized Discord DM provenance produced:

```text
route notification:custody custody:provenance-pending:sha256:...
```

Thus real provenance cannot reach the Discord route. Conversely, a deliberately
malformed marker that the resident normalizer rejected as
`unsupported Discord conversation_key` was accepted by direct admission and
produced:

```text
admission_route ('notification:discord', 'discord:user:999999999')
```

Diagnostic admission occurs before `_resolve_provenance()`
(`human_review_diagnostic.py:460-525`, then validation at `:651-667`). A crash
between those points leaves a dispatchable intent created from unvalidated
caller data. This fails real provenance, recipient routing, and the
non-dispatchable pre-validation boundary.

### P0 — the worker can record fabricated provider success

`CanonicalNotificationDeliveryWorker` accepts an injected callable at
`incident_notification.py:1369-1375`. It overlays identity fields onto the
callable’s mapping at `:1422-1433`, and treats the self-asserted fields
`provider`, `message_ids`, `evidence_type=provider_api_receipt`, and
`provider_verified=True` as sufficient at `:1434-1459`.

Probe: a provider callable returned only caller-invented evidence with
`provider='caller-fabricated'` and `message_ids=['invented-by-caller']`. The
worker returned and durably stored `SUCCEEDED` with that invented message ID.
There is no provider signature, provider-bound nonce verification, or real
provider adapter in this candidate. A typed shape is not provider-verifiable
authenticity.

### P0 — canonical-row recovery is not deterministic across versions

The reducer at `incident_notification.py:803-892` selects an arbitrary
`notification_intents` row (`WHERE occurrence_id = ?`, no `ORDER BY` at `:805-809`)
and the first matching started event (`:812-821`). It does not reduce the
latest state-version history.

Probe: admitted v1 `manual_review`, admitted v2 `launched`, deleted the
`incident_occurrences` row, and called `rebuild_incident_card()`. Recovery
failed with:

```text
NotificationAuthorityError: authority target tuple does not match incident occurrence
```

The reducer selected the old v1 history while the current authority targeted
v2. This is a direct failure of deterministic rebuild after canonical-row
deletion, beyond the card-only recovery that passes.

## High-severity remaining defects

- **Lineage split remains possible.** Admission event lineage uses the current
  `session`/`owner` at `incident_notification.py:574-579`, while the occurrence
  upsert deliberately preserves the old lineage at `:667-670`. A v1 admission
  with `(session-one, owner-one)` followed by v2 with `(session-two, owner-two)`
  produced canonical lineage `session-one/owner-one` but event lineages for
  both sessions. The implementation must reject or canonically bind tuple
  changes.

- **Reconciliation is durable but not signed or owner-authenticated.**
  `authority_transition()` accepts only the string enum
  `provider_outcome` at `:1319-1333`; `reconcile_indeterminate()` verifies a
  transition row and that enum at `:1238-1267`. No signature, signed evidence,
  provider query proof, or immutable owner attestation is checked. A local
  probe omitted any `signed` field, supplied
  `{'provider_outcome':'confirmed_delivered'}`, and obtained:

  ```text
  unsigned_reconcile_transition_accepted reconcile_provider has_signed_field False
  reconcile_result ... dispatch_eligible True
  ```

- **Persistence is allowlisted but still retains secret-derived identity.**
  `_safe_persisted_payload()` at `incident_notification.py:344-354` hashes
  `redact_text(summary)` without secret-name context. For
  `UNIQUE_SECRET_9a7c`, the raw string was absent, but the durable intent and
  outbox retained `summary_digest`, `payload_digest`, and an intent ID derived
  from that digest. A digest of unredacted caller content is not a safe
  secret boundary or an acceptable secret-derived idempotency material.

- **An alternate writer remains executable.** The active progress-auditor
  call was removed (`wrappers/arnold-progress-auditor:6593-6612`), but the
  public `EscalationLedgerWriter` remains enableable and writes an append-only
  incident sidecar at `cloud/human_blockers.py:644-711` and lifecycle methods at
  `:713-770`. It is not retired or quarantined from production. The general
  resident completion DM path also remains in
  `arnold_pipelines/megaplan/agentbox_adapter.py:898-948`; the diagnostic’s
  suppression contract does prevent that path for this internal diagnostic,
  but it is not a canonical notification worker.

- **There is no installed production delivery worker/provider.**
  `cloud/notification_worker.py:11-25` checks environment labels and then
  always raises `DeliveryWorkerUnavailable`; the materialized wrapper merely
  invokes it (`wrappers/arnold-notification-delivery:4-14`). Running with both
  authority and provider environment labels still returned exit 1:

  ```text
  DeliveryWorkerUnavailable: no provider adapter implementation is installed in this candidate
  ```

  Therefore local injected-callable tests cannot establish production custody,
  provider crash/response-loss reconciliation, or the actual installed
  provider.

## Explicit pass-2 allegation disposition

Refuted or materially fixed in this candidate:

1. The old synthetic admission grant is gone; admission and terminalization
   now call `NotificationAuthority.validate()` (`incident_notification.py:511-513`
   and `:743-752`). The boundary itself remains forgeable as described above.
2. The old resident completion notification identity is suppressed and bound to
   the canonical intent (`human_review_diagnostic.py:676-696`); the split
   resident identity allegation is refuted for this diagnostic path.
3. Missing provenance uses custody-only routing and terminalization tombstones
   the intent/outbox (`incident_notification.py:606-623`, `:789-798`). The raw
   malformed-marker bypass and real-normalized-provenance misroute remain.
4. Same-slot divergent claims, unknown intents, immutable terminal receipts,
   sticky `INDETERMINATE`, and pending-attempt rejection are implemented at
   `:1058-1082` and `:1177-1195`. They do not provide an exclusive effect claim.
5. A resolve replay preserves `resolved=true` and exact version 2; resolve then
   acknowledge raises `IllegalIncidentTransition`. The focused probe printed
   `resolved_replay ... resolved:true` and `resolve_to_ack IllegalIncidentTransition`.
6. Ordinary meaningful state advancement creates v2; the multi-lineage and
   multi-version recovery defects remain.
7. Outbox payload conflict and commit ambiguity are refuted for the exercised
   SQLite path: the focused ledger suites passed `43 tests`.
8. `record_fallback_delivery()` is retired at
   `human_review_diagnostic.py:737-742`; fabricated success remains at the
   canonical worker seam.
9. The repair-loop direct Discord function and progress-auditor lifecycle write
   are no longer active in the inspected wrappers; `REPORT_WEBHOOK` was absent.
   The separately executable `EscalationLedgerWriter` remains a bypass surface.
10. Malformed payloads, malformed escalation IDs, and invalid stable-gate state
    now receive stable hash identities and state paths through
    `human_review_diagnostic.py:408-452`; direct probe results had
    `invalid_payload`, stable `esc-*`, and an existing `state.json`.
11. The diagnostic wrapper is included in the materialization allowlist, and
    source-to-materialized hashes matched for notification, diagnostic, and
    progress-auditor wrappers. Wheel parity was not independently proven in
    this environment because `pip wheel . --no-deps --no-build-isolation`
    stopped before build with missing `hatchling.build`.

## Verification and evidence classification

Test-proven facts:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -o cache_dir=<temporary> \
  tests/cloud/test_incident_notification_ux_pass2.py \
  tests/cloud/test_incident_notification_ux.py \
  tests/cloud/test_human_review_diagnostic.py -q
29 passed in 3.16s

PYTHONDONTWRITEBYTECODE=1 python -m pytest -o cache_dir=<temporary> \
  tests/arnold/workflow/test_ledger_outbox.py \
  tests/arnold/workflow/test_ledger_outbox_pass2.py -q
43 passed in 0.31s
```

The passing suites establish narrow local invariants only. The independent
authority-forgery, provider-double-invocation, routing, lineage, reconciliation,
secret-digest, malformed-routing, and deleted-latest-row probes above establish
the remaining local failures.

Unresolved production/deployment facts:

- The owner runtime never installs a real authority resolver in this checkout;
  `rg` found only the definition/export of the installer.
- No provider adapter, outbox polling/scheduling loop, provider receipt
  verification protocol, or real provider crash/response-loss harness is
  shipped. The candidate intentionally fails closed at that boundary.
- Wheel parity cannot be confirmed here because the build backend is absent;
  no network install was attempted.

## Acceptance checklist — required to change FAIL to PASS

- Replace the Python seal/global installer with a one-time, owner-controlled
  resolver that cannot be forged, rotated, or pointed at caller-selected roots;
  prove one canonical WBC/Custody store.
- Enforce one lineage and exact monotonic CAS across all versions and replay;
  reject tuple/authority drift.
- Add an exclusive provider claim/lease so concurrent workers can invoke a
  provider at most once per GLEK, and bind a cryptographically/provider-
  verifiable receipt before `SUCCEEDED`.
- Normalize and validate provenance before any dispatchable intent exists;
  route real DM/channel targets correctly and reject all pseudo/derived IDs.
- Implement a deterministic latest-version reducer from ledger/outbox/provider
  history, including canonical-row deletion/corruption.
- Make reconciliation a signed, durable owner transition and preserve the
  redaction boundary without secret-derived keys/digests.
- Retire/quarantine every alternate incident writer/provider/webhook path and
  ship, install, and exercise the real canonical worker across source, wheel,
  and materialized deployment artifacts with crash/ENOSPC/200-observer proof.
