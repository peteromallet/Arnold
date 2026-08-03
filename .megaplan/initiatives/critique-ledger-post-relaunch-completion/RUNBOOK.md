# Incident-specific finite-canary and follow-up runbook

This runbook is the only launch route for this recovery. Generic deployment,
chain, supervision, tmux, watchdog, resident, or manual restart instructions do
not apply. In particular, do not use ordinary `cloud deploy`, `cloud chain`,
`cloud supervise`, a tmux launch, or a manual supervisor restart for this
incident. None of those routes reconciles the immutable one-dispatch intents.

## Live generation and resident

The accepted operational generation at this handoff is live:

- chain session `critique-ledger-accountability-v3-r5-20260803`;
- plan `cl2-wbc-backed-ledger-20260803-1357`;
- product `e5e9f2b1c1a7e7779121405fd4801768e1e8a4c2`;
- isolated runtime `82a5a012fa58f44cdc5e9e895f454d86d95b446d`;
- isolated image
  `sha256:2b6b18caeaf90ecdf6246f2c5eec5bcb9eccdb86435f66b0c3f98a5af0dce82d`;
- OAuth-backed all-Codex profile. Prep completed successfully at
  `2026-08-03T14:04:08Z` after 393,318 ms with artifact SHA-256 prefix
  `b8f292c2`, advancing state to `prepped`; tmux remains alive and the current
  worker is `gpt-5.6-sol` high in `plan`, with no current failure.

The Discord resident is independently healthy at recovery epoch
`discord-enospc-20260803-r7`: container
`a2c9a0d058af24ec38b05f2c8a1d2865c6120420faa4802d4cd9a740eaed9b1a`,
image
`sha256:78474208a513bfa03c51d6e04f3d31381ae07305b1c291db112098c05ba82c20`,
runtime `31d2e052104a57eb48e782dce8bdf678e6731caf`, receipt
`healthy/discord_ready`.

Normal operation is observation, not redeployment. Keep the exact live tuple
running while it advances. Do not stop it merely because a follow-up runtime
commit exists.

## Complete fresh restart/relaunch procedure

Use this only after the current generation is terminal or positively proven
dead. A timeout or lost client response is not proof: inventory tmux, process,
chain state and launch receipts first. If ownership or effect outcome is
ambiguous, reconcile and stop; do not redispatch.

1. Capture the current session's final chain state, log tail, process/tmux
   inventory, product/runtime/image revisions and any effect receipts. Fence a
   failed generation before creating a successor.
2. Create a new generation suffix. Use a new remote workspace, chain session,
   and all milestone branch names. Never reuse `v3-r5`, its plan, its workspace
   or any ambiguous branch. Remove or reject a seed when chain ownership is
   missing or ambiguous.
3. Commit and push the product spec/config and the runtime independently. Bind
   their full 40-character revisions and exact image digest. The launch
   admission must prove: provider credential available for every selected
   route; product/spec lineage fresh and coherent; clone/setup complete;
   writable working directory separate from read-only runtime/source; tracked
   symlinks cannot escape the admitted source; and no duplicate launch-owned
   environment selector can override the declared runtime.
4. Choose the profile from admitted credentials. If the direct DeepSeek key is
   absent, select the declared OAuth-backed all-Codex profile and record the
   change; never silently retain DeepSeek labels or claim DeepSeek execution.
5. From the exact runtime checkout, perform the supported fresh launch. Replace
   the variables below only with the newly committed product/runtime paths; do
   not add hidden environment selectors or credentials on argv:

   ```bash
   PYTHONPATH="$RUNTIME_CHECKOUT" \
     python -m arnold_pipelines.megaplan.cli cloud chain \
     --cloud-yaml "$PRODUCT_CHECKOUT/.megaplan/initiatives/critique-ledger/cloud.yaml" \
     --fresh --no-editable-install-sync \
     "$PRODUCT_CHECKOUT/.megaplan/initiatives/critique-ledger/chain.yaml"
   ```

6. Treat command return as launch acknowledgement only. After the setup
   completion contract settles, verify the exact tmux/process exists, the plan
   advances beyond initialization, and
   `editable_root == import_root == configured runtime root` plus
   `editable_revision == source_revision == configured runtime revision`.
   Verify the active worker/profile matches the admitted provider route and no
   terminal failure has appeared.
7. Observe again after the initial worker boundary. Only then record the new
   generation as durably moving. A failed admission gets one evidence-rich
   terminal result, not a retry loop or repeated user notification.

Resident recovery is a separate transaction. It must retain separate exact
source and resident image IDs, run the read-only pre-fence admission before any
restart-policy mutation, and emit stage-specific failure evidence. Never copy
the source environment into logs. Rotate all resident credentials before the
next resident recovery because a diagnostic command exposed the environment
file in a tool transcript; this document intentionally records no values.

## Hard NO-GO default

The follow-up chain remains closed while any prelaunch gate is pending, any
historical operation lacks an effective terminal reconciliation, B11-B25 remain
failed history, transaction `404dd858567d48ffbe8cb7c27d85185a` lacks imported
failure bytes, the terminal B27-B30 live receipts lack imported bytes, B35
attempt 9 has no run receipt, the A36/B36 publication gate remains a terminal
NO-GO, B38 attempt 12 still lacks imported exact receipt bytes, the exact B44
attempt-14 terminal failed/misclassified outcome is rewritten as success, the
exact A15/B15 attempt-15 infrastructure failure is rewritten as success, the
exact B16 attempt-16 infrastructure-recovery proof is missing or misclassified
as PROCEED/finalized/durable launch, the custody-v3-to-v4 migration task is not
completed, the fresh v3 post-launch runtime tuple does not bind one identical
configured pinned root/revision across editable and imported source, or F0 has
not admitted an exact completion plus stable-exit handoff.
Attempts 13-15 are immutable terminal history; attempt 16 is terminal
recovered-infrastructure, product-non-PROCEED history. A40 is closed. Remaining
product and broader systemic hardening belongs to F1/F2 and is not a relaunch
blocker; every future execution still requires fresh explicit authority.
There is intentionally no launch command in this runbook until an accepted installed
authority path and its exact invocation are committed and independently
reviewed. A generic command is not a fallback.

## Recovery authority split

With ordinary writable capacity, the supported typed provider persists intent
and receipts in the fixed root-owned, symlink-free authority directory before
mutation. At exactly zero writable bytes, authority originates off-host and an
already-installed immutable helper may stage only same-boot evidence under
`/run`; `/var/lib/arnold-zero-recovery` becomes the durable projection/seal
only after the admitted reclaim creates capacity. It is not the original
zero-byte authority.

Use only the supported receipt inventory/read/copy surface. Never substitute a
raw internal provider command. After client loss, response loss, or reboot:
inventory, copy, and reconcile. Never redispatch an operation merely because a
caller did not receive its result. A missing historical receipt becomes an
explicit `EVIDENCE_MISSING` or `UNKNOWN` reconciliation result, never a
backdated or reconstructed receipt.

## Ordered route

1. Inventory the host authority directory and copy every existing receipt and
   evidence directory byte-for-byte, recording mode, owner, inode, size and
   SHA-256. Preserve `active.json` only as a current projection, not proof of
   historical effects.
2. Join the copied bytes to the five immutable checked-in intents and provider
   WBC/outbox records. Produce and independently review the terminal operation
   reconciliation manifest. Do not rewrite an intent's historical status.
3. Fix the progress-auditor recursion at its source: the installed-source
   trampoline must check the snapshot guard before exec, and snapshot cleanup
   must remain in a non-overwritten `finally`/trap across every exit. Enforce
   singleton/attempt caps, disk budget/reserved headroom, a pre-model/tool
   capacity trip and a resident-only recovery surface. Preserve the completed
   reclaim receipt for predecessor container
   `277d2e6dbc149e01b25881350238a7b0ff5de78cc27d8ef52c144dca7c35c5ab`:
   1,156,578 copies and 387,889,659,906 logical bytes deleted, zero remaining,
   390,136,713,216 free bytes afterward, predecessor and workspace preserved.
   Then obtain fresh reserve, cache, container epoch, boot, unit-mask and
   notification-provider zero-call observations. Process absence alone is not
   notification evidence. Separately fix notification/watchdog durable
   incident-key dedupe so one terminal `manual_review` incident is not
   re-emitted; do not attribute its repeated Discord messages to the auditor.
   Preserve the diagnostic fixer's separate provenance-validation failure.
4. Preserve B26's independent Sol GO, B27-B30's offline and terminal
   failed-live evidence, and B31-B34's diagnostic/rejected schema-access
   history, plus B39 attempt 13's exact stopped/sealed terminal non-PROCEED
   evidence. Then copy and independently review B35's diagnostic and production
   acceptance smokes and attempt 9's poll-induced stop. B8-B10 build failures
   and B10-B25 smoke failures remain immutable evidence.
5. Import and reconcile transaction `404dd858567d48ffbe8cb7c27d85185a`'s
   durable failure receipt and import B27-B30's already-terminal run receipts.
   Only after B36 passes offline and independent gates: run status as a
   non-cancelling observation, bind fresh predeploy authority, run a new
   supported live transaction, apply
   and verify the fence. Preserve the exact A15/B15 source/tree/image and its
   terminal attempt-15 receipt before completing the explicit custody-v3-to-v4
   producer/validator migration. Neither prior failure grants reusable launch
   authority; any later canary needs a fresh explicit successor identity.
6. Push the exact follow-up authority and evidence, create the required custody
   refs/tags, and independently reconstruct and validate it from a fresh clone.
7. Preserve attempt 14 as terminal failed/misclassified, stopped and sealed:
   exact receipt digest/file SHA, `init→plan→critique→gate→revise`, ITERATE gate
   SHA, predispatch `NSA-7` human halt, old ordinal 4, and no finalize. Classify
   attempt 15 as terminal infrastructure failure after `init→plan→critique`,
   with its exact receipt, returned Sol plan, returned critique output followed
   by code-host SIGTRAP/closed stdout, failed/failed/partial runner state, null
   product outcome, stopped container, sealed workspace and below-floor capacity.
8. Preserve attempt 16 as `available` v3 receipt status `passed`, infrastructure
   recovery proof passed and terminal product `ITERATE` after the bounded second
   gate: all seven phases rc0, complete dispatch integrity, null failure, exact
   receipt/file/state/final-gate hashes, reconciled stopped container and sealed
   workspace. Do not call it an infrastructure failure, PROCEED, finalized or a
   durable epic launch. Carry its product hardening into F2 and the broader
   systemic hardening into F1 without making either a relaunch blocker. Any new
   execution requires fresh explicit authority. F0 may run only after its exact
   completion and stable-exit preconditions are independently satisfied.
   F0 may write only its admission manifest and completes no deferred F1-F8
   obligation. F1 may begin
   only after F0 is accepted.
9. Preserve the contained v3 relaunch precursor exactly. The abbreviated
   initiative revision `0bb0c0b74e` was rejected before init and is resolved by
   the full pin `0bb0c0b74e6b1913d39b51f33559b2f5127f1886`. Its fresh retry
   returned zero, was alive and advanced, and initialized
   `cl2-wbc-backed-ledger-20260803-1313`, but stability evidence rejected it:
   editable root/revision were pinned to the `a8e7ef6c345bbc1aceb19af67e7e25b1e05ad4e4`
   runtime while import root/source revision were the old
   `c7bcb06af536acfe759c1b31a785afc19afe92d4` runtime. The same isolated
   collector was redeployed to stop the untrusted run. Do not resume or reuse
   that initialized plan. Fix the cloud hot-environment ordering, launch a fresh
   retry, and accept it only when a post-launch stability read proves
   `editable_root == import_root == configured pinned root` and
   `editable_revision == source_revision == configured pinned revision` in
   addition to exit zero, alive and advanced.

If any step cannot be proved exactly, stop at NO-GO while preserving the
predecessor and all evidence. Do not improvise another execution route.

The 11:42 Europe/Berlin `/whats-cooking` outage is separate product-availability
evidence: Discord resident offline, production container exited on ENOSPC,
restart attempts failed before Discord connect, and no resident event existed.
The handler defers before collecting status, so acknowledgement ordering is not
the cause. Attempt 14 started 27 minutes later without a Discord token or
resident; do not attribute the outage to the canary. Preserve the incident for
F1 resident supervision, capacity-safe recovery, synthetic interaction
monitoring, and one deduplicated alert per outage epoch.
