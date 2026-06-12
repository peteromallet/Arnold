---
name: babysit
description: >
  Keep a long-running autonomous process moving to completion by setting up a
  RECURRING REMINDER that, on every fire, checks status, unblocks whatever is
  stuck, pushes the work forward, and re-arms itself — until the whole thing is
  done. The canonical target is a `megaplan chain`/epic, but it works for any
  unattended run (a build, a deploy, a batch job). Use when the user says
  "babysit", "keep it moving", "push it forward", "unblock the run", "don't stop
  until it's done", "check on it every hour", or "set up a babysit loop".
---

# Babysit

**The job is not to watch — it is to UNBLOCK and PUSH FORWARD on a timer.** A
passive "I'll check in and report" loop is the failure mode. Each fire must end
with the run measurably closer to done, or with a concrete blocker fixed.

Set up a reminder that re-fires on an interval. On every fire you:

1. **Assess** — is the run progressing, stopped, or stalled?
2. **Unblock** — if stopped/failed/stalled, diagnose the ROOT cause and fix it.
3. **Push** — re-drive the next unit of work.
4. **Re-arm** — schedule the next fire (this is what makes it a loop).
5. **Stop only when the whole thing is genuinely done** (every milestone
   complete / the job exited success), then tear the reminder down.

## Arguments

`/babysit [interval] [direction…]`

- **interval** (optional) — how often to fire. A leading `\d+[smhd]` token
  (`30m`, `1h`, `2h`) or a trailing `every <N><unit>` sets the cadence. If
  omitted, self-pace: arm a `Monitor` (Claude) / `--poll` follow (Codex) on the
  run's state and use a ~20–30 min fallback heartbeat. The interval becomes the
  `/loop` cadence (Claude) or `--sleep <seconds>` (Codex).
- **direction** (optional) — the rest of the input is free-text steering folded
  into EVERY fire's instruction. Use it for: which run/spec/dir to babysit;
  what to prioritize (e.g. "unblock aggressively, skip deliverable
  spot-checks"); guardrails ("don't touch the reigh run", "pin the engine
  before m3"); or a stop condition ("stop when m7 lands"). If no run is named,
  infer the active one (most recent in-progress chain/plan/job).

Parse like `/loop`: peel the interval token first, the remainder is direction.
Both flow into the reminder — interval sets cadence, direction is embedded in
the re-fired message so every tick carries the same focus and guardrails.

Examples:
- `/babysit 1h drive the arnold chain to all 14 milestones; pin engine before m3`
- `/babysit 30m keep the deploy green, only ping me on failure`
- `/babysit` — self-paced, infer the active run, default focus.

## Setting up the reminder (harness-specific)

This is the load-bearing step. Pick by which harness you are:

- **Claude Code** → use the **`/loop`** skill with an explicit interval and the
  full babysit prompt, e.g.
  `/loop 1h <the babysit instruction block below>`.
  `/loop` re-enters itself each interval. For event-driven waking between
  ticks, arm a `Monitor` on the run's state file (it fires the moment a phase
  transitions or the driver exits) and keep the `/loop` interval as the
  fallback heartbeat. Session-local; it stops when the session closes. For a
  durable cloud reminder use `/schedule` instead.
- **Codex** → use the **`wakeup-loop`** skill (`/wakeup-loop`) with
  `--repeat forever` and a `--message` that is the babysit instruction:
  ```bash
  ~/.codex/skills/wakeup-loop/scripts/wakeup_loop.sh \
    --sleep 3600 --poll 60 --repeat forever --label "babysit <run>" \
    --message "Babysit: check status, unblock any stall, re-drive the next step, stop the loop only when the whole run is done."
  ```
  This keeps the same thread alive and re-fires the message on each wake.

Write the babysit instruction once (status command, the milestone list, where
state lives, common fixes) and pass that same block as the loop/wake message so
every fire is self-contained.

## The babysit loop (what each fire does)

### 1. Assess
- Read the run's status. For megaplan:
  `cd <project> && megaplan chain status --spec <spec>` — note completed vs
  pending milestones and `Last state`.
- Check the current plan's `state.json`: `current_state`, `latest_failure`, and
  the worker channel in use. For Shannon stream-json runs, treat the stream
  artifacts as the primary evidence: captured stream-json stdout, the current
  `phase_result.json`, `events.ndjson`, and the transcript tail.
- Is a worker process actually alive? (`pgrep -f "chain start"`, a `shannon`/
  `megaplan <phase>` child, etc.)
- **Verify cumulative INTEGRATION, not just liveness — is HEAD advancing per
  milestone?** Check that milestone N's base actually contains N-1's *committed*
  work (`git log --oneline` on the worktree). A "0 commits" milestone or a clean
  worktree mid-epic is a RED FLAG that work is being stashed/lost (the classic
  `--no-push` + `require_clean_base` trap), not a benign `--no-push` artifact.

#### Stream-json ground truth

For the default Shannon stream-json worker, inspect the structured artifacts
first:

- **Stream-json stdout** shows the live event stream emitted by the native
  worker turn and is the first place to check for progress, refusal metadata,
  tool results, and terminal messages.
- **`phase_result.json`** is the normalized phase outcome: exit kind,
  retryability, worker metadata, landed-diff evidence, and completion status.
- **`events.ndjson`** is the durable driver timeline: sampling decisions,
  retries, errors, state transitions, and handoff points.
- **Transcript tail** is the human-readable recent conversation context; use it
  to understand what the worker was doing immediately before a stall or exit.

### 2. Distinguish a REAL stall from a false one
- **False stall (do nothing):** for stream-json runs, stream-json stdout or the
  transcript tail is still advancing, `phase_result.json` has not recorded a
  terminal failure, and `state.json` heartbeat/artifact counts are fresh even if
  `events.ndjson` is quiet. Long Opus/execute turns can log infrequently;
  structured stream artifacts plus fresh heartbeat are the truth.
- **Real stall (act):** no live worker, `latest_failure` set, `current_state`
  unchanged with a stale heartbeat, `phase_result.json` records a terminal
  failure, or the driver process exited non-success.

#### Tmux fallback ground truth

Tmux remains a maintained fallback when
`MEGAPLAN_SHANNON_STREAM_WORKER=0`/`false`/`off`/`no` selects the legacy Shannon
tmux worker. Only in that fallback mode, the tmux pane and its transcript tail
are operational ground truth for the live turn. Continue to cross-check
`state.json`, `events.ndjson`, and `phase_result.json` before acting, because
driver state still determines whether a phase completed, failed, or will retry.

### 3. Unblock — diagnose ROOT, then fix
Get to the actual root (read `latest_failure`, grep `events.ndjson` and the
stream-json stdout, `phase_result.json`, transcript tail, and drive log for
`429|auth|trust|worker_timeout|Traceback|Error|stall`). Don't patch a symptom.
Common blockers + fixes (megaplan + Shannon/DeepSeek):
- **No/wrong model keys** → the spawned subprocess does NOT inherit the parent
  harness's auth. Find the real key source (e.g. megaplan's
  `auto_improve/api_keys.json`); route Claude via **Shannon** (uses the local
  `claude` CLI subscription, no API key) and DeepSeek via its **direct API**
  (`hermes:deepseek:...`, not OpenRouter/Fireworks unless intended).
- **429 / "rate limited"** → check whether it's a real throttle or an
  **exhausted key/credits** (`curl -s -H "Authorization: Bearer $KEY"
  https://openrouter.ai/api/v1/auth/key` shows `limit_remaining`). Switch
  provider/model or top up; don't just retry.
- **Shannon hangs / `worker_timeout 120s` with empty output** → the `claude`
  CLI is stuck on its interactive **"trust this folder?"** dialog (not
  suppressed by `--dangerously-skip-permissions`). Pre-trust the workspace in
  `~/.claude.json` → `projects[<path>]` with `hasTrustDialogAccepted` +
  `hasCompletedProjectOnboarding` = true. **Trust the resolved realpath** — on
  macOS `/tmp/x` resolves to `/private/tmp/x`. Validate with the REAL
  `shannon ...` command, not `claude -p` (which handles trust differently and
  gives a false pass). Better: fix it in the worker so it auto-trusts the cwd
  (see "Fix the engine, not just the run" below).
- **Engine pin** → if the run modifies the very engine that drives it
  (dogfooding a self-refactor), drive from a frozen clone/venv (non-editable
  install) made from a branch that carries your fixes, BEFORE the
  engine-mutating milestone.
- **Completion-contract / shadow verdicts** → a `blocked-would-be` shadow
  verdict claiming "files not in git status" is often a FALSE POSITIVE when the
  chain already committed them (the check compares working-tree status, not the
  committed diff). Verify the files exist/are committed before trusting it.
- Then **reset the terminal state** so the milestone re-attempts: clear the
  chain-state json + remove the failed plan dir, and re-drive.

### 3a. Fix the engine, not just the run

**When the blocker is a megaplan bug, the real fix is in the megaplan source —
not a per-tick band-aid in the run's worktree.** A stall you re-patch every fire
(re-trusting a folder, hand-editing state, nudging a wedged worker) is a defect
in the harness that will recur on the next run and the run after that. The
durable fix is to go ACTUALLY fix it in the code:

- The engine source lives at **`~/Documents/megaplan`** (the repo housing the
  megaplan package — adjust if it's checked out elsewhere; `pip show -f
  megaplan` or `python -c "import megaplan, os; print(os.path.dirname(megaplan.__file__))"`
  tells you the installed path). Edit the worker / state / CLI code there,
  add or extend a test that reproduces the stall, and let the editable install
  (`pip install -e .`) make the fix live for the next tick. Then re-drive.
- **Mind the engine-pin caveat:** if the *current* run is itself dogfooding a
  megaplan self-refactor, don't hot-edit the engine underneath it — land the fix
  on a branch and drive the live run from the frozen clone/venv (see "Engine
  pin" above), then merge.
- Prefer the root fix over the symptom: "Shannon hangs on the trust dialog" →
  make the worker pre-trust its cwd in code, not just patch `~/.claude.json`
  this once. "Idle watchdog false-kills long Opus turns" → raise/condition the
  backstop in the engine, not skip the milestone. Leave a megaplan ticket
  (`/megaplan-tickets`) for anything you can't fix on the spot so it gets folded
  into a future epic.

> **This skill ships with megaplan.** Its canonical source is
> `megaplan/data/babysit_skill.md` in that same repo; `megaplan setup --global`
> *symlinks* it into `~/.claude/skills/babysit/SKILL.md` and
> `~/.codex/skills/babysit` (the same symlink-not-copy pattern poms_skills'
> `sync.sh` uses). So improving babysit itself is the same move as fixing the
> engine: edit the in-repo source and the change is live for every harness — no
> copy step.

### 4. Push forward
Re-drive the next unit. For megaplan, single-step so each is a clean checkpoint:
`megaplan chain start --spec <spec> --no-git-refresh --no-push --one` (in the
background). Confirm a fresh plan dir appears with the expected profile/config.

### 5. Verify deliverables at each completion
When a unit reports `done`, spot-check the work actually landed (files exist /
committed; tests present) — don't trust the status word alone.

### 6. Re-arm or stop
If work remains, schedule the next fire (step "Setting up the reminder"). If
everything is complete, report the final state and **tear down the
loop/monitor** (don't leave a zombie reminder running).

## Discipline
- One concrete forward step (or one fixed blocker) per fire — never just a
  status echo.
- Stale instructions in the loop prompt happen (e.g. a model/profile that was
  later changed). Re-read current reality each fire; trust the live state over
  the prompt's assumptions.
- Don't intervene in a healthy-but-slow run — slow premium/Opus execution is
  not a stall.
- Prefer fixing the megaplan source over re-patching the run every tick — a
  recurring blocker is an engine defect (see "Fix the engine, not just the run").

Related: `megaplan-epic` (driving the chain), `megaplan-observe` (live
introspection), `megaplan-tickets` (file what you can't fix on the spot),
`loop` (Claude reminder), `wakeup-loop` (Codex reminder).
