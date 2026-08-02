# GPT-5.6 Luna independent review — T1.10 pass 4

Date: 2026-08-02

Verdict: **HARD FAIL**

## Exact subject

- Repository: `/private/tmp/arnold-critique-recovery-notification-ux-20260802`
- Commit: `0c3d662024bc0497ed3979991a20b3b48ecf19cd`
- Tree: `d4c10e167be87e1655704d1beeaf92d6c4e46526`
- `HEAD` matched the requested commit.
- `git status --porcelain=v1` was empty; `git diff --quiet <commit> --` returned 0.
- No code, commit, provider, cloud, or owner configuration was changed.

## Commands and results

1. Focused recovery/notification suite:

   ```text
   pytest -q tests/cloud/test_incident_notification_ux.py \
     tests/cloud/test_incident_notification_ux_pass2.py \
     tests/cloud/test_incident_notification_ux_pass3.py \
     tests/cloud/test_recovery_topology_surfaces.py \
     tests/cloud/test_supervisor_runtime_isolation.py \
     tests/agentbox/test_guardian_notifications.py \
     tests/agentbox/test_reset_notifications.py
   ```

   Result: **91 passed, 1 failed**. The failure was:

   `tests/cloud/test_incident_notification_ux_pass2.py::test_direct_provider_source_is_retired_and_diagnostic_wrapper_materializes`

   The materialized `arnold-human-review-diagnostic` wrapper exited 1 with:

   ```text
   Error while finding module specification for
   'arnold_pipelines.megaplan.cloud.human_review_diagnostic'
   (ModuleNotFoundError: No module named 'arnold_pipelines')
   ```

2. Recovery/observer/provenance/rebuild subset:

   ```text
   pytest -q tests/cloud/test_incident_notification_ux.py \
     tests/cloud/test_incident_notification_ux_pass3.py
   ```

   Result: **19 passed**. This independently confirms the passing portions:
   two processes and 200 observer scans collapse to one intent; intent crash
   replay is idempotent; missing/malformed provenance is custody-only; valid DM,
   channel, and thread provenance binds exact recipients; claim CAS has one
   durable winner; fabricated/untyped provider mappings do not become success;
   provider ambiguity is sticky; and deleted/corrupt projections can be rebuilt.

3. Direct writer reproduction:

   ```text
   pytest -q \
     tests/arnold_pipelines/megaplan/test_discord_dm.py::test_send_discord_dm_posts_dm_channel_then_messages \
     tests/arnold_pipelines/megaplan/test_agentbox_adapter.py::test_record_completion_dm_emits_event_and_sends_discord_dm
   ```

   Result: **2 passed**. These tests use a fake opener, so no network was used,
   but prove that the legacy `send_discord_dm()`/AgentBox completion path remains
   executable independently of the canonical incident-notification worker.

4. Materialized notification wrapper from a clean source checkout:

   ```text
   env -u PYTHONPATH -u MEGAPLAN_RUNTIME_SRC -u CLOUD_WATCHDOG_ARNOLD_SRC \
     bash arnold_pipelines/megaplan/cloud/wrappers/arnold-notification-delivery --help
   ```

   Result: exit 1, `ModuleNotFoundError: No module named 'arnold_pipelines'`.
   The wrapper is only `exec python3 -P -m ...`; it does not bind an installed
   wheel, a materialized source root, or a verified runtime root.

5. Production authority boundary:

   ```text
   python - <<'PY'
   from arnold_pipelines.megaplan.cloud.production_authority import load_adapters
   try: load_adapters({})
   except Exception as e: print(type(e).__name__ + ': ' + str(e))
   PY
   ```

   Result: `RuntimeError: owner-backed RA/Custody/WBC adapter deployment is not installed`.
   This is the implementation at `arnold_pipelines/megaplan/cloud/production_authority.py:24-32`,
   so the production path cannot admit or deliver any incident.

6. Recipient substitution probe using two valid DM markers for the same
   occurrence/state:

   ```text
   python <read-only probe using IncidentNotificationStore.for_test>
   ```

   Result: the second admission was rejected by the canonical outbox with
   `DivergentDuplicateError` for the stable `incident-state:<occurrence>:v1`
   idempotency key. No second intent was accepted. This closes the specific
   recipient-drift data-plane case, although the rejection is not normalized to
   the module's typed `NotificationConflict` API.

## Findings against the requested failure list

### Closed or substantially closed in the canonical test path

- In-process authority forgery and caller-selected split roots are rejected by
  the production constructor; the test seal is separated from production.
- The signed owner-document path pins the canonical root to
  `/var/lib/arnold/custody`, checks validity, sequence monotonicity, target tuple,
  and predecessor digest. Mutable authority installation is retired.
- Two canonical workers cannot both win one provider claim: `BEGIN IMMEDIATE`
  plus the conditional PENDING-to-DISPATCHED update provides one CAS winner.
- Valid `dm_user_id`, channel, and thread provenance route to exact
  `discord:user:<id>`, `discord:channel:<id>`, and `discord:thread:<id>` values.
  Normalization rejects malformed provenance; malformed data becomes custody-only.
- Raw provider mappings and unsigned/fabricated receipts do not become
  `SUCCEEDED`; success requires typed provider evidence and signed receipt
  verification bound to request ID, intent, attempt, digest, GLEK, fence, nonce,
  and lease token in production mode.
- Write-ahead claim state is sticky before provider invocation. Provider-applied/
  acknowledgement-lost cases remain non-eligible for blind resend; reconciliation
  is required.
- Projection/card rebuild is not driven by caller JSON and the focused tests
  cover deleted/corrupt cards, deleted occurrence rows, provider-history rebuild,
  and deterministic meaningful-transition dedupe.
- The focused tests cover two processes, 200 observers, claim races, intent
  replay, and persistence refusal before provider invocation.

### Confirmed hard failures or missing required gates

1. **Production owner authority is absent.**

   `production_authority.load_adapters()` always raises. The signed document is
   not enough to run the RA/Custody/WBC action gate, and no production owner
   configuration is present in this commit. This independently blocks T1.10.

2. **Production supervision is absent from the notification worker.**

   `arnold-notification-delivery` directly invokes the worker and has no
   supervisor/runtime-attestation/lease-supervision integration. The source
   explicitly says the deployment must replace the stub at build time; that
   replacement and its owner authority are not part of this exact tree.

3. **Reinstallable/split runtime remains possible.**

   The wrapper uses `python3 -P -m` without a fixed source root, wheel digest,
   import-origin receipt, or supervisor-bound runtime. `-P` removes the script
   directory but does not cryptographically bind the imported package. The
   authority/provider checks only module-name prefixes, not package content or
   artifact identity. A substituted installation can therefore replace the
   fixed boundary implementation while retaining the expected import names.

4. **Materialized-wrapper parity fails.**

   `materialize_deploy_dir()` emits the notification wrapper, but executing it
   from the materialized deployment directory fails to import the package. The
   focused pass-2 test is red. Installed-wheel parity was not demonstrated; the
   wrapper failure is already a concrete parity failure.

5. **Executable legacy/direct writers remain.**

   `arnold_pipelines/megaplan/discord_dm.py:63-217` still reads
   `DISCORD_BOT_TOKEN` and `DISCORD_DM_USER_ID` and calls Discord directly.
   `agentbox_adapter.py:934-946` still calls it. Worse, when a delivery-effects
   attempt raises, `discord_dm.py:176-181` falls through to the direct provider
   path. This permits duplicate provider effects and bypasses the canonical
   intent/claim/receipt protocol. It is a direct contradiction of the
   all-legacy/direct-writer and environment-flag bypass requirement.

6. **Key rotation is not implemented.**

   The owner and provider verification keys are single compiled Ed25519 public
   keys. Authority sequence rotation is chained, but `_verify_owner_document()`
   requires one fixed `key_id`; there is no trusted key set or signed key-rotation
   transition. Authority-document rotation is therefore not equivalent to key
   rotation.

7. **Reminder bucketing and child chunk GLEKs are absent from the canonical
   notification path.**

   `rg -n "reminder|chunk|glek"` finds only the one intent/claim GLEK plumbing;
   there is no reminder-bucket state or child-chunk identity. The production
   provider sends one truncated message (`production_provider.py:81-85`) and
   emits one message ID/one GLEK (`:89-105`). The direct legacy helper has
   chunking, but it is exactly the alternate writer that must not remain.

8. **T1.5/T1.6 integration is not frozen.**

   The exact commit contains no integrated/frozen T1.5/T1.6 production interfaces
   sufficient to validate the owner authority, RA/Custody/WBC evidence, or
   supervision contract. Per the review request, a local green subset cannot
   formally complete T1.10 under this condition.

## Crash/restart, stale fencing, replay, corruption, and rebuild assessment

The canonical implementation has the correct high-level write-ahead shape:
intent/outbox first, claim before provider call, sticky ambiguity, exact CAS,
receipt binding, and projection rebuild. Focused tests cover intent crash/replay,
claim race, provider ambiguity, receipt rejection, stale state projection, and
rebuild. However, there is no integrated production test proving crash/restart
at every boundary with real owner adapters, no production lease-renewal/
supervisor process, and no production key-rotation test. The unavailable owner
adapter means stale lease/fence/epoch behavior is only exercised through the
test authority, not the actual T1.5/T1.6 boundary.

## Limitations

- No Discord, cloud, SSH, provider, or owner service was contacted.
- No commit, source file, installed package, runtime configuration, or provider
  credential was changed. Pytest used isolated temporary test directories.
- A fresh wheel was not built in this read-only review. The materialized-wrapper
  failure and absence of a pinned runtime/import-origin contract are sufficient
  to fail the packaging/parity gate; no positive wheel parity claim is made.
- The canonical test suite does not cover every requested category, notably
  reminder bucketing, child-chunk GLEKs, production owner/supervisor integration,
  true key rotation, and all alternate writer call sites. Static inspection
  found those omissions and the direct-writer bypass above.

## Final verdict

**HARD FAIL** — pass-3 canonical data-plane protections are mostly present, but
the exact commit has a red focused test, no installed production owner authority
or supervision, a runtime/package binding gap, executable direct/env-driven
alternate writers, no key rotation, and no canonical reminder/chunk-GLEK model.
