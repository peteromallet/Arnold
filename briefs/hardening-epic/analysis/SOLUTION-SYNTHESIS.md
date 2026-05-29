# Solution synthesis — A (excellent fix), B (right fix + implications), C (applied)

Companion to ROOTCAUSE-SYNTHESIS.md and DEEPER-SYNTHESIS.md. This is the "what to build" doc.

---

## A. The excellent solution — a 3-layer loop that converges, with a backstop

Three agents attacked A from different lenses (Codex: algorithmic/loop-control; Claude: agent-prompting;
Claude: pragmatic/ROI). The excellent solution is the **layered composition** of all three, where each
layer makes the next *safe*, but **Layer 0 alone captures ~80% of the value.**

### Layer 0 — Backstop cap (ship FIRST; guaranteed win, hours of work)
The plan-critique loop simply never got the cap the execute-review loop already has (`review.py:248`).
Add it in `_apply_gate_outcome` (`gate.py:360-361`), replacing the unconditional `revise`:
- **Hard round cap**, scaled by robustness: light 2 · **full 4 (default)** · thorough 6 · extreme 8 · bare 0.
- **No-net-progress early stop**: 2 consecutive rounds of `resolved_delta==0 AND new_blocking>=1` → stop early.
- **Severity-gated cap action** (reuse the predicate at `gate.py:328`): cosmetic-only open flags →
  *force-proceed-with-note*; any open correctness/security flag → **ESCALATE to human** (never silently ship).
- **Config**: `max_critique_iterations=4`, `max_robust_critique_iterations=6`, `max_critique_no_progress=2`
  in `DEFAULTS` (`types.py:672`) + `_SETTABLE_NUMERIC`.
- **What influences the setting**: robustness (rounds) + remaining-flag severity (cap action). NOT plan size, NOT stakes.

*Impact:* cap=4 alone elides M2 rounds 5-9 ≈ **605K tokens (~55%)** and ~half of M4's 450K. This is the
guaranteed-correct, low-risk fix and should land on its own.

### Layer 1 — Convergence mechanism (ship SECOND; mostly prompts + one churn guard)
Makes the loop *converge* rather than merely *stop at N*. These attack the root dynamic
(unbounded discovery + moving target). Mostly **prompt edits** (cheap), plus one code-enforced churn bound:
- **Exhaustive-first for discovery lenses** — rewrite `scope`/`all_locations`/`callers` guidance
  (`robustness.py:47-82`) to demand a *closed* enumeration on round 1 ("list every X with the search
  command; if you can't prove the list complete, flag the gap loudly"). Kills the one-location-per-round
  peel and the R1 "validate my own JSON" waste.
- **Near-last-round signaling** — inject a 3-tier block (normal / penultimate "prioritize correctness,
  no new scope" / final "only significant correctness/security") into both the critic
  (`critique.py:391-423`) and reviser (`critique.py:115-131`) prompts. Turns the existing advisory hint
  (`gate_checks.py:125-129`) into enforced behavior.
- **Severity discipline** — require a per-finding `severity` and reframe "when in doubt, flag it" as
  *visibility, not blocking* (doubt → `minor`, never inflate to blocker). This is what kept the loop alive.
- **Bounded revise churn** — add "TOUCH ONLY FLAGGED SECTIONS, copy the rest verbatim" to the revise
  prompt, **and enforce in code**: after revise, compute delta via `compute_plan_delta_percent`
  (`gate_signals.py:55-59`); budget = max(15%, 40 lines); unjustified overage → blocking flag. Stops the
  53%/round rewrite that handed each critic fresh surface.

### Layer 2 — Formal convergence + anti-regression (only if telemetry shows residual)
The most engineering, and the **over-engineering landmine the pragmatic lens flagged**: carrying prior
PASS verdicts forward (diff-aware anchored re-critique) risks *silently missing a regression* in a
previously-passing area. **The synthesis insight: that risk is defused by sequencing.** Once Layer 1
bounds churn to ≤15% and anchors invalidate on any diff-touch, anchoring becomes safe — so:
- Define a **lexicographic loop variant** `V = (open_blocking_flags, invalidated_anchors,
  unclosed_required_sets, churn_violations)` that must strictly decrease each round; surface it in
  `build_gate_signals` (`gate_signals.py:91-220`); on ITERATE, allow `revise` only if `V` decreased.
- **Anchored PASS verdicts** — carry forward, invalidate only spans the diff touched. Build this **last**,
  and only after churn-bounding (Layer 1) makes it non-regressive.

**Why this is excellent, not just a cap:** Layer 0 guarantees termination cheaply; Layer 1 makes most
runs converge *before* the cap for the right reason (exhaustive first pass + bounded churn); Layer 2
gives a formal decreasing-variant guarantee and is only worth it if data shows plans still hitting the
cap. Build 0 → 1 → 2, stop when telemetry says the residual isn't worth chasing. M2 under Layer 0+1 ≈ 2-3 rounds.

---

## B. The right solution — the completion contract, with implementation reality

Two independent models (Claude + Codex, blind) converged on the **same** design, so the *shape* is
high-confidence: **a terminal state is a claim; a completion verdict is the authority.** A reusable
`CompletionContract` of composable evidence providers verifies objective facts at every terminal
transition. (Full design: `B-completion-contract-{claude,codex}.md`.) Three implication agents then
ground-truthed it against the codebase. Net:

**Reuse vs new (~60/40).** Genuine reuse: `landed_diff` wraps `validate_execution_evidence`
(`execution_evidence.py` — its hollow-done check already catches the "abandoned, zero diff" case);
`phase_coverage` composes `PhaseResult` + `_latest_execution_batch_all_tasks_done` (`chain:968`);
failure plumbing (`_record_lifecycle_failure`, `recoverable_via`, `PhaseResult.Deviation`) already exists.
**Genuinely new** (and two design-doc claims were *wrong* — corrected by the reuse agent):
- **Base-ref diff must be built** — `validate_execution_evidence` uses *working-tree* `git status`
  (`:121`), not `git diff base..HEAD`; no checkpoint exists. The contract needs a per-milestone base ref.
- **Worker-did-work signal is NOT in `cli_provenance`** (config-keys only); the real signal is delegate
  `tool_trace`/`api_calls` (`delegate_tool.py:286,358`) + `execution_batch_*.json`.
- **Green-suite** reuses only the `_capture_test_baseline` *runner*; the post-execute re-run + compare is new.
- **Declared-no-op / waiver artifact** is must-build-new (nothing structured exists today).

**The big cost is the test migration, not new infra.** ~30-45 test files need touching; ~20-30 need new
evidence-producing fixtures. 14 tests drive fake/stub workers to `done` with no diff and 0 tool calls
(they fail fail-closed immediately); 21 stub `review_verdict:"approved"`. Plan for this explicitly.

**Performance forces caching.** The suite is **~390s (6.5 min) for ~3197 tests**, and the existing
baseline runner already caps at 120s (would time out). So green-suite **must** run once per HEAD and
reuse execute's own final run (`verification/suite_run.json`), keyed on `baseline_head_sha` + file mtimes;
raise the cap to a configurable `test_command_timeout` (default 900s). Running the full suite at every
plan-done *and* milestone-done unguarded would add N×6.5min per chain — unacceptable.

**Roll out shadow → warn → enforce, per evidence class.** Add `completion_contract_mode`
(off/shadow/warn/**default shadow**) to `PlanConfig`/`ChainState`/`execution.*`. All modes compute and
persist `completion_verdict.json` from day one; graduate one evidence class to enforce at a time, in
order **worker_did_work → landed_diff → phase_coverage → green_suite** (cheapest/least-flaky first), when
the shadow false-positive rate is <2% on known-good runs.

**It subsumes the worktree-carry fix (finding #4).** Diff-scoping via a per-milestone
`milestone_base_sha = _branch_head(root)` (`chain/git_ops.py:461`) checkpointed at milestone start, then
`<milestone_base_sha>..HEAD`, isolates one milestone's commits even with prior commits carried in the
tree — which is exactly the m5a false-`needs_rework` cause. One mechanism, two findings closed.

**Anti-brittleness stays as designed:** honest no-op/docs-only/deferred passes via a *declared* typed
artifact; silent abandonment fails (no diff, no suite, no tool calls, no declaration). Override appends a
`waived` evidence ref — never mutates a failure into a pass. Fail-closed; failures surface loudly in
`megaplan status` + a `COMPLETION_VERIFICATION_FAILED` event.

**Build order:** base-ref-diff + worker-activity reader + green-suite-cache + no-op-waiver (the new pieces)
behind the shadow flag → run shadow on a few real plans → graduate per class → migrate tests alongside.

---

## C. Decision-skill fix — APPLIED

Edited `megaplan/data/decision_skill.md` (the real file behind the `megaplan-decision` skill symlink),
three surgical in-voice edits:
1. New bolded rule after the "one profile per sprint" line: **"The driver tier tracks decision DIFFICULTY,
   not stakes — especially behind an objective gate."** Behavior-preserving work behind a characterization/
   green gate defaults the driver to `solo`; a high-stakes *noun* doesn't raise the driver if the *decision*
   is "move code, keep behavior." Premium drivers reserved for genuine decision-difficulty / no-cheap-recovery.
2. Reconciled the split-signal line (`:41`): stakes raise the *gate/robustness*, not automatically the *driver*.
3. Promoted the buried tier-4 counter-guidance (`:84`): "high stakes alone don't justify a premium *driver*:
   behind a green gate, behavior-preserving work drops to `solo` regardless of the noun it touches."
Plus: split epics now tier *each milestone on its own difficulty*, not the riskiest in the chain.

This is the high-leverage fix — the over-tiering in this epic was a pure profile-*selection* error
(`solo` + the green gate were both available and unused), so better guidance removes it entirely. The
code-level per-phase difficulty wiring remains a separate, optional refinement for mixed-difficulty
single milestones.
