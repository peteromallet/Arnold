# CLI command migration + umbrella-vs-module namespace split (Arnold SDK)

**Status:** Design decision (2026-05-29). Resolves the open "what moves from an overall command to a
megaplan subcommand and vice versa" question in `.megaplan/briefs/pipeline-unification-EPIC.md`.

## Framing & the deferred-rename rule
The repo is renaming **Megaplan → Arnold (umbrella)**. The *trigger* to actually introduce the `arnold`
namespace/CLI/package is **a second non-Megaplan capability landing on the SDK** (resident is plausibly it,
M6). **Until that trigger fires, the command binary, the package, and on-disk state all stay `megaplan`.**
So this doc decides the *target* topology and the *aliasing* that lets us ship the topology now without the
rename: every umbrella command is reachable today as `megaplan <x>`, and when the rename lands `arnold <x>`
becomes canonical with `megaplan <x>` kept as a back-compat alias for the deferred-rename period.

Two homes:
- **UMBRELLA (`arnold <x>`)** — operates on the SDK/runtime, or on ANY module/run regardless of domain.
- **MODULE (planning's own; `arnold planning <phase>` post-split, `megaplan <phase>` today)** — specific to
  the planning domain (its 4-verdict gate, its phase graph, its prompts/rubrics).

Invocation shape decision (below): **`arnold <umbrella-verb>`** for SDK/runtime/any-run verbs, and a
**per-module command namespace `arnold <module> <verb>`** for domain commands (planning is just the first
module). The phases run as a graph driver under one entry — see "Invocation shape".

---

## Authoritative current surface

Enumerated from code: `COMMAND_HANDLERS` (`megaplan/cli/__init__.py:1014-1051`, 36 entries), the
special-cased runners intercepted *before* generic dispatch (`cli/__init__.py:1421-1558`:
`cloud`, `resident`, `bakeoff` parsed off `argv[0]`; `auto`, `run`, `describe`, `chain`, `tiebreaker`
dispatched after root-resolve), and the subparser set in `cli/parser.py` (incl. the `run` parser from
`_pipeline/run_cli.py:36`, the 3 `status/progress/watch` step parsers at `parser.py:534`, and the
`override` 8-action positional at `parser.py:779-792`).

### Full command-by-command map

| Command | Source | Home | Invocation (target) | Justification |
|---|---|---|---|---|
| `run` | run_cli.py:38 | **UMBRELLA** | `arnold run <pipeline> …` | Runs ANY registered pipeline by name; already domain-agnostic — the canonical umbrella entry. |
| `list` (`list pipelines`) | parser:304 | **UMBRELLA** | `arnold pipelines list` | Lists pipelines across modules; the `pipelines` arg already exists (parser:331). |
| `pipelines check` | EPIC M1 (new) | **UMBRELLA** | `arnold pipelines check` | Static graph linter over ANY composition. |
| `pipelines doctor` | EPIC M1 (new) | **UMBRELLA** | `arnold pipelines doctor` | Per-path discovered/rejected diagnostics, any module. |
| `pipelines new` | EPIC M6 (new) | **UMBRELLA** | `arnold pipelines new` | Scaffolds ANY new package. |
| `describe` | cli:1537 | **UMBRELLA** | `arnold pipelines describe` / `arnold describe` | Describes any pipeline's contract. Fold under `pipelines`. |
| `status` | __init__:1024 | **UMBRELLA (after M5c)** | `arnold status [--plan]` | Per-run inspection of any run — BUT payload is planning-SHAPED today (leaks `current_state`/`awaiting_human_verify`, `status_view.py:892`). Cannot move until M5c run-outcome vocab de-planning-izes the payload. See Fuzzy/§Theme-D. |
| `progress` | __init__:1026 | **UMBRELLA (after M5c)** | `arnold progress` | Same STATE_* leak class as status. |
| `watch` | __init__:1027 | **UMBRELLA (after M5c)** | `arnold watch` | Same. |
| `introspect` | __init__:1045 | **UMBRELLA (after M4)** | `arnold introspect` | Re-homed onto the composition-observability event contract (EPIC M4). Backend-agnostic once re-homed. |
| `trace` | __init__:1047 | **UMBRELLA (after M4)** | `arnold trace` | Same — observability contract. |
| `doctor` (per-run) | __init__:1048 | **UMBRELLA (after M4)** | `arnold doctor` | Same. (Distinct from `pipelines doctor` = discovery diagnostics.) |
| `cost` | __init__:1046 | **UMBRELLA (after M4/M5c)** | `arnold cost` | Cost folds onto the ONE budget authority (M4) + observability contract; payload also planning-shaped today (Theme-D), needs M5c vocab. |
| `record-tag` | __init__:1049 | **UMBRELLA** | `arnold record-tag` | Tags a run's event stream — runtime/observability, domain-neutral. |
| `config` | parser:717 | **UMBRELLA** | `arnold config {show,set,reset,profiles,use-profile}` | SDK-wide config + N-layer precedence resolver (M4). Profiles can be module-scoped via `@<pipeline>:<profile>`. |
| `setup` / `setup-global` / `setup-hooks` | setup.py | **UMBRELLA** | `arnold setup …` | Installs the SDK/runtime itself. |
| `cloud` | __init__:1423 | **UMBRELLA** | `arnold cloud …` | Hosts ANY run/chain in a container (own subparser tree). |
| `chain` | __init__:1544 | **UMBRELLA (supervisor tier, M5d)** | `arnold chain …` | General cross-run orchestration; M5d makes it invoke general control ops, not planning by name. |
| `epic` | __init__:1038 | **UMBRELLA (supervisor tier)** | `arnold epic {snapshot,migrate,export}` | Inspect/migrate Arnold epics — already named "Arnold epics" (parser:350). |
| `ticket` | __init__:1037 | **UMBRELLA** | `arnold ticket …` | Repo-scoped notes folded into epics; not planning-specific. |
| `debt` | __init__:1035 | **UMBRELLA** | `arnold debt {list,add,resolve}` | Technical-debt registry is run/repo-scoped, any module can write it. |
| `feedback` | __init__:1029 | **UMBRELLA** | `arnold feedback` | Collects feedback rows across runs. |
| `audit` (query/report) | __init__:1025 | **UMBRELLA** | `arnold audit {query,report}` | Reads the evidence/receipts stream — general evidence piece. (`audit-verifiability` below is the planning one.) |
| `migrate-local-plans` | __init__:1039 | **UMBRELLA** | `arnold migrate-local-plans` | State-store migration utility (runtime maintenance). |
| `resident` | __init__:1435 | **MODULE (resident's)** | `arnold resident …` | The 2nd app; its own module namespace (own subparser tree already). |
| `bakeoff` | __init__:1450 | **UMBRELLA (supervisor tier)** | `arnold bakeoff …` | Multi-profile head-to-head over any pipeline; supervisor-tier orchestration. |
| **— planning module —** | | | | |
| `init` | __init__:1015 | **MODULE** | `arnold planning init` (alias `megaplan init`) | Initializes a planning run (its worktree, brief, robustness). Planning-domain bootstrap. |
| `plan` | __init__:1016 | **MODULE** | phase of `arnold planning` graph | Planning phase. |
| `prep` | __init__:1017 | **MODULE** | phase | Planning phase. |
| `critique` | __init__:1018 | **MODULE** | phase | Planning phase (evaluator-only). |
| `revise` | __init__:1019 | **MODULE** | phase | Planning phase. |
| `gate` | __init__:1020 | **MODULE** | phase | Owns the 4-verdict vocab — definitionally planning. |
| `finalize` | __init__:1021 | **MODULE** | phase | Planning phase (incl. tier hardening). |
| `execute` | __init__:1022 | **MODULE** | phase | Planning's task-DAG realm (M5b). |
| `review` | __init__:1023 | **MODULE** | phase | Planning phase. |
| `tiebreaker` / `tiebreaker-run` | __init__:1044,1552 | **MODULE** | `arnold planning tiebreaker` | Tiebreaks planning gate verdicts — planning-domain. |
| `verify-human` | __init__:1042 | **MODULE** | `arnold planning verify-human` | Human-gate over planning verification (planning's `awaiting_human_verify`). The general human-gate hook is SDK; *this* binds planning to it. |
| `quality-gate` | __init__:1050 | **MODULE** | `arnold planning quality-gate` | Resolves planning quality blockers. |
| `user-action` | __init__:1036 | **MODULE** | `arnold planning user-action` | Resolves planning user-action prerequisites. |
| `audit-verifiability` | __init__:1043 | **MODULE** | `arnold planning audit-verifiability` | Audits planning's verifiability claims (vs general `audit`). |
| `step` (add/remove/move) | __init__:1040 | **MODULE** | `arnold planning step` | Edits the planning task list. |
| `loop-init/run/status/pause` | __init__:1031-1034 | **MODULE (loop driver binding)** | `arnold planning loop-*` | The loop *driver* is SDK (M3 loop-control node); these 4 are planning's binding to it. Could later generalize, but ship as module. |
| **— FUZZY (edge calls) —** | | | | see below |
| `auto` | __init__:1521 | **SPLIT → UMBRELLA core + MODULE default** | `arnold auto [<module>]` | Fuzzy #1. |
| `override` (8 actions) | __init__:1041 / parser:779 | **SPLIT** | `arnold override …` (general) / `arnold planning override …` (planning) | Fuzzy #2. |
| `resume` | parser:613 | **MODULE (driver-resumable later)** | `arnold planning resume` | Fuzzy #3. |

Count: **23 UMBRELLA** (incl. 3 new M1/M6 `pipelines` verbs and `describe`), **1 MODULE for resident**,
**~18 planning MODULE** commands/phases, **3 FUZZY** (`auto`, `override`, `resume`).

---

## The FUZZY decisions (the real edges)

### 1. `auto` — SPLIT: umbrella driver-loop + module-default target
`auto` is two things fused: (a) a generic "drive a graph to completion, applying the RecoveryPolicy / budget
/ retry brain" loop (`auto.py` is literally the home of the un-extracted `RecoveryPolicy`, EPIC §M4/§3), and
(b) a default assumption that the graph is *planning's*. The generic loop is **UMBRELLA** — it is the
runtime's drive-a-composition verb and belongs next to `run`. The planning-default is a **module binding**.
**Decision:** `arnold auto [<module>] [args]`, defaulting `<module>=planning` during the deferred-rename
period so `megaplan auto` keeps meaning "drive the planning graph." The loop itself drives any driver's
graph via the M4 policy spine; it must NOT reference `STATE_*` (it queries `valid_targets(state)` from the
control interface, M5c). **Cannot fully de-planning-ize until M5c** (the loop's halt/continue decisions read
run-outcome vocab). Ships as umbrella-with-planning-default at M5c, fully generic at M6.

> Memory note honored: `megaplan auto` historically *bypasses* the auto_approve gate and does not halt
> before execute. The umbrella `auto` must route halt/proceed through the M5c control interface
> (`apply_transition`), not through `state.config.auto_approve` flips — fixing that coupling is part of
> the de-planning-ization, not a regression to preserve.

### 2. `override` — SPLIT by action along the general/planning seam
The 8 actions split cleanly: actions that manipulate the *run/control plane* are **UMBRELLA**; actions that
encode *planning semantics* are **MODULE**.
- **UMBRELLA** (`arnold override …`, general control ops via M5c `apply_transition`): `abort`,
  `add-note` (with `--source user|driver`), `set-robustness`, `set-profile`, `set-model`. These act on any
  run's control plane / config; `set-robustness` rides the topology-realizer's live re-invocation (M3).
- **MODULE / planning** (`arnold planning override …`): `force-proceed`, `replan`, `recover-blocked`. These
  are planning-control-vocabulary: `force-proceed` past a planning gate ESCALATE, `replan` re-enters the
  planning graph, `recover-blocked` (requires `--reason`) recovers a planning `STATE_BLOCKED`. Per the EPIC,
  "planning keeps only content" is **false** for the control plane — these *implement* the general control
  interface with planning-specific transition names. **Decision:** the general `override` verb takes a
  module-routing arg; `force-proceed`/`replan`/`recover-blocked` are planning's registered transitions, not
  umbrella verbs. The supervisor (M5d) must invoke "the run's force-proceed transition," never `force-proceed`
  by literal name. **Blocked on M5c** (the control interface) for the split to be real rather than cosmetic.

### 3. `resume` — MODULE now, driver-resumable later
`resume` today resolves to planning's `resume_plan` (`_core.resume_plan`, plus the missing-surface
`workflow.py::resume_plan` and `loop/engine.py` per EPIC guardrails) and carries a planning `--resume-choice`
for `human_gate`. Resuming is conceptually a *driver* capability (a graph/loop driver knows how to re-enter
its own state). **Decision:** keep `resume` as a **planning MODULE** command (`arnold planning resume`) for
the epic; do NOT promote to umbrella, because a generic "resume any run" requires every driver to implement a
uniform resume contract, which is out of scope (EPIC defers the symmetric Realizer Protocol). The umbrella's
generic re-entry need is already served by `auto` re-invocation + the M5c `apply_transition` trio.

### Theme-D: the STATE_* leak at the command edge (status/progress/watch/cost)
`handle_status` returns `state["current_state"]` raw and special-cases `awaiting_human_verify`
(`status_view.py:888-901`); `cost`/`progress`/`watch` are likewise planning-shaped. These are *umbrella*
commands by domain (inspect any run) but their **payloads speak planning's state machine**. Per EPIC §M5c /
problem-4, the fix is the run-outcome vocabulary `{succeeded, failed, escalated, blocked, awaiting_human}` +
`valid_targets`/`recover_targets`, with planning's `STATE_*` *binding onto* it. **Therefore the per-run
umbrella commands cannot move up until M5c lands the vocabulary** — moving them earlier would freeze the
planning leak into the umbrella's public contract. Observability re-homing (introspect/trace/doctor/cost) is
M4; payload de-planning-ization is M5c. Net: these commands ship as umbrella *after* both M4 (re-home onto
the observability contract) and M5c (de-planning-ize the run-outcome words).

---

## Invocation shape (decision)

- **Umbrella verbs:** `arnold <verb>` — `arnold run`, `arnold status`, `arnold cost`, `arnold config`,
  `arnold cloud`, `arnold chain`, `arnold pipelines {list,check,doctor,new,describe}`, `arnold auto`,
  `arnold override`.
- **Module namespace:** `arnold <module> <verb>` — `arnold planning <phase>`, `arnold resident <verb>`.
  Planning's phases (`plan/prep/critique/revise/gate/finalize/execute/review`) run as nodes of the planning
  graph driver; the explicit per-phase command form (`arnold planning gate …`) is kept for manual stepping
  and is *not* a privileged execution path (M6 drops `_BUILTIN_NAMES`). Equivalent: `arnold run planning`
  drives the whole graph; `arnold planning <phase>` runs one node — both are just the graph driver invoked at
  different granularity.
- **Rejected:** a flat `arnold <phase>` top-level namespace (re-privileges planning, the exact thing M6
  removes) and `arnold module:verb` colon syntax (reserve `@pipeline:profile` colon for profiles only).

### Back-compat for the deferred-rename period
1. **Binary alias:** ship `arnold` as a console-script alias of the same entrypoint; `megaplan` stays the
   documented binary until the rename trigger fires.
2. **Bare planning commands:** every current top-level command keeps working as today — `megaplan gate`,
   `megaplan status`, `megaplan auto` — by registering bare aliases that resolve to `planning <verb>` /
   the umbrella verb. (Honors EPIC guardrail: "keep planning phase names valid in profiles," name aliases,
   `handle_* __all__` shims.)
3. **State/package:** stay `megaplan` (package dir, `.megaplan/` state, the 26 `MEGAPLAN_*` env vars) until
   the second non-Megaplan app lands (M6 / resident).
4. **`arnold epic` / `--from-arnold-epic`:** already named "Arnold" in code (parser:350, __init__:1638) —
   these are the seed of the umbrella naming and stay.

---

## Migration — what moves, what stays, what splits, dependency order

**Stay put (already umbrella-shaped, no payload coupling):** `run`, `list/pipelines`, `config`, `cloud`,
`epic`, `ticket`, `debt`, `feedback`, `audit`, `setup*`, `migrate-local-plans`, `record-tag`. These get the
`arnold`-alias treatment whenever the rename lands; no semantic migration needed.

**Move UP (megaplan → arnold) once their dependency clears:**
- `introspect`, `trace`, `doctor`, `cost` — after **M4** (re-home onto the composition-observability event
  contract + ONE budget authority).
- `status`, `progress`, `watch`, `cost` (payload) — after **M5c** (run-outcome vocabulary evicts `STATE_*`
  from the payload). *This is the hard dependency the brief flags: per-run umbrella commands can't move
  until M5c de-planning-izes their payloads.*
- `chain`, `bakeoff`, `epic` (orchestration) — into the **supervisor tier at M5d** (depends on M6 + the
  process driver); supervisor must invoke general control ops, not planning transitions by name.

**SPLIT:**
- `auto` → umbrella driver-loop + planning-default module target. Core extracted at **M4** (RecoveryPolicy),
  de-planning-ized at **M5c**, fully generic at **M6**.
- `override` → umbrella control actions (`abort/add-note/set-robustness/set-profile/set-model`) + planning
  transitions (`force-proceed/replan/recover-blocked`). Real split needs the **M5c** control interface.

**Stay MODULE (planning's own):** `init`, the 8 phases, `tiebreaker(-run)`, `verify-human`, `quality-gate`,
`user-action`, `audit-verifiability`, `step`, `loop-*`, `resume`. Relocated under the `planning` package at
**M6** (drop `_BUILTIN_NAMES`; manifest + driver + bindings + SKILL.md). `resident` becomes its own module at
**M6** (adopts the pieces).

### Dependency order (critical path)
```
M1  pipelines check/doctor land as umbrella verbs (new surface)
M3  set-robustness rides the topology-realizer (live re-invoke)        ── unblocks override set-robustness semantics
M4  observability contract + budget authority + RecoveryPolicy + config-precedence
        └─ introspect/trace/doctor/cost re-home up; auto-loop core extracted
M5c control plane: run-outcome vocab {succeeded,failed,escalated,blocked,awaiting_human}
        └─ status/progress/watch/cost PAYLOAD de-planning-ized → can move up
        └─ override SPLIT becomes real (general apply_transition vs planning transitions)
        └─ auto halt/proceed routes through apply_transition (fixes the auto_approve-bypass coupling)
M5d supervisor tier: chain/bakeoff/epic invoke GENERAL control ops (not "force-proceed" by name)
M6  arnold namespace introduced (rename trigger = 2nd app): planning relocated to a module,
        _BUILTIN_NAMES dropped, bare `megaplan <x>` aliases retained, resident adopts pieces;
        auto fully generic; all umbrella verbs canonical as `arnold <verb>`
```

### Which milestone OWNS this
**Primary owner: M6** — "Megaplan as a discovered module + `arnold` namespace + trust boundary" is where the
namespace split is physically realized (relocate planning, drop `_BUILTIN_NAMES`, introduce `arnold`, keep
`megaplan` aliases). **But M6 is not self-sufficient:** the per-run umbrella commands' payload de-planning-
ization is owned by **M5c**, their observability re-home by **M4**, and the supervisor-tier promotion of
chain/bakeoff/epic by **M5d**. So: **M6 owns the namespace + invocation + aliasing decision; M5c is the hard
prerequisite for moving the per-run inspection commands up (status/progress/watch/cost + the override
split); M4 is the prerequisite for the observability commands.** This doc is the design-of-record the M4/
M5c/M5d/M6 plan briefs cite for command placement.
