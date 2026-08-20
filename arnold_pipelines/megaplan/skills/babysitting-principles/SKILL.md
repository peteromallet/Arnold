---
name: babysitting-principles
description: >
  The operating philosophy for the fix-the-fixer / babysitting loop: the three
  layers of fixing (self-healing → automated fixer → fix the fixer), escalation
  on repetition, evidence-first, minimalism, per-epic branch lineage, cost
  discipline, the living evidence doc, and honest logging — plus the
  aspirational principles for harness improvements and the anti-principles that
  cause the most pain. Use when deciding HOW to fix a stalled chain/fixer, when
  escalating a repeated blocker, when improving the Arnold/megaplan harness, or
  when reviewing whether a gate/pin/check is overzealous. Includes the
  one-command status tools (fixer-status, epic-board).
---

# Babysitting Principles

How we run the fix-the-fixer / babysitting loop, and what the harness should
aspire to. Canonical source: `docs/babysitting-principles.md` in the Arnold
repo; this skill is the agent-facing form (same content, plus the tools).

---

## 1. The three layers of fixing

### 1.1 Self-healing wherever possible

The system should be programmatically self-healing first — before any agent is
involved. When something fails, the harness tries to recover on its own:
restart the chain, retry the phase, re-drive the stuck step. The goal is that
the thing heals itself, or at least tries to. Self-healing is the cheapest fix
and should always be attempted first.

### 1.2 The automated fixer fixes things

When self-healing isn't enough, the automatic fixer fixes the problem. It
watches the epics, notices when they stop running, understands why they
stopped, and repairs — investigating, shipping its own engine patches,
rebinding, and re-driving the chain. The fixer is the primary repair
mechanism; it should fix any stoppage, including itself.

### 1.3 Failing that, fix the fixer — never hand-fix the chain

When the fixer can't reach the root, the operator's job is to improve the
fixer so it can — never to rescue the chain directly. Fix the machinery, not
the instance. Direct implementation is only the last rung of the escalation
ladder, and even then it is *improving the fixer* (engine fixes the fixer can
ship), not hand-driving the chain. Hand-fixing the chain is forbidden: it
invalidates in-flight rebinds, re-blocks plans, and teaches nothing.

---

## 2. Operating principles

### 2.1 Escalate on repetition

When the same issue repeats — roughly the same class three times in a row, or
the chain stays blocked ~1 hour without autorecovery — escalate. Deploy a
swarm of DeepSeek Flash agents to understand the fixer's failure, feed that
evidence to a Codex/Grok sub-agent to think about the higher issue at play,
then improve the fixer and retrigger it. Keep looping until unblocked. The
escalation is about the fixer's failure to fix, not the chain's failure to
run.

### 2.2 Evidence first

Verify the root cause before shipping; the fix must reach the root, not the
symptom. Deploy swarms of DeepSeek sub-agents to gather precise evidence at
each stage — not just what happened, but the code, how it's doing it, and how
things are being passed around. Feed evidence packs to the oracle for the
once-and-for-all design. Never trust narrative over evidence; ask "does this
get to the root of why it failed?" before acting.

### 2.3 Minimalism

Remove overzealous bureaucracy rather than patch around it; bias toward
simplicity. Delete pins, gates, and layers that convert ordinary development
into blocks. Use the fewest moving parts that can disagree. Default-on for the
one intended flow; everything else is removed or deleted. If a check doesn't
protect a real invariant, it just makes change expensive — get rid of it.

### 2.4 The fixer edits the epic's own branch

Engine fixes are shared machinery, but lineage is per-epic. The fixer makes
its fixes on the epic's own branch (`fixer/<slug>-<date>`); the PR to main
happens at sprint end, with all fixes together. Never push engine fixes
straight to main mid-sprint.

### 2.5 Cost discipline

Flash does the work; strong models only for the hard core and the oracle.
Route by difficulty: easy work on cheap models, hard work on the strongest,
oracle decisions on high reasoning. Don't spend expensive reasoning on tasks a
flash agent can do.

### 2.6 Living evidence doc

Maintain a living document of every observed issue, fix, and oracle
assessment. Whenever the fixer resolves a real issue, ask: "Would completing
the current epic have prevented or resolved this? If not, what needs to
change?" Keep updating the epic and the fixer from this evidence.

### 2.7 The system should tell the truth

Honest logs, honest fixers. Logs must say what actually happens; typed errors
must distinguish real cases (e.g. "nothing to claim" vs "couldn't claim"); the
fixer states "movement not yet proven" rather than fabricating it. Every claim
must be verifiable against the live system.

---

## 3. Aspirational principles

### 3.1 What a good harness improvement looks like

1. **Minimal surface.** The best fix is often a deletion. Reduce the number of
   moving parts that can disagree; default-on for the one intended flow.
2. **Fail-closed only where load-bearing.** A gate should protect a real
   invariant — never just make change expensive. The test: does it protect a
   real property, or does it convert ordinary development into a block?
3. **Root fixes over band-aids.** "How do we prevent this ever happening
   again?" is the acceptance test. Explicitly reject fixes that mask the root
   cause (raise the cap, staple an index, async the gate).
4. **Immutable + migration-safe.** Content-addressed generations, CAS
   cutovers, shape-tolerant validators. Any shape change ships with a
   migration; old state must not become permanently invalid.
5. **Every consumer has a producer.** Every required env var has a builder;
   every failure producer leaves identity a reader can find; every contract
   has a test proving it.
6. **One enforcement point per invariant.** Consolidate ad-hoc checks into
   canonical loaders and gates. Duplicated enforcement points let the same
   defect hide in six places.
7. **Honest observability.** Logs say what happens; typed errors distinguish
   real cases; the fixer states "movement not yet proven" when it's true.
8. **Node-aware, not file-level; identity-scoped, not env-scoped.** Check the
   right granularity — the two deepest root causes were exactly this:
   file-existence instead of node-existence, and box-wide env instead of
   target-session identity.

### 3.2 What the system should aspire to

1. **Self-healing, fixer-first.** Success = the chain advances, not merely
   that the fixer diagnosed. The end-state: watchdog detects a stoppage →
   launches exactly one fixer → that fixer's goal drives evidence swarm →
   oracle → implement → relaunch → prove movement → the chain progresses to
   completion.
2. **The harness should make the fixer succeed.** Every gate, pin, and
   identity seam should be evaluated against one question: does this help the
   fixer fix, or does it give the fixer a new wall to climb? The best fixes
   are the ones that remove walls the harness built around the fixer.
3. **Evidence over narrative.** Every judgment call is fed with evidence packs
   (code + how things are passed around), not summaries.
4. **Immutable runtime + mutable lineage.** One coherent identity per epic
   (recorded == manifest == live import root == wrapper digest == dependency
   generation); divergences typed UNKNOWN, never green. The fixer's engine
   fixes live on the epic branch and reach main only through the sprint-end
   PR.
5. **Resume is idempotent on authority-completed units.** A worker may die at
   any point; the next resume continues from the last authority-accepted
   frontier, never restarting from batch 1.
6. **The fixer's own loop is observable and self-terminating.** Dedup (no
   relaunch storms), liveness timeouts for wedged agents, receipts at every
   stage, honest "movement not yet proven" — so a human can trust the loop
   without watching it, and the loop can be improved from its own evidence.

### 3.3 Anti-principles — what causes the most pain

1. **Overzealous gates** — pins that convert ordinary development into blocks
   (chain-spec hash pins, test budgets that don't fit the tests the planner
   wrote).
2. **Shape changes without migration** — schema changes that permanently
   invalidate existing state.
3. **Legacy bindings without bridges** — old state that can never advance to
   the new shape.
4. **Stateless-terminal assumptions** — one-shot phase-runners treated as
   supervisors; a live runner treated as "healthy" when the chain is actually
   stuck.
5. **Silent fallbacks and silent records** — absence = allow, fallback =
   silence, override = no memory.
6. **Log messages that lie** — a log that says "relaunched" when it returned
   1; one error kind conflating two different failures.
7. **Duplicated enforcement points** — the same invariant checked ad-hoc at
   every boundary instead of once.
8. **Contracts without producers** — required env vars with no builder;
   identity consumers with no writer.
9. **Big-file hiding** — huge files (multi-thousand-line scripts) let defects
   hide.
10. **Fabrication and premature claims** — a fix that passes tests but never
    populated the live path; a deploy that claims success before the box
    proves it. The antidote: verify against the live system, never trust a
    claim.

---

## Tools: one-command status

The campaign ships two status CLIs (in `tools/` in the Arnold repo, installed
on the box at `/usr/local/bin/`):

### `fixer-status [EPIC...]` — one chain + its fixer, in one go

Prints per epic: manifest gen/head · chain state/idx/done/plan/rev · plan
state/phase/worker/failure/events/cursor/raw error · seed readiness/revision +
gen match vs manifest · fixer log age + live hermes agents (with CPU) ·
watchdog procs.

```
fixer-status                        # all manifest-backed epics (box)
fixer-status megaplan-maintenance astrid-first   # specific epics
fixer-status --json [EPIC...]       # machine-readable
```

### `epic-board [board|deep]` — all epics everywhere, or deep-diagnose one

- `epic-board board` — every megaplan epic on the machine (local Mac +
  remote box), one line each: location, chain state, idx, done, plan, fixer
  liveness. `--json` for machine-readable.
- `epic-board deep <epic>` — full drill-down: chain rev · plan
  state/failure/cursor/raw error · seed readiness/revision + gen match ·
  manifest gen/head · engine head + recent commits · last 5 plan events ·
  fixer log tail (what the fixer is doing right now).

```
epic-board board
epic-board deep astrid-first
epic-board board --json
```

Local epic roots are configurable via `EPIC_BOARD_LOCAL_ROOTS` (colon-
separated; empty on the box so board shows only box epics there). The tools
detect in-container execution and skip the self-ssh.

---

*Living reference: keep updating with each new incident, each new direction,
and each improvement decision. Append to the principles — never let the
sources creep back in.*
