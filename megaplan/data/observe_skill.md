---
name: megaplan-observe
description: Observe an in-flight or stuck megaplan run — introspect, trace, doctor, and drift detection. Consult when a plan is quiet, blocked, misbehaving, or burning budget faster than expected.
---

# Megaplan Observe

When megaplan is running and something feels off — too quiet, too expensive, or outright blocked — this skill tells you where to look and what to do next. Every question you have about a running plan starts with the same one command: `megaplan introspect`.

## When to reach for this skill

- The user asks "is it still going?" or "what's it doing right now?"
- A plan transitioned to `blocked` and you don't know why.
- Cost is climbing faster than expected and you need to see which model is chewing tokens.
- You suspect a binary or rubric has drifted from what the plan expects.
- A phase has been quiet for longer than its timeout and you need to decide whether to wait or intervene.

Do **not** use this skill for:
- Working with the plan — that's the main `megaplan` skill.
- Filing bugs or observations — that's `megaplan-tickets`.
- Picking a profile or robustness level — that's `megaplan-decision`.

## The four signals

`megaplan introspect --plan <plan>` returns a structured payload. Four fields matter more than the rest:

| Signal | What it tells you | Gotcha |
|---|---|---|
| `now_utc` | The server's clock at introspect time. | **Never** infer recency from JSON timestamps without cross-checking against `now_utc` from the same payload. A stale `state.json` read from disk looks current until you compare it. |
| `active_phase.liveness` | Enum: `active`, `quiet`, `stalled`, `dead`. | Don't assume a phase is stuck before consulting `liveness`. A phase can be `quiet` for 10 minutes and be perfectly healthy. |
| `block_details.recoverable_via` | Ordered list of recovery actions the harness understands. | Never run an override not in this list. If you paste an unlisted override, the harness will reject it with `invalid_transition`. |
| `binary_git.drift` / `rubric_doc.drift` | Tooling and doc misalignment before it bites. | The rubric says "use profile X" but profile X doesn't exist locally, or the binary the plan was built against is a different version than what's on `$PATH`. This is the highest-ROI check in the whole surface — wasted a real session before it existed. |

## The observation hierarchy

When something seems wrong, work through these in order. Each step is cheaper and safer than the next.

1. **`megaplan introspect --plan <plan>`** — one call, full picture. Start here every time.
2. **`megaplan trace --plan <plan> --follow`** — if introspect says `liveness: active` or `quiet` but you want to watch the journal stream as it evolves.
3. **`megaplan doctor --plan <plan>`** — if introspect surfaces a flag you don't recognise or the recovery list isn't obvious.
4. **Direct filesystem inspection** — last resort. If you find yourself reaching for `cat state.json`, file a ticket — introspect should have covered it.

### Trace formatting

```bash
megaplan trace --plan <plan> --format narrative --since 10m
```

`--format narrative` gives you a human-readable timeline. `--since` accepts durations like `5m`, `1h`, `30s`. Without `--follow`, trace prints what's already in the journal and exits.

## Failure-mode catalog

Each entry: the `introspect` signature you'll see, the recovery path, and context.

### Stalled critique

**Signature:** 4 of N critique checks complete, `last_artifact_rel > 15min`, subprocess socket still open, `liveness: quiet`.

**Recovery:** If `last_artifact_rel < phase_timeout / 2`, wait — the model is thinking. If `last_artifact_rel > phase_timeout`, inspect the LLM heartbeat via `megaplan trace --plan <plan> --since <phase_timeout>`. If the heartbeat shows repeated retries without progress, the critique may be stuck in a reasoning loop; escalate to the user.

**Context:** The most common cause is a reviewer that's been assigned too many concurrent checks on a low-tier model. The harness retries internally, but the surface looks like silence.

### Blocked state

**Signature:** `state: blocked`, `block_details.outstanding_flags` populated (typically 1-3 flags), `block_details.recoverable_via` lists one or more actions.

**Recovery:** Read `recoverable_via`. Pick the first applicable action. Execute it via `megaplan override --plan <plan> --action <action>`. Verify the state transitioned away from `blocked` with a follow-up `introspect`. Do not paste an override not in the list.

**Context:** Blocked is not a failure — it's the harness refusing to proceed on a conflict it can't resolve alone. The recovery list is the contract. Respect it.

### Rubric / binary drift

**Signature:** `rubric_doc.drift.missing_locally` non-empty, OR `binary_git.drift.commit` differs from the plan's pinned commit.

**Recovery:** For rubric drift, use a profile from `profiles_available_locally` whose recipe matches what the rubric describes. For binary drift, pin the binary to the SHA the plan was built against (`git checkout <sha>` in the binary's repo). In either case the plan can proceed after the mismatch is resolved.

**Context:** Rubric drift is silent until it isn't — a plan runs and the tool it calls has a different flag surface than the plan expects. `megaplan doctor --repo` run at plan init catches this before any spend occurs.

### Execute loop spinning

**Signature:** `active_phase: execute`, `last_artifact_rel < 2min` but `batch_completion_pct` hasn't moved in >3 cycles, OR cost-per-batch is flat but task completion rate is near zero.

**Recovery:** Run `megaplan trace --plan <plan> --since <3_cycles_duration>` and look for repeated retries on the same task IDs with different worker models. If a particular batch is stalling, the task decomposition may be too fine-grained for the worker to make progress. Escalate to the user with the batch number and a recommendation to increase `max_execute_no_progress` or adjust the task granularity.

**Context:** Execute loops can spin when tasks are decomposed below the model's useful atomicity threshold — the worker completes each task trivially but makes no aggregate progress. The harness counts completions, not impact.

## Do-not rules

These are hard rules derived from real failure modes. Don't break them.

1. **Do not infer wall time from JSON timestamps without `now_utc` cross-check.** A stale read looks current. Always compare against `now_utc` from the same introspect payload.
2. **Do not retry overrides that returned `invalid_transition` — read `recoverable_via` first.** The override list is exhaustive. If your action isn't there, it won't work.
3. **Do not stash / checkout in the megaplan source repo without user consent.** Editable installs make repo state load-bearing. A `git checkout` in the megaplan repo can silently change the tool the running plan is using.
4. **Do not assume a phase is stuck before consulting `liveness`.** `quiet` ≠ `stalled`. The `liveness` enum is computed from multiple signals (heartbeat, socket, artifact recency); trust it over intuition.

## Worked invocation chains

### "Is it still going?"

```bash
megaplan introspect --plan <plan>
```

Read `active_phase.liveness` and `last_artifact_rel`. Narrate them back:

> "It's in the critique phase, `liveness: active`, last artifact 3 minutes ago. Looks healthy."

If `liveness: stalled` or `last_artifact_rel > phase_timeout`, escalate to the failure-mode catalog above.

### "Plan went blocked, what now?"

```bash
megaplan introspect --plan <plan>   # read block_details.recoverable_via
```

Pick the first recovery action, run it, verify:

```bash
megaplan override --plan <plan> --action <first-recoverable-action>
megaplan introspect --plan <plan>   # confirm state is no longer blocked
```

### "Cost is climbing faster than expected"

```bash
megaplan trace --plan <plan> --format narrative --since 10m
```

Look at which model is being called and how often. If `opus` is running sequential retries on a problem `haiku` could handle, the profile may need adjusting. If the execute phase is looping through batches faster than expected, the plan may have over-decomposed the work.

## Quick reference

| You want to … | Run |
|---|---|
| Check if a plan is alive | `megaplan introspect --plan <plan>` |
| Watch a plan as it runs | `megaplan trace --plan <plan> --follow` |
| Diagnose a blocked plan | `megaplan introspect --plan <plan>` → read `block_details.recoverable_via` |
| Check for tooling drift | `megaplan doctor --repo` (at init) or `megaplan introspect` (during run) |
| See what model is burning budget | `megaplan trace --plan <plan> --format narrative --since 10m` |

Start with `introspect`. The answer is almost always in that first payload.

## How this skill fits with the others

| Skill | When to reach for it |
|---|---|
| `megaplan` (main) | Driving the harness — init, plan, execute, review. The operator skill. |
| `megaplan-decision` | Before invocation — profile, robustness, depth. The pre-flight skill. |
| `megaplan-observe` (this skill) | During or after a run — introspect, trace, doctor. The dashboard skill. |
| `megaplan-tickets` | Capture out-of-scope problems found during observation. The note-taking skill. |
| `megaplan-epic` | Work bigger than one sprint — chain multiple megaplan runs. The scaling skill. |

The typical flow: **decide** (megaplan-decision) → **drive** (megaplan) → **observe** (this skill, whenever something feels off) → **ticket** (megaplan-tickets, for anything out-of-scope). If the work is multi-sprint, wrap it in an **epic** (megaplan-epic).
