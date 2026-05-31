# Arnold Epic — Pre-Launch Verification Synthesis

**Verdict: NO-GO for hands-off launch as-is.** The runnable triple
(`.megaplan/briefs/pipeline-unification-EPIC.md` + `.megaplan/briefs/epic-pipeline-unification/{chain.yaml, m0..m7}` +
`.megaplan/briefs/validation/{sequencing/PROGRAM.md, human-blockers/REGISTER.md}`) describes an autonomous,
gated, parallelizable, retry/escalate-laddered run. The live harness
(`megaplan/chain/__init__.py`, `megaplan/chain/git_ops.py`, `megaplan/_pipeline/*`) implements a
**strictly serial, retry-once-then-stop_chain, unconditionally-auto-merging** driver. The autonomy
story is config + prose the engine silently drops. It is launchable **after** a pre-t0
engine-readiness patch + base-branch protection (the must-fix list below) — but with a corrected,
honest posture, not the REGISTER's "172/172 converted, zero human blockers."

All load-bearing claims below were re-verified against the code at HEAD on this branch.

---

## The class of defect (confirmed exemplar, now generalized)

The plan repeatedly **assumes harness/megaplan features that do not exist**, and the machinery the
autonomy rests on is itself the chain's own output (bootstrapping circularity). Verified instances:

- **Autonomy ladder dropped.** `chain.yaml` declares `on_failure: {retry, escalate, abort}` and
  `on_escalate: {escalate, abort}` ladders. `_action()` at `chain/__init__.py:339` reads **only**
  `block.get("abort", default)` — the `retry:`/`escalate:` sub-keys are silently ignored.
  `VALID_FAILURE_ACTIONS = ("stop_chain","skip_milestone","retry_milestone")` (`:89`);
  `bump_profile`/`bump_robustness` have **zero implementations** (grep = 0). So at runtime
  `on_failure`/`on_escalate` both resolve to `stop_chain` (`:347-348`), and `_handle_outcome`
  (`:1227-1234`) returns `"stop"` for any failed/non-done outcome → chain halts on a human.
- **`require_clean_base` never read.** `chain.yaml:driver.require_clean_base: true`; `ChainSpec.from_dict`
  driver block (`:384-401`) parses only stall/max_iter/poll/timeouts/on_escalate/robustness/auto_approve.
  Grep `require_clean_base` in `megaplan/` = 0. Carried WIP is tolerated, not refused.
- **`depends_on`/`parallel`/gating is prose-only.** `MilestoneSpec` (`:170-187`) has no
  `depends_on`/`parallel`/`gate` field; grep in `chain.yaml` and the harness = 0. The loop is a
  single serial cursor (`:1313 while idx < len(...)`, `:1597 for index, milestone in enumerate(...)`).
  Every "gated on Mx green" and "∥ parallel" is enforced solely by **list adjacency**.
- **Auto-merge is ungated.** `_enable_auto_merge` (`git_ops.py:712`) runs
  `gh pr merge --auto --squash --delete-branch` (defers only to GitHub branch protection / required
  CI) and on "Auto merge is not allowed" **falls back to an immediate unconditional squash merge**
  (`:726-730`) — no oracle/parity/strangler/grep gate anywhere in the merge path.
- **No engine-selection flag.** Chain shells every sub-command via `[sys.executable, "-m", "megaplan", ...]`
  (`chain/__init__.py:762, :835`); no `--engine`/venv/interpreter flag. The driving engine is whatever
  python launched `megaplan chain`, fixed before the chain starts.

---

## 1. blocks_launch — the chain literally cannot self-run as written

1. **Autonomy ladder unbuilt → halts on first failure.** `on_failure`/`on_escalate` collapse to
   `stop_chain` (`chain/__init__.py:339, :347-348, :1227-1234`). The single t0 "go = full autonomy"
   framing (`chain.yaml:11-15`) is false; the first non-`done` outcome on any of 14 milestones (most
   likely on apex/extreme M3/M5c/M6) parks on a person. `retry_milestone` also has **no counter**
   (`:1467-1483` re-inits the same milestone at the same tier; grep `retry_count`/`attempt` = 0) — if
   ever wired naively it is an infinite loop on deterministic failure.
2. **M0 is a manual t0 pre-step, not chain milestone #1.** M0's deliverable is the pinned/frozen
   engine that drives the epic, but the chain has no interpreter-selection flag and cannot install a
   venv and re-exec into it. A chain milestone cannot pin the engine that is already running it
   (bootstrap paradox). Listing `m0-keepalive-floor` as milestone #1 in `chain.yaml` is structurally
   impossible to satisfy.
3. **Auto-merge to `main` with no oracle in the path.** Under `merge_policy: auto` a partial/wrong
   conversion auto-squash-merges (and the fallback path merges with no `--auto`, no CI wait). REGISTER
   §4 / row 56 claim "a wrong-but-green change cannot auto-merge" — false unless the epic's
   oracle/parity/strangler/grep gates are wired as **GitHub required checks**, which nothing in the
   triple establishes.
4. **Per-milestone oracle / strangler / behavioral-replay / chain↔EPIC↔briefs lint are to-be-built
   deliverables with no harness hook.** grep `oracle|substrate-swap|behavioral-replay|lint-green` in
   `megaplan/` = 0. The chain has no pre-advance/pre-merge hook that consults a green/red verdict; the
   only enforcement surface is a CI check that gates MERGE, not chain progression.
5. **Clarify / verify-human / tiebreaker park on a human and fall to `stop_chain`.** On
   `STATE_AWAITING_HUMAN` the runner logs "automation stopping"; on `STATE_TIEBREAKER_PENDING` it prints
   a human `tiebreaker-run` command. Neither is `done`/`aborted`/`escalated`, so both hit the else →
   `on_failure` → `stop_chain` branch. REGISTER rows 60/61/67 promise auto-answer/auto-tiebreaker; no
   owning milestone builds it into the **live** driver.
6. **Bootstrapping circularity (master).** The ladder, oracle-gated merge, run-outcome vocabulary
   (M5c), supervisor escalate (M5d, the 13th node, after M6, default-OFF), and recover-blocked spine
   (M4) are the chain's own outputs. The frozen-at-t0 engine cannot inherit them mid-run, so the most
   expensive early milestones run with the **least** autonomy.

## 2. must_fix_in_m0_m1 — machinery to build/pre-build before autonomous run

These must land on `main` and be included in the t0 pin **before** `chain start` (a pre-M0 / "M(-1)"
engine-readiness patch — a milestone cannot retroactively fix the engine already driving it):

1. **Ladder parse + impl in the pinned engine.** Fix `_action` (`:339`) to read `retry:`/`escalate:`;
   add `bump_profile`/`bump_robustness` to `VALID_FAILURE_ACTIONS` + `_handle_outcome`; add a
   per-milestone retry counter (bounded ×2 then bump). Cap retries on apex+extreme at 1; make
   `bump_profile` a no-op-with-warning when already apex (there is no tier above `apex.toml`).
2. **`require_clean_base` read + pre-run assertion** (auto-clean or fail-loud) in the milestone loop
   before `_init_plan` — closes the recurring carried-WIP review false-positive halt class.
3. **Oracle/strangler/parity gates wired as GitHub required checks** on each milestone PR (couple to
   base-branch protection) so `--auto` actually defers to them; do **not** assume the chain invokes
   oracles itself.
4. **`awaiting_human` / `tiebreaker_pending` handling in the live driver**: auto-invoke `tiebreaker-run`
   then resume; map `awaiting_human` to a brief-sourced best-guess-and-flag or into the ladder, not the
   silent else → `stop_chain`.
5. **External wallet/budget ceiling** for the whole run (the in-band Governor/Capacity-Lease is built by
   M3, mid-run; the chain has no spend cap field). `stop_chain`-on-failure fires on failure, not overspend.

## 3. seam_mismatches — cross-brief contract drifts to fix

1. **`depends_on` graph is prose-only** — state explicitly that ordering is enforced SOLELY by linear
   chain order + per-milestone strangler gate, and strip ∥-parallelism language from the runnable
   artifact (or add a real `depends_on`/gate field as an M1/W8 deliverable). The "non-negotiable"
   M5-eval→M5-cal edge is enforced only by YAML line adjacency.
2. **M2.5 cites the wrong home for `_pipeline_paused_stage`** ("_core/workflow.py"); actual home is
   `_pipeline/run_cli.py:267` (read), `steps/human_gate.py:94` (write), `cli/__init__.py:951` (pop).
   M2.5 also omits `awaiting_user.json` (`_pipeline/executor.py:264,376 → resume.py:104 → run_cli.py:271`),
   which M5c F6 consumes — the resume reconciliation is four-way, not three-way.
3. **"M2 routing-key type" does not exist.** M5a/M5c/M5-eval depend on it; M2 defines Port,
   ReduceResult/Aggregate[T], SelectionResult, StateDelta, planning_reduce→GateRecommendation — no
   `routing-key`. Add an explicit `RoutingKey` to M2 or have downstream cite the concrete type
   (likely `SelectionResult.winner` or a `ReduceResult` label).
4. **M5b→M5c run-outcome handoff has no named type and no 4→5 mapping table.** M5b says "I define a type
   M5c consumes" without naming it; M5c maps from planning `STATE_*` without citing an M5b type. Name the
   reducer return type in M5b; write the `{success, blocked_by_quality, blocked_by_prereq, timeout} →
   {succeeded, failed, escalated, blocked, awaiting_human}` table in M5c (resolve where `timeout` and
   `blocked_by_prereq` land) — silent-downgrade class.
5. **M5d binds onto a non-existent "M5c F6 auto-merge."** M5c F6 is explicitly halt-and-wait and ships
   no `gh` auto-merger. Assign the auto-merge-on-green actor to M5d concretely (run-granularity
   orchestration over `chain/__init__.py:1318-1514`); M5c F6 should state it ships only halt + cursor +
   resume. (REGISTER row 73 claims this is converted — it is not.)
6. **M5-cal references the M4 scaffold record `{judge-version, rubric-version, input-set-hash, score}`
   but its taint-aware aggregation (Scope #6) needs the `taint` field only the M5-eval attributable
   record carries.** Re-target M5-cal Scope #1 EvaluandRef to the M5-eval Evaluand; one taint source.
7. **M4 Scope #7 "Kill the read-time substring vendor classification" contradicts strangler discipline.**
   Every other brief keeps the old `_classify_vendor` read live until M6 retires it. Change "Kill" →
   "stop the new path reading the substring classifier; the old read stays live, retired at M6."
8. **M5c forward-read method has two names** (`read_valid_targets` vs `valid_targets`); M5d binds against
   both. Pick one (recommend `read_valid_targets` as the interface method, `valid_targets(state)` as the
   planning-binding impl) and align M5d + PROGRAM.

## 4. corrected_sequencing — the fixed front-of-sequence

- **Before t0 (operator + pre-M0 engine-readiness patch on `main`, then pin):**
  1. Land the ladder parse+impl (must-fix #1), `require_clean_base` (#2), `awaiting_human`/tiebreaker
     handling (#4) into `chain/__init__.py`; merge to `main`.
  2. Configure base-branch protection requiring the oracle/parity/strangler/grep-gate CI checks (#3) so
     `merge_policy: auto` actually defers to them — OR keep `merge_policy: review` until M5d wires
     gate-checked merge.
  3. Build the **frozen venv** from `main`@t0-sha and launch `megaplan chain` from that interpreter with
     `--no-git-refresh`. This is W1 of M0 as a **scripted operator pre-step / `tools/` artifact**, NOT a
     chain milestone. Set the external wallet ceiling (#5).
  4. Run the M1/W8 chain↔EPIC↔briefs lint as a **pre-flight check** (drop the "auto-arm on lint-green"
     framing — the lint is M1's own output and cannot gate the run that produces it; the real
     authorization is the single human `chain start`).
- **Chain milestone #1 (M0', harness-code-only):** W2 report-only validator, W3-W5 dual-run/oracle/replay
  harnesses + corpus, W6 strangler-gate entrypoint — the in-repo subset only. Update
  EPIC/PROGRAM/REGISTER/chain.yaml so milestone #1 is harness-code-only.
- **M1 onward:** runs on the patched, pinned engine. Re-pin M1's file:line citations against the current
  tree (symbols real, line numbers stale, e.g. `load_plan_from_dir` is at `state.py:127` not `:93`) or
  instruct the agent to grep-by-symbol. Treat all ∥ tracks as a valid topological-sort assertion over
  serial order, never as concurrency.

## 5. cost_time_estimate

- **~$500–$1,200, midpoint ~$850, budget the upper band (~$1.2k).** megaplan run cost has ~3× variance at
  fixed config; ~half the spend sits in three apex+extreme+max milestones (M3 hinge, M5c control-plane,
  M6 swap at ~$80–200 each). Calibrated from real `state.json` anchors (pipeline-week1 $47, cloud-runtime
  $97, add-resident-discord $158, resident-orchestrator $420; M3/M6 are larger/deeper/higher-tier).
- **Wall-clock ~3–7 days CONTINUOUS machine time** = the **sum** of 14 serial milestones, not the shorter
  critical path PROGRAM advertises (the chain cannot exploit ∥ tracks). Per-phase cap 7200s.
- **Calendar time is open-ended** because (per blocks_launch #1) the unpatched chain halt-and-waits on
  first failure with upstream spend sunk. Add a re-run contingency (one hand-driven apex re-run ≈
  +$80–200 after a halt). If the ladder is implemented but uncapped, retries multiply cost hardest on the
  most-expensive, most-likely-to-fail nodes (M3 ×3 ≈ +$270–600). **This is not fire-and-forget.**

## 6. go_no_go

**NO-GO as-is. Conditional GO after the must-fix list — with a corrected posture.** There is no deeper
architectural impossibility: the seam contracts are mostly aligned in intent (taint reuse, Manifest
identity, one-Ledger join key, grep-gate escalation all check out), and the must-fix items are bounded
days-1 driver hardening (ladder parse+impl, clean-base, awaiting_human/tiebreaker, oracle-as-CI,
external wallet) plus brief reconciliations. The deeper issue is **not** technical infeasibility but a
**truthfulness gap**: REGISTER's "172/172 blockers converted, zero human blockers, no agent stalls" is
contradicted by the live driver on every count. Either (a) land the pre-t0 engine-readiness patch +
base-branch protection and re-pin, then launch with the ladder genuinely live; or (b) launch **attended
through M5d** and downgrade the guarantee to "halts-with-ticket at every unrecovered red gate." Do not
press "go" believing the current triple is hands-off — it is not.
