# Testing the Shannon stream-json channel end-to-end

A simple, escalating way to verify the headless `claude --print` stream-json channel
(`megaplan/workers/shannon_stream.py`) — from "the code is sound" up to "it really drives a
real megaplan phase against real Claude instead of tmux."

Run everything from the repo root: `~/Documents/.megaplan-worktrees/shannon-stream` (or wherever
this branch is checked out). `PYENV_VERSION=3.11.11` if you use pyenv.

---

## The 30-second version

```bash
# 1. Code is correct (offline, no Claude, no network):
python -m pytest tests/test_workers_shannon_stream.py tests/test_workers_shannon_session.py \
                 tests/test_worker_dispatch.py \
                 tests/test_channel_parity.py tests/bakeoff/test_channel_shadow.py -q

# 2. The channel really works against real Claude (needs a logged-in `claude` CLI):
MEGAPLAN_SHANNON_STREAM_CONFORMANCE=1 python -m pytest tests/test_shannon_stream_conformance.py -v
```

If both pass, the channel is good. Everything below is for proving the *integration* (a real
python -m arnold.pipelines.megaplan phase flowing through the new worker) and exercising the shadow / cutover knobs.

---

## Level 1 — Offline unit verification (no Claude, no network)

Proves the worker, parser, session handling, and shadow/parity logic are correct.

```bash
python -m pytest \
  tests/test_workers_shannon_stream.py \
  tests/test_workers_shannon_session.py \
  tests/test_worker_dispatch.py \
  tests/test_shannon_stream_idle_timeout.py \
  tests/test_channel_parity.py \
  tests/bakeoff/test_channel_shadow.py \
  tests/test_shannon_stream_conformance.py \
  -q
```

Expected: all pass. `test_shannon_stream_conformance.py` **skips** here by design (it only runs when
you opt in — see Level 2).

> Note: a *full* `pytest` run in a bare checkout shows ~27 unrelated failures — tests that spawn
> `python -m arnold ...` as a subprocess fail with `ModuleNotFoundError` because the checkout
> isn't pip-installed. Those are environmental, not this change. Either run the scoped list above,
> or `pip install -e .` first to make the subprocess tests pass.

---

## Level 2 — Live conformance (the real headless channel) — **the simple end-to-end**

This is the cleanest "does headless stream-json actually work against real Claude" test. It launches
`claude --print --input-format=stream-json --output-format=stream-json --verbose` with the host's
normal Claude config and asserts Claude emits real `init` / `assistant` / `result` events.

**Requires:** a **logged-in** Claude Code CLI on PATH (subscription OAuth — `claude` works
interactively for you). It is gated off unless you opt in:

```bash
MEGAPLAN_SHANNON_STREAM_CONFORMANCE=1 python -m pytest tests/test_shannon_stream_conformance.py -v
```

- Pass → the headless channel bills your subscription and emits a valid structured turn.
- Skipped → you didn't set the env var.
- Fails with `Not logged in · Please run /login` → the CLI isn't authenticated in this shell or
  `CLAUDE_CONFIG_DIR` is pointed at a fresh config. Run `claude` once interactively to log in, make
  sure the conformance run is using the normal Claude config, then retry.

This is also wired as a CI smoke test in `.github/workflows/shannon-stream-conformance.yml` — it's
the drift tripwire that catches a future `claude` version breaking the `--print` schema or permission
behavior.

---

## Level 3 — True end-to-end: drive a real megaplan phase through the stream worker

Prove the dispatcher actually routes a Shannon (`vendor: claude`) phase to the **new** headless
worker instead of tmux, and that **no tmux session is spawned**.

The new worker is **additive and OFF by default**. Turn it on with one env var:

```bash
export MEGAPLAN_SHANNON_STREAM_WORKER=1     # 1/true/yes/on enables the headless stream worker
```

Then run a tiny plan on the Claude vendor and watch how it executes:

```bash
# a trivial single-file task is enough to exercise the channel
PYENV_VERSION=3.11.11 MEGAPLAN_SHANNON_STREAM_WORKER=1 \
  python -m arnold.pipelines.megaplan init "Add a one-line docstring to <some small file>" \
  --profile solo --robustness bare --vendor claude --in-worktree sstest

PYENV_VERSION=3.11.11 MEGAPLAN_SHANNON_STREAM_WORKER=1 \
  python -m arnold.pipelines.megaplan auto --project-dir ~/Documents/.megaplan-worktrees/sstest
```

**While it runs, confirm the channel — two checks:**

```bash
# (a) the new worker is driving: a `claude --print ... --output-format=stream-json` process appears
ps aux | grep -v grep | grep -E "claude --print|claude .*--output-format=stream-json"

# (b) the OLD path is NOT used: NO bun/index.ts driver, NO private tmux server
ps aux | grep -v grep | grep -E "vendor/shannon/index.ts|tmux -L mp-"   # expect: nothing
```

If you see (a) and not (b), a real megaplan phase just ran through the headless stream-json channel.
With `MEGAPLAN_SHANNON_STREAM_WORKER` unset, the same run uses the tmux path — that's the toggle, and
**tmux is still fully present** (nothing was retired), so falling back is a one-flag change.

### One-shot, no full plan

If you just want to see the worker handle a single turn without spinning a whole plan, drive it
directly from a Python shell:

```python
from arnold.pipelines.megaplan.workers.shannon_stream import run_shannon_stream_step   # see its signature
# build a minimal step/state per the existing call site in megaplan/workers/_impl.py (~line 3076)
```

(The dispatcher call site in `_impl.py` shows exactly what `run_shannon_stream_step` expects.)

---

## Optional — exercise the rollout knobs (M3)

| Feature | Env knob | Quick check |
|---|---|---|
| **Auth channel** | `MEGAPLAN_SHANNON_STREAM_AUTH_CHANNEL=subscription` (default) or `api_key` | with `api_key`, set `ANTHROPIC_API_KEY`/`MEGAPLAN_SHANNON_STREAM_API_KEY` to bill the API instead of the subscription (the "validated flip"). |
| **Sampled shadow** | `MEGAPLAN_CHANNEL_SHADOW_SAMPLE_RATE=0.1` | runs the tmux + stream channels on a ≤10% sample and records deterministic-artifact parity (reuses the bakeoff harness; see `arnold/pipelines/megaplan/bakeoff/channel_shadow.py`). |
| **Idle / execute timeouts** | `MEGAPLAN_SHANNON_STREAM_IDLE_TIMEOUT_SECONDS`, `..._EXECUTE_TIMEOUT_SECONDS` | tune liveness bounds. |

The API-adapter proof is recorded at `docs/shannon-stream-api-proof-record.json` (a dry-run in the
build env — no live API key was present; run Level 3 with `MEGAPLAN_SHANNON_STREAM_AUTH_CHANNEL=api_key`
+ a real key to produce a live proof).

---

## Level 4 — real-life / soak (the part that actually matters)

**Levels 1–3 prove the channel *functions*. They do NOT prove it *survives real life*.** This whole
channel exists because the tmux path broke under messy, concurrent, hours-long, failure-prone load —
and none of that shows up in a single happy-path turn. If you only care that "it works once," stop at
Level 2. If you care whether it's safe to *rely on*, do these. Each item names the real-world failure
it's actually testing for.

### 4a. Shadow mode on a real, ongoing workload — **highest signal, do this first**

The honest end-to-end test isn't a docstring — it's "does the new channel produce equivalent results
to tmux on *real* phases?" That's what shadow mode is for. Turn it on against an actual running
python -m arnold.pipelines.megaplan chain (not a toy):

```bash
export MEGAPLAN_SHANNON_STREAM_WORKER=1
export MEGAPLAN_CHANNEL_SHADOW_SAMPLE_RATE=0.1   # run BOTH channels on ~10% of real phases, compare
# ...then run a normal, real chain/plan on --vendor claude as you usually would...
```

It runs the stream channel alongside tmux on a sampled fraction of real phases and records
**deterministic-artifact parity** (exit-kind class, payload schema validity, landed-diff status,
worker-did-work) via the bakeoff harness (`arnold/pipelines/megaplan/bakeoff/channel_shadow.py`). After a handful of
real phases, inspect the recorded parity:

```bash
find . -path "*channel_shadow*" \( -name "*.json" -o -name "*.ndjson" \) | xargs ls -lt | head
# look for: same exit-kind class on both channels, no stream-only error/timeout, schema-valid on both
```

**Passes when** N≥5 real phases show parity and the stream arm never produces an error/timeout the
tmux arm didn't. **Tests for:** behavioral fidelity on real work (not a one-liner) — the thing a
happy-path turn can't tell you.

### 4b. Unattended auth — **the single biggest unknown**

Level 2 assumes *your* logged-in interactive shell. The real question is whether headless `claude`
is authenticated **when megaplan drives it unattended** (cron/CI/sandboxed executor). We have direct
evidence it sometimes isn't — the build itself hit `auth_error: Not logged in · Please run /login`
when an executor tried a live stream-json turn in a sandbox.

```bash
# Simulate the unattended context: a clean shell with no interactive login state inherited.
env -i PATH="$PATH" HOME="$HOME" \
  claude --print --output-format=stream-json --verbose "say READY" </dev/null
# A `result` event with no auth_error => unattended auth works.
# `Not logged in` => the headless channel is NOT safe to rely on in automation until auth is solved
#   (persisted OAuth creds / a correct CLAUDE_CONFIG_DIR / a key via MEGAPLAN_SHANNON_STREAM_AUTH_CHANNEL=api_key).
```

**Tests for:** whether "it works" generalizes from your terminal to how megaplan actually runs it.
**Until this passes in your real run context, treat the channel as proven only for interactive use.**

### 4c. Concurrency under contention

```bash
export MEGAPLAN_SHANNON_STREAM_WORKER=1
# launch 3–4 real chains at once (the original pain was "many concurrent on one box")
```
Watch: provider `rate_limit` / capacity failures surface as normal external errors and the chain remains
recoverable without any host-wide admission throttle. **Tests for:** failure #6 (subscription
starvation) without reintroducing a local cap that can block unrelated agents.

### 4d. Failure injection — does it fail *fast*, not hang?

The headline failure the old path had was a **2-hour silent hang** on a dead turn. Prove the new one
fails fast and attributed:

```bash
# during a live stream-worker phase, kill the turn out from under it:
pkill -f "claude --print"        # or revoke auth / SIGKILL the worker mid-turn
```
Watch the driver surface a clear, *retryable* error within seconds (not minutes), and recover or
re-dispatch. Also force a permission denial on a tool-using turn and confirm the **permission
fail-fast watchdog** converts it to an immediate retryable fail rather than a headless hang.
**Tests for:** failures #4 and #8 (dead-turn hang; fail-slow → fail-fast).

### 4e. Real tool-using work under `bypassPermissions`

Level 3's docstring may use no tools. Run a task that genuinely needs **Bash + Edit + Write** so the
worker actually executes tools headlessly:

```bash
MEGAPLAN_SHANNON_STREAM_WORKER=1 python -m arnold.pipelines.megaplan init \
  "Create scripts/hello.sh that echoes hi, chmod +x it, run it, and capture output to out.txt" \
  --profile solo --robustness bare --vendor claude --in-worktree sstools
# then drive it and confirm the files were actually created + the commands ran
```
**Tests for:** that `bypassPermissions` really executes tools in an automated context (not just a
no-tool turn), and that the OS-user safety boundary behaves as documented.

### 4f. Long-session / multi-hour soak

Run a multi-hour, multi-turn chain on the stream worker and watch for: OAuth surviving (no
mid-session expiry), context recycling (`/clear`/`/compact`) firing cleanly across many turns, and no
slow degradation. **Tests for:** the long-lived-session decay risk a 4-second conformance turn can't
surface.

### 4g. Version drift (across an actual upgrade)

The CI conformance smoke test (`.github/workflows/shannon-stream-conformance.yml`) is the tripwire,
but the *real* drift test is to let `claude` auto-update to a new version and re-run Level 2 — a
parse/schema mismatch should fail **loudly** (not silently produce a garbage WorkerResult). **Tests
for:** that the structured channel degrades gracefully when the vendor changes `--print` behavior
(it has, twice).

---

## What "passing" means

- **Level 1** green → the implementation is correct.
- **Level 2** green → the headless stream-json channel works against real Claude on the subscription
  **(in your interactive shell)**.
- **Level 3** showing a `claude --print` process and **no** tmux/bun → a real megaplan phase ran on
  the new channel, with tmux retained as the fallback.
- **Level 4** is the only level that tells you it's safe to *rely on* in production: parity on real
  work (4a), unattended auth (4b), the cap under load (4c), fail-fast on death (4d), real tool
  execution (4e), long-session survival (4f), graceful drift (4g). **4a + 4b are the two to do before
  trusting it for anything automated.**

Design reference: `docs/shannon-stream-channel-plan.md`. Originating ticket: `01KTVV4ANX9MVKBFPRZX6F1AEH`.
