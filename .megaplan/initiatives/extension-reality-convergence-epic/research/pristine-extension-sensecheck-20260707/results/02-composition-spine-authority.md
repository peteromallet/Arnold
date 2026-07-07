Reading additional input from stdin...
OpenAI Codex v0.137.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/reigh-app
model: gpt-5.5
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019f3a0c-4cb2-7d41-a14b-2d3a2f85f8c6
--------
user
# Codex Sense-Check: Composition Spine Authority

Repo: `/Users/peteromalley/Documents/reigh-workspace/reigh-app`

Run read-only. Do not edit files.

## Task

Investigate the current threat and best next move for landing the composition spine and retiring legacy authority paths.

The criticism to evaluate:

> The composition spine's beauty payoff only arrives if old authority paths are deleted, not wrapped. Prove the planner no longer reads legacy-only facts.

## What To Inspect

Prioritize current code and the staged epic:

- `.megaplan/initiatives/reigh-extension-composition-spine-epic/NORTHSTAR.md`
- `.megaplan/initiatives/reigh-extension-composition-spine-epic/prep.md`
- `.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml`
- `src/sdk/index.ts`
- `src/sdk/video/**` if present
- `src/tools/video-editor/runtime/**`
- `src/tools/video-editor/runtime/renderPlanner.ts`
- `src/tools/video-editor/runtime/renderability.ts`
- `src/tools/video-editor/lib/renderRouter.ts`
- `src/tools/video-editor/lib/**`
- `src/tools/video-editor/commands/**`
- `src/tools/video-editor/hooks/useTimelineCommands.ts`
- `src/tools/video-editor/compositions/**`
- docs under `docs/extensions/**` and `docs/video-editor/**` that discuss composition, render planner, target paths, shaders, live data, materials, output formats

## Questions

1. What graph/composition-spine concepts exist in current code, and what is only planned?
2. Which fact families are still legacy-authoritative?
3. Where does planner/export/preview behavior still read legacy-only facts?
4. Is "delete old authority paths" feasible now, or should the next step be a fact-family-by-fact-family authority ratchet?
5. What would a pristine migration plan look like without breaking existing timelines?

## Output

Markdown under 2000 words:

# Composition Spine Authority
## Verdict
Say whether the criticism is valid and how severe the threat is.
## Current Code Reality
Concrete files and facts.
## Pristine End State
What authority convergence should mean.
## Recommended Work
Ranked actions, with "now" vs "later".
## Tests / Gates
Specific tests proving planner/export no longer read legacy-only facts.
## Biggest Trap
The tempting but wrong thing to do.
codex
I’ll keep this read-only and use the context-mining/subagent guidance because this is a broad repo sense-check. First I’m going to inspect the relevant skill instructions, then fan out code/doc searches and consolidate only the findings.
exec
/bin/zsh -lc "sed -n '1,220p' /Users/peteromalley/Documents/poms_skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
---
name: contextminning-subagentmaxxing
description: >
  Keep the main-thread context as lean as possible while working. Two moves: (1)
  context minning — after each turn, look for a natural break-off point to condense,
  save state to markdown, and compact - write .md docs to make sure you don't lose 
  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
  a subagent (especially the DeepSeek/Kimi agents via subagent-launcher) should research,
  validate, or execute it so the verbose work never lands in your context. Use on 
  any long, multi-step, or research-heavy task.
---

# Context Minning & Subagent Maxxing

The goal of this skill is singular: **keep the actual work in the main thread's
context as small as possible.** Long contexts get slow, expensive, and forgetful.
Every turn, the most useful tokens should be present and the rest should be
elsewhere — in a file, in a summary, or in a subagent that already finished.

It runs as two continuous moves — a posture, not a one-time cleanup. This file is the
philosophy and the high level; each move has a standalone skill with the mechanics,
syntax, and anti-patterns. **Invoke those for the how.**

---

## Move 1 — Context minning: condense at the seams

When a chunk of work becomes *done and durable* — a plan spec'd out, a bug
root-caused, a long read distilled to one answer — the path to that conclusion is dead
weight. At those seams: **write the conclusion to a durable artifact, then compact from
there.** Prefer landing real work as a megaplan asset (plan file or ticket) over a loose
note, so what you shed becomes trackable work rather than vanishing.

The discipline is *write it down first* — you can only safely forget what you can
re-read. And don't over-do it: compact at seams, never on a timer; a slightly long
context costs less than a lost decision.

→ **`minimize-context`** for the seam catalogue, the `/compact` · `/clear` · `/context`
mechanics, megaplan-asset detail, and the over-minning failure mode.

→ **`context-usage`** to *see* the context filling: a turn-by-turn token-growth chart
read from the session transcript, with every compaction boundary marked. Use it to
check whether you're minning at the right seams or letting context balloon to
auto-compaction. (`/context` is the live snapshot; `context-usage` is the trajectory.)

## Move 2 — Subagent maxxing: do the work elsewhere

**Default to doing work in a subagent, not the thread.** Flip the question from "should
a subagent do this?" to "is there any reason this *can't*?" Its tool calls, file reads,
and reasoning stay in *its* context; only the conclusion returns to you. **Execution is
the headline case** — implementing, investigating, building is where byproduct piles up,
so it's the first thing to hand off, not the last. Be willing to launch **many**, even
in parallel, until you have clarity — that's cheaper than carrying the trail inline.

Two principles carry most of the value: spend the subagent on the *byproduct-heavy*
part and ask it to **return the conclusion, not the trail**; and **use the cheapest
model that can do the job** (cheap scan-work → reasoning → frontier only for real
complexity), preparing the context well enough that a cheaper tier can win. Don't
dispatch if you already have the answer.

**Match the venue to the scale.** A one-shot subagent dispatch is for ad-hoc work —
research, a sense-check, a contained fix. Once something is more than ~a day or two of
work it's a *deliverable*: run it as a **megaplan** (itself launched in a subagent) and
use **`megaplan-decision`** to size the tier/robustness/depth. Past ~2 weeks → an epic.

→ **`subagent-launcher`** for the pathways, the cost-escalation ladder with model
identifiers, and how to shape a self-contained subagent prompt.

---

## The loop, in one line

Every turn: *Did I just hit a seam? → write it down, compact. Am I about to do real
work? → hand it to a subagent.* Keep the main thread holding only what the next
decision needs.

exec
/bin/zsh -lc "sed -n '1,220p' /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/skills/subagent-launcher/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
---
name: subagent-launcher
description: Launch an external model as a subagent for a second opinion, adversarial review, or delegated work. Default pathway is an agentic DeepSeek / Kimi / Zhipu GLM hermes subagent (file/web/terminal tools, one process or fanned out N-wide); also Codex (GPT-5.5) and Claude via the Agent tool. Use for independent root-cause analysis, cross-checking your reasoning, judge/jury panels, or handing implementation to a different model.
---

# Subagent launcher (multi-model)

Dispatch work to a model other than the one driving the conversation. Two payoffs: **independence** — a *different* model's judgement, not a copy of your own — and **context hygiene** — the subagent's tool calls and reasoning stay in *its* context; only the conclusion returns to you.

Three pathways:

| Pathway | Model | Invocation | Tools |
| --- | --- | --- | --- |
| **Hermes agentic** *(default)* | DeepSeek V4 (Pro/Flash), Kimi K2.7, Zhipu GLM, … | `launch_hermes_agent.py` — or `fan.py` to run N in one process | `file`, `web`, optional `terminal` |
| **Codex** | GPT-5.5 | `codex exec` (CLI) | sandboxed workspace |
| **Claude** | Claude (Opus/Sonnet/Haiku) | `launch_claude_agent.py --model=opus` or Claude Code `Agent` tool | Claude Code tools |

**Default to the hermes agentic pathway, and to DeepSeek within it** — different model family, cheap, tool-using. Reach for Codex or Claude only when you specifically want their strengths.

> **⚠️ Network sandbox warning for Codex subagents**
> `codex exec` runs its subprocess with `CODEX_SANDBOX_NETWORK_DISABLED=1`. Hermes agents (DeepSeek/Kimi/MiMo/GLM/OpenRouter) need outbound network to reach their provider APIs, so **launching them from inside a `codex exec` subagent will fail**. The launcher itself is fine; it fails only because the parent process has no network.
>
> **Workarounds:**
> 1. Launch the hermes subagent directly from a normal shell or Bash tool.
> 2. If you need a **Codex subagent to orchestrate hermes subagents**, run the
>    outer Codex command with `--sandbox danger-full-access` and seal stdin with
>    `</dev/null`, for example:
>
>    ```bash
>    timeout 3600 codex exec --sandbox danger-full-access \
>      -c model_reasoning_effort=high \
>      "$(cat /tmp/brief.md)" </dev/null
>    ```
>
>    `read-only` and `workspace-write` both disable outbound network for the
>    Codex subprocess; only `danger-full-access` allows nested Hermes provider
>    API calls from inside `codex exec`. Tell Codex explicitly to use
>    `launch_hermes_agent.py` or `fan.py`, and to spend its own context budget
>    by delegating broad searches, file mapping, and independent reviews to
>    DeepSeek/Kimi subagents wherever practical.
>
> This network restriction does not affect Codex or Claude subagents.

## Picking a pathway

- **Default — an independent DeepSeek/Kimi subagent that reads the repo itself?** → §1 (`launch_hermes_agent.py --toolsets="file,web"`). Need many at once (≥ ~5 parallel)? Same pathway, `fan.py`.
- **Pure chat opinion, no tools?** → §1 with `--toolsets=""`.
- **Most-different-from-Claude judgement, or write-heavy implementation in a sandbox?** → §2 Codex.
- **Same-*family* judgement but isolated from this thread, with explicit Opus/Sonnet selection?** → §3 Claude CLI launcher. If the host exposes the Claude Code `Agent` tool and model selection is not required, that is also fine.
- **Jury for a high-stakes call?** → fan the same prompt to Codex + hermes-DeepSeek + hermes-Kimi in parallel; divergence is the signal.
- **Bigger than ~a day or two of work?** → it's a *deliverable*, not a dispatch: run a `megaplan` (itself launched as a subagent) and size it with the **`megaplan-decision`** skill. Past ~2 weeks → an epic.
- **Already have the answer?** → don't dispatch. Subagents aren't free.

## Use the cheapest subagent that can do the job

Independence is the *why*; cost is the *which*. Default to the cheapest model that can plausibly succeed; escalate only on evidence.

1. **MiMo V2.5 Pro Ultraspeed** (`fast`, alias for `mimo:mimo-v2.5-pro-ultraspeed`) — very fast. High-volume, low-judgement work: scan files, extract facts, short first-pass research.
2. **DeepSeek V4 Flash** (`deepseek:deepseek-v4-flash`) — non-reasoning, fast, cheap. High-volume work that needs more coding-tuned behavior than MiMo.
3. **DeepSeek V4 Pro** (`deepseek:deepseek-v4-pro`, the default) — reasoning model. When the task needs judgement: root-cause analysis, "is this sound", "should this merge".
4. **GPT-5.5 (Codex) or Claude** — only for *real* complexity: subtle multi-step reasoning, write-heavy implementation, the strongest adversarial review.

Two rules: **start low, escalate on evidence** (don't reach for the frontier model "to be safe"); and **prepare the context so a cheap model can win** — most "cheap model failed" cases are under-specified prompts. A moment spent scoping the task is cheaper than burning a Claude subagent on something Flash could do.

Beware the asymmetry: reasoning models handed mechanical briefs refactor (because that's what reasoning does); non-reasoning models handed architectural briefs literally execute fragments without understanding the intent. Match brief shape to model mode, not just model to task.

---

## 1. Hermes agentic (DeepSeek / Kimi / Zhipu GLM) — the default

A real tool-using agent in a non-Claude model's voice, far lighter than a `megaplan` run. It wraps megaplan's `AIAgent` primitive as a standalone CLI: the agent reads files, searches the codebase, fetches URLs, and (with `terminal`) runs commands — single-turn, no plan state or critique loop. For a pure-chat opinion with no repo access, run the same command with `--toolsets=""`.

The launcher discovers the active runtime itself. It first tries an installed legacy `megaplan.agent` distribution, then falls back to the current Arnold checkout (`~/Documents/Arnold` by default, or `ARNOLD_PATH=/path/to/Arnold`). Do not add an `arnold_pipelines.megaplan.agent` compatibility package to fix import failures; the real Hermes runtime lives under `arnold.pipelines.megaplan.agent` in the Arnold checkout.

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --toolsets="file,web" \
  --query-file=/tmp/brief.md \
  --max-tokens=65536 \
  --project-dir="$PWD"
# Final response → stdout; tool progress/timings → stderr.
```

Key flags:

- **`--model`** (default `deepseek:deepseek-v4-pro`). Prefix convention from the megaplan key pool:
  - `fast`, `mimo`, `mimo-fast` → `mimo:mimo-v2.5-pro-ultraspeed` (very fast MiMo path; requires `MIMO_API_KEY`)
  - `deepseek:deepseek-v4-pro` (default) / `deepseek:deepseek-v4-flash` (faster, non-reasoning) → DeepSeek API
  - `kimi:kimi-k2.7-code` → Kimi coding API (requires `KIMI_API_KEY` or `MOONSHOT_API_KEY`)
  - `zhipu:glm-5.2` / `zhipu:glm-4.6` → Zhipu GLM API (requires `ZHIPU_API_KEY`)
  - `google:gemini-…`, `minimax:MiniMax-M2`, … — see `megaplan/runtime/key_pool.py:resolve_model`
- **`--toolsets`** (default `"file,web"`): `file` (`read_file`/`write_file`/`patch`/`search_files`), `web` (`fetch_url`), `terminal` (shell — **no sandbox**, runs as you; never for untrusted prompts). `""` = pure chat.
- **Note:** in the standalone `launch_hermes_agent.py` entrypoint, the `file` toolset is only available when `terminal` is also enabled, because file operations are routed through the terminal environment. If the agent emits tool-call markup but does not actually read files (or claims it has no filesystem access), pass `--toolsets="file,web,terminal"`.
- **`--query` / `--query-file`** — pass exactly one; use `--query-file` for anything past a sentence.
- **`--max-tokens`** (default 65536 — model output ceiling for DeepSeek V4). **In normal use, do not pass this flag.** The launcher already defaults to the model's ceiling, so adding it yourself just creates copy-paste noise and makes it easy to accidentally inflate the cap for no benefit. These are reasoning models; reasoning tokens are billed and counted against `max_tokens`, so a brief that fires 20+ tool calls can burn the entire budget on reasoning before emitting a single output token — the result is an empty answer (`finish_reason: length`) with the tool history visible in stderr. The built-in ceiling protects against that silent failure. **Only pass `--max-tokens` when you specifically want a shorter cap** because you have already scoped the brief to ≤5 tool calls and want to bound cost/output length. Other ceilings: Kimi K2.7 ~32768, Zhipu GLM-5.2 / GLM-4.6 ~32768, DeepSeek Flash 8192 (non-reasoning, doesn't burn budget on thinking so 8K is fine).
- **`--project-dir`** — chdir so the `file` tool resolves relative paths as you expect.
- **Runtime discovery** — set `ARNOLD_PATH=/path/to/Arnold` only for nonstandard checkouts. Normal shells should not need manual `PYTHONPATH`.
- **`--context-budget-tokens`** — raise the auto-compaction floor when a broad file audit on a long-context model compacts too early, e.g. `--context-budget-tokens=100000`.

Output is **freeform text** — if you want JSON, ask for it in the prompt and parse defensively; for an *enforced* schema, use megaplan, not this pathway.

### Fan out N at once — `fan.py`

`launch_hermes_agent.py` is one subprocess per call; each re-imports the Arnold/Hermes runtime. For **≥ ~5 parallel agents or programmatic batches**, `fan.py` runs N `AIAgent`s in one process (imports once, ~5–15× less RAM). Same flags, plus a briefs directory and per-task output:

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py \
  --briefs-dir=/tmp/briefs --output-dir=/tmp/results \
  --max-workers=5 --model="deepseek:deepseek-v4-pro" \
  --toolsets="file,web" --max-tokens=65536 --task-timeout=1800 --project-dir="$PWD"
# Or positional brief paths instead of --briefs-dir.
# Per-brief models: --model-map="fast:scan-*.md,pro:verdict-*.md"
```

Each brief `<stem>.md` yields `<stem>.txt` (response), `<stem>.meta.json` (status/timing/tool_calls), and an aggregate `_report.json`. Kill a running fan from another shell: `fan_kill.py --output-dir=… [--hard]`. Default `--task-timeout=1800` (30 min — forensic work with ≥10 tool calls routinely exceeds 10 min; the old 600s default would silently SIGKILL agents mid-investigation). Bump higher for very heavy briefs (e.g. `--task-timeout=3600` for cross-file audits). Add `--isolation=processes` if you need to SIGKILL one task without touching the rest. Below ~5 parallel, just launch `launch_hermes_agent.py` N times in parallel Bash calls — simpler.

### Use `megaplan` instead when you need

multi-phase orchestration (plan → critique → revise → execute → gate → review), schema-enforced output, persistent plan state / approval gates, or the megaplan sandbox. See *Multi-phase delegation* below.

### Liveness

The script logs `[tool]` / `[done]` to stderr every 1–5 s while alive and ends with `[launch_hermes_agent] done in N.Ns`. No new tool lines for minutes = wedged. For `fan.py`, watch `.meta.json` files appearing under `--output-dir`.

---

## 2. Codex (GPT-5.5)

`codex exec` from Bash (the `/codex:*` plugin wraps the same call).

```bash
codex exec --sandbox read-only "$(cat /tmp/prompt.md)" </dev/null > /tmp/out.txt 2>&1
```

- `--sandbox read-only | workspace-write | danger-full-access` — analysis / let it edit files / full shell.
- `-c model_reasoning_effort=low|medium|high` — `medium` default.
- `codex exec review [--pr <n>]` for PR review; `codex apply` to apply its last diff.
- **Always seal stdin with `</dev/null`.** Otherwise `codex exec` blocks forever at `Reading additional input from stdin...` (0% CPU, no error) even when the prompt is in argv. That banner prints on healthy runs too — the wedge signal is the output file *not growing*. Wrap long runs in `timeout 1800` (30 min — review and write-heavy briefs routinely run 15+ min; 600s is too tight).

## 3. Claude (Opus/Sonnet/Haiku)

Use the Claude CLI launcher when you need an explicit model selector from any
host, including Codex sessions where the platform `spawn_agent` tool does not
expose a model field:

```bash
python ~/.claude/skills/subagent-launcher/launch_claude_agent.py \
  --model=opus \
  --query-file=/tmp/brief.md \
  --project-dir="$PWD" \
  --tools="Read,Grep,Glob" \
  --timeout=1800
```

`--model` accepts Claude Code aliases such as `opus` / `sonnet` / `haiku` or a
full model name such as `claude-opus-4-8`. The launcher invokes
`claude --print --model <model>` with `--project-dir` as the subprocess cwd and
prints the final answer to stdout while diagnostics go to stderr. It leaves
Claude Code's default tool policy alone unless you pass `--tools`; use
`--permission-mode` deliberately. It adds `--no-session-persistence` by default
so one-off subagents do not clutter Claude history; pass `--keep-session` when
you want resumability.

When you are already inside Claude Code and the `Agent` tool is available,
you can still dispatch through it — cleanly-scoped, no memory of the outer
conversation, so the prompt must be self-contained. Subagent types:
`general-purpose` (full tools), `Explore` (fast read-only search), `Plan`
(architect, no code), `claude-code-guide`, `code-reviewer`.

```
Agent({ description: "…", subagent_type: "general-purpose",
        prompt: "<self-contained brief: working dir, files, what to return, length cap>" })
```

Prefer Claude over Codex when you want the *same family* of judgement isolated from this thread (keeping the main context clean), or specifically want Opus judgement. For genuinely different model-family judgement, prefer Codex, DeepSeek, or Kimi.

---

## Multi-phase delegation (when a single-turn agent isn't enough)

When DeepSeek/Kimi need a full plan-execute-review cycle across many files, route through megaplan:

```bash
PYENV_VERSION=3.11.11 megaplan init --project-dir "$PWD" \
  --profile all-deepseek-pro-direct --robustness light "<task>"
# Kimi: --profile all-open
```

`--robustness light` is a fast single pass; drop it for the full workflow (default `full`). The **`megaplan-decision`** skill covers the profile / robustness / depth dials.

## Writing the prompt (any pathway)

The receiving model has **zero context** from your conversation. Brief it like a smart colleague who just walked in:

**Is your brief a spec or a memo?** A spec lists inputs and outputs (do X at line Y, then Z). A memo explains context and asks for judgement. Reasoning models will treat any memo as license to architect — even if the underlying ask was 5 mechanical edits. If the work is mechanical, strip the rationale; the "why" belongs in the commit message, not the brief.

- Working directory and **exact** file paths (not "the relevant files").
- Goal + why it matters; what you've already ruled out.
- Output shape and a length cap ("ranked list, < 300 words").
- For adversarial / second-opinion work, tell it to take a position and not hedge — otherwise it hedges.
- Anti-pattern: the options menu. "Pick whichever of A/B/C fits" reliably invites a reasoning model to optimize across the options and often produce a fourth one you didn't ask for. One ask, one solution path. Save options menus for genuine judgement calls — and when you do use them, route the work to a non-reasoning model that can't optimize past them.

Don't dispatch what you already know, and don't re-ask what you've answered — add a twist (rank these, find the flaw, argue the other side) or skip it.

## Judge / jury for high-stakes calls

Send the same unbiased prompt to several models in parallel (Codex + hermes-DeepSeek + hermes-Kimi, optionally a Claude `Agent`) and compare — convergence on a subtle call is far stronger than one model's confidence; divergence is signal. Reserve it for risky pre-merge reviews, hard-to-reverse architecture calls, security-sensitive paths. Don't fan out routine work. For a multi-lens sense-check of one proposal (human-user / agent-user / abstraction lenses), give each agent only its own lens and never show one's output to another.

## Detecting hangs

Check liveness **30–60 s after launch**, not 10 minutes in.

- **Codex** — see the `</dev/null` wedge above; the tell is an output file stuck at the banner size while wall-clock climbs.
- **Hermes / fan.py** — `--max-tokens` too low → empty answer (`finish_reason: length`); else watch the stderr `[tool]`/`[done]` heartbeat.
- **Claude Agent / launcher** — synchronous, rarely wedges; the common failure is a terse prompt → shallow hedged answer in < 30 s. Cap length and demand a position.
- **megaplan** — an "stuck" run is usually a gated step awaiting approval; `megaplan status --plan <name>`.

**Liveness ≠ correctness.** A subagent can stream for 10 minutes and still answer uselessly — read the response; there's no shortcut.

## Quick reference

codex
The available subagent tool is stricter than the repo guidance: it only permits spawning when the user explicitly asks for delegation. I’ll keep the same lean posture locally: focused searches, then a compact synthesis.
exec
/bin/zsh -lc 'pwd && rg --files .megaplan/initiatives/reigh-extension-composition-spine-epic src/sdk src/tools/video-editor docs/extensions docs/video-editor 2>/dev/null | sort' in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
/Users/peteromalley/Documents/reigh-workspace/reigh-app
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml
docs/extensions/authoring.md
docs/extensions/compatibility.md
docs/extensions/loading.md
docs/extensions/phase4-readiness.md
docs/extensions/reigh-extension-layer-foundation-plan.md
docs/extensions/reigh-extension-layer-roadmap-v2.md
docs/extensions/reigh-extension-layer-tickets.md
docs/video-editor/extension-author-contract.md
docs/video-editor/extension-platform-contract-recheck.md
docs/video-editor/extension-platform-release-checklist.md
docs/video-editor/extension-platform-supported-deferred.md
docs/video-editor/extensions-debugging.md
docs/video-editor/extensions-migration-local-to-pack.md
docs/video-editor/extensions-quickstart.md
docs/video-editor/extensions-trust-envelope.md
docs/video-editor/frontend-closure-checklist.md
docs/video-editor/frontend-closure-matrix.md
docs/video-editor/live-data-bridge-manual-smoke-checklist.txt
docs/video-editor/provider-compatibility-matrix.md
docs/video-editor/shader-execution-model.md
docs/video-editor/timeline-patch-operations.md
src/sdk/__tests__/sdk-boundary.test.ts
src/sdk/boundary.test.ts
src/sdk/contracts.ts
src/sdk/examples-governance.test.ts
src/sdk/extensionSettingsMigration.test.ts
src/sdk/extensionSettingsMigration.ts
src/sdk/extensionSettingsService.test.ts
src/sdk/extensionSettingsService.ts
src/sdk/index.test.ts
src/sdk/index.ts
src/sdk/manifest-schema-validation.test.ts
src/sdk/smoke/extensionSmoke.test.ts
src/sdk/smoke/extensionSmoke.ts
src/tools/video-editor/adapters/reigh/generationLookup.ts
src/tools/video-editor/adapters/reigh/staleVariantRepository.ts
src/tools/video-editor/adapters/reigh/useReighEffectsCatalog.ts
src/tools/video-editor/adapters/reigh/useReighShotsHost.ts
src/tools/video-editor/adapters/reigh/useReighTimelinesList.test.ts
src/tools/video-editor/adapters/reigh/useReighTimelinesList.ts
src/tools/video-editor/adapters/reigh/variantPromotionLookup.ts
src/tools/video-editor/browser-provider.ts
src/tools/video-editor/browser.ts
src/tools/video-editor/browser/BrowserVideoEditor.test.tsx
src/tools/video-editor/browser/BrowserVideoEditor.tsx
src/tools/video-editor/browser/BrowserVideoEditorProvider.test.tsx
src/tools/video-editor/browser/BrowserVideoEditorProvider.tsx
src/tools/video-editor/browser/hooks.test.tsx
src/tools/video-editor/browser/hooks.tsx
src/tools/video-editor/browser/mountVideoEditor.tsx
src/tools/video-editor/capabilityManifest.test.ts
src/tools/video-editor/capabilityManifest.ts
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts
src/tools/video-editor/clip-types/ClipTypeRegistry.ts
src/tools/video-editor/clip-types/ClipTypeRegistryContext.tsx
src/tools/video-editor/clip-types/defineClipType.test.ts
src/tools/video-editor/clip-types/defineClipType.ts
src/tools/video-editor/clip-types/index.ts
src/tools/video-editor/clip-types/manifest.test.ts
src/tools/video-editor/clip-types/manifest.ts
src/tools/video-editor/clip-types/registry.test.ts
src/tools/video-editor/clip-types/registry.ts
src/tools/video-editor/clip-types/runtime.test.ts
src/tools/video-editor/clip-types/runtime.ts
src/tools/video-editor/commands/index.ts
src/tools/video-editor/commands/media.ts
src/tools/video-editor/commands/provisioning.ts
src/tools/video-editor/commands/runner.ts
src/tools/video-editor/commands/timelineData.ts
src/tools/video-editor/commands/types.ts
src/tools/video-editor/components/AgentChat/AgentChat.test.tsx
src/tools/video-editor/components/AgentChat/AgentChat.tsx
src/tools/video-editor/components/AgentChat/AgentChatMessage.test.tsx
src/tools/video-editor/components/AgentChat/AgentChatMessage.tsx
src/tools/video-editor/components/AgentChat/index.ts
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.test.tsx
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx
src/tools/video-editor/components/BatchLabelPanel.tsx
src/tools/video-editor/components/Canary/Canary.test.tsx
src/tools/video-editor/components/Canary/CodePanelCanary.tsx
src/tools/video-editor/components/Canary/StagePanelCanary.tsx
src/tools/video-editor/components/Canary/WritingPanelCanary.tsx
src/tools/video-editor/components/CommandPalette/CommandPalette.test.tsx
src/tools/video-editor/components/CommandPalette/CommandPalette.tsx
src/tools/video-editor/components/CompactPreview.tsx
src/tools/video-editor/components/CopilotPrompt/CopilotPrompt.test.tsx
src/tools/video-editor/components/CopilotPrompt/CopilotPrompt.tsx
src/tools/video-editor/components/CueListEditor.tsx
src/tools/video-editor/components/CustomEffectEditor.tsx
src/tools/video-editor/components/DiagnosticPanel/DiagnosticPanel.test.tsx
src/tools/video-editor/components/DiagnosticPanel/DiagnosticPanel.tsx
src/tools/video-editor/components/EffectCreatorPanel.test.tsx
src/tools/video-editor/components/EffectCreatorPanel.tsx
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx
src/tools/video-editor/components/ExtensionManager/ExtensionManagerErrorBoundary.tsx
src/tools/video-editor/components/ExtensionManager/ExtensionTrustWarningBanner.tsx
src/tools/video-editor/components/ExtensionManager/index.ts
src/tools/video-editor/components/ExtensionSettings/ExtensionSettingsPanel.tsx
src/tools/video-editor/components/GenerationSessionPanel/GenerationSessionPanel.test.tsx
src/tools/video-editor/components/GenerationSessionPanel/GenerationSessionPanel.tsx
src/tools/video-editor/components/KeyframeInspector/KeyframeInspector.test.tsx
src/tools/video-editor/components/KeyframeInspector/KeyframeInspector.tsx
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.test.tsx
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx
src/tools/video-editor/components/ManagedObjectConfirmationDialog/ManagedObjectConfirmationDialog.test.tsx
src/tools/video-editor/components/ManagedObjectConfirmationDialog/ManagedObjectConfirmationDialog.tsx
src/tools/video-editor/components/MaterialBrowser.test.tsx
src/tools/video-editor/components/MaterialBrowser.tsx
src/tools/video-editor/components/ParameterControls.tsx
src/tools/video-editor/components/PendingMaterialPlaceholder.tsx
src/tools/video-editor/components/PreviewPanel/OverlayEditor.test.tsx
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx
src/tools/video-editor/components/PreviewPanel/PreviewPanel.tsx
src/tools/video-editor/components/PreviewPanel/RemotionPreview.test.tsx
src/tools/video-editor/components/PreviewPanel/RemotionPreview.tsx
src/tools/video-editor/components/PreviewPanel/useVideoEditorPreviewSurface.tsx
src/tools/video-editor/components/ProcessSettingsForm.test.tsx
src/tools/video-editor/components/ProcessSettingsForm.tsx
src/tools/video-editor/components/PropertiesPanel/AssetPanel.test.tsx
src/tools/video-editor/components/PropertiesPanel/AssetPanel.tsx
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx
src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx
src/tools/video-editor/components/PropertiesPanel/ClipPanel.transition.test.tsx
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx
src/tools/video-editor/components/PropertiesPanel/SequenceParamEditor.tsx
src/tools/video-editor/components/PropertiesPanel/VideoEditorAssetPanelSurface.tsx
src/tools/video-editor/components/ProposalPanel/ProposalPanel.test.tsx
src/tools/video-editor/components/ProposalPanel/ProposalPanel.tsx
src/tools/video-editor/components/ReighTimelineEditor.tsx
src/tools/video-editor/components/ReighVideoEditorShell.tsx
src/tools/video-editor/components/RoundtripResultsPanel.test.tsx
src/tools/video-editor/components/RoundtripResultsPanel.tsx
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx
src/tools/video-editor/components/SegmentCaptionEditor.tsx
src/tools/video-editor/components/SequenceCreator/CodePathParamEditor.tsx
src/tools/video-editor/components/SequenceCreator/CodePathPreview.tsx
src/tools/video-editor/components/SequenceCreator/ControlsManifestLayout.test.tsx
src/tools/video-editor/components/SequenceCreator/ControlsManifestLayout.tsx
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.test.tsx
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx
src/tools/video-editor/components/SequenceCreator/sequenceGenerationService.ts
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx
src/tools/video-editor/components/SidecarEditingWidgets.test.tsx
src/tools/video-editor/components/SidecarPreview.test.tsx
src/tools/video-editor/components/SidecarPreview.tsx
src/tools/video-editor/components/ThemeChip.tsx
src/tools/video-editor/components/TimelineEditor/ClipAction.test.tsx
src/tools/video-editor/components/TimelineEditor/ClipAction.tsx
src/tools/video-editor/components/TimelineEditor/DropIndicator.test.tsx
src/tools/video-editor/components/TimelineEditor/DropIndicator.tsx
src/tools/video-editor/components/TimelineEditor/ExtensionContextMenuItems.tsx
src/tools/video-editor/components/TimelineEditor/ShotGroupContextMenu.tsx
src/tools/video-editor/components/TimelineEditor/ShotGroupOverlay.test.tsx
src/tools/video-editor/components/TimelineEditor/ShotGroupOverlay.tsx
src/tools/video-editor/components/TimelineEditor/TimeRuler.tsx
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.test.tsx
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.tsx
src/tools/video-editor/components/TimelineEditor/TimelineEditor.test.ts
src/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.tsx
src/tools/video-editor/components/TimelineEditor/TimelineGhostLayer.test.tsx
src/tools/video-editor/components/TimelineEditor/TimelineGhostLayer.tsx
src/tools/video-editor/components/TimelineEditor/TimelineRulerAndGrid.tsx
src/tools/video-editor/components/TimelineEditor/TrackLabel.tsx
src/tools/video-editor/components/TimelineEditor/TrackListRenderer.test.tsx
src/tools/video-editor/components/TimelineEditor/TrackListRenderer.tsx
src/tools/video-editor/components/TimelineEditor/WaveformOverlay.test.tsx
src/tools/video-editor/components/TimelineEditor/WaveformOverlay.tsx
src/tools/video-editor/components/TimelineEditor/timeline-canvas-constants.ts
src/tools/video-editor/components/TimelineEditor/timeline-overrides.css
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx
src/tools/video-editor/components/TimelineEditorShellCore.tsx
src/tools/video-editor/components/VideoEditorLightboxOverlay.test.tsx
src/tools/video-editor/components/VideoEditorLightboxOverlay.tsx
src/tools/video-editor/components/VideoEditorShell.tsx
src/tools/video-editor/components/__tests__/PreviewPersistence.test.tsx
src/tools/video-editor/components/__tests__/ThemeChip.test.tsx
src/tools/video-editor/components/sidecar-editing.ts
src/tools/video-editor/compositions/AudioAnalysisProvider.test.tsx
src/tools/video-editor/compositions/AudioAnalysisProvider.tsx
src/tools/video-editor/compositions/AudioTrack.test.tsx
src/tools/video-editor/compositions/AudioTrack.tsx
src/tools/video-editor/compositions/ClipEffectsSnapshot.test.tsx
src/tools/video-editor/compositions/DebugTrack.tsx
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx
src/tools/video-editor/compositions/EffectLayerSequence.tsx
src/tools/video-editor/compositions/MediaErrorBoundary.tsx
src/tools/video-editor/compositions/TextClip.tsx
src/tools/video-editor/compositions/TimelineRenderer.dynamic.test.tsx
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx
src/tools/video-editor/compositions/TimelineRenderer.test.tsx
src/tools/video-editor/compositions/TimelineRenderer.tsx
src/tools/video-editor/compositions/UnknownClipPlaceholder.tsx
src/tools/video-editor/compositions/VisualClip.test.tsx
src/tools/video-editor/compositions/VisualClip.tsx
src/tools/video-editor/compositions/fallback/registry.generated.tsx
src/tools/video-editor/compositions/fallback/theme-api.tsx
src/tools/video-editor/compositions/installed-themes.ts
src/tools/video-editor/contexts/DataProviderContext.tsx
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx
src/tools/video-editor/contexts/VideoEditorProvider.tsx
src/tools/video-editor/core/CoreProvider.tsx
src/tools/video-editor/core/core-ports.ts
src/tools/video-editor/core/core-runtime.tsx
src/tools/video-editor/data/AssetResolver.ts
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts
src/tools/video-editor/data/AstridBridgeDataProvider.ts
src/tools/video-editor/data/DataProvider.test.ts
src/tools/video-editor/data/DataProvider.ts
src/tools/video-editor/data/InMemoryDataProvider.test.ts
src/tools/video-editor/data/SupabaseDataProvider.test.ts
src/tools/video-editor/data/SupabaseDataProvider.ts
src/tools/video-editor/data/conformance/extensionPersistenceConformance.ts
src/tools/video-editor/data/generationAssetResolver.test.ts
src/tools/video-editor/data/generationAssetResolver.ts
src/tools/video-editor/data/syncLedgerIndexedDb.test.ts
src/tools/video-editor/data/syncLedgerIndexedDb.ts
src/tools/video-editor/effects/DynamicEffectRegistry.test.tsx
src/tools/video-editor/effects/DynamicEffectRegistry.ts
src/tools/video-editor/effects/EffectErrorBoundary.tsx
src/tools/video-editor/effects/audioBindingParams.test.tsx
src/tools/video-editor/effects/chromatic-glitch-storm.js
src/tools/video-editor/effects/compileEffect.tsx
src/tools/video-editor/effects/continuous.tsx
src/tools/video-editor/effects/effect-store.ts
src/tools/video-editor/effects/effectPromptTemplate.ts
src/tools/video-editor/effects/entrances.tsx
src/tools/video-editor/effects/exits.tsx
src/tools/video-editor/effects/index.tsx
src/tools/video-editor/effects/registry/EffectRegistry.test.ts
src/tools/video-editor/effects/registry/EffectRegistry.ts
src/tools/video-editor/effects/registry/EffectRegistryContext.test.tsx
src/tools/video-editor/effects/registry/EffectRegistryContext.tsx
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.ts
src/tools/video-editor/effects/registry/adapters/index.ts
src/tools/video-editor/effects/registry/index.ts
src/tools/video-editor/effects/registry/types.ts
src/tools/video-editor/effects/transitions.ts
src/tools/video-editor/effects/useAudioReactive.test.ts
src/tools/video-editor/effects/useAudioReactive.ts
src/tools/video-editor/effects/validateParams.ts
src/tools/video-editor/examples/CustomTwoPaneVideoEditorExample.tsx
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx
src/tools/video-editor/examples/extensions/__tests__/flagship-local-transition.test.ts
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx
src/tools/video-editor/examples/extensions/__tests__/live-generated-frame-canary.test.ts
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts
src/tools/video-editor/examples/extensions/agent-tools-canary/reigh-extension.json
src/tools/video-editor/examples/extensions/agent-tools-copilot/index.ts
src/tools/video-editor/examples/extensions/agent-tools-copilot/reigh-extension.json
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts
src/tools/video-editor/examples/extensions/agent-tools-export/reigh-extension.json
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts
src/tools/video-editor/examples/extensions/clip-local-shader-canary/reigh-extension.json
src/tools/video-editor/examples/extensions/flagship-local/FlagshipEffectComponent.tsx
src/tools/video-editor/examples/extensions/flagship-local/index.ts
src/tools/video-editor/examples/extensions/flagship-local/reigh-extension.json
src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts
src/tools/video-editor/examples/extensions/live-generated-frame-canary/reigh-extension.json
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts
src/tools/video-editor/examples/extensions/live-webcam-canary/reigh-extension.json
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json
src/tools/video-editor/hooks/__tests__/resolve-overlaps.test.ts
src/tools/video-editor/hooks/clip-editing/index.ts
src/tools/video-editor/hooks/clip-editing/types.ts
src/tools/video-editor/hooks/clip-editing/useClipAudioManagement.ts
src/tools/video-editor/hooks/clip-editing/useClipDeletion.ts
src/tools/video-editor/hooks/clip-editing/useClipPositioning.ts
src/tools/video-editor/hooks/clip-editing/useClipSplitting.ts
src/tools/video-editor/hooks/clip-editing/useClipTextOverlay.ts
src/tools/video-editor/hooks/timeline-state-types.ts
src/tools/video-editor/hooks/timelineStore.ts
src/tools/video-editor/hooks/useActiveTaskClips.ts
src/tools/video-editor/hooks/useAddVariantAsGeneration.test.tsx
src/tools/video-editor/hooks/useAddVariantAsGeneration.ts
src/tools/video-editor/hooks/useAgentSession.test.tsx
src/tools/video-editor/hooks/useAgentSession.ts
src/tools/video-editor/hooks/useAgentVoice.ts
src/tools/video-editor/hooks/useAssetManagement.assetDrop.test.ts
src/tools/video-editor/hooks/useAssetManagement.ts
src/tools/video-editor/hooks/useAssetOperations.test.tsx
src/tools/video-editor/hooks/useAssetOperations.ts
src/tools/video-editor/hooks/useClientRender.ts
src/tools/video-editor/hooks/useClipDrag.helpers.ts
src/tools/video-editor/hooks/useClipDrag.softtag.test.tsx
src/tools/video-editor/hooks/useClipDrag.test.tsx
src/tools/video-editor/hooks/useClipDrag.ts
src/tools/video-editor/hooks/useClipEditing.test.ts
src/tools/video-editor/hooks/useClipEditing.ts
src/tools/video-editor/hooks/useClipResize.test.tsx
src/tools/video-editor/hooks/useClipResize.ts
src/tools/video-editor/hooks/useClipResizeGesture.helpers.ts
src/tools/video-editor/hooks/useClipResizeGesture.ts
src/tools/video-editor/hooks/useDerivedTimeline.ts
src/tools/video-editor/hooks/useDragCoordinator.ts
src/tools/video-editor/hooks/useEditorPreferences.ts
src/tools/video-editor/hooks/useEditorSync.test.ts
src/tools/video-editor/hooks/useEditorSync.ts
src/tools/video-editor/hooks/useEffectRegistry.ts
src/tools/video-editor/hooks/useEffectResources.test.tsx
src/tools/video-editor/hooks/useEffectResources.ts
src/tools/video-editor/hooks/useEffects.ts
src/tools/video-editor/hooks/useExternalDrop.test.tsx
src/tools/video-editor/hooks/useExternalDrop.ts
src/tools/video-editor/hooks/useFinalVideoAvailable.ts
src/tools/video-editor/hooks/useKeyboardShortcuts.test.tsx
src/tools/video-editor/hooks/useKeyboardShortcuts.ts
src/tools/video-editor/hooks/useManagedObjectConfirmation.ts
src/tools/video-editor/hooks/useMarqueeSelect.ts
src/tools/video-editor/hooks/usePerfDiagnostics.ts
src/tools/video-editor/hooks/usePinnedShotGroups.ts
src/tools/video-editor/hooks/usePollSync.test.ts
src/tools/video-editor/hooks/usePollSync.ts
src/tools/video-editor/hooks/useRenderState.test.tsx
src/tools/video-editor/hooks/useRenderState.ts
src/tools/video-editor/hooks/useSelectedMediaClips.ts
src/tools/video-editor/hooks/useSequenceResources.ts
src/tools/video-editor/hooks/useShotGroupHandlers.ts
src/tools/video-editor/hooks/useShotGroups.test.ts
src/tools/video-editor/hooks/useShotGroups.ts
src/tools/video-editor/hooks/useStaleVariants.ts
src/tools/video-editor/hooks/useSwitchToFinalVideo.ts
src/tools/video-editor/hooks/useTimeline.test.tsx
src/tools/video-editor/hooks/useTimeline.ts
src/tools/video-editor/hooks/useTimelineClipsForAttachments.ts
src/tools/video-editor/hooks/useTimelineCommands.ts
src/tools/video-editor/hooks/useTimelineCommit.test.tsx
src/tools/video-editor/hooks/useTimelineCommit.ts
src/tools/video-editor/hooks/useTimelineEventBus.test.ts
src/tools/video-editor/hooks/useTimelineEventBus.ts
src/tools/video-editor/hooks/useTimelineHistory.test.ts
src/tools/video-editor/hooks/useTimelineHistory.ts
src/tools/video-editor/hooks/useTimelineOps.test.ts
src/tools/video-editor/hooks/useTimelineOps.ts
src/tools/video-editor/hooks/useTimelinePersistence.test.tsx
src/tools/video-editor/hooks/useTimelinePersistence.ts
src/tools/video-editor/hooks/useTimelinePlayback.ts
src/tools/video-editor/hooks/useTimelineQueries.ts
src/tools/video-editor/hooks/useTimelineRealtime.ts
src/tools/video-editor/hooks/useTimelineSave.ts
src/tools/video-editor/hooks/useTimelineScale.ts
src/tools/video-editor/hooks/useTimelineSelection.ts
src/tools/video-editor/hooks/useTimelineState.ts
src/tools/video-editor/hooks/useTimelineState.types.ts
src/tools/video-editor/hooks/useTimelineSync.ts
src/tools/video-editor/hooks/useTimelineTrackManagement.test.ts
src/tools/video-editor/hooks/useTimelineTrackManagement.ts
src/tools/video-editor/hooks/useTimelinesList.ts
src/tools/video-editor/hooks/useVideoEditorLightboxNavigation.test.ts
src/tools/video-editor/hooks/useVideoEditorLightboxNavigation.ts
src/tools/video-editor/hooks/useWaveformData.test.tsx
src/tools/video-editor/hooks/useWaveformData.ts
src/tools/video-editor/index.ts
src/tools/video-editor/keyframes/index.test.ts
src/tools/video-editor/keyframes/index.ts
src/tools/video-editor/lib/__tests__/coordinate-utils.test.ts
src/tools/video-editor/lib/__tests__/editor-utils.test.ts
src/tools/video-editor/lib/assetMetadata.test.ts
src/tools/video-editor/lib/assetMetadata.ts
src/tools/video-editor/lib/assetMetadataUIHelpers.ts
src/tools/video-editor/lib/assetParserRuntime.test.ts
src/tools/video-editor/lib/assetParserRuntime.ts
src/tools/video-editor/lib/assetRegistryContract.test.ts
src/tools/video-editor/lib/assetRegistryPersistence.ts
src/tools/video-editor/lib/auto-scroll.ts
src/tools/video-editor/lib/browser-runtime.ts
src/tools/video-editor/lib/bulk-utils.test.ts
src/tools/video-editor/lib/bulk-utils.ts
src/tools/video-editor/lib/clip-editing-utils.ts
src/tools/video-editor/lib/clip-inspector.ts
src/tools/video-editor/lib/compiler-canary.test.ts
src/tools/video-editor/lib/compiler-canary.ts
src/tools/video-editor/lib/config-utils.test.ts
src/tools/video-editor/lib/config-utils.ts
src/tools/video-editor/lib/coordinate-utils.ts
src/tools/video-editor/lib/defaults.test.ts
src/tools/video-editor/lib/defaults.ts
src/tools/video-editor/lib/derivedAssetRegistry.ts
src/tools/video-editor/lib/drop-position.ts
src/tools/video-editor/lib/duplicate-clip.test.ts
src/tools/video-editor/lib/duplicate-clip.ts
src/tools/video-editor/lib/editor-utils.ts
src/tools/video-editor/lib/effect-catalog.test.ts
src/tools/video-editor/lib/effect-catalog.ts
src/tools/video-editor/lib/external-drop-utils.ts
src/tools/video-editor/lib/finalVideoAssets.test.ts
src/tools/video-editor/lib/finalVideoAssets.ts
src/tools/video-editor/lib/fixtures.ts
src/tools/video-editor/lib/generated-lanes.ts
src/tools/video-editor/lib/generation-utils.ts
src/tools/video-editor/lib/interaction-state.test.ts
src/tools/video-editor/lib/interaction-state.ts
src/tools/video-editor/lib/keyboard-delete.test.ts
src/tools/video-editor/lib/keyboard-delete.ts
src/tools/video-editor/lib/managed-object-guard.test.ts
src/tools/video-editor/lib/managed-object-guard.ts
src/tools/video-editor/lib/mediaMetadata.test.ts
src/tools/video-editor/lib/mediaMetadata.ts
src/tools/video-editor/lib/migrate.test.ts
src/tools/video-editor/lib/migrate.ts
src/tools/video-editor/lib/mobile-interaction-model.ts
src/tools/video-editor/lib/multi-drag-utils.test.ts
src/tools/video-editor/lib/multi-drag-utils.ts
src/tools/video-editor/lib/overhang.test.ts
src/tools/video-editor/lib/overhang.ts
src/tools/video-editor/lib/overlay-bounds.ts
src/tools/video-editor/lib/perf-diagnostics.ts
src/tools/video-editor/lib/pinned-group-projection.test.ts
src/tools/video-editor/lib/pinned-group-projection.ts
src/tools/video-editor/lib/proposal-runtime.test.ts
src/tools/video-editor/lib/proposal-runtime.ts
src/tools/video-editor/lib/registry.generated.fallback.ts
src/tools/video-editor/lib/render-bounds.test.ts
src/tools/video-editor/lib/render-bounds.ts
src/tools/video-editor/lib/render-bounds.validation.test.ts
src/tools/video-editor/lib/renderRouter.test.ts
src/tools/video-editor/lib/renderRouter.ts
src/tools/video-editor/lib/resize-math.test.ts
src/tools/video-editor/lib/resize-math.ts
src/tools/video-editor/lib/resolve-overlaps.ts
src/tools/video-editor/lib/sequence-component-catalog.ts
src/tools/video-editor/lib/sequence-drafts.test.ts
src/tools/video-editor/lib/sequence-drafts.ts
src/tools/video-editor/lib/sequence-public.ts
src/tools/video-editor/lib/serialize.test.ts
src/tools/video-editor/lib/serialize.ts
src/tools/video-editor/lib/sha256.test.ts
src/tools/video-editor/lib/sha256.ts
src/tools/video-editor/lib/shader-catalog.ts
src/tools/video-editor/lib/shot-group-commands.test.ts
src/tools/video-editor/lib/shot-group-commands.ts
src/tools/video-editor/lib/shot-group-contiguity.ts
src/tools/video-editor/lib/snap-edges.ts
src/tools/video-editor/lib/source-code-navigation.test.ts
src/tools/video-editor/lib/source-code-navigation.ts
src/tools/video-editor/lib/source-map-runtime.test.ts
src/tools/video-editor/lib/source-map-runtime.ts
src/tools/video-editor/lib/theme-api.fallback.tsx
src/tools/video-editor/lib/themeTokens.ts
src/tools/video-editor/lib/timeline-asset-durations.ts
src/tools/video-editor/lib/timeline-asset-plans.ts
src/tools/video-editor/lib/timeline-data.test.ts
src/tools/video-editor/lib/timeline-data.ts
src/tools/video-editor/lib/timeline-domain.live-bindings.test.ts
src/tools/video-editor/lib/timeline-domain.shaders.test.ts
src/tools/video-editor/lib/timeline-domain.transition.test.ts
src/tools/video-editor/lib/timeline-domain.ts
src/tools/video-editor/lib/timeline-golden-replay.test.ts
src/tools/video-editor/lib/timeline-mutation-engine.ts
src/tools/video-editor/lib/timeline-patch.test.ts
src/tools/video-editor/lib/timeline-patch.ts
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts
src/tools/video-editor/lib/timeline-reader.test.ts
src/tools/video-editor/lib/timeline-reader.ts
src/tools/video-editor/lib/timeline-save-utils.test.ts
src/tools/video-editor/lib/timeline-save-utils.ts
src/tools/video-editor/lib/timeline-scale.test.ts
src/tools/video-editor/lib/timeline-scale.ts
src/tools/video-editor/lib/timeline-schema.fallback.ts
src/tools/video-editor/lib/timeline-viewport-events.ts
src/tools/video-editor/lib/video-editor-path.ts
src/tools/video-editor/pages/VideoEditorPage.test.tsx
src/tools/video-editor/pages/VideoEditorPage.tsx
src/tools/video-editor/public-browser.acceptance.test.tsx
src/tools/video-editor/registration.test.ts
src/tools/video-editor/render/renderPipeline.ts
src/tools/video-editor/render/renderRuntime.ts
src/tools/video-editor/runtime-components/DynamicComponentRegistry.test.tsx
src/tools/video-editor/runtime-components/DynamicComponentRegistry.ts
src/tools/video-editor/runtime-components/compileWithGlobals.ts
src/tools/video-editor/runtime-components/index.ts
src/tools/video-editor/runtime/ContributionErrorBoundary.test.tsx
src/tools/video-editor/runtime/ContributionErrorBoundary.tsx
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx
src/tools/video-editor/runtime/VideoEditorDialogHost.tsx
src/tools/video-editor/runtime/agentToolContracts.test.ts
src/tools/video-editor/runtime/agentToolContracts.ts
src/tools/video-editor/runtime/agentToolInvocationAdapters.ts
src/tools/video-editor/runtime/agentToolInvocationService.ts
src/tools/video-editor/runtime/agentToolRegistry.test.ts
src/tools/video-editor/runtime/agentToolRegistry.ts
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts
src/tools/video-editor/runtime/browserLocalPersistenceStore.ts
src/tools/video-editor/runtime/clipTypeRegistrationService.ts
src/tools/video-editor/runtime/commandPredicates.test.ts
src/tools/video-editor/runtime/commandPredicates.ts
src/tools/video-editor/runtime/commandRegistry.test.ts
src/tools/video-editor/runtime/commandRegistry.ts
src/tools/video-editor/runtime/diagnosticCollectionSync.ts
src/tools/video-editor/runtime/effectRegistrationService.test.ts
src/tools/video-editor/runtime/effectRegistrationService.ts
src/tools/video-editor/runtime/exportGuard.test.ts
src/tools/video-editor/runtime/exportGuard.ts
src/tools/video-editor/runtime/extensionIntegrity.test.ts
src/tools/video-editor/runtime/extensionIntegrity.ts
src/tools/video-editor/runtime/extensionLifecycle.test.ts
src/tools/video-editor/runtime/extensionLifecycle.ts
src/tools/video-editor/runtime/extensionLoader.test.ts
src/tools/video-editor/runtime/extensionLoader.ts
src/tools/video-editor/runtime/extensionLockMetadata.test.ts
src/tools/video-editor/runtime/extensionLockMetadata.ts
src/tools/video-editor/runtime/extensionMigration.test.ts
src/tools/video-editor/runtime/extensionMigration.ts
src/tools/video-editor/runtime/extensionPackageManifest.test.ts
src/tools/video-editor/runtime/extensionPackageManifest.ts
src/tools/video-editor/runtime/extensionPersistenceCache.test.ts
src/tools/video-editor/runtime/extensionPersistenceCache.ts
src/tools/video-editor/runtime/extensionReferenceReport.test.ts
src/tools/video-editor/runtime/extensionReferenceReport.ts
src/tools/video-editor/runtime/extensionRendererRegistry.test.ts
src/tools/video-editor/runtime/extensionRendererRegistry.ts
src/tools/video-editor/runtime/extensionSettings.test.ts
src/tools/video-editor/runtime/extensionSettings.ts
src/tools/video-editor/runtime/extensionStateRepository.test.ts
src/tools/video-editor/runtime/extensionStateRepository.ts
src/tools/video-editor/runtime/extensionStateRepositoryIndexedDB.test.ts
src/tools/video-editor/runtime/extensionStateRepositoryIndexedDB.ts
src/tools/video-editor/runtime/extensionStateRepositoryProvider.test.ts
src/tools/video-editor/runtime/extensionStateRepositoryProvider.ts
src/tools/video-editor/runtime/extensionSurface.test.ts
src/tools/video-editor/runtime/extensionSurface.ts
src/tools/video-editor/runtime/liveBake.test.ts
src/tools/video-editor/runtime/liveBake.ts
src/tools/video-editor/runtime/liveDataRegistry.test.ts
src/tools/video-editor/runtime/liveDataRegistry.ts
src/tools/video-editor/runtime/liveMapping.test.ts
src/tools/video-editor/runtime/liveMapping.ts
src/tools/video-editor/runtime/livePermissions.test.ts
src/tools/video-editor/runtime/livePermissions.ts
src/tools/video-editor/runtime/liveRecording.test.ts
src/tools/video-editor/runtime/liveRecording.ts
src/tools/video-editor/runtime/liveSteering.test.ts
src/tools/video-editor/runtime/liveSteering.ts
src/tools/video-editor/runtime/outputFormatRegistry.test.ts
src/tools/video-editor/runtime/outputFormatRegistry.ts
src/tools/video-editor/runtime/ports.ts
src/tools/video-editor/runtime/processCommandRegistration.test.ts
src/tools/video-editor/runtime/processCommandRegistration.ts
src/tools/video-editor/runtime/renderPlanner.test.ts
src/tools/video-editor/runtime/renderPlanner.ts
src/tools/video-editor/runtime/renderability.test.ts
src/tools/video-editor/runtime/renderability.ts
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts
src/tools/video-editor/runtime/shaderRegistrationService.ts
src/tools/video-editor/runtime/transitionRegistrationService.ts
src/tools/video-editor/runtime/useExtensionLoaderWiring.ts
src/tools/video-editor/runtime/useVideoEditorRenderContext.ts
src/tools/video-editor/sequence.test.ts
src/tools/video-editor/sequence.ts
src/tools/video-editor/sequences/DynamicSequenceRegistry.ts
src/tools/video-editor/sequences/SequenceComponentRegistryContext.tsx
src/tools/video-editor/sequences/aiSequenceComponentPrompt.test.ts
src/tools/video-editor/sequences/compileSequenceComponent.tsx
src/tools/video-editor/sequences/components/ImageJumpSequence.tsx
src/tools/video-editor/sequences/components/TitleCardSequence.tsx
src/tools/video-editor/sequences/controlsManifest.test.ts
src/tools/video-editor/sequences/controlsManifest.ts
src/tools/video-editor/sequences/generation.ts
src/tools/video-editor/sequences/getBundledComponentSource.ts
src/tools/video-editor/sequences/headlessRender.test.ts
src/tools/video-editor/sequences/headlessRender.ts
src/tools/video-editor/sequences/materialize.test.ts
src/tools/video-editor/sequences/materialize.ts
src/tools/video-editor/sequences/metadata.test.ts
src/tools/video-editor/sequences/metadata.ts
src/tools/video-editor/sequences/registry.test.ts
src/tools/video-editor/sequences/registry.ts
src/tools/video-editor/sequences/validation.test.ts
src/tools/video-editor/sequences/validation.ts
src/tools/video-editor/settings/useEditorSettings.ts
src/tools/video-editor/settings/videoEditorDefaults.ts
src/tools/video-editor/shaders/compile/diagnostics.test.ts
src/tools/video-editor/shaders/compile/diagnostics.ts
src/tools/video-editor/shaders/compile/index.ts
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts
src/tools/video-editor/shaders/compile/webgl-adapter.ts
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts
src/tools/video-editor/shaders/preview/index.ts
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts
src/tools/video-editor/shaders/registry/ShaderEffectRegistryContext.tsx
src/tools/video-editor/shaders/registry/index.ts
src/tools/video-editor/shaders/registry/types.ts
src/tools/video-editor/state/sequenceCreatorStore.test.ts
src/tools/video-editor/state/sequenceCreatorStore.ts
src/tools/video-editor/testing.test.ts
src/tools/video-editor/testing.ts
src/tools/video-editor/testing/InMemoryDataProvider.extensionPersistence.test.ts
src/tools/video-editor/testing/InMemoryDataProvider.ts
src/tools/video-editor/testing/__tests__/providerCompatibility.astrid.test.ts
src/tools/video-editor/testing/__tests__/providerCompatibility.browserInMemory.test.ts
src/tools/video-editor/testing/__tests__/providerCompatibility.inmemory.test.ts
src/tools/video-editor/testing/__tests__/providerCompatibility.supabase.test.ts
src/tools/video-editor/testing/banodoco-stubs/registry.generated.ts
src/tools/video-editor/testing/banodoco-stubs/theme-api.tsx
src/tools/video-editor/testing/banodoco-stubs/timeline-schema.ts
src/tools/video-editor/testing/coreTestPorts.ts
src/tools/video-editor/testing/providerCompatibility.shared.ts
src/tools/video-editor/transitions/catalog.test.ts
src/tools/video-editor/transitions/catalog.ts
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts
src/tools/video-editor/transitions/registry/TransitionRegistry.ts
src/tools/video-editor/transitions/registry/TransitionRegistryContext.tsx
src/tools/video-editor/transitions/registry/index.ts
src/tools/video-editor/transitions/registry/types.ts
src/tools/video-editor/transitions/validation.test.ts
src/tools/video-editor/transitions/validation.ts
src/tools/video-editor/types/agent-session.ts
src/tools/video-editor/types/history.ts
src/tools/video-editor/types/index.ts
src/tools/video-editor/types/timeline-canvas.ts

exec
/bin/zsh -lc 'rg -n "composition|spine|graph|renderPlanner|renderability|target path|targetPath|output format|outputFormat|shader|material|live data|liveData|legacy|authority|authoritative" .megaplan/initiatives/reigh-extension-composition-spine-epic src/sdk src/tools/video-editor docs/extensions docs/video-editor 2>/dev/null' in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
src/tools/video-editor/sequence.test.ts:6:  materializeSequenceConfig,
src/tools/video-editor/sequence.test.ts:51:  it('materializes asset-backed params without mutating persisted asset-key params', () => {
src/tools/video-editor/sequence.test.ts:70:    const materialized = materializeSequenceConfig({
src/tools/video-editor/sequence.test.ts:75:    expect(materialized.clips[0].params).toMatchObject({
src/tools/video-editor/public-browser.acceptance.test.tsx:12:vi.mock('@banodoco/timeline-composition/registry.generated', () => ({
src/sdk/index.ts:265:    shaderId?: string;
src/sdk/index.ts:266:    shaderScope?: ShaderMaterializerRequirementScope;
src/sdk/index.ts:271:// M5: Renderability, blocker, material, and artifact contracts
src/sdk/index.ts:278:  shaderMissingMaterializerBlockerMessage,
src/sdk/index.ts:279:} from '@/tools/video-editor/runtime/renderability.ts';
src/sdk/index.ts:307:} from '@/tools/video-editor/runtime/renderability.ts';
src/sdk/index.ts:384:  // M6: parser, output format, search provider, metadata facet, asset detail section
src/sdk/index.ts:386:  | 'outputFormat'
src/sdk/index.ts:396:  // M13: dedicated shader/WebGL contributions
src/sdk/index.ts:397:  | 'shader'
src/sdk/index.ts:446:  shaderId?: string;
src/sdk/index.ts:450:  outputFormatId?: string;
src/sdk/index.ts:480:  'outputFormat',
src/sdk/index.ts:488:  'shader',
src/sdk/index.ts:677:// M6: Parser / output format / search provider contributions
src/sdk/index.ts:724: * M6: An output format contribution declared in an extension manifest.
src/sdk/index.ts:738:  kind: 'outputFormat';
src/sdk/index.ts:766:/** M12: Compile-only output formats never enter render planning. */
src/sdk/index.ts:772:/** M12: Render-dependent output formats require planner-owned route execution. */
src/sdk/index.ts:778:/** M12: Route/process requirements for a render-dependent output format. */
src/sdk/index.ts:797: * Search providers supply asset/material search results to the host search
src/sdk/index.ts:820:  resultKinds?: readonly ('asset' | 'material')[];
src/sdk/index.ts:1009:/** M13: Color-space posture declared by a shader pass or texture input. */
src/sdk/index.ts:1012:/** M13: Host-owned fallback posture when a shader cannot compile or preview. */
src/sdk/index.ts:1015:/** M13: Texture source categories supported by the V1 shader bridge. */
src/sdk/index.ts:1031: * because the host can provide the default fullscreen-triangle vertex shader.
src/sdk/index.ts:1046:/** M13: Public shader source descriptor. */
src/sdk/index.ts:1052: * V1 supports a single shader per clip scope and one active postprocess shader.
src/sdk/index.ts:1053: * Ordered stacks, multipass FBO chains, feedback buffers, and shader transitions
src/sdk/index.ts:1066:/** M13: Supported shader uniform control/value kinds for V1. */
src/sdk/index.ts:1080:/** M13: Enum option for shader uniform controls. */
src/sdk/index.ts:1093:/** M13: Default values accepted by shader uniform definitions. */
src/sdk/index.ts:1101:/** M13: A host-rendered shader uniform definition. */
src/sdk/index.ts:1114:/** M13: Ordered shader uniform schema. */
src/sdk/index.ts:1117:/** M13: A host-provided texture input binding for a shader. */
src/sdk/index.ts:1131:/** M13: Ordered shader texture binding schema. */
src/sdk/index.ts:1135: * M13: Optional materializer metadata.
src/sdk/index.ts:1148:/** M13: A shader/WebGL contribution declared in an extension manifest. */
src/sdk/index.ts:1152:  kind: 'shader';
src/sdk/index.ts:1153:  /** Identifier used in ctx.shaders.registerShader(). */
src/sdk/index.ts:1154:  shaderId: string;
src/sdk/index.ts:1164:  readonly materializer?: ShaderMaterializerDescriptor;
src/sdk/index.ts:1171:/** M13: Options for imperative shader registration via ctx.shaders.registerShader(). */
src/sdk/index.ts:1178:  readonly materializer?: ShaderMaterializerDescriptor;
src/sdk/index.ts:1182: * M13: Shader registration service available as `ctx.shaders` during activate().
src/sdk/index.ts:1185: * `ctx.effects.registerComponent()`. The `shaderId` must match a
src/sdk/index.ts:1190:    shaderId: string,
src/sdk/index.ts:1350:  | 'material/artifact'
src/sdk/index.ts:1402:  family: 'material/artifact';
src/sdk/index.ts:1414:  /** Enrichment suggestions keyed by asset/material key. */
src/sdk/index.ts:1465:  /** Artifact identifier (asset key, material key, etc.). */
src/sdk/index.ts:1467:  /** Kind of artifact (asset, material, placeholder). */
src/sdk/index.ts:1468:  kind: 'asset' | 'material' | 'placeholder';
src/sdk/index.ts:1477:  /** Asset or material key. */
src/sdk/index.ts:1529:  materials?: readonly { key: string; metadata?: Record<string, unknown> }[];
src/sdk/index.ts:1538:  /** Selected output format ID. */
src/sdk/index.ts:1539:  outputFormatId?: string;
src/sdk/index.ts:1698:  readonly outputKinds?: readonly ('artifact' | 'material' | 'sidecar' | 'diagnostic' | 'planner-result' | 'tool-result')[];
src/sdk/index.ts:1781: * Kind of a live data source.
src/sdk/index.ts:1807: * Lifecycle status of a live data source.
src/sdk/index.ts:1811: *   active     → source is streaming live data
src/sdk/index.ts:1825: * A diagnostic produced by a live source or live data operation.
src/sdk/index.ts:1838: * A provider-scoped live data source.
src/sdk/index.ts:1917: * A single frame/tick of live data.
src/sdk/index.ts:2021: *   render-material — RenderMaterialRef in the deterministic material vocabulary
src/sdk/index.ts:2029:  | 'render-material';
src/sdk/index.ts:2307: * All live data is ephemeral runtime state scoped to the current
src/sdk/index.ts:2377:   * Bake converts live data into asset registry entries, keyframes,
src/sdk/index.ts:2512:  /** Resolved dependency graph at install time. */
src/sdk/index.ts:2801:            'manifest/legacy-migration-shape',
src/sdk/index.ts:2806:            'manifest/legacy-migration-shape',
src/sdk/index.ts:2889:    // ---- Dev mode: compatibility warnings for legacy (M1/local) manifests ----
src/sdk/index.ts:3034:    // M6: parser, output format, search provider, metadata facet, asset detail section
src/sdk/index.ts:3048:    // M13: shader/WebGL contributions
src/sdk/index.ts:3057:  /** Typed migration hooks (preferred); legacy Record<string, unknown>[] accepted. */
src/sdk/index.ts:3064:  renderability?: Record<string, unknown>;
src/sdk/index.ts:3115:   * with the authoritative extension ID and {@link DIAGNOSTIC_SOURCE_EXTENSION}.
src/sdk/index.ts:3210:  /** Read-only material metadata surface (M6). */
src/sdk/index.ts:3211:  readonly materials: MaterialReadSurface;
src/sdk/index.ts:3214:  /** Export service for registering output format handlers (M6). */
src/sdk/index.ts:3227:  materials: 'M6',
src/sdk/index.ts:3393:   * coercion continues to work for already-applied legacy data).
src/sdk/index.ts:3477:   * coercion continues to work for already-applied legacy data).
src/sdk/index.ts:3541:  /** M13: Shader registration service for dedicated WebGL shader passes. */
src/sdk/index.ts:3542:  readonly shaders: ShaderRegistrationService;
src/sdk/index.ts:3605:  shaders?: ShaderRegistrationService,
src/sdk/index.ts:3850:  // ---- shaders service (optional, wired by provider) ------------------------
src/sdk/index.ts:3851:  const shadersService: ShaderRegistrationService = shaders ?? {
src/sdk/index.ts:3852:    registerShader(_shaderId: string, _source: ShaderSourceDescriptor, _options?: ShaderRegistrationOptions): DisposeHandle {
src/sdk/index.ts:3855:        code: 'shaders/not-wired',
src/sdk/index.ts:3856:        message: `Cannot register shader "${_shaderId}" — the ShaderRegistry has not been wired by the host provider.`,
src/sdk/index.ts:3905:    shaders: shadersService,
src/sdk/index.ts:4065:  // M6: parser, output format, search provider, metadata facet, asset detail section
src/sdk/index.ts:4067:  outputFormat: 'M6',
src/sdk/index.ts:4076:  shader: 'M13',
src/sdk/index.ts:4103:  // outputFormat and searchProvider are typed but execution is reserved
src/sdk/index.ts:4132:  // M13: shader is bridged as a dedicated WebGL contribution kind.
src/sdk/index.ts:4133:  if (milestone === 'M13' && kind === 'shader') {
src/sdk/index.ts:4170:} from '@/tools/video-editor/runtime/renderability.ts';
src/sdk/index.ts:4171:import { shaderMissingMaterializerBlockerMessage } from '@/tools/video-editor/runtime/renderability.ts';
src/sdk/index.ts:4216: * authoritatively execute on a given route, or whether it must fall back
src/sdk/index.ts:4237: * renderPlanner aggregation.
src/sdk/index.ts:4262: * renderPlanner.
src/sdk/index.ts:4329:  readonly outputFormatId?: string;
src/sdk/index.ts:4355:  readonly kind: 'timeline' | 'clip' | 'track' | 'asset' | 'material' | 'render-group';
src/sdk/index.ts:4360:  readonly materialRefId?: string;
src/sdk/index.ts:4673:// material-ref, source-ref, render-group, and output-metadata summaries
src/sdk/index.ts:4724: * Live bindings connect a clip parameter to a live data source.
src/sdk/index.ts:4733:  /** Source identifier for the live data source. */
src/sdk/index.ts:4744: * M12: Lightweight material-ref summary extracted from clip data
src/sdk/index.ts:4747: * Material refs point at assets or generated materials consumed by a clip.
src/sdk/index.ts:4750:  /** Unique identifier for this material ref. */
src/sdk/index.ts:4752:  /** The clip that consumes this material. */
src/sdk/index.ts:4754:  /** Asset key in the timeline registry, when the material is an asset. */
src/sdk/index.ts:4756:  /** Media kind of the referenced material. */
src/sdk/index.ts:4758:  /** Determinism posture for this material ref. */
src/sdk/index.ts:4760:  /** Render group this material contributes to, when part of a multi-pass group. */
src/sdk/index.ts:4762:  /** Pass name this material contributes, when known. */
src/sdk/index.ts:4764:  /** Whether this material can be composited into a render group. */
src/sdk/index.ts:4779:  materialRefId?: string;
src/sdk/index.ts:4780:  /** Current pass status from the planner/material registry projection. */
src/sdk/index.ts:4892:  materialRefs?: readonly TimelineMaterialRefSummary[];
src/sdk/index.ts:4896:  shaders?: readonly TimelineShaderSummary[];
src/sdk/index.ts:4924:  materialRefs?: readonly TimelineMaterialRefSummary[];
src/sdk/index.ts:4941:/** Lightweight shader metadata summary for provider-free planner inspection. */
src/sdk/index.ts:4944:  shaderId: string;
src/sdk/index.ts:4968: * Inspects clip types, effects, transitions, live bindings, and material
src/sdk/index.ts:5133:  if (snapshot.materialRefs) {
src/sdk/index.ts:5134:    for (const ref of snapshot.materialRefs) {
src/sdk/index.ts:5140:        id: nextId('materialRef'),
src/sdk/index.ts:5180:                message: `Source ref "${ref.id}" on clip "${ref.clipId}" requires materialization before browser export.`,
src/sdk/index.ts:5188:  // ── Shader materializer requirements ───────────────────────────────
src/sdk/index.ts:5189:  if (snapshot.shaders) {
src/sdk/index.ts:5190:    for (const shader of snapshot.shaders) {
src/sdk/index.ts:5191:      if (shader.enabled === false) continue;
src/sdk/index.ts:5195:        extensionId: shader.extensionId,
src/sdk/index.ts:5196:        contributionId: shader.contributionId,
src/sdk/index.ts:5201:        const message = shaderMissingMaterializerBlockerMessage(
src/sdk/index.ts:5202:          shader.shaderId,
src/sdk/index.ts:5203:          shader.scope,
src/sdk/index.ts:5204:          shader.clipId,
src/sdk/index.ts:5207:          id: nextId('shader'),
src/sdk/index.ts:5210:          requiredCapabilities: ['render-material', 'shader-materializer'],
src/sdk/index.ts:5216:            reason: 'missing-material',
src/sdk/index.ts:5948: * The result of executing a compile-only output format.
src/sdk/index.ts:5971: * A compile-only output format handler registered by an extension.
src/sdk/index.ts:5981: * Context passed to an output format handler.
src/sdk/index.ts:5993:  /** The output format contribution ID. */
src/sdk/index.ts:6005:  /** Asset or material reference key. */
src/sdk/index.ts:6008:  kind: 'asset' | 'material';
src/sdk/index.ts:6037: * Receives a query string and returns scored asset/material refs.
src/sdk/index.ts:6056:  /** Optional filter scoping the search to asset/material kind. */
src/sdk/index.ts:6057:  readonly resultKind?: 'asset' | 'material';
src/sdk/index.ts:6098: * Read-only material metadata surface exposed to extension code.
src/sdk/index.ts:6105:   * Get material metadata by its registry key.
src/sdk/index.ts:6106:   * Returns undefined if the material is not found.
src/sdk/index.ts:6108:  get(materialKey: string): Readonly<Record<string, unknown>> | undefined;
src/sdk/index.ts:6111:   * List all material keys known to the registry.
src/sdk/index.ts:6116:   * Check whether a material key exists in the registry.
src/sdk/index.ts:6118:  has(materialKey: string): boolean;
src/sdk/index.ts:6126:// The `assets`, `materials`, and `export` members are typed here
src/sdk/index.ts:6135: * Export service available to extensions for registering output format
src/sdk/index.ts:6144:   * Register a compile-only output format handler.
src/sdk/index.ts:6159:/** Options for imperative output format registration. */
src/tools/video-editor/testing.test.ts:25:vi.mock('@banodoco/timeline-composition/registry.generated', () => ({
src/tools/video-editor/testing.test.ts:29:vi.mock('@banodoco/timeline-composition/theme-api', () => ({
src/tools/video-editor/data/AstridBridgeDataProvider.ts:116:  | { state: 'materialized'; file: string }
src/tools/video-editor/data/AstridBridgeDataProvider.ts:213:  private materializationStates = new Map<string, AssetMaterializationState>();
src/tools/video-editor/data/AstridBridgeDataProvider.ts:251:    for (const [assetId, state] of this.materializationStates) {
src/tools/video-editor/data/AstridBridgeDataProvider.ts:310:      const materializedRegistry = await this.materializeGenerationAssets(timelineId, nextRegistry);
src/tools/video-editor/data/AstridBridgeDataProvider.ts:311:      await this.writeLocalJson(this.localTimelineFiles.timelineHandle, REGISTRY_JSON_FILENAME, materializedRegistry);
src/tools/video-editor/data/AstridBridgeDataProvider.ts:316:        registry: materializedRegistry,
src/tools/video-editor/data/AstridBridgeDataProvider.ts:553:    const materializedRegistry = await this.materializeGenerationAssets(timelineId, normalizedRegistry);
src/tools/video-editor/data/AstridBridgeDataProvider.ts:554:    if (JSON.stringify(materializedRegistry) !== beforeMaterialization) {
src/tools/video-editor/data/AstridBridgeDataProvider.ts:555:      await this.writeLocalJson(localFiles.timelineHandle, REGISTRY_JSON_FILENAME, materializedRegistry);
src/tools/video-editor/data/AstridBridgeDataProvider.ts:564:      registry: materializedRegistry,
src/tools/video-editor/data/AstridBridgeDataProvider.ts:811:  private async materializeGenerationAssets(
src/tools/video-editor/data/AstridBridgeDataProvider.ts:823:      if (!entry?.generationId || this.hasLocalFile(entry) || this.materializationStates.get(assetId)?.state === 'skipped-with-diagnostic') {
src/tools/video-editor/data/AstridBridgeDataProvider.ts:824:        if (!this.materializationStates.has(assetId)) {
src/tools/video-editor/data/AstridBridgeDataProvider.ts:825:          this.materializationStates.set(assetId, { state: 'not-attempted' });
src/tools/video-editor/data/AstridBridgeDataProvider.ts:830:      this.materializationStates.set(assetId, { state: 'not-attempted' });
src/tools/video-editor/data/AstridBridgeDataProvider.ts:831:      const result = await this.materializeGenerationAsset(timelineId, assetId, entry);
src/tools/video-editor/data/AstridBridgeDataProvider.ts:834:        this.materializationStates.set(assetId, { state: 'materialized', file: result.entry.file });
src/tools/video-editor/data/AstridBridgeDataProvider.ts:837:        this.materializationStates.set(assetId, {
src/tools/video-editor/data/AstridBridgeDataProvider.ts:852:  private async materializeGenerationAsset(
src/tools/video-editor/data/AstridBridgeDataProvider.ts:861:      throw new Error('Generation materialization requires local timeline files and a generationId');
src/tools/video-editor/keyframes/index.test.ts:1626:  it('later automation clip overrides earlier one for same target path (last-write-wins)', () => {
src/tools/video-editor/data/SupabaseDataProvider.test.ts:256:  it('loadTimeline and loadAssetRegistry keep reading materialized Supabase rows', async () => {
src/tools/video-editor/data/SupabaseDataProvider.test.ts:881:    it('the append-service CAS is the authoritative conflict boundary for Supabase', async () => {
src/tools/video-editor/components/EffectCreatorPanel.test.tsx:99:vi.mock('@/tools/video-editor/compositions/AudioAnalysisProvider.tsx', () => ({
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:44:} from '@/tools/video-editor/runtime/outputFormatRegistry';
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:47:} from '@/tools/video-editor/runtime/outputFormatRegistry';
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:783:  it('materializes generation-backed assets to sources/assets and persists a consistent registry after download', async () => {
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:852:      state: 'materialized',
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:857:  it('keeps failed generation materialization out of the persisted registry and records a diagnostic', async () => {
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:910:  it('materializes resolvable assets, preserves failed entries, and surfaces diagnostics in one local registry pass', async () => {
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:1007:      state: 'materialized',
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:1029:  it('does not automatically retry skipped assets on local save but still materializes newly attempted ones', async () => {
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:1141:    const materializedAssetIds = resolveGenerationAssetMock.mock.calls.map(([request]) => request.assetId);
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:1144:    expect(materializedAssetIds).toEqual(['asset-new']);
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:1169:          state: 'materialized',
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:2208:            { ref: 'mat-1', kind: 'material', score: 0.75, excerpt: 'Material match from e2e' },
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:2241:        expect(matMatch.kind).toBe('material');
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:2249:      // Build a compile-only output format handler that serializes the asset metadata to JSON
src/tools/video-editor/data/AstridBridgeDataProvider.test.ts:2290:        kind: 'outputFormat',
src/tools/video-editor/components/PendingMaterialPlaceholder.tsx:3:import type { RenderPlannerMaterialStatus } from '@/tools/video-editor/runtime/renderPlanner.ts';
src/tools/video-editor/components/PendingMaterialPlaceholder.tsx:7:  material: RenderMaterialRef;
src/tools/video-editor/components/PendingMaterialPlaceholder.tsx:14:    label: 'pending material missing',
src/tools/video-editor/components/PendingMaterialPlaceholder.tsx:20:    label: 'materializing updated material',
src/tools/video-editor/components/PendingMaterialPlaceholder.tsx:26:    label: 'pending materialization',
src/tools/video-editor/components/PendingMaterialPlaceholder.tsx:32:    label: 'material ready',
src/tools/video-editor/components/PendingMaterialPlaceholder.tsx:48:  material,
src/tools/video-editor/components/PendingMaterialPlaceholder.tsx:56:      data-testid="pending-material-placeholder"
src/tools/video-editor/components/PendingMaterialPlaceholder.tsx:58:      data-material-ref-id={material.id}
src/tools/video-editor/components/PendingMaterialPlaceholder.tsx:59:      data-material-state={status.state}
src/tools/video-editor/components/PendingMaterialPlaceholder.tsx:76:        <div>{copy.label}: {material.id}</div>
src/sdk/manifest-schema-validation.test.ts:161:          'comments', 'dependsOn', 'renderability', 'settingsDefaults',
src/sdk/manifest-schema-validation.test.ts:324:      expect(kindEnum).toContain('shader');
src/tools/video-editor/clip-types/runtime.test.ts:63:    // returns 'unknown' from this legacy path. Consumers should use
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:6:  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m0-decisions-fixtures.md
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:7:  branch: epic/composition-spine-m0-decisions-fixtures
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:15:  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m1a-reference-identity.md
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:16:  branch: epic/composition-spine-m1a-reference-identity
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:22:    graph patch vocabulary, and first shader-scope validation extraction.
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:23:- label: m1b-shader-graph-authority
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:24:  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m1b-shader-graph-authority.md
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:25:  branch: epic/composition-spine-m1b-shader-graph-authority
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:30:  notes: Make CompositionGraph projection authoritative for shader/ref facts and contribution-index
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:33:  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m2-target-paths-schema.md
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:34:  branch: epic/composition-spine-m2-target-paths-schema
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:39:  notes: Define V1 target paths, schema capability, animates/binds-live edges, and
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:41:- label: m3a-material-status-matrix
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:42:  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m3a-material-status-matrix.md
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:43:  branch: epic/composition-spine-m3a-material-status-matrix
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:48:  notes: Lock material statuses, detail taxonomy, helper predicates, blocking matrix,
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:51:  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m3b-live-binding-capture.md
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:52:  branch: epic/composition-spine-m3b-live-binding-capture
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:58:    graph-owned keyframe patch execution for live/bake paths.
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:59:- label: m3c-agent-material-promotion
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:60:  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m3c-agent-material-promotion.md
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:61:  branch: epic/composition-spine-m3c-agent-material-promotion
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:66:  notes: Promote agent-produced materials to durable RenderMaterial/RenderArtifact
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:68:- label: m4-clip-shader-keyframes
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:69:  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m4-clip-shader-keyframes.md
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:70:  branch: epic/composition-spine-m4-clip-shader-keyframes
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:75:  notes: Execute shader assignment, shader-uniform keyframes, clip-type refs, graph-projected
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:76:    requires edges, and the clip shader canary.
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:78:  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m5-effects-transitions-mask.md
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:79:  branch: epic/composition-spine-m5-effects-transitions-mask
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:84:  notes: Add effect/transition refs, effect live binding, transition mask material
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:87:  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m6a-process-runtime-core.md
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:88:  branch: epic/composition-spine-m6a-process-runtime-core
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:96:  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m6b-process-ux-canary.md
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:97:  branch: epic/composition-spine-m6b-process-ux-canary
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:105:  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m7a-output-format-routes.md
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:106:  branch: epic/composition-spine-m7a-output-format-routes
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:111:  notes: Introduce graph-backed output-format route planning, route artifacts, typed
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:114:  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m7b-output-format-sidecars.md
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:115:  branch: epic/composition-spine-m7b-output-format-sidecars
src/tools/video-editor/transitions/catalog.ts:8: * and deterministic renderability metadata. The resolver always prefers
src/tools/video-editor/transitions/catalog.ts:45:    renderability: Object.freeze({
src/tools/video-editor/transitions/catalog.ts:258:export function materializeTransitionDefaults(
src/tools/video-editor/transitions/catalog.ts:277: * object), this function materializes the schema defaults from the resolved
src/tools/video-editor/transitions/catalog.ts:305:  const defaults = materializeTransitionDefaults(record.schema);
src/tools/video-editor/transitions/validation.test.ts:36:    renderability: {
src/tools/video-editor/transitions/validation.test.ts:456:  it('returns set-transition with materialized defaults for empty params', () => {
src/tools/video-editor/transitions/validation.test.ts:504:  it('returns clear-transition with explicit null transition for malformed legacy objects', () => {
src/tools/video-editor/transitions/validation.test.ts:505:    // Simulate a legacy transition object that somehow got corrupted
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:22:} from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:53: * Synchronous live data read facade for renderers.
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:126:  readonly renderability: ContributionRenderability;
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:213:  renderability: ContributionRenderability,
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:216:    ...renderability,
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:218:      renderability.capabilities.map((c) => Object.freeze({ ...c })),
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:220:    ...(renderability.blockers
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:223:            renderability.blockers.map((b) => Object.freeze({ ...b })),
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:233:    renderability: freezeRenderability(record.renderability),
src/tools/video-editor/components/SequenceCreator/CodePathPreview.tsx:134:      compositionWidth={PREVIEW_WIDTH}
src/tools/video-editor/components/SequenceCreator/CodePathPreview.tsx:135:      compositionHeight={PREVIEW_HEIGHT}
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:21:    renderability: {
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:190:      renderability: current.renderability,
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:209:      renderability: current.renderability,
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:323:  // ---- renderability defaults ---------------------------------------------
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:325:  it('records preserve their declared renderability', () => {
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:327:      renderability: {
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:342:    const previewCap = resolved.renderability.capabilities.find((c) => c.route === 'preview');
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:347:    const browserCap = resolved.renderability.capabilities.find((c) => c.route === 'browser-export');
src/tools/video-editor/clip-types/ClipTypeRegistry.test.ts:352:    const workerCap = resolved.renderability.capabilities.find((c) => c.route === 'worker-export');
src/tools/video-editor/transitions/registry/types.ts:2:import type { ContributionRenderability } from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/transitions/registry/types.ts:10:  | 'legacy-db-transition'
src/tools/video-editor/transitions/registry/types.ts:25:  readonly renderability: ContributionRenderability;
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.test.tsx:602:  it('client-validates generated drafts and previews the selected draft through Remotion with materialized assets', async () => {
src/tools/video-editor/transitions/registry/TransitionRegistry.ts:58:  renderability: TransitionRegistryRecord['renderability'],
src/tools/video-editor/transitions/registry/TransitionRegistry.ts:59:): TransitionRegistryRecord['renderability'] {
src/tools/video-editor/transitions/registry/TransitionRegistry.ts:61:    ...renderability,
src/tools/video-editor/transitions/registry/TransitionRegistry.ts:63:      renderability.capabilities.map((capability) => Object.freeze({ ...capability })),
src/tools/video-editor/transitions/registry/TransitionRegistry.ts:65:    ...(renderability.blockers
src/tools/video-editor/transitions/registry/TransitionRegistry.ts:68:            renderability.blockers.map((blocker) => Object.freeze({ ...blocker })),
src/tools/video-editor/transitions/registry/TransitionRegistry.ts:78:    renderability: freezeRenderability(record.renderability),
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:15:    renderability: {
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:51:    expect(Object.isFrozen(snapshotA.records[0].renderability)).toBe(true);
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:52:    expect(Object.isFrozen(snapshotA.records[0].renderability.capabilities)).toBe(true);
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:217:  it('keeps record diagnostics and renderability metadata available in snapshots', () => {
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:225:      renderability: {
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:250:    expect(entry?.renderability.capabilities[0].route).toBe('browser-export');
src/tools/video-editor/transitions/registry/TransitionRegistry.test.ts:251:    expect(entry?.renderability.blockers?.[0].reason).toBe('preview-only');
src/tools/video-editor/testing/__tests__/providerCompatibility.supabase.test.ts:179:    it('loadTimeline returns configVersion from materialized Supabase row', async () => {
src/tools/video-editor/testing/__tests__/providerCompatibility.supabase.test.ts:198:    it('loadAssetRegistry returns asset data from the materialized row', async () => {
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx:43:import { materializeResolvedSequenceConfig } from '@/tools/video-editor/sequences/materialize.ts';
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx:129:  return materializeResolvedSequenceConfig({
src/tools/video-editor/transitions/catalog.test.ts:2: * Tests for transition schema default materialization.
src/tools/video-editor/transitions/catalog.test.ts:8:  materializeTransitionDefaults,
src/tools/video-editor/transitions/catalog.test.ts:24:    renderability: {
src/tools/video-editor/transitions/catalog.test.ts:43:// materializeTransitionDefaults
src/tools/video-editor/transitions/catalog.test.ts:46:describe('materializeTransitionDefaults', () => {
src/tools/video-editor/transitions/catalog.test.ts:48:    const result = materializeTransitionDefaults(undefined);
src/tools/video-editor/transitions/catalog.test.ts:54:    const result = materializeTransitionDefaults(null as unknown as ParameterSchema);
src/tools/video-editor/transitions/catalog.test.ts:60:    const result = materializeTransitionDefaults([]);
src/tools/video-editor/transitions/catalog.test.ts:65:  it('materializes number defaults from schema', () => {
src/tools/video-editor/transitions/catalog.test.ts:69:    const result = materializeTransitionDefaults(schema);
src/tools/video-editor/transitions/catalog.test.ts:74:  it('materializes number fallback to min when no default specified', () => {
src/tools/video-editor/transitions/catalog.test.ts:78:    const result = materializeTransitionDefaults(schema);
src/tools/video-editor/transitions/catalog.test.ts:82:  it('materializes number fallback to 0 when no min or default', () => {
src/tools/video-editor/transitions/catalog.test.ts:86:    const result = materializeTransitionDefaults(schema);
src/tools/video-editor/transitions/catalog.test.ts:90:  it('materializes select defaults from schema', () => {
src/tools/video-editor/transitions/catalog.test.ts:103:    const result = materializeTransitionDefaults(schema);
src/tools/video-editor/transitions/catalog.test.ts:107:  it('materializes select fallback to first option when no default', () => {
src/tools/video-editor/transitions/catalog.test.ts:119:    const result = materializeTransitionDefaults(schema);
src/tools/video-editor/transitions/catalog.test.ts:123:  it('materializes boolean defaults from schema', () => {
src/tools/video-editor/transitions/catalog.test.ts:127:    const result = materializeTransitionDefaults(schema);
src/tools/video-editor/transitions/catalog.test.ts:131:  it('materializes boolean fallback to false when no default', () => {
src/tools/video-editor/transitions/catalog.test.ts:135:    const result = materializeTransitionDefaults(schema);
src/tools/video-editor/transitions/catalog.test.ts:139:  it('materializes color defaults from schema', () => {
src/tools/video-editor/transitions/catalog.test.ts:143:    const result = materializeTransitionDefaults(schema);
src/tools/video-editor/transitions/catalog.test.ts:147:  it('materializes color fallback to #000000 when no default', () => {
src/tools/video-editor/transitions/catalog.test.ts:151:    const result = materializeTransitionDefaults(schema);
src/tools/video-editor/transitions/catalog.test.ts:155:  it('materializes audio-binding defaults from schema', () => {
src/tools/video-editor/transitions/catalog.test.ts:164:    const result = materializeTransitionDefaults(schema);
src/tools/video-editor/transitions/catalog.test.ts:168:  it('materializes audio-binding fallback when no default', () => {
src/tools/video-editor/transitions/catalog.test.ts:172:    const result = materializeTransitionDefaults(schema);
src/tools/video-editor/transitions/catalog.test.ts:176:  it('materializes multiple parameters', () => {
src/tools/video-editor/transitions/catalog.test.ts:182:    const result = materializeTransitionDefaults(schema);
src/tools/video-editor/transitions/catalog.test.ts:194:    const a = materializeTransitionDefaults(schema);
src/tools/video-editor/transitions/catalog.test.ts:195:    const b = materializeTransitionDefaults(schema);
src/tools/video-editor/transitions/catalog.test.ts:241:  it('materializes defaults when clip has no params', () => {
src/tools/video-editor/transitions/catalog.test.ts:254:  it('materializes defaults when clip has empty params object', () => {
src/tools/video-editor/transitions/catalog.test.ts:275:  it('does not mutate existing clip params when materializing', () => {
src/tools/video-editor/transitions/catalog.test.ts:301:  it('materializes defaults from schema with multiple parameters', () => {
src/tools/video-editor/transitions/catalog.test.ts:318:  it('preserves transition type and duration while materializing defaults', () => {
src/tools/video-editor/transitions/validation.ts:5: * registry snapshot (built-ins + contributed), detect malformed legacy data,
src/tools/video-editor/transitions/validation.ts:101:   * - For 'set-transition': the repaired ClipTransition with defaults materialized.
src/tools/video-editor/transitions/validation.ts:148: * Handles legacy malformed data:
src/tools/video-editor/transitions/validation.ts:414:  // Case 2: Resolvable but has missing-params warning → materialize defaults
src/tools/video-editor/lib/timeline-save-utils.test.ts:600:  it('buildDataFromCurrentRegistry materializes rows from clip geometry while keeping soft-tag groups unchanged', () => {
src/tools/video-editor/lib/timeline-save-utils.test.ts:654:  it('repairs legacy pinned groups to soft-tag `clipIds` without re-projecting clip geometry', () => {
src/tools/video-editor/commands/media.ts:448:export const materializeProvisionedMediaCommand = (
src/tools/video-editor/components/Canary/WritingPanelCanary.tsx:63:    message: 'Word "therefore" used 3 times in this paragraph.',
src/tools/video-editor/commands/index.ts:14:  materializeProvisionedMediaCommand,
src/tools/video-editor/lib/overlay-bounds.ts:67:  compositionWidth: number,
src/tools/video-editor/lib/overlay-bounds.ts:68:  compositionHeight: number,
src/tools/video-editor/lib/overlay-bounds.ts:70:  left: (bounds.x / compositionWidth) * layout.width,
src/tools/video-editor/lib/overlay-bounds.ts:71:  top: (bounds.y / compositionHeight) * layout.height,
src/tools/video-editor/lib/overlay-bounds.ts:72:  width: (bounds.width / compositionWidth) * layout.width,
src/tools/video-editor/lib/overlay-bounds.ts:73:  height: (bounds.height / compositionHeight) * layout.height,
src/tools/video-editor/components/RoundtripResultsPanel.tsx:30:function materialPayload(material: RenderMaterial | undefined, artifact: RenderArtifact | undefined) {
src/tools/video-editor/components/RoundtripResultsPanel.tsx:32:    material,
src/tools/video-editor/components/RoundtripResultsPanel.tsx:34:    locator: material?.locator ?? artifact?.locator,
src/tools/video-editor/components/RoundtripResultsPanel.tsx:35:    mediaKind: material?.mediaKind ?? artifact?.mediaKind,
src/tools/video-editor/components/RoundtripResultsPanel.tsx:44:  const material = firstMaterial(result);
src/tools/video-editor/components/RoundtripResultsPanel.tsx:47:    ...materialPayload(material, artifact),
src/tools/video-editor/components/RoundtripResultsPanel.tsx:59:        target: material?.id ?? artifact?.id ?? result.requestId,
src/tools/video-editor/components/RoundtripResultsPanel.tsx:80:      target: context.targetClipId ?? material?.id ?? result.requestId,
src/tools/video-editor/components/RoundtripResultsPanel.tsx:123:      <ul aria-label="Returned materials">
src/tools/video-editor/components/RoundtripResultsPanel.tsx:124:        {result.returnedMaterials.map((material) => (
src/tools/video-editor/components/RoundtripResultsPanel.tsx:125:          <li key={material.id}>{material.id} {material.mediaKind} {material.locator.uri}</li>
src/tools/video-editor/components/PreviewPanel/RemotionPreview.tsx:6:import { TimelineRenderer } from '@/tools/video-editor/compositions/TimelineRenderer.tsx';
src/tools/video-editor/components/PreviewPanel/RemotionPreview.tsx:77:      compositionWidth: Math.max(1, width),
src/tools/video-editor/components/PreviewPanel/RemotionPreview.tsx:78:      compositionHeight: Math.max(1, height),
src/tools/video-editor/components/PreviewPanel/RemotionPreview.tsx:147:        compositionWidth={metadata.compositionWidth}
src/tools/video-editor/components/PreviewPanel/RemotionPreview.tsx:148:        compositionHeight={metadata.compositionHeight}
src/tools/video-editor/lib/effect-catalog.test.ts:6:import type { ContributionRenderability, RenderCapability, RenderRoute } from '@/tools/video-editor/runtime/renderability';
src/tools/video-editor/lib/effect-catalog.test.ts:46:    renderability: makeRenderability(),
src/tools/video-editor/lib/effect-catalog.test.ts:136:      'legacy-db-effect',
src/tools/video-editor/lib/effect-catalog.test.ts:144:  it('maps renderability through', () => {
src/tools/video-editor/lib/effect-catalog.test.ts:145:    const renderability = makeRenderability({
src/tools/video-editor/lib/effect-catalog.test.ts:148:    const resource = registryRecordToEffectResource(makeRegistryRecord({ renderability }));
src/tools/video-editor/lib/effect-catalog.test.ts:149:    expect(resource.renderability).toBe(renderability);
src/tools/video-editor/lib/effect-catalog.test.ts:191:      'legacy-db-effect',
src/tools/video-editor/lib/effect-catalog.test.ts:354:  it('preserves renderability for preview-only effects', () => {
src/tools/video-editor/lib/effect-catalog.test.ts:355:    const renderability = makeRenderability({
src/tools/video-editor/lib/effect-catalog.test.ts:362:    const record = makeRegistryRecord({ effectId: 'preview-only', renderability });
src/tools/video-editor/lib/effect-catalog.test.ts:367:    expect(catalog.effects[0].renderability).toBe(renderability);
src/tools/video-editor/runtime/liveMapping.ts:29:export type LiveMappingTargetKind = 'clip' | 'effect' | 'material' | 'session' | 'custom';
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:47:  compositionWidth: number;
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:48:  compositionHeight: number;
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:90:  compositionWidth,
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:91:  compositionHeight,
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:142:      x: Math.round(compositionWidth * (1 - trackScale) / 2),
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:143:      y: Math.round(compositionHeight * (1 - trackScale) / 2),
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:144:      width: Math.round(compositionWidth * trackScale),
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:145:      height: Math.round(compositionHeight * trackScale),
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:147:  }, [compositionHeight, compositionWidth, trackScaleMap]);
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:155:    // clip.x/y/width/height (with fallbacks 0/0/compositionW/compositionH).
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:171:        width: clipMeta.width ?? compositionWidth,
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:172:        height: clipMeta.height ?? compositionHeight,
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:181:  }, [compositionHeight, compositionWidth, getTrackDefaultBounds]);
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:275:    if (!player || compositionWidth <= 0 || compositionHeight <= 0) {
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:286:    const videoAspect = compositionWidth / compositionHeight;
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:297:  }, [compositionHeight, compositionWidth, playerContainerRef]);
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:528:    const scaleX = compositionWidth / Math.max(1, layout?.width ?? 1);
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:529:    const scaleY = compositionHeight / Math.max(1, layout?.height ?? 1);
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:550:    compositionHeight,
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:551:    compositionWidth,
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:599:  const fontScale = layout.width / Math.max(1, compositionWidth);
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:608:      {/* Dim entire composition during crop drag, with a hole for the visible crop area */}
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:613:        const vl = ((cropOverlay.bounds.x) / compositionWidth) * 100;
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:614:        const vt = ((cropOverlay.bounds.y) / compositionHeight) * 100;
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:615:        const vr = ((cropOverlay.bounds.x + cropOverlay.bounds.width) / compositionWidth) * 100;
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:616:        const vb = ((cropOverlay.bounds.y + cropOverlay.bounds.height) / compositionHeight) * 100;
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:617:        // Clamp to composition edges (0-100%)
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:640:        // Do NOT clamp overlay bounds to composition — the overlay should extend
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:641:        // beyond the composition edge so users can see and drag their clip back.
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:644:        const style = toOverlayStyle(displayBounds, layout, compositionWidth, compositionHeight);
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:658:              left: ((renderFullBounds.x - displayBounds.x) / compositionWidth) * layout.width,
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:659:              top: ((renderFullBounds.y - displayBounds.y) / compositionHeight) * layout.height,
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:660:              width: (renderFullBounds.width / compositionWidth) * layout.width,
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:661:              height: (renderFullBounds.height / compositionHeight) * layout.height,
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:800:                          // Keep current position (x/y), reset size to composition
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:803:                            width: compositionWidth,
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:804:                            height: compositionHeight,
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:817:                      title="Fill composition"
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:818:                      aria-label="Fill overlay to composition"
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:825:                          width: compositionWidth,
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:826:                          height: compositionHeight,
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:858:      && prev.compositionWidth === next.compositionWidth
src/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx:859:      && prev.compositionHeight === next.compositionHeight
src/tools/video-editor/effects/useAudioReactive.ts:7:} from '@/tools/video-editor/compositions/AudioAnalysisProvider.tsx';
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:120:      compositionSize: { width: 1920, height: 1080 },
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:284:    it('selects the postprocess shader inspector target from the timeline badge', () => {
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:288:          shaderPostprocess: {
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:290:            extensionId: 'ext.shader',
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:292:            shaderId: 'shader.post.grade',
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:299:      const badge = container.querySelector('[data-postprocess-shader-badge="true"]');
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:301:        throw new Error('expected postprocess shader badge');
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:309:        kind: 'shader',
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:310:        shaderScope: 'postprocess',
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:311:        shaderId: 'shader.post.grade',
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:312:        extensionId: 'ext.shader',
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:316:        kind: 'shader',
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:317:        shaderScope: 'postprocess',
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:318:        shaderId: 'shader.post.grade',
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.test.tsx:319:        extensionId: 'ext.shader',
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:15:} from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:20:} from '@/tools/video-editor/runtime/outputFormatRegistry.ts';
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:25:} from '@/tools/video-editor/runtime/outputFormatRegistry.ts';
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:34:    kind: 'outputFormat',
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:190:      outputFormatId: 'metadata-json',
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:198:    expect(artifact.consumedMaterialRefs[0].id).toBe('material.asset.asset-1');
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:199:    expect(artifact.consumedMaterialRefs[1].id).toBe('material.asset.asset-2');
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:510:// Tests: createCompileOnlyArtifact (renderability integration)
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:513:describe('createCompileOnlyArtifact (renderability integration)', () => {
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:604:    expect(artifact.consumedMaterialRefs[0].id).toBe('material.asset.img-1');
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:608:    expect(artifact.consumedMaterialRefs[1].id).toBe('material.asset.vid-2');
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:609:    expect(artifact.consumedMaterialRefs[2].id).toBe('material.asset.aud-3');
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:641:  it('executeCompileOnlyOutputSync only invokes the handler and renderability helpers', () => {
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:665:    // are imported or invoked is proven by the module's own import graph
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:666:    // (outputFormatRegistry.ts imports only from @reigh/editor-sdk and renderability.ts)
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1399:      outputFormatId: 'full-artifact',
src/tools/video-editor/components/PreviewPanel/OverlayEditor.test.tsx:66:      compositionWidth: 1920,
src/tools/video-editor/components/PreviewPanel/OverlayEditor.test.tsx:67:      compositionHeight: 1080,
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:98:  'material/artifact': 'Artifact',
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:169:    case 'material/artifact': {
src/tools/video-editor/runtime/browserLocalPersistenceStore.ts:203: * are best-effort; the base state in localStorage is the authoritative
src/sdk/__tests__/sdk-boundary.test.ts:158:  // M6: Parser / output format / search provider
src/sdk/__tests__/sdk-boundary.test.ts:260:      'materials',
src/sdk/__tests__/sdk-boundary.test.ts:977:// M6: Parser / output format / search provider contribution type interfaces
src/sdk/__tests__/sdk-boundary.test.ts:980:describe('M6: parser/outputFormat/searchProvider type interfaces are importable from @reigh/editor-sdk', () => {
src/sdk/__tests__/sdk-boundary.test.ts:1023:      kind: 'outputFormat',
src/sdk/__tests__/sdk-boundary.test.ts:1031:    expect(contrib.kind).toBe('outputFormat');
src/sdk/__tests__/sdk-boundary.test.ts:1042:      kind: 'outputFormat',
src/sdk/__tests__/sdk-boundary.test.ts:1049:    expect(contrib.kind).toBe('outputFormat');
src/sdk/__tests__/sdk-boundary.test.ts:1057:      kind: 'outputFormat',
src/sdk/__tests__/sdk-boundary.test.ts:1064:      kind: 'outputFormat',
src/sdk/__tests__/sdk-boundary.test.ts:1092:      resultKinds: ['asset', 'material'],
src/sdk/__tests__/sdk-boundary.test.ts:1094:    expect(contrib.resultKinds).toEqual(['asset', 'material']);
src/sdk/__tests__/sdk-boundary.test.ts:1116:  it('outputFormat is typed but execution is reserved (returns M6)', () => {
src/sdk/__tests__/sdk-boundary.test.ts:1117:    expect(contributionKindNotYetBridged('outputFormat')).toBe('M6');
src/sdk/__tests__/sdk-boundary.test.ts:1125:    // outputFormat contributions (both compile-only and render-dependent)
src/sdk/__tests__/sdk-boundary.test.ts:1129:    const bridged = contributionKindNotYetBridged('outputFormat');
src/sdk/__tests__/sdk-boundary.test.ts:1149:    expect(CONTRIBUTION_KIND_MILESTONE.outputFormat).toBe('M6');
src/sdk/__tests__/sdk-boundary.test.ts:1179:    'outputFormatRegistry',
src/sdk/__tests__/sdk-boundary.test.ts:1195:    // Asset/material internal accessors
src/sdk/__tests__/sdk-boundary.test.ts:1197:    'materialStore',
src/sdk/__tests__/sdk-boundary.test.ts:1433:        materials: {},
src/sdk/__tests__/sdk-boundary.test.ts:1723:        materials: {},
src/sdk/__tests__/sdk-boundary.test.ts:2004:        materials: {},
src/sdk/__tests__/sdk-boundary.test.ts:2165:// M5: Renderability, blocker, material, and artifact type interfaces
src/sdk/__tests__/sdk-boundary.test.ts:2195:describe('M5: renderability type interfaces are importable from @reigh/editor-sdk', () => {
src/sdk/__tests__/sdk-boundary.test.ts:2234:      'missing-materializer',
src/sdk/__tests__/sdk-boundary.test.ts:2263:    const renderability: ContributionRenderability = {
src/sdk/__tests__/sdk-boundary.test.ts:2269:    expect(renderability.capabilities).toHaveLength(2);
src/sdk/__tests__/sdk-boundary.test.ts:2296:      reason: 'missing-materializer' as RenderBlockerReason,
src/sdk/__tests__/sdk-boundary.test.ts:2297:      message: 'No materializer available',
src/sdk/__tests__/sdk-boundary.test.ts:2300:    expect(blocker.reason).toBe('missing-materializer');
src/sdk/__tests__/sdk-boundary.test.ts:2369:      materials: [],
src/sdk/__tests__/sdk-boundary.test.ts:2502:      'material/artifact',
src/sdk/__tests__/sdk-boundary.test.ts:2550:      family: 'material/artifact',
src/sdk/__tests__/sdk-boundary.test.ts:2554:    expect(result.family).toBe('material/artifact');
src/sdk/__tests__/sdk-boundary.test.ts:2628:  it('ToolArtifactRef covers asset, material, placeholder kinds', () => {
src/sdk/__tests__/sdk-boundary.test.ts:2629:    const kinds: ToolArtifactRef['kind'][] = ['asset', 'material', 'placeholder'];
src/sdk/__tests__/sdk-boundary.test.ts:2678:      materials: [{ key: 'mat-1' }],
src/sdk/__tests__/sdk-boundary.test.ts:2687:      outputFormatId: 'mp4-export',
src/sdk/__tests__/sdk-boundary.test.ts:2688:      blockers: [{ reason: 'missing-materializer', message: 'Wait for M12' }],
src/sdk/__tests__/sdk-boundary.test.ts:2691:    expect(exportCtx.outputFormatId).toBe('mp4-export');
src/sdk/__tests__/sdk-boundary.test.ts:2887:      outputKinds: ['material', 'sidecar'],
src/sdk/__tests__/sdk-boundary.test.ts:3049:      outputKinds: ['material', 'sidecar', 'diagnostic'],
src/sdk/__tests__/sdk-boundary.test.ts:3055:    expect(op.outputKinds).toEqual(['material', 'sidecar', 'diagnostic']);
src/sdk/__tests__/sdk-boundary.test.ts:3087:describe('M13: shader type interfaces are importable from @reigh/editor-sdk', () => {
src/sdk/__tests__/sdk-boundary.test.ts:3215:      id: 'shader-glow' as ContributionId,
src/sdk/__tests__/sdk-boundary.test.ts:3216:      kind: 'shader',
src/sdk/__tests__/sdk-boundary.test.ts:3217:      shaderId: 'shader.clipGlow',
src/sdk/__tests__/sdk-boundary.test.ts:3225:    expect(contrib.kind).toBe('shader');
src/sdk/__tests__/sdk-boundary.test.ts:3226:    expect(contrib.shaderId).toBe('shader.clipGlow');
src/sdk/__tests__/sdk-boundary.test.ts:3243:      registerShader(_shaderId, _source, _options) {
src/sdk/__tests__/sdk-boundary.test.ts:3248:    const handle = svc.registerShader('shader.test', { kind: 'inline', fragment: 'void main() {}' });
src/sdk/__tests__/sdk-boundary.test.ts:3345:  it('ExportDiagnostic detail includes shader scope fields', () => {
src/sdk/__tests__/sdk-boundary.test.ts:3348:      code: 'export/missing-shader-materializer',
src/sdk/__tests__/sdk-boundary.test.ts:3349:      message: 'Shader has no materializer for export route',
src/sdk/__tests__/sdk-boundary.test.ts:3351:        shaderId: 'shader.glow',
src/sdk/__tests__/sdk-boundary.test.ts:3352:        shaderScope: 'clip' as ShaderMaterializerRequirementScope,
src/sdk/__tests__/sdk-boundary.test.ts:3355:    expect(diag.detail?.shaderId).toBe('shader.glow');
src/sdk/__tests__/sdk-boundary.test.ts:3356:    expect(diag.detail?.shaderScope).toBe('clip');
src/sdk/__tests__/sdk-boundary.test.ts:3581:// M5/M12: Internal renderability types are NOT leaked
src/sdk/__tests__/sdk-boundary.test.ts:3584:describe('M5/M12: internal renderability types are NOT re-exported from @reigh/editor-sdk', () => {
src/sdk/__tests__/sdk-boundary.test.ts:3586:    'renderabilityRegistry',
src/sdk/__tests__/sdk-boundary.test.ts:3593:    'materializeEffect',
src/sdk/__tests__/sdk-boundary.test.ts:3594:    'materializeTransition',
src/sdk/__tests__/sdk-boundary.test.ts:3605:  it('none of the forbidden renderability/process internal names appear as SDK value exports', () => {
src/sdk/__tests__/sdk-boundary.test.ts:3634:    // Contract: SDK must export renderability constants for cross-milestone
src/sdk/__tests__/sdk-boundary.test.ts:3652:      'parser', 'outputFormat', 'searchProvider',
src/sdk/__tests__/sdk-boundary.test.ts:3653:      'effect', 'transition', 'clipType', 'shader',
src/sdk/__tests__/sdk-boundary.test.ts:3664:    // After adding the new re-exports (renderability constants, migration, settings
src/tools/video-editor/components/PropertiesPanel/ClipPanel.transition.test.tsx:6: * Covers: selector with None/built-ins/contributed transitions, provenance/renderability
src/tools/video-editor/components/PropertiesPanel/ClipPanel.transition.test.tsx:74:vi.mock('@banodoco/timeline-composition/registry.generated', () => ({
src/tools/video-editor/components/PropertiesPanel/ClipPanel.transition.test.tsx:129:    compositionWidth: 1920,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.transition.test.tsx:130:    compositionHeight: 1080,
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.test.tsx:549:  it('displays material/artifact result summary', async () => {
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.test.tsx:551:      family: 'material/artifact',
src/tools/video-editor/components/PreviewPanel/PreviewPanel.tsx:39:    compositionSize,
src/tools/video-editor/components/PreviewPanel/PreviewPanel.tsx:50:    compositionSize: timeline.compositionSize,
src/tools/video-editor/components/PreviewPanel/PreviewPanel.tsx:151:                compositionWidth={compositionSize.width}
src/tools/video-editor/components/PreviewPanel/PreviewPanel.tsx:152:                compositionHeight={compositionSize.height}
src/tools/video-editor/components/TimelineEditorShellCore.tsx:406:    const all = renderContext.extensions?.outputFormats ?? [];
src/tools/video-editor/components/TimelineEditorShellCore.tsx:408:  }, [renderContext.extensions?.outputFormats]);
src/tools/video-editor/components/TimelineEditorShellCore.tsx:410:    const all = renderContext.extensions?.outputFormats ?? [];
src/tools/video-editor/components/TimelineEditorShellCore.tsx:412:  }, [renderContext.extensions?.outputFormats]);
src/tools/video-editor/runtime/clipTypeRegistrationService.ts:8: * provenance / owner / schema / renderability / diagnostics, supports HMR
src/tools/video-editor/runtime/clipTypeRegistrationService.ts:34:} from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/runtime/clipTypeRegistrationService.ts:203:    const renderability = buildRenderability(contrib);
src/tools/video-editor/runtime/clipTypeRegistrationService.ts:219:      renderability,
src/tools/video-editor/effects/chromatic-glitch-storm.js:13:  // Drift is now a percentage of composition width — looks consistent at any resolution
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:23:import type { LiveDataRegistry, LiveDataRegistrySnapshot } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:57:  liveDataRegistry?: LiveDataRegistry | null;
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:356:  liveDataRegistry,
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:362:  const registry = liveDataRegistry ?? runtime?.liveDataRegistry ?? null;
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.test.tsx:8:import { createLiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry';
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.test.tsx:124:        liveDataRegistry={registry}
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.test.tsx:153:        liveDataRegistry={registry}
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.test.tsx:181:        liveDataRegistry={registry}
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.test.tsx:216:        liveDataRegistry={registry}
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.test.tsx:240:        liveDataRegistry={invalidRegistry}
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.test.tsx:254:        liveDataRegistry={registry}
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.test.tsx:285:        liveDataRegistry={registry}
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.test.tsx:313:        liveDataRegistry={registry}
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.test.tsx:342:        liveDataRegistry={registry}
src/tools/video-editor/effects/registry/index.ts:15:  legacyDbEffectsToRegistryRecords,
src/tools/video-editor/runtime/browserLocalPersistenceStore.test.ts:1075:      // the base state in localStorage is the authoritative source
src/tools/video-editor/components/__tests__/PreviewPersistence.test.tsx:32:vi.mock('@banodoco/timeline-composition/theme-api', () => ({
src/tools/video-editor/components/__tests__/PreviewPersistence.test.tsx:37:vi.mock('@banodoco/timeline-composition/registry.generated', () => ({
src/tools/video-editor/components/__tests__/PreviewPersistence.test.tsx:41:vi.mock('@banodoco/timeline-composition/theme-api', () => ({
src/tools/video-editor/components/__tests__/PreviewPersistence.test.tsx:314:    compositionSize: { width: 1280, height: 720 },
src/tools/video-editor/components/__tests__/PreviewPersistence.test.tsx:419:      compositionSize: null,
src/tools/video-editor/effects/registry/adapters/index.ts:6:  legacyDbEffectsToRegistryRecords,
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:8:  legacyDbEffectsToRegistryRecords,
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:100:  it('lets adapter callers override owner, status, contribution prefix, and renderability', () => {
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:101:    const renderability = createDefaultEffectRenderability();
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:105:      renderability,
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:112:      renderability,
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:119:    const renderability = records[0].renderability;
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:121:    expect(renderability.defaultRoute).toBe('preview');
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:122:    expect(renderability.determinism).toBe('deterministic');
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:123:    expect(renderability.capabilities).toEqual([
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:141:  it('maps legacy DB effect rows by slug with legacy provenance and compiled string code', () => {
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:144:    const records = legacyDbEffectsToRegistryRecords([
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:157:        contributionId: 'legacy-db:effect:db-shake',
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.test.ts:161:        provenance: 'legacy-db-effect',
src/tools/video-editor/components/MaterialBrowser.tsx:6:} from '@/tools/video-editor/runtime/renderPlanner.ts';
src/tools/video-editor/components/MaterialBrowser.tsx:21:  materials: readonly RenderMaterialRef[];
src/tools/video-editor/components/MaterialBrowser.tsx:22:  materialStatuses?: readonly RenderPlannerMaterialStatus[];
src/tools/video-editor/components/MaterialBrowser.tsx:24:  onAction?: (action: VideoEditorPlannerNextActionDescriptor, material: RenderMaterialRef) => void;
src/tools/video-editor/components/MaterialBrowser.tsx:38:function detailValue(material: RenderMaterialRef, key: string): string {
src/tools/video-editor/components/MaterialBrowser.tsx:39:  const record = material as unknown as Record<string, unknown>;
src/tools/video-editor/components/MaterialBrowser.tsx:40:  return text(record[key] ?? (material.locator as unknown as Record<string, unknown>)[key]);
src/tools/video-editor/components/MaterialBrowser.tsx:44:  material: RenderMaterialRef,
src/tools/video-editor/components/MaterialBrowser.tsx:47:  return statuses.find((status) => status.materialRefId === material.id)
src/tools/video-editor/components/MaterialBrowser.tsx:48:    ?? { materialRefId: material.id, state: material.determinism === 'deterministic' ? 'resolved' : 'unbaked' };
src/tools/video-editor/components/MaterialBrowser.tsx:51:function matches(material: RenderMaterialRef, status: RenderPlannerMaterialStatus, filters: MaterialBrowserFilters): boolean {
src/tools/video-editor/components/MaterialBrowser.tsx:52:  if (filters.producerExtensionId && material.producerExtensionId !== filters.producerExtensionId) return false;
src/tools/video-editor/components/MaterialBrowser.tsx:53:  if (filters.mediaKind && material.mediaKind !== filters.mediaKind) return false;
src/tools/video-editor/components/MaterialBrowser.tsx:54:  if (filters.determinism && material.determinism !== filters.determinism) return false;
src/tools/video-editor/components/MaterialBrowser.tsx:57:  if (filters.passName && detailValue(material, 'passName') !== filters.passName) return false;
src/tools/video-editor/components/MaterialBrowser.tsx:58:  if (filters.renderGroupId && detailValue(material, 'renderGroupId') !== filters.renderGroupId) return false;
src/tools/video-editor/components/MaterialBrowser.tsx:59:  if (filters.sourceRef && !text(material.locator.uri).includes(filters.sourceRef)) return false;
src/tools/video-editor/components/MaterialBrowser.tsx:60:  if (filters.provenance && !text((material as unknown as Record<string, unknown>).provenance).includes(filters.provenance)) return false;
src/tools/video-editor/components/MaterialBrowser.tsx:65:  material: RenderMaterialRef,
src/tools/video-editor/components/MaterialBrowser.tsx:68:  const materialActions = actions.filter((action) =>
src/tools/video-editor/components/MaterialBrowser.tsx:70:    && (action.label.toLowerCase().includes('materialize') || action.message?.toLowerCase().includes('material')));
src/tools/video-editor/components/MaterialBrowser.tsx:71:  return materialActions.find((action) => action.message?.includes(material.id) || action.label.includes(material.id))
src/tools/video-editor/components/MaterialBrowser.tsx:72:    ?? materialActions[0];
src/tools/video-editor/components/MaterialBrowser.tsx:76:  material: RenderMaterialRef,
src/tools/video-editor/components/MaterialBrowser.tsx:80:    finding.materialRefId === material.id
src/tools/video-editor/components/MaterialBrowser.tsx:81:    || finding.message.includes(material.id)
src/tools/video-editor/components/MaterialBrowser.tsx:82:    || text(finding.detail).includes(material.id));
src/tools/video-editor/components/MaterialBrowser.tsx:86:  materials,
src/tools/video-editor/components/MaterialBrowser.tsx:87:  materialStatuses = [],
src/tools/video-editor/components/MaterialBrowser.tsx:92:  const [selectedId, setSelectedId] = useState(materials[0]?.id ?? '');
src/tools/video-editor/components/MaterialBrowser.tsx:94:  const rows = useMemo(() => materials
src/tools/video-editor/components/MaterialBrowser.tsx:95:    .map((material) => ({ material, status: statusFor(material, materialStatuses) }))
src/tools/video-editor/components/MaterialBrowser.tsx:96:    .filter(({ material, status }) => matches(material, status, filters)), [filters, materialStatuses, materials]);
src/tools/video-editor/components/MaterialBrowser.tsx:97:  const selected = rows.find((row) => row.material.id === selectedId) ?? rows[0];
src/tools/video-editor/components/MaterialBrowser.tsx:98:  const selectedAction = selected ? actionFor(selected.material, plannerResult?.nextActions ?? []) : undefined;
src/tools/video-editor/components/MaterialBrowser.tsx:113:        <p>No materials match the current filters.</p>
src/tools/video-editor/components/MaterialBrowser.tsx:117:            {rows.map(({ material, status }) => (
src/tools/video-editor/components/MaterialBrowser.tsx:118:              <li key={material.id}>
src/tools/video-editor/components/MaterialBrowser.tsx:119:                <button type="button" onClick={() => setSelectedId(material.id)}>
src/tools/video-editor/components/MaterialBrowser.tsx:120:                  {material.id} {material.mediaKind} {material.determinism} {status.state}
src/tools/video-editor/components/MaterialBrowser.tsx:127:              <h3>{selected.material.id}</h3>
src/tools/video-editor/components/MaterialBrowser.tsx:129:                <dt>Producer</dt><dd>{selected.material.producerExtensionId ?? 'unknown'}</dd>
src/tools/video-editor/components/MaterialBrowser.tsx:130:                <dt>Locator</dt><dd>{selected.material.locator.kind}: {selected.material.locator.uri}</dd>
src/tools/video-editor/components/MaterialBrowser.tsx:132:                <dt>Pass</dt><dd>{detailValue(selected.material, 'passName') || 'none'}</dd>
src/tools/video-editor/components/MaterialBrowser.tsx:133:                <dt>Group</dt><dd>{detailValue(selected.material, 'renderGroupId') || 'none'}</dd>
src/tools/video-editor/components/MaterialBrowser.tsx:134:                <dt>Provenance</dt><dd>{text((selected.material as unknown as Record<string, unknown>).provenance) || 'none'}</dd>
src/tools/video-editor/components/MaterialBrowser.tsx:136:              {relatedFindings(selected.material, findings).map((finding) => <p key={finding.id}>{finding.message}</p>)}
src/tools/video-editor/components/MaterialBrowser.tsx:137:              {selectedAction && <button type="button" onClick={() => onAction?.(selectedAction, selected.material)}>{selectedAction.label}</button>}
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.ts:12:import type { ContributionRenderability } from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.ts:21:  readonly renderability?: ContributionRenderability;
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.ts:130:    renderability: options.renderability ?? createDefaultEffectRenderability(),
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.ts:192:export function legacyDbEffectsToRegistryRecords(
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.ts:197:  const contributionIdPrefix = options.contributionIdPrefix ?? 'legacy-db:effect';
src/tools/video-editor/effects/registry/adapters/effectSourceAdapters.ts:205:      provenance: 'legacy-db-effect',
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.test.tsx:142:function materializeShotGroup(
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.test.tsx:222:      () => [materializeShotGroup(initialShotGroup, rows)],
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.test.tsx:473:describe('TimelineCanvas postprocess shader badge', () => {
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.test.tsx:476:    extensionId: 'ext.shader',
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.test.tsx:478:    shaderId: 'shader.post.grade',
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.test.tsx:482:  it('renders a stable postprocess shader badge and selects the shader target', () => {
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.test.tsx:489:    const badge = container.querySelector('[data-postprocess-shader-badge="true"]');
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.test.tsx:491:      throw new Error('expected postprocess shader badge');
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.test.tsx:494:    expect(badge).toHaveAttribute('data-shader-scope', 'postprocess');
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.test.tsx:495:    expect(badge).toHaveAttribute('data-shader-id', 'shader.post.grade');
src/tools/video-editor/components/MaterialBrowser.test.tsx:6:function material(id: string, overrides: Partial<RenderMaterialRef> & Record<string, unknown> = {}): RenderMaterialRef {
src/tools/video-editor/components/MaterialBrowser.test.tsx:11:    producerExtensionId: 'ext.materials',
src/tools/video-editor/components/MaterialBrowser.test.tsx:13:    replacementPolicy: 'materialize-on-export',
src/tools/video-editor/components/MaterialBrowser.test.tsx:22:        materials={[
src/tools/video-editor/components/MaterialBrowser.test.tsx:23:          material('mat-a', { passName: 'beauty', renderGroupId: 'hero', provenance: { source: 'camera-a' } }),
src/tools/video-editor/components/MaterialBrowser.test.tsx:24:          material('mat-b', {
src/tools/video-editor/components/MaterialBrowser.test.tsx:33:        materialStatuses={[
src/tools/video-editor/components/MaterialBrowser.test.tsx:34:          { materialRefId: 'mat-a', state: 'stale' },
src/tools/video-editor/components/MaterialBrowser.test.tsx:35:          { materialRefId: 'mat-b', state: 'resolved' },
src/tools/video-editor/components/MaterialBrowser.test.tsx:40:    fireEvent.change(screen.getByLabelText('Producer filter'), { target: { value: 'ext.materials' } });
src/tools/video-editor/components/MaterialBrowser.test.tsx:53:  it('renders empty states, material detail, findings, and dispatches planner next actions', () => {
src/tools/video-editor/components/MaterialBrowser.test.tsx:56:    const { rerender } = render(<MaterialBrowser materials={[]} />);
src/tools/video-editor/components/MaterialBrowser.test.tsx:57:    expect(screen.getByText('No materials match the current filters.')).toBeInTheDocument();
src/tools/video-editor/components/MaterialBrowser.test.tsx:61:        materials={[material('mat-a', { provenance: { process: 'bake' } })]}
src/tools/video-editor/components/MaterialBrowser.test.tsx:62:        materialStatuses={[{ materialRefId: 'mat-a', state: 'missing', message: 'Missing bytes' }]}
src/tools/video-editor/components/MaterialBrowser.test.tsx:69:            reason: 'missing-material',
src/tools/video-editor/components/MaterialBrowser.test.tsx:70:            materialRefId: 'mat-a',
src/tools/video-editor/adapters/reigh/useReighTimelinesList.test.ts:85:  it('reads materialized timelines rows including config via select(*)', async () => {
src/tools/video-editor/adapters/reigh/useReighTimelinesList.test.ts:114:    // The returned data must preserve the materialized config field.
src/tools/video-editor/effects/registry/types.ts:4:import type { ContributionRenderability } from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/effects/registry/types.ts:12:  | 'legacy-db-effect'
src/tools/video-editor/effects/registry/types.ts:27:  readonly renderability: ContributionRenderability;
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:99:      renderability: {
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:144:/** Create an extension with an inactive/reserved contribution (outputFormat kind). */
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:158:          kind: 'outputFormat',
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:186:          kind: 'outputFormat',
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:277:    expect(inventory!.extensions[0].contributions[0].kind).toBe('outputFormat');
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:305:    const output = contribs.find((c) => c.kind === 'outputFormat');
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:949:  it('shows provider effect registry counts, renderability summaries, and planner/export blockers', async () => {
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:992:    expect(document.querySelector('[data-video-editor-effect-renderability-summary="supported"]')?.textContent).toContain('1');
src/tools/video-editor/runtime/ExtensionStatusDrawer.test.tsx:993:    expect(document.querySelector('[data-video-editor-effect-renderability-summary="blocked"]')?.textContent).toContain('1');
src/tools/video-editor/effects/registry/EffectRegistryContext.test.tsx:24:    renderability: {
src/tools/video-editor/components/RoundtripResultsPanel.test.tsx:8:const material: RenderMaterial = {
src/tools/video-editor/components/RoundtripResultsPanel.test.tsx:23:    returnedMaterials: [material],
src/tools/video-editor/components/RoundtripResultsPanel.test.tsx:39:  it('lists returned materials, sidecars, diagnostics, logs, metadata, and downloads sidecars', () => {
src/tools/video-editor/components/RoundtripResultsPanel.test.tsx:50:    expect(screen.getByLabelText('Returned materials')).toHaveTextContent('mat-returned image https://example.test/returned.png');
src/tools/video-editor/components/RoundtripResultsPanel.test.tsx:99:            payload: { material: expect.objectContaining({ id: 'mat-returned' }) },
src/tools/video-editor/effects/registry/EffectRegistry.ts:58:  renderability: EffectRegistryRecord['renderability'],
src/tools/video-editor/effects/registry/EffectRegistry.ts:59:): EffectRegistryRecord['renderability'] {
src/tools/video-editor/effects/registry/EffectRegistry.ts:61:    ...renderability,
src/tools/video-editor/effects/registry/EffectRegistry.ts:63:      renderability.capabilities.map((capability) => Object.freeze({ ...capability })),
src/tools/video-editor/effects/registry/EffectRegistry.ts:65:    ...(renderability.blockers
src/tools/video-editor/effects/registry/EffectRegistry.ts:68:            renderability.blockers.map((blocker) => Object.freeze({ ...blocker })),
src/tools/video-editor/effects/registry/EffectRegistry.ts:78:    renderability: freezeRenderability(record.renderability),
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.tsx:451:  const handlePostprocessShaderSelect = useCallback((shader: TimelinePostprocessShaderMetadata) => {
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.tsx:455:      kind: 'shader' as const,
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.tsx:456:      shaderScope: 'postprocess' as const,
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.tsx:457:      shaderId: shader.shaderId,
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.tsx:458:      extensionId: shader.extensionId,
src/tools/video-editor/components/TimelineEditor/TimelineEditorCore.tsx:459:      contributionId: shader.contributionId,
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:19:    renderability: {
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:55:    expect(Object.isFrozen(snapshotA.records[0].renderability)).toBe(true);
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:56:    expect(Object.isFrozen(snapshotA.records[0].renderability.capabilities)).toBe(true);
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:221:  it('keeps record diagnostics and renderability metadata available in snapshots', () => {
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:229:      renderability: {
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:254:    expect(entry?.renderability.capabilities[0].route).toBe('browser-export');
src/tools/video-editor/effects/registry/EffectRegistry.test.ts:255:    expect(entry?.renderability.blockers?.[0].reason).toBe('preview-only');
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:154:describe('shader uniform controls', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:155:  function shaderUniform(overrides: ShaderUniformSchema[number]): ShaderUniformSchema[number] {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:162:      schema: [shaderUniform({
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:185:      schema: [shaderUniform({ name: 'u_count', label: 'Count', type: 'int', default: 2 })],
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:198:      schema: [shaderUniform({ name: 'u_enabled', label: 'Enabled', type: 'bool', default: false })],
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:212:      schema: [shaderUniform({ name: 'u_offset', label: 'Offset', type: 'vec2', default: [0, 1] })],
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:224:      schema: [shaderUniform({ name: 'u_axis', label: 'Axis', type: 'vec3', default: [0, 1, 0] })],
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:236:      schema: [shaderUniform({ name: 'u_bounds', label: 'Bounds', type: 'vec4', default: [0, 0, 1, 1] })],
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:248:      schema: [shaderUniform({ name: 'u_tint', label: 'Tint', type: 'color', default: [1, 0, 0, 1] })],
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:260:      schema: [shaderUniform({
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:281:      schema: [shaderUniform({
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:301:      schema: [shaderUniform({ name: 'u_frame', label: 'Frame', type: 'frame', default: 12 })],
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:313:      schema: [shaderUniform({ name: 'u_time', label: 'Time', type: 'time', default: 1.5 })],
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:1818:  it('shader-number input has aria-labelledby and aria-describedby', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:1820:      schema: [shaderUniform({ name: 'u_gain', label: 'Gain', description: 'Gain control', type: 'float', default: 0.5 })],
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:1828:  it('shader-number input has id attribute', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:1830:      schema: [shaderUniform({ name: 'u_gain', label: 'Gain', type: 'float', default: 0.5 })],
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:1841:      schema: [shaderUniform({ name: 'u_offset', label: 'Offset', description: 'Position offset', type: 'vec2', default: [0, 1] })],
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:1852:      schema: [shaderUniform({ name: 'u_offset', label: 'Offset', type: 'vec2', default: [0, 1] })],
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:2028:  // -- Focuses first invalid field (shader-number) ---------------------------
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:2030:  it('focuses the first invalid shader-number input', () => {
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:2204:// Shader uniform helper (re-used from shader test block)
src/tools/video-editor/components/SchemaForm/SchemaForm.test.tsx:2205:function shaderUniform(overrides: ShaderUniformSchema[number]): ShaderUniformSchema[number] {
src/tools/video-editor/components/CopilotPrompt/CopilotPrompt.test.tsx:282:      resultFamilies: ['material/artifact'] as any,
src/tools/video-editor/effects/useAudioReactive.test.ts:18:import { AudioAnalysisContext, SILENT_AUDIO_DATA, type AudioAnalysisData } from '@/tools/video-editor/compositions/AudioAnalysisProvider';
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:134:  _source: 'parameter' | 'standardschema' | 'shader';
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:291:    message: '"oneOf" composition is not yet supported in SchemaForm. Provide a flat, concrete schema.',
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:295:    message: '"anyOf" composition is not yet supported in SchemaForm. Provide a flat, concrete schema.',
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:299:    message: '"allOf" composition is not yet supported in SchemaForm. Provide a flat, concrete schema.',
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:410:        _source: isShader ? 'shader' as const : 'parameter' as const,
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:784:            {/* Compact shader scalar widget */}
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:785:            {field._capability.widgetType === 'shader-number' && (
src/tools/video-editor/components/SchemaForm/SchemaForm.tsx:853:            {/* Compact shader vector widget */}
src/tools/video-editor/lib/timeline-mutation-engine.ts:85:export const materializeTimelineRows = (
src/tools/video-editor/lib/timeline-mutation-engine.ts:181:      const baseNextData = materializeTimelineRows(
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:7:import type { ShaderEffectRegistryRecord, ShaderEffectRegistrySnapshot } from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:17:vi.mock('@/tools/video-editor/shaders/registry/index.ts', async () => {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:18:  const actual = await vi.importActual<typeof import('@/tools/video-editor/shaders/registry/index.ts')>(
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:19:    '@/tools/video-editor/shaders/registry/index.ts',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:74:vi.mock('@banodoco/timeline-composition/registry.generated', () => ({
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:107:function renderability({
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:113:} = {}): ShaderEffectRegistryRecord['renderability'] {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:137:function shaderRecord(overrides: Partial<ShaderEffectRegistryRecord> = {}): ShaderEffectRegistryRecord {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:139:    shaderId: 'shader.clip.bloom',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:140:    ownerExtensionId: 'ext.shader',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:152:    renderability: renderability(),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:158:function shaderSnapshot(records: readonly ShaderEffectRegistryRecord[]): ShaderEffectRegistrySnapshot {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:162:    get: (shaderId, ownerExtensionId) => records.find((record) => (
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:163:      record.shaderId === shaderId && record.ownerExtensionId === ownerExtensionId
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:166:      record.shaderId === lookup.shaderId && record.ownerExtensionId === lookup.ownerExtensionId
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:168:    has: (shaderId, ownerExtensionId) => records.some((record) => (
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:169:      record.shaderId === shaderId && record.ownerExtensionId === ownerExtensionId
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:172:      record.shaderId === lookup.shaderId && record.ownerExtensionId === lookup.ownerExtensionId
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:195:    compositionWidth: 1920,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:196:    compositionHeight: 1080,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:205:  return screen.getByTestId('clip-panel-shader-section');
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:208:describe('ClipPanel shader picker', () => {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:220:      snapshot: shaderSnapshot([]),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:224:  it('shows valid clip shader entries with Shader and pass badges and hides postprocess records', () => {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:225:    const valid = shaderRecord();
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:226:    const postprocess = shaderRecord({
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:227:      shaderId: 'shader.post.grade',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:234:      snapshot: shaderSnapshot([valid, postprocess]),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:250:  it('keeps invalid shader entries visible but disabled', () => {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:252:    const invalid = shaderRecord({
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:253:      shaderId: 'shader.clip.broken',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:259:        code: 'shader/compile-error',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:260:        message: 'Fragment shader failed to compile.',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:265:      snapshot: shaderSnapshot([invalid]),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:281:  it('rejects selecting a second clip shader with an explicit diagnostic', () => {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:283:    const existing = shaderRecord();
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:284:    const next = shaderRecord({
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:285:      shaderId: 'shader.clip.edge',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:291:      snapshot: shaderSnapshot([existing, next]),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:298:          shader: {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:300:            extensionId: 'ext.shader',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:302:            shaderId: 'shader.clip.bloom',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:315:    expect(screen.getByTestId('clip-panel-shader-diagnostic')).toHaveTextContent(
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:316:      'Cannot add shader "shader.clip.edge" to clip "clip-1" because shader "shader.clip.bloom" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:320:  it('labels selected preview-only shader entries with a Preview only badge', () => {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:321:    const previewOnly = shaderRecord({
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:322:      renderability: renderability({ browserExport: 'blocked', workerExport: 'blocked' }),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:326:      snapshot: shaderSnapshot([previewOnly]),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:332:          shader: {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:334:            extensionId: 'ext.shader',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:336:            shaderId: 'shader.clip.bloom',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:346:  it('labels selected export-blocked shader entries with blocked route badges', () => {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:347:    const blocked = shaderRecord({
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:348:      renderability: renderability({ browserExport: 'blocked', workerExport: 'supported' }),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:352:      snapshot: shaderSnapshot([blocked]),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:358:          shader: {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:360:            extensionId: 'ext.shader',
src/tools/video-editor/components/PropertiesPanel/ClipPanel.shader.test.tsx:362:            shaderId: 'shader.clip.bloom',
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:118:let __exportExtensions: any = { slots: {}, dialogHost: { dialogs: [] }, registry: { panels: [], inspectorSections: [] }, outputFormats: [] };
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:125:    outputFormats: [],
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:131:  __exportExtensions = { slots: {}, dialogHost: { dialogs: [] }, registry: { panels: [], inspectorSections: [] }, outputFormats: [] };
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:476:  it('renders Export dropdown when compile-only output formats are registered', () => {
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:478:      outputFormats: [
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:490:      outputFormats: [
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:500:  it('does not render Export dropdown when no output formats are registered', () => {
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:501:    __setExportExtensions({ outputFormats: [] });
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:508:  it('does not render Export dropdown when extensions context has no outputFormats property', () => {
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:509:    // Default mock has no outputFormats property
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:519:      outputFormats: [
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:542:      outputFormats: [
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:562:      outputFormats: [
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:586:      outputFormats: [
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:603:      outputFormats: [
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:629:      outputFormats: [
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:641:      outputFormats: [
src/tools/video-editor/components/TimelineEditorShellCore.test.tsx:658:      outputFormats: [
src/tools/video-editor/lib/timeline-data.test.ts:131:  it('round-trips trusted generation provenance additively while preserving legacy no-generation clips', async () => {
src/tools/video-editor/lib/timeline-data.test.ts:146:          id: 'clip-legacy',
src/tools/video-editor/lib/timeline-data.test.ts:150:          asset: 'legacy-video',
src/tools/video-editor/lib/timeline-data.test.ts:158:        'legacy-video': { file: 'legacy-video.mp4', type: 'video/mp4' },
src/tools/video-editor/lib/timeline-data.test.ts:164:    expect(data.meta['clip-legacy'].generation).toBeUndefined();
src/tools/video-editor/lib/timeline-data.test.ts:176:    const legacyClip = roundTripped.clips.find((clip) => clip.id === 'clip-legacy');
src/tools/video-editor/lib/timeline-data.test.ts:179:    expect(legacyClip).not.toHaveProperty('generation');
src/tools/video-editor/lib/timeline-data.test.ts:186:    expect(serialized.clips.find((clip) => clip.id === 'clip-legacy')).not.toHaveProperty('generation');
src/tools/video-editor/lib/timeline-data.test.ts:279:        throw new Error('legacy resolveAssetUrl should not be called');
src/tools/video-editor/lib/timeline-data.test.ts:283:      resolveAssetUrl: vi.fn(async (file: string) => `legacy:${file}`),
src/tools/video-editor/lib/timeline-data.test.ts:319:        throw new Error('legacy resolveAssetUrl should not be called');
src/tools/video-editor/lib/timeline-data.test.ts:359:  it('falls back to legacy loadAssetProfile when no profile hook is installed', async () => {
src/tools/video-editor/lib/timeline-data.test.ts:364:          segments: [{ start: 1, end: 2, text: `legacy:${assetId}` }],
src/tools/video-editor/lib/timeline-data.test.ts:369:    await expect(loadTranscript(assetResolver, 'asset-2', 'timeline-legacy')).resolves.toEqual([
src/tools/video-editor/lib/timeline-data.test.ts:370:      { start: 1, end: 2, text: 'legacy:asset-2' },
src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx:70:vi.mock('@banodoco/timeline-composition/registry.generated', () => ({
src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx:184:      compositionWidth={1920}
src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx:185:      compositionHeight={1080}
src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx:449:      renderability: makeRenderability({ preview: true, browserExport: false, workerExport: false }),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx:477:      renderability: makeRenderability({ preview: true, browserExport: true, workerExport: false }),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx:530:      renderability: makeRenderability({ preview: true, browserExport: false, workerExport: false }),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.sequence.test.tsx:554:      renderability: makeRenderability({ preview: true, browserExport: false, workerExport: true }),
src/tools/video-editor/runtime/renderPlanner.test.ts:2:import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
src/tools/video-editor/runtime/renderPlanner.test.ts:85:    shaders: [
src/tools/video-editor/runtime/renderPlanner.test.ts:87:        id: 'clip-1:shader:shader.preview.clip',
src/tools/video-editor/runtime/renderPlanner.test.ts:88:        shaderId: 'shader.preview.clip',
src/tools/video-editor/runtime/renderPlanner.test.ts:91:        extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:92:        contributionId: 'ext.shader.clip',
src/tools/video-editor/runtime/renderPlanner.test.ts:96:        id: 'postprocess:shader:shader.preview.post',
src/tools/video-editor/runtime/renderPlanner.test.ts:97:        shaderId: 'shader.preview.post',
src/tools/video-editor/runtime/renderPlanner.test.ts:99:        extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:100:        contributionId: 'ext.shader.post',
src/tools/video-editor/runtime/renderPlanner.test.ts:230:function shaderMaterializerDescriptor(): VideoEditorShaderDescriptor {
src/tools/video-editor/runtime/renderPlanner.test.ts:232:    id: 'ext.shader.clip',
src/tools/video-editor/runtime/renderPlanner.test.ts:233:    extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:234:    shaderId: 'shader.preview.clip',
src/tools/video-editor/runtime/renderPlanner.test.ts:235:    label: 'Preview clip shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:237:    materializer: {
src/tools/video-editor/runtime/renderPlanner.test.ts:238:      processId: 'shader-materializer',
src/tools/video-editor/runtime/renderPlanner.test.ts:239:      operationId: 'materializeClipShader',
src/tools/video-editor/runtime/renderPlanner.test.ts:240:      requiredCapabilities: ['render-material', 'shader-materializer'],
src/tools/video-editor/runtime/renderPlanner.test.ts:246:function shaderMaterializerProcess(): VideoEditorProcessDescriptor {
src/tools/video-editor/runtime/renderPlanner.test.ts:248:    id: 'shader-materializer-process',
src/tools/video-editor/runtime/renderPlanner.test.ts:249:    extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:250:    processId: 'shader-materializer',
src/tools/video-editor/runtime/renderPlanner.test.ts:251:    label: 'Shader materializer',
src/tools/video-editor/runtime/renderPlanner.test.ts:253:      id: 'shader-materializer',
src/tools/video-editor/runtime/renderPlanner.test.ts:254:      label: 'Shader materializer',
src/tools/video-editor/runtime/renderPlanner.test.ts:258:        args: ['shader-materializer.js'],
src/tools/video-editor/runtime/renderPlanner.test.ts:262:          id: 'materializeClipShader',
src/tools/video-editor/runtime/renderPlanner.test.ts:263:          label: 'Materialize clip shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:265:          outputKinds: ['material'],
src/tools/video-editor/runtime/renderPlanner.test.ts:272:        id: 'materializeClipShader',
src/tools/video-editor/runtime/renderPlanner.test.ts:273:        label: 'Materialize clip shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:275:        outputKinds: ['material'],
src/tools/video-editor/runtime/renderPlanner.test.ts:280:      { source: 'extension', extensionId: 'ext.shader', contributionId: 'ext.shader.clip' },
src/tools/video-editor/runtime/renderPlanner.test.ts:287:function materialRef(
src/tools/video-editor/runtime/renderPlanner.test.ts:294:    locator: { kind: 'provider', uri: `provider://materials/${id}` },
src/tools/video-editor/runtime/renderPlanner.test.ts:296:    replacementPolicy: 'materialize-on-export',
src/tools/video-editor/runtime/renderPlanner.test.ts:297:    producerExtensionId: 'ext.materials',
src/tools/video-editor/runtime/renderPlanner.test.ts:380:          id: 'shader-transition-worker-downgrade',
src/tools/video-editor/runtime/renderPlanner.test.ts:384:            extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:385:            contributionId: 'transition.shader-wipe',
src/tools/video-editor/runtime/renderPlanner.test.ts:387:          requiredCapabilities: ['worker-export', 'shader-fallback'],
src/tools/video-editor/runtime/renderPlanner.test.ts:393:            message: 'Worker export will use a deterministic shader fallback.',
src/tools/video-editor/runtime/renderPlanner.test.ts:403:        id: 'shader-transition-worker-downgrade.worker-export.process-dependent',
src/tools/video-editor/runtime/renderPlanner.test.ts:407:        message: 'Worker export will use a deterministic shader fallback.',
src/tools/video-editor/runtime/renderPlanner.test.ts:408:        extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:409:        contributionId: 'transition.shader-wipe',
src/tools/video-editor/runtime/renderPlanner.test.ts:414:            extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:415:            contributionId: 'transition.shader-wipe',
src/tools/video-editor/runtime/renderPlanner.test.ts:417:          requiredCapabilities: ['shader-fallback', 'worker-export'],
src/tools/video-editor/runtime/renderPlanner.test.ts:423:            message: 'Worker export will use a deterministic shader fallback.',
src/tools/video-editor/runtime/renderPlanner.test.ts:433:      requiredCapabilities: ['shader-fallback', 'worker-export'],
src/tools/video-editor/runtime/renderPlanner.test.ts:437:  it('blocks worker export for browser-only shader transitions with complete route metadata', () => {
src/tools/video-editor/runtime/renderPlanner.test.ts:441:          id: 'shader-transition-browser-route',
src/tools/video-editor/runtime/renderPlanner.test.ts:445:            extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:446:            contributionId: 'transition.shader-wipe',
src/tools/video-editor/runtime/renderPlanner.test.ts:448:          requiredCapabilities: ['browser-export', 'webgl-shader'],
src/tools/video-editor/runtime/renderPlanner.test.ts:456:          id: 'shader-transition-worker-route',
src/tools/video-editor/runtime/renderPlanner.test.ts:460:            extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:461:            contributionId: 'transition.shader-wipe',
src/tools/video-editor/runtime/renderPlanner.test.ts:463:          requiredCapabilities: ['worker-export', 'webgl-shader'],
src/tools/video-editor/runtime/renderPlanner.test.ts:470:            message: 'Shader transition "shader-wipe" requires browser WebGL APIs unavailable in worker export.',
src/tools/video-editor/runtime/renderPlanner.test.ts:480:      requiredCapabilities: ['browser-export', 'webgl-shader'],
src/tools/video-editor/runtime/renderPlanner.test.ts:487:      requiredCapabilities: ['webgl-shader', 'worker-export'],
src/tools/video-editor/runtime/renderPlanner.test.ts:490:          id: 'shader-transition-worker-route.worker-export.process-dependent',
src/tools/video-editor/runtime/renderPlanner.test.ts:494:          message: 'Shader transition "shader-wipe" requires browser WebGL APIs unavailable in worker export.',
src/tools/video-editor/runtime/renderPlanner.test.ts:495:          extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:496:          contributionId: 'transition.shader-wipe',
src/tools/video-editor/runtime/renderPlanner.test.ts:501:              extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:502:              contributionId: 'transition.shader-wipe',
src/tools/video-editor/runtime/renderPlanner.test.ts:504:            requiredCapabilities: ['webgl-shader', 'worker-export'],
src/tools/video-editor/runtime/renderPlanner.test.ts:510:              message: 'Shader transition "shader-wipe" requires browser WebGL APIs unavailable in worker export.',
src/tools/video-editor/runtime/renderPlanner.test.ts:518:  it('blocks export for timeline shader metadata until a materializer produces RenderMaterial', () => {
src/tools/video-editor/runtime/renderPlanner.test.ts:526:        reason: 'missing-material',
src/tools/video-editor/runtime/renderPlanner.test.ts:527:        message: 'Shader "shader.preview.clip" cannot export because no shader materializer produced RenderMaterial for clip "clip-1".',
src/tools/video-editor/runtime/renderPlanner.test.ts:528:        extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:529:        contributionId: 'ext.shader.clip',
src/tools/video-editor/runtime/renderPlanner.test.ts:533:        reason: 'missing-material',
src/tools/video-editor/runtime/renderPlanner.test.ts:534:        message: 'Shader "shader.preview.post" cannot export because no shader materializer produced RenderMaterial for timeline postprocess.',
src/tools/video-editor/runtime/renderPlanner.test.ts:535:        extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:536:        contributionId: 'ext.shader.post',
src/tools/video-editor/runtime/renderPlanner.test.ts:543:      .toEqual(expect.arrayContaining(['render-material', 'shader-materializer']));
src/tools/video-editor/runtime/renderPlanner.test.ts:546:  it('diagnoses duplicate clip and postprocess shaders instead of stacking planner requirements', () => {
src/tools/video-editor/runtime/renderPlanner.test.ts:551:        shaders: [
src/tools/video-editor/runtime/renderPlanner.test.ts:552:          ...(snapshot.shaders ?? []),
src/tools/video-editor/runtime/renderPlanner.test.ts:554:            id: 'clip-1:shader:shader.preview.clip.second',
src/tools/video-editor/runtime/renderPlanner.test.ts:555:            shaderId: 'shader.preview.clip.second',
src/tools/video-editor/runtime/renderPlanner.test.ts:558:            extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:559:            contributionId: 'ext.shader.clip.second',
src/tools/video-editor/runtime/renderPlanner.test.ts:563:            id: 'postprocess:shader:shader.preview.post.second',
src/tools/video-editor/runtime/renderPlanner.test.ts:564:            shaderId: 'shader.preview.post.second',
src/tools/video-editor/runtime/renderPlanner.test.ts:566:            extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:567:            contributionId: 'ext.shader.post.second',
src/tools/video-editor/runtime/renderPlanner.test.ts:579:        message: 'Cannot add shader "shader.preview.clip.second" to clip "clip-1" because shader "shader.preview.clip" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.',
src/tools/video-editor/runtime/renderPlanner.test.ts:580:        extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:581:        contributionId: 'ext.shader.clip.second',
src/tools/video-editor/runtime/renderPlanner.test.ts:586:        message: 'Cannot add postprocess shader "shader.preview.post.second" because postprocess shader "shader.preview.post" is already assigned. V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.',
src/tools/video-editor/runtime/renderPlanner.test.ts:587:        extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:588:        contributionId: 'ext.shader.post.second',
src/tools/video-editor/runtime/renderPlanner.test.ts:593:        message: 'Shader "shader.preview.clip.second" cannot export because no shader materializer produced RenderMaterial for clip "clip-1".',
src/tools/video-editor/runtime/renderPlanner.test.ts:596:        message: 'Shader "shader.preview.post.second" cannot export because no shader materializer produced RenderMaterial for timeline postprocess.',
src/tools/video-editor/runtime/renderPlanner.test.ts:601:  it('uses registered shader materializer process routes for materialization next actions', () => {
src/tools/video-editor/runtime/renderPlanner.test.ts:604:      shaders: [shaderMaterializerDescriptor()],
src/tools/video-editor/runtime/renderPlanner.test.ts:605:      processes: [shaderMaterializerProcess()],
src/tools/video-editor/runtime/renderPlanner.test.ts:608:          processId: 'shader-materializer',
src/tools/video-editor/runtime/renderPlanner.test.ts:610:          message: 'Materializing clip shader.',
src/tools/video-editor/runtime/renderPlanner.test.ts:618:        id: 'snapshot.shader.2.browser-export.process-dependent',
src/tools/video-editor/runtime/renderPlanner.test.ts:621:        message: 'Shader "shader.preview.clip" has a materializer route for browser-export; run process "shader-materializer" to produce RenderMaterial.',
src/tools/video-editor/runtime/renderPlanner.test.ts:622:        extensionId: 'ext.shader',
src/tools/video-editor/runtime/renderPlanner.test.ts:623:        contributionId: 'ext.shader.clip',
src/tools/video-editor/runtime/renderPlanner.test.ts:629:        reason: 'missing-material',
src/tools/video-editor/runtime/renderPlanner.test.ts:630:        message: 'Shader "shader.preview.clip" cannot export because no shader materializer produced RenderMaterial for clip "clip-1".',
src/tools/video-editor/runtime/renderPlanner.test.ts:635:        id: 'snapshot.shader.2.browser-export.shader-materializer.discovered',
src/tools/video-editor/runtime/renderPlanner.test.ts:639:          source: 'shader-materializer',
src/tools/video-editor/runtime/renderPlanner.test.ts:640:          shaderId: 'shader.preview.clip',
src/tools/video-editor/runtime/renderPlanner.test.ts:641:          processId: 'shader-materializer',
src/tools/video-editor/runtime/renderPlanner.test.ts:642:          operationId: 'materializeClipShader',
src/tools/video-editor/runtime/renderPlanner.test.ts:644:          materializationState: 'in-progress',
src/tools/video-editor/runtime/renderPlanner.test.ts:652:        label: 'Materialize shader shader.preview.clip',
src/tools/video-editor/runtime/renderPlanner.test.ts:653:        processId: 'shader-materializer',
src/tools/video-editor/runtime/renderPlanner.test.ts:654:        operationId: 'materializeClipShader',
src/tools/video-editor/runtime/renderPlanner.test.ts:662:          processId: 'shader-materializer',
src/tools/video-editor/runtime/renderPlanner.test.ts:663:          operationId: 'materializeClipShader',
src/tools/video-editor/runtime/renderPlanner.test.ts:670:  it('plans normalized render-dependent output formats as process-dependent route blockers', () => {
src/tools/video-editor/runtime/renderPlanner.test.ts:672:      outputFormats: [renderDependentOutput()],
src/tools/video-editor/runtime/renderPlanner.test.ts:674:      request: { outputFormatId: 'dataset.zip' },
src/tools/video-editor/runtime/renderPlanner.test.ts:685:      outputFormatIds: ['dataset.zip'],
src/tools/video-editor/runtime/renderPlanner.test.ts:700:        id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.exportDataset.process-dependent',
src/tools/video-editor/runtime/renderPlanner.test.ts:705:        id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.route-process-dependent',
src/tools/video-editor/runtime/renderPlanner.test.ts:712:  it('surfaces missing requested output formats as structured request blockers', () => {
src/tools/video-editor/runtime/renderPlanner.test.ts:714:      outputFormats: [renderDependentOutput()],
src/tools/video-editor/runtime/renderPlanner.test.ts:715:      request: { outputFormatId: 'missing.format', route: 'sidecar-export' },
src/tools/video-editor/runtime/renderPlanner.test.ts:725:        id: 'planner.outputFormat.missing.format.missing',
src/tools/video-editor/runtime/renderPlanner.test.ts:735:      outputFormats: [renderDependentOutput()],
src/tools/video-editor/runtime/renderPlanner.test.ts:737:        outputFormatId: 'dataset.zip',
src/tools/video-editor/runtime/renderPlanner.test.ts:748:          id: 'planner.outputFormat.ext.dataset.dataset.zip.browser-export.route-unsupported',
src/tools/video-editor/runtime/renderPlanner.test.ts:755:      outputFormatIds: ['dataset.zip'],
src/tools/video-editor/runtime/renderPlanner.test.ts:759:  it('converts materialize-on-export live material refs into browser-export blockers', () => {
src/tools/video-editor/runtime/renderPlanner.test.ts:760:    const materialRef: RenderMaterialRef = {
src/tools/video-editor/runtime/renderPlanner.test.ts:765:      replacementPolicy: 'materialize-on-export',
src/tools/video-editor/runtime/renderPlanner.test.ts:768:    const result = planRender({ materialRefs: [materialRef] });
src/tools/video-editor/runtime/renderPlanner.test.ts:773:        id: 'planner.material.mat-live-1.browser-export.live-unbaked',
src/tools/video-editor/runtime/renderPlanner.test.ts:776:        materialRefId: 'mat-live-1',
src/tools/video-editor/runtime/renderPlanner.test.ts:781:  it('materializes missing and stale material next actions while resolved material refs do not block', () => {
src/tools/video-editor/runtime/renderPlanner.test.ts:783:      materialRefs: [
src/tools/video-editor/runtime/renderPlanner.test.ts:784:        materialRef('mat-missing'),
src/tools/video-editor/runtime/renderPlanner.test.ts:785:        materialRef('mat-stale'),
src/tools/video-editor/runtime/renderPlanner.test.ts:786:        materialRef('mat-resolved'),
src/tools/video-editor/runtime/renderPlanner.test.ts:788:      materialStatuses: [
src/tools/video-editor/runtime/renderPlanner.test.ts:789:        { materialRefId: 'mat-missing', state: 'missing', message: 'Material bytes are unavailable.' },
src/tools/video-editor/runtime/renderPlanner.test.ts:790:        { materialRefId: 'mat-stale', state: 'stale', message: 'Material was produced from an older source hash.' },
src/tools/video-editor/runtime/renderPlanner.test.ts:791:        { materialRefId: 'mat-resolved', state: 'resolved' },
src/tools/video-editor/runtime/renderPlanner.test.ts:798:        id: 'planner.material.mat-missing.browser-export.missing-material',
src/tools/video-editor/runtime/renderPlanner.test.ts:799:        reason: 'missing-material',
src/tools/video-editor/runtime/renderPlanner.test.ts:800:        materialRefId: 'mat-missing',
src/tools/video-editor/runtime/renderPlanner.test.ts:803:        id: 'planner.material.mat-stale.browser-export.materialization-failed',
src/tools/video-editor/runtime/renderPlanner.test.ts:804:        reason: 'materialization-failed',
src/tools/video-editor/runtime/renderPlanner.test.ts:805:        materialRefId: 'mat-stale',
src/tools/video-editor/runtime/renderPlanner.test.ts:808:    expect(result.blockers.some((blocker) => blocker.materialRefId === 'mat-resolved')).toBe(false);
src/tools/video-editor/runtime/renderPlanner.test.ts:837:      outputFormats: [renderDependentOutput()],
src/tools/video-editor/runtime/renderPlanner.test.ts:840:      request: { outputFormatId: 'dataset.zip' },
src/tools/video-editor/runtime/renderPlanner.test.ts:843:      outputFormats: [renderDependentOutput()],
src/tools/video-editor/runtime/renderPlanner.test.ts:846:      request: { outputFormatId: 'dataset.zip' },
src/tools/video-editor/runtime/renderPlanner.test.ts:869:        id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.exportDataset.process-dependent.degraded',
src/tools/video-editor/runtime/renderPlanner.test.ts:876:        id: 'planner.outputFormat.ext.dataset.dataset.zip.sidecar-export.dataset-process.route-process-dependent.degraded',
src/tools/video-editor/runtime/renderPlanner.test.ts:908:                materialRefId: 'mat-beauty',
src/tools/video-editor/runtime/renderPlanner.test.ts:916:                materialRefId: 'mat-depth',
src/tools/video-editor/runtime/renderPlanner.test.ts:924:                materialRefId: 'mat-normal',
src/tools/video-editor/runtime/renderPlanner.test.ts:943:        id: 'planner.renderGroup.hero-shot.depth-pass.browser-export.missing-material',
src/tools/video-editor/runtime/renderPlanner.test.ts:944:        reason: 'missing-material',
src/tools/video-editor/runtime/renderPlanner.test.ts:945:        materialRefId: 'mat-depth',
src/tools/video-editor/runtime/renderPlanner.test.ts:948:        id: 'planner.renderGroup.hero-shot.normal-pass.browser-export.materialization-failed',
src/tools/video-editor/runtime/renderPlanner.test.ts:949:        reason: 'materialization-failed',
src/tools/video-editor/runtime/renderPlanner.test.ts:950:        materialRefId: 'mat-normal',
src/tools/video-editor/runtime/renderPlanner.test.ts:953:    expect(result.blockers.some((blocker) => blocker.materialRefId === 'mat-beauty')).toBe(false);
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:27:vi.mock('@/tools/video-editor/shaders/registry/ShaderEffectRegistryContext.tsx', () => ({
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:139:    compositionSize: { width: 1280, height: 720 },
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:153:    ownerExtensionId: 'ext.shader',
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:155:    shaderId: 'shader.post.grade',
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:175:    get: (shaderId: string, ownerExtensionId?: string) => (
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:176:      shaderId === record.shaderId && ownerExtensionId === record.ownerExtensionId ? record : undefined
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:178:    getByLookup: (lookup: { shaderId: string; ownerExtensionId?: string }) => (
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:179:      lookup.shaderId === record.shaderId && lookup.ownerExtensionId === record.ownerExtensionId ? record : undefined
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:181:    has: (shaderId: string, ownerExtensionId?: string) => shaderId === record.shaderId && ownerExtensionId === record.ownerExtensionId,
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:182:    hasByLookup: (lookup: { shaderId: string; ownerExtensionId?: string }) => lookup.shaderId === record.shaderId && lookup.ownerExtensionId === record.ownerExtensionId,
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:431:  it('opens postprocess shader controls for the shader inspector target', () => {
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:437:          shaderPostprocess: {
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:439:            extensionId: 'ext.shader',
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:441:            shaderId: 'shader.post.grade',
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:450:        kind: 'shader',
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:451:        shaderScope: 'postprocess',
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:452:        shaderId: 'shader.post.grade',
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:453:        extensionId: 'ext.shader',
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:460:    expect(screen.getByTestId('shader-inspector')).toBeInTheDocument();
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:469:        kind: 'shader',
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:470:        shaderScope: 'postprocess',
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.test.tsx:471:        shaderId: 'shader.post.grade',
src/tools/video-editor/runtime/extensionLockMetadata.test.ts:113:        { id: 'shader.blur' as any, kind: 'shader' as any },
src/tools/video-editor/runtime/extensionLockMetadata.test.ts:125:      'shader.blur',
src/tools/video-editor/runtime/extensionLockMetadata.test.ts:702:    const kinds = ['command', 'effect', 'transition', 'shader', 'clipType', 'agentTool', 'panel', 'dialog', 'slot', 'parser', 'outputFormat'];
src/tools/video-editor/effects/DynamicEffectRegistry.test.tsx:261:      <div data-testid="legacy-bridge-effect">{children}</div>
src/tools/video-editor/effects/DynamicEffectRegistry.test.tsx:267:      'legacy-bridge': LegacyBridgeEffect,
src/tools/video-editor/effects/DynamicEffectRegistry.test.tsx:272:    expect(getEffectRegistry().get('custom:legacy-bridge')).toBe(LegacyBridgeEffect);
src/tools/video-editor/effects/DynamicEffectRegistry.test.tsx:353:  it('loads effects into the provider registry without mutating the legacy singleton', async () => {
src/tools/video-editor/effects/DynamicEffectRegistry.test.tsx:606:  it('wrapWithClipEffects prefers provider record component and schema over legacy singleton for same effect ID', () => {
src/tools/video-editor/effects/DynamicEffectRegistry.test.tsx:608:      <div data-testid="legacy-override-component">{children}</div>
src/tools/video-editor/effects/DynamicEffectRegistry.test.tsx:616:    const legacySchema: ParameterSchema = [
src/tools/video-editor/effects/DynamicEffectRegistry.test.tsx:620:    // Seed the legacy singleton with one component and schema
src/tools/video-editor/effects/DynamicEffectRegistry.test.tsx:622:    getEffectRegistry().register('override-effect', 'export default function Effect(){}', legacySchema);
src/tools/video-editor/effects/DynamicEffectRegistry.test.tsx:633:      renderability: {
src/tools/video-editor/effects/DynamicEffectRegistry.test.tsx:669:    // Provider component renders, not legacy
src/tools/video-editor/effects/DynamicEffectRegistry.test.tsx:671:    expect(screen.queryByTestId('legacy-override-component')).not.toBeInTheDocument();
src/tools/video-editor/effects/DynamicEffectRegistry.test.tsx:672:    // Provider schema default (42) used, not legacy default (1)
src/tools/video-editor/effects/index.tsx:132: * 2. `snapshot.get(type)` — fallback for legacy `custom:` keys
src/tools/video-editor/effects/index.tsx:137: * render-time parameter coercion for already-applied legacy data.
src/tools/video-editor/effects/index.tsx:184:  const legacyRegistry = effectRegistrySnapshot ? null : getEffectRegistry();
src/tools/video-editor/effects/index.tsx:192:      ?? (legacyRegistry ? lookupEffect(continuousEffects, continuousEffect.type) : null)
src/tools/video-editor/effects/index.tsx:204:      schema: continuousRecord?.schema ?? legacyRegistry?.getSchema(continuousEffect!.type),
src/tools/video-editor/effects/index.tsx:214:      ?? (legacyRegistry ? lookupEffect(entranceEffects, entranceEffect.type) : null)
src/tools/video-editor/effects/index.tsx:223:      schema: entranceRecord?.schema ?? legacyRegistry?.getSchema(entranceEffect!.type),
src/tools/video-editor/effects/index.tsx:233:      ?? (legacyRegistry ? lookupEffect(exitEffects, exitEffect.type) : null)
src/tools/video-editor/effects/index.tsx:242:      schema: exitRecord?.schema ?? legacyRegistry?.getSchema(exitEffect!.type),
src/tools/video-editor/runtime/agentToolContracts.ts:34:  'material/artifact',
src/tools/video-editor/runtime/agentToolContracts.ts:635:    case 'material/artifact': {
src/tools/video-editor/runtime/agentToolContracts.ts:640:            'material-missing-refs',
src/tools/video-editor/runtime/agentToolContracts.ts:648:            'material-empty-refs',
src/sdk/extensionSettingsMigration.test.ts:5: *  - Schema version detection from manifest (settingsSchema.version + legacy settingsSchemaVersion)
src/sdk/extensionSettingsMigration.test.ts:118:  it('returns version from legacy settingsSchemaVersion', () => {
src/sdk/extensionSettingsMigration.test.ts:128:  it('prefers settingsSchema.version over legacy field', () => {
src/sdk/extensionSettingsMigration.test.ts:216:  it('handles legacy plain-object migration entries', () => {
src/sdk/extensionSettingsMigration.test.ts:219:        { kind: 'settings', fromVersion: '1.0.0', toVersion: '2.0.0', handler: 'legacy' },
src/sdk/extensionSettingsMigration.test.ts:224:    expect(result[0].handler).toBe('legacy');
src/sdk/extensionSettingsMigration.test.ts:352:    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark', oldSetting: 'legacy' });
src/sdk/extensionSettingsMigration.test.ts:745:  it('legacy settingsSchemaVersion mismatch triggers migration', async () => {
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.tsx:145:  /** Active timeline-scoped postprocess shader shown as a selectable timeline badge. */
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.tsx:147:  /** Selects the timeline-scoped postprocess shader inspector target. */
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.tsx:148:  onSelectPostprocessShader?: (shader: TimelinePostprocessShaderMetadata) => void;
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.tsx:638:          data-postprocess-shader-badge="true"
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.tsx:639:          data-shader-scope="postprocess"
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.tsx:640:          data-shader-id={postprocessShader.shaderId}
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.tsx:642:          aria-label={`Open postprocess shader controls for ${postprocessShader.label ?? postprocessShader.shaderId}`}
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.tsx:643:          title={`Postprocess shader: ${postprocessShader.label ?? postprocessShader.shaderId}`}
src/tools/video-editor/components/TimelineEditor/TimelineCanvas.tsx:648:          <span className="truncate text-foreground/90">{postprocessShader.label ?? postprocessShader.shaderId}</span>
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:57:      outputFormats: [],
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:64:      shaders: [],
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:73:    outputFormats: [],
src/tools/video-editor/components/ExtensionManager/ExtensionManager.test.tsx:80:    shaders: [],
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:48:  materializeTransitionDefaults,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:59:} from '@/tools/video-editor/shaders/registry/index.ts';
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:65:} from '@/tools/video-editor/lib/shader-catalog.ts';
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:91:  compositionWidth: number;
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:92:  compositionHeight: number;
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:171:  shader,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:174:  shader: TimelineClipShaderMetadata | undefined;
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:177:  if (!shader) {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:181:  const label = record?.label ?? shader.label ?? shader.shaderId;
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:190:    record.shaderId,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:194:function getMissingShaderPickerValue(shader: TimelineClipShaderMetadata): string {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:195:  return `missing|${encodeURIComponent(shader.extensionId)}|${encodeURIComponent(shader.contributionId)}|${encodeURIComponent(shader.shaderId)}`;
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:200:  delete nextApp.shader;
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:239:  if (!effect.renderability?.capabilities) return [];
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:240:  return effect.renderability.capabilities
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:247:  if (!effect.renderability?.capabilities) return false;
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:248:  const hasBrowserExport = effect.renderability.capabilities.some(
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:251:  const hasWorkerExport = effect.renderability.capabilities.some(
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:254:  const hasPreview = effect.renderability.capabilities.some(
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:309:  if (!record.renderability?.capabilities) return [];
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:310:  return record.renderability.capabilities
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:317:  if (!record.renderability?.capabilities) return false;
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:318:  const hasBrowserExport = record.renderability.capabilities.some(
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:321:  const hasWorkerExport = record.renderability.capabilities.some(
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:324:  const hasPreview = record.renderability.capabilities.some(
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:336:  const defaults = materializeTransitionDefaults(record.schema);
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:353:    ...materializeTransitionDefaults(record?.schema),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:385:  compositionWidth,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:386:  compositionHeight,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:456:  // M13: Clip-local shader picker. Postprocess shaders are timeline-scoped and
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:457:  // intentionally excluded from ClipPanel until a render graph exists.
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:458:  const [shaderDiagnostic, setShaderDiagnostic] = useState<string | null>(null);
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:459:  const shaderRegistryContext = useOptionalShaderEffectRegistryContext();
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:460:  const shaderPickerEntries = useMemo(
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:461:    () => listClipShaderPickerEntries(shaderRegistryContext?.snapshot),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:462:    [shaderRegistryContext?.snapshot],
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:464:  const clipShader = clip?.app?.shader;
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:467:    return shaderRegistryContext?.snapshot.get(clipShader.shaderId, clipShader.extensionId);
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:468:  }, [clipShader, shaderRegistryContext?.snapshot]);
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1114:              <div className="space-y-2 md:col-span-2" data-testid="clip-panel-shader-section">
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1125:                    const entry = shaderPickerEntries.find((candidate) => (
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1136:                        clipShader.shaderId,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1137:                        nextShader.shaderId,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1147:                        shader: nextShader,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1153:                    <ShaderSelectValue shader={clipShader} record={resolvedClipShaderRecord} />
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1157:                    {shaderPickerEntries.length > 0 && (
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1160:                        {shaderPickerEntries.map((entry) => {
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1166:                              key={`${record.ownerExtensionId ?? ''}:${record.contributionId}:${record.shaderId}`}
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1176:                                  clipShader.shaderId,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1177:                                  nextShader.shaderId,
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1214:                            {clipShader.label ?? clipShader.shaderId} (missing)
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1222:                {shaderDiagnostic && (
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1225:                    data-testid="clip-panel-shader-diagnostic"
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1229:                    <span>{shaderDiagnostic}</span>
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1234:                  const entry = shaderPickerEntries.find((candidate) => (
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1257:                    <span>Shader "{clipShader.shaderId}" is not available. The extension may have been removed.</span>
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1287:                      ? materializeTransitionDefaults(record.schema)
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1436:                              params: materializeTransitionDefaults(resolvedTransitionRecord.schema),
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1581:                <NumberInput value={clip.width ?? compositionWidth} min={0} max={compositionWidth} onChange={(value) => { if (value !== null) onChange({ width: value }); }} />
src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx:1585:                <NumberInput value={clip.height ?? compositionHeight} min={0} max={compositionHeight} onChange={(value) => { if (value !== null) onChange({ height: value }); }} />
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:30:  materializeTransitionDefaults,
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:43:  compositionWidth: number;
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:44:  compositionHeight: number;
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:128:/** Returns blocked export routes for an effect's renderability. */
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:129:function getBlockedRoutes(effect: { renderability?: { capabilities?: Array<{ route: string; status: string }> } }): string[] {
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:130:  if (!effect.renderability?.capabilities) return [];
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:131:  return effect.renderability.capabilities
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:173:  if (!record.renderability?.capabilities) return [];
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:174:  return record.renderability.capabilities
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:183:    compositionWidth,
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:184:    compositionHeight,
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:231:    props.compositionHeight,
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:232:    props.compositionWidth,
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:281:        onChange({ width: Math.min(compositionWidth, Math.max(0, value)) });
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:284:        onChange({ height: Math.min(compositionHeight, Math.max(0, value)) });
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:550:                      ? materializeTransitionDefaults(record.schema)
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:680:                              params: materializeTransitionDefaults(resolvedTransitionRecord.schema),
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:713:              {renderNumberInput('width', 'Width', { min: 0, max: compositionWidth })}
src/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx:714:              {renderNumberInput('height', 'Height', { min: 0, max: compositionHeight })}
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:40:    { type: 'float', widgetType: 'shader-number', label: 'Float' },
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:41:    { type: 'int', widgetType: 'shader-number', label: 'Integer' },
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:47:    { type: 'frame', widgetType: 'shader-number', label: 'Frame' },
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:48:    { type: 'time', widgetType: 'shader-number', label: 'Time' },
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:222:  it('built-in validation paths cover number, shader scalars, vectors, boolean, select, color, audio-binding', () => {
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:228:    expect(reg.validationPaths.has('shader-scalar-path')).toBe(true);
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:229:    expect(reg.validationPaths.has('shader-vector-path')).toBe(true);
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:230:    expect(reg.validationPaths.has('shader-color-vector-path')).toBe(true);
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:289:  it('shader scalar validation covers float, int, frame, and time', () => {
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:291:    const path = reg.validationPaths.get('shader-scalar-path')!;
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:300:  it('shader vector validation covers vec2, vec3, vec4, and color vectors', () => {
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:302:    const vectorPath = reg.validationPaths.get('shader-vector-path')!;
src/tools/video-editor/runtime/schemaCapabilityRegistry.test.ts:303:    const colorPath = reg.validationPaths.get('shader-color-vector-path')!;
src/tools/video-editor/runtime/diagnosticCollectionSync.ts:11:} from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/runtime/diagnosticCollectionSync.ts:18:  | 'shader-effect-registry'
src/tools/video-editor/runtime/diagnosticCollectionSync.ts:37:    detail.clipId ?? detail.effectType ?? detail.shaderId ?? detail.clipType ?? detail.transitionType ?? index,
src/tools/video-editor/runtime/diagnosticCollectionSync.ts:52:  //    a shader stage) inside detail.source; we move that into
src/tools/video-editor/components/PropertiesPanel/AssetPanel.tsx:569:                      {/* Host-owned related materials */}
src/tools/video-editor/components/EffectCreatorPanel.tsx:27:import { SyntheticAudioProvider } from '@/tools/video-editor/compositions/AudioAnalysisProvider.tsx';
src/tools/video-editor/components/EffectCreatorPanel.tsx:68:// Preview composition — colored rectangle wrapped by the effect component
src/tools/video-editor/components/EffectCreatorPanel.tsx:410:  // Preview composition memoized on the component ref
src/tools/video-editor/components/EffectCreatorPanel.tsx:501:                  compositionWidth={PREVIEW_SIZE}
src/tools/video-editor/components/EffectCreatorPanel.tsx:502:                  compositionHeight={PREVIEW_SIZE}
src/tools/video-editor/components/PropertiesPanel/AssetPanel.test.tsx:666:  it('expands to show related materials', () => {
src/tools/video-editor/components/PropertiesPanel/AssetPanel.test.tsx:1079:      matches: Array<{ ref: string; kind: 'asset' | 'material'; score: number; excerpt?: string }>;
src/tools/video-editor/components/PropertiesPanel/AssetPanel.test.tsx:1168:  it('includes material results in merged output without affecting asset visibility', () => {
src/tools/video-editor/components/PropertiesPanel/AssetPanel.test.tsx:1187:            { ref: 'mat-1', kind: 'material', score: 0.9, excerpt: 'Material match' },
src/tools/video-editor/components/PropertiesPanel/AssetPanel.test.tsx:1201:    // Material match does NOT appear as an asset row (materials are separate)
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:128:  outputFormat: 'Output format',
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:134:  shader: 'Shader',
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:187:  for (const of_ of extensionRuntime.config.outputFormats) {
src/tools/video-editor/components/ExtensionManager/ExtensionManager.tsx:205:  for (const sh of extensionRuntime.config.shaders) {
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:11:import { useShaderEffectRegistrySnapshot } from '@/tools/video-editor/shaders/registry/ShaderEffectRegistryContext.tsx';
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:106:    compositionSize,
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:135:  const shaderSnapshot = useShaderEffectRegistrySnapshot();
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:146:      inspectorTarget?.kind === 'shader'
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:147:      && inspectorTarget.shaderScope === 'postprocess'
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:152:        kind: 'shader' as const,
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:153:        shaderScope: 'postprocess' as const,
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:154:        shaderId: inspectorTarget.shaderId ?? undefined,
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:175:    if (inspectorSelectionTarget.kind !== 'shader' || inspectorSelectionTarget.shaderScope !== 'postprocess') {
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:195:  const bulkWidth = getSharedValue(bulkSelectedClips.map((clip) => clip.width ?? compositionSize.width));
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:196:  const bulkHeight = getSharedValue(bulkSelectedClips.map((clip) => clip.height ?? compositionSize.height));
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:316:            compositionWidth={compositionSize.width}
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:317:            compositionHeight={compositionSize.height}
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:378:            compositionWidth={compositionSize.width}
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:379:            compositionHeight={compositionSize.height}
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:398:          shaderSnapshot={shaderSnapshot}
src/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx:407:          shaderSnapshot={shaderSnapshot}
src/tools/video-editor/lib/renderRouter.test.ts:77:  it('treats legacy clips with undefined clipType as native media', () => {
src/tools/video-editor/lib/renderRouter.test.ts:201:    renderability: {
src/tools/video-editor/lib/renderRouter.test.ts:533:  it('materializes sequence asset keys for the render payload without mutating persisted params', () => {
src/tools/video-editor/runtime/extensionLifecycle.test.ts:37:import type { LiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry';
src/tools/video-editor/runtime/extensionLifecycle.test.ts:98:      materials: {},
src/tools/video-editor/runtime/extensionLifecycle.test.ts:1870:      'materials',
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2359:  // ---- shader cleanup -------------------------------------------------------
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2361:  it('cleans up shader contribution on extension removal', () => {
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2362:    const shaderCleanup = vi.fn();
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2364:    const e1 = extWithContributions('com.example.shader', [
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2365:      { contribId: 'my-shader', kind: 'shader', cleanup: shaderCleanup },
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2372:    expect(shaderCleanup).toHaveBeenCalledTimes(1);
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2407:  // ---- live-data cleanup (via liveDataRegistry) ------------------------------
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2418:    const liveDataCleanup = vi.fn();
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2421:      { contribId: 'live-source', kind: 'slot', cleanup: liveDataCleanup },
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2429:    // Remove extension — liveDataRegistry.disposeExtensionSources should be called
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2433:    expect(liveDataCleanup).toHaveBeenCalledTimes(1); // dispose handle also fires
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2523:      shader: vi.fn(),
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2534:        { id: 'c-shader' as ContributionId, kind: 'shader' as any },
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2543:          cleanup.shader();
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2569:      shader: vi.fn(),
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2577:        { id: 'd-shader' as ContributionId, kind: 'shader' as any },
src/tools/video-editor/runtime/extensionLifecycle.test.ts:2583:          cleanup.shader();
src/tools/video-editor/runtime/extensionLifecycle.test.ts:3068:    const extC = makeCleanableExt('com.example.c', 'shader');
src/sdk/examples-governance.test.ts:197:  // enrichment status, export service, material read surface, diagnostics,
src/sdk/examples-governance.test.ts:213:  // M13 deferred shader-frontend exports (all Shader* exports)
src/sdk/examples-governance.test.ts:647:  const outputFormatContribution = contributions.find(
src/sdk/examples-governance.test.ts:649:      contribution.kind === 'outputFormat',
src/sdk/examples-governance.test.ts:652:  it('compiles through public SDK output format exports', () => {
src/sdk/examples-governance.test.ts:656:    expect(outputFormatContribution).toBeDefined();
src/sdk/examples-governance.test.ts:657:    expect(outputFormatContribution.kind).toBe('outputFormat');
src/sdk/examples-governance.test.ts:658:    expect(outputFormatContribution.label).toBe('Metadata JSON Export');
src/sdk/examples-governance.test.ts:661:  it('declares a compile-only output format with requiresRender: false', () => {
src/sdk/examples-governance.test.ts:662:    expect(outputFormatContribution.requiresRender).toBe(false);
src/sdk/examples-governance.test.ts:663:    expect(outputFormatContribution.outputExtension).toBe('json');
src/sdk/examples-governance.test.ts:664:    expect(outputFormatContribution.outputMimeType).toBe('application/json');
src/sdk/examples-governance.test.ts:668:    expect(typeof outputFormatContribution.description).toBe('string');
src/sdk/examples-governance.test.ts:669:    expect(outputFormatContribution.description!.length).toBeGreaterThan(0);
src/sdk/examples-governance.test.ts:673:    expect(outputFormatContribution.order).toBe(10);
src/tools/video-editor/lib/sha256.ts:7: * (or eagerly) from import, timeline load, or preview materialization code paths.
src/tools/video-editor/lib/sha256.ts:19: * never materialise their entire contents in a single ArrayBuffer.
src/tools/video-editor/runtime/livePermissions.ts:9: * The service is pure: it does not mutate the live data registry or persisted
src/tools/video-editor/runtime/livePermissions.ts:79: * A service that probes and requests browser permissions for live data sources.
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:18:import type { ShaderEffectRegistrySnapshot } from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:21:type ShaderInspectorCompareMode = 'shader' | 'bypass';
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:27:  shaderSnapshot: ShaderEffectRegistrySnapshot;
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:126:function getCompareMode(shader: TimelineShaderBaseMetadata): ShaderInspectorCompareMode {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:127:  if (shader.enabled === false) {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:131:  return shader.metadata?.inspectorCompareMode === 'bypass' ? 'bypass' : 'shader';
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:134:function getUniformPreset(shader: TimelineShaderBaseMetadata): 'custom' | 'defaults' {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:135:  return shader.metadata?.uniformPreset === 'defaults' ? 'defaults' : 'custom';
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:139:  shader: EditableShaderMetadata,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:146:      code: 'shader-inspector/texture-ref-deferred',
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:149:        ownerExtensionId: shader.extensionId,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:150:        contributionId: shader.contributionId,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:151:        shaderId: shader.shaderId,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:159:  shader: EditableShaderMetadata,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:160:  shaderSnapshot: ShaderEffectRegistrySnapshot,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:165:    ...shaderSnapshot.diagnostics.filter((diagnostic) => {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:167:      return detail?.shaderId === shader.shaderId
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:168:        || detail?.contributionId === shader.contributionId
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:169:        || detail?.ownerExtensionId === shader.extensionId;
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:182:  shaderSnapshot,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:185:  const shader = clip ? getTimelineClipShader(clip) : postprocessShader ?? undefined;
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:186:  const record = shader
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:187:    ? shaderSnapshot.get(shader.shaderId, shader.extensionId)
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:189:  const diagnostics = shader && record
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:190:    ? collectShaderDiagnostics(shader, shaderSnapshot, record.diagnostics)
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:192:  const textureRefDiagnostics = shader
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:193:    ? collectTextureRefDiagnostics(shader, record?.uniforms)
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:205:    () => getEditableShaderUniformValues(shader?.uniforms, record?.uniforms),
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:206:    [record?.uniforms, shader?.uniforms],
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:220:    shader?.extensionId,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:221:    shader?.contributionId,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:222:    shader?.shaderId,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:225:  if (!resolvedConfig || !shader || (shader.scope === 'clip' && !clip)) {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:237:          code: 'shader-inspector/missing-registry-record',
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:238:          message: `Shader "${shader.shaderId}" is assigned to this clip but is not registered.`,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:244:  const enabled = shader.enabled !== false;
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:245:  const compareMode = getCompareMode(shader);
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:258:      ...shader,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:259:      label: shader.label ?? record.label,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:261:      ...((Object.keys(defaultTextures).length > 0 || shader.textures)
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:262:        ? { textures: { ...defaultTextures, ...(shader.textures ?? {}) } }
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:267:        ...(shader.metadata ?? {}),
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:277:          shader: nextShader,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:289:        shaderPostprocess: nextShader,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:299:      getUniformPreset(shader),
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:301:      nextEnabled ? 'shader' : 'bypass',
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:308:      data-testid="shader-inspector"
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:313:            {shader.scope === 'postprocess' ? 'Postprocess Shader' : 'Shader'}
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:316:            {record?.label ?? shader.label ?? shader.shaderId}
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:319:            {shader.extensionId} / {shader.contributionId}
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:328:            data-testid="shader-inspector-enabled"
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:339:              data-testid={`shader-inspector-diagnostic-${index}`}
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:368:              onClick={() => persist(values, getUniformPreset(shader), false, 'bypass')}
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:371:              data-testid="shader-inspector-compare-bypass"
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:377:              variant={compareMode === 'shader' ? 'secondary' : 'outline'}
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:379:              onClick={() => persist(values, getUniformPreset(shader), true, 'shader')}
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:381:              aria-pressed={compareMode === 'shader'}
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:382:              data-testid="shader-inspector-compare-shader"
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:396:          data-testid="shader-inspector-split-view-deferred"
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:415:          This shader does not expose editable uniforms.
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:438:          Apply shader
src/sdk/extensionSettingsService.test.ts:498:  const EXT_ID = 't9.legacy.ext';
src/sdk/extensionSettingsService.test.ts:508:  it('reads legacy localStorage keys with no snapshot', () => {
src/sdk/extensionSettingsService.test.ts:509:    // Pre-populate legacy localStorage (as a previous version of the service would)
src/sdk/extensionSettingsService.test.ts:510:    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'legacyKey', JSON.stringify('legacyValue'));
src/sdk/extensionSettingsService.test.ts:518:    expect(s.get('legacyKey')).toBe('legacyValue');
src/sdk/extensionSettingsService.test.ts:524:  it('legacy localStorage overrides snapshot values', () => {
src/sdk/extensionSettingsService.test.ts:525:    // Simulate: previous version stored legacy value, then a new version loads
src/sdk/extensionSettingsService.test.ts:527:    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'theme', JSON.stringify('legacy-dark'));
src/sdk/extensionSettingsService.test.ts:537:    expect(s.get('theme')).toBe('legacy-dark');
src/sdk/extensionSettingsService.test.ts:542:  it('legacy key migration: snapshot values readable alongside legacy keys', () => {
src/sdk/extensionSettingsService.test.ts:544:    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'legacyOnly', JSON.stringify('from-legacy'));
src/sdk/extensionSettingsService.test.ts:555:    expect(s.get('legacyOnly')).toBe('from-legacy');
src/sdk/extensionSettingsService.test.ts:560:    expect(keys).toContain('legacyOnly');
src/sdk/extensionSettingsService.test.ts:566:  it('legacy keys are included in keys()', () => {
src/sdk/extensionSettingsService.test.ts:567:    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'legacy1', 'v1');
src/sdk/extensionSettingsService.test.ts:568:    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'legacy2', 'v2');
src/sdk/extensionSettingsService.test.ts:576:    expect(keys).toContain('legacy1');
src/sdk/extensionSettingsService.test.ts:577:    expect(keys).toContain('legacy2');
src/sdk/extensionSettingsService.test.ts:807:  it('legacy localStorage keys are migrated into repository snapshot on first dispose', async () => {
src/sdk/extensionSettingsService.test.ts:808:    // Simulate legacy keys from a previous version that didn't use repos
src/sdk/extensionSettingsService.test.ts:809:    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'legacyTheme', JSON.stringify('blue'));
src/sdk/extensionSettingsService.test.ts:810:    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'legacyCount', JSON.stringify(42));
src/sdk/extensionSettingsService.test.ts:819:    expect(s.get('legacyTheme')).toBe('blue');
src/sdk/extensionSettingsService.test.ts:820:    expect(s.get('legacyCount')).toBe(42);
src/sdk/extensionSettingsService.test.ts:825:    // Dispose — should write merged snapshot to repo including legacy keys
src/sdk/extensionSettingsService.test.ts:833:    expect(snapshot!.values.legacyTheme).toBe('blue');
src/sdk/extensionSettingsService.test.ts:834:    expect(snapshot!.values.legacyCount).toBe(42);
src/sdk/extensionSettingsService.test.ts:838:  it('post-migration: snapshot values survive reload without legacy localStorage', async () => {
src/sdk/extensionSettingsService.test.ts:867:  it('legacy-to-repo migration preserves manifest defaults for keys not in legacy', async () => {
src/sdk/extensionSettingsService.test.ts:892:  it('keys() reflects the merged state including legacy, snapshot, and defaults', () => {
src/sdk/extensionSettingsService.test.ts:893:    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'legacy', JSON.stringify('l'));
src/sdk/extensionSettingsService.test.ts:903:    expect(keys).toContain('legacy');
src/sdk/extensionSettingsService.test.ts:1110:    const snapshot = makeSnapshot(EXT_ID, 1, { theme: 'dark', oldKey: 'legacy' });
src/sdk/extensionSettingsService.test.ts:1187:  // ---- Migration with legacy settingsSchemaVersion ------------------------
src/sdk/extensionSettingsService.test.ts:1189:  it('detects schema version from legacy settingsSchemaVersion', () => {
src/sdk/extensionSettingsService.test.ts:2005:  it('validates candidate including legacy localStorage values', () => {
src/sdk/extensionSettingsService.test.ts:2006:    // Pre-populate legacy localStorage
src/sdk/extensionSettingsService.test.ts:2007:    localStorage.setItem(getSettingsPrefix(EXT_ID) + 'theme', JSON.stringify('legacy-dark'));
src/sdk/extensionSettingsService.test.ts:2022:    expect(s.get('theme')).toBe('legacy-dark');
src/sdk/extensionSettingsService.test.ts:2024:    // Setting an invalid maxItems — candidate includes legacy theme value
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:5:import type { ShaderEffectRegistryRecord, ShaderEffectRegistrySnapshot } from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:14:    shader: {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:16:      extensionId: 'com.example.shader',
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:18:      shaderId: 'wash',
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:35:    ownerExtensionId: 'com.example.shader',
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:37:    shaderId: 'wash',
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:56:    renderability: {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:69:    get: (shaderId, ownerExtensionId) => (
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:70:      shaderId === record.shaderId && ownerExtensionId === record.ownerExtensionId ? record : undefined
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:73:      lookup.shaderId === record.shaderId && lookup.ownerExtensionId === record.ownerExtensionId ? record : undefined
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:75:    has: (shaderId, ownerExtensionId) => shaderId === record.shaderId && ownerExtensionId === record.ownerExtensionId,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:76:    hasByLookup: (lookup) => lookup.shaderId === record.shaderId && lookup.ownerExtensionId === record.ownerExtensionId,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:95:      shaderSnapshot={createSnapshot(record)}
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:104:  it('renders clip-local shader controls and persists edited uniforms on timeline metadata', () => {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:111:    fireEvent.click(screen.getByRole('button', { name: 'Apply shader' }));
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:115:    const nextShader = mutation.resolvedConfig.clips[0].app.shader;
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:118:    expect(nextShader.metadata.inspectorCompareMode).toBe('shader');
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:129:    const nextShader = mutation.resolvedConfig.clips[0].app.shader;
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:132:    expect(nextShader.metadata.inspectorCompareMode).toBe('shader');
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:140:        shader: {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:141:          ...baseClip.app!.shader!,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:156:    const nextShader = applyEdit.mock.calls[0][0].resolvedConfig.clips[0].app.shader;
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:163:  it('persists bypass through host-owned shader metadata without touching unrelated clip app data', () => {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:169:        shader: {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:170:          ...baseClip.app!.shader!,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:183:    fireEvent.click(screen.getByTestId('shader-inspector-enabled'));
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:190:    expect(nextClip.app.shader.enabled).toBe(false);
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:191:    expect(nextClip.app.shader.uniforms).toEqual({ intensity: 0.25 });
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:192:    expect(nextClip.app.shader.metadata).toMatchObject({
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:202:    const splitView = screen.getByTestId('shader-inspector-split-view-deferred');
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:212:    expect(screen.getByTestId('shader-inspector-compare-shader')).toHaveAttribute('aria-pressed', 'true');
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:213:    expect(screen.getByTestId('shader-inspector-compare-bypass')).toHaveAttribute('aria-pressed', 'false');
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:215:    fireEvent.click(screen.getByTestId('shader-inspector-compare-bypass'));
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:217:    const nextShader = applyEdit.mock.calls[0][0].resolvedConfig.clips[0].app.shader;
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:223:  it('restores shader A/B mode through host-owned metadata without touching unrelated clip app data', () => {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:229:        shader: {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:230:          ...baseClip.app!.shader!,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:240:    expect(screen.getByTestId('shader-inspector-compare-bypass')).toHaveAttribute('aria-pressed', 'true');
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:241:    expect(screen.getByTestId('shader-inspector-compare-shader')).toHaveAttribute('aria-pressed', 'false');
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:242:    fireEvent.click(screen.getByTestId('shader-inspector-compare-shader'));
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:246:    expect(nextClip.app.shader.enabled).toBe(true);
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:247:    expect(nextClip.app.shader.metadata.uniformPreset).toBe('defaults');
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:248:    expect(nextClip.app.shader.metadata.inspectorCompareMode).toBe('shader');
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:256:        shader: {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:257:          ...baseClip.app!.shader!,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:265:    expect(screen.getByTestId('shader-inspector-compare-bypass')).toHaveAttribute('aria-pressed', 'true');
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:266:    expect(screen.getByTestId('shader-inspector-compare-shader')).toHaveAttribute('aria-pressed', 'false');
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:270:    const nextShader = applyEdit.mock.calls[0][0].resolvedConfig.clips[0].app.shader;
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:299:    expect(screen.getByTestId('shader-inspector-diagnostic-0')).toHaveTextContent(
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:300:      'shader-inspector/texture-ref-deferred',
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:302:    expect(screen.getByTestId('shader-inspector-diagnostic-0')).toHaveAttribute('role', 'status');
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:307:    const applyButton = screen.getByRole('button', { name: 'Apply shader' });
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:311:    const nextShader = applyEdit.mock.calls[0][0].resolvedConfig.clips[0].app.shader;
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:323:        shader: {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:324:          ...baseClip.app!.shader!,
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:359:    const nextShader = applyEdit.mock.calls[0][0].resolvedConfig.clips[0].app.shader;
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:372:        shaderSnapshot={createSnapshot(createRecord())}
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:383:        shaderSnapshot={createSnapshot(createRecord({
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:402:  it('disables apply when shader diagnostics contain errors', () => {
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:408:          code: 'shader/compile-error',
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:409:          message: 'Fragment shader failed to compile.',
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:414:    expect(screen.getByRole('button', { name: 'Apply shader' })).toBeDisabled();
src/tools/video-editor/components/ShaderInspector/ShaderInspector.test.tsx:415:    expect(screen.getByTestId('shader-inspector-diagnostic-0')).toHaveTextContent('shader/compile-error');
src/tools/video-editor/runtime/agentToolRegistry.test.ts:29:import { createLiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry';
src/tools/video-editor/runtime/agentToolRegistry.test.ts:699:    const registry = createAgentToolRegistry({ liveDataRegistry: liveRegistry });
src/tools/video-editor/runtime/agentToolRegistry.test.ts:718:    const registry = createAgentToolRegistry({ liveDataRegistry: liveRegistry });
src/tools/video-editor/runtime/agentToolRegistry.test.ts:806:    const configuredRegistry = createAgentToolRegistry({ liveDataRegistry: liveRegistry });
src/sdk/extensionSettingsMigration.ts:89: * Prefers `manifest.settingsSchema?.version` over the legacy
src/sdk/extensionSettingsMigration.ts:122:    // Accept both typed MigrationDeclaration and legacy Record<string, unknown>
src/tools/video-editor/runtime/ContributionErrorBoundary.test.tsx:390:    describe('without recoveryKey (legacy behavior)', () => {
src/tools/video-editor/runtime/ContributionErrorBoundary.test.tsx:394:            contributionId="test.legacy"
src/tools/video-editor/runtime/ContributionErrorBoundary.test.tsx:408:            contributionId="test.legacy"
src/tools/video-editor/runtime/liveDataRegistry.ts:2: * M11: Provider-scoped live data registry.
src/tools/video-editor/runtime/liveDataRegistry.ts:16: * @module liveDataRegistry
src/sdk/boundary.test.ts:57:  // M6: Parser / output format / search provider
src/sdk/boundary.test.ts:400:      'shaders',
src/sdk/boundary.test.ts:417:      'shaders',
src/sdk/boundary.test.ts:507:      'materials',
src/sdk/boundary.test.ts:617:      'shaders',
src/sdk/boundary.test.ts:639:  it('outputFormat is typed but execution is reserved (returns M6)', () => {
src/sdk/boundary.test.ts:640:    expect(contributionKindNotYetBridged('outputFormat')).toBe('M6');
src/sdk/boundary.test.ts:648:    // outputFormat (both compile-only and render-dependent) is declarable
src/sdk/boundary.test.ts:650:    const bridged = contributionKindNotYetBridged('outputFormat');
src/sdk/boundary.test.ts:667:    expect(CONTRIBUTION_KIND_MILESTONE.outputFormat).toBe('M6');
src/sdk/boundary.test.ts:686:describe('M6: ExtensionManifest contributions accept parser/outputFormat/searchProvider', () => {
src/sdk/boundary.test.ts:708:  it('defineExtension accepts a manifest with an outputFormat contribution (compile-only)', () => {
src/sdk/boundary.test.ts:717:            kind: 'outputFormat',
src/sdk/boundary.test.ts:727:    expect(ext.manifest.contributions![0].kind).toBe('outputFormat');
src/sdk/boundary.test.ts:730:  it('defineExtension accepts a manifest with an outputFormat contribution (render-dependent, reserved)', () => {
src/sdk/boundary.test.ts:739:            kind: 'outputFormat',
src/sdk/boundary.test.ts:749:    expect(ext.manifest.contributions![0].kind).toBe('outputFormat');
src/sdk/boundary.test.ts:790:              kind: 'outputFormat',
src/sdk/boundary.test.ts:939:      'material/artifact',
src/sdk/boundary.test.ts:997:  it('ToolMaterialArtifactResult has family material/artifact with refs', () => {
src/sdk/boundary.test.ts:1005:      family: 'material/artifact',
src/sdk/boundary.test.ts:1009:    expect(result.family).toBe('material/artifact');
src/sdk/boundary.test.ts:1073:      { family: 'material/artifact', refs: [] },
src/sdk/boundary.test.ts:1107:  it('ToolArtifactRef supports asset, material, and placeholder kinds', () => {
src/sdk/boundary.test.ts:1109:    const materialRef: ToolArtifactRef = { ref: 'key-2', kind: 'material', label: 'Material' };
src/sdk/boundary.test.ts:1113:    expect(materialRef.kind).toBe('material');
src/sdk/boundary.test.ts:1136:  it('AgentToolRequestContext carries timeline, assets, materials, export, and meta', () => {
src/sdk/boundary.test.ts:1140:      materials: [{ key: 'mat-1', metadata: { type: 'video' } }],
src/sdk/boundary.test.ts:1142:        outputFormatId: 'metadata-json',
src/sdk/boundary.test.ts:1150:    expect(ctx.export?.outputFormatId).toBe('metadata-json');
src/sdk/boundary.test.ts:1156:      outputFormatId: 'mp4-export',
src/sdk/boundary.test.ts:1160:    expect(exportCtx.outputFormatId).toBe('mp4-export');
src/sdk/boundary.test.ts:1385:    expect(contributionKindNotYetBridged('shader')).toBeNull();
src/sdk/boundary.test.ts:1390:// M13: Dedicated shader contribution and registration boundary
src/sdk/boundary.test.ts:1393:describe('M13: shader contributions stay separate from component effects', () => {
src/sdk/boundary.test.ts:1394:  const shaderSource: ShaderInlineSource = {
src/sdk/boundary.test.ts:1399:  const shaderContribution: ShaderContribution = {
src/sdk/boundary.test.ts:1401:    kind: 'shader',
src/sdk/boundary.test.ts:1402:    shaderId: 'shader.postprocessGrade',
src/sdk/boundary.test.ts:1405:    source: shaderSource,
src/sdk/boundary.test.ts:1429:  it('normalizes kind: shader as bridged M13 metadata', () => {
src/sdk/boundary.test.ts:1430:    expect(CONTRIBUTION_KIND_MILESTONE.shader).toBe('M13');
src/sdk/boundary.test.ts:1431:    expect(contributionKindNotYetBridged('shader')).toBeNull();
src/sdk/boundary.test.ts:1434:  it('defineExtension preserves shader shape and does not create effect metadata', () => {
src/sdk/boundary.test.ts:1437:        id: 'com.m13.shader' as any,
src/sdk/boundary.test.ts:1440:        contributions: [shaderContribution],
src/sdk/boundary.test.ts:1444:    expect(contribution.kind).toBe('shader');
src/sdk/boundary.test.ts:1445:    expect(contribution.shaderId).toBe('shader.postprocessGrade');
src/sdk/boundary.test.ts:1449:  it('ctx.shaders registration does not call ctx.effects.registerComponent', () => {
src/sdk/boundary.test.ts:1452:        id: 'com.m13.shader-service' as any,
src/sdk/boundary.test.ts:1455:        contributions: [shaderContribution],
src/sdk/boundary.test.ts:1459:    const shaderCalls: string[] = [];
src/sdk/boundary.test.ts:1460:    const shaderService: ShaderRegistrationService = {
src/sdk/boundary.test.ts:1461:      registerShader(shaderId, source) {
src/sdk/boundary.test.ts:1462:        shaderCalls.push(`${shaderId}:${source.kind}`);
src/sdk/boundary.test.ts:1480:      shaderService,
src/sdk/boundary.test.ts:1483:    ctx.shaders.registerShader('shader.postprocessGrade', shaderSource);
src/sdk/boundary.test.ts:1484:    expect(shaderCalls).toEqual(['shader.postprocessGrade:inline']);
src/sdk/boundary.test.ts:1488:  it('unwired shader registration emits only shader not-wired diagnostics', () => {
src/sdk/boundary.test.ts:1491:        id: 'com.m13.shader-unwired' as any,
src/sdk/boundary.test.ts:1494:        contributions: [shaderContribution],
src/sdk/boundary.test.ts:1499:    ctx.shaders.registerShader('shader.postprocessGrade', shaderSource);
src/sdk/boundary.test.ts:1502:    expect(codes).toContain('shaders/not-wired');
src/sdk/boundary.test.ts:1969:      materials: {} as any,
src/sdk/boundary.test.ts:1986:    'liveDataRegistry',
src/tools/video-editor/lib/timeline-patch.test.ts:1818:  extensionId: 'com.example.shader',
src/tools/video-editor/lib/timeline-patch.test.ts:1819:  contributionId: 'clip-glow-shader',
src/tools/video-editor/lib/timeline-patch.test.ts:1820:  shaderId: 'shader.clipGlow',
src/tools/video-editor/lib/timeline-patch.test.ts:1826:  extensionId: 'com.example.shader',
src/tools/video-editor/lib/timeline-patch.test.ts:1827:  contributionId: 'clip-edge-shader',
src/tools/video-editor/lib/timeline-patch.test.ts:1828:  shaderId: 'shader.clipEdge',
src/tools/video-editor/lib/timeline-patch.test.ts:1833:  extensionId: 'com.example.shader',
src/tools/video-editor/lib/timeline-patch.test.ts:1834:  contributionId: 'post-grade-shader',
src/tools/video-editor/lib/timeline-patch.test.ts:1835:  shaderId: 'shader.postGrade',
src/tools/video-editor/lib/timeline-patch.test.ts:1841:  extensionId: 'com.example.shader',
src/tools/video-editor/lib/timeline-patch.test.ts:1842:  contributionId: 'post-vignette-shader',
src/tools/video-editor/lib/timeline-patch.test.ts:1843:  shaderId: 'shader.postVignette',
src/tools/video-editor/lib/timeline-patch.test.ts:1905:describe('compileTimelinePatch — shader metadata scope limits', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:1906:  it('patches and persists a clip-local shader through clip.update', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:1914:        operations: [makeOp('clip.update', 'c1', { app: { shader: clipShader } })],
src/tools/video-editor/lib/timeline-patch.test.ts:1921:    expect(result.nextData!.config.clips.find((clip: any) => clip.id === 'c1')!.app.shader).toEqual(clipShader);
src/tools/video-editor/lib/timeline-patch.test.ts:1922:    expect(result.mutation!.metaUpdates!['c1'].app).toEqual({ shader: clipShader });
src/tools/video-editor/lib/timeline-patch.test.ts:1925:  it('refuses to replace an occupied clip-local shader scope', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:1928:      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10, app: { shader: clipShader } }],
src/tools/video-editor/lib/timeline-patch.test.ts:1933:        operations: [makeOp('clip.update', 'c1', { app: { shader: replacementClipShader } })],
src/tools/video-editor/lib/timeline-patch.test.ts:1940:        code: 'timeline-patch/shader-scope-occupied',
src/tools/video-editor/lib/timeline-patch.test.ts:1942:        message: 'Cannot add shader "shader.clipEdge" to clip "c1" because shader "shader.clipGlow" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.',
src/tools/video-editor/lib/timeline-patch.test.ts:1945:    expect(result.nextData!.config.clips.find((clip: any) => clip.id === 'c1')!.app.shader).toEqual(clipShader);
src/tools/video-editor/lib/timeline-patch.test.ts:1948:  it('patches and persists the timeline postprocess shader through app.update', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:1966:  it('refuses to replace an occupied postprocess shader scope', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:1982:        code: 'timeline-patch/shader-scope-occupied',
src/tools/video-editor/lib/timeline-patch.test.ts:1984:        message: 'Cannot add postprocess shader "shader.postVignette" because postprocess shader "shader.postGrade" is already assigned. V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.',
src/tools/video-editor/lib/timeline-patch.test.ts:4212:  it('persists a small DSL snippet (shader/material) and replays identically', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:4219:      type: 'shader',
src/tools/video-editor/lib/timeline-patch.test.ts:4228:        makeOp('project-data.write', 'com.shaders.ext', { key: 'fragment_red', value: dslSnippet }),
src/tools/video-editor/lib/timeline-patch.test.ts:4235:    const stored1 = (result1.nextData!.config.app['com.shaders.ext'] as Record<string, unknown>).fragment_red;
src/tools/video-editor/lib/timeline-patch.test.ts:4241:    const stored2 = (result2.nextData!.config.app['com.shaders.ext'] as Record<string, unknown>).fragment_red;
src/tools/video-editor/lib/timeline-patch.test.ts:4314:  it('round-trips a material reference through write, read, delete, re-add', () => {
src/tools/video-editor/lib/timeline-patch.test.ts:4320:    const materialRef = {
src/tools/video-editor/lib/timeline-patch.test.ts:4321:      type: 'material_ref',
src/tools/video-editor/lib/timeline-patch.test.ts:4323:      resourcePath: '/materials/glossy_red.json',
src/tools/video-editor/lib/timeline-patch.test.ts:4332:          makeOp('project-data.write', 'com.materials.ext', { key: 'mat_glossy', value: materialRef }),
src/tools/video-editor/lib/timeline-patch.test.ts:4338:    expect((r1.nextData!.config.app['com.materials.ext'] as Record<string, unknown>).mat_glossy).toEqual(materialRef);
src/tools/video-editor/lib/timeline-patch.test.ts:4341:    const stored = (r1.nextData!.config.app['com.materials.ext'] as Record<string, unknown>).mat_glossy;
src/tools/video-editor/lib/timeline-patch.test.ts:4342:    expect(stored).toEqual(materialRef);
src/tools/video-editor/lib/timeline-patch.test.ts:4348:          makeOp('project-data.delete', 'com.materials.ext', { key: 'mat_glossy' }),
src/tools/video-editor/lib/timeline-patch.test.ts:4357:      expect(r2App['com.materials.ext']).toBeUndefined();
src/tools/video-editor/lib/timeline-patch.test.ts:4361:    const updatedRef = { ...materialRef, parameters: { roughness: 0.7, metallic: 0.5 } };
src/tools/video-editor/lib/timeline-patch.test.ts:4365:          makeOp('project-data.write', 'com.materials.ext', { key: 'mat_glossy', value: updatedRef }),
src/tools/video-editor/lib/timeline-patch.test.ts:4371:    expect((r3.nextData!.config.app['com.materials.ext'] as Record<string, unknown>).mat_glossy).toEqual(updatedRef);
src/tools/video-editor/lib/timeline-patch.test.ts:4649:    // - material refs (key values are often material/asset references)
src/tools/video-editor/runtime/liveBake.test.ts:119:  it('bakes material destinations to RenderMaterial replacement refs', () => {
src/tools/video-editor/runtime/liveBake.test.ts:126:          kind: 'render-material',
src/tools/video-editor/runtime/liveBake.test.ts:127:          ref: 'material-live-frame',
src/tools/video-editor/runtime/liveBake.test.ts:139:    expect(result.replacements[0].deterministicRef.kind).toBe('render-material');
src/tools/video-editor/runtime/liveBake.test.ts:141:      id: 'material-live-frame',
src/tools/video-editor/runtime/liveBake.test.ts:148:    expect(result.replacements[0].renderMaterial?.locator.uri).toBe('live-bake://src-live/material-live-frame');
src/tools/video-editor/runtime/transitionRegistrationService.ts:8: * provenance / owner / schema / renderability / diagnostics, supports HMR
src/tools/video-editor/runtime/transitionRegistrationService.ts:33:} from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/runtime/transitionRegistrationService.ts:255: * failures — legacy applied parameters continue to be coerced at render time
src/tools/video-editor/runtime/transitionRegistrationService.ts:445:    const renderability = buildRenderability(contrib);
src/tools/video-editor/runtime/transitionRegistrationService.ts:449:    // continues to work for already-applied legacy data.
src/tools/video-editor/runtime/transitionRegistrationService.ts:463:      renderability,
src/tools/video-editor/runtime/renderPlanner.ts:29:  readonly outputFormatId?: string;
src/tools/video-editor/runtime/renderPlanner.ts:36:  readonly materialRefId: string;
src/tools/video-editor/runtime/renderPlanner.ts:45:  readonly extensionRuntime?: Pick<ExtensionRuntime, 'outputFormats' | 'processes' | 'shaders'>;
src/tools/video-editor/runtime/renderPlanner.ts:46:  readonly outputFormats?: readonly VideoEditorOutputFormatDescriptor[];
src/tools/video-editor/runtime/renderPlanner.ts:48:  readonly shaders?: readonly VideoEditorShaderDescriptor[];
src/tools/video-editor/runtime/renderPlanner.ts:50:  readonly materialRefs?: readonly RenderMaterialRef[];
src/tools/video-editor/runtime/renderPlanner.ts:51:  readonly materialStatuses?: readonly RenderPlannerMaterialStatus[];
src/tools/video-editor/runtime/renderPlanner.ts:68:  readonly outputFormatIds: readonly string[];
src/tools/video-editor/runtime/renderPlanner.ts:258:function shaderDescriptorKey(extensionId: string | undefined, contributionId: string | undefined): string {
src/tools/video-editor/runtime/renderPlanner.ts:266:    shaderDescriptorKey(descriptor.extensionId, descriptor.id),
src/tools/video-editor/runtime/renderPlanner.ts:279:    && requirement.requiredCapabilities.includes('shader-materializer')
src/tools/video-editor/runtime/renderPlanner.ts:280:    && requirement.requiredCapabilities.includes('render-material');
src/tools/video-editor/runtime/renderPlanner.ts:292:    return !operation.outputKinds || operation.outputKinds.includes('material');
src/tools/video-editor/runtime/renderPlanner.ts:296:function shaderMaterializerSupportsRoute(
src/tools/video-editor/runtime/renderPlanner.ts:301:  const materializer = descriptor.materializer;
src/tools/video-editor/runtime/renderPlanner.ts:302:  if (!materializer) return false;
src/tools/video-editor/runtime/renderPlanner.ts:303:  if (materializer.routes?.includes(requirement.route)) return true;
src/tools/video-editor/runtime/renderPlanner.ts:304:  if (!materializer.processId) return false;
src/tools/video-editor/runtime/renderPlanner.ts:306:    processById.get(materializer.processId),
src/tools/video-editor/runtime/renderPlanner.ts:307:    materializer.operationId,
src/tools/video-editor/runtime/renderPlanner.ts:312:function shaderMaterializationMessage(
src/tools/video-editor/runtime/renderPlanner.ts:316:  if (descriptor.materializer?.unavailableMessage) return descriptor.materializer.unavailableMessage;
src/tools/video-editor/runtime/renderPlanner.ts:317:  if (descriptor.materializer?.processId) {
src/tools/video-editor/runtime/renderPlanner.ts:318:    return `Shader "${descriptor.shaderId}" has a materializer route for ${requirement.route}; ` +
src/tools/video-editor/runtime/renderPlanner.ts:319:      `run process "${descriptor.materializer.processId}" to produce RenderMaterial.`;
src/tools/video-editor/runtime/renderPlanner.ts:321:  return `Shader "${descriptor.shaderId}" has a materializer route for ${requirement.route}; ` +
src/tools/video-editor/runtime/renderPlanner.ts:322:    'materialize it to produce RenderMaterial.';
src/tools/video-editor/runtime/renderPlanner.ts:325:function shaderMaterializationAction(
src/tools/video-editor/runtime/renderPlanner.ts:332:    label: `Materialize shader ${descriptor.shaderId}`,
src/tools/video-editor/runtime/renderPlanner.ts:334:    processId: descriptor.materializer?.processId,
src/tools/video-editor/runtime/renderPlanner.ts:335:    operationId: descriptor.materializer?.operationId,
src/tools/video-editor/runtime/renderPlanner.ts:340:function shaderMaterializerFinding(
src/tools/video-editor/runtime/renderPlanner.ts:347:    id: `${requirement.id}.${requirement.route}.shader-materializer.discovered`,
src/tools/video-editor/runtime/renderPlanner.ts:350:    message: `Shader materializer route discovered for "${descriptor.shaderId}" on ${requirement.route}.`,
src/tools/video-editor/runtime/renderPlanner.ts:354:      source: 'shader-materializer',
src/tools/video-editor/runtime/renderPlanner.ts:355:      shaderId: descriptor.shaderId,
src/tools/video-editor/runtime/renderPlanner.ts:356:      processId: descriptor.materializer?.processId,
src/tools/video-editor/runtime/renderPlanner.ts:357:      operationId: descriptor.materializer?.operationId,
src/tools/video-editor/runtime/renderPlanner.ts:359:      materializationState: processStatus?.state === 'busy' ? 'in-progress' : 'pending',
src/tools/video-editor/runtime/renderPlanner.ts:371:  const processStatus = descriptor.materializer?.processId
src/tools/video-editor/runtime/renderPlanner.ts:372:    ? processStatusById.get(descriptor.materializer.processId)
src/tools/video-editor/runtime/renderPlanner.ts:374:  const message = shaderMaterializationMessage(descriptor, requirement);
src/tools/video-editor/runtime/renderPlanner.ts:375:  const action = shaderMaterializationAction(descriptor, requirement, message);
src/tools/video-editor/runtime/renderPlanner.ts:389:      shaderMaterializerFinding(descriptor, requirement, action, processStatus),
src/tools/video-editor/runtime/renderPlanner.ts:395:function shaderCompositionKey(shader: TimelineShaderSummary): string | undefined {
src/tools/video-editor/runtime/renderPlanner.ts:396:  if (shader.enabled === false) return undefined;
src/tools/video-editor/runtime/renderPlanner.ts:397:  if (shader.scope === 'clip') return `clip:${shader.clipId ?? ''}`;
src/tools/video-editor/runtime/renderPlanner.ts:401:function shaderCompositionScopeMessage(
src/tools/video-editor/runtime/renderPlanner.ts:407:    return `Cannot add shader "${incoming.shaderId}" to ${target} because shader "${existing.shaderId}" is already assigned. ` +
src/tools/video-editor/runtime/renderPlanner.ts:408:      'V1 supports one clip shader per clip. Remove the existing shader before assigning another.';
src/tools/video-editor/runtime/renderPlanner.ts:411:  return `Cannot add postprocess shader "${incoming.shaderId}" because postprocess shader "${existing.shaderId}" is already assigned. ` +
src/tools/video-editor/runtime/renderPlanner.ts:412:    'V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.';
src/tools/video-editor/runtime/renderPlanner.ts:415:function shaderCompositionScopeLabel(shader: TimelineShaderSummary): string {
src/tools/video-editor/runtime/renderPlanner.ts:416:  return shader.scope === 'clip' ? `clip:${shader.clipId ?? 'unknown'}` : 'postprocess';
src/tools/video-editor/runtime/renderPlanner.ts:422:  if (!snapshot?.shaders || snapshot.shaders.length === 0) {
src/tools/video-editor/runtime/renderPlanner.ts:430:  for (const shader of snapshot.shaders) {
src/tools/video-editor/runtime/renderPlanner.ts:431:    const scopeKey = shaderCompositionKey(shader);
src/tools/video-editor/runtime/renderPlanner.ts:433:      filteredShaders.push(shader);
src/tools/video-editor/runtime/renderPlanner.ts:439:      firstByScope.set(scopeKey, shader);
src/tools/video-editor/runtime/renderPlanner.ts:440:      filteredShaders.push(shader);
src/tools/video-editor/runtime/renderPlanner.ts:444:    const message = shaderCompositionScopeMessage(existing, shader);
src/tools/video-editor/runtime/renderPlanner.ts:447:        id: `planner.shaderComposition.${shaderCompositionScopeLabel(shader)}.${shader.shaderId}.${route}.scope-occupied`,
src/tools/video-editor/runtime/renderPlanner.ts:452:        extensionId: shader.extensionId,
src/tools/video-editor/runtime/renderPlanner.ts:453:        contributionId: shader.contributionId,
src/tools/video-editor/runtime/renderPlanner.ts:455:          source: 'shader-composition-limit',
src/tools/video-editor/runtime/renderPlanner.ts:456:          scope: shader.scope,
src/tools/video-editor/runtime/renderPlanner.ts:457:          clipId: shader.clipId,
src/tools/video-editor/runtime/renderPlanner.ts:458:          existingShaderId: existing.shaderId,
src/tools/video-editor/runtime/renderPlanner.ts:459:          incomingShaderId: shader.shaderId,
src/tools/video-editor/runtime/renderPlanner.ts:472:      shaders: filteredShaders.length > 0 ? filteredShaders : undefined,
src/tools/video-editor/runtime/renderPlanner.ts:536:  outputFormat: VideoEditorOutputFormatDescriptor,
src/tools/video-editor/runtime/renderPlanner.ts:543:    id: `planner.outputFormat.${outputFormat.extensionId}.${outputFormat.id}.${route}.${requirement.processId}${operationSuffix}.process-dependent`,
src/tools/video-editor/runtime/renderPlanner.ts:547:    message: processStatusMessage(outputFormat.label, requirement.processId, route, status),
src/tools/video-editor/runtime/renderPlanner.ts:548:    extensionId: outputFormat.extensionId,
src/tools/video-editor/runtime/renderPlanner.ts:549:    contributionId: outputFormat.id,
src/tools/video-editor/runtime/renderPlanner.ts:552:      outputFormatId: outputFormat.id,
src/tools/video-editor/runtime/renderPlanner.ts:553:      outputLabel: outputFormat.label,
src/tools/video-editor/runtime/renderPlanner.ts:563:  outputFormat: VideoEditorOutputFormatDescriptor,
src/tools/video-editor/runtime/renderPlanner.ts:572:    id: `planner.outputFormat.${outputFormat.extensionId}.${outputFormat.id}.${route}.${routeRequirement.processId}.route-process-dependent`,
src/tools/video-editor/runtime/renderPlanner.ts:577:      ?? processStatusMessage(outputFormat.label, routeRequirement.processId, route, status),
src/tools/video-editor/runtime/renderPlanner.ts:578:    extensionId: outputFormat.extensionId,
src/tools/video-editor/runtime/renderPlanner.ts:579:    contributionId: outputFormat.id,
src/tools/video-editor/runtime/renderPlanner.ts:582:      outputFormatId: outputFormat.id,
src/tools/video-editor/runtime/renderPlanner.ts:583:      outputLabel: outputFormat.label,
src/tools/video-editor/runtime/renderPlanner.ts:637:  outputFormat: VideoEditorOutputFormatDescriptor,
src/tools/video-editor/runtime/renderPlanner.ts:640:  const availableRoutes = outputFormat.availableRoutes.length > 0
src/tools/video-editor/runtime/renderPlanner.ts:641:    ? outputFormat.availableRoutes
src/tools/video-editor/runtime/renderPlanner.ts:642:    : (outputFormat.requiresRender ? (['sidecar-export'] as const) : ([] as const));
src/tools/video-editor/runtime/renderPlanner.ts:645:    addRouteSetValue(acc.routeOutputFormatIds, route, outputFormat.id);
src/tools/video-editor/runtime/renderPlanner.ts:648:  for (const requirement of outputFormat.capabilities?.capabilityRequirements ?? []) {
src/tools/video-editor/runtime/renderPlanner.ts:652:  for (const routeRequirement of outputFormat.routeRequirements) {
src/tools/video-editor/runtime/renderPlanner.ts:659:      const routeBlocker = routeRequirementBlocker(outputFormat, routeRequirement, route, status);
src/tools/video-editor/runtime/renderPlanner.ts:669:  for (const requirement of outputFormat.processRequirements) {
src/tools/video-editor/runtime/renderPlanner.ts:674:      const blocker = processRequirementBlocker(outputFormat, route, requirement, status);
src/tools/video-editor/runtime/renderPlanner.ts:684:  for (const blocker of outputFormat.blockers) {
src/tools/video-editor/runtime/renderPlanner.ts:687:  acc.nextActions.push(...outputFormat.nextActions);
src/tools/video-editor/runtime/renderPlanner.ts:692:  outputFormat: VideoEditorOutputFormatDescriptor | undefined,
src/tools/video-editor/runtime/renderPlanner.ts:695:  if (!outputFormat) return;
src/tools/video-editor/runtime/renderPlanner.ts:699:  const availableRoutes = outputFormat.availableRoutes.length > 0
src/tools/video-editor/runtime/renderPlanner.ts:700:    ? outputFormat.availableRoutes
src/tools/video-editor/runtime/renderPlanner.ts:701:    : (outputFormat.requiresRender ? ([] as const) : (['browser-export'] as const));
src/tools/video-editor/runtime/renderPlanner.ts:707:      id: `planner.outputFormat.${outputFormat.extensionId}.${outputFormat.id}.${route}.route-unsupported`,
src/tools/video-editor/runtime/renderPlanner.ts:711:      message: `Output format "${outputFormat.label}" is not available on ${route}.`,
src/tools/video-editor/runtime/renderPlanner.ts:712:      extensionId: outputFormat.extensionId,
src/tools/video-editor/runtime/renderPlanner.ts:713:      contributionId: outputFormat.id,
src/tools/video-editor/runtime/renderPlanner.ts:716:        outputFormatId: outputFormat.id,
src/tools/video-editor/runtime/renderPlanner.ts:746:  return new Map((statuses ?? []).map((status) => [status.materialRefId, status]));
src/tools/video-editor/runtime/renderPlanner.ts:749:function materializeAction(
src/tools/video-editor/runtime/renderPlanner.ts:761:function materialBlockerReason(
src/tools/video-editor/runtime/renderPlanner.ts:762:  materialRef: RenderMaterialRef,
src/tools/video-editor/runtime/renderPlanner.ts:765:  if (status?.state === 'missing') return 'missing-material';
src/tools/video-editor/runtime/renderPlanner.ts:766:  if (status?.state === 'stale') return 'materialization-failed';
src/tools/video-editor/runtime/renderPlanner.ts:768:  if (status?.state === 'unbaked') return materialRef.determinism;
src/tools/video-editor/runtime/renderPlanner.ts:769:  if (materialRef.determinism === 'live-unbaked' || materialRef.determinism === 'process-dependent') {
src/tools/video-editor/runtime/renderPlanner.ts:770:    return materialRef.determinism;
src/tools/video-editor/runtime/renderPlanner.ts:777:  materialRef: RenderMaterialRef,
src/tools/video-editor/runtime/renderPlanner.ts:778:  materialStatusById: ReadonlyMap<string, RenderPlannerMaterialStatus>,
src/tools/video-editor/runtime/renderPlanner.ts:780:  addRouteValue(acc.routeDeterminism, 'browser-export', materialRef.determinism);
src/tools/video-editor/runtime/renderPlanner.ts:781:  if (materialRef.replacementPolicy !== 'materialize-on-export') return;
src/tools/video-editor/runtime/renderPlanner.ts:783:  const status = materialStatusById.get(materialRef.id);
src/tools/video-editor/runtime/renderPlanner.ts:784:  const reason = materialBlockerReason(materialRef, status);
src/tools/video-editor/runtime/renderPlanner.ts:786:  const message = status?.message ?? `Material "${materialRef.id}" must be materialized before browser export.`;
src/tools/video-editor/runtime/renderPlanner.ts:788:    id: `planner.material.${materialRef.id}.browser-export.${reason}`,
src/tools/video-editor/runtime/renderPlanner.ts:793:    materialRefId: materialRef.id,
src/tools/video-editor/runtime/renderPlanner.ts:794:    extensionId: materialRef.producerExtensionId,
src/tools/video-editor/runtime/renderPlanner.ts:796:      source: 'material-ref',
src/tools/video-editor/runtime/renderPlanner.ts:797:      mediaKind: materialRef.mediaKind,
src/tools/video-editor/runtime/renderPlanner.ts:798:      locatorKind: materialRef.locator.kind,
src/tools/video-editor/runtime/renderPlanner.ts:799:      replacementPolicy: materialRef.replacementPolicy,
src/tools/video-editor/runtime/renderPlanner.ts:800:      determinism: materialRef.determinism,
src/tools/video-editor/runtime/renderPlanner.ts:801:      materialState: status?.state ?? 'unbaked',
src/tools/video-editor/runtime/renderPlanner.ts:806:  acc.nextActions.push(materializeAction(`Materialize ${materialRef.id}`, message));
src/tools/video-editor/runtime/renderPlanner.ts:816:        ? 'missing-material'
src/tools/video-editor/runtime/renderPlanner.ts:817:        : 'materialization-failed';
src/tools/video-editor/runtime/renderPlanner.ts:825:        materialRefId: pass.materialRefId,
src/tools/video-editor/runtime/renderPlanner.ts:840:      acc.nextActions.push(materializeAction(`Materialize ${group.id}:${pass.passName}`, message));
src/tools/video-editor/runtime/renderPlanner.ts:876:  const outputFormatIds = Object.freeze([...(acc.routeOutputFormatIds.get(route) ?? new Set())].sort());
src/tools/video-editor/runtime/renderPlanner.ts:896:    outputFormatIds,
src/tools/video-editor/runtime/renderPlanner.ts:920:  const shaderComposition = diagnoseSnapshotShaderComposition(input.snapshot);
src/tools/video-editor/runtime/renderPlanner.ts:921:  const requirements = input.requirements ?? (shaderComposition.snapshot
src/tools/video-editor/runtime/renderPlanner.ts:922:    ? getCapabilityRequirements(shaderComposition.snapshot)
src/tools/video-editor/runtime/renderPlanner.ts:924:  const outputFormats = input.outputFormats ?? input.extensionRuntime?.outputFormats ?? [];
src/tools/video-editor/runtime/renderPlanner.ts:926:  const shaders = input.shaders ?? input.extensionRuntime?.shaders ?? [];
src/tools/video-editor/runtime/renderPlanner.ts:929:  const shaderBySourceRef = createShaderDescriptorMap(shaders);
src/tools/video-editor/runtime/renderPlanner.ts:930:  const materialStatusById = createMaterialStatusMap(input.materialStatuses);
src/tools/video-editor/runtime/renderPlanner.ts:931:  const requestedOutputFormat = input.request?.outputFormatId
src/tools/video-editor/runtime/renderPlanner.ts:932:    ? outputFormats.find((format) => format.id === input.request?.outputFormatId)
src/tools/video-editor/runtime/renderPlanner.ts:936:    const shaderDescriptor = isShaderMaterializerRequirement(requirement)
src/tools/video-editor/runtime/renderPlanner.ts:937:      ? shaderBySourceRef.get(shaderDescriptorKey(
src/tools/video-editor/runtime/renderPlanner.ts:943:      shaderDescriptor
src/tools/video-editor/runtime/renderPlanner.ts:944:      && shaderMaterializerSupportsRoute(shaderDescriptor, requirement, processById)
src/tools/video-editor/runtime/renderPlanner.ts:946:      collectShaderMaterializerRequirement(acc, requirement, shaderDescriptor, processStatusById);
src/tools/video-editor/runtime/renderPlanner.ts:952:  for (const outputFormat of outputFormats) {
src/tools/video-editor/runtime/renderPlanner.ts:953:    if (input.request?.outputFormatId && input.request.outputFormatId !== outputFormat.id) continue;
src/tools/video-editor/runtime/renderPlanner.ts:954:    collectOutputFormat(acc, outputFormat, processStatusById);
src/tools/video-editor/runtime/renderPlanner.ts:960:  for (const materialRef of input.materialRefs ?? []) {
src/tools/video-editor/runtime/renderPlanner.ts:961:    collectMaterialRef(acc, materialRef, materialStatusById);
src/tools/video-editor/runtime/renderPlanner.ts:964:  acc.findings.push(...shaderComposition.findings);
src/tools/video-editor/runtime/renderPlanner.ts:967:  if (input.request?.outputFormatId && !outputFormats.some((format) => format.id === input.request?.outputFormatId)) {
src/tools/video-editor/runtime/renderPlanner.ts:969:      id: `planner.outputFormat.${input.request.outputFormatId}.missing`,
src/tools/video-editor/runtime/renderPlanner.ts:973:      message: `Output format "${input.request.outputFormatId}" is not registered.`,
src/tools/video-editor/runtime/renderPlanner.ts:974:      contributionId: input.request.outputFormatId,
src/tools/video-editor/runtime/renderPlanner.ts:977:        outputFormatId: input.request.outputFormatId,
src/tools/video-editor/runtime/outputFormatRegistry.ts:2: * Compile-only output format registry and execution.
src/tools/video-editor/runtime/outputFormatRegistry.ts:4: * Manages registered compile-only output format handlers and executes them
src/tools/video-editor/runtime/outputFormatRegistry.ts:11: * @module outputFormatRegistry
src/tools/video-editor/runtime/outputFormatRegistry.ts:26:} from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/runtime/outputFormatRegistry.ts:33: * A registered compile-only output format entry.
src/tools/video-editor/runtime/outputFormatRegistry.ts:50: * Immutable registry of compile-only output format entries keyed by format ID.
src/tools/video-editor/runtime/outputFormatRegistry.ts:59: * Create a compile-only output format registry from a list of entries.
src/tools/video-editor/runtime/outputFormatRegistry.ts:83: * Options for executing a compile-only output format.
src/tools/video-editor/runtime/outputFormatRegistry.ts:86:  /** The output format contribution ID to execute. */
src/tools/video-editor/runtime/outputFormatRegistry.ts:99: * The result of executing a compile-only output format.
src/tools/video-editor/runtime/outputFormatRegistry.ts:115: * Execute a compile-only output format handler.
src/tools/video-editor/runtime/outputFormatRegistry.ts:126: * @param registry - The compile-only output format registry.
src/tools/video-editor/runtime/outputFormatRegistry.ts:161:      outputFormatId: options.formatId,
src/tools/video-editor/runtime/outputFormatRegistry.ts:175:    assertFinalArtifactHasManifest(artifact, 'outputFormatRegistry.executeCompileOnlyOutput');
src/tools/video-editor/runtime/outputFormatRegistry.ts:191:    outputFormatId: options.formatId,
src/tools/video-editor/runtime/outputFormatRegistry.ts:206:  assertFinalArtifactHasManifest(artifact, 'outputFormatRegistry.executeCompileOnlyOutput');
src/tools/video-editor/runtime/outputFormatRegistry.ts:216: * Execute a compile-only output format synchronously.
src/tools/video-editor/runtime/outputFormatRegistry.ts:249:      outputFormatId: options.formatId,
src/tools/video-editor/runtime/outputFormatRegistry.ts:263:    assertFinalArtifactHasManifest(artifact, 'outputFormatRegistry.executeCompileOnlyOutputSync');
src/tools/video-editor/runtime/outputFormatRegistry.ts:287:    outputFormatId: options.formatId,
src/tools/video-editor/runtime/outputFormatRegistry.ts:302:  assertFinalArtifactHasManifest(artifact, 'outputFormatRegistry.executeCompileOnlyOutputSync');
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:109:  /** M5: Planner-compatible blocker diagnostics published by renderPlanner. */
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:124:  /** M5: Supported renderability capability declarations across effect records. */
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:126:  /** M5: Blocked renderability capability declarations across effect records. */
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:128:  /** M5: Unknown renderability capability declarations across effect records. */
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:375:      const capability = record.renderability.capabilities.find((item) => item.route === 'browser-export');
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:378:    const effectCapabilities = effectRegistrySnapshot.records.flatMap((record) => record.renderability.capabilities);
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:388:      for (const cap of record.renderability.capabilities) {
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:651:          <div className="flex items-center gap-1" data-video-editor-effect-renderability-summary="supported">
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:657:          <div className="flex items-center gap-1" data-video-editor-effect-renderability-summary="blocked">
src/tools/video-editor/runtime/ExtensionStatusDrawer.tsx:664:            <div className="flex items-center gap-1" data-video-editor-effect-renderability-summary="unknown">
src/sdk/extensionSettingsService.ts:25: *  1. localStorage value (legacy, most-recent synchronous write)
src/sdk/extensionSettingsService.ts:351:    // Priority 1: localStorage (legacy, most-recent synchronous write)
src/tools/video-editor/runtime/agentToolContracts.test.ts:447:      'material/artifact',
src/tools/video-editor/runtime/agentToolContracts.test.ts:465:      'material/artifact',
src/tools/video-editor/runtime/agentToolContracts.test.ts:534:  it('accepts a valid material/artifact result', () => {
src/tools/video-editor/runtime/agentToolContracts.test.ts:536:      family: 'material/artifact',
src/tools/video-editor/runtime/agentToolContracts.test.ts:719:  // material/artifact family errors
src/tools/video-editor/runtime/agentToolContracts.test.ts:720:  it('errors on material/artifact result without refs', () => {
src/tools/video-editor/runtime/agentToolContracts.test.ts:722:      family: 'material/artifact',
src/tools/video-editor/runtime/agentToolContracts.test.ts:724:    expect(codes(diags)).toContain('agent-tool/material-missing-refs');
src/tools/video-editor/runtime/agentToolContracts.test.ts:727:  it('warns on material/artifact result with empty refs', () => {
src/tools/video-editor/runtime/agentToolContracts.test.ts:729:      family: 'material/artifact',
src/tools/video-editor/runtime/agentToolContracts.test.ts:732:    expect(codes(diags)).toContain('agent-tool/material-empty-refs');
src/tools/video-editor/runtime/shaderRegistrationService.ts:2: * Shared host-owned service factory for WebGL shader registration.
src/tools/video-editor/runtime/shaderRegistrationService.ts:20:import { validateShaderSchemas } from '@/tools/video-editor/shaders/compile/diagnostics.ts';
src/tools/video-editor/runtime/shaderRegistrationService.ts:21:import type { ShaderEffectRegistry } from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/runtime/shaderRegistrationService.ts:25:} from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/runtime/shaderRegistrationService.ts:30:} from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/runtime/shaderRegistrationService.ts:36:    (contribution): contribution is ShaderContribution => contribution.kind === 'shader',
src/tools/video-editor/runtime/shaderRegistrationService.ts:44:function materializerRoutes(
src/tools/video-editor/runtime/shaderRegistrationService.ts:45:  materializer: ShaderMaterializerDescriptor | undefined,
src/tools/video-editor/runtime/shaderRegistrationService.ts:47:  return new Set((materializer?.routes ?? []) as readonly RenderRoute[]);
src/tools/video-editor/runtime/shaderRegistrationService.ts:53:  materializer: ShaderMaterializerDescriptor | undefined,
src/tools/video-editor/runtime/shaderRegistrationService.ts:55:  const routes = materializerRoutes(materializer);
src/tools/video-editor/runtime/shaderRegistrationService.ts:65:    const materializerSupportsRoute = routes.has(route);
src/tools/video-editor/runtime/shaderRegistrationService.ts:68:      status: materializerSupportsRoute ? 'supported' : 'blocked',
src/tools/video-editor/runtime/shaderRegistrationService.ts:69:      determinism: materializerSupportsRoute ? 'process-dependent' : 'preview-only',
src/tools/video-editor/runtime/shaderRegistrationService.ts:70:      ...(materializerSupportsRoute
src/tools/video-editor/runtime/shaderRegistrationService.ts:73:            blockerReason: 'missing-material' as const,
src/tools/video-editor/runtime/shaderRegistrationService.ts:75:              `Shader "${contribution.shaderId}" is preview-only until extension "${extensionId}" ` +
src/tools/video-editor/runtime/shaderRegistrationService.ts:76:              'declares a materializer route that can produce RenderMaterial.',
src/tools/video-editor/runtime/shaderRegistrationService.ts:90:  readonly shaderRegistry: ShaderEffectRegistry;
src/tools/video-editor/runtime/shaderRegistrationService.ts:97:  const { extension, shaderRegistry, diagnosticsService } = params;
src/tools/video-editor/runtime/shaderRegistrationService.ts:99:  const shaderContributions = getShaderContributions(extension.manifest);
src/tools/video-editor/runtime/shaderRegistrationService.ts:102:  for (const contribution of shaderContributions) {
src/tools/video-editor/runtime/shaderRegistrationService.ts:103:    contributionsByShaderId.set(contribution.shaderId, contribution);
src/tools/video-editor/runtime/shaderRegistrationService.ts:116:    shaderId: string,
src/tools/video-editor/runtime/shaderRegistrationService.ts:120:    const contribution = contributionsByShaderId.get(shaderId);
src/tools/video-editor/runtime/shaderRegistrationService.ts:124:        'shaders/undeclared-shader',
src/tools/video-editor/runtime/shaderRegistrationService.ts:125:        `Shader "${shaderId}" is not declared as a ShaderContribution in extension "${extensionId}". ` +
src/tools/video-editor/runtime/shaderRegistrationService.ts:126:          `Declared shader IDs: [${[...contributionsByShaderId.keys()].join(', ') || '(none)'}].`,
src/tools/video-editor/runtime/shaderRegistrationService.ts:127:        { shaderId, extensionId },
src/tools/video-editor/runtime/shaderRegistrationService.ts:137:        shaderId,
src/tools/video-editor/runtime/shaderRegistrationService.ts:149:    const materializer = options?.materializer ?? contribution.materializer;
src/tools/video-editor/runtime/shaderRegistrationService.ts:152:      shaderId,
src/tools/video-editor/runtime/shaderRegistrationService.ts:154:      label: options?.label ?? contribution.label ?? shaderId,
src/tools/video-editor/runtime/shaderRegistrationService.ts:161:      materializer,
src/tools/video-editor/runtime/shaderRegistrationService.ts:164:      renderability: buildShaderRenderability(extensionId, contribution, materializer),
src/tools/video-editor/runtime/shaderRegistrationService.ts:169:    const handle = shaderRegistry.register(record);
src/tools/video-editor/runtime/shaderRegistrationService.ts:172:      'shaders/registered',
src/tools/video-editor/runtime/shaderRegistrationService.ts:173:      `Shader "${shaderId}" registered for extension "${extensionId}"${hasSchemaErrors ? ' with schema errors' : ''}.`,
src/tools/video-editor/runtime/shaderRegistrationService.ts:175:        shaderId,
src/tools/video-editor/runtime/shaderRegistrationService.ts:193:            'shaders/dispose-failed',
src/tools/video-editor/runtime/shaderRegistrationService.ts:194:            `Failed to dispose shader "${shaderId}" for extension "${extensionId}": ${String(error)}`,
src/tools/video-editor/runtime/shaderRegistrationService.ts:195:            { shaderId, extensionId, error: String(error) },
src/tools/video-editor/runtime/shaderRegistrationService.ts:201:          'shaders/disposed',
src/tools/video-editor/runtime/shaderRegistrationService.ts:202:          `Shader "${shaderId}" disposed for extension "${extensionId}".`,
src/tools/video-editor/runtime/shaderRegistrationService.ts:203:          { shaderId, extensionId },
src/tools/video-editor/runtime/exportGuard.ts:43:} from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/runtime/exportGuard.ts:45:  shaderMissingMaterializerBlockerMessage,
src/tools/video-editor/runtime/exportGuard.ts:47:} from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/runtime/exportGuard.ts:217: * authoritative; extension-declared IDs are collected but NOT treated as
src/tools/video-editor/runtime/exportGuard.ts:330:  if (isTimelineShaderMetadata(config.app?.shaderPostprocess, 'postprocess')) return true;
src/tools/video-editor/runtime/exportGuard.ts:331:  return config.clips.some((clip) => isTimelineShaderMetadata(clip.app?.shader, 'clip'));
src/tools/video-editor/runtime/exportGuard.ts:341:  readonly shaderId: string;
src/tools/video-editor/runtime/exportGuard.ts:351:    && typeof (value as Record<string, unknown>).shaderId === 'string'
src/tools/video-editor/runtime/exportGuard.ts:364:    const shader = isTimelineShaderMetadata(clip.app?.shader, 'clip') ? clip.app.shader : undefined;
src/tools/video-editor/runtime/exportGuard.ts:365:    if (!shader || shader.enabled === false) continue;
src/tools/video-editor/runtime/exportGuard.ts:367:      shaderId: shader.shaderId,
src/tools/video-editor/runtime/exportGuard.ts:368:      extensionId: shader.extensionId,
src/tools/video-editor/runtime/exportGuard.ts:369:      contributionId: shader.contributionId,
src/tools/video-editor/runtime/exportGuard.ts:375:  const postprocessShader = isTimelineShaderMetadata(config.app?.shaderPostprocess, 'postprocess')
src/tools/video-editor/runtime/exportGuard.ts:376:    ? config.app.shaderPostprocess
src/tools/video-editor/runtime/exportGuard.ts:380:      shaderId: postprocessShader.shaderId,
src/tools/video-editor/runtime/exportGuard.ts:393:    readonly shaderId: string;
src/tools/video-editor/runtime/exportGuard.ts:403:    const message = shaderMissingMaterializerBlockerMessage(input.shaderId, input.scope, input.clipId);
src/tools/video-editor/runtime/exportGuard.ts:404:    const id = `export.shader.${input.scope}.${input.clipId ?? 'timeline'}.${input.shaderId}.${route}.missing-materializer`;
src/tools/video-editor/runtime/exportGuard.ts:406:      shaderId: input.shaderId,
src/tools/video-editor/runtime/exportGuard.ts:407:      shaderScope: input.scope,
src/tools/video-editor/runtime/exportGuard.ts:414:      code: 'export/unrenderable-shader',
src/tools/video-editor/runtime/exportGuard.ts:425:      reason: 'missing-material',
src/tools/video-editor/runtime/exportGuard.ts:431:        shaderId: input.shaderId,
src/tools/video-editor/runtime/exportGuard.ts:432:        shaderScope: input.scope,
src/tools/video-editor/runtime/exportGuard.ts:433:        source: 'timeline-shader-metadata',
src/tools/video-editor/runtime/exportGuard.ts:441:      reason: 'missing-material',
src/tools/video-editor/runtime/exportGuard.ts:730:    const capability = record.renderability.capabilities.find((cap) => cap.route === route);
src/tools/video-editor/runtime/exportGuard.ts:812:  return record.renderability.blockers?.find((blocker) => blocker.route === route)?.reason;
src/tools/video-editor/runtime/exportGuard.ts:902:    const capability = record.renderability.capabilities.find((cap) => cap.route === route);
src/tools/video-editor/runtime/exportGuard.ts:1004:  return record.renderability.blockers?.find((blocker) => blocker.route === route)?.reason;
src/tools/video-editor/runtime/exportGuard.ts:1094:    const capability = record.renderability.capabilities.find((cap) => cap.route === route);
src/tools/video-editor/runtime/exportGuard.ts:1174:  return record.renderability.blockers?.find((blocker) => blocker.route === route)?.reason;
src/tools/video-editor/lib/timeline-data.ts:92:  'output-composition': '#e06c75',
src/tools/video-editor/lib/timeline-data.ts:488:  legacyUrlResolver?: UrlResolver,
src/tools/video-editor/lib/timeline-data.ts:512:    ?? legacyUrlResolver
src/tools/video-editor/lib/timeline-data.ts:543:  const legacy = (providerOrResolver as { loadAssetProfile?: (id: string) => Promise<{ transcript?: { segments?: TranscriptSegment[] } } | null> }).loadAssetProfile;
src/tools/video-editor/lib/timeline-data.ts:544:  const profile = legacy ? await legacy(assetKey) : null;
src/tools/video-editor/runtime/extensionLoader.test.ts:472:  it('optional dependency from legacy optional flag', () => {
src/sdk/index.test.ts:323:    expect(contributionKindNotYetBridged('outputFormat')).toBe('M6');
src/sdk/index.test.ts:333:  it('outputFormat is typed but execution is reserved (returns M6)', () => {
src/sdk/index.test.ts:334:    expect(contributionKindNotYetBridged('outputFormat')).toBe('M6');
src/sdk/index.test.ts:342:    const bridged = contributionKindNotYetBridged('outputFormat');
src/sdk/index.test.ts:349:    expect(contributionKindNotYetBridged('shader')).toBeNull();
src/sdk/index.test.ts:354:  it('shader is M13-active as its own contribution kind', () => {
src/sdk/index.test.ts:355:    expect(CONTRIBUTION_KIND_MILESTONE.shader).toBe('M13');
src/sdk/index.test.ts:356:    expect(contributionKindNotYetBridged('shader')).toBeNull();
src/sdk/index.test.ts:361:    expect(CONTRIBUTION_KIND_MILESTONE.outputFormat).toBe('M6');
src/sdk/index.test.ts:373:    expect(contributionKindNotYetBridged('shader')).toBeNull();
src/sdk/index.test.ts:378:// M13: defineExtension accepts dedicated shader contributions
src/sdk/index.test.ts:381:describe('M13: shader SDK contracts', () => {
src/sdk/index.test.ts:387:  const shaderContribution: ShaderContribution = {
src/sdk/index.test.ts:388:    id: 'clip-glow-shader' as any,
src/sdk/index.test.ts:389:    kind: 'shader',
src/sdk/index.test.ts:390:    shaderId: 'shader.clipGlow',
src/sdk/index.test.ts:436:  it('preserves shader contribution metadata without normalizing to effect', () => {
src/sdk/index.test.ts:439:        id: 'com.example.shader' as any,
src/sdk/index.test.ts:442:        contributions: [shaderContribution],
src/sdk/index.test.ts:447:    expect(contribution.kind).toBe('shader');
src/sdk/index.test.ts:448:    expect(contribution.shaderId).toBe('shader.clipGlow');
src/sdk/index.test.ts:454:  it('ctx.shaders is a dedicated registration service and does not call ctx.effects', () => {
src/sdk/index.test.ts:457:        id: 'com.example.shader-service' as any,
src/sdk/index.test.ts:460:        contributions: [shaderContribution],
src/sdk/index.test.ts:464:    const shaderCalls: string[] = [];
src/sdk/index.test.ts:465:    const shaderService: ShaderRegistrationService = {
src/sdk/index.test.ts:466:      registerShader(shaderId, source) {
src/sdk/index.test.ts:467:        shaderCalls.push(`${shaderId}:${source.kind}`);
src/sdk/index.test.ts:485:      shaderService,
src/sdk/index.test.ts:488:    const handle = ctx.shaders.registerShader('shader.clipGlow', inlineShaderSource);
src/sdk/index.test.ts:490:    expect(shaderCalls).toEqual(['shader.clipGlow:inline']);
src/sdk/index.test.ts:494:  it('unwired shader registration reports shader diagnostics, not effect diagnostics', () => {
src/sdk/index.test.ts:497:        id: 'com.example.shader-unwired' as any,
src/sdk/index.test.ts:500:        contributions: [shaderContribution],
src/sdk/index.test.ts:505:    ctx.shaders.registerShader('shader.clipGlow', inlineShaderSource);
src/sdk/index.test.ts:508:    expect(codes).toContain('shaders/not-wired');
src/sdk/index.test.ts:514:// M6: defineExtension accepts parser/outputFormat/searchProvider contributions
src/sdk/index.test.ts:539:  it('accepts a manifest with a compile-only outputFormat contribution', () => {
src/sdk/index.test.ts:548:            kind: 'outputFormat',
src/sdk/index.test.ts:558:    expect(ext.manifest.contributions![0].kind).toBe('outputFormat');
src/sdk/index.test.ts:562:  it('accepts a manifest with a render-dependent outputFormat contribution (reserved)', () => {
src/sdk/index.test.ts:571:            kind: 'outputFormat',
src/sdk/index.test.ts:581:    expect(ext.manifest.contributions![0].kind).toBe('outputFormat');
src/sdk/index.test.ts:621:            kind: 'outputFormat',
src/sdk/index.test.ts:636:    expect(ext.manifest.contributions![1].kind).toBe('outputFormat');
src/sdk/index.test.ts:656:              kind: 'outputFormat',
src/sdk/index.test.ts:676:            kind: 'outputFormat',
src/sdk/index.test.ts:685:    expect(ext.manifest.contributions![0].kind).toBe('outputFormat');
src/sdk/index.test.ts:687:    expect(contributionKindNotYetBridged('outputFormat')).toBe('M6');
src/sdk/index.test.ts:731:      renderability: {},
src/sdk/index.test.ts:870:  it('creative.materials throws with M6 milestone', () => {
src/sdk/index.test.ts:871:    expect(() => ctx.creative.materials).toThrow(ExtensionNotImplementedError);
src/sdk/index.test.ts:873:      ctx.creative.materials;
src/sdk/index.test.ts:875:      expect((err as ExtensionNotImplementedError).feature).toBe('materials');
src/sdk/index.test.ts:1300:      'shaders',
src/sdk/index.test.ts:1441:      'materials',
src/sdk/index.test.ts:1489:      'materials',
src/sdk/index.test.ts:1735:      'render-material',
src/sdk/index.test.ts:2411:  const materialRef = {
src/sdk/index.test.ts:2422:      kind: 'outputFormat',
src/sdk/index.test.ts:2430:      kind: 'outputFormat',
src/sdk/index.test.ts:2449:  it('keeps existing manifest acceptance for output formats and adds process contributions', () => {
src/sdk/index.test.ts:2458:            kind: 'outputFormat',
src/sdk/index.test.ts:2483:                  outputKinds: ['material', 'sidecar'],
src/sdk/index.test.ts:2522:      outputFormatId: 'show-control',
src/sdk/index.test.ts:2523:      consumedMaterialRefs: [materialRef],
src/sdk/index.test.ts:2576:      materialRefId: 'mat-main',
src/sdk/index.test.ts:2590:      operations: [{ id: 'render-pass', label: 'Render Pass', outputKinds: ['material', 'sidecar'] }],
src/sdk/index.test.ts:2611:      inputMaterialRefs: [materialRef],
src/sdk/index.test.ts:2624:          ...materialRef,
src/sdk/index.test.ts:2847:  it('warns on legacy migration shape in dev mode', () => {
src/sdk/index.test.ts:2855:    expect(result.warnings.some(w => w.code === 'manifest/legacy-migration-shape')).toBe(true);
src/sdk/index.test.ts:2858:  it('errors on legacy migration shape in installed mode', () => {
src/sdk/index.test.ts:2868:    expect(result.errors.some(e => e.code === 'manifest/legacy-migration-shape')).toBe(true);
src/sdk/index.test.ts:3096:    // outputFormat is in KNOWN_CONTRIBUTION_KINDS but contributionKindNotYetBridged('outputFormat') === 'M6'
src/sdk/index.test.ts:3100:        { id: 'deferred-ok' as any, kind: 'outputFormat' as any },
src/sdk/index.test.ts:4004:          outputKinds: ['material', 'sidecar', 'diagnostic'],
src/sdk/index.test.ts:4054:  it('SDK exports renderability constants via re-exports', () => {
src/sdk/index.test.ts:4056:    // re-exported from tools/video-editor/runtime/renderability.ts.
src/tools/video-editor/runtime/extensionLifecycle.ts:21:import type { LiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
src/tools/video-editor/runtime/extensionLifecycle.ts:493:  /** The live data registry associated with this host (if any). */
src/tools/video-editor/runtime/extensionLifecycle.ts:494:  readonly liveDataRegistry: LiveDataRegistry | undefined;
src/tools/video-editor/runtime/extensionLifecycle.ts:500: * @param liveDataRegistry  Optional live data registry. When provided, the host
src/tools/video-editor/runtime/extensionLifecycle.ts:505: *   NOTE: The live data registry is future-only scaffolding. It is not yet
src/tools/video-editor/runtime/extensionLifecycle.ts:510:  liveDataRegistry?: LiveDataRegistry,
src/tools/video-editor/runtime/extensionLifecycle.ts:566:          if (liveDataRegistry && !liveDataRegistry.isDisposed) {
src/tools/video-editor/runtime/extensionLifecycle.ts:568:              liveDataRegistry.disposeExtensionSources(oldId);
src/tools/video-editor/runtime/extensionLifecycle.ts:594:        if (liveDataRegistry && !liveDataRegistry.isDisposed) {
src/tools/video-editor/runtime/extensionLifecycle.ts:596:            liveDataRegistry.disposeExtensionSources(removedId);
src/tools/video-editor/runtime/extensionLifecycle.ts:650:    if (liveDataRegistry && !liveDataRegistry.isDisposed) {
src/tools/video-editor/runtime/extensionLifecycle.ts:653:          liveDataRegistry.disposeExtensionSources(id);
src/tools/video-editor/runtime/extensionLifecycle.ts:672:    get liveDataRegistry() {
src/tools/video-editor/runtime/extensionLifecycle.ts:673:      return liveDataRegistry;
src/tools/video-editor/runtime/renderability.test.ts:24:} from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/runtime/renderability.test.ts:33:} from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/runtime/renderability.test.ts:35:function materialRef(id: string, uri: string): RenderMaterialRef {
src/tools/video-editor/runtime/renderability.test.ts:44:    producerExtensionId: 'com.example.materials',
src/tools/video-editor/runtime/renderability.test.ts:88:describe('shared renderability contracts', () => {
src/tools/video-editor/runtime/renderability.test.ts:123:      'missing-material',
src/tools/video-editor/runtime/renderability.test.ts:124:      'materialization-failed',
src/tools/video-editor/runtime/renderability.test.ts:160:    const renderability: ContributionRenderability = {
src/tools/video-editor/runtime/renderability.test.ts:167:    expect(renderability).toMatchObject({
src/tools/video-editor/runtime/renderability.test.ts:176:  it('separates render materials from final artifacts and bake contracts', () => {
src/tools/video-editor/runtime/renderability.test.ts:178:      id: 'material.image.1',
src/tools/video-editor/runtime/renderability.test.ts:186:      producerExtensionId: 'com.example.materials',
src/tools/video-editor/runtime/renderability.test.ts:192:    const material: RenderMaterial = {
src/tools/video-editor/runtime/renderability.test.ts:216:      producerExtensionId: 'com.example.materials',
src/tools/video-editor/runtime/renderability.test.ts:235:    expect(material.locator.kind).toBe('asset-registry');
src/tools/video-editor/runtime/renderability.test.ts:247:  it('serializes manifests stably across object key, material, sidecar, and diagnostic order', () => {
src/tools/video-editor/runtime/renderability.test.ts:269:      outputFormatId: 'dataset-show-control',
src/tools/video-editor/runtime/renderability.test.ts:286:      consumedMaterialRefs: [materialRef('mat-z', 'asset://z'), materialRef('mat-a', 'asset://a')],
src/tools/video-editor/runtime/renderability.test.ts:292:      consumedMaterialRefs: [materialRef('mat-a', 'asset://a'), materialRef('mat-z', 'asset://z')],
src/tools/video-editor/runtime/renderability.test.ts:313:      outputFormatId: 'metadata-json',
src/tools/video-editor/runtime/renderability.test.ts:314:      consumedMaterialRefs: [materialRef('mat-main', 'asset://main')],
src/tools/video-editor/runtime/renderability.test.ts:370:  it('preserves route metadata, determinism status, producer fields, and consumed materials', () => {
src/tools/video-editor/runtime/renderability.test.ts:389:        materialRef('mat-background', 'asset://background'),
src/tools/video-editor/runtime/renderability.test.ts:390:        materialRef('mat-foreground', 'asset://foreground'),
src/tools/video-editor/runtime/renderability.test.ts:433:      outputFormatId: 'metadata-json',
src/tools/video-editor/runtime/renderability.test.ts:443:      'material.asset.asset-b',
src/tools/video-editor/runtime/renderability.test.ts:444:      'material.asset.asset-a',
src/tools/video-editor/runtime/renderability.test.ts:452:      outputFormatId: 'metadata-json',
src/tools/video-editor/runtime/renderability.test.ts:456:      'material.asset.asset-a',
src/tools/video-editor/runtime/renderability.test.ts:457:      'material.asset.asset-b',
src/tools/video-editor/runtime/renderability.test.ts:484:      'src/tools/video-editor/runtime/outputFormatRegistry.ts',
src/tools/video-editor/runtime/renderability.test.ts:485:      'src/tools/video-editor/runtime/renderability.ts',
src/tools/video-editor/runtime/renderability.test.ts:489:      if (relative === 'src/tools/video-editor/runtime/renderability.ts') return [];
src/tools/video-editor/runtime/extensionReferenceReport.ts:25:  | 'shader'
src/tools/video-editor/runtime/extensionReferenceReport.ts:157:    shader: 'shader',
src/tools/video-editor/runtime/extensionReferenceReport.ts:158:    shaders: 'shader',
src/tools/video-editor/runtime/extensionReferenceReport.ts:165:    liveDataSource: 'live-data-source',
src/tools/video-editor/runtime/extensionReferenceReport.ts:166:    liveDataSources: 'live-data-source',
src/tools/video-editor/runtime/liveMapping.test.ts:3:import { createLiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry';
src/tools/video-editor/lib/sha256.test.ts:530:// T9: Sync boundary — import/materialization/load must not hash synchronously
src/tools/video-editor/lib/sha256.test.ts:533:describe('sync boundary — no synchronous hashing in import/materialization/load', () => {
src/tools/video-editor/lib/sha256.test.ts:688:  // applyTimelineCommandEffect (materialization path)
src/tools/video-editor/runtime/extensionLoader.ts:242: * Builds a directed graph where edge A→B means A depends on B (any posture).
src/tools/video-editor/runtime/ContributionErrorBoundary.tsx:60:   * When no `recoveryKey` is given the boundary falls back to the legacy
src/tools/video-editor/runtime/ContributionErrorBoundary.tsx:194:    // Without a recoveryKey, fall back to the legacy children-change reset.
src/tools/video-editor/runtime/extensionSettings.ts:70: * (shader-specific vec2/vec3/vec4/bool/float/int/enum etc.) are not
src/tools/video-editor/runtime/extensionStateRepository.test.ts:450:      contributionRefs: ['cmd.run', 'effect.fade', 'shader.blur'],
src/tools/video-editor/runtime/extensionStateRepository.test.ts:458:    expect(entry.contributionRefs).toContain('shader.blur');
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:10: * - Shader uniform types map to compact shader controls where they do
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:11: *   not overlap legacy parameter widgets.
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:40:  | 'shader-number'; // Compact numeric shader uniform input
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:149:      + 'Bind textures through the host shader texture picker.',
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:233:    widgetType: 'shader-number',
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:241:    widgetType: 'shader-number',
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:297:    widgetType: 'shader-number',
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:305:    widgetType: 'shader-number',
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:339:    ['shader-scalar-path', {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:340:      path: 'shader-scalar-path',
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:363:    ['shader-vector-path', {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:364:      path: 'shader-vector-path',
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:380:    // Shader color uniforms use vec4 RGBA arrays; legacy parameter colors use hex strings.
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:381:    ['shader-color-vector-path', {
src/tools/video-editor/runtime/schemaCapabilityRegistry.ts:382:      path: 'shader-color-vector-path',
src/tools/video-editor/runtime/agentToolRegistry.ts:44:import type { LiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry';
src/tools/video-editor/runtime/agentToolRegistry.ts:187:  readonly liveDataRegistry?: LiveDataRegistry;
src/tools/video-editor/runtime/agentToolRegistry.ts:842:    const liveRegistry = config.liveDataRegistry;
src/tools/video-editor/runtime/agentToolRegistry.ts:847:        message: 'GenerationSession live delivery requires a live data registry.',
src/tools/video-editor/runtime/agentToolRegistry.ts:968:      // getSampleChannel is part of the typed contract, but legacy sessions may throw.
src/tools/video-editor/runtime/extensionSurface.test.ts:322:        { id: 'my-output' as any, kind: 'outputFormat', label: 'Output', requiresRender: false, outputExtension: 'json' },
src/tools/video-editor/runtime/extensionSurface.test.ts:345:      'outputFormat', 'process', 'searchProvider',
src/tools/video-editor/runtime/extensionSurface.test.ts:384:    const output = rt.inactiveReserved.find((r) => r.kind === 'outputFormat')!;
src/tools/video-editor/runtime/extensionSurface.test.ts:915:describe('normalizeExtensionRuntime — M6 output format contributions', () => {
src/tools/video-editor/runtime/extensionSurface.test.ts:916:  it('surfaces compile-only outputFormat as enabled in config.outputFormats', () => {
src/tools/video-editor/runtime/extensionSurface.test.ts:920:          { id: 'metadata-json' as any, kind: 'outputFormat', label: 'Metadata JSON', requiresRender: false, outputExtension: 'json', outputMimeType: 'application/json', description: 'Export metadata as JSON', order: 0 },
src/tools/video-editor/runtime/extensionSurface.test.ts:925:    expect(rt.config.outputFormats).toHaveLength(1);
src/tools/video-editor/runtime/extensionSurface.test.ts:926:    const of = rt.config.outputFormats[0];
src/tools/video-editor/runtime/extensionSurface.test.ts:938:  it('surfaces render-dependent outputFormat as planner-ready instead of permanently disabled', () => {
src/tools/video-editor/runtime/extensionSurface.test.ts:944:            kind: 'outputFormat',
src/tools/video-editor/runtime/extensionSurface.test.ts:964:    expect(rt.config.outputFormats).toHaveLength(1);
src/tools/video-editor/runtime/extensionSurface.test.ts:965:    const of = rt.config.outputFormats[0];
src/tools/video-editor/runtime/extensionSurface.test.ts:1008:  it('projects outputFormat into runtime.outputFormats (same as config)', () => {
src/tools/video-editor/runtime/extensionSurface.test.ts:1012:          { id: 'metadata-json' as any, kind: 'outputFormat', label: 'JSON', requiresRender: false, outputExtension: 'json' },
src/tools/video-editor/runtime/extensionSurface.test.ts:1017:    expect(rt.outputFormats).toBe(rt.config.outputFormats);
src/tools/video-editor/runtime/extensionSurface.test.ts:1020:  it('marks outputFormat as inactive reserved with M6 milestone', () => {
src/tools/video-editor/runtime/extensionSurface.test.ts:1024:          { id: 'metadata-json' as any, kind: 'outputFormat', label: 'JSON', requiresRender: false, outputExtension: 'json' },
src/tools/video-editor/runtime/extensionSurface.test.ts:1029:    const reserved = rt.inactiveReserved.filter((r) => r.kind === 'outputFormat');
src/tools/video-editor/runtime/extensionSurface.test.ts:1035:  it('emits info diagnostic for outputFormat', () => {
src/tools/video-editor/runtime/extensionSurface.test.ts:1039:          { id: 'metadata-json' as any, kind: 'outputFormat', label: 'JSON', requiresRender: false, outputExtension: 'json' },
src/tools/video-editor/runtime/extensionSurface.test.ts:1050:    expect(reserved!.kind).toBe('outputFormat');
src/tools/video-editor/runtime/extensionSurface.test.ts:1053:  it('orders output formats by extension order, then contribution order, then ID', () => {
src/tools/video-editor/runtime/extensionSurface.test.ts:1057:          { id: 'z-format' as any, kind: 'outputFormat', label: 'Z', requiresRender: false, outputExtension: 'z', order: 0 },
src/tools/video-editor/runtime/extensionSurface.test.ts:1058:          { id: 'a-format' as any, kind: 'outputFormat', label: 'A', requiresRender: false, outputExtension: 'a', order: 0 },
src/tools/video-editor/runtime/extensionSurface.test.ts:1065:          { id: 'early-format' as any, kind: 'outputFormat', label: 'Early', requiresRender: false, outputExtension: 'early', order: -10 },
src/tools/video-editor/runtime/extensionSurface.test.ts:1070:    expect(rt.config.outputFormats).toHaveLength(3);
src/tools/video-editor/runtime/extensionSurface.test.ts:1072:    const ids = rt.config.outputFormats.map((f) => f.id);
src/tools/video-editor/runtime/extensionSurface.test.ts:1076:  it('creates non-DEFAULT config when only outputFormat contributions exist', () => {
src/tools/video-editor/runtime/extensionSurface.test.ts:1080:          { id: 'metadata-json' as any, kind: 'outputFormat', label: 'JSON', requiresRender: false, outputExtension: 'json' },
src/tools/video-editor/runtime/extensionSurface.test.ts:1085:    // Config should NOT be DEFAULT because outputFormat descriptors need to be surfaced
src/tools/video-editor/runtime/extensionSurface.test.ts:1087:    expect(rt.config.outputFormats).toHaveLength(1);
src/tools/video-editor/runtime/extensionSurface.test.ts:1097:          { id: 'default-label-format' as any, kind: 'outputFormat', requiresRender: false, outputExtension: 'json' },
src/tools/video-editor/runtime/extensionSurface.test.ts:1102:    expect(rt.config.outputFormats[0].label).toBe('default-label-format');
src/tools/video-editor/runtime/extensionSurface.test.ts:1109:          { id: 'no-render-flag' as any, kind: 'outputFormat', outputExtension: 'json' },
src/tools/video-editor/runtime/extensionSurface.test.ts:1114:    expect(rt.config.outputFormats[0].requiresRender).toBe(false);
src/tools/video-editor/runtime/extensionSurface.test.ts:1115:    expect(rt.config.outputFormats[0].disabled).toBe(false);
src/tools/video-editor/runtime/extensionSurface.test.ts:1116:    expect(rt.config.outputFormats[0].availableRoutes).toEqual([]);
src/tools/video-editor/runtime/extensionSurface.test.ts:1117:    expect(rt.config.outputFormats[0].routeRequirements).toEqual([]);
src/tools/video-editor/runtime/extensionSurface.test.ts:1118:    expect(rt.config.outputFormats[0].processRequirements).toEqual([]);
src/tools/video-editor/runtime/extensionSurface.test.ts:1119:    expect(rt.config.outputFormats[0].blockers).toEqual([]);
src/tools/video-editor/runtime/extensionSurface.test.ts:1120:    expect(rt.config.outputFormats[0].nextActions).toEqual([]);
src/tools/video-editor/runtime/extensionSurface.test.ts:1127:          { id: 'missing-render' as any, kind: 'outputFormat', label: 'Broken Video', requiresRender: true, outputExtension: 'mp4' },
src/tools/video-editor/runtime/extensionSurface.test.ts:1132:    const of = rt.config.outputFormats[0];
src/tools/video-editor/runtime/extensionSurface.test.ts:1385:  it('respects extension order for M6-reserved contributions too (outputFormats)', () => {
src/tools/video-editor/runtime/extensionSurface.test.ts:1389:          { id: 'a-output' as any, kind: 'outputFormat', label: 'A', requiresRender: false, outputExtension: 'a', order: 100 },
src/tools/video-editor/runtime/extensionSurface.test.ts:1396:          { id: 'b-output' as any, kind: 'outputFormat', label: 'B', requiresRender: false, outputExtension: 'b', order: 0 },
src/tools/video-editor/runtime/extensionSurface.test.ts:1401:    const ids = rt.config.outputFormats.map((f) => f.id);
src/tools/video-editor/runtime/extensionSurface.test.ts:1449:    expect(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME.outputFormats).toEqual([]);
src/tools/video-editor/runtime/extensionSurface.test.ts:1450:    expect(Object.isFrozen(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME.outputFormats)).toBe(true);
src/tools/video-editor/runtime/extensionSurface.test.ts:1459:    expect(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME.shaders).toEqual([]);
src/tools/video-editor/runtime/extensionSurface.test.ts:1460:    expect(Object.isFrozen(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME.shaders)).toBe(true);
src/tools/video-editor/runtime/extensionSurface.test.ts:1466:    expect(rt.outputFormats).toEqual([]);
src/tools/video-editor/runtime/extensionSurface.test.ts:1471:    expect(rt.shaders).toEqual([]);
src/tools/video-editor/runtime/extensionSurface.test.ts:1473:    expect(Object.isFrozen(rt.outputFormats)).toBe(true);
src/tools/video-editor/runtime/extensionSurface.test.ts:1478:    expect(Object.isFrozen(rt.shaders)).toBe(true);
src/tools/video-editor/runtime/extensionSurface.test.ts:1486:describe('normalizeExtensionRuntime — M13 shader contributions', () => {
src/tools/video-editor/runtime/extensionSurface.test.ts:1487:  it('projects shader contributions into config.shaders without routing through effects', () => {
src/tools/video-editor/runtime/extensionSurface.test.ts:1488:    const shaderSource = {
src/tools/video-editor/runtime/extensionSurface.test.ts:1492:    const ex = ext('com.example.shader-runtime', {
src/tools/video-editor/runtime/extensionSurface.test.ts:1496:            id: 'grade-shader' as any,
src/tools/video-editor/runtime/extensionSurface.test.ts:1497:            kind: 'shader',
src/tools/video-editor/runtime/extensionSurface.test.ts:1498:            shaderId: 'shader.grade',
src/tools/video-editor/runtime/extensionSurface.test.ts:1502:            source: shaderSource,
src/tools/video-editor/runtime/extensionSurface.test.ts:1514:            id: 'legacy-effect' as any,
src/tools/video-editor/runtime/extensionSurface.test.ts:1516:            effectId: 'legacy.effect',
src/tools/video-editor/runtime/extensionSurface.test.ts:1520:            id: 'legacy-transition' as any,
src/tools/video-editor/runtime/extensionSurface.test.ts:1522:            transitionId: 'legacy.transition',
src/tools/video-editor/runtime/extensionSurface.test.ts:1531:    expect(rt.config.shaders).toHaveLength(1);
src/tools/video-editor/runtime/extensionSurface.test.ts:1532:    expect(rt.shaders).toBe(rt.config.shaders);
src/tools/video-editor/runtime/extensionSurface.test.ts:1533:    expect(rt.config.shaders[0]).toMatchObject({
src/tools/video-editor/runtime/extensionSurface.test.ts:1534:      id: 'grade-shader',
src/tools/video-editor/runtime/extensionSurface.test.ts:1535:      extensionId: 'com.example.shader-runtime',
src/tools/video-editor/runtime/extensionSurface.test.ts:1536:      shaderId: 'shader.grade',
src/tools/video-editor/runtime/extensionSurface.test.ts:1540:      source: shaderSource,
src/tools/video-editor/runtime/extensionSurface.test.ts:1543:    expect(rt.config.effects.map((descriptor) => descriptor.effectId)).toEqual(['legacy.effect']);
src/tools/video-editor/runtime/extensionSurface.test.ts:1544:    expect(rt.config.transitions.map((descriptor) => descriptor.transitionId)).toEqual(['legacy.transition']);
src/tools/video-editor/runtime/extensionSurface.test.ts:1545:    expect(rt.inactiveReserved.some((entry) => entry.kind === 'shader')).toBe(false);
src/tools/video-editor/runtime/extensionSurface.test.ts:1548:  it('orders shader descriptors by extension order, contribution order, then ID', () => {
src/tools/video-editor/runtime/extensionSurface.test.ts:1549:    const extA = ext('com.example.first-shaders', {
src/tools/video-editor/runtime/extensionSurface.test.ts:1553:            id: 'z-shader' as any,
src/tools/video-editor/runtime/extensionSurface.test.ts:1554:            kind: 'shader',
src/tools/video-editor/runtime/extensionSurface.test.ts:1555:            shaderId: 'shader.z',
src/tools/video-editor/runtime/extensionSurface.test.ts:1561:            id: 'a-shader' as any,
src/tools/video-editor/runtime/extensionSurface.test.ts:1562:            kind: 'shader',
src/tools/video-editor/runtime/extensionSurface.test.ts:1563:            shaderId: 'shader.a',
src/tools/video-editor/runtime/extensionSurface.test.ts:1571:    const extB = ext('com.example.second-shaders', {
src/tools/video-editor/runtime/extensionSurface.test.ts:1575:            id: 'early-shader' as any,
src/tools/video-editor/runtime/extensionSurface.test.ts:1576:            kind: 'shader',
src/tools/video-editor/runtime/extensionSurface.test.ts:1577:            shaderId: 'shader.early',
src/tools/video-editor/runtime/extensionSurface.test.ts:1588:    expect(rt.config.shaders.map((descriptor) => descriptor.id)).toEqual([
src/tools/video-editor/runtime/extensionSurface.test.ts:1589:      'a-shader',
src/tools/video-editor/runtime/extensionSurface.test.ts:1590:      'z-shader',
src/tools/video-editor/runtime/extensionSurface.test.ts:1591:      'early-shader',
src/tools/video-editor/runtime/extensionSurface.test.ts:1614:          { id: 'b-output' as any, kind: 'outputFormat', label: 'B Output', requiresRender: false, outputExtension: 'json' },
src/tools/video-editor/runtime/extensionSurface.test.ts:1615:          { id: 'b-render-output' as any, kind: 'outputFormat', label: 'B Render', requiresRender: true, outputExtension: 'mp4' },
src/tools/video-editor/runtime/extensionSurface.test.ts:1631:    expect(rt.config.outputFormats).toHaveLength(2);
src/tools/video-editor/runtime/extensionSurface.test.ts:1632:    expect(rt.config.outputFormats[0].id).toBe('b-output');
src/tools/video-editor/runtime/extensionSurface.test.ts:1633:    expect(rt.config.outputFormats[0].disabled).toBe(false);
src/tools/video-editor/runtime/extensionSurface.test.ts:1634:    expect(rt.config.outputFormats[1].id).toBe('b-render-output');
src/tools/video-editor/runtime/extensionSurface.test.ts:1635:    expect(rt.config.outputFormats[1].disabled).toBe(false);
src/tools/video-editor/runtime/extensionSurface.test.ts:1636:    expect(rt.config.outputFormats[1].blockers).toHaveLength(1);
src/tools/video-editor/runtime/extensionSurface.test.ts:1640:    // Inactive reserved should only contain the reserved kinds (outputFormat, searchProvider)
src/tools/video-editor/runtime/extensionSurface.test.ts:1642:    expect(reservedKinds).toEqual(['outputFormat', 'outputFormat', 'searchProvider']);
src/tools/video-editor/runtime/liveDataRegistry.test.ts:2: * M11 T2: Unit tests for liveDataRegistry.
src/tools/video-editor/runtime/liveDataRegistry.test.ts:20: * @module liveDataRegistry.test
src/tools/video-editor/runtime/liveDataRegistry.test.ts:30:} from '@/tools/video-editor/runtime/liveDataRegistry';
src/tools/video-editor/runtime/liveDataRegistry.test.ts:819:        { kind: 'render-material', ref: 'material-live-full' },
src/tools/video-editor/runtime/liveDataRegistry.test.ts:825:    expect(result.targets.map((target) => target.outputRef)).toEqual(['asset-live-full', 'material-live-full']);
src/tools/video-editor/runtime/liveDataRegistry.test.ts:839:      id: 'material-live-full',
src/tools/video-editor/runtime/liveDataRegistry.test.ts:1129:    // not the live data registry.)
src/tools/video-editor/runtime/liveBake.ts:21:import type { RenderMaterialRef, RenderMaterialMediaKind } from './renderability';
src/tools/video-editor/runtime/liveBake.ts:78:  'render-material': 'render-material',
src/tools/video-editor/runtime/liveBake.ts:93:      `Live bake for source "${request.source.id}" has no samples to materialize.`,
src/tools/video-editor/runtime/liveBake.ts:405:  const renderMaterial = target.kind === 'render-material'
src/tools/video-editor/lib/assetMetadata.test.ts:532:    it('accepts metadata with only extensions and enrichment (search/related materials)', () => {
src/tools/video-editor/lib/assetMetadata.test.ts:720:          'ext.related': { materials: ['doc-1.pdf', 'doc-2.pdf'] },
src/tools/video-editor/runtime/extensionPackageManifest.ts:259:  // (e.g. legacy wrapper formats). This is advisory only.
src/tools/video-editor/runtime/extensionPackageManifest.ts:383:  'manifest/legacy-migration-shape', // only blocks in installed mode
src/tools/video-editor/runtime/extensionPackageManifest.ts:408:  'manifest/legacy-migration-shape', // warning in dev, error in installed
src/tools/video-editor/runtime/extensionMigration.test.ts:232:        { kind: 'shader', id: 'com.test.migration.shader1' } as ExtensionContribution,
src/tools/video-editor/runtime/extensionMigration.test.ts:240:    expect(result.installedOnly).toEqual(['com.test.migration.eff1', 'com.test.migration.shader1']);
src/tools/video-editor/runtime/extensionMigration.test.ts:256:        { kind: 'shader', id: 'com.test.migration.installedOnly' } as ExtensionContribution,
src/tools/video-editor/runtime/extensionReferenceReport.test.ts:112:  it('finds shader references', () => {
src/tools/video-editor/runtime/extensionReferenceReport.test.ts:115:        shaders: {
src/tools/video-editor/runtime/extensionReferenceReport.test.ts:116:          'com.shaders.gl.glowingEdge': ['Project-wide shader'],
src/tools/video-editor/runtime/extensionReferenceReport.test.ts:123:    expect(result.entries[0].referencesByKind.shader).toHaveLength(1);
src/tools/video-editor/runtime/extensionReferenceReport.test.ts:157:        liveDataSources: {
src/tools/video-editor/runtime/renderability.ts:2: * Shared renderability and artifact vocabulary for provider-scoped
src/tools/video-editor/runtime/renderability.ts:23: * Determinism posture for a contribution, material, artifact, or bake.
src/tools/video-editor/runtime/renderability.ts:26: * - `preview-only`: usable only for interactive preview, not authoritative export.
src/tools/video-editor/runtime/renderability.ts:27: * - `live-unbaked`: depends on live provider/runtime state until materialized.
src/tools/video-editor/runtime/renderability.ts:55:  | 'missing-material'
src/tools/video-editor/runtime/renderability.ts:56:  | 'materialization-failed'
src/tools/video-editor/runtime/renderability.ts:67:  'missing-material',
src/tools/video-editor/runtime/renderability.ts:68:  'materialization-failed',
src/tools/video-editor/runtime/renderability.ts:105:  readonly materialRefId?: string;
src/tools/video-editor/runtime/renderability.ts:109:/** Blocking subset of a finding that prevents a route from being authoritative. */
src/tools/video-editor/runtime/renderability.ts:128:export function shaderMissingMaterializerBlockerMessage(
src/tools/video-editor/runtime/renderability.ts:129:  shaderId: string,
src/tools/video-editor/runtime/renderability.ts:133:  return `Shader "${shaderId}" cannot export because no shader materializer produced RenderMaterial for ${
src/tools/video-editor/runtime/renderability.ts:156:/** Storage locator for material bytes or generated artifact outputs. */
src/tools/video-editor/runtime/renderability.ts:166: * Stable timeline-facing reference to deterministic composition input.
src/tools/video-editor/runtime/renderability.ts:168: * A RenderMaterialRef points at source material used to compose or bake a
src/tools/video-editor/runtime/renderability.ts:180:  readonly replacementPolicy: 'replace-live-ref' | 'preserve-live-ref' | 'materialize-on-export';
src/tools/video-editor/runtime/renderability.ts:183:/** Concrete material metadata plus optional duration/range constraints. */
src/tools/video-editor/runtime/renderability.ts:192:/** Boundary where a material or artifact may cross provider/process/storage. */
src/tools/video-editor/runtime/renderability.ts:300:  readonly outputFormatId?: string;
src/tools/video-editor/runtime/renderability.ts:328:  readonly outputFormatId?: string;
src/tools/video-editor/runtime/renderability.ts:387:    outputFormatId: params.outputFormatId,
src/tools/video-editor/runtime/renderability.ts:460:  readonly outputFormatId?: string;
src/tools/video-editor/runtime/renderability.ts:517:  // Build consumed material refs from asset keys
src/tools/video-editor/runtime/renderability.ts:519:    id: `material.asset.${key}`,
src/tools/video-editor/runtime/renderability.ts:549:    outputFormatId: params.outputFormatId,
src/tools/video-editor/runtime/exportGuard.test.ts:8:import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
src/tools/video-editor/runtime/exportGuard.test.ts:65:    renderability: {
src/tools/video-editor/runtime/exportGuard.test.ts:105:    renderability: {
src/tools/video-editor/runtime/exportGuard.test.ts:524:  it('passes provider snapshot effect IDs that are absent from legacy known IDs', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:656:        renderability: {
src/tools/video-editor/runtime/exportGuard.test.ts:728:        renderability: {
src/tools/video-editor/runtime/exportGuard.test.ts:842:        renderability: {
src/tools/video-editor/runtime/exportGuard.test.ts:1212:        renderability: {
src/tools/video-editor/runtime/exportGuard.test.ts:1280:        renderability: {
src/tools/video-editor/runtime/exportGuard.test.ts:1381:  it('emits exact missing materializer blockers for clip and postprocess shader metadata', () => {
src/tools/video-editor/runtime/exportGuard.test.ts:1382:    const clipShaderMessage = 'Shader "shader.preview.clip" cannot export because no shader materializer produced RenderMaterial for clip "c1".';
src/tools/video-editor/runtime/exportGuard.test.ts:1383:    const postprocessShaderMessage = 'Shader "shader.preview.post" cannot export because no shader materializer produced RenderMaterial for timeline postprocess.';
src/tools/video-editor/runtime/exportGuard.test.ts:1386:        shader: {
src/tools/video-editor/runtime/exportGuard.test.ts:1388:          extensionId: 'ext.shader',
src/tools/video-editor/runtime/exportGuard.test.ts:1389:          contributionId: 'ext.shader.clip',
src/tools/video-editor/runtime/exportGuard.test.ts:1390:          shaderId: 'shader.preview.clip',
src/tools/video-editor/runtime/exportGuard.test.ts:1397:        shaderPostprocess: {
src/tools/video-editor/runtime/exportGuard.test.ts:1399:          extensionId: 'ext.shader',
src/tools/video-editor/runtime/exportGuard.test.ts:1400:          contributionId: 'ext.shader.post',
src/tools/video-editor/runtime/exportGuard.test.ts:1401:          shaderId: 'shader.preview.post',
src/tools/video-editor/runtime/exportGuard.test.ts:1411:        code: 'export/unrenderable-shader',
src/tools/video-editor/runtime/exportGuard.test.ts:1413:        extensionId: 'ext.shader',
src/tools/video-editor/runtime/exportGuard.test.ts:1414:        contributionId: 'ext.shader.clip',
src/tools/video-editor/runtime/exportGuard.test.ts:1417:          shaderId: 'shader.preview.clip',
src/tools/video-editor/runtime/exportGuard.test.ts:1418:          shaderScope: 'clip',
src/tools/video-editor/runtime/exportGuard.test.ts:1424:        code: 'export/unrenderable-shader',
src/tools/video-editor/runtime/exportGuard.test.ts:1426:        extensionId: 'ext.shader',
src/tools/video-editor/runtime/exportGuard.test.ts:1427:        contributionId: 'ext.shader.post',
src/tools/video-editor/runtime/exportGuard.test.ts:1429:          shaderId: 'shader.preview.post',
src/tools/video-editor/runtime/exportGuard.test.ts:1430:          shaderScope: 'postprocess',
src/tools/video-editor/runtime/exportGuard.test.ts:1438:        reason: 'missing-material',
src/tools/video-editor/runtime/exportGuard.test.ts:1443:        reason: 'missing-material',
src/tools/video-editor/runtime/exportGuard.test.ts:1456:        renderability: {
src/tools/video-editor/runtime/exportGuard.test.ts:1492:        renderability: {
src/tools/video-editor/runtime/effectRegistrationService.ts:8: * provenance / owner / schema / renderability / diagnostics, supports HMR
src/tools/video-editor/runtime/effectRegistrationService.ts:35:} from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/runtime/effectRegistrationService.ts:257: * registration-time validation failures — legacy applied parameters continue
src/tools/video-editor/runtime/effectRegistrationService.ts:447:    const renderability = buildRenderability(contrib);
src/tools/video-editor/runtime/effectRegistrationService.ts:451:    // (validateAndCoerceParams) continues to work for already-applied legacy data.
src/tools/video-editor/runtime/effectRegistrationService.ts:470:      renderability,
src/tools/video-editor/lib/timeline-domain.ts:36:  | 'legacy_pinned_shot_group_repaired'
src/tools/video-editor/lib/timeline-domain.ts:37:  | 'legacy_tracks_migrated'
src/tools/video-editor/lib/timeline-domain.ts:38:  | 'legacy_background_clip_inserted'
src/tools/video-editor/lib/timeline-domain.ts:45:  | 'legacy_transition_missing_type'
src/tools/video-editor/lib/timeline-domain.ts:46:  | 'legacy_transition_unresolvable'
src/tools/video-editor/lib/timeline-domain.ts:47:  | 'legacy_transition_removed_contributed'
src/tools/video-editor/lib/timeline-domain.ts:48:  | 'legacy_transition_params_repaired'
src/tools/video-editor/lib/timeline-domain.ts:49:  | 'legacy_transition_cleared'
src/tools/video-editor/lib/timeline-domain.ts:56:  | 'shader_scope_occupied';
src/tools/video-editor/lib/timeline-domain.ts:119:  'output-composition': {
src/tools/video-editor/lib/timeline-domain.ts:142:export const TIMELINE_POSTPROCESS_SHADER_APP_KEY = 'shaderPostprocess';
src/tools/video-editor/lib/timeline-domain.ts:294:      code: 'shader_scope_occupied';
src/tools/video-editor/lib/timeline-domain.ts:316:    && typeof value.shaderId === 'string'
src/tools/video-editor/lib/timeline-domain.ts:317:    && value.shaderId.length > 0
src/tools/video-editor/lib/timeline-domain.ts:322:  const shader = clip.app?.shader;
src/tools/video-editor/lib/timeline-domain.ts:323:  return isTimelineShaderMetadata(shader, 'clip') ? shader : undefined;
src/tools/video-editor/lib/timeline-domain.ts:329:  const shader = config.app?.[TIMELINE_POSTPROCESS_SHADER_APP_KEY];
src/tools/video-editor/lib/timeline-domain.ts:330:  return isTimelineShaderMetadata(shader, 'postprocess') ? shader : undefined;
src/tools/video-editor/lib/timeline-domain.ts:340:  && left.shaderId === right.shaderId
src/tools/video-editor/lib/timeline-domain.ts:351:    return `Cannot add shader "${incomingShaderId}" to ${target} because shader "${existingShaderId}" is already assigned. ` +
src/tools/video-editor/lib/timeline-domain.ts:352:      'V1 supports one clip shader per clip. Remove the existing shader before assigning another.';
src/tools/video-editor/lib/timeline-domain.ts:355:  return `Cannot add postprocess shader "${incomingShaderId}" because postprocess shader "${existingShaderId}" is already assigned. ` +
src/tools/video-editor/lib/timeline-domain.ts:356:    'V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.';
src/tools/video-editor/lib/timeline-domain.ts:366:  code: 'shader_scope_occupied',
src/tools/video-editor/lib/timeline-domain.ts:370:  message: timelineShaderScopeOccupiedMessage(scope, existing.shaderId, incoming.shaderId, clipId),
src/tools/video-editor/lib/timeline-domain.ts:375:  shader: TimelineClipShaderMetadata,
src/tools/video-editor/lib/timeline-domain.ts:378:  if (existing && !sameTimelineShaderIdentity(existing, shader)) {
src/tools/video-editor/lib/timeline-domain.ts:379:    return createShaderScopeOccupiedResult('clip', existing, shader, clip.id);
src/tools/video-editor/lib/timeline-domain.ts:388:        shader,
src/tools/video-editor/lib/timeline-domain.ts:396:  shader: TimelinePostprocessShaderMetadata,
src/tools/video-editor/lib/timeline-domain.ts:399:  if (existing && !sameTimelineShaderIdentity(existing, shader)) {
src/tools/video-editor/lib/timeline-domain.ts:400:    return createShaderScopeOccupiedResult('postprocess', existing, shader);
src/tools/video-editor/lib/timeline-domain.ts:409:        [TIMELINE_POSTPROCESS_SHADER_APP_KEY]: shader,
src/tools/video-editor/lib/timeline-domain.ts:550:    'legacy_background_clip_inserted',
src/tools/video-editor/lib/timeline-domain.ts:658:    const legacy = group as LegacyPinnedShotGroup;
src/tools/video-editor/lib/timeline-domain.ts:659:    const hasLegacyFields = typeof legacy.start === 'number' || Array.isArray(legacy.children);
src/tools/video-editor/lib/timeline-domain.ts:667:    const derivedClipIds = Array.isArray(legacy.children) && legacy.children.length > 0
src/tools/video-editor/lib/timeline-domain.ts:668:      ? legacy.children.map((child) => child.clipId).filter((id): id is string => typeof id === 'string' && id.length > 0)
src/tools/video-editor/lib/timeline-domain.ts:713:      'legacy_pinned_shot_group_repaired',
src/tools/video-editor/lib/timeline-domain.ts:714:      `Repaired ${repairedLegacyGroupCount} legacy pinned shot group projection(s).`,
src/tools/video-editor/lib/timeline-domain.ts:748:    'legacy_tracks_migrated',
src/tools/video-editor/lib/timeline-domain.ts:749:    'Migrated legacy timeline config into the flat-track shape.',
src/tools/video-editor/lib/timeline-domain.ts:1089:  'material-ref',
src/tools/video-editor/lib/timeline-domain.ts:1741:      (mapping.kind === 'frame-ref' || mapping.kind === 'material-ref')
src/tools/video-editor/lib/timeline-domain.ts:1831:  [TransitionDiagnosticCodes.MISSING_TRANSITION_OBJECT]: 'legacy_transition_cleared',
src/tools/video-editor/lib/timeline-domain.ts:1832:  [TransitionDiagnosticCodes.MISSING_TYPE]: 'legacy_transition_missing_type',
src/tools/video-editor/lib/timeline-domain.ts:1833:  [TransitionDiagnosticCodes.INVALID_TYPE]: 'legacy_transition_missing_type',
src/tools/video-editor/lib/timeline-domain.ts:1834:  [TransitionDiagnosticCodes.UNRESOLVED_TYPE]: 'legacy_transition_unresolvable',
src/tools/video-editor/lib/timeline-domain.ts:1835:  [TransitionDiagnosticCodes.REMOVED_CONTRIBUTED]: 'legacy_transition_removed_contributed',
src/tools/video-editor/lib/timeline-domain.ts:1836:  [TransitionDiagnosticCodes.MISSING_PARAMS]: 'legacy_transition_params_repaired',
src/tools/video-editor/lib/timeline-domain.ts:1837:  [TransitionDiagnosticCodes.INACTIVE_RECORD]: 'legacy_transition_unresolvable',
src/tools/video-editor/lib/timeline-domain.ts:1844: * `@/tools/video-editor/transitions/validation.ts` to detect malformed legacy
src/tools/video-editor/lib/timeline-domain.ts:1850: * - Missing params → schema defaults are materialized via `set-transition`.
src/tools/video-editor/lib/timeline-domain.ts:1896:        TRANSITION_CODE_TO_ISSUE_CODE[diag.code] ?? 'legacy_transition_unresolvable';
src/tools/video-editor/lib/timeline-domain.ts:1939:      'legacy_transition_cleared',
src/tools/video-editor/lib/timeline-domain.ts:1953:      'legacy_transition_params_repaired',
src/tools/video-editor/lib/timeline-domain.ts:1954:      `Repaired ${repairedParamsCount} clip transition(s) with materialized schema defaults.`,
src/tools/video-editor/lib/timeline-domain.ts:2068:    if (Array.isArray(clipApp?.shader)) {
src/tools/video-editor/lib/timeline-domain.ts:2069:      const shaderStack = clipApp.shader;
src/tools/video-editor/lib/timeline-domain.ts:2070:      const existing = shaderStack[0] as { shaderId?: unknown } | undefined;
src/tools/video-editor/lib/timeline-domain.ts:2071:      const incoming = shaderStack[1] as { shaderId?: unknown } | undefined;
src/tools/video-editor/lib/timeline-domain.ts:2075:        'shader_scope_occupied',
src/tools/video-editor/lib/timeline-domain.ts:2078:          typeof existing?.shaderId === 'string' ? existing.shaderId : 'unknown',
src/tools/video-editor/lib/timeline-domain.ts:2079:          typeof incoming?.shaderId === 'string' ? incoming.shaderId : 'unknown',
src/tools/video-editor/lib/timeline-domain.ts:2084:          path: `clips.${clip.id}.app.shader`,
src/tools/video-editor/lib/timeline-domain.ts:2088:            shaderCount: shaderStack.length,
src/tools/video-editor/lib/timeline-domain.ts:2151:    const existing = postprocessShaderValue[0] as { shaderId?: unknown } | undefined;
src/tools/video-editor/lib/timeline-domain.ts:2152:    const incoming = postprocessShaderValue[1] as { shaderId?: unknown } | undefined;
src/tools/video-editor/lib/timeline-domain.ts:2156:      'shader_scope_occupied',
src/tools/video-editor/lib/timeline-domain.ts:2159:        typeof existing?.shaderId === 'string' ? existing.shaderId : 'unknown',
src/tools/video-editor/lib/timeline-domain.ts:2160:        typeof incoming?.shaderId === 'string' ? incoming.shaderId : 'unknown',
src/tools/video-editor/lib/timeline-domain.ts:2167:          shaderCount: postprocessShaderValue.length,
src/tools/video-editor/runtime/effectRegistrationService.test.ts:717:  it('registered record gets preview-supported renderability by default', () => {
src/tools/video-editor/runtime/effectRegistrationService.test.ts:718:    const extensionId = 'com.example.renderability';
src/tools/video-editor/runtime/effectRegistrationService.test.ts:732:    expect(record?.renderability).toBeDefined();
src/tools/video-editor/runtime/effectRegistrationService.test.ts:733:    expect(record?.renderability.defaultRoute).toBe('preview');
src/tools/video-editor/runtime/effectRegistrationService.test.ts:735:    const capabilities = record?.renderability.capabilities ?? [];
src/tools/video-editor/runtime/effectRegistrationService.test.ts:765:    const browserCap = record?.renderability.capabilities.find((c) => c.route === 'browser-export');
src/tools/video-editor/runtime/effectRegistrationService.test.ts:786:    const workerCap = record?.renderability.capabilities.find((c) => c.route === 'worker-export');
src/tools/video-editor/sequence.ts:6: * validate a trusted sequence draft, materialize asset-backed params, and
src/tools/video-editor/sequence.ts:40:  materializeSequenceParams,
src/tools/video-editor/sequence.ts:41:  materializeSequenceClip,
src/tools/video-editor/sequence.ts:42:  materializeSequenceConfig,
src/tools/video-editor/sequence.ts:43:  materializeResolvedSequenceConfig,
src/tools/video-editor/sequence.ts:44:} from './sequences/materialize.ts';
src/tools/video-editor/sequence.ts:48:} from './sequences/materialize.ts';
src/tools/video-editor/lib/mobile-interaction-model.ts:19:  | 'shader'
src/tools/video-editor/lib/mobile-interaction-model.ts:32:  shaderScope?: 'clip' | 'postprocess';
src/tools/video-editor/lib/mobile-interaction-model.ts:33:  shaderId?: string | null;
src/tools/video-editor/runtime/extensionSurface.ts:144:  /** M6: Normalized output format descriptors (disabled diagnostics for render-dependent). */
src/tools/video-editor/runtime/extensionSurface.ts:145:  outputFormats: readonly VideoEditorOutputFormatDescriptor[];
src/tools/video-editor/runtime/extensionSurface.ts:158:  /** M13: Normalized WebGL shader descriptors, provider-scoped and deterministically ordered. */
src/tools/video-editor/runtime/extensionSurface.ts:159:  shaders: readonly VideoEditorShaderDescriptor[];
src/tools/video-editor/runtime/extensionSurface.ts:174:// M6: Asset parser / output format / search provider descriptors
src/tools/video-editor/runtime/extensionSurface.ts:189:/** A normalized output format descriptor produced by runtime normalization. */
src/tools/video-editor/runtime/extensionSurface.ts:203:  /** Planner-visible routes declared by render-dependent output formats. */
src/tools/video-editor/runtime/extensionSurface.ts:207:  /** Process requirements referenced by this output format. */
src/tools/video-editor/runtime/extensionSurface.ts:249:/** Planner next-action metadata for resolving route/process/material blockers. */
src/tools/video-editor/runtime/extensionSurface.ts:284:  resultKinds?: readonly ('asset' | 'material')[];
src/tools/video-editor/runtime/extensionSurface.ts:353:// M13: WebGL shader descriptors
src/tools/video-editor/runtime/extensionSurface.ts:356:/** A normalized WebGL shader descriptor produced by runtime normalization. */
src/tools/video-editor/runtime/extensionSurface.ts:361:  /** The shader identifier that must match registerShader calls. */
src/tools/video-editor/runtime/extensionSurface.ts:362:  shaderId: string;
src/tools/video-editor/runtime/extensionSurface.ts:363:  /** Human-readable label, falling back to shaderId. */
src/tools/video-editor/runtime/extensionSurface.ts:366:  /** V1 shader pass scope. */
src/tools/video-editor/runtime/extensionSurface.ts:372:  materializer?: ShaderMaterializerDescriptor;
src/tools/video-editor/runtime/extensionSurface.ts:431:  readonly outputFormats: readonly VideoEditorOutputFormatDescriptor[];
src/tools/video-editor/runtime/extensionSurface.ts:444:  /** M13: Normalized WebGL shader descriptors. */
src/tools/video-editor/runtime/extensionSurface.ts:445:  readonly shaders: readonly VideoEditorShaderDescriptor[];
src/tools/video-editor/runtime/extensionSurface.ts:518:  outputFormats: EMPTY_OUTPUT_FORMATS,
src/tools/video-editor/runtime/extensionSurface.ts:525:  shaders: EMPTY_SHADERS,
src/tools/video-editor/runtime/extensionSurface.ts:705:        (contrib.kind === 'outputFormat' || contrib.kind === 'searchProvider')
src/tools/video-editor/runtime/extensionSurface.ts:729:        if (contrib.kind === 'outputFormat') {
src/tools/video-editor/runtime/extensionSurface.ts:816:  const shaderDescriptors: VideoEditorShaderDescriptor[] = [];
src/tools/video-editor/runtime/extensionSurface.ts:946:      // M13: shader — bridge dedicated WebGL shader contributions into shaders
src/tools/video-editor/runtime/extensionSurface.ts:947:      case 'shader': {
src/tools/video-editor/runtime/extensionSurface.ts:948:        const shaderContrib = contribution as unknown as ShaderContribution;
src/tools/video-editor/runtime/extensionSurface.ts:949:        if (shaderContrib.shaderId) {
src/tools/video-editor/runtime/extensionSurface.ts:950:          shaderDescriptors.push({
src/tools/video-editor/runtime/extensionSurface.ts:954:            shaderId: shaderContrib.shaderId,
src/tools/video-editor/runtime/extensionSurface.ts:955:            label: shaderContrib.label ?? shaderContrib.shaderId,
src/tools/video-editor/runtime/extensionSurface.ts:956:            description: shaderContrib.description,
src/tools/video-editor/runtime/extensionSurface.ts:957:            pass: shaderContrib.pass,
src/tools/video-editor/runtime/extensionSurface.ts:958:            source: shaderContrib.source,
src/tools/video-editor/runtime/extensionSurface.ts:959:            uniforms: shaderContrib.uniforms,
src/tools/video-editor/runtime/extensionSurface.ts:960:            textures: shaderContrib.textures,
src/tools/video-editor/runtime/extensionSurface.ts:961:            fallback: shaderContrib.fallback,
src/tools/video-editor/runtime/extensionSurface.ts:962:            materializer: shaderContrib.materializer,
src/tools/video-editor/runtime/extensionSurface.ts:963:            hasSourceMetadata: shaderContrib.source !== undefined,
src/tools/video-editor/runtime/extensionSurface.ts:968:            code: 'runtime/shader-missing-shader-id',
src/tools/video-editor/runtime/extensionSurface.ts:971:              'has no shaderId. The shader will be inactive.',
src/tools/video-editor/runtime/extensionSurface.ts:1001:  const outputFormatDescriptors: VideoEditorOutputFormatDescriptor[] = [];
src/tools/video-editor/runtime/extensionSurface.ts:1011:    outputFormatDescriptors.push({
src/tools/video-editor/runtime/extensionSurface.ts:1033:  // Order output formats by extension order, then contribution order, then ID
src/tools/video-editor/runtime/extensionSurface.ts:1034:  outputFormatDescriptors.sort((a, b) => {
src/tools/video-editor/runtime/extensionSurface.ts:1122:    outputFormatDescriptors.length > 0 ||
src/tools/video-editor/runtime/extensionSurface.ts:1129:    shaderDescriptors.length > 0 ||
src/tools/video-editor/runtime/extensionSurface.ts:1144:        outputFormats: Object.freeze(outputFormatDescriptors),
src/tools/video-editor/runtime/extensionSurface.ts:1151:        shaders: Object.freeze(shaderDescriptors),
src/tools/video-editor/runtime/extensionSurface.ts:1168:    outputFormats: Object.freeze(outputFormatDescriptors),
src/tools/video-editor/runtime/extensionSurface.ts:1175:    shaders: Object.freeze(shaderDescriptors),
src/tools/video-editor/runtime/extensionSurface.ts:1228:    message: 'Render-dependent output formats must declare render routes before planning can execute them.',
src/tools/video-editor/runtime/extensionSurface.ts:1370:  outputFormats: EMPTY_OUTPUT_FORMATS,
src/tools/video-editor/runtime/extensionSurface.ts:1377:  shaders: EMPTY_SHADERS,
src/tools/video-editor/runtime/extensionSurface.ts:1445:  readonly kind: 'clip' | 'selection' | 'track' | 'timeline' | 'shader';
src/tools/video-editor/runtime/extensionSurface.ts:1452:  /** Shader scope when kind === 'shader'. */
src/tools/video-editor/runtime/extensionSurface.ts:1453:  readonly shaderScope?: 'clip' | 'postprocess';
src/tools/video-editor/runtime/extensionSurface.ts:1454:  /** Shader ID when kind === 'shader'. */
src/tools/video-editor/runtime/extensionSurface.ts:1455:  readonly shaderId?: string;
src/tools/video-editor/runtime/extensionSurface.ts:1456:  /** Owning extension ID when kind === 'shader'. */
src/tools/video-editor/runtime/extensionSurface.ts:1458:  /** Contribution ID when kind === 'shader'. */
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:512:// Related materials
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:516: * Get material IDs related to this asset.
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:519: * Future: may also surface material references from parser enrichment.
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:536: * Check whether the asset has any related materials.
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:677:  /** Asset or material reference key. */
src/tools/video-editor/lib/assetMetadataUIHelpers.ts:680:  kind: 'asset' | 'material';
src/tools/video-editor/lib/effect-catalog.ts:8:import type { ContributionRenderability } from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/lib/effect-catalog.ts:24:  renderability?: ContributionRenderability;
src/tools/video-editor/lib/effect-catalog.ts:129:    renderability: record.renderability,
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:15:} from '@/tools/video-editor/shaders/compile/webgl-adapter.ts';
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:16:import type { ShaderValidationContext } from '@/tools/video-editor/shaders/compile/diagnostics.ts';
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:105:      'shader',
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:107:      code.replace(/^shader\//, ''),
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:109:      context.contributionId ?? context.shaderId ?? 'anonymous',
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:118:      ...(context.shaderId ? { shaderId: context.shaderId } : {}),
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:277:      shaderId: input.shaderId,
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:437:          'shader/webgl-context-lost',
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:438:          'WebGL shader preview context was lost; rendering is paused until the context is restored.',
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:490:        'shader/preview-buffer-unavailable',
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:491:        'WebGL shader preview could not allocate a fullscreen vertex buffer.',
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:632:          'shader/texture-unsupported',
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:648:          'shader/texture-unavailable',
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:665:      diagnostic.code !== 'shader/texture-unsupported'
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts:666:      && diagnostic.code !== 'shader/texture-unavailable'
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:5:import { PostprocessShaderPreviewCanvas } from '@/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx';
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:7:import type { ShaderEffectRegistryRecord } from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:21:vi.mock('@/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts', () => ({
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:36:function shader(overrides: Partial<TimelinePostprocessShaderMetadata> = {}): TimelinePostprocessShaderMetadata {
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:39:    extensionId: 'ext.shader',
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:40:    contributionId: 'ext.shader.post',
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:41:    shaderId: 'shader.preview.post',
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:52:    shaderId: 'shader.preview.post',
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:53:    ownerExtensionId: 'ext.shader',
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:54:    contributionId: 'ext.shader.post',
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:68:    renderability: {
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:90:  it('creates a preview surface for an active inline postprocess shader and renders the current timeline frame', () => {
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:93:        shader={shader()}
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:102:    expect(screen.getByTestId('postprocess-shader-preview-canvas')).toHaveAttribute('data-shader-scope', 'postprocess');
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:105:      shaderId: 'shader.preview.post',
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:106:      extensionId: 'ext.shader',
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:107:      contributionId: 'ext.shader.post',
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:117:        shader={shader({ uniforms: { intensity: 0.25 } })}
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:126:    expect(screen.getByTestId('postprocess-shader-preview-canvas')).toHaveAttribute('data-shader-frame', '60');
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:136:      shader: TimelinePostprocessShaderMetadata;
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:139:      { name: 'disabled', shader: shader({ enabled: false }), record: record() },
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:140:      { name: 'inactive', shader: shader(), record: record({ status: 'inactive' }) },
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:143:        shader: shader(),
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:147:            specifier: './shader.ts',
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:151:      { name: 'clip pass', shader: shader(), record: record({ pass: 'clip' }) },
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.test.tsx:157:          shader={item.shader}
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:19:import { EffectLayerSequence } from '@/tools/video-editor/compositions/EffectLayerSequence.tsx';
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:31:const renderability: EffectRegistryRecord['renderability'] = {
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:82:    renderability,
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:123:  it('prefers provider snapshot records and schemas over the legacy singleton for matching effect IDs', async () => {
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:124:    const LegacyEffect = makeEffect('legacy-effect');
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:141:    expect(screen.queryByTestId('legacy-effect')).not.toBeInTheDocument();
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:168:    replaceEffectRegistry(new DynamicEffectRegistry({ 'legacy-only': makeEffect('legacy-only') }));
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:172:      <EffectLayerSequence clip={clip('legacy-only')} fps={30} effectRegistrySnapshot={emptySnapshot}>
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:178:    expect(screen.queryByTestId('legacy-only')).not.toBeInTheDocument();
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:179:    expect(warn).toHaveBeenCalledWith('[EffectLayer] effect NOT FOUND for clip=%s type=%s', 'clip-legacy-only', 'legacy-only');
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:245:  it('context-based resolution falls back to legacy singleton when no provider context exists', async () => {
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:246:    const LegacyOnly = makeEffect('legacy-context-only');
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:247:    replaceEffectRegistry(new DynamicEffectRegistry({ 'legacy-context-only': LegacyOnly }));
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:249:    // No EffectRegistryProvider wrapper — legacy fallback is active
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:251:      <EffectLayerSequence clip={clip('legacy-context-only')} fps={30}>
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:256:    // With no provider context, falls back to legacy singleton
src/tools/video-editor/compositions/EffectLayerSequence.test.tsx:258:      expect(screen.getByTestId('legacy-context-only')).toBeInTheDocument();
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:44:// Finding shape (compatible with CapabilityFinding from renderability.ts)
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:56:  readonly materialRefId?: string;
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:98:    hasOutputFormat: !!exportCtx?.outputFormatId,
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:111:    if (!exportCtx.outputFormatId) {
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:112:      analysis.missingFields.push('outputFormatId');
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:176:        'Export tool invoked without export context. Provide outputFormatId, blockers, and contributionIds for complete planning.',
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:194:        'No output format selected. The export plan cannot tailor recommendations to a specific format.',
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:198:          recommendation: 'Select an output format before invoking export planning.',
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:229:        'Contribution IDs are available for export. Export plan can assess contribution renderability.',
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:238:        'No contribution IDs provided. The export plan cannot assess per-contribution renderability or export readiness.',
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:243:            'Include contributionIds in the export context for per-contribution renderability analysis.',
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:377:      ...(f.materialRefId ? { materialRefId: f.materialRefId } : {}),
src/tools/video-editor/examples/extensions/agent-tools-export/index.ts:600:      ...(f.materialRefId ? { materialRefId: f.materialRefId } : {}),
src/tools/video-editor/lib/shader-catalog.ts:9:import type { RenderRoute } from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/lib/shader-catalog.ts:13:} from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/lib/shader-catalog.ts:37:  return record.renderability.capabilities
src/tools/video-editor/lib/shader-catalog.ts:43:  const hasPreview = record.renderability.capabilities.some(
src/tools/video-editor/lib/shader-catalog.ts:46:  const hasBrowserExport = record.renderability.capabilities.some(
src/tools/video-editor/lib/shader-catalog.ts:49:  const hasWorkerExport = record.renderability.capabilities.some(
src/tools/video-editor/lib/shader-catalog.ts:123:export function materializeShaderUniformDefaults(
src/tools/video-editor/lib/shader-catalog.ts:133:export function materializeShaderTextureDefaults(
src/tools/video-editor/lib/shader-catalog.ts:146:  const uniforms = materializeShaderUniformDefaults(record.uniforms);
src/tools/video-editor/lib/shader-catalog.ts:147:  const textures = materializeShaderTextureDefaults(record.uniforms);
src/tools/video-editor/lib/shader-catalog.ts:153:    shaderId: record.shaderId,
src/tools/video-editor/lib/shader-catalog.ts:168:  const uniforms = materializeShaderUniformDefaults(record.uniforms);
src/tools/video-editor/lib/shader-catalog.ts:169:  const textures = materializeShaderTextureDefaults(record.uniforms);
src/tools/video-editor/lib/shader-catalog.ts:175:    shaderId: record.shaderId,
src/tools/video-editor/compositions/EffectLayerSequence.tsx:64:  // Sequence so they still see the original composition time.
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:13:} from '@/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts';
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:14:import type { ShaderEffectRegistryRecord } from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:17:  readonly shader: TimelinePostprocessShaderMetadata;
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:43:  shader,
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:51:  testId = 'postprocess-shader-preview-canvas',
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:58:  const active = shader.enabled !== false
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:73:      shaderId: shader.shaderId,
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:74:      extensionId: shader.extensionId,
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:75:      contributionId: shader.contributionId,
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:79:      uniformValues: shader.uniforms,
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:81:      textureValues: shader.textures,
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:110:    shader.contributionId,
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:111:    shader.extensionId,
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:112:    shader.shaderId,
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:113:    shader.textures,
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:114:    shader.uniforms,
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:121:    surface.setUniformValues(shader.uniforms ?? {});
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:122:    surface.setTextureValues(shader.textures ?? {});
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:130:    shader.textures,
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:131:    shader.uniforms,
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:144:      data-shader-id={shader.shaderId}
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:145:      data-shader-scope="postprocess"
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:146:      data-shader-frame={Math.floor(frame)}
src/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx:147:      data-shader-time={timeSeconds}
src/tools/video-editor/compositions/TimelineRenderer.test.tsx:5: *   1. A clipType registered in `@banodoco/timeline-composition/registry.generated`
src/tools/video-editor/compositions/TimelineRenderer.test.tsx:12: * `packages/timeline-composition/typescript/src/registry.generated.ts`.
src/tools/video-editor/compositions/TimelineRenderer.test.tsx:19:} from '@banodoco/timeline-composition/registry.generated';
src/tools/video-editor/lib/timeline-domain.live-bindings.test.ts:274:  it('accepts scalar, vector, FFT-bin, RMS/amplitude, onset event, frame ref, and material ref mappings as metadata', () => {
src/tools/video-editor/lib/timeline-domain.live-bindings.test.ts:323:              bindingId: 'uniform-material-ref',
src/tools/video-editor/lib/timeline-domain.live-bindings.test.ts:326:              mapping: { kind: 'material-ref', uniform: 'u_material', ref: { kind: 'render-material', ref: 'mat-live' } },
src/tools/video-editor/lib/timeline-domain.live-bindings.test.ts:344:      'uniform-material-ref',
src/tools/video-editor/lib/timeline-domain.live-bindings.test.ts:353:      'material-ref',
src/tools/video-editor/lib/timeline-domain.live-bindings.test.ts:379:              mapping: { kind: 'material-ref', uniform: 'u_mat', ref: { kind: 'render-material' } },
src/tools/video-editor/compositions/installed-themes.ts:4:} from '@banodoco/timeline-composition/theme-api';
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:127:    const materialRef: TimelineMaterialRefSummary = {
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:152:    expect(materialRef.assetKey).toBe('asset-1');
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:333:  it('snapshot includes material refs from clip assets', async () => {
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:354:    expect(clip!.materialRefs).toBeDefined();
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:355:    expect(clip!.materialRefs!.length).toBe(1);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:356:    expect(clip!.materialRefs![0].assetKey).toBe('some-asset-key');
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:359:    expect(snap.materialRefs).toBeDefined();
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:360:    expect(snap.materialRefs!.length).toBe(1);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:452:    // Bare clip has no effects, transitions, live bindings, or material refs
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:458:    expect(clip.materialRefs).toBeUndefined();
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:465:    // materialRefs might be present if any clip has an asset, but this one doesn't
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:466:    expect(snap.materialRefs).toBeUndefined();
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:654:  it('emits material-ref requirements when material refs exist', async () => {
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:675:    const materialReqs = reqs.filter((r) =>
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:676:      r.id.startsWith('snapshot.materialRef.'),
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:678:    expect(materialReqs.length).toBeGreaterThanOrEqual(1);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:679:    expect(materialReqs[0].sourceRef.source).toBe('registry');
src/tools/video-editor/lib/serialize.test.ts:232:  it('round-trips legacy pinnedShotGroups through repairConfig before serialization', () => {
src/tools/video-editor/lib/serialize.test.ts:599:  it('round-trips clip-local and postprocess shader metadata through disk serialization', () => {
src/tools/video-editor/lib/serialize.test.ts:602:      extensionId: 'com.example.shader',
src/tools/video-editor/lib/serialize.test.ts:603:      contributionId: 'clip-glow-shader',
src/tools/video-editor/lib/serialize.test.ts:604:      shaderId: 'shader.clipGlow',
src/tools/video-editor/lib/serialize.test.ts:611:      extensionId: 'com.example.shader',
src/tools/video-editor/lib/serialize.test.ts:612:      contributionId: 'grade-postprocess-shader',
src/tools/video-editor/lib/serialize.test.ts:613:      shaderId: 'shader.postGrade',
src/tools/video-editor/lib/serialize.test.ts:623:          id: 'clip-shader',
src/tools/video-editor/lib/serialize.test.ts:628:          app: { shader: clipShader, untouched: { survives: true } },
src/tools/video-editor/lib/serialize.test.ts:637:    expect(serialized.clips[0].app?.shader).toEqual(clipShader);
src/tools/video-editor/examples/extensions/flagship-local/FlagshipEffectComponent.tsx:51:}> = ({ children, durationInFrames, intensity: legacyIntensity, params }) => {
src/tools/video-editor/examples/extensions/flagship-local/FlagshipEffectComponent.tsx:57:  const glowIntensity = p?.intensity ?? legacyIntensity ?? 0.5;
src/tools/video-editor/lib/timeline-reader.ts:254:    && typeof (value as Record<string, unknown>).shaderId === 'string'
src/tools/video-editor/lib/timeline-reader.ts:266:    && typeof (value as Record<string, unknown>).shaderId === 'string'
src/tools/video-editor/lib/timeline-reader.ts:328:      const materialRefSummaries: TimelineMaterialRefSummary[] = [];
src/tools/video-editor/lib/timeline-reader.ts:330:      const shaderSummaries: TimelineShaderSummary[] = [];
src/tools/video-editor/lib/timeline-reader.ts:348:        const clipShader = isClipShaderMetadata(clip.app?.shader)
src/tools/video-editor/lib/timeline-reader.ts:349:          ? clip.app.shader
src/tools/video-editor/lib/timeline-reader.ts:352:          shaderSummaries.push({
src/tools/video-editor/lib/timeline-reader.ts:353:            id: `${clip.id}:shader:${clipShader.shaderId}`,
src/tools/video-editor/lib/timeline-reader.ts:354:            shaderId: clipShader.shaderId,
src/tools/video-editor/lib/timeline-reader.ts:468:        // ── Extract material refs ────────────────────────────────────
src/tools/video-editor/lib/timeline-reader.ts:472:            id: `material.asset.${clipMeta.asset}.${clip.id}`,
src/tools/video-editor/lib/timeline-reader.ts:478:          materialRefSummaries.push(clipMaterialRefs[0]);
src/tools/video-editor/lib/timeline-reader.ts:480:        // Check for generation material refs
src/tools/video-editor/lib/timeline-reader.ts:483:            id: `material.generation.${clip.id}`,
src/tools/video-editor/lib/timeline-reader.ts:488:          materialRefSummaries.push(clipMaterialRefs[clipMaterialRefs.length - 1]);
src/tools/video-editor/lib/timeline-reader.ts:542:            ? { materialRefs: clipMaterialRefs }
src/tools/video-editor/lib/timeline-reader.ts:573:      const postprocessShader = isPostprocessShaderMetadata(app.shaderPostprocess)
src/tools/video-editor/lib/timeline-reader.ts:574:        ? app.shaderPostprocess
src/tools/video-editor/lib/timeline-reader.ts:577:        shaderSummaries.push({
src/tools/video-editor/lib/timeline-reader.ts:578:          id: `postprocess:shader:${postprocessShader.shaderId}`,
src/tools/video-editor/lib/timeline-reader.ts:579:          shaderId: postprocessShader.shaderId,
src/tools/video-editor/lib/timeline-reader.ts:662:        materialRefs:
src/tools/video-editor/lib/timeline-reader.ts:663:          materialRefSummaries.length > 0 ? materialRefSummaries : undefined,
src/tools/video-editor/lib/timeline-reader.ts:666:        shaders:
src/tools/video-editor/lib/timeline-reader.ts:667:          shaderSummaries.length > 0 ? shaderSummaries : undefined,
src/tools/video-editor/lib/migrate.test.ts:7:describe('repairConfig — legacy pinnedShotGroups migration', () => {
src/tools/video-editor/lib/migrate.test.ts:32:        // `as unknown as ...` escape hatch — the runtime file has extra legacy fields
src/tools/video-editor/lib/migrate.test.ts:46:  it('strips legacy `start`/`children` and derives clipIds from children', () => {
src/tools/video-editor/lib/migrate.test.ts:70:  it('preserves clipIds when legacy `children` array is missing', () => {
src/tools/video-editor/lib/migrate.test.ts:73:    const legacyWithoutChildren = {
src/tools/video-editor/lib/migrate.test.ts:80:    config.pinnedShotGroups = [legacyWithoutChildren] as TimelineConfig['pinnedShotGroups'];
src/tools/video-editor/lib/migrate.test.ts:88:  it('round-trips via configToRows → rowsToConfig without emitting legacy fields', () => {
src/tools/video-editor/lib/migrate.test.ts:148:    expect(configOnly.issues.map((issue) => issue.code)).toContain('legacy_tracks_migrated');
src/tools/video-editor/compositions/VisualClip.test.tsx:13:import { VisualClip } from '@/tools/video-editor/compositions/VisualClip.tsx';
src/tools/video-editor/compositions/VisualClip.test.tsx:16:import type { ShaderEffectRegistryRecord, ShaderEffectRegistrySnapshot } from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/compositions/VisualClip.test.tsx:56:vi.mock('@/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts', () => ({
src/tools/video-editor/compositions/VisualClip.test.tsx:113:    renderability: {
src/tools/video-editor/compositions/VisualClip.test.tsx:129:function materialRef(overrides: Partial<RenderMaterialRef> = {}): RenderMaterialRef {
src/tools/video-editor/compositions/VisualClip.test.tsx:133:    locator: { kind: 'url', uri: 'https://example.test/material.png' },
src/tools/video-editor/compositions/VisualClip.test.tsx:134:    producerExtensionId: 'ext.materials',
src/tools/video-editor/compositions/VisualClip.test.tsx:136:    replacementPolicy: 'materialize-on-export',
src/tools/video-editor/compositions/VisualClip.test.tsx:141:function shaderRecord(overrides: Partial<ShaderEffectRegistryRecord> = {}): ShaderEffectRegistryRecord {
src/tools/video-editor/compositions/VisualClip.test.tsx:143:    shaderId: 'shader.preview.clip',
src/tools/video-editor/compositions/VisualClip.test.tsx:144:    ownerExtensionId: 'ext.shader',
src/tools/video-editor/compositions/VisualClip.test.tsx:145:    contributionId: 'ext.shader.clip',
src/tools/video-editor/compositions/VisualClip.test.tsx:156:    renderability: {
src/tools/video-editor/compositions/VisualClip.test.tsx:172:function shaderSnapshot(record: ShaderEffectRegistryRecord): ShaderEffectRegistrySnapshot {
src/tools/video-editor/compositions/VisualClip.test.tsx:176:    get: (shaderId, ownerExtensionId) => (
src/tools/video-editor/compositions/VisualClip.test.tsx:177:      shaderId === record.shaderId && ownerExtensionId === record.ownerExtensionId ? record : undefined
src/tools/video-editor/compositions/VisualClip.test.tsx:180:      lookup.shaderId === record.shaderId && lookup.ownerExtensionId === record.ownerExtensionId ? record : undefined
src/tools/video-editor/compositions/VisualClip.test.tsx:182:    has: (shaderId, ownerExtensionId) => shaderId === record.shaderId && ownerExtensionId === record.ownerExtensionId,
src/tools/video-editor/compositions/VisualClip.test.tsx:183:    hasByLookup: (lookup) => lookup.shaderId === record.shaderId && lookup.ownerExtensionId === record.ownerExtensionId,
src/tools/video-editor/compositions/VisualClip.test.tsx:222:  it('renders clip-local shader preview in browser mode and updates current clip time and frame', () => {
src/tools/video-editor/compositions/VisualClip.test.tsx:223:    const record = shaderRecord();
src/tools/video-editor/compositions/VisualClip.test.tsx:226:        shader: {
src/tools/video-editor/compositions/VisualClip.test.tsx:228:          extensionId: 'ext.shader',
src/tools/video-editor/compositions/VisualClip.test.tsx:229:          contributionId: 'ext.shader.clip',
src/tools/video-editor/compositions/VisualClip.test.tsx:230:          shaderId: 'shader.preview.clip',
src/tools/video-editor/compositions/VisualClip.test.tsx:242:        shaderRegistrySnapshot={shaderSnapshot(record)}
src/tools/video-editor/compositions/VisualClip.test.tsx:246:    expect(screen.getByTestId('visual-clip-shader-preview')).toHaveAttribute('data-shader-frame', '15');
src/tools/video-editor/compositions/VisualClip.test.tsx:247:    expect(screen.getByTestId('visual-clip-shader-preview')).toHaveAttribute('data-shader-time', '0.5');
src/tools/video-editor/compositions/VisualClip.test.tsx:250:      shaderId: 'shader.preview.clip',
src/tools/video-editor/compositions/VisualClip.test.tsx:263:        shaderRegistrySnapshot={shaderSnapshot(record)}
src/tools/video-editor/compositions/VisualClip.test.tsx:267:    expect(screen.getByTestId('visual-clip-shader-preview')).toHaveAttribute('data-shader-frame', '30');
src/tools/video-editor/compositions/VisualClip.test.tsx:268:    expect(screen.getByTestId('visual-clip-shader-preview')).toHaveAttribute('data-shader-time', '1');
src/tools/video-editor/compositions/VisualClip.test.tsx:272:  it('keeps Remotion export honest by showing clip shaders as unsupported instead of running WebGL preview', () => {
src/tools/video-editor/compositions/VisualClip.test.tsx:282:            shader: {
src/tools/video-editor/compositions/VisualClip.test.tsx:284:              extensionId: 'ext.shader',
src/tools/video-editor/compositions/VisualClip.test.tsx:285:              contributionId: 'ext.shader.clip',
src/tools/video-editor/compositions/VisualClip.test.tsx:286:              shaderId: 'shader.preview.clip',
src/tools/video-editor/compositions/VisualClip.test.tsx:292:        shaderRegistrySnapshot={shaderSnapshot(shaderRecord())}
src/tools/video-editor/compositions/VisualClip.test.tsx:296:    expect(screen.queryByTestId('visual-clip-shader-preview')).not.toBeInTheDocument();
src/tools/video-editor/compositions/VisualClip.test.tsx:298:    expect(screen.getByTestId('unsupported-clip-shader-export')).toHaveTextContent(
src/tools/video-editor/compositions/VisualClip.test.tsx:299:      'export requires a shader materializer that produces RenderMaterial',
src/tools/video-editor/compositions/VisualClip.test.tsx:303:  it('renders pending, materializing, and failed material placeholders with diagnostics', () => {
src/tools/video-editor/compositions/VisualClip.test.tsx:304:    const ref = materialRef();
src/tools/video-editor/compositions/VisualClip.test.tsx:310:        materialRefs={[ref]}
src/tools/video-editor/compositions/VisualClip.test.tsx:311:        materialStatuses={[{ materialRefId: 'mat-1', state: 'unbaked', message: 'Queued for materialization' }]}
src/tools/video-editor/compositions/VisualClip.test.tsx:315:    expect(screen.getByTestId('pending-material-placeholder')).toHaveAttribute('data-material-state', 'unbaked');
src/tools/video-editor/compositions/VisualClip.test.tsx:316:    expect(screen.getByText(/pending materialization: mat-1/)).toBeInTheDocument();
src/tools/video-editor/compositions/VisualClip.test.tsx:323:        materialRefs={[ref]}
src/tools/video-editor/compositions/VisualClip.test.tsx:324:        materialStatuses={[{ materialRefId: 'mat-1', state: 'stale', message: 'Refreshing bytes' }]}
src/tools/video-editor/compositions/VisualClip.test.tsx:327:    expect(screen.getByTestId('pending-material-placeholder')).toHaveAttribute('data-material-state', 'stale');
src/tools/video-editor/compositions/VisualClip.test.tsx:335:        materialRefs={[ref]}
src/tools/video-editor/compositions/VisualClip.test.tsx:336:        materialStatuses={[{ materialRefId: 'mat-1', state: 'missing' }]}
src/tools/video-editor/compositions/VisualClip.test.tsx:337:        materialDiagnostics={[{ id: 'diag-1', severity: 'error', materialRefId: 'mat-1', message: 'Materialization failed' }]}
src/tools/video-editor/compositions/VisualClip.test.tsx:340:    expect(screen.getByTestId('pending-material-placeholder')).toHaveAttribute('data-material-state', 'missing');
src/tools/video-editor/compositions/VisualClip.test.tsx:344:  it('renders concrete material-backed clips normally when material is resolved', async () => {
src/tools/video-editor/compositions/VisualClip.test.tsx:350:        materialRefs={[materialRef({ determinism: 'deterministic' })]}
src/tools/video-editor/compositions/VisualClip.test.tsx:351:        materialStatuses={[{ materialRefId: 'mat-1', state: 'resolved' }]}
src/tools/video-editor/compositions/VisualClip.test.tsx:356:    expect(screen.queryByTestId('pending-material-placeholder')).not.toBeInTheDocument();
src/tools/video-editor/lib/render-bounds.ts:66:  compositionWidth: number,
src/tools/video-editor/lib/render-bounds.ts:67:  compositionHeight: number,
src/tools/video-editor/lib/render-bounds.ts:69:  const right = Math.min(bounds.x + bounds.width, compositionWidth);
src/tools/video-editor/lib/render-bounds.ts:70:  const bottom = Math.min(bounds.y + bounds.height, compositionHeight);
src/tools/video-editor/lib/render-bounds.ts:89:  compositionWidth,
src/tools/video-editor/lib/render-bounds.ts:90:  compositionHeight,
src/tools/video-editor/lib/render-bounds.ts:96:  compositionWidth: number;
src/tools/video-editor/lib/render-bounds.ts:97:  compositionHeight: number;
src/tools/video-editor/lib/render-bounds.ts:103:  const renderBounds = computeRenderBounds(visibleBounds, compositionWidth, compositionHeight);
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:3:import { createWebGLShaderPreviewSurface } from '@/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts';
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:30:  shaderId: 'shader.preview.grade',
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:31:  extensionId: 'com.example.shader',
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:155:    shaderSource: vi.fn(),
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:157:    getShaderParameter: vi.fn((shader: MockShader, parameter: number): boolean => (
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:158:      parameter === COMPILE_STATUS && (shader.type === VERTEX_SHADER || fragmentCompile)
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:160:    getShaderInfoLog: vi.fn((shader: MockShader): string => (
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:161:      shader.type === FRAGMENT_SHADER ? options.fragmentInfoLog ?? '' : ''
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:384:        code: 'shader/texture-unsupported',
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:431:        code: 'shader/compile-error',
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:491:    expect(glAfterRestore.shaderSource).toHaveBeenCalledWith(expect.anything(), FRAGMENT_SOURCE);
src/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.test.ts:510:      code: 'shader/webgl-unavailable',
src/tools/video-editor/lib/render-bounds.test.ts:9:  it('intersects oversized bounds with the composition', () => {
src/tools/video-editor/lib/render-bounds.test.ts:38:      compositionWidth: 1920,
src/tools/video-editor/lib/render-bounds.test.ts:39:      compositionHeight: 1080,
src/tools/video-editor/lib/render-bounds.test.ts:59:  it('returns null when nothing remains visible after composition clipping', () => {
src/tools/video-editor/lib/render-bounds.test.ts:62:      compositionWidth: 1920,
src/tools/video-editor/lib/render-bounds.test.ts:63:      compositionHeight: 1080,
src/tools/video-editor/compositions/TimelineRenderer.dynamic.test.tsx:19:import { TimelineRenderer } from '@/tools/video-editor/compositions/TimelineRenderer';
src/tools/video-editor/compositions/TimelineRenderer.dynamic.test.tsx:40:vi.mock('@banodoco/timeline-composition/theme-api', async () => {
src/tools/video-editor/compositions/TimelineRenderer.dynamic.test.tsx:60:vi.mock('@/tools/video-editor/compositions/AudioAnalysisProvider', () => ({
src/tools/video-editor/lib/timeline-domain.transition.test.ts:4: * Covers: legacy malformed transitions, removed contributed transitions,
src/tools/video-editor/lib/timeline-domain.transition.test.ts:54:    renderability: {
src/tools/video-editor/lib/timeline-domain.transition.test.ts:111:    // @ts-expect-error - intentionally malformed for legacy test
src/tools/video-editor/lib/timeline-domain.transition.test.ts:124:    expect(issues.some((i) => i.code === 'legacy_transition_missing_type')).toBe(true);
src/tools/video-editor/lib/timeline-domain.transition.test.ts:152:    expect(issues.some((i) => i.code === 'legacy_transition_unresolvable')).toBe(true);
src/tools/video-editor/lib/timeline-domain.transition.test.ts:167:    expect(issues.some((i) => i.code === 'legacy_transition_removed_contributed')).toBe(true);
src/tools/video-editor/lib/timeline-domain.transition.test.ts:180:    expect(issues.some((i) => i.code === 'legacy_transition_removed_contributed')).toBe(true);
src/tools/video-editor/lib/timeline-domain.transition.test.ts:185:  it('materializes default params for transition with schema but no stored params', () => {
src/tools/video-editor/lib/timeline-domain.transition.test.ts:202:    // Transition should still exist but with materialized defaults
src/tools/video-editor/lib/timeline-domain.transition.test.ts:208:    expect(issues.some((i) => i.code === 'legacy_transition_params_repaired')).toBe(true);
src/tools/video-editor/lib/timeline-domain.transition.test.ts:265:    expect(issues.some((i) => i.code === 'legacy_transition_cleared')).toBe(true);
src/tools/video-editor/compositions/AudioTrack.test.tsx:5:import { AudioTrack } from '@/tools/video-editor/compositions/AudioTrack';
src/tools/video-editor/compositions/AudioTrack.test.tsx:40:vi.mock('@/tools/video-editor/compositions/MediaErrorBoundary', () => ({
src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts:550:          kind: 'render-material',
src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts:551:          ref: ref ?? `${createRefBase(session?.id ?? 'generated-frame-session-1')}:material`,
src/tools/video-editor/lib/renderRouter.ts:14://     in the architecture doc; uniform composition end-to-end inside
src/tools/video-editor/lib/renderRouter.ts:35:import { materializeSequenceConfig } from '@/tools/video-editor/sequences/materialize.ts';
src/tools/video-editor/lib/renderRouter.ts:39:} from '@/tools/video-editor/runtime/renderPlanner.ts';
src/tools/video-editor/lib/renderRouter.ts:44:import type { ContributionRenderability } from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/lib/renderRouter.ts:64:  readonly renderability: ContributionRenderability;
src/tools/video-editor/lib/renderRouter.ts:138:  // legacy clips). They route to the client renderer.
src/tools/video-editor/lib/renderRouter.ts:175:  return record.renderability.capabilities.some(
src/tools/video-editor/lib/renderRouter.ts:194:    readonly legacyReason?: RenderRouteDecision['reason'];
src/tools/video-editor/lib/renderRouter.ts:211:          message: options?.message ?? `Clip type "${clipType ?? 'legacy'}" cannot render on ${route}.`,
src/tools/video-editor/lib/renderRouter.ts:224:            message: options?.message ?? `Clip type "${clipType ?? 'legacy'}" cannot render on ${route}.`,
src/tools/video-editor/lib/renderRouter.ts:228:              legacyReason: options?.legacyReason,
src/tools/video-editor/lib/renderRouter.ts:245:      legacyReason: reason,
src/tools/video-editor/lib/renderRouter.ts:264:      legacyReason: reason,
src/tools/video-editor/lib/renderRouter.ts:280:      legacyReason: reason,
src/tools/video-editor/lib/renderRouter.ts:286:      legacyReason: reason,
src/tools/video-editor/lib/renderRouter.ts:336:    const requirementId = `router.clip.${index}.${clip.clipType ?? 'legacy'}`;
src/tools/video-editor/lib/renderRouter.ts:344:          ? 'missing-material'
src/tools/video-editor/lib/renderRouter.ts:345:          : 'materialization-failed',
src/tools/video-editor/lib/renderRouter.ts:605:      timeline: materializeSequenceConfig(request.resolvedConfig as Parameters<typeof materializeSequenceConfig>[0]),
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:13:} from '@/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts';
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:14:import type { ShaderEffectRegistryRecord } from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:17:  readonly shader: TimelineClipShaderMetadata;
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:43:  shader,
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:51:  testId = 'clip-shader-preview-canvas',
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:58:  const active = shader.enabled !== false
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:73:      shaderId: shader.shaderId,
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:74:      extensionId: shader.extensionId,
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:75:      contributionId: shader.contributionId,
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:79:      uniformValues: shader.uniforms,
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:81:      textureValues: shader.textures,
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:110:    shader.contributionId,
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:111:    shader.extensionId,
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:112:    shader.shaderId,
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:113:    shader.textures,
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:114:    shader.uniforms,
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:121:    surface.setUniformValues(shader.uniforms ?? {});
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:122:    surface.setTextureValues(shader.textures ?? {});
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:130:    shader.textures,
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:131:    shader.uniforms,
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:144:      data-shader-id={shader.shaderId}
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:145:      data-shader-frame={Math.floor(frame)}
src/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx:146:      data-shader-time={timeSeconds}
src/tools/video-editor/compositions/TimelineRenderer.tsx:13:import { AudioTrack } from '@/tools/video-editor/compositions/AudioTrack.tsx';
src/tools/video-editor/compositions/TimelineRenderer.tsx:14:import { AudioAnalysisProvider } from '@/tools/video-editor/compositions/AudioAnalysisProvider.tsx';
src/tools/video-editor/compositions/TimelineRenderer.tsx:15:import { EffectLayerSequence } from '@/tools/video-editor/compositions/EffectLayerSequence.tsx';
src/tools/video-editor/compositions/TimelineRenderer.tsx:16:import { TextClipSequence } from '@/tools/video-editor/compositions/TextClip.tsx';
src/tools/video-editor/compositions/TimelineRenderer.tsx:17:import { VisualClipSequence } from '@/tools/video-editor/compositions/VisualClip.tsx';
src/tools/video-editor/compositions/TimelineRenderer.tsx:18:import { UnknownClipPlaceholderSequence } from '@/tools/video-editor/compositions/UnknownClipPlaceholder.tsx';
src/tools/video-editor/compositions/TimelineRenderer.tsx:19:import { resolveTimelineRenderTheme } from '@/tools/video-editor/compositions/installed-themes.ts';
src/tools/video-editor/compositions/TimelineRenderer.tsx:24:import { materializeResolvedSequenceConfig } from '@/tools/video-editor/sequences/materialize.ts';
src/tools/video-editor/compositions/TimelineRenderer.tsx:30:} from '@banodoco/timeline-composition/theme-api';
src/tools/video-editor/compositions/TimelineRenderer.tsx:53:import type { LiveDataRegistry, LiveDataRegistrySnapshot } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
src/tools/video-editor/compositions/TimelineRenderer.tsx:55:import { PostprocessShaderPreviewCanvas } from '@/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx';
src/tools/video-editor/compositions/TimelineRenderer.tsx:56:import { useShaderEffectRegistrySnapshot } from '@/tools/video-editor/shaders/registry/index.ts';
src/tools/video-editor/compositions/TimelineRenderer.tsx:61:// `packages/timeline-composition/typescript/src/TimelineComposition.tsx`).
src/tools/video-editor/compositions/TimelineRenderer.tsx:72:    return true; // legacy clips with no clipType default to media-equivalent dispatch
src/tools/video-editor/compositions/TimelineRenderer.tsx:485:  liveDataRegistry: LiveDataRegistry,
src/tools/video-editor/compositions/TimelineRenderer.tsx:487:  const live = createClipRendererLiveProps([record], liveDataRegistry);
src/tools/video-editor/compositions/TimelineRenderer.tsx:514:  liveDataRegistry: LiveDataRegistry | undefined,
src/tools/video-editor/compositions/TimelineRenderer.tsx:521:  const source = liveDataRegistry?.getSource(record.binding.sourceId);
src/tools/video-editor/compositions/TimelineRenderer.tsx:530:  if (!liveDataRegistry || record.status !== 'active') {
src/tools/video-editor/compositions/TimelineRenderer.tsx:544:  const sample = resolveLiveFrameSample(record, clip, fps, liveDataRegistry);
src/tools/video-editor/compositions/TimelineRenderer.tsx:574:  liveDataRegistry: LiveDataRegistry | undefined,
src/tools/video-editor/compositions/TimelineRenderer.tsx:585:    if (!liveDataRegistry || !isActiveSourceBinding(sourceId)) return undefined;
src/tools/video-editor/compositions/TimelineRenderer.tsx:587:      const channel = liveDataRegistry.getChannelMetadata(channelId as LiveChannelDescriptor);
src/tools/video-editor/compositions/TimelineRenderer.tsx:595:      const channel = liveDataRegistry.getChannelMetadata(boundChannelId as LiveChannelDescriptor);
src/tools/video-editor/compositions/TimelineRenderer.tsx:599:    return liveDataRegistry.getSnapshot().channels.find((channel) => channel.sourceId === sourceId)?.channelId;
src/tools/video-editor/compositions/TimelineRenderer.tsx:603:    if (!liveDataRegistry || !isActiveSourceBinding(sourceId)) return undefined;
src/tools/video-editor/compositions/TimelineRenderer.tsx:604:    return liveDataRegistry.getSource(sourceId);
src/tools/video-editor/compositions/TimelineRenderer.tsx:612:    return resolvedChannelId ? liveDataRegistry?.getChannelMetadata(resolvedChannelId) : undefined;
src/tools/video-editor/compositions/TimelineRenderer.tsx:617:    return resolvedChannelId ? liveDataRegistry?.getLatestSample(resolvedChannelId) : undefined;
src/tools/video-editor/compositions/TimelineRenderer.tsx:626:    return resolvedChannelId ? liveDataRegistry?.getSampleAt(resolvedChannelId, sequenceNumber) : undefined;
src/tools/video-editor/compositions/TimelineRenderer.tsx:631:    return resolvedChannelId ? liveDataRegistry?.getSamples(resolvedChannelId) ?? Object.freeze([]) : Object.freeze([]);
src/tools/video-editor/compositions/TimelineRenderer.tsx:636:    return resolvedChannelId ? liveDataRegistry?.getSampleCount(resolvedChannelId) ?? 0 : 0;
src/tools/video-editor/compositions/TimelineRenderer.tsx:747:  liveDataRegistry?: LiveDataRegistry;
src/tools/video-editor/compositions/TimelineRenderer.tsx:748:}> = ({ clip, fps, records, liveDataRegistry }) => {
src/tools/video-editor/compositions/TimelineRenderer.tsx:751:  const result = resolveLiveFrameReadResult(records, clip, fps, liveDataRegistry);
src/tools/video-editor/compositions/TimelineRenderer.tsx:783:const UnsupportedPostprocessShaderExportBody: FC<{ shaderId: string }> = ({ shaderId }) => (
src/tools/video-editor/compositions/TimelineRenderer.tsx:785:    data-testid="unsupported-postprocess-shader-export"
src/tools/video-editor/compositions/TimelineRenderer.tsx:786:    data-shader-id={shaderId}
src/tools/video-editor/compositions/TimelineRenderer.tsx:813:      {`postprocess shader '${shaderId}' is browser-preview only; export requires a shader materializer that produces RenderMaterial`}
src/tools/video-editor/compositions/TimelineRenderer.tsx:850:  liveDataRegistry?: LiveDataRegistry;
src/tools/video-editor/compositions/TimelineRenderer.tsx:876:  liveDataRegistry,
src/tools/video-editor/compositions/TimelineRenderer.tsx:915:    live: createClipRendererLiveProps(liveBindingRecords, liveDataRegistry),
src/tools/video-editor/compositions/TimelineRenderer.tsx:949:  liveDataRegistry?: LiveDataRegistry;
src/tools/video-editor/compositions/TimelineRenderer.tsx:963:  liveDataRegistry,
src/tools/video-editor/compositions/TimelineRenderer.tsx:989:              liveDataRegistry={liveDataRegistry}
src/tools/video-editor/compositions/TimelineRenderer.tsx:1059:              // Check renderability: if preview route is explicitly blocked,
src/tools/video-editor/compositions/TimelineRenderer.tsx:1061:              const previewCap = extensionRecord.renderability.capabilities.find(
src/tools/video-editor/compositions/TimelineRenderer.tsx:1083:                  liveDataRegistry={liveDataRegistry}
src/tools/video-editor/compositions/TimelineRenderer.tsx:1189:  const liveDataRegistry = runtime?.liveDataRegistry;
src/tools/video-editor/compositions/TimelineRenderer.tsx:1191:    (listener) => liveDataRegistry?.subscribe(listener).dispose ?? (() => {}),
src/tools/video-editor/compositions/TimelineRenderer.tsx:1192:    () => liveDataRegistry?.getSnapshot(),
src/tools/video-editor/compositions/TimelineRenderer.tsx:1193:    () => liveDataRegistry?.getSnapshot(),
src/tools/video-editor/compositions/TimelineRenderer.tsx:1195:  const renderConfig = useMemo(() => materializeResolvedSequenceConfig(config), [config]);
src/tools/video-editor/compositions/TimelineRenderer.tsx:1196:  const shaderSnapshot = useShaderEffectRegistrySnapshot();
src/tools/video-editor/compositions/TimelineRenderer.tsx:1233:    ? shaderSnapshot.get(postprocessShader.shaderId, postprocessShader.extensionId)
src/tools/video-editor/compositions/TimelineRenderer.tsx:1235:  const { width: compositionWidth, height: compositionHeight } = parseResolution(renderConfig.output.resolution);
src/tools/video-editor/compositions/TimelineRenderer.tsx:1266:              liveDataRegistry={liveDataRegistry}
src/tools/video-editor/compositions/TimelineRenderer.tsx:1294:    liveDataRegistry,
src/tools/video-editor/compositions/TimelineRenderer.tsx:1308:              <UnsupportedPostprocessShaderExportBody shaderId={postprocessShader.shaderId} />
src/tools/video-editor/compositions/TimelineRenderer.tsx:1312:                shader={postprocessShader}
src/tools/video-editor/compositions/TimelineRenderer.tsx:1316:                width={compositionWidth}
src/tools/video-editor/compositions/TimelineRenderer.tsx:1317:                height={compositionHeight}
src/tools/video-editor/compositions/TimelineRenderer.tsx:1318:                testId="timeline-postprocess-shader-preview"
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:4:import { TimelineRenderer } from '@/tools/video-editor/compositions/TimelineRenderer';
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:15:} from '@/tools/video-editor/runtime/liveDataRegistry';
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:49:vi.mock('@banodoco/timeline-composition/theme-api', async () => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:133:vi.mock('@/tools/video-editor/compositions/AudioAnalysisProvider', async () => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:141:vi.mock('@/tools/video-editor/compositions/VisualClip', () => ({
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:148:vi.mock('@/tools/video-editor/compositions/TextClip', () => ({
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:155:vi.mock('@/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx', () => ({
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:160:        data-testid={String(props.testId ?? 'timeline-postprocess-shader-preview')}
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:161:        data-shader-id={String((props.shader as { shaderId?: string })?.shaderId ?? '')}
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:169:vi.mock('@/tools/video-editor/shaders/registry/index.ts', async () => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:170:  const actual = await vi.importActual<typeof import('@/tools/video-editor/shaders/registry/index.ts')>(
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:171:    '@/tools/video-editor/shaders/registry/index.ts',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:179:      getByLookup: (lookup: { shaderId: string; ownerExtensionId?: string }) => (
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:180:        mockShaderRegistryGet(lookup.shaderId, lookup.ownerExtensionId)
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:183:      hasByLookup: (lookup: { shaderId: string; ownerExtensionId?: string }) => (
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:184:        mockShaderRegistryHas(lookup.shaderId, lookup.ownerExtensionId)
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:190:vi.mock('@banodoco/timeline-composition/theme-api', async () => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:221:vi.mock('@banodoco/timeline-composition/registry.generated', async () => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:382:  it('materializes registry asset keys into component-facing preview URLs for registered sequences', () => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:490:  it('keeps trusted_v1, schema_sequence, and legacy clips on their normal preview paths', () => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:519:          id: 'clip-legacy',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:553:describe('TimelineRenderer postprocess shader preview', () => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:562:    extensionId: 'ext.shader',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:563:    contributionId: 'ext.shader.post',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:564:    shaderId: 'shader.preview.post',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:569:    shaderId: 'shader.preview.post',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:570:    ownerExtensionId: 'ext.shader',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:571:    contributionId: 'ext.shader.post',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:579:    renderability: {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:599:      app: { shaderPostprocess: postprocessShader },
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:602:    expect(screen.getByTestId('timeline-postprocess-shader-preview')).toHaveAttribute(
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:603:      'data-shader-id',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:604:      'shader.preview.post',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:607:      shader: postprocessShader,
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:614:    expect(screen.queryByTestId('unsupported-postprocess-shader-export')).not.toBeInTheDocument();
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:617:  it('keeps postprocess shaders preview-only during Remotion export rendering', () => {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:626:      app: { shaderPostprocess: postprocessShader },
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:630:    expect(screen.queryByTestId('timeline-postprocess-shader-preview')).not.toBeInTheDocument();
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:631:    expect(screen.getByTestId('unsupported-postprocess-shader-export')).toHaveTextContent(
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:632:      'export requires a shader materializer that produces RenderMaterial',
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:692:    renderability: {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:703:function runtimeWithLiveRegistry(liveDataRegistry?: LiveDataRegistry): VideoEditorRuntimeContextValue {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:717:    liveDataRegistry,
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:721:function renderWithLiveRegistry(config: ResolvedTimelineConfig, liveDataRegistry?: LiveDataRegistry) {
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:723:    <DataProviderWrapper value={runtimeWithLiveRegistry(liveDataRegistry)}>
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:8:} from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:18:  return `${lookup.ownerExtensionId ?? ''}\u0000${lookup.shaderId}`;
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:66:      'shader-effect-registry/dispose-failed',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:67:      `Shader "${entry.record.shaderId}" dispose failed: ${String(error)}`,
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:71:        shaderId: entry.record.shaderId,
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:89:    const shaderCmp = a.record.shaderId.localeCompare(b.record.shaderId);
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:90:    if (shaderCmp !== 0) return shaderCmp;
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:126:      get: (shaderId: string, ownerExtensionId?: string) => getByLookup({ shaderId, ownerExtensionId }),
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:128:      has: (shaderId: string, ownerExtensionId?: string) => hasByLookup({ shaderId, ownerExtensionId }),
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:151:      'shader-effect-registry/disposed',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:182:        'shader-effect-registry/duplicate-shader',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:183:        `Shader "${frozenRecord.shaderId}" is already registered for this owner. The previous record will be replaced.`,
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:187:          shaderId: frozenRecord.shaderId,
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:229:        'shader-effect-registry/update-missing-shader',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:230:        `Shader "${lookup.shaderId}" cannot be updated because it is not registered for this owner.`,
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:250:        'shader-effect-registry/update-shader-key-mismatch',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:251:        `Shader "${lookup.shaderId}" update returned mismatched owner or shader ID.`,
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:255:          shaderId: lookup.shaderId,
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:257:          nextShaderId: nextRecord.shaderId,
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:286:  function unregister(shaderId: string, ownerExtensionId?: string): void {
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:288:    removeEntry({ shaderId, ownerExtensionId });
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:313:  function resolve(shaderId: string, ownerExtensionId?: string): ShaderEffectRegistryRecord | undefined {
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts:314:    return getByLookup({ shaderId, ownerExtensionId });
src/tools/video-editor/compositions/ClipEffectsSnapshot.test.tsx:17:import { TextClip } from '@/tools/video-editor/compositions/TextClip.tsx';
src/tools/video-editor/compositions/ClipEffectsSnapshot.test.tsx:18:import { VisualClip } from '@/tools/video-editor/compositions/VisualClip.tsx';
src/tools/video-editor/compositions/ClipEffectsSnapshot.test.tsx:45:const renderability: EffectRegistryRecord['renderability'] = {
src/tools/video-editor/compositions/ClipEffectsSnapshot.test.tsx:88:    renderability,
src/tools/video-editor/compositions/ClipEffectsSnapshot.test.tsx:158:describe('clip composition effect snapshot resolution', () => {
src/tools/video-editor/compositions/ClipEffectsSnapshot.test.tsx:182:  it('VisualClip uses explicit snapshots and does not leak to the legacy singleton for same IDs', () => {
src/tools/video-editor/compositions/ClipEffectsSnapshot.test.tsx:183:    const LegacyShared = makeEffect('legacy-shared');
src/tools/video-editor/compositions/ClipEffectsSnapshot.test.tsx:199:    expect(screen.queryByTestId('legacy-shared')).not.toBeInTheDocument();
src/tools/video-editor/compositions/ClipEffectsSnapshot.test.tsx:203:    replaceEffectRegistry(new DynamicEffectRegistry({ shared: makeEffect('legacy-shared') }));
src/tools/video-editor/compositions/ClipEffectsSnapshot.test.tsx:216:    expect(screen.queryByTestId('legacy-shared')).not.toBeInTheDocument();
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:2:import { createShaderEffectRegistry } from '@/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts';
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:3:import type { ShaderEffectRegistryRecord } from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:9:  shaderId: string,
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:13:    shaderId,
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:14:    contributionId: `${shaderId}.contribution`,
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:15:    label: shaderId,
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:50:    renderability: {
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:63:          blockerReason: 'missing-material',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:69:          id: `${shaderId}.worker-export`,
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:72:          reason: 'missing-material',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:73:          message: 'Shader requires a materializer before export.',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:85:    const handle = registry.register(record('shader.glow'));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:87:    expect(registry.resolve('shader.glow', 'com.example.owner')?.source).toMatchObject({
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:91:    expect(registry.resolve('shader.glow')).toBeUndefined();
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:92:    expect(registry.resolve('shader.missing', 'com.example.owner')).toBeUndefined();
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:96:  it('allows the same shader ID from different owner scopes without replacement', () => {
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:100:    registry.register(record('shader.glow', {
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:105:    registry.register(record('shader.glow', {
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:112:    expect(registry.resolve('shader.glow', 'com.example.a')?.contributionId).toBe('a.glow');
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:113:    expect(registry.resolve('shader.glow', 'com.example.b')?.contributionId).toBe('b.glow');
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:120:    registry.register(record('shader.glow'));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:133:    expect(Object.isFrozen(snapshotA.records[0].renderability)).toBe(true);
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:134:    expect(Object.isFrozen(snapshotA.records[0].renderability.capabilities)).toBe(true);
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:135:    expect(Object.isFrozen(snapshotA.records[0].renderability.blockers)).toBe(true);
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:137:    registry.register(record('shader.zoom'));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:141:  it('orders snapshot records deterministically by owner, shader ID, then contribution ID', () => {
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:143:    registry.register(record('shader.z', { ownerExtensionId: 'com.example.b' }));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:144:    registry.register(record('shader.b', { ownerExtensionId: 'com.example.a', contributionId: 'a.b.2' }));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:145:    registry.register(record('shader.a', { ownerExtensionId: 'com.example.a' }));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:147:    expect(registry.getSnapshot().records.map((entry) => `${entry.ownerExtensionId}:${entry.shaderId}:${entry.contributionId}`))
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:149:        'com.example.a:shader.a:shader.a.contribution',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:150:        'com.example.a:shader.b:a.b.2',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:151:        'com.example.b:shader.z:shader.z.contribution',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:164:    registry.register(record('shader.glow'));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:170:    registry.register(record('shader.zoom'));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:178:    const handleA = registry.register(record('shader.glow', { dispose: disposeA }));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:179:    const handleB = registry.register(record('shader.glow', {
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:180:      contributionId: 'shader.glow.replacement',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:189:    expect(registry.resolve('shader.glow', 'com.example.owner')?.source).toMatchObject({
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:196:          code: 'shader-effect-registry/duplicate-shader',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:198:          contributionId: 'shader.glow.replacement',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:204:    expect(registry.resolve('shader.glow', 'com.example.owner')?.contributionId)
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:205:      .toBe('shader.glow.replacement');
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:211:    expect(registry.resolve('shader.glow', 'com.example.owner')).toBeUndefined();
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:218:    const handleA = registry.register(record('shader.hmr', { dispose: disposeA }));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:220:      { shaderId: 'shader.hmr', ownerExtensionId: 'com.example.owner' },
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:223:        contributionId: 'shader.hmr.replacement',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:233:    expect(registry.resolve('shader.hmr', 'com.example.owner')?.contributionId)
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:234:      .toBe('shader.hmr.replacement');
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:237:    expect(registry.resolve('shader.hmr', 'com.example.owner')).toBeDefined();
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:243:    expect(registry.resolve('shader.hmr', 'com.example.owner')).toBeUndefined();
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:246:  it('rejects updates that change the owner-scoped shader key and keeps the existing record', () => {
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:249:    registry.register(record('shader.keyed', { dispose: disposeA }));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:251:      { shaderId: 'shader.keyed', ownerExtensionId: 'com.example.owner' },
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:254:        shaderId: 'shader.other',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:258:    expect(registry.resolve('shader.keyed', 'com.example.owner')).toBeDefined();
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:259:    expect(registry.resolve('shader.other', 'com.example.owner')).toBeUndefined();
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:264:          code: 'shader-effect-registry/update-shader-key-mismatch',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:270:    expect(registry.resolve('shader.keyed', 'com.example.owner')).toBeDefined();
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:277:    registry.register(record('shader.glow', { ownerExtensionId: 'com.example.a', dispose: disposeA }));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:278:    registry.register(record('shader.glow', { ownerExtensionId: 'com.example.b', dispose: disposeB }));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:280:    registry.unregister('shader.glow', 'com.example.a');
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:281:    registry.unregister('shader.glow', 'com.example.a');
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:285:    expect(registry.resolve('shader.glow', 'com.example.a')).toBeUndefined();
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:286:    expect(registry.resolve('shader.glow', 'com.example.b')).toBeDefined();
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:294:    registry.register(record('shader.a1', { ownerExtensionId: 'com.example.a', dispose: disposeA1 }));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:295:    registry.register(record('shader.a2', { ownerExtensionId: 'com.example.a', dispose: disposeA2 }));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:296:    registry.register(record('shader.b', { ownerExtensionId: 'com.example.b', dispose: disposeB }));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:297:    registry.register(record('shader.b', { ownerExtensionId: 'com.example.b', dispose: disposeB }));
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:305:    expect(registry.resolve('shader.a1', 'com.example.a')).toBeUndefined();
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:306:    expect(registry.resolve('shader.a2', 'com.example.a')).toBeUndefined();
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:307:    expect(registry.resolve('shader.b', 'com.example.b')).toBeDefined();
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:308:    expect(registry.getSnapshot().diagnostics.some((d) => d.code === 'shader-effect-registry/duplicate-shader'))
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:314:    registry.register(record('shader.invalid', {
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:319:          code: 'shader/compile-failed',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:320:          message: 'Fragment shader failed to compile.',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:327:      renderability: {
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:342:    const entry = registry.getSnapshot().get('shader.invalid', 'com.example.owner');
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:345:      code: 'shader/compile-failed',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:361:    registry.register(record('shader.bad', {
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:378:          code: 'shader-effect-registry/dispose-failed',
src/tools/video-editor/shaders/registry/ShaderEffectRegistry.test.ts:380:          contributionId: 'shader.bad.contribution',
src/tools/video-editor/examples/extensions/__tests__/live-generated-frame-canary.test.ts:27:} from '@/tools/video-editor/runtime/liveDataRegistry';
src/tools/video-editor/examples/extensions/__tests__/live-generated-frame-canary.test.ts:148:  const agentRegistry = createAgentToolRegistry({ liveDataRegistry: liveRegistry });
src/tools/video-editor/examples/extensions/__tests__/live-generated-frame-canary.test.ts:381:    const material = test.controller.bakeRenderMaterial('generated-full-material');
src/tools/video-editor/examples/extensions/__tests__/live-generated-frame-canary.test.ts:383:    expect(material.success).toBe(true);
src/tools/video-editor/examples/extensions/__tests__/live-generated-frame-canary.test.ts:396:    expect(replacements(material)[0].renderMaterial).toEqual(expect.objectContaining({
src/tools/video-editor/examples/extensions/__tests__/live-generated-frame-canary.test.ts:397:      id: 'generated-full-material',
src/tools/video-editor/compositions/AudioAnalysisProvider.test.tsx:19:} from '@/tools/video-editor/compositions/AudioAnalysisProvider';
src/tools/video-editor/types/index.ts:70:// call sites that still narrow against the legacy four. Effect-id / theme-id
src/tools/video-editor/types/index.ts:191:  | 'render-material';
src/tools/video-editor/types/index.ts:239:  | 'material-ref';
src/tools/video-editor/types/index.ts:282:      kind: 'material-ref';
src/tools/video-editor/types/index.ts:298:// M13: Host-owned shader metadata persisted on the timeline. V1 stores one
src/tools/video-editor/types/index.ts:299:// clip-local shader in clip.app.shader and one postprocess shader in
src/tools/video-editor/types/index.ts:300:// config.app.shaderPostprocess.
src/tools/video-editor/types/index.ts:315:  shaderId: string;
src/tools/video-editor/types/index.ts:333:  shader?: TimelineClipShaderMetadata;
src/tools/video-editor/types/index.ts:337:  shaderPostprocess?: TimelinePostprocessShaderMetadata;
src/tools/video-editor/shaders/registry/index.ts:1:export { createShaderEffectRegistry } from '@/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts';
src/tools/video-editor/shaders/registry/index.ts:9:} from '@/tools/video-editor/shaders/registry/ShaderEffectRegistryContext.tsx';
src/tools/video-editor/shaders/registry/index.ts:18:} from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/compositions/AudioTrack.tsx:12:import { MediaErrorBoundary } from '@/tools/video-editor/compositions/MediaErrorBoundary.tsx';
src/tools/video-editor/shaders/registry/types.ts:12:import type { ContributionRenderability } from '@/tools/video-editor/runtime/renderability.ts';
src/tools/video-editor/shaders/registry/types.ts:26:  readonly shaderId: string;
src/tools/video-editor/shaders/registry/types.ts:39:  readonly materializer?: ShaderMaterializerDescriptor;
src/tools/video-editor/shaders/registry/types.ts:41:  readonly renderability: ContributionRenderability;
src/tools/video-editor/shaders/registry/types.ts:51:    shaderId: string,
src/tools/video-editor/shaders/registry/types.ts:55:  readonly has: (shaderId: string, ownerExtensionId?: string) => boolean;
src/tools/video-editor/shaders/registry/types.ts:68:  unregister(shaderId: string, ownerExtensionId?: string): void;
src/tools/video-editor/shaders/registry/types.ts:71:  resolve(shaderId: string, ownerExtensionId?: string): ShaderEffectRegistryRecord | undefined;
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:19:} from '@/tools/video-editor/examples/extensions/postprocess-shader-canary';
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:20:import { createShaderRegistrationService } from '@/tools/video-editor/runtime/shaderRegistrationService.ts';
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:22:import { createShaderEffectRegistry } from '@/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts';
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:27:} from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:28:import { createTimelinePostprocessShaderMetadata } from '@/tools/video-editor/lib/shader-catalog.ts';
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:29:import { PostprocessShaderPreviewCanvas } from '@/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx';
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:31:import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:134:    shaderSource: vi.fn(),
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:136:    getShaderParameter: vi.fn((_shader: MockShader, parameter: number): boolean => parameter === COMPILE_STATUS),
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:221:  const shaders = createShaderRegistrationService({
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:223:    shaderRegistry: registry,
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:234:    shaders,
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:270:      shaderPostprocess: createTimelinePostprocessShaderMetadata(record),
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:277:  const shader = config.app?.shaderPostprocess!;
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:279:    projectId: 'project-postprocess-shader-canary',
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:294:    shaders: [{
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:295:      id: `postprocess:shader:${shader.shaderId}`,
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:296:      shaderId: shader.shaderId,
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:298:      extensionId: shader.extensionId,
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:299:      contributionId: shader.contributionId,
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:300:      enabled: shader.enabled !== false,
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:311:describe('postprocess-shader-canary extension', () => {
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:312:  it('registers through the public shader SDK path and exposes runtime, diagnostics, and renderability contracts', () => {
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:321:    expect(runtime.shaders.map((shader) => shader.id)).toEqual([
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:328:      shaderId: POSTPROCESS_SHADER_CANARY_SHADER_ID,
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:354:    expect(record.renderability.capabilities).toEqual(expect.arrayContaining([
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:356:      expect.objectContaining({ route: 'browser-export', status: 'blocked', blockerReason: 'missing-material' }),
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:357:      expect.objectContaining({ route: 'worker-export', status: 'blocked', blockerReason: 'missing-material' }),
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:361:      shaderId: POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:366:          code: 'shader/uniform-unsupported',
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:373:        code: 'shaders/registered',
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:374:        detail: expect.objectContaining({ shaderId: POSTPROCESS_SHADER_CANARY_SHADER_ID }),
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:378:        code: 'shader/uniform-unsupported',
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:379:        detail: expect.objectContaining({ shaderId: POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_SHADER_ID }),
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:386:  it('materializes timeline metadata, inspector edits, deterministic browser preview output, and planner export blockers', () => {
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:397:    const shader = config.app!.shaderPostprocess!;
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:400:    expect(shader).toEqual(expect.objectContaining({
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:404:      shaderId: POSTPROCESS_SHADER_CANARY_SHADER_ID,
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:424:        postprocessShader={shader}
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:426:        shaderSnapshot={test.snapshot}
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:432:    fireEvent.click(screen.getByRole('button', { name: 'Apply shader' }));
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:435:    expect(applyEdit.mock.calls[0][0].resolvedConfig.app.shaderPostprocess).toEqual(expect.objectContaining({
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:436:      shaderId: POSTPROCESS_SHADER_CANARY_SHADER_ID,
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:445:        shader={shader}
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:456:      'data-shader-scope',
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:460:      'data-shader-id',
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:474:        shader={{ ...shader, uniforms: { ...shader.uniforms, intensity: 0.1 } }}
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:494:        reason: 'missing-material',
src/tools/video-editor/examples/extensions/__tests__/postprocess-shader-canary.integration.test.tsx:497:        message: `Shader "${POSTPROCESS_SHADER_CANARY_SHADER_ID}" cannot export because no shader materializer produced RenderMaterial for postprocess.`,
src/tools/video-editor/shaders/registry/ShaderEffectRegistryContext.tsx:10:import { createShaderEffectRegistry } from '@/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts';
src/tools/video-editor/shaders/registry/ShaderEffectRegistryContext.tsx:14:} from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/compositions/fallback/registry.generated.tsx:3:import type { RuntimeTheme } from '@/tools/video-editor/compositions/fallback/theme-api.tsx';
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:19:} from '@/tools/video-editor/examples/extensions/clip-local-shader-canary';
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:20:import { createShaderRegistrationService } from '@/tools/video-editor/runtime/shaderRegistrationService.ts';
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:22:import { createShaderEffectRegistry } from '@/tools/video-editor/shaders/registry/ShaderEffectRegistry.ts';
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:27:} from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:31:} from '@/tools/video-editor/lib/shader-catalog.ts';
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:32:import { ClipShaderPreviewCanvas } from '@/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx';
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:34:import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:42:vi.mock('@/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts', () => ({
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:76:  const shaders = createShaderRegistrationService({
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:78:    shaderRegistry: registry,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:89:    shaders,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:121:      shader: createTimelineClipShaderMetadata(record),
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:137:  const shader = clip.app?.shader!;
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:139:    projectId: 'project-shader-canary',
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:154:    shaders: [{
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:155:      id: `${clip.id}:shader:${shader.shaderId}`,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:156:      shaderId: shader.shaderId,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:159:      extensionId: shader.extensionId,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:160:      contributionId: shader.contributionId,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:161:      enabled: shader.enabled !== false,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:186:describe('clip-local-shader-canary extension', () => {
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:187:  it('registers through the public shader SDK path and exposes runtime, diagnostics, renderability, and picker contracts', () => {
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:196:    expect(runtime.shaders.map((shader) => shader.id)).toEqual([
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:203:      shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:228:    expect(record.renderability.capabilities).toEqual(expect.arrayContaining([
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:230:      expect.objectContaining({ route: 'browser-export', status: 'blocked', blockerReason: 'missing-material' }),
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:231:      expect.objectContaining({ route: 'worker-export', status: 'blocked', blockerReason: 'missing-material' }),
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:235:      shaderId: CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:240:          code: 'shader/uniform-unsupported',
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:247:        code: 'shaders/registered',
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:248:        detail: expect.objectContaining({ shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID }),
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:252:        code: 'shader/uniform-unsupported',
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:253:        detail: expect.objectContaining({ shaderId: CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID }),
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:269:        errorDiagnostics: [expect.objectContaining({ code: 'shader/uniform-unsupported' })],
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:276:  it('materializes timeline metadata defaults, inspector edits, preview input, and planner export blockers for the canary shader', () => {
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:283:    expect(clip.app?.shader).toEqual(expect.objectContaining({
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:287:      shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:308:        shaderSnapshot={test.snapshot}
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:314:    fireEvent.click(screen.getByRole('button', { name: 'Apply shader' }));
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:317:    expect(applyEdit.mock.calls[0][0].resolvedConfig.clips[0].app.shader).toEqual(expect.objectContaining({
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:318:      shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:329:        shader={clip.app!.shader!}
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:335:        testId="canary-clip-shader-preview"
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:339:    expect(screen.getByTestId('canary-clip-shader-preview')).toHaveAttribute(
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:340:      'data-shader-id',
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:344:      shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:349:      uniformValues: clip.app!.shader!.uniforms,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:351:      textureValues: clip.app!.shader!.textures,
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:362:        reason: 'missing-material',
src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx:365:        message: `Shader "${CLIP_LOCAL_SHADER_CANARY_SHADER_ID}" cannot export because no shader materializer produced RenderMaterial for clip "clip-canary".`,
src/tools/video-editor/contexts/DataProviderContext.tsx:24:import type { LiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
src/tools/video-editor/contexts/DataProviderContext.tsx:49:  /** M11: Provider-scoped live data registry for source lifecycle, channels, samples, and bake. */
src/tools/video-editor/contexts/DataProviderContext.tsx:50:  liveDataRegistry?: LiveDataRegistry;
src/tools/video-editor/shaders/compile/diagnostics.test.ts:8:} from '@/tools/video-editor/shaders/compile/diagnostics.ts';
src/tools/video-editor/shaders/compile/diagnostics.test.ts:11:  shaderId: 'shader.grade',
src/tools/video-editor/shaders/compile/diagnostics.test.ts:12:  extensionId: 'com.example.shader',
src/tools/video-editor/shaders/compile/diagnostics.test.ts:16:describe('shader compile diagnostics', () => {
src/tools/video-editor/shaders/compile/diagnostics.test.ts:69:          shaderId: CONTEXT.shaderId,
src/tools/video-editor/shaders/compile/diagnostics.test.ts:171:      "WARNING: 0:4(17): 'texture2D' : legacy function",
src/tools/video-editor/shaders/compile/diagnostics.test.ts:189:        message: "'texture2D' : legacy function",
src/tools/video-editor/shaders/compile/diagnostics.test.ts:207:      'Fragment shader is not compiled.',
src/tools/video-editor/shaders/compile/diagnostics.test.ts:228:        message: 'Fragment shader is not compiled.',
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:26:import { TimelineRenderer } from '@/tools/video-editor/compositions/TimelineRenderer';
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:40:} from '@/tools/video-editor/runtime/liveDataRegistry';
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:69:vi.mock('@banodoco/timeline-composition/theme-api', async () => {
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:92:vi.mock('@banodoco/timeline-composition/registry.generated', async () => ({
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:97:vi.mock('@/tools/video-editor/compositions/AudioAnalysisProvider', async () => ({
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:103:vi.mock('@/tools/video-editor/compositions/VisualClip', async () => ({
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:107:vi.mock('@/tools/video-editor/compositions/TextClip', async () => ({
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:234:function runtimeWithLiveRegistry(liveDataRegistry?: LiveDataRegistry): VideoEditorRuntimeContextValue {
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:248:    liveDataRegistry,
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:295:    renderability: {
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:320:  const agentRegistry = createAgentToolRegistry({ liveDataRegistry: liveRegistry });
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:383:describe('M11 live data bridge integration', () => {
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:569:    const material = test.controller.bakeRenderMaterial('generated-int-full-material');
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:571:    expect(material.success).toBe(true);
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:576:    expect(replacements(material)[0].renderMaterial).toEqual(expect.objectContaining({
src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx:577:      id: 'generated-int-full-material',
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:396:    bakeRenderMaterial(ref = `${sourceId}:render-material`) {
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:401:          kind: 'render-material',
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:22:} from '@/tools/video-editor/runtime/liveDataRegistry';
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:264:    const materialBake = controller.bakeRenderMaterial('webcam-material');
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:265:    expect(materialBake.success).toBe(true);
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:266:    expect(materialBake.targets[0].diagnostics?.[0].detail).toEqual(expect.objectContaining({
src/tools/video-editor/examples/extensions/__tests__/live-webcam-canary.test.ts:268:        id: 'webcam-material',
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:66:import { createShaderRegistrationService } from '@/tools/video-editor/runtime/shaderRegistrationService.ts';
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:67:import type { ShaderEffectRegistry } from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:79:import { createLiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:80:import type { LiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:95:} from '@/tools/video-editor/shaders/registry/index.ts';
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:175:  shaderRegistryRef,
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:178:  liveDataRegistryRef,
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:189:  shaderRegistryRef: React.MutableRefObject<ShaderEffectRegistry | null>;
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:192:  liveDataRegistryRef: React.MutableRefObject<LiveDataRegistry | null>;
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:316:        const shaderRegistry = shaderRegistryRef.current;
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:350:        const shadersService: ShaderRegistrationService | undefined = shaderRegistry
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:353:              shaderRegistry,
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:387:        const liveRegistry = liveDataRegistryRef.current;
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:402:          shadersService,
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:410:  }, [activeExtensionIds, diagnosticCollection, lifecycleHostRef, extensionRuntime, liveCreativeOverrides, commandRegistryRef, shaderRegistryRef]);
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:414:    const registry = liveDataRegistryRef.current;
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:422:  }, [diagnosticCollection, liveDataRegistryRef]);
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:461:                shaderRegistryRef={shaderRegistryRef}
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:605:  shaderRegistryRef,
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:609:  shaderRegistryRef: React.MutableRefObject<ShaderEffectRegistry | null>;
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:612:  const { registry: shaderRegistry, snapshot: shaderRegistrySnapshot } = useShaderEffectRegistryContext();
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:613:  shaderRegistryRef.current = shaderRegistry;
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:620:      shaderRegistry.unregisterOwner(extensionId);
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:625:  }, [diagnosticCollection, shaderRegistry, lifecycleHostRef]);
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:628:    const shaderDiagnostics = [
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:629:      ...shaderRegistrySnapshot.diagnostics,
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:630:      ...shaderRegistrySnapshot.records.flatMap((record) =>
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:636:            shaderId: record.shaderId,
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:645:      'shader-effect-registry',
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:646:      shaderDiagnostics,
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:649:  }, [activeExtensionIds, diagnosticCollection, shaderRegistrySnapshot]);
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:715:  // ---- M11: live data registry (one per provider mount) -----------------------
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:716:  const liveDataRegistryRef = useRef<LiveDataRegistry | null>(null);
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:717:  if (!liveDataRegistryRef.current) {
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:718:    liveDataRegistryRef.current = createLiveDataRegistry();
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:723:    lifecycleHostRef.current = createExtensionLifecycleHost(liveDataRegistryRef.current ?? undefined);
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:740:  // ---- M13: shader registry ref (registry is created by ShaderEffectRegistryProvider,
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:742:  const shaderRegistryRef = useRef<ShaderEffectRegistry | null>(null);
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:752:      liveDataRegistry: liveDataRegistryRef.current ?? undefined,
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:797:      // Dispose live data registry and permission service on provider unmount
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:798:      liveDataRegistryRef.current?.dispose();
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:859:    liveDataRegistry: liveDataRegistryRef.current ?? undefined,
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:895:        shaderRegistryRef={shaderRegistryRef}
src/tools/video-editor/contexts/EditorRuntimeProvider.tsx:898:        liveDataRegistryRef={liveDataRegistryRef}
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:20:  extensionId: 'com.example.shader',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:21:  contributionId: 'clip-glow-shader',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:22:  shaderId: 'shader.clipGlow',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:28:  extensionId: 'com.example.shader',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:29:  contributionId: 'clip-edge-shader',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:30:  shaderId: 'shader.clipEdge',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:35:  extensionId: 'com.example.shader',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:36:  contributionId: 'post-grade-shader',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:37:  shaderId: 'shader.postGrade',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:43:  extensionId: 'com.example.shader',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:44:  contributionId: 'post-vignette-shader',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:45:  shaderId: 'shader.postVignette',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:63:describe('timeline shader metadata domain helpers', () => {
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:64:  it('assigns and serializes one clip-local shader without disturbing existing clip app data', () => {
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:72:    expect(serializeTimelineConfigSnapshot(makeConfig(assigned.ok ? assigned.value : clip)).config.clips[0].app?.shader)
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:76:  it('refuses a second clip-local shader in the same clip scope', () => {
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:77:    const clip = makeClip({ app: { shader: clipShader } });
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:83:      expect(assigned.code).toBe('shader_scope_occupied');
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:85:      expect(assigned.existing.shaderId).toBe('shader.clipGlow');
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:86:      expect(assigned.incoming.shaderId).toBe('shader.clipEdge');
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:88:        'Cannot add shader "shader.clipEdge" to clip "clip-1" because shader "shader.clipGlow" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:94:  it('rejects stacked clip-local shader metadata during domain validation', () => {
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:97:        shader: [clipShader, otherClipShader],
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:106:        code: 'shader_scope_occupied',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:109:        path: 'clips.clip-1.app.shader',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:110:        message: 'Cannot add shader "shader.clipEdge" to clip "clip-1" because shader "shader.clipGlow" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:115:  it('assigns and serializes one postprocess shader in timeline app metadata', () => {
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:127:  it('refuses a second postprocess shader in the timeline scope', () => {
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:135:      expect(assigned.code).toBe('shader_scope_occupied');
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:137:      expect(assigned.existing.shaderId).toBe('shader.postGrade');
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:138:      expect(assigned.incoming.shaderId).toBe('shader.postVignette');
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:140:        'Cannot add postprocess shader "shader.postVignette" because postprocess shader "shader.postGrade" is already assigned. V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:146:  it('rejects stacked postprocess shader metadata during domain validation', () => {
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:157:        code: 'shader_scope_occupied',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:159:        path: 'app.shaderPostprocess',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:160:        message: 'Cannot add postprocess shader "shader.postVignette" because postprocess shader "shader.postGrade" is already assigned. V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.',
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:2: * clip-local-shader-canary — M13 clip-local WebGL shader canary.
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:4: * Exercises the public shader SDK path: manifest-declared ShaderContribution
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:5: * records, ctx.shaders.registerShader(), uniform defaults, textureRef binding
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:6: * metadata, registry diagnostics, preview-only renderability, picker metadata,
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:22:export const CLIP_LOCAL_SHADER_CANARY_EXTENSION_ID = 'com.reigh.examples.clip-local-shader-canary';
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:23:export const CLIP_LOCAL_SHADER_CANARY_SHADER_ID = 'shader.clipLocalCanary.grade';
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:24:export const CLIP_LOCAL_SHADER_CANARY_CONTRIBUTION_ID = 'clip-local-shader-canary';
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:25:export const CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID = 'shader.clipLocalCanary.diagnostic';
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:26:export const CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_CONTRIBUTION_ID = 'clip-local-shader-canary-diagnostic';
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:36:  readonly shaderId: string;
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:163:  kind: 'shader',
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:164:  shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:166:  description: 'Preview-only clip-local WebGL shader canary with editable uniforms and clip-frame texture input.',
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:182:  kind: 'shader',
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:183:  shaderId: CLIP_LOCAL_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:185:  description: 'Deliberately invalid clip-local shader contribution used to prove diagnostic surfacing.',
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:200:  handles.push(ctx.shaders.registerShader(
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:213:    handles.push(ctx.shaders.registerShader(
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:227:    code: 'clip-local-shader-canary/activated',
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:228:    message: 'Clip-local shader canary registered through ctx.shaders.',
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:230:      shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:237:    shaderId: CLIP_LOCAL_SHADER_CANARY_SHADER_ID,
src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts:262:      description: 'M13 canary for clip-local WebGL shader registration, uniforms, diagnostics, preview, picker, and planner behavior.',
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:183:      compositionSize: { width: 1920, height: 1080 },
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:509:    renderability: {
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:541:    renderability: {
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:567:    renderability: {
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:691:  it('uses an injected effect catalog without enabling the legacy effect query', () => {
src/tools/video-editor/contexts/VideoEditorProvider.test.tsx:3130:// Agent tools and live data registries are future-only scaffolding and are
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:2: * postprocess-shader-canary - M13 timeline postprocess WebGL shader canary.
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:4: * Exercises the public shader SDK path for timeline-scope postprocess shaders:
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:5: * manifest-declared ShaderContribution records, ctx.shaders.registerShader(),
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:7: * renderability, browser preview output, inspector persistence, and M12 planner
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:23:export const POSTPROCESS_SHADER_CANARY_EXTENSION_ID = 'com.reigh.examples.postprocess-shader-canary';
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:24:export const POSTPROCESS_SHADER_CANARY_SHADER_ID = 'shader.postprocessCanary.scanline';
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:25:export const POSTPROCESS_SHADER_CANARY_CONTRIBUTION_ID = 'postprocess-shader-canary';
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:26:export const POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_SHADER_ID = 'shader.postprocessCanary.diagnostic';
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:27:export const POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_CONTRIBUTION_ID = 'postprocess-shader-canary-diagnostic';
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:37:  readonly shaderId: string;
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:171:  kind: 'shader',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:172:  shaderId: POSTPROCESS_SHADER_CANARY_SHADER_ID,
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:174:  description: 'Preview-only timeline postprocess WebGL shader canary with editable uniforms.',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:190:  kind: 'shader',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:191:  shaderId: POSTPROCESS_SHADER_CANARY_DIAGNOSTIC_SHADER_ID,
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:193:  description: 'Deliberately invalid postprocess shader contribution used to prove diagnostic surfacing.',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:208:  handles.push(ctx.shaders.registerShader(
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:221:    handles.push(ctx.shaders.registerShader(
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:235:    code: 'postprocess-shader-canary/activated',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:236:    message: 'Postprocess shader canary registered through ctx.shaders.',
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:238:      shaderId: POSTPROCESS_SHADER_CANARY_SHADER_ID,
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:245:    shaderId: POSTPROCESS_SHADER_CANARY_SHADER_ID,
src/tools/video-editor/examples/extensions/postprocess-shader-canary/index.ts:270:      description: 'M13 canary for timeline postprocess WebGL shader registration, uniforms, diagnostics, preview, and planner behavior.',
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:12:import { useShaderEffectRegistryContext } from '@/tools/video-editor/shaders/registry/index.ts';
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:13:import type { ShaderEffectRegistryRecord } from '@/tools/video-editor/shaders/registry/types.ts';
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:18:import type { LiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:121:    renderability: {
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:141:function shaderRecord(
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:142:  shaderId: string,
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:148:    shaderId,
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:149:    contributionId: `${ownerExtensionId}.shader`,
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:150:    label: shaderId,
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:157:    renderability: {
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:184:    renderability: {
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:210:    renderability: {
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:250:  it('activates and cleans up shader registrations without changing effect or transition registration', async () => {
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:251:    const extensionId = 'com.example.shader-runtime';
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:252:    const effectId = 'shader-runtime-effect';
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:253:    const transitionId = 'shader-runtime-transition';
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:254:    const shaderId = 'shader.runtime.grade';
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:266:            id: 'shader-runtime.effect' as never,
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:272:            id: 'shader-runtime.transition' as never,
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:278:            id: 'shader-runtime.shader' as never,
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:279:            kind: 'shader',
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:280:            shaderId,
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:290:        const shaderHandle = ctx.shaders.registerShader(shaderId, SHADER_SOURCE);
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:294:            shaderHandle.dispose();
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:327:      expect(latestShaderRecords.map((record) => record.shaderId)).toContain(shaderId);
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:330:    expect(latestEffectRecords.map((record) => record.effectId)).not.toContain(shaderId);
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:332:      shaderId,
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:334:      contributionId: 'shader-runtime.shader',
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:338:    expect(latestShaderRecords[0].renderability.capabilities).toEqual(
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:351:      expect(latestShaderRecords.map((record) => record.shaderId)).not.toContain(shaderId);
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:523:    const shaderId = 'diagnostics.shader';
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:554:      const { registry: shaderRegistry } = useShaderEffectRegistryContext();
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:588:        const shader = shaderRegistry.register(shaderRecord(
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:589:          shaderId,
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:592:            id: 'diagnostics-shader-compile-error',
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:594:            code: 'shader/compile-error',
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:607:          shader.dispose();
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:611:      }, [enabled, registry, runtime.diagnosticCollection, shaderRegistry]);
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:650:          diagnostic.detail?.source === 'shader-effect-registry'
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:651:          && diagnostic.code === 'shader/compile-error'
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:653:          && diagnostic.contributionId === `${extensionId}.shader`
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:654:          && diagnostic.detail?.shaderId === shaderId
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:697:describe('EditorRuntimeProvider live data registry lifecycle', () => {
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:698:  it('instantiates liveDataRegistry and livePermissionService on mount and disposes on unmount', async () => {
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:704:      capturedRegistry = runtime.liveDataRegistry ?? null;
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:807:      capturedRegistry = runtime.liveDataRegistry ?? null;
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:875:      capturedRegistry = runtime.liveDataRegistry ?? null;
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1629:// (effects, transitions, shaders, clip-types) correctly scopes cleanup to
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1632:// Agent tools and live data registries are future-only scaffolding and are
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1715:describe('EditorRuntimeProvider shader registry scoped cleanup', () => {
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1716:  it('clears only the removed extension shader records and preserves unrelated extension records', async () => {
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1717:    const EXT_A = 'com.example.shader-ext-a';
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1718:    const EXT_B = 'com.example.shader-ext-b';
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1719:    const shaderAId = 'shader.ext.a.grade';
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1720:    const shaderBId = 'shader.ext.b.blur';
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1746:        const hA = registry.register(shaderRecord(shaderAId, EXT_A, [], disposeA));
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1747:        const hB = registry.register(shaderRecord(shaderBId, EXT_B, [], disposeB));
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1774:      expect(latestRecords.map((r) => r.shaderId)).toEqual(
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1775:        expect.arrayContaining([shaderAId, shaderBId]),
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1783:      // Extension A's shader record must be removed
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1784:      expect(latestRecords.map((r) => r.shaderId)).not.toContain(shaderAId);
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1787:    // Extension B's shader record must be preserved
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1788:    expect(latestRecords.map((r) => r.shaderId)).toContain(shaderBId);
src/tools/video-editor/contexts/EditorRuntimeProvider.test.tsx:1789:    expect(latestRecords.map((r) => r.shaderId)).toHaveLength(1);
src/tools/video-editor/lib/timeline-patch.ts:9: * Compilation materializes a validated patch through the existing
src/tools/video-editor/lib/timeline-patch.ts:848:  const shader = (app as { shader?: unknown }).shader;
src/tools/video-editor/lib/timeline-patch.ts:849:  return shader && typeof shader === 'object' && !Array.isArray(shader)
src/tools/video-editor/lib/timeline-patch.ts:850:    ? shader as TimelineClipShaderMetadata
src/tools/video-editor/lib/timeline-patch.ts:880:  /** The fully-materialized nextData after applying the patch. */
src/tools/video-editor/lib/timeline-patch.ts:898: * materializes through the existing config/row serialization paths, and
src/tools/video-editor/lib/timeline-patch.ts:1124:              diag('error', 'timeline-patch/shader-scope-occupied', assignment.message, {
src/tools/video-editor/lib/timeline-patch.ts:1130:                  existingShaderId: assignment.existing.shaderId,
src/tools/video-editor/lib/timeline-patch.ts:1131:                  incomingShaderId: assignment.incoming.shaderId,
src/tools/video-editor/lib/timeline-patch.ts:1500:        // handled at materialization time via buildDataFromCurrentRegistry.
src/tools/video-editor/lib/timeline-patch.ts:1572:              diag('error', 'timeline-patch/shader-scope-occupied', assignment.message, {
src/tools/video-editor/lib/timeline-patch.ts:1578:                  existingShaderId: assignment.existing.shaderId,
src/tools/video-editor/lib/timeline-patch.ts:1579:                  incomingShaderId: assignment.incoming.shaderId,
src/tools/video-editor/examples/extensions/clip-local-shader-canary/reigh-extension.json:3:    "id": "com.reigh.examples.clip-local-shader-canary",
src/tools/video-editor/examples/extensions/clip-local-shader-canary/reigh-extension.json:6:    "description": "M13 canary for clip-local WebGL shader registration, uniforms, diagnostics, preview, picker, and planner behavior.",
src/tools/video-editor/examples/extensions/clip-local-shader-canary/reigh-extension.json:10:        "id": "clip-local-shader-canary",
src/tools/video-editor/examples/extensions/clip-local-shader-canary/reigh-extension.json:11:        "kind": "shader",
src/tools/video-editor/examples/extensions/clip-local-shader-canary/reigh-extension.json:12:        "shaderId": "shader.clipLocalCanary.grade",
src/tools/video-editor/examples/extensions/clip-local-shader-canary/reigh-extension.json:14:        "description": "Preview-only clip-local WebGL shader canary with editable uniforms and clip-frame texture input.",
src/tools/video-editor/examples/extensions/clip-local-shader-canary/reigh-extension.json:107:        "id": "clip-local-shader-canary-diagnostic",
src/tools/video-editor/examples/extensions/clip-local-shader-canary/reigh-extension.json:108:        "kind": "shader",
src/tools/video-editor/examples/extensions/clip-local-shader-canary/reigh-extension.json:109:        "shaderId": "shader.clipLocalCanary.diagnostic",
src/tools/video-editor/examples/extensions/clip-local-shader-canary/reigh-extension.json:111:        "description": "Deliberately invalid clip-local shader contribution used to prove diagnostic surfacing.",
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:10: *   - Fake baked asset/material refs (material/artifact result family)
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:45:const MATERIAL_TOOL_ID = 'canary.material';
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:121:          { ref: 'fake-material-001', kind: 'material', label: 'Generated material X' },
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:234: * Material/artifact tool handler — returns fake baked asset/material refs.
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:236:const materialHandler: AgentToolHandler = (
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:252:      ref: `canary-baked-material-${Date.now()}`,
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:253:      kind: 'material',
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:254:      label: 'Canary baked material (fake)',
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:278:      message: `Generated ${refs.length} fake baked asset/material/placeholder refs.`,
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:292:    family: 'material/artifact',
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:295:      'Fake baked asset/material/placeholder refs demonstrating the material/artifact result family. ' +
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:412:      'sample channel, proposal-ready output, fake baked asset/material refs, and diagnostics.',
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:429:        id: 'canary-material-contribution' as any,
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:434:          'Fake material/artifact tool returning placeholder baked asset and material refs.',
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:435:        resultFamilies: ['material/artifact'],
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:470:    // Register material tool handler
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:471:    const matHandle = ctx.agentTools!.registerTool(MATERIAL_TOOL_ID, materialHandler);
src/tools/video-editor/lib/render-bounds.validation.test.ts:10:const composition = { width: 1920, height: 1080 };
src/tools/video-editor/lib/render-bounds.validation.test.ts:16:  const overlayBounds = computeRenderBounds(visibleBounds, composition.width, composition.height);
src/tools/video-editor/lib/render-bounds.validation.test.ts:20:    compositionWidth: composition.width,
src/tools/video-editor/lib/render-bounds.validation.test.ts:21:    compositionHeight: composition.height,
src/tools/video-editor/lib/render-bounds.validation.test.ts:61:      compositionWidth: composition.width,
src/tools/video-editor/lib/render-bounds.validation.test.ts:62:      compositionHeight: composition.height,
src/tools/video-editor/lib/render-bounds.validation.test.ts:78:      compositionWidth: composition.width,
src/tools/video-editor/lib/render-bounds.validation.test.ts:79:      compositionHeight: composition.height,
src/tools/video-editor/lib/render-bounds.validation.test.ts:86:      compositionWidth: composition.width,
src/tools/video-editor/lib/render-bounds.validation.test.ts:87:      compositionHeight: composition.height,
src/tools/video-editor/lib/render-bounds.validation.test.ts:93:      computeRenderBounds(getVisibleBoundsFromCrop(fullBounds, tighterCrop), composition.width, composition.height),
src/tools/video-editor/lib/render-bounds.validation.test.ts:96:      computeRenderBounds(getVisibleBoundsFromCrop(fullBounds, looserCrop), composition.width, composition.height),
src/tools/video-editor/shaders/compile/diagnostics.ts:12:  UNIFORM_UNSUPPORTED: 'shader/uniform-unsupported',
src/tools/video-editor/shaders/compile/diagnostics.ts:13:  TEXTURE_UNSUPPORTED: 'shader/texture-unsupported',
src/tools/video-editor/shaders/compile/diagnostics.ts:14:  COMPILE_ERROR: 'shader/compile-error',
src/tools/video-editor/shaders/compile/diagnostics.ts:15:  LINK_ERROR: 'shader/link-error',
src/tools/video-editor/shaders/compile/diagnostics.ts:35:  readonly shaderId?: string;
src/tools/video-editor/shaders/compile/diagnostics.ts:114:      'shader',
src/tools/video-editor/shaders/compile/diagnostics.ts:115:      code.replace(/^shader\//, ''),
src/tools/video-editor/shaders/compile/diagnostics.ts:117:      context.contributionId ?? context.shaderId ?? 'anonymous',
src/tools/video-editor/shaders/compile/diagnostics.ts:127:      ...(context.shaderId ? { shaderId: context.shaderId } : {}),
src/tools/video-editor/shaders/compile/diagnostics.ts:144:    `Unsupported shader uniform schema at ${index === 'root' ? 'uniforms' : `uniforms[${index}]`}: ${reason}.`,
src/tools/video-editor/shaders/compile/diagnostics.ts:165:    `Unsupported shader texture schema at ${index === 'root' ? 'textures' : `textures[${index}]`}: ${reason}.`,
src/tools/video-editor/shaders/compile/webgl-adapter.ts:6:} from '@/tools/video-editor/shaders/compile/diagnostics.ts';
src/tools/video-editor/shaders/compile/webgl-adapter.ts:64:      'shader',
src/tools/video-editor/shaders/compile/webgl-adapter.ts:66:      code.replace(/^shader\//, ''),
src/tools/video-editor/shaders/compile/webgl-adapter.ts:68:      context.contributionId ?? context.shaderId ?? 'anonymous',
src/tools/video-editor/shaders/compile/webgl-adapter.ts:77:      ...(context.shaderId ? { shaderId: context.shaderId } : {}),
src/tools/video-editor/shaders/compile/webgl-adapter.ts:100:  shader: WebGLShader | null,
src/tools/video-editor/shaders/compile/webgl-adapter.ts:102:  if (!shader) return;
src/tools/video-editor/shaders/compile/webgl-adapter.ts:104:    gl.deleteShader(shader);
src/tools/video-editor/shaders/compile/webgl-adapter.ts:124:  shaderType: number,
src/tools/video-editor/shaders/compile/webgl-adapter.ts:128:): { shader: WebGLShader | null; diagnostics: readonly Diagnostic[] } {
src/tools/video-editor/shaders/compile/webgl-adapter.ts:129:  const shader = gl.createShader(shaderType);
src/tools/video-editor/shaders/compile/webgl-adapter.ts:130:  if (!shader) {
src/tools/video-editor/shaders/compile/webgl-adapter.ts:132:      shader: null,
src/tools/video-editor/shaders/compile/webgl-adapter.ts:138:          `WebGL could not create a ${phase} shader.`,
src/tools/video-editor/shaders/compile/webgl-adapter.ts:145:  gl.shaderSource(shader, source);
src/tools/video-editor/shaders/compile/webgl-adapter.ts:146:  gl.compileShader(shader);
src/tools/video-editor/shaders/compile/webgl-adapter.ts:148:  if (gl.getShaderParameter(shader, gl.COMPILE_STATUS) === true) {
src/tools/video-editor/shaders/compile/webgl-adapter.ts:149:    return { shader, diagnostics: Object.freeze([]) };
src/tools/video-editor/shaders/compile/webgl-adapter.ts:152:  const infoLog = gl.getShaderInfoLog(shader);
src/tools/video-editor/shaders/compile/webgl-adapter.ts:153:  const diagnostics = parseWebGLInfoLog(infoLog || `${phase} shader compilation failed.`, {
src/tools/video-editor/shaders/compile/webgl-adapter.ts:158:  return { shader, diagnostics };
src/tools/video-editor/shaders/compile/webgl-adapter.ts:176:          'WebGL could not create a shader program.',
src/tools/video-editor/shaders/compile/webgl-adapter.ts:203:    shaderId: input.shaderId,
src/tools/video-editor/shaders/compile/webgl-adapter.ts:217:          'shader/webgl-unavailable',
src/tools/video-editor/shaders/compile/webgl-adapter.ts:218:          'WebGL shader compilation requires a browser canvas.',
src/tools/video-editor/shaders/compile/webgl-adapter.ts:233:          'shader/webgl-unavailable',
src/tools/video-editor/shaders/compile/webgl-adapter.ts:234:          'No WebGL rendering context is available for shader compilation.',
src/tools/video-editor/shaders/compile/webgl-adapter.ts:254:    vertexShader = vertexResult.shader;
src/tools/video-editor/shaders/compile/webgl-adapter.ts:264:    fragmentShader = fragmentResult.shader;
src/tools/video-editor/shaders/compile/webgl-adapter.ts:333:          `WebGL shader compilation failed: ${String(error)}`,
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:3:    "id": "com.reigh.examples.postprocess-shader-canary",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:6:    "description": "M13 canary for timeline postprocess WebGL shader registration, uniforms, diagnostics, preview, and planner behavior.",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:10:        "id": "postprocess-shader-canary",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:11:        "kind": "shader",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:12:        "shaderId": "shader.postprocessCanary.scanline",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:14:        "description": "Preview-only timeline postprocess WebGL shader canary with editable uniforms.",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:113:        "id": "postprocess-shader-canary-diagnostic",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:114:        "kind": "shader",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:115:        "shaderId": "shader.postprocessCanary.diagnostic",
src/tools/video-editor/examples/extensions/postprocess-shader-canary/reigh-extension.json:117:        "description": "Deliberately invalid postprocess shader contribution used to prove diagnostic surfacing.",
src/tools/video-editor/hooks/useRenderState.ts:12:} from '@/tools/video-editor/runtime/outputFormatRegistry.ts';
src/tools/video-editor/hooks/useRenderState.ts:25:} from '@/tools/video-editor/runtime/renderPlanner.ts';
src/tools/video-editor/hooks/useRenderState.ts:128:            : diag.detail?.shaderId
src/tools/video-editor/hooks/useRenderState.ts:129:              ? ` shader "${diag.detail.shaderId}"`
src/tools/video-editor/hooks/useRenderState.ts:145:            : diag.detail?.shaderId
src/tools/video-editor/hooks/useRenderState.ts:146:              ? ` shader "${diag.detail.shaderId}"`
src/tools/video-editor/hooks/useRenderState.ts:163:          : finding.detail?.shaderId
src/tools/video-editor/hooks/useRenderState.ts:164:            ? `"${finding.detail.shaderId}"`
src/tools/video-editor/hooks/useRenderState.ts:182:    detail.effectType ?? detail.transitionType ?? detail.clipType ?? detail.shaderId ?? index,
src/tools/video-editor/hooks/useRenderState.ts:196:  if (diagnostic.code.includes('shader')) {
src/tools/video-editor/hooks/useRenderState.ts:197:    return 'missing-material';
src/tools/video-editor/hooks/useRenderState.ts:237:function outputFormatsForPlanning(extensionRuntime: ExtensionRuntime | undefined): readonly VideoEditorOutputFormatDescriptor[] {
src/tools/video-editor/hooks/useRenderState.ts:238:  const outputFormats = extensionRuntime?.outputFormats
src/tools/video-editor/hooks/useRenderState.ts:239:    ?? extensionRuntime?.config?.outputFormats
src/tools/video-editor/hooks/useRenderState.ts:241:  return outputFormats.map((format) => ({
src/tools/video-editor/hooks/useRenderState.ts:271:/** Categorize output format descriptors into compile-only and render-dependent groups. */
src/tools/video-editor/hooks/useRenderState.ts:273:  outputFormats: readonly VideoEditorOutputFormatDescriptor[],
src/tools/video-editor/hooks/useRenderState.ts:280:  for (const fmt of outputFormats) {
src/tools/video-editor/hooks/useRenderState.ts:312:    const outputFormats = outputFormatsForPlanning(extensionRuntime);
src/tools/video-editor/hooks/useRenderState.ts:313:    return categorizeExportFormats(outputFormats);
src/tools/video-editor/hooks/useRenderState.ts:514:    const plannerOutputFormats = outputFormatsForPlanning(extensionRuntime);
src/tools/video-editor/hooks/useRenderState.ts:516:      outputFormats: plannerOutputFormats,
src/tools/video-editor/hooks/useRenderState.ts:519:        outputFormatId: formatId,
src/tools/video-editor/hooks/useRenderState.ts:524:            id: `planner.outputFormat.${formatId}.disabled`,
src/tools/video-editor/hooks/useRenderState.ts:531:            detail: { source: 'output-format', outputFormatId: formatId },
src/tools/video-editor/hooks/useRenderState.ts:539:      const blocker = outputPlan.blockers.find((candidate) => candidate.id === `planner.outputFormat.${formatId}.disabled`)
src/tools/video-editor/hooks/useTimelineCommit.ts:106:  materializeData: (
src/tools/video-editor/hooks/useTimelineCommit.ts:155:  const materializeData = useCallback((
src/tools/video-editor/hooks/useTimelineCommit.ts:284:      const baseNextData = materializeData(
src/tools/video-editor/hooks/useTimelineCommit.ts:334:  }, [commitData, materializeData, withPinnedShotGroups]);
src/tools/video-editor/hooks/useTimelineCommit.ts:447:    materializeData,
src/tools/video-editor/hooks/useTimelineState.ts:81:  compositionSize,
src/tools/video-editor/hooks/useTimelineState.ts:119:  compositionSize: { width: number; height: number };
src/tools/video-editor/hooks/useTimelineState.ts:175:    compositionSize,
src/tools/video-editor/hooks/useTimelineState.ts:262:    compositionSize,
src/tools/video-editor/hooks/useTimelineState.ts:497:    compositionSize,
src/tools/video-editor/hooks/useTimelineState.ts:757:    compositionSize,
src/tools/video-editor/hooks/useTimelineState.ts:811:    compositionSize: editor.compositionSize,
src/tools/video-editor/examples/extensions/agent-tools-canary/reigh-extension.json:6:    "description": "Fake long-running generation canary demonstrating the M10 agent tool SDK surface: progress reporting, cancellation, preview-only GenerationSession, placeholder sample channel, proposal-ready output, fake baked asset/material refs, and diagnostics.",
src/tools/video-editor/examples/extensions/agent-tools-canary/reigh-extension.json:19:        "id": "canary-material-contribution",
src/tools/video-editor/examples/extensions/agent-tools-canary/reigh-extension.json:21:        "toolId": "canary.material",
src/tools/video-editor/examples/extensions/agent-tools-canary/reigh-extension.json:23:        "description": "Fake material/artifact tool returning placeholder baked asset and material refs.",
src/tools/video-editor/examples/extensions/agent-tools-canary/reigh-extension.json:24:        "resultFamilies": ["material/artifact"],
src/tools/video-editor/hooks/useTimelinePersistence.ts:33:   * authoritative on refresh.
src/tools/video-editor/hooks/useDerivedTimeline.ts:10:  compositionWidth: number;
src/tools/video-editor/hooks/useDerivedTimeline.ts:11:  compositionHeight: number;
src/tools/video-editor/hooks/useDerivedTimeline.ts:53:  const compositionSize = useMemo(() => {
src/tools/video-editor/hooks/useDerivedTimeline.ts:69:      compositionWidth: Math.max(1, width),
src/tools/video-editor/hooks/useDerivedTimeline.ts:70:      compositionHeight: Math.max(1, height),
src/tools/video-editor/hooks/useDerivedTimeline.ts:88:    compositionSize,
src/tools/video-editor/hooks/usePollSync.test.ts:47:  it('preserves legacy poll decisions except for the intentional save-in-flight rejection', () => {
src/tools/video-editor/hooks/usePollSync.test.ts:76:                const legacyReason = getLegacyPollRejectionReason({
src/tools/video-editor/hooks/usePollSync.test.ts:85:                  : legacyReason;
src/tools/video-editor/hooks/useClipDrag.softtag.test.tsx:3:// T9 regression tests for soft-tag grouped drag. The legacy useClipDrag.test.tsx
src/tools/video-editor/hooks/timelineStore.ts:162:    compositionSize: { width: 0, height: 0 },
src/tools/video-editor/hooks/useTimelineState.types.ts:109:  compositionSize: { width: number; height: number };
src/tools/video-editor/hooks/useClientRender.ts:4:import { TimelineRenderer } from '@/tools/video-editor/compositions/TimelineRenderer.tsx';
src/tools/video-editor/hooks/useClientRender.ts:14:  compositionWidth: number;
src/tools/video-editor/hooks/useClientRender.ts:15:  compositionHeight: number;
src/tools/video-editor/hooks/useClientRender.ts:228:      const width = metadata.compositionWidth % 2 === 0 ? metadata.compositionWidth : metadata.compositionWidth + 1;
src/tools/video-editor/hooks/useClientRender.ts:229:      const height = metadata.compositionHeight % 2 === 0 ? metadata.compositionHeight : metadata.compositionHeight + 1;
src/tools/video-editor/hooks/useClientRender.ts:251:      // renderMediaOnWeb expects a composition object
src/tools/video-editor/hooks/useClientRender.ts:252:      const composition = {
src/tools/video-editor/hooks/useClientRender.ts:262:        composition,
src/tools/video-editor/hooks/useAssetOperations.test.tsx:86:        throw new Error('legacy uploadAsset should not be called');
src/tools/video-editor/hooks/useClipDrag.ts:432:            liveData: effectiveDataRef.current,
src/tools/video-editor/hooks/useEffectResources.test.tsx:368:      renderability: {
src/tools/video-editor/hooks/useEffectResources.test.tsx:421:        renderability: {
src/tools/video-editor/hooks/useEffectResources.test.tsx:433:  it('registry records carry renderability through to catalog resources', () => {
src/tools/video-editor/hooks/useEffectResources.test.tsx:434:    const renderability = {
src/tools/video-editor/hooks/useEffectResources.test.tsx:447:      renderability,
src/tools/video-editor/hooks/useEffectResources.test.tsx:452:    expect(catalog.effects[0].renderability).toEqual(renderability);
src/tools/video-editor/hooks/useEffectResources.test.tsx:462:      renderability: {
src/tools/video-editor/hooks/useEffectResources.test.tsx:481:      renderability: {
src/tools/video-editor/hooks/useEffectResources.test.tsx:511:      renderability: {
src/tools/video-editor/hooks/useEffectResources.test.tsx:539:      renderability: {
src/tools/video-editor/hooks/useEffectResources.test.tsx:556:      renderability: {
src/tools/video-editor/hooks/useEffectResources.test.tsx:574:        renderability: {
src/tools/video-editor/hooks/useEffectRegistry.ts:15:  legacyDbEffectsToRegistryRecords,
src/tools/video-editor/hooks/useEffectRegistry.ts:28: * Dual-read registry: registers effects from both the legacy `effects` table
src/tools/video-editor/hooks/useEffectRegistry.ts:60:      console.warn('[EffectRegistry] legacy DB effects are deprecated; migrate to resource-based effects via useEffectResources.');
src/tools/video-editor/hooks/useEffectRegistry.ts:69:      ...legacyDbEffectsToRegistryRecords(
src/tools/video-editor/hooks/useShotGroups.test.ts:79:  it('derives group start and children from the live row actions instead of legacy projection fields', () => {
src/tools/video-editor/hooks/useClipDrag.helpers.ts:127:  liveData: TimelineData | null;
src/tools/video-editor/hooks/useClipDrag.helpers.ts:346:  liveData,
src/tools/video-editor/hooks/useClipDrag.helpers.ts:369:    if (liveData) {
src/tools/video-editor/hooks/useClipDrag.helpers.ts:375:          liveData,
src/tools/video-editor/hooks/useClipDrag.helpers.ts:401:                  liveData.config.pinnedShotGroups,
src/tools/video-editor/hooks/useClipDrag.helpers.ts:426:          liveData,
src/tools/video-editor/hooks/useClipDrag.helpers.ts:436:          const { nextRows, metaUpdates, nextClipOrder } = applyMultiDragMoves(liveData, moves);
src/tools/video-editor/hooks/useClipDrag.helpers.ts:439:                liveData.config.pinnedShotGroups,
src/tools/video-editor/hooks/useRenderState.test.tsx:141:    renderability: {
src/tools/video-editor/hooks/useRenderState.test.tsx:248:    const browserExport = record.renderability.capabilities.find((capability) => capability.route === 'browser-export');
src/tools/video-editor/hooks/useRenderState.test.tsx:351:        compositionWidth: 1920,
src/tools/video-editor/hooks/useRenderState.test.tsx:352:        compositionHeight: 1080,
src/tools/video-editor/hooks/useRenderState.test.tsx:484:    it('does not let timeline shader preview metadata bypass export readiness', async () => {
src/tools/video-editor/hooks/useRenderState.test.tsx:485:      const message = 'Shader "shader.preview.clip" cannot export because no shader materializer produced RenderMaterial for clip "c1".';
src/tools/video-editor/hooks/useRenderState.test.tsx:492:            code: 'export/unrenderable-shader',
src/tools/video-editor/hooks/useRenderState.test.tsx:494:            extensionId: 'ext.shader',
src/tools/video-editor/hooks/useRenderState.test.tsx:495:            contributionId: 'ext.shader.clip',
src/tools/video-editor/hooks/useRenderState.test.tsx:498:              shaderId: 'shader.preview.clip',
src/tools/video-editor/hooks/useRenderState.test.tsx:499:              shaderScope: 'clip',
src/tools/video-editor/hooks/useRenderState.test.tsx:506:            id: 'export.shader.clip.c1.shader.preview.clip.browser-export.missing-materializer',
src/tools/video-editor/hooks/useRenderState.test.tsx:509:            reason: 'missing-material',
src/tools/video-editor/hooks/useRenderState.test.tsx:512:            extensionId: 'ext.shader',
src/tools/video-editor/hooks/useRenderState.test.tsx:513:            contributionId: 'ext.shader.clip',
src/tools/video-editor/hooks/useRenderState.test.tsx:515:              shaderId: 'shader.preview.clip',
src/tools/video-editor/hooks/useRenderState.test.tsx:516:              shaderScope: 'clip',
src/tools/video-editor/hooks/useRenderState.test.tsx:531:            shader: {
src/tools/video-editor/hooks/useRenderState.test.tsx:533:              extensionId: 'ext.shader',
src/tools/video-editor/hooks/useRenderState.test.tsx:534:              contributionId: 'ext.shader.clip',
src/tools/video-editor/hooks/useRenderState.test.tsx:535:              shaderId: 'shader.preview.clip',
src/tools/video-editor/hooks/useRenderState.test.tsx:1264:          compositionWidth: 1920,
src/tools/video-editor/hooks/useRenderState.test.tsx:1265:          compositionHeight: 1080,
src/tools/video-editor/hooks/useRenderState.test.tsx:1310:          compositionWidth: 1920,
src/tools/video-editor/hooks/useRenderState.test.tsx:1311:          compositionHeight: 1080,
src/tools/video-editor/hooks/useRenderState.test.tsx:1700:      expect(snapshot.get('preview-only-provider-effect')?.renderability.capabilities).toEqual(
src/tools/video-editor/hooks/useRenderState.test.tsx:1756:vi.mock('@/tools/video-editor/runtime/outputFormatRegistry', async () => {
src/tools/video-editor/hooks/useRenderState.test.tsx:1757:  const actual = await vi.importActual('@/tools/video-editor/runtime/outputFormatRegistry');
src/tools/video-editor/hooks/useRenderState.test.tsx:1795:  it('categorizes output formats into compile-only and render-dependent from extension runtime config', () => {
src/tools/video-editor/hooks/useRenderState.test.tsx:1801:        outputFormats: [
src/tools/video-editor/hooks/useRenderState.test.tsx:1823:  it('returns empty arrays when no output formats are registered', () => {
src/tools/video-editor/hooks/useRenderState.test.tsx:1829:        outputFormats: [],
src/tools/video-editor/hooks/useRenderState.test.tsx:1870:        outputFormats: [
src/tools/video-editor/hooks/useRenderState.test.tsx:1910:        outputFormats: [
src/tools/video-editor/hooks/useRenderState.test.tsx:1939:        outputFormats: [
src/tools/video-editor/hooks/useRenderState.test.tsx:1967:        outputFormats: [
src/tools/video-editor/hooks/useRenderState.test.tsx:1997:        outputFormats: [
src/tools/video-editor/hooks/useRenderState.test.tsx:2020:  it('rejects disabled output formats from planner diagnostics when disabledReason is provided', async () => {
src/tools/video-editor/hooks/useRenderState.test.tsx:2026:        outputFormats: [
src/tools/video-editor/hooks/useRenderState.test.tsx:2054:        outputFormats: [
src/tools/video-editor/hooks/useRenderState.test.tsx:2086:        outputFormats: [
src/tools/video-editor/hooks/useRenderState.test.tsx:2115:        outputFormats: [
src/tools/video-editor/hooks/useRenderState.test.tsx:2150:        outputFormats: [
src/tools/video-editor/hooks/useRenderState.test.tsx:2182:        outputFormats: [
src/tools/video-editor/hooks/useRenderState.test.tsx:2225:        outputFormats: [
src/tools/video-editor/hooks/useRenderState.test.tsx:2264:        outputFormats: [
src/tools/video-editor/hooks/useRenderState.test.tsx:2302:        outputFormats: [
src/tools/video-editor/hooks/useRenderState.test.tsx:2346:        outputFormats: [
src/tools/video-editor/hooks/useRenderState.test.tsx:2354:      { fps: 30, durationInFrames: 30, compositionWidth: 1920, compositionHeight: 1080 },
src/tools/video-editor/hooks/useRenderState.test.tsx:2384:        outputFormats: [
src/tools/video-editor/sequences/registry.ts:3:} from '@banodoco/timeline-composition/registry.generated';
src/tools/video-editor/sequences/registry.ts:9:} from '@/tools/video-editor/compositions/installed-themes.ts';
src/tools/video-editor/sequences/materialize.ts:24:const materializeAssetListParam = (
src/tools/video-editor/sequences/materialize.ts:56:export const materializeSequenceParams = (
src/tools/video-editor/sequences/materialize.ts:76:    const materialized = materializeAssetListParam(params[param.key], registry);
src/tools/video-editor/sequences/materialize.ts:77:    if (materialized === null) continue;
src/tools/video-editor/sequences/materialize.ts:79:    nextParams[componentParam] = materialized;
src/tools/video-editor/sequences/materialize.ts:91:    const materialized = materializeAssetListParam(params[keysParam], registry);
src/tools/video-editor/sequences/materialize.ts:92:    if (materialized === null || materialized.length === 0) continue;
src/tools/video-editor/sequences/materialize.ts:94:    nextParams[urlsParam] = materialized;
src/tools/video-editor/sequences/materialize.ts:101:export const materializeSequenceClip = (
src/tools/video-editor/sequences/materialize.ts:105:  const nextParams = materializeSequenceParams(clip.clipType, clip.params, registry);
src/tools/video-editor/sequences/materialize.ts:115:export const materializeSequenceConfig = <
src/tools/video-editor/sequences/materialize.ts:128:    const nextClip = materializeSequenceClip(clip, registry);
src/tools/video-editor/sequences/materialize.ts:145:export const materializeResolvedSequenceConfig = (
src/tools/video-editor/sequences/materialize.ts:147:): ResolvedTimelineConfig => materializeSequenceConfig(config);
src/tools/video-editor/sequences/components/TitleCardSequence.tsx:3:import { useTheme, type RuntimeTheme } from '@banodoco/timeline-composition/theme-api';
src/tools/video-editor/sequences/metadata.ts:211:        description: 'Registry asset keys to materialize into preview image URLs.',
src/tools/video-editor/sequences/materialize.test.ts:3:import { materializeResolvedSequenceConfig } from '@/tools/video-editor/sequences/materialize';
src/tools/video-editor/sequences/materialize.test.ts:46:describe('sequence asset materialization', () => {
src/tools/video-editor/sequences/materialize.test.ts:49:    const materialized = materializeResolvedSequenceConfig(config);
src/tools/video-editor/sequences/materialize.test.ts:51:    expect(materialized).not.toBe(config);
src/tools/video-editor/sequences/materialize.test.ts:52:    expect(materialized.clips[0]).not.toBe(config.clips[0]);
src/tools/video-editor/sequences/materialize.test.ts:53:    expect(materialized.clips[0].params).toMatchObject({
src/tools/video-editor/sequences/materialize.test.ts:87:    expect(materializeResolvedSequenceConfig(config)).toBe(config);
src/tools/video-editor/sequences/materialize.test.ts:90:  it('materializes image-jump imageAssetKeys into component image URLs', () => {
src/tools/video-editor/sequences/materialize.test.ts:108:    const materialized = materializeResolvedSequenceConfig(config);
src/tools/video-editor/sequences/materialize.test.ts:110:    expect(materialized.clips[0].params).toMatchObject({
src/tools/video-editor/sequences/compileSequenceComponent.tsx:15:import { composeAnimations, useTheme, type RuntimeTheme } from '@banodoco/timeline-composition/theme-api';
src/tools/video-editor/sequences/components/ImageJumpSequence.tsx:3:import { useTheme, type RuntimeTheme } from '@banodoco/timeline-composition/theme-api';
src/tools/video-editor/compositions/VisualClip.tsx:18:import { MediaErrorBoundary } from '@/tools/video-editor/compositions/MediaErrorBoundary.tsx';
src/tools/video-editor/compositions/VisualClip.tsx:31:import type { RenderPlannerMaterialStatus } from '@/tools/video-editor/runtime/renderPlanner.ts';
src/tools/video-editor/compositions/VisualClip.tsx:32:import { ClipShaderPreviewCanvas } from '@/tools/video-editor/shaders/preview/ClipShaderPreviewCanvas.tsx';
src/tools/video-editor/compositions/VisualClip.tsx:36:} from '@/tools/video-editor/shaders/registry/index.ts';
src/tools/video-editor/compositions/VisualClip.tsx:154:const UnsupportedClipShaderExportBody: FC<{ clipId: string; shaderId: string }> = ({ clipId, shaderId }) => (
src/tools/video-editor/compositions/VisualClip.tsx:156:    data-testid="unsupported-clip-shader-export"
src/tools/video-editor/compositions/VisualClip.tsx:158:    data-shader-id={shaderId}
src/tools/video-editor/compositions/VisualClip.tsx:183:      {`shader '${shaderId}' is browser-preview only — export requires a shader materializer that produces RenderMaterial`}
src/tools/video-editor/compositions/VisualClip.tsx:194:  shaderRegistrySnapshot?: ShaderEffectRegistrySnapshot;
src/tools/video-editor/compositions/VisualClip.tsx:195:  materialRefs?: readonly RenderMaterialRef[];
src/tools/video-editor/compositions/VisualClip.tsx:196:  materialStatuses?: readonly RenderPlannerMaterialStatus[];
src/tools/video-editor/compositions/VisualClip.tsx:197:  materialDiagnostics?: readonly CapabilityFinding[];
src/tools/video-editor/compositions/VisualClip.tsx:203:  compositionWidth: number,
src/tools/video-editor/compositions/VisualClip.tsx:204:  compositionHeight: number,
src/tools/video-editor/compositions/VisualClip.tsx:222:        width: clip.width ?? compositionWidth,
src/tools/video-editor/compositions/VisualClip.tsx:223:        height: clip.height ?? compositionHeight,
src/tools/video-editor/compositions/VisualClip.tsx:247:  compositionWidth: number,
src/tools/video-editor/compositions/VisualClip.tsx:248:  compositionHeight: number,
src/tools/video-editor/compositions/VisualClip.tsx:259:    width: clip.width ?? compositionWidth,
src/tools/video-editor/compositions/VisualClip.tsx:260:    height: clip.height ?? compositionHeight,
src/tools/video-editor/compositions/VisualClip.tsx:268:function materialRefsForClip(
src/tools/video-editor/compositions/VisualClip.tsx:270:  materialRefs: readonly RenderMaterialRef[] | undefined,
src/tools/video-editor/compositions/VisualClip.tsx:272:  if (materialRefs && materialRefs.length > 0) return materialRefs;
src/tools/video-editor/compositions/VisualClip.tsx:274:  const refs = app?.materialRefs ?? clip.params?.materialRefs;
src/tools/video-editor/compositions/VisualClip.tsx:278:function statusForMaterial(material: RenderMaterialRef, statuses: readonly RenderPlannerMaterialStatus[] | undefined): RenderPlannerMaterialStatus {
src/tools/video-editor/compositions/VisualClip.tsx:279:  return statuses?.find((status) => status.materialRefId === material.id)
src/tools/video-editor/compositions/VisualClip.tsx:280:    ?? { materialRefId: material.id, state: material.determinism === 'deterministic' ? 'resolved' : 'unbaked' };
src/tools/video-editor/compositions/VisualClip.tsx:288:  const { width: compositionWidth, height: compositionHeight } = useVideoConfig();
src/tools/video-editor/compositions/VisualClip.tsx:329:    const style = getClipBoxStyle(clip, track, compositionWidth, compositionHeight);
src/tools/video-editor/compositions/VisualClip.tsx:361:    width: clip.width ?? compositionWidth,
src/tools/video-editor/compositions/VisualClip.tsx:362:    height: clip.height ?? compositionHeight,
src/tools/video-editor/compositions/VisualClip.tsx:364:  const intrinsicSize = getIntrinsicMediaSize(clip, compositionWidth, compositionHeight);
src/tools/video-editor/compositions/VisualClip.tsx:373:    compositionWidth,
src/tools/video-editor/compositions/VisualClip.tsx:374:    compositionHeight,
src/tools/video-editor/compositions/VisualClip.tsx:441:  shaderRegistrySnapshot,
src/tools/video-editor/compositions/VisualClip.tsx:442:  materialRefs,
src/tools/video-editor/compositions/VisualClip.tsx:443:  materialStatuses,
src/tools/video-editor/compositions/VisualClip.tsx:444:  materialDiagnostics,
src/tools/video-editor/compositions/VisualClip.tsx:450:  const shaderSnapshot = shaderRegistrySnapshot ?? providerShaderRegistryContext?.snapshot;
src/tools/video-editor/compositions/VisualClip.tsx:451:  const { width: compositionWidth, height: compositionHeight } = useVideoConfig();
src/tools/video-editor/compositions/VisualClip.tsx:466:  const pendingMaterial = materialRefsForClip(clip, materialRefs)
src/tools/video-editor/compositions/VisualClip.tsx:467:    .map((material) => ({ material, status: statusForMaterial(material, materialStatuses) }))
src/tools/video-editor/compositions/VisualClip.tsx:474:        material={pendingMaterial.material}
src/tools/video-editor/compositions/VisualClip.tsx:476:        diagnostics={materialDiagnostics?.filter((diagnostic) =>
src/tools/video-editor/compositions/VisualClip.tsx:477:          diagnostic.materialRefId === pendingMaterial.material.id || diagnostic.clipId === clip.id)}
src/tools/video-editor/compositions/VisualClip.tsx:484:  const shader = getTimelineClipShader(clip);
src/tools/video-editor/compositions/VisualClip.tsx:485:  const shaderRecord = shader
src/tools/video-editor/compositions/VisualClip.tsx:486:    ? shaderSnapshot?.get(shader.shaderId, shader.extensionId)
src/tools/video-editor/compositions/VisualClip.tsx:489:    shader
src/tools/video-editor/compositions/VisualClip.tsx:490:    && shader.enabled !== false
src/tools/video-editor/compositions/VisualClip.tsx:491:    && shaderRecord
src/tools/video-editor/compositions/VisualClip.tsx:496:    shader
src/tools/video-editor/compositions/VisualClip.tsx:497:    && shader.enabled !== false
src/tools/video-editor/compositions/VisualClip.tsx:536:      {renderUnsupportedShaderExport && shader ? (
src/tools/video-editor/compositions/VisualClip.tsx:537:        <UnsupportedClipShaderExportBody clipId={clip.id} shaderId={shader.shaderId} />
src/tools/video-editor/compositions/VisualClip.tsx:539:      {renderBrowserShaderPreview && shader && shaderRecord ? (
src/tools/video-editor/compositions/VisualClip.tsx:541:          shader={shader}
src/tools/video-editor/compositions/VisualClip.tsx:542:          record={shaderRecord}
src/tools/video-editor/compositions/VisualClip.tsx:545:          width={compositionWidth}
src/tools/video-editor/compositions/VisualClip.tsx:546:          height={compositionHeight}
src/tools/video-editor/compositions/VisualClip.tsx:547:          testId="visual-clip-shader-preview"
src/tools/video-editor/compositions/VisualClip.tsx:579:  shaderRegistrySnapshot,
src/tools/video-editor/compositions/VisualClip.tsx:580:  materialRefs,
src/tools/video-editor/compositions/VisualClip.tsx:581:  materialStatuses,
src/tools/video-editor/compositions/VisualClip.tsx:582:  materialDiagnostics,
src/tools/video-editor/compositions/VisualClip.tsx:608:          shaderRegistrySnapshot={shaderRegistrySnapshot}
src/tools/video-editor/compositions/VisualClip.tsx:609:          materialRefs={materialRefs}
src/tools/video-editor/compositions/VisualClip.tsx:610:          materialStatuses={materialStatuses}
src/tools/video-editor/compositions/VisualClip.tsx:611:          materialDiagnostics={materialDiagnostics}
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:2:import { SHADER_DIAGNOSTIC_CODES } from '@/tools/video-editor/shaders/compile/diagnostics.ts';
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:3:import { compileWebGLShaderProgram } from '@/tools/video-editor/shaders/compile/webgl-adapter.ts';
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:11:  shaderId: 'shader.grade',
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:12:  extensionId: 'com.example.shader',
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:58:  const shaderSources = new Map<MockShader, string>();
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:66:    shaderSource: vi.fn((shader: MockShader, source: string): void => {
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:67:      shaderSources.set(shader, source);
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:70:    getShaderParameter: vi.fn((shader: MockShader, parameter: number): boolean => {
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:72:      return shader.type === VERTEX_SHADER ? vertexCompile : fragmentCompile;
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:74:    getShaderInfoLog: vi.fn((shader: MockShader): string => (
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:75:      shader.type === VERTEX_SHADER
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:106:    expect(gl.shaderSource).toHaveBeenNthCalledWith(1, expect.objectContaining({ type: VERTEX_SHADER }), VERTEX_SOURCE);
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:107:    expect(gl.shaderSource).toHaveBeenNthCalledWith(2, expect.objectContaining({ type: FRAGMENT_SHADER }), FRAGMENT_SOURCE);
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:139:          shaderId: CONTEXT.shaderId,
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:155:      linkInfoLog: 'ERROR: program link failed: fragment shader varying mismatch',
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:171:        message: 'program link failed: fragment shader varying mismatch',
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:173:          shaderId: CONTEXT.shaderId,
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:175:          infoLogLine: 'ERROR: program link failed: fragment shader varying mismatch',
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:195:        code: 'shader/webgl-unavailable',
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:197:        message: 'WebGL shader compilation requires a browser canvas.',
src/tools/video-editor/shaders/compile/webgl-adapter.test.ts:199:          shaderId: CONTEXT.shaderId,
src/tools/video-editor/sequences/headlessRender.ts:42:import { composeAnimations, useTheme } from '@banodoco/timeline-composition/theme-api';
src/tools/video-editor/hooks/useEditorSync.test.ts:174:    compositionSize: { width: 1280, height: 720 },

codex
Initial file listing shows the staged initiative directory only has `chain.yaml`; the named `NORTHSTAR.md` and `prep.md` do not appear under that path. I’m checking the plan file and the actual planner/reader/router files next, with line numbers.
exec
/bin/zsh -lc "nl -ba src/tools/video-editor/runtime/renderPlanner.ts | sed -n '1,360p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
     1	import {
     2	  getCapabilityRequirements,
     3	  type CapabilityFinding,
     4	  type CapabilityRequirement,
     5	  type DeterminismStatus,
     6	  type ProcessStatus,
     7	  type RenderBlocker,
     8	  type RenderBlockerReason,
     9	  type RenderMaterialRef,
    10	  type RenderRoute,
    11	  RENDER_ROUTES,
    12	  type TimelineSnapshot,
    13	  type TimelineShaderSummary,
    14	} from '@reigh/editor-sdk';
    15	import type {
    16	  ExtensionRuntime,
    17	  VideoEditorOutputFormatDescriptor,
    18	  VideoEditorPlannerBlockerDescriptor,
    19	  VideoEditorPlannerNextActionDescriptor,
    20	  VideoEditorProcessDescriptor,
    21	  VideoEditorProcessRequirementDescriptor,
    22	  VideoEditorRouteRequirementDescriptor,
    23	  VideoEditorShaderDescriptor,
    24	} from '@/tools/video-editor/runtime/extensionSurface.ts';
    25	
    26	export interface RenderPlannerRequest {
    27	  readonly route?: RenderRoute;
    28	  readonly routes?: readonly RenderRoute[];
    29	  readonly outputFormatId?: string;
    30	  readonly requiredCapabilities?: readonly string[];
    31	}
    32	
    33	export type RenderPlannerMaterialState = 'missing' | 'stale' | 'resolved' | 'unbaked';
    34	
    35	export interface RenderPlannerMaterialStatus {
    36	  readonly materialRefId: string;
    37	  readonly state: RenderPlannerMaterialState;
    38	  readonly message?: string;
    39	  readonly updatedAt?: string;
    40	}
    41	
    42	export interface RenderPlannerInput {
    43	  readonly snapshot?: TimelineSnapshot | null;
    44	  readonly requirements?: readonly CapabilityRequirement[];
    45	  readonly extensionRuntime?: Pick<ExtensionRuntime, 'outputFormats' | 'processes' | 'shaders'>;
    46	  readonly outputFormats?: readonly VideoEditorOutputFormatDescriptor[];
    47	  readonly processes?: readonly VideoEditorProcessDescriptor[];
    48	  readonly shaders?: readonly VideoEditorShaderDescriptor[];
    49	  readonly processStatuses?: readonly ProcessStatus[];
    50	  readonly materialRefs?: readonly RenderMaterialRef[];
    51	  readonly materialStatuses?: readonly RenderPlannerMaterialStatus[];
    52	  readonly request?: RenderPlannerRequest;
    53	  readonly diagnostics?: readonly CapabilityFinding[];
    54	}
    55	
    56	export interface RenderRouteSummary {
    57	  readonly route: RenderRoute;
    58	  readonly blockerCount: number;
    59	  readonly findingCount: number;
    60	  readonly blocked: boolean;
    61	}
    62	
    63	export interface RenderRoutePlan extends RenderRouteSummary {
    64	  readonly requiredCapabilities: readonly string[];
    65	  readonly determinism: DeterminismStatus;
    66	  readonly blockers: readonly RenderBlocker[];
    67	  readonly diagnostics: readonly CapabilityFinding[];
    68	  readonly outputFormatIds: readonly string[];
    69	  readonly processRequirements: readonly VideoEditorProcessRequirementDescriptor[];
    70	  readonly nextActions: readonly VideoEditorPlannerNextActionDescriptor[];
    71	}
    72	
    73	export interface RenderPlannerGuardCompatibility {
    74	  readonly diagnostics: readonly CapabilityFinding[];
    75	  readonly findings: readonly CapabilityFinding[];
    76	  readonly blockers: readonly RenderBlocker[];
    77	  readonly unknownClipTypes: readonly string[];
    78	  readonly unknownEffects: readonly string[];
    79	  readonly unknownTransitions: readonly string[];
    80	  readonly inactiveExtensionIds: {
    81	    readonly effectIds: ReadonlySet<string>;
    82	    readonly transitionIds: ReadonlySet<string>;
    83	    readonly clipTypeIds: ReadonlySet<string>;
    84	  };
    85	  readonly hasBlockingErrors: boolean;
    86	}
    87	
    88	export interface RenderPlannerResult {
    89	  readonly guard: RenderPlannerGuardCompatibility;
    90	  readonly findings: readonly CapabilityFinding[];
    91	  readonly blockers: readonly RenderBlocker[];
    92	  readonly routes: readonly RenderRouteSummary[];
    93	  readonly routePlans: readonly RenderRoutePlan[];
    94	  readonly diagnostics: readonly CapabilityFinding[];
    95	  readonly nextActions: readonly VideoEditorPlannerNextActionDescriptor[];
    96	  readonly canBrowserExport: boolean;
    97	  readonly canWorkerExport: boolean;
    98	}
    99	
   100	interface PlanAccumulator {
   101	  findings: CapabilityFinding[];
   102	  blockers: RenderBlocker[];
   103	  nextActions: VideoEditorPlannerNextActionDescriptor[];
   104	  routeCapabilities: Map<RenderRoute, Set<string>>;
   105	  routeOutputFormatIds: Map<RenderRoute, Set<string>>;
   106	  routeProcessRequirements: Map<RenderRoute, VideoEditorProcessRequirementDescriptor[]>;
   107	  routeDeterminism: Map<RenderRoute, DeterminismStatus[]>;
   108	}
   109	
   110	const EMPTY_IDS = Object.freeze({
   111	  effectIds: Object.freeze(new Set<string>()),
   112	  transitionIds: Object.freeze(new Set<string>()),
   113	  clipTypeIds: Object.freeze(new Set<string>()),
   114	});
   115	
   116	const DETERMINISM_RANK: Record<DeterminismStatus, number> = {
   117	  deterministic: 0,
   118	  'preview-only': 1,
   119	  'live-unbaked': 2,
   120	  'process-dependent': 3,
   121	  unknown: 4,
   122	};
   123	
   124	function createAccumulator(): PlanAccumulator {
   125	  return {
   126	    findings: [],
   127	    blockers: [],
   128	    nextActions: [],
   129	    routeCapabilities: new Map(),
   130	    routeOutputFormatIds: new Map(),
   131	    routeProcessRequirements: new Map(),
   132	    routeDeterminism: new Map(),
   133	  };
   134	}
   135	
   136	function addRouteValue<T>(map: Map<RenderRoute, T[]>, route: RenderRoute, value: T): void {
   137	  const values = map.get(route);
   138	  if (values) {
   139	    values.push(value);
   140	    return;
   141	  }
   142	  map.set(route, [value]);
   143	}
   144	
   145	function addRouteSetValue(map: Map<RenderRoute, Set<string>>, route: RenderRoute, value: string): void {
   146	  const values = map.get(route);
   147	  if (values) {
   148	    values.add(value);
   149	    return;
   150	  }
   151	  map.set(route, new Set([value]));
   152	}
   153	
   154	function freezeFinding(finding: CapabilityFinding): CapabilityFinding {
   155	  return Object.freeze({
   156	    ...finding,
   157	    ...(finding.detail ? { detail: Object.freeze({ ...finding.detail }) } : {}),
   158	  });
   159	}
   160	
   161	function freezeBlocker(blocker: RenderBlocker): RenderBlocker {
   162	  return Object.freeze({
   163	    ...blocker,
   164	    ...(blocker.detail ? { detail: Object.freeze({ ...blocker.detail }) } : {}),
   165	  });
   166	}
   167	
   168	function dedupeById<T extends { readonly id: string }>(items: readonly T[]): T[] {
   169	  const seen = new Set<string>();
   170	  const deduped: T[] = [];
   171	  for (const item of items) {
   172	    if (seen.has(item.id)) continue;
   173	    seen.add(item.id);
   174	    deduped.push(item);
   175	  }
   176	  return deduped;
   177	}
   178	
   179	function sortedFindings(findings: readonly CapabilityFinding[]): readonly CapabilityFinding[] {
   180	  return Object.freeze(
   181	    dedupeById(findings.map(freezeFinding)).sort((a, b) => a.id.localeCompare(b.id)),
   182	  );
   183	}
   184	
   185	function sortedBlockers(blockers: readonly RenderBlocker[]): readonly RenderBlocker[] {
   186	  return Object.freeze(
   187	    dedupeById(blockers.map(freezeBlocker)).sort((a, b) => a.id.localeCompare(b.id)),
   188	  );
   189	}
   190	
   191	function blockerForFinding(finding: CapabilityFinding): RenderBlocker | undefined {
   192	  if (finding.severity !== 'error' || !finding.route || !finding.reason) return undefined;
   193	  return {
   194	    ...finding,
   195	    severity: 'error',
   196	    route: finding.route,
   197	    reason: finding.reason,
   198	  };
   199	}
   200	
   201	function routeFitFinding(requirement: CapabilityRequirement): CapabilityFinding | undefined {
   202	  const routeFit = requirement.routeFit;
   203	  if (!routeFit && !requirement.blocking) return undefined;
   204	  if (routeFit?.fit === 'supported' && !requirement.blocking) return undefined;
   205	
   206	  const reason = routeFit?.reason ?? blockerReasonForDeterminism(requirement.determinism);
   207	  const severity = requirement.blocking || routeFit?.fit === 'blocked' ? 'error' : 'warning';
   208	  return {
   209	    id: `${requirement.id}.${requirement.route}.${reason}`,
   210	    severity,
   211	    route: requirement.route,
   212	    reason,
   213	    message: routeFit?.message
   214	      ?? `Capability requirement "${requirement.id}" is ${routeFit?.fit ?? 'blocked'} for ${requirement.route}.`,
   215	    extensionId: requirement.sourceRef.extensionId,
   216	    contributionId: requirement.sourceRef.contributionId,
   217	    detail: {
   218	      source: 'capability-requirement',
   219	      sourceRef: requirement.sourceRef,
   220	      requiredCapabilities: [...requirement.requiredCapabilities].sort(),
   221	      determinism: requirement.determinism,
   222	      routeFit: routeFit ? { ...routeFit } : undefined,
   223	    },
   224	  };
   225	}
   226	
   227	function blockerReasonForDeterminism(determinism: DeterminismStatus): RenderBlockerReason {
   228	  switch (determinism) {
   229	    case 'preview-only':
   230	    case 'live-unbaked':
   231	    case 'process-dependent':
   232	    case 'unknown':
   233	      return determinism;
   234	    case 'deterministic':
   235	      return 'unknown';
   236	  }
   237	}
   238	
   239	function collectRequirement(acc: PlanAccumulator, requirement: CapabilityRequirement): void {
   240	  addRouteValue(acc.routeDeterminism, requirement.route, requirement.determinism);
   241	  for (const capability of requirement.requiredCapabilities) {
   242	    addRouteSetValue(acc.routeCapabilities, requirement.route, capability);
   243	  }
   244	
   245	  for (const finding of requirement.findings ?? []) {
   246	    acc.findings.push(finding);
   247	    const blocker = blockerForFinding(finding);
   248	    if (blocker) acc.blockers.push(blocker);
   249	  }
   250	
   251	  const routeFit = routeFitFinding(requirement);
   252	  if (!routeFit) return;
   253	  acc.findings.push(routeFit);
   254	  const blocker = blockerForFinding(routeFit);
   255	  if (blocker) acc.blockers.push(blocker);
   256	}
   257	
   258	function shaderDescriptorKey(extensionId: string | undefined, contributionId: string | undefined): string {
   259	  return `${extensionId ?? ''}:${contributionId ?? ''}`;
   260	}
   261	
   262	function createShaderDescriptorMap(
   263	  descriptors: readonly VideoEditorShaderDescriptor[],
   264	): ReadonlyMap<string, VideoEditorShaderDescriptor> {
   265	  return new Map(descriptors.map((descriptor) => [
   266	    shaderDescriptorKey(descriptor.extensionId, descriptor.id),
   267	    descriptor,
   268	  ]));
   269	}
   270	
   271	function createProcessDescriptorMap(
   272	  descriptors: readonly VideoEditorProcessDescriptor[],
   273	): ReadonlyMap<string, VideoEditorProcessDescriptor> {
   274	  return new Map(descriptors.map((descriptor) => [descriptor.processId, descriptor]));
   275	}
   276	
   277	function isShaderMaterializerRequirement(requirement: CapabilityRequirement): boolean {
   278	  return requirement.sourceRef.source === 'extension'
   279	    && requirement.requiredCapabilities.includes('shader-materializer')
   280	    && requirement.requiredCapabilities.includes('render-material');
   281	}
   282	
   283	function processOperationSupportsMaterializerRoute(
   284	  process: VideoEditorProcessDescriptor | undefined,
   285	  operationId: string | undefined,
   286	  route: RenderRoute,
   287	): boolean {
   288	  if (!process) return false;
   289	  return process.operations.some((operation) => {
   290	    if (operationId && operation.id !== operationId) return false;
   291	    if (!operation.routes?.includes(route)) return false;
   292	    return !operation.outputKinds || operation.outputKinds.includes('material');
   293	  });
   294	}
   295	
   296	function shaderMaterializerSupportsRoute(
   297	  descriptor: VideoEditorShaderDescriptor,
   298	  requirement: CapabilityRequirement,
   299	  processById: ReadonlyMap<string, VideoEditorProcessDescriptor>,
   300	): boolean {
   301	  const materializer = descriptor.materializer;
   302	  if (!materializer) return false;
   303	  if (materializer.routes?.includes(requirement.route)) return true;
   304	  if (!materializer.processId) return false;
   305	  return processOperationSupportsMaterializerRoute(
   306	    processById.get(materializer.processId),
   307	    materializer.operationId,
   308	    requirement.route,
   309	  );
   310	}
   311	
   312	function shaderMaterializationMessage(
   313	  descriptor: VideoEditorShaderDescriptor,
   314	  requirement: CapabilityRequirement,
   315	): string {
   316	  if (descriptor.materializer?.unavailableMessage) return descriptor.materializer.unavailableMessage;
   317	  if (descriptor.materializer?.processId) {
   318	    return `Shader "${descriptor.shaderId}" has a materializer route for ${requirement.route}; ` +
   319	      `run process "${descriptor.materializer.processId}" to produce RenderMaterial.`;
   320	  }
   321	  return `Shader "${descriptor.shaderId}" has a materializer route for ${requirement.route}; ` +
   322	    'materialize it to produce RenderMaterial.';
   323	}
   324	
   325	function shaderMaterializationAction(
   326	  descriptor: VideoEditorShaderDescriptor,
   327	  requirement: CapabilityRequirement,
   328	  message: string,
   329	): VideoEditorPlannerNextActionDescriptor {
   330	  return {
   331	    kind: 'resolve-blocker',
   332	    label: `Materialize shader ${descriptor.shaderId}`,
   333	    route: requirement.route,
   334	    processId: descriptor.materializer?.processId,
   335	    operationId: descriptor.materializer?.operationId,
   336	    message,
   337	  };
   338	}
   339	
   340	function shaderMaterializerFinding(
   341	  descriptor: VideoEditorShaderDescriptor,
   342	  requirement: CapabilityRequirement,
   343	  action: VideoEditorPlannerNextActionDescriptor,
   344	  processStatus: ProcessStatus | undefined,
   345	): CapabilityFinding {
   346	  return {
   347	    id: `${requirement.id}.${requirement.route}.shader-materializer.discovered`,
   348	    severity: 'info',
   349	    route: requirement.route,
   350	    message: `Shader materializer route discovered for "${descriptor.shaderId}" on ${requirement.route}.`,
   351	    extensionId: descriptor.extensionId,
   352	    contributionId: descriptor.id,
   353	    detail: {
   354	      source: 'shader-materializer',
   355	      shaderId: descriptor.shaderId,
   356	      processId: descriptor.materializer?.processId,
   357	      operationId: descriptor.materializer?.operationId,
   358	      processState: processStatus?.state ?? 'unknown',
   359	      materializationState: processStatus?.state === 'busy' ? 'in-progress' : 'pending',
   360	      nextAction: action,

exec
/bin/zsh -lc "nl -ba src/tools/video-editor/runtime/renderability.ts | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
     1	/**
     2	 * Shared renderability and artifact vocabulary for provider-scoped
     3	 * registries and export-readiness planning.
     4	 *
     5	 * These contracts are intentionally data-only. Registries own lifecycle and
     6	 * snapshots, export guards produce findings/blockers, and later planners can
     7	 * aggregate the same records without renaming fields.
     8	 */
     9	
    10	/** Routes that a contribution may support when previewing or exporting. */
    11	export type RenderRoute = 'preview' | 'browser-export' | 'worker-export' | 'sidecar-export';
    12	
    13	/** Locked render route vocabulary shared by registries, guards, and planners. */
    14	export const RENDER_ROUTES = [
    15	  'preview',
    16	  'browser-export',
    17	  'worker-export',
    18	  'sidecar-export',
    19	] as const satisfies readonly RenderRoute[];
    20	Object.freeze(RENDER_ROUTES);
    21	
    22	/**
    23	 * Determinism posture for a contribution, material, artifact, or bake.
    24	 *
    25	 * - `deterministic`: same inputs are expected to produce equivalent outputs.
    26	 * - `preview-only`: usable only for interactive preview, not authoritative export.
    27	 * - `live-unbaked`: depends on live provider/runtime state until materialized.
    28	 * - `process-dependent`: depends on external process/tool versions or sidecars.
    29	 * - `unknown`: insufficient metadata; guards should stay conservative.
    30	 */
    31	export type DeterminismStatus =
    32	  | 'deterministic'
    33	  | 'preview-only'
    34	  | 'live-unbaked'
    35	  | 'process-dependent'
    36	  | 'unknown';
    37	
    38	/** Locked determinism vocabulary shared across registry records and artifacts. */
    39	export const DETERMINISM_STATUSES = [
    40	  'deterministic',
    41	  'preview-only',
    42	  'live-unbaked',
    43	  'process-dependent',
    44	  'unknown',
    45	] as const satisfies readonly DeterminismStatus[];
    46	Object.freeze(DETERMINISM_STATUSES);
    47	
    48	/** Stable blocker reasons emitted by early guards and later planner aggregation. */
    49	export type RenderBlockerReason =
    50	  | 'missing-contribution'
    51	  | 'route-unsupported'
    52	  | 'preview-only'
    53	  | 'live-unbaked'
    54	  | 'process-dependent'
    55	  | 'missing-material'
    56	  | 'materialization-failed'
    57	  | 'inactive-extension'
    58	  | 'unknown';
    59	
    60	/** Locked blocker reason vocabulary for planner-compatible records. */
    61	export const RENDER_BLOCKER_REASONS = [
    62	  'missing-contribution',
    63	  'route-unsupported',
    64	  'preview-only',
    65	  'live-unbaked',
    66	  'process-dependent',
    67	  'missing-material',
    68	  'materialization-failed',
    69	  'inactive-extension',
    70	  'unknown',
    71	] as const satisfies readonly RenderBlockerReason[];
    72	Object.freeze(RENDER_BLOCKER_REASONS);
    73	
    74	export type RenderCapabilityStatus = 'supported' | 'blocked' | 'unknown';
    75	
    76	/** Per-route capability advertised by a registry record or derived guard scan. */
    77	export interface RenderCapability {
    78	  readonly route: RenderRoute;
    79	  readonly status: RenderCapabilityStatus;
    80	  readonly determinism: DeterminismStatus;
    81	  readonly blockerReason?: RenderBlockerReason;
    82	  readonly message?: string;
    83	}
    84	
    85	/** Renderability summary carried by provider-scoped registry records. */
    86	export interface ContributionRenderability {
    87	  readonly capabilities: readonly RenderCapability[];
    88	  readonly defaultRoute?: RenderRoute;
    89	  readonly determinism: DeterminismStatus;
    90	  readonly blockers?: readonly RenderBlocker[];
    91	}
    92	
    93	export type CapabilityFindingSeverity = 'error' | 'warning' | 'info';
    94	
    95	/** Planner-compatible finding record emitted by guards, registries, or loaders. */
    96	export interface CapabilityFinding {
    97	  readonly id: string;
    98	  readonly severity: CapabilityFindingSeverity;
    99	  readonly route?: RenderRoute;
   100	  readonly reason?: RenderBlockerReason;
   101	  readonly message: string;
   102	  readonly extensionId?: string;
   103	  readonly contributionId?: string;
   104	  readonly clipId?: string;
   105	  readonly materialRefId?: string;
   106	  readonly detail?: Record<string, unknown>;
   107	}
   108	
   109	/** Blocking subset of a finding that prevents a route from being authoritative. */
   110	export interface RenderBlocker extends CapabilityFinding {
   111	  readonly severity: 'error';
   112	  readonly route: RenderRoute;
   113	  readonly reason: RenderBlockerReason;
   114	}
   115	
   116	export type ShaderMaterializerRequirementScope = 'clip' | 'postprocess';
   117	
   118	export function describeShaderMaterializerRequirementScope(
   119	  scope: ShaderMaterializerRequirementScope,
   120	  ownerId?: string,
   121	): string {
   122	  if (scope === 'clip') {
   123	    return ownerId ? `clip "${ownerId}"` : 'clip scope';
   124	  }
   125	  return 'timeline postprocess';
   126	}
   127	
   128	export function shaderMissingMaterializerBlockerMessage(
   129	  shaderId: string,
   130	  scope: ShaderMaterializerRequirementScope,
   131	  ownerId?: string,
   132	): string {
   133	  return `Shader "${shaderId}" cannot export because no shader materializer produced RenderMaterial for ${
   134	    describeShaderMaterializerRequirementScope(scope, ownerId)
   135	  }.`;
   136	}
   137	
   138	export type RenderMaterialMediaKind =
   139	  | 'image'
   140	  | 'video'
   141	  | 'audio'
   142	  | 'text'
   143	  | 'json'
   144	  | 'binary'
   145	  | 'sidecar'
   146	  | 'unknown';
   147	
   148	export type RenderLocatorKind =
   149	  | 'asset-registry'
   150	  | 'artifact-store'
   151	  | 'url'
   152	  | 'local-file'
   153	  | 'inline'
   154	  | 'provider';
   155	
   156	/** Storage locator for material bytes or generated artifact outputs. */
   157	export interface RenderStorageLocator {
   158	  readonly kind: RenderLocatorKind;
   159	  readonly uri: string;
   160	  readonly mimeType?: string;
   161	  readonly contentSha256?: string;
   162	  readonly expiresAt?: string;
   163	}
   164	
   165	/**
   166	 * Stable timeline-facing reference to deterministic composition input.
   167	 *
   168	 * A RenderMaterialRef points at source material used to compose or bake a
   169	 * timeline object. It is not the final export output; final outputs use
   170	 * RenderArtifact so planners can distinguish consumed inputs from produced
   171	 * files and sidecars.
   172	 */
   173	export interface RenderMaterialRef {
   174	  readonly id: string;
   175	  readonly mediaKind: RenderMaterialMediaKind;
   176	  readonly locator: RenderStorageLocator;
   177	  readonly producerExtensionId?: string;
   178	  readonly producerVersion?: string;
   179	  readonly determinism: DeterminismStatus;
   180	  readonly replacementPolicy: 'replace-live-ref' | 'preserve-live-ref' | 'materialize-on-export';
   181	}
   182	
   183	/** Concrete material metadata plus optional duration/range constraints. */
   184	export interface RenderMaterial extends RenderMaterialRef {
   185	  readonly durationSeconds?: number;
   186	  readonly frameRange?: readonly [startFrame: number, endFrame: number];
   187	  readonly sampleRange?: readonly [startSample: number, endSample: number];
   188	  readonly inputHash?: string;
   189	  readonly metadata?: Record<string, unknown>;
   190	}
   191	
   192	/** Boundary where a material or artifact may cross provider/process/storage. */
   193	export interface ArtifactBoundary {
   194	  readonly source: 'provider' | 'browser' | 'worker' | 'sidecar-process' | 'artifact-store';
   195	  readonly target: 'provider' | 'browser' | 'worker' | 'sidecar-process' | 'artifact-store' | 'export-output';
   196	  readonly route: RenderRoute;
   197	  readonly failureBehavior: 'block-export' | 'fallback-to-preview' | 'emit-diagnostic';
   198	}
   199	
   200	/** Final output or sidecar produced by a render/bake route. */
   201	export interface RenderArtifact {
   202	  readonly id: string;
   203	  readonly route: RenderRoute;
   204	  readonly locator: RenderStorageLocator;
   205	  readonly mediaKind: RenderMaterialMediaKind;
   206	  readonly producerExtensionId?: string;
   207	  readonly producerVersion?: string;
   208	  readonly consumedMaterialRefs: readonly RenderMaterialRef[];
   209	  readonly determinism: DeterminismStatus;
   210	  readonly boundary: ArtifactBoundary;
   211	  readonly findings?: readonly CapabilityFinding[];
   212	  readonly sidecars?: readonly RenderArtifactSidecarDescriptor[];
   213	  readonly manifest?: RenderArtifactManifest;
   214	}
   215	
   216	export type ManifestedRenderArtifact = RenderArtifact & {
   217	  readonly manifest: RenderArtifactManifest;
   218	};
   219	
   220	export function assertFinalArtifactHasManifest(
   221	  artifact: RenderArtifact,
   222	  producer: string,
   223	): asserts artifact is ManifestedRenderArtifact {
   224	  if (!artifact.manifest) {
   225	    throw new Error(
   226	      `Final render artifact "${artifact.id}" from ${producer} is missing a render artifact manifest. ` +
   227	      'Route final artifact creation through createRenderArtifactManifest().',
   228	    );
   229	  }
   230	  if (artifact.manifest.artifactId !== artifact.id) {
   231	    throw new Error(
   232	      `Final render artifact "${artifact.id}" from ${producer} has manifest artifactId ` +
   233	      `"${artifact.manifest.artifactId}".`,
   234	    );
   235	  }
   236	  if (artifact.manifest.route !== artifact.route) {
   237	    throw new Error(
   238	      `Final render artifact "${artifact.id}" from ${producer} has manifest route ` +
   239	      `"${artifact.manifest.route}" but artifact route "${artifact.route}".`,
   240	    );
   241	  }
   242	  if (artifact.manifest.determinism !== artifact.determinism) {
   243	    throw new Error(
   244	      `Final render artifact "${artifact.id}" from ${producer} has manifest determinism ` +
   245	      `"${artifact.manifest.determinism}" but artifact determinism "${artifact.determinism}".`,
   246	    );
   247	  }
   248	}
   249	
   250	/** Contract a contribution declares for replacing live/runtime refs with artifacts. */
   251	export interface BakeContract {
   252	  readonly id: string;
   253	  readonly route: RenderRoute;
   254	  readonly inputMaterialRefs: readonly RenderMaterialRef[];
   255	  readonly outputArtifactKind: RenderMaterialMediaKind;
   256	  readonly determinism: DeterminismStatus;
   257	  readonly boundary: ArtifactBoundary;
   258	  readonly replacementPolicy: RenderMaterialRef['replacementPolicy'];
   259	  readonly blockers?: readonly RenderBlocker[];
   260	}

exec
/bin/zsh -lc "ls -la .megaplan/initiatives/reigh-extension-composition-spine-epic && nl -ba .megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
total 160
drwxr-xr-x  19 peteromalley  staff    608 Jul  1 19:25 .
drwxr-xr-x   4 peteromalley  staff    128 Jul  7 01:31 ..
-rw-r--r--   1 peteromalley  staff   1583 Jul  1 19:13 NORTHSTAR.md
drwxr-xr-x@ 15 peteromalley  staff    480 Jul  1 19:25 briefs
-rw-r--r--@  1 peteromalley  staff   5652 Jul  1 19:25 chain.yaml
-rw-r--r--   1 peteromalley  staff   3605 Jul  1 18:58 m0-decisions-fixtures.md
-rw-r--r--   1 peteromalley  staff   3201 Jul  1 18:58 m1a-reference-identity.md
-rw-r--r--   1 peteromalley  staff   3290 Jul  1 18:58 m1b-shader-graph-authority.md
-rw-r--r--   1 peteromalley  staff   3280 Jul  1 18:58 m2-target-paths-schema.md
-rw-r--r--   1 peteromalley  staff   3253 Jul  1 18:58 m3a-material-status-matrix.md
-rw-r--r--   1 peteromalley  staff   3534 Jul  1 18:58 m3b-live-binding-capture.md
-rw-r--r--   1 peteromalley  staff   3035 Jul  1 18:58 m3c-agent-material-promotion.md
-rw-r--r--   1 peteromalley  staff   3142 Jul  1 18:58 m4-clip-shader-keyframes.md
-rw-r--r--   1 peteromalley  staff   3388 Jul  1 18:58 m5-effects-transitions-mask.md
-rw-r--r--   1 peteromalley  staff   3477 Jul  1 18:58 m6a-process-runtime-core.md
-rw-r--r--   1 peteromalley  staff   3091 Jul  1 18:58 m6b-process-ux-canary.md
-rw-r--r--   1 peteromalley  staff   3308 Jul  1 18:58 m7a-output-format-routes.md
-rw-r--r--   1 peteromalley  staff   3672 Jul  1 18:58 m7b-output-format-sidecars.md
-rw-r--r--   1 peteromalley  staff  15948 Jul  1 19:13 prep.md
     1	base_branch: main
     2	anchors:
     3	  north_star: NORTHSTAR.md
     4	milestones:
     5	- label: m0-decisions-fixtures
     6	  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m0-decisions-fixtures.md
     7	  branch: epic/composition-spine-m0-decisions-fixtures
     8	  profile: partnered-5
     9	  robustness: thorough
    10	  depth: high
    11	  vendor: codex
    12	  notes: Freeze route model, ownership decisions, release examples, fixture matrices,
    13	    deterministic-capture profiles, and JSON-RPC protocol v0 before implementation.
    14	- label: m1a-reference-identity
    15	  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m1a-reference-identity.md
    16	  branch: epic/composition-spine-m1a-reference-identity
    17	  profile: partnered-5
    18	  robustness: thorough
    19	  depth: high
    20	  vendor: codex
    21	  notes: Add SDK refs, scoped contribution identity, duplicate preservation, reserved
    22	    graph patch vocabulary, and first shader-scope validation extraction.
    23	- label: m1b-shader-graph-authority
    24	  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m1b-shader-graph-authority.md
    25	  branch: epic/composition-spine-m1b-shader-graph-authority
    26	  profile: partnered-5
    27	  robustness: thorough
    28	  depth: high
    29	  vendor: codex
    30	  notes: Make CompositionGraph projection authoritative for shader/ref facts and contribution-index
    31	    lookups.
    32	- label: m2-target-paths-schema
    33	  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m2-target-paths-schema.md
    34	  branch: epic/composition-spine-m2-target-paths-schema
    35	  profile: partnered-5
    36	  robustness: thorough
    37	  depth: high
    38	  vendor: codex
    39	  notes: Define V1 target paths, schema capability, animates/binds-live edges, and
    40	    canonical target validation.
    41	- label: m3a-material-status-matrix
    42	  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m3a-material-status-matrix.md
    43	  branch: epic/composition-spine-m3a-material-status-matrix
    44	  profile: partnered-5
    45	  robustness: thorough
    46	  depth: high
    47	  vendor: codex
    48	  notes: Lock material statuses, detail taxonomy, helper predicates, blocking matrix,
    49	    next actions, and provenance validation.
    50	- label: m3b-live-binding-capture
    51	  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m3b-live-binding-capture.md
    52	  branch: epic/composition-spine-m3b-live-binding-capture
    53	  profile: partnered-5
    54	  robustness: thorough
    55	  depth: high
    56	  vendor: codex
    57	  notes: Implement live binding bake semantics, deterministic capture profiles, and
    58	    graph-owned keyframe patch execution for live/bake paths.
    59	- label: m3c-agent-material-promotion
    60	  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m3c-agent-material-promotion.md
    61	  branch: epic/composition-spine-m3c-agent-material-promotion
    62	  profile: partnered-5
    63	  robustness: thorough
    64	  depth: high
    65	  vendor: codex
    66	  notes: Promote agent-produced materials to durable RenderMaterial/RenderArtifact
    67	    records and attach only resolved refs to existing slots.
    68	- label: m4-clip-shader-keyframes
    69	  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m4-clip-shader-keyframes.md
    70	  branch: epic/composition-spine-m4-clip-shader-keyframes
    71	  profile: partnered-5
    72	  robustness: thorough
    73	  depth: high
    74	  vendor: codex
    75	  notes: Execute shader assignment, shader-uniform keyframes, clip-type refs, graph-projected
    76	    requires edges, and the clip shader canary.
    77	- label: m5-effects-transitions-mask
    78	  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m5-effects-transitions-mask.md
    79	  branch: epic/composition-spine-m5-effects-transitions-mask
    80	  profile: partnered-5
    81	  robustness: thorough
    82	  depth: high
    83	  vendor: codex
    84	  notes: Add effect/transition refs, effect live binding, transition mask material
    85	    consumption, repair UI, and the first three V1 release examples.
    86	- label: m6a-process-runtime-core
    87	  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m6a-process-runtime-core.md
    88	  branch: epic/composition-spine-m6a-process-runtime-core
    89	  profile: partnered-5
    90	  robustness: thorough
    91	  depth: high
    92	  vendor: codex
    93	  notes: Add trusted process manager, JSON-RPC stdio protocol, process lifecycle contracts,
    94	    runtime overlays, blockers, and result attachment.
    95	- label: m6b-process-ux-canary
    96	  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m6b-process-ux-canary.md
    97	  branch: epic/composition-spine-m6b-process-ux-canary
    98	  profile: partnered-5
    99	  robustness: thorough
   100	  depth: high
   101	  vendor: codex
   102	  notes: Wire process runtime into UX, start/cancel/shutdown repair flows, returned-ref
   103	    inspection, canary tests, and browser acceptance.
   104	- label: m7a-output-format-routes
   105	  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m7a-output-format-routes.md
   106	  branch: epic/composition-spine-m7a-output-format-routes
   107	  profile: partnered-5
   108	  robustness: thorough
   109	  depth: high
   110	  vendor: codex
   111	  notes: Introduce graph-backed output-format route planning, route artifacts, typed
   112	    manifest profiles, route-scope symmetry, and multi-artifact completion.
   113	- label: m7b-output-format-sidecars
   114	  idea: .megaplan/initiatives/reigh-extension-composition-spine-epic/briefs/m7b-output-format-sidecars.md
   115	  branch: epic/composition-spine-m7b-output-format-sidecars
   116	  profile: partnered-5
   117	  robustness: thorough
   118	  depth: high
   119	  vendor: codex
   120	  notes: Wire output-format planning to trusted sidecar/process execution, prove the
   121	    fourth composed example, and harden release governance.
   122	on_failure:
   123	  abort: stop_chain
   124	on_escalate:
   125	  abort: stop_chain
   126	merge_policy: auto
   127	driver:
   128	  robustness: full
   129	  auto_approve: true
   130	  max_iterations: 120
   131	  poll_sleep: 8.0

exec
/bin/zsh -lc "nl -ba src/tools/video-editor/lib/renderRouter.ts | sed -n '1,320p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
     1	// Sprint 8 (SD-027 + SD-034): render-button routing.
     2	//
     3	// Decides whether the user's "Render" click should:
     4	//   * stay in the existing client-side WebCodecs path (`useClientRender`),
     5	//     which handles pure-media + Reigh-native clipTypes ("text",
     6	//     "effect-layer", "media", "hold").
     7	//   * delegate to the new orchestrator `banodoco_render_timeline` task,
     8	//     which the banodoco-worker pool services with Node + Chromium +
     9	//     Remotion + the @banodoco/timeline-theme-* packages.
    10	//
    11	// Decision rule (per sprint brief):
    12	//   * If ANY clip's clipType is in THEME_PACKAGE_REGISTRY → orchestrator.
    13	//   * Mixed timelines (themed + media) → orchestrator (option (a)
    14	//     in the architecture doc; uniform composition end-to-end inside
    15	//     the worker, no cross-task ffmpeg-join).
    16	//   * Pure-Reigh-native timelines → client-side render (untouched).
    17	//
    18	// The router is shape-driven — it inspects the resolved TimelineConfig
    19	// and returns a tagged decision. The caller (UI hook) translates that
    20	// decision into either a `useClientRender` invocation or an
    21	// `enqueueBanodocoRenderTimeline` POST.
    22	//
    23	// We intentionally do NOT inspect `timeline.theme` — a timeline can
    24	// declare a theme but only contain pure-media clips, and the existing
    25	// client renderer can still handle that. The trigger is the clipType
    26	// dispatch, not theme presence.
    27	
    28	import type { TimelineRenderRequest } from '@/tools/video-editor/hooks/timeline-state-types.ts';
    29	import { getRegisteredClipTypeDescriptor } from '@/tools/video-editor/clip-types/runtime.ts';
    30	import {
    31	  getGeneratedRemotionModuleStatus,
    32	  type GeneratedRemotionModuleBlockReason,
    33	  type GeneratedLaneClipShape,
    34	} from '@/tools/video-editor/lib/generated-lanes.ts';
    35	import { materializeSequenceConfig } from '@/tools/video-editor/sequences/materialize.ts';
    36	import {
    37	  planRender,
    38	  type RenderPlannerResult,
    39	} from '@/tools/video-editor/runtime/renderPlanner.ts';
    40	import type {
    41	  CapabilityRequirement,
    42	  RenderBlockerReason,
    43	} from '@reigh/editor-sdk';
    44	import type { ContributionRenderability } from '@/tools/video-editor/runtime/renderability.ts';
    45	
    46	/** Minimal clip shape we need from the resolved timeline. */
    47	export interface RouterClipShape extends GeneratedLaneClipShape {
    48	  clipType?: string;
    49	}
    50	
    51	/** Minimal timeline shape we need from the resolved config. */
    52	export interface RouterTimelineShape {
    53	  clips?: ReadonlyArray<RouterClipShape> | null;
    54	}
    55	
    56	/**
    57	 * Minimal contributed clip record the router needs to check dynamic
    58	 * capability declarations. Consumers pass a subset of
    59	 * ClipTypeRegistryRecord or an equivalent shape extracted from the
    60	 * provider-scoped registry snapshot.
    61	 */
    62	export interface ContributedClipRecord {
    63	  readonly clipTypeId: string;
    64	  readonly renderability: ContributionRenderability;
    65	}
    66	
    67	/**
    68	 * Sprint 8 (final): provider-id taxonomy used by the render pipeline +
    69	 * `renderPipeline.ts`. Each route maps 1:1 onto a provider id so middleware
    70	 * can dispatch on the route without a separate lookup table.
    71	 *
    72	 *   * `browser-remotion`  — client-side WebCodecs / Remotion path
    73	 *                          (`useClientRender`, native + media clips).
    74	 *   * `worker-banodoco`   — orchestrator `banodoco_render_timeline`
    75	 *                          (themed + generated-remotion-module clips).
    76	 *   * `preview-only`      — generated remotion_module clips with invalid /
    77	 *                          missing artifact metadata. Cannot be rendered;
    78	 *                          surfaces a hard "render blocked" message.
    79	 *   * `external`          — reserved for future external render providers.
    80	 *                          Currently unreachable from `decideRenderRoute`.
    81	 */
    82	export type RenderRoute =
    83	  | 'browser-remotion'
    84	  | 'worker-banodoco'
    85	  | 'preview-only'
    86	  | 'external';
    87	
    88	export type RenderProviderId = RenderRoute;
    89	
    90	export const RENDER_PROVIDER_REGISTRY: Readonly<Record<RenderRoute, RenderProviderId>> = {
    91	  'browser-remotion': 'browser-remotion',
    92	  'worker-banodoco': 'worker-banodoco',
    93	  'preview-only': 'preview-only',
    94	  external: 'external',
    95	};
    96	
    97	export interface RenderRouteDecision {
    98	  route: RenderRoute;
    99	  /** True iff at least one clip is themed (i.e. uses the registry). */
   100	  hasThemedClip: boolean;
   101	  /** True iff at least one clip is pure-media / Reigh-native. */
   102	  hasMediaClip: boolean;
   103	  /** True iff at least one clip is a contributed extension clip. */
   104	  hasContributedClip: boolean;
   105	  reason:
   106	    | 'no_clips'
   107	    | 'pure_native_clips'
   108	    | 'themed_only'
   109	    | 'mixed_themed_and_media'
   110	    | 'generated_remotion_module'
   111	    | 'mixed_generated_module_and_other'
   112	    | 'browser_capable_contributed'
   113	    | 'mixed_browser_capable_contributed_and_native'
   114	    | 'contributed_blocked_no_browser_capability'
   115	    | 'contributed_blocked_worker_route_conflict'
   116	    | GeneratedRemotionModuleBlockReason;
   117	}
   118	
   119	interface PlannerRouteDecisionContext {
   120	  readonly plannerResult: RenderPlannerResult;
   121	  readonly selectedPlannerRoute: 'preview' | 'browser-export' | 'worker-export' | 'sidecar-export';
   122	}
   123	
   124	export interface PlannerBackedRenderRouteDecision extends RenderRouteDecision {
   125	  readonly planner: PlannerRouteDecisionContext;
   126	}
   127	
   128	const NATIVE_BUILTIN_CLIP_TYPES: ReadonlySet<string> = new Set([
   129	  'media',
   130	  'text',
   131	  'effect-layer',
   132	  'hold',
   133	  'automation',
   134	]);
   135	
   136	const isNativeBuiltinClipType = (value: unknown): boolean => {
   137	  // Treat undefined/null clipType as media-equivalent (pre-clipType
   138	  // legacy clips). They route to the client renderer.
   139	  if (typeof value !== 'string') return true;
   140	  return NATIVE_BUILTIN_CLIP_TYPES.has(value);
   141	};
   142	
   143	const isCustomRenderClipType = (value: unknown): boolean => {
   144	  if (typeof value !== 'string') {
   145	    return false;
   146	  }
   147	  const descriptor = getRegisteredClipTypeDescriptor(value);
   148	  return descriptor?.renderCapabilities.exportRoute === 'custom';
   149	};
   150	
   151	/**
   152	 * Map contributed clip records by clipTypeId for O(1) lookup during the
   153	 * routing loop.
   154	 */
   155	function indexContributedRecords(
   156	  records: ReadonlyArray<ContributedClipRecord> | undefined,
   157	): ReadonlyMap<string, ContributedClipRecord> {
   158	  if (!records || records.length === 0) return new Map();
   159	  const map = new Map<string, ContributedClipRecord>();
   160	  for (const record of records) {
   161	    if (!map.has(record.clipTypeId)) {
   162	      map.set(record.clipTypeId, record);
   163	    }
   164	  }
   165	  return map;
   166	}
   167	
   168	/**
   169	 * Check whether a contributed clip record explicitly declares a supported
   170	 * browser-export capability.
   171	 */
   172	function hasBrowserExportCapability(
   173	  record: ContributedClipRecord,
   174	): boolean {
   175	  return record.renderability.capabilities.some(
   176	    (c) => c.route === 'browser-export' && c.status === 'supported',
   177	  );
   178	}
   179	
   180	function sourceRefForClip(clipType: string | undefined): CapabilityRequirement['sourceRef'] {
   181	  return typeof clipType === 'string' && clipType.length > 0
   182	    ? { source: 'registry', contributionId: clipType }
   183	    : { source: 'built-in' };
   184	}
   185	
   186	function routeRequirement(
   187	  id: string,
   188	  route: CapabilityRequirement['route'],
   189	  clipType: string | undefined,
   190	  options?: {
   191	    readonly blocking?: boolean;
   192	    readonly reason?: RenderBlockerReason;
   193	    readonly message?: string;
   194	    readonly legacyReason?: RenderRouteDecision['reason'];
   195	    readonly requiredCapabilities?: readonly string[];
   196	  },
   197	): CapabilityRequirement {
   198	  const blocking = options?.blocking === true;
   199	  return {
   200	    id,
   201	    sourceRef: sourceRefForClip(clipType),
   202	    route,
   203	    requiredCapabilities: options?.requiredCapabilities ?? [route],
   204	    determinism: route === 'worker-export' ? 'process-dependent' : 'deterministic',
   205	    blocking,
   206	    routeFit: blocking
   207	      ? {
   208	          route,
   209	          fit: 'blocked',
   210	          reason: options?.reason ?? 'route-unsupported',
   211	          message: options?.message ?? `Clip type "${clipType ?? 'legacy'}" cannot render on ${route}.`,
   212	        }
   213	      : {
   214	          route,
   215	          fit: 'supported',
   216	        },
   217	    findings: blocking
   218	      ? [
   219	          {
   220	            id: `${id}.${route}.${options?.reason ?? 'route-unsupported'}`,
   221	            severity: 'error',
   222	            route,
   223	            reason: options?.reason ?? 'route-unsupported',
   224	            message: options?.message ?? `Clip type "${clipType ?? 'legacy'}" cannot render on ${route}.`,
   225	            detail: {
   226	              source: 'render-router',
   227	              clipType,
   228	              legacyReason: options?.legacyReason,
   229	            },
   230	          },
   231	        ]
   232	      : undefined,
   233	  };
   234	}
   235	
   236	function requirementsForWorkerOnlyClip(
   237	  clipType: string | undefined,
   238	  id: string,
   239	  reason: RenderRouteDecision['reason'],
   240	): CapabilityRequirement[] {
   241	  return [
   242	    routeRequirement(`${id}.browser-export`, 'browser-export', clipType, {
   243	      blocking: true,
   244	      reason: 'route-unsupported',
   245	      legacyReason: reason,
   246	      message: `Clip type "${clipType ?? 'generated'}" requires worker export.`,
   247	    }),
   248	    routeRequirement(`${id}.worker-export`, 'worker-export', clipType, {
   249	      requiredCapabilities: ['worker-export'],
   250	    }),
   251	  ];
   252	}
   253	
   254	function requirementsForBrowserOnlyClip(
   255	  clipType: string | undefined,
   256	  id: string,
   257	  reason: RenderRouteDecision['reason'],
   258	): CapabilityRequirement[] {
   259	  return [
   260	    routeRequirement(`${id}.browser-export`, 'browser-export', clipType),
   261	    routeRequirement(`${id}.worker-export`, 'worker-export', clipType, {
   262	      blocking: true,
   263	      reason: 'route-unsupported',
   264	      legacyReason: reason,
   265	      message: `Clip type "${clipType ?? 'contributed'}" cannot run on worker export.`,
   266	    }),
   267	  ];
   268	}
   269	
   270	function requirementsForBlockedClip(
   271	  clipType: string | undefined,
   272	  id: string,
   273	  reason: RenderRouteDecision['reason'],
   274	  blockerReason: RenderBlockerReason,
   275	): CapabilityRequirement[] {
   276	  return [
   277	    routeRequirement(`${id}.browser-export`, 'browser-export', clipType, {
   278	      blocking: true,
   279	      reason: blockerReason,
   280	      legacyReason: reason,
   281	      message: `Clip type "${clipType ?? 'generated'}" cannot be rendered until ${reason} is resolved.`,
   282	    }),
   283	    routeRequirement(`${id}.worker-export`, 'worker-export', clipType, {
   284	      blocking: true,
   285	      reason: blockerReason,
   286	      legacyReason: reason,
   287	      message: `Clip type "${clipType ?? 'generated'}" cannot be rendered until ${reason} is resolved.`,
   288	    }),
   289	  ];
   290	}
   291	
   292	function selectPlannerRoute(result: RenderPlannerResult): PlannerRouteDecisionContext {
   293	  if (result.canBrowserExport) {
   294	    return { plannerResult: result, selectedPlannerRoute: 'browser-export' };
   295	  }
   296	  if (result.canWorkerExport) {
   297	    return { plannerResult: result, selectedPlannerRoute: 'worker-export' };
   298	  }
   299	  return { plannerResult: result, selectedPlannerRoute: 'preview' };
   300	}
   301	
   302	/** Pure-decision routing — call this from a hook or test. */
   303	export function decideRenderRoute(
   304	  timeline: RouterTimelineShape | null | undefined,
   305	  contributedClipRecords?: ReadonlyArray<ContributedClipRecord>,
   306	): PlannerBackedRenderRouteDecision {
   307	  const clips = (timeline?.clips ?? []) as ReadonlyArray<RouterClipShape>;
   308	  const contributedIndex = indexContributedRecords(contributedClipRecords);
   309	
   310	  if (clips.length === 0) {
   311	    return {
   312	      route: 'browser-remotion',
   313	      hasThemedClip: false,
   314	      hasMediaClip: false,
   315	      hasContributedClip: false,
   316	      reason: 'no_clips',
   317	      planner: selectPlannerRoute(planRender({ requirements: [] })),
   318	    };
   319	  }
   320	

codex
The first pass shows two route vocabularies already coexisting: SDK planner routes like `browser-export`/`worker-export`, and the older render-button routes like `browser-remotion`/`worker-banodoco`. I’m drilling into the lower half of the router plus timeline-reader/domain code, since that’s where “legacy-only facts” usually leak into planner inputs.
exec
/bin/zsh -lc "nl -ba src/tools/video-editor/runtime/renderPlanner.ts | sed -n '360,760p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
exec
/bin/zsh -lc "nl -ba src/tools/video-editor/lib/timeline-reader.ts | sed -n '1,360p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
   360	      nextAction: action,
   361	    },
   362	  };
   363	}
   364	
   365	function collectShaderMaterializerRequirement(
   366	  acc: PlanAccumulator,
   367	  requirement: CapabilityRequirement,
   368	  descriptor: VideoEditorShaderDescriptor,
   369	  processStatusById: ReadonlyMap<string, ProcessStatus>,
   370	): void {
   371	  const processStatus = descriptor.materializer?.processId
   372	    ? processStatusById.get(descriptor.materializer.processId)
   373	    : undefined;
   374	  const message = shaderMaterializationMessage(descriptor, requirement);
   375	  const action = shaderMaterializationAction(descriptor, requirement, message);
   376	
   377	  collectRequirement(acc, {
   378	    ...requirement,
   379	    determinism: 'process-dependent',
   380	    blocking: true,
   381	    routeFit: {
   382	      route: requirement.route,
   383	      fit: 'supported',
   384	      reason: 'process-dependent',
   385	      message,
   386	    },
   387	    findings: [
   388	      ...(requirement.findings ?? []),
   389	      shaderMaterializerFinding(descriptor, requirement, action, processStatus),
   390	    ],
   391	  });
   392	  acc.nextActions.push(action);
   393	}
   394	
   395	function shaderCompositionKey(shader: TimelineShaderSummary): string | undefined {
   396	  if (shader.enabled === false) return undefined;
   397	  if (shader.scope === 'clip') return `clip:${shader.clipId ?? ''}`;
   398	  return 'postprocess';
   399	}
   400	
   401	function shaderCompositionScopeMessage(
   402	  existing: TimelineShaderSummary,
   403	  incoming: TimelineShaderSummary,
   404	): string {
   405	  if (incoming.scope === 'clip') {
   406	    const target = incoming.clipId ? `clip "${incoming.clipId}"` : 'the clip scope';
   407	    return `Cannot add shader "${incoming.shaderId}" to ${target} because shader "${existing.shaderId}" is already assigned. ` +
   408	      'V1 supports one clip shader per clip. Remove the existing shader before assigning another.';
   409	  }
   410	
   411	  return `Cannot add postprocess shader "${incoming.shaderId}" because postprocess shader "${existing.shaderId}" is already assigned. ` +
   412	    'V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.';
   413	}
   414	
   415	function shaderCompositionScopeLabel(shader: TimelineShaderSummary): string {
   416	  return shader.scope === 'clip' ? `clip:${shader.clipId ?? 'unknown'}` : 'postprocess';
   417	}
   418	
   419	function diagnoseSnapshotShaderComposition(
   420	  snapshot: TimelineSnapshot | null | undefined,
   421	): { snapshot: TimelineSnapshot | null | undefined; findings: CapabilityFinding[] } {
   422	  if (!snapshot?.shaders || snapshot.shaders.length === 0) {
   423	    return { snapshot, findings: [] };
   424	  }
   425	
   426	  const firstByScope = new Map<string, TimelineShaderSummary>();
   427	  const findings: CapabilityFinding[] = [];
   428	  const filteredShaders: TimelineShaderSummary[] = [];
   429	
   430	  for (const shader of snapshot.shaders) {
   431	    const scopeKey = shaderCompositionKey(shader);
   432	    if (!scopeKey) {
   433	      filteredShaders.push(shader);
   434	      continue;
   435	    }
   436	
   437	    const existing = firstByScope.get(scopeKey);
   438	    if (!existing) {
   439	      firstByScope.set(scopeKey, shader);
   440	      filteredShaders.push(shader);
   441	      continue;
   442	    }
   443	
   444	    const message = shaderCompositionScopeMessage(existing, shader);
   445	    for (const route of ['browser-export', 'worker-export'] as const satisfies readonly RenderRoute[]) {
   446	      findings.push({
   447	        id: `planner.shaderComposition.${shaderCompositionScopeLabel(shader)}.${shader.shaderId}.${route}.scope-occupied`,
   448	        severity: 'error',
   449	        route,
   450	        reason: 'unknown',
   451	        message,
   452	        extensionId: shader.extensionId,
   453	        contributionId: shader.contributionId,
   454	        detail: {
   455	          source: 'shader-composition-limit',
   456	          scope: shader.scope,
   457	          clipId: shader.clipId,
   458	          existingShaderId: existing.shaderId,
   459	          incomingShaderId: shader.shaderId,
   460	        },
   461	      });
   462	    }
   463	  }
   464	
   465	  if (findings.length === 0) {
   466	    return { snapshot, findings };
   467	  }
   468	
   469	  return {
   470	    snapshot: {
   471	      ...snapshot,
   472	      shaders: filteredShaders.length > 0 ? filteredShaders : undefined,
   473	    },
   474	    findings,
   475	  };
   476	}
   477	
   478	function sortedRoutes(routes: readonly RenderRoute[]): readonly RenderRoute[] {
   479	  const requested = new Set(routes);
   480	  return Object.freeze(RENDER_ROUTES.filter((route) => requested.has(route)));
   481	}
   482	
   483	function requestedRoutes(request: RenderPlannerRequest | undefined): readonly RenderRoute[] {
   484	  if (!request) return Object.freeze([]);
   485	  if (request.routes && request.routes.length > 0) return sortedRoutes(request.routes);
   486	  if (request.route) return Object.freeze([request.route]);
   487	  return Object.freeze([]);
   488	}
   489	
   490	function collectRequestCapabilities(acc: PlanAccumulator, request: RenderPlannerRequest | undefined): void {
   491	  if (!request?.requiredCapabilities || request.requiredCapabilities.length === 0) return;
   492	  const routes = requestedRoutes(request);
   493	  const targetRoutes = routes.length > 0 ? routes : RENDER_ROUTES;
   494	
   495	  for (const route of targetRoutes) {
   496	    for (const capability of request.requiredCapabilities) {
   497	      addRouteSetValue(acc.routeCapabilities, route, capability);
   498	    }
   499	  }
   500	}
   501	
   502	function descriptorBlockerToFinding(
   503	  blocker: VideoEditorPlannerBlockerDescriptor,
   504	  fallbackRoute: RenderRoute,
   505	  source: 'output-format' | 'process',
   506	): CapabilityFinding {
   507	  return {
   508	    id: blocker.id,
   509	    severity: 'error',
   510	    route: blocker.route ?? fallbackRoute,
   511	    reason: blocker.reason,
   512	    message: blocker.message,
   513	    extensionId: blocker.extensionId,
   514	    contributionId: blocker.contributionId,
   515	    detail: {
   516	      source,
   517	      nextAction: blocker.nextAction,
   518	    },
   519	  };
   520	}
   521	
   522	function collectDescriptorBlocker(
   523	  acc: PlanAccumulator,
   524	  blocker: VideoEditorPlannerBlockerDescriptor,
   525	  fallbackRoute: RenderRoute,
   526	  source: 'output-format' | 'process',
   527	): void {
   528	  const finding = descriptorBlockerToFinding(blocker, fallbackRoute, source);
   529	  acc.findings.push(finding);
   530	  const routeBlocker = blockerForFinding(finding);
   531	  if (routeBlocker) acc.blockers.push(routeBlocker);
   532	  if (blocker.nextAction) acc.nextActions.push(blocker.nextAction);
   533	}
   534	
   535	function processRequirementBlocker(
   536	  outputFormat: VideoEditorOutputFormatDescriptor,
   537	  route: RenderRoute,
   538	  requirement: VideoEditorProcessRequirementDescriptor,
   539	  status?: ProcessStatus,
   540	): RenderBlocker {
   541	  const operationSuffix = requirement.operationId ? `.${requirement.operationId}` : '';
   542	  return {
   543	    id: `planner.outputFormat.${outputFormat.extensionId}.${outputFormat.id}.${route}.${requirement.processId}${operationSuffix}.process-dependent`,
   544	    severity: 'error',
   545	    route,
   546	    reason: 'process-dependent',
   547	    message: processStatusMessage(outputFormat.label, requirement.processId, route, status),
   548	    extensionId: outputFormat.extensionId,
   549	    contributionId: outputFormat.id,
   550	    detail: {
   551	      source: 'output-format',
   552	      outputFormatId: outputFormat.id,
   553	      outputLabel: outputFormat.label,
   554	      processId: requirement.processId,
   555	      operationId: requirement.operationId,
   556	      requiredCapabilities: [...requirement.requiredCapabilities].sort(),
   557	      processState: status?.state ?? 'unknown',
   558	    },
   559	  };
   560	}
   561	
   562	function routeRequirementBlocker(
   563	  outputFormat: VideoEditorOutputFormatDescriptor,
   564	  routeRequirement: VideoEditorRouteRequirementDescriptor,
   565	  route: RenderRoute,
   566	  status?: ProcessStatus,
   567	): RenderBlocker | undefined {
   568	  if (!routeRequirement.processId && routeRequirement.requiredCapabilities.length === 0) return undefined;
   569	  if (!routeRequirement.processId) return undefined;
   570	
   571	  return {
   572	    id: `planner.outputFormat.${outputFormat.extensionId}.${outputFormat.id}.${route}.${routeRequirement.processId}.route-process-dependent`,
   573	    severity: 'error',
   574	    route,
   575	    reason: 'process-dependent',
   576	    message: routeRequirement.unavailableMessage
   577	      ?? processStatusMessage(outputFormat.label, routeRequirement.processId, route, status),
   578	    extensionId: outputFormat.extensionId,
   579	    contributionId: outputFormat.id,
   580	    detail: {
   581	      source: 'output-format',
   582	      outputFormatId: outputFormat.id,
   583	      outputLabel: outputFormat.label,
   584	      processId: routeRequirement.processId,
   585	      operationId: routeRequirement.operationId,
   586	      requiredCapabilities: [...routeRequirement.requiredCapabilities].sort(),
   587	      determinism: routeRequirement.determinism,
   588	      processState: status?.state ?? 'unknown',
   589	    },
   590	  };
   591	}
   592	
   593	function processStatusMessage(
   594	  outputLabel: string,
   595	  processId: string,
   596	  route: RenderRoute,
   597	  status?: ProcessStatus,
   598	): string {
   599	  if (!status) return `Output format "${outputLabel}" requires process "${processId}" before ${route} can run.`;
   600	  if (status.message) return status.message;
   601	  return `Process "${processId}" is ${status.state} for ${route}.`;
   602	}
   603	
   604	function processStatusBlocks(status: ProcessStatus | undefined): boolean {
   605	  if (!status) return true;
   606	  return status.state !== 'ready' && status.state !== 'degraded';
   607	}
   608	
   609	function processStatusDegraded(status: ProcessStatus | undefined): boolean {
   610	  return status?.state === 'degraded';
   611	}
   612	
   613	function processStatusWarning(
   614	  blocker: RenderBlocker,
   615	  status: ProcessStatus,
   616	): CapabilityFinding {
   617	  return {
   618	    ...blocker,
   619	    id: `${blocker.id}.degraded`,
   620	    severity: 'warning',
   621	    message: processStatusMessage(
   622	      String(blocker.detail?.outputLabel ?? blocker.contributionId ?? 'output'),
   623	      status.processId,
   624	      blocker.route,
   625	      status,
   626	    ),
   627	    detail: {
   628	      ...blocker.detail,
   629	      processState: status.state,
   630	      diagnostics: status.diagnostics,
   631	    },
   632	  };
   633	}
   634	
   635	function collectOutputFormat(
   636	  acc: PlanAccumulator,
   637	  outputFormat: VideoEditorOutputFormatDescriptor,
   638	  processStatusById: ReadonlyMap<string, ProcessStatus>,
   639	): void {
   640	  const availableRoutes = outputFormat.availableRoutes.length > 0
   641	    ? outputFormat.availableRoutes
   642	    : (outputFormat.requiresRender ? (['sidecar-export'] as const) : ([] as const));
   643	
   644	  for (const route of availableRoutes) {
   645	    addRouteSetValue(acc.routeOutputFormatIds, route, outputFormat.id);
   646	  }
   647	
   648	  for (const requirement of outputFormat.capabilities?.capabilityRequirements ?? []) {
   649	    collectRequirement(acc, requirement);
   650	  }
   651	
   652	  for (const routeRequirement of outputFormat.routeRequirements) {
   653	    for (const route of routeRequirement.routes) {
   654	      addRouteValue(acc.routeDeterminism, route, routeRequirement.determinism);
   655	      for (const capability of routeRequirement.requiredCapabilities) {
   656	        addRouteSetValue(acc.routeCapabilities, route, capability);
   657	      }
   658	      const status = routeRequirement.processId ? processStatusById.get(routeRequirement.processId) : undefined;
   659	      const routeBlocker = routeRequirementBlocker(outputFormat, routeRequirement, route, status);
   660	      if (routeBlocker && processStatusBlocks(status)) {
   661	        acc.findings.push(routeBlocker);
   662	        acc.blockers.push(routeBlocker);
   663	      } else if (routeBlocker && status && processStatusDegraded(status)) {
   664	        acc.findings.push(processStatusWarning(routeBlocker, status));
   665	      }
   666	    }
   667	  }
   668	
   669	  for (const requirement of outputFormat.processRequirements) {
   670	    const routes = availableRoutes.length > 0 ? availableRoutes : RENDER_ROUTES;
   671	    for (const route of routes) {
   672	      addRouteValue(acc.routeProcessRequirements, route, requirement);
   673	      const status = processStatusById.get(requirement.processId);
   674	      const blocker = processRequirementBlocker(outputFormat, route, requirement, status);
   675	      if (processStatusBlocks(status)) {
   676	        acc.findings.push(blocker);
   677	        acc.blockers.push(blocker);
   678	      } else if (status && processStatusDegraded(status)) {
   679	        acc.findings.push(processStatusWarning(blocker, status));
   680	      }
   681	    }
   682	  }
   683	
   684	  for (const blocker of outputFormat.blockers) {
   685	    collectDescriptorBlocker(acc, blocker, availableRoutes[0] ?? 'sidecar-export', 'output-format');
   686	  }
   687	  acc.nextActions.push(...outputFormat.nextActions);
   688	}
   689	
   690	function collectRequestedOutputRouteSupport(
   691	  acc: PlanAccumulator,
   692	  outputFormat: VideoEditorOutputFormatDescriptor | undefined,
   693	  request: RenderPlannerRequest | undefined,
   694	): void {
   695	  if (!outputFormat) return;
   696	  const routes = requestedRoutes(request);
   697	  if (routes.length === 0) return;
   698	
   699	  const availableRoutes = outputFormat.availableRoutes.length > 0
   700	    ? outputFormat.availableRoutes
   701	    : (outputFormat.requiresRender ? ([] as const) : (['browser-export'] as const));
   702	  const available = new Set(availableRoutes);
   703	
   704	  for (const route of routes) {
   705	    if (available.has(route)) continue;
   706	    const blocker: RenderBlocker = {
   707	      id: `planner.outputFormat.${outputFormat.extensionId}.${outputFormat.id}.${route}.route-unsupported`,
   708	      severity: 'error',
   709	      route,
   710	      reason: 'route-unsupported',
   711	      message: `Output format "${outputFormat.label}" is not available on ${route}.`,
   712	      extensionId: outputFormat.extensionId,
   713	      contributionId: outputFormat.id,
   714	      detail: {
   715	        source: 'render-request',
   716	        outputFormatId: outputFormat.id,
   717	        requestedRoute: route,
   718	        availableRoutes: [...availableRoutes].sort(),
   719	      },
   720	    };
   721	    acc.findings.push(blocker);
   722	    acc.blockers.push(blocker);
   723	  }
   724	}
   725	
   726	function collectProcess(acc: PlanAccumulator, process: VideoEditorProcessDescriptor): void {
   727	  for (const route of process.availableRoutes) {
   728	    addRouteSetValue(acc.routeCapabilities, route, process.processId);
   729	  }
   730	  for (const requirement of process.capabilities?.capabilityRequirements ?? []) {
   731	    collectRequirement(acc, requirement);
   732	  }
   733	  for (const blocker of process.blockers) {
   734	    collectDescriptorBlocker(acc, blocker, process.availableRoutes[0] ?? 'sidecar-export', 'process');
   735	  }
   736	  acc.nextActions.push(...process.nextActions);
   737	}
   738	
   739	function createProcessStatusMap(statuses: readonly ProcessStatus[] | undefined): ReadonlyMap<string, ProcessStatus> {
   740	  return new Map((statuses ?? []).map((status) => [status.processId, status]));
   741	}
   742	
   743	function createMaterialStatusMap(
   744	  statuses: readonly RenderPlannerMaterialStatus[] | undefined,
   745	): ReadonlyMap<string, RenderPlannerMaterialStatus> {
   746	  return new Map((statuses ?? []).map((status) => [status.materialRefId, status]));
   747	}
   748	
   749	function materializeAction(
   750	  label: string,
   751	  message: string,
   752	): VideoEditorPlannerNextActionDescriptor {
   753	  return {
   754	    kind: 'resolve-blocker',
   755	    label,
   756	    route: 'browser-export',
   757	    message,
   758	  };
   759	}
   760	

 succeeded in 0ms:
     1	/**
     2	 * TimelineReader — stable, read-only projection of timeline state.
     3	 *
     4	 * Exposes TimelineSnapshot summaries while hiding raw row/meta/registry
     5	 * internals.  Extensions and proposal machinery consume this reader
     6	 * instead of raw TimelineData, useTimelineCommit, or store internals.
     7	 *
     8	 * @publicContract
     9	 */
    10	
    11	import type {
    12	  TimelineReader,
    13	  TimelineSnapshot,
    14	  TimelineClipSummary,
    15	  TimelineTrackSummary,
    16	  TimelineEffectSummary,
    17	  TimelineTransitionSummary,
    18	  TimelineLiveBindingSummary,
    19	  TimelineMaterialRefSummary,
    20	  TimelineSourceRefSummary,
    21	  TimelineShaderSummary,
    22	  TimelineRenderGroupSummary,
    23	  TimelineOutputMetadata,
    24	  ProjectExtensionRequirement,
    25	  GeneratedObjectMeta,
    26	  SourceMapEntry,
    27	} from '@/sdk/index';
    28	
    29	import { getCapabilityRequirements as sdkGetCapabilityRequirements } from '@/sdk/index';
    30	
    31	import type { TimelineData, ClipMeta } from '@/tools/video-editor/lib/timeline-data';
    32	import type {
    33	  TimelineClip,
    34	  TimelineClipShaderMetadata,
    35	  TimelinePostprocessShaderMetadata,
    36	  TimelineLiveBindingResolutionStatus,
    37	  TimelineLiveSourceKind,
    38	  TimelineLiveSourceStatus,
    39	} from '@/tools/video-editor/types/index';
    40	import {
    41	  scanTimelineLiveBindings,
    42	  type TimelineLiveBindingRecord,
    43	} from '@/tools/video-editor/lib/timeline-domain.ts';
    44	
    45	// ---------------------------------------------------------------------------
    46	// Helpers
    47	// ---------------------------------------------------------------------------
    48	
    49	/**
    50	 * Determine whether an effect or transition object is managed by a
    51	 * registered extension.  Mirrors {@link deriveManaged} for clips but
    52	 * works on plain effect/transition records (which carry `app`,
    53	 * `managedBy`, or `extensionId` keys).
    54	 */
    55	function deriveEffectManaged(
    56	  obj: Record<string, unknown>,
    57	  extensionIds: ReadonlySet<string>,
    58	): { managed: boolean; managedBy?: string } {
    59	  // Explicit managedBy key.
    60	  if (
    61	    typeof obj.managedBy === 'string' &&
    62	    obj.managedBy.length > 0
    63	  ) {
    64	    return { managed: true, managedBy: obj.managedBy };
    65	  }
    66	
    67	  // Extension ID directly in the record.
    68	  if (
    69	    typeof obj.extensionId === 'string' &&
    70	    extensionIds.has(obj.extensionId)
    71	  ) {
    72	    return { managed: true, managedBy: obj.extensionId };
    73	  }
    74	
    75	  // Check app sub-object.
    76	  const app = obj.app;
    77	  if (app && typeof app === 'object' && !Array.isArray(app)) {
    78	    const appObj = app as Record<string, unknown>;
    79	    if (
    80	      typeof appObj.managedBy === 'string' &&
    81	      appObj.managedBy.length > 0
    82	    ) {
    83	      return { managed: true, managedBy: appObj.managedBy };
    84	    }
    85	    for (const key of Object.keys(appObj)) {
    86	      if (extensionIds.has(key)) {
    87	        return { managed: true, managedBy: key };
    88	      }
    89	    }
    90	  }
    91	
    92	  return { managed: false };
    93	}
    94	
    95	/**
    96	 * Compute clip duration in seconds from meta.
    97	 * Mirrors the hold-vs-speed logic in timeline-data.ts.
    98	 */
    99	function computeClipDuration(meta: ClipMeta): number {
   100	  if (typeof meta.hold === 'number') {
   101	    return meta.hold;
   102	  }
   103	  const from = meta.from ?? 0;
   104	  const to = meta.to ?? 0;
   105	  const speed = meta.speed ?? 1;
   106	  return to > from ? (to - from) / speed : 0;
   107	}
   108	
   109	/**
   110	 * Determine whether a clip is managed by a registered extension.
   111	 *
   112	 * In M3 a clip is "managed" when its `app` record carries an
   113	 * extension namespace (e.g. `app?.managedBy`), or when a
   114	 * `source_uuid` / `generation` provenance link exists.
   115	 */
   116	function deriveManaged(
   117	  clip: TimelineClip,
   118	  extensionIds: ReadonlySet<string>,
   119	): { managed: boolean; managedBy?: string } {
   120	  // Explicit managedBy key in clip app data.
   121	  if (clip.app && typeof clip.app.managedBy === 'string' && clip.app.managedBy.length > 0) {
   122	    return { managed: true, managedBy: clip.app.managedBy };
   123	  }
   124	
   125	  // If the clip has an app key that matches a known extension ID,
   126	  // treat it as managed.
   127	  if (clip.app) {
   128	    for (const key of Object.keys(clip.app)) {
   129	      if (extensionIds.has(key)) {
   130	        return { managed: true, managedBy: key };
   131	      }
   132	    }
   133	  }
   134	
   135	  // source_uuid linking to an extension.
   136	  if (clip.source_uuid && extensionIds.has(clip.source_uuid)) {
   137	    return { managed: true, managedBy: clip.source_uuid };
   138	  }
   139	
   140	  return { managed: false };
   141	}
   142	
   143	/**
   144	 * Well-known key under which GeneratedObjectMeta is stored
   145	 * in clip / track / asset app data.
   146	 */
   147	const GENERATED_META_KEY = '__generated__';
   148	
   149	/**
   150	 * Extract GeneratedObjectMeta from an object's app record if present.
   151	 * The app record may carry arbitrary extension data; we only extract
   152	 * the well-known `__generated__` key.
   153	 */
   154	function extractGeneratedMeta(
   155	  app: Record<string, unknown> | undefined,
   156	): GeneratedObjectMeta | undefined {
   157	  if (!app) return undefined;
   158	  const raw = app[GENERATED_META_KEY];
   159	  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return undefined;
   160	  const g = raw as Record<string, unknown>;
   161	  if (typeof g.extensionId !== 'string') return undefined;
   162	  const meta: GeneratedObjectMeta = {
   163	    extensionId: g.extensionId,
   164	  };
   165	  if (typeof g.contributionId === 'string') meta.contributionId = g.contributionId;
   166	  if (g.provenance !== undefined && typeof g.provenance === 'object' && !Array.isArray(g.provenance)) {
   167	    meta.provenance = g.provenance as Record<string, unknown>;
   168	  }
   169	  if (typeof g.generatedAt === 'number') meta.generatedAt = g.generatedAt;
   170	  if (typeof g.sourceMapEntryId === 'string') meta.sourceMapEntryId = g.sourceMapEntryId;
   171	  return meta;
   172	}
   173	
   174	function getStringField(
   175	  value: Record<string, unknown> | undefined,
   176	  keys: readonly string[],
   177	): string | undefined {
   178	  if (!value) return undefined;
   179	  for (const key of keys) {
   180	    const field = value[key];
   181	    if (typeof field === 'string' && field.length > 0) return field;
   182	  }
   183	  return undefined;
   184	}
   185	
   186	function collectLiveBindingRecords(data: TimelineData): TimelineLiveBindingRecord[] {
   187	  const records = [...scanTimelineLiveBindings(data.config).bindings];
   188	  const seen = new Set(records.map((record) => `${record.clipId}:${record.binding.bindingId}`));
   189	
   190	  for (const clip of data.config.clips) {
   191	    const appLiveBindings = clip.app?.liveBindings;
   192	    if (!Array.isArray(appLiveBindings)) continue;
   193	
   194	    for (const rawBinding of appLiveBindings) {
   195	      if (!rawBinding || typeof rawBinding !== 'object' || Array.isArray(rawBinding)) {
   196	        continue;
   197	      }
   198	      const binding = rawBinding as Record<string, unknown>;
   199	      if (typeof binding.bindingId !== 'string' || binding.bindingId.length === 0) {
   200	        continue;
   201	      }
   202	      const key = `${clip.id}:${binding.bindingId}`;
   203	      if (seen.has(key)) continue;
   204	
   205	      seen.add(key);
   206	      records.push({
   207	        binding: {
   208	          bindingId: binding.bindingId,
   209	          sourceId: typeof binding.sourceId === 'string' ? binding.sourceId : '',
   210	          sourceKind: (typeof binding.sourceKind === 'string'
   211	            ? binding.sourceKind
   212	            : 'custom') as TimelineLiveSourceKind,
   213	          ...(typeof binding.channelId === 'string' ? { channelId: binding.channelId } : {}),
   214	          ...(typeof binding.targetParamName === 'string'
   215	            ? { targetParamName: binding.targetParamName }
   216	            : {}),
   217	          ...(typeof binding.targetEffectId === 'string'
   218	            ? { targetEffectId: binding.targetEffectId }
   219	            : {}),
   220	          ...(typeof binding.ownerExtensionId === 'string'
   221	            ? { ownerExtensionId: binding.ownerExtensionId }
   222	            : {}),
   223	          ...(typeof binding.sourceStatus === 'string'
   224	            ? { sourceStatus: binding.sourceStatus as TimelineLiveSourceStatus }
   225	            : {}),
   226	          ...(typeof binding.resolutionStatus === 'string'
   227	            ? {
   228	                resolutionStatus:
   229	                  binding.resolutionStatus as TimelineLiveBindingResolutionStatus,
   230	              }
   231	            : {}),
   232	        },
   233	        clipId: clip.id,
   234	        path: `clips.${clip.id}.app.liveBindings`,
   235	        status:
   236	          typeof binding.resolutionStatus === 'string'
   237	            ? (binding.resolutionStatus as TimelineLiveBindingResolutionStatus)
   238	            : 'active',
   239	        diagnostics: Object.freeze([]),
   240	        blocksExport: binding.resolutionStatus !== 'resolved',
   241	      });
   242	    }
   243	  }
   244	
   245	  return records;
   246	}
   247	
   248	function isClipShaderMetadata(value: unknown): value is TimelineClipShaderMetadata {
   249	  return Boolean(
   250	    value
   251	    && typeof value === 'object'
   252	    && !Array.isArray(value)
   253	    && (value as Record<string, unknown>).scope === 'clip'
   254	    && typeof (value as Record<string, unknown>).shaderId === 'string'
   255	    && typeof (value as Record<string, unknown>).extensionId === 'string'
   256	    && typeof (value as Record<string, unknown>).contributionId === 'string',
   257	  );
   258	}
   259	
   260	function isPostprocessShaderMetadata(value: unknown): value is TimelinePostprocessShaderMetadata {
   261	  return Boolean(
   262	    value
   263	    && typeof value === 'object'
   264	    && !Array.isArray(value)
   265	    && (value as Record<string, unknown>).scope === 'postprocess'
   266	    && typeof (value as Record<string, unknown>).shaderId === 'string'
   267	    && typeof (value as Record<string, unknown>).extensionId === 'string'
   268	    && typeof (value as Record<string, unknown>).contributionId === 'string',
   269	  );
   270	}
   271	
   272	// ---------------------------------------------------------------------------
   273	// createTimelineReader
   274	// ---------------------------------------------------------------------------
   275	
   276	export interface TimelineReaderOptions {
   277	  /**
   278	   * The current timeline data to project.
   279	   * Can be a static snapshot or a getter that returns the latest state.
   280	   */
   281	  data: TimelineData | (() => TimelineData);
   282	
   283	  /**
   284	   * Project identifier, when available from the host / provider.
   285	   */
   286	  projectId?: string | null;
   287	
   288	  /**
   289	   * Extension requirements for this project.
   290	   * Extracted from project metadata (e.g. TimelineConfig.app or a
   291	   * project-level manifest).
   292	   */
   293	  extensionRequirements?: readonly ProjectExtensionRequirement[];
   294	}
   295	
   296	/**
   297	 * Create a TimelineReader from TimelineData and optional project metadata.
   298	 *
   299	 * The reader hides raw row/meta/registry internals and only exposes
   300	 * stable TimelineSnapshot projections suitable for extension and
   301	 * proposal code.
   302	 */
   303	export function createTimelineReader(
   304	  options: TimelineReaderOptions,
   305	): TimelineReader {
   306	  const getData: () => TimelineData =
   307	    typeof options.data === 'function' ? options.data : () => options.data;
   308	
   309	  const projectId = options.projectId ?? null;
   310	  const extensionRequirements: readonly ProjectExtensionRequirement[] =
   311	    options.extensionRequirements ?? [];
   312	
   313	  // Pre-compute the set of known extension IDs for managed-by detection.
   314	  const knownExtensionIds: ReadonlySet<string> = new Set(
   315	    extensionRequirements.map((r) => r.extensionId),
   316	  );
   317	
   318	  return {
   319	    snapshot(): TimelineSnapshot {
   320	      const data = getData();
   321	      const { config, configVersion, registry, meta: metaMap } = data;
   322	
   323	      // ── Clips ──────────────────────────────────────────────────────
   324	      const clipSummaries: TimelineClipSummary[] = [];
   325	      const effectSummaries: TimelineEffectSummary[] = [];
   326	      const transitionSummaries: TimelineTransitionSummary[] = [];
   327	      const liveBindingSummaries: TimelineLiveBindingSummary[] = [];
   328	      const materialRefSummaries: TimelineMaterialRefSummary[] = [];
   329	      const sourceRefSummaries: TimelineSourceRefSummary[] = [];
   330	      const shaderSummaries: TimelineShaderSummary[] = [];
   331	      const liveBindingsByClip = new Map<string, TimelineLiveBindingRecord[]>();
   332	
   333	      for (const record of collectLiveBindingRecords(data)) {
   334	        const records = liveBindingsByClip.get(record.clipId) ?? [];
   335	        records.push(record);
   336	        liveBindingsByClip.set(record.clipId, records);
   337	      }
   338	
   339	      for (const clip of config.clips) {
   340	        const clipMeta = metaMap[clip.id];
   341	        if (!clipMeta) continue;
   342	
   343	        const { managed, managedBy } = deriveManaged(clip, knownExtensionIds);
   344	
   345	        const generatedMeta: GeneratedObjectMeta | undefined =
   346	          extractGeneratedMeta(clip.app);
   347	
   348	        const clipShader = isClipShaderMetadata(clip.app?.shader)
   349	          ? clip.app.shader
   350	          : undefined;
   351	        if (clipShader) {
   352	          shaderSummaries.push({
   353	            id: `${clip.id}:shader:${clipShader.shaderId}`,
   354	            shaderId: clipShader.shaderId,
   355	            scope: 'clip',
   356	            clipId: clip.id,
   357	            extensionId: clipShader.extensionId,
   358	            contributionId: clipShader.contributionId,
   359	            enabled: clipShader.enabled !== false,
   360	          });

exec
/bin/zsh -lc "nl -ba src/tools/video-editor/lib/renderRouter.ts | sed -n '300,620p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
   300	}
   301	
   302	/** Pure-decision routing — call this from a hook or test. */
   303	export function decideRenderRoute(
   304	  timeline: RouterTimelineShape | null | undefined,
   305	  contributedClipRecords?: ReadonlyArray<ContributedClipRecord>,
   306	): PlannerBackedRenderRouteDecision {
   307	  const clips = (timeline?.clips ?? []) as ReadonlyArray<RouterClipShape>;
   308	  const contributedIndex = indexContributedRecords(contributedClipRecords);
   309	
   310	  if (clips.length === 0) {
   311	    return {
   312	      route: 'browser-remotion',
   313	      hasThemedClip: false,
   314	      hasMediaClip: false,
   315	      hasContributedClip: false,
   316	      reason: 'no_clips',
   317	      planner: selectPlannerRoute(planRender({ requirements: [] })),
   318	    };
   319	  }
   320	
   321	  const requirements: CapabilityRequirement[] = [];
   322	  let hasThemedClip = false;
   323	  let hasMediaClip = false;
   324	  let hasContributedClip = false;
   325	  let hasBrowserCapableContributedClip = false;
   326	  let hasNativeOrMediaClip = false;
   327	  let hasGeneratedModuleClip = false;
   328	  let hasOtherClip = false;
   329	  let blockedReason: RenderRouteDecision['reason'] | null = null;
   330	  let blockedHasThemedClip = false;
   331	  let blockedHasMediaClip = false;
   332	  let blockedHasContributedClip = false;
   333	
   334	  clips.forEach((clip, index) => {
   335	    if (blockedReason) return;
   336	    const requirementId = `router.clip.${index}.${clip.clipType ?? 'legacy'}`;
   337	    const moduleStatus = getGeneratedRemotionModuleStatus(clip);
   338	    if (moduleStatus.kind === 'blocked_module') {
   339	      requirements.push(...requirementsForBlockedClip(
   340	        clip.clipType,
   341	        requirementId,
   342	        moduleStatus.reason,
   343	        moduleStatus.reason === 'remotion_module_missing_artifact'
   344	          ? 'missing-material'
   345	          : 'materialization-failed',
   346	      ));
   347	      blockedReason = moduleStatus.reason;
   348	      return;
   349	    }
   350	    if (moduleStatus.kind === 'valid_module') {
   351	      hasGeneratedModuleClip = true;
   352	      requirements.push(...requirementsForWorkerOnlyClip(clip.clipType, requirementId, 'generated_remotion_module'));
   353	      return;
   354	    }
   355	
   356	    hasOtherClip = true;
   357	
   358	    // M9 T11: Check contributed clip records first. Contributed clip
   359	    // code is only allowed in browser-remotion when it explicitly
   360	    // declares browser-export capability. Worker routes are always
   361	    // blocked for contributed code (SD1).
   362	    const clipType = clip?.clipType;
   363	    if (typeof clipType === 'string') {
   364	      const contributedRecord = contributedIndex.get(clipType);
   365	      if (contributedRecord) {
   366	        hasContributedClip = true;
   367	        if (hasBrowserExportCapability(contributedRecord)) {
   368	          hasBrowserCapableContributedClip = true;
   369	          requirements.push(...requirementsForBrowserOnlyClip(clipType, requirementId, 'browser_capable_contributed'));
   370	        } else {
   371	          // Contributed clip without browser-export capability is
   372	          // immediately blocked — worker routes are out of scope
   373	          // for contributed code and no other route is available.
   374	          requirements.push(...requirementsForBlockedClip(
   375	            clipType,
   376	            requirementId,
   377	            'contributed_blocked_no_browser_capability',
   378	            'route-unsupported',
   379	          ));
   380	          blockedReason = 'contributed_blocked_no_browser_capability';
   381	          blockedHasContributedClip = true;
   382	          return;
   383	        }
   384	        return;
   385	      }
   386	    }
   387	
   388	    // Non-contributed clips follow existing routing.
   389	    if (isCustomRenderClipType(clip?.clipType)) {
   390	      hasThemedClip = true;
   391	      // A themed clip mixed with browser-capable contributed clips
   392	      // creates a conflict: themed clips need worker, contributed
   393	      // clips can't go to worker.
   394	      if (hasBrowserCapableContributedClip) {
   395	        requirements.push(...requirementsForBlockedClip(
   396	          clip.clipType,
   397	          requirementId,
   398	          'contributed_blocked_worker_route_conflict',
   399	          'route-unsupported',
   400	        ));
   401	        blockedReason = 'contributed_blocked_worker_route_conflict';
   402	        blockedHasThemedClip = true;
   403	        blockedHasMediaClip = true;
   404	        blockedHasContributedClip = true;
   405	        return;
   406	      }
   407	      requirements.push(...requirementsForWorkerOnlyClip(clip.clipType, requirementId, 'themed_only'));
   408	    } else if (isNativeBuiltinClipType(clip?.clipType)) {
   409	      hasMediaClip = true;
   410	      hasNativeOrMediaClip = true;
   411	      requirements.push(routeRequirement(`${requirementId}.browser-export`, 'browser-export', clip.clipType));
   412	    } else {
   413	      // Unknown clipType (theme package not installed, typo). Treat as
   414	      // media so the existing render path's loud-placeholder fallback
   415	      // surfaces — orchestrator wouldn't be able to render it either
   416	      // without the theme package, and the sprint scopes us to
   417	      // registered themes.
   418	      hasMediaClip = true;
   419	      hasNativeOrMediaClip = true;
   420	      requirements.push(routeRequirement(`${requirementId}.browser-export`, 'browser-export', clip.clipType));
   421	    }
   422	  });
   423	
   424	  const planner = selectPlannerRoute(planRender({ requirements }));
   425	
   426	  if (blockedReason) {
   427	    return {
   428	      route: 'preview-only',
   429	      hasThemedClip: blockedHasThemedClip,
   430	      hasMediaClip: blockedHasMediaClip,
   431	      hasContributedClip: blockedHasContributedClip,
   432	      reason: blockedReason,
   433	      planner,
   434	    };
   435	  }
   436	
   437	  // Generated Remotion module clips always go to the worker pool if
   438	  // they survived the blocked_module short-circuit above. Mixed
   439	  // generated + browser-capable contributed clips create an
   440	  // unresolvable conflict because contributed code cannot execute in
   441	  // the worker.
   442	  if (hasGeneratedModuleClip) {
   443	    if (hasBrowserCapableContributedClip) {
   444	      const conflictPlanner = selectPlannerRoute(planRender({
   445	        requirements: [
   446	          ...requirements,
   447	          ...requirementsForBlockedClip(
   448	            'generated-remotion-module',
   449	            'router.generated.contributed-conflict',
   450	            'contributed_blocked_worker_route_conflict',
   451	            'route-unsupported',
   452	          ),
   453	        ],
   454	      }));
   455	      return {
   456	        route: 'preview-only',
   457	        hasThemedClip,
   458	        hasMediaClip,
   459	        hasContributedClip: true,
   460	        reason: 'contributed_blocked_worker_route_conflict',
   461	        planner: conflictPlanner,
   462	      };
   463	    }
   464	    return {
   465	      route: 'worker-banodoco',
   466	      hasThemedClip,
   467	      hasMediaClip,
   468	      hasContributedClip: false,
   469	      reason: hasOtherClip ? 'mixed_generated_module_and_other' : 'generated_remotion_module',
   470	      planner,
   471	    };
   472	  }
   473	
   474	  // Browser-capable contributed clips mixed with themed clips already
   475	  // short-circuit above (contributed_blocked_worker_route_conflict).
   476	  // Here we handle the remaining combinations.
   477	
   478	  if (hasBrowserCapableContributedClip) {
   479	    if (hasThemedClip) {
   480	      // Should not reach here (caught above), but defensive.
   481	      return {
   482	        route: 'preview-only',
   483	        hasThemedClip: true,
   484	        hasMediaClip: true,
   485	        hasContributedClip: true,
   486	        reason: 'contributed_blocked_worker_route_conflict',
   487	        planner,
   488	      };
   489	    }
   490	    if (hasNativeOrMediaClip) {
   491	      // Mixed browser-capable contributed + native → browser-remotion
   492	      // handles both.
   493	      return {
   494	        route: 'browser-remotion',
   495	        hasThemedClip: false,
   496	        hasMediaClip: true,
   497	        hasContributedClip: true,
   498	        reason: 'mixed_browser_capable_contributed_and_native',
   499	        planner,
   500	      };
   501	    }
   502	    // Pure browser-capable contributed clips
   503	    return {
   504	      route: 'browser-remotion',
   505	      hasThemedClip: false,
   506	      hasMediaClip: false,
   507	      hasContributedClip: true,
   508	      reason: 'browser_capable_contributed',
   509	      planner,
   510	    };
   511	  }
   512	
   513	  if (hasThemedClip && hasMediaClip) {
   514	    return {
   515	      route: 'worker-banodoco',
   516	      hasThemedClip,
   517	      hasMediaClip,
   518	      hasContributedClip: false,
   519	      reason: 'mixed_themed_and_media',
   520	      planner,
   521	    };
   522	  }
   523	  if (hasThemedClip) {
   524	    return {
   525	      route: 'worker-banodoco',
   526	      hasThemedClip,
   527	      hasMediaClip,
   528	      hasContributedClip: false,
   529	      reason: 'themed_only',
   530	      planner,
   531	    };
   532	  }
   533	  return {
   534	    route: 'browser-remotion',
   535	    hasThemedClip,
   536	    hasMediaClip,
   537	    hasContributedClip: false,
   538	    reason: 'pure_native_clips',
   539	    planner,
   540	  };
   541	}
   542	
   543	// ---------------------------------------------------------------------------
   544	// Orchestrator dispatch (banodoco_render_timeline)
   545	// ---------------------------------------------------------------------------
   546	
   547	export interface BanodocoRenderTimelinePayload {
   548	  timeline_id: string;
   549	  timeline: unknown;
   550	  assets: unknown;
   551	  theme_id: string;
   552	  output_filename: string;
   553	  user_jwt: string;
   554	  project_id: string;
   555	  correlation_id: string;
   556	}
   557	
   558	export interface BuildRenderPayloadInput {
   559	  /**
   560	   * The TimelineRenderRequest the UI/hook composed for this render.
   561	   * `renderRuntime.projectId` and `assetRegistry` are read from here,
   562	   * keeping caller call-sites aligned with the rest of the pipeline.
   563	   */
   564	  request: Pick<TimelineRenderRequest, 'timelineId' | 'assetRegistry' | 'resolvedConfig' | 'renderRuntime'> & {
   565	    outputFilename?: string;
   566	  };
   567	  userJwt: string;
   568	  /** Tests inject a deterministic UUID; production uses crypto.randomUUID. */
   569	  correlationId?: string;
   570	}
   571	
   572	const FALLBACK_THEME_ID = '2rp';
   573	
   574	function defaultThemeId(config: { theme?: string } | null | undefined): string {
   575	  const value = config?.theme;
   576	  return typeof value === 'string' && value.trim() ? value : FALLBACK_THEME_ID;
   577	}
   578	
   579	function defaultOutputFilename(timelineId: string): string {
   580	  // Suggested filename — the worker may suffix with task_id.
   581	  return `timeline-${timelineId}.mp4`;
   582	}
   583	
   584	function newCorrelationId(): string {
   585	  if (typeof globalThis.crypto?.randomUUID === 'function') {
   586	    return globalThis.crypto.randomUUID();
   587	  }
   588	  // Defensive non-prod fallback (e.g. test envs without the crypto API);
   589	  // the sprint's prod path has crypto everywhere.
   590	  return `corr-${Math.random().toString(16).slice(2)}-${Date.now().toString(16)}`;
   591	}
   592	
   593	export function buildRenderTimelinePayload(
   594	  input: BuildRenderPayloadInput,
   595	): { payload?: BanodocoRenderTimelinePayload; error?: string } {
   596	  const { request } = input;
   597	  if (!request?.timelineId) return { error: 'timelineId is required' };
   598	  if (!request?.renderRuntime?.projectId) return { error: 'projectId is required' };
   599	  if (!input.userJwt) return { error: 'user JWT is required (SD-022)' };
   600	  if (!request.resolvedConfig) return { error: 'resolved timeline config is required' };
   601	
   602	  return {
   603	    payload: {
   604	      timeline_id: request.timelineId,
   605	      timeline: materializeSequenceConfig(request.resolvedConfig as Parameters<typeof materializeSequenceConfig>[0]),
   606	      assets: request.assetRegistry ?? { assets: {} },
   607	      theme_id: defaultThemeId(request.resolvedConfig),
   608	      output_filename: request.outputFilename ?? defaultOutputFilename(request.timelineId),
   609	      user_jwt: input.userJwt,
   610	      project_id: request.renderRuntime.projectId,
   611	      correlation_id: input.correlationId ?? newCorrelationId(),
   612	    },
   613	  };
   614	}
   615	
   616	export interface EnqueueRenderResult {
   617	  status: 'queued' | 'error';
   618	  task_id?: string;
   619	  correlation_id?: string;
   620	  message: string;

exec
/bin/zsh -lc "nl -ba src/tools/video-editor/lib/timeline-domain.ts | sed -n '1,420p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
     1	import type {
     2	  AssetRegistry,
     3	  AssetRegistryEntry,
     4	  ClipContinuous,
     5	  ClipEntrance,
     6	  ClipExit,
     7	  ClipTransition,
     8	  PinnedShotGroup,
     9	  TimelineClip,
    10	  TimelineConfig,
    11	  TimelineClipShaderMetadata,
    12	  TimelineLiveBinding,
    13	  TimelineLiveBindingResolutionStatus,
    14	  TimelineLiveDeterministicRef,
    15	  TimelineLiveSourceKind,
    16	  TimelineLiveSourceStatus,
    17	  TimelineLiveUniformBinding,
    18	  TimelineLiveUniformBindingMappingKind,
    19	  TimelinePostprocessShaderMetadata,
    20	  TimelineShaderScope,
    21	  TrackDefinition,
    22	} from '../types/index.ts';
    23	import { validateAssetMetadata } from './assetMetadata';
    24	import type { TransitionRegistrySnapshot } from '@/tools/video-editor/transitions/registry/types.ts';
    25	import {
    26	  validateClipTransition,
    27	  repairClipTransition,
    28	  TransitionDiagnosticCodes,
    29	} from '@/tools/video-editor/transitions/validation.ts';
    30	
    31	export type TimelineDomainContractLevel = 'config-only' | 'pair-aware';
    32	export type TimelineDomainIssueSeverity = 'warning' | 'error';
    33	export type TimelineDomainIssueCode =
    34	  | 'duplicate_track_removed'
    35	  | 'duplicate_clip_removed'
    36	  | 'legacy_pinned_shot_group_repaired'
    37	  | 'legacy_tracks_migrated'
    38	  | 'legacy_background_clip_inserted'
    39	  | 'shot_group_contiguity_repaired'
    40	  | 'malformed_non_hold_trim_repaired'
    41	  | 'malformed_non_hold_trim_zero_duration'
    42	  | 'unexpected_top_level_key'
    43	  | 'unexpected_clip_key'
    44	  | 'unexpected_track_key'
    45	  | 'legacy_transition_missing_type'
    46	  | 'legacy_transition_unresolvable'
    47	  | 'legacy_transition_removed_contributed'
    48	  | 'legacy_transition_params_repaired'
    49	  | 'legacy_transition_cleared'
    50	  | 'live_binding_malformed_metadata'
    51	  | 'live_binding_missing_binding_id'
    52	  | 'live_binding_missing_source_id'
    53	  | 'live_binding_missing_source_kind'
    54	  | 'live_binding_unsupported_source_kind'
    55	  | 'live_binding_sample_payload_rejected'
    56	  | 'shader_scope_occupied';
    57	
    58	export interface TimelineDomainIssue {
    59	  level: TimelineDomainContractLevel;
    60	  severity: TimelineDomainIssueSeverity;
    61	  code: TimelineDomainIssueCode;
    62	  message: string;
    63	  path?: string;
    64	  clipId?: string;
    65	  assetId?: string;
    66	  trackId?: string;
    67	  repairApplied?: boolean;
    68	  details?: Record<string, unknown>;
    69	}
    70	
    71	export interface CanonicalTimelineConfigSnapshot {
    72	  level: 'config-only';
    73	  config: TimelineConfig;
    74	  issues: TimelineDomainIssue[];
    75	}
    76	
    77	export interface CanonicalTimelinePair {
    78	  level: 'pair-aware';
    79	  config: TimelineConfig;
    80	  registry: AssetRegistry;
    81	  issues: TimelineDomainIssue[];
    82	}
    83	
    84	export interface TimelineDomainValidationResult {
    85	  level: TimelineDomainContractLevel;
    86	  ok: boolean;
    87	  issues: TimelineDomainIssue[];
    88	}
    89	
    90	export class TimelineDomainError extends Error {
    91	  readonly issues: TimelineDomainIssue[];
    92	  readonly level: TimelineDomainContractLevel;
    93	
    94	  constructor(level: TimelineDomainContractLevel, issues: TimelineDomainIssue[], message?: string) {
    95	    super(message ?? (issues.map((issue) => issue.message).join('; ') || 'Invalid timeline payload'));
    96	    this.name = 'TimelineDomainError';
    97	    this.issues = issues;
    98	    this.level = level;
    99	  }
   100	}
   101	
   102	type TimelineExtras = Pick<TimelineConfig, 'theme' | 'theme_overrides' | 'generation_defaults' | 'app'>;
   103	type LegacyPinnedGroupChild = { clipId: string; offset?: number; duration?: number };
   104	type LegacyPinnedShotGroup = PinnedShotGroup & {
   105	  start?: number;
   106	  children?: LegacyPinnedGroupChild[];
   107	};
   108	
   109	const DEFAULT_VIDEO_SCALE = 0.95;
   110	const LEGACY_TRACK_MAP: Record<string, string> = {
   111	  video: 'V2',
   112	  overlay: 'V3',
   113	  audio: 'A1',
   114	};
   115	const LEGACY_ASSET_EFFECTS: Record<
   116	  string,
   117	  { entrance?: ClipEntrance; exit?: ClipExit; continuous?: ClipContinuous }
   118	> = {
   119	  'output-composition': {
   120	    entrance: { type: 'slide-up', duration: 0.6 },
   121	    exit: { type: 'flip', duration: 0.6 },
   122	    continuous: { type: 'float', intensity: 0.45 },
   123	  },
   124	  'venn-diagram': {
   125	    entrance: { type: 'zoom-spin', duration: 0.6 },
   126	    exit: { type: 'zoom-out', duration: 0.5 },
   127	    continuous: { type: 'ken-burns', intensity: 0.55 },
   128	  },
   129	  'demo-one': {
   130	    entrance: { type: 'slide-right', duration: 0.6 },
   131	    exit: { type: 'slide-down', duration: 0.5 },
   132	    continuous: { type: 'glitch', intensity: 0.45 },
   133	  },
   134	  'demo-two': {
   135	    entrance: { type: 'pulse', duration: 0.5 },
   136	    exit: { type: 'flip', duration: 0.6 },
   137	  },
   138	};
   139	
   140	const TIMELINE_TIME_PRECISION = 4;
   141	const CONTIGUITY_EPSILON = 0.001;
   142	export const TIMELINE_POSTPROCESS_SHADER_APP_KEY = 'shaderPostprocess';
   143	
   144	export const TIMELINE_CLIP_FIELDS = [
   145	  'id',
   146	  'at',
   147	  'track',
   148	  'clipType',
   149	  'asset',
   150	  'from',
   151	  'to',
   152	  'speed',
   153	  'hold',
   154	  'volume',
   155	  'x',
   156	  'y',
   157	  'width',
   158	  'height',
   159	  'cropTop',
   160	  'cropBottom',
   161	  'cropLeft',
   162	  'cropRight',
   163	  'opacity',
   164	  'text',
   165	  'entrance',
   166	  'exit',
   167	  'continuous',
   168	  'transition',
   169	  'effects',
   170	  'params',
   171	  'pool_id',
   172	  'clip_order',
   173	  'source_uuid',
   174	  'generation',
   175	  'app',
   176	  // M9: Host-owned keyframes keyed by parameter name
   177	  'keyframes',
   178	] as const;
   179	
   180	export type TimelineClipField = (typeof TIMELINE_CLIP_FIELDS)[number];
   181	
   182	export const TRACK_DEFINITION_FIELDS = [
   183	  'id',
   184	  'kind',
   185	  'label',
   186	  'scale',
   187	  'fit',
   188	  'opacity',
   189	  'volume',
   190	  'muted',
   191	  'blendMode',
   192	  'app',
   193	] as const;
   194	
   195	export type TrackDefinitionField = (typeof TRACK_DEFINITION_FIELDS)[number];
   196	
   197	const ALLOWED_TOP_LEVEL_KEYS = new Set([
   198	  'output',
   199	  'clips',
   200	  'tracks',
   201	  'pinnedShotGroups',
   202	  'theme',
   203	  'theme_overrides',
   204	  'generation_defaults',
   205	  'app',
   206	]);
   207	
   208	const ASSET_REGISTRY_ENTRY_FIELDS = [
   209	  'file',
   210	  'url',
   211	  'etag',
   212	  'content_sha256',
   213	  'url_expires_at',
   214	  'type',
   215	  'duration',
   216	  'resolution',
   217	  'fps',
   218	  'origin',
   219	  'derivedFrom',
   220	  'generationId',
   221	  'variantId',
   222	  'thumbnailUrl',
   223	  'metadata',
   224	] as const;
   225	
   226	const roundTimelineValue = (value: number, digits = TIMELINE_TIME_PRECISION): number => {
   227	  const factor = 10 ** digits;
   228	  return Math.round(value * factor) / factor;
   229	};
   230	
   231	const cloneAppValue = (value: unknown): unknown => {
   232	  if (Array.isArray(value)) {
   233	    return value.map(cloneAppValue);
   234	  }
   235	
   236	  if (value !== null && typeof value === 'object') {
   237	    return Object.fromEntries(
   238	      Object.entries(value as Record<string, unknown>).map(([key, childValue]) => [key, cloneAppValue(childValue)]),
   239	    );
   240	  }
   241	
   242	  return value;
   243	};
   244	
   245	export const cloneAppExtension = (app: Record<string, unknown>): Record<string, unknown> => {
   246	  if (typeof structuredClone === 'function') {
   247	    try {
   248	      return structuredClone(app) as Record<string, unknown>;
   249	    } catch {
   250	      // Fall back to JSON-shaped structural passthrough for non-cloneable values.
   251	    }
   252	  }
   253	
   254	  return cloneAppValue(app) as Record<string, unknown>;
   255	};
   256	
   257	const cloneTimelineExtras = (config: TimelineConfig): TimelineExtras => ({
   258	  ...(config.theme !== undefined ? { theme: config.theme } : {}),
   259	  ...(config.theme_overrides !== undefined ? { theme_overrides: config.theme_overrides } : {}),
   260	  ...(config.generation_defaults !== undefined ? { generation_defaults: config.generation_defaults } : {}),
   261	  ...(config.app !== undefined ? { app: cloneAppExtension(config.app) } : {}),
   262	});
   263	
   264	const clonePinnedShotImageSnapshots = (
   265	  imageClipSnapshot: PinnedShotGroup['imageClipSnapshot'],
   266	): PinnedShotGroup['imageClipSnapshot'] => imageClipSnapshot?.map((snapshot) => ({
   267	  ...snapshot,
   268	  meta: { ...snapshot.meta },
   269	}));
   270	
   271	export const clonePinnedShotGroups = (
   272	  pinnedShotGroups: TimelineConfig['pinnedShotGroups'],
   273	): TimelineConfig['pinnedShotGroups'] => pinnedShotGroups?.map((group) => ({
   274	  shotId: group.shotId,
   275	  trackId: group.trackId,
   276	  clipIds: [...group.clipIds],
   277	  mode: group.mode,
   278	  videoAssetKey: group.videoAssetKey,
   279	  imageClipSnapshot: clonePinnedShotImageSnapshots(group.imageClipSnapshot),
   280	}));
   281	
   282	export const cloneAssetRegistry = (registry: AssetRegistry): AssetRegistry => ({
   283	  assets: Object.fromEntries(
   284	    Object.entries(registry.assets ?? {}).map(([assetId, entry]) => [assetId, sanitizeAssetRegistryEntry(entry)]),
   285	  ),
   286	});
   287	
   288	export type TimelineShaderMetadata = TimelineClipShaderMetadata | TimelinePostprocessShaderMetadata;
   289	
   290	export type TimelineShaderAssignmentResult<T> =
   291	  | { ok: true; value: T }
   292	  | {
   293	      ok: false;
   294	      code: 'shader_scope_occupied';
   295	      scope: TimelineShaderScope;
   296	      existing: TimelineShaderMetadata;
   297	      incoming: TimelineShaderMetadata;
   298	      message: string;
   299	    };
   300	
   301	const isRecord = (value: unknown): value is Record<string, unknown> => (
   302	  value !== null && typeof value === 'object' && !Array.isArray(value)
   303	);
   304	
   305	const isTimelineShaderMetadata = <Scope extends TimelineShaderScope>(
   306	  value: unknown,
   307	  scope: Scope,
   308	): value is Scope extends 'clip' ? TimelineClipShaderMetadata : TimelinePostprocessShaderMetadata => {
   309	  return (
   310	    isRecord(value)
   311	    && value.scope === scope
   312	    && typeof value.extensionId === 'string'
   313	    && value.extensionId.length > 0
   314	    && typeof value.contributionId === 'string'
   315	    && value.contributionId.length > 0
   316	    && typeof value.shaderId === 'string'
   317	    && value.shaderId.length > 0
   318	  );
   319	};
   320	
   321	export const getTimelineClipShader = (clip: Pick<TimelineClip, 'app'>): TimelineClipShaderMetadata | undefined => {
   322	  const shader = clip.app?.shader;
   323	  return isTimelineShaderMetadata(shader, 'clip') ? shader : undefined;
   324	};
   325	
   326	export const getTimelinePostprocessShader = (
   327	  config: Pick<TimelineConfig, 'app'>,
   328	): TimelinePostprocessShaderMetadata | undefined => {
   329	  const shader = config.app?.[TIMELINE_POSTPROCESS_SHADER_APP_KEY];
   330	  return isTimelineShaderMetadata(shader, 'postprocess') ? shader : undefined;
   331	};
   332	
   333	export const sameTimelineShaderIdentity = (
   334	  left: TimelineShaderMetadata,
   335	  right: TimelineShaderMetadata,
   336	): boolean => (
   337	  left.scope === right.scope
   338	  && left.extensionId === right.extensionId
   339	  && left.contributionId === right.contributionId
   340	  && left.shaderId === right.shaderId
   341	);
   342	
   343	export const timelineShaderScopeOccupiedMessage = (
   344	  scope: TimelineShaderScope,
   345	  existingShaderId: string,
   346	  incomingShaderId: string,
   347	  clipId?: string,
   348	): string => {
   349	  if (scope === 'clip') {
   350	    const target = clipId ? `clip "${clipId}"` : 'the clip scope';
   351	    return `Cannot add shader "${incomingShaderId}" to ${target} because shader "${existingShaderId}" is already assigned. ` +
   352	      'V1 supports one clip shader per clip. Remove the existing shader before assigning another.';
   353	  }
   354	
   355	  return `Cannot add postprocess shader "${incomingShaderId}" because postprocess shader "${existingShaderId}" is already assigned. ` +
   356	    'V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.';
   357	};
   358	
   359	const createShaderScopeOccupiedResult = <T>(
   360	  scope: TimelineShaderScope,
   361	  existing: TimelineShaderMetadata,
   362	  incoming: TimelineShaderMetadata,
   363	  clipId?: string,
   364	): TimelineShaderAssignmentResult<T> => ({
   365	  ok: false,
   366	  code: 'shader_scope_occupied',
   367	  scope,
   368	  existing,
   369	  incoming,
   370	  message: timelineShaderScopeOccupiedMessage(scope, existing.shaderId, incoming.shaderId, clipId),
   371	});
   372	
   373	export const assignTimelineClipShader = (
   374	  clip: TimelineClip,
   375	  shader: TimelineClipShaderMetadata,
   376	): TimelineShaderAssignmentResult<TimelineClip> => {
   377	  const existing = getTimelineClipShader(clip);
   378	  if (existing && !sameTimelineShaderIdentity(existing, shader)) {
   379	    return createShaderScopeOccupiedResult('clip', existing, shader, clip.id);
   380	  }
   381	
   382	  return {
   383	    ok: true,
   384	    value: {
   385	      ...clip,
   386	      app: {
   387	        ...(clip.app ?? {}),
   388	        shader,
   389	      },
   390	    },
   391	  };
   392	};
   393	
   394	export const assignTimelinePostprocessShader = (
   395	  config: TimelineConfig,
   396	  shader: TimelinePostprocessShaderMetadata,
   397	): TimelineShaderAssignmentResult<TimelineConfig> => {
   398	  const existing = getTimelinePostprocessShader(config);
   399	  if (existing && !sameTimelineShaderIdentity(existing, shader)) {
   400	    return createShaderScopeOccupiedResult('postprocess', existing, shader);
   401	  }
   402	
   403	  return {
   404	    ok: true,
   405	    value: {
   406	      ...config,
   407	      app: {
   408	        ...(config.app ?? {}),
   409	        [TIMELINE_POSTPROCESS_SHADER_APP_KEY]: shader,
   410	      },
   411	    },
   412	  };
   413	};
   414	
   415	const createIssue = (
   416	  level: TimelineDomainContractLevel,
   417	  severity: TimelineDomainIssueSeverity,
   418	  code: TimelineDomainIssueCode,
   419	  message: string,
   420	  extra: Omit<TimelineDomainIssue, 'level' | 'severity' | 'code' | 'message'> = {},

codex
The current “spine” is not yet a graph object; it is a set of projections and compatibility wrappers. The reader builds `TimelineSnapshot` from raw config/app fields, the router synthesizes `CapabilityRequirement`s from clip shape, and `planRender` aggregates those plus registry descriptors.
exec
/bin/zsh -lc "nl -ba src/tools/video-editor/runtime/renderPlanner.ts | sed -n '760,1160p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
   760	
   761	function materialBlockerReason(
   762	  materialRef: RenderMaterialRef,
   763	  status: RenderPlannerMaterialStatus | undefined,
   764	): RenderBlockerReason | undefined {
   765	  if (status?.state === 'missing') return 'missing-material';
   766	  if (status?.state === 'stale') return 'materialization-failed';
   767	  if (status?.state === 'resolved') return undefined;
   768	  if (status?.state === 'unbaked') return materialRef.determinism;
   769	  if (materialRef.determinism === 'live-unbaked' || materialRef.determinism === 'process-dependent') {
   770	    return materialRef.determinism;
   771	  }
   772	  return undefined;
   773	}
   774	
   775	function collectMaterialRef(
   776	  acc: PlanAccumulator,
   777	  materialRef: RenderMaterialRef,
   778	  materialStatusById: ReadonlyMap<string, RenderPlannerMaterialStatus>,
   779	): void {
   780	  addRouteValue(acc.routeDeterminism, 'browser-export', materialRef.determinism);
   781	  if (materialRef.replacementPolicy !== 'materialize-on-export') return;
   782	
   783	  const status = materialStatusById.get(materialRef.id);
   784	  const reason = materialBlockerReason(materialRef, status);
   785	  if (!reason) return;
   786	  const message = status?.message ?? `Material "${materialRef.id}" must be materialized before browser export.`;
   787	  const blocker: RenderBlocker = {
   788	    id: `planner.material.${materialRef.id}.browser-export.${reason}`,
   789	    severity: 'error',
   790	    route: 'browser-export',
   791	    reason,
   792	    message,
   793	    materialRefId: materialRef.id,
   794	    extensionId: materialRef.producerExtensionId,
   795	    detail: {
   796	      source: 'material-ref',
   797	      mediaKind: materialRef.mediaKind,
   798	      locatorKind: materialRef.locator.kind,
   799	      replacementPolicy: materialRef.replacementPolicy,
   800	      determinism: materialRef.determinism,
   801	      materialState: status?.state ?? 'unbaked',
   802	    },
   803	  };
   804	  acc.findings.push(blocker);
   805	  acc.blockers.push(blocker);
   806	  acc.nextActions.push(materializeAction(`Materialize ${materialRef.id}`, message));
   807	}
   808	
   809	function collectRenderGroups(acc: PlanAccumulator, snapshot: TimelineSnapshot | null | undefined): void {
   810	  for (const group of snapshot?.renderGroups ?? []) {
   811	    for (const pass of group.passes ?? []) {
   812	      if (!pass.required) continue;
   813	      if (pass.status !== 'missing' && pass.status !== 'stale') continue;
   814	
   815	      const reason: RenderBlockerReason = pass.status === 'missing'
   816	        ? 'missing-material'
   817	        : 'materialization-failed';
   818	      const message = `Render group "${group.id}" pass "${pass.passName}" is ${pass.status}.`;
   819	      const blocker: RenderBlocker = {
   820	        id: `planner.renderGroup.${group.id}.${pass.id}.browser-export.${reason}`,
   821	        severity: 'error',
   822	        route: 'browser-export',
   823	        reason,
   824	        message,
   825	        materialRefId: pass.materialRefId,
   826	        detail: {
   827	          source: 'render-group',
   828	          renderGroupId: group.id,
   829	          passId: pass.id,
   830	          passName: pass.passName,
   831	          passStatus: pass.status,
   832	          composable: pass.composable,
   833	          required: pass.required,
   834	        },
   835	      };
   836	      addRouteSetValue(acc.routeCapabilities, 'browser-export', 'render-groups');
   837	      addRouteValue(acc.routeDeterminism, 'browser-export', 'process-dependent');
   838	      acc.findings.push(blocker);
   839	      acc.blockers.push(blocker);
   840	      acc.nextActions.push(materializeAction(`Materialize ${group.id}:${pass.passName}`, message));
   841	    }
   842	  }
   843	}
   844	
   845	function mostConservativeDeterminism(statuses: readonly DeterminismStatus[]): DeterminismStatus {
   846	  if (statuses.length === 0) return 'deterministic';
   847	  return [...statuses].sort((a, b) => DETERMINISM_RANK[b] - DETERMINISM_RANK[a])[0];
   848	}
   849	
   850	function sortedActions(
   851	  actions: readonly VideoEditorPlannerNextActionDescriptor[],
   852	): readonly VideoEditorPlannerNextActionDescriptor[] {
   853	  const seen = new Set<string>();
   854	  return Object.freeze([...actions]
   855	    .sort((a, b) =>
   856	      `${a.kind}:${a.route ?? ''}:${a.processId ?? ''}:${a.operationId ?? ''}:${a.label}`
   857	        .localeCompare(`${b.kind}:${b.route ?? ''}:${b.processId ?? ''}:${b.operationId ?? ''}:${b.label}`))
   858	    .filter((action) => {
   859	      const key = `${action.kind}:${action.route ?? ''}:${action.processId ?? ''}:${action.operationId ?? ''}:${action.label}`;
   860	      if (seen.has(key)) return false;
   861	      seen.add(key);
   862	      return true;
   863	    })
   864	    .map((action) => Object.freeze({ ...action })));
   865	}
   866	
   867	function buildRoutePlan(
   868	  route: RenderRoute,
   869	  findings: readonly CapabilityFinding[],
   870	  blockers: readonly RenderBlocker[],
   871	  acc: PlanAccumulator,
   872	): RenderRoutePlan {
   873	  const routeBlockers = blockers.filter((blocker) => blocker.route === route);
   874	  const routeFindings = findings.filter((finding) => !finding.route || finding.route === route);
   875	  const requiredCapabilities = Object.freeze([...(acc.routeCapabilities.get(route) ?? new Set())].sort());
   876	  const outputFormatIds = Object.freeze([...(acc.routeOutputFormatIds.get(route) ?? new Set())].sort());
   877	  const processRequirements = Object.freeze([...(acc.routeProcessRequirements.get(route) ?? [])]
   878	    .sort((a, b) =>
   879	      `${a.processId}:${a.operationId ?? ''}:${a.requiredCapabilities.join(',')}`
   880	        .localeCompare(`${b.processId}:${b.operationId ?? ''}:${b.requiredCapabilities.join(',')}`))
   881	    .map((requirement) => Object.freeze({
   882	      ...requirement,
   883	      requiredCapabilities: Object.freeze([...requirement.requiredCapabilities].sort()),
   884	    })));
   885	
   886	  const actions = sortedActions(acc.nextActions.filter((action) => !action.route || action.route === route));
   887	  return Object.freeze({
   888	    route,
   889	    blockerCount: routeBlockers.length,
   890	    findingCount: routeFindings.length,
   891	    blocked: routeBlockers.length > 0,
   892	    requiredCapabilities,
   893	    determinism: mostConservativeDeterminism(acc.routeDeterminism.get(route) ?? []),
   894	    blockers: Object.freeze(routeBlockers),
   895	    diagnostics: Object.freeze(routeFindings),
   896	    outputFormatIds,
   897	    processRequirements,
   898	    nextActions: actions,
   899	  });
   900	}
   901	
   902	function emptyGuard(
   903	  findings: readonly CapabilityFinding[],
   904	  blockers: readonly RenderBlocker[],
   905	): RenderPlannerGuardCompatibility {
   906	  return Object.freeze({
   907	    diagnostics: findings,
   908	    findings,
   909	    blockers,
   910	    unknownClipTypes: Object.freeze([]),
   911	    unknownEffects: Object.freeze([]),
   912	    unknownTransitions: Object.freeze([]),
   913	    inactiveExtensionIds: EMPTY_IDS,
   914	    hasBlockingErrors: blockers.length > 0,
   915	  });
   916	}
   917	
   918	export function planRender(input: RenderPlannerInput): RenderPlannerResult {
   919	  const acc = createAccumulator();
   920	  const shaderComposition = diagnoseSnapshotShaderComposition(input.snapshot);
   921	  const requirements = input.requirements ?? (shaderComposition.snapshot
   922	    ? getCapabilityRequirements(shaderComposition.snapshot)
   923	    : []);
   924	  const outputFormats = input.outputFormats ?? input.extensionRuntime?.outputFormats ?? [];
   925	  const processes = input.processes ?? input.extensionRuntime?.processes ?? [];
   926	  const shaders = input.shaders ?? input.extensionRuntime?.shaders ?? [];
   927	  const processStatusById = createProcessStatusMap(input.processStatuses);
   928	  const processById = createProcessDescriptorMap(processes);
   929	  const shaderBySourceRef = createShaderDescriptorMap(shaders);
   930	  const materialStatusById = createMaterialStatusMap(input.materialStatuses);
   931	  const requestedOutputFormat = input.request?.outputFormatId
   932	    ? outputFormats.find((format) => format.id === input.request?.outputFormatId)
   933	    : undefined;
   934	
   935	  for (const requirement of requirements) {
   936	    const shaderDescriptor = isShaderMaterializerRequirement(requirement)
   937	      ? shaderBySourceRef.get(shaderDescriptorKey(
   938	        requirement.sourceRef.extensionId,
   939	        requirement.sourceRef.contributionId,
   940	      ))
   941	      : undefined;
   942	    if (
   943	      shaderDescriptor
   944	      && shaderMaterializerSupportsRoute(shaderDescriptor, requirement, processById)
   945	    ) {
   946	      collectShaderMaterializerRequirement(acc, requirement, shaderDescriptor, processStatusById);
   947	      continue;
   948	    }
   949	    collectRequirement(acc, requirement);
   950	  }
   951	  collectRequestCapabilities(acc, input.request);
   952	  for (const outputFormat of outputFormats) {
   953	    if (input.request?.outputFormatId && input.request.outputFormatId !== outputFormat.id) continue;
   954	    collectOutputFormat(acc, outputFormat, processStatusById);
   955	  }
   956	  collectRequestedOutputRouteSupport(acc, requestedOutputFormat, input.request);
   957	  for (const process of processes) {
   958	    collectProcess(acc, process);
   959	  }
   960	  for (const materialRef of input.materialRefs ?? []) {
   961	    collectMaterialRef(acc, materialRef, materialStatusById);
   962	  }
   963	  collectRenderGroups(acc, input.snapshot);
   964	  acc.findings.push(...shaderComposition.findings);
   965	  acc.findings.push(...(input.diagnostics ?? []));
   966	
   967	  if (input.request?.outputFormatId && !outputFormats.some((format) => format.id === input.request?.outputFormatId)) {
   968	    const blocker: RenderBlocker = {
   969	      id: `planner.outputFormat.${input.request.outputFormatId}.missing`,
   970	      severity: 'error',
   971	      route: input.request.route ?? input.request.routes?.[0] ?? 'sidecar-export',
   972	      reason: 'missing-contribution',
   973	      message: `Output format "${input.request.outputFormatId}" is not registered.`,
   974	      contributionId: input.request.outputFormatId,
   975	      detail: {
   976	        source: 'render-request',
   977	        outputFormatId: input.request.outputFormatId,
   978	      },
   979	    };
   980	    acc.findings.push(blocker);
   981	    acc.blockers.push(blocker);
   982	  }
   983	
   984	  const findings = sortedFindings(acc.findings);
   985	  const blockers = sortedBlockers([
   986	    ...acc.blockers,
   987	    ...findings.map(blockerForFinding).filter((blocker): blocker is RenderBlocker => Boolean(blocker)),
   988	  ]);
   989	  const routePlans = Object.freeze(RENDER_ROUTES.map((route) => buildRoutePlan(route, findings, blockers, acc)));
   990	  const routes = Object.freeze(routePlans.map((routePlan) => Object.freeze({
   991	    route: routePlan.route,
   992	    blockerCount: routePlan.blockerCount,
   993	    findingCount: routePlan.findingCount,
   994	    blocked: routePlan.blocked,
   995	  })));
   996	  const browserRoute = routePlans.find((route) => route.route === 'browser-export');
   997	  const workerRoute = routePlans.find((route) => route.route === 'worker-export');
   998	
   999	  return Object.freeze({
  1000	    guard: emptyGuard(findings, blockers),
  1001	    findings,
  1002	    blockers,
  1003	    routes,
  1004	    routePlans,
  1005	    diagnostics: findings,
  1006	    nextActions: sortedActions(acc.nextActions),
  1007	    canBrowserExport: !browserRoute?.blocked,
  1008	    canWorkerExport: !workerRoute?.blocked,
  1009	  });
  1010	}

exec
/bin/zsh -lc "nl -ba src/tools/video-editor/lib/timeline-reader.ts | sed -n '340,760p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
   340	        const clipMeta = metaMap[clip.id];
   341	        if (!clipMeta) continue;
   342	
   343	        const { managed, managedBy } = deriveManaged(clip, knownExtensionIds);
   344	
   345	        const generatedMeta: GeneratedObjectMeta | undefined =
   346	          extractGeneratedMeta(clip.app);
   347	
   348	        const clipShader = isClipShaderMetadata(clip.app?.shader)
   349	          ? clip.app.shader
   350	          : undefined;
   351	        if (clipShader) {
   352	          shaderSummaries.push({
   353	            id: `${clip.id}:shader:${clipShader.shaderId}`,
   354	            shaderId: clipShader.shaderId,
   355	            scope: 'clip',
   356	            clipId: clip.id,
   357	            extensionId: clipShader.extensionId,
   358	            contributionId: clipShader.contributionId,
   359	            enabled: clipShader.enabled !== false,
   360	          });
   361	        }
   362	
   363	        // ── Extract effects ──────────────────────────────────────────
   364	        const clipEffects: TimelineEffectSummary[] = [];
   365	        const rawEffects = clipMeta.effects ?? clip.effects;
   366	        if (rawEffects) {
   367	          if (Array.isArray(rawEffects)) {
   368	            for (let ei = 0; ei < rawEffects.length; ei += 1) {
   369	              const eff = rawEffects[ei];
   370	              if (!eff || typeof eff !== 'object') continue;
   371	              const effectObj = eff as Record<string, unknown>;
   372	              const effectType =
   373	                typeof effectObj.type === 'string'
   374	                  ? effectObj.type
   375	                  : typeof effectObj.effectId === 'string'
   376	                    ? effectObj.effectId
   377	                    : undefined;
   378	              const effectId = `${clip.id}.effect.${effectType ?? `unnamed.${ei}`}`;
   379	              const effectManaged = deriveEffectManaged(
   380	                effectObj,
   381	                knownExtensionIds,
   382	              );
   383	              clipEffects.push({
   384	                id: effectId,
   385	                clipId: clip.id,
   386	                effectType,
   387	                params:
   388	                  effectObj.params !== undefined &&
   389	                  typeof effectObj.params === 'object' &&
   390	                  !Array.isArray(effectObj.params)
   391	                    ? (effectObj.params as Record<string, unknown>)
   392	                    : undefined,
   393	                ...(effectManaged.managed
   394	                  ? { managed: true, managedBy: effectManaged.managedBy }
   395	                  : {}),
   396	              });
   397	              effectSummaries.push(clipEffects[clipEffects.length - 1]);
   398	            }
   399	          } else if (typeof rawEffects === 'object') {
   400	            // Record<string, number> — effect names to intensity
   401	            for (const [effectName, intensity] of Object.entries(
   402	              rawEffects as Record<string, unknown>,
   403	            )) {
   404	              if (typeof intensity !== 'number') continue;
   405	              const effectId = `${clip.id}.effect.${effectName}`;
   406	              const effectEntry: TimelineEffectSummary = {
   407	                id: effectId,
   408	                clipId: clip.id,
   409	                effectType: effectName,
   410	                params: { intensity },
   411	              };
   412	              clipEffects.push(effectEntry);
   413	              effectSummaries.push(effectEntry);
   414	            }
   415	          }
   416	        }
   417	
   418	        // ── Extract transition ───────────────────────────────────────
   419	        let clipTransition: TimelineTransitionSummary | undefined;
   420	        const rawTransition = clipMeta.transition ?? clip.transition;
   421	        if (rawTransition && typeof rawTransition === 'object') {
   422	          const tObj = rawTransition as Record<string, unknown>;
   423	          const transitionType =
   424	            typeof tObj.type === 'string' ? tObj.type : undefined;
   425	          const transitionDuration =
   426	            typeof tObj.duration === 'number'
   427	              ? tObj.duration
   428	              : 0;
   429	          const transitionManaged = deriveEffectManaged(
   430	            tObj,
   431	            knownExtensionIds,
   432	          );
   433	          clipTransition = {
   434	            id: `${clip.id}.transition.${transitionType ?? 'unknown'}`,
   435	            clipId: clip.id,
   436	            transitionType,
   437	            duration: transitionDuration,
   438	            params:
   439	              tObj.params !== undefined &&
   440	              typeof tObj.params === 'object' &&
   441	              !Array.isArray(tObj.params)
   442	                ? (tObj.params as Record<string, unknown>)
   443	                : undefined,
   444	            ...(transitionManaged.managed
   445	              ? { managed: true, managedBy: transitionManaged.managedBy }
   446	              : {}),
   447	          };
   448	          transitionSummaries.push(clipTransition);
   449	        }
   450	
   451	        // ── Extract live bindings ────────────────────────────────────
   452	        const clipLiveBindings: TimelineLiveBindingSummary[] = [];
   453	        for (const record of liveBindingsByClip.get(clip.id) ?? []) {
   454	          const binding: TimelineLiveBindingSummary = {
   455	            bindingId: record.binding.bindingId,
   456	            clipId: clip.id,
   457	            sourceId: record.binding.sourceId,
   458	            sourceKind: record.binding.sourceKind,
   459	            ...(record.binding.targetParamName !== undefined
   460	              ? { targetParamName: record.binding.targetParamName }
   461	              : {}),
   462	            status: record.status,
   463	          };
   464	          clipLiveBindings.push(binding);
   465	          liveBindingSummaries.push(binding);
   466	        }
   467	
   468	        // ── Extract material refs ────────────────────────────────────
   469	        const clipMaterialRefs: TimelineMaterialRefSummary[] = [];
   470	        if (clipMeta.asset) {
   471	          clipMaterialRefs.push({
   472	            id: `material.asset.${clipMeta.asset}.${clip.id}`,
   473	            clipId: clip.id,
   474	            assetKey: clipMeta.asset,
   475	            mediaKind: 'unknown',
   476	            determinism: 'deterministic',
   477	          });
   478	          materialRefSummaries.push(clipMaterialRefs[0]);
   479	        }
   480	        // Check for generation material refs
   481	        if (clipMeta.generation) {
   482	          clipMaterialRefs.push({
   483	            id: `material.generation.${clip.id}`,
   484	            clipId: clip.id,
   485	            mediaKind: 'unknown',
   486	            determinism: 'process-dependent',
   487	          });
   488	          materialRefSummaries.push(clipMaterialRefs[clipMaterialRefs.length - 1]);
   489	        }
   490	
   491	        // ── Extract source refs ──────────────────────────────────────
   492	        const clipSourceRefs: TimelineSourceRefSummary[] = [];
   493	        if (clipMeta.source_uuid) {
   494	          const sourceRef: TimelineSourceRefSummary = {
   495	            id: `source.${clipMeta.source_uuid}.${clip.id}`,
   496	            clipId: clip.id,
   497	            sourceKind: knownExtensionIds.has(clipMeta.source_uuid)
   498	              ? 'extension'
   499	              : 'unknown',
   500	            sourceUuid: clipMeta.source_uuid,
   501	            ...(knownExtensionIds.has(clipMeta.source_uuid)
   502	              ? { extensionId: clipMeta.source_uuid }
   503	              : {}),
   504	            determinism: knownExtensionIds.has(clipMeta.source_uuid)
   505	              ? 'preview-only'
   506	              : 'unknown',
   507	          };
   508	          clipSourceRefs.push(sourceRef);
   509	          sourceRefSummaries.push(sourceRef);
   510	        }
   511	        if (clipMeta.generation) {
   512	          const generation = clipMeta.generation as Record<string, unknown>;
   513	          const generationId = getStringField(generation, ['id', 'generationId', 'uuid']);
   514	          const extensionId = getStringField(generation, ['extensionId', 'providerId']);
   515	          const sourceRef: TimelineSourceRefSummary = {
   516	            id: `source.generation.${generationId ?? clip.id}`,
   517	            clipId: clip.id,
   518	            sourceKind: extensionId ? 'extension' : 'generation',
   519	            ...(generationId ? { generationId } : {}),
   520	            ...(extensionId ? { extensionId } : {}),
   521	            determinism: 'process-dependent',
   522	          };
   523	          clipSourceRefs.push(sourceRef);
   524	          sourceRefSummaries.push(sourceRef);
   525	        }
   526	
   527	        clipSummaries.push({
   528	          id: clip.id,
   529	          track: clip.track,
   530	          at: clip.at,
   531	          clipType: clip.clipType,
   532	          duration: computeClipDuration(clipMeta),
   533	          managed,
   534	          ...(managedBy !== undefined ? { managedBy } : {}),
   535	          ...(generatedMeta !== undefined ? { generatedMeta } : {}),
   536	          ...(clipEffects.length > 0 ? { effects: clipEffects } : {}),
   537	          ...(clipTransition !== undefined ? { transition: clipTransition } : {}),
   538	          ...(clipLiveBindings.length > 0
   539	            ? { liveBindings: clipLiveBindings }
   540	            : {}),
   541	          ...(clipMaterialRefs.length > 0
   542	            ? { materialRefs: clipMaterialRefs }
   543	            : {}),
   544	          ...(clipSourceRefs.length > 0
   545	            ? { sourceRefs: clipSourceRefs }
   546	            : {}),
   547	        });
   548	      }
   549	
   550	      // ── Tracks ─────────────────────────────────────────────────────
   551	      const trackSummaries: TimelineTrackSummary[] = (config.tracks ?? []).map(
   552	        (track) => {
   553	          const trackGeneratedMeta: GeneratedObjectMeta | undefined =
   554	            extractGeneratedMeta(track.app);
   555	          return {
   556	            id: track.id,
   557	            kind: track.kind,
   558	            label: track.label,
   559	            muted: track.muted ?? false,
   560	            ...(track.app !== undefined ? { app: track.app } : {}),
   561	            ...(trackGeneratedMeta !== undefined ? { generatedMeta: trackGeneratedMeta } : {}),
   562	          };
   563	        },
   564	      );
   565	
   566	      // ── Asset keys ─────────────────────────────────────────────────
   567	      const assetKeys: string[] = Object.keys(registry.assets ?? {});
   568	
   569	      // ── App data ───────────────────────────────────────────────────
   570	      const app: Record<string, unknown> = config.app !== undefined
   571	        ? { ...config.app }
   572	        : {};
   573	      const postprocessShader = isPostprocessShaderMetadata(app.shaderPostprocess)
   574	        ? app.shaderPostprocess
   575	        : undefined;
   576	      if (postprocessShader) {
   577	        shaderSummaries.push({
   578	          id: `postprocess:shader:${postprocessShader.shaderId}`,
   579	          shaderId: postprocessShader.shaderId,
   580	          scope: 'postprocess',
   581	          extensionId: postprocessShader.extensionId,
   582	          contributionId: postprocessShader.contributionId,
   583	          enabled: postprocessShader.enabled !== false,
   584	        });
   585	      }
   586	
   587	      // ── Source-map entries ─────────────────────────────────────────
   588	      const sourceMapEntries: SourceMapEntry[] = [];
   589	      for (const [, extData] of Object.entries(app)) {
   590	        if (!extData || typeof extData !== 'object' || Array.isArray(extData)) continue;
   591	        const extObj = extData as Record<string, unknown>;
   592	        for (const [key, value] of Object.entries(extObj)) {
   593	          if (!key.startsWith('__sm__:') || !value || typeof value !== 'object') continue;
   594	          const entry = value as Record<string, unknown>;
   595	          if (typeof entry.id !== 'string' || typeof entry.source !== 'string') continue;
   596	          sourceMapEntries.push({
   597	            id: entry.id as string,
   598	            source: entry.source as string,
   599	            targetId: entry.targetId as string,
   600	            targetGranularity: entry.targetGranularity as SourceMapEntry['targetGranularity'],
   601	            sourceUri: entry.sourceUri as string,
   602	            sourceStartLine: typeof entry.sourceStartLine === 'number' ? entry.sourceStartLine : 0,
   603	            sourceStartColumn: typeof entry.sourceStartColumn === 'number' ? entry.sourceStartColumn : 0,
   604	            sourceEndLine: typeof entry.sourceEndLine === 'number' ? entry.sourceEndLine : 0,
   605	            sourceEndColumn: typeof entry.sourceEndColumn === 'number' ? entry.sourceEndColumn : 0,
   606	            stale: entry.stale === true,
   607	            ...(entry.meta !== undefined && typeof entry.meta === 'object' ? { meta: entry.meta as Record<string, unknown> } : {}),
   608	          });
   609	        }
   610	      }
   611	
   612	      // ── Render groups ─────────────────────────────────────────────
   613	      const renderGroups: TimelineRenderGroupSummary[] = [];
   614	      const pinnedGroups = config.pinnedShotGroups;
   615	      if (pinnedGroups && Array.isArray(pinnedGroups)) {
   616	        for (const group of pinnedGroups) {
   617	          if (!group || typeof group !== 'object') continue;
   618	          const clipIds: string[] = [];
   619	          if (Array.isArray(group.clipIds)) {
   620	            for (const cid of group.clipIds) {
   621	              if (typeof cid === 'string') clipIds.push(cid);
   622	            }
   623	          }
   624	          if (clipIds.length > 0) {
   625	            renderGroups.push({
   626	              id: `${group.shotId}:${group.trackId}`,
   627	              clipIds,
   628	              groupType: group.mode ?? 'pinned-shot-group',
   629	            });
   630	          }
   631	        }
   632	      }
   633	
   634	      // ── Output metadata ───────────────────────────────────────────
   635	      const output: TimelineOutputMetadata | undefined = config.output
   636	        ? {
   637	            resolution: config.output.resolution,
   638	            fps: config.output.fps,
   639	            file: config.output.file,
   640	            background: config.output.background ?? null,
   641	            backgroundScale: config.output.background_scale ?? null,
   642	          }
   643	        : undefined;
   644	
   645	      return {
   646	        projectId,
   647	        baseVersion: configVersion,
   648	        currentVersion: configVersion,
   649	        extensionRequirements,
   650	        clips: clipSummaries,
   651	        tracks: trackSummaries,
   652	        assetKeys,
   653	        app,
   654	        sourceMapEntries:
   655	          sourceMapEntries.length > 0 ? sourceMapEntries : undefined,
   656	        effects:
   657	          effectSummaries.length > 0 ? effectSummaries : undefined,
   658	        transitions:
   659	          transitionSummaries.length > 0 ? transitionSummaries : undefined,
   660	        liveBindings:
   661	          liveBindingSummaries.length > 0 ? liveBindingSummaries : undefined,
   662	        materialRefs:
   663	          materialRefSummaries.length > 0 ? materialRefSummaries : undefined,
   664	        sourceRefs:
   665	          sourceRefSummaries.length > 0 ? sourceRefSummaries : undefined,
   666	        shaders:
   667	          shaderSummaries.length > 0 ? shaderSummaries : undefined,
   668	        renderGroups:
   669	          renderGroups.length > 0 ? renderGroups : undefined,
   670	        outputMetadata: output,
   671	      };
   672	    },
   673	  };
   674	}
   675	
   676	// ---------------------------------------------------------------------------
   677	// Re-export getCapabilityRequirements from timeline-reader for planner
   678	// convenience.  The canonical implementation lives in @/sdk/index.ts so it
   679	// stays provider-free.
   680	// ---------------------------------------------------------------------------
   681	export { sdkGetCapabilityRequirements as getCapabilityRequirements };

exec
/bin/zsh -lc "nl -ba src/tools/video-editor/lib/timeline-domain.ts | sed -n '420,980p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
   420	  extra: Omit<TimelineDomainIssue, 'level' | 'severity' | 'code' | 'message'> = {},
   421	): TimelineDomainIssue => ({
   422	  level,
   423	  severity,
   424	  code,
   425	  message,
   426	  ...extra,
   427	});
   428	
   429	const isFiniteNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
   430	
   431	const isPositiveNumber = (value: unknown): value is number => isFiniteNumber(value) && value > 0;
   432	
   433	const stripDupSuffix = (id: string): string => id.replace(/(-dup-\d+)+$/, '');
   434	
   435	const isHoldLikeClip = (clip: TimelineClip): boolean => clip.clipType === 'hold' || typeof clip.hold === 'number';
   436	
   437	const hasValidNonHoldTrim = (clip: Pick<TimelineClip, 'from' | 'to'>): boolean => {
   438	  return isFiniteNumber(clip.from) && isFiniteNumber(clip.to) && clip.to > clip.from;
   439	};
   440	
   441	const getClipAssetDurationSeconds = (registry: AssetRegistry, assetId?: string): number | null => {
   442	  if (!assetId) {
   443	    return null;
   444	  }
   445	
   446	  const duration = registry.assets?.[assetId]?.duration;
   447	  return isPositiveNumber(duration) ? duration : null;
   448	};
   449	
   450	const getDefaultTracks = (config: TimelineConfig): TrackDefinition[] => {
   451	  const videoScale = config.output.background_scale ?? DEFAULT_VIDEO_SCALE;
   452	  return [
   453	    {
   454	      id: 'V1',
   455	      kind: 'visual',
   456	      label: 'V1',
   457	      scale: 1,
   458	      fit: 'cover',
   459	      opacity: 1,
   460	      blendMode: 'normal',
   461	    },
   462	    {
   463	      id: 'V2',
   464	      kind: 'visual',
   465	      label: 'V2',
   466	      scale: videoScale,
   467	      fit: 'contain',
   468	      opacity: 1,
   469	      blendMode: 'normal',
   470	    },
   471	    {
   472	      id: 'V3',
   473	      kind: 'visual',
   474	      label: 'V3',
   475	      scale: 1,
   476	      fit: 'manual',
   477	      opacity: 1,
   478	      blendMode: 'normal',
   479	    },
   480	    {
   481	      id: 'A1',
   482	      kind: 'audio',
   483	      label: 'A1',
   484	      scale: 1,
   485	      fit: 'contain',
   486	      opacity: 1,
   487	      blendMode: 'normal',
   488	    },
   489	  ];
   490	};
   491	
   492	const migrateLegacyEffects = (clip: TimelineClip): TimelineClip => {
   493	  const nextClip: TimelineClip = { ...clip };
   494	  const fadeIn = clip.effects && !Array.isArray(clip.effects) ? clip.effects.fade_in : undefined;
   495	  const fadeOut = clip.effects && !Array.isArray(clip.effects) ? clip.effects.fade_out : undefined;
   496	  const fallback = clip.asset ? LEGACY_ASSET_EFFECTS[clip.asset] : undefined;
   497	
   498	  if (!nextClip.entrance && typeof fadeIn === 'number' && fadeIn > 0) {
   499	    nextClip.entrance = { type: 'fade', duration: fadeIn };
   500	  } else if (!nextClip.entrance && fallback?.entrance) {
   501	    nextClip.entrance = fallback.entrance;
   502	  }
   503	
   504	  if (!nextClip.exit && typeof fadeOut === 'number' && fadeOut > 0) {
   505	    nextClip.exit = { type: 'fade-out', duration: fadeOut };
   506	  } else if (!nextClip.exit && fallback?.exit) {
   507	    nextClip.exit = fallback.exit;
   508	  }
   509	
   510	  if (!nextClip.continuous && fallback?.continuous) {
   511	    nextClip.continuous = fallback.continuous;
   512	  }
   513	
   514	  delete nextClip.effects;
   515	  return nextClip;
   516	};
   517	
   518	const migrateLegacyClip = (clip: TimelineClip): TimelineClip => {
   519	  const nextTrack = LEGACY_TRACK_MAP[clip.track] ?? clip.track;
   520	  const clipType = clip.clipType
   521	    ?? (clip.text ? 'text' : typeof clip.hold === 'number' ? 'hold' : 'media');
   522	
   523	  return migrateLegacyEffects({
   524	    ...clip,
   525	    track: nextTrack,
   526	    clipType,
   527	  });
   528	};
   529	
   530	const ensureBackgroundClip = (
   531	  config: TimelineConfig,
   532	  level: TimelineDomainContractLevel,
   533	  issues?: TimelineDomainIssue[],
   534	): TimelineClip[] => {
   535	  const backgroundAsset = config.output.background;
   536	  if (!backgroundAsset) {
   537	    return config.clips.map(migrateLegacyClip);
   538	  }
   539	
   540	  const migratedClips = config.clips.map(migrateLegacyClip);
   541	  const alreadyPresent = migratedClips.some((clip) => clip.track === 'V1');
   542	  if (alreadyPresent) {
   543	    return migratedClips;
   544	  }
   545	
   546	  const timelineDuration = Math.max(0.1, roundTimelineValue(getConfigTimelineDuration(migratedClips)));
   547	  issues?.push(createIssue(
   548	    level,
   549	    'warning',
   550	    'legacy_background_clip_inserted',
   551	    `Inserted missing V1 background clip for asset '${backgroundAsset}'.`,
   552	    {
   553	      assetId: backgroundAsset,
   554	      path: 'clips',
   555	      repairApplied: true,
   556	      details: { duration: timelineDuration },
   557	    },
   558	  ));
   559	  return [
   560	    {
   561	      id: 'clip-background',
   562	      at: 0,
   563	      track: 'V1',
   564	      clipType: 'hold',
   565	      asset: backgroundAsset,
   566	      hold: timelineDuration,
   567	      opacity: 1,
   568	    },
   569	    ...migratedClips,
   570	  ];
   571	};
   572	
   573	export const getCanonicalClipPlaybackRate = (speed: TimelineClip['speed']): number => {
   574	  return isPositiveNumber(speed) ? speed : 1;
   575	};
   576	
   577	export const getConfigTimelineClipSourceDuration = (clip: TimelineClip): number => {
   578	  if (isHoldLikeClip(clip)) {
   579	    return isFiniteNumber(clip.hold) ? Math.max(0, clip.hold) : 0;
   580	  }
   581	
   582	  if (hasValidNonHoldTrim(clip)) {
   583	    return clip.to - clip.from;
   584	  }
   585	
   586	  return 0;
   587	};
   588	
   589	export const getPairTimelineClipSourceDuration = (
   590	  clip: TimelineClip,
   591	  registry: AssetRegistry,
   592	): number => {
   593	  if (isHoldLikeClip(clip)) {
   594	    return getConfigTimelineClipSourceDuration(clip);
   595	  }
   596	
   597	  if (hasValidNonHoldTrim(clip)) {
   598	    return clip.to - clip.from;
   599	  }
   600	
   601	  return getClipAssetDurationSeconds(registry, clip.asset) ?? 0;
   602	};
   603	
   604	export const getConfigTimelineClipDuration = (clip: TimelineClip): number => {
   605	  return getConfigTimelineClipSourceDuration(clip) / getCanonicalClipPlaybackRate(clip.speed);
   606	};
   607	
   608	export const getPairTimelineClipDuration = (
   609	  clip: TimelineClip,
   610	  registry: AssetRegistry,
   611	): number => {
   612	  return getPairTimelineClipSourceDuration(clip, registry) / getCanonicalClipPlaybackRate(clip.speed);
   613	};
   614	
   615	export const getConfigTimelineDuration = (clips: TimelineClip[]): number => {
   616	  return clips.reduce((maxDuration, clip) => Math.max(maxDuration, clip.at + getConfigTimelineClipDuration(clip)), 0);
   617	};
   618	
   619	export const getPairTimelineDuration = (clips: TimelineClip[], registry: AssetRegistry): number => {
   620	  return clips.reduce((maxDuration, clip) => Math.max(maxDuration, clip.at + getPairTimelineClipDuration(clip, registry)), 0);
   621	};
   622	
   623	export const repairConfig = (
   624	  config: TimelineConfig,
   625	  issues?: TimelineDomainIssue[],
   626	  level: TimelineDomainContractLevel = 'config-only',
   627	): TimelineConfig => {
   628	  let repaired = false;
   629	  let duplicateTrackCount = 0;
   630	  let duplicateClipCount = 0;
   631	  let repairedLegacyGroupCount = 0;
   632	
   633	  const seenTracks = new Set<string>();
   634	  const tracks = (config.tracks ?? []).filter((track) => {
   635	    if (seenTracks.has(track.id)) {
   636	      duplicateTrackCount += 1;
   637	      repaired = true;
   638	      return false;
   639	    }
   640	    seenTracks.add(track.id);
   641	    return true;
   642	  });
   643	
   644	  const seenClips = new Set<string>();
   645	  const clips: TimelineClip[] = [];
   646	  for (const clip of config.clips) {
   647	    const baseId = stripDupSuffix(clip.id);
   648	    if (seenClips.has(baseId)) {
   649	      duplicateClipCount += 1;
   650	      repaired = true;
   651	      continue;
   652	    }
   653	    seenClips.add(baseId);
   654	    clips.push(baseId !== clip.id ? { ...clip, id: baseId } : clip);
   655	  }
   656	
   657	  const pinnedShotGroups = config.pinnedShotGroups?.map((group) => {
   658	    const legacy = group as LegacyPinnedShotGroup;
   659	    const hasLegacyFields = typeof legacy.start === 'number' || Array.isArray(legacy.children);
   660	
   661	    if (!hasLegacyFields) {
   662	      return group;
   663	    }
   664	
   665	    repaired = true;
   666	    repairedLegacyGroupCount += 1;
   667	    const derivedClipIds = Array.isArray(legacy.children) && legacy.children.length > 0
   668	      ? legacy.children.map((child) => child.clipId).filter((id): id is string => typeof id === 'string' && id.length > 0)
   669	      : [...group.clipIds];
   670	
   671	    return {
   672	      shotId: group.shotId,
   673	      trackId: group.trackId,
   674	      clipIds: derivedClipIds,
   675	      mode: group.mode,
   676	      videoAssetKey: group.videoAssetKey,
   677	      imageClipSnapshot: clonePinnedShotImageSnapshots(group.imageClipSnapshot),
   678	    };
   679	  });
   680	
   681	  if (duplicateTrackCount > 0) {
   682	    issues?.push(createIssue(
   683	      level,
   684	      'warning',
   685	      'duplicate_track_removed',
   686	      `Removed ${duplicateTrackCount} duplicate track definition(s).`,
   687	      {
   688	        path: 'tracks',
   689	        repairApplied: true,
   690	        details: { duplicateTrackCount },
   691	      },
   692	    ));
   693	  }
   694	
   695	  if (duplicateClipCount > 0) {
   696	    issues?.push(createIssue(
   697	      level,
   698	      'warning',
   699	      'duplicate_clip_removed',
   700	      `Removed ${duplicateClipCount} duplicate clip(s) after stripping cascading -dup suffixes.`,
   701	      {
   702	        path: 'clips',
   703	        repairApplied: true,
   704	        details: { duplicateClipCount },
   705	      },
   706	    ));
   707	  }
   708	
   709	  if (repairedLegacyGroupCount > 0) {
   710	    issues?.push(createIssue(
   711	      level,
   712	      'warning',
   713	      'legacy_pinned_shot_group_repaired',
   714	      `Repaired ${repairedLegacyGroupCount} legacy pinned shot group projection(s).`,
   715	      {
   716	        path: 'pinnedShotGroups',
   717	        repairApplied: true,
   718	        details: { repairedLegacyGroupCount },
   719	      },
   720	    ));
   721	  }
   722	
   723	  return repaired ? { ...config, tracks, clips, pinnedShotGroups } : config;
   724	};
   725	
   726	export const migrateToFlatTracks = (
   727	  config: TimelineConfig,
   728	  issues?: TimelineDomainIssue[],
   729	  level: TimelineDomainContractLevel = 'config-only',
   730	): TimelineConfig => {
   731	  if (config.tracks?.length) {
   732	    return {
   733	      output: { ...config.output },
   734	      tracks: config.tracks.map((track) => ({ ...track })),
   735	      clips: config.clips.map((clip) => ({
   736	        ...clip,
   737	        clipType: clip.clipType
   738	          ?? (clip.text ? 'text' : typeof clip.hold === 'number' ? 'hold' : 'media'),
   739	      })),
   740	      pinnedShotGroups: clonePinnedShotGroups(config.pinnedShotGroups),
   741	      ...cloneTimelineExtras(config),
   742	    };
   743	  }
   744	
   745	  issues?.push(createIssue(
   746	    level,
   747	    'warning',
   748	    'legacy_tracks_migrated',
   749	    'Migrated legacy timeline config into the flat-track shape.',
   750	    {
   751	      path: 'tracks',
   752	      repairApplied: true,
   753	    },
   754	  ));
   755	
   756	  return {
   757	    output: { ...config.output },
   758	    tracks: getDefaultTracks(config),
   759	    clips: ensureBackgroundClip(config, level, issues),
   760	    pinnedShotGroups: clonePinnedShotGroups(config.pinnedShotGroups),
   761	    ...cloneTimelineExtras(config),
   762	  };
   763	};
   764	
   765	export const repairShotGroupContiguity = (
   766	  config: TimelineConfig,
   767	  issues?: TimelineDomainIssue[],
   768	  level: TimelineDomainContractLevel = 'config-only',
   769	): TimelineConfig => {
   770	  if (!config.pinnedShotGroups?.length) {
   771	    return config;
   772	  }
   773	
   774	  const clipById = new Map<string, TimelineClip>();
   775	  for (const clip of config.clips) {
   776	    clipById.set(clip.id, clip);
   777	  }
   778	
   779	  let totalFixed = 0;
   780	  const clipAtOverrides = new Map<string, number>();
   781	
   782	  for (const group of config.pinnedShotGroups) {
   783	    if (group.clipIds.length < 2) {
   784	      continue;
   785	    }
   786	
   787	    const groupClips: TimelineClip[] = [];
   788	    for (const clipId of group.clipIds) {
   789	      const clip = clipById.get(clipId);
   790	      if (clip) {
   791	        groupClips.push(clip);
   792	      }
   793	    }
   794	    if (groupClips.length < 2) {
   795	      continue;
   796	    }
   797	
   798	    groupClips.sort((left, right) => left.at - right.at);
   799	    let fixedInGroup = 0;
   800	    let cursor = groupClips[0].at + getConfigTimelineClipDuration(groupClips[0]);
   801	
   802	    for (let index = 1; index < groupClips.length; index += 1) {
   803	      const clip = groupClips[index];
   804	      const gap = Math.abs(clip.at - cursor);
   805	
   806	      if (gap > CONTIGUITY_EPSILON) {
   807	        clipAtOverrides.set(clip.id, roundTimelineValue(cursor));
   808	        fixedInGroup += 1;
   809	      }
   810	
   811	      const duration = getConfigTimelineClipDuration(clip);
   812	      cursor = (clipAtOverrides.get(clip.id) ?? clip.at) + duration;
   813	    }
   814	
   815	    if (fixedInGroup > 0) {
   816	      totalFixed += fixedInGroup;
   817	      issues?.push(createIssue(
   818	        level,
   819	        'warning',
   820	        'shot_group_contiguity_repaired',
   821	        `Snapped ${fixedInGroup} non-contiguous clip(s) back into pinned shot group '${group.shotId}'.`,
   822	        {
   823	          path: 'clips',
   824	          trackId: group.trackId,
   825	          repairApplied: true,
   826	          details: { fixedInGroup, shotId: group.shotId, clipIds: [...group.clipIds] },
   827	        },
   828	      ));
   829	    }
   830	  }
   831	
   832	  if (totalFixed === 0) {
   833	    return config;
   834	  }
   835	
   836	  return {
   837	    ...config,
   838	    clips: config.clips.map((clip) => {
   839	      const override = clipAtOverrides.get(clip.id);
   840	      return override !== undefined ? { ...clip, at: override } : clip;
   841	    }),
   842	    pinnedShotGroups: clonePinnedShotGroups(config.pinnedShotGroups),
   843	  };
   844	};
   845	
   846	const canonicalizeNonHoldTrim = (
   847	  clip: TimelineClip,
   848	  level: TimelineDomainContractLevel,
   849	  issues: TimelineDomainIssue[],
   850	  registry?: AssetRegistry,
   851	): TimelineClip => {
   852	  if (isHoldLikeClip(clip) || hasValidNonHoldTrim(clip)) {
   853	    return clip;
   854	  }
   855	
   856	  const assetDuration = registry ? getClipAssetDurationSeconds(registry, clip.asset) : null;
   857	  if (assetDuration !== null) {
   858	    issues.push(createIssue(
   859	      level,
   860	      'warning',
   861	      'malformed_non_hold_trim_repaired',
   862	      `Repaired malformed trim for clip '${clip.id}' using registry duration ${assetDuration}s.`,
   863	      {
   864	        clipId: clip.id,
   865	        assetId: clip.asset,
   866	        path: `clips.${clip.id}`,
   867	        repairApplied: true,
   868	        details: { from: 0, to: assetDuration },
   869	      },
   870	    ));
   871	    return {
   872	      ...clip,
   873	      from: 0,
   874	      to: roundTimelineValue(assetDuration),
   875	    };
   876	  }
   877	
   878	  issues.push(createIssue(
   879	    level,
   880	    'warning',
   881	    'malformed_non_hold_trim_zero_duration',
   882	    `Clip '${clip.id}' has malformed non-hold trim and no registry duration; canonical duration remains 0s.`,
   883	    {
   884	      clipId: clip.id,
   885	      assetId: clip.asset,
   886	      path: `clips.${clip.id}`,
   887	      repairApplied: false,
   888	      details: {
   889	        from: clip.from,
   890	        to: clip.to,
   891	      },
   892	    },
   893	  ));
   894	  return clip;
   895	};
   896	
   897	const withCanonicalClips = (
   898	  config: TimelineConfig,
   899	  clips: TimelineClip[],
   900	): TimelineConfig => ({
   901	  output: { ...config.output },
   902	  tracks: (config.tracks ?? []).map((track) => ({ ...track })),
   903	  clips,
   904	  pinnedShotGroups: clonePinnedShotGroups(config.pinnedShotGroups),
   905	  ...cloneTimelineExtras(config),
   906	});
   907	
   908	export const canonicalizeTimelineConfigSnapshot = (
   909	  config: TimelineConfig,
   910	): CanonicalTimelineConfigSnapshot => {
   911	  const issues: TimelineDomainIssue[] = [];
   912	  const repairedConfig = repairConfig(config, issues, 'config-only');
   913	  const contiguousConfig = repairShotGroupContiguity(repairedConfig, issues, 'config-only');
   914	  const migratedConfig = migrateToFlatTracks(contiguousConfig, issues, 'config-only');
   915	  // Repair clip transitions against built-in catalog (no registry snapshot in config-only)
   916	  const transitionRepairedConfig = repairTimelineClipTransitions(
   917	    migratedConfig,
   918	    undefined,
   919	    issues,
   920	    'config-only',
   921	  );
   922	  const canonicalConfig = withCanonicalClips(
   923	    transitionRepairedConfig,
   924	    transitionRepairedConfig.clips.map((clip) => canonicalizeNonHoldTrim(clip, 'config-only', issues)),
   925	  );
   926	
   927	  return {
   928	    level: 'config-only',
   929	    config: canonicalConfig,
   930	    issues,
   931	  };
   932	};
   933	
   934	export const canonicalizeTimelinePair = (
   935	  config: TimelineConfig,
   936	  registry: AssetRegistry,
   937	): CanonicalTimelinePair => {
   938	  const issues: TimelineDomainIssue[] = [];
   939	  const repairedConfig = repairConfig(config, issues, 'pair-aware');
   940	  const contiguousConfig = repairShotGroupContiguity(repairedConfig, issues, 'pair-aware');
   941	  const migratedConfig = migrateToFlatTracks(contiguousConfig, issues, 'pair-aware');
   942	  // Repair clip transitions against built-in catalog (no registry snapshot in pair-aware)
   943	  const transitionRepairedConfig = repairTimelineClipTransitions(
   944	    migratedConfig,
   945	    undefined,
   946	    issues,
   947	    'pair-aware',
   948	  );
   949	  const canonicalConfig = withCanonicalClips(
   950	    transitionRepairedConfig,
   951	    transitionRepairedConfig.clips.map((clip) => canonicalizeNonHoldTrim(clip, 'pair-aware', issues, registry)),
   952	  );
   953	
   954	  return {
   955	    level: 'pair-aware',
   956	    config: canonicalConfig,
   957	    registry: cloneAssetRegistry(registry),
   958	    issues,
   959	  };
   960	};
   961	
   962	// ---------------------------------------------------------------------------
   963	// M11 live binding metadata scan / resolution
   964	// ---------------------------------------------------------------------------
   965	
   966	export type TimelineLiveBindingDiagnosticSeverity = 'info' | 'warning' | 'error';
   967	export type TimelineLiveBindingDiagnosticCode =
   968	  | 'live-binding/malformed-metadata'
   969	  | 'live-binding/missing-binding-id'
   970	  | 'live-binding/missing-source-id'
   971	  | 'live-binding/missing-source-kind'
   972	  | 'live-binding/unsupported-source-kind'
   973	  | 'live-binding/sample-payload-rejected'
   974	  | 'live-binding/missing-source'
   975	  | 'live-binding/inactive-source'
   976	  | 'live-binding/disposed-source'
   977	  | 'live-binding/orphaned-source'
   978	  | 'live-binding/partially-baked'
   979	  | 'live-binding/resolved';
   980	

exec
/bin/zsh -lc "rg -n \"CompositionGraph|Composition|Graph|TimelineSnapshot|CapabilityRequirement|materialRefs|sourceRefs|liveBindings|targetParamName|targetPath|shaderPostprocess|app\\.shader|clip\\.app|params\\.materialRefs|outputFormatId|decideRenderRoute|planRender\\(\" src/sdk/index.ts src/tools/video-editor/{runtime,lib,commands,hooks,compositions,render,sequences,shaders} docs/extensions docs/video-editor .megaplan/initiatives/reigh-extension-composition-spine-epic -g '"'!**/*.map'"'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
src/sdk/index.ts:450:  outputFormatId?: string;
src/sdk/index.ts:1382:  sourceRefs?: readonly ToolSourceRef[];
src/sdk/index.ts:1525:  timeline?: TimelineSnapshot;
src/sdk/index.ts:1539:  outputFormatId?: string;
src/sdk/index.ts:2255:  readonly targetParamName?: string;
src/sdk/index.ts:4233: * Each CapabilityRequirement describes what a contribution needs for a
src/sdk/index.ts:4239:export interface CapabilityRequirement {
src/sdk/index.ts:4278:  readonly capabilityRequirements: readonly CapabilityRequirement[];
src/sdk/index.ts:4280:  readonly sourceRefs: readonly CapabilitySourceRef[];
src/sdk/index.ts:4329:  readonly outputFormatId?: string;
src/sdk/index.ts:4738:  targetParamName?: string;
src/sdk/index.ts:4848:// M3: TimelineSnapshot / TimelineReader
src/sdk/index.ts:4856:export interface TimelineSnapshot {
src/sdk/index.ts:4890:  liveBindings?: readonly TimelineLiveBindingSummary[];
src/sdk/index.ts:4892:  materialRefs?: readonly TimelineMaterialRefSummary[];
src/sdk/index.ts:4894:  sourceRefs?: readonly TimelineSourceRefSummary[];
src/sdk/index.ts:4903:/** Lightweight clip summary for TimelineSnapshot projection. */
src/sdk/index.ts:4922:  liveBindings?: readonly TimelineLiveBindingSummary[];
src/sdk/index.ts:4924:  materialRefs?: readonly TimelineMaterialRefSummary[];
src/sdk/index.ts:4926:  sourceRefs?: readonly TimelineSourceRefSummary[];
src/sdk/index.ts:4929:/** Lightweight track summary for TimelineSnapshot projection. */
src/sdk/index.ts:4958:  snapshot(): TimelineSnapshot;
src/sdk/index.ts:4962:// M12: getCapabilityRequirements — provider-free capability inspection
src/sdk/index.ts:4966: * M12: Derive capability requirements from a TimelineSnapshot.
src/sdk/index.ts:4969: * refs present in the snapshot and emits {@link CapabilityRequirement}
src/sdk/index.ts:4977: * @param snapshot - A TimelineSnapshot produced by a TimelineReader.
src/sdk/index.ts:4978: * @returns Ordered array of CapabilityRequirement records.
src/sdk/index.ts:4980:export function getCapabilityRequirements(
src/sdk/index.ts:4981:  snapshot: TimelineSnapshot,
src/sdk/index.ts:4982:): CapabilityRequirement[] {
src/sdk/index.ts:4983:  const requirements: CapabilityRequirement[] = [];
src/sdk/index.ts:5080:  if (snapshot.liveBindings) {
src/sdk/index.ts:5082:    for (const binding of snapshot.liveBindings) {
src/sdk/index.ts:5133:  if (snapshot.materialRefs) {
src/sdk/index.ts:5134:    for (const ref of snapshot.materialRefs) {
src/sdk/index.ts:5150:  if (snapshot.sourceRefs) {
src/sdk/index.ts:5151:    for (const ref of snapshot.sourceRefs) {
src/sdk/index.ts:5988:  readonly timeline: TimelineSnapshot;
src/tools/video-editor/hooks/useRenderState.ts:3:import type { CompositionMetadata } from '@/tools/video-editor/hooks/useDerivedTimeline.ts';
src/tools/video-editor/hooks/useRenderState.ts:234:  return planRender({ diagnostics });
src/tools/video-editor/hooks/useRenderState.ts:292:  renderMetadata: CompositionMetadata | null,
src/tools/video-editor/hooks/useRenderState.ts:414:        importedDecision = renderRouter.decideRenderRoute(resolvedConfig);
src/tools/video-editor/hooks/useRenderState.ts:515:    const outputPlan = planRender({
src/tools/video-editor/hooks/useRenderState.ts:519:        outputFormatId: formatId,
src/tools/video-editor/hooks/useRenderState.ts:531:            detail: { source: 'output-format', outputFormatId: formatId },
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:7:  TimelineSnapshot,
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:45:function makeTimelineSnapshot(overrides?: Partial<TimelineSnapshot>): TimelineSnapshot {
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:160:    const timeline = makeTimelineSnapshot();
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:190:      outputFormatId: 'metadata-json',
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:221:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:257:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:279:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:291:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:313:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:332:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:357:        timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:376:    const timeline = makeTimelineSnapshot();
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:413:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:433:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:459:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:485:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:501:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:656:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:684:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:713:    const timeline = makeTimelineSnapshot();
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:743:    const timeline = makeTimelineSnapshot();
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:779:    const timeline = makeTimelineSnapshot();
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:800:    let capturedTimeline: TimelineSnapshot | undefined;
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:819:    const timeline1 = makeTimelineSnapshot();
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:820:    const timeline2 = makeTimelineSnapshot({
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:854:        formatId: 'always-det', timeline: makeTimelineSnapshot(), assets: makeAssets(), extensionId: 'com.example.test',
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:927:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:946:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:966:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:986:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1024:    const timeline = makeTimelineSnapshot();
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1057:    const timeline = makeTimelineSnapshot();
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1092:    const timeline = makeTimelineSnapshot();
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1119:    let received: TimelineSnapshot | undefined;
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1130:    const timeline = makeTimelineSnapshot({ projectId: 'custom-project' });
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1155:      formatId: 'ref-assets', timeline: makeTimelineSnapshot(), assets, extensionId: 'com.example.ref',
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1178:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1190:    let received: TimelineSnapshot | undefined;
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1201:    const emptyTimeline = makeTimelineSnapshot({ clips: [], assetKeys: [] });
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1232:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1263:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1289:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1313:    const timeline = makeTimelineSnapshot();
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1351:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1379:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1399:      outputFormatId: 'full-artifact',
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1410:    const timeline = makeTimelineSnapshot({ assetKeys: ['img-main', 'audio-narration'] });
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1440:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1464:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/outputFormatRegistry.test.ts:1490:      timeline: makeTimelineSnapshot(),
src/tools/video-editor/runtime/renderPlanner.test.ts:5:  CapabilityRequirement,
src/tools/video-editor/runtime/renderPlanner.test.ts:8:  TimelineSnapshot,
src/tools/video-editor/runtime/renderPlanner.test.ts:16:function snapshotWithLiveBinding(): TimelineSnapshot {
src/tools/video-editor/runtime/renderPlanner.test.ts:42:    liveBindings: [
src/tools/video-editor/runtime/renderPlanner.test.ts:59:function snapshotWithShaders(): TimelineSnapshot {
src/tools/video-editor/runtime/renderPlanner.test.ts:112:function requirement(input: Partial<CapabilityRequirement> & Pick<CapabilityRequirement, 'id' | 'route'>): CapabilityRequirement {
src/tools/video-editor/runtime/renderPlanner.test.ts:166:      sourceRefs: [
src/tools/video-editor/runtime/renderPlanner.test.ts:303:  it('derives route blockers from a public TimelineSnapshot without registry inputs', () => {
src/tools/video-editor/runtime/renderPlanner.test.ts:304:    const result = planRender({ snapshot: snapshotWithLiveBinding() });
src/tools/video-editor/runtime/renderPlanner.test.ts:332:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:377:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:438:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:519:    const result = planRender({ snapshot: snapshotWithShaders() });
src/tools/video-editor/runtime/renderPlanner.test.ts:548:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:602:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:671:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:674:      request: { outputFormatId: 'dataset.zip' },
src/tools/video-editor/runtime/renderPlanner.test.ts:685:      outputFormatIds: ['dataset.zip'],
src/tools/video-editor/runtime/renderPlanner.test.ts:713:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:715:      request: { outputFormatId: 'missing.format', route: 'sidecar-export' },
src/tools/video-editor/runtime/renderPlanner.test.ts:734:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:737:        outputFormatId: 'dataset.zip',
src/tools/video-editor/runtime/renderPlanner.test.ts:755:      outputFormatIds: ['dataset.zip'],
src/tools/video-editor/runtime/renderPlanner.test.ts:768:    const result = planRender({ materialRefs: [materialRef] });
src/tools/video-editor/runtime/renderPlanner.test.ts:782:    const result = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:783:      materialRefs: [
src/tools/video-editor/runtime/renderPlanner.test.ts:836:    const ready = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:840:      request: { outputFormatId: 'dataset.zip' },
src/tools/video-editor/runtime/renderPlanner.test.ts:842:    const degraded = planRender({
src/tools/video-editor/runtime/renderPlanner.test.ts:846:      request: { outputFormatId: 'dataset.zip' },
src/tools/video-editor/runtime/renderPlanner.test.ts:886:    const result = planRender({
src/tools/video-editor/runtime/agentToolContracts.ts:576:      // Validate sourceRefs if present
src/tools/video-editor/runtime/agentToolContracts.ts:577:      if (r.sourceRefs !== undefined) {
src/tools/video-editor/runtime/agentToolContracts.ts:578:        if (!Array.isArray(r.sourceRefs)) {
src/tools/video-editor/runtime/agentToolContracts.ts:582:              'sourceRefs must be an array.',
src/tools/video-editor/runtime/agentToolContracts.ts:924:  if (result.sourceRefs && result.sourceRefs.length > 0) {
src/tools/video-editor/runtime/agentToolContracts.ts:925:    const refSummaries = result.sourceRefs
src/tools/video-editor/runtime/agentToolContracts.ts:992:    if (result.sourceRefs && result.sourceRefs.length > 0) {
src/tools/video-editor/runtime/agentToolContracts.ts:993:      const refSummaries = result.sourceRefs
src/tools/video-editor/runtime/agentToolInvocationService.ts:205:        sourceRefs: result.sourceRefs,
src/tools/video-editor/runtime/outputFormatRegistry.ts:19:  TimelineSnapshot,
src/tools/video-editor/runtime/outputFormatRegistry.ts:89:  readonly timeline: TimelineSnapshot;
src/tools/video-editor/runtime/outputFormatRegistry.ts:161:      outputFormatId: options.formatId,
src/tools/video-editor/runtime/outputFormatRegistry.ts:191:    outputFormatId: options.formatId,
src/tools/video-editor/runtime/outputFormatRegistry.ts:249:      outputFormatId: options.formatId,
src/tools/video-editor/runtime/outputFormatRegistry.ts:287:    outputFormatId: options.formatId,
src/tools/video-editor/compositions/VisualClip.test.tsx:310:        materialRefs={[ref]}
src/tools/video-editor/compositions/VisualClip.test.tsx:323:        materialRefs={[ref]}
src/tools/video-editor/compositions/VisualClip.test.tsx:335:        materialRefs={[ref]}
src/tools/video-editor/compositions/VisualClip.test.tsx:350:        materialRefs={[materialRef({ determinism: 'deterministic' })]}
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:599:      app: { shaderPostprocess: postprocessShader },
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:626:      app: { shaderPostprocess: postprocessShader },
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:1002:    liveBindings: unknown,
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:1009:    params: { liveBindings },
src/tools/video-editor/compositions/TimelineRenderer.sequence.test.tsx:1183:      liveBindings: [binding],
src/tools/video-editor/runtime/exportGuard.test.ts:590:    const planned = planRender({ diagnostics: [...scan.findings, ...scan.blockers] });
src/tools/video-editor/runtime/exportGuard.test.ts:1397:        shaderPostprocess: {
src/tools/video-editor/runtime/exportGuard.test.ts:1447:    expect(planRender({ diagnostics: result.findings }).canBrowserExport).toBe(false);
src/tools/video-editor/runtime/extensionSurface.ts:39:  CapabilityRequirement,
src/tools/video-editor/runtime/extensionSurface.ts:1296:      sourceRefs: Object.freeze([sourceRef]),
src/tools/video-editor/runtime/extensionSurface.ts:1314:  const capabilityRequirements: CapabilityRequirement[] = routes.map((route) => Object.freeze({
src/tools/video-editor/runtime/extensionSurface.ts:1355:    sourceRefs: Object.freeze([sourceRef]),
src/tools/video-editor/compositions/VisualClip.tsx:195:  materialRefs?: readonly RenderMaterialRef[];
src/tools/video-editor/compositions/VisualClip.tsx:268:function materialRefsForClip(
src/tools/video-editor/compositions/VisualClip.tsx:270:  materialRefs: readonly RenderMaterialRef[] | undefined,
src/tools/video-editor/compositions/VisualClip.tsx:272:  if (materialRefs && materialRefs.length > 0) return materialRefs;
src/tools/video-editor/compositions/VisualClip.tsx:273:  const app = isRecord(clip.app) ? clip.app : undefined;
src/tools/video-editor/compositions/VisualClip.tsx:274:  const refs = app?.materialRefs ?? clip.params?.materialRefs;
src/tools/video-editor/compositions/VisualClip.tsx:442:  materialRefs,
src/tools/video-editor/compositions/VisualClip.tsx:466:  const pendingMaterial = materialRefsForClip(clip, materialRefs)
src/tools/video-editor/compositions/VisualClip.tsx:580:  materialRefs,
src/tools/video-editor/compositions/VisualClip.tsx:609:          materialRefs={materialRefs}
src/tools/video-editor/runtime/agentToolContracts.test.ts:518:      sourceRefs: [
src/tools/video-editor/runtime/agentToolContracts.test.ts:686:  it('warns on non-array sourceRefs', () => {
src/tools/video-editor/runtime/agentToolContracts.test.ts:690:      sourceRefs: 'bad',
src/tools/video-editor/runtime/agentToolContracts.test.ts:1005:  it('incorporates sourceRefs into rationale', () => {
src/tools/video-editor/runtime/agentToolContracts.test.ts:1007:      sourceRefs: [
src/tools/video-editor/runtime/agentToolContracts.test.ts:1055:  it('includes both affectedObjectIds and sourceRefs in rationale', () => {
src/tools/video-editor/runtime/agentToolContracts.test.ts:1059:      sourceRefs: [{ sourceId: 's1', outputId: 'o1' }],
src/tools/video-editor/runtime/agentToolContracts.test.ts:1148:  it('carries sourceRefs across all proposals', () => {
src/tools/video-editor/runtime/agentToolContracts.test.ts:1151:      sourceRefs: [{ sourceId: 'a', outputId: 'b' }],
src/tools/video-editor/runtime/agentToolContracts.test.ts:1216:  it('handles result with empty sourceRefs array', () => {
src/tools/video-editor/runtime/agentToolContracts.test.ts:1218:      sourceRefs: [],
src/tools/video-editor/compositions/TimelineRenderer.tsx:60:// Mirrors `tools/remotion/src/HypeComposition.tsx:58-64` (lifted into
src/tools/video-editor/compositions/TimelineRenderer.tsx:61:// `packages/timeline-composition/typescript/src/TimelineComposition.tsx`).
src/tools/video-editor/compositions/TimelineRenderer.tsx:302:    targetParamName: record.binding.targetParamName,
src/tools/video-editor/compositions/TimelineRenderer.tsx:421:    binding.targetParamName,
src/tools/video-editor/compositions/TimelineRenderer.tsx:426:  const app = isRecord(clip.app) ? clip.app : undefined;
src/tools/video-editor/compositions/TimelineRenderer.tsx:1027:        // Mirrors HypeComposition.tsx:58-64 with DB augmentation.
src/tools/video-editor/runtime/extensionSurface.test.ts:1182:                sourceRefs: [],
src/tools/video-editor/hooks/useDerivedTimeline.ts:7:export interface CompositionMetadata {
src/tools/video-editor/hooks/useDerivedTimeline.ts:58:  const renderMetadata = useMemo<CompositionMetadata | null>(() => {
src/tools/video-editor/runtime/renderability.test.ts:269:      outputFormatId: 'dataset-show-control',
src/tools/video-editor/runtime/renderability.test.ts:313:      outputFormatId: 'metadata-json',
src/tools/video-editor/runtime/renderability.test.ts:433:      outputFormatId: 'metadata-json',
src/tools/video-editor/runtime/renderability.test.ts:452:      outputFormatId: 'metadata-json',
src/tools/video-editor/hooks/useTimelineCommands.ts:393:      clip.app && typeof clip.app.managedBy === 'string' ? [clip.app.managedBy] : [],
src/tools/video-editor/hooks/useTimelineCommands.ts:396:    const nextApp = detachManagedApp(clip.app as Record<string, unknown> | undefined, knownExtIds);
src/tools/video-editor/lib/compiler-canary.ts:26:  TimelineSnapshot,
src/tools/video-editor/lib/compiler-canary.ts:223:  snapshot: TimelineSnapshot,
src/tools/video-editor/lib/compiler-canary.ts:270:  snapshot: TimelineSnapshot,
src/tools/video-editor/lib/compiler-canary.ts:313:  snapshot: TimelineSnapshot,
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:30:  notes: Make CompositionGraph projection authoritative for shader/ref facts and contribution-index
src/tools/video-editor/hooks/useClientRender.ts:11:interface CompositionMetadata {
src/tools/video-editor/hooks/useClientRender.ts:20:  metadata: CompositionMetadata | null;
src/tools/video-editor/hooks/timeline-state-types.ts:3:import type { CompositionMetadata } from '@/tools/video-editor/hooks/useDerivedTimeline.ts';
src/tools/video-editor/hooks/timeline-state-types.ts:29:  renderMetadata: CompositionMetadata | null;
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:109:        path: 'clips.clip-1.app.shader',
src/tools/video-editor/lib/timeline-domain.shaders.test.ts:159:        path: 'app.shaderPostprocess',
src/tools/video-editor/hooks/useRenderState.test.tsx:31:  decideRenderRoute: (timeline: ResolvedTimelineConfig | null | undefined) => {
src/tools/video-editor/lib/timeline-domain.live-bindings.test.ts:26:  it('enumerates clip.app.live and params.liveBindings metadata without runtime registry state', () => {
src/tools/video-editor/lib/timeline-domain.live-bindings.test.ts:48:          liveBindings: [
src/tools/video-editor/lib/timeline-domain.live-bindings.test.ts:53:              targetParamName: 'title',
src/tools/video-editor/lib/timeline-domain.live-bindings.test.ts:249:          liveBindings: [
src/tools/video-editor/lib/timeline-domain.ts:142:export const TIMELINE_POSTPROCESS_SHADER_APP_KEY = 'shaderPostprocess';
src/tools/video-editor/lib/timeline-domain.ts:322:  const shader = clip.app?.shader;
src/tools/video-editor/lib/timeline-domain.ts:387:        ...(clip.app ?? {}),
src/tools/video-editor/lib/timeline-domain.ts:1184:  if (Array.isArray(value.liveBindings)) {
src/tools/video-editor/lib/timeline-domain.ts:1185:    return [{ value: value.liveBindings, pathSuffix: '.liveBindings' }];
src/tools/video-editor/lib/timeline-domain.ts:1200:  const appLive = clip.app?.live;
src/tools/video-editor/lib/timeline-domain.ts:1213:  const paramsLiveBindings = clip.params?.liveBindings;
src/tools/video-editor/lib/timeline-domain.ts:1215:    candidates.push({ value: paramsLiveBindings, path: `clips.${clip.id}.params.liveBindings` });
src/tools/video-editor/lib/timeline-domain.ts:1561:  if (clip.app?.liveUniformBindings !== undefined) {
src/tools/video-editor/lib/timeline-domain.ts:1562:    candidates.push({ value: clip.app.liveUniformBindings, path: `clips.${clip.id}.app.liveUniformBindings` });
src/tools/video-editor/lib/timeline-domain.ts:1565:  if (clip.app?.live !== undefined) {
src/tools/video-editor/lib/timeline-domain.ts:1566:    for (const candidate of getLiveUniformBindingArrayCandidates(clip.app.live)) {
src/tools/video-editor/lib/timeline-domain.ts:2067:    const clipApp = clip.app as Record<string, unknown> | undefined;
src/tools/video-editor/lib/timeline-domain.ts:2084:          path: `clips.${clip.id}.app.shader`,
src/tools/video-editor/lib/renderRouter.ts:41:  CapabilityRequirement,
src/tools/video-editor/lib/renderRouter.ts:80: *                          Currently unreachable from `decideRenderRoute`.
src/tools/video-editor/lib/renderRouter.ts:180:function sourceRefForClip(clipType: string | undefined): CapabilityRequirement['sourceRef'] {
src/tools/video-editor/lib/renderRouter.ts:188:  route: CapabilityRequirement['route'],
src/tools/video-editor/lib/renderRouter.ts:197:): CapabilityRequirement {
src/tools/video-editor/lib/renderRouter.ts:240:): CapabilityRequirement[] {
src/tools/video-editor/lib/renderRouter.ts:258:): CapabilityRequirement[] {
src/tools/video-editor/lib/renderRouter.ts:275:): CapabilityRequirement[] {
src/tools/video-editor/lib/renderRouter.ts:303:export function decideRenderRoute(
src/tools/video-editor/lib/renderRouter.ts:317:      planner: selectPlannerRoute(planRender({ requirements: [] })),
src/tools/video-editor/lib/renderRouter.ts:321:  const requirements: CapabilityRequirement[] = [];
src/tools/video-editor/lib/renderRouter.ts:424:  const planner = selectPlannerRoute(planRender({ requirements }));
src/tools/video-editor/lib/renderRouter.ts:444:      const conflictPlanner = selectPlannerRoute(planRender({
src/tools/video-editor/lib/compiler-canary.test.ts:27:  TimelineSnapshot,
src/tools/video-editor/lib/compiler-canary.test.ts:86:/** Create a mock TimelineSnapshot. */
src/tools/video-editor/lib/compiler-canary.test.ts:87:function makeSnapshot(overrides?: Partial<TimelineSnapshot>): TimelineSnapshot {
src/tools/video-editor/lib/compiler-canary.test.ts:115:    _snapshotOverrides: Partial<TimelineSnapshot> | null;
src/tools/video-editor/lib/compiler-canary.test.ts:127:function createMockServices(snapshotOverrides?: Partial<TimelineSnapshot>): MockServices {
src/tools/video-editor/lib/compiler-canary.test.ts:186:    _snapshotOverrides: null as Partial<TimelineSnapshot> | null,
src/tools/video-editor/lib/compiler-canary.test.ts:187:    snapshot: vi.fn((): TimelineSnapshot => {
src/tools/video-editor/lib/timeline-reader.test.ts:2: * Tests for TimelineReader and stable TimelineSnapshot projection.
src/tools/video-editor/lib/timeline-reader.test.ts:11:  TimelineSnapshot,
src/tools/video-editor/lib/timeline-data.test.ts:10:import { decideRenderRoute } from '@/tools/video-editor/lib/renderRouter';
src/tools/video-editor/lib/timeline-data.test.ts:190:  it('preserves clip.app.live metadata through rowsToConfig without sample payloads', async () => {
src/tools/video-editor/lib/timeline-data.test.ts:254:    expect(decideRenderRoute(serialized)).toMatchObject({
src/tools/video-editor/lib/timeline-reader.ts:4: * Exposes TimelineSnapshot summaries while hiding raw row/meta/registry
src/tools/video-editor/lib/timeline-reader.ts:13:  TimelineSnapshot,
src/tools/video-editor/lib/timeline-reader.ts:29:import { getCapabilityRequirements as sdkGetCapabilityRequirements } from '@/sdk/index';
src/tools/video-editor/lib/timeline-reader.ts:121:  if (clip.app && typeof clip.app.managedBy === 'string' && clip.app.managedBy.length > 0) {
src/tools/video-editor/lib/timeline-reader.ts:122:    return { managed: true, managedBy: clip.app.managedBy };
src/tools/video-editor/lib/timeline-reader.ts:127:  if (clip.app) {
src/tools/video-editor/lib/timeline-reader.ts:128:    for (const key of Object.keys(clip.app)) {
src/tools/video-editor/lib/timeline-reader.ts:191:    const appLiveBindings = clip.app?.liveBindings;
src/tools/video-editor/lib/timeline-reader.ts:214:          ...(typeof binding.targetParamName === 'string'
src/tools/video-editor/lib/timeline-reader.ts:215:            ? { targetParamName: binding.targetParamName }
src/tools/video-editor/lib/timeline-reader.ts:234:        path: `clips.${clip.id}.app.liveBindings`,
src/tools/video-editor/lib/timeline-reader.ts:300: * stable TimelineSnapshot projections suitable for extension and
src/tools/video-editor/lib/timeline-reader.ts:319:    snapshot(): TimelineSnapshot {
src/tools/video-editor/lib/timeline-reader.ts:331:      const liveBindingsByClip = new Map<string, TimelineLiveBindingRecord[]>();
src/tools/video-editor/lib/timeline-reader.ts:334:        const records = liveBindingsByClip.get(record.clipId) ?? [];
src/tools/video-editor/lib/timeline-reader.ts:336:        liveBindingsByClip.set(record.clipId, records);
src/tools/video-editor/lib/timeline-reader.ts:346:          extractGeneratedMeta(clip.app);
src/tools/video-editor/lib/timeline-reader.ts:348:        const clipShader = isClipShaderMetadata(clip.app?.shader)
src/tools/video-editor/lib/timeline-reader.ts:349:          ? clip.app.shader
src/tools/video-editor/lib/timeline-reader.ts:453:        for (const record of liveBindingsByClip.get(clip.id) ?? []) {
src/tools/video-editor/lib/timeline-reader.ts:459:            ...(record.binding.targetParamName !== undefined
src/tools/video-editor/lib/timeline-reader.ts:460:              ? { targetParamName: record.binding.targetParamName }
src/tools/video-editor/lib/timeline-reader.ts:539:            ? { liveBindings: clipLiveBindings }
src/tools/video-editor/lib/timeline-reader.ts:542:            ? { materialRefs: clipMaterialRefs }
src/tools/video-editor/lib/timeline-reader.ts:545:            ? { sourceRefs: clipSourceRefs }
src/tools/video-editor/lib/timeline-reader.ts:573:      const postprocessShader = isPostprocessShaderMetadata(app.shaderPostprocess)
src/tools/video-editor/lib/timeline-reader.ts:574:        ? app.shaderPostprocess
src/tools/video-editor/lib/timeline-reader.ts:660:        liveBindings:
src/tools/video-editor/lib/timeline-reader.ts:662:        materialRefs:
src/tools/video-editor/lib/timeline-reader.ts:664:        sourceRefs:
src/tools/video-editor/lib/timeline-reader.ts:677:// Re-export getCapabilityRequirements from timeline-reader for planner
src/tools/video-editor/lib/timeline-reader.ts:681:export { sdkGetCapabilityRequirements as getCapabilityRequirements };
src/tools/video-editor/runtime/exportGuard.ts:330:  if (isTimelineShaderMetadata(config.app?.shaderPostprocess, 'postprocess')) return true;
src/tools/video-editor/runtime/exportGuard.ts:331:  return config.clips.some((clip) => isTimelineShaderMetadata(clip.app?.shader, 'clip'));
src/tools/video-editor/runtime/exportGuard.ts:364:    const shader = isTimelineShaderMetadata(clip.app?.shader, 'clip') ? clip.app.shader : undefined;
src/tools/video-editor/runtime/exportGuard.ts:375:  const postprocessShader = isTimelineShaderMetadata(config.app?.shaderPostprocess, 'postprocess')
src/tools/video-editor/runtime/exportGuard.ts:376:    ? config.app.shaderPostprocess
src/tools/video-editor/runtime/liveDataRegistry.ts:177:  targetParamName?: string;
src/tools/video-editor/runtime/liveDataRegistry.ts:932:        targetParamName: binding.targetParamName,
src/tools/video-editor/runtime/liveDataRegistry.ts:1028:            targetParamName: b.targetParamName,
src/tools/video-editor/lib/timeline-data.ts:155:    app: clip.app,
src/tools/video-editor/lib/managed-object-guard.ts:156: * Keys that should be removed from clip.app when detaching a managed clip.
src/tools/video-editor/lib/timeline-patch.test.ts:1921:    expect(result.nextData!.config.clips.find((clip: any) => clip.id === 'c1')!.app.shader).toEqual(clipShader);
src/tools/video-editor/lib/timeline-patch.test.ts:1945:    expect(result.nextData!.config.clips.find((clip: any) => clip.id === 'c1')!.app.shader).toEqual(clipShader);
src/tools/video-editor/runtime/renderPlanner.ts:2:  getCapabilityRequirements,
src/tools/video-editor/runtime/renderPlanner.ts:4:  type CapabilityRequirement,
src/tools/video-editor/runtime/renderPlanner.ts:12:  type TimelineSnapshot,
src/tools/video-editor/runtime/renderPlanner.ts:29:  readonly outputFormatId?: string;
src/tools/video-editor/runtime/renderPlanner.ts:43:  readonly snapshot?: TimelineSnapshot | null;
src/tools/video-editor/runtime/renderPlanner.ts:44:  readonly requirements?: readonly CapabilityRequirement[];
src/tools/video-editor/runtime/renderPlanner.ts:50:  readonly materialRefs?: readonly RenderMaterialRef[];
src/tools/video-editor/runtime/renderPlanner.ts:68:  readonly outputFormatIds: readonly string[];
src/tools/video-editor/runtime/renderPlanner.ts:201:function routeFitFinding(requirement: CapabilityRequirement): CapabilityFinding | undefined {
src/tools/video-editor/runtime/renderPlanner.ts:239:function collectRequirement(acc: PlanAccumulator, requirement: CapabilityRequirement): void {
src/tools/video-editor/runtime/renderPlanner.ts:277:function isShaderMaterializerRequirement(requirement: CapabilityRequirement): boolean {
src/tools/video-editor/runtime/renderPlanner.ts:298:  requirement: CapabilityRequirement,
src/tools/video-editor/runtime/renderPlanner.ts:314:  requirement: CapabilityRequirement,
src/tools/video-editor/runtime/renderPlanner.ts:327:  requirement: CapabilityRequirement,
src/tools/video-editor/runtime/renderPlanner.ts:342:  requirement: CapabilityRequirement,
src/tools/video-editor/runtime/renderPlanner.ts:367:  requirement: CapabilityRequirement,
src/tools/video-editor/runtime/renderPlanner.ts:395:function shaderCompositionKey(shader: TimelineShaderSummary): string | undefined {
src/tools/video-editor/runtime/renderPlanner.ts:401:function shaderCompositionScopeMessage(
src/tools/video-editor/runtime/renderPlanner.ts:415:function shaderCompositionScopeLabel(shader: TimelineShaderSummary): string {
src/tools/video-editor/runtime/renderPlanner.ts:419:function diagnoseSnapshotShaderComposition(
src/tools/video-editor/runtime/renderPlanner.ts:420:  snapshot: TimelineSnapshot | null | undefined,
src/tools/video-editor/runtime/renderPlanner.ts:421:): { snapshot: TimelineSnapshot | null | undefined; findings: CapabilityFinding[] } {
src/tools/video-editor/runtime/renderPlanner.ts:431:    const scopeKey = shaderCompositionKey(shader);
src/tools/video-editor/runtime/renderPlanner.ts:444:    const message = shaderCompositionScopeMessage(existing, shader);
src/tools/video-editor/runtime/renderPlanner.ts:447:        id: `planner.shaderComposition.${shaderCompositionScopeLabel(shader)}.${shader.shaderId}.${route}.scope-occupied`,
src/tools/video-editor/runtime/renderPlanner.ts:552:      outputFormatId: outputFormat.id,
src/tools/video-editor/runtime/renderPlanner.ts:582:      outputFormatId: outputFormat.id,
src/tools/video-editor/runtime/renderPlanner.ts:716:        outputFormatId: outputFormat.id,
src/tools/video-editor/runtime/renderPlanner.ts:809:function collectRenderGroups(acc: PlanAccumulator, snapshot: TimelineSnapshot | null | undefined): void {
src/tools/video-editor/runtime/renderPlanner.ts:876:  const outputFormatIds = Object.freeze([...(acc.routeOutputFormatIds.get(route) ?? new Set())].sort());
src/tools/video-editor/runtime/renderPlanner.ts:896:    outputFormatIds,
src/tools/video-editor/runtime/renderPlanner.ts:918:export function planRender(input: RenderPlannerInput): RenderPlannerResult {
src/tools/video-editor/runtime/renderPlanner.ts:920:  const shaderComposition = diagnoseSnapshotShaderComposition(input.snapshot);
src/tools/video-editor/runtime/renderPlanner.ts:921:  const requirements = input.requirements ?? (shaderComposition.snapshot
src/tools/video-editor/runtime/renderPlanner.ts:922:    ? getCapabilityRequirements(shaderComposition.snapshot)
src/tools/video-editor/runtime/renderPlanner.ts:931:  const requestedOutputFormat = input.request?.outputFormatId
src/tools/video-editor/runtime/renderPlanner.ts:932:    ? outputFormats.find((format) => format.id === input.request?.outputFormatId)
src/tools/video-editor/runtime/renderPlanner.ts:953:    if (input.request?.outputFormatId && input.request.outputFormatId !== outputFormat.id) continue;
src/tools/video-editor/runtime/renderPlanner.ts:960:  for (const materialRef of input.materialRefs ?? []) {
src/tools/video-editor/runtime/renderPlanner.ts:964:  acc.findings.push(...shaderComposition.findings);
src/tools/video-editor/runtime/renderPlanner.ts:967:  if (input.request?.outputFormatId && !outputFormats.some((format) => format.id === input.request?.outputFormatId)) {
src/tools/video-editor/runtime/renderPlanner.ts:969:      id: `planner.outputFormat.${input.request.outputFormatId}.missing`,
src/tools/video-editor/runtime/renderPlanner.ts:973:      message: `Output format "${input.request.outputFormatId}" is not registered.`,
src/tools/video-editor/runtime/renderPlanner.ts:974:      contributionId: input.request.outputFormatId,
src/tools/video-editor/runtime/renderPlanner.ts:977:        outputFormatId: input.request.outputFormatId,
src/tools/video-editor/lib/source-map-runtime.ts:10: * visible in TimelineSnapshot.app.
docs/video-editor/shader-execution-model.md:34:- Clip-local shaders assigned to one clip through `clip.app.shader`.
docs/video-editor/shader-execution-model.md:35:- Timeline postprocess shaders assigned through `config.app.shaderPostprocess`.
docs/video-editor/shader-execution-model.md:118:## V1 Composition Limits
docs/video-editor/shader-execution-model.md:155:## Non-Render-Graph V1 Posture
src/tools/video-editor/runtime/renderability.ts:300:  readonly outputFormatId?: string;
src/tools/video-editor/runtime/renderability.ts:328:  readonly outputFormatId?: string;
src/tools/video-editor/runtime/renderability.ts:387:    outputFormatId: params.outputFormatId,
src/tools/video-editor/runtime/renderability.ts:460:  readonly outputFormatId?: string;
src/tools/video-editor/runtime/renderability.ts:549:    outputFormatId: params.outputFormatId,
docs/video-editor/extension-platform-supported-deferred.md:232:| D-022 | Planner/export inspection using public `TimelineSnapshot`/`TimelineReader` | **deferred** | CR:M12-007; BLOCKER:B-002 |
docs/extensions/reigh-extension-layer-roadmap-v2.md:196:- `RenderMaterialContribution`/capability metadata consumed by `planRender()`.
src/tools/video-editor/lib/renderRouter.test.ts:8:  decideRenderRoute,
src/tools/video-editor/lib/renderRouter.test.ts:13:describe('Sprint 8 render-button router (decideRenderRoute)', () => {
src/tools/video-editor/lib/renderRouter.test.ts:15:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:29:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:42:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:52:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:65:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:78:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:87:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:95:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:110:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:125:    const decision = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:144:    const missingArtifact = decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:155:    expect(decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:162:    expect(decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:172:      expect(decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:185:    expect(decideRenderRoute({ clips: [] }).reason).toBe('no_clips');
src/tools/video-editor/lib/renderRouter.test.ts:186:    expect(decideRenderRoute(null).reason).toBe('no_clips');
src/tools/video-editor/lib/renderRouter.test.ts:187:    expect(decideRenderRoute(undefined).reason).toBe('no_clips');
src/tools/video-editor/lib/renderRouter.test.ts:229:describe('M9 T11 contributed clip routing (decideRenderRoute)', () => {
src/tools/video-editor/lib/renderRouter.test.ts:231:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:242:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:258:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:268:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:278:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:288:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:304:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:328:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:343:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:354:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:364:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:374:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:385:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:400:    const decision = decideRenderRoute({ clips: [] }, [browserCapableRecord]);
src/tools/video-editor/lib/renderRouter.test.ts:407:    const decision = decideRenderRoute(
src/tools/video-editor/lib/renderRouter.test.ts:646:    const decision = decideRenderRoute(config);
src/tools/video-editor/lib/renderRouter.test.ts:685:    const decision = decideRenderRoute(config);
src/tools/video-editor/lib/renderRouter.test.ts:741:      decision: decideRenderRoute(request.resolvedConfig),
src/tools/video-editor/lib/renderRouter.test.ts:774:      decision: decideRenderRoute({ clips: [{ clipType: 'media' }] }),
src/tools/video-editor/lib/renderRouter.test.ts:802:      decision: decideRenderRoute({
src/tools/video-editor/lib/renderRouter.test.ts:869:      decision: decideRenderRoute({ clips: [{ clipType: 'image-jump' }] }),
src/tools/video-editor/lib/renderRouter.test.ts:900:      decision: decideRenderRoute({ clips: [{ clipType: 'image-jump' }] }),
docs/video-editor/extension-platform-contract-recheck.md:222:| M12-007 | Planner/export inspection using public `TimelineSnapshot`/`TimelineReader` contract, contribution requirements, missing-extension blockers, no raw provider reads | gap | supported | `TimelineReader` and `TimelineSnapshot` contracts defined; planner consuming them not confirmed | `src/tools/video-editor/runtime/` |
docs/extensions/phase4-readiness.md:29:  Remotion module, and contributed clip content into `CapabilityRequirement`
docs/extensions/phase4-readiness.md:30:  entries, calls `planRender()`, and returns a planner-backed route decision.
docs/extensions/phase4-readiness.md:50:   `CapabilityRequirement` records or a descriptor that `planRender()` can
docs/extensions/phase4-readiness.md:110:| Render planning | Preview/export capability, determinism, material/process requirements, and blockers are visible to `planRender()` before execution. |
docs/extensions/phase4-readiness.md:122:| Clip type | Sequence-backed subset first, insertion/inspection/rendering, serialization/reload, duplicate/missing/blocked capability failures, and planner participation through `renderRouter.ts`/`planRender()`. |
docs/extensions/phase4-readiness.md:143:| EXT-033 ClipTypeContribution | Planned as a sequence-backed subset. | Keep subset scope; require `renderRouter.ts` contributed clip records and `planRender()` blockers before support. |
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:4: * These tests prove that planner code can consume TimelineSnapshot,
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:12:import { createTimelineReader, getCapabilityRequirements } from '@/tools/video-editor/lib/timeline-reader';
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:14:  TimelineSnapshot,
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:23:  CapabilityRequirement,
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:69:  it('can import TimelineSnapshot without provider stores', () => {
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:71:    // the planner can access TimelineSnapshot without raw rows.
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:72:    const snap: TimelineSnapshot = {
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:85:  it('can import CapabilityRequirement without provider stores', () => {
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:86:    const req: CapabilityRequirement = {
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:102:      sourceRefs: [],
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:250:            liveBindings: [
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:255:                targetParamName: 'texture',
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:269:    expect(clip!.liveBindings).toBeDefined();
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:270:    expect(clip!.liveBindings!.length).toBe(1);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:271:    expect(clip!.liveBindings![0].bindingId).toBe('lb-1');
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:272:    expect(clip!.liveBindings![0].sourceKind).toBe('webcam');
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:273:    expect(clip!.liveBindings![0].status).toBe('active');
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:276:    expect(snap.liveBindings).toBeDefined();
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:277:    expect(snap.liveBindings!.length).toBe(1);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:304:            liveBindings: [
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:309:                targetParamName: 'opacity',
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:323:    expect(clip!.liveBindings?.map((binding) => binding.bindingId)).toEqual([
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:327:    expect(snap.liveBindings?.map((binding) => binding.bindingId)).toEqual([
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:354:    expect(clip!.materialRefs).toBeDefined();
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:355:    expect(clip!.materialRefs!.length).toBe(1);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:356:    expect(clip!.materialRefs![0].assetKey).toBe('some-asset-key');
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:359:    expect(snap.materialRefs).toBeDefined();
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:360:    expect(snap.materialRefs!.length).toBe(1);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:394:    expect(clip!.sourceRefs).toHaveLength(2);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:395:    expect(clip!.sourceRefs![0]).toEqual(expect.objectContaining({
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:400:    expect(clip!.sourceRefs![1]).toEqual(expect.objectContaining({
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:406:    expect(snap.sourceRefs).toHaveLength(2);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:457:    expect(clip.liveBindings).toBeUndefined();
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:458:    expect(clip.materialRefs).toBeUndefined();
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:459:    expect(clip.sourceRefs).toBeUndefined();
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:464:    expect(snap.liveBindings).toBeUndefined();
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:465:    // materialRefs might be present if any clip has an asset, but this one doesn't
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:466:    expect(snap.materialRefs).toBeUndefined();
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:467:    expect(snap.sourceRefs).toBeUndefined();
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:472:// M12: getCapabilityRequirements — provider-free inspection
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:475:describe('M12 getCapabilityRequirements', () => {
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:486:    const reqs = getCapabilityRequirements(snap);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:504:    const reqs = getCapabilityRequirements(snap);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:536:    const reqs = getCapabilityRequirements(snap);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:567:    const reqs = getCapabilityRequirements(snap);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:588:            liveBindings: [
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:604:    const reqs = getCapabilityRequirements(snap);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:628:            liveBindings: [
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:644:    const reqs = getCapabilityRequirements(snap);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:673:    const reqs = getCapabilityRequirements(snap);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:701:    const reqs = getCapabilityRequirements(snap);
src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:741:    const reqs = getCapabilityRequirements(snap);
docs/extensions/reigh-extension-layer-tickets.md:432:- `planRender()` inspects contributed clip/effect/transition/render material metadata.

exec
/bin/zsh -lc "nl -ba src/tools/video-editor/runtime/exportGuard.ts | sed -n '300,430p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
exec
/bin/zsh -lc "nl -ba src/tools/video-editor/hooks/useRenderState.ts | sed -n '360,560p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
   360	      isExtensionRuntimeEmpty(extensionRuntime)
   361	      && effectRegistrySnapshot.records.length === 0
   362	      && transitionRegistrySnapshot.records.length === 0
   363	      && clipTypeRegistrySnapshot.records.length === 0
   364	      && !hasTimelineShaderMetadata(resolvedConfig)
   365	    ) {
   366	      return true; // no blocker
   367	    }
   368	
   369	    if (!resolvedConfig || resolvedConfig.clips.length === 0) {
   370	      return true; // nothing to scan
   371	    }
   372	
   373	    const builtIn = collectBuiltInKnownIds();
   374	    const allContributions = extensionRuntime ? buildExtensionContributions(extensionRuntime) : [];
   375	    const extIds = collectExtensionDeclaredIds(allContributions);
   376	    const guardResult = scanExportConfig(resolvedConfig, builtIn, extIds, effectRegistrySnapshot, transitionRegistrySnapshot, clipTypeRegistrySnapshot);
   377	    const plannerResult = planFromExportGuardResult(guardResult);
   378	
   379	    guardResult.diagnostics.forEach((diagnostic, index) => {
   380	      diagnosticCollection?.publish(toCollectionDiagnostic(diagnostic, index));
   381	    });
   382	    syncPlannerDiagnosticsToCollection(diagnosticCollection, plannerResult.blockers);
   383	
   384	    // Emit structured diagnostics as concise render log output
   385	    const log = formatExportGuardLog(guardResult);
   386	    setRenderLog(log);
   387	
   388	    if (plannerResult.blockers.length > 0) {
   389	      // Planner-owned blockers are the canonical readiness decision.
   390	      setRenderStatus('error');
   391	      setRenderProgress(null);
   392	      setRenderDirty(false);
   393	      return false; // blocker
   394	    }
   395	
   396	    // Extension-declared warnings only — preserve native routing
   397	    return true; // no blocker
   398	  }, [diagnosticCollection, effectRegistrySnapshot, transitionRegistrySnapshot, clipTypeRegistrySnapshot, extensionRuntime, resolvedConfig]);
   399	
   400	  const startRender = useCallback(async () => {
   401	    // ---- export guard: scan for unknown IDs before routing ------------------
   402	    if (!runExportGuard()) {
   403	      return; // blocked by export guard
   404	    }
   405	
   406	    let decision = getFastRenderRouteDecision(resolvedConfig);
   407	    if (!decision) {
   408	      let importedDecision: {
   409	      route: 'browser-remotion' | 'worker-banodoco' | 'preview-only' | 'external';
   410	      reason: string;
   411	      };
   412	      try {
   413	        const renderRouter = await import('@/tools/video-editor/lib/renderRouter');
   414	        importedDecision = renderRouter.decideRenderRoute(resolvedConfig);
   415	      } catch (error) {
   416	        setRenderStatus('error');
   417	        setRenderProgress(null);
   418	        setRenderDirty(false);
   419	        setRenderLog(error instanceof Error
   420	          ? `Render routing unavailable: ${error.message}`
   421	          : 'Render routing unavailable.');
   422	        return;
   423	      }
   424	      decision = importedDecision;
   425	    }
   426	    if (decision.route === 'preview-only') {
   427	      setRenderStatus('error');
   428	      setRenderProgress(null);
   429	      setRenderDirty(false);
   430	      setRenderLog(`Render blocked: ${decision.reason}. Generated Remotion module clips require valid worker artifact metadata.`);
   431	      return;
   432	    }
   433	
   434	    if (decision.route === 'worker-banodoco' || decision.route === 'external') {
   435	      setRenderStatus('error');
   436	      setRenderProgress(null);
   437	      setRenderDirty(false);
   438	      setRenderLog(`Worker render unavailable for route "${decision.reason}". This timeline was not sent to the browser renderer.`);
   439	      return;
   440	    }
   441	
   442	    if (exporter && resolvedConfig) {
   443	      setRenderStatus('rendering');
   444	      setRenderProgress({
   445	        current: 0,
   446	        total: renderMetadata?.durationInFrames ?? 1,
   447	        percent: 0,
   448	        phase: 'validating',
   449	      });
   450	      setRenderResultUrl((current) => {
   451	        if (current) {
   452	          URL.revokeObjectURL(current);
   453	        }
   454	        return null;
   455	      });
   456	      setRenderResultFilename(null);
   457	      setRenderLog('');
   458	
   459	      const job = await exporter.render({
   460	        timeline: resolvedConfig,
   461	        registry: resolvedConfig.registry,
   462	        output: {
   463	          file: resolvedConfig.output.file,
   464	          fps: resolvedConfig.output.fps,
   465	        },
   466	      });
   467	
   468	      job.subscribe((progress) => {
   469	        setRenderLog(progress.log ?? '');
   470	        setRenderProgress(progress.progress == null
   471	          ? null
   472	          : {
   473	            current: Math.round((renderMetadata?.durationInFrames ?? 1) * progress.progress),
   474	            total: renderMetadata?.durationInFrames ?? 1,
   475	            percent: Math.round(progress.progress * 100),
   476	            phase: progress.phase,
   477	          });
   478	
   479	        if (progress.phase === 'complete') {
   480	          setRenderStatus('done');
   481	          setRenderDirty(false);
   482	          if (progress.resultUrl) {
   483	            setRenderResultUrl(progress.resultUrl);
   484	            setRenderResultFilename(resolvedConfig.output.file);
   485	          }
   486	          return;
   487	        }
   488	
   489	        if (progress.phase === 'failed') {
   490	          setRenderStatus('error');
   491	          setRenderDirty(false);
   492	          return;
   493	        }
   494	
   495	        setRenderStatus('rendering');
   496	      });
   497	      return;
   498	    }
   499	
   500	    await startClientRender();
   501	  }, [exporter, renderMetadata?.durationInFrames, resolvedConfig, startClientRender, runExportGuard]);
   502	
   503	  // ---- M6: compile-only export ------------------------------------------------
   504	  const startExport = useCallback(async (
   505	    formatId: string,
   506	    compileOnlyRegistry?: CompileOnlyOutputFormatRegistry,
   507	  ) => {
   508	    if (!resolvedConfig) {
   509	      setExportStatus('error');
   510	      setExportLogState('Export unavailable: no timeline configuration.');
   511	      return;
   512	    }
   513	
   514	    const plannerOutputFormats = outputFormatsForPlanning(extensionRuntime);
   515	    const outputPlan = planRender({
   516	      outputFormats: plannerOutputFormats,
   517	      processes: extensionRuntime?.processes ?? [],
   518	      request: {
   519	        outputFormatId: formatId,
   520	        routes: ['browser-export'],
   521	      },
   522	      diagnostics: plannerOutputFormats.find((candidate) => candidate.id === formatId)?.disabled
   523	        ? [{
   524	            id: `planner.outputFormat.${formatId}.disabled`,
   525	            severity: 'error',
   526	            route: 'browser-export',
   527	            reason: 'inactive-extension',
   528	            message: plannerOutputFormats.find((candidate) => candidate.id === formatId)?.disabledReason
   529	              ?? `Export format "${formatId}" is disabled.`,
   530	            contributionId: formatId,
   531	            detail: { source: 'output-format', outputFormatId: formatId },
   532	          }]
   533	        : [],
   534	    });
   535	    const browserOutputPlan = outputPlan.routePlans.find((routePlan) => routePlan.route === 'browser-export');
   536	    const fmt = plannerOutputFormats.find((f) => f.id === formatId && !f.requiresRender && !f.disabled);
   537	    if (!fmt || browserOutputPlan?.blocked) {
   538	      const requestedFormat = plannerOutputFormats.find((f) => f.id === formatId);
   539	      const blocker = outputPlan.blockers.find((candidate) => candidate.id === `planner.outputFormat.${formatId}.disabled`)
   540	        ?? browserOutputPlan?.blockers[0]
   541	        ?? outputPlan.blockers[0];
   542	      setExportStatus('error');
   543	      if (blocker) {
   544	        setExportLogState(`Export blocked: ${blocker.message}`);
   545	      } else if (requestedFormat) {
   546	        setExportLogState(`Export blocked: "${requestedFormat.label}" is not available for browser export.`);
   547	      } else {
   548	        setExportLogState(`Export format "${formatId}" not found.`);
   549	      }
   550	      return;
   551	    }
   552	
   553	    // ---- M7: Run export guard before compile-only export --------------------
   554	    // Compile-only exports don't need rendered pixels, but they still process
   555	    // timeline data.  Unknown / missing-contribution effects should block
   556	    // because the exported data would be invalid.  Route-specific capability
   557	    // blockers (browser-export blocked, worker-export blocked) are surfaced
   558	    // as warnings but do not prevent compile-only export.
   559	    const guardPassed = runExportGuard();
   560	    if (!guardPassed) {

 succeeded in 0ms:
   300	  return Object.freeze({
   301	    diagnostics: Object.freeze(diagnostics),
   302	    findings: Object.freeze(findings),
   303	    blockers: Object.freeze(blockers),
   304	    unknownClipTypes: Object.freeze([...unknownClipTypes].sort()),
   305	    unknownEffects: Object.freeze([...unknownEffects].sort()),
   306	    unknownTransitions: Object.freeze([...unknownTransitions].sort()),
   307	    inactiveExtensionIds: extIds,
   308	    hasBlockingErrors,
   309	  });
   310	}
   311	
   312	function scanLiveBindingExportBlockers(
   313	  config: ResolvedTimelineConfig,
   314	  diagnostics: ExportDiagnostic[],
   315	  findings: CapabilityFinding[],
   316	  blockers: RenderBlocker[],
   317	): void {
   318	  const liveScan = scanTimelineLiveBindings(config as TimelineConfig);
   319	
   320	  for (const record of liveScan.bindings) {
   321	    if (!record.blocksExport) {
   322	      continue;
   323	    }
   324	    pushLiveBindingFindingAndBlocker(diagnostics, findings, blockers, record);
   325	  }
   326	}
   327	
   328	function hasTimelineShaderMetadata(config: ResolvedTimelineConfig | null | undefined): boolean {
   329	  if (!config) return false;
   330	  if (isTimelineShaderMetadata(config.app?.shaderPostprocess, 'postprocess')) return true;
   331	  return config.clips.some((clip) => isTimelineShaderMetadata(clip.app?.shader, 'clip'));
   332	}
   333	
   334	export { hasTimelineShaderMetadata };
   335	
   336	function isTimelineShaderMetadata(
   337	  value: unknown,
   338	  scope: ShaderMaterializerRequirementScope,
   339	): value is {
   340	  readonly scope: ShaderMaterializerRequirementScope;
   341	  readonly shaderId: string;
   342	  readonly extensionId: string;
   343	  readonly contributionId: string;
   344	  readonly enabled?: boolean;
   345	} {
   346	  return Boolean(
   347	    value
   348	    && typeof value === 'object'
   349	    && !Array.isArray(value)
   350	    && (value as Record<string, unknown>).scope === scope
   351	    && typeof (value as Record<string, unknown>).shaderId === 'string'
   352	    && typeof (value as Record<string, unknown>).extensionId === 'string'
   353	    && typeof (value as Record<string, unknown>).contributionId === 'string',
   354	  );
   355	}
   356	
   357	function scanTimelineShaderExportBlockers(
   358	  config: ResolvedTimelineConfig,
   359	  diagnostics: ExportDiagnostic[],
   360	  findings: CapabilityFinding[],
   361	  blockers: RenderBlocker[],
   362	): void {
   363	  for (const clip of config.clips) {
   364	    const shader = isTimelineShaderMetadata(clip.app?.shader, 'clip') ? clip.app.shader : undefined;
   365	    if (!shader || shader.enabled === false) continue;
   366	    pushShaderMaterializerFindingAndBlocker(diagnostics, findings, blockers, {
   367	      shaderId: shader.shaderId,
   368	      extensionId: shader.extensionId,
   369	      contributionId: shader.contributionId,
   370	      scope: 'clip',
   371	      clipId: clip.id,
   372	    });
   373	  }
   374	
   375	  const postprocessShader = isTimelineShaderMetadata(config.app?.shaderPostprocess, 'postprocess')
   376	    ? config.app.shaderPostprocess
   377	    : undefined;
   378	  if (postprocessShader && postprocessShader.enabled !== false) {
   379	    pushShaderMaterializerFindingAndBlocker(diagnostics, findings, blockers, {
   380	      shaderId: postprocessShader.shaderId,
   381	      extensionId: postprocessShader.extensionId,
   382	      contributionId: postprocessShader.contributionId,
   383	      scope: 'postprocess',
   384	    });
   385	  }
   386	}
   387	
   388	function pushShaderMaterializerFindingAndBlocker(
   389	  diagnostics: ExportDiagnostic[],
   390	  findings: CapabilityFinding[],
   391	  blockers: RenderBlocker[],
   392	  input: {
   393	    readonly shaderId: string;
   394	    readonly extensionId: string;
   395	    readonly contributionId: string;
   396	    readonly scope: ShaderMaterializerRequirementScope;
   397	    readonly clipId?: string;
   398	  },
   399	): void {
   400	  const routes: readonly RenderRoute[] = ['browser-export', 'worker-export'];
   401	
   402	  for (const route of routes) {
   403	    const message = shaderMissingMaterializerBlockerMessage(input.shaderId, input.scope, input.clipId);
   404	    const id = `export.shader.${input.scope}.${input.clipId ?? 'timeline'}.${input.shaderId}.${route}.missing-materializer`;
   405	    const detail = {
   406	      shaderId: input.shaderId,
   407	      shaderScope: input.scope,
   408	      renderRoute: route,
   409	      ...(input.clipId ? { clipId: input.clipId } : {}),
   410	    };
   411	
   412	    diagnostics.push({
   413	      severity: 'error',
   414	      code: 'export/unrenderable-shader',
   415	      message,
   416	      extensionId: input.extensionId,
   417	      contributionId: input.contributionId,
   418	      detail,
   419	    });
   420	
   421	    const finding: CapabilityFinding = {
   422	      id,
   423	      severity: 'error',
   424	      route,
   425	      reason: 'missing-material',
   426	      message,
   427	      ...(input.clipId ? { clipId: input.clipId } : {}),
   428	      extensionId: input.extensionId,
   429	      contributionId: input.contributionId,
   430	      detail: {

exec
/bin/zsh -lc "nl -ba src/sdk/index.ts | sed -n '4848,5225p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
  4848	// M3: TimelineSnapshot / TimelineReader
  4849	// ---------------------------------------------------------------------------
  4850	
  4851	/**
  4852	 * Stable, read-only projection of timeline state for extensions and proposal
  4853	 * machinery. Never exposes raw internal rows, provider handles, or mutation
  4854	 * engine internals.
  4855	 */
  4856	export interface TimelineSnapshot {
  4857	  /** Project identifier, when available. */
  4858	  projectId: string | null;
  4859	  /**
  4860	   * Base version for concurrency control. This is the version the snapshot
  4861	   * was taken at; proposals based on this snapshot must revalidate against
  4862	   * the current reader version before acceptance.
  4863	   */
  4864	  baseVersion: number;
  4865	  /**
  4866	   * Current version at the time the snapshot was taken. Equal to baseVersion
  4867	   * when there are no uncommitted local edits.
  4868	   */
  4869	  currentVersion: number;
  4870	  /** Extensions referenced by this project with version-range constraints. */
  4871	  extensionRequirements: readonly ProjectExtensionRequirement[];
  4872	  /** Ordered list of clip summaries (ID, track, at, clipType, duration). */
  4873	  clips: readonly TimelineClipSummary[];
  4874	  /** Ordered list of track summaries (ID, kind, label, muted). */
  4875	  tracks: readonly TimelineTrackSummary[];
  4876	  /** Asset keys present in the timeline. */
  4877	  assetKeys: readonly string[];
  4878	  /** Extension-owned app data (project-data) keyed by extension ID. */
  4879	  app: Record<string, unknown>;
  4880	  /**
  4881	   * Source-map entries extracted from extension project-data.
  4882	   * Each entry maps a timeline object to a source location.
  4883	   */
  4884	  sourceMapEntries?: readonly SourceMapEntry[];
  4885	  /** M12: Ordered list of effect summaries extracted from clips. */
  4886	  effects?: readonly TimelineEffectSummary[];
  4887	  /** M12: Ordered list of transition summaries extracted from clips. */
  4888	  transitions?: readonly TimelineTransitionSummary[];
  4889	  /** M12: Live-binding summaries extracted from clip metadata. */
  4890	  liveBindings?: readonly TimelineLiveBindingSummary[];
  4891	  /** M12: Material-ref summaries extracted from clip data. */
  4892	  materialRefs?: readonly TimelineMaterialRefSummary[];
  4893	  /** M12: Source-ref summaries extracted from clip provenance. */
  4894	  sourceRefs?: readonly TimelineSourceRefSummary[];
  4895	  /** M13: Shader metadata persisted on clips or timeline postprocess app data. */
  4896	  shaders?: readonly TimelineShaderSummary[];
  4897	  /** M12: Render-group summaries extracted from timeline data. */
  4898	  renderGroups?: readonly TimelineRenderGroupSummary[];
  4899	  /** M12: Output metadata extracted from the timeline config. */
  4900	  outputMetadata?: TimelineOutputMetadata;
  4901	}
  4902	
  4903	/** Lightweight clip summary for TimelineSnapshot projection. */
  4904	export interface TimelineClipSummary {
  4905	  id: string;
  4906	  track: string;
  4907	  at: number;
  4908	  clipType?: string;
  4909	  /** Duration in frames (derived from to-from or hold). */
  4910	  duration: number;
  4911	  /** True when this clip is managed by a registered extension. */
  4912	  managed: boolean;
  4913	  /** Extension ID that manages this clip, if managed. */
  4914	  managedBy?: string;
  4915	  /** Generated-object metadata attached by the owning extension, if any. */
  4916	  generatedMeta?: GeneratedObjectMeta;
  4917	  /** M12: Effects applied to this clip. */
  4918	  effects?: readonly TimelineEffectSummary[];
  4919	  /** M12: Transition applied to this clip, if any. */
  4920	  transition?: TimelineTransitionSummary;
  4921	  /** M12: Live bindings attached to this clip. */
  4922	  liveBindings?: readonly TimelineLiveBindingSummary[];
  4923	  /** M12: Material refs consumed by this clip. */
  4924	  materialRefs?: readonly TimelineMaterialRefSummary[];
  4925	  /** M12: Source refs carried by this clip. */
  4926	  sourceRefs?: readonly TimelineSourceRefSummary[];
  4927	}
  4928	
  4929	/** Lightweight track summary for TimelineSnapshot projection. */
  4930	export interface TimelineTrackSummary {
  4931	  id: string;
  4932	  kind: 'visual' | 'audio';
  4933	  label: string;
  4934	  muted: boolean;
  4935	  /** Extension-owned app data attached to this track. */
  4936	  app?: Record<string, unknown>;
  4937	  /** Generated-object metadata attached by the owning extension, if any. */
  4938	  generatedMeta?: GeneratedObjectMeta;
  4939	}
  4940	
  4941	/** Lightweight shader metadata summary for provider-free planner inspection. */
  4942	export interface TimelineShaderSummary {
  4943	  id: string;
  4944	  shaderId: string;
  4945	  scope: ShaderMaterializerRequirementScope;
  4946	  clipId?: string;
  4947	  extensionId: string;
  4948	  contributionId: string;
  4949	  enabled: boolean;
  4950	}
  4951	
  4952	/**
  4953	 * Read-only timeline reader exposed to host and extension code.
  4954	 * Provides stable snapshots without exposing internal stores.
  4955	 */
  4956	export interface TimelineReader {
  4957	  /** Take a point-in-time snapshot of the current timeline state. */
  4958	  snapshot(): TimelineSnapshot;
  4959	}
  4960	
  4961	// ---------------------------------------------------------------------------
  4962	// M12: getCapabilityRequirements — provider-free capability inspection
  4963	// ---------------------------------------------------------------------------
  4964	
  4965	/**
  4966	 * M12: Derive capability requirements from a TimelineSnapshot.
  4967	 *
  4968	 * Inspects clip types, effects, transitions, live bindings, and material
  4969	 * refs present in the snapshot and emits {@link CapabilityRequirement}
  4970	 * records without importing provider stores, raw timeline rows, or
  4971	 * mutation APIs.
  4972	 *
  4973	 * The returned requirements are data-only; they carry route-fit metadata
  4974	 * and determinism posture so planners can aggregate them without
  4975	 * re-deriving the same information from raw timeline data.
  4976	 *
  4977	 * @param snapshot - A TimelineSnapshot produced by a TimelineReader.
  4978	 * @returns Ordered array of CapabilityRequirement records.
  4979	 */
  4980	export function getCapabilityRequirements(
  4981	  snapshot: TimelineSnapshot,
  4982	): CapabilityRequirement[] {
  4983	  const requirements: CapabilityRequirement[] = [];
  4984	  let reqCounter = 0;
  4985	
  4986	  const nextId = (prefix: string): string => {
  4987	    reqCounter += 1;
  4988	    return `snapshot.${prefix}.${reqCounter}`;
  4989	  };
  4990	
  4991	  // Guard: if snapshot has no clips, return empty.
  4992	  if (!snapshot.clips || snapshot.clips.length === 0) {
  4993	    return requirements;
  4994	  }
  4995	
  4996	  // ── Clip-type requirements ──────────────────────────────────────────
  4997	  const seenClipTypes = new Set<string>();
  4998	  for (const clip of snapshot.clips) {
  4999	    if (!clip.clipType || seenClipTypes.has(clip.clipType)) continue;
  5000	    seenClipTypes.add(clip.clipType);
  5001	
  5002	    const sourceRef: CapabilitySourceRef = clip.managedBy
  5003	      ? {
  5004	          source: 'extension',
  5005	          extensionId: clip.managedBy,
  5006	        }
  5007	      : { source: 'built-in' };
  5008	
  5009	    requirements.push({
  5010	      id: nextId('clipType'),
  5011	      sourceRef,
  5012	      route: 'browser-export',
  5013	      requiredCapabilities: ['browser-export'],
  5014	      determinism: clip.managedBy ? 'preview-only' : 'deterministic',
  5015	    });
  5016	  }
  5017	
  5018	  // ── Effect requirements ─────────────────────────────────────────────
  5019	  const seenEffects = new Set<string>();
  5020	  for (const clip of snapshot.clips) {
  5021	    if (!clip.effects) continue;
  5022	    for (const effect of clip.effects) {
  5023	      const effectKey = `${clip.id}.${effect.effectType ?? 'unknown'}`;
  5024	      if (seenEffects.has(effectKey)) continue;
  5025	      seenEffects.add(effectKey);
  5026	
  5027	      const sourceRef: CapabilitySourceRef = effect.managedBy
  5028	        ? {
  5029	            source: 'extension',
  5030	            extensionId: effect.managedBy,
  5031	          }
  5032	        : { source: 'built-in' };
  5033	
  5034	      requirements.push({
  5035	        id: nextId('effect'),
  5036	        sourceRef,
  5037	        route: 'browser-export',
  5038	        requiredCapabilities: ['browser-export'],
  5039	        determinism: effect.managedBy ? 'preview-only' : 'deterministic',
  5040	        findings: effect.managedBy
  5041	          ? undefined
  5042	          : [
  5043	              {
  5044	                id: `builtin.effect.${effect.effectType ?? 'unknown'}.${clip.id}`,
  5045	                severity: 'info',
  5046	                route: 'browser-export',
  5047	                message: `Built-in effect "${effect.effectType ?? 'unknown'}" on clip "${clip.id}" is deterministic for browser export.`,
  5048	                clipId: clip.id,
  5049	              },
  5050	            ],
  5051	      });
  5052	    }
  5053	  }
  5054	
  5055	  // ── Transition requirements ─────────────────────────────────────────
  5056	  const seenTransitions = new Set<string>();
  5057	  for (const clip of snapshot.clips) {
  5058	    if (!clip.transition) continue;
  5059	    const tKey = `${clip.id}.${clip.transition.transitionType ?? 'unknown'}`;
  5060	    if (seenTransitions.has(tKey)) continue;
  5061	    seenTransitions.add(tKey);
  5062	
  5063	    const sourceRef: CapabilitySourceRef = clip.transition.managedBy
  5064	      ? {
  5065	          source: 'extension',
  5066	          extensionId: clip.transition.managedBy,
  5067	        }
  5068	      : { source: 'built-in' };
  5069	
  5070	    requirements.push({
  5071	      id: nextId('transition'),
  5072	      sourceRef,
  5073	      route: 'browser-export',
  5074	      requiredCapabilities: ['browser-export'],
  5075	      determinism: clip.transition.managedBy ? 'preview-only' : 'deterministic',
  5076	    });
  5077	  }
  5078	
  5079	  // ── Live-binding requirements ───────────────────────────────────────
  5080	  if (snapshot.liveBindings) {
  5081	    const seenBindings = new Set<string>();
  5082	    for (const binding of snapshot.liveBindings) {
  5083	      if (seenBindings.has(binding.bindingId)) continue;
  5084	      seenBindings.add(binding.bindingId);
  5085	
  5086	      const sourceRef: CapabilitySourceRef = {
  5087	        source: 'provider',
  5088	      };
  5089	
  5090	      const isBlocking = binding.status !== 'resolved';
  5091	
  5092	      requirements.push({
  5093	        id: nextId('liveBinding'),
  5094	        sourceRef,
  5095	        route: 'browser-export',
  5096	        requiredCapabilities: ['browser-export', 'sidecar-export'],
  5097	        determinism: 'live-unbaked',
  5098	        blocking: isBlocking,
  5099	        routeFit: isBlocking
  5100	          ? {
  5101	              route: 'browser-export',
  5102	              fit: 'blocked',
  5103	              reason: 'live-unbaked',
  5104	              message: `Live binding "${binding.bindingId}" on clip "${binding.clipId}" is not resolved.`,
  5105	            }
  5106	          : {
  5107	              route: 'browser-export',
  5108	              fit: 'supported',
  5109	            },
  5110	        findings: [
  5111	          isBlocking
  5112	            ? {
  5113	                id: `liveBinding.${binding.bindingId}.${binding.clipId}`,
  5114	                severity: 'warning',
  5115	                route: 'browser-export',
  5116	                reason: 'live-unbaked',
  5117	                message: `Live binding "${binding.bindingId}" (source: ${binding.sourceKind}) on clip "${binding.clipId}" has status "${binding.status ?? 'unknown'}".`,
  5118	                clipId: binding.clipId,
  5119	              }
  5120	            : {
  5121	                id: `liveBinding.${binding.bindingId}.${binding.clipId}`,
  5122	                severity: 'info',
  5123	                route: 'browser-export',
  5124	                message: `Live binding "${binding.bindingId}" on clip "${binding.clipId}" is resolved.`,
  5125	                clipId: binding.clipId,
  5126	              },
  5127	        ],
  5128	      });
  5129	    }
  5130	  }
  5131	
  5132	  // ── Material-ref requirements ───────────────────────────────────────
  5133	  if (snapshot.materialRefs) {
  5134	    for (const ref of snapshot.materialRefs) {
  5135	      const sourceRef: CapabilitySourceRef = {
  5136	        source: 'registry',
  5137	      };
  5138	
  5139	      requirements.push({
  5140	        id: nextId('materialRef'),
  5141	        sourceRef,
  5142	        route: 'browser-export',
  5143	        requiredCapabilities: ['browser-export'],
  5144	        determinism: ref.determinism ?? 'unknown',
  5145	      });
  5146	    }
  5147	  }
  5148	
  5149	  // ── Source-ref requirements ────────────────────────────────────────
  5150	  if (snapshot.sourceRefs) {
  5151	    for (const ref of snapshot.sourceRefs) {
  5152	      const sourceRef: CapabilitySourceRef = ref.extensionId
  5153	        ? {
  5154	            source: 'extension',
  5155	            extensionId: ref.extensionId,
  5156	          }
  5157	        : {
  5158	            source: ref.sourceKind === 'generation' ? 'provider' : 'registry',
  5159	          };
  5160	
  5161	      const determinism = ref.determinism ?? 'unknown';
  5162	      const blocksBrowserExport =
  5163	        determinism === 'process-dependent' || determinism === 'live-unbaked';
  5164	
  5165	      requirements.push({
  5166	        id: nextId('sourceRef'),
  5167	        sourceRef,
  5168	        route: 'browser-export',
  5169	        requiredCapabilities: blocksBrowserExport
  5170	          ? ['browser-export', 'sidecar-export']
  5171	          : ['browser-export'],
  5172	        determinism,
  5173	        ...(blocksBrowserExport
  5174	          ? {
  5175	              blocking: true,
  5176	              routeFit: {
  5177	                route: 'browser-export',
  5178	                fit: 'blocked',
  5179	                reason: determinism,
  5180	                message: `Source ref "${ref.id}" on clip "${ref.clipId}" requires materialization before browser export.`,
  5181	              },
  5182	            }
  5183	          : {}),
  5184	      });
  5185	    }
  5186	  }
  5187	
  5188	  // ── Shader materializer requirements ───────────────────────────────
  5189	  if (snapshot.shaders) {
  5190	    for (const shader of snapshot.shaders) {
  5191	      if (shader.enabled === false) continue;
  5192	
  5193	      const sourceRef: CapabilitySourceRef = {
  5194	        source: 'extension',
  5195	        extensionId: shader.extensionId,
  5196	        contributionId: shader.contributionId,
  5197	      };
  5198	      const routes: readonly RenderRoute[] = ['browser-export', 'worker-export'];
  5199	
  5200	      for (const route of routes) {
  5201	        const message = shaderMissingMaterializerBlockerMessage(
  5202	          shader.shaderId,
  5203	          shader.scope,
  5204	          shader.clipId,
  5205	        );
  5206	        requirements.push({
  5207	          id: nextId('shader'),
  5208	          sourceRef,
  5209	          route,
  5210	          requiredCapabilities: ['render-material', 'shader-materializer'],
  5211	          determinism: 'preview-only',
  5212	          blocking: true,
  5213	          routeFit: {
  5214	            route,
  5215	            fit: 'blocked',
  5216	            reason: 'missing-material',
  5217	            message,
  5218	          },
  5219	        });
  5220	      }
  5221	    }
  5222	  }
  5223	
  5224	  return requirements;
  5225	}

exec
/bin/zsh -lc "nl -ba src/tools/video-editor/compositions/TimelineRenderer.tsx | sed -n '260,460p' && nl -ba src/tools/video-editor/compositions/VisualClip.tsx | sed -n '260,550p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
   260	  records: readonly TimelineLiveBindingRecord[],
   261	): LiveBindingRecordsByClip {
   262	  const grouped = new Map<string, TimelineLiveBindingRecord[]>();
   263	  for (const record of records) {
   264	    const entries = grouped.get(record.clipId) ?? [];
   265	    entries.push(record);
   266	    grouped.set(record.clipId, entries);
   267	  }
   268	  return grouped;
   269	}
   270	
   271	function liveSourceSnapshotsFromRegistry(
   272	  snapshot: LiveDataRegistrySnapshot | undefined,
   273	): readonly TimelineLiveSourceSnapshot[] {
   274	  if (!snapshot) return Object.freeze([]);
   275	  return Object.freeze([
   276	    ...snapshot.sources.map((source) => ({
   277	      sourceId: source.id,
   278	      kind: source.kind,
   279	      status: source.status,
   280	    })),
   281	    ...snapshot.tombstones.map((tombstone) => ({
   282	      sourceId: tombstone.id,
   283	      kind: tombstone.kind,
   284	      status: tombstone.status,
   285	      ownerExtensionId: tombstone.extensionId,
   286	    })),
   287	  ]);
   288	}
   289	
   290	function deterministicRefsForRecord(record: TimelineLiveBindingRecord) {
   291	  return Object.freeze([
   292	    ...(record.binding.deterministicRefs ?? []),
   293	    ...(record.binding.bake?.deterministicRefs ?? []),
   294	  ]);
   295	}
   296	
   297	function toRendererLiveBinding(record: TimelineLiveBindingRecord): ClipRendererLiveBinding {
   298	  return Object.freeze({
   299	    bindingId: record.binding.bindingId,
   300	    sourceId: record.binding.sourceId,
   301	    channelId: record.binding.channelId,
   302	    targetParamName: record.binding.targetParamName,
   303	    status: record.status,
   304	    binding: record.binding,
   305	    deterministicRefs: deterministicRefsForRecord(record),
   306	    diagnostics: Object.freeze(record.diagnostics.map((diagnostic) => Object.freeze({
   307	      severity: diagnostic.severity,
   308	      code: diagnostic.code,
   309	      message: diagnostic.message,
   310	      path: diagnostic.path,
   311	    }))),
   312	  });
   313	}
   314	
   315	const isRecord = (value: unknown): value is Record<string, unknown> => (
   316	  value !== null && typeof value === 'object' && !Array.isArray(value)
   317	);
   318	
   319	function numericValue(value: unknown): number | undefined {
   320	  if (typeof value === 'number' && Number.isFinite(value)) return value;
   321	  if (typeof value === 'string' && value.trim().length > 0) {
   322	    const parsed = Number(value);
   323	    return Number.isFinite(parsed) ? parsed : undefined;
   324	  }
   325	  return undefined;
   326	}
   327	
   328	function normalizedProgress(value: unknown): number | undefined {
   329	  const numeric = numericValue(value);
   330	  if (numeric === undefined) return undefined;
   331	  const percent = numeric <= 1 ? numeric * 100 : numeric;
   332	  return Math.max(0, Math.min(100, Math.round(percent)));
   333	}
   334	
   335	function firstString(...values: unknown[]): string | undefined {
   336	  for (const value of values) {
   337	    if (typeof value === 'string' && value.length > 0) return value;
   338	  }
   339	  return undefined;
   340	}
   341	
   342	function sampleDataRecord(sample: LiveSample | undefined): Record<string, unknown> | undefined {
   343	  if (!sample) return undefined;
   344	  return isRecord(sample.frame.data) ? sample.frame.data : undefined;
   345	}
   346	
   347	function sampleMetadataRecord(sample: LiveSample | undefined): Record<string, unknown> | undefined {
   348	  if (!sample) return undefined;
   349	  return isRecord(sample.frame.metadata) ? sample.frame.metadata : undefined;
   350	}
   351	
   352	function sampleFrameSrc(sample: LiveSample | undefined): string | undefined {
   353	  const data = sampleDataRecord(sample);
   354	  const metadata = sampleMetadataRecord(sample);
   355	  return firstString(
   356	    data?.src,
   357	    data?.url,
   358	    data?.dataUrl,
   359	    data?.dataURL,
   360	    data?.uri,
   361	    metadata?.src,
   362	    metadata?.url,
   363	    metadata?.dataUrl,
   364	    metadata?.dataURL,
   365	    metadata?.uri,
   366	  );
   367	}
   368	
   369	function sampleFrameState(sample: LiveSample | undefined): 'pending' | 'refining' | 'final' | 'cancelled' | 'error' | undefined {
   370	  const data = sampleDataRecord(sample);
   371	  const metadata = sampleMetadataRecord(sample);
   372	  const raw = firstString(
   373	    metadata?.state,
   374	    metadata?.status,
   375	    metadata?.phase,
   376	    data?.state,
   377	    data?.status,
   378	    data?.phase,
   379	  )?.toLowerCase();
   380	
   381	  if (raw === 'pending' || raw === 'queued' || raw === 'requesting') return 'pending';
   382	  if (raw === 'refining' || raw === 'refine' || raw === 'progress' || raw === 'processing') return 'refining';
   383	  if (raw === 'final' || raw === 'ready' || raw === 'complete' || raw === 'completed') return 'final';
   384	  if (raw === 'cancelled' || raw === 'canceled') return 'cancelled';
   385	  if (raw === 'error' || raw === 'failed' || raw === 'failure') return 'error';
   386	  return undefined;
   387	}
   388	
   389	function sampleProgress(sample: LiveSample | undefined): number | undefined {
   390	  const data = sampleDataRecord(sample);
   391	  const metadata = sampleMetadataRecord(sample);
   392	  return normalizedProgress(
   393	    metadata?.progress
   394	      ?? metadata?.percent
   395	      ?? data?.progress
   396	      ?? data?.percent,
   397	  );
   398	}
   399	
   400	function bindingProgress(binding: TimelineLiveBindingRecord['binding']): number | undefined {
   401	  const placeholder = isRecord(binding.placeholder) ? binding.placeholder : undefined;
   402	  const metadata = isRecord(binding.metadata) ? binding.metadata : undefined;
   403	  return normalizedProgress(
   404	    placeholder?.progress
   405	      ?? placeholder?.percent
   406	      ?? metadata?.progress
   407	      ?? metadata?.percent,
   408	  );
   409	}
   410	
   411	function bindingPreviewHint(binding: TimelineLiveBindingRecord['binding']): string | undefined {
   412	  const placeholder = isRecord(binding.placeholder) ? binding.placeholder : undefined;
   413	  const metadata = isRecord(binding.metadata) ? binding.metadata : undefined;
   414	  return firstString(
   415	    placeholder?.kind,
   416	    placeholder?.preview,
   417	    placeholder?.reader,
   418	    metadata?.preview,
   419	    metadata?.previewReader,
   420	    metadata?.reader,
   421	    binding.targetParamName,
   422	  )?.toLowerCase();
   423	}
   424	
   425	function clipPreviewHint(clip: ResolvedTimelineClip): string | undefined {
   426	  const app = isRecord(clip.app) ? clip.app : undefined;
   427	  if (app?.livePreview === true || clip.params?.livePreview === true) return 'frame';
   428	  return firstString(
   429	    app?.livePreview,
   430	    app?.livePreviewReader,
   431	    clip.params?.livePreview,
   432	    clip.params?.livePreviewReader,
   433	  )?.toLowerCase();
   434	}
   435	
   436	function shouldUseLiveFramePreview(
   437	  clip: ResolvedTimelineClip,
   438	  records: readonly TimelineLiveBindingRecord[],
   439	): boolean {
   440	  if (records.length === 0) return false;
   441	  if (clip.clipType === 'live-frame-preview' || clip.clipType === 'live-visual-preview') return true;
   442	  const clipHint = clipPreviewHint(clip);
   443	  if (clipHint === 'frame' || clipHint === 'frame-preview' || clipHint === 'live-frame') return true;
   444	  return records.some((record) => {
   445	    const hint = bindingPreviewHint(record.binding);
   446	    return (
   447	      hint === 'frame'
   448	      || hint === 'frame-preview'
   449	      || hint === 'live-frame'
   450	      || hint === 'src'
   451	      || hint === 'image'
   452	      || hint === 'video'
   453	    );
   454	  });
   455	}
   456	
   457	function sampleFrameIndex(sample: LiveSample): number | undefined {
   458	  const data = sampleDataRecord(sample);
   459	  const metadata = sampleMetadataRecord(sample);
   460	  return numericValue(
   260	    height: clip.height ?? compositionHeight,
   261	  };
   262	};
   263	
   264	const isRecord = (value: unknown): value is Record<string, unknown> => (
   265	  value !== null && typeof value === 'object' && !Array.isArray(value)
   266	);
   267	
   268	function materialRefsForClip(
   269	  clip: ResolvedTimelineClip,
   270	  materialRefs: readonly RenderMaterialRef[] | undefined,
   271	): readonly RenderMaterialRef[] {
   272	  if (materialRefs && materialRefs.length > 0) return materialRefs;
   273	  const app = isRecord(clip.app) ? clip.app : undefined;
   274	  const refs = app?.materialRefs ?? clip.params?.materialRefs;
   275	  return Array.isArray(refs) ? refs.filter(isRecord) as unknown as readonly RenderMaterialRef[] : [];
   276	}
   277	
   278	function statusForMaterial(material: RenderMaterialRef, statuses: readonly RenderPlannerMaterialStatus[] | undefined): RenderPlannerMaterialStatus {
   279	  return statuses?.find((status) => status.materialRefId === material.id)
   280	    ?? { materialRefId: material.id, state: material.determinism === 'deterministic' ? 'resolved' : 'unbaked' };
   281	}
   282	
   283	function shouldRenderMaterialPlaceholder(status: RenderPlannerMaterialStatus): boolean {
   284	  return status.state === 'missing' || status.state === 'stale' || status.state === 'unbaked';
   285	}
   286	
   287	const VisualAsset: FC<VisualClipProps> = ({ clip, track, fps }) => {
   288	  const { width: compositionWidth, height: compositionHeight } = useVideoConfig();
   289	  // SD-025: never silent-null when a built-in clip is missing its asset.
   290	  // Render a labeled red band so the gap is obvious in preview/export.
   291	  if (!clip.assetEntry) {
   292	    return <MissingAssetBody clipId={clip.id} clipType={clip.clipType ?? 'media'} />;
   293	  }
   294	
   295	  const mediaSrc = getSanitizedMediaSrc(clip.assetEntry.src);
   296	  if (!mediaSrc) {
   297	    return <MissingAssetBody clipId={clip.id} clipType={clip.clipType ?? 'media'} />;
   298	  }
   299	
   300	  const clipVolume = getSanitizedVolume(clip.volume);
   301	  const effectiveVolume = track.muted ? 0 : getSanitizedVolume(track.volume) * clipVolume;
   302	  const playbackRate = getSanitizedPlaybackRate(clip.speed);
   303	  const trimProps = getSanitizedMediaTrimProps(clip, fps);
   304	  const isImage = clip.assetEntry.type?.startsWith('image');
   305	  const isVideo = clip.assetEntry.type?.startsWith('video');
   306	  if (!isImage && !isVideo) {
   307	    return (
   308	      <UnsupportedAssetBody
   309	        clipId={clip.id}
   310	        clipType={clip.clipType ?? 'media'}
   311	        assetType={clip.assetEntry.type}
   312	      />
   313	    );
   314	  }
   315	  const hasPositionOverride = (
   316	    clip.x !== undefined
   317	    || clip.y !== undefined
   318	    || clip.width !== undefined
   319	    || clip.height !== undefined
   320	    || clip.cropTop !== undefined
   321	    || clip.cropBottom !== undefined
   322	    || clip.cropLeft !== undefined
   323	    || clip.cropRight !== undefined
   324	  );
   325	  const fit = track.fit ?? 'contain';
   326	  const useViewportLayout = fit === 'manual' || hasPositionOverride;
   327	
   328	  if (!useViewportLayout) {
   329	    const style = getClipBoxStyle(clip, track, compositionWidth, compositionHeight);
   330	    const sharedStyle: CSSProperties = {
   331	      ...style,
   332	      mixBlendMode: track.blendMode && track.blendMode !== 'normal' ? track.blendMode : undefined,
   333	    };
   334	
   335	    if (isImage) {
   336	      return <Img src={mediaSrc} style={sharedStyle} crossOrigin="anonymous" />;
   337	    }
   338	
   339	    return (
   340	      <MediaErrorBoundary
   341	        clipId={clip.id}
   342	        resetKey={`${clip.id}:${mediaSrc}:${trimProps.trimBefore}:${trimProps.trimAfter ?? 'none'}:${playbackRate}:${effectiveVolume}`}
   343	        fallback={null}
   344	      >
   345	        <Video
   346	          src={mediaSrc}
   347	          trimBefore={trimProps.trimBefore}
   348	          trimAfter={trimProps.trimAfter}
   349	          playbackRate={playbackRate}
   350	          volume={effectiveVolume}
   351	          muted={effectiveVolume <= 0}
   352	          style={sharedStyle}
   353	        />
   354	      </MediaErrorBoundary>
   355	    );
   356	  }
   357	
   358	  const fullBounds = {
   359	    x: clip.x ?? 0,
   360	    y: clip.y ?? 0,
   361	    width: clip.width ?? compositionWidth,
   362	    height: clip.height ?? compositionHeight,
   363	  };
   364	  const intrinsicSize = getIntrinsicMediaSize(clip, compositionWidth, compositionHeight);
   365	  const viewportLayout = computeViewportMediaLayout({
   366	    fullBounds,
   367	    cropValues: {
   368	      cropTop: clip.cropTop,
   369	      cropBottom: clip.cropBottom,
   370	      cropLeft: clip.cropLeft,
   371	      cropRight: clip.cropRight,
   372	    },
   373	    compositionWidth,
   374	    compositionHeight,
   375	    intrinsicWidth: intrinsicSize.width,
   376	    intrinsicHeight: intrinsicSize.height,
   377	  });
   378	
   379	  if (!viewportLayout) {
   380	    return null;
   381	  }
   382	
   383	  const viewportStyle: CSSProperties = {
   384	    position: 'absolute',
   385	    left: viewportLayout.renderBounds.x,
   386	    top: viewportLayout.renderBounds.y,
   387	    width: viewportLayout.renderBounds.width,
   388	    height: viewportLayout.renderBounds.height,
   389	    overflow: 'hidden',
   390	    opacity: clip.opacity ?? 1,
   391	  };
   392	  const mediaStyle: CSSProperties = {
   393	    position: 'absolute',
   394	    left: viewportLayout.mediaBounds.x,
   395	    top: viewportLayout.mediaBounds.y,
   396	    width: viewportLayout.mediaBounds.width,
   397	    height: viewportLayout.mediaBounds.height,
   398	    // Override Tailwind preflight's `img { max-width: 100%; height: auto; }`
   399	    // which would squash the media to fit the viewport container. The media
   400	    // must overflow the container (clipped by overflow:hidden) for the
   401	    // manual cover layout to work correctly.
   402	    maxWidth: 'none',
   403	    maxHeight: 'none',
   404	    mixBlendMode: track.blendMode && track.blendMode !== 'normal' ? track.blendMode : undefined,
   405	  };
   406	
   407	  if (isImage) {
   408	    return (
   409	      <div style={viewportStyle}>
   410	        <Img src={mediaSrc} style={mediaStyle} crossOrigin="anonymous" />
   411	      </div>
   412	    );
   413	  }
   414	
   415	  return (
   416	    <div style={viewportStyle}>
   417	      <MediaErrorBoundary
   418	        clipId={clip.id}
   419	        resetKey={`${clip.id}:${mediaSrc}:${trimProps.trimBefore}:${trimProps.trimAfter ?? 'none'}:${playbackRate}:${effectiveVolume}:viewport`}
   420	        fallback={null}
   421	      >
   422	        <Video
   423	          src={mediaSrc}
   424	          trimBefore={trimProps.trimBefore}
   425	          trimAfter={trimProps.trimAfter}
   426	          playbackRate={playbackRate}
   427	          volume={effectiveVolume}
   428	          muted={effectiveVolume <= 0}
   429	          style={mediaStyle}
   430	        />
   431	      </MediaErrorBoundary>
   432	    </div>
   433	  );
   434	};
   435	
   436	export const VisualClip: FC<VisualClipProps> = ({
   437	  clip,
   438	  track,
   439	  fps,
   440	  effectRegistrySnapshot,
   441	  shaderRegistrySnapshot,
   442	  materialRefs,
   443	  materialStatuses,
   444	  materialDiagnostics,
   445	}) => {
   446	  const environment = useRemotionEnvironment();
   447	  const providerRegistryContext = useOptionalEffectRegistryContext();
   448	  const registrySnapshot = effectRegistrySnapshot ?? providerRegistryContext?.snapshot;
   449	  const providerShaderRegistryContext = useOptionalShaderEffectRegistryContext();
   450	  const shaderSnapshot = shaderRegistrySnapshot ?? providerShaderRegistryContext?.snapshot;
   451	  const { width: compositionWidth, height: compositionHeight } = useVideoConfig();
   452	
   453	  // Transition registry: resolve through the unified catalog (built-ins +
   454	  // provider-scoped contributed transitions). No silent fallback to crossfade
   455	  // for missing or unrenderable IDs.
   456	  const transitionRegistryContext = useOptionalTransitionRegistryContext();
   457	  const mergedTransitionSnapshot = useMemo(
   458	    () => createTransitionSnapshot(transitionRegistryContext?.snapshot),
   459	    [transitionRegistryContext?.snapshot],
   460	  );
   461	
   462	  if (clip.clipType === 'effect-layer') {
   463	    return null;
   464	  }
   465	
   466	  const pendingMaterial = materialRefsForClip(clip, materialRefs)
   467	    .map((material) => ({ material, status: statusForMaterial(material, materialStatuses) }))
   468	    .find(({ status }) => shouldRenderMaterialPlaceholder(status));
   469	
   470	  if (pendingMaterial) {
   471	    return (
   472	      <PendingMaterialPlaceholder
   473	        clipId={clip.id}
   474	        material={pendingMaterial.material}
   475	        status={pendingMaterial.status}
   476	        diagnostics={materialDiagnostics?.filter((diagnostic) =>
   477	          diagnostic.materialRefId === pendingMaterial.material.id || diagnostic.clipId === clip.id)}
   478	      />
   479	    );
   480	  }
   481	
   482	  const durationInFrames = getClipDurationInFrames(clip, fps);
   483	  const frame = useCurrentFrame();
   484	  const shader = getTimelineClipShader(clip);
   485	  const shaderRecord = shader
   486	    ? shaderSnapshot?.get(shader.shaderId, shader.extensionId)
   487	    : undefined;
   488	  const renderBrowserShaderPreview = Boolean(
   489	    shader
   490	    && shader.enabled !== false
   491	    && shaderRecord
   492	    && !environment.isRendering
   493	    && !environment.isClientSideRendering,
   494	  );
   495	  const renderUnsupportedShaderExport = Boolean(
   496	    shader
   497	    && shader.enabled !== false
   498	    && (environment.isRendering || environment.isClientSideRendering),
   499	  );
   500	
   501	  let transitionStyle: CSSProperties | undefined;
   502	  if (clip.transition) {
   503	    const record = resolveTransition(clip.transition.type, mergedTransitionSnapshot);
   504	    if (record) {
   505	      const transitionProgress = interpolate(
   506	        frame,
   507	        [0, Math.max(1, secondsToFrames(clip.transition.duration, fps))],
   508	        [0, 1],
   509	        {
   510	          extrapolateLeft: 'clamp',
   511	          extrapolateRight: 'clamp',
   512	        },
   513	      );
   514	      const renderer = record.renderer;
   515	      const params = clip.transition.params ?? {};
   516	      if (typeof renderer === 'function') {
   517	        transitionStyle = (renderer as (progress: number, params: Record<string, unknown>) => CSSProperties)(
   518	          transitionProgress,
   519	          params,
   520	        );
   521	      } else {
   522	        // Object-style renderer (static CSSProperties)
   523	        transitionStyle = renderer as CSSProperties;
   524	      }
   525	    } else {
   526	      // Transition ID not found in catalog — render diagnostic placeholder
   527	      // and skip the clip content wrapper (the clip still renders, but
   528	      // without transition styling). No crossfade fallback.
   529	      return <MissingTransitionBody clipId={clip.id} transitionType={clip.transition.type} />;
   530	    }
   531	  }
   532	
   533	  const content: ReactNode = (
   534	    <AbsoluteFill style={{ overflow: 'hidden', ...transitionStyle }}>
   535	      <VisualAsset clip={clip} track={track} fps={fps} />
   536	      {renderUnsupportedShaderExport && shader ? (
   537	        <UnsupportedClipShaderExportBody clipId={clip.id} shaderId={shader.shaderId} />
   538	      ) : null}
   539	      {renderBrowserShaderPreview && shader && shaderRecord ? (
   540	        <ClipShaderPreviewCanvas
   541	          shader={shader}
   542	          record={shaderRecord}
   543	          timeSeconds={frame / fps}
   544	          frame={frame}
   545	          width={compositionWidth}
   546	          height={compositionHeight}
   547	          testId="visual-clip-shader-preview"
   548	          style={{
   549	            position: 'absolute',
   550	            inset: 0,

codex
Export still has duplicated scanner paths: `exportGuard.ts` scans raw `ResolvedTimelineConfig` for live bindings and shader metadata, while `planRender` can also consume a `TimelineSnapshot`. That duplication is the clearest evidence the deletion payoff has not landed yet.
exec
/bin/zsh -lc "nl -ba src/tools/video-editor/compositions/TimelineRenderer.tsx | sed -n '1,180p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
     1	import { AbsoluteFill, Sequence, useCurrentFrame, useRemotionEnvironment } from 'remotion';
     2	import { Component, memo, useContext, useMemo, useSyncExternalStore, type FC, type ReactNode } from 'react';
     3	import { getAudioTracks, getVisualTracks } from '@/tools/video-editor/lib/editor-utils.ts';
     4	import { getClipDurationInFrames, getTimelineDurationInFrames, secondsToFrames } from '@/tools/video-editor/lib/config-utils.ts';
     5	import {
     6	  BUILTIN_CLIP_TYPES,
     7	  type ParameterSchema,
     8	  type ResolvedTimelineClip,
     9	  type ResolvedTimelineConfig,
    10	  type TimelineConfig,
    11	  type TrackDefinition,
    12	} from '@/tools/video-editor/types/index.ts';
    13	import { AudioTrack } from '@/tools/video-editor/compositions/AudioTrack.tsx';
    14	import { AudioAnalysisProvider } from '@/tools/video-editor/compositions/AudioAnalysisProvider.tsx';
    15	import { EffectLayerSequence } from '@/tools/video-editor/compositions/EffectLayerSequence.tsx';
    16	import { TextClipSequence } from '@/tools/video-editor/compositions/TextClip.tsx';
    17	import { VisualClipSequence } from '@/tools/video-editor/compositions/VisualClip.tsx';
    18	import { UnknownClipPlaceholderSequence } from '@/tools/video-editor/compositions/UnknownClipPlaceholder.tsx';
    19	import { resolveTimelineRenderTheme } from '@/tools/video-editor/compositions/installed-themes.ts';
    20	import {
    21	  getGeneratedRemotionModuleStatus,
    22	  isGeneratedRemotionModuleClip,
    23	} from '@/tools/video-editor/lib/generated-lanes.ts';
    24	import { materializeResolvedSequenceConfig } from '@/tools/video-editor/sequences/materialize.ts';
    25	import {
    26	  ThemeProvider,
    27	  useTheme,
    28	  type RuntimeTheme,
    29	  type Theme,
    30	} from '@banodoco/timeline-composition/theme-api';
    31	import {
    32	  describeClipCapabilityWith,
    33	  resolveSequenceClipEntry,
    34	  SEQUENCE_COMPONENT_REGISTRY,
    35	  type DynamicSequenceComponentEntry,
    36	} from '@/tools/video-editor/sequences/registry.ts';
    37	import { useSequenceComponentRegistrySnapshot } from '@/tools/video-editor/sequences/SequenceComponentRegistryContext.tsx';
    38	import { useClipTypeRegistrySnapshot } from '@/tools/video-editor/clip-types/ClipTypeRegistryContext.tsx';
    39	import type {
    40	  ClipRendererLiveBinding,
    41	  ClipRendererLiveProps,
    42	  ClipRendererProps,
    43	  ClipTypeRegistryRecord,
    44	} from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';
    45	import { applyAutomationOverrides, resolveAnimatedParams } from '@/tools/video-editor/keyframes/index.ts';
    46	import { DataProviderContext } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
    47	import {
    48	  getTimelinePostprocessShader,
    49	  scanTimelineLiveBindings,
    50	  type TimelineLiveBindingRecord,
    51	  type TimelineLiveSourceSnapshot,
    52	} from '@/tools/video-editor/lib/timeline-domain.ts';
    53	import type { LiveDataRegistry, LiveDataRegistrySnapshot } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
    54	import type { LiveChannelDescriptor, LiveChannelMetadata, LiveSample, LiveSource } from '@reigh/editor-sdk';
    55	import { PostprocessShaderPreviewCanvas } from '@/tools/video-editor/shaders/preview/PostprocessShaderPreviewCanvas.tsx';
    56	import { useShaderEffectRegistrySnapshot } from '@/tools/video-editor/shaders/registry/index.ts';
    57	
    58	// Phase 4d (Sprint 5): EFFECT_REGISTRY dispatch.
    59	//
    60	// Mirrors `tools/remotion/src/HypeComposition.tsx:58-64` (lifted into
    61	// `packages/timeline-composition/typescript/src/TimelineComposition.tsx`).
    62	// Lookup chain for a clipType:
    63	//
    64	//   1. Reigh-native built-ins (effect-layer, text, media, hold) — same as
    65	//      pre-Sprint-5 behavior.
    66	//   2. THEME_PACKAGE_REGISTRY (codegenned from installed
    67	//      @banodoco/timeline-theme-* packages) — render the theme component.
    68	//   3. Sprint-3 loud placeholder — defensive fallback when the theme
    69	//      package isn't installed OR the clipType is unknown.
    70	const isBuiltinClipType = (value: string | undefined): boolean => {
    71	  if (typeof value !== 'string') {
    72	    return true; // legacy clips with no clipType default to media-equivalent dispatch
    73	  }
    74	  return (BUILTIN_CLIP_TYPES as readonly string[]).includes(value);
    75	};
    76	
    77	// Dynamic-aware sequence-component dispatch check. Built-in entries match
    78	// SEQUENCE_COMPONENT_REGISTRY directly; DB-stored entries (clipType
    79	// `custom:<name>`) match via the dynamic resolver. We accept any clipType
    80	// that has a registry entry on either side and a browser-preview-capable
    81	// capability descriptor.
    82	const isSequenceComponentClipType = (
    83	  value: string | undefined,
    84	  dynamicEntries: readonly DynamicSequenceComponentEntry[],
    85	): boolean => {
    86	  if (typeof value !== 'string') return false;
    87	  if (resolveSequenceClipEntry(value, dynamicEntries)) return true;
    88	  return Object.prototype.hasOwnProperty.call(SEQUENCE_COMPONENT_REGISTRY, value);
    89	};
    90	
    91	const sortClipsByAt = (clips: ResolvedTimelineClip[]): ResolvedTimelineClip[] => {
    92	  return [...clips].sort((left, right) => left.at - right.at);
    93	};
    94	
    95	type ThemeEffectSequenceProps = {
    96	  clip: ResolvedTimelineClip;
    97	  fps: number;
    98	  theme: Theme;
    99	  dynamicEntries: readonly DynamicSequenceComponentEntry[];
   100	};
   101	
   102	const ThemePackageComponent: FC<{
   103	  component: FC<{
   104	    clip: ResolvedTimelineClip;
   105	    params: unknown;
   106	    theme: RuntimeTheme;
   107	    fps: number;
   108	  }>;
   109	  clip: ResolvedTimelineClip;
   110	  fps: number;
   111	}> = ({ component: Component, clip, fps }) => {
   112	  const theme = useTheme();
   113	  return <Component clip={clip} params={clip.params} theme={theme} fps={fps} />;
   114	};
   115	
   116	const ThemeEffectSequence: FC<ThemeEffectSequenceProps> = ({ clip, fps, theme, dynamicEntries }) => {
   117	  // Dynamic-aware lookup: prefer DB-stored components for `custom:` clipTypes;
   118	  // fall back to the static SEQUENCE_COMPONENT_REGISTRY for built-ins.
   119	  const dynamicEntry = resolveSequenceClipEntry(clip.clipType, dynamicEntries);
   120	  const staticEntry = SEQUENCE_COMPONENT_REGISTRY[clip.clipType as keyof typeof SEQUENCE_COMPONENT_REGISTRY];
   121	  const Component = (dynamicEntry?.component ?? staticEntry?.component) as
   122	    | FC<{ clip: ResolvedTimelineClip; params: unknown; theme: RuntimeTheme; fps: number }>
   123	    | undefined;
   124	  // Defensive: if neither registry has the component, fall back to the loud
   125	  // placeholder. This is the second layer of the SD-025 "loud placeholder"
   126	  // safety net for clipTypes that *are* in the registry but somehow fail to
   127	  // render.
   128	  if (!Component) {
   129	    return <UnknownClipPlaceholderSequence clip={clip} fps={fps} reason="unsupported" />;
   130	  }
   131	  const durationInFrames = getClipDurationInFrames(clip, fps);
   132	  return (
   133	    <Sequence
   134	      key={clip.id}
   135	      from={Math.round(clip.at * fps)}
   136	      durationInFrames={durationInFrames}
   137	    >
   138	      <ThemeProvider value={theme}>
   139	        <ThemePackageComponent component={Component} clip={clip} fps={fps} />
   140	      </ThemeProvider>
   141	    </Sequence>
   142	  );
   143	};
   144	
   145	const GeneratedModulePlaceholderSequence: FC<{
   146	  clip: ResolvedTimelineClip;
   147	  fps: number;
   148	}> = ({ clip, fps }) => {
   149	  const moduleStatus = getGeneratedRemotionModuleStatus(clip);
   150	  const durationInFrames = getClipDurationInFrames(clip, fps);
   151	  const artifactId = moduleStatus.kind === 'valid_module' ? moduleStatus.artifactId : null;
   152	  const reason = moduleStatus.kind === 'blocked_module' ? moduleStatus.reason : 'worker_only';
   153	  return (
   154	    <Sequence
   155	      key={clip.id}
   156	      from={Math.max(0, Math.round(clip.at * fps))}
   157	      durationInFrames={durationInFrames}
   158	    >
   159	      <AbsoluteFill
   160	        data-testid="generated-module-placeholder"
   161	        data-clip-id={clip.id}
   162	        data-artifact-id={artifactId ?? undefined}
   163	        data-placeholder-reason={reason}
   164	        style={{
   165	          backgroundColor: '#111827',
   166	          borderTop: '2px solid #38bdf8',
   167	          borderBottom: '2px solid #38bdf8',
   168	          color: '#e0f2fe',
   169	          display: 'flex',
   170	          alignItems: 'center',
   171	          justifyContent: 'center',
   172	          padding: '12px 24px',
   173	          textAlign: 'center',
   174	          fontFamily: 'ui-monospace, SFMono-Regular, "Roboto Mono", Menlo, Consolas, monospace',
   175	          fontSize: 14,
   176	          lineHeight: 1.4,
   177	          letterSpacing: '0.04em',
   178	        }}
   179	      >
   180	        <div

exec
/bin/zsh -lc "nl -ba src/tools/video-editor/compositions/TimelineRenderer.tsx | sed -n '400,620p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
   400	function bindingProgress(binding: TimelineLiveBindingRecord['binding']): number | undefined {
   401	  const placeholder = isRecord(binding.placeholder) ? binding.placeholder : undefined;
   402	  const metadata = isRecord(binding.metadata) ? binding.metadata : undefined;
   403	  return normalizedProgress(
   404	    placeholder?.progress
   405	      ?? placeholder?.percent
   406	      ?? metadata?.progress
   407	      ?? metadata?.percent,
   408	  );
   409	}
   410	
   411	function bindingPreviewHint(binding: TimelineLiveBindingRecord['binding']): string | undefined {
   412	  const placeholder = isRecord(binding.placeholder) ? binding.placeholder : undefined;
   413	  const metadata = isRecord(binding.metadata) ? binding.metadata : undefined;
   414	  return firstString(
   415	    placeholder?.kind,
   416	    placeholder?.preview,
   417	    placeholder?.reader,
   418	    metadata?.preview,
   419	    metadata?.previewReader,
   420	    metadata?.reader,
   421	    binding.targetParamName,
   422	  )?.toLowerCase();
   423	}
   424	
   425	function clipPreviewHint(clip: ResolvedTimelineClip): string | undefined {
   426	  const app = isRecord(clip.app) ? clip.app : undefined;
   427	  if (app?.livePreview === true || clip.params?.livePreview === true) return 'frame';
   428	  return firstString(
   429	    app?.livePreview,
   430	    app?.livePreviewReader,
   431	    clip.params?.livePreview,
   432	    clip.params?.livePreviewReader,
   433	  )?.toLowerCase();
   434	}
   435	
   436	function shouldUseLiveFramePreview(
   437	  clip: ResolvedTimelineClip,
   438	  records: readonly TimelineLiveBindingRecord[],
   439	): boolean {
   440	  if (records.length === 0) return false;
   441	  if (clip.clipType === 'live-frame-preview' || clip.clipType === 'live-visual-preview') return true;
   442	  const clipHint = clipPreviewHint(clip);
   443	  if (clipHint === 'frame' || clipHint === 'frame-preview' || clipHint === 'live-frame') return true;
   444	  return records.some((record) => {
   445	    const hint = bindingPreviewHint(record.binding);
   446	    return (
   447	      hint === 'frame'
   448	      || hint === 'frame-preview'
   449	      || hint === 'live-frame'
   450	      || hint === 'src'
   451	      || hint === 'image'
   452	      || hint === 'video'
   453	    );
   454	  });
   455	}
   456	
   457	function sampleFrameIndex(sample: LiveSample): number | undefined {
   458	  const data = sampleDataRecord(sample);
   459	  const metadata = sampleMetadataRecord(sample);
   460	  return numericValue(
   461	    metadata?.frame
   462	      ?? metadata?.frameIndex
   463	      ?? metadata?.frameNumber
   464	      ?? data?.frame
   465	      ?? data?.frameIndex
   466	      ?? data?.frameNumber,
   467	  );
   468	}
   469	
   470	function resolveTimeSample(samples: readonly LiveSample[], targetTimestampMs: number): LiveSample | undefined {
   471	  const ordered = [...samples].sort((left, right) => left.frame.timestamp - right.frame.timestamp);
   472	  let best: LiveSample | undefined;
   473	  for (const sample of ordered) {
   474	    if (sample.frame.timestamp <= targetTimestampMs) {
   475	      best = sample;
   476	    }
   477	  }
   478	  return best ?? ordered[0];
   479	}
   480	
   481	function resolveLiveFrameSample(
   482	  record: TimelineLiveBindingRecord,
   483	  clip: ResolvedTimelineClip,
   484	  fps: number,
   485	  liveDataRegistry: LiveDataRegistry,
   486	): LiveSample | undefined {
   487	  const live = createClipRendererLiveProps([record], liveDataRegistry);
   488	  const sourceId = record.binding.sourceId;
   489	  const channelId = record.binding.channelId;
   490	  const sampling = record.binding.sampling;
   491	
   492	  if (sampling?.mode === 'sequence') {
   493	    return live.readSampleAt(sourceId, sampling.frameOffset ?? 0, channelId);
   494	  }
   495	
   496	  if (sampling?.mode === 'frame') {
   497	    const targetFrame = sampling.frameOffset ?? secondsToFrames(clip.at, fps);
   498	    return live.readSamples(sourceId, channelId).find((sample) => sampleFrameIndex(sample) === targetFrame)
   499	      ?? live.readSampleAt(sourceId, targetFrame, channelId);
   500	  }
   501	
   502	  if (sampling?.mode === 'time') {
   503	    const targetTimestampMs = (clip.at * 1000) + (sampling.timeOffsetMs ?? 0);
   504	    return resolveTimeSample(live.readSamples(sourceId, channelId), targetTimestampMs);
   505	  }
   506	
   507	  return live.readLatestSample(sourceId, channelId);
   508	}
   509	
   510	function resolveLiveFrameReadResult(
   511	  records: readonly TimelineLiveBindingRecord[],
   512	  clip: ResolvedTimelineClip,
   513	  fps: number,
   514	  liveDataRegistry: LiveDataRegistry | undefined,
   515	): LiveFrameReadResult {
   516	  const record = records[0];
   517	  if (!record) {
   518	    return { kind: 'placeholder', state: 'missing' };
   519	  }
   520	
   521	  const source = liveDataRegistry?.getSource(record.binding.sourceId);
   522	  if (record.status === 'malformed') return { kind: 'placeholder', state: 'malformed' };
   523	  if (record.status === 'missing') return { kind: 'placeholder', state: 'missing' };
   524	  if (record.status === 'orphaned') return { kind: 'placeholder', state: 'orphaned' };
   525	  if (record.status === 'disposed') return { kind: 'placeholder', state: 'disposed' };
   526	  if (record.status === 'partiallyBaked') {
   527	    return { kind: 'placeholder', state: 'partiallyBaked', progress: bindingProgress(record.binding) };
   528	  }
   529	
   530	  if (!liveDataRegistry || record.status !== 'active') {
   531	    if (source?.permission?.state === 'prompt') {
   532	      return { kind: 'placeholder', state: 'permission-pending', progress: bindingProgress(record.binding) };
   533	    }
   534	    if (source?.status === 'error' || source?.permission?.state === 'denied' || source?.permission?.state === 'unavailable') {
   535	      return { kind: 'placeholder', state: 'error', detail: source.diagnostics[0]?.message };
   536	    }
   537	    return { kind: 'placeholder', state: 'inactive', progress: bindingProgress(record.binding) };
   538	  }
   539	
   540	  if (source?.status === 'error') {
   541	    return { kind: 'placeholder', state: 'error', detail: source.diagnostics[0]?.message };
   542	  }
   543	
   544	  const sample = resolveLiveFrameSample(record, clip, fps, liveDataRegistry);
   545	  if (!sample) {
   546	    return { kind: 'placeholder', state: 'pending', progress: bindingProgress(record.binding) };
   547	  }
   548	
   549	  const state = sampleFrameState(sample);
   550	  const progress = sampleProgress(sample) ?? bindingProgress(record.binding);
   551	  if (state === 'cancelled') return { kind: 'placeholder', state: 'cancelled', progress };
   552	  if (state === 'error') return { kind: 'placeholder', state: 'error', progress };
   553	
   554	  const src = sampleFrameSrc(sample);
   555	  if (!src) {
   556	    return {
   557	      kind: 'placeholder',
   558	      state: state === 'refining' ? 'refining' : 'pending',
   559	      progress,
   560	    };
   561	  }
   562	
   563	  return {
   564	    kind: 'frame',
   565	    sample,
   566	    src,
   567	    state: state ?? 'ready',
   568	    progress,
   569	  };
   570	}
   571	
   572	function createClipRendererLiveProps(
   573	  records: readonly TimelineLiveBindingRecord[],
   574	  liveDataRegistry: LiveDataRegistry | undefined,
   575	): ClipRendererLiveProps {
   576	  const rendererBindings = Object.freeze(records.map(toRendererLiveBinding));
   577	  const diagnostics = Object.freeze(rendererBindings.flatMap((binding) => binding.diagnostics));
   578	  const activeRecords = records.filter((record) => record.status === 'active');
   579	
   580	  const isActiveSourceBinding = (sourceId: string): boolean => (
   581	    activeRecords.some((record) => record.binding.sourceId === sourceId)
   582	  );
   583	
   584	  const resolveChannelId = (sourceId: string, channelId?: string): LiveChannelDescriptor | undefined => {
   585	    if (!liveDataRegistry || !isActiveSourceBinding(sourceId)) return undefined;
   586	    if (channelId) {
   587	      const channel = liveDataRegistry.getChannelMetadata(channelId as LiveChannelDescriptor);
   588	      return channel?.sourceId === sourceId ? channel.channelId : undefined;
   589	    }
   590	
   591	    const boundChannelId = activeRecords.find((record) => (
   592	      record.binding.sourceId === sourceId && typeof record.binding.channelId === 'string'
   593	    ))?.binding.channelId;
   594	    if (boundChannelId) {
   595	      const channel = liveDataRegistry.getChannelMetadata(boundChannelId as LiveChannelDescriptor);
   596	      if (channel?.sourceId === sourceId) return channel.channelId;
   597	    }
   598	
   599	    return liveDataRegistry.getSnapshot().channels.find((channel) => channel.sourceId === sourceId)?.channelId;
   600	  };
   601	
   602	  const getSource = (sourceId: string): LiveSource | undefined => {
   603	    if (!liveDataRegistry || !isActiveSourceBinding(sourceId)) return undefined;
   604	    return liveDataRegistry.getSource(sourceId);
   605	  };
   606	
   607	  const getChannelMetadata = (
   608	    sourceId: string,
   609	    channelId?: string,
   610	  ): LiveChannelMetadata | undefined => {
   611	    const resolvedChannelId = resolveChannelId(sourceId, channelId);
   612	    return resolvedChannelId ? liveDataRegistry?.getChannelMetadata(resolvedChannelId) : undefined;
   613	  };
   614	
   615	  const readLatestSample = (sourceId: string, channelId?: string): LiveSample | undefined => {
   616	    const resolvedChannelId = resolveChannelId(sourceId, channelId);
   617	    return resolvedChannelId ? liveDataRegistry?.getLatestSample(resolvedChannelId) : undefined;
   618	  };
   619	
   620	  const readSampleAt = (

exec
/bin/zsh -lc "nl -ba src/tools/video-editor/hooks/useRenderState.ts | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
     1	import { useCallback, useContext, useEffect, useMemo, useState } from 'react';
     2	import { useClientRender } from '@/tools/video-editor/hooks/useClientRender.ts';
     3	import type { CompositionMetadata } from '@/tools/video-editor/hooks/useDerivedTimeline.ts';
     4	import type { VideoEditorExporter } from '@/tools/video-editor/lib/browser-runtime.ts';
     5	import type { ResolvedTimelineConfig } from '@/tools/video-editor/types/index.ts';
     6	import type { ExtensionRuntime, VideoEditorOutputFormatDescriptor } from '@/tools/video-editor/runtime/extensionSurface.ts';
     7	import {
     8	  createCompileOnlyOutputFormatRegistry,
     9	  executeCompileOnlyOutput,
    10	  type CompileOnlyOutputFormatEntry,
    11	  type CompileOnlyOutputFormatRegistry,
    12	} from '@/tools/video-editor/runtime/outputFormatRegistry.ts';
    13	import { useEffectRegistrySnapshot } from '@/tools/video-editor/effects/registry/EffectRegistryContext.tsx';
    14	import { useTransitionRegistrySnapshot } from '@/tools/video-editor/transitions/registry/TransitionRegistryContext.tsx';
    15	import { useClipTypeRegistrySnapshot } from '@/tools/video-editor/clip-types/ClipTypeRegistryContext.tsx';
    16	import {
    17	  collectBuiltInKnownIds,
    18	  collectExtensionDeclaredIds,
    19	  hasTimelineShaderMetadata,
    20	  scanExportConfig,
    21	} from '@/tools/video-editor/runtime/exportGuard.ts';
    22	import {
    23	  planRender,
    24	  type RenderPlannerResult,
    25	} from '@/tools/video-editor/runtime/renderPlanner.ts';
    26	import { DataProviderContext } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
    27	import { syncPlannerDiagnosticsToCollection } from '@/tools/video-editor/runtime/diagnosticCollectionSync.ts';
    28	import type {
    29	  CapabilityFinding,
    30	  Diagnostic,
    31	  ExportDiagnostic,
    32	  RenderBlockerReason,
    33	} from '@reigh/editor-sdk';
    34	
    35	export type RenderStatus = 'idle' | 'rendering' | 'done' | 'error';
    36	
    37	/** M6: Export status for compile-only and render-dependent export operations. */
    38	export type ExportStatus = 'idle' | 'exporting' | 'done' | 'error';
    39	
    40	type RenderProgress = { current: number; total: number; percent: number; phase: string } | null;
    41	
    42	const CLIENT_CLIP_TYPES = new Set(['media', 'text', 'effect-layer', 'hold']);
    43	
    44	function getFastRenderRouteDecision(resolvedConfig: ResolvedTimelineConfig | null) {
    45	  const clips = resolvedConfig?.clips ?? [];
    46	
    47	  if (clips.length === 0) {
    48	    return { route: 'browser-remotion' as const, reason: 'no_clips' };
    49	  }
    50	
    51	  let hasGeneratedModuleClip = false;
    52	  let hasOtherClip = false;
    53	  for (const clip of clips) {
    54	    if (clip.generation?.sequence_lane === 'remotion_module') {
    55	      if (!clip.generation?.artifact_id) {
    56	        return { route: 'preview-only' as const, reason: 'remotion_module_missing_artifact' };
    57	      }
    58	      hasGeneratedModuleClip = true;
    59	      continue;
    60	    }
    61	
    62	    if (!clip.clipType || CLIENT_CLIP_TYPES.has(clip.clipType)) {
    63	      hasOtherClip = true;
    64	      continue;
    65	    }
    66	
    67	    return null;
    68	  }
    69	
    70	  if (hasGeneratedModuleClip) {
    71	    return {
    72	      route: 'worker-banodoco' as const,
    73	      reason: hasOtherClip ? 'mixed_generated_module_and_other' : 'generated_remotion_module',
    74	    };
    75	  }
    76	
    77	  return { route: 'browser-remotion' as const, reason: 'pure_native_clips' };
    78	}
    79	
    80	function isExtensionRuntimeEmpty(extRuntime: ExtensionRuntime | undefined): boolean {
    81	  if (!extRuntime) return true;
    82	  return extRuntime.extensions.length === 0 && extRuntime.inactiveReserved.length === 0;
    83	}
    84	
    85	function buildExtensionContributions(extRuntime: ExtensionRuntime) {
    86	  const allContributions: import('@reigh/editor-sdk').ExtensionContribution[] = [];
    87	  for (const ext of extRuntime.extensions) {
    88	    const contribs = ext.manifest.contributions ?? [];
    89	    for (const c of contribs) {
    90	      allContributions.push(c);
    91	    }
    92	  }
    93	  return allContributions;
    94	}
    95	
    96	/**
    97	 * Create a concise render log line from export guard diagnostics.
    98	 * Emits a single summary line plus per-diagnostic error lines for blocking issues.
    99	 */
   100	function formatExportGuardLog(
   101	  guardResult: ReturnType<typeof scanExportConfig>,
   102	): string {
   103	  const lines: string[] = [];
   104	
   105	  const totalDiags = guardResult.diagnostics.length;
   106	  const errorCount = guardResult.diagnostics.filter((d) => d.severity === 'error').length;
   107	  const warningCount = guardResult.diagnostics.filter((d) => d.severity === 'warning').length;
   108	  const infoCount = totalDiags - errorCount - warningCount;
   109	
   110	  if (totalDiags === 0) {
   111	    lines.push('Export guard: no issues found.');
   112	    return lines.join('\n');
   113	  }
   114	
   115	  lines.push(
   116	    `Export guard: ${totalDiags} issue(s) — ${errorCount} error(s), ${warningCount} warning(s), ${infoCount} info(s).`,
   117	  );
   118	
   119	  // Show blocking errors first, naming the effect/transition and route when available
   120	  for (const diag of guardResult.diagnostics) {
   121	    if (diag.severity === 'error') {
   122	      const name = diag.detail?.effectType
   123	        ? ` effect "${diag.detail.effectType}"`
   124	        : diag.detail?.transitionType
   125	          ? ` transition "${diag.detail.transitionType}"`
   126	          : diag.detail?.clipType
   127	            ? ` clip type "${diag.detail.clipType}"`
   128	            : diag.detail?.shaderId
   129	              ? ` shader "${diag.detail.shaderId}"`
   130	            : '';
   131	      const route = diag.detail?.renderRoute ? ` (${diag.detail.renderRoute})` : '';
   132	      lines.push(`  [${diag.code}]${name}${route}: ${diag.message}`);
   133	    }
   134	  }
   135	
   136	  // Then warnings — also name effects/transitions/clip types
   137	  for (const diag of guardResult.diagnostics) {
   138	    if (diag.severity === 'warning') {
   139	      const name = diag.detail?.effectType
   140	        ? ` effect "${diag.detail.effectType}"`
   141	        : diag.detail?.transitionType
   142	          ? ` transition "${diag.detail.transitionType}"`
   143	          : diag.detail?.clipType
   144	            ? ` clip type "${diag.detail.clipType}"`
   145	            : diag.detail?.shaderId
   146	              ? ` shader "${diag.detail.shaderId}"`
   147	            : '';
   148	      const route = diag.detail?.renderRoute ? ` (${diag.detail.renderRoute})` : '';
   149	      lines.push(`  [${diag.code}]${name}${route}: ${diag.message}`);
   150	    }
   151	  }
   152	
   153	  // Append per-route blocker summaries from findings (when available)
   154	  const blockerFindings = (guardResult.findings ?? []).filter((f) => f.severity === 'error');
   155	  if (blockerFindings.length > 0) {
   156	    lines.push('');
   157	    lines.push('Route blockers:');
   158	    for (const finding of blockerFindings) {
   159	      const name = finding.detail?.effectType
   160	        ? `"${finding.detail.effectType}"`
   161	        : finding.detail?.transitionType
   162	          ? `"${finding.detail.transitionType}"`
   163	          : finding.detail?.shaderId
   164	            ? `"${finding.detail.shaderId}"`
   165	          : 'unknown';
   166	      const route = finding.route ?? 'unknown-route';
   167	      lines.push(`  ${name} blocked on ${route}: ${finding.message}`);
   168	    }
   169	  }
   170	
   171	  return lines.join('\n');
   172	}
   173	
   174	function exportDiagnosticId(diagnostic: ReturnType<typeof scanExportConfig>['diagnostics'][number], index: number): string {
   175	  const detail = diagnostic.detail ?? {};
   176	  return [
   177	    'export-guard',
   178	    diagnostic.code,
   179	    diagnostic.extensionId ?? 'host',
   180	    diagnostic.contributionId ?? 'timeline',
   181	    detail.clipId ?? 'no-clip',
   182	    detail.effectType ?? detail.transitionType ?? detail.clipType ?? detail.shaderId ?? index,
   183	  ].join(':');
   184	}
   185	
   186	function blockerReasonForExportDiagnostic(diagnostic: ExportDiagnostic): RenderBlockerReason {
   187	  if (diagnostic.code.includes('unknown') || diagnostic.code.includes('missing')) {
   188	    return 'missing-contribution';
   189	  }
   190	  if (diagnostic.code.includes('inactive')) {
   191	    return 'inactive-extension';
   192	  }
   193	  if (diagnostic.code.includes('live-binding')) {
   194	    return 'live-unbaked';
   195	  }
   196	  if (diagnostic.code.includes('shader')) {
   197	    return 'missing-material';
   198	  }
   199	  return 'route-unsupported';
   200	}
   201	
   202	function exportDiagnosticToPlannerFinding(diagnostic: ExportDiagnostic, index: number): CapabilityFinding {
   203	  const route = diagnostic.detail?.renderRoute === 'worker-export' || diagnostic.detail?.renderRoute === 'preview'
   204	    ? diagnostic.detail.renderRoute
   205	    : 'browser-export';
   206	  const reason = diagnostic.severity === 'error'
   207	    ? blockerReasonForExportDiagnostic(diagnostic)
   208	    : undefined;
   209	
   210	  return {
   211	    id: exportDiagnosticId(diagnostic, index),
   212	    severity: diagnostic.severity,
   213	    route,
   214	    ...(reason ? { reason } : {}),
   215	    message: diagnostic.message,
   216	    ...(diagnostic.extensionId ? { extensionId: diagnostic.extensionId } : {}),
   217	    ...(diagnostic.contributionId ? { contributionId: diagnostic.contributionId } : {}),
   218	    detail: {
   219	      ...(diagnostic.detail ?? {}),
   220	      source: 'export-guard-compat',
   221	      code: diagnostic.code,
   222	    },
   223	  };
   224	}
   225	
   226	function planFromExportGuardResult(
   227	  guardResult: ReturnType<typeof scanExportConfig>,
   228	): RenderPlannerResult {
   229	  const diagnostics: CapabilityFinding[] = [
   230	    ...(guardResult.findings ?? []),
   231	    ...(guardResult.blockers ?? []),
   232	    ...guardResult.diagnostics.map(exportDiagnosticToPlannerFinding),
   233	  ];
   234	  return planRender({ diagnostics });
   235	}
   236	
   237	function outputFormatsForPlanning(extensionRuntime: ExtensionRuntime | undefined): readonly VideoEditorOutputFormatDescriptor[] {
   238	  const outputFormats = extensionRuntime?.outputFormats
   239	    ?? extensionRuntime?.config?.outputFormats
   240	    ?? [];
   241	  return outputFormats.map((format) => ({
   242	    ...format,
   243	    availableRoutes: format.availableRoutes ?? [],
   244	    routeRequirements: format.routeRequirements ?? [],
   245	    processRequirements: format.processRequirements ?? [],
   246	    blockers: format.blockers ?? [],
   247	    nextActions: format.nextActions ?? [],
   248	    sidecars: format.sidecars ?? [],
   249	  }));
   250	}
   251	
   252	function toCollectionDiagnostic(
   253	  diagnostic: ReturnType<typeof scanExportConfig>['diagnostics'][number],
   254	  index: number,
   255	): Diagnostic {
   256	  return {
   257	    id: exportDiagnosticId(diagnostic, index),
   258	    severity: diagnostic.severity,
   259	    code: diagnostic.code,
   260	    message: diagnostic.message,

exec
/bin/zsh -lc "nl -ba src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts | sed -n '1,180p'; nl -ba src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts | sed -n '472,760p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
     1	/**
     2	 * M12: Planner-public-contract-only tests for TimelineReader inspection surface.
     3	 *
     4	 * These tests prove that planner code can consume TimelineSnapshot,
     5	 * TimelineReader, and SDK requirement types without importing provider
     6	 * stores, raw timeline rows, or mutation APIs.
     7	 *
     8	 * @publicContract
     9	 */
    10	
    11	import { describe, expect, it } from 'vitest';
    12	import { createTimelineReader, getCapabilityRequirements } from '@/tools/video-editor/lib/timeline-reader';
    13	import type {
    14	  TimelineSnapshot,
    15	  TimelineClipSummary,
    16	  TimelineEffectSummary,
    17	  TimelineTransitionSummary,
    18	  TimelineLiveBindingSummary,
    19	  TimelineMaterialRefSummary,
    20	  TimelineSourceRefSummary,
    21	  TimelineRenderGroupSummary,
    22	  TimelineOutputMetadata,
    23	  CapabilityRequirement,
    24	  CapabilityVersion,
    25	  CapabilitySourceRef,
    26	  RouteFitMetadata,
    27	  IntegrationCapabilities,
    28	  DeterminismStatus,
    29	  RenderRoute,
    30	  RenderBlockerReason,
    31	  CapabilityFinding,
    32	} from '@/sdk/index';
    33	import { buildTimelineData } from '@/tools/video-editor/lib/timeline-data';
    34	import type { TimelineConfig, AssetRegistry } from '@/tools/video-editor/types/index';
    35	
    36	// ---------------------------------------------------------------------------
    37	// Helpers
    38	// ---------------------------------------------------------------------------
    39	
    40	const emptyRegistry: AssetRegistry = { assets: {} };
    41	
    42	function makeBaseConfig(): TimelineConfig {
    43	  return {
    44	    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    45	    tracks: [
    46	      { id: 'V1', kind: 'visual', label: 'Visual 1' },
    47	      { id: 'A1', kind: 'audio', label: 'Audio 1', muted: true },
    48	    ],
    49	    clips: [
    50	      {
    51	        id: 'clip-1',
    52	        at: 0,
    53	        track: 'V1',
    54	        clipType: 'media',
    55	        asset: 'asset-1',
    56	        from: 0,
    57	        to: 2,
    58	        speed: 1,
    59	      },
    60	    ],
    61	  };
    62	}
    63	
    64	// ---------------------------------------------------------------------------
    65	// Boundary: planner imports only public types
    66	// ---------------------------------------------------------------------------
    67	
    68	describe('M12 planner contract boundary', () => {
    69	  it('can import TimelineSnapshot without provider stores', () => {
    70	    // This test proves the import compiles.  If this file compiles,
    71	    // the planner can access TimelineSnapshot without raw rows.
    72	    const snap: TimelineSnapshot = {
    73	      projectId: null,
    74	      baseVersion: 1,
    75	      currentVersion: 1,
    76	      extensionRequirements: [],
    77	      clips: [],
    78	      tracks: [],
    79	      assetKeys: [],
    80	      app: {},
    81	    };
    82	    expect(snap).toBeDefined();
    83	  });
    84	
    85	  it('can import CapabilityRequirement without provider stores', () => {
    86	    const req: CapabilityRequirement = {
    87	      id: 'test.req.1',
    88	      sourceRef: { source: 'built-in' },
    89	      route: 'browser-export',
    90	      requiredCapabilities: ['browser-export'],
    91	      determinism: 'deterministic',
    92	    };
    93	    expect(req.id).toBe('test.req.1');
    94	  });
    95	
    96	  it('can import IntegrationCapabilities without provider stores', () => {
    97	    const ic: IntegrationCapabilities = {
    98	      extensionId: 'com.test.ext',
    99	      routes: ['browser-export'],
   100	      determinism: 'deterministic',
   101	      capabilityRequirements: [],
   102	      sourceRefs: [],
   103	      fullySupported: true,
   104	      anyBlocked: false,
   105	    };
   106	    expect(ic.fullySupported).toBe(true);
   107	  });
   108	
   109	  it('can import all M12 summary types without provider stores', () => {
   110	    const effect: TimelineEffectSummary = {
   111	      id: 'e1',
   112	      clipId: 'c1',
   113	      effectType: 'fade_in',
   114	    };
   115	    const transition: TimelineTransitionSummary = {
   116	      id: 't1',
   117	      clipId: 'c1',
   118	      transitionType: 'crossfade',
   119	      duration: 1,
   120	    };
   121	    const liveBinding: TimelineLiveBindingSummary = {
   122	      bindingId: 'lb1',
   123	      clipId: 'c1',
   124	      sourceId: 'src1',
   125	      sourceKind: 'webcam',
   126	    };
   127	    const materialRef: TimelineMaterialRefSummary = {
   128	      id: 'm1',
   129	      clipId: 'c1',
   130	      assetKey: 'asset-1',
   131	    };
   132	    const sourceRef: TimelineSourceRefSummary = {
   133	      id: 's1',
   134	      clipId: 'c1',
   135	      sourceKind: 'generation',
   136	      generationId: 'gen-1',
   137	      determinism: 'process-dependent',
   138	    };
   139	    const renderGroup: TimelineRenderGroupSummary = {
   140	      id: 'rg1',
   141	      clipIds: ['c1', 'c2'],
   142	    };
   143	    const outputMeta: TimelineOutputMetadata = {
   144	      resolution: '1920x1080',
   145	      fps: 30,
   146	      file: 'out.mp4',
   147	    };
   148	
   149	    expect(effect.effectType).toBe('fade_in');
   150	    expect(transition.duration).toBe(1);
   151	    expect(liveBinding.sourceKind).toBe('webcam');
   152	    expect(materialRef.assetKey).toBe('asset-1');
   153	    expect(sourceRef.generationId).toBe('gen-1');
   154	    expect(renderGroup.clipIds).toEqual(['c1', 'c2']);
   155	    expect(outputMeta.fps).toBe(30);
   156	  });
   157	});
   158	
   159	// ---------------------------------------------------------------------------
   160	// M12: Snapshot carries planner inspection data
   161	// ---------------------------------------------------------------------------
   162	
   163	describe('M12 snapshot inspection fields', () => {
   164	  it('snapshot includes outputMetadata from config', async () => {
   165	    const config = makeBaseConfig();
   166	    const data = await buildTimelineData(config, emptyRegistry);
   167	    const reader = createTimelineReader({ data });
   168	    const snap = reader.snapshot();
   169	
   170	    expect(snap.outputMetadata).toBeDefined();
   171	    expect(snap.outputMetadata!.resolution).toBe('1920x1080');
   172	    expect(snap.outputMetadata!.fps).toBe(30);
   173	    expect(snap.outputMetadata!.file).toBe('out.mp4');
   174	  });
   175	
   176	  it('snapshot includes effects on clips when effects are present', async () => {
   177	    const config: TimelineConfig = {
   178	      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
   179	      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
   180	      clips: [
   472	// M12: getCapabilityRequirements — provider-free inspection
   473	// ---------------------------------------------------------------------------
   474	
   475	describe('M12 getCapabilityRequirements', () => {
   476	  it('returns empty array for snapshot with no clips', async () => {
   477	    const config: TimelineConfig = {
   478	      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
   479	      tracks: [],
   480	      clips: [],
   481	    };
   482	    const data = await buildTimelineData(config, emptyRegistry);
   483	    const reader = createTimelineReader({ data });
   484	    const snap = reader.snapshot();
   485	
   486	    const reqs = getCapabilityRequirements(snap);
   487	    expect(reqs).toEqual([]);
   488	  });
   489	
   490	  it('emits clip-type requirements for each unique clip type', async () => {
   491	    const config: TimelineConfig = {
   492	      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
   493	      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
   494	      clips: [
   495	        { id: 'c1', at: 0, track: 'V1', clipType: 'media', hold: 2 },
   496	        { id: 'c2', at: 2, track: 'V1', clipType: 'media', hold: 2 },
   497	        { id: 'c3', at: 4, track: 'V1', clipType: 'hold', hold: 2 },
   498	      ],
   499	    };
   500	    const data = await buildTimelineData(config, emptyRegistry);
   501	    const reader = createTimelineReader({ data });
   502	    const snap = reader.snapshot();
   503	
   504	    const reqs = getCapabilityRequirements(snap);
   505	
   506	    // Should have 2 clip-type requirements (media, hold)
   507	    const clipTypeReqs = reqs.filter((r) => r.id.startsWith('snapshot.clipType.'));
   508	    expect(clipTypeReqs).toHaveLength(2);
   509	
   510	    // Both should be built-in (no managedBy)
   511	    for (const req of clipTypeReqs) {
   512	      expect(req.sourceRef.source).toBe('built-in');
   513	      expect(req.determinism).toBe('deterministic');
   514	    }
   515	  });
   516	
   517	  it('emits effect requirements when clips have effects', async () => {
   518	    const config: TimelineConfig = {
   519	      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
   520	      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
   521	      clips: [
   522	        {
   523	          id: 'c1',
   524	          at: 0,
   525	          track: 'V1',
   526	          clipType: 'media',
   527	          hold: 2,
   528	          effects: [{ type: 'fade_in' }],
   529	        },
   530	      ],
   531	    };
   532	    const data = await buildTimelineData(config, emptyRegistry);
   533	    const reader = createTimelineReader({ data });
   534	    const snap = reader.snapshot();
   535	
   536	    const reqs = getCapabilityRequirements(snap);
   537	
   538	    const effectReqs = reqs.filter((r) => r.id.startsWith('snapshot.effect.'));
   539	    expect(effectReqs.length).toBeGreaterThanOrEqual(1);
   540	
   541	    const fadeReq = effectReqs.find((r) =>
   542	      r.findings?.some((f) => f.message.includes('fade_in')),
   543	    );
   544	    expect(fadeReq).toBeDefined();
   545	    expect(fadeReq!.sourceRef.source).toBe('built-in');
   546	  });
   547	
   548	  it('emits transition requirements when clips have transitions', async () => {
   549	    const config: TimelineConfig = {
   550	      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
   551	      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
   552	      clips: [
   553	        {
   554	          id: 'c1',
   555	          at: 0,
   556	          track: 'V1',
   557	          clipType: 'media',
   558	          hold: 2,
   559	          transition: { type: 'crossfade', duration: 1 },
   560	        },
   561	      ],
   562	    };
   563	    const data = await buildTimelineData(config, emptyRegistry);
   564	    const reader = createTimelineReader({ data });
   565	    const snap = reader.snapshot();
   566	
   567	    const reqs = getCapabilityRequirements(snap);
   568	
   569	    const transitionReqs = reqs.filter((r) =>
   570	      r.id.startsWith('snapshot.transition.'),
   571	    );
   572	    expect(transitionReqs.length).toBeGreaterThanOrEqual(1);
   573	    expect(transitionReqs[0].sourceRef.source).toBe('built-in');
   574	  });
   575	
   576	  it('emits live-binding requirements when live bindings are present', async () => {
   577	    const config: TimelineConfig = {
   578	      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
   579	      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
   580	      clips: [
   581	        {
   582	          id: 'c1',
   583	          at: 0,
   584	          track: 'V1',
   585	          clipType: 'media',
   586	          hold: 2,
   587	          app: {
   588	            liveBindings: [
   589	              {
   590	                bindingId: 'lb-1',
   591	                sourceId: 'webcam-1',
   592	                sourceKind: 'webcam',
   593	                resolutionStatus: 'active',
   594	              },
   595	            ],
   596	          },
   597	        },
   598	      ],
   599	    };
   600	    const data = await buildTimelineData(config, emptyRegistry);
   601	    const reader = createTimelineReader({ data });
   602	    const snap = reader.snapshot();
   603	
   604	    const reqs = getCapabilityRequirements(snap);
   605	
   606	    const bindingReqs = reqs.filter((r) =>
   607	      r.id.startsWith('snapshot.liveBinding.'),
   608	    );
   609	    expect(bindingReqs.length).toBeGreaterThanOrEqual(1);
   610	    expect(bindingReqs[0].determinism).toBe('live-unbaked');
   611	    expect(bindingReqs[0].sourceRef.source).toBe('provider');
   612	    // Active bindings are blocking
   613	    expect(bindingReqs[0].blocking).toBe(true);
   614	  });
   615	
   616	  it('resolved live bindings are not blocking', async () => {
   617	    const config: TimelineConfig = {
   618	      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
   619	      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
   620	      clips: [
   621	        {
   622	          id: 'c1',
   623	          at: 0,
   624	          track: 'V1',
   625	          clipType: 'media',
   626	          hold: 2,
   627	          app: {
   628	            liveBindings: [
   629	              {
   630	                bindingId: 'lb-resolved',
   631	                sourceId: 'webcam-1',
   632	                sourceKind: 'webcam',
   633	                resolutionStatus: 'resolved',
   634	              },
   635	            ],
   636	          },
   637	        },
   638	      ],
   639	    };
   640	    const data = await buildTimelineData(config, emptyRegistry);
   641	    const reader = createTimelineReader({ data });
   642	    const snap = reader.snapshot();
   643	
   644	    const reqs = getCapabilityRequirements(snap);
   645	
   646	    const bindingReq = reqs.find((r) =>
   647	      r.id.startsWith('snapshot.liveBinding.'),
   648	    );
   649	    expect(bindingReq).toBeDefined();
   650	    expect(bindingReq!.blocking).toBe(false);
   651	    expect(bindingReq!.routeFit?.fit).toBe('supported');
   652	  });
   653	
   654	  it('emits material-ref requirements when material refs exist', async () => {
   655	    const config: TimelineConfig = {
   656	      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
   657	      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
   658	      clips: [
   659	        {
   660	          id: 'c1',
   661	          at: 0,
   662	          track: 'V1',
   663	          clipType: 'media',
   664	          asset: 'my-asset',
   665	          hold: 2,
   666	        },
   667	      ],
   668	    };
   669	    const data = await buildTimelineData(config, emptyRegistry);
   670	    const reader = createTimelineReader({ data });
   671	    const snap = reader.snapshot();
   672	
   673	    const reqs = getCapabilityRequirements(snap);
   674	
   675	    const materialReqs = reqs.filter((r) =>
   676	      r.id.startsWith('snapshot.materialRef.'),
   677	    );
   678	    expect(materialReqs.length).toBeGreaterThanOrEqual(1);
   679	    expect(materialReqs[0].sourceRef.source).toBe('registry');
   680	  });
   681	
   682	  it('emits source-ref requirements when source refs exist', async () => {
   683	    const config: TimelineConfig = {
   684	      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
   685	      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
   686	      clips: [
   687	        {
   688	          id: 'c-source',
   689	          at: 0,
   690	          track: 'V1',
   691	          clipType: 'media',
   692	          generation: { id: 'gen-1', extensionId: 'com.generator.ext' },
   693	          hold: 2,
   694	        },
   695	      ],
   696	    };
   697	    const data = await buildTimelineData(config, emptyRegistry);
   698	    const reader = createTimelineReader({ data });
   699	    const snap = reader.snapshot();
   700	
   701	    const reqs = getCapabilityRequirements(snap);
   702	
   703	    const sourceReq = reqs.find((r) =>
   704	      r.id.startsWith('snapshot.sourceRef.'),
   705	    );
   706	    expect(sourceReq).toBeDefined();
   707	    expect(sourceReq!.sourceRef.source).toBe('extension');
   708	    expect(sourceReq!.sourceRef.extensionId).toBe('com.generator.ext');
   709	    expect(sourceReq!.determinism).toBe('process-dependent');
   710	    expect(sourceReq!.blocking).toBe(true);
   711	  });
   712	
   713	  it('managingExtensionIds from clip.managedBy influences clip-type determinism', async () => {
   714	    const config: TimelineConfig = {
   715	      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
   716	      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
   717	      clips: [
   718	        {
   719	          id: 'c-managed',
   720	          at: 0,
   721	          track: 'V1',
   722	          clipType: 'custom-clip',
   723	          hold: 2,
   724	          app: { managedBy: 'com.example.ext' },
   725	        },
   726	      ],
   727	    };
   728	    const data = await buildTimelineData(config, emptyRegistry);
   729	    const reader = createTimelineReader({
   730	      data,
   731	      extensionRequirements: [
   732	        {
   733	          extensionId: 'com.example.ext',
   734	          versionRange: '>=1.0.0',
   735	          posture: 'required',
   736	        },
   737	      ],
   738	    });
   739	    const snap = reader.snapshot();
   740	
   741	    const reqs = getCapabilityRequirements(snap);
   742	
   743	    const clipTypeReq = reqs.find((r) => r.id.startsWith('snapshot.clipType.'));
   744	    expect(clipTypeReq).toBeDefined();
   745	    expect(clipTypeReq!.sourceRef.source).toBe('extension');
   746	    expect(clipTypeReq!.sourceRef.extensionId).toBe('com.example.ext');
   747	    // Managed clips are preview-only until explicitly declared
   748	    expect(clipTypeReq!.determinism).toBe('preview-only');
   749	  });
   750	
   751	  it('does not import provider stores or mutation APIs', () => {
   752	    // Structural check: this test file only imports from @/sdk/index
   753	    // and timeline-reader.  It does NOT import DataProvider, useTimelineCommit,
   754	    // TimelineOps, or any mutation APIs.
   755	    //
   756	    // If this file compiles and runs without crashing, the boundary holds.
   757	    expect(typeof createTimelineReader).toBe('function');
   758	  });
   759	});

exec
/bin/zsh -lc "nl -ba .megaplan/initiatives/reigh-extension-composition-spine-epic/NORTHSTAR.md | sed -n '1,220p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
     1	# North Star: Reigh Extension Composition Spine
     2	
     3	## What we are building
     4	
     5	A unified composition spine for Reigh extensions. Clips, shaders, effects, transitions, live data, agent-produced materials, and output formats all participate through a host-projected `CompositionGraph` of contribution refs, typed target paths, graph edges, route requirements, and artifact manifests.
     6	
     7	## Why it matters
     8	
     9	Without this spine, every new extension family invents its own identity, validation, and mutation path. The spine makes extension contributions first-class, auditable, and composable while keeping the host in control of projection, validation, and execution.
    10	
    11	## Immutable constraints
    12	
    13	- Extensions and processes never mutate raw timeline internals directly.
    14	- The graph is the authority for graph-authoritative fact families; legacy fields are compatibility inputs only.
    15	- V1 target paths are limited to clip/effect/transition params and shader uniforms.
    16	- Live or nondeterministic inputs must bake or promote to durable materials/artifacts/captures before authoritative export.
    17	- Trusted process runtime and output-format sidecars are real, but they stay namespaced outside the V1 composition SDK.
    18	- No sandbox, marketplace, headless renderer, WebGPU, arbitrary material graphs, shader stacks, FBO chains, or generic texture routing in this epic.
    19	
    20	## Success in one sentence
    21	
    22	Users can compose, preview, bake, repair, and export video projects using contributions from multiple extensions, and extension authors can declare portable SDK contracts without leaking into host internals.

exec
/bin/zsh -lc "nl -ba .megaplan/initiatives/reigh-extension-composition-spine-epic/prep.md | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
     1	# Megaplan Prep: Reigh Extension Composition Spine
     2	
     3	Date: 2026-07-01
     4	Workspace: `/Users/peteromalley/Documents/.megaplan-worktrees/reigh-pristine-sdk-boundary-run`
     5	Source plan: `/Users/peteromalley/Documents/.megaplan-worktrees/reigh-pristine-sdk-boundary-run/.megaplan/briefs/reigh-extension-composition-spine-plan-elegant-v8.md`
     6	
     7	## Outcome
     8	
     9	Build the Reigh extension composition spine: shared contribution identity, typed target paths, fact-scoped graph authority, material/artifact contracts, process-family runtime contracts, and output-format route planning. The epic proves four composed examples: clip + shader + shader-uniform keyframes, effect + live data + bake, transition + agent-produced mask material, and output format + sidecar/process dependency with non-video artifact output.
    10	
    11	The V1 composition SDK remains small and data-only. Trusted process runtime and output-format sidecars are release-scope milestones after V1 graph authority is proven, not additions to the V1 composition SDK surface.
    12	
    13	## Scope Sizing
    14	
    15	This is larger than one sprint-sized megaplan. It contains multiple graph-authority transitions, public SDK contracts, planner/export invariants, runtime overlays, agent/live materialization paths, trusted process runtime, output-format route planning, browser acceptance, and governance gates. Treat it as an epic chain of sprint-sized megaplans.
    16	
    17	Recommended chain:
    18	
    19	1. **M0: Decisions, fixtures, and protocol v0** - freeze route model, ownership boundaries, deterministic-capture profiles, release examples, fixture matrices, and process protocol names before implementation.
    20	2. **M1a: Reference identity, patch vocabulary, and first validation rule** - add portable refs, scoped contribution identity, duplicate preservation, reserved patch ops, and shader-scope validation extraction.
    21	3. **M1b: Composition graph projection becomes shader/ref fact authority** - add graph contracts, resolver states, shader `consumes` projection, patch preview, and graph-first planner authority for shader/ref facts.
    22	4. **M2: Target paths, schema capability, keyframes, and live binding** - add target-path grammar, schema capability, `animates`/`binds-live`, and canonical target diagnostics.
    23	5. **M3a: Material status and planner matrix** - lock the five-status material model, status details, predicates, planner matrix, next actions, and provenance validation.
    24	6. **M3b: Live binding and deterministic capture** - bake live inputs to durable artifacts or deterministic captures and execute graph-owned keyframe operations for accepted live/bake paths.
    25	7. **M3c: Agent material promotion** - promote agent-produced masks/materials to durable `RenderMaterial`/`RenderArtifact` records and attach only resolved refs to existing slots.
    26	8. **M4: Clip type, shader, and shader-uniform keyframes** - execute shader assign/remove, integrate shader-uniform keyframes, introduce graph-projected `requires`, and prove the clip + shader example.
    27	9. **M5: Effects, transitions, live data, and agent mask material** - prove effect live binding and transition mask material consumption; finish the first three V1 composed examples.
    28	10. **M6a: Process runtime core** - add trusted process manager, JSON-RPC stdio protocol, lifecycle vocabulary, runtime overlays, route-scoped blockers, and result attachment without timeline mutation rights.
    29	11. **M6b: Process UX and canary** - add process dashboard/repair UI, `start-process` action mapping, canary coverage, and browser acceptance for process repair.
    30	12. **M7a: Output-format route planning** - add graph-backed output-format route planning, route artifacts, typed manifest profiles, route-scope symmetry, and multi-artifact completion records.
    31	13. **M7b: Output-format sidecar integration** - wire sidecar/process execution to output-format route planning, prove the fourth composed example, and harden docs/readiness/governance checks.
    32	
    33	## Locked Decisions
    34	
    35	- Cross-family composition is host-owned and data-only. Extensions declare descriptors, refs, schemas, and proposals; they do not mutate other families or raw timeline internals.
    36	- SDK contracts live behind `src/sdk/index.ts` and SDK modules own portable refs, target paths, graph contracts, material status/action strings, diagnostics, typed artifact/profile contracts, and patch vocabulary. Host runtime wiring stays under `src/tools/video-editor/**`.
    37	- `ExtensionRuntime` gains an additive contribution index. Existing family arrays remain source-compatible but stop being sufficient authority for a fact family after that family becomes graph-authoritative.
    38	- Graph authority is fact-scoped, not global. Legacy fields may be normalized into graph facts, but cannot drive new planner/export behavior or release examples after the owning milestone lands.
    39	- Contribution identity defaults to versionless lookup by `(extensionId, kind, contributionId)`. `version` and `compatibilityRange` constrain candidate selection before refs are persisted or accepted.
    40	- V1 executable target paths are limited to `clip-param`, `effect-param`, `transition-param`, and `shader-uniform`. `output`, `process`, `agent`, and `app` validate only through non-executable `extension-param` with `composition/unsupported-target-kind`.
    41	- Media-like nondeterministic inputs must resolve to `RenderMaterial` or `RenderArtifact` before authoritative export. Non-media live data may bake to deterministic captures, then target params or shader uniforms through normal target paths.
    42	- Material statuses remain `missing`, `pending`, `resolved`, `stale`, and `failed`, with narrow `detail.phase` and `detail.quality` taxonomy.
    43	- Planner next actions remain `select-route`, `materialize`, `bake`, `invoke-agent`, `open-settings`, `install-extension`, and `enable-extension` until M6 introduces process-family `start-process`.
    44	- Public graph edges remain small: `consumes`, `animates`, `binds-live`, and M4-owned `requires`. This epic does not add public `materializes`, `produces`, or `fallbacks` edge discriminants.
    45	- `requires` edge ownership belongs to M4. M3 may preserve declarative requirement payloads, but process repair is executable only in M6.
    46	- M2 owns target-path grammar and validation. M3b owns executable keyframe patch semantics for accepted live/bake paths. M4 owns shader assignment execution and shader-uniform render-path integration.
    47	- Process lifecycle, process task result states, and sidecar route vocabulary are process/output-format contracts introduced in M6/M7, not V1 composition SDK contracts.
    48	- Processes never mutate the timeline directly. Returned refs are recorded through `process.result.attach`, then consumed through graph-owned material, media, keyframe, or proposal patch operations.
    49	- Route-scope symmetry is mandatory. Missing, inferred, caller-dependent, or ambiguous route scope is invalid.
    50	
    51	## Open Questions For The Planner
    52	
    53	- Where should Phase 0 decision records and fixture inventories live so later milestones can cite them durably: `docs/extensions/composition-spine/`, `.megaplan/briefs/...`, or both?
    54	- Should the first-class non-media bake concept be named `DeterministicCapture` everywhere, or should implementation use `BakedValueRef` with documentation aliasing?
    55	- Which existing canaries are the canonical seeds for the four release examples, and which new fixture rows need to be created before implementation begins?
    56	- Where is the least invasive host boundary for `ExtensionRuntime.contributionIndex` assembly and package-state inventory: current `FamilyRuntimeAssembly` paths, a new runtime composition module, or a small adapter beside existing family normalization?
    57	- Which existing inspector/export/status surfaces should host blocker and repair UI before adding any shared component, and what is the minimal browser acceptance surface for each composed example?
    58	- How should the sequential chain handle v8's parallelization notes for M3a/M3b, M3c/M4, and M7a/M6b: keep this chain strictly ordered, or split later into parallel chains once contracts are stable?
    59	- What repo-controlled fixture process should M6 use, and where should JSON-RPC protocol fixtures live so M6a core tests and M6b browser tests share the same source of truth?
    60	- Which governance scripts already exist versus need to be created in M7b, especially SDK public export checks, docs maturity sync, family conformance, example readiness, and graph-path marker checks?
    61	
    62	## Constraints
    63	
    64	- Preserve existing editor behavior and old planner callers through compatibility shims until each fact family becomes graph-authoritative.
    65	- Do not import host runtime modules from SDK contracts.
    66	- Do not expose raw `DataProvider`, raw `applyEdit`, internal ops, descriptor pointers, or contribution-index entry shapes through public SDK.
    67	- Do not add sandboxing, marketplace, remote/untrusted process execution, arbitrary shell access, headless renderers, WebGPU, visual node editor, shader stacks, arbitrary texture routing, FBO chains, or arbitrary material graphs.
    68	- Do not expand V1 target paths beyond `clip-param`, `effect-param`, `transition-param`, and `shader-uniform`.
    69	- Do not add public process lifecycle or sidecar statuses to the V1 composition SDK.
    70	- Do not claim export support based on preview behavior.
    71	- Do not let docs, canaries, or release examples pass through legacy-only planner facts after graph authority lands for their family.
    72	- Do not let processes, agents, or sidecars mutate the timeline directly.
    73	- Do not treat live-only, pending-active, stale, failed, weaker-provenance, or route-incompatible material states as generic missing-package cases.
    74	- Do not treat omitted route scope as `all`.
    75	- Do not hardcode physical-device support, sandbox safety, executable-package preview, or runtime-safety claims for machine-path or executable-package artifact profiles.
    76	
    77	## Touchpoints
    78	
    79	- `src/sdk/index.ts`
    80	- `src/sdk/video/composition/references.ts`
    81	- `src/sdk/video/composition/graph.ts`
    82	- `src/sdk/video/rendering/artifacts.ts`
    83	- `src/tools/video-editor/runtime/ExtensionRuntime*`
    84	- `src/tools/video-editor/runtime/FamilyRuntimeAssembly.ts`
    85	- `src/tools/video-editor/runtime/composition/**`
    86	- `src/tools/video-editor/runtime/extensionManifest.ts`
    87	- `src/tools/video-editor/runtime/extensionLoader.ts`
    88	- `src/tools/video-editor/runtime/contributionFamilies.ts`
    89	- `src/tools/video-editor/lib/renderRouter.ts`
    90	- `src/tools/video-editor/rendering/**`
    91	- `src/tools/video-editor/commands/**`
    92	- `src/tools/video-editor/hooks/useTimelineCommands.ts`
    93	- `src/tools/video-editor/hooks/useAgentSession.ts`
    94	- `src/tools/video-editor/components/**`
    95	- `src/tools/video-editor/data/**`
    96	- `config/contracts/registry.json`
    97	- `config/contracts/reigh-extension.schema.json`
    98	- `scripts/quality/check-extension-family-conformance.mjs`
    99	- `scripts/quality/check-extension-example-readiness.mjs`
   100	- `scripts/quality/check-docs-maturity-sync.mjs`
   101	- `scripts/quality/check-sdk-public-exports.mjs`
   102	- `tests/e2e/video-editor-*.spec.ts`
   103	- `tests/**/video-editor/**`
   104	- `examples/video-editor-extension/**`
   105	- `docs/extensions/phase4-readiness.md`
   106	- `docs/extensions/foundation-closure-assessment.md`
   107	- `docs/extensions/**`
   108	- `supabase/functions/ai-timeline-agent/**`
   109	- `supabase/migrations/**`
   110	
   111	## Anti-Scope
   112	
   113	- No runtime implementation in these planning artifacts.
   114	- No test execution as part of this setup task.
   115	- No marketplace, package install, dependency manager, or remote extension discovery work.
   116	- No sandbox or permissions enforcement epic.
   117	- No headless renderer, WebGPU renderer, visual graph editor, shader stack, arbitrary texture routing, FBO chain, or arbitrary material graph.
   118	- No public `materializes`, `produces`, or `fallbacks` edge discriminants.
   119	- No process/output/agent/app executable V1 target paths.
   120	- No arbitrary multi-process DAGs.
   121	- No untrusted or remote process execution.
   122	- No docs or examples claiming support beyond graph/planner/schema/runtime evidence.
   123	
   124	## Done Criteria
   125	
   126	- All required epic input files exist under `.megaplan/initiatives/reigh-extension-composition-spine-epic/`.
   127	- Each milestone brief is scoped to the fact family and release example ownership described in v8.
   128	- `chain.yaml` lists 13 milestones, uses `base_branch: main`, `profile: partnered-5`, `robustness: thorough`, `depth: high`, `vendor: codex`, auto merge policy, and the requested driver settings.
   129	- Phase 0 freezes decisions and fixtures before implementation milestones begin.
   130	- M1-M5 prove the V1 composition SDK and first three graph-backed release examples without legacy-only planner authority.
   131	- M6-M7 add trusted process runtime and output-format sidecar route planning outside the V1 composition SDK and prove the fourth composed example.
   132	- Release gates enforce SDK exports, family maturity, graph participation, route claims, material statuses, deterministic captures, process-backed live sources, sidecar blockers, typed non-video artifacts, multi-artifact route completion, docs capability claims, graph-path markers, example readiness, and browser acceptance where UI exists.
   133	
   134	## Megaplan Dial Recommendation
   135	
   136	Use `partnered-5` profile for all milestones. Use `robustness: thorough`, `depth: high`, and `vendor: codex` for all milestones.
   137	
   138	Overall plan difficulty: 5/5 for every milestone; selected profile: `partnered-5`; because bad planning could pass local tests while damaging public SDK contracts, graph authority invariants, planner/export behavior, process trust boundaries, or release claims.
   139	
   140	Planning complexity: use `thorough` for all milestones. The epic repeatedly crosses SDK/runtime/planner/export/docs boundaries and depends on fact-scoped authority handoffs; each milestone needs explicit prep, critique, gate, revise, finalize, execute, and review.
   141	
   142	Depth: use `high` for all milestones. The planner needs structural reasoning across source-compatible legacy paths, graph authority migration, route requirements, artifact profiles, and UI/export acceptance. The higher depth is justified even when an individual milestone looks local because each milestone locks a downstream contract.
   143	
   144	Recommended chain invocation:
   145	
   146	```bash
   147	python -m arnold.pipelines.megaplan chain start \
   148	  --project-dir /Users/peteromalley/Documents/.megaplan-worktrees/reigh-pristine-sdk-boundary-run \
   149	  --spec .megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml
   150	```
   151	
   152	Suggested single-step mode while validating this high-trust chain:
   153	
   154	```bash
   155	python -m arnold.pipelines.megaplan chain start \
   156	  --project-dir /Users/peteromalley/Documents/.megaplan-worktrees/reigh-pristine-sdk-boundary-run \
   157	  --spec .megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml \
   158	  --one
   159	```
   160	
   161	## Required Briefs
   162	
   163	- `.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml`
   164	- `.megaplan/initiatives/reigh-extension-composition-spine-epic/m0-decisions-fixtures.md`
   165	- `.megaplan/initiatives/reigh-extension-composition-spine-epic/m1a-reference-identity.md`
   166	- `.megaplan/initiatives/reigh-extension-composition-spine-epic/m1b-shader-graph-authority.md`
   167	- `.megaplan/initiatives/reigh-extension-composition-spine-epic/m2-target-paths-schema.md`
   168	- `.megaplan/initiatives/reigh-extension-composition-spine-epic/m3a-material-status-matrix.md`
   169	- `.megaplan/initiatives/reigh-extension-composition-spine-epic/m3b-live-binding-capture.md`
   170	- `.megaplan/initiatives/reigh-extension-composition-spine-epic/m3c-agent-material-promotion.md`
   171	- `.megaplan/initiatives/reigh-extension-composition-spine-epic/m4-clip-shader-keyframes.md`
   172	- `.megaplan/initiatives/reigh-extension-composition-spine-epic/m5-effects-transitions-mask.md`
   173	- `.megaplan/initiatives/reigh-extension-composition-spine-epic/m6a-process-runtime-core.md`
   174	- `.megaplan/initiatives/reigh-extension-composition-spine-epic/m6b-process-ux-canary.md`
   175	- `.megaplan/initiatives/reigh-extension-composition-spine-epic/m7a-output-format-routes.md`
   176	- `.megaplan/initiatives/reigh-extension-composition-spine-epic/m7b-output-format-sidecars.md`

exec
/bin/zsh -lc "for f in .megaplan/initiatives/reigh-extension-composition-spine-epic/m1b-shader-graph-authority.md .megaplan/initiatives/reigh-extension-composition-spine-epic/m2-target-paths-schema.md .megaplan/initiatives/reigh-extension-composition-spine-epic/m3b-live-binding-capture.md .megaplan/initiatives/reigh-extension-composition-spine-epic/m7a-output-format-routes.md; do printf '\\nFILE %s\\n' \""'$f"; nl -ba "$f" | sed -n '"'1,200p'; done" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:

FILE .megaplan/initiatives/reigh-extension-composition-spine-epic/m1b-shader-graph-authority.md
     1	# M1b: Composition Graph Projection Becomes Shader/Ref Fact Authority
     2	
     3	## Outcome
     4	
     5	Make `CompositionGraph` projection authoritative for shader/ref facts and contribution-index lookups. Legacy inputs remain compatibility sources, but new shader/ref planner and export behavior must consume graph facts.
     6	
     7	## Execution Posture
     8	
     9	This is the first graph-authority handoff. Be strict about resolver precedence, package-state interpretation, graph-derived diagnostics, and legacy shim parity.
    10	
    11	## Scope
    12	
    13	IN:
    14	- Add SDK `CompositionGraph` contracts with M1b fields: `nodes`, `edges`, `referenceStates`, `diagnostics`, and `preview`.
    15	- Support node kinds `clip`, `timeline-postprocess`, and `contribution`.
    16	- Support `consumes` edges for clip/postprocess shader assignment.
    17	- Add host projector from `CompositionGraphInput` over snapshot, contribution index, optional runtime overlay, and optional patch overlay.
    18	- Add host resolver over contribution refs and package state with exact v8 resolver states and precedence.
    19	- Add patch preview for `shader.assign` and `shader.remove`.
    20	- Add canonical M1b ref/preview diagnostics.
    21	- Change planner input to graph-first authority for shader/ref facts and contribution-index lookups.
    22	- Add tests for graph-derived shader diagnostics, missing/disabled/version-incompatible refs, duplicate scope, and legacy shim parity.
    23	
    24	OUT:
    25	- Target paths.
    26	- `animates` or `binds-live`.
    27	- Material statuses.
    28	- Agent/live material promotion.
    29	- Process or output-format vocabularies.
    30	- New planner/export behavior that reads legacy shader/ref fields as alternate authority.
    31	
    32	## Locked Decisions
    33	
    34	- Resolver states are `resolved`, `missing`, `disabled`, `inactive-reserved`, `invalid-package`, `duplicate`, `settings-error`, `runtime-error`, `version-incompatible`, and `unknown`.
    35	- No scoped index entry is `missing`; missing means no scoped candidate exists.
    36	- Package failures classify before inactive/resolved states in the v8 order.
    37	- `undefined` runtime overlay and all-empty runtime overlay are equivalent no-ops.
    38	- Release examples cannot satisfy shader/ref gates through legacy-only inputs.
    39	
    40	## Constraints
    41	
    42	- Keep old callers supported through compatibility shims.
    43	- Do not add public edge kinds beyond `consumes`.
    44	- Do not bypass graph projection for M1b-owned facts.
    45	- Do not expose contribution-index internals through SDK contracts.
    46	- Do not treat duplicate, inactive, or version-incompatible refs as missing.
    47	
    48	## Done Criteria
    49	
    50	- New shader/ref planner/export tests fail if `CompositionGraph` is not constructed.
    51	- Legacy-only planner input remains supported but compatibility-only in tests/docs.
    52	- M1a shader-scope validation is consumed through graph projection.
    53	- Resolver precedence is asserted with duplicate, package failure, inactive-reserved, version-incompatible, and missing candidates.
    54	- M1b diagnostics use canonical `composition/` codes and include structured ref/state detail.
    55	
    56	## Touchpoints
    57	
    58	- `src/sdk/index.ts`
    59	- `src/sdk/video/composition/graph.ts`
    60	- `src/sdk/video/composition/references.ts`
    61	- `src/tools/video-editor/runtime/composition/**`
    62	- `src/tools/video-editor/runtime/FamilyRuntimeAssembly.ts`
    63	- `src/tools/video-editor/lib/renderRouter.ts`
    64	- `src/tools/video-editor/rendering/**`
    65	- `tests/**/video-editor/**`
    66	- `docs/extensions/**`

FILE .megaplan/initiatives/reigh-extension-composition-spine-epic/m2-target-paths-schema.md
     1	# M2: Target Paths, Schema Capability, Keyframes, And Live Binding
     2	
     3	## Outcome
     4	
     5	Define the V1 target-path grammar and schema capability answer used by keyframes, live bindings, proposal serialization, inspector controls, and export blockers.
     6	
     7	## Execution Posture
     8	
     9	Treat target paths as a public contract. Validate and canonicalize through SDK-owned pure data contracts, while host adapters resolve context from descriptors, schemas, refs, and legacy fields.
    10	
    11	## Scope
    12	
    13	IN:
    14	- Add `CompositionTargetPath` contracts and canonicalizers.
    15	- Limit executable target kinds to `clip-param`, `effect-param`, `transition-param`, and `shader-uniform`.
    16	- Add reserved non-executable `extension-param` envelope for `output`, `process`, `agent`, and `app`.
    17	- Add host migration adapters for keyframes, automation, and live binding fields.
    18	- Add `CompositionParamCapability` with render widget, animatable, live-bindable, serializable, export-deterministic, default value, value type, and interpolation policy.
    19	- Add schema examples for scalar, vector, color, bounded structured-data values, and source selectors.
    20	- Project `animates` and `binds-live` graph edges.
    21	- Add target/schema diagnostics for invalid paths, ambiguity, unsupported target kinds, unknown refs/uniforms, non-bindable targets, value types, and interpolation.
    22	
    23	OUT:
    24	- Executable process/output/agent/app target paths.
    25	- Material runtime and bake execution.
    26	- Shader assignment execution.
    27	- Visual graph editor.
    28	- Special app/process/output routing state for source selectors.
    29	
    30	## Locked Decisions
    31	
    32	- Non-shader parameter paths are relative to params and never start with `params.` after normalization.
    33	- Shader uniform paths canonicalize to `uniforms.<name>` and require a `ShaderRef`.
    34	- Legacy flat keys and live mapping names are compatibility/source-shaping data only.
    35	- Structured params are schema capability, not a new target-path kind.
    36	- Inspector controls, keyframe validation, live binding, proposal serialization, and export blockers consume the same capability answer.
    37	
    38	## Constraints
    39	
    40	- Do not expand V1 executable target kinds.
    41	- Reserved domains validate lexically but emit `composition/unsupported-target-kind`.
    42	- Do not infer animation/export capability from raw JavaScript value shape.
    43	- Do not let explicit `targetPath` be overridden by legacy fields.
    44	- Invalid target paths must block graph-backed export/planning.
    45	
    46	## Done Criteria
    47	
    48	- Shader-uniform keyframes persist explicit `targetPath` and validate against shader schema.
    49	- Effect and transition param paths can be represented before their full verticals land.
    50	- Descriptor-owned source selectors validate as enum or bounded integer clip/effect params.
    51	- Small structured-data params validate with bounded schemas.
    52	- Legacy target strings normalize only when unambiguous.
    53	- Target diagnostics include canonical `composition/` codes and structured target/ref detail.
    54	
    55	## Touchpoints
    56	
    57	- `src/sdk/index.ts`
    58	- `src/sdk/video/composition/graph.ts`
    59	- `src/sdk/video/composition/references.ts`
    60	- `src/tools/video-editor/runtime/composition/**`
    61	- `src/tools/video-editor/commands/**`
    62	- `src/tools/video-editor/hooks/useTimelineCommands.ts`
    63	- `src/tools/video-editor/components/**`
    64	- `config/contracts/reigh-extension.schema.json`
    65	- `tests/**/video-editor/**`

FILE .megaplan/initiatives/reigh-extension-composition-spine-epic/m3b-live-binding-capture.md
     1	# M3b: Live Binding And Deterministic Capture
     2	
     3	## Outcome
     4	
     5	Make live bindings export-safe by baking media-like sources to durable artifacts/materials or non-media sources to deterministic captures, then executing graph-owned keyframe patch operations for accepted live/bake paths.
     6	
     7	## Execution Posture
     8	
     9	Keep live preview distinct from authoritative export. No mutable live source may satisfy export until it resolves to durable provenance, hashes, and route constraints.
    10	
    11	## Scope
    12	
    13	IN:
    14	- Add live source refs and live-binding graph edges through M2 target paths.
    15	- Add live bake path for media-like sources that must produce durable `RenderMaterial` or `RenderArtifact`.
    16	- Add first-class host-owned `DeterministicCapture` or `BakedValueRef` for non-media live data.
    17	- Implement Phase 0 capture profiles: seed table, event table, scalar table, and structured motion curve table.
    18	- Add executable `keyframe.add`, `keyframe.update`, and `keyframe.remove` semantics for accepted live/bake paths.
    19	- Convert event tables into graph-owned keyframe patch operations after target path, timing map, value schema, and collision policy validation.
    20	- Add patch preview for event-table conversion with per-keyframe event id, target path, mapped time, normalized value, interpolation/hold policy, collision policy, capture ref, provenance hash, and blocking diagnostics.
    21	
    22	OUT:
    23	- Agent material promotion.
    24	- Transition/effect graph verticals.
    25	- General-purpose keyframe editor rewrite.
    26	- Process execution and output-format sidecars.
    27	- Networking, collection, moderation, privacy review, or live mutable web-state semantics for external datasets.
    28	
    29	## Locked Decisions
    30	
    31	- Deterministic captures do not replace `RenderMaterial`/`RenderArtifact` for media-like outputs or non-video output artifacts.
    32	- Event-table-to-keyframe conversion is an accepted-proposal step, not sidecar mutation.
    33	- Event removal or replacement uses stable event ids to produce keyframe operations.
    34	- Patch preview must expose generated keyframe detail, not just a summary count.
    35	- Deferred capture candidates remain backlog unless a release example pulls them forward.
    36	
    37	## Constraints
    38	
    39	- Live binding blocks authoritative export until bake resolves.
    40	- Each capture profile must define schema, provenance, hash, route constraints, and rejection rules.
    41	- Event conversion requires deterministic timing, resolved target paths, schema-valid values, and explicit collision policy.
    42	- Do not allow sidecars or live captures to mutate timeline state directly.
    43	- Do not add process lifecycle or output-format sidecar behavior.
    44	
    45	## Done Criteria
    46	
    47	- Live binding blocks export until a resolved media artifact/material or deterministic capture exists.
    48	- Seed table, event table, scalar table, and structured motion curve table are validated with provenance and hashes.
    49	- Event-table conversion expands into explicit graph-owned keyframe patch operations.
    50	- Conversion preview fails readiness if it collapses detail into summary counts or host-only side effects.
    51	- Executable keyframe patch semantics are covered before M4 shader-uniform render-path integration consumes them.
    52	
    53	## Touchpoints
    54	
    55	- `src/sdk/index.ts`
    56	- `src/sdk/video/composition/graph.ts`
    57	- `src/sdk/video/composition/references.ts`
    58	- `src/sdk/video/rendering/artifacts.ts`
    59	- `src/tools/video-editor/runtime/composition/**`
    60	- `src/tools/video-editor/commands/**`
    61	- `src/tools/video-editor/hooks/useTimelineCommands.ts`
    62	- `src/tools/video-editor/hooks/useAgentSession.ts`
    63	- `tests/**/video-editor/**`
    64	- `docs/extensions/**`

FILE .megaplan/initiatives/reigh-extension-composition-spine-epic/m7a-output-format-routes.md
     1	# M7a: Output-Format Route Planning
     2	
     3	## Outcome
     4	
     5	Introduce graph-backed output-format route planning, route artifacts, typed manifest profiles, route-scope symmetry, audio attachment contract, and multi-artifact completion records.
     6	
     7	## Execution Posture
     8	
     9	Add output-format planning only after M1-M5 graph-backed examples and M6a process overlay contracts exist. Do not reintroduce legacy planner authority or retroactively expand the V1 composition SDK.
    10	
    11	## Scope
    12	
    13	IN:
    14	- Add output-format route planning over graph-derived facts and host-normalized descriptors.
    15	- Project output-format descriptors as `contribution` nodes keyed by `OutputFormatRef`.
    16	- Allow output-format descriptors to consume graph-derived timing facts, clip/timeline events, selected keyframe or parameter curves, material dependencies, and process requirements.
    17	- Add route artifacts and multi-artifact route completion records using typed `RenderArtifact` manifest profiles.
    18	- Enforce route-scope symmetry across snapshot-derived, material-derived, process-derived, and output-format-derived requirements.
    19	- Validate named non-video artifact profiles when a route needs them.
    20	- Add audio artifact attachment through existing timeline media/audio slots via graph-owned `media.attach`/`media.remove` patch operations.
    21	
    22	OUT:
    23	- Sidecar process integration for the fourth example.
    24	- Governance scripts and docs gates.
    25	- Marketplace.
    26	- Sandbox.
    27	- Headless renderer.
    28	- Arbitrary multi-process DAGs.
    29	- Untrusted or remote process execution.
    30	
    31	## Locked Decisions
    32	
    33	- Output-format routes use typed `requires`/`consumes` detail, route artifact records, and multi-artifact completion records.
    34	- Public `materializes`, `produces`, and `fallbacks` edge discriminants remain deferred.
    35	- Route completion is conjunctive across all required artifact profiles.
    36	- Partial success may produce inspectable artifacts but leaves the route incomplete.
    37	- Audio artifacts attach only through existing media/audio slot patch operations.
    38	
    39	## Constraints
    40	
    41	- Every requirement carries explicit `routeScope` or explicit route set.
    42	- Missing scope emits `composition/unsupported-route`; unrecognized scope emits `composition/unknown-route`.
    43	- No caller may treat omitted scope as `all`.
    44	- Artifact profiles must validate required fields, provenance, hashes, route constraints, and rejection rules.
    45	- Do not introduce arbitrary artifact-to-node routing.
    46	
    47	## Done Criteria
    48	
    49	- Output-format route claims are proven through graph-derived planner behavior.
    50	- Output-format descriptors participate as contribution nodes keyed by `OutputFormatRef`.
    51	- Route completion depends on every required typed artifact resolving.
    52	- Named non-video artifact profiles validate required manifest fields and provenance.
    53	- Route-scope symmetry holds for snapshot, material, process, and output-format requirements.
    54	- Audio artifacts attach only through existing media/audio slot operations.
    55	
    56	## Touchpoints
    57	
    58	- `src/sdk/index.ts`
    59	- `src/sdk/video/composition/graph.ts`
    60	- `src/sdk/video/composition/references.ts`
    61	- `src/sdk/video/rendering/artifacts.ts`
    62	- `src/tools/video-editor/runtime/composition/**`
    63	- `src/tools/video-editor/lib/renderRouter.ts`
    64	- `src/tools/video-editor/commands/**`
    65	- `config/contracts/reigh-extension.schema.json`
    66	- `tests/**/video-editor/**`
    67	- `docs/extensions/**`

codex
The staged epic itself agrees with the criticism: it says graph authority must be fact-scoped, and M1b is specifically the first handoff for shader/ref facts. Current code has the pre-handoff scaffolding, but not the `src/sdk/video/composition/**` or `runtime/composition/**` graph layer the plan names.
exec
/bin/zsh -lc "find src/sdk -maxdepth 4 -type d -print | sort; find src/tools/video-editor/runtime -maxdepth 3 -type d -print | sort | rg 'composition|rendering|graph' || true" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
src/sdk
src/sdk/__tests__
src/sdk/__tests__/fixtures
src/sdk/smoke

exec
/bin/zsh -lc "rg -n \"CompositionGraph|CompositionTargetPath|TargetPath|targetPath|targetParamName|targetEffectId|liveBindings|shaderPostprocess|app\\.shader|materialRefs|sourceRefs|renderGroups|outputFormatsForPlanning|scanExportConfig|scanTimelineLiveBindings\\(|getFastRenderRouteDecision|CLIENT_CLIP_TYPES|clip\\.generation|generation\\?\\.sequence_lane|materializeSequenceConfig|ThemeProvider|SEQUENCE_COMPONENT_REGISTRY|THEME_PACKAGE_REGISTRY\" src/tools/video-editor src/sdk docs/extensions docs/video-editor .megaplan/initiatives/reigh-extension-composition-spine-epic -g '"'!**/*.test.*'"'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
.megaplan/initiatives/reigh-extension-composition-spine-epic/chain.yaml:30:  notes: Make CompositionGraph projection authoritative for shader/ref facts and contribution-index
docs/video-editor/shader-execution-model.md:34:- Clip-local shaders assigned to one clip through `clip.app.shader`.
docs/video-editor/shader-execution-model.md:35:- Timeline postprocess shaders assigned through `config.app.shaderPostprocess`.
src/sdk/index.ts:1382:  sourceRefs?: readonly ToolSourceRef[];
src/sdk/index.ts:2253:  readonly targetEffectId?: string;
src/sdk/index.ts:2255:  readonly targetParamName?: string;
src/sdk/index.ts:4280:  readonly sourceRefs: readonly CapabilitySourceRef[];
src/sdk/index.ts:4738:  targetParamName?: string;
src/sdk/index.ts:4890:  liveBindings?: readonly TimelineLiveBindingSummary[];
src/sdk/index.ts:4892:  materialRefs?: readonly TimelineMaterialRefSummary[];
src/sdk/index.ts:4894:  sourceRefs?: readonly TimelineSourceRefSummary[];
src/sdk/index.ts:4898:  renderGroups?: readonly TimelineRenderGroupSummary[];
src/sdk/index.ts:4922:  liveBindings?: readonly TimelineLiveBindingSummary[];
src/sdk/index.ts:4924:  materialRefs?: readonly TimelineMaterialRefSummary[];
src/sdk/index.ts:4926:  sourceRefs?: readonly TimelineSourceRefSummary[];
src/sdk/index.ts:5080:  if (snapshot.liveBindings) {
src/sdk/index.ts:5082:    for (const binding of snapshot.liveBindings) {
src/sdk/index.ts:5133:  if (snapshot.materialRefs) {
src/sdk/index.ts:5134:    for (const ref of snapshot.materialRefs) {
src/sdk/index.ts:5150:  if (snapshot.sourceRefs) {
src/sdk/index.ts:5151:    for (const ref of snapshot.sourceRefs) {
src/tools/video-editor/testing/banodoco-stubs/theme-api.tsx:72:export function ThemeProvider({
src/tools/video-editor/testing/banodoco-stubs/registry.generated.ts:3:export const THEME_PACKAGE_REGISTRY = {
src/tools/video-editor/testing/banodoco-stubs/registry.generated.ts:26:export type ThemePackageClipType = keyof typeof THEME_PACKAGE_REGISTRY;
src/tools/video-editor/testing/banodoco-stubs/registry.generated.ts:29:  Object.keys(THEME_PACKAGE_REGISTRY) as ThemePackageClipType[],
src/tools/video-editor/types/index.ts:212:  targetParamName?: string;
src/tools/video-editor/types/index.ts:213:  targetEffectId?: string;
src/tools/video-editor/types/index.ts:293:  targetParamName?: string;
src/tools/video-editor/types/index.ts:299:// clip-local shader in clip.app.shader and one postprocess shader in
src/tools/video-editor/types/index.ts:300:// config.app.shaderPostprocess.
src/tools/video-editor/types/index.ts:337:  shaderPostprocess?: TimelinePostprocessShaderMetadata;
src/tools/video-editor/clip-types/ClipTypeRegistry.ts:40:  readonly targetParamName?: string;
src/tools/video-editor/sequences/generation.ts:176:      generationId: clip.generationId,
src/tools/video-editor/sequences/headlessRender.ts:10:// - It does NOT exercise ThemeProvider — components calling useTheme() outside
src/tools/video-editor/sequences/headlessRender.ts:11://   of a wrapping ThemeProvider may render fine in this gate but fail in the
src/tools/video-editor/sequences/registry.ts:2:  THEME_PACKAGE_REGISTRY,
src/tools/video-editor/sequences/registry.ts:108:export const SEQUENCE_COMPONENT_REGISTRY = {
src/tools/video-editor/sequences/registry.ts:109:  ...THEME_PACKAGE_REGISTRY,
src/tools/video-editor/sequences/registry.ts:114:  clipType: keyof typeof SEQUENCE_COMPONENT_REGISTRY;
src/tools/video-editor/sequences/registry.ts:173:  SEQUENCE_COMPONENT_REGISTRY,
src/tools/video-editor/sequences/registry.ts:188:  SEQUENCE_COMPONENT_REGISTRY,
src/tools/video-editor/sequences/registry.ts:199:const AVAILABLE_CLIP_TYPE_REGISTRY_VIEW = createAvailableClipTypeRegistry(SEQUENCE_COMPONENT_REGISTRY);
src/tools/video-editor/sequences/registry.ts:321: * SEQUENCE_COMPONENT_REGISTRY lookup).
src/tools/video-editor/sequences/registry.ts:340:      if (!Object.prototype.hasOwnProperty.call(SEQUENCE_COMPONENT_REGISTRY, normalized)) {
src/tools/video-editor/compositions/fallback/registry.generated.tsx:32:export const THEME_PACKAGE_REGISTRY = {
src/tools/video-editor/compositions/fallback/registry.generated.tsx:55:export type ThemePackageClipType = keyof typeof THEME_PACKAGE_REGISTRY;
src/tools/video-editor/runtime/agentToolContracts.ts:576:      // Validate sourceRefs if present
src/tools/video-editor/runtime/agentToolContracts.ts:577:      if (r.sourceRefs !== undefined) {
src/tools/video-editor/runtime/agentToolContracts.ts:578:        if (!Array.isArray(r.sourceRefs)) {
src/tools/video-editor/runtime/agentToolContracts.ts:582:              'sourceRefs must be an array.',
src/tools/video-editor/runtime/agentToolContracts.ts:924:  if (result.sourceRefs && result.sourceRefs.length > 0) {
src/tools/video-editor/runtime/agentToolContracts.ts:925:    const refSummaries = result.sourceRefs
src/tools/video-editor/runtime/agentToolContracts.ts:992:    if (result.sourceRefs && result.sourceRefs.length > 0) {
src/tools/video-editor/runtime/agentToolContracts.ts:993:      const refSummaries = result.sourceRefs
src/tools/video-editor/compositions/fallback/theme-api.tsx:78:export function ThemeProvider({
src/tools/video-editor/compositions/VisualClip.tsx:195:  materialRefs?: readonly RenderMaterialRef[];
src/tools/video-editor/compositions/VisualClip.tsx:268:function materialRefsForClip(
src/tools/video-editor/compositions/VisualClip.tsx:270:  materialRefs: readonly RenderMaterialRef[] | undefined,
src/tools/video-editor/compositions/VisualClip.tsx:272:  if (materialRefs && materialRefs.length > 0) return materialRefs;
src/tools/video-editor/compositions/VisualClip.tsx:274:  const refs = app?.materialRefs ?? clip.params?.materialRefs;
src/tools/video-editor/compositions/VisualClip.tsx:442:  materialRefs,
src/tools/video-editor/compositions/VisualClip.tsx:466:  const pendingMaterial = materialRefsForClip(clip, materialRefs)
src/tools/video-editor/compositions/VisualClip.tsx:580:  materialRefs,
src/tools/video-editor/compositions/VisualClip.tsx:609:          materialRefs={materialRefs}
src/tools/video-editor/runtime/agentToolInvocationService.ts:205:        sourceRefs: result.sourceRefs,
src/tools/video-editor/compositions/TimelineRenderer.tsx:26:  ThemeProvider,
src/tools/video-editor/compositions/TimelineRenderer.tsx:34:  SEQUENCE_COMPONENT_REGISTRY,
src/tools/video-editor/compositions/TimelineRenderer.tsx:66://   2. THEME_PACKAGE_REGISTRY (codegenned from installed
src/tools/video-editor/compositions/TimelineRenderer.tsx:78:// SEQUENCE_COMPONENT_REGISTRY directly; DB-stored entries (clipType
src/tools/video-editor/compositions/TimelineRenderer.tsx:88:  return Object.prototype.hasOwnProperty.call(SEQUENCE_COMPONENT_REGISTRY, value);
src/tools/video-editor/compositions/TimelineRenderer.tsx:118:  // fall back to the static SEQUENCE_COMPONENT_REGISTRY for built-ins.
src/tools/video-editor/compositions/TimelineRenderer.tsx:120:  const staticEntry = SEQUENCE_COMPONENT_REGISTRY[clip.clipType as keyof typeof SEQUENCE_COMPONENT_REGISTRY];
src/tools/video-editor/compositions/TimelineRenderer.tsx:138:      <ThemeProvider value={theme}>
src/tools/video-editor/compositions/TimelineRenderer.tsx:140:      </ThemeProvider>
src/tools/video-editor/compositions/TimelineRenderer.tsx:302:    targetParamName: record.binding.targetParamName,
src/tools/video-editor/compositions/TimelineRenderer.tsx:421:    binding.targetParamName,
src/tools/video-editor/compositions/TimelineRenderer.tsx:1227:  const liveBindingScan = scanTimelineLiveBindings(renderConfig as TimelineConfig, {
src/tools/video-editor/sequences/materialize.ts:115:export const materializeSequenceConfig = <
src/tools/video-editor/sequences/materialize.ts:147:): ResolvedTimelineConfig => materializeSequenceConfig(config);
src/tools/video-editor/runtime/extensionSurface.ts:1296:      sourceRefs: Object.freeze([sourceRef]),
src/tools/video-editor/runtime/extensionSurface.ts:1355:    sourceRefs: Object.freeze([sourceRef]),
src/tools/video-editor/lib/theme-api.fallback.tsx:83:export function ThemeProvider({
src/tools/video-editor/runtime/exportGuard.ts:267:export function scanExportConfig(
src/tools/video-editor/runtime/exportGuard.ts:318:  const liveScan = scanTimelineLiveBindings(config as TimelineConfig);
src/tools/video-editor/runtime/exportGuard.ts:330:  if (isTimelineShaderMetadata(config.app?.shaderPostprocess, 'postprocess')) return true;
src/tools/video-editor/runtime/exportGuard.ts:364:    const shader = isTimelineShaderMetadata(clip.app?.shader, 'clip') ? clip.app.shader : undefined;
src/tools/video-editor/runtime/exportGuard.ts:375:  const postprocessShader = isTimelineShaderMetadata(config.app?.shaderPostprocess, 'postprocess')
src/tools/video-editor/runtime/exportGuard.ts:376:    ? config.app.shaderPostprocess
src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts:206:      liveBindings: [binding],
src/tools/video-editor/runtime/liveDataRegistry.ts:176:  targetEffectId?: string;
src/tools/video-editor/runtime/liveDataRegistry.ts:177:  targetParamName?: string;
src/tools/video-editor/runtime/liveDataRegistry.ts:931:        targetEffectId: binding.targetEffectId,
src/tools/video-editor/runtime/liveDataRegistry.ts:932:        targetParamName: binding.targetParamName,
src/tools/video-editor/runtime/liveDataRegistry.ts:1027:            targetEffectId: b.targetEffectId,
src/tools/video-editor/runtime/liveDataRegistry.ts:1028:            targetParamName: b.targetParamName,
src/tools/video-editor/runtime/renderPlanner.ts:50:  readonly materialRefs?: readonly RenderMaterialRef[];
src/tools/video-editor/runtime/renderPlanner.ts:810:  for (const group of snapshot?.renderGroups ?? []) {
src/tools/video-editor/runtime/renderPlanner.ts:960:  for (const materialRef of input.materialRefs ?? []) {
src/tools/video-editor/lib/registry.generated.fallback.ts:1:export const THEME_PACKAGE_REGISTRY = {} as const;
src/tools/video-editor/capabilityManifest.ts:2:import { SEQUENCE_COMPONENT_REGISTRY } from '@/tools/video-editor/sequences/registry.ts';
src/tools/video-editor/capabilityManifest.ts:5:  SEQUENCE_COMPONENT_REGISTRY,
src/tools/video-editor/lib/timeline-reader.ts:187:  const records = [...scanTimelineLiveBindings(data.config).bindings];
src/tools/video-editor/lib/timeline-reader.ts:191:    const appLiveBindings = clip.app?.liveBindings;
src/tools/video-editor/lib/timeline-reader.ts:214:          ...(typeof binding.targetParamName === 'string'
src/tools/video-editor/lib/timeline-reader.ts:215:            ? { targetParamName: binding.targetParamName }
src/tools/video-editor/lib/timeline-reader.ts:217:          ...(typeof binding.targetEffectId === 'string'
src/tools/video-editor/lib/timeline-reader.ts:218:            ? { targetEffectId: binding.targetEffectId }
src/tools/video-editor/lib/timeline-reader.ts:234:        path: `clips.${clip.id}.app.liveBindings`,
src/tools/video-editor/lib/timeline-reader.ts:331:      const liveBindingsByClip = new Map<string, TimelineLiveBindingRecord[]>();
src/tools/video-editor/lib/timeline-reader.ts:334:        const records = liveBindingsByClip.get(record.clipId) ?? [];
src/tools/video-editor/lib/timeline-reader.ts:336:        liveBindingsByClip.set(record.clipId, records);
src/tools/video-editor/lib/timeline-reader.ts:349:          ? clip.app.shader
src/tools/video-editor/lib/timeline-reader.ts:453:        for (const record of liveBindingsByClip.get(clip.id) ?? []) {
src/tools/video-editor/lib/timeline-reader.ts:459:            ...(record.binding.targetParamName !== undefined
src/tools/video-editor/lib/timeline-reader.ts:460:              ? { targetParamName: record.binding.targetParamName }
src/tools/video-editor/lib/timeline-reader.ts:539:            ? { liveBindings: clipLiveBindings }
src/tools/video-editor/lib/timeline-reader.ts:542:            ? { materialRefs: clipMaterialRefs }
src/tools/video-editor/lib/timeline-reader.ts:545:            ? { sourceRefs: clipSourceRefs }
src/tools/video-editor/lib/timeline-reader.ts:573:      const postprocessShader = isPostprocessShaderMetadata(app.shaderPostprocess)
src/tools/video-editor/lib/timeline-reader.ts:574:        ? app.shaderPostprocess
src/tools/video-editor/lib/timeline-reader.ts:613:      const renderGroups: TimelineRenderGroupSummary[] = [];
src/tools/video-editor/lib/timeline-reader.ts:625:            renderGroups.push({
src/tools/video-editor/lib/timeline-reader.ts:660:        liveBindings:
src/tools/video-editor/lib/timeline-reader.ts:662:        materialRefs:
src/tools/video-editor/lib/timeline-reader.ts:664:        sourceRefs:
src/tools/video-editor/lib/timeline-reader.ts:668:        renderGroups:
src/tools/video-editor/lib/timeline-reader.ts:669:          renderGroups.length > 0 ? renderGroups : undefined,
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:369:  const sourceRefs: ToolSourceRef[] = affectedObjectIds.map((id, index) => ({
src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts:383:    sourceRefs,
src/tools/video-editor/examples/extensions/agent-tools-copilot/index.ts:171:  const sourceRefs = buildSourceRefsFromSnapshot(snapshot);
src/tools/video-editor/examples/extensions/agent-tools-copilot/index.ts:178:      sourceRefs,
src/tools/video-editor/examples/extensions/agent-tools-copilot/index.ts:188:          sourceRefCount: sourceRefs.length,
src/tools/video-editor/examples/extensions/agent-tools-copilot/index.ts:215:      sourceRefs: [],
src/tools/video-editor/examples/extensions/agent-tools-copilot/index.ts:274:  const sourceRefs = buildSourceRefsFromSnapshot(snapshot);
src/tools/video-editor/examples/extensions/agent-tools-copilot/index.ts:302:    sourceRefs,
src/tools/video-editor/examples/extensions/agent-tools-copilot/index.ts:310:          `${sourceRefs.length} source→output refs.`,
src/tools/video-editor/examples/extensions/agent-tools-copilot/index.ts:314:          sourceRefCount: sourceRefs.length,
src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts:130:      liveBindings: [binding],
src/tools/video-editor/hooks/useRenderState.ts:20:  scanExportConfig,
src/tools/video-editor/hooks/useRenderState.ts:42:const CLIENT_CLIP_TYPES = new Set(['media', 'text', 'effect-layer', 'hold']);
src/tools/video-editor/hooks/useRenderState.ts:44:function getFastRenderRouteDecision(resolvedConfig: ResolvedTimelineConfig | null) {
src/tools/video-editor/hooks/useRenderState.ts:54:    if (clip.generation?.sequence_lane === 'remotion_module') {
src/tools/video-editor/hooks/useRenderState.ts:55:      if (!clip.generation?.artifact_id) {
src/tools/video-editor/hooks/useRenderState.ts:62:    if (!clip.clipType || CLIENT_CLIP_TYPES.has(clip.clipType)) {
src/tools/video-editor/hooks/useRenderState.ts:101:  guardResult: ReturnType<typeof scanExportConfig>,
src/tools/video-editor/hooks/useRenderState.ts:174:function exportDiagnosticId(diagnostic: ReturnType<typeof scanExportConfig>['diagnostics'][number], index: number): string {
src/tools/video-editor/hooks/useRenderState.ts:227:  guardResult: ReturnType<typeof scanExportConfig>,
src/tools/video-editor/hooks/useRenderState.ts:237:function outputFormatsForPlanning(extensionRuntime: ExtensionRuntime | undefined): readonly VideoEditorOutputFormatDescriptor[] {
src/tools/video-editor/hooks/useRenderState.ts:253:  diagnostic: ReturnType<typeof scanExportConfig>['diagnostics'][number],
src/tools/video-editor/hooks/useRenderState.ts:312:    const outputFormats = outputFormatsForPlanning(extensionRuntime);
src/tools/video-editor/hooks/useRenderState.ts:376:    const guardResult = scanExportConfig(resolvedConfig, builtIn, extIds, effectRegistrySnapshot, transitionRegistrySnapshot, clipTypeRegistrySnapshot);
src/tools/video-editor/hooks/useRenderState.ts:406:    let decision = getFastRenderRouteDecision(resolvedConfig);
src/tools/video-editor/hooks/useRenderState.ts:514:    const plannerOutputFormats = outputFormatsForPlanning(extensionRuntime);
src/tools/video-editor/sequence.ts:42:  materializeSequenceConfig,
src/tools/video-editor/lib/timeline-data.ts:154:    generation: clip.generation,
src/tools/video-editor/lib/generated-lanes.ts:27:): unknown => clip?.generation?.sequence_lane;
src/tools/video-editor/lib/renderRouter.ts:12://   * If ANY clip's clipType is in THEME_PACKAGE_REGISTRY → orchestrator.
src/tools/video-editor/lib/renderRouter.ts:35:import { materializeSequenceConfig } from '@/tools/video-editor/sequences/materialize.ts';
src/tools/video-editor/lib/renderRouter.ts:605:      timeline: materializeSequenceConfig(request.resolvedConfig as Parameters<typeof materializeSequenceConfig>[0]),
src/tools/video-editor/lib/timeline-domain.ts:142:export const TIMELINE_POSTPROCESS_SHADER_APP_KEY = 'shaderPostprocess';
src/tools/video-editor/lib/timeline-domain.ts:1184:  if (Array.isArray(value.liveBindings)) {
src/tools/video-editor/lib/timeline-domain.ts:1185:    return [{ value: value.liveBindings, pathSuffix: '.liveBindings' }];
src/tools/video-editor/lib/timeline-domain.ts:1213:  const paramsLiveBindings = clip.params?.liveBindings;
src/tools/video-editor/lib/timeline-domain.ts:1215:    candidates.push({ value: paramsLiveBindings, path: `clips.${clip.id}.params.liveBindings` });
src/tools/video-editor/lib/timeline-domain.ts:2084:          path: `clips.${clip.id}.app.shader`,
src/tools/video-editor/lib/timeline-domain.ts:2113:  const liveBindingValidation = scanTimelineLiveBindings(config);
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:757:                              {'sourceRefs' in result &&
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:759:                                  (result as unknown as Record<string, unknown>).sourceRefs,
src/tools/video-editor/components/AgentToolsPanel/AgentToolsPanel.tsx:765:                                        .sourceRefs as Array<Record<string, unknown>>
src/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel.tsx:574:  // FLAG-005 caveat that ThemeProvider/SequenceContext are NOT exercised.
src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx:289:        shaderPostprocess: nextShader,
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:137:    for (const key of ['bindings', 'liveBindings'] as const) {
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:181:    if (clip.params?.liveBindings !== undefined) {
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:182:      const filtered = filterBindingValue(clip.params.liveBindings, sourceId);
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:187:          nextParams.liveBindings = filtered.value;
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:189:          nextParams.liveBindings = filtered.value;
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:191:          delete nextParams.liveBindings;
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:389:    return scanTimelineLiveBindings(timelineConfig as TimelineConfig, {
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:485:        parameterPath: binding?.binding.targetParamName ?? 'params.live',
src/tools/video-editor/components/LiveSourcesPanel/LiveSourcesPanel.tsx:486:        label: binding?.binding.targetParamName ?? sourceLabel(row),
src/tools/video-editor/components/AgentChat/AgentChat.tsx:205:        generationId: clip.generationId,
src/tools/video-editor/components/AgentChat/AgentChat.tsx:402:      generationId: clip.generationId,
src/tools/video-editor/hooks/useAgentSession.ts:309:                ...(clip.generationId ? { generation_id: clip.generationId } : {}),

exec
/bin/zsh -lc "nl -ba docs/video-editor/shader-execution-model.md | sed -n '1,210p'; nl -ba docs/video-editor/extension-platform-contract-recheck.md | sed -n '200,235p'; nl -ba docs/extensions/phase4-readiness.md | sed -n '20,60p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
     1	# Shader Execution Model RFC
     2	
     3	Status: M13 V1 implementation note.
     4	
     5	This RFC documents the shader/WebGL bridge that M13 adds to the video editor.
     6	The model is intentionally browser-preview first. It gives extension authors a
     7	dedicated shader contribution path, deterministic diagnostics, host-owned
     8	uniform controls, and explicit export blockers. It does not introduce a render
     9	graph or imply that previewed WebGL output can be exported.
    10	
    11	## Contribution Ownership
    12	
    13	Shaders are registered as dedicated `kind: 'shader'` contributions. They do not
    14	route through component effect registration and they are not component effects
    15	with a fragment-shader prop. A shader contribution declares:
    16	
    17	- `shaderId`, label, pass, source, uniforms, textures, fallback, and optional
    18	  materializer metadata.
    19	- `source.kind: 'inline'` with fragment source and optional vertex source, or
    20	  `source.kind: 'module'` for a future host-resolved module source.
    21	- `ctx.shaders.registerShader(shaderId, source, options)` during activation.
    22	
    23	The host owns the provider-scoped shader registry, diagnostics, picker entries,
    24	timeline metadata, WebGL preview canvas lifecycle, and export-planner posture.
    25	Extension code owns shader source and contribution metadata, but it does not own
    26	the editor's WebGL context or persisted timeline metadata shape.
    27	
    28	## Pass Ownership
    29	
    30	The public SDK pass vocabulary is `clip`, `overlay`, and `postprocess`.
    31	
    32	M13 V1 implements browser preview surfaces for:
    33	
    34	- Clip-local shaders assigned to one clip through `clip.app.shader`.
    35	- Timeline postprocess shaders assigned through `config.app.shaderPostprocess`.
    36	
    37	Overlay remains part of the SDK vocabulary, but M13 does not ship an overlay
    38	composition surface, overlay picker path, or overlay export materialization
    39	path. Overlay contributions can still be represented as shader records and
    40	diagnostics; they should not be treated as runnable V1 preview/export passes
    41	until a later milestone assigns ownership for placement, ordering, and
    42	composition.
    43	
    44	## Frame Sources
    45	
    46	The WebGL preview surface receives the current host frame and time from the
    47	browser preview path:
    48	
    49	- Clip-local shaders receive clip-local seconds and frame index from the visual
    50	  clip preview.
    51	- Postprocess shaders receive timeline seconds and frame index from the timeline
    52	  renderer preview.
    53	- Built-in uploads include resolution, frame, and time values for shader code
    54	  that declares matching uniforms.
    55	
    56	Frame inputs are preview-time host values. They are not stable export artifacts
    57	and are not materialized unless a later materializer process writes
    58	`RenderMaterial`.
    59	
    60	## Texture Lifecycle
    61	
    62	Textures are host-bound preview inputs. The supported V1 source kinds are:
    63	
    64	- `clip-frame`
    65	- `static-image-asset`
    66	- `live-generated-frame`
    67	
    68	Texture definitions map a logical texture name to a sampler uniform. A
    69	`textureRef` uniform can provide the selected source kind and optional `ref`.
    70	During preview, the WebGL surface resolves host-provided texture sources,
    71	creates WebGL textures, uploads them before drawing, and releases preview-owned
    72	WebGL resources on disposal or context loss.
    73	
    74	Unsupported texture categories include external URLs, arbitrary DOM media not
    75	provided through a supported host source, cubemaps, 3D textures, depth/stencil
    76	textures, previous-frame feedback buffers, multipass FBO chains, render-graph
    77	intermediate textures, audio/FFT textures, and worker-owned GPU resources. These
    78	must produce diagnostics or be deferred behind a later explicit host contract;
    79	they must not be silently approximated.
    80	
    81	Required supported textures that are missing at preview time produce
    82	`shader/texture-unavailable`. Unsupported source kinds produce
    83	`shader/texture-unsupported`.
    84	
    85	## Uniform Subset
    86	
    87	M13 V1 supports host-rendered controls for these shader uniform types:
    88	
    89	- `float`, `int`, `bool`
    90	- `vec2`, `vec3`, `vec4`, `color`
    91	- `enum`
    92	- `frame`, `time`
    93	- `textureRef`
    94	
    95	Editable scalar, vector, color, enum, frame, and time values are persisted under
    96	timeline shader metadata. `textureRef` values are host bindings, not raw form
    97	inputs. The generic `SchemaForm` renders a diagnostic placeholder for
    98	`textureRef`; the shader inspector persists texture defaults/bindings under the
    99	shader metadata texture map and leaves full texture editing deferred.
   100	
   101	Unsupported uniform schemas produce `shader/uniform-unsupported` during shader
   102	schema validation.
   103	
   104	## Preview Bypass And A/B Posture
   105	
   106	The inspector owns preview bypass state through shader metadata:
   107	
   108	- `enabled: false` means the shader is bypassed.
   109	- `metadata.inspectorCompareMode` stores the inspector's shader/bypass A/B
   110	  intent.
   111	- `metadata.uniformPreset` tracks whether persisted uniforms are defaults or
   112	  custom edits.
   113	
   114	Split-view comparison is explicitly deferred in M13. The inspector can store
   115	A/B intent and apply bypass, but it does not create a second synchronized preview
   116	pipeline.
   117	
   118	## V1 Composition Limits
   119	
   120	M13 V1 enforces one shader per runnable scope:
   121	
   122	- One clip-local shader per clip.
   123	- One timeline postprocess shader.
   124	
   125	Adding a second shader to the same scope is a domain and planner error, not a
   126	silent replacement and not an ordered stack. The user-facing messages are:
   127	
   128	- `Cannot add shader "<incoming>" to clip "<clipId>" because shader "<existing>" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.`
   129	- `Cannot add postprocess shader "<incoming>" because postprocess shader "<existing>" is already assigned. V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.`
   130	
   131	Ordered shader stacks, multipass composition, temporal feedback, previous-frame
   132	inputs, transition shaders, and render-graph scheduling are deferred.
   133	
   134	## Export And Materialization
   135	
   136	Browser preview is not export support.
   137	
   138	Timeline shader metadata emits shader materializer requirements for export
   139	routes. If no materializer has produced `RenderMaterial`, the planner and export
   140	guard block export with this exact blocker text:
   141	
   142	`Shader "<id>" cannot export because no shader materializer produced RenderMaterial for <scope>.`
   143	
   144	The concrete `<scope>` text is produced by the host:
   145	
   146	- Clip shader example: `clip "clip-1"`.
   147	- Postprocess shader example: `timeline postprocess`.
   148	
   149	A shader contribution may declare materializer metadata so the planner can
   150	discover a process route. Discovery changes the planner posture to a
   151	materialization next action/progress state, but it still does not mean export is
   152	ready. Export becomes available only after a supported renderer route or
   153	materializer produces the required `RenderMaterial`.
   154	
   155	## Non-Render-Graph V1 Posture
   156	
   157	The V1 bridge is a narrow preview execution path:
   158	
   159	- One fullscreen WebGL program per assigned scope.
   160	- Host-owned canvas/context creation, resize, draw, `readPixels`-friendly
   161	  deterministic rendering, and disposal.
   162	- Context-loss handling that pauses preview, preserves shader source/uniform
   163	  state, recompiles on restore, and resumes rendering.
   164	
   165	It is not a render graph. There is no pass scheduler, no graph edge model, no
   166	ordered dependency chain, no multipass FBO ownership, and no implicit export
   167	capture.
   168	
   169	## Diagnostics
   170	
   171	Shader diagnostics use the existing host diagnostic surfaces. Important codes
   172	include:
   173	
   174	- `shader/compile-error`
   175	- `shader/link-error`
   176	- `shader/uniform-unsupported`
   177	- `shader/texture-unsupported`
   178	- `shader/texture-unavailable`
   179	- `shader/webgl-unavailable`
   180	- `shader/webgl-context-lost`
   181	
   182	Invalid shader records can stay registered with error status so the picker,
   183	inspector, diagnostics panel, and planner can explain the problem without
   184	crashing the preview.
   185	
   186	## Canary Coverage
   187	
   188	M13 includes two browser-preview-only canaries:
   189	
   190	- A clip-local shader canary.
   191	- A timeline postprocess shader canary.
   192	
   193	Both canaries use the same SDK contribution kind, `ctx.shaders` registration,
   194	uniform schema subset, diagnostics path, renderability metadata, preview
   195	surface, picker/selection contracts, and planner blocker/materializer posture.
   200	| M11-002 | Timeline mutation/history does not grow per sample | pass | supported | Ring-buffer sample delivery outside `TimelinePatch` and undo history | `src/tools/video-editor/runtime/` |
   201	| M11-003 | Bake creates deterministic data: video/image/audio asset, keyframes, automation clips, standard clips, sidecars, or `RenderMaterial` refs | pass | supported | Bake semantics converting ephemeral samples into deterministic assets; bake destination is explicit per source | `src/tools/video-editor/runtime/` |
   202	| M11-004 | Export blocked before bake, follows normal route after bake with standard asset or resolved `RenderMaterial` | pass | supported | Export guard detects active live sources and surfaces bake/remove actions | `src/tools/video-editor/runtime/` |
   203	| M11-005 | Lifecycle cleanup works on unmount, provider change, HMR, and permission failure | gap | supported | `DisposeHandle` and provider-scoped lifecycle for data sources; permission failure cleanup tests not identified | `src/tools/video-editor/runtime/` |
   204	| M11-006 | Frontend shows permission, active/error, export-blocked, and bake-ready states for canary source | gap | supported | `live-webcam-canary/` and `live-generated-frame-canary/` extensions; dedicated frontend tests not identified | live extensions |
   205	| M11-007 | Clips/effects reading reserved live-source IDs show diagnostics before source activation and deterministic references after bake | gap | supported | Live-source binding semantics defined; dedicated diagnostics tests not identified | `src/tools/video-editor/runtime/` |
   206	| M11-008 | Progressive generated-frame replacement, cancellation, timeline placeholder state, bake into deterministic assets or `RenderMaterial` refs | gap | supported | `live-generated-frame-canary/` extension exists; dedicated tests not identified | live-generated-frame-canary |
   207	| M11-009 | Microphone/MIDI/device sample streams baking into deterministic keyframes or automation clips without per-sample timeline mutations | gap | supported | Source kinds defined; dedicated bake tests not identified | SDK types |
   208	| M11-010 | Steering/reconfigure diagnostics and live-source-to-uniform binding metadata | gap | supported | Steering vocabulary defined; dedicated tests not identified | `src/tools/video-editor/runtime/` |
   209	| M11-011 | `GenerationSession` live sample delivery, supersede/fork metadata, partial bake mixed-state diagnostics, recording pass take acceptance, learn-mode mapping | gap | supported | Session concepts defined; dedicated live-delivery tests not identified | `src/tools/video-editor/runtime/` |
   210	| M11-012 | Session panel rendering, steering fork/supersede UI, partial-bake range selection, recording strip, mapping table, learn-mode, audio-analysis overlay, take-review accept/discard | gap | supported | Host-owned UI surfaces listed; dedicated frontend tests not identified | `src/tools/video-editor/components/` |
   211	
   212	### 2.13 M12 — Render Capability Planning, Output Formats, And Processes
   213	
   214	| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
   215	|---|---|---|---|---|---|
   216	| M12-001 | Render planner reports capabilities and blockers for native, component-effect, extension-transition, extension-clip, live-source, process-dependent, and output-format scenarios | gap | supported | Planner vocabulary (`CapabilityFinding`, `RenderBlocker`, `RenderRoute`) exported; full planner implementation not confirmed | `src/sdk/index.ts` |
   217	| M12-002 | Export UI surfaces clear reasons and next actions | gap | supported | Export guard integration exists; UI surfacing completeness not confirmed | `src/tools/video-editor/` |
   218	| M12-003 | Component effect blocking worker export downgrades to browser export or blocks with structured reason | pass | supported | `EffectContribution.allowBrowserExport`/`allowWorkerExport`; render capability metadata | `src/sdk/index.ts` |
   219	| M12-004 | Artifact model compatibility, render-dependent output formats, mock process invocation, health failure, shutdown, sidecar download UI | gap | supported | `RenderArtifact`, `RenderDependentOutputFormatContribution`, `ProcessContribution` in SDK; comprehensive tests not identified | `src/sdk/index.ts` |
   220	| M12-005 | Artifact manifest provenance, input hash propagation, determinism status, sidecar manifest consistency | gap | supported | `RenderArtifactManifest` vocabulary defined; dedicated tests not identified | `src/sdk/index.ts` |
   221	| M12-006 | Multi-artifact dataset/show-control export with sidecar manifest, provenance metadata, download-all behavior | gap | supported | `OutputFormatContribution.sampling`, `sidecars` fields; dedicated E2E tests not identified | `src/sdk/index.ts` |
   222	| M12-007 | Planner/export inspection using public `TimelineSnapshot`/`TimelineReader` contract, contribution requirements, missing-extension blockers, no raw provider reads | gap | supported | `TimelineReader` and `TimelineSnapshot` contracts defined; planner consuming them not confirmed | `src/tools/video-editor/runtime/` |
   223	| M12-008 | Missing, stale, and resolved `RenderMaterialRef`s in planner reports and final artifact manifests | gap | supported | `RenderMaterialRef` and materialization vocabulary defined; planner reports not confirmed | `src/sdk/index.ts` |
   224	| M12-009 | Frame/audio sampling manifest entries and process roundtrip attachment behavior | gap | supported | `SamplingConfig` in SDK; dedicated tests not identified | `src/sdk/index.ts` |
   225	| M12-010 | Material metadata propagation, render-group blocking, roundtrip request/result fixtures, material proposal helper output, review provenance, show-control cue sidecars, captions vs labels, declarative sampling config validation | gap | supported | Vocabulary defined; comprehensive tests not identified | `src/sdk/index.ts` |
   226	| M12-011 | Material browser/detail filters, pending-material timeline placeholder, process operation discovery, process env widgets, roundtrip results panel, sidecar previews, export dry-run table, cue-list editor, segment/caption editor, batch-label panel, download-all UI | gap | supported | Host-owned UI surfaces listed; frontend tests not identified | `src/tools/video-editor/components/` |
   227	| M12-012 | Mock MCP-style process invoked by command/agent tool through `ctx.services.invokeProcess` | gap | supported | `invokeProcess` service path; mock process canary not identified | `src/tools/video-editor/runtime/` |
   228	| M12-013 | JSON-RPC correlation, progress, cancellation, unavailable dependency diagnostics, process status transitions in frontend UI | gap | supported | `ProcessStatus` sealed union defined; IPC tests not identified | `src/sdk/index.ts` |
   229	
   230	### 2.14 M13 — Shader And WebGL Bridge
   231	
   232	| Row ID | Done Criteria Claim | Status | Disposition | Evidence | Owner Document |
   233	|---|---|---|---|---|---|
   234	| M13-001 | Shader example renders correctly in browser preview and exposes configurable uniforms in inspector | pass | supported | `src/tools/video-editor/examples/extensions/clip-local-shader-canary/`, `postprocess-shader-canary/`; `clip-local-shader-canary.integration.test.tsx`, `postprocess-shader-canary.integration.test.tsx` | shader canary extensions |
   235	| M13-002 | Shader execution model note/RFC checked in with implementation and backed by clip-local and postprocess canaries | pass | supported | `docs/video-editor/shader-execution-model.md` — covers pass ownership, frame source, texture binding, lifecycle, V1 composition limits | `docs/video-editor/shader-execution-model.md` |
    20	  or reserved contributions into provider/runtime descriptors.
    21	- `src/tools/video-editor/runtime/extensionSurface.ts` currently bridges or
    22	  surfaces reserved descriptors for output formats, processes, shaders, and
    23	  agent tools. Output formats are turned into planner metadata with route
    24	  requirements, process requirements, blockers, next actions, sidecars, and
    25	  capability metadata. Process descriptors are surfaced as planner-visible
    26	  declarations without starting a runtime process.
    27	- `src/tools/video-editor/lib/renderRouter.ts` remains the route decision
    28	  adapter for user render clicks. It converts native, themed, generated
    29	  Remotion module, and contributed clip content into `CapabilityRequirement`
    30	  entries, calls `planRender()`, and returns a planner-backed route decision.
    31	- `src/tools/video-editor/runtime/renderPlanner.ts` is the canonical render
    32	  readiness reducer. It consumes timeline snapshot requirements, explicit
    33	  requirements, output format descriptors, process descriptors, shader
    34	  descriptors, material refs/statuses, render groups, request constraints, and
    35	  diagnostics, then returns route plans, blockers, diagnostics, next actions,
    36	  and `canBrowserExport`/`canWorkerExport`.
    37	
    38	## Render Planner Participation Contract
    39	
    40	Any Phase 4 family that can affect preview, export, generated artifacts, or
    41	determinism must participate in planning through stable capability metadata
    42	before it can be promoted to public support.
    43	
    44	Required contract:
    45	
    46	1. Each promoted family must expose provider-free planner inspection data. The
    47	   planner must not import live registries, component implementations, provider
    48	   stores, or extension package handles.
    49	2. Each render-relevant contribution must declare one or more route-level
    50	   `CapabilityRequirement` records or a descriptor that `planRender()` can
    51	   convert into equivalent requirements.
    52	3. Unsupported, preview-only, live-unbaked, missing-material, stale-material,
    53	   process-dependent, missing-contribution, and route-unsupported states must
    54	   produce actionable `RenderBlocker` records rather than silent fallback.
    55	4. Route decisions must remain planner-backed. For clip routing,
    56	   `renderRouter.ts` already indexes contributed clip records by `clipTypeId`,
    57	   allows browser export only when the contribution explicitly declares a
    58	   supported browser-export capability, and blocks worker conflicts for
    59	   contributed code.
    60	5. Output-format and process families must keep using planner descriptors

codex
The docs have a useful contradiction: `shader-execution-model.md` explicitly says the current shader bridge is not a render graph, while the new epic is planning a graph authority handoff. That means the next move should bridge those facts deliberately, not pretend the graph already exists.
exec
/bin/zsh -lc "nl -ba src/tools/video-editor/hooks/useTimelineCommands.ts | sed -n '330,430p'; nl -ba src/tools/video-editor/hooks/useTimelineCommands.ts | sed -n '1,120p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
   330	  }
   331	};
   332	
   333	export interface CreateTimelineCommandsOptions {
   334	  /** Optional ManagedObjectGuard for intercepting edits on managed clips. */
   335	  managedObjectGuard?: ManagedObjectGuard | null;
   336	}
   337	
   338	/**
   339	 * Build the mounted command facade from the timeline store.
   340	 *
   341	 * Prefer `useTimelineCommands()` or `useTimelineCommandsSafe()` at runtime.
   342	 */
   343	export function createTimelineCommands(
   344	  store: TimelineStoreApi,
   345	  options?: CreateTimelineCommandsOptions,
   346	): TimelineCommands {
   347	  const explicitGuard = options?.managedObjectGuard;
   348	  const getManagedObjectGuard = (): ManagedObjectGuard | null => {
   349	    if (explicitGuard !== undefined) return explicitGuard;
   350	    return store.getState().managedObjectGuard ?? null;
   351	  };
   352	
   353	  const getMountedState = (): CommandStoreState | null => {
   354	    const state = store.getState();
   355	    if (!state.availability.mounted) {
   356	      return null;
   357	    }
   358	    return state;
   359	  };
   360	
   361	  /**
   362	   * Check if a clip is managed by an extension and return a blocked error
   363	   * if it is. Returns null if the clip can be freely edited.
   364	   */
   365	  const checkManagedClip = (clipId: string): TimelineCommandResult<never> | null => {
   366	    const guard = getManagedObjectGuard();
   367	    if (!guard) return null;
   368	    const info = guard.checkClipManaged(clipId);
   369	    if (!info) return null;
   370	
   371	    return failure(
   372	      'managed_object_blocked',
   373	      `Clip '${clipId}' is managed by ${info.managedBy}. Confirm to detach and edit anyway.`,
   374	      { managedInfo: info },
   375	    );
   376	  };
   377	
   378	  /**
   379	   * Build a patch that detaches managed-object metadata from the clip's app
   380	   * and source_uuid fields, using the store's extension requirements for
   381	   * namespace key detection.
   382	   */
   383	  const buildDetachPatch = (clip: TimelineClip): Partial<Omit<TimelineClip, 'id'>> => {
   384	    const state = store.getState();
   385	    // Collect known extension IDs from the store's extension requirements.
   386	    const extensionIds = new Set<string>();
   387	    if (state.timelineOps) {
   388	      const snapshot = state.timelineOps;
   389	      // We need to get extension IDs — read from the timeline reader if available.
   390	    }
   391	    // Fallback: use the managedBy value from the clip itself.
   392	    const knownExtIds: ReadonlySet<string> = new Set(
   393	      clip.app && typeof clip.app.managedBy === 'string' ? [clip.app.managedBy] : [],
   394	    );
   395	
   396	    const nextApp = detachManagedApp(clip.app as Record<string, unknown> | undefined, knownExtIds);
   397	
   398	    const patch: Partial<Omit<TimelineClip, 'id'>> = {
   399	      app: nextApp as any,
   400	    };
   401	
   402	    // Also clear source_uuid if it matches a known extension.
   403	    if (clip.source_uuid && knownExtIds.has(clip.source_uuid)) {
   404	      patch.source_uuid = undefined as any;
   405	    }
   406	
   407	    return patch;
   408	  };
   409	
   410	  const commands: TimelineCommands = {
   411	  addClip(input) {
   412	      const state = getMountedState();
   413	      if (!state) {
   414	        return failure('editor_not_mounted', 'Timeline commands are only available in a mounted editor.');
   415	      }
   416	
   417	      const current = getCurrentData(state);
   418	      if (!current) {
   419	        return failure('timeline_unavailable', 'Timeline data is not loaded.');
   420	      }
   421	
   422	      const assetEntry = current.registry.assets[input.assetId];
   423	      const playableKind = getPlayableAssetKind(assetEntry);
   424	      if (!assetEntry) {
   425	        return failure('asset_not_found', `Asset '${input.assetId}' is not registered in the timeline registry.`);
   426	      }
   427	      if (!playableKind) {
   428	        return failure('unsupported_asset_type', 'Only image, video, and audio assets can be added to the timeline.');
   429	      }
   430	
     1	import { useMemo } from 'react';
     2	import {
     3	  addTrack as addTrackToConfig,
     4	  getClipEndSeconds,
     5	  getTrackById,
     6	  isHoldClip,
     7	  roundTimelineValue,
     8	  splitClipAtPlayhead,
     9	  updateClipInConfig,
    10	} from '@/tools/video-editor/lib/editor-utils.ts';
    11	import { buildDuplicateClipEdit } from '@/tools/video-editor/lib/duplicate-clip.ts';
    12	import { findEnclosingPinnedGroup } from '@/tools/video-editor/lib/pinned-group-projection.ts';
    13	import { previewTimelineMutation } from '@/tools/video-editor/lib/timeline-mutation-engine.ts';
    14	import {
    15	  buildAssetDropEdit,
    16	  estimateAssetDuration,
    17	  getPlayableAssetKind,
    18	  planAssetDropTarget,
    19	  planGenerationAssetRegistration,
    20	} from '@/tools/video-editor/lib/timeline-asset-plans.ts';
    21	import { readPositiveDurationSeconds } from '@/tools/video-editor/lib/timeline-asset-durations.ts';
    22	import type { TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
    23	import { moveTrackWithinKind } from '@/tools/video-editor/hooks/useTimelineTrackManagement.ts';
    24	import {
    25	  hasMountedTimelineAvailability,
    26	  useTimelineAvailabilityState,
    27	  useTimelineStoreApi,
    28	  useTimelineStoreApiSafe,
    29	  type TimelineStoreApi,
    30	} from '@/tools/video-editor/hooks/timelineStore.ts';
    31	import type {
    32	  TimelineEditorDataContextValue,
    33	  TimelineEditorOpsContextValue,
    34	} from '@/tools/video-editor/hooks/useTimelineState.types.ts';
    35	import type { AssetRegistryEntry, TimelineClip, TrackKind } from '@/tools/video-editor/types/index.ts';
    36	import type { ManagedObjectGuard, ManagedObjectInfo } from '@/tools/video-editor/lib/managed-object-guard';
    37	import { detachManagedApp } from '@/tools/video-editor/lib/managed-object-guard';
    38	
    39	export type TimelineCommandErrorCode =
    40	  | 'editor_not_mounted'
    41	  | 'timeline_unavailable'
    42	  | 'clip_not_found'
    43	  | 'track_not_found'
    44	  | 'asset_not_found'
    45	  | 'unsupported_asset_type'
    46	  | 'invalid_argument'
    47	  | 'pinned_group_edit_blocked'
    48	  | 'managed_object_blocked'
    49	  | 'mutation_failed'
    50	  | 'asset_registration_failed';
    51	
    52	export interface TimelineCommandError {
    53	  code: TimelineCommandErrorCode;
    54	  message: string;
    55	  level?: string;
    56	  issues?: unknown[];
    57	  cause?: unknown;
    58	  /** Managed-object metadata when code is 'managed_object_blocked'. */
    59	  managedInfo?: ManagedObjectInfo;
    60	}
    61	
    62	export type TimelineCommandResult<T> =
    63	  | { ok: true; data: T }
    64	  | { ok: false; error: TimelineCommandError };
    65	
    66	export interface AddClipCommandInput {
    67	  assetId: string;
    68	  time?: number;
    69	  trackId?: string;
    70	  forceNewTrack?: boolean;
    71	  insertAtTop?: boolean;
    72	  clipSpanSeconds?: number | null;
    73	  afterClipId?: string;
    74	}
    75	
    76	export interface UpdateClipCommandInput {
    77	  clipId: string;
    78	  patch: Partial<Omit<TimelineClip, 'id'>>;
    79	}
    80	
    81	export interface MoveClipCommandInput {
    82	  clipId: string;
    83	  trackId?: string;
    84	  time?: number;
    85	}
    86	
    87	export interface TrimClipCommandInput {
    88	  clipId: string;
    89	  startTime?: number;
    90	  endTime?: number;
    91	}
    92	
    93	export interface SplitClipCommandInput {
    94	  clipId: string;
    95	  time: number;
    96	}
    97	
    98	export interface DeleteClipCommandInput {
    99	  clipId: string;
   100	  allowPinnedGroupDelete?: boolean;
   101	}
   102	
   103	export interface AddTrackCommandInput {
   104	  kind: TrackKind;
   105	  index?: number;
   106	}
   107	
   108	export interface MoveTrackCommandInput {
   109	  trackId: string;
   110	  overTrackId: string;
   111	}
   112	
   113	export type RegisterAssetCommandInput =
   114	  | {
   115	      assetId: string;
   116	      entry: AssetRegistryEntry;
   117	      sourceUrl?: string;
   118	    }
   119	  | {
   120	      assetId?: string;

exec
/bin/zsh -lc "nl -ba src/tools/video-editor/lib/timeline-patch.ts | sed -n '1,260p'; nl -ba src/tools/video-editor/lib/timeline-patch.ts | sed -n '900,1040p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
     1	/**
     2	 * TimelinePatch pure validation, compilation, and preview.
     3	 *
     4	 * Validates, compiles, and previews TimelinePatch batches against the M3
     5	 * public contract types defined in @reigh/editor-sdk.  This module is
     6	 * intentionally pure — it does not import DataProvider, useTimelineCommit,
     7	 * or any editor-internal mutation / store / provider machinery.
     8	 *
     9	 * Compilation materializes a validated patch through the existing
    10	 * config/row serialization paths (rowsToConfig, configToRows,
    11	 * buildDataFromCurrentRegistry) to produce nextData and a semantic diff
    12	 * without committing.
    13	 *
    14	 * @publicContract
    15	 */
    16	
    17	import type {
    18	  DiagnosticSeverity,
    19	  TimelinePatch,
    20	  TimelinePatchAnyOpFamily,
    21	  TimelinePatchDiagnostic,
    22	  TimelinePatchOperation,
    23	  TimelinePatchValidationResult,
    24	  TimelineDiff,
    25	  TimelineDiffEntry,
    26	  TimelineDiffGranularity,
    27	  TimelineDiffKind,
    28	  TimelinePreviewResult,
    29	  ProjectDataLimitDetail,
    30	} from '@/sdk/index';
    31	
    32	import {
    33	  validateExtensionId,
    34	  EXTENSION_PROJECT_DATA_LIMITS,
    35	} from '@/sdk/index';
    36	
    37	import {
    38	  configToRows,
    39	  rowsToConfig,
    40	  assembleTimelineData,
    41	  type TimelineData,
    42	  type ClipMeta,
    43	  type ClipOrderMap,
    44	} from '@/tools/video-editor/lib/timeline-data';
    45	
    46	import type { TimelineEditMutation } from '@/tools/video-editor/hooks/useTimelineCommit';
    47	
    48	import { buildDataFromCurrentRegistry } from '@/tools/video-editor/lib/timeline-save-utils';
    49	
    50	import type {
    51	  TimelineClip,
    52	  TimelineClipShaderMetadata,
    53	  TimelinePostprocessShaderMetadata,
    54	  TrackDefinition,
    55	} from '@/tools/video-editor/types/index';
    56	
    57	import {
    58	  TIMELINE_POSTPROCESS_SHADER_APP_KEY,
    59	  assignTimelineClipShader,
    60	  assignTimelinePostprocessShader,
    61	} from '@/tools/video-editor/lib/timeline-domain';
    62	
    63	
    64	
    65	// ---------------------------------------------------------------------------
    66	// Reserved operation families
    67	// ---------------------------------------------------------------------------
    68	
    69	/** Operation families that are validated but deferred (not executed in M3). */
    70	const RESERVED_OPS: ReadonlySet<TimelinePatchAnyOpFamily> = new Set([
    71	  'clip.split',
    72	  'clip.slice',
    73	]);
    74	
    75	/**
    76	 * Active operation families that the validator must accept.
    77	 * The full set is also defined in the SDK contract; this module mirrors it
    78	 * so validation is self-contained.
    79	 */
    80	const ACTIVE_OPS: ReadonlySet<TimelinePatchAnyOpFamily> = new Set([
    81	  'clip.add',
    82	  'clip.update',
    83	  'clip.remove',
    84	  'clip.move',
    85	  'track.add',
    86	  'track.update',
    87	  'track.remove',
    88	  'asset.update',
    89	  'asset.remove',
    90	  'app.update',
    91	  'project-data.write',
    92	  'project-data.delete',
    93	  'extension.noop',
    94	]);
    95	
    96	const ALL_KNOWN_OPS: ReadonlySet<TimelinePatchAnyOpFamily> = new Set([
    97	  ...Array.from(ACTIVE_OPS),
    98	  ...Array.from(RESERVED_OPS),
    99	]);
   100	
   101	// ---------------------------------------------------------------------------
   102	// Helpers
   103	// ---------------------------------------------------------------------------
   104	
   105	function diag(
   106	  severity: DiagnosticSeverity,
   107	  code: `timeline-patch/${string}`,
   108	  message: string,
   109	  overrides: Partial<TimelinePatchDiagnostic> = {},
   110	): TimelinePatchDiagnostic {
   111	  return { severity, code, message, ...overrides };
   112	}
   113	
   114	/** True when the extension ID syntax matches the SDK contract. */
   115	function isValidExtensionId(id: string): boolean {
   116	  return validateExtensionId(id).length === 0;
   117	}
   118	
   119	// ---------------------------------------------------------------------------
   120	// Per-family payload validators
   121	// ---------------------------------------------------------------------------
   122	
   123	function validateClipAdd(
   124	  op: TimelinePatchOperation,
   125	  idx: number,
   126	): TimelinePatchDiagnostic[] {
   127	  const diags: TimelinePatchDiagnostic[] = [];
   128	  const p = op.payload;
   129	  if (p && p.track !== undefined && typeof p.track !== 'string') {
   130	    diags.push(
   131	      diag('error', 'timeline-patch/invalid-payload', 'clip.add: payload.track must be a string', {
   132	        operationIndex: idx,
   133	        op: op.op,
   134	        target: op.target,
   135	        detail: { key: 'track', expected: 'string', actual: typeof p.track },
   136	      }),
   137	    );
   138	  }
   139	  if (p && p.at !== undefined && typeof p.at !== 'number') {
   140	    diags.push(
   141	      diag('error', 'timeline-patch/invalid-payload', 'clip.add: payload.at must be a number', {
   142	        operationIndex: idx,
   143	        op: op.op,
   144	        target: op.target,
   145	        detail: { key: 'at', expected: 'number', actual: typeof p.at },
   146	      }),
   147	    );
   148	  }
   149	  if (p && p.clipType !== undefined && typeof p.clipType !== 'string') {
   150	    diags.push(
   151	      diag('error', 'timeline-patch/invalid-payload', 'clip.add: payload.clipType must be a string', {
   152	        operationIndex: idx,
   153	        op: op.op,
   154	        target: op.target,
   155	        detail: { key: 'clipType', expected: 'string', actual: typeof p.clipType },
   156	      }),
   157	    );
   158	  }
   159	  return diags;
   160	}
   161	
   162	function validateClipUpdate(
   163	  op: TimelinePatchOperation,
   164	  idx: number,
   165	): TimelinePatchDiagnostic[] {
   166	  const diags: TimelinePatchDiagnostic[] = [];
   167	  const p = op.payload;
   168	
   169	  // Validate mode if present
   170	  if (p && p.mode !== undefined) {
   171	    if (p.mode !== 'merge' && p.mode !== 'replace') {
   172	      diags.push(
   173	        diag('error', 'timeline-patch/invalid-payload', 'clip.update: payload.mode must be "merge" or "replace"', {
   174	          operationIndex: idx,
   175	          op: op.op,
   176	          target: op.target,
   177	          detail: { key: 'mode', expected: '"merge" | "replace"', actual: p.mode },
   178	        }),
   179	      );
   180	    }
   181	  }
   182	
   183	  // clip.update should have at least one updateable field (not just mode)
   184	  const updateableKeys = p ? Object.keys(p).filter((k) => k !== 'mode') : [];
   185	  if (!p || updateableKeys.length === 0) {
   186	    diags.push(
   187	      diag('warning', 'timeline-patch/empty-payload', 'clip.update: payload has no updateable fields', {
   188	        operationIndex: idx,
   189	        op: op.op,
   190	        target: op.target,
   191	      }),
   192	    );
   193	  }
   194	  return diags;
   195	}
   196	
   197	function validateClipMove(
   198	  op: TimelinePatchOperation,
   199	  idx: number,
   200	): TimelinePatchDiagnostic[] {
   201	  const diags: TimelinePatchDiagnostic[] = [];
   202	  const p = op.payload;
   203	
   204	  // At least one of track, at, before, after must be present
   205	  if (!p || (p.track === undefined && p.at === undefined && p.before === undefined && p.after === undefined)) {
   206	    diags.push(
   207	      diag('error', 'timeline-patch/invalid-payload', 'clip.move: payload must contain track, at, before, and/or after', {
   208	        operationIndex: idx,
   209	        op: op.op,
   210	        target: op.target,
   211	      }),
   212	    );
   213	  }
   214	  if (p) {
   215	    if (p.track !== undefined && typeof p.track !== 'string') {
   216	      diags.push(
   217	        diag('error', 'timeline-patch/invalid-payload', 'clip.move: payload.track must be a string', {
   218	          operationIndex: idx,
   219	          op: op.op,
   220	          target: op.target,
   221	          detail: { key: 'track', expected: 'string', actual: typeof p.track },
   222	        }),
   223	      );
   224	    }
   225	    if (p.at !== undefined && typeof p.at !== 'number') {
   226	      diags.push(
   227	        diag('error', 'timeline-patch/invalid-payload', 'clip.move: payload.at must be a number', {
   228	          operationIndex: idx,
   229	          op: op.op,
   230	          target: op.target,
   231	          detail: { key: 'at', expected: 'number', actual: typeof p.at },
   232	        }),
   233	      );
   234	    }
   235	    if (p.before !== undefined && typeof p.before !== 'string') {
   236	      diags.push(
   237	        diag('error', 'timeline-patch/invalid-payload', 'clip.move: payload.before must be a string (clip ID)', {
   238	          operationIndex: idx,
   239	          op: op.op,
   240	          target: op.target,
   241	          detail: { key: 'before', expected: 'string', actual: typeof p.before },
   242	        }),
   243	      );
   244	    }
   245	    if (p.after !== undefined && typeof p.after !== 'string') {
   246	      diags.push(
   247	        diag('error', 'timeline-patch/invalid-payload', 'clip.move: payload.after must be a string (clip ID)', {
   248	          operationIndex: idx,
   249	          op: op.op,
   250	          target: op.target,
   251	          detail: { key: 'after', expected: 'string', actual: typeof p.after },
   252	        }),
   253	      );
   254	    }
   255	    if (p.before !== undefined && p.after !== undefined && p.before === p.after) {
   256	      diags.push(
   257	        diag('warning', 'timeline-patch/invalid-payload', 'clip.move: payload.before and payload.after cannot be the same clip', {
   258	          operationIndex: idx,
   259	          op: op.op,
   260	          target: op.target,
   900	 * a semantic TimelineDiff, and the set of affected object IDs.
   901	 *
   902	 * **It does not commit** — the caller is responsible for feeding the
   903	 * returned `mutation` into `applyEdit` or `nextData` into `commitData`.
   904	 *
   905	 * Reserved operations (`clip.split`, `clip.slice`) are skipped during
   906	 * compilation (they produce warning diagnostics but no diff entries).
   907	 *
   908	 * @param patch  The patch to compile (must pass validation).
   909	 * @param data   Current canonical TimelineData snapshot.
   910	 * @returns A {@link TimelinePatchCompileResult}.
   911	 */
   912	export function compileTimelinePatch(
   913	  patch: TimelinePatch,
   914	  data: TimelineData,
   915	): TimelinePatchCompileResult {
   916	  const validation = validateTimelinePatch(patch);
   917	
   918	  // If validation produced errors, refuse to compile.
   919	  if (!validation.valid) {
   920	    return {
   921	      valid: false,
   922	      nextData: null,
   923	      mutation: null,
   924	      diff: {
   925	        version: patch.version,
   926	        entries: [],
   927	        affectedObjectIds: [],
   928	      },
   929	      diagnostics: validation.diagnostics,
   930	    };
   931	  }
   932	
   933	  // ── Clone mutable working copies ──────────────────────────────────────
   934	  const clips: TimelineClip[] = data.config.clips.map((c) => ({ ...c, app: c.app ? { ...c.app } : undefined }));
   935	  let tracks: TrackDefinition[] = (data.config.tracks ?? data.tracks).map((t) => ({ ...t, app: t.app ? { ...t.app } : undefined }));
   936	  const meta: Record<string, ClipMeta> = {};
   937	  for (const [id, m] of Object.entries(data.meta)) {
   938	    meta[id] = { ...m };
   939	  }
   940	  const clipOrder: ClipOrderMap = {};
   941	  for (const [trackId, ids] of Object.entries(data.clipOrder)) {
   942	    clipOrder[trackId] = [...ids];
   943	  }
   944	
   945	  // Working config.app clone (extension project-data lives here per SD2).
   946	  const configApp: Record<string, unknown> = data.config.app
   947	    ? { ...data.config.app }
   948	    : {};
   949	
   950	  // Track-level app data clone
   951	  const trackAppSnapshots = new Map<string, Record<string, unknown> | undefined>();
   952	  for (const t of tracks) {
   953	    trackAppSnapshots.set(t.id, t.app ? { ...t.app } : undefined);
   954	  }
   955	
   956	  const diffEntries: TimelineDiffEntry[] = [];
   957	  const affectedIds = new Set<string>();
   958	  const compileDiags: TimelinePatchDiagnostic[] = [...validation.diagnostics];
   959	
   960	  const hasReservedOps = patch.operations.some(
   961	    (op) => RESERVED_OPS.has(op.op as TimelinePatchAnyOpFamily),
   962	  );
   963	
   964	  // ── Sort operations by order field (stable) ───────────────────────────
   965	  //   - Operations with explicit `order` are applied before those without.
   966	  //   - Ties on `order` are broken by original array position (stable sort).
   967	  //   - Operations without `order` are applied last in original order.
   968	  //   - Negative orders are allowed and sorted naturally.
   969	  const indexedOps = patch.operations.map((op, originalIndex) => ({
   970	    op,
   971	    originalIndex,
   972	    hasOrder: op.order !== undefined,
   973	  }));
   974	
   975	  // Stable sort: operations with order first (ascending), then without order
   976	  const sortedOps = [...indexedOps].sort((a, b) => {
   977	    if (a.hasOrder && !b.hasOrder) return -1;
   978	    if (!a.hasOrder && b.hasOrder) return 1;
   979	    if (a.hasOrder && b.hasOrder) {
   980	      const diff = (a.op.order as number) - (b.op.order as number);
   981	      if (diff !== 0) return diff;
   982	    }
   983	    // Same order or both without order — preserve original position
   984	    return a.originalIndex - b.originalIndex;
   985	  });
   986	
   987	  // ── Apply each operation to the working copies ─────────────────────────
   988	  for (let i = 0; i < sortedOps.length; i++) {
   989	    const { op, originalIndex } = sortedOps[i];
   990	    const family = op.op as TimelinePatchAnyOpFamily;
   991	
   992	    // Reserved ops — skip execution, they only produce warnings.
   993	    if (RESERVED_OPS.has(family)) {
   994	      continue;
   995	    }
   996	
   997	    switch (family) {
   998	      // ── clip.add ──────────────────────────────────────────────────────
   999	      case 'clip.add': {
  1000	        const track = (op.payload?.track as string) ?? tracks[0]?.id ?? 'V1';
  1001	        const at = (op.payload?.at as number) ?? 0;
  1002	        const clipType = op.payload?.clipType as string | undefined;
  1003	
  1004	        const newClip: TimelineClip = {
  1005	          id: op.target,
  1006	          at,
  1007	          track,
  1008	        };
  1009	        if (clipType !== undefined) newClip.clipType = clipType;
  1010	
  1011	        // Ensure track exists
  1012	        if (!tracks.some((t) => t.id === track)) {
  1013	          compileDiags.push(
  1014	            diag('warning', 'timeline-patch/target-not-found', `clip.add: track "${track}" not found — auto-creating visual track`, {
  1015	              operationIndex: originalIndex,
  1016	              op: family,
  1017	              target: op.target,
  1018	              detail: { missingTrack: track, autoCreated: true },
  1019	            }),
  1020	          );
  1021	          const newTrack: TrackDefinition = { id: track, kind: 'visual', label: track };
  1022	          tracks = [...tracks, newTrack];
  1023	          clipOrder[track] = [];
  1024	          trackAppSnapshots.set(track, undefined);
  1025	        }
  1026	
  1027	        // Ensure clipOrder entry exists for track
  1028	        if (!clipOrder[track]) {
  1029	          clipOrder[track] = [];
  1030	        }
  1031	
  1032	        // Append to clips and clipOrder
  1033	        clips.push(newClip);
  1034	        clipOrder[track] = [...clipOrder[track], op.target];
  1035	
  1036	        // Minimal meta
  1037	        meta[op.target] = {
  1038	          track,
  1039	          clipType: clipType as TimelineClip['clipType'],
  1040	        };

exec
/bin/zsh -lc "for f in src/tools/video-editor/commands/index.ts src/tools/video-editor/commands/timelineData.ts src/tools/video-editor/commands/media.ts src/tools/video-editor/commands/provisioning.ts src/tools/video-editor/commands/runner.ts src/tools/video-editor/commands/types.ts; do printf '\\nFILE %s\\n' \""'$f"; rg -n "target|shader|live|material|sourceRef|outputFormat|timeline|apply|mutation|command|params" "$f"; done' in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:

FILE src/tools/video-editor/commands/index.ts
2:  applyTimelineCommandEffect,
9:  applyProvisionedMediaCommand,
10:  applyProvisionedMediaCommandToConfig,
14:  materializeProvisionedMediaCommand,
25:} from './timelineData.ts';

FILE src/tools/video-editor/commands/timelineData.ts
2:import { assembleTimelineData, type TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';

FILE src/tools/video-editor/commands/media.ts
2:import { getNextClipId, type TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
4:import { applyTimelineCommandEffect, createTimelineCommandRunner } from './runner.ts';
5:import { buildTimelineCommandData } from './timelineData.ts';
157:    mutation: {
240:    mutation: {
257:    const { trackId, at, asset } = context.command.payload ?? {};
258:    errors.push(...validateProvisionedAsset(asset, `$.commands[${context.commandIndex}].payload.asset`));
262:        path: `$.commands[${context.commandIndex}].payload.trackId`,
272:        path: `$.commands[${context.commandIndex}].payload.trackId`,
280:        path: `$.commands[${context.commandIndex}].payload.at`,
289:          path: `$.commands[${context.commandIndex}].payload.asset.mediaType`,
297:          path: `$.commands[${context.commandIndex}].payload.asset.mediaType`,
306:  dryRun: (context) => buildAddMediaCommandEffect(context.currentData, context.command.payload!),
307:  apply: (context) => buildAddMediaCommandEffect(context.currentData, context.command.payload!),
315:    const { clipId, asset } = context.command.payload ?? {};
316:    errors.push(...validateProvisionedAsset(asset, `$.commands[${context.commandIndex}].payload.asset`));
320:        path: `$.commands[${context.commandIndex}].payload.clipId`,
330:        path: `$.commands[${context.commandIndex}].payload.clipId`,
339:        path: `$.commands[${context.commandIndex}].payload.clipId`,
349:          path: `$.commands[${context.commandIndex}].payload.asset.mediaType`,
357:          path: `$.commands[${context.commandIndex}].payload.asset.mediaType`,
366:  dryRun: (context) => buildSwapMediaCommandEffect(context.currentData, context.command.payload!),
367:  apply: (context) => buildSwapMediaCommandEffect(context.currentData, context.command.payload!),
369:    const clip = context.currentData.resolvedConfig.clips.find((candidate) => candidate.id === context.command.payload?.clipId);
403:  result: ReturnType<typeof mediaCommandRunner.apply>,
409:export const applyProvisionedMediaCommandToConfig = (
412:  command: AddMediaCommand | SwapMediaCommand,
415:  const result = mediaCommandRunner.apply(data, { commands: [command] });
422:    result: result.commandResults[0]?.summary ?? 'Applied media command.',
428:  command: AddMediaCommand | SwapMediaCommand,
430:  return mediaCommandRunner.dryRun(currentData, { commands: [command] });
433:export const applyProvisionedMediaCommand = (
435:  command: AddMediaCommand | SwapMediaCommand,
437:  const result = mediaCommandRunner.apply(currentData, { commands: [command] });
444:    commandResult: result.commandResults[0],
448:export const materializeProvisionedMediaCommand = (
452:  return applyTimelineCommandEffect(currentData, effect);

FILE src/tools/video-editor/commands/provisioning.ts

FILE src/tools/video-editor/commands/runner.ts
3:import { buildDataFromCurrentRegistry } from '@/tools/video-editor/lib/timeline-save-utils.ts';
9:} from '@/tools/video-editor/lib/timeline-data.ts';
76:  commandIndex: number,
77:): { command: TimelineCommand | null; errors: TimelineCommandValidationError[] } => {
80:      command: null,
82:        path: `$.commands[${commandIndex}]`,
83:        code: 'invalid_command',
93:      path: `$.commands[${commandIndex}].type`,
94:      code: 'invalid_command_type',
103:      path: `$.commands[${commandIndex}].payload`,
104:      code: 'invalid_command_payload',
109:  if (input.commandId !== undefined && typeof input.commandId !== 'string') {
111:      path: `$.commands[${commandIndex}].commandId`,
112:      code: 'invalid_command_id',
113:      message: 'commandId must be a string when present.',
119:      path: `$.commands[${commandIndex}].metadata`,
120:      code: 'invalid_command_metadata',
126:    return { command: null, errors };
130:    command: {
133:      ...(typeof input.commandId === 'string' ? { commandId: input.commandId } : {}),
143:  if (isRecord(input) && Array.isArray(input.commands)) {
155:    const commands = input.commands.map((entry, commandIndex) => {
156:      const normalized = normalizeCommand(entry, commandIndex);
158:      return normalized.command;
161:    if (input.commands.length === 0) {
163:        path: '$.commands',
165:        message: 'Transaction must include at least one command.',
172:        commands,
181:      commands: normalized.command ? [normalized.command] : [],
191:  code: error.code === 'invalid_command' || error.code.startsWith('invalid_command_')
192:    ? 'invalid_command'
202:  params: Omit<TimelineCommandError, 'path'> & { path?: string },
204:  path: params.path ?? '$',
205:  ...params,
226:export const applyTimelineCommandEffect = (
230:  switch (effect.mutation.type) {
232:      validateSerializedConfig(effect.mutation.data.config);
233:      return effect.mutation.data;
236:      validateSerializedConfig(effect.mutation.config);
239:        buildDataFromCurrentRegistry(effect.mutation.config, current),
244:        effect.mutation.resolvedConfig,
245:        effect.mutation.pinnedShotGroupsOverride ?? current.config.pinnedShotGroups,
257:          withPinnedShotGroups(current.config, effect.mutation.pinnedShotGroups),
265:      if (effect.mutation.metaUpdates) {
266:        for (const [clipId, patch] of Object.entries(effect.mutation.metaUpdates)) {
273:      if (effect.mutation.metaDeletes) {
274:        for (const clipId of effect.mutation.metaDeletes) {
280:        effect.mutation.rows,
283:        effect.mutation.clipOrderOverride
284:          ?? buildTrackClipOrder(current.tracks, current.clipOrder, effect.mutation.metaDeletes),
286:        effect.mutation.pinnedShotGroupsOverride ?? current.config.pinnedShotGroups,
291:        { ...current, rows: effect.mutation.rows, meta: nextMeta } as TimelineData,
307:      throw new Error(`Duplicate timeline command descriptor registered for "${descriptor.type}".`);
335:  const commandResults: TimelineCommandStepResult<TCommand>[] = [];
338:  for (let commandIndex = 0; commandIndex < normalizedTransaction.commands.length; commandIndex += 1) {
339:    const command = normalizedTransaction.commands[commandIndex];
340:    const descriptor = registry.get(command.type);
344:        code: 'unknown_command',
345:        message: `No timeline command descriptor is registered for "${command.type}".`,
346:        path: `$.commands[${commandIndex}].type`,
348:        commandType: command.type,
349:        commandId: command.commandId,
350:        commandIndex,
352:      commandResults.push({
353:        command,
354:        commandIndex,
364:        command,
366:        commandIndex,
368:        previousResults: commandResults,
376:            message: `Timeline command "${command.type}" failed validation.`,
377:            path: `$.commands[${commandIndex}]`,
379:            commandType: command.type,
380:            commandId: command.commandId,
381:            commandIndex,
385:          commandResults.push({
386:            command,
387:            commandIndex,
396:          const effect = runMode === 'apply'
397:            ? descriptor.apply(context)
399:          const nextData = applyTimelineCommandEffect(workingData, effect);
418:              message: `Timeline command "${command.type}" could not produce an inverse transaction: ${asErrorMessage(error)}`,
419:              path: `$.commands[${commandIndex}]`,
421:              commandType: command.type,
422:              commandId: command.commandId,
423:              commandIndex,
425:            commandResults.push({
426:              command,
427:              commandIndex,
441:          commandResults.push({
442:            command,
443:            commandIndex,
444:            status: runMode === 'apply'
459:          code: runMode === 'apply' ? 'apply_failed' : 'dry_run_failed',
460:          message: `Timeline command "${command.type}" failed during ${runMode === 'apply' ? 'apply' : 'dry run'}: ${asErrorMessage(error)}`,
461:          path: `$.commands[${commandIndex}]`,
463:          commandType: command.type,
464:          commandId: command.commandId,
465:          commandIndex,
467:        commandResults.push({
468:          command,
469:          commandIndex,
489:  const succeededResults = commandResults.filter((result) => result.error === undefined);
495:    .flatMap((result) => result.inverse?.commands ?? []);
500:        commands: inverseCommands,
505:    kind: 'command',
507:    commandTypes: committedResults.map((result) => result.command.type),
508:    commandIds: committedResults
509:      .map((result) => result.command.commandId)
510:      .filter((commandId): commandId is string => typeof commandId === 'string'),
531:    commandResults,
555:      commandResults: [],
558:        kind: 'command',
560:        commandTypes: [],
561:        commandIds: [],
596:    apply: (data, input, options) => runTimelineCommands(data, input, registry, 'apply', options),

FILE src/tools/video-editor/commands/types.ts
1:import type { ClipMeta, ClipOrderMap, TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
2:import type { TimelineRow } from '@/tools/video-editor/types/timeline-canvas.ts';
14:  commandId?: string;
20:  commands: readonly TCommand[];
28:export type TimelineCommandRunMode = 'validate' | 'dry_run' | 'apply';
38:  | 'invalid_command'
40:  | 'unknown_command'
43:  | 'apply_failed'
51:  commandType?: string;
52:  commandId?: string;
53:  commandIndex?: number;
86:  mutation: TimelineCommandMutation;
92:  command: TCommand;
94:  commandIndex: number;
100:  command: TCommand;
104:  commandIndex: number;
115:  apply: (context: TimelineCommandContext<TCommand>) => TimelineCommandEffect;
131:  command: TCommand;
132:  commandIndex: number;
147:  kind: 'command';
149:  commandTypes: string[];
150:  commandIds: string[];
169:  commandResults: TimelineCommandStepResult<TCommand>[];
191:  apply: (

exec
/bin/zsh -lc "nl -ba src/tools/video-editor/keyframes/index.ts | sed -n '1580,1660p'; nl -ba src/tools/video-editor/keyframes/index.ts | sed -n '1,180p'" in /Users/peteromalley/Documents/reigh-workspace/reigh-app
 succeeded in 0ms:
     1	/**
     2	 * M9: Deterministic keyframe utilities.
     3	 *
     4	 * Provides linear/hold interpolation, ParameterDefinition validation
     5	 * diagnostics for keyframe values, resolveAnimatedParams() which
     6	 * computes interpolated parameter values at a given time from
     7	 * host-owned keyframe data, and automation recorder utilities that
     8	 * quantize sampled control values into deterministic keyframes,
     9	 * downsample by tolerance, preserve hold semantics, and reject
    10	 * non-serializable or schema-invalid values.
    11	 *
    12	 * All functions are deterministic — same inputs always produce same outputs.
    13	 */
    14	
    15	import type {
    16	  ClipKeyframe,
    17	  KeyframeInterpolation,
    18	  ParameterDefinition,
    19	  ParameterSchema,
    20	} from '../types/index.ts';
    21	
    22	// ---------------------------------------------------------------------------
    23	// InterpolatedParam (host-internal shape)
    24	// ---------------------------------------------------------------------------
    25	
    26	export interface InterpolatedParam {
    27	  /** The parameter name. */
    28	  name: string;
    29	  /** The interpolated value at the requested time. */
    30	  value: number | string | boolean;
    31	}
    32	
    33	// ---------------------------------------------------------------------------
    34	// Validation diagnostics
    35	// ---------------------------------------------------------------------------
    36	
    37	export interface KeyframeValidationDiagnostic {
    38	  severity: 'error' | 'warning';
    39	  code: string;
    40	  message: string;
    41	  detail?: Record<string, unknown>;
    42	}
    43	
    44	// ---------------------------------------------------------------------------
    45	// Interpolation helpers
    46	// ---------------------------------------------------------------------------
    47	
    48	/**
    49	 * Linearly interpolate between two values.
    50	 *
    51	 * For numbers: standard lerp: a + (b - a) * t.
    52	 * For strings/booleans: behaves like hold — returns `a` when t < 1, `b` when t >= 1.
    53	 * This is deterministic and matches the host's guarantee that non-numeric
    54	 * parameters only meaningfully animate with hold interpolation.
    55	 */
    56	export function interpolateLinear(
    57	  a: number | string | boolean,
    58	  b: number | string | boolean,
    59	  t: number,
    60	): number | string | boolean {
    61	  if (typeof a === 'number' && typeof b === 'number') {
    62	    return a + (b - a) * t;
    63	  }
    64	  // Non-numeric values: discrete step at t=1 boundary
    65	  return t < 1 ? a : b;
    66	}
    67	
    68	/**
    69	 * Hold (step) interpolation.
    70	 *
    71	 * Returns `a` for any t < 1, returns `b` when t >= 1.
    72	 */
    73	export function interpolateHold(
    74	  a: number | string | boolean,
    75	  b: number | string | boolean,
    76	  t: number,
    77	): number | string | boolean {
    78	  return t < 1 ? a : b;
    79	}
    80	
    81	/**
    82	 * Interpolate between two keyframe values given an interpolation mode.
    83	 */
    84	export function interpolatePair(
    85	  a: number | string | boolean,
    86	  b: number | string | boolean,
    87	  t: number,
    88	  mode: KeyframeInterpolation,
    89	): number | string | boolean {
    90	  if (mode === 'hold') {
    91	    return interpolateHold(a, b, t);
    92	  }
    93	  return interpolateLinear(a, b, t);
    94	}
    95	
    96	// ---------------------------------------------------------------------------
    97	// Value coercion / validation
    98	// ---------------------------------------------------------------------------
    99	
   100	const isHexColor = (value: string): boolean => /^#[0-9a-fA-F]{3,8}$/.test(value);
   101	
   102	/**
   103	 * Validate a single keyframe value against a parameter definition.
   104	 *
   105	 * Returns diagnostics for type mismatches, out-of-range values,
   106	 * invalid colors, invalid select options, and invalid audio-binding shapes.
   107	 * An empty array means the value is valid.
   108	 */
   109	export function validateKeyframeValue(
   110	  value: unknown,
   111	  definition: ParameterDefinition,
   112	): KeyframeValidationDiagnostic[] {
   113	  const diags: KeyframeValidationDiagnostic[] = [];
   114	  const ctx = `parameter "${definition.name}"`;
   115	
   116	  // Null / undefined values are invalid for all types
   117	  if (value === null || value === undefined) {
   118	    diags.push({
   119	      severity: 'error',
   120	      code: 'keyframes/invalid-null-value',
   121	      message: `${ctx}: keyframe value must not be null or undefined.`,
   122	      detail: { parameterName: definition.name, value },
   123	    });
   124	    return diags;
   125	  }
   126	
   127	  // Type-specific validation
   128	  switch (definition.type) {
   129	    case 'number': {
   130	      if (typeof value !== 'number' || Number.isNaN(value) || !Number.isFinite(value)) {
   131	        diags.push({
   132	          severity: 'error',
   133	          code: 'keyframes/invalid-number-value',
   134	          message: `${ctx}: expected finite number, got ${typeof value === 'number' ? (Number.isNaN(value) ? 'NaN' : 'Infinity') : typeof value}.`,
   135	          detail: { parameterName: definition.name, value, expectedType: 'number' },
   136	        });
   137	        return diags;
   138	      }
   139	      // Range validation
   140	      if (definition.min !== undefined && value < definition.min) {
   141	        diags.push({
   142	          severity: 'warning',
   143	          code: 'keyframes/value-below-min',
   144	          message: `${ctx}: value ${value} is below min ${definition.min}.`,
   145	          detail: { parameterName: definition.name, value, min: definition.min },
   146	        });
   147	      }
   148	      if (definition.max !== undefined && value > definition.max) {
   149	        diags.push({
   150	          severity: 'warning',
   151	          code: 'keyframes/value-above-max',
   152	          message: `${ctx}: value ${value} is above max ${definition.max}.`,
   153	          detail: { parameterName: definition.name, value, max: definition.max },
   154	        });
   155	      }
   156	      break;
   157	    }
   158	
   159	    case 'boolean': {
   160	      if (typeof value !== 'boolean') {
   161	        diags.push({
   162	          severity: 'error',
   163	          code: 'keyframes/invalid-boolean-value',
   164	          message: `${ctx}: expected boolean, got ${typeof value}.`,
   165	          detail: { parameterName: definition.name, value, expectedType: 'boolean' },
   166	        });
   167	      }
   168	      break;
   169	    }
   170	
   171	    case 'select': {
   172	      if (typeof value !== 'string') {
   173	        diags.push({
   174	          severity: 'error',
   175	          code: 'keyframes/invalid-select-value',
   176	          message: `${ctx}: expected string for select, got ${typeof value}.`,
   177	          detail: { parameterName: definition.name, value, expectedType: 'string' },
   178	        });
   179	        return diags;
   180	      }

codex
I have enough evidence now: there are strong public snapshot/planner contracts, but no graph layer and several planner/export/preview adapters still derive facts directly from raw timeline/config shapes. I’ll now consolidate into the requested markdown structure.
codex
# Composition Spine Authority

## Verdict
The criticism is valid and the threat is high, but not “delete everything now” high. Current code has planner-compatible scaffolding, not a composition spine authority. Deleting old paths now would break timelines because legacy fields are still the storage/projection source for multiple fact families.

The right next move is a fact-family authority ratchet, starting with shader/ref facts as the staged M1b says.

## Current Code Reality
Current concepts:

- `TimelineSnapshot`/`TimelineReader` exist as provider-free planner input ([src/sdk/index.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/sdk/index.ts:4856), [timeline-reader.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/lib/timeline-reader.ts:303)).
- `getCapabilityRequirements(snapshot)` derives requirements from snapshot summaries ([src/sdk/index.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/sdk/index.ts:4980)).
- `planRender()` aggregates snapshot requirements, output formats, processes, shaders, material refs/statuses, render groups, request constraints, and diagnostics ([renderPlanner.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/runtime/renderPlanner.ts:918)).
- Renderability/material/artifact vocabulary exists ([renderability.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/runtime/renderability.ts:10)).
- Tests prove planner can consume `TimelineSnapshot`, but mostly as a boundary/compatibility contract, not graph authority ([timeline-reader.planner-contract.test.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:1)).

Planned only:

- `src/sdk/video/composition/**` and `src/tools/video-editor/runtime/composition/**` do not exist.
- `CompositionGraph`, graph nodes/edges, `CompositionTargetPath`, `consumes`/`animates`/`binds-live`/`requires`, graph-backed output-format routes are staged in the epic, not current code ([NORTHSTAR.md](/Users/peteromalley/Documents/reigh-workspace/reigh-app/.megaplan/initiatives/reigh-extension-composition-spine-epic/NORTHSTAR.md:5), [prep.md](/Users/peteromalley/Documents/reigh-workspace/reigh-app/.megaplan/initiatives/reigh-extension-composition-spine-epic/prep.md:19)).
- M1b is explicitly the first graph-authority handoff for shader/ref facts ([m1b-shader-graph-authority.md](/Users/peteromalley/Documents/reigh-workspace/reigh-app/.megaplan/initiatives/reigh-extension-composition-spine-epic/m1b-shader-graph-authority.md:5)).

Still legacy-authoritative fact families:

- Shader assignment: `clip.app.shader`, `config.app.shaderPostprocess` ([timeline-reader.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/lib/timeline-reader.ts:348), [exportGuard.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/runtime/exportGuard.ts:328)).
- Live bindings/targets: `clip.app.liveBindings`, `clip.params.liveBindings`, `targetParamName` ([timeline-reader.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/lib/timeline-reader.ts:186)).
- Render route: raw `clipType`, theme/generated-module shape, contributed clip records ([renderRouter.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/lib/renderRouter.ts:303)).
- Preview: raw renderer config scans live bindings, shader metadata, sequence registries, `app/params.materialRefs` ([TimelineRenderer.tsx](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/compositions/TimelineRenderer.tsx:48), [VisualClip.tsx](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/compositions/VisualClip.tsx:268)).
- Export guard: scans raw `ResolvedTimelineConfig`, then wraps diagnostics back into `planRender({ diagnostics })` ([useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:226), [useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:376)).
- Output formats: extension runtime descriptors are planner inputs, not graph contribution nodes ([useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:514)).

## Pristine End State
Authority convergence should mean:

Legacy timeline fields may persist as storage/back-compat, but planner/export/preview acceptance reads canonical graph facts. Each fact family has one projector from legacy/current storage into graph facts, one validator, one diagnostics vocabulary, and one planner/export path.

For a graph-authoritative family, tests should fail if planner/export can pass using only raw legacy fields that were not projected into graph facts.

## Recommended Work
Now:

1. Land M1b as an authority ratchet for shader/ref facts. Build `CompositionGraph` projection and make shader planner/export blockers consume graph shader/ref facts, not direct `clip.app.shader` scans.
2. Keep legacy shader fields as compatibility inputs only through the projector. Add a fixture where raw `clip.app.shader` exists but graph projection is disabled; planner/export must not treat it as authoritative.
3. Split export guard: unknown contribution scanning can remain compat for now, but shader/ref blockers should move behind graph-derived facts.
4. Add an import/usage gate forbidding `renderPlanner.ts` and new shader/ref export path from reading `clip.app.shader`, `shaderPostprocess`, or raw config.

Later:

1. M2 target-path ratchet: replace `targetParamName`/flat keys with canonical target paths.
2. M3 material/live ratchets: media-like live data must resolve to `RenderMaterial`/`RenderArtifact`; non-media to deterministic captures.
3. M7 output-format ratchet: output formats become graph contribution nodes with explicit route scope.

## Tests / Gates
- `planRender` shader/ref tests: no legacy raw config input; only graph-projected facts create shader blockers/materializer next actions.
- Export guard parity: legacy shader fields projected to graph produce identical blockers; disabling projection causes explicit “legacy-only ignored/not authoritative” failure.
- Static gate: `renderPlanner.ts` and graph-owned export modules cannot import timeline raw types or scan `app.shader`, `shaderPostprocess`, `liveBindings`, `targetParamName`.
- Fixture matrix: legacy-only, graph-only, both-agree, both-conflict, missing contribution, disabled, duplicate scope, version-incompatible.
- Route gate: no omitted route scope treated as all-routes.

## Biggest Trap
Wrapping old scanners in graph-shaped types and calling that authority. That preserves the same hidden authority, just with nicer names. The migration must move one fact family at a time from “legacy field decides” to “projector emits graph fact, graph fact decides.”
tokens used
229,351
# Composition Spine Authority

## Verdict
The criticism is valid and the threat is high, but not “delete everything now” high. Current code has planner-compatible scaffolding, not a composition spine authority. Deleting old paths now would break timelines because legacy fields are still the storage/projection source for multiple fact families.

The right next move is a fact-family authority ratchet, starting with shader/ref facts as the staged M1b says.

## Current Code Reality
Current concepts:

- `TimelineSnapshot`/`TimelineReader` exist as provider-free planner input ([src/sdk/index.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/sdk/index.ts:4856), [timeline-reader.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/lib/timeline-reader.ts:303)).
- `getCapabilityRequirements(snapshot)` derives requirements from snapshot summaries ([src/sdk/index.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/sdk/index.ts:4980)).
- `planRender()` aggregates snapshot requirements, output formats, processes, shaders, material refs/statuses, render groups, request constraints, and diagnostics ([renderPlanner.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/runtime/renderPlanner.ts:918)).
- Renderability/material/artifact vocabulary exists ([renderability.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/runtime/renderability.ts:10)).
- Tests prove planner can consume `TimelineSnapshot`, but mostly as a boundary/compatibility contract, not graph authority ([timeline-reader.planner-contract.test.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/lib/timeline-reader.planner-contract.test.ts:1)).

Planned only:

- `src/sdk/video/composition/**` and `src/tools/video-editor/runtime/composition/**` do not exist.
- `CompositionGraph`, graph nodes/edges, `CompositionTargetPath`, `consumes`/`animates`/`binds-live`/`requires`, graph-backed output-format routes are staged in the epic, not current code ([NORTHSTAR.md](/Users/peteromalley/Documents/reigh-workspace/reigh-app/.megaplan/initiatives/reigh-extension-composition-spine-epic/NORTHSTAR.md:5), [prep.md](/Users/peteromalley/Documents/reigh-workspace/reigh-app/.megaplan/initiatives/reigh-extension-composition-spine-epic/prep.md:19)).
- M1b is explicitly the first graph-authority handoff for shader/ref facts ([m1b-shader-graph-authority.md](/Users/peteromalley/Documents/reigh-workspace/reigh-app/.megaplan/initiatives/reigh-extension-composition-spine-epic/m1b-shader-graph-authority.md:5)).

Still legacy-authoritative fact families:

- Shader assignment: `clip.app.shader`, `config.app.shaderPostprocess` ([timeline-reader.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/lib/timeline-reader.ts:348), [exportGuard.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/runtime/exportGuard.ts:328)).
- Live bindings/targets: `clip.app.liveBindings`, `clip.params.liveBindings`, `targetParamName` ([timeline-reader.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/lib/timeline-reader.ts:186)).
- Render route: raw `clipType`, theme/generated-module shape, contributed clip records ([renderRouter.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/lib/renderRouter.ts:303)).
- Preview: raw renderer config scans live bindings, shader metadata, sequence registries, `app/params.materialRefs` ([TimelineRenderer.tsx](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/compositions/TimelineRenderer.tsx:48), [VisualClip.tsx](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/compositions/VisualClip.tsx:268)).
- Export guard: scans raw `ResolvedTimelineConfig`, then wraps diagnostics back into `planRender({ diagnostics })` ([useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:226), [useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:376)).
- Output formats: extension runtime descriptors are planner inputs, not graph contribution nodes ([useRenderState.ts](/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/hooks/useRenderState.ts:514)).

## Pristine End State
Authority convergence should mean:

Legacy timeline fields may persist as storage/back-compat, but planner/export/preview acceptance reads canonical graph facts. Each fact family has one projector from legacy/current storage into graph facts, one validator, one diagnostics vocabulary, and one planner/export path.

For a graph-authoritative family, tests should fail if planner/export can pass using only raw legacy fields that were not projected into graph facts.

## Recommended Work
Now:

1. Land M1b as an authority ratchet for shader/ref facts. Build `CompositionGraph` projection and make shader planner/export blockers consume graph shader/ref facts, not direct `clip.app.shader` scans.
2. Keep legacy shader fields as compatibility inputs only through the projector. Add a fixture where raw `clip.app.shader` exists but graph projection is disabled; planner/export must not treat it as authoritative.
3. Split export guard: unknown contribution scanning can remain compat for now, but shader/ref blockers should move behind graph-derived facts.
4. Add an import/usage gate forbidding `renderPlanner.ts` and new shader/ref export path from reading `clip.app.shader`, `shaderPostprocess`, or raw config.

Later:

1. M2 target-path ratchet: replace `targetParamName`/flat keys with canonical target paths.
2. M3 material/live ratchets: media-like live data must resolve to `RenderMaterial`/`RenderArtifact`; non-media to deterministic captures.
3. M7 output-format ratchet: output formats become graph contribution nodes with explicit route scope.

## Tests / Gates
- `planRender` shader/ref tests: no legacy raw config input; only graph-projected facts create shader blockers/materializer next actions.
- Export guard parity: legacy shader fields projected to graph produce identical blockers; disabling projection causes explicit “legacy-only ignored/not authoritative” failure.
- Static gate: `renderPlanner.ts` and graph-owned export modules cannot import timeline raw types or scan `app.shader`, `shaderPostprocess`, `liveBindings`, `targetParamName`.
- Fixture matrix: legacy-only, graph-only, both-agree, both-conflict, missing contribution, disabled, duplicate scope, version-incompatible.
- Route gate: no omitted route scope treated as all-routes.

## Biggest Trap
Wrapping old scanners in graph-shaped types and calling that authority. That preserves the same hidden authority, just with nicer names. The migration must move one fact family at a time from “legacy field decides” to “projector emits graph fact, graph fact decides.”
