# GPT-5.6 Luna implementation — RA-CONTAIN repair pass 13

Continue from exact clean commit `88393e2d0da80d76205ba03ddabf7577d864306b`
in `/private/tmp/arnold-critique-recovery-ra-contain-20260802`. Start only when a
mutation slot is free. Read the full pass-13 review and prior repair result.

Fix the three valid blockers:

1. Include the materialized backend's authoritative durable nonce map/binding in
   the exact replay proof. Missing, wrong, extra/forked nonce authority or a
   mismatch with SQLite request/identity/receipt must reject across restart.
2. Every file-backed backend read/proof/replay path must process-lock and reload
   required materialized files. A deleted/missing/replaced/corrupt anchor, key,
   receipt-authority identity or nonce state must raise typed corruption/
   unavailability; stale in-memory `_head`/`_used_nonces` cannot establish truth.
3. Successful `reconcile` and exact reconcile replay must return the same
   canonical complete operation receipt/bundle as issue/revoke, binding request,
   nonce, operation identity, journal, backend, decision, target, effect and
   content. Mutable result side rows cannot substitute for the caller receipt.

Adjudication of review finding 3: do not implement an impossible invariant that
no later overlapping transition may occur after the original operation's
linearization point. A legitimate peer CAS after durable proof can be ordered
after the successful issue even if it completes before the original caller
returns. Instead, document and test the exact linearization point, ensure the
returned receipt pins that committed revision, and ensure the later transition
has its own authorized request/journal/receipt. Raw direct backend CAS remains a
visibly test-only capability and cannot be production authority. If a peer
mutation is injected *before* the proof/linearization point it must reject or
indeterminate; if after, the original receipt remains valid historical proof and
current status may legitimately advance. Unauthorized path replacement/deletion
is covered by item 2 and must fail current reads without retroactively falsifying
an already committed receipt.

Add exact regressions for backend nonce delete/wrong/extra, stale instance after
anchor/key/identity deletion, reconcile first-run/replay complete receipts, and
before-versus-after-linearization peer ordering. Preserve all existing replay,
expiry, marker, final-CAS and process tests. Run containment, full Run Authority/
closure, static/diff checks; commit scoped changes, leave clean, and write exact
evidence to:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-repair-pass13-result.md`.

No cloud/owner/checklist mutation and no formal T0.0 completion claim.
