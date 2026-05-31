# Over-tier root cause — Profile / Policy lens

**Verdict up front: this is a POLICY (wrong-profile) failure, not a capability gap.**
A fully cheap-driver profile (`solo`) exists and is documented for exactly this kind
of mechanical work. The chain author never used it — the lowest tier they reached was
`directed`, which already drives on a premium model.

## 1. Profile → {driver, critic, execute} table

"Driver" = the orchestration phases that read the repo and steer the run:
`plan` / `loop_plan` / `review` (+ tiebreakers). These are what cost money when they
run premium. Source: `megaplan/profiles/*.toml`.

| Profile | DRIVER (plan/review) | critic | execute (routed) | driver is cheap? |
|---|---|---|---|---|
| `solo` (tier 1) | **DeepSeek V4 Pro** | DeepSeek | flash↔pro (DeepSeek only) | **YES** |
| `directed` (tier 2) | **claude:low** (Opus) | DeepSeek | flash → pro → Sonnet → Opus | no |
| `partnered` (tier 3) | **claude:low** | DeepSeek (premium-directed) | flash → pro → Sonnet → Opus | no |
| `premium` (tier 4) | **claude:low** | claude:low | pro → Sonnet → Opus | no |
| `apex` (tier 5) | **claude / codex** | codex | pro → Sonnet → Opus → codex | no |
| `all-deepseek-pro` | DeepSeek (Fireworks) | DeepSeek | all DeepSeek pro | YES |
| `all-deepseek-pro-direct` | DeepSeek (direct API) | DeepSeek | all DeepSeek pro | YES |
| `all-deepseek-flash` | DeepSeek flash | DeepSeek flash | all flash | YES |
| `all-kimi` (.megaplan local) | Kimi K2.6 | Kimi | Kimi | YES |
| `all-deepseek` (.megaplan local) | DeepSeek V4 Pro | DeepSeek | DeepSeek | YES |

(Notes: `directed`/`partnered`/`premium` `--vendor codex` flips the `claude:low`
driver slots to `codex:low` — still premium. `finalize` is premium on every tier
except `solo`, and `execute` is complexity-routed per task on every tier — those two
are off the tier ladder, so the *tier* only buys premium **reasoning/driver** phases.)

## 2. The crux: which profiles drive cheap?

Phase table (megaplan-decision SKILL.md:91): `plan` is **DeepSeek only in `solo`**.
Tiers 2–5 (`directed`, `partnered`, `premium`, `apex`) all drive `plan`/`review` on a
premium model — the monotonic ladder upgrades reasoning phases first, and `plan` is
the first to go premium at tier 2. So among the named tier profiles, **only `solo`
has a cheap driver.** The all-deepseek / all-kimi profiles are also cheap-driver but
are bake-off / open-stack profiles, not the rubric ladder.

This is exactly the symptom: every hardening milestone was pinned to `directed`/
`partnered`/`premium` (chain.yaml:22–122), so **every milestone got a premium
GPT-5.x/Opus driver** — even the mechanical `directed//high` ones (m4, m5b–d, m6a/b).
`directed` is the *floor* the author treated as "cheap," but its `plan`/`loop_plan`/
`review`/`tiebreaker` slots are all `claude:low` (directed.toml:31,39,42–43) plus a
premium `finalize` (directed.toml:36). There is no "cheap" in `directed` for driving.

## 3. Is tier-by-stakes baked into the policy/docs?

Partly — and it actively pushed the author up. The decision skill's own guidance:
- SKILL.md:46 — *"pick the profile that matches the **highest-stakes deliverable** —
  lower-stakes items inherit the tier."* (one-profile-per-sprint by max stakes)
- SKILL.md:41 — *"high-stakes infra warrants its own sprint, at a higher tier."*
- Tier rows are written around **consequence** ("regression = production incident",
  "kernel-invariant changes") as much as orchestration difficulty.

But the docs also contain the *correct* counter-rule the author missed: SKILL.md:82/84
say "Drop down to `solo` when the plan is obvious — DeepSeek can plan mechanical work
just fine" and "decision-difficulty alone doesn't justify tier 4." `solo`'s own header
lists *"mechanical refactors"* (solo.toml:1–13). So the conflation is real in the
stakes-driven framing, **but the escape hatch was documented and ignored.** The author
read "this store work is risky → higher tier" and let the rest inherit, rather than
splitting the mechanical milestones down to `solo`.

## 4. Recommendation

The fix needs no new profile — **use `solo` for the mechanical milestones.** Concretely:
- m4-naming, m5b/c/d-godfiles, m6a/b → `solo` (behavior-preserving renames/splits
  with a green characterization gate; the gate is the safety net, not the driver tier).
- Keep `premium/thorough` only on m2-store and the genuinely cross-cutting m1/m3*.
- This trades the per-sprint-simplicity rule (SKILL.md:46) for real savings, which the
  skill explicitly permits *"when the lower-stakes work is substantial and independent"*
  — true here (multiple independent decomposition fronts across many days).
- Policy nit worth filing: tighten SKILL.md:46 so "inherit the highest tier" doesn't
  read as "drive everything premium" — make the mechanical-milestone → `solo` drop the
  default, not the exception, when an objective gate (characterization tests) backstops it.
