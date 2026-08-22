# Babysitting Principles

How we run the fix-the-fixer / babysitting loop, and what the harness should aspire to.

---

## 1. The hourly check-in

The babysitting loop runs as a **once-per-hour check-in**. Each check-in is one pass over the live system: **check → fix → push → re-arm**. It never just reports — every check-in ends with the run measurably closer to done or a concrete blocker fixed at the root. (Acute stoppages between check-ins are caught by the status-trigger path — see the `babysitter` skill.)

### 1.1 Check for failures and repeated misses

- Pull the live status with the one-command tools (`fixer-status`, `epic-board`) and read the living evidence doc (§3.6).
- For every stopped/failed/stalled chain, ask: **is this a repeated failure class the fixer isn't fixing, or isn't getting around to?** Same failure fingerprint roughly three times in a row, or a chain blocked ~1 hour without autorecovery, is the trigger.
- This question targets the **fixer's failure to fix**, not the chain's failure to run.

### 1.2 The fixing loop — bias toward fixing the fixer

When something is stuck or a failure class repeats, run the loop entirely inside sub-agents:

1. **Understand** — deploy a bounded, read-only swarm of DeepSeek Flash sub-agents over the failure evidence (what happened, the code path, how state is passed around) — `skills/subagent-launcher/fan.py`.
2. **Recommend** — hand the packed context (evidence pack, swarm index, every investigator report) to a premium model — **Grok** — for the once-and-for-all recommendation.
3. **Implement** — with DeepSeek Flash, fix the fixer itself (its prompt, its dispatch, its config) in the approved editable runtime — the chain-level fix is what the fixer does once it runs again. Verify against the focused regression.
4. **Relaunch the fixer** — the deliverable of the loop is the fixer running again with the fix in place: restart the fixer (and, when the evidence requires, the chain via megaplan resume / chain start); never `--fresh`.
5. **Verify at the next check-in** — the next hourly check-in checks whether and how the fixer actually fixed the chain: `chain-*.json` `last_state` leaves blocked and the same `failure_fingerprint` does not recur. A PID, commit, self-report, or heartbeat is NOT proof.

Stand down cleanly when nothing is actually blocked/failed, or when another fixer already owns the occurrence — never invent work.

### 1.3 Extreme intervention — fix the megaplan code itself

When the check-in finds the **fixer itself** stuck for structural reasons — a higher-level problem, e.g. its prompt is missing, its engine/dispatch is broken, it cannot even attempt the loop — the last rung is fixing the actual megaplan code itself, so the machinery the fixer runs on is actually fixed:

1. DeepSeek Flash sub-agents swarm the fixer's own failure evidence.
2. **Grok sense-checks** the plan — one or two passes via the sub-agent launcher — before any change.
3. DeepSeek implements the fix directly in the megaplan source (the engine, the harness, the fixer's own code), not just the chain.
4. Relaunch the fixer and prove it now makes movement.

This is still *improving the machinery*, never hand-driving the chain: the extreme tier fixes the actual megaplan code itself so the fixer (and future chains) work. Hand-fixing the chain remains forbidden (§2.3).

### 1.4 Loop mechanics

- **Re-arm** — schedule the next check-in in one hour; tear the loop down only when the whole run is genuinely done (all milestones complete / job exited success).
- **No questions** — a check-in never asks the operator anything. Decide every blocker, prefer the reversible option, log the decision + rationale in the check-in report so it can be audited later.
- **Verify, don't trust** — on any "done", check the work actually landed (files/commits/merged content), not the status word.
- **Fix the engine, not just the run** — when a stall traces to a harness/engine defect, fix it in the engine source (with a test) so it never recurs; ticket what you can't fix on the spot.

---

## 2. The three layers of fixing

### 2.1 Self-healing wherever possible

The system should be programmatically self-healing first — before any agent is involved. When something fails, the harness tries to recover on its own: restart the chain, retry the phase, re-drive the stuck step. The goal is that the thing heals itself, or at least tries to. Self-healing is the cheapest fix and should always be attempted first.

### 2.2 The automated fixer fixes things

When self-healing isn't enough, the automatic fixer fixes the problem. It watches the epics, notices when they stop running, understands why they stopped, and repairs — investigating, shipping its own engine patches, rebinding, and re-driving the chain. The fixer is the primary repair mechanism; it should fix any stoppage, including itself.

### 2.3 Failing that, fix the fixer — never hand-fix the chain

When the fixer can't reach the root, the operator's job is to improve the fixer so it can — never to rescue the chain directly. Fix the machinery, not the instance. Direct implementation is only the last rung of the escalation ladder, and even then it is *improving the fixer* (engine fixes the fixer can ship), not hand-driving the chain. Hand-fixing the chain is forbidden: it invalidates in-flight rebinds, re-blocks plans, and teaches nothing.

---

## 3. Operating principles

### 3.1 Escalate on repetition

When the same issue repeats — roughly the same class three times in a row, or the chain stays blocked ~1 hour without autorecovery — the hourly check-in fires the fixing loop (§1.2): a swarm of DeepSeek Flash agents to understand the fixer's failure, Grok for the recommendation, then improve the fixer and retrigger it. Keep looping until unblocked. The escalation is about the fixer's failure to fix, not the chain's failure to run.

### 3.2 Evidence first

Verify the root cause before shipping; the fix must reach the root, not the symptom. Deploy swarms of DeepSeek sub-agents to gather precise evidence at each stage — not just what happened, but the code, how it's doing it, and how things are being passed around. Feed evidence packs to the oracle for the once-and-for-all design. Never trust narrative over evidence; ask "does this get to the root of why it failed?" before acting.

### 3.3 Minimalism

Remove overzealous bureaucracy rather than patch around it; bias toward simplicity. Delete pins, gates, and layers that convert ordinary development into blocks. Use the fewest moving parts that can disagree. Default-on for the one intended flow; everything else is removed or deleted. If a check doesn't protect a real invariant, it just makes change expensive — get rid of it.

### 3.4 The fixer edits the epic's own branch

Engine fixes are shared machinery, but lineage is per-epic. The fixer makes its fixes on the epic's own branch (`fixer/<slug>-<date>`); the PR to main happens at sprint end, with all fixes together. Never push engine fixes straight to main mid-sprint.

### 3.5 Cost discipline

Flash does the work; strong models only for the hard core and the oracle. Route by difficulty: easy work on cheap models, hard work on the strongest, oracle decisions on high reasoning (Grok for the recommendation and sense-checks, §1.2–1.3). Don't spend expensive reasoning on tasks a flash agent can do.

### 3.6 Living evidence doc

Maintain a living document of every observed issue, fix, and oracle assessment. Whenever the fixer resolves a real issue, ask: "Would completing the current epic have prevented or resolved this? If not, what needs to change?" Keep updating the epic and the fixer from this evidence.

### 3.7 The system should tell the truth

Honest logs, honest fixers. Logs must say what actually happens; typed errors must distinguish real cases (e.g. "nothing to claim" vs "couldn't claim"); the fixer states "movement not yet proven" rather than fabricating it. Every claim must be verifiable against the live system.

---

## 4. Aspirational principles

### 4.1 What a good harness improvement looks like

1. **Minimal surface.** The best fix is often a deletion. Reduce the number of moving parts that can disagree; default-on for the one intended flow.
2. **Fail-closed only where load-bearing.** A gate should protect a real invariant — never just make change expensive. The test: does it protect a real property, or does it convert ordinary development into a block?
3. **Root fixes over band-aids.** "How do we prevent this ever happening again?" is the acceptance test. Explicitly reject fixes that mask the root cause (raise the cap, staple an index, async the gate).
4. **Immutable + migration-safe.** Content-addressed generations, CAS cutovers, shape-tolerant validators. Any shape change ships with a migration; old state must not become permanently invalid.
5. **Every consumer has a producer.** Every required env var has a builder; every failure producer leaves identity a reader can find; every contract has a test proving it.
6. **One enforcement point per invariant.** Consolidate ad-hoc checks into canonical loaders and gates. Duplicated enforcement points let the same defect hide in six places.
7. **Honest observability.** Logs say what happens; typed errors distinguish real cases; the fixer states "movement not yet proven" when it's true.
8. **Node-aware, not file-level; identity-scoped, not env-scoped.** Check the right granularity — the two deepest root causes were exactly this: file-existence instead of node-existence, and box-wide env instead of target-session identity.

### 4.2 What the system should aspire to

1. **Self-healing, fixer-first.** Success = the chain advances, not merely that the fixer diagnosed. The end-state: watchdog detects a stoppage → launches exactly one fixer → that fixer's goal drives evidence swarm → oracle → implement → relaunch → prove movement → the chain progresses to completion.
2. **The harness should make the fixer succeed.** Every gate, pin, and identity seam should be evaluated against one question: does this help the fixer fix, or does it give the fixer a new wall to climb? The best fixes are the ones that remove walls the harness built around the fixer.
3. **Evidence over narrative.** Every judgment call is fed with evidence packs (code + how things are passed around), not summaries.
4. **Immutable runtime + mutable lineage.** One coherent identity per epic (recorded == manifest == live import root == wrapper digest == dependency generation); divergences typed UNKNOWN, never green. The fixer's engine fixes live on the epic branch and reach main only through the sprint-end PR.
5. **Resume is idempotent on authority-completed units.** A worker may die at any point; the next resume continues from the last authority-accepted frontier, never restarting from batch 1.
6. **The fixer's own loop is observable and self-terminating.** Dedup (no relaunch storms), liveness timeouts for wedged agents, receipts at every stage, honest "movement not yet proven" — so a human can trust the loop without watching it, and the loop can be improved from its own evidence.

### 4.3 Anti-principles — what causes the most pain

1. **Overzealous gates** — pins that convert ordinary development into blocks (chain-spec hash pins, test budgets that don't fit the tests the planner wrote).
2. **Shape changes without migration** — schema changes that permanently invalidate existing state.
3. **Legacy bindings without bridges** — old state that can never advance to the new shape.
4. **Stateless-terminal assumptions** — one-shot phase-runners treated as supervisors; a live runner treated as "healthy" when the chain is actually stuck.
5. **Silent fallbacks and silent records** — absence = allow, fallback = silence, override = no memory.
6. **Log messages that lie** — a log that says "relaunched" when it returned 1; one error kind conflating two different failures.
7. **Duplicated enforcement points** — the same invariant checked ad-hoc at every boundary instead of once.
8. **Contracts without producers** — required env vars with no builder; identity consumers with no writer.
9. **Big-file hiding** — huge files (multi-thousand-line scripts) let defects hide.
10. **Fabrication and premature claims** — a fix that passes tests but never populated the live path; a deploy that claims success before the box proves it. The antidote: verify against the live system, never trust a claim.

---

*Living reference: keep updating with each new incident, each new direction, and each improvement decision. Append to the principles — never let the sources creep back in.*
