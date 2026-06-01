# M9: Decouple Liveness From Full-State Persistence (heartbeat/WAL root fix)

## Outcome

Make process liveness independent of full-state serialization so a streaming
worker no longer re-serializes the entire plan state (and, on this branch,
re-embeds a full snapshot into the event WAL) just to publish "I am alive at
time T". After this milestone, `state.json` is rewritten **only on genuine
state changes**, the stall monitor learns liveness from a cheap dedicated
channel, and the event WAL stores **diffs, not full snapshots** — eliminating
the ~80%-of-a-core json.dumps churn and the ~33MB-per-milestone `events.ndjson`
bloat at the root, not by throttling.

## Context (why this exists)

During a live LLM stream the in-process token heartbeat fired ~1/s and routed a
one-field liveness timestamp through the full state-write path: a complete
~24KB `atomic_write_json` of `state.json` **plus** an `emit_state_wal` that
embedded the whole snapshot into `events.ndjson`. Measured live: 1779+ full
re-serializations in one milestone, ~80% CPU in `_json` encoding, 33MB WAL
(97% redundant full-state copies).

An **interim mitigation already shipped** — coalescing the heartbeat full-write
to once per `MEGAPLAN_HEARTBEAT_PERSIST_INTERVAL_S` (default 30s) + `os.utime`
for mtime liveness, and (on this branch) skipping the WAL emit on coalesced
beats. Commits: `70a95f63` on `main`, `8d320115` on branch
`fix/arnold-heartbeat-wal-skip`. That is a ~15× band-aid, NOT the root fix: it
still re-serializes the whole blob periodically, still couples liveness to the
state-write path, and the WAL still stores a full snapshot on every *real*
write. This milestone does the architectural fix and supersedes the band-aid.

## Scope

In:
- **Decouple liveness:** introduce a tiny, cheap liveness channel (a sidecar
  file or equivalent — run_id + monotonic/UTC timestamp + phase) written on
  every heartbeat beat without serializing plan state. Update the phase-idle /
  stall monitor (currently `_active_step_last_activity_stale`, reads the
  `active_step.last_activity_at` *content field* out of `state.json`) to read
  this channel instead. Writer and monitor change together (in lockstep).
- After decoupling, the `active-step-heartbeat` write mode of the state writer
  performs **no `state.json` rewrite at all** — heartbeats touch only the
  liveness channel. `state.json` is written solely on real transitions.
- **WAL stores diffs:** change `emit_state_wal` to record a structural diff
  against the last persisted snapshot (plus a periodic full checkpoint), not a
  full `deepcopy(next_state)` on every write. Update the WAL fold/replay
  (`observability/fold.py`) to reconstruct state from checkpoint + diffs.
- Remove or neutralize the interim coalescing band-aid once the decoupled path
  is in place (keep the env knob only if still meaningful).
- Tests: heartbeat performs zero full `state.json` writes and zero full-snapshot
  WAL appends; stall monitor still detects a genuinely dead worker via the new
  channel within the smallest idle threshold; WAL fold replays a
  checkpoint+diff stream to a byte-faithful state; crash-recovery/resume from
  `state.json` is unchanged.

Out / stretch:
- **Hot/cold state split** (separating frequently-mutated small state from
  append-only `history`/`idea`/`last_gate` so even real writes don't re-encode
  cold data) is OUT of this milestone unless it falls out naturally — it is a
  larger restructuring; note it as a follow-up rather than blowing scope.

## Locked Decisions

- The interim coalescing fix (`70a95f63` / `8d320115`) is the baseline this
  supersedes; do not just re-tune its interval.
- Liveness must be observable WITHOUT reading or writing the full state blob.
- `state.json` remains the crash-recovery/resume point; its content semantics
  must not change except that the ephemeral `last_activity_*` fields may move
  out to the liveness channel.
- WAL fold must remain able to reconstruct the exact persisted state
  (checkpoint + replayed diffs == full snapshot).

## Open Questions (resolve in plan/prep, do not invent silently)

- Liveness channel shape: sidecar file vs a dedicated tiny state field written
  with a cheap separate path. Pick one and justify.
- Whether `active_step.last_activity_at` stays in `state.json` (for display /
  receipts) as a snapshot-time value, or moves entirely to the channel.
- WAL diff format + checkpoint cadence (every N writes? size-based?) and how
  fold handles a truncated/partial diff tail after a crash.
- Back-compat: in-flight or archived plans written by the old full-snapshot WAL
  must still fold; pick a versioned WAL record or a migration.

## Constraints

- **Cross-version-safe rollout:** during deploy, a new-code worker may run under
  an old-code driver/monitor and vice-versa — neither may false-stall the other.
  (This is exactly why the interim fix kept the content field fresh.)
- Liveness freshness must stay under the smallest realistic idle threshold
  (~40s; chains tune it low).
- No regression to crash-recovery/resume; no false-stalls of healthy long
  streams.
- Note: by the time this milestone runs, the runtime/state has been relocated by
  earlier milestones (m3a neutral-runtime, m5a state/schemas) — touchpoints
  below are pre-relocation names; prep must re-locate them in the new layout.

## Done Criteria

- A long streaming execute phase produces **zero** heartbeat-driven full
  `state.json` rewrites and **zero** full-snapshot WAL appends (assert via test
  + a quick live check: driver CPU no longer pegged on json.dumps,
  `events.ndjson` growth bounded by real transitions).
- Killing a worker mid-stream is still detected as stalled within the idle
  threshold via the new liveness channel.
- `observability/fold` replays checkpoint+diffs to a state byte-equal to a full
  snapshot, including across the old→new WAL format boundary.
- Resume from `state.json` after an interrupt behaves exactly as before.
- The full `tests/test_plan_state_writer.py` (and WAL/fold + auto-staleness
  suites) pass.

## Touchpoints (pre-relocation names; prep re-locates post-epic)

- state writer: `megaplan/_core/state.py` `write_plan_state` (`active-step-heartbeat` mode), `touch_active_step`
- stall monitor: `megaplan/auto.py` `_active_step_last_activity_stale`
- heartbeat: `megaplan/workers/hermes.py` `_start_heartbeat`
- WAL: `megaplan/observability/events.py` `emit_state_wal`; replay in `megaplan/observability/fold.py`
- tests: `tests/test_plan_state_writer.py`, hermes-liveness + auto-staleness suites

## Anti-Scope

- Do not change phase semantics, resume-cursor logic, or gate/critique behavior.
- Do not undertake the full hot/cold state split here (follow-up).
- Do not weaken stall detection to "fix" CPU — liveness must stay correct.
- Do not leave both the band-aid and the real path active in a way that
  double-writes.
