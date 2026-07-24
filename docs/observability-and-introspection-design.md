# Observability and Introspection — Design Doc

**Status:** Draft proposal (2026-05-18)
**Author:** Filed during a Veas megaplan session that compounded confusion across an hour due to missing observability. Specific failure modes referenced below are drawn from that session's actual transcript.

## Problem

Megaplan today tells you *what state it's in*. It does not tell you *what it's doing, why, since when, or how to intervene*. Symptoms that surface repeatedly:

1. **Stale-timestamp inference.** `state.json` and per-step receipts use ISO timestamps. A caller (human or agent) reads `last_step.timestamp` and assumes recency without a wall-clock anchor, leading to wrong claims about progress.
2. **Opaque blocked state.** `state: blocked` is terminal. The state machine refuses `force-proceed`, `replan`, `critique`, etc. with `invalid_transition` errors — but the caller has to discover by trial which override is valid. There is no forward-looking "here are the moves the state machine will accept right now" surface.
3. **No streaming visibility into LLM calls.** A long critique phase emits per-check artifacts as they complete (good), but nothing between them. The caller can't distinguish "model is still producing tokens" from "TCP wedged" from "rate-limited and retrying."
4. **Rubric/binary drift goes undetected.** The `megaplan-prep` skill describes canonical profiles (`thoughtful`, `basic`, `led`, `premium`, `super-premium`). A local binary that predates the canonical naming, or that's running off a refactor branch with renamed profiles, will silently fail with `Unknown profile 'thoughtful'`. There's no preflight check that catches this.
5. **Editable-install repo drift.** Because the binary is symlinked into an editable virtualenv, any branch switch or uncommitted change in the megaplan source tree changes behavior immediately. Today nothing surfaces this — a switched branch can quietly remove the profile a caller is about to invoke.
6. **No event journal.** State is a current-snapshot file that gets overwritten. Per-phase artifacts land in scattered files; subprocess stdout/stderr go nowhere; LLM calls disappear into provider APIs. To reconstruct "what happened" the caller has to compose `lsof` + `ls -lat` + `cat state.json` + `pgrep` + manual time arithmetic.

## Core insight

Every confusion above traces to the same root: **there's no append-only log of what happened.** Add the journal, build everything else as thin readers over it.

## Architecture

### Foundation: `events.ndjson` per plan

One append-only newline-delimited JSON file per plan: `.megaplan/plans/<name>/events.ndjson`. Every state-changing moment writes one event.

```jsonc
{
  "seq": 142,                          // monotonic, gap-detectable
  "ts_utc": "2026-05-18T14:25:11.483Z",
  "ts_rel_init_s": 3721.4,             // seconds since init — convenient for plotting / sparklines
  "kind": "llm_token_heartbeat",
  "phase": "critique",
  "payload": { ... }                   // kind-specific
}
```

#### Event kinds (~25 total)

- **Lifecycle:** `init`, `phase_start`, `phase_end`, `phase_retry`, `state_transition`, `lock_acquired`, `lock_released`, `plan_aborted`, `plan_finished`
- **Subprocess:** `subprocess_spawned`, `subprocess_exited`, `subprocess_signaled`
- **LLM:** `llm_call_start`, `llm_token_heartbeat` (~1Hz during streaming, with running token count — not per-token), `llm_call_end`, `llm_call_error`
- **Artifacts:** `artifact_written`, `artifact_invalidated`
- **Decisions:** `override_applied`, `flag_raised`, `flag_resolved`, `note_added`
- **Cost:** `cost_recorded` (per LLM call, with provider `request_id`)
- **Diagnostics:** `health_check_failed`, `drift_detected`

Append-only because:
- Replayable post-mortem
- Concurrent writers (parent driver + child workers) tee in safely
- Trivial to `tail -f`
- ~1KB per event × maybe 1000 events per plan = ~1MB, trivial

### Hermes instrumentation (the unlock)

Hermes is megaplan's LLM runtime wrapper. Today LLM calls are opaque to anything outside hermes. The instrumentation:

- `llm_call_start` event with `provider`, `model`, `prompt_hash`, `request_id` (from provider response headers), `streaming: bool`.
- A **token heartbeat** thread that emits `llm_token_heartbeat` every ~1s during streaming with `tokens_emitted_so_far`, `last_token_at`. This is the field that distinguishes "model thinking hard" from "TCP wedged."
- `llm_call_end` with token totals, cost, finish_reason, duration.
- `llm_call_error` with provider error code, `retry-after` if rate-limited.

This single addition is worth half the sprint on its own. Also benefits anything else using hermes, not just megaplan.

## Surfaces

### 1. `megaplan introspect --plan X`

Single call. Reads `events.ndjson` + `state.json` + filesystem + `psutil`. Returns one structured payload.

```jsonc
{
  "now_utc": "2026-05-18T14:31:59Z",        // wall clock embedded — kills the stale-timestamp failure mode
  "now_local": "16:31:59 CEST (UTC+2)",
  "binary_version": "0.21.0",
  "binary_git": {
    "repo": "/path/to/megaplan",
    "branch": "sprint-a-base",              // catches branch flips the moment they happen
    "dirty": true,
    "head": "b6bd1328",
    "editable_install": true
  },
  "rubric_doc": {
    "skill_path": "~/.claude/skills/megaplan-prep/SKILL.md",
    "resolves_to": "/path/to/poms_skills/megaplan-prep/SKILL.md",
    "profiles_referenced": ["basic","led","thoughtful","premium","super-premium"],
    "profiles_available_locally": ["apex","claude-kimi-deepseek","directed","partnered","premium","solo","..."],
    "drift": {
      "missing_locally": ["basic","led","thoughtful","super-premium"],
      "warning": "rubric references 4 profiles your binary doesn't expose"
    }
  },
  "active_phase": {
    "name": "critique",
    "model": "fireworks:accounts/fireworks/models/kimi-k2p6",
    "started_at": "2026-05-18T13:53:27Z",
    "started_rel": "38m 32s ago",            // computed against now_utc above
    "last_artifact_at": "2026-05-18T14:25:11Z",
    "last_artifact_rel": "6m 48s ago",
    "last_artifact_path": "critique_check_issue_hints.json",
    "liveness": "progressing",                // ENUM: progressing | quiet | stalled | timeout-imminent
    "liveness_reason": "wrote 4 artifacts in last 32m; 5th in flight",
    "subprocess": {
      "pid": 58769,
      "cpu_percent": 0.3,
      "rss_mb": 142,
      "open_network_sockets": 1,
      "last_stdout_at": "14:25:11Z (6m ago)",
      "last_stderr_at": null
    }
  },
  "block_details": {                          // populated only when state=blocked
    "reason": "stalled_at_critique",
    "stalled_after_iterations": 5,
    "last_successful_phase": "critique",
    "outstanding_flags": [
      {"id":"FLAG-V4-001","severity":"high","summary":"brief invariant 2 contradicts decision 8 on slot body extension"},
      {"id":"FLAG-V4-002","severity":"medium","summary":"partner_sharing.py not addressed"}
    ],
    "recoverable_via": [
      "fix brief and re-init (recommended)",
      "override add-note + override force-proceed",
      "override replan (requires state ∈ {critiqued, failed, finalized, gated})"
    ]
  },
  "process_tree": [
    {"pid":58769, "cmd":"python3 megaplan auto --plan ...-v5", "role":"auto_driver",   "since":"15:23 local"},
    {"pid":58800, "cmd":"python3 -m hermes ...kimi-k2p6 ...", "role":"critique_worker","since":"15:53 local","parent":58769}
  ],
  "timeline": [
    {"t":"13:23:10Z", "rel":"1h 8m ago",  "evt":"init",          "dur":"0s",    "cost_usd":0.00, "model":"-"},
    {"t":"13:27:57Z", "rel":"1h 4m ago",  "evt":"plan done",     "dur":"4m21s", "cost_usd":0.51, "model":"claude:opus"},
    {"t":"13:53:27Z", "rel":"38m ago",    "evt":"critique start","dur":"running","cost_usd":0.00,"model":"kimi-k2p6"},
    {"t":"14:13:00Z", "rel":"19m ago",    "evt":"check scope complete"},
    {"t":"14:13:00Z", "rel":"19m ago",    "evt":"check correctness complete"},
    {"t":"14:25:11Z", "rel":"6m ago",     "evt":"check issue_hints complete"},
    {"t":"14:25:11Z", "rel":"6m ago",     "evt":"check all_locations complete"}
  ]
}
```

The four killer fields:
- `now_utc` — the anti-stale-timestamp anchor. Every relative time elsewhere in the payload is computed against this.
- `rubric_doc.drift` — the single check that prevents an hour of profile-name flailing.
- `active_phase.liveness` (enum) — `progressing` says wait; `stalled` says intervene; `timeout-imminent` says decide now.
- `block_details.recoverable_via` — the list of moves the state machine will accept. Never try a recovery action that isn't in this list.

### 2. `megaplan trace --plan X [--phase Y] [--follow] [--since DURATION] [--format json|pretty|narrative]`

Reads `events.ndjson`. Three formats:

- `--format json` — raw events, pipe-friendly.
- `--format pretty` *(default)* — indented timeline, colored kind labels, relative times computed against current wall clock.
- `--format narrative` — synthesised prose, e.g.:
  > "13:53 → critique started using kimi-k2p6 on Fireworks. Token stream began 8s later, has emitted 4,200 tokens at an average 18 tok/s. Last token 2.3s ago — actively producing."

The narrative format is the killer for AI-agent consumption — one paragraph that names the right things.

`--follow` streams new events. Use during long phases instead of polling.

### 3. `megaplan doctor [--plan X | --repo]`

Diagnostic. Output is a list of `[OK | WARN | ERROR]` lines, each with a remediation hint.

**Plan-level** (`--plan`):
- Lock present but holder dead → stale lock, recoverable with `--clear-lock`
- Phase running > 80% of `phase_timeout` → consider extending or killing
- LLM call with no heartbeat for > 60s → likely wedged
- Cost trajectory > 2× nominal for tier → unexpected spend, drill in
- Subprocess orphans (megaplan-spawned but parent gone)
- Outstanding flags + how to clear each

**Repo-level** (`--repo`):
- **Rubric/binary drift:** load the megaplan-prep skill, extract every profile name it references, diff against `megaplan profiles list`. WARN on each mismatch with the specific bridge (`"rubric says 'thoughtful', binary doesn't have it; on main HEAD it does; you're on 'sprint-a-base' which renamed it"`).
- Editable install + dirty working tree → behavior changes will land on next phase.
- Multiple megaplan checkouts on disk → potential confusion source.
- Skill files out of sync with their installed copies.

This single command would have prevented the entire first hour of the session that prompted this doc.

### 4. `megaplan dash --plan X` (TUI)

Textual-based persistent dashboard. Six panes read from `events.ndjson` incrementally:

```
┌─ prompt-registry-and-reminder-bundling-v5 ─────────────────────┐
│ state: planned  phase: critique (38m 32s)  cost: $0.51/$30.00  │
├─ Phase timeline ───────────────────────────────────────────────┤
│ init     ████ done   5m  $0.00                                 │
│ plan     ████████ done  4m21s  $0.51                           │
│ critique █████████████░░░░░░░ 4/5 checks  $0.00 so far         │
│ gate     ░ pending                                             │
├─ Active LLM call ──────────────┬─ Live token rate ─────────────┤
│ model: kimi-k2p6 (fireworks)   │  ▁▂▄▆█▆▄▂▁▂▃▅▇█▆▄▂▁▃▆█▇▅▃   │
│ tokens: 4,243  last: 2.3s ago  │  18 tok/s avg                 │
├─ Recent events ────────────────┴───────────────────────────────┤
│ 14:25:11 ✓ artifact_written critique_check_issue_hints.json    │
│ 14:25:11 ✓ artifact_written critique_check_all_locations.json  │
│ 14:13:00 ✓ artifact_written critique_check_correctness.json    │
│ 14:13:00 ✓ artifact_written critique_check_scope.json          │
├─ Outstanding flags ────────────────────────────────────────────┤
│ (none)                                                         │
└── [q]uit  [p]ause-follow  [t]ag-now  [o]verride-menu ──────────┘
```

The TUI is a polish surface; `introspect` is the primary interface. The TUI reads the same data.

### 5. `megaplan record-tag --plan X --tag NAME --note "..."`

Emits a tag event into the journal. Lets humans (or agents) annotate moments during a run — "user intervened here", "noticed unusual token rate", "cost cap raised". Makes post-mortems possible.

## Two-week sprint plan

| Day | Work | Why |
|---|---|---|
| 1 | Event schema design doc; enumerate every kind; write payload schemas with examples. Land in `docs/events.md`. | Schema lock-down before any code. |
| 2 | Event writer library + integration at phase boundaries in `megaplan/handlers/*.py`. State transitions emit. Lock acquire/release emits. | Foundation: every existing transition becomes journaled. |
| 3 | Subprocess instrumentation: wrap spawn points in hermes / `claude_subagent` / `codex_subagent` to emit `subprocess_spawned` and capture stdout/stderr to per-phase `.live.log` files. | Subprocess visibility from outside. |
| 4 | Hermes LLM call instrumentation: `llm_call_start` / `heartbeat` / `end` / `error`. Provider `request_id`s captured. ~1Hz heartbeat during streaming. | The unlock for live LLM observability. |
| 5 | `megaplan introspect` command. Reads journal + state + filesystem + `psutil`. Schema-locked output. Tests against fixture journals. | First user-visible surface. |
| 6 | `megaplan trace` command. Pretty / JSON / narrative formats. `--follow`, `--phase`, `--since` filters. Relative-time rendering against wall clock. | Streaming visibility for long phases. |
| 7 | `megaplan doctor` for plan-level: stale locks, wedged LLM calls, phase-timeout-imminent, orphan subprocesses, outstanding flags + `recoverable_via`. | Diagnostic for in-flight issues. |
| 8 | `megaplan doctor --repo`: rubric/binary drift detection (parses skill MD, extracts profile names, diffs against `profiles list`), editable-install + dirty-tree warning, multiple-checkout detection. | The single check that prevents this design doc's motivating session. |
| 9 | TUI `megaplan dash` skeleton with `textual`. Six-pane layout reading from journal. | Polish surface for humans. |
| 10 | TUI polish: token-rate sparkline, color coding, keybindings, override menu. | Make it pleasant. |
| 11 | Auto-driver integration: `megaplan auto` emits richer events and streams structured progress to its parent (so a parent agent harness gets pushed-to instead of polling). | Closes the loop with the broader agent layer. |
| 12 | Skill doc work — see "Skill documents" below. New `megaplan-observe` skill drafted. | Make the tooling reachable for agents. |
| 13 | Failure-mode runbook: every common stuck state with the `introspect` signature and the recovery path. Backed by fixture journals captured from prior incidents. | Teach the recoveries, not just the tooling. |
| 14 | Doc pass, integration tests, smoke test against a real `megaplan auto` run, ship. | Land it. |

## Skill documents

Today: one skill (`megaplan-prep`) covering profile selection. After: **two skills, complementary.**

### Skill 1 (small additions): `megaplan-prep`

Still about picking profile / robustness / depth *before* a run. Two changes:

- Top-of-skill **preflight checklist** mentioning `megaplan doctor --repo` as the first thing to run when the rubric and binary haven't been used together recently.
- A "drift" callout box noting that the skill describes canonical names; legacy aliases or in-progress refactor states may not have them; pointing at `doctor --repo` for the bridge.

### Skill 2 (new): `megaplan-observe`

About what to do *during and after* a run. Sections:

**1. The four signals.** What `introspect` returns and why each field exists:
- `now_utc` — the anti-stale-timestamp rule. Never infer recency from JSON timestamps without cross-checking against `now_utc` from the same payload.
- `active_phase.liveness` (enum) — what to do in each state.
- `block_details.recoverable_via` — never try a recovery action not in this list.
- `binary_git.drift` / `rubric_doc.drift` — surfaces tooling/doc misalignment before it bites.

**2. The observation hierarchy.** When something seems wrong, in order:
1. `megaplan introspect --plan X` (one call, full picture)
2. `megaplan trace --plan X --follow` (if introspect says progressing but you want to watch)
3. `megaplan doctor --plan X` (if introspect shows a flag you don't recognise)
4. Direct filesystem inspection (last resort; if you need this, file a bug — introspect should cover it)

**3. Failure-mode catalog.** Each entry: `introspect` signature, recovery, worked example from a real journal.
- *Stalled critique*: 4 of N checks complete, `last_artifact_rel > 15min`, subprocess still has open socket, `liveness: quiet`. → Wait if `last_artifact_rel < phase_timeout/2`, else inspect LLM heartbeat.
- *Blocked state*: `state: blocked`, `block_details.outstanding_flags` populated. → Read `recoverable_via`; pick first applicable; never paste an unlisted override.
- *Rubric/binary drift*: `rubric_doc.drift.missing_locally` non-empty. → Use a profile from `profiles_available_locally` whose recipe matches what the rubric describes, OR pin the binary to a state that has the canonical names.

**4. The do-not rules.** Explicit, short, named — derived from real failure modes:
- "Do not infer wall time from JSON timestamps without `now_utc` cross-check."
- "Do not retry overrides that returned `invalid_transition` — read `recoverable_via` first."
- "Do not stash / checkout in the megaplan source repo without user consent — editable installs make repo state load-bearing."
- "Do not assume a phase is stuck before consulting `liveness`."

**5. Worked invocation chains.** Several real scenarios end-to-end:
- "User says 'is it still going?'" → `introspect` → narrate `active_phase.liveness` + `last_artifact_rel`.
- "Plan went blocked, what now?" → `introspect.block_details.recoverable_via` → execute first option → verify state transition.
- "Cost is climbing faster than expected" → `trace --format narrative --since 10m` to see which model is being called and how often.

## Why this is the right two weeks

1. **The event journal is leverage, not a feature.** Every surface above is a thin reader over the same file. The journal is the only thing that has to be *right*; everything else is presentation. That makes the work safe (each surface is small, independently replaceable) and the maintenance burden low.

2. **The drift check pays for the sprint by itself.** Rubric/binary drift cost the motivating session ~$1.50 of wasted spend and an hour of context. At one sprint per week across a team running megaplan, that compounds fast. `megaplan doctor --repo` as the first thing in any plan's lifecycle is the single highest-ROI piece.

3. **The skill docs make it reachable.** Without `megaplan-observe`, an agent (or a human in a hurry) still reads `state.json` directly and misses the `liveness` field. The skill is what turns the tooling into behaviour change.

## One-line summary

Today megaplan tells you *what state it's in*. The two-week build makes it tell you *what it's doing, why, since when, and how to intervene*.
