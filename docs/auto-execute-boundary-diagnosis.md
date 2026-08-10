# Auto-driver ↔ Execute Boundary: Architectural Diagnosis

Read-only analysis. Source: bug cluster on 2026-05-11 (`c0ebd3c6`, `eb4ac447`,
`2c5bfb22`, plus an unfixed Bug 4).

## 1. What I actually looked at

- `megaplan/auto.py`
  - `_run_megaplan` and the two parallel subprocess branches (lines 139–260)
  - `_run_phase` wrapper (789–807)
  - `_status` (284–297) and the per-iteration call (837–840)
  - `_phase_command` for execute (304–329)
  - `_read_execute_blocked_task_notes` / `_read_execute_blocking_deviations`
    / `_last_history_step_result` (337–458)
  - The main loop’s post-execute handling: lines 1245, 1313–1327, 1368–1411
  - The `on_phase_complete` callback boundary (1330–1361, used by `chain.py`
    `phase_callback` at 1095–1104)
- `megaplan/execute/core.py`
  - `handle_execute_auto_loop` (1034–1129) — the cross-session blocked reset
    and the within-session short-circuit
  - The batch-coverage check using `TERMINAL_TASK_STATUSES` (380–411)
- `megaplan/execute/merge.py` — `TERMINAL_TASK_STATUSES` (15–17)
- `megaplan/execute/timeout.py` — the timeout-recovery shape that also writes
  history and an `execution_batch_*` artifact
- `megaplan/handlers/execute.py` — entry point that returns a `StepResponse`
  and the post-response state-mutation logic (60–201)
- `megaplan/profiles/__init__.py::apply_profile_expansion` (143–210), the
  three-tier precedence merge
- `megaplan/cli.py`
  - `render_response` and `error_response` (87–147)
  - `_build_active_step` and where `phase_progress_summary` is computed
    (280–343) — confirms this field is only emitted by `status`, never by
    `execute`
  - Top-level `main` dispatch (1707–1715)
- `megaplan/workers.py` — direct `print(...)` calls that go to the same
  stdout the final JSON uses (175, 1784, 1810, 1989, 2022, 2051, 2128, 2156,
  2183, 2241)
- `megaplan/progress.py` — confirmed progress events go to a `Store` (file
  or DB), not stdout
- `megaplan/chain.py` `_commit_and_push_phase` (721–784) and
  `phase_callback` (1095–1104), to see what runs synchronously after
  execute under chain mode

## 2. Thesis

The auto driver and the execute subprocess do not share an interface — they
share a *coincidence* of files on disk, exit codes, stdout text, and a
state-machine convention, and every one of the four bugs is a place where
one side of the boundary believed something about the other that wasn’t
written down. The “API” between `auto.py` and `megaplan execute` is
implicit, narrow at the points where it should be wide (no structured
phase-result transport) and wide at the points where it should be narrow
(every phase rehydrates its own args from `state.json`, every retry
classification re-reads disk artifacts and string-matches free-text
deviations). The fix is not “add another flag” — it is to make the
phase-boundary an explicit, schema’d hand-off so the driver doesn’t have
to *infer* what happened from the union of (exit code, state.json,
execution_batch_N.json, stdout text, history entries).

## 3. Evidence

### Bug 1 — profile precedence across subprocess rehydration

`auto.py:187` and `auto.py:1242` spawn `python -m megaplan <phase> --plan ...`
with **no `--phase-model`, no `--profile`, no robustness flag.** The child
re-derives all of that from `state["config"]` via
`apply_profile_expansion`. The “args” passed across the boundary are
*state.json itself*. The bug existed because the original
`apply_profile_expansion` was correct on the first invocation
(`cli_steps` from current CLI) but wrong on rehydration (current CLI is
empty; `cli_steps` is empty; the profile defaults win again). The fix
(`c0ebd3c6`) didn’t introduce an explicit “persisted CLI” argument — it
re-derived precedence inside the function, threading a third source of
truth into a two-source design.

> `profiles/__init__.py:156`: `cli_phase_models = list(getattr(args, "phase_model", None) or [])`
> `profiles/__init__.py:188`: `persisted = list((state.get("config") or {}).get("phase_model") or [])`

Two “current CLI” candidates (live args and persisted args) collapsed into
one ordering decision, with the live one snapshotted before profile
expansion so a later subprocess can tell them apart. This is a workaround
for the fact that the subprocess transport doesn’t carry CLI provenance.

### Bug 2 — terminal-status drift + free-text retry classification

The schema enum and the coverage filter were independent literals:

> `execute/core.py:392`: `enum_fields={"status": set(TERMINAL_TASK_STATUSES)}`
> `execute/core.py:406`: `if all_tasks_by_id.get(tid, {}).get("status") in TERMINAL_TASK_STATUSES`

The fix factored a shared constant (`execute/merge.py:15`,
`TERMINAL_TASK_STATUSES = {"done","skipped","completed","blocked"}`).
Good — but the deeper problem is on the *other* side of the boundary.
`auto.py:393–398` enumerates **prefixes of human-readable deviation
strings** to decide what counts as a blocking failure:

```python
blocking_prefixes = (
    "tasks have no executor update",
    "sense checks have no executor acknowledgment",
    "done tasks missing both files_changed and commands_run",
    "Done tasks missing sections_written",
)
```

This is the auto driver string-matching the executor’s prose deviations.
The deviation message and the retry classifier are in different files,
written by different prompts of the human author, and any rewording of
one will silently desynchronise the other.

### Bug 3 — within-session vs cross-session retry

`execute/core.py:1086–1129` short-circuits with `result=blocked` when any
finalize task already has `status="blocked"`. This is a correct
within-session optimisation. The fix (`2c5bfb22`) added a CLI flag
`--retry-blocked-tasks` that the auto driver passes unconditionally
(`auto.py:323–328`), and execute resets blocked→pending if the flag is
set (`execute/core.py:1060–1069`).

The fix works. But notice the shape: a new flag was added because there
was nowhere to encode “invocation #” on the boundary. The
single-process state machine treats session N’s persisted status and
session N+1’s starting status as the same state. The driver compensates
by always sending the “forget last session’s memo” flag. That is a hint
that the persisted state has no notion of “session” at all.

### Bug 4 — truncated `phase_progress_summary` JSON

This is the strongest evidence for the thesis. `phase_progress_summary`
appears **only in `cli.py:314–342`**, inside the `status` subcommand. It
is **never** emitted by execute. The auto loop calls `_status(plan)`
at the top of every iteration (`auto.py:840`), and `_status` raises
`RuntimeError` on any non-zero exit (`auto.py:295–297`).

`_status` uses the *no-idle-timeout* branch of `_run_megaplan`, which is
`subprocess.run(..., capture_output=True, timeout=status_timeout)` with
`DEFAULT_STATUS_TIMEOUT_SECONDS = 60`. On `TimeoutExpired`, `_run_megaplan`
returns the *partial* `proc.output` plus `PHASE_TIMEOUT_EXIT_CODE`
(line 183), at which point `_status` raises and the driver bails. If
the status child happened to be midway through `print(json_dump(response))`
when killed, the caller sees truncated JSON.

My read: **the report’s “execute subprocess” is the `status` subprocess
run between iterations.** The execute subprocess itself does not emit
`phase_progress_summary` anywhere in the code I read, and the auto driver
does not parse execute’s stdout as JSON (it only string-tails the last
400 bytes for logging, `auto.py:1317, 1327`).

Even if I’m wrong about which subprocess truncated, the same structural
issue is present: stdout from any phase subprocess is a *mixed* channel —
`workers.py` prints plain-text `[megaplan] Detected poisoned session…`
notices to the same stdout that `render_response` later flushes a single
JSON blob to (`workers.py:1784,1810,1989,2022,2051,2128,2156,2183,2241`).
No framing, no record separator. The auto driver doesn’t parse this for
execute today, but `chain.py`’s `phase_callback` *does* run synchronously
after execute reads `out` and `err`. The channel is overloaded and the
discipline that nothing reads it as JSON is policy, not type.

### The pattern in one picture

| Bug | What the driver/handler *needed* | What the boundary *provided* |
|-----|-----------------------------------|------------------------------|
| 1   | The CLI args the human typed     | `state.json["config"]` re-parsed |
| 2   | A structured “task blocked, reason X” signal | An array of free-text deviations |
| 3   | “This is invocation #N”          | One mutable file on disk |
| 4   | A clean RPC return value         | Captured stdout that mixes notices and JSON |

Every row is the auto driver inferring something the execute subprocess
should be telling it explicitly.

## 4. The missing abstraction

The missing abstraction is a **PhaseResult transport**: a structured,
schema-validated record written by the phase subprocess to a *known*
file (or, equivalently, the final line of stdout under an unambiguous
framing prefix) and read by the auto driver as the single source of
truth about “what the phase did.”

Interface:

```python
@dataclass(frozen=True)
class PhaseResult:
    phase: str                       # "execute", "review", ...
    invocation_id: str               # ULID; encodes session boundary (Bug 3)
    exit_kind: Literal[              # explicit enum, not (exit_code, stdout) tuple
        "success", "blocked_by_quality", "blocked_by_prereq",
        "timeout", "context_exhausted", "internal_error",
    ]
    blocked_tasks: list[BlockedTask] # task_id + structured reason (Bug 2)
    deviations: list[Deviation]      # structured: kind + payload, not free text
    artifacts_written: list[str]
    cli_provenance: dict             # the live args this run was given (Bug 1)
```

What it owns:
- The single contract between any phase and the auto driver. Phases stop
  embedding their conclusions in `history[-1].result + deviations[*] (free
  text) + state["current_state"] + finalize.json[*].status`. They emit
  one `PhaseResult`.
- The notion of “invocation” / session boundary that Bug 3 needed.
- The CLI provenance (live args) the rehydration path in Bug 1 needed.

What it stops scattering:
- `_last_history_step_result(plan_dir, "execute")` reading state.json
- `_read_execute_blocked_task_notes(plan_dir)` reading
  `execution_batch_*.json`
- `_read_execute_blocking_deviations(plan_dir)` re-parsing the same file
  with a different filter
- The prefix-match table in `auto.py:393–398`
- The “did execute return result=blocked?” branch at `auto.py:1368–1411`

Counterfactual:
- **Bug 1** would not exist because the subprocess would carry CLI
  provenance in `PhaseResult.cli_provenance` (or, more directly,
  `python -m megaplan <phase>` would receive a single `--rehydrate
  <path-to-rehydration.json>` arg instead of re-reading
  `state["config"]`).
- **Bug 2** would not exist because the executor would emit
  `exit_kind="blocked_by_prereq"` with `blocked_tasks=[…]`. The auto
  driver would never have to string-match
  `"tasks have no executor update"`, and the schema enum / coverage
  filter would not need to be kept in sync — both would derive from
  the same dataclass.
- **Bug 3** would not exist because `invocation_id` differs between
  sessions; the within-session short-circuit fires only when the
  blocked status was emitted by *this* invocation_id.
- **Bug 4** would not exist because the structured result is written to
  a known path atomically; mid-print truncation of stdout is irrelevant
  to the driver.

## 5. The smallest credible refactor

Don’t introduce the full `PhaseResult` yet. The smallest move that
materially reduces bug frequency is:

1. **Add `phase_result.json`** written atomically by every phase
   handler at exit (success, blocked, or CliError). One file. Fixed
   filename. Last-writer-wins. Schema validated by the existing
   `validate_payload` machinery.
2. **Auto driver consumes `phase_result.json` only.** Stop reading
   `state.json["history"][-1]`, stop globbing `execution_batch_*.json`
   for retry classification, stop prefix-matching deviations.
3. **Encode the four things that mattered in those bugs**: `exit_kind`
   (enum), `blocked_tasks` (list), `invocation_id` (ULID stamped at
   `set_active_step` time), `cli_args_used` (snapshot of resolved args
   post-profile-expansion).

Cost:
- Two-week task; touches every phase handler (eight of them). Mostly
  mechanical: each `return response` becomes
  `return _emit_phase_result(response, kind=...)`.
- `chain.py`’s `phase_callback(_phase, _code, _out, _err)` becomes
  `phase_callback(phase, result: PhaseResult)`. Trivial.
- Some existing tests will need to update.

What it doesn’t fix:
- Stdout is still a mixed channel; `workers.py` print statements still
  go there. The driver just stops *caring*, which is the actual goal.
- The state-machine itself (the seven phases, the gates, the retries)
  is unchanged; this is purely about *how the driver learns the
  outcome of a phase*.
- Subprocess rehydration is still implicit — Bug 1 is mitigated by
  including `cli_args_used` in `phase_result.json`, but the *next*
  subprocess still rehydrates its own args from state.json. Fully
  fixing that needs a separate refactor (rehydration cursor file).
  I’d defer it: Bug 1 was a one-time profile-precedence error and the
  fix already in place is defensible.

## 6. Things I considered and rejected

**Alternative thesis: “The state machine has too many phases / the
retry policy is too clever; simplify it.”** I considered this because
three of the four bugs are about retry classification. But the retry
logic itself is appropriately discriminating — within-session vs
cross-session, quality-gate vs prereq-block, context exhaustion vs
ordinary failure are all real distinctions that the system needs to
make and that the user clearly wants. The bug pattern isn’t “the
distinctions are wrong,” it’s “the driver has to reconstruct the
distinctions from impoverished signals.” Simplifying the policy would
either drop signal the user cares about or just move the impedance
mismatch somewhere else.

**Alternative thesis: “Execute is too big — split it into smaller
phases.”** Execute is large (`execute/core.py` is 1503 lines,
`handle_execute_auto_loop` alone is ~70 lines of branching), but
none of the four bugs were about size. They were about the *handoff*.
Splitting execute would multiply the number of boundaries that suffer
the same problem.

**Alternative thesis: “The chain layer is over-coupled to auto.”** The
`on_phase_complete` callback (`auto.py:1336`) does invite this — chain
gets `(phase, code, out, err)` and runs git commands synchronously
inside the auto loop. But the bugs in this session were all
auto↔execute, not chain↔auto, so I’m not claiming this. It’s a
related smell.

## 7. Confidence

**High** that the structural diagnosis (Section 2) is correct: every
bug in the cluster maps cleanly to an inferred-rather-than-declared
signal at the same boundary. The pattern is too tight to be
coincidence in one session.

**Medium-high** on the specific “missing abstraction” framing in
Section 4. A reasonable alternative is “there’s no missing abstraction,
the abstraction is `state.json` + history and it just needs better
discipline — write structured records into the existing channel.” That
would also work; the practical difference is whether the existing
`state["history"][-1]` becomes the load-bearing object or whether a
new `phase_result.json` does. I prefer the new file because
`state.json`’s history is append-only and shared across phases, which
makes “the latest result of the *current* phase” harder to read than
it should be.

**Medium** on the specific reading of Bug 4 as a status-subprocess
truncation rather than an execute-subprocess truncation. Without
seeing the actual session log I’m inferring from
`grep phase_progress_summary` returning only `cli.py` status-payload
sites. If Bug 4 turns out to be the execute subprocess truncating
something else entirely (e.g., a `print(...)` from `workers.py`
followed by an OS-level kill), the structural thesis is unchanged
— the “stdout is an unframed mixed channel” evidence stands either
way. What would change my mind on the thesis would be evidence that
the four bugs span genuinely independent design surfaces, e.g., one
of them was an auth bug or a database race that I’m misreading as a
boundary issue. I went looking for that and didn’t find it.
