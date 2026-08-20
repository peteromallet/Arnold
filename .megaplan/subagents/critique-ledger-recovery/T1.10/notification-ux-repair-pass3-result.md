# T1.10 notification UX repair — pass 3 implementation report

## Outcome

Implemented and committed the safely achievable T1.10 pass-3 repairs in the
authorized checkout.

- Starting commit: `109d2a38bf6da210f650d5bf480967a19d9a09a8`
- Final commit: `0c3d662024bc0497ed3979991a20b3b48ecf19cd`
- Commit message: `T1.10 harden notification authority and delivery UX`
- Checkout: `/private/tmp/arnold-critique-recovery-notification-ux-20260802`
- External notification/provider/cloud/Discord effects: none

## Changed files

- `arnold_pipelines/megaplan/cloud/incident_notification.py`
  - Removed the mutable production authority installer/seal path.
  - Added fixed-root Ed25519 owner-document verification, validity, monotonic
    sequence/replay/downgrade checks, store binding, and RA/Custody/WBC evidence
    binding. Test authorities remain available only through `for_test()`.
  - Added normalized provenance routing for Discord DM, channel, and thread
    targets; malformed provenance is custody-only and non-dispatchable.
  - Rejected lineage tuple drift and removed summary/raw-marker-derived durable
    notification identities.
  - Added deterministic latest-version reduction from event/outbox history,
    including reconstruction after notification-intent and provider-row
    deletion; provider attempts/claims/receipts are copied into append-only
    canonical notification events.
  - Added transactional CAS provider claims with lease owner/token/expiry,
    fencing, write-ahead `DISPATCHED`/sticky ambiguity, and no same-attempt
    lease reclaim.
  - Added typed production adapter/verifier boundaries and signed receipt
    verification; arbitrary callables/mappings cannot produce production
    success.
  - Added signed owner-transition enforcement in production and monotonic
    reconciliation behavior.
- `arnold_pipelines/megaplan/cloud/production_authority.py`
  - Fixed production RA/Custody/WBC adapter boundary; absent deployment
    adapters fail closed.
- `arnold_pipelines/megaplan/cloud/production_provider.py`
  - Installed Discord API adapter using the fixed custody credential/signing-key
    paths and provider-signed receipts.
- `arnold_pipelines/megaplan/cloud/notification_worker.py`
  - Added canonical fixed-root outbox scan, signed authority resolution, typed
    provider/verifier loading, claim, delivery, and outcome recording.
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-notification-delivery`
  - Removed environment-label authority and caller-selected `PYTHONPATH`; uses
    installed-package `python3 -P` execution.
- `arnold_pipelines/megaplan/cloud/human_review_diagnostic.py`
  - Removed arbitrary summary/raw-payload hashing from stable escalation IDs.
- `arnold_pipelines/megaplan/resident/runtime.py`
  - Removed active `EscalationLedgerWriter` adoption from the resident resume
    path.
- `tests/cloud/test_incident_notification_ux_pass2.py`
  - Updated two worker fixtures to canonical normalized Discord DM provenance.
- `tests/cloud/test_incident_notification_ux_pass3.py`
  - Added adversarial routing, authority-forgery, lineage/redaction, claim-CAS,
    signed-receipt, write-ahead, and deleted-row reconstruction coverage.

## Verification

Focused notification/diagnostic suites:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -o cache_dir=/tmp/t110-pytest \
  tests/cloud/test_incident_notification_ux_pass3.py \
  tests/cloud/test_incident_notification_ux_pass2.py \
  tests/cloud/test_incident_notification_ux.py \
  tests/cloud/test_human_review_diagnostic.py -q
36 passed
```

The focused pass-3 suite alone: `7 passed`.

Dependency-closure notification/ledger suites:

```text
tests/cloud/test_incident_notification_ux_pass3.py
tests/cloud/test_incident_notification_ux_pass2.py
tests/cloud/test_incident_notification_ux.py
tests/cloud/test_human_review_diagnostic.py
tests/arnold/workflow/test_ledger_outbox.py
tests/arnold/workflow/test_ledger_outbox_pass2.py
79 passed
```

The broader run including `tests/cloud/test_human_blockers.py` had one
pre-existing/unrelated failure in
`test_ledger_write_incident_when_enabled`: the existing writer returned
`source=legacy-jsonl-evidence` while that test expected `source=operator`.

Static and syntax checks:

```text
ruff check <all changed Python files and T1.10 tests>
All checks passed
python -m compileall -q arnold_pipelines/megaplan/cloud arnold_pipelines/megaplan/resident/runtime.py
passed
git diff --check
passed
```

Wheel/install proof:

- Built with `python -m pip wheel . --no-deps --no-build-isolation`.
- Wheel: `/tmp/t110-wheel-final.CooZ9W/arnold-0.23.0-py3-none-any.whl`
- Wheel SHA-256: `1c62de85a940958adcf209664fa2e7304d7bd3c6852e235b7cc6b5745ee5375c`
- Installed into isolated venv `/tmp/t110-venv-final.DBESag` with `--no-deps`.
- From outside the checkout, the installed package imported
  `incident_notification`, `notification_worker`, `production_authority`, and
  `production_provider` from the venv site-packages directory, and exposed the
  new authority/provider/worker symbols.
- Materialized wrapper hashes matched source for notification delivery,
  human-review diagnostic, and progress-auditor wrappers. Notification wrapper
  hash: `a9b31455c3171b5124ee16155b550344ba671085bde1b8db9d110a0b563054c3`.

## Adversarial guarantees now covered locally

- Module-global authority installation and in-process seal replacement are no
  longer production authority mechanisms.
- Caller-selected roots, unsigned/invalid owner documents, expired documents,
  replay/downgrade sequences, and store-binding mismatches fail closed.
- Two concurrent claimants produce one durable active claim and one possible
  provider entrant; the winner writes sticky ambiguity before provider entry.
- Provider success requires the typed verifier path and a signed receipt bound to
  adapter identity, request, intent, attempt, GLEK, fence, nonce, lease token,
  and message IDs.
- Canonical Discord DM/channel/thread routes are accepted only from normalized
  resident provenance; pseudo, malformed, and unsupported markers route to
  custody-only state.
- Latest state versions and provider history rebuild deterministically after
  canonical-row deletion; lineage changes are rejected.
- Summary, raw marker, and raw invalid-payload contents are excluded from
  durable identity hashing.
- Provider exceptions, response loss, and receipt persistence ambiguity remain
  sticky `DISPATCHED`/`POSSIBLY_APPLIED` state rather than pending retry.
- The active resident resume path no longer adopts the alternate escalation
  ledger writer; the delivery wrapper no longer trusts environment labels or a
  caller-selected source root.

## Remaining external production/deployment prerequisites

These cannot be honestly proven or provisioned in this isolated checkout:

1. The real owner deployment must provision the private key corresponding to
   the compiled owner trust anchor, a root-owned signed authority document at
   `/var/lib/arnold/custody/notification-owner-authority.json`, and its durable
   monotonic sequence state.
2. The real owner deployment must install the fixed-boundary RA/Custody/WBC
   adapter implementation. The source `production_authority.load_adapters()`
   intentionally fails closed until those owner-backed adapters exist.
3. The deployment must provision the Discord bot token and provider receipt
   signing key at the fixed custody paths, plus service/supervisor scheduling
   for the installed worker.
4. A provider/gateway must honor the durable request identity/GLEK and support
   authoritative reconciliation. Local SQLite fencing cannot prevent a paused
   process from being accepted twice by a remote provider that lacks an
   idempotency/lookup boundary.
5. Resident provenance origin authentication, production crash/ENOSPC/response
   loss exercises, live provider receipt verification, and cloud deployment
   parity require the external owner/provider environment and were not run.
6. `EscalationLedgerWriter` remains as a legacy compatibility class for the
   existing non-T1.10 test surface, but its active resident production adoption
   was removed. Full removal from packaging requires a separate compatibility
   migration and is not claimed here.

The installed production path therefore remains deliberately fail-closed until
items 1–3 are provisioned and verified by the owner deployment.
