# m5 — Config Substrate: `HandlerContext`

**Epic:** pipeline-unification (`.megaplan/briefs/pipeline-unification-EPIC.md`, m5 section L120–130).
**Tier/robustness:** premium · thorough/high.
**Depends on:** m1 (dispatch toggle, parity gate as permanent CI) and **m3 (auto.py in-process)**.
Grounded 2026-05-28. Primary findings: `.megaplan/briefs/validation/c4-handlercontext.md`,
`.megaplan/briefs/validation/s4-external-coupling.md`.

---

## Outcome

A typed config substrate for the handler layer. The untyped `argparse.Namespace` config bus
(`handle_*(root, args)`) is replaced — *behind the m1 dispatch toggle* — by a typed
`HandlerContext` that (a) carries the config surface as named, documented fields and (b) injects
runtime **services** (`progress_emitter`, event sink, `worker_runner`) instead of having handlers
reach for ambient globals. The 26 ambient `MEGAPLAN_*` env reads, the `~/.megaplan/config.json`
load, and the in-place `apply_profile_expansion` mutation are hoisted onto that typed surface.

**Honest framing (c4 verdict, L155–200).** The epic line "handlers are pure-ish functions of
`(root, state, hctx)`" is *partly aspirational*. `handle_gate` (`gate.py:448`) embeds a tiebreaker
cascade + reprompt loop + auto-downgrade + 2–3 worker spawns; `handle_execute` (`execute.py:96`) is
a multi-batch driver with embedded approval/session policy. A context object does **not** make these
pure — it makes their *config dependency* typed and their *service dependency* injected. This
milestone delivers the **achievable** half: typed-config + service-injection + ambient-hoist, plus
only the purity that falls out for free (passing a service in instead of reaching for a global). The
control-flow/worker-fan-out refactor (the deep purity work) is explicitly **out of scope** and
deferred — m6 consumes this substrate but does not require pure handlers.

**Handoff:** typed config substrate; `args_to_hctx` adapter; handlers take `(root, state, hctx)`
on the new path; ambient env/config/profile-mutation reads centralized in the typed surface;
deprecation shims preserve the two public `__all__` handler exports.

---

## Scope (tied to current file:line)

### 1. The typed `HandlerContext` / config surface
- Define `HandlerContext` (a frozen-ish dataclass or two: a `RunConfig` value object + a `services`
  bundle). `HandlerContext` does **not exist today** — `grep -rn HandlerContext` → zero matches
  (c4 §0). This is greenfield in `megaplan/handlers/` (proposed `megaplan/handlers/context.py`).
- The config surface is **not "~25 fields"** — c4 §1 measured **81 distinct fields** read in
  `handlers/*.py` (35 via `args.<f>`, 55 via `getattr(args, "f", default)`, combined-distinct 81),
  with 218 distinct getattr field-names repo-wide. The brief's "~17 stable" is at best the
  per-command core threading subset. **Action:** type the *core threaded subset* (the fields that
  flow handler → worker → receipt → profile/agent resolution), and keep a typed escape hatch for
  command-specific fields rather than enumerating all 81. Inventory the threaded subset from the
  actual flow: `args` → `_run_worker` (`shared.py:204`) → `apply_profile_expansion`
  (`shared.py:219`) + `resolve_agent_mode` (`shared.py:220`) → `worker_module.run_step_with_worker`
  (`shared.py:239`); and `_finish_step` (`shared.py:380`) → `_emit_receipt` (`shared.py:347`) →
  `build_receipt(..., args=args, ...)` (`receipts/__init__.py:31`, reads only
  `getattr(args,"profile")`).

### 2. Service injection (the clean, high-ROI part)
- `progress_emitter` is **already a service set at the dispatch seam**, not a config field:
  `cli/__init__.py:1574` `args.progress_emitter = ProgressEmitter.from_env()`. m5 moves it from
  "stapled onto the namespace" into `hctx.services.progress_emitter` — a one-site change at the
  dispatch boundary plus the readers.
- `worker_runner`: today handlers call `_run_worker(...)` (`shared.py:204`) which calls
  `worker_module.run_step_with_worker(...)` (`shared.py:239`) directly. Inject the worker entry
  point as a service so handlers depend on an interface, not the module global. This is the seam
  m6's realizers and m3's in-process driver both want; do the *injection*, not a rewrite of the
  fan-out loops inside `execute/batch.py`.
- Event sink: emission already fires on production paths (EPIC L38, 3 sites). Thread the sink as a
  service rather than introducing a new emission concept.

### 3. Hoist ambient inputs onto the typed surface
- **`apply_profile_expansion` in-place mutation** (`profiles/__init__.py:1506`): mutates `args` —
  guards on `args._profile_applied` (`:1517`), writes `args._live_phase_model_steps` (`:1527`),
  writes `args.profile` from inferred vendor (`:1540`), splices into `args.phase_model`. Called from
  `_run_worker` (`shared.py:219`) **and** each handler top (e.g. `gate.py:451`). The `_profile_applied`
  sentinel exists *precisely* to make the in-place mutation idempotent across N call sites.
  Also `args._agent_fallback = {...}` is written in `workers/_impl.py:2432,2640` and later read via
  `hasattr(args,"_agent_fallback")` in `attach_agent_fallback` (`shared.py:128–130`).
  **Action:** model profile expansion as a function that *produces* the expanded config onto the
  typed surface (compute-once at context construction, store the expanded `phase_model` /
  `_live_phase_model_steps` / inferred `profile` as typed fields), retiring the sentinel-driven
  idempotency. Because m3 is in-process, expansion happens **once per run in one process** — there
  is no longer a per-subprocess rebuild forcing repeated mutation (see Constraints).
- **26 ambient `MEGAPLAN_*` env reads** (s4 claim 3): hoist the *handler-facing* ones onto the typed
  surface so handlers read `hctx`, not `os.getenv`. Confirmed handler-layer sites:
  `finalize.py:31` (`MEGAPLAN_FINALIZE_STRICT_VALIDATION`), `finalize.py:496` / `plan.py:117` /
  `review.py:527` (`MOCK_ENV_VAR`). The remaining ~22 (`workers/_impl.py:828` NARROW_SANDBOX,
  `:867` TRUSTED_CONTAINER, `:1853` CODEX_PRE_FIRST_BYTE_TIMEOUT_S, `:2390` MOCK_WORKERS, Shannon
  timeouts, cloud/resident vars) live in workers/core/cloud and are **out of scope** for the handler
  context (see Anti-scope) — m5 hoists the env reads that handlers themselves perform.
- **`~/.megaplan/config.json`**: `resolve_agent_mode` (`workers/_impl.py:2313`) on the
  no-explicit-flag path calls `load_config(home)` (`_core/io.py:743`, reads
  `config_dir(home)/config.json`) and reads `config.get("agents",{}).get(step)` (`:2382`).
  `handle_execute_auto_loop` also reads `load_config()` (per c4 §3). **Action:** load this config
  once at context construction and place the resolved routing/quality-check config on `hctx`, so
  `resolve_agent_mode` reads from the typed surface instead of an ambient disk read mid-handler.
  Keep `get_effective` (`_core/io.py:764`) behavior identical — this is a read-relocation, not a
  semantics change.

### 4. `args_to_hctx` adapter + dispatch toggle
- `COMMAND_HANDLERS` (`cli/__init__.py:1014`) maps command → handler; dispatch at
  `cli/__init__.py:1561,1566` calls `handler(root, args)`. m1 introduces `MEGAPLAN_UNIFIED_DISPATCH`
  / `dispatch_path` (does **not exist yet** — `grep` confirms zero matches today; it is an m1
  deliverable). m5 builds `args_to_hctx(args, state, services) -> HandlerContext` and routes:
  old path → `handler(root, args)`; new path → `handler(root, state, hctx)`. The toggle selects the
  signature during cutover; parity gate runs both.

### 5. Deprecation shims for public exports
- `handle_*` are exported in **two** `__all__`s: `megaplan/handlers/__init__.py:75–90` (14 symbols)
  and `megaplan/__init__.py:48–72` (17 symbols, partly overlapping — s4 claim 4, c4 §4). Changing
  the signature to `(root, state, hctx)` is a **public-API break** for package consumers (tests,
  cloud entrypoint). Provide shim wrappers that preserve the `(root, args)` signature and internally
  build the context, so external callers keep working through the deprecation window.

---

## Locked decisions

1. **Achievable subset only.** Deliver typed-config + service-injection + ambient-hoist. Do **not**
   attempt to make `handle_gate`/`handle_execute` pure; their loops/spawns stay. (c4 verdict.)
2. **Type the threaded core, escape-hatch the rest.** Do not enumerate all 81 fields; type the
   subset that threads to workers/receipts/profile/agent resolution; keep a typed pass-through for
   command-specific fields. (c4 §1.)
3. **Compute-once profile expansion.** Replace the `_profile_applied`-guarded in-place mutation with
   a single expansion into typed fields at context construction. Legal *only because m3 is
   in-process* (Constraints). (c4 §3, Unknown-unknown.)
4. **Service injection, not rewrite.** `progress_emitter`, `worker_runner`, event sink are injected;
   the fan-out loops in `execute/batch.py` are not refactored. (Anti-scope.)
5. **Handler-facing ambient reads only.** Hoist env/config reads that *handlers* perform; leave
   worker/core/cloud env reads (~22) in place.
6. **Shims preserve both `__all__`s.** No public-API break lands; `(root, args)` shims stay through
   the deprecation window.
7. **Tickets handlers carved out.** 12 ticket handlers take `(args)` only, no `root` (c4 §1,
   `tickets.py:28–149`), and read 42 CLI-shaped sites — they do **not** fit `(root, state, hctx)`
   and are explicitly not migrated by m5.

## Open questions

1. **One dataclass or two?** `HandlerContext` = `{config, services}` composite, vs. a flat context.
   Lean: composite (`hctx.config.*`, `hctx.services.*`) so the config half can be the value object
   m6/realizers consume. Decide in plan.
2. **Frozen vs. mutable config.** c4 §5 warns a frozen hctx collides with what was in-place mutation.
   Compute-once expansion (decision 3) should make frozen viable; confirm no remaining mid-run writer
   (`_agent_fallback` at `_impl.py:2432,2640` is the known offender — does it become a typed field or
   a service-side cache?).
3. **`worker_runner` interface shape.** Minimal callable matching `run_step_with_worker`'s signature,
   or a richer protocol m6 will extend? Prefer the minimal callable now; let m6 widen.
4. **Adapter ownership of `load_config`.** Does `args_to_hctx` own the single `load_config(home)` read,
   and does `resolve_agent_mode` change signature to take resolved routing, or read it off `hctx`?
   (14 `resolve_agent_mode` call sites per EPIC m2 — coordinate with m2's fail-loud slot resolution.)

## Constraints

- **m3 dependency is load-bearing.** c4's Unknown-unknown (L202–210): the *old* model spawned each
  phase as a fresh subprocess rebuilding config from `state["config"]` + profile expansion, so a
  context "built once" had **no home**. m3 makes execution in-process; the context built once now
  threads in-process. **m5 cannot start until m3 is done** (EPIC dependency graph L149,154).
- **Behavior parity is the central invariant.** The m1 parity gate stays green throughout (EPIC
  L130,156–159). Every read-relocation (env, config.json, profile expansion) must be byte-for-byte
  behavior-preserving; precedence order in `apply_profile_expansion` (live CLI > persisted CLI >
  profile, `profiles/__init__.py:1520–1529`) must be preserved exactly.
- **No public-API break may land** (decision 6). Cloud SSH coupling (`cloud/supervise.py`, s4 claim
  1) bakes import paths into shell strings — m3 re-points it onto the pinned contract; m5 must not
  reintroduce a handler-import break.
- **Coordinate with m2/m4 surfaces.** `resolve_agent_mode` is touched by both m2 (fail-loud slot
  resolution) and m5 (read routing off hctx); m4 collapses split-brain routing. Don't fight those.

## Done criteria (testable)

1. **Parity gate green on both paths.** With `MEGAPLAN_UNIFIED_DISPATCH` off → `(root, args)`; on →
   `(root, state, hctx)`. The m1 parity gate (with `extract_decision_fields` + branch coverage)
   passes identically for both. This is the central acceptance test.
2. **`HandlerContext` typed and constructed once per run** in-process; `args_to_hctx(args, state,
   services)` produces it; unit test asserts the threaded-core fields populate from a representative
   `args`.
3. **`progress_emitter`, `worker_runner`, event sink are injected** via `hctx.services`; no migrated
   handler reaches for `worker_module`/`ProgressEmitter.from_env()` as a global on the new path.
   Test: a fake `worker_runner` injected via hctx is the one invoked.
4. **Profile expansion is compute-once** on the typed surface; `_profile_applied` sentinel and the
   in-place `args.*` writes in `apply_profile_expansion` are gone on the new path; expanded
   `phase_model`/`_live_phase_model_steps`/inferred `profile` match the old in-place result
   field-for-field (parity test against fixtures).
5. **Handler-facing ambient reads hoisted:** `finalize.py:31`, `finalize.py:496`, `plan.py:117`,
   `review.py:527`, and `resolve_agent_mode`'s `load_config` read source from `hctx` on the new path;
   test injects values via hctx and confirms no `os.getenv`/`load_config` disk read fires mid-handler.
6. **Public exports preserved:** both `__all__`s (`handlers/__init__.py:75–90`, `__init__.py:48–72`)
   still import; `(root, args)` shim callers still work; a deprecation warning is emitted. Import-surface
   characterization test (`tests/characterization/test_import_surface.py`) stays green.
7. **No behavior change** anywhere else: full suite green; no golden gate expectation edited (if one
   must change, it is wrong — m5 is parity-only).

## Touchpoints

- `megaplan/handlers/context.py` (new) — `HandlerContext`, config value object, services bundle.
- `megaplan/handlers/__init__.py:75–90` — `__all__`, shim wrappers.
- `megaplan/__init__.py:48–72` — re-exported `__all__`, shims.
- `megaplan/handlers/shared.py:204` (`_run_worker`), `:219` (apply_profile_expansion call),
  `:220`/`:380`/`:347` (resolve/`_finish_step`/`_emit_receipt`), `:128–130` (`attach_agent_fallback`).
- `megaplan/handlers/{gate.py:448, execute.py:96, finalize.py:31,496,616, plan.py:45,106,117,
  review.py:480,527, init.py:262, critique.py, override.py, tiebreaker.py, verifiability.py}` —
  migrate signatures behind the toggle (NOT `tickets.py`).
- `megaplan/cli/__init__.py:1014` (`COMMAND_HANDLERS`), `:1561,1566,1574` (dispatch + progress_emitter).
- `megaplan/profiles/__init__.py:1506–1540` (`apply_profile_expansion`).
- `megaplan/workers/_impl.py:2313` (`resolve_agent_mode` config.json read at `:2382`), `:2432,2640`
  (`_agent_fallback` write).
- `megaplan/_core/io.py:734,743,764` (`config_dir`/`load_config`/`get_effective`).
- `megaplan/receipts/__init__.py:31,39` (`build_receipt(args=...)`).
- Tests: `tests/characterization/test_import_surface.py`; m1 parity gate.

## Anti-scope

- **No behavior change.** Parity gate green throughout (EPIC L130). No golden expectations edited.
- **No handler purity refactor.** gate's tiebreaker/reprompt/auto-downgrade cascade and execute's
  multi-batch/approval/session driver are **not** restructured (c4 verdict). "Pure-ish" = typed-config
  + injected-services only.
- **No Realizer.** EvidenceRealizer / `is_prose_mode` consolidation / PR #43 re-home are m6.
- **No worker/core/cloud env hoist.** The ~22 non-handler `MEGAPLAN_*` reads (NARROW_SANDBOX,
  TRUSTED_CONTAINER, Shannon timeouts, cloud/resident) stay where they are.
- **No tickets-handler migration.** 12 `(args)`-only ticket handlers are carved out.
- **No execution-model change.** That was m3; m5 assumes in-process and does not touch the driver.
- **No `resolve_agent_mode` slot-resolution rewrite** (that's m2) and **no split-brain routing
  collapse** (that's m4) — only the config/read-source relocation onto hctx.
