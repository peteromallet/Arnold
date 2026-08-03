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
  through B30's corresponding offline and terminal failed-live receipts;
- failed live transaction `404dd858567d48ffbe8cb7c27d85185a` is imported and
  reconciled as no-marker/no-canary evidence before any fresh live retry;
- A31-B34's schema-access diagnostic/rejected history remains preserved, and
  B35's passing diagnostic/production-smoke evidence plus attempt 9's terminal
  status-poll collision remain preserved;
- B39 attempt 13 is preserved as a terminal, safely stopped non-PROCEED result:
  plan, critique and gate returned, the gate recommended `ITERATE`, state
  remained `critiqued`, eight blocking changes were recorded, and finalize did
  not run; neither the runner's current `unexpected_or_active_state` diagnostic
  nor process absence may be promoted into success;
- B39 remains immutable terminal, safely stopped, not-accepted non-PROCEED
  history. A40 is closed and authorizes only the exact direct-PROCEED route or
  one ITERATE→revise→PROCEED route; it does not retroactively promote B39;
- attempt 14 binds implementation `a15e87adea1fa78e90008422f42bc79ae60dff13`
  / tree `63a75d9333e3fa69c9a039846595d3dd4d3cc4b3`, B44 manifest
  `006895e8d66812dec5e85d26b32635af21ca21c7` / tree
  `8d70cc79bc8f5a79a60be282bcc22122109c7f83`, and production image
  `sha256:209a64de1f321b5ec49e8d6e6748187f790099a6fe8a68696352a5488bc7ffa6`;
- attempt 14 is immutable terminal failed/misclassified history: receipt digest
  `59f0d1712bbd6f379d921f9662989a7a524b62e8509182041e08ba368e0abe0d`,
  file SHA `23f260ba72c0785401d4749132491beeac1bd2cf7c61cc386c7b29e980ecb3c0`,
  phases `init→plan→critique→gate→revise`, ITERATE gate SHA
  `415fb3ffac618a196d2822f288d69d9457abd6f121615c1153e34fb7404e6545`,
  predispatch `NSA-7` human halt, no finalize, stopped container and sealed
  workspace; its generic-failure/partial-dispatch/ordinal-4 record is preserved
  as the defect, never promoted into F0 authority;
- attempt 15 binds A15 implementation
  `8932873ba1c81d398cf42fb9879605d14d50cbb4` / tree
  `7fdcf11dba38354645290314443c1de3c8b33bbb`, B15 manifest
  `4f021cb70f3202dd90d599f8d710b626ba27b16b` / tree
  `3777df403e9ae06cba75cf6fb6ac3b804f808723`, production image
  `sha256:ea1e66940e7445649b083b8d7acc896080526011f9bfc4a9e21b475046e1814a`,
  exact attempt-15 workspace/container, and the four settled source-identity,
  typed fresh-invocation, product-revise-blocked, and ordinal-4 fixes;
- attempt 15 is terminal infrastructure failure, not accepted: receipt digest
  `59bc8d659ca8ec59baa9da9051fcd7320199e6ffea12a97d3b7018694b266331`,
  file SHA `10eb82a07ca0829b585c4316413b76851665ac9b90ef93e051f94626f91a182a`,
  phases `init→plan→critique`, returned Sol plan and critique output followed by
  repeated code-host SIGTRAP/closed stdout, critique return 1/state `planned`,
  no gate/revise/finalize, failed/failed/partial receipt, null product outcome,
  stopped container and sealed workspace;
- attempt 16 is exact terminal infrastructure-recovery proof: outer status
  `available`; v3 receipt `passed`; source B16
  `fb5a394878bc900b189213a3de5dcc40169d8b7b` / tree
  `a8f903a94e5029fa50c148df3289186dc4c39caf`; phases
  `init→plan→critique→gate→revise→critique→gate` all rc0; complete dispatch
  integrity; null failure; both gate attempts `ITERATE`; product outcome
  `product_gate_not_proceed` / `ITERATE` / gate attempt 2; exact receipt digest
  `3a9925dbfcc0c901905db0265b48c062f051b16bdbb31b9f873c5e086eac08c0`,
  file SHA `1b4e1d013f444b3f3f2c3af1bb4938002e730f727a0be39834a2ca235fa592ba`,
  state SHA `4ef979066dfb3c822625de21ec52e95c7d25a42f185ea01970865d4b4116e525`
  and final-gate SHA
  `b8d6dcf366b04bde245890e1cb224c191f202101cb53dbb3fa59ca721c05d546`;
  exact stopped container
  `0552d39f4589239cb0b8e10b68b12c8ebab3a0e2fde6284049e1e466f0896ba6`
  at exit 143, OOM false, restart zero; reconciled stop and sealed workspace.
  Classify it as infrastructure recovery PASSED, not infrastructure failure,
  product PROCEED, finalized result or durable epic launch;
- post-run capacity is 1,484,693,504 bytes, below the 1,611,661,312-byte hard
  floor. The preserved production predecessor writable snapshot/container is
  approximately 389.927 GB, with `/tmp` approximately 388.813 GB. Exactly
  1,156,578 progress-auditor recursion copies consumed 387,889,659,906 logical
  bytes. Installed-source trampoline-before-guard, snapshot-execs-source,
  active-path mismatch and an overwritten cleanup trap caused the recursion.
  Receipted reclaim deleted all copies, left zero, restored 390,136,713,216 free
  bytes and preserved predecessor/workspace. Separately, notification/watchdog
  re-emitted the terminal `manual_review` incident without durable incident-key
  dedupe; the auditor did not send those messages, and the diagnostic fixer
  separately failed provenance validation. Attempt 16 proves infrastructure
  recovery; remaining product and broader systemic hardening is deferred to
  F2/F1 and does not block relaunch. Future execution still needs fresh explicit
  authority;
- diagnostic r1-r5 failures, diagnostic r6 PASS, and the B44 production-smoke
  PASS retain their exact file hashes, receipt digests, derived images, and
  failure classifications from `custody-manifest.json`; no smoke is a live result;
- the explicit custody-v3-to-v4 migration is complete across the completion
  producer, finite-canary validator, distinct stable-exit validator, and
  fresh-clone reconstruction, with v3 rejected by regression tests;
- any fresh later execution—not attempts 14-16—has new explicit authority and an
  independently verified PASS branch. Direct PASS is exactly five phases,
  eight ledger events and one PROCEED; revised PASS is exactly eight phases,
  fourteen events and ITERATE→PROCEED. Both require finalized state, exact new
  identity, stopped successor, runtime absence, stable exit, pushed custody and
  fresh-clone reconstruction;
- the contained v3 relaunch precursor remains non-authoritative: abbreviated
  initiative revision `0bb0c0b74e` was rejected before init; full revision
  `0bb0c0b74e6b1913d39b51f33559b2f5127f1886` then returned zero, went alive,
  advanced and initialized `cl2-wbc-backed-ledger-20260803-1313`, but the
  stability read found editable root/revision at the pinned
  `a8e7ef6c345bbc1aceb19af67e7e25b1e05ad4e4` runtime and import root/source
  revision at stale `c7bcb06af536acfe759c1b31a785afc19afe92d4` runtime. The
  isolated collector was redeployed to stop it, and that plan has no reuse or
  resume authority. A later fresh relaunch may be admitted only when its
  post-launch observation proves editable root equals import root and the
  configured pinned runtime root, while editable revision equals source
  revision and the configured pinned runtime revision, in addition to exit
  zero, alive and advanced;
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
