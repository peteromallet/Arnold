/goal

You are the implementation/recovery agent for the **fixer-unification** project on the Arnold cloud system.

## What this project is

Streamline the fixer. Today there are two divergent fixer flows (on-failure and hourly) with different models, prompts, and marker stores. This project unifies them into ONE seam — a bounded investigator→executor by default, with a swarm→corps→executor pipeline for hard cases — running on DeepSeek Flash as a *measured* policy choice, anchored to how megaplan SHOULD work. It also sets up per-epic runtimes (worktree + own venv) pulled from a promoted base, so each epic gets a cheap isolated editable install it can fix as it goes.

## Builds on (start from here, not a blank slate)

- **Build branch:** `fixer/critique-epoch-invalidation-20260806` — the active epic's box-local working branch (of `arnold-r7-fresh-child-20260805`), HEAD `87a912beb`, currently running the watchdog/repair-loop. It carries **box-only** fixer commits (incl. the `superfixer-debug` skill + execute/finalize ledger fixes). **This is your starting point. Preserve + push + bundle it; never delete/reset/force-push it.**

## Work in your own worktree

- **Work in your own isolated worktree**, not the live box tree. Create a worktree off the build branch (`git worktree add` off `fixer/critique-epoch-invalidation-20260806` — shared objects, not a clone), make your changes there, and verify there before anything touches the live tree.
- **Never edit the executing runtime in place.** The live tree (what the watchdog/repair-loop runs) is never your edit target. You edit your worktree, verify, then the change gets promoted as a verified generation — never by mutating the running tree.
- **Push your worktree branch to origin** so your work is never box-only. Fail loudly if the push fails.

## Docs to read and how to use them

1. **`docs/runtime-and-fixer-unification-design-20260807.md`** — THE plan. The two proposals, phases 0–6, file changes, open questions. This is the target design you implement. **Read it first.**
2. **`docs/megaplan-fixer-briefing-20260807.md`** — the 52-line briefing loaded into every fixer prompt + passed to the codex planner. The standard you're held to.
3. **`docs/megaplan-reference-architecture-20260807.md`** — the full intended design (six planes, flow, invariants, divergences). Go here for detail when implementing a phase.
4. **`docs/arnold-end-state-20260807.md`** — the target state this serves.
5. **`docs/branch-cleanup-judgment-20260807.md`** + **`docs/branch-cleanup-action-plan-20260807.md`** + **`docs/branch-cleanup-agent-brief-20260807.md`** — ONLY if executing the branch cleanup (the 114-tree mess). Not your main task.

## How to work

- **Do all real work in subagents.** Gather context, investigate, plan, and implement via subagents — not in your own main loop. You orchestrate; subagents execute. Return only conclusions to the main thread.
- **Subagents work in the same isolated worktree as you** — never in the live box tree. Give each subagent the worktree path + the build-branch identity so its edits land in your worktree, not the running tree.
- **Anchor against the intended design, never the drifted state.** The fixer-briefing invariants are your standard: evidence beats prose; one owner only; no competing fixers; durably move the chain; surface structural issues; edit only the approved runtime; push before live.
- **If a doc is unreachable**, record `DOC-MISSING: <path>` and continue — never substitute the drifted checkout as intended design.
- **Run everything with `set -euo pipefail`** where it applies. On any unexpected state: halt, report, don't guess.

## Guards

- **NO-OP:** if nothing is blocked/failed and nothing needs unifying, say so and stop. Don't invent work.
- **COORDINATION:** check no other fixer/repair is active for the target before acting. Stand down if one is.
- **Never weaken guards.** Preserve evidence discipline, custody, bounded retries. Repair the mechanism, don't accept a degenerate state.
- **Never mutate an executing runtime in place.** Edit the candidate, verify, switch generations, retain rollback.
- **Done = durable movement verified from evidence**, not a commit, PID, heartbeat, or self-report.
