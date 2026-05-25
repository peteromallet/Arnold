---
name: megaplan-decision
description: Pick the right megaplan profile, thinking-strength tier, and robustness level for the work in front of you — for both Codex and Claude harnesses. Consult before invoking megaplan.
---

# Megaplan Decision

Three dials decide how to run a sprint:

| | Question | Dial | What it scales | Flag |
|---|---|---|---|---|
| 1 | What level of raw capability does this need? | **Intelligence tier** | `$/call` | `--profile` |
| 2 | What level of process rigor does this need? | **Planning complexity** | `# of calls` | `--robustness` |
| 3 | How deeply does each model need to think? | **Depth** | `tokens/call` | `--depth` (with `--phase-model` as the surgical escape hatch) |

**Always run a megaplan, even for tiny work.** The harness captures the brief, plan, execution, and outcome — that record is worth the few seconds of overhead. `bare` is the floor; there is no "skip megaplan" option.

**Run megaplan inside a subagent by default**, off the main thread — keeping the orchestrating conversation thin while the harness handles its own multi-phase chatter. On-thread is the exception, reserved for when you want to watch each phase live. The subagent is the venue; megaplan is still the harness — never skip megaplan in favor of "just doing it in a subagent."

The dials are independent — work through each one ignoring the others — then weigh the three together holistically. A high tier with low robustness is usually a mismatch; so is a low tier with `max` depth. When the three pull in opposite directions, the work probably needs to be split.

**The dials measure residual complexity, not nominal scope.** Discount for decisions already made; add for unknowns remaining. A spec-shaped brief with everything known lands a tier lower than the same nominal scope arriving as a sketch.

**Defaults to keep in mind:** `--robustness full`, `--depth` unset (which means the profile's existing depths win — usually `:low` on premium phases), vendor from your config (`claude` if unset). Reach past those only when you can name the specific reason. Built-in profiles live in `megaplan/profiles/`; per-user (`~/.config/megaplan/profiles.toml`) and per-project (`<project>/.megaplan/profiles.toml`) TOML overrides win over them.

---

## Sizing and briefing

Two decisions come before the three dials: **how many megaplans you need**, and **what each brief covers**. Get these wrong and the dials can't save the run.

### Size each megaplan to ~2 weeks of work

A megaplan should fit roughly **two weeks of human work** — the time a skilled engineer would take to plan, build, and review the same scope. Wall-clock for the harness itself is unrelated; this is about scope, not duration.

If the work is bigger, **split it into an epic** — a chain of sprint-sized megaplans driven sequentially by `megaplan chain`. Each sprint in the chain gets its own brief, its own profile, its own retrospective. See the **megaplan-epic** skill for spec format, per-milestone rubric, and end-to-end usage. Cramming a month of work into one plan means the brief drifts, the critique loses focus, and the review can't hold the whole shape in one pass.

Signs you should split:

- Multiple major architectural decisions — each deserves its own sprint.
- Deliverables with different stakes — high-stakes infra warrants its own sprint, at a higher tier; bundling it with cheap work either over-pays for the cheap work or under-protects the expensive part.
- You can't describe the outcome in one or two sentences.

When you split, structure the dependency graph explicitly. Each handoff is a written artifact — schema, API surface, doc — that the next brief can cite. Sprints without that artifact between them are really one sprint pretending to be two.

**But: one profile per sprint.** Within a sprint, pick the profile that matches the **highest-stakes deliverable** — lower-stakes items inherit the tier. Operational simplicity beats the savings from splitting by stakes alone. Only split when the lower-stakes work is *substantial* (multiple days) **and** independent. Structure the plan so cheap work lives in cheap sprints, not interleaved inside expensive ones.

### What goes in the brief

**Tightening the brief beats picking a higher tier** — and is usually cheaper. Invest here before anywhere else.

**The brief must be locked in before init** — fully self-contained so the model can run end-to-end without coming back for clarification. The harness snapshots the brief at `init`; later edits to the idea-file are not re-read. If you find yourself wanting to "ask the model" what to do, write that decision down first.

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
| 1 | **`solo`** | One non-premium model working alone across every phase. Discovery, docs, schema migrations, ports of self-contained code, utility scripts, config changes, mechanical refactors, CRUD over existing schemas, test fixtures — anything where patterns are stable and overlapping concerns are few. This is already the floor; if it feels like too much, `bare` robustness is the answer, not a lower tier. | ~$0.50-2 |
| 2 | **`directed`** | A premium model writes the plan; DeepSeek executes it. Complex schema migrations where step ordering matters, multi-step refactors needing careful sequencing, features whose architecture demands deliberation but whose code follows patterns, greenfield implementations with non-trivial design but well-shaped pieces. Drop down to `solo` when the plan is obvious — DeepSeek can plan mechanical work just fine. | ~$1-3 |
| 3 | **`partnered`** | Premium and DeepSeek working together — premium handles plan, revise, and review; critique now runs on cheap DeepSeek *directed by the premium critique-evaluator* (adaptive critique on by default), and DeepSeek handles the mechanical phases. New CLI commands with cross-cutting concerns, inbox/routing rewrites, adapters with non-trivial edge cases, export/import surfaces with format edge cases, novel features in known architecture, refactors with real cross-system implications. Drop down to `directed` when patterns are stable and variables are few — `partnered` is for genuinely novel or cross-cutting work. | ~$5-15 |
| 4 | **`premium`** | Premium mind everywhere — DeepSeek exits; single-vendor premium end-to-end. Schema definitions, wire formats, security-critical code paths, public API contracts, migration logic against production data, kernel-invariant changes. Drop down to `partnered` when the execution is mechanical once mapped out — decision-difficulty alone doesn't justify tier 4. | ~$30-70 |
| 5 | **`apex`** | Both Claude and Codex contributing — the only tier where the two premium models stop being interchangeable. Concurrency primitives that cascade, schemas all later sprints build on, wire formats / claim semantics, multi-system migration decisions, huge architectural choices. Drop down to `premium` unless (a) high-stakes — regression = production incident — or (b) the sprint is making a huge architectural decision, and the execution has enough detail to warrant premium implementing it. | ~$30-50 |

Tiers 4 and 5 are the only tiers where a premium model executes the code, not just reasons about it — reach for them when the *implementation* itself is nuanced, not just the decision. Tier 5 specifically combines Claude and Codex's different strengths (Opus on author/repo-reading, Codex on critique/structural-analysis); that pairing is its whole rationale.

### Which model handles each phase

| Phase | solo | directed | partnered | premium | apex |
|---|---|---|---|---|---|
| **plan**     | DeepSeek | claude   | claude   | claude | claude |
| **prep**     | DeepSeek | DeepSeek | DeepSeek | claude | claude |
| **critique** | DeepSeek | DeepSeek | DeepSeek | claude | codex  |
| **revise**   | DeepSeek | DeepSeek | claude   | claude | claude |
| **gate**     | DeepSeek | DeepSeek | DeepSeek | claude | claude |
| **finalize** | DeepSeek | DeepSeek | DeepSeek | claude | claude |
| **execute**  | DeepSeek | DeepSeek | DeepSeek | claude | codex  |
| **review**   | DeepSeek | DeepSeek | claude   | claude | codex  |

Legend:

- **DeepSeek** = DeepSeek V4 Pro (open-source workhorse; competent, structured, non-premium).
- **claude** = Claude Opus 4.7. **codex** = Codex GPT-5.5.

Each tier upgrades one block of phases to premium; once upgraded, a phase stays upgraded. Tier 5 doesn't add coverage — it splits premium across two vendors.

### Adaptive critique — premium direction, cheap execution

For the premium-bearing profiles (**`partnered`**, **`premium`**, **`apex`**) adaptive critique is **on by default**. Instead of running every critique lens on the profile's critique model, a premium **critique-evaluator** reads the finished plan and *adjudicates* the critique: it decides which of the lenses fire (justifying every skip), routes each surviving lens to the **cheapest critic in the roster that can do it justice**, and escalates to a premium critic only for the lenses that genuinely demand deeper judgment. In `partnered` the critique slot itself is cheap DeepSeek — the cheap slot is precisely what *triggers* the premium evaluator to take the wheel, rather than something it fights.

This is the concrete embodiment of megaplan's model philosophy — *cheapest capable model per task; premium reserved for adjudication and the genuinely hard work* — applied to the critique phase: the expensive premium judgment goes into **deciding and directing**, while the bulk of the lens-by-lens grinding runs cheap.

Adaptive critique is **off for the open-only profiles** (`solo`, `directed`): there is no premium model in those tiers to direct with, and forcing one in would push a premium key into an otherwise key-free setup. Force it on for any profile with `--adaptive-critique`; pin `[execution].adaptive_critique` in config to override the per-profile default in either direction.

### Vendor: Claude and Codex are mostly interchangeable at tiers 2-4

**Claude and Codex are treated as mostly interchangeable at tiers 2-4 — by policy, not just by observation.** The marginal quality difference between them on a given task is small relative to picking the wrong tier or robustness; encoding per-task vendor preferences would add a dial that doesn't earn its keep. Users may prefer one or the other depending on which subscription has more credits available — pick a preferred vendor once (`--vendor`, or `[defaults].vendor` in config) and the preference flows through every tier-2-through-4 profile.

**Tier 5 is the exception** — its whole rationale is using both vendors' different strengths together. `--vendor` is silently ignored there. The phase table above shows the claude variant for tiers 2-4; for the codex variant, swap `claude`↔`codex` throughout.

---

## Dial 2 — Planning complexity

> **"What level of process rigor does this need?"**

The `--robustness` flag. Picks how many phases run and how many critique passes happen. The five levels form a coherent process-completeness scale: **bare → light → full → thorough → extreme**.

| Setting | Workflow | When to use |
|---|---|---|
| `bare` | plan → finalize → execute (no prep, no critique, no gate, no review) | **The floor — use this when nothing heavier earns its cost.** Single-file fixes, mechanical changes, tasks you'd otherwise do inline. The 3-phase run captures what you did and why, even when critique would be a no-op. Always preferable to skipping the harness. |
| `light` | plan → critique → revise → finalize → execute (no prep, no gate, no review) | Small/scoped, well-known feature, low blast radius — but you want **one** sense-check pass on the plan before committing. ~5 phases instead of 8. |
| `full` *(default)* | prep → plan → critique → gate → revise → finalize → execute → review; 4 critique checks | Cross-cutting, unfamiliar code, ambiguous brief. **This is almost always perfect for everything.** |
| `thorough` | Same shape as `full`, 8 critique checks + parallel critique | Security, data migration, public API contract — anything where a regression = production incident. **Extremely rare.** You should be able to name the specific stakes that warrant it. |
| `extreme` | `thorough` + parallel review | Both deep critique *and* concurrent review matter. **Vanishingly rare.** Only when the user specifically asks for it. |

Cost scales ~1.5-2× from `light` → `full`, another ~1.3× to `thorough`.

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

## When the dials turn out wrong — mid-flight escalation

**If a run is struggling, escalate mid-flight rather than letting it grind.** Common signals: the plan keeps missing concerns critique surfaces; revise doesn't resolve the critique's flags; the executor produces work review can't accept; iteration cycles through the same defects without converging. Don't sit through a degenerate run — one wasted phase costs much less than restarting the sprint.

- `megaplan override set-profile --profile NAME --plan ID` — swap tier mid-run. Started on `partnered`, hit something gnarlier, escalate to `premium` for the remainder.
- `megaplan override set-robustness --robustness LEVEL --plan ID` — same for the planning-complexity dial.
- `megaplan override replan --plan ID` — back up to planning and redo with whatever models / robustness are now active.
- `megaplan override add-note --plan ID --note "..."` — inject guidance into an active plan without restarting any phase. Read by every subsequent phase. The brief is snapshotted at `init`; later edits to the idea-file are NOT re-read, so this is the verb for "I missed something." **`megaplan feedback` is end-of-run rating, not in-flight guidance** — common confusion.

Lean on these instead of inventing new profile names. If you find yourself thinking "I want a profile that's *like* `partnered` but with X" — the answer is almost always `partnered` plus an override, not a new profile.

---

## Optional phases (`--with-prep`, `--with-feedback`)

Two narrower levers orthogonal to the three dials. Both off by default.

### Prep (`--with-prep`)

> **"Does the planner need to do explicit research before it can commit to a plan?"**

`prep` is a visible research phase that runs *before* `plan` — the planner explicitly reads external docs, surveys an unfamiliar library, maps an API surface, or disambiguates a vague brief. Enable with `--with-prep`.

**Reach for it when at least one of these is true:**

- **External APIs whose semantics aren't already known** — the planner has to read API docs before deciding what calls to make.
- **Unfamiliar libraries or frameworks** — codebase patterns aren't enough; the planner needs to survey the library's API surface first.
- **Research-heavy briefs** — the work is research-bounded ("figure out how X behaves, then implement").
- **Ambiguous or under-specified requirements** — the planner needs a budget to disambiguate explicitly instead of interleaving with planning.
- **Integration work where target-system behavior must be discovered** — wire formats, error semantics, performance characteristics undocumented in the codebase.

"Prep just in case" doesn't earn its cost. Redundant at `thorough` and `extreme` (those already include prep); the flag's value is at `light` and `full`, where prep is normally skipped.

**Steering prep with `--prep-direction`.** When prep runs (either via `--with-prep` or because robustness is `thorough`/`extreme`), you can hand it explicit guidance about *what* to explore: `megaplan init … --prep-direction "focus on the worker shutdown path; ignore CLI plumbing"`. It's shown to the prep worker as a distinct "User direction for prep" section — steering, not a replacement for the task. Use it when prep would otherwise wander (broad codebase, multiple plausible entry points) or when you want it to skip the obvious file and trace a specific call chain. You can also set or replace it after init with `megaplan prep --direction "…"` before the phase runs, and chain milestones accept `prep_direction:` per milestone. Has no effect if prep is skipped.

### Feedback (`--with-feedback`)

> **"Do you want a per-stage ratings template waiting on disk when the run finishes?"**

`--with-feedback` adds a `feedback` step between `review` and `done` that scaffolds `feedback.md` (a per-stage ratings template) and then completes the plan. Enable with `--with-feedback`.

**Reach for it when at least one of these is true:**

- **You're uncertain whether enough model was used** — there's real ambiguity about whether the tier choice was right, and you want a per-stage record that lets you go back and decide whether to step up (or down) next time.
- **The user specifically requests it.**

The auto driver runs this non-interactively — never blocks on human input, never opens `$EDITOR`. The file is just left on disk. The user fills in `feedback.md` afterward (or ignores it — no reminders, no prompts).

"Feedback just in case" doesn't earn its cost. The template exists to be used; if nobody is going to rate the run, skip the flag.

---

## Notation

Write `profile/robustness/depth`, omit defaults, append modifiers. Order is fixed left-to-right: tier → robustness → depth, matching dial numbers 1 → 2 → 3. The `//` reads as "skip the middle slot — defaults there."

| Shorthand | Meaning |
|---|---|
| `solo` | Tier 1, defaults throughout |
| `partnered//high` | Tier 3, high depth, default robustness |
| `partnered//high @codex +prep` | Tier 3, high depth, codex vendor, with prep phase |
| `premium/thorough/high, critic=cross` | Tier 4, thorough, high depth, cross-vendor critic |
| `apex/thorough/high` | Tier 5, thorough, high depth (no `+prep` needed — apex includes prep at thorough) |

Modifier conventions: `@<vendor>` for vendor override, `, critic=<kind>` for critic override, `+prep` to enable prep, `+feedback` to enable feedback. Append modifiers without disturbing the spine.

The shorthand is for recording (sprint notes, brief headers, commit messages), not for the CLI. The actual invocation is still `megaplan init --profile … --robustness … --depth …` — see "Running it" below.

---

## Running it — profile plus the knobs

The invocation has three layers: three flags for the dials, four modifiers for orthogonal toggles, one escape hatch for surgical needs.

### The three dial flags

1. **`--profile`** — the tier name (`solo`, `directed`, `partnered`, `premium`, `apex`).
2. **`--robustness bare|light|full|thorough|extreme`** — `full` is home base.
3. **`--depth low|medium|high|xhigh|max`** — rewrites the effort suffix on author-side claude/codex slots (plan, revise, loop_plan, tiebreaker_*) at the resolved vendor. Critic + mechanical phases plateau at their existing depth (the asymmetry principle). Defaults to whatever the profile sets (usually `:low`). Honored on vendor-locked profiles. Codex caps at `high`; Claude adds `xhigh` and `max`.

### The modifier flags

- **`--vendor claude|codex`** — vendor override at tiers 2-4. Defaults to `[defaults].vendor` in `~/.config/megaplan/config.toml` (or `claude` if unset). Tier 1 ignores it (no premium phases); tier 5 silently ignores it (vendor-locked).
- **`--critic cross`** — overrides the critique+review pair to the other premium vendor relative to `--vendor`. Silently ignored at tier 5.
- **`--deepseek-provider fireworks|direct`** — swaps canonical DeepSeek v4-pro slots between Fireworks and DeepSeek's direct API. Defaults to `direct`; use `fireworks` as the explicit secondary/fallback route.
- **`--with-prep`** — force the `prep` research phase into the workflow regardless of `--robustness`. Off by default; no-op at `thorough`/`extreme`. See "Optional phases" above.
- **`--prep-direction "…"`** — steering text shown to the prep worker (when prep runs) as a "User direction for prep" section. Points prep at specific files / subsystems / questions to explore. Can also be set or replaced later with `megaplan prep --direction "…"` before the phase runs. No-op if prep is skipped. See "Optional phases" above.
- **`--with-feedback`** — force the `feedback` phase into the workflow regardless of `--robustness`. Scaffolds `feedback.md` (a per-stage ratings template) between `review` and `done`, then completes the plan non-interactively. Off by default. See "Optional phases" above.

### The escape hatch

**`--phase-model phase=spec`**, repeatable. For when `--depth` is too coarse — e.g. bump just `critique` without touching the rest. Most runs don't need it.

### The critique == review invariant

The model that critiques the plan also reviews the executed work — same mind pre-execution and post-execution. Wiring them to the same non-author model gives you one coherent second mind across both checkpoints and keeps the author's blindspots out of the sense-check loop.

`--critic` bundles the two phases in one flag and preserves the invariant. Bare `--phase-model` does not — if you override critique with `--phase-model`, override review the same way, or use `--critic` instead.

**Exception — `partnered`:** here critique runs on cheap DeepSeek under the premium *critique-evaluator's* direction (adaptive critique is on by default), while review stays premium. The premium **director** — not a strict same-model invariant — is what keeps the critique phase honest: the evaluator picks the lenses the cheap critic runs and rejects weak findings, so you get premium-grade critique judgment without paying for a premium critic model on every lens.

### Worktree isolation — `--in-worktree`

`megaplan init --in-worktree NAME` spins up a dedicated git worktree at `~/Documents/.megaplan-worktrees/<NAME>/` on a new branch, so each sprint lives in its own checkout. Use it for multi-PR migrations, or when concurrent work on `main` shouldn't be disturbed. Substitutes for `--project-dir`.

- **`--worktree-from GITREF`** — fork from a specific branch/tag/SHA instead of `HEAD`.
- **`--clean-worktree`** — fork from a clean base. By default, uncommitted state in the invoking repo is replicated into the new worktree (the source repo's working tree is never touched).

Safe to use: never runs stash/checkout/reset against the source, refuses on busy repo states (mid-rebase/merge/cherry-pick/bisect) and name collisions, atomic on failure.

Skip `--in-worktree` for small one-shot plans, bakeoff runs (orchestrator manages its own worktrees), or when extending an existing worktree (use `--project-dir <path>` instead).

### Worked invocations

> *"Schema migration, step ordering intricate but each step mechanical."*
> `megaplan init <brief> --profile directed`

> *"Novel cross-cutting feature, long brief, unfamiliar codebase."*
> `megaplan init <brief> --profile partnered --depth high`

> *"Novel feature against an external API we haven't used."*
> `megaplan init <brief> --profile partnered --with-prep`

> *"Migration logic against production data."*
> `megaplan init <brief> --profile premium --robustness thorough --depth high`

> *"Schema everyone downstream will build on — concurrency primitive, cascading consequences."*
> `megaplan init <brief> --profile apex --robustness thorough --depth high`

> *"Tier 3, brief is clear, but I want the critic specifically to deliberate more — leave the planner alone."*
> `megaplan init <brief> --profile partnered --phase-model critique=claude:medium --phase-model review=claude:medium` *(surgical: bumps just the critic+review pair — preserving the critique==review invariant — and leaves plan/revise at the profile's default. `--depth` can't express this because it's by-phase-name, not by-author-vs-critic.)*

Three pieces of intent → three flags (`--profile`, `--robustness`, `--depth`), plus `--vendor` / `--critic` / `--with-prep` / `--with-feedback` / `--in-worktree` when you need them.

### Config defaults

The `--vendor` flag honors a per-user config default. Write `~/.config/megaplan/config.toml`:

```toml
[defaults]
vendor = "claude"   # "claude" or "codex"
```

Set this once on a new machine and tiers 2-4 default to your preferred premium without per-invocation flags. The CLI flag still wins when passed. A malformed or missing config falls back to `claude` silently.

---

## Bake-off

Default to a single profile. Only run a multi-arm bake-off when (a) the user asks, (b) three or more mixes are genuinely plausible, (c) the deliverable is a diff worth comparing, and (d) per-arm cost is well below the cost of guessing wrong. Don't bake off discovery / scoping / contract-freeze sprints — no diff to compare.

---

## Watching and diagnosing a running plan

This skill covers profile/robustness/depth selection *before* a run. Once a plan is in flight, switch to the **`megaplan-observe`** skill — same author, complementary focus:

- **Pull-mode observation**: `megaplan introspect` / `trace` / `doctor` for on-demand inspection, blockage diagnosis, drift detection. Read it before reaching for `override` so you don't guess at an `invalid_transition`.
- **Push-mode observation**: `watcher.sh` (bundled in the same skill) is a bash polling loop that streams phase-transition notifications. Wire it through Claude Code's `Monitor` tool to get told when phases start/end, when cost climbs, and when the plan reaches a terminal state — no manual polling.

When something looks wrong during a run (cost spiking, phase not advancing, iteration counter stuck), `megaplan-observe` is the next stop, not `--max-cost-usd`. The cost-cap and rework-cap flags exist for narrow recovery cases; they are not a default. Trust the defaults; intervene with `override` + tests if a phase fixates.
