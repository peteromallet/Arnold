---
name: subagent-launcher
description: Launch an external model as a subagent for a second opinion, adversarial review, or delegated work. Pathways are Codex (GPT-5.x) via `codex exec`, Claude via the CLI launcher or the Agent tool, and omp-routed model specs for DeepSeek/Kimi/GLM-family work. Use for independent root-cause analysis, cross-checking your reasoning, judge/jury panels, or handing implementation to a different model.
---

# Subagent launcher (multi-model)

Dispatch work to a model other than the one driving the conversation. Two payoffs: **independence** — a *different* model's judgement, not a copy of your own — and **context hygiene** — the subagent's tool calls and reasoning stay in *its* context; only the conclusion returns to you.

Pathways:

| Pathway | Model | Invocation | Tools |
| --- | --- | --- | --- |
| **omp-routed** | DeepSeek V4 (Pro/Flash), Kimi, Zhipu GLM, … | `megaplan` phases or the resident subagent seam with an `omp:<provider>/<modelId>` spec | omp toolset |
| **Codex** | GPT-5.x | `codex exec` (CLI) | sandboxed workspace |
| **Claude** | Claude (Opus/Sonnet/Haiku) | `launch_claude_agent.py --model=opus` or Claude Code `Agent` tool | Claude Code tools |

> **⚠️ Network sandbox warning for Codex subagents**
> `codex exec` runs its subprocess with `CODEX_SANDBOX_NETWORK_DISABLED=1`. Any
> nested provider calls need outbound network to reach their APIs, so launching
> them from inside a `codex exec` subagent fails unless the outer Codex command
> runs with `--sandbox danger-full-access` (seal stdin with `</dev/null`).
>
> This network restriction does not affect Codex or Claude subagents themselves.

## Picking a pathway

- **An independent DeepSeek/Kimi/GLM subagent that reads the repo itself?** → use a `megaplan` phase or the resident subagent seam with an `omp:` model spec (e.g. `omp:deepseek/deepseek-v4-pro`, `omp:zai/glm-5.2`, `omp:kimi/kimi-k2.7-code`). The former hermes launch surface was deleted in B11; hermes-family model specs route through omp.
- **Pure chat opinion, no tools?** → same omp route with a pure-chat toolset.
- **Most-different-from-Claude judgement, or write-heavy implementation in a sandbox?** → Codex.
- **Same-*family* judgement but isolated from this thread, with explicit Opus/Sonnet selection?** → Claude CLI launcher. If the host exposes the Claude Code `Agent` tool and model selection is not required, that is also fine.
- **Jury for a high-stakes call?** → fan the same prompt to Codex + omp-DeepSeek + omp-Kimi in parallel; divergence is the signal.
- **Bigger than ~a day or two of work?** → it's a *deliverable*, not a dispatch: run a `megaplan` (itself launched as a subagent) and size it with the **`megaplan-decision`** skill. Past ~2 weeks → an epic.
- **Already have the answer?** → don't dispatch. Subagents aren't free.

## Use the cheapest subagent that can do the job

Independence is the *why*; cost is the *which*. Default to the cheapest model that can plausibly succeed; escalate only on evidence.

1. **DeepSeek V4 Flash** (`omp:deepseek/deepseek-v4-flash`) — non-reasoning, fast, cheap. High-volume work that needs coding-tuned behavior.
2. **DeepSeek V4 Pro** (`omp:deepseek/deepseek-v4-pro`, the default) — reasoning model. When the task needs judgement: root-cause analysis, "is this sound", "should this merge".
3. **GPT-5.x (Codex) or Claude** — only for *real* complexity: subtle multi-step reasoning, write-heavy implementation, the strongest adversarial review.

Two rules: **start low, escalate on evidence** (don't reach for the frontier model "to be safe"); and **prepare the context so a cheap model can win** — most "cheap model failed" cases are under-specified prompts. A moment spent scoping the task is cheaper than burning a Claude subagent on something Flash could do.

Beware the asymmetry: reasoning models handed mechanical briefs refactor (because that's what reasoning does); non-reasoning models handed architectural briefs literally execute fragments without understanding the intent. Match brief shape to model mode, not just model to task.

---

## 1. Codex (GPT-5.x)

`codex exec` from Bash (the `/codex:*` plugin wraps the same call).

```bash
codex exec --sandbox read-only "$(cat /tmp/prompt.md)" </dev/null > /tmp/out.txt 2>&1
```

- `--sandbox read-only | workspace-write | danger-full-access` — analysis / let it edit files / full shell.
- `-c model_reasoning_effort=low|medium|high` — `medium` default.
- `codex exec review [--pr <n>]` for PR review; `codex apply` to apply its last diff.
- **Always seal stdin with `</dev/null`.** Otherwise `codex exec` blocks forever at `Reading additional input from stdin...` (0% CPU, no error) even when the prompt is in argv. That banner prints on healthy runs too — the wedge signal is the output file *not growing*. Wrap long runs in `timeout 1800` (30 min — review and write-heavy briefs routinely run 15+ min; 600s is too tight).

## 2. Claude (Opus/Sonnet/Haiku)

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

Prefer Claude over Codex when you want the *same family* of judgement isolated from this thread (keeping the main context clean), or specifically want Opus judgement. For genuinely different model-family judgement, prefer Codex or an omp-routed DeepSeek/Kimi spec.

---

## Multi-phase delegation (when a single-turn agent isn't enough)

When a full plan-execute-review cycle across many files is needed, route through megaplan:

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

Send the same unbiased prompt to several models in parallel (Codex + omp-DeepSeek + omp-Kimi, optionally a Claude `Agent`) and compare — convergence on a subtle call is far stronger than one model's confidence; divergence is signal. Reserve it for risky pre-merge reviews, hard-to-reverse architecture calls, security-sensitive paths. Don't fan out routine work. For a multi-lens sense-check of one proposal (human-user / agent-user / abstraction lenses), give each agent only its own lens and never show one's output to another.

## Detecting hangs

Check liveness **30–60 s after launch**, not 10 minutes in.

- **Codex** — see the `</dev/null` wedge above; the tell is an output file stuck at the banner size while wall-clock climbs.
- **Claude Agent / launcher** — synchronous, rarely wedges; the common failure is a terse prompt → shallow hedged answer in < 30 s. Cap length and demand a position.
- **megaplan / omp phase** — an "stuck" run is usually a gated step awaiting approval; `megaplan status --plan <name>`.

**Liveness ≠ correctness.** A subagent can stream for 10 minutes and still answer uselessly — read the response; there's no shortcut.

## Quick reference

```bash
# 1. Codex — always seal stdin with </dev/null, allow 30 min
timeout 1800 codex exec --sandbox read-only "<prompt>" </dev/null              # analysis
timeout 1800 codex exec --sandbox workspace-write "<prompt>" </dev/null        # implementer
codex exec review --pr 123

# 2. Claude — explicit Opus selector via Claude CLI
python ~/.claude/skills/subagent-launcher/launch_claude_agent.py \
  --model=opus --query-file=/tmp/prompt.md --project-dir="$PWD"

# 3. Multi-phase / omp-routed DeepSeek-Kimi-GLM work:
#    megaplan init --profile all-deepseek-pro-direct --robustness light "<task>"
```
