# M6 — Megaplan as a discovered module + the `arnold` namespace + trust boundary

**Status:** Milestone brief (re-derived to the consolidated EPIC, 2026-05-29). Authoritative scope:
`briefs/pipeline-unification-EPIC.md` — M6 entry (§156-160), Structural piece #5 the discovery trust
boundary (§115-118), "What this means for planning — it becomes a module like any other" (§44-54), and
"Proof of success" (§79-89). Grounding evidence: `validation/interrogation/SYNTHESIS.md` (Theme E +
the over-simplification "a5's low-risk verdict carried into M6 unchanged is dangerously wrong");
`validation/decision/{resident-shape,migration-fit}.md`; `validation/premortem/p1-blast-radius.md`
(the 3 next-step encodings); `validation/confidence/a5-sandbox-trust.md`.

This is the **payoff** milestone: M1-M5 built the SDK pieces; M6 collapses planning's privilege so it is
*discovered like creative/doc*, stands up the **discovery trust boundary** (the one new structural piece
this milestone owns), and proves a fourth, non-planning tool ships on the identical parts.

---

## Outcome

Planning stops being the one hardcoded built-in and becomes a discovered package, identical in shape to
`creative`/`doc`: a manifest + driver choice + the M5 bindings + a **required** `SKILL.md`. `_BUILTIN_NAMES`
is gone (`registry.py:53`); discovery no longer skips/privileges any name. Planning's builder reads as a
**composition** of the M2-M5 SDK pieces — no special execution path remains. Discovery becomes
**manifest-first and non-executing**: the import seam that is today arbitrary code execution
(`registry.py:336-339`) is gated behind an operator trust tier. The three independent next-step encodings
collapse onto M3's realized graph as the single source of truth (now SAFE — M3 proved the projection). An
`arnold` umbrella namespace stands up with one discovery surface for all drivers/packages, and `resident`
adopts the shared dispatch/emit/state pieces it currently reinvents. The bar for the whole epic is cleared
here: acceptance tests #1-#4 all green; **no binding carries `STATE_*` as mechanism**.

## Scope (M6 LOCKED — five items)

1. **Relocate planning to a discovered package.** Move `compile_planning_pipeline` (`_pipeline/planning.py:24`)
   and the planning bindings to `megaplan/pipelines/planning/` with a `build_pipeline()` entrypoint, module
   metadata (`description`/`default_profile`/`supported_modes`, read non-executing per `_module_metadata`,
   `registry.py:343`), the M5 bindings (prompts, rubrics, the 4-verdict vocab, tier map, robustness presets),
   a chosen driver, and a **`SKILL.md`** (now a required package element — fail discovery loud if absent).
   Drop `_BUILTIN_NAMES` (`registry.py:53`), its discovery skip (`registry.py:382`), the `read_skill_md`
   built-in branch (`registry.py:154`), and the `_planning_builder` programmatic registration
   (`registry.py:415,420-424`). Planning is discovered by the `arnold` discovery surface (today
   `discover_python_pipelines`, `registry.py:360`) exactly like creative/doc. **Planning COMPOSES the M2-M5
   pieces** — `build_pipeline()` reads as an assembly of dispatch/state/emit + the `patterns.py` node library
   + a declared driver, the way `doc` already composes `dynamic_fanout` (`pipelines/doc/__init__.py:66,79`).
   No `_pipeline`-vs-production split-brain: the discovered planning package IS the path real plans run
   through; the M5 process/loop/control pieces are the runtime; planning supplies only content + wiring.

2. **THE discovery trust boundary (the structural piece M6 owns).** Make discovery **manifest-first and
   non-executing**: read `name`/`driver`/`entrypoint`/declared-`capabilities`/`SKILL`-path/`arnold_api_version`
   from a static manifest WITHOUT importing, and **defer `exec_module` to selected-to-run**, gated on an
   operator trust tier (`in-tree` / `blessed` / `quarantined`). Today discovery is **eager and executing** —
   `_load_module_from_path` does `spec.loader.exec_module(module)` then `except Exception: return None`
   (`registry.py:336-339`, `# noqa: BLE001`), which on M6 success ("drop a community package in
   `~/.megaplan/pipelines`", `registry.py:375`) is **arbitrary code execution** of the author's top-level
   imports on the next `megaplan` command, since discovery funnels list/status/profile resolution; and that
   same `except: return None` makes any import error / typo'd entrypoint / (post-M6) missing `SKILL.md`
   **vanish with no error, warning, or log** (Theme E). Add an SDK-assigned `tenant_id` (not self-declared)
   + a per-package quota sub-budget reserved in the broker ledger. `arnold_api_version` is checked at
   discovery against the SDK's supported range so a package can declare which surface version it pins.
   **Re-open `a5` with the IMPORT seam in scope** — a5's "low risk" verdict examined only the runtime
   *dispatch* sandbox and explicitly never looked at the import seam (a5 §1, SYNTHESIS over-simplification);
   it is correct for shared dispatch but dangerously wrong as the sole trust analysis once external packages
   are first-class.

3. **Collapse ALL THREE next-step encodings onto M3's realized graph.** Today next-step is computed three
   ways (p1 §4, migration-fit §e7): (a) `workflow_next`/`infer_next_steps` (`_core/workflow.py:282,302`,
   the robustness-transition graph) feeding override's 9 actions, `handle_status.next_step`, doctor,
   introspect, `require_state`; (b) `InProcessHandlerStep._label_for`/`_gate_next_step`
   (`stages/inprocess_step.py:141,192` — the M5 target, the split-brain confirmed in s1); (c) the Pipeline
   graph edges (`planning.py:24+`). M6 makes **M3's realized graph (`build_topology`) the single source of
   truth**; `workflow_next` survives only as a **thin projection layer** over the realized graph that keeps
   its robustness/predicate semantics, so override, status, doctor, introspect read the same labels the
   graph produces. This is now safe **because M3 proved the projection faithful** — the realized-graph layer
   + the `{5 robustness}×{prep,feedback}×{states}×{verdicts}` parity test landed as an M3 gate
   (SYNTHESIS Theme B; EPIC §144). Recovery maps become `predecessors(stage)` on the realized graph, not a
   persisted fourth copy that drifts.

4. **Stand up the `arnold` umbrella namespace + discovery for all drivers/packages.** One discovery surface
   enumerates all packages (planning, creative/doc, the M3 `process`/`loop`/`graph` drivers, resident) under
   the `arnold` umbrella — the manifest-first reader from #2 is its front door. Keep CLI/package/on-disk
   identifiers on `megaplan` for now; `arnold` is the umbrella registry/namespace, **not** a CLI rename.

5. **Resident adopts the shared pieces it reinvents.** Resident reinvents dispatch
   (`OpenAICompatibleAgentRunner`, `agent_loop.py:151,169`), emission
   (`store.log_system_event`/`append_progress_event` + `OutboundSink`, runtime.py), and shares state already
   (the `Store`). Per resident-shape §129-144, bind to the **Protocols** (the well-chosen seam set) — wire
   resident's `AgentRunner` (Protocol, `agent_loop.py:35`) onto the `dispatch` interface (async-api backend)
   and its event writes onto the `emit` verb, WITHOUT a rewrite of its async event-loop driver.

## Locked decisions

- **No privilege, no exit, no opportunistic adoption** (EPIC §45): full extraction; planning discovered
  like any pack.
- **Discovery is manifest-first and non-executing; `exec_module` is deferred to selected-to-run and gated
  on the trust tier** (EPIC §115-118, SYNTHESIS missing-abstraction #5). The eager-execute `except: return
  None` seam is replaced, not patched.
- **M3's realized graph = single source of truth** for next-step; `workflow_next` is a projection, not a
  parallel truth (resolves the gate→TIEBREAKER→ITERATE silent-downgrade class, migration-fit §e7).
- **`SKILL.md` is a required package element** (EPIC §37,128) — discovery rejects (loudly) a package without
  one; no silent vanish.
- **`arnold` = umbrella namespace/discovery only**; commands/package/state stay `megaplan`.
- **Resident binds to Protocols, not today's exact signatures** (resident-shape §144 — expect concrete
  signatures to still move; the seam set is the binding constraint, not the method shapes).
- **No binding carries `STATE_*` as mechanism** (EPIC §160, SYNTHESIS Theme D) — the M5c control interface
  is what planning binds onto; M6 asserts the eviction is complete, mirroring the `JoinFn`→`GateRecommendation`
  eviction one layer down.

## Open questions (flag to the human)

- **Which driver does planning's manifest name — `process` or `graph` (or compose both)?** migration-fit §e2
  flags `auto.py`'s per-phase subprocess vs the in-process DAG as *different substrates*. The EPIC resolves
  the flat driver enum into 2 orthogonal axes (substrate `in_process|subprocess_isolated` × topology)
  (EPIC §123), so the manifest should name a **(substrate, topology)** pair, not one of four. The concrete
  pick is **settled by M3's outcome** — M6 must not re-litigate it. **This is the biggest open dependency.**
- Where does `workflow_next`'s projection physically live — in the `arnold` registry, M3's realized-graph
  layer, or a planning binding — given override/status/doctor/introspect all import it today?
- Does the `arnold` discovery surface replace `discover_python_pipelines` outright or wrap it as one source
  among drivers+packages?

## Constraints (back-compat & the human-recovery surface)

- **Resume of a plan created as the old built-in.** Plans on disk were created under the `planning`
  built-in; `resume_plan` (`workflow.py:339`) keys phases via `_RESUME_ACTIVE_STATES` (`workflow.py:326`,
  planning-phase literals: prep/plan/critique/gate/revise/finalize/execute/review/feedback). After
  relocation the old `planning` name and those phase keys must still resolve — keep a **name alias**
  (`planning` → relocated package) and preserve the planning phase slot names so a mid-flight resume of a
  pre-M6 plan does not orphan (p1 §2,5; EPIC §122). Also scope the 2nd/3rd subprocess drivers — `resume_plan`
  and `loop/engine.py` MegaLoop — which carry the same hardcoded phase literals (p1 §2).
- **The human-recovery surface stays intact.** The 9 override actions, `handle_status`, doctor/introspect,
  `next_step_runtime`, cost-by-phase event `phase` tags, and `feedback workflow`'s REVIEWED→DONE transition
  all read next-step labels — they must read the *projected* labels unchanged (p1 §4,5). A stuck operator
  must still get a correct recovery command.
- Honor the standing guardrails: `extra="ignore"` state load, `MEGAPLAN_*` env preserved, `handle_*`
  `__all__` shims, parity gate green and **honestly labelled** (control-flow/artifact parity on the happy
  path, not "drift provably zero" — Theme G; EPIC §121-128,179).

## Done criteria — the acceptance tests (build them, don't assert)

1. **A non-planning-shaped fourth tool ships on the SDK** (the load-bearing test, EPIC §80-83): one
   deliberately un-planning-like package — a `select`-tournament, a `snapshot/restore` search, or a
   `run(cmd)`-oracle bisect — discovered (manifest-first) + run on the identical parts. creative/doc +
   planning + resident are ALL forward-only/verdict-shaped and would never surface the gaps; only a fourth,
   differently-shaped thing is honest proof "others can build a fourth thing." Plus the SYNTHESIS check:
   **no toy hand-rolls inter-step plumbing** (all data crosses a declared Port).
2. **A new simple pipeline is cheap** (EPIC §84): `jokes`/a stub upgraded to a *real* SDK pipeline (~50
   lines domain code + "I'm a `graph` driver, I need `dispatch`+`emit`"), not a hand-wired stub.
3. **Planning reads as composition, not as the SDK** (EPIC §86-88): a reader points at planning and says
   "`iterate` is just planning's binding of `revise_in_place`" — the 4 verdicts are the planning app's, not
   the SDK's only reduce output.
4. **The two existing apps name which SDK pieces they adopt without a rewrite** (EPIC §89): planning
   (extracted in full) and resident (dispatch+emit+state) each enumerated.

Plus the M6-specific gate: `_BUILTIN_NAMES` removed; planning discovered manifest-first; **discovery is
non-executing until selected-to-run, gated on the trust tier; a re-opened a5 covers the import seam;
`arnold_api_version` checked; missing-`SKILL.md`/import-error packages surface (no silent vanish)**; all
three next-step encodings collapsed onto M3's realized graph with `workflow_next` as a thin projection;
`arnold` namespace + discovery live; **no binding carries `STATE_*` as mechanism**; parity gate green.

## Touchpoints

- `megaplan/_pipeline/registry.py:53` (`_BUILTIN_NAMES`), `:154` (`read_skill_md` built-in branch),
  `:336-339` (the `exec_module` + `except: return None` ACE seam + silent-vanish — replace with manifest-first
  non-executing read), `:343` (`_module_metadata`), `:360` (`discover_python_pipelines`), `:375`
  (`~/.megaplan/pipelines` user root — the untrusted-author entry), `:382` (built-in skip),
  `:415,420-424` (`_planning_builder` registration).
- `megaplan/_pipeline/planning.py:24` (`compile_planning_pipeline`) → `megaplan/pipelines/planning/__init__.py`
  (+ `steps.py`, `prompts/`, `SKILL.md`) following the `doc` package layout (`pipelines/doc/__init__.py:66,79,119`).
- `megaplan/_core/workflow.py:282,302` (`workflow_next`/`infer_next_steps` → projection over M3's realized
  graph), `:326` (`_RESUME_ACTIVE_STATES`), `:339` (`resume_plan` alias + slot preservation), `:315`
  (`_default_resume_runner`, the 2nd subprocess driver).
- `megaplan/_pipeline/stages/inprocess_step.py:141,192` (`_label_for`/`_gate_next_step` removed — encoding
  (b) collapsed onto the realized graph).
- `megaplan/resident/agent_loop.py:35` (`AgentRunner` Protocol — bind here), `:151,169`
  (`OpenAICompatibleAgentRunner.run` onto `dispatch`), resident emit sites
  (`store.log_system_event`/`append_progress_event`, `runtime.py` `OutboundSink`).
- New: the `arnold` umbrella namespace + manifest-first discovery surface (wraps/replaces
  `discover_python_pipelines`); the trust-tier evaluator + `arnold_api_version` check; the per-package
  `tenant_id`/quota sub-budget reservation in the broker ledger.
- New: the fourth non-planning package + `jokes` upgraded to a real SDK pipeline.

## Anti-scope

- NOT a CLI/package/on-disk-identifier rename — `megaplan …`, `import megaplan`, `.megaplan/`, `MEGAPLAN_*`,
  `~/Documents/megaplan` all stay. `arnold` is the umbrella registry/namespace only.
- NOT a rewrite of resident's async event-loop driver — adopt dispatch/emit/state at the Protocol seam only.
- NOT re-litigating the M2-M5 piece designs (types de-planning-izing, the realized graph, drivers,
  dispatch/emit/evidence, the policy spine, the M5c control interface) — M6 *consumes* them. In particular
  M6 does NOT re-pick the driver substrate — M3's outcome settles it.
- NOT shipping new pipeline branches or new SDK primitives; M6 is relocation + the trust boundary + the
  next-step collapse + the `arnold` namespace + resident adoption + the fourth-tool proof — not abstraction
  work.
- NOT the deferred items (symmetric Realizer Protocol, full 81-field HandlerContext, PR#43 re-home).
