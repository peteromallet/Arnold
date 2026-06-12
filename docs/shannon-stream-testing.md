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
                 tests/test_worker_dispatch.py tests/test_workers_turn_cap.py \
                 tests/test_channel_parity.py tests/bakeoff/test_channel_shadow.py -q

# 2. The channel really works against real Claude (needs a logged-in `claude` CLI):
MEGAPLAN_SHANNON_STREAM_CONFORMANCE=1 python -m pytest tests/test_shannon_stream_conformance.py -v
```

If both pass, the channel is good. Everything below is for proving the *integration* (a real
megaplan phase flowing through the new worker) and exercising the cap / shadow / cutover knobs.

---

## Level 1 — Offline unit verification (no Claude, no network)

Proves the worker, parser, session handling, cap, and shadow/parity logic are correct.

```bash
python -m pytest \
  tests/test_workers_shannon_stream.py \
  tests/test_workers_shannon_session.py \
  tests/test_worker_dispatch.py \
  tests/test_shannon_stream_idle_timeout.py \
  tests/test_workers_turn_cap.py \
  tests/test_channel_parity.py \
  tests/bakeoff/test_channel_shadow.py \
  tests/test_shannon_stream_conformance.py \
  -q
```

Expected: all pass. `test_shannon_stream_conformance.py` **skips** here by design (it only runs when
you opt in — see Level 2).

> Note: a *full* `pytest` run in a bare checkout shows ~27 unrelated failures — tests that spawn
> `python -m megaplan ...` as a subprocess fail with `ModuleNotFoundError` because the checkout
> isn't pip-installed. Those are environmental, not this change. Either run the scoped list above,
> or `pip install -e .` first to make the subprocess tests pass.

---

## Level 2 — Live conformance (the real headless channel) — **the simple end-to-end**

This is the cleanest "does headless stream-json actually work against real Claude" test. It launches
`claude --print --input-format=stream-json --output-format=stream-json --verbose` in an isolated
config dir and asserts Claude emits real `init` / `assistant` / `result` events.

**Requires:** a **logged-in** Claude Code CLI on PATH (subscription OAuth — `claude` works
interactively for you). It is gated off unless you opt in:

```bash
MEGAPLAN_SHANNON_STREAM_CONFORMANCE=1 python -m pytest tests/test_shannon_stream_conformance.py -v
```

- Pass → the headless channel bills your subscription and emits a valid structured turn.
- Skipped → you didn't set the env var.
- Fails with `Not logged in · Please run /login` → the CLI isn't authenticated in this shell. Run
  `claude` once interactively to log in, then retry. (This is exactly the auth condition that blocks
  the same proof inside a sandboxed executor.)

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
  megaplan init "Add a one-line docstring to <some small file>" \
  --profile solo --robustness bare --vendor claude --in-worktree sstest

PYENV_VERSION=3.11.11 MEGAPLAN_SHANNON_STREAM_WORKER=1 \
  megaplan auto --project-dir ~/Documents/.megaplan-worktrees/sstest
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
from megaplan.workers.shannon_stream import run_shannon_stream_step   # see its signature
# build a minimal step/state per the existing call site in megaplan/workers/_impl.py (~line 3076)
```

(The dispatcher call site in `_impl.py` shows exactly what `run_shannon_stream_step` expects.)

---

## Optional — exercise the rollout knobs (M3)

| Feature | Env knob | Quick check |
|---|---|---|
| **Concurrency cap** | `MEGAPLAN_WORKER_TURN_CAP=2` | start 3+ Claude turns at once; only 2 run concurrently, the rest queue (slot files under `MEGAPLAN_WORKER_TURN_CAP_DIR`). |
| **Auth channel** | `MEGAPLAN_SHANNON_STREAM_AUTH_CHANNEL=subscription` (default) or `api_key` | with `api_key`, set `ANTHROPIC_API_KEY`/`MEGAPLAN_SHANNON_STREAM_API_KEY` to bill the API instead of the subscription (the "validated flip"). |
| **Sampled shadow** | `MEGAPLAN_CHANNEL_SHADOW_SAMPLE_RATE=0.1` | runs the tmux + stream channels on a ≤10% sample and records deterministic-artifact parity (reuses the bakeoff harness; see `megaplan/bakeoff/channel_shadow.py`). |
| **Idle / execute timeouts** | `MEGAPLAN_SHANNON_STREAM_IDLE_TIMEOUT_SECONDS`, `..._EXECUTE_TIMEOUT_SECONDS` | tune liveness bounds. |

The API-adapter proof is recorded at `docs/shannon-stream-api-proof-record.json` (a dry-run in the
build env — no live API key was present; run Level 3 with `MEGAPLAN_SHANNON_STREAM_AUTH_CHANNEL=api_key`
+ a real key to produce a live proof).

---

## What "passing" means

- **Level 1** green → the implementation is correct.
- **Level 2** green → the headless stream-json channel works against real Claude on the subscription.
- **Level 3** showing a `claude --print` process and **no** tmux/bun → a real megaplan phase ran on
  the new channel, with tmux retained as the fallback.

Design reference: `docs/shannon-stream-channel-plan.md`. Originating ticket: `01KTVV4ANX9MVKBFPRZX6F1AEH`.
