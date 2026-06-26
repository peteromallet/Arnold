---
name: megaplan-prep
description: Set up a megaplan run before invoking it — size the work, write the brief, score overall plan difficulty, and choose robustness/depth. Consult before every `python -m arnold_pipelines.megaplan init`.
---

# Megaplan Setup

Three dials decide how to run a sprint:

| | Question | Dial | What it scales | Flag |
|---|---|---|---|---|
| 1 | How model-quality-sensitive is the planning loop? | **Overall plan difficulty** | model quality for plan/revise/finalize | `--profile partnered-3|partnered-4|partnered-5` |
| 2 | What level of process rigor does this need? | **Planning complexity** | `# of calls` | `--robustness` |
| 3 | How deeply does each model need to think? | **Depth** | `tokens/call` | `--depth` (with `--phase-model` as the surgical escape hatch) |

**Always run a megaplan, even for tiny work.** The harness captures the brief, plan, execution, and outcome — that record is worth the few seconds of overhead. `bare` is the floor; there is no "skip megaplan" option.

**Run megaplan inside a subagent by default**, off the main thread — keeping the orchestrating conversation thin while the harness handles its own multi-phase chatter. On-thread is the exception, reserved for when you want to watch each phase live. The subagent is the venue; megaplan is still the harness — never skip megaplan in favor of "just doing it in a subagent."

The dials are independent — work through each one ignoring the others — then weigh the three together holistically. A high tier with low robustness is usually a mismatch; so is a low tier with `max` depth. When the three pull in opposite directions, the work probably needs to be split.

**The dials measure residual complexity, not nominal scope.** Discount for decisions already made; add for unknowns remaining. A spec-shaped brief with everything known lands a tier lower than the same nominal scope arriving as a sketch.

**Defaults to keep in mind:** score the run first; use `--profile partnered-3 --vendor codex` for overall plan difficulty 1–3, `partnered-4` for 4, and `partnered-5` for 5. Keep `--robustness full` and `--depth` unset unless you can name the specific reason to change them. Built-in profiles live in `megaplan/profiles/`; per-user (`~/.config/megaplan/profiles.toml`) and per-project (`<project>/.megaplan/profiles.toml`) TOML overrides win over them.

---

## Sizing and briefing

Two decisions come before the three dials: **how many megaplans you need**, and **what each brief covers**. Get these wrong and the dials can't save the run.

### Size each megaplan to ~2 weeks of work

A megaplan should fit roughly **two weeks of human work** — the time a skilled engineer would take to plan, build, and review the same scope. Wall-clock for the harness itself is unrelated; this is about scope, not duration.

If the work is bigger, **split it into an epic** — a chain of sprint-sized megaplans driven sequentially by `python -m arnold_pipelines.megaplan chain`. Each sprint in the chain gets its own brief, its own overall plan difficulty score, its own profile, and its own retrospective. See the **megaplan-epic** skill for spec format, per-milestone rubric, and end-to-end usage. Cramming a month of work into one plan means the brief drifts, the critique loses focus, and the review can't hold the whole shape in one pass.

For epics, migrations, public contract changes, or cross-cutting refactors, write a North Star before kickoff. The North Star is the durable end-state intent that every milestone should preserve; milestone briefs should narrow local scope without redefining that destination. Epics require a top-level `anchors.north_star` by default; single-plan North Stars remain optional.

Signs you should split:

- Multiple major architectural decisions — each deserves its own sprint.
- Deliverables with different stakes — high-stakes infra warrants its own sprint, at a higher tier; bundling it with cheap work either over-pays for the cheap work or under-protects the expensive part.
- You can't describe the outcome in one or two sentences.

When you split, structure the dependency graph explicitly. Each handoff is a written artifact — schema, API surface, doc — that the next brief can cite. Sprints without that artifact between them are really one sprint pretending to be two.

**But: one profile per sprint.** Within a sprint, score the overall planning difficulty for the sprint as a whole. Operational simplicity beats the savings from splitting by difficulty alone. Only split when lower-difficulty work is *substantial* (multiple days) **and** independent. Structure the plan so easier work lives in easier sprints, not interleaved inside harder ones.

### What goes in the brief

**Tightening the brief beats picking a higher tier** — and is usually cheaper. Invest here before anywhere else.

**The brief must be locked in before init** — fully self-contained so the model can run end-to-end without coming back for clarification. The harness snapshots the brief at `init`; later edits to the idea-file are not re-read. If you find yourself wanting to "ask the model" what to do, write that decision down first.

**Store durable briefs in `.megaplan/briefs/`.** Single-plan ideas live at `.megaplan/briefs/<slug>.md`. Epics live at `.megaplan/briefs/<epic-slug>/chain.yaml` with their milestone briefs in the same directory. `.megaplan/plans/` is generated run state; `.megaplan/briefs/` is the committed input material you hand to `python -m arnold_pipelines.megaplan init` or `python -m arnold_pipelines.megaplan chain start`. Use `python -m arnold_pipelines.megaplan brief new` or `python -m arnold_pipelines.megaplan brief epic` to create the canonical files.

For single plans, pass `--north-star path/to/NORTHSTAR.md` at `init` when the local brief needs durable alignment context. This is optional, but strongly recommended for drift-sensitive standalone plans: migrations, public contracts, cross-cutting refactors, multi-agent handoffs, or any task where local success criteria could accidentally narrow the intended destination. For epics, keep `NORTHSTAR.md` beside `chain.yaml` and declare it as `anchors.north_star`; `brief epic` scaffolds this by default and chain runs require it unless explicitly opted out. Anchor files are snapshotted into plan state at initialization, so edit the source before starting the run.

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

## Dial 1 — Overall Plan Difficulty

> **"How model-quality-sensitive is the planning/revision/adjudication loop?"**

Score the whole plan's residual difficulty from **1 to 5** before choosing the profile. This is not the same as per-task execution complexity: it decides how strong the planning/revision/adjudication loop should be for the run as a whole. Task execution still gets routed later by `finalize` through `tier_models.execute`.

The score is intentionally more granular than the profile map: scores `1`, `2`, and `3` all use `partnered-3`. The extra resolution is for auditability and repeatability, not fake precision. Only move to `partnered-4` or `partnered-5` when the plan itself is model-quality-sensitive.

| Score | Profile | Use when |
|---|---|---|
| `1` | `partnered-3` | Small, local, well-specified work with obvious files and tests. |
| `2` | `partnered-3` | Moderate implementation where patterns are known and failure is easy to detect. |
| `3` | `partnered-3` | Default for real engineering work: some judgment calls, but no unusually hard architecture or validation problem. |
| `4` | `partnered-4` | Hard planning or decomposition: unfamiliar code, cross-system behavior, subtle ordering, import/package topology, or a difficult task-difficulty adjudication problem. |
| `5` | `partnered-5` | Highest-stakes or hardest plans: architecture pivots, production data, security, public contracts, migrations, or failures that could pass tests while causing non-local damage. |

Use these guardrails:

- Do not upscore for size alone. Large repetitive work should split into an epic, raise `--robustness`, or cap execution spend; it should not become `partnered-5` just because there are many edits.
- Raise to `4` for package moves, import graph changes, public re-exports, shared initialization paths, dependency inversion, or other topology work, even when the desired behavior is unchanged.
- Use `5` when a bad plan could still pass local tests while damaging a contract, invariant, migration path, data model, security boundary, or downstream architecture.
- Score the highest plausible planning failure, not the scariest noun. Production data, auth, or schemas do not automatically mean `5` if the actual change is local and well-proven.

When genuinely torn between two scores, choose the lower score and raise `--depth` or `--robustness` first, unless the specific risk is bad task decomposition, bad task-difficulty adjudication, or a bad architecture choice. Those are profile-selection risks.

Use the dials separately:

- Unclear requirements or missing context -> `--with-prep` or higher `--robustness`.
- Need more deliberation from the same planner -> higher `--depth`.
- Need a better model for decomposition/adjudication/architecture -> higher profile.

Always record the choice in the prep output:

```text
Overall plan difficulty: N/5; selected profile: partnered-3|partnered-4|partnered-5; because: <one sentence naming the planning failure being guarded against>.
```

---

## Dial 2 — Planning complexity

> **"What level of process rigor does this need?"**

The `--robustness` flag. Picks how many phases run and how many critique passes happen. The five levels form a coherent process-completeness scale: **bare → light → full → thorough → extreme**.

| Setting | Workflow | When to use |
|---|---|---|
| `bare` | plan → finalize → execute (no prep, no critique, no gate, no review) | **The floor — use this when nothing heavier earns its cost.** Single-file fixes, mechanical changes, tasks you'd otherwise do inline. The 3-phase run captures what you did and why, even when critique would be a no-op. Always preferable to skipping the harness. |
| `light` | plan → critique → revise → finalize → execute (no prep, no gate, no review) | Small/scoped, well-known feature, low blast radius — but you want **one** sense-check pass on the plan before committing. ~5 phases instead of 8. |
| `full` *(default)* | prep → plan → critique → gate → revise → finalize → execute → review; up to 6 critique lenses | Cross-cutting, unfamiliar code, ambiguous brief. **This is almost always perfect for everything.** |
| `thorough` | Same shape as `full`, up to 9 critique lenses + parallel critique | Security, data migration, public API contract — anything where a regression = production incident. **Extremely rare.** You should be able to name the specific stakes that warrant it. |
| `extreme` | `thorough` + parallel review | Both deep critique *and* concurrent review matter. **Vanishingly rare.** Only when the user specifically asks for it. |

Cost scales ~1.5-2× from `light` → `full`, another ~1.3× to `thorough`.

The "critique lenses" counts above are the **static** lens pools used when adaptive critique is **off**. When adaptive critique is **on**, the evaluator selects which lenses fire from the same 9-lens catalog per iteration — the robustness dial no longer fixes a count; the evaluator does (see [`docs/critique.md`](critique.md)). Robustness still governs the surrounding workflow shape (whether `gate`/`review` run, whether prep/parallel critique are forced).

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

- `python -m arnold_pipelines.megaplan override set-profile --profile NAME --plan ID` — swap profile mid-run. Started on `partnered-3`, hit something gnarlier, escalate to `partnered-4` or `partnered-5` for the remainder.
- `python -m arnold_pipelines.megaplan override set-robustness --robustness LEVEL --plan ID` — same for the planning-complexity dial.
- `python -m arnold_pipelines.megaplan override replan --plan ID` — back up to planning and redo with whatever models / robustness are now active.
- `python -m arnold_pipelines.megaplan override add-note --plan ID --note "..."` — inject guidance into an active plan without restarting any phase. Read by every subsequent phase. The brief is snapshotted at `init`; later edits to the idea-file are NOT re-read, so this is the verb for "I missed something." **`python -m arnold_pipelines.megaplan feedback` is end-of-run rating, not in-flight guidance** — common confusion.

Lean on these instead of inventing more profile names. If you find yourself thinking "I want a profile that's *like* `partnered-3` but with X" — the answer is usually `partnered-3` plus an override, unless it matches the explicit `partnered-4` or `partnered-5` rubric above.

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

**Steering prep with `--prep-direction`.** When prep runs (either via `--with-prep` or because robustness is `thorough`/`extreme`), you can hand it explicit guidance about *what* to explore: `python -m arnold_pipelines.megaplan init … --prep-direction "focus on the worker shutdown path; ignore CLI plumbing"`. It's shown to the prep worker as a distinct "User direction for prep" section — steering, not a replacement for the task. Use it when prep would otherwise wander (broad codebase, multiple plausible entry points) or when you want it to skip the obvious file and trace a specific call chain. You can also set or replace it after init with `python -m arnold_pipelines.megaplan prep --direction "…"` before the phase runs, and chain milestones accept `prep_direction:` per milestone. Has no effect if prep is skipped.

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
| `partnered-3` | Overall plan difficulty 1–3, defaults throughout |
| `partnered-4//high` | Overall plan difficulty 4, high depth, default robustness |
| `partnered-3//high @codex +prep` | Overall plan difficulty 1–3, high depth, codex vendor, with prep phase |
| `partnered-5/thorough/high` | Overall plan difficulty 5, thorough, high depth |

Modifier conventions: `@<vendor>` for vendor override, `, critic=<kind>` for critic override, `+prep` to enable prep, `+feedback` to enable feedback. Append modifiers without disturbing the spine.

The shorthand is for recording (sprint notes, brief headers, commit messages), not for the CLI. The actual invocation is still `python -m arnold_pipelines.megaplan init --profile … --robustness … --depth …` — see "Running it" below.

---

## Running it — profile plus the knobs

The invocation has three layers: three flags for the dials, four modifiers for orthogonal toggles, one escape hatch for surgical needs.

### The three dial flags

1. **`--profile`** — `partnered-3`, `partnered-4`, or `partnered-5`, chosen from the overall plan difficulty score.
2. **`--robustness bare|light|full|thorough|extreme`** — `full` is home base.
3. **`--depth low|medium|high|xhigh|max`** — rewrites the effort suffix on author-side claude/codex slots (plan, revise, loop_plan, tiebreaker_*) at the resolved vendor. Critic + mechanical phases plateau at their existing depth (the asymmetry principle). Defaults to whatever the profile sets (usually `:low`). Honored on vendor-locked profiles. Codex caps at `high`; Claude adds `xhigh` and `max`.

### The modifier flags

- **`--vendor claude|codex`** — vendor override where the selected profile exposes premium vendor slots. Defaults to `[defaults].vendor` in `~/.config/megaplan/config.toml` (or `claude` if unset).
- **`--critic cross`** — overrides the critique+review pair to the other premium vendor relative to `--vendor`, when supported by the selected profile.
- **`--deepseek-provider direct`** — keeps canonical DeepSeek v4-pro slots on DeepSeek's direct API. Defaults to `direct`; Fireworks is not a supported DeepSeek route.
- **`--with-prep`** — force the `prep` research phase into the workflow regardless of `--robustness`. Off by default; no-op at `thorough`/`extreme`. See "Optional phases" above.
- **`--prep-direction "…"`** — steering text shown to the prep worker (when prep runs) as a "User direction for prep" section. Points prep at specific files / subsystems / questions to explore. Can also be set or replaced later with `python -m arnold_pipelines.megaplan prep --direction "…"` before the phase runs. No-op if prep is skipped. See "Optional phases" above.
- **`--with-feedback`** — force the `feedback` phase into the workflow regardless of `--robustness`. Scaffolds `feedback.md` (a per-stage ratings template) between `review` and `done`, then completes the plan non-interactively. Off by default. See "Optional phases" above.

### The escape hatch

**`--phase-model phase=spec`**, repeatable. For when `--depth` is too coarse — e.g. bump just `critique` without touching the rest. Most runs don't need it.

For an in-flight plan, `python -m arnold_pipelines.megaplan override set-model --phase PHASE --model MODEL`
updates that phase's persisted `phase_model` entry. If you are switching premium
vendors, pass a full premium spec such as `--model claude:sonnet` or
`--model codex:gpt-5.5`; passing only `--model sonnet` keeps the phase's
currently inferred premium agent and changes only its model token.

Important: `--phase-model critique=...` and `override set-model --phase critique`
pin the critique **phase/orchestrator**. They do not by themselves pin the
per-lens critics chosen by adaptive critique. In the normal adaptive path, a
premium evaluator/director may run first and then dispatch the selected critique
lenses to cheaper DeepSeek/Kimi-style workers; seeing `critique_evaluator` on a
premium model followed by `critique` on Hermes/DeepSeek is expected. Only pin
`execution.critic_model` when you intentionally want to override that adaptive
critic-worker routing.

### The critique == review invariant

The model that critiques the plan also reviews the executed work — same mind pre-execution and post-execution. Wiring them to the same non-author model gives you one coherent second mind across both checkpoints and keeps the author's blindspots out of the sense-check loop.

`--critic` bundles the two phases in one flag and preserves the invariant. Bare `--phase-model` does not — if you override critique with `--phase-model`, override review the same way, or use `--critic` instead.

**Exception — `partnered-*`:** critique may run on cheap DeepSeek under the premium *critique-evaluator's* direction (adaptive critique is on by default), while review stays premium. The premium **director** — not a strict same-model invariant — is what keeps the critique phase honest: the evaluator picks the lenses the cheap critic runs and rejects weak findings, so you get premium-grade critique judgment without paying for a premium critic model on every lens.

### Worktree isolation — `--in-worktree`

`python -m arnold_pipelines.megaplan init --in-worktree NAME` spins up a dedicated git worktree at `~/Documents/.megaplan-worktrees/<NAME>/` on a new branch, so each sprint lives in its own checkout. Use it for multi-PR migrations, or when concurrent work on `main` shouldn't be disturbed. Substitutes for `--project-dir`.

- **`--worktree-from GITREF`** — fork from a specific branch/tag/SHA instead of `HEAD`.
- **`--clean-worktree`** — fork from a clean base. By default, uncommitted state in the invoking repo is replicated into the new worktree (the source repo's working tree is never touched).

Safe to use: never runs stash/checkout/reset against the source, refuses on busy repo states (mid-rebase/merge/cherry-pick/bisect) and name collisions, atomic on failure.

Skip `--in-worktree` for small one-shot plans, bakeoff runs (orchestrator manages its own worktrees), or when extending an existing worktree (use `--project-dir <path>` instead).

### Worked invocations

> *"Schema migration, step ordering intricate but each step mechanical."*
> `python -m arnold_pipelines.megaplan init <brief> --profile partnered-3`

> *"Novel cross-cutting feature, long brief, unfamiliar codebase."*
> `python -m arnold_pipelines.megaplan init <brief> --profile partnered-4 --depth high`

> *"Novel feature against an external API we haven't used."*
> `python -m arnold_pipelines.megaplan init <brief> --profile partnered-3 --with-prep`

> *"Migration logic against production data."*
> `python -m arnold_pipelines.megaplan init <brief> --profile partnered-5 --robustness thorough --depth high`

> *"Schema everyone downstream will build on — concurrency primitive, cascading consequences."*
> `python -m arnold_pipelines.megaplan init <brief> --profile partnered-5 --robustness thorough --depth high`

> *"Tier 3, brief is clear, but I want the critic specifically to deliberate more — leave the planner alone."*
> `python -m arnold_pipelines.megaplan init <brief> --profile partnered-3 --phase-model critique=claude:medium --phase-model review=claude:medium` *(surgical: bumps just the critic+review pair — preserving the critique==review invariant — and leaves plan/revise at the profile's default. `--depth` can't express this because it's by-phase-name, not by-author-vs-critic.)*

Three pieces of intent → three flags (`--profile`, `--robustness`, `--depth`), plus `--vendor` / `--critic` / `--with-prep` / `--with-feedback` / `--in-worktree` when you need them.

### Config defaults

The `--vendor` flag honors a per-user config default. Write `~/.config/megaplan/config.toml`:

```toml
[defaults]
vendor = "claude"   # "claude" or "codex"
```

Set this once on a new machine and supported premium slots default to your preferred vendor without per-invocation flags. The CLI flag still wins when passed. A malformed or missing config falls back to `claude` silently.

---

## Bake-off

Default to a single profile. Only run a multi-arm bake-off when (a) the user asks, (b) three or more mixes are genuinely plausible, (c) the deliverable is a diff worth comparing, and (d) per-arm cost is well below the cost of guessing wrong. Don't bake off discovery / scoping / contract-freeze sprints — no diff to compare.

---

## Watching and diagnosing a running plan

This skill covers profile/robustness/depth selection *before* a run. Once a plan is in flight, switch to the **`megaplan-observe`** skill — same author, complementary focus:

- **Pull-mode observation**: `python -m arnold_pipelines.megaplan introspect` / `trace` / `doctor` for on-demand inspection, blockage diagnosis, drift detection. Read it before reaching for `override` so you don't guess at an `invalid_transition`.
- **Push-mode observation**: `watcher.sh` (bundled in the same skill) is a bash polling loop that streams phase-transition notifications. Wire it through Claude Code's `Monitor` tool to get told when phases start/end, when cost climbs, and when the plan reaches a terminal state — no manual polling.

When something looks wrong during a run (cost spiking, phase not advancing, iteration counter stuck), `megaplan-observe` is the next stop, not `--max-cost-usd`. The cost-cap and rework-cap flags exist for narrow recovery cases; they are not a default. Trust the defaults; intervene with `override` + tests if a phase fixates.
