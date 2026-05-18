---
name: megaplan-decision
description: Pick the right megaplan profile, thinking-strength tier, and robustness level for the work in front of you — for both Codex and Claude harnesses. Consult before invoking megaplan.
---

# Megaplan Decision

This doc is for deciding **how to execute work through megaplan**. The goal: take a piece of work, scope it into sprints of at most two weeks each, decide how to run each sprint (which models, how much process, how deeply they think), and turn that decision into a concrete action plan the megaplan CLI runs end-to-end. Three dials capture the per-sprint decision; everything else is a modifier on top.

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

**Defaults to keep in mind:** `--robustness full`, `--depth` unset (which means the profile's existing depths win — usually `:low` on premium phases), vendor from your config (`claude` if unset). Reach past those only when you can name the specific reason. Built-in profiles live in `megaplan/profiles/`; per-user (`~/.config/megaplan/profiles.toml`) and per-project (`<project>/.megaplan/profiles.toml`) TOML overrides win over them.

---

## Sizing and briefing

Two decisions come before the three dials: **how many megaplans you need**, and **what each brief covers**. Get these wrong and the dials can't save the run.

### Size each megaplan to ~2 weeks of work

A megaplan should fit roughly **two weeks of human work** — the time a skilled engineer would take to plan, build, and review the same scope. Wall-clock for the harness itself is unrelated; this is about scope, not duration.

If the work is bigger, **split it**. Each sprint gets its own brief, its own profile, its own retrospective. Cramming a month of work into one plan means the brief drifts, the critique loses focus, and the review can't hold the whole shape in one pass.

Signs you should split:

- Multiple major architectural decisions — each deserves its own sprint.
- Deliverables with different stakes — high-stakes infra warrants its own sprint, at a higher tier; bundling it with cheap work either over-pays for the cheap work or under-protects the expensive part.
- You can't describe the outcome in one or two sentences.

When you split, structure the dependency graph explicitly. Each handoff is a written artifact — schema, API surface, doc — that the next brief can cite. Sprints without that artifact between them are really one sprint pretending to be two.

### What goes in the brief

The brief is the dominant variable — a tighter brief lets you pick a lower tier without losing quality. Invest here before anywhere else; tightening the brief beats picking a higher tier, and is usually cheaper.

A good brief covers:

1. **Outcome** — what's being delivered, in one or two sentences. The thing a reviewer would check.
2. **Scope** — what's IN, what's OUT, sized to ≤2 weeks of work.
3. **Locked decisions** — architecture, interfaces, libraries, patterns already chosen. Naming them stops the planner from relitigating.
4. **Open questions** — things you don't know yet that the planner needs to resolve. Naming them stops the planner from quietly inventing answers.
5. **Constraints** — performance budgets, security requirements, backward-compat needs, deadlines.
6. **Done criteria** — what "done" looks like: a test that passes, a workflow that completes, a metric below a threshold.
7. **Touchpoints** — which files / modules / surfaces the work touches.
8. **Anti-scope** — explicit "don't touch X" or "don't refactor Y" so the planner doesn't drift into bonus work.

A brief missing #3 or #4 surfaces those gaps as critique flags — better to write them down up front than have the harness rediscover them mid-run.

---

## Dial 1 — Intelligence tier (5 rungs)

> **"What level of raw capability does this need?"**

Five tiers, named for the **social configuration of minds** working on the problem. Each rung swaps one block of phases from DeepSeek to premium (Claude / Codex). The progression is monotonic — once a phase upgrades, it stays upgraded. Tier 1 (`solo`) is all DeepSeek end-to-end.

### When to pick each tier

| Tier | Profile | Picks for | Rough cost (light) |
|---|---|---|---|
| 1 | **`solo`** | One powerful but non-premium model working alone across every phase (plan through review). Discovery, docs, schema migrations, ports of self-contained code, utility scripts, config changes, mechanical refactors, CRUD over an existing schema, glue code between known surfaces, test fixtures, anything where the patterns are stable and the number of overlapping concerns is small. Tier 1 doesn't mean "no second opinion" — robustness controls whether critique runs; tier 1 just means that critique (and everything else) runs on DeepSeek rather than a premium model. | ~$0.50-2 |
| 2 | **`directed`** | Same shape as `solo`, but a premium model gives direction — writes the plan, then steps away. Use when the *planning* is the hard part — the implementation is mechanical once mapped out, but you need real thinking to get the map right: complex schema migrations where step ordering matters, multi-step refactors where the sequence needs care, features whose architecture demands deliberation but whose code follows patterns, greenfield implementations with non-trivial design but well-shaped pieces. DeepSeek executes confidently once the premium plan exists. Use when you'd say "I just need a smart plan; the rest is following instructions." | ~$1-3 |
| 3 | **`partnered`** | Premium and DeepSeek working together throughout the reasoning loop. Novel implementation, cross-cutting code, judgment calls, multi-system features: a new CLI command with cross-cutting concerns, an inbox or routing rewrite, adapters with non-trivial edge cases, plan-mutation verbs touching shared state, export/import surfaces with format edge cases, novel features in a known architecture, refactors with real cross-system implications. Premium handles every reasoning phase (plan, critique, revise, review); DeepSeek handles mechanical phases (prep, gate, finalize, execute). This is the default for *real* engineering work — but only when the work is genuinely novel or cross-cutting. If the patterns are stable and the variables are few, drop back to **`solo`** or **`directed`**. | ~$5-15 |
| 4 | **`premium`** | Premium mind everywhere — DeepSeek exits. Single-vendor premium end-to-end. **Tiers 4 and 5 are the only tiers where a premium model *executes* the code, not just reasons about it.** Bias toward this tier when the *execution itself* is nuanced — lots of detail, lots of edge cases, lots of "the practical implementation is hard even after you've decided what to do." Decision-difficulty alone doesn't justify tier 4; `partnered` is enough when the implementation is mechanical once mapped out. Reach for `premium` when the work has deep, irreversible repercussions whose complexity demands premium across every phase including execution: schema definitions, wire formats, security-critical code paths, public API contracts, migration logic running against production data, kernel-invariant changes. Pair with `--robustness thorough` for the most complex of these. Pick `--vendor claude` or `--vendor codex` by preference, credits, or prior fit — they're treated as mostly interchangeable. | ~$30-70 |
| 5 | **`apex`** | Premium minds combined across vendors — both Claude *and* Codex contributing to the same job. Inherits tier 4's "premium executes the code" property, then adds a second premium vendor. **This is the one tier where the two premium models stop being interchangeable** — Claude and Codex have different strengths (Opus on author/repo-reading side, Codex on critique/structural-analysis side), and the value of this tier comes from combining them. Reach for it when one premium model's depth isn't enough *and* the practical execution has enough nuance to need both minds — concurrency primitives that cascade (locks, locked event-append, writer epochs, session schemas), schemas all later sprints will build on, wire formats / claim semantics / parent-child propagation rules, multi-system migration decisions, huge architectural choices where downstream sprints all depend on what you decide here. Trigger conditions: **(1)** high-stakes — regression = production incident or worse — *or* **(2)** the sprint is *making* a huge architectural decision, not just implementing one already made — *and* the execution itself has enough detail to warrant premium implementing it, not just deciding what to implement. If neither applies, drop to tier 4. | ~$30-50 |

### Which model handles each phase

| Phase | solo | directed | partnered | premium | apex |
|---|---|---|---|---|---|
| **plan**     | DeepSeek | claude   | claude   | claude | claude |
| **prep**     | DeepSeek | DeepSeek | DeepSeek | claude | claude |
| **critique** | DeepSeek | DeepSeek | claude   | claude | codex  |
| **revise**   | DeepSeek | DeepSeek | claude   | claude | claude |
| **gate**     | DeepSeek | DeepSeek | DeepSeek | claude | claude |
| **finalize** | DeepSeek | DeepSeek | DeepSeek | claude | claude |
| **execute**  | DeepSeek | DeepSeek | DeepSeek | claude | codex  |
| **review**   | DeepSeek | DeepSeek | claude   | claude | codex  |

Legend:

- **DeepSeek** = DeepSeek V4 Pro (open-source workhorse; competent, structured, non-premium).
- **claude** = Claude Opus 4.7. **codex** = Codex GPT-5.5.

**Two things to notice in the phase table:**

1. **Each tier adds a block of phases to premium**, and once upgraded, a phase stays upgraded:
   - Tier 2 adds `plan` (one phase).
   - Tier 3 adds `critique` + `revise` + `review` (the rest of the reasoning loop).
   - Tier 4 adds `prep` + `gate` + `finalize` + `execute` (all mechanical and judgment phases).
   - Tier 5 doesn't add new premium coverage; it splits the existing premium roles across two vendors.

2. **Only two model classes appear in canonical profiles: DeepSeek (non-premium) and Claude/Codex (premium).** DeepSeek runs every phase at tier 1, narrows to mechanical-plus-sense-check phases at tier 2, narrows further to mechanical phases at tier 3, and exits entirely at tier 4. At tier 5 the question stops being "premium vs DeepSeek" and becomes "which premium for which role."

### Vendor: Claude and Codex are mostly interchangeable at tiers 2-4

**Claude and Codex are treated as mostly interchangeable at tiers 2-4 — by policy, not just by observation.** The marginal quality difference between them on a given task is small relative to picking the wrong tier or robustness; encoding per-task vendor preferences would add a dial that doesn't earn its keep. Users may prefer one or the other depending on which subscription has more credits available — pick a preferred vendor once (`--vendor`, or `[defaults].vendor` in config) and the preference flows through every tier-2-through-4 profile.

**Tier 5 is the exception** — its whole rationale is using both vendors' different strengths together. `--vendor` is silently ignored there. The phase table above shows the claude variant for tiers 2-4; for the codex variant, swap `claude`↔`codex` throughout.

---

## Dial 2 — Planning complexity

> **"What level of process rigor does this need?"**

The `--robustness` flag. Picks how many phases run and how many critique passes happen. The five levels form a coherent process-completeness scale: **bare → light → full → thorough → extreme**.

**Always run a megaplan, even for tiny work.** The harness captures the brief, plan, execution, and outcome — that record is worth the few extra seconds of overhead. `bare` is the floor; there is no "skip megaplan" option. If the work is too small for `bare` to feel useful, the answer is to invoke `bare` anyway and accept a 3-phase run, not to bypass the harness.

| Setting | Workflow | When to use |
|---|---|---|
| `bare` | plan → finalize → execute (no prep, no critique, no gate, no review) | **The floor — use this when nothing heavier earns its cost.** Single-file fixes, mechanical changes, tasks you'd otherwise do inline. The 3-phase run captures what you did and why, even when critique would be a no-op. Always preferable to skipping the harness. |
| `light` | plan → critique → revise → finalize → execute (no prep, no gate, no review) | Small/scoped, well-known feature, low blast radius — but you want **one** sense-check pass on the plan before committing. ~5 phases instead of 8. |
| `full` *(default)* | prep → plan → critique → gate → revise → finalize → execute → review; 4 critique checks | Cross-cutting, unfamiliar code, ambiguous brief. **This is almost always perfect for everything.** |
| `thorough` | Same shape as `full`, 8 critique checks + parallel critique | Security, data migration, public API contract — anything where a regression = production incident. **Extremely rare.** You should be able to name the specific stakes that warrant it. |
| `extreme` | `thorough` + parallel review | Both deep critique *and* concurrent review matter. **Vanishingly rare.** Only when the user specifically asks for it. |

`full` is home base. `light` is a cost optimization for cleanly-scoped work that still wants a sense-check. `bare` is the floor — used when even one critique pass would be a no-op, but the run still goes through the harness to capture the work. `thorough` should feel exceptional — you're saying "this regression would page someone." `extreme` is a user-requested override, never a default.

Don't reach past `bare` reflexively. The hops are real: `bare` for unambiguous mechanical work, `light` when one critique pass earns its cost, `full` for anything cross-cutting or ambiguous.

Cost bands in the tier table above are at `light`. Roughly 1.5-2× the per-phase cost going from `light` → `full`, and another ~1.3× going to `thorough`.

---

## Dial 3 — Depth

> **"How deeply does each model need to think within the tier I picked?"**

Picks the thinking strength of the premium model(s) the tier brought in. Independent of tier and robustness — orthogonal lever. Spelled out in the agent spec after a colon (`claude:low`, `codex:medium`, etc.).

| Pattern | When to use |
|---|---|
| `low` planner / `low` critic | **The default.** The pattern is mechanical, intuition is enough, the codebase is well-known. A lot of work lands here even at tier 3 — premium models at `low` thinking are still substantially smarter than DeepSeek, so the upgrade isn't free but doesn't need to be expensive either. |
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

"Prep just in case" doesn't earn its cost. Redundant at `thorough` and `extreme` (those already include prep); the flag's value is at `light` and `full`, where prep is normally skipped.

---

## When to add a feedback phase

> **"Do you want a per-stage ratings template waiting on disk when the run finishes?"**

A fifth, narrower lever orthogonal to the three dials. `--with-feedback` adds a `feedback` step between `review` and `done` that scaffolds `feedback.md` (a per-stage ratings template) and then completes the plan. Off by default. Enable with `--with-feedback`.

**Reach for it when at least one of these is true:**

- **You're uncertain whether enough model was used** — there's real ambiguity about whether the tier choice was right, and you want a per-stage record that lets you go back and decide whether to step up (or down) next time.
- **The user specifically requests it.**

The auto driver runs this non-interactively — never blocks on human input, never opens `$EDITOR`. The file is just left on disk. The user fills in `feedback.md` afterward (or ignores it — no reminders, no prompts).

"Feedback just in case" doesn't earn its cost. The template exists to be used; if nobody is going to rate the run, skip the flag.

---

## Notation for recording profile choices

For sprint notes, brief headers, commit messages, or anywhere you need to write down a profile choice compactly, use the slash form: **`profile/robustness/depth`** — defaults can be omitted.

Order is fixed left-to-right: tier → robustness → depth, matching dial numbers 1 → 2 → 3. The `//` reads as "skip the middle slot — defaults there."

### Spine examples (just the three dials)

| What you decided | Shorthand |
|---|---|
| Tier-1 work at default robustness and depth | `solo` |
| Tier-1 work at light robustness | `solo/light` |
| Tier-2 work at defaults | `directed` |
| Tier-3 work at defaults | `partnered` |
| Tier-3 work with depth bumped to high (default robustness) | `partnered//high` |
| Tier-3 work with medium depth (default robustness) | `partnered//medium` |
| Tier-4 work at thorough + high depth | `premium/thorough/high` |
| Apex sprint, thorough + high depth | `apex/thorough/high` |

### With modifiers (secondary flags)

For `--vendor`, `--critic`, `--with-prep`, `--with-feedback`, append modifiers without disturbing the spine. The conventions:

- `@<vendor>` — vendor override (e.g. `@codex`).
- `, critic=<kind>` — critic override (e.g. `, critic=cross`).
- `+prep` — enable the prep phase.
- `+feedback` — enable the feedback phase.

| What you decided | Shorthand |
|---|---|
| Tier-2 work, prefer codex | `directed @codex` |
| Tier-3 work, cross-vendor critic | `partnered, critic=cross` |
| Tier-3 work, needs upfront API discovery | `partnered +prep` |
| Tier-3 work, wants feedback scaffolding | `partnered +feedback` |
| Tier-3 work, novel external API, codex preferred, high depth | `partnered//high @codex +prep` |
| Tier-4 production migration with cross-vendor critic | `premium/thorough/high, critic=cross` |
| Apex sprint with prep | `apex/thorough/high` *(no `+prep` needed — apex includes prep at thorough)* |

### Where to use this

The shorthand is for **recording**, not for the CLI. Use it in:

- Sprint planning docs ("Sprint 14 — `partnered//high +prep`")
- Brief headers (`[premium/thorough/high]` as the first line of a brief)
- Commit messages ("ran as `partnered`, defaults")
- Slack / chat references when describing a sprint setup at a glance

The actual invocation is still `megaplan init --profile … --robustness … --depth …` — see "Running it" below for the mapping.

---

## Running it — profile plus the knobs

The invocation has three layers: three flags for the dials, four modifiers for orthogonal toggles, one escape hatch for surgical needs.

### The three dial flags

1. **`--profile`** — the tier name (`solo`, `directed`, `partnered`, `premium`, `apex`).
2. **`--robustness bare|light|full|thorough|extreme`** — `full` is home base.
3. **`--depth low|medium|high|xhigh|max`** — rewrites the effort suffix on author-side claude/codex slots (plan, revise, loop_plan, tiebreaker_*) at the resolved vendor. Critic + mechanical phases plateau at their existing depth (the asymmetry principle). Defaults to whatever the profile sets (usually `:low`). Honored on vendor-locked profiles. Codex caps at `high`; Claude adds `xhigh` and `max`.

### The modifier flags

- **`--vendor claude|codex`** — vendor override at tiers 2-4. Defaults to `[defaults].vendor` in `~/.config/megaplan/config.toml` (or `claude` if unset). Tier 1 ignores it (no premium phases); tier 5 silently ignores it (vendor-locked).
- **`--critic cross`** — overrides the critique+review pair (preserving the invariant — see below) to the other premium vendor relative to `--vendor`. Silently ignored at tier 5.
- **`--deepseek-provider fireworks|direct`** — swaps canonical DeepSeek v4-pro slots between Fireworks and DeepSeek's direct API. Defaults to `direct`; use `fireworks` as the explicit secondary/fallback route.
- **`--with-prep`** — force the `prep` research phase into the workflow regardless of `--robustness`. Off by default; no-op at `thorough`/`extreme`. See "When to add a prep phase" above.
- **`--with-feedback`** — force the `feedback` phase into the workflow regardless of `--robustness`. Scaffolds `feedback.md` (a per-stage ratings template) between `review` and `done`, then completes the plan non-interactively. Off by default. See "When to add a feedback phase" above.

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

- `megaplan override set-profile --profile NAME --plan ID` — swap tier mid-run. Started on `partnered`, hit something gnarlier, escalate to `premium` for the remainder.
- `megaplan override set-robustness --robustness LEVEL --plan ID` — same for the planning-complexity dial.
- `megaplan override replan --plan ID` — back up to planning and redo with whatever models / robustness are now active.
- `megaplan override add-note --plan ID --note "..."` — inject guidance into an active plan without restarting any phase. Read by every subsequent phase. The brief is snapshotted at `init`; later edits to the idea-file are NOT re-read, so this is the verb for "I missed something." `--source user` (default) blocks `force-proceed` under `--strict-notes`; `--source driver` doesn't. **`megaplan feedback` is end-of-run rating, not in-flight guidance** — common confusion.

**If a run is struggling, escalate mid-flight rather than letting it grind.** Common signals: the plan keeps missing concerns the critique surfaces; revise doesn't actually resolve the critique's flags; the executor produces work the review can't accept; iteration cycles through the same defects without converging. Don't sit through a degenerate run — `override set-profile` to the next tier up (or bump `--robustness`), and let the remainder benefit from the better setup. One wasted phase costs much less than restarting the sprint. The same applies to depth: if the planner is clearly under-deliberating, `override` with a higher `--depth` rather than accepting a thin plan.

Lean on these instead of inventing new profile names. If you find yourself thinking "I want a profile that's *like* `partnered` but with X" — the answer is almost always `partnered` plus an override, not a new profile.

### The critique == review invariant

The model that critiques the plan also reviews the executed work — same mind pre-execution and post-execution. Wiring them to the same non-author model gives you one coherent second mind across both checkpoints and keeps the author's blindspots out of the sense-check loop.

`--critic` bundles the two phases in one flag and preserves the invariant. Bare `--phase-model` does not — if you override critique with `--phase-model`, override review the same way, or use `--critic` instead.

### Worked invocations

> *"Schema migration where step ordering is intricate but each step is mechanical. Prefer codex; brief is clear so default depth is fine."*
> `megaplan init <brief> --profile directed --vendor codex`

> *"Novel feature, cross-cutting, brief is long, codebase is unfamiliar."*
> `megaplan init <brief> --profile partnered --depth high` *(vendor defaults from config; depth lifts plan + revise + loop_plan + tiebreaker_* to claude:high; critic + mechanical stay at their defaults)*

> *"Novel feature involving an external API we haven't used before. Planner needs to read the API docs before committing."*
> `megaplan init <brief> --profile partnered --with-prep --depth medium` *(adds the visible `prep` phase even at `full` robustness, so the planner can survey the API surface before producing a plan)*

> *"Cross-cutting feature, tier 3, but I want the other premium vendor catching what the chosen author missed."*
> `megaplan init <brief> --profile partnered --critic cross`

> *"Migration logic against production data. Tier 4, thorough, deep planner."*
> `megaplan init <brief> --profile premium --robustness thorough --depth high`

> *"Schema everyone downstream will build on. Apex tier."*
> `megaplan init <brief> --profile apex --robustness thorough --depth high`

> *"Tier-3 work, brief is clear, but I want the critic to deliberate a little more — the planner can stay at the profile default."*
> `megaplan init <brief> --profile partnered --phase-model critique=claude:medium --phase-model review=claude:medium` *(surgical: bump just one pair, leave plan + revise at the profile's `:low`. The kind of override `--depth` can't express because it's by-phase-name, not by-author-vs-critic.)*

> *"Verification sprint, mostly text, lowest-stakes thing in the queue."*
> `megaplan init <brief> --profile solo --robustness light`

Three pieces of intent → three flags (`--profile`, `--robustness`, `--depth`), plus `--vendor` / `--critic` / `--with-prep` / `--with-feedback` when you need them.

### Where megaplan runs

**Megaplan defaults to running inside a subagent**, off the main thread — keeping the orchestrating conversation thin while the harness handles its own multi-phase chatter. Running megaplan on-thread is the exception, reserved for cases where the user explicitly wants to watch each phase in the main conversation. The subagent is the venue; megaplan is still the harness — never skip megaplan in favor of "just doing it in a subagent."

### Config defaults

The `--vendor` flag honors a per-user config default. Write `~/.config/megaplan/config.toml`:

```toml
[defaults]
vendor = "claude"   # "claude" or "codex"
```

Set this once on a new machine and tiers 2-4 default to your preferred premium without per-invocation flags. The CLI flag still wins when passed. A malformed or missing config falls back to `claude` silently.

---

## Operating principles

**Brief quality dominates outcome.** See "Sizing and briefing" above — if you only invest in one thing, invest in the brief.

**Where the premium model goes matters more than how many premium models you use.** Concentrating the premium model in author-side phases (plan, revise) gives the biggest cost-quality win. DeepSeek as the executor is fine — premium there is overkill.

**One profile per sprint.** Pick the profile that matches the **highest-stakes deliverable** in the sprint; lower-stakes items inherit the tier. Operational simplicity beats the savings from splitting. Only split when the lower-stakes work is *substantial* (multiple days) **and** independent. Structure the plan so cheap work lives in cheap sprints, not interleaved inside expensive ones.

**Bake-off is opt-in.** Default to a single profile. Only run a multi-arm bake-off when (a) the user asks, (b) three or more mixes are genuinely plausible, (c) the deliverable is a diff worth comparing, and (d) per-arm cost is well below the cost of guessing wrong. Don't bake off discovery / scoping / contract-freeze sprints — no diff to compare.

**Anti-patterns:**

- *"Always use Claude."* Wrong. Codex on author-side phases steers DeepSeek-executor profiles just as well; pick the vendor your subscription has credits on.
- *"Higher thinking strength always helps."* Wrong. Strength plateaus on sense-check duty; spend it on author-side phases only.
- *"Profile choice dominates outcome."* Mostly wrong. Brief quality dominates. If three profiles all produce brief-interpretation defects, fix the brief.
