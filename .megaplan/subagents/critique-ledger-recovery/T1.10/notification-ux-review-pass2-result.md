FAIL

# T1.10 notification/incident UX — independent review pass 2

Reviewed exactly commit `7031b40dcd6ece7a24bbb3fec47fb440dfd57cce` in
`/private/tmp/arnold-critique-recovery-notification-ux-20260802`. The source
worktree remained unmodified. No provider, Discord, SSH, cloud, or deployment
effect was contacted.

The change fixes several narrow pass-1 defects, but the candidate still fails
the required invariant: repeated observations are cheap and unlimited; an
external effect requires one durable, uniquely claimed, authority-bound intent.

## Prior FAIL report: explicit reproduction/refutation

1. **Synthetic/shadow authority — partially fixed, not closed.** Missing
   authority now fails before a ledger write at
   `arnold_pipelines/megaplan/cloud/incident_notification.py:336-345`, and a
   forged RA view was rejected by `NotificationAuthority.validate()` at
   `:112-152`. The old synthetic grant string is gone from admission. However,
   `build_test_only_notification_authority()` is public and constructs a fully
   accepted `NotificationAuthority` from caller-selected data at `:155-180`,
   while `IncidentNotificationStore` accepts any such object. There is no
   owner-resolved production factory/adapter. A test-only authority can enter
   the same production store and worker methods.

2. **Caller-selected parallel custody roots — reproduced.** The constructor
   only checks `requested_root == authority.store_root` at `:341-345`; it does
   not resolve the owner root. A local probe created authorities for roots `a`
   and `b` with `build_test_only_notification_authority`, then admitted the
   same occurrence into both: output was
   `parallel_roots False False True True True` (both `duplicate=False`, same
   deterministic intent ID, and both SQLite files existed). The two-root
   universe remains caller-selectable.

3. **Split diagnostic identity — second provider identity refuted, lineage
   split reproduced.** The diagnostic task is now explicitly non-delivery at
   `human_review_diagnostic.py:288`, and the resident manifest is suppressed
   and bound to the canonical intent at `:360-367` and `:659-670`; this fixes
   the prior resident-completion duplicate notification route. But the
   canonical admission event uses `identity.run_id=session` at
   `incident_notification.py:465-472`, while
   `record_diagnostic_terminal()` writes the same attempt with
   `identity.run_id=occurrence_id` at `:607-623`, and changes provenance from
   the admission owner to `diagnostic-launcher` at `:618`. The probe printed
   `terminal_lineage session occ watchdog diagnostic-launcher`. Occurrence,
   diagnostic terminal, and authority lineage are therefore not one stable
   identity chain.

4. **Unfenced provider attempts/results — partially fixed, blocker remains.**
   Same-slot duplicate/different-digest races, unknown intents, immutable
   terminal receipts, and sticky indeterminate behavior are now covered by
   `BEGIN IMMEDIATE` and checks at `:791-838` and `:841-911`; the focused race
   passed. But while attempt 1 is still `PENDING`, the code allows attempt 2
   because `:813-819` only requires the next integer and does not require the
   prior attempt to be terminal. The probe printed two durable claims:
   `parallel_claim_slots provider-...-1 provider-...-2 2`.
   `CanonicalNotificationDeliveryWorker.run_once()` also promotes any mapping
   returned by an injected provider to `SUCCEEDED` at `:1075-1100`; an empty
   message list and arbitrary provider request ID are accepted. A receipt
   cannot be fabricated by the caller of `record_provider_receipt()` without
   the schema fields, but the worker itself supplies the success transition
   without provider-bound evidence.

5. **Provenance-pending under a real Discord route — missing-provenance case
   fixed, pseudo-recipient case reproduced.** Missing provenance now selects
   `custody:provenance-pending:*` and `notification:custody` at
   `:292-315` and `:489-504`; terminalization tombstones both intent and
   outbox at `:641-650`. The 200-call diagnostic missing-provenance probe
   never called its provider. But `_has_provenance()` only checks three
   nonempty strings. With syntactically complete marker provenance and no
   actual recipient, `_stable_recipient()` generated
   `discord:source:source-pseudo`; `CanonicalNotificationDeliveryWorker` only
   rejects `custody:` recipients at `:1053-1062`, so the fake provider was
   called and returned `SUCCEEDED`. Probe output:
   `pseudo_delivery notification:discord discord:source:source-pseudo SUCCEEDED 1`.

6. **Forged ack/resolve and state regression — caller forgery fixed, state
   regression reproduced.** `authority_transition()` now checks actor/grant
   equality and current stored authority at `:961-1017`; forged values and
   resolve-to-acknowledge were rejected in the focused tests. However, it has
   no exact expected state-version/CAS argument, and `admit()` overwrites
   `authority_state_json` with both flags false at `:540` on a replay/upsert.
   A resolve followed by an identical replay printed
   `resolved_replay {"acknowledged":false,"resolved":false}`. Resolution is
   therefore not monotonic across ordinary observations.

7. **Hard-coded state version — fixed for ordinary transitions.**
   `admit()` derives the next version from durable rows at `:410-431`, and the
   focused meaningful-transition test passed with one new v2 intent. A replay
   under changed current authority evidence is not safely reconciled: the
   authority evidence is embedded in the event payload at `:450-464`, so the
   same `incident-state:...:v1` key is rejected as
   `DivergentDuplicateError` rather than treated as the same observation.
   The probe output was `authority_replay rejected:DivergentDuplicateError`.

8. **Unrebuildable projections — card-only case fixed, canonical-row rebuild
   remains incomplete.** Deleted/corrupt `incident-card.json` rebuilds from
   rows through `rebuild_incident_card()` at `:655-731`, and caller-supplied
   card JSON is rejected at `:771-775`; the focused test passed. But deleting
   the authoritative `incident_occurrences` row makes rebuild fail with
   `UnknownNotificationIntent: cannot rebuild an unknown occurrence` rather
   than reducing from the ledger/outbox/provider rows. Probe output:
   `rebuild_deleted_occurrence UnknownNotificationIntent ...`. There is no
   reducer that reconstructs the occurrence/intent projection from the durable
   ledger event and outbox row after canonical-row corruption/deletion.

9. **Outbox payload/commit ambiguity — refuted for the tested ledger path.**
   `OutboxPayloadConflictError`, deterministic outbox specs, and commit
   reconciliation are implemented at
   `arnold/workflow/ledger_outbox.py:376-455` and `:560-644`. Divergent payload
   and simulated “COMMIT committed then raised” tests both passed. This prior
   finding is not a remaining blocker in the exercised SQLite outbox path.

10. **Fabricated fallback success — fallback API retired, worker success
    fabrication remains.** `record_fallback_delivery()` now fails closed at
    `human_review_diagnostic.py:721-726`, so the old arbitrary fallback result
    path is refuted. But the canonical worker accepts an arbitrary injected
    provider mapping and records `SUCCEEDED` without binding
    `provider_request_id`, intent nonce, or real provider evidence
    (`incident_notification.py:1072-1100`). This is still a fabricated-success
    path at the only remaining delivery seam.

11. **Direct Discord/legacy JSONL paths — direct Discord wrapper retired, an
    active legacy incident ledger remains.** `arnold-discord-dm` is a fail-closed
    stub and the repair-loop provider function is unreachable behind an
    immediate fail-closed return at
    `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop:8399-8403`.
    However the production materialized `arnold-progress-auditor` still imports
    and enables `EscalationLedgerWriter` at
    `:6463-6473` and `:6580-6588`, then calls `writer.write_opened()` at
    `:6614-6627`. Its JSONL sidecar is labelled evidence-only by
    `repair_contract.py:3595-3613`, but it is still a second incident ledger
    and alternate lifecycle authority surface. The source/wheel scan found
    these exact active paths. `arnold-watchdog` also retains a configurable
    `REPORT_WEBHOOK` surface at `:112` and `:1724-1726`, currently deferred by
    a log message rather than integrated with the canonical outbox.

12. **Malformed input without stable identity/path — reproduced for malformed
    gate/escalation data.** Raw invalid JSON and non-object payloads now get a
    stable hash path through `:407-451`, and that pass2 test passed. But
    `_escalation_id()` is called outside the protected admission/failure block
    at `human_review_diagnostic.py:452-464`; an invalid
    `stable_human_gate.plan.current_state` still raises `ValueError` at
    `:227-233` before state creation. The direct API probe printed
    `malformed_gate ValueError ... False`, with no durable diagnostics directory
    or stable result. The CLI catch can synthesize a result, but does not make
    the same durable state path.

13. **Omitted diagnostic wrapper — refuted.** `template.py:385-396` now includes
    `arnold-human-review-diagnostic`; the materialization/help test passed. The
    wheel build also included the wrapper and the diagnostic/notification
    modules.

## Invariant attack

1. **Canonical owner-resolved root: FAIL.** Root equality is checked only
   against a caller-supplied authority. The public test factory lets callers
   select both authority and root, reproducing two independent stores.

2. **One identity/authority lineage: FAIL.** The terminal event changes
   `run_id`/actor, and authority rotation rejects an otherwise identical replay
   as divergent instead of preserving one lineage.

3. **Malformed/missing provenance stable path: FAIL.** Missing provenance with
   owner authority creates a durable custody intent, terminal event, tombstone,
   and stable card. Malformed gate input still raises before durable identity.

4. **Two watchdogs + 200 identical ticks: PASS only for the narrow observed
   admission.** The existing test passed: one occurrence and one outbox row,
   and the two-process provider same-slot race left one attempt row. Global
   provider uniqueness is not proven because the API permits a second claim
   while the first remains pending.

5. **Monotonic provider state: FAIL.** Same-slot fencing and sticky
   `INDETERMINATE` pass; active pending-slot fanout, weak reconciliation
   (`transition.get("signed") is True` at `:933-955`), and worker-accepted
   fabricated success violate the stronger invariant. `SUCCEEDED`/terminal
   rows are immutable once recorded, but claim/result authority is incomplete.

6. **Only canonical outbox worker for effects: FAIL as a production proof.**
   The class exists at `:1046-1101`, but no production wrapper or scheduler
   consumes canonical outbox rows with a real provider adapter. The materialized
   wrappers only contain the retired fail-closed stub plus unrelated legacy
   incident ledger paths.

7. **Missing provenance non-deliverable/pseudo-recipient safe: FAIL.** Missing
   provenance is custody-only; syntactically forged provenance can produce
   `discord:source:*` and reach the worker/provider.

8. **Real RA and exact-version ack/resolve: FAIL.** Current action-gate checks
   reject basic forged callers, but a public test-only authority is accepted by
   production methods, transitions have no exact expected version, and replay
   resets resolution.

9. **Projection rebuild from authoritative rows: FAIL.** Card projection
   rebuild works after card deletion/corruption; deleting the occurrence row
   cannot be reduced/rebuilt from the ledger/outbox.

10. **ENOSPC/crash ambiguity: PARTIAL, not proven.** The pass2 ENOSPC seam test
    confirmed no provider call before claim persistence, and the outbox COMMIT
    ambiguity simulation reconciled an already-committed event. There is no
    real provider crash/response-loss harness or production worker proving the
    post-invocation outcome protocol; the worker maps provider exceptions to
    `INDETERMINATE`, but persistence failure after invocation remains dependent
    on later reconciliation.

11. **Source/wheel/materialization parity: FAIL.** The source and wheel carry
    the same active `arnold-progress-auditor` legacy ledger and no real
    canonical delivery worker wrapper. The diagnostic wrapper is now packaged,
    but parity preserves the unresolved bypass surface.

12. **Secret exclusion: FAIL.** `admit()` copies unredacted `stable_payload`
    into the outbox and intent payload JSON at `:404-409` and `:489-504`.
    `record_provider_receipt()` stores the entire arbitrary receipt mapping at
    `:854-869` without redaction/allowlisting. Probes found
    `SECRET_PAYLOAD` in the durable outbox JSON and `SECRET_RECEIPT` in the
    durable provider receipt JSON. The incident card exposes recipient and
    payload digest at `:697-724`; its digest is derived from the unredacted
    payload and is not a safe secret-boundary substitute.

## Verification

All tests ran one process at a time with temporary roots:

```text
PYENV_VERSION=3.11.11 python -m pytest \
  tests/cloud/test_incident_notification_ux_pass2.py \
  tests/arnold/workflow/test_ledger_outbox_pass2.py -q
13 passed in 1.90s

PYENV_VERSION=3.11.11 python -m pytest \
  tests/cloud/test_incident_notification_ux.py \
  tests/cloud/test_incident_notification_ux_pass2.py \
  tests/cloud/test_human_review_diagnostic.py \
  tests/cloud/test_watchdog_wrappers.py \
  tests/arnold/workflow/test_ledger_outbox.py \
  tests/arnold/workflow/test_ledger_outbox_pass2.py -q
456 passed in 323.41s (0:05:23)
```

Additional local probes reproduced the root split, authority-rotation
divergence, split terminal identity, pseudo-recipient delivery, two active
provider claim slots, secret persistence, resolve replay regression, deleted
occurrence rebuild failure, and malformed-gate exception. The simulated
outbox commit-ambiguity probe reconciled a committed event. No external
provider was invoked.

Static verification passed:

```text
git diff --check 7031b40d^ 7031b40d
bash -n arnold-watchdog arnold-human-review-diagnostic arnold-repair-loop \
  arnold-discord-dm arnold-progress-auditor
python -m py_compile ledger_outbox.py incident_notification.py \
  human_review_diagnostic.py template.py resident/subagent.py
```

Packaging/materialization proof: `pip wheel . --no-deps --no-build-isolation`
built a wheel; a clean system-site-packages venv installed it and imported
`arnold_pipelines.megaplan.cloud.incident_notification` from site-packages,
with `CanonicalNotificationDeliveryWorker` exported and the Discord wrapper
packaged. SHA-256 hashes for source versus wheel matched for the two Python
modules and both relevant wrappers. The materialization/help test passed.

## Required corrections

- Replace caller-constructible `NotificationAuthority`/test factory use in
  production with an owner-resolved, sealed store locator; reject test-only
  authorities in production paths and bind one canonical WBC/Custody root.
- Use one stable run/attempt/authority lineage for admission and terminal
  events; store authority evidence separately from replay identity so current
  fence rereads do not turn identical observations into divergent event
  payloads.
- Make provider claims single-active and exact CAS-fenced; require prior
  attempts to be terminal, bind request nonce/GLEK/intent, and require
  provider-verifiable receipt evidence. Reconciliation must be a real signed,
  durable owner transition, not `signed == True`.
- Reject every pseudo/derived recipient (`discord:source:*`, caller-supplied
  recipient IDs) unless resolved from validated resident provenance and a real
  provider route; keep missing provenance tombstoned and non-dispatchable.
- Preserve acknowledgement/resolution in all state upserts and require exact
  state-version monotonic CAS transitions.
- Add a deterministic reducer that can reconstruct occurrence/intent/card
  projections from the authoritative ledger/outbox/provider records after
  canonical-row corruption/deletion.
- Remove or quarantine all active legacy incident ledger writers, including
  `arnold-progress-auditor`, and provide a real deployed canonical outbox
  worker/provider adapter; eliminate webhook/alternate recipient ambiguity.
- Route every validation failure through the same stable durable identity/path,
  including invalid gate tokens and malformed supplied escalation IDs.
- Redact/allowlist payload and receipt fields before persistence; never retain
  secrets or secret-derived idempotency material in cards, ledger/outbox rows,
  provider receipts, or keys.

This local candidate review does not prove formal T1.10 and does not authorize
cloud deployment or provider effects.
