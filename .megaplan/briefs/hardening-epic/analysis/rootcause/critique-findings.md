# Root-cause: critique findings accrete instead of converge

Lens: **findings lifecycle**. Why FLAG-M2-001…017 piled up across 9 rounds.

## 1. How findings are represented & persisted

Per-round critic output is a `checks[]` list, each check carrying `findings[]`
with `flagged: bool` and `detail`. The single-check template is written/parsed in
`megaplan/orchestration/parallel_critique.py:50` (`write_single_check_template`)
and `:114-120` (must contain exactly one check). The aggregated payload is written
to `critique_v{N}.json` at `megaplan/handlers/critique.py:424`
(`atomic_write_json(plan_dir / critique_filename, worker.payload)`).

Flags themselves live in a **separate, cumulative registry** (`flags.json`),
not in the per-round critique file. Findings are *synthesized into flags* and
folded into that registry by `update_flags_after_critique`
(`critique.py:447` → `flags.py:211` → `_apply_flag_updates` `flags.py:111`).
`_synthesize_flags_from_checks` (`flags.py:72`) turns every `flagged` finding into
a flag whose id is the **check id** (`flags.py:98`:
`flag_id = check_id if len(flagged_findings)==1 else f"{check_id}-{index}"`).
Genuinely new free-form flags get monotonic ids via
`next_flag_number`/`make_flag_id` (`flags.py:13-23`, `:141-143`) — `FLAG-001`,
`FLAG-002`, … never reused.

Status fields: `FLAG_BLOCKING_STATUSES = {"open","disputed","addressed"}`
(`types.py:379`). A flag only stops blocking when it becomes `verified`
(set in `_apply_flag_updates` `flags.py:128-131` from `verified_flag_ids`) or
`accepted_tradeoff`/`gate_disputed` (`update_flags_after_gate` `flags.py:326-329`).

## 2. Is "zero open flags" ever a termination signal?

**No.** There is no convergence test on the flag set. Termination is decided
entirely by the gate's LLM `recommendation` (PROCEED/ITERATE/ESCALATE/TIEBREAKER)
in `_apply_gate_outcome` (`handlers/gate.py:294-368`). PROCEED→finalize requires
the gate model to emit a `flag_resolutions` entry per blocking flag
(`prompts/gate.py:115-118`); otherwise it returns `("...", "revise", ...)`
(`gate.py:360-361`). The only hard backstop on the loop is `max_iterations`
in `auto.py:1232` (`while iteration < max_iterations:`) and `auto.py:2232`
(`hit max_iterations`). Nothing observes "open flag count went to zero" as a stop.

## 3. Why NEW flags appear every round (the accretion engine)

The critic does **not** receive the open-flag set as "already-raised, don't
re-litigate." Each round it re-scans the whole plan fresh. The dedup that exists
is **id-keyed only**: in `_apply_flag_updates` `flags.py:147-153`, a finding that
lands on an *existing* id is merged and reset to `open`. But synthesized flag ids
are derived from `check_id` + a **positional index** (`flags.py:98`,
`finding`-enumeration `flags.py:89`). A *different* concern surfaced by the same
lens in round N+1 either lands at a new index (`check-2`, `check-3`) or, for
free-form flags, gets a brand-new `FLAG-0NN`. So a fresh observation from a lens
that already "passed" is a **new id → a new open flag**, with zero check against
prior resolved concerns. There is no semantic/text dedup at write time.

The only convergence machinery is *advisory prompt text*, not enforcement:
`compute_recurring_critiques` (`gate_signals.py:62-73`) intersects normalized
concern strings between consecutive critique files, and the evaluator's
differential block (`prompts/critique_evaluator.py:57-95`) tells the model
"do not re-litigate verified flags." Both are exact/Jaccard string heuristics
fed to an LLM that is free to ignore them — and they only damp re-raises of the
*same* concern, never the steady stream of *fresh* ones each lens emits.

The planner→flag feedback path exists (`update_flags_after_revise`
`flags.py:252-299` flips ids to `addressed`; evaluator verify block
`critique_evaluator.py:286-350` confirms `verified`/`open`), so prior flags *do*
get closed — but closing K old flags while the re-scan opens K+ new ones nets
out flat-or-worse. That is exactly the observed FLAG-M2-001→017 ramp.

## 4. Is there a "no net progress" detector?

**No.** `compute_iteration_pressure` / `has_mechanical_recurrence`
(`audits/iteration.py:111,143`) detect *reopened/recurring* groups, and
`build_gate_signals` warns at iteration ≥5 / ≥12 (`gate_signals.py:208-213`).
None of these compute **(new_flags_this_round) − (resolutions_this_round)** and
stop when it is ≥0 across consecutive rounds. The signal needed (per-round
resolved-count vs new-count) is computable from successive `flags.json` /
`critique_v{N}.json` diffs but is never derived.

**Where the fix belongs:** add a net-progress signal in
`megaplan/orchestration/gate_signals.py:build_gate_signals` (≈`:116-144`,
alongside `recurring`/`loop_summary`) — e.g. `new_flag_ids` vs
`newly_resolved_ids` between iteration N-1 and N — and consume it as a forced
ESCALATE/TIEBREAKER in the gate decision at
`megaplan/handlers/gate.py:_apply_gate_outcome:360` (don't let the LLM choose
ITERATE when net progress ≤ 0 for two consecutive rounds). Write-time semantic
dedup for synthesized flags belongs in `flags.py:_apply_flag_updates:139-163`.
