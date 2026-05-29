# C4 Validation — Config Bus & proposed `HandlerContext`

Brief: 2026-05-23 (component A3 + hazard 7 + audit F6). Code refactored May 24–28;
brief line-cites are stale. All cites below are CURRENT (`grep`/`Read` 2026-05-28).

## 0. Premise check: HandlerContext does not exist

`grep -rn "HandlerContext" --include="*.py" .` → **zero matches**. HandlerContext is
purely a proposal. This validation assesses (a) the PROBLEM (the `args` config bus) and
(b) the proposed solution's ROI/leakage.

## 1. The config bus — `handle_*(root, args)`

Every funneled handler is dispatched `handle_X(root: Path, args: argparse.Namespace)`:

- `megaplan/handlers/execute.py:96` `handle_execute(root, args)`
- `megaplan/handlers/finalize.py:616` `handle_finalize(root, args)`
- `megaplan/handlers/critique.py:56` `handle_critique`, `:515` `handle_revise`
- `megaplan/handlers/gate.py:448` `handle_gate(root, args)`
- `megaplan/handlers/plan.py:45` `handle_plan`, `:106` `handle_prep`
- `megaplan/handlers/init.py:262` `handle_init`
- `megaplan/handlers/override.py:913` `handle_override`
- `megaplan/handlers/review.py:480` `handle_review`
- `megaplan/handlers/tiebreaker.py:34,73` tiebreaker run/decide
- `megaplan/handlers/verifiability.py:137,297` verify_human / audit_verifiability
- `megaplan/handlers/tickets.py` — **12 ticket handlers take `(args)` only, no root**
  (`handle_ticket_new/list/show/edit/link/unlink/addressed/dismiss/reopen/search`, lines 28–149).

`args` is an `argparse.Namespace` used as an untyped property bag.

### How many fields / read sites

- Direct `args.<field>` in `handlers/*.py`: **35 distinct fields, 97 occurrences**.
  Most direct reads are in `tickets.py` (42 sites) and `override.py` (16) and `init.py` (12).
- Defensive `getattr(args, "field", ...)` is the dominant access pattern (the namespace
  is sparsely populated per-command, so handlers can't assume attributes exist):
  - Repo-wide: **218 distinct `getattr(args, ...)` field names**.
  - In `handlers/*.py` alone: **55 distinct getattr fields**.
  - Combined distinct (`args.` + `getattr`) read in handlers: **81 distinct fields**.
- The brief's "~25-field bus / ~17 stable" is an UNDERCOUNT for the repo as a whole, but
  plausible as the *per-command core threading subset*. The true surface is far larger and
  command-specific.

### Threading path (confirmed)

`args` is threaded by value all the way down, never decomposed:

1. handler → `_run_worker(step, state, plan_dir, args, *, root, ...)`
   (`megaplan/handlers/shared.py:204`).
2. `_run_worker` calls `apply_profile_expansion(args, ...)` (`:219`), then
   `resolve_agent_mode(step, args)` (`:220`), then forwards `args` wholesale into
   `worker_module.run_step_with_worker(step, state, plan_dir, args, **kwargs)` (`:239`).
3. `_finish_step(plan_dir, state, args, ...)` (`shared.py:380`) forwards `args` into
   `_emit_receipt` (`:347`) → `build_receipt(..., args=args, ...)`
   (`megaplan/receipts/__init__.py:31`). `build_receipt` only reads `getattr(args,"profile")`
   (`:39`) — i.e. it accepts the whole bus to read one field.
4. `resolve_agent_mode` (`megaplan/workers/_impl.py:2313`) reads ~7 fields off args
   (`agent`, `hermes`, `_live_phase_model_steps`, `phase_model`, plus calls
   `_agent_requested_explicitly(step, args)`).

So `args` flows handler → shared `_run_worker`/`_finish_step` → workers / receipts /
profile expansion / agent resolution. The brief's claim that it threads through
`_finish_step → build_receipt → _run_worker → resolve_agent_mode` and ~20 helpers is
**substantially accurate** — every link verified; "~20 helpers" is order-of-magnitude
right given the sparse `getattr` reads scattered across workers/receipts/profiles.

## 2. Handler impurity (the hard part) — CONFIRMED

### handle_gate (`gate.py:448`)
Within one `load_plan_locked` ctx the handler:
- mutates state via `apply_profile_expansion(args, ...)` (`:451`),
- spawns a worker `_run_worker("gate", ...)` (`:455`),
- runs a **tiebreaker cascade**: `_validate_tiebreaker(... worker, args, agent, resolved ...)`
  when `result == "tiebreaker_recommended"` (`:489-493`) — itself spawns workers,
- runs a **reprompt loop**: if `blocking_unresolved_ids`, builds a reprompt override
  (`_build_gate_prompt_override`, `:495`) and spawns a SECOND `_run_worker("gate", ...,
  prompt_override=reprompt_prompt)` (`:502-510`), merges worker results
  (`_merge_gate_worker_attempt`, `:511`), re-applies outcome (`:529`),
- **auto-downgrade cascade**: if flags still unresolved after reprompt, forcibly rewrites
  `gate_summary["recommendation"]="ITERATE"`, `passed=False`, sets `result="blocked"`,
  `next_step="revise"` (`:535-549`).

This is control flow + multiple worker spawns + verdict mutation embedded in the handler.
(Cross-ref memory `project_gate_tiebreaker_downgrade.md` — the silent
TIEBREAKER→ITERATE downgrade lives here.)

### handle_execute (`execute.py:96`)
- Embeds the **approval gate**: reads `auto_approve = state["config"].get("auto_approve")`
  and `state["meta"].get("user_approved_gate")`, raises CliError if neither (`:108-115`).
  (Cross-ref memory `feedback_auto_gate_bypass.md`.)
- Forces fresh session on rework/blocked-retry (`_is_rework_reexecution` / `_is_blocked_retry`,
  `:133-135`).
- Delegates the **auto-loop** to `handle_execute_auto_loop(...)`
  (`execute.py:178`, defined `megaplan/execute/batch.py:859`). That loop iterates batches
  (`batch.py:1069 for batch_index, batch_task_ids in enumerate(batches_to_run...)`), each
  calling `handle_execute_one_batch` (`:432`) which spawns
  `worker_module.run_step_with_worker(...)` (`:310`, `:543`).
- `_resolve_execute_tier_spec` builds a throwaway namespace and **mutates** it:
  `tier_args.phase_model = [f"execute={tier_spec}"]` (`execute.py:57`).

So execute is a multi-batch driver with embedded approval policy + session policy + worker
fan-out. Confirmed impure.

## 3. Ambient inputs not in `args` (audit F6) — CONFIRMED

### `args` is mutated in place
`apply_profile_expansion(args, project_dir, state)` (`megaplan/profiles/__init__.py:1506`):
- guards on sentinel `args._profile_applied` (`:1517`),
- WRITES sentinel `args._live_phase_model_steps = set(cli_steps)` (`:1527`),
- WRITES `args.profile = profile_name` when inferred from vendor (`:1540`),
- splices profile defaults into `args.phase_model` downstream.
Called from inside `_run_worker` (`shared.py:219`) AND each handler top
(`gate.py:451`, etc.). So the namespace is a mutable, statefully-expanded object, not an
immutable config — the `_profile_applied` flag exists precisely to make the in-place
mutation idempotent across the multiple call sites.
Also `args._agent_fallback = {...}` written in `workers/_impl.py:2432,2640`, later read by
`attach_agent_fallback` (`shared.py:128-130` via `hasattr(args,"_agent_fallback")`).

### MEGAPLAN_* env read directly inside handlers — YES
- `finalize.py:31` `os.getenv("MEGAPLAN_FINALIZE_STRICT_VALIDATION")`; `:496` `MOCK_ENV_VAR`.
- `review.py:527` `os.getenv(MOCK_ENV_VAR)`.
- `plan.py:117` `os.getenv(MOCK_ENV_VAR)`.
- `resolve_agent_mode` reads `os.environ.get("MEGAPLAN_MOCK_WORKERS")` (`workers/_impl.py`).
- Repo-wide ~20 distinct `MEGAPLAN_*` vars read in handlers/workers/core (mock, actor,
  turn id, shannon timeouts/sandbox, finalize strict, narrow-sandbox, trusted-container…).

### resolve_agent_mode reads ~/.megaplan/config.json — YES
`resolve_agent_mode` (`workers/_impl.py:2313`) on the no-explicit-flag path calls
`config = load_config(home)` and reads `config.get("agents",{}).get(step)`
(falling back to `DEFAULT_AGENT_ROUTING`). `load_config` reads
`config_dir(home)/"config.json"` (`megaplan/_core/io.py:743`). Also `get_effective` and
`handle_execute_auto_loop` (`batch.py:875 global_config = load_config()`) read it.
So routing + quality-check config is ambient global state, not in `args`.

## 4. Public API — `handle_*` in `__all__`

`megaplan/handlers/__init__.py:75` `__all__` exports: handle_init, handle_plan, handle_prep,
handle_critique, handle_revise, handle_gate, handle_finalize, handle_execute, handle_review,
handle_override, handle_audit_verifiability, handle_verify_human, handle_tiebreaker_run,
handle_tiebreaker_decide (lines 76–89).
`megaplan/__init__.py:59-62` re-exports handle_init/plan/critique/revise/gate/finalize/
execute/review/step/status/audit/progress/list/override/setup/setup_global/config.
**Consequence:** changing any `handle_*(root, args)` signature to `(root, state, hctx)` is a
**public-API break** — these are top-level package exports, not internal symbols.

## 5. ASSESSMENT — is HandlerContext the right ROI move?

**The problem is real and well-diagnosed.** `args` is a 80+-field untyped, sparsely-populated,
in-place-MUTATED namespace, threaded by value through workers/receipts/profiles, and it is
NOT even the full config surface — env vars and `~/.megaplan/config.json` are read ambiently
inside handlers and `resolve_agent_mode`. A typed boundary would document the real contract
and kill the `getattr(args, "x", default)` defensive-coding sprawl (55 distinct in handlers).

**But the proposed framing — "separate ~17 stable fields from runtime services, handlers
become pure-ish `(root, state, hctx)`" — undersells the cost and overstates the payoff.**
The hard part isn't the dataclass; it's that:

1. **Handlers are not pure and a context object doesn't make them pure.** gate embeds a
   reprompt loop + tiebreaker cascade + auto-downgrade + 2–3 worker spawns; execute is a
   multi-batch driver with embedded approval/session policy. Wrapping config in `hctx`
   leaves all the control flow, I/O (state save/merge, receipt write, event emit), and
   worker fan-out exactly where they are. "Pure-ish" is aspirational — the handlers will
   stay effectful; you'd get a *typed-config* handler, not a pure one.

2. **The mutation is load-bearing, not incidental.** `apply_profile_expansion` writes
   `args.profile`, `args._live_phase_model_steps`, `args.phase_model` and uses
   `_profile_applied` to stay idempotent across ~N call sites. If `hctx` is frozen, profile
   expansion has to be re-architected to return a new context (and every downstream reader —
   `resolve_agent_mode`, `build_receipt`, workers — updated to take it). That is the actual
   work, and it's a refactor of the routing pipeline, not a signature swap.

3. **Services don't cleanly separate from config either.** `resolve_agent_mode` blends
   args + `config.json` + env (`MEGAPLAN_MOCK_WORKERS`) + PATH availability checks. A
   `worker_runner`/`event sink` service split is plausible, but the config half still leaks
   into ambient `load_config()`/`get_effective()`/`os.getenv` calls scattered through
   finalize/review/plan/batch — `hctx` would have to *own* those to deliver the promised
   "all config in one typed place," which is a much wider change than 17 fields.

### Where it will leak
- **Ambient config/env.** Unless `hctx` absorbs `load_config()`/`get_effective()`/
  `os.getenv("MEGAPLAN_*")`, those reads stay ambient and the "typed config bus" is a
  half-measure; the env/config-json surface (~20 vars + agents/quality_checks json) is the
  bigger un-typed bus.
- **Profile expansion mutation.** A frozen hctx collides with in-place
  `apply_profile_expansion`; either hctx stays mutable (and you've renamed the problem) or
  you rewrite the routing pipeline (the real, larger task).
- **Public API.** All `handle_*` are in two `__all__`s; a `(root, state, hctx)` signature is
  a breaking change to package consumers (tests, cloud entrypoint, auto-driver subprocess
  dispatch in `cli/__init__.py`).
- **tickets handlers** take `(args)` only and read 42 sites of CLI-shaped fields — they don't
  fit the `(root, state, hctx)` shape at all and would need a separate carve-out.

### Verdict
HandlerContext addresses a **real** problem but, as scoped (dataclass swap separating ~17
fields), it is a **deep rewrite masquerading as a dataclass swap**. The high-ROI subset is:
(a) a typed `RunConfig`/frozen dataclass to replace the *getattr-defensive read surface*
threaded into workers/receipts (mechanical, valuable, low risk), and (b) hoisting ambient
`load_config`/env reads into that object. The low-ROI / high-risk part is pretending it makes
handlers pure or that it's free given profile-expansion mutation + public-API breakage. Do
(a)+(b); don't sell "pure handlers."

### Unknown-unknown
The auto-driver spawns each phase as a **fresh subprocess** that does NOT re-pass the
original CLI flags (per the `apply_profile_expansion` docstring + memory
`project_megaplan_auto_project_dir_ignored.md`): config is reconstituted from
`state["config"]` + profile expansion on EACH subprocess. A `HandlerContext` built once
in-process has no obvious home in this multi-process model — it must be (de)serializable
from state on every subprocess boundary, or the context becomes a per-process rebuild from
state anyway. This subprocess-reconstitution requirement is the hidden constraint that most
threatens the "build hctx once, thread it" design and is not mentioned in the brief.
