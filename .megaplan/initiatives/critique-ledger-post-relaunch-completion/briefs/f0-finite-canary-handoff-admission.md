# F0 — finite-canary handoff admission

Admit the post-relaunch epic only after independently verifying the exact
finite-canary and stable-exit handoff. This milestone is a deterministic,
read-only evidence boundary. It must not deploy, dispatch, retry, restart,
resume, supervise, notify, or otherwise mutate cloud or product state.

Verify all of the following from committed evidence bytes:

- every T6.2 prelaunch gate is accepted and its declared SHA-256 recomputes;
- the accepted build, smoke, predeploy, fence, canary, stop, stable-exit and
  fresh-clone receipts bind one exact commit/tree/image lineage;
- all B8-B10 failed builds and B10-B25 failed smokes remain preserved as
  rejected history; B26's independent Sol GO remains preserved; and B27's
  offline pass plus terminal failed-live receipt remain preserved, as do B28's
  and B29's corresponding offline and terminal failed-live receipts;
- failed live transaction `404dd858567d48ffbe8cb7c27d85185a` is imported and
  reconciled as no-marker/no-canary evidence before any fresh live retry;
- B30's passing offline receipt is independently accepted before it becomes the
  launch candidate, and its fresh workspace/container cannot reuse B27/B28/B29
  state;
- every immutable operation intent has one independently reviewed effective
  terminal outcome in `operation-reconciliation-manifest.json`, with no effect
  dispatched more than its declared maximum and no ambiguous operation left
  redispatchable;
- fresh capacity/reserve/cache, predecessor epoch, boot, persistent-mask and
  provider notification-zero-call evidence joins the same recovery interval;
- the exact fifteen deferred obligations remain unchanged as
  `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`; and
- a fresh clone recomputes the same evidence hashes and validates this chain.

Write only
`evidence/critique-ledger-recovery/T6.2/handoff-admission/completion-manifest.json`.
The manifest must bind every admitted input hash, record the validator command
and result, and state explicitly that F0 discharges **zero** F1-F8 obligations.
Any missing, ambiguous, inconsistent, untracked, dirty, or unhashed input is a
hard NO-GO. Do not create replacement historical receipts or infer success from
`active.json`, a prepared command, process absence, or supersession alone.
