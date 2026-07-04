---
name: superfixer-debug
description: Diagnose a broken Hetzner superfixer (watchdog → repair-loop/Kimi goal operator → meta-repair → 6h progress-auditor) when a cloud epic chain won't self-heal. Walk each fixer asking four questions — did it track the real data, actually fix the thing, understand the intent, have the context it needed? Find the first layer that broke the chain of custody and the layer above that failed to catch it; fix the fixer, re-trigger it, verify the real chain recovers. Use when "the error checker / the fixer / the 6h audit" isn't converging on a stuck chain.
---

# superfixer-debug

A playbook for debugging the machine that fixes the machines that fix the machines.

## The philosophy

The superfixer is a **stack of backstops**: each layer fixes the layer below, and the top audits them all. When an epic chain is stuck and won't self-heal, the bug is almost never in the epic — it is in whichever layer of the superfixer *went blind, lied, or gave up*, **and** the layer above it that *failed to notice*. A stuck chain is therefore always two failures: a fixer that didn't fix, and a backstop that didn't catch that.

So the reframe is total:

> Never ask *"why is the chain stuck?"* — always ask *"which fixer failed, and why didn't the one above it catch it?"*
>
> "We should fix the machine that should fix the machine, rather than just fix the machine."

Your job is not to unblock the epic. It is to find the first layer that broke the chain of custody, repair that layer, re-trigger it so the real chain recovers, and then close the backstop above it so the failure class can't hide again. Fixing the fixer and walking away leaves the chain dead; that is not done.

## The cast (short)

On the box (`ssh root@159.69.51.216`, `docker exec megaplan-cloud-agent`):

| Layer | Who | Fixes |
| --- | --- | --- |
| — | **epic chain** | the actual work |
| detect | **watchdog** (`arnold-watchdog`, 1h) | notices stop/stall, dispatches repair |
| **L1** | **repair-loop** / Kimi goal operator | the **stuck chain** |
| **L2** | **meta-repair-loop** ("fixer of the fixer") | **L1**, when L1 failed |
| **L3** | **progress-auditor** (6h) | audits **L1+L2** ("superfixer health / repair-the-repairer") |

Each layer is the backstop for the one below. Evidence flows upward through a fixed chain of artifacts — knowing that chain is most of the skill.

## The chain of custody (ground truth)

State is recorded in **six places** that can disagree. Trust them in this order — **never answer from fewer than all of them**, and treat disagreement as the signal, not noise:

> live process (`ps`/`tmux ls`) → marker JSON (`.megaplan/cloud-sessions/<s>.json`) → chain JSON (`<ws>/.megaplan/plans/.chains/*.json`) → plan `state.json` → log tail → external state (PR/CI/build).

**The core discipline: ground truth beats derived labels.** The watchdog's words — `complete`, `active`, `chain_stuck`, `needs_human` — are a *derived view*. The files and the process table are the truth. `last_state: done` while a milestone is missing from `completed[]`, or while `dirty_flag`/`sync_state` say otherwise, is a lie you catch only by reading the files. "The chain status is internally inconsistent in a useful way" — that inconsistency *is* the diagnosis.

Before you touch any fixer, ask one question first: **can I even see?** Diagnose the observation path before the system. Confirm `PATH`/`PYTHONPATH`, that the status command imports, that the container is reachable. A silent import failure looks exactly like "no sessions."

## The interrogation — walk each fixer, ask four questions

Start at L1. For each layer, in order, ask:

1. **TRACKED?** — Did it actually see the real data, or a derived label / stale snapshot? Was the *real error* (stderr, exit code, exception) inlined into its context, or did it spin on a status word (`chain_stuck`, `blocked`, generic `needs_human`) that hid the mechanism?
2. **FIXED?** — Did its fix *take*? Verify against ground truth (re-read `state.json`, re-check the process), **never against the fixer's own SUCCESS log.** A repair loop can log `outcome=running` from an exit code while the chain is still blocked.
3. **INTENT?** — Was it fixing the *real goal* or a proxy? The signature of failure here is **guard-weakening**: a fixer patches the system to accept a degenerate state so it can declare success (e.g. relaxing a completion guard to treat a metadata-only merge as "done"). Catch it by `git diff`-ing the repair checkout's *uncommitted* tree before it commits — see what it is *about to* do, not just what it reports.
4. **CONTEXT?** — Did it have what it needed? Was the evidence it passes downstream actually written (cloud `complete` ≠ the manifest the dependent chain reads regenerated)? Did its state token match the dispatcher's vocabulary? Did it lack the recovery metadata to pick a valid next step?

The chain recovers only when **L1 passes all four.** The first layer to fail one is your **root-cause layer**; the layer above failing to catch it is the **recurrence to close.**

## The recurring failure shapes (what the four questions usually uncover)

Name which one before fixing — it tells you the axis and the sibling-hunt:

- **Blind fixer (TRACKED fail).** The error never reached the agent. *Move:* read `repair-data.json` and the repair log; if the real error isn't inlined, fix the evidence/transport (huge evidence crashing argv → pass via temp file; truncated prompt → widen it).
- **False success (FIXED fail).** Logs say terminal/done, the state file says `initialized`. *Move:* cross-reference the execution log against the committed state file. Never trust a return code; re-verify `alive && progressing && blocker_cleared`.
- **Token drift / unreachable repair (CONTEXT fail).** The stuck chain's actual state isn't in the dispatcher's switch, or the writer emits `awaiting_human_verify` while the reader branches on `awaiting_human`. *Move:* grep every concrete state token the writer emits; verify each appears in the repair-dispatch decision. Missing = silent no-op.
- **Evidence-contract gap (CONTEXT fail).** Upstream `complete` didn't write the artifact the dependent chain consumes; or a stale blocker conclusion is baked into a downstream doc. *Move:* ask "did completion *write the evidence* the next reader needs?"; then grep dependents for stale embedded conclusions.
- **Guard-weakening (INTENT fail).** The fixer "succeeds" by lowering the bar. *Move:* refuse to let any layer count "I fixed the epic directly" or "I relaxed the guard" as success. Force it to retrigger ordinary repair and verify the genuine condition.
- **Spinning fixer (budget fail).** Same error + state + command repeating. *Move:* split the **deterministic-failure budget** (cap at 2–3) from the productive-iteration budget. "Should have tripped a circuit breaker at iteration 2, not 80." Verify the repair command is even *valid* for the current state before spending budget on it.

When you find one of these, **hunt its siblings**: one transport or token bug is almost always a family across repair-loop / meta-repair / auditor. Patch all of them.

## Run it as a swarm — investigate wide with DeepSeek, fix deep with Codex

The diagnostic is fan-out-shaped: each layer, each evidence source, each failure shape is an independent question. Don't work it serially in your own context — **dispatch DeepSeek subagents to investigate in parallel, keep your context for synthesis, then dispatch Codex to do the fix.** (Tooling: `~/.claude/skills/subagent-launcher` — `fan.py` for the DeepSeek fan, `codex exec` for the fix.)

**Investigate — DeepSeek V4 Pro (`fan.py`, `--model="deepseek:deepseek-v4-pro"`).** One self-contained brief per direction; each agent reads the box artifacts and returns a tight verdict only. **Point every investigation brief at `/megaplan-cloud`** — that skill owns the canonical way to work the box: lead with `megaplan cloud status --all` (not raw `ssh`/`tmux`/`ps`), then the session markers, chain state, logs, and repair artifacts. Fan these directions out:

- **one per layer** — "for session `<s>`, did L1 / L2 / L3 each ACT, SEE real data, FIX, understand INTENT, and have CONTEXT?" (its `repair-data.json`, its logs, `pgrep`).
- **one per evidence source** in the chain of custody — triangulate, report contradictions and stale mtimes.
- **one per failure shape** — does this session show blind-fixer / false-success / token-drift / evidence-gap / guard-weakening / spinning?
- **one "can I even see?" probe** — is the observation path itself healthy (PATH/PYTHONPATH/import/container)?

You read the verdicts and decide the single **root-cause layer + axis** — that judgement stays in your context.

**Fix — Codex GPT-5.5 (`codex exec --sandbox danger-full-access`, `</dev/null`, `timeout 1800`).** Hand the source fix to a Codex subagent: narrow brief, edit in `/workspace/arnold` on `editible-install`, `bash -n` + `tests/cloud/test_watchdog_wrappers.py`, scan-complete proof before commit. Point it at `/megaplan-cloud` for the on-box deploy (sync editable install, copy wrapper to `/usr/local/bin`, restart supervisor) — same skill, so investigate and fix speak the same cloud vocabulary. Keep DeepSeek on investigation; Codex on the write.

Two rules:

- **Don't nest them.** Launch DeepSeek and Codex separately from your own shell. A `codex exec` subagent can't reach the DeepSeek API (its network is sandboxed) unless the outer Codex ran `danger-full-access` — and even then, keep the investigate/fix split clean and parallel.
- **Verdicts are disposable; the fix is the deliverable.** DeepSeek returns *conclusions* (root-cause layer + axis + evidence). Only the Codex fix and the close-the-loop redeploy persist.

## Two moves people forget

- **Don't restart a live, slow chain.** Quantify the grind first (count error signatures: "173 failures, 48 the same config bug" is a different diagnosis from "173 random errors"). A chain that is heartbeating and dirty-tree-progressing is *not stuck* — restarting destroys real work and re-triggers the same grind. Batch-diagnose *all* blockers before any restart.
- **Plan-to-reality scan.** When a doc or prompt names an artifact (`meta_repair.py`, a milestone, a stage), `find`/`rg` for the literal filename and `git blame` promising lines. Zero hits, or hits only in uncommitted working-tree edits, means the feature is vaporware regardless of what the docs claim. Diff planning-doc names against executor names before concluding "X was skipped" — it may have been renamed.

## Close the loop (or it isn't done)

After fixing layer *N*'s code, do **all** of:

1. **Validate** — `bash -n` and `tests/cloud/test_watchdog_wrappers.py` (focused).
2. **Redeploy the chain of custody** — copy the changed wrapper to `/usr/local/bin/<wrapper>` + `chmod +x` (the editable-install sync does **not** refresh `/usr/local/bin`) → `git commit` + `git push origin editible-install`.
3. **Restart the supervisor** — `pkill -f "bash /usr/local/bin/arnold-watchdog"; setsid bash -lc /usr/local/bin/arnold-watchdog >> /workspace/watchdog-supervisor.log 2>&1 &`.
4. **Re-trigger the fix on the still-stuck session** — force L1 repair / redispatch the Kimi operator so the *now-fixed* fixer actually fixes the **real chain**. Verify *that* session advances — not merely that the supervisor restarted.
5. **Retroactive auditor test** — "if I had waited 6h, would L3 have caught this *and* had the root-cause insight to fix it?" If no, L3 is also blind: fix its detection/prompt so this class can't hide from it again. **This is what stops recurrence.**

Not done until: the fixed layer is redeployed, the chain is re-triggered, the **original** session has recovered, and L3 would catch the next one.

## Anti-patterns (known time-wasters)

- **Shell quoting on remote boxes** eats patterns repeatedly — use heredocs or `python3 -c`/`open()` to read ndjson/state directly.
- **Trusting one snapshot** (`watchdog-report.json`) without checking its mtime against the thing it describes.
- **Broad `search_files`/`find /`** before narrowing to the implementation paths.
- **`git merge-tree` "no conflicts"** as a green light — it catches textual collisions, never semantic staleness; diff against the recorded base SHA, not `HEAD`.
- **Restarting before diagnosing**, or hand-merging a PR the superfixer is correctly waiting on.

## Don't

- **Fix the symptom when the fixer is blind** — fix the broken layer first.
- **Hand-advance a chain** the superfixer is correctly handling — that's its job.
- **Stop at L1.** If L1 failed, the mandatory next question is why L2/L3 didn't catch it.
