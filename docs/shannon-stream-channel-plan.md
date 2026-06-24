# Shannon: from tmux-puppeteering to a headless stream-json channel

**Status:** build spec (validated) · **Date:** 2026-06-11
**Supersedes (long-term):** ticket `01KTVV4ANX9MVKBFPRZX6F1AEH`
**Validation:** two independent DeepSeek panels (10 load-bearing + 10 system bets) + a live Phase-0 spike.
Findings are folded in below as resolved design decisions, not open questions.

---

## 1. The problem

Megaplan's **Shannon** worker runs **Claude** by **puppeteering the interactive `claude` TUI through
tmux**: per phase it cold-spawns a fresh `claude`, screen-scrapes the pane for readiness, pastes the
prompt, tails Claude Code's on-disk transcript to read the reply, then tears it down. The other engines
are clean — **Codex** via `codex exec`, **Hermes (DeepSeek/Kimi)** via HTTP. Only Claude is driven
through its UI.

At scale (many concurrent chains on one box) the puppeteering is a continuous fragility generator —
one milestone on 2026-06-11 cost a full day and ~10 root-fixes, almost all infra, not work. Root cause
(the ticket's): **we run an interactive, single-user tool as a programmatic, many-tenant service,
without a stable invocation boundary or a resource governor.** The eight named failures: corrupt-binary
stub, `CLAUDECODE` transcript suppression, shared-tmux-server collapse, bun dead-turn hang, opaque
readiness, subscription starvation, baseline storm, and timeouts-firing-as-hangs.

---

## 2. What we proved before committing

**The channel exists and is sound (Phase-0 spike, `claude` 2.1.173).** A non-`-p` interactive stream-json
mode does **not** exist (`--input/--output-format` only work with `--print`), so the channel is
**headless `--print`** — exactly what the old "never `-p`" rule banned. One controlled turn refuted that
rule's premise:
- **Bills the subscription** (`apiKeySource: none`, succeeded with the API key forced empty).
- **Full semantic parity** — identical tool/skill/subagent list, model `claude-opus-4-8[1m]`.
- **Writes a real transcript** once `CLAUDECODE` is scrubbed.
- **Structured turn-end** (`result` event) + an inline **`rate_limit_event`** (rolling utilization).
- **Multi-turn + resume** both work; **`--permission-mode bypassPermissions`** is the minimum that lets
  tools execute headlessly (verified by a file written to disk). `acceptEdits` is cwd-sandboxed and an
  unexpected headless denial makes the model *ask* → hangs.

**The relay alternative is worse (panel 1).** The ticket's recommended option — a warm relay dispatching
Task subagents via a file handshake — regresses fidelity (a subagent is *not* a real-user turn), only
solves the answer-read half (death detection still needs the full liveness stack), and needs a relay
*pool* with mandatory recycling. Headless stream-json beats it on every axis. **Decision: stream-json is
the channel; the relay is shelved as a documented fallback.**

---

## 3. Design principles (the spine everything hangs off)

1. **One channel, real Claude.** Drive the same engine a human drives — headless, structured, no UI
   scraping. Fidelity and simplicity are the same choice.
2. **The contract is an interface, not a transport.** `run_step(step, state, dir) -> WorkerResult`, with
   two orthogonal axes: **transport** (stream-json / HTTP / `codex exec`) and **auth/billing channel**
   (subscription-OAuth ↔ API-key). Hermes and Codex already satisfy it natively; only Shannon needs new
   transport code. Never force one transport onto an engine that has a clean one.
3. **Cap the resource now; govern it only when a billing boundary makes scaling safe.** Two Codex
   high-abstraction reviews converged: a sophisticated cross-engine governor is *throughput-enablement*
   wearing exposure-reduction's costume — it makes the one risky thing (concurrency on a single
   subscription seat) bigger and smoother. Most Bucket-B pain came from running 8–9 concurrent, not from
   a missing scheduler. So **a blunt concurrency cap (~3) replaces the governor** for now; the real
   per-channel governor is deferred until an API/enterprise billing boundary exists to scale into. The
   durable assets are **the seam and the API adapter**, not the scheduler.
4. **Fail fast, attributed.** Every wedge surfaces in seconds as a typed, engine-attributed error. A
   missing signal degrades to "conservatively alive," never to a silent hang.
5. **Tell the truth about the boundary.** The safety boundary is the **OS user** (and, under root,
   drop-to-unprivileged), *not* the worktree — because `bypassPermissions` ignores cwd and the megaplan
   sandbox isn't installed on the Claude path. Either install it on the new path or document this plainly.
6. **Additive, reversible, dogfood-safe.** Build the new worker alongside the old, flag-gated, from a
   separate known-good driver checkout — the running engine never depends on half-built code until cutover.

---

## 4. Architecture

**4.1 The invocation seam.** `run_step -> WorkerResult`. The dispatch already bifurcates cleanly
(hermes / shannon / codex) and callers consume only neutral fields (`payload`, `session_id`, `cost_usd`,
tokens). Two additions make it host the governor and the new channel without leaks:
- Add a **typed `rate_limit: dict | None`** to `WorkerResult` (Shannon populates it; others `None`). The
  governor reads the rate signal *through the interface*, never via a Shannon backchannel.
- Treat `session_id` as opaque and keep the lone branded field (`shannon_plan`) optional. The retry path
  is the **only** place allowed to branch on engine; a new engine must self-clean its session like
  Shannon does, not grow a new retry arm.

**4.2 `ShannonStreamWorker`.** Headless stream-json behind the seam: launch (env-scrub +
`bypassPermissions` + cwd=worktree) → parse `init / assistant / result / rate_limit_event` →
`WorkerResult`. Multi-turn via `--input-format=stream-json` (primary) with `--resume` as the
restart-survival fallback. The explicit `result` event is the unambiguous turn-end/death signal. **The
three-channel liveness probe re-homes onto the direct subprocess PID** (today's channels 2–3 read tmux
pane-pids; under stream-json the Claude process is a direct child — use `process.pid`). A
**permission-fail-fast watchdog** treats any headless "awaiting-permission / unexpected-denial" state as
an immediate *retryable* fail, so a denial can never wedge the channel (this is the fail-slow→fail-fast
property failure #8 demands).

**4.3 No local admission throttle.** The former local concurrency throttle has been removed. It throttled
unrelated agents at the host layer and produced synthetic `rate_limit` failures that looked like provider
capacity. The `rate_limit` field (§4.1) is still surfaced and *logged* for backpressure visibility, but
Megaplan now relies on provider/API signals and normal recovery policy rather than a local admission
throttle. Any future governor must live at an explicit API/enterprise billing boundary with real quota
semantics, not as a host-global slot file.

**4.3b Prove the API adapter early (the replaceable path).** Through the *same* `run_step` seam, run a
real phase on an **API key** instead of subscription OAuth — measuring cost, quota, and tool/permission
parity — so "subscription → API" is a *validated flip*, not a deferred leap. Ship an explicit
**migration-trigger list**: switch the auth axis to API when (a) the rate-event schema or permission
semantics break, (b) sustained utilization structurally exceeds a set ceiling, (c) megaplan grows
multi-tenant/commercial, or (d) any policy signal appears. The subscription channel is a *bounded tenant*
of the seam; the API channel is the destination, wired and tested, not yet walked.

**M3 API-adapter proof record (2026-06-12).** The current implementation environment has no live
`ANTHROPIC_API_KEY` or `MEGAPLAN_SHANNON_STREAM_API_KEY`, so the recorded proof is **dry-run only**:
`docs/shannon-stream-api-proof-record.json`. This validates adapter plumbing only: `api_key` auth-channel
selection reaches `ShannonStreamWorker`, missing-key handling stays explicit, and non-secret auth metadata
is present in traces and receipts. It does **not** validate live API billing, API quota/rate-limit
behavior, API tool-permission parity, API-channel shadow parity, or stream-json default cutover. Until a
live API-key-backed phase completes and writes cost, token, quota/rate-limit, permission-mode, and payload
schema evidence into this record, downstream shadow/cutover work may only claim subscription
stream-vs-tmux parity.

Migration triggers remain the same whether this record is dry-run or live: switch the auth axis to API
when the subscription stream path's rate-event schema or permission semantics break, sustained utilization
requires provider-backed API quota or enterprise billing controls, megaplan becomes multi-tenant or
commercial, or provider policy/billing guidance requires API-key usage.

**4.4 Drift defense (always-on).** Today's "stream-json" is the vendored wrapper's *synthesized* events;
the plan moves to Anthropic's **native** `--print` schema — a different, undocumented-stability surface,
and the vendor has broken this surface twice (2.1.169 transcripts, 2.1.170 env behavior). So:
- **Defensive parsing** — tolerate unknown event types *and* renamed fields; never silently fall through
  to a garbage payload.
- A **CI conformance smoke-test** — invoke `claude --print --output-format=stream-json` on a trivial
  prompt against the pinned version, validate the full event schema *and* that `bypassPermissions` still
  executes a tool headlessly. This is what catches a 2.1.170-class break at upgrade time, not in prod.
- **Autoupdater lock** — pin the binary with `autoUpdates:false` / `DISABLE_AUTOUPDATER` (absent from the
  codebase today) so a version can't flip underneath a run.

**4.5 Keep the landed guards** (env-scrub, binary validator, retryable phase-timeout, idle/hard-cap
watchdogs, baseline gate). They remain load-bearing under the new channel.

---

## 5. Execution sequence — 4 milestones (an epic)

Sized as four ~2-week milestones. Briefs: `.megaplan/briefs/shannon-stream/`.

- **M1 — The seam.** Define `run_step -> WorkerResult`; add the typed `rate_limit` field; route existing
  Hermes + Codex through it unchanged; retry-path is the only engine-aware spot. Behavior-preserving; the
  green suite backstops. *Exit:* full suite green, zero behavior change.
- **M2 — `ShannonStreamWorker` + drift defense.** (a) launch+scrub+bypass+cwd; (b) stream-json parser →
  result, emitting `rate_limit`; (c) multi-turn + `--resume`; (d) permission fail-fast watchdog;
  (e) re-home liveness onto the subprocess PID; (f) **drift defense** — defensive parsing, CI conformance
  smoke-test against the pinned binary, autoupdater lock. **Additive + flag-OFF** (the running engine
  keeps using the old tmux path). *Exit:* one real phase runs through it behind a flag.
- **M3 — API-adapter proof.** No local admission throttle; the same seam is proven on an API key with
  cost/quota/parity measured + the migration-trigger list (§4.3b). *Exit:* contention surfaces provider
  capacity through normal external-error paths; a phase completes on the API channel.
- **M4 — Shadow + cutover; keep tmux.** Sampled shadow (**≤10%** of phases, reusing the bakeoff harness)
  on **deterministic artifacts** (`exit_kind`, payload schema validity, `landed_diff`, `worker_did_work`)
  at **N≥5**; flag-gated cutover with per-phase `fresh=True` on switch; rewrite the babysit ground-truth
  section. **tmux is retained as a maintained fallback, NOT retired** — deletion waits until the API path
  is independently production-proven, a separate future decision. *Exit:* N≥5 parity, a week of green
  default runs, tmux still flag-reachable.

**Always-on across milestones:** the §3.5 safety-boundary decision (install the sandbox on the new path,
or document the OS-user boundary plainly).

---

## 6. Build-safety (the dogfood trap)

This is megaplan rewriting its own execution path. Build against a **separate known-good driver checkout
off a clean branch**, and scaffold `ShannonStreamWorker` **additively** alongside the old worker, flag-gated, so the
running engine never depends on half-built code until the step-5 cutover.

---

## 7. The exposure axis (why the billing seam exists now)

Per-request, headless `--print` is ~indistinguishable from a human pasting (same binary, same backend,
same client identity). What's legible is the account's **aggregate shape**, and the un-disguisable tell
is **concurrency**: one OAuth seat with N sessions simultaneously in flight is categorically not a human —
and the metering system already computes this (it produced the 0.84 figure). So exposure is dominated by
**concurrency + volume, not protocol**, and the governor (§4.3) is precisely what raises concurrency. The
cheap insurance: the §3.2 auth/billing seam makes subscription-OAuth → API-key a config flip, not a
rewrite, for the day this scales or Anthropic meters the seat. Until then the governor doubles as the cap
that keeps the shape modest.

---

## 8. What the validation changed (for the record)

The two panels confirmed the core decision and corrected five things now baked in above: **(1)** governor
before shadow, and shadow sampled — or it starves the live subscription; **(2)** the safety boundary is
the OS user, not the worktree (the sandbox isn't on the Claude path); **(3)** the governor must be
cross-engine/per-auth-channel — Codex burns the same subscription with no admission control; **(4)** the
rate axis needs a typed `WorkerResult` field + a shared token-bucket over all windows, not per-turn reads;
**(5)** drift defense (conformance test + autoupdater lock + defensive parsing) is mandatory and largely
absent today. None of the findings challenged the central thesis: headless stream-json is the right
channel.
