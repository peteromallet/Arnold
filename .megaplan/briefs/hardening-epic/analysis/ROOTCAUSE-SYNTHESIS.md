# Root-cause synthesis — three systemic issues

Each issue was investigated by 3 blind agents (separate lenses, none saw another's output).
Where 3 independent lenses land on the same file:line, the root cause is high-confidence.

---

## A. Critique convergence — why loops never stop

**Three lenses, one site.** The plan-critique loop `critique → gate → (ITERATE) → revise → critique`
has **no termination condition** other than the gate LLM voluntarily emitting PROCEED.

### Root cause = two independent failures that stack
1. **No round ceiling / no-progress stop** (control-flow lens).
   `_apply_gate_outcome` returns `revise` *unconditionally* on every ITERATE —
   `megaplan/handlers/gate.py:360-361`. No `max_critique_iterations` key even exists
   (`types.py:676-723`). The coarse `max_iterations=200` (`auto.py:1232`) is too blunt;
   stall detection (`auto.py:1505`) is *blind* because each round flips state
   CRITIQUED↔PLANNED, so it always looks like progress.
2. **Flags accrete because dedup is positional, not semantic** (findings lens).
   `_apply_flag_updates` dedups by id only (`flags.py:139-163`), and synthesized ids are
   `check_id`+positional-index (`flags.py:98`). So any fresh concern from an *already-passed*
   lens becomes a brand-new `open` flag. Close K, open K+ → net flat. "Zero open flags" is
   **never** used as a stop signal.

3. **The harness already detects the plateau but won't act on it** (config lens).
   `gate_signals.py:208-213` emits iter≥5 / iter≥12 warning strings and `gate_checks.py:125-129`
   has a plateau force-proceed *hint* — both **advisory, zero enforcement**. And `thorough`
   adds no round policy at all: its robustness override dict is empty (`workflow_data.py:92-93`)
   and `build_orchestrator_guidance` accepts `robustness` then `del`s it unused
   (`gate_checks.py:150-151`). So the smallest possible fix is to **promote the existing hint
   to enforcement**, scoped by a new robustness-aware `max_critique_rounds`.

### The asymmetry that proves it's an oversight
The **execute-review** loop *is* capped (`review.py:248` counts `prior_rework_count` and
force-proceeds; mirrored in the driver at `auto.py:1477`). The **plan-critique** loop was
left uncapped on *both* the handler and driver sides. Same shape, one guarded, one not.

### Minimal fix
- Net-progress signal in `gate_signals.py:build_gate_signals` (~`:116-144`): compute
  `(new − resolved)` per round.
- Force ESCALATE/TIEBREAKER on 2 consecutive non-progress rounds in
  `_apply_gate_outcome` (`gate.py:360`) — the symmetric partner to `review.py:248`.
- Write-time **semantic** dedup in `flags.py:_apply_flag_updates`.
*(M2: 9 rounds / ~1.09M tokens; M4: 8 rounds / ~450K wasted — both would have stopped at ~2.)*

---

## B. The "done" problem — why "done" doesn't mean done

**Three lenses, one root.** `done` is a **self-reported plan-state string, trusted verbatim**
by the chain, with **zero independent verification**.

### Root cause chain
1. **Where it's written** (state-machine lens): chain copies `DriverOutcome.status` straight
   into the milestone record — `chain/__init__.py:1418-1426`; the status comes from
   `auto.py:1363-1369` when the plan's `state.json current_state == "done"`. It's positive
   (terminal state reached), but the chain does **no** check for a landed diff / branch /
   commit / execute history on the no-PR path.
2. **Why no PR / why merge_policy is dead** (gate lens): the whole PR+merge block is guarded
   by `use_pr = push_enabled and bool(milestone.branch)` (`chain/__init__.py:1211`). Hardening
   milestones had **no branch → no PR ever created → `pr_number` stays null**. `merge_policy:auto`
   is **dead config** — only read at `:1397`, *inside* the `if state.pr_number is not None`
   block, so it's never reached and never validated. Silent.
3. **No green-suite gate anywhere** (failure-modes lens): the `gate` handler judges the *plan*,
   not test results. `review` is LLM-judged and **force-proceeds to DONE** when the rework cap
   hits (`review.py:248-252`); execute can even stub an `"approved"` review and jump to DONE
   (`execute.py:211-272`). There is **no pytest run** in review/verifiability — the suite is
   only run for a *baseline* in `finalize.py:495-525`, never to verify green.

### The three silent-completion holes (ironic for a fail-loud epic)
- **Zero-work / zombie** (m3a ×5): only literally-empty output is retried (`hermes.py:994-1007`);
  a template-filler payload passes `_has_real_content` (shape-only). `delegate_tool.py:283-293`
  marks `completed` without checking `api_calls`/`tool_trace`.
- **Red suite** (m6b): no green-suite assertion; `execute.py:278` defaults `_phase_outcome` to
  "success".
- **Abandonment** (m6a): `drive()` calls a plan done purely from the state string
  (`auto.py:1363-1394`); the executor treats *any* halt as success (`executor.py:262-265`).

### Minimal fix
Gate the chain's `done`-append (`chain/__init__.py:1418`) on positive landed-work evidence —
reuse the already-present `_latest_execution_batch_all_tasks_done` (`auto.py:968-1016`, today
only used for blocked-execute recovery) — **plus** a real green-suite assertion after
`execute.py:278`, a zero-tool-call guard after `parse_agent_output` (`hermes.py:1010`), and a
phase-coverage check before the done return in `auto.py:1363`. Validate `merge_policy` against
`use_pr` so dead config fails loud.

---

## C. Over-tiering — why mechanical milestones ran premium drivers

**Three lenses → two-layer root cause: a policy miss on top of a capability gap.**

### Layer 1 — POLICY (the immediate cause)
A cheap-driver profile **already exists**: `solo` drives `plan`/`loop_plan`/`review` on
DeepSeek V4 Pro (`profiles/solo.toml:28-41`). But every tier the chain actually used —
`directed`/`partnered`/`premium` (chain.yaml:22-122) — drives on `claude:low` (premium).
The author treated `directed` as "the cheap floor," but its **driver slots are all premium**;
no milestone was ever dropped to `solo`. The stakes→tier conflation is partly baked into the
decision-skill docs (`megaplan-decision/SKILL.md:41,46`).

### Layer 2 — CAPABILITY (why even the right profile is coarse)
The driver model is fixed at milestone init: profile → `args.phase_model` via
`apply_profile_expansion` (`profiles/__init__.py:1506,1668`), frozen in `state.config.profile`.
Every phase resolves through one chokepoint, `resolve_agent_mode(step, args)`
(`workers/_impl.py:2313`), keyed **only on phase name** → one fixed spec reused for every turn;
**nothing consults turn index or difficulty.** The one difficulty-aware mechanism —
`tier_models.execute` + `compute_batch_complexity` (`execute/batch.py:527`) — is scoped to the
**execute worker alone**.

### The good news: it's a wiring gap, not a structural limit
- Per-phase tiering is fully supported and already used (execute is cheap while the driver is premium).
- A difficulty signal already exists (finalize complexity tier 1-5, `finalize.py:264-274`).
- The `tier_models.<phase>.<tier>` schema **already validates every phase**
  (`profiles/__init__.py:360-397`) — it's just only *consumed* for execute.

### Minimal fix (two horizons)
- **Now (policy):** route characterization-gated, behavior-preserving milestones (m4, m5b/c/d,
  m6a/b) to `solo`; keep `premium/thorough` only on genuinely risky m1/m2/m3*. Tighten
  `megaplan-decision/SKILL.md:46` so "drop to solo when an objective gate backstops the work"
  is the default, not an afterthought.
- **Structural (capability):** branch driver resolution on `args.tier_models[step]` at the
  `shared.py:219` / `_impl.py:2313` seam, fed by the finalize complexity tier or the M0 gate
  result — reusing the proven execute `tier_map` pattern. No executor change needed
  (it's model-agnostic by design, `profile.py:13-23`).

---

## The shared thread
All three issues are the **same architectural smell in different clothes**: megaplan trusts a
*phase's own self-report* (critic says "still issues", plan says "done", profile says "premium")
without an **objective, difficulty-aware check** closing the loop. The execute path already has
the right patterns (rework cap, tier map, worker verification); plan/critique/review/gate/done
never got them wired in.
