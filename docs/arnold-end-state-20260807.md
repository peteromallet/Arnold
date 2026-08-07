# Arnold end-state — what the plan achieves

**Updated:** 2026-08-07 (UTC)
**Status:** target state. Not yet realized. Every doc in this set (`runtime-and-fixer-unification-design-20260807.md`, `megaplan-reference-architecture-20260807.md`, `megaplan-fixer-briefing-20260807.md`, `branch-cleanup-judgment-20260807.md`, `branch-cleanup-action-plan-20260807.md`) is a step toward this end-state.

---

## One-line mission

> **One base, one fast fixer anchored to the true design, recoverable everywhere, deployed by generation-switch, cleaned only when proven safe — so megaplan becomes a self-healing system that never loses work and always moves durably forward.**

---

## The end-state in one picture

Megaplan becomes a self-healing, evidence-backed operating system for shipping — where the fixer is a fast worker anchored to a true design, the code it edits is always recoverable, and nothing is ever silently lost.

Five properties hold simultaneously:

### 1. One source of truth, one base
- `origin/main` (general code), `origin/editible-install` (deploy mirror), and the active epic line are the **only** durable keep lines.
- The 114 orphaned runtime trees are gone — replaced by a small set of per-epic **worktrees** (shared objects, ~free) with their **own venv**, each recorded in a `runtime-manifest.json`.
- "What's running" has one answer, not three trees on three commits.

### 2. The fixer is a fast, anchored worker
- A single seam — `arnold-repair-loop --mode=reactive|proactive` — handles both on-failure and hourly backup.
- Default path is a **bounded investigator→executor**; the **swarm→corps→executor** pipeline (and Codex as planner) fires only on ambiguity/hard cases.
- **DeepSeek Flash runs it**, *having earned* the role on a replay benchmark rather than by assumption.
- Every prompt it sends (to Codex, to subagents) **carries the intended-design briefing** — so it reasons against how megaplan *should* work, never its drifted shape.

### 3. Everything is recoverable, and deletion is safe
- The box-only commits are on origin + bundled + clean-room-restore-drilled.
- The bundle restores a **runtime**, not just git objects.
- Deletion happens only through `close` → `gc-sweep` (closed + restore-proven), never by inferring "stale."
- The scheduler runs on a healthy systemd timer, not an ad-hoc loop.

### 4. Deploy is generation-switched, not edit-in-place
- You still edit your per-epic editable install — but the thing that *runs* is an **immutable release generation** built from a candidate, verified separately, then switched atomically with the previous generation retained.
- No mixed-version execution, and rollback always exists.
- The "shadowed bind-mount edits nothing" trap is impossible because edits are content-attested.

### 5. The machinery self-checks against its own design
- Custody, leases, evidence, gates all enforce: evidence beats prose; one owner only; no competing fixers; durably move the chain; surface structural issues to the ticket.
- The fixer's own prompts are validated against the reference architecture, so a fixer that starts patching the broken shape of the system instead of restoring the intended shape gets caught.

---

## What it achieves (the "why")

- **Not losing the thing that works.** The running code is no longer one fragile box away from oblivion.
- **Cheap, safe iteration.** New epics cost a worktree + venv, not a 1.9G clone and a naming gamble. Old epics get cleaned up *because* deletion is proven-safe.
- **Trustworthy autonomy.** "Done" means evidence-verified durable movement, not a heartbeat or self-report. The fixer can fan out to a swarm for hard cases and have Codex plan, without any actor silently lowering the bar.
- **The system converges toward its design.** Because fixers and planners are anchored to the intended architecture, drift stops being self-reinforcing — each fix restores the design instead of entrenching the deviation.

---

## Doc map (how each gets us here)

| Doc | Role toward the end-state |
|---|---|
| `megaplan-reference-architecture-20260807.md` | the intended design fixers/planners anchor to |
| `megaplan-fixer-briefing-20260807.md` | the compact briefing every fixer prompt carries |
| `runtime-and-fixer-unification-design-20260807.md` | the phases (0–6) to build the base + unified fixer + deploy contract |
| `branch-cleanup-judgment-20260807.md` | gpt-5.6-sol's merge/delete verdict on the current mess |
| `branch-cleanup-action-plan-20260807.md` | the mechanical cleanup Flash executes with Codex sense-checks |
| `branch-cleanup-agent-brief-20260807.md` | the operating brief given to the Flash agent before it starts the cleanup |
