# NBF execution contract — Batch 4 accepted / NBF06 complete / NBF08 suffix authorized — 2026-09-01

- State: `BATCH_4_ACCEPTED_NBF06`; NBF06 is accepted at the Batch 4
  implementation checkpoint with the Grok 4.6 `FINAL PASS` verdict.
- Accepted tasks: `NBF-01`, `NBF-02`, `NBF-03`, `NBF-04`, `NBF-05`, and `NBF-06`.
- Strict progress: `6/8 = 75%`; batches: `4/6 = 66.7%`; Batch 4 is complete;
  next is **Batch 5 / NBF-08**.
- NBF06 implementation gate evidence: acceptance `54/54` passed; exact A32
  batch/fanout/loop nodes `1/1` each passed; A38 checker
  `ALLOWLIST PASS; forbidden=0; negative_fixtures=PASS`; bounded
  production-door/ledger superset `163/163` passed; owned-module compile
  passed; scoped source/test staged `git diff --check` passed. The full staged
  diff reports only five imported Markdown hard-break whitespace findings in
  frozen planning/adjudication artifacts and exits nonzero; these bytes remain
  unchanged for custody.
- Planning packet vectors, hashes, seals, and other planning-only artifacts
  are contract/provenance evidence and do not count as implementation
  progress. The progress number above credits only the accepted NBF06 source,
  tests, checker/fixtures, and this checkpoint.
- Checkpoint receipt: `.oracle/rework/batch-4-nbf06-acceptance.md`.

- State: `BATCH_3_ACCEPTED_NBF04_NBF05`; NBF04 and NBF05 are accepted at the
  Batch 3 attempt-5 metadata checkpoint.
- Accepted tasks: `NBF-01`, `NBF-02`, `NBF-03`, `NBF-04`, and `NBF-05`.
- Strict progress: `5/8 = 62.5%`; batches: `3/6 = 50%`; Batch 3 is complete;
  next is **Batch 4 / NBF-06**.
- Final Batch 3 packet: `.oracle/rework/batch-3-attempt-5-combined-nbf04-nbf05.md`
  SHA-256 `8481da7b8575d98ba4019e1620cfc72b1a9b6b2f26e93e942ce0cdf473e4e792`;
  framed aggregate `7f134a29fee76c1f68436798482dca46a301a380456c0793ce3b2b0ecf80c958`.
- Final inventory: `docs/nbf-signal-inventory.json` SHA-256
  `e92b6c90c6adf7c6d5f05a8d10c888f4900b1a2395cf35ce55689323987568da`, 120
  entries, source digest `60d5d933e722d8f49905b534866e1a2bdb6d0c7766103f3176adacd7cd33a958`.
- The denominator changed from 7 tasks/5 batches to 8 tasks/6 batches through
  the authorized NBF08 future-suffix rebind. This is a transparent planning
  denominator change, not retroactive completion credit.
- Authorized suffix order: Batch 4 `NBF-06`, Batch 5 `NBF-08`, then Batch 6
  `NBF-07`.
- Five independent Luna reviews converged: ambiguous `PASS`; contract `PASS`;
  focused regression `PASS` (broader results unclassified); expanded review 4
  `PASS` (439 passes, documented baselines only); review 5 `PASS_BATCH_2`.
- Three final Luna review rounds PASSed after the single Sol REWORK ruling was
  remediated; no second Sol was commissioned. The one controlling Sol ruling
  remains binding: no managed second WBC authority. Batch 3/provider-policy/
  scheduler/journal/network and taxonomy redesigns remain out of scope.
- Gate4 is the custody-reconciled cumulative branch from `2297fb3…`; source
  bytes are preserved and this checkpoint contains the reviewed cumulative
  Batch 1 + Batch 2 state because the original Batch 1 checkpoint ancestry was
  not imported.

# Historical Batch-2 provider-credit block — preserved record — 2026-08-30

- State at the time: `BLOCKED_GROK_BUILD_BALANCE` at the Batch-2 Oracle gate.
- Current HEAD: `5f172e3588e740bacd6692ca9e4cc50ae01f6a6b`; candidate implementation
  parent remains `5da26ec5be4d13559948fe4256a114ad7626482b` (**not** validly
  Batch-2 passed).
- Oracle policy remains Grok 4.6. The authorized direct native command was
  `/Users/peteromalley/.grok/bin/grok` version `grok 1.0.5 (5115b46bc909)`,
  requesting `grok-4.6` with `--reasoning-effort high`.
- Direct v3 brief: `.oracle/briefs/oracle-nbf02-nbf03-grok-v3.md` — SHA-256
  `0f5dd6b85165c2be927f1e0843207db791db2721c80af560fc618ff8015163f3`.
- Direct subscription failure receipt: `.oracle/receipts/oracle-nbf02-nbf03-grok-v3-subscription-launch-failure.md`
  — SHA-256 `6719fe4fa1392201e593f05f9789f0da40f16888cc9f77ac65d2bd87772dc3c7`.
- Confirmed native provider response: `API error (status 402 Payment Required):
  Grok Build usage balance exhausted`; no reviewer or gate artifact was
  produced, and no fallback was used.
- The earlier OMP/OpenRouter HTTP 402 is historical routing failure evidence,
  not a Grok subscription result. Invalid Sol artifacts remain quarantined and
  do not count as Oracle review. Batch 3 is stopped with its preserved dirty
  material untouched.
- Next action: retry the same direct v3 command after the Grok Build balance
  resets, or await explicit user authorization to change Oracle. Do not
  fabricate a verdict or switch providers implicitly.

# Historical prior Batch-2 provider-credit block — preserved record — 2026-08-30

- Historical state: `BLOCKED_PROVIDER_CREDITS` at the Batch-2 Oracle gate.
- The authorized v2 wrapper failure and its original evidence remain below for
  provenance; the current state above supersedes this stale checkpoint.
- Historical candidate HEAD: `5da26ec5be4d13559948fe4256a114ad7626482b`
  (committed implementation identity; **not** validly Batch-2 passed).
- Historical Oracle policy remained Grok 4.6. The authorized v2 wrapper failed
  before review commissioning with HTTP 402: `This request requires more
  credits, or fewer max_tokens. You requested up to 16384 tokens, but can only
  afford 388.`
- Historical failure receipt:
  `.oracle/receipts/oracle-nbf02-nbf03-grok-v2-launch-failure.md` — SHA-256
  `477eb4aec0374dadbc307ada8ee7ef4058830d0eeb1651b21e0fe3d41ad115ea`.
- Historical Grok v2 brief: `.oracle/briefs/oracle-nbf02-nbf03-grok-v2.md` —
  SHA-256 `e770f5bb556c81a6238e4dffce517662c1624d3c312e5147532f073aaf89762a`.
- Invalid Sol artifacts remain quarantined and do not count as Oracle review.
- Batch 3 was stopped; its preserved dirty/untracked materials were not
  mutated by that blocked launch.

# NBF execution contract — Batch 1 PASS checkpoint — 2026-08-30

- State: `BATCH_1_PASS` at checkpoint `878a9b2980f0eab6642ed51c30e687903a7213b9`.
- Oracle: Grok 4.6, per the authoritative model policy; verdict:
  `PASS_BATCH_1`.
- Settled plan v8 SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- Proposed tasklist v8 SHA-256: `88adb2e2e849285c7f83c924ef32c4fab12f1d05d3d4820dab0813f40c445e43`
- Frozen tasklist v8 SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- Luna gate receipt SHA-256: `2691b341c030e51056987f1aeb02fa130af75f22a901d5847cdf1c94b2d0f2f6`
- Sol freeze receipt SHA-256: `6e5a2b51c2b4954506a171884cbc2c2fe31bbf826b620ef13aa30ef1283f942e`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Immutable source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- PASS artifacts and production evidence:
  - `.oracle/checkins/batch-1-rework6-luna.md` — `de278150f2245ce7330694470f5b474788aaf1e234c712a5099dfbda2aeef850`
  - `.oracle/receipts/oracle-nbf01-rework6-luna.md` — `ce5136fde4af45a8d64f372b733ae1868c4b718258177bff88e6f262527ca4ba`
  - `.oracle/checkins/batch-1-rework6-grok.md` — `1a3cac2973d67ea270bd324ee742fcd074a696bff49ab55cd7e20b9aaa8d6b79`
  - `.oracle/receipts/oracle-nbf01-rework6-grok.md` — `5ede0d4cf30e0cef5c1dfbdf6fab7aed36269e818b1122bac3def59928e0832a`
  - attempt-6 production diff — `ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e`
- Wrapper correction: `.oracle/receipts/oracle-nbf01-rework6-grok-wrapper-exit-correction.md` — `43c1d6b250136d1449575c811d39976a9da177030d4d50cde2e88e0bf02c50f5`.
  The primary Grok wrapper returned exit 1 on provider spending-limit 403 only
  after PASS artifacts were complete; the existing exit-0 record is Luna-only.
- Batch 2 is eligible after this PASS and appears to be in progress in the
  preserved dirty worktree. No Batch-1 blocker remains; future Grok Oracle
  spending-limit availability is the only recorded later-gate availability
  risk.

# Prior status — Megado run resumed, custody/source reconciliation

Location: /Users/peteromalley/Documents/Arnold-oracle-nbf (branch megado-nbf-guard-0826)

Resume audit 2026-08-29: refreshed `origin/main` is `798c506192`; current branch
HEAD before rebase is `004540970f`. The checked-in `.oracle/tasklist.md` is a
foreign onboarding-run artifact and is NOT execution-ready for this NBF goal.
Next: preserve resume artifacts, rebase the five NBF-only commits onto the
refreshed source SHA, then have Sol produce/validate the NBF plan and tasklist.
Model policy: Luna normal; Sol planner/oracle/`[XHARD]`.

## Temporary execution-policy override — 2026-08-29

For the next 30 minutes, the user authorizes GPT-5.6 Sol subagents for obvious
fixes and normal implementation/validation work. Independent Sol oracle ownership,
the prohibition on direct main-agent implementation, no main merge, and all
existing delivery boundaries remain unchanged. The actual goal is unchanged and
no tasklist is frozen by this bookkeeping note.

## Authoritative model-policy update — 2026-08-29

From this instruction onward, Grok 4.6 is pinned for Oracle and any justified
`[XHARD]` work. Normal exploration, critique, execution, and independent review
remain GPT-5.6 Luna. This supersedes the earlier temporary Sol override for
future Oracle/`[XHARD]` dispatches; completed Sol planning and freeze receipts
remain historical evidence and are not invalidated. The frozen tasklist, goal
scope, and source code are unchanged.

## Prepared
- .oracle/northstar.md   — durable direction + anti-patterns
- .oracle/custody.md     — immutable baseline (base SHA f8725af516 == origin/main)
- .oracle/agent_goal.md  — frozen contract: worker_disposition control plane,
  three-door wiring, typed deaths, redispatch block, joint model admission,
  structural spy; model policy pinned: Sol planner/oracle/[XHARD],
  Luna everywhere else
- .oracle/briefs/planner-grok.md — Grok deep-plan brief

## Probes already green
- glm-5.3-flash via omp: verified live ("ok")
- grok CLI present at ~/.grok/bin/grok, headless --prompt-file supported
- fan.py available for parallel glm investigators/executors

## Resume sequence now authorized
1. Rebase preserved NBF artifacts onto refreshed `origin/main`.
2. Sol plans/revises and produces the NBF execution contract.
3. Luna settled-plan sense-check wave; Sol freezes classifications/tasklist only
   after a fresh independent Luna contract review passes.
4. Batched Luna execution, with any exceptional `[XHARD]` kernel routed to Sol.
5. Per-batch Sol oracle gates → rework loop until PASS each batch.
6. Final overall review (1–3 independent Luna passes), push megado-nbf-guard-0826 branch,
   main-merge only with your explicit approval at completion review

## Plan evolution log
- Entry 13 -> T7 cooldown-aware scheduling conditions (codex ADD; criterion 7)
- Entry 14 -> T8 typed provider_degraded scheduling condition (grok ADD;
  criterion 8; full spec .oracle/findings/evolution-entry14.txt)
- Foundation commits on main: a9e1c7d0d6, af370f5ec6 (cooldown/deferral), plus
  catalog/pin/timeout fixes f8725af516..ff4c64835b
