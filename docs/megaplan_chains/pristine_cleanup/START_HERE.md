# START HERE — Agent Kickoff: The Pristine Cleanup Epic

You're picking up a 9-milestone epic that takes VibeComfy from "structurally messy"
to **pristine**. It was scoped by a 10-agent audit and hardened by two independent
reviewers (Opus + Codex). The thinking is done. Your job is to **finish it — all of it.**

---

## Where everything lives

| Thing | Path |
|---|---|
| The chain spec (9 milestones) | `docs/megaplan_chains/pristine_cleanup/chain.yaml` |
| Full rationale, DAG, branch policy | `docs/megaplan_chains/pristine_cleanup/README.md` |
| Per-milestone briefs (M1→M7 + publish) | `docs/megaplan_chains/pristine_cleanup/ideas/*.md` |
| The raw 10-lens audit (your evidence) | `docs/megaplan_chains/pristine_cleanup/audit/01..10-*.md` |
| Handoff artifacts you'll produce | `docs/megaplan_chains/pristine_cleanup/artifacts/` |
| Project ground truth / conventions | `CLAUDE.md` and `AGENTS.md` (repo root) |
| Repo root | `/Users/peteromalley/Documents/reigh-workspace/vibecomfy` |

## How to run it

```bash
# One-time: branch off CLEAN main (NOT the in-progress agentic-port branch).
git branch megaplan/pristine-cleanup main

# Inspect without driving anything.
megaplan chain status --spec docs/megaplan_chains/pristine_cleanup/chain.yaml

# Single-step a milestone, inspect, repeat (recommended early).
megaplan chain start --spec docs/megaplan_chains/pristine_cleanup/chain.yaml --one

# Drive the whole chain.
megaplan chain start --spec docs/megaplan_chains/pristine_cleanup/chain.yaml
```

State persists under `.megaplan/plans/.chains/` — a crash or SIGINT loses nothing.
Re-run the same command to resume exactly where you stopped.

## The order, and why it's the order

```
M1 safety net → M2 shared utils (kernel) → M3 validation ┐
                                          → M4 eval/diag  ┘ → M5a emitter
                                                            → M5b session+errors
                                          → M6 code conventions → M7 docs → publish
```

- **M1 first, always.** The test suite is currently a liar (broken import, stub
  fixtures, 4-of-9 parity coverage). You repair it AND emit a concrete golden gate.
- **Consolidate before you split.** M3/M4 shrink the god-files; M5a/M5b carve what's left.
- **Docs dead last (M7),** so they describe a settled API, not a moving target.
- Only **M3 ∥ M5a** are truly independent. Everything else is a real dependency — respect it.

## The three rules you do not break

1. **The M1 golden gate is sacred.** `docs/audits/m1-safety-gate.md` is the bar every
   later milestone clears: full green pytest, CLI JSON snapshots, import-surface, 9/9
   parity. You do not advance a milestone that doesn't pass it.
2. **Behavior-preserving means byte-for-byte where tests assert it.** If a snapshot
   moves, you justify and re-bless it deliberately — you never "fix" a test to make red
   go green.
3. **`stop_chain` is a feature, not a failure.** If a milestone genuinely can't pass the
   gate, the chain halts and waits. Halting honestly beats shipping a silent regression.

---

## The screed

Read this when you hit the wall. You will hit the wall.

You are not here to *attempt* this cleanup. You are here to **complete it.** Nine
milestones. A 3304-line god-file that's been daring someone to touch it. Three
validation systems that quietly disagree. Eight copies of the same function pretending
they're different. A test suite that lies about being green. Every one of these is a
thing a previous pass looked at, flinched, and walked away from. **You are the pass that
doesn't walk away.**

When M3 fights you because the three validators diverged in ways the briefs didn't fully
predict — good. That divergence is *exactly* the rot you were sent to cut out. When the
emitter split in M5a throws a parity diff you don't understand — you don't suppress it,
you *understand it*, because understanding it is the entire job. When a test is red, you
do not delete the assertion. You do not `# type: ignore` the problem. You do not lower
the bar to meet your patience. **You raise your patience to meet the bar.**

Obstacles are not detours from the work. They *are* the work. The codebase got messy
because, every time, someone chose the shortcut. You are the answer to all of those
shortcuts at once. Bust through. Read the actual source. Verify every claim. Make the
gate green for *real*. Then take the next milestone. And the next. Until `publish-shared-branch`
runs and the whole thing is done — not "mostly done," not "done except for that one
flaky test," **done.**

The plan is airtight. The evidence is in `audit/`. The gate tells you the truth. All
that's left is someone relentless enough to carry it across all nine milestones without
blinking.

That's you. Go finish it. 🔨
