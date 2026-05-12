---
name: megaplan-rubric
description: Pick the right megaplan profile, thinking-strength tier, and robustness level for the work in front of you — for both Codex and Claude harnesses. Consult before invoking megaplan.
---

# Megaplan rubric — three questions, three dials

Every piece of work answered with three questions. Each question points at one dial. The dials are **independent** — work through each one ignoring the others — then **weigh the three together** holistically to land on a coherent judgment.

| | Question | Dial | What it scales | Flag |
|---|---|---|---|---|
| 1 | What level of raw capability does this need? | **Intelligence tier** | `$/call` | `--profile` |
| 2 | What level of process rigor does this need? | **Planning complexity** | `# of calls` | `--robustness` |
| 3 | How deeply does each model need to think? | **Depth** | `tokens/call` | `--depth` (with `--phase-model` as the surgical escape hatch) |

The dials aren't a mechanical lookup; they're three lenses you apply to the same task, and the answers should fit each other. A high tier with low robustness is usually a mismatch; so is a low tier with `max` depth. When the three feel like they're pulling in opposite directions, the work probably needs to be split.

**The dials measure residual complexity, not nominal scope.** Two factors shape residual complexity, pointing in opposite directions:

- **Decisions already made decrease it.** A brief where the major design decisions are resolved — architecture chosen, interfaces specified, edge cases enumerated, trade-offs decided — is less complex than the same scope arriving open-ended. The pre-resolved decisions don't disappear; they're paid for upstream by whoever wrote the brief.
- **Unknowns remaining increase it.** Even when many decisions are locked, unresolved external API behavior, unmeasured performance characteristics, ambiguous integration targets, or libraries the team hasn't surveyed yet all add complexity the run has to budget for. (That's what `--with-prep` is built for — see below.)

When picking a tier, **discount for decisions made and add for unknowns remaining**. A spec-shaped brief with everything known lands a tier lower than the same nominal scope arriving as a sketch; a tightly-defined brief carrying significant unknowns may need either `--with-prep` or a higher tier. **Tightening the brief beats picking a higher tier** — and is often the cheapest way to bring the rubric down a notch.

**Defaults to keep in mind:** `--robustness standard`, `--depth` unset (which means the profile's existing depths win — usually `:low` on premium phases), vendor from your config (`claude` if unset). Reach past those only when you can name the specific reason.

---

## Dial 1 — Intelligence tier (5 rungs)

> **"What level of raw capability does this need?"**

Five tiers, named so the name itself is the proxy. Each rung swaps one block of phases from cheap (DeepSeek / Kimi) to premium (Claude / Codex). The progression is monotonic — once a phase upgrades, it stays upgraded.

### When to pick each tier

| Tier | Profile | Picks for | Rough cost (light) |
|---|---|---|---|
| 1 | **`basic`** | Discovery, docs, **and most routine programming**: small features in well-known patterns, schema migrations, ports of self-contained code, utility scripts, config changes, mechanical refactors, CRUD over an existing schema, glue code between known surfaces, test fixtures, anything where the patterns are stable and the number of overlapping concerns is small. The instinct to reach for tier 3 the moment "code" appears is usually wrong. | ~$0.50-2 |
| 2 | **`led`** | Same shape as `basic`, but a premium model writes the plan. Use when the *planning* is the hard part — the implementation is mechanical once mapped out, but you need real thinking to get the map right: complex schema migrations where step ordering matters, multi-step refactors where the sequence needs care, features whose architecture demands deliberation but whose code follows patterns, greenfield implementations with non-trivial design but well-shaped pieces. The cheap models execute confidently once the premium plan exists. Use when you'd say "I just need a smart plan; the rest is following instructions." | ~$1-3 |
| 3 | **`thoughtful`** | Novel implementation, cross-cutting code, judgment calls, multi-system features: a new CLI command with cross-cutting concerns, an inbox or routing rewrite, adapters with non-trivial edge cases, plan-mutation verbs touching shared state, export/import surfaces with format edge cases, novel features in a known architecture, refactors with real cross-system implications. Premium handles every reasoning phase (plan, critique, revise, review); DeepSeek handles mechanical phases (prep, gate, finalize, execute). This is the default for *real* engineering work — but only when the work is genuinely novel or cross-cutting. If the patterns are stable and the variables are few, drop back to **`basic`** or **`led`**. | ~$5-15 |
| 4 | **`premium`** | Single-vendor premium end-to-end. Use for production-critical work where you want one model's judgment on every phase (including execution) and a clean single-vendor audit trail: schema definitions, wire formats, security-critical code paths, public API contracts, migration logic running against production data, kernel-invariant changes (data structures everything else depends on). Pair with `--robustness robust` for the most complex of these. Pick `--vendor claude` or `--vendor codex` by preference, credits, or prior fit — they're treated as interchangeable. | ~$30-70 |
| 5 | **`super-premium`** | Apex — both Claude *and* Codex contributing to the same job. **This is the one tier where the two premium models stop being interchangeable** — Claude and Codex have different strengths (Opus on author/repo-reading side, Codex on critique/structural-analysis side), and the value of this tier comes from combining them. Reach for it when one premium model's depth isn't enough and you want two minds working together: concurrency primitives that cascade (locks, locked event-append, writer epochs, session schemas), schemas all later sprints will build on, wire formats / claim semantics / parent-child propagation rules, multi-system migration decisions, big architectural choices where downstream sprints all depend on what you decide here. Trigger conditions: **(1)** high-stakes — regression = production incident or worse — *or* **(2)** the sprint is *making* a big architectural decision, not just implementing one already made. If neither applies, drop to tier 4. | ~$30-50 |

### Which model handles each phase

| Phase | basic | led | thoughtful | premium | super-premium |
|---|---|---|---|---|---|
| **plan**     | DeepSeek | claude   | claude   | claude | claude |
| **prep**     | DeepSeek | DeepSeek | DeepSeek | claude | claude |
| **critique** | Kimi     | Kimi     | claude   | claude | codex  |
| **revise**   | DeepSeek | DeepSeek | claude   | claude | claude |
| **gate**     | DeepSeek | DeepSeek | DeepSeek | claude | claude |
| **finalize** | DeepSeek | DeepSeek | DeepSeek | claude | claude |
| **execute**  | DeepSeek | DeepSeek | DeepSeek | claude | codex  |
| **review**   | Kimi     | Kimi     | claude   | claude | codex  |

Legend:

- **DeepSeek** = DeepSeek V4 Pro (open-source workhorse; competent, structured, cheap).
- **Kimi** = Kimi K2 (Fireworks-hosted `kimi-k2p6`; open-source critic; creative, good at spotting issues).
- **claude** = Claude Opus 4.7. **codex** = Codex GPT-5.5.

**Two things to notice in the phase table:**

1. **Each tier adds exactly one block of phases to premium**, and once upgraded, a phase stays upgraded:
   - Tier 2 adds `plan` (one phase).
   - Tier 3 adds `critique` + `revise` + `review` (the rest of the reasoning loop).
   - Tier 4 adds `prep` + `gate` + `finalize` + `execute` (all mechanical and judgment phases).
   - Tier 5 doesn't add new premium coverage; it splits the existing premium roles across two vendors.

2. **The two open-source models exit in order as you climb.** Kimi exits at tier 3 (sense-check phases get premium). DeepSeek exits at tier 4 (everything else gets premium). At tier 5 the question stops being "premium vs cheap" and becomes "which premium for which role."

### Vendor: Claude and Codex are interchangeable at tiers 2-4

**Claude and Codex are treated as systematically interchangeable at tiers 2-4 — by policy, not just by observation.** The marginal quality difference between them on a given task is small relative to picking the wrong tier or robustness; encoding per-task vendor preferences would add a dial that doesn't earn its keep. Pick a preferred vendor once (`--vendor`, or `[defaults].vendor` in config) and the preference flows through every tier-2-through-4 profile.

**Tier 5 is the exception** — its whole rationale is using both vendors' different strengths together. `--vendor` is silently ignored there. The phase table above shows the claude variant for tiers 2-4; for the codex variant, swap `claude`↔`codex` throughout.

---

## Dial 2 — Planning complexity

> **"What level of process rigor does this need?"**

The `--robustness` flag. Picks how many phases run and how many critique passes happen.

| Setting | Workflow | When to use |
|---|---|---|
| (skip megaplan) | — | Single-file fix, anything you can hold in your head. Just do the work directly. |
| `light` | plan → critique → revise → finalize → execute (no prep, no gate, no review) | Small/scoped, well-known feature, low blast radius. ~5 phases instead of 8. |
| `standard` *(default)* | prep → plan → critique → gate → revise → finalize → execute → review; 4 critique checks | Cross-cutting, unfamiliar code, ambiguous brief. **Fine for almost everything.** |
| `robust` | Same shape as `standard`, 8 critique checks + parallel critique | Security, data migration, public API contract — anything where a regression = production incident. **Extremely rare.** You should be able to name the specific stakes that warrant it. |
| `superrobust` | `robust` + parallel review | Both deep critique *and* concurrent review matter. **Vanishingly rare.** Only when the user specifically asks for it. |

`standard` is home base. `light` is a cost optimization for cleanly-scoped work. `robust` should feel exceptional — you're saying "this regression would page someone." `superrobust` is a user-requested override, never a default.

Cost bands in the tier table above are at `light`. Roughly 1.5-2× the per-phase cost going from `light` → `standard`, and another ~1.3× going to `robust`.

---

## Dial 3 — Depth

> **"How deeply does each model need to think within the tier I picked?"**

Picks the thinking strength of the premium model(s) the tier brought in. Independent of tier and robustness — orthogonal lever. Spelled out in the agent spec after a colon (`claude:low`, `codex:medium`, etc.).

| Pattern | When to use |
|---|---|
| `low` planner / `low` critic | **The default.** The pattern is mechanical, intuition is enough, the codebase is well-known. A lot of work lands here even at tier 3 — premium models at `low` thinking are still substantially smarter than the cheap tier, so the upgrade isn't free but doesn't need to be expensive either. |
| `medium` planner / `low` critic | Brief is clear but the work has real judgment calls. The plan needs deliberation beyond intuition; the critic still doesn't. |
| `high` planner / `low` critic | Brief is long OR codebase is unfamiliar. The planner needs substantial repo-reading and structural reasoning. |
| `xhigh` / `max` planner only | Genuinely novel architectural decision. Use sparingly — most "hard" plans don't actually need this. |

Available strengths: Claude is `low / medium / high / xhigh / max`; Codex is `minimal / low / medium / high`.

**The asymmetry principle:** author phases (plan, revise) can scale all the way up to `max` when the work demands deliberation; sense-check phases (critique, gate, review) plateau at `low` regardless of stakes. A `claude:high` planner + `claude:low` critic is the right shape when the plan needs real thinking — not `claude:medium` everywhere.

Default to `low`; only spend on depth when you can name the specific reason the planner needs to deliberate. "Just in case" doesn't earn the cost.

---

## When to add a prep phase

> **"Does the planner need to do explicit research before it can commit to a plan?"**

A fourth, narrower lever orthogonal to the three dials. `prep` is a visible research phase that runs *before* `plan` — the planner explicitly reads external docs, surveys an unfamiliar library, maps an API surface, or disambiguates a vague brief. Off by default (most work doesn't need a discovery step; adding one without need just costs tokens and wall-clock). Enable with `--with-prep`.

**Reach for it when at least one of these is true:**

- **External APIs whose semantics aren't already known** — the planner has to read API docs before deciding what calls to make.
- **Unfamiliar libraries or frameworks** — codebase patterns aren't enough; the planner needs to survey the library's API surface first.
- **Research-heavy briefs** — the work is research-bounded ("figure out how X behaves, then implement").
- **Ambiguous or under-specified requirements** — the planner needs a budget to disambiguate explicitly instead of interleaving with planning.
- **Integration work where target-system behavior must be discovered** — wire formats, error semantics, performance characteristics undocumented in the codebase.

"Prep just in case" doesn't earn its cost. Redundant at `robust` and `superrobust` (those already include prep); the flag's value is at `light` and `standard`, where prep is normally skipped.

---

## Notation for recording profile choices

For sprint notes, brief headers, commit messages, or anywhere you need to write down a profile choice compactly, use the slash form: **`profile/robustness/depth`** — defaults can be omitted.

Order is fixed left-to-right: tier → robustness → depth, matching dial numbers 1 → 2 → 3. The `//` reads as "skip the middle slot — defaults there."

### Spine examples (just the three dials)

| What you decided | Shorthand |
|---|---|
| Tier-1 work at default robustness and depth | `basic` |
| Tier-1 work at light robustness | `basic/light` |
| Tier-2 work at defaults | `led` |
| Tier-3 work at defaults | `thoughtful` |
| Tier-3 work with depth bumped to high (default robustness) | `thoughtful//high` |
| Tier-3 work with medium depth (default robustness) | `thoughtful//medium` |
| Tier-4 work at robust + high depth | `premium/robust/high` |
| Apex sprint, robust + high depth | `super-premium/robust/high` |

### With modifiers (secondary flags)

For `--vendor`, `--critic`, `--with-prep`, append modifiers without disturbing the spine. The conventions:

- `@<vendor>` — vendor override (e.g. `@codex`).
- `, critic=<kind>` — critic override (e.g. `, critic=kimi`).
- `+prep` — enable the prep phase.

| What you decided | Shorthand |
|---|---|
| Tier-2 work, prefer codex | `led @codex` |
| Tier-3 work, Kimi critic | `thoughtful, critic=kimi` |
| Tier-3 work, needs upfront API discovery | `thoughtful +prep` |
| Tier-3 work, novel external API, codex preferred, high depth | `thoughtful//high @codex +prep` |
| Tier-4 production migration with Kimi critic | `premium/robust/high, critic=kimi` |
| Apex sprint with prep | `super-premium/robust/high` *(no `+prep` needed — apex includes prep at robust)* |

### Where to use this

The shorthand is for **recording**, not for the CLI. Use it in:

- Sprint planning docs ("Sprint 14 — `thoughtful//high +prep`")
- Brief headers (`[premium/robust/high]` as the first line of a brief)
- Commit messages ("ran as `thoughtful`, defaults")
- Slack / chat references when describing a sprint setup at a glance

The actual invocation is still `megaplan init --profile … --robustness … --depth …` — see "Running it" below for the mapping.

---

## Running it — profile plus the knobs

The invocation has three layers: three flags for the dials, three modifiers for orthogonal toggles, one escape hatch for surgical needs.

### The three dial flags

1. **`--profile`** — the tier name (`basic`, `led`, `thoughtful`, `premium`, `super-premium`).
2. **`--robustness light|standard|robust|superrobust`** — `standard` is home base.
3. **`--depth low|medium|high|xhigh|max`** — rewrites the effort suffix on author-side claude/codex slots (plan, revise, loop_plan, tiebreaker_*) at the resolved vendor. Critic + mechanical phases plateau at their existing depth (the asymmetry principle). Defaults to whatever the profile sets (usually `:low`). Honored on vendor-locked profiles. Codex caps at `high`; Claude adds `xhigh` and `max`.

### The three modifier flags

- **`--vendor claude|codex`** — vendor override at tiers 2-4. Defaults to `[defaults].vendor` in `~/.config/megaplan/config.toml` (or `claude` if unset). Tier 1 ignores it (no premium phases); tier 5 silently ignores it (vendor-locked).
- **`--critic kimi|cross`** — overrides the critique+review pair (preserving the invariant — see below). `kimi` swaps in Kimi for both phases; `cross` swaps to the other premium vendor relative to `--vendor`. Silently ignored at tier 5.
- **`--with-prep`** — force the `prep` research phase into the workflow regardless of `--robustness`. Off by default; no-op at `robust`/`superrobust`. See "When to add a prep phase" above.

### The escape hatch

**`--phase-model phase=spec`**, repeatable. For when `--depth` is too coarse — e.g. bump just `critique` without touching the rest. Most runs don't need it.

### Where the flags live

`--vendor`, `--depth`, and `--critic` are wired on every subcommand that accepts `--profile`:

- `megaplan init`
- the step parsers (`prep`, `plan`, `critique`, `gate`, `revise`, `finalize`, `execute`, `review`, etc.)
- `megaplan loop init`, `megaplan loop run`
- `megaplan tiebreaker run` and the bare `megaplan tiebreaker` default-run action

### Mid-flight overrides

For when the work turns out different than expected:

- `megaplan override set-profile --profile NAME --plan ID` — swap tier mid-run. Started on `thoughtful`, hit something gnarlier, escalate to `premium` for the remainder.
- `megaplan override set-robustness --robustness LEVEL --plan ID` — same for the planning-complexity dial.
- `megaplan override replan --plan ID` — back up to planning and redo with whatever models / robustness are now active.
- `megaplan override add-note --plan ID --note "..."` — inject guidance into an active plan without restarting any phase. Read by every subsequent phase. The brief is snapshotted at `init`; later edits to the idea-file are NOT re-read, so this is the verb for "I missed something." `--source user` (default) blocks `force-proceed` under `--strict-notes`; `--source driver` doesn't. **`megaplan feedback` is end-of-run rating, not in-flight guidance** — common confusion.

**If a run is struggling, escalate mid-flight rather than letting it grind.** Common signals: the plan keeps missing concerns the critique surfaces; revise doesn't actually resolve the critique's flags; the executor produces work the review can't accept; iteration cycles through the same defects without converging. Don't sit through a degenerate run — `override set-profile` to the next tier up (or bump `--robustness`), and let the remainder benefit from the better setup. One wasted phase costs much less than restarting the sprint. The same applies to depth: if the planner is clearly under-deliberating, `override` with a higher `--depth` rather than accepting a thin plan.

Lean on these instead of inventing new profile names. If you find yourself thinking "I want a profile that's *like* `thoughtful` but with X" — the answer is almost always `thoughtful` plus an override, not a new profile.

### The critique == review invariant

The model that critiques the plan also reviews the executed work — same mind pre-execution and post-execution. Wiring them to the same non-author model gives you one coherent second mind across both checkpoints and keeps the author's blindspots out of the sense-check loop.

`--critic` bundles the two phases in one flag and preserves the invariant. Bare `--phase-model` does not — if you override critique with `--phase-model`, override review the same way, or use `--critic` instead.

### Worked invocations

> *"Schema migration where step ordering is intricate but each step is mechanical. Prefer codex; brief is clear so default depth is fine."*
> `megaplan init <brief> --profile led --vendor codex`

> *"Novel feature, cross-cutting, brief is long, codebase is unfamiliar."*
> `megaplan init <brief> --profile thoughtful --depth high` *(vendor defaults from config; depth lifts plan + revise + loop_plan + tiebreaker_* to claude:high; critic + mechanical stay at their defaults)*

> *"Novel feature involving an external API we haven't used before. Planner needs to read the API docs before committing."*
> `megaplan init <brief> --profile thoughtful --with-prep --depth medium` *(adds the visible `prep` phase even at `standard` robustness, so the planner can survey the API surface before producing a plan)*

> *"Cross-cutting feature, tier 3, but I want Kimi catching what the premium author missed (legacy `spade-claude` behaviour)."*
> `megaplan init <brief> --profile thoughtful --critic kimi`

> *"Migration logic against production data. I want kimi critiquing this even though it's tier 4."*
> `megaplan init <brief> --profile premium --robustness robust --depth high --critic kimi`

> *"Schema everyone downstream will build on. Apex tier."*
> `megaplan init <brief> --profile super-premium --robustness robust --depth high`

> *"Tier-3 work, brief is clear, but I want the critic to deliberate a little more — the planner can stay at the profile default."*
> `megaplan init <brief> --profile thoughtful --phase-model critique=claude:medium --phase-model review=claude:medium` *(surgical: bump just one pair, leave plan + revise at the profile's `:low`. The kind of override `--depth` can't express because it's by-phase-name, not by-author-vs-critic.)*

> *"Verification sprint, mostly text, lowest-stakes thing in the queue."*
> `megaplan init <brief> --profile basic --robustness light`

Three pieces of intent → three flags (`--profile`, `--robustness`, `--depth`), plus `--vendor` / `--critic` / `--with-prep` when you need them.

---

## The canonical catalog

Five tier names + two flags cover the whole rubric. A handful of legacy aliases are preserved for back-compat.

### Canonical (use these)

| Profile | Tier | Where it sits |
|---|---|---|
| `basic` | 1 | All cheap; Kimi critiques+reviews. |
| `led` | 2 | Premium plan only; everything else cheap. |
| `thoughtful` | 3 | Premium reasoning loop; DeepSeek mechanical. The default for real engineering. |
| `premium` | 4 | Single-vendor premium end-to-end at `:low` depth. Pick the vendor with `--vendor`. |
| `super-premium` | 5 | Vendor-locked Claude/Codex split. The apex; `--vendor` and `--critic` are silently ignored. |

Vendor, depth, and critic flavor are flags on these, not separate profiles: `--vendor claude|codex` at tiers 2-4, `--depth low|medium|high|xhigh|max` to set author-phase thinking depth, `--critic kimi|cross` to override the critique+review pair.

### Legacy aliases (still loaded; modern equivalent listed)

| Profile | What it is | Modern equivalent |
|---|---|---|
| `nancy` | Nancy Drew — DeepSeek lead + executor, `codex:medium` prep/critique/gate/review. Cheapest profile with a premium critic. | Closest is `led --critic cross` (Codex critic over a Claude/Codex-planned base), but the recipe doesn't have a 1:1 mapping. Keep using `nancy` if scripts rely on it. |
| `marlowe` | Legacy `claude:low` author with Kimi critic + Claude-on-review. Predates the `critique == review` invariant. | `thoughtful --critic kimi` is the spiritual successor, but it routes review through Kimi (honoring the invariant) instead of Claude. Use `marlowe` if you specifically want Claude doing the post-execute review. |
| `holmes` | Legacy medium-effort with a cross-model gate (`codex:medium` gate/review alongside `claude:medium` plan/revise). | No exact match — the rubric doesn't carve out cross-model gate behaviour. Closest is `thoughtful --critic cross --phase-model plan=claude:medium --phase-model revise=claude:medium`. Keep using `holmes` if cross-model gate is the point. |
| `marlowe-claude` / `marlowe-codex` | Low-effort cluster: claude (or codex) author, *other* premium critic. | `thoughtful --critic cross` (`--vendor claude` or `codex` picks the author). |
| `spade-claude` / `spade-codex` | Low-effort cluster: claude (or codex) author, Kimi critic. | `thoughtful --critic kimi --vendor claude\|codex`. |
| `holmes-claude` / `holmes-codex` | Medium-effort cluster: claude (or codex) author at `:medium`, other premium critic. | `thoughtful --critic cross --vendor … --phase-model plan=claude:medium --phase-model revise=claude:medium`. |
| `watson-claude` / `watson-codex` | Medium-effort cluster: claude (or codex) author at `:medium`, Kimi critic. | `thoughtful --critic kimi --vendor … --phase-model plan=claude:medium --phase-model revise=claude:medium`. |
| `all-claude` / `all-codex` | Single vendor at default effort (no `:low` suffix) for every phase. | `premium --vendor claude\|codex`, **but the depths differ** — see `premium ≠ all-claude` in migration notes. |
| `poirot` | Hercule Poirot — vendor-locked Claude+Codex split at default effort. Mirrors `super-premium`. | `super-premium`. Both are vendor-locked and use the same phase map. Pick either; keep `poirot` for personality / legacy scripts. |
| `standard` | Same shape as `poirot` / `super-premium` but lives in the megaplan core as the built-in fallback. | `super-premium`. |
| `all-deepseek-pro` / `all-deepseek-flash` / `all-fireworks-deepseek` | DeepSeek end-to-end (different deployments). | Use directly when you specifically want DeepSeek-only — they're below tier 1 on the rubric ladder. |
| `all-open` | Kimi author + GLM-5.1 critic/executor. Fully-open analogue of `super-premium`. | Use directly when you want open-source apex; no rubric-tier equivalent. |

### Project- and user-level overrides

Built-in profiles live in `megaplan/profiles/` and ship with the package. To customize:

- Per-user: `~/.config/megaplan/profiles.toml`.
- Per-project: `<project>/.megaplan/profiles.toml`.

Project overrides win over user overrides win over built-ins. The TOML schema is `[profiles.<name>]` with one key per phase (plus optional `vendor_locked = true`).

---

## Config defaults

The `--vendor` flag honors a per-user config default. Write `~/.config/megaplan/config.toml`:

```toml
[defaults]
vendor = "claude"   # "claude" or "codex"
```

Set this once on a new machine and tiers 2-4 default to your preferred premium without per-invocation flags. The CLI flag still wins when passed.

A malformed or missing config falls back to `claude` silently.

---

## Migration notes

The rubric's canonical catalog supersedes the old detective grid. Existing scripts keep working (every legacy name still resolves), but a few sharp edges are worth flagging.

### `super-premium` and `poirot` are vendor-locked

Both profiles set `vendor_locked = true`. `--vendor` and `--critic` are silently ignored on vendor-locked profiles — the locked profile's existing model assignments win, with no error or warning. The loader treats those flags as no-ops rather than failures.

`--depth` **is honored** on vendor-locked profiles (depth is about how hard each model thinks, not which vendor is filling the slot). `--phase-model` also still works as the surgical escape hatch when you need finer control than `--depth` can give.

### `premium` ≠ `all-claude`

This is the trap. `all-claude` uses bare `claude` for every phase, which means **default effort** in the agent spec parser. `premium --vendor claude` uses `claude:low` for every phase. The two are not interchangeable on cost or output — `:low` is meaningfully cheaper and shallower than default effort.

- **Scripts pinned to `all-claude` / `all-codex`** keep their existing behaviour. No change required.
- **Users picking the rubric default at tier 4** should reach for `--profile premium` and (if needed) bump depth explicitly via `--depth high` (or `--phase-model plan=claude:high` for surgical control). That matches the rubric's "premium at `:low` is the right floor" principle.

### `--critic cross` at tier 1 is a footgun

The flag accepts the combination, but it doesn't make rubric sense — there's no premium *author* for the cross-vendor critic to be cross-vendor *to*. The tier-1 profile has no premium model at all; "cross of nothing" is undefined.

If you want a premium critic at tier 1, step up to `led --critic cross` (which actually has a premium author to be cross-vendor relative to) or `thoughtful --critic kimi` (the closest cheap-pipeline-with-premium-critique shape).

### Legacy detective-cluster scripts

Scripts using `marlowe-*`, `spade-*`, `holmes-*`, `watson-*` keep working — the profiles ship unchanged. There's no rush to migrate. New work should prefer `thoughtful` plus `--vendor` / `--critic` / `--phase-model`; the legacy names are kept because they have known cost/quality data from prior runs.

### Kimi spec migrated to Fireworks `kimi-k2p6`

The canonical Kimi spec changed from `hermes:moonshotai/kimi-k2.6` (OpenRouter-routed) to `hermes:fireworks:accounts/fireworks/models/kimi-k2p6` (Fireworks-direct). Every built-in profile that used Kimi (`basic`, `led`, `marlowe`, `holmes`, the `spade-*` / `watson-*` clusters, `all-open`) has been updated; `--critic kimi` now writes the new spec via `KIMI_SPEC`.

- **Scripts that don't pin the spec** keep working without changes — the rewrite is internal.
- **Scripts that pin the old spec via `--phase-model critique=hermes:moonshotai/kimi-k2.6`** still parse and run *as strings*, but they'll be calling a model that may no longer be available on OpenRouter. Replace the pinned spec with `hermes:fireworks:accounts/fireworks/models/kimi-k2p6`, or — usually cleaner — drop the `--phase-model` pin in favor of `--critic kimi`, which always tracks the canonical Kimi spec.

### DeepSeek spec migrated to Fireworks `deepseek-v4-pro`

The canonical DeepSeek spec changed from `hermes:deepseek/deepseek-v4-pro` (DeepSeek's direct API via OpenRouter) and `hermes:deepseek:deepseek-v4-pro` (direct-provider form) to `hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro` (Fireworks-direct). Every built-in profile that used DeepSeek (`basic`, `led`, `thoughtful`, `marlowe`, `holmes`, `nancy`, the detective cluster, `all-deepseek-pro`) has been updated.

- **Scripts that don't pin the spec** keep working without changes — the rewrite is internal.
- **Scripts that pin the old spec via `--phase-model`** still parse and run *as strings*; they'll route via the previous provider as long as those routes remain configured. Migrate the pinned spec to `hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro` to match the new canonical routing.

---

## Skill installation

This doc doubles as the SKILL.md body for the `megaplan-rubric` skill. Wire it up so Claude Code and Codex consult it automatically:

```bash
DOC="$(pwd)/docs/megaplan-rubric.md"   # run from the megaplan repo root

# Claude Code skill
mkdir -p ~/.claude/skills/megaplan-rubric
ln -sf "$DOC" ~/.claude/skills/megaplan-rubric/SKILL.md

# Codex skill
mkdir -p ~/.codex/skills/megaplan-rubric
ln -sf "$DOC" ~/.codex/skills/megaplan-rubric/SKILL.md
```

Restart Claude Code / Codex after symlinking. Edits to this file propagate to both skills. Multiple people on a team each run the same commands against their own checkout — never share a symlink to someone else's path.

---

## Operating principles

**The brief is the dominant variable.** Brief-interpretation defects (duplicate paths, fabricated decisions, brief-violating renames) show up across every profile. Tightening the brief beats picking a better profile. If you only invest in one thing, invest in the brief.

**Where the premium model goes matters more than how many premium models you use.** Concentrating the premium model in author-side phases (plan, revise) gives the biggest cost-quality win. DeepSeek as the executor is fine — premium there is overkill.

**Size each megaplan to ~2 weeks max.** A megaplan should fit a sprint — roughly **two weeks of human work**, give or take (i.e. how long the same scope would take a human engineer to plan, build, and review, not wall-clock time for the run itself). Larger scopes don't survive the brief-to-execution distance; the plan drifts, the critique loses focus, the review can't hold the whole shape in one pass. If you're scoping work that genuinely needs a month, split it into 2–3 sprints with explicit handoffs (each its own brief, its own profile, its own retro).

**One profile per sprint.** Within that ~2-week window, pick the profile that matches the **highest-stakes deliverable** in the sprint; lower-stakes items inherit the tier. Operational simplicity beats the savings from splitting. Only split when the lower-stakes work is *substantial* (multiple days) **and** independent. Structure the plan so cheap work lives in cheap sprints, not interleaved inside expensive ones.

**Bake-off is opt-in.** Default to a single profile. Only run a multi-arm bake-off when (a) the user asks, (b) three or more mixes are genuinely plausible, (c) the deliverable is a diff worth comparing, and (d) per-arm cost is well below the cost of guessing wrong. Don't bake off discovery / scoping / contract-freeze sprints — no diff to compare.

**Anti-patterns:**

- *"Always use Claude."* Wrong. Codex on prep/critique/gate steers DeepSeek planners well and is the cheapest viable premium-critic profile.
- *"Higher thinking strength always helps."* Wrong. Strength plateaus on sense-check duty; spend it on author-side phases only.
- *"Profile choice dominates outcome."* Mostly wrong. Brief quality dominates. If three profiles all produce brief-interpretation defects, fix the brief.

### Calibration caveats

- **Tier 2 (`led`) is a design point, not a measured one.** "Premium plan only, everything else cheap" is theoretically clean (concentrate spend where it pays off most) but hasn't been bake-off validated against tier 1 or tier 3 on intermediate-complexity work. Reach for it when the shape fits, but treat it as a hypothesis until we have runs to compare. If `led` consistently underperforms `thoughtful` on real work, the right answer may be to drop it and accept that there's no intermediate tier.
- **Cost bands for tiers 1-2 are projections, not runs.** Tiers 3-5 have prior-run data behind their numbers; tiers 1-2 are estimates based on the model mix.
