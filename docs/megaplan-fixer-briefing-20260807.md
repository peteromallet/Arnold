# Megaplan fixer briefing — launch prompt

**Generated:** 2026-08-07 (UTC) — by gpt-5.6-sol. Loaded into the DeepSeek Flash fixer prompt and passed to the codex planner at the start of every fixer run.

---

## How to use this doc pack

You are given a **set of docs**, not just this one. Use them in this order:

1. **This briefing** — read first. It's the 2-minute orientation: what megaplan is, where you fit, what "done" means.
2. **`megaplan-reference-architecture-20260807.md`** — when you need the full detail behind anything here (the six planes, the exact phase ladder, the intended flow, all invariants). Read the section you need, not the whole thing.
3. **`runtime-and-fixer-unification-design-20260807.md`** — when a fix touches how runtimes, the fixer, or deployment are supposed to be structured. This is the *target design* — the system you're helping converge toward.
4. **`branch-cleanup-judgment-20260807.md`** + **`branch-cleanup-action-plan-20260807.md`** — ONLY if you are executing the branch cleanup (they are the cleanup's why + how).

**Ground rules for using these docs:**
- **Anchor against the intended design, not the drifted state.** Always reason against the six-plane architecture and the fixer invariants below. The "current divergence" section lists how the box *differs* from intent — treat that as drift to fix, never as the design.
- **If a doc is unreachable**, record `DOC-MISSING: <path>` in your report for the operator — never silently use the drifted checkout as the intended design.
- **When in doubt, the design doc wins over a stale assumption.** If this briefing or any doc contradicts `runtime-and-fixer-unification-design-20260807.md`, the design doc is the target.

---

## Mission

Megaplan turns committed briefs into durably executed, independently verified work — without letting any model silently lower the bar.

## Six planes (at a glance)

- **Chain runner** — drives each plan through `prep → plan → critique → gate → revise → finalize → execute → review → done`, and orders bigger work through `chain.yaml` milestones.
- **Custody** — gives each piece of work one content-addressed lease/epoch, and double-fences every authority-increasing action against durable state.
- **Resident** — the always-on operator (converse, schedule, delegate, deliver). Not the runner, watchdog, or deployer.
- **Fixer stack** — watchdog → singleton L1 repair → L2/L3 meta-repair → progress audit. Each layer checks the one below.
- **Cloud runtime** — runs from one promoted, immutable base. Editable engine fixes travel through the single durable base path.
- **Evidence and gates** — journals, step receipts, proof maps, manifests, validation receipts turn every transition and completion into a re-verifiable claim.

## The flow

- **Normal:** the `auto` driver advances persisted state. Frontier models own judgment; cheaper models own volume work. Each guarded phase writes evidence before the next begins.
- **Failure:** the driver fails closed with `resume_cursor` + retry strategy. The watchdog classifies the authoritative nonterminal condition and enqueues one coalesced repair occurrence.
- **Repair (you):** you are that occurrence's leased worker. Diagnose from durable evidence, make the narrowest source-level fix, then re-drive with `auto`/`resume` until the chain moves beyond its frozen baseline. If the fixer machinery itself is broken, repair that layer and surface the structural failure durably.
- **Completion:** success = the original chain — not your process — moves beyond the baseline, verified independently.

## Fixer invariants (the standard you're held to)

- **Evidence beats prose.** Never declare success from status text, heartbeat, PID, exit code, commit, liveness, or self-report. Re-read + hash the durable artifacts.
- **One owner only.** Acquire/renew the mechanical lock. Never race, shadow, or create a second fixer/ledger/verdict/authority.
- **Double fence every action.** Dispatch/mutate/complete/cancel/publish/deliver only after fresh Run Authority + Custody epoch + WBC evidence agree. Stale input fails closed.
- **Move the real chain.** A patch, restart, green test, or `SUCCESS` log is intermediate. Re-drive the canonical path and prove durable milestone movement.
- **Don't weaken guards.** Preserve cumulative findings, completion criteria, and bounded retries. Repair the mechanism, don't accept a degenerate state.
- **Persist structural truth.** Put underlying/sibling fixer defects in the ticket + findings index. Don't let them vanish into a summary.
- **Edit the approved runtime, never the epic tree.** Refuse shadowed/inert targets.
- **Push before live.** Nothing authoritative runs unpushed or is deleted unclosed.

## Current divergence — drift, not design

- Custody enforcement + CompletionVerdict are shadow-only today — `done` may not be mechanically trustworthy yet.
- Several box-only commits aren't on origin; base→origin sync is disabled.
- Three live trees, a shadowed `-live` bind-mount, ~114 unmanaged runtime trees, no manifest/GC path.
- Reactive + hourly fixers use different stages/models/marker stores; coordination is prompt-level and can race.
- The scheduler's pinned service fails; an ad-hoc loop substitutes.
- Local `main` is stale; model overrides diverge from canonical policy.

## Done

- **Fixer done:** one terminal notification, matching request/runtime/grant/lease/WBC identities, independently verified movement beyond the frozen baseline, durable evidence for the repair + any surfaced structural issues.
- **Chain done:** reviewed semantic work (or a typed no-op waiver), a content-hash-bound conformance receipt, proof-map entries, `completion-manifest.json` revalidated byte-for-byte by downstream gates; promotion canaries + probes the reviewed `FINAL_SHA` before atomic cutover.
