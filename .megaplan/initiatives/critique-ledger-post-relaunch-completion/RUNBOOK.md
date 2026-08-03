# Incident-specific finite-canary and follow-up runbook

This runbook is the only launch route for this recovery. Generic deployment,
chain, supervision, tmux, watchdog, resident, or manual restart instructions do
not apply. In particular, do not use ordinary `cloud deploy`, `cloud chain`,
`cloud supervise`, a tmux launch, or a manual supervisor restart for this
incident. None of those routes reconciles the immutable one-dispatch intents.

## Hard NO-GO default

The follow-up chain remains closed while any prelaunch gate is pending, any
historical operation lacks an effective terminal reconciliation, B11-B25 remain
failed history, transaction `404dd858567d48ffbe8cb7c27d85185a` lacks imported
failure bytes, the terminal B27-B30 live receipts lack imported bytes, B35
attempt 9 has no run receipt, the A36/B36 publication gate remains a terminal
NO-GO, B38 attempt 12 still lacks imported exact receipt bytes, B39 offline,
independent, live and stable-exit gates remain pending, or F0 has not admitted the exact stable-exit
handoff. There is intentionally no launch command in this runbook until an accepted installed
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
3. Obtain fresh capacity, reserve, cache, container epoch, boot, unit-mask and
   notification-provider zero-call observations. Process absence alone is not
   notification evidence.
4. Preserve B26's independent Sol GO, B27-B30's offline and terminal
   failed-live evidence, and B31-B34's diagnostic/rejected schema-access
   history. Then copy and independently review B35's diagnostic and production
   acceptance smokes and attempt 9's poll-induced stop. B8-B10 build failures
   and B10-B25 smoke failures remain immutable evidence.
5. Import and reconcile transaction `404dd858567d48ffbe8cb7c27d85185a`'s
   durable failure receipt and import B27-B30's already-terminal run receipts.
   Only after B36 passes offline and independent gates: run status as a
   non-cancelling observation, bind fresh predeploy authority, run a new
   supported live transaction, apply
   and verify the fence, run the one finite canary, record conformance and
   completion, stop it, and prove stable exit. Neither prior failure grants
   reusable launch authority.
6. Push the exact follow-up authority and evidence, create the required custody
   refs/tags, and independently reconstruct and validate it from a fresh clone.
7. Run F0. F0 may write only its admission manifest and completes no deferred
   F1-F8 obligation. F1 may begin only after F0 is accepted.

If any step cannot be proved exactly, stop at NO-GO while preserving the
predecessor and all evidence. Do not improvise another execution route.
