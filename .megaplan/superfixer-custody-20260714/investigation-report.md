# custody-control-plane-20260714 superfixer chain-of-custody report

Evidence captured in UTC. Investigation owner: resident run
`subagent-20260714-183634-a0e5519b`.

## Observation health and six evidence levels

- Runtime container: hostname `8fb90d8780ad`. Resident runtime source
  `/workspace/arnold-consolidation-20260714` remained clean at pinned revision
  `2a5c263df865daff3760c47380f8eb17f240273a`. The live supervisor source was
  `/workspace/.megaplan/repository-strategy-roadmap-supervisor-source` on
  `editible-install`; three pre-existing generated composed-doc modifications
  were preserved.
- Live process: at initial observation on 2026-07-14, no chain runner, phase
  worker, L1 repair worker, or L2 worker owned the target. The watchdog was live
  from `/usr/local/bin/arnold-watchdog`. A separate reconciliation process was
  observed and not disturbed; it exited before deployment.
- Session marker:
  `/workspace/.megaplan/cloud-sessions/custody-control-plane-20260714.json`
  had `should_run=true`, the expected workspace/spec, and a successful launch
  timestamp of `2026-07-14T17:21:49Z`.
- Chain state:
  `/workspace/custody-control-plane-20260714/Arnold/.megaplan/plans/.chains/chain-1e998199f544.json`
  held milestone index 0, no completed milestones, and `last_state=blocked`.
- Plan state:
  `/workspace/custody-control-plane-20260714/Arnold/.megaplan/plans/m5-run-authority-receipt-20260714-1428/state.json`
  held `current_state=blocked`, iteration 2, review/manual-review resume authority,
  failure `review_quality_blocked_unknown`, and the exact review custody hash
  `sha256:587b481cba37d751e37bc0fd243377bb78cc1c6a8ae1b6c7e518182254fa0c43`.
- Logs: the plan failure was recorded at `2026-07-14T18:04:22Z`; watchdog
  request `84134d62e1e766a3c0264603a57f238dcd048679eec4a9d59600ed31dbb0b5c0`
  was queued at `2026-07-14T18:33:55Z` but initially accepted without a claim
  or attempt. The chain log was blocked with no runner.
- External state: PR 250 was open/draft, not approved, mergeable state unstable,
  and its `test` check failed at `2026-07-14T18:05:06Z`; generated-doc drift
  also failed while merge/Docker checks were skipped. No merge or approval was
  performed.

The exact review artifact contained five executable deterministic checks whose
statuses were detailed strings such as `failed: ...`. It recorded 38 collection
errors across the M1/M2/M3 selected suites (16/15/7), three rejected completion
receipts, `verified_count=3` with `divergence_count=3`, stale M1/M2 receipt
digests, no canonical retirement marker, and a blocked final attestation.

## First failure and missed backstops

The first failed layer was L1 before dispatch:

- TRACKED: partial. The watchdog produced an accepted request, but it lacked a
  blocker/task identity and remained unclaimed.
- FIXED: no. No L1 worker existed.
- INTENT: the bounded one-attempt deterministic-quality path existed, but was
  unreachable.
- CONTEXT: missing. `handlers/review.py::_deterministic_review_block_evidence`
  accepted only exact `fail`, `failed`, or `error`; it dropped live detailed
  statuses such as `failed: ...`. Separately, merge commit `cbe69337...` lost
  `quality_gate_blocked` and `deterministic_quality_blocked` from the L1
  repairable-token whitelist even though the one-attempt policy and tests
  remained.

L2 did not launch because L1 had never claimed the request. This is a
pre-dispatch blind spot: L2 had no failed L1 attempt to classify. After the
corrected L1 was exercised, a second source/install reconciliation defect was
proven: its managed dev and Kimi calls omitted newly mandatory machine-origin
arguments and both exited with CLI return code 2 before doing work. The L2
worker and meta-retrigger seams had the same provenance drift. L2 later tracked
that failure under `model_tool_launch_failure`, but the master-plus-path mutation
gate correctly denied mutation and recorded `NO_FIX`; it did not weaken the
gate.

L3's latest completed audit predated the target failure (audit generated around
`2026-07-14T13:35Z`, completed around `2026-07-14T13:52Z`; target failure was
`2026-07-14T18:04:22Z`). Its accepted-unclaimed-cycle checks would only run at
the next cadence, so it had not yet missed this incident, but the backstop was
delayed by cadence and could not provide immediate recovery.

The next L3 cycle ran from `2026-07-14T19:35:06Z` to
`2026-07-14T19:41:29Z`. It detected `green_with_recent_repair_churn`, the
accepted/dispatched attempt-custody inconsistency, and low resolver confidence.
It correctly suppressed another meta-repair dispatch because the ordinary L1
target had corroborated live activity. That proves L3 eventually tracked the
incident, while also preserving the recurrence gap: cadence and incomplete
attempt-to-current-retrigger linkage prevent it from being an immediate repair
backstop.

Failure-shape verdicts:

- blind fixer: proven at the L1 pre-dispatch boundary;
- false success: absent for the fixer (there was no attempt); the plan/review
  correctly contradicted prior execute success and failed closed;
- token drift/unreachable recovery: proven;
- evidence-contract gap: proven;
- guard weakening/fabricated approval: absent;
- deterministic spin: absent; review rework budget 2 was exhausted and the
  distinct bounded repair path stopped instead of spinning;
- budget failure: the first post-dispatch L1 run stopped deterministically after
  both model launches failed their provenance contract.

## Durable supervisor repair

Published fast-forward commits on `origin/editible-install`:

1. `78f686423e3d7e15d8878c8a99d05489428eb413` — normalize detailed failed/error
   review statuses, restore deterministic-quality tokens, and add fail-closed
   legacy compatibility bound to the exact current plan/chain fingerprints and
   review artifact hash.
2. `5c5932f44ecf6f541e08f4188d90af70fc828002` — derive a missing legacy blocker
   identity only from the hash-bound deterministic review evidence.
3. `98c56727ceab37d92343f928c7f0ba2b167365af` — restore mandatory managed-agent
   provenance to watchdog L1/L2 dispatches and L1 dev/Kimi plus L2 worker calls.
4. `e910b289f3df4e78bd080bafa20f07a544e169ce` — bind the internal L2 ordinary
   repair retrigger to `meta_repair_retrigger` machine provenance.

No code rewrote plan state, review state, receipts, or approval. Legacy
compatibility fails closed unless the authoritative current target, state and
chain fingerprints, exact persisted review hash, and executable failing checks
all match. The repair allowance remains one bounded attempt.

Focused validation:

- deterministic writer/token/legacy-custody tests: 5 passed;
- `tests/cloud/test_repair_trigger_wrapper.py`: 20 passed;
- related repair-loop semantic tests: 5 passed;
- `tests/test_managed_agent.py`: 21 passed;
- new provenance selection: 4 passed;
- Python compile and `bash -n` on affected wrappers: passed;
- full `test_watchdog_wrappers.py`: 255 passed, 29 failed; representative
  failures reproduced against the unpatched deployed baseline and no affected
  behavior regressed. This pre-existing suite drift is retained as a caveat,
  not reported green.

Deployment receipts:

- Source fast-forwarded to `e910b289f3df4e78bd080bafa20f07a544e169ce`
  with the three unrelated generated-doc modifications preserved.
- Canonical `apply_install_sync` succeeded at `2026-07-14T19:14:07.618216Z`
  for revision `98c56727...`, event `isa-f1e524adf1e2`, and again after
  `e910b289...`; expected and observed git heads matched and pip returned 0.
- Canonical SSH hot-upload was attempted with only the three affected wrappers
  and no restart, but the in-container operator lacked host SSH authorization.
  The same narrow on-box deployment copied those exact source wrappers into
  `/usr/local/bin`; source/runtime SHA-256 pairs matched and all passed `bash -n`.
  No watchdog or session restart occurred.

## Re-trigger and original-session evidence

- First queue retrigger at `2026-07-14T19:05:11Z` failed closed with
  `claim_retry=1/3` because the blocker identity was absent; this motivated the
  hash-bound blocker fix.
- Ordinary queue retrigger at `2026-07-14T19:07:18Z` launched attempt
  `c7dde511fcb6234bef00b3e7a403022b823a3fb1973a539e4b0f3356a203c85c`,
  managed run `managed-automatic-repair-6927a5c43ce698a84241`, blocker
  `blocker:v1:848e4a41b078fc4399c7ff8c087f53236349fec17a770a0443a504f6bd0a047f`.
  It proved the missing-provenance defect and stopped; it did not mutate the
  project.
- L2 evidence run `managed-automatic-meta-repair-c6cc2f02ef1fcbc8254f`
  classified `model_tool_launch_failure` and recorded meta record
  `34941d34-79f4-46e8-92b0-03943e3de5fa` at `2026-07-14T19:16:44Z`.
- The canonical post-fix meta-retrigger seam started managed run
  `managed-automatic-repair-retry-6651d8e32ac3f26ce440` at
  `2026-07-14T19:18:44Z`, preserving the same request, blocker, parent run, and
  session. Its L1 dev worker launched successfully with provenance
  `repair_loop_worker`, attempt 3.
- That ordinary worker committed and pushed target-repo compatibility commit
  `f8464e305980960ecf2c44ede195d7c9033f7490` at
  `2026-07-14T19:25:59Z`. Its focused validation collected 137 tests with zero
  collection errors; deeper legacy semantic mismatches remained. The following
  Kimi recovery launch also carried valid machine provenance and attempted one
  ordinary chain relaunch.
- The ordinary fixer also generated, but did not commit or admit, updated
  receipt-suite/completion-receipt reconciliation artifacts, proof map,
  completion manifest, retirement marker, and incident-ledger projections. They
  remain dirty in the target worktree and are inputs to fresh review attempt 4,
  not accepted completion evidence from this investigation. No investigator
  hand-edited those artifacts.
- The first relaunch did not hand-advance: the chain command observed the exact
  plan was durably blocked with no active step and preserved the stop. The live
  chain log records this at `2026-07-14T19:28Z`.
- In iteration 2, L1 revalidated the former collection blocker with focused
  collection checks and a broad `pytest --collect-only -q`: 12,148 tests
  collected successfully in 4.19 seconds. It then used the supported,
  evidence-bearing `quality-gate resolve --resolution fixed` followed by
  `override recover-blocked`. This cleared the exact stale quality blocker and
  moved the plan from `blocked` to `executed` solely so review could rerun; it
  did not write a passing review, approve the plan, complete a milestone, or
  merge the PR.
- The second single Kimi relaunch started fresh review attempt 4. At
  `2026-07-14T19:43:36Z`, authoritative plan state was `executed`, `latest_failure`
  and `resume_cursor` were absent, `active_step.phase=review`, and reviewer PID
  3036954 was live with fresh liveness events. Chain state correspondingly moved
  from `blocked` to `executed`, with no completed milestones.
- The bounded repair run finished at `2026-07-14T19:43:25.077442Z` with outcome
  `partial_liveness`, not `complete` or `verified_recovered`. Managed retrigger
  run `managed-automatic-repair-retry-6651d8e32ac3f26ce440` returned 0 at
  `2026-07-14T19:43:32Z`. The original session therefore genuinely advanced
  under a live review process, but recovery cannot be claimed until that review
  and the ordinary chain admission gates produce terminal evidence.
- Fresh external verification at target head
  `f8464e305980960ecf2c44ede195d7c9033f7490` showed PR 250 still open/draft,
  no review decision, and GitHub Actions run 29361794303 `test` failed at
  `2026-07-14T19:27:06Z`. The failed step was the generated-Arnold-docs drift
  check; Docker and merge-result conformance were skipped. This remains a real
  admission caveat for the live reviewer.
