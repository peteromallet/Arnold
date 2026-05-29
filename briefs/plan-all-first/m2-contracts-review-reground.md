# M2 — plan-all-first: execution-ready contracts + review + reground

Sprint 2 of the plan-all-first epic. Design of record:
`briefs/plan-all-first-epic-mode.md` (see "Review findings" — this sprint is
build-order steps 3–5). **Depends on M1** (two-pass plumbing + durability) being
merged. Sizing: `partnered`, `full`, depth `high`, `--with-prep`.

## Outcome
Make plan-all-first plans **genuinely executable for tightly-coupled epics** by
adding (a) structured cross-milestone interface contracts, (b) a human review
surface, and (c) an execute-time reground gate. Without these, a milestone planned
in advance against an upstream milestone's *plan* (not its built code) drifts from
reality at execute time and is net-negative. A reviewer checks: a `plan_only` run
of a coupled fixture produces interface contracts in each plan, a `review.md` that
flags seam mismatches, and prep/plan that reads upstream contracts without choking
on not-yet-built code; and the reground gate catches a forced upstream divergence.

## Scope (IN)
- **Provides/Assumes contract.** Finalize emits a structured block (in `final.md`
  and/or a `contract.json` sidecar) per milestone: **Provides** = interfaces /
  paths / signatures this milestone commits to create; **Assumes** = upstream
  interfaces it depends on, copied verbatim from the upstream's Provides. Loose
  milestones have an empty Assumes — no special path. Siblings then agree by
  construction instead of inventing incompatible APIs against loose prose.
- **Cross-milestone context injection.** When planning milestone N under
  `plan_only`, inject prior milestones' **Provides** blocks into prep + plan. Force
  a summary of each `depends_on` upstream as a **seeded prep research area** (reuse
  triage's "production-of-an-artifact is a research area" precedent) — do NOT leave
  it to triage's minimization bias, which will otherwise skip exactly the context
  the planner most needs. Remaining upstreams are offered as optional pointers.
- **Mode-conditioned prep/plan/critique prompts.** Under `plan_only`, invert the
  pervasive "inspect the repo / ground against the tree" instructions to:
  *"upstream milestones are planned-not-built; read their Provides, do not expect
  their code in the tree."* Partition the prep cross-reference
  (`_cross_reference_prep_output`) so upstream paths are classified
  **"to-be-built-by-<milestone>"**, NOT `missing_files` (today every milestone that
  correctly references upstream gets penalized as having dangling references).
  Critique/gate must treat criteria referencing upstream-provided interfaces as
  **deferred-verification**, not unverifiable defects.
- **Chain-level `review.md`.** Generated after the planning pass: a table of
  Provides→Assumes across all milestones, flagging mismatches (an Assumes with no
  matching upstream Provides; signature/path divergence). This is the operator's
  decision surface — the thing that makes "review before spend" real instead of a
  crawl across N separate `final.md`s.
- **Reground gate.** Before each milestone's execute pass, diff its **Assumes**
  against the upstream's **actual committed** Provides (or exported symbols). On
  material drift: halt-for-human or auto-trigger `override replan` for that one
  milestone. **MVP-mandatory for any milestone with a non-empty `depends_on`.**

## Locked decisions
- The contract lives with `final.md` (written by `finalize.py`); the contract block
  is additive and inert when not in `plan_only` mode.
- `review.md` is a chain-level artifact produced after the planning pass.
- The reground gate reuses the existing `override replan` transition
  (`workflow_data.py:~69/73`) for the heavy path; this sprint builds the
  **detection** (Assumes-vs-actual diff) + the halt/auto-replan decision, not a new
  replan mechanism.
- Forced upstream summary is a seeded triage area, not a triage-optional candidate.

## Open questions (planner resolves)
- The exact contract schema: structured markdown section vs `contract.json`
  sidecar; how interface signatures are represented for machine comparison.
- What counts as "material drift" for the reground gate (missing symbol vs
  signature change vs moved path) and the halt-vs-auto-replan threshold.
- How the cross-reference partition determines which paths are
  "to-be-built-by-<milestone>" (from upstream Provides? from `depends_on`?).
- Whether mode-conditioning is a separate prompt-template variant or an injected
  context section alongside the existing prompts.

## Constraints
- Must compose with M1's two-pass plumbing (M1 merged first).
- Default (non-`plan_only`) runs MUST be unaffected: no Provides/Assumes
  requirement, no prompt changes, no reground when not in `plan_only`. A contract
  block MAY be emitted always, but must be additive-only and inert by default.
- The review surface must let a human catch seam mismatches across 8+ milestones at
  a glance, not by reading every plan in full.

## Done criteria
- A `plan_only` run of a **3-milestone fixture with a real interface dependency**
  (M-b consumes an interface M-a Provides) produces: Provides/Assumes blocks in
  each `final.md`; a `review.md` that surfaces the M-a→M-b edge; and prep/plan that
  reads upstream Provides WITHOUT flagging upstream paths as `missing_files`.
- A deliberately **mismatched Assumes** (references an interface no upstream
  Provides) is flagged in `review.md`.
- The reground gate, given an upstream whose actual output diverged from its plan
  (forced in the fixture), halts or replans the affected downstream milestone.
- Default-mode regression: a normal `chain start` / single `init` run is unaffected
  in prompt and finalize behavior (or a test asserts the contract block is
  additive-and-inert by default).

## Touchpoints
- `megaplan/handlers/finalize.py` (~613 `final.md` write; ~626 state) — emit
  Provides/Assumes.
- `megaplan/prompts/planning.py` (plan ~296; prep ~363; triage ~411; research
  ~472) — mode-conditioned variants + Provides injection + seeded upstream-summary
  area.
- `megaplan/prompts/_shared.py` (~188 `_render_prep_block`).
- `megaplan/orchestration/prep_research.py` (~452 `_cross_reference_prep_output`;
  ~446 `_gap_notes`; ~411 triage skip bias; `PREP_AREA_CAPS` ~46) — partition
  exists-now vs to-be-built; seed the upstream-summary area.
- `megaplan/chain/__init__.py` — inject prior Provides into `_init_plan`; generate
  `review.md` after the planning pass; reground gate before each milestone's
  execute.
- critique/gate handlers — deferred-verification classification under `plan_only`.
- `megaplan/_core/workflow_data.py` — `override replan` transition (reused,
  ~69/73).

## Anti-scope
- Do NOT re-implement M1's plumbing (two-pass mode, finalized outcome, durability).
- Do NOT change default-mode prompts/finalize beyond an additive, inert-by-default
  contract block.
- Do NOT build a general static-analysis / interface-extraction engine — scope
  reground detection to the Provides/Assumes contract diff.
- Do NOT add new model-routing tiers.
