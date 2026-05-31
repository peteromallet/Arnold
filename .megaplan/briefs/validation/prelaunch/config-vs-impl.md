# Pre-launch verification — CONFIG-VS-IMPLEMENTATION GAP

Vantage: every place the runnable triple (chain.yaml + 14 briefs + PROGRAM + REGISTER) assumes a
harness/megaplan feature that the code does NOT implement. The confirmed exemplar (autonomy ladder
parsed only as `abort:`, ladder keys silently dropped) is one of a CLASS. This file enumerates the
whole class with file:line evidence. Severity gates a real autonomous launch.

The autonomy/zero-human-blocker story in REGISTER.md rests on THREE load-bearing harness behaviors —
the failure/escalate ladder, oracle-gated auto-merge, and require_clean_base — and ALL THREE are
config-only. The plan also assumes parallel track execution and several auto-resume hooks that do
not exist. Worse, the milestones that are supposed to BUILD the gate/oracle/recovery machinery need
that same machinery to run autonomously (bootstrapping circularity).

---

## CONFIRMED EXEMPLAR (given, restated for completeness)
`ChainSpec.from_dict._action` reads ONLY `block.get("abort", default)` —
`megaplan/chain/__init__.py:339`. `retry:`/`escalate:` sub-keys in `on_failure`/`on_escalate` are
never read. `VALID_FAILURE_ACTIONS = ("stop_chain","skip_milestone","retry_milestone")`
(`:89`) — `bump_profile`/`bump_robustness` are not implemented (grep: zero hits in repo).
So at runtime `on_failure`/`on_escalate` collapse to whatever the single `abort:` says — here
`stop_chain`, a human-halt. The REGISTER §3 edits #2/#3 ("ladder") are dropped silently.

---

## FINDING 1 — `bump_profile` / `bump_robustness` escalation ladder does not exist
- chain.yaml:107-113 declares retry→bump_profile→stop and escalate→bump_robustness→stop.
- Harness: `VALID_FAILURE_ACTIONS` (`megaplan/chain/__init__.py:89`) has only stop/skip/retry.
  `_handle_outcome` (`:1228-1234`) maps a policy string to advance/stop/retry/skip; there is no
  branch that raises a milestone's profile or robustness tier.
- The `retry_milestone` path (`:1477-1483`) re-inits the SAME milestone with the SAME profile +
  robustness, and there is NO retry COUNTER (grep retry_count/attempt in chain: zero). A
  deterministic failure (the common case for a code defect) → infinite re-init loop, bounded only by
  `driver.max_iterations` at the plan level, not at the milestone level. "retry ×2 then bump" is
  unreachable.
- NOTE: auto.py DOES have an internal execute-PIN escalation (`_escalated_tier`, climb execute tier
  within ONE plan run) — but that is per-plan complexity tiering, NOT the chain-level
  profile/robustness bump the chain.yaml means. Do not mistake one for the other.
- Severity: blocks-launch. Build in: M5c (run-outcome → transition vocab) + M5d (chain/supervisor
  escalate ladder) per REGISTER rows 74-75. Until then on_failure=stop_chain is a human halt.

## FINDING 2 — `driver.require_clean_base` is never parsed or enforced
- chain.yaml:128 sets `require_clean_base: true`; REGISTER §3 edit #5 makes it load-bearing
  (kills the carried-WIP false-positive review halts — a known recurring failure, see MEMORY
  project_worktree_carry_review_falsepositive).
- Harness: grep `require_clean_base` across `megaplan/` = ZERO hits. `ChainSpec.from_dict` driver
  block (`:384-401`) reads stall_threshold/max_iterations/poll_sleep/phase_timeout/status_timeout/
  on_escalate/robustness/auto_approve and NOTHING else. The key is silently ignored.
- `run_chain` snapshots `preexisting_dirty_paths = _dirty_worktree_paths(root)` (`:1250`) and
  carries them as preexisting — i.e. it TOLERATES carried WIP rather than refusing to start. There
  is no clean-base assertion / auto-clean / fail-loud.
- Severity: must-fix-in-M0/M1. M0 (dual-run rig) or M1 (foundation) must add the parse + enforce.
  Risk if unbuilt: the documented carried-WIP review false-positive halts the chain on a human.

## FINDING 3 — Parallel tracks (M1∥M2, M5a∥M5b∥M5-eval, M6∥M5d, M7 three-way) are not supported
- PROGRAM.md asserts parallelism throughout: `[T1, parallel with M2]` (m2.5), `M1 ∥ M2` (:350),
  `M5a ∥ M5b ∥ M5-eval` (:354), `M6 ∥ M5d` (:356), three-way M7 sinks (:358); M4 "internally 5
  parallel PRs" (:194). chain.yaml even orders M5a/M5b/M5-eval as flat sequential entries.
- Harness: the chain loop is a strictly serial single cursor — `while idx < len(spec.milestones)`
  (`:1313`), one `current_milestone_index`, one `current_plan_name`. `MilestoneSpec` has NO
  `parallel`/`after`/`depends`/`track` field (`class MilestoneSpec`, :~250-265). There is no
  dependency DAG, no concurrent driver, no fan-out across milestones.
- So every "∥" runs serially in listed order. This is not a correctness bug by itself (serial is a
  valid superset of the DAG ordering) BUT: (a) the wall-clock + cost model in PROGRAM/EPIC assumes
  overlap and is wrong; (b) M4's "5 parallel PRs" and M5's three-way fan-out are descriptions of
  intra-plan structure the single-plan driver does not parallelize either; (c) any place the plan
  counts on two tracks racing (e.g. M2.5 spike landing before M3 while M2 proceeds) is actually
  forced into a fixed serial order that must be verified to be a valid topological sort.
- Severity: fix-before-its-milestone (M5 era). At minimum the launch must drop the parallelism
  claim and assert the chain.yaml order is a valid topo-sort of dependency-dag.md. Real parallel
  tracks would need a new harness capability (multi-cursor chain) nobody is scheduled to build.

## FINDING 4 — Oracle hooks (behavioral-replay, substrate-swap, parity, grep-gates) are not harness features
- REGISTER row 56 + §4 make auto-merge "gated on parity gate + pipelines check/doctor linter +
  per-milestone strangler/substrate-swap oracles + chain↔EPIC↔briefs lint; red → auto-halt+revert."
  Line 119: "standing behavioral-replay + substrate-swap oracles every milestone."
- Harness: grep oracle/substrate-swap/behavioral-replay/lint-green in `megaplan/` = ZERO. These are
  to-be-BUILT artifacts (the briefs themselves scope them: m0/m1/m2/m3/m4/m5-eval mention oracle as
  a deliverable). They are NOT harness hooks the chain consults before merging.
- What the chain ACTUALLY does on advance (`:1484-1521`): commit+push the phase, capture sync
  state, mark PR ready, then under `merge_policy: auto` call `_enable_auto_merge` →
  `gh pr merge --auto --squash --delete-branch` (`git_ops.py:712-731`). "--auto" defers to
  GitHub's branch-protection / required CI checks ONLY. If the repo has no required-check branch
  protection, `gh pr merge --auto` merges as soon as mergeable — and the fallback path even does an
  IMMEDIATE unconditional squash merge when auto-merge is unavailable (`git_ops.py:726-730`).
- NET: auto-merge "works" mechanically but it is NOT gated on any epic oracle/parity/grep gate. The
  containment story in REGISTER §4 ("a wrong-but-green change cannot auto-merge") is FALSE unless
  every one of those gates is wired into GitHub required checks on the base branch BEFORE M0 runs.
  Nothing in the triple establishes that branch protection.
- Severity: blocks-launch. The single biggest autonomy risk: a milestone that builds a partial/wrong
  conversion auto-squash-merges to main with no oracle in the merge path. Must-fix before t0:
  either (a) configure GitHub branch protection requiring the gate checks, or (b) keep
  `merge_policy: review` until M5d wires real gate-checked merge.

## FINDING 5 — `merge_policy: auto` does auto-merge — but unconditionally, and bypasses the gates
- This is the nuance behind Finding 4: the feature EXISTS (Finding: not absent), but its semantics
  are "merge on GitHub-mergeable", not "merge on epic-gate-green". The plan conflates the two.
- Evidence: `_enable_auto_merge` (`git_ops.py:712`) — no call into parity gate / oracle / grep
  gate; fallback (`:726`) merges immediately with `--squash` and no `--auto`, i.e. no CI wait at
  all if auto-merge is disallowed on the repo.
- Severity: must-fix-in-M0/M1 (couple to Finding 4's branch-protection requirement).

## FINDING 6 — `STATE_AWAITING_HUMAN` and TIEBREAKER park on a human; no auto-answer/auto-tiebreaker
- REGISTER rows 60 (clarify auto-answer from brief→escalate→best-guess) and 67 (auto-invoke
  tiebreaker-run on STATE_TIEBREAKER_PENDING) promise these never park.
- Harness: `auto.py:1544-1571` — on STATE_AWAITING_HUMAN the driver logs "automation stopping" and
  returns outcome `awaiting_human` with a human hint ("answer via `megaplan override add-note` and
  resume via `resume-clarify`"). NO auto-answer, NO escalate-to-model, NO auto-resume.
  `auto.py:1572-1573` — on STATE_TIEBREAKER_PENDING it logs "run 'megaplan tiebreaker-run …'" and
  returns; no auto-invocation.
- Chain consequence: `_handle_outcome` (`:1213-1234`) only special-cases `done`/`aborted`/
  `escalated`; `awaiting_human` (and `paused`, `cap`, `blocked`) fall into the else→`on_failure`
  branch → which the harness has read as `stop_chain` (Finding 1) → chain halts on a human. So a
  single clarify ambiguity or tiebreaker in any of 14 milestones stops the whole autonomous run.
- Severity: blocks-launch for the "zero human blocker" claim. Build in: clarify auto-answer is
  unscoped in the briefs (REGISTER row 60 asserts it but no milestone owns building it — GAP);
  tiebreaker auto-invoke similarly unowned. These are claimed-converted blockers with no builder.

## FINDING 7 — Bootstrapping circularity: the chain needs machinery the milestones build
- The autonomy guarantees (ladder=F1, oracle-gated merge=F4/F5, run-outcome transitions=M5c,
  supervisor escalate=M5d, recover-blocked spine=M4) are the DELIVERABLES of M3-M5d. But the chain
  must run M0-M5d AUTONOMOUSLY to produce them. Until M5c/M5d land, the chain runs on TODAY's
  harness: serial, abort-only failure policy = stop_chain, no clean-base, unconditional auto-merge,
  human-parking clarify/tiebreaker.
- So the early milestones (M0-M4) — the most expensive (apex/extreme) and most likely to hit a
  clarify/blocked/escalate — run with the LEAST autonomy. The zero-human-blocker property is only
  even potentially true AFTER the milestones that build it have themselves been driven through the
  un-autonomous harness.
- Severity: blocks-launch as stated; the realistic posture is "expect human touches through M5d,"
  which contradicts REGISTER §1's "no agent executing any milestone stalls."

---

## VERDICT
Do NOT launch as a hands-off autonomous chain. The zero-human-blocker guarantee rests on three
config-only behaviors (failure/escalate ladder, oracle-gated merge, require_clean_base) that the
harness silently ignores, plus parallel-track + auto-clarify/tiebreaker hooks that do not exist and
have no owning milestone — and the machinery that would make it true is itself the chain's output
(bootstrapping circularity). Either down-scope to "attended chain, human-park expected through
M5d" or land Findings 1/2/4/6 as a pre-M0 harness patch + configure base-branch protection first.
