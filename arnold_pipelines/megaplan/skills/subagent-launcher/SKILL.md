---
name: subagent-launcher
description: Launch an external model as a subagent for a second opinion, adversarial review, or delegated work. Default pathway is an agentic DeepSeek / Kimi / Zhipu GLM hermes subagent (file/web/terminal tools, one process or fanned out N-wide); also Codex (GPT-5.5), Claude via the Agent tool, and Grok via omp (same x.ai token as the grok CLI). Use for independent root-cause analysis, cross-checking your reasoning, judge/jury panels, or handing implementation to a different model.
---

# Subagent launcher (multi-model)

Dispatch work to a model other than the one driving the conversation. Two payoffs: **independence** — a *different* model's judgement, not a copy of your own — and **context hygiene** — the subagent's tool calls and reasoning stay in *its* context; only the conclusion returns to you.

Pathways:

| Pathway | Model | Invocation | Tools |
| --- | --- | --- | --- |
| **Hermes agentic** *(default)* | DeepSeek V4 (Pro/Flash), Kimi K2.7, Zhipu GLM, … | `launch_hermes_agent.py` — or `fan.py` to run N in one process | `file`, `web`, optional `terminal` |
| **Codex** | GPT-5.5 | `codex exec` (CLI) | sandboxed workspace |
| **Claude** | Claude (Opus/Sonnet/Haiku) | `launch_claude_agent.py --model=opus` or Claude Code `Agent` tool | Claude Code tools |
| **Grok via omp** | Grok 4.6 / 4.5 | `launch_omp_agent.py --model=grok-4.6` | full omp toolset (Bash, Read, Edit, …) |

**Default to the hermes agentic pathway, and to DeepSeek Flash within it** — different model family, cheap, fast, tool-using. Reach for DeepSeek Pro only when the task needs reasoning judgement; reach for Codex or Claude only when you specifically want their strengths.

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
- **Want xAI's model with the full omp toolset, no API key, billed to your grok account?** → §4 (`launch_omp_agent.py`).
- **Jury for a high-stakes call?** → fan the same prompt to Codex + hermes-DeepSeek + hermes-Kimi in parallel; divergence is the signal.
- **Bigger than ~a day or two of work?** → it's a *deliverable*, not a dispatch: run a `megaplan` (itself launched as a subagent) and size it with the **`megaplan-decision`** skill. Past ~2 weeks → an epic.
- **Already have the answer?** → don't dispatch. Subagents aren't free.

## Use the cheapest subagent that can do the job

Independence is the *why*; cost is the *which*. Default to the cheapest model that can plausibly succeed; escalate only on evidence.

1. **MiMo V2.5 Pro Ultraspeed** (`fast`, alias for `mimo:mimo-v2.5-pro-ultraspeed`) — very fast. High-volume, low-judgement work: scan files, extract facts, short first-pass research.
2. **DeepSeek V4 Flash** (`deepseek:deepseek-v4-flash`, **the default**) — non-reasoning, fast, cheap. The default for most dispatches: implementation, mechanical edits, focused investigation, verification. Escalate to Pro only on evidence that reasoning is needed.
3. **DeepSeek V4 Pro** (`deepseek:deepseek-v4-pro`) — reasoning model. Use when the task needs judgement: root-cause analysis, "is this sound", "should this merge".
4. **GPT-5.5 (Codex) or Claude** — only for *real* complexity: subtle multi-step reasoning, write-heavy implementation, the strongest adversarial review.

Two rules: **start low, escalate on evidence** (don't reach for the frontier model "to be safe"); and **prepare the context so a cheap model can win** — most "cheap model failed" cases are under-specified prompts. A moment spent scoping the task is cheaper than burning a Claude subagent on something Flash could do.

Beware the asymmetry: reasoning models handed mechanical briefs refactor (because that's what reasoning does); non-reasoning models handed architectural briefs literally execute fragments without understanding the intent. Match brief shape to model mode, not just model to task.

---

## 1. Hermes agentic (DeepSeek / Kimi / Zhipu GLM) — the default

A real tool-using agent in a non-Claude model's voice, far lighter than a `megaplan` run. It runs as a one-off **omp (Oh My Pi)** process — `omp -p --model <model> "<prompt>"` — so the agent gets omp's full toolset (Bash, Read, Edit, Glob, Grep, web search, …). No Arnold/megaplan runtime, no key pool: provider availability follows what omp has configured (`~/.omp/agent/models.yml` + stored credentials). This is the same migration `origin/omp-migration` performs for megaplan's workers (hermes SDK → omp RPC).

```bash
python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --model="deepseek:deepseek-v4-flash" \
  --toolsets="file,web" \
  --query-file=/tmp/brief.md \
  --project-dir="$PWD"
# Final response → stdout; omp progress ("Working...") → stderr.
```

Key flags:

- **`--model`** (default `deepseek:deepseek-v4-flash`). Prefix convention (translated to omp selectors):
  - `deepseek:deepseek-v4-flash` (default, non-reasoning) / `deepseek:deepseek-v4-pro` (reasoning) → `deepseek/…`
  - `kimi:kimi-k2.7-code` → `openrouter/moonshotai/kimi-latest` (nearest omp catalog row)
  - `zhipu:glm-5.2` / `zhipu:glm-4.6` → `openrouter/z-ai/glm-latest`
  - `codex:gpt-5.6-sol` / `codex:gpt-5.5` — optional `:low|:medium|:high` effort suffix (maps to omp `--thinking`) — ChatGPT-subscription Codex backend via omp's `openai-codex` provider; **no API key**
  - `grok` (shortcut) → `grok/grok-4.6` — the grok CLI-proxy provider in `~/.omp/agent/models.yml` (same x.ai token as the `grok` CLI, no API key)
  - `fast` / `mimo` / `mimo-fast` → `openrouter/xiaomi/mimo-v2-flash` (very fast MiMo path)
  - `flash` / `pro` shortcuts → the two deepseek rows
  - `openrouter:X`, `google:X`, `minimax:X`, `xai:X` → translated to the matching omp provider (`xai:` → the grok CLI-proxy provider); anything else passes through for omp fuzzy matching
- **`--toolsets`** (default `"file,web"`): omp gives the full toolset regardless — `file`/`web`/`terminal` is a superset here (native Read/Edit/Write, web search, Bash). `""` = pure chat (`--no-tools`).
- **`--query` / `--query-file`** — pass exactly one; use `--query-file` for anything past a sentence.
- **`--max-tokens`** — informational; omp uses the model's native output ceiling (don't set it).
- **`--project-dir`** — cwd for the omp process.
- **`--timeout`** (default 1800) — subprocess deadline; omp is terminated after it.

Output is **freeform text** — if you want JSON, ask for it in the prompt and parse defensively; for an *enforced* schema, use megaplan, not this pathway.

### Fan out N at once — `fan.py`

For **≥ ~5 parallel agents or programmatic batches**, `fan.py` runs one launcher subprocess per brief (`max-workers` concurrent), each an omp run. Same flags, plus a briefs directory and per-task output:

```bash
python ~/.claude/skills/subagent-launcher/fan.py \
  --briefs-dir=/tmp/briefs --output-dir=/tmp/results \
  --max-workers=5 --model="deepseek:deepseek-v4-flash" \
  --toolsets="file,web" --task-timeout=1800 --project-dir="$PWD"
# Or positional brief paths instead of --briefs-dir.
# Per-brief models: --model-map="fast:scan-*.md,pro:verdict-*.md"
```

Each brief `<stem>.md` yields `<stem>.txt` (response), `<stem>.meta.json` (status/timing/pid), `<stem>.pid` (killable task group), and an aggregate `_report.json`. Kill a running fan from another shell: `fan_kill.py --output-dir=… [--hard]`. Default `--task-timeout=1800` (30 min — forensic work with ≥10 tool calls routinely exceeds 10 min). Bump higher for very heavy briefs (e.g. `--task-timeout=3600` for cross-file audits). Each task runs in its own process group; `fan_kill.py --hard` SIGKILLs the whole tree. Below ~5 parallel, just launch `launch_hermes_agent.py` N times in parallel Bash calls — simpler.

### Use `megaplan` instead when you need

multi-phase orchestration (plan → critique → revise → execute → gate → review), schema-enforced output, persistent plan state / approval gates, or the megaplan sandbox. See *Multi-phase delegation* below.

### Liveness

The launcher forwards omp's stderr, ending with `[launch_hermes_agent] done in N.Ns`; a run stuck in "Working..." with no exit for minutes = wedged (check `--timeout`). For `fan.py`, watch `.meta.json` files appearing under `--output-dir`.

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

## 4. Grok via omp (Grok 4.6 / 4.5)

Dispatches a Grok model through **omp (Oh My Pi)**: the subagent runs as a
one-off `omp -p --model <model> "<prompt>"` process, so it gets omp's full
toolset (Bash, Read, Edit, Glob, Grep, web search, …) in Grok's voice.

```bash
python ~/.claude/skills/subagent-launcher/launch_omp_agent.py \
  --model=grok-4.6 \
  --query-file=/tmp/brief.md \
  --project-dir="$PWD" \
  --timeout=1800
```

Auth is **the same x.ai account the `grok` CLI uses** — no API key. omp's
`~/.omp/agent/models.yml` defines a `grok` provider pointing at the CLI's
`cli-chat-proxy.grok.com` proxy; the bearer token is read from
`~/.grok/auth.json` and rotated by `~/.omp/agent/grok-token.py` (OIDC refresh,
~6 h lifetime, refresh on demand — no TUI spawn). Billing and usage limits are
your grok subscription's.

- `--model` is an omp model selector: `grok/grok-4.6` (default) or fuzzy
  `grok-4.6` / `grok-4.5`. Any other omp model works too — the launcher is
  model-agnostic.
- `--auto-approve` passes omp's `--auto-approve` (unneeded for most briefs;
  `-p` mode runs tools without approval prompts).
- Ephemeral by default (`--no-session`), so one-off subagents do not clutter
  omp's session history; pass `--no-no-session` (or edit the flag) to keep a
  session.
- Caveats: the omp process caches the token for its lifetime (fine for
  6 h tokens); grok output tokens are billed through the proxy exactly like
  the CLI.

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
- **Hermes / fan.py** — stuck in "Working..." with no `[launch_hermes_agent] done` line for minutes = wedged; `--timeout` bounds it. For fan.py, watch `.meta.json` files appearing under `--output-dir`.
- **Claude Agent / launcher** — synchronous, rarely wedges; the common failure is a terse prompt → shallow hedged answer in < 30 s. Cap length and demand a position.
- **megaplan** — an "stuck" run is usually a gated step awaiting approval; `megaplan status --plan <name>`.

**Liveness ≠ correctness.** A subagent can stream for 10 minutes and still answer uselessly — read the response; there's no shortcut.

## Quick reference

```bash
# 1. Hermes agentic (default) — DeepSeek/Kimi/Zhipu GLM via omp
python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --model="deepseek:deepseek-v4-flash" --toolsets="file,web" \
  --query-file=/tmp/brief.md --project-dir="$PWD"
# Default: --model="deepseek:deepseek-v4-flash"   Very fast: --model=fast   Pro (reasoning): --model="deepseek:deepseek-v4-pro"   Kimi: --model="kimi:kimi-k2.7-code"   GLM: --model="zhipu:glm-5.2"   GPT: --model="codex:gpt-5.6-sol:high" (ChatGPT subscription, no API key)   Grok: --model=grok
# Pure chat: --toolsets=""    Fan N≥5: fan.py --briefs-dir=… --output-dir=… --max-workers=5 --task-timeout=1800

# 2. Codex — always seal stdin with </dev/null, allow 30 min
timeout 1800 codex exec --sandbox read-only "<prompt>" </dev/null              # analysis
timeout 1800 codex exec --sandbox workspace-write "<prompt>" </dev/null        # implementer
timeout 1800 codex exec --sandbox danger-full-access "<prompt>" </dev/null     # orchestrates hermes subagents (network required)
codex exec review --pr 123

# 3. Claude — explicit Opus selector via Claude CLI
python ~/.claude/skills/subagent-launcher/launch_claude_agent.py \
  --model=opus --query-file=/tmp/prompt.md --project-dir="$PWD"

# 4. Grok via omp — same x.ai token as the grok CLI, no API key
python ~/.claude/skills/subagent-launcher/launch_omp_agent.py \
  --model=grok-4.6 --query-file=/tmp/brief.md --project-dir="$PWD"

# Multi-phase: megaplan init --profile all-deepseek-pro-direct --robustness light "<task>"
```
