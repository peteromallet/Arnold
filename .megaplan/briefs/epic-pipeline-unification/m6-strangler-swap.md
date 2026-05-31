# M6 — THE STRANGLER SWAP: megaplan as a discovered module + `arnold` namespace + trust boundary + journal unification + R7 load-bearing

**Status:** Milestone brief, re-aimed onto the sequenced program (2026-05-29). Authoritative scope:
`.megaplan/briefs/validation/sequencing/PROGRAM.md` M6 entry (§270-289, the LAST load-bearing node), the
critical-path apex/discipline (§336-415), and open-risk #5 (§448-453). Architecture: the eleven organs +
seven reshapers of `.megaplan/briefs/pipeline-unification-EPIC.md` (§23-84, "Sequenced build program — FINAL"
§225-258). Organ specs: `.megaplan/briefs/validation/committed-uu/SYNTHESIS.md` (R5 one-Ledger §374-377; R7
model-identity §385-388; the Manifest §297-306, R6; the trust/Contract organs §267-273). Human-blocker
defaults: `.megaplan/briefs/validation/human-blockers/REGISTER.md` (M6 row §70-72, trust-tier policy §97-101, M6
open-question resolutions §112). CLI migration: `.megaplan/briefs/validation/edges/cli-migration.md`. Prior draft
re-aimed: `.megaplan/briefs/epic-pipeline-unification/m6-megaplan-as-module.md` (cites re-verified against current
code).

**This is the deferred strangler SWAP** — the single deletion that removes the old path's root and the
one irreversible self-reference change (the ship-of-Theseus killzone). It lands LAST among load-bearing
nodes, one atomic oracle-gated cutover, so there is never a multi-week broken window. Everything
underneath (M3 driver/log, M4 services/one-Ledger, M5b execute, M5c control plane, M5-eval/cal) is
proven before the root is removed.

---

## Outcome

Planning stops being the one hardcoded built-in and becomes a discovered package identical in shape to
`creative`/`doc`: a static manifest + a `build_pipeline()` entrypoint + the M5 bindings + a **required**
`SKILL.md` + a chosen `(substrate, topology)` driver. `_BUILTIN_NAMES` is gone (`registry.py:53`);
discovery privileges no name and is **manifest-first and non-executing** — the import seam that is today
arbitrary code execution on every `megaplan` command (`registry.py:336-339`) is deferred to
selected-to-run and gated on a path-derived trust tier. Planning's builder reads as a **composition** of
the M2-M5 SDK pieces — no special execution path remains. The three independent next-step encodings
collapse onto M3's realized graph as the single source of truth (now SAFE — M3 proved the projection).
The two disjoint journals unify into the one M4 Ledger (R5 completion). R7 becomes load-bearing —
routing consumes the hash-pinned model-identity. An `arnold` umbrella namespace + the CLI migration land
behind the deferred-rename alias. `resident` adopts the shared dispatch/emit pieces it currently
reinvents. **The OLD subprocess seam is RETIRED here** — but only after the discovered-planning full
dual-run oracle is green; the `megaplan <x>` aliases stay as fallback until then.

## Scope (work items tied to current file:line)

1. **Relocate planning to a discovered package.** Move `compile_planning_pipeline`
   (`megaplan/_pipeline/planning.py:24`) and the planning bindings to
   `megaplan/pipelines/planning/` with a `build_pipeline()` entrypoint, static module metadata
   (`description`/`default_profile`/`supported_modes`, read non-executing per `_module_metadata`,
   `registry.py:343`), the M5 bindings (prompts, rubrics, the 4-verdict vocab, tier map, robustness
   presets), the chosen driver, and a required `SKILL.md` — following the `doc` layout (`build_pipeline`
   at `pipelines/doc/__init__.py:66`, composing `dynamic_fanout` from `patterns.py`). Drop
   `_BUILTIN_NAMES` (`registry.py:53`), its discovery skip (`registry.py:382`), the `read_skill_md`
   built-in branch (`registry.py:154`), and the `_planning_builder` programmatic registration
   (`registry.py:415,420-424`). Planning is discovered by the `arnold` discovery surface exactly like
   creative/doc. **Planning COMPOSES the M2-M5 pieces** — `build_pipeline()` reads as an assembly of
   dispatch/state/emit + the `patterns.py` node library + a declared driver; planning supplies only
   content + wiring. The M5 process/loop/control pieces ARE the runtime; the discovered package IS the
   path real plans run through (no `_pipeline`-vs-production split-brain).

2. **THE discovery trust boundary (the structural piece M6 owns).** Make discovery manifest-first and
   non-executing: read `name`/`driver`/`entrypoint`/declared-`capabilities`/`SKILL`-path/`arnold_api_version`
   from a static manifest WITHOUT importing, and **defer `exec_module` to selected-to-run**. Today
   `_load_module_from_path` does `spec.loader.exec_module(module)` then `except Exception: return None`
   (`registry.py:336-339`, `# noqa: BLE001`) — on M6 success ("drop a package in `~/.megaplan/pipelines`",
   `registry.py:21,375`) that is **ACE** of the author's top-level imports on the next `megaplan`
   command (discovery funnels list/status/profile resolution), and that same `except: return None` makes
   any import error / typo'd entrypoint / missing `SKILL.md` **vanish silently** (Theme E). Replace, do
   not patch. Compute trust from origin (path-derived, no prompt): `in-tree` (repo/installed-dist) =
   trusted, auto-exec on selection; `out-of-tree`/`~/.megaplan/pipelines` = quarantined-by-default
   (manifest-only, no exec, SDK-assigned `tenant_id = hash(name + install_path)`, capped per-package
   quota reserved in the M4 broker ledger); `blessed` = explicit allowlist, default empty, auto-promoted
   only on passing the graph-abuse oracle. `arnold_api_version` checked at discovery against the SDK's
   supported range without importing.

3. **Collapse ALL THREE next-step encodings onto M3's realized graph.** Today next-step is computed three
   ways: (a) `workflow_next` (`_core/workflow.py:282`; `infer_next_steps = workflow_next` alias at `:302`)
   feeding override, `handle_status.next_step`, doctor, introspect, `require_state`; (b)
   `InProcessHandlerStep._label_for`/`_gate_next_step` (`stages/inprocess_step.py:141,192`); (c) the
   Pipeline graph edges (`planning.py:24+`). M6 makes **M3's realized graph (`build_topology`) the single
   source of truth**; `workflow_next` survives only as a **thin projection layer** over the realized
   graph (re-exported at its old path, `register §112`) keeping its robustness/predicate semantics, so
   override/status/doctor/introspect read the same labels the graph produces. Safe now because M3 landed
   the `{5 robustness}×{prep,feedback}×{states}×{verdicts}` parity test as a gate. Remove
   `_label_for`/`_gate_next_step` (encoding (b)); recovery maps become `predecessors(stage)` on the
   realized graph, not a persisted fourth copy.

4. **Unify the two disjoint journals into the one Ledger (R5 completion).** Today two journals coexist —
   `events.ndjson` (filesystem/presentation) vs the DB `EpicEvent`/`epic_events` (content-hashed) — with
   no shared schema/ID-space/join-key, and surfaces re-derive truth heuristically (SYNTHESIS §187-191,
   R5 §374-377). M4 stood up the single `EventSink.emit(kind,payload,scope)` write path and the one
   content-addressed Ledger as the authoritative spine (report-only schema until this milestone). M6
   flips journal unification to load-bearing: every surface READS the one Ledger, nothing recomputes;
   the `events.ndjson` path becomes a projection of the one log, not a parallel truth.

5. **R7 made load-bearing (model-identity is a hash-pinned provenance fact).** The R7 receipt field was
   seeded at M1 with no consumer. M6 makes routing CONSUME the hash-pinned model-identity (SYNTHESIS
   reshaper #7, §385-388): the cache key, the journal, and the routing telemetry key on
   `(prompt_hash, model_version, params)` so a model that drifts behind a stable name is a recorded
   version event, not a silent replay lie.

6. **Stand up the `arnold` umbrella namespace + CLI migration.** One discovery surface enumerates all
   packages (planning, creative/doc, the M3 `process`/`loop`/`graph` drivers, resident) under the
   `arnold` umbrella; the manifest-first reader from #2 is its front door — it **WRAPS**
   `discover_python_pipelines` (`registry.py:360`), not replaces it (`register §112`). Per
   `cli-migration.md`: introduce `arnold <umbrella-verb>` (SDK/runtime/any-run: `run`, `pipelines
   list/check/doctor`, the per-run inspectors) + `arnold <module> <verb>` (`arnold planning gate`);
   `arnold auto [module=planning]`; split `override` along the umbrella (abort/add-note/set-*) vs
   planning (force-proceed/replan/recover-blocked) seam; `resume` stays planning. Adopt the brief's own
   resolutions as a parser-snapshot fixture so drift auto-fails CI.

7. **Resident adopts the shared pieces it reinvents.** Wire resident's `AgentRunner` (Protocol,
   `resident/agent_loop.py:34-35`) onto the M4 `dispatch` interface (async-api backend; today
   `OpenAICompatibleAgentRunner.run` at `agent_loop.py:151,169`) and its event writes
   (`store.log_system_event`/`append_progress_event` + `OutboundSink`, runtime.py) onto the `emit` verb —
   bind to the **Protocols**, WITHOUT a rewrite of resident's async event-loop driver.

8. **RETIRE the OLD subprocess seam.** Delete the dormant subprocess state-machine path (`auto.py`
   per-phase subprocess driver + the `_run_megaplan` seam) — but ONLY after the discovered-planning full
   dual-run milestone is green (Done criteria, the oracle gate). No organ-swap + old-path-deletion in one
   PR: the relocation/discovery/journal-unification swap lands first behind the flag; the deletion is a
   separate PR gated on the dual-run oracle.

## Locked decisions

- **No privilege, no exit, no opportunistic adoption** (EPIC §128): full extraction; planning discovered
  like any pack.
- **Discovery is manifest-first and non-executing; `exec_module` deferred to selected-to-run and gated on
  the trust tier** (SYNTHESIS missing-abstraction #5). The eager `except: return None` seam is replaced.
- **Trust tier is path-derived, never a prompt** (REGISTER §97-101): in-tree=auto-exec, out-of-tree/user-pack=quarantined-by-default, blessed=allowlist-default-empty; new capability KINDs default to DENY.
- **M3's realized graph = single source of truth** for next-step; `workflow_next` is a projection re-exported at its old path, not a parallel truth.
- **`SKILL.md` is a required package element** (REGISTER §72) — discovery rejects loudly without one; `pipelines check` exits non-zero; no silent vanish.
- **The OLD subprocess seam is the ONE atomic deletion, separate from the swap PR, gated on the discovered-planning full dual-run oracle** (PROGRAM §448-453); `megaplan <x>` aliases stay as fallback until that oracle is green.
- **`arnold` = umbrella namespace/discovery + CLI topology only**; the binary/package/on-disk state stay `megaplan` until the deferred-rename trigger (`cli-migration.md` §6-13).
- **The Behavioral Identity Manifest (R6, landed M5a) pins discovery identity** — a package's runnable identity is its Manifest hash, not its name; resume keys on it (chimera defense, SYNTHESIS §297-306).
- **Resident binds to Protocols, not today's exact signatures.**
- **No binding carries `STATE_*` as mechanism** (EPIC §197) — planning binds onto the M5c control interface; M6 asserts the eviction complete, mirroring `JoinFn`→`GateRecommendation` (`pattern_types.py:16-19`).

## Open questions (each RESOLVED to its default — zero human blockers)

- **Which `(substrate, topology)` does planning's manifest name?** → **The manifest names the
  `(subprocess_isolated, graph+loop-node)` pair M3 already resolved** (REGISTER §112). M6 READS M3's
  outcome; it does NOT re-pick the substrate (anti-scope).
- **Where does `workflow_next`'s projection physically live, given override/status/doctor/introspect all
  import it today?** → **Thin projection over M3's realized graph, re-exported at its old
  `_core/workflow.py:282` path** so all callers keep importing the same symbol (REGISTER §112).
- **Does `arnold` discovery replace or wrap `discover_python_pipelines`?** → **WRAPS it** as one source
  among drivers+packages (REGISTER §112).
- **`arnold_api_version` range + out-of-range behavior?** → range `[1.0, current-major)`, **out-of-range
  rejected loudly at discovery** (REGISTER §112).
- **The fourth non-planning tool + the cheap-pipeline proof?** → fourth tool = a `select`-tournament
  (shared with M7); cheap new pipeline = upgrade `jokes` to a real SDK pipeline (REGISTER §112).
- **Theme-E silent-vanish on a bad package?** → loud catalogued discovery error, exclude from the runnable
  set, surface in doctor/check, proceed with the rest (REGISTER §71).
- **First-ever NEW capability KIND in a community manifest?** → DENY by default; package stays quarantined,
  runs without it; allowlist grows only via versioned code change (REGISTER §83).
- **Resume of a pre-M6 plan created under the `planning` built-in?** → keep a **name alias** (`planning` →
  relocated package) and preserve the planning phase slot names so `resume_plan`
  (`_core/workflow.py:339`, keyed via `_RESUME_ACTIVE_STATES` at `:326`) does not orphan; scope the 2nd
  subprocess driver `_default_resume_runner` (`:315`) and the 3rd, `loop/engine.py` MegaLoop (hardcoded
  phase literals, `engine.py:464,483,543`) under the same alias.

## Constraints

- **Strangler discipline, machine-gated (PROGRAM §361-389):** at M6 close, (OLD alive) the pinned/frozen
  external engine still self-hosts a throwaway 1-milestone plan (`--no-git-refresh`, schema report-only,
  flag-OFF); (NEW alive) the discovered-planning path runs the behavioral-replay oracle green against
  recorded REAL-run traces (recovery/escalate/blocked included). The swap lands behind a default-OFF
  flag; the old-path deletion is a separate, oracle-gated PR.
- **The behavioral-replay + substrate-swap oracle is the SOLE retirement authority** — never the
  happy-path parity gate (honest label: "happy-path control-flow/artifact parity, NOT drift-provably-zero").
  M6's substrate-swap oracle is the **discovered-planning full dual-run** (PROGRAM §386).
- **The human-recovery surface stays intact** — the 9 override actions (`handlers/override.py`),
  `handle_status`, doctor/introspect, `next_step_runtime`, cost-by-phase `phase` tags, and `feedback
  workflow`'s REVIEWED→DONE transition all read the *projected* labels unchanged; a stuck operator still
  gets a correct recovery command.
- **Untrusted code never executes on import; runs only quarantined** with an SDK-assigned `tenant_id` +
  capped quota; promotion is a passed graph-abuse oracle (REGISTER §138-140).
- **Standing guardrails:** `extra="ignore"` state load, 26 `MEGAPLAN_*` env preserved, `handle_*`
  `__all__` shims, the `cloud/cli.py:225-227` `_phase_command` shim still resolves.
- **Autonomy / no human wait:** every gate auto-proceeds on green, auto-halts/auto-reverts or runs the
  bounded ladder on red (retry ×2 → bump profile/robustness one tier → `stop_chain` + auto-ticket).

## Done criteria (testable; incl. the oracle gate)

1. **The oracle gate — discovered-planning full dual-run is green.** A planning-shaped throwaway plan
   runs end-to-end on the discovered package behind the flag and the behavioral-replay oracle confirms it
   matches recorded real-run traces (recovery/escalate/blocked, NOT just happy-path mock parity). **Only
   on this green is the OLD subprocess seam deleted** (a separate PR). Red → auto-halt + revert + the
   bounded ladder; the `megaplan <x>` aliases stay live.
2. **A non-planning-shaped fourth tool ships on the SDK** — a `select`-tournament — discovered
   manifest-first and run on the identical parts (the load-bearing test, EPIC §163-166). SYNTHESIS check:
   **no toy hand-rolls inter-step plumbing** (all data crosses a declared Port).
3. **A new simple pipeline is cheap** — `jokes` upgraded to a real SDK pipeline (~50 lines domain code +
   "I'm a `graph` driver, I need `dispatch`+`emit`"), not a hand-wired stub.
4. **Planning reads as composition, not as the SDK** — a reader points at planning and says "`iterate` is
   just planning's binding of `revise_in_place`"; the 4 verdicts are the planning app's, not the SDK's
   only reduce output.
5. **The two existing apps name which SDK pieces they adopt without a rewrite** — planning (extracted in
   full) and resident (dispatch+emit+state) each enumerated.
6. **M6-specific gate:** `_BUILTIN_NAMES` removed; planning discovered manifest-first; discovery
   non-executing until selected-to-run, gated on the trust tier; `a5` re-opened with the import seam in
   scope; `arnold_api_version` range-checked; missing-`SKILL.md`/import-error packages surface (no silent
   vanish); all three next-step encodings collapsed onto M3's realized graph with `workflow_next` as a
   thin projection; the two journals unified into the one Ledger; R7 routing consumes the hash-pinned
   model-identity; `arnold` namespace + CLI migration live behind the deferred-rename alias with a
   parser-snapshot fixture; **no binding carries `STATE_*` as mechanism**; parity gate green and honestly
   labelled.

## Touchpoints

- `megaplan/_pipeline/registry.py:53` (`_BUILTIN_NAMES`), `:154` (`read_skill_md` built-in branch),
  `:336-339` (the `exec_module` + `except: return None` ACE + silent-vanish — replace with manifest-first
  non-executing read), `:343` (`_module_metadata`), `:360` (`discover_python_pipelines` — WRAP), `:375`
  (`~/.megaplan/pipelines` untrusted-author entry), `:382` (built-in skip), `:415,420-424`
  (`_planning_builder` registration).
- `megaplan/_pipeline/planning.py:24` (`compile_planning_pipeline`) → `megaplan/pipelines/planning/`
  (`__init__.py:build_pipeline`, `steps.py`, `prompts/`, `SKILL.md`), following `pipelines/doc/__init__.py:66`.
- `megaplan/_core/workflow.py:282` (`workflow_next` → projection over M3's realized graph), `:302`
  (`infer_next_steps` alias), `:326` (`_RESUME_ACTIVE_STATES`), `:339` (`resume_plan` alias + slot
  preservation), `:315` (`_default_resume_runner`, 2nd subprocess driver).
- `megaplan/loop/engine.py:464,483,543` (MegaLoop hardcoded phase literals — 3rd subprocess driver).
- `megaplan/_pipeline/stages/inprocess_step.py:141,192` (`_label_for`/`_gate_next_step` removed —
  encoding (b) collapsed).
- `megaplan/resident/agent_loop.py:34-35` (`AgentRunner` Protocol — bind here), `:151,169`
  (`OpenAICompatibleAgentRunner.run` onto `dispatch`); resident emit sites.
- `megaplan/handlers/override.py:218` (`strict_notes`), the force-proceed actions — read projected labels.
- `megaplan/cloud/cli.py:225-227` (`_phase_command` shim — keep resolving).
- `megaplan/_pipeline/pattern_types.py:16-19` (`GateRecommendation`/`JoinFn` — assert `STATE_*` eviction
  mirrors the already-evicted enum).
- New: the `arnold` umbrella namespace + manifest-first discovery surface (wraps `discover_python_pipelines`);
  the trust-tier evaluator + `arnold_api_version` check; the per-package `tenant_id`/quota reservation in
  the M4 broker ledger; the journal-unification projection; the R7 routing consumer; the fourth
  `select`-tournament package + `jokes` upgrade; the parser-snapshot fixture (`cli-migration.md`).

## Anti-scope

- NOT a binary/package/on-disk-identifier rename — `megaplan …`, `import megaplan`, `.megaplan/`,
  `MEGAPLAN_*`, `~/Documents/megaplan` all stay. `arnold` is the umbrella namespace + CLI topology only.
- NOT re-picking the driver substrate — M3's outcome settles the `(substrate, topology)` pair; M6 reads it.
- NOT a rewrite of resident's async event-loop driver — adopt dispatch/emit/state at the Protocol seam only.
- NOT re-litigating the M2-M5 piece designs (types, realized graph, drivers, dispatch/emit/evidence, the
  policy spine, Effect Ledger, Evaluand/Calibration, the M5c control interface) — M6 *consumes* them.
- NOT building the M5d supervisor tier (runs ∥ M6 / after, gates on M6's relocation) nor the M7 sinks
  (Capsule / Warrant / docs).
- NOT shipping new SDK primitives or new pipeline branches; M6 is relocation + trust boundary + next-step
  collapse + journal unification + R7 + `arnold` namespace + resident adoption + the fourth-tool proof +
  the old-seam retirement — not abstraction work.
- NOT deleting the old subprocess seam in the same PR as the swap, and NOT deleting it before the
  discovered-planning dual-run oracle is green.
